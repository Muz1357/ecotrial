import os

DB_CONFIG = {
    'host': os.environ.get('DB_HOST'),
    'user': os.environ.get('DB_USER'),
    'password': os.environ.get('DB_PASS'),
    'database': os.environ.get('DB_NAME')
}


UPLOAD_FOLDER = None  


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

GOOGLE_MAPS_API_KEY = "AIzaSyA0kovojziyFywE0eF1mnMJdJnubZCX6Hs"