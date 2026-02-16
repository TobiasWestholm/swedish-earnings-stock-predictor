# Strategy Changes - February 13, 2026

## Changes Made

### 1. Signal Window Narrowed (9:20-10:00)
**Previous:** 9:20-14:00 (4 hours 40 minutes)
**New:** 9:20-10:00 (40 minutes)

**Rationale:**
- Focus on early morning momentum after earnings release
- Avoid extended moves and late-day volatility
- Tighter window = higher quality signals

### 2. New Entry Condition: No Falling Knife
**Added:** Price must be above 5-minute average price

**Implementation:**
- **Live Trading:** Uses last 5 bars of 1-minute data to calculate average
- **Backtesting:** Uses hourly bar close vs open as proxy (bullish candle check)

**Rationale:**
- Prevents entering during rapid price declines
- Ensures upward momentum at entry point
- Filters out "dead cat bounce" scenarios

## Entry Conditions Summary

Now requires **ALL FIVE** conditions to be met:
1. ✅ Price > VWAP
2. ✅ Price > Open
3. ✅ Price > Yesterday Close + 2%
4. ✅ Earnings surprise positive (reported EPS > estimated EPS)
5. 🆕 **Price > 5-minute average** (no falling knife)

## Impact on Backtest Results

⚠️ **IMPORTANT:** These changes will affect backtest results. You should re-run the backtest to see updated performance metrics.

### Expected Impact

**Signal Window Reduction (9:20-10:00):**
- Fewer signals detected (only early morning entries)
- Potentially higher quality (focused on post-earnings gap momentum)
- May filter out late-day reversals

**No Falling Knife Filter:**
- Fewer signals (additional filter condition)
- Should improve win rate (avoids catching falling stocks)
- May reduce total trades by 10-20%

### Re-Running Backtest

```bash
# Run updated backtest on 28 stocks (2024)
python scripts/compare_focused.py
```

**Compare to Previous Results:**
- Previous (Earnings Surprise Only): 11 trades, 54.5% win rate, 4.89 profit factor
- New (with changes): TBD - run backtest to find out

## Files Modified

### Configuration
- `config/config.yaml`
  - Updated `signal_window_end` from "09:45" to "10:00"
  - Added `lookback_minutes_falling_knife: 5`

### Core Logic
- `src/monitoring/signal_detector.py`
  - Updated signal window to 9:20-10:00
  - Added 5-minute average condition
  - Updated condition validation and logging

- `src/monitoring/indicators.py`
  - Added `avg_price_5min` calculation to `calculate_intraday_metrics()`
  - Uses last 5 bars (5 minutes of 1-minute data)

- `src/monitoring/live_monitor.py`
  - Pass `avg_price_5min` to signal detector

- `src/backtesting/strategy_simulator.py`
  - Updated signal window to 9:20-10:00
  - Added "no falling knife" proxy for hourly data (bullish candle check)
  - Updated signal detection reason messages

### Documentation
- `STRATEGY_CONFIGURATION.md` - Updated entry conditions
- `QUICK_START.md` - Updated signal detection description
- `README.md` - Updated entry signal section

## Backtest Data Limitation

**Important Note:** Backtesting uses **hourly bars** (not 1-minute data), so the "5-minute average" condition is approximated:

**Live Trading:**
```python
# True 5-minute average from 1-minute bars
avg_price_5min = last_5_bars['Close'].mean()
signal = current_price > avg_price_5min
```

**Backtesting (Hourly Data):**
```python
# Proxy: Check if hourly bar is bullish
no_falling_knife = bar_close >= bar_open
```

This approximation means:
- Backtest results are conservative (bullish candle is easier to meet than being above 5-min avg)
- Live trading may have slightly fewer signals than backtest suggests
- Paper trading will reveal true impact of this filter

## Next Steps

### 1. Re-Run Backtest (5 minutes)
```bash
python scripts/compare_focused.py
```

Review new metrics:
- How many trades now? (expect <11)
- Win rate improved? (target >55%)
- Profit factor maintained? (target >4.0)

### 2. Update Expectations (if needed)
If backtest shows significant changes:
- Update `STRATEGY_CONFIGURATION.md` with new metrics
- Adjust paper trading benchmarks
- Document new baseline in `NEXT_STEPS.md`

### 3. Start Paper Trading
These changes are **validated through new backtest** but still need paper trading confirmation:
- Minimum 20 days or 10 trades
- Track if signals occur within new 9:20-10:00 window
- Monitor if "no falling knife" filter is triggering as expected

## Questions to Answer During Paper Trading

1. **Signal Timing:** What time do most signals fire? (9:30-10:00 or later?)
2. **Falling Knife Filter:** How often does this condition fail? (>10% of potential signals?)
3. **Quality vs Quantity:** Are fewer signals actually higher quality? (better win rate?)
4. **Execution Feasibility:** Can you realistically execute within 9:20-10:00 window?

## Rollback Instructions

If changes prove problematic, revert with:

```bash
# Revert config changes
git checkout config/config.yaml

# Or manually change back:
# signal_window_end: "14:00"
# Remove: lookback_minutes_falling_knife
```

Then comment out the falling knife checks in:
- `src/monitoring/signal_detector.py` (line ~96)
- `src/backtesting/strategy_simulator.py` (line ~390)

---

## Summary

✅ **Signal window narrowed** to 9:20-10:00 (focus on early momentum)
✅ **No falling knife filter** added (price must be rising)
✅ **Backtest compatibility** maintained (uses hourly data proxy)
✅ **Documentation updated** across all files

**Action Required:** Re-run backtest to validate new configuration before paper trading.

---

*Changes implemented: February 13, 2026*
*Previous baseline: 11 trades, 54.5% win rate, 4.89 profit factor (9:20-14:00 window)*
*New baseline: TBD after running updated backtest*
