# Quick Start Guide - Production Strategy

**Current Configuration:** Earnings Surprise Filter ✅ | Trailing Stop ❌

---

## Running Backtests

### Quick Test (Recommended Settings)
```bash
source venv/bin/activate
python scripts/compare_focused.py
```

This runs the validated configuration on 28 high-quality stocks (2024 data).

### Custom Backtest
```python
from src.backtesting.backtest_engine import BacktestEngine

# Create engine with production configuration
engine = BacktestEngine(
    use_earnings_surprise_filter=True,  # ✅ Keep this
    use_trailing_stop=False              # ❌ Keep this disabled
)

# Run backtest
results = engine.run_backtest(
    tickers=['BRAV.ST', 'VOLV-B.ST', 'ERIC-B.ST'],
    start_date='2024-01-01',
    end_date='2024-12-31',
    verbose=True
)

# View results
print(f"Trades: {results['trades_executed']}")
print(f"Win Rate: {results['win_rate']:.1f}%")
print(f"Total P&L: {results['total_pnl']:.2f} SEK")
print(f"Profit Factor: {results['profit_factor']:.2f}")
```

---

## Key Performance Metrics (2024 Backtest)

**With Earnings Surprise Filter:**
- ✅ **11 trades** (high quality, selective)
- ✅ **54.5% win rate**
- ✅ **+49.98 SEK profit**
- ✅ **4.89 profit factor** (excellent)
- ✅ **4.54 SEK average trade**

**Comparison to Baseline:**
- 📉 54% fewer trades (11 vs 24)
- 📈 +6.7% more profit
- 📈 +133% larger average win
- 📈 +94% better profit factor

---

## Understanding the Strategy

### What It Does:
1. **Pre-market:** Filters stocks by momentum (3M + 1Y + SMA200)
2. **Post-earnings:** ✅ **Only trades positive earnings surprises**
3. **Intraday (9:20-10:00):** Detects entry signals
   - Price > VWAP
   - Price > Open
   - Price > Yesterday Close + 2%
   - Price > 5-minute average (no falling knife)
4. **Exit:** Fixed -2.5% stop loss OR end of day

### Why Earnings Surprise Filter Works:
- Companies that beat earnings estimates tend to continue momentum intraday
- Filters out disappointing earnings that lack follow-through
- Reduces noise, increases signal quality
- 92.8% data availability (yfinance provides estimate + reported EPS)

### Why Trailing Stop Is Disabled:
- Backtest showed it cut profits by 66%
- Earnings day volatility triggers trailing stops too early
- Fixed -2.5% stop provides sufficient protection
- Better to let winners run to end of day

---

## File Structure

```
Tradeit/
├── src/
│   ├── backtesting/
│   │   ├── strategy_simulator.py    # Core strategy logic
│   │   ├── backtest_engine.py       # Runs backtests
│   │   ├── historical_data.py       # Earnings date detection
│   │   └── metrics.py               # Performance calculations
│   └── screening/
│       └── momentum_filter.py       # Pre-market filter
│
├── scripts/
│   ├── compare_focused.py           # Quick comparison (28 stocks)
│   └── run_backtest.py              # Custom backtests
│
├── data/
│   └── all_tickers.txt              # 544 Swedish stocks
│
└── docs/
    ├── STRATEGY_CONFIGURATION.md    # Production config (this one)
    ├── EARNINGS_SURPRISE_ANALYSIS.md # Data availability study
    ├── IMPROVEMENTS_SUMMARY.md       # Implementation details
    └── TRADE_ANALYSIS.md             # Original backtest analysis
```

---

## Example: Single Trade Simulation

```python
from src.backtesting.strategy_simulator import StrategySimulator

# Create simulator with production config
simulator = StrategySimulator(
    use_earnings_surprise_filter=True,
    use_trailing_stop=False
)

# Test a specific trade
trade = simulator.simulate_trade('BRAV.ST', '2024-07-12')

print(f"Passed filter: {trade.passed_filter}")
print(f"Earnings surprise: {trade.passed_earnings_surprise}")
print(f"  Estimate: {trade.eps_estimate}")
print(f"  Reported: {trade.reported_eps}")
print(f"Signal detected: {trade.signal_detected}")
print(f"P&L: {trade.pnl} SEK ({trade.pnl_pct:.1f}%)")
```

**Example Output:**
```
Passed filter: True
Earnings surprise: False
  Estimate: 1.24
  Reported: 1.16
Signal detected: True
P&L: 5.5 SEK (6.5%)
```

