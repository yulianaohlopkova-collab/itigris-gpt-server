from __future__ import annotations

import csv
import argparse
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from xml.etree import ElementTree as ET


TABLE_NS = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
OFFICE_NS = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
TEXT_NS = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"

SALON_NAMES = {
    "Ленина, 7",
    "Лермонтова, 49",
    "СахаЭкспоЦентр",
    "Улуруу Молл",
    "ТЦ Айсберг",
    "ТЦ Качели",
    "Советский проспект",
    "Пояркова, 5",
    "Интернет-магазин Якутск",
    "Мобильный салон",
    "Общий 7 салонов",
    "Общее 7 салонов",
}


def cell_text(cell: ET.Element) -> str:
    value = (
        cell.attrib.get(OFFICE_NS + "value")
        or cell.attrib.get(OFFICE_NS + "date-value")
        or cell.attrib.get(OFFICE_NS + "string-value")
    )
    texts = []
    for paragraph in cell.iter(TEXT_NS + "p"):
        text = "".join(paragraph.itertext()).strip()
        if text:
            texts.append(text)
    return " ".join(texts) if texts else (value or "")


def parse_row(row: ET.Element, max_cols: int = 80) -> List[str]:
    values: List[str] = []
    for cell in list(row):
        if not (cell.tag.endswith("}table-cell") or cell.tag.endswith("}covered-table-cell")):
            continue
        repeated = int(cell.attrib.get(TABLE_NS + "number-columns-repeated", "1"))
        value = cell_text(cell)
        if repeated > max_cols and not value:
            if len(values) < max_cols:
                values.extend([""] * (max_cols - len(values)))
        else:
            values.extend([value] * min(repeated, max(0, max_cols - len(values))))
        if len(values) >= max_cols:
            break
    while values and values[-1] == "":
        values.pop()
    return values


def load_table(path: Path, table_name: str, max_cols: int = 80) -> List[List[str]]:
    rows: List[List[str]] = []
    current_table: Optional[str] = None
    with zipfile.ZipFile(path) as archive:
        with archive.open("content.xml") as content:
            for event, element in ET.iterparse(content, events=("start", "end")):
                if event == "start" and element.tag == TABLE_NS + "table":
                    current_table = element.attrib.get(TABLE_NS + "name")
                elif event == "end" and element.tag == TABLE_NS + "table":
                    current_table = None
                    element.clear()
                elif event == "end" and element.tag == TABLE_NS + "table-row" and current_table == table_name:
                    row = parse_row(element, max_cols=max_cols)
                    if any(value.strip() for value in row):
                        rows.append(row)
                    element.clear()
    return rows


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def get(row: List[str], index: int) -> str:
    return clean(row[index]) if index < len(row) else ""


def parse_amount(value: str) -> float:
    text = clean(value)
    if not text or text == "-":
        return 0.0
    text = text.replace("\u00a0", "").replace(" ", "").replace(",", "")
    try:
        return float(text)
    except ValueError:
        return 0.0


def parse_date(value: str) -> Optional[datetime]:
    try:
        return datetime.strptime(clean(value), "%d.%m.%Y")
    except ValueError:
        return None


def find_row(rows: List[List[str]], startswith: str) -> int:
    for idx, row in enumerate(rows):
        if row and row[0].startswith(startswith):
            return idx
    raise ValueError(f"Cannot find block: {startswith}")


def find_row_contains(rows: List[List[str]], text: str) -> int:
    for idx, row in enumerate(rows):
        if row and text in row[0]:
            return idx
    raise ValueError(f"Cannot find block containing: {text}")


def salon_rows_after(rows: List[List[str]], header_index: int) -> Iterable[List[str]]:
    for row in rows[header_index + 1 :]:
        if not row:
            continue
        if row[0] in SALON_NAMES:
            yield row
            continue
        if row[0].startswith("САЛОН /") or row[0].isupper():
            break


def upsert_salon(target: Dict[str, Dict[str, str]], salon: str, period_start: str, period_end: str) -> Dict[str, str]:
    if salon not in target:
        target[salon] = {"period_start": period_start, "period_end": period_end, "salon": salon}
    return target[salon]


