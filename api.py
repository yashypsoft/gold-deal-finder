# api.py
import re
from fastapi import FastAPI, Query, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
# from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import os
import glob
from pathlib import Path
import hashlib
import asyncio
import uvicorn
from collections import defaultdict
from fastapi.responses import FileResponse



from gold_scraper import GoldScraper
from price_calculator import GoldPriceCalculator

app = FastAPI(title="Gold Deal Finder - Historical Data Viewer", version="2.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup templates and static files
# templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Ensure directories exist
Path("static").mkdir(exist_ok=True)
Path("data").mkdir(exist_ok=True)
Path("templates").mkdir(exist_ok=True)
Path("cache").mkdir(exist_ok=True)

# Global instances
scraper = GoldScraper()
price_calculator = GoldPriceCalculator()

# Response Models
class ProductResponse(BaseModel):
    source: str
    title: str
    description: Optional[str] = ""
    weight_grams: float
    purity: str
    product_type: str
    is_jewellery: bool
    selling_price: float
    original_price: Optional[float] = 0
    expected_price: float
    discount_percent: float
    price_per_gram: float
    url: str
    image_url: str
    brand: str
    spot_price: float
    making_charges_percent: float
    gst_percent: float
    timestamp: str
    scan_id: Optional[str] = ""

class ScanHistoryResponse(BaseModel):
    scan_id: str
    timestamp: str
    total_products: int
    good_deals: int
    avg_discount: float
    source_breakdown: Dict[str, int]
    file_name: str

class HistoricalStatsResponse(BaseModel):
    total_scans: int
    total_products_ever: int
    total_good_deals: int
    avg_discount_all: float
    best_deal_ever: Optional[Dict[str, Any]]
    scans_by_day: Dict[str, int]
    source_distribution: Dict[str, int]
    purity_distribution: Dict[str, int]

# Cache for API responses
response_cache = {}
CACHE_TTL = 60  # seconds

def get_cache_key(prefix: str, **kwargs) -> str:
    """Generate cache key from parameters"""
    key_str = prefix + json.dumps(kwargs, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()

def get_cached_response(cache_key: str) -> Optional[Any]:
    """Get cached response if valid"""
    if cache_key in response_cache:
        cached_data, timestamp = response_cache[cache_key]
        if datetime.now().timestamp() - timestamp < CACHE_TTL:
            return cached_data
        else:
            del response_cache[cache_key]
    return None

def set_cached_response(cache_key: str, data: Any):
    """Cache response with timestamp"""
    response_cache[cache_key] = (data, datetime.now().timestamp())

# Historical data functions
def get_all_scan_files() -> List[Path]:
    """Get all scan result files sorted by date (newest first)"""
    data_dir = Path("data")
    if not data_dir.exists():
        return []
    
    scan_files = list(data_dir.glob("scan_results_*.json"))
    scan_files.extend(list(data_dir.glob("scan_results_*.json.gz")))
    scan_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return scan_files

def load_scan_file(file_path: Path) -> Dict:
    """Load and parse a scan file"""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            
        # Handle different formats
        if 'products' in data:
            products = data['products']
        elif 'all_products' in data:
            products = data['all_products']
        elif isinstance(data, list):
            products = data
        else:
            products = []
            
        # Extract timestamp from filename or data
        if 'timestamp' in data:
            timestamp = data['timestamp']
        else:
            # Parse from filename: scan_results_20260212_2122.json
            match = re.search(r'(\d{8}_\d{4})', str(file_path))
            if match:
                timestamp = datetime.strptime(match.group(1), '%Y%m%d_%H%M').isoformat()
            else:
                timestamp = datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
        
        # Count good deals
        good_deals = sum(1 for p in products if p.get('discount_percent', 0) >= 10)
        
        # Calculate avg discount
        avg_discount = 0
        if products:
            avg_discount = sum(p.get('discount_percent', 0) for p in products) / len(products)
        
        # Source breakdown
        source_breakdown = {}
        for p in products:
            source = p.get('source', 'Unknown')
            source_breakdown[source] = source_breakdown.get(source, 0) + 1
        
        # Generate scan ID
        scan_id = file_path.stem.replace('scan_results_', '')
        
        return {
            'scan_id': scan_id,
            'timestamp': timestamp,
            'total_products': len(products),
            'good_deals': good_deals,
            'avg_discount': round(avg_discount, 2),
            'source_breakdown': source_breakdown,
            'file_name': file_path.name,
            'products': products
        }
    except Exception as e:
        print(f"Error loading scan file {file_path}: {e}")
        return None

def get_all_historical_products(limit_per_file: int = None) -> List[Dict]:
    """Get all products from all scan files"""
    all_products = []
    scan_files = get_all_scan_files()[:1]  # Limit to last 20 scans for performance
    
    for file_path in scan_files:
        scan_data = load_scan_file(file_path)
        if scan_data and 'products' in scan_data:
            products = scan_data['products']
            # if limit_per_file:
            #     products = products[:limit_per_file]
            
            # Add scan_id to each product
            for p in products:
                p['scan_id'] = scan_data['scan_id']
            all_products.extend(products)
    
    return all_products

def get_historical_stats() -> Dict:
    """Calculate statistics from all historical scans"""
    scan_files = get_all_scan_files()
    
    if not scan_files:
        return {
            'total_scans': 0,
            'total_products_ever': 0,
            'total_good_deals': 0,
            'avg_discount_all': 0,
            'best_deal_ever': None,
            'scans_by_day': {},
            'source_distribution': {},
            'purity_distribution': {}
        }
    
    total_scans = len(scan_files)
    total_products = 0
    total_good_deals = 0
    all_discounts = []
    best_deal = None
    scans_by_day = {}
    source_dist = defaultdict(int)
    purity_dist = defaultdict(int)
    
    for file_path in scan_files[:30]:  # Analyze last 30 scans
        scan_data = load_scan_file(file_path)
        if not scan_data:
            continue
        
        total_products += scan_data['total_products']
        total_good_deals += scan_data['good_deals']
        
        # Day grouping
        date_str = scan_data['timestamp'][:10]
        scans_by_day[date_str] = scans_by_day.get(date_str, 0) + 1
        
        # Analyze products
        for product in scan_data.get('products', []):
            discount = product.get('discount_percent', 0)
            all_discounts.append(discount)
            
            # Track best deal
            if not best_deal or discount > best_deal.get('discount_percent', 0):
                best_deal = {
                    'title': product.get('title', 'Unknown'),
                    'discount': discount,
                    'price': product.get('selling_price', 0),
                    'source': product.get('source', 'Unknown'),
                    'timestamp': product.get('timestamp', ''),
                    'weight': product.get('weight_grams', 0),
                    'purity': product.get('purity', '')
                }
            
            # Distributions
            source = product.get('source', 'Unknown')
            source_dist[source] += 1
            
            purity = product.get('purity', 'Unknown')
            purity_dist[purity] += 1
    
    avg_discount = sum(all_discounts) / len(all_discounts) if all_discounts else 0
    
    return {
        'total_scans': total_scans,
        'total_products_ever': total_products,
        'total_good_deals': total_good_deals,
        'avg_discount_all': round(avg_discount, 2),
        'best_deal_ever': best_deal,
        'scans_by_day': dict(sorted(scans_by_day.items(), reverse=True)[:7]),
        'source_distribution': dict(source_dist),
        'purity_distribution': dict(purity_dist)
    }

# API Endpoints
@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/api/v1/historical/scans", response_model=List[ScanHistoryResponse])
async def get_scan_history(
    limit: int = Query(30, description="Number of scans to return"),
    offset: int = Query(0, description="Skip offset")
):
    """Get list of all historical scans"""
    cache_key = get_cache_key("scans", limit=limit, offset=offset)
    cached = get_cached_response(cache_key)
    if cached:
        return cached
    
    scan_files = get_all_scan_files()
    total_files = len(scan_files)
    
    # Apply pagination
    paginated_files = scan_files[offset:offset + limit]
    
    scans = []
    for file_path in paginated_files:
        scan_data = load_scan_file(file_path)
        if scan_data:
            scans.append(ScanHistoryResponse(
                scan_id=scan_data['scan_id'],
                timestamp=scan_data['timestamp'],
                total_products=scan_data['total_products'],
                good_deals=scan_data['good_deals'],
                avg_discount=scan_data['avg_discount'],
                source_breakdown=scan_data['source_breakdown'],
                file_name=scan_data['file_name']
            ))
    
    set_cached_response(cache_key, scans)
    return scans

@app.get("/api/v1/historical/products")
async def get_historical_products(
    scan_id: Optional[str] = Query(None, description="Filter by specific scan"),
    source: Optional[str] = Query(None, description="Filter by source"),
    purity: Optional[str] = Query(None, description="Filter by purity"),
    min_discount: float = Query(0, description="Minimum discount"),
    max_discount: float = Query(100, description="Maximum discount"),
    search: Optional[str] = Query(None, description="Search in title"),
    limit: int = Query(100, description="Limit results"),
    offset: int = Query(0, description="Skip results"),
    sort_by: str = Query("timestamp", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order")
):
    """Get historical products with filters"""
    cache_key = get_cache_key("historical_products", scan_id=scan_id, source=source, 
                              purity=purity, min_discount=min_discount, max_discount=max_discount,
                              search=search, limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order)
    
    cached = get_cached_response(cache_key)
    if cached:
        return cached
    
    # If specific scan_id is provided, load only that scan
    if scan_id:
        file_path = Path(f"data/scan_results_{scan_id}.json")
        if file_path.exists():
            scan_data = load_scan_file(file_path)
            products = scan_data.get('products', []) if scan_data else []
        else:
            products = []
    else:
        # Load from all scans
        products = get_all_historical_products(limit_per_file=50)  # Limit per file for performance
    # return products
    
    # Apply filters
    filtered_products = products.copy()
    
    if source:
        filtered_products = [p for p in filtered_products if p.get('source') == source]
    
    if purity:
        filtered_products = [p for p in filtered_products if p.get('purity') == purity]
    
    filtered_products = [p for p in filtered_products if 
                        min_discount <= p.get('discount_percent', 0) <= max_discount]
    
    if search:
        search_lower = search.lower()
        filtered_products = [p for p in filtered_products 
                           if search_lower in p.get('title', '').lower() or 
                              search_lower in p.get('brand', '').lower()]
    
    # Sort
    reverse = sort_order.lower() == 'desc'
    if sort_by in ['discount_percent', 'selling_price', 'price_per_gram', 'weight_grams', 'timestamp']:
        filtered_products.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)
    elif sort_by == 'date':
        filtered_products.sort(key=lambda x: x.get('timestamp', ''), reverse=reverse)
    
    # Pagination
    total_count = len(filtered_products)
    paginated_products = filtered_products[offset:offset + limit]
    
    response = {
        'total': total_count,
        'offset': offset,
        'limit': limit,
        'products': paginated_products
    }
    
    set_cached_response(cache_key, response)
    return response

@app.get("/api/v1/historical/stats", response_model=HistoricalStatsResponse)
async def get_historical_stats_endpoint():
    """Get historical statistics"""
    cache_key = get_cache_key("historical_stats")
    cached = get_cached_response(cache_key)
    if cached:
        return cached
    
    stats = get_historical_stats()
    set_cached_response(cache_key, stats)
    return stats

@app.get("/api/v1/historical/scan/{scan_id}")
async def get_specific_scan(scan_id: str):
    """Get details of a specific scan"""
    # Try different file patterns
    patterns = [
        f"data/scan_results_{scan_id}.json",
        f"data/scan_results_{scan_id}.json.gz",
        f"data/{scan_id}.json"
    ]
    
    for pattern in patterns:
        file_path = Path(pattern)
        if file_path.exists():
            scan_data = load_scan_file(file_path)
            if scan_data:
                return scan_data
    
    raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

@app.get("/api/v1/historical/timeline")
async def get_scan_timeline(days: int = 30):
    """Get scan frequency and product counts over time"""
    cache_key = get_cache_key("timeline", days=days)
    cached = get_cached_response(cache_key)
    if cached:
        return cached
    
    scan_files = get_all_scan_files()
    
    # Filter to last N days
    cutoff_date = datetime.now() - timedelta(days=days)
    recent_files = []
    
    for file_path in scan_files:
        file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
        if file_time >= cutoff_date:
            recent_files.append((file_path, file_time))
    
    # Group by date
    timeline = {}
    for file_path, file_time in recent_files:
        date_str = file_time.strftime('%Y-%m-%d')
        hour_str = file_time.strftime('%H:00')
        
        if date_str not in timeline:
            timeline[date_str] = {'total': 0, 'scans': 0, 'products': 0, 'by_hour': {}}
        
        timeline[date_str]['scans'] += 1
        timeline[date_str]['by_hour'][hour_str] = timeline[date_str]['by_hour'].get(hour_str, 0) + 1
        
        scan_data = load_scan_file(file_path)
        if scan_data:
            timeline[date_str]['products'] += scan_data['total_products']
            timeline[date_str]['total'] += 1
    
    response = {
        'days': days,
        'timeline': timeline,
        'total_scans': sum(d['scans'] for d in timeline.values()),
        'total_products': sum(d['products'] for d in timeline.values())
    }
    
    set_cached_response(cache_key, response)
    return response

SCAN_COOLDOWN = timedelta(minutes=30)
last_scan_time: datetime | None = None
scan_lock = asyncio.Lock()

SCAN_COOLDOWN = timedelta(minutes=30)

last_scan_time: datetime | None = None
scan_lock = asyncio.Lock()

@app.get("/api/v1/scan", response_model=Dict)
async def scan_products(background_tasks: BackgroundTasks):
    global last_scan_time, response_cache

    async with scan_lock:
        now = datetime.utcnow()

        # cooldown check
        if last_scan_time and (now - last_scan_time) < SCAN_COOLDOWN:
            remaining = SCAN_COOLDOWN - (now - last_scan_time)
            raise HTTPException(
                status_code=429,
                detail=f"Scan already triggered. Try again in {int(remaining.total_seconds()//60)} min."
            )

        # mark immediately to prevent race
        last_scan_time = now

    try:
        products = scraper.scrape_all()

        timestamp = now.strftime("%Y%m%d_%H%M%S")
        filename = f"data/scan_results_{timestamp}.json"

        scan_data = {
            "timestamp": now.isoformat(),
            "total_products": len(products),
            "products": products,
        }

        background_tasks.add_task(save_results, filename, scan_data)

        response_cache = {}

        return {
            "success": True,
            "message": f"Found {len(products)} gold products",
            "scan_id": timestamp,
            "total_count": len(products),
            "timestamp": now.isoformat(),
        }

    except Exception as e:
        # optional: reset last_scan_time on failure
        # last_scan_time = None
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/spot-price")
async def get_spot_price():
    """Get current spot price of gold"""
    try:
        cache_key = get_cache_key("spot_price")
        cached = get_cached_response(cache_key)
        if cached:
            return cached
        
        spot_price = price_calculator.get_live_gold_price()
        
        set_cached_response(cache_key, spot_price)
        return spot_price
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/products/latest")
async def get_latest_products(limit: int = Query(100, description="Number of products")):
    """Get products from the most recent scan"""
    cache_key = get_cache_key("latest_products", limit=limit)
    cached = get_cached_response(cache_key)
    if cached:
        return cached
    
    scan_files = get_all_scan_files()
    if not scan_files:
        return []
    
    latest_file = scan_files[0]
    scan_data = load_scan_file(latest_file)
    
    products = scan_data.get('products', [])[:limit] if scan_data else []
    
    set_cached_response(cache_key, products)
    return products

@app.post("/api/v1/cache/clear")
async def clear_cache():
    """Clear all response caches"""
    global response_cache
    response_cache = {}
    return {"message": "Cache cleared", "status": "success"}

@app.get("/api/v1/stats/summary")
async def get_summary_stats():
    """Get summary statistics combining live and historical data"""
    live_products = await get_latest_products(limit=500)
    historical_stats = get_historical_stats()
    
    # Calculate live stats
    live_total = len(live_products)
    live_avg_discount = sum(p.get('discount_percent', 0) for p in live_products) / live_total if live_total > 0 else 0
    live_good_deals = sum(1 for p in live_products if p.get('discount_percent', 0) >= 10)
    
    # Source breakdown for live
    live_sources = {}
    for p in live_products:
        source = p.get('source', 'Unknown')
        live_sources[source] = live_sources.get(source, 0) + 1
    
    return {
        'live': {
            'total_products': live_total,
            'avg_discount': round(live_avg_discount, 2),
            'good_deals': live_good_deals,
            'sources': live_sources
        },
        'historical': historical_stats
    }

# Helper functions
def save_results(filename: str, data: Dict):
    """Save scan results to file"""
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2, default=str)

# Health check endpoint
@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'cache_size': len(response_cache),
        'scan_files': len(get_all_scan_files()),
        'version': '2.0.0'
    }

