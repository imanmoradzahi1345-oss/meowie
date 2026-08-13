import sqlite3
import random
import time
import json
import os
import telebot
from telebot import types

# --- تنظیمات اصلی ---
TOKEN = '8968618358:AAHReb2nlduQkclIJE1V-_FKh206VxmYmuc'
ADMIN_ID = 7530457395
ADMIN_USERNAME = '@vcxczc'
DB_FILE = 'virtual_life.db'

bot = telebot.TeleBot(TOKEN)

# --- ساختار و راه‌اندازی دیتابیس SQLite ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # جدول کاربران
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        balance REAL DEFAULT 1000.0,
        level INTEGER DEFAULT 1,
        xp INTEGER DEFAULT 0,
        job_id INTEGER DEFAULT 0,
        house_id INTEGER DEFAULT 1,
        car_id INTEGER DEFAULT 0,
        spouse_id INTEGER DEFAULT 0,
        last_work INTEGER DEFAULT 0,
        last_crime INTEGER DEFAULT 0,
        last_daily INTEGER DEFAULT 0,
        missions_completed INTEGER DEFAULT 0,
        invited_by INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        created_at INTEGER DEFAULT 0
    )
    ''')
    
    # جدول خانه‌ها
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS houses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price REAL,
        income_boost REAL,
        min_level INTEGER
    )
    ''')
    
    # جدول ماشین‌ها
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cars (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price REAL,
        speed_boost REAL,
        min_level INTEGER
    )
    ''')
    
    # جدول شغل‌ها
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        min_level INTEGER,
        base_salary REAL,
        xp_reward INTEGER,
        cooldown_sec INTEGER
    )
    ''')

    # جدول مأموریت‌های کاربران
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_missions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT,
        target_count INTEGER,
        current_count INTEGER DEFAULT 0,
        reward_money REAL,
        reward_xp INTEGER,
        is_completed INTEGER DEFAULT 0
    )
    ''')

    # افزودن داده‌های اولیه پیش‌فرض در صورت خالی بودن جداول
    cursor.execute("SELECT COUNT(*) FROM jobs")
    if cursor.fetchone()[0] == 0:
        default_jobs = [
            (1, '👷 کارگر ساختمانی', 1, 150.0, 15, 60),
            (2, '🍔 پرسنل فست‌فود', 2, 300.0, 25, 60),
            (3, '🚕 راننده تاکسی', 3, 600.0, 40, 90),
            (4, '💻 برنامه‌نویس جونیور', 5, 1200.0, 70, 120),
            (5, '👨‍⚕️ پزشک عمومی', 8, 2500.0, 120, 180),
            (6, '👨‍💼 مدیر ارشد شرکت', 12, 500.0, 200, 240)
        ]
        cursor.executemany("INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?)", default_jobs)

    cursor.execute("SELECT COUNT(*) FROM houses")
    if cursor.fetchone()[0] == 0:
        default_houses = [
            (1, '🏚 چادر و اتاق کوچک', 0.0, 1.0, 1),
            (2, '🏠 خانه معمولی شهری', 15000.0, 1.15, 2),
            (3, '🏡 ویلای لوکس حومه', 75000.0, 1.35, 5),
            (4, '🏰 عمارت سلطنتی', 300000.0, 1.70, 8),
            (5, '🏙 پنت‌هاوس برج تجاری', 1000000.0, 2.20, 12)
        ]
        cursor.executemany("INSERT INTO houses VALUES (?, ?, ?, ?, ?)", default_houses)

    cursor.execute("SELECT COUNT(*) FROM cars")
    if cursor.fetchone()[0] == 0:
        default_cars = [
            (0, '🚶 پیاده (بدون ماشین)', 0.0, 1.0, 1),
            (1, '🚲 دوچرخه کوهستان', 1200.0, 1.05, 1),
            (2, '🛵 موتور سیکلت', 5000.0, 1.10, 2),
            (3, '🚗 پراید / ماشین معمولی', 20000.0, 1.20, 3),
            (4, '🏎 ماشین اسپرت', 80000.0, 1.40, 6),
            (5, '🚘 ماشین لوکس ب‌ام‌و', 250000.0, 1.70, 9),
            (6, '🏆 بوگاتی افسانه‌ای', 1200000.0, 2.20, 15)
        ]
        cursor.executemany("INSERT INTO cars VALUES (?, ?, ?, ?, ?)", default_cars)

    conn.commit()
    conn.close()

# اجرای راه‌اندازی دیتابیس
init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn
    # --- بخش ۲ از ۸: توابع کمکی دیتابیس، مدیریت سطح (Level & XP) و کیبوردها ---

def format_money(amount):
    """قالب‌بندی مبالغ مالی"""
    return f"{amount:,.0f} سکه"

def is_banned(user_id):
    """بررسی مسدود بودن کاربر"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row and row['is_banned'] == 1

def get_or_create_user(user_id, username, first_name, inviter_id=0):
    """دریافت اطلاعات کاربر یا ساخت کاربر جدید"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        # هدیه خوش‌آمدگویی و ثبت کاربر
        initial_balance = 1000.0
        created_at = int(time.time())
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, balance, level, xp, invited_by, created_at)
            VALUES (?, ?, ?, ?, 1, 0, ?, ?)
        ''', (user_id, username, first_name, initial_balance, inviter_id, created_at))
        conn.commit()

        # در صورتی که با لینک دعوت وارد شده باشد
        if inviter_id and inviter_id != user_id:
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (inviter_id,))
            inviter = cursor.fetchone()
            if inviter:
                reward = 2000.0
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, inviter_id))
                conn.commit()
                try:
                    bot.send_message(inviter_id, f"🎉 **یک کاربر جدید با لینک دعوت شما وارد شد!**\n🎁 پاداش شما: {format_money(reward)}", parse_mode="Markdown")
                except Exception:
                    pass

        # ایجاد مأموریت‌های روزانه اولیه برای کاربر جدید
        generate_daily_missions(user_id, conn)

        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
    else:
        # بروزرسانی یوزرنیم و نام در صورت تغییر
        if user['username'] != username or user['first_name'] != first_name:
            cursor.execute("UPDATE users SET username = ?, first_name = ? WHERE user_id = ?", (username, first_name, user_id))
            conn.commit()

    conn.close()
    return user