def extract_sales_period(rows: List[List[str]], period_start: str, period_end: str) -> List[Dict[str, str]]:
    result: Dict[str, Dict[str, str]] = {}

    blocks = [
        ("ВЫРУЧКА, РУБ", "revenue", True),
        ("СРЕДНИЙ ДОХОД ОТ КЛИЕНТА, РУБ", "avg_customer", False),
        ("СРЕДНИЙ ЧЕК НА ОЧКИ, РУБ", "avg_glasses_check", False),
        ("ПОСЕТИТЕЛИ, ЧЕЛ", "visitors", True),
        ("КОНВЕРСИЯ ПРОДАЖА/ПОСЕТИТЕЛЬ, %", "conversion_sale", False),
        ("КОНВЕРСИЯ ЗАКАЗ/ПРОВЕРИВШИЙСЯ, %", "exam_to_order", False),
        ("КОНВЕРСИЯ ПОСЕТИТЕЛИ / ЗАКАЗ НА ОЧКИ, %", "conversion_glasses_order", False),
    ]

    for title, prefix, has_full_month in blocks:
        title_index = find_row(rows, title)
        header_index = title_index + 1
        for row in salon_rows_after(rows, header_index):
            salon = row[0]
            item = upsert_salon(result, salon, period_start, period_end)
            item[f"{prefix}_plan_current"] = get(row, 1)
            item[f"{prefix}_fact_current"] = get(row, 2)
            item[f"{prefix}_variance_pct"] = get(row, 3)
            if has_full_month:
                item[f"{prefix}_plan_full"] = get(row, 19)
                item[f"{prefix}_fact_full"] = get(row, 20)
                item[f"{prefix}_full_gap_pct"] = get(row, 21)

    qty_index = find_row(rows, "ПРОДАЖИ, ШТ")
    for row in salon_rows_after(rows, qty_index + 1):
        salon = row[0]
        item = upsert_salon(result, salon, period_start, period_end)
        item["glasses_orders_qty_yoy_base"] = get(row, 1)
        item["glasses_orders_qty"] = get(row, 2)
        item["glasses_orders_yoy_pct"] = get(row, 3)
        item["frames_qty_yoy_base"] = get(row, 4)
        item["frames_qty"] = get(row, 5)
        item["frames_yoy_pct"] = get(row, 6)
        item["lenses_qty_yoy_base"] = get(row, 7)
        item["lenses_qty"] = get(row, 8)
        item["lenses_yoy_pct"] = get(row, 9)

    return list(result.values())


def category_rows(
    rows: List[List[str]],
    title: str,
    category: str,
    period_start: str,
    period_end: str,
    unit: str,
    fact_col: int = 2,
    plan_col: int = 1,
    variance_col: int = 3,
    title_index: Optional[int] = None,
) -> List[Dict[str, str]]:
    if title_index is None:
        title_index = find_row(rows, title)
    output = []
    for row in salon_rows_after(rows, title_index + 1):
        output.append(
            {
                "period_start": period_start,
                "period_end": period_end,
                "salon": row[0],
                "category": category,
                "plan": get(row, plan_col),
                "fact": get(row, fact_col),
                "variance_pct": get(row, variance_col),
                "unit": unit,
                "revenue": "",
            }
        )
    return output


def extract_categories(rows: List[List[str]], period_start: str, period_end: str) -> List[Dict[str, str]]:
    output: List[Dict[str, str]] = []
    output.extend(category_rows(rows, "ФОТОХРОМНЫЕ ЛИНЗЫ", "photochromic_lenses_qty", period_start, period_end, "шт"))
    output.extend(category_rows(rows, "СОЛНЦЕЗАЩИТНЫЕ ОЧКИ", "sunglasses_qty", period_start, period_end, "шт"))
    output.extend(category_rows(rows, "", "better_best_lenses_qty", period_start, period_end, "шт", title_index=find_row_contains(rows, "ФОКУС. ЛИНЗЫ BETTER / BEST")))
    output.extend(category_rows(rows, "", "stm_frames_share", period_start, period_end, "%", title_index=find_row_contains(rows, "ПРОДАЖИ ОПРАВ СТМ")))
    output.extend(category_rows(rows, "", "myopia_control_lenses_qty", period_start, period_end, "шт", fact_col=6, plan_col=5, variance_col=7, title_index=find_row_contains(rows, "ФОКУС. ЛИНЗЫ КОНТРОЛЬ МИОПИИ")))
    output.extend(category_rows(rows, "", "multifocal_lenses_qty", period_start, period_end, "шт", fact_col=6, plan_col=5, variance_col=7, title_index=find_row_contains(rows, "ФОКУС. ЛИНЗЫ МУЛЬТИФОКУСНЫЕ")))

    lens_range_index = find_row(rows, "ПРОДАННЫЕ ЛИНЗЫ ПО ДИАПАЗОНАМ")
    for row in salon_rows_after(rows, lens_range_index + 1):
        output.append(
            {
                "period_start": period_start,
                "period_end": period_end,
                "salon": row[0],
                "category": "lenses_above_15000_qty",
                "plan": "",
                "fact": get(row, 11),
                "variance_pct": "",
                "unit": "шт",
                "revenue": get(row, 12),
            }
        )
    return output


