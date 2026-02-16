import sqlite3

def init_db():
    conn = sqlite3.connect("waiters.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            birth_date TEXT NOT NULL,
            phone TEXT NOT NULL,
            medbook_expiry DATE NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blacklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            phone TEXT,
            reason TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_staff(telegram_id, full_name, birth_date, phone, medbook_expiry):
    conn = sqlite3.connect("waiters.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO staff 
        (telegram_id, full_name, birth_date, phone, medbook_expiry)
        VALUES (?, ?, ?, ?, ?)
    """, (telegram_id, full_name, birth_date, phone, medbook_expiry))
    conn.commit()
    conn.close()
    return True

def staff_exists(telegram_id):
    conn = sqlite3.connect("waiters.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM staff WHERE telegram_id = ?", (telegram_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None
