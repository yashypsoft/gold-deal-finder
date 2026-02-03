import requests
import time
import re
import random
from typing import Dict, List, Optional, Tuple, Any
from config import AJIO_API_URL, SEARCH_PARAMS, REQUEST_DELAY
from price_calculator import GoldPriceCalculator
from datetime import datetime

class GoldScraper:
    def __init__(self):
        self.price_calculator = GoldPriceCalculator()
        self.ajio_headers = {
            'authority': 'www.ajio.com',
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en;q=0.9',
            'referer': 'https://www.ajio.com/',
            'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
        }
    
    def create_myntra_session(self):
        """Create and prepare a session for Myntra with proper cookies"""
        s = requests.Session()
        
        base_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-GB,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Connection": "keep-alive",
        }
        
        # First visit to generate cookies
        s.get("https://www.myntra.com", headers=base_headers, timeout=15)
        time.sleep(random.uniform(1, 2))
        
        # Visit gold coins page
        s.get("https://www.myntra.com/gold-coin", headers=base_headers, timeout=15)
        time.sleep(random.uniform(1, 2))
        
        # Set pincode cookie
        s.cookies.set(
            "mynt-ulc",
            "pincode:384345|addressId:",
            domain=".myntra.com"
        )
        
        return s, base_headers
    
    def extract_purity_and_weight(self, title: str) -> Tuple[Optional[str], Optional[float]]:
        """
        Extract purity and weight from product title
        Returns: (purity, weight_in_grams)
        """
        title_lower = title.lower()
        
        # Extract purity
        purity = None
        purity_patterns = [
            (r'24\s*kt|24\s*karat|999\s*(\D|$)', '24K'),
            (r'22\s*kt|22\s*karat|916\s*(\D|$)', '22K'),
            (r'18\s*kt|18\s*karat|750\s*(\D|$)', '18K'),
            (r'14\s*kt|14\s*karat|585\s*(\D|$)', '14K'),
            (r'24k', '24K'),
            (r'22k', '22K'),
            (r'18k', '18K'),
            (r'14k', '14K'),
        ]
        
        for pattern, purity_value in purity_patterns:
            if re.search(pattern, title_lower):
                purity = purity_value
                break
        
        # Extract weight
        weight = None
        weight_patterns = [
            r'(\d+\.?\d*)\s*gm\b',
            r'(\d+\.?\d*)\s*gram\b',
            r'(\d+\.?\d*)\s*g\b',
            r'(\d+\.?\d*)\s*grams\b',
            r'(\d+\.?\d*)\s*gr\b',
            r'(\d+)\s*gm',  # For whole numbers
        ]
        
        for pattern in weight_patterns:
            match = re.search(pattern, title_lower)
            if match:
                try:
                    weight = float(match.group(1))
                    break
                except:
                    continue
        
        # If weight not found in patterns, try to find any number that could be weight
        if weight is None:
            numbers = re.findall(r'\d+\.?\d*', title)
            for num in numbers:
                try:
                    num_float = float(num)
                    # Check if it's a plausible weight (0.1g to 1000g)
                    if 0.1 <= num_float <= 1000:
                        weight = num_float
                        break
                except:
                    continue
        
        return purity, weight
    
    def determine_product_type(self, title: str, description: str = "") -> str:
        """
        Determine if product is jewellery or coin/bar
        """
        text = (title + " " + description).lower()
        
        coin_keywords = ['coin', 'sovereign', 'bar', 'biscuit', 'ingot', 'bullion', 'investment']
        jewellery_keywords = ['chain', 'pendant', 'ring', 'bangle', 'bracelet', 'earring', 
                             'necklace', 'mangalsutra', 'jewellery', 'jewelry', 'ornament']
        
        coin_count = sum(1 for keyword in coin_keywords if keyword in text)
        jewellery_count = sum(1 for keyword in jewellery_keywords if keyword in text)
        
        if coin_count > jewellery_count:
            return 'coin'
        else:
            return 'jewellery'
    
    def scrape_ajio(self) -> List[Dict]:
        """Scrape gold products from AJIO"""
        products = []
        params = SEARCH_PARAMS['ajio'].copy()
        
        try:
            print("🔄 Scraping AJIO...")
            
            for page in range(1, 6):  # Scrape first 3 pages
                params['currentPage'] = page
                
                response = requests.get(AJIO_API_URL, params=params, headers=self.ajio_headers, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    for product in data.get('products', []):
                        product_info = self._parse_ajio_product(product)
                        if product_info:
                            products.append(product_info)
                    
                    print(f"   Page {page}: Found {len(data.get('products', []))} products")
                else:
                    print(f"   Page {page}: Failed with status {response.status_code}")
                
                time.sleep(REQUEST_DELAY)  # Respectful delay
            
            print(f"✅ AJIO: Found {len(products)} valid gold products")
            
        except Exception as e:
            print(f"❌ Error scraping AJIO: {e}")
        
        return products
    
    def _parse_ajio_product(self, product: Dict) -> Optional[Dict]:
        """Parse AJIO product data"""
        try:
            title = product.get('name', '')
            description = product.get('description', '')
            
            # Skip non-gold products
            if 'gold' not in title.lower() and 'gold' not in description.lower():
                return None

            if 'silver' in title.lower():
                return None
            
            # Extract purity and weight
            purity, weight = self.extract_purity_and_weight(title)
            
            if not purity or not weight:
                return None
            
            # Skip very small items
            if weight < 0.3:
                return None
            
            # Determine product type
            product_type = self.determine_product_type(title, description)
            is_jewellery = (product_type == 'jewellery')
            
            # Extract price
            price_data = product.get('price', {})
            selling_price2 = price_data.get('value', 0)

            price_data = product.get('offerPrice', {})
            selling_price = price_data.get('value', 0)
            selling_price = selling_price if selling_price > 0 else selling_price2
            
            # Skip if price is too low
            if selling_price < 1000:
                return None
            
            # Calculate expected price
            expected_price_info = self.price_calculator.calculate_expected_price(
                weight, purity, is_jewellery
            )
            # print(weight, purity, is_jewellery)
            # print(expected_price_info);
            expected_price = expected_price_info['total_expected']
            
            # Calculate discount
            discount_percent = self.price_calculator.calculate_discount_percentage(
                selling_price, expected_price
            )
            
            # Calculate price per gram
            price_per_gram = selling_price / weight
            # print({
            #     'source': 'AJIO',
            #     'title': title,
            #     'description': description[:200] if description else '',
            #     'weight_grams': weight,
            #     'purity': purity,
            #     'product_type': product_type,
            #     'is_jewellery': is_jewellery,
            #     'selling_price': selling_price,
            #     'expected_price': round(expected_price, 2),
            #     'discount_percent': discount_percent,
            #     'price_per_gram': round(price_per_gram, 2),
            #     'url': f"https://www.ajio.com{product.get('url', '')}",
            #     'image_url': product.get('images', [{}])[0].get('url', '') if product.get('images') else '',
            #     'brand': product.get('fnlColorVariantData', {}).get('brandName', 'Unknown'),
            #     'spot_price': expected_price_info['spot_price_per_gram'],
            #     'making_charges_percent': expected_price_info['making_charges_percent'],
            #     'gst_percent': expected_price_info['gst_percent'],
            #     'timestamp': datetime.now().isoformat()
            # })
            return {
                'source': 'AJIO',
                'title': title,
                'description': description[:200] if description else '',
                'weight_grams': weight,
                'purity': purity,
                'product_type': product_type,
                'is_jewellery': is_jewellery,
                'selling_price': selling_price,
                'expected_price': round(expected_price, 2),
                'discount_percent': discount_percent,
                'price_per_gram': round(price_per_gram, 2),
                'url': f"https://www.ajio.com{product.get('url', '')}",
                'image_url': product.get('images', [{}])[0].get('url', '') if product.get('images') else '',
                'brand': product.get('fnlColorVariantData', {}).get('brandName', 'Unknown'),
                'spot_price': expected_price_info['spot_price_per_gram'],
                'making_charges_percent': expected_price_info['making_charges_percent'],
                'gst_percent': expected_price_info['gst_percent'],
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error parsing AJIO product: {e}")
            return None
    
    def scrape_myntra(self) -> List[Dict]:
        """Scrape gold products from Myntra using proper session"""
        products = []
        
        try:
            print("🔄 Scraping Myntra...")
            
            # Create session with proper cookies
            session, base_headers = self.create_myntra_session()
            
            for page in range(1, 5):  # Scrape first 3 pages
                params = {
                    'rows': 50,
                    'o': (49*(page-1))+1,
                    'pincode': '384315'
                }
                
                # Myntra requires specific headers for API
                api_headers = {
                    "User-Agent": base_headers["User-Agent"],
                    "Accept": "application/json",
                    "referer": "https://www.myntra.com/gold-coin",
                    "x-meta-app": "channel=web",
                    "x-myntraweb": "Yes",
                    "x-requested-with": "browser"
                }
                
                response = session.get(
                    "https://www.myntra.com/gateway/v4/search/gold-coin",
                    params=params,
                    headers=api_headers,
                    timeout=20
                )
                
                if response.status_code == 200:
                    data = response.json()
                    products_data = data.get('products', [])
                    
                    # if page == 1 and products_data:
                    #     print(f"DEBUG: First product keys: {list(products_data[0].keys())}")
                    #     print(f"DEBUG: First product price type: {type(products_data[0].get('price'))}")
                    #     print(f"DEBUG: First product price value: {products_data[0].get('price')}")
                    
                    for product in products_data:
                        product_info = self._parse_myntra_product(product)
                        if product_info:
                            products.append(product_info)
                    
                    print(f"   Page {page}: Found {len(products_data)} products")
                    
                    # Stop if no more products
                    if len(products_data) < 40:
                        break
                else:
                    print(f"   Page {page}: Failed with status {response.status_code}")
                    print(f"   Response: {response.text[:500]}")
                
                time.sleep(REQUEST_DELAY + random.uniform(1, 2))
            
            print(f"✅ Myntra: Found {len(products)} valid gold products")
            
        except Exception as e:
            print(f"❌ Error scraping Myntra: {e}")
            import traceback
            traceback.print_exc()
        
        return products
    
    def _extract_myntra_price(self, price_data: Any) -> Tuple[float, float]:
        """
        Extract prices from Myntra product data
        Returns: (selling_price, original_price)
        """
        try:
            # If price_data is a dictionary
            if isinstance(price_data, dict):
                selling_price = price_data.get('discountedPrice', 0)
                original_price = price_data.get('mrp', selling_price)
                return float(selling_price), float(original_price)
            
            # If price_data is a single integer/float
            elif isinstance(price_data, (int, float)):
                return float(price_data), float(price_data)
            
            # If price_data is a string
            elif isinstance(price_data, str):
                try:
                    price = float(price_data)
                    return price, price
                except:
                    return 0, 0
            
            else:
                return 0, 0
                
        except Exception as e:
            print(f"Error extracting Myntra price: {e}")
            return 0, 0
    
    def _parse_myntra_product(self, product: Dict) -> Optional[Dict]:
        """Parse Myntra product data with improved price handling"""
        try:
            title = product.get('productName', '')
            
            # Skip if no title
            if not title:
                return None
            
            # Skip non-gold products
            if 'gold' not in title.lower():
                return None
        
            if 'silver' in title.lower():
                return None
            
            # Extract purity and weight
            purity, weight = self.extract_purity_and_weight(title)
            
            if not purity or not weight:
                return None
            
            # Skip very small items
            if weight < 0.3:
                return None
            
            # Determine product type from title
            product_type = self.determine_product_type(title)
            is_jewellery = (product_type == 'jewellery')
            
            # Extract price - handle different formats
            price_data = product.get('price')
            selling_price, original_price = self._extract_myntra_price(price_data)
            
            # Skip if price is too low
            if selling_price < 1000:
                return None
            
            # Calculate expected price
            expected_price_info = self.price_calculator.calculate_expected_price(
                weight, purity, is_jewellery
            )
            expected_price = expected_price_info['total_expected']
            # print(expected_price,weight, purity, is_jewellery)
            # print(expected_price_info)
            # return {}
            # Calculate discount
            discount_percent = self.price_calculator.calculate_discount_percentage(
                selling_price, expected_price
            )
            
            # Calculate price per gram
            price_per_gram = selling_price / weight
            
            # Get other product details
            landing_url = product.get('landingPageUrl', '')
            if landing_url and not landing_url.startswith('http'):
                landing_url = f"https://www.myntra.com/{landing_url}"
            
            # print({
            #     'source': 'Myntra',
            #     'title': title,
            #     'weight_grams': weight,
            #     'purity': purity,
            #     'product_type': product_type,
            #     'is_jewellery': is_jewellery,
            #     'selling_price': selling_price,
            #     'original_price': original_price,
            #     'expected_price': round(expected_price, 2),
            #     'discount_percent': discount_percent,
            #     'price_per_gram': round(price_per_gram, 2),
            #     'url': landing_url,
            #     'image_url': product.get('searchImage', ''),
            #     'brand': product.get('brandName', 'Unknown'),
            #     'spot_price': expected_price_info['spot_price_per_gram'],
            #     'making_charges_percent': expected_price_info['making_charges_percent'],
            #     'gst_percent': expected_price_info['gst_percent'],
            #     'timestamp': datetime.now().isoformat()
            # })

            return {
                'source': 'Myntra',
                'title': title,
                'weight_grams': weight,
                'purity': purity,
                'product_type': product_type,
                'is_jewellery': is_jewellery,
                'selling_price': selling_price,
                'original_price': original_price,
                'expected_price': round(expected_price, 2),
                'discount_percent': discount_percent,
                'price_per_gram': round(price_per_gram, 2),
                'url': landing_url,
                'image_url': product.get('searchImage', ''),
                'brand': product.get('brandName', 'Unknown'),
                'spot_price': expected_price_info['spot_price_per_gram'],
                'making_charges_percent': expected_price_info['making_charges_percent'],
                'gst_percent': expected_price_info['gst_percent'],
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error parsing Myntra product '{product.get('productName', 'Unknown')}': {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def scrape_all(self) -> List[Dict]:
        """Scrape all sources and return filtered products"""
        all_products = []
        
        # Scrape both sources
        ajio_products = self.scrape_ajio()
        myntra_products = self.scrape_myntra()
        
        all_products.extend(ajio_products)
        all_products.extend(myntra_products)
        
        print(f"\n📊 Total products found: {len(all_products)}")
        
        return all_products