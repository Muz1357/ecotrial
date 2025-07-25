import os

DB_CONFIG = {
    'host': os.environ.get('DB_HOST'),
    'user': os.environ.get('DB_USER'),
    'password': os.environ.get('DB_PASS'),
    'database': os.environ.get('DB_NAME')
}

# No local uploads needed since images upload directly to Cloudinary
UPLOAD_FOLDER = None  

# Allowed extensions (optional, if you validate uploads)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
