from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='donor')  # 'donor', 'receiver', 'admin'
    organization = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(255), nullable=True)
    is_verified = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    donations = db.relationship('FoodDonation', backref='donor', lazy=True, foreign_keys='FoodDonation.donor_id')
    claimed_donations = db.relationship('FoodDonation', backref='claimed_by_user', lazy=True, foreign_keys='FoodDonation.claimed_by_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'organization': self.organization,
            'phone': self.phone,
            'is_verified': self.is_verified
        }


class FoodDonation(db.Model):
    __tablename__ = 'food_donations'

    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Food Details
    item_name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # Cooked Meal, Bakery, Packaged Goods, Raw Produce
    dietary_type = db.Column(db.String(20), nullable=False)  # Veg, Non-Veg, Vegan
    quantity_kg = db.Column(db.Float, nullable=False)
    servings_estimate = db.Column(db.Integer, nullable=False)
    storage_condition = db.Column(db.String(50), nullable=False)  # Chilled (4°C), Hot Insulated (>60°C), Room Temp / Dry
    
    # Time Tracking
    prepared_at = db.Column(db.DateTime, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    
    # Logistics
    pickup_address = db.Column(db.String(255), nullable=False)
    pickup_contact = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text, nullable=True)  # Allergen or packaging remarks
    
    # Status & Handover Security
    status = db.Column(db.String(20), default='Available')  # 'Available', 'Claimed', 'Completed', 'Expired'
    claim_pin = db.Column(db.String(6), nullable=True)  # Secure 4-6 digit handover verification code
    
    claimed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    claimed_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def current_status(self):
        """Dynamic status evaluation taking real-time expiry into account."""
        now = datetime.now()
        # If naive comparison is needed
        exp = self.expires_at.replace(tzinfo=None) if self.expires_at.tzinfo else self.expires_at
        
        if self.status == 'Available' and now > exp:
            return 'Expired'
        return self.status

    @property
    def time_remaining_seconds(self):
        """Returns remaining seconds until expiry. Negative if expired."""
        now = datetime.now()
        exp = self.expires_at.replace(tzinfo=None) if self.expires_at.tzinfo else self.expires_at
        delta = exp - now
        return int(delta.total_seconds())

    @property
    def urgency_level(self):
        """Categorize urgency based on hours remaining: critical, warning, safe, expired."""
        secs = self.time_remaining_seconds
        if secs <= 0 or self.current_status == 'Expired':
            return 'expired'
        hours = secs / 3600.0
        if hours < 2.0:
            return 'critical'   # Red badge: <2 hours
        elif hours < 6.0:
            return 'warning'    # Amber badge: 2-6 hours
        return 'safe'           # Green badge: >6 hours

    @property
    def co2_saved_kg(self):
        """Standard environmental index: 1 kg food waste ≈ 2.5 kg CO2 equivalent avoided."""
        return round(self.quantity_kg * 2.5, 2)

    @property
    def water_saved_liters(self):
        """Standard environmental index: 1 kg food waste ≈ 1,000 liters virtual water saved."""
        return round(self.quantity_kg * 1000, 1)

    def to_dict(self):
        return {
            'id': self.id,
            'donor_id': self.donor_id,
            'donor_name': self.donor.name if self.donor else 'Unknown',
            'donor_org': self.donor.organization if self.donor else 'Unknown',
            'item_name': self.item_name,
            'category': self.category,
            'dietary_type': self.dietary_type,
            'quantity_kg': self.quantity_kg,
            'servings_estimate': self.servings_estimate,
            'storage_condition': self.storage_condition,
            'prepared_at': self.prepared_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'pickup_address': self.pickup_address,
            'pickup_contact': self.pickup_contact,
            'notes': self.notes,
            'status': self.current_status,
            'urgency_level': self.urgency_level,
            'time_remaining_seconds': self.time_remaining_seconds,
            'claim_pin': self.claim_pin if self.current_status in ['Claimed', 'Completed'] else None,
            'claimed_by_name': self.claimed_by_user.name if self.claimed_by_user else None,
            'claimed_by_org': self.claimed_by_user.organization if self.claimed_by_user else None,
            'co2_saved_kg': self.co2_saved_kg,
            'water_saved_liters': self.water_saved_liters
        }
