"""
Двусторонняя связь с поддержкой прямо через бота:
1. Пользователь жмёт "💬 Поддержка" -> пишет сообщение
2. Бот копирует его всем админам с пометкой, от кого
3. Админ отвечает на это сообщение (обычный Reply в Telegram) —
   бот сам находит нужного пользователя и пересылает ответ ему
"""

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

import config
from database.db import get_user_language, save_support_mapping, get_support_user
from services.i18n import t

router = Router()


class SupportStates(StatesGroup):
    writing = State()


def _is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


@router.callback_query(F.data == "menu:support")
async def start_support(call: CallbackQuery, state: FSMContext):
    lang = await get_user_language(call.from_user.id)
    await state.set_state(SupportStates.writing)
    await call.message.answer(t(lang, "support_prompt"))
    await call.answer()


@router.message(SupportStates.writing)
async def relay_to_admin(message: Message, state: FSMContext, bot: Bot):
    lang = await get_user_language(message.from_user.id)
    user = message.from_user

    header = (
        f"✉️ <b>Сообщение от {user.full_name}</b>\n"
        f"@{user.username or '—'} · id: {user.id}\n"
        f"Ответь на это сообщение (Reply), чтобы отправить ответ клиенту."
    )

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, header)
            sent = await bot.copy_message(admin_id, message.chat.id, message.message_id)
            await save_support_mapping(admin_id, sent.message_id, user.id)
        except Exception:
            pass

    await message.answer(t(lang, "support_sent"))
    await state.clear()


@router.message(F.reply_to_message, F.chat.type == "private")
async def admin_reply(message: Message, bot: Bot):
    if not _is_admin(message.from_user.id):
        return

    user_id = await get_support_user(message.from_user.id, message.reply_to_message.message_id)
    if not user_id:
        return  # это Reply не на сообщение поддержки — не наш случай

    try:
        await bot.copy_message(user_id, message.chat.id, message.message_id)
        await message.reply("✅ Отправлено клиенту")
    except Exception as e:
        await message.reply(f"⚠️ Не удалось отправить: {e}")
