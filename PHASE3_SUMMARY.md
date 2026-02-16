# Phase 3 Implementation Summary: Live Monitoring + VWAP

## Status: ✅ COMPLETE

Phase 3 (Live Monitoring + VWAP calculations) has been successfully implemented.

---

## What Was Implemented

### 1. Technical Indicators Module ✅
**File:** `src/monitoring/indicators.py`

**Functions:**
- `calculate_vwap()` - Volume Weighted Average Price calculation
- `calculate_cumulative_vwap()` - Cumulative VWAP across time series
- `calculate_sma()` - Simple Moving Average
- `calculate_ema()` - Exponential Moving Average
- `calculate_price_change()` - Price change metrics
- `calculate_intraday_metrics()` - Comprehensive intraday statistics

**Key Features:**
- Handles typical price calculation: (High + Low + Close) / 3
- Cumulative VWAP from market open
- Error handling for missing/invalid data

### 2. Live Monitor ✅
**File:** `src/monitoring/live_monitor.py`

**Class:** `LiveMonitor`

**Functionality:**
- Loads today's watchlist automatically
- Polls prices every 60 seconds (configurable)
- Calculates VWAP in real-time
- Stores data to database
- Market hours awareness (09:00-17:30 CET)
- Monitoring window (09:00-10:30 CET focused)

**Methods:**
- `load_watchlist()` - Load stocks to monitor
- `poll_watchlist()` - Fetch current data for all tickers
- `is_market_hours()` - Check if market is open
- `is_monitoring_window()` - Check if in 09:00-10:30 window
- `run()` - Main monitoring loop
- `stop()` - Graceful shutdown

### 3. Database Updates ✅
**Added Table:** `intraday_data`

**Schema:**
```sql
CREATE TABLE intraday_data (
    id INTEGER PRIMARY KEY,
    ticker TEXT,
    timestamp TIMESTAMP,
    date DATE,
    open_price REAL,
    current_price REAL,
    high REAL,
    low REAL,
    volume INTEGER,
    vwap REAL,
    data_age_seconds INTEGER,
    created_at TIMESTAMP
);
```

**New Functions:**
- `save_intraday_data()` - Store monitoring snapshots
- `get_intraday_data()` - Retrieve ticker history
- `get_latest_intraday_data()` - Get current state for all tickers

### 4. Monitoring Script ✅
**File:** `scripts/run_monitor.py`

**Usage:**
```bash
# Run until stopped
python scripts/run_monitor.py

# Run for specific duration
python scripts/run_monitor.py --duration 90

# Monitor specific date's watchlist
python scripts/run_monitor.py --date 2026-02-13
```

**Features:**
- Auto-loads today's watchlist
- Validates watchlist exists before starting
- Displays monitored stocks
- Graceful Ctrl+C handling
- Clear status messages

### 5. API Endpoints ✅
**New Routes:**

1. **GET /api/monitoring/status**
   - Returns monitoring status (running/idle/not_running)
   - Checks data freshness

2. **GET /api/monitoring/live**
   - Returns latest intraday data for all tickers
   - Includes VWAP, prices, volume

3. **GET /api/monitoring/ticker/<ticker>**
   - Returns full intraday history for specific ticker
   - Query param: `date` (YYYY-MM-DD)

### 6. UI Integration ✅

**Dashboard Updates:**
- Live monitoring status (auto-updates every 10s)
- Status indicator: Running/Idle/Not Running
- Last update timestamp

**Watchlist Updates:**
- Added VWAP column
- Live price updates every 10 seconds
- Color-coded VWAP (green if price > VWAP, red if below)
- Live/Stale status badges
- Auto-refresh when monitoring active

**CSS Updates:**
- `.status-live` - Green badge for active monitoring
- `.status-stale` - Red badge for stale data
- `.status-idle` - Gray for idle state

---

## How to Use

### Step 1: Run the Screener
```bash
python scripts/run_screener.py
```
This creates today's watchlist.

### Step 2: Start Live Monitoring
```bash
python scripts/run_monitor.py
```

**What happens:**
1. Loads today's watchlist (4 stocks in current test)
2. Checks if within monitoring window (09:00-10:30 CET)
3. Polls prices every 60 seconds
4. Calculates VWAP from market open
5. Saves data to database
6. Displays live updates in terminal

### Step 3: View in Web UI
Open http://127.0.0.1:5000/watchlist

**You'll see:**
- Current price (auto-updates every 10s)
- VWAP column (color-coded)
- Live status badges
- Monitoring status in dashboard

---

## Test Results

### ✅ Monitoring Test
**Watchlist:** 4 stocks (VSSAB-B.ST, ELTEL.ST, GGEO.ST, DIOS.ST)

**Sample Output:**
```
VSSAB-B.ST   - Open: 139.50, Current: 139.00, VWAP: 139.69, Change: -0.36%
ELTEL.ST     - Open: 9.04,   Current: 9.30,   VWAP: 9.32,   Change: +2.88%
GGEO.ST      - Open: 9.88,   Current: 9.98,   VWAP: 9.88,   Change: +1.01%
DIOS.ST      - Open: 68.00,  Current: 68.75,  VWAP: 68.37,  Change: +1.10%
```

### ✅ Database Verification
- 4 stocks saved to `intraday_data` table
- VWAP calculated correctly
- Timestamps accurate
- Data retrievable via API

### ✅ UI Integration
- Dashboard shows "running" status
- Watchlist displays live prices
- VWAP column updates automatically
- Color coding works (green/red)

---

