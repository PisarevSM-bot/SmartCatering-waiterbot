import asyncio
import os
import sys
from datetime import datetime, timedelta
import logging

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import dotenv

# Импорт всех функций одной строкой (без риска SyntaxError)
from database import init_db, add_staff, update_medbook, get_staff_by_surname, get_all_staff, get_expiring_medbooks, add_to_blacklist, get_blacklist, remove_from_blacklist, staff_exists, get_staff_stats

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

dotenv.load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]
REMINDER_DAYS = [int(x.strip()) for x in os.getenv('REMINDER_DAYS', '14,3').split(',') if x.strip()]

if not BOT_TOKEN:
    logger.error("❌ Не указан BOT_TOKEN!")
    exit(1)

if not ADMIN_IDS:
    logger.warning("⚠️ Не указаны ADMIN_IDS")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
scheduler = AsyncIOScheduler(timezone='Europe/Moscow')
router = Router()

class Registration(StatesGroup):
    consent = State()
    full_name = State()
    birth_date = State()
    phone = State()
    medbook_expiry = State()

class UpdateMedbook(StatesGroup):
    medbook_expiry = State()
class BlacklistAdd(StatesGroup):
    full_name = State()
    phone = State()
    birth_date = State()
    reason = State()

def is_admin(telegram_id):
    return telegram_id in ADMIN_IDS

def validate_date(date_text):
    try:
        datetime.strptime(date_text, '%d.%m.%Y')
        return True
    except ValueError:
        return False

def validate_phone(phone):
    phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    return phone.startswith('+7') and len(phone) == 12 and phone[2:].isdigit()

def format_date_for_db(date_text):
    d = datetime.strptime(date_text, '%d.%m.%Y')
    return d.strftime('%Y-%m-%d')

def format_date_for_user(date_text):
    try:
        d = datetime.strptime(date_text, '%Y-%m-%d')
        return d.strftime('%d.%m.%Y')
    except:
        return date_text

