"""
Seed script for Smart Food Waste Management & Redistribution Platform.
Populates realistic test data for instant academic evaluation and demo.
"""
from datetime import datetime, timedelta
from app import app, db
from models import User, FoodDonation

def seed_database():
    with app.app_context():
        # Clean existing tables
        db.drop_all()
        db.create_all()

        print("[*] Creating Users...")
        # Donors
        donor1 = User(
            name="Rahul Sharma (Mess Manager)",
            email="donor@campus.edu",
            role="donor",
            organization="Campus Central Mess (Block A)",
            phone="+91 98765 43210",
            address="Campus Dining Complex, North Wing, Gate 2",
            is_verified=True
        )
        donor1.set_password("donor123")

        donor2 = User(
            name="Chef Vikram Singhania",
            email="royal@banquet.com",
            role="donor",
            organization="Grand Royal Banquet & Restaurant",
            phone="+91 98111 22334",
            address="Plot 45, Sector 18, Commercial Zone",
            is_verified=True
        )
        donor2.set_password("donor123")

        # Receivers (NGOs / Shelters)
        receiver1 = User(
            name="Ananya Desai (Coordinator)",
            email="shelter@hope.org",
            role="receiver",
            organization="Hope Community Shelter & Food Bank",
            phone="+91 99222 33445",
            address="12-B Old City Road, Near Civil Hospital",
            is_verified=True
        )
        receiver1.set_password("receiver123")

        receiver2 = User(
            name="Karthik Verma (Logistics Lead)",
            email="seva@ngo.org",
            role="receiver",
            organization="Seva Youth Volunteer Foundation",
            phone="+91 97333 44556",
            address="Shelter Haven, Ring Road Junction",
            is_verified=True
        )
        receiver2.set_password("receiver123")

        # Admin
        admin = User(
            name="Prof. K. Venkatesh (Admin Moderator)",
            email="admin@foodwaste.org",
            role="admin",
            organization="Smart Food Redistribution Authority",
            phone="+91 90000 11111",
            address="University Center for Sustainable Tech",
            is_verified=True
        )
        admin.set_password("admin123")

        db.session.add_all([donor1, donor2, receiver1, receiver2, admin])
        db.session.commit()

        print("[*] Creating Food Donation Listings...")
        now = datetime.now()

        # Item 1: Active - High Urgency (< 2 hours remaining)
        item1 = FoodDonation(
            donor_id=donor1.id,
            item_name="Steamed Basmati Rice, Paneer Butter Masala & 80 Rotis",
            category="Cooked Meal",
            dietary_type="Veg",
            quantity_kg=28.5,
            servings_estimate=60,
            storage_condition="Hot Insulated (>60°C)",
            prepared_at=now - timedelta(hours=2),
            expires_at=now + timedelta(hours=1, minutes=35),  # 1h 35m left!
            pickup_address="Campus Dining Complex, Mess Loading Dock A",
            pickup_contact="+91 98765 43210 (Mess Supervisor)",
            notes="Packed in clean food-grade insulated steel containers. Safe for immediate distribution.",
            status="Available",
            created_at=now - timedelta(hours=2)
        )

        # Item 2: Active - Safe Window (approx 5.5 hours remaining)
        item2 = FoodDonation(
            donor_id=donor2.id,
            item_name="Assorted Fresh Bread Loaves, Croissants & Veg Sandwiches",
            category="Bakery",
            dietary_type="Veg",
            quantity_kg=14.0,
            servings_estimate=40,
            storage_condition="Room Temp / Dry",
            prepared_at=now - timedelta(hours=3),
            expires_at=now + timedelta(hours=5, minutes=30),  # 5h 30m left
            pickup_address="Grand Royal Banquet Kitchen Gate, Sector 18",
            pickup_contact="+91 98111 22334 (Head Chef)",
            notes="Individually wrapped and packed in dry carton trays. Contains wheat and dairy.",
            status="Available",
            created_at=now - timedelta(hours=3)
        )

        # Item 3: Active - Non-Veg (3.5 hours remaining)
        item3 = FoodDonation(
            donor_id=donor2.id,
            item_name="Hyderabadi Chicken Dum Biryani & Mirchi Ka Salan",
            category="Cooked Meal",
            dietary_type="Non-Veg",
            quantity_kg=35.0,
            servings_estimate=75,
            storage_condition="Hot Insulated (>60°C)",
            prepared_at=now - timedelta(hours=1, minutes=30),
            expires_at=now + timedelta(hours=3, minutes=30),
            pickup_address="Grand Royal Banquet Main Entrance, Sector 18",
            pickup_contact="+91 98111 22334 (Banquet Manager)",
            notes="Surplus from afternoon corporate banquet. High temperature maintained in thermal cafs.",
            status="Available",
            created_at=now - timedelta(hours=1, minutes=30)
        )

        # Item 4: Claimed - In Transit (Handover PIN active)
        item4 = FoodDonation(
            donor_id=donor1.id,
            item_name="Dal Tadka, Jeera Rice & Mixed Veg Sabzi",
            category="Cooked Meal",
            dietary_type="Veg",
            quantity_kg=22.0,
            servings_estimate=50,
            storage_condition="Chilled (4°C)",
            prepared_at=now - timedelta(hours=4),
            expires_at=now + timedelta(hours=4),
            pickup_address="Campus Dining Complex, Block B Storage",
            pickup_contact="+91 98765 43210 (Mr. Rahul)",
            notes="Chilled immediately post lunch. NGO vehicle en-route.",
            status="Claimed",
            claim_pin="7842",
            claimed_by_id=receiver1.id,
            claimed_at=now - timedelta(minutes=25),
            created_at=now - timedelta(hours=4)
        )

        # Item 5: Completed - Historical Impact Record
        item5 = FoodDonation(
            donor_id=donor1.id,
            item_name="Breakfast Combo: Idli, Medu Vada, Sambar & Coconut Chutney",
            category="Cooked Meal",
            dietary_type="Veg",
            quantity_kg=20.0,
            servings_estimate=45,
            storage_condition="Hot Insulated (>60°C)",
            prepared_at=now - timedelta(hours=10),
            expires_at=now - timedelta(hours=4),
            pickup_address="Campus Dining Complex, Morning Dispatch Counter",
            pickup_contact="+91 98765 43210 (Rahul)",
            notes="Delivered successfully to Seva Youth Shelter. Verified by PIN 4321.",
            status="Completed",
            claim_pin="4321",
            claimed_by_id=receiver2.id,
            claimed_at=now - timedelta(hours=8),
            completed_at=now - timedelta(hours=7),
            created_at=now - timedelta(hours=10)
        )

        # Item 6: Expired - Safety Lockout Demonstration
        item6 = FoodDonation(
            donor_id=donor2.id,
            item_name="Cream of Mushroom Soup & Garlic Croutons",
            category="Cooked Meal",
            dietary_type="Veg",
            quantity_kg=10.0,
            servings_estimate=20,
            storage_condition="Chilled (4°C)",
            prepared_at=now - timedelta(hours=14),
            expires_at=now - timedelta(hours=2),  # Expired 2 hours ago
            pickup_address="Grand Royal Banquet Kitchen",
            pickup_contact="+91 98111 22334",
            notes="Passed safety threshold. System automatically flagged as Expired.",
            status="Expired",
            created_at=now - timedelta(hours=14)
        )

        db.session.add_all([item1, item2, item3, item4, item5, item6])
        db.session.commit()

        print("[+] Seed completed successfully!")
        print(f"    - 5 Users added (Donors, Receivers, Admin)")
        print(f"    - 6 Food Donations added (3 Active, 1 Claimed, 1 Completed, 1 Expired)")

if __name__ == "__main__":
    seed_database()
