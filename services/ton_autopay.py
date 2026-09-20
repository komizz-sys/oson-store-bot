"""
Обвязка автоплатежа: одна функция, которую зовут и покупка звёзд, и аренда.

Сам перевод делает services/ton_wallet.py. Здесь — то, что вокруг: решить,
можно ли платить автоматически, написать админу результат и, главное, НЕ
сломать магазин, если автоплатёж не сработал.

Правило, которое нельзя нарушать: если автооплата не удалась по любой причине,
функция возвращает False, и вызывающий код продолжает работать по-старому —
присылает админу ton://-ссылку на ручное подтверждение. Худший случай при
поломке автоплатежа — сегодняшнее поведение, а не остановленный магазин.
"""

from aiogram import Bot

import config
from database.db import get_order


async def _notify_admins(bot: Bot, text: str) -> None:
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, disable_web_page_preview=True)
        except Exception:
            pass


async def _client_really_paid(order_id: int) -> bool:
    """
    Деньги от клиента реально получены?

    Тратим НАСТОЯЩИЕ TON, поэтому не полагаемся на то, что нас вызвали из
    правильного места: перечитываем заказ из базы и смотрим статус. `paid`
    и `fulfilling` выставляются только после подтверждения оплаты — вручную
    админом или автоматически по SMS о поступлении на карту.
    """
    order = await get_order(order_id)
    if not order:
        return False
    return order["status"] in ("paid", "fulfilling", "completed")


async def autopay_or_none(bot: Bot, tx: dict, order: dict, purpose: str, what: str) -> bool:
    """
    Оплатить транзакцию автоматически, если это возможно и безопасно.

    -> True  — оплачено, вызывающему коду делать больше ничего не нужно;
       False — не оплачено, дальше идёт обычный путь с ручной ссылкой.
    """
    from services.ton_wallet import TonPayError, is_configured, pay_transaction, total_amount_nano

    if not is_configured():
        return False  # автоплатёж не настроен — это нормальный режим, молчим

    order_id = order["id"]

    if not await _client_really_paid(order_id):
        await _notify_admins(
            bot,
            f"🛑 Заказ #{order_id} ({what}) — автооплата НЕ выполнена: в базе заказ "
            "не помечен как оплаченный клиентом. Это защита от списания TON за "
            "неоплаченный заказ. Проверь заказ вручную.",
        )
        return False

    try:
        amount_ton = total_amount_nano(tx) / 1_000_000_000
    except Exception:
        amount_ton = 0

    try:
        result = await pay_transaction(tx, order_id=order_id, purpose=purpose)
    except TonPayError as e:
        # Нехватка денег — самый частый и самый безобидный случай: ничего не
        # списалось, заказ не заблокирован, после пополнения следующие
        # оплатятся сами. Поэтому и значок другой, и текст без паники.
        low = "не хватает TON" in str(e)
        head = "🪫" if low else "⚠️"
        await _notify_admins(
            bot,
            f"{head} Заказ #{order_id} ({what}) — автооплата не прошла:\n{e}\n\n"
            + (
                "Магазин работает как обычно: оплати этот заказ по ссылке ниже, "
                "а после пополнения кошелька следующие пойдут автоматически."
                if low
                else f"Сумма была бы {amount_ton:.4f} TON. Ниже — ссылка для ручной оплаты."
            ),
        )
        return False
    except Exception as e:
        # Непредвиденная ошибка не должна ронять выполнение заказа
        await _notify_admins(
            bot,
            f"⚠️ Заказ #{order_id} ({what}) — автооплата сорвалась неожиданно: {e}\n"
            "Ниже — ссылка для ручной оплаты.",
        )
        return False

    tx_note = f"\nХеш: <code>{result['tx_hash']}</code>" if result.get("tx_hash") else ""
    left = result.get("balance_left_ton")
    left_note = f"\nОстаток: {left:.4f} TON" if isinstance(left, (int, float)) else ""

    # Отдельного сообщения об УСПЕХЕ админу больше не шлём: при потоке заказов
    # эти «оплачено автоматически» забивали чат, и на их фоне терялось то
    # единственное, что требует внимания — НЕудачная автооплата. Результат
    # дописываем прямо в карточку чека, там же, где админ нажимал кнопку.
    from handlers.admin import note_on_admin_card

    await note_on_admin_card(
        bot,
        order_id,
        f"🤖💸 Автооплата по #{order_id}: {result['amount_ton']:.4f} TON"
        + (f" · остаток {left:.4f}" if isinstance(left, (int, float)) else ""),
    )

    # Предупреждаем ЗАРАНЕЕ, пока деньги ещё есть. Отдельным сообщением —
    # чтобы не потерялось в хвосте обычного уведомления об оплате.
    if result.get("low_balance"):
        await _notify_admins(
            bot,
            f"🪫 <b>Кошелёк магазина заканчивается: {left:.4f} TON</b>\n\n"
            "Пополни его, пока заказы идут. Когда TON закончится, магазин НЕ "
            "встанет — бот пришлёт ссылку на ручную оплату, — но каждую "
            "покупку придётся подтверждать в кошельке самому.",
        )
    return True
