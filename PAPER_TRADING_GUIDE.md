# Paper Trading Guide

**Last Updated:** February 13, 2026
**Purpose:** Validate the strategy in real-time before risking capital

---

## Why Paper Trade?

Paper trading allows you to:
1. **Validate backtest results** hold up in real market conditions
2. **Test your execution** speed and discipline
3. **Identify data quality issues** before they cost money
4. **Build confidence** in the system and strategy
5. **Practice the workflow** without financial risk

**⚠️ CRITICAL:** Do NOT skip paper trading. Backtest results are based on historical data and may not reflect current market conditions, data quality, or your execution ability.

---

## Paper Trading Workflow

### Daily Routine

#### Morning (08:00 CET)
**1. Run Pre-Market Screener**
```bash
python scripts/run_screener.py
```

This identifies stocks reporting earnings today that pass the momentum filter.

**Expected Output:**
- 0-5 stocks per day (most days will have 0-1)
- Each stock shows momentum score, SMA200 status, 3M/1Y returns

**Action:**
- Review the watchlist
- Check earnings calendar to confirm report times (typically 07:30-08:30)
- Note which stocks you'll monitor

#### Intraday (09:00-14:30 CET)
**2. Start Paper Trading Monitor**
```bash
python scripts/run_paper_trading.py
```

This automatically:
- Monitors all watchlist stocks
- Calculates VWAP in real-time
- Detects entry signals (09:20-14:00)
- Checks earnings surprise filter
- Logs all signals to database

**What You'll See:**
```
🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔
SIGNAL DETECTED: VOLV-B.ST @ 245.50 SEK
================================================================================
Signal ID:         42
Time:              2026-02-13T09:37:15+01:00
Entry Price:       245.50 SEK
VWAP:              244.20 SEK (+0.5%)
Open:              243.80 SEK (+0.7%)
Yesterday Close:   240.00 SEK (+2.3%)
Confidence:        78%
Data Age:          35 seconds

✅ EARNINGS SURPRISE: PASSED
  Estimate:  8.45
  Reported:  9.12
  Surprise:  +7.9%

💼 RISK MANAGEMENT (1% of 100k account):
  Entry:          245.50 SEK
  Stop Loss:      239.37 SEK (-2.5%)
  Position Size:  163 shares
  Capital:        40,016 SEK
  Risk:           999 SEK

================================================================================
📝 Signal logged to paper trading tracker (ID: 42)
Use paper_trading_dashboard.py to:
  - Mark as executed if you take the trade
  - Mark as skipped if you don't trade
  - Log outcome at end of day
🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔
```

**Your Decision:**
- **Execute**: Open Avanza, enter order manually (or paper trade mentally)
- **Skip**: Note reason (data stale, uncomfortable with signal, etc.)

**Execution Tips:**
- Open Avanza app/web immediately when signal fires
- Use limit order slightly above current price to ensure fill
- Expect 15-45 second delay from signal to execution
- If price moved significantly (>1%), consider skipping

#### End of Day (17:00+ CET)
**3. Review and Log Outcomes**
```bash
python scripts/paper_trading_dashboard.py
```

**Dashboard Menu:**
```
================================================================================
PAPER TRADING DASHBOARD
================================================================================

1. View today's signals
2. View pending outcomes (need to log results)
3. Log trade outcome
4. Mark signal as executed
5. Mark signal as skipped
6. View summary (all time)
7. View summary (last 7 days)
8. View summary (last 30 days)
9. Compare to backtest expectations
10. Export signals to CSV
0. Exit
```

**Steps:**
1. Select option **2** to see pending outcomes
2. For each signal, select option **3** to log outcome:
   - If you executed: Enter exit price, time, reason
   - If you skipped: Select option **5** and enter reason
3. Select option **6** to view overall summary
4. Select option **9** to compare vs backtest

---

## Logging Signal Outcomes

### If You Executed the Trade

**Example:**
```
Select option (0-10): 3

Enter signal ID: 42

📝 Logging outcome for VOLV-B.ST (Entry: 245.50 SEK)
Exit price (SEK): 248.20
Exit time (HH:MM): 17:25
Exit reason:
1. Stop loss
2. End of day
3. Manual exit
4. Other
Select (1-4): 2
Notes (optional): Held until close, good momentum all day

✅ Outcome logged: +2.70 SEK (+1.1%)
```

### If You Skipped the Signal

**Example:**
```
Select option (0-10): 5

Enter signal ID: 42
Reason for skipping:
1. Data too stale
2. Risk limit reached
3. Market conditions
4. Other
Select (1-4): 1
✅ Signal 42 marked as skipped: Data too stale
```

**Common Skip Reasons:**
- Data age >90 seconds (delayed data reduces edge)
- Already in 3 positions today (risk management)
- Market volatility too high
- Uncomfortable with signal quality
- Price moved too much before you could execute

