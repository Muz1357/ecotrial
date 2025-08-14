import os
import requests
import math
from flask import Blueprint, request, jsonify, current_app
from models.db import get_connection
from datetime import datetime

plan_trip_bp = Blueprint('plan_trip', __name__)

# ----------------------
# Configuration
# ----------------------
GOOGLE_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', 'AIzaSyA0kovojziyFywE0eF1mnMJdJnubZCX6Hs')
HOTEL_SEARCH_RADIUS_KM = 10  # Radius to search for hotels near route
MAX_HOTELS_TO_RETURN = 10     # Limit number of hotels returned

# CO2 emission factors (kg CO2 per km)
EMISSION_FACTORS = {
    'driving': 0.192,    # Average petrol car
    'bicycling': 0.0,
    'walking': 0.0,
    'transit': 0.105,    # Average bus/train
    'train': 0.035,      # Electric train
    'bus': 0.105,        # Average bus
    'motorcycle': 0.103, # Average motorcycle
    'electric_car': 0.053 # Electric vehicle
}

# ----------------------
# Utility Functions
# ----------------------
def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in km using Haversine formula"""
    R = 6371.0  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def calculate_co2(distance_km, mode):
    """Calculate CO2 emissions for a given distance and travel mode"""
    factor = EMISSION_FACTORS.get(mode, 0.192)  # Default to car if mode unknown
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

def get_route_midpoint(poly_points):
    """Calculate midpoint of a route from polyline points"""
    if not poly_points:
        return None
    
    # Simple approach: take middle point of polyline
    mid_idx = len(poly_points) // 2
    return poly_points[mid_idx]

def find_nearby_hotels(lat, lng, radius_km):
    """Query database for hotels near given coordinates"""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Haversine formula in SQL to find hotels within radius
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
            WHERE is_approved = 1
            HAVING distance < %s
            ORDER BY distance
            LIMIT %s
        """
        cursor.execute(query, (lat, lng, lat, radius_km, MAX_HOTELS_TO_RETURN))
        hotels = cursor.fetchall()
        
        # Convert Decimal to float for JSON serialization
        for hotel in hotels:
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

# ----------------------
# Main Endpoint
# ----------------------
@plan_trip_bp.route('/plan_trip', methods=['POST'])
def plan_trip():
    """
    Plan an eco-friendly trip between two locations
    
    Request JSON:
    {
        "start": {"lat": 6.9271, "lng": 79.8612} or "Colombo, Sri Lanka",
        "end": {"lat": 7.2906, "lng": 80.6337} or "Kandy, Sri Lanka",
        "travel_date": "2023-12-15" (optional),
        "travel_time": "08:00" (optional)
    }
    
    Response:
    {
        "status": "success",
        "routes": [
            {
                "mode": "driving",
                "distance_km": 115.5,
                "duration_min": 180,
                "co2_kg": 22.2,
                "polyline": "encoded_polyline_string",
                "poly_points": [{"lat":..., "lng":...}, ...]
            },
            ...
        ],
        "hotels": [
            {
                "id": 1,
                "title": "Eco Hotel",
                "price": 100,
                "distance_from_route_km": 2.5,
                "eco_cert_url": "...",
                ...
            }
        ],
        "recommendations": {
            "fastest": {"mode": "driving", ...},
            "eco_friendliest": {"mode": "train", ...},
            "cheapest": {"mode": "bus", ...}
        }
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    
    # Validate input
    start = data.get('start')
    end = data.get('end')
    if not start or not end:
        return jsonify({"error": "Both start and end locations are required"}), 400
    
    # Optional travel date/time
    travel_date = data.get('travel_date')
    travel_time = data.get('travel_time')
    departure_time = None
    
    if travel_date and travel_time:
        try:
            departure_time = datetime.strptime(f"{travel_date} {travel_time}", "%Y-%m-%d %H:%M")
        except ValueError:
            pass
    
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
        
        if departure_time and mode != 'walking' and mode != 'bicycling':
            params['departure_time'] = 'now' if departure_time <= datetime.now() else departure_time.timestamp()
        
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
    
    # Find hotels near the midpoint of the primary route
    primary_route = routes[0]
    midpoint = get_route_midpoint(primary_route['poly_points'])
    hotels = []
    
    if midpoint:
        hotels = find_nearby_hotels(midpoint['lat'], midpoint['lng'], HOTEL_SEARCH_RADIUS_KM)
    
    # Generate recommendations
    fastest = min(routes, key=lambda x: x['duration_min'])
    eco_friendliest = min(routes, key=lambda x: x['co2_kg'])
    
    # For demo purposes, assume cheapest is bus or train
    cheapest = None
    for route in routes:
        if route['mode'] in ['bus', 'transit']:
            cheapest = route
            break
    if not cheapest:
        cheapest = min(routes, key=lambda x: x['co2_kg'])  # Fallback
    
    return jsonify({
        "status": "success",
        "routes": routes,
        "hotels": hotels,
        "recommendations": {
            "fastest": fastest,
            "eco_friendliest": eco_friendliest,
            "cheapest": cheapest
        }
    })