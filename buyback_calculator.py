"""
Reverse Arbitrage & Physical Bullion Liquidation Engine.
Calculates net risk-free profit when liquidating gold bought online at sub-spot
to offline physical bullion merchants, refineries, and RTGS desks across India.
"""

import logging
from typing import Dict, Any, Optional
from config import (
    BUYBACK_MELT_DEDUCTION_24K,
    BUYBACK_MELT_DEDUCTION_22K,
    BUYBACK_CASH_LIMIT_INR,
    DEFAULT_TURNOVER_DAYS,
    PURITY_MAPPING
)
from price_calculator import price_calculator

logger = logging.getLogger(__name__)


class BuybackCalculator:
    """
    Computes real-world physical liquidation payouts across Indian bullion hubs:
    Zaveri Bazaar (Mumbai), Manek Chowk (Ahmedabad), Bowbazar (Kolkata), Sowcarpet (Chennai),
    and national gold exchange desks (Muthoot Gold Point, MMTC-PAMP, MMTC).
    """

    def __init__(self):
        self.default_deduction_24k = BUYBACK_MELT_DEDUCTION_24K * 100  # 0.5%
        self.default_deduction_22k = BUYBACK_MELT_DEDUCTION_22K * 100  # 1.0%

    def get_live_rates(self) -> Dict[str, float]:
        """Fetches live IBJA wholesale benchmark rates for 24K, 22K, and 18K."""
        rate_24k = 15837.5
        rate_22k = rate_24k * (22.0 / 24.0)
        rate_18k = rate_24k * (18.0 / 24.0)
        try:
            live_data = price_calculator.get_live_gold_price()
            gold_rates = live_data.get("gold", {}).get("per_gram", {})
            r999 = float(gold_rates.get("999_spot", 0) or live_data.get("rate_24k", 0) or live_data.get("spot_price_per_gram", 0))
            if r999 > 1000:
                rate_24k = r999
                rate_22k = float(gold_rates.get("22k_spot", 0) or (r999 * (22.0 / 24.0)))
                rate_18k = rate_24k * (18.0 / 24.0)
        except Exception as e:
            logger.warning(f"Error fetching live spot rate for buyback: {e}")

        return {
            "24K": round(rate_24k, 2),
            "22K": round(rate_22k, 2),
            "18K": round(rate_18k, 2)
        }

    def calculate_liquidation(
        self,
        delivered_cost: float,
        weight_grams: float,
        purity: str = "24K",
        item_type: str = "coin",  # 'bar', 'coin', or 'jewellery'
        spot_override: Optional[float] = None,
        custom_deduction_pct: Optional[float] = None,
        turnover_days: int = DEFAULT_TURNOVER_DAYS,
        payment_mode: str = "RTGS"  # 'RTGS' or 'CASH'
    ) -> Dict[str, Any]:
        """
        Calculates exact net cash/RTGS payout and ROI for sub-spot bullion arbitrage.
        """
        if weight_grams <= 0 or delivered_cost <= 0:
            return {"error": "Invalid weight or cost parameters"}

        # Normalize purity
        norm_purity = purity.upper().strip()
        if norm_purity not in ["24K", "22K", "18K"]:
            if "24" in norm_purity or "999" in norm_purity:
                norm_purity = "24K"
            elif "22" in norm_purity or "916" in norm_purity:
                norm_purity = "22K"
            elif "18" in norm_purity or "750" in norm_purity:
                norm_purity = "18K"
            else:
                norm_purity = "24K"

        # Determine benchmark buyback spot rate
        live_rates = self.get_live_rates()
        benchmark_spot = spot_override if spot_override else live_rates.get(norm_purity, live_rates["24K"])

        # Determine melting / assaying deduction percentage
        if custom_deduction_pct is not None:
            deduction_pct = custom_deduction_pct
        else:
            if norm_purity == "24K":
                # Certified mint blister packaging (bars/coins) has lowest deduction
                deduction_pct = 0.25 if item_type in ["bar", "coin"] else self.default_deduction_24k
            elif norm_purity == "22K":
                deduction_pct = self.default_deduction_22k
            else:
                deduction_pct = 1.5

        # Payout math
        gross_value = round(weight_grams * benchmark_spot, 2)
        deduction_amount = round(gross_value * (deduction_pct / 100.0), 2)
        net_payout = round(gross_value - deduction_amount, 2)

        # Profit & Return metrics
        net_profit_inr = round(net_payout - delivered_cost, 2)
        effective_cost_per_gram = round(delivered_cost / weight_grams, 2)
        net_payout_per_gram = round(net_payout / weight_grams, 2)
        margin_per_gram = round(net_payout_per_gram - effective_cost_per_gram, 2)

        roi_pct = round((net_profit_inr / delivered_cost) * 100.0, 2)
        cycle_days = max(1, turnover_days)
        annualized_roi_pct = round(roi_pct * (365.0 / cycle_days), 2) if roi_pct > 0 else round(roi_pct, 2)

        is_viable = net_profit_inr > 0

        # Compliance & Recommended Desk
        tax_compliance_warning = None
        if payment_mode.upper() == "CASH" and net_payout > BUYBACK_CASH_LIMIT_INR:
            tax_compliance_warning = (
                f"Section 269ST Alert: Cash payout of ₹{net_payout:,.2f} exceeds statutory ₹{BUYBACK_CASH_LIMIT_INR:,.2f} limit. "
                f"Must liquidate via RTGS/NEFT direct bank settlement."
            )

        channels = [
            {
                "channel_name": "Zaveri Bazaar / Bullion Association RTGS Desk",
                "spread_note": "Lowest spread (-0.25% to -0.5% from spot for 999 certified bars)",
                "payout_time": "Instant RTGS / Same-day NEFT"
            },
            {
                "channel_name": "Muthoot Gold Point / Organised Bullion Desks",
                "spread_note": "Free ultrasonic cleaning & German XRF karat testing on-the-spot",
                "payout_time": "Instant Bank Transfer (< 15 mins)"
            },
            {
                "channel_name": "Local BIS Hallmarked Jeweller",
                "spread_note": "Standard 1% melting deduction for 916 jewellery or exchange against new bullion",
                "payout_time": "Immediate"
            }
        ]

        return {
            "purity": norm_purity,
            "weight_grams": weight_grams,
            "item_type": item_type,
            "delivered_cost": round(delivered_cost, 2),
            "effective_cost_per_gram": effective_cost_per_gram,
            "benchmark_spot_per_gram": round(benchmark_spot, 2),
            "gross_liquidation_value": gross_value,
            "assaying_deduction_pct": deduction_pct,
            "assaying_deduction_amount": deduction_amount,
            "net_liquidation_payout": net_payout,
            "net_payout_per_gram": net_payout_per_gram,
            "margin_per_gram": margin_per_gram,
            "net_profit_inr": net_profit_inr,
            "roi_pct": roi_pct,
            "annualized_roi_pct": annualized_roi_pct,
            "arbitrage_viable": is_viable,
            "turnover_days": cycle_days,
            "payment_mode": payment_mode.upper(),
            "tax_compliance_warning": tax_compliance_warning,
            "recommended_channels": channels
        }

    def evaluate_deal(self, deal: Dict[str, Any], custom_card: Optional[str] = None) -> Dict[str, Any]:
        """
        Takes any scraped or stacked deal dictionary and evaluates offline liquidation profit.
        """
        weight = float(deal.get("weight_grams", 1.0) or 1.0)
        purity = deal.get("purity", "24K")
        effective_price = float(deal.get("effective_net_price", deal.get("selling_price", 0)) or 0)
        title = deal.get("title", "").lower()

        item_type = "jewellery" if any(w in title for w in ["chain", "ring", "necklace", "bangle", "earring"]) else "coin"
        if "bar" in title:
            item_type = "bar"

        liquidation = self.calculate_liquidation(
            delivered_cost=effective_price,
            weight_grams=weight,
            purity=purity,
            item_type=item_type
        )

        return {
            "product_id": deal.get("id"),
            "title": deal.get("title"),
            "url": deal.get("url"),
            "platform": deal.get("source", deal.get("platform")),
            "buyback_evaluation": liquidation
        }


buyback_calculator = BuybackCalculator()
