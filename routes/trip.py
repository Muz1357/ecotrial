from flask import Blueprint, request, jsonify
from models.db import get_connection
from utils.co2_calculator import calculate_co2

trip_bp = Blueprint('trip', __name__)

@trip_bp.route('/', methods=['POST'])
def create_trip():
    data = request.json
    tourist_id = data['tourist_id']
    start_location = data['start_location']
    end_location = data['end_location']
    travel_dates = data['travel_dates']
    stops = data.get('stops', [])

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO trips (tourist_id, start_location, end_location, travel_dates, stops)
        VALUES (%s, %s, %s, %s, %s)
    """, (tourist_id, start_location, end_location, str(travel_dates), str(stops)))
    conn.commit()
    trip_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({"status": "success", "trip_id": trip_id})

@trip_bp.route('/<int:trip_id>/legs', methods=['POST'])
def add_trip_leg(trip_id):
    data = request.json
    start_point = data['start_point']
    end_point = data['end_point']
    distance_km = float(data['distance_km'])
    transport_mode = data['transport_mode']

    co2 = calculate_co2(distance_km, transport_mode)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO trip_legs (trip_id, start_point, end_point, distance_km, transport_mode, co2_kg)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (trip_id, start_point, end_point, distance_km, transport_mode, co2))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"status": "success", "co2_kg": co2})

@trip_bp.route('/<int:tourist_id>', methods=['GET'])
def get_trips(tourist_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM trips WHERE tourist_id=%s", (tourist_id,))
    trips = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(trips)
