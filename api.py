from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import logging
import re
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import (
    CACHE_TTL,
    HISTORICAL_SCAN_LIMIT_DEFAULT,
    MAX_HISTORICAL_SCAN_LIMIT,
    SCAN_COOLDOWN_MINUTES,
    SUBSCRIPTION_PLANS,
    RAZORPAY_KEY_ID,
)
from gold_scraper import GoldScraper
from price_calculator import GoldPriceCalculator
from database import db_manager
from card_engine import card_stacker, card_parser, CARD_REGISTRY, DEFAULT_SEASONAL_BANK_OFFERS
from sgb_screener import sgb_screener
from arbitrage_engine import arbitrage_engine
from vip_alerts import vip_dispatcher
from receipt_generator import receipt_generator
from buyback_calculator import buyback_calculator
from restock_sniper import restock_sniper
from whatsapp_service import whatsapp_service

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

@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/static/") or path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

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


@app.api_route("/", methods=["GET", "HEAD"])
async def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.api_route("/favicon.ico", methods=["GET", "HEAD"])
async def favicon() -> FileResponse:
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


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


class ScanProgressManager:
    def __init__(self):
        self._lock = threading.RLock()
        self.status = "idle"  # idle | running | completed | error
        self.scan_id = ""
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.total_products = 0
        self.current_site = ""
        self.error_message: Optional[str] = None
        self.sites = self._init_sites()
        self.logs: List[Dict[str, Any]] = []
        self._runner_thread: Optional[threading.Thread] = None

    def _init_sites(self, selected_keys: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        all_sites = {
            "ajio": {"key": "ajio", "name": "AJIO", "status": "pending", "count": 0, "duration": 0, "message": "Pending"},
            "myntra": {"key": "myntra", "name": "Myntra", "status": "pending", "count": 0, "duration": 0, "message": "Pending"},
            "candere": {"key": "candere", "name": "Candere / Kalyan", "status": "pending", "count": 0, "duration": 0, "message": "Pending"},
            "bhima": {"key": "bhima", "name": "Bhima Gold", "status": "pending", "count": 0, "duration": 0, "message": "Pending"},
            "tanishq": {"key": "tanishq", "name": "Tanishq", "status": "pending", "count": 0, "duration": 0, "message": "Pending"},
            "mmtc": {"key": "mmtc", "name": "MMTC-PAMP", "status": "pending", "count": 0, "duration": 0, "message": "Pending"},
            "josalukkas": {"key": "josalukkas", "name": "Jos Alukkas", "status": "pending", "count": 0, "duration": 0, "message": "Pending"},
            "joyalukkas": {"key": "joyalukkas", "name": "Joyalukkas", "status": "pending", "count": 0, "duration": 0, "message": "Pending"},
            "malabar": {"key": "malabar", "name": "Malabar Gold", "status": "pending", "count": 0, "duration": 0, "message": "Pending"},
        }
        if selected_keys:
            selected_set = {k.lower().strip() for k in selected_keys if k and k.strip()}
            filtered = {k: v for k, v in all_sites.items() if k in selected_set}
            return filtered if filtered else all_sites
        return all_sites

    def on_progress(self, site_key: str, status: str, count: Optional[int], message: Optional[str]):
        with self._lock:
            if site_key in self.sites:
                site = self.sites[site_key]
                site["status"] = status
                if count is not None:
                    site["count"] = count
                if message:
                    site["message"] = message

            if status == "running":
                self.current_site = self.sites.get(site_key, {}).get("name", site_key)
                log_type = "info"
            elif status == "completed":
                log_type = "success"
            elif status == "error":
                log_type = "error"
            else:
                log_type = "info"

            # Recalculate total products
            self.total_products = sum(s.get("count", 0) for s in self.sites.values())
            self.logs.append({
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "site": self.sites.get(site_key, {}).get("name", site_key),
                "type": log_type,
                "message": message or f"{site_key}: {status}"
            })
            if len(self.logs) > 100:
                self.logs.pop(0)

    def _to_dict_unlocked(self) -> Dict[str, Any]:
        now = datetime.utcnow()
        if self.started_at:
            if self.status == "running":
                elapsed = max(0.0, round((now - self.started_at).total_seconds(), 1))
            elif self.completed_at:
                elapsed = max(0.0, round((self.completed_at - self.started_at).total_seconds(), 1))
            else:
                elapsed = 0.0
        else:
            elapsed = 0.0

        total_sites = len(self.sites)
        finished_sites = sum(1 for s in self.sites.values() if s["status"] in ("completed", "error"))
        running_sites = sum(1 for s in self.sites.values() if s["status"] == "running")
        
        if self.status == "completed":
            progress_pct = 100
        elif self.status == "running":
            progress_pct = min(95, max(5, int((finished_sites / max(total_sites, 1)) * 90) + (5 if running_sites > 0 else 0)))
        else:
            progress_pct = 0 if self.status == "idle" else 100

        return {
            "status": self.status,
            "is_running": self.status == "running",
            "scan_id": self.scan_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "elapsed_seconds": elapsed,
            "progress_percent": progress_pct,
            "total_products": self.total_products,
            "current_site": self.current_site,
            "error_message": self.error_message,
            "sites": list(self.sites.values()),
            "logs": list(self.logs[-40:]),
        }

    def start_scan(self, sites: Optional[List[str]] = None) -> Dict[str, Any]:
        with self._lock:
            if self.status == "running":
                return self._to_dict_unlocked()

            # Default to all stores EXCEPT bhima (slow page-by-page) if not specified
            if sites is None:
                chosen_sites = ["ajio", "myntra", "candere", "tanishq", "mmtc", "josalukkas", "joyalukkas", "malabar"]
            else:
                chosen_sites = [s.lower().strip() for s in sites if s and s.strip()]
                if not chosen_sites:
                    chosen_sites = ["ajio", "myntra", "candere", "tanishq", "mmtc", "josalukkas", "joyalukkas", "malabar"]

            now = datetime.utcnow()
            self.scan_id = now.strftime("%Y%m%d_%H%M%S")
            self.status = "running"
            self.started_at = now
            self.completed_at = None
            self.total_products = 0
            self.error_message = None
            self.current_site = "Initializing scrapers..."
            self.sites = self._init_sites(selected_keys=chosen_sites)
            num_stores = len(self.sites)
            store_names = ", ".join(s["name"] for s in self.sites.values())
            self.logs = [{
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "site": "System",
                "type": "info",
                "message": f"Scan #{self.scan_id} initiated for {num_stores} stores ({store_names})..."
            }]
            snapshot = self._to_dict_unlocked()

        def _background_worker():
            try:
                products = scraper.scrape_all(progress_callback=self.on_progress, sites=chosen_sites)
                
                filename = DATA_DIR / f"scan_results_{self.scan_id}.json"
                scan_data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "total_products": len(products),
                    "products": products,
                }
                save_results(filename, scan_data)

                # Merge with latest_scan.json if it exists so un-scraped stores aren't lost
                latest_filename = DATA_DIR / "latest_scan.json"
                if latest_filename.exists() and len(chosen_sites) < 9:
                    try:
                        with open(latest_filename, "r") as lf:
                            old_latest = json.load(lf)
                        old_products = old_latest.get("products", [])

                        scraped_site_names = {self.sites[k]["name"].lower() for k in chosen_sites if k in self.sites}
                        scraped_sources = set(chosen_sites)
                        for s_name in scraped_site_names:
                            scraped_sources.add(s_name)
                            if "kalyan" in s_name or "candere" in s_name:
                                scraped_sources.update(["candere", "candere / kalyan", "kalyan"])
                            if "mmtc" in s_name:
                                scraped_sources.update(["mmtc", "mmtc-pamp", "mmtc pamp"])
                            if "bhima" in s_name:
                                scraped_sources.update(["bhima", "bhima gold"])
                            if "jos" in s_name:
                                scraped_sources.update(["jos alukkas", "josalukkas"])
                            if "joy" in s_name:
                                scraped_sources.update(["joyalukkas", "joy alukkas"])
                            if "malabar" in s_name:
                                scraped_sources.update(["malabar", "malabar gold"])
                            if "ajio" in s_name:
                                scraped_sources.add("ajio")
                            if "myntra" in s_name:
                                scraped_sources.add("myntra")
                            if "tanishq" in s_name:
                                scraped_sources.add("tanishq")

                        preserved_products = [
                            p for p in old_products 
                            if p.get("source", "").lower() not in scraped_sources and p.get("brand", "").lower() not in scraped_sources
                        ]
                        merged_products = products + preserved_products
                        save_results(latest_filename, {
                            "timestamp": datetime.utcnow().isoformat(),
                            "total_products": len(merged_products),
                            "products": merged_products,
                        })
                    except Exception as merge_err:
                        print(f"Error merging latest scan: {merge_err}")
                        save_results(latest_filename, scan_data)
                else:
                    save_results(latest_filename, scan_data)

                clear_response_cache()

                with self._lock:
                    self.status = "completed"
                    self.completed_at = datetime.utcnow()
                    self.total_products = len(products)
                    self.current_site = "Completed"
                    self.logs.append({
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "site": "System",
                        "type": "success",
                        "message": f"Scan completed! Saved {len(products)} products across {num_stores} stores."
                    })
            except Exception as exc:
                print(f"Scan background runner error: {exc}")
                with self._lock:
                    self.status = "error"
                    self.error_message = str(exc)
                    self.completed_at = datetime.utcnow()
                    self.logs.append({
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "site": "System",
                        "type": "error",
                        "message": f"Scan failed: {exc}"
                    })

        self._runner_thread = threading.Thread(target=_background_worker, daemon=True)
        self._runner_thread.start()
        return snapshot

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return self._to_dict_unlocked()


