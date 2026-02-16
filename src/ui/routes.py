"""Flask routes for Svea Surveillance web UI."""

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
        """Hypothetical trade history view."""
        try:
            from src.utils.database import get_hypothetical_trades, get_hypothetical_stats

            # Get date from query param or use today
            date_param = request.args.get('date')

            if date_param:
                target_date_obj = datetime.strptime(date_param, '%Y-%m-%d').date()
                trades = get_hypothetical_trades(trade_date=target_date_obj, limit=100)
                stats = get_hypothetical_stats(trade_date=target_date_obj)
                date_filter = date_param
            else:
                # Show today's trades by default
                target_date_obj = date.today()
                trades = get_hypothetical_trades(trade_date=target_date_obj, limit=100)
                stats = get_hypothetical_stats(trade_date=target_date_obj)
                date_filter = target_date_obj.strftime('%Y-%m-%d')

            # Also get overall stats
            overall_stats = get_hypothetical_stats()

            return render_template(
                'history.html',
                trades=trades,
                stats=stats,
                overall_stats=overall_stats,
                date=date_filter
            )

        except Exception as e:
            logger.error(f"Error rendering history: {e}")
            return f"Error loading history: {str(e)}", 500

    # API Endpoints

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
