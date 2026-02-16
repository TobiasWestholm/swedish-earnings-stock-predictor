"""Database cleanup utilities."""

import sqlite3
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from src.utils.database import get_connection

logger = logging.getLogger(__name__)


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


def archive_old_data(archive_days: int = 30) -> dict:
    """
    Archive data older than archive_days (move to archive tables or files).

    Currently just cleans up to prevent database bloat.
    In production, you might want to export to CSV before deleting.

    Args:
        archive_days: Days of data to keep

    Returns:
        Dictionary with counts of archived items
    """
    logger.info(f"Archiving data older than {archive_days} days")

    result = {
        'watchlist': clear_old_watchlist(keep_days=archive_days),
        'signals': clear_old_signals(keep_days=archive_days),
        'intraday_data': clear_old_intraday_data(keep_days=archive_days)
    }

    logger.info(f"Archive complete: {result}")
    return result


def get_database_stats() -> dict:
    """
    Get statistics about database contents.

    Returns:
        Dictionary with table row counts and date ranges
    """
    conn = get_connection()
    cursor = conn.cursor()

    stats = {}

    # Watchlist stats
    cursor.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM watchlist")
    row = cursor.fetchone()
    stats['watchlist'] = {
        'count': row[0],
        'oldest_date': row[1],
        'newest_date': row[2]
    }

    # Signals stats
    cursor.execute("SELECT COUNT(*), MIN(DATE(signal_time)), MAX(DATE(signal_time)) FROM signals")
    row = cursor.fetchone()
    stats['signals'] = {
        'count': row[0],
        'oldest_date': row[1],
        'newest_date': row[2]
    }

    # Intraday data stats
    cursor.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM intraday_data")
    row = cursor.fetchone()
    stats['intraday_data'] = {
        'count': row[0],
        'oldest_date': row[1],
        'newest_date': row[2]
    }

    conn.close()
    return stats


if __name__ == '__main__':
    # Test cleanup functions
    from src.utils.logger import setup_logger

    setup_logger()

    print("\n" + "="*80)
    print("DATABASE STATISTICS")
    print("="*80)

    stats = get_database_stats()
    for table, data in stats.items():
        print(f"\n{table}:")
        print(f"  Count: {data['count']}")
        print(f"  Date Range: {data['oldest_date']} to {data['newest_date']}")

    print("\n" + "="*80)
    print("Test cleanup? (y/n): ", end='')

    response = input().strip().lower()
    if response == 'y':
        print("\nRunning cleanup for today...")
        today = date.today()

        watchlist_cleared = clear_old_watchlist(target_date=today)
        signals_cleared = clear_old_signals(target_date=today)

        print(f"\nCleared:")
        print(f"  Watchlist: {watchlist_cleared} entries")
        print(f"  Signals: {signals_cleared} entries")

        print("\nUpdated statistics:")
        stats = get_database_stats()
        for table, data in stats.items():
            print(f"\n{table}: {data['count']} entries")
