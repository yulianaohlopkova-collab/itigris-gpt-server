# Baseline: Product Intelligence (Working)

Date: 2026-05-19 (Asia/Yakutsk)

This document marks a known-good baseline for the "product intelligence" layer:
accurate stock answers from ITigris remainGoodsReport snapshots, including detailed
product filtering via `productSearch`, and a clean GPT Actions OpenAPI schema that
prevents routing into legacy approximate endpoints.

## What Works (Must Not Break)

1. Production backend is deployed and stable.
2. ITigris Optima legacy flow:
   - auth/login/bootstrap/export chain works (cookie-only for legacy reports).
3. remainGoodsReport export and parsing:
   - parser produces correct totals (qty_packs / qty_units / value) and department rollups.
4. Category-aware snapshots:
   - `report_type` snapshots are supported (e.g. "Контактные линзы", "Оправы").
5. `productSearch`:
   - accurate filtered queries across departments and report types, backed by remainGoodsReport snapshot.
6. Clean GPT Actions schema:
   - legacy tools (remoteRemains / remains-filtered / count-by-filters) are hidden from GPT Actions.
7. Auto refresh:
   - refresh by `report_type` works.

## Working Endpoints (Production)

These endpoints are considered part of the working contract for this baseline:

1. `GET /product-search`
2. `POST /contactlenses/remainGoodsReport/auto/refresh`
3. `GET /openapi-actions.yaml`
4. `GET /healthz`

## GPT Actions Schema (Clean)

File:
- `openapi-actions.yaml`

Goal:
- expose only the minimal "truth" tools required for product stock answers:
  `productSearch` + `auto/refresh`.

## Verified Facts (Manually Cross-Checked With XLS)

Frames (Оправы), `report_type=Оправы`:

1. UNITY, design=Бабочка, department=Ленина:
   - 5 positions / 6 units / 9 140 ₽
2. UNITY, design=Бабочка, department=Айсберг:
   - 3 positions / 3 units / 4 270 ₽
3. SEEON, department=Ленина:
   - 45 positions / 50 units / 132 400 ₽
4. model=8338-C12, department=Ленина:
   - 1 position / 2 units / 1 780 ₽

Contact lenses (МКЛ), snapshot-backed productSearch:

1. Miru 1 month Menicon, department=Айсберг:
   - productSearch works through remainGoodsReport snapshot and matches XLS checks.

## Invariants / Constraints

1. Do not change the auth/bootstrap/export pipeline unless explicitly required.
2. Do not change numeric semantics:
   - `qty_packs`, `qty_units`, `value`, `unit_price` parsing must remain stable.
3. Do not reintroduce legacy approximate tools into GPT Actions schema.
4. Keep `productSearch` as the primary routing target for detailed product questions.

## Smoke Tests (Recommended After Any Change)

1. Refresh:
   - `POST /contactlenses/remainGoodsReport/auto/refresh?force=true&report_type=Оправы`
   - `POST /contactlenses/remainGoodsReport/auto/refresh?force=true&report_type=Контактные линзы`
2. productSearch queries:
   - Оправы UNITY Бабочка Ленина
   - Оправы SEEON Ленина
   - МКЛ Miru 1 month Menicon Айсберг

