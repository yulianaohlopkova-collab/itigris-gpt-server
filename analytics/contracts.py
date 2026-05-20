from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class WeekMeta:
    name: str  # I..V
    start: str  # ISO-ish string from XLS (keep as string for stability)
    end: str
    days: int


@dataclass
class MonthMeta:
    month: str  # e.g. 05.2026
    start: str
    end: str
    days: int
    weeks: List[WeekMeta]


@dataclass
class KPIBlock:
    """
    A KPI block as extracted from the dashboard sheet.
    `header` and `rows` preserve the original order and strings.
    """

    title: str
    header: List[str]
    rows: List[List[str]]


@dataclass
class MonthFacts:
    """
    Canonical internal representation for a monthly package.
    This is the contract between ingestion and:
    - signals engine
    - report rendering (management/trainers)

    The ingestion source (manual XLS in v1, auto-fetch in v2) can be swapped without
    rewriting signals/report logic as long as it outputs MonthFacts.
    """

    month_meta: MonthMeta
    # All detected KPI blocks (for debug/iterating selection)
    kpi_blocks_all: List[KPIBlock]
    # MVP selection of key KPI blocks by semantic key
    kpi_blocks_picked: Dict[str, KPIBlock]
    # Optional future sections (v1 may keep empty)
    mix_blocks: Dict[str, Any]
    orders_blocks: Dict[str, Any]
    people_blocks: Dict[str, Any]
    # Provenance
    source_type: str  # e.g. "xlsx_manual", "auto_fetch"
    source_id: str  # filename/url identifier
    generated_at_unix: int


def monthfacts_to_dict(f: MonthFacts) -> Dict[str, Any]:
    def wk(w: WeekMeta) -> Dict[str, Any]:
        return {"name": w.name, "start": w.start, "end": w.end, "days": w.days}

    def meta(m: MonthMeta) -> Dict[str, Any]:
        return {"month": m.month, "start": m.start, "end": m.end, "days": m.days, "weeks": [wk(x) for x in m.weeks]}

    def block(b: KPIBlock) -> Dict[str, Any]:
        return {"title": b.title, "header": list(b.header), "rows": [list(r) for r in b.rows]}

    return {
        "month_meta": meta(f.month_meta),
        "kpi_blocks_all": [block(b) for b in f.kpi_blocks_all],
        "kpi_blocks_picked": {k: block(v) for k, v in f.kpi_blocks_picked.items()},
        "mix_blocks": f.mix_blocks,
        "orders_blocks": f.orders_blocks,
        "people_blocks": f.people_blocks,
        "source": {
            "type": f.source_type,
            "id": f.source_id,
            "generated_at_unix": f.generated_at_unix,
        },
    }


def monthfacts_from_dict(obj: Dict[str, Any]) -> MonthFacts:
    mm = obj.get("month_meta") or {}
    weeks = [WeekMeta(**w) for w in (mm.get("weeks") or [])]
    month_meta = MonthMeta(
        month=str(mm.get("month") or ""),
        start=str(mm.get("start") or ""),
        end=str(mm.get("end") or ""),
        days=int(mm.get("days") or 0),
        weeks=weeks,
    )

    def mk_block(b: Dict[str, Any]) -> KPIBlock:
        return KPIBlock(title=str(b.get("title") or ""), header=list(b.get("header") or []), rows=list(b.get("rows") or []))

    all_blocks = [mk_block(b) for b in (obj.get("kpi_blocks_all") or [])]
    picked = {k: mk_block(v) for k, v in (obj.get("kpi_blocks_picked") or {}).items()}
    src = obj.get("source") or {}
    return MonthFacts(
        month_meta=month_meta,
        kpi_blocks_all=all_blocks,
        kpi_blocks_picked=picked,
        mix_blocks=obj.get("mix_blocks") or {},
        orders_blocks=obj.get("orders_blocks") or {},
        people_blocks=obj.get("people_blocks") or {},
        source_type=str(src.get("type") or ""),
        source_id=str(src.get("id") or ""),
        generated_at_unix=int(src.get("generated_at_unix") or 0),
    )

