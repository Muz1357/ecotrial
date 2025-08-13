from models.db import get_connection
from datetime import datetime

class Trip:
    def __init__(self, id, tourist_id, start_location, end_location, start_date, end_date, total_distance=0, total_co2=0, created_at=None):
        self.id = id
        self.tourist_id = tourist_id
        self.start_location = start_location
        self.end_location = end_location
        self.start_date = start_date
        self.end_date = end_date
        self.total_distance = total_distance
        self.total_co2 = total_co2
        self.created_at = created_at or datetime.utcnow()

    @staticmethod
    def create(tourist_id, start_location, end_location, start_date, end_date, total_distance, total_co2):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO trips (tourist_id, start_location, end_location, start_date, end_date, total_distance, total_co2, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (tourist_id, start_location, end_location, start_date, end_date, total_distance, total_co2, datetime.utcnow()))
        trip_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        return trip_id

    @staticmethod
    def find_by_id(trip_id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM trips WHERE id = %s", (trip_id,))
        data = cursor.fetchone()
        cursor.close()
        conn.close()
        if data:
            return Trip(**data)
        return None
