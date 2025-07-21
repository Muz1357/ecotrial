from flask import Blueprint, request, jsonify
from models.booking import Booking

booking_bp = Blueprint('booking', __name__)

@booking_bp.route('/bookings', methods=['POST'])
def create_booking():
    data = request.json
    if not data:
        return jsonify({"error": "Missing JSON data"}), 400

    booking = Booking(
        listing_id=data.get('listing_id'),
        tourist_id=data.get('tourist_id'),
        booking_date=data.get('booking_date')
    )
    booking.save()
    return jsonify({"message": "Booking created successfully"}), 201
