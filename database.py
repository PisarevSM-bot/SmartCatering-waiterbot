import os
import psycopg2
from datetime import datetime

DB_URL = os.getenv("DATABASE_URL")

def init_db():
    conn = psycopg2.connect(DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS staff (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    full_name TEXT NOT NULL,
                    birth_date TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    medbook_status TEXT CHECK(medbook_status IN ('действует', 'просрочена', 'оформляется')) DEFAULT 'действует',
                    medbook_expiry DATE NOT NULL,
                    consent_given BOOLEAN DEFAULT FALSE,
                    registered_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS blacklist (
                    id SERIAL PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    phone TEXT,
                    birth_date TEXT,
                    reason TEXT NOT NULL,
                    blacklisted_at TIMESTAMP DEFAULT NOW(),
                    added_by BIGINT NOT NULL
                )
            ''')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_staff_name ON staff(full_name)')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_staff_expiry ON staff(medbook_expiry)')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_blacklist_name ON blacklist(full_name)')
        conn.commit()
        print("✅ База данных инициализирована")
    finally:
        conn.close()

def add_staff(telegram_id, full_name, birth_date, phone, medbook_expiry):
    conn = psycopg2.connect(DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO staff 
                (telegram_id, full_name, birth_date, phone, medbook_status, medbook_expiry, consent_given, updated_at)                VALUES (%s, %s, %s, %s, 'действует', %s, TRUE, NOW())
                ON CONFLICT (telegram_id) DO UPDATE SET
                    full_name = %s,
                    birth_date = %s,
                    phone = %s,
                    medbook_expiry = %s,
                    updated_at = NOW()
            ''', (telegram_id, full_name, birth_date, phone, medbook_expiry,
                  full_name, birth_date, phone, medbook_expiry))
        conn.commit()
        return True
    except Exception as e:
        print(f"Ошибка добавления: {e}")
        return False
    finally:
        conn.close()

def update_medbook(telegram_id, medbook_expiry):
    conn = psycopg2.connect(DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute('''
                UPDATE staff 
                SET medbook_expiry = %s, updated_at = NOW() 
                WHERE telegram_id = %s
            ''', (medbook_expiry, telegram_id))
        conn.commit()
    finally:
        conn.close()

def get_staff_by_surname(surname):
    conn = psycopg2.connect(DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT full_name, birth_date, phone, medbook_status, medbook_expiry 
                FROM staff 
                WHERE full_name ILIKE %s 
                ORDER BY full_name
            ''', (f'%{surname}%',))
            return cur.fetchall()
    finally:
        conn.close()

def get_all_staff():
    conn = psycopg2.connect(DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT full_name, birth_date, phone, medbook_status, medbook_expiry                 FROM staff 
                ORDER BY full_name
            ''')
            return cur.fetchall()
    finally:
        conn.close()

def get_expiring_medbooks(days_ahead):
    conn = psycopg2.connect(DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT telegram_id, full_name, medbook_expiry 
                FROM staff 
                WHERE medbook_status = 'действует' 
                  AND medbook_expiry BETWEEN CURRENT_DATE AND CURRENT_DATE + %s
                  AND consent_given = TRUE
                ORDER BY medbook_expiry
            ''', (days_ahead,))
            return cur.fetchall()
    finally:
        conn.close()

def add_to_blacklist(full_name, phone, birth_date, reason, admin_id):
    conn = psycopg2.connect(DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT phone, birth_date FROM staff WHERE full_name = %s', (full_name,))
            existing = cur.fetchone()
            if existing:
                phone = existing[0] or phone
                birth_date = existing[1] or birth_date
            
            cur.execute('''
                INSERT INTO blacklist (full_name, phone, birth_date, reason, added_by)
                VALUES (%s, %s, %s, %s, %s)
            ''', (full_name, phone, birth_date, reason, admin_id))
            
            cur.execute('DELETE FROM staff WHERE full_name = %s', (full_name,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Ошибка ЧС: {e}")
        return False
    finally:
        conn.close()

def remove_from_blacklist(full_name):
    conn = psycopg2.connect(DB_URL)
    try:        
        with conn.cursor() as cur:
            cur.execute('DELETE FROM blacklist WHERE full_name ILIKE %s', (f'%{full_name}%',))
            conn.commit()
            return cur.rowcount
    finally:
        conn.close()

def get_blacklist():
    conn = psycopg2.connect(DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT full_name, phone, reason, blacklisted_at 
                FROM blacklist 
                ORDER BY blacklisted_at DESC
            ''')
            return cur.fetchall()
    finally:
        conn.close()

def staff_exists(telegram_id):
    conn = psycopg2.connect(DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT 1 FROM staff WHERE telegram_id = %s', (telegram_id,))
            return cur.fetchone() is not None
    finally:
        conn.close()

def get_staff_stats():
    conn = psycopg2.connect(DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM staff')
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM staff WHERE medbook_status = 'просрочена'")
            expired = cur.fetchone()[0]
            cur.execute('SELECT COUNT(*) FROM blacklist')
            blacklisted = cur.fetchone()[0]
            return total, expired, blacklisted
    finally:
        conn.close()
