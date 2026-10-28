import os
import random
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from models import db, User, FoodDonation

app = Flask(__name__)
app.config['SECRET_KEY'] = 'smart-food-waste-ia3-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///foodwaste.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Helper context processor to expose current user and demo helpers
@app.context_processor
def inject_globals():
    current_user = None
    if 'user_id' in session:
        current_user = db.session.get(User, session['user_id'])
    return {
        'current_user': current_user,
        'now': datetime.now(),
        'int': int,
        'round': round
    }


def login_required(role=None):
    def decorator(f):
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please log in to access this feature.", "warning")
                return redirect(url_for('login'))
            user = db.session.get(User, session['user_id'])
            if not user:
                session.clear()
                return redirect(url_for('login'))
            if role and user.role != role and user.role != 'admin':
                flash(f"Access restricted to {role.capitalize()} accounts.", "danger")
                return redirect(url_for('feed'))
            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator


# ============================================================================
# Core Views & Navigation
# ============================================================================

@app.route('/')
def index():
    return redirect(url_for('feed'))


@app.route('/feed')
def feed():
    """Marketplace / Claim Feed sorted by expiry urgency."""
    query = FoodDonation.query

    # Status filter (default to Available, but allow viewing Claimed/All)
    status_filter = request.args.get('status', 'Available')
    diet_filter = request.args.get('diet', 'all')
    category_filter = request.args.get('category', 'all')
    urgency_filter = request.args.get('urgency', 'all')

    donations = query.all()

    # Dynamic status update check
    for item in donations:
        if item.status == 'Available' and datetime.now() > item.expires_at:
            item.status = 'Expired'
    db.session.commit()

    # Filter logic in Python to respect dynamic property calculations
    filtered_items = []
    for item in donations:
        if status_filter != 'all' and item.current_status != status_filter:
            continue
        if diet_filter != 'all' and item.dietary_type.lower() != diet_filter.lower():
            continue
        if category_filter != 'all' and item.category.lower() != category_filter.lower():
            continue
        if urgency_filter != 'all' and item.urgency_level != urgency_filter:
            continue
        filtered_items.append(item)

    # Sort primarily by urgency: Available items expiring first, then others
    def sort_key(item):
        # Active items first, ordered by time remaining ascending
        if item.current_status == 'Available':
            return (0, item.time_remaining_seconds)
        elif item.current_status == 'Claimed':
            return (1, item.time_remaining_seconds)
        else:
            return (2, -item.id)

    filtered_items.sort(key=sort_key)

    # Count quick stats for header badge
    available_count = FoodDonation.query.filter_by(status='Available').count()
    claimed_count = FoodDonation.query.filter_by(status='Claimed').count()

    return render_template(
        'feed.html',
        donations=filtered_items,
        status_filter=status_filter,
        diet_filter=diet_filter,
        category_filter=category_filter,
        urgency_filter=urgency_filter,
        available_count=available_count,
        claimed_count=claimed_count
    )


@app.route('/donate', methods=['GET', 'POST'])
def donate():
    """Portal for Donors (Messes, Hostels, Restaurants) to log surplus food."""
    # Auto log-in as donor if not logged in for quick demo testing
    if 'user_id' not in session:
        default_donor = User.query.filter_by(role='donor').first()
        if default_donor:
            session['user_id'] = default_donor.id

    current_user = db.session.get(User, session.get('user_id'))
    if current_user and current_user.role not in ['donor', 'admin']:
        flash("You are currently logged in as a Receiver. Switch to Donor role to post food.", "info")

    if request.method == 'POST':
        item_name = request.form.get('item_name', '').strip()
        category = request.form.get('category', 'Cooked Meal')
        dietary_type = request.form.get('dietary_type', 'Veg')
        quantity_kg = request.form.get('quantity_kg', type=float)
        servings_estimate = request.form.get('servings_estimate', type=int)
        storage_condition = request.form.get('storage_condition', 'Hot Insulated (>60°C)')
        expiry_hours = request.form.get('expiry_hours', type=float)
        pickup_address = request.form.get('pickup_address', '').strip()
        pickup_contact = request.form.get('pickup_contact', '').strip()
        notes = request.form.get('notes', '').strip()

        # Validation
        errors = []
        if not item_name:
            errors.append("Item name is required.")
        if not quantity_kg or quantity_kg <= 0:
            errors.append("Quantity in kg must be greater than zero.")
        if not servings_estimate or servings_estimate <= 0:
            # Fallback estimation: ~2.2 meals per kg
            servings_estimate = int(quantity_kg * 2.2) if quantity_kg else 10
        if not expiry_hours or expiry_hours <= 0:
            errors.append("Expiry window must be at least 0.5 hours.")
        if not pickup_address:
            pickup_address = current_user.address if current_user and current_user.address else "Campus Dining Loading Bay"
        if not pickup_contact:
            pickup_contact = current_user.phone if current_user else "+91 98765 43210"

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template('donate.html', form_data=request.form)

        now = datetime.now()
        prepared_at = now
        expires_at = now + timedelta(hours=expiry_hours)

        donor_id = current_user.id if current_user else 1

        new_donation = FoodDonation(
            donor_id=donor_id,
            item_name=item_name,
            category=category,
            dietary_type=dietary_type,
            quantity_kg=quantity_kg,
            servings_estimate=servings_estimate,
            storage_condition=storage_condition,
            prepared_at=prepared_at,
            expires_at=expires_at,
            pickup_address=pickup_address,
            pickup_contact=pickup_contact,
            notes=notes,
            status='Available'
        )

        db.session.add(new_donation)
        db.session.commit()

        flash(f"Successfully listed '{item_name}'! It is now live on the Redistribution Marketplace.", "success")
        return redirect(url_for('feed'))

    return render_template('donate.html')


