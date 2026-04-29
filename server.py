from __future__ import annotations

import csv
import io
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import openpyxl
import xlsxwriter
import xlrd
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from analytics import analyze_dataset, load_input_folder


app = FastAPI(
    title="ODL Sales Analyst MVP API",
    version="3.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


APP_NAME = os.getenv("ITIGRIS_APP_NAME", "odl").strip() or "odl"
REMOTE_API_KEY = (
    os.getenv("ITIGRIS_REMOTE_API_KEY")
    or os.getenv("ITIGRIS_API_KEY")
    or ""
).strip()
EXTERNAL_API_KEY = os.getenv("ITIGRIS_EXTERNAL_API_KEY", "").strip()
ODL_SERVER_TOKEN = os.getenv("ODL_SERVER_TOKEN", "").strip()
SERVER_URL = os.getenv("PUBLIC_SERVER_URL", "https://itigris-gpt-server.onrender.com").strip()
TIMEOUT = float(os.getenv("ITIGRIS_TIMEOUT", "40"))
REMOTE_REMAINS_URL = f"https://optima.itigris.ru/{APP_NAME}/remoteRemains/list"


DEPARTMENTS: Dict[str, int] = {
    "Ленина": 1000000021,
    "Склад. Мобильный салон": 1000000020,
    "Мобильный салон": 1000000019,
    "Интернет-магазин Якутск": 1000000018,
    "Склад. Интернет-магазин Якутск": 1000000017,
    "Айсберг": 1000000016,
    "Качели": 1000000012,
    "Улуру": 1000000011,
    "Лермонтова": 1000000009,
    "Пояркова": 1000000008,
    "Склад ИП": 1000000007,
    "Цех": 1000000006,
    "Склад ООО": 1000000005,
    "Экспо": 1000000004,
    "Офис": 1000000003,
}

DEPARTMENT_ALIASES: Dict[str, int] = {
    "качели": 1000000012,
    "в качелях": 1000000012,
    "качелях": 1000000012,
    "тц качели": 1000000012,
    "айсберг": 1000000016,
    "в айсберге": 1000000016,
    "айсберге": 1000000016,
    "тц айсберг": 1000000016,
    "ленина": 1000000021,
    "ленина 7": 1000000021,
    "ленина, 7": 1000000021,
    "на ленина": 1000000021,
    "пояркова": 1000000008,
    "пояркова 5": 1000000008,
    "пояркова, 5": 1000000008,
    "на пояркова": 1000000008,
    "лермонтова": 1000000009,
    "лермонтова 49": 1000000009,
    "лермонтова, 49": 1000000009,
    "на лермонтова": 1000000009,
    "улуру": 1000000011,
    "улуруу": 1000000011,
    "улуруу молл": 1000000011,
    "в улуру": 1000000011,
    "экспо": 1000000004,
    "сахаэкспоцентр": 1000000004,
    "саха экспо": 1000000004,
}

GROUPS_RU: Dict[str, List[int]] = {
    "салоны": [
        1000000021,
        1000000019,
        1000000018,
        1000000016,
        1000000012,
        1000000011,
        1000000004,
        1000000009,
        1000000008,
    ],
    "склады_ип": [1000000007],
    "склады_ооо": [1000000005],
    "цех": [1000000006],
}

GROUP_ALIASES: Dict[str, str] = {
    "salons": "салоны",
    "салоны": "салоны",
    "салон": "салоны",
    "магазины": "салоны",
    "warehouse_ip": "склады_ип",
    "склад ип": "склады_ип",
    "ип": "склады_ип",
    "warehouse_ooo": "склады_ооо",
    "склад ооо": "склады_ооо",
    "ооо": "склады_ооо",
    "workshop": "цех",
    "цех": "цех",
}

CATEGORY_FILTERS: Dict[str, List[str]] = {
    "accessories": ["manufacturer", "brand", "model", "color", "material", "type"],
    "contactlenses": [
        "manufacturer",
        "name",
        "color",
        "radius",
        "diameter",
        "dioptre",
        "cylinder",
        "axis",
        "add",
        "wearingPeriod",
        "inPack",
    ],
    "glasses": ["manufacturer", "brand", "model", "color", "purpose", "material", "type", "size", "design"],
    "lenses": [
        "manufacturer",
        "brand",
        "index",
        "cover",
        "color",
        "diameter",
        "material",
        "geometry",
        "lensType",
        "lensClass",
        "technology",
        "dioptre",
        "cylinder",
        "add",
    ],
    "sunglasses": ["manufacturer", "brand", "model", "color", "purpose", "material", "type", "lensType", "design"],
}

CATEGORY_ALIASES: Dict[str, str] = {
    "accessories": "accessories",
    "аксессуар": "accessories",
    "аксессуары": "accessories",
    "contactlenses": "contactlenses",
    "contact lenses": "contactlenses",
    "контактные линзы": "contactlenses",
    "контактные": "contactlenses",
    "контакты": "contactlenses",
    "кл": "contactlenses",
    "мкл": "contactlenses",
    "мягкие контактные линзы": "contactlenses",
    "glasses": "glasses",
    "frames": "glasses",
    "frame": "glasses",
    "оправы": "glasses",
    "оправа": "glasses",
    "lenses": "lenses",
    "очковые линзы": "lenses",
    "ол": "lenses",
    "линзы": "lenses",
    "стекла": "lenses",
    "стекло": "lenses",
    "sunglasses": "sunglasses",
    "солнцезащитные": "sunglasses",
    "солнцезащитные очки": "sunglasses",
    "солнечные очки": "sunglasses",
    "солнце": "sunglasses",
    "сз": "sunglasses",
}

FILTER_FIELD_ALIASES: Dict[str, str] = {
    "add": "add",
    "аддидация": "add",
    "axis": "axis",
    "ось": "axis",
    "brand": "brand",
    "бренд": "brand",
    "color": "color",
    "цвет": "color",
    "cover": "cover",
    "покрытие": "cover",
    "cylinder": "cylinder",
    "цилиндр": "cylinder",
    "design": "design",
    "дизайн": "design",
    "форма": "design",
    "diameter": "diameter",
    "диаметр": "diameter",
    "dioptre": "dioptre",
    "диоптрии": "dioptre",
    "диоптрия": "dioptre",
    "сфера": "dioptre",
    "geometry": "geometry",
    "геометрия": "geometry",
    "inpack": "inPack",
    "inPack": "inPack",
    "в упаковке": "inPack",
    "штук в упаковке": "inPack",
    "index": "index",
    "индекс": "index",
    "lensclass": "lensClass",
    "lensClass": "lensClass",
    "класс линзы": "lensClass",
    "lenstype": "lensType",
    "lensType": "lensType",
    "тип линзы": "lensType",
    "manufacturer": "manufacturer",
    "производитель": "manufacturer",
    "material": "material",
    "материал": "material",
    "model": "model",
    "модель": "model",
    "name": "name",
    "название": "name",
    "наименование": "name",
    "purpose": "purpose",
    "target": "purpose",
    "целевая группа": "purpose",
    "целевая_группа": "purpose",
    "пол": "purpose",
    "radius": "radius",
    "radiusofcurvature": "radius",
    "radiusOfCurvature": "radius",
    "радиус": "radius",
    "радиус кривизны": "radius",
    "size": "size",
    "размер": "size",
    "technology": "technology",
    "технология": "technology",
    "type": "type",
    "тип": "type",
    "wearingperiod": "wearingPeriod",
    "wearingPeriod": "wearingPeriod",
    "срок ношения": "wearingPeriod",
    "период ношения": "wearingPeriod",
}

BREAKDOWN_FIELDS: Dict[str, List[str]] = {
    "accessories": ["type", "brand", "manufacturer"],
    "contactlenses": ["manufacturer", "name", "dioptre", "radius", "diameter", "wearingPeriod", "inPack"],
    "glasses": ["brand", "manufacturer", "material", "type", "purpose", "design"],
    "lenses": ["manufacturer", "brand", "lensType", "lensClass", "cover", "index", "dioptre"],
    "sunglasses": ["brand", "manufacturer", "material", "type", "purpose", "design"],
}


class RemainsFilteredRequest(BaseModel):
    category: str
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    group: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    price: Optional[float] = None
    return_items: bool = False
    items_limit: int = Field(default=0, ge=0, le=1000)


class SalesAnalyzeRequest(BaseModel):
    data: Optional[Dict[str, List[Dict[str, Any]]]] = None


class SalesAnalyzeCsvRequest(BaseModel):
    sales_period_csv: str = Field(..., description="CSV content for sales_period.csv (UTF-8).")
    plan_fact_csv: Optional[str] = Field(default=None, description="CSV content for plan_fact.csv (optional).")
    employees_csv: Optional[str] = Field(default=None, description="CSV content for employees.csv (optional).")
    categories_csv: Optional[str] = Field(default=None, description="CSV content for categories.csv (optional).")
    training_csv: Optional[str] = Field(default=None, description="CSV content for training.csv (optional).")


def csv_bytes_to_rows(raw: bytes) -> List[Dict[str, Any]]:
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def csv_text_to_rows(text: str) -> List[Dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


async def load_csv_upload(file: Optional[UploadFile], required: bool) -> List[Dict[str, Any]]:
    if file is None:
        if required:
            raise HTTPException(status_code=400, detail="missing_required_csv")
        return []
    data = await file.read()
    if len(data) > 10_000_000:
        raise HTTPException(status_code=413, detail="csv_too_large")
    return csv_bytes_to_rows(data)


def require_auth_token(request: Request) -> Optional[JSONResponse]:
    if not ODL_SERVER_TOKEN:
        return JSONResponse(
            {"error": "server_token_not_configured", "detail": "Set ODL_SERVER_TOKEN in Render Environment."},
            status_code=500,
        )

    header_token = request.headers.get("x-odl-token") or request.headers.get("X-ODL-Token")
    query_token = request.query_params.get("token")
    if header_token == ODL_SERVER_TOKEN or query_token == ODL_SERVER_TOKEN:
        return None
    return JSONResponse({"error": "forbidden"}, status_code=403)


def normalize_category(category: str) -> str:
    return CATEGORY_ALIASES.get(category.strip().lower(), category.strip().lower())


def normalize_group(group: Optional[str]) -> Optional[str]:
    if not group:
        return None
    return GROUP_ALIASES.get(group.strip().lower(), group.strip().lower())


def normalize_department(department_id: Optional[int] = None, department_name: Optional[str] = None) -> Optional[int]:
    if department_id:
        return department_id
    if not department_name:
        return None

    raw = department_name.strip()
    if raw.isdigit():
        return int(raw)

    if raw in DEPARTMENTS:
        return DEPARTMENTS[raw]

    low = raw.lower()
    if low in DEPARTMENT_ALIASES:
        return DEPARTMENT_ALIASES[low]

    for name, dep_id in DEPARTMENTS.items():
        if name.lower() == low:
            return dep_id
    return None


def resolve_dep_ids(department_id: Optional[int], department_name: Optional[str], group: Optional[str]) -> List[int]:
    dep_id = normalize_department(department_id, department_name)
    if dep_id:
        return [dep_id]
    if department_name and not dep_id:
        raise ValueError("unknown_department")
    if group:
        normalized_group = normalize_group(group)
        if normalized_group not in GROUPS_RU:
            raise ValueError("unknown_group")
        return GROUPS_RU[normalized_group]
    return list(DEPARTMENTS.values())


def normalize_filter_field_name(field: str) -> str:
    key = field.strip()
    return FILTER_FIELD_ALIASES.get(key, FILTER_FIELD_ALIASES.get(key.lower(), key))


def normalize_filters(category: str, filters: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not filters:
        return None

    allowed = set(CATEGORY_FILTERS[category])
    normalized: Dict[str, Any] = {}
    ignored: Dict[str, Any] = {}
    for field, value in filters.items():
        norm_field = normalize_filter_field_name(field)
        if norm_field not in allowed:
            ignored[field] = value
            continue
        normalized[norm_field] = value
    if ignored:
        normalized["_ignoredFilters"] = ignored
    return normalized or None


def build_filter_payload(
    filters: Optional[Dict[str, Any]],
    min_price: Optional[float],
    max_price: Optional[float],
    price: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    payload: Dict[str, Any] = {}
    if filters:
        payload.update({k: v for k, v in filters.items() if not k.startswith("_")})
    if price is not None:
        payload["minPrice"] = float(price)
        payload["maxPrice"] = float(price)
    else:
        if min_price is not None:
            payload["minPrice"] = float(min_price)
        if max_price is not None:
            payload["maxPrice"] = float(max_price)
    return payload or None


def amount_as_int(row: Dict[str, Any]) -> int:
    try:
        return int(float(row.get("amount") or 0))
    except (TypeError, ValueError):
        return 0


def price_as_float(row: Dict[str, Any]) -> float:
    try:
        return float(row.get("price") or 0)
    except (TypeError, ValueError):
        return 0.0


def sum_qty_value(rows: List[Dict[str, Any]]) -> Tuple[int, float]:
    qty = sum(amount_as_int(row) for row in rows)
    value = sum(price_as_float(row) * amount_as_int(row) for row in rows)
    return qty, value


def parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text in {"-", "None", "nan"}:
        return None
    text = text.replace("\u00a0", "").replace(" ", "").replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def contact_lenses_totals(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    # For contact lenses we prefer explicit fields when present:
    # - qty_packs: "Количество, уп."
    # - qty_units: "Количество, шт."
    # - remaining_in_pack: "Осталось в уп."
    # - in_pack: "Кол-во в уп."
    # - value: "Сумма"
    # Otherwise we fall back to remoteRemains fields: amount/price and try to account for open packs
    # via remaining_in_pack + in_pack when present.
    total_packs = 0
    total_units = 0
    total_value = 0.0
    open_packs_count = 0

    for row in rows:
        qty_packs = parse_float(row.get("qty_packs") or row.get("Количество, уп.") or row.get("packs"))
        qty_units = parse_float(row.get("qty_units") or row.get("Количество, шт.") or row.get("units") or row.get("qty"))
        remaining_in_pack = parse_float(
            row.get("remaining_in_pack")
            or row.get("Осталось в уп.")
            or row.get("remainingInPack")
            or row.get("restInPack")
        )
        in_pack = parse_float(
            row.get("in_pack")
            or row.get("Кол-во в уп.")
            or row.get("inPack")
            or row.get("inpack")
        )
        value = parse_float(row.get("value") or row.get("Сумма") or row.get("sum") or row.get("total"))

        # 1) If report-style fields exist, use them as source of truth for this row.
        used_report_fields = False
        if qty_packs is not None or qty_units is not None or value is not None:
            used_report_fields = True
            total_packs += int(qty_packs or 0)
            total_units += int(qty_units or 0)
            total_value += float(value or 0)

        # 2) Otherwise fall back to remoteRemains.
        if not used_report_fields:
            packs = amount_as_int(row)
            price = price_as_float(row)
            total_packs += packs
            total_value += price * packs

            # If we have open-pack info, add 1 pack + remaining units for the open pack.
            if remaining_in_pack is not None and in_pack is not None:
                if remaining_in_pack > 0 and remaining_in_pack < in_pack:
                    open_packs_count += 1
                    total_packs += 1
                    total_units += int(remaining_in_pack)
                else:
                    # Best-effort: if only in_pack exists and no open pack, estimate units from full packs.
                    total_units += int(packs * in_pack)

    return {
        "total_qty_packs": total_packs,
        "total_qty_units": total_units,
        "total_value": round(total_value, 2),
        "open_packs_detected": open_packs_count,
    }


def normalize_header(text: str) -> str:
    return str(text or "").strip().lower()


REMAINGOODS_HEADERS = {
    "qty_packs": {"количество, уп.", "количество уп.", "кол-во, уп.", "кол-во уп.", "количество упаковок", "упаковки"},
    "qty_units": {"количество, шт.", "количество шт.", "кол-во, шт.", "кол-во шт.", "количество штук", "штуки", "шт"},
    "remaining_in_pack": {"осталось в уп.", "осталось в уп", "остаток в уп.", "осталось"},
    "in_pack": {"кол-во в уп.", "кол-во в уп", "количество в уп.", "количество в уп", "в упаковке", "кол-во в упаковке"},
    "value": {"сумма", "итого", "стоимость", "сумма, руб", "сумма руб", "сумма (руб)"},
}


def find_col_index(headers: List[str], variants: set[str]) -> Optional[int]:
    for idx, header in enumerate(headers):
        if normalize_header(header) in variants:
            return idx
    return None


def parse_remain_goods_csv(raw: bytes) -> List[Dict[str, Any]]:
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []
    headers = rows[0]
    idx_packs = find_col_index(headers, REMAINGOODS_HEADERS["qty_packs"])
    idx_units = find_col_index(headers, REMAINGOODS_HEADERS["qty_units"])
    idx_remaining = find_col_index(headers, REMAINGOODS_HEADERS["remaining_in_pack"])
    idx_in_pack = find_col_index(headers, REMAINGOODS_HEADERS["in_pack"])
    idx_value = find_col_index(headers, REMAINGOODS_HEADERS["value"])

    if idx_packs is None or idx_units is None or idx_value is None:
        raise HTTPException(status_code=400, detail="remainGoodsReport_missing_required_columns")

    out: List[Dict[str, Any]] = []
    for row in rows[1:]:
        def get_i(i: Optional[int]) -> Any:
            if i is None or i >= len(row):
                return None
            return row[i]

        out.append(
            {
                "qty_packs": parse_float(get_i(idx_packs)) or 0,
                "qty_units": parse_float(get_i(idx_units)) or 0,
                "remaining_in_pack": parse_float(get_i(idx_remaining)) if idx_remaining is not None else None,
                "in_pack": parse_float(get_i(idx_in_pack)) if idx_in_pack is not None else None,
                "value": parse_float(get_i(idx_value)) or 0,
            }
        )
    return out


def parse_remain_goods_xlsx(raw: bytes) -> List[Dict[str, Any]]:
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    headers_tuple = next(rows_iter, None)
    if not headers_tuple:
        return []
    headers = [str(h or "") for h in headers_tuple]
    idx_packs = find_col_index(headers, REMAINGOODS_HEADERS["qty_packs"])
    idx_units = find_col_index(headers, REMAINGOODS_HEADERS["qty_units"])
    idx_remaining = find_col_index(headers, REMAINGOODS_HEADERS["remaining_in_pack"])
    idx_in_pack = find_col_index(headers, REMAINGOODS_HEADERS["in_pack"])
    idx_value = find_col_index(headers, REMAINGOODS_HEADERS["value"])

    if idx_packs is None or idx_units is None or idx_value is None:
        raise HTTPException(status_code=400, detail="remainGoodsReport_missing_required_columns")

    out: List[Dict[str, Any]] = []
    for row in rows_iter:
        def get_i(i: Optional[int]) -> Any:
            if i is None or i >= len(row):
                return None
            return row[i]

        out.append(
            {
                "qty_packs": parse_float(get_i(idx_packs)) or 0,
                "qty_units": parse_float(get_i(idx_units)) or 0,
                "remaining_in_pack": parse_float(get_i(idx_remaining)) if idx_remaining is not None else None,
                "in_pack": parse_float(get_i(idx_in_pack)) if idx_in_pack is not None else None,
                "value": parse_float(get_i(idx_value)) or 0,
            }
        )
    return out


def parse_remain_goods_xls(raw: bytes) -> List[Dict[str, Any]]:
    book = xlrd.open_workbook(file_contents=raw)
    sheet = book.sheet_by_index(0)
    if sheet.nrows <= 0:
        return []
    headers = [str(sheet.cell_value(0, c) or "") for c in range(sheet.ncols)]
    idx_packs = find_col_index(headers, REMAINGOODS_HEADERS["qty_packs"])
    idx_units = find_col_index(headers, REMAINGOODS_HEADERS["qty_units"])
    idx_remaining = find_col_index(headers, REMAINGOODS_HEADERS["remaining_in_pack"])
    idx_in_pack = find_col_index(headers, REMAINGOODS_HEADERS["in_pack"])
    idx_value = find_col_index(headers, REMAINGOODS_HEADERS["value"])

    if idx_packs is None or idx_units is None or idx_value is None:
        raise HTTPException(status_code=400, detail="remainGoodsReport_missing_required_columns")

    def cell(r: int, c: Optional[int]) -> Any:
        if c is None or c < 0 or c >= sheet.ncols:
            return None
        if r < 0 or r >= sheet.nrows:
            return None
        return sheet.cell_value(r, c)

    out: List[Dict[str, Any]] = []
    for r in range(1, sheet.nrows):
        out.append(
            {
                "qty_packs": parse_float(cell(r, idx_packs)) or 0,
                "qty_units": parse_float(cell(r, idx_units)) or 0,
                "remaining_in_pack": parse_float(cell(r, idx_remaining)) if idx_remaining is not None else None,
                "in_pack": parse_float(cell(r, idx_in_pack)) if idx_in_pack is not None else None,
                "value": parse_float(cell(r, idx_value)) or 0,
            }
        )
    return out


def remain_goods_totals(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_packs = int(sum(parse_float(r.get("qty_packs")) or 0 for r in rows))
    total_units = int(sum(parse_float(r.get("qty_units")) or 0 for r in rows))
    total_value = float(sum(parse_float(r.get("value")) or 0 for r in rows))
    open_lines = 0
    open_packs = 0
    open_units = 0
    open_value = 0.0
    for r in rows:
        rem = parse_float(r.get("remaining_in_pack"))
        in_pack = parse_float(r.get("in_pack"))
        if rem is None or in_pack is None:
            continue
        if rem > 0 and rem < in_pack:
            open_lines += 1
            open_packs += int(parse_float(r.get("qty_packs")) or 0)
            open_units += int(parse_float(r.get("qty_units")) or 0)
            open_value += float(parse_float(r.get("value")) or 0)

    return {
        "total_qty_packs": total_packs,
        "total_qty_units": total_units,
        "total_value": round(total_value, 2),
        "open_lines": open_lines,
        "open_qty_packs": open_packs,
        "open_qty_units": open_units,
        "open_value": round(open_value, 2),
    }


def rows_to_excel_bytes(rows: List[Dict[str, Any]], sheet_name: str = "Remains") -> bytes:
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    worksheet = workbook.add_worksheet(sheet_name[:31] or "Remains")
    data = rows or [{"message": "Нет данных"}]
    headers = list(data[0].keys())
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)
    for row_index, row in enumerate(data, start=1):
        for col, header in enumerate(headers):
            worksheet.write(row_index, col, row.get(header))
    workbook.close()
    output.seek(0)
    return output.getvalue()


async def fetch_optima_remains_once(
    category: str,
    department_id: Optional[int],
    page: int,
    filter_payload: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not REMOTE_API_KEY:
        raise RuntimeError("ITIGRIS_REMOTE_API_KEY or ITIGRIS_API_KEY is not configured")

    body: Dict[str, Any] = {"product": category, "page": page}
    if department_id:
        body["departmentId"] = department_id
    if filter_payload:
        body["filter"] = filter_payload

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(REMOTE_REMAINS_URL, params={"key": REMOTE_API_KEY}, json=body)
        if response.status_code in {404, 405} and not filter_payload:
            params = {"key": REMOTE_API_KEY, "product": category, "page": page}
            if department_id:
                params["departmentId"] = department_id
            response = await client.get(REMOTE_REMAINS_URL, params=params)

    if response.status_code != 200:
        raise RuntimeError(f"ITigris remoteRemains error {response.status_code}: {response.text[:500]}")
    data = response.json()
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected ITigris response: {data}")
    return data


async def fetch_optima_remains(
    category: str,
    department_ids: List[int],
    filter_payload: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    all_rows: List[Dict[str, Any]] = []
    for dep_id in department_ids:
        for page in range(1, 501):
            rows = await fetch_optima_remains_once(category, dep_id, page, filter_payload)
            if not rows:
                break
            for row in rows:
                row.setdefault("departmentId", dep_id)
            all_rows.extend(rows)
        else:
            raise RuntimeError(f"Pagination limit reached for department {dep_id}")
    return all_rows


def summarize_rows(category: str, rows: List[Dict[str, Any]], limit: int = 0) -> Dict[str, Any]:
    if category == "contactlenses":
        totals = contact_lenses_totals(rows)
        total_qty = int(totals["total_qty_packs"])
        total_value = float(totals["total_value"])
        avg_price = total_value / total_qty if total_qty else 0.0
    else:
        total_qty, total_value = sum_qty_value(rows)
        avg_price = total_value / total_qty if total_qty else 0.0

    response: Dict[str, Any] = {
        "category": category,
        "source": "ITigris remoteRemains/list",
        "positions_count": len(rows),
        "summary": {
            "total_qty": total_qty,
            "total_value": round(total_value, 2),
            "avg_price": round(avg_price, 2),
        },
    }
    if category == "contactlenses":
        response["summary"].update(
            {
                "total_qty_packs": int(totals["total_qty_packs"]),
                "total_qty_units": int(totals["total_qty_units"]),
                "open_packs_detected": int(totals["open_packs_detected"]),
                "note": (
                    "contactlenses totals are reported as packs+units when possible. "
                    "remoteRemains may undercount open packs compared to report exports."
                ),
            }
        )
    if limit > 0:
        response["items"] = rows[:limit]
        response["items_truncated"] = len(rows) > limit
        response["items_total"] = len(rows)
    return response


def build_breakdown(category: str, rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    result: Dict[str, Dict[str, int]] = {}
    for field in BREAKDOWN_FIELDS.get(category, CATEGORY_FILTERS[category]):
        bucket: Dict[str, int] = {}
        for row in rows:
            value = row.get(field)
            if value in (None, ""):
                continue
            bucket[str(value)] = bucket.get(str(value), 0) + amount_as_int(row)
        result[field] = dict(sorted(bucket.items(), key=lambda item: item[1], reverse=True))
    return result


@app.get("/healthz")
def healthz() -> Dict[str, Any]:
    return {
        "ok": True,
        "version": app.version,
        "itigris_app": APP_NAME,
        "remote_api_key_configured": bool(REMOTE_API_KEY),
        "external_api_key_configured": bool(EXTERNAL_API_KEY),
        "server_token_configured": bool(ODL_SERVER_TOKEN),
    }


@app.get("/", include_in_schema=False)
def home(request: Request) -> Any:
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err
    return {"message": "ODL Sales Analyst MVP API is running", "version": app.version}


@app.get("/departments")
def departments(request: Request) -> Any:
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err
    return {
        "departments": [{"name": name, "id": dep_id} for name, dep_id in DEPARTMENTS.items()],
        "aliases": DEPARTMENT_ALIASES,
        "groups": GROUPS_RU,
    }


@app.get("/categories")
def categories(request: Request) -> Any:
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err
    return {
        "codes": list(CATEGORY_FILTERS.keys()),
        "aliases": CATEGORY_ALIASES,
        "filters": CATEGORY_FILTERS,
        "filter_aliases": FILTER_FIELD_ALIASES,
    }


@app.post("/remains-filtered")
async def remains_filtered(request: Request, body: RemainsFilteredRequest) -> Any:
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err

    category = normalize_category(body.category)
    if category not in CATEGORY_FILTERS:
        return JSONResponse({"error": "unknown_category", "category": body.category}, status_code=400)

    try:
        dep_ids = resolve_dep_ids(body.department_id, body.department_name, body.group)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    normalized_filters = normalize_filters(category, body.filters)
    filter_payload = build_filter_payload(normalized_filters, body.min_price, body.max_price, body.price)
    try:
        rows = await fetch_optima_remains(category, dep_ids, filter_payload)
    except Exception as exc:
        return JSONResponse({"error": "upstream_error", "detail": str(exc)}, status_code=502)

    limit = body.items_limit if body.return_items else 0
    response = summarize_rows(category, rows, limit=limit)
    response["scope"] = {
        "department_id": body.department_id,
        "department_name": body.department_name,
        "group": body.group,
        "departments_used": dep_ids,
    }
    response["filters_used"] = filter_payload or {}
    if normalized_filters and "_ignoredFilters" in normalized_filters:
        response["ignored_filters"] = normalized_filters["_ignoredFilters"]
    return response


@app.post("/count-by-filters")
async def count_by_filters(request: Request, body: RemainsFilteredRequest) -> Any:
    body.return_items = False
    body.items_limit = 0
    return await remains_filtered(request, body)


@app.get("/count-by-price/{category}")
async def count_by_price(
    request: Request,
    category: str,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    department_id: Optional[int] = None,
    department_name: Optional[str] = None,
    group: Optional[str] = None,
    limit_items: int = Query(50, ge=0, le=500),
) -> Any:
    body = RemainsFilteredRequest(
        category=category,
        department_id=department_id,
        department_name=department_name,
        group=group,
        min_price=min_price,
        max_price=max_price,
        return_items=limit_items > 0,
        items_limit=limit_items,
    )
    return await remains_filtered(request, body)


@app.get("/count/{category}")
async def count_category(
    request: Request,
    category: str,
    department_id: Optional[int] = None,
    department_name: Optional[str] = None,
    group: Optional[str] = None,
) -> Any:
    return await count_by_price(
        request=request,
        category=category,
        department_id=department_id,
        department_name=department_name,
        group=group,
        limit_items=0,
    )


@app.get("/breakdown/{category}")
async def breakdown_category(
    request: Request,
    category: str,
    department_id: Optional[int] = None,
    department_name: Optional[str] = None,
    group: Optional[str] = None,
) -> Any:
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err

    normalized_category = normalize_category(category)
    if normalized_category not in CATEGORY_FILTERS:
        return JSONResponse({"error": "unknown_category", "category": category}, status_code=400)
    try:
        dep_ids = resolve_dep_ids(department_id, department_name, group)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    try:
        rows = await fetch_optima_remains(normalized_category, dep_ids, filter_payload=None)
    except Exception as exc:
        return JSONResponse({"error": "upstream_error", "detail": str(exc)}, status_code=502)

    total_qty, total_value = sum_qty_value(rows)
    return {
        "category": normalized_category,
        "scope": {
            "department_id": department_id,
            "department_name": department_name,
            "group": group,
            "departments_used": dep_ids,
        },
        "source": "ITigris remoteRemains/list",
        "total_qty": total_qty,
        "total_value": round(total_value, 2),
        "breakdown": build_breakdown(normalized_category, rows),
    }


@app.get("/gpt/breakdown/{category}")
async def gpt_breakdown(
    request: Request,
    category: str,
    department_id: Optional[int] = None,
    department_name: Optional[str] = None,
    group: Optional[str] = None,
    top_n: int = Query(10, ge=1, le=30),
) -> Any:
    result = await breakdown_category(request, category, department_id, department_name, group)
    if isinstance(result, JSONResponse):
        return result
    compact = {}
    for field, values in result["breakdown"].items():
        compact[field] = dict(list(values.items())[:top_n])
    result["breakdown"] = compact
    result["note"] = "Это остатки ITigris remoteRemains, не продажи."
    return result


@app.get("/remains/{category}", include_in_schema=False)
async def remains_excel(
    request: Request,
    category: str,
    department_id: Optional[int] = None,
    department_name: Optional[str] = None,
    group: Optional[str] = None,
) -> Any:
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err
    normalized_category = normalize_category(category)
    if normalized_category not in CATEGORY_FILTERS:
        return JSONResponse({"error": "unknown_category", "category": category}, status_code=400)
    try:
        dep_ids = resolve_dep_ids(department_id, department_name, group)
        rows = await fetch_optima_remains(normalized_category, dep_ids, filter_payload=None)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"error": "upstream_error", "detail": str(exc)}, status_code=502)

    data = rows_to_excel_bytes(rows, sheet_name=normalized_category)
    filename = f"{normalized_category}_remains.xlsx"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@app.post("/sales/analyze")
async def sales_analyze(request: Request, body: SalesAnalyzeRequest) -> Any:
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err
    dataset = body.data if body.data is not None else load_input_folder(Path("data/input"))
    return analyze_dataset(dataset)


@app.post("/sales/analyze-upload")
async def sales_analyze_upload(
    request: Request,
    sales_period: UploadFile = File(...),
    plan_fact: Optional[UploadFile] = File(None),
    employees: Optional[UploadFile] = File(None),
    categories: Optional[UploadFile] = File(None),
    training: Optional[UploadFile] = File(None),
) -> Any:
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err

    dataset = {
        "sales_period": await load_csv_upload(sales_period, required=True),
        "plan_fact": await load_csv_upload(plan_fact, required=False),
        "employees": await load_csv_upload(employees, required=False),
        "categories": await load_csv_upload(categories, required=False),
        "training": await load_csv_upload(training, required=False),
    }
    return analyze_dataset(dataset)


@app.post("/sales/analyze-csv")
async def sales_analyze_csv(request: Request, body: SalesAnalyzeCsvRequest) -> Any:
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err

    dataset = {
        "sales_period": csv_text_to_rows(body.sales_period_csv),
        "plan_fact": csv_text_to_rows(body.plan_fact_csv) if body.plan_fact_csv else [],
        "employees": csv_text_to_rows(body.employees_csv) if body.employees_csv else [],
        "categories": csv_text_to_rows(body.categories_csv) if body.categories_csv else [],
        "training": csv_text_to_rows(body.training_csv) if body.training_csv else [],
    }
    return analyze_dataset(dataset)


@app.post("/contactlenses/remainGoodsReport/analyze")
async def contactlenses_remain_goods_report_analyze(
    request: Request,
    report_file: UploadFile = File(...),
) -> Any:
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err

    raw = await report_file.read()
    if len(raw) > 30_000_000:
        raise HTTPException(status_code=413, detail="report_file_too_large")

    filename = (report_file.filename or "").lower()
    content_type = (report_file.content_type or "").lower()
    if filename.endswith(".csv") or "csv" in content_type or content_type == "text/plain":
        rows = parse_remain_goods_csv(raw)
    elif filename.endswith(".xlsx") or "spreadsheetml" in content_type:
        rows = parse_remain_goods_xlsx(raw)
    elif filename.endswith(".xls") or content_type in {"application/vnd.ms-excel"}:
        rows = parse_remain_goods_xls(raw)
    else:
        raise HTTPException(status_code=400, detail="unsupported_report_file_type")

    totals = remain_goods_totals(rows)
    return {
        "category": "contactlenses",
        "source": "remainGoodsReport upload (truth source for contact lenses packs/units/value)",
        "rows_count": len(rows),
        "summary": totals,
        "note": (
            "Use this endpoint for exact contact lenses stock in packs/units/value including open packs. "
            "ITigris remoteRemains is an API snapshot and may undercount open packs."
        ),
    }


@app.get("/openapi.json", include_in_schema=False)
def openapi_json(request: Request) -> Any:
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err

    schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
        description=(
            "MVP API: ITigris remoteRemains for stock/assortment plus sales analytical report "
            "from DataLens/Google Sheets CSV input. remoteRemains is not sales."
        ),
    )
    schema["servers"] = [{"url": SERVER_URL}]
    schema.setdefault("components", {}).setdefault("securitySchemes", {})
    schema["components"]["securitySchemes"]["OdlServerToken"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-ODL-Token",
        "description": "Server token from Render Environment.",
    }
    schema["security"] = [{"OdlServerToken": []}]
    return JSONResponse(schema)


@app.get("/docs", include_in_schema=False)
def swagger_docs(request: Request) -> Any:
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err
    token = request.query_params.get("token")
    openapi_url = f"/openapi.json?token={token}" if token else "/openapi.json"
    return get_swagger_ui_html(openapi_url=openapi_url, title=f"{app.title} - Swagger")
