"""
Проверка initData, которую Telegram WebApp даёт мини-аппу (window.Telegram.WebApp.initData).

Нужна, чтобы отдавать личные данные (историю заказов, свою статистику) только
реальному владельцу — иначе любой человек мог бы просто подставить чужой
user_id в запрос и увидеть заказы другого человека.

Алгоритм ровно по официальной документации Telegram:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict | None:
    """-> {"id": int, "username": str|None, "first_name": str, ...} если подпись верна, иначе None."""
    if not init_data or not bot_token:
        return None

    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    auth_date = pairs.get("auth_date")
    if auth_date and max_age_seconds:
        if time.time() - int(auth_date) > max_age_seconds:
            return None  # старая, протухшая ссылка — просим открыть заново

    user_raw = pairs.get("user")
    if not user_raw:
        return None
    try:
        return json.loads(user_raw)
    except json.JSONDecodeError:
        return None