def create_main_kb(is_admin=False):
    buttons = [
        [KeyboardButton(text="👤 Мои данные")],
        [KeyboardButton(text="🔄 Обновить медкнижку")],
        [KeyboardButton(text="ℹ️ Помощь")]
    ]
    if is_admin:
        buttons.insert(0, [KeyboardButton(text="👑 Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def create_admin_kb():
    buttons = [
        [KeyboardButton(text="🔍 Поиск по фамилии")],
        [KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="📤 Выгрузить всех")],
        [KeyboardButton(text="🚫 Чёрный список")],
        [KeyboardButton(text="⬅️ Назад")]
    ]    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if is_admin(user_id):
        await message.answer("👑 Вы администратор.", reply_markup=create_main_kb(is_admin=True))
        return
    if staff_exists(user_id):
        await message.answer("✅ Вы уже зарегистрированы!", reply_markup=create_main_kb())
        return
    await state.set_state(Registration.consent)
    await message.answer(
        "👋 Добро пожаловать!\n\n"
        "Подтвердите согласие на обработку ПДн:\n"
        "— ФИО\n— Дата рождения\n— Телефон\n— Данные о медкнижке\n\n"
        "Напишите 'Согласен' для продолжения.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Согласен")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )

@router.message(Registration.consent)
async def process_consent(message: Message, state: FSMContext):
    if message.text.lower().strip() not in ['согласен', 'согласна']:
        await message.answer("Напишите 'Согласен' для продолжения.")
        return
    await state.set_state(Registration.full_name)
    await message.answer("👤 Введите ФИО:")

@router.message(Registration.full_name)
async def process_name(message: Message, state: FSMContext):
    if len(message.text.strip()) < 5:
        await message.answer("ФИО должно содержать минимум 5 символов:")
        return
    await state.update_data(full_name=message.text.strip())
    await state.set_state(Registration.birth_date)
    await message.answer("📅 Дата рождения ДД.ММ.ГГГГ:")

@router.message(Registration.birth_date)
async def process_birth_date(message: Message, state: FSMContext):
    if not validate_date(message.text.strip()):
        await message.answer("Неверный формат. Укажите ДД.ММ.ГГГГ:")
        return
    birth_date = datetime.strptime(message.text.strip(), '%d.%m.%Y')
    age = (datetime.now() - birth_date).days / 365.25
    if age < 16:
        await message.answer("Возраст должен быть не менее 16 лет:")        
        return
    await state.update_data(birth_date=message.text.strip())
    await state.set_state(Registration.phone)
    await message.answer("📱 Телефон +79991234567:")

@router.message(Registration.phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.text.strip().replace(' ', '')
    if not validate_phone(phone):
        await message.answer("Неверный формат. Укажите +79991234567:")
        return
    await state.update_data(phone=phone)
    await state.set_state(Registration.medbook_expiry)
    await message.answer("⚕️ Дата окончания медкнижки ДД.ММ.ГГГГ:")

@router.message(Registration.medbook_expiry)
async def process_medbook(message: Message, state: FSMContext):
    if not validate_date(message.text.strip()):
        await message.answer("Неверный формат. Укажите ДД.ММ.ГГГГ:")
        return
    expiry_date = datetime.strptime(message.text.strip(), '%d.%m.%Y')
    if expiry_date < datetime.now() - timedelta(days=30):
        await message.answer("Укажите планируемую дату продления:")
        return
    data = await state.get_data()
    medbook_db = format_date_for_db(message.text.strip())
    success = add_staff(
        telegram_id=message.from_user.id,
        full_name=data['full_name'],
        birth_date=format_date_for_db(data['birth_date']),
        phone=data['phone'],
        medbook_expiry=medbook_db
    )
    if success:
        await message.answer(
            f"✅ Регистрация завершена!\n\n"
            f"ФИО: {data['full_name']}\n"
            f"Дата рождения: {data['birth_date']}\n"
            f"Телефон: {data['phone']}\n"
            f"Медкнижка до: {message.text.strip()}\n\n"
            "Напоминания за 14 и 3 дня до окончания.",
            reply_markup=create_main_kb()
        )
        logger.info(f"Новый официант: {data['full_name']} (ID: {message.from_user.id})")
    else:
        await message.answer("❌ Ошибка сохранения данных.", reply_markup=create_main_kb())
    await state.clear()

@router.message(F.text == "👤 Мои данные")
async def my_data(message: Message):    
    if not staff_exists(message.from_user.id):
        await message.answer("❌ Вы не зарегистрированы. Нажмите /start")
        return
    conn = sqlite3.connect('waiters.db')
    cursor = conn.cursor()
    cursor.execute('SELECT full_name, birth_date, phone, medbook_status, medbook_expiry FROM staff WHERE telegram_id = ?', (message.from_user.id,))
    data = cursor.fetchone()
    conn.close()
    if not 
        await message.answer("❌ Ваши данные не найдены.")
        return
    name, birth, phone, status, expiry = data
    status_text = {'действует': '✅ Действует', 'просрочена': '❌ Просрочена', 'оформляется': '🔄 Оформляется'}.get(status, status)
    await message.answer(
        f"📋 Ваши данные:\n\n"
        f"ФИО: {name}\n"
        f"Дата рождения: {format_date_for_user(birth)}\n"
        f"Телефон: {phone}\n"
        f"Медкнижка: {status_text} до {format_date_for_user(expiry)}\n\n"
        "Для обновления — нажмите «🔄 Обновить медкнижку»"
    )

@router.message(F.text == "🔄 Обновить медкнижку")
async def update_medbook_start(message: Message, state: FSMContext):
    if not staff_exists(message.from_user.id):
        await message.answer("❌ Вы не зарегистрированы. Нажмите /start")
        return
    await state.set_state(UpdateMedbook.medbook_expiry)
    await message.answer("⚕️ Новая дата окончания ДД.ММ.ГГГГ:")

@router.message(UpdateMedbook.medbook_expiry)
async def update_medbook_process(message: Message, state: FSMContext):
    if not validate_date(message.text.strip()):
        await message.answer("Неверный формат. Укажите ДД.ММ.ГГГГ:")
        return
    expiry_db = format_date_for_db(message.text.strip())
    update_medbook(message.from_user.id, expiry_db)
    await message.answer(f"✅ Срок обновлён до {message.text.strip()}", reply_markup=create_main_kb())
    await state.clear()

@router.message(F.text == "👑 Админ-панель")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора.")
        return
    await message.answer("👑 Админ-панель", reply_markup=create_admin_kb())

@router.message(F.text == "🔍 Поиск по фамилии")
async def search_start(message: Message):
    if not is_admin(message.from_user.id):        
        return
    await message.answer("🔍 Введите фамилию:")

@router.message(F.text.regexp(r'^[А-Яа-яЁё\s\-]+$'))
async def search_process(message: Message):
    if not is_admin(message.from_user.id):
        return
    surname = message.text.strip()
    results = get_staff_by_surname(surname)
    if not results:
        await message.answer("❌ Ничего не найдено.")
        return
    text = f"📋 Найдено {len(results)} сотрудников:\n\n"
    for i, (name, birth, phone, status, expiry) in enumerate(results, 1):
        status_emoji = '✅' if status == 'действует' else ('❌' if status == 'просрочена' else '🔄')
        text += f"{i}. {name}\n   ДР: {format_date_for_user(birth)}\n   Тел: {phone}\n   Медкнижка: {status_emoji} до {format_date_for_user(expiry)}\n\n"
    await message.answer(text)

@router.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    total, expired, blacklisted = get_staff_stats()
    await message.answer(f"📊 Статистика:\n\n👥 Активных: {total}\n⚠️ Просрочена: {expired}\n🚫 В ЧС: {blacklisted}")

@router.message(F.text == "📤 Выгрузить всех")
async def export_all(message: Message):
    if not is_admin(message.from_user.id):
        return
    staff = get_all_staff()
    if not staff:
        await message.answer("❌ Нет активных официантов.")
        return
    text = "ФИО | ДР | Телефон | Статус | Медкнижка до\n"
    for name, birth, phone, status, expiry in staff:
        text += f"{name} | {format_date_for_user(birth)} | {phone} | {status} | {format_date_for_user(expiry)}\n"
    if len(text) > 4096:
        parts = [text[i:i+4096] for i in range(0, len(text), 4096)]
        for part in parts:
            await message.answer(part)
    else:
        await message.answer(text)

@router.message(F.text == "🚫 Чёрный список")
async def blacklist_menu(message: Message):
    if not is_admin(message.from_user.id):
        return
    blacklist = get_blacklist()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="blacklist_add")],        
        [InlineKeyboardButton(text="🗑 Удалить запись", callback_data="blacklist_remove")]
    ])
    if blacklist:
        text = f"🚫 В чёрном списке ({len(blacklist)} чел.):\n\n"
        for i, (name, phone, reason, date) in enumerate(blacklist[:10], 1):
            date_short = datetime.fromisoformat(date).strftime('%d.%m.%Y')
            text += f"{i}. {name} ({phone or 'нет телефона'})\n   Причина: {reason}\n   Добавлен: {date_short}\n\n"
        if len(blacklist) > 10:
            text += f"... и ещё {len(blacklist) - 10} записей"
    else:
        text = "✅ Чёрный список пуст"
    await message.answer(text, reply_markup=kb)

