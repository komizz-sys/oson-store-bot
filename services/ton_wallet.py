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
import hashlib
import hmac

import config

# ---- Деривация ключа из сид-фразы ----
#
# Один и тот же набор слов может превращаться в ключ ДВУМЯ разными способами,
# и они дают разные кошельки:
#
# 1) "ton"   — родной стандарт TON (PBKDF2, соль "TON default seed").
#    Так делают 24-словные фразы обычных TON-кошельков. Это то, что умеет
#    библиотека из коробки.
# 2) "bip39" — общий стандарт, как у биткоина и эфира: PBKDF2 с солью
#    "mnemonic", затем SLIP-0010 по пути m/44'/607'/0'. Так устроены
#    12-словные фразы — их выдают кошельки, умеющие несколько блокчейнов.
#
# Если выбрать не тот способ, адрес получится чужой и с нулевым балансом —
# именно так и выглядит "бот показывает не мой адрес". Поэтому /tonwallet
# перебирает оба способа и все версии кошелька, пока не найдёт совпадение.
HARDENED = 0x80000000

# Пути деривации, которые встречаются у TON-кошельков. 607 — номер TON в
# реестре SLIP-0044. Разные приложения используют разную глубину пути,
# поэтому пробуем все три.
BIP39_PATHS = (
    (44 + HARDENED, 607 + HARDENED, 0 + HARDENED),
    (44 + HARDENED, 607 + HARDENED, 0 + HARDENED, 0 + HARDENED, 0 + HARDENED),
    (44 + HARDENED, 607 + HARDENED, 0 + HARDENED, 0 + HARDENED),
)

DERIVATIONS = ("ton", "bip39")


def _bip39_seed(words: list[str], passphrase: str = "") -> bytes:
    """Мастер-семя BIP-39: PBKDF2-HMAC-SHA512, 2048 итераций, соль 'mnemonic'."""
    mnemonic = " ".join(words)
    return hashlib.pbkdf2_hmac(
        "sha512", mnemonic.encode("utf-8"), ("mnemonic" + passphrase).encode("utf-8"), 2048
    )


def _slip10_ed25519(seed: bytes, path: tuple[int, ...]) -> bytes:
    """
    SLIP-0010 для ed25519: из мастер-семени получаем приватный ключ по пути.
    Проверено на официальных тест-векторах SLIP-0010.
    """
    I = hmac.new(b"ed25519 seed", seed, hashlib.sha512).digest()
    key, chain = I[:32], I[32:]
    for index in path:
        data = b"\x00" + key + index.to_bytes(4, "big")
        I = hmac.new(chain, data, hashlib.sha512).digest()
        key, chain = I[:32], I[32:]
    return key

# Столько нанотонов в одном TON
NANO = 1_000_000_000

# Запас сверх суммы перевода — на комиссию сети. Без него кошелёк с балансом
# ровно в размер перевода не сможет его отправить: комиссию платить нечем.
FEE_RESERVE_NANO = 50_000_000  # 0.05 TON


class TonPayError(Exception):
    """Автоплатёж не состоялся. Текст — уже человеческий, идёт админу как есть."""


def is_configured() -> bool:
    """Автоплатёж включён и сид-фраза задана? (библиотеку проверяем отдельно)"""
    return bool(config.TON_AUTO_PAY_ENABLED and _mnemonic_words())


def _mnemonic_words() -> list[str]:
    raw = (config.TON_WALLET_MNEMONIC or "").replace(",", " ")
    return [w for w in raw.split() if w]


# Версии кошельков, которые бот умеет открывать, в порядке распространённости.
# Одна и та же сид-фраза даёт РАЗНЫЕ адреса для каждой версии, и деньги лежат
# только на одном из них — поэтому /tonwallet перебирает их все и показывает,
# какой адрес получается. Отдельно стоит `tg`: кошелёк внутри Telegram
# (TON Space) — это не W5 и не V4, у него свой тип контракта со своим
# subwallet_id, и без него адрес такого кошелька не воспроизвести.
WALLET_VERSIONS = ("tg", "v5r1", "v4r2", "v3r2", "v3r1")

_VERSION_LABELS = {
    "tg": "Telegram Wallet (TON Space)",
    "v5r1": "W5 — современный Tonkeeper",
    "v4r2": "V4R2 — более старый Tonkeeper",
    "v3r2": "V3R2 — старые кошельки",
    "v3r1": "V3R1 — совсем старые",
}


