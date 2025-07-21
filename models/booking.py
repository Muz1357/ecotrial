from models.db import get_connection

class Booking:
    def __init__(self, id=None, listing_id=None, tourist_id=None, booking_date=None):
        self.id = id
        self.listing_id = listing_id
        self.tourist_id = tourist_id
        self.booking_date = booking_date

    def save(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO booking (listing_id, tourist_id, booking_date)
            VALUES (%s, %s, %s)
        """, (self.listing_id, self.tourist_id, self.booking_date))
        conn.commit()
        cursor.close()
        conn.close()
