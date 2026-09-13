import math
from typing import Dict, Any, Optional
from datetime import datetime


class DealReceiptGenerator:
    """
    Generates high-converting viral receipts and social proof graphics
    for Twitter/X, Telegram, and marketing channels.
    """

    @staticmethod
    def generate_ascii_receipt(deal: Dict[str, Any], seconds_active: int = 260) -> str:
        title = deal.get("title", "10g 24K Gold Bar 999 Purity")[:40]
        platform = str(deal.get("source", deal.get("platform", "Tata CLiQ"))).upper()
        weight = float(deal.get("weight_grams", 1.0))
        purity = str(deal.get("purity", "24K")).upper()

        spot_rate = float(deal.get("live_spot_rate_per_gram", 15837.5))
        mrp = float(deal.get("selling_price", spot_rate * weight))
        coupon_disc = float(deal.get("coupon_discount", 0))
        bank_disc = float(deal.get("instant_card_savings", deal.get("bank_discount", 1500.0)))
        reward_val = float(deal.get("card_reward_value", 0))
        net_price = float(deal.get("effective_net_price", mrp - coupon_disc - bank_disc - reward_val))
        effective_ppg = float(deal.get("effective_price_per_gram", net_price / weight if weight else net_price))
        spread_ppg = float(deal.get("spread_per_gram", spot_rate - effective_ppg))
        total_savings = float(deal.get("total_stack_savings", (spot_rate * weight) - net_price))

        card_used = deal.get("recommended_card", "HDFC Infinia / Tata Neu Infinity")
        minutes = seconds_active // 60
        secs = seconds_active % 60

        receipt = f"""+-------------------------------------------------------------+
|                 GOLD DEAL FINDER - ARBITRAGE PROOF          |
|                   PLATFORM: {platform:<32}|
+-------------------------------------------------------------+
| ITEM: {weight}g {purity} {title:<36}|
| WHOLESALE IBJA SPOT RATE:                   Rs {spot_rate:>10,.1f}/g |
|                                                             |
| Listed Catalog MRP:                         Rs {mrp:>10,.2f} |
| Store Coupon Discount:                     -Rs {coupon_disc:>10,.2f} |
| Bank Instant Card Off:                     -Rs {bank_disc:>10,.2f} |
| Value of Reward Points Accrued:            -Rs {reward_val:>10,.2f} |
| ----------------------------------------------------------- |
| NET DELIVERED OUT-OF-POCKET:                Rs {net_price:>10,.2f} |
| EFFECTIVE RATE PER GRAM:                    Rs {effective_ppg:>10,.2f}/g |
| ARBITRAGE SPREAD BELOW SPOT:                Rs {spread_ppg:>10,.2f}/g |
| TOTAL ESTIMATED RISK-FREE PROFIT:           Rs {total_savings:>10,.2f} |
+-------------------------------------------------------------+
| BEST PAYMENT CARD: {card_used:<41}|
| STATUS: INVENTORY EXHAUSTED IN {minutes}m {secs:02d}s                       |
| Pro VIP alerted 14 minutes before public channel.           |
| Upgrade to Pro: http://localhost:8000/#pricing              |
+-------------------------------------------------------------+"""
        return receipt

    @staticmethod
    def generate_svg_receipt(deal: Dict[str, Any], seconds_active: int = 260) -> str:
        """Generates a crisp SVG image for web display and social cards"""
        title = deal.get("title", "10g 24K Gold Bar 999 Purity")[:36]
        platform = str(deal.get("source", deal.get("platform", "Tata CLiQ"))).upper()
        weight = float(deal.get("weight_grams", 1.0))
        purity = str(deal.get("purity", "24K")).upper()

        spot_rate = float(deal.get("live_spot_rate_per_gram", 15837.5))
        mrp = float(deal.get("selling_price", spot_rate * weight))
        net_price = float(deal.get("effective_net_price", mrp * 0.88))
        effective_ppg = float(deal.get("effective_price_per_gram", net_price / weight if weight else net_price))
        spread_ppg = float(deal.get("spread_per_gram", spot_rate - effective_ppg))
        total_savings = float(deal.get("total_stack_savings", (spot_rate * weight) - net_price))

        card_used = deal.get("recommended_card", "Tata Neu Infinity / HDFC")
        minutes = seconds_active // 60
        secs = seconds_active % 60

        svg = f"""<svg width="600" height="520" viewBox="0 0 600 520" xmlns="http://www.w3.org/2000/svg" style="background:#0f1115; font-family:'Plus Jakarta Sans',sans-serif;">
  <defs>
    <linearGradient id="goldGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#f59e0b"/>
      <stop offset="100%" stop-color="#d97706"/>
    </linearGradient>
    <linearGradient id="redGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#ef4444"/>
      <stop offset="100%" stop-color="#b91c1c"/>
    </linearGradient>
  </defs>

  <!-- Border Card -->
  <rect x="15" y="15" width="570" height="490" rx="16" fill="#181b20" stroke="#262b34" stroke-width="2"/>

  <!-- Header -->
  <rect x="15" y="15" width="570" height="65" rx="16" fill="#14171d"/>
  <text x="35" y="44" fill="#c5a059" font-size="12" font-weight="800" letter-spacing="2">GOLD DEAL FINDER • VERIFIED RECEIPT</text>
  <text x="35" y="64" fill="#9ca3af" font-size="14">Platform: <tspan fill="#f0f2f5" font-weight="700">{platform}</tspan></text>

  <!-- Deal Title -->
  <text x="35" y="115" fill="#ffffff" font-size="18" font-weight="800">{weight}g {purity} {title}</text>
  <text x="35" y="140" fill="#9ca3af" font-size="13">Benchmark Wholesale IBJA Spot: <tspan fill="#f59e0b" font-weight="700">₹{spot_rate:,.1f}/g</tspan></text>

  <!-- Financial Matrix -->
  <rect x="35" y="160" width="530" height="180" rx="10" fill="#14171d" stroke="#262b34"/>

  <text x="55" y="195" fill="#9ca3af" font-size="13">Listed Catalog Price:</text>
  <text x="545" y="195" fill="#9ca3af" font-size="13" text-anchor="end" text-decoration="line-through">₹{mrp:,.2f}</text>

  <text x="55" y="225" fill="#10b981" font-size="13">Stacked Card & Promo Off:</text>
  <text x="545" y="225" fill="#10b981" font-size="13" font-weight="700" text-anchor="end">-₹{total_savings:,.2f}</text>

  <line x1="55" y1="245" x2="545" y2="245" stroke="#262b34" stroke-dasharray="4"/>

  <text x="55" y="275" fill="#ffffff" font-size="15" font-weight="700">Effective Net Out-of-Pocket:</text>
  <text x="545" y="275" fill="#ffffff" font-size="20" font-weight="800" text-anchor="end">₹{net_price:,.2f}</text>

  <text x="55" y="305" fill="#ef4444" font-size="14" font-weight="800">Effective Rate per Gram:</text>
  <text x="545" y="305" fill="#ef4444" font-size="16" font-weight="800" text-anchor="end">₹{effective_ppg:,.2f}/g (₹{spread_ppg:,.1f}/g BELOW SPOT)</text>

  <text x="55" y="325" fill="#9ca3af" font-size="11">Optimal Card: {card_used}</text>

  <!-- Scarcity Badge -->
  <rect x="35" y="360" width="530" height="75" rx="10" fill="rgba(239, 68, 68, 0.1)" stroke="rgba(239, 68, 68, 0.3)"/>
  <text x="55" y="390" fill="#ef4444" font-size="13" font-weight="800">⏱️ EXHAUSTED IN {minutes}m {secs:02d}s</text>
  <text x="55" y="415" fill="#9ca3af" font-size="12">Pro VIP members were notified in 0.4s. Free channels received alert 15m later.</text>

  <!-- CTA Footer -->
  <rect x="35" y="450" width="530" height="40" rx="8" fill="url(#goldGrad)"/>
  <text x="300" y="475" fill="#ffffff" font-size="13" font-weight="800" text-anchor="middle">JOIN GOLD DEAL PRO (From ₹599/mo) • golddealfinder.in</text>
</svg>"""
        return svg

    @staticmethod
    def generate_tweet_text(deal: Dict[str, Any], seconds_active: int = 260) -> str:
        weight = float(deal.get("weight_grams", 1.0))
        purity = str(deal.get("purity", "24K")).upper()
        platform = deal.get("source", deal.get("platform", "Tata CLiQ"))
        spot = float(deal.get("live_spot_rate_per_gram", 15837.5))
        net_ppg = float(deal.get("effective_price_per_gram", 13400.0))
        spread = float(deal.get("spread_per_gram", spot - net_ppg))
        savings = float(deal.get("total_stack_savings", spread * weight))
        mins = seconds_active // 60

        text = f"""🚨 GOLD ARBITRAGE FLASH ALERT 🚨

Just bought {weight}g {purity} pure bullion on {platform} for ₹{net_ppg:,.0f}/g.
Wholesale IBJA Spot rate: ₹{spot:,.0f}/g

🔥 Net discount: ₹{spread:,.0f}/g BELOW SPOT!
💰 Total profit/savings: ₹{savings:,.0f}

Stock sold out in {mins} minutes.
Our Pro members scored with sub-second VIP alerts.

Stop buying gold at retail rates 👇
golddealfinder.in

#GoldPrice #SGB #CreditCard #Infinia #Arbitrage"""
        return text


receipt_generator = DealReceiptGenerator()
