import os
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gold_deal_finder.log'),
        # logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

load_dotenv()

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', 'YOUR_CHAT_ID')

# If you have API keys for premium services
METALPRICE_API_KEY = os.getenv('METALPRICE_API_KEY', '')
GOLDAPI_TOKEN = os.getenv('GOLDAPI_TOKEN', '')

# API Endpoints
AJIO_API_URL = "https://www.ajio.com/api/search"
MYNTRA_API_URL = "https://www.myntra.com/gateway/v4/search"

# GST Rate (for India)
GST_RATE = 0  # 3% GST on gold

# Purity to karat mapping
PURITY_MAPPING = {
    '24K': 0.999,
    '22K': 0.9167,
    '18K': 0.750,
    '14K': 0.585,
    '916': 0.9167,
    '999': 0.999,
    '750': 0.750,
    '585': 0.585
}

# Search Parameters
SEARCH_PARAMS = {
    'ajio': {
        'query': 'gold coin:relevance',
        'text': 'gold coin',
        'pageSize': 45,
        'format': 'json',
        'fields': 'SITE',
        'pincode': '384315',
        'state': 'GUJARAT',
        'city': 'MAHESANA'
    },
    'myntra': {
        'rows': 50,
        'pincode': '384345',
        'plaEnabled': 'true'
    }
}

# Alert Thresholds
MIN_DISCOUNT_PERCENTAGE = -1
MIN_WEIGHT = 0.5
MAX_PRICE_PER_GRAM = {
    '24K': 18000,
    '22K': 17000,
    '18K': 16000,
    '14K': 15000,
    'default': 14000
}

# Price calculation constants
OZ_TO_GRAM = 31.1035
LANDED_MULTIPLIER = 1.11
RETAIL_SPREAD = 700
RTGS_DISCOUNT = 600
JEWELLERY_PREMIUM_22K = 1200

# Cache settings
CACHE_TTL = 300  # 5 minutes
CACHE_FILE = "bullion_cache.json"

# Local app runtime
APP_HOST = os.getenv('APP_HOST', '0.0.0.0')
APP_PORT = int(os.getenv('APP_PORT', '8000'))
APP_RELOAD = os.getenv('APP_RELOAD', 'true').lower() == 'true'
AUTO_OPEN_BROWSER = os.getenv('AUTO_OPEN_BROWSER', 'false').lower() == 'true'

# Scan behavior
SCAN_COOLDOWN_MINUTES = int(os.getenv('SCAN_COOLDOWN_MINUTES', '0'))
HISTORICAL_SCAN_LIMIT_DEFAULT = int(os.getenv('HISTORICAL_SCAN_LIMIT_DEFAULT', '5'))
MAX_HISTORICAL_SCAN_LIMIT = int(os.getenv('MAX_HISTORICAL_SCAN_LIMIT', '25'))

# Scraping settings
REQUEST_DELAY = 2  # seconds between requests
MAX_PAGES = 3
REQUEST_TIMEOUT = 30

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 5

# Database Configuration (PostgreSQL with SQLite fallback)
DATABASE_URL = os.getenv('DATABASE_URL', '')

# SaaS Subscription Plans & Pricing (INR)
SUBSCRIPTION_PLANS = {
    'free': {
        'id': 'free',
        'name': 'Free Explorer',
        'price_inr': 0,
        'duration_days': 0,
        'features': [
            '15-Minute Delayed Deal Alerts',
            'Standard Deals (3-5% discount)',
            'Top 2 SGB Tranches',
            'Community Support'
        ],
        'is_featured': False,
        'delay_seconds': 900
    },
    'pro_monthly': {
        'id': 'pro_monthly',
        'name': 'Gold Deal Pro (Monthly)',
        'price_inr': 599,
        'duration_days': 30,
        'features': [
            '0-Second Instant VIP Alerts',
            'Sub-Spot Bullion Deals (Negative Premium)',
            'Direct 1-Click Cart Deeplinks with Coupons',
            'Credit Card Stacking Calculator',
            'Full 60+ SGB Screener with Live YTM',
            '0% Making Charge Jewellery Glitches'
        ],
        'is_featured': True,
        'delay_seconds': 0
    },
    'festive_pass': {
        'id': 'festive_pass',
        'name': 'Festive Gold Rush Pass (45 Days)',
        'price_inr': 899,
        'duration_days': 45,
        'features': [
            'All Pro Features for 45 Days',
            'Dhanteras & Diwali Rush Sniper',
            'High-Speed Restock Notifications',
            'Full 100% Credit towards Annual Pro'
        ],
        'is_featured': False,
        'delay_seconds': 0
    },
    'pro_annual': {
        'id': 'pro_annual',
        'name': 'Gold Deal Pro (Annual)',
        'price_inr': 4999,
        'duration_days': 365,
        'features': [
            'Everything in Pro (Save 30%)',
            'Priority Sub-Second Notification Queue',
            'Personalized Card Alert Triggers',
            'Wedding & Gifting Gold Advisory'
        ],
        'is_featured': False,
        'delay_seconds': 0
    },
    'trader_monthly': {
        'id': 'trader_monthly',
        'name': 'HNI & Bullion Trader',
        'price_inr': 1499,
        'duration_days': 30,
        'features': [
            'Zero-Latency WebSocket Stream',
            'Sub-Spot & Reverse Arbitrage Buyback Calculator',
            'NSE/BSE SGB Depth & Block Trade Screener',
            'Restock SMS / IVR Call Trigger (Urgent)',
            'Unlimited Custom Webhook Integrations'
        ],
        'is_featured': False,
        'delay_seconds': 0
    }
}

# Free vs Pro delay settings
FREE_TIER_DELAY_SECONDS = 900  # 15 minutes

# Arbitrage Engine Thresholds
SUB_SPOT_MIN_DISCOUNT_PCT = 0.5  # At least 0.5% below wholesale spot
LOW_MAKING_CHARGE_THRESHOLD_PCT = 4.0  # Making charge under 4% is a deal
OUT_OF_STOCK_WATCH_SKUS = []

# Payment Gateway (Razorpay)
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', 'rzp_test_placeholder')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', 'placeholder_secret')
RAZORPAY_WEBHOOK_SECRET = os.getenv('RAZORPAY_WEBHOOK_SECRET', '')

# Telegram VIP Channel / Bot
TELEGRAM_VIP_CHAT_ID = os.getenv('TELEGRAM_VIP_CHAT_ID', TELEGRAM_CHAT_ID)
TELEGRAM_FREE_CHAT_ID = os.getenv('TELEGRAM_FREE_CHAT_ID', TELEGRAM_CHAT_ID)

# WhatsApp Cloud API Configuration
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN', '')
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID', '')
WHATSAPP_TEMPLATE_NAME = os.getenv('WHATSAPP_TEMPLATE_NAME', 'gold_arbitrage_alert')

# Reverse Arbitrage & Bullion Buyback Constants
BUYBACK_MELT_DEDUCTION_24K = 0.005  # 0.5% standard melting/assaying for 999 bars/coins
BUYBACK_MELT_DEDUCTION_22K = 0.010  # 1.0% standard melting/refining for 916 jewellery
BUYBACK_CASH_LIMIT_INR = 199999     # Section 269ST Income Tax cash limit
DEFAULT_TURNOVER_DAYS = 5           # Estimated e-commerce delivery-to-liquidation cycle

