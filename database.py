import sqlite3
import os

# Используем текущую рабочую директорию — Railway сохраняет её при наличии volume
DB_PATH = 'waiters.db'

def get_db_connection():
    """Создаёт соединение и таблицы при первом вызове. Безопасно для Railway."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
        cursor = conn.cursor()
        
        # Проверяем наличие таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='staff'")
        if not cursor.fetchone():
            # Создаём таблицы
            cursor.execute('''
                CREATE TABLE staff (
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
                CREATE TABLE blacklist (
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
        return conn
    except Exception as e:
        raise RuntimeError(f"Не удалось открыть базу данных: {e}")

def add_staff(telegram_id, full_name, birth_date, phone, medbook_expiry):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()        cursor.execute('''
            INSERT OR REPLACE INTO staff 
            (telegram_id, full_name, birth_date, phone, medbook_status, medbook_expiry, consent_given, updated_at)
            VALUES (?, ?, ?, ?, 'действует', ?, 1, CURRENT_TIMESTAMP)
        ''', (telegram_id, full_name, birth_date, phone, medbook_expiry))
        conn.commit()
        return True
    finally:
        conn.close()

def update_medbook(telegram_id, medbook_expiry):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE staff 
            SET medbook_expiry = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE telegram_id = ?
        ''', (medbook_expiry, telegram_id))
        conn.commit()
    finally:
        conn.close()

def get_staff_by_surname(surname):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT full_name, birth_date, phone, medbook_status, medbook_expiry FROM staff WHERE full_name LIKE ? ORDER BY full_name', (f'%{surname}%',))
        return cursor.fetchall()
    finally:
        conn.close()

def get_all_staff():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT full_name, birth_date, phone, medbook_status, medbook_expiry FROM staff ORDER BY full_name')
        return cursor.fetchall()
    finally:
        conn.close()

def get_expiring_medbooks(days_ahead):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT telegram_id, full_name, medbook_expiry FROM staff WHERE medbook_status = "действует" AND date(medbook_expiry) BETWEEN date("now") AND date("now", ? || " days") AND consent_given = 1 ORDER BY medbook_expiry', (days_ahead,))
        return cursor.fetchall()
    finally:
        conn.close()
def add_to_blacklist(full_name, phone, birth_date, reason, admin_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO blacklist (full_name, phone, birth_date, reason, added_by) VALUES (?, ?, ?, ?, ?)', (full_name, phone, birth_date, reason, admin_id))
        cursor.execute('DELETE FROM staff WHERE full_name = ?', (full_name,))
        conn.commit()
        return True
    finally:
        conn.close()

def remove_from_blacklist(full_name):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM blacklist WHERE full_name LIKE ?', (f'%{full_name}%',))
        return cursor.rowcount
    finally:
        conn.close()

def get_blacklist():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT full_name, phone, reason, blacklisted_at FROM blacklist ORDER BY blacklisted_at DESC')
        return cursor.fetchall()
    finally:
        conn.close()

def staff_exists(telegram_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM staff WHERE telegram_id = ?', (telegram_id,))
        return cursor.fetchone() is not None
    finally:
        conn.close()

def get_staff_stats():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM staff')
        total = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM staff WHERE medbook_status = "просрочена"')
        expired = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM blacklist')
        blacklisted = cursor.fetchone()[0]
        return total, expired, blacklisted
    finally:        conn.close()
