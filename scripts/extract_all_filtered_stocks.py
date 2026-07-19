#!/usr/bin/env python3
"""
Extract intraday data for ALL stocks that passed any filter:
- Watchlist (08:30 screener)
- Signals (09:00-09:30 live detection)
- Hypothetical trades (actual trades created)
"""

import sys
import os
from datetime import datetime, timedelta
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data.yfinance_provider import YFinanceProvider
from src.utils.database import get_connection
from src.utils.logger import setup_logger
import yfinance as yf
import time

logger = setup_logger('comprehensive_extractor', 'logs/comprehensive_extraction.log', 'INFO', console=True)

def extract_intraday(ticker, date_str):
    """Extract intraday data for a specific date."""
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        start_date = date_obj.strftime('%Y-%m-%d')
        end_date = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
        
        stock = yf.Ticker(ticker)
        df = stock.history(start=start_date, end=end_date, interval='1m')
        
        if df is None or len(df) == 0:
            return []
        
        try:
            df = df.between_time('09:00', '17:30')
        except:
            pass
        
        if len(df) == 0:
            return []
        
        # Find base price - prefer 9:00, but accept first available if not found
        base_price = None
        base_time = None

        # First try to find 09:00 or 09:01 (preferred)
        for timestamp, row in df.iterrows():
            time_str = timestamp.strftime('%H:%M')
            if time_str.startswith('09:00') or time_str.startswith('09:01'):
                base_price = row['Close']
                base_time = time_str
                break

        # If not found, use the first available datapoint
        if base_price is None:
            first_row = df.iloc[0]
            base_price = first_row['Close']
            base_time = df.index[0].strftime('%H:%M')
            logger.info(f"{ticker} {date_str}: Using {base_time} as base (09:00 not available)")

        if base_price is None or base_price == 0:
            return []
        
        # Extract normalized data
        intraday_points = []
        for timestamp, row in df.iterrows():
            time_str = timestamp.strftime('%H:%M')
            price = row['Close']
            if price > 0:
                normalized_price = (price / base_price) * 100
                intraday_points.append({
                    'time': time_str,
                    'price': float(price),
                    'normalized_price': float(normalized_price),
                    'base_price': float(base_price)
                })
        
        return intraday_points
        
    except Exception as e:
        logger.error(f"Error extracting {ticker} {date_str}: {e}")
        return []

def save_intraday_data(ticker, date, intraday_data, passed_filter, created_signal, filter_score=100.0):
    """Save intraday data to database."""
    if not intraday_data:
        return 0
    
    conn = get_connection()
    cursor = conn.cursor()
    
    saved_count = 0
    for point in intraday_data:
        try:
            timestamp = f"{date} {point['time']}:00"
            cursor.execute("""
                INSERT OR REPLACE INTO earnings_intraday_analysis
                (ticker, earnings_date, time_of_day, timestamp, price,
                 normalized_price, base_price, filter_score, passed_filter, created_signal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker, date, point['time'], timestamp, point['price'],
                point['normalized_price'], point['base_price'], 
                filter_score, passed_filter, created_signal
            ))
            saved_count += 1
        except Exception as e:
            logger.error(f"Error saving {ticker} {date} {point['time']}: {e}")
    
    conn.commit()
    conn.close()
    
    return saved_count

def main():
    print("=" * 80)
    print("EXTRACTING ALL FILTERED STOCKS FROM ALL SOURCES")
    print("=" * 80)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get ALL unique (ticker, date) combinations from all sources
    cursor.execute("""
        SELECT DISTINCT ticker, date FROM (
            SELECT ticker, date FROM watchlist
            UNION
            SELECT ticker, DATE(signal_time) as date FROM signals
            UNION
            SELECT ticker, date FROM hypothetical_trades
        )
        ORDER BY date DESC, ticker
    """)
    
    all_entries = cursor.fetchall()
    print(f"Found {len(all_entries)} unique (ticker, date) combinations\n")
    
    total_extracted = 0
    total_saved = 0
    
    for i, (ticker, date) in enumerate(all_entries, 1):
        print(f"[{i}/{len(all_entries)}] {ticker} on {date}...")
        
        # Check if trade was created
        cursor.execute("""
            SELECT COUNT(*) FROM hypothetical_trades
            WHERE ticker = ? AND date = ?
        """, (ticker, date))
        created_signal = cursor.fetchone()[0] > 0
        
        # Extract intraday data
        intraday_data = extract_intraday(ticker, date)
        
        if intraday_data:
            saved = save_intraday_data(
                ticker, date, intraday_data,
                passed_filter=True,  # In any source = passed filter
                created_signal=created_signal,
                filter_score=100.0
            )
            signal_mark = " ✓ SIGNAL" if created_signal else ""
            print(f"  → Saved {saved} points{signal_mark}")
            total_extracted += 1
            total_saved += saved
        else:
            print(f"  → No intraday data available")
        
        time.sleep(0.5)  # Rate limiting
    
    conn.close()
    
    print("\n" + "=" * 80)
    print(f"COMPLETE: Extracted {total_extracted} stocks, saved {total_saved} data points")
    print("=" * 80)

if __name__ == '__main__':
    main()