def add_xp(user_id, xp_amount):
    """افزودن XP و ارتقاء سطح (Level Up) در صورت رسیدن به حد نصاب"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT level, xp, balance FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return False, 0

    current_level = user['level']
    current_xp = user['xp'] + xp_amount
    needed_xp = current_level * 100  # فرمول محاسبه XP لازم برای Level بعد

    leveled_up = False
    new_level = current_level

    while current_xp >= needed_xp:
        current_xp -= needed_xp
        new_level += 1
        leveled_up = True
        needed_xp = new_level * 100

    if leveled_up:
        bonus = new_level * 1000.0  # پاداش ارتقاء سطح
        cursor.execute("UPDATE users SET level = ?, xp = ?, balance = balance + ? WHERE user_id = ?",
                       (new_level, current_xp, bonus, user_id))
        conn.commit()
        conn.close()
        return True, new_level
    else:
        cursor.execute("UPDATE users SET xp = ? WHERE user_id = ?", (current_xp, user_id))
        conn.commit()
        conn.close()
        return False, current_level

def generate_daily_missions(user_id, conn=None):
    """ایجاد مأموریت‌های روزانه برای کاربر"""
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    cursor = conn.cursor()
    # پاک کردن مأموریت‌های قبلی
    cursor.execute("DELETE FROM user_missions WHERE user_id = ?", (user_id,))

    missions = [
        ("💼 انجام 3 بار کار", 3, 1000.0, 50),
        ("🦹 انجام 2 بار دزدی", 2, 1500.0, 70),
        ("💰 به دست آوردن 5000 سکه", 5000, 2000.0, 100)
    ]

    for title, target, reward_m, reward_x in missions:
        cursor.execute('''
            INSERT INTO user_missions (user_id, title, target_count, current_count, reward_money, reward_xp, is_completed)
            VALUES (?, ?, ?, 0, ?, ?, 0)
        ''', (user_id, title, target, reward_m, reward_x))

    conn.commit()
    if close_conn:
        conn.close()

def update_mission_progress(user_id, mission_type, increment=1):
    """بروزرسانی پیشرفت مأموریت‌های روزانه"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM user_missions WHERE user_id = ? AND is_completed = 0", (user_id,))
    missions = cursor.fetchall()
    
    for m in missions:
        if (mission_type in m['title']) or (mission_type == 'work' and 'کار' in m['title']) or (mission_type == 'crime' and 'دزدی' in m['title']):
            new_count = m['current_count'] + increment
            if new_count >= m['target_count']:
                cursor.execute("UPDATE user_missions SET current_count = ?, is_completed = 1 WHERE id = ?", (m['target_count'], m['id']))
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (m['reward_money'], user_id))
                conn.commit()
                add_xp(user_id, m['reward_xp'])
                try:
                    bot.send_message(user_id, f"🎯 **مأموریت تکمیل شد:** {m['title']}\n🎁 پاداش: {format_money(m['reward_money'])} و {m['reward_xp']} XP!", parse_mode="Markdown")
                except Exception:
                    pass
            else:
                cursor.execute("UPDATE user_missions SET current_count = ? WHERE id = ?", (new_count, m['id']))
                conn.commit()
    conn.close()

# --- کیبوردهای اصلی ---

