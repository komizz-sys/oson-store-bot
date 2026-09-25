"""
Подключение арендованного гифта к профилю клиента — с ПОВТОРНЫМИ попытками.

Зачем повторы. Порядок событий при аренде такой:
1. клиент оплачивает заказ (картой) — подтверждается админом или по SMS;
2. бот создаёт аренду на MarketApp и присылает АДМИНУ ton://-ссылку, которую
   тот должен подтвердить в своём кошельке (реальный перевод TON);
3. клиент получает на Fragment свою tc://-ссылку и присылает её нам;
4. бот дёргает marketapp /tonconnect/ и подключает гифт.

Шаги 2 и 3 идут ПАРАЛЛЕЛЬНО и в любом порядке: клиент обычно успевает прислать
ссылку за минуту, а админ в это время ещё не открыл кошелёк. Тогда MarketApp
отвечает `400 {'detail': {'status': 'error', 'detail': 'forbidden'}}` — аренды
ещё не существует, подключать нечего. Раньше на этом всё и останавливалось:
клиенту писали «оператор подключит вручную», админ шёл делать это руками.

Теперь ссылка сохраняется и бот сам повторяет попытку по нарастающим
интервалам примерно полчаса. Как только админ подтвердит перевод в кошельке,
очередная попытка проходит — и клиент, и админ получают уведомление.
Кнопка «🔗 Подключить сейчас» у админа запускает попытку немедленно.
"""

import asyncio
import html

from aiogram import Bot

import config
from database.db import get_order, get_user_language
from services import marketapp_api

# Через сколько секунд после неудачи пробовать снова. Первые попытки частые —
# админ обычно платит сразу; дальше реже, чтобы не долбить API без толку.
RETRY_DELAYS = (30, 60, 90, 120, 180, 240, 300, 420, 600)

# Признак «аренда ещё не оплачена в кошельке» в ответе MarketApp. Именно этот
# случай имеет смысл повторять — остальные ошибки, скорее всего, повтором не
# лечатся, но повторяем и их: лишняя попытка дешевле ручной работы.
_NOT_PAID_MARKERS = ("forbidden", "not found", "404")

_lang_fallback = lambda v: v if v in ("uz", "ru", "en") else "uz"

# Фоновые задачи повторов. Держим на них ссылки: asyncio хранит задачи слабо,
# и без этого сборщик мусора может убить повтор посреди ожидания — подключение
# молча не случится, а понять причину будет почти невозможно.
_RETRY_TASKS: set[asyncio.Task] = set()
# Какой заказ уже крутит повторы. Второй цикл на тот же заказ не нужен:
# если клиент прислал новую ссылку, идущий цикл подхватит её сам.
_RETRY_BY_ORDER: dict[int, asyncio.Task] = {}
# Когда по заказу последний раз была попытка переподключения — защита от
# того, что человек жмёт «отправить» пять раз подряд.
_LAST_RECONNECT: dict[int, float] = {}
RECONNECT_COOLDOWN = 15  # секунд

CONNECTING = {
    "uz": "⏳ Havolangiz qabul qilindi, sovg'ani ulayapman...",
    "ru": "⏳ Ссылку получил, подключаю подарок...",
    "en": "⏳ Got your link, connecting the gift...",
}
# ВАЖНО про текст ниже.
#
# Раньше здесь было написано «откройте профиль — подарок должен отображаться»,
# и это вводило людей в заблуждение: подарок действительно приходит, но
# Telegram НЕ показывает его на странице сам по себе. Пока владелец не включит
# показ, гифт лежит скрытым — снаружи его видно только на Fragment. Это
# поведение самого Telegram (в их API у подарка есть флаг "скрыт", и он
# снимается либо вручную, либо настройкой автопоказа в приватности).
#
# Включить показ за клиента бот не может физически: это действие внутри его
# аккаунта, никакой бот в чужие настройки не лезет. Поэтому единственное, что
# мы можем — написать по шагам, что нажать. Отсюда и такой длинный текст:
# короткий («проверьте профиль») стоил нам потока вопросов в поддержку.
SUCCESS = {
    "uz": (
        "✅ Tayyor! «{item}» sovg'asi hisobingizga o'tkazildi.\n\n"
        "⚠️ Sovg'a profilda <b>o'zi ko'rinmaydi</b> — uni bir marta "
        "ko'rsatish kerak.\n\n"
        "Pastdagi tugmani bosing — videoda qanday qilish ko'rsatilgan."
    ),
    "ru": (
        "✅ Готово! Подарок «{item}» переведён на ваш аккаунт.\n\n"
        "⚠️ Сам по себе в профиле он <b>не появится</b> — показ нужно "
        "включить один раз.\n\n"
        "Нажмите кнопку ниже — в видео показано, как это сделать."
    ),
    "en": (
        "✅ Done! The gift \"{item}\" has been transferred to your account.\n\n"
        "⚠️ It will <b>not</b> appear on your profile by itself — the display "
        "has to be turned on once.\n\n"
        "Tap the button below — the video shows how."
    ),
}

