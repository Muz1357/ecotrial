from flask import Blueprint, request, jsonify
from models.booking import Booking
from datetime import datetime
from dateutil import parser

from models.listing import Listing

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

    # Validate dates
    try:
        check_in_date = parser.isoparse(check_in)
        check_out_date = parser.isoparse(check_out)
        if check_out_date <= check_in_date:
            return jsonify({"error": "Check-out must be after check-in"}), 400
    except Exception:
        return jsonify({"error": "Invalid date format"}), 400

    # ✅ Check room availability
    listing = Listing.get_listing_by_id(listing_id)
    if not listing:
        return jsonify({'error': 'Listing not found'}), 404

    if listing['rooms_available'] <= 0:
        return jsonify({'error': 'No rooms available'}), 400

    # ✅ Create booking and update room count
    booking = Booking(
        listing_id=listing_id,
        tourist_id=tourist_id,
        check_in=check_in,
        check_out=check_out
    )
    booking.save()

    listing.rooms_available -= 1
    listing.save()

    return jsonify({"message": "Booking created successfully"}), 201
