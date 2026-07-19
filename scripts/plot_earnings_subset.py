#!/usr/bin/env python3
"""
Plot earnings analysis for specific stock patterns using matplotlib.

This script queries the earnings intraday database and creates custom visualizations
for stocks matching certain criteria. Uses flexible time matching (±5 minutes) to
maximize data coverage.

Example: Plot all stocks that gained >=0% from 09:00 to 17:00 (default)
"""

import sqlite3
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from collections import defaultdict
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.utils.database import get_connection


def get_stocks_by_early_gain(min_gain_pct=2.0, max_gain_pct=None, start_time="09:00", end_time="09:10"):
    """
    Get all stocks that gained at least min_gain_pct between start_time and end_time.
    Uses closest available time within 5 minutes if exact time not available.

    Args:
        min_gain_pct: Minimum gain percentage (e.g., 2.0 for 2%)
        max_gain_pct: Maximum gain percentage (e.g., 10.0 for 10%), None for no ceiling
        start_time: Start time in HH:MM format (default "09:00")
        end_time: End time in HH:MM format (default "09:10")

    Returns:
        List of (ticker, earnings_date) tuples that meet the criteria
    """
    from datetime import datetime, timedelta

    conn = get_connection()
    cursor = conn.cursor()

    # Convert time strings to datetime for comparison
    def time_to_minutes(time_str):
        """Convert HH:MM to minutes since midnight."""
        h, m = map(int, time_str.split(':'))
        return h * 60 + m

    start_minutes = time_to_minutes(start_time)
    end_minutes = time_to_minutes(end_time)
    tolerance_minutes = 5

    # Get all unique stock-date combinations with their available times
    cursor.execute("""
        SELECT DISTINCT ticker, earnings_date
        FROM earnings_intraday_analysis
    """)
    all_stocks = cursor.fetchall()

    results = []

    for ticker, earnings_date in all_stocks:
        # Get all available times for this stock
        cursor.execute("""
            SELECT time_of_day, normalized_price
            FROM earnings_intraday_analysis
            WHERE ticker = ? AND earnings_date = ?
            ORDER BY time_of_day
        """, (ticker, earnings_date))

        time_data = cursor.fetchall()

        # Find closest time to start_time
        start_price = None
        min_start_diff = float('inf')
        for time_str, price in time_data:
            time_mins = time_to_minutes(time_str)
            diff = abs(time_mins - start_minutes)
            if diff <= tolerance_minutes and diff < min_start_diff:
                min_start_diff = diff
                start_price = price

        # Find closest time to end_time
        end_price = None
        min_end_diff = float('inf')
        for time_str, price in time_data:
            time_mins = time_to_minutes(time_str)
            diff = abs(time_mins - end_minutes)
            if diff <= tolerance_minutes and diff < min_end_diff:
                min_end_diff = diff
                end_price = price

        # If we found both prices, calculate gain
        if start_price is not None and end_price is not None:
            gain = end_price - start_price
            # Check if gain is within the specified range
            if gain >= min_gain_pct:
                if max_gain_pct is None or gain <= max_gain_pct:
                    results.append((ticker, earnings_date, gain))

    conn.close()

    # Sort by gain descending
    results.sort(key=lambda x: x[2], reverse=True)

    return results


def get_intraday_data(ticker, earnings_date):
    """
    Get full intraday normalized price data for a specific stock.

    Args:
        ticker: Stock ticker
        earnings_date: Earnings date (YYYY-MM-DD)

    Returns:
        Dictionary mapping time_of_day -> normalized_price
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT time_of_day, normalized_price
        FROM earnings_intraday_analysis
        WHERE ticker = ? AND earnings_date = ?
        ORDER BY time_of_day
    """, (ticker, earnings_date))

    data = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()

    return data


