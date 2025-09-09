from flask import jsonify, Blueprint, request
from models.db import get_connection
import cloudinary
import cloudinary.uploader

business_bp = Blueprint('business', __name__)

# ------- Business Report -------
@business_bp.route('/report/<int:business_owner_id>', methods=['GET'])
def business_report(business_owner_id):
    conn = get_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    cursor = conn.cursor(dictionary=True)

    # Owner info
    cursor.execute("""
        SELECT id, name, business_name, profile_image
        FROM user_account WHERE id = %s
    """, (business_owner_id,))
    owner = cursor.fetchone()

    # Listings
    cursor.execute("""
    SELECT id, title, price, rooms_available, is_approved, location, image_path
        FROM listing WHERE user_id = %s
    """, (business_owner_id,))
    listings = cursor.fetchall()

    # Booking summary
    cursor.execute("""
        SELECT 
            COUNT(*) AS total_bookings,
            SUM(is_cancelled=1) AS cancelled,
            SUM(is_completed=1) AS completed,
            SUM(is_released=1) AS released,
            COALESCE(SUM(CAST(l.price AS DECIMAL(10,2))),0) AS revenue
        FROM booking b
        JOIN listing l ON b.listing_id = l.id
        WHERE l.user_id = %s
    """, (business_owner_id,))
    booking_summary = cursor.fetchone()

    # Room utilization
    cursor.execute("""
        SELECT 
            COALESCE(SUM(ra.rooms_booked),0) AS total_rooms_booked,
            COALESCE(SUM(l.rooms_available),0) AS total_rooms_available
        FROM room_availability ra
        JOIN listing l ON ra.listing_id = l.id
        WHERE l.user_id = %s
    """, (business_owner_id,))
    room_data = cursor.fetchone()

    # Community experience summary
    cursor.execute("""
        SELECT 
            COUNT(*) AS total_community_bookings,
            SUM(status='cancelled') AS cancelled_community,
            SUM(status='finished') AS finished_community
        FROM community_booking cb
        JOIN community_experience ce ON cb.experience_id = ce.id
        WHERE ce.user_id = %s
    """, (business_owner_id,))
    community_summary = cursor.fetchone()

    cursor.close()
    conn.close()

    return jsonify({
        "owner": owner,
        "listings": listings,
        "booking_summary": booking_summary,
        "room_data": room_data,
        "community_summary": community_summary
    })

# ------- Listings GET (owner) -------
@business_bp.route('/listings/<int:business_owner_id>', methods=['GET'])
def get_listings(business_owner_id):
    conn = get_connection()
    if not conn:
        return jsonify({"error": "DB connection failed"}), 500
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT id, title, price, rooms_available, is_approved, location, image_path
        FROM listing WHERE user_id = %s
    """, (business_owner_id,))
    listings = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify({"listings": listings}), 200

# ------- Experiences GET (owner) -------
@business_bp.route('/experiences/<int:business_owner_id>', methods=['GET'])
def get_experiences(business_owner_id):
    conn = get_connection()
    if not conn:
        return jsonify({"error": "DB connection failed"}), 500
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT id, title, description, image_path, is_approved
        FROM community_experience
        WHERE user_id = %s
    """, (business_owner_id,))
    experiences = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify({"experiences": experiences}), 200

# ------- Delete Listing -------
@business_bp.route('/listing/<int:listing_id>', methods=['DELETE'])
def delete_listing(listing_id):
    conn = get_connection()
    if not conn:
        return jsonify({"error": "DB connection failed"}), 500
    cur = conn.cursor()
    cur.execute("DELETE FROM listing WHERE id = %s", (listing_id,))
    conn.commit()
    affected = cur.rowcount
    cur.close()
    conn.close()
    if affected:
        return jsonify({"success": True}), 200
    return jsonify({"error": "Not found"}), 404

# ------- Delete Experience -------
@business_bp.route('/experience/<int:exp_id>', methods=['DELETE'])
def delete_experience(exp_id):
    conn = get_connection()
    if not conn:
        return jsonify({"error": "DB connection failed"}), 500
    cur = conn.cursor()
    cur.execute("DELETE FROM community_experience WHERE id = %s", (exp_id,))
    conn.commit()
    affected = cur.rowcount
    cur.close()
    conn.close()
    if affected:
        return jsonify({"success": True}), 200
    return jsonify({"error": "Not found"}), 404

# ------- Update Listing (JSON fields) -------
@business_bp.route('/listing/<int:listing_id>', methods=['PUT'])
def update_listing(listing_id):
    payload = request.get_json() or {}
    allowed = ['title', 'price', 'rooms_available', 'location', 'is_approved']
    fields = []
    vals = []
    for k in allowed:
        if k in payload:
            fields.append(f"{k} = %s")
            vals.append(payload[k])
    if not fields:
        return jsonify({"error": "No valid fields provided"}), 400

    conn = get_connection()
    if not conn:
        return jsonify({"error": "DB connection failed"}), 500
    cur = conn.cursor()
    sql = f"UPDATE listing SET {', '.join(fields)} WHERE id = %s"
    vals.append(listing_id)
    cur.execute(sql, tuple(vals))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"success": True}), 200

# ------- Update Experience (JSON fields) -------
@business_bp.route('/experience/<int:exp_id>', methods=['PUT'])
def update_experience(exp_id):
    payload = request.get_json() or {}
    allowed = ['title', 'description', 'is_approved']
    fields = []
    vals = []
    for k in allowed:
        if k in payload:
            fields.append(f"{k} = %s")
            vals.append(payload[k])
    if not fields:
        return jsonify({"error": "No valid fields provided"}), 400

    conn = get_connection()
    if not conn:
        return jsonify({"error": "DB connection failed"}), 500
    cur = conn.cursor()
    sql = f"UPDATE community_experience SET {', '.join(fields)} WHERE id = %s"
    vals.append(exp_id)
    cur.execute(sql, tuple(vals))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"success": True}), 200