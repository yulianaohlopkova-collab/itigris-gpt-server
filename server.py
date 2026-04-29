from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import xlsxwriter
from fastapi import FastAPI, Query, Request
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
