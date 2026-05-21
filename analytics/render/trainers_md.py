from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..contracts import KPIBlock, MonthFacts


def _fmt_money(x: Any) -> str:
    try:
        v = float(str(x).replace(" ", "").replace("\u00a0", "").replace(",", "."))
    except Exception:
        return str(x)
    return f"{v:,.0f}".replace(",", " ")


def _fmt_num(x: Any) -> str:
    try:
        v = float(str(x).replace(" ", "").replace("\u00a0", "").replace(",", "."))
    except Exception:
        return str(x)
    if abs(v - int(v)) < 1e-9:
        return str(int(v))
    return f"{v:.2f}"


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, str) and x.strip() in {"", "-", "#DIV/0!"}:
            return None
        return float(str(x).replace(" ", "").replace("\u00a0", "").replace(",", "."))
    except Exception:
        return None


def _worst_consultants(block: KPIBlock, top_n: int = 8) -> List[Dict[str, Any]]:
    # Columns vary; find month plan/fact/dev by header.
    h = [str(x or "").strip().lower() for x in (block.header or [])]
    def _find(substr: str) -> Optional[int]:
        for i, v in enumerate(h):
            if substr in v:
                return i
        return None
    idx_name = 0
    idx_plan = _find("план, 05.2026") or _find("план,") or 1
    idx_fact = _find("факт, 05.2026") or _find("факт,") or 2
    idx_dev = _find("отклонение, 05.2026") or _find("отклонение,") or 3

    items = []
    for r in block.rows:
        if not r or not r[0] or str(r[0]).lower().startswith("общее"):
            continue
        dev = _safe_float(r[idx_dev] if idx_dev < len(r) else None)
        if dev is None:
            continue
        items.append(
            {
                "name": r[idx_name] if idx_name < len(r) else "",
                "plan": r[idx_plan] if idx_plan < len(r) else None,
                "fact": r[idx_fact] if idx_fact < len(r) else None,
                "dev": dev,
            }
        )
    return sorted(items, key=lambda x: x["dev"])[:top_n]


def render_trainers_md(facts: MonthFacts, signals: Dict[str, Any]) -> str:
    """
    MVP v1 trainer-facing brief:
    - where conversion / revenue is down (salons)
    - who has biggest plan/fact negative deltas (consultants)
    - suggested training focus areas (heuristic mapping)
    """
    meta = facts.month_meta
    picked = facts.kpi_blocks_picked

    lines: List[str] = []
    lines.append(f"# Trainers Brief — {meta.month}")
    lines.append("")
    lines.append("Фокус: просадки по салонам, категории, и точечные 1:1 по людям. Это MVP v1 (heuristics).")
    lines.append("")

    # Salon signals
    rev_down = next((s for s in (signals.get("signals") or []) if s.get("type") == "top_down" and s.get("key") == "revenue"), None)
    conv_down = next((s for s in (signals.get("signals") or []) if s.get("type") == "top_down" and s.get("key") == "conversion"), None)

    if conv_down and conv_down.get("items"):
        lines.append("## Просадки по конверсии (салоны)")
        lines.append("")
        for it in conv_down["items"][:5]:
            lines.append(f"+ {it['name']}: факт {it.get('fact')}, отклонение {it.get('dev')}")
        lines.append("")
        lines.append("Рекомендации (v1): скрипт выявления потребности, работа с возражениями, пакетирование (оправа+линзы/МКЛ+раствор).")
        lines.append("")

    if rev_down and rev_down.get("items"):
        lines.append("## Просадки по выручке (салоны)")
        lines.append("")
        for it in rev_down["items"][:5]:
            lines.append(f"+ {it['name']}: факт {_fmt_money(it.get('fact'))}, отклонение {it.get('dev')}")
        lines.append("")
        lines.append("Рекомендации (v1): разбор структуры чека (категории/микс), контроль допродаж, дисциплина записи/доведения до оплаты.")
        lines.append("")

    # People blocks: consultants
    cons = facts.people_blocks.get("consultants") if isinstance(facts.people_blocks.get("consultants"), dict) else None
    cons_blocks = cons.get("blocks") if isinstance(cons, dict) else None
    if isinstance(cons_blocks, dict) and cons_blocks:
        lines.append("## Кто проседает по плану (люди)")
        lines.append("")
        for key, label in [
            ("photochromic_consultants", "Фотохромы (линзы)"),
            ("sold_sunglasses_consultants", "Солнцезащитные очки"),
            ("sold_frames_consultants", "Оправы"),
            ("sold_lenses_consultants", "Линзы"),
        ]:
            blk = cons_blocks.get(key)
            if not blk:
                continue
            worst = _worst_consultants(blk, top_n=6)
            if not worst:
                continue
            lines.append(f"### {label}")
            for it in worst[:6]:
                lines.append(f"+ {it['name']}: план {_fmt_num(it.get('plan'))}, факт {_fmt_num(it.get('fact'))}, откл {_fmt_num(it.get('dev'))}")
            lines.append("")

        lines.append("## Навыки для прокачки (v1)")
        lines.append("")
        lines.append("- Если просадка по оправам: презентация бренда/дизайна, подбор по форме лица, апселл на бренд/СТМ.")
        lines.append("- Если просадка по линзам: объяснение индекса/покрытий, аргументация фотохрома, апселл Better-Best.")
        lines.append("- Если просадка по МКЛ/солнцу: повторный контакт, допродажа растворов/аксессуаров, закрытие на оплату.")
        lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append(f"- Source: {facts.source_type} ({facts.source_id})")
    lenses_pack = (facts.mix_blocks or {}).get("lenses") if isinstance(facts.mix_blocks, dict) else None
    if isinstance(lenses_pack, dict) and isinstance(lenses_pack.get("source"), dict):
        src = lenses_pack["source"]
        lines.append(f"- Линзы: fallback source = {src.get('type')} ({src.get('id')} :: {src.get('entry')})")
    lines.append("- Это тренерский вывод v1; уточним метрики/триггеры после 1–2 циклов применения.")
    lines.append("")
    return "\n".join(lines)
