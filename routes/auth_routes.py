from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
from models.user import User
from config import ALLOWED_EXTENSIONS, UPLOAD_FOLDER

auth_bp = Blueprint('auth', __name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------- REGISTER ----------
@auth_bp.route('/register', methods=['POST'])
def register():
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role')

    # Validate required fields
    if not name or not email or not password or not role:
        return jsonify({"error": "Missing required fields"}), 400

    if User.find_by_email(email):
        return jsonify({"error": "Email already registered"}), 400

    # Handle business owner proof upload
    business_name = None
    proof_path = None
    if role == 'business_owner':
        business_name = request.form.get('business_name')
        proof_file = request.files.get('proof')

        if not business_name or not proof_file:
            return jsonify({"error": "Business name and proof are required"}), 400

        if not allowed_file(proof_file.filename):
            return jsonify({"error": "File type not allowed"}), 400

        filename = secure_filename(proof_file.filename)
        proof_path = os.path.join(UPLOAD_FOLDER, filename)
        proof_file.save(proof_path)

    # Save user
    hashed_password = generate_password_hash(password)
    user = User(
        name=name,
        email=email,
        password=hashed_password,
        role=role,
        is_approved=False if role == 'business_owner' else True,
        business_name=business_name,
        proof_path=proof_path
    )
    user.save()

    return jsonify({"message": "User registered successfully"}), 201

# ---------- LOGIN ----------
@auth_bp.route('/login', methods=['POST'])
def loginUser():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.find_by_email(email)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Since user is a dict, get password via key
    hashed_password = user.get('password')
    if not check_password_hash(hashed_password, password):
        return jsonify({'error': 'Invalid password'}), 401

    return jsonify({
        'id': user.get('id'),
        'name': user.get('name'),
        'email': user.get('email'),
        'role': user.get('role'),
        'is_approved': user.get('is_approved'),
    }), 200