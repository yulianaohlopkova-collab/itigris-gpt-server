from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from ..contracts import MonthFacts, monthfacts_to_dict


def write_month_facts_json(facts: MonthFacts, out_path: str) -> None:
    Path(out_path).write_text(json.dumps(monthfacts_to_dict(facts), ensure_ascii=False, indent=2), encoding="utf-8")

def _safe_float(x: Any) -> Any:
    try:
        if x is None:
            return None
        if isinstance(x, str) and x.strip() in {"", "-", "#DIV/0!"}:
            return None
        return float(str(x).replace(" ", "").replace("\u00a0", "").replace(",", "."))
    except Exception:
        return None


def build_signals(facts: MonthFacts) -> Dict[str, Any]:
    """
    MVP v1 signals:
    - revenue top up/down by % deviation
    - conversion top up/down by % deviation (if available)
    - consultants: top negative deviations for key blocks (if present)
    """
    month = facts.month_meta.month
    out: Dict[str, Any] = {
        "month": month,
        "source": {"type": facts.source_type, "id": facts.source_id, "generated_at_unix": facts.generated_at_unix},
        "signals": [],
    }

    def add_top_deltas(block, key: str, metric: str, top_n: int = 3):
        if not block:
            return
        rows = block.rows
        items = []
        for r in rows:
            if not r or not r[0] or str(r[0]).lower().startswith("общий"):
                continue
            dev = _safe_float(r[3] if len(r) > 3 else None)
            if dev is None:
                continue
            items.append({"name": r[0], "plan": r[1] if len(r) > 1 else None, "fact": r[2] if len(r) > 2 else None, "dev": dev})
        if not items:
            return
        up = sorted(items, key=lambda x: x["dev"], reverse=True)[:top_n]
        down = sorted(items, key=lambda x: x["dev"])[:top_n]
        out["signals"].append({"type": "top_up", "key": key, "metric": metric, "items": up})
        out["signals"].append({"type": "top_down", "key": key, "metric": metric, "items": down})

    picked = facts.kpi_blocks_picked
    add_top_deltas(picked.get("revenue"), "revenue", "deviation_pct")
    add_top_deltas(picked.get("conversion"), "conversion", "deviation_pct")

    # Lenses mix (v1): if we have a photochromic-by-department block, surface top/bottom salons by revenue.
    try:
        lenses_pack = (facts.mix_blocks or {}).get("lenses") or {}
        lenses_blocks = lenses_pack.get("blocks") if isinstance(lenses_pack, dict) else {}
        photo_blk = None
        if isinstance(lenses_blocks, dict):
            photo_blk = lenses_blocks.get("photochromic_by_department_brand") or lenses_blocks.get("photochromic")
        if photo_blk and getattr(photo_blk, "rows", None):
            agg: Dict[str, Dict[str, float]] = {}
            for r in photo_blk.rows:
                if not r or not r[0]:
                    continue
                name = str(r[0]).strip()
                # Expected row shape: [dept, brand, sum_rub, share_pct, count, avg_rub]
                sum_v = _safe_float(r[2] if len(r) > 2 else None)
                cnt_v = _safe_float(r[4] if len(r) > 4 else None)
                if sum_v is None:
                    continue
                a = agg.setdefault(name, {"sum_rub": 0.0, "count": 0.0})
                a["sum_rub"] += float(sum_v)
                a["count"] += float(cnt_v or 0.0)
            if agg:
                items_sorted = sorted(
                    [{"name": k, "sum_rub": v["sum_rub"], "count": v["count"]} for k, v in agg.items()],
                    key=lambda x: x["sum_rub"],
                    reverse=True,
                )
                out["signals"].append({"type": "lenses_photochromic_top", "key": "lenses_photochromic", "metric": "sum_rub", "items": items_sorted[:5]})
                out["signals"].append({"type": "lenses_photochromic_bottom", "key": "lenses_photochromic", "metric": "sum_rub", "items": list(reversed(items_sorted[-5:]))})
    except Exception:
        pass

    # Consultant blocks: we treat column 3 as absolute deviation for the month.
    cons = (facts.people_blocks.get("consultants") or {}).get("blocks") if isinstance(facts.people_blocks.get("consultants"), dict) else None
    if isinstance(cons, dict):
        for bkey in ["sold_frames_consultants", "sold_lenses_consultants", "sold_sunglasses_consultants", "photochromic_consultants"]:
            blk = cons.get(bkey)
            if not blk:
                continue
            items = []
            for r in blk.rows:
                if not r or not r[0] or str(r[0]).lower().startswith("общее"):
                    continue
                dev = _safe_float(r[3] if len(r) > 3 else None)
                if dev is None:
                    continue
                items.append({"name": r[0], "plan": r[1] if len(r) > 1 else None, "fact": r[2] if len(r) > 2 else None, "dev": dev})
            if not items:
                continue
            worst = sorted(items, key=lambda x: (x["dev"] if x["dev"] is not None else 0.0))[:5]
            out["signals"].append({"type": "consultants_worst", "key": bkey, "metric": "dev_abs", "items": worst})

    return out


