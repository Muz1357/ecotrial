from flask import Blueprint, request, jsonify, current_app
import cloudinary.uploader
from models.db import get_connection
from models.listing import Listing
from config import ALLOWED_EXTENSIONS, GOOGLE_MAPS_API_KEY  
import requests

listing_bp = Blueprint('listing', __name__)

def geocode_location(location):
    try:
        base_url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            'address': location,
            'key': "AIzaSyA0kovojziyFywE0eF1mnMJdJnubZCX6Hs"
        }
        
        response = requests.get(base_url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data['status'] == 'OK' and data.get('results'):
            location_data = data['results'][0]['geometry']['location']
            return {
                'latitude': location_data['lat'],
                'longitude': location_data['lng'],
                'formatted_address': data['results'][0]['formatted_address']
            }
        current_app.logger.error(f"Geocoding failed for {location}: {data.get('status')}")
        return None
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Geocoding API error for {location}: {str(e)}")
        return None
    except Exception as e:
        current_app.logger.error(f"Unexpected geocoding error for {location}: {str(e)}")
        return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@listing_bp.route('/listings', methods=['GET'])
def get_listings():
    try:
        lat = request.args.get('lat', type=float)
        lng = request.args.get('lng', type=float)
        radius_km = request.args.get('radius_km', 5, type=float)
        
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        if lat and lng:
            query = """
            SELECT 
                id, title, description, price, 
                rooms_available, room_details, 
                latitude, longitude, eco_cert_url,
                (6371 * acos(
                    cos(radians(%s)) * cos(radians(latitude)) *
                    cos(radians(longitude) - radians(%s)) +
                    sin(radians(%s)) * sin(radians(latitude))
                )) AS distance
            FROM listing
            WHERE is_approved = 1
            AND latitude IS NOT NULL
            AND longitude IS NOT NULL
            HAVING distance <= %s
            ORDER BY distance
            LIMIT 20
            """
            cursor.execute(query, (lat, lng, lat, radius_km))
        else:
            cursor.execute("""
                SELECT * FROM listing 
                WHERE is_approved = 1
                AND latitude IS NOT NULL
                AND longitude IS NOT NULL
                LIMIT 20
            """)

        listings = cursor.fetchall()
        
        
        for listing in listings:
            if 'distance' in listing:
                listing['distance'] = float(listing['distance'])
            listing['latitude'] = float(listing['latitude'])
            listing['longitude'] = float(listing['longitude'])
        
        return jsonify({
            "status": "success",
            "count": len(listings),
            "listings": listings
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
        
    finally:
        cursor.close()
        connection.close()


@listing_bp.route('/upload-listing', methods=['POST'])
def upload_listing():
    try:
        
        required_fields = {
            'user_id': request.form.get('user_id'),
            'title': request.form.get('title'),
            'description': request.form.get('description'),
            'price': request.form.get('price'),
            'location': request.form.get('location'),
            'rooms_available': request.form.get('rooms'),
            'room_details': request.form.get('room_details')
        }
        
        
        image_file = request.files.get('image')
        cert_file = request.files.get('eco_cert')

        if not all(required_fields.values()) or not image_file or not cert_file:
            missing = [k for k, v in required_fields.items() if not v]
            if not image_file:
                missing.append('image')
            if not cert_file:
                missing.append('eco_cert')
            return jsonify({
                "error": "Missing required fields",
                "missing": missing
            }), 400

        
        search_query = f"{required_fields['title']}, {required_fields['location']}"
        geo_data = geocode_location(search_query)
        if not geo_data:
            return jsonify({
                "error": "Could not determine location coordinates",
                "details": "Please check the address and try again"
            }), 400

        
        try:
            image_upload = cloudinary.uploader.upload(image_file)
            cert_upload = cloudinary.uploader.upload(cert_file)
            image_url = image_upload.get('secure_url')
            cert_url = cert_upload.get('secure_url')
        except Exception as upload_error:
            current_app.logger.error(f"Media upload failed: {str(upload_error)}")
            return jsonify({
                "error": "Failed to upload media files",
                "details": str(upload_error)
            }), 500

        
        listing = Listing(
            user_id=required_fields['user_id'],
            title=required_fields['title'],
            description=required_fields['description'],
            price=required_fields['price'],
            location=geo_data.get('formatted_address', search_query),
            latitude=geo_data['latitude'],
            longitude=geo_data['longitude'],
            image_url=image_url,
            eco_cert_url=cert_url,
            rooms_available=required_fields['rooms_available'],
            room_details=required_fields['room_details'],
            is_approved=False
        )
        
        listing.save()

        return jsonify({
            "message": "Listing uploaded successfully",
            "location_details": {
                "original_input": required_fields['location'],
                "formatted_address": geo_data.get('formatted_address'),
                "coordinates": {
                    "lat": geo_data['latitude'],
                    "lng": geo_data['longitude']
                }
            },
            "media": {
                "image_url": image_url,
                "eco_cert_url": cert_url
            }
        }), 201

    except Exception as e:
        current_app.logger.error(f"Listing upload failed: {str(e)}")
        return jsonify({
            "error": "Failed to create listing",
            "details": str(e)
        }), 500

@listing_bp.route('/listings/<int:listing_id>', methods=['GET'])
def get_listing_by_id(listing_id):
    listing = Listing.get_listing_by_id(listing_id)
    if listing:
        return jsonify(listing), 200
    else:
        return jsonify({"error": "Listing not found"}), 404

@listing_bp.route('/nearby', methods=['POST'])
def get_hotels_near_route():
    data = request.json
    route_points = data.get("route", [])  

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM listing WHERE approved=1")
    listings = cursor.fetchall()
    nearby_hotels = []

    
    for hotel in listings:
        hotel_lat = float(hotel['latitude'])
        hotel_lng = float(hotel['longitude'])
        for point in route_points:
            
            dist = ((hotel_lat - point['lat'])**2 + (hotel_lng - point['lng'])**2)**0.5
            if dist < 0.1:  
                nearby_hotels.append(hotel)
                break
    cursor.close()
    conn.close()
    return jsonify(nearby_hotels)

def get_recommended_listings(user_id):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Get user's most recent booking location
        cursor.execute("""
            SELECT l.location
            FROM booking b
            JOIN listing l ON b.listing_id = l.id
            WHERE b.tourist_id = %s AND b.is_cancelled = 0
            ORDER BY b.created_at DESC
            LIMIT 1
        """, (user_id,))
        
        recent_booking = cursor.fetchone()
        
        if recent_booking:
            full_location = recent_booking['location']
            print(f"User {user_id} last booked in: {full_location}")
            
            # Extract city name - look for common Sri Lankan cities
            city_keywords = ['trincomalee', 'colombo', 'kandy', 'galle', 'jaffna', 'negombo', 'batticaloa', 'anuradhapura', 'polonnaruwa', 'matara', 'hambantota']
            
            main_location = None
            for city in city_keywords:
                if city in full_location.lower():
                    main_location = city
                    break
            
            # If no city found, try to extract any word longer than 4 characters
            if not main_location:
                words = full_location.lower().split()
                for word in words:
                    clean_word = word.strip('.,!?;:()[]{}"\'+')
                    if len(clean_word) > 4 and not clean_word.isdigit():
                        main_location = clean_word
                        break
            
            print(f"Main location to search: {main_location}")
            
            recommendations = []
            
            if main_location:
                # Search with case-insensitive matching
                # Option 1: Use LOWER on both sides
                cursor.execute("""
                    SELECT l.*, 
                           'last_location' as recommendation_type,
                           100 as match_score
                    FROM listing l
                    WHERE l.is_approved = 1 
                    AND (LOWER(l.location) LIKE LOWER(%s) OR LOWER(l.title) LIKE LOWER(%s))
                    LIMIT 10
                """, (f'%{main_location}%', f'%{main_location}%'))
                
                recommendations = cursor.fetchall()
                print(f"Found {len(recommendations)} listings matching: {main_location}")
                
                # If still no results, try searching with capitalized first letter
                if len(recommendations) == 0:
                    capitalized_location = main_location.capitalize()
                    cursor.execute("""
                        SELECT l.*, 
                               'last_location' as recommendation_type,
                               100 as match_score
                        FROM listing l
                        WHERE l.is_approved = 1 
                        AND (l.location LIKE %s OR l.title LIKE %s)
                        LIMIT 10
                    """, (f'%{capitalized_location}%', f'%{capitalized_location}%'))
                    
                    recommendations = cursor.fetchall()
                    print(f"Found {len(recommendations)} listings matching capitalized: {capitalized_location}")
            
            # If still no results, get ANY approved listings
            if len(recommendations) == 0:
                cursor.execute("""
                    SELECT l.*, 
                           'popular' as recommendation_type,
                           50 as match_score
                    FROM listing l
                    WHERE l.is_approved = 1
                    LIMIT 10
                """)
                
                recommendations = cursor.fetchall()
                print(f"Using {len(recommendations)} approved listings as fallback")
            
            return recommendations
        
        else:
            # New user - show any approved listings
            cursor.execute("""
                SELECT l.*, 
                       'new_user' as recommendation_type,
                       0 as match_score
                FROM listing l
                WHERE l.is_approved = 1
                LIMIT 10
            """)
            return cursor.fetchall()
            
    except Exception as e:
        current_app.logger.error(f"Error in get_recommended_listings for user {user_id}: {str(e)}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return []
    finally:
        cursor.close()
        connection.close()

def get_popular_listings(limit=20):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT l.*
            FROM listing l
            WHERE l.is_approved = 1
            ORDER BY RAND()
            LIMIT %s
        """, (limit,))
        listings = cursor.fetchall()
        return listings
    finally:
        cursor.close()
        connection.close()

@listing_bp.route('/home-listings', methods=['GET'])
def home_listings():
    user_id = request.args.get('user_id', type=int)

    try:
        recommended = get_recommended_listings(user_id) if user_id else []
        popular = get_popular_listings()
        return jsonify({
            "status": "success",
            "recommended": recommended,
            "popular": popular
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# REMOVE THE DUPLICATE get_recommended_listings FUNCTION FROM THE BOTTOM!
# Delete everything from "def get_recommended_listings(user_id):" line 484 onwards