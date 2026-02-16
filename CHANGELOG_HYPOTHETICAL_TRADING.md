# Changelog: Hypothetical Trading System

**Date:** February 13, 2026
**Feature:** Automatic paper trading with performance tracking

---

## Summary

Implemented a complete hypothetical trading system that automatically:
1. Creates paper trades when entry signals are detected
2. Closes all positions at end of trading day (17:00 CET)
3. Tracks performance metrics (win rate, average return, best/worst trades)
4. Displays results in new History page

---

## New Features

### 1. Hypothetical Trade Tracking

**Entry Logic:**
- When first signal detected for a ticker (9:20-10:00 CET)
- Creates hypothetical trade with entry price and time
- Status: 'open'
- Subsequent signals for same ticker ignored (first signal only)

**Exit Logic:**
- At 17:00 CET daily (scheduled task)
- Fetches current market price for each open position
- Calculates P&L percentage
- Updates status to 'closed'

**Benefits:**
- Validate strategy performance without risk
- Track win rate and average returns
- Identify best/worst performing setups
- Build confidence before live trading

### 2. History Page

**Location:** http://localhost:5000/history

**Features:**
- Daily statistics for selected date
- Overall statistics (all time)
- Trade history table with status, entry/exit prices, P&L%
- Color-coded metrics (green=profit, red=loss, yellow=open)

**Metrics Displayed:**
- Total Trades
- Closed/Open Trades
- Profitable/Losing Trades
- Average Return %
- Win Rate %
- Best/Worst Trade %

### 3. Automatic Scheduling

**New Task: 17:00 CET**
- Close all open hypothetical trades
- Fetch exit prices from yfinance
- Calculate and store P&L percentages
- Log results

**Updated Schedule:**
- 08:30 CET: Morning screener
- 17:00 CET: Close hypothetical trades ⭐ NEW
- 17:30 CET: Daily cleanup

---

## Files Created

### New Files

1. **HYPOTHETICAL_TRADING.md**
   - Complete documentation for hypothetical trading system
   - Usage instructions
   - Performance metrics explanations
   - Troubleshooting guide

2. **CHANGELOG_HYPOTHETICAL_TRADING.md** (this file)
   - Summary of changes
   - Implementation details

### Modified Files

#### Database Layer

1. **src/utils/database.py**
   - Added `hypothetical_trades` table schema
   - Added indexes for performance
   - Added functions:
     - `create_hypothetical_trade()` - Create new paper trade
     - `has_hypothetical_trade_today()` - Check if trade exists
     - `close_hypothetical_trade()` - Close with exit price
     - `get_open_hypothetical_trades()` - Get all open positions
     - `get_hypothetical_trades()` - Get trade history
     - `get_hypothetical_stats()` - Calculate performance metrics

#### Monitoring System

2. **src/monitoring/live_monitor.py**
   - Updated `check_signals()` method
   - After saving signal, checks if hypothetical trade exists
   - Creates hypothetical trade if this is first signal for ticker today
   - Logs trade creation

#### Scheduler

3. **src/utils/scheduler.py**
   - Added `_close_hypothetical_trades()` method
   - Scheduled at 17:00 CET
   - Fetches open trades, gets current prices, closes positions
   - Added `close_trades_now()` for manual triggering

#### Web UI

4. **src/ui/routes.py**
   - Updated `/history` route
   - Fetches hypothetical trades for date
   - Calculates daily and overall statistics
   - Passes data to template

5. **src/ui/templates/history.html**
   - Complete redesign from placeholder
   - Statistics dashboard (daily + overall)
   - Trade history table with status badges
   - Color-coded P&L displays
   - Responsive grid layout

#### Documentation

6. **DAILY_AUTOMATION.md**
   - Added 17:00 close trades task to overview
   - Added section explaining trade closure process
   - Updated all automatic task lists
   - Updated summary section

---

## Database Schema Changes

### New Table: hypothetical_trades

```sql
CREATE TABLE hypothetical_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    signal_id INTEGER,
    entry_time TIMESTAMP NOT NULL,
    entry_price REAL NOT NULL,
    exit_time TIMESTAMP,
    exit_price REAL,
    pnl_percent REAL,
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (signal_id) REFERENCES signals(id),
    UNIQUE(ticker, date)
);
```

**Indexes:**
```sql
CREATE INDEX idx_hypothetical_date ON hypothetical_trades(date);
CREATE INDEX idx_hypothetical_ticker_date ON hypothetical_trades(ticker, date);
```

**Key Constraints:**
- `UNIQUE(ticker, date)`: Ensures only one trade per ticker per day
- `status`: 'open' or 'closed'
- `signal_id`: Links to original signal that triggered trade

---

## Implementation Details

### Trade Creation Flow

```
1. Live monitoring detects signal (9:20-10:00)
   ↓
2. Signal saved to signals table
   ↓
3. Check: Has hypothetical trade for this ticker today?
   ↓
   YES → Skip (log: already exists)
   NO → Continue
   ↓
4. Create hypothetical trade:
   - ticker: from signal
   - entry_time: signal_time
   - entry_price: signal entry_price
   - date: today
   - status: 'open'
   ↓
5. Log: "✓ Hypothetical trade created for TICKER (ID: X)"
```

### Trade Closure Flow

```
1. Scheduler triggers at 17:00 CET
   ↓
2. Query: Get all open trades for today
   ↓
3. For each open trade:
   ↓
4. Fetch current price from yfinance
   ↓
5. Calculate P&L: ((exit - entry) / entry) × 100
   ↓
6. Update trade:
   - exit_time: now
   - exit_price: current price
   - pnl_percent: calculated P&L
   - status: 'closed'
   ↓
7. Log: "✓ Closed TICKER: Entry X → Exit Y (+Z%)"
```

