from flask import jsonify
from . import business_bp
from models.db import get_connection
from flask import Blueprint

business_bp = Blueprint('business', __name__)

@business_bp.route('/report/<int:business_owner_id>', methods=['GET'])
def business_report(business_owner_id):
    conn = get_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    cursor = conn.cursor(dictionary=True)

    # 1. Business owner info
    cursor.execute("""
        SELECT id, name, business_name, profile_image, eco_points 
        FROM user_account WHERE id = %s
    """, (business_owner_id,))
    owner = cursor.fetchone()

    # 2. Listings
    cursor.execute("""
        SELECT id, title, price, rooms_available, is_approved 
        FROM listing WHERE user_id = %s
    """, (business_owner_id,))
    listings = cursor.fetchall()

    # 3. Booking summary
    cursor.execute("""
        SELECT 
            COUNT(*) AS total_bookings,
            SUM(is_cancelled=1) AS cancelled,
            SUM(is_completed=1) AS completed,
            SUM(is_released=1) AS released,
            COALESCE(SUM(CAST(price AS DECIMAL(10,2))),0) AS revenue
        FROM booking b
        JOIN listing l ON b.listing_id = l.id
        WHERE l.user_id = %s
    """, (business_owner_id,))
    booking_summary = cursor.fetchone()

    # 4. Room utilization
    cursor.execute("""
        SELECT 
            SUM(ra.rooms_booked) AS total_rooms_booked,
            SUM(l.rooms_available) AS total_rooms_available
        FROM room_availability ra
        JOIN listing l ON ra.listing_id = l.id
        WHERE l.user_id = %s
    """, (business_owner_id,))
    room_data = cursor.fetchone()

    # 5. Eco Points summary
    cursor.execute("""
        SELECT 
            SUM(CASE WHEN type='earn' THEN points ELSE 0 END) AS earned,
            SUM(CASE WHEN type='redeem' THEN points ELSE 0 END) AS redeemed,
            SUM(CASE WHEN type='revert' THEN points ELSE 0 END) AS reverted
        FROM eco_points_transactions
        WHERE user_id = %s
    """, (business_owner_id,))
    eco_points = cursor.fetchone()

    cursor.close()
    conn.close()

    return jsonify({
        "owner": owner,
        "listings": listings,
        "booking_summary": booking_summary,
        "room_data": room_data,
        "eco_points": eco_points
    })
