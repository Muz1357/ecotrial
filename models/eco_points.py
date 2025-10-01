from models.db import get_connection
from datetime import datetime
import pytz

class EcoPoints:
    @staticmethod
    def get_balance(user_id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT eco_points FROM user_account WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row['eco_points'] if row else 0

    @staticmethod
    def adjust_balance(user_id, delta):
        """delta can be positive (earn) or negative (spend). Returns new balance."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE user_account SET eco_points = GREATEST(eco_points + %s, 0) WHERE id = %s", (delta, user_id))
        conn.commit()
        
        cursor2 = conn.cursor(dictionary=True)
        cursor2.execute("SELECT eco_points FROM user_account WHERE id = %s", (user_id,))
        row = cursor2.fetchone()
        cursor2.close()
        conn.close()
        return row['eco_points'] if row else 0

    @staticmethod
    def create_transaction(user_id, points, tx_type, booking_id=None, description=None):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO eco_points_transactions (user_id, points, type, booking_id, description, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, points, tx_type, booking_id, description, datetime.now(pytz.utc)))
        conn.commit()
        cursor.close()
        conn.close()
