import unittest
from gold_scraper import GoldScraper
from price_calculator import GoldPriceCalculator


class TestJoyalukkasCaratMapping(unittest.TestCase):
    def setUp(self):
        self.scraper = GoldScraper()
        self.calculator = GoldPriceCalculator()

    def test_extract_purity_patterns(self):
        self.assertEqual(self.scraper.extract_purity("22 KT Yellow Gold"), "22K")
        self.assertEqual(self.scraper.extract_purity("24 KT Yellow Gold"), "24K")
        self.assertEqual(self.scraper.extract_purity("18 KT Rose Gold"), "18K")
        self.assertEqual(self.scraper.extract_purity("14 KT Gold"), "14K")
        self.assertEqual(self.scraper.extract_purity("999 Pure Gold"), "24K")
        self.assertEqual(self.scraper.extract_purity("916 Hallmarked"), "22K")
        self.assertIsNone(self.scraper.extract_purity("8 Gram New Born Gold Coin"))
        self.assertIsNone(self.scraper.extract_purity(""))
        self.assertIsNone(self.scraper.extract_purity(None))

    def test_extract_purity_and_weight_with_default(self):
        # When explicit karat is in title, it should be honored
        purity, weight = self.scraper.extract_purity_and_weight("Joyalukkas 24K Gold Coin 5g", default_purity="22K")
        self.assertEqual(purity, "24K")
        self.assertEqual(weight, 5.0)

        # When no karat is in title and default_purity='22K' is provided, it must not default to 24K
        purity, weight = self.scraper.extract_purity_and_weight("8 Gram New Born Gold Coin", default_purity="22K")
        self.assertEqual(purity, "22K")
        self.assertEqual(weight, 8.0)

    def test_joyalukkas_carat_mapping_fallback_to_22k(self):
        """
        Verify Joyalukkas fallback rules:
        1. Explicit metal_label 22KT -> 22K
        2. Carat not found anywhere (metal_label empty, no carat in title/sku) -> 22K (NOT 24K)
        3. Explicit 24KT in metal_label -> 24K
        """
        # Case 1: Standard Joyalukkas coin with metal_label
        item_with_metal = {
            "name": "8 Gram New Born Gold Coin",
            "metal_label": "22 KT Yellow Gold",
            "sku": "ONGCNNB22G8",
            "url_key": "8-gram-new-born-gold-coin-ongcnnb22g8"
        }
        purity = self.scraper.extract_purity(item_with_metal.get("metal_label"))
        if not purity:
            purity = self.scraper.extract_purity(item_with_metal.get("name"))
        if not purity:
            purity = self.scraper.extract_purity(f"{item_with_metal.get('sku')} {item_with_metal.get('url_key')}")
        if not purity:
            purity = "22K"
        _, weight = self.scraper.extract_purity_and_weight(item_with_metal["name"], default_purity=purity)
        self.assertEqual(purity, "22K")
        self.assertEqual(weight, 8.0)

        # Case 2: Carat completely missing from metal_label and title
        item_missing_carat = {
            "name": "1 Gram Plain Gold Coin",
            "metal_label": "",
            "sku": "2022A1GH5",
            "url_key": "1-gram-plain-gold-coin-2022a1gh5"
        }
        purity = self.scraper.extract_purity(item_missing_carat.get("metal_label"))
        if not purity:
            purity = self.scraper.extract_purity(item_missing_carat.get("name"))
        if not purity:
            purity = self.scraper.extract_purity(f"{item_missing_carat.get('sku')} {item_missing_carat.get('url_key')}")
        if not purity:
            purity = "22K"
        _, weight = self.scraper.extract_purity_and_weight(item_missing_carat["name"], default_purity=purity)
        self.assertEqual(purity, "22K")
        self.assertEqual(weight, 1.0)

        # Case 3: Explicit 24K coin
        item_24k = {
            "name": "Joyalukkas 24KT 10g Bar",
            "metal_label": "24 KT Yellow Gold",
            "sku": "JOY24K10",
            "url_key": "joyalukkas-24kt-10g-bar"
        }
        purity = self.scraper.extract_purity(item_24k.get("metal_label"))
        if not purity:
            purity = self.scraper.extract_purity(item_24k.get("name"))
        if not purity:
            purity = self.scraper.extract_purity(f"{item_24k.get('sku')} {item_24k.get('url_key')}")
        if not purity:
            purity = "22K"
        self.assertEqual(purity, "24K")

    def test_pricing_accuracy_22k_vs_24k(self):
        """
        Selling price of ₹121,303 for 8g coin (~₹15,163/g) is realistic for 22K,
        and should NOT show fake ~7% arbitrage discount vs 24K spot.
        """
        weight = 8.0
        selling_price = 121303.0

        # With wrong 24K assignment:
        exp_24k = self.calculator.calculate_expected_price(weight, "24K", is_jewellery=False)
        disc_24k = self.calculator.calculate_discount_percentage(selling_price, exp_24k["total_expected"])
        self.assertGreater(disc_24k, 5.0)  # Fake discount > 5%

        # With correct 22K assignment:
        exp_22k = self.calculator.calculate_expected_price(weight, "22K", is_jewellery=False)
        disc_22k = self.calculator.calculate_discount_percentage(selling_price, exp_22k["total_expected"])
        # Expected price for 22K is lower than selling price (discount is negative / premium), which is correct!
        self.assertLess(disc_22k, 0.0)


if __name__ == "__main__":
    unittest.main()
