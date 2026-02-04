import asyncio
import schedule
import time
from datetime import datetime
import json
from typing import List, Dict

from gold_scraper import GoldScraper
from telegram_bot import TelegramAlertBot
from config import MIN_DISCOUNT_PERCENTAGE, MIN_WEIGHT, MAX_PRICE_PER_GRAM

class GoldDealFinder:
    def __init__(self):
        self.scraper = GoldScraper()
        self.bot = TelegramAlertBot()
        self.sent_alerts = set()
        self.deals_history = []
        
    def filter_good_deals(self, products: List[Dict]) -> List[Dict]:
        """Filter products based on criteria"""
        good_deals = []
        
        for product in products:
            # Create unique key for product
            product_key = f"{product['source']}_{product['title'][:50]}_{product['weight_grams']}"
            
            # Check if already sent
            if product_key in self.sent_alerts:
                continue
            
            # Get max price for this purity
            purity = product['purity']
            max_price = MAX_PRICE_PER_GRAM.get(purity, MAX_PRICE_PER_GRAM['default'])
            
            print(f"Evaluating {product['url']} | Discount: {product['discount_percent']:.1f}% | Price/g: ₹{product['price_per_gram']:,.2f} | Max/g: ₹{max_price}")
            # Apply filters
            meets_criteria = (
                product['discount_percent'] >= MIN_DISCOUNT_PERCENTAGE and
                product['weight_grams'] >= MIN_WEIGHT and
                product['price_per_gram'] <= max_price and
                product['selling_price'] > 1000  # Minimum price
            )
            
            if meets_criteria:
                good_deals.append(product)
                self.sent_alerts.add(product_key)
                
                # Add to history
                self.deals_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'product': product
                })
                
                # Keep only last 100 deals in history
                if len(self.deals_history) > 100:
                    self.deals_history = self.deals_history[-100:]
        good_deals = sorted(
            good_deals,
            key=lambda p: p.get("discount_percent", float("inf"))
        )[:4]
        return good_deals
    
    async def run_scraping_cycle(self):
        """Run one complete scraping cycle"""
        print(f"\n{'='*60}")
        print(f"🔄 Starting scraping cycle at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        start_time = time.time()
        
        try:
            # Scrape all products
            all_products = self.scraper.scrape_all()
            
            # Filter for good deals
            good_deals = self.filter_good_deals(all_products)
            
            scraping_time = time.time() - start_time
            
            # Log results
            print(f"\n📊 Results:")
            print(f"   ├ Total products found: {len(all_products)}")
            print(f"   ├ Good deals found: {len(good_deals)}")
            print(f"   └ Scraping time: {scraping_time:.2f} seconds")
            
            if good_deals:
                print(f"\n🔥 Top deals:")
                for i, deal in enumerate(good_deals[:3], 1):
                    print(f"   {i}. {deal['source']}: {deal['discount_percent']:.1f}% off")
                    print(f"      {deal['title'][:50]}...")
                    print(f"      ₹{deal['selling_price']:,.0f} ({deal['weight_grams']}g {deal['purity']})")
                    print(f"      Price/g: ₹{deal['price_per_gram']:,.0f}")
            
            # Send alerts
            await self.bot.send_bulk_alerts(good_deals)
            
            # Send status update
            await self.bot.send_status_update(
                len(all_products), 
                len(good_deals), 
                scraping_time
            )
            
            # Save deals to file
            self.save_deals_to_file(good_deals)
            
        except Exception as e:
            print(f"❌ Error in scraping cycle: {e}")
            error_msg = f"⚠️ <b>Scraping Error</b>\n\nError: {str(e)[:100]}..."
            
            try:
                await self.bot.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=error_msg,
                    parse_mode='HTML'
                )
            except:
                pass
    
    def save_deals_to_file(self, deals: List[Dict]):
        """Save deals to JSON file for analysis"""
        try:
            filename = f"deals_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
            with open(filename, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'total_deals': len(deals),
                    'deals': deals
                }, f, indent=2)
            print(f"💾 Saved deals to {filename}")
        except Exception as e:
            print(f"Error saving deals to file: {e}")
    
    def schedule_scraping(self):
        """Schedule regular scraping"""
        print("\n" + "="*60)
        print("🏆 GOLD DEAL FINDER - Now with Accurate Price Calculation")
        print("="*60)
        print("\n📊 Features:")
        print("  • Real-time gold spot price tracking")
        print("  • GST calculation (3%)")
        print("  • Making charges based on purity and type")
        print("  • Live cache system for gold prices")
        print("  • Telegram alerts with rich formatting")
        print("\n🔍 Monitoring:")
        print("  • Myntra - Gold coins & jewellery")
        print("  • AJIO - Gold products")
        print(f"\n🎯 Alert threshold: Discount > {MIN_DISCOUNT_PERCENTAGE}%")
        print("="*60 + "\n")
        
        # Run immediately
        print("🚀 Running initial scan...")
        asyncio.run(self.run_scraping_cycle())
        
        # Schedule every hour
        schedule.every(1).hours.do(lambda: asyncio.run(self.run_scraping_cycle()))
        
        # Schedule at peak shopping times
        peak_times = ["09:00", "12:00", "15:00", "18:00", "21:00", "22:00"]
        for peak_time in peak_times:
            schedule.every().day.at(peak_time).do(
                lambda: asyncio.run(self.run_scraping_cycle())
            )
        
        print("\n⏰ Scheduling started:")
        print("   • Initial scan completed")
        print("   • Scans every hour")
        print("   • Peak time scans at:", ", ".join(peak_times))
        print("\n📱 Alerts will be sent to Telegram")
        print("💾 Gold prices cached for 60 seconds")
        print("="*60 + "\n")
        
        # Keep the script running
        # try:
        #     while True:
        #         schedule.run_pending()
        #         time.sleep(60)
        # except KeyboardInterrupt:
        #     print("\n\n👋 Shutting down Gold Deal Finder...")
        #     print("Thanks for using the service!")
        # except Exception as e:
        #     print(f"\n❌ Unexpected error: {e}")

def main():
    """Main entry point"""
    finder = GoldDealFinder()
    finder.schedule_scraping()

if __name__ == "__main__":
    # Run the main function
    main()