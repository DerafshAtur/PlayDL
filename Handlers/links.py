import asyncio
import logging
import threading
from contextlib import suppress
from pathlib import Path
from typing import Any

from aiogram import F, Router
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.handlers import CallbackQueryHandler, MessageHandler
from aiogram.types import FSInputFile

logger = logging.getLogger(__name__)

from Services.extract import extract_package_name, is_google_play_url
from Services.nixfile import NixfileError
from Services.pipeline import run_download_pipeline
from Services.rubika import RubikaError
from Services.sweeper import is_nixfile_url_alive
from Utils.html import bold, safe
from Utils.keyboards import (
    cancel_keyboard,
    delivery_keyboard,
    link_keyboard,
    main_keyboard,
)
from Utils.progress import AnimatedProgress, SnapshotProgress
from Utils.texts import (
    BAD_LINK_TEXT,
    BUSY_TEXT,
    CANCELLED_TEXT,
    DONE_TEXT,
    FAILED_TEXT,
    JOB_NOT_FOUND_TEXT,
    LINK_READY_TEXT,
    NIXFILE_DISABLED_TEXT,
    NIXFILE_PREPARING_TEXT,
    NIXFILE_QUOTA_TEXT,
    NIXFILE_TOO_BIG_TEXT,
    NIXFILE_UPLOAD_TITLE,
    RUBIKA_DELIVERED_TEXT,
    RUBIKA_DISABLED_TEXT,
    RUBIKA_PROMPT_USERNAME_TEXT,
    RUBIKA_TOO_BIG_TEXT,
    RUBIKA_UPLOADING_TEXT,
    RUBIKA_USERNAME_INVALID_TEXT,
    RUBIKA_USER_NOT_FOUND_TEXT,
    SEND_LINK_TEXT,
    UPLOAD_TITLE,
    USER_BUSY_TEXT,
)


class RubikaDeliveryStates(StatesGroup):
    waiting_username = State()

router = Router(name="links")


def _maybe_delete_after_upload(settings, apk_path: Path) -> None:
    if getattr(settings, "keep_files", True):
        return
    with suppress(Exception):
        if apk_path.exists():
            apk_path.unlink()
            logger.info("KEEP_FILES=false, deleted %s after upload", apk_path)


@router.callback_query(F.data == "send_link")
class SendLinkCallback(CallbackQueryHandler):
    async def handle(self) -> Any:
        await self.event.answer()
        if not self.message:
            return

        try:
            await self.message.edit_text(SEND_LINK_TEXT, reply_markup=cancel_keyboard())
        except TelegramBadRequest:
            await self.message.answer(SEND_LINK_TEXT, reply_markup=cancel_keyboard())


@router.callback_query(F.data == "cancel")
class CancelCallback(CallbackQueryHandler):
    async def handle(self) -> Any:
        await self.event.answer("لغو شد")
        if not self.message:
            return

        try:
            await self.message.edit_text(CANCELLED_TEXT, reply_markup=main_keyboard())
        except TelegramBadRequest:
            await self.message.answer(CANCELLED_TEXT, reply_markup=main_keyboard())


@router.message(F.text)
class GooglePlayLinkHandler(MessageHandler):
    async def handle(self) -> Any:
        text = (self.event.text or "").strip()
        if not is_google_play_url(text):
            await self.event.answer(BAD_LINK_TEXT, reply_markup=main_keyboard())
            return

        package_name = extract_package_name(text)
        if not package_name:
            await self.event.answer(BAD_LINK_TEXT, reply_markup=main_keyboard())
            return

        job_runner = self.data["job_runner"]
        if job_runner.user_busy(self.from_user.id):
            await self.event.answer(USER_BUSY_TEXT, reply_markup=main_keyboard())
            return
        if not job_runner.available:
            await self.event.answer(BUSY_TEXT, reply_markup=main_keyboard())
            return

        await job_runner.run(
            self.from_user.id,
            run_download_pipeline(
                event_message=self.event,
                user_id=self.from_user.id,
                url=text,
                package_name=package_name,
                deps=self.data,
            ),
        )


