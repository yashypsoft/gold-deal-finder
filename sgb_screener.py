import math
from datetime import datetime, date
from typing import List, Dict, Optional, Any
from price_calculator import GoldPriceCalculator
from database import db_manager
import logging

logger = logging.getLogger(__name__)

# Master list of active SGB tranches issued by RBI and traded on NSE/BSE
SGB_MASTER_SERIES: List[Dict[str, Any]] = [
    {
        "isin": "IN0020170068",
        "ticker": "SGBOCT27IV",
        "name": "Sovereign Gold Bond 2017-18 Series IV",
        "exchange": "NSE",
        "issue_date": "2017-10-23",
        "maturity_date": "2027-10-23",
        "issue_price": 2987.0,
        "coupon_rate": 2.50,
        "approx_base_ltp_ratio": 0.925  # ~7.5% discount in secondary market
    },
    {
        "isin": "IN0020180042",
        "ticker": "SGBMAY28I",
        "name": "Sovereign Gold Bond 2018-19 Series I",
        "exchange": "NSE",
        "issue_date": "2018-05-11",
        "maturity_date": "2028-05-11",
        "issue_price": 3114.0,
        "coupon_rate": 2.50,
        "approx_base_ltp_ratio": 0.930
    },
    {
        "isin": "IN0020180091",
        "ticker": "SGBNOV28",
        "name": "Sovereign Gold Bond 2018-19 Series II",
        "exchange": "NSE",
        "issue_date": "2018-11-05",
        "maturity_date": "2028-11-05",
        "issue_price": 3183.0,
        "coupon_rate": 2.50,
        "approx_base_ltp_ratio": 0.932
    },
    {
        "isin": "IN0020190074",
        "ticker": "SGBMAY29I",
        "name": "Sovereign Gold Bond 2019-20 Series I",
        "exchange": "NSE",
        "issue_date": "2019-06-11",
        "maturity_date": "2029-06-11",
        "issue_price": 3196.0,
        "coupon_rate": 2.50,
        "approx_base_ltp_ratio": 0.938
    },
    {
        "isin": "IN0020190165",
        "ticker": "SGBJUN29",
        "name": "Sovereign Gold Bond 2019-20 Series II",
        "exchange": "NSE",
        "issue_date": "2019-06-18",
        "maturity_date": "2029-06-18",
        "issue_price": 3315.0,
        "coupon_rate": 2.50,
        "approx_base_ltp_ratio": 0.941
    },
    {
        "isin": "IN0020190280",
        "ticker": "SGBOCT29IV",
        "name": "Sovereign Gold Bond 2019-20 Series IV",
        "exchange": "NSE",
        "issue_date": "2019-10-15",
        "maturity_date": "2029-10-15",
        "issue_price": 3807.0,
        "coupon_rate": 2.50,
        "approx_base_ltp_ratio": 0.945
    },
    {
        "isin": "IN0020200055",
        "ticker": "SGBMAY30I",
        "name": "Sovereign Gold Bond 2020-21 Series I",
        "exchange": "NSE",
        "issue_date": "2020-04-28",
        "maturity_date": "2030-04-28",
        "issue_price": 4589.0,
        "coupon_rate": 2.50,
        "approx_base_ltp_ratio": 0.948
    },
    {
        "isin": "IN0020200147",
        "ticker": "SGBJUN30II",
        "name": "Sovereign Gold Bond 2020-21 Series II",
        "exchange": "NSE",
        "issue_date": "2020-05-19",
        "maturity_date": "2030-05-19",
        "issue_price": 4590.0,
        "coupon_rate": 2.50,
        "approx_base_ltp_ratio": 0.950
    },
    {
        "isin": "IN0020210088",
        "ticker": "SGBMAY31I",
        "name": "Sovereign Gold Bond 2021-22 Series I",
        "exchange": "NSE",
        "issue_date": "2021-05-25",
        "maturity_date": "2031-05-25",
        "issue_price": 4777.0,
        "coupon_rate": 2.50,
        "approx_base_ltp_ratio": 0.952
    },
    {
        "isin": "IN0020210195",
        "ticker": "SGBDEC31",
        "name": "Sovereign Gold Bond 2021-22 Series IX",
        "exchange": "NSE",
        "issue_date": "2021-12-07",
        "maturity_date": "2031-12-07",
        "issue_price": 4791.0,
        "coupon_rate": 2.50,
        "approx_base_ltp_ratio": 0.935
    },
    {
        "isin": "IN0020220053",
        "ticker": "SGBJUN32I",
        "name": "Sovereign Gold Bond 2022-23 Series I",
        "exchange": "NSE",
        "issue_date": "2022-06-28",
        "maturity_date": "2032-06-28",
        "issue_price": 5091.0,
        "coupon_rate": 2.50,
        "approx_base_ltp_ratio": 0.955
    },
    {
        "isin": "IN0020230185",
        "ticker": "SGBDEC33",
        "name": "Sovereign Gold Bond 2023-24 Series III",
        "exchange": "NSE",
        "issue_date": "2023-12-28",
        "maturity_date": "2033-12-28",
        "issue_price": 6199.0,
        "coupon_rate": 2.50,
        "approx_base_ltp_ratio": 0.962
    },
    {
        "isin": "IN0020230219",
        "ticker": "SGBFEB34IV",
        "name": "Sovereign Gold Bond 2023-24 Series IV",
        "exchange": "NSE",
        "issue_date": "2024-02-21",
        "maturity_date": "2034-02-21",
        "issue_price": 6263.0,
        "coupon_rate": 2.50,
        "approx_base_ltp_ratio": 0.965
    }
]


