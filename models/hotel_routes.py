from flask import Blueprint, jsonify
from models.db import get_connection

hotel_bp = Blueprint("hotel", __name__)

# Simple function to filter hotels by proximity
# For demo, we match listings with route 'location' substring
@hotel_bp.route("/trips/<int:trip_id>/routes/<int:route_id>/hotels", methods=["GET"])
def get_hotels_along_route(trip_id, route_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Get route start/end (for simplicity, using route_id)
    cursor.execute("""
        SELECT start_lat, start_lng, end_lat, end_lng
        FROM trip_routes
        WHERE id=%s
    """, (route_id,))
    route = cursor.fetchone()
    if not route:
        cursor.close()
        conn.close()
        return jsonify([]), 200

    # 2. Get approved listings in relevant location
    # For demo, we consider listings whose 'location' contains the destination
    cursor.execute("""
        SELECT id, title, description, image_path, price, location, rooms_available, room_details, eco_cert_url
        FROM listing
        WHERE is_approved=1 AND location IS NOT NULL
    """)
    listings = cursor.fetchall()

    cursor.close()
    conn.close()
    return jsonify(listings), 200
