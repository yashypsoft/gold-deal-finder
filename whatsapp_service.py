import os
import logging
from typing import Dict, Any, Optional
import requests

logger = logging.getLogger(__name__)

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")
WHATSAPP_TEMPLATE_NAME = os.getenv("WHATSAPP_TEMPLATE_NAME", "gold_arbitrage_alert")


class WhatsAppCloudService:
    """
    Sub-second WhatsApp Business Cloud API dispatcher for VIP deal alerts.
    """

    def __init__(self):
        self.token = WHATSAPP_TOKEN
        self.phone_id = WHATSAPP_PHONE_ID
        self.template_name = WHATSAPP_TEMPLATE_NAME
        self.api_url = f"https://graph.facebook.com/v19.0/{self.phone_id}/messages" if self.phone_id else ""

    def is_configured(self) -> bool:
        return bool(self.token and self.phone_id)

    def format_text_alert(self, deal: Dict[str, Any]) -> str:
        """WhatsApp formatted text with bold styling and clean emojis"""
        title = deal.get("title", "")[:50]
        platform = deal.get("source", deal.get("platform", "E-Commerce"))
        weight = deal.get("weight_grams", 1.0)
        purity = deal.get("purity", "24K")
        net_price = deal.get("effective_net_price", deal.get("selling_price", 0))
        net_ppg = deal.get("effective_price_per_gram", 0)
        spot_ppg = deal.get("live_spot_rate_per_gram", 15837.5)
        spread_ppg = deal.get("spread_per_gram", 0)
        savings = deal.get("total_stack_savings", 0)
        card = deal.get("recommended_card", "Optimal Card")
        url = deal.get("url", "http://localhost:8000")

        return f"""🚨 *SUB-SPOT GOLD ARBITRAGE ALERT* 🚨

🪙 *{platform} • {title}*
⚖️ *Weight:* {weight}g | *Purity:* {purity}

💰 *Effective Net Cost:* ₹{net_price:,.2f} (*₹{net_ppg:,.2f}/g*)
🏪 *Wholesale Spot Rate:* ₹{spot_ppg:,.2f}/g
🔥 *SPREAD BELOW SPOT:* *₹{spread_ppg:,.2f}/gram*
💵 *Your Net Profit/Savings:* *₹{savings:,.2f}*

💳 *Best Payment Card:* {card}
🛒 *Direct 1-Click Checkout:* {url}

⚡ _Sub-second VIP notification delivered to your WhatsApp._"""

    def dispatch_alert(self, to_phone: str, deal: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches WhatsApp alert via Meta Graph API or simulates if not configured."""
        formatted_phone = to_phone.replace("+", "").replace(" ", "").replace("-", "")
        if not formatted_phone.startswith("91") and len(formatted_phone) == 10:
            formatted_phone = "91" + formatted_phone

        text_message = self.format_text_alert(deal)

        if not self.is_configured():
            logger.info(f"WhatsApp Cloud API simulated for {formatted_phone}: {deal.get('title')[:30]}")
            return {
                "status": "simulated",
                "phone": formatted_phone,
                "message_preview": text_message[:100] + "..."
            }

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        # Dispatch via WhatsApp Template or Interactive Message
        payload = {
            "messaging_product": "whatsapp",
            "to": formatted_phone,
            "type": "text",
            "text": {"body": text_message}
        }

        try:
            resp = requests.post(self.api_url, headers=headers, json=payload, timeout=5)
            if resp.status_code in (200, 201):
                logger.info(f"WhatsApp alert successfully dispatched to {formatted_phone}")
                return {"status": "success", "response": resp.json()}
            else:
                logger.error(f"WhatsApp API error {resp.status_code}: {resp.text}")
                return {"status": "error", "code": resp.status_code, "detail": resp.text}
        except Exception as e:
            logger.error(f"Failed to dispatch WhatsApp alert: {e}")
            return {"status": "failed", "error": str(e)}


whatsapp_service = WhatsAppCloudService()
