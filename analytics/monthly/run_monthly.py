from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..contracts import monthfacts_to_dict
from ..ingest.xlsx_source import XlsxDashboardSource
from ..monthly.pipeline import build_actions, build_signals
from ..render.management_md import render_management_md
from ..render.trainers_md import render_trainers_md


def _default_out_dir(month_label: str) -> str:
    # month_label like "05.2026" -> "2026-05"
    parts = month_label.split(".")
    if len(parts) == 2 and len(parts[0]) in {1, 2} and len(parts[1]) == 4:
        mm = parts[0].zfill(2)
        yyyy = parts[1]
        return f"repo/reports/monthly/{yyyy}-{mm}"
    return "repo/reports/monthly/out"


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate monthly MVP package from ODL dashboard XLSX (v1 ingestion).")
    ap.add_argument("--xlsx", required=True, help="Path to ODL dashboard .xlsx export")
    ap.add_argument("--month", required=True, help='Month label used in sheet names, e.g. "05.2026"')
    ap.add_argument("--out-dir", default=None, help="Output directory (default: repo/reports/monthly/YYYY-MM)")
    args = ap.parse_args()

    xlsx_path = Path(args.xlsx)
    if not xlsx_path.exists():
        raise SystemExit(f"XLSX not found: {xlsx_path}")

    out_dir = Path(args.out_dir or _default_out_dir(args.month))
    out_dir.mkdir(parents=True, exist_ok=True)

    src = XlsxDashboardSource(str(xlsx_path))
    facts = src.load_month(args.month)

    facts_dict = monthfacts_to_dict(facts)
    facts_path = out_dir / f"facts_{args.month.replace('.', '_')}.json"
    facts_path.write_text(json.dumps(facts_dict, ensure_ascii=False, indent=2), encoding="utf-8")

    management_md = render_management_md(facts)
    (out_dir / "management.md").write_text(management_md, encoding="utf-8")

    signals = build_signals(facts)
    signals_path = out_dir / f"signals_{args.month.replace('.', '_')}.json"
    signals_path.write_text(json.dumps(signals, ensure_ascii=False, indent=2), encoding="utf-8")

    trainers_md = render_trainers_md(facts, signals)
    (out_dir / "trainers.md").write_text(trainers_md, encoding="utf-8")

    actions = build_actions(facts, signals)
    (out_dir / f"actions_{args.month.replace('.', '_')}.json").write_text(json.dumps(actions, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
