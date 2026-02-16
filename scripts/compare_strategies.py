"""Compare different strategy variations."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.backtesting.backtest_engine import BacktestEngine
from src.utils.logger import setup_logger

# Setup logging
setup_logger()

# Load tickers
with open('data/all_tickers.txt', 'r') as f:
    tickers = [line.strip() for line in f if line.strip()]

print(f"Loaded {len(tickers)} tickers from all_tickers.txt")

# Define test period
start_date = '2023-01-01'
end_date = '2024-12-31'

# Run 4 different configurations
configurations = [
    {
        'name': 'Baseline (Original Strategy)',
        'use_earnings_surprise_filter': False,
        'use_trailing_stop': False
    },
    {
        'name': 'Earnings Surprise Filter Only',
        'use_earnings_surprise_filter': True,
        'use_trailing_stop': False
    },
    {
        'name': 'Trailing Stop Only',
        'use_earnings_surprise_filter': False,
        'use_trailing_stop': True
    },
    {
        'name': 'Both Improvements',
        'use_earnings_surprise_filter': True,
        'use_trailing_stop': True
    }
]

results = []

for config in configurations:
    print("\n" + "="*100)
    print(f"TESTING: {config['name']}")
    print("="*100)

    engine = BacktestEngine(
        use_earnings_surprise_filter=config['use_earnings_surprise_filter'],
        use_trailing_stop=config['use_trailing_stop']
    )

    result = engine.run_backtest(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        verbose=False  # Suppress detailed output for comparison
    )

    results.append({
        'name': config['name'],
        'result': result
    })

    # Print summary for this configuration
    metrics = result.get('metrics', {})
    print(f"\n{'='*100}")
    print(f"RESULTS: {config['name']}")
    print(f"{'='*100}")
    print(f"Total Trades:     {metrics.get('trades_executed', 0)}")
    print(f"Win Rate:         {metrics.get('win_rate', 0):.1f}%")
    print(f"Total P&L:        {metrics.get('total_pnl', 0):.2f} SEK")
    print(f"Average Trade:    {metrics.get('avg_pnl', 0):.2f} SEK")
    print(f"Profit Factor:    {metrics.get('profit_factor', 0):.2f}")
    print()

# Final comparison table
print("\n" + "="*100)
print("STRATEGY COMPARISON SUMMARY")
print("="*100)
print()
print(f"{'Strategy':<35} {'Trades':>8} {'Win Rate':>10} {'Total P&L':>12} {'Avg P&L':>10} {'Profit Factor':>15}")
print("-"*100)

for r in results:
    name = r['name']
    metrics = r['result'].get('metrics', {})

    print(f"{name:<35} "
          f"{metrics.get('trades_executed', 0):>8} "
          f"{metrics.get('win_rate', 0):>9.1f}% "
          f"{metrics.get('total_pnl', 0):>11.2f} "
          f"{metrics.get('avg_pnl', 0):>9.2f} "
          f"{metrics.get('profit_factor', 0):>14.2f}")

print("\n" + "="*100)
print("INTERPRETATION")
print("="*100)
print()
print("Win Rate:        Higher is better (target >50%)")
print("Total P&L:       Cumulative profit/loss over test period")
print("Avg P&L:         Expected value per trade (expectancy)")
print("Profit Factor:   Gross profit / Gross loss (target >1.5)")
print()
print("RECOMMENDATION: Choose the strategy with the best combination of:")
print("  1. Win rate >50%")
print("  2. Positive total P&L")
print("  3. Profit factor >1.5")
print()
