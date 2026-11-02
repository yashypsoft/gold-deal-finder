import unittest
from fastapi.testclient import TestClient
from api import app, _fetch_dealer_rates_sync
from price_calculator import GoldPriceCalculator


class TestDealerRatesBenchmark(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.calculator = GoldPriceCalculator()

    def test_dealer_rates_summary(self):
        rates = _fetch_dealer_rates_sync()
        self.assertIn("_summary", rates)
        summary = rates["_summary"]
        self.assertIn("lowest_rate_24k", summary)
        self.assertIn("lowest_rate_22k", summary)
        self.assertIn("lowest_brand", summary)
        self.assertGreater(summary["lowest_rate_24k"], 5000.0)
        self.assertGreater(summary["lowest_rate_22k"], 4000.0)

    def test_gold_calculator_uses_dealer_lowest(self):
        gold_data = self.calculator.get_live_gold_price()
        self.assertEqual(gold_data.get("source"), "dealer_lowest_rate")
        self.assertIn("lowest_dealer", gold_data)
        self.assertGreater(gold_data["spot_price_per_gram"], 5000.0)

    def test_spot_price_endpoint_returns_dealer_lowest(self):
        res = self.client.get("/api/v1/spot-price")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("source"), "dealer_lowest_rate")
        self.assertIn("lowest_dealer", data)

    def test_product_metrics_benchmark_comparison(self):
        gold_data = self.calculator.get_live_gold_price()
        expected = self.calculator.calculate_expected_price(1.0, "24K", is_jewellery=False)
        self.assertEqual(expected["total_expected"], gold_data["spot_price_per_gram"])


if __name__ == "__main__":
    unittest.main()
