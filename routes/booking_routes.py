from flask import Blueprint, request, jsonify
from models.booking import Booking
from models.listing import Listing
from datetime import datetime, timedelta
from dateutil import parser
from models.db import get_connection

booking_bp = Blueprint('booking', __name__)

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

    if not listing_id or not tourist_id or not check_in or not check_out:
        return jsonify({"error": "Missing required booking fields"}), 400

    # ✅ Parse and validate dates
    try:
        check_in_date = parser.isoparse(check_in).date()
        check_out_date = parser.isoparse(check_out).date()
        if check_out_date <= check_in_date:
            return jsonify({"error": "Check-out must be after check-in"}), 400
    except Exception:
        return jsonify({"error": "Invalid date format"}), 400

    # ✅ Get listing and total room count
    listing = Listing.get_listing_by_id(listing_id)
    if not listing:
        return jsonify({'error': 'Listing not found'}), 404

    total_rooms = listing['rooms_available']

    # ✅ Check availability for each day
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

    # ✅ All dates are available: create booking
    booking = Booking(
        listing_id=listing_id,
        tourist_id=tourist_id,
        check_in=check_in_date,
        check_out=check_out_date
    )
    booking.save()

    # ✅ Update room_availability table for each date
    current_date = check_in_date
    while current_date < check_out_date:
        cursor.execute("""
            INSERT INTO room_availability (listing_id, date, rooms_booked)
            VALUES (%s, %s, 1)
            ON DUPLICATE KEY UPDATE rooms_booked = rooms_booked + 1
        """, (listing_id, current_date))
        current_date += timedelta(days=1)

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Booking created successfully"}), 201

@booking_bp.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
def cancel_booking(booking_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # ⏳ Fetch booking and validate cancellation window
    cursor.execute("SELECT * FROM booking WHERE id = %s AND is_cancelled = FALSE", (booking_id,))
    booking = cursor.fetchone()

    if not booking:
        return jsonify({"error": "Booking not found or already cancelled"}), 404

    booking_time = booking['booking_time']  
    now = datetime.now()

    
    if (now - booking_time).total_seconds() > 3 * 3600:
        return jsonify({"error": "Cancellation window expired (3 hours)."}), 403

    
    cursor.execute("UPDATE booking SET is_cancelled = TRUE WHERE id = %s", (booking_id,))

    check_in = booking['check_in']
    check_out = booking['check_out']
    listing_id = booking['listing_id']

    current_date = check_in
    while current_date < check_out:
        cursor.execute("""
            UPDATE room_availability 
            SET rooms_booked = GREATEST(rooms_booked - 1, 0)
            WHERE listing_id = %s AND date = %s
        """, (listing_id, current_date))
        current_date += timedelta(days=1)

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Booking cancelled successfully"}), 200


@booking_bp.route('/bookings/<int:tourist_id>', methods=['GET'])
def get_user_bookings(tourist_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT b.id, l.title, b.check_in, b.check_out, b.is_cancelled, b.booking_time
        FROM booking b
        JOIN listing l ON b.listing_id = l.id
        WHERE b.tourist_id = %s
        ORDER BY b.check_in DESC
    """, (tourist_id,))
    bookings = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(bookings)