def build_actions(facts: MonthFacts, signals: Dict[str, Any]) -> Dict[str, Any]:
    """
    MVP v1 action list derived from signals. Owners are placeholders to be filled/adjusted.
    """
    actions = []
    month = facts.month_meta.month

    def mk(owner: str, title: str, due: str, kpi_check: str, rationale: str):
        actions.append(
            {
                "owner": owner,
                "title": title,
                "due": due,
                "kpi_check": kpi_check,
                "rationale": rationale,
                "month": month,
            }
        )

    for s in signals.get("signals") or []:
        if s.get("type") == "top_down" and s.get("key") == "revenue":
            items = s.get("items") or []
            if items:
                mk(
                    owner="Коммерческий директор",
                    title=f"Разобрать просадку выручки: {', '.join([i['name'] for i in items[:3]])}",
                    due=f"{month} + 7d",
                    kpi_check="Выручка (факт) и отклонение vs план на следующей неделе месяца",
                    rationale="Сигнал v1: топ просадка по отклонению в выручке.",
                )
        if s.get("type") == "top_down" and s.get("key") == "conversion":
            items = s.get("items") or []
            if items:
                mk(
                    owner="Тренер",
                    title=f"План обучения по конверсии: {', '.join([i['name'] for i in items[:3]])}",
                    due=f"{month} + 14d",
                    kpi_check="Конверсия продажа/посетитель + средний чек",
                    rationale="Сигнал v1: просадка конверсии по салонам.",
                )
        if s.get("type") == "consultants_worst":
            items = s.get("items") or []
            if items:
                mk(
                    owner="Тренер",
                    title=f"Точечные 1:1 по отклонениям ({s.get('key')}): {', '.join([i['name'] for i in items[:3]])}",
                    due=f"{month} + 10d",
                    kpi_check="Факт vs план по категории на следующей неделе",
                    rationale="Сигнал v1: худшие отклонения по консультантам/оптометристам.",
                )

        if s.get("type") == "lenses_photochromic_bottom":
            items = s.get("items") or []
            if items:
                mk(
                    owner="Коммерческий директор",
                    title=f"Фотохромы (ОЛ): разобрать просадку по салонам: {', '.join([i['name'] for i in items[:3]])}",
                    due=f"{month} + 10d",
                    kpi_check="Фотохромы: выручка и кол-во по салонам (следующая неделя)",
                    rationale="Сигнал v1: нижние салоны по выручке фотохромных ОЛ.",
                )

    return {"month": month, "actions": actions}


def write_signals_json(facts: MonthFacts, out_path: str) -> None:
    """
    MVP v1: minimal real signals.
    """
    signals = build_signals(facts)
    Path(out_path).write_text(json.dumps(signals, ensure_ascii=False, indent=2), encoding="utf-8")
