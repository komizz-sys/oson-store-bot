from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

import config
from database.db import get_order, set_order_status
from keyboards.admin_kb import admin_fulfill_kb
from services.prices import format_uzs
from services.fragment_service import try_auto_fulfill_stars, notify_manual_premium
from services.marketapp_service import start_rent_payment
from services.telegram_gifts import fulfill_simple_gift

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


@router.message(Command("admin"))
async def admin_help(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "🛠 Админ-команды:\n"
        "/order_&lt;id&gt; — посмотреть заказ (напр. /order_5)\n\n"
        "Подтверждение/отклонение оплаты — кнопками под чеком."
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

    await bot.send_message(
        order["user_id"],
        f"✅ Оплата по заказу #{order_id} подтверждена! Приступаем к выполнению.",
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
            await bot.send_message(order["user_id"], f"🎉 Заказ #{order_id} выполнен! {note}")
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

    await bot.send_message(
        order["user_id"],
        f"❌ Оплата по заказу #{order_id} не подтверждена. "
        "Свяжитесь с поддержкой, если считаете это ошибкой.",
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

    await bot.send_message(
        order["user_id"],
        f"🎉 Заказ #{order_id} ({order['item_name']}) выполнен! Спасибо за покупку 🙌",
    )
