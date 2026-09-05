"""
Простые подарки Telegram (не NFT) — мишка, сердце, подарочная коробка и т.д.
Отправляются напрямую через Bot API (getAvailableGifts / sendGift), оплата —
звёздами С БАЛАНСА САМОГО БОТА. Никаких кошельков и сторонних маркетов не нужно.

⚠️ ВАЖНОЕ УСЛОВИЕ: чтобы бот мог отправлять подарки, у него должен быть
собственный баланс Stars (пополняется через @BotFather -> Bot Settings ->
Stars Balance, либо накапливается от платных функций бота). Если баланса
не хватит — sendGift вернёт ошибку, и бот сообщит админу выполнить вручную.

⚠️ ОГРАНИЧЕНИЕ ПОЛУЧАТЕЛЯ: sendGift принимает числовой user_id, не @username.
Telegram отдаёт информацию по @username только если пользователь хотя бы раз
писал этому боту. Поэтому при оформлении заказа мы просим получателя сначала
написать /start этому же боту — иначе бот не сможет определить его user_id.
"""

import config

STAR_UNIT_PRICE_UZS = config.STAR_UNIT_PRICE_UZS


def gift_price_uzs(star_count: int) -> int:
    return round(star_count * STAR_UNIT_PRICE_UZS)


async def get_catalog(bot) -> list[dict]:
    """
    Живой каталог простых (не-limited, без апгрейда) подарков.
    -> [{'id': str, 'star_count': int, 'price_uzs': int, 'emoji': str}]
    """
    gifts = await bot.get_available_gifts()
    result = []
    for g in gifts.gifts:
        # limited-выпуски и такие, что требуют апгрейда, пропускаем —
        # это обычные "простые" подарки, не коллекционные NFT
        if getattr(g, "remaining_count", None) is not None:
            continue
        result.append({
            "id": g.id,
            "star_count": g.star_count,
            "price_uzs": gift_price_uzs(g.star_count),
            "sticker_emoji": getattr(g.sticker, "emoji", "🎁"),
        })
    result.sort(key=lambda x: x["star_count"])
    return result


async def resolve_user_id(bot, username: str) -> int | None:
    """Пытается получить числовой user_id по @username (работает, только если
    пользователь уже писал этому боту хотя бы раз)."""
    try:
        chat = await bot.get_chat(username)
        return chat.id
    except Exception:
        return None


async def fulfill_simple_gift(bot, order: dict) -> tuple[bool, str]:
    """
    Пытается отправить подарок автоматически. Если в заказе quantity > 1,
    отправляет подарок несколько раз подряд (максимум 10 за один заказ —
    столько же, сколько разрешено выбрать в магазине).
    -> (успех: bool, сообщение для админа: str)
    """
    username = order["recipient"] if order["recipient"].startswith("@") else f"@{order['recipient']}"

    # 1) Если при оформлении заказа мы уже точно знали user_id получателя
    #    (например, заказ "себе") — используем его напрямую, без повторного
    #    поиска по @username через Telegram API.
    user_id = order.get("recipient_user_id")

    # 2) Подстраховка для старых заказов без recipient_user_id: если получатель —
    #    это сам заказчик (username совпадает), берём его user_id из заказа.
    if not user_id and order.get("username") and username.lower() == f"@{order['username']}".lower():
        user_id = order.get("user_id")

    # 3) В остальных случаях (подарок другу) пробуем разрешить по @username —
    #    сработает, только если получатель уже писал этому боту.
    if not user_id:
        user_id = await resolve_user_id(bot, username)

    if user_id is None:
        return False, (
            f"Не удалось определить user_id получателя {username} — "
            "он ещё не писал этому боту. Попроси клиента отправить /start "
            "этому же боту, затем выполни заказ вручную (или повтори)."
        )

    quantity = order.get("quantity") or 1
    quantity = max(1, min(int(quantity), 10))  # защита от некорректных/слишком больших значений

    sent = 0
    for _ in range(quantity):
        try:
            await bot.send_gift(user_id=user_id, gift_id=order["nft_address"])  # используем то же поле под gift_id
            sent += 1
        except Exception as e:
            if sent == 0:
                return False, f"Ошибка при отправке подарка через Bot API: {e}"
            # Часть подарков уже ушла — сообщаем админу, сколько именно, остальное придётся отправить вручную
            return False, (
                f"Отправлено {sent} из {quantity} подарков пользователю {username}, "
                f"дальше остановилось из-за ошибки: {e}. Оставшиеся ({quantity - sent}) "
                "отправь вручную."
            )

    qty_note = f" (x{quantity})" if quantity > 1 else ""
    return True, f"🎁 Подарок{qty_note} отправлен автоматически пользователю {username}."
