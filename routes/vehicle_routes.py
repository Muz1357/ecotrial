from flask import Blueprint, request, jsonify
from models.vehicle import Vehicle
import os
import cloudinary.uploader

vehicle_bp = Blueprint('vehicle', __name__)

# Submit vehicle (User)
@vehicle_bp.route('/vehicles', methods=['POST'])
def submit_vehicle():
    try:
        user_id = request.form.get('user_id')
        model_name = request.form.get('model_name')
        plate_number = request.form.get('plate_number')
        vehicle_type = request.form.get('vehicle_type')

        proof_file = None
        if 'proof_file' in request.files:
            upload_result = cloudinary.uploader.upload(
                request.files['proof_file'],
                folder="vehicle_proofs"
            )
            proof_file = upload_result['secure_url']

        Vehicle.create(user_id, model_name, plate_number, vehicle_type, proof_file)
        return jsonify({"message": "Vehicle submitted for admin review"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Get pending vehicles (Admin)
@vehicle_bp.route('/vehicles/pending', methods=['GET'])
def get_pending_vehicles():
    try:
        vehicles = Vehicle.get_all_pending()
        return jsonify(vehicles), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Approve vehicle (Admin)
@vehicle_bp.route('/vehicles/<int:vehicle_id>/approve', methods=['PUT'])
def approve_vehicle(vehicle_id):
    try:
        data = request.get_json()
        eco_category = data.get('eco_category')
        price_per_km = data.get('price_per_km')
        eco_points_per_km = data.get('eco_points_per_km')

        Vehicle.approve(vehicle_id, eco_category, price_per_km, eco_points_per_km)
        return jsonify({"message": "Vehicle approved successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Update price and points (Admin)
@vehicle_bp.route('/vehicles/<int:vehicle_id>/pricing', methods=['PUT'])
def update_pricing(vehicle_id):
    try:
        data = request.get_json()
        price_per_km = data.get('price_per_km')
        eco_points_per_km = data.get('eco_points_per_km')

        Vehicle.update_pricing(vehicle_id, price_per_km, eco_points_per_km)
        return jsonify({"message": "Pricing updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
