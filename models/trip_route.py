from models.db import get_connection

class TripRoute:
    def __init__(self, id, trip_id, mode, distance_km, co2_kg, duration_min, cost, is_eco_friendly):
        self.id = id
        self.trip_id = trip_id
        self.mode = mode
        self.distance_km = distance_km
        self.co2_kg = co2_kg
        self.duration_min = duration_min
        self.cost = cost
        self.is_eco_friendly = is_eco_friendly

    @staticmethod
    def create(trip_id, mode, distance_km, co2_kg, duration_min, cost, is_eco_friendly):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO trip_routes (trip_id, mode, distance_km, co2_kg, duration_min, cost, is_eco_friendly)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (trip_id, mode, distance_km, co2_kg, duration_min, cost, is_eco_friendly))
        conn.commit()
        cursor.close()
        conn.close()
