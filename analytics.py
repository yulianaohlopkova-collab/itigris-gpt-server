from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


Dataset = Dict[str, List[Dict[str, Any]]]

CSV_KEY_ALIASES: Dict[str, str] = {
    # Common identity fields
    "period_start": "period_start",
    "period end": "period_end",
    "period_end": "period_end",
    "start": "period_start",
    "end": "period_end",
    "дата начала": "period_start",
    "начало": "period_start",
    "дата конца": "period_end",
    "конец": "period_end",
    "salon": "salon",
    "store": "salon",
    "department": "salon",
    "департамент": "salon",
    "салон": "salon",
    "category": "category",
    "категория": "category",
    "товарная категория": "category",

    # Sales measures (the priority fields user requested)
    "revenue": "revenue",
    "выручка": "revenue",
    "сумма": "revenue",
    "сумма продаж": "revenue",
    "sales_revenue": "revenue",
    "amount": "revenue",
    "руб": "revenue",

    "qty_units": "qty_units",
    "units": "qty_units",
    "unit_qty": "qty_units",
    "qty": "qty_units",
    "quantity": "qty_units",
    "шт": "qty_units",
    "штук": "qty_units",
    "кол-во штук": "qty_units",
    "количество штук": "qty_units",

    "qty_packs": "qty_packs",
    "packs": "qty_packs",
    "pack_qty": "qty_packs",
    "упаковки": "qty_packs",
    "упак": "qty_packs",
    "кол-во упаковок": "qty_packs",
    "количество упаковок": "qty_packs",
}

CATEGORY_ALIASES: Dict[str, str] = {
    "contactlenses": "contactlenses",
    "contact lenses": "contactlenses",
    "контактные линзы": "contactlenses",
    "мкл": "contactlenses",
    "кл": "contactlenses",
    "glasses": "glasses",
    "оправы": "glasses",
    "frames": "glasses",
    "lenses": "lenses",
    "ол": "lenses",
    "очковые линзы": "lenses",
    "sunglasses": "sunglasses",
    "солнцезащитные очки": "sunglasses",
}


def parse_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text in {"-", "None", "nan"}:
        return None
    text = text.replace("%", "").replace("\u00a0", "").replace(" ", "").replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def fmt_money(value: Any) -> str:
    num = parse_number(value)
    if num is None:
        return "нет данных"
    return f"{num:,.0f} руб".replace(",", " ")


def fmt_qty(value: Any) -> str:
    num = parse_number(value)
    if num is None:
        return "нет данных"
    return f"{num:,.0f}".replace(",", " ")


def fmt_pct(value: Any) -> str:
    num = parse_number(value)
    if num is None:
        return "нет данных"
    if abs(num) < 0.05:
        num = 0.0
    return f"{num:.1f}%"


def read_csv_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_input_folder(input_dir: Path) -> Dataset:
    return {
        "sales_period": read_csv_rows(input_dir / "sales_period.csv"),
        "plan_fact": read_csv_rows(input_dir / "plan_fact.csv"),
        "employees": read_csv_rows(input_dir / "employees.csv"),
        "categories": read_csv_rows(input_dir / "categories.csv"),
        "training": read_csv_rows(input_dir / "training.csv"),
    }


def normalize_key(key: str) -> str:
    raw = str(key or "").strip()
    if not raw:
        return raw
    low = raw.lower()
    return CSV_KEY_ALIASES.get(low, CSV_KEY_ALIASES.get(raw, raw))


def normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in row.items():
        nk = normalize_key(k)
        if nk and nk not in out:
            out[nk] = v
        else:
            out[k] = v
    cat = out.get("category")
    if isinstance(cat, str) and cat.strip():
        out["category"] = CATEGORY_ALIASES.get(cat.strip().lower(), cat.strip())
    return out


def normalize_dataset(data: Dataset) -> Dataset:
    normalized: Dataset = {}
    for name, rows in data.items():
        normalized[name] = [normalize_row(row) for row in rows]
    return normalized