@router.callback_query(F.data == "blacklist_add")
async def blacklist_add_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(BlacklistAdd.full_name)
    await callback.message.answer("Введите ФИО:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Отмена")]], resize_keyboard=True))

@router.message(BlacklistAdd.full_name)
async def blacklist_add_name(message: Message, state: FSMContext):
    text = message.text.strip()
    if text in ["Отмена", "отмена", "-"]:
        await state.clear()
        await message.answer("Действие отменено", reply_markup=create_admin_kb())
        return
    await state.update_data(full_name=text)
    await state.set_state(BlacklistAdd.phone)
    await message.answer("Телефон (или '-'): ")

@router.message(BlacklistAdd.phone)
async def blacklist_add_phone(message: Message, state: FSMContext):
    text = message.text.strip()
    if text in ["Отмена", "отмена", "-"]:
        await state.clear()
        await message.answer("Действие отменено", reply_markup=create_admin_kb())
        return
    phone = None if text == '-' else text
    await state.update_data(phone=phone)
    await state.set_state(BlacklistAdd.birth_date)
    await message.answer("Дата рождения ДД.ММ.ГГГГ (или '-'): ")

@router.message(BlacklistAdd.birth_date)
async def blacklist_add_birth(message: Message, state: FSMContext):
    text = message.text.strip()
    if text in ["Отмена", "отмена", "-"]:
        await state.clear()
        await message.answer("Действие отменено", reply_markup=create_admin_kb())
        return
    birth_date = None if text == '-' else text    
    await state.update_data(birth_date=birth_date)
    await state.set_state(BlacklistAdd.reason)
    await message.answer("Причина добавления в ЧС:")