---

## Performance Tracking

### Weekly Review (Every Friday)

Run option **7** (last 7 days summary):
```
================================================================================
PAPER TRADING SUMMARY
================================================================================

Period: 2026-02-10 to 2026-02-13

📊 SIGNALS
  Total signals detected:  8
  Executed:                6 (75.0%)
  Skipped:                 2

💼 TRADES
  Completed trades:        6
  Pending outcomes:        0
  Wins:                    4
  Losses:                  2
  Breakeven:               0
  Win rate:                66.7%

📈 PERFORMANCE
  Total P&L:               +18.50 SEK
  Average P&L:             +3.08 SEK
  Average win:             +5.75 SEK
  Average loss:            -2.38 SEK
  Largest win:             +8.20 SEK
  Largest loss:            -2.50 SEK
  Profit factor:           4.84
  Avg confidence:          74%

================================================================================
```

### Monthly Comparison (Compare vs Backtest)

Run option **9** after 10+ trades:
```
================================================================================
BACKTEST VS PAPER TRADING COMPARISON
================================================================================

📊 WIN RATE
  Backtest:        54.5%
  Paper Trading:   66.7%
  Variance:        +12.2%

💰 AVERAGE P&L
  Backtest:        4.54 SEK
  Paper Trading:   3.08 SEK
  Variance:        -1.46 SEK

📈 PROFIT FACTOR
  Backtest:        4.89
  Paper Trading:   4.84

📝 ASSESSMENT
  ✅ ALIGNED: Paper trading results are consistent with backtest expectations

================================================================================
```

---

## Success Criteria

### Minimum Paper Trading Duration

Complete **BOTH** of these:
1. **Time**: 20 trading days (4 weeks)
2. **Trades**: 10 completed trades

**Why Both?**
- Time: Ensures you experience different market conditions
- Trades: Provides statistical significance for performance metrics

**If Only 5 Trades After 4 Weeks:**
- This is normal (strategy is selective)
- Continue paper trading for another 2-4 weeks
- Consider expanding stock universe (more earnings reports = more opportunities)

### Performance Benchmarks

You're ready for live trading if:

| Metric | Backtest | Acceptable Range | Red Flag |
|--------|----------|------------------|----------|
| **Win Rate** | 54.5% | 45-65% | <40% or >70% |
| **Avg P&L** | 4.54 SEK | 2.0-7.0 SEK | <1.0 SEK |
| **Profit Factor** | 4.89 | >2.0 | <1.5 |
| **Data Quality** | N/A | >70% fresh data (<90s) | <50% fresh |

**Red Flag Interpretations:**
- **Win rate <40%**: Strategy not working, investigate why
- **Win rate >70%**: Lucky streak or small sample size, keep paper trading
- **Avg P&L <1.0 SEK**: Execution problems or data delays eating edge
- **Profit Factor <1.5**: Risk/reward imbalanced, review stop-loss execution

### Qualitative Criteria

Answer these questions:
1. ✅ Do you understand when to execute and when to skip?
2. ✅ Can you execute within 30-60 seconds of signal?
3. ✅ Are you comfortable with the 2.5% stop-loss?
4. ✅ Have you experienced at least 3 losing trades without panic?
5. ✅ Do you trust the system won't generate false signals?

If any answer is "No", continue paper trading until you're comfortable.

---

## Common Issues & Solutions

### Issue 1: "No signals detected after 1 week"

**Possible Causes:**
- No companies reported earnings (check calendar)
- Companies failed momentum filter (check watchlist)
- Companies failed earnings surprise filter (check logs)
- Signal conditions not met intraday (check VWAP data)

**Solutions:**
- Expand stock universe (add more tickers to `data/all_tickers.txt`)
- Verify screener is running daily
- Check yfinance data availability

### Issue 2: "Win rate much lower than backtest (30-40%)"

**Possible Causes:**
- Execution delay causing worse entry prices
- Data staleness (signals firing on 2+ minute old data)
- Market regime change (2024 data vs current conditions)
- Slippage not accounted for in backtest

**Solutions:**
- Only execute signals with data age <60 seconds
- Use limit orders to control entry price
- Track actual entry vs signal entry price
- May need to adjust expectations if market changed

### Issue 3: "Profit factor lower than backtest (1.5-2.5)"

**Possible Causes:**
- Stop-losses hit more frequently than backtest
- Winners not running as far
- Execution slippage on entries and exits

**Solutions:**
- Review stop-loss hit rate vs backtest
- Verify end-of-day exit prices match signal day closes
- Consider if hourly backtest data smoothed intraday volatility

### Issue 4: "Data too stale (>90 seconds) on most signals"

**Possible Causes:**
- yfinance delays on volatile days
- Network/API issues
- Small-cap stocks have less frequent updates

