"""
Автоматическая оплата транзакций с TON-кошелька магазина.

Зачем. И покупка звёзд, и аренда гифтов на MarketApp устроены одинаково: их
API возвращает готовую транзакцию в формате TonConnect, а перевести TON должен
владелец кошелька. Раньше бот просто присылал админу ton://-ссылку, и тот
подтверждал КАЖДУЮ покупку руками в Tonkeeper — магазин не мог работать, пока
админ не у телефона, а клиент всё это время ждал.

Теперь бот подписывает транзакцию сам — тем же кошельком, которым сгенерирован
API-токен на marketapp.org (это обязательное требование MarketApp).

О безопасности, коротко и честно:
- бот хранит СИД-ФРАЗУ кошелька в переменной окружения (TON_WALLET_MNEMONIC).
  Кто получит доступ к переменным Railway — получит и кошелёк. Поэтому сюда
  заводится ОТДЕЛЬНЫЙ «рабочий» кошелёк с небольшим остатком на текущие
  закупки, а не основной;
- платёж уходит ТОЛЬКО за заказ, который уже оплачен клиентом (статус `paid`
  в базе) — это проверяет вызывающий код;
- на каждую транзакцию есть потолок (TON_AUTO_PAY_MAX_TON) и суточный лимит
  (TON_AUTO_PAY_DAILY_MAX_TON). Превышение — не платим, зовём админа;
- каждая оплата пишется в таблицу ton_payments ДО отправки, с UNIQUE по
  (заказ, назначение) — второй раз за тот же заказ заплатить нельзя;
- если что-то в этом модуле не сработало (нет библиотеки, нет сети, неверная
  сид-фраза), магазин НЕ ломается: вызывающий код откатывается на старую
  схему с ручной ton://-ссылкой админу.

Библиотека подписи (tonutils) импортируется ЛЕНИВО, внутри функций. Так бот
запускается даже там, где её не поставили, — просто с выключенным автоплатежом.
"""

import base64

import config

# Столько нанотонов в одном TON
NANO = 1_000_000_000


class TonPayError(Exception):
    """Автоплатёж не состоялся. Текст — уже человеческий, идёт админу как есть."""


def is_configured() -> bool:
    """Автоплатёж включён и сид-фраза задана? (библиотеку проверяем отдельно)"""
    return bool(config.TON_AUTO_PAY_ENABLED and _mnemonic_words())


def _mnemonic_words() -> list[str]:
    raw = (config.TON_WALLET_MNEMONIC or "").replace(",", " ")
    return [w for w in raw.split() if w]


def _wallet_class(version: str | None = None):
    """
    Класс кошелька нужной версии. Версия ВАЖНА: у одной сид-фразы адреса
    v4R2 и V5R1 разные, и деньги лежат только на одном из них. Какая именно
    версия у админа — видно командой /tonwallet, она показывает оба адреса
    с балансами.
    """
    from tonutils.wallet import WalletV4R2, WalletV5R1

    v = (version or config.TON_WALLET_VERSION or "v5r1").lower().replace("_", "").replace("-", "")
    if v in ("v4r2", "v4"):
        return WalletV4R2
    if v in ("v5r1", "v5", "w5"):
        return WalletV5R1
    raise TonPayError(
        f"Неизвестная версия кошелька TON_WALLET_VERSION={version!r}. "
        "Допустимо: v5r1 (современный Tonkeeper W5) или v4r2 (старый)."
    )


def _client():
    """
    Клиент к сети TON. Пробуем несколько классов: в разных версиях tonutils
    они называются по-разному, и жёсткая привязка к одному имени — лишний
    повод сломаться на ровном месте после обновления библиотеки.
    """
    import tonutils.client as tc

    api_key = (config.TONCENTER_API_KEY or "").strip()
    last_err = None
    for name in ("ToncenterV3Client", "ToncenterClient", "TonapiClient"):
        cls = getattr(tc, name, None)
        if cls is None:
            continue
        try:
            if name == "TonapiClient":
                if not api_key:
                    continue  # tonapi без ключа не работает
                return cls(api_key=api_key, is_testnet=False)
            return cls(api_key=api_key or None, is_testnet=False)
        except Exception as e:
            last_err = e
            try:
                return cls(is_testnet=False)  # часть версий не принимает api_key=None
            except Exception as e2:
                last_err = e2
    raise TonPayError(f"Не удалось создать клиент TON: {last_err}")


async def _open_wallet(version: str | None = None):
    """-> (wallet, адрес строкой). Бросает TonPayError с понятным текстом."""
    words = _mnemonic_words()
    if not words:
        raise TonPayError("TON_WALLET_MNEMONIC не задан — автоплатёж выключен.")
    if len(words) not in (12, 24):
        raise TonPayError(
            f"В TON_WALLET_MNEMONIC {len(words)} слов, а должно быть 24 (или 12). "
            "Проверь переменную на Railway."
        )

    try:
        cls = _wallet_class(version)
        client = _client()
        wallet, _pub, _priv, _mnemo = cls.from_mnemonic(client, words)
    except TonPayError:
        raise
    except ImportError as e:
        raise TonPayError(
            f"Библиотека для подписи TON не установлена ({e}). "
            "Добавь `tonutils` в requirements.txt и передеплой."
        )
    except Exception as e:
        raise TonPayError(f"Не удалось открыть кошелёк: {e}")

    return wallet, wallet.address.to_str()