scan_manager = ScanProgressManager()


class ScanPayload(BaseModel):
    sites: Optional[List[str]] = None


@app.post("/api/v1/scan", response_model=Dict[str, Any])
async def scan_products_post(payload: Optional[ScanPayload] = None):
    """Trigger an asynchronous background scan session with optional site selection"""
    sites = payload.sites if payload and payload.sites else None
    state = scan_manager.start_scan(sites=sites)
    return {
        "success": True,
        "message": "Scan started in background" if state["is_running"] else "Scan already in progress",
        "scan_id": state["scan_id"],
        "status": state["status"],
        "progress": state,
    }


@app.get("/api/v1/scan", response_model=Dict[str, Any])
async def scan_products_get(sites: Optional[str] = Query(None, description="Comma-separated site keys e.g. ajio,joyalukkas")):
    """Trigger an asynchronous background scan session (GET alias with optional ?sites=...)"""
    selected = [s.strip() for s in sites.split(",") if s.strip()] if sites else None
    state = scan_manager.start_scan(sites=selected)
    return {
        "success": True,
        "message": "Scan started in background" if state["is_running"] else "Scan already in progress",
        "scan_id": state["scan_id"],
        "status": state["status"],
        "progress": state,
    }


@app.get("/api/v1/scan/status", response_model=Dict[str, Any])
async def get_scan_status():
    """Get live progress details of current or latest scan"""
    return scan_manager.to_dict()


