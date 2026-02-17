import os
import asyncpg
from datetime import datetime

# Получаем URL из переменных Railway
DB_URL = os.getenv("DATABASE_URL")

async def init_db():
    """Инициализация базы данных"""
    conn = await asyncpg.connect(DB_URL)
    try:
        # Таблица активных официантов
        await conn.execute('''
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
        
        # Таблица чёрного списка
        await conn.execute('''
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
        
        # Индексы для ускорения поиска
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_staff_name ON staff(full_name)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_staff_expiry ON staff(medbook_expiry)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_blacklist_name ON blacklist(full_name)')
        
        print("✅ База данных инициализирована")
    finally:
        await conn.close()

async def add_staff(telegram_id, full_name, birth_date, phone, medbook_expiry):    """Добавление нового официанта"""
    conn = await asyncpg.connect(DB_URL)
    try:
        await conn.execute('''
            INSERT INTO staff 
            (telegram_id, full_name, birth_date, phone, medbook_status, medbook_expiry, consent_given, updated_at)
            VALUES ($1, $2, $3, $4, 'действует', $5, TRUE, NOW())
            ON CONFLICT (telegram_id) 
            DO UPDATE SET
                full_name = $2,
                birth_date = $3,
                phone = $4,
                medbook_expiry = $5,
                updated_at = NOW()
        ''', telegram_id, full_name, birth_date, phone, medbook_expiry)
        return True
    except Exception as e:
        print(f"Ошибка добавления: {e}")
        return False
    finally:
        await conn.close()

async def update_medbook(telegram_id, medbook_expiry):
    """Обновление срока медкнижки"""
    conn = await asyncpg.connect(DB_URL)
    try:
        await conn.execute('''
            UPDATE staff 
            SET medbook_expiry = $1, updated_at = NOW() 
            WHERE telegram_id = $2
        ''', medbook_expiry, telegram_id)
    finally:
        await conn.close()

async def get_staff_by_surname(surname):
    """Поиск официантов по фамилии"""
    conn = await asyncpg.connect(DB_URL)
    try:
        results = await conn.fetch('''
            SELECT full_name, birth_date, phone, medbook_status, medbook_expiry 
            FROM staff 
            WHERE full_name ILIKE $1 
            ORDER BY full_name
        ''', f'%{surname}%')
        return results
    finally:
        await conn.close()

async def get_all_staff():
    """Получить всех официантов"""    conn = await asyncpg.connect(DB_URL)
    try:
        results = await conn.fetch('''
            SELECT full_name, birth_date, phone, medbook_status, medbook_expiry 
            FROM staff 
            ORDER BY full_name
        ''')
        return results
    finally:
        await conn.close()

async def get_expiring_medbooks(days_ahead):
    """Получить официантов с истекающей медкнижкой"""
    conn = await asyncpg.connect(DB_URL)
    try:
        results = await conn.fetch('''
            SELECT telegram_id, full_name, medbook_expiry 
            FROM staff 
            WHERE medbook_status = 'действует' 
              AND medbook_expiry BETWEEN CURRENT_DATE AND CURRENT_DATE + $1
              AND consent_given = TRUE
            ORDER BY medbook_expiry
        ''', days_ahead)
        return results
    finally:
        await conn.close()

async def add_to_blacklist(full_name, phone, birth_date, reason, admin_id):
    """Добавить в чёрный список"""
    conn = await asyncpg.connect(DB_URL)
    try:
        # Сначала получаем данные из активных (если есть)
        existing = await conn.fetchrow('SELECT phone, birth_date FROM staff WHERE full_name = $1', full_name)
        if existing:
            phone = existing['phone'] or phone
            birth_date = existing['birth_date'] or birth_date
        
        # Добавляем в ЧС
        await conn.execute('''
            INSERT INTO blacklist (full_name, phone, birth_date, reason, added_by)
            VALUES ($1, $2, $3, $4, $5)
        ''', full_name, phone, birth_date, reason, admin_id)
        
        # Удаляем из активных
        await conn.execute('DELETE FROM staff WHERE full_name = $1', full_name)
        return True
    finally:
        await conn.close()

async def remove_from_blacklist(full_name):    """Удалить из чёрного списка"""
    conn = await asyncpg.connect(DB_URL)
    try:
        result = await conn.execute('DELETE FROM blacklist WHERE full_name ILIKE $1', f'%{full_name}%')
        count = int(result.split()[1])  # "DELETE 3" → 3
        return count
    finally:
        await conn.close()

async def get_blacklist():
    """Получить весь чёрный список"""
    conn = await asyncpg.connect(DB_URL)
    try:
        results = await conn.fetch('''
            SELECT full_name, phone, reason, blacklisted_at 
            FROM blacklist 
            ORDER BY blacklisted_at DESC
        ''')
        return results
    finally:
        await conn.close()

async def staff_exists(telegram_id):
    """Проверить, зарегистрирован ли официант"""
    conn = await asyncpg.connect(DB_URL)
    try:
        result = await conn.fetchval('SELECT 1 FROM staff WHERE telegram_id = $1', telegram_id)
        return result is not None
    finally:
        await conn.close()

async def get_staff_stats():
    """Статистика по базе"""
    conn = await asyncpg.connect(DB_URL)
    try:
        total = await conn.fetchval('SELECT COUNT(*) FROM staff')
        expired = await conn.fetchval("SELECT COUNT(*) FROM staff WHERE medbook_status = 'просрочена'")
        blacklisted = await conn.fetchval('SELECT COUNT(*) FROM blacklist')
        return total, expired, blacklisted
    finally:
        await conn.close()
