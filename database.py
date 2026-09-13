import os
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from config import DATABASE_URL, SUBSCRIPTION_PLANS

logger = logging.getLogger(__name__)

# Fallback SQLite DB path
SQLITE_DB_PATH = Path(__file__).resolve().parent / "data" / "gold_saas.db"
SQLITE_DB_PATH.parent.mkdir(exist_ok=True)


class DatabaseManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        self.use_postgres = False
        self.pg_conn = None

        if DATABASE_URL and (DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")):
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
                self.pg_conn = psycopg2.connect(DATABASE_URL)
                self.pg_conn.autocommit = True
                self.use_postgres = True
                logger.info("Connected successfully to PostgreSQL database.")
            except Exception as e:
                logger.warning(f"Failed to connect to PostgreSQL ({e}). Falling back to SQLite.")
                self.use_postgres = False
        else:
            logger.info(f"No PostgreSQL DATABASE_URL found. Using SQLite at {SQLITE_DB_PATH}.")

        self._create_tables()

    def get_connection(self):
        if self.use_postgres:
            try:
                if self.pg_conn.closed:
                    import psycopg2
                    self.pg_conn = psycopg2.connect(DATABASE_URL)
                    self.pg_conn.autocommit = True
                return self.pg_conn
            except Exception:
                import psycopg2
                self.pg_conn = psycopg2.connect(DATABASE_URL)
                self.pg_conn.autocommit = True
                return self.pg_conn
        else:
            conn = sqlite3.connect(str(SQLITE_DB_PATH), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn

    def _create_tables(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        if self.use_postgres:
            # PostgreSQL DDL
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR(64) PRIMARY KEY,
                full_name VARCHAR(100),
                email VARCHAR(255) UNIQUE,
                phone_number VARCHAR(20) UNIQUE,
                telegram_chat_id BIGINT UNIQUE,
                current_tier VARCHAR(20) DEFAULT 'FREE',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS user_subscriptions (
                id VARCHAR(64) PRIMARY KEY,
                user_id VARCHAR(64) REFERENCES users(id) ON DELETE CASCADE,
                tier VARCHAR(20) NOT NULL,
                status VARCHAR(20) DEFAULT 'ACTIVE',
                payment_gateway VARCHAR(30) DEFAULT 'MOCK',
                gateway_ref VARCHAR(100),
                amount_paid_inr NUMERIC(10, 2) NOT NULL,
                starts_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS user_card_profiles (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(64) REFERENCES users(id) ON DELETE CASCADE,
                bank_code VARCHAR(30) NOT NULL,
                card_tier_name VARCHAR(50) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                UNIQUE(user_id, bank_code, card_tier_name)
            );

            CREATE TABLE IF NOT EXISTS deal_scans (
                id SERIAL PRIMARY KEY,
                product_id VARCHAR(100),
                platform VARCHAR(50) NOT NULL,
                sku VARCHAR(100),
                brand VARCHAR(100),
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                image_url TEXT,
                weight_grams NUMERIC(8, 3) NOT NULL,
                purity_karat VARCHAR(10) NOT NULL,
                is_jewellery BOOLEAN DEFAULT FALSE,
                selling_price NUMERIC(10, 2) NOT NULL,
                coupon_code VARCHAR(50),
                coupon_discount NUMERIC(10, 2) DEFAULT 0,
                bank_discount NUMERIC(10, 2) DEFAULT 0,
                effective_net_price NUMERIC(10, 2) NOT NULL,
                effective_price_per_gram NUMERIC(10, 2) NOT NULL,
                live_spot_rate_per_gram NUMERIC(10, 2) NOT NULL,
                arbitrage_spread_inr NUMERIC(10, 2) NOT NULL,
                discount_vs_spot_pct NUMERIC(6, 2) NOT NULL,
                is_sub_spot BOOLEAN DEFAULT FALSE,
                is_low_making BOOLEAN DEFAULT FALSE,
                stock_status VARCHAR(20) DEFAULT 'IN_STOCK',
                scanned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS sgb_tranches (
                isin VARCHAR(20) PRIMARY KEY,
                ticker VARCHAR(30) NOT NULL,
                exchange VARCHAR(10) DEFAULT 'NSE',
                issue_date DATE,
                maturity_date DATE NOT NULL,
                issue_price NUMERIC(10, 2) NOT NULL,
                coupon_rate NUMERIC(4, 2) DEFAULT 2.50,
                ltp NUMERIC(10, 2) NOT NULL,
                ask_price NUMERIC(10, 2),
                ask_quantity INT DEFAULT 0,
                underlying_spot_price NUMERIC(10, 2) NOT NULL,
                discount_to_spot_pct NUMERIC(6, 2) NOT NULL,
                annualized_ytm_pct NUMERIC(6, 2) NOT NULL,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            """)
        else:
            # SQLite DDL
            cursor.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                full_name TEXT,
                email TEXT UNIQUE,
                phone_number TEXT UNIQUE,
                telegram_chat_id INTEGER UNIQUE,
                current_tier TEXT DEFAULT 'FREE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS user_subscriptions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                tier TEXT NOT NULL,
                status TEXT DEFAULT 'ACTIVE',
                payment_gateway TEXT DEFAULT 'MOCK',
                gateway_ref TEXT,
                amount_paid_inr REAL NOT NULL,
                starts_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS user_card_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                bank_code TEXT NOT NULL,
                card_tier_name TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                UNIQUE(user_id, bank_code, card_tier_name)
            );

            CREATE TABLE IF NOT EXISTS deal_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                platform TEXT NOT NULL,
                sku TEXT,
                brand TEXT,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                image_url TEXT,
                weight_grams REAL NOT NULL,
                purity_karat TEXT NOT NULL,
                is_jewellery INTEGER DEFAULT 0,
                selling_price REAL NOT NULL,
                coupon_code TEXT,
                coupon_discount REAL DEFAULT 0,
                bank_discount REAL DEFAULT 0,
                effective_net_price REAL NOT NULL,
                effective_price_per_gram REAL NOT NULL,
                live_spot_rate_per_gram REAL NOT NULL,
                arbitrage_spread_inr REAL NOT NULL,
                discount_vs_spot_pct REAL NOT NULL,
                is_sub_spot INTEGER DEFAULT 0,
                is_low_making INTEGER DEFAULT 0,
                stock_status TEXT DEFAULT 'IN_STOCK',
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS sgb_tranches (
                isin TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                exchange TEXT DEFAULT 'NSE',
                issue_date TEXT,
                maturity_date TEXT NOT NULL,
                issue_price REAL NOT NULL,
                coupon_rate REAL DEFAULT 2.50,
                ltp REAL NOT NULL,
                ask_price REAL,
                ask_quantity INTEGER DEFAULT 0,
                underlying_spot_price REAL NOT NULL,
                discount_to_spot_pct REAL NOT NULL,
                annualized_ytm_pct REAL NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.commit()

        cursor.close()
        if not self.use_postgres:
            conn.close()
        logger.info("Database schema initialized successfully.")

    # ---------------- USER & SUBSCRIPTION METHODS ---------------- #

    def get_or_create_user(self, user_id: str, phone: Optional[str] = None, email: Optional[str] = None, name: Optional[str] = None, telegram_chat_id: Optional[int] = None) -> Dict[str, Any]:
        conn = self.get_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM users WHERE id = %s" if self.use_postgres else "SELECT * FROM users WHERE id = ?"
        cursor.execute(query, (user_id,))
        row = cursor.fetchone()

        if row:
            user = dict(row) if not self.use_postgres else {desc[0]: val for desc, val in zip(cursor.description, row)}
            cursor.close()
            if not self.use_postgres:
                conn.close()
            return user

        # Insert new user
        insert_query = """
        INSERT INTO users (id, full_name, email, phone_number, telegram_chat_id, current_tier)
        VALUES (%s, %s, %s, %s, %s, 'FREE')
        """ if self.use_postgres else """
        INSERT INTO users (id, full_name, email, phone_number, telegram_chat_id, current_tier)
        VALUES (?, ?, ?, ?, ?, 'FREE')
        """
        cursor.execute(insert_query, (user_id, name or "Investor", email, phone, telegram_chat_id))
        if not self.use_postgres:
            conn.commit()
            conn.close()
        return {
            "id": user_id,
            "full_name": name or "Investor",
            "email": email,
            "phone_number": phone,
            "telegram_chat_id": telegram_chat_id,
            "current_tier": "FREE"
        }

    def upgrade_user_subscription(self, user_id: str, plan_id: str, amount_paid: float, gateway_ref: str = "MANUAL") -> Dict[str, Any]:
        plan = SUBSCRIPTION_PLANS.get(plan_id)
        if not plan:
            raise ValueError(f"Invalid plan ID: {plan_id}")

        duration_days = plan.get("duration_days", 30)
        target_tier = "TRADER" if "trader" in plan_id else "PRO"
        starts_at = datetime.utcnow()
        expires_at = starts_at + timedelta(days=duration_days)
        sub_id = f"sub_{int(starts_at.timestamp())}_{user_id[:8]}"

        conn = self.get_connection()
        cursor = conn.cursor()

        # Update user current_tier
        u_query = "UPDATE users SET current_tier = %s WHERE id = %s" if self.use_postgres else "UPDATE users SET current_tier = ? WHERE id = ?"
        cursor.execute(u_query, (target_tier, user_id))

        # Insert subscription record
        s_query = """
        INSERT INTO user_subscriptions (id, user_id, tier, status, amount_paid_inr, starts_at, expires_at, gateway_ref)
        VALUES (%s, %s, %s, 'ACTIVE', %s, %s, %s, %s)
        """ if self.use_postgres else """
        INSERT INTO user_subscriptions (id, user_id, tier, status, amount_paid_inr, starts_at, expires_at, gateway_ref)
        VALUES (?, ?, ?, 'ACTIVE', ?, ?, ?, ?)
        """
        cursor.execute(s_query, (sub_id, user_id, target_tier, amount_paid, starts_at.isoformat(), expires_at.isoformat(), gateway_ref))

        if not self.use_postgres:
            conn.commit()
            conn.close()

        return {
            "subscription_id": sub_id,
            "user_id": user_id,
            "tier": target_tier,
            "plan_id": plan_id,
            "starts_at": starts_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "status": "ACTIVE"
        }

    def get_user_cards(self, user_id: str) -> List[str]:
        conn = self.get_connection()
        cursor = conn.cursor()
        q = "SELECT bank_code, card_tier_name FROM user_card_profiles WHERE user_id = %s AND is_active = TRUE" if self.use_postgres else "SELECT bank_code, card_tier_name FROM user_card_profiles WHERE user_id = ? AND is_active = 1"
        cursor.execute(q, (user_id,))
        rows = cursor.fetchall()
        cards = [f"{r[0]}_{r[1]}" for r in rows]
        cursor.close()
        if not self.use_postgres:
            conn.close()
        return cards

    def set_user_cards(self, user_id: str, card_names: List[str]):
        conn = self.get_connection()
        cursor = conn.cursor()
        del_q = "DELETE FROM user_card_profiles WHERE user_id = %s" if self.use_postgres else "DELETE FROM user_card_profiles WHERE user_id = ?"
        cursor.execute(del_q, (user_id,))

        ins_q = "INSERT INTO user_card_profiles (user_id, bank_code, card_tier_name) VALUES (%s, %s, %s)" if self.use_postgres else "INSERT INTO user_card_profiles (user_id, bank_code, card_tier_name) VALUES (?, ?, ?)"
        for c in card_names:
            parts = c.split("_", 1)
            bank = parts[0]
            tier = parts[1] if len(parts) > 1 else "STANDARD"
            cursor.execute(ins_q, (user_id, bank, tier))

        if not self.use_postgres:
            conn.commit()
            conn.close()

    # ---------------- DEAL & ARBITRAGE STORAGE ---------------- #

    def save_deal_scans(self, deals: List[Dict[str, Any]]):
        if not deals:
            return
        conn = self.get_connection()
        cursor = conn.cursor()

        ins_q = """
        INSERT INTO deal_scans (
            product_id, platform, sku, brand, title, url, image_url,
            weight_grams, purity_karat, is_jewellery, selling_price,
            coupon_code, coupon_discount, bank_discount, effective_net_price,
            effective_price_per_gram, live_spot_rate_per_gram, arbitrage_spread_inr,
            discount_vs_spot_pct, is_sub_spot, is_low_making, stock_status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """ if self.use_postgres else """
        INSERT INTO deal_scans (
            product_id, platform, sku, brand, title, url, image_url,
            weight_grams, purity_karat, is_jewellery, selling_price,
            coupon_code, coupon_discount, bank_discount, effective_net_price,
            effective_price_per_gram, live_spot_rate_per_gram, arbitrage_spread_inr,
            discount_vs_spot_pct, is_sub_spot, is_low_making, stock_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        for d in deals:
            cursor.execute(ins_q, (
                d.get("product_id", ""),
                d.get("source", d.get("platform", "ajio")),
                d.get("sku", ""),
                d.get("brand", "Unknown"),
                d.get("title", ""),
                d.get("url", ""),
                d.get("image_url", ""),
                float(d.get("weight_grams", 1.0)),
                d.get("purity", "24K"),
                1 if d.get("is_jewellery") else 0,
                float(d.get("selling_price", 0)),
                d.get("coupon_code", ""),
                float(d.get("coupon_discount", 0)),
                float(d.get("bank_discount", 0)),
                float(d.get("effective_net_price", d.get("selling_price", 0))),
                float(d.get("price_per_gram", 0)),
                float(d.get("spot_price", 0)),
                float(d.get("arbitrage_spread_inr", 0)),
                float(d.get("discount_percent", 0)),
                1 if d.get("is_sub_spot") else 0,
                1 if d.get("is_low_making") else 0,
                d.get("stock_status", "IN_STOCK")
            ))

        if not self.use_postgres:
            conn.commit()
            conn.close()

    def get_sub_spot_deals(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        q = """
        SELECT * FROM deal_scans 
        WHERE is_sub_spot = 1 OR discount_vs_spot_pct > 0.5 
        ORDER BY discount_vs_spot_pct DESC, scanned_at DESC 
        LIMIT %s
        """ if self.use_postgres else """
        SELECT * FROM deal_scans 
        WHERE is_sub_spot = 1 OR discount_vs_spot_pct > 0.5 
        ORDER BY discount_vs_spot_pct DESC, scanned_at DESC 
        LIMIT ?
        """
        cursor.execute(q, (limit,))
        rows = cursor.fetchall()
        deals = []
        if self.use_postgres:
            cols = [desc[0] for desc in cursor.description]
            for r in rows:
                deals.append(dict(zip(cols, r)))
        else:
            for r in rows:
                deals.append(dict(r))

        cursor.close()
        if not self.use_postgres:
            conn.close()
        return deals

    # ---------------- SGB TRANCHES STORAGE ---------------- #

    def upsert_sgb_tranches(self, tranches: List[Dict[str, Any]]):
        if not tranches:
            return
        conn = self.get_connection()
        cursor = conn.cursor()

        q = """
        INSERT INTO sgb_tranches (
            isin, ticker, exchange, issue_date, maturity_date, issue_price,
            coupon_rate, ltp, ask_price, ask_quantity, underlying_spot_price,
            discount_to_spot_pct, annualized_ytm_pct, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT(isin) DO UPDATE SET
            ltp = EXCLUDED.ltp,
            ask_price = EXCLUDED.ask_price,
            ask_quantity = EXCLUDED.ask_quantity,
            underlying_spot_price = EXCLUDED.underlying_spot_price,
            discount_to_spot_pct = EXCLUDED.discount_to_spot_pct,
            annualized_ytm_pct = EXCLUDED.annualized_ytm_pct,
            updated_at = NOW()
        """ if self.use_postgres else """
        INSERT OR REPLACE INTO sgb_tranches (
            isin, ticker, exchange, issue_date, maturity_date, issue_price,
            coupon_rate, ltp, ask_price, ask_quantity, underlying_spot_price,
            discount_to_spot_pct, annualized_ytm_pct, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """

        for t in tranches:
            cursor.execute(q, (
                t["isin"], t["ticker"], t.get("exchange", "NSE"),
                t.get("issue_date", "2020-01-01"), t["maturity_date"],
                float(t.get("issue_price", 5000.0)), float(t.get("coupon_rate", 2.50)),
                float(t["ltp"]), float(t.get("ask_price", t["ltp"])),
                int(t.get("ask_quantity", 50)), float(t["underlying_spot_price"]),
                float(t["discount_to_spot_pct"]), float(t["annualized_ytm_pct"])
            ))

        if not self.use_postgres:
            conn.commit()
            conn.close()

    def get_sgb_tranches(self, min_discount_pct: float = -10.0) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        q = "SELECT * FROM sgb_tranches WHERE discount_to_spot_pct >= %s ORDER BY discount_to_spot_pct DESC" if self.use_postgres else "SELECT * FROM sgb_tranches WHERE discount_to_spot_pct >= ? ORDER BY discount_to_spot_pct DESC"
        cursor.execute(q, (min_discount_pct,))
        rows = cursor.fetchall()
        results = []
        if self.use_postgres:
            cols = [desc[0] for desc in cursor.description]
            for r in rows:
                results.append(dict(zip(cols, r)))
        else:
            for r in rows:
                results.append(dict(r))

        cursor.close()
        if not self.use_postgres:
            conn.close()
        return results


# Global singleton instance
db_manager = DatabaseManager()
db = db_manager
