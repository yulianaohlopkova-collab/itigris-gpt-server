from flask import Flask, request, jsonify, send_file
import requests
import os
import io
import pandas as pd

app = Flask(__name__)

ITIGRIS_APP_NAME = os.getenv("ITIGRIS_APP_NAME")
ITIGRIS_API_KEY = os.getenv("ITIGRIS_API_KEY")

DEPARTMENTS = {
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
    "Офис": 1000000003
}


def fetch_all_pages(payload):
    all_data = []
    page = 1

    while True:
        payload["page"] = page
        url = f"https://optima.itigris.ru/{ITIGRIS_APP_NAME}/remoteRemains/list?key={ITIGRIS_API_KEY}"

        response = requests.post(url, json=payload)

        if response.status_code != 200:
            return {"error": response.text, "status": response.status_code}

        data = response.json()

        if not data:
            break

        all_data.extend(data)
        page += 1

    return all_data


@app.route("/remains", methods=["POST"])
def get_remains():
    request_data = request.json

    product = request_data.get("product")
    department_name = request_data.get("department")
    filters = request_data.get("filter", {})

    payload = {
        "product": product,
        "filter": filters
    }

    if department_name and department_name in DEPARTMENTS:
        payload["departmentId"] = DEPARTMENTS[department_name]

    data = fetch_all_pages(payload)

    return jsonify(data)


@app.route("/remains/excel", methods=["POST"])
def get_remains_excel():
    request_data = request.json

    product = request_data.get("product")
    department_name = request_data.get("department")
    filters = request_data.get("filter", {})

    payload = {
        "product": product,
        "filter": filters
    }

    if department_name and department_name in DEPARTMENTS:
        payload["departmentId"] = DEPARTMENTS[department_name]

    data = fetch_all_pages(payload)

    if isinstance(data, dict) and "error" in data:
        return jsonify(data), data["status"]

    df = pd.DataFrame(data)

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(
        output,
        download_name="remains.xlsx",
        as_attachment=True
    )


@app.route("/")
def home():
    return {"status": "Server is running"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
