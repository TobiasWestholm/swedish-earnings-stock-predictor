"""
Coarse-to-fine grid search to find optimal earnings trading parameters.

This script performs an iterative grid search:
1. Round 1: Coarse grid covering full parameter space (fast)
2. Round 2+: Fine grid around top configurations from previous round
3. Continues until convergence or max rounds reached

Profit is calculated as the sum of individual stock returns.

OPTIMIZATION: All intraday data is preloaded into memory once at startup,
eliminating millions of redundant database queries during grid search.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_connection
import numpy as np
from datetime import datetime
from itertools import product
import json
import copy
import time
import multiprocessing
from functools import partial

# Global variable to hold preloaded data for multiprocessing workers
_global_data = None


def time_to_minutes(time_str):
    """Convert HH:MM to minutes since midnight."""
    if time_str is None:
        return None
    h, m = map(int, time_str.split(':'))
    return h * 60 + m


def minutes_to_time(minutes):
    """Convert minutes since midnight to HH:MM."""
    if minutes is None:
        return None
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def preload_all_data():
    """Preload ALL intraday data and fundamentals into memory once (MAJOR SPEED OPTIMIZATION)."""
    print("Preloading all intraday data and fundamentals into memory...")
    start_time = time.time()

    conn = get_connection()
    cursor = conn.cursor()

    # Get all intraday data in one query
    cursor.execute("""
        SELECT ticker, earnings_date, time_of_day, normalized_price, price
        FROM earnings_intraday_analysis
        ORDER BY ticker, earnings_date, time_of_day
    """)

    all_data = {}
    row_count = 0

    for ticker, earnings_date, time_str, normalized_price, actual_price in cursor.fetchall():
        key = (ticker, earnings_date)
        if key not in all_data:
            all_data[key] = {
                'prices': {},
                'actual_prices': {}
            }
        all_data[key]['prices'][time_str] = normalized_price
        all_data[key]['actual_prices'][time_str] = actual_price
        row_count += 1

    # Get all fundamentals in one query
    cursor.execute("""
        SELECT ticker, earnings_date, yesterday_close, return_1m, return_3m, return_1y, sma_200
        FROM earnings_fundamentals
    """)

    fundamentals_count = 0
    for ticker, earnings_date, yesterday_close, return_1m, return_3m, return_1y, sma_200 in cursor.fetchall():
        key = (ticker, earnings_date)
        if key in all_data:
            all_data[key]['fundamentals'] = {
                'yesterday_close': yesterday_close,
                'return_1m': return_1m,
                'return_3m': return_3m,
                'return_1y': return_1y,
                'sma_200': sma_200
            }
            fundamentals_count += 1

    # Get 52-week position data
    cursor.execute("""
        SELECT ticker, earnings_date, position_in_range, distance_from_high_pct,
               distance_from_low_pct, weeks_since_high, weeks_since_low
        FROM earnings_52week_position
    """)

    pos52w_count = 0
    for row in cursor.fetchall():
        ticker, earnings_date, position_in_range, distance_from_high_pct, distance_from_low_pct, weeks_since_high, weeks_since_low = row
        key = (ticker, earnings_date)
        if key in all_data:
            all_data[key]['position_52w'] = {
                'position_in_range': position_in_range,
                'distance_from_high_pct': distance_from_high_pct,
                'distance_from_low_pct': distance_from_low_pct,
                'weeks_since_high': weeks_since_high,
                'weeks_since_low': weeks_since_low
            }
            pos52w_count += 1

    # Get market cap & liquidity data
    cursor.execute("""
        SELECT ticker, earnings_date, market_cap_usd, liquidity_score,
               dollar_volume_daily, avg_volume_10d
        FROM market_cap_liquidity
    """)

    liquidity_count = 0
    for row in cursor.fetchall():
        ticker, earnings_date, market_cap_usd, liquidity_score, dollar_volume_daily, avg_volume_10d = row
        key = (ticker, earnings_date)
        if key in all_data:
            all_data[key]['liquidity'] = {
                'market_cap_usd': market_cap_usd,
                'liquidity_score': liquidity_score,
                'dollar_volume_daily': dollar_volume_daily,
                'avg_volume_10d': avg_volume_10d
            }
            liquidity_count += 1

    # Get volatility data
    cursor.execute("""
        SELECT ticker, earnings_date, volatility_20d, volatility_60d, volatility_252d
        FROM earnings_volatility
    """)

    volatility_count = 0
    for row in cursor.fetchall():
        ticker, earnings_date, volatility_20d, volatility_60d, volatility_252d = row
        key = (ticker, earnings_date)
        if key in all_data:
            all_data[key]['volatility'] = {
                'volatility_20d': volatility_20d,
                'volatility_60d': volatility_60d,
                'volatility_252d': volatility_252d
            }
            volatility_count += 1

    # Get valuation data
    cursor.execute("""
        SELECT ticker, earnings_date, trailing_pe, price_to_book, price_to_sales, valuation_category
        FROM earnings_valuation_metrics
    """)

    valuation_count = 0
    for row in cursor.fetchall():
        ticker, earnings_date, trailing_pe, price_to_book, price_to_sales, valuation_category = row
        key = (ticker, earnings_date)
        if key in all_data:
            all_data[key]['valuation'] = {
                'trailing_pe': trailing_pe,
                'price_to_book': price_to_book,
                'price_to_sales': price_to_sales,
                'valuation_category': valuation_category
            }
            valuation_count += 1

    # Get volume data
    cursor.execute("""
        SELECT ticker, earnings_date, volume_trend_ratio, avg_volume_20d,
               avg_volume_60d, avg_volume_252d, day_before_volume
        FROM earnings_volume
    """)

    volume_count = 0
    for row in cursor.fetchall():
        ticker, earnings_date, vol_trend, avg_vol_20d, avg_vol_60d, avg_vol_252d, day_before = row
        key = (ticker, earnings_date)
        if key in all_data:
            all_data[key]['volume'] = {
                'volume_trend_ratio': vol_trend,
                'avg_volume_20d': avg_vol_20d,
                'avg_volume_60d': avg_vol_60d,
                'avg_volume_252d': avg_vol_252d,
                'day_before_volume': day_before
            }
            volume_count += 1

    # Get earnings surprise data
    cursor.execute("""
        SELECT ticker, earnings_date, eps_actual, eps_estimate,
               eps_difference, surprise_percent
        FROM earnings_surprise
    """)

    surprise_count = 0
    for row in cursor.fetchall():
        ticker, earnings_date, eps_actual, eps_estimate, eps_diff, surprise_pct = row
        key = (ticker, earnings_date)
        if key in all_data:
            all_data[key]['surprise'] = {
                'eps_actual': eps_actual,
                'eps_estimate': eps_estimate,
                'eps_difference': eps_diff,
                'surprise_percent': surprise_pct
            }
            surprise_count += 1

    # Get historical patterns data
    cursor.execute("""
        SELECT ticker, earnings_date, win_rate, avg_abs_return,
               max_positive_return, max_negative_return,
               directional_consistency, earnings_count
        FROM historical_earnings_patterns
    """)

    patterns_count = 0
    for row in cursor.fetchall():
        ticker, earnings_date, win_rate, avg_abs, max_pos, max_neg, dir_con, earn_count = row
        key = (ticker, earnings_date)
        if key in all_data:
            all_data[key]['patterns'] = {
                'win_rate': win_rate,
                'avg_abs_return': avg_abs,
                'max_positive_return': max_pos,
                'max_negative_return': max_neg,
                'directional_consistency': dir_con,
                'earnings_count': earn_count
            }
            patterns_count += 1

    # Get analyst coverage data
    cursor.execute("""
        SELECT ticker, earnings_date, num_analysts, avg_rating,
               eps_current_year, eps_forward,
               target_price_current, target_price_high, target_price_low,
               target_price_mean, target_price_median,
               upside_to_mean_target,
               strong_buy_count, buy_count, hold_count, sell_count, strong_sell_count
        FROM earnings_analyst_coverage
    """)

    analyst_count = 0
    for row in cursor.fetchall():
        (ticker, earnings_date, num_analysts, avg_rating,
         eps_current_year, eps_forward,
         target_price_current, target_price_high, target_price_low,
         target_price_mean, target_price_median,
         upside_to_mean_target,
         strong_buy_count, buy_count, hold_count, sell_count, strong_sell_count) = row
        key = (ticker, earnings_date)
        if key in all_data:
            all_data[key]['analyst'] = {
                'num_analysts': num_analysts,
                'avg_rating': avg_rating,
                'eps_current_year': eps_current_year,
                'eps_forward': eps_forward,
                'target_price_current': target_price_current,
                'target_price_high': target_price_high,
                'target_price_low': target_price_low,
                'target_price_mean': target_price_mean,
                'target_price_median': target_price_median,
                'upside_to_mean_target': upside_to_mean_target,
                'strong_buy_count': strong_buy_count,
                'buy_count': buy_count,
                'hold_count': hold_count,
                'sell_count': sell_count,
                'strong_sell_count': strong_sell_count,
            }
            analyst_count += 1

    conn.close()

    elapsed = time.time() - start_time
    print(f"  Loaded {row_count:,} data points for {len(all_data):,} stocks in {elapsed:.2f}s")
    print(f"  Loaded {fundamentals_count:,} fundamental records")
    print(f"  Loaded {pos52w_count:,} 52-week position records")
    print(f"  Loaded {liquidity_count:,} liquidity records")
    print(f"  Loaded {volatility_count:,} volatility records")
    print(f"  Loaded {valuation_count:,} valuation records")
    print(f"  Loaded {volume_count:,} volume records")
    print(f"  Loaded {surprise_count:,} earnings surprise records")
    print(f"  Loaded {patterns_count:,} historical pattern records")
    print(f"  Loaded {analyst_count:,} analyst coverage records")
    print(f"  Memory footprint: ~{len(all_data)} stocks × ~{row_count//len(all_data) if all_data else 0} time points")
    print()

    return all_data


def get_stocks_by_early_gain(all_data, min_gain_pct, max_gain_pct, start_time, end_time):
    """Get stocks matching gain criteria (works on preloaded data)."""
    start_minutes = time_to_minutes(start_time)
    end_minutes = time_to_minutes(end_time)
    tolerance_minutes = 5

    results = []

    for (ticker, earnings_date), stock_data in all_data.items():
        time_data = stock_data['prices']

        # Find closest time to start_time
        start_price = None
        min_start_diff = float('inf')
        for time_str, price in time_data.items():
            time_mins = time_to_minutes(time_str)
            diff = abs(time_mins - start_minutes)
            if diff <= tolerance_minutes and diff < min_start_diff:
                min_start_diff = diff
                start_price = price

        # Find closest time to end_time
        end_price = None
        min_end_diff = float('inf')
        for time_str, price in time_data.items():
            time_mins = time_to_minutes(time_str)
            diff = abs(time_mins - end_minutes)
            if diff <= tolerance_minutes and diff < min_end_diff:
                min_end_diff = diff
                end_price = price

        if start_price is not None and end_price is not None:
            gain = end_price - start_price
            if min_gain_pct is None or gain >= min_gain_pct:
                if max_gain_pct is None or gain <= max_gain_pct:
                    results.append((ticker, earnings_date, gain))

    return results


def calculate_total_profit(all_data, params):
    """Calculate total profit (sum of individual stock returns) - works on preloaded data."""
    # Unpack parameters
    min_gain_pct = params['min_gain_pct']
    max_gain_pct = params['max_gain_pct']
    start_time = params['start_time']
    end_time = params['end_time']
    buy_time = params['buy_time']
    sell_time = params['sell_time']
    profit_target = params['profit_target']
    stop_loss = params['stop_loss']
    max_buy_increase = params['max_buy_increase']
    max_buy_decrease = params['max_buy_decrease']
    min_buy_increase = params['min_buy_increase']
    min_data_points = params['min_data_points']
    max_data_points = params['max_data_points']
    min_sod_increase = params.get('min_sod_increase')
    min_return_1m = params.get('min_return_1m')
    min_return_3m = params.get('min_return_3m')
    min_sma200_ratio = params.get('min_sma200_ratio')

    # Advanced fundamental filters (correlation-based)
    max_position_in_range = params.get('max_position_in_range')
    min_liquidity_score = params.get('min_liquidity_score')
    min_volatility_20d = params.get('min_volatility_20d')
    min_volatility_60d = params.get('min_volatility_60d')
    min_volatility_252d = params.get('min_volatility_252d')
    max_return_1y = params.get('max_return_1y')
    min_return_1y = params.get('min_return_1y')
    max_trailing_pe = params.get('max_trailing_pe')
    min_trailing_pe = params.get('min_trailing_pe')

    # Volume filters
    min_volume_trend_ratio = params.get('min_volume_trend_ratio')
    min_avg_volume_20d = params.get('min_avg_volume_20d')

    # Earnings surprise filters
    min_surprise_percent = params.get('min_surprise_percent')
    max_surprise_percent = params.get('max_surprise_percent')

    # Historical pattern filters
    min_earnings_count = params.get('min_earnings_count')
    max_historical_volatility = params.get('max_historical_volatility')

    # Analyst coverage filters (sorted by |corr| with earnings_day_return)
    min_avg_rating = params.get('min_avg_rating')          # corr=+0.180, p=0.0236*
    max_avg_rating = params.get('max_avg_rating')          # corr=+0.180, p=0.0236*
    min_upside_to_mean_target = params.get('min_upside_to_mean_target')  # corr=-0.143, p=0.0632.
    max_upside_to_mean_target = params.get('max_upside_to_mean_target')  # corr=-0.143, p=0.0632.
    min_strong_buy_count = params.get('min_strong_buy_count')            # corr=+0.121, p=0.1073
    min_hold_count = params.get('min_hold_count')                        # corr=+0.089, p=0.2368
    min_buy_count = params.get('min_buy_count')                          # corr=+0.068, p=0.3706
    min_eps_current_year = params.get('min_eps_current_year')            # corr=+0.067, p=0.4065
    min_num_analysts = params.get('min_num_analysts')                    # corr=+0.055, p=0.4734
    min_target_price_low = params.get('min_target_price_low')            # corr=+0.055, p=0.4748
    min_target_price_mean = params.get('min_target_price_mean')          # corr=+0.037, p=0.6299
    min_target_price_high = params.get('min_target_price_high')          # corr=+0.019, p=0.8019
    max_strong_sell_count = params.get('max_strong_sell_count')          # corr=+0.019, p=0.8007
    max_sell_count = params.get('max_sell_count')                        # corr=-0.017, p=0.8236
    min_eps_forward = params.get('min_eps_forward')                      # corr=+0.016, p=0.8270

    # Get stocks matching selection criteria (from preloaded data)
    stocks = get_stocks_by_early_gain(all_data, min_gain_pct, max_gain_pct, start_time, end_time)

    if not stocks:
        return None, 0, 0, "No stocks found"

    # Build subset of data for matching stocks
    stock_data = {}
    for ticker, earnings_date, gain in stocks:
        key = (ticker, earnings_date)
        if key in all_data:
            stock_data[key] = all_data[key]

    # Filter by datapoints (Percentiles: 10th=2, 25th=7, 50th=20, 75th=43, 90th=56 in 09:00-10:00 window)
    if min_data_points is not None or max_data_points is not None:
        buy_minutes = time_to_minutes(buy_time)

        if buy_minutes < 600:
            count_start_minutes = 540
        else:
            count_start_minutes = buy_minutes - 60

        count_end_minutes = buy_minutes

        filtered_data = {}
        for key, data in stock_data.items():
            count = 0
            for time_str in data['prices'].keys():
                time_mins = time_to_minutes(time_str)
                if count_start_minutes <= time_mins <= count_end_minutes:
                    count += 1

            passes_min = min_data_points is None or count >= min_data_points
            passes_max = max_data_points is None or count <= max_data_points

            if passes_min and passes_max:
                filtered_data[key] = data

        stock_data = filtered_data

    if not stock_data:
        return None, 0, 0, "No stocks after datapoint filter"

    # Filter by fundamentals
    if any([min_sod_increase is not None, min_return_1m is not None, min_return_3m is not None,
            min_sma200_ratio is not None]):

        filtered_data = {}
        for key, data in stock_data.items():
            # Check if fundamentals exist
            if 'fundamentals' not in data:
                continue

            fundamentals = data['fundamentals']
            yesterday_close = fundamentals['yesterday_close']
            return_1m = fundamentals['return_1m']
            return_3m = fundamentals['return_3m']
            return_1y = fundamentals['return_1y']
            sma_200 = fundamentals['sma_200']

            # Calculate SOD increase: gap from yesterday_close to first intraday price on earnings day
            if min_sod_increase is not None:
                if not data['actual_prices']:
                    continue

                first_time = min(data['actual_prices'].keys())
                price_sod = data['actual_prices'][first_time]
                sod_increase = ((price_sod - yesterday_close) / yesterday_close) * 100

                if sod_increase < min_sod_increase:
                    continue

            # Check 1-month return (Percentiles: 10th=-19%, 25th=-12%, 50th=-4%, 75th=1%, 90th=9%)
            if min_return_1m is not None:
                if return_1m is None or return_1m < min_return_1m:
                    continue

            # Check 3-month return (Percentiles: 10th=-31%, 25th=-15%, 50th=-3%, 75th=7%, 90th=23%)
            if min_return_3m is not None:
                if return_3m is None or return_3m < min_return_3m:
                    continue

            # Check SMA200 ratio (Percentiles: 10th=-39%, 25th=-21%, 50th=-10%, 75th=4%, 90th=16%)
            # Positive = above 200-day SMA, Negative = below 200-day SMA
            if min_sma200_ratio is not None:
                if sma_200 is None or yesterday_close is None:
                    continue
                sma200_ratio = ((yesterday_close / sma_200) - 1) * 100
                if sma200_ratio < min_sma200_ratio:
                    continue

            filtered_data[key] = data

        stock_data = filtered_data

    if not stock_data:
        return None, 0, 0, "No stocks after fundamental filter"

    # Filter by advanced fundamentals (correlation-based)
    if any([max_position_in_range is not None, min_liquidity_score is not None,
            min_volatility_20d is not None, min_volatility_60d is not None,
            min_volatility_252d is not None, max_return_1y is not None,
            min_return_1y is not None, max_trailing_pe is not None,
            min_trailing_pe is not None, min_volume_trend_ratio is not None,
            min_avg_volume_20d is not None, min_surprise_percent is not None,
            max_surprise_percent is not None, min_earnings_count is not None,
            max_historical_volatility is not None,
            min_avg_rating is not None, max_avg_rating is not None,
            min_upside_to_mean_target is not None, max_upside_to_mean_target is not None,
            min_strong_buy_count is not None, min_hold_count is not None,
            min_buy_count is not None, min_eps_current_year is not None,
            min_num_analysts is not None, min_target_price_low is not None,
            min_target_price_mean is not None, min_target_price_high is not None,
            max_strong_sell_count is not None, max_sell_count is not None,
            min_eps_forward is not None]):

        filtered_data = {}
        for key, data in stock_data.items():
            # 52-week position filter (Percentiles: 10th=0.01, 25th=0.07, 50th=0.28, 75th=0.57, 90th=0.80)
            # Stocks near 52w highs have LOWER earnings returns (correlation: -0.198)
            if max_position_in_range is not None:
                if 'position_52w' not in data:
                    continue
                position_in_range = data['position_52w']['position_in_range']
                if position_in_range is None or position_in_range > max_position_in_range:
                    continue

            # Liquidity filter (Percentiles: 10th=0, 25th=4, 50th=17, 75th=31, 90th=45)
            # Tradability filter: Filter out illiquid stocks that can't be traded (not predictive)
            if min_liquidity_score is not None:
                if 'liquidity' not in data:
                    continue
                liquidity_score = data['liquidity']['liquidity_score']
                if liquidity_score is None or liquidity_score < min_liquidity_score:
                    continue

            # Volatility filter (Percentiles: 10th=0.21, 25th=0.28, 50th=0.41, 75th=0.61, 90th=1.06)
            # Higher volatility stocks have HIGHER earnings returns
            # volatility_20d: corr=+0.162, p=0.0059**
            if min_volatility_20d is not None:
                if 'volatility' not in data:
                    continue
                volatility_20d = data['volatility']['volatility_20d']
                if volatility_20d is None or volatility_20d < min_volatility_20d:
                    continue

            # volatility_60d: corr=+0.123, p=0.0374*
            if min_volatility_60d is not None:
                if 'volatility' not in data:
                    continue
                volatility_60d = data['volatility']['volatility_60d']
                if volatility_60d is None or volatility_60d < min_volatility_60d:
                    continue

            # volatility_252d: corr=-0.013, p=0.8232 (no signal)
            if min_volatility_252d is not None:
                if 'volatility' not in data:
                    continue
                volatility_252d = data['volatility']['volatility_252d']
                if volatility_252d is None or volatility_252d < min_volatility_252d:
                    continue

            # 1-year return filter (Percentiles: 10th=-61%, 25th=-34%, 50th=-9%, 75th=16%, 90th=79%)
            # Mean reversion strategy: stocks DOWN over the past year outperform on earnings
            if max_return_1y is not None:
                if 'fundamentals' not in data:
                    continue
                return_1y = data['fundamentals']['return_1y']
                if return_1y is None or return_1y > max_return_1y:
                    continue

            # 1-year return floor: avoid extreme losers
            if min_return_1y is not None:
                if 'fundamentals' not in data:
                    continue
                return_1y = data['fundamentals']['return_1y']
                if return_1y is None or return_1y < min_return_1y:
                    continue

            # Valuation filters (Trailing P/E Percentiles: 10th=6, 25th=13, 50th=23, 75th=35, 90th=68)
            # Test Growth vs Value separately (for strategy segmentation)
            if max_trailing_pe is not None or min_trailing_pe is not None:
                if 'valuation' not in data:
                    continue
                trailing_pe = data['valuation']['trailing_pe']

                if max_trailing_pe is not None:
                    if trailing_pe is None or trailing_pe > max_trailing_pe:
                        continue

                if min_trailing_pe is not None:
                    if trailing_pe is None or trailing_pe < min_trailing_pe:
                        continue

            # Volume filters (100% coverage - 289/289 stocks)
            # Volume trend ratio (Percentiles: 10th=0.42, 25th=0.59, 50th=0.81, 75th=1.12, 90th=1.61)
            # 1.0 = normal volume, >1.0 = higher than average (institutional interest)
            if min_volume_trend_ratio is not None:
                if 'volume' not in data:
                    continue
                volume_trend_ratio = data['volume']['volume_trend_ratio']
                if volume_trend_ratio is None or volume_trend_ratio < min_volume_trend_ratio:
                    continue

            # Average volume filter (Percentiles: 10th=4726, 25th=14968, 50th=56433, 75th=253877, 90th=825420)
            # Filter out low-volume stocks (tradability filter)
            if min_avg_volume_20d is not None:
                if 'volume' not in data:
                    continue
                avg_volume_20d = data['volume']['avg_volume_20d']
                if avg_volume_20d is None or avg_volume_20d < min_avg_volume_20d:
                    continue

            # Earnings surprise filters (39% coverage - 112/289 stocks)
            # Surprise percent (Percentiles: 10th=-150%, 25th=-52%, 50th=-5%, 75th=23%, 90th=96%)
            # Positive surprise = earnings beat, negative = earnings miss
            if min_surprise_percent is not None:
                if 'surprise' not in data:
                    continue
                surprise_percent = data['surprise']['surprise_percent']
                if surprise_percent is None or surprise_percent < min_surprise_percent:
                    continue

            if max_surprise_percent is not None:
                if 'surprise' not in data:
                    continue
                surprise_percent = data['surprise']['surprise_percent']
                if surprise_percent is None or surprise_percent > max_surprise_percent:
                    continue

            # Historical pattern filters (66% coverage - 191/289 stocks with earnings_count > 0)
            # Require minimum historical data (Percentiles: 10th=3, 25th=5, 50th=10, 75th=16, 90th=21)
            if min_earnings_count is not None:
                if 'patterns' not in data:
                    continue
                earnings_count = data['patterns']['earnings_count']
                if earnings_count is None or earnings_count < min_earnings_count:
                    continue

            # Cap historical volatility (Percentiles: 10th=2.15%, 25th=3.27%, 50th=4.94%, 75th=6.88%, 90th=9.67%)
            # Avoid unpredictable stocks with extreme historical moves
            if max_historical_volatility is not None:
                if 'patterns' not in data:
                    continue
                avg_abs_return = data['patterns']['avg_abs_return']
                if avg_abs_return is None or avg_abs_return > max_historical_volatility:
                    continue

            # Analyst coverage filters (59-61% coverage)
            # avg_rating: 1=Strong Buy → 5=Strong Sell. corr=+0.180, p=0.0236*
            # Positive corr: bearish-rated stocks outperform (mean reversion)
            if min_avg_rating is not None:
                if 'analyst' not in data:
                    continue
                avg_rating = data['analyst']['avg_rating']
                if avg_rating is None or avg_rating < min_avg_rating:
                    continue

            if max_avg_rating is not None:
                if 'analyst' not in data:
                    continue
                avg_rating = data['analyst']['avg_rating']
                if avg_rating is None or avg_rating > max_avg_rating:
                    continue

            # upside_to_mean_target: corr=-0.143, p=0.0632.
            # Negative corr: high analyst upside → underperforms (mean reversion)
            if min_upside_to_mean_target is not None:
                if 'analyst' not in data:
                    continue
                upside = data['analyst']['upside_to_mean_target']
                if upside is None or upside < min_upside_to_mean_target:
                    continue

            if max_upside_to_mean_target is not None:
                if 'analyst' not in data:
                    continue
                upside = data['analyst']['upside_to_mean_target']
                if upside is None or upside > max_upside_to_mean_target:
                    continue

            # strong_buy_count: corr=+0.121, p=0.1073
            if min_strong_buy_count is not None:
                if 'analyst' not in data:
                    continue
                val = data['analyst']['strong_buy_count']
                if val is None or val < min_strong_buy_count:
                    continue

            # hold_count: corr=+0.089, p=0.2368
            if min_hold_count is not None:
                if 'analyst' not in data:
                    continue
                val = data['analyst']['hold_count']
                if val is None or val < min_hold_count:
                    continue

            # buy_count: corr=+0.068, p=0.3706
            if min_buy_count is not None:
                if 'analyst' not in data:
                    continue
                val = data['analyst']['buy_count']
                if val is None or val < min_buy_count:
                    continue

            # eps_current_year: corr=+0.067, p=0.4065
            if min_eps_current_year is not None:
                if 'analyst' not in data:
                    continue
                val = data['analyst']['eps_current_year']
                if val is None or val < min_eps_current_year:
                    continue

            # num_analysts: corr=+0.055, p=0.4734
            if min_num_analysts is not None:
                if 'analyst' not in data:
                    continue
                val = data['analyst']['num_analysts']
                if val is None or val < min_num_analysts:
                    continue

            # target_price_low: corr=+0.055, p=0.4748
            if min_target_price_low is not None:
                if 'analyst' not in data:
                    continue
                val = data['analyst']['target_price_low']
                if val is None or val < min_target_price_low:
                    continue

            # target_price_mean: corr=+0.037, p=0.6299
            if min_target_price_mean is not None:
                if 'analyst' not in data:
                    continue
                val = data['analyst']['target_price_mean']
                if val is None or val < min_target_price_mean:
                    continue

            # target_price_high: corr=+0.019, p=0.8019
            if min_target_price_high is not None:
                if 'analyst' not in data:
                    continue
                val = data['analyst']['target_price_high']
                if val is None or val < min_target_price_high:
                    continue

            # strong_sell_count: corr=+0.019, p=0.8007
            if max_strong_sell_count is not None:
                if 'analyst' not in data:
                    continue
                val = data['analyst']['strong_sell_count']
                if val is None or val > max_strong_sell_count:
                    continue

            # sell_count: corr=-0.017, p=0.8236
            if max_sell_count is not None:
                if 'analyst' not in data:
                    continue
                val = data['analyst']['sell_count']
                if val is None or val > max_sell_count:
                    continue

            # eps_forward: corr=+0.016, p=0.8270
            if min_eps_forward is not None:
                if 'analyst' not in data:
                    continue
                val = data['analyst']['eps_forward']
                if val is None or val < min_eps_forward:
                    continue

            filtered_data[key] = data

        stock_data = filtered_data

    if not stock_data:
        return None, 0, 0, "No stocks after advanced filter"

    # Calculate returns for each stock
    buy_minutes = time_to_minutes(buy_time)
    tolerance_minutes = 5

    returns = []

    for (ticker, date), stock_info in stock_data.items():
        data = stock_info['prices']
        times_available = sorted(data.keys())

        # Find buy price and index
        buy_price = None
        buy_index = None
        min_diff = float('inf')
        for idx, time_str in enumerate(times_available):
            time_mins = time_to_minutes(time_str)
            diff = abs(time_mins - buy_minutes)
            if diff <= tolerance_minutes and diff < min_diff:
                min_diff = diff
                buy_price = data[time_str]
                buy_index = idx

        if buy_price is None or buy_index is None:
            continue

        # Apply buy filter
        sod_to_buy_change = buy_price - 100.0

        if max_buy_increase is not None and sod_to_buy_change > max_buy_increase:
            continue

        if max_buy_decrease is not None and sod_to_buy_change < -max_buy_decrease:
            continue

        if min_buy_increase is not None and sod_to_buy_change < min_buy_increase:
            continue

        # Calculate sell price
        if profit_target is not None or stop_loss is not None:
            profit_price = buy_price * (1 + profit_target / 100) if profit_target else None
            # stop_loss is negative (e.g., -3.0), so we ADD it: buy_price * (1 + (-3)/100) = buy_price * 0.97
            loss_price = buy_price * (1 + stop_loss / 100) if stop_loss else None

            if sell_time:
                sell_minutes = time_to_minutes(sell_time)
                max_check_index = len(times_available) - 1
                for idx, time_str in enumerate(times_available):
                    time_mins = time_to_minutes(time_str)
                    if time_mins > sell_minutes + tolerance_minutes:
                        max_check_index = idx - 1
                        break
            else:
                max_check_index = len(times_available) - 1

            sell_price = None

            for idx in range(buy_index + 1, max_check_index + 1):
                time_str = times_available[idx]
                current_price = data[time_str]

                if profit_price and current_price >= profit_price:
                    sell_price = profit_price
                    break

                if loss_price and current_price <= loss_price:
                    sell_price = loss_price
                    break

            if sell_price is None:
                if sell_time:
                    sell_minutes = time_to_minutes(sell_time)
                    min_diff = float('inf')
                    for time_str in times_available:
                        time_mins = time_to_minutes(time_str)
                        diff = abs(time_mins - sell_minutes)
                        if diff <= tolerance_minutes and diff < min_diff:
                            min_diff = diff
                            sell_price = data[time_str]
                else:
                    sell_price = data[times_available[-1]]

        else:
            if sell_time:
                sell_minutes = time_to_minutes(sell_time)
                sell_price = None
                min_diff = float('inf')
                for time_str in times_available:
                    time_mins = time_to_minutes(time_str)
                    diff = abs(time_mins - sell_minutes)
                    if diff <= tolerance_minutes and diff < min_diff:
                        min_diff = diff
                        sell_price = data[time_str]
            else:
                sell_price = data[times_available[-1]]

        if sell_price is not None:
            return_pct = ((sell_price - buy_price) / buy_price) * 100
            # Deduct 1% trading fee per stock (simulates purchasing costs)
            return_pct -= 1.0
            returns.append(return_pct)

    if not returns:
        return None, 0, 0, "No valid trades"

    total_profit = sum(returns)
    num_stocks = len(returns)
    avg_profit = total_profit / num_stocks if num_stocks > 0 else 0

    return total_profit, num_stocks, avg_profit, "OK"


def validate_params(params):
    """Validate parameter constraints."""
    def time_valid(t):
        if t is None:
            return True
        mins = time_to_minutes(t)
        return 540 <= mins <= 1050

    if not all(time_valid(t) for t in [params['start_time'], params['end_time'],
                                        params['buy_time'], params['sell_time']]):
        return False

    start_mins = time_to_minutes(params['start_time'])
    end_mins = time_to_minutes(params['end_time'])
    buy_mins = time_to_minutes(params['buy_time'])

    if start_mins > end_mins:
        return False

    if end_mins > buy_mins:
        return False

    if params['sell_time'] is not None:
        sell_mins = time_to_minutes(params['sell_time'])
        if buy_mins >= sell_mins:
            return False

    if params['profit_target'] is not None and params['profit_target'] <= 0:
        return False

    if params['stop_loss'] is not None and params['stop_loss'] >= 0:
        return False

    if params['max_gain_pct'] is not None:
        if params['max_gain_pct'] <= params['min_gain_pct']:
            return False

    if params['max_buy_increase'] is not None and params['max_buy_increase'] <= 0:
        return False

    if params['max_buy_decrease'] is not None and params['max_buy_decrease'] >= 0:
        return False

    if params['min_buy_increase'] is not None and params['min_buy_increase'] < 0:
        return False

    # Ensure min_buy_increase < max_buy_increase if both are set
    if (params['min_buy_increase'] is not None and
        params['max_buy_increase'] is not None):
        if params['min_buy_increase'] >= params['max_buy_increase']:
            return False

    if (params['min_data_points'] is not None and
        params['max_data_points'] is not None):
        if params['min_data_points'] >= params['max_data_points']:
            return False

    return True


def deduplicate_results(results):
    """Remove duplicate configurations, keeping the first occurrence (highest profit).

    Args:
        results: List of result dictionaries (already sorted by profit descending)

    Returns:
        List of unique results
    """
    seen_configs = set()
    unique_results = []

    for result in results:
        # Create a hashable representation of the parameters
        config_tuple = tuple(sorted(result['params'].items()))

        if config_tuple not in seen_configs:
            seen_configs.add(config_tuple)
            unique_results.append(result)

    return unique_results


def generate_fine_grid(winner_params, original_coarse_grid, round_divisor, reference_grid=None):
    """Generate fine grid around a winning configuration.

    Args:
        winner_params: The winning parameter configuration
        original_coarse_grid: The original coarse grid to find nearest neighbors
        round_divisor: 2 for Round 2, 4 for Round 3 (step = distance/divisor)
        reference_grid: Grid to use for distance calculations (defaults to original_coarse_grid)
                       For Round 3, pass the Round 2 grid to get correct distances
    """
    # Use reference_grid if provided, otherwise fall back to original_coarse_grid
    if reference_grid is None:
        reference_grid = original_coarse_grid

    fine_grid = {}

    for param_name, value in winner_params.items():
        # Get the reference grid values for this parameter
        ref_values = reference_grid[param_name]

        if value is None:
            # If value is None, keep it as None
            fine_grid[param_name] = [None]
            continue

        # Find nearest neighbor in reference grid (excluding None)
        ref_numeric = [v for v in ref_values if v is not None]

        if not ref_numeric:
            # If no numeric values in reference grid, just use the value
            fine_grid[param_name] = [value]
            continue

        # If reference grid has only 1 value, it's "fixed" - don't refine it
        if len(ref_numeric) == 1:
            fine_grid[param_name] = [value]
            continue

        if param_name in ['start_time', 'end_time', 'buy_time', 'sell_time']:
            # For times, work in minutes
            value_mins = time_to_minutes(value)
            ref_mins = [time_to_minutes(t) for t in ref_numeric]

            # Find nearest neighbor (exclude distance to self if value is in grid)
            distances = [abs(value_mins - c) for c in ref_mins if abs(value_mins - c) > 0]
            min_distance = min(distances) if distances else 1  # Default to 1 minute if no other values

            # Step size = distance / round_divisor
            step_mins = min_distance / round_divisor

            # Generate options
            options = [
                minutes_to_time(int(value_mins - step_mins)),
                minutes_to_time(value_mins),
                minutes_to_time(int(value_mins + step_mins))
            ]
            fine_grid[param_name] = [t for t in options if t and time_to_minutes(t) >= 540 and time_to_minutes(t) <= 1050]

        else:
            # For numeric parameters
            # Find nearest neighbor distance (exclude distance to self if value is in grid)
            distances = [abs(value - c) for c in ref_numeric if abs(value - c) > 0.001]  # Small epsilon for float comparison
            min_distance = min(distances) if distances else 1.0  # Default to 1.0 if no other values

            # Step size = distance / round_divisor
            step = min_distance / round_divisor

            # Generate options
            options = [value - step, value, value + step]

            # For integer parameters (data points), round the values
            if param_name in ['min_data_points', 'max_data_points']:
                options = [int(round(v)) for v in options]
                options = [v for v in options if v > 0]

            fine_grid[param_name] = options

    return fine_grid


def _init_worker(data):
    """Initialize worker process with shared data."""
    global _global_data
    _global_data = data


def _process_combination(param_names, combination):
    """Worker function to process a single parameter combination."""
    params = dict(zip(param_names, combination))

    # Validate parameters
    if not validate_params(params):
        return None

    # Calculate profit using global data
    total_profit, num_stocks, avg_profit, status = calculate_total_profit(_global_data, params)

    if total_profit is not None:
        return {
            'params': params,
            'total_profit': total_profit,
            'num_stocks': num_stocks,
            'avg_profit': avg_profit,
            'status': status
        }
    return None


def run_grid_search_round(all_data, param_grid, round_num):
    """Run a single round of grid search (works on preloaded data)."""
    print(f"\n{'='*80}")
    print(f"ROUND {round_num}")
    print(f"{'='*80}\n")

    param_names = list(param_grid.keys())
    param_values = [param_grid[name] for name in param_names]

    total_combinations = 1
    for values in param_values:
        total_combinations *= len(values)

    num_cores = multiprocessing.cpu_count()
    print(f"Testing {total_combinations:,} combinations in this round...")
    print(f"Using {num_cores} CPU cores for parallel processing")
    print()

    start_time = time.time()

    # Create pool with workers initialized with the data
    with multiprocessing.Pool(processes=num_cores, initializer=_init_worker, initargs=(all_data,)) as pool:
        # Create worker function with param_names bound
        worker_func = partial(_process_combination, param_names)

        # Process all combinations in parallel
        all_results = pool.map(worker_func, product(*param_values), chunksize=100)

    # Filter out None results (invalid params or no profit)
    results = [r for r in all_results if r is not None]
    valid_count = len(results)
    invalid_count = total_combinations - valid_count

    elapsed = time.time() - start_time
    rate = total_combinations / elapsed if elapsed > 0 else 0
    print(f"\nRound {round_num} complete: {valid_count} valid configurations tested in {elapsed:.2f}s")
    print(f"Processing rate: {rate:.1f} combos/sec (average across {num_cores} cores)")

    results.sort(key=lambda x: x['total_profit'], reverse=True)
    return results


def coarse_to_fine_search():
    """Iterative coarse-to-fine grid search."""
    print("="*80)
    print("COARSE-TO-FINE EARNINGS TRADING STRATEGY OPTIMIZATION")
    print("="*80)
    print()
    print("Strategy: Three-round adaptive refinement")
    print("  Round 1: Coarse grid (full parameter space)")
    print("  Round 2: Refine top 30 unique (step = distance_to_neighbor / 2)")
    print("  Round 3: Refine top 10 unique (step = distance_to_neighbor / 2)")
    print()
    print("Profit metric: Sum of individual stock returns (minus 0.8% fee per stock)")
    print()

    # PRELOAD ALL DATA ONCE (major speed optimization!)
    all_data = preload_all_data()

    # Round 1: Coarse grid
    # Removed parameters based on significance analysis:
    # - max_gain_pct: Zero correlation, fixed to None (unbounded)
    # - stop_loss: Weak signal, fixed to None (no stop loss)
    # - max_data_points: Moderate significance, fixed to None (no upper limit on data points)
    # - max_buy_increase: No clear optimum (14.25, 15.0, 15.75 all same result), fixed to None
    #
    # PERCENTILE NOTATION: Comments show data distribution across 289 earnings events
    # Format: "Percentiles: 10th=X, 25th=Y, 50th=Z (median), 75th=A, 90th=B"
    # - 10th-90th captures 80% of the data (excludes extreme outliers)
    # - Use these ranges to design realistic grid search parameters
    # FOCUSED GRID: Test impact of NEW data (volume, surprise, patterns)
    # on top of best-known parameter values from previous optimization
    # Total combinations: 2^7 = 128 (< 1 minute runtime!)
    coarse_grid = {
        # FIXED: Timing parameters (from best config)
        'min_gain_pct': [None], #optimal
        'max_gain_pct': [None], #optimal
        'start_time': ['09:00'],
        'end_time': ['09:00'],
        'buy_time': ['09:00'], #TESTING: expand buy time options around 9:30 to see if earlier/later entry improves results
        'sell_time': ['16:00','16:20','16:40'],
        'profit_target': [None], #optimal
        'stop_loss': [-10], #optimal
        'max_buy_increase': [None],
        'max_buy_decrease': [None], #optimal
        'min_buy_increase': [None], #optimal
        'min_data_points': [None], 
        'max_data_points': [None], #optimal
        # sod_increase: overnight gap from prev_close to first intraday price on earnings day
        #   vs earnings_day_return (prev_close→close):  corr=+0.727, p≈0 *** (n=289) — strong, real
        #   vs intraday_return    (9am→close, trade P&L): corr=+0.111, p=0.091.      — weak
        # The gap is a strong signal of the earnings reaction but the trade enters AFTER it.
        # Percentiles (n=289): 10th=-8.14%,  25th=-2.32%,  50th=0.00%,  75th=3.31%,  90th=7.46%
        'min_sod_increase': [-1], #CONFIG #2 (analyst-momentum)
        #'min_sod_increase': [None], #CONFIG #1 Analyst sentiment + quality screen

#   ┌───────────┬──────────────────────────────────────┬────────────────────────────────────────┐                                                                                                                   
#   │           │ SOD→EOD (intraday, current strategy) │ EOD→EOD (full day incl. overnight gap) │
#   ├───────────┼──────────────────────────────────────┼────────────────────────────────────────┤                                                                                                                   
#   │ Config #1 │ 110-115% total, 7.08% avg (15 stocks) │ 134.62% total, 6.73% avg (20 stocks)   │
#                  105-110% if: buy_time=9:30-9:45, 
#                  sell_time=16:10-16:45, min_gain_pct=-10%, 
#                  stop_loss=-10%, min_data_points=6                                                                                                                   
#   ├───────────┼──────────────────────────────────────┼────────────────────────────────────────┤                                                                                                                 
#   │ Config #2 │ 110-115% total, 5.28% avg (20 stocks) │ 219.98% total, 10.48% avg (21 stocks)  │
#                 110-120 if: buy_time=9:15-9:45, 
#                 sell_time=16:15-16:50, min_gain_pct=-10%,
#                 stop_loss=-10%, min_data_points=2-8                                                                                                                   
#   └───────────┴──────────────────────────────────────┴────────────────────────────────────────┘  

        # ==============================================================================
        # PARAMETERS SORTED BY UNIVARIATE PREDICTIVE POWER
        # ==============================================================================
        # Correlation analysis vs earnings_day_return
        # Significance: *** p<0.001, ** p<0.01, * p<0.05, . p<0.10
        # Analyst coverage parameters: n≈100, 59-61% data coverage
        # Other parameters: n=289 unless noted
        # ==============================================================================

        # STRONG PREDICTORS (|corr| >= 0.15, p < 0.05):
        # ------------------------------------------------

        # volume_trend_ratio: corr=+0.182, p=0.0018** — STRONGEST PREDICTOR
        # Percentiles (n=289): 10th=0.42,  25th=0.59,  50th=0.81,  75th=1.12,  90th=1.61
        'min_volume_trend_ratio': [0.37], #CONFIG #2 (analyst-momentum)
        # 'min_volume_trend_ratio': [None], #CONFIG #1 Analyst sentiment + quality screen

        # avg_rating: corr=+0.180, p=0.0236* — analyst rating (1=Strong Buy → 5=Strong Sell)
        # Higher rating = more bearish consensus = historically outperforms (mean reversion)
        # Percentiles (n=158): 10th=0.00,  25th=0.00,  50th=1.00,  75th=2.00,  90th=3.00
        'min_avg_rating': [1.00], #CONFIG #2 (analyst-momentum)
        #'min_avg_rating': [None], #CONFIG #1 Analyst sentiment + quality screen

        # volatility_20d: corr=+0.162, p=0.0059**
        # Percentiles (n=289): 10th=0.21,  25th=0.28,  50th=0.41,  75th=0.61,  90th=1.06
        'min_volatility_20d': [0.41], #CONFIG #2 (analyst-momentum)
        # 'min_volatility_20d': [0.1825], #CONFIG #1 Analyst sentiment + quality screen

        # MODERATE PREDICTORS (|corr| >= 0.10):
        # ------------------------------------------------

        # upside_to_mean_target: corr=-0.143, p=0.0632. — high analyst upside → underperforms
        # Percentiles (n=170): 10th=0.98%,  25th=14.37%,  50th=34.90%,  75th=72.88%,  90th=139.86%
        'max_upside_to_mean_target': [None], #CONFIG #2 (analyst-momentum)
        # 'max_upside_to_mean_target': [40.0325], #CONFIG #1 Analyst sentiment + quality screen
        'min_upside_to_mean_target': [None],

        # volatility_60d: corr=+0.123, p=0.0374* — EXCLUDED: r=+0.859 with volatility_20d (redundant)
        # 'min_volatility_60d': [None],

        # strong_buy_count: corr=+0.121, p=0.1073
        # Percentiles (n=177): 10th=0,  25th=0,  50th=0,  75th=0,  90th=1
        'min_strong_buy_count': [None],

        # WEAK PREDICTORS (|corr| >= 0.05):
        # ------------------------------------------------

        # avg_volume_20d: corr=+0.099, p=0.0940.
        # Percentiles (n=289): 10th=4,726,  25th=14,968,  50th=56,433,  75th=253,877,  90th=825,420
        'min_avg_volume_20d': [None],

        # surprise_percent: corr=-0.094, p=0.3219 (n=114, 39% coverage)
        # 'min_surprise_percent': [None, 0],
        # 'max_surprise_percent': [None],

        # hold_count: corr=+0.089, p=0.2368
        # 'min_hold_count': [None],

        # position_in_range: corr=-0.082, p=0.1623
        # Percentiles (n=289): 10th=0.01,  25th=0.07,  50th=0.28,  75th=0.57,  90th=0.80
        'max_position_in_range': [0.385], #CONFIG #2 (analyst-momentum)
        # 'max_position_in_range': [0.175], #CONFIG #1 Analyst sentiment + quality screen

        # max_historical_volatility (avg_abs_return): corr=-0.068, p=0.0005*** (negative! n=2554)
        # Percentiles (n=2554): 10th=2.15%,  25th=3.27%,  50th=4.94%,  75th=6.88%,  90th=9.67%
        'max_historical_volatility': [None], 

        # buy_count: corr=+0.068, p=0.3706
        # 'min_buy_count': [None],

        # eps_current_year: corr=+0.067, p=0.4065
        # 'min_eps_current_year': [None],

        # return_1m: corr=-0.059, p=0.3190
        # 'min_return_1m': [None],

        # liquidity_score: corr=+0.057, p=0.3379 — kept for tradability (risk management)
        # 'min_liquidity_score': [10],  # FIXED: Risk management filter

        # num_analysts: corr=+0.055, p=0.4734 — EXCLUDED: r=+0.821 with buy_count (redundant)
        # 'min_num_analysts': [None],

        # target_price_low: corr=+0.055, p=0.4748
        # 'min_target_price_low': [None],

        # NO SIGNAL (|corr| < 0.05):
        # ------------------------------------------------

        # trailing_pe: N/A (insufficient data, n=151); price_to_book: corr=+0.044, p=0.4586
        # 'max_trailing_pe': [None],
        # 'min_trailing_pe': [None],

        # return_1y: corr=-0.040, p=0.5025 — critical interaction effect with volatility_20d
        # 'max_return_1y': [-9],  # FIXED: Mean reversion (stocks down ≤-9% on the year)
        # 'min_return_1y': [-75],  # FIXED: Avoid extreme losers

        # target_price_mean: corr=+0.037, p=0.6299 — EXCLUDED: r=+0.992 with target_price_low (redundant)
        # 'min_target_price_mean': [None],

        # earnings_count: corr=-0.031, p=0.0853. (n=3015, 100% coverage; grid found useful)
        # 'min_earnings_count': [None, 5],

        # target_price_high: corr=+0.019, p=0.8019 — EXCLUDED: r=+0.974 with target_price_low (redundant)
        # 'min_target_price_high': [None],

        # strong_sell_count: corr=+0.019, p=0.8007
        # 'max_strong_sell_count': [None],

        # return_3m: corr=-0.019, p=0.7527
        # 'min_return_3m': [None],

        # sell_count: corr=-0.017, p=0.8236
        # 'max_sell_count': [None],

        # eps_forward: corr=+0.016, p=0.8270
        # 'min_eps_forward': [None],

        # sma200_ratio: corr=+0.016, p=0.7881 — EXCLUDED: r≈+0.98 with target prices (redundant)
        # 'min_sma200_ratio': [None],

        # volatility_252d: corr=-0.013, p=0.8232 — EXCLUDED: r=+0.984 with return_1y (redundant)
        # 'min_volatility_252d': [None],
    }

    all_rounds_results = []

    # Round 1: Coarse grid
    print("="*80)
    print("ROUND 1: COARSE GRID")
    print("="*80)
    round1_results = run_grid_search_round(all_data, coarse_grid, 1)
    all_rounds_results.append({'round': 1, 'results': round1_results})

    # Deduplicate Round 1 results
    round1_unique = deduplicate_results(round1_results)
    print(f"\nRound 1: {len(round1_results)} total configs, {len(round1_unique)} unique")

    # Display top 20 from round 1
    print(f"\nTop 20 from Round 1:")
    for rank, result in enumerate(round1_unique[:20], 1):
        print(f"  {rank:2d}. Profit: {result['total_profit']:7.2f}% ({result['num_stocks']:3d} stocks)")

    # Create output directory
    output_dir = os.path.join('data', 'grid_search')
    os.makedirs(output_dir, exist_ok=True)

    # Save round 1
    with open(os.path.join(output_dir, 'grid_search_round1.json'), 'w') as f:
        json.dump(round1_results, f, indent=2)

    # Round 2: Refine around top 30 unique from Round 1 (step = distance / 2)
    top30_round1 = round1_unique[:30]
    round2_all_results = []

    print(f"\n{'='*80}")
    print(f"ROUND 2: Refining top 30 unique from Round 1 (step = distance/2)")
    print(f"{'='*80}\n")

    for i, config in enumerate(top30_round1, 1):
        print(f"Refining configuration {i}/30...")
        fine_grid = generate_fine_grid(config['params'], coarse_grid, round_divisor=2)
        round2_results = run_grid_search_round(all_data, fine_grid, f"2.{i}")
        # Store the parent grid with each result for Round 3
        for result in round2_results:
            result['parent_grid'] = fine_grid
        round2_all_results.extend(round2_results)

    round2_all_results.sort(key=lambda x: x['total_profit'], reverse=True)
    all_rounds_results.append({'round': 2, 'results': round2_all_results})

    # Deduplicate Round 2 results
    round2_unique = deduplicate_results(round2_all_results)
    print(f"\nRound 2: {len(round2_all_results)} total configs, {len(round2_unique)} unique")

    # Display top 20 from round 2
    print(f"\nTop 20 from Round 2:")
    for rank, result in enumerate(round2_unique[:20], 1):
        print(f"  {rank:2d}. Profit: {result['total_profit']:7.2f}% ({result['num_stocks']:3d} stocks)")

    # Save round 2
    with open(os.path.join(output_dir, 'grid_search_round2.json'), 'w') as f:
        json.dump(round2_all_results, f, indent=2)

    # Round 3: Refine around top 10 unique from Round 2 (step = distance / 2)
    top10_round2 = round2_unique[:10]
    round3_all_results = []

    print(f"\n{'='*80}")
    print(f"ROUND 3: Refining top 10 unique from Round 2 (step = distance/2)")
    print(f"{'='*80}\n")

    for i, config in enumerate(top10_round2, 1):
        print(f"Refining configuration {i}/10...")
        # Use the stored parent grid from Round 2 (the actual grid that produced this config)
        round2_grid = config.get('parent_grid', coarse_grid)
        # Generate Round 3 grid using actual Round 2 grid as reference
        fine_grid = generate_fine_grid(config['params'], coarse_grid, round_divisor=2, reference_grid=round2_grid)
        round3_results = run_grid_search_round(all_data, fine_grid, f"3.{i}")
        round3_all_results.extend(round3_results)

    round3_all_results.sort(key=lambda x: x['total_profit'], reverse=True)
    all_rounds_results.append({'round': 3, 'results': round3_all_results})

    # Deduplicate Round 3 results
    round3_unique = deduplicate_results(round3_all_results)
    print(f"\nRound 3: {len(round3_all_results)} total configs, {len(round3_unique)} unique")

    # Save round 3
    with open(os.path.join(output_dir, 'grid_search_round3.json'), 'w') as f:
        json.dump(round3_all_results, f, indent=2)

    # Display final top 10
    print(f"\n{'='*80}")
    print("FINAL TOP 10 UNIQUE CONFIGURATIONS (After Round 3)")
    print(f"{'='*80}\n")

    for rank, result in enumerate(round3_unique[:10], 1):
        print(f"RANK {rank}:")
        print(f"  Total Profit: {result['total_profit']:.2f}%")
        print(f"  Stocks Traded: {result['num_stocks']}")
        print(f"  Avg Profit per Stock: {result['avg_profit']:.2f}%")
        print(f"  Parameters:")
        for key, value in sorted(result['params'].items()):
            print(f"    {key}: {value}")
        print()

    # Save all results
    with open(os.path.join(output_dir, 'grid_search_final.json'), 'w') as f:
        json.dump(all_rounds_results, f, indent=2)

    print(f"Results saved to {output_dir}:")
    print(f"  - grid_search_round1.json (Round 1 results)")
    print(f"  - grid_search_round2.json (Round 2 results)")
    print(f"  - grid_search_round3.json (Round 3 results)")
    print(f"  - grid_search_final.json (All rounds)")
    print()


if __name__ == '__main__':
    coarse_to_fine_search()
