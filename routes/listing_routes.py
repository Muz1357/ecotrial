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
            
            # Extract the main city name - look for the most significant word
            # For Sri Lankan addresses, the city is usually before the postal code
            location_parts = full_location.split(',')
            main_location = None
            
            # Try to find the city name (usually the part before postal code)
            for part in location_parts:
                part = part.strip()
                # Look for parts that don't contain numbers and are not too short
                if (len(part) > 3 and 
                    not any(char.isdigit() for char in part) and
                    part.lower() not in ['sri lanka', 'sri', 'lanka']):
                    words = part.split()
                    for word in words:
                        clean_word = word.strip('.,!?;:()[]{}"\'+').lower()
                        if (len(clean_word) > 3 and 
                            clean_word not in ['post', 'rd', 'road', 'street', 'st'] and
                            not clean_word.isdigit()):
                            main_location = clean_word
                            break
                    if main_location:
                        break
            
            # If no main location found, use the entire location but clean it
            if not main_location:
                # Take the first meaningful word from the location
                words = full_location.split()
                for word in words:
                    clean_word = word.strip('.,!?;:()[]{}"\'+').lower()
                    if (len(clean_word) > 3 and 
                        clean_word not in ['post', 'rd', 'road', 'street', 'st', 'sri', 'lanka'] and
                        not clean_word.isdigit()):
                        main_location = clean_word
                        break
            
            print(f"Main location to search: {main_location}")
            
            recommendations = []
            
            if main_location:
                # Simple query without complex joins or subqueries
                cursor.execute("""
                    SELECT l.*, 
                           'last_location' as recommendation_type,
                           100 as match_score
                    FROM listing l
                    WHERE l.is_approved = 1 
                    AND LOWER(l.location) LIKE %s
                    AND l.id NOT IN (
                        SELECT DISTINCT listing_id 
                        FROM booking 
                        WHERE tourist_id = %s AND is_cancelled = 0
                    )
                    LIMIT 10
                """, (f'%{main_location}%', user_id))
                
                recommendations = cursor.fetchall()
                print(f"Found {len(recommendations)} listings matching: {main_location}")
            
            # If still no results, try a broader search
            if not recommendations:
                # Get any listings from approved locations
                cursor.execute("""
                    SELECT l.*, 
                           'popular' as recommendation_type,
                           50 as match_score
                    FROM listing l
                    WHERE l.is_approved = 1 
                    AND l.id NOT IN (
                        SELECT DISTINCT listing_id 
                        FROM booking 
                        WHERE tourist_id = %s AND is_cancelled = 0
                    )
                    ORDER BY RAND()
                    LIMIT 10
                """, (user_id,))
                
                recommendations = cursor.fetchall()
                print(f"Using {len(recommendations)} popular listings as fallback")
            
            return recommendations
        
        else:
            # New user - show popular listings
            cursor.execute("""
                SELECT l.*, 
                       'new_user' as recommendation_type,
                       0 as match_score
                FROM listing l
                WHERE l.is_approved = 1
                ORDER BY RAND()
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
        # Get user's detailed booking history
        cursor.execute("""
            SELECT 
                l.id as listing_id,
                l.location,
                l.title,
                l.price,
                l.room_details,
                l.latitude,
                l.longitude,
                COUNT(b.id) as booking_count,
                AVG(b.points_earned) as avg_points_earned
            FROM booking b
            JOIN listing l ON b.listing_id = l.id
            WHERE b.tourist_id = %s AND b.is_cancelled = 0
            GROUP BY l.id, l.location, l.title, l.price, l.room_details, l.latitude, l.longitude
            ORDER BY booking_count DESC
        """, (user_id,))
        
        user_bookings = cursor.fetchall()
        
        if user_bookings:
            # Analyze user preferences
            location_stats = {}
            for booking in user_bookings:
                location = booking['location']
                if location not in location_stats:
                    location_stats[location] = {
                        'count': 0,
                        'avg_price': 0,
                        'listings': []
                    }
                location_stats[location]['count'] += booking['booking_count']
                location_stats[location]['listings'].append(booking)
            
            # Calculate average price per location
            for location in location_stats:
                prices = [float(b['price']) for b in location_stats[location]['listings'] if b['price']]
                location_stats[location]['avg_price'] = sum(prices) / len(prices) if prices else 0
            
            # Find favorite location (most booked)
            favorite_location = max(location_stats.items(), key=lambda x: x[1]['count'])
            fav_location_name = favorite_location[0]
            fav_location_data = favorite_location[1]
            
            print(f"User {user_id} favorite location: {fav_location_name} with {fav_location_data['count']} bookings")
            
            # Get similar listings in the same location but different properties
            cursor.execute("""
                SELECT 
                    l.*,
                    (CASE 
                        WHEN l.location = %s THEN 5 
                        ELSE 0 
                    END) as location_score,
                    (CASE 
                        WHEN l.price BETWEEN %s AND %s THEN 3 
                        ELSE 0 
                    END) as price_score,
                    COUNT(b.id) as total_bookings,
                    'location_based' as recommendation_type
                FROM listing l
                LEFT JOIN booking b ON l.id = b.listing_id AND b.is_cancelled = 0
                WHERE l.is_approved = 1 
                AND l.id NOT IN (
                    SELECT DISTINCT listing_id 
                    FROM booking 
                    WHERE tourist_id = %s AND is_cancelled = 0
                )
                AND l.location = %s
                GROUP BY l.id
                ORDER BY (location_score + price_score) DESC, total_bookings DESC
                LIMIT 6
            """, (
                fav_location_name,
                fav_location_data['avg_price'] * 0.7,  # 30% lower than average
                fav_location_data['avg_price'] * 1.3,  # 30% higher than average
                user_id,
                fav_location_name
            ))
            
            location_based = cursor.fetchall()
            print(f"Found {len(location_based)} location-based recommendations")
            
            # Get listings in nearby locations (if we have coordinates)
            nearby_recommendations = []
            if len(location_based) < 10 and user_bookings[0].get('latitude'):
                # Use the most booked location's coordinates
                ref_lat = user_bookings[0]['latitude']
                ref_lng = user_bookings[0]['longitude']
                
                cursor.execute("""
                    SELECT 
                        l.*,
                        (6371 * acos(
                            cos(radians(%s)) * cos(radians(l.latitude)) *
                            cos(radians(l.longitude) - radians(%s)) +
                            sin(radians(%s)) * sin(radians(l.latitude))
                        )) AS distance,
                        (CASE 
                            WHEN l.price BETWEEN %s AND %s THEN 2 
                            ELSE 0 
                        END) as price_score,
                        COUNT(b.id) as total_bookings,
                        'nearby' as recommendation_type
                    FROM listing l
                    LEFT JOIN booking b ON l.id = b.listing_id AND b.is_cancelled = 0
                    WHERE l.is_approved = 1 
                    AND l.id NOT IN (
                        SELECT DISTINCT listing_id 
                        FROM booking 
                        WHERE tourist_id = %s AND is_cancelled = 0
                    )
                    AND l.id NOT IN (%s)
                    AND l.latitude IS NOT NULL
                    AND l.longitude IS NOT NULL
                    HAVING distance <= 50  -- Within 50km
                    ORDER BY distance ASC, price_score DESC, total_bookings DESC
                    LIMIT %s
                """, (
                    ref_lat, ref_lng, ref_lat,
                    fav_location_data['avg_price'] * 0.7,
                    fav_location_data['avg_price'] * 1.3,
                    user_id,
                    ','.join([str(r['id']) for r in location_based]) if location_based else '0',
                    10 - len(location_based)
                ))
                
                nearby_recommendations = cursor.fetchall()
                print(f"Found {len(nearby_recommendations)} nearby recommendations")
            
            # Combine recommendations
            all_recommendations = location_based + nearby_recommendations
            
            # If still not enough, add popular listings in similar price range
            if len(all_recommendations) < 10:
                cursor.execute("""
                    SELECT 
                        l.*,
                        COUNT(b.id) as total_bookings,
                        'popular_fallback' as recommendation_type
                    FROM listing l
                    LEFT JOIN booking b ON l.id = b.listing_id AND b.is_cancelled = 0
                    WHERE l.is_approved = 1 
                    AND l.id NOT IN (
                        SELECT DISTINCT listing_id 
                        FROM booking 
                        WHERE tourist_id = %s AND is_cancelled = 0
                    )
                    AND l.id NOT IN (%s)
                    AND l.price BETWEEN %s AND %s
                    GROUP BY l.id
                    ORDER BY total_bookings DESC
                    LIMIT %s
                """, (
                    user_id,
                    ','.join([str(r['id']) for r in all_recommendations]) if all_recommendations else '0',
                    fav_location_data['avg_price'] * 0.5,
                    fav_location_data['avg_price'] * 1.5,
                    10 - len(all_recommendations)
                ))
                
                popular_fallback = cursor.fetchall()
                all_recommendations.extend(popular_fallback)
                print(f"Added {len(popular_fallback)} popular fallback recommendations")
            
            return all_recommendations[:10]
        
        else:
            # New user - show diverse popular listings
            cursor.execute("""
                SELECT l.*, COUNT(b.id) as total_bookings,
                       'new_user' as recommendation_type
                FROM listing l
                LEFT JOIN booking b ON l.id = b.listing_id AND b.is_cancelled = 0
                WHERE l.is_approved = 1
                GROUP BY l.id
                ORDER BY total_bookings DESC, RAND()
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
                COUNT(DISTINCT l.location) as unique_locations,
                COUNT(DISTINCT l.id) as unique_listings,
                AVG(b.points_earned) as avg_points_per_booking,
                MIN(b.created_at) as first_booking_date,
                MAX(b.created_at) as last_booking_date
            FROM booking b
            JOIN listing l ON b.listing_id = l.id
            WHERE b.tourist_id = %s AND b.is_cancelled = 0
        """, (user_id,))
        
        booking_stats = cursor.fetchone()
        
        # Get top locations with detailed analytics
        cursor.execute("""
            SELECT 
                l.location,
                COUNT(b.id) as visit_count,
                AVG(CAST(l.price AS DECIMAL)) as avg_price_in_location,
                AVG(b.points_earned) as avg_points_earned,
                COUNT(DISTINCT l.id) as unique_listings_in_location,
                MAX(b.created_at) as last_visit_date
            FROM booking b
            JOIN listing l ON b.listing_id = l.id
            WHERE b.tourist_id = %s AND b.is_cancelled = 0
            GROUP BY l.location
            ORDER BY visit_count DESC
            LIMIT 3
        """, (user_id,))
        
        top_locations = cursor.fetchall()
        
        # Determine personalization level
        total_bookings = booking_stats['total_bookings'] or 0
        if total_bookings >= 3:
            personalization_level = "high"
        elif total_bookings >= 1:
            personalization_level = "medium"
        else:
            personalization_level = "low"
        
        return jsonify({
            "status": "success",
            "user_id": user_id,
            "booking_stats": booking_stats,
            "top_locations": top_locations,
            "personalization_level": personalization_level,
            "has_booking_history": total_bookings > 0
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in get_user_recommendation_insights: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        connection.close()