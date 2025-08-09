from models.db import get_connection
from datetime import datetime
import pytz

class TravelLog:
    @staticmethod
    def save(tourist_id, start_time, end_time, distance_km, mode, co2_kg, points_awarded):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO travel_logs (tourist_id, start_time, end_time, distance_km, mode, co2_kg, points_awarded, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (tourist_id, start_time, end_time, distance_km, mode, co2_kg, points_awarded, datetime.now(pytz.utc)))
        conn.commit()
        cursor.close()
        conn.close()