@app.post("/api/v1/scan/cancel", response_model=Dict[str, Any])
async def cancel_scan():
    """Mark running scan as idle if stuck"""
    with scan_manager._lock:
        scan_manager.status = "idle"
        scan_manager.current_site = "Cancelled"
    return {"success": True, "message": "Scan status reset to idle"}


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
        "rate_24k_per_g": 16151.00,
        "rate_22k_per_g": 14805.00,
        "rate_18k_per_g": 12113.00,
        "rate_24k_10g": 161510.00,
        "rate_22k_8g": 118440.00,
        "updated_at": datetime.now().isoformat(),
        "source_url": "https://www.tanishq.co.in/gold-rate.html"
    }
    try:
        try:
            from curl_cffi import requests as c_requests
            session_tq = c_requests.Session(impersonate='chrome120')
        except Exception:
            session_tq = requests.Session()

        r_tq = session_tq.get('https://www.tanishq.co.in/gold-rate.html', timeout=8)
        if r_tq.status_code == 200 and r_tq.text:
            m_tq = re.search(r'data-goldrate22kt=\"(\d+)\"[^>]*data-goldrate24kt=\"(\d+)\"(?:[^>]*data-goldrate18kt=\"(\d+)\")?', r_tq.text)
            if not m_tq:
                m_tq = re.search(r'data-goldrate24kt=\"(\d+)\"[^>]*data-goldrate22kt=\"(\d+)\"', r_tq.text)
                if m_tq:
                    r24 = float(m_tq.group(1))
                    r22 = float(m_tq.group(2))
                    r18 = round(r24 * 0.75, 2)
            else:
                r22 = float(m_tq.group(1))
                r24 = float(m_tq.group(2))
                r18 = float(m_tq.group(3)) if m_tq.group(3) else round(r24 * 0.75, 2)

            if m_tq:
                date_m = re.search(r'<td>(\d{2}-\d{2}-\d{4})</td>\s*<td>[^<]*<span[^>]*class=[\"\']goldpurity-rate[\"\']', r_tq.text)
                date_str = date_m.group(1) if date_m else datetime.now().strftime('%d-%m-%Y')
                tanishq_data.update({
                    "rate_24k_per_g": r24,
                    "rate_22k_per_g": r22,
                    "rate_18k_per_g": r18,
                    "rate_24k_10g": round(r24 * 10, 2),
                    "rate_22k_8g": round(r22 * 8, 2),
                    "updated_at": datetime.now().isoformat(),
                    "rate_date": date_str
                })
    except Exception as e:
        print(f"Error fetching live Tanishq rates: {e}")

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
        "db_mode": "postgresql" if db_manager.use_postgres else "sqlite"
    }


