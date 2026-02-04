import json
import time
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from config import GST_RATE, PURITY_MAPPING
import logging

logger = logging.getLogger(__name__)

class GoldPriceCalculator:
    def __init__(self):
        # Multiple API endpoints for redundancy
        self.API_ENDPOINTS = [
            {
                'name': 'goldprice.org',
                'url': 'https://data-asg.goldprice.org/dbXRates/INR',
                'parser': self._parse_goldprice_response
            },
            # {
            #     'name': 'metalpriceapi',
            #     'url': 'https://api.metalpriceapi.com/v1/latest',
            #     'parser': self._parse_metalprice_response,
            #     'params': {'api_key': '', 'base': 'XAU', 'currencies': 'INR'}
            # },
            # {
            #     'name': 'goldapi',
            #     'url': 'https://www.goldapi.io/api/XAU/INR',
            #     'parser': self._parse_goldapi_response,
            #     'headers': {'x-access-token': ''}
            # }
        ]
        
        self.CACHE_FILE = Path("bullion_cache.json")
        self.CACHE_TTL = 300  # 5 minutes cache
        
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

            # 'coin_24K': 0.03,      # 3% for 24K coins/bars
            # 'coin_22K': 0.04,      # 4% for 22K coins
            # 'jewellery_24K': 0.08, # 8% for 24K jewellery
            # 'jewellery_22K': 0.12, # 12% for 22K jewellery
            # 'jewellery_18K': 0.15, # 15% for 18K jewellery
            # 'jewellery_14K': 0.18, # 18% for 14K jewellery
        }
    
    def _parse_goldprice_response(self, response_data: Dict) -> Tuple[float, float]:
        """Parse response from goldprice.org"""
        try:
            item = response_data["items"][0]
            xau = float(item["xauPrice"])  # Gold price per troy ounce in INR
            xag = float(item["xagPrice"])  # Silver price per troy ounce in INR
            return xau, xag
        except (KeyError, IndexError, ValueError) as e:
            logger.error(f"Error parsing goldprice response: {e}")
            raise
    
    def _parse_metalprice_response(self, response_data: Dict) -> Tuple[float, float]:
        """Parse response from metalpriceapi.com"""
        try:
            rates = response_data["rates"]
            # Convert from price per ounce to price per troy ounce
            # metalpriceapi returns price per ounce (28.3495g), not troy ounce (31.1035g)
            price_per_ounce = float(rates["INR"])
            # Convert to troy ounce
            xau = price_per_ounce * (31.1035 / 28.3495)
            # For silver, we'll use a default ratio if not available
            xag = xau / 80  # Approximate gold/silver ratio
            return xau, xag
        except (KeyError, ValueError) as e:
            logger.error(f"Error parsing metalprice response: {e}")
            raise
    
    def _parse_goldapi_response(self, response_data: Dict) -> Tuple[float, float]:
        """Parse response from goldapi.io"""
        try:
            xau = float(response_data["price"])  # Price per troy ounce in INR
            # Goldapi might not return silver price
            xag = xau / 80  # Approximate gold/silver ratio
            return xau, xag
        except (KeyError, ValueError) as e:
            logger.error(f"Error parsing goldapi response: {e}")
            raise
    
    def _fetch_from_api(self, endpoint_config: Dict) -> Optional[Tuple[float, float]]:
        """Fetch gold price from a specific API endpoint"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
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
            xau, xag = endpoint_config['parser'](data)
            logger.info(f"Successfully fetched from {endpoint_config['name']}: {xau:.2f} INR/troy oz")
            return xau, xag
            
        except requests.RequestException as e:
            logger.warning(f"Network error with {endpoint_config['name']}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Error with {endpoint_config['name']}: {e}")
            return None
    
    def get_live_gold_price(self) -> Dict:
        """
        Get live gold prices with cache and multiple fallback options
        """
        # Check cache first
        if self.CACHE_FILE.exists():
            try:
                cache_time = self.CACHE_FILE.stat().st_mtime
                if time.time() - cache_time < self.CACHE_TTL:
                    cached_data = json.loads(self.CACHE_FILE.read_text())
                    # Check if cache is still valid (less than 1 hour old)
                    cache_timestamp = datetime.fromisoformat(cached_data.get('timestamp', '2000-01-01'))
                    if datetime.now() - cache_timestamp < timedelta(hours=1):
                        logger.info("Using cached gold prices")
                        return cached_data
            except Exception as e:
                logger.warning(f"Error reading cache: {e}")
        
        # Try multiple APIs
        xau, xag = None, None
        for endpoint in self.API_ENDPOINTS:
            result = self._fetch_from_api(endpoint)
            if result:
                xau, xag = result
                break
        
        # If all APIs fail, use fallback calculation
        if xau is None:
            logger.warning("All APIs failed, using fallback calculation")
            return self._calculate_fallback_prices()
        
        # Calculate prices
        try:
            gold_per_gram = xau / self.OZ_TO_GRAM
            silver_per_gram = xag / self.OZ_TO_GRAM if xag else gold_per_gram / 80
            
            spot_10g = gold_per_gram * 10
            landed_10g = spot_10g * self.LANDED_MULTIPLIER
            
            # 24K (999) prices for 10g
            retail_999 = landed_10g + self.RETAIL_SPREAD
            rtgs_999 = landed_10g - self.RTGS_DISCOUNT
            gst_999 = rtgs_999 * (1 + GST_RATE/100)
            
            # 22K prices for 10g
            base_22k = landed_10g * 0.9167
            retail_22k = base_22k + self.JEWELLERY_PREMIUM_22K
            retail_22k_gst = retail_22k * (1 + GST_RATE/100)
            
            # Create output structure
            output = {
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
            
            # Save to cache
            try:
                self.CACHE_FILE.write_text(json.dumps(output, indent=2))
                logger.info("Gold prices cached successfully")
            except Exception as e:
                logger.error(f"Error saving cache: {e}")
            
            return output
            
        except Exception as e:
            logger.error(f"Error calculating prices: {e}")
            return self._calculate_fallback_prices()
    
    def _calculate_fallback_prices(self) -> Dict:
        """Calculate fallback prices when APIs fail"""
        logger.warning("Using fallback gold prices")
        
        # Try to get last cached price
        if self.CACHE_FILE.exists():
            try:
                cached = json.loads(self.CACHE_FILE.read_text())
                # Mark as fallback
                cached['source'] = 'cached_fallback'
                cached['timestamp'] = datetime.utcnow().isoformat()
                return cached
            except:
                pass
        
        # Hardcoded fallback prices (based on recent averages)
        gold_per_gram = 5800  # Conservative estimate
        
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
        
        # Base landed price per gram for 24K
        base_price_per_gram = gold_data['gold']['per_gram']['999_landed']
        
        # Calculate pure gold value
        pure_gold_value = base_price_per_gram * weight
        
        # Apply purity
        gold_value = pure_gold_value * purity_factor
        
        # Determine making charges key
        if product_type == 'coin':
            charges_key = f'coin_{purity}'
        else:
            charges_key = f'jewellery_{purity}'
        
        # Get making charges percentage
        # making_charges_percent = self.MAKING_CHARGES.get(
        #     charges_key, 
        #     0.12 if product_type == 'jewellery' else 0.04
        # )
        making_charges_percent = 0
        # Calculate making charges
        making_charges = gold_value * making_charges_percent
        
        # Calculate GST
        gst_amount = (gold_value + making_charges) * (GST_RATE/100)
        
        # Total expected price
        total_expected = gold_value # + making_charges + gst_amount
        
        # Price per gram (all inclusive)
        price_per_gram = total_expected / weight if weight > 0 else 0
        # print('Base Gold value gram:',gold_value)
        # print('Base price per gram:',price_per_gram)
        # Add jewellery premium for 22K jewellery
        if product_type == 'jewellery' and purity in ['22K', '18K', '14K']:
            jewellery_premium = self.JEWELLERY_PREMIUM_22K * (weight/10) * purity_factor
            total_expected += jewellery_premium
            making_charges += jewellery_premium
            price_per_gram = total_expected / weight if weight > 0 else 0
        # print('Calculating expected price:',total_expected)
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
        return round(max(discount, -5), 2)  # Ensure non-negative
    
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
                    'price': result[0] if result else None
                }
            except Exception as e:
                results[endpoint['name']] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        return results