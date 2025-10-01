from flask import jsonify, Blueprint, request
from models.db import get_connection
import cloudinary
import cloudinary.uploader
from datetime import datetime
import uuid


business_manage_bp = Blueprint('business_manage', __name__)


@business_manage_bp.route('/business/listings/<int:business_owner_id>', methods=['GET'])
def fetch_business_listings(business_owner_id):
    conn = get_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, title, description, image_path, is_approved, created_at, 
                   updated_at, price, currency, location, rooms_available, 
                   room_details, eco_cert_url, latitude, longitude
            FROM listing 
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (business_owner_id,))
        listings = cursor.fetchall()
        
        return jsonify(listings)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    finally:
        if conn:
            conn.close()


@business_manage_bp.route('/business/experiences/<int:business_owner_id>', methods=['GET'])
def fetch_business_experiences(business_owner_id):
    conn = get_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, title, description, location, latitude, longitude, price, 
                   image_path, certificate_path, weather_type, contact_info, 
                   approved as is_approved, created_at, updated_at
            FROM community_experience 
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (business_owner_id,))
        experiences = cursor.fetchall()
        
        return jsonify(experiences)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    finally:
        if conn:
            conn.close()


@business_manage_bp.route('/listing/<int:listing_id>', methods=['DELETE'])
def delete_listing(listing_id):
    conn = get_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = conn.cursor()
        
        
        cursor.execute("DELETE FROM room_availability WHERE listing_id = %s", (listing_id,))
        
       
        cursor.execute("DELETE FROM listing WHERE id = %s", (listing_id,))
        
        conn.commit()
        
        if cursor.rowcount > 0:
            return jsonify({"success": True, "message": "Listing deleted successfully"})
        else:
            return jsonify({"success": False, "message": "Listing not found"}), 404
    
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    
    finally:
        if conn:
            conn.close()


@business_manage_bp.route('/experience/<int:experience_id>', methods=['DELETE'])
def delete_experience(experience_id):
    conn = get_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = conn.cursor()
        
       
        cursor.execute("DELETE FROM community_booking WHERE experience_id = %s", (experience_id,))
        
       
        cursor.execute("DELETE FROM community_experience WHERE id = %s", (experience_id,))
        
        conn.commit()
        
        if cursor.rowcount > 0:
            return jsonify({"success": True, "message": "Experience deleted successfully"})
        else:
            return jsonify({"success": False, "message": "Experience not found"}), 404
    
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    
    finally:
        if conn:
            conn.close()


@business_manage_bp.route('/listing/<int:listing_id>', methods=['PUT'])
def update_listing(listing_id):
    conn = get_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        data = request.get_json()
        
        cursor = conn.cursor(dictionary=True)
        
        
        cursor.execute("SELECT * FROM listing WHERE id = %s", (listing_id,))
        listing = cursor.fetchone()
        
        if not listing:
            return jsonify({"error": "Listing not found"}), 404
        
        
        cursor.execute("""
            UPDATE listing 
            SET title = %s, description = %s, price = %s, rooms_available = %s, 
                room_details = %s, updated_at = %s
            WHERE id = %s
        """, (
            data.get('title', listing['title']),
            data.get('description', listing['description']),
            data.get('price', listing['price']),
            data.get('rooms_available', listing['rooms_available']),
            data.get('room_details', listing['room_details']),
            datetime.now(),
            listing_id
        ))
        
        conn.commit()
        
        return jsonify({"success": True, "message": "Listing updated successfully"})
    
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    
    finally:
        if conn:
            conn.close()


@business_manage_bp.route('/experience/<int:experience_id>', methods=['PUT'])
def update_experience(experience_id):
    conn = get_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        data = request.get_json()
        
        cursor = conn.cursor(dictionary=True)
        
        
        cursor.execute("SELECT * FROM community_experience WHERE id = %s", (experience_id,))
        experience = cursor.fetchone()
        
        if not experience:
            return jsonify({"error": "Experience not found"}), 404
        
      
        cursor.execute("""
            UPDATE community_experience 
            SET title = %s, description = %s, price = %s, contact_info = %s, updated_at = %s
            WHERE id = %s
        """, (
            data.get('title', experience['title']),
            data.get('description', experience['description']),
            data.get('price', experience['price']),
            data.get('contact_info', experience['contact_info']),
            datetime.now(),
            experience_id
        ))
        
        conn.commit()
        
        return jsonify({"success": True, "message": "Experience updated successfully"})
    
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    
    finally:
        if conn:
            conn.close()


@business_manage_bp.route('/listing/<int:listing_id>/image', methods=['POST'])
def upload_listing_image(listing_id):
    conn = get_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        
        if 'image' not in request.files:
            return jsonify({"error": "No image file provided"}), 400
        
        file = request.files['image']
        
        if file.filename == '':
            return jsonify({"error": "No image file selected"}), 400
        
        
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM listing WHERE id = %s", (listing_id,))
        listing = cursor.fetchone()
        
        if not listing:
            return jsonify({"error": "Listing not found"}), 404
        
        
        upload_result = cloudinary.uploader.upload(
            file,
            folder="listings",
            public_id=f"listing_{listing_id}_{uuid.uuid4().hex[:8]}",
            overwrite=True
        )
        
        
        cursor.execute("""
            UPDATE listing 
            SET image_path = %s, updated_at = %s
            WHERE id = %s
        """, (upload_result['secure_url'], datetime.now(), listing_id))
        
        conn.commit()
        
        return jsonify({
            "success": True, 
            "message": "Image uploaded successfully",
            "image_path": upload_result['secure_url']
        })
    
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    
    finally:
        if conn:
            conn.close()


@business_manage_bp.route('/experience/<int:experience_id>/image', methods=['POST'])
def upload_experience_image(experience_id):
    conn = get_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        
        if 'image' not in request.files:
            return jsonify({"error": "No image file provided"}), 400
        
        file = request.files['image']
        
        if file.filename == '':
            return jsonify({"error": "No image file selected"}), 400
        
       
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM community_experience WHERE id = %s", (experience_id,))
        experience = cursor.fetchone()
        
        if not experience:
            return jsonify({"error": "Experience not found"}), 404
        
        
        upload_result = cloudinary.uploader.upload(
            file,
            folder="community_experiences",
            public_id=f"experience_{experience_id}_{uuid.uuid4().hex[:8]}",
            overwrite=True
        )
        
        
        cursor.execute("""
            UPDATE community_experience 
            SET image_path = %s, updated_at = %s
            WHERE id = %s
        """, (upload_result['secure_url'], datetime.now(), experience_id))
        
        conn.commit()
        
        return jsonify({
            "success": True, 
            "message": "Image uploaded successfully",
            "image_path": upload_result['secure_url']
        })
    
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    
    finally:
        if conn:
            conn.close()