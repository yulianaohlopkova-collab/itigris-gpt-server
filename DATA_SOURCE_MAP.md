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

## Critical Concepts (Must Be Explicit In v2)

### 1) Weekly logic is core (I / II / III / IV / V)

The operational dashboard is managed not only by month totals, but by:
- plan vs fact per week (I..V)
- deviation per week
- month-to-date cumulative fact (accumulating)

This implies v2 ingestion must support a stable week calendar for each month:
- week boundaries (start/end) for I..V as used by the business
- consistent assignment of orders/events to weeks

### 2) Plans are a separate source (not ITigris)

The dashboard is built around plan vs fact. Plans are not produced by ITigris and must be modeled as a separate
entity/source:
- plan by salon, by KPI, by week, by month
- owner/versioning (who sets the plan, when changed)
- export format (XLSX/CSV) for v1, then plan store (DB/Google Sheet/Notion) for v2+

We should treat plans as *first-class data*:
`PlanSource -> PlanFacts -> analytics`.

### 3) People analytics is not one block

In the real dashboard, "doctor / consultant / optometrist" blocks include distinct management views:
- sales / revenue
- avg check
- lenses/frames KPIs
- ranking and targets
- performance tracking

So in v2 we need explicit datasets keyed by employee and role, not a single generic "people performance" bucket.

### 4) Non-ITigris metrics (ROI/CPA/visitors/new clients)

Some KPIs likely come from outside ITigris (ads platforms, analytics, call-tracking, POS/traffic counters):
- ROI / CPA (marketing spend + attribution)
- visitors (traffic counters / analytics)
- new clients (CRM logic + identity resolution)

These must be explicitly marked as non-ITigris and modeled with their own ingestion path and limitations.

## Inventory / Stock (Товарка)

| KPI / Output | Current Manual Source | Fields Needed | Target ITigris Source (v2) | Backend Status |
|---|---|---|---|---|
| Stock by product filters (brand/design/model/target group) | ITigris remainGoodsReport | department, qty_units/qty_packs/value, brand, design, model, target_group, material, type, color, size | remainGoodsReport export (.xls) + parser | ✅ (`/product-search`, `/low-stock-models`, `/auto/refresh`) |
| Low stock list (“модели по 1 штуке”) | ITigris remainGoodsReport | same + grouping keys | remainGoodsReport export (.xls) | ✅ (`/low-stock-models`) |

## Sales / Orders (Продажи / Заказы)

### A) Orders master (Отчет по заказам)

| KPI / Output | Current Manual Source | Fields Needed | Target ITigris Source (v2) | Status |
|---|---|---|---|---|
| Revenue (выручка) by salon, month + week I–V | ITigris orders report -> dashboard | order_id, created_at/closed_at, status, department, sums (gross/net/discount), payment fields + week assignment | ITigris “Orders report” endpoint/export (the same that produces QL export) | 🟡 reference file exists, auto-fetch 🔴 |
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
7. (Non-ITigris) Visitors/traffic source + marketing spend source, if ROI/CPA must be automated

For each export we need to capture:
- URL(s) called on “Export”
- method + payload + query params (filters: date range, department, status)
- auth mechanism (cookies / bearer / headers)
- file download endpoint (content-disposition, format xlsx/csv)

## MVP v1 Manual Remainders

Until v2 auto-fetch exists:
- These datasets remain manual downloads.
- The dashboard XLSX remains a reference truth for validating computed KPIs.
