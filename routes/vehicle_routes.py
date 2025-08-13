# routes/vehicle_routes.py
from flask import Blueprint, request, jsonify
from models.vehicle import Vehicle
from models.user import User
from functools import wraps
import cloudinary.uploader
from datetime import datetime
from models.db import get_connection

vehicle_bp = Blueprint('vehicle', __name__)

# Helper: auth decorator
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user_id = request.headers.get("X-USER-ID")
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Replace with your actual database query
        # This is just a placeholder - implement your actual user lookup
        user_data = get_user_from_db(user_id)  # You'll need to implement this
        if not user_data:
            return jsonify({"error": "Unauthorized"}), 401
            
        request.current_user = User(**user_data)
        return f(*args, **kwargs)
    return wrapper

# Database helper functions (implement these according to your DB)
def get_user_from_db(user_id):
    """Implement your actual user lookup from database"""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM user_account WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    connection.close()
    return user

def save_vehicle_to_db(vehicle):
    """Implement your actual vehicle save to database"""
    connection = get_connection()
    cursor = connection.cursor()
    if vehicle.id:
        # Update existing vehicle
        query = """UPDATE vehicle SET 
                   owner_id=%s, model_name=%s, plate_number=%s, 
                   rate_per_km=%s, points_per_km=%s, proof_path=%s,
                   vehicle_type=%s, approval_status=%s, updated_at=%s
                   WHERE id=%s"""
        cursor.execute(query, (
            vehicle.owner_id, vehicle.model_name, vehicle.plate_number,
            vehicle.rate_per_km, vehicle.points_per_km, vehicle.proof_path,
            vehicle.vehicle_type, vehicle.approval_status, datetime.utcnow(),
            vehicle.id
        ))
    else:
        # Insert new vehicle
        query = """INSERT INTO vehicle 
                   (owner_id, model_name, plate_number, rate_per_km, 
                   points_per_km, proof_path, vehicle_type, approval_status, 
                   created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"""
        cursor.execute(query, (
            vehicle.owner_id, vehicle.model_name, vehicle.plate_number,
            vehicle.rate_per_km, vehicle.points_per_km, vehicle.proof_path,
            vehicle.vehicle_type, vehicle.approval_status, 
            vehicle.created_at, vehicle.updated_at
        ))
        vehicle.id = cursor.fetchone()[0]
    connection.commit()
    connection.close()

def get_vehicles_by_owner(owner_id):
    """Implement your actual vehicle lookup by owner"""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM vehicle WHERE owner_id = %s", (owner_id,))
    vehicles = cursor.fetchall()
    connection.close()
    return [Vehicle.from_dict(dict(zip([
        'id', 'owner_id', 'model_name', 'plate_number', 'rate_per_km',
        'points_per_km', 'proof_path', 'vehicle_type', 'approval_status',
        'created_at', 'updated_at'
    ], vehicle))) for vehicle in vehicles]

def get_pending_vehicles():
    """Implement your actual pending vehicles lookup"""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM vehicle WHERE approval_status = 'pending'")
    vehicles = cursor.fetchall()
    connection.close()
    return [Vehicle.from_dict(dict(zip([
        'id', 'owner_id', 'model_name', 'plate_number', 'rate_per_km',
        'points_per_km', 'proof_path', 'vehicle_type', 'approval_status',
        'created_at', 'updated_at'
    ], vehicle))) for vehicle in vehicles]

def get_vehicle_by_id(vehicle_id):
    """Implement your actual vehicle lookup by ID"""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM vehicle WHERE id = %s", (vehicle_id,))
    vehicle = cursor.fetchone()
    connection.close()
    if vehicle:
        return Vehicle.from_dict(dict(zip([
            'id', 'owner_id', 'model_name', 'plate_number', 'rate_per_km',
            'points_per_km', 'proof_path', 'vehicle_type', 'approval_status',
            'created_at', 'updated_at'
        ], vehicle)))
    return None

# Routes
@vehicle_bp.route('/vehicles', methods=['POST'])
def register_vehicle():
    user = request.current_user
    if user.role != 'vehicle_owner':
        return jsonify({"error": "Only owners can register vehicles"}), 403

    data = request.form
    proof_file = request.files.get('proof_file')
    proof_url = None

    if proof_file:
        result = cloudinary.uploader.upload(
            proof_file,
            folder="vehicle_proofs",
            resource_type="auto"
        )
        proof_url = result.get('secure_url')

    # Owner does NOT set price or points here
    vehicle = Vehicle(
        owner_id=user.id,
        model_name=data.get('model_name'),
        plate_number=data.get('plate_number'),
        rate_per_km=None,
        points_per_km=None,
        proof_path=proof_url,
        approval_status='pending',
        vehicle_type=None  # To be set by admin
    )

    save_vehicle_to_db(vehicle)
    return jsonify({
        "message": "Vehicle submitted for admin approval",
        "vehicle": vehicle.to_dict()
    }), 201

@vehicle_bp.route('/owner/vehicles', methods=['GET'])
def owner_vehicles():
    user = request.current_user
    if user.role != 'vehicle_owner':
        return jsonify([]), 200

    vehicles = get_vehicles_by_owner(user.id)
    return jsonify([v.to_dict() for v in vehicles]), 200

@vehicle_bp.route('/admin/vehicles/pending', methods=['GET'])
def admin_pending_vehicles():
    if request.current_user.role != 'admin':
        return jsonify({"error": "Only admin"}), 403

    pending_vehicles = get_pending_vehicles()
    result = []
    
    for vehicle in pending_vehicles:
        owner_data = get_user_from_db(vehicle.owner_id)
        owner = User(**owner_data) if owner_data else None
        result.append({
            **vehicle.to_dict(),
            "owner_name": owner.name if owner else None
        })
    
    return jsonify(result), 200

@vehicle_bp.route('/admin/vehicles/<int:vehicle_id>/review', methods=['POST'])
def admin_review_vehicle(vehicle_id):
    if request.current_user.role != 'admin':
        return jsonify({"error": "Only admin"}), 403

    data = request.json
    action = data.get('action')  # 'approve' or 'reject'
    vehicle_type = data.get('vehicle_type')  # EV/Hybrid/Normal if approving

    vehicle = get_vehicle_by_id(vehicle_id)
    if not vehicle:
        return jsonify({"error": "Not found"}), 404

    if action == 'approve':
        if vehicle_type not in ('EV', 'Hybrid', 'Normal'):
            return jsonify({"error": "vehicle_type required"}), 400
        vehicle.approval_status = 'approved'
        vehicle.vehicle_type = vehicle_type
    else:
        vehicle.approval_status = 'rejected'

    vehicle.updated_at = datetime.utcnow()
    save_vehicle_to_db(vehicle)
    return jsonify({"message": "done"}), 200