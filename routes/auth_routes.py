from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import cloudinary.uploader
from models.user import User
from config import ALLOWED_EXTENSIONS

auth_bp = Blueprint('auth', __name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@auth_bp.route('/register', methods=['POST'])
def register():
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role')
    business_name = request.form.get('business_name')
    proof_file = request.files.get('proof')

    if not all([name, email, password, role]):
        return jsonify({'message': 'Missing required fields'}), 400

    # Check if email already exists
    if User.find_by_email(email):
        return jsonify({'message': 'Email already registered'}), 400

    hashed_password = generate_password_hash(password)

    proof_path = None
    if role == 'business_owner':
        if not business_name or not proof_file or not allowed_file(proof_file.filename):
            return jsonify({'message': 'Business name and proof file are required'}), 400
        upload_result = cloudinary.uploader.upload(proof_file)
        proof_path = upload_result['secure_url']

    # Create new user
    new_user = User.create(
        name=name,
        email=email,
        password=hashed_password,
        role=role,
        is_approved=0,
        business_name=business_name if role == 'business_owner' else None,
        proof_path=proof_path
    )

    return jsonify({'message': 'Registered successfully, pending admin approval'}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.find_by_email(email)
    if not user or not check_password_hash(user.password, password):
        return jsonify({'message': 'Invalid email or password'}), 401

    if user.role == 'business_owner' and not user.is_approved:
        return jsonify({'message': 'Account not yet approved by admin'}), 403

    return jsonify({
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'role': user.role,
        'is_approved': user.is_approved,
        'proof_path': user.proof_path,
        'business_name': user.business_name
    }), 200
