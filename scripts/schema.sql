-- ============================================================
-- GOLD DEAL FINDER - PRODUCTION POSTGRESQL SCHEMA (scrapper_db)
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Enums (Safe creation)
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'subscription_tier_enum') THEN
        CREATE TYPE subscription_tier_enum AS ENUM ('FREE', 'PRO', 'TRADER');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'subscription_status_enum') THEN
        CREATE TYPE subscription_status_enum AS ENUM ('ACTIVE', 'EXPIRED', 'PAST_DUE', 'CANCELLED');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'deal_type_enum') THEN
        CREATE TYPE deal_type_enum AS ENUM ('STANDARD', 'SUB_SPOT_BULLION', 'MAKING_CHARGE_GLITCH', 'HIGH_STACK_DEAL');
    END IF;
END $$;

-- 1. USERS TABLE
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(64) PRIMARY KEY,
    full_name VARCHAR(100) DEFAULT 'Gold Investor',
    email VARCHAR(255) UNIQUE,
    phone_number VARCHAR(20) UNIQUE,
    telegram_chat_id BIGINT UNIQUE,
    whatsapp_number VARCHAR(20) UNIQUE,
    current_tier subscription_tier_enum DEFAULT 'FREE',
    notify_telegram BOOLEAN DEFAULT TRUE,
    notify_whatsapp BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. SUBSCRIPTIONS TABLE
CREATE TABLE IF NOT EXISTS user_subscriptions (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tier subscription_tier_enum NOT NULL,
    status subscription_status_enum DEFAULT 'ACTIVE',
    payment_gateway VARCHAR(30) DEFAULT 'RAZORPAY',
    gateway_ref VARCHAR(100),
    amount_paid_inr NUMERIC(10, 2) NOT NULL,
    starts_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    auto_renew BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_user_sub_lookup ON user_subscriptions (user_id, status, expires_at);

-- 3. USER CREDIT CARD PROFILES
CREATE TABLE IF NOT EXISTS user_card_profiles (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    bank_code VARCHAR(30) NOT NULL,
    card_tier_name VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, bank_code, card_tier_name)
);

-- 4. MASTER PRODUCTS CATALOG
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform VARCHAR(50) NOT NULL,
    sku VARCHAR(100) NOT NULL,
    brand VARCHAR(100) NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    image_url TEXT,
    weight_grams NUMERIC(8, 3) NOT NULL,
    purity_karat VARCHAR(10) NOT NULL,
    is_jewellery BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(platform, sku)
);
CREATE INDEX IF NOT EXISTS idx_products_weight_purity ON products (weight_grams, purity_karat, is_jewellery);

-- 5. HISTORICAL DEAL SCANS & ARBITRAGE SIGNALS
CREATE TABLE IF NOT EXISTS deal_scans (
    id BIGSERIAL PRIMARY KEY,
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
    recommended_card VARCHAR(100),
    scanned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_deal_scans_arbitrage ON deal_scans (is_sub_spot, scanned_at DESC);
CREATE INDEX IF NOT EXISTS idx_deal_scans_discount ON deal_scans (discount_vs_spot_pct DESC);
CREATE INDEX IF NOT EXISTS idx_deal_scans_platform_sku ON deal_scans (platform, sku);

-- 6. SOVEREIGN GOLD BOND (SGB) TRANCHES
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
CREATE INDEX IF NOT EXISTS idx_sgb_discount ON sgb_tranches (discount_to_spot_pct DESC);

-- 7. RESTOCK & CART DROP WATCH LIST
CREATE TABLE IF NOT EXISTS restock_watch_list (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(50) NOT NULL,
    sku VARCHAR(100) NOT NULL,
    product_title TEXT NOT NULL,
    url TEXT NOT NULL,
    purity VARCHAR(10) DEFAULT '24K',
    weight_grams NUMERIC(8, 3) DEFAULT 1.0,
    target_price_threshold NUMERIC(10, 2),
    is_active BOOLEAN DEFAULT TRUE,
    last_status VARCHAR(20) DEFAULT 'OUT_OF_STOCK',
    last_checked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_restocked_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(platform, sku)
);
CREATE INDEX IF NOT EXISTS idx_restock_active ON restock_watch_list (is_active, last_status);
