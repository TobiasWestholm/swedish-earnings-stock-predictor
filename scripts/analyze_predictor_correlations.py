#!/usr/bin/env python3
"""
Analyze correlations between predictors and earnings day returns.

Identifies which fundamental metrics have the strongest relationship
with earnings day performance to guide filter design and strategy development.
"""

import pandas as pd
import numpy as np
import sys

def main():
    print("=" * 80)
    print("PREDICTOR CORRELATION ANALYSIS")
    print("=" * 80)
    print()

    # Load enriched dataset
    df = pd.read_csv('data/enriched_earnings_dataset.csv')

    print(f"Loaded {len(df)} records with {len(df.columns)} columns")
    print()

    # Calculate correlations with earnings_day_return (numeric columns only)
    target = 'earnings_day_return'

    if target not in df.columns:
        print(f"ERROR: {target} not found in dataset")
        sys.exit(1)

    # Select only numeric columns
    numeric_df = df.select_dtypes(include=[np.number])
    print(f"Using {len(numeric_df.columns)} numeric columns for correlation analysis")
    print()

    correlations = numeric_df.corr()[target].dropna().sort_values(key=abs, ascending=False)

    # Remove the target itself
    correlations = correlations.drop(target)

    print("=" * 80)
    print("TOP 20 PREDICTORS BY ABSOLUTE CORRELATION")
    print("=" * 80)
    print()

    for i, (col, corr) in enumerate(correlations.head(20).items(), 1):
        direction = "📈 Positive" if corr > 0 else "📉 Negative"
        strength = ""
        if abs(corr) >= 0.5:
            strength = "🔥 STRONG"
        elif abs(corr) >= 0.3:
            strength = "⚡ MODERATE"
        elif abs(corr) >= 0.1:
            strength = "💡 WEAK"
        else:
            strength = "⚪ MINIMAL"

        print(f"{i:2d}. {col:40s} {corr:+.3f} {strength} {direction}")

    print()
    print("=" * 80)
    print("PREDICTOR CATEGORY BREAKDOWN")
    print("=" * 80)
    print()

    # Group by category
    categories = {
        'Historical Patterns': ['avg_abs_return', 'std_return', 'max_positive_return',
                               'max_negative_return', 'win_rate', 'directional_consistency',
                               'earnings_count'],
        '52-Week Position': ['position_in_range', 'distance_from_high_pct',
                            'distance_from_low_pct', 'weeks_since_high', 'weeks_since_low'],
        'Market Cap & Liquidity': ['market_cap_usd', 'liquidity_score', 'dollar_volume_daily',
                                   'float_percent', 'avg_volume_10d', 'avg_volume_3m'],
        'Earnings Surprise': ['eps_difference', 'surprise_percent'],
        'Volatility': ['volatility_20d', 'volatility_60d', 'volatility_252d'],
        'Volume': ['volume_avg_20d', 'volume_avg_60d', 'volume_avg_252d', 'volume_trend_ratio'],
        'Momentum': ['momentum_20d', 'momentum_60d', 'momentum_252d', 'relative_strength'],
        'Price Data': ['normalized_price', 'filter_score', 'prev_close']
    }

    for category, cols in categories.items():
        available_cols = [c for c in cols if c in correlations.index]
        if not available_cols:
            continue

        cat_corrs = correlations[available_cols].sort_values(key=abs, ascending=False)

        if len(cat_corrs) == 0:
            continue

        print(f"\n{category}:")
        print("-" * 60)
        for col, corr in cat_corrs.head(5).items():
            print(f"  {col:35s} {corr:+.3f}")

    print()
    print("=" * 80)
    print("KEY INSIGHTS FOR FILTER DESIGN")
    print("=" * 80)
    print()

    # Identify actionable filters
    print("RECOMMENDED FILTERS (based on correlation analysis):")
    print()

    # 52-week position
    pos_in_range_corr = correlations.get('position_in_range', 0)
    if abs(pos_in_range_corr) > 0.1:
        if pos_in_range_corr < 0:
            print("✓ 52-Week Position: FILTER OUT stocks >90% of range (near highs)")
            print("  Correlation suggests stocks near 52w highs have lower returns")
        else:
            print("✓ 52-Week Position: PREFER stocks >70% of range (strong momentum)")
            print("  Correlation suggests stocks near 52w highs have higher returns")
    else:
        print("⚪ 52-Week Position: NO CLEAR PATTERN (use for segmentation, not filtering)")
    print()

    # Historical patterns
    avg_abs_corr = correlations.get('avg_abs_return', 0)
    if abs(avg_abs_corr) > 0.1:
        if avg_abs_corr > 0:
            print("✓ Historical Patterns: PREFER 'high-reaction' stocks (avg_abs_return >5%)")
            print("  Stocks with historically large moves continue to have large moves")
        else:
            print("✓ Historical Patterns: PREFER 'low-reaction' stocks (avg_abs_return <3%)")
            print("  Stable stocks have better risk-adjusted returns")
    print()

    # Market cap
    mcap_corr = correlations.get('market_cap_usd', 0)
    if abs(mcap_corr) > 0.1:
        if mcap_corr > 0:
            print("✓ Market Cap: PREFER larger caps ($100M+ USD)")
            print("  Larger stocks have higher/better earnings returns")
        else:
            print("✓ Market Cap: PREFER small caps (<$50M USD)")
            print("  Small caps have higher earnings returns (but check liquidity!)")
    print()

    # Liquidity
    liq_corr = correlations.get('liquidity_score', 0)
    if abs(liq_corr) > 0.05:
        print(f"✓ Liquidity Score: Correlation {liq_corr:+.3f}")
        print("  ALWAYS filter out liquidity_score <20 (untradeable)")
    else:
        print("✓ Liquidity Score: NO CORRELATION with returns")
        print("  Use as TRADABILITY filter, not performance predictor")
    print()

    # Momentum
    mom_20d_corr = correlations.get('momentum_20d', 0)
    if abs(mom_20d_corr) > 0.1:
        if mom_20d_corr > 0:
            print(f"✓ Momentum (20d): PREFER positive momentum (>0%)")
            print(f"  Correlation {mom_20d_corr:+.3f} suggests trend continuation")
        else:
            print(f"✓ Momentum (20d): PREFER negative momentum (<0%)")
            print(f"  Correlation {mom_20d_corr:+.3f} suggests mean reversion")
    print()

    print("=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print()
    print("1. Review top correlated predictors above")
    print("2. Add filters to grid_search_earnings.py based on insights")
    print("3. Test filter combinations:")
    print("   - Baseline: liquidity_score >= 30")
    print("   - Add 52-week position filter")
    print("   - Add historical pattern filter")
    print("   - Add market cap filter")
    print("4. Compare performance with/without each filter")
    print()
    print("=" * 80)


if __name__ == '__main__':
    main()
