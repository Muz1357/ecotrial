from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from models.user import User
from models.db import get_connection

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role')
    business_name = request.form.get('business_name')

    if not all([name, email, password, role]):
        return jsonify({'message': 'Missing required fields'}), 400

    # Check if email already exists
    if User.find_by_email(email):
        return jsonify({'message': 'Email already registered'}), 400

    hashed_password = generate_password_hash(password)

    # Require business name for business owners
    if role == 'business_owner' and not business_name:
        return jsonify({'message': 'Business name is required for business owners'}), 400

    # Create new user (no proof or approval required)
    new_user = User.create(
        name=name,
        email=email,
        password=hashed_password,
        role=role,
        business_name=business_name if role == 'business_owner' else None
    )

    return jsonify({'message': 'Registered successfully'}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.find_by_email(email)
    if not user or not check_password_hash(user.password, password):
        return jsonify({'message': 'Invalid email or password'}), 401

    return jsonify({
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'role': user.role,
        'business_name': user.business_name
    }), 200


@auth_bp.route('/update_user/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    data = request.json
    name = data.get('name')
    password = data.get('password', None)

    if not name:
        return jsonify({"error": "Name is required"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    if password:
        hashed_password = generate_password_hash(password)
        cursor.execute(
            "UPDATE users SET name=%s, password=%s WHERE id=%s",
            (name, hashed_password, user_id)
        )
    else:
        cursor.execute(
            "UPDATE users SET name=%s WHERE id=%s",
            (name, user_id)
        )

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "User updated successfully"}), 200

# ❌ Delete User Account
@auth_bp.route('/delete_user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"message": "User deleted successfully"}), 200