@app.route('/claim/<int:id>', methods=['POST'])
def claim_donation(id):
    """Claim a donation item by a verified receiver/NGO."""
    if 'user_id' not in session:
        # Default to demo receiver if testing
        default_receiver = User.query.filter_by(role='receiver').first()
        if default_receiver:
            session['user_id'] = default_receiver.id
        else:
            flash("Please sign in as a Receiver / NGO to claim food.", "warning")
            return redirect(url_for('login'))

    user = db.session.get(User, session['user_id'])
    donation = db.get_or_404(FoodDonation, id)

    # Check if expired
    if donation.current_status == 'Expired':
        flash("This food donation has expired and cannot be claimed for safety reasons.", "danger")
        return redirect(url_for('feed'))

    if donation.status != 'Available':
        flash(f"This donation is already {donation.status.lower()}.", "warning")
        return redirect(url_for('feed'))

    # Generate 4-digit handover PIN for secure physical pickup verification
    pin = f"{random.randint(1000, 9999)}"

    donation.status = 'Claimed'
    donation.claim_pin = pin
    donation.claimed_by_id = user.id
    donation.claimed_at = datetime.now()

    db.session.commit()

    flash(f"Successfully claimed! Your Handover Verification PIN is: {pin}. Share this with the donor at pickup.", "success")
    return redirect(url_for('feed'))


@app.route('/complete/<int:id>', methods=['POST'])
def complete_donation(id):
    """Verify Handover PIN and mark the donation distribution as Completed."""
    entered_pin = request.form.get('pin', '').strip()
    donation = db.get_or_404(FoodDonation, id)

    if donation.status != 'Claimed':
        flash("Only claimed items can be marked as completed.", "warning")
        return redirect(url_for('feed'))

    # Verify PIN or allow admin override
    is_admin = False
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        if user and user.role == 'admin':
            is_admin = True

    if not is_admin and entered_pin != donation.claim_pin:
        flash(f"Incorrect PIN '{entered_pin}'. Please enter the 4-digit PIN provided to the claimant.", "danger")
        return redirect(url_for('feed'))

    donation.status = 'Completed'
    donation.completed_at = datetime.now()
    db.session.commit()

    flash(f"Handover verified! {donation.servings_estimate} meals redistributed ({donation.co2_saved_kg} kg CO2 prevented).", "success")
    return redirect(url_for('dashboard'))


@app.route('/cancel-claim/<int:id>', methods=['POST'])
def cancel_claim(id):
    """Release reservation if claimant cannot collect."""
    donation = db.get_or_404(FoodDonation, id)
    if donation.status == 'Claimed':
        donation.status = 'Available'
        donation.claimed_by_id = None
        donation.claimed_at = None
        donation.claim_pin = None
        db.session.commit()
        flash("Claim cancelled. Item returned to the active marketplace.", "info")
    return redirect(url_for('feed'))


# ============================================================================
# Impact & Analytics Dashboard
# ============================================================================

