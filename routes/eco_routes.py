# eco_routes.py
from flask import Blueprint, jsonify
from models.db import get_connection

eco_bp = Blueprint('eco', __name__)

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


@eco_bp.route('/carbon_summary/<int:user_id>', methods=['GET'])
def get_carbon_summary(user_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            IFNULL(SUM(co2_kg), 0) AS total_co2_emitted,
            IFNULL(SUM(points_awarded), 0) AS total_points_awarded
        FROM travel_logs 
        WHERE tourist_id = %s
    """, (user_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify({
        "co2_emitted": float(result["total_co2_emitted"]),
        "points_awarded": int(result["total_points_awarded"])
    })

