# Catch-Up Feature: Smart Late Start Handling

**Date:** February 13, 2026
**Feature:** Automatic execution of missed tasks when app starts late

---

## Problem Solved

**Before:** If you started the app at 09:05, you'd miss:
- Morning screener (08:30) ❌
- Live monitor start (09:00) ❌
- No signals detected today ❌

**After:** Start at any time, system catches up automatically ✅

---

## How It Works

When the scheduler starts, it checks:
1. What time is it now?
2. Which tasks should have already run?
3. Do those tasks still make sense to run?
4. Execute missed tasks immediately

### Catch-Up Rules

#### Morning Screener (08:30)
**Runs if:**
- Current time ≥ 08:30
- Current time < 17:30
- Watchlist is empty (hasn't run yet)

**Why:** You still want to see today's watchlist candidates

#### Live Monitor (09:00)
**Runs if:**
- Current time ≥ 09:00
- Current time < 10:00
- Monitor not already running

**Duration:** Remaining time until 10:30

**Skips if:** Past 10:00 (signal window 9:20-10:00 already missed)

#### Close Trades (17:00)
**Runs if:**
- Current time ≥ 17:00
- Current time < 17:30
- Open trades exist

**Why:** Ensures P&L is calculated for history

#### Daily Cleanup (17:30)
**Runs if:**
- Current time ≥ 17:30
- Today's data still exists

**Why:** Prepares database for tomorrow

---

## Real-World Scenarios

### Scenario 1: "Forgot to start before market open"

**Started:** 09:02 CET

**What happens:**
```
[09:02:15] Catch-up check starting...
[09:02:15] ⚠️  Screener missed - running now
[09:02:30] ✓ Screener complete: 3 stocks found
[09:02:30] ⚠️  Monitor missed - starting now
[09:02:31] ✓ Monitor started (runs for 88 minutes)
```

**Result:**
- Screener runs immediately (30 seconds)
- Monitor starts and catches signal window (9:20-10:00)
- Full functionality preserved ✅

### Scenario 2: "Started during lunch break"

**Started:** 12:00 CET

**What happens:**
```
[12:00:05] Catch-up check starting...
[12:00:05] ⚠️  Screener missed - running now
[12:00:20] ✓ Screener complete: 3 stocks found
[12:00:20] ✓ Monitor window passed - skipping
```

**Result:**
- Screener runs (you can view watchlist)
- Monitor skipped (signal window passed)
- No signals today (started too late) ⚠️

### Scenario 3: "Started before market close"

**Started:** 17:15 CET

**What happens:**
```
[17:15:00] Catch-up check starting...
[17:15:00] ✓ Screener already completed
[17:15:00] ✓ Monitor window passed
[17:15:00] ⚠️  Trades not closed - closing now
[17:15:00]    Found 2 open trades
[17:15:05] ✓ Closed 2 trades
```

**Result:**
- Screener already ran (app was running earlier)
- Trades close immediately
- Cleanup runs at 17:30 as scheduled

### Scenario 4: "Restarted in evening"

**Started:** 20:00 CET

**What happens:**
```
[20:00:00] Catch-up check starting...
[20:00:00] ⚠️  Cleanup missed - running now
[20:00:00]    Found 3 watchlist entries
[20:00:01] ✓ Cleanup complete
```

**Result:**
- All daily tasks completed
- Database ready for tomorrow
- Can view today's history

---

## Technical Details

### Detection Logic

**Screener:**
```python
if current_time >= 08:30 and current_time < 17:30:
    watchlist = get_watchlist(today)
    if not watchlist:  # Empty means hasn't run
        run_screener()
```

**Monitor:**
```python
if current_time >= 09:00 and current_time < 10:00:
    if monitor not running:
        remaining_minutes = calculate_time_until(10:30)
        start_monitor(duration=remaining_minutes)
```

**Close Trades:**
```python
if current_time >= 17:00 and current_time < 17:30:
    open_trades = get_open_trades(today)
    if open_trades:  # Trades exist means hasn't closed
        close_trades()
```

**Cleanup:**
```python
if current_time >= 17:30:
    watchlist = get_watchlist(today)
    if watchlist:  # Data exists means hasn't cleaned
        run_cleanup()
```

### Thread Safety

Monitor runs in background thread to avoid blocking:
```python
monitor_thread = threading.Thread(target=run_monitor, daemon=True)
monitor_thread.start()
```

This allows:
- Scheduler continues running
- Web UI remains responsive
- Multiple tasks don't block each other

---

## Log Examples

### Successful Catch-Up (Started 09:02)

```
[09:02:15] ================================================================================
[09:02:15] CATCH-UP CHECK: Looking for missed tasks...
[09:02:15] Current time: 09:02:15 CET
[09:02:15] ================================================================================
[09:02:15] ⚠️  Missed Task: Morning screener has not run yet
[09:02:15]    Running screener now (catch-up)...
[09:02:16] ================================================================================
[09:02:16] SCHEDULED TASK: Morning Screener (08:30)
[09:02:16] ================================================================================
[09:02:16] Running screener for 2026-02-17
[09:02:28] Found 5 companies reporting earnings
[09:02:29] Filtering 5 stocks by momentum...
[09:02:30] Morning screener complete: 3 stocks found
[09:02:30] ================================================================================
[09:02:30] ⚠️  Missed Task: Live monitor has not started yet
[09:02:30]    Starting monitor now (catch-up)...
[09:02:30]    Monitor will run for 88 minutes (until 10:30)
[09:02:31] Live monitor started in background thread
[09:02:31] ================================================================================
[09:02:31] Catch-up check complete
[09:02:31] ================================================================================
[09:02:32] Loading today's watchlist...
[09:02:32] Loaded 3 tickers from watchlist
[09:02:32] Starting live monitoring for 3 tickers
[09:02:32] Poll interval: 60 seconds
```

### No Catch-Up Needed (Started 08:00)

```
[08:00:00] ================================================================================
[08:00:00] CATCH-UP CHECK: Looking for missed tasks...
[08:00:00] Current time: 08:00:00 CET
[08:00:00] ================================================================================
[08:00:00] (No tasks to catch up - too early)
[08:00:00] ================================================================================
[08:00:00] Catch-up check complete
[08:00:00] ================================================================================

... at 08:30, screener runs as scheduled ...
... at 09:00, monitor starts as scheduled ...
```

### Partial Catch-Up (Started 11:30)

```
[11:30:00] ================================================================================
[11:30:00] CATCH-UP CHECK: Looking for missed tasks...
[11:30:00] Current time: 11:30:00 CET
[11:30:00] ================================================================================
[11:30:00] ⚠️  Missed Task: Morning screener has not run yet
[11:30:00]    Running screener now (catch-up)...
[11:30:15] Morning screener complete: 3 stocks found
[11:30:15] ✓ Live monitor: Window passed (9:20-10:00), skipping
[11:30:15] ================================================================================
[11:30:15] Catch-up check complete
[11:30:15] ================================================================================
```

---

## Benefits

### For Users

1. **Flexible Start Times**
   - Start app whenever convenient
   - Don't miss functionality
   - No need to babysit schedule

2. **Resilient to Crashes**
   - If app crashes and restarts
   - Automatically resumes where it left off
   - No manual intervention needed

3. **Easy Recovery**
   - Forgot to start on time? No problem
   - System figures out what to do
   - Minimal data loss

### For System

1. **Self-Healing**
   - Detects incomplete state
   - Fixes itself automatically
   - Reduces user burden

2. **Idempotent**
   - Won't run tasks twice
   - Checks completion before running
   - Safe to restart multiple times

3. **Time-Aware**
   - Understands task windows
   - Skips tasks that don't make sense
   - Optimizes remaining time

---

## Edge Cases Handled

### Multiple Restarts

**Scenario:** App crashes at 09:30, restarts, crashes again at 10:15, restarts again

**09:30 Restart:**
- Screener: Already ran ✓ (sees watchlist)
- Monitor: Starts with 60 min remaining ✓

**10:15 Restart:**
- Screener: Already ran ✓
- Monitor: Skips (past 10:00) ✓

### Data Exists But Task Failed

**Scenario:** Screener ran but only saved 1 stock due to error

**Current behavior:**
- Watchlist has 1 stock → screener considered "complete"
- Won't re-run automatically

**Future improvement:**
- Could add quality checks
- Re-run if watchlist seems incomplete

### Time Zone Changes

**Scenario:** System time zone changes

**Current behavior:**
- Scheduler uses `Europe/Stockholm`
- All time comparisons use same timezone
- Should work correctly

---

## Limitations

### Won't Catch Up If...

1. **Monitor window completely missed**
   - Started after 10:00
   - Signal window (9:20-10:00) already passed
   - No signals detected for today

2. **Multiple days missed**
   - App off for days/weeks
   - Only catches up current day
   - Historical data not backfilled

3. **Calendar not updated**
   - If earnings calendar empty
   - Screener runs but finds 0 stocks
   - Not a catch-up issue, data issue

### When to Manually Intervene

**If started after 10:00:**
- Check History page for open trades
- If open, manually close:
  ```bash
  python -c "from src.utils.scheduler import DailyScheduler; s = DailyScheduler(); s.close_trades_now()"
  ```

**If data looks wrong:**
- Check logs for errors
- Manually re-run screener:
  ```bash
  python scripts/run_screener.py
  ```

---

## Testing the Catch-Up

### Test 1: Late Screener

```bash
# Start app at 09:05
python scripts/run_with_scheduler.py

# Check logs
tail -f logs/svea_surveillance.log | grep "CATCH-UP"

# Should see:
# [09:05:XX] ⚠️  Missed Task: Morning screener
# [09:05:XX] Morning screener complete: X stocks found
```

### Test 2: Simulate Late Start

```python
# In Python shell at 14:00
from src.utils.scheduler import DailyScheduler

scheduler = DailyScheduler()
scheduler.start()

# Check logs - screener should have run
# Monitor should be skipped (past 10:00)
```

### Test 3: Manual Trigger

```python
from src.utils.scheduler import DailyScheduler

scheduler = DailyScheduler()

# Manually trigger catch-up (testing)
scheduler._catch_up_missed_tasks()
```

---

## Summary

**Key Feature:**
- Start app anytime, system catches up automatically

**What Gets Caught Up:**
- ✅ Screener (if before 17:30)
- ✅ Monitor (if before 10:00, runs for remaining time)
- ✅ Close trades (if after 17:00, before 17:30)
- ✅ Cleanup (if after 17:30)

**What Doesn't:**
- ❌ Historical data (only current day)
- ❌ Past signal windows (can't retroactively detect signals)

**Best Practice:**
- Start before 08:30 for full automation
- But even late starts work fine!

---

*Catch-up feature implemented: February 13, 2026*
*Start the app anytime - we've got you covered!*