**Solutions:**
- Skip signals with data age >90 seconds
- Consider upgrading to real-time data provider
- Focus on large-cap stocks (better data quality)

---

## Transitioning to Live Trading

### After Meeting Success Criteria

**Phase 1: Micro Positions (Week 1-2)**
- Start with **0.5% risk** per trade (500 SEK on 100k account)
- Execute only highest-confidence signals (>75%)
- Track every detail: entry time, slippage, execution errors

**Phase 2: Standard Positions (Week 3-4)**
- Increase to **1% risk** per trade (1,000 SEK)
- Execute all qualifying signals
- Continue tracking performance vs paper trading

**Phase 3: Full Operation (Month 2+)**
- Maintain 1% risk per trade
- Review performance monthly
- Adjust if metrics deviate >15% from expectations

### Risk Management Rules (Live Trading)

**Position Limits:**
- Max 1% risk per trade
- Max 3 positions per day
- Max 3% daily loss limit (stop trading for the day)

**Stop-Loss Discipline:**
- Set stop-loss immediately after entry (-2.5%)
- Never move stop-loss further away
- Never "hope" a trade will recover
- Cut losses quickly, let winners run

**Performance Reviews:**
- Daily: Log all trades, review execution quality
- Weekly: Calculate win rate, profit factor, avg P&L
- Monthly: Compare to backtest, adjust if needed

---

## Record Keeping Best Practices

### Daily Trade Log (Manual Supplement)

Keep a simple spreadsheet with additional notes:

| Date | Ticker | Signal ID | Executed? | Entry Notes | Exit Notes | Emotion |
|------|--------|-----------|-----------|-------------|------------|---------|
| 2026-02-12 | VOLV-B.ST | 42 | Yes | Smooth execution, 20s delay | Held to close, profit | Confident |
| 2026-02-13 | ERIC-B.ST | 43 | No | Data too stale (140s) | - | Frustrated |
| 2026-02-13 | HM-B.ST | 44 | Yes | Fast execution, good entry | Stop-loss hit | Disappointed |

**Why This Helps:**
- Identify patterns in execution (time of day, ticker size)
- Track emotional state (are you making good decisions?)
- Document lessons learned
- Reference for future improvements

### Weekly Review Checklist

Every Friday, review:
- [ ] Total signals this week
- [ ] Execution rate (% of signals traded)
- [ ] Win rate vs backtest
- [ ] Avg P&L vs backtest
- [ ] Data quality issues
- [ ] Execution problems (slippage, delays)
- [ ] Emotional state (confident, anxious, impulsive?)
- [ ] Lessons learned

---

## FAQ

### Q: How long should I paper trade?
**A:** Minimum 20 trading days AND 10 completed trades. If signals are rare, continue until you have 10 trades.

### Q: What if I can't execute within 30 seconds?
**A:** Skip the signal. Delayed execution reduces your edge. Practice to improve speed or accept you'll skip more signals.

### Q: Should I paper trade hypothetically or actually click buttons?
**A:** Practice the full execution workflow (open broker, find ticker, enter order) to simulate real conditions. Stop short of submitting the order.

### Q: What if my win rate is higher than backtest?
**A:** Could be luck. Continue paper trading to get more data. Don't go live until you have 20+ trades.

### Q: Can I paper trade on historical data instead?
**A:** No. Paper trading tests execution speed, data quality, and your decision-making in real-time. Historical backtests can't replicate these factors.

### Q: What if a signal fires but I'm not at my computer?
**A:** Log it as "skipped - unavailable". This reveals if your availability aligns with signal times (09:20-14:00).

### Q: Should I paper trade every signal or only high-confidence ones?
**A:** Trade all signals that meet criteria. This gives you realistic performance data. You can filter by confidence later if needed.

---

## Export and Analysis

### Export Data for Excel/Python Analysis

```bash
python scripts/paper_trading_dashboard.py
# Select option 10 (Export to CSV)
```

This creates a CSV with all signals, outcomes, and metadata for custom analysis in Excel, Python pandas, or other tools.

---

## Next Steps After Successful Paper Trading

1. ✅ **Document your results** (win rate, profit factor, lessons learned)
2. ✅ **Review STRATEGY_CONFIGURATION.md** one more time
3. ✅ **Set up live trading account** with appropriate capital (100k SEK)
4. ✅ **Start with micro positions** (0.5% risk = 500 SEK)
5. ✅ **Track live vs paper performance** for first 2 weeks
6. ✅ **Scale to full positions** (1% risk) after 10 successful live trades

---

**Remember:** Paper trading is NOT about making hypothetical profits. It's about validating the strategy works in real market conditions with real execution constraints. Take it seriously, log everything accurately, and use it to build confidence before risking capital.

---

*For questions or issues, refer to QUICK_START.md or STRATEGY_CONFIGURATION.md.*
