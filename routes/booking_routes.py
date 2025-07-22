from flask import Blueprint, request, jsonify
from models.booking import Booking

booking_bp = Blueprint('booking', __name__)

booking_bp = Blueprint('booking', __name__)

@booking_bp.route('/bookings', methods=['POST'])
def create_booking():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON data"}), 400

    listing_id = data.get('listing_id')
    tourist_id = data.get('tourist_id')
    check_in = data.get('check_in')
    check_out = data.get('check_out')

    if not listing_id or not tourist_id or not check_in or not check_out:
        return jsonify({"error": "Missing required booking fields"}), 400

    # Optional: validate date formats, check that check_out > check_in here

    booking = Booking(
        listing_id=listing_id,
        tourist_id=tourist_id,
        check_in=check_in,
        check_out=check_out
    )
    booking.save()

    return jsonify({"message": "Booking created successfully"}), 201