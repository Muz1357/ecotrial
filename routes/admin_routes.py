from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session, flash
from models.db import get_connection
from models.community_experience import CommunityExperience
import os
import requests


admin_bp = Blueprint('admin', __name__)

GOOGLE_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', 'AIzaSyA0kovojziyFywE0eF1mnMJdJnubZCX6Hs')

@admin_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == 'admin123':  
            session['admin_logged_in'] = True
            return redirect(url_for('admin.admin_dashboard'))
        else:
            flash('Invalid username or password')
            return render_template('admin_login.html', error="Invalid username or password")
    return render_template('admin_login.html')

@admin_bp.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.admin_login'))

    with get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT id, title FROM listing WHERE is_approved=FALSE")
            pending_listings = cursor.fetchall()

    return render_template('admin_dashboard.html', pending_listings=pending_listings)

@admin_bp.route('/admin/approve-listing/<int:listing_id>', methods=['POST'])
def approve_listing_web(listing_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.admin_login'))

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE listing SET is_approved=TRUE WHERE id=%s", (listing_id,))
            conn.commit()
    flash('Listing approved successfully.')
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/decline-listing/<int:listing_id>', methods=['POST'])
def decline_listing_web(listing_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.admin_login'))

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM listing WHERE id=%s", (listing_id,))
            conn.commit()
    flash('Listing declined and removed.')
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/listing/<int:listing_id>')
def view_listing_detail(listing_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.admin_login'))

    with get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM listing WHERE id=%s", (listing_id,))
            listing = cursor.fetchone()

    if not listing:
        flash("Listing not found.")
        return redirect(url_for('admin.admin_dashboard'))

    return render_template('listing_detail.html', listing=listing)

def geocode_location(address):
    """Convert address text into latitude/longitude using Google Maps API"""
    if not GOOGLE_API_KEY:
        return None, None

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": GOOGLE_API_KEY}

    try:
        resp = requests.get(url, params=params)
        data = resp.json()
        if data.get("status") == "OK" and len(data["results"]) > 0:
            location = data["results"][0]["geometry"]["location"]
            return location["lat"], location["lng"]
    except Exception as e:
        print("Geocoding error:", e)

    return None, None


@admin_bp.route('/admin/community-experiences')
def pending_community_experiences():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.admin_login'))

    with get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT id, title, category, location, price, certificate_path
                FROM community_experience 
                WHERE approved = 0
            """)
            pending_experiences = cursor.fetchall()

    return render_template(
        'admin_dashboard.html',
        pending_experiences=pending_experiences
    )



# --- Approve community experience ---
@admin_bp.route('/admin/community-experiences/<int:exp_id>/approve', methods=['POST'])
def approve_community_experience(exp_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.admin_login'))

    with get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            # fetch location text
            cursor.execute("SELECT location FROM community_experience WHERE id=%s", (exp_id,))
            exp = cursor.fetchone()

            lat, lng = (None, None)
            if exp and exp["location"]:
                lat, lng = geocode_location(exp["location"])

            # approve + save geocoded lat/lng
            cursor.execute("""
                UPDATE community_experience
                SET approved = 1, latitude = %s, longitude = %s
                WHERE id = %s
            """, (lat, lng, exp_id))
            conn.commit()

    flash('Community experience approved successfully (geocoded).')
    return redirect(url_for('admin.pending_community_experiences'))


# --- Decline / Delete community experience ---
@admin_bp.route('/admin/community-experiences/<int:exp_id>/decline', methods=['POST'])
def decline_community_experience(exp_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.admin_login'))

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM community_experience WHERE id=%s", (exp_id,))
            conn.commit()

    flash('Community experience declined and removed.')
    return redirect(url_for('admin.pending_community_experiences'))


# --- View details of a community experience ---
@admin_bp.route('/admin/community-experiences/<int:exp_id>')
def view_community_experience(exp_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.admin_login'))

    with get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM community_experience WHERE id=%s", (exp_id,))
            exp = cursor.fetchone()

    if not exp:
        flash("Community experience not found.")
        return redirect(url_for('admin.pending_community_experiences'))

    return render_template('community_experience_detail.html', experience=exp)

@admin_bp.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin.admin_login'))
