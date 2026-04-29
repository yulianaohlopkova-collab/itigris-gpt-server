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
