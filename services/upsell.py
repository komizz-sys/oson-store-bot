"""
Допродажа (upsell) — короткое сообщение с предложением смежной категории,
отправляется СРАЗУ ПОСЛЕ подтверждения оплаты (вместе с видео/инструкцией,
если она есть). Логика маркетинга:

  Купил Stars        -> предлагаем Premium
  Купил Premium       -> предлагаем подарки/аренду (сделать профиль ещё круче)
  Купил обычный Gift  -> предлагаем Stars (конкретные суммы: 50/100/200)
  Купил аренду NFT     -> предлагаем Stars и Premium

Тексты — на 3 языках, показываются в языке, который клиент выбрал при /start
(см. database.db.get_user_language). Если язык не определён — используется uz.
"""

from aiogram import Bot

UPSELL_TEXT = {
    "stars": {
        "uz": "💎 Aytgancha, Telegram Premium ham juda foydali — profilda status belgisi, katta fayl yuklash va boshqa imtiyozlar. Juda qulay narxda mavjud!",
        "ru": "💎 Кстати, Telegram Premium тоже очень полезен — значок статуса в профиле, загрузка больших файлов и другие плюшки. У нас по очень удобной цене!",
        "en": "💎 By the way, Telegram Premium is also great — a status badge, bigger file uploads, and more. Available at a great price!",
    },
    "premium": {
        "uz": "🎁 Profilingizni yanada ko'rkam qilish uchun noyob Telegram-sovg'alarini ijaraga olishni yoki oddiy sovg'a sotib olishni ham ko'rib chiqing!",
        "ru": "🎁 Чтобы сделать профиль ещё круче — присмотрись к аренде уникальных Telegram-подарков или покупке обычного подарка!",
        "en": "🎁 Want to make your profile even cooler? Check out renting a unique Telegram gift or buying a regular one!",
    },
    "simple_gift": {
        "uz": "⭐ Telegram Stars ham qulay narxda mavjud — 50, 100 yoki 200 dona sotib olib do'stlaringizga sovg'a qilishingiz mumkin!",
        "ru": "⭐ Telegram Stars тоже есть по хорошей цене — можно взять 50, 100 или 200 штук и подарить друзьям!",
        "en": "⭐ Telegram Stars are also available at a great price — grab 50, 100, or 200 to gift to friends!",
    },
    "nft_rent": {
        "uz": "⭐💎 Stars yoki Telegram Premium haqida ham o'ylab ko'ring — ikkalasi ham juda qulay narxda!",
        "ru": "⭐💎 Обрати внимание и на Stars или Premium — тоже по очень приятной цене!",
        "en": "⭐💎 Also check out Stars or Premium — great prices there too!",
    },
}

SHOP_HINT = {
    "uz": "\n\n🛍 Pastdagi \"Do'konni ochish\" tugmasi orqali ko'rib chiqishingiz mumkin.",
    "ru": "\n\n🛍 Посмотреть можно через кнопку «Do'konni ochish» внизу чата.",
    "en": "\n\n🛍 You can browse via the \"Do'konni ochish\" button at the bottom of the chat.",
}


async def send_upsell(bot: Bot, user_id: int, category: str, lang: str | None) -> None:
    lang = lang if lang in ("uz", "ru", "en") else "uz"
    texts = UPSELL_TEXT.get(category)
    if not texts:
        return  # для неизвестной категории просто ничего не предлагаем
    try:
        await bot.send_message(user_id, texts[lang] + SHOP_HINT[lang])
    except Exception:
        pass  # апсейл не критичен — не мешаем основному потоку оплаты, если что-то пошло не так