# Подпись к видео. Само видео одно на всё: в нём и получение ссылки, и показ
# подарка в профиле — поэтому текст только называет, что внутри, и не
# пересказывает шаги словами.
DISPLAY_HELP = {
    "uz": (
        "🎥 <b>Videoda ko'rsatilgan:</b>\n\n"
        "1️⃣ Havolani <b>fragment.com</b> dan qanday olish\n"
        "2️⃣ Sovg'ani profilda qanday ko'rsatish\n\n"
        "Chiqmasa — Telegram'ni qayta ishga tushiring yoki /operator ga yozing."
    ),
    "ru": (
        "🎥 <b>В видео показано:</b>\n\n"
        "1️⃣ как получить ссылку на <b>fragment.com</b>\n"
        "2️⃣ как показать подарок в профиле\n\n"
        "Если не появился — перезапустите Telegram или напишите /operator."
    ),
    "en": (
        "🎥 <b>The video shows:</b>\n\n"
        "1️⃣ how to get the link on <b>fragment.com</b>\n"
        "2️⃣ how to display the gift on your profile\n\n"
        "If it doesn't appear — restart Telegram or contact /operator."
    ),
}

DISPLAY_VIDEO_BTN = {
    "uz": "📹 Profilda qanday ko'rsatish",
    "ru": "📹 Как показать в профиле",
    "en": "📹 How to display it",
}


def display_help_kb(lang: str, order_id: int | None = None):
    """Под сообщением об успехе: инструкции для Android/iPhone и «Обновить ссылку»."""
    from services.rent_link import tutorial_kb

    return tutorial_kb(lang, relink_order_id=order_id)


# Первая неудача — НЕ повод пугать клиента: почти всегда это «админ ещё не
# подтвердил перевод». Поэтому текст спокойный и без слова «ошибка».
PENDING = {
    "uz": ("⏳ Havola saqlandi. Sovg'a bir necha daqiqada ulanadi — tayyor bo'lgach xabar beramiz.\n\n"
           "❗️ Fragment sahifasini <b>yopmang va yangilamang</b> — ulanish aynan o'sha sahifada ko'rinadi."),
    "ru": ("⏳ Ссылка сохранена. Подарок подключится в течение нескольких минут — как будет готово, напишем.\n\n"
           "❗️ <b>Не закрывайте и не обновляйте</b> страницу Fragment — подключение появится именно на ней."),
    "en": ("⏳ Link saved. The gift will be connected within a few minutes — we'll message you when it's done.\n\n"
           "❗️ <b>Don't close or refresh</b> the Fragment page — the connection shows up on that exact page."),
}

