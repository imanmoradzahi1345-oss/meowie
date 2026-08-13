# ==================== بخش ۱ از ۴ ====================
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
import sqlite3
import random
import string
from datetime import datetime, timedelta

BOT_TOKEN = "8968618358:AAHReb2nlduQkclIJE1V-_FKh206VxmYmuc"
ADMIN_IDS = [7530457395]

bot = telebot.TeleBot(BOT_TOKEN)

def get_connection():
    return sqlite3.connect("mainbot.db", check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        balance INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        joined_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        task_type TEXT,
        target TEXT,
        reward INTEGER DEFAULT 1,
        active INTEGER DEFAULT 1
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS free_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task_id INTEGER,
        link TEXT,
        code TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        code_type TEXT,
        value TEXT,
        max_uses INTEGER DEFAULT 1,
        used_count INTEGER DEFAULT 0,
        expire_at TEXT,
        active INTEGER DEFAULT 1
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        price_stars INTEGER,
        price_balance INTEGER,
        min_qty INTEGER DEFAULT 1,
        max_qty INTEGER DEFAULT 10,
        active INTEGER DEFAULT 1
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS shop_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_title TEXT,
        quantity INTEGER,
        total INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS forced_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT UNIQUE,
        title TEXT
    )''')

    # تنظیمات پیش‌فرض
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('star_rate', '4000')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance', '0')")

    conn.commit()
    conn.close()

init_db()

def is_admin(uid):
    return uid in ADMIN_IDS

def get_setting(key, default=""):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key, value):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def ensure_user(user):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id=?", (user.id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, username, full_name, balance, joined_at) VALUES (?, ?, ?, 0, ?)",
                  (user.id, user.username or "", user.full_name or "", datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
    else:
        c.execute("UPDATE users SET username=?, full_name=? WHERE user_id=?",
                  (user.username or "", user.full_name or "", user.id))
        conn.commit()
    conn.close()

def get_balance(uid):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def add_balance(uid, amount):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, uid))
    conn.commit()
    conn.close()

def generate_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# منوی اصلی
def main_menu(uid):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("⭐ استارز رایگان", callback_data="free_stars"),
        InlineKeyboardButton("👤 پروفایل", callback_data="profile")
    )
    markup.add(
        InlineKeyboardButton("🛒 فروشگاه", callback_data="shop"),
        InlineKeyboardButton("🎁 کد هدیه", callback_data="gift_code")
    )
    markup.add(InlineKeyboardButton("🛠 پشتیبانی", callback_data="support"))
    if is_admin(uid):
        markup.add(InlineKeyboardButton("👑 پنل ادمین", callback_data="admin"))
    return markup

def admin_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📦 سفارشات رایگان", callback_data="adm_free_orders"),
        InlineKeyboardButton("🛍 سفارشات فروشگاه", callback_data="adm_shop_orders")
    )
    markup.add(
        InlineKeyboardButton("➕ اضافه کردن کار", callback_data="adm_add_task"),
        InlineKeyboardButton("🗑 حذف کار", callback_data="adm_del_task")
    )
    markup.add(
        InlineKeyboardButton("🎁 ساخت کد هدیه", callback_data="adm_create_code"),
        InlineKeyboardButton("📢 ارسال کد به کاربران", callback_data="adm_send_code")
    )
    markup.add(
        InlineKeyboardButton("🛒 اضافه کردن محصول", callback_data="adm_add_product"),
        InlineKeyboardButton("🔒 قفل کانال", callback_data="adm_forced")
    )
    markup.add(
        InlineKeyboardButton("💰 تنظیم نرخ استارز", callback_data="adm_rate"),
        InlineKeyboardButton("💸 شارژ دستی", callback_data="adm_charge")
    )
    markup.add(
        InlineKeyboardButton("👥 لیست کاربران", callback_data="adm_users"),
        InlineKeyboardButton("📨 پیام همگانی", callback_data="adm_broadcast")
    )
    markup.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
    return markup

print("✅ بخش ۱ آماده است")
# ==================== بخش ۲ از ۴ ====================
# /start + کال‌بک‌ها

user_steps = {}

@bot.message_handler(commands=['start'])
def start(message):
    ensure_user(message.from_user)
    uid = message.from_user.id

    if get_setting("maintenance") == "1" and not is_admin(uid):
        bot.send_message(message.chat.id, "🛠️ ربات در حال تعمیرات است.")
        return

    # بررسی قفل کانال
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT channel_id, title FROM forced_channels")
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
                link = f"https://t.me/{str(ch_id).lstrip('@').replace('-100','')}"
                mk.add(InlineKeyboardButton(f"📢 {title or ch_id}", url=link))
            mk.add(InlineKeyboardButton("✅ عضو شدم - بررسی", callback_data="check_join"))
            bot.send_message(message.chat.id, "🔒 برای استفاده از ربات باید در کانال‌های زیر عضو شوید:", reply_markup=mk)
            return

    bot.send_message(message.chat.id, f"سلام {message.from_user.first_name}!\nبه ربات خوش آمدید.", reply_markup=main_menu(uid))

@bot.message_handler(commands=['Gifts', 'gifts'])
def gifts_cmd(message):
    ensure_user(message.from_user)
    user_steps[message.from_user.id] = {"step": "enter_code"}
    bot.send_message(message.chat.id, "🔑 کد هدیه را وارد کنید:")

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    uid = call.from_user.id
    ensure_user(call.from_user)
    data = call.data

    if data == "back_main":
        bot.edit_message_text("منوی اصلی:", call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))

    elif data == "check_join":
        bot.answer_callback_query(call.id)
        start(call.message)
        return

    # ---------- استارز رایگان ----------
    elif data == "free_stars":
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, title, reward FROM tasks WHERE active=1")
        tasks = c.fetchall()
        conn.close()
        if not tasks:
            bot.answer_callback_query(call.id, "فعلاً کاری تعریف نشده", show_alert=True)
            return
        mk = InlineKeyboardMarkup(row_width=1)
        for t in tasks:
            mk.add(InlineKeyboardButton(f"{t[1]} ({t[2]}⭐)", callback_data=f"task_{t[0]}"))
        mk.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
        bot.edit_message_text("کار مورد نظر را انتخاب کنید:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data.startswith("task_"):
        task_id = int(data.split("_")[1])
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT title, task_type, target, reward FROM tasks WHERE id=?", (task_id,))
        task = c.fetchone()
        conn.close()
        if not task:
            bot.answer_callback_query(call.id, "کار پیدا نشد", show_alert=True)
            return
        user_steps[uid] = {"step": "waiting_link", "task_id": task_id, "reward": task[3]}
        bot.edit_message_text(
            f"📌 {task[0]}\n\n{task[2]}\n\nبعد از انجام کار، لینک پست را بفرستید:",
            call.message.chat.id, call.message.message_id
        )

    # ---------- پروفایل ----------
    elif data == "profile":
        bal = get_balance(uid)
        rate = get_setting("star_rate", "4000")
        text = f"👤 **پروفایل**\n\nآیدی: `{uid}`\nموجودی: **{bal:,}** تومان\nنرخ: هر استارز ≈ {rate} تومان"
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(InlineKeyboardButton("⭐ شارژ حساب با استارز", callback_data="charge"),
               InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode="Markdown")

    elif data == "charge":
        user_steps[uid] = {"step": "charge_amount"}
        bot.edit_message_text("تعداد استارز مورد نظر را بفرستید (مثال: ۱۰):", call.message.chat.id, call.message.message_id)

    # ---------- فروشگاه ----------
    elif data == "shop":
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, title, price_stars, price_balance FROM products WHERE active=1")
        products = c.fetchall()
        conn.close()
        if not products:
            bot.answer_callback_query(call.id, "محصولی وجود ندارد", show_alert=True)
            return
        mk = InlineKeyboardMarkup(row_width=1)
        for p in products:
            mk.add(InlineKeyboardButton(f"{p[1]} | {p[2]}⭐ / {p[3]:,}ت", callback_data=f"prod_{p[0]}"))
        mk.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
        bot.edit_message_text("🛒 فروشگاه:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data.startswith("prod_"):
        pid = int(data.split("_")[1])
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, title, price_stars, price_balance, min_qty, max_qty FROM products WHERE id=?", (pid,))
        p = c.fetchone()
        conn.close()
        if not p:
            return
        user_steps[uid] = {"step": "shop_qty", "product": p}
        bot.edit_message_text(f"محصول: {p[1]}\nحداقل: {p[4]} | حداکثر: {p[5]}\n\nتعداد را بفرستید:", call.message.chat.id, call.message.message_id)

    # ---------- کد هدیه ----------
    elif data == "gift_code":
        user_steps[uid] = {"step": "enter_code"}
        bot.edit_message_text("کد هدیه را وارد کنید:\n(یا از دستور /Gifts استفاده کنید)", call.message.chat.id, call.message.message_id)

    # ---------- پشتیبانی ----------
    elif data == "support":
        user_steps[uid] = {"step": "support"}
        bot.edit_message_text("پیام خود را برای پشتیبانی بفرستید:", call.message.chat.id, call.message.message_id)

    # ==================== پنل ادمین ====================
    elif data == "admin" and is_admin(uid):
        bot.edit_message_text("👑 پنل ادمین:", call.message.chat.id, call.message.message_id, reply_markup=admin_menu())

    elif data == "adm_free_orders" and is_admin(uid):
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, user_id, code, link, created_at FROM free_orders WHERE status='pending' ORDER BY id DESC LIMIT 15")
        rows = c.fetchall()
        conn.close()
        if not rows:
            bot.send_message(call.message.chat.id, "هیچ سفارش در انتظاری نیست.")
            return
        text = "📦 سفارشات استارز رایگان:\n\n"
        mk = InlineKeyboardMarkup(row_width=1)
        for r in rows:
            text += f"#{r[0]} | کاربر `{r[1]}`\nکد: `{r[2]}`\n"
            mk.add(InlineKeyboardButton(f"✅ تأیید #{r[0]}", callback_data=f"approve_free_{r[0]}"))
        bot.send_message(call.message.chat.id, text, reply_markup=mk, parse_mode="Markdown")

    elif data.startswith("approve_free_") and is_admin(uid):
        oid = int(data.split("_")[2])
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT user_id, code FROM free_orders WHERE id=? AND status='pending'", (oid,))
        row = c.fetchone()
        if row:
            c.execute("UPDATE free_orders SET status='approved' WHERE id=?", (oid,))
            conn.commit()
            try:
                bot.send_message(row[0], f"✅ سفارش شما تأیید شد\nکد: `{row[1]}`", parse_mode="Markdown")
            except:
                pass
            bot.answer_callback_query(call.id, "تأیید شد", show_alert=True)
        conn.close()

    elif data == "adm_shop_orders" and is_admin(uid):
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, user_id, product_title, quantity, total FROM shop_orders WHERE status='pending' ORDER BY id DESC LIMIT 15")
        rows = c.fetchall()
        conn.close()
        if not rows:
            bot.send_message(call.message.chat.id, "سفارش فروشگاهی نیست.")
            return
        text = "🛍 سفارشات فروشگاه:\n\n"
        mk = InlineKeyboardMarkup(row_width=1)
        for r in rows:
            text += f"#{r[0]} | `{r[1]}` | {r[2]} × {r[3]}\n"
            mk.add(InlineKeyboardButton(f"✅ انجام شد #{r[0]}", callback_data=f"done_shop_{r[0]}"))
        bot.send_message(call.message.chat.id, text, reply_markup=mk, parse_mode="Markdown")

    elif data.startswith("done_shop_") and is_admin(uid):
        oid = int(data.split("_")[2])
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT user_id, product_title, quantity FROM shop_orders WHERE id=?", (oid,))
        row = c.fetchone()
        if row:
            c.execute("UPDATE shop_orders SET status='done' WHERE id=?", (oid,))
            conn.commit()
            try:
                bot.send_message(row[0], f"✅ سفارش شما انجام شد\n{row[1]} × {row[2]}")
            except:
                pass
            bot.answer_callback_query(call.id, "انجام شد", show_alert=True)
        conn.close()

    elif data == "adm_add_task" and is_admin(uid):
        user_steps[uid] = {"step": "add_task_title"}
        bot.edit_message_text("عنوان کار را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "adm_del_task" and is_admin(uid):
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, title FROM tasks WHERE active=1")
        tasks = c.fetchall()
        conn.close()
        mk = InlineKeyboardMarkup(row_width=1)
        for t in tasks:
            mk.add(InlineKeyboardButton(f"🗑 {t[1]}", callback_data=f"deltask_{t[0]}"))
        mk.add(InlineKeyboardButton("🔙", callback_data="admin"))
        bot.edit_message_text("کار را برای حذف انتخاب کنید:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data.startswith("deltask_") and is_admin(uid):
        tid = int(data.split("_")[1])
        conn = get_connection()
        c = conn.cursor()
        c.execute("UPDATE tasks SET active=0 WHERE id=?", (tid,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "حذف شد", show_alert=True)

    elif data == "adm_create_code" and is_admin(uid):
        user_steps[uid] = {"step": "code_type"}
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(InlineKeyboardButton("⭐ کد استارز", callback_data="ctype_stars"),
               InlineKeyboardButton("💰 کد شارژ حساب", callback_data="ctype_balance"),
               InlineKeyboardButton("🔙", callback_data="admin"))
        bot.edit_message_text("نوع کد را انتخاب کنید:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data.startswith("ctype_") and is_admin(uid):
        ctype = data.split("_")[1]
        user_steps[uid] = {"step": "code_value", "ctype": ctype}
        bot.edit_message_text("مقدار را بفرستید (تعداد استارز یا مبلغ تومان):", call.message.chat.id, call.message.message_id)

    elif data == "adm_send_code" and is_admin(uid):
        user_steps[uid] = {"step": "send_code"}
        bot.edit_message_text("کدی که می‌خواهید به همه کاربران ارسال شود را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "adm_add_product" and is_admin(uid):
        user_steps[uid] = {"step": "prod_title"}
        bot.edit_message_text("نام محصول را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "adm_rate" and is_admin(uid):
        user_steps[uid] = {"step": "set_rate"}
        bot.edit_message_text(f"نرخ فعلی: {get_setting('star_rate')}\nنرخ جدید را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "adm_charge" and is_admin(uid):
        user_steps[uid] = {"step": "charge_id"}
        bot.edit_message_text("آیدی عددی کاربر را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "adm_users" and is_admin(uid):
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT user_id, username, full_name, balance FROM users ORDER BY user_id DESC LIMIT 20")
        rows = c.fetchall()
        conn.close()
        text = "👥 لیست کاربران:\n\n"
        for r in rows:
            text += f"`{r[0]}` | @{r[1] or '-'} | {r[2] or '-'}\nموجودی: {r[3]:,}\n────────\n"
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

    elif data == "adm_broadcast" and is_admin(uid):
        user_steps[uid] = {"step": "broadcast"}
        bot.edit_message_text("پیام همگانی را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "adm_forced" and is_admin(uid):
        user_steps[uid] = {"step": "add_forced"}
        bot.edit_message_text("آیدی کانال برای قفل را بفرستید:", call.message.chat.id, call.message.message_id)

    bot.answer_callback_query(call.id)

print("✅ بخش ۲ آماده است")
# ==================== بخش ۳ از ۴ ====================
# هندلر پیام‌ها

@bot.message_handler(content_types=['text'])
def handle_text(message):
    uid = message.from_user.id
    ensure_user(message.from_user)
    step_data = user_steps.get(uid, {})
    step = step_data.get("step")

    # ----- لینک پست برای استارز رایگان -----
    if step == "waiting_link":
        link = message.text.strip()
        task_id = step_data.get("task_id")
        code = generate_code(9)

        conn = get_connection()
        c = conn.cursor()
        c.execute("INSERT INTO free_orders (user_id, task_id, link, code, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
                  (uid, task_id, link, code, datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        conn.close()

        bot.send_message(message.chat.id,
            f"✅ درخواست ثبت شد.\n\nکد شما: `{code}`\n\nبعد از تأیید ادمین به شما اطلاع داده می‌شود.",
            parse_mode="Markdown", reply_markup=main_menu(uid))

        for adm in ADMIN_IDS:
            try:
                bot.send_message(adm, f"📦 سفارش جدید استارز رایگان\nکاربر: `{uid}`\nکد: `{code}`\nلینک: {link}", parse_mode="Markdown")
            except:
                pass
        user_steps[uid] = {}
        return

    # ----- وارد کردن کد هدیه -----
    if step == "enter_code":
        code = message.text.strip().upper()
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT code_type, value, max_uses, used_count, expire_at, active FROM codes WHERE code=?", (code,))
        row = c.fetchone()

        if not row or row[5] == 0:
            bot.send_message(message.chat.id, "❌ کد نامعتبر است.", reply_markup=main_menu(uid))
            conn.close()
            user_steps[uid] = {}
            return

        if row[3] >= row[2]:
            bot.send_message(message.chat.id, "❌ دیر رسیدی، ظرفیت این کد تکمیل شده.", reply_markup=main_menu(uid))
            conn.close()
            user_steps[uid] = {}
            return

        if row[4]:
            try:
                if datetime.now() > datetime.strptime(row[4], "%Y-%m-%d %H:%M"):
                    bot.send_message(message.chat.id, "❌ دیر رسیدی، کد منقضی شده.", reply_markup=main_menu(uid))
                    conn.close()
                    user_steps[uid] = {}
                    return
            except:
                pass

        c.execute("UPDATE codes SET used_count = used_count + 1 WHERE code=?", (code,))
        conn.commit()
        conn.close()

        if row[0] == "stars":
            rate = int(get_setting("star_rate", "4000"))
            amount = int(row[1]) * rate
            add_balance(uid, amount)
            bot.send_message(message.chat.id, f"✅ {row[1]} استارز ≈ {amount:,} تومان به حساب شما اضافه شد.", reply_markup=main_menu(uid))
        else:
            add_balance(uid, int(row[1]))
            bot.send_message(message.chat.id, f"✅ {int(row[1]):,} تومان به حساب شما اضافه شد.", reply_markup=main_menu(uid))

        user_steps[uid] = {}
        return

    # ----- شارژ با استارز -----
    if step == "charge_amount":
        try:
            stars = int(message.text.strip())
            if stars < 1:
                bot.send_message(message.chat.id, "حداقل ۱ استارز")
                return
            rate = int(get_setting("star_rate", "4000"))
            toman = stars * rate
            bot.send_invoice(
                message.chat.id,
                title=f"شارژ {stars} استارز",
                description=f"معادل تقریبی {toman:,} تومان",
                invoice_payload=f"charge_{stars}_{uid}",
                provider_token="",
                currency="XTR",
                prices=[LabeledPrice(label=f"{stars} Stars", amount=stars)]
            )
        except:
            bot.send_message(message.chat.id, "فقط عدد بفرستید.")
        user_steps[uid] = {}
        return

    # ----- تعداد خرید از فروشگاه -----
    if step == "shop_qty":
        try:
            qty = int(message.text.strip())
            p = step_data["product"]
            if qty < p[4] or qty > p[5]:
                bot.send_message(message.chat.id, f"تعداد باید بین {p[4]} تا {p[5]} باشد.")
                return

            total = p[3] * qty
            if get_balance(uid) < total:
                bot.send_message(message.chat.id, f"موجودی کافی نیست.\nموجودی شما: {get_balance(uid):,}\nمبلغ لازم: {total:,}")
                user_steps[uid] = {}
                return

            add_balance(uid, -total)
            conn = get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO shop_orders (user_id, product_title, quantity, total, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
                      (uid, p[1], qty, total, datetime.now().strftime("%Y-%m-%d %H:%M")))
            conn.commit()
            oid = c.lastrowid
            conn.close()

            bot.send_message(message.chat.id, f"✅ سفارش ثبت شد\nشماره: #{oid}\nمبلغ: {total:,} تومان", reply_markup=main_menu(uid))
            for adm in ADMIN_IDS:
                try:
                    bot.send_message(adm, f"🛍 سفارش فروشگاه #{oid}\nکاربر: `{uid}`\nمحصول: {p[1]}\nتعداد: {qty}\nمبلغ: {total:,}", parse_mode="Markdown")
                except:
                    pass
        except:
            bot.send_message(message.chat.id, "فقط عدد بفرستید.")
        user_steps[uid] = {}
        return

    # ----- پشتیبانی -----
    if step == "support":
        for adm in ADMIN_IDS:
            try:
                bot.send_message(adm, f"🛠 پیام پشتیبانی\nاز کاربر `{uid}`:\n\n{message.text}", parse_mode="Markdown")
            except:
                pass
        bot.send_message(message.chat.id, "✅ پیام شما به پشتیبانی ارسال شد.", reply_markup=main_menu(uid))
        user_steps[uid] = {}
        return

    # ==================== بخش ادمین ====================
    if not is_admin(uid):
        bot.send_message(message.chat.id, "از منو استفاده کنید:", reply_markup=main_menu(uid))
        return

    # اضافه کردن کار
    if step == "add_task_title":
        user_steps[uid] = {"step": "add_task_target", "title": message.text}
        bot.send_message(message.chat.id, "توضیحات یا لینک کانال/پست را بفرستید:")
        return

    if step == "add_task_target":
        user_steps[uid] = {"step": "add_task_reward", "title": step_data["title"], "target": message.text}
        bot.send_message(message.chat.id, "تعداد استارز پاداش را بفرستید:")
        return

    if step == "add_task_reward":
        try:
            reward = int(message.text.strip())
            conn = get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO tasks (title, task_type, target, reward, active) VALUES (?, 'other', ?, ?, 1)",
                      (step_data["title"], step_data["target"], reward))
            conn.commit()
            conn.close()
            bot.send_message(message.chat.id, "✅ کار با موفقیت اضافه شد.", reply_markup=admin_menu())
        except:
            bot.send_message(message.chat.id, "عدد معتبر بفرستید.")
        user_steps[uid] = {}
        return

    # ساخت کد
    if step == "code_value":
        user_steps[uid] = {"step": "code_uses", "ctype": step_data["ctype"], "value": message.text}
        bot.send_message(message.chat.id, "حداکثر تعداد نفرات قابل استفاده را بفرستید (مثال: ۱ یا ۱۰):")
        return

    if step == "code_uses":
        user_steps[uid] = {"step": "code_expire", "ctype": step_data["ctype"], "value": step_data["value"], "uses": message.text}
        bot.send_message(message.chat.id, "مدت اعتبار به دقیقه را بفرستید (۰ = بدون انقضا):")
        return

    if step == "code_expire":
        try:
            uses = int(step_data["uses"])
            minutes = int(message.text.strip())
            code = generate_code(8)
            expire = (datetime.now() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M") if minutes > 0 else None

            conn = get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO codes (code, code_type, value, max_uses, expire_at, active) VALUES (?, ?, ?, ?, ?, 1)",
                      (code, step_data["ctype"], step_data["value"], uses, expire))
            conn.commit()
            conn.close()

            bot.send_message(message.chat.id,
                f"✅ کد ساخته شد:\n\nکد: `{code}`\nنوع: {step_data['ctype']}\nمقدار: {step_data['value']}\nظرفیت: {uses}\nانقضا: {expire or 'ندارد'}",
                parse_mode="Markdown", reply_markup=admin_menu())
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا: {e}")
        user_steps[uid] = {}
        return

    # ارسال کد به کاربران
    if step == "send_code":
        code = message.text.strip().upper()
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        users = c.fetchall()
        conn.close()

        text = f"🎁 کد جدید تعیین شد\n\nکد: `{code}`\n\nبرای استفاده دستور /Gifts را بزنید و کد را ارسال کنید."
        success = 0
        for u in users:
            try:
                bot.send_message(u[0], text, parse_mode="Markdown")
                success += 1
            except:
                pass
        bot.send_message(message.chat.id, f"✅ کد به {success} کاربر ارسال شد.", reply_markup=admin_menu())
        user_steps[uid] = {}
        return

    # اضافه کردن محصول
    if step == "prod_title":
        user_steps[uid] = {"step": "prod_stars", "title": message.text}
        bot.send_message(message.chat.id, "قیمت به استارز را بفرستید:")
        return

    if step == "prod_stars":
        user_steps[uid] = {"step": "prod_balance", "title": step_data["title"], "stars": message.text}
        bot.send_message(message.chat.id, "قیمت به تومان (موجودی) را بفرستید:")
        return

    if step == "prod_balance":
        user_steps[uid] = {"step": "prod_min", "title": step_data["title"], "stars": step_data["stars"], "balance": message.text}
        bot.send_message(message.chat.id, "حداقل تعداد خرید:")
        return

    if step == "prod_min":
        user_steps[uid] = {"step": "prod_max", "title": step_data["title"], "stars": step_data["stars"], "balance": step_data["balance"], "min": message.text}
        bot.send_message(message.chat.id, "حداکثر تعداد خرید:")
        return

    if step == "prod_max":
        try:
            conn = get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO products (title, price_stars, price_balance, min_qty, max_qty, active) VALUES (?, ?, ?, ?, ?, 1)",
                      (step_data["title"], int(step_data["stars"]), int(step_data["balance"]), int(step_data["min"]), int(message.text)))
            conn.commit()
            conn.close()
            bot.send_message(message.chat.id, "✅ محصول اضافه شد.", reply_markup=admin_menu())
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا: {e}")
        user_steps[uid] = {}
        return

    # تنظیم نرخ
    if step == "set_rate":
        try:
            set_setting("star_rate", str(int(message.text.strip())))
            bot.send_message(message.chat.id, "✅ نرخ استارز تغییر کرد.", reply_markup=admin_menu())
        except:
            bot.send_message(message.chat.id, "عدد معتبر بفرستید.")
        user_steps[uid] = {}
        return

    # شارژ دستی
    if step == "charge_id":
        user_steps[uid] = {"step": "charge_amount_admin", "target": message.text.strip()}
        bot.send_message(message.chat.id, "مبلغ به تومان را بفرستید:")
        return

    if step == "charge_amount_admin":
        try:
            target = int(step_data["target"])
            amount = int(message.text.strip())
            add_balance(target, amount)
            bot.send_message(message.chat.id, f"✅ {amount:,} تومان به کاربر `{target}` اضافه شد.", parse_mode="Markdown", reply_markup=admin_menu())
            try:
                bot.send_message(target, f"💰 حساب شما توسط ادمین {amount:,} تومان شارژ شد.")
            except:
                pass
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا: {e}")
        user_steps[uid] = {}
        return

    # پیام همگانی
    if step == "broadcast":
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        users = c.fetchall()
        conn.close()
        success = 0
        for u in users:
            try:
                bot.send_message(u[0], message.text)
                success += 1
            except:
                pass
        bot.send_message(message.chat.id, f"✅ پیام به {success} کاربر ارسال شد.", reply_markup=admin_menu())
        user_steps[uid] = {}
        return

    # قفل کانال
    if step == "add_forced":
        try:
            chat = bot.get_chat(message.text.strip())
            conn = get_connection()
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO forced_channels (channel_id, title) VALUES (?, ?)", (str(chat.id), chat.title))
            conn.commit()
            conn.close()
            bot.send_message(message.chat.id, f"✅ کانال «{chat.title}» به لیست قفل اضافه شد.", reply_markup=admin_menu())
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا: {e}\nمطمئن شوید ربات ادمین کانال است.")
        user_steps[uid] = {}
        return

    bot.send_message(message.chat.id, "از منو استفاده کنید:", reply_markup=main_menu(uid))

print("✅ بخش ۳ آماده است")
# ==================== بخش ۴ از ۴ ====================
# پرداخت استارز + اجرا

@bot.pre_checkout_query_handler(func=lambda q: True)
def pre_checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def successful_payment(message):
    uid = message.from_user.id
    payment = message.successful_payment
    payload = payment.invoice_payload
    stars = payment.total_amount

    if payload.startswith("charge_"):
        rate = int(get_setting("star_rate", "4000"))
        toman = stars * rate
        add_balance(uid, toman)

        bot.send_message(message.chat.id,
            f"✅ پرداخت موفق!\n\n"
            f"{stars} استارز پرداخت شد\n"
            f"{toman:,} تومان به موجودی اضافه شد\n"
            f"موجودی جدید: {get_balance(uid):,} تومان",
            reply_markup=main_menu(uid))

        for adm in ADMIN_IDS:
            try:
                bot.send_message(adm, f"⭐ شارژ جدید\nکاربر: `{uid}`\n{stars} استارز ≈ {toman:,} تومان", parse_mode="Markdown")
            except:
                pass

# ---------- اجرا ----------
print("🤖 ربات با موفقیت روشن شد")
print("قابلیت‌های فعال:")
print("- استارز رایگان (کار + لینک + کد + تأیید ادمین)")
print("- پروفایل و شارژ با استارز")
print("- فروشگاه (خرید با موجودی)")
print("- کد هدیه (با ظرفیت و انقضا)")
print("- پشتیبانی")
print("- قفل کانال")
print("- پنل ادمین کامل")
print("- پیام همگانی")
print("- شارژ دستی کاربر")
bot.infinity_polling()
