import os
import io
from typing import Optional, Dict, List, Any, Tuple

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel

# =======================
# APP (docs/openapi отключены, мы добавим их вручную с токеном)
# =======================
app = FastAPI(
    title="Optima Assistant API",
    version="2.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# =======================
# НАСТРОЙКИ И СЕКРЕТЫ (только через Render Environment)
# =======================
APP_NAME = os.getenv("ITIGRIS_APP_NAME", "odl")
API_KEY = os.getenv("ITIGRIS_API_KEY")  # ключ API (remoteRemains)
ODL_SERVER_TOKEN = os.getenv("ODL_SERVER_TOKEN")  # защитный токен сервера

TIMEOUT = 40.0
BASE_URL = f"https://optima.itigris.ru/{APP_NAME}/remoteRemains/list"

# =======================
# ДЕПАРТАМЕНТЫ + АЛИАСЫ + ГРУППЫ
# =======================
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
    "качели": 1000000012, "в качелях": 1000000012, "качелях": 1000000012,
    "айсберг": 1000000016, "в айсберге": 1000000016, "айсберге": 1000000016,
    "ленина": 1000000021, "на ленина": 1000000021,
    "пояркова": 1000000008, "на пояркова": 1000000008,
    "лермонтова": 1000000009, "на лермонтова": 1000000009,
    "улуру": 1000000011, "в улуру": 1000000011,
}

GROUPS_RU: Dict[str, List[int]] = {
    "салоны": [
        1000000021, 1000000019, 1000000018, 1000000016,
        1000000012, 1000000011, 1000000004, 1000000009, 1000000008
    ],
    "склады_ип": [1000000007],
    "склады_ооо": [1000000005],
    "цех": [1000000006],
}

GROUP_ALIASES: Dict[str, str] = {
    "salons": "салоны", "салоны": "салоны", "салон": "салоны",
    "warehouse_ip": "склады_ип", "склад ип": "склады_ип", "ип": "склады_ип",
    "warehouse_ooo": "склады_ооо", "склад ооо": "склады_ооо", "ооо": "склады_ооо",
    "workshop": "цех", "цех": "цех"
}

# =======================
# КАТЕГОРИИ
# =======================
CATEGORY_FILTERS = {
    "lenses": ["manufacturer","brand","index","cover","color","diameter","material","geometry","lensType","lensClass","technology","dioptre","cylinder","add"],
    "contactlenses": ["manufacturer","name","color","radius","diameter","dioptre","cylinder","axis","add","wearingPeriod","inPack"],
    "glasses": ["manufacturer","brand","model","color","purpose","material","type","size"],
    "sunglasses": ["manufacturer","brand","model","color","purpose","material","type","lensType","design"],
    "accessories": ["manufacturer","brand","model","color","material","type"],
}

CATEGORY_ALIASES = {
    "оправы": "glasses", "оправа": "glasses", "frames": "glasses", "frame": "glasses",
    "солнцезащитные": "sunglasses", "солнцезащитные очки": "sunglasses",
    "линзы": "lenses",
    "контактные линзы": "contactlenses",
    "аксессуары": "accessories",
}

# =======================
# AUTH (token в URL ?token=...)
# =======================
def require_auth_token(request: Request) -> Optional[JSONResponse]:
    if not ODL_SERVER_TOKEN:
        return JSONResponse(
            {"error": "Server token is not configured (ODL_SERVER_TOKEN)"},
            status_code=500
        )

    # 1) Сначала пробуем токен из заголовка
    header_token = request.headers.get("x-odl-token")
    if header_token == ODL_SERVER_TOKEN:
        return None

    # 2) Потом пробуем старый вариант из URL
    query_token = request.query_params.get("token")
    if query_token == ODL_SERVER_TOKEN:
        return None

    return JSONResponse({"error": "Forbidden"}, status_code=403)

# =======================
# ХЕЛПЕРЫ
# =======================
def normalize_category(cat: str) -> str:
    return CATEGORY_ALIASES.get(cat.strip().lower(), cat.strip().lower())

