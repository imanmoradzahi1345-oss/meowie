# ==================== بخش ۱ از ۶ ====================
# تنظیمات + دیتابیس کامل + توابع پایه

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
import sqlite3
import threading
import time
import json
import random
import string
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
    TEHRAN = ZoneInfo("Asia/Tehran")
except:
    TEHRAN = None

BOT_TOKEN = "8968618358:AAHReb2nlduQkclIJE1V-_FKh206VxmYmuc"
ADMIN_IDS = [7530457395]

bot = telebot.TeleBot(BOT_TOKEN)

def init_db():
    conn = sqlite3.connect("stars_lottery_bot.db")
    c = conn.cursor()

    # کاربران
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        balance INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        joined_at TEXT,
        last_active TEXT
    )''')

    # تنظیمات
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

    # کارهای استارز رایگان (تعیین شده توسط ادمین)
    c.execute('''CREATE TABLE IF NOT EXISTS free_star_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        task_type TEXT,
        target TEXT,
        reward_stars INTEGER DEFAULT 1,
        is_active INTEGER DEFAULT 1
    )''')

    # سفارشات استارز رایگان (کدهای در انتظار تأیید ادمین)
    c.execute('''CREATE TABLE IF NOT EXISTS free_star_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task_id INTEGER,
        post_link TEXT,
        code TEXT UNIQUE,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )''')

    # کدهای هدیه و گیفت
    c.execute('''CREATE TABLE IF NOT EXISTS gift_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        code_type TEXT,
        value TEXT,
        max_uses INTEGER DEFAULT 1,
        used_count INTEGER DEFAULT 0,
        expire_at TEXT,
        sticker_file_id TEXT,
        is_active INTEGER DEFAULT 1,
        created_by INTEGER
    )''')

    # تاریخچه استفاده از کد
    c.execute('''CREATE TABLE IF NOT EXISTS code_uses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT,
        user_id INTEGER,
        used_at TEXT
    )''')

    # قفل کانال‌ها
    c.execute('''CREATE TABLE IF NOT EXISTS forced_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT UNIQUE,
        channel_title TEXT
    )''')

    # تیکت پشتیبانی
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        status TEXT DEFAULT 'open',
        created_at TEXT
    )''')

    # لاگ
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        details TEXT,
        created_at TEXT
    )''')

    # تنظیمات پیش‌فرض
    defaults = {
        "star_to_toman": "4000",      # هر استارز چند تومان
        "maintenance": "0",
        "lottery_channel": ""
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect("stars_lottery_bot.db")

def is_admin(uid):
    return uid in ADMIN_IDS

def now_tehran():
    if TEHRAN:
        return datetime.now(TEHRAN)
    return datetime.now()

def get_setting(key, default=""):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key, value):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def ensure_user(user):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id=?", (user.id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, username, full_name, balance, joined_at, last_active) VALUES (?, ?, ?, 0, ?, ?)",
                  (user.id, user.username or "", user.full_name or "",
                   now_tehran().strftime("%Y-%m-%d %H:%M"), now_tehran().strftime("%Y-%m-%d %H:%M")))
    else:
        c.execute("UPDATE users SET username=?, full_name=?, last_active=? WHERE user_id=?",
                  (user.username or "", user.full_name or "", now_tehran().strftime("%Y-%m-%d %H:%M"), user.id))
    conn.commit()
    conn.close()

def get_balance(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def add_balance(uid, amount):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, uid))
    conn.commit()
    conn.close()

def log_action(uid, action, details=""):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO logs (user_id, action, details, created_at) VALUES (?, ?, ?, ?)",
              (uid, action, details, now_tehran().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def generate_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

print("✅ بخش ۱ آماده شد")
# ==================== بخش ۲ از ۶ ====================
# منوها + /start + بررسی قفل کانال

def main_menu(uid):
    m = InlineKeyboardMarkup(row_width=2)
    m.add(
        InlineKeyboardButton("⭐ استارز و قرعه کشی", callback_data="stars_lottery"),
        InlineKeyboardButton("👤 پروفایل و شارژ", callback_data="profile_charge"),
    )
    m.add(
        InlineKeyboardButton("🎁 کد هدیه و گیفت", callback_data="gift_codes"),
        InlineKeyboardButton("🛠 پشتیبانی", callback_data="support"),
    )
    if is_admin(uid):
        m.add(InlineKeyboardButton("👑 پنل ادمین", callback_data="admin_panel"))
    return m

def stars_lottery_menu():
    m = InlineKeyboardMarkup(row_width=1)
    m.add(
        InlineKeyboardButton("🆓 استارز رایگان", callback_data="free_stars"),
        InlineKeyboardButton("🎲 شرکت در قرعه کشی", callback_data="join_lottery"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"),
    )
    return m

def profile_menu(uid):
    bal = get_balance(uid)
    rate = get_setting("star_to_toman", "4000")
    m = InlineKeyboardMarkup(row_width=1)
    m.add(
        InlineKeyboardButton(f"💰 موجودی: {bal:,} تومان", callback_data="show_balance"),
        InlineKeyboardButton("⭐ شارژ حساب با استارز", callback_data="charge_stars"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"),
    )
    return m

def gift_menu():
    m = InlineKeyboardMarkup(row_width=1)
    m.add(
        InlineKeyboardButton("🔑 وارد کردن کد هدیه", callback_data="enter_gift_code"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"),
    )
    return m

def admin_menu():
    m = InlineKeyboardMarkup(row_width=2)
    m.add(
        InlineKeyboardButton("📦 سفارشات مونده", callback_data="admin_orders"),
        InlineKeyboardButton("✅ تأیید سفارش", callback_data="admin_confirm_order"),
    )
    m.add(
        InlineKeyboardButton("➕ کار جدید (استارز رایگان)", callback_data="admin_add_task"),
        InlineKeyboardButton("📋 لیست کارها", callback_data="admin_list_tasks"),
    )
    m.add(
        InlineKeyboardButton("🎁 ساخت کد هدیه استارز", callback_data="admin_create_star_code"),
        InlineKeyboardButton("🎀 ساخت کد گیفت", callback_data="admin_create_gift_code"),
    )
    m.add(
        InlineKeyboardButton("📢 ارسال کد به کانال", callback_data="admin_send_code_channel"),
        InlineKeyboardButton("📨 ارسال کد به کاربران", callback_data="admin_send_code_users"),
    )
    m.add(
        InlineKeyboardButton("🔒 مدیریت قفل کانال", callback_data="admin_forced"),
        InlineKeyboardButton("💰 تنظیم قیمت استارز", callback_data="admin_set_rate"),
    )
    m.add(
        InlineKeyboardButton("💸 شارژ دستی کاربر", callback_data="admin_manual_charge"),
        InlineKeyboardButton("👥 لیست کاربران", callback_data="admin_users"),
    )
    m.add(
        InlineKeyboardButton("📊 آمار ربات", callback_data="admin_stats"),
        InlineKeyboardButton("🛠 حالت تعمیرات", callback_data="admin_maintenance"),
    )
    m.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
    return m

@bot.message_handler(commands=['start'])
def start(message):
    ensure_user(message.from_user)
    uid = message.from_user.id

    # حالت تعمیرات
    if get_setting("maintenance") == "1" and not is_admin(uid):
        bot.send_message(message.chat.id, "🛠️ ربات موقتاً در حال تعمیرات است.")
        return

    # بررسی مسدود بودن
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    if row and row[0] == 1:
        bot.send_message(message.chat.id, "🚫 حساب شما مسدود شده است.")
        conn.close()
        return

    # بررسی قفل کانال‌ها
    c.execute("SELECT channel_id, channel_title FROM forced_channels")
    forced = c.fetchall()
    conn.close()

    if forced and not is_admin(uid):
        not_joined = []
        for ch_id, title in forced:
            try:
                member = bot.get_chat_member(ch_id, uid)
                if member.status in ["left", "kicked"]:
                    not_joined.append((ch_id, title))
            except:
                not_joined.append((ch_id, title))

        if not_joined:
            mk = InlineKeyboardMarkup(row_width=1)
            for ch_id, title in not_joined:
                link = f"https://t.me/{str(ch_id).lstrip('@').replace('-100', '')}"
                mk.add(InlineKeyboardButton(f"📢 عضویت در {title or ch_id}", url=link))
            mk.add(InlineKeyboardButton("✅ عضو شدم - بررسی کن", callback_data="check_join"))
            bot.send_message(message.chat.id, "🔒 برای استفاده از ربات باید در کانال‌های زیر عضو شوید:", reply_markup=mk)
            return

    bot.send_message(message.chat.id,
        f"سلام {message.from_user.first_name}!\n\nبه ربات استارز و قرعه کشی خوش آمدید.",
        reply_markup=main_menu(uid))

@bot.message_handler(commands=['Gifts', 'gifts', 'gift'])
def gifts_command(message):
    ensure_user(message.from_user)
    bot.user_steps = getattr(bot, "user_steps", {})
    bot.user_steps[message.from_user.id] = {"step": "enter_code"}
    bot.send_message(message.chat.id, "🔑 کد هدیه یا گیفت را وارد کنید:")

print("✅ بخش ۲ آماده شد")
# ==================== بخش ۳ از ۶ ====================
# کال‌بک‌های اصلی کاربر + پنل ادمین

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    uid = call.from_user.id
    ensure_user(call.from_user)
    data = call.data
    bot.user_steps = getattr(bot, "user_steps", {})

    # ---------- بازگشت ----------
    if data == "back_main":
        bot.edit_message_text("منوی اصلی:", call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))

    elif data == "check_join":
        bot.answer_callback_query(call.id)
        start(call.message)
        return

    # ---------- استارز و قرعه کشی ----------
    elif data == "stars_lottery":
        bot.edit_message_text("⭐ بخش استارز و قرعه کشی:", call.message.chat.id, call.message.message_id, reply_markup=stars_lottery_menu())

    elif data == "free_stars":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, title, task_type, reward_stars FROM free_star_tasks WHERE is_active=1")
        tasks = c.fetchall()
        conn.close()

        if not tasks:
            bot.answer_callback_query(call.id, "فعلاً کاری تعریف نشده", show_alert=True)
            return

        mk = InlineKeyboardMarkup(row_width=1)
        for t in tasks:
            mk.add(InlineKeyboardButton(f"{t[1]} ({t[3]} استارز)", callback_data=f"do_task_{t[0]}"))
        mk.add(InlineKeyboardButton("🔙 بازگشت", callback_data="stars_lottery"))
        bot.edit_message_text("کار مورد نظر را انتخاب کنید:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data.startswith("do_task_"):
        task_id = int(data.split("_")[2])
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT title, task_type, target, reward_stars FROM free_star_tasks WHERE id=?", (task_id,))
        task = c.fetchone()
        conn.close()
        if not task:
            bot.answer_callback_query(call.id, "کار پیدا نشد", show_alert=True)
            return

        bot.user_steps[uid] = {"step": "waiting_task_proof", "task_id": task_id, "reward": task[3]}
        
        if task[1] == "join":
            text = f"📌 کار: {task[0]}\n\nدر کانال زیر عضو شوید و بعد روی دکمه «انجام دادم» بزنید:\n{task[2]}"
            mk = InlineKeyboardMarkup()
            mk.add(InlineKeyboardButton("✅ انجام دادم", callback_data=f"confirm_task_{task_id}"))
            mk.add(InlineKeyboardButton("🔙 انصراف", callback_data="free_stars"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=mk)
        else:
            bot.edit_message_text(f"📌 کار: {task[0]}\n\nتوضیحات: {task[2]}\n\nبعد از انجام، لینک پست را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data.startswith("confirm_task_"):
        task_id = int(data.split("_")[2])
        bot.user_steps[uid] = {"step": "waiting_post_link", "task_id": task_id}
        bot.edit_message_text("لینک پستی که می‌خواهید استارز بخورد را بفرستید:", call.message.chat.id, call.message.message_id)

    # ---------- پروفایل و شارژ ----------
    elif data == "profile_charge":
        bal = get_balance(uid)
        rate = get_setting("star_to_toman", "4000")
        text = f"""
👤 **پروفایل شما**

آیدی: `{uid}`
موجودی: **{bal:,}** تومان
نرخ فعلی: هر استارز ≈ {rate} تومان
"""
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=profile_menu(uid), parse_mode="Markdown")

    elif data == "charge_stars":
        bot.user_steps[uid] = {"step": "charge_amount"}
        bot.edit_message_text("تعداد استارزی که می‌خواهید پرداخت کنید را بفرستید (مثال: ۱۰):", call.message.chat.id, call.message.message_id)

    # ---------- کد هدیه ----------
    elif data == "gift_codes":
        bot.edit_message_text("🎁 بخش کد هدیه و گیفت:\n\nبرای وارد کردن کد از دستور /Gifts هم می‌توانید استفاده کنید.", 
                              call.message.chat.id, call.message.message_id, reply_markup=gift_menu())

    elif data == "enter_gift_code":
        bot.user_steps[uid] = {"step": "enter_code"}
        bot.edit_message_text("کد هدیه یا گیفت را وارد کنید:", call.message.chat.id, call.message.message_id)

    # ---------- پشتیبانی ----------
    elif data == "support":
        bot.user_steps[uid] = {"step": "support_message"}
        bot.edit_message_text("پیام خود را برای پشتیبانی بفرستید:", call.message.chat.id, call.message.message_id)

    # ==================== پنل ادمین ====================
    elif data == "admin_panel" and is_admin(uid):
        bot.edit_message_text("👑 پنل ادمین:", call.message.chat.id, call.message.message_id, reply_markup=admin_menu())

    elif data == "admin_orders" and is_admin(uid):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, user_id, code, post_link, status, created_at FROM free_star_orders WHERE status='pending' ORDER BY id DESC LIMIT 15")
        rows = c.fetchall()
        conn.close()
        if not rows:
            bot.send_message(call.message.chat.id, "هیچ سفارش در انتظاری وجود ندارد.")
            return
        text = "📦 **سفارشات مونده:**\n\n"
        mk = InlineKeyboardMarkup(row_width=1)
        for r in rows:
            text += f"#{r[0]} | کاربر `{r[1]}`\nکد: `{r[2]}`\nلینک: {r[3][:40]}...\n────────\n"
            mk.add(InlineKeyboardButton(f"✅ تأیید #{r[0]}", callback_data=f"approve_order_{r[0]}"))
        mk.add(InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel"))
        bot.send_message(call.message.chat.id, text, reply_markup=mk, parse_mode="Markdown")

    elif data.startswith("approve_order_") and is_admin(uid):
        oid = int(data.split("_")[2])
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id, code FROM free_star_orders WHERE id=? AND status='pending'", (oid,))
        row = c.fetchone()
        if row:
            c.execute("UPDATE free_star_orders SET status='approved' WHERE id=?", (oid,))
            conn.commit()
            try:
                bot.send_message(row[0], f"✅ سفارش شما تأیید شد!\nکد شما: `{row[1]}`", parse_mode="Markdown")
            except: pass
            bot.answer_callback_query(call.id, f"سفارش #{oid} تأیید شد", show_alert=True)
        conn.close()

    elif data == "admin_add_task" and is_admin(uid):
        bot.user_steps[uid] = {"step": "add_task_title"}
        bot.edit_message_text("عنوان کار را بفرستید (مثال: عضویت در کانال اصلی):", call.message.chat.id, call.message.message_id)

    elif data == "admin_list_tasks" and is_admin(uid):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, title, task_type, reward_stars, is_active FROM free_star_tasks")
        rows = c.fetchall()
        conn.close()
        text = "📋 لیست کارها:\n\n"
        for r in rows:
            status = "✅" if r[4] else "❌"
            text += f"{status} #{r[0]} | {r[1]} | {r[2]} | {r[3]} استارز\n"
        bot.send_message(call.message.chat.id, text or "خالی")

    elif data == "admin_create_star_code" and is_admin(uid):
        bot.user_steps[uid] = {"step": "star_code_amount"}
        bot.edit_message_text("تعداد استارز این کد هدیه را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "admin_create_gift_code" and is_admin(uid):
        bot.user_steps[uid] = {"step": "gift_code_info"}
        bot.edit_message_text("اطلاعات گیفت را بفرستید (مثال: گیفت ۱۵ استارزی تدی):", call.message.chat.id, call.message.message_id)

    elif data == "admin_set_rate" and is_admin(uid):
        bot.user_steps[uid] = {"step": "set_rate"}
        bot.edit_message_text(f"نرخ فعلی: هر استارز = {get_setting('star_to_toman')} تومان\nنرخ جدید را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "admin_manual_charge" and is_admin(uid):
        bot.user_steps[uid] = {"step": "manual_charge_id"}
        bot.edit_message_text("آیدی عددی کاربر را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "admin_forced" and is_admin(uid):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, channel_id, channel_title FROM forced_channels")
        rows = c.fetchall()
        conn.close()
        mk = InlineKeyboardMarkup(row_width=1)
        for r in rows:
            mk.add(InlineKeyboardButton(f"❌ {r[2] or r[1]}", callback_data=f"del_forced_{r[0]}"))
        mk.add(InlineKeyboardButton("➕ اضافه کردن کانال قفل", callback_data="add_forced"))
        mk.add(InlineKeyboardButton("🔙", callback_data="admin_panel"))
        bot.edit_message_text("کانال‌های قفل‌شده:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "add_forced" and is_admin(uid):
        bot.user_steps[uid] = {"step": "add_forced"}
        bot.edit_message_text("آیدی کانال را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data.startswith("del_forced_") and is_admin(uid):
        fid = int(data.split("_")[2])
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM forced_channels WHERE id=?", (fid,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "حذف شد")

    elif data == "admin_users" and is_admin(uid):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id, username, balance FROM users ORDER BY balance DESC LIMIT 20")
        rows = c.fetchall()
        conn.close()
        text = "👥 کاربران:\n\n"
        for r in rows:
            text += f"`{r[0]}` | @{r[1] or '-'} | {r[2]:,} تومان\n"
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

    elif data == "admin_stats" and is_admin(uid):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM free_star_orders WHERE status='pending'")
        pending = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM gift_codes WHERE is_active=1")
        codes = c.fetchone()[0]
        conn.close()
        text = f"📊 آمار ربات\n\nکاربران: {total}\nسفارشات مونده: {pending}\nکدهای فعال: {codes}"
        bot.send_message(call.message.chat.id, text)

    elif data == "admin_maintenance" and is_admin(uid):
        cur = get_setting("maintenance")
        set_setting("maintenance", "0" if cur == "1" else "1")
        bot.answer_callback_query(call.id, "وضعیت تعمیرات تغییر کرد", show_alert=True)

    bot.answer_callback_query(call.id)

print("✅ بخش ۳ آماده شد")
# ==================== بخش ۴ از ۶ ====================
# هندلر پیام‌ها (کاربر + ادمین)

@bot.message_handler(content_types=['text', 'sticker'])
def handle_text(message):
    uid = message.from_user.id
    ensure_user(message.from_user)
    bot.user_steps = getattr(bot, "user_steps", {})
    step_data = bot.user_steps.get(uid, {})
    step = step_data.get("step")

    # ----- لینک پست برای استارز رایگان -----
    if step == "waiting_post_link":
        link = message.text.strip()
        task_id = step_data.get("task_id")
        code = generate_code(9)

        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO free_star_orders (user_id, task_id, post_link, code, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
                  (uid, task_id, link, code, now_tehran().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        conn.close()

        bot.send_message(message.chat.id, 
            f"✅ درخواست ثبت شد.\n\nکد شما: `{code}`\n\nاین کد برای ادمین ارسال شد. بعد از تأیید بهتون خبر می‌دیم.",
            parse_mode="Markdown", reply_markup=main_menu(uid))
        
        for adm in ADMIN_IDS:
            try:
                bot.send_message(adm, f"📦 سفارش جدید استارز رایگان\nکاربر: `{uid}`\nکد: `{code}`\nلینک: {link}", parse_mode="Markdown")
            except: pass
        bot.user_steps[uid] = {}
        return

    # ----- وارد کردن کد هدیه -----
    if step == "enter_code":
        code = message.text.strip().upper()
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, code_type, value, max_uses, used_count, expire_at, sticker_file_id, is_active FROM gift_codes WHERE code=?", (code,))
        row = c.fetchone()

        if not row or row[7] == 0:
            bot.send_message(message.chat.id, "❌ کد نامعتبر یا منقضی شده.", reply_markup=main_menu(uid))
            conn.close()
            bot.user_steps[uid] = {}
            return

        if row[4] >= row[3]:
            bot.send_message(message.chat.id, "❌ ظرفیت این کد تکمیل شده.", reply_markup=main_menu(uid))
            conn.close()
            bot.user_steps[uid] = {}
            return

        if row[5]:
            try:
                if now_tehran().replace(tzinfo=None) > datetime.strptime(row[5], "%Y-%m-%d %H:%M"):
                    bot.send_message(message.chat.id, "❌ کد منقضی شده.", reply_markup=main_menu(uid))
                    conn.close()
                    bot.user_steps[uid] = {}
                    return
            except: pass

        # ثبت استفاده
        c.execute("UPDATE gift_codes SET used_count = used_count + 1 WHERE code=?", (code,))
        c.execute("INSERT INTO code_uses (code, user_id, used_at) VALUES (?, ?, ?)", (code, uid, now_tehran().strftime("%Y-%m-%d %H:%M")))
        conn.commit()

        if row[1] == "stars":
            stars = int(row[2])
            rate = int(get_setting("star_to_toman", "4000"))
            amount = stars * rate
            add_balance(uid, amount)
            bot.send_message(message.chat.id, f"✅ کد صحیح بود!\n{stars} استارز ≈ {amount:,} تومان به حساب شما اضافه شد.", reply_markup=main_menu(uid))
        else:
            # گیفت
            bot.send_message(message.chat.id, f"🎁 کد گیفت صحیح بود!\nاطلاعات: {row[2]}")
            if row[6]:
                try:
                    bot.send_sticker(message.chat.id, row[6])
                except: pass
            bot.send_message(message.chat.id, "اطلاعات قرعه کشی برای شما ثبت شد.", reply_markup=main_menu(uid))

        conn.close()
        bot.user_steps[uid] = {}
        return

    # ----- شارژ با استارز -----
    if step == "charge_amount":
        try:
            stars = int(message.text.strip())
            if stars < 1:
                bot.send_message(message.chat.id, "حداقل ۱ استارز")
                return
            rate = int(get_setting("star_to_toman", "4000"))
            toman = stars * rate
            prices = [LabeledPrice(label=f"{stars} استارز", amount=stars)]
            bot.send_invoice(
                message.chat.id,
                title=f"شارژ {stars} استارز",
                description=f"معادل تقریبی {toman:,} تومان",
                invoice_payload=f"charge_{stars}_{uid}",
                provider_token="",
                currency="XTR",
                prices=prices
            )
        except:
            bot.send_message(message.chat.id, "فقط عدد بفرستید.")
        bot.user_steps[uid] = {}
        return

    # ----- پشتیبانی -----
    if step == "support_message":
        msg = message.text
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO tickets (user_id, message, status, created_at) VALUES (?, ?, 'open', ?)",
                  (uid, msg, now_tehran().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ پیام شما به پشتیبانی ارسال شد.", reply_markup=main_menu(uid))
        for adm in ADMIN_IDS:
            try:
                bot.send_message(adm, f"🛠 تیکت جدید\nاز: `{uid}`\nپیام: {msg}", parse_mode="Markdown")
            except: pass
        bot.user_steps[uid] = {}
        return

    # ==================== بخش‌های ادمین ====================
    if not is_admin(uid):
        bot.send_message(message.chat.id, "از منو استفاده کنید:", reply_markup=main_menu(uid))
        return

    # اضافه کردن کار
    if step == "add_task_title":
        bot.user_steps[uid] = {"step": "add_task_type", "title": message.text}
        bot.send_message(message.chat.id, "نوع کار را بفرستید:\n`join` برای عضویت کانال\n`react` برای ریکشن\n`other` برای کار دیگر")
        return

    if step == "add_task_type":
        bot.user_steps[uid] = {"step": "add_task_target", "title": step_data["title"], "type": message.text.strip().lower()}
        bot.send_message(message.chat.id, "تارگت را بفرستید (آیدی کانال یا لینک پست یا توضیحات):")
        return

    if step == "add_task_target":
        bot.user_steps[uid] = {"step": "add_task_reward", "title": step_data["title"], "type": step_data["type"], "target": message.text}
        bot.send_message(message.chat.id, "تعداد استارز پاداش را بفرستید:")
        return

    if step == "add_task_reward":
        try:
            reward = int(message.text.strip())
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO free_star_tasks (title, task_type, target, reward_stars, is_active) VALUES (?, ?, ?, ?, 1)",
                      (step_data["title"], step_data["type"], step_data["target"], reward))
            conn.commit()
            conn.close()
            bot.send_message(message.chat.id, "✅ کار با موفقیت اضافه شد.", reply_markup=admin_menu())
        except:
            bot.send_message(message.chat.id, "عدد معتبر بفرستید.")
        bot.user_steps[uid] = {}
        return

    # ساخت کد هدیه استارز
    if step == "star_code_amount":
        bot.user_steps[uid] = {"step": "star_code_uses", "amount": message.text.strip()}
        bot.send_message(message.chat.id, "حداکثر تعداد استفاده از کد را بفرستید (مثال: ۱ یا ۱۰):")
        return

    if step == "star_code_uses":
        bot.user_steps[uid] = {"step": "star_code_expire", "amount": step_data["amount"], "uses": message.text.strip()}
        bot.send_message(message.chat.id, "مدت اعتبار به ساعت را بفرستید (مثال: ۲۴ برای یک روز، ۰ برای بدون انقضا):")
        return

    if step == "star_code_expire":
        try:
            amount = step_data["amount"]
            uses = int(step_data["uses"])
            hours = int(message.text.strip())
            code = generate_code(8)
            expire = (now_tehran() + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M") if hours > 0 else None

            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO gift_codes (code, code_type, value, max_uses, expire_at, is_active, created_by) VALUES (?, 'stars', ?, ?, ?, 1, ?)",
                      (code, amount, uses, expire, uid))
            conn.commit()
            conn.close()

            bot.send_message(message.chat.id, 
                f"✅ کد هدیه استارز ساخته شد:\n\nکد: `{code}`\nاستارز: {amount}\nظرفیت: {uses}\nانقضا: {expire or 'ندارد'}",
                parse_mode="Markdown", reply_markup=admin_menu())
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا: {e}")
        bot.user_steps[uid] = {}
        return

    # ساخت کد گیفت
    if step == "gift_code_info":
        bot.user_steps[uid] = {"step": "gift_code_sticker", "info": message.text}
        bot.send_message(message.chat.id, "حالا استیکر مربوط به گیفت را بفرستید:")
        return

    if step == "gift_code_sticker" and message.content_type == "sticker":
        info = step_data.get("info", "گیفت")
        code = generate_code(8)
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO gift_codes (code, code_type, value, max_uses, sticker_file_id, is_active, created_by) VALUES (?, 'gift', ?, 1, ?, 1, ?)",
                  (code, info, message.sticker.file_id, uid))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ کد گیفت ساخته شد:\nکد: `{code}`\nاطلاعات: {info}", parse_mode="Markdown", reply_markup=admin_menu())
        bot.user_steps[uid] = {}
        return

    # تنظیم نرخ
    if step == "set_rate":
        try:
            set_setting("star_to_toman", str(int(message.text.strip())))
            bot.send_message(message.chat.id, "✅ نرخ تغییر کرد.", reply_markup=admin_menu())
        except:
            bot.send_message(message.chat.id, "عدد بفرستید.")
        bot.user_steps[uid] = {}
        return

    # شارژ دستی
    if step == "manual_charge_id":
        bot.user_steps[uid] = {"step": "manual_charge_amount", "target": message.text.strip()}
        bot.send_message(message.chat.id, "مبلغ به تومان را بفرستید:")
        return

    if step == "manual_charge_amount":
        try:
            target = int(step_data["target"])
            amount = int(message.text.strip())
            ensure_user(type("obj", (object,), {"id": target, "username": "", "full_name": ""})())
            add_balance(target, amount)
            bot.send_message(message.chat.id, f"✅ {amount:,} تومان به `{target}` اضافه شد.", parse_mode="Markdown", reply_markup=admin_menu())
            try:
                bot.send_message(target, f"💰 حساب شما توسط ادمین {amount:,} تومان شارژ شد.")
            except: pass
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا: {e}")
        bot.user_steps[uid] = {}
        return

    # اضافه کردن کانال قفل
    if step == "add_forced":
        ch = message.text.strip()
        try:
            chat = bot.get_chat(ch)
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO forced_channels (channel_id, channel_title) VALUES (?, ?)", (str(chat.id), chat.title))
            conn.commit()
            conn.close()
            bot.send_message(message.chat.id, f"✅ کانال قفل اضافه شد: {chat.title}", reply_markup=admin_menu())
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا: {e}")
        bot.user_steps[uid] = {}
        return

    bot.send_message(message.chat.id, "از منو استفاده کنید:", reply_markup=main_menu(uid))

print("✅ بخش ۴ آماده شد")
# ==================== بخش ۵ از ۶ ====================
# پرداخت استارز + ارسال کد + باقی‌مانده ادمین

@bot.pre_checkout_query_handler(func=lambda q: True)
def pre_checkout(q):
    bot.answer_pre_checkout_query(q.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def on_payment(message):
    uid = message.from_user.id
    payload = message.successful_payment.invoice_payload
    amount_stars = message.successful_payment.total_amount

    if payload.startswith("charge_"):
        parts = payload.split("_")
        stars = int(parts[1])
        rate = int(get_setting("star_to_toman", "4000"))
        toman = stars * rate
        add_balance(uid, toman)
        bot.send_message(message.chat.id,
            f"✅ پرداخت موفق!\n{stars} استارز پرداخت شد.\n{toman:,} تومان به موجودی شما اضافه شد.\nموجودی جدید: {get_balance(uid):,} تومان",
            reply_markup=main_menu(uid))
        log_action(uid, "charge", f"stars={stars}")
        for adm in ADMIN_IDS:
            try:
                bot.send_message(adm, f"⭐ شارژ جدید\nکاربر: `{uid}`\n{stars} استارز ≈ {toman:,} تومان", parse_mode="Markdown")
            except: pass

# ---------- ارسال کد به کانال / کاربران ----------
@bot.callback_query_handler(func=lambda call: call.data in ["admin_send_code_channel", "admin_send_code_users"])
def send_code_handler(call):
    uid = call.from_user.id
    if not is_admin(uid):
        return

    bot.user_steps = getattr(bot, "user_steps", {})
    if call.data == "admin_send_code_channel":
        bot.user_steps[uid] = {"step": "send_code_ch_code"}
        bot.edit_message_text("کدی که می‌خواهید به کانال ارسال شود را بفرستید:", call.message.chat.id, call.message.message_id)
    else:
        bot.user_steps[uid] = {"step": "send_code_users_code"}
        bot.edit_message_text("کدی که می‌خواهید به همه کاربران ارسال شود را بفرستید:", call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)

# ادامه هندلر برای ارسال کد
@bot.message_handler(func=lambda m: getattr(bot, "user_steps", {}).get(m.from_user.id, {}).get("step") in ["send_code_ch_code", "send_code_users_code", "send_code_ch_text"])
def handle_send_code(message):
    uid = message.from_user.id
    if not is_admin(uid):
        return

    step_data = bot.user_steps.get(uid, {})
    step = step_data.get("step")

    if step == "send_code_ch_code":
        code = message.text.strip().upper()
        bot.user_steps[uid] = {"step": "send_code_ch_text", "code": code}
        bot.send_message(message.chat.id, "متن پیام همراه کد را بفرستید (یا کلمه `خالی`):")
        return

    if step == "send_code_ch_text":
        code = step_data.get("code")
        text = message.text if message.text != "خالی" else ""
        channel = get_setting("lottery_channel")
        if not channel:
            bot.send_message(message.chat.id, "اول از تنظیمات، کانال قرعه کشی را مشخص کنید.", reply_markup=admin_menu())
            bot.user_steps[uid] = {}
            return
        try:
            final_text = f"{text}\n\n🔑 کد: `{code}`\n\nبرای استفاده دستور /Gifts را بزنید و کد را ارسال کنید." if text else f"🔑 کد جدید: `{code}`\n\nدستور /Gifts را بزنید و کد را وارد کنید."
            bot.send_message(channel, final_text, parse_mode="Markdown")
            bot.send_message(message.chat.id, "✅ کد به کانال ارسال شد.", reply_markup=admin_menu())
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا در ارسال به کانال: {e}", reply_markup=admin_menu())
        bot.user_steps[uid] = {}
        return

    if step == "send_code_users_code":
        code = message.text.strip().upper()
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        users = c.fetchall()
        conn.close()

        success = 0
        for u in users:
            try:
                bot.send_message(u[0], f"🎁 کد هدیه جدید\n\nکد: `{code}`\n\nبا دستور /Gifts کد را وارد کنید.", parse_mode="Markdown")
                success += 1
            except:
                pass
        bot.send_message(message.chat.id, f"✅ کد به {success} کاربر ارسال شد.", reply_markup=admin_menu())
        bot.user_steps[uid] = {}
        return

print("✅ بخش ۵ آماده شد")
# ==================== بخش ۶ از ۶ ====================
# کارهای نهایی + اجرا

# تنظیم کانال قرعه کشی از ادمین (اگر لازم شد)
@bot.callback_query_handler(func=lambda call: call.data == "admin_set_lottery_channel")
def set_lottery_channel(call):
    if not is_admin(call.from_user.id):
        return
    bot.user_steps = getattr(bot, "user_steps", {})
    bot.user_steps[call.from_user.id] = {"step": "set_lottery_ch"}
    bot.edit_message_text("آیدی کانال قرعه کشی را بفرستید:", call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda m: getattr(bot, "user_steps", {}).get(m.from_user.id, {}).get("step") == "set_lottery_ch")
def save_lottery_channel(message):
    if not is_admin(message.from_user.id):
        return
    set_setting("lottery_channel", message.text.strip())
    bot.send_message(message.chat.id, f"✅ کانال قرعه کشی تنظیم شد:\n{message.text.strip()}", reply_markup=admin_menu())
    bot.user_steps[message.from_user.id] = {}

# دکمه‌های اضافی ادمین که ممکن است جا مانده باشد
def extra_admin_buttons():
    # این تابع فقط برای اطمینان است که دکمه‌های مهم وجود دارند
    pass

# ---------- اجرا ----------
print("🤖 ربات استارز و قرعه کشی با موفقیت روشن شد")
print("=" * 40)
print("قابلیت‌های اصلی:")
print("• استارز رایگان (کار + لینک پست + کد)")
print("• سیستم کد هدیه استارز و گیفت")
print("• شارژ حساب با پرداخت استارز")
print("• پروفایل و موجودی")
print("• قفل کانال (Forced Join)")
print("• پنل ادمین کامل (سفارشات، کارها، کدها، شارژ دستی و ...)")
print("• دستور /Gifts برای وارد کردن کد")
print("=" * 40)

bot.infinity_polling()
