from flask import Blueprint, jsonify
from models.db import get_connection

hotel_bp = Blueprint("hotel", __name__)


@hotel_bp.route("/trips/<int:trip_id>/routes/<int:route_id>/hotels", methods=["GET"])
def get_hotels_along_route(trip_id, route_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    
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

    cursor.execute("""
        SELECT id, title, description, image_path, price, location, rooms_available, room_details, eco_cert_url
        FROM listing
        WHERE is_approved=1 AND location IS NOT NULL
    """)
    listings = cursor.fetchall()

    cursor.close()
    conn.close()
    return jsonify(listings), 200
