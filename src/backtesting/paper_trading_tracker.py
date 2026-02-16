"""Paper trading tracker for validating strategy before live trading."""

import sqlite3
import pandas as pd
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class PaperTradingTracker:
    """
    Tracks paper trading signals and simulated trades.

    Logs all signals detected by the system and allows manual entry
    of actual outcomes to validate strategy performance.
    """

    def __init__(self, db_path: str = 'data/paper_trades.db'):
        """
        Initialize paper trading tracker.

        Args:
            db_path: Path to SQLite database for paper trades
        """
        self.db_path = db_path
        self._init_database()
        logger.info(f"Initialized PaperTradingTracker with database: {db_path}")

    def _init_database(self):
        """Create database tables if they don't exist."""
        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Table for logged signals
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS paper_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                signal_date DATE NOT NULL,
                signal_time TIME NOT NULL,
                entry_price REAL NOT NULL,
                open_price REAL,
                vwap REAL,
                yesterday_close REAL,
                pct_from_yesterday REAL,
                vwap_distance_pct REAL,
                open_distance_pct REAL,
                confidence_score REAL,
                data_age_seconds INTEGER,

                -- Earnings data
                passed_earnings_surprise BOOLEAN,
                eps_estimate REAL,
                reported_eps REAL,
                surprise_pct REAL,

                -- Status tracking
                executed BOOLEAN DEFAULT 0,
                skipped BOOLEAN DEFAULT 0,
                skip_reason TEXT,

                -- Outcome (filled manually after EOD)
                exit_price REAL,
                exit_time TIME,
                exit_reason TEXT,
                pnl REAL,
                pnl_pct REAL,

                -- Notes
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Index for quick lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_signal_date
            ON paper_signals(signal_date)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_ticker
            ON paper_signals(ticker)
        ''')

        conn.commit()
        conn.close()

    def log_signal(self, signal: Dict[str, Any],
                   earnings_data: Optional[Dict[str, Any]] = None) -> int:
        """
        Log a signal detected by the system.

        Args:
            signal: Signal dictionary from SignalDetector
            earnings_data: Optional earnings surprise data

        Returns:
            Signal ID (for later updates)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Parse signal time
        signal_dt = datetime.fromisoformat(signal['signal_time'])

        cursor.execute('''
            INSERT INTO paper_signals (
                ticker, signal_date, signal_time, entry_price,
                open_price, vwap, yesterday_close,
                pct_from_yesterday, vwap_distance_pct, open_distance_pct,
                confidence_score, data_age_seconds,
                passed_earnings_surprise, eps_estimate, reported_eps, surprise_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            signal['ticker'],
            signal_dt.date(),
            signal_dt.time(),
            signal['entry_price'],
            signal.get('open_price'),
            signal.get('vwap'),
            signal.get('yesterday_close'),
            signal.get('pct_from_yesterday'),
            signal.get('vwap_distance_pct'),
            signal.get('open_distance_pct'),
            signal.get('confidence_score'),
            signal.get('data_age_seconds'),
            earnings_data.get('passed') if earnings_data else None,
            earnings_data.get('eps_estimate') if earnings_data else None,
            earnings_data.get('reported_eps') if earnings_data else None,
            earnings_data.get('surprise_pct') if earnings_data else None
        ))

        signal_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"Logged paper signal: {signal['ticker']} @ {signal['entry_price']:.2f} (ID: {signal_id})")
        return signal_id

    def mark_executed(self, signal_id: int, notes: str = None):
        """
        Mark a signal as executed (user actually took the trade).

        Args:
            signal_id: Signal ID from log_signal()
            notes: Optional execution notes
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE paper_signals
            SET executed = 1, notes = ?
            WHERE id = ?
        ''', (notes, signal_id))

        conn.commit()
        conn.close()
        logger.info(f"Marked signal {signal_id} as executed")

    def mark_skipped(self, signal_id: int, reason: str):
        """
        Mark a signal as skipped (user chose not to trade).

        Args:
            signal_id: Signal ID from log_signal()
            reason: Reason for skipping (e.g., "Data too stale", "Risk limit hit")
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE paper_signals
            SET skipped = 1, skip_reason = ?
            WHERE id = ?
        ''', (reason, signal_id))

        conn.commit()
        conn.close()
        logger.info(f"Marked signal {signal_id} as skipped: {reason}")

    def log_outcome(self, signal_id: int, exit_price: float,
                   exit_time: str, exit_reason: str, notes: str = None):
        """
        Log the outcome of a paper trade.

        Args:
            signal_id: Signal ID from log_signal()
            exit_price: Exit price achieved
            exit_time: Exit time (HH:MM format)
            exit_reason: Why trade closed (e.g., "stop_loss", "end_of_day")
            notes: Optional notes
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get entry price to calculate P&L
        cursor.execute('SELECT entry_price FROM paper_signals WHERE id = ?', (signal_id,))
        result = cursor.fetchone()

        if not result:
            logger.error(f"Signal {signal_id} not found")
            conn.close()
            return

        entry_price = result[0]
        pnl = exit_price - entry_price
        pnl_pct = (pnl / entry_price) * 100

        cursor.execute('''
            UPDATE paper_signals
            SET exit_price = ?, exit_time = ?, exit_reason = ?,
                pnl = ?, pnl_pct = ?, notes = COALESCE(notes || ' | ', '') || ?
            WHERE id = ?
        ''', (exit_price, exit_time, exit_reason, pnl, pnl_pct, notes or '', signal_id))

        conn.commit()
        conn.close()

        logger.info(f"Logged outcome for signal {signal_id}: {pnl:+.2f} SEK ({pnl_pct:+.1f}%)")

    def get_today_signals(self) -> List[Dict[str, Any]]:
        """Get all signals from today."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM paper_signals
            WHERE signal_date = DATE('now')
            ORDER BY signal_time DESC
        ''')

        columns = [desc[0] for desc in cursor.description]
        signals = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return signals

    def get_pending_outcomes(self) -> List[Dict[str, Any]]:
        """Get signals that are executed but don't have outcomes logged yet."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM paper_signals
            WHERE executed = 1 AND exit_price IS NULL
            ORDER BY signal_date DESC, signal_time DESC
        ''')

        columns = [desc[0] for desc in cursor.description]
        signals = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return signals

    def get_date_range_signals(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Get all signals in a date range as DataFrame.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with all signals
        """
        conn = sqlite3.connect(self.db_path)

        df = pd.read_sql_query('''
            SELECT * FROM paper_signals
            WHERE signal_date BETWEEN ? AND ?
            ORDER BY signal_date, signal_time
        ''', conn, params=(start_date, end_date))

        conn.close()
        return df

    def generate_summary_report(self, start_date: str = None,
                               end_date: str = None) -> Dict[str, Any]:
        """
        Generate performance summary for paper trading period.

        Args:
            start_date: Start date (defaults to first signal)
            end_date: End date (defaults to last signal)

        Returns:
            Dictionary with summary metrics
        """
        conn = sqlite3.connect(self.db_path)

        # Build query with optional date filter
        date_filter = ""
        params = []
        if start_date:
            date_filter += "WHERE signal_date >= ?"
            params.append(start_date)
        if end_date:
            date_filter += (" AND " if start_date else "WHERE ") + "signal_date <= ?"
            params.append(end_date)

        # Get overall stats
        query = f'''
            SELECT
                COUNT(*) as total_signals,
                SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END) as executed_count,
                SUM(CASE WHEN skipped = 1 THEN 1 ELSE 0 END) as skipped_count,
                SUM(CASE WHEN exit_price IS NOT NULL THEN 1 ELSE 0 END) as completed_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                SUM(CASE WHEN pnl = 0 THEN 1 ELSE 0 END) as breakeven_trades,
                AVG(pnl) as avg_pnl,
                SUM(pnl) as total_pnl,
                AVG(CASE WHEN pnl > 0 THEN pnl END) as avg_win,
                AVG(CASE WHEN pnl < 0 THEN pnl END) as avg_loss,
                MAX(pnl) as largest_win,
                MIN(pnl) as largest_loss,
                AVG(confidence_score) as avg_confidence
            FROM paper_signals
            {date_filter}
        '''

        cursor = conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchone()

        if not result or result[0] == 0:
            conn.close()
            return {'error': 'No signals in specified period'}

        # Unpack results
        (total_signals, executed_count, skipped_count, completed_trades,
         winning_trades, losing_trades, breakeven_trades,
         avg_pnl, total_pnl, avg_win, avg_loss, largest_win, largest_loss,
         avg_confidence) = result

        # Calculate win rate
        win_rate = (winning_trades / completed_trades * 100) if completed_trades > 0 else 0

        # Calculate profit factor
        gross_profit = cursor.execute(f'''
            SELECT SUM(pnl) FROM paper_signals
            {date_filter} {"AND" if date_filter else "WHERE"} pnl > 0
        ''', params).fetchone()[0] or 0

        gross_loss = abs(cursor.execute(f'''
            SELECT SUM(pnl) FROM paper_signals
            {date_filter} {"AND" if date_filter else "WHERE"} pnl < 0
        ''', params).fetchone()[0] or 0)

        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

        conn.close()

        return {
            'period': {
                'start_date': start_date or 'First signal',
                'end_date': end_date or 'Last signal'
            },
            'signals': {
                'total': total_signals,
                'executed': executed_count,
                'skipped': skipped_count,
                'execution_rate': (executed_count / total_signals * 100) if total_signals > 0 else 0
            },
            'trades': {
                'completed': completed_trades,
                'pending_outcomes': executed_count - completed_trades,
                'wins': winning_trades,
                'losses': losing_trades,
                'breakeven': breakeven_trades,
                'win_rate': win_rate
            },
            'performance': {
                'total_pnl': total_pnl or 0,
                'avg_pnl': avg_pnl or 0,
                'avg_win': avg_win or 0,
                'avg_loss': avg_loss or 0,
                'largest_win': largest_win or 0,
                'largest_loss': largest_loss or 0,
                'profit_factor': profit_factor,
                'avg_confidence': avg_confidence or 0
            }
        }

    def compare_to_backtest(self, backtest_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare paper trading results to backtest expectations.

        Args:
            backtest_metrics: Metrics dictionary from backtest

        Returns:
            Comparison dictionary with variances
        """
        paper_summary = self.generate_summary_report()

        if 'error' in paper_summary:
            return paper_summary

        paper_trades = paper_summary['trades']
        paper_perf = paper_summary['performance']

        return {
            'win_rate': {
                'backtest': backtest_metrics.get('win_rate', 0),
                'paper_trading': paper_trades['win_rate'],
                'variance': paper_trades['win_rate'] - backtest_metrics.get('win_rate', 0)
            },
            'avg_pnl': {
                'backtest': backtest_metrics.get('avg_pnl', 0),
                'paper_trading': paper_perf['avg_pnl'],
                'variance': paper_perf['avg_pnl'] - backtest_metrics.get('avg_pnl', 0)
            },
            'profit_factor': {
                'backtest': backtest_metrics.get('profit_factor', 0),
                'paper_trading': paper_perf['profit_factor'],
                'variance': paper_perf['profit_factor'] - backtest_metrics.get('profit_factor', 0)
            },
            'trades': {
                'backtest_trades': backtest_metrics.get('trades_executed', 0),
                'paper_trades': paper_trades['completed'],
                'note': 'Different time periods make direct comparison difficult'
            },
            'assessment': self._assess_variance(paper_summary, backtest_metrics)
        }

    def _assess_variance(self, paper_summary: Dict, backtest_metrics: Dict) -> str:
        """Generate assessment of how paper trading compares to backtest."""
        paper_wr = paper_summary['trades']['win_rate']
        backtest_wr = backtest_metrics.get('win_rate', 0)
        wr_diff = paper_wr - backtest_wr

        paper_pf = paper_summary['performance']['profit_factor']
        backtest_pf = backtest_metrics.get('profit_factor', 0)

        if paper_summary['trades']['completed'] < 5:
            return "⚠️  INSUFFICIENT DATA: Need at least 5 completed trades for meaningful comparison"

        if abs(wr_diff) <= 10 and paper_pf >= backtest_pf * 0.7:
            return "✅ ALIGNED: Paper trading results are consistent with backtest expectations"
        elif wr_diff < -15 or paper_pf < backtest_pf * 0.5:
            return "❌ UNDERPERFORMING: Paper trading significantly worse than backtest. Review strategy execution."
        elif wr_diff > 15 and paper_pf > backtest_pf * 1.3:
            return "⚠️  OVERPERFORMING: Results better than backtest (may be lucky streak, need more data)"
        else:
            return "⚙️  MONITORING: Some variance from backtest, continue paper trading to gather more data"

    def export_to_csv(self, filepath: str, start_date: str = None, end_date: str = None):
        """
        Export signals to CSV for external analysis.

        Args:
            filepath: Output CSV path
            start_date: Optional start date filter
            end_date: Optional end date filter
        """
        df = self.get_date_range_signals(
            start_date or '2000-01-01',
            end_date or '2099-12-31'
        )

        df.to_csv(filepath, index=False)
        logger.info(f"Exported {len(df)} signals to {filepath}")

    def print_summary(self, start_date: str = None, end_date: str = None):
        """Print formatted summary report to console."""
        summary = self.generate_summary_report(start_date, end_date)

        if 'error' in summary:
            print(f"\n{summary['error']}\n")
            return

        print("\n" + "="*80)
        print("PAPER TRADING SUMMARY")
        print("="*80)
        print(f"\nPeriod: {summary['period']['start_date']} to {summary['period']['end_date']}")

        print(f"\n📊 SIGNALS")
        print(f"  Total signals detected:  {summary['signals']['total']}")
        print(f"  Executed:                {summary['signals']['executed']} ({summary['signals']['execution_rate']:.1f}%)")
        print(f"  Skipped:                 {summary['signals']['skipped']}")

        print(f"\n💼 TRADES")
        print(f"  Completed trades:        {summary['trades']['completed']}")
        print(f"  Pending outcomes:        {summary['trades']['pending_outcomes']}")
        print(f"  Wins:                    {summary['trades']['wins']}")
        print(f"  Losses:                  {summary['trades']['losses']}")
        print(f"  Breakeven:               {summary['trades']['breakeven']}")
        print(f"  Win rate:                {summary['trades']['win_rate']:.1f}%")

        print(f"\n📈 PERFORMANCE")
        print(f"  Total P&L:               {summary['performance']['total_pnl']:+.2f} SEK")
        print(f"  Average P&L:             {summary['performance']['avg_pnl']:+.2f} SEK")
        print(f"  Average win:             {summary['performance']['avg_win']:+.2f} SEK")
        print(f"  Average loss:            {summary['performance']['avg_loss']:+.2f} SEK")
        print(f"  Largest win:             {summary['performance']['largest_win']:+.2f} SEK")
        print(f"  Largest loss:            {summary['performance']['largest_loss']:+.2f} SEK")

        pf = summary['performance']['profit_factor']
        pf_str = f"{pf:.2f}" if pf != float('inf') else "∞"
        print(f"  Profit factor:           {pf_str}")
        print(f"  Avg confidence:          {summary['performance']['avg_confidence']:.0%}")

        print("\n" + "="*80 + "\n")
