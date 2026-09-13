from typing import List, Dict, Optional, Any
from price_calculator import GoldPriceCalculator
from card_engine import card_stacker, card_parser
from config import SUB_SPOT_MIN_DISCOUNT_PCT, LOW_MAKING_CHARGE_THRESHOLD_PCT
from database import db_manager
import logging

logger = logging.getLogger(__name__)


class ArbitrageEngine:
    def __init__(self):
        self.price_calculator = GoldPriceCalculator()

    def get_live_spot_rates(self) -> Dict[str, float]:
        """Fetch current landed spot rates per gram for 24K and 22K"""
        try:
            rates = self.price_calculator.get_live_gold_price()
            gold_rates = rates.get("gold", {}).get("per_gram", {})
            r999 = float(gold_rates.get("999_spot", 0))
            r22k = float(gold_rates.get("22k_spot", 0))
            if r999 > 1000:
                return {"24K": r999, "22K": r22k or (r999 * 0.9167), "18K": r999 * 0.75}
        except Exception as e:
            logger.warning(f"Failed to fetch live rates for arbitrage: {e}")
        return {"24K": 15800.0, "22K": 14400.0, "18K": 11800.0}

    def evaluate_product_arbitrage(
        self,
        product: Dict[str, Any],
        spot_rates: Dict[str, float],
        user_card_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Calculates stacked net cost, sub-spot spread, making charge %,
        and classifies arbitrage opportunity type.
        """
        selling_price = float(product.get("selling_price", 0))
        weight_grams = float(product.get("weight_grams", 1.0))
        purity = str(product.get("purity", "24K")).upper()
        is_jewellery = bool(product.get("is_jewellery", False))

        # Benchmark spot rate
        spot_rate = spot_rates.get(purity, spot_rates.get("24K", 7400.0))

        # Extract or assume coupon discount
        coupon_disc = float(product.get("coupon_discount", 0))
        if coupon_disc == 0 and selling_price > 3000:
            # Check if discount_percent implies coupon on platform
            raw_disc_pct = float(product.get("discount_percent", 0))
            if raw_disc_pct > 3.0:
                coupon_disc = round(selling_price * (raw_disc_pct / 100.0) * 0.3, 2)

        # Run card stacker
        stack = card_stacker.calculate_stack(
            selling_price=selling_price,
            weight_grams=weight_grams,
            spot_price_per_gram=spot_rate,
            coupon_discount=coupon_disc,
            coupon_code=product.get("coupon_code", "AUTO_PROMO"),
            user_card_ids=user_card_ids
        )

        effective_net_price = stack.get("effective_net_cost", selling_price)
        effective_price_per_gram = stack.get("effective_price_per_gram", (selling_price / weight_grams if weight_grams else selling_price))

        # Spread vs spot
        spread_inr = round((spot_rate * weight_grams) - effective_net_price, 2)
        spread_per_gram = round(spot_rate - effective_price_per_gram, 2)
        spread_pct = round(((spot_rate - effective_price_per_gram) / spot_rate) * 100, 2)

        # Making charge analysis for jewellery
        pure_metal_value = round(spot_rate * weight_grams, 2)
        calculated_making_charge_inr = max(0.0, (selling_price / 1.03) - pure_metal_value)
        effective_making_charge_pct = round((calculated_making_charge_inr / pure_metal_value) * 100, 2) if pure_metal_value > 0 else 0.0

        # Classification
        is_sub_spot = spread_per_gram > (spot_rate * (SUB_SPOT_MIN_DISCOUNT_PCT / 100.0))
        is_low_making = is_jewellery and (effective_making_charge_pct <= LOW_MAKING_CHARGE_THRESHOLD_PCT)

        deal_type = "STANDARD"
        if is_sub_spot and not is_jewellery:
            deal_type = "SUB_SPOT_BULLION"
        elif is_low_making:
            deal_type = "MAKING_CHARGE_GLITCH"
        elif stack.get("total_discount_pct", 0) >= 8.0:
            deal_type = "HIGH_STACK_DEAL"

        enriched_deal = dict(product)
        enriched_deal.update({
            "effective_net_price": effective_net_price,
            "effective_price_per_gram": effective_price_per_gram,
            "live_spot_rate_per_gram": spot_rate,
            "arbitrage_spread_inr": spread_inr,
            "spread_per_gram": spread_per_gram,
            "discount_vs_spot_pct": spread_pct,
            "is_sub_spot": is_sub_spot,
            "is_low_making": is_low_making,
            "deal_type": deal_type,
            "effective_making_charge_pct": effective_making_charge_pct,
            "recommended_card": stack.get("card_name", "Standard Card"),
            "best_bank_offer": stack.get("bank_offer_description", ""),
            "instant_card_savings": stack.get("bank_instant_discount", 0),
            "card_reward_value": stack.get("reward_points_value_inr", 0),
            "total_stack_savings": stack.get("total_savings_inr", 0),
            "total_stack_discount_pct": stack.get("total_discount_pct", 0)
        })
        return enriched_deal

    def process_catalog_arbitrage(
        self,
        products: List[Dict[str, Any]],
        user_card_ids: Optional[List[str]] = None,
        save_to_db: bool = True
    ) -> Dict[str, Any]:
        """
        Processes a full batch of scanned products, extracts sub-spot and low-making charge deals,
        and logs to the database.
        """
        spot_rates = self.get_live_spot_rates()
        evaluated_deals = []
        sub_spot_deals = []
        low_making_deals = []

        for p in products:
            deal = self.evaluate_product_arbitrage(p, spot_rates, user_card_ids)
            evaluated_deals.append(deal)

            if deal["is_sub_spot"]:
                sub_spot_deals.append(deal)
            elif deal["is_low_making"]:
                low_making_deals.append(deal)

        # Sort by best arbitrage spread
        sub_spot_deals.sort(key=lambda x: x["spread_per_gram"], reverse=True)
        low_making_deals.sort(key=lambda x: x["effective_making_charge_pct"])

        if save_to_db and sub_spot_deals:
            try:
                db_manager.save_deal_scans(sub_spot_deals)
            except Exception as e:
                logger.error(f"Error saving sub-spot deals to DB: {e}")

        total_potential_profit = sum(d["arbitrage_spread_inr"] for d in sub_spot_deals)

        return {
            "spot_rates": spot_rates,
            "total_scanned": len(products),
            "sub_spot_count": len(sub_spot_deals),
            "low_making_count": len(low_making_deals),
            "total_potential_arbitrage_inr": round(total_potential_profit, 2),
            "sub_spot_deals": sub_spot_deals,
            "low_making_deals": low_making_deals,
            "all_evaluated": evaluated_deals
        }


arbitrage_engine = ArbitrageEngine()