async def get_wallet_info(version: str | None = None) -> dict:
    """
    Диагностика для команды /tonwallet: адрес и баланс.
    Ничего не отправляет и не подписывает — безопасно дёргать когда угодно.
    """
    wallet, address = await _open_wallet(version)
    balance_ton = None
    try:
        # Имя метода тоже плавает между версиями библиотеки
        for attr in ("balance", "get_balance"):
            fn = getattr(wallet, attr, None)
            if fn is None:
                continue
            value = await fn() if callable(fn) else fn
            balance_ton = int(value) / NANO if value and value > 1000 else value
            break
    except Exception:
        balance_ton = None
    return {"address": address, "balance_ton": balance_ton}


def _parse_messages(tx: dict) -> list[dict]:
    """Сообщения из ответа MarketApp (формат TonConnect)."""
    try:
        messages = tx["transaction"]["messages"]
    except (KeyError, TypeError):
        raise TonPayError("MarketApp вернул транзакцию в непонятном формате.")
    if not messages:
        raise TonPayError("MarketApp вернул транзакцию без единого перевода.")
    return messages


def total_amount_nano(tx: dict) -> int:
    return sum(int(m.get("amount") or 0) for m in _parse_messages(tx))


async def check_limits(tx: dict) -> int:
    """
    Проверка потолков ДО любых действий с кошельком.
    -> сумма перевода в нанотонах. Бросает TonPayError, если нельзя платить.
    """
    from database.db import get_ton_spent_today_nano

    amount_nano = total_amount_nano(tx)
    if amount_nano <= 0:
        raise TonPayError("Сумма перевода нулевая — платить нечего.")

    max_nano = int(config.TON_AUTO_PAY_MAX_TON * NANO)
    if amount_nano > max_nano:
        raise TonPayError(
            f"Перевод {amount_nano / NANO:.4f} TON больше разового лимита "
            f"{config.TON_AUTO_PAY_MAX_TON} TON (TON_AUTO_PAY_MAX_TON). "
            "Оплати вручную или подними лимит, если сумма ожидаемая."
        )

    spent = await get_ton_spent_today_nano()
    daily_nano = int(config.TON_AUTO_PAY_DAILY_MAX_TON * NANO)
    if spent + amount_nano > daily_nano:
        raise TonPayError(
            f"Суточный лимит исчерпан: уже потрачено {spent / NANO:.2f} TON из "
            f"{config.TON_AUTO_PAY_DAILY_MAX_TON} TON (TON_AUTO_PAY_DAILY_MAX_TON). "
            "Этот заказ оплати вручную."
        )
    return amount_nano


async def pay_transaction(tx: dict, order_id: int, purpose: str) -> dict:
    """
    Подписать и отправить транзакцию MarketApp с кошелька магазина.

    order_id + purpose нужны для защиты от двойной оплаты — за одну и ту же
    пару заплатить можно только один раз, даже если функцию позвали дважды.

    -> {"amount_ton": float, "address": str, "tx_hash": str | None}
    Бросает TonPayError, если платёж не состоялся (тогда вызывающий код
    возвращается к ручной ton://-ссылке).
    """
    from database.db import claim_ton_payment, finish_ton_payment, release_ton_payment

    if not is_configured():
        raise TonPayError("Автоплатёж выключен (TON_AUTO_PAY_ENABLED / TON_WALLET_MNEMONIC).")

    messages = _parse_messages(tx)
    if len(messages) > 1:
        # Несколько переводов в одной транзакции — редкий случай. Не рискуем
        # частичной отправкой (часть ушла, часть нет — потом не разберёшься),
        # отдаём такое админу целиком.
        raise TonPayError(
            f"В транзакции {len(messages)} переводов — такое бот сам не отправляет. "
            "Подтверди вручную по ссылке."
        )

    amount_nano = await check_limits(tx)
    msg = messages[0]
    destination = msg["address"]

    # Бронируем ДО отправки: если такой платёж уже начинали — выходим сразу.
    if not await claim_ton_payment(order_id, purpose, amount_nano, destination):
        raise TonPayError(
            f"Платёж по заказу #{order_id} ({purpose}) уже отправлялся ранее — "
            "повторно не плачу. Проверь кошелёк и marketapp.org."
        )

    try:
        wallet, address = await _open_wallet()
    except TonPayError:
        await release_ton_payment(order_id, purpose)  # кошелёк не открыли — ничего не ушло
        raise

    try:
        body = None
        payload = msg.get("payload")
        if payload:
            from pytoniq_core import Cell

            body = Cell.one_from_boc(base64.b64decode(payload))

        state_init = None
        raw_init = msg.get("stateInit")
        if raw_init:
            from pytoniq_core import Cell

            state_init = Cell.one_from_boc(base64.b64decode(raw_init))

        kwargs = {"destination": destination, "amount": amount_nano / NANO}
        if body is not None:
            kwargs["body"] = body
        if state_init is not None:
            kwargs["state_init"] = state_init

        tx_hash = await wallet.transfer(**kwargs)
    except Exception as e:
        # ВАЖНО: бронь НЕ снимаем. На этом этапе транзакция могла уже уйти в
        # сеть, а ответ потеряться — повторная отправка означала бы вторую
        # оплату того же заказа. Пусть лучше админ проверит кошелёк руками.
        await finish_ton_payment(order_id, purpose, ok=False, error=str(e))
        raise TonPayError(
            f"Не удалось отправить перевод: {e}\n\n"
            "⚠️ Проверь кошелёк — возможно, транзакция всё-таки ушла. "
            "Повторно бот платить не будет."
        )

    await finish_ton_payment(order_id, purpose, ok=True)
    return {
        "amount_ton": amount_nano / NANO,
        "address": address,
        "tx_hash": str(tx_hash) if tx_hash else None,
    }
