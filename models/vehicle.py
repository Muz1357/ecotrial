from models.db import get_connection
from datetime import datetime

class Vehicle:
    @staticmethod
    def create(user_id, registration_number, brand, model, year):
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO vehicles (user_id, registration_number, brand, model, year, status, created_at)
            VALUES (%s, %s, %s, %s, %s, 'pending', %s)
        """
        cursor.execute(query, (user_id, registration_number, brand, model, year, datetime.now()))
        conn.commit()
        cursor.close()
        conn.close()
        return cursor.lastrowid

    @staticmethod
    def get_pending():
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM vehicles WHERE status = 'pending'")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows

    @staticmethod
    def approve(vehicle_id, vehicle_type):
        conn = get_connection()
        cursor = conn.cursor()
        query = "UPDATE vehicles SET status='approved', vehicle_type=%s WHERE id=%s"
        cursor.execute(query, (vehicle_type, vehicle_id))
        conn.commit()
        cursor.close()
        conn.close()

    @staticmethod
    def update_pricing(vehicle_type, price_per_km, eco_points_per_km):
        conn = get_connection()
        cursor = conn.cursor()
        # If type exists, update; else insert
        query = """
            INSERT INTO vehicle_pricing (vehicle_type, price_per_km, eco_points_per_km)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE price_per_km=%s, eco_points_per_km=%s
        """
        cursor.execute(query, (vehicle_type, price_per_km, eco_points_per_km, price_per_km, eco_points_per_km))
        conn.commit()
        cursor.close()
        conn.close()

    @staticmethod
    def get_pricing():
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM vehicle_pricing")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
