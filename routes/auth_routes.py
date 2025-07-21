from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
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

    # Validate required fields
    if not name or not email or not password or not role:
        return jsonify({"error": "Missing required fields"}), 400

    if User.find_by_email(email):
        return jsonify({"error": "Email already registered"}), 400

    business_name = None
    proof_url = None
    if role == 'business_owner':
        business_name = request.form.get('business_name')
        proof_file = request.files.get('proof')

        if not business_name or not proof_file:
            return jsonify({"error": "Business name and proof are required"}), 400

        if not allowed_file(proof_file.filename):
            return jsonify({"error": "File type not allowed"}), 400

        # Upload proof to Cloudinary
        upload_result = cloudinary.uploader.upload(proof_file)
        proof_url = upload_result.get('secure_url')

    hashed_password = generate_password_hash(password)
    user = User(
        name=name,
        email=email,
        password=hashed_password,
        role=role,
        is_approved=False if role == 'business_owner' else True,
        business_name=business_name,
        proof_path=proof_url  # save URL instead of local path
    )
    user.save()

    return jsonify({"message": "User registered successfully"}), 201
