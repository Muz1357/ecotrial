from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os
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
        filename = secure_filename(image.filename)
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        image.save(save_path)

        data = request.form
        listing = Listing(
            user_id=data.get('user_id'),
            title=data.get('title'),
            description=data.get('description'),
            price=data.get('price'),           # <-- added price
            location=data.get('location'),     # <-- added location
            image_path=filename,
            is_approved=False  # Needs admin approval
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