# Подсказка «не подключилось на Fragment — пришли новую ссылку». Ставится под
# сообщением об успехе: бот не может проверить, поймала ли страница Fragment
# подтверждение (см. get_reconnectable_rent_order), так что честно говорим,
# что делать, если нет.
RECONNECT_HINT = {
    "uz": "\n\n🔄 Fragment'da ulanmagan bo'lsa — pastdagi <b>«Havolani yangilash»</b> tugmasini bosing va yangi havola yuboring.",
    "ru": "\n\n🔄 Если на Fragment не подключилось — нажмите <b>«Обновить ссылку»</b> ниже и пришлите новую ссылку.",
    "en": "\n\n🔄 If it didn't connect on Fragment — tap <b>«Update the link»</b> below and send a new link.",
}
RECONNECTING = {
    "uz": "🔄 Yangi havolani oldim, qayta ulayapman... Fragment sahifasini yopmang.",
    "ru": "🔄 Получил новую ссылку, переподключаю... Не закрывайте страницу Fragment.",
    "en": "🔄 Got the new link, reconnecting... Keep the Fragment page open.",
}
RECONNECTED = {
    "uz": "✅ Qayta ulandi! Fragment sahifasiga qarang.",
    "ru": "✅ Переподключил! Посмотрите на страницу Fragment.",
    "en": "✅ Reconnected! Check the Fragment page.",
}
RECONNECT_FAILED = {
    "uz": "⚠️ Qayta ulab bo'lmadi. Operator tekshiradi — yoki bir daqiqadan keyin yana yangi havola yuboring.",
    "ru": "⚠️ Переподключить не вышло. Оператор проверит — или пришлите новую ссылку ещё раз через минуту.",
    "en": "⚠️ Couldn't reconnect. An operator will check — or send a new link again in a minute.",
}
RECONNECT_SLOW_DOWN = {
    "uz": "⏳ Havola hozirgina yuborildi — bir oz kuting.",
    "ru": "⏳ Ссылку только что прислали — подождите немного.",
    "en": "⏳ A link was just sent — please wait a moment.",
}
# Все попытки исчерпаны — вот тут уже зовём оператора. Просим и свежую ссылку:
# tc://-ссылки Fragment живут недолго и к этому моменту могли протухнуть.
FAILED = {
    "uz": "⚠️ Sovg'ani ulab bo'lmadi. Iltimos, Fragment'da YANGI havola oling va shu yerga yuboring — yoki operator qo'lda ulab beradi.",
    "ru": "⚠️ Не удалось подключить подарок. Пожалуйста, получите на Fragment НОВУЮ ссылку и пришлите её сюда — или оператор подключит вручную.",
    "en": "⚠️ Could not connect the gift. Please get a NEW link on Fragment and send it here — or an operator will connect it manually.",
}


def explain_error(err: Exception) -> str:
    """Человеческая расшифровка ошибки MarketApp для сообщения админу."""
    text = str(err).lower()
    if any(m in text for m in _NOT_PAID_MARKERS):
        return (
            "Скорее всего аренда ещё НЕ оплачена в кошельке — подтверди "
            "ton://-перевод из сообщения выше тем кошельком, которым "
            "генерировал API-токен на marketapp.org."
        )
    return "Причина не распознана — посмотри заказ на marketapp.org."


async def _notify_admins(bot: Bot, text: str, reply_markup=None) -> None:
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id, text, reply_markup=reply_markup, disable_web_page_preview=True
            )
        except Exception:
            pass


async def _notify_client(bot: Bot, user_id: int, text: str, reply_markup=None) -> None:
    try:
        await bot.send_message(user_id, text, reply_markup=reply_markup)
    except Exception:
        pass  # клиент мог закрыть чат — не роняем подключение из-за этого


async def attempt_connect(bot: Bot, order: dict, link: str) -> tuple[bool, str]:
    """
    Одна попытка подключения. -> (получилось, текст ошибки)
    Никому ничего не пишет — сообщениями занимается вызывающий код.
    """
    try:
        await marketapp_api.rent_connect_tonconnect(order["nft_address"], link)
        return True, ""
    except Exception as e:
        return False, str(e)


async def _complete_order(bot: Bot, order: dict) -> None:
    """
    Закрыть заказ аренды как выполненный.

    Для аренды подключение гифта — это и есть выполнение заказа, больше
    делать нечего. Раньше статус всё равно оставался «оплачен» до тех пор,
    пока админ не нажмёт «Заказ выполнен», и клиент в витрине бесконечно
    видел крутящуюся шестерёнку «выполняется» — при том, что подарок уже
    лежал у него в профиле, а админу бот писал «вручную ничего не нужно».
    """
    from database.db import set_order_status
    from services.live_feed import push_live_feed_event
    from services.public_channel import post_completed_order

    await set_order_status(order["id"], "completed")
    try:
        await post_completed_order(bot, dict(order, status="completed"))
    except Exception:
        pass  # витрина и канал не должны мешать закрытию заказа
    try:
        await push_live_feed_event("🖼", order["item_name"])
    except Exception:
        pass


async def announce_success(bot: Bot, order: dict, attempt_note: str = "") -> None:
    lang = _lang_fallback(await get_user_language(order["user_id"]))
    await _notify_client(
        bot,
        order["user_id"],
        # Имя подарка приходит из MarketApp и может содержать символы, которые
        # Telegram примет за HTML («&», «<»). Тогда сообщение не отправится
        # вообще, и клиент решит, что его кинули. Экранируем.
        SUCCESS[lang].format(item=html.escape(order["item_name"] or "")) + RECONNECT_HINT[lang],
        reply_markup=display_help_kb(lang, order["id"]),
    )
    await _complete_order(bot, order)
    await _notify_admins(
        bot,
        f"✅ Заказ #{order['id']} ({order['item_name']}) — аренда подключена "
        f"клиенту {order['recipient']}{attempt_note}.\n"
        "Заказ закрыт как выполненный, вручную ничего делать не нужно.",
    )