def extract_employees(order_rows: List[List[str]], period_start: str, period_end: str) -> List[Dict[str, str]]:
    header = order_rows[0]
    idx = {name: header.index(name) for name in header}
    start = datetime.strptime(period_start, "%Y-%m-%d")
    end = datetime.strptime(period_end, "%Y-%m-%d")
    by_employee: Dict[tuple, Dict[str, Any]] = defaultdict(
        lambda: {
            "revenue": 0.0,
            "orders": 0,
            "glasses_orders": 0,
            "frames_revenue": 0.0,
            "lenses_revenue": 0.0,
            "contact_lenses_revenue": 0.0,
            "accessories_revenue": 0.0,
            "unfinished_orders": 0,
            "large_checks": 0,
        }
    )

    for row in order_rows[1:]:
        created = parse_date(get(row, idx["Дата создания"]))
        if not created or created < start or created > end:
            continue
        salon = get(row, idx["Департамент"])
        employee = get(row, idx["Консультант"])
        if not salon or not employee:
            continue
        revenue = parse_amount(get(row, idx["Сумма заказа"]))
        if revenue <= 0:
            continue
        key = (salon, employee)
        item = by_employee[key]
        item["revenue"] += revenue
        item["orders"] += 1
        item["frames_revenue"] += parse_amount(get(row, idx["Оправы со скидкой"]))
        item["lenses_revenue"] += parse_amount(get(row, idx["Линзы OD со скидкой"])) + parse_amount(get(row, idx["Линзы OS со скидкой"]))
        item["contact_lenses_revenue"] += parse_amount(get(row, idx["КЛ со скидкой"]))
        item["accessories_revenue"] += parse_amount(get(row, idx["Аксессуары со скидкой"]))
        if get(row, idx["Тип заказа"]) == "Изготовление очков":
            item["glasses_orders"] += 1
        if get(row, idx["Статус заказа"]) != "Завершен":
            item["unfinished_orders"] += 1
        if revenue >= 15000:
            item["large_checks"] += 1

    output = []
    for (salon, employee), item in sorted(by_employee.items(), key=lambda x: x[1]["revenue"], reverse=True):
        orders = item["orders"] or 1
        output.append(
            {
                "period_start": period_start,
                "period_end": period_end,
                "salon": salon,
                "employee": employee,
                "revenue": round(item["revenue"], 2),
                "orders": item["orders"],
                "avg_check": round(item["revenue"] / orders, 2),
                "glasses_orders": item["glasses_orders"],
                "frames_revenue": round(item["frames_revenue"], 2),
                "lenses_revenue": round(item["lenses_revenue"], 2),
                "contact_lenses_revenue": round(item["contact_lenses_revenue"], 2),
                "accessories_revenue": round(item["accessories_revenue"], 2),
                "unfinished_orders": item["unfinished_orders"],
                "large_checks_share": round(item["large_checks"] / orders * 100, 2),
            }
        )
    return output


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_dictionary(path: Path) -> None:
    path.write_text(
        """# data/input — словарь данных MVP

Источник текущего примера: `source_docs/ODL_dashboard.ods`, листы `показатели 04.2026` и `заказы созданные 2026`.

Период примера: 2026-04-01 — 2026-04-26. Это не полный апрель: в исходном дашборде факт за 27-30 апреля еще не заполнен.

## sales_period.csv
Агрегаты по салонам: выручка, план-факт, посетители, средний доход от клиента, средний чек заказа на очки, конверсии, продажи очков/оправ/ОЛ.

## plan_fact.csv
Упрощенный слой план-факт по выручке для быстрых проверок и GPT Actions.

## categories.csv
Категорийные фокусы: ОЛ по диапазонам, СТМ оправы, фотохром, солнцезащитные очки, Better/Best, контроль миопии, мультифокальные линзы.

## employees.csv
Агрегаты по сотрудникам без клиентских персональных данных: выручка, заказы, средний чек, очковые заказы, категорийная выручка, незавершенные заказы, доля крупных чеков.

## training.csv
Опциональный файл. Сейчас только структура, потому что в переданных данных нет фактов тренерских вмешательств.
""",
        encoding="utf-8",
    )


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Extract ODS dashboards into MVP CSV inputs.")
    parser.add_argument(
        "--ods",
        dest="ods_path",
        default=str(project_root / "source_docs" / "ODL_dashboard.ods"),
        help="Path to ODS file (default: source_docs/ODL_dashboard.ods).",
    )
    parser.add_argument(
        "--out",
        dest="output_dir",
        default=str(project_root / "data" / "input"),
        help="Output directory for CSV files (default: data/input).",
    )
    parser.add_argument("--period-start", default="2026-04-01", help="Period start in YYYY-MM-DD.")
    parser.add_argument("--period-end", default="2026-04-26", help="Period end in YYYY-MM-DD.")
    parser.add_argument(
        "--metrics-sheet",
        default="показатели 04.2026",
        help="ODS sheet name containing KPI blocks.",
    )
    parser.add_argument(
        "--orders-sheet",
        default="заказы созданные 2026",
        help="ODS sheet name containing order rows.",
    )
    args = parser.parse_args()

    ods_path = Path(args.ods_path)
    output_dir = Path(args.output_dir)
    period_start = args.period_start
    period_end = args.period_end

    metric_rows = load_table(ods_path, args.metrics_sheet)
    order_rows = load_table(ods_path, args.orders_sheet, max_cols=40)

    sales_rows = extract_sales_period(metric_rows, period_start, period_end)
    category_data = extract_categories(metric_rows, period_start, period_end)
    employee_data = extract_employees(order_rows, period_start, period_end)
    plan_fact = [
        {
            "period_start": row["period_start"],
            "period_end": row["period_end"],
            "salon": row["salon"],
            "revenue_plan_current": row.get("revenue_plan_current", ""),
            "revenue_fact_current": row.get("revenue_fact_current", ""),
            "revenue_variance_pct": row.get("revenue_variance_pct", ""),
            "revenue_plan_full": row.get("revenue_plan_full", ""),
            "revenue_fact_full": row.get("revenue_fact_full", ""),
            "revenue_full_gap_pct": row.get("revenue_full_gap_pct", ""),
        }
        for row in sales_rows
    ]

    write_csv(output_dir / "sales_period.csv", sales_rows, sorted({k for row in sales_rows for k in row.keys()}))
    write_csv(output_dir / "plan_fact.csv", plan_fact, list(plan_fact[0].keys()))
    write_csv(output_dir / "categories.csv", category_data, ["period_start", "period_end", "salon", "category", "plan", "fact", "variance_pct", "unit", "revenue"])
    write_csv(
        output_dir / "employees.csv",
        employee_data,
        [
            "period_start",
            "period_end",
            "salon",
            "employee",
            "revenue",
            "orders",
            "avg_check",
            "glasses_orders",
            "frames_revenue",
            "lenses_revenue",
            "contact_lenses_revenue",
            "accessories_revenue",
            "unfinished_orders",
            "large_checks_share",
        ],
    )
    write_csv(
        output_dir / "training.csv",
        [],
        ["period_start", "period_end", "trainer", "salon", "employee", "intervention_type", "intervention_date", "comment"],
    )
    write_dictionary(output_dir / "data_dictionary.md")

    print(f"sales_period rows: {len(sales_rows)}")
    print(f"categories rows: {len(category_data)}")
    print(f"employees rows: {len(employee_data)}")
    print(f"output: {output_dir}")


if __name__ == "__main__":
    main()
