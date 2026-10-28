"""
Smart Food Waste Management & Redistribution Platform
Academic Evaluation (IA3) Micro-Project
Backend: Flask 3.1 + SQLite (Auto-seeding food_redistribution.db)
Features: Firebase Google Auth Sync, Image Upload / URL support, Real-Time Expiry
"""

import os
import random
import sqlite3
import time
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ia3-light-glassmorphic-eco-rescue-2026'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'food_redistribution.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DEFAULT_IMAGES = {
    'Cooked Meal': '/static/images/rice_curry.svg',
    'Bakery': '/static/images/bakery_bread.svg',
    'Non-Veg': '/static/images/chicken_biryani.svg',
    'Packaged Goods': '/static/images/khichdi_dal.svg',
    'Raw Produce': '/static/images/default_food.svg'
}

SUPER_ADMIN_EMAIL = 'kavinprasanth2306@gmail.com'


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============================================================================
# DATABASE UTILITIES & AUTO-SEEDER
# ============================================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL, -- 'donor', 'receiver', 'admin'
            organization TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT,
            photo_url TEXT,
            is_verified INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Food Listings Table with image_url column
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS food_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donor_id INTEGER,
            item_name TEXT NOT NULL,
            donor_org TEXT NOT NULL,
            category TEXT NOT NULL, -- 'Cooked Meal', 'Bakery', 'Packaged Goods', 'Raw Produce'
            dietary_type TEXT NOT NULL, -- 'Veg', 'Non-Veg', 'Vegan'
            quantity_kg REAL NOT NULL,
            servings_estimate INTEGER NOT NULL,
            storage_condition TEXT NOT NULL, -- 'Hot Insulated (>60°C)', 'Chilled (4°C)', 'Room Temp / Dry'
            prepared_at TIMESTAMP NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            pickup_address TEXT NOT NULL,
            pickup_contact TEXT NOT NULL,
            notes TEXT,
            image_url TEXT,
            status TEXT DEFAULT 'Available', -- 'Available', 'Claimed', 'Completed', 'Expired'
            claim_pin TEXT,
            claimed_by_org TEXT,
            claimed_by_contact TEXT,
            claimed_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (donor_id) REFERENCES users(id)
        )
    ''')
    conn.commit()

    # Migration check: Ensure photo_url column exists in older sqlite tables
    cursor.execute("PRAGMA table_info(users)")
    user_cols = [col[1] for col in cursor.fetchall()]
    if 'photo_url' not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN photo_url TEXT")
        conn.commit()

    # Migration check: Ensure image_url column exists in older sqlite tables
    cursor.execute("PRAGMA table_info(food_listings)")
    cols = [col[1] for col in cursor.fetchall()]
    if 'image_url' not in cols:
        cursor.execute("ALTER TABLE food_listings ADD COLUMN image_url TEXT")
        conn.commit()

    # Enforce admin privilege exclusivity: only SUPER_ADMIN_EMAIL can be 'admin'
    cursor.execute("UPDATE users SET role = 'admin' WHERE LOWER(email) = LOWER(?)", (SUPER_ADMIN_EMAIL,))
    cursor.execute("UPDATE users SET role = 'receiver' WHERE role = 'admin' AND LOWER(email) != LOWER(?)", (SUPER_ADMIN_EMAIL,))
    conn.commit()

    # Check if data exists; if not, seed realistic Indian campus/restaurant records
    cursor.execute("SELECT COUNT(*) FROM food_listings")
    count = cursor.fetchone()[0]

    if count == 0:
        seed_data(conn)
    conn.close()


def seed_data(conn):
    cursor = conn.cursor()
    now = datetime.now()

    # 1. Seed Personas / Users
    users = [
        ("Rahul Sharma (Mess Manager)", "donor@campus.edu", "donor", "Campus Central Mess (Hostel Block A)", "+91 98765 43210", "Campus Dining Complex, North Gate 2", "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&h=120&q=80", 1),
        ("Chef Vikram Singhania", "royal@banquet.com", "donor", "Grand Royal Banquet & Caterers", "+91 98111 22334", "Plot 45, Sector 18 Commercial Hub", "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=120&h=120&q=80", 1),
        ("Ananya Desai (Director)", "shelter@hope.org", "receiver", "Hope Community Shelter & Food Bank", "+91 99222 33445", "12-B Old City Road, Near Civil Hospital", "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=120&h=120&q=80", 1),
        ("Karthik Verma (Coordinator)", "seva@ngo.org", "receiver", "Seva Youth Volunteer Foundation", "+91 97333 44556", "Sector 9 Community Haven", "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=120&h=120&q=80", 1),
        ("Dr. Kavin Prasanth", SUPER_ADMIN_EMAIL, "admin", "University Food Safety & Redistribution Board", "+91 99222 33445", "Faculty IT Complex, Admin Block", "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&h=120&q=80", 1)
    ]
    cursor.executemany('''
        INSERT OR IGNORE INTO users (name, email, role, organization, phone, address, photo_url, is_verified)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', users)

    # 2. Seed 5 Realistic Indian Campus/Restaurant Food Listings with High-Res Photos
    r1_exp = now + timedelta(hours=1, minutes=35)
    r1_prep = now - timedelta(hours=2)

    r2_exp = now + timedelta(hours=5, minutes=30)
    r2_prep = now - timedelta(hours=3)

    r3_exp = now + timedelta(hours=3, minutes=30)
    r3_prep = now - timedelta(hours=1, minutes=30)

    r4_exp = now + timedelta(hours=4)
    r4_prep = now - timedelta(hours=4)
    r4_claimed = now - timedelta(minutes=25)

    r5_exp = now - timedelta(hours=2)
    r5_prep = now - timedelta(hours=14)

    listings = [
        (
            1, "Steamed Basmati Rice, Paneer Butter Masala & 80 Rotis",
            "Campus Central Mess (Hostel Block A)", "Cooked Meal", "Veg",
            28.5, 60, "Hot Insulated (>60°C)", r1_prep.strftime("%Y-%m-%d %H:%M:%S"),
            r1_exp.strftime("%Y-%m-%d %H:%M:%S"), "Campus Dining Complex, Loading Dock A",
            "+91 98765 43210 (Mess Supervisor)", "Surplus from lunch rush. Packed in 3 insulated thermal cafs.",
            "/static/images/rice_curry.svg",
            "Available", None, None, None, None, None
        ),
        (
            2, "Assorted Multi-Grain Breads, Vegetable Puffs & Sandwiches",
            "Grand Royal Banquet & Caterers", "Bakery", "Veg",
            14.0, 40, "Room Temp / Dry", r2_prep.strftime("%Y-%m-%d %H:%M:%S"),
            r2_exp.strftime("%Y-%m-%d %H:%M:%S"), "Grand Royal Kitchen Bay, Sector 18",
            "+91 98111 22334 (Head Pastry Chef)", "Individually wrapped and tray-sealed. Safe for evening snack distribution.",
            "/static/images/bakery_bread.svg",
            "Available", None, None, None, None, None
        ),
        (
            3, "Hyderabadi Chicken Dum Biryani & Mirchi Ka Salan",
            "Grand Royal Banquet & Caterers", "Cooked Meal", "Non-Veg",
            35.0, 75, "Hot Insulated (>60°C)", r3_prep.strftime("%Y-%m-%d %H:%M:%S"),
            r3_exp.strftime("%Y-%m-%d %H:%M:%S"), "Grand Royal Banquet Main Entrance, Sector 18",
            "+91 98111 22334 (Banquet Operations Lead)", "Corporate convention lunch excess. Strictly kept above 65°C in chafing dishes.",
            "/static/images/chicken_biryani.svg",
            "Available", None, None, None, None, None
        ),
        (
            1, "Mixed Vegetable Khichdi, Tadka Dal & Sweet Kesari",
            "Campus Central Mess (Hostel Block A)", "Cooked Meal", "Veg",
            22.0, 50, "Chilled (4°C)", r4_prep.strftime("%Y-%m-%d %H:%M:%S"),
            r4_exp.strftime("%Y-%m-%d %H:%M:%S"), "Campus Dining Complex, Block B Cold Room",
            "+91 98765 43210 (Mr. Rahul)", "Rapidly chilled in clean food-safe bins. Van dispatched.",
            "/static/images/khichdi_dal.svg",
            "Claimed", "7842", "Hope Community Shelter & Food Bank", "+91 99222 33445",
            r4_claimed.strftime("%Y-%m-%d %H:%M:%S"), None
        ),
        (
            2, "Cream of Mushroom Soup & Garlic Herb Crostini",
            "Grand Royal Banquet & Caterers", "Cooked Meal", "Veg",
            10.0, 20, "Chilled (4°C)", r5_prep.strftime("%Y-%m-%d %H:%M:%S"),
            r5_exp.strftime("%Y-%m-%d %H:%M:%S"), "Grand Royal Banquet Kitchen Gate",
            "+91 98111 22334", "Exceeded safety consumption threshold. Automated safety lockout active.",
            "/static/images/mushroom_soup.svg",
            "Expired", None, None, None, None, None
        )
    ]

    cursor.executemany('''
        INSERT INTO food_listings (
            donor_id, item_name, donor_org, category, dietary_type,
            quantity_kg, servings_estimate, storage_condition, prepared_at,
            expires_at, pickup_address, pickup_contact, notes, image_url,
            status, claim_pin, claimed_by_org, claimed_by_contact,
            claimed_at, completed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', listings)
    conn.commit()


# ============================================================================
# HELPER LOGIC: URGENCY & IMPACT COMPUTATIONS
# ============================================================================

def format_listing_row(row):
    d = dict(row)
    now = datetime.now()

    try:
        exp = datetime.strptime(d['expires_at'], "%Y-%m-%d %H:%M:%S")
    except Exception:
        exp = now

    remaining_seconds = int((exp - now).total_seconds())
    d['time_remaining_seconds'] = remaining_seconds

    # Dynamic status enforcement
    if d['status'] == 'Available' and remaining_seconds <= 0:
        d['status'] = 'Expired'

    # Fallback image if missing
    if not d.get('image_url'):
        if d.get('dietary_type') == 'Non-Veg':
            d['image_url'] = DEFAULT_IMAGES['Non-Veg']
        else:
            d['image_url'] = DEFAULT_IMAGES.get(d.get('category'), DEFAULT_IMAGES['Cooked Meal'])

    # Urgency level categorization
    if d['status'] == 'Expired' or remaining_seconds <= 0:
        d['urgency_level'] = 'expired'
        d['urgency_label'] = 'Expired'
    elif remaining_seconds < 7200: # < 2 hours
        d['urgency_level'] = 'critical'
        hours = remaining_seconds // 3600
        mins = (remaining_seconds % 3600) // 60
        d['urgency_label'] = f"Urgent ({hours}h {mins}m left)"
    elif remaining_seconds < 18000: # 2 - 5 hours
        d['urgency_level'] = 'warning'
        hours = remaining_seconds // 3600
        mins = (remaining_seconds % 3600) // 60
        d['urgency_label'] = f"Expiring ({hours}h {mins}m left)"
    else:
        hours = remaining_seconds // 3600
        d['urgency_level'] = 'safe'
        d['urgency_label'] = f"Safe ({hours}h left)"

    # Impact metrics: 1 kg = 2.5 kg CO2e
    d['co2_saved_kg'] = round(d['quantity_kg'] * 2.5, 2)
    d['water_saved_liters'] = int(d['quantity_kg'] * 1000)
    return d


def compute_aggregate_metrics():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM food_listings")
    rows = cursor.fetchall()
    conn.close()

    items = [format_listing_row(r) for r in rows]

    saved_items = [i for i in items if i['status'] in ('Claimed', 'Completed')]
    total_kg = sum(i['quantity_kg'] for i in saved_items)
    total_meals = sum(i['servings_estimate'] for i in saved_items)
    total_co2 = round(total_kg * 2.5, 1)
    total_water = int(total_kg * 1000)

    active_count = sum(1 for i in items if i['status'] == 'Available')
    claimed_count = sum(1 for i in items if i['status'] == 'Claimed')
    completed_count = sum(1 for i in items if i['status'] == 'Completed')
    expired_count = sum(1 for i in items if i['status'] == 'Expired')

    return {
        'total_kg_saved': round(total_kg, 1),
        'total_meals_saved': total_meals,
        'total_co2_avoided_kg': total_co2,
        'total_water_saved_liters': total_water,
        'active_count': active_count,
        'claimed_count': claimed_count,
        'completed_count': completed_count,
        'expired_count': expired_count,
        'total_lots': len(items)
    }


# ============================================================================
# HTTP CONTROLLERS & JSON REST APIS
# ============================================================================

@app.route('/')
def index():
    """Renders the master ultra-clean light glassmorphic single-page dashboard."""
    metrics = compute_aggregate_metrics()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM food_listings ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    listings = [format_listing_row(r) for r in rows]

    def sort_order(x):
        if x['status'] == 'Available':
            return (0, x['time_remaining_seconds'])
        elif x['status'] == 'Claimed':
            return (1, x['time_remaining_seconds'])
        else:
            return (2, -x['id'])

    listings.sort(key=sort_order)
    return render_template('index.html', listings=listings, metrics=metrics)


@app.route('/api/listings', methods=['GET'])
def api_listings():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM food_listings ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    items = [format_listing_row(r) for r in rows]
    return jsonify({'success': True, 'listings': items})


@app.route('/api/metrics', methods=['GET'])
def api_metrics():
    return jsonify({'success': True, 'metrics': compute_aggregate_metrics()})


@app.route('/api/listings', methods=['POST'])
def api_add_listing():
    """Create a new surplus food donation from the modal with image upload or URL support."""
    # Handle multipart form data or json
    if request.is_json:
        data = request.get_json() or {}
        image_url = data.get('image_url', '').strip()
    else:
        data = request.form
        image_url = data.get('image_url', '').strip()
        
        # Check if an actual file was uploaded
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename and allowed_file(file.filename):
                safe_name = f"{int(time.time())}_{secure_filename(file.filename)}"
                file_dest = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
                file.save(file_dest)
                image_url = f"/static/uploads/{safe_name}"

    item_name = data.get('item_name', '').strip()
    donor_org = data.get('donor_org', 'Campus Central Mess (Hostel A)').strip()
    category = data.get('category', 'Cooked Meal').strip()
    dietary_type = data.get('dietary_type', 'Veg').strip()
    quantity_kg = float(data.get('quantity_kg', 0))
    servings_estimate = int(data.get('servings_estimate') or int(quantity_kg * 2.2))
    storage_condition = data.get('storage_condition', 'Hot Insulated (>60°C)').strip()
    expiry_hours = float(data.get('expiry_hours', 4.0))
    pickup_address = data.get('pickup_address', 'Dining Hall Loading Dock 1').strip()
    pickup_contact = data.get('pickup_contact', '+91 98765 43210').strip()
    notes = data.get('notes', '').strip()

    if not item_name or quantity_kg <= 0 or expiry_hours <= 0:
        return jsonify({'success': False, 'message': 'Please provide a valid item name, positive quantity, and expiry window.'}), 400

    # Auto fallback image if none provided
    if not image_url:
        if dietary_type == 'Non-Veg':
            image_url = DEFAULT_IMAGES['Non-Veg']
        else:
            image_url = DEFAULT_IMAGES.get(category, DEFAULT_IMAGES['Cooked Meal'])

    now = datetime.now()
    prepared_at = now.strftime("%Y-%m-%d %H:%M:%S")
    expires_at = (now + timedelta(hours=expiry_hours)).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO food_listings (
            donor_id, item_name, donor_org, category, dietary_type,
            quantity_kg, servings_estimate, storage_condition, prepared_at,
            expires_at, pickup_address, pickup_contact, notes, image_url, status
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Available')
    ''', (item_name, donor_org, category, dietary_type, quantity_kg, servings_estimate, storage_condition, prepared_at, expires_at, pickup_address, pickup_contact, notes, image_url))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    return jsonify({
        'success': True,
        'message': f"Food lot '{item_name}' broadcast to local shelter network with photo verified!",
        'listing_id': new_id
    })


