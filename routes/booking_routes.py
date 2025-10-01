from flask import Blueprint, request, jsonify
from models.booking import Booking
from models.listing import Listing
from models.eco_points import EcoPoints
from datetime import datetime, timedelta
from pytz import timezone
from dateutil import parser
from models.db import get_connection
import pytz

booking_bp = Blueprint('booking', __name__)


POINTS_PER_BOOKING_DAY = 15

LKR_PER_POINT = 10


def detect_mode(avg_kmh):
    if avg_kmh < 5:
        return "walking"
    if avg_kmh < 15:
        return "cycling"
    if avg_kmh < 30:
        return "tuk"
    if avg_kmh < 60:
        
        return "car"
    return "unknown"

EMISSION_FACTORS = {
    
    "walking": 0.0,
    "cycling": 0.0,
    "tuk": 0.08,
    "bus": 0.05,
    "car": 0.2,
    "unknown": 0.15
}

POINTS_PER_KM_BY_MODE = {
    "walking": 10,   
    "cycling": 7,
    "tuk": 2,
    "bus": 3,
    "car": 0,
    "unknown": 0
}


@booking_bp.route('/bookings', methods=['POST'])
def create_booking():
    print("👉 Received JSON:", request.get_json())
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON data"}), 400

    listing_id = data.get('listing_id')
    tourist_id = data.get('tourist_id')
    check_in = data.get('check_in')
    check_out = data.get('check_out')
    redeem_points = int(data.get('redeem_points', 0)) if data.get('redeem_points') is not None else 0

    if not listing_id or not tourist_id or not check_in or not check_out:
        return jsonify({"error": "Missing required booking fields"}), 400

    
    try:
        check_in_date = parser.isoparse(check_in).date()
        check_out_date = parser.isoparse(check_out).date()
        if check_out_date <= check_in_date:
            return jsonify({"error": "Check-out must be after check-in"}), 400
    except Exception:
        return jsonify({"error": "Invalid date format"}), 400

    
    listing = Listing.get_listing_by_id(listing_id)
    if not listing:
        return jsonify({'error': 'Listing not found'}), 404

    total_rooms = listing['rooms_available']

    
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    current_date = check_in_date
    while current_date < check_out_date:
        cursor.execute("""
            SELECT rooms_booked FROM room_availability 
            WHERE listing_id = %s AND date = %s
        """, (listing_id, current_date))
        result = cursor.fetchone()
        if result and result['rooms_booked'] >= total_rooms:
            cursor.close()
            conn.close()
            return jsonify({"error": f"No rooms available on {current_date}"}), 400
        current_date += timedelta(days=1)

    
    try:
        
        if redeem_points > 0:
            balance = EcoPoints.get_balance(tourist_id)
            if redeem_points > balance:
                cursor.close()
                conn.close()
                return jsonify({"error": "Not enough eco-points to redeem"}), 400
            redemption_amount = redeem_points * LKR_PER_POINT
            
            new_balance = EcoPoints.adjust_balance(tourist_id, -redeem_points)
            EcoPoints.create_transaction(tourist_id, redeem_points, 'redeem', None,
                                         f"Redeemed {redeem_points} points for booking (preliminary).")
        else:
            redemption_amount = 0

        
        days = (check_out_date - check_in_date).days
        points_earned = days * POINTS_PER_BOOKING_DAY

        
        booking_obj = Booking(
            listing_id=listing_id,
            tourist_id=tourist_id,
            check_in=check_in_date,
            check_out=check_out_date,
            points_earned=points_earned,
            points_redeemed=redeem_points,
            redemption_amount=redemption_amount
        )
        booking_id = booking_obj.save()

       
        if points_earned > 0:
            EcoPoints.adjust_balance(tourist_id, points_earned)
            EcoPoints.create_transaction(tourist_id, points_earned, 'earn', booking_id,
                                         f"Earned {points_earned} points for booking #{booking_id} ({days} days).")

        
        current_date = check_in_date
        while current_date < check_out_date:
            cursor.execute("""
                INSERT INTO room_availability (listing_id, date, rooms_booked)
                VALUES (%s, %s, 1)
                ON DUPLICATE KEY UPDATE rooms_booked = rooms_booked + 1
            """, (listing_id, current_date))
            current_date += timedelta(days=1)

        conn.commit()
    except Exception as e:
        conn.rollback()
        
        try:
            if redeem_points > 0:
                EcoPoints.adjust_balance(tourist_id, redeem_points)
                EcoPoints.create_transaction(tourist_id, redeem_points, 'revert', None,
                                             f"Redeem revert due to booking failure: {str(e)}")
        except Exception:
            pass
        cursor.close()
        conn.close()
        return jsonify({"error": "Failed to create booking", "details": str(e)}), 500

    cursor.close()
    conn.close()

    return jsonify({
        "message": "Booking created successfully",
        "booking_id": booking_id,
        "points_earned": points_earned,
        "points_redeemed": redeem_points,
        "redemption_amount": redemption_amount
    }), 201


