import asyncio
import logging
import shutil
import threading
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.handlers import CallbackQueryHandler, MessageHandler

from Services.file2link import File2LinkError, package_for_upload
from Services.nixfile import NixfileError
from Utils.html import safe
from Utils.keyboards import cancel_keyboard, main_keyboard, multi_link_keyboard
from Utils.progress import SnapshotProgress
from Utils.texts import (
    BUSY_TEXT,
    CANCELLED_TEXT,
    FAILED_TEXT,
    FILE2LINK_DOWNLOADING_TEXT,
    FILE2LINK_NO_FILE_TEXT,
    FILE2LINK_PACKAGING_TEXT,
    FILE2LINK_PROMPT_TEXT,
    FILE2LINK_READY_MULTI_TEXT,
    FILE2LINK_READY_SINGLE_TEXT,
    FILE2LINK_UPLOADING_TEXT,
    NIXFILE_DISABLED_TEXT,
    NIXFILE_UPLOAD_TITLE,
    USER_BUSY_TEXT,
)

logger = logging.getLogger(__name__)


class File2LinkStates(StatesGroup):
    waiting_file = State()


router = Router(name="file2link")


@router.callback_query(F.data == "file2link")
class File2LinkStartCallback(CallbackQueryHandler):
    async def handle(self) -> Any:
        await self.event.answer()
        if not self.message:
            return

        settings = self.data["settings"]
        state: FSMContext = self.data["state"]
        await state.set_state(File2LinkStates.waiting_file)

        text = FILE2LINK_PROMPT_TEXT.format(limit_mb=settings.nixfile_max_file_mb)
        try:
            prompt = await self.message.edit_text(text, reply_markup=cancel_keyboard())
        except TelegramBadRequest:
            prompt = await self.message.answer(text, reply_markup=cancel_keyboard())

        if prompt is not None:
            await state.update_data(
                prompt_chat_id=prompt.chat.id,
                prompt_message_id=prompt.message_id,
            )


@router.callback_query(StateFilter(File2LinkStates.waiting_file), F.data == "cancel")
class File2LinkCancelCallback(CallbackQueryHandler):
    async def handle(self) -> Any:
        await self.event.answer("لغو شد")
        state: FSMContext = self.data["state"]
        await state.clear()

        if not self.message:
            return
        try:
            await self.message.edit_text(CANCELLED_TEXT, reply_markup=main_keyboard())
        except TelegramBadRequest:
            await self.message.answer(CANCELLED_TEXT, reply_markup=main_keyboard())


@router.message(StateFilter(File2LinkStates.waiting_file), F.text)
class File2LinkTextHandler(MessageHandler):
    async def handle(self) -> Any:
        await self.event.answer(FILE2LINK_NO_FILE_TEXT, reply_markup=cancel_keyboard())


@router.message(StateFilter(File2LinkStates.waiting_file), F.document)
class File2LinkDocumentHandler(MessageHandler):
    async def handle(self) -> Any:
        state: FSMContext = self.data["state"]
        settings = self.data["settings"]
        job_runner = self.data["job_runner"]

        if job_runner.user_busy(self.from_user.id):
            await self.event.answer(USER_BUSY_TEXT, reply_markup=main_keyboard())
            return
        if not job_runner.available:
            await self.event.answer(BUSY_TEXT, reply_markup=main_keyboard())
            return

        data = await state.get_data()
        await state.clear()

        prompt_chat_id = data.get("prompt_chat_id")
        prompt_message_id = data.get("prompt_message_id")
        if prompt_chat_id and prompt_message_id:
            with suppress(TelegramBadRequest):
                await self.event.bot.delete_message(prompt_chat_id, prompt_message_id)

        document = self.event.document
        original_name = document.file_name or f"file_{document.file_unique_id}"
        status_message = await self.event.answer(FILE2LINK_DOWNLOADING_TEXT)

        work_dir = settings.download_dir / f"file2link-{self.from_user.id}-{int(time.time())}"
        work_dir.mkdir(parents=True, exist_ok=True)
        source_path = work_dir / original_name

        await job_runner.run(
            self.from_user.id,
            _process(
                bot=self.event.bot,
                document=document,
                source_path=source_path,
                work_dir=work_dir,
                status_message=status_message,
                settings=settings,
                uploader=self.data.get("nixfile_uploader"),
            ),
        )


async def _process(
    *,
    bot,
    document,
    source_path: Path,
    work_dir: Path,
    status_message,
    settings,
    uploader,
) -> None:
    cleanup_paths: list[Path] = []
    try:
        if uploader is None or not uploader.enabled:
            await status_message.edit_text(NIXFILE_DISABLED_TEXT, reply_markup=main_keyboard())
            return

        await bot.download(document, destination=source_path)
        cleanup_paths.append(source_path)

        await status_message.edit_text(FILE2LINK_PACKAGING_TEXT)
        try:
            parts = await package_for_upload(source_path, work_dir, settings)
        except File2LinkError as exc:
            await status_message.edit_text(
                FAILED_TEXT.format(error=safe(exc)),
                reply_markup=main_keyboard(),
            )
            return

        for part in parts:
            if part != source_path and part not in cleanup_paths:
                cleanup_paths.append(part)

        urls: list[str] = []
        total = len(parts)
        for index, part in enumerate(parts, start=1):
            label = part.name
            await status_message.edit_text(
                FILE2LINK_UPLOADING_TEXT.format(index=index, total=total)
                + f"\n{label}"
            )
            upload_started = threading.Event()
            progress = SnapshotProgress(
                status_message, NIXFILE_UPLOAD_TITLE, label, uploader.progress_snapshot
            )
            progress_started = False

            async def watch_start() -> None:
                nonlocal progress_started
                while not upload_started.is_set():
                    await asyncio.sleep(0.3)
                progress.start()
                progress_started = True

            watcher = asyncio.create_task(watch_start())
            try:
                url = await uploader.upload(part, upload_started=upload_started)
            except NixfileError as exc:
                watcher.cancel()
                if progress_started:
                    await progress.stop()
                await status_message.edit_text(
                    FAILED_TEXT.format(error=safe(exc)),
                    reply_markup=main_keyboard(),
                )
                return
            else:
                watcher.cancel()
                if progress_started:
                    await progress.stop(percent=100)
            urls.append(url)

        if total == 1:
            ready = FILE2LINK_READY_SINGLE_TEXT.format(name=safe(parts[0].name))
        else:
            ready = FILE2LINK_READY_MULTI_TEXT.format(
                name=safe(document.file_name or "file"),
                count=total,
            )
        await status_message.edit_text(ready, reply_markup=multi_link_keyboard(urls))

    except Exception as exc:
        logger.exception("file2link pipeline failed")
        with suppress(Exception):
            await status_message.edit_text(
                FAILED_TEXT.format(error=safe(exc)),
                reply_markup=main_keyboard(),
            )
    finally:
        if not getattr(settings, "keep_files", True):
            for path in cleanup_paths:
                with suppress(Exception):
                    if path.exists():
                        path.unlink()
            with suppress(Exception):
                if work_dir.exists() and not any(work_dir.iterdir()):
                    shutil.rmtree(work_dir, ignore_errors=True)
