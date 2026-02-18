import os
import io
from typing import Optional, Dict, List, Any, Tuple

import httpx
from fastapi import FastAPI, Query, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="Optima Assistant API", version="2.0.0")

# =======================
# НАСТРОЙКИ И СЕКРЕТЫ
# =======================
APP_NAME = os.getenv("ITIGRIS_APP_NAME", "odl")
API_KEY = os.getenv("ITIGRIS_API_KEY")
ODL_SERVER_TOKEN = os.getenv("ODL_SERVER_TOKEN")

TIMEOUT = 40.0
BASE_URL = f"https://optima.itigris.ru/{APP_NAME}/remoteRemains/list"

# =======================
# 🔐 ГЛОБАЛЬНАЯ ЗАЩИТА СЕРВЕРА
# =======================
def require_auth_token(request: Request):
    if not ODL_SERVER_TOKEN:
        raise HTTPException(status_code=500, detail="Server token not configured")

    provided = request.query_params.get("token")
    if not provided or provided != ODL_SERVER_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")


# =======================
# ДЕПАРТАМЕНТЫ
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
    "lenses": [],
    "contactlenses": [],
    "glasses": [],
    "sunglasses": [],
    "accessories": [],
}

CATEGORY_ALIASES = {
    "оправы": "glasses", "оправа": "glasses",
    "солнцезащитные": "sunglasses",
    "линзы": "lenses",
    "контактные линзы": "contactlenses",
    "аксессуары": "accessories",
}

# =======================
# ХЕЛПЕРЫ
# =======================
def normalize_category(cat: str) -> str:
    return CATEGORY_ALIASES.get(cat.strip().lower(), cat.strip().lower())

def normalize_department(department_id: Optional[int], department_name: Optional[str]) -> Optional[int]:
    if department_id:
        return department_id
    if not department_name:
        return None
    return DEPARTMENTS.get(department_name)

def rows_to_excel_bytes(rows: List[Dict[str, Any]], sheet_name: str) -> bytes:
    import xlsxwriter
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    ws = wb.add_worksheet(sheet_name[:31])

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

# =======================
# ИТИГРИС
# =======================
async def fetch_optima_remains(category: str, department_ids: List[int]):
    if not API_KEY:
        raise RuntimeError("ITIGRIS_API_KEY is not configured")

    all_rows = []
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for dep_id in department_ids:
            page = 1
            while True:
                body = {"product": category, "departmentId": dep_id, "page": page}
                resp = await client.post(BASE_URL, params={"key": API_KEY}, json=body)
                if resp.status_code != 200:
                    raise RuntimeError(resp.text)
                data = resp.json()
                if not data:
                    break
                all_rows.extend(data)
                page += 1
    return all_rows

# =======================
# ENDPOINTS (ВСЕ С ЗАЩИТОЙ)
# =======================
@app.get("/")
def home(request: Request):
    require_auth_token(request)
    return {"message": "Optima Assistant is running"}

@app.get("/healthz")
def healthz(request: Request):
    require_auth_token(request)
    return {"ok": True, "version": app.version}

@app.get("/departments")
def departments(request: Request):
    require_auth_token(request)
    return {"departments": [{"name": k, "id": v} for k, v in DEPARTMENTS.items()]}

@app.get("/remains/{category}")
async def remains_one_department(request: Request, category: str, department_name: Optional[str] = None):
    require_auth_token(request)

    cat = normalize_category(category)
    dep_id = normalize_department(None, department_name)

    if not dep_id:
        return JSONResponse({"error": "missing_department"}, status_code=400)

    rows = await fetch_optima_remains(cat, [dep_id])
    xls = rows_to_excel_bytes(rows, f"{cat}_{dep_id}")

    return StreamingResponse(
        io.BytesIO(xls),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=remains.xlsx"}
    )

