import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_VIP_CHAT_ID,
    TELEGRAM_FREE_CHAT_ID,
    FREE_TIER_DELAY_SECONDS
)
from whatsapp_service import whatsapp_service
import logging

logger = logging.getLogger(__name__)


class VIPAlertDispatcher:
    def __init__(self):
        self.bot = None
        if TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN != 'YOUR_BOT_TOKEN':
            try:
                self.bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
            except Exception as e:
                logger.warning(f"Failed to initialize Telegram bot: {e}")

    def format_pro_alert(self, deal: Dict[str, Any]) -> str:
        """Unredacted, actionable VIP alert with exact coupon and direct checkout math"""
        is_sub_spot = deal.get("is_sub_spot", False)
        emoji_header = "🚨🔥 <b>SUB-SPOT ARBITRAGE ALERT!</b> 🔥🚨" if is_sub_spot else "💎 <b>PRO ARBITRAGE DEAL</b> 💎"

        title = deal.get("title", "")[:75]
        source = deal.get("source", deal.get("platform", "Online"))
        brand = deal.get("brand", "Hallmarked")
        weight = deal.get("weight_grams", 1.0)
        purity = deal.get("purity", "24K")

        catalog_price = deal.get("selling_price", 0.0)
        net_price = deal.get("effective_net_price", catalog_price)
        price_per_g = deal.get("effective_price_per_gram", 0.0)
        spot_rate = deal.get("live_spot_rate_per_gram", 15837.5)
        spread_g = deal.get("spread_per_gram", 0.0)
        total_savings = deal.get("total_stack_savings", 0.0)

        card_name = deal.get("recommended_card", "Standard Credit Card")
        bank_offer = deal.get("best_bank_offer", "10% Instant Card Discount")
        coupon = deal.get("coupon_code", "AUTO_PROMO")

        message = f"""{emoji_header}

🪙 <b>{source} • {brand}</b>
📦 <b>Item:</b> {title}...
⚖️ <b>Weight:</b> {weight}g | <b>Purity:</b> {purity}

💰 <b>Listed MRP:</b> ₹{catalog_price:,.2f}
🎟️ <b>Coupon Code:</b> <code>{coupon}</code>
💳 <b>Best Card:</b> {card_name}
⚡ <b>Bank Offer:</b> {bank_offer}
──────────────────────────
🎯 <b>NET EFFECTIVE COST:</b> <b>₹{net_price:,.2f}</b>
💎 <b>Net Rate:</b> <b>₹{price_per_g:,.2f}/g</b>
🏪 <b>Market Spot Rate:</b> ₹{spot_rate:,.2f}/g
🚀 <b>ARBITRAGE SPREAD:</b> <b>₹{spread_g:,.2f}/g BELOW SPOT!</b>
💵 <b>YOUR NET PROFIT/SAVINGS:</b> <b>₹{total_savings:,.2f}</b>
──────────────────────────
⚡ <i>Sub-second alert delivered to Pro VIP members.</i>
"""
        return message

    def format_free_teaser(self, deal: Dict[str, Any]) -> str:
        """FOMO-inducing blurred teaser for free tier users"""
        weight = deal.get("weight_grams", 1.0)
        purity = deal.get("purity", "24K")
        spot_rate = deal.get("live_spot_rate_per_gram", 15837.5)
        spread_g = deal.get("spread_per_gram", 0.0)
        total_savings = deal.get("total_stack_savings", 0.0)

        message = f"""🔒 <b>[PRO ARBITRAGE OPPORTUNITY DETECTED]</b> 🔒

🪙 <b>Item:</b> {weight}g {purity} Pure Gold Bar / Coin
🏬 <b>Store:</b> [LOCKED - PRO ONLY]
🏷️ <b>Brand:</b> [LOCKED - PRO ONLY]

🏪 <b>Market Spot Rate:</b> ₹{spot_rate:,.2f}/g
🔥 <b>Arbitrage Spread:</b> <b>₹{spread_g:,.2f}/gram BELOW WHOLESALE SPOT!</b>
💰 <b>Net Savings On This Deal:</b> <b>₹{total_savings:,.2f}</b>
💳 <b>Stacking Strategy:</b> [LOCKED - PRO ONLY]
🎟️ <b>Secret Coupon:</b> <code>[REDACTED]</code>

⏳ <i>Pro Members received direct checkout link 15 minutes ago. Stock may be low.</i>
👉 <b>Upgrade to Pro to unlock instant sub-second alerts & direct cart links:</b>
🔗 <a href="http://localhost:8000/#pricing">Join Gold Deal Pro</a>
"""
        return message

    def format_deal_receipt_postmortem(self, deal: Dict[str, Any], seconds_active: int = 240) -> str:
        """Viral proof receipt showing how much money Pro users saved"""
        title = deal.get("title", "10g 24K Gold Bar")[:60]
        total_savings = deal.get("total_stack_savings", 3500.0)
        source = deal.get("source", "E-Commerce")

        message = f"""🧾 <b>DEAL OF THE DAY — EXHAUSTED PROOF</b> 🧾

📦 <b>Item:</b> {title}
🏬 <b>Platform:</b> {source}
⏱️ <b>Stock Lasted:</b> {seconds_active // 60}m {seconds_active % 60}s

💰 <b>Average Pro Member Savings:</b> ₹{total_savings:,.2f}
👥 <b>Pro Members Who Scored:</b> 18+ members

💡 <i>Free users saw this 15 mins late after stock ran out.</i>
⚡ <b>Never miss another flash gold drop:</b> <a href="http://localhost:8000/#pricing">Get Gold Deal Pro</a>
"""
        return message

    def dispatch_whatsapp_alert(self, phone: str, deal: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches deal alert directly to subscriber WhatsApp"""
        return whatsapp_service.dispatch_alert(to_phone=phone, deal=deal)

    async def dispatch_deal_alerts(self, deal: Dict[str, Any], is_vip: bool = True, whatsapp_number: Optional[str] = None):
        """Dispatches instantly to VIP and schedules delayed teaser to free channel"""
        # WhatsApp delivery for VIP subscribers
        if whatsapp_number:
            try:
                self.dispatch_whatsapp_alert(whatsapp_number, deal)
            except Exception as e:
                logger.error(f"Failed to dispatch VIP WhatsApp alert: {e}")

        if not self.bot:
            logger.info(f"Telegram bot not configured. Alert logged: {deal.get('title')}")
            return

        # 1. Dispatch to Pro VIP instantly
        try:
            pro_msg = self.format_pro_alert(deal)
            url = deal.get("url", "https://www.ajio.com")
            keyboard = [[InlineKeyboardButton("🛒 Direct 1-Click Checkout", url=url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await self.bot.send_message(
                chat_id=TELEGRAM_VIP_CHAT_ID,
                text=pro_msg,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            logger.info("Successfully dispatched Pro VIP Telegram alert.")
        except Exception as e:
            logger.error(f"Failed to send VIP Telegram alert: {e}")

        # 2. Schedule delayed teaser for free tier
        try:
            asyncio.create_task(self._send_delayed_free_teaser(deal, delay_seconds=FREE_TIER_DELAY_SECONDS))
        except Exception as e:
            logger.warning(f"Could not schedule delayed teaser task: {e}")

    async def _send_delayed_free_teaser(self, deal: Dict[str, Any], delay_seconds: int = 900):
        try:
            await asyncio.sleep(delay_seconds)
            if self.bot and TELEGRAM_FREE_CHAT_ID:
                teaser = self.format_free_teaser(deal)
                await self.bot.send_message(
                    chat_id=TELEGRAM_FREE_CHAT_ID,
                    text=teaser,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                logger.info("Sent delayed free-tier teaser alert.")
        except Exception as e:
            logger.warning(f"Failed to send delayed free teaser: {e}")


vip_dispatcher = VIPAlertDispatcher()
