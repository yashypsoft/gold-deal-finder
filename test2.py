from curl_cffi import requests
import time
import random

# Don't use proxies - use your own IP
session = requests.Session(impersonate="chrome120")

# Add more realistic headers
session.headers.update({
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
})

try:
    # First visit - get cookies
    print("Step 1: Visiting homepage...")
    home_response = session.get("https://www.myntra.com/", timeout=10)
    print(f"Homepage status: {home_response.status_code}")
    time.sleep(random.uniform(3, 5))
    
    # Second visit - search page
    print("Step 2: Visiting search page...")
    search_response = session.get("https://www.myntra.com/gold-coin", timeout=10)
    print(f"Search page status: {search_response.status_code}")
    time.sleep(random.uniform(4, 6))
    
    # Now make the API request
    print("Step 3: Making API request...")
    response = session.get(
        "https://www.myntra.com/gateway/v4/search/gold%20coin",
        params={
            "rawQuery": "gold coin",
            "rows": 50,
            "o": 0,  # Start from beginning
            "p": 1   # Page 1
        },
        timeout=15
    )
    
    print(f"API status: {response.status_code}")
    
    if response.status_code == 200:
        print("Success!")
        print(response.text[:500])
    else:
        print(f"Failed with status {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"Error: {e}")