@booking_bp.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
def cancel_booking(booking_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM booking WHERE id = %s AND is_cancelled = FALSE", (booking_id,))
    booking = cursor.fetchone()

    if not booking:
        cursor.close()
        conn.close()
        return jsonify({"error": "Booking not found or already cancelled"}), 404

    booking_time = booking['created_at']
    
    if isinstance(booking_time, datetime) and booking_time.tzinfo is None:
        booking_time = booking_time.replace(tzinfo=pytz.utc)
    now = datetime.now(pytz.utc)

    if (now - booking_time).total_seconds() > 3 * 3600:
        cursor.close()
        conn.close()
        return jsonify({"error": "Cancellation window expired (3 hours)."}), 403

    try:
        
        cursor.execute("UPDATE booking SET is_cancelled = TRUE WHERE id = %s", (booking_id,))

        check_in = booking['check_in']
        check_out = booking['check_out']
        listing_id = booking['listing_id']
        tourist_id = booking['tourist_id']

        current_date = check_in
        while current_date < check_out:
            cursor.execute("""
                UPDATE room_availability 
                SET rooms_booked = GREATEST(rooms_booked - 1, 0)
                WHERE listing_id = %s AND date = %s
            """, (listing_id, current_date))
            current_date += timedelta(days=1)

        
        points_earned = booking.get('points_earned', 0) or 0
        if points_earned > 0:
            EcoPoints.adjust_balance(tourist_id, -points_earned)
            EcoPoints.create_transaction(tourist_id, points_earned, 'revert', booking_id,
                                         f"Reverted {points_earned} points from cancelled booking #{booking_id}")

        
        points_redeemed = booking.get('points_redeemed', 0) or 0
        if points_redeemed > 0:
            EcoPoints.adjust_balance(tourist_id, points_redeemed)
            EcoPoints.create_transaction(tourist_id, points_redeemed, 'revert', booking_id,
                                         f"Restored {points_redeemed} redeemed points from cancelled booking #{booking_id}")

        conn.commit()
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({"error": "Failed to cancel booking", "details": str(e)}), 500

    cursor.close()
    conn.close()
    return jsonify({"message": "Booking cancelled successfully"}), 200


@booking_bp.route('/bookings/<int:tourist_id>', methods=['GET'])
def get_user_bookings(tourist_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT b.id, l.title, b.check_in, b.check_out, b.is_cancelled, b.created_at, b.points_earned, b.points_redeemed
        FROM booking b
        JOIN listing l ON b.listing_id = l.id
        WHERE b.tourist_id = %s
        ORDER BY b.check_in DESC
    """, (tourist_id,))
    bookings = cursor.fetchall()
    cursor.close()
    conn.close()

    for booking in bookings:
        if isinstance(booking["created_at"], datetime):
            booking["created_at"] = booking["created_at"].astimezone(timezone("UTC")).isoformat()

    return jsonify(bookings)



@booking_bp.route('/eco_points/<int:tourist_id>/transactions', methods=['GET'])
def get_transactions(tourist_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, points, type, booking_id, description, created_at
        FROM eco_points_transactions
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 200
    """, (tourist_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    for r in rows:
        if isinstance(r.get('created_at'), datetime):
            r['created_at'] = r['created_at'].isoformat()
    return jsonify(rows)
