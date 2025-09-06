from flask import Blueprint, request, jsonify
from models.community_experience import CommunityExperience
from datetime import datetime
import os, cloudinary.uploader, requests
from math import radians, cos, sin, asin, sqrt

community_bp = Blueprint("community_experience", __name__)

# Google Maps API Key (set in .env or system environment)
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
        # Required fields
        title = request.form.get("title")
        category = request.form.get("category")
        location_name = request.form.get("location")

        if not title or not category or not location_name:
            return jsonify({"error": "title, category and location required"}), 400

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
            "category": category,
            "location": location_name,
            "latitude": latitude,
            "longitude": longitude,
            "price": request.form.get("price"),
            "image_path": image_path,
            "certificate_path": certificate_path,
            "impact_note": request.form.get("impact_note"),
            "weather_type": request.form.get("weather_type") or "Both",
            "contact_info": request.form.get("contact_info"),
        })

        return jsonify({"id": exp_id, "message": "Experience created"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- List experiences ---
@community_bp.route("/community-experiences", methods=["GET"])
def list_experiences():
    category = request.args.get("category")
    only_approved = request.args.get("approved", "true").lower() == "true"
    items = CommunityExperience.get_all(category, only_approved)
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


# --- Approve / Unapprove experience ---
@community_bp.route("/admin/community-experiences/<int:exp_id>/approve", methods=["PUT"])
def approve_experience(exp_id):
    approved = request.json.get("approved", True)
    CommunityExperience.approve(exp_id, approved)
    return jsonify({"message": f"Experience {'approved' if approved else 'unapproved'}"})
