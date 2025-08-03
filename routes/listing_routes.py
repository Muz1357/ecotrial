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
    current_app.logger.info(f"Received files: {request.files}")
    current_app.logger.info(f"Received form data: {request.form}")

    if 'image' not in request.files or 'eco_cert' not in request.files:
        return jsonify({"error": "Both listing image and eco certificate are required"}), 400

    image = request.files['image']
    eco_cert = request.files['eco_cert']

    if image.filename == '' or eco_cert.filename == '':
        return jsonify({"error": "One or more files are empty"}), 400

    if not allowed_file(image.filename) or not allowed_file(eco_cert.filename):
        return jsonify({"error": "File type not allowed"}), 400

    try:
        # Upload listing image
        image_upload = cloudinary.uploader.upload(image)
        image_url = image_upload.get('secure_url')

        # Upload eco certification (PDF/image)
        eco_cert_upload = cloudinary.uploader.upload(eco_cert, resource_type="auto")
        eco_cert_url = eco_cert_upload.get('secure_url')

        if not image_url or not eco_cert_url:
            return jsonify({"error": "Failed to upload files to Cloudinary"}), 500

        # Form data
        data = request.form
        user_id = data.get('user_id')
        title = data.get('title')
        description = data.get('description')
        price = data.get('price')
        location = data.get('location')
        rooms_available = data.get('rooms')  # changed
        room_details = data.get('room_details')

        if not all([user_id, title, description, price, location, rooms_available, room_details]):
            return jsonify({"error": "Missing form data"}), 400

        listing = Listing(
            user_id=user_id,
            title=title,
            description=description,
            price=price,
            location=location,
            image_path=image_url,
            eco_cert_url=eco_cert_url,
            rooms_available=rooms_available,
            room_details=room_details,
            is_approved=False
        )
        listing.save()

        return jsonify({"message": "Listing uploaded successfully, pending admin approval"}), 201

    except Exception as e:
        current_app.logger.error(f"Upload failed: {e}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@listing_bp.route('/listings/<int:listing_id>', methods=['GET'])
def get_listing_by_id(listing_id):
    listing = Listing.get_listing_by_id(listing_id)
    if listing:
        return jsonify(listing), 200
    else:
        return jsonify({"error": "Listing not found"}), 404
