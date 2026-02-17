import sqlite3
import os

DB_PATH = 'waiters.db'  # ← просто имя файла

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            birth_date TEXT NOT NULL,
            phone TEXT NOT NULL,
            medbook_status TEXT CHECK(medbook_status IN ('действует', 'просрочена', 'оформляется')) DEFAULT 'действует',
            medbook_expiry DATE NOT NULL,
            consent_given BOOLEAN DEFAULT 0,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blacklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            phone TEXT,
            birth_date TEXT,
            reason TEXT NOT NULL,
            blacklisted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            added_by INTEGER NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ База инициализирована")

# Остальные функции — те же, что раньше, но с `sqlite3.connect('waiters.db')`
def add_staff(telegram_id, full_name, birth_date, phone, medbook_expiry):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO staff 
            (telegram_id, full_name, birth_date, phone, medbook_status, medbook_expiry, consent_given, updated_at)
            VALUES (?, ?, ?, ?, 'действует', ?, 1, CURRENT_TIMESTAMP)
        ''', (telegram_id, full_name, birth_date, phone, medbook_expiry))
        conn.commit()
        return True
    except Exception as e:
        print(f"Ошибка: {e}")
        return False
    finally:
        conn.close()

# ... остальные функции (get_staff_by_surname, update_medbook и т.д.) — аналогично, с DB_PATH
