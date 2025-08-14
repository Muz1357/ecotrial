from models.db import get_connection

class Listing:
    def __init__(self, id=None, user_id=None, title=None, description=None,
                 price=None, location=None, latitude=None, longitude=None, 
                 image_url=None, eco_cert_url=None, rooms_available=None, 
                 room_details=None, is_approved=False):
        self.id = id
        self.user_id = user_id
        self.title = title
        self.description = description
        self.price = price
        self.location = location
        self.latitude = latitude
        self.longitude = longitude
        self.image_path = image_url
        self.eco_cert_url = eco_cert_url
        self.rooms_available = rooms_available
        self.room_details = room_details
        self.is_approved = is_approved

    def save(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO listing (
                user_id, title, description, price, location,
                latitude, longitude, image_path, eco_cert_url, 
                rooms_available, room_details, is_approved
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            self.user_id, self.title, self.description, self.price,
            self.location, self.latitude, self.longitude, self.image_path, 
            self.eco_cert_url, self.rooms_available, self.room_details, 
            self.is_approved
        ))
        conn.commit()
        cursor.close()
        conn.close()

    @staticmethod
    def get_approved_listings():
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM listing WHERE is_approved=TRUE")
        listings = cursor.fetchall()
        cursor.close()
        conn.close()
        return listings

    @staticmethod
    def get_listing_by_id(listing_id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM listing WHERE id = %s AND is_approved = TRUE", (listing_id,))
        listing = cursor.fetchone()
        cursor.close()
        conn.close()
        return listing
