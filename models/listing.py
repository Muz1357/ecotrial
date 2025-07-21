from models.db import get_connection

class Listing:
    def __init__(self, id=None, user_id=None, title=None, description=None,
                 price=None, location=None, image_path=None, is_approved=False):
        self.id = id
        self.user_id = user_id
        self.title = title
        self.description = description
        self.price = price
        self.location = location
        self.image_path = image_path
        self.is_approved = is_approved

    def save(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO listing (user_id, title, description, price, location, image_path, is_approved)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (self.user_id, self.title, self.description, self.price,
              self.location, self.image_path, self.is_approved))
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
