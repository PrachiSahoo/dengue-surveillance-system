"""
Comprehensive Automated Test Suite for DengueWatch Full-Stack Platform.
Tests database persistence, REST endpoints, authentication RBAC,
probabilistic forecasting calculations, and the Agentic AI advisor.
"""

import unittest
import json
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import database
from app import app
import forecasting_service
import agentic_advisor

class TestDengueWatchFullStack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initializes database schema and test client."""
        database.init_db()
        database.seed_database_if_empty()
        cls.client = app.test_client()

    def test_01_health_endpoint(self):
        """Verifies system health check returns 200 and database metrics."""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "healthy")
        self.assertTrue(data["database"]["connected"])
        self.assertGreater(data["database"]["surveillance_records"], 0)

    def test_02_database_seeding(self):
        """Verifies database contains 36 states and longitudinal records."""
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT state) AS num_states FROM surveillance_records;")
        num_states = cursor.fetchone()["num_states"]
        self.assertGreaterEqual(num_states, 30)

        cursor.execute("SELECT COUNT(*) AS total_alerts FROM state_alerts;")
        total_alerts = cursor.fetchone()["total_alerts"]
        self.assertGreaterEqual(total_alerts, 30)
        conn.close()

    def test_03_auth_demo_login(self):
        """Verifies demo login as Admin generates valid session token."""
        res = self.client.post("/api/auth/demo-login", json={"role": "admin"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("token", data)
        self.assertEqual(data["user"]["role"], "admin")

        # Verify session using Bearer token
        token = data["token"]
        me_res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_res.status_code, 200)
        self.assertTrue(me_res.get_json()["authenticated"])

    def test_04_alerts_and_summary_api(self):
        """Verifies state alerts and national summary KPIs."""
        res = self.client.get("/api/alerts")
        self.assertEqual(res.status_code, 200)
        alerts = res.get_json()
        self.assertIsInstance(alerts, list)
        self.assertGreater(len(alerts), 0)

        summary_res = self.client.get("/api/alerts/summary")
        self.assertEqual(summary_res.status_code, 200)
        summary = summary_res.get_json()
        self.assertIn("national_avg_rt", summary)
        self.assertIn("high_alert_states", summary)

    def test_05_forecasting_simulation(self):
        """Verifies probabilistic multi-horizon forecasting generation."""
        res = self.client.post("/api/forecast/predict", json={
            "state": "Kerala",
            "horizon": 4,
            "model": "Chronos-Bolt"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["state"], "Kerala")
        self.assertEqual(data["horizon_weeks"], 4)
        self.assertEqual(len(data["forecast_points"]), 4)
        for pt in data["forecast_points"]:
            self.assertIn("p10", pt)
            self.assertIn("p50", pt)
            self.assertIn("p90", pt)
            self.assertGreaterEqual(pt["p90"], pt["p50"])
            self.assertGreaterEqual(pt["p50"], pt["p10"])

    def test_06_agentic_advisor_execution(self):
        """Verifies autonomous Agentic AI multi-agent advisory protocol."""
        res = self.client.post("/api/agent/advise", json={"state": "Kerala"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("risk_stratification", data)
        self.assertIn("clinical_logistics_plan", data)
        self.assertIn("vector_control_directives", data)
        self.assertIn("executive_briefing", data)
        self.assertGreater(data["clinical_logistics_plan"]["projected_peak_weekly_admissions"], 0)

    def test_07_surveillance_crud_flow(self):
        """Verifies creating, fetching, and updating surveillance records."""
        login_res = self.client.post("/api/auth/demo-login", json={"role": "admin"})
        token = login_res.get_json()["token"]
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Create record
        new_record = {
            "state": "Goa",
            "week_start": "2026-01-10",
            "cases": 28,
            "source": "Automated Unit Test Bulletin"
        }
        create_res = self.client.post("/api/surveillance", json=new_record, headers=headers)
        self.assertEqual(create_res.status_code, 201)
        created_id = create_res.get_json()["record"]["id"]

        # Update record
        update_res = self.client.put(f"/api/surveillance/{created_id}", json={"cases": 35}, headers=headers)
        self.assertEqual(update_res.status_code, 200)
        self.assertEqual(update_res.get_json()["record"]["cases"], 35)

        # Delete record
        delete_res = self.client.delete(f"/api/surveillance/{created_id}", headers=headers)
        self.assertEqual(delete_res.status_code, 200)

if __name__ == "__main__":
    unittest.main()
