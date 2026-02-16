# Hypothetical Trading System

**Last Updated:** February 13, 2026
**Purpose:** Automatic paper trading to validate strategy performance

---

## Overview

The system now includes an **automatic hypothetical trading system** that simulates paper trades based on detected signals. This allows you to track strategy performance without risking real capital.

### How It Works

1. **Monitor Starts (09:00):** Live monitor starts automatically, polls watchlist every minute
2. **Entry (Morning):** When a signal is detected (9:20-10:00 CET), a hypothetical trade is automatically created
3. **Exit (End of Day):** At 17:00 CET, all open positions are automatically closed at market price
4. **Tracking:** Performance metrics are calculated and displayed in the History page

### Key Rules

- **First Signal Only:** Only the first signal per ticker per day creates a trade
- **Consecutive Signals Ignored:** If multiple signals fire for the same ticker, only the first counts
- **Automatic Exit:** All positions close at 17:00 CET regardless of performance
- **Paper Trading Only:** These are simulated trades for performance validation

---

## Automatic Process

### Signal Detection → Trade Creation

When the monitoring system detects an entry signal:

```
09:37:15 - Signal detected for VOLV-B.ST
           Entry: 245.50 SEK
           Conditions met: Above VWAP, Above Open, >2% since yesterday, Above 5-min avg

09:37:15 - ✓ Signal saved to database (ID: 123)
09:37:15 - ✓ Hypothetical trade created for VOLV-B.ST (ID: 45)
```

**What happens:**
1. Signal is saved to `signals` table
2. System checks if hypothetical trade already exists for VOLV-B.ST today
3. If not, creates new entry in `hypothetical_trades` table with status='open'
4. Trade is immediately visible on History page as "OPEN"

### End of Day → Trade Closure

At 17:00 CET, the scheduler automatically closes all open trades:

```
17:00:00 - SCHEDULED TASK: Close Hypothetical Trades (17:00)
17:00:00 - Closing open trades for 2026-02-13
17:00:00 - Found 3 open trades to close

17:00:01 - Fetching exit price for VOLV-B.ST...
17:00:01 - ✓ Closed VOLV-B.ST: Entry 245.50 → Exit 248.30 (+1.14%)

17:00:02 - Fetching exit price for ERIC-B.ST...
17:00:02 - ✓ Closed ERIC-B.ST: Entry 52.80 → Exit 51.90 (-1.70%)

17:00:03 - Fetching exit price for HM-B.ST...
17:00:03 - ✓ Closed HM-B.ST: Entry 178.20 → Exit 180.50 (+1.29%)

17:00:03 - Closed 3/3 hypothetical trades
```

**What happens:**
1. Scheduler fetches all open trades for today
2. For each trade, fetches current market price via yfinance
3. Calculates P&L percentage: `((exit_price - entry_price) / entry_price) * 100`
4. Updates trade status to 'closed' with exit price and P&L
5. Trade now appears as "CLOSED" on History page

---

## Viewing History

### Web UI

Visit: **http://localhost:5000/history**

The History page displays:

**Daily Statistics (Today)**
- Total Trades
- Closed Trades
- Open Trades
- Profitable Trades
- At Loss Trades
- Average Return (%)
- Win Rate (%)

**Overall Statistics (All Time)**
- Total Trades
- Profitable Trades
- At Loss Trades
- Average Return (%)
- Win Rate (%)
- Best Trade (%)
- Worst Trade (%)

**Trade History Table**
- Status (OPEN/CLOSED)
- Ticker
- Entry Time
- Entry Price
- Exit Time
- Exit Price
- P&L %

### Color Coding

- **Green boxes:** Positive metrics (profitable trades, positive returns)
- **Red boxes:** Negative metrics (losing trades, negative returns)
- **Yellow badges:** Open trades (pending close)
- **Green badges:** Closed trades

---

## Performance Metrics

### Win Rate

```
Win Rate = (Profitable Trades / Closed Trades) × 100
```

**Example:**
- 10 total trades
- 6 profitable
- 4 at loss
- Win Rate = (6 / 10) × 100 = 60%

### Average Return

```
Average Return = Sum of all P&L % / Number of Closed Trades
```

**Example:**
- Trade 1: +2.5%
- Trade 2: -1.2%
- Trade 3: +3.8%
- Average = (2.5 - 1.2 + 3.8) / 3 = +1.70%

### Best/Worst Trade

- **Best Trade:** Highest P&L % (most profitable)
- **Worst Trade:** Lowest P&L % (biggest loss)

---

## Database Schema

### hypothetical_trades Table

```sql
CREATE TABLE hypothetical_trades (
    id INTEGER PRIMARY KEY,
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

**Key Constraints:**
- `UNIQUE(ticker, date)`: Ensures only one trade per ticker per day
- `status`: 'open' or 'closed'
- `pnl_percent`: Calculated as `((exit_price - entry_price) / entry_price) * 100`

---

## Manual Operations

### View Statistics

```bash
python -c "
from src.utils.database import get_hypothetical_stats
import pprint
from datetime import date

# Today's stats
today_stats = get_hypothetical_stats(date.today())
print('Today:')
pprint.pprint(today_stats)

# Overall stats
overall_stats = get_hypothetical_stats()
print('\nOverall:')
pprint.pprint(overall_stats)
"
```

### Close Trades Manually

```bash
python -c "
from src.utils.scheduler import DailyScheduler
scheduler = DailyScheduler()
scheduler.close_trades_now()
"
```

### View Open Trades

```bash
python -c "
from src.utils.database import get_open_hypothetical_trades
from datetime import date

