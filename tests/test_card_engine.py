import unittest
from card_engine import card_parser, card_stacker, CARD_REGISTRY, BankOffer


class TestCardEngine(unittest.TestCase):
    def test_parse_percentage_offer(self):
        promo_text = "10% Instant Discount with HDFC Bank Credit Cards on min spend of Rs 5,000 up to Rs 1,500"
        offer = card_parser.parse_string(promo_text)
        self.assertIsNotNone(offer)
        self.assertEqual(offer.bank_code, "HDFC")
        self.assertEqual(offer.discount_percentage, 10.0)
        self.assertEqual(offer.max_discount_inr, 1500.0)
        self.assertEqual(offer.min_transaction_inr, 5000.0)

    def test_parse_flat_offer(self):
        promo_text = "Flat Rs 1,000 Off on ICICI Credit Card on Rs 10,000 and above"
        offer = card_parser.parse_string(promo_text)
        self.assertIsNotNone(offer)
        self.assertEqual(offer.bank_code, "ICICI")
        self.assertEqual(offer.discount_percentage, 0.0)
        self.assertEqual(offer.max_discount_inr, 1000.0)
        self.assertEqual(offer.min_transaction_inr, 10000.0)

    def test_card_reward_stacking_calculation(self):
        # 10g bar priced at Rs 74,000, spot Rs 7,350/g
        res = card_stacker.calculate_stack(
            selling_price=74000.0,
            weight_grams=10.0,
            spot_price_per_gram=7350.0,
            coupon_discount=1000.0,
            coupon_code="GOLD1000",
            user_card_ids=["HDFC_INFINIA", "AMEX_PLATINUM_TRAVEL", "TATA_NEU_INFINITY"]
        )
        self.assertIsNotNone(res)
        self.assertIn("effective_net_cost", res)
        self.assertIn("effective_price_per_gram", res)
        # Verify stack savings are positive
        self.assertGreater(res["total_savings_inr"], 2000.0)
        # Verify price per gram is below catalog price
        self.assertLess(res["effective_price_per_gram"], 7400.0)


if __name__ == "__main__":
    unittest.main()
