from flask import Flask, jsonify
from flask_cors import CORS
from config import UPLOAD_FOLDER
import os

# Route imports
from models.db import get_connection
from routes.auth_routes import auth_bp
from routes.listing_routes import listing_bp
from routes.booking_routes import booking_bp
from routes.admin_routes import admin_bp

app = Flask(__name__)
CORS(app)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.secret_key = 'your_secret_key_here'

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(listing_bp)
app.register_blueprint(booking_bp)
app.register_blueprint(admin_bp)



if __name__ == '__main__':
    app.run(debug=True)