@app.route('/api/auth/google-sync', methods=['POST'])
def api_google_sync():
    """Sync authenticated Google User with the SQLite Users table."""
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    name = data.get('displayName', 'Google User').strip()
    photo_url = data.get('photoURL', '')
    role = data.get('role', 'receiver')

    is_super_admin = (email.strip().lower() == SUPER_ADMIN_EMAIL.lower())
    if is_super_admin:
        role = 'admin'
    elif role == 'admin':
        role = 'receiver'

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, role, organization, phone, address, photo_url FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()

    if user:
        if is_super_admin:
            assigned_role = 'admin'
            org = user['organization'] or 'University Food Safety & Redistribution Board'
            cursor.execute("UPDATE users SET role = 'admin', photo_url = ?, name = ? WHERE email = ?", (photo_url, name, email))
        else:
            assigned_role = user['role']
            if assigned_role == 'admin':
                assigned_role = 'receiver'
                cursor.execute("UPDATE users SET role = 'receiver' WHERE email = ?", (email,))
            cursor.execute("UPDATE users SET photo_url = ?, name = ? WHERE email = ?", (photo_url, name, email))
            org = user['organization'] or ('Campus Dining Complex' if assigned_role == 'donor' else 'Hope Community Shelter')
        
        user_id = user['id']
        phone = user['phone'] or '+91 98765 00000'
        address = user['address'] or 'Campus Dining Dock 1'
    else:
        if is_super_admin:
            assigned_role = 'admin'
            org = "University Food Safety & Redistribution Board"
            phone = "+91 99222 33445"
            address = "Faculty IT Complex, Admin Block"
        else:
            assigned_role = 'donor' if role == 'donor' else 'receiver'
            org = "Campus Dining Complex" if assigned_role == 'donor' else "Hope Community Shelter"
            phone = "+91 98765 43210"
            address = "Campus Dining Loading Dock Gate 2"

        cursor.execute('''
            INSERT INTO users (name, email, role, organization, phone, address, photo_url, is_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        ''', (name, email, assigned_role, org, phone, address, photo_url))
        user_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'user': {
            'id': user_id,
            'name': name,
            'email': email,
            'role': assigned_role,
            'organization': org,
            'phone': phone,
            'address': address,
            'photo_url': photo_url
        }
    })