def main_keyboard():
    """منوی اصلی ربات (منوی کیبورد اصلی)"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_profile = types.KeyboardButton('👤 پروفایل من')
    btn_work = types.KeyboardButton('💼 کار کردن')
    btn_crime = types.KeyboardButton('🦹 دزدی و جرم')
    btn_shop = types.KeyboardButton('🛒 فروشگاه و املاک')
    btn_missions = types.KeyboardButton('🎯 مأموریت‌ها')
    btn_marriage = types.KeyboardButton('💍 ازدواج')
    btn_wallet = types.KeyboardButton('💰 کیف پول و انتقال')
    btn_leaderboard = types.KeyboardButton('🏆 رتبه‌بندی')
    btn_invite = types.KeyboardButton('🎁 دعوت دوستان')
    btn_help = types.KeyboardButton('📖 راهنما و دستورات')

    markup.add(btn_profile, btn_work)
    markup.add(btn_crime, btn_shop)
    markup.add(btn_missions, btn_marriage)
    markup.add(btn_wallet, btn_leaderboard)
    markup.add(btn_invite, btn_help)

    return markup
    # --- بخش ۳ از ۸: دستورات اصلی، پروفایل، سیستم شغل و کار، و سیستم دزدی ---

# --- دستورات اولیه (/start و راهنما) ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if is_banned(message.from_user.id):
        bot.reply_to(message, "❌ شما از استفاده از این ربات مسدود شده‌اید.")
        return

    # بررسی لینک دعوت (Deep Linking)
    args = message.text.split()
    inviter_id = 0
    if len(args) > 1 and args[1].isdigit():
        inviter_id = int(args[1])

    user = get_or_create_user(
        message.from_user.id,
        message.from_user.username or "بدون آیدی",
        message.from_user.first_name or "کاربر",
        inviter_id
    )

    text = (
        f"🌟 **به دنیای Virtual Life خوش آمدید، {message.from_user.first_name}!** 🌟\n\n"
        f"در این ربات می‌توانید زندگی مجازی خود را از صفر شروع کنید، شغل انتخاب کنید، "
        f"خانه و ماشین بخرید، دزدی کنید، ازدواج کنید و تبدیل به ثروتمندترین فرد شوید!\n\n"
        f"💰 **هدیه شروع:** {format_money(user['balance'])}\n"
        f"📊 **سطح شما:** Level {user['level']}\n\n"
        f"از دکمه‌های زیر یا دستورات متنی برای شروع استفاده کنید 👇"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard(), parse_mode="Markdown")

@bot.message_handler(commands=['help', 'commands'])
@bot.message_handler(func=lambda m: m.text in ['📖 راهنما و دستورات', 'دستورات', 'راهنما'])
def show_help(message):
    if is_banned(message.from_user.id): return
    
    help_text = (
        "📖 **راهنمای جامع دستورات ربات Virtual Life**\n\n"
        "🎮 **دستورات متنی (قابل استفاده در گروه و پیوی):**\n"
        "• `پروفایل` - مشاهده وضعیت، دارایی‌ها و لول\n"
        "• `کار` - انجام کار بر اساس شغل و دریافت درآمد\n"
        "• `دزدی` - انجام دزدی و ریسک کسب درآمد یا جریمه\n"
        "• `شغل ها` - لیست شغل‌های موجود و انتخاب شغل\n"
        "• `فروشگاه` - مشاهده لیست خانه‌ها و ماشین‌ها برای خرید\n"
        "• `ماموریت` - دریافت و مشاهده مأموریت‌های روزانه\n"
        "• `کیف پول` - مشاهده موجودی و انتقال پول\n"
        "• `انتقال [مبلغ] [آیدی یا ریپلاِی]` - انتقال پول به دیگران\n"
        "• `ازدواج` - مشاهده وضعیت تأهل یا پیشنهاد ازدواج\n"
        "• `برترین ها` - مشاهده لیست ثروتمندترین‌ها و بالاترین لول‌ها\n"
        "• `دعوت` - دریافت لینک اختصاصی دعوت از دوستان\n\n"
        "💡 *نکته:* در گروه‌ها می‌توانید مستقیماً کلمات بالا را تایپ کنید!"
    )
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

# --- نمایش پروفایل ---

def build_profile_text(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return "❌ کاربر یافت نشد."

    # شغل
    cursor.execute("SELECT title FROM jobs WHERE id = ?", (user['job_id'],))
    job_row = cursor.fetchone()
    job_title = job_row['title'] if job_row else "بدون شغل (بیکار)"

    # خانه
    cursor.execute("SELECT name FROM houses WHERE id = ?", (user['house_id'],))
    house_row = cursor.fetchone()
    house_name = house_row['name'] if house_row else "آواره"

    # ماشین
    cursor.execute("SELECT name FROM cars WHERE id = ?", (user['car_id'],))
    car_row = cursor.fetchone()
    car_name = car_row['name'] if car_row else "بدون ماشین"

    # همسر
    spouse_text = "مجرد"
    if user['spouse_id']:
        cursor.execute("SELECT first_name FROM users WHERE user_id = ?", (user['spouse_id'],))
        spouse_row = cursor.fetchone()
        spouse_text = spouse_row['first_name'] if spouse_row else "متاهل"

    conn.close()

    needed_xp = user['level'] * 100

    profile_msg = (
        f"👤 **پروفایل کاربری: {user['first_name']}**\n"
        f"🆔 شناسه: `{user['user_id']}`\n"
        f"----------------------------------\n"
        f"💰 **موجودی:** {format_money(user['balance'])}\n"
        f"⭐ **سطح (Level):** {user['level']} (XP: {user['xp']}/{needed_xp})\n"
        f"💼 **شغل:** {job_title}\n"
        f"🏠 **مسکن:** {house_name}\n"
        f"🚗 **مرکب:** {car_name}\n"
        f"💍 **وضعیت تأهل:** {spouse_text}\n"
        f"🎯 **مأموریت‌های انجام‌شده:** {user['missions_completed']}\n"
        f"----------------------------------"
    )
    return profile_msg

@bot.message_handler(func=lambda m: m.text in ['👤 پروفایل من', 'پروفایل'])
def show_profile_handler(message):
    if is_banned(message.from_user.id): return
    get_or_create_user(message.from_user.id, message.from_user.username or "بدون آیدی", message.from_user.first_name or "کاربر")
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("💼 کار کردن", callback_data="act_work"),
        types.InlineKeyboardButton("🦹 دزدی", callback_data="act_crime")
    )
    markup.add(
        types.InlineKeyboardButton("🛒 فروشگاه", callback_data="open_shop"),
        types.InlineKeyboardButton("🔄 بروزرسانی", callback_data="refresh_profile")
    )
    
    bot.send_message(message.chat.id, build_profile_text(message.from_user.id), reply_markup=markup, parse_mode="Markdown")

# --- سیستم شغل و کار ---

@bot.message_handler(func=lambda m: m.text in ['💼 کار کردن', 'کار', 'شغل ها', 'شغل‌ها'])
def work_and_job_handler(message):
    if is_banned(message.from_user.id): return
    user = get_or_create_user(message.from_user.id, message.from_user.username or "بدون آیدی", message.from_user.first_name or "کاربر")
    
    if message.text in ['شغل ها', 'شغل‌ها']:
        show_jobs_list(message.chat.id, user['user_id'])
        return

    # انجام کار
    process_work(message.chat.id, user['user_id'])

def show_jobs_list(chat_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT level FROM users WHERE user_id = ?", (user_id,))
    user_level = cursor.fetchone()['level']

    cursor.execute("SELECT * FROM jobs ORDER BY min_level ASC")
    jobs = cursor.fetchall()
    conn.close()

    text = "💼 **لیست شغل‌های موجود:**\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)

    for job in jobs:
        status = "✅ قابل انتخاب" if user_level >= job['min_level'] else f"🔒 نیازمند سطح {job['min_level']}"
        text += f"🔹 **{job['title']}**\n"
        text += f"   💰 حقوق base: {format_money(job['base_salary'])} | ⭐ XP: {job['xp_reward']} | ⏱ کول‌داون: {job['cooldown_sec']} ثانیه\n"
        text += f"   وضعیت: {status}\n\n"

        if user_level >= job['min_level']:
            markup.add(types.InlineKeyboardButton(f"استخدام در {job['title']}", callback_data=f"select_job_{job['id']}"))

    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

def process_work(chat_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if user['job_id'] == 0:
        conn.close()
        bot.send_message(chat_id, "⚠️ **شما هنوز شغلی ندارید!**\nلطفاً ابتدا از دستور `شغل ها` یک شغل انتخاب کنید.", parse_mode="Markdown")
        return

    cursor.execute("SELECT * FROM jobs WHERE id = ?", (user['job_id'],))
    job = cursor.fetchone()

    # بررسی کول‌داون
    now = int(time.time())
    elapsed = now - user['last_work']
    cooldown = job['cooldown_sec']

    if elapsed < cooldown:
        conn.close()
        bot.send_message(chat_id, f"⏳ **شما خسته هستید!**\nلطفاً `{cooldown - elapsed}` ثانیه دیگر دوباره تلاش کنید.", parse_mode="Markdown")
        return

    # محاسبه ضریب خانه و ماشین
    cursor.execute("SELECT income_boost FROM houses WHERE id = ?", (user['house_id'],))
    house_boost = cursor.fetchone()['income_boost']

    cursor.execute("SELECT speed_boost FROM cars WHERE id = ?", (user['car_id'],))
    car_boost = cursor.fetchone()['speed_boost']

    # درآمد نهایی
    earned = job['base_salary'] * house_boost * car_boost * (1 + (user['level'] * 0.05))

    # بروزرسانی دیتابیس
    cursor.execute("UPDATE users SET balance = balance + ?, last_work = ? WHERE user_id = ?", (earned, now, user_id))
    conn.commit()
    conn.close()

    # اضافه کردن XP
    leveled_up, new_lvl = add_xp(user_id, job['xp_reward'])
    
    # بروزرسانی ماموریت
    update_mission_progress(user_id, 'work')

    msg = f"💼 **کار انجام شد!**\n"
    msg += f"💵 شما به عنوان **{job['title']}** کار کردید و **{format_money(earned)}** به دست آوردید!\n"
    msg += f"⭐ **+{job['xp_reward']} XP** دریافت کردید."

    if leveled_up:
        msg += f"\n\n🎉 **تبریک! شما به سطح (Level {new_lvl}) ارتقاء یافتید!**\n🎁 پاداش سطح جدید اضافه شد."

    bot.send_message(chat_id, msg, parse_mode="Markdown")

# --- سیستم دزدی و جرم ---

@bot.message_handler(func=lambda m: m.text in ['🦹 دزدی و جرم', 'دزدی', 'جرم'])
def crime_handler(message):
    if is_banned(message.from_user.id): return
    user = get_or_create_user(message.from_user.id, message.from_user.username or "بدون آیدی", message.from_user.first_name or "کاربر")
    
    now = int(time.time())
    cooldown = 120  # 2 دقیقه
    elapsed = now - user['last_crime']

    if elapsed < cooldown:
        bot.send_message(message.chat.id, f"🚨 **پلیس در تعقیب شماست!**\nلطفاً `{cooldown - elapsed}` ثانیه دیگر صبر کنید تا اوضاع آرام شود.", parse_mode="Markdown")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    # 60٪ شانس موفقیت، 40٪ شانس دستگیری
    success = random.choice([True, True, True, False, False])

    if success:
        stolen = random.randint(500, 3000) * user['level']
        cursor.execute("UPDATE users SET balance = balance + ?, last_crime = ? WHERE user_id = ?", (stolen, now, user_id := user['user_id']))
        conn.commit()
        conn.close()

        add_xp(user['user_id'], 40)
        update_mission_progress(user['user_id'], 'crime')

        bot.send_message(message.chat.id, f"🦹‍♂️ **دزدی با موفقیت انجام شد!**\n💰 شما توانستید **{format_money(stolen)}** کش بروید و قسر در برید!\n⭐ **+40 XP**", parse_mode="Markdown")
    else:
        fine = min(user['balance'] * 0.1, 5000.0)  # جریمه ۱۰ درصد موجودی یا حداکثر ۵۰۰۰
        cursor.execute("UPDATE users SET balance = balance - ?, last_crime = ? WHERE user_id = ?", (fine, now, user['user_id']))
        conn.commit()
        conn.close()

        bot.send_message(message.chat.id, f"🚔 **دستگیر شدید!**\nپلیس شما را بازداشت کرد و مبلغ **{format_money(fine)}** جریمه شدید!", parse_mode="Markdown")
    # --- بخش ۴ از ۸: فروشگاه (خانه و ماشین)، مأموریت‌های روزانه و سیستم ازدواج ---

# --- سیستم فروشگاه (خانه و ماشین) ---

@bot.message_handler(func=lambda m: m.text in ['🛒 فروشگاه و املاک', 'فروشگاه', 'مغازه'])
def shop_main_handler(message):
    if is_banned(message.from_user.id): return
    get_or_create_user(message.from_user.id, message.from_user.username or "بدون آیدی", message.from_user.first_name or "کاربر")
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🏠 خرید خانه و املاک", callback_data="shop_houses"),
        types.InlineKeyboardButton("🚗 خرید خودرو و مرکب", callback_data="shop_cars")
    )
    
    text = "🛒 **به فروشگاه مجازی خوش آمدید!**\n\nلطفاً دسته‌بندی مورد نظر خود را انتخاب کنید:"
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("shop_") or call.data.startswith("buy_"))
def shop_callback_handler(call):
    user_id = call.from_user.id
    if is_banned(user_id): return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if call.data == "shop_houses":
        cursor.execute("SELECT * FROM houses ORDER BY min_level ASC")
        houses = cursor.fetchall()
        text = "🏠 **فروشگاه املاک و خانه‌ها:**\n\n"
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        for h in houses:
            is_owned = " (خانه فعلی شما)" if user['house_id'] == h['id'] else ""
            text += f"🔹 **{h['name']}**{is_owned}\n"
            text += f"   💰 قیمت: {format_money(h['price'])} | 📈 ضریب درآمد: {h['income_boost']}x | 🎯 سطح لازم: {h['min_level']}\n\n"
            
            if user['house_id'] != h['id']:
                markup.add(types.InlineKeyboardButton(f"خرید {h['name']}", callback_data=f"buy_house_{h['id']}"))
        
        conn.close()
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "shop_cars":
        cursor.execute("SELECT * FROM cars ORDER BY min_level ASC")
        cars = cursor.fetchall()
        text = "🚗 **فروشگاه ماشین و وسایل نقلیه:**\n\n"
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        for c in cars:
            is_owned = " (ماشین فعلی شما)" if user['car_id'] == c['id'] else ""
            text += f"🔹 **{c['name']}**{is_owned}\n"
            text += f"   💰 قیمت: {format_money(c['price'])} | 🚀 ضریب سرعت/درآمد: {c['speed_boost']}x | 🎯 سطح لازم: {c['min_level']}\n\n"
            
            if user['car_id'] != c['id'] and c['price'] > 0:
                markup.add(types.InlineKeyboardButton(f"خرید {c['name']}", callback_data=f"buy_car_{c['id']}"))
        
        conn.close()
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data.startswith("buy_house_"):
        house_id = int(call.data.split("_")[2])
        cursor.execute("SELECT * FROM houses WHERE id = ?", (house_id,))
        house = cursor.fetchone()
        
        if not house:
            conn.close()
            bot.answer_callback_query(call.id, "❌ خانه یافت نشد.", show_alert=True)
            return

        if user['level'] < house['min_level']:
            conn.close()
            bot.answer_callback_query(call.id, f"❌ برای خرید این خانه باید به سطح {house['min_level']} برسید!", show_alert=True)
            return

        if user['balance'] < house['price']:
            conn.close()
            bot.answer_callback_query(call.id, "❌ موجودی حساب شما برای خرید این خانه کافی نیست!", show_alert=True)
            return

        cursor.execute("UPDATE users SET balance = balance - ?, house_id = ? WHERE user_id = ?", (house['price'], house_id, user_id))
        conn.commit()
        conn.close()
        
        bot.answer_callback_query(call.id, "🎉 مبارکه! خانه جدید با موفقیت خریداری شد.", show_alert=True)
        bot.send_message(call.message.chat.id, f"🏡 **مبارکه!** شما خانه **{house['name']}** را به قیمت {format_money(house['price'])} خریداری کردید!", parse_mode="Markdown")

    elif call.data.startswith("buy_car_"):
        car_id = int(call.data.split("_")[2])
        cursor.execute("SELECT * FROM cars WHERE id = ?", (car_id,))
        car = cursor.fetchone()

        if not car:
            conn.close()
            bot.answer_callback_query(call.id, "❌ ماشین یافت نشد.", show_alert=True)
            return

        if user['level'] < car['min_level']:
            conn.close()
            bot.answer_callback_query(call.id, f"❌ برای خرید این ماشین باید به سطح {car['min_level']} برسید!", show_alert=True)
            return

        if user['balance'] < car['price']:
            conn.close()
            bot.answer_callback_query(call.id, "❌ موجودی شما کافی نیست!", show_alert=True)
            return

        cursor.execute("UPDATE users SET balance = balance - ?, car_id = ? WHERE user_id = ?", (car['price'], car_id, user_id))
        conn.commit()
        conn.close()

        bot.answer_callback_query(call.id, "🏎 مبارکه! ماشین جدید خریداری شد.", show_alert=True)
        bot.send_message(call.message.chat.id, f"🏎 **مبارکه!** شما ماشین **{car['name']}** را به قیمت {format_money(car['price'])} خریداری کردید!", parse_mode="Markdown")

# --- سیستم مأموریت‌های روزانه ---

@bot.message_handler(func=lambda m: m.text in ['🎯 مأموریت‌ها', 'ماموریت ها', 'ماموریت'])
def missions_handler(message):
    if is_banned(message.from_user.id): return
    user_id = message.from_user.id
    get_or_create_user(user_id, message.from_user.username or "بدون آیدی", message.from_user.first_name or "کاربر")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_missions WHERE user_id = ?", (user_id,))
    missions = cursor.fetchall()
    conn.close()

    if not missions:
        bot.send_message(message.chat.id, "🎯 **مأموریت روزانه‌ای برای شما ثبت نشده است.**", parse_mode="Markdown")
        return

    text = "🎯 **لیست مأموریت‌های روزانه شما:**\n\n"
    for m in missions:
        status = "✅ تکمیل شده" if m['is_completed'] else f"⏳ ({m['current_count']}/{m['target_count']})"
        text += f"🔹 **{m['title']}**\n"
        text += f"   وضعیت: {status}\n"
        text += f"   🎁 جایزه: {format_money(m['reward_money'])} و {m['reward_xp']} XP\n\n"

    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# --- سیستم ازدواج و خانواده ---

@bot.message_handler(func=lambda m: m.text in ['💍 ازدواج', 'ازدواج'])
def marriage_handler(message):
    if is_banned(message.from_user.id): return
    user_id = message.from_user.id
    user = get_or_create_user(user_id, message.from_user.username or "بدون آیدی", message.from_user.first_name or "کاربر")

    conn = get_db_connection()
    cursor = conn.cursor()

    if user['spouse_id']:
        cursor.execute("SELECT first_name, username FROM users WHERE user_id = ?", (user['spouse_id'],))
        spouse = cursor.fetchone()
        spouse_name = spouse['first_name'] if spouse else "نامشخص"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💔 طلاق گرفتن", callback_data="divorce_confirm"))

        text = (
            f"💍 **شما متأهل هستید!**\n\n"
            f"❤️ **همسر شما:** {spouse_name}\n"
            f"✨ با ازدواج، ۱۰٪ بونوس درآمد بر روی کلیه کارها دریافت می‌کنید!"
        )
        conn.close()
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")
    else:
        conn.close()
        text = (
            f"💍 **سیستم ازدواج Virtual Life**\n\n"
            f"شما در حال حاضر **مجرد** هستید.\n\n"
            f"📌 **روش پیشنهاد ازدواج:**\n"
            f"۱. روی پیام شخص مورد نظر ریپلاِی کنید و بگوئید: `ازدواج` یا `/propose`\n"
            f"۲. یا دستور `/propose [آیدی_عددی_یا_یوزرنیم]` را ارسال کنید."
        )
        bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['propose'])
def propose_handler(message):
    if is_banned(message.from_user.id): return
    sender_id = message.from_user.id
    sender = get_or_create_user(sender_id, message.from_user.username or "بدون آیدی", message.from_user.first_name or "کاربر")

    if sender['spouse_id']:
        bot.reply_to(message, "❌ شما قبلاً ازدواج کرده‌اید!")
        return

    target_id = None
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    else:
        args = message.text.split()
        if len(args) > 1:
            target = args[1].replace('@', '')
            conn = get_db_connection()
            cursor = conn.cursor()
            if target.isdigit():
                cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (int(target),))
            else:
                cursor.execute("SELECT user_id FROM users WHERE username = ?", (target,))
            row = cursor.fetchone()
            conn.close()
            if row:
                target_id = row['user_id']

    if not target_id:
        bot.reply_to(message, "⚠️ **لطفاً روی پیام فرد مورد نظر ریپلای کنید یا آیدی او را بنویسید.**\nمثال: `/propose @username`", parse_mode="Markdown")
        return

    if target_id == sender_id:
        bot.reply_to(message, "❌ نمی‌توانید با خودتان ازدواج کنید!")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (target_id,))
    target_user = cursor.fetchone()
    conn.close()

    if not target_user:
        bot.reply_to(message, "❌ کاربر مورد نظر در دیتابیس ثبت نشده است.")
        return

    if target_user['spouse_id']:
        bot.reply_to(message, "❌ کاربر مورد نظر متأهل است!")
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("💖 بله، می‌پذیرم", callback_data=f"accept_marry_{sender_id}"),
        types.InlineKeyboardButton("❌ خیر، رد پیشنهاد", callback_data=f"reject_marry_{sender_id}")
    )

    text = (
        f"💍 **پیشنهاد ازدواج!**\n\n"
        f"کاربر [{sender['first_name']}](tg://user?id={sender_id}) به کاربر [{target_user['first_name']}](tg://user?id={target_id}) پیشنهاد ازدواج داده است!\n"
        f"آیا این پیشنهاد را می‌پذیرید؟"
    )
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("accept_marry_") or call.data.startswith("reject_marry_") or call.data == "divorce_confirm")
def marriage_callbacks(call):
    user_id = call.from_user.id
    
    if call.data == "divorce_confirm":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT spouse_id FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        
        if user and user['spouse_id']:
            spouse_id = user['spouse_id']
            cursor.execute("UPDATE users SET spouse_id = 0 WHERE user_id = ?", (user_id,))
            cursor.execute("UPDATE users SET spouse_id = 0 WHERE user_id = ?", (spouse_id,))
            conn.commit()
            conn.close()
            
            bot.answer_callback_query(call.id, "💔 شما و همسرتان متارکه کردید.", show_alert=True)
            bot.send_message(call.message.chat.id, "💔 **طلاق انجام شد.** شما و همسرتان مجدداً مجرد شدید.", parse_mode="Markdown")
        else:
            conn.close()
            bot.answer_callback_query(call.id, "شما متأهل نیستید.", show_alert=True)
        return

    sender_id = int(call.data.split("_")[2])
    
    if call.data.startswith("accept_marry_"):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT spouse_id FROM users WHERE user_id = ?", (user_id,))
        u1 = cursor.fetchone()
        cursor.execute("SELECT spouse_id FROM users WHERE user_id = ?", (sender_id,))
        u2 = cursor.fetchone()

        if u1['spouse_id'] or u2['spouse_id']:
            conn.close()
            bot.answer_callback_query(call.id, "❌ یکی از طرفین متأهل است!", show_alert=True)
            return

        cursor.execute("UPDATE users SET spouse_id = ? WHERE user_id = ?", (sender_id, user_id))
        cursor.execute("UPDATE users SET spouse_id = ? WHERE user_id = ?", (user_id, sender_id))
        conn.commit()
        conn.close()

        bot.edit_message_text("🎉 **پیوندتان مبارک!** شما دو نفر رسماً با یکدیگر ازدواج کردید! 💍❤️", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif call.data.startswith("reject_marry_"):
        bot.edit_message_text("💔 **پیشنهاد ازدواج رد شد.**", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
                     # --- بخش ۵ از ۸: سیستم کیف پول و انتقال پول، رتبه‌بندی، دعوت دوستان و کالبک‌های پروفایل ---

# --- سیستم کیف پول و انتقال پول ---

@bot.message_handler(func=lambda m: m.text in ['💰 کیف پول و انتقال', 'کیف پول', 'انتقال'])
def wallet_handler(message):
    if is_banned(message.from_user.id): return
    user_id = message.from_user.id
    user = get_or_create_user(user_id, message.from_user.username or "بدون آیدی", message.from_user.first_name or "کاربر")

    text = (
        f"💰 **کیف پول و مدیریت دارایی**\n\n"
        f"💵 **موجودی نقدی:** {format_money(user['balance'])}\n\n"
        f"📌 **راهنمای انتقال پول:**\n"
        f"برای انتقال سکه به کاربر دیگر می‌توانید:\n"
        f"۱. روی پیام شخص مورد نظر ریپلای کرده و بنویسید: `انتقال 5000`\n"
        f"۲. یا از دستور زیر استفاده کنید:\n"
        f"`/transfer 5000 @username`\n"
        f"`/transfer 5000 12345678`"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['transfer'])
def transfer_command_handler(message):
    if is_banned(message.from_user.id): return
    sender_id = message.from_user.id
    sender = get_or_create_user(sender_id, message.from_user.username or "بدون آیدی", message.from_user.first_name or "کاربر")

    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ **فرمت دستور اشتباه است.**\nمثال: `/transfer 1000 @username` یا ریپلای بکنید: `انتقال 1000`", parse_mode="Markdown")
        return

    try:
        amount = float(args[1])
    except ValueError:
        bot.reply_to(message, "❌ لطفاً مبلغ را به عدد انگلیسی وارد کنید.")
        return

    if amount <= 0:
        bot.reply_to(message, "❌ مبلغ باید بزرگتر از صفر باشد.")
        return

    if sender['balance'] < amount:
        bot.reply_to(message, "❌ موجودی حساب شما کافی نیست.")
        return

    target_id = None
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    elif len(args) >= 3:
        target = args[2].replace('@', '')
        conn = get_db_connection()
        cursor = conn.cursor()
        if target.isdigit():
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (int(target),))
        else:
            cursor.execute("SELECT user_id FROM users WHERE username = ?", (target,))
        row = cursor.fetchone()
        conn.close()
        if row:
            target_id = row['user_id']

    if not target_id:
        bot.reply_to(message, "❌ کاربر مقصد یافت نشد.")
        return

    if target_id == sender_id:
        bot.reply_to(message, "❌ نمی‌توانید به خودتان پول منتقل کنید.")
        return

    process_transfer(message, sender_id, target_id, amount)

@bot.message_handler(func=lambda m: m.text and m.text.startswith('انتقال'))
def transfer_text_handler(message):
    if is_banned(message.from_user.id): return
    sender_id = message.from_user.id
    sender = get_or_create_user(sender_id, message.from_user.username or "بدون آیدی", message.from_user.first_name or "کاربر")

    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ **راهنمای انتقال:**\nروی پیام شخص ریپلای کنید و بنویسید: `انتقال 5000`", parse_mode="Markdown")
        return

    try:
        amount = float(parts[1])
    except ValueError:
        bot.reply_to(message, "❌ مبلغ وارد شده نامعتبر است.")
        return

    if amount <= 0:
        bot.reply_to(message, "❌ مبلغ باید بزرگتر از صفر باشد.")
        return

    if sender['balance'] < amount:
        bot.reply_to(message, "❌ موجودی شما کافی نیست.")
        return

    if not message.reply_to_message:
        bot.reply_to(message, "⚠️ برای استفاده از دستور متنی انتقال، باید روی پیام فرد مورد نظر ریپلای کنید.")
        return

    target_id = message.reply_to_message.from_user.id
    if target_id == sender_id:
        bot.reply_to(message, "❌ نمی‌توانید به خودتان پول انتقال دهید.")
        return

    process_transfer(message, sender_id, target_id, amount)

def process_transfer(message, sender_id, target_id, amount):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT balance, first_name FROM users WHERE user_id = ?", (sender_id,))
    sender = cursor.fetchone()

    cursor.execute("SELECT first_name FROM users WHERE user_id = ?", (target_id,))
    target = cursor.fetchone()

    if not target:
        conn.close()
        bot.reply_to(message, "❌ کاربر دریافت‌کننده در دیتابیس ثبت نشده است.")
        return

    if sender['balance'] < amount:
        conn.close()
        bot.reply_to(message, "❌ موجودی ناكافی است.")
        return

    # انجام تراکنش
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, sender_id))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
    conn.commit()
    conn.close()

    bot.send_message(
        message.chat.id,
        f"✅ **انتقال با موفقیت انجام شد!**\n\n"
        f"👤 فرستنده: [{sender['first_name']}](tg://user?id={sender_id})\n"
        f"👤 گیرنده: [{target['first_name']}](tg://user?id={target_id})\n"
        f"💸 مبلغ: **{format_money(amount)}**",
        parse_mode="Markdown"
    )

    try:
        bot.send_message(target_id, f"🎁 شما مبلغ **{format_money(amount)}** از طرف [{sender['first_name']}](tg://user?id={sender_id}) دریافت کردید!", parse_mode="Markdown")
    except Exception:
        pass

# --- سیستم رتبه‌بندی (Leaderboard) ---

@bot.message_handler(func=lambda m: m.text in ['🏆 رتبه‌بندی', 'رتبه‌بندی', 'رتبه', 'برترین ها', 'برترین‌ها'])
def leaderboard_handler(message):
    if is_banned(message.from_user.id): return
    get_or_create_user(message.from_user.id, message.from_user.username or "بدون آیدی", message.from_user.first_name or "کاربر")

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("💰 ثروتمندترین‌ها", callback_data="lb_richest"),
        types.InlineKeyboardButton("⭐ بالاترین Level", callback_data="lb_level")
    )

    text = "🏆 **جدول برترین‌های دنیای Virtual Life**\n\nلطفاً دسته‌بندی مورد نظر را انتخاب کنید:"
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data in ["lb_richest", "lb_level"])
def leaderboard_callbacks(call):
    if is_banned(call.from_user.id): return
    conn = get_db_connection()
    cursor = conn.cursor()

    if call.data == "lb_richest":
        cursor.execute("SELECT first_name, balance FROM users ORDER BY balance DESC LIMIT 10")
        users = cursor.fetchall()
        conn.close()

        text = "🏆 **۱۰ کاربر ثروتمند برتر:**\n\n"
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for idx, u in enumerate(users):
            medal = medals[idx] if idx < len(medals) else "🔹"
            text += f"{medal} **{u['first_name']}** - {format_money(u['balance'])}\n"

    elif call.data == "lb_level":
        cursor.execute("SELECT first_name, level, xp FROM users ORDER BY level DESC, xp DESC LIMIT 10")
        users = cursor.fetchall()
        conn.close()

        text = "⭐ **۱۰ کاربر با بالاترین سطح (Level):**\n\n"
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for idx, u in enumerate(users):
            medal = medals[idx] if idx < len(medals) else "🔹"
            text += f"{medal} **{u['first_name']}** - Level {u['level']} ({u['xp']} XP)\n"

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

# --- سیستم دعوت دوستان ---

@bot.message_handler(func=lambda m: m.text in ['🎁 دعوت دوستان', 'دعوت'])
def invite_handler(message):
    if is_banned(message.from_user.id): return
    user_id = message.from_user.id
    get_or_create_user(user_id, message.from_user.username or "بدون آیدی", message.from_user.first_name or "کاربر")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE invited_by = ?", (user_id,))
    invited_count = cursor.fetchone()['count']
    conn.close()

    bot_info = bot.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start={user_id}"

    text = (
        f"🎁 **سیستم دعوت دوستان**\n\n"
        f"با دعوت از دوستان خود به بازی، هم شما و هم دوستتان پاداش دریافت می‌کنید!\n\n"
        f"💰 **پاداش دعوت:** 2,000 سکه برای شما\n"
        f"👥 **تعداد افراد دعوت‌شده:** {invited_count} نفر\n\n"
        f"🔗 **لینک دعوت اختصاصی شما:**\n`{invite_link}`"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# --- کالبک‌های دکمه‌های شیشه‌ای پروفایل ---

@bot.callback_query_handler(func=lambda call: call.data in ["act_work", "act_crime", "open_shop", "refresh_profile"])
def profile_quick_actions(call):
    user_id = call.from_user.id
    if is_banned(user_id): return

    if call.data == "act_work":
        process_work(call.message.chat.id, user_id)
        bot.answer_callback_query(call.id)
    elif call.data == "act_crime":
        now = int(time.time())
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()

        cooldown = 120
        elapsed = now - user['last_crime']

        if elapsed < cooldown:
            conn.close()
            bot.answer_callback_query(call.id, f"🚨 پلیس در تعقیب شماست! {cooldown - elapsed} ثانیه صبر کنید.", show_alert=True)
            return

        success = random.choice([True, True, True, False, False])
        if success:
            stolen = random.randint(500, 3000) * user['level']
            cursor.execute("UPDATE users SET balance = balance + ?, last_crime = ? WHERE user_id = ?", (stolen, now, user_id))
            conn.commit()
            conn.close()
            add_xp(user_id, 40)
            update_mission_progress(user_id, 'crime')
            bot.answer_callback_query(call.id, f"🦹 موفق! +{format_money(stolen)}", show_alert=True)
        else:
            fine = min(user['balance'] * 0.1, 5000.0)
            cursor.execute("UPDATE users SET balance = balance - ?, last_crime = ? WHERE user_id = ?", (fine, now, user_id))
            conn.commit()
            conn.close()
            bot.answer_callback_query(call.id, f"🚔 دستگیر شدید! جریمه: {format_money(fine)}", show_alert=True)

    elif call.data == "open_shop":
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🏠 خرید خانه و املاک", callback_data="shop_houses"),
            types.InlineKeyboardButton("🚗 خرید خودرو و مرکب", callback_data="shop_cars")
        )
        bot.send_message(call.message.chat.id, "🛒 **به فروشگاه مجازی خوش آمدید!**", reply_markup=markup, parse_mode="Markdown")

    elif call.data == "refresh_profile":
        bot.answer_callback_query(call.id, "🔄 پروفایل بروزرسانی شد.")
        try:
            bot.edit_message_text(build_profile_text(user_id), call.message.chat.id, call.message.message_id, reply_markup=call.message.reply_markup, parse_mode="Markdown")
        except Exception:
            pass
# --- بخش ۶ از ۸: پنل مدیریت (Admin Panel) - آمار، لیست کاربران، تغییر موجودی، تغییر لول و بن/آن‌بن ---

def is_admin(user_id):
    """بررسی دسترسی ادمین"""
    return str(user_id) == str(ADMIN_ID)

def admin_keyboard():
    """منوی کیبورد شیشه‌ای ادمین"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 آمار کامل ربات", callback_data="admin_stats"),
        types.InlineKeyboardButton("👥 لیست کاربران", callback_data="admin_users_list")
    )
    markup.add(
        types.InlineKeyboardButton("💰 تغییر موجودی کاربر", callback_data="admin_change_balance"),
        types.InlineKeyboardButton("⭐ تغییر لول/XP کاربر", callback_data="admin_change_level")
    )
    markup.add(
        types.InlineKeyboardButton("🚫 مسدود/رفع مسدودی", callback_data="admin_ban_unban"),
        types.InlineKeyboardButton("🔍 جستجوی کاربر", callback_data="admin_search_user")
    )
    markup.add(
        types.InlineKeyboardButton("➕ افزودن خانه/ماشین جدید", callback_data="admin_add_item"),
        types.InlineKeyboardButton("🏷 تغییر قیمت آیتم‌ها", callback_data="admin_edit_prices")
    )
    markup.add(
        types.InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin_broadcast")
    )
    return markup

