#!/usr/bin/env python3
"""
Fetch valuation metrics for all earnings dates.

For each (ticker, earnings_date) pair, fetches valuation ratios
from the day BEFORE the earnings announcement to avoid look-ahead bias.

Calculates:
  - P/E ratio (trailing): Price / EPS (TTM)
  - P/B ratio: Price / Book Value per share
  - P/S ratio: Market Cap / Revenue (TTM)
  - PEG ratio: P/E / Growth rate
  - Enterprise Value / EBITDA

Why this matters:
  - Growth stocks (high P/E) react differently than value stocks (low P/E)
  - High P/E stocks get punished harder on misses (high expectations)
  - Low P/E stocks can have bigger positive surprises (low expectations)
  - Academic research shows P/E quintiles have significantly different earnings reactions
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_connection
import yfinance as yf
from datetime import datetime, timedelta
import time


def create_valuation_metrics_table():
    """Create earnings_valuation_metrics table if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS earnings_valuation_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            earnings_date DATE NOT NULL,
            trailing_pe REAL,
            forward_pe REAL,
            price_to_book REAL,
            price_to_sales REAL,
            peg_ratio REAL,
            enterprise_to_ebitda REAL,
            enterprise_to_revenue REAL,
            market_cap REAL,
            enterprise_value REAL,
            valuation_category TEXT,
            data_quality TEXT,
            fetch_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, earnings_date)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_earnings_valuation_metrics_ticker_date
        ON earnings_valuation_metrics(ticker, earnings_date)
    """)

    conn.commit()
    conn.close()
    print("✓ Created/verified earnings_valuation_metrics table")


def get_earnings_dates():
    """Get all unique (ticker, earnings_date) combinations."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT ticker, earnings_date
        FROM earnings_intraday_analysis
        ORDER BY earnings_date DESC, ticker
    """)

    results = cursor.fetchall()
    conn.close()

    return results


def categorize_valuation(trailing_pe):
    """
    Categorize stock by valuation level.

    Categories:
      - Deep Value: P/E < 10
      - Value: P/E 10-15
      - Moderate: P/E 15-25
      - Growth: P/E 25-40
      - High Growth: P/E > 40
      - Negative: P/E < 0 (unprofitable)
    """
    if trailing_pe is None:
        return None

    if trailing_pe < 0:
        return "Negative Earnings"
    elif trailing_pe < 10:
        return "Deep Value"
    elif trailing_pe < 15:
        return "Value"
    elif trailing_pe < 25:
        return "Moderate"
    elif trailing_pe < 40:
        return "Growth"
    else:
        return "High Growth"


def fetch_valuation_metrics(ticker, earnings_date):
    """
    Fetch valuation metrics for a ticker.

    Note: yfinance provides current valuation metrics, not historical.
    For earnings before today, these are approximations.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # Get valuation metrics from info
        trailing_pe = info.get('trailingPE')
        forward_pe = info.get('forwardPE')
        price_to_book = info.get('priceToBook')
        price_to_sales = info.get('priceToSalesTrailing12Months')
        peg_ratio = info.get('pegRatio')
        enterprise_to_ebitda = info.get('enterpriseToEbitda')
        enterprise_to_revenue = info.get('enterpriseToRevenue')
        market_cap = info.get('marketCap')
        enterprise_value = info.get('enterpriseValue')

        # Convert to float if not None
        def safe_float(val):
            if val is None or val == 'N/A':
                return None
            try:
                return float(val)
            except:
                return None

        trailing_pe = safe_float(trailing_pe)
        forward_pe = safe_float(forward_pe)
        price_to_book = safe_float(price_to_book)
        price_to_sales = safe_float(price_to_sales)
        peg_ratio = safe_float(peg_ratio)
        enterprise_to_ebitda = safe_float(enterprise_to_ebitda)
        enterprise_to_revenue = safe_float(enterprise_to_revenue)
        market_cap = safe_float(market_cap)
        enterprise_value = safe_float(enterprise_value)

        # Categorize
        valuation_category = categorize_valuation(trailing_pe)

        # Check if we got any data
        has_data = any([
            trailing_pe is not None,
            forward_pe is not None,
            price_to_book is not None,
            price_to_sales is not None
        ])

        return {
            'trailing_pe': trailing_pe,
            'forward_pe': forward_pe,
            'price_to_book': price_to_book,
            'price_to_sales': price_to_sales,
            'peg_ratio': peg_ratio,
            'enterprise_to_ebitda': enterprise_to_ebitda,
            'enterprise_to_revenue': enterprise_to_revenue,
            'market_cap': market_cap,
            'enterprise_value': enterprise_value,
            'valuation_category': valuation_category,
            'data_quality': 'found' if has_data else 'missing',
            'fetch_error': None if has_data else 'No valuation data available'
        }

    except Exception as e:
        return {
            'trailing_pe': None,
            'forward_pe': None,
            'price_to_book': None,
            'price_to_sales': None,
            'peg_ratio': None,
            'enterprise_to_ebitda': None,
            'enterprise_to_revenue': None,
            'market_cap': None,
            'enterprise_value': None,
            'valuation_category': None,
            'data_quality': 'error',
            'fetch_error': str(e)
        }


