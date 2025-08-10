from flask import Blueprint, request, jsonify
from models.db import get_connection
from werkzeug.security import generate_password_hash
import cloudinary.uploader

user_bp = Blueprint('user', __name__)

@user_bp.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    try:
        name = request.form.get('name')
        password = request.form.get('password')
        email = request.form.get('email')
        profile_image_url = None

        # Handle profile image upload
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            upload_result = cloudinary.uploader.upload(file, folder="profile_images")
            profile_image_url = upload_result.get('secure_url')

        conn = get_connection()
        cursor = conn.cursor()

        if name:
            cursor.execute("UPDATE user_account SET name=%s WHERE id=%s", (name, user_id))

        if password:
            hashed_pw = generate_password_hash(password)
            cursor.execute("UPDATE user_account SET password=%s WHERE id=%s", (hashed_pw, user_id))

        if email:
            cursor.execute("UPDATE user_account SET email=%s WHERE id=%s", (email, user_id))

        if profile_image_url:
            cursor.execute("UPDATE user_account SET profile_image=%s WHERE id=%s", (profile_image_url, user_id))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "message": "User updated successfully",
            "profile_image": profile_image_url
        }), 200

    except Exception as e:
        return jsonify({"error": "Failed to update user", "details": str(e)}), 500



# --- Delete user ---
@user_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM user_account WHERE id=%s", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "User deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": "Failed to delete user", "details": str(e)}), 500
