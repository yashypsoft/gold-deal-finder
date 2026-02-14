import json
import time
import requests
import os
import fcntl
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from config import GST_RATE, PURITY_MAPPING
import logging
import threading
from functools import lru_cache

logger = logging.getLogger(__name__)

class GoldPriceCalculator:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        # Singleton pattern to ensure only one instance exists
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance
    
    def __init__(self):
        # Only initialize once
        if hasattr(self, '_initialized'):
            return
            
        # Multiple API endpoints for redundancy
        self.API_ENDPOINTS = [
            {
                'name': 'myb-be',
                'url': 'https://myb-be.onrender.com/api/rates',
                'parser': self._parse_myb_response
            },
            {
                'name': 'goldprice.org',
                'url': 'https://data-asg.goldprice.org/dbXRates/INR',
                'parser': self._parse_goldprice_response
            }
        ]
        
        self.CACHE_FILE = Path("bullion_cache.json")
        self.CACHE_TTL = 300  # 5 minutes cache
        self._last_api_call = 0
        self._cache_lock = threading.Lock()
        self._min_api_interval = 2  # Minimum seconds between API calls
        
        # Constants
        self.OZ_TO_GRAM = 31.1035
        self.LANDED_MULTIPLIER = 1.11
        self.RETAIL_SPREAD = 700  # For 10g
        self.RTGS_DISCOUNT = 600  # For 10g
        self.JEWELLERY_PREMIUM_22K = 1200  # For 10g
        
        # Making charges percentages
        self.MAKING_CHARGES = {
            'coin_24K': 0.00,      # 3% for 24K coins/bars
            'coin_22K': 0.00,      # 4% for 22K coins
            'jewellery_24K': 0.00, # 8% for 24K jewellery
            'jewellery_22K': 0.00, # 12% for 22K jewellery
            'jewellery_18K': 0.00, # 15% for 18K jewellery
            'jewellery_14K': 0.00, # 18% for 14K jewellery
        }
        
        self._initialized = True
    
    def _parse_myb_response(self, response_data: Dict) -> Dict:
        """Parse response from myb-be API and return the complete data structure"""
        try:
            # Extract spot prices
            spot = response_data['spot']
            gold_products = response_data['goldProducts']
            silver_products = response_data['silverProducts']
            gold_by_karat = response_data['goldByKarat']
            
            # Calculate per gram prices from 10g prices
            gold_per_gram = float(gold_products['retail999']) / 10
            
            # Create output structure matching our expected format
            output = {
                "timestamp": datetime.utcnow().isoformat(),
                "source": "live_api",
                "spot_price_per_gram": round(gold_per_gram, 2),
                "gold": {
                    "spot_10g": round(float(spot['gldInr']), 2),
                    "retail_999_10g": round(float(gold_products['retail999']), 2),
                    "rtgs_999_10g": round(float(gold_products['rtgs999']), 2),
                    "999_with_gst_10g": round(float(gold_products['withGst999']), 2),
                    "retail_22k_10g": round(float(gold_by_karat['22K']), 2),
                    "retail_22k_with_gst_10g": round(float(gold_by_karat['22K']) * (1 + GST_RATE/100), 2),
                    "per_gram": {
                        "999_spot": round(float(spot['gldInr']) / 10, 2),
                        "999_landed": round(float(gold_products['withGst999']) / 10, 2),
                        "22k_spot": round(float(gold_by_karat['22K']) / 10, 2),
                        "22k_landed": round(float(gold_by_karat['22K']) / 10, 2),
                    }
                },
                "silver": {
                    "per_gram": round(float(silver_products['retail999']) / 1000, 2),
                    "per_kg": round(float(silver_products['retail999']), 2)
                },
                "raw_api_response": response_data  # Store original for reference if needed
            }
            
            logger.info(f"Successfully parsed myb-be response")
            return output
            
        except (KeyError, ValueError) as e:
            logger.error(f"Error parsing myb-be response: {e}")
            raise
    
    def _parse_goldprice_response(self, response_data: Dict) -> Dict:
        """Parse response from goldprice.org and calculate all prices"""
        try:
            item = response_data["items"][0]
            xau = float(item["xauPrice"])  # Gold price per troy ounce in INR
            xag = float(item["xagPrice"])  # Silver price per troy ounce in INR
            
            # Calculate all prices from spot
            gold_per_gram = xau / self.OZ_TO_GRAM
            silver_per_gram = xag / self.OZ_TO_GRAM
            
            spot_10g = gold_per_gram * 10
            landed_10g = spot_10g * self.LANDED_MULTIPLIER
            
            # 24K (999) prices for 10g
            retail_999 = landed_10g + self.RETAIL_SPREAD
            rtgs_999 = landed_10g - self.RTGS_DISCOUNT
            gst_999 = rtgs_999
            
            # 22K prices for 10g
            base_22k = landed_10g * 0.9167
            retail_22k = base_22k + self.JEWELLERY_PREMIUM_22K
            retail_22k_gst = retail_22k * (1 + GST_RATE/100)
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "source": "live_api",
                "spot_price_per_gram": round(gold_per_gram, 2),
                "gold": {
                    "spot_10g": round(spot_10g, 2),
                    "retail_999_10g": round(retail_999, 2),
                    "rtgs_999_10g": round(rtgs_999, 2),
                    "999_with_gst_10g": round(gst_999, 2),
                    "retail_22k_10g": round(retail_22k, 2),
                    "retail_22k_with_gst_10g": round(retail_22k_gst, 2),
                    "per_gram": {
                        "999_spot": round(gold_per_gram, 2),
                        "999_landed": round(gold_per_gram * self.LANDED_MULTIPLIER, 2),
                        "22k_spot": round(gold_per_gram * 0.9167, 2),
                        "22k_landed": round((gold_per_gram * 0.9167) * self.LANDED_MULTIPLIER, 2),
                    }
                },
                "silver": {
                    "per_gram": round(silver_per_gram, 2),
                    "per_kg": round(silver_per_gram * 1000, 2)
                }
            }
        except (KeyError, IndexError, ValueError) as e:
            logger.error(f"Error parsing goldprice response: {e}")
            raise
    
    def _read_cache_safe(self) -> Optional[Dict]:
        """Safely read cache file with file locking"""
        if not self.CACHE_FILE.exists():
            return None
        
        try:
            with open(self.CACHE_FILE, 'r') as f:
                # Acquire shared lock for reading
                fcntl.flock(f, fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                    return data
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        except (json.JSONDecodeError, OSError, IOError) as e:
            logger.warning(f"Error reading cache: {e}")
            return None
    
    def _write_cache_safe(self, data: Dict) -> bool:
        """Safely write to cache file with file locking"""
        try:
            # Write to temporary file first
            temp_file = self.CACHE_FILE.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            
            # Atomic rename
            temp_file.replace(self.CACHE_FILE)
            return True
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
            return False
    
    def _is_cache_valid(self, cached_data: Dict) -> bool:
        """Check if cached data is still valid"""
        try:
            cache_timestamp = datetime.fromisoformat(cached_data.get('timestamp', '2000-01-01'))
            return datetime.now() - cache_timestamp < timedelta(seconds=self.CACHE_TTL)
        except (ValueError, TypeError):
            return False
    
    def _fetch_from_api(self, endpoint_config: Dict) -> Optional[Dict]:
        """Fetch gold price from a specific API endpoint and return complete data"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
                'Accept': 'application/json',
            }

            # Add custom headers if provided
            if 'headers' in endpoint_config:
                headers.update(endpoint_config['headers'])
            
            params = endpoint_config.get('params', {})
            
            logger.info(f"Trying {endpoint_config['name']} API...")
            response = requests.get(
                endpoint_config['url'],
                headers=headers,
                params=params,
                timeout=15
            )
            
            # Check if response is valid
            if response.status_code != 200:
                logger.warning(f"{endpoint_config['name']} returned status {response.status_code}")
                return None
            
            # Try to parse JSON
            try:
                data = response.json()
            except json.JSONDecodeError:
                logger.warning(f"{endpoint_config['name']} returned invalid JSON")
                return None
            
            # Parse using the endpoint's parser
            output = endpoint_config['parser'](data)
            logger.info(f"Successfully fetched from {endpoint_config['name']}")
            return output
            
        except requests.RequestException as e:
            logger.warning(f"Network error with {endpoint_config['name']}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Error with {endpoint_config['name']}: {e}")
            return None
    
    def get_live_gold_price(self, force_refresh: bool = False) -> Dict:
        """
        Get live gold prices with cache and multiple fallback options
        
        Args:
            force_refresh: If True, bypass cache and fetch fresh data
        """
        # Use lock to prevent multiple simultaneous API calls
        with self._cache_lock:
            # Check cache first (unless force refresh)
            if not force_refresh:
                cached_data = self._read_cache_safe()
                if cached_data and self._is_cache_valid(cached_data):
                    logger.info("Using cached gold prices")
                    return cached_data
            
            # Check if we recently made an API call (rate limiting)
            current_time = time.time()
            if current_time - self._last_api_call < self._min_api_interval:
                logger.info("Rate limiting: using cache or fallback")
                cached_data = self._read_cache_safe()
                if cached_data:
                    # Mark as cached but return it
                    cached_data['source'] = 'cached_rate_limited'
                    return cached_data
                # If no cache, wait a bit
                time.sleep(self._min_api_interval)
            
            # Try multiple APIs
            output = None
            for endpoint in self.API_ENDPOINTS:
                result = self._fetch_from_api(endpoint)
                if result:
                    output = result
                    self._last_api_call = time.time()
                    break
            
            # If all APIs fail, use fallback calculation
            if output is None:
                logger.warning("All APIs failed, using fallback calculation")
                return self._calculate_fallback_prices()
            
            # Save to cache
            self._write_cache_safe(output)
            
            return output
    
    def _calculate_fallback_prices(self) -> Dict:
        """Calculate fallback prices when APIs fail"""
        logger.warning("Using fallback gold prices")
        
        # Try to get last cached price
        cached_data = self._read_cache_safe()
        if cached_data:
            # Mark as fallback
            cached_data['source'] = 'cached_fallback'
            cached_data['timestamp'] = datetime.utcnow().isoformat()
            return cached_data
        
        # Hardcoded fallback prices (based on recent averages)
        gold_per_gram = 7010.4176  # Conservative estimate
        
        # Calculate based on fallback
        spot_10g = gold_per_gram * 10
        landed_10g = spot_10g * self.LANDED_MULTIPLIER
        
        retail_999 = landed_10g + self.RETAIL_SPREAD
        rtgs_999 = landed_10g - self.RTGS_DISCOUNT
        gst_999 = rtgs_999 * (1 + GST_RATE/100)
        
        base_22k = landed_10g * 0.9167
        retail_22k = base_22k + self.JEWELLERY_PREMIUM_22K
        retail_22k_gst = retail_22k * (1 + GST_RATE/100)
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "source": "hardcoded_fallback",
            "spot_price_per_gram": gold_per_gram,
            "gold": {
                "spot_10g": round(spot_10g, 2),
                "retail_999_10g": round(retail_999, 2),
                "rtgs_999_10g": round(rtgs_999, 2),
                "999_with_gst_10g": round(gst_999, 2),
                "retail_22k_10g": round(retail_22k, 2),
                "retail_22k_with_gst_10g": round(retail_22k_gst, 2),
                "per_gram": {
                    "999_spot": gold_per_gram,
                    "999_landed": round(gold_per_gram * self.LANDED_MULTIPLIER, 2),
                    "22k_spot": round(gold_per_gram * 0.9167, 2),
                    "22k_landed": round((gold_per_gram * 0.9167) * self.LANDED_MULTIPLIER, 2),
                }
            },
            "silver": {
                "per_gram": round(gold_per_gram / 80, 2),
                "per_kg": round(gold_per_gram / 80 * 1000, 2)
            }
        }
    
    def calculate_expected_price(self, weight: float, purity: str, 
                                product_type: str = 'jewellery') -> Dict:
        """
        Calculate expected price for gold item
        
        Args:
            weight: Weight in grams
            purity: '24K', '22K', '18K', '14K'
            product_type: 'jewellery' or 'coin'
        """
        # Get current gold prices
        gold_data = self.get_live_gold_price()
        
        # Get purity factor
        purity_factor = PURITY_MAPPING.get(purity, 0.9167)
        
        # Get the appropriate base price based on purity and product type
        if purity == '24K':
            base_price_per_gram = gold_data['gold']['per_gram']['999_landed']
        else:
            # For other purities, use the karat price from API if available, otherwise calculate
            if 'raw_api_response' in gold_data and 'goldByKarat' in gold_data['raw_api_response']:
                # Use the exact karat price from API
                karat_price_10g = float(gold_data['raw_api_response']['goldByKarat'].get(purity, 0))
                if karat_price_10g > 0:
                    base_price_per_gram = karat_price_10g / 10
                else:
                    # Fallback to calculation
                    base_price_per_gram = gold_data['gold']['per_gram']['999_landed'] * purity_factor
            else:
                # Calculate from 24K price
                base_price_per_gram = gold_data['gold']['per_gram']['999_landed'] * purity_factor
        
        # Calculate pure gold value
        gold_value = base_price_per_gram * weight
        
        # Determine making charges key
        if product_type == 'coin':
            charges_key = f'coin_{purity}'
        else:
            charges_key = f'jewellery_{purity}'
        
        # Get making charges percentage
        making_charges_percent = self.MAKING_CHARGES.get(
            charges_key, 
            0.12 if product_type == 'jewellery' else 0.04
        )
        
        # Calculate making charges
        making_charges = gold_value * making_charges_percent
        
        # Calculate GST
        gst_amount = (gold_value + making_charges) * (GST_RATE/100)
        
        # Total expected price
        total_expected = gold_value + making_charges + gst_amount
        
        # Price per gram (all inclusive)
        price_per_gram = total_expected / weight if weight > 0 else 0
        
        return {
            'source': gold_data.get('source', 'unknown'),
            'spot_price_per_gram': gold_data['spot_price_per_gram'],
            'landed_price_per_gram': base_price_per_gram,
            'gold_value': round(gold_value, 2),
            'making_charges': round(making_charges, 2),
            'making_charges_percent': round(making_charges_percent * 100, 2),
            'gst': round(gst_amount, 2),
            'gst_percent': GST_RATE,
            'total_expected': round(total_expected, 2),
            'price_per_gram': round(price_per_gram, 2),
            'purity_factor': purity_factor,
            'product_type': product_type,
            'timestamp': gold_data['timestamp'],
            'data_source': gold_data.get('source', 'live_api')
        }
    
    def calculate_discount_percentage(self, selling_price: float, expected_price: float) -> float:
        """Calculate discount percentage"""
        if expected_price <= 0:
            return 0
        discount = ((expected_price - selling_price) / expected_price) * 100
        return round(max(discount, -100), 2)  # Ensure non-negative
    
    @lru_cache(maxsize=1)
    def get_cached_price_summary(self) -> str:
        """Cached version of price summary - refreshes every 5 minutes"""
        return self.get_price_summary()
    
    def get_price_summary(self) -> str:
        """Get formatted price summary for alerts"""
        gold_data = self.get_live_gold_price()
        gold = gold_data['gold']
        source = gold_data.get('source', 'live_api')
        
        # Source emoji
        source_emoji = "🟢" if source == 'live_api' else "🟡" if source == 'cached_fallback' else "🔴"
        
        summary = f"""
{source_emoji} <b>Current Gold Prices</b> {source_emoji}

<b>24K (999) Gold:</b>
├ Spot (10g): ₹{gold['spot_10g']:,.0f}
├ Landed (10g): ₹{gold['retail_999_10g']:,.0f}
├ With GST (10g): ₹{gold['999_with_gst_10g']:,.0f}
└ Per gram: ₹{gold['per_gram']['999_landed']:,.0f}

<b>22K Gold (Jewellery):</b>
├ Retail (10g): ₹{gold['retail_22k_10g']:,.0f}
├ With GST (10g): ₹{gold['retail_22k_with_gst_10g']:,.0f}
└ Per gram: ₹{gold['per_gram']['22k_landed']:,.0f}

<i>Source: {source.replace('_', ' ').title()}
Last updated: {datetime.fromisoformat(gold_data['timestamp']).strftime('%d %b %Y, %I:%M %p')}</i>
"""
        return summary
    
    def test_api_connectivity(self) -> Dict:
        """Test connectivity to all APIs"""
        results = {}
        
        for endpoint in self.API_ENDPOINTS:
            try:
                logger.info(f"Testing {endpoint['name']}...")
                result = self._fetch_from_api(endpoint)
                results[endpoint['name']] = {
                    'status': 'success' if result else 'failed',
                    'data': result if result else None
                }
            except Exception as e:
                results[endpoint['name']] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        return results
    
    def clear_cache(self) -> None:
        """Manually clear the cache"""
        with self._cache_lock:
            if self.CACHE_FILE.exists():
                try:
                    self.CACHE_FILE.unlink()
                    logger.info("Cache cleared successfully")
                except Exception as e:
                    logger.error(f"Error clearing cache: {e}")
    
    def get_cache_age(self) -> Optional[float]:
        """Get age of cache in seconds"""
        cached_data = self._read_cache_safe()
        if cached_data and 'timestamp' in cached_data:
            try:
                cache_time = datetime.fromisoformat(cached_data['timestamp'])
                return (datetime.now() - cache_time).total_seconds()
            except (ValueError, TypeError):
                return None
        return None