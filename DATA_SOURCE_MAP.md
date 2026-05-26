# DATA_SOURCE_MAP (MVP)

Goal: replace the operational leader's manual work by pulling raw data directly from ITigris, computing metrics, and generating management/trainer outputs.

Important:
- XLSX dashboard = reference for final KPI layout and expected numbers.
- DataLens/QL exports = reference for *which fields* and *which calculations* are needed.
- Final source (v2+) must be ITigris directly (not DataLens files).

Status legend:
- ✅ already automated in backend
- 🟡 available as reference (we have a file/export), but not auto-fetched yet
- 🔴 needs reverse engineering (HAR/DevTools) or missing source

## Inventory / Stock (Товарка)

| KPI / Output | Current Manual Source | Fields Needed | Target ITigris Source (v2) | Backend Status |
|---|---|---|---|---|
| Stock by product filters (brand/design/model/target group) | ITigris remainGoodsReport | department, qty_units/qty_packs/value, brand, design, model, target_group, material, type, color, size | remainGoodsReport export (.xls) + parser | ✅ (`/product-search`, `/low-stock-models`, `/auto/refresh`) |
| Low stock list (“модели по 1 штуке”) | ITigris remainGoodsReport | same + grouping keys | remainGoodsReport export (.xls) | ✅ (`/low-stock-models`) |

## Sales / Orders (Продажи / Заказы)

### A) Orders master (Отчет по заказам)

| KPI / Output | Current Manual Source | Fields Needed | Target ITigris Source (v2) | Status |
|---|---|---|---|---|
| Revenue (выручка) by salon, month + week I–V | ITigris orders report -> dashboard | order_id, created_at/closed_at, status, department, sums (gross/net/discount), payment fields | ITigris “Orders report” endpoint/export (the same that produces QL export) | 🟡 reference file exists, auto-fetch 🔴 |
| Average order check (средний чек) | same | revenue / orders count, filter to completed orders | same as above | 🟡/🔴 |
| Order structure: frames/lenses/contacts/etc in order | same | per-category sums or line items | either a richer orders report or multiple category line exports | 🟡/🔴 |

Reference file(s) (not final source):
- `Отчет по заказам - optima_odl - QL-чарт_*.xlsx` (sheet `Chart data`)

### B) Unfinished orders (Незавершенные заказы)

| KPI / Output | Current Manual Source | Fields Needed | Target ITigris Source (v2) | Status |
|---|---|---|---|---|
| Backlog risk: “готов / не оплачен / к доплате” | ITigris unfinished orders report -> dashboard | order_id, status, department, consultant, sum, paid, to_pay, created_at, closed_at | ITigris unfinished orders report export | 🟡 reference file exists, auto-fetch 🔴 |

Reference file(s):
- `Незавершенные заказы - odl - QL-чарт_*.xlsx`

### C) Conversion (Конверсия)

| KPI / Output | Current Manual Source | Fields Needed | Target ITigris Source (v2) | Status |
|---|---|---|---|---|
| Conversion (sales/visitors) monthly | ITigris conversion report -> dashboard | period, visitors, value, conversion | ITigris conversion dataset/export | 🟡 reference file exists, auto-fetch 🔴 |
| Check conversion weekly (проверки) | ITigris checks conversion -> dashboard | period, clients, value, conversion | ITigris checks dataset/export | 🟡 reference file exists, auto-fetch 🔴 |

Reference file(s):
- `Конверсия - odl - QL-чарт_*.xlsx`
- `Конверсия проверок - odl - QL-чарт_*.xlsx`

### D) Frames / Lenses line exports (Оправы / Линзы как строки заказов)

These are *sales line* datasets, useful for mix and training insights (not stock).

| KPI / Output | Current Manual Source | Fields Needed | Target ITigris Source (v2) | Status |
|---|---|---|---|---|
| Frames mix by brand/design/model | ITigris paid line export -> dashboard | order_id, department, consultant, manufacturer, brand, model, color, size, created_at/closed_at, status | ITigris frames lines export | 🟡 reference file exists, auto-fetch 🔴 |
| Lenses mix (photochromic/technology/manufacturer/brand) | ITigris paid line export -> dashboard | order_id, department, consultant, category, manufacturer, brand, technology, color, created_at/closed_at, status | ITigris lenses lines export | 🟡 reference file exists, auto-fetch 🔴 |

Reference file(s):
- `Оправы - odl - QL-чарт_*.xlsx`
- `odl - Данные отчета по линзам - QL-чарт_*.xlsx`

### E) Clients / attribution (Клиенты и заказы)

| KPI / Output | Current Manual Source | Fields Needed | Target ITigris Source (v2) | Status |
|---|---|---|---|---|
| Client sources (“откуда узнал”) and client counts | ITigris report -> dashboard | department, source_channel, clients_total, clients_with_sales, clients_with_checks, sum_orders | ITigris clients attribution export | 🟡 reference file exists, auto-fetch 🔴 |

Reference file(s):
- `Клиенты и заказы - odl_*.xlsx`

## Dashboard XLSX (Управленческий файл)

The dashboard workbook is a *target layout & expected results*, not a raw source.

| Sheet / Section | Meaning | Source Today | Target (v2) |
|---|---|---|---|
| `показатели <month>` | KPI pivots (plan/fact/deviation) | manual entry from ITigris reports | computed from ITigris datasets above |
| `оправы <month>` | frames mix pivots | manual/pivot from paid exports | computed from ITigris frames lines export |
| `линзы <month>` | lenses mix pivots | manual/pivot from paid exports | computed from ITigris lenses lines export |
| `консопто <month>` / `врач <month>` | people performance | manual/pivot from ITigris | computed from ITigris orders + people attribution |

Status:
- 🟡 We can parse it (analytics v1), but it is not the final source.

## What We Already Have Automated (as baseline)

✅ remainGoodsReport (stock) pipeline:
- login/bootstrap/export
- snapshots per report_type
- `/product-search` + `group_by`
- `/low-stock-models`

## What Needs Reverse Engineering Next (HAR/DevTools)

Priority order (v2):
1. Orders master export (the one behind `Отчет по заказам ... QL-чарт`)
2. Unfinished orders export
3. Conversion exports (monthly + weekly checks)
4. Frames lines export
5. Lenses lines export
6. Clients attribution export

For each export we need to capture:
- URL(s) called on “Export”
- method + payload + query params (filters: date range, department, status)
- auth mechanism (cookies / bearer / headers)
- file download endpoint (content-disposition, format xlsx/csv)

## MVP v1 Manual Remainders

Until v2 auto-fetch exists:
- These datasets remain manual downloads.
- The dashboard XLSX remains a reference truth for validating computed KPIs.