def normalize_group(group: Optional[str]) -> Optional[str]:
    if not group:
        return None
    return GROUP_ALIASES.get(group.strip().lower(), group.strip().lower())

def try_int(s: str) -> Optional[int]:
    try:
        return int(s)
    except Exception:
        return None

def normalize_department(department_id: Optional[int] = None, department_name: Optional[str] = None) -> Optional[int]:
    if department_id:
        return department_id
    if not department_name:
        return None

    name = department_name.strip()
    maybe = try_int(name)
    if maybe:
        return maybe

    if name in DEPARTMENTS:
        return DEPARTMENTS[name]

    low = name.lower()
    if low in DEPARTMENT_ALIASES:
        return DEPARTMENT_ALIASES[low]

    if low.startswith("в "):
        low2 = low[2:].strip()
        if low2 in DEPARTMENT_ALIASES:
            return DEPARTMENT_ALIASES[low2]
        for k, v in DEPARTMENTS.items():
            if k.lower() == low2:
                return v

    for k, v in DEPARTMENTS.items():
        if k.lower() == low:
            return v

    return None

def resolve_dep_ids(department_id: Optional[int], department_name: Optional[str], group: Optional[str]) -> List[int]:
    dep_id = normalize_department(department_id, department_name)
    if dep_id:
        return [dep_id]
    if group:
        grp = normalize_group(group)
        if grp not in GROUPS_RU:
            raise ValueError("unknown_group")
        return GROUPS_RU[grp]
    return list(DEPARTMENTS.values())

def rows_to_excel_bytes(rows: List[Dict[str, Any]], sheet_name: str = "Remains") -> bytes:
    import xlsxwriter
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    ws = wb.add_worksheet((sheet_name[:31] if sheet_name else "Remains"))

    if not rows:
        rows = [{"message": "Нет данных"}]

    headers = list(rows[0].keys())
    for c, h in enumerate(headers):
        ws.write(0, c, h)

    for r_i, row in enumerate(rows, start=1):
        for c, h in enumerate(headers):
            ws.write(r_i, c, row.get(h))

    wb.close()
    buf.seek(0)
    return buf.getvalue()

def sum_qty_value(rows: List[Dict[str, Any]]) -> Tuple[int, float]:
    qty = sum(int(r.get("amount", 0) or 0) for r in rows)
    value = sum(float(r.get("price", 0) or 0) * int(r.get("amount", 0) or 0) for r in rows)
    return qty, value

