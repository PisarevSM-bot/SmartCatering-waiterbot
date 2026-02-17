import sqlite3
import os

# Используем относительный путь — Railway сохраняет файлы в корне при наличии volume
DB_PATH = 'waiters.db'

# Создаём файл явно при импорте (критично для Railway)
if not os.path.exists(DB_PATH):
    try:
        with open(DB_PATH, 'w') as f:
            f.write('')  # пустой файл
        print(f"✅ Создан файл: {DB_PATH}")
    except Exception as e:
        print(f"⚠️ Не удалось создать файл: {e}")

def init_db():
    """Инициализирует таблицы, если их нет"""
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
    print("✅ База данных инициализирована")
def add_staff(telegram_id, full_name, birth_date, phone, medbook_expiry):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO staff 
        (telegram_id, full_name, birth_date, phone, medbook_status, medbook_expiry, consent_given, updated_at)
        VALUES (?, ?, ?, ?, 'действует', ?, 1, CURRENT_TIMESTAMP)
    ''', (telegram_id, full_name, birth_date, phone, medbook_expiry))
    conn.commit()
    conn.close()
    return True

def update_medbook(telegram_id, medbook_expiry):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE staff 
        SET medbook_expiry = ?, updated_at = CURRENT_TIMESTAMP 
        WHERE telegram_id = ?
    ''', (medbook_expiry, telegram_id))
    conn.commit()
    conn.close()

def get_staff_by_surname(surname):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT full_name, birth_date, phone, medbook_status, medbook_expiry FROM staff WHERE full_name LIKE ? ORDER BY full_name', (f'%{surname}%',))
    result = cursor.fetchall()
    conn.close()
    return result

def get_all_staff():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT full_name, birth_date, phone, medbook_status, medbook_expiry FROM staff ORDER BY full_name')
    result = cursor.fetchall()
    conn.close()
    return result

def get_expiring_medbooks(days_ahead):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT telegram_id, full_name, medbook_expiry FROM staff WHERE medbook_status = "действует" AND date(medbook_expiry) BETWEEN date("now") AND date("now", ? || " days") AND consent_given = 1 ORDER BY medbook_expiry', (days_ahead,))
    result = cursor.fetchall()
    conn.close()
    return result

def add_to_blacklist(full_name, phone, birth_date, reason, admin_id):
    conn = sqlite3.connect(DB_PATH)    cursor = conn.cursor()
    cursor.execute('INSERT INTO blacklist (full_name, phone, birth_date, reason, added_by) VALUES (?, ?, ?, ?, ?)', (full_name, phone, birth_date, reason, admin_id))
    cursor.execute('DELETE FROM staff WHERE full_name = ?', (full_name,))
    conn.commit()
    conn.close()
    return True

def remove_from_blacklist(full_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM blacklist WHERE full_name LIKE ?', (f'%{full_name}%',))
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count

def get_blacklist():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT full_name, phone, reason, blacklisted_at FROM blacklist ORDER BY blacklisted_at DESC')
    result = cursor.fetchall()
    conn.close()
    return result

def staff_exists(telegram_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM staff WHERE telegram_id = ?', (telegram_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def get_staff_stats():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM staff')
    total = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM staff WHERE medbook_status = "просрочена"')
    expired = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM blacklist')
    blacklisted = cursor.fetchone()[0]
    conn.close()
    return total, expired, blacklisted
