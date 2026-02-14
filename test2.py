from curl_cffi import requests
import time

# Use a session to maintain cookies
session = requests.Session(impersonate="chrome120")  # Impersonates Chrome's TLS fingerprint

# First visit main page
session.get("https://www.myntra.com/gold-coin")

# Add delay to appear human
time.sleep(2)

# Now make the API request
response = session.get(
    "https://www.myntra.com/gateway/v4/search/gold%20coin",
    params={
        "rawQuery": "gold coin",
        "rows": 50,
        "o": 99,
        "p": 3
    }
)

print(response.json())