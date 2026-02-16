# Daily Automation Guide

**Last Updated:** February 13, 2026
**Purpose:** Automatic daily operations for hands-free trading system

---

## Overview

The trading system now includes automatic daily operations:
- **08:30 CET**: Morning screener runs automatically (populate watchlist)
- **09:00 CET**: Live monitor starts automatically (runs until 10:30, detects signals)
- **17:00 CET**: Close all open hypothetical trades (end of trading day)
- **17:30 CET**: End of day cleanup (clear old watchlist and signals)
- **Always**: Web UI shows today's date dynamically

No manual intervention needed - the system handles daily resets and monitoring automatically.

---

## What Happens Automatically

### Morning (08:30 CET)
**Task:** Morning Screener

**Actions:**
1. Loads today's earnings calendar from `data/earnings_calendar.csv`
2. Filters stocks by momentum (3M + 1Y + SMA200)
3. Saves results to watchlist table
4. Logs how many stocks passed filter

**Result:** Watchlist populated with today's candidates

**Logs:**
```
[08:30:00] SCHEDULED TASK: Morning Screener (08:30)
[08:30:00] Running screener for 2026-02-13
[08:30:15] Morning screener complete: 3 stocks found
```

### Morning Monitoring (09:00 CET)
**Task:** Start Live Monitor

**Actions:**
1. Starts live monitor for today's watchlist
2. Polls each ticker every 60 seconds
3. Calculates VWAP and 5-minute averages
4. Checks for entry signals during 9:20-10:00 window
5. Creates signals and hypothetical trades when conditions met
6. Runs for 90 minutes (until 10:30)

**Result:** Signals detected and hypothetical trades created automatically

**Logs:**
```
[09:00:00] SCHEDULED TASK: Start Live Monitor (09:00)
[09:00:00] Starting live monitor for 2026-02-13
[09:00:00] Monitor will run for 90 minutes (09:00-10:30)
[09:00:00] Live monitor started in background thread
[09:00:01] Loading today's watchlist...
[09:00:01] Loaded 3 tickers from watchlist
[09:00:01] Starting live monitoring for 3 tickers
[09:00:01] Poll interval: 60 seconds
[09:25:32] ✓ SIGNAL DETECTED: VOLV-B.ST at 245.50 SEK
[09:25:32] ✓ Signal saved to database (ID: 123)
[09:25:32] ✓ Hypothetical trade created for VOLV-B.ST (ID: 45)
[10:30:00] Duration limit reached (90 minutes)
[10:30:00] Live monitor completed successfully
```

### End of Trading (17:00 CET)
**Task:** Close Hypothetical Trades

**Actions:**
1. Gets all open hypothetical trades for today
2. Fetches current market price for each ticker
3. Closes each trade with exit price
4. Calculates P&L percentage
5. Updates trade status to 'closed'

**Result:** All hypothetical trades closed with performance metrics

**Logs:**
```
[17:00:00] SCHEDULED TASK: Close Hypothetical Trades (17:00)
[17:00:00] Closing open trades for 2026-02-13
[17:00:00] Found 3 open trades to close
[17:00:00] Fetching exit price for VOLV-B.ST...
[17:00:01] ✓ Closed VOLV-B.ST: Entry 245.50 → Exit 248.30 (+1.14%)
[17:00:01] Fetching exit price for ERIC-B.ST...
[17:00:02] ✓ Closed ERIC-B.ST: Entry 52.80 → Exit 51.90 (-1.70%)
[17:00:02] Fetching exit price for HM-B.ST...
[17:00:03] ✓ Closed HM-B.ST: Entry 178.20 → Exit 180.50 (+1.29%)
[17:00:03] Closed 3/3 hypothetical trades
```

### End of Day (17:30 CET)
**Task:** Daily Cleanup

**Actions:**
1. Clears today's watchlist entries
2. Clears today's signal entries
3. Keeps intraday data from today only
4. Logs how many entries removed

**Result:** Database ready for next trading day

