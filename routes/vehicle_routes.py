from flask import Blueprint, request, jsonify
from models.vehicle import Vehicle

vehicle_bp = Blueprint('vehicle', __name__)

# Tourist submits vehicle registration
@vehicle_bp.route('/vehicles', methods=['POST'])
def register_vehicle():
    data = request.json
    required = ['user_id', 'registration_number', 'brand', 'model', 'year']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400

    vehicle_id = Vehicle.create(
        data['user_id'],
        data['registration_number'],
        data['brand'],
        data['model'],
        data['year']
    )
    return jsonify({'message': 'Vehicle submitted for review', 'vehicle_id': vehicle_id}), 201


# Admin - View pending vehicles
@vehicle_bp.route('/vehicles/pending', methods=['GET'])
def get_pending_vehicles():
    vehicles = Vehicle.get_pending()
    return jsonify(vehicles), 200


# Admin - Approve vehicle and set type
@vehicle_bp.route('/vehicles/<int:vehicle_id>/approve', methods=['PUT'])
def approve_vehicle(vehicle_id):
    data = request.json
    if 'vehicle_type' not in data:
        return jsonify({'error': 'Vehicle type is required'}), 400
    if data['vehicle_type'] not in ['EV', 'Hybrid', 'Normal']:
        return jsonify({'error': 'Invalid vehicle type'}), 400

    Vehicle.approve(vehicle_id, data['vehicle_type'])
    return jsonify({'message': 'Vehicle approved'}), 200


# Admin - Update pricing for a vehicle type
@vehicle_bp.route('/vehicles/<vehicle_type>/pricing', methods=['PUT'])
def update_vehicle_pricing(vehicle_type):
    data = request.json
    if not all(k in data for k in ['price_per_km', 'eco_points_per_km']):
        return jsonify({'error': 'Missing pricing fields'}), 400

    Vehicle.update_pricing(vehicle_type, data['price_per_km'], data['eco_points_per_km'])
    return jsonify({'message': 'Pricing updated'}), 200


# Get all vehicle pricing
@vehicle_bp.route('/pricing', methods=['GET'])
def get_vehicle_pricing():
    pricing = Vehicle.get_pricing()
    return jsonify(pricing), 200