def first_period(data: Dataset) -> Tuple[str, str]:
    for rows in data.values():
        for row in rows:
            start = row.get("period_start")
            end = row.get("period_end")
            if start and end:
                return str(start), str(end)
    return "нет данных", "нет данных"


def is_network_row(row: Dict[str, Any]) -> bool:
    salon = str(row.get("salon", "")).lower()
    return "общ" in salon and "салон" in salon


def is_active_salon(row: Dict[str, Any]) -> bool:
    salon = str(row.get("salon", "")).strip()
    if not salon:
        return False
    low = salon.lower()
    if "общ" in low or "мобильный" in low:
        return False
    return True


def find_network(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    for row in rows:
        if is_network_row(row):
            return row
    return rows[0] if rows else {}


def num(row: Dict[str, Any], key: str) -> Optional[float]:
    return parse_number(row.get(key))


def sort_rows(rows: Iterable[Dict[str, Any]], key: str, reverse: bool = False) -> List[Dict[str, Any]]:
    return sorted(
        [r for r in rows if parse_number(r.get(key)) is not None],
        key=lambda r: parse_number(r.get(key)) or 0,
        reverse=reverse,
    )


def line_salon(row: Dict[str, Any], metric_key: str, fact_key: str, plan_key: Optional[str] = None) -> str:
    salon = row.get("salon", "нет данных")
    fact = fmt_money(row.get(fact_key)) if "revenue" in fact_key else (
        fmt_pct(row.get(fact_key)) if "conversion" in fact_key or "share" in fact_key else fmt_qty(row.get(fact_key))
    )
    plan_part = ""
    if plan_key:
        plan = fmt_money(row.get(plan_key)) if "revenue" in plan_key else (
            fmt_pct(row.get(plan_key)) if "conversion" in plan_key or "share" in plan_key else fmt_qty(row.get(plan_key))
        )
        plan_part = f" при плане {plan}"
    return f"{salon}: {fact}{plan_part}, отклонение {fmt_pct(row.get(metric_key))}"


def category_lookup(rows: List[Dict[str, Any]], category: str, salon: str = "Общее 7 салонов") -> Dict[str, Any]:
    salons = [salon]
    if salon in {"Общее 7 салонов", "Общий 7 салонов"}:
        salons = ["Общее 7 салонов", "Общий 7 салонов"]
    for row in rows:
        if row.get("category") == category and row.get("salon") in salons:
            return row
    return {}


def category_totals(rows: List[Dict[str, Any]], category_code: str) -> Dict[str, Any]:
    # Prefer network totals row if present; otherwise sum across salons.
    network = category_lookup(rows, category_code)
    if network:
        return network

    revenue = 0.0
    qty_units = 0.0
    qty_packs = 0.0
    found_any = False
    for row in rows:
        if row.get("category") != category_code:
            continue
        r = parse_number(row.get("revenue"))
        u = parse_number(row.get("qty_units"))
        p = parse_number(row.get("qty_packs"))
        if r is not None:
            revenue += r
            found_any = True
        if u is not None:
            qty_units += u
            found_any = True
        if p is not None:
            qty_packs += p
            found_any = True
    if not found_any:
        return {}
    return {"category": category_code, "salon": "network_sum", "revenue": revenue, "qty_units": qty_units, "qty_packs": qty_packs}


def top_employee_lines(rows: List[Dict[str, Any]]) -> Tuple[List[str], List[str], List[str]]:
    eligible = [r for r in rows if (num(r, "orders") or 0) >= 5]
    top_revenue = sort_rows(eligible, "revenue", reverse=True)[:5]
    low_check = sort_rows(eligible, "avg_check")[:5]
    unfinished = sort_rows(eligible, "unfinished_orders", reverse=True)[:5]

    top_lines = [
        f"{r.get('employee')} ({r.get('salon')}): {fmt_money(r.get('revenue'))}, заказов {fmt_qty(r.get('orders'))}, средний чек {fmt_money(r.get('avg_check'))}"
        for r in top_revenue
    ]
    low_lines = [
        f"{r.get('employee')} ({r.get('salon')}): средний чек {fmt_money(r.get('avg_check'))}, заказов {fmt_qty(r.get('orders'))}"
        for r in low_check
    ]
    unfinished_lines = [
        f"{r.get('employee')} ({r.get('salon')}): незавершенных заказов {fmt_qty(r.get('unfinished_orders'))}, выручка {fmt_money(r.get('revenue'))}"
        for r in unfinished
        if (num(r, "unfinished_orders") or 0) > 0
    ]
    return top_lines, low_lines, unfinished_lines


def bulletize(lines: List[str], fallback: str = "нет данных") -> str:
    real = [line for line in lines if line]
    if not real:
        return f"- {fallback}"
    return "\n".join(f"- {line}" for line in real)


def analyze_dataset(data: Dataset) -> Dict[str, Any]:
    normalized = normalize_dataset(data)
    report = build_report(normalized)
    return {
        "report_markdown": report,
        "data_sources": {
            name: len(rows) for name, rows in normalized.items()
        },
    }


def build_report(data: Dataset) -> str:
    sales = data.get("sales_period", [])
    categories = data.get("categories", [])
    employees = data.get("employees", [])
    training = data.get("training", [])

    period_start, period_end = first_period(data)
    network = find_network(sales)
    salons = [r for r in sales if is_active_salon(r)]

    revenue_risks = sort_rows(salons, "revenue_full_gap_pct")[:5]
    current_revenue_risks = sort_rows(salons, "revenue_variance_pct")[:4]
    conversion_order_risks = sort_rows(salons, "conversion_glasses_order_variance_pct")[:5]
    avg_customer_risks = sort_rows(salons, "avg_customer_variance_pct")[:4]
    revenue_growth = sort_rows(salons, "revenue_variance_pct", reverse=True)[:3]

    top_employee, low_check_employee, unfinished_employee = top_employee_lines(employees)

    better_best = category_lookup(categories, "better_best_lenses_qty")
    stm_frames = category_lookup(categories, "stm_frames_share")
    photochromic = category_lookup(categories, "photochromic_lenses_qty")
    myopia = category_lookup(categories, "myopia_control_lenses_qty")
    multifocal = category_lookup(categories, "multifocal_lenses_qty")
    lens_high = category_lookup(categories, "lenses_above_15000_qty")
    contact_sales = category_totals(categories, "contactlenses")

    limitations = [
        "ITigris remoteRemains дает остатки и товарную структуру, а не полную продажную аналитику.",
        "Текущая выгрузка закрывает период с 1 по 26 апреля 2026 года; факта за 27-30 апреля в таблице еще нет.",
        "Нет надежных данных по возвратам, переделкам, скидочной дисциплине и структуре одного чека.",
        "Нет связки сотрудников с тренерами и фактов обучающих вмешательств, поэтому эффект тренеров пока нельзя измерить.",
        "МКЛ в продажах видны как сумма по заказам, но детальная структура МКЛ по параметрам пока должна проверяться через ITigris остатки или отдельную выгрузку.",
    ]
    if training:
        limitations = [l for l in limitations if "тренерами" not in l] + [
            "Данные по обучению загружены, но MVP пока использует их как справочник без оценки причинно-следственного эффекта."
        ]

    short_picture = [
        (
            f"Сеть по текущему плану почти в нуле: факт {fmt_money(network.get('revenue_fact_current'))} "
            f"при плане {fmt_money(network.get('revenue_plan_current'))}, отклонение {fmt_pct(network.get('revenue_variance_pct'))}."
        ),
        (
            f"К полному плану месяца остается риск: факт {fmt_money(network.get('revenue_fact_full'))} "
            f"против плана {fmt_money(network.get('revenue_plan_full'))}, разрыв {fmt_pct(network.get('revenue_full_gap_pct'))}."
        ),
        (
            f"Трафик выше текущего плана ({fmt_pct(network.get('visitors_variance_pct'))}), но конверсия посетитель -> заказ на очки ниже плана "
            f"({fmt_pct(network.get('conversion_glasses_order_variance_pct'))}). Это главный управленческий разрыв: поток есть, очковые заказы недособираются."
        ),
        (
            f"Средний чек заказа на очки по сети выше плана ({fmt_pct(network.get('avg_glasses_check_variance_pct'))}), значит проблема сильнее похожа на конверсию и структуру, а не только на цену."
        ),
    ]

    signals = [
        (
            f"Разрыв к полному плану месяца {fmt_pct(network.get('revenue_full_gap_pct'))}: при факте "
            f"{fmt_money(network.get('revenue_fact_full'))} нужно добирать выручку в последние дни периода."
        ),
        (
            f"Посетителей больше плана на {fmt_pct(network.get('visitors_variance_pct'))}, но конверсия в заказ на очки ниже на "
            f"{fmt_pct(network.get('conversion_glasses_order_variance_pct'))}: есть потеря в переводе трафика в основной продукт."
        ),
        (
            f"Better/Best ОЛ: факт {fmt_qty(better_best.get('fact'))} при плане {fmt_qty(better_best.get('plan'))}. "
            "Это зона качества продажи, а не только количества заказов."
        ),
        (
            f"СТМ оправы сильные: доля {fmt_pct(stm_frames.get('fact'))} против плана {fmt_pct(stm_frames.get('plan'))}. "
            "Можно использовать практики сильных салонов как обучающий материал."
        ),
    ]

    salon_problem_lines = [
        line_salon(r, "revenue_full_gap_pct", "revenue_fact_full", "revenue_plan_full")
        for r in revenue_risks
    ]
    current_problem_lines = [
        line_salon(r, "revenue_variance_pct", "revenue_fact_current", "revenue_plan_current")
        for r in current_revenue_risks
    ]
    conversion_problem_lines = [
        f"{r.get('salon')}: заказ на очки {fmt_pct(r.get('conversion_glasses_order_fact_current'))} при плане {fmt_pct(r.get('conversion_glasses_order_plan_current'))}, отклонение {fmt_pct(r.get('conversion_glasses_order_variance_pct'))}"
        for r in conversion_order_risks
    ]
    avg_problem_lines = [
        f"{r.get('salon')}: средний доход от клиента {fmt_money(r.get('avg_customer_fact_current'))} при плане {fmt_money(r.get('avg_customer_plan_current'))}, отклонение {fmt_pct(r.get('avg_customer_variance_pct'))}"
        for r in avg_customer_risks
    ]

    growth_lines = [
        line_salon(r, "revenue_variance_pct", "revenue_fact_current", "revenue_plan_current")
        for r in revenue_growth
    ]
    growth_lines.extend([
        (
            f"Линзы выше 15 000 руб: {fmt_qty(lens_high.get('fact'))} шт и "
            f"{fmt_money(lens_high.get('revenue'))}; это высокая маржинальная зона для разбора лучших продаж."
        ),
        (
            f"Контроль миопии: {fmt_qty(myopia.get('fact'))} шт за апрель к 26 апреля; нужна отдельная проверка по салонам с нулевым фактом."
        ),
        (
            f"Мультифокальные линзы просели до {fmt_qty(multifocal.get('fact'))} шт, отклонение {fmt_pct(multifocal.get('variance_pct'))}; это отдельный тренерский фокус."
        ),
    ])

    hypotheses = [
        (
            "Факт: трафик по сети выше плана, а конверсия в заказ на очки ниже. "
            "Гипотеза: консультанты не всегда переводят визит/проверку в очковый заказ, особенно в салонах с низкой конверсией."
        ),
        (
            "Факт: средний чек очков выше плана, но Better/Best и мультифокальные линзы требуют внимания. "
            "Гипотеза: часть чеков растет за счет отдельных дорогих продаж, но целевая лестница ОЛ используется неровно."
        ),
        (
            "Факт: у ряда салонов выручка проседает при неплохом потоке. "
            "Гипотеза: проблема не в количестве входящих, а в навыке диагностики потребности, аргументации ОЛ и закрытия заказа."
        ),
        (
            f"Факт: фотохромные линзы {fmt_qty(photochromic.get('fact'))} шт, Better/Best {fmt_qty(better_best.get('fact'))} шт. "
            "Гипотеза: сильные практики по фотохрому можно перенести в Better/Best и мультифокальные продажи."
        ),
    ]

    commercial_focus = [
        "До закрытия апреля держать ежедневный контроль разрыва к полному плану по салонам с просадкой: Качели, Айсберг, СахаЭкспоЦентр, интернет-магазин.",
        "Разобрать воронку 'посетитель -> заказ на очки': где трафик есть, но заказ не оформляется, там приоритет управленческого внимания выше, чем просто докрутка трафика.",
        "Сравнить сильные салоны по СТМ/чеку с просевшими и быстро перенести рабочие сценарии: какие оправы предлагают, как объясняют ОЛ, где закрывают допродажи.",
        "Использовать ITigris только как слой остатков: проверить наличие МКЛ, оправ и ОЛ в салонах, где продавцы могут ссылаться на отсутствие товара.",
    ]

    trainer_focus = [
        "ТЦ Айсберг, ТЦ Качели, Улуруу Молл, Пояркова: тренировка перевода посетителя в заказ на очки и закрытия после проверки зрения.",
        "Better/Best ОЛ: отработать с консультантами лестницу ценности, аргументацию покрытия/класса линзы и сценарий 'почему не базовая линза'.",
        "Мультифокальные линзы: отдельный разбор консультации по пресбиопии, выявления потребности и уверенного предложения.",
        "Сотрудники с низким средним чеком: разобрать 5-7 последних заказов без клиентских персональных данных и найти, где теряется допродажа/категория.",
    ]

    next_steps = [
        "Подключить регулярную выгрузку DataLens/Google Sheets в тот же формат CSV.",
        "Добавить отдельный файл по МКЛ с параметрами manufacturer/name/dioptre/radius/diameter и связать продажи с остатками ITigris.",
        "Добавить скидки, возвраты, переделки и структуру одного чека для оценки качества продаж.",
        "Добавить справочник тренеров и факты обучающих вмешательств, чтобы v2 показывала эффект тренерской работы.",
    ]

    sections = [
        f"# ИИ-аналитик продаж — отчет за период {period_start} — {period_end}",
        "## 1. Краткая картина периода\n" + "\n".join(short_picture),
        "## 2. Ключевые сигналы\n" + bulletize(signals),
        (
            "## 3. Проблемные зоны\n"
            "### Салоны\n"
            + bulletize(salon_problem_lines)
            + "\n\n### Текущий темп месяца\n"
            + bulletize(current_problem_lines)
            + "\n\n### Конверсия и чек\n"
            + bulletize(conversion_problem_lines + avg_problem_lines)
            + "\n\n### Сотрудники\n"
            + bulletize(low_check_employee + unfinished_employee, "нет агрегированных данных по сотрудникам")
            + "\n\n### Категории\n"
            + bulletize([
                f"Better/Best ОЛ: факт {fmt_qty(better_best.get('fact'))} против плана {fmt_qty(better_best.get('plan'))}.",
                f"Мультифокальные ОЛ: факт {fmt_qty(multifocal.get('fact'))}, отклонение {fmt_pct(multifocal.get('variance_pct'))}.",
                (
                    f"МКЛ (продажи из CSV): выручка {fmt_money(contact_sales.get('revenue'))}, "
                    f"упаковок {fmt_qty(contact_sales.get('qty_packs'))}, штук {fmt_qty(contact_sales.get('qty_units'))}."
                    if contact_sales else
                    "МКЛ: нет явных колонок qty_packs/qty_units/revenue в sales CSV (или категория не промапилась на contactlenses)."
                ),
            ])
        ),
        "## 4. Точки роста\n" + bulletize(growth_lines + top_employee),
        "## 5. Гипотезы причин\n" + bulletize(hypotheses),
        "## 6. Фокус для Коммерческого директора\n" + bulletize(commercial_focus),
        "## 7. Фокус для Тренеров\n" + bulletize(trainer_focus),
        "## 8. Ограничения по данным\n" + bulletize(limitations),
        "## 9. Следующий шаг\n" + bulletize(next_steps),
    ]
    return "\n\n".join(sections) + "\n"
