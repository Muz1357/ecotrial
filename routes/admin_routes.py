from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session, flash
from models.db import get_connection

admin_bp = Blueprint('admin', __name__)

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
            # Business owner approval removed – no need to fetch pending users
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

@admin_bp.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin.admin_login'))
