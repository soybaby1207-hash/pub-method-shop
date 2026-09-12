from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import hashlib
import time
import random
import string
import os

app = Flask(__name__)
CORS(app)

# =============================================
# CONFIG
# =============================================
PAYPAL_CLIENT_ID = "AdDwcrFvRvMl_BM_Ib__rKegb8GoXLb-oQ7gkCATgMAzAR_cb0M_LNsFb10sDvsCLryM4HnnePqOfPaL"
PAYPAL_SECRET    = "EB1NuVup92A1uG0WnyWJjgrIDW9Ssa4qwhmj82ieawbW-DyxDUpi2PbANUJdCqFqtEgvtjV9n8ga9JF4"
PAYPAL_BASE      = "https://api-m.sandbox.paypal.com"  # sandbox

ADMIN_SERVER     = "https://admin-key-server-1.onrender.com"
ADMIN_PASSWORD   = "soybaby12071207"
SECRET_KEY       = os.environ.get("SECRET_KEY", "MiClaveSecreta123")

PLANS = {
    "1day":      {"label": "1 Día",      "price": "3.00",  "duration": 86400},
    "1week":     {"label": "1 Semana",   "price": "8.00",  "duration": 604800},
    "1month":    {"label": "1 Mes",      "price": "15.00", "duration": 2592000},
    "permanent": {"label": "Permanente", "price": "20.00", "duration": 0},
}

# =============================================
# PAYPAL HELPERS
# =============================================
def get_paypal_token():
    r = requests.post(
        f"{PAYPAL_BASE}/v1/oauth2/token",
        auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
        data={"grant_type": "client_credentials"}
    )
    return r.json().get("access_token")

def create_paypal_order(plan_id, username):
    plan = PLANS[plan_id]
    token = get_paypal_token()
    r = requests.post(
        f"{PAYPAL_BASE}/v2/checkout/orders",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {"currency_code": "EUR", "value": plan["price"]},
                "description": f"Pub Method Key - {plan['label']} - {username}"
            }],
            "application_context": {
                "return_url": "https://pub-method-shop.onrender.com/success",
                "cancel_url": "https://pub-method-shop.onrender.com/cancel"
            }
        }
    )
    return r.json()

def capture_paypal_order(order_id):
    token = get_paypal_token()
    r = requests.post(
        f"{PAYPAL_BASE}/v2/checkout/orders/{order_id}/capture",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    )
    return r.json()

def generate_key_on_server(username, duration):
    r = requests.post(
        f"{ADMIN_SERVER}/generate",
        json={"password": ADMIN_PASSWORD, "username": username, "duration": duration}
    )
    return r.json()

# =============================================
# ROUTES
# =============================================
@app.route("/")
def index():
    return "Pub Method Key Shop ✅"

@app.route("/create-order", methods=["POST"])
def create_order():
    data = request.get_json()
    plan_id = data.get("plan")
    username = data.get("username", "").strip().upper()
    if not plan_id or plan_id not in PLANS:
        return jsonify({"success": False, "error": "Plan inválido"}), 400
    if not username:
        return jsonify({"success": False, "error": "Usuario obligatorio"}), 400
    try:
        order = create_paypal_order(plan_id, username)
        order_id = order.get("id")
        if not order_id:
            return jsonify({"success": False, "error": "Error creando orden PayPal"}), 500
        # Guardar en memoria temporal
        pending_orders[order_id] = {"plan": plan_id, "username": username}
        return jsonify({"success": True, "order_id": order_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/capture-order", methods=["POST"])
def capture_order():
    data = request.get_json()
    order_id = data.get("order_id")
    if not order_id:
        return jsonify({"success": False, "error": "order_id requerido"}), 400
    order_data = pending_orders.get(order_id)
    if not order_data:
        return jsonify({"success": False, "error": "Orden no encontrada"}), 404
    try:
        capture = capture_paypal_order(order_id)
        status = capture.get("status")
        if status != "COMPLETED":
            return jsonify({"success": False, "error": "Pago no completado"}), 400
        # Generar key
        plan = PLANS[order_data["plan"]]
        key_result = generate_key_on_server(order_data["username"], plan["duration"])
        if not key_result.get("success"):
            return jsonify({"success": False, "error": "Error generando key"}), 500
        del pending_orders[order_id]
        return jsonify({
            "success": True,
            "key": key_result["key"],
            "expiry": key_result["expiry"],
            "username": key_result["username"],
            "plan": plan["label"]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/plans", methods=["GET"])
def get_plans():
    return jsonify({"success": True, "plans": PLANS})

pending_orders = {}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
