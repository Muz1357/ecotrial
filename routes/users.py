from flask import Blueprint, request, jsonify
from models.db import get_connection
from werkzeug.security import generate_password_hash

user_bp = Blueprint('user', __name__)

# --- Update user ---
@user_bp.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON data"}), 400

    username = data.get('username')
    password = data.get('password')

    if not username and not password:
        return jsonify({"error": "No fields to update"}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()

        if username:
            cursor.execute("UPDATE users SET username=%s WHERE id=%s", (username, user_id))

        if password:
            hashed_pw = generate_password_hash(password)
            cursor.execute("UPDATE users SET password=%s WHERE id=%s", (hashed_pw, user_id))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "User updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": "Failed to update user", "details": str(e)}), 500


# --- Delete user ---
@user_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "User deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": "Failed to delete user", "details": str(e)}), 500
