# ODL Sales Analyst MVP

Рабочая MVP-версия ИИ-аналитика продаж для «Очкидалинзы».

## Быстрый запуск

```bash
python -m py_compile server.py
uvicorn server:app --host 0.0.0.0 --port 8000
```

Для protected endpoints нужен `ODL_SERVER_TOKEN`.

```bash
export ODL_SERVER_TOKEN=dev-token
curl -H "X-ODL-Token: dev-token" http://localhost:8000/categories
```

## Render

`Procfile`:

```txt
web: uvicorn server:app --host 0.0.0.0 --port $PORT
```

Environment:

- `ITIGRIS_APP_NAME`
- `ITIGRIS_REMOTE_API_KEY` или `ITIGRIS_API_KEY`
- `ITIGRIS_EXTERNAL_API_KEY` optional
- `ODL_SERVER_TOKEN`
- `ITIGRIS_REMAINGOODSREPORT_URL_TEMPLATE` optional (auto-fetch remainGoodsReport для точных остатков МКЛ)
- `ITIGRIS_REMAINGOODSREPORT_WEB_COOKIE` optional (Cookie header, если авто-fetch возможен только через web session)
- `ITIGRIS_REMAINGOODSREPORT_WEB_USER_ID` optional
- `ITIGRIS_REMAINGOODSREPORT_WEB_PAGE_UUID` optional
- `ITIGRIS_REMAINGOODSREPORT_WEB_UUID_VALUE` optional
- `ITIGRIS_REMAINGOODSREPORT_WEB_COMPANY_UUID` optional (default = ITIGRIS_APP_NAME)
- `ITIGRIS_REMAINGOODSREPORT_WEB_DEPARTMENT_IDS` optional (comma-separated; default = all known departments in server)
- `ITIGRIS_WEB_LOGIN` optional (логин Optima Web; предпочтительный способ авто-обновления)
- `ITIGRIS_WEB_PASSWORD` optional
- `ITIGRIS_WEB_KEY` optional
- `ITIGRIS_WEB_LOGIN_URL` optional (default `https://optima.itigris.ru/{app}/login/login`)
- `ITIGRIS_WEB_VERSION_DESC` optional (как в браузере, напр. `670_27.04.2026`)
- `ITIGRIS_WEB_BROWSER_DESC` optional (как в браузере; можно положить User-Agent)
- `ITIGRIS_WEB_USER_AGENT` optional (User-Agent header для web login/report requests)
- `ITIGRIS_WEB_PAGE_UUID` optional (fallback: если сервер не смог извлечь pageUUID из pre-login HTML)
- `ITIGRIS_WEB_UUID_VALUE` optional (fallback: если сервер не смог извлечь uuidValue из pre-login HTML)
- `ITIGRIS_WEB_USER_ID` optional (fallback)
- `REMAINGOODS_AUTO_REFRESH_MIN_SECONDS` optional (default 600)

## Реальный прогон MVP

```bash
python scripts/extract_ods_mvp.py
python scripts/run_weekly_report.py
```

Результат:

- `data/input/*.csv`
- `reports/weekly_output_2026-04-01_2026-04-26.md`

## API

- `/healthz`
- `/departments`
- `/categories`
- `/remains-filtered`
- `/count-by-filters`
- `/count-by-price/{category}`
- `/count/{category}`
- `/breakdown/{category}`
- `/gpt/breakdown/{category}`
- `/sales/analyze`

Важно: ITigris `remoteRemains` — это остатки, не продажи.

## Contact lenses (МКЛ): точные остатки

`remoteRemains` по МКЛ не отдает "шт" и может недосчитывать открытые упаковки. Для точного ответа (упаковки / штуки / сумма)
используется выгрузка `remainGoodsReport`:

- `POST /contactlenses/remainGoodsReport/analyze` (multipart .xls/.xlsx/.csv)
- `POST /contactlenses/remainGoodsReport/analyze-csv` (JSON, GPT-friendly)
- `POST /contactlenses/remainGoodsReport/analyze-base64` (JSON, GPT-friendly)

Чтобы убрать ручную загрузку snapshot, можно настроить авто-подтягивание отчета:

1. В Render env задать `ITIGRIS_REMAINGOODSREPORT_URL_TEMPLATE` (URL-шаблон экспорта, поддерживает `{app}`, `{key}`, `{external_key}`).
2. Вызывать `POST /contactlenses/remainGoodsReport/auto/refresh` (или просто `GET /contactlenses/stock/{department_name}?source=auto`).

Проверка: `GET /contactlenses/remainGoodsReport/auto/status`.
