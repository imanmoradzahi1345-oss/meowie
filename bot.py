# ==================== بخش ۱ از ۴ ====================
# تنظیمات + دیتابیس کامل + توابع پایه + منوها

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
    conn = sqlite3.connect("full_bot.db")
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        balance INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        is_banned INTEGER DEFAULT 0,
        referral_code TEXT,
        referred_by INTEGER,
        joined_at TEXT,
        last_active TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS free_star_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        task_type TEXT,
        target TEXT,
        reward_stars INTEGER DEFAULT 1,
        is_active INTEGER DEFAULT 1
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS free_star_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task_id INTEGER,
        post_link TEXT,
        code TEXT UNIQUE,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )''')

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

    c.execute('''CREATE TABLE IF NOT EXISTS code_uses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT,
        user_id INTEGER,
        used_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_type TEXT,
        title TEXT,
        description TEXT,
        price_stars INTEGER,
        price_balance INTEGER,
        min_qty INTEGER DEFAULT 1,
        max_qty INTEGER DEFAULT 1,
        is_active INTEGER DEFAULT 1
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS shop_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        product_title TEXT,
        quantity INTEGER,
        pay_method TEXT,
        total_price INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS forced_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT UNIQUE,
        channel_title TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        status TEXT DEFAULT 'open',
        admin_reply TEXT,
        created_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        details TEXT,
        created_at TEXT
    )''')

    defaults = {
        "star_to_toman": "4000",
        "maintenance": "0",
        "lottery_channel": "",
        "maintenance_text": "ربات در حال تعمیرات است."
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect("full_bot.db")

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
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        c.execute("INSERT INTO users (user_id, username, full_name, balance, referral_code, joined_at, last_active) VALUES (?, ?, ?, 0, ?, ?, ?)",
                  (user.id, user.username or "", user.full_name or "", code,
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

# ----------------- منوها -----------------
def main_menu(uid):
    m = InlineKeyboardMarkup(row_width=2)
    m.add(
        InlineKeyboardButton("⭐ استارز و قرعه کشی", callback_data="menu_stars"),
        InlineKeyboardButton("👤 پروفایل و شارژ", callback_data="menu_profile"),
    )
    m.add(
        InlineKeyboardButton("🛒 فروشگاه", callback_data="menu_shop"),
        InlineKeyboardButton("🎁 کد هدیه", callback_data="menu_gift"),
    )
    m.add(InlineKeyboardButton("🛠 پشتیبانی", callback_data="menu_support"))
    if is_admin(uid):
        m.add(InlineKeyboardButton("👑 پنل ادمین", callback_data="admin_panel"))
    return m

def admin_menu():
    m = InlineKeyboardMarkup(row_width=2)
    m.add(
        InlineKeyboardButton("📦 سفارشات استارز رایگان", callback_data="adm_free_orders"),
        InlineKeyboardButton("🛍 سفارشات فروشگاه", callback_data="adm_shop_orders"),
    )
    m.add(
        InlineKeyboardButton("➕ کار استارز رایگان", callback_data="adm_add_task"),
        InlineKeyboardButton("🗑 حذف کار", callback_data="adm_del_task"),
    )
    m.add(
        InlineKeyboardButton("🎁 ساخت کد هدیه", callback_data="adm_create_code"),
        InlineKeyboardButton("📢 ارسال کد", callback_data="adm_send_code"),
    )
    m.add(
        InlineKeyboardButton("🛒 مدیریت فروشگاه", callback_data="adm_shop"),
        InlineKeyboardButton("🔒 قفل کانال", callback_data="adm_forced"),
    )
    m.add(
        InlineKeyboardButton("💰 تنظیم نرخ استارز", callback_data="adm_rate"),
        InlineKeyboardButton("💸 شارژ دستی", callback_data="adm_charge"),
    )
    m.add(
        InlineKeyboardButton("👥 لیست کاربران", callback_data="adm_users"),
        InlineKeyboardButton("🔍 چک حساب کاربر", callback_data="adm_check_user"),
    )
    m.add(
        InlineKeyboardButton("📨 پیام همگانی", callback_data="adm_broadcast"),
        InlineKeyboardButton("📊 آمار", callback_data="adm_stats"),
    )
    m.add(
        InlineKeyboardButton("🛠 تعمیرات", callback_data="adm_maint"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"),
    )
    return m

print("✅ بخش ۱ آماده شد")
# ==================== بخش ۲ از ۴ ====================
# /start + کال‌بک‌های اصلی کاربر و ادمین

@bot.message_handler(commands=['start'])
def start(message):
    ensure_user(message.from_user)
    uid = message.from_user.id

    if get_setting("maintenance") == "1" and not is_admin(uid):
        bot.send_message(message.chat.id, get_setting("maintenance_text", "ربات در حال تعمیرات است."))
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    if row and row[0] == 1:
        bot.send_message(message.chat.id, "🚫 حساب شما مسدود است.")
        conn.close()
        return

    # قفل کانال
    c.execute("SELECT channel_id, channel_title FROM forced_channels")
    forced = c.fetchall()
    conn.close()
    if forced and not is_admin(uid):
        not_joined = []
        for ch_id, title in forced:
            try:
                m = bot.get_chat_member(ch_id, uid)
                if m.status in ["left", "kicked"]:
                    not_joined.append((ch_id, title))
            except:
                not_joined.append((ch_id, title))
        if not_joined:
            mk = InlineKeyboardMarkup(row_width=1)
            for ch_id, title in not_joined:
                link = f"https://t.me/{str(ch_id).lstrip('@').replace('-100','')}"
                mk.add(InlineKeyboardButton(f"📢 {title or ch_id}", url=link))
            mk.add(InlineKeyboardButton("✅ عضو شدم", callback_data="check_join"))
            bot.send_message(message.chat.id, "🔒 برای استفاده باید عضو کانال‌های زیر شوید:", reply_markup=mk)
            return

    bot.send_message(message.chat.id, f"سلام {message.from_user.first_name}!\nبه ربات خوش آمدید.", reply_markup=main_menu(uid))

@bot.message_handler(commands=['Gifts', 'gifts'])
def cmd_gifts(message):
    ensure_user(message.from_user)
    bot.user_steps = getattr(bot, "user_steps", {})
    bot.user_steps[message.from_user.id] = {"step": "enter_code"}
    bot.send_message(message.chat.id, "🔑 کد هدیه را وارد کنید:")

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    uid = call.from_user.id
    ensure_user(call.from_user)
    data = call.data
    bot.user_steps = getattr(bot, "user_steps", {})

    if data == "back_main":
        bot.edit_message_text("منوی اصلی:", call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))

    elif data == "check_join":
        bot.answer_callback_query(call.id)
        start(call.message)
        return

    # ----- منوهای کاربر -----
    elif data == "menu_stars":
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(InlineKeyboardButton("🆓 استارز رایگان", callback_data="free_stars"),
               InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
        bot.edit_message_text("⭐ استارز و قرعه کشی:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "free_stars":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, title, reward_stars FROM free_star_tasks WHERE is_active=1")
        tasks = c.fetchall()
        conn.close()
        if not tasks:
            bot.answer_callback_query(call.id, "کاری تعریف نشده", show_alert=True)
            return
        mk = InlineKeyboardMarkup(row_width=1)
        for t in tasks:
            mk.add(InlineKeyboardButton(f"{t[1]} ({t[2]}⭐)", callback_data=f"task_{t[0]}"))
        mk.add(InlineKeyboardButton("🔙", callback_data="menu_stars"))
        bot.edit_message_text("کار را انتخاب کنید:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data.startswith("task_"):
        tid = int(data.split("_")[1])
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT title, task_type, target, reward_stars FROM free_star_tasks WHERE id=?", (tid,))
        task = c.fetchone()
        conn.close()
        if not task:
            return
        bot.user_steps[uid] = {"step": "task_proof", "task_id": tid, "reward": task[3]}
        if task[1] == "join":
            mk = InlineKeyboardMarkup()
            mk.add(InlineKeyboardButton("✅ انجام دادم", callback_data=f"done_task_{tid}"))
            bot.edit_message_text(f"📌 {task[0]}\n\nعضو شوید:\n{task[2]}", call.message.chat.id, call.message.message_id, reply_markup=mk)
        else:
            bot.edit_message_text(f"📌 {task[0]}\n\n{task[2]}\n\nبعد از انجام لینک پست را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data.startswith("done_task_"):
        tid = int(data.split("_")[2])
        bot.user_steps[uid] = {"step": "post_link", "task_id": tid}
        bot.edit_message_text("لینک پست را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "menu_profile":
        bal = get_balance(uid)
        rate = get_setting("star_to_toman", "4000")
        text = f"👤 پروفایل\n\nآیدی: `{uid}`\nموجودی: **{bal:,}** تومان\nنرخ: هر استارز ≈ {rate} تومان"
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(InlineKeyboardButton("⭐ شارژ با استارز", callback_data="charge"),
               InlineKeyboardButton("🔙", callback_data="back_main"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode="Markdown")

    elif data == "charge":
        bot.user_steps[uid] = {"step": "charge_stars"}
        bot.edit_message_text("تعداد استارز را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "menu_shop":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, product_type, title, price_stars, price_balance FROM products WHERE is_active=1")
        products = c.fetchall()
        conn.close()
        if not products:
            bot.answer_callback_query(call.id, "محصولی وجود ندارد", show_alert=True)
            return
        mk = InlineKeyboardMarkup(row_width=1)
        for p in products:
            mk.add(InlineKeyboardButton(f"{p[2]} | {p[3]}⭐ / {p[4]:,}ت", callback_data=f"prod_{p[0]}"))
        mk.add(InlineKeyboardButton("🔙", callback_data="back_main"))
        bot.edit_message_text("🛒 فروشگاه:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data.startswith("prod_"):
        pid = int(data.split("_")[1])
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM products WHERE id=?", (pid,))
        p = c.fetchone()
        conn.close()
        if not p:
            return
        bot.user_steps[uid] = {"step": "shop_qty", "product": p}
        bot.edit_message_text(f"محصول: {p[2]}\nحداقل: {p[6]} | حداکثر: {p[7]}\n\nتعداد را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "menu_gift":
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(InlineKeyboardButton("🔑 وارد کردن کد", callback_data="enter_code_btn"),
               InlineKeyboardButton("🔙", callback_data="back_main"))
        bot.edit_message_text("🎁 کد هدیه:\nیا از /Gifts استفاده کنید.", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "enter_code_btn":
        bot.user_steps[uid] = {"step": "enter_code"}
        bot.edit_message_text("کد را وارد کنید:", call.message.chat.id, call.message.message_id)

    elif data == "menu_support":
        bot.user_steps[uid] = {"step": "support_msg"}
        bot.edit_message_text("پیام خود را بفرستید:", call.message.chat.id, call.message.message_id)

    # ==================== پنل ادمین ====================
    elif data == "admin_panel" and is_admin(uid):
        bot.edit_message_text("👑 پنل ادمین:", call.message.chat.id, call.message.message_id, reply_markup=admin_menu())

    elif data == "adm_free_orders" and is_admin(uid):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, user_id, code, post_link, created_at FROM free_star_orders WHERE status='pending' ORDER BY id DESC LIMIT 10")
        rows = c.fetchall()
        conn.close()
        if not rows:
            bot.send_message(call.message.chat.id, "سفارشی نیست.")
            return
        text = "📦 سفارشات استارز رایگان:\n\n"
        mk = InlineKeyboardMarkup(row_width=1)
        for r in rows:
            text += f"#{r[0]} | `{r[1]}` | کد: `{r[2]}`\n"
            mk.add(InlineKeyboardButton(f"بررسی #{r[0]}", callback_data=f"see_order_{r[0]}"))
        bot.send_message(call.message.chat.id, text, reply_markup=mk, parse_mode="Markdown")

    elif data.startswith("see_order_") and is_admin(uid):
        oid = int(data.split("_")[2])
        bot.user_steps[uid] = {"step": "approve_order", "oid": oid}
        bot.send_message(call.message.chat.id, f"برای تأیید سفارش #{oid} آیدی عددی یا یوزرنیم کاربر را بفرستید:")

    elif data == "adm_shop_orders" and is_admin(uid):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, user_id, product_title, quantity, status FROM shop_orders WHERE status='pending' ORDER BY id DESC LIMIT 10")
        rows = c.fetchall()
        conn.close()
        text = "🛍 سفارشات فروشگاه:\n\n"
        mk = InlineKeyboardMarkup(row_width=1)
        for r in rows:
            text += f"#{r[0]} | `{r[1]}` | {r[2]} × {r[3]}\n"
            mk.add(InlineKeyboardButton(f"تأیید #{r[0]}", callback_data=f"done_shop_{r[0]}"))
        bot.send_message(call.message.chat.id, text, reply_markup=mk, parse_mode="Markdown")

    elif data.startswith("done_shop_") and is_admin(uid):
        oid = int(data.split("_")[2])
        bot.user_steps[uid] = {"step": "finish_shop", "oid": oid}
        bot.send_message(call.message.chat.id, "آیدی عددی یا یوزرنیم کاربر را برای تأیید نهایی بفرستید:")

    elif data == "adm_add_task" and is_admin(uid):
        bot.user_steps[uid] = {"step": "task_title"}
        bot.edit_message_text("عنوان کار را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "adm_del_task" and is_admin(uid):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, title FROM free_star_tasks WHERE is_active=1")
        rows = c.fetchall()
        conn.close()
        mk = InlineKeyboardMarkup(row_width=1)
        for r in rows:
            mk.add(InlineKeyboardButton(f"🗑 {r[1]}", callback_data=f"deltask_{r[0]}"))
        mk.add(InlineKeyboardButton("🔙", callback_data="admin_panel"))
        bot.edit_message_text("کار برای حذف:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data.startswith("deltask_") and is_admin(uid):
        tid = int(data.split("_")[1])
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE free_star_tasks SET is_active=0 WHERE id=?", (tid,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "حذف شد", show_alert=True)

    elif data == "adm_create_code" and is_admin(uid):
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(InlineKeyboardButton("⭐ کد استارز", callback_data="code_stars"),
               InlineKeyboardButton("🎁 کد گیفت", callback_data="code_gift"),
               InlineKeyboardButton("💰 کد شارژ حساب", callback_data="code_balance"),
               InlineKeyboardButton("🔙", callback_data="admin_panel"))
        bot.edit_message_text("نوع کد:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "adm_shop" and is_admin(uid):
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(InlineKeyboardButton("➕ اضافه کردن محصول", callback_data="add_product"),
               InlineKeyboardButton("📋 لیست محصولات", callback_data="list_products"),
               InlineKeyboardButton("🔙", callback_data="admin_panel"))
        bot.edit_message_text("مدیریت فروشگاه:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "add_product" and is_admin(uid):
        mk = InlineKeyboardMarkup(row_width=2)
        mk.add(InlineKeyboardButton("🎁 گیفت", callback_data="prodtype_gift"),
               InlineKeyboardButton("⭐ استارز", callback_data="prodtype_stars"))
        bot.edit_message_text("نوع محصول را انتخاب کنید:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data.startswith("prodtype_") and is_admin(uid):
        ptype = data.split("_")[1]
        bot.user_steps[uid] = {"step": "prod_title", "ptype": ptype}
        bot.edit_message_text("نام محصول را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "adm_rate" and is_admin(uid):
        bot.user_steps[uid] = {"step": "set_rate"}
        bot.edit_message_text(f"نرخ فعلی: {get_setting('star_to_toman')}\nنرخ جدید:", call.message.chat.id, call.message.message_id)

    elif data == "adm_charge" and is_admin(uid):
        bot.user_steps[uid] = {"step": "charge_target"}
        bot.edit_message_text("آیدی عددی یا یوزرنیم کاربر را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "adm_users" and is_admin(uid):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id, username, full_name, balance FROM users ORDER BY last_active DESC LIMIT 20")
        rows = c.fetchall()
        conn.close()
        text = "👥 کاربران:\n\n"
        for r in rows:
            text += f"`{r[0]}` | @{r[1] or '-'} | {r[2] or '-'}\nموجودی: {r[3]:,}\n──────\n"
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

    elif data == "adm_check_user" and is_admin(uid):
        bot.user_steps[uid] = {"step": "check_user"}
        bot.edit_message_text("آیدی عددی کاربر را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "adm_broadcast" and is_admin(uid):
        bot.user_steps[uid] = {"step": "broadcast"}
        bot.edit_message_text("پیام همگانی را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "adm_forced" and is_admin(uid):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, channel_title, channel_id FROM forced_channels")
        rows = c.fetchall()
        conn.close()
        mk = InlineKeyboardMarkup(row_width=1)
        for r in rows:
            mk.add(InlineKeyboardButton(f"❌ {r[1] or r[2]}", callback_data=f"delf_{r[0]}"))
        mk.add(InlineKeyboardButton("➕ اضافه", callback_data="addf"))
        mk.add(InlineKeyboardButton("🔙", callback_data="admin_panel"))
        bot.edit_message_text("قفل کانال‌ها:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "addf" and is_admin(uid):
        bot.user_steps[uid] = {"step": "add_forced"}
        bot.edit_message_text("آیدی کانال:", call.message.chat.id, call.message.message_id)

    elif data.startswith("delf_") and is_admin(uid):
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM forced_channels WHERE id=?", (int(data.split("_")[1]),))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "حذف شد")

    elif data == "adm_maint" and is_admin(uid):
        cur = get_setting("maintenance")
        set_setting("maintenance", "0" if cur == "1" else "1")
        bot.answer_callback_query(call.id, "تغییر کرد", show_alert=True)

    elif data == "adm_stats" and is_admin(uid):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM shop_orders")
        orders = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM gift_codes WHERE is_active=1")
        codes = c.fetchone()[0]
        conn.close()
        bot.send_message(call.message.chat.id, f"📊 آمار\nکاربران: {users}\nسفارشات: {orders}\nکدهای فعال: {codes}")

    bot.answer_callback_query(call.id)

print("✅ بخش ۲ آماده شد")
# ==================== بخش ۳ از ۴ ====================
# هندلر پیام‌ها (کاربر + ادمین)

@bot.message_handler(content_types=['text', 'sticker'])
def handle_messages(message):
    uid = message.from_user.id
    ensure_user(message.from_user)
    bot.user_steps = getattr(bot, "user_steps", {})
    step_data = bot.user_steps.get(uid, {})
    step = step_data.get("step")

    # ----- لینک پست استارز رایگان -----
    if step == "post_link":
        link = message.text.strip()
        task_id = step_data.get("task_id")
        code = generate_code(9)
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO free_star_orders (user_id, task_id, post_link, code, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
                  (uid, task_id, link, code, now_tehran().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ ثبت شد\nکد شما: `{code}`\nمنتظر تأیید ادمین باشید.", parse_mode="Markdown", reply_markup=main_menu(uid))
        for a in ADMIN_IDS:
            try: bot.send_message(a, f"📦 سفارش جدید\nکاربر: `{uid}`\nکد: `{code}`\nلینک: {link}", parse_mode="Markdown")
            except: pass
        bot.user_steps[uid] = {}
        return

    # ----- وارد کردن کد -----
    if step == "enter_code":
        code = message.text.strip().upper()
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT code_type, value, max_uses, used_count, expire_at, sticker_file_id, is_active FROM gift_codes WHERE code=?", (code,))
        row = c.fetchone()
        if not row or not row[6]:
            bot.send_message(message.chat.id, "❌ کد نامعتبر یا منسوخ شده.", reply_markup=main_menu(uid))
            conn.close()
            bot.user_steps[uid] = {}
            return
        if row[3] >= row[2]:
            bot.send_message(message.chat.id, "❌ دیر رسیدی، ظرفیت کد تکمیل شده.", reply_markup=main_menu(uid))
            conn.close()
            bot.user_steps[uid] = {}
            return
        if row[4]:
            try:
                if now_tehran().replace(tzinfo=None) > datetime.strptime(row[4], "%Y-%m-%d %H:%M"):
                    bot.send_message(message.chat.id, "❌ دیر رسیدی، کد منقضی شده.", reply_markup=main_menu(uid))
                    conn.close()
                    bot.user_steps[uid] = {}
                    return
            except: pass

        c.execute("UPDATE gift_codes SET used_count = used_count + 1 WHERE code=?", (code,))
        c.execute("INSERT INTO code_uses (code, user_id, used_at) VALUES (?, ?, ?)", (code, uid, now_tehran().strftime("%Y-%m-%d %H:%M")))
        conn.commit()

        if row[0] == "stars":
            rate = int(get_setting("star_to_toman", "4000"))
            amount = int(row[1]) * rate
            add_balance(uid, amount)
            bot.send_message(message.chat.id, f"✅ {row[1]} استارز ≈ {amount:,} تومان اضافه شد.", reply_markup=main_menu(uid))
        elif row[0] == "balance":
            add_balance(uid, int(row[1]))
            bot.send_message(message.chat.id, f"✅ {int(row[1]):,} تومان به حساب شما اضافه شد.", reply_markup=main_menu(uid))
        else:
            bot.send_message(message.chat.id, f"🎁 گیفت دریافت شد:\n{row[1]}")
            if row[5]:
                try: bot.send_sticker(message.chat.id, row[5])
                except: pass
            bot.send_message(message.chat.id, "ثبت شد.", reply_markup=main_menu(uid))
        conn.close()
        bot.user_steps[uid] = {}
        return

    # ----- شارژ با استارز -----
    if step == "charge_stars":
        try:
            stars = int(message.text.strip())
            rate = int(get_setting("star_to_toman", "4000"))
            toman = stars * rate
            bot.send_invoice(message.chat.id, title=f"شارژ {stars} استارز", description=f"≈ {toman:,} تومان",
                             invoice_payload=f"charge_{stars}_{uid}", provider_token="", currency="XTR",
                             prices=[LabeledPrice(f"{stars} Stars", stars)])
        except:
            bot.send_message(message.chat.id, "عدد بفرستید.")
        bot.user_steps[uid] = {}
        return

    # ----- خرید از فروشگاه -----
    if step == "shop_qty":
        try:
            qty = int(message.text.strip())
            p = step_data["product"]
            if qty < p[6] or qty > p[7]:
                bot.send_message(message.chat.id, f"تعداد باید بین {p[6]} تا {p[7]} باشد.")
                return
            bot.user_steps[uid] = {"step": "shop_pay", "product": p, "qty": qty}
            mk = InlineKeyboardMarkup(row_width=1)
            mk.add(InlineKeyboardButton(f"پرداخت با استارز ({p[4]*qty}⭐)", callback_data="pay_stars"),
                   InlineKeyboardButton(f"پرداخت با موجودی ({p[5]*qty:,}ت)", callback_data="pay_balance"),
                   InlineKeyboardButton("انصراف", callback_data="back_main"))
            bot.send_message(message.chat.id, f"محصول: {p[2]}\nتعداد: {qty}\nروش پرداخت را انتخاب کنید:", reply_markup=mk)
        except:
            bot.send_message(message.chat.id, "عدد بفرستید.")
        return

    # ----- پشتیبانی -----
    if step == "support_msg":
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO tickets (user_id, message, status, created_at) VALUES (?, ?, 'open', ?)",
                  (uid, message.text, now_tehran().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ پیام ارسال شد.", reply_markup=main_menu(uid))
        for a in ADMIN_IDS:
            try: bot.send_message(a, f"🛠 تیکت\nاز `{uid}`:\n{message.text}", parse_mode="Markdown")
            except: pass
        bot.user_steps[uid] = {}
        return

    # ==================== ادمین ====================
    if not is_admin(uid):
        bot.send_message(message.chat.id, "از منو استفاده کنید:", reply_markup=main_menu(uid))
        return

    # تأیید سفارش استارز رایگان
    if step == "approve_order":
        target = message.text.strip().lstrip("@")
        oid = step_data["oid"]
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id, code FROM free_star_orders WHERE id=?", (oid,))
        row = c.fetchone()
        if row:
            c.execute("UPDATE free_star_orders SET status='approved' WHERE id=?", (oid,))
            conn.commit()
            try:
                bot.send_message(row[0], f"✅ سفارش شما تأیید شد.\nکد: `{row[1]}`", parse_mode="Markdown")
            except: pass
            bot.send_message(message.chat.id, f"✅ سفارش #{oid} تأیید و به کاربر اطلاع داده شد.", reply_markup=admin_menu())
        conn.close()
        bot.user_steps[uid] = {}
        return

    # تأیید سفارش فروشگاه
    if step == "finish_shop":
        target = message.text.strip().lstrip("@")
        oid = step_data["oid"]
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id, product_title, quantity FROM shop_orders WHERE id=?", (oid,))
        row = c.fetchone()
        if row:
            c.execute("UPDATE shop_orders SET status='done' WHERE id=?", (oid,))
            conn.commit()
            try:
                bot.send_message(row[0], f"✅ سفارش شما انجام شد.\nمحصول: {row[1]}\nتعداد: {row[2]}")
            except: pass
            bot.send_message(message.chat.id, f"✅ سفارش #{oid} انجام شد و به کاربر اطلاع داده شد.", reply_markup=admin_menu())
        conn.close()
        bot.user_steps[uid] = {}
        return

    # اضافه کردن کار
    if step == "task_title":
        bot.user_steps[uid] = {"step": "task_type", "title": message.text}
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(InlineKeyboardButton("عضویت کانال", callback_data="tt_join"),
               InlineKeyboardButton("ریکشن پست", callback_data="tt_react"),
               InlineKeyboardButton("سایر", callback_data="tt_other"))
        bot.send_message(message.chat.id, "نوع کار را انتخاب کنید:", reply_markup=mk)
        return

    # ساخت محصول
    if step == "prod_title":
        bot.user_steps[uid] = {"step": "prod_price_stars", "ptype": step_data["ptype"], "title": message.text}
        bot.send_message(message.chat.id, "قیمت به استارز را بفرستید:")
        return

    if step == "prod_price_stars":
        bot.user_steps[uid] = {"step": "prod_price_bal", "ptype": step_data["ptype"], "title": step_data["title"], "ps": message.text}
        bot.send_message(message.chat.id, "قیمت به تومان (موجودی) را بفرستید:")
        return

    if step == "prod_price_bal":
        bot.user_steps[uid] = {"step": "prod_min", "ptype": step_data["ptype"], "title": step_data["title"], "ps": step_data["ps"], "pb": message.text}
        bot.send_message(message.chat.id, "حداقل تعداد:")
        return

    if step == "prod_min":
        bot.user_steps[uid] = {"step": "prod_max", "ptype": step_data["ptype"], "title": step_data["title"], "ps": step_data["ps"], "pb": step_data["pb"], "min": message.text}
        bot.send_message(message.chat.id, "حداکثر تعداد:")
        return

    if step == "prod_max":
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO products (product_type, title, price_stars, price_balance, min_qty, max_qty, is_active) VALUES (?, ?, ?, ?, ?, ?, 1)",
                      (step_data["ptype"], step_data["title"], int(step_data["ps"]), int(step_data["pb"]), int(step_data["min"]), int(message.text)))
            conn.commit()
            conn.close()
            bot.send_message(message.chat.id, "✅ محصول اضافه شد.", reply_markup=admin_menu())
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا: {e}")
        bot.user_steps[uid] = {}
        return

    # نرخ
    if step == "set_rate":
        try:
            set_setting("star_to_toman", str(int(message.text.strip())))
            bot.send_message(message.chat.id, "✅ نرخ تغییر کرد.", reply_markup=admin_menu())
        except:
            bot.send_message(message.chat.id, "عدد بفرستید.")
        bot.user_steps[uid] = {}
        return

    # شارژ دستی
    if step == "charge_target":
        bot.user_steps[uid] = {"step": "charge_amount", "target": message.text.strip().lstrip("@")}
        bot.send_message(message.chat.id, "مبلغ به تومان:")
        return

    if step == "charge_amount":
        try:
            target = step_data["target"]
            amount = int(message.text.strip())
            # اگر یوزرنیم بود سعی می‌کنیم آیدی پیدا کنیم (ساده)
            if not target.isdigit():
                bot.send_message(message.chat.id, "فعلاً آیدی عددی بفرستید (یوزرنیم در نسخه بعدی کامل‌تر می‌شود).")
                bot.user_steps[uid] = {}
                return
            tid = int(target)
            add_balance(tid, amount)
            bot.send_message(message.chat.id, f"✅ {amount:,} تومان به `{tid}` اضافه شد.", parse_mode="Markdown", reply_markup=admin_menu())
            try: bot.send_message(tid, f"💰 حساب شما {amount:,} تومان شارژ شد.")
            except: pass
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا: {e}")
        bot.user_steps[uid] = {}
        return

    # چک کاربر
    if step == "check_user":
        try:
            tid = int(message.text.strip())
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT user_id, username, full_name, balance, level FROM users WHERE user_id=?", (tid,))
            u = c.fetchone()
            conn.close()
            if u:
                text = f"🔍 کاربر\nآیدی: `{u[0]}`\nیوزرنیم: @{u[1] or '-'}\nنام: {u[2]}\nموجودی: {u[3]:,}\nسطح: {u[4]}"
                bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=admin_menu())
            else:
                bot.send_message(message.chat.id, "کاربر پیدا نشد.")
        except:
            bot.send_message(message.chat.id, "آیدی عددی بفرستید.")
        bot.user_steps[uid] = {}
        return

    # پیام همگانی
    if step == "broadcast":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        users = c.fetchall()
        conn.close()
        ok = 0
        for u in users:
            try:
                bot.send_message(u[0], message.text)
                ok += 1
            except: pass
        bot.send_message(message.chat.id, f"✅ به {ok} کاربر ارسال شد.", reply_markup=admin_menu())
        bot.user_steps[uid] = {}
        return

    # قفل کانال
    if step == "add_forced":
        try:
            chat = bot.get_chat(message.text.strip())
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO forced_channels (channel_id, channel_title) VALUES (?, ?)", (str(chat.id), chat.title))
            conn.commit()
            conn.close()
            bot.send_message(message.chat.id, f"✅ اضافه شد: {chat.title}", reply_markup=admin_menu())
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا: {e}")
        bot.user_steps[uid] = {}
        return

    bot.send_message(message.chat.id, "از منو استفاده کنید:", reply_markup=main_menu(uid))

print("✅ بخش ۳ آماده شد")
# ==================== بخش ۴ از ۴ ====================
# پرداخت + ساخت کد + نوع کار + اجرا

@bot.pre_checkout_query_handler(func=lambda q: True)
def pre_checkout(q):
    bot.answer_pre_checkout_query(q.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def on_payment(message):
    uid = message.from_user.id
    payload = message.successful_payment.invoice_payload
    stars = message.successful_payment.total_amount

    if payload.startswith("charge_"):
        rate = int(get_setting("star_to_toman", "4000"))
        toman = stars * rate
        add_balance(uid, toman)
        bot.send_message(message.chat.id, f"✅ {stars} استارز پرداخت شد\n{toman:,} تومان به موجودی اضافه شد.\nموجودی: {get_balance(uid):,}", reply_markup=main_menu(uid))
        for a in ADMIN_IDS:
            try: bot.send_message(a, f"⭐ شارژ\n`{uid}` → {stars} استارز", parse_mode="Markdown")
            except: pass

# ---------- پرداخت فروشگاه با استارز یا موجودی ----------
@bot.callback_query_handler(func=lambda c: c.data in ["pay_stars", "pay_balance"])
def shop_pay(c):
    uid = c.from_user.id
    bot.user_steps = getattr(bot, "user_steps", {})
    data = bot.user_steps.get(uid, {})
    if data.get("step") != "shop_pay":
        bot.answer_callback_query(c.id, "منقضی شده", show_alert=True)
        return

    p = data["product"]
    qty = data["qty"]

    if c.data == "pay_balance":
        total = p[5] * qty
        if get_balance(uid) < total:
            bot.answer_callback_query(c.id, "موجودی کافی نیست", show_alert=True)
            return
        add_balance(uid, -total)
        method = "balance"
        total_price = total
    else:
        # پرداخت با استارز
        total_stars = p[4] * qty
        bot.send_invoice(c.message.chat.id, title=p[2], description=f"{qty} عدد",
                         invoice_payload=f"shop_{p[0]}_{qty}_{uid}", provider_token="", currency="XTR",
                         prices=[LabeledPrice(p[2], total_stars)])
        bot.user_steps[uid] = {}
        bot.answer_callback_query(c.id)
        return

    # ثبت سفارش
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO shop_orders (user_id, product_id, product_title, quantity, pay_method, total_price, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)",
                (uid, p[0], p[2], qty, method, total_price, now_tehran().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    oid = cur.lastrowid
    conn.close()

    bot.edit_message_text(f"✅ سفارش ثبت شد\nشماره: #{oid}\nمنتظر تأیید ادمین باشید.", c.message.chat.id, c.message.message_id, reply_markup=main_menu(uid))
    for a in ADMIN_IDS:
        try:
            bot.send_message(a, f"🛍 سفارش فروشگاه #{oid}\nکاربر: `{uid}`\nمحصول: {p[2]}\nتعداد: {qty}\nروش: موجودی", parse_mode="Markdown")
        except: pass
    bot.user_steps[uid] = {}
    bot.answer_callback_query(c.id)

# ---------- نوع کار استارز رایگان ----------
@bot.callback_query_handler(func=lambda c: c.data.startswith("tt_"))
def task_type(c):
    uid = c.from_user.id
    if not is_admin(uid): return
    bot.user_steps = getattr(bot, "user_steps", {})
    ttype = c.data.split("_")[1]
    bot.user_steps[uid] = {"step": "task_target", "title": bot.user_steps[uid].get("title", "کار"), "type": ttype}
    bot.edit_message_text("تارگت را بفرستید (آیدی کانال یا لینک یا توضیحات):", c.message.chat.id, c.message.message_id)
    bot.answer_callback_query(c.id)

@bot.message_handler(func=lambda m: getattr(bot, "user_steps", {}).get(m.from_user.id, {}).get("step") == "task_target")
def task_target(m):
    uid = m.from_user.id
    if not is_admin(uid): return
    bot.user_steps[uid]["step"] = "task_reward"
    bot.user_steps[uid]["target"] = m.text
    bot.send_message(m.chat.id, "تعداد استارز پاداش:")

@bot.message_handler(func=lambda m: getattr(bot, "user_steps", {}).get(m.from_user.id, {}).get("step") == "task_reward")
def task_reward(m):
    uid = m.from_user.id
    if not is_admin(uid): return
    try:
        reward = int(m.text.strip())
        d = bot.user_steps[uid]
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO free_star_tasks (title, task_type, target, reward_stars, is_active) VALUES (?, ?, ?, ?, 1)",
                  (d["title"], d["type"], d["target"], reward))
        conn.commit()
        conn.close()
        bot.send_message(m.chat.id, "✅ کار اضافه شد.", reply_markup=admin_menu())
    except:
        bot.send_message(m.chat.id, "عدد بفرستید.")
    bot.user_steps[uid] = {}

# ---------- ساخت کد ----------
@bot.callback_query_handler(func=lambda c: c.data in ["code_stars", "code_gift", "code_balance"])
def create_code_type(c):
    uid = c.from_user.id
    if not is_admin(uid): return
    bot.user_steps = getattr(bot, "user_steps", {})
    ctype = c.data.split("_")[1]
    bot.user_steps[uid] = {"step": "code_value", "ctype": ctype}
    if ctype == "gift":
        bot.edit_message_text("اطلاعات گیفت را بفرستید:", c.message.chat.id, c.message.message_id)
    else:
        bot.edit_message_text("مقدار (تعداد استارز یا مبلغ تومان) را بفرستید:", c.message.chat.id, c.message.message_id)
    bot.answer_callback_query(c.id)

@bot.message_handler(func=lambda m: getattr(bot, "user_steps", {}).get(m.from_user.id, {}).get("step") == "code_value")
def code_value(m):
    uid = m.from_user.id
    if not is_admin(uid): return
    bot.user_steps[uid]["value"] = m.text
    bot.user_steps[uid]["step"] = "code_uses"
    bot.send_message(m.chat.id, "حداکثر تعداد نفرات (مثال: ۱ یا ۱۰):")

@bot.message_handler(func=lambda m: getattr(bot, "user_steps", {}).get(m.from_user.id, {}).get("step") == "code_uses")
def code_uses(m):
    uid = m.from_user.id
    if not is_admin(uid): return
    bot.user_steps[uid]["uses"] = m.text
    bot.user_steps[uid]["step"] = "code_expire"
    bot.send_message(m.chat.id, "مدت اعتبار به دقیقه (۰ = بدون انقضا):")

@bot.message_handler(func=lambda m: getattr(bot, "user_steps", {}).get(m.from_user.id, {}).get("step") == "code_expire")
def code_expire(m):
    uid = m.from_user.id
    if not is_admin(uid): return
    try:
        d = bot.user_steps[uid]
        uses = int(d["uses"])
        minutes = int(m.text.strip())
        code = generate_code(8)
        expire = (now_tehran() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M") if minutes > 0 else None

        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO gift_codes (code, code_type, value, max_uses, expire_at, is_active, created_by) VALUES (?, ?, ?, ?, ?, 1, ?)",
                  (code, d["ctype"], d["value"], uses, expire, uid))
        conn.commit()
        conn.close()

        bot.send_message(m.chat.id, f"✅ کد ساخته شد:\n`{code}`\nنوع: {d['ctype']}\nظرفیت: {uses}\nانقضا: {expire or 'ندارد'}", parse_mode="Markdown", reply_markup=admin_menu())
    except Exception as e:
        bot.send_message(m.chat.id, f"خطا: {e}")
    bot.user_steps[uid] = {}

# ---------- ارسال کد ----------
@bot.callback_query_handler(func=lambda c: c.data == "adm_send_code")
def send_code_menu(c):
    if not is_admin(c.from_user.id): return
    bot.user_steps = getattr(bot, "user_steps", {})
    bot.user_steps[c.from_user.id] = {"step": "send_code_value"}
    bot.edit_message_text("کد را بفرستید تا به کاربران ارسال شود:", c.message.chat.id, c.message.message_id)
    bot.answer_callback_query(c.id)

@bot.message_handler(func=lambda m: getattr(bot, "user_steps", {}).get(m.from_user.id, {}).get("step") == "send_code_value")
def send_code_to_users(m):
    uid = m.from_user.id
    if not is_admin(uid): return
    code = m.text.strip().upper()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    conn.close()
    ok = 0
    text = f"🎁 کد جدید تعیین شد\n\nکد: `{code}`\n\nبرای استفاده دستور /Gifts را بزنید و کد را ارسال کنید."
    for u in users:
        try:
            bot.send_message(u[0], text, parse_mode="Markdown")
            ok += 1
        except: pass
    bot.send_message(m.chat.id, f"✅ به {ok} کاربر ارسال شد.", reply_markup=admin_menu())
    bot.user_steps[uid] = {}

# ---------- اجرا ----------
print("🤖 ربات کامل با موفقیت روشن شد")
print("قابلیت‌ها: استارز رایگان | فروشگاه | کد هدیه | شارژ | پشتیبانی | پیام همگانی | پنل ادمین کامل")
bot.infinity_polling()
