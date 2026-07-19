"""Database utilities for Earnings Predictor."""

import sqlite3
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def get_db_path() -> str:
    """Get the database path from config or use default."""
    from src.utils.config import load_config
    config = load_config()
    return config.get('database', {}).get('path', 'data/trades.db')


def get_connection() -> sqlite3.Connection:
    """Create a database connection."""
    db_path = get_db_path()

    # Ensure directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn


def init_database():
    """Initialize database with required schema."""
    conn = get_connection()
    cursor = conn.cursor()

    # Watchlist table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT,
            trend_score REAL,
            report_time TEXT,
            sma_200 REAL,
            current_price REAL,
            yesterday_close REAL,
            return_3m REAL,
            return_1y REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, ticker)
        )
    """)

    # Migration: Add yesterday_close column if it doesn't exist
    try:
        cursor.execute("SELECT yesterday_close FROM watchlist LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Adding yesterday_close column to watchlist table")
        cursor.execute("ALTER TABLE watchlist ADD COLUMN yesterday_close REAL")

    # Signals table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            signal_time TIMESTAMP NOT NULL,
            entry_price REAL NOT NULL,
            vwap REAL,
            open_price REAL,
            yesterday_close REAL,
            pct_from_yesterday REAL,
            data_age_seconds INTEGER,
            conditions TEXT,  -- JSON string
            confidence_score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migration: Add yesterday_close and pct_from_yesterday columns if they don't exist
    try:
        cursor.execute("SELECT yesterday_close FROM signals LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Adding yesterday_close column to signals table")
        cursor.execute("ALTER TABLE signals ADD COLUMN yesterday_close REAL")

    try:
        cursor.execute("SELECT pct_from_yesterday FROM signals LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Adding pct_from_yesterday column to signals table")
        cursor.execute("ALTER TABLE signals ADD COLUMN pct_from_yesterday REAL")

    # Trades table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id INTEGER,
            ticker TEXT NOT NULL,
            entry_time TIMESTAMP NOT NULL,
            entry_price REAL NOT NULL,
            shares INTEGER NOT NULL,
            exit_time TIMESTAMP,
            exit_price REAL,
            pnl REAL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (signal_id) REFERENCES signals(id)
        )
    """)

    # Intraday data table (Phase 3)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS intraday_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            date DATE NOT NULL,
            open_price REAL,
            current_price REAL,
            high REAL,
            low REAL,
            volume INTEGER,
            vwap REAL,
            data_age_seconds INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, timestamp)
        )
    """)

    # Hypothetical trades table (for paper trading results)
    # Check if table needs migration for strategy support
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='hypothetical_trades'
    """)
    table_exists = cursor.fetchone() is not None

    if table_exists:
        # Check if strategy_type column exists
        cursor.execute("PRAGMA table_info(hypothetical_trades)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'strategy_type' not in columns:
            logger.info("Migrating hypothetical_trades table for strategy support")

            # Create new table with strategy support
            cursor.execute("""
                CREATE TABLE hypothetical_trades_new (
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
                    strategy_type TEXT DEFAULT 'eod',
                    profit_target_pct REAL,
                    exit_reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (signal_id) REFERENCES signals(id),
                    UNIQUE(ticker, date, strategy_type)
                )
            """)

            # Copy existing data with strategy_type='eod'
            cursor.execute("""
                INSERT INTO hypothetical_trades_new
                (id, ticker, date, signal_id, entry_time, entry_price,
                 exit_time, exit_price, pnl_percent, status, strategy_type, created_at)
                SELECT id, ticker, date, signal_id, entry_time, entry_price,
                       exit_time, exit_price, pnl_percent, status, 'eod', created_at
                FROM hypothetical_trades
            """)

            # Drop old table and rename new one
            cursor.execute("DROP TABLE hypothetical_trades")
            cursor.execute("ALTER TABLE hypothetical_trades_new RENAME TO hypothetical_trades")

            logger.info("Migration completed successfully")
    else:
        # Create new table with strategy support from scratch
        cursor.execute("""
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
                strategy_type TEXT DEFAULT 'eod',
                profit_target_pct REAL,
                exit_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (signal_id) REFERENCES signals(id),
                UNIQUE(ticker, date, strategy_type)
            )
        """)

    # Earnings intraday analysis table (for historical analysis)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS earnings_intraday_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            earnings_date DATE NOT NULL,
            time_of_day TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            price REAL NOT NULL,
            normalized_price REAL NOT NULL,
            base_price REAL NOT NULL,
            filter_score REAL DEFAULT 0.0,
            passed_filter INTEGER DEFAULT 0,
            created_signal INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, earnings_date, time_of_day)
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_date ON watchlist(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_time ON signals(signal_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_entry ON trades(entry_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_intraday_ticker_date ON intraday_data(ticker, date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_intraday_timestamp ON intraday_data(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_hypothetical_date ON hypothetical_trades(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_hypothetical_ticker_date ON hypothetical_trades(ticker, date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_hypothetical_strategy ON hypothetical_trades(strategy_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_earnings_analysis_date ON earnings_intraday_analysis(earnings_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_earnings_analysis_ticker_date ON earnings_intraday_analysis(ticker, earnings_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_earnings_analysis_filter ON earnings_intraday_analysis(passed_filter, created_signal)")

    conn.commit()
    conn.close()

    logger.info("Database initialized successfully")


def save_watchlist(stocks: List[Dict[str, Any]], date: str) -> int:
    """
    Save watchlist stocks to database.

    Args:
        stocks: List of stock dictionaries with screening results
        date: Date string (YYYY-MM-DD)

    Returns:
        Number of stocks saved
    """
    conn = get_connection()
    cursor = conn.cursor()

    saved_count = 0
    for stock in stocks:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO watchlist
                (date, ticker, name, trend_score, report_time, sma_200,
                 current_price, yesterday_close, return_3m, return_1y)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date,
                stock['ticker'],
                stock.get('name'),
                stock.get('trend_score'),
                stock.get('report_time'),
                stock.get('sma_200'),
                stock.get('current_price'),
                stock.get('yesterday_close'),
                stock.get('return_3m'),
                stock.get('return_1y')
            ))
            saved_count += 1
        except Exception as e:
            logger.error(f"Error saving {stock.get('ticker')}: {e}")

    conn.commit()
    conn.close()

    logger.info(f"Saved {saved_count} stocks to watchlist for {date}")
    return saved_count


def get_watchlist(date: str) -> List[Dict[str, Any]]:
    """
    Get watchlist for a specific date.

    Args:
        date: Date string (YYYY-MM-DD)

    Returns:
        List of stock dictionaries
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM watchlist
        WHERE date = ?
        ORDER BY trend_score DESC
    """, (date,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def save_signal(signal_data: Dict[str, Any]) -> int:
    """
    Save a trading signal to database.

    Args:
        signal_data: Dictionary containing signal information

    Returns:
        Signal ID
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Convert conditions dict to JSON string
    conditions_json = json.dumps(signal_data.get('conditions', {}))

    cursor.execute("""
        INSERT INTO signals
        (ticker, signal_time, entry_price, vwap, open_price,
         yesterday_close, pct_from_yesterday,
         data_age_seconds, conditions, confidence_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        signal_data['ticker'],
        signal_data['signal_time'],
        signal_data['entry_price'],
        signal_data.get('vwap'),
        signal_data.get('open_price'),
        signal_data.get('yesterday_close'),
        signal_data.get('pct_from_yesterday'),
        signal_data.get('data_age_seconds'),
        conditions_json,
        signal_data.get('confidence_score')
    ))

    signal_id = cursor.lastrowid
    conn.commit()
    conn.close()

    logger.info(f"Saved signal for {signal_data['ticker']} at {signal_data['signal_time']}")
    return signal_id


def get_signals(date: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get trading signals, optionally filtered by date.
    Returns only the latest signal per ticker.

    Args:
        date: Optional date string (YYYY-MM-DD)
        limit: Maximum number of signals to return

    Returns:
        List of signal dictionaries (one per ticker, most recent only)
    """
    conn = get_connection()
    cursor = conn.cursor()

    if date:
        # Get latest signal per ticker for specified date
        cursor.execute("""
            SELECT s.* FROM signals s
            INNER JOIN (
                SELECT ticker, MAX(signal_time) as max_time
                FROM signals
                WHERE DATE(signal_time) = ?
                GROUP BY ticker
            ) latest ON s.ticker = latest.ticker AND s.signal_time = latest.max_time
            ORDER BY s.signal_time DESC
            LIMIT ?
        """, (date, limit))
    else:
        # Get latest signal per ticker (all time)
        cursor.execute("""
            SELECT s.* FROM signals s
            INNER JOIN (
                SELECT ticker, MAX(signal_time) as max_time
                FROM signals
                GROUP BY ticker
            ) latest ON s.ticker = latest.ticker AND s.signal_time = latest.max_time
            ORDER BY s.signal_time DESC
            LIMIT ?
        """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    signals = []
    for row in rows:
        signal = dict(row)
        # Parse JSON conditions
        if signal.get('conditions'):
            try:
                signal['conditions'] = json.loads(signal['conditions'])
            except:
                signal['conditions'] = {}
        signals.append(signal)

    return signals


def save_trade(trade_data: Dict[str, Any]) -> int:
    """
    Save a trade to database.

    Args:
        trade_data: Dictionary containing trade information

    Returns:
        Trade ID
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO trades
        (signal_id, ticker, entry_time, entry_price, shares,
         exit_time, exit_price, pnl, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        trade_data.get('signal_id'),
        trade_data['ticker'],
        trade_data['entry_time'],
        trade_data['entry_price'],
        trade_data['shares'],
        trade_data.get('exit_time'),
        trade_data.get('exit_price'),
        trade_data.get('pnl'),
        trade_data.get('notes')
    ))

    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()

    logger.info(f"Saved trade for {trade_data['ticker']}")
    return trade_id


def get_trades(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get trade history.

    Args:
        limit: Maximum number of trades to return

    Returns:
        List of trade dictionaries
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM trades
        ORDER BY entry_time DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def save_intraday_data(data: Dict[str, Any]) -> int:
    """
    Save intraday price data.

    Args:
        data: Dictionary with intraday data

    Returns:
        Row ID
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO intraday_data
        (ticker, timestamp, date, open_price, current_price, high, low,
         volume, vwap, data_age_seconds)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data['ticker'],
        data['timestamp'],
        data['date'],
        data.get('open_price'),
        data.get('current_price'),
        data.get('high'),
        data.get('low'),
        data.get('volume'),
        data.get('vwap'),
        data.get('data_age_seconds')
    ))

    row_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return row_id


def get_intraday_data(ticker: str, date: str) -> List[Dict[str, Any]]:
    """
    Get intraday data for a ticker on a specific date.

    Args:
        ticker: Stock ticker
        date: Date string (YYYY-MM-DD)

    Returns:
        List of intraday data points
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM intraday_data
        WHERE ticker = ? AND date = ?
        ORDER BY timestamp ASC
    """, (ticker, date))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_latest_intraday_data(date: str) -> List[Dict[str, Any]]:
    """
    Get latest intraday data for all tickers on a date.

    Args:
        date: Date string (YYYY-MM-DD)

    Returns:
        List of latest data points for each ticker
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT i1.*
        FROM intraday_data i1
        INNER JOIN (
            SELECT ticker, MAX(timestamp) as max_timestamp
            FROM intraday_data
            WHERE date = ?
            GROUP BY ticker
        ) i2 ON i1.ticker = i2.ticker AND i1.timestamp = i2.max_timestamp
        ORDER BY i1.ticker
    """, (date,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]

# Cleanup functions

def clear_old_watchlist(target_date: Optional[date] = None, keep_days: int = 0) -> int:
    """
    Clear watchlist entries for a specific date or older than keep_days.

    Args:
        target_date: Specific date to clear (if None, clears based on keep_days)
        keep_days: Number of days to keep (0 = clear all, 7 = keep last 7 days)

    Returns:
        Number of entries deleted
    """
    conn = get_connection()
    cursor = conn.cursor()

    if target_date:
        # Clear specific date
        cursor.execute("""
            DELETE FROM watchlist
            WHERE date = ?
        """, (target_date.strftime('%Y-%m-%d'),))

    elif keep_days > 0:
        # Clear entries older than keep_days
        cutoff_date = (date.today() - timedelta(days=keep_days)).strftime('%Y-%m-%d')
        cursor.execute("""
            DELETE FROM watchlist
            WHERE date < ?
        """, (cutoff_date,))

    else:
        # Clear all
        cursor.execute("DELETE FROM watchlist")

    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()

    logger.info(f"Cleared {deleted_count} watchlist entries")
    return deleted_count


def clear_old_signals(target_date: Optional[date] = None, keep_days: int = 0) -> int:
    """
    Clear signal entries for a specific date or older than keep_days.

    Args:
        target_date: Specific date to clear (if None, clears based on keep_days)
        keep_days: Number of days to keep (0 = clear all, 7 = keep last 7 days)

    Returns:
        Number of entries deleted
    """
    conn = get_connection()
    cursor = conn.cursor()

    if target_date:
        # Clear specific date
        cursor.execute("""
            DELETE FROM signals
            WHERE DATE(signal_time) = ?
        """, (target_date.strftime('%Y-%m-%d'),))

    elif keep_days > 0:
        # Clear entries older than keep_days
        cutoff_date = (date.today() - timedelta(days=keep_days)).strftime('%Y-%m-%d')
        cursor.execute("""
            DELETE FROM signals
            WHERE DATE(signal_time) < ?
        """, (cutoff_date,))

    else:
        # Clear all
        cursor.execute("DELETE FROM signals")

    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()

    logger.info(f"Cleared {deleted_count} signal entries")
    return deleted_count


def clear_old_intraday_data(keep_days: int = 1) -> int:
    """
    Clear intraday data older than keep_days.

    Args:
        keep_days: Number of days to keep (default: 1 = keep today only)

    Returns:
        Number of entries deleted
    """
    conn = get_connection()
    cursor = conn.cursor()

    cutoff_date = (date.today() - timedelta(days=keep_days)).strftime('%Y-%m-%d')

    cursor.execute("""
        DELETE FROM intraday_data
        WHERE date < ?
    """, (cutoff_date,))

    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()

    logger.info(f"Cleared {deleted_count} intraday data entries")
    return deleted_count


# Hypothetical trading functions

def create_hypothetical_trade(ticker: str, signal_id: int, entry_time: datetime,
                               entry_price: float, trade_date: date,
                               strategy_type: str = 'eod',
                               profit_target_pct: Optional[float] = None) -> Optional[int]:
    """
    Create a hypothetical trade entry (paper trading).
    Only creates if no trade exists for this ticker + strategy on this date.

    Args:
        ticker: Stock ticker
        signal_id: ID of the signal that triggered this trade
        entry_time: Entry timestamp
        entry_price: Entry price
        trade_date: Date of the trade
        strategy_type: Strategy type ('eod' or '1pct_target')
        profit_target_pct: Profit target percentage (for target-based strategies)

    Returns:
        Trade ID if created, None if already exists
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Check if trade already exists for this ticker + strategy today
    cursor.execute("""
        SELECT id FROM hypothetical_trades
        WHERE ticker = ? AND date = ? AND strategy_type = ?
    """, (ticker, trade_date.strftime('%Y-%m-%d'), strategy_type))

    existing = cursor.fetchone()
    if existing:
        conn.close()
        logger.debug(f"Hypothetical trade already exists for {ticker} ({strategy_type}) on {trade_date}")
        return None

    # Create new hypothetical trade
    cursor.execute("""
        INSERT INTO hypothetical_trades
        (ticker, date, signal_id, entry_time, entry_price, status,
         strategy_type, profit_target_pct)
        VALUES (?, ?, ?, ?, ?, 'open', ?, ?)
    """, (
        ticker,
        trade_date.strftime('%Y-%m-%d'),
        signal_id,
        entry_time.strftime('%Y-%m-%d %H:%M:%S'),
        entry_price,
        strategy_type,
        profit_target_pct
    ))

    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()

    logger.info(f"Created hypothetical trade for {ticker} ({strategy_type}) at {entry_price} SEK")
    return trade_id


def has_hypothetical_trade_today(ticker: str, trade_date: date,
                                  strategy_type: Optional[str] = None) -> bool:
    """
    Check if a hypothetical trade already exists for ticker on given date.

    Args:
        ticker: Stock ticker
        trade_date: Date to check
        strategy_type: Optional strategy type filter

    Returns:
        True if trade exists, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()

    if strategy_type:
        cursor.execute("""
            SELECT id FROM hypothetical_trades
            WHERE ticker = ? AND date = ? AND strategy_type = ?
        """, (ticker, trade_date.strftime('%Y-%m-%d'), strategy_type))
    else:
        cursor.execute("""
            SELECT id FROM hypothetical_trades
            WHERE ticker = ? AND date = ?
        """, (ticker, trade_date.strftime('%Y-%m-%d')))

    exists = cursor.fetchone() is not None
    conn.close()

    return exists


def close_hypothetical_trade(trade_id: int, exit_time: datetime, exit_price: float,
                              exit_reason: str = 'eod') -> bool:
    """
    Close a hypothetical trade with exit price and calculate P&L.

    Args:
        trade_id: ID of the trade to close
        exit_time: Exit timestamp
        exit_price: Exit price
        exit_reason: Reason for exit ('eod', 'profit_target', 'eod_fallback')

    Returns:
        True if successful, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Get entry price
    cursor.execute("""
        SELECT entry_price FROM hypothetical_trades
        WHERE id = ? AND status = 'open'
    """, (trade_id,))

    row = cursor.fetchone()
    if not row:
        conn.close()
        logger.warning(f"Hypothetical trade {trade_id} not found or already closed")
        return False

    entry_price = row[0]
    pnl_percent = ((exit_price - entry_price) / entry_price) * 100

    # Update trade
    cursor.execute("""
        UPDATE hypothetical_trades
        SET exit_time = ?,
            exit_price = ?,
            pnl_percent = ?,
            status = 'closed',
            exit_reason = ?
        WHERE id = ?
    """, (
        exit_time.strftime('%Y-%m-%d %H:%M:%S'),
        exit_price,
        pnl_percent,
        exit_reason,
        trade_id
    ))

    conn.commit()
    conn.close()

    logger.info(f"Closed hypothetical trade {trade_id} ({exit_reason}): {pnl_percent:+.2f}%")
    return True


def get_open_hypothetical_trades(trade_date: Optional[date] = None,
                                  strategy_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get all open hypothetical trades, optionally filtered by date and strategy.

    Args:
        trade_date: Optional date filter (default: today)
        strategy_type: Optional strategy type filter

    Returns:
        List of open trade dictionaries
    """
    conn = get_connection()
    cursor = conn.cursor()

    if trade_date and strategy_type:
        cursor.execute("""
            SELECT * FROM hypothetical_trades
            WHERE status = 'open' AND date = ? AND strategy_type = ?
            ORDER BY entry_time ASC
        """, (trade_date.strftime('%Y-%m-%d'), strategy_type))
    elif trade_date:
        cursor.execute("""
            SELECT * FROM hypothetical_trades
            WHERE status = 'open' AND date = ?
            ORDER BY entry_time ASC
        """, (trade_date.strftime('%Y-%m-%d'),))
    elif strategy_type:
        cursor.execute("""
            SELECT * FROM hypothetical_trades
            WHERE status = 'open' AND strategy_type = ?
            ORDER BY entry_time ASC
        """, (strategy_type,))
    else:
        cursor.execute("""
            SELECT * FROM hypothetical_trades
            WHERE status = 'open'
            ORDER BY entry_time ASC
        """)

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_hypothetical_trades(trade_date: Optional[date] = None,
                             limit: int = 100,
                             strategy_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get hypothetical trades, optionally filtered by date and strategy.

    Args:
        trade_date: Optional date filter
        limit: Maximum number of trades to return
        strategy_type: Optional strategy type filter

    Returns:
        List of trade dictionaries
    """
    conn = get_connection()
    cursor = conn.cursor()

    if trade_date and strategy_type:
        cursor.execute("""
            SELECT * FROM hypothetical_trades
            WHERE date = ? AND strategy_type = ?
            ORDER BY entry_time DESC
            LIMIT ?
        """, (trade_date.strftime('%Y-%m-%d'), strategy_type, limit))
    elif trade_date:
        cursor.execute("""
            SELECT * FROM hypothetical_trades
            WHERE date = ?
            ORDER BY entry_time DESC
            LIMIT ?
        """, (trade_date.strftime('%Y-%m-%d'), limit))
    elif strategy_type:
        cursor.execute("""
            SELECT * FROM hypothetical_trades
            WHERE strategy_type = ?
            ORDER BY entry_time DESC
            LIMIT ?
        """, (strategy_type, limit))
    else:
        cursor.execute("""
            SELECT * FROM hypothetical_trades
            ORDER BY entry_time DESC
            LIMIT ?
        """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_hypothetical_stats(trade_date: Optional[date] = None,
                            strategy_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Calculate statistics for hypothetical trades.

    Args:
        trade_date: Optional date filter (default: all trades)
        strategy_type: Optional strategy type filter

    Returns:
        Dictionary with statistics
    """
    conn = get_connection()
    cursor = conn.cursor()

    if trade_date and strategy_type:
        # Stats for specific date and strategy
        cursor.execute("""
            SELECT
                COUNT(*) as total_trades,
                COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_trades,
                COUNT(CASE WHEN status = 'open' THEN 1 END) as open_trades,
                COUNT(CASE WHEN pnl_percent > 0 THEN 1 END) as profitable_trades,
                COUNT(CASE WHEN pnl_percent < 0 THEN 1 END) as losing_trades,
                AVG(CASE WHEN status = 'closed' THEN pnl_percent END) as avg_return,
                MAX(pnl_percent) as max_return,
                MIN(pnl_percent) as min_return
            FROM hypothetical_trades
            WHERE date = ? AND strategy_type = ?
        """, (trade_date.strftime('%Y-%m-%d'), strategy_type))
    elif trade_date:
        # Stats for specific date (all strategies)
        cursor.execute("""
            SELECT
                COUNT(*) as total_trades,
                COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_trades,
                COUNT(CASE WHEN status = 'open' THEN 1 END) as open_trades,
                COUNT(CASE WHEN pnl_percent > 0 THEN 1 END) as profitable_trades,
                COUNT(CASE WHEN pnl_percent < 0 THEN 1 END) as losing_trades,
                AVG(CASE WHEN status = 'closed' THEN pnl_percent END) as avg_return,
                MAX(pnl_percent) as max_return,
                MIN(pnl_percent) as min_return
            FROM hypothetical_trades
            WHERE date = ?
        """, (trade_date.strftime('%Y-%m-%d'),))
    elif strategy_type:
        # Overall stats for specific strategy
        cursor.execute("""
            SELECT
                COUNT(*) as total_trades,
                COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_trades,
                COUNT(CASE WHEN status = 'open' THEN 1 END) as open_trades,
                COUNT(CASE WHEN pnl_percent > 0 THEN 1 END) as profitable_trades,
                COUNT(CASE WHEN pnl_percent < 0 THEN 1 END) as losing_trades,
                AVG(CASE WHEN status = 'closed' THEN pnl_percent END) as avg_return,
                MAX(pnl_percent) as max_return,
                MIN(pnl_percent) as min_return
            FROM hypothetical_trades
            WHERE strategy_type = ?
        """, (strategy_type,))
    else:
        # Overall stats (all strategies)
        cursor.execute("""
            SELECT
                COUNT(*) as total_trades,
                COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_trades,
                COUNT(CASE WHEN status = 'open' THEN 1 END) as open_trades,
                COUNT(CASE WHEN pnl_percent > 0 THEN 1 END) as profitable_trades,
                COUNT(CASE WHEN pnl_percent < 0 THEN 1 END) as losing_trades,
                AVG(CASE WHEN status = 'closed' THEN pnl_percent END) as avg_return,
                MAX(pnl_percent) as max_return,
                MIN(pnl_percent) as min_return
            FROM hypothetical_trades
        """)
    
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {
            'total_trades': 0,
            'closed_trades': 0,
            'open_trades': 0,
            'profitable_trades': 0,
            'losing_trades': 0,
            'avg_return': 0.0,
            'max_return': 0.0,
            'min_return': 0.0,
            'win_rate': 0.0
        }

    stats = dict(row)

    # Convert None values to 0.0 (happens when no trades exist)
    stats['avg_return'] = stats['avg_return'] if stats['avg_return'] is not None else 0.0
    stats['max_return'] = stats['max_return'] if stats['max_return'] is not None else 0.0
    stats['min_return'] = stats['min_return'] if stats['min_return'] is not None else 0.0

    # Calculate win rate
    if stats['closed_trades'] > 0:
        stats['win_rate'] = (stats['profitable_trades'] / stats['closed_trades']) * 100
    else:
        stats['win_rate'] = 0.0

    return stats


def extract_earnings_intraday_for_date(target_date: date) -> Dict[str, int]:
    """
    Extract intraday data for all earnings on the given date.

    This function:
    1. Finds all tickers with earnings on target_date from the earnings calendar
    2. Extracts their intraday price data
    3. Determines which passed filter and which created signals
    4. Saves all data to earnings_intraday_analysis table

    Args:
        target_date: Date to extract earnings data for

    Returns:
        Dictionary with extraction statistics:
        {
            'total_earnings': int,
            'extracted': int,
            'passed_filter': int,
            'created_signal': int,
            'data_points': int
        }
    """
    import pandas as pd
    import yfinance as yf
    from datetime import timedelta

    logger.info(f"Extracting earnings intraday data for {target_date}")

    # Load earnings calendar to find earnings for this date
    csv_path = 'data/earnings_calendar.csv'

    try:
        df = pd.read_csv(csv_path, encoding='utf-8')
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(csv_path, encoding='latin-1')
        except:
            df = pd.read_csv(csv_path, encoding='cp1252')

    # Parse dates and filter for target date
    def parse_date(date_str):
        try:
            from datetime import datetime
            return datetime.strptime(date_str, '%m/%d/%y').date()
        except:
            try:
                from datetime import datetime
                return datetime.strptime(date_str, '%Y-%m-%d').date()
            except:
                return None

    earnings_today = []
    for _, row in df.iterrows():
        if pd.isna(row['date']) or pd.isna(row['ticker']):
            continue

        date_obj = parse_date(str(row['date']))
        if date_obj == target_date:
            earnings_today.append(row['ticker'])

    logger.info(f"Found {len(earnings_today)} earnings for {target_date}")

    if len(earnings_today) == 0:
        return {
            'total_earnings': 0,
            'extracted': 0,
            'passed_filter': 0,
            'created_signal': 0,
            'data_points': 0
        }

    # Get filter-passed and signal-created sets
    conn = get_connection()
    cursor = conn.cursor()

    target_date_str = target_date.strftime('%Y-%m-%d')

    cursor.execute("SELECT DISTINCT ticker FROM watchlist WHERE date = ?", (target_date_str,))
    watchlist_set = set(row[0] for row in cursor.fetchall())

    cursor.execute("SELECT DISTINCT ticker FROM signals WHERE DATE(signal_time) = ?", (target_date_str,))
    signals_set = set(row[0] for row in cursor.fetchall())

    cursor.execute("SELECT DISTINCT ticker FROM hypothetical_trades WHERE date = ?", (target_date_str,))
    trades_set = set(row[0] for row in cursor.fetchall())

    filter_passed_set = watchlist_set | signals_set | trades_set

    # Extract intraday data for each ticker
    extracted_count = 0
    data_points_count = 0

    start_date = target_date.strftime('%Y-%m-%d')
    end_date = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')

    for ticker in earnings_today:
        try:
            # Fetch intraday data
            stock = yf.Ticker(ticker)
            intraday_df = stock.history(start=start_date, end=end_date, interval='1m')

            if intraday_df is None or len(intraday_df) == 0:
                continue

            # Filter for market hours
            try:
                intraday_df = intraday_df.between_time('09:00', '17:30')
            except:
                pass

            if len(intraday_df) == 0:
                continue

            # Find base price (prefer 09:00, accept first available)
            base_price = None
            for timestamp, row in intraday_df.iterrows():
                time_str = timestamp.strftime('%H:%M')
                if time_str.startswith('09:00') or time_str.startswith('09:01'):
                    base_price = row['Close']
                    break

            if base_price is None:
                first_row = intraday_df.iloc[0]
                base_price = first_row['Close']

            if base_price is None or base_price == 0:
                continue

            # Check filter status
            passed_filter = ticker in filter_passed_set
            created_signal = ticker in trades_set

            # Save intraday points
            for timestamp, row in intraday_df.iterrows():
                time_str = timestamp.strftime('%H:%M')
                price = row['Close']

                if price > 0:
                    normalized_price = (price / base_price) * 100
                    timestamp_str = f"{target_date_str} {time_str}:00"

                    cursor.execute("""
                        INSERT OR REPLACE INTO earnings_intraday_analysis
                        (ticker, earnings_date, time_of_day, timestamp, price,
                         normalized_price, base_price, filter_score, passed_filter, created_signal)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ticker, target_date_str, time_str, timestamp_str, float(price),
                        float(normalized_price), float(base_price),
                        100.0 if passed_filter else 0.0, passed_filter, created_signal
                    ))
                    data_points_count += 1

            extracted_count += 1

        except Exception as e:
            logger.error(f"Error extracting {ticker} for {target_date}: {e}")

    conn.commit()
    conn.close()

    result = {
        'total_earnings': len(earnings_today),
        'extracted': extracted_count,
        'passed_filter': len(filter_passed_set & set(earnings_today)),
        'created_signal': len(trades_set & set(earnings_today)),
        'data_points': data_points_count
    }

    logger.info(f"Extracted {extracted_count}/{len(earnings_today)} earnings, "
                f"saved {data_points_count} data points")

    return result


def calculate_top_performers(target_date: date, percentile: float = 0.30) -> Dict[str, Any]:
    """
    Calculate and mark the top and bottom performing stocks for a given earnings date.

    Performance is measured as percentage gain from base price (9:00) to final price (last available).
    Top performers are marked in the top_20pct_performer field.
    Bottom performers are marked in the bottom_30pct_performer field.

    Args:
        target_date: Date to calculate performers for
        percentile: Percentile to mark as top/bottom performers (default 0.30 = 30%)

    Returns:
        Dictionary with statistics:
        {
            'total_stocks': int,
            'top_performer_count': int,
            'bottom_performer_count': int,
            'top_min_gain_threshold': float,
            'bottom_max_gain_threshold': float
        }
    """
    conn = get_connection()
    cursor = conn.cursor()

    target_date_str = target_date.strftime('%Y-%m-%d')

    # Get all unique tickers for this date with their base price and actual closing price
    # Use the price at the latest time_of_day (actual close), not MAX price (best moment)
    cursor.execute("""
        SELECT
            e1.ticker,
            e1.base_price,
            e1.normalized_price as final_price
        FROM earnings_intraday_analysis e1
        INNER JOIN (
            SELECT ticker, MAX(time_of_day) as max_time
            FROM earnings_intraday_analysis
            WHERE earnings_date = ?
            GROUP BY ticker
        ) e2 ON e1.ticker = e2.ticker AND e1.time_of_day = e2.max_time
        WHERE e1.earnings_date = ?
          AND e1.base_price > 0
          AND e1.normalized_price > 0
    """, (target_date_str, target_date_str))

    stocks = cursor.fetchall()

    if not stocks:
        conn.close()
        logger.warning(f"No stocks found for {target_date} to calculate performers")
        return {
            'total_stocks': 0,
            'top_performer_count': 0,
            'bottom_performer_count': 0,
            'top_min_gain_threshold': 0.0,
            'bottom_max_gain_threshold': 0.0
        }

    # Calculate gain for each stock
    stock_gains = []
    for ticker, base_price, final_price in stocks:
        # Gain as percentage points from 100% baseline
        # (final_price is normalized_price which is relative to 9:00 = 100%)
        gain = final_price - 100.0
        stock_gains.append((ticker, gain))

    # Sort by gain (descending)
    stock_gains.sort(key=lambda x: x[1], reverse=True)

    # Calculate how many stocks are in each percentile
    count = max(1, int(len(stock_gains) * percentile))

    # Get the top and bottom performers
    top_performers = [ticker for ticker, gain in stock_gains[:count]]
    bottom_performers = [ticker for ticker, gain in stock_gains[-count:]]

    top_min_gain = stock_gains[count - 1][1] if count > 0 else 0.0
    bottom_max_gain = stock_gains[-count][1] if count > 0 else 0.0

    # Reset all stocks for this date
    cursor.execute("""
        UPDATE earnings_intraday_analysis
        SET top_20pct_performer = 0, bottom_30pct_performer = 0
        WHERE earnings_date = ?
    """, (target_date_str,))

    # Mark top performers
    for ticker in top_performers:
        cursor.execute("""
            UPDATE earnings_intraday_analysis
            SET top_20pct_performer = 1
            WHERE earnings_date = ? AND ticker = ?
        """, (target_date_str, ticker))

    # Mark bottom performers
    for ticker in bottom_performers:
        cursor.execute("""
            UPDATE earnings_intraday_analysis
            SET bottom_30pct_performer = 1
            WHERE earnings_date = ? AND ticker = ?
        """, (target_date_str, ticker))

    conn.commit()
    conn.close()

    result = {
        'total_stocks': len(stock_gains),
        'top_performer_count': count,
        'bottom_performer_count': count,
        'top_min_gain_threshold': round(top_min_gain, 2),
        'bottom_max_gain_threshold': round(bottom_max_gain, 2)
    }

    logger.info(f"Marked top/bottom {percentile*100}% performers for {target_date}: "
                f"top={count}/{len(stock_gains)} (min: {top_min_gain:+.2f}%), "
                f"bottom={count}/{len(stock_gains)} (max: {bottom_max_gain:+.2f}%)")

    return result
