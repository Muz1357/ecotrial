from flask import Blueprint, request, jsonify, current_app
import cloudinary.uploader
from models.listing import Listing
from config import ALLOWED_EXTENSIONS

listing_bp = Blueprint('listing', __name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@listing_bp.route('/listings', methods=['GET'])
def get_listings():
    listings = Listing.get_approved_listings()
    return jsonify(listings), 200

@listing_bp.route('/upload-listing', methods=['POST'])
def upload_listing():
    try:
        # Required form fields
        user_id = request.form.get('user_id')
        title = request.form.get('title')
        description = request.form.get('description')
        price = request.form.get('price')
        location = request.form.get('location')
        rooms_count = request.form.get('rooms')
        room_details = request.form.get('room_details')

        # Required files
        image_file = request.files.get('image')
        cert_file = request.files.get('eco_cert')

        if not all([user_id, title, description, price, location, rooms_count, room_details, image_file, cert_file]):
            return jsonify({"error": "Missing required fields"}), 400

        # Upload to Cloudinary
        image_upload = cloudinary.uploader.upload(image_file)
        cert_upload = cloudinary.uploader.upload(cert_file)

        image_url = image_upload.get('secure_url')
        cert_url = cert_upload.get('secure_url')

        # Create and save listing
        listing = Listing(
            user_id=user_id,
            title=title,
            description=description,
            price=price,
            location=location,
            image_url=image_url,
            eco_cert_url=cert_url,
            rooms_count=rooms_count,
            room_details=room_details,
            is_approved=False  # initially not approved
        )
        listing.save()

        return jsonify({
            "message": "Listing uploaded and saved successfully",
            "image_url": image_url,
            "eco_cert_url": cert_url
        }), 200

    except Exception as e:
        print("❌ Upload Error:", str(e))
        return jsonify({"error": str(e)}), 500


@listing_bp.route('/listings/<int:listing_id>', methods=['GET'])
def get_listing_by_id(listing_id):
    listing = Listing.get_listing_by_id(listing_id)
    if listing:
        return jsonify(listing), 200
    else:
        return jsonify({"error": "Listing not found"}), 404