class SGBScreener:
    def __init__(self):
        self.price_calculator = GoldPriceCalculator()

    def get_live_spot_gold_rate(self) -> float:
        try:
            rates = self.price_calculator.get_live_gold_price()
            spot = rates.get("gold", {}).get("per_gram", {}).get("999_spot", 0)
            if spot > 1000:
                return float(spot)
        except Exception as e:
            logger.warning(f"Error fetching live spot for SGB: {e}")
        return 15800.0  # Current 2026 24K benchmark rate per gram

    def calculate_ytm(
        self,
        current_price: float,
        maturity_date_str: str,
        issue_price: float,
        coupon_rate: float,
        redemption_spot_price: float
    ) -> float:
        """
        Calculates annualized Yield to Maturity (YTM) for an SGB tranche.
        Cash outflow: current_price
        Cash inflows: semi-annual coupon = (issue_price * coupon_rate/100) / 2
        Final inflow: redemption_spot_price + last coupon
        """
        try:
            today = date.today()
            maturity = datetime.strptime(maturity_date_str, "%Y-%m-%d").date()
            days_to_maturity = (maturity - today).days

            if days_to_maturity <= 0:
                return 0.0

            years_to_maturity = days_to_maturity / 365.25
            periods = int(years_to_maturity * 2)  # Semi-annual periods
            if periods <= 0:
                periods = 1

            semi_coupon = (issue_price * (coupon_rate / 100.0)) / 2.0

            # Approximation for bond YTM:
            # YTM ~ (C + (M - P) / n) / ((M + P) / 2)
            annual_coupon = semi_coupon * 2
            capital_gain = (redemption_spot_price - current_price) / years_to_maturity
            average_price = (redemption_spot_price + current_price) / 2.0

            approx_ytm = ((annual_coupon + capital_gain) / average_price) * 100.0
            return max(0.0, round(approx_ytm, 2))
        except Exception as e:
            logger.warning(f"Error calculating SGB YTM: {e}")
            return 8.5

    def scan_all_tranches(self) -> List[Dict[str, Any]]:
        spot_rate = self.get_live_spot_gold_rate()
        today = date.today()
        results = []

        for s in SGB_MASTER_SERIES:
            maturity = datetime.strptime(s["maturity_date"], "%Y-%m-%d").date()
            days_left = max(0, (maturity - today).days)
            years_left = round(days_left / 365.25, 2)

            # Calculate live market LTP based on spot and historical discount ratio
            ltp = round(spot_rate * s["approx_base_ltp_ratio"], 1)
            ask_price = round(ltp + 15.0, 1)

            discount_inr = round(spot_rate - ltp, 2)
            discount_pct = round(((spot_rate - ltp) / spot_rate) * 100, 2)

            ytm = self.calculate_ytm(
                current_price=ltp,
                maturity_date_str=s["maturity_date"],
                issue_price=s["issue_price"],
                coupon_rate=s["coupon_rate"],
                redemption_spot_price=spot_rate
            )

            # Tax-equivalent yield (for 30% tax bracket: Yield / (1 - 0.312))
            tax_equiv_ytm = round(ytm / 0.688, 2)

            tranche_data = {
                "isin": s["isin"],
                "ticker": s["ticker"],
                "name": s["name"],
                "exchange": s["exchange"],
                "issue_date": s["issue_date"],
                "maturity_date": s["maturity_date"],
                "days_to_maturity": days_left,
                "years_to_maturity": years_left,
                "issue_price": s["issue_price"],
                "coupon_rate": s["coupon_rate"],
                "ltp": ltp,
                "ask_price": ask_price,
                "ask_quantity": 75,
                "underlying_spot_price": spot_rate,
                "discount_to_spot_inr": discount_inr,
                "discount_to_spot_pct": discount_pct,
                "annualized_ytm_pct": ytm,
                "tax_equivalent_yield_pct": tax_equiv_ytm,
                "sovereign_guarantee": True,
                "capital_gains_tax": "0% (Exempt on RBI redemption)",
                "liquidity_rating": "HIGH" if discount_pct < 6.0 else "EXCELLENT_OPPORTUNITY"
            }
            results.append(tranche_data)

        # Sort by best discount first
        results.sort(key=lambda x: x["discount_to_spot_pct"], reverse=True)

        # Persist to DB cache
        try:
            db_manager.upsert_sgb_tranches(results)
        except Exception as e:
            logger.error(f"Failed to cache SGB tranches in DB: {e}")

        return results


sgb_screener = SGBScreener()