async def _still_needs_connect(order_id: int) -> dict | None:
    """
    Заказ всё ещё ждёт подключения? Между попытками админ мог подключить гифт
    руками и нажать «Заказ выполнен», или заказ вообще отменили — в обоих
    случаях продолжать долбить API незачем.
    """
    order = await get_order(order_id)
    if not order:
        return None
    if order["status"] not in ("paid", "fulfilling"):
        return None
    return order


async def _retry_loop(bot: Bot, order_id: int, link: str) -> None:
    for delay in RETRY_DELAYS:
        await asyncio.sleep(delay)

        order = await _still_needs_connect(order_id)
        if not order:
            return  # подключили вручную или заказ закрыли — тихо выходим

        # Клиент мог за это время прислать НОВУЮ ссылку (старая умерла вместе
        # с закрытой вкладкой Fragment) — пробуем всегда с самой свежей.
        link = (order.get("rent_link") or "").strip() or link
        ok, err = await attempt_connect(bot, order, link)
        if ok:
            await announce_success(bot, order, " автоматически, со второй попытки (после оплаты в кошельке)")
            return

    # Попытки кончились. Теперь уже честно зовём на помощь — и клиента, и админа.
    order = await _still_needs_connect(order_id)
    if not order:
        return

    lang = _lang_fallback(await get_user_language(order["user_id"]))
    await _notify_client(bot, order["user_id"], FAILED[lang])
    await _notify_admins(
        bot,
        f"⚠️ Заказ #{order['id']} ({order['item_name']}) — за полчаса подключить "
        f"аренду так и не удалось.\n\n"
        f"Ссылка клиента:\n<code>{link}</code>\n\n"
        "Проверь, прошёл ли ton://-перевод, и подключи вручную на marketapp.org. "
        "Если ссылка устарела — попроси у клиента новую.",
        reply_markup=_retry_kb(order["id"]),
    )


def _retry_kb(order_id: int):
    from keyboards.admin_kb import admin_rent_retry_kb

    return admin_rent_retry_kb(order_id)


async def connect_rent_link(bot: Bot, order: dict, link: str, *, announce_start: bool = True) -> bool:
    """
    Главная точка входа: пробует подключить сразу, а при неудаче ставит
    фоновые повторы. Используется ОБОИМИ путями — и когда ссылка пришла
    сообщением в чат, и когда её прислали из витрины, — чтобы поведение
    не разъезжалось на две разные ветки.

    -> True, если подключилось сразу.
    """
    lang = _lang_fallback(await get_user_language(order["user_id"]))
    if announce_start:
        await _notify_client(bot, order["user_id"], CONNECTING[lang])

    ok, err = await attempt_connect(bot, order, link)
    if ok:
        await announce_success(bot, order, " автоматически")
        return True

    # Не получилось — почти наверняка админ ещё не подтвердил перевод.
    # Клиенту спокойное «подключится в течение нескольких минут», админу —
    # что именно пошло не так и что с этим делать.
    await _notify_client(bot, order["user_id"], PENDING[lang])
    await _notify_admins(
        bot,
        f"⏳ Заказ #{order['id']} ({order['item_name']}) — клиент прислал ссылку, "
        f"но подключить пока не вышло:\n<code>{err}</code>\n\n"
        f"{explain_error(Exception(err))}\n\n"
        "Бот будет пробовать сам ещё ~30 минут — как только перевод пройдёт, "
        "подключит и сообщит. Кнопка ниже запускает попытку немедленно.",
        reply_markup=_retry_kb(order["id"]),
    )

    running = _RETRY_BY_ORDER.get(order["id"])
    if running is None or running.done():
        task = asyncio.create_task(_retry_loop(bot, order["id"], link))
        _RETRY_TASKS.add(task)
        _RETRY_BY_ORDER[order["id"]] = task

        def _cleanup(t, oid=order["id"]):
            _RETRY_TASKS.discard(t)
            if _RETRY_BY_ORDER.get(oid) is t:
                _RETRY_BY_ORDER.pop(oid, None)

        task.add_done_callback(_cleanup)
    return False


