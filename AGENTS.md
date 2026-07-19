# Swedish Stock Earnings Predictor - Day Trading Guide

This document provides a consolidated technical, operational, and architectural reference for developing, maintaining, and operating the **Swedish Stock Earnings Predictor**.

---

## 1. System Overview & Important Disclaimers

The **Swedish Stock Earnings Predictor** is an automated Swedish stock market earnings day trading platform. It screens candidates pre-market, monitors intraday price action, detects entry signals, logs paper/hypothetical trades, and displays performance metrics via a Flask web dashboard.

### ⚠️ Critical Disclaimers & Operational Limits
1. **Data Delay:** `yfinance` data features a 15+ minute delay. It is not real-time tick data.
2. **Execution Latency:** Manual execution lag (15–45 seconds) or wide small-cap bid/ask spreads can erode strategy edge.
3. **Validation Required:** Always paper trade for a minimum of 20 trading days or 10 completed trades before risking real capital.
4. **Data Age Limits:** Signals generated on data >90 seconds old should generally be skipped.

---

## 2. Project Architecture & Database Schema

```
Tradeit/
├── src/
│   ├── backtesting/          # Backtest engine, strategy simulator, metrics
│   ├── data/                 # Data fetching (yfinance abstraction layer)
│   ├── screening/            # Pre-market momentum filters
│   ├── monitoring/           # Live monitoring & VWAP calculations
│   ├── risk/                 # Risk management & position sizing
│   ├── ui/                   # Flask web dashboard (routes & templates)
│   └── utils/                # Database setup, logger, scheduler, cleanup
├── data/
│   ├── all_tickers.txt       # Swedish stock ticker list (Yahoo format, e.g., VOLV-B.ST)
│   ├── earnings_calendar.csv # Daily earnings calendar (date, ticker, company_name)
│   ├── trades.db             # Main SQLite database
│   └── paper_trades.db       # Paper trading logs database
├── config/
│   └── config.yaml           # System parameters & screening configuration
├── scripts/
│   ├── run_with_scheduler.py # Main production runner (Web UI + APScheduler)
│   ├── run_screener.py       # Pre-market screening CLI
│   ├── run_paper_trading.py  # Standalone paper trading monitor CLI
│   ├── paper_trading_dashboard.py # Interactive paper trading dashboard CLI
│   ├── compare_focused.py    # Backtest validation script (28 high-quality stocks)
│   ├── verify_setup.py       # Diagnostic system setup checker
│   ├── extract_earnings_intraday_data.py # Intraday earnings data fetcher
│   ├── plot_earnings_subset.py # Standalone matplotlib plotting script
│   └── grid_search_earnings.py # Fundamental filter grid search engine
└── logs/
    └── earnings_predictor.log # Operational log file
```

### Database Schema (`data/trades.db` & `data/paper_trades.db`)

- `watchlist`: Daily screened candidates (`date`, `ticker`, `score`, `trend_3m`, `trend_1y`, `sma200`, `passed_filter`).
- `signals`: Intraday entry signals (`date`, `ticker`, `entry_price`, `vwap`, `open_price`, `prev_close`, `confidence_score`, `data_age_seconds`).
- `trades`: Executed manual/paper trades (`ticker`, `entry_price`, `exit_price`, `entry_time`, `exit_time`, `pnl`, `pnl_pct`, `status`, `notes`).
- `hypothetical_trades`: Automated paper trades (`id`, `ticker`, `date`, `signal_id`, `entry_time`, `entry_price`, `exit_time`, `exit_price`, `pnl_percent`, `status`). Enforces `UNIQUE(ticker, date)`.
- `earnings_intraday_analysis`: 1-minute intraday prices for historical earnings analysis (`ticker`, `earnings_date`, `time_of_day`, `timestamp`, `price`, `normalized_price`, `base_price`, `passed_filter`).

---

## 3. Strategy Rules & Configuration

The production strategy configuration is optimized based on 2024 backtesting.

### A. Pre-Market Screener (08:00 CET)
1. Company reporting earnings today.
2. Price > 200-day Simple Moving Average (SMA).
3. Positive 3-month return (`require_both_momentum: true`).
4. Positive 1-year return.
5. Overall score ≥ 60.

### B. Earnings Surprise Filter ✅ (ENABLED)
- **Rule:** Only trade if `reported_eps > estimated_eps` (positive surprise).
- **Behavior:** Skips companies missing EPS estimates/reports or reporting negative surprises.

### C. Intraday Entry Signal (09:20 - 10:00 CET Window)
All four conditions must hold simultaneously:
1. `Price > VWAP` (Volume-Weighted Average Price)
2. `Price > Open Price`
3. `Price > Yesterday Close + 2%`
4. `Price > 5-minute average price` (Falling knife protection)

### D. Exit Rules
- **Fixed Stop-Loss:** -2.5% below entry price.
- **Market Close Exit:** Exit at 17:00 CET if stop loss is not triggered.
- **Trailing Stop:** ❌ **DISABLED** (Backtests showed trailing stops cut winners early during earnings day volatility).

### E. Risk Management & Position Sizing
- **Account Capital:** 100,000 SEK
- **Risk Per Trade:** 1% of account balance (1,000 SEK)
- **Position Size Formula:**
  $$\text{Shares} = \frac{\text{Account Value} \times 0.01}{\text{Entry Price} \times 0.025}$$
- **Daily Constraints:** Max 3 positions per day, max 3% total daily drawdown limit (-3,000 SEK).

---

## 4. Environment & Installation

