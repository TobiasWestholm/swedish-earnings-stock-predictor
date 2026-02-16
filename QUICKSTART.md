# Svea Surveillance - Quick Start Guide

This guide will get you up and running with Phase 1 (Static Screener + Web UI) in under 5 minutes.

## Prerequisites

- Python 3.9 or higher
- pip package manager
- Terminal/Command line access

## Installation Steps

### 1. Navigate to Project Directory

```bash
cd svea-surveillance
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate  # On Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- yfinance (market data)
- pandas & numpy (data processing)
- flask (web framework)
- pyyaml (configuration)

### 4. Initialize Database

```bash
python -c "from src.utils.database import init_database; init_database()"
```

This creates `data/trades.db` with the necessary tables.

## Usage

### Step 1: Update Earnings Calendar

Edit `data/earnings_calendar.csv` to add today's earnings reports:

```csv
date,ticker,company_name
2026-02-13,VOLV-B.ST,Volvo AB
2026-02-13,ERIC-B.ST,Ericsson
```

**Important Notes:**
- **Ticker is the primary identifier** - must match Yahoo Finance format exactly
- Company name is for display only (can be anything)
- Use `.ST` suffix for Swedish stocks (e.g., `VOLV-B.ST`)
- Optional: Add `report_time` column if you want to track timing

### Step 2: Run the Screener

```bash
python scripts/run_screener.py
```

This will:
1. Load today's earnings calendar
2. Fetch historical data for each ticker
3. Apply momentum filter (3M + 1Y + SMA200)
4. Display results in terminal
5. Save to database

**Expected Output:**
```
================================================================================
SVEA SURVEILLANCE - STOCK SCREENER
Date: 2026-02-13
================================================================================

✓ Found 2 stocks passing momentum filter:

Rank   Ticker       Company                   Score    3M         1Y
--------------------------------------------------------------------------------
1      VOLV-B.ST    Volvo AB                  85       +12.5%     +18.3%
2      ERIC-B.ST    Ericsson                  72       +6.2%      +11.7%

--------------------------------------------------------------------------------
Summary:
  - Average Score: 78.5
  - Average 3M Return: +9.4%
  - Average 1Y Return: +15.0%
  - Score Range: 72-85

================================================================================
✓ Results saved to database
✓ View in web UI: http://localhost:5000/watchlist
================================================================================
```

### Step 3: Start Web Dashboard

In a new terminal window (keep the same virtual environment active):

```bash
python scripts/run_app.py
```

**Expected Output:**
```
================================================================================
SVEA SURVEILLANCE - WEB DASHBOARD
================================================================================

✓ Starting web server...
  - Host: 127.0.0.1
  - Port: 5000
  - Debug: True

✓ Dashboard URL: http://127.0.0.1:5000/

Available pages:
  - Dashboard:  http://127.0.0.1:5000/
  - Watchlist:  http://127.0.0.1:5000/watchlist
  - Signals:    http://127.0.0.1:5000/signals
  - History:    http://127.0.0.1:5000/history

✓ Press Ctrl+C to stop the server
================================================================================
```

### Step 4: Open Web Browser

Navigate to: **http://localhost:5000**

You should see:
- **Dashboard** - Overview with today's watchlist count
- **Watchlist** - Table of stocks that passed the filter with scores and momentum metrics
- **Signals** - Placeholder (Phase 4 feature)
- **History** - Placeholder (Phase 6 feature)

## Testing with Real Data

To test with real Swedish stocks, add these to `data/earnings_calendar.csv`:

```csv
date,ticker,company_name
2026-02-13,VOLV-B.ST,Volvo AB
2026-02-13,ERIC-B.ST,Ericsson
2026-02-13,HM-B.ST,H&M
2026-02-13,SEB-A.ST,SEB Bank
2026-02-13,ABB.ST,ABB
```

Then run the screener again:
```bash
python scripts/run_screener.py
```

## Troubleshooting

### "No module named 'src'" Error

**Solution:** Make sure you're running scripts from the project root directory:
```bash
cd svea-surveillance
python scripts/run_screener.py
```

### Empty Watchlist

**Possible Causes:**
1. No earnings reports in CSV for today
2. All stocks failed momentum filter
3. Incorrect ticker symbols

**Solution:**
- Check `data/earnings_calendar.csv` has entries for today's date
- Verify ticker format (e.g., `VOLV-B.ST` not `VOLV-B`)
- Test with known large-cap Swedish stocks first

### "Ticker Not Found" Errors

**Solution:** Verify tickers on Yahoo Finance:
- Visit https://finance.yahoo.com
- Search for the stock
- Use the exact ticker symbol shown (including `.ST`)

### Port 5000 Already in Use

**Solution:** Run on a different port:
```bash
python scripts/run_app.py --port 5001
```

## Daily Workflow

1. **Sunday Evening:** Update earnings calendar for upcoming week
2. **08:00 CET:** Run screener before market opens
3. **08:15 CET:** Review watchlist in web UI
4. **09:00 CET:** Market opens - manual monitoring (Phase 3 will automate)
5. **09:30-09:45:** Look for entry opportunities (manual for now)

## Next Steps

After validating Phase 1 works:

- **Phase 2:** UI improvements (already integrated)
- **Phase 3:** Implement live monitoring and VWAP calculations
- **Phase 4:** Signal detection and risk management
- **Phase 5:** Backtesting engine
- **Phase 6:** Automation and polish

## Configuration

To customize settings, edit `config/config.yaml`:

```yaml
risk:
  account_value: 100000  # Change your account size
  risk_per_trade: 0.01   # Change risk percentage

screening:
  min_trend_score: 60    # Minimum score to pass filter
```

## Getting Help

- Check logs: `logs/svea_surveillance.log`
- Read full documentation: `README.md`
- Review implementation plan (provided separately)

## Important Reminders

⚠️ **Data Limitations:**
- yfinance has 15+ minute delays
- Data may be stale or have gaps
- NOT suitable for precise real-time trading

⚠️ **Strategy Validation:**
- Pattern is unproven - needs backtesting
- Paper trade before risking real money
- Consider upgrading to real-time data provider

⚠️ **Manual Execution:**
- You must execute trades manually in Avanza
- 13-45 second lag expected
- This is a validation tool, not production system

---

**You're now ready to start screening stocks!**

Run the screener daily before market opens to identify high-quality earnings day trading candidates.