# ==========================================
# SAAS SUBSCRIPTION & MONETIZATION ENDPOINTS
# ==========================================

class UpgradePlanRequest(BaseModel):
    user_id: str
    plan_id: str
    payment_ref: Optional[str] = "DEMO_SUCCESS"


class UpdateCardsRequest(BaseModel):
    user_id: str
    card_ids: List[str]


class CardStackRequest(BaseModel):
    selling_price: float
    weight_grams: float
    purity: Optional[str] = "24K"
    coupon_discount: Optional[float] = 0.0
    coupon_code: Optional[str] = ""
    card_ids: Optional[List[str]] = None


@app.get("/api/v1/subscription/plans")
async def get_subscription_plans():
    """Returns available pricing plans and features for the Indian market."""
    return {
        "status": "success",
        "currency": "INR",
        "plans": list(SUBSCRIPTION_PLANS.values())
    }


@app.post("/api/v1/subscription/upgrade")
async def upgrade_subscription(req: UpgradePlanRequest):
    """Upgrades user tier and generates active subscription record."""
    plan = SUBSCRIPTION_PLANS.get(req.plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Invalid plan ID '{req.plan_id}'")

    amount = plan.get("price_inr", 0)
    result = db_manager.upgrade_user_subscription(
        user_id=req.user_id,
        plan_id=req.plan_id,
        amount_paid=amount,
        gateway_ref=req.payment_ref
    )
    return {"status": "success", "subscription": result}


@app.get("/api/v1/user/profile")
async def get_user_profile(user_id: str = Query("user_default")):
    """Retrieves user tier, active subscription, and saved credit cards."""
    user = db_manager.get_or_create_user(user_id=user_id)
    saved_cards = db_manager.get_user_cards(user_id=user_id)
    return {
        "status": "success",
        "user": user,
        "cards": saved_cards,
        "is_pro": user.get("current_tier") in ("PRO", "TRADER")
    }


@app.post("/api/v1/user/cards")
async def update_user_cards(req: UpdateCardsRequest):
    """Saves user's credit card portfolio for personalized price stacking."""
    db_manager.set_user_cards(user_id=req.user_id, card_names=req.card_ids)
    return {"status": "success", "saved_cards": req.card_ids}


@app.get("/api/v1/cards/catalog")
async def get_card_catalog():
    """Returns supported Indian credit cards and current active bank promotions."""
    cards_list = [
        {
            "card_id": c.card_id,
            "card_name": c.card_name,
            "bank_code": c.bank_code,
            "reward_pct": c.jewellery_mcc_reward_pct,
            "notes": c.notes
        }
        for c in CARD_REGISTRY.values()
    ]
    offers_list = [o.model_dump() for o in DEFAULT_SEASONAL_BANK_OFFERS]
    return {
        "status": "success",
        "cards": cards_list,
        "active_bank_offers": offers_list
    }


@app.post("/api/v1/cards/stack")
async def calculate_card_stack(req: CardStackRequest):
    """Calculates optimal out-of-pocket payment and highlight card for any product."""
    rates = arbitrage_engine.get_live_spot_rates()
    spot = rates.get(req.purity, rates.get("24K", 7400.0))
    result = card_stacker.calculate_stack(
        selling_price=req.selling_price,
        weight_grams=req.weight_grams,
        spot_price_per_gram=spot,
        coupon_discount=req.coupon_discount or 0.0,
        coupon_code=req.coupon_code or "",
        user_card_ids=req.card_ids
    )
    return {"status": "success", "stack": result}


# ==========================================
# SAAS ARBITRAGE & SGB SCREENER ENDPOINTS
# ==========================================

@app.get("/api/v1/arbitrage/sub-spot")
async def get_sub_spot_radar(
    user_id: Optional[str] = None,
    min_spread: Optional[float] = 0.0
):
    """
    Sub-Spot Arbitrage Radar: Identifies products trading below wholesale spot rates
    or with 0% making charge glitches.
    """
    actual_user_id = user_id if isinstance(user_id, str) else None
    cache_key = get_cache_key("sub_spot_radar", user_id=actual_user_id or "all")
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    # Fetch latest products
    scan_files = get_all_scan_files()
    products = []
    if scan_files:
        scan_data = load_scan_file(scan_files[0])
        if scan_data:
            products = scan_data.get("products", [])

    # If user has specific cards saved, personalize stacking
    user_cards = db_manager.get_user_cards(actual_user_id) if actual_user_id else None

    # Run arbitrage evaluation
    radar_data = arbitrage_engine.process_catalog_arbitrage(
        products=products,
        user_card_ids=user_cards,
        save_to_db=True
    )

    set_cached_response(cache_key, radar_data)
    return radar_data


@app.get("/api/v1/sgb/screener")
async def get_sgb_screener(min_discount: Optional[float] = Query(-10.0)):
    """Live Sovereign Gold Bond secondary market discount and YTM screener."""
    cache_key = get_cache_key("sgb_screener", min_discount=min_discount)
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    tranches = sgb_screener.scan_all_tranches()
    filtered = [t for t in tranches if t["discount_to_spot_pct"] >= (min_discount or -10.0)]

    response = {
        "status": "success",
        "count": len(filtered),
        "spot_gold_999": sgb_screener.get_live_spot_gold_rate(),
        "top_discount_tranche": filtered[0] if filtered else None,
        "tranches": filtered
    }
    set_cached_response(cache_key, response)
    return response


@app.post("/api/v1/subscription/webhook")
async def razorpay_webhook(payload: Dict[str, Any]):
    """Receives Razorpay payment confirmation webhook."""
    event = payload.get("event")
    logger.info(f"Received payment webhook event: {event}")
    return {"status": "received", "event": event}


# ==========================================
# VIRAL MARKETING & PROOF RECEIPT ENDPOINTS
# ==========================================

@app.get("/api/v1/marketing/receipt")
async def get_viral_deal_receipt():
    """Generates ASCII receipt, Tweet text, and metadata for the top active sub-spot deal."""
    radar = await get_sub_spot_radar()
    deals = radar.get("sub_spot_deals", [])

    if deals:
        top_deal = deals[0]
    else:
        top_deal = {
            "title": "10g 24K Kundan Gold Bar (999 Purity)",
            "source": "Tata CLiQ",
            "weight_grams": 10.0,
            "purity": "24K",
            "selling_price": 149270.0,
            "live_spot_rate_per_gram": 15837.5,
            "effective_net_price": 124345.0,
            "effective_price_per_gram": 12434.5,
            "spread_per_gram": 3403.0,
            "total_stack_savings": 34030.0,
            "recommended_card": "Tata Neu Infinity HDFC"
        }

    ascii_card = receipt_generator.generate_ascii_receipt(top_deal, seconds_active=260)
    tweet_text = receipt_generator.generate_tweet_text(top_deal, seconds_active=260)

    return {
        "status": "success",
        "deal_title": top_deal.get("title"),
        "platform": top_deal.get("source"),
        "savings_inr": top_deal.get("total_stack_savings"),
        "spread_per_gram": top_deal.get("spread_per_gram"),
        "ascii_receipt": ascii_card,
        "tweet_copy": tweet_text,
        "svg_url": "/api/v1/marketing/receipt/svg"
    }


@app.get("/api/v1/marketing/receipt/svg")
async def get_viral_deal_receipt_svg():
    """Renders high-res SVG graphic receipt directly for Twitter/LinkedIn embedding."""
    radar = await get_sub_spot_radar()
    deals = radar.get("sub_spot_deals", [])

    if deals:
        top_deal = deals[0]
    else:
        top_deal = {
            "title": "10g 24K Kundan Gold Bar (999 Purity)",
            "source": "Tata CLiQ",
            "weight_grams": 10.0,
            "purity": "24K",
            "selling_price": 149270.0,
            "live_spot_rate_per_gram": 15837.5,
            "effective_net_price": 124345.0,
            "effective_price_per_gram": 12434.5,
            "spread_per_gram": 3403.0,
            "total_stack_savings": 34030.0,
            "recommended_card": "Tata Neu Infinity HDFC"
        }

    svg_content = receipt_generator.generate_svg_receipt(top_deal, seconds_active=260)
    return Response(content=svg_content, media_type="image/svg+xml")


# ==========================================
# PHASE 3: REVERSE ARBITRAGE & RESTOCK SNIPER
# ==========================================

class WatchSkuRequest(BaseModel):
    sku_id: str
    title: str
    platform: str
    url: str
    weight_grams: float
    purity: str = "24K"
    target_price: float = 0.0


class WhatsAppTestRequest(BaseModel):
    phone: str


@app.get("/api/v1/arbitrage/buyback-calculator")
async def calculate_buyback_payout(
    delivered_cost: float = Query(..., description="Net delivered purchase cost paid online"),
    weight: float = Query(..., description="Weight in grams"),
    purity: str = Query("24K", description="Gold purity (24K, 22K, 18K)"),
    item_type: str = Query("coin", description="Item type: bar, coin, jewellery"),
    turnover_days: int = Query(5, description="Holding cycle in days"),
    payment_mode: str = Query("RTGS", description="RTGS or CASH"),
    spot_override: Optional[float] = Query(None, description="Optional custom spot rate per gram")
):
    """Calculates physical bullion buyback liquidation payout, profit margin, and annualized ROI."""
    result = buyback_calculator.calculate_liquidation(
        delivered_cost=delivered_cost,
        weight_grams=weight,
        purity=purity,
        item_type=item_type,
        spot_override=spot_override,
        turnover_days=turnover_days,
        payment_mode=payment_mode
    )
    return result


@app.get("/api/v1/arbitrage/sub-spot-buybacks")
async def get_sub_spot_buybacks(limit: int = Query(20, ge=1, le=100)):
    """Returns top active sub-spot deals evaluated with physical bullion buyback liquidation profit."""
    radar = await get_sub_spot_radar()
    deals = radar.get("sub_spot_deals", [])[:limit]

    evaluated = []
    for deal in deals:
        eval_item = buyback_calculator.evaluate_deal(deal)
        eval_item["total_stack_savings"] = deal.get("total_stack_savings", 0)
        eval_item["spread_per_gram"] = deal.get("spread_per_gram", 0)
        eval_item["effective_net_price"] = deal.get("effective_net_price", 0)
        eval_item["recommended_card"] = deal.get("recommended_card", "Optimal Card")
        evaluated.append(eval_item)

    return {
        "status": "success",
        "count": len(evaluated),
        "live_rates": buyback_calculator.get_live_rates(),
        "deals": evaluated
    }


@app.get("/api/v1/sniper/status")
async def get_sniper_status():
    """Returns active restock sniper operational status and monitored SKUs."""
    return restock_sniper.get_status()


@app.post("/api/v1/sniper/watch")
async def add_sniper_watch_item(req: WatchSkuRequest):
    """Adds a target SKU to the high-frequency restock watch list."""
    item = restock_sniper.add_watch_sku(
        sku_id=req.sku_id,
        title=req.title,
        platform=req.platform,
        url=req.url,
        weight_grams=req.weight_grams,
        purity=req.purity,
        target_price=req.target_price
    )
    return {"status": "added", "item": item}


@app.post("/api/v1/sniper/poll-now")
async def poll_sniper_now():
    """Triggers an immediate check pass on all monitored restock SKUs."""
    results = restock_sniper.poll_once()
    return {"status": "success", "polled_count": len(results), "results": results}


@app.post("/api/v1/alerts/test-whatsapp")
async def test_whatsapp_alert(req: WhatsAppTestRequest):
    """Sends or simulates a VIP deal alert to a WhatsApp number."""
    sample_deal = {
        "title": "10g 24K Kundan Gold Bar (999 Purity)",
        "source": "Tata CLiQ",
        "weight_grams": 10.0,
        "purity": "24K",
        "selling_price": 149270.0,
        "live_spot_rate_per_gram": 15837.5,
        "effective_net_price": 124345.0,
        "effective_price_per_gram": 12434.5,
        "spread_per_gram": 3403.0,
        "total_stack_savings": 34030.0,
        "recommended_card": "Tata Neu Infinity HDFC",
        "url": "http://localhost:8000"
    }
    result = vip_dispatcher.dispatch_whatsapp_alert(phone=req.phone, deal=sample_deal)
    return result


