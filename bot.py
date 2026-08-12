import os
import random
import string
import sqlite3
import telebot
from telebot import types

# اطلاعات اختصاصی ربات
TOKEN = "8924668463:AAH7rV1LMZZ6Amn3JEQV6SRHeEM9KwI6lgA"
ADMIN_ID = 7530457395

bot = telebot.TeleBot(TOKEN)
DB_NAME = "bot_database.db"

# ---------------------------------------------------------
# ۱. راه‌اندازی و مدیریت دیتابیس (Database Initialization)
# ---------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # جدول کاربران
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            stars INTEGER DEFAULT 0,
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # جدول کانال‌های قفل اجباری
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS forced_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT UNIQUE,
            title TEXT
        )
    ''')
    
    # جدول سفارشات استارز
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_code TEXT PRIMARY KEY,
            user_id INTEGER,
            post_link TEXT,
            status TEXT DEFAULT 'معلق',
            reason TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # جدول کدهای هدیه پیشرفته (استارز و گیفت تلگرام)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gift_codes (
            code TEXT PRIMARY KEY,
            type TEXT, -- 'stars' یا 'gift'
            reward_title TEXT,
            stars_amount INTEGER DEFAULT 0,
            sticker_id TEXT DEFAULT '',
            capacity INTEGER,
            used_count INTEGER DEFAULT 0
        )
    ''')
    
    # جدول کدهای مصرف شده
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS used_codes (
            user_id INTEGER,
            code TEXT,
            PRIMARY KEY (user_id, code)
        )
    ''')
    
    # جدول تنظیمات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('star_rate', '40000')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('star_unit', '10')")
    
    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect(DB_NAME)

def get_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
    conn.close()
    return user

def generate_random_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# ---------------------------------------------------------
# ۲. بررسی قفل عضویت اجباری (Forced Join Middleware)
# ---------------------------------------------------------
def check_forced_join(user_id):
    if user_id == ADMIN_ID:
        return True, []
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id, title FROM forced_channels")
    channels = cursor.fetchall()
    conn.close()
    
    not_joined = []
    for ch_id, title in channels:
        try:
            member = bot.get_chat_member(ch_id, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                not_joined.append((ch_id, title))
        except Exception:
            pass # در صورت بروز خطا در دسترسی به کانال
            
    if not_joined:
        return False, not_joined
    return True, []

def forced_join_keyboard(not_joined_channels):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for ch_id, title in not_joined_channels:
        url = f"https://t.me/{ch_id.replace('@', '')}" if ch_id.startswith('@') else "https://t.me/telegram"
        markup.add(types.InlineKeyboardButton(f"📢 عضویت در {title}", url=url))
    markup.add(types.InlineKeyboardButton("🔄 بررسی عضویت", callback_data="check_subscription"))
    return markup

# ---------------------------------------------------------
# ۳. کیبوردهای اصلی و پنل مدیریت
# ---------------------------------------------------------
def main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_stars = types.KeyboardButton("⭐ استارز رایگان / ثبت سفارش")
    btn_giveaway = types.KeyboardButton("🎁 کدهای هدیه و قرعه‌کشی")
    btn_profile = types.KeyboardButton("👤 پروفایل و شارژ حساب")
    btn_orders = types.KeyboardButton("📋 پیگیری سفارشات من")
    
    markup.add(btn_stars, btn_giveaway)
    markup.add(btn_profile, btn_orders)
    
    if user_id == ADMIN_ID:
        btn_admin = types.KeyboardButton("⚙️ پنل مدیریت ارشد")
        markup.add(btn_admin)
    return markup

def admin_main_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📦 سفارشات معلق", callback_data="admin_pending_orders"),
        types.InlineKeyboardButton("🔒 مدیریت قفل کانال‌ها", callback_data="admin_channels_menu"),
        types.InlineKeyboardButton("⭐ ساخت کد استارز", callback_data="admin_create_star_code"),
        types.InlineKeyboardButton("🧸 ساخت کد گیفت تلگرام", callback_data="admin_create_gift_code"),
        types.InlineKeyboardButton("💳 شارژ دستی کاربر", callback_data="admin_recharge_user"),
        types.InlineKeyboardButton("📊 تنظیم نرخ استارز", callback_data="admin_set_rate"),
        types.InlineKeyboardButton("📈 آمار کامل ربات", callback_data="admin_stats"),
        types.InlineKeyboardButton("📣 ارسال همگانی", callback_data="admin_broadcast")
    )
    return markup

# ---------------------------------------------------------
# ۴. پردازش دستورات اصلی کاربر
# ---------------------------------------------------------
@bot.message_handler(commands=['start', 'Gifts'])
def start_and_gifts_handler(message):
    user_id = message.from_user.id
    get_user(user_id)
    
    is_joined, not_joined = check_forced_join(user_id)
    if not is_joined:
        bot.send_message(
            message.chat.id,
            "⚠️ **دسترسی محدود شده است!**\n\nبرای استفاده از ربات و ثبت کدها، ابتدا باید در کانال‌های زیر عضو شوید:",
            parse_mode="Markdown",
            reply_markup=forced_join_keyboard(not_joined)
        )
        return

    if message.text.startswith('/Gifts'):
        msg = bot.send_message(
            message.chat.id,
            "🎁 **ثبت کد هدیه و قرعه‌کشی**\n\nلطفاً کد هدیه خود را ارسال کنید:"
        )
        bot.register_next_step_handler(msg, process_code_redeem)
        return

    bot.send_message(
        message.chat.id,
        f"سلام {message.from_user.first_name} عزیز!\nبه ربات پیشرفته خدمات استارز و قرعه‌کشی خوش آمدید.",
        reply_markup=main_keyboard(user_id)
    )

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def check_subscription_callback(call):
    is_joined, not_joined = check_forced_join(call.from_user.id)
    if is_joined:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(
            call.message.chat.id,
            "✅ عضویت شما تایید شد! اکنون می‌توانید از امکانات ربات استفاده کنید.",
            reply_markup=main_keyboard(call.from_user.id)
        )
    else:
        bot.answer_callback_query(call.id, "❌ هنوز در تمام کانال‌ها عضو نشده‌اید!", show_alert=True)

# ---------------------------------------------------------
# ۵. بخش پروفایل، پیگیری و شارژ حساب
# ---------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "👤 پروفایل و شارژ حساب")
def profile_handler(message):
    is_joined, not_joined = check_forced_join(message.from_user.id)
    if not is_joined:
        bot.send_message(message.chat.id, "⚠️ ابتدا در کانال‌های قفل عضو شوید.", reply_markup=forced_join_keyboard(not_joined))
        return

    user = get_user(message.from_user.id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key='star_rate'")
    rate = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key='star_unit'")
    unit = cursor.fetchone()[0]
    conn.close()
    
    text = (
        f"👤 **پروفایل کاربری**\n\n"
        f"🆔 شناسه کاربری: `{user[0]}`\n"
        f"💰 موجودی اعتبار: {user[1]:,} تومان\n"
        f"⭐ استارز دریافت شده: {user[2]} عدد\n\n"
        f"🌐 **نرخ تبدیل استارز:**\n"
        f"هر {unit} استارز = {int(rate):,} تومان شارژ"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 شارژ آنلاین با استارز تلگرام", callback_data="recharge_stars"))
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "recharge_stars")
def recharge_stars_callback(call):
    msg = bot.send_message(call.message.chat.id, "تعداد استارز مدنظر جهت پرداخت را به عدد وارد کنید:")
    bot.register_next_step_handler(msg, process_star_payment)

def process_star_payment(message):
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "❌ لطفاً فقط عدد وارد کنید.")
        return
    stars_amount = int(message.text)
    prices = [types.LabeledPrice(label="Telegram Stars", amount=stars_amount)]
    bot.send_invoice(
        message.chat.id,
        title="شارژ حساب ربات",
        description=f"افزایش اعتبار حساب با پرداخت {stars_amount} استارز",
        invoice_payload=f"stars_recharge_{stars_amount}",
        provider_token="",
        currency="XTR",
        prices=prices
    )

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout_process(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def successful_payment_handler(message):
    payload = message.successful_payment.invoice_payload
    stars_amount = int(payload.split("_")[-1])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key='star_rate'")
    rate = int(cursor.fetchone()[0])
    cursor.execute("SELECT value FROM settings WHERE key='star_unit'")
    unit = int(cursor.fetchone()[0])
    added_balance = (stars_amount / unit) * rate
    cursor.execute("UPDATE users SET balance = balance + ?, stars = stars + ? WHERE user_id = ?", 
                   (added_balance, stars_amount, message.from_user.id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f"✅ پرداخت با موفقیت انجام شد!\nحساب شما به مبلغ {int(added_balance):,} تومان شارژ شد.")

@bot.message_handler(func=lambda m: m.text == "📋 پیگیری سفارشات من")
def my_orders_handler(message):
    is_joined, not_joined = check_forced_join(message.from_user.id)
    if not is_joined:
        bot.send_message(message.chat.id, "⚠️ ابتدا در کانال‌های قفل عضو شوید.", reply_markup=forced_join_keyboard(not_joined))
        return

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT order_code, post_link, status, reason FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 5", (message.from_user.id,))
    orders = cursor.fetchall()
    conn.close()
    
    if not orders:
        bot.send_message(message.chat.id, "شما هیچ سفارشی ثبت نکرده‌اید.")
        return
        
    text = "📋 **لیست آخرین سفارشات شما:**\n\n"
    for code, link, status, reason in orders:
        text += f"🔑 کد: `{code}`\n🔗 لینک: {link}\n📌 وضعیت: **{status}**\n"
        if reason:
            text += f"⚠️ دلیل رد: {reason}\n"
        text += "---------------------\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ---------------------------------------------------------
# ۶. ثبت سفارش استارز رایگان
# ---------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "⭐ استارز رایگان / ثبت سفارش")
def free_stars_handler(message):
    is_joined, not_joined = check_forced_join(message.from_user.id)
    if not is_joined:
        bot.send_message(message.chat.id, "⚠️ ابتدا در کانال‌های قفل عضو شوید.", reply_markup=forced_join_keyboard(not_joined))
        return

    msg = bot.send_message(message.chat.id, "لطفاً لینک پستی که می‌خواهید استارز به آن تعلق گیرد را بفرستید:")
    bot.register_next_step_handler(msg, process_order_submission)

def process_order_submission(message):
    post_link = message.text
    if not post_link.startswith("http"):
        bot.send_message(message.chat.id, "❌ لینک ارسالی معتبر نیست.")
        return
    order_code = f"ST-{generate_random_code(6)}"
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO orders (order_code, user_id, post_link) VALUES (?, ?, ?)",
                   (order_code, message.from_user.id, post_link))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f"✅ سفارش شما ثبت شد!\n🔑 کد پیگیری: `{order_code}`", parse_mode="Markdown")
    
    # اطلاع به ادمین
    admin_markup = types.InlineKeyboardMarkup()
    admin_markup.add(
        types.InlineKeyboardButton("✅ تایید سفارش", callback_data=f"approve_{order_code}"),
        types.InlineKeyboardButton("❌ رد سفارش", callback_data=f"reject_{order_code}")
    )
    bot.send_message(ADMIN_ID, f"📦 **سفارش جدید استارز**\n\nکد: `{order_code}`\nکاربر: `{message.from_user.id}`\nلینک: {post_link}",
                     parse_mode="Markdown", reply_markup=admin_markup)

# ---------------------------------------------------------
# ۷. بخش کدهای هدیه و قرعه‌کشی
# ---------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "🎁 کدهای هدیه و قرعه‌کشی")
def gift_and_draw_handler(message):
    is_joined, not_joined = check_forced_join(message.from_user.id)
    if not is_joined:
        bot.send_message(message.chat.id, "⚠️ ابتدا در کانال‌های قفل عضو شوید.", reply_markup=forced_join_keyboard(not_joined))
        return

    msg = bot.send_message(
        message.chat.id,
        "📌 **بخش کدهای هدیه و قرعه‌کشی**\n\n"
        "برای فعال‌سازی کد، آن را بفرستید یا از دستور `/Gifts کد` استفاده کنید:"
    )
    bot.register_next_step_handler(msg, process_code_redeem)

def process_code_redeem(message):
    code_input = message.text.replace('/Gifts', '').strip()
    user_id = message.from_user.id
    
    if not code_input:
        bot.send_message(message.chat.id, "❌ کد وارد نشده است.")
        return

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM used_codes WHERE user_id=? AND code=?", (user_id, code_input))
    if cursor.fetchone():
        bot.send_message(message.chat.id, "❌ شما قبلاً از این کد استفاده کرده‌اید.")
        conn.close()
        return
        
    cursor.execute("SELECT * FROM gift_codes WHERE code=?", (code_input,))
    code_data = cursor.fetchone()
    if not code_data:
        bot.send_message(message.chat.id, "❌ کد هدیه وارد شده معتبر نیست یا منقضی شده است.")
        conn.close()
        return
        
    code, c_type, reward_title, stars_amount, sticker_id, capacity, used_count = code_data
    if used_count >= capacity:
        bot.send_message(message.chat.id, "❌ ظرفیت این کد به پایان رسیده است.")
        conn.close()
        return
        
    # ثبت استفاده
    cursor.execute("UPDATE gift_codes SET used_count = used_count + 1 WHERE code=?", (code_input,))
    cursor.execute("INSERT INTO used_codes (user_id, code) VALUES (?, ?)", (user_id, code_input))
    
    if c_type == "stars":
        cursor.execute("UPDATE users SET stars = stars + ? WHERE user_id=?", (stars_amount, user_id))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"🎉 **مبارک است!**\nتعداد {stars_amount} استارز به حساب شما اضافه شد.")
    else:
        conn.commit()
        conn.close()
        if sticker_id:
            bot.send_sticker(message.chat.id, sticker_id)
        bot.send_message(message.chat.id, f"🎉 **تبریک! شما برنده گیفت تلگرام شدید!**\n🎁 عنوان جایزه: **{reward_title}**\n\nجهت دریافت گیفت، کد پیگیری `{code_input}` را به پشتیبانی ارائه دهید.")

# ---------------------------------------------------------
# ۸. پنل مدیریت کامل ارشد (Admin Panel)
# ---------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "⚙️ پنل مدیریت ارشد" and m.from_user.id == ADMIN_ID)
def admin_panel_handler(message):
    bot.send_message(message.chat.id, "به پنل مدیریت ارشد خوش آمدید:", reply_markup=admin_main_keyboard())

# --- مدیریت قفل کانال‌ها ---
@bot.callback_query_handler(func=lambda call: call.data == "admin_channels_menu" and call.from_user.id == ADMIN_ID)
def admin_channels_menu(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("➕ افزودن کانال قفل", callback_data="admin_add_channel"),
        types.InlineKeyboardButton("🗑 حذف کانال قفل", callback_data="admin_del_channel")
    )
    bot.send_message(call.message.chat.id, "مدیریت کانال‌های قفل اجباری:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "admin_add_channel" and call.from_user.id == ADMIN_ID)
def admin_add_channel_start(call):
    msg = bot.send_message(call.message.chat.id, "آیدی کانال و عنوان را به فرمت زیر بفرستید:\n`@ChannelID,عنوان کانال`\n\n*(ربات باید در کانال ادمین باشد)*", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_channel_save)

def process_add_channel_save(message):
    try:
        ch_id, title = message.text.split(",")
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO forced_channels (channel_id, title) VALUES (?, ?)", (ch_id.strip(), title.strip()))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ کانال قفل با موفقیت اضافه شد.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطا: {e}")

# --- ساخت کد استارز پیشرفته ---
@bot.callback_query_handler(func=lambda call: call.data == "admin_create_star_code" and call.from_user.id == ADMIN_ID)
def admin_create_star_code_start(call):
    msg = bot.send_message(call.message.chat.id, "تعداد استارز جایزه را به عدد وارد کنید:")
    bot.register_next_step_handler(msg, process_star_code_step1)

def process_star_code_step1(message):
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "❌ فقط عدد وارد کنید.")
        return
    stars_val = int(message.text)
    msg = bot.send_message(message.chat.id, "کد اختصاصی را وارد کنید (یا کلمه `auto` را برای کد رندوم بفرستید):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, lambda m: process_star_code_step2(m, stars_val))

def process_star_code_step2(message, stars_val):
    code = generate_random_code(8) if message.text.lower() == 'auto' else message.text.strip()
    msg = bot.send_message(message.chat.id, "ظرفیت تعداد نفرات استفاده کننده را وارد کنید:")
    bot.register_next_step_handler(msg, lambda m: process_star_code_step3(m, stars_val, code))

def process_star_code_step3(message, stars_val, code):
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "❌ عدد معتبر وارد کنید.")
        return
    capacity = int(message.text)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📢 ارسال به کانال ادمین", callback_data=f"sendcode_channel_stars_{code}"),
        types.InlineKeyboardButton("👥 ارسال همگانی به کاربران", callback_data=f"sendcode_users_stars_{code}")
    )
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO gift_codes (code, type, reward_title, stars_amount, capacity) VALUES (?, 'stars', 'استارز رایگان', ?, ?)",
                   (code, stars_val, capacity))
    conn.commit()
    c
