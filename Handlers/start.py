from contextlib import suppress
from typing import Any

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.handlers import MessageHandler

from Utils.keyboards import main_keyboard
from Utils.texts import START_TEXT

router = Router(name="start")


@router.message(CommandStart())
class StartHandler(MessageHandler):
    async def handle(self) -> Any:
        db = self.data["db"]
        state: FSMContext | None = self.data.get("state")

        if state is not None:
            data = await state.get_data()
            await state.clear()
            prompt_chat_id = data.get("prompt_chat_id")
            prompt_message_id = data.get("prompt_message_id")
            if prompt_chat_id and prompt_message_id:
                with suppress(TelegramBadRequest):
                    await self.event.bot.delete_message(prompt_chat_id, prompt_message_id)

        await db.upsert_user(self.from_user.id, self.from_user.full_name)
        await self.event.answer(START_TEXT, reply_markup=main_keyboard())
