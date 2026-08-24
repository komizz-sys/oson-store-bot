# Деплой бота через GitHub + Railway (без терминала)

## Шаг 1. Залить код на GitHub

1. Зайди на [github.com](https://github.com) → New repository
2. Назови, например, `tg-shop-bot` → **обязательно Private** (внутри есть чувствительные
   настройки) → Create repository
3. На странице репозитория нажми **Add file → Upload files**
4. Перетащи туда ВСЕ файлы и папки из архива `tg_shop_bot`, КРОМЕ файла `.env`
   (в нём токен бота и ключ API — их светить на GitHub нельзя, даже в приватном репо)
5. Commit changes

## Шаг 2. Подключить Railway (бесплатный хостинг для бота)

1. Зайди на [railway.app](https://railway.app) → Login → Login with GitHub
2. New Project → **Deploy from GitHub repo** → выбери `tg-shop-bot`
3. Railway сам увидит `requirements.txt` и `Procfile`, установит всё и запустит

## Шаг 3. Внести переменные окружения (вместо .env)

Всё, что было в файле `.env`, теперь нужно вписать в Railway вручную:

1. В проекте на Railway → вкладка **Variables**
2. Добавь по одной (New Variable) — значения бери из своего файла `.env`:
   - `BOT_TOKEN`
   - `ADMIN_IDS`
   - `MARKETAPP_API_KEY`
   - `DB_PATH` = `data/shop.db`
   - `RENT_MARKUP` = `1.2`
   - `TON_GRAM_RATE_UZS` = `18250`
   - `RENT_FEE_GRAM` = `0.1`
   - `RENT_FEE_REFUND_PERCENT` = `40`
   - `STAR_UNIT_PRICE_UZS` = `213.3`
   - `PAYMENT_CARD_NUMBER`, `PAYMENT_CARD_HOLDER` — твои реквизиты для оплаты

3. После сохранения переменных Railway сам перезапустит бота

## Шаг 4. Проверить, что работает

Открой вкладку **Deployments** → последний деплой → **View Logs**.
Если видишь лог без красных ошибок — бот запущен. Напиши ему `/start` в Telegram.

## ⚠️ Важный момент про базу данных

`data/shop.db` (SQLite) на Railway по умолчанию **не сохраняется между
перезапусками** — при каждом обновлении кода база обнулится, заказы пропадут.

Для старта это не критично, но когда пойдут реальные продажи — надо подключить
постоянное хранилище:
- Railway → в проекте → **+ New → Volume** → примонтировать в `/app/data`
- Либо позже перейти на Postgres (Railway даёт бесплатную PostgreSQL базу в один клик)

Скажи, когда дойдёшь до этого шага — помогу настроить.

## Как обновлять бота потом

Просто заливаешь изменённые файлы на GitHub (Add file → Upload files, или через
GitHub Desktop) → Railway сам подхватит изменения и перезапустит бота. Ничего
руками на сервере трогать не нужно.
