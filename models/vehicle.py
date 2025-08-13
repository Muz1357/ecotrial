from models.db import get_connection

class Vehicle:
    @staticmethod
    def create(user_id, model_name, plate_number, vehicle_type, proof_file):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO vehicle (user_id, model_name, plate_number, vehicle_type, proof_file)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, model_name, plate_number, vehicle_type, proof_file))
        conn.commit()
        cursor.close()
        conn.close()
        return True

    @staticmethod
    def get_all_pending():
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT v.*, u.name AS owner_name, u.email AS owner_email
            FROM vehicle v
            JOIN user_account u ON v.user_id = u.id
            WHERE v.status = 'pending'
        """)
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    @staticmethod
    def approve(vehicle_id, eco_category, price_per_km, eco_points_per_km):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE vehicle
            SET status = 'approved',
                eco_category = %s,
                price_per_km = %s,
                eco_points_per_km = %s
            WHERE id = %s
        """, (eco_category, price_per_km, eco_points_per_km, vehicle_id))
        conn.commit()
        cursor.close()
        conn.close()
        return True

    @staticmethod
    def update_pricing(vehicle_id, price_per_km, eco_points_per_km):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE vehicle
            SET price_per_km = %s,
                eco_points_per_km = %s
            WHERE id = %s
        """, (price_per_km, eco_points_per_km, vehicle_id))
        conn.commit()
        cursor.close()
        conn.close()
        return True
