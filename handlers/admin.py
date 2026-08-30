from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
import asyncio

import config
from database.db import get_order, set_order_status, get_stats, get_all_user_ids
from keyboards.admin_kb import admin_fulfill_kb
from services.prices import format_uzs
from services.fragment_service import try_auto_fulfill_stars, notify_manual_premium
from services.marketapp_service import start_rent_payment
from services.telegram_gifts import fulfill_simple_gift
from services.public_channel import post_completed_order
from services.i18n import t
from database.db import get_user_language as _get_user_language

router = Router()


class BroadcastStates(StatesGroup):
    waiting_message = State()


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


@router.message(Command("admin"))
async def admin_help(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "🛠 Админ-команды:\n"
        "/stats — статистика по пользователям и заказам\n"
        "/broadcast — разослать сообщение всем пользователям\n"
        "/order_&lt;id&gt; — посмотреть заказ (напр. /order_5)\n\n"
        "Подтверждение/отклонение оплаты — кнопками под чеком."
    )


@router.message(Command("broadcast"))
async def broadcast_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(BroadcastStates.waiting_message)
    await message.answer(
        "✍️ Пришли сообщение (текст, фото, видео — что угодно), которое разослать "
        "ВСЕМ пользователям бота. Для отмены — /cancel"
    )


@router.message(BroadcastStates.waiting_message, Command("cancel"))
async def broadcast_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Рассылка отменена.")


@router.message(BroadcastStates.waiting_message)
async def broadcast_send(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_ids = await get_all_user_ids()

    status_msg = await message.answer(f"⏳ Рассылаю {len(user_ids)} пользователям...")
    sent, failed = 0, 0

    for user_id in user_ids:
        try:
            await bot.copy_message(user_id, message.chat.id, message.message_id)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # не упереться в лимиты Telegram на массовую отправку

    await status_msg.edit_text(f"✅ Разослано: {sent}\n❌ Не доставлено: {failed}")


@router.message(Command("stats"))
async def stats_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return

    s = await get_stats()
    status_labels = {
        "awaiting_payment": "Ожидают оплаты",
        "payment_review": "На проверке",
        "paid": "Оплачены",
        "fulfilling": "Выполняются",
        "completed": "Выполнены",
        "rejected": "Отклонены",
    }
    status_lines = "\n".join(
        f"  • {status_labels.get(k, k)}: {v}" for k, v in s["orders_by_status"].items()
    ) or "  —"

    await message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Всего пользователей: <b>{s['total_users']}</b>\n"
        f"🟢 Активных за 24ч: <b>{s['active_24h']}</b>\n"
        f"🟢 Активных за 7дн: <b>{s['active_7d']}</b>\n\n"
        f"📦 Всего заказов: <b>{s['total_orders']}</b>\n"
        f"{status_lines}"
    )


@router.callback_query(F.data.startswith("admin:approve:"))
async def approve_payment(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return

    order_id = int(call.data.split(":")[2])
    order = await get_order(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return

    await set_order_status(order_id, "paid")
    await call.message.edit_caption(
        caption=(call.message.caption or "") + "\n\n✅ Оплата подтверждена",
        reply_markup=admin_fulfill_kb(order_id),
    )
    await call.answer("Подтверждено")

    lang = await _get_user_language(order["user_id"])
    await bot.send_message(
        order["user_id"],
        t(lang, "payment_confirmed").format(order_id=order_id),
    )

    # Выполнение в зависимости от категории
    if order["category"] == "stars":
        await try_auto_fulfill_stars(bot, order)

    elif order["category"] == "premium":
        await notify_manual_premium(bot, order)

    elif order["category"] == "nft_rent":
        await start_rent_payment(
            bot, order, order["nft_address"], float(order["base_price_per_day_gram"]), order["rent_days"]
        )

    elif order["category"] == "simple_gift":
        success, note = await fulfill_simple_gift(bot, order)
        if success:
            await set_order_status(order_id, "completed")
            lang = await _get_user_language(order["user_id"])
            await bot.send_message(
                order["user_id"],
                t(lang, "order_completed").format(order_id=order_id, item_name=order["item_name"]),
            )
            await post_completed_order(bot, order)
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(admin_id, f"Заказ #{order_id}: {note}")
            except Exception:
                pass


@router.callback_query(F.data.startswith("admin:reject:"))
async def reject_payment(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return

    order_id = int(call.data.split(":")[2])
    order = await get_order(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return

    await set_order_status(order_id, "rejected", admin_comment="Оплата не подтверждена")
    await call.message.edit_caption(caption=(call.message.caption or "") + "\n\n❌ Отклонено")
    await call.answer("Отклонено")

    lang = await _get_user_language(order["user_id"])
    await bot.send_message(
        order["user_id"],
        t(lang, "order_rejected").format(order_id=order_id),
    )


@router.callback_query(F.data.startswith("admin:done:"))
async def mark_done(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return

    order_id = int(call.data.split(":")[2])
    order = await get_order(order_id)
    await set_order_status(order_id, "completed")
    await call.message.edit_caption(caption=(call.message.caption or "") + "\n\n🎉 Выполнено")
    await call.answer("Отмечено как выполнено")

    lang = await _get_user_language(order["user_id"])
    await bot.send_message(
        order["user_id"],
        t(lang, "order_completed").format(order_id=order_id, item_name=order["item_name"]),
    )
    await post_completed_order(bot, order)
