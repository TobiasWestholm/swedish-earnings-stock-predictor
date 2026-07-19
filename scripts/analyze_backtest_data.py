#!/usr/bin/env python3
"""
Macro analysis script for backtest data.

This script performs various analyses on exported backtest CSV data to identify
trends, patterns, and insights.

Usage:
    python scripts/analyze_backtest_data.py backtest_results.csv

Analyses performed:
    1. Time-based analysis (monthly, quarterly performance)
    2. Ticker-based analysis (which stocks perform best)
    3. Filter score correlation (do higher scores = better returns?)
    4. Win/loss distribution
    5. Entry/exit timing analysis
"""

import sys
import pandas as pd
import argparse
from pathlib import Path
from datetime import datetime


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Analyze backtest CSV data for trends and patterns',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        'csv_file',
        type=str,
        help='Path to backtest CSV file'
    )

    parser.add_argument(
        '--output',
        type=str,
        help='Optional output file for detailed analysis'
    )

    return parser.parse_args()


def load_data(csv_file: str) -> pd.DataFrame:
    """Load and prepare backtest data."""
    df = pd.read_csv(csv_file)

    # Convert date columns
    df['date'] = pd.to_datetime(df['date'])
    df['entry_time'] = pd.to_datetime(df['entry_time'], errors='coerce')
    df['exit_time'] = pd.to_datetime(df['exit_time'], errors='coerce')

    # Add derived columns
    df['year'] = df['date'].dt.year
    df['month'] = df['date'].dt.month
    df['quarter'] = df['date'].dt.quarter
    df['year_quarter'] = df['year'].astype(str) + '-Q' + df['quarter'].astype(str)
    df['month_name'] = df['date'].dt.strftime('%Y-%m')

    # Win/loss classification
    df['is_winner'] = df['pnl'] > 0
    df['is_loser'] = df['pnl'] < 0

    return df


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def overall_summary(df: pd.DataFrame):
    """Print overall summary statistics."""
    print_section("OVERALL SUMMARY")

    total_trades = len(df)
    signaled_trades = len(df[df['signal_detected'] == True])
    executed_trades = len(df[df['pnl'].notna()])

    print(f"Total events tested: {total_trades}")
    print(f"Passed filter: {len(df[df['passed_filter'] == True])} ({len(df[df['passed_filter'] == True])/total_trades*100:.1f}%)")
    print(f"Signals detected: {signaled_trades} ({signaled_trades/len(df[df['passed_filter'] == True])*100:.1f}% of filtered)" if len(df[df['passed_filter'] == True]) > 0 else "")
    print(f"Trades executed: {executed_trades}")

    if executed_trades > 0:
        winning = len(df[df['is_winner'] == True])
        losing = len(df[df['is_loser'] == True])
        win_rate = winning / executed_trades * 100

        print(f"\nWin Rate: {win_rate:.1f}% ({winning}W / {losing}L)")
        print(f"Average P&L: {df['pnl_pct'].mean():.2f}%")
        print(f"Average Win: {df[df['is_winner'] == True]['pnl_pct'].mean():.2f}%")
        print(f"Average Loss: {df[df['is_loser'] == True]['pnl_pct'].mean():.2f}%")
        print(f"Best Trade: {df['pnl_pct'].max():.2f}%")
        print(f"Worst Trade: {df['pnl_pct'].min():.2f}%")


def time_based_analysis(df: pd.DataFrame):
    """Analyze performance over time."""
    print_section("TIME-BASED ANALYSIS")

    executed = df[df['pnl'].notna()]

    if len(executed) == 0:
        print("No executed trades to analyze")
        return

    # Monthly performance
    print("\n--- Monthly Performance ---")
    monthly = executed.groupby('month_name').agg({
        'pnl': ['count', 'sum', 'mean'],
        'pnl_pct': 'mean',
        'is_winner': 'sum'
    }).round(2)
    monthly.columns = ['Trades', 'Total P&L (SEK)', 'Avg P&L (SEK)', 'Avg P&L %', 'Winners']
    monthly['Win Rate %'] = (monthly['Winners'] / monthly['Trades'] * 100).round(1)
    print(monthly.to_string())

    # Quarterly performance
    print("\n--- Quarterly Performance ---")
    quarterly = executed.groupby('year_quarter').agg({
        'pnl': ['count', 'sum', 'mean'],
        'pnl_pct': 'mean',
        'is_winner': 'sum'
    }).round(2)
    quarterly.columns = ['Trades', 'Total P&L (SEK)', 'Avg P&L (SEK)', 'Avg P&L %', 'Winners']
    quarterly['Win Rate %'] = (quarterly['Winners'] / quarterly['Trades'] * 100).round(1)
    print(quarterly.to_string())


