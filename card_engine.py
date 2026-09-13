import re
from typing import Dict, List, Optional, Any
from pydantic import BaseModel


class BankOffer(BaseModel):
    id: str
    bank_code: str  # HDFC, ICICI, AXIS, SBI, AMEX, KOTAK, BOB, FEDERAL
    card_type: str  # CREDIT, DEBIT, ANY
    discount_percentage: float
    max_discount_inr: float
    min_transaction_inr: float
    is_instant: bool = True
    description: str = ""


class CardRewardProfile(BaseModel):
    card_id: str
    bank_code: str
    card_name: str
    jewellery_mcc_reward_pct: float
    point_value_inr: float  # Value of 1 point in INR
    milestone_bonus_value_inr: float = 0.0
    notes: str = ""


# Pre-configured popular card profiles in India
CARD_REGISTRY: Dict[str, CardRewardProfile] = {
    "HDFC_INFINIA": CardRewardProfile(
        card_id="HDFC_INFINIA",
        bank_code="HDFC",
        card_name="HDFC Bank Infinia Metal",
        jewellery_mcc_reward_pct=3.33,
        point_value_inr=1.0,
        notes="3.33% base points on jewellery MCC 5944 (1:1 on Flights/Hotels)"
    ),
    "HDFC_DCB": CardRewardProfile(
        card_id="HDFC_DCB",
        bank_code="HDFC",
        card_name="HDFC Diners Club Black",
        jewellery_mcc_reward_pct=3.33,
        point_value_inr=1.0,
        notes="3.33% reward rate redeemable for flights/hotels"
    ),
    "HDFC_REGALIA_GOLD": CardRewardProfile(
        card_id="HDFC_REGALIA_GOLD",
        bank_code="HDFC",
        card_name="HDFC Regalia Gold",
        jewellery_mcc_reward_pct=1.33,
        point_value_inr=0.5,
        notes="4 reward points per Rs 150 (approx 1.33% return)"
    ),
    "AXIS_ATLAS": CardRewardProfile(
        card_id="AXIS_ATLAS",
        bank_code="AXIS",
        card_name="Axis Bank Atlas",
        jewellery_mcc_reward_pct=2.00,
        point_value_inr=1.0,
        notes="2 EDGE Miles per Rs 100 on normal spends (1 EDGE Mile = 2 Partner Points / Rs 1)"
    ),
    "AMEX_PLATINUM_TRAVEL": CardRewardProfile(
        card_id="AMEX_PLATINUM_TRAVEL",
        bank_code="AMEX",
        card_name="American Express Platinum Travel",
        jewellery_mcc_reward_pct=1.00,
        point_value_inr=0.5,
        milestone_bonus_value_inr=24000.0,
        notes="Counts towards Rs 4 Lakh spend milestone unlocking 48,000 Marriott Bonvoy points"
    ),
    "TATA_NEU_INFINITY": CardRewardProfile(
        card_id="TATA_NEU_INFINITY",
        bank_code="HDFC",
        card_name="Tata Neu Infinity HDFC",
        jewellery_mcc_reward_pct=5.00,
        point_value_inr=1.0,
        notes="5% NeuCoins on Tata Neu / Tata CLiQ Luxury (1 NeuCoin = Rs 1)"
    ),
    "SBI_CASHBACK": CardRewardProfile(
        card_id="SBI_CASHBACK",
        bank_code="SBI",
        card_name="SBI Cashback Card",
        jewellery_mcc_reward_pct=1.00,
        point_value_inr=1.0,
        notes="1% base cashback (Jewellery MCC excluded from 5% online tier)"
    ),
    "ICICI_AMAZON_PAY": CardRewardProfile(
        card_id="ICICI_AMAZON_PAY",
        bank_code="ICICI",
        card_name="Amazon Pay ICICI Card",
        jewellery_mcc_reward_pct=2.00,
        point_value_inr=1.0,
        notes="2% unlimited cashback on Amazon Gold/Jewellery for Prime users"
    ),
    "STANDARD_CARD": CardRewardProfile(
        card_id="STANDARD_CARD",
        bank_code="ALL",
        card_name="Standard Bank Credit Card",
        jewellery_mcc_reward_pct=0.75,
        point_value_inr=0.25,
        notes="Standard retail reward points"
    )
}