def build_filter_payload(
    filters: Optional[Dict[str, Any]],
    min_price: Optional[float],
    max_price: Optional[float],
    price: Optional[float] = None
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if filters:
        payload.update(filters)
    if price is not None:
        payload["minPrice"] = float(price)
        payload["maxPrice"] = float(price)
        return payload
    if min_price is not None:
        payload["minPrice"] = float(min_price)
    if max_price is not None:
        payload["maxPrice"] = float(max_price)
    return payload

# =======================
# ЗАПРОСЫ К ИТИГРИС (POST режим)
# =======================
async def fetch_optima_remains_once(
    category: str,
    department_id: Optional[int],
    page: int,
    filter_payload: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    if not API_KEY:
        raise RuntimeError("ITIGRIS_API_KEY is not configured")

    body: Dict[str, Any] = {"product": category}
    if department_id:
        body["departmentId"] = department_id
    if page:
        body["page"] = page
    if filter_payload:
        body["filter"] = filter_payload

    params = {"key": API_KEY}

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(BASE_URL, params=params, json=body)
        if resp.status_code != 200:
            raise RuntimeError(f"Itigris error {resp.status_code}: {resp.text}")
        data = resp.json()
        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected response: {data}")
        return data

async def fetch_optima_remains(
    category: str,
    department_ids: List[int],
    filter_payload: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    all_rows: List[Dict[str, Any]] = []
    for dep_id in department_ids:
        page = 1
        while True:
            rows = await fetch_optima_remains_once(category, dep_id, page, filter_payload)
            if not rows:
                break
            for r in rows:
                if "department" not in r and dep_id:
                    r["department"] = dep_id
            all_rows.extend(rows)
            page += 1
    return all_rows

# =======================
# MODELS
# =======================
class RemainsFilteredRequest(BaseModel):
    category: str
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    group: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    price: Optional[float] = None
    return_items: Optional[bool] = None
    items_limit: Optional[int] = None

# =======================
# PROTECTED OPENAPI + SWAGGER
# =======================
@app.get("/openapi.json", include_in_schema=False)
def openapi_json(request: Request):
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err
        
    schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
        description="Optima Assistant API (protected)",
    )

    schema["servers"] = [
        {"url": "https://itigris-gpt-server.onrender.com?token=odl_super_secure_private_2026"}
    ]
     # --- говорим GPT Actions, что нужна авторизация через query параметр token ---
    schema.setdefault("components", {}).setdefault("securitySchemes", {})
    schema["components"]["securitySchemes"]["OdlServerToken"] = {
        "type": "apiKey",
        "in": "query",
        "name": "token",
        "description": "ODL server token. Send as ?token=..."
    }
    schema["security"] = [{"OdlServerToken": []}]
    return JSONResponse(schema)

@app.get("/docs", include_in_schema=False)
def swagger_docs(request: Request):
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err
    token = request.query_params.get("token")
    # чтобы swagger сам ходил за /openapi.json тоже с токеном
    openapi_url = f"/openapi.json?token={token}"
    return get_swagger_ui_html(openapi_url=openapi_url, title=f"{app.title} - Swagger")

# =======================
# ENDPOINTS (все защищены токеном)
# =======================
@app.get("/")
def home(request: Request):
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err
    return {"message": "Optima Assistant is running", "version": app.version}

@app.get("/healthz")
def healthz(request: Request):
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err
    return {"ok": True, "version": app.version}

@app.get("/departments")
def departments(request: Request):
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err
    return {"departments": [{"name": k, "id": v} for k, v in DEPARTMENTS.items()], "aliases": DEPARTMENT_ALIASES}

@app.get("/categories")
def categories(request: Request):
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err
    return {"codes": list(CATEGORY_FILTERS.keys()), "aliases": CATEGORY_ALIASES}

# -------- Excel: один департамент
@app.get("/remains/{category}")
async def remains_one_department(
    request: Request,
    category: str,
    department_id: Optional[int] = None,
    department_name: Optional[str] = None
):
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err

    cat = normalize_category(category)
    if cat not in CATEGORY_FILTERS:
        return JSONResponse({"error": "unknown_category"}, status_code=400)

    dep_id = normalize_department(department_id, department_name)
    if not dep_id:
        return JSONResponse({"error": "missing_department", "hint": "Укажите department_id или department_name"}, status_code=400)

    try:
        rows = await fetch_optima_remains(cat, [dep_id], filter_payload=None)
    except Exception as e:
        return JSONResponse({"error": "upstream_error", "detail": str(e)}, status_code=502)

    xls = rows_to_excel_bytes(rows, sheet_name=f"{cat}_{dep_id}")
    filename = f"{cat}_{dep_id}.xlsx"
    return StreamingResponse(
        io.BytesIO(xls),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
    )

# -------- Excel: все департаменты
@app.get("/remains-all/{category}")
async def remains_all_departments(request: Request, category: str):
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err

    cat = normalize_category(category)
    if cat not in CATEGORY_FILTERS:
        return JSONResponse({"error": "unknown_category"}, status_code=400)

    try:
        rows = await fetch_optima_remains(cat, list(DEPARTMENTS.values()), filter_payload=None)
    except Exception as e:
        return JSONResponse({"error": "upstream_error", "detail": str(e)}, status_code=502)

    xls = rows_to_excel_bytes(rows, sheet_name=f"{cat}_all")
    filename = f"{cat}_all.xlsx"
    return StreamingResponse(
        io.BytesIO(xls),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
    )

# -------- Excel: группа
@app.get("/remains-group/{category}")
async def remains_group(request: Request, category: str, group: str):
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err

    cat = normalize_category(category)
    grp = normalize_group(group)
    if cat not in CATEGORY_FILTERS:
        return JSONResponse({"error": "unknown_category"}, status_code=400)
    if grp not in GROUPS_RU:
        return JSONResponse({"error": "unknown_group"}, status_code=400)

    dep_ids = GROUPS_RU[grp]
    try:
        rows = await fetch_optima_remains(cat, dep_ids, filter_payload=None)
    except Exception as e:
        return JSONResponse({"error": "upstream_error", "detail": str(e)}, status_code=502)

    xls = rows_to_excel_bytes(rows, sheet_name=f"{cat}_{grp}")
    filename = f"{cat}_{grp}.xlsx"
    return StreamingResponse(
        io.BytesIO(xls),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
    )

# -------- JSON+аналитика: items + summary
@app.post("/remains-filtered")
async def remains_filtered(request: Request, body: RemainsFilteredRequest):
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err

    cat = normalize_category(body.category)
    if cat not in CATEGORY_FILTERS:
        return JSONResponse({"error": "unknown_category"}, status_code=400)

    try:
        dep_ids = resolve_dep_ids(body.department_id, body.department_name, body.group)
    except ValueError:
        return JSONResponse({"error": "unknown_group"}, status_code=400)

    single_scope = bool(body.department_id or body.department_name)
    return_items = body.return_items if isinstance(body.return_items, bool) else single_scope
    items_limit = body.items_limit if isinstance(body.items_limit, int) else (1000 if single_scope else 0)
    items_limit = max(0, min(items_limit, 1000))

    fp = build_filter_payload(body.filters, body.min_price, body.max_price, body.price)
    fp = fp if fp else None

    try:
        rows = await fetch_optima_remains(cat, dep_ids, filter_payload=fp)
    except Exception as e:
        return JSONResponse({"error": "upstream_error", "detail": str(e)}, status_code=502)

    total_qty, total_value = sum_qty_value(rows)
    avg_price = (total_value / total_qty) if total_qty else 0.0

    resp: Dict[str, Any] = {
        "positions_count": len(rows),  # позиций (не штук!)
        "summary": {
            "total_qty": total_qty,
            "total_value": round(total_value, 2),
            "avg_price": round(avg_price, 2),
        }
    }

    if return_items and items_limit > 0:
        resp["items"] = rows[:items_limit]
        if len(rows) > items_limit:
            resp["items_truncated"] = True
            resp["items_total"] = len(rows)

    return resp

# -------- только summary (быстро)
@app.post("/count-by-filters")
async def count_by_filters(request: Request, body: RemainsFilteredRequest):
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err

    cat = normalize_category(body.category)
    if cat not in CATEGORY_FILTERS:
        return JSONResponse({"error": "unknown_category"}, status_code=400)

    try:
        dep_ids = resolve_dep_ids(body.department_id, body.department_name, body.group)
    except ValueError:
        return JSONResponse({"error": "unknown_group"}, status_code=400)

    fp = build_filter_payload(body.filters, body.min_price, body.max_price, body.price)
    fp = fp if fp else None

    try:
        rows = await fetch_optima_remains(cat, dep_ids, filter_payload=fp)
    except Exception as e:
        return JSONResponse({"error": "upstream_error", "detail": str(e)}, status_code=502)

    total_qty, total_value = sum_qty_value(rows)
    avg_price = (total_value / total_qty) if total_qty else 0.0

    return {
        "category": cat,
        "scope": {
            "department_id": body.department_id,
            "department_name": body.department_name,
            "group": body.group,
            "departments_used": dep_ids,
        },
        "total_qty": total_qty,
        "total_value": round(total_value, 2),
        "avg_price": round(avg_price, 2),
    }

# -------- GET: count by price (и опционально items)
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
):
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err

    cat = normalize_category(category)
    if cat not in CATEGORY_FILTERS:
        return JSONResponse({"error": "unknown_category"}, status_code=400)

    try:
        dep_ids = resolve_dep_ids(department_id, department_name, group)
    except ValueError:
        return JSONResponse({"error": "unknown_group"}, status_code=400)

    fp = build_filter_payload(filters=None, min_price=min_price, max_price=max_price, price=None)
    fp = fp if fp else None

    try:
        rows = await fetch_optima_remains(cat, dep_ids, filter_payload=fp)
    except Exception as e:
        return JSONResponse({"error": "upstream_error", "detail": str(e)}, status_code=502)

    total_qty, total_value = sum_qty_value(rows)
    avg_price = (total_value / total_qty) if total_qty else 0.0

    items = [{
        "label": r.get("name") or r.get("model") or "",
        "price": r.get("price"),
        "qty": r.get("amount"),
        "department": r.get("department"),
    } for r in (rows[:limit_items] if limit_items else [])]

    scope = "all"
    if department_id or department_name:
        d = normalize_department(department_id, department_name)
        scope = f"department:{d}" if d else "department:unknown"
    elif group:
        g = normalize_group(group)
        scope = f"group:{g}"

    return {
        "category": cat,
        "scope": scope,
        "min_price": min_price,
        "max_price": max_price,
        "total_qty": total_qty,
        "total_value": round(total_value, 2),
        "avg_price": round(avg_price, 2),
        "items": items,
    }

# -------- GET: просто "сколько штук" (без ценовых фильтров)
@app.get("/count/{category}")
async def count_all(
    request: Request,
    category: str,
    department_id: Optional[int] = None,
    department_name: Optional[str] = None,
    group: Optional[str] = None,
):
    return await count_by_price(
        request=request,
        category=category,
        min_price=None,
        max_price=None,
        department_id=department_id,
        department_name=department_name,
        group=group,
        limit_items=0,
    )
@app.get("/breakdown/{category}")
async def breakdown_category(
    request: Request,
    category: str,
    department_name: Optional[str] = None
):
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err

    cat = normalize_category(category)
    if cat not in CATEGORY_FILTERS:
        return JSONResponse({"error": "unknown_category"}, status_code=400)

    dep_id = normalize_department(None, department_name)
    dep_ids = [dep_id] if dep_id else list(DEPARTMENTS.values())

    try:
        rows = await fetch_optima_remains(cat, dep_ids, filter_payload=None)
    except Exception as e:
        return JSONResponse({"error": "upstream_error", "detail": str(e)}, status_code=502)

    design = {}
    type_ = {}
    material = {}

    for r in rows:
        qty = int(r.get("amount", 0) or 0)

        d = r.get("design")
        t = r.get("type")
        m = r.get("material")

        if d:
            design[d] = design.get(d, 0) + qty

        if t:
            type_[t] = type_.get(t, 0) + qty

        if m:
            material[m] = material.get(m, 0) + qty

    return {
        "category": cat,
        "department": department_name,
        "design": design,
        "type": type_,
        "material": material
    }
@app.get("/gpt/breakdown/{category}")
async def gpt_breakdown(
    request: Request,
    category: str,
    department_name: Optional[str] = None
):
    auth_err = require_auth_token(request)
    if auth_err:
        return auth_err

    cat = normalize_category(category)

    # Проверяем категорию
    if cat not in CATEGORY_FILTERS:
        return JSONResponse({"error": "unknown_category"}, status_code=400)

    # Определяем департамент
    dep_id = normalize_department(None, department_name)

    # Если передали название отдела, но оно не распознано
    if department_name and not dep_id:
        return JSONResponse({"error": "unknown_department"}, status_code=400)

    # Если департамент найден — используем его
    # иначе берём все департаменты
    dep_ids = [dep_id] if dep_id else list(DEPARTMENTS.values())

    try:
        rows = await fetch_optima_remains(cat, dep_ids, filter_payload=None)
    except Exception as e:
        return JSONResponse({"error": "upstream_error", "detail": str(e)}, status_code=502)

    design = {}
    type_ = {}
    material = {}

    for r in rows:
        qty = int(r.get("amount", 0) or 0)

        d = r.get("design")
        t = r.get("type")
        m = r.get("material")

        if d:
            design[d] = design.get(d, 0) + qty

        if t:
            type_[t] = type_.get(t, 0) + qty

        if m:
            material[m] = material.get(m, 0) + qty

    return {
        "category": cat,
        "department": department_name,
        "design": design,
        "type": type_,
        "material": material
    }
