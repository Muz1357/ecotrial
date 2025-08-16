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

def geocode_location(location):
    """Convert location name (e.g., 'Pasikuda') to coordinates using Google Geocoding API"""
    try:
        params = {
            'address': location,
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

def find_nearby_hotels(location=None, lat=None, lng=None, radius_km=None):
    """
    FINAL WORKING VERSION - Query approved eco-certified hotels:
    - If location is provided: Search by location name (case-insensitive)
    - If coordinates are provided: Search within radius
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        if location:
            # Location-based search
            query = """
                SELECT 
                    id, title, location, is_approved, eco_cert_url,
                    latitude, longitude, price, image_path
                FROM listing
                WHERE LOWER(location) LIKE LOWER(%s)
                  AND is_approved = 1
                  AND eco_cert_url IS NOT NULL
                LIMIT %s
            """
            search_term = f"%{location}%"
            cursor.execute(query, (search_term, MAX_HOTELS_TO_RETURN))
        elif lat and lng and radius_km:
            # Coordinate-based search
            query = """
                SELECT 
                    id, title, location, is_approved, eco_cert_url,
                    latitude, longitude, price, image_path,
                    (6371 * acos(
                        cos(radians(%s)) * cos(radians(latitude)) * 
                        cos(radians(longitude) - radians(%s)) + 
                        sin(radians(%s)) * sin(radians(latitude))
                    )) AS distance
                FROM listing
                WHERE is_approved = 1 
                  AND eco_cert_url IS NOT NULL
                HAVING distance < %s
                ORDER BY distance
                LIMIT %s
            """
            cursor.execute(query, (lat, lng, lat, radius_km, MAX_HOTELS_TO_RETURN))
        else:
            return []

        hotels = cursor.fetchall()
        current_app.logger.info(f"Found {len(hotels)} hotels matching criteria")
        
        # Convert numeric fields
        for hotel in hotels:
            if 'distance' in hotel:
                hotel['distance'] = float(hotel['distance'])
            if 'latitude' in hotel:
                hotel['latitude'] = float(hotel['latitude'])
            if 'longitude' in hotel:
                hotel['longitude'] = float(hotel['longitude'])
            if 'price' in hotel:
                hotel['price'] = float(hotel['price'])
        
        return hotels
    except Exception as e:
        current_app.logger.error(f"Database error in find_nearby_hotels: {str(e)}")
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
        # First try exact location match
        hotels = find_nearby_hotels(location=end)
        current_app.logger.info(f"Initial search for '{end}' found {len(hotels)} hotels")
        
        if not hotels:
            # Fallback to geocoding if no hotels found by name
            destination_coords = geocode_location(end)
            if destination_coords:
                hotels = find_nearby_hotels(
                    lat=destination_coords['lat'],
                    lng=destination_coords['lng'],
                    radius_km=HOTEL_SEARCH_RADIUS_KM
                )
                current_app.logger.info(f"Geocode search found {len(hotels)} hotels")
    else:
        # Handle coordinate-based search
        destination_coords = (
            end if isinstance(end, dict) 
            else {'lat': float(end.split(',')[0]), 'lng': float(end.split(',')[1])}
        )
        hotels = find_nearby_hotels(
            lat=destination_coords['lat'],
            lng=destination_coords['lng'],
            radius_km=HOTEL_SEARCH_RADIUS_KM
        )

    # Prepare response
    response_data = {
        "status": "success",
        "routes": routes,
        "hotels": hotels,
        "recommendations": get_recommendations(routes),
        "destination": destination_coords if 'destination_coords' in locals() else None
    }
    
    current_app.logger.info(f"Returning {len(hotels)} hotels in response")
    return jsonify(response_data)