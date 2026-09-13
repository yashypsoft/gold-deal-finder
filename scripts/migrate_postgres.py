#!/usr/bin/env python3
"""
PostgreSQL Production Migration & Seed CLI Script
Applies schema.sql to the target PostgreSQL database and seeds initial SGB tranches.
Usage:
    python scripts/migrate_postgres.py
    python scripts/migrate_postgres.py --db-url postgresql://user:pass@129.154.253.67:5432/scrapper_db
"""

import os
import sys
import argparse
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DATABASE_URL
from sgb_screener import sgb_screener

SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"


def run_migration(db_url: str):
    if not db_url:
        print("❌ Error: No DATABASE_URL provided. Set DATABASE_URL in .env or pass --db-url.")
        sys.exit(1)

    print(f"🔌 Connecting to PostgreSQL at: {db_url.split('@')[-1] if '@' in db_url else db_url}...")

    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

        conn = psycopg2.connect(db_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        print("📄 Reading schema.sql...")
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            sql_content = f.read()

        print("⚡ Executing DDL migrations on scrapper_db...")
        cursor.execute(sql_content)
        print("✅ Tables, enums, and indexes successfully initialized!")

        # Seed initial SGB tranches
        print("🌱 Seeding Sovereign Gold Bond (SGB) master tranches...")
        tranches = sgb_screener.scan_all_tranches()
        
        insert_sgb_sql = """
        INSERT INTO sgb_tranches (
            isin, ticker, exchange, issue_date, maturity_date, issue_price,
            coupon_rate, ltp, ask_price, ask_quantity, underlying_spot_price,
            discount_to_spot_pct, annualized_ytm_pct, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (isin) DO UPDATE SET
            ltp = EXCLUDED.ltp,
            ask_price = EXCLUDED.ask_price,
            underlying_spot_price = EXCLUDED.underlying_spot_price,
            discount_to_spot_pct = EXCLUDED.discount_to_spot_pct,
            annualized_ytm_pct = EXCLUDED.annualized_ytm_pct,
            updated_at = NOW();
        """
        for t in tranches:
            cursor.execute(insert_sgb_sql, (
                t["isin"], t["ticker"], t.get("exchange", "NSE"),
                t.get("issue_date", "2020-01-01"), t["maturity_date"],
                float(t.get("issue_price", 5000.0)), float(t.get("coupon_rate", 2.50)),
                float(t["ltp"]), float(t.get("ask_price", t["ltp"])),
                int(t.get("ask_quantity", 50)), float(t["underlying_spot_price"]),
                float(t["discount_to_spot_pct"]), float(t["annualized_ytm_pct"])
            ))

        print(f"✅ Seeded {len(tranches)} active SGB tranches.")

        # Seed default demo user
        cursor.execute("""
        INSERT INTO users (id, full_name, email, current_tier)
        VALUES ('user_default', 'Pro Bullion Investor', 'pro@golddealfinder.in', 'PRO')
        ON CONFLICT (id) DO UPDATE SET current_tier = 'PRO';
        """)

        cursor.close()
        conn.close()
        print("\n🎉 PostgreSQL migration and seeding completed successfully!")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PostgreSQL Migration Tool for Gold Deal Finder")
    parser.add_argument("--db-url", type=str, default=DATABASE_URL, help="PostgreSQL connection string")
    args = parser.parse_args()
    run_migration(args.db_url)
