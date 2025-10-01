# scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from models.db import get_connection

def auto_release_rooms():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    now = datetime.now()

    
    cursor.execute("""
        SELECT * FROM booking 
        WHERE is_cancelled = FALSE AND check_out < %s 
    """, (now,))
    expired_bookings = cursor.fetchall()

    for booking in expired_bookings:
        listing_id = booking['listing_id']
        check_in = booking['check_in']
        check_out = booking['check_out']

        current_date = check_in
        while current_date < check_out:
            cursor.execute("""
                UPDATE room_availability 
                SET rooms_booked = GREATEST(rooms_booked - 1, 0)
                WHERE listing_id = %s AND date = %s
            """, (listing_id, current_date))
            current_date += timedelta(days=1)

        
        cursor.execute("UPDATE booking SET is_completed = TRUE WHERE id = %s", (booking['id'],))

    conn.commit()
    cursor.close()
    conn.close()

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(auto_release_rooms, 'interval', minutes=30)  
    scheduler.start()
