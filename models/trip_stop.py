from models.db import get_connection

class TripStop:
    def __init__(self, id, trip_id, location_name, latitude, longitude, type, order_index):
        self.id = id
        self.trip_id = trip_id
        self.location_name = location_name
        self.latitude = latitude
        self.longitude = longitude
        self.type = type
        self.order_index = order_index

    @staticmethod
    def create(trip_id, location_name, latitude, longitude, type, order_index):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO trip_stops (trip_id, location_name, latitude, longitude, type, order_index)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (trip_id, location_name, latitude, longitude, type, order_index))
        conn.commit()
        cursor.close()
        conn.close()
