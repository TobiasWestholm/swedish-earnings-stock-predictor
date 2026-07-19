# Swedish Stock Earnings Predictor

An automated Swedish stock market earnings day trading platform. This system screens candidate stocks pre-market, monitors intraday price action, detects entry signals, logs paper/hypothetical trades, and displays performance metrics via an interactive Flask dashboard.

---

## ⚠️ Important Disclaimers & Limits

1. **Data Delay:** Default market data fetched via `yfinance` has a 15+ minute delay and is not real-time tick data.
2. **Execution Latency:** Expect a manual execution lag of 15–45 seconds. Wide small-cap bid/ask spreads can erode strategy edge.
3. **Paper Trading Requirement:** Always paper trade for at least 20 trading days or 10 completed trades before risking real capital.
4. **Data Age Limit:** Signals generated on data >90 seconds old should generally be skipped.

---

## Core Strategy Features

- **Pre-Market Screener:** Filters stocks reporting earnings today based on 3-month momentum, 1-year momentum, and 200-day SMA.
- **Earnings Surprise Filter:** Trades only positive earnings surprises (`reported_eps > estimated_eps`).
- **Intraday Signal Window (09:20 - 10:00 CET):** Entry signals fire when price concurrently beats VWAP, the day's open price, yesterday's close + 2%, and a 5-minute average price (falling knife protection).
- **Exit Logic:** Fixed stop-loss of -2.5% or exit at market close (17:00 CET).
- **Position Sizing:** Position sizes calculated dynamically to risk exactly 1% of account capital per trade.
- **Downtime Catch-up & Historical Replay:** Reconstructs watchlists, signals, and hypothetical trades retroactively for up to 28 days of downtime.
- **Interactive ROI Calculator:** Visualizes per-stock ROI estimates and compares holding to close against a 1% early profit target exit strategy.

---

## Quick Start

### 1. Setup Environment
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize database schemas
python -c "from src.utils.database import init_database; init_database()"
```

### 2. Run Diagnostics
```bash
python scripts/verify_setup.py
```

### 3. Run Production Server (Web Dashboard + Scheduler)
```bash
python scripts/run_with_scheduler.py
```
Access the dashboard at: [http://localhost:5000](http://localhost:5000)

- **08:30 CET:** Morning screener runs automatically.
- **09:00 CET:** Live Monitor starts in background (monitors until 10:30 CET).
- **17:00 CET:** Closes open hypothetical trades at current market price.
- **17:30 CET:** Daily database maintenance runs.

---

## Documentation

For a comprehensive guide on strategy configuration, database schemas, advanced tools, daily manual workflows, and paper trading benchmarks, please refer to the main documentation:

- 📄 **[AGENTS.md](AGENTS.md)** - Technical developer, agent, and operator guide.
