"""
Automated Test Suite for Smart Food Waste Management & Redistribution Platform
Designed for Local Execution and Continuous Integration (GitHub Actions)
Covers: Positive, Negative, Boundary, Functional, Integration, and Validation Testing
"""

import os
import json
import unittest
from app import app, init_db, get_db, SUPER_ADMIN_EMAIL


class FoodRedistributionSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        cls.client = app.test_client()
        with app.app_context():
            init_db()

    def setUp(self):
        # Reset database to clean sample demonstration state before each test
        self.client.post('/api/reset-demo')

    # ========================================================================
    # 1. POSITIVE TESTING
    # ========================================================================

    def test_tc_pos_01_create_valid_listing(self):
        """TC-POS-01: Broadcast available surplus food lot with complete valid data."""
        payload = {
            'item_name': 'Steamed Basmati Rice & Dal Fry',
            'donor_org': 'Campus Central Mess (Hostel A)',
            'category': 'Cooked Meal',
            'dietary_type': 'Veg',
            'quantity_kg': 30.0,
            'expiry_hours': 4.0,
            'storage_condition': 'Hot Insulated (>60°C)',
            'pickup_address': 'Hostel Dining Complex Gate 1',
            'notes': 'Prepared fresh for dinner'
        }
        res = self.client.post('/api/listings', data=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('listing_id', data)

    def test_tc_pos_02_claim_available_lot(self):
        """TC-POS-02: Verified shelter NGO claims available surplus lot and receives 4-digit PIN."""
        # Find first available listing
        listings_res = self.client.get('/api/listings')
        listings = listings_res.get_json()['listings']
        available = [item for item in listings if item['status'] == 'Available']
        self.assertTrue(len(available) > 0, "No available listings to claim")

        target_id = available[0]['id']
        claim_payload = {
            'ngo_name': 'Hope Community Shelter',
            'contact': '+91 99222 33445'
        }
        res = self.client.post(f'/api/claim/{target_id}', json=claim_payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('claim_pin', data)
        self.assertEqual(len(str(data['claim_pin'])), 4)

    def test_tc_pos_03_complete_handover_with_valid_pin(self):
        """TC-POS-03: Complete physical handover verification with matching PIN."""
        # Claim listing #1 first
        claim_res = self.client.post('/api/claim/1', json={'ngo_name': 'Hope Shelter', 'contact': '+91 99222 33445'})
        pin = claim_res.get_json()['claim_pin']

        # Complete handover
        comp_res = self.client.post('/api/complete/1', json={'pin': pin})
        self.assertEqual(comp_res.status_code, 200)
        data = comp_res.get_json()
        self.assertTrue(data['success'])

    def test_tc_pos_04_google_auth_sync(self):
        """TC-POS-04: Google OAuth account authentication and profile sync."""
        payload = {
            'email': 'mentor_evaluator@example.com',
            'displayName': 'Dr. Academic Mentor',
            'photoURL': 'https://example.com/avatar.jpg',
            'role': 'donor'
        }
        res = self.client.post('/api/auth/google-sync', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['user']['email'], 'mentor_evaluator@example.com')

    def test_tc_pos_05_export_audit_csv(self):
        """TC-POS-05: Export food redistribution logs to Excel/CSV audit format."""
        res = self.client.get('/api/export/csv')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'text/csv')
        self.assertIn('Listing ID', res.data.decode('utf-8'))
        self.assertIn('Food Item Name', res.data.decode('utf-8'))
        self.assertIn('FSSAI Food Safety Compliance', res.data.decode('utf-8'))

    # ========================================================================
    # 2. NEGATIVE TESTING
    # ========================================================================

    def test_tc_neg_01_unauthorized_user_admin_access_rejected(self):
        """TC-NEG-01: Unauthorized user cannot update profile to admin (HTTP 403 Forbidden)."""
        payload = {
            'email': 'student_hacker@campus.edu',
            'name': 'Hacker Student',
            'role': 'admin',
            'organization': 'Unauthorized Group',
            'phone': '+91 99999 00000',
            'address': 'Dorm Room 101'
        }
        res = self.client.post('/api/user/update-profile', json=payload)
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('Access Denied', data['message'])

    def test_tc_neg_02_double_claim_rejected(self):
        """TC-NEG-02: Double claim on already claimed lot rejected with HTTP 400."""
        # Listing #4 is already seeded as 'Claimed'
        res = self.client.post('/api/claim/4', json={'ngo_name': 'Second Shelter', 'contact': '+91 90000 00000'})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('already', data['message'].lower())

    def test_tc_neg_03_invalid_handover_pin_rejected(self):
        """TC-NEG-03: Invalid handover PIN rejected with HTTP 400."""
        # Listing #4 has genuine pin '7842'
        res = self.client.post('/api/complete/4', json={'pin': '0000'})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('pin', data['message'].lower())

    def test_tc_neg_04_negative_quantity_rejected(self):
        """TC-NEG-04: Negative food quantity rejected with HTTP 400."""
        payload = {
            'item_name': 'Invalid Lot',
            'quantity_kg': -25.0,
            'expiry_hours': 3.0
        }
        res = self.client.post('/api/listings', data=payload)
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data['success'])

    # ========================================================================
    # 3. BOUNDARY TESTING
    # ========================================================================

    def test_tc_bnd_01_minimum_expiry_window(self):
        """TC-BND-01: Minimum safe window boundary (0.1 hours / 6 minutes)."""
        payload = {
            'item_name': 'Fresh Cut Fruit Salad',
            'donor_org': 'Canteen Counter',
            'category': 'Raw Produce',
            'dietary_type': 'Veg',
            'quantity_kg': 5.0,
            'expiry_hours': 0.1,
            'storage_condition': 'Chilled (4°C)',
            'pickup_address': 'Counter 3'
        }
        res = self.client.post('/api/listings', data=payload)
        self.assertEqual(res.status_code, 200)
        new_id = res.get_json()['listing_id']

        # Verify urgency level is critical (<2h)
        listings = self.client.get('/api/listings').get_json()['listings']
        created = next(item for item in listings if item['id'] == new_id)
        self.assertEqual(created['urgency_level'], 'critical')

    def test_tc_bnd_02_minimum_quantity_boundary(self):
        """TC-BND-02: Smallest allowed food quantity (0.1 kg)."""
        payload = {
            'item_name': 'Micro Surplus Sample',
            'quantity_kg': 0.1,
            'expiry_hours': 2.0
        }
        res = self.client.post('/api/listings', data=payload)
        self.assertEqual(res.status_code, 200)

    def test_tc_bnd_03_pin_range_boundary(self):
        """TC-BND-03: Handover PIN strictly contained in [1000, 9999]."""
        res = self.client.post('/api/claim/1', json={'ngo_name': 'Test Shelter', 'contact': '+91 99999 11111'})
        pin = int(res.get_json()['claim_pin'])
        self.assertTrue(1000 <= pin <= 9999)

    def test_tc_bnd_04_expired_lot_cannot_be_claimed(self):
        """TC-BND-04: Listing past expiration window cannot be claimed."""
        # Listing #5 is seeded as expired
        res = self.client.post('/api/claim/5', json={'ngo_name': 'Shelter', 'contact': '+91 99999 11111'})
        self.assertEqual(res.status_code, 400)

    # ========================================================================
    # 4. FUNCTIONAL TESTING
    # ========================================================================

    def test_tc_fnc_01_super_admin_role_preservation(self):
        """TC-FNC-01: kavinprasanth2306@gmail.com is always authorized with admin role."""
        payload = {
            'email': SUPER_ADMIN_EMAIL,
            'displayName': 'Dr. Kavin Prasanth',
            'role': 'receiver' # Client passes receiver, server must preserve admin
        }
        res = self.client.post('/api/auth/google-sync', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['user']['role'], 'admin')

    def test_tc_fnc_02_update_profile_super_admin(self):
        """TC-FNC-02: Super admin can update profile with admin role successfully."""
        payload = {
            'email': SUPER_ADMIN_EMAIL,
            'name': 'Dr. Kavin Prasanth',
            'role': 'admin',
            'organization': 'University Food Safety Board',
            'phone': '+91 99222 33445',
            'address': 'Admin Complex Gate 1'
        }
        res = self.client.post('/api/user/update-profile', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['user']['role'], 'admin')

    def test_tc_fnc_03_homepage_renders_cleanly(self):
        """TC-FNC-03: Homepage renders HTTP 200 with all critical UI panels."""
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn('EcoRescue', html)
        self.assertIn('openConsentModal', html)
        self.assertIn('openProfileModal', html)

    # ========================================================================
    # 5. INTEGRATION TESTING
    # ========================================================================

    def test_tc_int_01_handover_recalculates_telemetry(self):
        """TC-INT-01: Claiming an available surplus lot recalculates carbon and meals saved telemetry."""
        # Initial metrics (seed has 22 kg claimed)
        m0 = self.client.get('/api/metrics').get_json()['metrics']
        initial_kg = m0['total_kg_saved']
        initial_co2 = m0['total_co2_avoided_kg']

        # Claim listing #1 (seeded Available with 28.5 kg)
        self.client.post('/api/claim/1', json={'ngo_name': 'Hope Shelter', 'contact': '+91 99222 33445'})

        # Post metrics
        m1 = self.client.get('/api/metrics').get_json()['metrics']
        self.assertAlmostEqual(m1['total_kg_saved'], initial_kg + 28.5, places=1)
        self.assertAlmostEqual(m1['total_co2_avoided_kg'], initial_co2 + (28.5 * 2.5), places=1)

    def test_tc_int_02_reset_demo_pipeline(self):
        """TC-INT-02: Reset demo endpoint repopulates exactly 5 pristine listings."""
        res = self.client.post('/api/reset-demo')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

        listings = self.client.get('/api/listings').get_json()['listings']
        self.assertEqual(len(listings), 5)

    # ========================================================================
    # 6. VALIDATION & ERROR HANDLING
    # ========================================================================

    def test_tc_val_01_claim_non_existent_listing(self):
        """TC-VAL-01: Requesting claim for non-existent listing ID returns HTTP 404."""
        res = self.client.post('/api/claim/99999', json={'ngo_name': 'Test', 'contact': '123'})
        self.assertEqual(res.status_code, 404)
        data = res.get_json()
        self.assertFalse(data['success'])

    def test_tc_val_02_empty_item_name_validation(self):
        """TC-VAL-02: Missing required item name rejected with HTTP 400."""
        payload = {
            'item_name': '',
            'quantity_kg': 10.0,
            'expiry_hours': 3.0
        }
        res = self.client.post('/api/listings', data=payload)
        self.assertEqual(res.status_code, 400)

    # ========================================================================
    # 7. MESS DONOR OPERATIONS & DISPATCH
    # ========================================================================

    def test_tc_donor_01_extend_safety_window(self):
        """TC-DONOR-01: Mess donor extends safe consumption window by +45 minutes under hot holding."""
        res = self.client.post('/api/listing/1/extend', json={'minutes': 45})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('+45 minutes', data['message'])

    def test_tc_donor_02_cancel_claim_reservation(self):
        """TC-DONOR-02: Mess donor releases NGO reservation if vehicle cannot arrive in time."""
        # Listing #4 is seeded as Claimed
        res = self.client.post('/api/listing/4/cancel-claim')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

        # Verify listing #4 is now Available and PIN is voided
        listings = self.client.get('/api/listings').get_json()['listings']
        l4 = next(i for i in listings if i['id'] == 4)
        self.assertEqual(l4['status'], 'Available')
        self.assertIsNone(l4['claim_pin'])

    def test_tc_donor_03_cancel_claim_invalid_status(self):
        """TC-DONOR-03: Attempting to release an un-claimed listing returns HTTP 400."""
        res = self.client.post('/api/listing/1/cancel-claim')
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data['success'])


if __name__ == '__main__':
    unittest.main()
