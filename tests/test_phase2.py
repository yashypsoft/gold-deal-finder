import unittest
from fastapi.testclient import TestClient
from api import app
from receipt_generator import receipt_generator


class TestPhase2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_ascii_receipt_generation(self):
        deal = {
            "title": "10g 24K Kundan Gold Bar",
            "source": "Tata CLiQ",
            "weight_grams": 10.0,
            "purity": "24K",
            "selling_price": 149000.0,
            "live_spot_rate_per_gram": 15837.5,
            "effective_net_price": 132000.0,
            "effective_price_per_gram": 13200.0,
            "spread_per_gram": 2637.5,
            "total_stack_savings": 26375.0,
            "recommended_card": "Tata Neu Infinity HDFC"
        }
        receipt = receipt_generator.generate_ascii_receipt(deal, seconds_active=240)
        self.assertIn("ARBITRAGE PROOF", receipt)
        self.assertIn("TATA CLIQ", receipt)
        self.assertIn("15,837.5/g", receipt)
        self.assertIn("2,637.50/g", receipt)

    def test_svg_receipt_generation(self):
        deal = {
            "title": "10g 24K Kundan Gold Bar",
            "source": "Tata CLiQ",
            "weight_grams": 10.0,
            "purity": "24K",
            "selling_price": 149000.0,
            "live_spot_rate_per_gram": 15837.5,
            "effective_net_price": 132000.0,
            "effective_price_per_gram": 13200.0,
            "spread_per_gram": 2637.5,
            "total_stack_savings": 26375.0,
            "recommended_card": "Tata Neu Infinity HDFC"
        }
        svg = receipt_generator.generate_svg_receipt(deal)
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.endswith("</svg>"))
        self.assertIn("GOLD DEAL FINDER", svg)

    def test_tweet_copy_generation(self):
        deal = {
            "title": "10g 24K Gold Coin",
            "source": "Ajio",
            "weight_grams": 10.0,
            "purity": "24K",
            "selling_price": 145000.0,
            "effective_price_per_gram": 13500.0,
            "spread_per_gram": 2337.5,
            "total_stack_savings": 23375.0
        }
        tweet = receipt_generator.generate_tweet_text(deal)
        self.assertIn("GOLD ARBITRAGE FLASH ALERT", tweet)
        self.assertIn("#GoldPrice", tweet)

    def test_marketing_receipt_api(self):
        res = self.client.get("/api/v1/marketing/receipt")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("ascii_receipt", data)
        self.assertIn("tweet_copy", data)
        self.assertIn("svg_url", data)

    def test_marketing_receipt_svg_api(self):
        res = self.client.get("/api/v1/marketing/receipt/svg")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"], "image/svg+xml")
        self.assertIn("<svg", res.text)


if __name__ == "__main__":
    unittest.main()
