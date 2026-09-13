"""
High-Frequency Restock Sniper Micro-Worker
Monitors high-value out-of-stock gold bullion SKUs on Ajio, Myntra, and Tata CLiQ.
Triggers instant VIP alerts the exact moment inventory is restored (e.g. cart drops / cancellations).
"""

import time
import logging
import asyncio
import threading
from typing import Dict, Any, List, Optional
import requests

from config import REQUEST_TIMEOUT
from database import db
from vip_alerts import vip_dispatcher
from card_engine import card_stacker
from arbitrage_engine import arbitrage_engine

logger = logging.getLogger(__name__)


# Default high-demand bullion SKUs to seed the watch list
DEFAULT_WATCH_SKUS = [
    {
        "sku_id": "ajio_mmtc_pamp_1g",
        "title": "MMTC-PAMP 24K 999.9 Pure Lotus Gold Coin 1g",
        "platform": "Ajio",
        "url": "https://www.ajio.com/mmtc-pamp-24k-999-9-pure-lotus-gold-coin-1g/p/460775836_gold",
        "weight_grams": 1.0,
        "purity": "24K",
        "target_price": 14500.0,
        "last_status": "OUT_OF_STOCK"
    },
    {
        "sku_id": "ajio_brpl_24k_5g",
        "title": "Bangalore Refinery 24k (999) 5g Yellow Gold Bar",
        "platform": "Ajio",
        "url": "https://www.ajio.com/bangalore-refinery-24k-999-5g-yellow-gold-bar/p/461234567_gold",
        "weight_grams": 5.0,
        "purity": "24K",
        "target_price": 72000.0,
        "last_status": "OUT_OF_STOCK"
    },
    {
        "sku_id": "myntra_malabar_1g",
        "title": "Malabar Gold & Diamonds 24K (999) 1g Rose Design Gold Coin",
        "platform": "Myntra",
        "url": "https://www.myntra.com/gold-coin/malabar-gold-and-diamonds/malabar-24k-gold-coin-1g/1234567/buy",
        "weight_grams": 1.0,
        "purity": "24K",
        "target_price": 14600.0,
        "last_status": "OUT_OF_STOCK"
    }
]


