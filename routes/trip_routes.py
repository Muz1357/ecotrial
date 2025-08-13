from flask import Blueprint, request, jsonify
from models.db import get_connection
from models.trip import Trip
from models.trip_stop import TripStop
from models.trip_route import TripRoute

trip_bp = Blueprint('trip', __name__)

EMISSION_FACTORS = {
    "walking": 0,
    "cycling": 0,
    "bus": 0.05,
    "train": 0.04,
    "car": 0.12,
    "taxi": 0.14,
    "flight": 0.25
}

def calculate_co2(distance_km, mode):
    return distance_km * EMISSION_FACTORS.get(mode, 0)

@trip_bp.route('/trips', methods=['POST'])
def create_trip():
    data = request.get_json()
    tourist_id = data.get('tourist_id')
    start_location = data.get('start_location')
    end_location = data.get('end_location')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    stops = data.get('stops', [])  # list of dicts with location_name, lat, lng, type
    routes = data.get('routes', []) # list of dicts with mode, distance, duration, cost

    if not all([tourist_id, start_location, end_location, start_date, end_date]):
        return jsonify({"message":"Missing required fields"}), 400

    total_distance = sum([r['distance'] for r in routes])
    total_co2 = sum([calculate_co2(r['distance'], r['mode']) for r in routes])

    trip_id = Trip.create(tourist_id, start_location, end_location, start_date, end_date, total_distance, total_co2)

    for i, stop in enumerate(stops):
        TripStop.create(trip_id, stop['location_name'], stop['latitude'], stop['longitude'], stop['type'], i)

    for route in routes:
        TripRoute.create(
            trip_id,
            route['mode'],
            route['distance'],
            calculate_co2(route['distance'], route['mode']),
            route.get('duration',0),
            route.get('cost',0),
            route.get('is_eco_friendly', False)
        )

    return jsonify({"trip_id": trip_id, "total_distance": total_distance, "total_co2": total_co2}), 201

@trip_bp.route('/trips/<int:trip_id>/routes', methods=['GET'])
def get_trip_routes(trip_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, trip_id, mode, distance_km, co2_kg, duration_min, cost, is_eco_friendly
        FROM trip_routes
        WHERE trip_id = %s
    """, (trip_id,))
    routes = cursor.fetchall()
    cursor.close()
    conn.close()

    # Add dummy start/end coordinates for map visualization
    for r in routes:
        # In real case, fetch actual coordinates from trip stops
        r['start_lat'] = 0.0
        r['start_lng'] = 0.0
        r['end_lat'] = 0.1
        r['end_lng'] = 0.1

    return jsonify(routes), 200


# --- POST to confirm a selected route ---
@trip_bp.route('/trips/<int:trip_id>/routes/<int:route_id>/confirm', methods=['POST'])
def confirm_trip_route(trip_id, route_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Set all routes for this trip as not selected
    cursor.execute("""
        UPDATE trip_routes SET is_selected = 0 WHERE trip_id = %s
    """, (trip_id,))

    # Mark chosen route as selected
    cursor.execute("""
        UPDATE trip_routes SET is_selected = 1 WHERE id = %s AND trip_id = %s
    """, (route_id, trip_id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Route confirmed"}), 200

@trip_bp.route("/api/trips/<int:trip_id>/routes/<int:route_id>/hotels", methods=["GET"])
def get_hotels_along_route(trip_id, route_id):
    """
    Returns approved hotels along the selected route with CO2 info.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # For simplicity, filter by hotels in route area (backend can refine by geolocation)
    query = """
        SELECT id, title, price, image_path, location, rooms_available, room_details, eco_cert_url
        FROM listing
        WHERE is_approved = 1
    """
    cursor.execute(query)
    listings = cursor.fetchall()

    hotels_with_co2 = []
    for hotel in listings:
        # Example: CO2 standard (non-eco) = 10 kg, CO2 eco-certified = 6 kg
        # In real app, calculate based on hotel type, distance from route, etc.
        co2_standard = 10
        co2_eco = 6 if hotel['eco_cert_url'] else 9  # slightly less if eco-certified
        hotels_with_co2.append({
            "id": hotel['id'],
            "title": hotel['title'],
            "price": hotel['price'],
            "image_path": hotel['image_path'],
            "location": hotel['location'],
            "rooms_available": hotel['rooms_available'],
            "room_details": hotel['room_details'],
            "eco_cert_url": hotel['eco_cert_url'],
            "co2_standard": co2_standard,
            "co2_eco": co2_eco
        })

    cursor.close()
    conn.close()
    return jsonify(hotels_with_co2), 200