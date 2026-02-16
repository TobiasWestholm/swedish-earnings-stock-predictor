# Svea Surveillance - Swedish Stock Earnings Day Trading

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status](https://img.shields.io/badge/Status-Paper%20Trading-orange.svg)](https://github.com)

**Status:** ✅ Backtest Complete | 📝 Paper Trading Phase | ⏳ Ready for Validation

A Swedish stock market earnings day trading system with validated backtest results. Currently in paper trading phase to validate strategy performance before live trading.

## Table of Contents

- [Important Disclaimers](#️-important-disclaimers)
- [Strategy Overview](#strategy-overview)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Development Status](#development-status)
- [Documentation](#documentation)
- [Data Quality](#data-quality)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## ⚠️ Important Disclaimers

**Critical Limitations:**
1. yfinance data has 15+ minute delays - NOT suitable for precise 9:30 entries in production
2. The 9:30-9:45 "dip" pattern is unproven and may not provide an edge
3. Manual execution lag (13-45 seconds) may miss optimal entries
4. Swedish small-caps have wide spreads - slippage can eliminate edge
5. This is a validation tool, NOT a production trading system

**Before Live Trading:**
- Complete backtest with positive results
- Paper trade for 1 month minimum
- Test with small position sizes first
- Have clear exit rules and discipline
- Consider upgrading to real-time data provider

## Strategy Overview

**Validated Configuration (2024 Backtest):**
- ✅ **Earnings Surprise Filter:** ENABLED (only trade when reported EPS > estimated EPS)
- ❌ **Trailing Stop:** DISABLED (reduced profits by 66% in backtest)

### Pre-Market Filter
1. Stock reporting earnings today
2. Price above 200-day SMA
3. 3-month return positive
4. 1-year return positive
5. Reported EPS beats estimate (earnings surprise)

### Entry Signal (09:20-10:00 CET)
- Price > VWAP (volume-weighted average price)
- Price > Open
- Price > Yesterday Close + 2%
- Price > 5-minute average price (no falling knife protection)

### Exit Strategy
- Fixed stop-loss: -2.5% from entry
- Exit at market close if stop not hit
- NO trailing stop (disabled based on backtest results)

### Risk Management
- Account: 100,000 SEK
- Risk per trade: 1% (1,000 SEK)
- Position sizing: Based on stop-loss distance
- Max 3 positions per day
- Max 3% daily loss limit

### Backtest Results (28 Stocks, 2024)
- **Trades:** 11 (selective, high quality)
- **Win Rate:** 54.5%
- **Total P&L:** +49.98 SEK
- **Avg P&L:** +4.54 SEK
- **Profit Factor:** 4.89 (excellent)

See `STRATEGY_CONFIGURATION.md` for complete details.

## Project Structure

```
svea-surveillance/
├── src/
│   ├── backtesting/           # ✅ Strategy validation & paper trading
│   │   ├── backtest_engine.py
│   │   ├── strategy_simulator.py
│   │   ├── paper_trading_tracker.py  # 🆕 Paper trading logger
│   │   └── metrics.py
│   ├── data/                  # ✅ Data fetching (yfinance)
│   ├── screening/             # ✅ Pre-market filtering
│   ├── monitoring/            # ✅ Live monitoring & signals
│   ├── risk/                  # Position sizing
│   ├── ui/                    # ✅ Flask web dashboard
│   └── utils/                 # Config, logging, database
├── data/
│   ├── all_tickers.txt        # 544 Swedish stocks
│   ├── trades.db              # Main database
│   └── paper_trades.db        # 🆕 Paper trading records
├── config/
│   └── config.yaml            # Main configuration
├── scripts/
│   ├── compare_focused.py     # ✅ Validated backtest (28 stocks)
│   ├── run_screener.py        # Pre-market scan
│   ├── run_paper_trading.py   # 🆕 Paper trading monitor
│   ├── paper_trading_dashboard.py  # 🆕 Review & log outcomes
│   └── verify_setup.py        # 🆕 System verification
├── docs/
│   ├── STRATEGY_CONFIGURATION.md   # 📄 Production config
│   ├── QUICK_START.md              # 📄 Getting started
│   ├── PAPER_TRADING_GUIDE.md      # 📄 Paper trading workflow
│   └── EARNINGS_SURPRISE_ANALYSIS.md
└── logs/                      # Application logs
```

## Installation

### Prerequisites
- Python 3.9 or higher
- pip
- Virtual environment (recommended)

### Setup

1. **Clone the repository:**
```bash
git clone <repository-url>
cd svea-surveillance
```

2. **Create and activate virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate  # On Windows
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Set up configuration:**
```bash
cp .env.example .env
# Edit .env if needed (default values work for testing)
```

5. **Initialize database:**
```bash
python -c "from src.utils.database import init_database; init_database()"
```

## Quick Start

### 1. Verify Setup
```bash
python scripts/verify_setup.py
```

This checks:
- All dependencies installed
- Database schemas created
- Production configuration correct
- Backtest capability working

### 2. Validate Configuration (Optional)
```bash
# Run backtest on 28 high-quality stocks (2024)
python scripts/compare_focused.py
```

Expected results:
- 11 trades with earnings surprise filter
- 54.5% win rate
- 4.89 profit factor

### 3. Paper Trading (REQUIRED Before Live Trading)

**Daily Workflow:**

#### Morning (08:00 CET)
```bash
# Run pre-market screener
python scripts/run_screener.py
```

#### Intraday (09:00-14:30 CET)
```bash
# Start paper trading monitor
# Automatically logs all signals to database
python scripts/run_paper_trading.py
```

#### End of Day (17:00+ CET)
```bash
# Review signals and log outcomes
python scripts/paper_trading_dashboard.py
```

**Dashboard Options:**
1. View today's signals
2. View pending outcomes
3. Log trade outcome
4. Mark signal as executed
5. Mark signal as skipped
6. View summary (all time)
7. View summary (last 7 days)
8. View summary (last 30 days)
9. Compare to backtest expectations
10. Export signals to CSV

**Paper Trading Duration:** Minimum 20 trading days OR 10 completed trades

See `PAPER_TRADING_GUIDE.md` for complete workflow and best practices.

### 4. Web Dashboard (Optional)

```bash
python scripts/run_app.py
```

Open browser to: http://localhost:5000

**Available Views:**
- `/` - Dashboard overview
- `/watchlist` - Pre-market scan results
- `/signals` - Live entry signals

## Configuration

Edit `config/config.yaml` to customize:

```yaml
screening:
  momentum_lookback_3m: 63  # trading days
  momentum_lookback_1y: 252
  sma_period: 200
  require_both_momentum: true  # Both 3M AND 1Y must be positive
  min_trend_score: 60

risk:
  account_value: 100000  # SEK
  risk_per_trade: 0.01  # 1%
  default_stop_loss_pct: 0.025  # 2.5%
  max_positions_per_day: 3
```

## Development Status

- **Phase 1** ✅ Static Screener: Complete
- **Phase 2** ✅ Basic Web UI: Complete
- **Phase 3** ✅ Live Monitoring: Complete
- **Phase 4** ✅ Signal Detection: Complete
- **Phase 5** ✅ Backtesting Engine: Complete & Validated
- **Phase 6** 🔄 Paper Trading: In Progress
- **Phase 7** ⏳ Live Trading: Pending paper trading validation

## Documentation

**Essential Reads:**
- `QUICK_START.md` - Get started quickly with backtesting
- `PAPER_TRADING_GUIDE.md` - Complete paper trading workflow (READ THIS FIRST)
- `STRATEGY_CONFIGURATION.md` - Production strategy rules and backtest results

**Technical Details:**
- `EARNINGS_SURPRISE_ANALYSIS.md` - Data availability study (92.8% coverage)
- `IMPROVEMENTS_SUMMARY.md` - Implementation timeline
- `TRADE_ANALYSIS.md` - Original 544-stock backtest analysis

## Data Quality

**yfinance Limitations:**
- 15+ minute delays (not real-time)
- Data gaps on volatile days
- Unreliable for Swedish stocks sometimes
- API rate limits on rapid polling

**Quality Indicators:**
- Data age warnings when >120 seconds old
- Quality scores for each stock
- Staleness alerts in UI

**Upgrade Path:**
- Abstract data layer allows swapping providers
- Future options: Nasdaq Nordic API, EODHD, Interactive Brokers

## Database Schema

SQLite database at `data/trades.db`:

**Tables:**
- `watchlist` - Daily screened stocks
- `signals` - Entry signals (Phase 4)
- `trades` - Executed trades (manual logging)

## Logging

Logs saved to `logs/svea_surveillance.log`

**Log levels:**
- INFO: Normal operations
- WARNING: Data quality issues
- ERROR: Critical failures

## Testing

```bash
# Run unit tests (when implemented)
pytest tests/

# Test screener with sample data
python scripts/run_screener.py
```

## Troubleshooting

### Common Issues

**"No signals detected after 1 week"**
- Normal - strategy is selective (11 trades/year on 28 stocks)
- Check screener is finding earnings days
- Verify stocks pass momentum filter
- Earnings surprise filter reduces signals by 50%

**"Win rate much lower than backtest (30-40%)"**
- Check execution delay (<60 seconds target)
- Verify data age (<90 seconds)
- Review slippage on entries
- Continue paper trading to build sample size

**"Backtest shows 0 trades"**
- Check date range (use 2024 data)
- Verify configuration:
  - `use_earnings_surprise_filter=True`
  - `use_trailing_stop=False`
- Some tickers may lack historical earnings data

**"Data too stale (>90 seconds)"**
- yfinance limitation on volatile days
- Skip signals with stale data
- Consider real-time data provider for live trading

For more troubleshooting, see:
- `QUICK_START.md` - Common issues section
- `PAPER_TRADING_GUIDE.md` - Execution problems

## License

MIT License - Use at your own risk.

**Disclaimer:** This software is for educational and research purposes. Trading involves substantial risk of loss. Past performance does not guarantee future results.

## Current Focus: Paper Trading

The strategy has been backtested and validated on 2024 data. The immediate next step is **paper trading** to:

1. ✅ Verify backtest results hold in real-time conditions
2. ✅ Test execution speed and discipline
3. ✅ Identify data quality issues
4. ✅ Build confidence before risking capital

**Do NOT skip paper trading.** Minimum 20 trading days or 10 completed trades required.

---

## Performance Expectations

Based on 2024 backtest (28 stocks):
- **Trade Frequency:** ~11 trades per year
- **Win Rate:** 50-60%
- **Avg Profit per Trade:** ~4.5 SEK
- **Profit Factor:** 4-5x
- **Risk per Trade:** 1% of account (1,000 SEK)

Scaling to 100 stocks: ~40 trades/year, ~180 SEK annual profit

---

**⚠️ Important:** This system is validated through backtesting but requires paper trading before live trading. Always understand the risks and start with small positions when going live.