# Standard Active Seasonal Bank Campaigns on Indian E-Commerce (Ajio, Myntra, Tata CLiQ)
DEFAULT_SEASONAL_BANK_OFFERS: List[BankOffer] = [
    BankOffer(
        id="hdfc_10_instant",
        bank_code="HDFC",
        card_type="CREDIT",
        discount_percentage=10.0,
        max_discount_inr=1500.0,
        min_transaction_inr=5000.0,
        description="10% Instant Discount on HDFC Bank Credit Cards up to Rs 1,500 on min spend of Rs 5,000"
    ),
    BankOffer(
        id="icici_10_instant",
        bank_code="ICICI",
        card_type="CREDIT",
        discount_percentage=10.0,
        max_discount_inr=2000.0,
        min_transaction_inr=6000.0,
        description="10% Instant Discount on ICICI Bank Credit Cards up to Rs 2,000 on min spend of Rs 6,000"
    ),
    BankOffer(
        id="axis_10_instant",
        bank_code="AXIS",
        card_type="CREDIT",
        discount_percentage=10.0,
        max_discount_inr=1750.0,
        min_transaction_inr=5000.0,
        description="10% Instant Discount on Axis Bank Credit Cards up to Rs 1,750 on min spend of Rs 5,000"
    ),
    BankOffer(
        id="sbi_10_instant",
        bank_code="SBI",
        card_type="CREDIT",
        discount_percentage=10.0,
        max_discount_inr=1500.0,
        min_transaction_inr=5000.0,
        description="10% Instant Discount on SBI Credit Cards up to Rs 1,500 on min spend of Rs 5,000"
    ),
    BankOffer(
        id="kotak_10_instant",
        bank_code="KOTAK",
        card_type="CREDIT",
        discount_percentage=10.0,
        max_discount_inr=1250.0,
        min_transaction_inr=4500.0,
        description="10% Instant Discount on Kotak Bank Cards up to Rs 1,250 on min spend of Rs 4,500"
    )
]


class CreditCardOfferParser:
    """
    Programmatic parser that extracts structured discount rules from
    unstructured promotional strings in e-commerce responses.
    """
    BANK_PATTERN = re.compile(r"\b(HDFC|ICICI|AXIS|SBI|KOTAK|BOB|FEDERAL|AMEX|INDUSIND|YES|HSBC)\b", re.IGNORECASE)
    PCT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:Instant\s+Discount|Off)", re.IGNORECASE)
    FLAT_PATTERN = re.compile(r"Flat\s*(?:Rs\.?|₹)?\s*([\d,]+)\s*Off", re.IGNORECASE)
    MAX_DISC_PATTERN = re.compile(r"(?:up\s*to|max(?:imum)?(?:\s*discount)?)\s*(?:Rs\.?|₹)?\s*([\d,]+)", re.IGNORECASE)
    MIN_SPEND_PATTERNS = [
        re.compile(r"(?:min(?:imum)?(?:\s*spend|\s*purchase|\s*order)?|orders?\s*above|spends?\s*above)\s*(?:of)?\s*(?:Rs\.?|₹)?\s*([\d,]+)", re.IGNORECASE),
        re.compile(r"(?:on|for\s*orders?\s*of)?\s*(?:Rs\.?|₹)?\s*([\d,]+)\s*(?:and\s*above|\+)", re.IGNORECASE)
    ]
    CARD_TYPE_PATTERN = re.compile(r"\b(Credit|Debit)\b", re.IGNORECASE)

    @classmethod
    def parse_string(cls, promo_text: str) -> Optional[BankOffer]:
        if not promo_text:
            return None

        bank_match = cls.BANK_PATTERN.search(promo_text)
        if not bank_match:
            return None

        bank = bank_match.group(1).upper()
        card_type_match = cls.CARD_TYPE_PATTERN.search(promo_text)
        card_type = card_type_match.group(1).upper() if card_type_match else "CREDIT"

        # Check for min spend
        min_spend = 0.0
        for pat in cls.MIN_SPEND_PATTERNS:
            min_match = pat.search(promo_text)
            if min_match:
                try:
                    min_spend = float(min_match.group(1).replace(",", ""))
                    break
                except ValueError:
                    continue

        # Check for flat discount
        flat_match = cls.FLAT_PATTERN.search(promo_text)
        if flat_match:
            try:
                flat_val = float(flat_match.group(1).replace(",", ""))
                return BankOffer(
                    id=f"{bank.lower()}_flat_{int(flat_val)}",
                    bank_code=bank,
                    card_type=card_type,
                    discount_percentage=0.0,
                    max_discount_inr=flat_val,
                    min_transaction_inr=min_spend,
                    is_instant=True,
                    description=promo_text
                )
            except ValueError:
                pass

        # Check for percentage discount
        pct_match = cls.PCT_PATTERN.search(promo_text)
        if pct_match:
            try:
                pct_val = float(pct_match.group(1))
                max_disc = 1500.0
                max_match = cls.MAX_DISC_PATTERN.search(promo_text)
                if max_match:
                    max_disc = float(max_match.group(1).replace(",", ""))

                return BankOffer(
                    id=f"{bank.lower()}_{int(pct_val)}_instant",
                    bank_code=bank,
                    card_type=card_type,
                    discount_percentage=pct_val,
                    max_discount_inr=max_disc,
                    min_transaction_inr=min_spend,
                    is_instant=True,
                    description=promo_text
                )
            except ValueError:
                pass

        return None


