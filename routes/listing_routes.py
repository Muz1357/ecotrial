from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
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
    if 'image' not in request.files:
        return jsonify({"error": "No image part"}), 400

    image = request.files['image']

    if image.filename == '':
        return jsonify({"error": "No selected image"}), 400

    if image and allowed_file(image.filename):
        # Upload image to Cloudinary
        upload_result = cloudinary.uploader.upload(image)
        image_url = upload_result.get('secure_url')

        data = request.form
        listing = Listing(
            user_id=data.get('user_id'),
            title=data.get('title'),
            description=data.get('description'),
            price=data.get('price'),           # Make sure Listing supports these fields
            location=data.get('location'),
            image_path=image_url,               # Save URL instead of filename
            is_approved=False                  # Needs admin approval
        )
        listing.save()

        return jsonify({"message": "Listing uploaded, pending admin approval"}), 201
    else:
        return jsonify({"error": "File type not allowed"}), 400

@listing_bp.route('/listings/<int:listing_id>', methods=['GET'])
def get_listing_by_id(listing_id):
    listing = Listing.get_listing_by_id(listing_id)
    if listing:
        return jsonify(listing), 200
    else:
        return jsonify({"error": "Listing not found"}), 404
