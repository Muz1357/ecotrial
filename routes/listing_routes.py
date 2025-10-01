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
        # Get user's detailed booking history and preferences
        cursor.execute("""
            SELECT 
                l.location,
                l.room_details,
                l.price,
                l.id as listing_id,
                COUNT(b.id) as booking_count,
                AVG(b.points_earned) as avg_points_earned
            FROM booking b
            JOIN listing l ON b.listing_id = l.id
            WHERE b.tourist_id = %s AND b.is_cancelled = 0
            GROUP BY l.location, l.room_details, l.price, l.id
            ORDER BY booking_count DESC
            LIMIT 10
        """, (user_id,))
        
        user_booking_history = cursor.fetchall()
        
        if user_booking_history:
            # Calculate user preferences
            favorite_locations = [booking['location'] for booking in user_booking_history[:3]]
            price_range = calculate_user_price_range(user_booking_history)
            preferred_room_types = extract_room_preferences(user_booking_history)
            
            # Build personalized recommendation query
            recommendations = []
            
            # Strategy 1: Similar listings in favorite locations
            if favorite_locations:
                placeholders = ','.join(['%s'] * len(favorite_locations))
                cursor.execute(f"""
                    SELECT l.*, 
                           3 as location_match_score,
                           (CASE WHEN l.price BETWEEN %s AND %s THEN 2 ELSE 0 END) as price_match_score,
                           COUNT(b.id) as total_bookings
                    FROM listing l
                    LEFT JOIN booking b ON l.id = b.listing_id
                    WHERE l.is_approved = 1 
                    AND l.location IN ({placeholders})
                    AND l.id NOT IN (
                        SELECT listing_id FROM booking 
                        WHERE tourist_id = %s AND is_cancelled = 0
                    )
                    GROUP BY l.id
                    ORDER BY (location_match_score + price_match_score) DESC, total_bookings DESC
                    LIMIT 6
                """, favorite_locations + [price_range['min'], price_range['max'], user_id])
                
                location_based = cursor.fetchall()
                recommendations.extend(location_based)
            
            # Strategy 2: Similar price range but new locations
            if len(recommendations) < 10:
                cursor.execute("""
                    SELECT l.*, 
                           2 as price_match_score,
                           COUNT(b.id) as total_bookings
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
                    ORDER BY price_match_score DESC, total_bookings DESC
                    LIMIT %s
                """, (
                    price_range['min'] * 0.8,  # Slightly wider range for discovery
                    price_range['max'] * 1.2,
                    user_id,
                    ','.join([str(r['id']) for r in recommendations]) if recommendations else '0',
                    10 - len(recommendations)
                ))
                
                price_based = cursor.fetchall()
                recommendations.extend(price_based)
            
            # Strategy 3: Highly rated listings that match user's earned points pattern
            if len(recommendations) < 10:
                avg_user_points = calculate_avg_user_points(user_booking_history)
                cursor.execute("""
                    SELECT l.*, 
                           AVG(b.points_earned) as avg_points,
                           COUNT(b.id) as total_bookings
                    FROM listing l
                    LEFT JOIN booking b ON l.id = b.listing_id AND b.is_cancelled = 0
                    WHERE l.is_approved = 1 
                    AND l.id NOT IN (
                        SELECT listing_id FROM booking 
                        WHERE tourist_id = %s AND is_cancelled = 0
                    )
                    AND l.id NOT IN (%s)
                    GROUP BY l.id
                    HAVING avg_points BETWEEN %s AND %s
                    ORDER BY total_bookings DESC, avg_points DESC
                    LIMIT %s
                """, (
                    user_id,
                    ','.join([str(r['id']) for r in recommendations]) if recommendations else '0',
                    avg_user_points * 0.7,
                    avg_user_points * 1.3,
                    10 - len(recommendations)
                ))
                
                points_based = cursor.fetchall()
                recommendations.extend(points_based)
                
            return recommendations[:10]
        
        else:
            # New user - show diverse popular listings
            cursor.execute("""
                SELECT l.*, COUNT(b.id) as total_bookings,
                       'new_user' as recommendation_type
                FROM listing l
                LEFT JOIN booking b ON l.id = b.listing_id
                WHERE l.is_approved = 1
                GROUP BY l.id
                ORDER BY total_bookings DESC, RAND()
                LIMIT 10
            """)
            return cursor.fetchall()
            
    except Exception as e:
        current_app.logger.error(f"Error in get_recommended_listings: {str(e)}")
        return []
    finally:
        cursor.close()
        connection.close()

def calculate_user_price_range(booking_history):
    if not booking_history:
        return {'min': 0, 'max': 1000}
    
    prices = [float(booking['price']) for booking in booking_history if booking['price']]
    if not prices:
        return {'min': 0, 'max': 1000}
    
    return {
        'min': max(0, min(prices) * 0.7),
        'max': max(prices) * 1.3
    }

def extract_room_preferences(booking_history):
    room_details = [booking['room_details'] for booking in booking_history if booking['room_details']]
    # Simple keyword extraction - you can enhance this
    keywords = []
    for detail in room_details:
        if 'sea' in detail.lower() or 'ocean' in detail.lower():
            keywords.append('sea_view')
        if 'mountain' in detail.lower():
            keywords.append('mountain_view')
        if 'garden' in detail.lower():
            keywords.append('garden_view')
    return list(set(keywords))

def calculate_avg_user_points(booking_history):
    points = [booking['avg_points_earned'] for booking in booking_history if booking['avg_points_earned']]
    return sum(points) / len(points) if points else 50

@listing_bp.route('/user-recommendation-insights', methods=['GET'])
def get_user_recommendation_insights():
    user_id = request.args.get('user_id', type=int)
    
    if not user_id:
        return jsonify({"error": "User ID required"}), 400
    
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Get user's detailed booking patterns
        cursor.execute("""
            SELECT 
                COUNT(b.id) as total_bookings,
                AVG(b.points_earned) as avg_points_per_booking,
                MIN(b.created_at) as first_booking_date,
                MAX(b.created_at) as last_booking_date
            FROM booking b
            WHERE b.tourist_id = %s AND b.is_cancelled = 0
        """, (user_id,))
        
        booking_stats = cursor.fetchone()
        
        # Get top locations with details
        cursor.execute("""
            SELECT 
                l.location,
                COUNT(b.id) as visit_count,
                AVG(l.price) as avg_price_in_location,
                AVG(b.points_earned) as avg_points_earned
            FROM booking b
            JOIN listing l ON b.listing_id = l.id
            WHERE b.tourist_id = %s AND b.is_cancelled = 0
            GROUP BY l.location
            ORDER BY visit_count DESC
            LIMIT 3
        """, (user_id,))
        
        top_locations = cursor.fetchall()
        
        # Get booking frequency pattern
        cursor.execute("""
            SELECT 
                DATE_FORMAT(b.created_at, '%%Y-%%m') as month,
                COUNT(b.id) as bookings_count
            FROM booking b
            WHERE b.tourist_id = %s AND b.is_cancelled = 0
            GROUP BY DATE_FORMAT(b.created_at, '%%Y-%%m')
            ORDER BY month DESC
            LIMIT 6
        """, (user_id,))
        
        booking_pattern = cursor.fetchall()
        
        return jsonify({
            "status": "success",
            "user_id": user_id,
            "booking_stats": booking_stats,
            "top_locations": top_locations,
            "booking_pattern": booking_pattern,
            "personalization_level": "high" if booking_stats['total_bookings'] > 2 else "medium" if booking_stats['total_bookings'] > 0 else "low"
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        connection.close()