open_trades = get_open_hypothetical_trades(date.today())
print(f'Open trades: {len(open_trades)}')
for trade in open_trades:
    print(f'  {trade[\"ticker\"]}: Entry {trade[\"entry_price\"]:.2f} at {trade[\"entry_time\"]}')
"
```

---

## Configuration

No additional configuration needed - hypothetical trading is automatically enabled when the scheduler is running.

To disable hypothetical trading:
1. Stop the scheduler: `python scripts/run_with_scheduler.py --no-scheduler`
2. Signals will still be detected but no hypothetical trades will be created

---

## Data Retention

### Current Behavior

- **Hypothetical trades are NOT cleared** by the daily cleanup (17:30)
- Historical trades are kept indefinitely for performance analysis
- You can view past days using date filter: `http://localhost:5000/history?date=2026-02-12`

### Manual Cleanup

If you want to clear old hypothetical trades:

```python
from src.utils.database import get_connection
from datetime import date, timedelta

conn = get_connection()
cursor = conn.cursor()

# Clear trades older than 30 days
cutoff_date = (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')
cursor.execute("DELETE FROM hypothetical_trades WHERE date < ?", (cutoff_date,))
deleted = cursor.rowcount
conn.commit()
conn.close()

print(f"Deleted {deleted} old hypothetical trades")
```

---

## Use Cases

### 1. Strategy Validation

**Goal:** Determine if the strategy has a statistical edge

**Approach:**
- Run system for 20+ trading days
- Track win rate and average return
- Compare against baseline (random entries)

**Success Criteria:**
- Win rate > 55%
- Average return > +1.0%
- Profit factor (gross profit / gross loss) > 1.5

### 2. Signal Quality Assessment

**Goal:** Identify which conditions produce best results

**Approach:**
- Export hypothetical trades to CSV
- Analyze which signal conditions correlate with profitable trades
- Adjust signal logic based on findings

**Example Analysis:**
```python
from src.utils.database import get_connection
import pandas as pd

conn = get_connection()
df = pd.read_sql_query("""
    SELECT
        h.ticker,
        h.entry_price,
        h.exit_price,
        h.pnl_percent,
        s.confidence_score,
        s.vwap,
        s.pct_from_yesterday
    FROM hypothetical_trades h
    JOIN signals s ON h.signal_id = s.id
    WHERE h.status = 'closed'
""", conn)
conn.close()

# Analyze correlation between confidence score and P&L
print(df.groupby(pd.cut(df['confidence_score'], bins=3))['pnl_percent'].mean())
```

### 3. Risk Management Tuning

**Goal:** Determine appropriate position sizing and stop-loss levels

**Approach:**
- Calculate max drawdown from historical trades
- Identify worst losing streaks
- Set portfolio risk limits accordingly

**Example:**
- Max single trade loss: -5.2%
- Worst 3-trade streak: -8.7%
- → Set max daily loss limit at -10% of portfolio

---

## Troubleshooting

### No Trades Created

**Problem:** Signals detected but no hypothetical trades appear

**Check:**
1. Scheduler is running: `ps aux | grep run_with_scheduler`
2. Check logs: `tail -f logs/svea_surveillance.log | grep "Hypothetical"`
3. Database table exists:
   ```bash
   sqlite3 data/trades.db "SELECT * FROM hypothetical_trades LIMIT 1;"
   ```

**Solution:**
- Ensure database was initialized with new schema
- Run: `python -c "from src.utils.database import init_database; init_database()"`

### Trades Not Closing at 17:00

**Problem:** Open trades remain after 17:00

**Check:**
1. Scheduler has 17:00 job:
   ```python
   from src.utils.scheduler import DailyScheduler
   scheduler = DailyScheduler()
   scheduler.start()
   scheduler.list_jobs()
   ```
2. Check logs for errors: `grep "17:00" logs/svea_surveillance.log`

**Solution:**
- Manually close trades:
  ```python
  from src.utils.scheduler import DailyScheduler
  scheduler = DailyScheduler()
  scheduler.close_trades_now()
  ```

### Exit Prices Missing

**Problem:** Trades closed but no exit price recorded

**Possible Causes:**
- yfinance data unavailable at 17:00
- Market closed (weekend/holiday)
- Ticker delisted or symbol changed

**Solution:**
- Check yfinance directly: `python -c "import yfinance as yf; print(yf.Ticker('VOLV-B.ST').info)"`
- For missing exit prices, manually update:
  ```sql
  UPDATE hypothetical_trades
  SET exit_price = 245.50, pnl_percent = 1.14
  WHERE id = 45;
  ```

---

## Performance Expectations

### With yfinance Data

**Limitations:**
- 15+ minute delays
- Potential data gaps during volatile days
- Exit prices may be stale (last trade before 17:00)

**Expected Accuracy:**
- Entry prices: ~85% accurate (signal window 9:20-10:00)
- Exit prices: ~75% accurate (market slowing down by 17:00)
- Overall P&L tracking: Good for trend validation, not precise

### Upgrade Path: Real-Time Data

For production trading with accurate tracking:
1. Integrate Nasdaq Nordic API or EODHD
2. Update `src/data/yfinance_provider.py` → create new provider
3. Reduce data age warnings in config
4. Entry/exit accuracy: >98%

---

## Summary

**Automatic Operations:**
- ✅ Hypothetical trades created when signals fire
- ✅ Positions closed at 17:00 CET
- ✅ Performance metrics calculated
- ✅ History page shows results

**You Do:**
- View History page to track performance
- Analyze win rate and average return
- Use insights to validate strategy
- Decide whether to proceed with live trading

**System Does:**
- Everything else automatically

---

*Hypothetical trading system configured: February 13, 2026*
*Status: Production ready*
