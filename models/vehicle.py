import os
import cloudinary
import cloudinary.uploader
from datetime import datetime
from models.db import get_connection
from pytz import timezone

class Vehicle:
    @staticmethod
    def create_vehicle(user_id, model_name, plate_number, vehicle_type, proof_file=None):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # First get vehicle_type_id
            cursor.execute("SELECT id FROM vehicle_types WHERE name = %s", (vehicle_type,))
            type_result = cursor.fetchone()
            
            if not type_result:
                raise ValueError("Invalid vehicle type")
                
            vehicle_type_id = type_result['id']
            
            # Upload to Cloudinary if file provided
            proof_url = None
            public_id = None
            
            if proof_file:
                upload_result = cloudinary.uploader.upload(
                    proof_file,
                    folder="vehicle_proofs",
                    resource_type="auto"
                )
                proof_url = upload_result['secure_url']
                public_id = upload_result['public_id']
            
            # Insert vehicle record
            cursor.execute("""
                INSERT INTO vehicles (
                    user_id, model_name, plate_number, vehicle_type_id, 
                    proof_url, cloudinary_public_id, status
                ) VALUES (%s, %s, %s, %s, %s, %s, 'pending')
            """, (user_id, model_name, plate_number, vehicle_type_id, proof_url, public_id))
            
            vehicle_id = cursor.lastrowid
            conn.commit()
            
            return {
                'id': vehicle_id,
                'status': 'pending',
                'message': 'Vehicle registration submitted for admin approval'
            }
            
        except Exception as e:
            conn.rollback()
            # Clean up Cloudinary upload if it failed after upload
            if 'public_id' in locals() and public_id:
                try:
                    cloudinary.uploader.destroy(public_id)
                except:
                    pass
            raise e
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_user_vehicles(user_id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT v.id, v.model_name, v.plate_number, vt.name as vehicle_type, 
                   v.status, v.proof_url, v.admin_notes,
                   v.approved_at, v.created_at
            FROM vehicles v
            JOIN vehicle_types vt ON v.vehicle_type_id = vt.id
            WHERE v.user_id = %s
            ORDER BY v.created_at DESC
        """, (user_id,))
        
        vehicles = cursor.fetchall()
        cursor.close()
        conn.close()
        return vehicles

    @staticmethod
    def get_pending_vehicles():
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT v.id, v.user_id, v.model_name, v.plate_number, 
                   vt.name as vehicle_type, v.proof_url, v.created_at,
                   u.name as user_name, u.email as user_email
            FROM vehicles v
            JOIN vehicle_types vt ON v.vehicle_type_id = vt.id
            JOIN users u ON v.user_id = u.id
            WHERE v.status = 'pending'
            ORDER BY v.created_at ASC
        """)
        
        vehicles = cursor.fetchall()
        cursor.close()
        conn.close()
        return vehicles

    @staticmethod
    def approve_vehicle(vehicle_id, admin_id, notes=None):
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE vehicles 
                SET status = 'approved',
                    approved_by = %s,
                    approved_at = UTC_TIMESTAMP(),
                    admin_notes = %s
                WHERE id = %s AND status = 'pending'
            """, (admin_id, notes, vehicle_id))
            
            affected_rows = cursor.rowcount
            conn.commit()
            
            if affected_rows == 0:
                raise ValueError("Vehicle not found or already processed")
                
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def reject_vehicle(vehicle_id, admin_id, notes=None):
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # First get public_id to delete from Cloudinary
            cursor.execute("""
                SELECT cloudinary_public_id FROM vehicles 
                WHERE id = %s AND status = 'pending'
            """, (vehicle_id,))
            result = cursor.fetchone()
            
            if not result:
                raise ValueError("Vehicle not found or already processed")
                
            public_id = result[0]
            
            # Delete from Cloudinary if exists
            if public_id:
                cloudinary.uploader.destroy(public_id)
            
            # Update record
            cursor.execute("""
                UPDATE vehicles 
                SET status = 'rejected',
                    approved_by = %s,
                    approved_at = UTC_TIMESTAMP(),
                    admin_notes = %s,
                    proof_url = NULL,
                    cloudinary_public_id = NULL
                WHERE id = %s
            """, (admin_id, notes, vehicle_id))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_vehicle_types():
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT id, name, price_per_km, eco_points_rate 
            FROM vehicle_types
            ORDER BY name
        """)
        
        types = cursor.fetchall()
        cursor.close()
        conn.close()
        return types

    @staticmethod
    def update_vehicle_type(type_id, price_per_km=None, eco_points_rate=None):
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            updates = []
            params = []
            
            if price_per_km is not None:
                updates.append("price_per_km = %s")
                params.append(price_per_km)
                
            if eco_points_rate is not None:
                updates.append("eco_points_rate = %s")
                params.append(eco_points_rate)
                
            if not updates:
                raise ValueError("No updates provided")
                
            params.append(type_id)
            
            query = f"UPDATE vehicle_types SET {', '.join(updates)} WHERE id = %s"
            cursor.execute(query, params)
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()