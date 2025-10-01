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
        
        cursor.execute("""
            SELECT l.location, COUNT(b.id) as location_count
            FROM booking b
            JOIN listing l ON b.listing_id = l.id
            WHERE b.tourist_id = %s
            GROUP BY l.location
            ORDER BY location_count DESC
            LIMIT 1
        """, (user_id,))
        
        favorite_location = cursor.fetchone()
        
        if favorite_location:
            
            cursor.execute("""
                SELECT l.* 
                FROM listing l
                WHERE l.location = %s AND l.is_approved = 1
                ORDER BY RAND()
                LIMIT 10
            """, (favorite_location['location'],))
        else:
            
            cursor.execute("""
                SELECT l.* 
                FROM listing l
                WHERE l.is_approved = 1
                ORDER BY RAND()
                LIMIT 10
            """)
        
        listings = cursor.fetchall()
        return listings
    finally:
        cursor.close()
        connection.close()


def get_popular_listings(limit=20):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT l.*, COUNT(b.id) AS booking_count
            FROM listing l
            LEFT JOIN booking b ON l.id = b.listing_id
            WHERE l.is_approved = 1
            GROUP BY l.id
            ORDER BY booking_count DESC
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

def get_recommended_listings(user_id):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        
        cursor.execute("""
            SELECT 
                l.location,
                l.room_details,
                l.price_range,
                COUNT(b.id) as booking_count
            FROM booking b
            JOIN listing l ON b.listing_id = l.id
            WHERE b.tourist_id = %s AND b.is_cancelled = 0
            GROUP BY l.location, l.room_details, l.price_range
            ORDER BY booking_count DESC
            LIMIT 5
        """, (user_id,))
        
        user_preferences = cursor.fetchall()
        
        if user_preferences:
            
            recommendations = []
            
            
            favorite_location = user_preferences[0]['location']
            cursor.execute("""
                SELECT l.*, 
                       (CASE WHEN l.location = %s THEN 3 ELSE 0 END) as location_score,
                       (CASE WHEN l.room_details LIKE %s THEN 2 ELSE 0 END) as room_score,
                       COUNT(b.id) as popularity_score
                FROM listing l
                LEFT JOIN booking b ON l.id = b.listing_id
                WHERE l.is_approved = 1 
                AND l.id NOT IN (
                    SELECT listing_id FROM booking 
                    WHERE tourist_id = %s AND is_cancelled = 0
                )
                GROUP BY l.id
                ORDER BY (location_score + room_score + popularity_score) DESC
                LIMIT 10
            """, (favorite_location, f"%{user_preferences[0].get('room_details', '')}%", user_id))
            
            location_based = cursor.fetchall()
            recommendations.extend(location_based)
            
            
            if len(recommendations) < 10:
                cursor.execute("""
                    SELECT l.*, COUNT(b.id) as popularity_score
                    FROM listing l
                    LEFT JOIN booking b ON l.id = b.listing_id
                    WHERE l.is_approved = 1 
                    AND l.price BETWEEN %s AND %s
                    AND l.id NOT IN (
                        SELECT listing_id FROM booking 
                        WHERE tourist_id = %s AND is_cancelled = 0
                    )
                    AND l.id NOT IN (%s)
                    GROUP BY l.id
                    ORDER BY popularity_score DESC
                    LIMIT %s
                """, (
                    max(0, float(user_preferences[0].get('price', 0)) * 0.7),
                    float(user_preferences[0].get('price', 0)) * 1.3,
                    user_id,
                    ','.join([str(r['id']) for r in recommendations]) if recommendations else '0',
                    10 - len(recommendations)
                ))
                
                price_based = cursor.fetchall()
                recommendations.extend(price_based)
            
            
            if len(recommendations) < 10:
                cursor.execute("""
                    SELECT l.*, COUNT(b.id) as booking_count
                    FROM listing l
                    LEFT JOIN booking b ON l.id = b.listing_id
                    WHERE l.is_approved = 1 
                    AND l.id NOT IN (
                        SELECT listing_id FROM booking 
                        WHERE tourist_id = %s AND is_cancelled = 0
                    )
                    AND l.id NOT IN (%s)
                    GROUP BY l.id
                    ORDER BY booking_count DESC
                    LIMIT %s
                """, (
                    user_id,
                    ','.join([str(r['id']) for r in recommendations]) if recommendations else '0',
                    10 - len(recommendations)
                ))
                
                popular_fallback = cursor.fetchall()
                recommendations.extend(popular_fallback)
                
            return recommendations[:10]  
        
        else:
           
            cursor.execute("""
                SELECT l.*, COUNT(b.id) as booking_count
                FROM listing l
                LEFT JOIN booking b ON l.id = b.listing_id
                WHERE l.is_approved = 1
                GROUP BY l.id
                ORDER BY booking_count DESC
                LIMIT 10
            """)
            return cursor.fetchall()
            
    except Exception as e:
        current_app.logger.error(f"Error in get_recommended_listings: {str(e)}")
        
        cursor.execute("""
            SELECT l.*, COUNT(b.id) as booking_count
            FROM listing l
            LEFT JOIN booking b ON l.id = b.listing_id
            WHERE l.is_approved = 1
            GROUP BY l.id
            ORDER BY booking_count DESC
            LIMIT 10
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def get_popular_listings(limit=20):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        
        cursor.execute("""
            SELECT 
                l.*, 
                COUNT(b.id) AS total_bookings,
                SUM(CASE WHEN b.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) THEN 1 ELSE 0 END) as recent_bookings,
                AVG(b.points_earned) as avg_points_earned
            FROM listing l
            LEFT JOIN booking b ON l.id = b.listing_id AND b.is_cancelled = 0
            WHERE l.is_approved = 1
            GROUP BY l.id
            ORDER BY 
                recent_bookings DESC,
                total_bookings DESC,
                avg_points_earned DESC
            LIMIT %s
        """, (limit,))
        
        listings = cursor.fetchall()
        
        
        for listing in listings:
            total_bookings = listing['total_bookings'] or 0
            recent_bookings = listing['recent_bookings'] or 0
            
            if recent_bookings >= 10:
                listing['popularity_badge'] = '🔥 Trending'
            elif total_bookings >= 50:
                listing['popularity_badge'] = '⭐ Most Popular'
            elif recent_bookings >= 5:
                listing['popularity_badge'] = '📈 Rising'
            else:
                listing['popularity_badge'] = None
                
        return listings
        
    except Exception as e:
        current_app.logger.error(f"Error in get_popular_listings: {str(e)}")
        
        cursor.execute("""
            SELECT l.*, COUNT(b.id) AS booking_count
            FROM listing l
            LEFT JOIN booking b ON l.id = b.listing_id
            WHERE l.is_approved = 1
            GROUP BY l.id
            ORDER BY booking_count DESC
            LIMIT %s
        """, (limit,))
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

