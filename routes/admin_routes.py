from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session, flash
from models.db import get_connection
from models.community_experience import CommunityExperience
from models.listing import Listing  # Make sure this exists

admin_bp = Blueprint('admin', __name__)

# --- Admin login ---
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


# --- Admin dashboard ---
@admin_bp.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.admin_login'))

    # Fetch pending listings
    pending_listings = Listing.get_pending()  # assuming this returns list of dicts

    # Fetch pending community experiences
    pending_communities = CommunityExperience.get_all(only_approved=False)

    return render_template(
        'admin_dashboard.html',
        pending_listings=pending_listings,
        pending_communities=pending_communities
    )


# --- Approve / decline listings ---
@admin_bp.route('/admin/approve-listing/<int:listing_id>', methods=['POST'])
def approve_listing_web(listing_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.admin_login'))

    Listing.approve(listing_id)  # Add an approve method in Listing model
    flash('Listing approved successfully.')
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/decline-listing/<int:listing_id>', methods=['POST'])
def decline_listing_web(listing_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.admin_login'))

    Listing.decline(listing_id)  # Add a decline method in Listing model
    flash('Listing declined and removed.')
    return redirect(url_for('admin.admin_dashboard'))


# --- Approve / decline community experiences ---
@admin_bp.route('/admin/community-experiences/<int:exp_id>/approve', methods=['POST'])
def approve_community(exp_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.admin_login'))

    approved = request.form.get("approved", "true") == "true"
    CommunityExperience.approve(exp_id, approved)
    flash('Community experience approved.')
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/community-experiences/<int:exp_id>/decline', methods=['POST'])
def decline_community(exp_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.admin_login'))

    CommunityExperience.decline(exp_id)  # You need to implement this in your model
    flash('Community experience declined and removed.')
    return redirect(url_for('admin.admin_dashboard'))


# --- View details ---
@admin_bp.route('/admin/listing/<int:listing_id>')
def view_listing_detail(listing_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.admin_login'))

    listing = Listing.get_by_id(listing_id)
    if not listing:
        flash("Listing not found.")
        return redirect(url_for('admin.admin_dashboard'))

    return render_template('listing_detail.html', listing=listing)


# --- Logout ---
@admin_bp.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin.admin_login'))