@app.route('/dashboard')
def dashboard():
    """Impact and analytics overview with carbon metrics and charts."""
    all_donations = FoodDonation.query.all()

    # Environmental impact calculations
    # Impact counts completed and claimed food saved
    saved_items = [d for d in all_donations if d.status in ['Completed', 'Claimed']]
    
    total_kg_saved = sum(d.quantity_kg for d in saved_items)
    total_meals_saved = sum(d.servings_estimate for d in saved_items)
    total_co2_avoided = round(total_kg_saved * 2.5, 2)  # 1kg food waste = 2.5kg CO2
    total_water_saved = round(total_kg_saved * 1000, 0) # 1000 liters / kg

    # Categorical breakdown
    categories = {}
    for d in saved_items:
        categories[d.category] = categories.get(d.category, 0) + d.quantity_kg

    category_labels = list(categories.keys()) or ["Cooked Meal", "Bakery", "Packaged Goods"]
    category_data = [round(v, 1) for v in categories.values()] or [50.0, 14.0, 8.0]

    # Status counts
    status_counts = {
        'Available': sum(1 for d in all_donations if d.current_status == 'Available'),
        'Claimed': sum(1 for d in all_donations if d.current_status == 'Claimed'),
        'Completed': sum(1 for d in all_donations if d.current_status == 'Completed'),
        'Expired': sum(1 for d in all_donations if d.current_status == 'Expired')
    }

    recent_activity = FoodDonation.query.order_by(FoodDonation.id.desc()).limit(8).all()

    return render_template(
        'dashboard.html',
        total_kg_saved=round(total_kg_saved, 1),
        total_meals_saved=total_meals_saved,
        total_co2_avoided=total_co2_avoided,
        total_water_saved=int(total_water_saved),
        category_labels=category_labels,
        category_data=category_data,
        status_counts=status_counts,
        recent_activity=recent_activity
    )


# ============================================================================
# Admin Moderation & User Management
# ============================================================================

@app.route('/admin')
def admin_portal():
    """Admin portal to monitor all listings, toggle verification, view system logs."""
    users = User.query.all()
    donations = FoodDonation.query.order_by(FoodDonation.id.desc()).all()
    return render_template('admin.html', users=users, donations=donations)


@app.route('/admin/toggle-user/<int:user_id>', methods=['POST'])
def admin_toggle_user(user_id):
    user = db.get_or_404(User, user_id)
    user.is_verified = not user.is_verified
    db.session.commit()
    flash(f"User {user.name} verification set to {user.is_verified}.", "info")
    return redirect(url_for('admin_portal'))


@app.route('/admin/delete-donation/<int:id>', methods=['POST'])
def admin_delete_donation(id):
    donation = db.get_or_404(FoodDonation, id)
    db.session.delete(donation)
    db.session.commit()
    flash(f"Listing '{donation.item_name}' removed by Administrator.", "info")
    return redirect(url_for('admin_portal'))


# ============================================================================
# Authentication & Demo Role Switcher
# ============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            flash(f"Welcome back, {user.name}! Logged in as {user.role.capitalize()}.", "success")
            return redirect(url_for('feed'))
        else:
            flash("Invalid email or password. You can also use the Instant Role Switcher below.", "danger")

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'donor')
        organization = request.form.get('organization', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()

        if User.query.filter_by(email=email).first():
            flash("An account with this email already exists.", "danger")
            return render_template('login.html', is_register=True)

        user = User(
            name=name,
            email=email,
            role=role,
            organization=organization or name,
            phone=phone or "+91 90000 00000",
            address=address,
            is_verified=True
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        session['user_id'] = user.id
        flash(f"Account created successfully! Logged in as {user.name}.", "success")
        return redirect(url_for('feed'))

    return render_template('login.html', is_register=True)


@app.route('/logout')
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for('feed'))


@app.route('/switch-role/<role>')
def switch_role(role):
    """
    Instant Role Switcher designed for presentation & academic viva.
    Switches active user without requiring re-typing credentials.
    """
    user = User.query.filter_by(role=role).first()
    if user:
        session['user_id'] = user.id
        flash(f"⚡ Switched active role to: {user.name} ({user.organization} - {role.upper()})", "success")
    else:
        flash(f"No user found for role {role}.", "warning")
    return redirect(request.referrer or url_for('feed'))


# ============================================================================
# JSON REST API Endpoints (For client-side AJAX & external integrations)
# ============================================================================

@app.route('/api/donations')
def api_donations():
    donations = FoodDonation.query.all()
    return jsonify([d.to_dict() for d in donations])


@app.route('/api/metrics')
def api_metrics():
    all_donations = FoodDonation.query.all()
    saved = [d for d in all_donations if d.status in ['Completed', 'Claimed']]
    total_kg = sum(d.quantity_kg for d in saved)
    return jsonify({
        'total_kg_saved': round(total_kg, 1),
        'total_meals_saved': sum(d.servings_estimate for d in saved),
        'total_co2_avoided_kg': round(total_kg * 2.5, 2),
        'total_water_saved_liters': round(total_kg * 1000, 0),
        'active_listings': sum(1 for d in all_donations if d.current_status == 'Available')
    })


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    print("Starting Smart Food Waste Platform on http://127.0.0.1:5000 ...")
    app.run(debug=True, port=5000)
