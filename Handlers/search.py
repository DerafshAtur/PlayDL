from contextlib import suppress
from typing import Any

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.handlers import CallbackQueryHandler, MessageHandler

from Services.pipeline import run_download_pipeline
from Services.search import SearchError, build_play_url, search_apps
from Utils.html import safe
from Utils.keyboards import cancel_keyboard, main_keyboard, search_results_keyboard
from Utils.texts import (
    BUSY_TEXT,
    CANCELLED_TEXT,
    SEARCH_EMPTY_TEXT,
    SEARCH_FAILED_TEXT,
    SEARCH_PROMPT_TEXT,
    SEARCH_RESULTS_TEXT,
    USER_BUSY_TEXT,
)


class SearchStates(StatesGroup):
    waiting_query = State()


router = Router(name="search")


@router.callback_query(F.data == "search_app")
class SearchStartCallback(CallbackQueryHandler):
    async def handle(self) -> Any:
        await self.event.answer()
        if not self.message:
            return

        state: FSMContext = self.data["state"]
        await state.set_state(SearchStates.waiting_query)

        prompt_message = None
        try:
            prompt_message = await self.message.edit_text(
                SEARCH_PROMPT_TEXT, reply_markup=cancel_keyboard()
            )
        except TelegramBadRequest:
            prompt_message = await self.message.answer(
                SEARCH_PROMPT_TEXT, reply_markup=cancel_keyboard()
            )

        if prompt_message is not None:
            await state.update_data(
                prompt_chat_id=prompt_message.chat.id,
                prompt_message_id=prompt_message.message_id,
            )


@router.callback_query(StateFilter(SearchStates.waiting_query), F.data == "cancel")
class SearchCancelCallback(CallbackQueryHandler):
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


@router.message(StateFilter(SearchStates.waiting_query), F.text)
class SearchQueryHandler(MessageHandler):
    async def handle(self) -> Any:
        query = (self.event.text or "").strip()
        state: FSMContext = self.data["state"]

        if not query:
            await self.event.answer(SEARCH_PROMPT_TEXT, reply_markup=cancel_keyboard())
            return

        data = await state.get_data()
        await state.clear()

        prompt_chat_id = data.get("prompt_chat_id")
        prompt_message_id = data.get("prompt_message_id")
        if prompt_chat_id and prompt_message_id:
            with suppress(TelegramBadRequest):
                await self.event.bot.delete_message(prompt_chat_id, prompt_message_id)

        try:
            results = await search_apps(query)
        except SearchError as exc:
            await self.event.answer(
                SEARCH_FAILED_TEXT.format(error=safe(exc)),
                reply_markup=main_keyboard(),
            )
            return

        if not results:
            await self.event.answer(SEARCH_EMPTY_TEXT, reply_markup=main_keyboard())
            return

        await self.event.answer(
            SEARCH_RESULTS_TEXT.format(query=safe(query)),
            reply_markup=search_results_keyboard(results),
        )


@router.callback_query(F.data.startswith("pick:"))
class SearchPickCallback(CallbackQueryHandler):
    async def handle(self) -> Any:
        await self.event.answer()
        if not self.message:
            return

        package = (self.event.data or "").split(":", 1)[1].strip()
        if not package:
            await self.message.edit_text(SEARCH_EMPTY_TEXT, reply_markup=main_keyboard())
            return

        job_runner = self.data["job_runner"]
        if job_runner.user_busy(self.from_user.id):
            await self.message.edit_text(USER_BUSY_TEXT, reply_markup=main_keyboard())
            return
        if not job_runner.available:
            await self.message.edit_text(BUSY_TEXT, reply_markup=main_keyboard())
            return

        results_message = self.message
        url = build_play_url(package)

        with suppress(TelegramBadRequest):
            await results_message.delete()

        await job_runner.run(
            self.from_user.id,
            run_download_pipeline(
                event_message=results_message,
                user_id=self.from_user.id,
                url=url,
                package_name=package,
                deps=self.data,
            ),
        )
