"""
Автопроверка оплаты: SMS-пересыльщик на телефоне отправляет текст входящих
SMS от банка в отдельный Telegram-чат (группу/канал), куда добавлен этот бот.
Бот вытаскивает из текста сумму поступления и ищет заказ с точно такой же
expected_amount_uzs (см. database/db.py: allocate_unique_amount) — если нашёл,
подтверждает оплату автоматически, без скриншота и без нажатия кнопки админом.

⚠️ ВАЖНО — этот файл ещё не привязан к твоему банку:
Формат SMS у каждого банка/агрегатора свой (Uzcard, Humo, Kapitalbank и т.д.
пишут по-разному: где-то "Popolnenie", где-то "Zачисление", по-разному стоят
пробелы/точки в сумме). Регулярка ниже — общая заготовка (ищет последнее
число вида 1 234 567 или 1.234.567 перед словом "сум"/"so'm"/"uzs" в тексте).

Пришли мне реальный текст SMS о поступлении (можно с закрытыми цифрами карты)
— я подгоню регулярку точно под твой банк, чтобы не было ложных срабатываний
или пропущенных платежей.
"""

import re

from aiogram import Router, F, Bot
from aiogram.types import Message

import config
from database.db import get_order_by_expected_amount
from handlers.admin import finalize_payment

router = Router()

# Черновой паттерн — см. предупреждение выше, нужно свериться с реальной SMS.
_AMOUNT_RE = re.compile(
    r"([\d][\d\s.,]{2,})\s*(?:so'?m|сум|uzs)",
    re.IGNORECASE,
)


def _parse_amount(text: str) -> int | None:
    match = _AMOUNT_RE.search(text)
    if not match:
        return None
    digits = re.sub(r"[^\d]", "", match.group(1))
    return int(digits) if digits else None


def _is_sms_relay_chat(message: Message) -> bool:
    return bool(config.SMS_RELAY_CHAT_ID) and message.chat.id == config.SMS_RELAY_CHAT_ID


@router.message(F.func(_is_sms_relay_chat))
async def handle_sms_relay(message: Message, bot: Bot):
    if not config.UNIQUE_AMOUNT_ENABLED:
        return

    text = message.text or message.caption or ""
    amount = _parse_amount(text)
    if amount is None:
        return  # не нашли сумму — не похоже на SMS о поступлении, игнорируем

    order = await get_order_by_expected_amount(amount)
    if not order:
        # Сумма не совпала ни с одним ожидающим заказом — либо это чужое
        # поступление (не через бота), либо регулярка выше не подходит под
        # формат твоего банка. Смотри предупреждение в шапке файла.
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"🤖 SMS на сумму {amount} не совпала ни с одним заказом (или это не оплата заказа).",
                )
            except Exception:
                pass
        return

    await finalize_payment(bot, order["id"], order)

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🤖✅ Заказ #{order['id']} ({order['item_name']}) подтверждён автоматически "
                f"по SMS на сумму {amount}.",
            )
        except Exception:
            pass
