import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SUBSCRIPTION_PLANS
from price_calculator import GoldPriceCalculator
from typing import List, Dict, Optional, Any
from datetime import datetime
from database import db_manager
from arbitrage_engine import arbitrage_engine
from sgb_screener import sgb_screener

class TelegramAlertBot:
    def __init__(self):
        self.bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
        self.price_calculator = GoldPriceCalculator()
    
    async def send_alert(self, product: Dict):
        """Send alert for a single product"""
        try:
            # Create message
            message = self._format_product_message(product)
            
            # Create inline keyboard
            keyboard = [
                [InlineKeyboardButton("🛒 View Product", url=product['url'])],
                [InlineKeyboardButton("📊 Price Details", callback_data=f"details_{product['source']}_{product['title'][:20]}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send with image if available
            if product.get('image_url'):
                try:
                    await self.bot.send_photo(
                        chat_id=TELEGRAM_CHAT_ID,
                        photo=product['image_url'],
                        caption=message,
                        parse_mode='HTML',
                        reply_markup=reply_markup
                    )
                    return
                except Exception as e:
                    print(f"Failed to send photo: {e}")
                    # Fall through to text message
            
            # Send text message
            await self.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=message,
                parse_mode='HTML',
                reply_markup=reply_markup,
                disable_web_page_preview=False
            )
            
        except Exception as e:
            print(f"Error sending Telegram alert: {e}")
    
    def _format_product_message(self, product: Dict) -> str:
        """Format product information for Telegram message"""
        # Emoji based on discount
        if product['discount_percent'] > 15:
            discount_emoji = "🔥🔥"
        elif product['discount_percent'] > 10:
            discount_emoji = "🔥"
        elif product['discount_percent'] > 5:
            discount_emoji = "💰"
        else:
            discount_emoji = "💎"
        
        # Format numbers
        selling_price = f"₹{product['selling_price']:,.2f}"
        expected_price = f"₹{product['expected_price']:,.2f}"
        price_per_gram = f"₹{product['price_per_gram']:,.2f}"
        
        # Product type emoji
        type_emoji = "💍" if product['is_jewellery'] else "🪙"
        
        message = f"""
{discount_emoji} <b>GOLD DEAL ALERT!</b> {discount_emoji}

{type_emoji} <b>{product['source']} - {product['brand']}</b>
📦 <b>Product:</b> {product['title'][:80]}...

<b>⚖️ Weight:</b> {product['weight_grams']}g
<b>🔬 Purity:</b> {product['purity']}
<b>🏷️ Type:</b> {'Jewellery' if product['is_jewellery'] else 'Coin/Bar'}

<b>💰 Selling Price:</b> {selling_price}
<b>📈 Expected Value:</b> {expected_price}
<b>💎 Price per gram:</b> {price_per_gram}

<b>📊 Making Charges:</b> {product['making_charges_percent']:.1f}%
<b>🧾 GST:</b> {product['gst_percent']:.1f}%

<code>🎯 DISCOUNT: {product['discount_percent']:.1f}%</code>

<b>🏪 Market Spot Price:</b> ₹{product['spot_price']:,.2f}/g
<b>⏰ Found at:</b> {datetime.fromisoformat(product['timestamp']).strftime('%I:%M %p')}
"""
        return message
    
    async def send_bulk_alerts(self, products: List[Dict]):
        """Send alerts for multiple products"""
        if not products:
            await self.send_no_deals_message()
            return
        
        # Sort by discount (highest first)
        products.sort(key=lambda x: x['discount_percent'], reverse=True)
        
        # Send price summary first
        await self.send_price_summary()
        
        # Send top 5 deals
        for product in products[:5]:
            await self.send_alert(product)
        
        # If more deals, send summary
        if len(products) > 5:
            await self.send_deals_summary(products)
    
    async def send_price_summary(self):
        """Send current gold price summary"""
        try:
            summary = self.price_calculator.get_price_summary()
            
            await self.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=summary,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Error sending price summary: {e}")
    
    async def send_no_deals_message(self):
        """Send message when no deals found"""
        message = """
📭 <b>No Gold Deals Found</b>

No significant discounts found in the current scan.
Will check again in the next cycle.

💡 <i>Tip: Check back during sale events for better deals!</i>
"""
        
        await self.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            parse_mode='HTML'
        )
    
    async def send_deals_summary(self, products: List[Dict]):
        """Send summary of all deals"""
        top_deals = products[:5]
        other_deals = products[5:]
        
        summary = f"""
📋 <b>Deals Summary</b>

<b>Top {len(top_deals)} Deals:</b>
"""
        
        for i, product in enumerate(top_deals, 1):
            summary += f"{i}. {product['source']}: {product['discount_percent']:.1f}% off ({product['weight_grams']}g {product['purity']})\n"
        
        if other_deals:
            summary += f"\n<b>Plus {len(other_deals)} more deals available!</b>"
        
        summary += f"\n\n<i>Total deals found: {len(products)}</i>"
        
        await self.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=summary,
            parse_mode='HTML'
        )
    
    async def send_status_update(self, total_products: int, good_deals: int, 
                                 scraping_time: float):
        """Send scraping status update"""
        status = f"""
🔄 <b>Scraping Complete</b>

✅ Successfully scanned:
   • Myntra - Gold products
   • AJIO - Gold jewellery & coins

📊 <b>Results:</b>
   ├ Total products found: {total_products}
   ├ Good deals found: {good_deals}
   └ Scraping time: {scraping_time:.1f}s

⏰ <b>Next scan:</b> 1 hour
📈 <b>Live gold price:</b> Updated with cache

<i>System running normally. Alerts sent for all good deals.</i>
"""
        
        await self.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=status,
            parse_mode='HTML'
        )


