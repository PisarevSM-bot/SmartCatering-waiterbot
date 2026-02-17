import sqlite3
import os

DB_PATH = 'waiters.db'

def init_db():
    """Создаёт файл и таблицы. Работает даже если файла нет."""
    # 1. Убедимся, что файл существует
    try:
        if not os.path.exists(DB_PATH):
            with open(DB_PATH, 'w') as f:
                f.write('')  # создаём пустой файл
            print(f"✅ Создан файл: {DB_PATH}")
    except Exception as e:
        print(f"⚠️ Не удалось создать файл: {e}")
        raise

    # 2. Подключаемся и создаём таблицы
    try:
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
        print("✅ Таблицы созданы")
    except Exception as e:
        print(f"❌ Ошибка при инициализации БД: {e}")
        raise
