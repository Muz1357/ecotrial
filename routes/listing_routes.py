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
        print("Form Keys:", request.form.keys())
        print("Form Data:", request.form.to_dict())
        print("File Keys:", request.files.keys())

        user_id = request.form['user_id']
        title = request.form['title']
        description = request.form['description']
        price = request.form['price']
        location = request.form['location']
        room_count = request.form['rooms_available']
        room_details = request.form['room_details']

        image = request.files['image']
        eco_cert = request.files['eco_cert']

        image_upload = cloudinary.uploader.upload(image)
        image_url = image_upload.get('secure_url')

        eco_cert_upload = cloudinary.uploader.upload(eco_cert, resource_type="auto")
        eco_cert_url = eco_cert_upload.get('secure_url')

        return jsonify({"message": "Listing uploaded successfully", "image_url": image_url, "cert_url": eco_cert_url}), 200
    except Exception as e:
        print("❌ Upload Error:", str(e))  # Print full error for debugging
        return jsonify({"error": str(e)}), 400



@listing_bp.route('/listings/<int:listing_id>', methods=['GET'])
def get_listing_by_id(listing_id):
    listing = Listing.get_listing_by_id(listing_id)
    if listing:
        return jsonify(listing), 200
    else:
        return jsonify({"error": "Listing not found"}), 404
