from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("ODL_SERVER_TOKEN", "dev-token")

from fastapi.testclient import TestClient

import server


async def fake_fetch_optima_remains(
    category: str,
    department_ids: List[int],
    filter_payload: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows = [
        {
            "manufacturer": "Alcon",
            "name": "Air Optix",
            "dioptre": "-5.5",
            "radius": "8.6",
            "diameter": "14.2",
            "amount": 3,
            "price": 2100,
            "departmentId": department_ids[0],
        },
        {
            "manufacturer": "CooperVision",
            "name": "Biofinity",
            "dioptre": "-3.0",
            "radius": "8.6",
            "diameter": "14.0",
            "amount": 2,
            "price": 1900,
            "departmentId": department_ids[0],
        },
    ]
    if filter_payload and filter_payload.get("dioptre"):
        rows = [row for row in rows if row.get("dioptre") == filter_payload["dioptre"]]
    return rows


def main() -> None:
    server.fetch_optima_remains = fake_fetch_optima_remains
    client = TestClient(server.app)
    headers = {"X-ODL-Token": "dev-token"}

    checks = [
        ("GET", "/healthz", None),
        ("GET", "/departments", None),
        ("GET", "/categories", None),
        ("GET", "/count/contactlenses?department_name=Ленина", None),
        ("GET", "/count-by-price/contactlenses?department_name=Ленина&min_price=1000&max_price=3000", None),
        ("GET", "/breakdown/contactlenses?department_name=Ленина", None),
        ("GET", "/gpt/breakdown/contactlenses?department_name=Ленина", None),
        ("POST", "/sales/analyze", {}),
        (
            "POST",
            "/remains-filtered",
            {"category": "contactlenses", "department_name": "Ленина", "return_items": True, "items_limit": 10},
        ),
        (
            "POST",
            "/remains-filtered",
            {"category": "контактные линзы", "group": "салоны", "return_items": False},
        ),
        (
            "POST",
            "/remains-filtered",
            {
                "category": "contactlenses",
                "department_name": "Качели",
                "filters": {"dioptre": "-5.5"},
                "return_items": True,
                "items_limit": 20,
            },
        ),
    ]

    for method, url, payload in checks:
        if method == "GET":
            response = client.get(url, headers=headers)
        else:
            response = client.post(url, json=payload, headers=headers)
        assert response.status_code == 200, (method, url, response.status_code, response.text)
        print(method, url, response.status_code)


if __name__ == "__main__":
    main()
