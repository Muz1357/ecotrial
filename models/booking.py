from models.db import get_connection
from datetime import datetime
import pytz

class Booking:
    def __init__(self, id=None, listing_id=None, tourist_id=None, check_in=None, check_out=None, created_at=None,
                 points_earned=0, points_redeemed=0, redemption_amount=0):
        self.id = id
        self.listing_id = listing_id
        self.tourist_id = tourist_id
        self.check_in = check_in
        self.check_out = check_out
        self.created_at = created_at
        self.points_earned = points_earned
        self.points_redeemed = points_redeemed
        self.redemption_amount = redemption_amount

    def save(self):
        """Insert booking and return inserted booking id."""
        with get_connection() as conn:
            with conn.cursor() as cursor:
                colombo_time = datetime.now(pytz.utc)
                cursor.execute("""
                    INSERT INTO booking (listing_id, tourist_id, check_in, check_out, created_at, points_earned, points_redeemed, redemption_amount)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (self.listing_id, self.tourist_id, self.check_in, self.check_out, colombo_time,
                      self.points_earned, self.points_redeemed, self.redemption_amount))
                booking_id = cursor.lastrowid
            conn.commit()
        return booking_id
