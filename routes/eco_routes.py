# eco_routes.py (or extend booking_bp)
from flask import Blueprint, request, jsonify
from dateutil import parser
from models.db import get_connection
import math
from datetime import datetime

eco_bp = Blueprint('eco', __name__)

# GET /eco_points/<user_id>/balance  (you already have a version — keep this)
@eco_bp.route('/eco_points/<int:user_id>/balance', methods=['GET'])
def get_eco_balance(user_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT eco_points FROM user_account WHERE id = %s", (user_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    balance = result["eco_points"] if result and result["eco_points"] is not None else 0
    return jsonify({"balance": balance})

