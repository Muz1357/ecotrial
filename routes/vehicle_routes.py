from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from models.vehicle import Vehicle
import os
from datetime import datetime


vehicle_bp = Blueprint('vehicles', __name__)

@vehicle_bp.route('/vehicles', methods=['POST'])
def register_vehicle(current_user):
    try:
        # Get form data
        model_name = request.form.get('model_name')
        plate_number = request.form.get('plate_number')
        vehicle_type = request.form.get('vehicle_type')
        
        if not all([model_name, plate_number, vehicle_type]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Handle file upload
        proof_file = None
        if 'proof_file' in request.files:
            file = request.files['proof_file']
            if file.filename != '':
                proof_file = file
        
        # Create vehicle
        result = Vehicle.create_vehicle(
            current_user['id'],
            model_name,
            plate_number,
            vehicle_type,
            proof_file
        )
        
        return jsonify(result), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@vehicle_bp.route('/vehicles/user/<int:user_id>', methods=['GET'])
def get_user_vehicles(current_user, user_id):
    # Verify the requesting user has access
    if not current_user['is_admin'] and current_user['id'] != user_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        vehicles = Vehicle.get_user_vehicles(user_id)
        return jsonify(vehicles), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@vehicle_bp.route('/vehicles/pending', methods=['GET'])
def get_pending_vehicles(current_admin):
    try:
        vehicles = Vehicle.get_pending_vehicles()
        return jsonify(vehicles), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@vehicle_bp.route('/vehicles/<int:vehicle_id>/approve', methods=['POST'])
def approve_vehicle(current_admin, vehicle_id):
    try:
        data = request.get_json()
        notes = data.get('notes', '')
        
        Vehicle.approve_vehicle(vehicle_id, current_admin['id'], notes)
        return jsonify({'message': 'Vehicle approved successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@vehicle_bp.route('/vehicles/<int:vehicle_id>/reject', methods=['POST'])
def reject_vehicle(current_admin, vehicle_id):
    try:
        data = request.get_json()
        notes = data.get('notes', '')
        
        Vehicle.reject_vehicle(vehicle_id, current_admin['id'], notes)
        return jsonify({'message': 'Vehicle rejected successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@vehicle_bp.route('/vehicle-types', methods=['GET'])
def get_vehicle_types():
    try:
        types = Vehicle.get_vehicle_types()
        return jsonify(types), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@vehicle_bp.route('/vehicle-types/<int:type_id>', methods=['PUT'])
def update_vehicle_type(current_admin, type_id):
    try:
        data = request.get_json()
        price_per_km = data.get('price_per_km')
        eco_points_rate = data.get('eco_points_rate')
        
        if price_per_km is None and eco_points_rate is None:
            return jsonify({'error': 'No updates provided'}), 400
            
        success = Vehicle.update_vehicle_type(
            type_id,
            price_per_km,
            eco_points_rate
        )
        
        if not success:
            return jsonify({'error': 'Vehicle type not found'}), 404
            
        return jsonify({'message': 'Vehicle type updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400