### Setup Steps
```bash
# 1. Activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy environment file (if applicable)
cp .env.example .env

# 4. Initialize database schemas
python -c "from src.utils.database import init_database; init_database()"

# 5. Run diagnostic verification
python scripts/verify_setup.py
```

---

## 5. Daily Workflows & CLI Commands

### Automated Daily Production Server
To run both the Flask Web UI and the automated APScheduler background process:
```bash
python scripts/run_with_scheduler.py
```
- Available flags:
  - `--host 0.0.0.0` (bind to all interfaces)
  - `--port 5000` (custom port)
  - `--debug` (enable auto-reload)
  - `--no-scheduler` (disable background jobs, run UI only)

- Web Dashboard URL: `http://localhost:5000`
  - `/` Overview dashboard
  - `/watchlist` Today's watchlist
  - `/signals` Live entry signals
  - `/history` Hypothetical/paper trading performance
  - `/earnings-analysis` Intraday earnings movement & ROI calculator

### Manual CLI Workflow
1. **Update Earnings Calendar:** Add today's earnings to `data/earnings_calendar.csv`:
   ```csv
   date,ticker,company_name
   2026-02-13,VOLV-B.ST,Volvo AB
   ```
2. **Run Screener:**
   ```bash
   python scripts/run_screener.py
   ```
3. **Start Live Monitor:**
   ```bash
   python scripts/run_paper_trading.py
   ```
4. **Manage Paper Trading Outcomes:**
   ```bash
   python scripts/paper_trading_dashboard.py
   ```

---

## 6. Daily Automation & Late-Start Catch-Up

### Automated Daily Timeline (`src/utils/scheduler.py`, Timezone: `Europe/Stockholm`)
- **08:30 CET:** Morning Screener runs automatically.
- **09:00 CET:** Live Monitor starts in background (monitors until 10:30 CET).
- **17:00 CET:** Closes open hypothetical trades at current market price.
- **17:30 CET:** Daily cleanup removes old watchlist & signal rows, keeping historical intraday records.

### Smart Catch-Up Feature
If `run_with_scheduler.py` is started late during the day, it automatically evaluates missed jobs:
- **Started 08:30–17:30:** Runs morning screener immediately if watchlist is empty.
- **Started 09:00–10:00:** Starts live monitor immediately for remaining time until 10:30.
- **Started 17:00–17:30:** Closes any open trades immediately.
- **Started after 17:30:** Runs daily cleanup immediately.

---

## 7. Paper Trading & Validation Criteria

Before deploying capital, paper trade to validate execution speed, data freshness, and discipline.

### Minimum Duration & Benchmarks
- **Required Period:** At least 20 trading days **OR** 10 completed trades.
- **Target Win Rate:** 45% – 65% (Backtest baseline: 54.5%).
- **Target Profit Factor:** > 2.0 (Backtest baseline: 4.89).
- **Freshness Benchmark:** >70% of signals executed on data age <90s.

### Transitioning to Live Trading
1. Start with **0.5% risk** per trade (500 SEK on 100k account) for the first 10 trades.
2. Scale up to **1% risk** per trade (1,000 SEK) after verifying execution latency (<60s).

---

## 8. Advanced Features & Utility Tools

### Backtesting & Strategy Validation
```bash
# Run 28-stock backtest validation
python scripts/compare_focused.py
```
Programmatic usage:
```python
from src.backtesting.backtest_engine import BacktestEngine

engine = BacktestEngine(
    use_earnings_surprise_filter=True,
    use_trailing_stop=False
)
results = engine.run_backtest(
    tickers=['VOLV-B.ST', 'ERIC-B.ST'],
    start_date='2024-01-01',
    end_date='2024-12-31'
)
print(f"Win Rate: {results['win_rate']:.1f}%, Profit Factor: {results['profit_factor']:.2f}")
```

### Multi-Day Historical Replay
If the application is offline for up to 4 weeks (28 days), starting the scheduler will automatically run a multi-day historical replay backtest during the 17:30 maintenance window to reconstruct missed watchlists, signals, and hypothetical trades.

### Intraday Earnings Data Extraction & Per-Stock ROI
- **Data Extractor:**
  ```bash
  python scripts/extract_earnings_intraday_data.py --start YYYY-MM-DD --end YYYY-MM-DD --max-tickers 100
  ```
  *Note:* `yfinance` only provides 1-minute resolution data for the past 30 days. Extracted intraday data persists permanently in SQLite.
- **Per-Stock ROI & 1% Early Exit Analysis:**
  Access `http://localhost:5000/earnings-analysis` to view per-stock ROI estimates and compare holding until market close vs exiting early at +1% profit. API endpoint:
  `/api/calculate-roi?purchase_time=09:30&sell_time=14:00&categories=all,filter,signal`

### Matplotlib Visualization Script
```bash
python scripts/plot_earnings_subset.py --min-gain 2.0 --start 09:00 --end 09:10 --save early_gainers.png
```

### Grid Search Fundamental Filters
Test fundamental filters (52-week high range position, liquidity score, 20-day volatility, 252-day momentum, trailing P/E ratio):
```bash
python scripts/grid_search_earnings.py
```

---

## 9. Troubleshooting & Diagnostics

- **Diagnostic Check:** Run `python scripts/verify_setup.py` to test imports, config settings, database schemas, and backtesting capability.
- **Stale Data Warnings:** If logs warn of data age >120 seconds, `yfinance` rate limits or delayed quotes are occurring. Skip trading signals during high latency.
- **Database Inspection:**
  ```bash
  sqlite3 data/trades.db ".tables"
  ```
- **Log Inspection:**
  ```bash
  tail -f logs/earnings_predictor.log
  ```
