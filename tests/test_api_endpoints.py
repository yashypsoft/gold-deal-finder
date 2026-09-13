import unittest
from fastapi.testclient import TestClient
from api import app


class TestAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_check(self):
        res = self.client.get("/api/v1/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("db_mode", data)

    def test_subscription_plans(self):
        res = self.client.get("/api/v1/subscription/plans")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertGreater(len(data["plans"]), 2)

    def test_cards_catalog(self):
        res = self.client.get("/api/v1/cards/catalog")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("cards", data)
        self.assertIn("active_bank_offers", data)

    def test_card_stack_calculation(self):
        payload = {
            "selling_price": 74000.0,
            "weight_grams": 10.0,
            "purity": "24K",
            "coupon_discount": 1200.0,
            "coupon_code": "PROMO10",
            "card_ids": ["HDFC_INFINIA", "TATA_NEU_INFINITY"]
        }
        res = self.client.post("/api/v1/cards/stack", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        stack = data["stack"]
        self.assertGreater(stack["total_savings_inr"], 2000.0)

    def test_sgb_screener_endpoint(self):
        res = self.client.get("/api/v1/sgb/screener")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertGreater(data["count"], 0)
        self.assertIn("tranches", data)

    def test_arbitrage_radar_endpoint(self):
        res = self.client.get("/api/v1/arbitrage/sub-spot")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("spot_rates", data)
        self.assertIn("sub_spot_deals", data)

    def test_scan_sites_selection_and_bhima_exclusion(self):
        from api import scan_manager
        # Check all known sites
        all_sites = scan_manager._init_sites(selected_keys=None)
        self.assertEqual(len(all_sites), 9)

        # Check selective subset (e.g. only Joyalukkas)
        selective = scan_manager._init_sites(selected_keys=["joyalukkas"])
        self.assertEqual(len(selective), 1)
        self.assertIn("joyalukkas", selective)
        self.assertNotIn("bhima", selective)

        # Check default 8 stores (excluding bhima)
        default_keys = ["ajio", "myntra", "candere", "tanishq", "mmtc", "josalukkas", "joyalukkas", "malabar"]
        filtered_default = scan_manager._init_sites(selected_keys=default_keys)
        self.assertEqual(len(filtered_default), 8)
        self.assertNotIn("bhima", filtered_default)

    def test_gold_scraper_scrape_all_accepts_sites(self):
        from gold_scraper import GoldScraper
        import inspect
        scraper = GoldScraper()
        sig = inspect.signature(scraper.scrape_all)
        self.assertIn("sites", sig.parameters)


if __name__ == "__main__":
    unittest.main()