Note: BRAV.ST missed estimates slightly but still generated +5.5 SEK. With the filter enabled, this trade would be skipped.

---

## Checking Earnings Surprise Data

```python
from src.backtesting.strategy_simulator import StrategySimulator

simulator = StrategySimulator(use_earnings_surprise_filter=True)

# Check if earnings beat estimates
result = simulator._check_earnings_surprise('VOLV-B.ST', '2024-01-25')

if result['passed']:
    print(f"✓ TRADE: Beat estimate by {result['surprise_pct']:.1f}%")
    print(f"  Estimate: {result['eps_estimate']}")
    print(f"  Reported: {result['reported_eps']}")
else:
    print(f"✗ SKIP: {result['reason']}")
```

---

## Next Steps

### 1. Validate Configuration
```bash
# Run the focused comparison to verify results
python scripts/compare_focused.py
```

Expected output: ~11 trades, 54.5% win rate, 4.89 profit factor

### 2. Paper Trade (Recommended)

**Before risking real capital, validate the strategy with paper trading:**

```bash
# Step 1: Run the pre-market screener (daily at 08:00 or manually)
python scripts/run_screener.py

# Step 2: Start paper trading monitor (runs 09:00-14:30)
python scripts/run_paper_trading.py

# Step 3: Review signals and log outcomes (end of day)
python scripts/paper_trading_dashboard.py
```

**Paper Trading Workflow:**
1. **Morning (08:00)**: Run screener to identify stocks reporting earnings today
2. **Intraday (09:20-14:00)**: Monitor automatically detects signals and logs them
3. **End of Day (17:00)**: Use dashboard to log trade outcomes
4. **Weekly**: Review performance vs backtest expectations

**Minimum Paper Trading Period**: 20 trading days or 10 completed trades (whichever comes first)

**Success Criteria to Go Live:**
- Win rate within 10% of backtest (target: 45-65%)
- Profit factor >2.0
- No major execution issues
- Comfortable with system reliability

### 3. Go Live (After Paper Trading)
- Start with 0.5% risk per trade (500 SEK on 100k account)
- Scale to 1% after 10 successful trades
- Monitor monthly performance
- Adjust if win rate drops below 45%

---

## Common Issues & Solutions

### Issue: "No trades executing"
**Check:**
1. Are stocks passing momentum filter? (Check Score > 60)
2. Are earnings beating estimates? (Check reported > estimate)
3. Is signal window correct? (09:20-14:00 CET)

### Issue: "Data not available"
**Solution:**
- yfinance has 92.8% coverage for earnings data
- Some stocks lack estimates or reported EPS
- These are automatically skipped (logged as "Missing EPS data")

### Issue: "Different results than documented"
**Possible Causes:**
1. yfinance data updates (new earnings data added)
2. Different time period tested
3. Different stock universe
4. Trailing stop accidentally enabled

**Verify Configuration:**
```python
# Check your engine settings
engine = BacktestEngine(
    use_earnings_surprise_filter=True,  # Should be True
    use_trailing_stop=False              # Should be False
)
print(f"Earnings filter: {engine.use_earnings_surprise_filter}")
print(f"Trailing stop: {engine.use_trailing_stop}")
```

---

## Performance Monitoring

Track these metrics monthly:

| Metric | Target | Red Flag |
|--------|--------|----------|
| **Win Rate** | 50-60% | <45% |
| **Profit Factor** | >2.5 | <1.5 |
| **Avg Win/Loss Ratio** | >2.0 | <1.5 |
| **Trades/Month** | 1-2 | 0 (no signals) |

**If Red Flags Appear:**
1. Review recent losing trades
2. Check if earnings surprise data quality changed
3. Verify momentum filter is working correctly
4. Consider expanding stock universe

---

## Support & Documentation

**Full Documentation:**
- `STRATEGY_CONFIGURATION.md` - Complete strategy rules
- `EARNINGS_SURPRISE_ANALYSIS.md` - Data availability study
- `TRADE_ANALYSIS.md` - Original 544-stock backtest

**Backtest Results:**
- `/tmp/focused_backtest_results.txt` - Latest 28-stock run
- Results show all 4 configurations tested

**Questions?**
- Review backtest logs for detailed trade-by-trade analysis
- Check individual trade simulations to debug issues
- Refer to STRATEGY_CONFIGURATION.md for decision rationale

---

*Last updated: February 13, 2026*
*Configuration: Earnings Surprise Filter ✅ | Trailing Stop ❌*
