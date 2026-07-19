#!/usr/bin/env python3
"""
Out-of-sample EOD-EOD Backtest — Config #1 & Config #2.

Strategy: Buy at yesterday's close (day before earnings announcement),
          sell at a random time within each config's optimal sell-time interval.

Test set: Feb 26 – Mar 13, 2026 (not used in optimization — new data only).

Config #1 (quality/sentiment screen):
  - min_volatility_20d     : 0.1825
  - max_upside_to_mean_tgt : 40.0325
  - max_position_in_range  : 0.175
  - Sell interval          : 16:10 – 16:45

Config #2 (analyst-momentum):
  - min_volatility_20d     : 0.41
  - max_position_in_range  : 0.385
  - min_volume_trend_ratio : 0.37
  - min_avg_rating         : 1.00
  - Sell interval          : 16:15 – 16:50

Note: min_sod_increase is excluded — it requires information not available
      at buy time (EOD the day before).

Fee: 1% per stock (round-trip).
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.database import get_connection
import yfinance as yf
import random
import time
from datetime import datetime, timedelta
from collections import defaultdict

# ── Configuration ─────────────────────────────────────────────────────────────

TEST_DATES = [
    '2026-02-26', '2026-02-27',
    '2026-03-04', '2026-03-05', '2026-03-06',
    '2026-03-10', '2026-03-11', '2026-03-12', '2026-03-13',
]
FEE_PCT    = 1.0   # round-trip fee per stock

CONFIGS = {
    'Config #1': {
        'min_volatility_20d':        0.1825,
        'max_upside_to_mean_target': 40.0325,
        'max_position_in_range':     0.175,
        'sell_start':                '16:10',
        'sell_end':                  '16:45',
    },
    'Config #2': {
        'min_volatility_20d':        0.41,
        'max_position_in_range':     0.385,
        'min_volume_trend_ratio':    0.37,
        'min_avg_rating':            1.00,
        'sell_start':                '16:15',
        'sell_end':                  '16:50',
    },
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def time_to_minutes(t):
    h, m = map(int, t.split(':'))
    return h * 60 + m


def random_sell_time(sell_start, sell_end):
    """Pick a random minute (as HH:MM) within [sell_start, sell_end] inclusive."""
    lo = time_to_minutes(sell_start)
    hi = time_to_minutes(sell_end)
    mins = random.randint(lo, hi)
    return f"{mins // 60:02d}:{mins % 60:02d}"


def closest_price(intraday_prices, target_time):
    """
    Find the actual price closest to target_time in the intraday dict.
    intraday_prices: {HH:MM -> actual_price}
    Returns (actual_time_str, price) or (None, None).
    """
    if not intraday_prices:
        return None, None
    target_mins = time_to_minutes(target_time)
    best_time, best_price, best_diff = None, None, float('inf')
    for t, p in intraday_prices.items():
        diff = abs(time_to_minutes(t) - target_mins)
        if diff < best_diff:
            best_diff, best_time, best_price = diff, t, p
    # Accept if within 5 minutes
    if best_diff <= 5:
        return best_time, best_price
    return None, None


# ── Data loading ──────────────────────────────────────────────────────────────

def load_intraday(dates):
    """Load actual intraday prices for the test dates.
    Returns {(ticker, date): {HH:MM: actual_price}}
    """
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ','.join('?' * len(dates))
    cursor.execute(f"""
        SELECT ticker, earnings_date, time_of_day, price
        FROM earnings_intraday_analysis
        WHERE earnings_date IN ({placeholders})
        ORDER BY ticker, earnings_date, time_of_day
    """, dates)
    data = defaultdict(dict)
    for ticker, date, time_str, price in cursor.fetchall():
        data[(ticker, date)][time_str] = price
    conn.close()
    return data


def load_filter_data(dates):
    """Load all filter-relevant columns for the test dates.
    Returns {(ticker, date): {col: value}}
    """
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ','.join('?' * len(dates))

    rows = {}

    # volatility
    cursor.execute(f"""
        SELECT ticker, earnings_date, volatility_20d
        FROM earnings_volatility
        WHERE earnings_date IN ({placeholders})
    """, dates)
    for ticker, date, v20 in cursor.fetchall():
        rows.setdefault((ticker, date), {})['volatility_20d'] = v20

    # 52-week position
    cursor.execute(f"""
        SELECT ticker, earnings_date, position_in_range
        FROM earnings_52week_position
        WHERE earnings_date IN ({placeholders})
    """, dates)
    for ticker, date, pos in cursor.fetchall():
        rows.setdefault((ticker, date), {})['position_in_range'] = pos

    # volume trend
    cursor.execute(f"""
        SELECT ticker, earnings_date, volume_trend_ratio
        FROM earnings_volume
        WHERE earnings_date IN ({placeholders})
    """, dates)
    for ticker, date, ratio in cursor.fetchall():
        rows.setdefault((ticker, date), {})['volume_trend_ratio'] = ratio

    # analyst coverage (avg_rating + upside_to_mean_target)
    cursor.execute(f"""
        SELECT ticker, earnings_date, avg_rating, upside_to_mean_target
        FROM earnings_analyst_coverage
        WHERE earnings_date IN ({placeholders})
    """, dates)
    for ticker, date, rating, upside in cursor.fetchall():
        rows.setdefault((ticker, date), {})['avg_rating'] = rating
        rows.setdefault((ticker, date), {})['upside_to_mean_target'] = upside

    conn.close()
    return rows


def fetch_prev_close(ticker, earnings_date_str):
    """Fetch previous trading day close from yfinance.
    Returns float or None.
    """
    try:
        date_obj = datetime.strptime(earnings_date_str, '%Y-%m-%d')
        start = (date_obj - timedelta(days=7)).strftime('%Y-%m-%d')
        end   = date_obj.strftime('%Y-%m-%d')   # exclusive
        hist = yf.Ticker(ticker).history(start=start, end=end, interval='1d')
        if hist.empty:
            return None
        return float(hist['Close'].iloc[-1])
    except Exception:
        return None


# ── Filter ────────────────────────────────────────────────────────────────────

def passes_filter(fdata, cfg):
    """Return True if this stock's filter data satisfies the config criteria."""

    v20  = fdata.get('volatility_20d')
    pos  = fdata.get('position_in_range')
    vol  = fdata.get('volume_trend_ratio')
    rtg  = fdata.get('avg_rating')
    ups  = fdata.get('upside_to_mean_target')

    min_vol   = cfg.get('min_volatility_20d')
    max_pos   = cfg.get('max_position_in_range')
    min_vtr   = cfg.get('min_volume_trend_ratio')
    min_rtg   = cfg.get('min_avg_rating')
    max_ups   = cfg.get('max_upside_to_mean_target')

    if min_vol is not None:
        if v20 is None or v20 < min_vol:
            return False
    if max_pos is not None:
        if pos is None or pos > max_pos:
            return False
    if min_vtr is not None:
        if vol is None or vol < min_vtr:
            return False
    if min_rtg is not None:
        if rtg is None or rtg < min_rtg:
            return False
    if max_ups is not None:
        if ups is None or ups > max_ups:
            return False

    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    random.seed(42)   # reproducible random sell times

    print("=" * 72)
    print("EOD-EOD OUT-OF-SAMPLE BACKTEST")
    print("=" * 72)
    print(f"Test dates : {', '.join(TEST_DATES)}")
    print(f"Fee        : {FEE_PCT}% per stock (round-trip)")
    print()

    # ── Load data ─────────────────────────────────────────────────────────────
    print("Loading intraday and filter data from database...")
    intraday  = load_intraday(TEST_DATES)
    filt_data = load_filter_data(TEST_DATES)
    all_keys  = sorted(intraday.keys())
    print(f"  {len(all_keys)} (ticker, date) pairs with intraday data\n")

    # ── Run each config ────────────────────────────────────────────────────────
    for cfg_name, cfg in CONFIGS.items():
        print("=" * 72)
        print(f"  {cfg_name.upper()}")
        print("=" * 72)
        for k, v in cfg.items():
            if k not in ('sell_start', 'sell_end'):
                print(f"  {k:<30} {v}")
        print(f"  {'sell_interval':<30} {cfg['sell_start']} – {cfg['sell_end']}")
        print()

        # ── Filter stocks ──────────────────────────────────────────────────────
        candidates = [
            (ticker, date) for (ticker, date) in all_keys
            if passes_filter(filt_data.get((ticker, date), {}), cfg)
        ]
        print(f"  Stocks passing filter : {len(candidates)}")

        if not candidates:
            print("  No stocks — skipping.\n")
            continue

        # ── Fetch yesterday_close and calculate returns ────────────────────────
        print(f"  Fetching yesterday_close from yfinance...\n")

        results = []
        skipped = 0

        for idx, (ticker, date) in enumerate(candidates, 1):
            print(f"    [{idx:2d}/{len(candidates)}] {ticker} ({date})...", end=' ', flush=True)

            # 1. Yesterday's close = buy price
            prev_close = fetch_prev_close(ticker, date)
            if prev_close is None:
                print("no prev_close — skip")
                skipped += 1
                time.sleep(0.2)
                continue

            # 2. Random sell time in interval
            sell_time = random_sell_time(cfg['sell_start'], cfg['sell_end'])

            # 3. Sell price from intraday data
            prices = intraday.get((ticker, date), {})
            actual_time, sell_price = closest_price(prices, sell_time)

            if sell_price is None:
                print(f"no intraday price near {sell_time} — skip")
                skipped += 1
                time.sleep(0.2)
                continue

            # 4. Return calculation (EOD → intraday sell)
            raw_return = (sell_price - prev_close) / prev_close * 100
            net_return = raw_return - FEE_PCT

            results.append({
                'ticker':     ticker,
                'date':       date,
                'prev_close': prev_close,
                'sell_time':  actual_time,
                'sell_price': sell_price,
                'raw_return': raw_return,
                'net_return': net_return,
            })

            sign = '+' if net_return >= 0 else ''
            print(f"buy={prev_close:.2f}  sell@{actual_time}={sell_price:.2f}  "
                  f"net={sign}{net_return:.2f}%")
            time.sleep(0.3)

        # ── Summary ────────────────────────────────────────────────────────────
        print()
        if not results:
            print("  No valid results.\n")
            continue

        total_return = sum(r['net_return'] for r in results)
        avg_return   = total_return / len(results)
        winners      = sum(1 for r in results if r['net_return'] > 0)
        losers       = len(results) - winners

        print("-" * 72)
        print(f"  {cfg_name} RESULTS")
        print("-" * 72)
        print(f"  Stocks traded      : {len(results)}  (skipped: {skipped})")
        print(f"  Winners / Losers   : {winners} / {losers}")
        print(f"  Total return       : {total_return:+.2f}%")
        print(f"  Avg return/stock   : {avg_return:+.2f}%")
        print()

        # Per-date breakdown
        by_date = defaultdict(list)
        for r in results:
            by_date[r['date']].append(r['net_return'])
        for d in sorted(by_date):
            d_total = sum(by_date[d])
            d_avg   = d_total / len(by_date[d])
            print(f"  {d}  {len(by_date[d]):3d} stocks  "
                  f"total={d_total:+.2f}%  avg={d_avg:+.2f}%")

        # Top 5 and bottom 5
        sorted_r = sorted(results, key=lambda x: x['net_return'], reverse=True)
        print()
        print("  Top 5:")
        for r in sorted_r[:5]:
            print(f"    {r['ticker']:<18} {r['date']}  {r['net_return']:+.2f}%")
        print("  Bottom 5:")
        for r in sorted_r[-5:]:
            print(f"    {r['ticker']:<18} {r['date']}  {r['net_return']:+.2f}%")
        print()


if __name__ == '__main__':
    main()