def version_label(version: str) -> str:
    return _VERSION_LABELS.get(version, version)


def _wallet_class(version: str | None = None):
    """Класс кошелька нужной версии (см. WALLET_VERSIONS)."""
    from tonutils.contracts import (
        WalletTg, WalletV3R1, WalletV3R2, WalletV4R2, WalletV5R1,
    )

    v = (version or config.TON_WALLET_VERSION or "v5r1").lower().replace("_", "").replace("-", "")
    mapping = {
        "tg": WalletTg, "telegram": WalletTg, "tonspace": WalletTg,
        "v5r1": WalletV5R1, "v5": WalletV5R1, "w5": WalletV5R1,
        "v4r2": WalletV4R2, "v4": WalletV4R2,
        "v3r2": WalletV3R2, "v3": WalletV3R2,
        "v3r1": WalletV3R1,
    }
    if v in mapping:
        return mapping[v]
    raise TonPayError(
        f"Неизвестная версия кошелька TON_WALLET_VERSION={version!r}. "
        f"Допустимо: {', '.join(WALLET_VERSIONS)}."
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
    Рабочий кошелёк по настройкам из переменных окружения.
    -> (wallet, client). Клиент нужно закрыть через client.close().
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
        _wallet_class(version)  # ранняя проверка имени версии и наличия библиотеки
    except TonPayError:
        raise
    except ImportError as e:
        raise TonPayError(
            f"Библиотека для подписи TON не установлена ({e}). "
            "Проверь, что `tonutils` есть в requirements.txt, и передеплой."
        )

    derivation, path_index = _configured_derivation()
    client = await _connect_client()
    try:
        wallet = _make_wallet(client, version or config.TON_WALLET_VERSION, derivation, path_index)
    except Exception as e:
        await _safe_close(client)
        raise TonPayError(
            f"Не удалось открыть кошелёк из сид-фразы: {e}\n"
            "Проверь TON_WALLET_VERSION и TON_WALLET_DERIVATION — их подсказывает /tonwallet."
        )
    return wallet, client


def _configured_derivation() -> tuple[str, int]:
    """
    Способ деривации из настроек. Формат TON_WALLET_DERIVATION:
    "ton" — родной стандарт TON; "bip39" — путь по умолчанию;
    "bip39:1", "bip39:2" — альтернативные пути (их подсказывает /tonwallet).
    """
    raw = (getattr(config, "TON_WALLET_DERIVATION", "") or "ton").strip().lower()
    name, _, idx = raw.partition(":")
    if name not in DERIVATIONS:
        name = "ton"
    try:
        path_index = int(idx) if idx else 0
    except ValueError:
        path_index = 0
    if not (0 <= path_index < len(BIP39_PATHS)):
        path_index = 0
    return name, path_index


async def _safe_close(client) -> None:
    try:
        await client.close()
    except Exception:
        pass  # закрытие клиента не должно ломать результат оплаты


def _same_address(a: str, b: str) -> bool:
    """
    Один и тот же ли это адрес. Сравнивать строки напрямую нельзя: один адрес
    записывается в разных формах (UQ.../EQ..., bounceable и нет), и все они
    указывают на один кошелёк. Поэтому сверяем по «хвосту» — он одинаковый во
    всех формах, меняются только первые пара символов и контрольная сумма.
    """
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b:
        return False
    if a == b:
        return True
    # Отбрасываем префикс формы (2 символа) и контрольную сумму (последние 4)
    return a[2:-4] == b[2:-4] and len(a) == len(b)


def _make_wallet(client, version: str, derivation: str, path_index: int = 0):
    """Кошелёк нужной версии, ключ получен выбранным способом деривации."""
    cls = _wallet_class(version)
    words = _mnemonic_words()

    if derivation == "ton":
        wallet, _p, _s, _m = cls.from_mnemonic(client, words)
        return wallet

    from ton_core import PrivateKey

    seed = _bip39_seed(words)
    key = _slip10_ed25519(seed, BIP39_PATHS[path_index])
    return cls.from_private_key(client, PrivateKey(key))


async def scan_versions(expected_address: str | None = None) -> list[dict]:
    """
    Перебрать ВСЕ сочетания «версия кошелька × способ деривации» и вернуть
    получившиеся адреса.

    Гадать тут нечего: из одной фразы получается с десяток разных адресов, и
    какой из них настоящий — видно только по совпадению с адресом владельца
    или по ненулевому балансу. Адреса считаются локально (это быстро), в сеть
    ходим только за балансом и только для совпавшего варианта либо когда
    адрес для сверки не передан.

    -> [{"version", "label", "derivation", "path", "address",
         "balance_ton", "match", "error"}]
    """
    results: list[dict] = []
    client = None
    try:
        client = await _connect_client()
    except TonPayError as e:
        return [{"version": v, "label": version_label(v), "derivation": "ton",
                 "path": 0, "address": None, "balance_ton": None,
                 "match": False, "error": str(e)}
                for v in WALLET_VERSIONS]

    try:
        combos = []
        for version in WALLET_VERSIONS:
            combos.append((version, "ton", 0))
            for i in range(len(BIP39_PATHS)):
                combos.append((version, "bip39", i))

        for version, derivation, path_index in combos:
            row = {
                "version": version, "label": version_label(version),
                "derivation": derivation, "path": path_index,
                "address": None, "balance_ton": None, "match": False, "error": None,
            }
            try:
                wallet = _make_wallet(client, version, derivation, path_index)
                row["address"] = wallet.address.to_str(is_bounceable=False)
                if expected_address:
                    row["match"] = _same_address(row["address"], expected_address)
                # Баланс — только там, где он реально нужен: иначе на каждый
                # запрос /tonwallet уходило бы два десятка обращений к сети,
                # и без ключа toncenter мы бы упёрлись в лимит.
                if row["match"] or not expected_address:
                    try:
                        await wallet.refresh()
                        row["balance_ton"] = int(wallet.balance) / NANO
                    except Exception:
                        pass
            except Exception as e:
                row["error"] = str(e)
            results.append(row)
    finally:
        await _safe_close(client)
    return results


async def _balance_nano(wallet) -> int | None:
    """Баланс кошелька в нанотонах. None, если сеть не ответила."""
    try:
        await wallet.refresh()
        return int(wallet.balance)
    except Exception:
        return None


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

    # Кошелёк открываем ДО брони — чтобы проверить баланс. Если денег не
    # хватает, бронь не ставится вообще, и после пополнения этот же заказ
    # можно оплатить автоматически. Иначе он навсегда остался бы помеченным
    # как «уже отправляли», хотя ничего не отправлялось.
    wallet, client = await _open_wallet()

    try:
        balance_nano = await _balance_nano(wallet)
    except Exception:
        balance_nano = None  # баланс не узнали — не мешаем оплате, решит сеть

    if balance_nano is not None and balance_nano < amount_nano + FEE_RESERVE_NANO:
        await _safe_close(client)
        raise TonPayError(
            f"На кошельке не хватает TON.\n"
            f"Нужно: {(amount_nano + FEE_RESERVE_NANO) / NANO:.4f} TON "
            f"(перевод {amount_nano / NANO:.4f} + комиссия сети)\n"
            f"Есть: {balance_nano / NANO:.4f} TON\n\n"
            "Пополни кошелёк — следующие заказы оплатятся сами. "
            "Этот оплати по ссылке ниже."
        )

    # Бронируем ДО отправки: если такой платёж уже начинали — выходим сразу.
    # Дневной лимит проверяется ещё раз ВНУТРИ той же транзакции, что и бронь:
    # check_limits() выше читает сумму за день до открытия кошелька, и между
    # этими двумя моментами успевает проскочить соседний заказ.
    daily_cap_nano = int(config.TON_AUTO_PAY_DAILY_MAX_TON * NANO)
    if not await claim_ton_payment(
        order_id, purpose, amount_nano, destination, daily_cap_nano
    ):
        await _safe_close(client)
        raise TonPayError(
            f"Платёж по заказу #{order_id} ({purpose}) не забронирован: либо его "
            f"уже отправляли, либо упёрлись в дневной лимит "
            f"{config.TON_AUTO_PAY_DAILY_MAX_TON} TON. "
            "Проверь кошелёк и marketapp.org."
        )

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

    # Остаток после перевода — чтобы предупредить о низком балансе ЗАРАНЕЕ,
    # а не когда деньги уже кончились посреди наплыва клиентов.
    left_nano = None if balance_nano is None else balance_nano - amount_nano

    return {
        "amount_ton": amount_nano / NANO,
        "address": address,
        "tx_hash": str(tx_hash) if tx_hash else None,
        "balance_left_ton": None if left_nano is None else round(left_nano / NANO, 4),
        "low_balance": bool(
            left_nano is not None and left_nano < config.TON_LOW_BALANCE_ALERT_TON * NANO
        ),
    }