def plot_early_gainers(min_gain_pct=2.0, max_gain_pct=None, start_time="09:00", end_time="09:10",
                       buy_time=None, sell_time=None, profit_target=None, stop_loss=None,
                       max_buy_increase=None, max_buy_decrease=None, min_buy_increase=None,
                       min_data_points=None, max_data_points=None,
                       min_sod_increase=None, min_return_1m=None, min_return_3m=None,
                       min_return_1y=None, min_sma200_ratio=None,
                       save_path=None, show_plot=True):
    """
    Plot all stocks that gained at least min_gain_pct in the specified time window.

    Args:
        min_gain_pct: Minimum gain percentage (e.g., 2.0 for 2%)
        max_gain_pct: Maximum gain percentage (e.g., 10.0 for 10%), None for no ceiling
        start_time: Start time for selection criteria (HH:MM)
        end_time: End time for selection criteria (HH:MM)
        buy_time: Time to buy stocks (HH:MM), defaults to end_time if not specified
        sell_time: Time to sell for return calculation (HH:MM), None for EOD
        profit_target: If set, sell when this profit % is reached (e.g., 2.0 for 2%), EOD fallback
        stop_loss: If set, sell when this loss % is reached (e.g., 2.0 for -2%), EOD fallback
        max_buy_increase: Max allowed increase from SOD to buy_time (e.g., 10.0 for 10%), None for no limit
        max_buy_decrease: Max allowed decrease from SOD to buy_time (e.g., 2.0 for -2%), None for no limit
        min_buy_increase: Min required increase from SOD to buy_time (e.g., 2.0 for 2%), None for no limit
        min_data_points: Min datapoints in hour before buy_time (or from 09:00), None for no limit
        max_data_points: Max datapoints in hour before buy_time (or from 09:00), None for no limit
        min_sod_increase: Min SOD increase (yesterday_close/open - 1) * 100, None for no limit
        min_return_1m: Min 1-month return percentage, None for no limit
        min_return_3m: Min 3-month return percentage, None for no limit
        min_return_1y: Min 1-year return percentage, None for no limit
        min_sma200_ratio: Min ratio (yesterday_close/sma_200 - 1) * 100, None for no limit
        save_path: Optional path to save the plot (e.g., 'early_gainers.png')
        show_plot: Whether to display the plot (default True)
    """
    print(f"\n{'='*80}")
    if max_gain_pct is not None:
        print(f"Analyzing stocks with {min_gain_pct}% to {max_gain_pct}% gain from {start_time} to {end_time}")
    else:
        print(f"Analyzing stocks with >{min_gain_pct}% gain from {start_time} to {end_time}")
    print(f"{'='*80}\n")

    # Get qualifying stocks
    stocks = get_stocks_by_early_gain(min_gain_pct, max_gain_pct, start_time, end_time)

    if not stocks:
        print(f"No stocks found with >{min_gain_pct}% gain in the specified window.")
        return

    print(f"Found {len(stocks)} stocks that meet the criteria:\n")
    for ticker, date, gain in stocks[:10]:  # Show first 10
        print(f"  {ticker:15s} {date}  {gain:+6.2f}%")
    if len(stocks) > 10:
        print(f"  ... and {len(stocks) - 10} more")
    print()

    # Get all intraday data
    print("Loading intraday data...")
    all_data = {}
    all_times = set()

    for ticker, earnings_date, gain in stocks:
        data = get_intraday_data(ticker, earnings_date)
        all_data[(ticker, earnings_date)] = data
        all_times.update(data.keys())

    # Apply fundamental filters if any are specified
    if any([min_sod_increase is not None, min_return_1m is not None, min_return_3m is not None,
            min_return_1y is not None, min_sma200_ratio is not None]):

        print("Applying fundamental filters...")
        conn = get_connection()
        cursor = conn.cursor()

        filtered_data = {}
        excluded_by_fundamentals = 0

        for (ticker, earnings_date), data in all_data.items():
            # Get fundamentals for this ticker/date
            cursor.execute("""
                SELECT yesterday_close, return_1m, return_3m, return_1y, sma_200
                FROM earnings_fundamentals
                WHERE ticker = ? AND earnings_date = ?
            """, (ticker, earnings_date))

            result = cursor.fetchone()
            if not result:
                excluded_by_fundamentals += 1
                continue

            yesterday_close, return_1m, return_3m, return_1y, sma_200 = result

            # Calculate SOD increase: gap from yesterday_close to 9:00 price on earnings day
            if min_sod_increase is not None:
                # Get actual price at 9:00 from earnings_intraday_analysis
                cursor.execute("""
                    SELECT price
                    FROM earnings_intraday_analysis
                    WHERE ticker = ? AND earnings_date = ? AND time_of_day = '09:00'
                """, (ticker, earnings_date))

                price_9am_result = cursor.fetchone()
                if not price_9am_result:
                    excluded_by_fundamentals += 1
                    continue

                price_9am = price_9am_result[0]

                # Calculate gap: ((9am_price - yesterday_close) / yesterday_close) * 100
                sod_increase = ((price_9am - yesterday_close) / yesterday_close) * 100

                if sod_increase < min_sod_increase:
                    excluded_by_fundamentals += 1
                    continue

            # Check 1-month return
            if min_return_1m is not None and (return_1m is None or return_1m < min_return_1m):
                excluded_by_fundamentals += 1
                continue

            # Check 3-month return
            if min_return_3m is not None and (return_3m is None or return_3m < min_return_3m):
                excluded_by_fundamentals += 1
                continue

            # Check 1-year return
            if min_return_1y is not None and (return_1y is None or return_1y < min_return_1y):
                excluded_by_fundamentals += 1
                continue

            # Check SMA200 ratio: (yesterday_close / sma_200 - 1) * 100
            if min_sma200_ratio is not None:
                if sma_200 is None:
                    excluded_by_fundamentals += 1
                    continue
                sma_ratio = ((yesterday_close / sma_200) - 1) * 100
                if sma_ratio < min_sma200_ratio:
                    excluded_by_fundamentals += 1
                    continue

            # Stock passed all filters
            filtered_data[(ticker, earnings_date)] = data

        conn.close()

        if excluded_by_fundamentals > 0:
            filter_parts = []
            if min_return_1m is not None:
                filter_parts.append(f"return_1m >= {min_return_1m}%")
            if min_return_3m is not None:
                filter_parts.append(f"return_3m >= {min_return_3m}%")
            if min_return_1y is not None:
                filter_parts.append(f"return_1y >= {min_return_1y}%")
            if min_sma200_ratio is not None:
                filter_parts.append(f"price/SMA200 >= {min_sma200_ratio:+.1f}%")

            print(f"Excluded {excluded_by_fundamentals} stocks by fundamental filters ({', '.join(filter_parts)})")
            print(f"Remaining stocks: {len(filtered_data)}")

        if not filtered_data:
            print(f"No stocks found matching fundamental criteria.")
            return

        # Update all_data to use filtered data
        all_data = filtered_data

    # Default buy_time to end_time if not specified
    if buy_time is None:
        buy_time = end_time

    # Filter stocks by data point count in the hour before buy_time (or from 09:00)
    if min_data_points is not None or max_data_points is not None:
        def time_to_minutes(time_str):
            h, m = map(int, time_str.split(':'))
            return h * 60 + m

        buy_minutes = time_to_minutes(buy_time)

        # Determine the counting window: 1 hour before buy_time, or from 09:00 if buying before 10:00
        if buy_minutes < 600:  # 10:00 is 600 minutes
            count_start_minutes = 540  # 09:00
        else:
            count_start_minutes = buy_minutes - 60  # 1 hour before buy_time

        count_end_minutes = buy_minutes

        filtered_data = {}
        excluded_count = 0

        for key, data in all_data.items():
            # Count datapoints in the window
            count = 0
            for time_str in data.keys():
                time_mins = time_to_minutes(time_str)
                if count_start_minutes <= time_mins <= count_end_minutes:
                    count += 1

            # Check if within limits
            passes_min = min_data_points is None or count >= min_data_points
            passes_max = max_data_points is None or count <= max_data_points

            if passes_min and passes_max:
                filtered_data[key] = data
            else:
                excluded_count += 1

        if excluded_count > 0:
            range_desc = []
            if min_data_points is not None:
                range_desc.append(f">={min_data_points}")
            if max_data_points is not None:
                range_desc.append(f"<={max_data_points}")

            count_window_start = f"{count_start_minutes//60:02d}:{count_start_minutes%60:02d}"
            count_window_end = f"{count_end_minutes//60:02d}:{count_end_minutes%60:02d}"

            print(f"Excluded {excluded_count} stocks outside datapoint range {' and '.join(range_desc)} in window {count_window_start}-{count_window_end}")
            print(f"Remaining stocks: {len(filtered_data)}")

        if not filtered_data:
            print(f"No stocks found matching datapoint criteria.")
            return

        # Update all_data to use filtered data
        all_data = filtered_data

    # Apply buy filter before plotting (so we only show stocks that would actually be traded)
    if max_buy_increase is not None or max_buy_decrease is not None or min_buy_increase is not None:
        def time_to_minutes(time_str):
            h, m = map(int, time_str.split(':'))
            return h * 60 + m

        buy_minutes = time_to_minutes(buy_time)
        tolerance_minutes = 5

        filtered_by_buy = {}
        excluded_by_buy_filter = 0

        for key, data in all_data.items():
            times_available = sorted(data.keys())

            # Find buy price (closest to buy_time)
            buy_price = None
            min_diff = float('inf')
            for time_str in times_available:
                time_mins = time_to_minutes(time_str)
                diff = abs(time_mins - buy_minutes)
                if diff <= tolerance_minutes and diff < min_diff:
                    min_diff = diff
                    buy_price = data[time_str]

            if buy_price is None:
                excluded_by_buy_filter += 1
                continue

            # Check buy filter: price change from SOD (100% baseline)
            sod_to_buy_change = buy_price - 100.0

            if max_buy_increase is not None and sod_to_buy_change > max_buy_increase:
                excluded_by_buy_filter += 1
                continue

            if max_buy_decrease is not None and sod_to_buy_change < -max_buy_decrease:
                excluded_by_buy_filter += 1
                continue

            if min_buy_increase is not None and sod_to_buy_change < min_buy_increase:
                excluded_by_buy_filter += 1
                continue

            # Stock passed all buy filters
            filtered_by_buy[key] = data

        if excluded_by_buy_filter > 0:
            parts = []
            if min_buy_increase is not None:
                parts.append(f"min +{min_buy_increase}%")
            if max_buy_decrease is not None:
                parts.append(f"max -{max_buy_decrease}%")
            if max_buy_increase is not None:
                parts.append(f"max +{max_buy_increase}%")
            print(f"Excluded {excluded_by_buy_filter} stocks by buy filter ({', '.join(parts)} from SOD)")
            print(f"Remaining stocks: {len(filtered_by_buy)}")

        if not filtered_by_buy:
            print(f"No stocks found matching buy filter criteria.")
            return

        # Update all_data to use buy-filtered data
        all_data = filtered_by_buy

    stocks = [(ticker, date, 0) for ticker, date in all_data.keys()]

    # Calculate average return based on strategy
    def time_to_minutes(time_str):
        h, m = map(int, time_str.split(':'))
        return h * 60 + m

    buy_minutes = time_to_minutes(buy_time)
    tolerance_minutes = 5

    if profit_target is not None or stop_loss is not None:
        # Profit target and/or stop loss strategy
        fallback_label = sell_time if sell_time else "EOD"
        if profit_target and stop_loss:
            strategy_desc = f"+{profit_target}%/-{stop_loss}% or {fallback_label}"
        elif profit_target:
            strategy_desc = f"+{profit_target}% or {fallback_label}"
        else:
            strategy_desc = f"-{stop_loss}% or {fallback_label}"

        print(f"\nCalculating returns: Buy at {buy_time}, Sell at {strategy_desc}...")
        returns = []

        for (ticker, date), data in all_data.items():
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

            # Calculate target prices
            profit_price = buy_price * (1 + profit_target / 100) if profit_target else None
            # stop_loss is negative (e.g., -3.0), so we ADD it: buy_price * (1 + (-3)/100) = buy_price * 0.97
            loss_price = buy_price * (1 + stop_loss / 100) if stop_loss else None

            # Determine the last time to check (sell_time or EOD)
            if sell_time:
                sell_minutes = time_to_minutes(sell_time)
                # Find the index closest to sell_time
                max_check_index = len(times_available) - 1
                for idx, time_str in enumerate(times_available):
                    time_mins = time_to_minutes(time_str)
                    if time_mins > sell_minutes + tolerance_minutes:
                        max_check_index = idx - 1
                        break
            else:
                max_check_index = len(times_available) - 1

            sell_price = None

            # Check each price after buy time for profit target or stop loss (up to sell_time or EOD)
            for idx in range(buy_index + 1, max_check_index + 1):
                time_str = times_available[idx]
                current_price = data[time_str]

                # Check profit target
                if profit_price and current_price >= profit_price:
                    sell_price = profit_price  # Sell at exactly the profit target
                    break

                # Check stop loss
                if loss_price and current_price <= loss_price:
                    sell_price = loss_price  # Sell at exactly the stop loss
                    break

            # Fallback to sell_time or EOD if neither target reached
            if sell_price is None:
                if sell_time:
                    # Find price closest to sell_time
                    min_diff = float('inf')
                    for time_str in times_available:
                        time_mins = time_to_minutes(time_str)
                        diff = abs(time_mins - sell_minutes)
                        if diff <= tolerance_minutes and diff < min_diff:
                            min_diff = diff
                            sell_price = data[time_str]
                else:
                    # Use EOD
                    sell_price = data[times_available[-1]]

            if sell_price is not None:
                return_pct = ((sell_price - buy_price) / buy_price) * 100
                # Deduct 0.8% trading fee per stock
                return_pct -= 0.8
                returns.append(return_pct)

        avg_return = np.mean(returns) if returns else 0
        sell_strategy_label = strategy_desc
        print(f"Average return: {avg_return:.2f}%")
        print(f"Based on {len(returns)} stocks\n")

    else:
        # Fixed time strategy
        sell_time_label = sell_time if sell_time else "EOD"

        print(f"\nCalculating returns: Buy at {buy_time}, Sell at {sell_time_label}...")
        returns = []

        for (ticker, date), data in all_data.items():
            times_available = sorted(data.keys())

            # Find buy price (closest to buy_time)
            buy_price = None
            min_diff = float('inf')
            for time_str in times_available:
                time_mins = time_to_minutes(time_str)
                diff = abs(time_mins - buy_minutes)
                if diff <= tolerance_minutes and diff < min_diff:
                    min_diff = diff
                    buy_price = data[time_str]

            if buy_price is None:
                continue

            # Find sell price
            if sell_time:
                # Use specified sell_time (closest within tolerance)
                sell_price = None
                sell_minutes = time_to_minutes(sell_time)
                min_diff = float('inf')
                for time_str in times_available:
                    time_mins = time_to_minutes(time_str)
                    diff = abs(time_mins - sell_minutes)
                    if diff <= tolerance_minutes and diff < min_diff:
                        min_diff = diff
                        sell_price = data[time_str]
            else:
                # Use EOD (last available time)
                sell_price = data[times_available[-1]] if times_available else None

            # Calculate return
            if buy_price is not None and sell_price is not None:
                return_pct = ((sell_price - buy_price) / buy_price) * 100
                # Deduct 0.8% trading fee per stock
                return_pct -= 0.8
                returns.append(return_pct)

        avg_return = np.mean(returns) if returns else 0
        sell_strategy_label = sell_time_label
        print(f"Average return: {avg_return:.2f}%")
        print(f"Based on {len(returns)} stocks\n")

    # Sort times
    times_sorted = sorted(all_times)

    # Organize data by time point (like the web app does)
    from collections import defaultdict
    prices_by_time = defaultdict(list)

    for (ticker, date), data in all_data.items():
        for time_str, price in data.items():
            prices_by_time[time_str].append(price)

    # Calculate mean and std dev at each time point (exactly like the web app)
    chart_data = []
    for time_str in times_sorted:
        if time_str in prices_by_time:
            prices = prices_by_time[time_str]
            if len(prices) >= 2:
                mean_val = np.mean(prices)
                std_val = np.std(prices, ddof=1)  # Sample std dev
                chart_data.append({
                    'time': time_str,
                    'mean': mean_val,
                    'std_dev': std_val,
                    'upper_band': mean_val + std_val,
                    'lower_band': mean_val - std_val,
                    'count': len(prices)
                })
            elif len(prices) == 1:
                mean_val = prices[0]
                chart_data.append({
                    'time': time_str,
                    'mean': mean_val,
                    'std_dev': 0.0,
                    'upper_band': mean_val,
                    'lower_band': mean_val,
                    'count': 1
                })

    # Apply Gaussian smoothing (exact same function as web app)
    def apply_gaussian_smoothing(data):
        """Apply Gaussian smoothing to chart data (exact copy from web app)."""
        if len(data) <= 5:
            return data

        mean_values = np.array([d['mean'] for d in data])
        n_points = len(mean_values)

        # Adaptive window size based on data length
        if n_points < 30:
            window_size = min(7, n_points)
            sigma = 2.0
        else:
            window_size = min(15, n_points // 3)
            sigma = 3.0

        # Create Gaussian kernel
        x = np.arange(window_size) - (window_size - 1) / 2
        kernel = np.exp(-0.5 * (x / sigma) ** 2)
        kernel = kernel / kernel.sum()

        # Apply edge-aware convolution
        pad_width = window_size // 2
        padded_values = np.pad(mean_values, pad_width, mode='edge')
        smoothed_padded = np.convolve(padded_values, kernel, mode='same')
        smoothed_values = smoothed_padded[pad_width:pad_width + n_points]

        # Build smoothed chart data
        smoothed_data = []
        for i, data_point in enumerate(data):
            smoothed_data.append({
                'time': data_point['time'],
                'mean': float(smoothed_values[i]),
                'count': data_point.get('count', 0)
            })

        return smoothed_data

    # Apply smoothing
    smoothed_data = apply_gaussian_smoothing(chart_data)

    # Extract arrays for plotting
    times = [d['time'] for d in chart_data]
    averages = np.array([d['mean'] for d in chart_data])
    std_devs = np.array([d['std_dev'] for d in chart_data])
    upper_bands = np.array([d['upper_band'] for d in chart_data])
    lower_bands = np.array([d['lower_band'] for d in chart_data])
    smoothed_averages = np.array([d['mean'] for d in smoothed_data])

    # Create a mapping from time string to numeric index for proper chronological plotting
    time_to_index = {time_str: idx for idx, time_str in enumerate(times)}
    time_indices = np.arange(len(times))

    # Create two subplots side by side
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8))

    # === LEFT PLOT: Individual Stocks ===
    import matplotlib.cm as cm
    num_stocks = len(all_data)
    colors = cm.rainbow(np.linspace(0, 1, num_stocks))

    for idx, ((ticker, date), data) in enumerate(all_data.items()):
        # Sort this stock's times chronologically and convert to indices
        stock_times_sorted = sorted(data.keys())
        stock_indices = []
        stock_prices = []
        for time_str in stock_times_sorted:
            if time_str in time_to_index:
                stock_indices.append(time_to_index[time_str])
                stock_prices.append(data[time_str])

        ax1.plot(stock_indices, stock_prices, alpha=0.5, linewidth=0.8,
                color=colors[idx], zorder=1)

    # Add baseline and selection window to left plot (using indices)
    ax1.axhline(y=100, color='black', linestyle='--', linewidth=1, alpha=0.3, label='9:00 Baseline (100%)')
    if start_time in time_to_index:
        ax1.axvline(x=time_to_index[start_time], color='green', linestyle='--', linewidth=1.5, alpha=0.5, label=f'Selection Window')
    if end_time in time_to_index:
        ax1.axvline(x=time_to_index[end_time], color='green', linestyle='--', linewidth=1.5, alpha=0.5)

    # Formatting for left plot
    ax1.set_xlabel('Time of Day', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Normalized Price (%)', fontsize=12, fontweight='bold')
    if max_gain_pct is not None:
        title_gain = f'{min_gain_pct}% to {max_gain_pct}%'
    else:
        title_gain = f'>{min_gain_pct}%'
    ax1.set_title(f'Individual Stocks ({len(stocks)} stocks)\n'
                  f'Gain {title_gain} from {start_time} to {end_time}',
                  fontsize=13, fontweight='bold', pad=15)
    ax1.legend(loc='best', fontsize=10, framealpha=0.95)
    ax1.grid(True, alpha=0.2)

    # Add return info text box on left plot
    return_color = 'green' if avg_return >= 0 else 'red'
    ax1.text(0.02, 0.98, f'Avg Return ({buy_time} → {sell_strategy_label}): {avg_return:+.2f}%',
             transform=ax1.transAxes, fontsize=11, fontweight='bold',
             verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor=return_color, linewidth=2))

    # Set x-ticks to show time strings at proper indices
    n_labels = len(times)
    if n_labels > 30:
        step = max(1, n_labels // 30)
        tick_indices = time_indices[::step]
        tick_labels = [times[i] for i in range(0, len(times), step)]
    else:
        tick_indices = time_indices
        tick_labels = times

    ax1.set_xticks(tick_indices)
    ax1.set_xticklabels(tick_labels, rotation=45, ha='right')

    # === RIGHT PLOT: Averages ===
    # Plot standard deviation bands (filled area) using numeric indices
    ax2.fill_between(time_indices, lower_bands, upper_bands,
                     alpha=0.2, color='#007bff', label='±1 Std Dev', zorder=50)

    # Plot raw average (thick line)
    ax2.plot(time_indices, averages, linewidth=3.5, color='#007bff',
            label=f'Average', zorder=100, alpha=0.9)

    # Plot smoothed average (thick line)
    ax2.plot(time_indices, smoothed_averages, linewidth=3.5, color='#dc3545',
            label='Smoothed Average', zorder=101, linestyle='-', alpha=0.95)

    # Add baseline and selection window to right plot (using indices)
    ax2.axhline(y=100, color='black', linestyle='--', linewidth=1, alpha=0.3, label='9:00 Baseline (100%)')
    if start_time in time_to_index:
        ax2.axvline(x=time_to_index[start_time], color='green', linestyle='--', linewidth=1.5, alpha=0.5, label=f'Selection Window')
    if end_time in time_to_index:
        ax2.axvline(x=time_to_index[end_time], color='green', linestyle='--', linewidth=1.5, alpha=0.5)

    # Formatting for right plot
    ax2.set_xlabel('Time of Day', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Normalized Price (%)', fontsize=12, fontweight='bold')
    ax2.set_title(f'Average Performance\n'
                  f'{len(stocks)} stocks • Smoothed with Gaussian filter',
                  fontsize=13, fontweight='bold', pad=15)
    ax2.legend(loc='best', fontsize=10, framealpha=0.95)
    ax2.grid(True, alpha=0.2)

    # Add return info text box on right plot
    ax2.text(0.02, 0.98, f'Avg Return ({buy_time} → {sell_strategy_label}): {avg_return:+.2f}%',
             transform=ax2.transAxes, fontsize=11, fontweight='bold',
             verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor=return_color, linewidth=2))

    # Set x-ticks to show time strings at proper indices (same as left plot)
    ax2.set_xticks(tick_indices)
    ax2.set_xticklabels(tick_labels, rotation=45, ha='right')

    plt.tight_layout()

    # Save if path provided
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"✓ Plot saved to: {save_path}")

    # Show if requested
    if show_plot:
        plt.show()

    print(f"\n{'='*80}")
    print("Analysis complete!")
    print(f"{'='*80}\n")