@router.callback_query(F.data.startswith("deliver:"))
class DeliveryCallback(CallbackQueryHandler):
    async def handle(self) -> Any:
        await self.event.answer()
        if not self.message:
            return

        try:
            _, mode, job_id_str = (self.event.data or "").split(":", 2)
            job_id = int(job_id_str)
        except (ValueError, AttributeError):
            await self.message.edit_text(JOB_NOT_FOUND_TEXT, reply_markup=main_keyboard())
            return

        db = self.data["db"]
        job = await db.get_job(job_id)
        if not job or not job.get("apk_path"):
            await self.message.edit_text(JOB_NOT_FOUND_TEXT, reply_markup=main_keyboard())
            return

        apk_path = Path(job["apk_path"])
        package_name = job.get("package_name", "")
        package_label = bold(package_name)

        if not apk_path.exists():
            await db.update_job(job_id, "failed", error="apk_missing")
            await self.message.edit_text(JOB_NOT_FOUND_TEXT, reply_markup=main_keyboard())
            return

        if mode == "tg":
            await self._deliver_telegram(job_id, apk_path, package_label)
        elif mode == "nx":
            settings = self.data["settings"]
            limit = int(getattr(settings, "limit_daily_ir", 0) or 0)
            if limit > 0:
                used = await db.count_user_nixfile_today(self.from_user.id)
                if used >= limit:
                    await self.message.edit_text(
                        NIXFILE_QUOTA_TEXT.format(limit=limit),
                        reply_markup=delivery_keyboard(job_id),
                    )
                    return
            max_mb = int(getattr(settings, "nixfile_max_file_mb", 0) or 0)
            if max_mb > 0 and apk_path.exists():
                size_mb = apk_path.stat().st_size / (1024 * 1024)
                if size_mb > max_mb:
                    await self.message.edit_text(
                        NIXFILE_TOO_BIG_TEXT.format(size_mb=size_mb, limit_mb=max_mb),
                        reply_markup=delivery_keyboard(job_id),
                    )
                    return
            await self._deliver_nixfile(job_id, apk_path, package_label, package_name)
        elif mode == "rb":
            settings = self.data["settings"]
            uploader = self.data.get("rubika_uploader")
            if uploader is None or not uploader.enabled:
                await self.message.edit_text(
                    RUBIKA_DISABLED_TEXT, reply_markup=delivery_keyboard(job_id)
                )
                return
            max_mb = int(getattr(settings, "rubika_max_file_mb", 0) or 0)
            if max_mb > 0 and apk_path.exists():
                size_mb = apk_path.stat().st_size / (1024 * 1024)
                if size_mb > max_mb:
                    await self.message.edit_text(
                        RUBIKA_TOO_BIG_TEXT.format(size_mb=size_mb, limit_mb=max_mb),
                        reply_markup=delivery_keyboard(job_id),
                    )
                    return
            state: FSMContext = self.data["state"]
            await state.set_state(RubikaDeliveryStates.waiting_username)
            await state.update_data(
                rubika_job_id=job_id,
                rubika_apk_path=str(apk_path),
                rubika_package_name=package_name,
            )
            await self.message.edit_text(
                RUBIKA_PROMPT_USERNAME_TEXT, reply_markup=cancel_keyboard()
            )
        else:
            await self.message.edit_text(JOB_NOT_FOUND_TEXT, reply_markup=main_keyboard())

    async def _deliver_telegram(
        self, job_id: int, apk_path: Path, package_label: str
    ) -> None:
        db = self.data["db"]
        settings = self.data["settings"]
        status_message = self.message
        if status_message is None:
            return

        upload_progress = AnimatedProgress(status_message, UPLOAD_TITLE, package_label)
        max_attempts = int(getattr(settings, "telegram_upload_retries", 4) or 4)
        try:
            await status_message.edit_text(
                AnimatedProgress.render(UPLOAD_TITLE, package_label, 6)
            )
            upload_progress.start()
            await self._send_document_with_retry(apk_path, package_label, max_attempts)
            await upload_progress.stop(percent=100)
            await status_message.delete()
            await db.set_job_delivery(job_id, "telegram")
            await db.update_job(job_id, "done")
            _maybe_delete_after_upload(settings, apk_path)
        except Exception as exc:
            await upload_progress.stop()
            await db.update_job(job_id, "failed", error=str(exc))
            await status_message.edit_text(
                FAILED_TEXT.format(error=safe(exc)),
                reply_markup=delivery_keyboard(job_id),
            )

    async def _send_document_with_retry(
        self, apk_path: Path, package_label: str, max_attempts: int
    ) -> None:
        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                await self.event.message.answer_document(
                    document=FSInputFile(apk_path, filename=apk_path.name),
                    caption=DONE_TEXT.format(package=package_label),
                    reply_markup=main_keyboard(),
                )
                if attempt > 1:
                    logger.info(
                        "telegram upload succeeded on attempt %d/%d (%s)",
                        attempt,
                        max_attempts,
                        apk_path.name,
                    )
                return
            except TelegramRetryAfter as exc:
                last_exc = exc
                delay = max(1, int(exc.retry_after))
                logger.warning(
                    "telegram flood wait: sleeping %ds before retry %d/%d",
                    delay,
                    attempt + 1,
                    max_attempts,
                )
                if attempt >= max_attempts:
                    break
                await asyncio.sleep(delay)
            except (TelegramNetworkError, TelegramServerError, asyncio.TimeoutError) as exc:
                last_exc = exc
                if attempt >= max_attempts:
                    break
                delay = min(30, 2 ** (attempt - 1) * 3)
                logger.warning(
                    "telegram upload attempt %d/%d failed (%s: %s); retrying in %ds",
                    attempt,
                    max_attempts,
                    exc.__class__.__name__,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
        if last_exc is None:
            raise RuntimeError("telegram upload failed without exception")
        raise last_exc

    async def _deliver_nixfile(
        self,
        job_id: int,
        apk_path: Path,
        package_label: str,
        package_name: str,
    ) -> None:
        db = self.data["db"]
        status_message = self.message
        if status_message is None:
            return

        uploader = self.data.get("nixfile_uploader")
        if uploader is None or not uploader.enabled:
            await status_message.edit_text(
                NIXFILE_DISABLED_TEXT, reply_markup=main_keyboard()
            )
            return

        cache = await db.get_package_cache(package_name)
        if cache and cache.get("nixfile_url"):
            cached_url = cache["nixfile_url"]
            if await is_nixfile_url_alive(cached_url):
                await status_message.edit_text(
                    LINK_READY_TEXT.format(package=package_label),
                    reply_markup=link_keyboard(cached_url),
                )
                await db.set_job_delivery(job_id, "nixfile")
                await db.update_job(job_id, "done")
                return
            await db.clear_package_nixfile(package_name)

        upload_progress = SnapshotProgress(
            status_message, NIXFILE_UPLOAD_TITLE, package_label, uploader.progress_snapshot
        )
        upload_started = threading.Event()
        progress_started = False

        await status_message.edit_text(NIXFILE_PREPARING_TEXT)

        async def watch_start() -> None:
            while not upload_started.is_set():
                await asyncio.sleep(0.3)
            nonlocal progress_started
            upload_progress.start()
            progress_started = True

        watcher = asyncio.create_task(watch_start())

        try:
            url = await uploader.upload(apk_path, upload_started=upload_started)
            watcher.cancel()
            if progress_started:
                await upload_progress.stop(percent=100)
            await status_message.edit_text(
                LINK_READY_TEXT.format(package=package_label),
                reply_markup=link_keyboard(url),
            )
            await db.set_package_nixfile(package_name, url)
            await db.set_job_delivery(job_id, "nixfile")
            await db.update_job(job_id, "done")
            _maybe_delete_after_upload(self.data["settings"], apk_path)
        except NixfileError as exc:
            watcher.cancel()
            if progress_started:
                await upload_progress.stop()
            await db.update_job(job_id, "failed", error=str(exc))
            await status_message.edit_text(
                FAILED_TEXT.format(error=safe(exc)),
                reply_markup=main_keyboard(),
            )
        except Exception as exc:
            watcher.cancel()
            if progress_started:
                await upload_progress.stop()
            await db.update_job(job_id, "failed", error=str(exc))
            await status_message.edit_text(
                FAILED_TEXT.format(error=safe(exc)),
                reply_markup=main_keyboard(),
            )


@router.callback_query(StateFilter(RubikaDeliveryStates.waiting_username), F.data == "cancel")
class RubikaCancelCallback(CallbackQueryHandler):
    async def handle(self) -> Any:
        await self.event.answer("لغو شد")
        state: FSMContext = self.data["state"]
        data = await state.get_data()
        await state.clear()
        if not self.message:
            return
        job_id = data.get("rubika_job_id")
        markup = delivery_keyboard(job_id) if job_id else main_keyboard()
        try:
            await self.message.edit_text(CANCELLED_TEXT, reply_markup=markup)
        except TelegramBadRequest:
            await self.message.answer(CANCELLED_TEXT, reply_markup=markup)


@router.message(StateFilter(RubikaDeliveryStates.waiting_username), F.text)
class RubikaUsernameHandler(MessageHandler):
    async def handle(self) -> Any:
        state: FSMContext = self.data["state"]
        data = await state.get_data()
        uploader = self.data.get("rubika_uploader")
        db = self.data["db"]
        settings = self.data["settings"]

        username = (self.event.text or "").strip().lstrip("@")
        if not username or not username.replace("_", "").isalnum():
            await self.event.answer(RUBIKA_USERNAME_INVALID_TEXT)
            return

        job_id = int(data.get("rubika_job_id") or 0)
        apk_path_str = data.get("rubika_apk_path", "")
        package_name = data.get("rubika_package_name", "")
        apk_path = Path(apk_path_str) if apk_path_str else None

        await state.clear()

        if uploader is None or not uploader.enabled:
            await self.event.answer(RUBIKA_DISABLED_TEXT, reply_markup=main_keyboard())
            return
        if not apk_path or not apk_path.exists():
            await db.update_job(job_id, "failed", error="apk_missing")
            await self.event.answer(JOB_NOT_FOUND_TEXT, reply_markup=main_keyboard())
            return

        status_message = await self.event.answer(
            RUBIKA_UPLOADING_TEXT.format(username=safe(username))
        )

        try:
            result = await uploader.send_file(
                apk_path,
                target_username=username,
                caption=f"{package_name}\n— via PlayDL bot",
            )
        except RubikaError as exc:
            err = str(exc)
            if "پیدا نشد" in err or "not found" in err.lower():
                await status_message.edit_text(
                    RUBIKA_USER_NOT_FOUND_TEXT,
                    reply_markup=delivery_keyboard(job_id),
                )
            else:
                await db.update_job(job_id, "failed", error=err)
                await status_message.edit_text(
                    FAILED_TEXT.format(error=safe(err)),
                    reply_markup=delivery_keyboard(job_id),
                )
            return
        except Exception as exc:
            logger.exception("rubika delivery failed")
            await db.update_job(job_id, "failed", error=str(exc))
            await status_message.edit_text(
                FAILED_TEXT.format(error=safe(exc)),
                reply_markup=delivery_keyboard(job_id),
            )
            return

        await db.set_job_delivery(job_id, "rubika")
        await db.update_job(job_id, "done")
        _maybe_delete_after_upload(settings, apk_path)
        await status_message.edit_text(
            RUBIKA_DELIVERED_TEXT.format(
                name=safe(result.get("name", "?")),
                username=safe(username),
            ),
            reply_markup=main_keyboard(),
        )
