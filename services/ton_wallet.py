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
  закупки, а не основной. На Railway переменную стоит сделать Sealed —
  запечатанное значение нельзя прочитать обратно даже из веб-интерфейса;
- платёж уходит ТОЛЬКО за заказ, который уже оплачен клиентом (статус `paid`
  в базе) — это проверяет services/ton_autopay.py;
- на каждую транзакцию есть потолок (TON_AUTO_PAY_MAX_TON) и суточный лимит
  (TON_AUTO_PAY_DAILY_MAX_TON). Превышение — не платим, зовём админа;
- каждая оплата пишется в таблицу ton_payments ДО отправки, с UNIQUE по
  (заказ, назначение) — второй раз за тот же заказ заплатить нельзя;
- если что-то здесь не сработало (нет библиотеки, нет сети, неверная
  сид-фраза), магазин НЕ ломается: вызывающий код откатывается на старую
  схему с ручной ton://-ссылкой админу.

Библиотека подписи (tonutils) импортируется ЛЕНИВО, внутри функций. Так бот
запускается даже там, где её не поставили, — просто с выключенным автоплатежом.

ВАЖНО про версии tonutils: в 2.x пакеты называются `tonutils.clients` и
`tonutils.contracts` (в 0.x было `tonutils.client` / `tonutils.wallet`), а
`transfer(amount=...)` принимает НАНОТОНЫ, а не TON. Код ниже написан под 2.x.
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
    V5R1 и V4R2 разные, и деньги лежат только на одном из них. Какая именно
    версия у админа — покажет команда /tonwallet: она выводит оба адреса
    с балансами.
    """
    from tonutils.contracts import WalletV4R2, WalletV5R1

    v = (version or config.TON_WALLET_VERSION or "v5r1").lower().replace("_", "").replace("-", "")
    if v in ("v4r2", "v4"):
        return WalletV4R2
    if v in ("v5r1", "v5", "w5"):
        return WalletV5R1
    raise TonPayError(
        f"Неизвестная версия кошелька TON_WALLET_VERSION={version!r}. "
        "Допустимо: v5r1 (современный Tonkeeper W5) или v4r2 (более старый)."
    )


async def _connect_client():
    """Подключённый клиент к mainnet. Закрывать обязан вызывающий код."""
    from ton_core import NetworkGlobalID
    from tonutils.clients import ToncenterClient

    api_key = (config.TONCENTER_API_KEY or "").strip() or None
    client = ToncenterClient(network=NetworkGlobalID.MAINNET, api_key=api_key)
    await client.connect()
    return client


async def _open_wallet(version: str | None = None):
    """
    -> (wallet, client). Клиент нужно закрыть через client.close().
    Бросает TonPayError с понятным для админа текстом.
    """
    words = _mnemonic_words()
    if not words:
        raise TonPayError("TON_WALLET_MNEMONIC не задан — автоплатёж выключен.")
    if len(words) not in (12, 18, 24):
        raise TonPayError(
            f"В TON_WALLET_MNEMONIC {len(words)} слов, а должно быть 24 (или 12/18). "
            "Проверь переменную на Railway."
        )

    try:
        cls = _wallet_class(version)
    except TonPayError:
        raise
    except ImportError as e:
        raise TonPayError(
            f"Библиотека для подписи TON не установлена ({e}). "
            "Проверь, что `tonutils` есть в requirements.txt, и передеплой."
        )

    client = await _connect_client()
    try:
        wallet, _pub, _priv, _mnemo = cls.from_mnemonic(client, words)
    except Exception as e:
        await _safe_close(client)
        raise TonPayError(
            f"Не удалось открыть кошелёк из сид-фразы: {e}\n"
            "Чаще всего это опечатка в словах или лишние символы в переменной."
        )
    return wallet, client


async def _safe_close(client) -> None:
    try:
        await client.close()
    except Exception:
        pass  # закрытие клиента не должно ломать результат оплаты


async def get_wallet_info(version: str | None = None) -> dict:
    """
    Диагностика для команды /tonwallet: адрес и баланс.
    Ничего не подписывает и не отправляет — безопасно дёргать когда угодно.
    """
    wallet, client = await _open_wallet(version)
    try:
        balance_ton = None
        try:
            await wallet.refresh()  # подтягивает баланс и состояние из сети
            balance_ton = int(wallet.balance) / NANO
        except Exception:
            balance_ton = None
        # Неbounceable (UQ...) — та форма адреса, которую показывают кошельки
        address = wallet.address.to_str(is_bounceable=False)
        return {"address": address, "balance_ton": balance_ton}
    finally:
        await _safe_close(client)


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
    -> сумма перевода в нанотонах. Бросает TonPayError, если платить нельзя.
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

    msg = messages[0]
    if msg.get("stateInit"):
        # stateInit = разворачивание нового контракта вместе с переводом.
        # Для покупки звёзд и аренды он не нужен; если вдруг появился —
        # значит происходит что-то нетипичное, и решать должен человек.
        raise TonPayError(
            "В транзакции есть stateInit (развёртывание контракта) — "
            "бот такое сам не подписывает. Проверь и подтверди вручную."
        )

    amount_nano = await check_limits(tx)
    destination = msg["address"]

    # Бронируем ДО отправки: если такой платёж уже начинали — выходим сразу.
    if not await claim_ton_payment(order_id, purpose, amount_nano, destination):
        raise TonPayError(
            f"Платёж по заказу #{order_id} ({purpose}) уже отправлялся ранее — "
            "повторно не плачу. Проверь кошелёк и marketapp.org."
        )

    try:
        wallet, client = await _open_wallet()
    except TonPayError:
        await release_ton_payment(order_id, purpose)  # кошелёк не открыли — ничего не ушло
        raise

    try:
        from ton_core import Address, Cell

        body = None
        payload = msg.get("payload")
        if payload:
            # payload приходит от MarketApp как BOC в base64
            body = Cell.one_from_boc(base64.b64decode(payload))

        sent = await wallet.transfer(
            destination=Address(destination),
            amount=amount_nano,  # в 2.x transfer принимает НАНОТОНЫ
            body=body,
        )
        tx_hash = getattr(sent, "normalized_hash", None)
        address = wallet.address.to_str(is_bounceable=False)
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
    finally:
        await _safe_close(client)

    await finish_ton_payment(order_id, purpose, ok=True)
    return {
        "amount_ton": amount_nano / NANO,
        "address": address,
        "tx_hash": str(tx_hash) if tx_hash else None,
    }
