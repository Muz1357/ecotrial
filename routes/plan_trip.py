# routes/plan_trip.py
import os
import math
import requests
from flask import Blueprint, request, jsonify, current_app
from models.db import get_connection

plan_trip_bp = Blueprint('plan_trip', __name__)

# ----------------------
# CO2 emission factors (kg CO2 per km)
# ----------------------
EMISSION_FACTORS = {
    'driving': 0.192,    # car
    'bicycling': 0.0,
    'walking': 0.0,
    'transit': 0.07      # approximate avg for mixed transit (train+bus). Tweak as needed.
}

def co2_for_mode(distance_km, mode):
    factor = EMISSION_FACTORS.get(mode, 0.192)
    return round(distance_km * factor, 6)

# ----------------------
# Geo helpers
# ----------------------
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def min_distance_to_polyline_km(lat, lng, poly_points):
    """Return min distance (km) from point to vertices of polyline_points (list of {'lat','lng'})."""
    if not poly_points:
        return float('inf')
    m = float('inf')
    for p in poly_points:
        try:
            d = haversine_km(lat, lng, float(p['lat']), float(p['lng']))
            if d < m:
                m = d
        except Exception:
            continue
    return m

def decode_polyline(polyline_str):
    if not polyline_str:
        return []
    index = 0
    lat = 0
    lng = 0
    coordinates = []
    length = len(polyline_str)
    while index < length:
        shift = 0
        result = 0
        while True:
            b = ord(polyline_str[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        shift = 0
        result = 0
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

# ----------------------
# Utility: parse coordinate-like string "lat,lng"
# ----------------------
def parse_latlng_from_string(s):
    if not s or not isinstance(s, str):
        return None
    parts = s.split(',')
    if len(parts) < 2:
        return None
    try:
        lat = float(parts[0].strip())
        lng = float(parts[1].strip())
        return {'lat': lat, 'lng': lng}
    except Exception:
        return None

# ----------------------
# Optional geocode (only used if GEOCODE_LISTINGS=true); uses Google Geocoding API
# ----------------------
def geocode_address(address):
    key = os.getenv('GOOGLE_MAPS_API_KEY', '')
    if not key:
        return None
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    try:
        r = requests.get(url, params={'address': address, 'key': key}, timeout=8)
        if r.status_code != 200:
            return None
        j = r.json()
        if j.get('status') != 'OK' or not j.get('results'):
            return None
        loc = j['results'][0]['geometry']['location']
        return {'lat': float(loc['lat']), 'lng': float(loc['lng'])}
    except Exception:
        return None

# ----------------------
# Main endpoint: /api/plan_trip
# ----------------------
@plan_trip_bp.route('/plan_trip', methods=['POST'])
def plan_trip():
    """
    Input JSON:
    {
      "start": "Colombo, Sri Lanka"  OR {"lat":6.9271, "lng":79.8612},
      "end":   "Kandy, Sri Lanka"    OR {"lat":6.8040, "lng":81.3675},
      // optional:
      "stops": [ {"lat":..., "lng":...}, ... ]
    }

    Response:
    {
      "routes": [
        {"mode":"driving","distance_km":..,"duration_sec":..,"duration_text":"..","co2_kg":.., "poly_points":[...]}
        ...
      ],
      "nearby_listings": [ {id,title,price,rooms_available,room_details,eco_cert_url,location,latitude,longitude,distance_from_route_km}, ... ],
      "recommended": { "fastest": mode, "eco": mode }
    }
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    # read input start & end (accept address string or lat/lng object)
    start = data.get('start')
    end = data.get('end')
    stops = data.get('stops', [])

    if not start or not end:
        return jsonify({'error': 'start and end required'}), 400

    # if given as object with lat/lng, use, else assume address string
    def resolve_input_point(p):
        if isinstance(p, dict) and 'lat' in p and 'lng' in p:
            try:
                return {'lat': float(p['lat']), 'lng': float(p['lng'])}
            except Exception:
                return None
        if isinstance(p, str):
            # treat as address string (do not geocode here — pass address to Directions API)
            return p
        return None

    origin = resolve_input_point(start)
    destination = resolve_input_point(end)
    if origin is None or destination is None:
        return jsonify({'error': 'start/end must be address string or object with lat & lng'}), 400

    # list of travel modes to ask Google Directions for
    modes = ['driving', 'transit', 'bicycling', 'walking']

    google_key = os.getenv('GOOGLE_MAPS_API_KEY', '')
    if not google_key:
        return jsonify({'error': 'GOOGLE_MAPS_API_KEY env var is required'}), 500

    # Build waypoints string if stops present and are lat/lng pairs
    waypoints = None
    if stops and isinstance(stops, list):
        # only include stops that are dicts with lat/lng
        wp_list = []
        for s in stops:
            if isinstance(s, dict) and 'lat' in s and 'lng' in s:
                wp_list.append(f"{float(s['lat'])},{float(s['lng'])}")
        if wp_list:
            waypoints = '|'.join(wp_list)

    routes_out = []
    first_poly_points = []  # keep polyline of first successful route to search hotels against
    # call Directions for each mode (we will skip modes that return ZERO_RESULTS)
    for mode in modes:
        params = {
            'key': google_key,
            'mode': mode,
            'alternatives': 'false'  # we only need 1 best route per mode
        }
        if isinstance(origin, dict):
            params['origin'] = f"{origin['lat']},{origin['lng']}"
        else:
            params['origin'] = origin  # address string
        if isinstance(destination, dict):
            params['destination'] = f"{destination['lat']},{destination['lng']}"
        else:
            params['destination'] = destination

        if waypoints:
            params['waypoints'] = waypoints

        try:
            resp = requests.get("https://maps.googleapis.com/maps/api/directions/json", params=params, timeout=12)
        except Exception as e:
            current_app.logger.exception("Directions request failed")
            continue

        if resp.status_code != 200:
            current_app.logger.error(f"Directions API error {resp.status_code}: {resp.text}")
            continue

        j = resp.json()
        status = j.get('status')
        if status != 'OK':
            # skip modes with no results
            continue

        route = j.get('routes', [])[0]  # take the first route
        legs = route.get('legs', [])
        total_m = 0
        total_sec = 0
        legs_info = []
        for leg in legs:
            d = leg.get('distance', {}).get('value', 0)
            t = leg.get('duration', {}).get('value', 0)
            total_m += d
            total_sec += t
            # try to extract start/end coords of the leg from steps (if present)
            s_lat = None; s_lng = None; e_lat = None; e_lng = None
            steps = leg.get('steps', [])
            if steps:
                try:
                    s0 = steps[0].get('start_location', {})
                    e0 = steps[-1].get('end_location', {})
                    s_lat = s0.get('lat'); s_lng = s0.get('lng')
                    e_lat = e0.get('lat'); e_lng = e0.get('lng')
                except Exception:
                    pass
            legs_info.append({
                'start_address': leg.get('start_address'),
                'end_address': leg.get('end_address'),
                'distance_km': round(d / 1000.0, 6),
                'duration_sec': t,
                'start_lat': s_lat, 'start_lng': s_lng,
                'end_lat': e_lat, 'end_lng': e_lng
            })

        distance_km = round(total_m / 1000.0, 6)
        duration_sec = total_sec
        co2 = co2_for_mode(distance_km, mode)

        overview_poly = route.get('overview_polyline', {}).get('points')
        poly_points = decode_polyline(overview_poly) if overview_poly else []

        # remember first poly_points for hotel search if none other set yet
        if not first_poly_points and poly_points:
            first_poly_points = poly_points

        routes_out.append({
            'mode': mode,
            'distance_km': distance_km,
            'duration_sec': duration_sec,
            'duration_text': leg.get('duration', {}).get('text') if legs else None,
            'co2_kg': co2,
            'legs': legs_info,
            'polyline': overview_poly,
            'poly_points': poly_points[:500]  # cap size
        })

    if not routes_out:
        return jsonify({'error': 'No route alternatives found for provided start/end'}), 400

    # determine recommended modes
    # fastest = mode with smallest duration_sec; eco = mode with smallest co2_kg
    fastest = min(routes_out, key=lambda r: r['duration_sec'])
    eco = min(routes_out, key=lambda r: r['co2_kg'])

    # ----------------------
    # Find nearby approved listings (hotels) based on first_poly_points
    # ----------------------
    PROX_KM = float(os.getenv('HOTEL_PROX_KM', '10'))
    geocode_listings = os.getenv('GEOCODE_LISTINGS', 'false').lower() in ('1','true','yes')
    nearby_listings = []

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        # select fields you provided in schema
        cursor.execute("SELECT id, user_id, title, description, image_path, is_approved, price, location, rooms_available, room_details, eco_cert_url FROM listing WHERE is_approved=1")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as e:
        current_app.logger.exception("DB error loading listings")
        rows = []

    # choose which polyline to use (prefer driving if available)
    chosen_poly = None
    for r in routes_out:
        if r['mode'] == 'driving' and r['poly_points']:
            chosen_poly = r['poly_points']
            break
    if not chosen_poly:
        chosen_poly = first_poly_points

    for h in rows:
        try:
            # Try to get coordinates from listing: prefer 'latitude'/'longitude' if columns exist (safe access)
            lat = None; lng = None
            if 'latitude' in h and 'longitude' in h and h.get('latitude') is not None and h.get('longitude') is not None:
                lat = float(h['latitude']); lng = float(h['longitude'])
            else:
                # try parse `location` as "lat,lng"
                parsed = parse_latlng_from_string(h.get('location'))
                if parsed:
                    lat = parsed['lat']; lng = parsed['lng']
                elif geocode_listings and h.get('location'):
                    geo = geocode_address(h.get('location'))
                    if geo:
                        lat = geo['lat']; lng = geo['lng']
            if lat is None or lng is None:
                continue

            d = min_distance_to_polyline_km(lat, lng, chosen_poly)
            if d <= PROX_KM:
                nearby_listings.append({
                    'id': h.get('id'),
                    'title': h.get('title'),
                    'description': h.get('description'),
                    'image_path': h.get('image_path'),
                    'price': h.get('price'),
                    'rooms_available': h.get('rooms_available'),
                    'room_details': h.get('room_details'),
                    'eco_cert_url': h.get('eco_cert_url'),
                    'location': h.get('location'),
                    'latitude': lat,
                    'longitude': lng,
                    'distance_from_route_km': round(d, 4)
                })
        except Exception:
            continue

    # Optional: sort nearby listings by distance_from_route_km (closest first)
    nearby_listings.sort(key=lambda x: x.get('distance_from_route_km', 9999))

    response = {
        'routes': routes_out,
        'nearby_listings': nearby_listings,
        'recommended': {
            'fastest': fastest['mode'],
            'eco': eco['mode']
        }
    }
    return jsonify(response)
