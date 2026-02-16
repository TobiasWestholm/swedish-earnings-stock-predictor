"""Main stock screener orchestrator."""

from datetime import date, datetime
from typing import List, Dict, Any
import logging

from src.screening.report_calendar import ReportCalendar
from src.screening.momentum_filter import MomentumFilter
from src.utils.database import save_watchlist
from src.data.yfinance_provider import YFinanceProvider

logger = logging.getLogger(__name__)


class Screener:
    """Main screener that orchestrates earnings calendar and momentum filtering."""

    def __init__(
        self,
        calendar: ReportCalendar = None,
        momentum_filter: MomentumFilter = None
    ):
        """
        Initialize screener.

        Args:
            calendar: ReportCalendar instance (optional)
            momentum_filter: MomentumFilter instance (optional)
        """
        self.calendar = calendar or ReportCalendar()
        self.momentum_filter = momentum_filter or MomentumFilter()

        logger.info("Initialized Screener")

    def run_daily_screen(self, target_date: date = None) -> List[Dict[str, Any]]:
        """
        Run the daily screening process.

        Steps:
        1. Load earnings calendar for target date
        2. Filter stocks by momentum (3M + 1Y + SMA200)
        3. Calculate quality scores
        4. Return watchlist sorted by score

        Args:
            target_date: Date to screen for (defaults to today)

        Returns:
            List of stock dictionaries sorted by trend_score (highest first)
        """
        if target_date is None:
            target_date = date.today()

        logger.info(f"=== Running Daily Screen for {target_date} ===")

        # Step 1: Get earnings reports for today
        reports = self.calendar.get_reports_for_date(target_date)

        if not reports:
            logger.warning(f"No earnings reports found for {target_date}")
            return []

        logger.info(f"Found {len(reports)} companies reporting earnings on {target_date}")

        # Extract tickers (TICKER is the primary identifier, company_name may not match yfinance)
        tickers = [report['ticker'] for report in reports]

        # Step 2: Apply momentum filter
        logger.info("Applying momentum filter (3M + 1Y + SMA200)...")
        momentum_results = self.momentum_filter.filter_stocks(tickers)

        # Step 3: Build watchlist with passing stocks
        watchlist = []

        for report in reports:
            ticker = report['ticker']
            momentum_data = momentum_results.get(ticker, {})

            # Only include stocks that pass the filter
            if momentum_data.get('passes_filter', False):
                stock_data = {
                    'ticker': ticker,
                    'name': report['company_name'],
                    'report_time': report['report_time'],
                    'trend_score': momentum_data.get('trend_score', 0),
                    'sma_200': momentum_data.get('sma_200'),
                    'current_price': momentum_data.get('current_price'),
                    'yesterday_close': momentum_data.get('yesterday_close'),
                    'return_3m': momentum_data.get('return_3m'),
                    'return_1y': momentum_data.get('return_1y'),
                    'price_above_sma200': momentum_data.get('price_above_sma200'),
                    'errors': momentum_data.get('errors', [])
                }

                watchlist.append(stock_data)
                logger.info(f"✓ {ticker}: PASSED (score={stock_data['trend_score']:.0f})")
            else:
                logger.debug(f"✗ {ticker}: Failed momentum filter")

        # Sort by trend score (highest first)
        watchlist.sort(key=lambda x: x['trend_score'], reverse=True)

        logger.info(f"=== Screen Complete: {len(watchlist)} stocks passed ===")

        if watchlist:
            logger.info("\nFinal Watchlist:")
            for i, stock in enumerate(watchlist, 1):
                logger.info(
                    f"{i}. {stock['ticker']} - Score: {stock['trend_score']:.0f}, "
                    f"3M: {stock['return_3m']:.1%}, 1Y: {stock['return_1y']:.1%}"
                )

        return watchlist

    def run_and_save(self, target_date: date = None) -> List[Dict[str, Any]]:
        """
        Run screening and save results to database.

        Args:
            target_date: Date to screen for (defaults to today)

        Returns:
            Watchlist of passing stocks
        """
        if target_date is None:
            target_date = date.today()

        # Run the screen
        watchlist = self.run_daily_screen(target_date)

        # Save to database
        if watchlist:
            date_str = target_date.strftime('%Y-%m-%d')
            saved_count = save_watchlist(watchlist, date_str)
            logger.info(f"Saved {saved_count} stocks to database")
        else:
            logger.info("No stocks to save (empty watchlist)")

        return watchlist

    def get_summary(self, watchlist: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate summary statistics for watchlist.

        Args:
            watchlist: List of stock dictionaries

        Returns:
            Summary statistics dictionary
        """
        if not watchlist:
            return {
                'total_stocks': 0,
                'avg_score': 0,
                'avg_return_3m': 0,
                'avg_return_1y': 0,
                'top_stock': None
            }

        scores = [s['trend_score'] for s in watchlist]
        returns_3m = [s['return_3m'] for s in watchlist if s['return_3m'] is not None]
        returns_1y = [s['return_1y'] for s in watchlist if s['return_1y'] is not None]

        summary = {
            'total_stocks': len(watchlist),
            'avg_score': sum(scores) / len(scores),
            'avg_return_3m': sum(returns_3m) / len(returns_3m) if returns_3m else 0,
            'avg_return_1y': sum(returns_1y) / len(returns_1y) if returns_1y else 0,
            'top_stock': watchlist[0] if watchlist else None,
            'score_range': f"{min(scores):.0f}-{max(scores):.0f}" if scores else "N/A"
        }

        return summary