### Statistics Calculation

**Win Rate:**
```python
win_rate = (profitable_trades / closed_trades) × 100
```

**Average Return:**
```python
avg_return = SUM(pnl_percent) / closed_trades
```

Calculated separately for:
- Daily (trades for specific date)
- Overall (all trades ever)

---

## Testing Checklist

### ✅ Database
- [x] New table created successfully
- [x] Indexes created
- [x] UNIQUE constraint works (prevents duplicate trades)
- [x] Functions work correctly

### ✅ Trade Creation
- [x] First signal creates hypothetical trade
- [x] Subsequent signals for same ticker ignored
- [x] Entry price and time recorded correctly
- [x] Status set to 'open'

### ✅ Trade Closure
- [x] Scheduler triggers at 17:00 CET
- [x] Exit prices fetched from yfinance
- [x] P&L calculated correctly
- [x] Status updated to 'closed'

### ✅ History Page
- [x] Daily statistics display correctly
- [x] Overall statistics display correctly
- [x] Trade table shows all trades
- [x] Color coding works (green/red/yellow)
- [x] Status badges display correctly

### ✅ Documentation
- [x] HYPOTHETICAL_TRADING.md created
- [x] DAILY_AUTOMATION.md updated
- [x] All automatic tasks documented

---

## User Instructions

### To Start Using

1. **Start system with scheduler:**
   ```bash
   python scripts/run_with_scheduler.py
   ```

2. **Wait for signal detection:**
   - System monitors watchlist during 9:20-10:00
   - First signal per ticker creates hypothetical trade
   - Trade visible immediately on History page as "OPEN"

3. **View results at end of day:**
   - At 17:00, all positions close automatically
   - Visit http://localhost:5000/history
   - Review daily and overall statistics

### Manual Operations

**View today's open trades:**
```bash
python -c "
from src.utils.database import get_open_hypothetical_trades
from datetime import date
trades = get_open_hypothetical_trades(date.today())
print(f'Open: {len(trades)} trades')
"
```

**Close trades manually (testing):**
```bash
python -c "
from src.utils.scheduler import DailyScheduler
scheduler = DailyScheduler()
scheduler.close_trades_now()
"
```

**View statistics:**
```bash
python -c "
from src.utils.database import get_hypothetical_stats
import pprint
stats = get_hypothetical_stats()
pprint.pprint(stats)
"
```

---

## Known Limitations

### Data Quality

**yfinance Delays:**
- Entry signals: ~15+ min delay (9:20-10:00 window helps mitigate)
- Exit prices: May be stale (last trade before 17:00)
- Gaps: Possible missing data on volatile days

**Impact:**
- Hypothetical P&L is approximate
- Real execution prices may differ by ±0.5-2%
- Use for trend validation, not precise profit projection

### Exit Timing

**17:00 CET Close:**
- Stockholm exchange closes at 17:30
- 17:00 exit gives 30-minute buffer
- Actual trading may hold until different times

**Consideration:**
- Real trades might benefit from intraday exits
- Hypothetical system forces end-of-day exit
- May miss optimal exit opportunities

### First Signal Only

**One Trade Per Day:**
- Only first signal creates trade
- Subsequent signals ignored

**Reasoning:**
- Prevents overtrading in simulation
- Models conservative approach
- Matches realistic position sizing limits

---

## Future Enhancements

### Potential Improvements

1. **Multiple Position Sizes**
   - Track different position sizes
   - Compare performance by size

2. **Stop-Loss Simulation**
   - Add stop-loss triggers
   - Track if stopped out vs. held to close

3. **Exit Strategy Variations**
   - Test different exit times (10:30, 15:00, 17:00)
   - Compare holding period performance

4. **Export to CSV**
   - Bulk export all trades
   - Advanced analysis in Excel/Python

5. **Real-Time Data Integration**
   - Upgrade to Nasdaq Nordic API
   - Improve entry/exit accuracy to >98%

6. **Performance Charts**
   - Equity curve visualization
   - Win rate over time
   - Drawdown analysis

---

## Rollback Instructions

If you need to disable hypothetical trading:

### Temporary Disable

```bash
# Run without scheduler
python scripts/run_with_scheduler.py --no-scheduler
```

Signals still detected, but no hypothetical trades created.

### Permanent Removal

```bash
# 1. Drop table
sqlite3 data/trades.db "DROP TABLE hypothetical_trades;"

# 2. Revert live_monitor.py
git checkout src/monitoring/live_monitor.py

# 3. Revert scheduler.py
git checkout src/utils/scheduler.py

# 4. Revert routes.py
git checkout src/ui/routes.py

# 5. Revert history.html
git checkout src/ui/templates/history.html
```

---

## Summary

**What Changed:**
- ✅ Database: New table + 6 new functions
- ✅ Monitoring: Auto-create trades on first signal
- ✅ Scheduler: Auto-close trades at 17:00
- ✅ UI: Complete History page with statistics
- ✅ Documentation: 2 new guides

**What Improved:**
- ✅ Strategy validation without risk
- ✅ Performance metrics tracking
- ✅ Win rate and average return calculation
- ✅ Historical analysis capability

**What's Next:**
- Paper trade for 20+ days
- Analyze win rate and returns
- Validate strategy has edge
- Decide on live trading

---

*Hypothetical trading system implemented: February 13, 2026*
*Status: Ready for testing*
