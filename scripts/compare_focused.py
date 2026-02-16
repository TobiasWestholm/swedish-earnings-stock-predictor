"""Focused strategy comparison on high-quality stocks (2024 only)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.backtesting.backtest_engine import BacktestEngine
from src.utils.logger import setup_logger

# Setup logging
setup_logger()

# Select high-quality Swedish stocks with good data coverage
# Mix of previous winners + large/mid caps
focused_tickers = [
    # Previous star performers
    'BRAV.ST', 'VPLAY-B.ST', 'HANZA.ST', 'SKIS-B.ST', 'OVZON.ST',
    'VICO.ST', 'BIOA-B.ST', 'CATE.ST',

    # Large caps (reliable data)
    'VOLV-B.ST', 'ERIC-B.ST', 'HM-B.ST', 'SEB-A.ST', 'SWED-A.ST',

    # Mid caps with frequent earnings
    'NIBE-B.ST', 'SINCH.ST', 'KAMBI.ST', 'AMBEA.ST', 'NCAB.ST',

    # Tech/industrial (momentum candidates)
    'GARO.ST', 'VBG-B.ST', 'ALLIGO-B.ST', 'MEKO.ST', 'PREC.ST',

    # Additional diverse sectors
    'DIOS.ST', 'SYNSAM.ST', 'BORG.ST', 'SALT-B.ST', 'RUSTA.ST'
]

print(f"\n{'='*100}")
print(f"FOCUSED BACKTEST COMPARISON")
print(f"{'='*100}")
print(f"Stocks: {len(focused_tickers)} high-quality Swedish companies")
print(f"Period: 2024-01-01 to 2024-12-31 (1 year)")
print(f"Goal: Compare strategy improvements on reliable data")
print(f"{'='*100}\n")

# Define test period (2024 only for reliable data)
start_date = '2024-01-01'
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

for i, config in enumerate(configurations, 1):
    print(f"\n[{i}/4] Testing: {config['name']}")
    print("-" * 100)

    engine = BacktestEngine(
        use_earnings_surprise_filter=config['use_earnings_surprise_filter'],
        use_trailing_stop=config['use_trailing_stop']
    )

    result = engine.run_backtest(
        tickers=focused_tickers,
        start_date=start_date,
        end_date=end_date,
        verbose=False
    )

    results.append({
        'name': config['name'],
        'result': result
    })

    # Print summary for this configuration
    metrics = result  # run_backtest returns metrics directly
    summary = result.get('backtest_summary', {})

    print(f"\n{'='*100}")
    print(f"RESULTS: {config['name']}")
    print(f"{'='*100}")
    print(f"Earnings days found:  {summary.get('earnings_days_found', 0)}")
    print(f"Passed filter:        {metrics.get('passed_filter', 0)}")
    print(f"Signals detected:     {metrics.get('signal_detected', 0)}")
    print(f"Trades executed:      {metrics.get('trades_executed', 0)}")
    print(f"")
    print(f"Win rate:             {metrics.get('win_rate', 0):.1f}%")
    print(f"Total P&L:            {metrics.get('total_pnl', 0):.2f} SEK")
    print(f"Average P&L:          {metrics.get('avg_pnl', 0):.2f} SEK")
    print(f"Profit factor:        {metrics.get('profit_factor', 0):.2f}")

    if metrics.get('trades_executed', 0) > 0:
        print(f"")
        print(f"Average win:          {metrics.get('avg_win', 0):.2f} SEK")
        print(f"Average loss:         {metrics.get('avg_loss', 0):.2f} SEK")
        print(f"Largest win:          {metrics.get('largest_win', 0):.2f} SEK")
        print(f"Largest loss:         {metrics.get('largest_loss', 0):.2f} SEK")
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
    metrics = r['result']  # result IS metrics

    pf = metrics.get('profit_factor', 0)
    pf_str = f"{pf:14.2f}" if pf != float('inf') else "             ∞"

    print(f"{name:<35} "
          f"{metrics.get('trades_executed', 0):>8} "
          f"{metrics.get('win_rate', 0):>9.1f}% "
          f"{metrics.get('total_pnl', 0):>11.2f} "
          f"{metrics.get('avg_pnl', 0):>9.2f} "
          f"{pf_str}")

print("\n" + "="*100)
print("ANALYSIS & RECOMMENDATION")
print("="*100)
print()

# Find best performer
if results:
    # Rank by multiple criteria
    best_win_rate = max(results, key=lambda x: x['result'].get('win_rate', 0))
    best_pnl = max(results, key=lambda x: x['result'].get('total_pnl', 0))
    best_pf = max(results, key=lambda x: x['result'].get('profit_factor', 0))

    print("Best Win Rate:     ", best_win_rate['name'])
    print("Best Total P&L:    ", best_pnl['name'])
    print("Best Profit Factor:", best_pf['name'])
    print()

    # Overall recommendation
    baseline_metrics = results[0]['result']
    best_metrics = best_pnl['result']

    if best_metrics.get('trades_executed', 0) > 0:
        improvement_pnl = best_metrics.get('total_pnl', 0) - baseline_metrics.get('total_pnl', 0)
        improvement_wr = best_metrics.get('win_rate', 0) - baseline_metrics.get('win_rate', 0)

        print("="*100)
        print("RECOMMENDATION:")
        print("="*100)
        print()

        if improvement_pnl > 0 or improvement_wr > 5:
            print(f"✓ USE: {best_pnl['name']}")
            print()
            print(f"  Improvements over baseline:")
            print(f"  • P&L improvement: {improvement_pnl:+.2f} SEK")
            print(f"  • Win rate improvement: {improvement_wr:+.1f}%")
            print(f"  • Profit factor: {best_metrics.get('profit_factor', 0):.2f}")
        else:
            print("✓ STICK WITH BASELINE")
            print()
            print("  The improvements did not significantly outperform the baseline.")
            print("  Focus on execution quality rather than additional filters.")
    else:
        print("⚠  INSUFFICIENT DATA")
        print()
        print("  Not enough trades to make a reliable recommendation.")
        print("  Consider expanding the test period or stock universe.")

print()
print("="*100)
