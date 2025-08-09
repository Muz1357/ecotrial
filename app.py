from flask import Flask
from flask_cors import CORS
import cloudinary
import os
from scheduler import start_scheduler
# Import your blueprints
from models.db import get_connection  
from routes.auth_routes import auth_bp
from routes.listing_routes import listing_bp
from routes.booking_routes import booking_bp
from routes.admin_routes import admin_bp
from routes.users import user_bp

app = Flask(__name__)
CORS(app)

# Use environment variable for secret key (set this in Heroku/Railway)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')

# Configure Cloudinary from environment variables
cloudinary.config(
    cloud_name='dfnzcn8dl',
    api_key='543959871613564',
    api_secret="A6vgVVwrMJDxZHJ3H0hVn8K0nKs",
    secure=True
)

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(listing_bp)
app.register_blueprint(booking_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(user_bp)

start_scheduler()

if __name__ == "__main__":
    # Use 0.0.0.0 so Heroku can bind the app
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
