"""
db.py
-----
SQLite data layer for the expense tracker.

Design decision: Gradio has no built-in auth, so every row is scoped by
`username` instead of keeping separate files per user (which is what a
flat-file/CSV approach would do). One database, one schema, filtered queries.
This is the difference between "storing data" and "designing a data model".
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = "data/expenses.db"


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                merchant TEXT,
                is_recurring INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                username TEXT NOT NULL,
                category TEXT NOT NULL,
                monthly_limit REAL NOT NULL,
                PRIMARY KEY (username, category)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                username TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (username, key)
            )
        """)


def insert_expense(username: str, raw_text: str, amount: float, category: str,
                    merchant: str = None, is_recurring: bool = False, created_at: str = None):
    created_at = created_at or datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO expenses (username, raw_text, amount, category, merchant, is_recurring, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (username, raw_text, amount, category, merchant, int(is_recurring), created_at),
        )


def get_expenses(username: str):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM expenses WHERE username = ? ORDER BY created_at DESC",
            (username,),
        ).fetchall()
        return [dict(r) for r in rows]


def find_recent_similar(username: str, merchant: str, amount: float, days: int = 35):
    """Used by the ETL layer to flag recurring subscriptions / duplicates."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM expenses
               WHERE username = ? AND merchant = ? AND ABS(amount - ?) < 1
               AND created_at >= datetime('now', ?)""",
            (username, merchant, amount, f"-{days} days"),
        ).fetchall()
        return [dict(r) for r in rows]


def set_budget(username: str, category: str, monthly_limit: float):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO budgets (username, category, monthly_limit) VALUES (?, ?, ?)
               ON CONFLICT(username, category) DO UPDATE SET monthly_limit = excluded.monthly_limit""",
            (username, category, monthly_limit),
        )


def get_budgets(username: str):
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM budgets WHERE username = ?", (username,)).fetchall()
        return {r["category"]: r["monthly_limit"] for r in rows}


def get_recurring_expenses(username: str):
    """All entries ever flagged as recurring, most recent first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM expenses WHERE username = ? AND is_recurring = 1 ORDER BY created_at DESC",
            (username,),
        ).fetchall()
        return [dict(r) for r in rows]


def set_preference(username: str, key: str, value: str):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO preferences (username, key, value) VALUES (?, ?, ?)
               ON CONFLICT(username, key) DO UPDATE SET value = excluded.value""",
            (username, key, value),
        )


def get_preference(username: str, key: str, default: str = None):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM preferences WHERE username = ? AND key = ?",
            (username, key),
        ).fetchone()
        return row["value"] if row else default