async def reconnect_completed(bot: Bot, order: dict, link: str) -> bool:
    """
    Переподключение по НОВОЙ ссылке, когда заказ уже закрыт как выполненный.
    Заказ повторно не закрываем и в канал второй раз не пишем — только
    подключаем и говорим клиенту.
    """
    lang = _lang_fallback(await get_user_language(order["user_id"]))
    await _notify_client(bot, order["user_id"], RECONNECTING[lang])
    ok, err = await attempt_connect(bot, order, link)
    if ok:
        await _notify_client(bot, order["user_id"], RECONNECTED[lang] + RECONNECT_HINT[lang],
                             reply_markup=display_help_kb(lang, order["id"]))
        await _notify_admins(
            bot,
            f"🔄 Заказ #{order['id']} ({order['item_name']}) — клиент прислал новую "
            "ссылку, аренда переподключена автоматически. Делать ничего не нужно.",
        )
        return True
    await _notify_client(bot, order["user_id"], RECONNECT_FAILED[lang])
    await _notify_admins(
        bot,
        f"⚠️ Заказ #{order['id']} ({order['item_name']}) — клиент прислал новую "
        f"ссылку, но переподключить не вышло:\n<code>{html.escape(err)}</code>\n\n"
        f"Ссылка:\n<code>{html.escape(link)}</code>",
        reply_markup=_retry_kb(order["id"]),
    )
    return False


async def submit_rent_link(bot: Bot, user_id: int, link: str, *, announce_start: bool = True) -> dict | None:
    """
    Единая точка приёма ссылки — из чата и из витрины.

    - заказ ждёт первую ссылку → обычное подключение с повторами;
    - ссылка уже была, но пришла новая (чаще всего Android: вкладка Fragment
      перезагрузилась и старая ссылка умерла) → переподключаем по новой.

    -> None, если у клиента нет подходящего заказа аренды;
       иначе {"order": ..., "connected": bool, "reconnect": bool, "throttled": bool}
    """
    from database.db import get_pending_rent_link_order, set_rent_link

    order = await get_pending_rent_link_order(user_id)
    if order:
        await set_rent_link(order["id"], link)
        # В чате клиенту сразу пишем «ссылку получил»; витрина показывает это сама.
        connected = await connect_rent_link(bot, order, link, announce_start=announce_start)
        return {"order": order, "connected": connected, "reconnect": False, "throttled": False}

    # Ссылку прислали без выбора аренды. Если действующая аренда одна —
    # переподключаем её; если несколько — пусть клиент выберет кнопкой.
    rentals = await relinkable_rentals(user_id)
    if not rentals:
        return None
    if len(rentals) > 1:
        return {"order": None, "connected": False, "reconnect": True, "throttled": False,
                "choose": rentals}
    return await relink_rental(bot, user_id, rentals[0]["order_id"], link)


async def relinkable_rentals(user_id: int) -> list[dict]:
    """Действующие аренды клиента, которые можно переподключить новой ссылкой."""
    from services.rent_extension import get_active_rentals

    return await get_active_rentals(user_id)


async def relink_rental(bot: Bot, user_id: int, order_id: int, link: str) -> dict | None:
    """
    Переподключить КОНКРЕТНУЮ аренду новой ссылкой — кнопка «Обновить ссылку»,
    /relink или «Qayta ulash» в витрине. Работает, пока аренда не закончилась.
    -> None, если такой действующей аренды у клиента нет.
    """
    import time
    from database.db import set_rent_link

    if order_id not in {r["order_id"] for r in await relinkable_rentals(user_id)}:
        return None
    order = await get_order(order_id)
    if not order or order["user_id"] != user_id:
        return None

    now = time.monotonic()
    if now - _LAST_RECONNECT.get(order_id, 0.0) < RECONNECT_COOLDOWN:
        lang = _lang_fallback(await get_user_language(user_id))
        await _notify_client(bot, user_id, RECONNECT_SLOW_DOWN[lang])
        return {"order": order, "connected": False, "reconnect": True, "throttled": True}
    _LAST_RECONNECT[order_id] = now

    await set_rent_link(order_id, link)
    order = dict(order, rent_link=link)
    if order["status"] == "completed":
        connected = await reconnect_completed(bot, order, link)
    else:
        # Ещё не подключали — идущий цикл повторов возьмёт новую ссылку сам;
        # пробуем и сразу.
        connected = await connect_rent_link(bot, order, link, announce_start=False)
    return {"order": order, "connected": connected, "reconnect": True, "throttled": False}
