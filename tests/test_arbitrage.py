import unittest
from arbitrage_engine import arbitrage_engine


class TestArbitrageEngine(unittest.TestCase):
    def test_sub_spot_detection(self):
        # Product listed at Rs 70,000 for 10g when 24K spot is Rs 7,400/g (spot total = Rs 74,000)
        product = {
            "source": "Tata CLiQ",
            "title": "10g 24K Gold Bar 999 Purity",
            "selling_price": 70000.0,
            "weight_grams": 10.0,
            "purity": "24K",
            "is_jewellery": False
        }
        spot_rates = {"24K": 7400.0, "22K": 6780.0, "18K": 5550.0}
        deal = arbitrage_engine.evaluate_product_arbitrage(product, spot_rates)
        self.assertTrue(deal["is_sub_spot"])
        self.assertGreater(deal["spread_per_gram"], 0)
        self.assertEqual(deal["deal_type"], "SUB_SPOT_BULLION")

    def test_low_making_charge_jewellery(self):
        # 10g 22K chain priced at pure gold value + 2% making charge
        spot_22k = 6780.0
        pure_val = spot_22k * 10.0  # 67,800
        selling_price = pure_val * 1.02 * 1.03  # with 2% making charge and 3% GST
        product = {
            "source": "Candere",
            "title": "22K Gold Chain 10g",
            "selling_price": round(selling_price, 2),
            "weight_grams": 10.0,
            "purity": "22K",
            "is_jewellery": True
        }
        spot_rates = {"24K": 7400.0, "22K": spot_22k, "18K": 5550.0}
        deal = arbitrage_engine.evaluate_product_arbitrage(product, spot_rates)
        self.assertTrue(deal["is_low_making"])
        self.assertLessEqual(deal["effective_making_charge_pct"], 4.0)


if __name__ == "__main__":
    unittest.main()
