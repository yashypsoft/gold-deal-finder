import unittest
from sgb_screener import sgb_screener


class TestSGBScreener(unittest.TestCase):
    def test_scan_tranches(self):
        tranches = sgb_screener.scan_all_tranches()
        self.assertGreater(len(tranches), 0)
        top = tranches[0]
        self.assertIn("ticker", top)
        self.assertIn("discount_to_spot_pct", top)
        self.assertIn("annualized_ytm_pct", top)
        self.assertIn("ltp", top)
        self.assertGreater(top["ltp"], 1000)

    def test_ytm_math(self):
        # A bond maturing in 2028 with coupon 2.5% trading below redemption spot should have positive YTM
        ytm = sgb_screener.calculate_ytm(
            current_price=6800.0,
            maturity_date_str="2028-10-23",
            issue_price=3000.0,
            coupon_rate=2.5,
            redemption_spot_price=7400.0
        )
        self.assertGreater(ytm, 4.0)


if __name__ == "__main__":
    unittest.main()
