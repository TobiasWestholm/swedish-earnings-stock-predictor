# Automatic Monitor Update

**Date:** February 13, 2026
**Change:** Live monitor now starts automatically at 09:00 CET

---

## What Changed

Previously, you had to manually start the live monitor:
```bash
python scripts/run_monitor.py  # Manual start needed
```

Now the monitor starts automatically at 09:00 when the scheduler is running.

---

## Updated Daily Schedule

**08:30 CET** - Morning Screener
- Loads earnings calendar
- Filters stocks by momentum
- Populates watchlist

**09:00 CET** - Live Monitor ⭐ NEW - AUTOMATIC
- Starts monitoring watchlist automatically
- Polls every 60 seconds
- Runs for 90 minutes (until 10:30)
- Detects signals during 9:20-10:00 window
- Creates hypothetical trades

**17:00 CET** - Close Hypothetical Trades
- Fetches exit prices
- Closes all open positions
- Calculates P&L

**17:30 CET** - Daily Cleanup
- Clears watchlist
- Clears signals
- Ready for next day

---

## What You Need to Do on Monday

### Before (Old Workflow)
1. Start app: `python scripts/run_with_scheduler.py`
2. Wait for 08:30 screener
3. **Manually start monitor at 09:00**: `python scripts/run_monitor.py` ❌
4. Monitor runs, signals detected
5. End of day: trades close, cleanup runs

### After (New Workflow - Automatic)
1. Start app: `python scripts/run_with_scheduler.py`
2. **Everything else happens automatically** ✅

---

## No Action Required!

Just keep the app running (or restart it Monday morning before 08:30), and the system will:
- ✅ Run screener at 08:30
- ✅ Start monitor at 09:00 (automatically)
- ✅ Detect signals and create trades (automatically)
- ✅ Close trades at 17:00
- ✅ Cleanup at 17:30

---

## Technical Details

### How It Works

The monitor runs in a **background thread** so it doesn't block the scheduler:

```python
# At 09:00, scheduler triggers:
monitor = LiveMonitor()
monitor.run(duration_minutes=90)  # Runs 09:00-10:30
```

**Why 90 minutes?**
- Signal window is 9:20-10:00 (40 minutes)
- Buffer before (9:00-9:20): 20 minutes to load data
- Buffer after (10:00-10:30): 30 minutes to catch late signals
- Total: 90 minutes

### Logs to Expect

**09:00:00** - Monitor Start
```
[09:00:00] SCHEDULED TASK: Start Live Monitor (09:00)
[09:00:00] Starting live monitor for 2026-02-17
[09:00:00] Monitor will run for 90 minutes (09:00-10:30)
[09:00:00] Live monitor started in background thread
[09:00:01] Loading today's watchlist...
[09:00:01] Loaded 3 tickers from watchlist
[09:00:01] Starting live monitoring for 3 tickers
```

**09:25:32** - Signal Detected
```
[09:25:32] ✓ SIGNAL DETECTED: VOLV-B.ST at 245.50 SEK
[09:25:32] ✓ Signal saved to database (ID: 123)
[09:25:32] ✓ Hypothetical trade created for VOLV-B.ST (ID: 45)
```

**10:30:00** - Monitor Stops
```
[10:30:00] Duration limit reached (90 minutes)
[10:30:00] Live monitor completed successfully
```

---

## Manual Override (Testing)

If you still want to manually trigger the monitor:

```bash
# Option 1: Use the old script (still works)
python scripts/run_monitor.py

# Option 2: Trigger via scheduler API
python -c "
from src.utils.scheduler import DailyScheduler
scheduler = DailyScheduler()
scheduler.start_monitor_now()
"
```

---

## Rollback (If Needed)

If you want to disable automatic monitoring:

Edit `src/utils/scheduler.py` and comment out the 09:00 job:

```python
# # Schedule live monitor start (09:00 CET)
# self.scheduler.add_job(
#     func=self._start_live_monitor,
#     trigger=CronTrigger(hour=9, minute=0, timezone=self.timezone),
#     id='start_monitor',
#     name='Start Live Monitor (09:00)',
#     replace_existing=True
# )
```

Then restart the app and manually run the monitor as before.

---

## Summary

**Before:**
- ❌ Manual monitor start required
- ❌ Easy to forget to start it
- ❌ No signals if you forget

**After:**
- ✅ Fully automatic
- ✅ Zero manual intervention
- ✅ Guaranteed signal detection

**Monday Morning:**
- Start app before 08:30
- Go make coffee ☕
- System handles everything
- Check History page at end of day for results

---

*Automatic monitor configured: February 13, 2026*
*No action required from user*
