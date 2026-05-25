# Sales Analytics MVP v1 — Status (Baseline)

Date: 2026-05-21

This repo now has two layers:

1. Product intelligence baseline (remainGoodsReport, snapshots, productSearch) — stable baseline.
2. Sales analytics MVP v1 (monthly management output from ODL dashboard exports) — stable baseline.

This file tracks the current working state of (2).

## What Works (v1)

1. Monthly analytics pipeline reads an ODL dashboard XLSX export and generates a management package for a month label (e.g. `05.2026`).
2. Key KPI blocks are extracted with fuzzy/semantic selection (titles can be renamed without breaking hard-coded anchors).
3. Mix blocks:
   - Frames (Оправы): STM units (with week I..V breakdown) from sheet `оправы <month>`.
   - Lenses (Линзы): photochromic + manufacturer/brand + salon breakdown:
     - Prefer cached values from sheet `линзы <month>`.
     - Fallback to Google Sheets HTML export stored in `ODL. Дашборд.zip` entry `линзы <month>.html`.
     - PDF parsing is intentionally not used.
4. Signals/actions:
   - Revenue and conversion top up/down by deviation %.
   - Consultant worst deviations for key blocks (if available).
   - Lenses photochromic top/bottom salons by revenue (when mix block is present).

## Outputs (Generated Artifacts)

Generated under `repo/reports/monthly/YYYY-MM/`:

1. `facts_<MM_YYYY>.json` — normalized MonthFacts (contract between ingestion and reports).
2. `management.md` — management monthly package.
3. `trainers.md` — trainer brief based on signals + people blocks.
4. `signals_<MM_YYYY>.json` — machine-readable signals (MVP v1).
5. `actions_<MM_YYYY>.json` — machine-readable action list derived from signals (MVP v1).

## Data Sources (v1)

Primary:
- Manual XLSX export from ODL dashboard:
  - Example: `/Users/roomofpromise/Downloads/ODL. Дашборд(2).xlsx`

Fallback (Lenses only, when the XLS has no cached values):
- Zip export with HTML tables:
  - Example: `/Users/roomofpromise/Downloads/ODL. Дашборд.zip`
  - Entry: `линзы <month>.html`

Every lenses fallback is recorded in `management.md`/`trainers.md` Notes as:
`fallback source = zip_html (<zip_path> :: <entry>)`.

## Limitations (v1)

1. Ingestion is manual (XLSX + optional ZIP/HTML). No live fetch from ITigris/DataLens yet.
2. Lenses HTML parsing assumes a Google Sheets HTML export layout for the given month label; we avoid PDF parsing by design.
3. Signals/actions are v1 heuristics; owners/dates are placeholders and should be reviewed by management.

## Next Step (v2)

Replace v1 ingestion with live/auto ingestion while keeping analytics contracts stable:

ITigris/DataLens/dashboard export (auto fetch) -> MonthFacts -> management/trainers/signals/actions

The goal is to swap only the ingestion layer while preserving:
- MonthFacts contract
- renderers
- signals/actions engine

## Data Needed Next (v2)

To move from manual exports (v1) to auto-ingestion (v2) without rewriting analytics logic, we need a stable
programmatic export for the same logical blocks currently consumed from XLS/HTML:

1. Month meta:
   - month start/end
   - weeks I..V start/end (as currently used in the dashboard)

2. KPI blocks (plan/fact/deviation) by salon for the month:
   - revenue
   - average order check
   - average income per client
   - conversion (if available/stable)

3. Mix blocks:
   - Frames (Оправы): STM units + weekly breakdown (I..V)
   - Lenses (Линзы): photochromic and manufacturer/brand and salon breakdowns

4. People blocks:
   - consultants/opto: plan/fact/deviation by key categories (frames, lenses, sunglasses, photochromic)

Preferred export formats (best to worst):
1. CSV/XLSX export endpoint (DataLens/BI) with values (not formulas only).
2. HTML table export (like the current ZIP fallback).
3. PDF export (explicitly not preferred).

Minimal artifacts needed from ITigris/DataLens:
- One export per month (e.g. `05.2026`) that includes the same blocks, OR separate exports per sheet/section with
  a deterministic naming convention.
