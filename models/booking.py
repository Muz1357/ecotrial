from models.db import get_connection
from datetime import datetime


class Booking:
    def __init__(self, id=None, listing_id=None, tourist_id=None, check_in=None, check_out=None, created_at=None):
        self.id = id
        self.listing_id = listing_id
        self.tourist_id = tourist_id
        self.check_in = check_in
        self.check_out = check_out
        self.created_at = created_at

    def save(self):
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO booking (listing_id, tourist_id, check_in, check_out, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                """, (self.listing_id, self.tourist_id, self.check_in, self.check_out, self.created_at))
            conn.commit()