# Initialize data directory with sample data if empty
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    data_dir = Path("data")
    if not data_dir.exists():
        data_dir.mkdir()
    
    # Create sample data if no scans exist
    if len(get_all_scan_files()) == 0:
        print("No scan files found. Creating sample data...")
        from sample_data import create_sample_scans
        create_sample_scans()


@app.on_event("startup")
async def create_sample_data_if_empty():
    """Create sample scan data if no scans exist"""
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    # Check if there are any scan files
    scan_files = list(data_dir.glob("scan_results_*.json"))
    
    if len(scan_files) == 0:
        print("📁 No scan data found. Creating sample data...")
        
        # Create 3 sample scans
        from datetime import datetime, timedelta
        import random
        
        for days_ago in [0, 1, 3, 7, 14]:
            scan_time = datetime.now() - timedelta(days=days_ago)
            timestamp = scan_time.strftime("%Y%m%d_%H%M%S")
            
            products = []
            for i in range(random.randint(20, 40)):
                weight = random.choice([1, 2, 5, 8, 10, 20, 50])
                purity = random.choice(['24K', '22K', '18K'])
                source = random.choice(['AJIO', 'Myntra'])
                brand = random.choice(['Tanishq', 'Kalyan', 'Malabar', 'PC Jeweller', 'Senco'])
                
                base_price = random.randint(5500, 6500)
                selling_price = weight * base_price * random.uniform(0.85, 0.95)
                expected_price = weight * base_price * 1.1
                discount = ((expected_price - selling_price) / expected_price) * 100
                
                product = {
                    'source': source,
                    'title': f"{weight}g {purity} Gold {'Coin' if random.random() > 0.5 else 'Jewellery'} - {brand}",
                    'description': f"Pure {purity} gold product",
                    'weight_grams': weight,
                    'purity': purity,
                    'product_type': 'coin' if random.random() > 0.5 else 'jewellery',
                    'is_jewellery': random.choice([True, False]),
                    'selling_price': round(selling_price, 2),
                    'expected_price': round(expected_price, 2),
                    'discount_percent': round(discount, 2),
                    'price_per_gram': round(selling_price / weight, 2),
                    'url': f"https://www.{source.lower()}.com/product/{i}",
                    'image_url': '',
                    'brand': brand,
                    'spot_price': round(base_price, 2),
                    'making_charges_percent': random.choice([0, 8, 12, 15]),
                    'gst_percent': 3,
                    'timestamp': scan_time.isoformat()
                }
                products.append(product)
            
            scan_data = {
                'timestamp': scan_time.isoformat(),
                'total_products': len(products),
                'products': products
            }
            
            filename = data_dir / f"scan_results_{timestamp}.json"
            with open(filename, 'w') as f:
                json.dump(scan_data, f, indent=2)
            
            print(f"   ✅ Created sample scan: {filename}")
        
        print(f"📊 Created {len(list(data_dir.glob('scan_results_*.json')))} sample scan files")
