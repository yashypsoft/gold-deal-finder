import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from price_calculator import GoldPriceCalculator
from typing import List, Dict
from datetime import datetime

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