# eco_routes.py (or extend booking_bp)
from flask import Blueprint, request, jsonify
from dateutil import parser
from models.db import get_connection
import math
from datetime import datetime

eco_bp = Blueprint('eco', __name__)

# Emission and points rules (tweak as you like)
EMISSION_FACTORS = {
    "walking": 0.0,
    "cycling": 0.0,
    "tuk": 0.08,
    "bus": 0.05,
    "car": 0.2,
    "unknown": 0.15
}
POINTS_PER_KM_BY_MODE = {
    "walking": 10,  # points per km
    "cycling": 7,
    "tuk": 2,
    "bus": 3,
    "car": 0,
    "unknown": 0
}

# POST /travel_logs  <- frontend will call this
@eco_bp.route('/travel_logs', methods=['POST'])
def create_travel_log():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    tourist_id = data.get('tourist_id')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    distance_km = data.get('distance_km')
    mode = (data.get('mode') or 'unknown').lower()

    if tourist_id is None or start_time is None or end_time is None or distance_km is None:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        # parse datetimes
        start_dt = parser.isoparse(start_time)
        end_dt = parser.isoparse(end_time)
    except Exception as e:
        return jsonify({"error": "Invalid datetime format", "details": str(e)}), 400

    # convert distance to float, sanitize
    try:
        distance = float(distance_km)
        if distance < 0:
            distance = 0.0
    except:
        distance = 0.0

    # calculate co2 and points
    factor = EMISSION_FACTORS.get(mode, EMISSION_FACTORS['unknown'])
    co2_kg = round(distance * float(factor), 3)
    points_rate = POINTS_PER_KM_BY_MODE.get(mode, 0)
    points_awarded = int(math.floor(distance * points_rate))

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO travel_logs (tourist_id, start_time, end_time, distance_km, mode, co2_kg, points_awarded)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (tourist_id, start_dt, end_dt, distance, mode, co2_kg, points_awarded))

        # update user's eco_points in user_account table
        if points_awarded > 0:
            cursor.execute("""
                UPDATE user_account
                SET eco_points = COALESCE(eco_points, 0) + %s
                WHERE id = %s
            """, (points_awarded, tourist_id))

            # optional: create a transaction row in eco_points_transactions (if you have that table)
            try:
                cursor.execute("""
                    INSERT INTO eco_points_transactions (user_id, points, type, booking_id, description, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, (tourist_id, points_awarded, 'earn', None, f"Earned {points_awarded} points for {mode} trip"))
            except:
                # ignore if transactions table missing
                pass

        conn.commit()
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({"error": "Failed to save travel log", "details": str(e)}), 500

    # fetch new balance to return to client
    cursor.execute("SELECT eco_points FROM user_account WHERE id = %s", (tourist_id,))
    row = cursor.fetchone()
    new_balance = int(row[0]) if row and row[0] is not None else 0

    cursor.close()
    conn.close()

    return jsonify({
        "message": "Travel log saved",
        "mode": mode,
        "distance_km": round(distance, 3),
        "co2_kg": co2_kg,
        "points_awarded": points_awarded,
        "new_balance": new_balance
    }), 201


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


# GET /tourists/<id>/co2-summary
@eco_bp.route('/tourists/<int:tourist_id>/co2-summary', methods=['GET'])
def get_co2_summary(tourist_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            IFNULL(SUM(CASE WHEN mode IN ('walking','cycling') THEN 0 ELSE co2_kg END), 0) AS co2_emitted,
            IFNULL(SUM(CASE WHEN mode IN ('walking','cycling') THEN co2_kg ELSE 0 END), 0) AS co2_saved,
            IFNULL(SUM(points_awarded), 0) AS total_points
        FROM travel_logs
        WHERE tourist_id = %s
    """, (tourist_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify({
        "co2_emitted": float(result["co2_emitted"] or 0),
        "co2_saved": float(result["co2_saved"] or 0),
        "total_points": int(result["total_points"] or 0)
    })
