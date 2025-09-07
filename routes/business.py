from flask import Blueprint, request, jsonify
from models.db import get_connection
from datetime import datetime
from dateutil import parser

report_bp = Blueprint('report', __name__)

@report_bp.route('/report/business/<int:business_id>', methods=['GET'])
def business_report(business_id):
    """
    Generate a summary report for a business owner:
    - total listings
    - total bookings
    - cancelled bookings
    - revenue (if price is in listing)
    - occupancy % (rooms booked / total rooms available)
    Optional query params: start_date, end_date (ISO format)
    """
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    try:
        if start_date:
            start_date = parser.isoparse(start_date).date()
        if end_date:
            end_date = parser.isoparse(end_date).date()
    except Exception:
        return jsonify({"error": "Invalid date format. Use ISO (YYYY-MM-DD)."}), 400

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # base filter
    date_filter = ""
    params = [business_id]
    if start_date and end_date:
        date_filter = "AND b.check_in >= %s AND b.check_out <= %s"
        params.extend([start_date, end_date])

    try:
        # 1) total listings
        cursor.execute("SELECT COUNT(*) as total_listings FROM listing WHERE user_id = %s", (business_id,))
        total_listings = cursor.fetchone()["total_listings"]

        # 2) total bookings & cancellations
        cursor.execute(f"""
            SELECT COUNT(*) as total_bookings,
                   SUM(CASE WHEN b.is_cancelled = TRUE THEN 1 ELSE 0 END) as cancelled
            FROM booking b
            JOIN listing l ON b.listing_id = l.id
            WHERE l.user_id = %s {date_filter}
        """, tuple(params))
        row = cursor.fetchone()
        total_bookings = row["total_bookings"] or 0
        cancelled = row["cancelled"] or 0

        # 3) revenue (if price in listing)
        cursor.execute(f"""
            SELECT SUM(l.price) as revenue
            FROM booking b
            JOIN listing l ON b.listing_id = l.id
            WHERE l.user_id = %s AND b.is_cancelled = FALSE {date_filter}
        """, tuple(params))
        revenue = cursor.fetchone()["revenue"] or 0

        # 4) occupancy = rooms booked / rooms available
        cursor.execute(f"""
            SELECT SUM(DATEDIFF(b.check_out, b.check_in)) as room_nights_booked,
                   SUM(l.rooms_available * DATEDIFF(b.check_out, b.check_in)) as room_nights_capacity
            FROM booking b
            JOIN listing l ON b.listing_id = l.id
            WHERE l.user_id = %s AND b.is_cancelled = FALSE {date_filter}
        """, tuple(params))
        occ_row = cursor.fetchone()
        booked = occ_row["room_nights_booked"] or 0
        capacity = occ_row["room_nights_capacity"] or 0
        occupancy_rate = round((booked / capacity) * 100, 2) if capacity > 0 else 0.0

        cursor.close()
        conn.close()

        return jsonify({
            "business_id": business_id,
            "total_listings": total_listings,
            "total_bookings": total_bookings,
            "cancelled_bookings": cancelled,
            "revenue": revenue,
            "occupancy_rate": occupancy_rate,
            "date_range": {
                "start_date": str(start_date) if start_date else None,
                "end_date": str(end_date) if end_date else None
            }
        })
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({"error": "Failed to generate report", "details": str(e)}), 500
