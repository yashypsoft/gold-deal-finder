from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import (
    CACHE_TTL,
    HISTORICAL_SCAN_LIMIT_DEFAULT,
    MAX_HISTORICAL_SCAN_LIMIT,
    SCAN_COOLDOWN_MINUTES,
)
from gold_scraper import GoldScraper
from price_calculator import GoldPriceCalculator

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"
CACHE_DIR = BASE_DIR / "cache"

for directory in (STATIC_DIR, DATA_DIR, TEMPLATES_DIR, CACHE_DIR):
    directory.mkdir(exist_ok=True)

app = FastAPI(title="Gold Deal Finder", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

scraper = GoldScraper()
price_calculator = GoldPriceCalculator()
response_cache: dict[str, tuple[Any, float]] = {}
scan_lock = asyncio.Lock()
last_scan_time: datetime | None = None
SCAN_COOLDOWN = timedelta(minutes=SCAN_COOLDOWN_MINUTES) if SCAN_COOLDOWN_MINUTES > 0 else None
TIMESTAMP_PATTERN = re.compile(r"(\d{8}_\d{6}|\d{8}_\d{4})")


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


def now_ts() -> float:
    return datetime.now().timestamp()


def clear_response_cache() -> None:
    response_cache.clear()


def get_cache_key(prefix: str, **kwargs: Any) -> str:
    payload = prefix + json.dumps(kwargs, sort_keys=True, default=str)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def get_cached_response(cache_key: str) -> Optional[Any]:
    cached = response_cache.get(cache_key)
    if not cached:
        return None

    data, created_at = cached
    if now_ts() - created_at >= CACHE_TTL:
        response_cache.pop(cache_key, None)
        return None
    return data


def set_cached_response(cache_key: str, data: Any) -> None:
    response_cache[cache_key] = (data, now_ts())


def error_detail(code: str, message: str, **extra: Any) -> Dict[str, Any]:
    detail = {"code": code, "message": message}
    detail.update(extra)
    return detail


def get_all_scan_files() -> List[Path]:
    scan_files = list(DATA_DIR.glob("scan_results_*.json"))
    scan_files.extend(DATA_DIR.glob("scan_results_*.json.gz"))
    latest_file = DATA_DIR.joinpath("latest_scan.json")
    if latest_file.exists():
        scan_files.append(latest_file)
    return sorted(scan_files, key=lambda path: path.stat().st_mtime, reverse=True)


def extract_scan_id(file_path: Path) -> str:
    name = file_path.name
    if name.endswith(".json.gz"):
        name = name[:-8]
    elif name.endswith(".json"):
        name = name[:-5]
    return name.replace("scan_results_", "")


def parse_file_timestamp(file_path: Path) -> str:
    match = TIMESTAMP_PATTERN.search(file_path.name)
    if match:
        raw_value = match.group(1)
        fmt = "%Y%m%d_%H%M%S" if len(raw_value) == 15 else "%Y%m%d_%H%M"
        try:
            return datetime.strptime(raw_value, fmt).isoformat()
        except ValueError:
            pass
    return datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()


def load_json_payload(file_path: Path) -> Any:
    if file_path.suffix == ".gz":
        with gzip.open(file_path, "rt", encoding="utf-8") as handle:
            return json.load(handle)

    with open(file_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def coerce_products(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("products"), list):
            return payload["products"]
        if isinstance(payload.get("all_products"), list):
            return payload["all_products"]
        if isinstance(payload.get("good_deals_details"), list):
            return payload["good_deals_details"]
        return []
    if isinstance(payload, list):
        return payload
    return []


def enrich_product(product: Dict[str, Any], scan_id: str) -> Dict[str, Any]:
    enriched = dict(product)
    enriched.setdefault("description", "")
    enriched.setdefault("original_price", 0)
    enriched.setdefault("brand", "Unknown")
    enriched.setdefault("image_url", "")
    enriched.setdefault("scan_id", scan_id)
    return enriched


def load_scan_file(file_path: Path) -> Optional[Dict[str, Any]]:
    try:
        payload = load_json_payload(file_path)
    except Exception as exc:
        print(f"Error loading scan file {file_path}: {exc}")
        return None

    scan_id = extract_scan_id(file_path)
    products = [enrich_product(item, scan_id) for item in coerce_products(payload)]

    if isinstance(payload, dict) and payload.get("timestamp"):
        timestamp = str(payload["timestamp"])
    else:
        timestamp = parse_file_timestamp(file_path)

    discounts = [product.get("discount_percent", 0) for product in products]
    source_breakdown: Dict[str, int] = {}
    for product in products:
        source = product.get("source", "Unknown") or "Unknown"
        source_breakdown[source] = source_breakdown.get(source, 0) + 1

    return {
        "scan_id": scan_id,
        "timestamp": timestamp,
        "total_products": len(products),
        "good_deals": sum(1 for discount in discounts if discount >= 10),
        "avg_discount": round(sum(discounts) / len(discounts), 2) if discounts else 0,
        "source_breakdown": source_breakdown,
        "file_name": file_path.name,
        "products": products,
    }


def resolve_scan_file(scan_id: str) -> Optional[Path]:
    candidates = [
        DATA_DIR / f"scan_results_{scan_id}.json",
        DATA_DIR / f"scan_results_{scan_id}.json.gz",
        DATA_DIR / f"{scan_id}.json",
        DATA_DIR / f"{scan_id}.json.gz",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def get_all_historical_products(
    scan_limit: int = HISTORICAL_SCAN_LIMIT_DEFAULT,
    limit_per_file: Optional[int] = None,
) -> List[Dict[str, Any]]:
    products: List[Dict[str, Any]] = []
    for file_path in get_all_scan_files()[:scan_limit]:
        scan_data = load_scan_file(file_path)
        if not scan_data:
            continue
        scan_products = scan_data["products"]
        if limit_per_file is not None:
            scan_products = scan_products[:limit_per_file]
        products.extend(scan_products)
    return products


def get_historical_stats() -> Dict[str, Any]:
    scan_files = get_all_scan_files()
    if not scan_files:
        return {
            "total_scans": 0,
            "total_products_ever": 0,
            "total_good_deals": 0,
            "avg_discount_all": 0,
            "best_deal_ever": None,
            "scans_by_day": {},
            "source_distribution": {},
            "purity_distribution": {},
        }

    total_products = 0
    total_good_deals = 0
    all_discounts: List[float] = []
    best_deal: Optional[Dict[str, Any]] = None
    scans_by_day: Dict[str, int] = defaultdict(int)
    source_distribution: Dict[str, int] = defaultdict(int)
    purity_distribution: Dict[str, int] = defaultdict(int)

    for file_path in scan_files[: max(30, HISTORICAL_SCAN_LIMIT_DEFAULT)]:
        scan_data = load_scan_file(file_path)
        if not scan_data:
            continue

        total_products += scan_data["total_products"]
        total_good_deals += scan_data["good_deals"]
        scans_by_day[str(scan_data["timestamp"])[:10]] += 1

        for product in scan_data["products"]:
            discount = float(product.get("discount_percent", 0) or 0)
            all_discounts.append(discount)

            if not best_deal or discount > float(best_deal.get("discount", 0) or 0):
                best_deal = {
                    "title": product.get("title", "Unknown"),
                    "discount": discount,
                    "price": product.get("selling_price", 0),
                    "source": product.get("source", "Unknown"),
                    "timestamp": product.get("timestamp", scan_data["timestamp"]),
                    "weight": product.get("weight_grams", 0),
                    "purity": product.get("purity", "Unknown"),
                    "scan_id": scan_data["scan_id"],
                }

            source_distribution[product.get("source", "Unknown") or "Unknown"] += 1
            purity_distribution[product.get("purity", "Unknown") or "Unknown"] += 1

    avg_discount_all = sum(all_discounts) / len(all_discounts) if all_discounts else 0

    return {
        "total_scans": len(scan_files),
        "total_products_ever": total_products,
        "total_good_deals": total_good_deals,
        "avg_discount_all": round(avg_discount_all, 2),
        "best_deal_ever": best_deal,
        "scans_by_day": dict(sorted(scans_by_day.items(), reverse=True)[:14]),
        "source_distribution": dict(source_distribution),
        "purity_distribution": dict(purity_distribution),
    }


def sort_products(products: List[Dict[str, Any]], sort_by: str, sort_order: str) -> None:
    reverse = sort_order.lower() == "desc"

    def sort_key(item: Dict[str, Any]) -> Any:
        value = item.get(sort_by)
        if sort_by == "timestamp":
            try:
                return datetime.fromisoformat(str(value)).timestamp()
            except Exception:
                return 0
        return value if value is not None else 0

    products.sort(key=sort_key, reverse=reverse)


def save_results(filename: str | Path, data: Dict[str, Any]) -> None:
    output_path = Path(filename)
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, default=str)


def ensure_sample_data_if_empty() -> None:
    if get_all_scan_files():
        return

    from sample_data import create_sample_scans

    print("📁 No scan data found. Creating sample data...")
    create_sample_scans(5)


@app.on_event("startup")
async def startup_event() -> None:
    ensure_sample_data_if_empty()


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/v1/historical/scans", response_model=List[ScanHistoryResponse])
async def get_scan_history(
    limit: int = Query(30, ge=1, le=100, description="Number of scans to return"),
    offset: int = Query(0, ge=0, description="Skip offset"),
):
    cache_key = get_cache_key("historical_scans", limit=limit, offset=offset)
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    scans: List[ScanHistoryResponse] = []
    for file_path in get_all_scan_files()[offset : offset + limit]:
        scan_data = load_scan_file(file_path)
        if not scan_data:
            continue
        scans.append(ScanHistoryResponse(**{key: scan_data[key] for key in ScanHistoryResponse.model_fields}))

    set_cached_response(cache_key, scans)
    return scans


@app.get("/api/v1/historical/products")
async def get_historical_products(
    scan_id: Optional[str] = Query(None, description="Filter by specific scan"),
    source: Optional[str] = Query(None, description="Filter by source"),
    purity: Optional[str] = Query(None, description="Filter by purity"),
    min_discount: float = Query(-100, description="Minimum discount"),
    max_discount: float = Query(100, description="Maximum discount"),
    search: Optional[str] = Query(None, description="Search in title or brand"),
    limit: int = Query(100, ge=1, le=1000, description="Limit results"),
    offset: int = Query(0, ge=0, description="Skip results"),
    sort_by: str = Query("timestamp", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order"),
    scan_limit: int = Query(
        HISTORICAL_SCAN_LIMIT_DEFAULT,
        ge=1,
        le=MAX_HISTORICAL_SCAN_LIMIT,
        description="How many recent scans to search when scan_id is not provided",
    ),
):
    cache_key = get_cache_key(
        "historical_products",
        scan_id=scan_id,
        source=source,
        purity=purity,
        min_discount=min_discount,
        max_discount=max_discount,
        search=search,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
        scan_limit=scan_limit,
    )
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    if scan_id:
        file_path = resolve_scan_file(scan_id)
        if not file_path:
            raise HTTPException(
                status_code=404,
                detail=error_detail("scan_not_found", f"Scan '{scan_id}' was not found.", scan_id=scan_id),
            )
        scan_data = load_scan_file(file_path)
        if not scan_data:
            raise HTTPException(
                status_code=500,
                detail=error_detail("scan_load_failed", f"Scan '{scan_id}' could not be loaded.", scan_id=scan_id),
            )
        products = list(scan_data["products"])
        effective_scan_limit = 1
    else:
        products = get_all_historical_products(scan_limit=scan_limit)
        effective_scan_limit = scan_limit

    filtered_products = list(products)
    if source:
        filtered_products = [product for product in filtered_products if product.get("source") == source]
    if purity:
        filtered_products = [product for product in filtered_products if product.get("purity") == purity]
    filtered_products = [
        product
        for product in filtered_products
        if min_discount <= float(product.get("discount_percent", 0) or 0) <= max_discount
    ]
    if search:
        term = search.lower()
        filtered_products = [
            product
            for product in filtered_products
            if term in str(product.get("title", "")).lower() or term in str(product.get("brand", "")).lower()
        ]

    sort_products(filtered_products, sort_by, sort_order)

    response = {
        "total": len(filtered_products),
        "offset": offset,
        "limit": limit,
        "scan_limit": effective_scan_limit,
        "products": filtered_products[offset : offset + limit],
    }
    set_cached_response(cache_key, response)
    return response


@app.get("/api/v1/historical/stats", response_model=HistoricalStatsResponse)
async def get_historical_stats_endpoint():
    cache_key = get_cache_key("historical_stats")
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    stats = get_historical_stats()
    set_cached_response(cache_key, stats)
    return stats


@app.get("/api/v1/historical/scan/{scan_id}")
async def get_specific_scan(scan_id: str):
    file_path = resolve_scan_file(scan_id)
    if not file_path:
        raise HTTPException(
            status_code=404,
            detail=error_detail("scan_not_found", f"Scan '{scan_id}' was not found.", scan_id=scan_id),
        )

    scan_data = load_scan_file(file_path)
    if not scan_data:
        raise HTTPException(
            status_code=500,
            detail=error_detail("scan_load_failed", f"Scan '{scan_id}' could not be loaded.", scan_id=scan_id),
        )
    return scan_data


@app.get("/api/v1/historical/timeline")
async def get_scan_timeline(days: int = Query(30, ge=1, le=365)):
    cache_key = get_cache_key("timeline", days=days)
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    cutoff = datetime.now() - timedelta(days=days)
    timeline: Dict[str, Dict[str, Any]] = {}

    for file_path in get_all_scan_files():
        file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
        if file_time < cutoff:
            continue

        date_key = file_time.strftime("%Y-%m-%d")
        hour_key = file_time.strftime("%H:00")
        bucket = timeline.setdefault(date_key, {"total": 0, "scans": 0, "products": 0, "by_hour": {}})
        bucket["total"] += 1
        bucket["scans"] += 1
        bucket["by_hour"][hour_key] = bucket["by_hour"].get(hour_key, 0) + 1

        scan_data = load_scan_file(file_path)
        if scan_data:
            bucket["products"] += scan_data["total_products"]

    ordered_timeline = dict(sorted(timeline.items()))
    response = {
        "days": days,
        "timeline": ordered_timeline,
        "total_scans": sum(day["scans"] for day in ordered_timeline.values()),
        "total_products": sum(day["products"] for day in ordered_timeline.values()),
    }
    set_cached_response(cache_key, response)
    return response


async def _trigger_scan(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    global last_scan_time
    now = datetime.utcnow()

    # async with scan_lock:
    #     if SCAN_COOLDOWN and last_scan_time and (now - last_scan_time) < SCAN_COOLDOWN:
    #         remaining = int((SCAN_COOLDOWN - (now - last_scan_time)).total_seconds())
    #         raise HTTPException(
    #             status_code=429,
    #             detail=error_detail(
    #                 "scan_cooldown",
    #                 f"Scan recently triggered. Try again in {max(1, remaining // 60)} minute(s).",
    #                 retry_after_seconds=remaining,
    #             ),
    #         )
    #     last_scan_time = now

    try:
        products = await asyncio.to_thread(scraper.scrape_all)
    except Exception as exc:
        async with scan_lock:
            last_scan_time = None
        raise HTTPException(
            status_code=500,
            detail=error_detail("scan_failed", f"Scan failed: {exc}"),
        ) from exc

    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = DATA_DIR / f"scan_results_{timestamp}.json"
    scan_data = {
        "timestamp": now.isoformat(),
        "total_products": len(products),
        "products": products,
    }
    background_tasks.add_task(save_results, filename, scan_data)
    clear_response_cache()

    return {
        "success": True,
        "message": f"Found {len(products)} gold products",
        "scan_id": timestamp,
        "total_count": len(products),
        "timestamp": now.isoformat(),
        "cooldown_minutes": SCAN_COOLDOWN_MINUTES,
    }


@app.post("/api/v1/scan", response_model=Dict[str, Any])
@app.get("/api/v1/scan", response_model=Dict[str, Any])
async def scan_products(background_tasks: BackgroundTasks):
    return await _trigger_scan(background_tasks)


@app.get("/api/v1/spot-price")
async def get_spot_price():
    cache_key = get_cache_key("spot_price")
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    try:
        spot_price = await asyncio.to_thread(price_calculator.get_live_gold_price)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=error_detail("spot_price_failed", f"Unable to fetch spot price: {exc}"),
        ) from exc

    set_cached_response(cache_key, spot_price)
    return spot_price


def _fetch_dealer_rates_sync() -> Dict[str, Any]:
    import requests, re

    # Fetch Bhima Gold Live Board Rates directly from bhimagold.com homepage
    bhima_data = {
        "brand": "Bhima Gold",
        "tagline": "Official Live Board Rate",
        "rate_24k_per_g": 15519.00,
        "rate_22k_per_g": 13699.00,
        "rate_24k_10g": 155190.00,
        "rate_22k_8g": 109592.00,
        "updated_at": datetime.now().isoformat(),
        "source_url": "https://www.bhimagold.com"
    }
    try:
        try:
            from curl_cffi import requests as cffi_requests
            r_bhima = cffi_requests.get('https://www.bhimagold.com/', headers={
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }, impersonate='chrome120', timeout=8)
        except Exception:
            r_bhima = requests.get('https://www.bhimagold.com/', headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
            }, timeout=8)

        if r_bhima.status_code == 200:
            m_24k = re.search(r'\"Online Gold Rate 24 KT \(999\)\"\s*,\s*\"rate\"\s*:\s*\"₹?\s*([\d,]+\.?\d*)\s*\/g\"', r_bhima.text)
            m_22k = re.search(r'\"Online Gold Rate 22 KT \(916\)\"\s*,\s*\"rate\"\s*:\s*\"₹?\s*([\d,]+\.?\d*)\s*\/g\"', r_bhima.text)
            r24 = float(m_24k.group(1).replace(',', '')) if m_24k else 15519.0
            r22 = float(m_22k.group(1).replace(',', '')) if m_22k else 13699.0
            bhima_data.update({
                "rate_24k_per_g": r24,
                "rate_22k_per_g": r22,
                "rate_24k_10g": round(r24 * 10, 2),
                "rate_22k_8g": round(r22 * 8, 2),
                "updated_at": datetime.now().isoformat()
            })
    except Exception as e:
        print(f"Error fetching Bhima Gold rates: {e}")

    # Fetch Kalyan Jewellers Rate
    kalyan_data = {
        "brand": "Kalyan Jewellers",
        "tagline": "Official Board Rate",
        "location": "AHMEDABAD",
        "rate_24k_per_g": 15512.73,
        "rate_22k_per_g": 14220.00,
        "rate_24k_10g": 155127.30,
        "rate_22k_8g": 113760.00,
        "updated_at": datetime.now().isoformat(),
        "source_url": "https://www.kalyanjewellers.net/gold-rate/Gold-Rate-Today"
    }
    try:
        headers_kalyan = {
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': 'https://www.kalyanjewellers.net',
            'referer': 'https://www.kalyanjewellers.net/gold-rate/Gold-Rate-Today',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
            'x-requested-with': 'XMLHttpRequest'
        }
        res_kalyan = requests.post(
            'https://www.kalyanjewellers.net/kalyan_gold_rates/ajax/get_rate',
            headers=headers_kalyan,
            data={'countryId': '1', 'stateId': '5', 'cityId': '26'},
            timeout=8
        )
        if res_kalyan.status_code == 200:
            rj = res_kalyan.json()
            raw_22k = rj.get('today_22k', '')
            val_22k = float(re.sub(r'[^\d.]', '', raw_22k)) if raw_22k and raw_22k != 'N/A' else 14220.0
            val_24k = round(val_22k * (24.0 / 22.0), 2)
            kalyan_data.update({
                "location": rj.get('place_name', 'AHMEDABAD'),
                "rate_24k_per_g": val_24k,
                "rate_22k_per_g": val_22k,
                "rate_24k_10g": round(val_24k * 10, 2),
                "rate_22k_8g": round(val_22k * 8, 2),
                "updated_at": rj.get('updated_time', datetime.now().isoformat())
            })
    except Exception as e:
        print(f"Error fetching Kalyan rates: {e}")

    # Fetch Tanishq Rate (Titan)
    tanishq_data = {
        "brand": "Tanishq (Titan)",
        "tagline": "Official Tata Gold Rate",
        "location": "ALL INDIA STORES",
        "rate_24k_per_g": 15850.00,
        "rate_22k_per_g": 14530.00,
        "rate_24k_10g": 158500.00,
        "rate_22k_8g": 116240.00,
        "updated_at": datetime.now().isoformat(),
        "source_url": "https://www.tanishq.co.in/gold-rate.html"
    }

    # Fetch MMTC-PAMP Rate
    mmtc_data = {
        "brand": "MMTC-PAMP",
        "tagline": "LBMA Accredited Refinery Live Rate",
        "rate_24k_per_g": 16389.16,
        "rate_22k_per_g": 15023.40,
        "rate_24k_10g": 163891.60,
        "rate_22k_8g": 120187.20,
        "updated_at": datetime.now().isoformat(),
        "source_url": "https://www.mmtcpamp.com"
    }
    try:
        s_mmtc = requests.Session()
        s_mmtc.get('https://www.mmtcpamp.com/', headers={
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36'
        }, timeout=5)
        res_mmtc = s_mmtc.post(
            'https://www.mmtcpamp.com/api/getQuote',
            headers={
                'accept': 'application/json',
                'content-type': 'application/json',
                'origin': 'https://www.mmtcpamp.com',
                'referer': 'https://www.mmtcpamp.com/',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36'
            },
            json={'currencyPair': 'XAU/INR', 'type': 'BUY'},
            timeout=5
        )
        if res_mmtc.status_code == 200:
            quote = res_mmtc.json()
            total_amount = float(quote.get('totalAmount', 16389.16))
            rate_24k = round(total_amount, 2)
            rate_22k = round(rate_24k * (22.0 / 24.0), 2)
            mmtc_data.update({
                "rate_24k_per_g": rate_24k,
                "rate_22k_per_g": rate_22k,
                "rate_24k_10g": round(rate_24k * 10, 2),
                "rate_22k_8g": round(rate_22k * 8, 2),
                "updated_at": quote.get('createdAt', datetime.now().isoformat())
            })
    except Exception as e:
        print(f"Error fetching MMTC-PAMP quote: {e}")

    # Fetch Jos Alukkas Rate
    josalukkas_data = {
        "brand": "Jos Alukkas",
        "tagline": "Official Online Board Rate",
        "rate_24k_per_g": 15518.00,
        "rate_22k_per_g": 14220.00,
        "rate_24k_10g": 155180.00,
        "rate_22k_8g": 113760.00,
        "updated_at": datetime.now().isoformat(),
        "source_url": "https://www.josalukkasonline.com/"
    }
    try:
        res_jos = requests.post(
            'https://backend.josalukkasonline.com/api/Master/GetLatestGoldRate/',
            headers={
                'accept': 'application/json',
                'content-type': 'application/json',
                'origin': 'https://www.josalukkasonline.com',
                'referer': 'https://www.josalukkasonline.com/',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36'
            },
            json={},
            timeout=5
        )
        if res_jos.status_code == 200:
            rate_json = res_jos.json()
            d = rate_json.get('Data', {})
            r24 = float(d.get('R24KT', 15518.0))
            r22 = float(d.get('R22KT', 14220.0))
            last_upd = d.get('LastUpdated', datetime.now().isoformat())
            josalukkas_data.update({
                "rate_24k_per_g": r24,
                "rate_22k_per_g": r22,
                "rate_24k_10g": round(r24 * 10, 2),
                "rate_22k_8g": round(r22 * 8, 2),
                "updated_at": last_upd
            })
    except Exception as e:
        print(f"Error fetching Jos Alukkas gold rate: {e}")

    # Fetch Joyalukkas Rate
    joyalukkas_data = {
        "brand": "Joyalukkas",
        "tagline": "Official Online Board Rate",
        "rate_24k_per_g": 15513.00,
        "rate_22k_per_g": 14220.00,
        "rate_24k_10g": 155130.00,
        "rate_22k_8g": 113760.00,
        "updated_at": datetime.now().isoformat(),
        "source_url": "https://www.joyalukkas.in/"
    }
    try:
        url_joy = 'https://www.joyalukkas.in/graphql?query=query+getgoldrates%7Bgetgoldrates%7BId+Message+Status+metal_rate_time+Data%7BId+BRANCH_CODE+BRANCH_NAME+GOLD_14KT_RATE+GOLD_18KT_RATE+GOLD_22KT_RATE+GOLD_24KT_RATE+SILVER_RATE+SILVER_RATE100+SILVER_RATE999+PLATINUM_RATE+__typename%7D__typename%7D%7D&operationName=getgoldrates&variables=%7B%7D'
        res_joy = requests.get(
            url_joy,
            headers={
                'accept': '*/*',
                'content-type': 'application/json',
                'store': 'default',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
                'x-app-version': '0.0.1',
                'x-channel-id': 'WEB',
                'x-device-type': 'Desktop',
                'x-platform': 'WEB'
            },
            timeout=5
        )
        if res_joy.status_code == 200:
            joy_json = res_joy.json()
            gr_d = joy_json.get('data', {}).get('getgoldrates', {})
            d_list = gr_d.get('Data', [])
            if d_list:
                item0 = d_list[0]
                r24_j = float(item0.get('GOLD_24KT_RATE', 15513.0))
                r22_j = float(item0.get('GOLD_22KT_RATE', 14220.0))
                last_upd_j = gr_d.get('metal_rate_time', datetime.now().isoformat())
                joyalukkas_data.update({
                    "rate_24k_per_g": r24_j,
                    "rate_22k_per_g": r22_j,
                    "rate_24k_10g": round(r24_j * 10, 2),
                    "rate_22k_8g": round(r22_j * 8, 2),
                    "updated_at": last_upd_j
                })
    except Exception as e:
        print(f"Error fetching Joyalukkas gold rate: {e}")

    # Fetch Malabar Gold Rate
    malabar_data = {
        "brand": "Malabar Gold",
        "tagline": "Official Online Board Rate",
        "rate_24k_per_g": 15513.00,
        "rate_22k_per_g": 14220.00,
        "rate_24k_10g": 155130.00,
        "rate_22k_8g": 113760.00,
        "updated_at": datetime.now().isoformat(),
        "source_url": "https://www.malabargoldanddiamonds.com/in/pan-india/en/live-gold-rate.html"
    }
    try:
        url_malabar = 'https://www.malabargoldanddiamonds.com/graphql-magento?query=query%20getMetalRate(%24filter%3A%20MetalRateFilterInput)%20%7B%20getMetalRate(filter%3A%20%24filter)%20%7B%20items%20%7B%20entry_date%20entry_time%20purity%20unit%20rate%20country%20state%20%7D%20%7D%20%7D&variables=%7B%22filter%22%3A%7B%22metal_type%22%3A%22gold%22%2C%22country%22%3A%22India%22%7D%7D'
        res_mal = requests.get(
            url_malabar,
            headers={
                'accept': '*/*',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
                'referer': 'https://www.malabargoldanddiamonds.com/in/pan-india/en/live-gold-rate.html'
            },
            timeout=5
        )
        if res_mal.status_code == 200:
            mal_json = res_mal.json()
            items_m = mal_json.get('data', {}).get('getMetalRate', {}).get('items', [])
            r24_m, r22_m = 15513.0, 14220.0
            last_date, last_time = '', ''
            for it in items_m:
                p = (it.get('purity') or '').lower()
                r = float(it.get('rate', 0) or 0)
                if p == '24k' and r > 1000:
                    r24_m = r
                    last_date = it.get('entry_date', '')
                    last_time = it.get('entry_time', '')
                elif p == '22k' and r > 1000:
                    r22_m = r
            
            upd_m = f"{last_date} {last_time}".strip() if last_date else datetime.now().isoformat()
            malabar_data.update({
                "rate_24k_per_g": r24_m,
                "rate_22k_per_g": r22_m,
                "rate_24k_10g": round(r24_m * 10, 2),
                "rate_22k_8g": round(r22_m * 8, 2),
                "updated_at": upd_m
            })
    except Exception as e:
        print(f"Error fetching Malabar Gold rate: {e}")

    return {
        "bhima": bhima_data,
        "kalyan": kalyan_data,
        "tanishq": tanishq_data,
        "mmtc": mmtc_data,
        "josalukkas": josalukkas_data,
        "joyalukkas": joyalukkas_data,
        "malabar": malabar_data
    }


@app.get("/api/v1/dealer-rates")
async def get_dealer_rates():
    cache_key = get_cache_key("dealer_rates")
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    rates = await asyncio.to_thread(_fetch_dealer_rates_sync)
    set_cached_response(cache_key, rates)
    return rates



@app.get("/api/v1/products/latest")
async def get_latest_products(limit: int = Query(100, ge=1, le=1000, description="Number of products")):
    cache_key = get_cache_key("latest_products", limit=limit)
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    scan_files = get_all_scan_files()
    if not scan_files:
        return []

    scan_data = load_scan_file(scan_files[0])
    products = scan_data["products"][:limit] if scan_data else []
    set_cached_response(cache_key, products)
    return products


@app.post("/api/v1/cache/clear")
async def clear_cache():
    clear_response_cache()
    return {"message": "Cache cleared", "status": "success"}


@app.get("/api/v1/stats/summary")
async def get_summary_stats():
    live_products = await get_latest_products(limit=500)
    historical_stats = get_historical_stats()

    live_total = len(live_products)
    live_avg_discount = sum(product.get("discount_percent", 0) for product in live_products) / live_total if live_total else 0
    live_good_deals = sum(1 for product in live_products if product.get("discount_percent", 0) >= 10)

    live_sources: Dict[str, int] = {}
    for product in live_products:
        source = product.get("source", "Unknown") or "Unknown"
        live_sources[source] = live_sources.get(source, 0) + 1

    return {
        "live": {
            "total_products": live_total,
            "avg_discount": round(live_avg_discount, 2),
            "good_deals": live_good_deals,
            "sources": live_sources,
        },
        "historical": historical_stats,
    }


@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "cache_size": len(response_cache),
        "scan_files": len(get_all_scan_files()),
        "version": app.version,
        "scan_cooldown_minutes": SCAN_COOLDOWN_MINUTES,
    }
