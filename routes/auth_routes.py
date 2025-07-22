from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import cloudinary.uploader
from models.user import User
from config import ALLOWED_EXTENSIONS

auth_bp = Blueprint('auth', __name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')

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
                return jsonify({"error": "Business name and proof file are required"}), 400

            print(f"Received file: {proof_file.filename}")
            print(f"Allowed file extensions: {ALLOWED_EXTENSIONS}")
            print(f"File allowed? {allowed_file(proof_file.filename)}")

            if not allowed_file(proof_file.filename):
                return jsonify({"error": "File type not allowed"}), 400

            try:
                upload_result = cloudinary.uploader.upload(proof_file)
                proof_url = upload_result.get('secure_url')
            except Exception as e:
                print(f"Cloudinary upload failed: {e}")
                return jsonify({"error": "Failed to upload proof file"}), 500

        hashed_password = generate_password_hash(password)

        user = User(
            name=name,
            email=email,
            password=hashed_password,
            role=role,
            is_approved=False if role == 'business_owner' else True,
            business_name=business_name,
            proof_path=proof_url
        )

        user.save()

        return jsonify({"message": "User registered successfully"}), 201

    except Exception as e:
        print(f"Register route error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({'error': 'Missing fields'}), 400

        user = User.find_by_email(email)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        print("[DEBUG] Hashed:", user.password)
        print("[DEBUG] Input:", password)

        if not check_password_hash(user.password, password):
            return jsonify({'error': 'Invalid credentials'}), 401

        if user.role == 'business_owner' and not user.is_approved:
            return jsonify({'error': 'Business owner not approved yet'}), 403

        return jsonify({
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role,
            'is_approved': user.is_approved,
            'proof_path': user.proof_path,
            'business_name': user.business_name
        }), 200

    except Exception as e:
        print("[ERROR] Login failed:", str(e))  # This prints in the terminal
        return jsonify({'error': 'Internal server error'}), 500