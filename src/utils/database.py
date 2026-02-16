"""Database utilities for Svea Surveillance."""

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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hypothetical_trades (
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (signal_id) REFERENCES signals(id),
            UNIQUE(ticker, date)
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
                               entry_price: float, trade_date: date) -> Optional[int]:
    """
    Create a hypothetical trade entry (paper trading).
    Only creates if no trade exists for this ticker on this date.
    
    Args:
        ticker: Stock ticker
        signal_id: ID of the signal that triggered this trade
        entry_time: Entry timestamp
        entry_price: Entry price
        trade_date: Date of the trade
    
    Returns:
        Trade ID if created, None if already exists
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if trade already exists for this ticker today
    cursor.execute("""
        SELECT id FROM hypothetical_trades
        WHERE ticker = ? AND date = ?
    """, (ticker, trade_date.strftime('%Y-%m-%d')))
    
    existing = cursor.fetchone()
    if existing:
        conn.close()
        logger.debug(f"Hypothetical trade already exists for {ticker} on {trade_date}")
        return None
    
    # Create new hypothetical trade
    cursor.execute("""
        INSERT INTO hypothetical_trades
        (ticker, date, signal_id, entry_time, entry_price, status)
        VALUES (?, ?, ?, ?, ?, 'open')
    """, (
        ticker,
        trade_date.strftime('%Y-%m-%d'),
        signal_id,
        entry_time.strftime('%Y-%m-%d %H:%M:%S'),
        entry_price
    ))
    
    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    logger.info(f"Created hypothetical trade for {ticker} at {entry_price} SEK")
    return trade_id


def has_hypothetical_trade_today(ticker: str, trade_date: date) -> bool:
    """
    Check if a hypothetical trade already exists for ticker on given date.
    
    Args:
        ticker: Stock ticker
        trade_date: Date to check
    
    Returns:
        True if trade exists, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id FROM hypothetical_trades
        WHERE ticker = ? AND date = ?
    """, (ticker, trade_date.strftime('%Y-%m-%d')))
    
    exists = cursor.fetchone() is not None
    conn.close()
    
    return exists


def close_hypothetical_trade(trade_id: int, exit_time: datetime, exit_price: float) -> bool:
    """
    Close a hypothetical trade with exit price and calculate P&L.
    
    Args:
        trade_id: ID of the trade to close
        exit_time: Exit timestamp
        exit_price: Exit price
    
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
            status = 'closed'
        WHERE id = ?
    """, (
        exit_time.strftime('%Y-%m-%d %H:%M:%S'),
        exit_price,
        pnl_percent,
        trade_id
    ))
    
    conn.commit()
    conn.close()
    
    logger.info(f"Closed hypothetical trade {trade_id}: {pnl_percent:+.2f}%")
    return True


def get_open_hypothetical_trades(trade_date: Optional[date] = None) -> List[Dict[str, Any]]:
    """
    Get all open hypothetical trades, optionally filtered by date.
    
    Args:
        trade_date: Optional date filter (default: today)
    
    Returns:
        List of open trade dictionaries
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if trade_date:
        cursor.execute("""
            SELECT * FROM hypothetical_trades
            WHERE status = 'open' AND date = ?
            ORDER BY entry_time ASC
        """, (trade_date.strftime('%Y-%m-%d'),))
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
                             limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get hypothetical trades, optionally filtered by date.
    
    Args:
        trade_date: Optional date filter
        limit: Maximum number of trades to return
    
    Returns:
        List of trade dictionaries
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if trade_date:
        cursor.execute("""
            SELECT * FROM hypothetical_trades
            WHERE date = ?
            ORDER BY entry_time DESC
            LIMIT ?
        """, (trade_date.strftime('%Y-%m-%d'), limit))
    else:
        cursor.execute("""
            SELECT * FROM hypothetical_trades
            ORDER BY entry_time DESC
            LIMIT ?
        """, (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def get_hypothetical_stats(trade_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Calculate statistics for hypothetical trades.
    
    Args:
        trade_date: Optional date filter (default: all trades)
    
    Returns:
        Dictionary with statistics
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if trade_date:
        # Stats for specific date
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
    else:
        # Overall stats
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
