import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "laundry.db")

def update_database():
    """Add new tables and columns for advanced features."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    
    # Add new columns to orders table
    try:
        conn.execute("ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'Pending'")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        conn.execute("ALTER TABLE orders ADD COLUMN service_type TEXT DEFAULT 'Wash & Fold'")
    except sqlite3.OperationalError:
        pass
    
    try:
        conn.execute("ALTER TABLE orders ADD COLUMN weight REAL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    
    try:
        conn.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT 'Cash'")
    except sqlite3.OperationalError:
        pass
    
    try:
        conn.execute("ALTER TABLE orders ADD COLUMN pickup_address TEXT")
    except sqlite3.OperationalError:
        pass
    
    try:
        conn.execute("ALTER TABLE orders ADD COLUMN delivery_address TEXT")
    except sqlite3.OperationalError:
        pass
    
    try:
        conn.execute("ALTER TABLE orders ADD COLUMN pickup_date TEXT")
    except sqlite3.OperationalError:
        pass
    
    try:
        conn.execute("ALTER TABLE orders ADD COLUMN delivery_date TEXT")
    except sqlite3.OperationalError:
        pass
    
    try:
        conn.execute("ALTER TABLE orders ADD COLUMN notes TEXT")
    except sqlite3.OperationalError:
        pass
    
    # Add loyalty points to customers table
    try:
        conn.execute("ALTER TABLE customers ADD COLUMN loyalty_points INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    
    try:
        conn.execute("ALTER TABLE customers ADD COLUMN total_orders INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    
    try:
        conn.execute("ALTER TABLE customers ADD COLUMN total_spent REAL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    
    # Create staff table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'staff',
            full_name TEXT,
            phone TEXT,
            email TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create loyalty rewards table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS loyalty_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            points INTEGER,
            reward_type TEXT,
            redeemed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)
    
    # Create activity log table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            action TEXT,
            details TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    print("✅ Database updated successfully with new features!")

if __name__ == "__main__":
    update_database()