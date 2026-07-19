"""Flask routes for Earnings Predictor web UI."""

from flask import render_template, jsonify, request
from datetime import date, datetime
import logging

from src.utils.database import get_watchlist, get_signals
from src.screening.screener import Screener

logger = logging.getLogger(__name__)


def register_routes(app):
    """
    Register all routes with the Flask app.

    Args:
        app: Flask application instance
    """

    @app.route('/')
    def dashboard():
        """Main dashboard view."""
        try:
            today = date.today().strftime('%Y-%m-%d')

            # Get today's watchlist count
            watchlist = get_watchlist(today)
            watchlist_count = len(watchlist)

            # Get recent signals (Phase 4)
            recent_signals = get_signals(date=today, limit=5)

            # Summary stats
            stats = {
                'watchlist_count': watchlist_count,
                'signals_today': len(recent_signals),
                'monitoring_status': 'Not Running',  # Updated by JavaScript
                'date': today
            }

            return render_template('dashboard.html', stats=stats, signals=recent_signals)

        except Exception as e:
            logger.error(f"Error rendering dashboard: {e}")
            return f"Error loading dashboard: {str(e)}", 500

    @app.route('/watchlist')
    def watchlist_view():
        """Watchlist view showing today's screened stocks."""
        try:
            # Get date from query param or use today
            date_param = request.args.get('date')
            if date_param:
                target_date = date_param
            else:
                target_date = date.today().strftime('%Y-%m-%d')

            # Get watchlist from database
            watchlist = get_watchlist(target_date)

            # Also get calendar info to show what was processed
            from src.screening.report_calendar import ReportCalendar
            from datetime import datetime
            cal = ReportCalendar()
            try:
                target_date_obj = datetime.strptime(target_date, '%Y-%m-%d').date()
                calendar_entries = cal.get_reports_for_date(target_date_obj)
            except:
                calendar_entries = []

            return render_template(
                'watchlist.html',
                watchlist=watchlist,
                date=target_date,
                calendar_count=len(calendar_entries),
                calendar_entries=calendar_entries[:10]  # Show first 10 for reference
            )

        except Exception as e:
            logger.error(f"Error rendering watchlist: {e}")
            return f"Error loading watchlist: {str(e)}", 500

    @app.route('/signals')
    def signals_view():
        """Signals view - displays detected entry signals."""
        try:
            # Get date from query param or use today
            date_param = request.args.get('date')

            if not date_param:
                date_param = date.today().strftime('%Y-%m-%d')

            # Get signals
            signals = get_signals(date=date_param, limit=50)

            return render_template('signals.html', signals=signals, date=date_param)

        except Exception as e:
            logger.error(f"Error rendering signals: {e}")
            return f"Error loading signals: {str(e)}", 500

    @app.route('/history')
    def history_view():
        """Hypothetical trade history view with strategy tabs."""
        try:
            from src.utils.database import get_hypothetical_trades, get_hypothetical_stats
            from src.utils.config import load_config

            # Get date from query param or use today
            date_param = request.args.get('date')

            if date_param:
                target_date_obj = datetime.strptime(date_param, '%Y-%m-%d').date()
                date_filter = date_param
            else:
                # Show today's trades by default
                target_date_obj = date.today()
                date_filter = target_date_obj.strftime('%Y-%m-%d')

            # Load profit targets from config
            config = load_config()
            strategies_config = config.get('strategies', {})
            profit_targets_config = strategies_config.get('profit_targets', {})
            profit_targets = profit_targets_config.get('targets', [1.0, 2.0, 3.0, 4.0, 5.0])

            # Fetch data for EOD strategy
            eod_trades = get_hypothetical_trades(trade_date=target_date_obj, limit=100, strategy_type='eod')
            eod_stats = get_hypothetical_stats(trade_date=target_date_obj, strategy_type='eod')
            eod_overall = get_hypothetical_stats(strategy_type='eod')

            # Fetch data for all profit target strategies
            strategies_data = []
            for target_pct in profit_targets:
                strategy_type = f"{int(target_pct)}pct_target"
                strategies_data.append({
                    'name': f"{int(target_pct)}% Target",
                    'type': strategy_type,
                    'target_pct': target_pct,
                    'trades': get_hypothetical_trades(trade_date=target_date_obj, limit=100, strategy_type=strategy_type),
                    'stats': get_hypothetical_stats(trade_date=target_date_obj, strategy_type=strategy_type),
                    'overall': get_hypothetical_stats(strategy_type=strategy_type)
                })

            return render_template(
                'history.html',
                eod_trades=eod_trades,
                eod_stats=eod_stats,
                eod_overall=eod_overall,
                strategies=strategies_data,
                date=date_filter
            )

        except Exception as e:
            logger.error(f"Error rendering history: {e}")
            return f"Error loading history: {str(e)}", 500

    @app.route('/earnings-analysis')
    def earnings_analysis_view():
        """Earnings analysis visualization page."""
        try:
            from src.utils.database import get_connection
            import json

            conn = get_connection()
            cursor = conn.cursor()

            # Check if table exists and has data
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='earnings_intraday_analysis'
            """)
            table_exists = cursor.fetchone() is not None

            if not table_exists:
                conn.close()
                return render_template(
                    'earnings_analysis.html',
                    has_data=False,
                    message="No earnings data found. Run the extraction script first."
                )

            # Get summary stats - ALL earnings days
            cursor.execute("""
                SELECT
                    COUNT(DISTINCT ticker || earnings_date) as total_days,
                    COUNT(DISTINCT ticker) as total_tickers,
                    MIN(earnings_date) as first_date,
                    MAX(earnings_date) as last_date
                FROM earnings_intraday_analysis
            """)
            stats = dict(cursor.fetchone())

            # Get filter-passed count
            cursor.execute("""
                SELECT COUNT(DISTINCT ticker || earnings_date)
                FROM earnings_intraday_analysis
                WHERE passed_filter = 1
            """)
            filter_passed_count = cursor.fetchone()[0]

            if stats['total_days'] == 0:
                conn.close()
                return render_template(
                    'earnings_analysis.html',
                    has_data=False,
                    message="No earnings data found. Run extraction script first."
                )

            # Get all data points and calculate statistics in Python
            # (SQLite doesn't have STDEV function)

            from collections import defaultdict
            import statistics

            # Dataset 1: ALL earnings (no filter)
            cursor.execute("""
                SELECT
                    time_of_day,
                    normalized_price
                FROM earnings_intraday_analysis
                ORDER BY time_of_day
            """)

            all_earnings_by_time = defaultdict(list)
            for row in cursor.fetchall():
                time_of_day = row[0]
                normalized_price = row[1]
                all_earnings_by_time[time_of_day].append(normalized_price)

            # Dataset 2: Earnings that passed filter
            cursor.execute("""
                SELECT
                    time_of_day,
                    normalized_price
                FROM earnings_intraday_analysis
                WHERE passed_filter = 1
                ORDER BY time_of_day
            """)

            filter_passed_by_time = defaultdict(list)
            for row in cursor.fetchall():
                time_of_day = row[0]
                normalized_price = row[1]
                filter_passed_by_time[time_of_day].append(normalized_price)

            # Dataset 3: Only earnings that created signals
            cursor.execute("""
                SELECT
                    time_of_day,
                    normalized_price
                FROM earnings_intraday_analysis
                WHERE passed_filter = 1 AND created_signal = 1
                ORDER BY time_of_day
            """)

            signal_data_by_time = defaultdict(list)
            for row in cursor.fetchall():
                time_of_day = row[0]
                normalized_price = row[1]
                signal_data_by_time[time_of_day].append(normalized_price)

            # Dataset 4: Top 20% performers
            cursor.execute("""
                SELECT
                    time_of_day,
                    normalized_price
                FROM earnings_intraday_analysis
                WHERE top_20pct_performer = 1
                ORDER BY time_of_day
            """)

            top_20pct_by_time = defaultdict(list)
            for row in cursor.fetchall():
                time_of_day = row[0]
                normalized_price = row[1]
                top_20pct_by_time[time_of_day].append(normalized_price)

            # Dataset 5: Bottom 30% performers
            cursor.execute("""
                SELECT
                    time_of_day,
                    normalized_price
                FROM earnings_intraday_analysis
                WHERE bottom_30pct_performer = 1
                ORDER BY time_of_day
            """)

            bottom_30pct_by_time = defaultdict(list)
            for row in cursor.fetchall():
                time_of_day = row[0]
                normalized_price = row[1]
                bottom_30pct_by_time[time_of_day].append(normalized_price)

            conn.close()

            # Calculate mean and std dev for all five datasets
            all_earnings_chart_data = []
            filter_passed_chart_data = []
            signal_chart_data = []
            top_20pct_chart_data = []
            bottom_30pct_chart_data = []

            # Process dataset 1: ALL earnings (yellow line with std dev)
            for time_str in sorted(all_earnings_by_time.keys()):
                prices = all_earnings_by_time[time_str]

                if len(prices) >= 2:  # Need at least 2 points for std dev
                    mean_val = statistics.mean(prices)
                    std_val = statistics.stdev(prices)
                    all_earnings_chart_data.append({
                        'time': time_str,
                        'mean': round(mean_val, 2),
                        'std_dev': round(std_val, 2),
                        'upper_band': round(mean_val + std_val, 2),
                        'lower_band': round(mean_val - std_val, 2),
                        'count': len(prices)
                    })
                elif len(prices) == 1:  # Only one point, no std dev
                    mean_val = statistics.mean(prices)
                    all_earnings_chart_data.append({
                        'time': time_str,
                        'mean': round(mean_val, 2),
                        'std_dev': 0.0,
                        'upper_band': round(mean_val, 2),
                        'lower_band': round(mean_val, 2),
                        'count': len(prices)
                    })

            # Process dataset 2: Filter-passed earnings (blue line with std dev)
            for time_str in sorted(filter_passed_by_time.keys()):
                prices = filter_passed_by_time[time_str]

                if len(prices) >= 2:  # Need at least 2 points for std dev
                    mean_val = statistics.mean(prices)
                    std_val = statistics.stdev(prices)
                    filter_passed_chart_data.append({
                        'time': time_str,
                        'mean': round(mean_val, 2),
                        'std_dev': round(std_val, 2),
                        'upper_band': round(mean_val + std_val, 2),
                        'lower_band': round(mean_val - std_val, 2),
                        'count': len(prices)
                    })
                elif len(prices) == 1:  # Only one point, no std dev
                    mean_val = statistics.mean(prices)
                    filter_passed_chart_data.append({
                        'time': time_str,
                        'mean': round(mean_val, 2),
                        'std_dev': 0.0,
                        'upper_band': round(mean_val, 2),
                        'lower_band': round(mean_val, 2),
                        'count': len(prices)
                    })

            # Process dataset 3: Signal-created earnings (green line with std dev)
            for time_str in sorted(signal_data_by_time.keys()):
                prices = signal_data_by_time[time_str]

                if len(prices) >= 2:  # Need at least 2 points for std dev
                    mean_val = statistics.mean(prices)
                    std_val = statistics.stdev(prices)
                    signal_chart_data.append({
                        'time': time_str,
                        'mean': round(mean_val, 2),
                        'std_dev': round(std_val, 2),
                        'upper_band': round(mean_val + std_val, 2),
                        'lower_band': round(mean_val - std_val, 2),
                        'count': len(prices)
                    })
                elif len(prices) == 1:  # Only one point, no std dev
                    mean_val = statistics.mean(prices)
                    signal_chart_data.append({
                        'time': time_str,
                        'mean': round(mean_val, 2),
                        'std_dev': 0.0,
                        'upper_band': round(mean_val, 2),
                        'lower_band': round(mean_val, 2),
                        'count': len(prices)
                    })

            # Process dataset 4: Top 20% performers (purple line with std dev)
            for time_str in sorted(top_20pct_by_time.keys()):
                prices = top_20pct_by_time[time_str]

                if len(prices) >= 2:  # Need at least 2 points for std dev
                    mean_val = statistics.mean(prices)
                    std_val = statistics.stdev(prices)
                    top_20pct_chart_data.append({
                        'time': time_str,
                        'mean': round(mean_val, 2),
                        'std_dev': round(std_val, 2),
                        'upper_band': round(mean_val + std_val, 2),
                        'lower_band': round(mean_val - std_val, 2),
                        'count': len(prices)
                    })
                elif len(prices) == 1:  # Only one point, no std dev
                    mean_val = statistics.mean(prices)
                    top_20pct_chart_data.append({
                        'time': time_str,
                        'mean': round(mean_val, 2),
                        'std_dev': 0.0,
                        'upper_band': round(mean_val, 2),
                        'lower_band': round(mean_val, 2),
                        'count': len(prices)
                    })

            # Process dataset 5: Bottom 30% performers (red line with std dev)
            for time_str in sorted(bottom_30pct_by_time.keys()):
                prices = bottom_30pct_by_time[time_str]

                if len(prices) >= 2:  # Need at least 2 points for std dev
                    mean_val = statistics.mean(prices)
                    std_val = statistics.stdev(prices)
                    bottom_30pct_chart_data.append({
                        'time': time_str,
                        'mean': round(mean_val, 2),
                        'std_dev': round(std_val, 2),
                        'upper_band': round(mean_val + std_val, 2),
                        'lower_band': round(mean_val - std_val, 2),
                        'count': len(prices)
                    })
                elif len(prices) == 1:  # Only one point, no std dev
                    mean_val = statistics.mean(prices)
                    bottom_30pct_chart_data.append({
                        'time': time_str,
                        'mean': round(mean_val, 2),
                        'std_dev': 0.0,
                        'upper_band': round(mean_val, 2),
                        'lower_band': round(mean_val, 2),
                        'count': len(prices)
                    })

            # Helper function for Gaussian smoothing
            def apply_gaussian_smoothing(chart_data):
                """Apply Gaussian smoothing to chart data."""
                if len(chart_data) <= 5:
                    # Not enough data for smoothing, return copy of original
                    return [{'time': d['time'], 'mean': d['mean'], 'count': d.get('count', 0)}
                            for d in chart_data]

                import numpy as np

                # Extract mean values for smoothing
                mean_values = np.array([d['mean'] for d in chart_data])
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
                for i, data_point in enumerate(chart_data):
                    smoothed_data.append({
                        'time': data_point['time'],
                        'mean': round(float(smoothed_values[i]), 2),
                        'count': data_point.get('count', 0)
                    })

                return smoothed_data

            # Apply smoothing to all three datasets
            all_earnings_smoothed = apply_gaussian_smoothing(all_earnings_chart_data)
            filter_passed_smoothed = apply_gaussian_smoothing(filter_passed_chart_data)
            signal_smoothed_chart_data = apply_gaussian_smoothing(signal_chart_data)
            top_20pct_smoothed = apply_gaussian_smoothing(top_20pct_chart_data)
            bottom_30pct_smoothed = apply_gaussian_smoothing(bottom_30pct_chart_data)

            # Count how many earnings days created signals
            cursor = get_connection().cursor()
            cursor.execute("""
                SELECT COUNT(DISTINCT ticker || earnings_date)
                FROM earnings_intraday_analysis
                WHERE passed_filter = 1 AND created_signal = 1
            """)
            signal_days_count = cursor.fetchone()[0]
            cursor.connection.close()

            return render_template(
                'earnings_analysis.html',
                has_data=True,
                stats=stats,
                filter_passed_count=filter_passed_count,
                signal_days_count=signal_days_count,
                # Raw data with std dev
                all_earnings_chart_data=json.dumps(all_earnings_chart_data),
                filter_passed_chart_data=json.dumps(filter_passed_chart_data),
                signal_chart_data=json.dumps(signal_chart_data),
                top_20pct_chart_data=json.dumps(top_20pct_chart_data),
                bottom_30pct_chart_data=json.dumps(bottom_30pct_chart_data),
                # Smoothed data
                all_earnings_smoothed=json.dumps(all_earnings_smoothed),
                filter_passed_smoothed=json.dumps(filter_passed_smoothed),
                signal_smoothed_chart_data=json.dumps(signal_smoothed_chart_data),
                top_20pct_smoothed=json.dumps(top_20pct_smoothed),
                bottom_30pct_smoothed=json.dumps(bottom_30pct_smoothed),
                # Raw versions for reference
                all_earnings_chart_data_raw=all_earnings_chart_data,
                filter_passed_chart_data_raw=filter_passed_chart_data,
                signal_chart_data_raw=signal_chart_data,
                top_20pct_chart_data_raw=top_20pct_chart_data,
                bottom_30pct_chart_data_raw=bottom_30pct_chart_data,
                all_earnings_smoothed_raw=all_earnings_smoothed,
                filter_passed_smoothed_raw=filter_passed_smoothed,
                signal_smoothed_chart_data_raw=signal_smoothed_chart_data,
                top_20pct_smoothed_raw=top_20pct_smoothed,
                bottom_30pct_smoothed_raw=bottom_30pct_smoothed
            )

        except Exception as e:
            logger.error(f"Error rendering earnings analysis: {e}", exc_info=True)
            return f"Error loading earnings analysis: {str(e)}", 500

    # API Endpoints

    @app.route('/api/calculate-roi')
    def api_calculate_roi():
        """
        Calculate per-stock ROI and aggregate.

        Query params:
            purchase_time: Time of purchase (e.g., "09:30")
            sell_time: Time of sell (e.g., "14:00")
            categories: Comma-separated list of categories (e.g., "all,filter,signal")

        Returns aggregated ROI for each category, including 1% early exit scenario.
        """
        try:
            purchase_time = request.args.get('purchase_time')
            sell_time = request.args.get('sell_time')
            categories_str = request.args.get('categories', 'all,filter,signal')

            if not purchase_time or not sell_time:
                return jsonify({
                    'success': False,
                    'error': 'purchase_time and sell_time are required'
                }), 400

            categories = categories_str.split(',')

            from src.utils.database import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            results = {}

            for category in categories:
                # Determine filter criteria
                if category == 'all':
                    where_clause = "1=1"
                    category_name = "All Earnings"
                elif category == 'filter':
                    where_clause = "passed_filter = 1"
                    category_name = "Filter-Passed"
                elif category == 'signal':
                    where_clause = "passed_filter = 1 AND created_signal = 1"
                    category_name = "Signal-Created"
                elif category == 'top30':
                    where_clause = "top_20pct_performer = 1"
                    category_name = "Top 30% Performers"
                elif category == 'bottom30':
                    where_clause = "bottom_30pct_performer = 1"
                    category_name = "Bottom 30% Performers"
                else:
                    continue

                # Get all unique tickers for this category
                cursor.execute(f"""
                    SELECT DISTINCT ticker, earnings_date
                    FROM earnings_intraday_analysis
                    WHERE {where_clause}
                """)

                tickers = cursor.fetchall()

                if not tickers:
                    results[category_name] = {
                        'roi': None,
                        'roi_with_1pct_exit': None,
                        'roi_with_2pct_exit': None,
                        'roi_with_3pct_exit': None,
                        'roi_with_4pct_exit': None,
                        'roi_with_5pct_exit': None,
                        'stock_count': 0,
                        'error': 'No stocks in this category'
                    }
                    continue

                per_stock_rois = []
                per_stock_rois_with_1pct = []
                per_stock_rois_with_2pct = []
                per_stock_rois_with_3pct = []
                per_stock_rois_with_4pct = []
                per_stock_rois_with_5pct = []

                def find_nearest_price(target_time_str, price_map, window_minutes=10):
                    """
                    Find the nearest trade price within ±window_minutes of target time.

                    Args:
                        target_time_str: Target time string (e.g., "09:30")
                        price_map: Dict mapping time strings to prices
                        window_minutes: Window size in minutes (default 10 = ±10 min = 20 min total)

                    Returns:
                        Tuple of (nearest_time, price) or (None, None) if no trade in window
                    """
                    from datetime import datetime, timedelta

                    # Parse target time
                    target_hour, target_min = map(int, target_time_str.split(':'))
                    target_dt = datetime(2000, 1, 1, target_hour, target_min)

                    best_time = None
                    best_price = None
                    min_diff = timedelta(minutes=window_minutes + 1)  # Start with diff > window

                    for time_str, price in price_map.items():
                        # Parse this time
                        hour, minute = map(int, time_str.split(':'))
                        time_dt = datetime(2000, 1, 1, hour, minute)

                        # Calculate time difference
                        diff = abs(time_dt - target_dt)

                        # Check if within window and closer than current best
                        if diff <= timedelta(minutes=window_minutes) and diff < min_diff:
                            best_time = time_str
                            best_price = price
                            min_diff = diff

                    return best_time, best_price

                # Calculate ROI for each stock
                for ticker, earnings_date in tickers:
                    # Get intraday data for this stock
                    cursor.execute("""
                        SELECT time_of_day, normalized_price
                        FROM earnings_intraday_analysis
                        WHERE ticker = ? AND earnings_date = ?
                        ORDER BY time_of_day
                    """, (ticker, earnings_date))

                    intraday_data = cursor.fetchall()

                    if not intraday_data:
                        continue

                    # Create time -> price map
                    price_map = {row[0]: row[1] for row in intraday_data}

                    # Get purchase and sell prices using nearest trade within ±10 min window
                    purchase_time_actual, purchase_price = find_nearest_price(purchase_time, price_map)
                    sell_time_actual, sell_price = find_nearest_price(sell_time, price_map)

                    if purchase_price is None or sell_price is None:
                        continue

                    # Calculate standard ROI
                    roi = sell_price - purchase_price
                    per_stock_rois.append(roi)

                    # Get sorted times for checking profit targets
                    times_sorted = sorted(price_map.keys())
                    purchase_idx = times_sorted.index(purchase_time_actual) if purchase_time_actual in times_sorted else None
                    sell_idx = times_sorted.index(sell_time_actual) if sell_time_actual in times_sorted else None

                    if purchase_idx is None or sell_idx is None:
                        continue

                    # Calculate ROI with early exits for each profit target
                    profit_targets = [1.0, 2.0, 3.0, 4.0, 5.0]
                    profit_target_rois = [per_stock_rois_with_1pct, per_stock_rois_with_2pct,
                                         per_stock_rois_with_3pct, per_stock_rois_with_4pct,
                                         per_stock_rois_with_5pct]

                    for target_pct, roi_list in zip(profit_targets, profit_target_rois):
                        target_price = purchase_price + target_pct
                        exit_price = sell_price

                        # Check if target was hit before sell_time
                        for time in times_sorted[purchase_idx + 1:sell_idx + 1]:
                            price = price_map[time]
                            if price >= target_price:
                                # Hit target early
                                exit_price = target_price
                                break

                        roi_with_target = exit_price - purchase_price
                        roi_list.append(roi_with_target)

                # Aggregate (mean)
                if per_stock_rois:
                    avg_roi = sum(per_stock_rois) / len(per_stock_rois)
                    avg_roi_with_1pct = sum(per_stock_rois_with_1pct) / len(per_stock_rois_with_1pct)
                    avg_roi_with_2pct = sum(per_stock_rois_with_2pct) / len(per_stock_rois_with_2pct)
                    avg_roi_with_3pct = sum(per_stock_rois_with_3pct) / len(per_stock_rois_with_3pct)
                    avg_roi_with_4pct = sum(per_stock_rois_with_4pct) / len(per_stock_rois_with_4pct)
                    avg_roi_with_5pct = sum(per_stock_rois_with_5pct) / len(per_stock_rois_with_5pct)

                    results[category_name] = {
                        'roi': round(avg_roi, 2),
                        'roi_with_1pct_exit': round(avg_roi_with_1pct, 2),
                        'roi_with_2pct_exit': round(avg_roi_with_2pct, 2),
                        'roi_with_3pct_exit': round(avg_roi_with_3pct, 2),
                        'roi_with_4pct_exit': round(avg_roi_with_4pct, 2),
                        'roi_with_5pct_exit': round(avg_roi_with_5pct, 2),
                        'stock_count': len(per_stock_rois)
                    }
                else:
                    results[category_name] = {
                        'roi': None,
                        'roi_with_1pct_exit': None,
                        'roi_with_2pct_exit': None,
                        'roi_with_3pct_exit': None,
                        'roi_with_4pct_exit': None,
                        'roi_with_5pct_exit': None,
                        'stock_count': 0,
                        'error': 'No valid data for this time window'
                    }

            conn.close()

            return jsonify({
                'success': True,
                'purchase_time': purchase_time,
                'sell_time': sell_time,
                'results': results
            })

        except Exception as e:
            logger.error(f"Error in /api/calculate-roi: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/watchlist')
    def api_watchlist():
        """API endpoint to get watchlist data."""
        try:
            date_param = request.args.get('date', date.today().strftime('%Y-%m-%d'))
            watchlist = get_watchlist(date_param)

            return jsonify({
                'success': True,
                'date': date_param,
                'count': len(watchlist),
                'stocks': watchlist
            })

        except Exception as e:
            logger.error(f"Error in /api/watchlist: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/signals')
    def api_signals():
        """API endpoint to get signals data."""
        try:
            date_param = request.args.get('date')
            limit = int(request.args.get('limit', 50))

            signals = get_signals(date=date_param, limit=limit)

            return jsonify({
                'success': True,
                'count': len(signals),
                'signals': signals
            })

        except Exception as e:
            logger.error(f"Error in /api/signals: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/monitoring/status')
    def api_monitoring_status():
        """API endpoint for monitoring process status."""
        try:
            from src.utils.database import get_latest_intraday_data
            from datetime import datetime

            today = date.today().strftime('%Y-%m-%d')
            latest_data = get_latest_intraday_data(today)

            if latest_data:
                # Check if data is recent (within last 5 minutes)
                # Parse timestamp and ensure both datetimes are naive for comparison
                timestamp_str = latest_data[0]['timestamp']

                # Handle timezone-aware timestamps by stripping timezone info
                if '+' in timestamp_str or timestamp_str.endswith('Z'):
                    # Remove timezone info for naive comparison
                    # Format: "2026-02-13 11:21:05.830002+01:00"
                    if '+' in timestamp_str:
                        timestamp_str = timestamp_str.split('+')[0]
                    elif timestamp_str.endswith('Z'):
                        timestamp_str = timestamp_str[:-1]

                latest_timestamp = datetime.fromisoformat(timestamp_str)
                age_seconds = (datetime.now() - latest_timestamp).total_seconds()

                status = 'running' if age_seconds < 300 else 'idle'
                message = f"Last update: {age_seconds:.0f} seconds ago"
            else:
                status = 'not_running'
                message = 'No monitoring data found for today'

            return jsonify({
                'success': True,
                'status': status,
                'message': message,
                'data_count': len(latest_data) if latest_data else 0
            })

        except Exception as e:
            logger.error(f"Error in /api/monitoring/status: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/screener/run', methods=['POST'])
    def api_run_screener():
        """API endpoint to manually trigger screener."""
        try:
            import numpy as np

            # Get date from request or use today (handle empty body)
            data = request.get_json(silent=True) or {}
            target_date_str = data.get('date')

            if target_date_str:
                target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
            else:
                target_date = date.today()

            logger.info(f"Manual screener trigger for {target_date}")

            # Run screener
            screener = Screener()
            watchlist = screener.run_and_save(target_date)

            # Convert numpy/pandas types to native Python types for JSON serialization
            def convert_to_serializable(obj):
                """Convert numpy/pandas types to native Python types."""
                if isinstance(obj, (np.integer, np.floating)):
                    return float(obj)
                elif isinstance(obj, np.bool_):
                    return bool(obj)
                elif isinstance(obj, dict):
                    return {k: convert_to_serializable(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_to_serializable(item) for item in obj]
                else:
                    return obj

            # Clean watchlist data
            watchlist_clean = convert_to_serializable(watchlist)

            return jsonify({
                'success': True,
                'date': target_date.strftime('%Y-%m-%d'),
                'stocks_found': len(watchlist),
                'watchlist': watchlist_clean
            })

        except Exception as e:
            logger.error(f"Error in /api/screener/run: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/signals/<int:signal_id>/execute', methods=['POST'])
    def api_execute_signal(signal_id):
        """API endpoint to mark signal as executed (placeholder for Phase 4)."""
        try:
            # Placeholder - will be implemented in Phase 4
            return jsonify({
                'success': True,
                'message': 'Signal execution tracking not yet implemented (Phase 4)'
            })

        except Exception as e:
            logger.error(f"Error in /api/signals/execute: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/monitoring/live')
    def api_monitoring_live():
        """API endpoint to get latest intraday data."""
        try:
            from src.utils.database import get_latest_intraday_data

            date_param = request.args.get('date', date.today().strftime('%Y-%m-%d'))
            data = get_latest_intraday_data(date_param)

            return jsonify({
                'success': True,
                'date': date_param,
                'count': len(data),
                'data': data
            })

        except Exception as e:
            logger.error(f"Error in /api/monitoring/live: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/monitoring/ticker/<ticker>')
    def api_monitoring_ticker(ticker):
        """API endpoint to get intraday data for a specific ticker."""
        try:
            from src.utils.database import get_intraday_data

            date_param = request.args.get('date', date.today().strftime('%Y-%m-%d'))
            data = get_intraday_data(ticker, date_param)

            return jsonify({
                'success': True,
                'ticker': ticker,
                'date': date_param,
                'count': len(data),
                'data': data
            })

        except Exception as e:
            logger.error(f"Error in /api/monitoring/ticker: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    logger.info("Routes registered successfully")
