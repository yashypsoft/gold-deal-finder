#!/usr/bin/env python3
"""
Simplified scanner for GitHub Actions
Runs the gold deal finder and sends results to Telegram
"""

import os
import sys
import json
import gzip
import shutil
import asyncio
from datetime import datetime
from pathlib import Path
import logging

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gold_scraper import GoldScraper
from telegram_bot import TelegramAlertBot
from price_calculator import GoldPriceCalculator
from config import MIN_DISCOUNT_PERCENTAGE, MIN_WEIGHT

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GitHubActionsScanner:
    def __init__(self):
        self.scraper = GoldScraper()
        self.bot = TelegramAlertBot()
        self.price_calc = GoldPriceCalculator()
        self.test_run = os.getenv('TEST_RUN', 'false').lower() == 'true'
        
        if self.test_run:
            logger.info("🔧 Running in TEST mode — No Telegram alerts will be sent")

    def _load_sent_alerts(self) -> set:
        """Load previously sent alert URLs to avoid duplicate Telegram notifications."""
        alert_file = Path("data/sent_alerts.json")
        if alert_file.exists():
            try:
                return set(json.loads(alert_file.read_text()))
            except Exception:
                return set()
        return set()

    def _save_sent_alerts(self, urls: set) -> None:
        """Persist sent alert URLs (keep last 500 to bound file size)."""
        alert_file = Path("data/sent_alerts.json")
        alert_file.write_text(json.dumps(list(urls)[-500:]))
        
    def filter_good_deals(self, products):
        """Filter products based on criteria"""
        good_deals = []
        
        for product in products:
            # Apply filters
            meets_criteria = (
                product['discount_percent'] >= MIN_DISCOUNT_PERCENTAGE and
                product['weight_grams'] >= MIN_WEIGHT and
                product['selling_price'] > 1000
            )
            
            if meets_criteria:
                good_deals.append(product)

        good_deals = sorted(
            good_deals,
            key=lambda p: p.get("discount_percent", float("inf"))
        )[:4]
        return good_deals
    
    async def send_telegram_summary(self, total_products, good_deals, duration):
        """Send summary to Telegram"""
        try:
            # Get current gold prices
            gold_data = self.price_calc.get_live_gold_price()
            gold_price = gold_data['gold']['per_gram']['999_landed']
            
            # Create summary message
            summary = f"""
📊 <b>GitHub Actions - Scan Complete</b>

✅ <b>Scan Results:</b>
├ Products scanned: {total_products}
├ Good deals found: {len(good_deals)}
├ Scan duration: {duration:.1f}s
└ Gold price: ₹{gold_price:,.0f}/g

🎯 <b>Deal Criteria:</b>
├ Min discount: {MIN_DISCOUNT_PERCENTAGE}%
├ Min weight: {MIN_WEIGHT}g
└ Active monitoring: Myntra & AJIO

"""
            
            if good_deals:
                summary += f"\n🔥 <b>Top {min(3, len(good_deals))} Deals:</b>\n"
                for i, deal in enumerate(good_deals[:3], 1):
                    summary += f"{i}. {deal['source']}: {deal['discount_percent']:.1f}% off\n"
                    summary += f"   ₹{deal['selling_price']:,.0f} ({deal['weight_grams']}g {deal['purity']})\n"
            
            summary += f"\n⏰ <i>Next scan: 10 minutes</i>"
            summary += f"\n🔄 <i>Run ID: #{os.getenv('GITHUB_RUN_NUMBER', 'N/A')}</i>"
            
            # Send summary
            await self.bot.bot.send_message(
                chat_id=os.getenv('TELEGRAM_CHAT_ID'),
                text=summary,
                parse_mode='HTML'
            )
            
            # Send individual alerts for good deals (if not test run)
            if good_deals and not self.test_run:
                sent_urls = self._load_sent_alerts()
                new_deals = [d for d in good_deals if d.get('url') not in sent_urls]
                if new_deals:
                    logger.info(f"Sending {len(new_deals)} NEW deal alerts (skipped {len(good_deals) - len(new_deals)} duplicates)")
                    await asyncio.gather(
                        *(self.bot.send_alert(d) for d in new_deals)
                    )
                    sent_urls.update(d.get('url', '') for d in new_deals)
                    self._save_sent_alerts(sent_urls)
                else:
                    logger.info("All deals already sent — skipping alerts")
                    
        except Exception as e:
            logger.error(f"Error sending Telegram summary: {e}")
    
    async def run_scan(self):
        logger.info("🚀 Starting gold deal scan...")
        start_time = datetime.now()

        try:
            # Run sources concurrently
            all_products = await asyncio.to_thread(self.scraper.scrape_all)

            good_deals = self.filter_good_deals(all_products)

            duration = (datetime.now() - start_time).total_seconds()

            logger.info(f"📊 Scan completed in {duration:.1f}s")
            logger.info(f"📦 Total products: {len(all_products)}")
            logger.info(f"🔥 Good deals: {len(good_deals)}")

            self.save_results(all_products, good_deals, duration)

            if not self.test_run:
                await self.send_telegram_summary(
                    len(all_products), good_deals, duration
                )

            return len(good_deals)


        except Exception as e:
            logger.error(f"❌ Scan failed: {e}")
            import traceback
            traceback.print_exc()
            
            # Send error notification
            if not self.test_run:
                try:
                    error_msg = f"""
❌ <b>Scan Failed</b>

Error: {str(e)[:200]}
Time: {datetime.now().strftime('%H:%M:%S')}
Run ID: #{os.getenv('GITHUB_RUN_NUMBER', 'N/A')}

<i>Check GitHub Actions logs for details.</i>
"""
                    await self.bot.bot.send_message(
                        chat_id=os.getenv('TELEGRAM_CHAT_ID'),
                        text=error_msg,
                        parse_mode='HTML'
                    )
                except:
                    pass
            
            return 0
    
    def save_results(self, all_products, good_deals, duration):
        """Save scan results to JSON file"""
        try:
            results = {
                'timestamp': datetime.now().isoformat(),
                'duration_seconds': duration,
                'total_products': len(all_products),
                'good_deals': len(good_deals),
                'all_products': all_products,
                'good_deals_details': good_deals,
                'github_run_id': os.getenv('GITHUB_RUN_ID', ''),
                'github_run_number': os.getenv('GITHUB_RUN_NUMBER', '')
            }
            
             # Save results in background
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"data/scan_results_{timestamp}.json"
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            
            logger.info(f"💾 Results saved to {filename}")
            
        except Exception as e:
            logger.error(f"Error saving results: {e}")

    @staticmethod
    def rotate_old_scans(max_files=200, compress_after=50):
        """Compress old scans to .gz and delete beyond max_files."""
        data_dir = Path("data")
        # Compress old JSON files
        json_files = sorted(
            data_dir.glob("scan_results_*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        for f in json_files[compress_after:]:
            try:
                with open(f, 'rb') as fin:
                    with gzip.open(f.with_suffix('.json.gz'), 'wb') as fout:
                        shutil.copyfileobj(fin, fout)
                f.unlink()
                logger.info(f"Compressed {f.name}")
            except Exception as e:
                logger.error(f"Error compressing {f.name}: {e}")

        # Delete files beyond max
        all_files = sorted(
            list(data_dir.glob("scan_results_*.json")) +
            list(data_dir.glob("scan_results_*.json.gz")),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        for f in all_files[max_files:]:
            try:
                f.unlink()
                logger.info(f"Deleted old scan {f.name}")
            except Exception as e:
                logger.error(f"Error deleting {f.name}: {e}")

async def main():
    """Main entry point"""
    scanner = GitHubActionsScanner()
    deals_found = await scanner.run_scan()
    scanner.rotate_old_scans()
    
    # Exit with code based on success
    sys.exit(0 if deals_found >= 0 else 1)

if __name__ == "__main__":
    asyncio.run(main())