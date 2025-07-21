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
    # Debug print incoming files and form data
    current_app.logger.info(f"Received files: {request.files}")
    current_app.logger.info(f"Received form data: {request.form}")

    if 'image' not in request.files:
        return jsonify({"error": "No image part"}), 400

    image = request.files['image']

    if image.filename == '':
        return jsonify({"error": "No selected image"}), 400

    if not allowed_file(image.filename):
        return jsonify({"error": "File type not allowed"}), 400

    try:
        upload_result = cloudinary.uploader.upload(image)
        image_url = upload_result.get('secure_url')
        if not image_url:
            current_app.logger.error("Cloudinary upload did not return secure_url")
            return jsonify({"error": "Failed to upload image to Cloudinary"}), 500

        data = request.form
        user_id = data.get('user_id')
        title = data.get('title')
        description = data.get('description')
        price = data.get('price')
        location = data.get('location')

        # Validate required form data:
        if not all([user_id, title, description, price, location]):
            return jsonify({"error": "Missing form data"}), 400

        listing = Listing(
            user_id=user_id,
            title=title,
            description=description,
            price=price,
            location=location,
            image_path=image_url,
            is_approved=False  # Needs admin approval
        )
        listing.save()

        return jsonify({"message": "Listing uploaded, pending admin approval"}), 201

    except Exception as e:
        current_app.logger.error(f"Upload or save failed: {e}")
        return jsonify({"error": f"Failed to upload image or save listing: {str(e)}"}), 500

@listing_bp.route('/listings/<int:listing_id>', methods=['GET'])
def get_listing_by_id(listing_id):
    listing = Listing.get_listing_by_id(listing_id)
    if listing:
        return jsonify(listing), 200
    else:
        return jsonify({"error": "Listing not found"}), 404
