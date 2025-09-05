from flask import Blueprint, request, jsonify
from models.community_experience import CommunityExperience
from datetime import datetime
import os, cloudinary.uploader
from math import radians, cos, sin, asin, sqrt

community_bp = Blueprint("community_experience", __name__)

# Utility haversine distance
def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return 6371 * 2 * asin(sqrt(a))

# --- Create experience ---
@community_bp.route("/community-experiences", methods=["POST"])
def create_experience():
    try:
        title = request.form.get("title")
        category = request.form.get("category")
        if not title or not category:
            return jsonify({"error": "title and category required"}), 400

        image_path = None
        if "image" in request.files:
            file = request.files["image"]
            upload_res = cloudinary.uploader.upload(file, folder="community_experiences")
            image_path = upload_res.get("secure_url")

        exp_id = CommunityExperience.create({
            "title": title,
            "description": request.form.get("description"),
            "category": category,
            "location": request.form.get("location"),
            "latitude": request.form.get("latitude"),
            "longitude": request.form.get("longitude"),
            "price": request.form.get("price"),
            "image_path": image_path,
            "impact_note": request.form.get("impact_note"),
            "weather_type": request.form.get("weather_type"),
            "contact_info": request.form.get("contact_info")
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

# --- Nearby ---
@community_bp.route("/community-experiences/nearby", methods=["GET"])
def nearby_experiences():
    lat, lng = request.args.get("lat", type=float), request.args.get("lng", type=float)
    radius = request.args.get("radius_km", type=float, default=5)
    weather = request.args.get("weather")

    if not lat or not lng:
        return jsonify({"error": "lat and lng required"}), 400

    items = CommunityExperience.get_all()
    results = []
    for i in items:
        if not i["latitude"] or not i["longitude"]:
            continue
        dist = haversine(lng, lat, float(i["longitude"]), float(i["latitude"]))
        if dist <= radius:
            if weather and i["weather_type"] not in ("Both", weather):
                continue
            i["distance_km"] = round(dist, 2)
            results.append(i)

    return jsonify(sorted(results, key=lambda x: x["distance_km"]))


@community_bp.route("/admin/community-experiences/<int:exp_id>/approve", methods=["PUT"])
def approve_experience(exp_id):
    approved = request.json.get("approved", True)
    CommunityExperience.approve(exp_id, approved)
    return jsonify({"message": f"Experience {'approved' if approved else 'unapproved'}"})
