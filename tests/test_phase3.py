import unittest
from fastapi.testclient import TestClient
from buyback_calculator import buyback_calculator
from restock_sniper import RestockSniper
from whatsapp_service import whatsapp_service
from api import app


class TestPhase3Suite(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_buyback_calculator_24k(self):
        # 10g 24K gold bar bought online for ₹1,24,345
        # Spot is ₹15,837.5/g -> Gross = ₹1,58,375.0
        # 0.25% deduction = ₹395.94 -> Net Payout = ₹1,57,979.06
        # Net Profit = ₹33,634.06
        res = buyback_calculator.calculate_liquidation(
            delivered_cost=124345.0,
            weight_grams=10.0,
            purity="24K",
            item_type="bar",
            spot_override=15837.5,
            turnover_days=5,
            payment_mode="RTGS"
        )
        self.assertTrue(res["arbitrage_viable"])
        self.assertGreater(res["net_profit_inr"], 30000)
        self.assertGreater(res["roi_pct"], 20.0)
        self.assertGreater(res["annualized_roi_pct"], 100.0)
        self.assertIsNone(res["tax_compliance_warning"])
        self.assertEqual(res["purity"], "24K")

    def test_buyback_calculator_section_269st_cash_warning(self):
        # 20g 24K gold bar with cash payout exceeding ₹2,00,000
        res = buyback_calculator.calculate_liquidation(
            delivered_cost=250000.0,
            weight_grams=20.0,
            purity="24K",
            item_type="bar",
            spot_override=15837.5,
            payment_mode="CASH"
        )
        self.assertIsNotNone(res["tax_compliance_warning"])
        self.assertIn("Section 269ST", res["tax_compliance_warning"])

    def test_buyback_calculator_22k_jewellery(self):
        # 8g 22K chain bought for ₹95,000
        res = buyback_calculator.calculate_liquidation(
            delivered_cost=95000.0,
            weight_grams=8.0,
            purity="22K",
            item_type="jewellery",
            spot_override=14438.8
        )
        self.assertEqual(res["assaying_deduction_pct"], 1.0)
        self.assertGreater(res["net_liquidation_payout"], 100000)
        self.assertTrue(res["arbitrage_viable"])

    def test_restock_sniper_lifecycle(self):
        sniper = RestockSniper(poll_interval_seconds=60)
        # Check initial watch items
        watch_list = sniper.get_watch_list()
        self.assertGreaterEqual(len(watch_list), 3)

        # Add custom SKU
        item = sniper.add_watch_sku(
            sku_id="test_sku_101",
            title="Kundan 5g 24K Bar",
            platform="Tata CLiQ",
            url="https://example.com/test-gold",
            weight_grams=5.0,
            purity="24K",
            target_price=70000.0
        )
        self.assertEqual(item["sku_id"], "test_sku_101")
        self.assertIn("test_sku_101", sniper.watch_list)

        # Status check
        status = sniper.get_status()
        self.assertIn("active_skus_monitored", status)
        self.assertGreaterEqual(status["active_skus_monitored"], 4)

        # Remove custom SKU
        removed = sniper.remove_watch_sku("test_sku_101")
        self.assertTrue(removed)
        self.assertNotIn("test_sku_101", sniper.watch_list)

    def test_whatsapp_service_formatting_and_simulation(self):
        deal = {
            "title": "5g MMTC-PAMP Lotus 24K Bar",
            "source": "Ajio",
            "weight_grams": 5.0,
            "purity": "24K",
            "effective_net_price": 68000.0,
            "effective_price_per_gram": 13600.0,
            "live_spot_rate_per_gram": 15837.5,
            "spread_per_gram": 2237.5,
            "total_stack_savings": 11187.5,
            "recommended_card": "Tata Neu Infinity",
            "url": "https://www.ajio.com/gold"
        }
        msg = whatsapp_service.format_text_alert(deal)
        self.assertIn("SUB-SPOT GOLD ARBITRAGE ALERT", msg)
        self.assertIn("MMTC-PAMP", msg)
        self.assertIn("Tata Neu Infinity", msg)

        # Simulated dispatch
        res = whatsapp_service.dispatch_alert("9876543210", deal)
        self.assertEqual(res["status"], "simulated")
        self.assertEqual(res["phone"], "919876543210")

    def test_api_buyback_endpoint(self):
        resp = self.client.get(
            "/api/v1/arbitrage/buyback-calculator",
            params={
                "delivered_cost": 124345.0,
                "weight": 10.0,
                "purity": "24K",
                "item_type": "bar",
                "payment_mode": "RTGS"
            }
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["arbitrage_viable"])
        self.assertIn("net_profit_inr", data)
        self.assertIn("annualized_roi_pct", data)

    def test_api_sniper_endpoints(self):
        # Status
        resp = self.client.get("/api/v1/sniper/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("active_skus_monitored", data)

        # WhatsApp test trigger
        resp_wa = self.client.post(
            "/api/v1/alerts/test-whatsapp",
            json={"phone": "+91 9988776655"}
        )
        self.assertEqual(resp_wa.status_code, 200)
        wa_data = resp_wa.json()
        self.assertEqual(wa_data["status"], "simulated")


if __name__ == "__main__":
    unittest.main()
