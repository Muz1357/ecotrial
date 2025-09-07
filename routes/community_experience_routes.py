from flask import Blueprint, request, jsonify
import pytz
from models.community_experience import CommunityExperience
from datetime import datetime, timedelta
import os, cloudinary.uploader, requests
from models.db import get_connection 
from math import radians, cos, sin, asin, sqrt
from models.eco_points import EcoPoints

community_bp = Blueprint("community_experience", __name__)

# Google Maps API Key
GOOGLE_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', 'AIzaSyA0kovojziyFywE0eF1mnMJdJnubZCX6Hs')

# Utility: haversine distance
def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))  # km

# Utility: geocode location string
def geocode_location(title, location_name):
    if not GOOGLE_API_KEY:
        raise ValueError("Google Maps API key not configured")

    full_address = f"{title}, {location_name}"
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": full_address, "key": GOOGLE_API_KEY}
    res = requests.get(url, params=params).json()

    if res.get("status") != "OK" or not res.get("results"):
        return None, None

    coords = res["results"][0]["geometry"]["location"]
    return coords["lat"], coords["lng"]

# --- Create experience ---
@community_bp.route("/community-experiences", methods=["POST"])
def create_experience():
    try:
        title = request.form.get("title")
        location_name = request.form.get("location")

        if not title or not location_name:
            return jsonify({"error": "title and location required"}), 400

        # Geocode the location
        latitude, longitude = geocode_location(title, location_name)
        if latitude is None or longitude is None:
            return jsonify({"error": "Could not geocode location"}), 400

        # Image upload
        image_path = None
        if "image" in request.files:
            file = request.files["image"]
            upload_res = cloudinary.uploader.upload(file, folder="community_experiences")
            image_path = upload_res.get("secure_url")

        # Certificate upload
        certificate_path = None
        if "eco_cert" in request.files:
            file = request.files["eco_cert"]
            upload_res = cloudinary.uploader.upload(file, folder="community_experiences/certificates")
            certificate_path = upload_res.get("secure_url")

        # Save to DB
        exp_id = CommunityExperience.create({
            "title": title,
            "description": request.form.get("description"),
            "location": location_name,
            "latitude": latitude,
            "longitude": longitude,
            "price": request.form.get("price"),
            "image_path": image_path,
            "certificate_path": certificate_path,
            "weather_type": request.form.get("weather_type") or "Both",
            "contact_info": request.form.get("contact_info"),
        })

        return jsonify({"id": exp_id, "message": "Experience created"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- List experiences ---
@community_bp.route("/community-experiences", methods=["GET"])
def list_experiences():
    only_approved = request.args.get("approved", "true").lower() == "true"
    items = CommunityExperience.get_all(only_approved=only_approved)
    return jsonify(items)

# --- Get one ---
@community_bp.route("/community-experiences/<int:exp_id>", methods=["GET"])
def get_experience(exp_id):
    exp = CommunityExperience.get_by_id(exp_id)
    if not exp or not exp.approved:
        return jsonify({"error": "Not found"}), 404
    return jsonify(exp.to_dict())

# --- Nearby experiences ---
@community_bp.route("/community-experiences/nearby", methods=["GET"])
def nearby_experiences():
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    radius = request.args.get("radius_km", type=float, default=5)
    weather = request.args.get("weather")

    if lat is None or lng is None:
        return jsonify({"error": "lat and lng required"}), 400

    items = CommunityExperience.get_all()
    results = []
    for i in items:
        if not i.get("latitude") or not i.get("longitude"):
            continue
        dist = haversine(lng, lat, float(i["longitude"]), float(i["latitude"]))
        if dist <= radius:
            if weather and i["weather_type"] not in ("Both", weather):
                continue
            i["distance_km"] = round(dist, 2)
            results.append(i)

    return jsonify(sorted(results, key=lambda x: x["distance_km"]))

@community_bp.route("/community-experiences/<int:exp_id>/book", methods=["POST"])
def book_experience(exp_id):
    data = request.get_json()
    user_id = data.get("user_id")
    redeem_points = data.get("redeem_points", 0)  # Get redeem points, default to 0
    
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Get experience price to calculate discount
        cursor.execute("SELECT price FROM community_experience WHERE id = %s", (exp_id,))
        experience = cursor.fetchone()
        experience_price = experience['price'] if experience else 0
        
        # Calculate discount (1 point = Rs.10)
        discount_amount = redeem_points * 10
        final_price = max(0, experience_price - discount_amount) if experience_price else 0

        # Check if user has enough points to redeem (points are in user_account table)
        if redeem_points > 0:
            cursor.execute("SELECT eco_points FROM user_account WHERE id = %s", (user_id,))
            user_account = cursor.fetchone()
            current_balance = user_account['eco_points'] if user_account else 0
            
            if current_balance < redeem_points:
                return jsonify({"error": "Insufficient eco points"}), 400

        # Use UTC-aware booking date
        booking_date_utc = datetime.now(pytz.utc).strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO community_booking (user_id, experience_id, booking_date, status, redeem_points, final_price)
            VALUES (%s, %s, %s, 'booked', %s, %s)
        """, (user_id, exp_id, booking_date_utc, redeem_points, final_price))
        booking_id = cursor.lastrowid

        # Deduct redeemed points if any (update user_account table)
        if redeem_points > 0:
            cursor.execute("""
                UPDATE user_account 
                SET eco_points = eco_points - %s 
                WHERE id = %s
            """, (redeem_points, user_id))
            
            # Log the redemption transaction
            cursor.execute("""
                INSERT INTO eco_points_transactions (user_id, points, type, booking_id, description)
                VALUES (%s, %s, 'redeem', %s, %s)
            """, (user_id, redeem_points, booking_id, f"Redeemed {redeem_points} points for community experience #{exp_id}"))

        # Award 10 eco points (update user_account table)
        points_earned = 10
        cursor.execute("""
            UPDATE user_account 
            SET eco_points = eco_points + %s 
            WHERE id = %s
        """, (points_earned, user_id))
        
        # Log the earning transaction
        cursor.execute("""
            INSERT INTO eco_points_transactions (user_id, points, type, booking_id, description)
            VALUES (%s, %s, 'earn', %s, %s)
        """, (user_id, points_earned, booking_id, f"Earned {points_earned} points for booking community experience #{exp_id}"))

        conn.commit()

        return jsonify({
            "booking_id": booking_id,
            "points_earned": points_earned,
            "points_redeemed": redeem_points,
            "discount_amount": discount_amount,
            "final_price": final_price,
            "booking_date": booking_date_utc,
            "message": "Booking successful"
        }), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Failed to book experience", "details": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# --- Approve / Unapprove experience ---
@community_bp.route("/admin/community-experiences/<int:exp_id>/approve", methods=["PUT"])
def approve_experience(exp_id):
    approved = request.json.get("approved", True)
    CommunityExperience.approve(exp_id, approved)
    return jsonify({"message": f"Experience {'approved' if approved else 'unapproved'}"})

@community_bp.route("/community-bookings/<int:booking_id>/cancel", methods=["POST"])
def cancel_community_booking(booking_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Fetch booking info
        cursor.execute(
            "SELECT * FROM community_booking WHERE id = %s AND status NOT IN ('cancelled', 'finished')",
            (booking_id,)
        )
        booking = cursor.fetchone()

        if not booking:
            return jsonify({"error": "Booking not found or already cancelled/finished"}), 404

        # Parse booking time (already UTC)
        booking_time = booking['booking_date']
        if isinstance(booking_time, str):
            try:
                booking_time = datetime.fromisoformat(booking_time.replace('Z', '+00:00'))
            except ValueError:
                booking_time = datetime.strptime(booking_time, "%Y-%m-%d %H:%M:%S")
        
        # Ensure booking_time is UTC-aware
        if booking_time.tzinfo is None:
            booking_time = booking_time.replace(tzinfo=pytz.utc)
        else:
            booking_time = booking_time.astimezone(pytz.utc)

        now = datetime.now(pytz.utc)

        # 3-hour cancellation window (compare in UTC)
        if (now - booking_time).total_seconds() > 3 * 3600:
            return jsonify({"error": "Cancellation window expired (3 hours)."}), 403

        # Mark booking as cancelled
        cursor.execute(
            "UPDATE community_booking SET status = 'cancelled' WHERE id = %s",
            (booking_id,)
        )

        # Revert eco points
        tourist_id = booking.get('user_id')
        if tourist_id:
            points_earned = 10
            EcoPoints.adjust_balance(tourist_id, -points_earned)
            EcoPoints.create_transaction(
                tourist_id,
                points_earned,
                'revert',
                booking_id,
                f"Reverted {points_earned} points from cancelled community booking #{booking_id}"
            )

        conn.commit()
        return jsonify({"message": "Community booking cancelled successfully"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Failed to cancel community booking", "details": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# --- List bookings (update expired bookings to finished) ---
@community_bp.route("/community-bookings", methods=["GET"])
def list_community_bookings():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    with get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            # Update expired bookings (older than 1 day) to 'finished'
            cursor.execute("""
                UPDATE community_booking
                SET status = 'finished'
                WHERE booking_date <= NOW() - INTERVAL 1 DAY
                  AND status NOT IN ('cancelled', 'finished')
            """)
            conn.commit()

            # Fetch user's bookings
            cursor.execute("""
                SELECT cb.id AS booking_id,
                       cb.experience_id,
                       cb.booking_date,
                       cb.status,
                       ce.title,
                       ce.description,
                       ce.price,
                       ce.location,
                       ce.latitude,
                       ce.longitude
                FROM community_booking cb
                JOIN community_experience ce ON cb.experience_id = ce.id
                WHERE cb.user_id = %s
                ORDER BY cb.booking_date DESC
            """, (user_id,))
            bookings = cursor.fetchall()

            # Add points info
            for b in bookings:
                b["points_earned"] = 10 if b["status"] == "booked" else 0

    return jsonify(bookings)