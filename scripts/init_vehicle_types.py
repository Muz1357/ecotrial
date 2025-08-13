from models.db import get_connection

def init_vehicle_types():
    default_types = [
        {
            'name': 'Car',
            'price_per_km': 0.50,
            'eco_points_rate': 1.0
        },
        {
            'name': 'Van',
            'price_per_km': 0.70,
            'eco_points_rate': 0.8  # Lower points as vans typically less eco-friendly
        },
        {
            'name': 'Tuk Tuk',
            'price_per_km': 0.30,
            'eco_points_rate': 1.2  # Higher points as tuktuks are more eco-friendly
        },
        {
            'name': 'Bike',
            'price_per_km': 0.20,
            'eco_points_rate': 1.5  # Highest points for bikes
        },
        {
            'name': 'EV Car',
            'price_per_km': 0.45,
            'eco_points_rate': 2.0  # Electric vehicles get double points
        },
        {
            'name': 'Plug-in Hybrid',
            'price_per_km': 0.48,
            'eco_points_rate': 1.8  # Hybrids get more points than regular cars
        }
    ]
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check if types already exist
        cursor.execute("SELECT COUNT(*) FROM vehicle_types")
        count = cursor.fetchone()[0]
        
        if count == 0:
            for vehicle_type in default_types:
                cursor.execute("""
                    INSERT INTO vehicle_types (name, price_per_km, eco_points_rate)
                    VALUES (%s, %s, %s)
                """, (
                    vehicle_type['name'],
                    vehicle_type['price_per_km'],
                    vehicle_type['eco_points_rate']
                ))
            
            conn.commit()
            print(f"Successfully initialized {len(default_types)} vehicle types")
        else:
            print("Vehicle types already exist, skipping initialization")
            
    except Exception as e:
        conn.rollback()
        print(f"Error initializing vehicle types: {str(e)}")
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    init_vehicle_types()