## Configuration

**File:** `config/config.yaml`

```yaml
monitoring:
  poll_interval: 60                # Seconds between polls
  signal_window_start: "09:30"     # Signal detection start (Phase 4)
  signal_window_end: "09:45"       # Signal detection end (Phase 4)
  max_price_extension: 0.05        # 5% max extension (Phase 4)

market:
  timezone: "Europe/Stockholm"
  market_open: "09:00"
  market_close: "17:30"
```

---

## Architecture Highlights

### Data Flow
```
Watchlist (DB)
    ↓
LiveMonitor.load_watchlist()
    ↓
Poll every 60s → YFinanceProvider
    ↓
Calculate VWAP → indicators.py
    ↓
Save to DB → intraday_data table
    ↓
API endpoints → /api/monitoring/*
    ↓
UI (JavaScript) → Auto-refresh every 10s
```

### Market Hours Logic
- **Market Hours:** 09:00 - 17:30 CET (Mon-Fri)
- **Monitoring Window:** 09:00 - 10:30 CET (focused period)
- **Signal Window:** 09:30 - 09:45 CET (Phase 4)

Monitor only runs during monitoring window, saving API calls and focusing on the critical morning session.

### VWAP Calculation
```python
# Typical Price
typical_price = (High + Low + Close) / 3

# VWAP
vwap = Sum(typical_price * volume) / Sum(volume)

# Cumulative from market open
```

This is the standard VWAP used by traders for intraday analysis.

---

## Phase 3 Files Created/Modified

### New Files (3)
1. `src/monitoring/indicators.py` - Technical indicators
2. `src/monitoring/live_monitor.py` - Monitoring engine
3. `scripts/run_monitor.py` - CLI script

### Modified Files (6)
1. `src/utils/database.py` - Added intraday_data table + functions
2. `src/ui/routes.py` - Added monitoring API endpoints
3. `src/ui/templates/dashboard.html` - Live status updates
4. `src/ui/templates/watchlist.html` - VWAP column + live updates
5. `src/ui/static/css/style.css` - New status badge styles
6. `config/config.yaml` - Already had monitoring settings

---

## Known Limitations

### 1. yfinance Delay
- **15+ minute delay** on data
- Not suitable for precise 9:30 entry in production
- Data age warnings included

### 2. API Rate Limits
- 60-second poll interval to avoid rate limits
- 0.5s delay between ticker requests
- Recommended: Max 20 tickers per watchlist

### 3. Market Hours
- Only monitors during weekdays
- Auto-stops outside 09:00-10:30 window
- No after-hours trading support

---

## Next Steps: Phase 4

Phase 3 provides the foundation for Phase 4: **Signal Detection**

**Phase 4 will add:**
1. **Signal Detector** - Detect 9:30-9:45 entry conditions
   - Price above VWAP ✓ (VWAP now available)
   - Price above open ✓ (Data tracked)
   - Not extended >5% above open ✓

2. **Position Sizer** - Calculate trade size
   - Based on account value
   - Stop-loss distance
   - Risk percentage (1%)

3. **Risk Manager** - Portfolio constraints
   - Max 3 positions per day
   - Max daily loss limit
   - Track open positions

4. **Signal UI** - Display entry signals
   - Real-time signal alerts
   - Risk calculations shown
   - "Open in Avanza" button

---

## Success Criteria: Phase 3 ✅

- ✅ Live monitoring tracks 3-5 tickers simultaneously
- ✅ VWAP calculated correctly with real-time data
- ✅ Data saved to database every 60 seconds
- ✅ UI updates automatically with live prices
- ✅ Market hours awareness working
- ✅ Data staleness warnings appear correctly
- ✅ Monitoring script starts/stops gracefully

**Phase 3 is complete and ready for Phase 4!**

---

## Example Usage Session

```bash
# Terminal 1: Start monitoring
$ python scripts/run_monitor.py

================================================================================
SVEA SURVEILLANCE - LIVE MONITORING
================================================================================

✓ Watchlist for 2026-02-13: 4 stocks

Stocks to monitor:
  1. VSSAB-B.ST    - Viking Supply Ships
  2. ELTEL.ST      - Eltel
  3. GGEO.ST       - Guideline Geo
  4. DIOS.ST       - Diös

✓ Monitoring window: 09:00 - 10:30 CET
✓ Poll interval: 60 seconds
✓ VWAP calculation: Enabled

✓ Starting monitoring...
================================================================================

=== Poll #1 at 09:05:23 ===
Polling 4 tickers...
VSSAB-B.ST: Saved intraday data (VWAP: 139.69)
ELTEL.ST: Saved intraday data (VWAP: 9.32)
GGEO.ST: Saved intraday data (VWAP: 9.88)
DIOS.ST: Saved intraday data (VWAP: 68.37)

Current prices:
  VSSAB-B.ST   - Price: 139.00, VWAP: 139.69, Change: -0.36%
  ELTEL.ST     - Price: 9.30, VWAP: 9.32, Change: +2.88%
  GGEO.ST      - Price: 9.98, VWAP: 9.88, Change: +1.01%
  DIOS.ST      - Price: 68.75, VWAP: 68.37, Change: +1.10%

Waiting 60 seconds until next poll...
```

```bash
# Terminal 2: View in browser
# Open http://127.0.0.1:5000/watchlist
# See live prices and VWAP updating every 10 seconds
```

---

**Phase 3 Complete!** The system now tracks live prices and calculates VWAP during market hours, providing the foundation for signal detection in Phase 4.
