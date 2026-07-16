import sqlite3
import os

# Get the directory where this file is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "laundry.db")


def get_connection():
    """Open a connection to the database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def get_db():
    """Context manager for database connections."""
    from contextlib import contextmanager
    
    @contextmanager
    def db_connection():
        conn = get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    return db_connection()


def init_db():
    """Create all tables if they don't already exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                item_description TEXT NOT NULL,
                price REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                service_type TEXT DEFAULT 'Wash & Fold',
                payment_method TEXT DEFAULT 'Cash',
                pickup_address TEXT,
                delivery_address TEXT,
                weight REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                notes TEXT,
                loyalty_points INTEGER DEFAULT 0,
                total_orders INTEGER DEFAULT 0,
                total_spent REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
    print("✅ Database ready!")


if __name__ == "__main__":
    init_db()