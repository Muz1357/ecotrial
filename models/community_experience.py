from models.db import get_connection
from datetime import datetime
import os
import requests

GOOGLE_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', 'AIzaSyA0kovojziyFywE0eF1mnMJdJnubZCX6Hs')


def geocode_location(address):
    """Convert address text into latitude/longitude using Google Maps API"""
    if not GOOGLE_API_KEY or not address:
        return None, None

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": GOOGLE_API_KEY}

    try:
        resp = requests.get(url, params=params)
        data = resp.json()
        if data.get("status") == "OK" and len(data["results"]) > 0:
            loc = data["results"][0]["geometry"]["location"]
            return loc["lat"], loc["lng"]
    except Exception as e:
        print("Geocoding error:", e)

    return None, None


class CommunityExperience:
    def __init__(self, id, title, description, category, location, latitude,
                 longitude, price, image_path, certificate_path, impact_note,
                 weather_type, contact_info, approved, created_at, updated_at):
        self.id = id
        self.title = title
        self.description = description
        self.category = category
        self.location = location
        self.latitude = latitude
        self.longitude = longitude
        self.price = price
        self.image_path = image_path
        self.certificate_path = certificate_path
        self.impact_note = impact_note
        self.weather_type = weather_type
        self.contact_info = contact_info
        self.approved = approved
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "location": self.location,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "price": float(self.price) if self.price else None,
            "image_path": self.image_path,
            "certificate_path": self.certificate_path,
            "impact_note": self.impact_note,
            "weather_type": self.weather_type,
            "contact_info": self.contact_info,
            "approved": bool(self.approved),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    @staticmethod
    def create(data):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO community_experience 
            (title, description, category, location, latitude, longitude, price,
             image_path, certificate_path, impact_note, weather_type, contact_info, approved, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (
            data.get("title"),
            data.get("description"),
            data.get("category"),
            data.get("location"),
            data.get("latitude"),
            data.get("longitude"),
            data.get("price"),
            data.get("image_path"),
            data.get("certificate_path"),
            data.get("impact_note"),
            data.get("weather_type") or "Both",
            data.get("contact_info"),
            False
        ))
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return new_id

    @staticmethod
    def get_all(category=None, only_approved=True):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        query = "SELECT * FROM community_experience WHERE 1=1"
        params = []
        if category:
            query += " AND category=%s"
            params.append(category)
        if only_approved:
            query += " AND approved=1"

        query += " ORDER BY created_at DESC"
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        return [CommunityExperience(**row).to_dict() for row in rows]

    @staticmethod
    def get_by_id(exp_id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM community_experience WHERE id=%s", (exp_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return CommunityExperience(**row) if row else None

    @staticmethod
    def approve(exp_id, approved=True):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # get current location string
        cursor.execute("SELECT location FROM community_experience WHERE id=%s", (exp_id,))
        row = cursor.fetchone()

        lat, lng = (None, None)
        if row and row.get("location"):
            lat, lng = geocode_location(row["location"])

        cursor.execute("""
            UPDATE community_experience 
            SET approved=%s, latitude=%s, longitude=%s, updated_at=NOW()
            WHERE id=%s
        """, (approved, lat, lng, exp_id))
        conn.commit()
        cursor.close()
        conn.close()
