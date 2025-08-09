# eco_routes.py
from flask import Blueprint, jsonify
from models.db import get_connection

eco_bp = Blueprint('eco', __name__)

@eco_bp.route('/eco_points/<int:user_id>/balance', methods=['GET'])
def get_eco_balance(user_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT eco_points FROM user_account WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify({"balance": result["points_balance"] if result else 0})

@eco_bp.route('/carbon_summary/<int:user_id>', methods=['GET'])
def get_carbon_summary(user_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            IFNULL(SUM(co2_kg), 0) AS total_co2_emitted,
            IFNULL(SUM(points_awarded), 0) AS total_points_awarded
        FROM your_table_name  -- replace with your actual table name
        WHERE tourist_id = %s
    """, (user_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify({
        "co2_emitted": float(result["total_co2_emitted"]),
        "points_awarded": int(result["total_points_awarded"])
    })

