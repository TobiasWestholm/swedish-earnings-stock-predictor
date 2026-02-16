"""Performance metrics calculation for backtesting."""

import logging
from typing import List, Dict, Any
from src.backtesting.strategy_simulator import Trade

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """Calculates performance metrics from backtest trades."""

    def calculate_metrics(self, trades: List[Trade]) -> Dict[str, Any]:
        """
        Calculate comprehensive performance metrics.

        Args:
            trades: List of Trade objects

        Returns:
            Dictionary with all metrics
        """
        if not trades:
            return self._empty_metrics()

        # Separate trades by stage
        filtered_trades = [t for t in trades if t.passed_filter]
        signal_trades = [t for t in trades if t.signal_detected]
        executed_trades = [t for t in trades if t.signal_detected and t.pnl is not None]

        # Win/loss analysis
        winning_trades = [t for t in executed_trades if t.pnl > 0]
        losing_trades = [t for t in executed_trades if t.pnl <= 0]

        # Calculate metrics
        metrics = {
            # Overview
            'total_events_tested': len(trades),
            'passed_filter': len(filtered_trades),
            'signal_detected': len(signal_trades),
            'trades_executed': len(executed_trades),

            # Filter performance
            'filter_pass_rate': (len(filtered_trades) / len(trades) * 100) if trades else 0,
            'signal_rate': (len(signal_trades) / len(filtered_trades) * 100) if filtered_trades else 0,

            # Trade statistics
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': (len(winning_trades) / len(executed_trades) * 100) if executed_trades else 0,

            # Profitability
            'total_pnl': sum(t.pnl for t in executed_trades),
            'avg_pnl': sum(t.pnl for t in executed_trades) / len(executed_trades) if executed_trades else 0,
            'avg_win': sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else 0,
            'avg_loss': sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0,
            'largest_win': max((t.pnl for t in winning_trades), default=0),
            'largest_loss': min((t.pnl for t in losing_trades), default=0),

            # Percentage returns
            'avg_return_pct': sum(t.pnl_pct for t in executed_trades) / len(executed_trades) if executed_trades else 0,
            'avg_win_pct': sum(t.pnl_pct for t in winning_trades) / len(winning_trades) if winning_trades else 0,
            'avg_loss_pct': sum(t.pnl_pct for t in losing_trades) / len(losing_trades) if losing_trades else 0,

            # Risk metrics
            'profit_factor': self._calculate_profit_factor(executed_trades),
            'expectancy': sum(t.pnl for t in executed_trades) / len(executed_trades) if executed_trades else 0,

            # Exit analysis
            'exits_eod': len([t for t in executed_trades if t.exit_reason == 'end_of_day']),
            'exits_stop_loss': len([t for t in executed_trades if t.exit_reason == 'stop_loss']),

            # Trade list
            'trades': [t.to_dict() for t in executed_trades]
        }

        return metrics

    def _calculate_profit_factor(self, trades: List[Trade]) -> float:
        """
        Calculate profit factor (total wins / total losses).

        Args:
            trades: List of executed trades

        Returns:
            Profit factor
        """
        if not trades:
            return 0.0

        total_wins = sum(t.pnl for t in trades if t.pnl > 0)
        total_losses = abs(sum(t.pnl for t in trades if t.pnl <= 0))

        if total_losses == 0:
            return float('inf') if total_wins > 0 else 0.0

        return total_wins / total_losses

    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure."""
        return {
            'total_events_tested': 0,
            'passed_filter': 0,
            'signal_detected': 0,
            'trades_executed': 0,
            'filter_pass_rate': 0,
            'signal_rate': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'avg_pnl': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'largest_win': 0,
            'largest_loss': 0,
            'avg_return_pct': 0,
            'avg_win_pct': 0,
            'avg_loss_pct': 0,
            'profit_factor': 0,
            'expectancy': 0,
            'exits_eod': 0,
            'exits_stop_loss': 0,
            'trades': []
        }

    def print_summary(self, metrics: Dict[str, Any]):
        """Print formatted metrics summary."""
        print("\n" + "=" * 80)
        print("BACKTEST SUMMARY")
        print("=" * 80)

        print(f"\nOVERVIEW")
        print(f"Total events tested: {metrics['total_events_tested']}")
        print(f"Passed filter: {metrics['passed_filter']} ({metrics['filter_pass_rate']:.1f}%)")
        print(f"Signals detected: {metrics['signal_detected']} ({metrics['signal_rate']:.1f}% of filtered)")
        print(f"Trades executed: {metrics['trades_executed']}")

        if metrics['trades_executed'] > 0:
            print(f"\nTRADE STATISTICS")
            print(f"Winning trades: {metrics['winning_trades']}")
            print(f"Losing trades: {metrics['losing_trades']}")
            print(f"Win rate: {metrics['win_rate']:.1f}%")

            print(f"\nPROFITABILITY")
            print(f"Total P&L: {metrics['total_pnl']:.2f} SEK")
            print(f"Average P&L: {metrics['avg_pnl']:.2f} SEK ({metrics['avg_return_pct']:.2f}%)")
            print(f"Average win: {metrics['avg_win']:.2f} SEK ({metrics['avg_win_pct']:.2f}%)")
            print(f"Average loss: {metrics['avg_loss']:.2f} SEK ({metrics['avg_loss_pct']:.2f}%)")
            print(f"Largest win: {metrics['largest_win']:.2f} SEK")
            print(f"Largest loss: {metrics['largest_loss']:.2f} SEK")

            print(f"\nRISK METRICS")
            pf = metrics['profit_factor']
            pf_str = f"{pf:.2f}" if pf != float('inf') else "∞"
            print(f"Profit factor: {pf_str}")
            print(f"Expectancy: {metrics['expectancy']:.2f} SEK per trade")

            print(f"\nEXIT ANALYSIS")
            print(f"End of day exits: {metrics['exits_eod']}")
            print(f"Stop loss hits: {metrics['exits_stop_loss']}")

        print("=" * 80 + "\n")