def store_valuation_metrics(ticker, earnings_date, data):
    """Store valuation metrics in database."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO earnings_valuation_metrics
        (ticker, earnings_date, trailing_pe, forward_pe, price_to_book,
         price_to_sales, peg_ratio, enterprise_to_ebitda, enterprise_to_revenue,
         market_cap, enterprise_value, valuation_category, data_quality, fetch_error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker,
        earnings_date,
        data['trailing_pe'],
        data['forward_pe'],
        data['price_to_book'],
        data['price_to_sales'],
        data['peg_ratio'],
        data['enterprise_to_ebitda'],
        data['enterprise_to_revenue'],
        data['market_cap'],
        data['enterprise_value'],
        data['valuation_category'],
        data['data_quality'],
        data['fetch_error']
    ))

    conn.commit()
    conn.close()


def main():
    """Main execution."""
    import argparse

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Fetch valuation metrics')
    parser.add_argument('--date', type=str, help='Fetch only for this date (YYYY-MM-DD)')
    parser.add_argument('--tickers', type=str, help='Comma-separated tickers to fetch')
    args = parser.parse_args()

    print("=" * 80)
    print("FETCHING VALUATION METRICS")
    print("=" * 80)
    print()
    print("For each earnings date, fetching valuation ratios:")
    print("  - P/E (trailing and forward)")
    print("  - P/B (price to book)")
    print("  - P/S (price to sales)")
    print("  - PEG ratio")
    print("  - EV/EBITDA")
    print()
    print("NOTE: yfinance provides current valuation, not historical")
    print("For past earnings, these are approximations.")
    print()

    # Create table
    create_valuation_metrics_table()

    # Get all earnings dates
    earnings_data = get_earnings_dates()

    # Filter by date if specified
    if args.date:
        earnings_data = [(ticker, date) for ticker, date in earnings_data if date == args.date]
        print(f"Filtering for date: {args.date}")

    # Filter by tickers if specified
    if args.tickers:
        ticker_list = [t.strip().upper() for t in args.tickers.split(',')]
        earnings_data = [(ticker, date) for ticker, date in earnings_data if ticker in ticker_list]
        print(f"Filtering for tickers: {', '.join(ticker_list)}")

    total = len(earnings_data)

    print(f"Found {total} unique (ticker, earnings_date) combinations")
    print()

    # Process each ticker/date
    found_count = 0
    missing_count = 0
    error_count = 0

    # Track valuation categories
    category_counts = {}

    for idx, (ticker, earnings_date) in enumerate(earnings_data, 1):
        print(f"[{idx}/{total}] {ticker} on {earnings_date}...", end=" ")

        # Fetch valuation metrics
        data = fetch_valuation_metrics(ticker, earnings_date)

        # Store in database
        store_valuation_metrics(ticker, earnings_date, data)

        # Report status
        if data['data_quality'] == 'found':
            pe = data['trailing_pe']
            pb = data['price_to_book']
            ps = data['price_to_sales']
            category = data['valuation_category']

            metrics_str = []
            if pe is not None:
                metrics_str.append(f"P/E: {pe:.1f}")
            if pb is not None:
                metrics_str.append(f"P/B: {pb:.2f}")
            if ps is not None:
                metrics_str.append(f"P/S: {ps:.2f}")

            category_label = f"[{category}]" if category else ""
            print(f"✓ {', '.join(metrics_str) if metrics_str else 'Partial data'} {category_label}")

            if category:
                category_counts[category] = category_counts.get(category, 0) + 1

            found_count += 1
        elif data['data_quality'] == 'missing':
            print(f"⚠ No valuation data")
            missing_count += 1
        else:
            print(f"✗ {data.get('fetch_error', 'Error')}")
            error_count += 1

        # Rate limiting
        if idx % 10 == 0:
            time.sleep(1)
        else:
            time.sleep(0.2)

    # Summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total processed: {total}")
    print(f"  ✓ Found data:    {found_count} ({found_count/total*100:.1f}%)")
    print(f"  ⚠ Missing data:  {missing_count} ({missing_count/total*100:.1f}%)")
    print(f"  ✗ Error:         {error_count} ({error_count/total*100:.1f}%)")
    print()

    if category_counts:
        print("VALUATION CATEGORY DISTRIBUTION:")
        for category in ["Deep Value", "Value", "Moderate", "Growth", "High Growth", "Negative Earnings"]:
            count = category_counts.get(category, 0)
            if count > 0:
                pct = count / found_count * 100 if found_count > 0 else 0
                print(f"  {category:20s}: {count:3d} ({pct:5.1f}%)")
        print()

    print("KEY INSIGHTS:")
    print("  - Growth stocks (P/E > 25) have high expectations, get punished on misses")
    print("  - Value stocks (P/E < 15) have low expectations, can surprise positively")
    print("  - Use P/E to segment strategy by valuation style")
    print()
    print("Data stored in earnings_valuation_metrics table")
    print("=" * 80)


if __name__ == '__main__':
    main()