@router.message(BlacklistAdd.reason)
async def blacklist_add_reason(message: Message, state: FSMContext):
    text = message.text.strip()
    if text in ["Отмена", "отмена", "-"]:
        await state.clear()
        await message.answer("Действие отменено", reply_markup=create_admin_kb())
        return
    data = await state.get_data()
    success = add_to_blacklist(data['full_name'], data.get('phone', ''), data.get('birth_date', ''), text, message.from_user.id)
    if success:
        await message.answer(f"✅ {data['full_name']} добавлен в ЧС.\nПричина: {text}", reply_markup=create_admin_kb())
        logger.info(f"Админ {message.from_user.id} добавил в ЧС: {data['full_name']}")
    else:
        await message.answer("❌ Ошибка добавления в ЧС", reply_markup=create_admin_kb())
    await state.clear()

@router.callback_query(F.data == "blacklist_remove")
async def blacklist_remove_start(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Введите ФИО для удаления из ЧС:")

@router.message(F.text.regexp(r'^[А-Яа-яЁё\s\-]+$'))
async def blacklist_remove_process(message: Message):
    if not is_admin(message.from_user.id):
        return
    count = remove_from_blacklist(message.text.strip())
    if count > 0:
        await message.answer(f"✅ Удалено {count} записей", reply_markup=create_admin_kb())
    else:
        await message.answer("❌ Записи не найдены", reply_markup=create_admin_kb())

@router.message(F.text == "⬅️ Назад")
async def back_to_main(message: Message):
    kb = create_main_kb(is_admin=is_admin(message.from_user.id))
    await message.answer("🔙 Возврат в главное меню", reply_markup=kb)

@router.message(F.text == "ℹ️ Помощь")
async def help_cmd(message: Message):
    text = "ℹ️ Справка:\n\n👤 Для официантов:\n— /start для регистрации\n— Автоматические напоминания\n\n👑 Для админов:\n— Поиск, выгрузка, ЧС\n\n🔒 Данные защищены."
    await message.answer(text)

async def send_medbook_reminders():
    logger.info("Запуск проверки напоминаний")
    for days in REMINDER_DAYS:
        expiring = get_expiring_medbooks(days)
        for tg_id, name, expiry in expiring:            days_left = (datetime.strptime(expiry, '%Y-%m-%d').date() - datetime.now().date()).days
            try:
                await bot.send_message(tg_id, f"⚠️ Напоминание!\n{name}, срок действия медкнижки истекает {format_date_for_user(expiry)} (осталось {days_left} дн.). Оформите продление!")
                logger.info(f"Напоминание отправлено {name} (ID: {tg_id}), дней до окончания: {days_left}")
            except Exception as e:
                logger.warning(f"Не удалось отправить напоминание {tg_id}: {e}")
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, f"🔔 Напоминание: у {name} истекает медкнижка {format_date_for_user(expiry)} (через {days_left} дн.)")
                except Exception as e:
                    logger.warning(f"Не удалось отправить админу {admin_id}: {e}")
    logger.info("Проверка завершена")

async def on_startup():
    init_db()
    scheduler.add_job(send_medbook_reminders, trigger=CronTrigger(hour=10, minute=0, timezone='Europe/Moscow'), id='medbook_reminders', replace_existing=True)
    scheduler.start()
    logger.info("✅ Бот запущен. Напоминания в 10:00.")

async def main():
    dp.include_router(router)
    await on_startup()
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "✅ Бот запущен и готов к работе!")
        except:
            pass
    logger.info("🚀 Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен")
    except Exception as e:
        logger.exception(f"❌ Ошибка: {e}")
    finally:
        if scheduler.running:
            scheduler.shutdown()
        logger.info("👋 Бот завершил работу")
