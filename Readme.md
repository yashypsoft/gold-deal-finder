# 🏆 Gold Deal Finder

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg)](https://core.telegram.org/bots)

A smart web scraper that monitors e-commerce websites for gold deals, calculates accurate prices using live spot rates with GST and making charges, and sends Telegram alerts when significant discounts are found.

## ✨ Features

- **Real-time Monitoring**: Scrapes Myntra and AJIO for gold products every hour
- **Accurate Price Calculation**: Uses live gold spot prices with GST (3%) and making charges
- **Smart Filtering**: Identifies genuine discounts vs. inflated prices
- **Telegram Alerts**: Instant notifications with product details and purchase links
- **Multiple API Fallbacks**: Robust gold price fetching with redundancy
- **Scheduled Scans**: Automatic hourly checks with peak-time optimization
- **Product Intelligence**: Distinguishes between jewellery and coins with appropriate charges

## 🛠️ How It Works

1. **Scrapes** gold products from Myntra and AJIO
2. **Extracts** weight and purity from product titles
3. **Calculates** expected price using:
   - Live gold spot price
   - 3% GST
   - Making charges (3-18% based on product type)
   - Purity adjustment (24K, 22K, 18K, 14K)
4. **Compares** selling price with calculated value
5. **Sends** Telegram alerts for discounts > 5%

## 📋 Prerequisites

- Python 3.8 or higher
- Telegram account (for bot setup)
- Internet connection

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/yashypsoft/gold-deal-finder.git
cd gold-deal-finder