class CardRewardStacker:
    """
    Evaluates stacked combinations of Seller Coupon + Instant Bank Discount + Card Reward Points.
    """

    @staticmethod
    def calculate_stack(
        selling_price: float,
        weight_grams: float,
        spot_price_per_gram: float,
        coupon_discount: float = 0.0,
        coupon_code: str = "",
        user_card_ids: Optional[List[str]] = None,
        available_offers: Optional[List[BankOffer]] = None
    ) -> Dict[str, Any]:
        """
        Calculates net delivered out-of-pocket cost and highlights the best card to use.
        """
        offers = available_offers if available_offers is not None else DEFAULT_SEASONAL_BANK_OFFERS
        price_after_coupon = max(0.0, selling_price - coupon_discount)

        # Candidates to evaluate
        card_keys = user_card_ids if (user_card_ids and len(user_card_ids) > 0) else list(CARD_REGISTRY.keys())
        best_scenario = None
        lowest_net_cost = float("inf")

        for c_id in card_keys:
            profile = CARD_REGISTRY.get(c_id, CARD_REGISTRY["STANDARD_CARD"])
            bank_code = profile.bank_code

            # Find matching bank instant discount
            best_bank_disc = 0.0
            matched_offer_desc = "No instant discount applicable"

            for off in offers:
                if off.bank_code == bank_code or off.bank_code == "ALL":
                    if price_after_coupon >= off.min_transaction_inr:
                        if off.discount_percentage > 0:
                            calc_disc = price_after_coupon * (off.discount_percentage / 100.0)
                            disc = min(calc_disc, off.max_discount_inr)
                        else:
                            disc = off.max_discount_inr

                        if disc > best_bank_disc:
                            best_bank_disc = disc
                            matched_offer_desc = off.description

            # Net payment after instant discount
            out_of_pocket = price_after_coupon - best_bank_disc

            # Reward points value accrued on out_of_pocket spend
            reward_value_inr = (out_of_pocket * (profile.jewellery_mcc_reward_pct / 100.0)) * profile.point_value_inr

            # Total financial cost to user
            effective_total_cost = out_of_pocket - reward_value_inr
            effective_rate_per_gram = effective_total_cost / weight_grams if weight_grams > 0 else effective_total_cost

            scenario = {
                "card_id": profile.card_id,
                "card_name": profile.card_name,
                "bank_code": profile.bank_code,
                "catalog_price": round(selling_price, 2),
                "coupon_code": coupon_code,
                "coupon_discount": round(coupon_discount, 2),
                "price_after_coupon": round(price_after_coupon, 2),
                "bank_instant_discount": round(best_bank_disc, 2),
                "bank_offer_description": matched_offer_desc,
                "out_of_pocket_payment": round(out_of_pocket, 2),
                "reward_points_value_inr": round(reward_value_inr, 2),
                "effective_net_cost": round(effective_total_cost, 2),
                "effective_price_per_gram": round(effective_rate_per_gram, 2),
                "total_savings_inr": round(selling_price - effective_total_cost, 2),
                "total_discount_pct": round(((selling_price - effective_total_cost) / selling_price) * 100, 2) if selling_price > 0 else 0.0,
                "spot_price_per_gram": round(spot_price_per_gram, 2),
                "sub_spot_spread_per_gram": round(spot_price_per_gram - effective_rate_per_gram, 2),
                "is_sub_spot": (effective_rate_per_gram < spot_price_per_gram)
            }

            if effective_total_cost < lowest_net_cost:
                lowest_net_cost = effective_total_cost
                best_scenario = scenario

        return best_scenario or {}


card_parser = CreditCardOfferParser()
card_stacker = CardRewardStacker()
