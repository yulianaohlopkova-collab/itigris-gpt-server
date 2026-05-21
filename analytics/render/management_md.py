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

def _maybe_add_frames_mix(lines: List[str], facts: MonthFacts) -> None:
    frames = facts.mix_blocks.get("frames") if isinstance(facts.mix_blocks, dict) else None
    if not isinstance(frames, dict):
        return
    blocks = frames.get("blocks")
    if not isinstance(blocks, dict):
        return
    stm = blocks.get("stm_units")
    by_brand = blocks.get("by_brand")
    if not stm and not by_brand:
        return
    lines.append("## Mix — Оправы (v1)")
    lines.append("")
    if stm:
        lines.append("**СТМ (штуки): факт за месяц + факт по неделям**")
        lines.append("")
        lines.append("| Бренд | Факт (мес) | I | II | III | IV | V |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for r in stm.rows:
            if not r or not r[0] or str(r[0]).lower().startswith("общее"):
                continue
            # header: salon/показатель | факт_мес | доля | факт I | доля I | факт II | ...
            b = r[0]
            fact_m = r[1] if len(r) > 1 else ""
            w1 = r[3] if len(r) > 3 else ""
            w2 = r[5] if len(r) > 5 else ""
            w3 = r[7] if len(r) > 7 else ""
            w4 = r[9] if len(r) > 9 else ""
            w5 = r[11] if len(r) > 11 else ""
            lines.append(f"| {b} | {_fmt_money(fact_m)} | {_fmt_money(w1)} | {_fmt_money(w2)} | {_fmt_money(w3)} | {_fmt_money(w4)} | {_fmt_money(w5)} |")
        lines.append("")
    if by_brand:
        lines.append("**Проданные оправы по бренду (срез, если есть в дашборде)**")
        lines.append("")
        lines.append(f"- Block: {by_brand.title}")
        lines.append("")


def _maybe_add_lenses_mix(lines: List[str], facts: MonthFacts) -> None:
    lenses = facts.mix_blocks.get("lenses") if isinstance(facts.mix_blocks, dict) else None
    if not isinstance(lenses, dict):
        return
    blocks = lenses.get("blocks")
    if not isinstance(blocks, dict):
        return
    # XLS path: photochromic/by_manufacturer/by_brand
    # HTML zip fallback: *_by_department_brand, by_manufacturer_brand
    # PDF fallback: *_pdf
    photo = (
        blocks.get("photochromic")
        or blocks.get("photochromic_by_department_brand")
        or blocks.get("photochromic_by_department_pdf")
    )
    manuf = blocks.get("by_manufacturer") or blocks.get("by_manufacturer_brand") or blocks.get("by_manufacturer_pdf")
    dept = blocks.get("by_department_brand") or blocks.get("by_department_pdf")
    brand = blocks.get("by_brand") or blocks.get("by_brand_pdf")

    if not (photo or manuf or dept or brand):
        return

    lines.append("## Mix — Линзы (v1)")
    lines.append("")

    if photo:
        lines.append("**Фотохромы: по салонам (выручка)**")
        lines.append("")
        lines.append("| Салон | Выручка, руб | Доля | Кол-во | Ср. чек, руб |")
        lines.append("|---|---:|---:|---:|---:|")
        # photo rows may be by (dept,brand). Aggregate by dept.
        agg = {}
        for r in photo.rows:
            if not r or not r[0] or str(r[0]).lower().startswith("общее"):
                continue
            d = r[0]
            s = r[2] if len(r) > 2 else r[1]  # HTML uses [dept,brand,sum,...]
            cnt = r[4] if len(r) > 4 else r[3]
            try:
                sv = float(str(s).replace(" ", "").replace("\u00a0", "").replace(",", "."))
            except Exception:
                continue
            try:
                cv = float(str(cnt).replace(" ", "").replace("\u00a0", "").replace(",", "."))
            except Exception:
                cv = 0.0
            a = agg.setdefault(d, {"sum": 0.0, "cnt": 0.0})
            a["sum"] += sv
            a["cnt"] += cv
        for d, a in sorted(agg.items(), key=lambda kv: kv[1]["sum"], reverse=True)[:15]:
            avg = (a["sum"] / a["cnt"]) if a["cnt"] else 0.0
            lines.append(f"| {d} | {_fmt_money(a['sum'])} |  | {int(a['cnt']) if a['cnt'].is_integer() else a['cnt']} | {_fmt_money(avg)} |")
        lines.append("")

    if manuf:
        lines.append("**Производители: топ по выручке (ОЛ)**")
        lines.append("")
        lines.append("| Производитель | Выручка, руб | Доля | Кол-во | Ср. чек, руб |")
        lines.append("|---|---:|---:|---:|---:|")
        # manuf may be by (manufacturer,brand). Aggregate by manufacturer.
        agg = {}
        for r in manuf.rows:
            if not r or not r[0] or str(r[0]).lower().startswith("общее"):
                continue
            name = r[0]
            s = r[2] if len(r) > 2 else r[1]
            cnt = r[4] if len(r) > 4 else r[3]
            try:
                sv = float(str(s).replace(" ", "").replace("\u00a0", "").replace(",", "."))
            except Exception:
                continue
            try:
                cv = float(str(cnt).replace(" ", "").replace("\u00a0", "").replace(",", "."))
            except Exception:
                cv = 0.0
            a = agg.setdefault(name, {"sum": 0.0, "cnt": 0.0})
            a["sum"] += sv
            a["cnt"] += cv
        for name, a in sorted(agg.items(), key=lambda kv: kv[1]["sum"], reverse=True)[:15]:
            avg = (a["sum"] / a["cnt"]) if a["cnt"] else 0.0
            lines.append(f"| {name} | {_fmt_money(a['sum'])} |  | {int(a['cnt']) if a['cnt'].is_integer() else a['cnt']} | {_fmt_money(avg)} |")
        lines.append("")

    if brand:
        lines.append(f"- Блок брендов линз: {brand.title}")
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

    _maybe_add_frames_mix(lines, facts)
    _maybe_add_lenses_mix(lines, facts)

    lines.append("## Notes")
    lines.append("")
    lines.append(f"- Source: {facts.source_type} ({facts.source_id})")
    lines.append("- Это MVP v1: 3–5 KPI из листа `показатели 05.2026` + сигналы по отклонениям.")
    lenses_pack = (facts.mix_blocks or {}).get("lenses") if isinstance(facts.mix_blocks, dict) else None
    if isinstance(lenses_pack, dict) and isinstance(lenses_pack.get("source"), dict):
        src = lenses_pack["source"]
        lines.append(f"- Линзы: fallback source = {src.get('type')} ({src.get('id')} :: {src.get('entry')})")
    lines.append("- Линзы v1: если в XLS нет рассчитанных значений, используем HTML-экспорт из zip (без PDF-парсинга).")
    lines.append("")
    return "\n".join(lines)