@bot.message_handler(commands=['admin'])
@bot.message_handler(func=lambda m: m.text in ['پنل ادمین', 'مدیریت'] and is_admin(m.from_user.id))
def admin_panel_handler(message):
    if not is_admin(message.from_user.id): return
    
    bot.send_message(
        message.chat.id,
        f"🛠 **پنل مدیریت ربات Virtual Life**\n\nخوش آمدید مدیر گرامی ({ADMIN_USERNAME})!\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=admin_keyboard(),
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_") and is_admin(call.from_user.id))
def admin_callbacks(call):
    action = call.data
    
    if action == "admin_stats":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM users")
        total_users = cursor.fetchone()['total']
        cursor.execute("SELECT SUM(balance) as total_bal FROM users")
        total_bal = cursor.fetchone()['total_bal'] or 0
        cursor.execute("SELECT COUNT(*) as banned FROM users WHERE is_banned = 1")
        banned_users = cursor.fetchone()['banned']
        conn.close()

        stats_msg = (
            f"📊 **آمار کلی ربات:**\n\n"
            f"👥 **تعداد کل کاربران:** {total_users} نفر\n"
            f"💰 **مجموع پول در گردش:** {format_money(total_bal)}\n"
            f"🚫 **تعداد کاربران مسدود:** {banned_users} نفر"
        )
        bot.edit_message_text(stats_msg, call.message.chat.id, call.message.message_id, reply_markup=admin_keyboard(), parse_mode="Markdown")

    elif action == "admin_users_list":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, first_name, balance, level FROM users ORDER BY created_at DESC LIMIT 20")
        users = cursor.fetchall()
        conn.close()

        text = "👥 **آخرین ۲۰ کاربر ثبت‌شده:**\n\n"
        for u in users:
            uname = f"@{u['username']}" if u['username'] and u['username'] != "بدون آیدی" else "بدون یوزرنیم"
            text += f"👤 [{u['first_name']}](tg://user?id={u['user_id']}) | `{u['user_id']}`\n"
            text += f"   یوزرنیم: {uname} | سکه: {format_money(u['balance'])} | Level: {u['level']}\n\n"

        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=admin_keyboard(), parse_mode="Markdown")

    elif action == "admin_change_balance":
        msg = bot.send_message(call.message.chat.id, "💰 **آیدی عددی کاربر و مقدار جدید سکه را بفرستید:**\n\nفرمت: `آیدی_عددی مقدار`\nمثال: `7530457395 50000`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_admin_change_balance)

    elif action == "admin_change_level":
        msg = bot.send_message(call.message.chat.id, "⭐ **آیدی عددی کاربر و لول جدید را بفرستید:**\n\nفرمت: `آیدی_عددی لول`\nمثال: `7530457395 10`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_admin_change_level)

    elif action == "admin_ban_unban":
        msg = bot.send_message(call.message.chat.id, "🚫 **آیدی عددی کاربر را برای مسدود/رفع مسدودی ارسال کنید:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_admin_ban_unban)

    elif action == "admin_search_user":
        msg = bot.send_message(call.message.chat.id, "🔍 **آیدی عددی یا یوزرنیم کاربر را وارد کنید:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_admin_search_user)

# --- توابع پردازش مراحل ادمین ---

def process_admin_change_balance(message):
    if not is_admin(message.from_user.id): return
    try:
        parts = message.text.split()
        uid = int(parts[0])
        new_bal = float(parts[1])

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_bal, uid))
        conn.commit()
        conn.close()

        bot.send_message(message.chat.id, f"✅ موجودی کاربر `{uid}` با موفقیت به **{format_money(new_bal)}** تغییر یافت.", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطایی رخ داد: {str(e)}\nلطفاً طبق فرمت مشخص‌شده وارد کنید.")

def process_admin_change_level(message):
    if not is_admin(message.from_user.id): return
    try:
        parts = message.text.split()
        uid = int(parts[0])
        new_lvl = int(parts[1])

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET level = ? WHERE user_id = ?", (new_lvl, uid))
        conn.commit()
        conn.close()

        bot.send_message(message.chat.id, f"✅ سطح (Level) کاربر `{uid}` به **{new_lvl}** تغییر یافت.", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطایی رخ داد: {str(e)}")

def process_admin_ban_unban(message):
    if not is_admin(message.from_user.id): return
    try:
        uid = int(message.text.strip())
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (uid,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            bot.send_message(message.chat.id, "❌ کاربر یافت نشد.")
            return

        new_status = 0 if row['is_banned'] == 1 else 1
        cursor.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (new_status, uid))
        conn.commit()
        conn.close()

        status_text = "مسدود (Ban) شد" if new_status == 1 else "رفع مسدودی (Unban) شد"
        bot.send_message(message.chat.id, f"✅ کاربر `{uid}` با موفقیت {status_text}.", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطایی رخ داد: {str(e)}")

def process_admin_search_user(message):
    if not is_admin(message.from_user.id): return
    query = message.text.strip().replace('@', '')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    if query.isdigit():
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (int(query),))
    else:
        cursor.execute("SELECT * FROM users WHERE username = ?", (query,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        bot.send_message(message.chat.id, "❌ کاربری با این مشخصات یافت نشد.")
        return

    banned_str = "بله 🚫" if user['is_banned'] else "خیر ✅"
    text = (
        f"🔍 **اطلاعات کاربر یافت شده:**\n\n"
        f"👤 **نام:** {user['first_name']}\n"
        f"🆔 **آیدی عددی:** `{user['user_id']}`\n"
        f"🏷 **یوزرنیم:** @{user['username']}\n"
        f"💰 **موجودی:** {format_money(user['balance'])}\n"
        f"⭐ **لول:** {user['level']} (XP: {user['xp']})\n"
        f"🚫 **مسدود:** {banned_str}"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")
# --- بخش ۷ از ۸: پنل مدیریت (افزودن خانه/ماشین جدید، تغییر قیمت‌ها و ارسال پیام همگانی) ---

@bot.callback_query_handler(func=lambda call: call.data in ["admin_add_item", "admin_edit_prices", "admin_broadcast"] and is_admin(call.from_user.id))
def admin_extra_callbacks(call):
    action = call.data

    if action == "admin_add_item":
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🏠 افزودن خانه جدید", callback_data="add_new_house"),
            types.InlineKeyboardButton("🚗 افزودن ماشین جدید", callback_data="add_new_car")
        )
        bot.edit_message_text("➕ **ایجاد آیتم جدید:**\n\nکدام نوع آیتم را می‌خواهید اضافه کنید؟", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif action == "admin_edit_prices":
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🏚 تغییر قیمت خانه‌ها", callback_data="edit_price_house"),
            types.InlineKeyboardButton("🚘 تغییر قیمت ماشین‌ها", callback_data="edit_price_car")
        )
        bot.edit_message_text("🏷 **تغییر قیمت آیتم‌ها:**\n\nکدام دسته را می‌خواهید ویرایش کنید؟", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif action == "admin_broadcast":
        msg = bot.send_message(call.message.chat.id, "📢 **پیام همگانی خود را بنویسید و ارسال کنید:**\n\n(این پیام برای تمام کاربران ثبت‌شده ارسال خواهد شد)", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_admin_broadcast)

@bot.callback_query_handler(func=lambda call: call.data in ["add_new_house", "add_new_car", "edit_price_house", "edit_price_car"] and is_admin(call.from_user.id))
def admin_items_action_callbacks(call):
    if call.data == "add_new_house":
        msg = bot.send_message(
            call.message.chat.id,
            "🏠 **مشخصات خانه جدید را ارسال کنید:**\n\nفرمت: `نام_خانه,قیمت,ضریب_درآمد,سطح_لازم`\nمثال: `پنت‌هاوس الماس,5000000,3.5,15`",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_add_house)

    elif call.data == "add_new_car":
        msg = bot.send_message(
            call.message.chat.id,
            "🚗 **مشخصات ماشین جدید را ارسال کنید:**\n\nفرمت: `نام_ماشین,قیمت,ضریب_سرعت,سطح_لازم`\nمثال: `لامبورگینی,3500000,2.8,12`",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_add_car)

    elif call.data == "edit_price_house":
        msg = bot.send_message(
            call.message.chat.id,
            "🏚 **تغییر قیمت خانه:**\n\nفرمت: `کد_خانه قیمت_جدید`\nمثال: `2 25000`",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_edit_house_price)

    elif call.data == "edit_price_car":
        msg = bot.send_message(
            call.message.chat.id,
            "🚘 **تغییر قیمت ماشین:**\n\nفرمت: `کد_ماشین قیمت_جدید`\nمثال: `3 35000`",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_edit_car_price)

# --- توابع پردازش مراحل ادمین (Next Step Handlers) ---

def process_add_house(message):
    if not is_admin(message.from_user.id): return
    try:
        parts = message.text.split(',')
        name = parts[0].strip()
        price = float(parts[1].strip())
        boost = float(parts[2].strip())
        min_lvl = int(parts[3].strip())

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO houses (name, price, income_boost, min_level) VALUES (?, ?, ?, ?)", (name, price, boost, min_lvl))
        conn.commit()
        conn.close()

        bot.send_message(message.chat.id, f"✅ خانه جدید **«{name}»** با موفقیت به فروشگاه اضافه شد!", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطایی رخ داد: {str(e)}\nلطفاً طبق فرمت مشخص‌شده ارسال کنید.")

def process_add_car(message):
    if not is_admin(message.from_user.id): return
    try:
        parts = message.text.split(',')
        name = parts[0].strip()
        price = float(parts[1].strip())
        boost = float(parts[2].strip())
        min_lvl = int(parts[3].strip())

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO cars (name, price, speed_boost, min_level) VALUES (?, ?, ?, ?)", (name, price, boost, min_lvl))
        conn.commit()
        conn.close()

        bot.send_message(message.chat.id, f"✅ ماشین جدید **«{name}»** با موفقیت به فروشگاه اضافه شد!", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطایی رخ داد: {str(e)}\nلطفاً طبق فرمت مشخص‌شده ارسال کنید.")

def process_edit_house_price(message):
    if not is_admin(message.from_user.id): return
    try:
        parts = message.text.split()
        house_id = int(parts[0])
        new_price = float(parts[1])

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE houses SET price = ? WHERE id = ?", (new_price, house_id))
        conn.commit()
        conn.close()

        bot.send_message(message.chat.id, f"✅ قیمت خانه کد `{house_id}` به **{format_money(new_price)}** تغییر یافت.", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطایی رخ داد: {str(e)}")

def process_edit_car_price(message):
    if not is_admin(message.from_user.id): return
    try:
        parts = message.text.split()
        car_id = int(parts[0])
        new_price = float(parts[1])

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE cars SET price = ? WHERE id = ?", (new_price, car_id))
        conn.commit()
        conn.close()

        bot.send_message(message.chat.id, f"✅ قیمت ماشین کد `{car_id}` به **{format_money(new_price)}** تغییر یافت.", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطایی رخ داد: {str(e)}")

def process_admin_broadcast(message):
    if not is_admin(message.from_user.id): return
    
    broadcast_text = message.text
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()

    success = 0
    failed = 0

    status_msg = bot.send_message(message.chat.id, "⏳ در حال ارسال پیام به تمام کاربران...")

    for u in users:
        try:
            bot.send_message(u['user_id'], f"📢 **پیام مدیریت:**\n\n{broadcast_text}", parse_mode="Markdown")
            success += 1
            time.sleep(0.05)
        except Exception:
            failed += 1

    bot.edit_message_text(f"✅ **ارسال پیام همگانی به پایان رسید.**\n\nموفق: {success}\nناموفق (بلاک/لغو): {failed}", message.chat.id, status_msg.message_id, parse_mode="Markdown")
    # --- بخش ۸ از ۸ (پایانی): پشتیبانی گروه‌ها و اجرای اصلی ربات ---

# --- هندلر میانبر برای دستورات متنی در گروه و پیوی ---

@bot.message_handler(func=lambda m: m.text and any(k in m.text for k in ['دستورات', 'راهنما', 'راهنمایی', 'کلمات دستورات']))
def group_help_shortcut(message):
    if is_banned(message.from_user.id): return
    show_help(message)

# --- مدیریت پیام‌های متفرقه در پیوی ---

@bot.message_handler(content_types=['text', 'photo', 'sticker', 'animation'])
def fallback_handler(message):
    # در گروه‌ها پیام‌های متفرقه نادیده گرفته می‌شوند تا مزاحمت ایجاد نشود
    if message.chat.type != 'private':
        return
    
    if is_banned(message.from_user.id): return
    
    bot.send_message(
        message.chat.id,
        "⚠️ **دستور متوجه شده نشد!**\nلطفاً از دکمه‌های منو استفاده کنید یا کلمه **دستورات** را تایپ کنید.",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )

# --- اجرای اصلی ربات (Main Entry Point) ---

if __name__ == '__main__':
    print("========================================")
    print("🤖 ربات Virtual Life با موفقیت فعال شد!")
    print(f"🆔 آیدی ادمین اصلی: {ADMIN_ID}")
    print("========================================")
    
    # اجرای بی‌وقفه ربات و نادیده گرفتن پیام‌های زمان خاموشی
    try:
        bot.infinity_polling(skip_pending=True)
    except Exception as e:
        print(f"❌ خطای غیرمنتظره در اجرای ربات: {e}")
    
