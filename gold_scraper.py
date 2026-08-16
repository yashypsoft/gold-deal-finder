import json
import os
import requests
import time
import re
import random
import urllib.parse
from typing import Dict, List, Optional, Tuple, Any
from config import AJIO_API_URL, SEARCH_PARAMS, REQUEST_DELAY
from price_calculator import GoldPriceCalculator
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

_EXCLUDE_PATTERNS = [
    r'gold[- ]plated',
    r'gold plated',
    r'american diamond',
    r'multi[- ]piece set',
    r'\d+[- ]piece\s+(?:suit|spread|collar|set)',
    r'embellished\s+\d+[- ]piece',
    r'mangalsutra',
    r'necklace',
    r'lobster closure',
    r'stone[- ]studded',
    r'beaded multi',
]
_EXCLUDE_RE = re.compile('|'.join(_EXCLUDE_PATTERNS), re.IGNORECASE)
 
 
def is_real_gold_product(title: str) -> bool:
    """Return False for gold-plated / fashion / non-coin products."""
    return not bool(_EXCLUDE_RE.search(title))

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
    
    # def extract_purity_and_weight(self, title: str) -> Tuple[Optional[str], Optional[float]]:
    #     """
    #     Extract purity and weight from product title
    #     Returns: (purity, weight_in_grams)
    #     """
    #     title_lower = title.lower()
        
    #     # Extract purity
    #     purity = None
    #     purity_patterns = [
    #         (r'24\s*kt|24\s*karat|999|24k', '24K'),
    #         (r'22\s*kt|22\s*karat|916|22k', '22K'),
    #         (r'18\s*kt|18\s*karat|750|18k', '18K'),
    #         (r'14\s*kt|14\s*karat|585|14k', '14K'),
    #     ]
        
    #     for pattern, purity_value in purity_patterns:
    #         if re.search(pattern, title_lower):
    #             purity = purity_value
    #             break
        
    #     # SPECIAL CASE 1: Handle parentheses with plus signs (like "4.5 Gm (0.5 Gm + 2 Gm + 2 Gm)")
    #     # First, check if there's a weight outside parentheses and a sum inside parentheses
    #     parentheses_pattern = r'(\d+\.?\d*)\s*gm?\s*\(([^)]+)\)'
    #     parentheses_match = re.search(parentheses_pattern, title_lower)
        
    #     if parentheses_match:
    #         # We have a pattern like "4.5 Gm (0.5 Gm + 2 Gm + 2 Gm)"
    #         outside_weight = float(parentheses_match.group(1))
    #         inside_content = parentheses_match.group(2)
            
    #         # Extract all weights from inside parentheses
    #         inside_weights = re.findall(r'(\d+\.?\d*)\s*gm?', inside_content)
    #         if inside_weights:
    #             # Sum the inside weights
    #             inside_sum = sum(float(w) for w in inside_weights)
                
    #             # If outside weight matches the sum, return the outside weight
    #             if abs(outside_weight - inside_sum) < 0.01:
    #                 return purity, outside_weight
        
    #     # SPECIAL CASE 2: Handle plus signs (these should ALWAYS be summed)
    #     if '+' in title_lower:
    #         parts = re.split(r'\s*\+\s*', title_lower)
    #         plus_weights = []
            
    #         for part in parts:
    #             weight_match = re.search(r'(\d+\.?\d*)\s*gm?', part)
    #             if weight_match:
    #                 try:
    #                     weight = float(weight_match.group(1))
    #                     if 0.001 <= weight <= 1000:
    #                         plus_weights.append(weight)
    #                 except:
    #                     continue
            
    #         if plus_weights:
    #             # Return the SUM of all weights found with plus signs
    #             total_weight = sum(plus_weights)
    #             return purity, total_weight
        
    #     # SPECIAL CASE 3: Handle hyphen pattern
    #     hyphen_pattern = r'-\s*(\d+\.?\d*)\s*gm?'
    #     hyphen_match = re.search(hyphen_pattern, title_lower)
    #     if hyphen_match:
    #         try:
    #             weight = float(hyphen_match.group(1))
    #             return purity, weight
    #         except:
    #             pass
        
    #     # SPECIAL CASE 4: Handle patterns where weight is explicitly stated first
    #     # (like "4.5 Gm" at the beginning)
    #     first_weight_pattern = r'^.*?(\d+\.?\d*)\s*gm?'
    #     first_match = re.search(first_weight_pattern, title_lower)
        
    #     # Find all weights
    #     weight_patterns = [
    #         r'(\d+\.?\d*)\s*gm\b',
    #         r'(\d+\.?\d*)\s*gram\b',
    #         r'(\d+\.?\d*)\s*g\b(?!\w)',
    #         r'(\d+\.?\d*)\s*grams\b',
    #         r'(\d+\.?\d*)\s*gr\b',
    #     ]
        
    #     all_weights = []
    #     for pattern in weight_patterns:
    #         matches = re.finditer(pattern, title_lower)
    #         for match in matches:
    #             try:
    #                 num_float = float(match.group(1))
    #                 # Filter out purity numbers
    #                 if num_float not in [24, 22, 18, 14, 999, 916, 750, 585]:
    #                     if 0.001 <= num_float <= 1000:
    #                         all_weights.append(num_float)
    #             except:
    #                 continue
        
    #     if all_weights:
    #         # Check if all weights are the same
    #         if all(w == all_weights[0] for w in all_weights):
    #             # All weights are identical, return that weight
    #             return purity, all_weights[0]
    #         else:
    #             # Different weights, sum them
    #             return purity, sum(all_weights)
        
    #     return purity, None
    def extract_purity_and_weight(self, title: str) -> Tuple[Optional[str], Optional[float]]:
        """
        Extract purity and weight from a gold product title.
        Returns: (purity, weight_in_grams)
    
        Purity can be None for items labelled 'Pure Gold' without explicit karat.
        Weight can be None if no weight info is present in the title.
        """
        title_lower = title.lower()
    
        # Quick exclusion
        if not is_real_gold_product(title):
            return None, None
    
        # ── PURITY ───────────────────────────────────────────────────────────────
        purity = None
        purity_patterns = [
            (r'24\s*kt|24\s*karat|\b999\b|24k', '24K'),
            (r'22\s*kt|22\s*karat|\b916\b|22k', '22K'),
            (r'18\s*kt|18\s*karat|\b750\b|18k', '18K'),
            (r'14\s*kt|14\s*karat|\b585\b|14k', '14K'),
            (r'\b995\b', '995'),
        ]
        for pattern, purity_value in purity_patterns:
            if re.search(pattern, title_lower):
                purity = purity_value
                break
    
        # ── WEIGHT ───────────────────────────────────────────────────────────────
        PURITY_NUMBERS = {24, 22, 18, 14, 999, 916, 750, 585, 995}
    
        def is_valid_weight(n: float) -> bool:
            return n not in PURITY_NUMBERS and 0.001 <= n <= 10_000
    
        # Parentheses resolving (e.g., "(2gm x 3)", "(2gm + 1gm)")
        for paren_content in re.findall(r'\(([^)]+)\)', title_lower):
            # Check if it has a multiplication pattern like "2gm x 3" or "2g * 3"
            mult_match = re.search(r'(\d+\.?\d*)\s*(?:grams?|gms?|gm|gr|g)?\s*(?:x|\*)\s*(\d+)', paren_content)
            if mult_match:
                each_w = float(mult_match.group(1))
                count = int(mult_match.group(2))
                calculated_total = each_w * count
                
                # Check for a matching outside weight
                title_without_paren = re.sub(r'\([^)]+\)', ' ', title_lower)
                outside_weights = []
                for w_match in re.finditer(r'(\d+\.?\d*)\s*(?:grams?|gms?|gm|gr|g(?!\w))\b', title_without_paren):
                    w = float(w_match.group(1))
                    if is_valid_weight(w):
                        outside_weights.append(w)
                
                for ow in outside_weights:
                    if abs(ow - calculated_total) < 0.01:
                        return purity, ow
                
                if is_valid_weight(calculated_total):
                    return purity, calculated_total
    
            # Check if it has an addition pattern like "2gm + 1gm"
            if '+' in paren_content:
                inside_weights = [float(w) for w in re.findall(r'(\d+\.?\d*)\s*(?:grams?|gms?|gm|gr|g(?!\w))\b', paren_content)]
                if inside_weights:
                    calculated_total = sum(inside_weights)
                    title_without_paren = re.sub(r'\([^)]+\)', ' ', title_lower)
                    outside_weights = []
                    for w_match in re.finditer(r'(\d+\.?\d*)\s*(?:grams?|gms?|gm|gr|g(?!\w))\b', title_without_paren):
                        w = float(w_match.group(1))
                        if is_valid_weight(w):
                            outside_weights.append(w)
                    
                    for ow in outside_weights:
                        if abs(ow - calculated_total) < 0.01:
                            return purity, ow
                    
                    if is_valid_weight(calculated_total):
                        return purity, calculated_total
    
        # Check for multiplication pattern outside parentheses (e.g. "2gm x 3")
        mult_match = re.search(r'(\d+\.?\d*)\s*(?:grams?|gms?|gm|gr|g)?\s*(?:x|\*)\s*(\d+)', title_lower)
        if mult_match:
            each_w = float(mult_match.group(1))
            count = int(mult_match.group(2))
            calculated_total = each_w * count
            
            span = mult_match.span()
            title_stripped = title_lower[:span[0]] + " " + title_lower[span[1]:]
            other_weights = []
            for w_match in re.finditer(r'(\d+\.?\d*)\s*(?:grams?|gms?|gm|gr|g(?!\w))\b', title_stripped):
                w = float(w_match.group(1))
                if is_valid_weight(w):
                    other_weights.append(w)
            
            for ow in other_weights:
                if abs(ow - calculated_total) < 0.01:
                    return purity, ow
            
            if is_valid_weight(calculated_total):
                return purity, calculated_total
    
        # CASE 2: Plus sums outside parentheses (e.g., "1gm + 1gm")
        if '+' in title_lower:
            parts = re.split(r'\s*\+\s*', title_lower)
            plus_weights = []
            for part in parts:
                m = re.search(r'(\d+\.?\d*)\s*(?:grams?|gms?|gm|gr|g(?!\w))\b', part)
                if m:
                    w = float(m.group(1))
                    if is_valid_weight(w):
                        plus_weights.append(w)
            if plus_weights:
                return purity, sum(plus_weights)
    
        # CASE 3: Hyphen before weight "Coin-1gm" "Coin- 0.500 gm"
        hyphen_match = re.search(r'-\s*(\d+\.?\d*)\s*(?:grams?|gms?|gm|gr|g(?!\w))\b', title_lower)
        if hyphen_match:
            w = float(hyphen_match.group(1))
            if is_valid_weight(w):
                return purity, w
    
        # CASE 4: Milligrams "100 Mg"
        mg_match = re.search(r'(\d+\.?\d*)\s*mg\b', title_lower)
        if mg_match:
            w_mg = float(mg_match.group(1))
            if 0.001 <= w_mg <= 10_000:
                return purity, round(w_mg / 1000, 6)
    
        # CASE 5: General patterns
        weight_patterns = [
            r'(\d+\.?\d*)\s*(?:grams?|gms?|gm|gr)\b',   # "1 Gms", "5 Gram", "0.5 gm"
            r'(\d+\.?\d*)\s*g(?!\w)',                      # "1G", "0.3g", "0.25G"
        ]
        all_weights = []
        seen_pos: set = set()
        for pat in weight_patterns:
            for m in re.finditer(pat, title_lower):
                if m.start() in seen_pos:
                    continue
                try:
                    w = float(m.group(1))
                    if is_valid_weight(w):
                        all_weights.append(w)
                        seen_pos.add(m.start())
                except ValueError:
                    continue
    
        if all_weights:
            # If we have multiple different weights, return the first one as it is the total weight
            return purity, all_weights[0]
    
        return purity, None
    
    
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
        print("🔄 Scraping AJIO...")
        products = []

        headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'referer': 'https://www.ajio.com/search/?text=gold%20coin',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        try:
            from curl_cffi import requests as cffi_requests
            session = cffi_requests.Session(impersonate='chrome120')
            # Warm up session on search landing page to get Akamai cookies
            session.get('https://www.ajio.com/search/?text=gold%20coin', headers=headers, timeout=12)
        except Exception as e:
            print(f"cffi session init warning: {e}")
            session = requests.Session()

        def fetch_page(page: int):
            params = {
                'fields': 'SITE',
                'currentPage': page,
                'pageSize': 45,
                'format': 'json',
                'query': 'gold coin:relevance',
                'gridDensity': '3'
            }

            try:
                r = session.get(
                    AJIO_API_URL,
                    params=params,
                    headers=headers,
                    timeout=12
                )

                if r.status_code != 200:
                    print(f"Page {page} failed: {r.status_code}")
                    return []

                data = r.json()
                page_products = []

                for p in data.get("products", []):
                    parsed = self._parse_ajio_product(p)
                    if parsed:
                        page_products.append(parsed)

                print(f"Page {page}: {len(page_products)} valid")
                return page_products

            except Exception as e:
                print(f"Page {page} error: {e}")
                return []

        # Run sequential or threadpool requests using the warmed session
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = [ex.submit(fetch_page, p) for p in range(0, 12)]

            for f in as_completed(futures):
                products.extend(f.result())

        print(f"✅ AJIO total: {len(products)}")
        return products
    
    def _parse_ajio_product(self, product: Dict) -> Optional[Dict]:
        """Parse AJIO product data"""
        try:
            title = product.get('name', '')
            description = product.get('description', '')
            
            # Skip non-gold products
            # if 'gold' not in title.lower() and 'gold' not in description.lower():
            #     print('Skipping non-gold product    :', title)
            #     return None

            if 'silver' in title.lower():
                # print('Skipping silver product    :', title)
                return None
            
            # Skip out of stock items
            fnl = product.get('fnlColorVariantData', {})
            if product.get('inStock') is False or fnl.get('outOfStock') is True or product.get('stockStatus') == 'OUT_OF_STOCK':
                return None
            
            # Extract purity and weight
            purity, weight = self.extract_purity_and_weight(title)
            
            if not purity or not weight:
                # print(product)
                print('AJIO>Skipping invalid purity/weight product :', title)
                return None
            
            # Skip very small items
            if weight < 0.3:
                print('Skipping <0.3 product    :', title)
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
                print('Skipping <1000 price product    :', title)
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
        print("🔄 Scraping Myntra...")
        products = []

        def fetch_page(page: int):
            session, base_headers = self.create_myntra_session()

            params = {
                "rows": 50,
                "o": (49 * (page - 1)) + 1,
                "pincode": "384315"
            }

            api_headers = {
                "User-Agent": base_headers["User-Agent"],
                # "Accept": "application/json",
                "referer": "https://www.myntra.com/gold-coin",
                "x-meta-app": "channel=web",
                "x-myntraweb": "Yes",
                "x-requested-with": "browser"
            }

            try:
                r = session.get(
                    "https://www.myntra.com/gateway/v4/search/gold-coin",
                    params=params,
                    headers=api_headers,
                    timeout=20
                )

                if r.status_code != 200:
                    return []
                # print(f"Page {page} response:")
                # print(r.status_code)
                # print(r.text)  # Print first 200 characters of response text
                data = r.json()
                page_products = []

                for p in data.get("products", []):
                    parsed = self._parse_myntra_product(p)
                    if parsed:
                        page_products.append(parsed)

                print(f"Page {page}: {len(page_products)} valid")
                return page_products

            except Exception as e:
                print(f"Page {page} error: {e}")
                return []

        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = [ex.submit(fetch_page, p) for p in range(1, 13)]

            for f in as_completed(futures):
                products.extend(f.result())

        print(f"✅ Myntra total: {len(products)}")
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
                print('Skipping Myntra price product    :', title)
                return None
            
            # Skip non-gold products
            # if 'gold' not in title.lower():
            #     print('Skipping not gold product    :', title)
            #     return None
        
            if 'silver' in title.lower():
                # print('Skipping silver  product    :', title)
                return None
            
            # Skip out of stock items
            if product.get('outOfStock') is True or product.get('inStock') is False or product.get('inventory', 1) <= 0:
                return None
            
            # Extract purity and weight
            purity, weight = self.extract_purity_and_weight(title)
            
            if not purity or not weight:
                # print(product);
                print('Myntra>Skipping invalid purity/weight product    :', title)
                return None
            
            # Skip very small items
            if weight < 0.3:
                print('Skipping very small weight < 0.3 product    :', title)
                return None
            
            # Determine product type from title
            product_type = self.determine_product_type(title)
            is_jewellery = (product_type == 'jewellery')
            
            # Extract price - handle different formats
            price_data = product.get('price')
            selling_price, original_price = self._extract_myntra_price(price_data)
            
            # Skip if price is too low
            if selling_price < 1000:
                print('Skipping very small price <1000 product    :', title)
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

    def scrape_candere(self) -> List[Dict]:
        print("🔄 Scraping Candere / Kalyan Jewellers...")
        products = []
        headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest',
            'referer': 'https://www.candere.com/tsearch/?q=Gold+Coin'
        }

        def fetch_page(page: int):
            url = f'https://www.candere.com/tsearch/?q=Gold+Coin&p={page}&is_scroll=1'
            try:
                r = requests.get(url, headers=headers, timeout=15)
                if r.status_code != 200:
                    return []
                html = r.json().get('categoryProducts', '')
                if not html:
                    return []

                blocks = html.split('class="item product product-item"')
                if len(blocks) <= 1:
                    blocks = html.split('class=\\"item product product-item\\"')

                page_products = []
                for b in blocks[1:]:
                    opts_match = re.search(r"data-options='([^']+)'", b)
                    if not opts_match:
                        opts_match = re.search(r'data-options="([^"]+)"', b)
                    if not opts_match:
                        continue

                    try:
                        data = json.loads(opts_match.group(1).replace('&quot;', '"'))
                    except Exception:
                        continue

                    title = data.get('name', '')
                    if not title or not is_real_gold_product(title):
                        continue

                    if 'silver' in title.lower():
                        continue

                    # Skip out of stock
                    if 'out of stock' in b.lower() or 'out-of-stock' in b.lower() or data.get('is_in_stock') == 0 or data.get('is_salable') is False:
                        continue

                    purity, weight = self.extract_purity_and_weight(title)
                    if not purity or not weight or weight < 0.3:
                        continue

                    selling_price = float(data.get('price', 0) or 0)
                    if selling_price < 1000:
                        continue

                    product_type = self.determine_product_type(title)
                    is_jewellery = (product_type == 'jewellery')

                    expected_price_info = self.price_calculator.calculate_expected_price(weight, purity, is_jewellery)
                    expected_price = expected_price_info['total_expected']
                    discount_percent = self.price_calculator.calculate_discount_percentage(selling_price, expected_price)
                    price_per_gram = selling_price / weight

                    img_match = re.search(r'data-src=\"([^\"]+)\"', b)
                    if not img_match:
                        img_match = re.search(r'src=\"([^\"]+)\"', b)
                    img_url = img_match.group(1) if img_match else ''
                    if img_url:
                        img_url = img_url.replace('&amp;', '&')

                    landing_url = data.get('url', '')

                    page_products.append({
                        'source': 'Candere',
                        'title': title,
                        'weight_grams': weight,
                        'purity': purity,
                        'product_type': product_type,
                        'is_jewellery': is_jewellery,
                        'selling_price': selling_price,
                        'original_price': selling_price,
                        'expected_price': round(expected_price, 2),
                        'discount_percent': discount_percent,
                        'price_per_gram': round(price_per_gram, 2),
                        'url': landing_url,
                        'image_url': img_url,
                        'brand': data.get('brand', 'Kalyan/Candere'),
                        'spot_price': expected_price_info['spot_price_per_gram'],
                        'making_charges_percent': expected_price_info['making_charges_percent'],
                        'gst_percent': expected_price_info['gst_percent'],
                        'timestamp': datetime.now().isoformat()
                    })

                return page_products
            except Exception as e:
                print(f"Candere Page {page} error: {e}")
                return []

        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = [ex.submit(fetch_page, p) for p in range(1, 10)]
            for f in as_completed(futures):
                products.extend(f.result())

        print(f"✅ Candere total: {len(products)}")
        return products

    def scrape_bhima(self) -> List[Dict]:
        print("🔄 Scraping Bhima Gold...")
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        search_terms = ['gold+coin', 'gold+bar', '24k', '22k', 'coin']
        unique_map = {}

        def fetch_term(term: str):
            term_products = []
            for page in range(1, 6):
                url = f'https://prod-apis.bhimagold.com/api/app/product/products?stateStock=INSTOCK&sortBy=&searchTerm[]={term}&pageNumber={page}&country=en-IN'
                try:
                    r = requests.get(url, headers=headers, timeout=12)
                    if r.status_code != 200:
                        break
                    data = r.json().get('data', {})
                    pl = data.get('productList', [])
                    if not pl:
                        break

                    for p in pl:
                        title = p.get('title', '')
                        if not title or not is_real_gold_product(title):
                            continue
                        if 'silver' in title.lower():
                            continue

                        purity, weight = self.extract_purity_and_weight(title)
                        if not purity or not weight or weight < 0.3:
                            continue

                        raw_price = float(p.get('converted_special_price', 0) or 0)
                        if raw_price <= 0:
                            continue
                        selling_price = raw_price / 100.0 if raw_price > 100000 else raw_price
                        if selling_price < 1000:
                            continue

                        product_type = self.determine_product_type(title)
                        is_jewellery = (product_type == 'jewellery')

                        expected_price_info = self.price_calculator.calculate_expected_price(weight, purity, is_jewellery)
                        expected_price = expected_price_info['total_expected']
                        discount_percent = self.price_calculator.calculate_discount_percentage(selling_price, expected_price)
                        price_per_gram = selling_price / weight

                        slug = p.get('slug', '')
                        landing_url = f"https://www.bhimagold.com/product/{slug}" if slug else "https://www.bhimagold.com"
                        img_url = p.get('image', '')

                        term_products.append({
                            'source': 'Bhima Gold',
                            'title': title,
                            'weight_grams': weight,
                            'purity': purity,
                            'product_type': product_type,
                            'is_jewellery': is_jewellery,
                            'selling_price': selling_price,
                            'original_price': selling_price,
                            'expected_price': round(expected_price, 2),
                            'discount_percent': discount_percent,
                            'price_per_gram': round(price_per_gram, 2),
                            'url': landing_url,
                            'image_url': img_url,
                            'brand': 'Bhima Gold',
                            'spot_price': expected_price_info['spot_price_per_gram'],
                            'making_charges_percent': expected_price_info['making_charges_percent'],
                            'gst_percent': expected_price_info['gst_percent'],
                            'timestamp': datetime.now().isoformat()
                        })
                except Exception as e:
                    print(f"Bhima Gold error term {term} page {page}: {e}")
                    break
            return term_products

        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = [ex.submit(fetch_term, term) for term in search_terms]
            for f in as_completed(futures):
                for item in f.result():
                    if item['url'] not in unique_map:
                        unique_map[item['url']] = item

        products = list(unique_map.values())
        print(f"✅ Bhima Gold total: {len(products)}")
        return products

    def scrape_tanishq(self) -> List[Dict]:
        print("🔄 Scraping Tanishq (Titan)...")
        products = []
        seen_urls = set()

        try:
            from curl_cffi import requests as c_requests
            session = c_requests.Session(impersonate='chrome120')
        except Exception:
            session = requests.Session()

        try:
            url = "https://www.tanishq.co.in/on/demandware.store/Sites-Tanishq-Site/en_IN/Search-UpdateGrid?cgid=tq-gold-coins&start=0&sz=100"
            r = session.get(url, timeout=12)
            if r.status_code == 200 and r.text:
                html = r.text
                tiles = html.split('data-productpositioninplp=')
                if len(tiles) <= 1:
                    tiles = html.split('class="col-6 col-sm-4')
                if len(tiles) <= 1:
                    tiles = html.split('class="product-tile"')

                for tile in tiles[1:]:
                    if 'out of stock' in tile.lower() or 'plp-notify-me-text' in tile.lower() or 'data-availabilitystatus="out of stock"' in tile.lower():
                        continue
                    m1 = re.search(r'class=\"link[^\"]*\"[^\>]*title=\"([^\"]+)\"', tile)
                    m2 = re.search(r'class=\"pdp-link[^\"]*\"[^\>]*>\s*<a[^\>]*>([^<]+)</a>', tile)
                    m3 = re.search(r'title=\"([^\"]+)\"', tile)
                    raw_title = ''
                    if m1 and m1.group(1):
                        raw_title = m1.group(1).strip()
                    elif m2 and m2.group(1):
                        raw_title = m2.group(1).strip()
                    elif m3 and m3.group(1):
                        raw_title = m3.group(1).strip()

                    title = re.sub(r'<[^>]+>', '', raw_title).strip()
                    title = ' '.join(title.split())
                    if not title or 'silver' in title.lower() or not is_real_gold_product(title):
                        continue

                    p_match = re.search(r'&quot;price&quot;:\s*([\d.]+)', tile) or re.search(r'\"price\":\s*([\d.]+)', tile) or re.search(r'class=\"sales[^\"]*\"[^\>]*>[^₹]*₹?\s*([\d,]+(?:\.\d+)?)', tile) or re.search(r'₹\s*([\d,]+(?:\.\d+)?)', tile)
                    if not p_match:
                        continue
                    selling_price = float(p_match.group(1).replace(',', ''))
                    if selling_price < 1000:
                        continue

                    purity, weight = self.extract_purity_and_weight(title)
                    if not purity or not weight or weight < 0.3:
                        continue

                    product_type = self.determine_product_type(title)
                    is_jewellery = (product_type == 'jewellery')

                    expected_price_info = self.price_calculator.calculate_expected_price(weight, purity, is_jewellery)
                    expected_price = expected_price_info['total_expected']
                    discount_percent = self.price_calculator.calculate_discount_percentage(selling_price, expected_price)

                    u_match = re.search(r'href=\"([^\"]+)\"', tile)
                    landing_url = u_match.group(1) if u_match else 'https://www.tanishq.co.in/shop/gold-coin'
                    if not landing_url.startswith('http'):
                        landing_url = f"https://www.tanishq.co.in{landing_url}"
                    key = (title, landing_url)
                    if key in seen_urls:
                        continue
                    seen_urls.add(key)

                    i_match = re.search(r'src=\"([^\"]+)\"', tile) or re.search(r'data-src=\"([^\"]+)\"', tile)
                    img_url = i_match.group(1) if i_match else ''
                    if img_url.startswith('//'):
                        img_url = 'https:' + img_url

                    products.append({
                        'source': 'Tanishq',
                        'title': title,
                        'weight_grams': weight,
                        'purity': purity,
                        'product_type': product_type,
                        'is_jewellery': is_jewellery,
                        'selling_price': selling_price,
                        'original_price': selling_price,
                        'expected_price': round(expected_price, 2),
                        'discount_percent': discount_percent,
                        'price_per_gram': round(selling_price / weight, 2),
                        'url': landing_url,
                        'image_url': img_url,
                        'brand': 'Tanishq',
                        'spot_price': expected_price_info['spot_price_per_gram'],
                        'making_charges_percent': expected_price_info['making_charges_percent'],
                        'gst_percent': expected_price_info['gst_percent'],
                        'timestamp': datetime.now().isoformat()
                    })
        except Exception as e:
            print(f"Tanishq scraping error: {e}")

        print(f"✅ Tanishq total: {len(products)}")
        return products

    def scrape_mmtc(self) -> List[Dict]:
        print("🔄 Scraping MMTC-PAMP...")
        products = []
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36'
        }
        seen_urls = set()
        try:
            session = requests.Session()
            r = session.get('https://www.mmtcpamp.com/shop/gold', headers=headers, timeout=12)
            if r.status_code == 200:
                m = re.search(r'<script id=\"__NEXT_DATA__\"[^>]*>(.*?)</script>', r.text)
                if m:
                    data = json.loads(m.group(1))
                    raw_prods = data.get('props', {}).get('pageProps', {}).get('shopGoldProducts', [])
                    for p in raw_prods:
                        base_name = p.get('name', '')
                        for sku in p.get('skus', []):
                            try:
                                weight_val = float(sku.get('weight', 0))
                                if weight_val < 0.3:
                                    continue

                                # Skip out of stock
                                if sku.get('inStock') is False or sku.get('stockStatus') == 'OUT_OF_STOCK' or sku.get('availableQty', 1) <= 0:
                                    continue
                                selling_price = float(sku.get('postTaxAmount', 0))
                                if selling_price < 1000:
                                    continue
                                original_price = float(sku.get('mrpAmount', selling_price))

                                purity_raw = sku.get('purity', '999.9')
                                purity = '24K' if '999' in str(purity_raw) else '22K'

                                prod_name = sku.get('productName') or f"{base_name} {weight_val}g"
                                slug = sku.get('slug', '')
                                url = f"https://www.mmtcpamp.com/shop/gold/{slug}" if slug else 'https://www.mmtcpamp.com/shop/gold'

                                if url in seen_urls:
                                    continue
                                seen_urls.add(url)

                                images = sku.get('images', [])
                                img_url = images[0].get('src', '') if images else ''

                                p_type = 'coin' if 'coin' in prod_name.lower() else ('bar' if 'bar' in prod_name.lower() else 'jewellery')
                                expected_info = self.price_calculator.calculate_expected_price(weight_val, purity, False)
                                exp_price = expected_info['total_expected']
                                disc = self.price_calculator.calculate_discount_percentage(selling_price, exp_price)

                                products.append({
                                    'source': 'MMTC-PAMP',
                                    'title': prod_name,
                                    'weight_grams': weight_val,
                                    'purity': purity,
                                    'product_type': p_type,
                                    'is_jewellery': False,
                                    'selling_price': selling_price,
                                    'original_price': original_price,
                                    'expected_price': round(exp_price, 2),
                                    'discount_percent': disc,
                                    'price_per_gram': round(selling_price / weight_val, 2),
                                    'url': url,
                                    'image_url': img_url,
                                    'brand': 'MMTC-PAMP',
                                    'spot_price': expected_info['spot_price_per_gram'],
                                    'making_charges_percent': expected_info['making_charges_percent'],
                                    'gst_percent': expected_info['gst_percent'],
                                    'timestamp': datetime.now().isoformat()
                                })
                            except Exception:
                                pass
        except Exception as e:
            print(f"MMTC-PAMP scraping error: {e}")

        print(f"✅ MMTC-PAMP total: {len(products)}")
        return products

    def scrape_josalukkas(self) -> List[Dict]:
        print("🔄 Scraping Jos Alukkas...")
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
            'origin': 'https://www.josalukkasonline.com',
            'referer': 'https://www.josalukkasonline.com/',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36'
        }
        url = 'https://backend.josalukkasonline.com/api/Master/GetAllProductByFilters/'

        products = []
        seen_urls = set()
        page_index = 1

        while True:
            payload = {
                'CategoryName': 'Gold',
                'SubCategoryName': ['Gold Coin'],
                'PageIndex': page_index,
                'PageSize': 24
            }
            try:
                r = requests.post(url, json=payload, headers=headers, timeout=12)
                if r.status_code != 200:
                    break
                data = r.json()
                items = data.get('Data', []) if isinstance(data, dict) else []
                if not items:
                    break

                new_items_on_page = 0
                for p in items:
                    title = p.get('ProductName', '').strip()
                    if not title or not is_real_gold_product(title):
                        continue
                    # Skip out of stock
                    if p.get('Quantity', 0) <= 0 or p.get('IsOutofStock') is True or p.get('StockStatus') == 'Out of Stock':
                        continue
                    selling_price = float(p.get('SellingPrice', 0))
                    if selling_price < 1000:
                        continue
                    discount = float(p.get('Discount', 0))
                    original_price = selling_price + discount

                    purity, weight = self.extract_purity_and_weight(title)
                    if not purity or not weight or weight < 0.3:
                        continue

                    prod_id = p.get('Id')
                    sku = p.get('Sku', '')
                    price_id = p.get('ProductPriceId', '')
                    cat_name = p.get('CategoryName', 'Gold')
                    sub_cat = p.get('SubCategoryName', 'Gold Coin')
                    if isinstance(sub_cat, list):
                        sub_cat = sub_cat[0] if sub_cat else 'Gold Coin'

                    sub_cat_slug = re.sub(r'[^a-zA-Z0-9]+', '-', sub_cat.lower()).strip('-')
                    title_slug = re.sub(r'[^a-zA-Z0-9]+', '-', title).strip('-')
                    p_param = f"{title_slug}-{sku}" if sku else title_slug
                    cs_param = f"{cat_name}_{urllib.parse.quote(str(sub_cat))}"

                    if prod_id and price_id:
                        prod_url = f"https://www.josalukkasonline.com/{sub_cat_slug}/detail/{prod_id}/?P={p_param}&Prd={prod_id}&Pri={price_id}&CS={cs_param}"
                    elif sku:
                        prod_url = f"https://www.josalukkasonline.com/product/{sku}"
                    else:
                        prod_url = 'https://www.josalukkasonline.com/'

                    if prod_url in seen_urls:
                        continue
                    seen_urls.add(prod_url)
                    new_items_on_page += 1

                    img = p.get('ProductImage', '')
                    img_url = f"https://www.josalukkasmedia.com/Media/large_{img}" if img and not img.startswith('http') else img

                    product_type = self.determine_product_type(title)
                    is_jewellery = (product_type == 'jewellery')
                    expected_info = self.price_calculator.calculate_expected_price(weight, purity, is_jewellery)
                    exp_price = expected_info['total_expected']
                    disc = self.price_calculator.calculate_discount_percentage(selling_price, exp_price)

                    products.append({
                        'source': 'Jos Alukkas',
                        'title': title,
                        'weight_grams': weight,
                        'purity': purity,
                        'product_type': product_type,
                        'is_jewellery': is_jewellery,
                        'selling_price': selling_price,
                        'original_price': original_price,
                        'expected_price': round(exp_price, 2),
                        'discount_percent': disc,
                        'price_per_gram': round(selling_price / weight, 2),
                        'url': prod_url,
                        'image_url': img_url,
                        'brand': 'Jos Alukkas',
                        'spot_price': expected_info['spot_price_per_gram'],
                        'making_charges_percent': expected_info['making_charges_percent'],
                        'gst_percent': expected_info['gst_percent'],
                        'timestamp': datetime.now().isoformat()
                    })

                if new_items_on_page == 0 and page_index > 5:
                    break
                page_index += 1
                if page_index > 30:
                    break
            except Exception as e:
                print(f"Jos Alukkas scraping error page {page_index}: {e}")
                break

        print(f"✅ Jos Alukkas total: {len(products)}")
        return products

    def scrape_joyalukkas(self) -> List[Dict]:
        print("🔄 Scraping Joyalukkas Official...")
        products = []
        seen_urls = set()
        headers = {
            'accept': '*/*',
            'content-type': 'application/json',
            'store': 'default',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
            'x-app-version': '0.0.1',
            'x-channel-id': 'WEB',
            'x-device-type': 'Desktop',
            'x-platform': 'WEB'
        }

        query_raw = 'https://www.joyalukkas.in/graphql?query=fragment+AmGiftCardPricesFragment+on+ProductInterface%7B...on+AmGiftCardProduct%7Bam_giftcard_type+...GiftCardPrices+__typename%7D__typename%7Dfragment+GiftCardPrices+on+AmGiftCardProduct%7Bam_allow_open_amount+am_open_amount_min%7Bcurrency+value+__typename%7Dam_open_amount_max%7Bcurrency+value+__typename%7Dam_giftcard_prices%7Bprice_id+attribute_id+value%7Bcurrency+value+default+__typename%7D__typename%7D__typename%7Dquery+GetCategories%28%24id%3AString%21%2C%24pageSize%3AInt%21%2C%24currentPage%3AInt%21%2C%24filters%3AProductAttributeFilterInput%21%2C%24sort%3AProductAttributeSortInput%29%7Bcategories%28filters%3A%7Bcategory_uid%3A%7Bin%3A%5B%24id%5D%7D%7D%29%7Bitems%7Buid+name+path+cms_block_list+meta_description+thumbnail_image+menu_image+image+similar_collection_block+cms_block_position+footer_block_content+cms_block%7Bcontent+identifier+title+__typename%7Dcms_list%7Bcontent+identifier+title+__typename%7D...CategoryFragment+__typename%7D__typename%7Dproducts%28pageSize%3A%24pageSize+currentPage%3A%24currentPage+filter%3A%24filters+sort%3A%24sort%29%7B...ProductsFragment+__typename%7D%7Dfragment+CategoryFragment+on+CategoryTree%7Bid+uid+meta_title+meta_keywords+meta_description+__typename%7Dfragment+ProductsFragment+on+Products%7Bitems%7Bid+uid+name+jas_product_video_url+is_retail_product+on_hover_image+engrave+offer_message+bestseller+new_arrival+ready_to_ship+krishna_leela+special_price+offer_label+occasion_label+secondary_category_label+metal_label+material_label+color_label+...AmGiftCardPricesFragment+price_range%7Bmaximum_price%7Bfinal_price%7Bcurrency+value+__typename%7Dregular_price%7Bcurrency+value+__typename%7Ddiscount%7Bamount_off+percent_off+__typename%7D__typename%7D__typename%7Dsku+small_image%7Burl+__typename%7Dthumbnail%7Burl+__typename%7Dmedia_gallery_entries%7Buid+label+position+disabled+file+types+__typename%7Dstock_status+rating_summary+__typename+url_key+...on+ConfigurableProduct%7Bconfigurable_options%7Battribute_code+attribute_id+uid+label+values%7Bdefault_label+label+store_label+use_default_value+value_index+swatch_data%7B...on+ImageSwatchData%7Bthumbnail+__typename%7Dvalue+__typename%7D__typename%7D__typename%7Dvariants%7Battributes%7Bcode+value_index+__typename%7Dproduct%7Buid+small_image%7Burl+__typename%7Dthumbnail%7Burl+__typename%7Dmedia_gallery_entries%7Buid+label+position+disabled+file+types%7Dprice%7BregularPrice%7Bamount%7Bcurrency+value+__typename%7D__typename%7D__typename%7Dprice_range%7Bmaximum_price%7Bfinal_price%7Bcurrency+value+__typename%7D__typename%7D__typename%7Doffer_label+sku+stock_status+jas_product_video_url+__typename%7D__typename%7D__typename%7D%7Dpage_info%7Btotal_pages+__typename%7Dtotal_count+__typename%7D&operationName=GetCategories&variables=%7B%22currentPage%22%3A'

        for page in range(1, 5):
            url = query_raw + str(page) + '%2C%22id%22%3A%22NTI4%22%2C%22filters%22%3A%7B%22category_uid%22%3A%7B%22eq%22%3A%22NTI4%22%7D%7D%2C%22pageSize%22%3A35%2C%22sort%22%3A%7B%22position%22%3A%22ASC%22%7D%7D'
            try:
                r = requests.get(url, headers=headers, timeout=12)
                if r.status_code != 200:
                    continue
                data = r.json().get('data', {}).get('products', {})
                items = data.get('items', [])
                if not items:
                    break

                for item in items:
                    title = item.get('name', '').strip()
                    if not title or 'silver' in title.lower() or not is_real_gold_product(title):
                        continue

                    if item.get('stock_status') != 'IN_STOCK':
                        continue

                    final_price = item.get('price_range', {}).get('maximum_price', {}).get('final_price', {}).get('value', 0) or 0
                    selling_price = float(final_price)
                    if selling_price < 1000:
                        continue

                    purity, weight = self.extract_purity_and_weight(title)
                    if not purity:
                        sku = item.get('sku', '')
                        purity = '24K' if ('24' in sku or '24k' in title.lower() or '999' in title.lower()) else '22K'

                    if not weight or weight < 0.3:
                        continue

                    product_type = self.determine_product_type(title)
                    is_jewellery = (product_type == 'jewellery')
                    expected_info = self.price_calculator.calculate_expected_price(weight, purity, is_jewellery)
                    expected_price = expected_info['total_expected']
                    discount_percent = self.price_calculator.calculate_discount_percentage(selling_price, expected_price)

                    url_key = item.get('url_key', '')
                    prod_url = f"https://www.joyalukkas.in/{url_key}.html" if url_key else 'https://www.joyalukkas.in/'
                    if prod_url in seen_urls:
                        continue
                    seen_urls.add(prod_url)

                    img_url = item.get('small_image', {}).get('url', '') or item.get('thumbnail', {}).get('url', '')

                    products.append({
                        'source': 'Joyalukkas',
                        'title': title,
                        'weight_grams': weight,
                        'purity': purity,
                        'product_type': product_type,
                        'is_jewellery': is_jewellery,
                        'selling_price': selling_price,
                        'original_price': selling_price,
                        'expected_price': round(expected_price, 2),
                        'discount_percent': discount_percent,
                        'price_per_gram': round(selling_price / weight, 2),
                        'url': prod_url,
                        'image_url': img_url,
                        'brand': 'Joyalukkas',
                        'spot_price': expected_info['spot_price_per_gram'],
                        'making_charges_percent': expected_info['making_charges_percent'],
                        'gst_percent': expected_info['gst_percent'],
                        'timestamp': datetime.now().isoformat()
                    })
            except Exception as e:
                print(f"Joyalukkas error page {page}: {e}")
                break

        print(f"✅ Joyalukkas total: {len(products)}")
        return products

    def scrape_malabar(self) -> List[Dict]:
        print("🔄 Scraping Malabar Gold & Diamonds...")
        products = []
        seen_skus = set()
        headers = {
            'accept': '*/*',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'referer': 'https://www.malabargoldanddiamonds.com/in/pan-india/en/product-list.html?malabar_product_type=126',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36'
        }

        query_prefix = 'https://www.malabargoldanddiamonds.com/graphql-magento?query=query%20products(%20%24filter%3A%20ProductAttributeFilterInput%20%24pageSize%3A%20Int%20%24currentPage%3A%20Int%20%24sort%3A%20ProductAttributeSortInput%20%24search%3A%20String%20%24last_applied_filter%3A%20String%20)%20%7B%20products(%20filter%3A%20%24filter%20pageSize%3A%20%24pageSize%20currentPage%3A%20%24currentPage%20sort%3A%20%24sort%20search%3A%20%24search%20last_applied_filter%3A%20%24last_applied_filter%20)%20%7B%20suggestions%20%7B%20search%20%7D%20aggregations%20%7B%20attribute_code%20count%20label%20options%20%7B%20label%20value%20count%20%7D%20%7D%20items%20%7B%20name%20sku%20default_combination%20...%20on%20BundleProduct%20%7B%20items%20%7B%20uid%20options%20%7B%20uid%20product%20%7B%20sku%20price_breakup%20%7B%20barcode%20variant_code%20selected_options%20%7B%20uid%20label%20code%20value_index%20%7D%20%7D%20%7D%20%7D%20%7D%20%7D%20promotions_label%20__typename%20categories%20%7B%20name%20%7D%20malabar_product_type_label%20id%20design_code%20store_values%20%7B%20store_name%20pickup_timing%20delivery_mode%20%7B%20boss%20ropis%20bopis%20express%20%7D%20%7D%20review_count%20rating_summary%20price_breakup%20%7B%20exp_delivery_date%20metal_charges%20total%20max_price%20barcode%20variant_code%20variant_dam_images%20selected_options%20%7B%20uid%20%7D%20%7D%20popular%20bestseller%20is_new_arrival%20%7D%20total_count%20page_info%20%7B%20page_size%20current_page%20total_pages%20%7D%20%7D%20%7D&variables='

        page = 1
        total_pages = 1
        std_weights = [0.5, 1, 1.5, 2, 3, 4, 5, 8, 10, 20, 50, 100]

        while page <= total_pages:
            vars_dict = {
                'pageSize': 18,
                'currentPage': page,
                'filter': {'malabar_product_type': {'in': ['126']}},
                'last_applied_filter': 'malabar_product_type',
                'sort': {'latitude': '28.56', 'longitude': '77.22'}
            }
            v_str = urllib.parse.quote(json.dumps(vars_dict))
            try:
                r = requests.get(query_prefix + v_str, headers=headers, timeout=12)
                if r.status_code != 200:
                    break
                data = r.json().get('data', {}).get('products', {})
                total_pages = data.get('page_info', {}).get('total_pages', 1)
                items = data.get('items', [])
                if not items:
                    break

                for item in items:
                    raw_title = item.get('name', '').strip()
                    if not raw_title or 'silver' in raw_title.lower() or not is_real_gold_product(raw_title):
                        continue

                    sku = item.get('sku', '')
                    if not sku or sku in seen_skus:
                        continue
                    seen_skus.add(sku)

                    price_info = item.get('price_breakup', {}) or {}
                    total_price = price_info.get('total', 0) or 0
                    selling_price = float(total_price)
                    if selling_price < 1000:
                        continue

                    purity, weight = self.extract_purity_and_weight(raw_title)
                    if not purity:
                        if '24k' in raw_title.lower() or '999' in raw_title.lower():
                            purity = '24K'
                        elif '22k' in raw_title.lower() or '916' in raw_title.lower():
                            purity = '22K'
                        else:
                            purity = '24K'

                    if not weight:
                        rate_per_g = 16600.38 if purity == '24K' else 14939.53
                        est_w = selling_price / rate_per_g
                        weight = min(std_weights, key=lambda w: abs(w - est_w))

                    if not weight or weight < 0.3:
                        continue

                    title = f"{raw_title} ({weight}g)" if f"{weight}g" not in raw_title and f"{weight} g" not in raw_title else raw_title

                    product_type = self.determine_product_type(title)
                    is_jewellery = (product_type == 'jewellery')
                    expected_info = self.price_calculator.calculate_expected_price(weight, purity, is_jewellery)
                    expected_price = expected_info['total_expected']
                    discount_percent = self.price_calculator.calculate_discount_percentage(selling_price, expected_price)

                    dam_images = price_info.get('variant_dam_images', '') or ''
                    img_url = dam_images.split('|')[0] if dam_images else ''

                    prod_url = f"https://www.malabargoldanddiamonds.com/in/pan-india/en/product-list.html?sku={sku}"

                    products.append({
                        'source': 'Malabar Gold',
                        'title': title,
                        'weight_grams': weight,
                        'purity': purity,
                        'product_type': product_type,
                        'is_jewellery': is_jewellery,
                        'selling_price': round(selling_price, 2),
                        'original_price': round(selling_price, 2),
                        'expected_price': round(expected_price, 2),
                        'discount_percent': discount_percent,
                        'price_per_gram': round(selling_price / weight, 2),
                        'url': prod_url,
                        'image_url': img_url,
                        'brand': 'Malabar Gold',
                        'spot_price': expected_info['spot_price_per_gram'],
                        'making_charges_percent': expected_info['making_charges_percent'],
                        'gst_percent': expected_info['gst_percent'],
                        'timestamp': datetime.now().isoformat()
                    })
                page += 1
            except Exception as e:
                print(f"Malabar error page {page}: {e}")
                break

        print(f"✅ Malabar Gold total: {len(products)}")
        return products

    def scrape_all(self) -> List[Dict]:
        with ThreadPoolExecutor(max_workers=18) as ex:
            f1 = ex.submit(self.scrape_ajio)
            f2 = ex.submit(self.scrape_myntra)
            f3 = ex.submit(self.scrape_candere)
            f4 = ex.submit(self.scrape_bhima)
            f5 = ex.submit(self.scrape_tanishq)
            f6 = ex.submit(self.scrape_mmtc)
            f7 = ex.submit(self.scrape_josalukkas)
            f8 = ex.submit(self.scrape_joyalukkas)
            f9 = ex.submit(self.scrape_malabar)

            ajio_products = f1.result()
            myntra_products = f2.result()
            candere_products = f3.result()
            bhima_products = f4.result()
            tanishq_products = f5.result()
            mmtc_products = f6.result()
            josalukkas_products = f7.result()
            joyalukkas_products = f8.result()
            malabar_products = f9.result()

        all_products = ajio_products + myntra_products + candere_products + bhima_products + tanishq_products + mmtc_products + josalukkas_products + joyalukkas_products + malabar_products
        print(f"\n📊 Total products: {len(all_products)}")

        return all_products

    def scrape_all_with_cache(self, force_refresh=False):
        """Scrape all sources with caching"""
        cache_file = "data/latest_scan.json"
        
        # Check cache if not forcing refresh
        if not force_refresh and os.path.exists(cache_file):
            cache_age = time.time() - os.path.getmtime(cache_file)
            if cache_age < 300:  # 5 minutes cache
                with open(cache_file, 'r') as f:
                    return json.load(f)
        
        # Perform fresh scrape
        products = self.scrape_all()
        
        # Save to cache
        with open(cache_file, 'w') as f:
            json.dump(products, f)
        
        return products