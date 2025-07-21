from flask import Blueprint, request, jsonify
from models.booking import Booking

booking_bp = Blueprint('booking', __name__)

@booking_bp.route('/bookings', methods=['POST'])
def create_booking():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON data"}), 400

    listing_id = data.get('listing_id')
    tourist_id = data.get('tourist_id')
    booking_date = data.get('booking_date')

    if not listing_id or not tourist_id or not booking_date:
        return jsonify({"error": "Missing required booking fields"}), 400

    booking = Booking(
        listing_id=listing_id,
        tourist_id=tourist_id,
        booking_date=booking_date
    )
    booking.save()

    return jsonify({"message": "Booking created successfully"}), 201
