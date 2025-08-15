import os
import requests
import math
from flask import Blueprint, request, jsonify, current_app
from models.db import get_connection
from datetime import datetime

plan_trip_bp = Blueprint('plan_trip', __name__)

# Configuration
GOOGLE_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', 'AIzaSyA0kovojziyFywE0eF1mnMJdJnubZCX6Hs')
HOTEL_SEARCH_RADIUS_KM = 20
MAX_HOTELS_TO_RETURN = 20

# CO2 emission factors (kg CO2 per km)
EMISSION_FACTORS = {
    'Car': 0.192,    
    'bicycling': 0.0,
    'walking': 0.0,
    'transit': 0.105,       
    'motorcycle': 0.103, 
    'electric_car': 0.053 
}

def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in km using Haversine formula"""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def calculate_co2(distance_km, mode):
    """Calculate CO2 emissions for a given distance and travel mode"""
    factor = EMISSION_FACTORS.get(mode, 0.192)
    return round(distance_km * factor, 3)

def decode_polyline(polyline_str):
    """Decode Google Maps polyline into list of coordinates"""
    if not polyline_str:
        return []
    
    index, lat, lng = 0, 0, 0
    coordinates = []
    length = len(polyline_str)
    
    while index < length:
        # Latitude
        shift, result = 0, 0
        while True:
            b = ord(polyline_str[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        # Longitude
        shift, result = 0, 0
        while True:
            b = ord(polyline_str[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng

        coordinates.append({'lat': lat / 1e5, 'lng': lng / 1e5})
    
    return coordinates

def geocode_location(location_name):
    """Convert location name (e.g., 'Pasikuda') to coordinates using Google Geocoding API"""
    try:
        params = {
            'address': location_name,
            'key': GOOGLE_API_KEY
        }
        response = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params=params,
            timeout=5
        )
        data = response.json()
        if data['status'] == 'OK' and data['results']:
            location = data['results'][0]['geometry']['location']
            return {'lat': location['lat'], 'lng': location['lng']}
        return None
    except Exception as e:
        current_app.logger.error(f"Geocoding error: {str(e)}")
        return None

def find_nearby_hotels(location_name=None, lat=None, lng=None, radius_km=None):
    """
    Query database for approved eco-certified hotels:
    - If `location_name` is given: Match hotels by name (e.g., "Kurunegala").
    - If `lat/lng` is given: Search within a radius (old behavior).
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        if location_name:
            # Search by location name (exact match)
            query = """
                SELECT 
                    id, user_id, title, description, image_path, 
                    price, rooms_available, room_details, eco_cert_url,
                    latitude, longitude
                FROM listing
                WHERE is_approved = 1 
                  AND eco_cert_url IS NOT NULL
                  AND location_name = %s  # Assumes a column `location_name` exists
                ORDER BY price ASC
                LIMIT %s
            """
            cursor.execute(query, (location_name, MAX_HOTELS_TO_RETURN))
        else:
            # Search by coordinates (old behavior)
            query = """
                SELECT 
                    id, user_id, title, description, image_path, 
                    price, rooms_available, room_details, eco_cert_url,
                    latitude, longitude,
                    (6371 * acos(
                        cos(radians(%s)) * cos(radians(latitude)) * 
                        cos(radians(longitude) - radians(%s)) + 
                        sin(radians(%s)) * sin(radians(latitude))
                    )) AS distance
                FROM listing
                WHERE is_approved = 1 AND eco_cert_url IS NOT NULL
                HAVING distance < %s
                ORDER BY distance
                LIMIT %s
            """
            cursor.execute(query, (lat, lng, lat, radius_km, MAX_HOTELS_TO_RETURN))

        hotels = cursor.fetchall()
        
        for hotel in hotels:
            if 'distance' in hotel:
                hotel['distance'] = float(hotel['distance'])
            hotel['latitude'] = float(hotel['latitude'])
            hotel['longitude'] = float(hotel['longitude'])
        
        return hotels
    except Exception as e:
        current_app.logger.error(f"Database error: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()

def get_recommendations(routes):
    """Determine the best recommendations from available routes"""
    if not routes:
        return {}
    
    # Filter out walking if distance is too long (>5km)
    valid_routes = [r for r in routes if not (r['mode'] == 'walking' and r['distance_km'] > 5)]
    
    return {
        'fastest': min(valid_routes, key=lambda x: x['duration_min']),
        'eco_friendliest': min(valid_routes, key=lambda x: x['co2_kg']),
        'cheapest': next((r for r in valid_routes if r['mode'] in ['bus', 'transit']), 
                    valid_routes[0])  # Fallback to first route if no transit
    }

@plan_trip_bp.route('/plan_trip', methods=['POST'])
def plan_trip():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    
    start = data.get('start')
    end = data.get('end')
    if not start or not end:
        return jsonify({"error": "Both start and end locations are required"}), 400
    
    # Get routes from Google Directions API
    routes = []
    modes = ['driving', 'transit', 'bicycling', 'walking']
    
    for mode in modes:
        params = {
            'origin': f"{start['lat']},{start['lng']}" if isinstance(start, dict) else start,
            'destination': f"{end['lat']},{end['lng']}" if isinstance(end, dict) else end,
            'mode': mode,
            'key': GOOGLE_API_KEY
        }
        
        try:
            response = requests.get(
                "https://maps.googleapis.com/maps/api/directions/json",
                params=params,
                timeout=10
            )
            data = response.json()
            
            if data.get('status') == 'OK' and data.get('routes'):
                route = data['routes'][0]
                leg = route['legs'][0]
                
                distance_km = leg['distance']['value'] / 1000
                duration_min = leg['duration']['value'] / 60
                co2_kg = calculate_co2(distance_km, mode)
                polyline = route['overview_polyline']['points']
                poly_points = decode_polyline(polyline)
                
                routes.append({
                    'mode': mode,
                    'distance_km': round(distance_km, 1),
                    'duration_min': round(duration_min, 1),
                    'co2_kg': co2_kg,
                    'polyline': polyline,
                    'poly_points': poly_points
                })
                
        except Exception as e:
            current_app.logger.error(f"Error fetching {mode} route: {str(e)}")
            continue
    
    if not routes:
        return jsonify({"error": "Could not calculate any routes"}), 400
    
    # Find approved eco-certified hotels near route midpoint
    if isinstance(end, str) and ',' not in end:
        hotels = find_nearby_hotels(location_name=end)  # Search by name
    else:
        # Handle coordinates (old behavior)
        destination_coords = (
            end if isinstance(end, dict) 
            else {'lat': float(end.split(',')[0]), 'lng': float(end.split(',')[1])}
        )
        hotels = find_nearby_hotels(lat=destination_coords['lat'], lng=destination_coords['lng'], radius_km=HOTEL_SEARCH_RADIUS_KM)
    
    # Generate recommendations
    recommendations = get_recommendations(routes)
    
    return jsonify({
        "status": "success",
        "routes": routes,
        "hotels": hotels,
        "recommendations": recommendations,
        "destination": destination_coords  # Include destination coords in response
    })