def main():
    """Main entry point for the script."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Plot earnings stocks by early gain pattern',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default: all stocks from 09:00 to 17:00 with gain >= 0%
  python plot_earnings_subset.py

  # Custom gain threshold and window
  python plot_earnings_subset.py --min-gain 3.0 --start 09:00 --end 09:15

  # Save to file instead of showing
  python plot_earnings_subset.py --save earnings_plot.png --no-show

  # Different time window (e.g., morning momentum)
  python plot_earnings_subset.py --min-gain 2.0 --start 09:00 --end 10:00

Note: Uses closest available time within 5 minutes if exact time not found.
      This maximizes data coverage while maintaining accuracy.
        """
    )

    parser.add_argument('--min-gain', type=float, default=1.5,
                        help='Minimum gain percentage (default: 1.5%)')
    parser.add_argument('--max-gain', type=float, default=100.0,
                        help='Maximum gain percentage ceiling (default: 100.0, effectively no filter). Excludes stocks above this gain.')
    parser.add_argument('--start', type=str, default='09:00',
                        help='Start time in HH:MM format (default: 09:00). Uses closest time within 5 min if exact time unavailable.')
    parser.add_argument('--end', type=str, default='09:10',
                        help='End time in HH:MM format (default: 09:10). Uses closest time within 5 min if exact time unavailable.')
    parser.add_argument('--buy', type=str, default='09:30',
                        help='Buy time in HH:MM format (default: 09:30). When to purchase stocks. Uses closest time within 5 min if exact time unavailable.')
    parser.add_argument('--sell', type=str, default='16:40',
                        help='Sell time for return calculation in HH:MM format (default: 16:40). Uses closest time within 5 min if exact time unavailable.')
    parser.add_argument('--profit-target', type=float, default=19.0,
                        help='Profit target percentage (default: 19.0 for 19%%). Sell when reached or at sell time.')
    parser.add_argument('--stop-loss', type=float, default=-21.0,
                        help='Stop loss percentage (e.g., -21.0 for -21%%). Must be negative. Sell when reached or at EOD. Default: -21.0')
    parser.add_argument('--max-buy-increase', type=float, default=None,
                        help='Maximum allowed increase from SOD to buy time (e.g., 10.0 for 10%%). Stocks above this are excluded. (default: 10.0)')
    parser.add_argument('--max-buy-decrease', type=float, default=None,
                        help='Maximum allowed decrease from SOD to buy time (e.g., 2.0 for -2%%). Stocks below this are excluded. (default: 2.0)')
    parser.add_argument('--min-buy-increase', type=float, default=None,
                        help='Minimum required increase from SOD to buy time (default: None, no filter). Stocks below this are excluded.')
    parser.add_argument('--min-data-points', type=int, default=6,
                        help='Minimum datapoints in hour before buy time (or from 09:00 if buying before 10:00). Default: 6.')
    parser.add_argument('--max-data-points', type=int, default=None,
                        help='Maximum datapoints in hour before buy time (or from 09:00 if buying before 10:00). Default: None (no limit)')
    parser.add_argument('--min-sod-increase', type=float, default=None,
                        help='Minimum SOD increase percentage (yesterday_close/open - 1) * 100. Default: None (no filter)')
    parser.add_argument('--min-return-1m', type=float, default=None,
                        help='Minimum 1-month return percentage. Default: None (no filter)')
    parser.add_argument('--min-return-3m', type=float, default=None,
                        help='Minimum 3-month return percentage. Default: None (no filter)')
    parser.add_argument('--min-return-1y', type=float, default=None,
                        help='Minimum 1-year return percentage. Default: None (no filter)')
    parser.add_argument('--min-sma200-ratio', type=float, default=None,
                        help='Minimum price/SMA200 ratio as percentage (yesterday_close/sma_200 - 1) * 100. E.g., 0 means price must be above SMA200. Default: None (no filter)')
    parser.add_argument('--save', type=str, default=None,
                        help='Path to save the plot (e.g., plot.png)')
    parser.add_argument('--no-show', action='store_true',
                        help='Do not display the plot (useful with --save)')

    args = parser.parse_args()

    # Run the analysis
    plot_early_gainers(
        min_gain_pct=args.min_gain,
        max_gain_pct=args.max_gain,
        start_time=args.start,
        end_time=args.end,
        buy_time=args.buy,
        sell_time=args.sell,
        profit_target=args.profit_target,
        stop_loss=args.stop_loss,
        max_buy_increase=args.max_buy_increase,
        max_buy_decrease=args.max_buy_decrease,
        min_buy_increase=args.min_buy_increase,
        min_data_points=args.min_data_points,
        max_data_points=args.max_data_points,
        min_sod_increase=args.min_sod_increase,
        min_return_1m=args.min_return_1m,
        min_return_3m=args.min_return_3m,
        min_return_1y=args.min_return_1y,
        min_sma200_ratio=args.min_sma200_ratio,
        save_path=args.save,
        show_plot=not args.no_show
    )


if __name__ == '__main__':
    main()
