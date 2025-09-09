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

# Get all listings of a business owner
@business_bp.route('/business/listings/<int:user_id>', methods=['GET'])
def get_listings(user_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM listing WHERE user_id = %s", (user_id,))
    listings = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(listings)

# Edit a listing
@business_bp.route('/listing/<int:listing_id>', methods=['PUT'])
def edit_listing(listing_id):
    data = request.json
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE listing SET title=%s, description=%s, price=%s, rooms_available=%s, room_details=%s, location=%s
        WHERE id=%s
    """, (
        data.get('title'),
        data.get('description'),
        data.get('price'),
        data.get('rooms_available'),
        data.get('room_details'),
        data.get('location'),
        listing_id
    ))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Listing updated successfully"})

# Delete a listing
@business_bp.route('/listing/<int:listing_id>', methods=['DELETE'])
def delete_listing(listing_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM listing WHERE id=%s", (listing_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Listing deleted successfully"})

# Get all experiences of a business owner
@business_bp.route('/business/experiences/<int:user_id>', methods=['GET'])
def get_experiences(user_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT ce.* FROM community_experience ce
        JOIN user_account ua ON ua.id=%s
        WHERE ce.id IN (
            SELECT experience_id FROM community_booking WHERE user_id=%s
        )
    """, (user_id, user_id))
    experiences = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(experiences)

# Edit experience
@business_bp.route('/experience/<int:experience_id>', methods=['PUT'])
def edit_experience(experience_id):
    data = request.json
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE community_experience
        SET title=%s, description=%s, price=%s, location=%s
        WHERE id=%s
    """, (
        data.get('title'),
        data.get('description'),
        data.get('price'),
        data.get('location'),
        experience_id
    ))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Experience updated successfully"})

# Delete experience
@business_bp.route('/experience/<int:experience_id>', methods=['DELETE'])
def delete_experience(experience_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM community_experience WHERE id=%s", (experience_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Experience deleted successfully"})