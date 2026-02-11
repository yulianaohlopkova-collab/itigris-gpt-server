from flask import Flask, request, jsonify, send_file
import requests
import os
import io
import pandas as pd

app = Flask(__name__)

# Итигрис
ITIGRIS_APP_NAME = os.getenv("ITIGRIS_APP_NAME")
ITIGRIS_API_KEY = os.getenv("ITIGRIS_API_KEY")

# Защита нашего сервера
ODL_SERVER_TOKEN = os.getenv("ODL_SERVER_TOKEN")  # хранится в Render Environment
AUTH_HEADER_NAME = "X-ODL-TOKEN"                  # как будет называться заголовок

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

def require_auth():
    """
    Проверяем, что пришёл правильный токен в заголовке.
    """
    # Если токен не задан в окружении — лучше сразу запретить доступ (чтобы не забыть включить защиту)
    if not ODL_SERVER_TOKEN:
        return False, ("Server token is not configured", 500)

    provided = request.headers.get(AUTH_HEADER_NAME)
    if not provided or provided != ODL_SERVER_TOKEN:
        return False, ("Forbidden", 403)

    return True, None


@app.route("/")
def home():
    return "Itigris GPT Server is running"


@app.route("/inventory", methods=["GET"])
def get_inventory():
    ok, err = require_auth()
    if not ok:
        message, code = err
        return jsonify({"error": message}), code

    category = request.args.get("category")
    department_name = request.args.get("department")

    if not category:
        return jsonify({"error": "Category is required"}), 400

    if not ITIGRIS_APP_NAME or not ITIGRIS_API_KEY:
        return jsonify({"error": "Environment variables not configured"}), 500

    base_url = f"https://optima.itigris.ru/{ITIGRIS_APP_NAME}/remoteRemains/list"
    params = {"key": ITIGRIS_API_KEY, "product": category}

    if department_name:
        if department_name not in DEPARTMENTS:
            return jsonify({"error": "Unknown department"}), 400
        params["departmentId"] = DEPARTMENTS[department_name]

    response = requests.get(base_url, params=params)

    if response.status_code != 200:
        return jsonify({
            "error": "Itigris API error",
            "status": response.status_code,
            "details": response.text
        }), response.status_code

    data = response.json()

    if not data:
        return jsonify({"message": "No data found"})

    df = pd.DataFrame(data)

    reverse_departments = {v: k for k, v in DEPARTMENTS.items()}
    if "department" in df.columns:
        df["department_name"] = df["department"].map(reverse_departments)

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="inventory.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.route("/departments", methods=["GET"])
def list_departments():
    ok, err = require_auth()
    if not ok:
        message, code = err
        return jsonify({"error": message}), code

    return jsonify(DEPARTMENTS)


if __name__ == "__main__":
    app.run(debug=True)
