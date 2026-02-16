"""Main backtesting engine for strategy validation."""

import logging
from typing import List, Dict, Any
from datetime import datetime

from src.backtesting.historical_data import EarningsDayDetector
from src.backtesting.strategy_simulator import StrategySimulator, Trade
from src.backtesting.metrics import MetricsCalculator
from src.data.yfinance_provider import YFinanceProvider

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Main engine for running backtests across multiple stocks and time periods.

    Workflow:
    1. Scan tickers for earnings-like days
    2. Simulate trades for each earnings day
    3. Calculate performance metrics
    4. Generate report
    """

    def __init__(self, data_provider: YFinanceProvider = None,
                 use_earnings_surprise_filter: bool = False,
                 use_trailing_stop: bool = False):
        """
        Initialize backtest engine.

        Args:
            data_provider: Data provider instance
            use_earnings_surprise_filter: If True, only trade when reported EPS beats estimate
            use_trailing_stop: If True, use trailing stop (breakeven at +2%, trail -2% at +5%)
        """
        self.data_provider = data_provider or YFinanceProvider()
        self.earnings_detector = EarningsDayDetector(data_provider=self.data_provider)
        self.strategy_simulator = StrategySimulator(
            data_provider=self.data_provider,
            use_earnings_surprise_filter=use_earnings_surprise_filter,
            use_trailing_stop=use_trailing_stop
        )
        self.metrics_calculator = MetricsCalculator()
        self.use_earnings_surprise_filter = use_earnings_surprise_filter
        self.use_trailing_stop = use_trailing_stop

    def run_backtest(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Run complete backtest across multiple tickers and time period.

        Args:
            tickers: List of ticker symbols (e.g., ['VOLV-B.ST', 'ERIC-B.ST'])
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            verbose: Print progress messages

        Returns:
            Dictionary with backtest results
        """
        if verbose:
            print("\n" + "=" * 80)
            print(f"BACKTEST: {len(tickers)} tickers from {start_date} to {end_date}")
            print("=" * 80)
            print(f"Earnings Surprise Filter: {'ENABLED' if self.use_earnings_surprise_filter else 'DISABLED'}")
            print(f"Trailing Stop:            {'ENABLED' if self.use_trailing_stop else 'DISABLED'}")
            print("=" * 80 + "\n")

        all_trades = []
        earnings_days_found = 0

        # Step 1: Scan each ticker for earnings-like days
        for i, ticker in enumerate(tickers, 1):
            if verbose:
                print(f"[{i}/{len(tickers)}] Scanning {ticker}...")

            try:
                # Find earnings-like days
                earnings_days = self.earnings_detector.scan_period(
                    ticker=ticker,
                    start_date=start_date,
                    end_date=end_date
                )

                earnings_days_found += len(earnings_days)

                if verbose and earnings_days:
                    print(f"  → Found {len(earnings_days)} earnings-like days")

                # Step 2: Simulate trade for each earnings day
                for earnings_day in earnings_days:
                    date = earnings_day['date']

                    trade = self.strategy_simulator.simulate_trade(ticker, date)
                    all_trades.append(trade)

                    if verbose and trade.signal_detected:
                        status = "✓ WIN" if (trade.pnl and trade.pnl > 0) else "✗ LOSS"
                        pnl_str = f"{trade.pnl:.2f} SEK" if trade.pnl else "N/A"
                        print(f"    {date}: {status} - P&L: {pnl_str}")

            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")
                if verbose:
                    print(f"  ✗ Error: {str(e)}")

        # Step 3: Calculate metrics
        if verbose:
            print("\n" + "-" * 80)
            print("Calculating metrics...")
            print("-" * 80 + "\n")

        metrics = self.metrics_calculator.calculate_metrics(all_trades)

        # Add summary info
        metrics['backtest_summary'] = {
            'tickers_tested': len(tickers),
            'start_date': start_date,
            'end_date': end_date,
            'earnings_days_found': earnings_days_found,
            'total_trades_analyzed': len(all_trades),
            'run_time': datetime.now().isoformat()
        }

        # Step 4: Print summary
        if verbose:
            self.metrics_calculator.print_summary(metrics)
            self._print_backtest_summary(metrics)

        return metrics

    def run_single_ticker(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Run backtest for a single ticker.

        Args:
            ticker: Ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            verbose: Print progress messages

        Returns:
            Dictionary with backtest results
        """
        return self.run_backtest([ticker], start_date, end_date, verbose)

    def _print_backtest_summary(self, metrics: Dict[str, Any]):
        """Print additional backtest-specific summary."""
        summary = metrics['backtest_summary']

        print("\n" + "=" * 80)
        print("BACKTEST CONFIGURATION")
        print("=" * 80)
        print(f"Tickers tested: {summary['tickers_tested']}")
        print(f"Date range: {summary['start_date']} to {summary['end_date']}")
        print(f"Earnings-like days found: {summary['earnings_days_found']}")
        print(f"Total events analyzed: {summary['total_trades_analyzed']}")
        print(f"Run completed: {summary['run_time']}")
        print("=" * 80 + "\n")

        # Strategy assessment
        self._print_strategy_assessment(metrics)

    def _print_strategy_assessment(self, metrics: Dict[str, Any]):
        """Print assessment of strategy viability."""
        print("\n" + "=" * 80)
        print("STRATEGY ASSESSMENT")
        print("=" * 80 + "\n")

        trades_executed = metrics['trades_executed']
        win_rate = metrics['win_rate']
        profit_factor = metrics['profit_factor']
        expectancy = metrics['expectancy']

        # Assess if strategy has edge
        if trades_executed == 0:
            print("⚠️  NO TRADES EXECUTED")
            print("   - No signals met entry conditions during backtest period")
            print("   - Strategy may be too restrictive or market conditions unfavorable")
        elif trades_executed < 20:
            print("⚠️  INSUFFICIENT SAMPLE SIZE")
            print(f"   - Only {trades_executed} trades executed")
            print("   - Recommend testing longer period or more tickers (target: 50+ trades)")
        else:
            # Assess performance
            print(f"Sample size: {trades_executed} trades ✓")
            print()

            # Win rate assessment
            if win_rate >= 55:
                print(f"✓ Win rate: {win_rate:.1f}% (Good - above 55% target)")
            elif win_rate >= 50:
                print(f"~ Win rate: {win_rate:.1f}% (Acceptable - above breakeven)")
            else:
                print(f"✗ Win rate: {win_rate:.1f}% (Poor - below 50%)")

            # Profit factor assessment
            if profit_factor >= 1.5:
                print(f"✓ Profit factor: {profit_factor:.2f} (Good - above 1.5 target)")
            elif profit_factor >= 1.2:
                print(f"~ Profit factor: {profit_factor:.2f} (Acceptable - above 1.2)")
            elif profit_factor > 1.0:
                print(f"~ Profit factor: {profit_factor:.2f} (Marginal - barely profitable)")
            else:
                print(f"✗ Profit factor: {profit_factor:.2f} (Unprofitable)")

            # Expectancy assessment
            if expectancy > 0:
                print(f"✓ Expectancy: {expectancy:.2f} SEK per trade (Positive)")
            else:
                print(f"✗ Expectancy: {expectancy:.2f} SEK per trade (Negative)")

            print()

            # Overall verdict
            if win_rate >= 50 and profit_factor >= 1.2 and expectancy > 0:
                print("🎯 VERDICT: Strategy shows POSITIVE EDGE")
                print("   - Consider paper trading to validate in real-time conditions")
                print("   - Monitor data quality (yfinance limitations)")
            elif win_rate >= 45 and profit_factor >= 1.0:
                print("⚠️  VERDICT: Strategy shows MARGINAL EDGE")
                print("   - Edge exists but may be too small after costs (spreads, slippage)")
                print("   - Consider optimizing entry/exit rules or focusing on higher quality setups")
            else:
                print("❌ VERDICT: Strategy shows NO EDGE")
                print("   - Win rate or profit factor too low")
                print("   - Do NOT proceed to live trading")
                print("   - Consider revising strategy logic")

        print("=" * 80 + "\n")
