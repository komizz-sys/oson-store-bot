"""
API возвращает транзакцию в формате TonConnect (validUntil + messages[]).
Превращаем каждое сообщение в ton://transfer-ссылку — админ открывает её
на телефоне, кошелёк (Tonkeeper и т.п.) открывается с уже заполненными
данными, остаётся только подтвердить.

ВАЖНО: это стандартная, но не officially-guaranteed-100%-в-каждом-кошельке
схема deep link'ов. Протестируй на маленькой сумме перед боевым использованием.
"""

from urllib.parse import quote


def build_ton_deeplinks(tx: dict) -> list[str]:
    links = []
    for msg in tx["transaction"]["messages"]:
        address = msg["address"]
        amount = msg["amount"]
        payload = msg.get("payload")
        state_init = msg.get("stateInit")

        link = f"ton://transfer/{address}?amount={amount}"
        if payload:
            link += f"&bin={quote(payload, safe='')}"
        if state_init:
            link += f"&init={quote(state_init, safe='')}"
        links.append(link)
    return links