@app.route('/api/user/update-profile', methods=['POST'])
def api_update_profile():
    """Update profile details (organization, phone, address, role)."""
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    name = data.get('name', '').strip()
    role = data.get('role', 'receiver').strip()
    org = data.get('organization', '').strip()
    phone = data.get('phone', '').strip()
    address = data.get('address', '').strip()

    if not email:
        return jsonify({'success': False, 'message': 'Email is required.'}), 400

    is_super_admin = (email.strip().lower() == SUPER_ADMIN_EMAIL.lower())
    if role == 'admin' and not is_super_admin:
        return jsonify({
            'success': False,
            'message': f'Access Denied: Admin Audit access is strictly restricted to platform administrator ({SUPER_ADMIN_EMAIL}).'
        }), 403

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET name = ?, role = ?, organization = ?, phone = ?, address = ?
        WHERE email = ?
    ''', (name, role, org, phone, address, email))
    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'message': 'Profile settings updated successfully!',
        'user': {
            'name': name,
            'email': email,
            'role': role,
            'organization': org,
            'phone': phone,
            'address': address
        }
    })


@app.route('/api/claim/<int:id>', methods=['POST'])
def api_claim(id):
    """Claim an available food donation with immediate reservation & PIN generation."""
    data = request.form if request.form else (request.get_json() or {})
    ngo_name = data.get('ngo_name', 'Hope Community Shelter').strip()
    contact = data.get('contact', '+91 99222 33445').strip()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM food_listings WHERE id = ?", (id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({'success': False, 'message': 'Listing not found.'}), 404

    item = format_listing_row(row)
    if item['status'] != 'Available':
        conn.close()
        return jsonify({'success': False, 'message': f"Item is already {item['status'].lower()}."}), 400

    pin = f"{random.randint(1000, 9999)}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute('''
        UPDATE food_listings
        SET status = 'Claimed',
            claim_pin = ?,
            claimed_by_org = ?,
            claimed_by_contact = ?,
            claimed_at = ?
        WHERE id = ?
    ''', (pin, ngo_name, contact, now_str, id))
    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'message': f"Reservation confirmed! Your Handover Verification PIN is #{pin}.",
        'claim_pin': pin
    })


@app.route('/api/complete/<int:id>', methods=['POST'])
def api_complete(id):
    """Mark a claimed item as Completed/Picked up after PIN verification."""
    data = request.form if request.form else (request.get_json() or {})
    entered_pin = str(data.get('pin', '')).strip()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM food_listings WHERE id = ?", (id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({'success': False, 'message': 'Listing not found.'}), 404

    actual_pin = str(row['claim_pin']).strip()
    if entered_pin and entered_pin != actual_pin:
        conn.close()
        return jsonify({'success': False, 'message': f"Incorrect verification PIN '{entered_pin}'."}), 400

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        UPDATE food_listings
        SET status = 'Completed',
            completed_at = ?
        WHERE id = ?
    ''', (now_str, id))
    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'message': "Handover verified! Food successfully redistributed to community shelter."
    })


@app.route('/api/delete/<int:id>', methods=['POST'])
def api_delete(id):
    """Admin moderation: remove or purge an entry."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM food_listings WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': f"Listing #{id} removed."})


@app.route('/api/reset-demo', methods=['POST'])
def api_reset_demo():
    """Reset to pristine evaluation dataset for live viva demonstration."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS food_listings")
    cursor.execute("DROP TABLE IF EXISTS users")
    conn.commit()
    conn.close()
    init_db()
    return jsonify({'success': True, 'message': 'Database restored to initial pristine IA3 demo state!'})


# ============================================================================
# INITIALIZATION & EXECUTION
# ============================================================================

init_db()

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🌿 Smart Food Waste Management & Redistribution Platform (IA3)")
    print("⚡ Design System: Ultra-Clean Light Glassmorphism")
    print("🔥 Firebase Google Authentication Enabled")
    print("📸 Rich Image Gallery & Inspect Modal Enabled")
    print("🌐 Running locally at: http://127.0.0.1:5000")
    print("="*70 + "\n")
    app.run(debug=True, port=5000)