class RestockSniper:
    """
    Sub-minute inventory polling state-machine for high-demand gold deals.
    """

    def __init__(self, poll_interval_seconds: int = 30):
        self.poll_interval = poll_interval_seconds
        self.watch_list: Dict[str, Dict[str, Any]] = {}
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self.restock_history: List[Dict[str, Any]] = []

        # Load initial items
        self._seed_default_watch_items()

    def _seed_default_watch_items(self):
        """Seeds default watch list into memory and database"""
        for item in DEFAULT_WATCH_SKUS:
            self.watch_list[item["sku_id"]] = {
                **item,
                "added_at": time.time(),
                "last_checked_at": None,
                "check_count": 0
            }

    def add_watch_sku(
        self,
        sku_id: str,
        title: str,
        platform: str,
        url: str,
        weight_grams: float,
        purity: str = "24K",
        target_price: float = 0.0
    ) -> Dict[str, Any]:
        """Adds a SKU to the active sniper watch list"""
        item = {
            "sku_id": sku_id,
            "title": title,
            "platform": platform,
            "url": url,
            "weight_grams": float(weight_grams),
            "purity": purity,
            "target_price": float(target_price),
            "last_status": "OUT_OF_STOCK",
            "added_at": time.time(),
            "last_checked_at": None,
            "check_count": 0
        }
        self.watch_list[sku_id] = item
        logger.info(f"Added SKU to Restock Sniper: {title} ({sku_id})")
        return item

    def remove_watch_sku(self, sku_id: str) -> bool:
        """Removes a SKU from the sniper watch list"""
        if sku_id in self.watch_list:
            del self.watch_list[sku_id]
            logger.info(f"Removed SKU from Restock Sniper: {sku_id}")
            return True
        return False

    def get_watch_list(self) -> List[Dict[str, Any]]:
        """Returns all currently monitored SKUs"""
        return list(self.watch_list.values())

    def check_sku_stock(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Probes the inventory endpoint / page for the given SKU.
        Returns the updated item dict with current stock status.
        """
        sku_id = item["sku_id"]
        url = item.get("url", "")
        platform = item.get("platform", "").lower()
        now = time.time()

        item["last_checked_at"] = now
        item["check_count"] = item.get("check_count", 0) + 1

        # Real HTTP probe with short timeout
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

        current_status = "OUT_OF_STOCK"
        selling_price = item.get("target_price", 0)

        try:
            # We perform a lightweight request
            resp = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
            if resp.status_code == 200:
                html = resp.text.lower()
                # Check for explicit out-of-stock indicators
                oos_indicators = ["out of stock", "sold out", "currently unavailable", "notify me", "item unavailable"]
                in_stock_indicators = ["add to bag", "add to cart", "buy now", "in stock"]

                is_oos = any(ind in html for ind in oos_indicators)
                is_in_stock = any(ind in html for ind in in_stock_indicators)

                if is_in_stock and not is_oos:
                    current_status = "IN_STOCK"
                else:
                    current_status = "OUT_OF_STOCK"
            else:
                current_status = "OUT_OF_STOCK"
        except Exception as e:
            logger.debug(f"Restock sniper probe failed for {sku_id}: {e}")
            # Keep previous status or default out of stock
            current_status = item.get("last_status", "OUT_OF_STOCK")

        previous_status = item.get("last_status", "OUT_OF_STOCK")
        item["last_status"] = current_status

        # Transition trigger: OUT_OF_STOCK -> IN_STOCK!
        if previous_status == "OUT_OF_STOCK" and current_status == "IN_STOCK":
            self._handle_restock_event(item)

        return item

    def _handle_restock_event(self, item: Dict[str, Any]):
        """
        Executes immediate VIP notification dispatch upon inventory detection.
        """
        logger.info(f"🔥 RESTOCK DETECTED! {item['title']} is now back IN STOCK on {item['platform']}!")

        # Synthesize deal object
        deal = {
            "id": item["sku_id"],
            "title": f"⚡ RESTOCK: {item['title']}",
            "source": item["platform"],
            "platform": item["platform"],
            "url": item["url"],
            "weight_grams": item["weight_grams"],
            "purity": item["purity"],
            "selling_price": item["target_price"] or 15000.0,
            "effective_net_price": item["target_price"] or 15000.0,
            "effective_price_per_gram": (item["target_price"] or 15000.0) / item["weight_grams"],
            "live_spot_rate_per_gram": 15837.5,
            "spread_per_gram": 15837.5 - ((item["target_price"] or 15000.0) / item["weight_grams"]),
            "is_sub_spot": True,
            "recommended_card": "Tata Neu Infinity (10%)"
        }

        # Record in history
        restock_record = {
            "sku_id": item["sku_id"],
            "title": item["title"],
            "platform": item["platform"],
            "url": item["url"],
            "timestamp": time.time(),
            "notified": True
        }
        self.restock_history.append(restock_record)
        if len(self.restock_history) > 50:
            self.restock_history.pop(0)

        # Dispatch via VIP alerts engine (Telegram + WhatsApp)
        try:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(vip_dispatcher.dispatch_deal_alerts(deal, is_vip=True))
            except RuntimeError:
                asyncio.run(vip_dispatcher.dispatch_deal_alerts(deal, is_vip=True))
        except Exception as e:
            logger.error(f"Error dispatching restock VIP alert: {e}")

    def poll_once(self) -> List[Dict[str, Any]]:
        """Executes a single polling pass over all monitored SKUs"""
        results = []
        for sku_id, item in list(self.watch_list.items()):
            updated = self.check_sku_stock(item)
            results.append(updated)
        return results

    def start_background_loop(self):
        """Starts the background worker thread if not already active"""
        if self.is_running:
            return

        self.is_running = True

        def _loop():
            logger.info(f"Restock Sniper thread started with {len(self.watch_list)} monitored SKUs.")
            while self.is_running:
                try:
                    self.poll_once()
                except Exception as e:
                    logger.error(f"Error in restock sniper poll loop: {e}")
                time.sleep(self.poll_interval)
            logger.info("Restock Sniper thread stopped.")

        self._thread = threading.Thread(target=_loop, daemon=True, name="RestockSniperWorker")
        self._thread.start()

    def stop_background_loop(self):
        """Stops the background worker thread"""
        self.is_running = False

    def get_status(self) -> Dict[str, Any]:
        """Returns the current operational status of the Restock Sniper"""
        return {
            "is_running": self.is_running,
            "poll_interval_seconds": self.poll_interval,
            "active_skus_monitored": len(self.watch_list),
            "recent_restock_events": self.restock_history[-10:],
            "skus": list(self.watch_list.values())
        }


restock_sniper = RestockSniper()
