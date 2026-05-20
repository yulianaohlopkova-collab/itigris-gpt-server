from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ..contracts import KPIBlock, MonthFacts


def _fmt_money(x: Any) -> str:
    try:
        v = float(x)
    except Exception:
        return str(x)
    return f"{v:,.0f}".replace(",", " ")


def _fmt_pct(x: Any) -> str:
    try:
        if x is None:
            return "-"
        if isinstance(x, str) and x.strip() in {"", "-", "#DIV/0!"}:
            return "-"
        v = float(x)
    except Exception:
        return str(x)
    if abs(v) <= 1.5:
        return f"{v*100:.1f}%"
    return f"{v:.1f}%"


def _top_deltas(rows: List[List[str]], idx_name: int, idx_fact: int, idx_dev: int, top_n: int = 3) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    items: List[Dict[str, Any]] = []
    for r in rows:
        if not r:
            continue
        name = r[idx_name] if idx_name < len(r) else ""
        if not name or name.lower().startswith("общий"):
            continue
        try:
            dev = float(r[idx_dev])
        except Exception:
            continue
        items.append({"department": name, "fact": r[idx_fact] if idx_fact < len(r) else None, "dev": dev})
    up = sorted(items, key=lambda x: x["dev"], reverse=True)[:top_n]
    down = sorted(items, key=lambda x: x["dev"])[:top_n]
    return up, down


def _add_kpi_table(lines: List[str], title: str, block: KPIBlock, value_fmt) -> None:
    rows = block.rows
    lines.append(f"## {title}")
    lines.append("")
    lines.append("| Салон | План (мес) | Факт (мес) | Отклонение |")
    lines.append("|---|---:|---:|---:|")
    for r in rows:
        if not r or not r[0] or r[0].lower().startswith("общий"):
            continue
        plan = r[1] if len(r) > 1 else ""
        fact = r[2] if len(r) > 2 else ""
        dev = r[3] if len(r) > 3 else ""
        lines.append(f"| {r[0]} | {value_fmt(plan)} | {value_fmt(fact)} | {_fmt_pct(dev)} |")
    lines.append("")


def render_management_md(facts: MonthFacts) -> str:
    meta = facts.month_meta
    picked = facts.kpi_blocks_picked

    rev = picked.get("revenue")
    aov = picked.get("avg_order_check")
    inc = picked.get("avg_income_per_client")
    conv = picked.get("conversion")

    lines: List[str] = []
    lines.append(f"# Monthly Management Package — {meta.month}")
    lines.append("")
    lines.append(f"Период: {meta.start[:10]} — {meta.end[:10]} (недель: {len(meta.weeks)})")
    lines.append("")

    if rev:
        idx_name = 0
        idx_fact = 2
        idx_dev = 3
        up, down = _top_deltas(rev.rows, idx_name, idx_fact, idx_dev, top_n=3)
        lines.append("## Сигналы (v1)")
        lines.append("")
        lines.append("**Выручка: топ рост / просадка (отклонение, месяц)**")
        for it in up:
            lines.append(f"+ Рост: {it['department']} — факт {_fmt_money(it['fact'])}, отклонение {_fmt_pct(it['dev'])}")
        for it in down:
            lines.append(f"+ Просадка: {it['department']} — факт {_fmt_money(it['fact'])}, отклонение {_fmt_pct(it['dev'])}")
        lines.append("")

    if rev:
        _add_kpi_table(lines, "Выручка", rev, _fmt_money)
    if aov:
        _add_kpi_table(lines, "Средний чек заказа", aov, _fmt_money)
    if inc:
        _add_kpi_table(lines, "Средний доход от клиента", inc, _fmt_money)
    if conv:
        _add_kpi_table(lines, "Конверсия (продажа/посетитель)", conv, _fmt_pct)

    lines.append("## Notes")
    lines.append("")
    lines.append(f"- Source: {facts.source_type} ({facts.source_id})")
    lines.append("- Это MVP v1: 3–5 KPI из листа `показатели 05.2026` + сигналы по отклонениям.")
    lines.append("- Mix (Оправы СТМ / Фотохромы / Better-Best) будет добавлен следующим шагом из листов `оправы 05.2026` и `линзы 05.2026`.")
    lines.append("")
    return "\n".join(lines)