def ticker_analysis(df: pd.DataFrame):
    """Analyze performance by ticker."""
    print_section("TICKER ANALYSIS")

    executed = df[df['pnl'].notna()]

    if len(executed) == 0:
        print("No executed trades to analyze")
        return

    ticker_perf = executed.groupby('ticker').agg({
        'pnl': ['count', 'sum', 'mean'],
        'pnl_pct': 'mean',
        'is_winner': 'sum'
    }).round(2)
    ticker_perf.columns = ['Trades', 'Total P&L (SEK)', 'Avg P&L (SEK)', 'Avg P&L %', 'Winners']
    ticker_perf['Win Rate %'] = (ticker_perf['Winners'] / ticker_perf['Trades'] * 100).round(1)

    # Sort by total P&L
    ticker_perf = ticker_perf.sort_values('Total P&L (SEK)', ascending=False)

    print("\n--- Top 20 Performers (by Total P&L) ---")
    print(ticker_perf.head(20).to_string())

    print("\n--- Bottom 10 Performers (by Total P&L) ---")
    print(ticker_perf.tail(10).to_string())


def filter_score_analysis(df: pd.DataFrame):
    """Analyze correlation between filter score and performance."""
    print_section("FILTER SCORE CORRELATION")

    executed = df[df['pnl'].notna()]

    if len(executed) == 0:
        print("No executed trades to analyze")
        return

    # Bin filter scores
    executed['score_bin'] = pd.cut(executed['filter_score'], bins=[0, 60, 70, 80, 90, 100], labels=['50-60', '60-70', '70-80', '80-90', '90+'])

    score_analysis = executed.groupby('score_bin').agg({
        'pnl': ['count', 'mean'],
        'pnl_pct': 'mean',
        'is_winner': 'sum'
    }).round(2)
    score_analysis.columns = ['Trades', 'Avg P&L (SEK)', 'Avg P&L %', 'Winners']
    score_analysis['Win Rate %'] = (score_analysis['Winners'] / score_analysis['Trades'] * 100).round(1)

    print("\n--- Performance by Filter Score Range ---")
    print(score_analysis.to_string())

    correlation = executed['filter_score'].corr(executed['pnl_pct'])
    print(f"\nCorrelation between Filter Score and P&L %: {correlation:.3f}")
    if abs(correlation) < 0.1:
        print("  → Weak/no correlation")
    elif abs(correlation) < 0.3:
        print("  → Moderate correlation")
    else:
        print("  → Strong correlation")


def exit_reason_analysis(df: pd.DataFrame):
    """Analyze exit reasons."""
    print_section("EXIT REASON ANALYSIS")

    executed = df[df['pnl'].notna()]

    if len(executed) == 0:
        print("No executed trades to analyze")
        return

    exit_analysis = executed.groupby('exit_reason').agg({
        'pnl': ['count', 'mean'],
        'pnl_pct': 'mean',
        'is_winner': 'sum'
    }).round(2)
    exit_analysis.columns = ['Trades', 'Avg P&L (SEK)', 'Avg P&L %', 'Winners']
    exit_analysis['Win Rate %'] = (exit_analysis['Winners'] / exit_analysis['Trades'] * 100).round(1)

    print(exit_analysis.to_string())


def main():
    """Main entry point."""
    args = parse_args()

    # Check if file exists
    if not Path(args.csv_file).exists():
        print(f"Error: File '{args.csv_file}' not found")
        sys.exit(1)

    print("\n" + "=" * 80)
    print(f"MACRO ANALYSIS: {args.csv_file}")
    print("=" * 80)

    # Load data
    print("\nLoading data...")
    df = load_data(args.csv_file)
    print(f"✓ Loaded {len(df)} records")

    # Run analyses
    overall_summary(df)
    time_based_analysis(df)
    ticker_analysis(df)
    filter_score_analysis(df)
    exit_reason_analysis(df)

    # Save detailed analysis if requested
    if args.output:
        print(f"\nSaving detailed analysis to {args.output}...")
        with open(args.output, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write(f"DETAILED BACKTEST ANALYSIS: {args.csv_file}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")

            # Save summary stats
            f.write("SUMMARY STATISTICS\n")
            f.write("-" * 80 + "\n")
            f.write(df[df['pnl'].notna()].describe().to_string())
            f.write("\n\n")

        print(f"✓ Saved to {args.output}")

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80 + "\n")


if __name__ == '__main__':
    main()
