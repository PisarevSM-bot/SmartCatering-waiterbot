import sqlite3
import os
from datetime import datetime

# Убедимся, что путь существует и записываемый
DB_PATH = '/app/waiters.db'
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def init_db():
    # Попробуем создать файл явно
    try:
        with open(DB_PATH, 'a'):
            pass  # просто создаст файл, если его нет
    except Exception as e:
        print(f"⚠️ Не удалось создать файл базы: {e}")

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
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_name ON staff(full_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_expiry ON staff(medbook_expiry)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_blacklist_name ON blacklist(full_name)')
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")
