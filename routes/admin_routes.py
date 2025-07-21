from flask import Blueprint, request, jsonify , render_template, redirect, url_for, session, flash
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

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, name, email FROM user_account WHERE role='business_owner' AND is_approved=FALSE")
    pending_users = cursor.fetchall()

    cursor.execute("SELECT id, title FROM listing WHERE is_approved=FALSE")
    pending_listings = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin_dashboard.html', pending_users=pending_users, pending_listings=pending_listings)

@admin_bp.route('/admin/approve-user/<int:user_id>', methods=['POST'])
def approve_user_web(user_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.admin_login'))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE user_account SET is_approved=TRUE WHERE id=%s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('User approved successfully.')
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/approve-listing/<int:listing_id>', methods=['POST'])
def approve_listing_web(listing_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.admin_login'))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE listing SET is_approved=TRUE WHERE id=%s", (listing_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Listing approved successfully.')
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin.admin_login'))

@admin_bp.route('/admin/listing/<int:listing_id>')
def view_listing_detail(listing_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.admin_login'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM listing WHERE id=%s", (listing_id,))
    listing = cursor.fetchone()
    cursor.close()
    conn.close()

    if not listing:
        flash("Listing not found.")
        return redirect(url_for('admin.admin_dashboard'))

    return render_template('listing_detail.html', listing=listing)

@admin_bp.route('/decline_user/<int:user_id>')
def decline_user_web(user_id):
    # You can delete or mark the user as declined in the DB
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_account WHERE id = %s", (user_id,))
    conn.commit()
    flash("User declined successfully.")
    return redirect(url_for('admin.admin_dashboard'))



@admin_bp.route('/admin/decline-listing/<int:listing_id>', methods=['POST'])
def decline_listing_web(listing_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.admin_login'))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM listing WHERE id=%s", (listing_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Listing declined and removed.')
    return redirect(url_for('admin.admin_dashboard'))