# ==========================================
# INTERACTIVE TELEGRAM BOT SLASH COMMANDS
# ==========================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name if update.effective_user else "Investor"
    user = db_manager.get_or_create_user(user_id=f"tg_{chat_id}", telegram_chat_id=chat_id, name=user_name)
    tier = user.get("current_tier", "FREE")

    welcome_msg = f"""👋 <b>Welcome to Gold Deal Finder, {user_name}!</b>

Your Current Status: <b>{tier} Member</b>

⚡ <b>Available Commands:</b>
• <code>/subspot</code> - Live bullion deals trading <b>BELOW</b> wholesale spot price
• <code>/sgb</code> - Sovereign Gold Bond secondary market screener (Discounts & YTM)
• <code>/upgrade</code> - Activate Pro VIP membership (Instant sub-second alerts)
• <code>/cards</code> - View supported credit cards & active promotions
• <code>/help</code> - Get assistance & FAQ

🌐 <b>Live Web Dashboard:</b> http://localhost:8000
"""
    keyboard = [
        [InlineKeyboardButton("⚡ Sub-Spot Deals", callback_data="cmd_subspot"),
         InlineKeyboardButton("🏛️ SGB Screener", callback_data="cmd_sgb")],
        [InlineKeyboardButton("👑 Upgrade to Pro", callback_data="cmd_upgrade"),
         InlineKeyboardButton("🌐 Open Dashboard", url="http://localhost:8000")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_msg, parse_mode="HTML", reply_markup=reply_markup)


async def cmd_subspot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    deals = db_manager.get_sub_spot_deals(limit=3)
    if not deals:
        await update.message.reply_text("🔍 Scanning market... No sub-spot negative premium deals found at this moment. Check back soon!", parse_mode="HTML")
        return

    msg = "🚨🔥 <b>TOP LIVE SUB-SPOT ARBITRAGE DEALS</b> 🔥🚨\n\n"
    for i, d in enumerate(deals, 1):
        title = d.get("title", "")[:45]
        spread = d.get("arbitrage_spread_inr", 0)
        net_price = d.get("effective_net_price", d.get("selling_price", 0))
        net_ppg = d.get("effective_price_per_gram", 0)
        spot_ppg = d.get("live_spot_rate_per_gram", 15837.5)
        source = d.get("platform", d.get("source", "Store"))
        card = d.get("recommended_card", "Optimal Card")

        msg += f"<b>{i}. {source} • {title}</b>\n"
        msg += f"   💰 Effective Price: <b>₹{net_price:,.0f}</b> (₹{net_ppg:,.0f}/g)\n"
        msg += f"   🏪 Wholesale Spot: ₹{spot_ppg:,.0f}/g\n"
        msg += f"   🚀 <b>Saves: ₹{spread:,.0f} BELOW SPOT!</b>\n"
        msg += f"   💳 Best Card: {card}\n"
        msg += f"   🛒 <a href=\"{d.get('url', 'http://localhost:8000')}\">Direct Checkout Link</a>\n\n"

    msg += "⚡ <i>Sub-second alerts delivered exclusively to Pro VIP members.</i>"
    await update.message.reply_text(msg, parse_mode="HTML", disable_web_page_preview=True)


async def cmd_sgb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tranches = sgb_screener.scan_all_tranches()[:3]
    if not tranches:
        await update.message.reply_text("Unable to load SGB tranches right now. Please try again later.", parse_mode="HTML")
        return

    msg = "🏛️ <b>TOP DISCOUNTED SOVEREIGN GOLD BONDS (SGB)</b> 🏛️\n"
    msg += "<i>RBI Guaranteed • 100% Tax-Free Capital Gains • +2.5% Annual Interest</i>\n\n"

    for i, t in enumerate(tranches, 1):
        msg += f"<b>{i}. {t['ticker']} (NSE)</b>\n"
        msg += f"   🏷️ Market Price: <b>₹{t['ltp']:,.0f}</b> (Fair Spot: ₹{t['underlying_spot_price']:,.0f})\n"
        msg += f"   🔥 Discount to Spot: <b>-{t['discount_to_spot_pct']}%</b>\n"
        msg += f"   📈 Annualized YTM: <b>{t['annualized_ytm_pct']}% p.a.</b>\n"
        msg += f"   ⏳ Maturity: {t['maturity_date']} ({t['years_to_maturity']} yrs left)\n\n"

    msg += "👉 View all 60+ live tranches: http://localhost:8000"
    await update.message.reply_text(msg, parse_mode="HTML", disable_web_page_preview=True)


async def cmd_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """👑 <b>UPGRADE TO GOLD DEAL PRO</b> 👑

<b>Why Pro Members Never Miss a Drop:</b>
✅ <b>0-Second VIP Telegram & WhatsApp</b> (Beats free delayed channel)
✅ <b>Unredacted Direct Cart Links</b> with auto-applied coupons
✅ <b>Negative Premium Engine</b> (Gold priced ₹500 to ₹3,500/g below spot)
✅ <b>Full SGB Secondary Screener</b> with live depth and YTM
✅ <b>Guaranteed Positive ROI:</b> Saves 5x-10x the monthly fee in 1 order!

💎 <b>Subscription Plans:</b>
• <b>Pro Monthly:</b> ₹599 / month
• <b>Festive Pass (45 Days):</b> ₹899 (Dhanteras Special)
• <b>Pro Annual:</b> ₹4,999 / year (Save 30%)

👉 <b>Activate Your Membership:</b>
<a href="http://localhost:8000/#pricing">Click Here to Upgrade Instantly</a>
"""
    keyboard = [
        [InlineKeyboardButton("⚡ Activate Pro Now", url="http://localhost:8000")],
        [InlineKeyboardButton("💬 Contact Support", url="https://t.me/")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=reply_markup)


def create_bot_application() -> Optional[Application]:
    """Factory creating telegram bot Application with command handlers attached"""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == 'YOUR_BOT_TOKEN':
        return None

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("subspot", cmd_subspot))
    app.add_handler(CommandHandler("sgb", cmd_sgb))
    app.add_handler(CommandHandler("upgrade", cmd_upgrade))
    return app