**Logs:**
```
[17:30:00] SCHEDULED TASK: End of Day Cleanup (17:30)
[17:30:00] Clearing data for 2026-02-13
[17:30:01] Cleared 3 watchlist entries
[17:30:01] Cleared 2 signal entries
[17:30:01] End of day cleanup complete
```

---

## Starting the System with Scheduler

### Option 1: Full Automation (Recommended)

```bash
# Start web app + scheduler together
python scripts/run_with_scheduler.py
```

This starts:
- ✅ Flask web application (http://localhost:5000)
- ✅ Background scheduler (08:30 screener, 09:00 monitor, 17:00 close trades, 17:30 cleanup)

**Output:**
```
================================================================================
SVEA SURVEILLANCE - STARTING WITH SCHEDULER
================================================================================
✓ Database initialized
Starting daily scheduler...
✓ Scheduler started
  - 08:30 CET: Morning screener (automatic)
  - 09:00 CET: Start live monitor (runs until 10:30)
  - 17:00 CET: Close hypothetical trades (automatic)
  - 17:30 CET: End of day cleanup (automatic)
Starting web application on 127.0.0.1:5000...
================================================================================
✓ SYSTEM READY
================================================================================

Web UI:  http://127.0.0.1:5000

Pages:
  - Dashboard:  http://127.0.0.1:5000/
  - Watchlist:  http://127.0.0.1:5000/watchlist
  - Signals:    http://127.0.0.1:5000/signals

Automatic Tasks:
  - 08:30: Morning screener runs automatically
  - 09:00: Live monitor starts automatically (runs until 10:30)
  - 17:00: Hypothetical trades closed automatically
  - 17:30: Old data cleared automatically

Press Ctrl+C to stop
================================================================================
```

### Option 2: Manual Mode (No Automation)

```bash
# Run without scheduler (manual screener execution only)
python scripts/run_with_scheduler.py --no-scheduler
```

Use this if you want to run the screener manually:
```bash
python scripts/run_screener.py
```

### Option 3: Just the Web App (Original Method)

```bash
# Run only web app (no scheduler, no automation)
python scripts/run_app.py
```

---

## Late Start / Catch-Up Feature

**What if you start the app after scheduled times?**

The system is intelligent and will **automatically catch up** on missed tasks.

### Examples

**Scenario 1: Started at 09:02**
```
[09:02:15] CATCH-UP CHECK: Looking for missed tasks...
[09:02:15] Current time: 09:02:15 CET
[09:02:15] ⚠️  Missed Task: Morning screener has not run yet
[09:02:15]    Running screener now (catch-up)...
[09:02:16] SCHEDULED TASK: Morning Screener (08:30)
[09:02:30] Morning screener complete: 3 stocks found
[09:02:30] ⚠️  Missed Task: Live monitor has not started yet
[09:02:30]    Starting monitor now (catch-up)...
[09:02:30]    Monitor will run for 88 minutes (until 10:30)
[09:02:31] Live monitor started in background thread
[09:02:31] Catch-up check complete
```

**Result:**
- ✅ Screener runs immediately
- ✅ Monitor starts immediately (runs for remaining time until 10:30)
- ✅ Signals detected during 9:20-10:00 window
- ✅ No functionality lost

**Scenario 2: Started at 11:00**
```
[11:00:05] CATCH-UP CHECK: Looking for missed tasks...
[11:00:05] Current time: 11:00:05 CET
[11:00:05] ⚠️  Missed Task: Morning screener has not run yet
[11:00:05]    Running screener now (catch-up)...
[11:00:06] Morning screener complete: 3 stocks found
[11:00:06] ✓ Live monitor: Window passed (9:20-10:00), skipping
[11:00:06] Catch-up check complete
```

**Result:**
- ✅ Screener runs (you can still see watchlist)
- ❌ Monitor skipped (signal window already passed)
- ⚠️  No signals detected today (started too late)

**Scenario 3: Started at 17:15**
```
[17:15:00] CATCH-UP CHECK: Looking for missed tasks...
[17:15:00] Current time: 17:15:00 CET
[17:15:00] ✓ Morning screener: Already completed (found 3 stocks)
[17:15:00] ✓ Live monitor: Window passed (9:20-10:00), skipping
[17:15:00] ⚠️  Missed Task: Trades have not been closed yet
[17:15:00]    Found 2 open trades
[17:15:00]    Closing trades now (catch-up)...
[17:15:01] SCHEDULED TASK: Close Hypothetical Trades (17:00)
[17:15:05] Closed 2/2 hypothetical trades
[17:15:05] Catch-up check complete
```

**Result:**
- ✅ Screener already ran (during market hours)
- ✅ Trades close immediately
- ✅ Cleanup will run at 17:30 as scheduled

**Scenario 4: Started at 18:00 (evening)**
```
[18:00:00] CATCH-UP CHECK: Looking for missed tasks...
[18:00:00] Current time: 18:00:00 CET
[18:00:00] ⚠️  Missed Task: Daily cleanup has not run yet
[18:00:00]    Found 3 watchlist entries from today
[18:00:00]    Running cleanup now (catch-up)...
[18:00:01] SCHEDULED TASK: End of Day Cleanup (17:30)
[18:00:01] Cleared 3 watchlist entries
[18:00:01] Cleared 2 signal entries
[18:00:01] End of day cleanup complete
[18:00:01] Catch-up check complete
```

**Result:**
- ✅ All missed tasks executed
- ✅ System ready for tomorrow

### Catch-Up Logic

The system checks:

1. **Screener (08:30)**
   - Runs if: Current time ≥ 08:30 AND < 17:30 AND watchlist is empty
   - Reason: You might still want to see today's watchlist

2. **Monitor (09:00)**
   - Runs if: Current time ≥ 09:00 AND < 10:00 AND monitor not running
   - Runs for: Remaining time until 10:30
   - Skips if: Past 10:00 (signal window missed)

3. **Close Trades (17:00)**
   - Runs if: Current time ≥ 17:00 AND < 17:30 AND open trades exist
   - Reason: Ensures P&L is calculated

4. **Cleanup (17:30)**
   - Runs if: Current time ≥ 17:30 AND today's data still exists
   - Reason: Prepares system for tomorrow

### Best Practices

**Recommended:**
- Start app before 08:30 for full automation
- Leave running 24/7 for zero manual intervention

**Acceptable:**
- Start between 08:30-09:00: Screener catches up, monitor starts on time
- Start between 09:00-10:00: Screener + monitor catch up, reduced signal window

**Not Recommended:**
- Start after 10:00: Monitor skipped, no signals today
- Start after 17:30: Can view history but no new data collection

---

## Command Line Options

```bash
python scripts/run_with_scheduler.py [OPTIONS]

Options:
  --host HOST         Host to bind to (default: 127.0.0.1)
  --port PORT         Port to bind to (default: 5000)
  --debug             Run in debug mode
  --no-scheduler      Disable automatic scheduler

Examples:
  # Run on all interfaces (accessible from network)
  python scripts/run_with_scheduler.py --host 0.0.0.0

  # Run on different port
  python scripts/run_with_scheduler.py --port 8080

  # Debug mode (auto-reload on code changes)
  python scripts/run_with_scheduler.py --debug

  # Manual mode (no automation)
  python scripts/run_with_scheduler.py --no-scheduler
```

---

## How the Scheduler Works

### Technology
- **APScheduler** (Advanced Python Scheduler)
- Runs as background thread
- Cron-like scheduling (hour:minute triggers)
- Timezone-aware (Europe/Stockholm)

### Schedule Configuration

**Defined in:** `src/utils/scheduler.py`

```python
# Morning screener: 08:30 CET every day
scheduler.add_job(
    func=_run_morning_screener,
    trigger=CronTrigger(hour=8, minute=30, timezone='Europe/Stockholm')
)

# End of day cleanup: 17:30 CET every day
scheduler.add_job(
    func=_run_end_of_day_cleanup,
    trigger=CronTrigger(hour=17, minute=30, timezone='Europe/Stockholm')
)
```

### Changing Schedule Times

Edit `src/utils/scheduler.py`:

```python
# Change morning screener to 08:00
trigger=CronTrigger(hour=8, minute=0, timezone=self.timezone)

# Change cleanup to 18:00
trigger=CronTrigger(hour=18, minute=0, timezone=self.timezone)
```

Then restart the application.

---

## Manual Triggering

### Run Screener Manually
```bash
python scripts/run_screener.py
```

### Run Cleanup Manually
```bash
python -c "from src.utils.cleanup import *; from datetime import date; clear_old_watchlist(date.today()); clear_old_signals(date.today())"
```

### Test Scheduler (Debug)
```python
from src.utils.scheduler import DailyScheduler

scheduler = DailyScheduler()
scheduler.start()

# Manually trigger tasks (for testing)
scheduler.run_screener_now()
scheduler.run_cleanup_now()

# View scheduled jobs
scheduler.list_jobs()
```

---

## Database Cleanup Strategies

### Current Strategy (Default)
- **Watchlist**: Clear today's entries at 17:30
- **Signals**: Clear today's entries at 17:30
- **Intraday Data**: Keep today only

**Rationale:**
- Each day starts fresh
- No historical clutter
- Minimal database size

### Alternative: Keep History

If you want to keep data for analysis:

**Edit** `src/utils/scheduler.py`:

```python
# Keep last 30 days instead of clearing daily
def _run_end_of_day_cleanup(self):
    clear_old_watchlist(keep_days=30)
    clear_old_signals(keep_days=30)
    clear_old_intraday_data(keep_days=7)
```

**Trade-offs:**
- ✅ Keeps historical data for analysis
- ✅ Can review past signals
- ❌ Database grows over time
- ❌ Need periodic maintenance

### Export Before Cleanup

If you want to export data before deleting:

```python
# Add before cleanup in scheduler
def _run_end_of_day_cleanup(self):
    # Export to CSV
    import pandas as pd
    from src.utils.database import get_watchlist, get_signals

    today_str = date.today().strftime('%Y-%m-%d')

    # Export watchlist
    watchlist = get_watchlist(today_str)
    if watchlist:
        df = pd.DataFrame(watchlist)
        df.to_csv(f'data/exports/watchlist_{today_str}.csv', index=False)

    # Export signals
    signals = get_signals(date=today_str)
    if signals:
        df = pd.DataFrame(signals)
        df.to_csv(f'data/exports/signals_{today_str}.csv', index=False)

    # Then clear
    clear_old_watchlist(target_date=date.today())
    clear_old_signals(target_date=date.today())
```

---

## Web UI Date Handling

### Always Shows Today
All pages dynamically use `date.today()`:
- Dashboard: "Today's watchlist"
- Watchlist: Defaults to today (can view other dates via `?date=YYYY-MM-DD`)
- Signals: Defaults to today

### Date Query Parameter

View historical data (if kept):
```
http://localhost:5000/watchlist?date=2026-02-12
http://localhost:5000/signals?date=2026-02-12
```

---

## Troubleshooting

### Scheduler Not Running

**Check logs:**
```bash
tail -f logs/svea_surveillance.log
```

Look for:
```
✓ Scheduler started
  - 08:30 CET: Morning screener
  - 17:30 CET: End of day cleanup
```

**If missing:**
- Make sure you're using `run_with_scheduler.py` not `run_app.py`
- Check for errors during startup
- Verify APScheduler is installed: `pip list | grep APScheduler`

### Tasks Not Executing

**Verify schedule:**
```python
from src.utils.scheduler import DailyScheduler
scheduler = DailyScheduler()
scheduler.start()
scheduler.list_jobs()
```

**Check timezone:**
```python
from datetime import datetime
import pytz
tz = pytz.timezone('Europe/Stockholm')
print(datetime.now(tz))  # Should show correct CET time
```

**Common Issues:**
1. **System time wrong**: Scheduler uses system time - check `date` command
2. **Timezone mismatch**: Scheduler uses Europe/Stockholm - adjust if needed
3. **Application stopped**: Scheduler only runs while app is running

### Screener Finds No Stocks

**08:30 screener ran but no stocks:**

**Possible Reasons:**
1. No earnings in `data/earnings_calendar.csv` for today
2. All stocks failed momentum filter
3. yfinance data unavailable

**Check logs:**
```
[08:30:00] Running screener for 2026-02-13
[08:30:05] Found 5 companies reporting earnings
[08:30:15] Morning screener complete: 0 stocks found
```

**Solution:** Ensure calendar has entries and stocks meet criteria

### Cleanup Clears Wrong Data

**If cleanup is too aggressive:**

Change strategy in `src/utils/scheduler.py`:

```python
# Instead of clearing today
clear_old_watchlist(target_date=date.today())

# Keep today, clear older
clear_old_watchlist(keep_days=1)
```

---

## Production Deployment

### Running as System Service (Linux)

Create `/etc/systemd/system/svea-surveillance.service`:

```ini
[Unit]
Description=Svea Surveillance Trading System
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/Tradeit
Environment="PATH=/path/to/Tradeit/venv/bin"
ExecStart=/path/to/Tradeit/venv/bin/python scripts/run_with_scheduler.py --host 0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable svea-surveillance
sudo systemctl start svea-surveillance
sudo systemctl status svea-surveillance
```

### Running as macOS Launch Agent

Create `~/Library/LaunchAgents/com.svea.surveillance.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.svea.surveillance</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/Tradeit/venv/bin/python</string>
        <string>/path/to/Tradeit/scripts/run_with_scheduler.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/Tradeit</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

Load:
```bash
launchctl load ~/Library/LaunchAgents/com.svea.surveillance.plist
launchctl start com.svea.surveillance
```

### Running in Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "scripts/run_with_scheduler.py", "--host", "0.0.0.0"]
```

---

## Monitoring

### Check if System is Running

```bash
# Check process
ps aux | grep run_with_scheduler

# Check logs
tail -f logs/svea_surveillance.log

# Check web UI
curl http://localhost:5000
```

### View Scheduler Activity

**In logs:**
```bash
grep "SCHEDULED TASK" logs/svea_surveillance.log
```

**Expected output:**
```
[08:30:00] SCHEDULED TASK: Morning Screener (08:30)
[08:30:15] Morning screener complete: 3 stocks found
[17:30:00] SCHEDULED TASK: End of Day Cleanup (17:30)
[17:30:01] End of day cleanup complete
```

### Database Stats

```bash
python -c "from src.utils.cleanup import get_database_stats; import pprint; pprint.pprint(get_database_stats())"
```

**Output:**
```python
{
    'watchlist': {
        'count': 3,
        'oldest_date': '2026-02-13',
        'newest_date': '2026-02-13'
    },
    'signals': {
        'count': 2,
        'oldest_date': '2026-02-13',
        'newest_date': '2026-02-13'
    },
    'intraday_data': {
        'count': 145,
        'oldest_date': '2026-02-13',
        'newest_date': '2026-02-13'
    }
}
```

---

## Benefits of Automation

### Before (Manual):
- ❌ Had to remember to run screener at 08:30
- ❌ Old data accumulated in database
- ❌ Had to manually clear signals/watchlist
- ❌ Risk of viewing stale data
- ❌ Date confusion (yesterday's watchlist still showing)

### After (Automated):
- ✅ Screener runs automatically every morning
- ✅ Database stays clean (auto-cleanup)
- ✅ Always see today's data
- ✅ Zero manual intervention needed
- ✅ Consistent daily operations

---

## Summary

**Setup (One Time):**
```bash
# Install APScheduler
pip install -r requirements.txt

# Start system with scheduler
python scripts/run_with_scheduler.py
```

**Daily Operations (Automatic):**
- 08:30: Screener runs → Watchlist populated
- 09:00: Monitor starts → Signals detected automatically
- 17:00: Close trades → Hypothetical positions closed
- 17:30: Cleanup runs → Old data cleared
- Always: Web UI shows today's date

**You Do:**
- Keep `data/earnings_calendar.csv` updated
- View web UI for signals
- Execute trades (paper or live)

**System Does:**
- Everything else automatically

---

*Automation configured: February 13, 2026*
*Schedule: 08:30 screener, 09:00 monitor, 17:00 close trades, 17:30 cleanup*
*Status: Production ready*
