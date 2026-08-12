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

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # جدول کاربران
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            stars INTEGER DEFAULT 0,
            completed_tasks TEXT DEFAULT ''
        )
    ''')
    
    # جدول مأموریت‌ها (مربوط به استارز رایگان)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            channel_id TEXT,
            reward INTEGER DEFAULT 1
        )
    ''')
    
    # جدول سفارشات استارز
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_code TEXT PRIMARY KEY,
            user_id INTEGER,
            post_link TEXT,
            status TEXT DEFAULT 'در حال بررسی',
            reason TEXT DEFAULT ''
        )
    ''')
    
    # جدول کدهای هدیه و ظرفیت
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gift_codes (
            code TEXT PRIMARY KEY,
            reward_type TEXT,
            reward_value INTEGER,
            capacity INTEGER,
            used_count INTEGER DEFAULT 0
        )
    ''')
    
    # جدول کدهای استفاده شده توسط کاربران
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS used_codes (
            user_id INTEGER,
            code TEXT,
            PRIMARY KEY (user_id, code)
        )
    ''')
    
    # جدول تنظیمات (نرخ تبدیل استارز به شارژ)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # نرخ اولیه (۱۰ استارز = ۴۰۰۰۰ تومان شارژ)
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

def main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_stars = types.KeyboardButton("⭐ استارز رایگان")
    btn_giveaway = types.KeyboardButton("🎁 قرعه‌کشی و ثبت کد")
    btn_profile = types.KeyboardButton("👤 پروفایل و شارژ حساب")
    markup.add(btn_stars, btn_giveaway, btn_profile)
    if user_id == ADMIN_ID:
        btn_admin = types.KeyboardButton("⚙️ پنل مدیریت")
        markup.add(btn_admin)
    return markup

def admin_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ افزودن مأموریت", callback_data="admin_add_task"),
        types.InlineKeyboardButton("🔑 ساخت کد هدیه", callback_data="admin_create_code"),
        types.InlineKeyboardButton("📊 تنظیم نرخ استارز", callback_data="admin_set_rate")
    )
    return markup

@bot.message_handler(commands=['start'])
def start_cmd(message):
    get_user(message.from_user.id)
    bot.send_message(
        message.chat.id,
        f"سلام {message.from_user.first_name} عزیز!\nبه ربات خدمات استارز و قرعه‌کشی خوش آمدید.",
        reply_markup=main_keyboard(message.from_user.id)
    )

@bot.message_handler(func=lambda m: m.text == "👤 پروفایل و شارژ حساب")
def profile_handler(message):
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
        f"🆔 شناسه: `{user[0]}`\n"
        f"💰 موجودی حساب: {user[1]:,} تومان\n"
        f"⭐ استارز دریافت شده: {user[2]} عدد\n\n"
        f"🌐 **نرخ ارزش استارز:**\n"
        f"هر {unit} استارز = {int(rate):,} تومان شارژ حساب"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 شارژ حساب با استارز تلگرام", callback_data="recharge_stars"))
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "recharge_stars")
def recharge_stars_callback(call):
    msg = bot.send_message(call.message.chat.id, "تعداد استارز مدنظر برای پرداخت را به عدد انگلیسی وارد کنید:")
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

@bot.message_handler(func=lambda m: m.text == "⭐ استارز رایگان")
def free_stars_handler(message):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks")
    tasks = cursor.fetchall()
    conn.close()
    if not tasks:
        bot.send_message(message.chat.id, "فعلاً هیچ مأموریت فعالی توسط ادمین ثبت نشده است.")
        return
    markup = types.InlineKeyboardMarkup()
    for task in tasks:
        markup.add(types.InlineKeyboardButton(f"📌 {task[1]}", callback_data=f"check_task_{task[0]}"))
    bot.send_message(message.chat.id, "جهت دریافت استارز رایگان، مأموریت‌های زیر را انجام دهید:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("check_task_"))
def check_task_callback(call):
    task_id = int(call.data.split("_")[-1])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
    task = cursor.fetchone()
    conn.close()
    if not task:
        bot.answer_callback_query(call.id, "مأموریت یافت نشد.")
        return
    try:
        member = bot.get_chat_member(task[2], call.from_user.id)
        if member.status in ['member', 'administrator', 'creator']:
            msg = bot.send_message(call.message.chat.id, "✅ عضویت شما تایید شد!\nلطفاً لینک پستی که می‌خواهید استارز دریافت کند را بفرستید:")
            bot.register_next_step_handler(msg, process_order_submission)
        else:
            bot.answer_callback_query(call.id, f"❌ هنوز در کانال {task[2]} عضو نشده‌اید!", show_alert=True)
    except Exception:
        bot.answer_callback_query(call.id, "خطا در بررسی عضویت. مطمئن شوید ربات در کانال ادمین است.", show_alert=True)

def process_order_submission(message):
    post_link = message.text
    if not post_link.startswith("http"):
        bot.send_message(message.chat.id, "❌ لینک ارسالی معتبر نیست. مجدداً تلاش کنید.")
        return
    order_code = f"ST-{generate_random_code(6)}"
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO orders (order_code, user_id, post_link) VALUES (?, ?, ?)",
                   (order_code, message.from_user.id, post_link))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f"✅ سفارش شما با موفقیت ثبت شد!\n🔑 کد پیگیری: `{order_code}`", parse_mode="Markdown")
    admin_markup = types.InlineKeyboardMarkup()
    admin_markup.add(
        types.InlineKeyboardButton("✅ تایید", callback_data=f"approve_{order_code}"),
        types.InlineKeyboardButton("❌ رد سفارش", callback_data=f"reject_{order_code}")
    )
    bot.send_message(ADMIN_ID, f"📦 **سفارش جدید استارز**\n\nکد: `{order_code}`\nکاربر: `{message.from_user.id}`\nلینک: {post_link}",
                     parse_mode="Markdown", reply_markup=admin_markup)
    @bot.message_handler(func=lambda m: m.text == "🎁 قرعه‌کشی و ثبت کد")
def gift_and_draw_handler(message):
    msg = bot.send_message(
        message.chat.id,
        "📌 **بخش کدهای هدیه و قرعه‌کشی**\n\n"
        "اگر کدی از کانال یا ادمین دریافت کرده‌اید، آن را ارسال کنید:"
    )
    bot.register_next_step_handler(msg, process_code_redeem)

def process_code_redeem(message):
    code_input = message.text.strip()
    user_id = message.from_user.id
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
        bot.send_message(message.chat.id, "❌ کد هدیه وارد شده نامعتبر است.")
        conn.close()
        return
    code, reward_type, reward_value, capacity, used_count = code_data
    if used_count >= capacity:
        bot.send_message(message.chat.id, "❌ ظرفیت استفاده از این کد به پایان رسیده است.")
        conn.close()
        return
    if reward_type == "balance":
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (reward_value, user_id))
        msg_text = f"🎉 مبارکه! مبلغ {reward_value:,} تومان به حساب شما اضافه شد."
    else:
        cursor.execute("UPDATE users SET stars = stars + ? WHERE user_id=?", (reward_value, user_id))
        msg_text = f"🎉 مبارکه! تعداد {reward_value} استارز/گیفت به حساب شما اضافه شد."
    cursor.execute("UPDATE gift_codes SET used_count = used_count + 1 WHERE code=?", (code_input,))
    cursor.execute("INSERT INTO used_codes (user_id, code) VALUES (?, ?)", (user_id, code_input))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, msg_text)

@bot.message_handler(func=lambda m: m.text == "⚙️ پنل مدیریت" and m.from_user.id == ADMIN_ID)
def admin_panel_handler(message):
    bot.send_message(message.chat.id, "به پنل مدیریت خوش آمدید:", reply_markup=admin_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "admin_add_task" and call.from_user.id == ADMIN_ID)
def admin_add_task_start(call):
    msg = bot.send_message(call.message.chat.id, "اطلاعات مأموریت را به فرمت زیر وارد کنید:\n`عنوان مأموریت,آیدی یا عددی کانال`\nمثال:\n`عضویت در کانال اخبار,@MyChannel`", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_task_save)

def process_add_task_save(message):
    try:
        title, channel_id = message.text.split(",")
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tasks (title, channel_id) VALUES (?, ?)", (title.strip(), channel_id.strip()))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ مأموریت جدید با موفقیت اضافه شد.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطا در ثبت مأموریت: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "admin_create_code" and call.from_user.id == ADMIN_ID)
def admin_create_code_start(call):
    msg = bot.send_message(call.message.chat.id, "اطلاعات کد را به فرمت زیر بفرستید:\n`کد,نوع(balance/stars),مقدار,ظرفیت`\nمثال:\n`GIFT100,stars,5,10`", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_create_code_save)

def process_create_code_save(message):
    try:
        code, r_type, val, cap = message.text.split(",")
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO gift_codes (code, reward_type, reward_value, capacity) VALUES (?, ?, ?, ?)",
                       (code.strip(), r_type.strip(), int(val), int(cap)))
        conn.commit()
        conn.close()
        text_post = (
            f"🎁 **کد هدیه جدید!**\n\n"
            f"🔑 کد: `{code.strip()}`\n"
            f"👥 ظرفیت: {cap} نفر\n\n"
            f"📌 وارد ربات شوید و در بخش «قرعه‌کشی و ثبت کد» کد بالا را وارد کنید."
        )
        bot.send_message(message.chat.id, f"✅ کد ساخته شد:\n\n{text_post}", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطا در فرمت ورودی: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "admin_set_rate" and call.from_user.id == ADMIN_ID)
def admin_set_rate_start(call):
    msg = bot.send_message(call.message.chat.id, "نرخ جدید هر ۱۰ استارز را به تومان وارد کنید (مثلاً 40000):")
    bot.register_next_step_handler(msg, process_set_rate_save)

def process_set_rate_save(message):
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "❌ عدد معتبر وارد کنید.")
        return
    new_rate = message.text
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET value=? WHERE key='star_rate'", (new_rate,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f"✅ نرخ ارزش استارز با موفقیت به {int(new_rate):,} تومان تغییر یافت.")

@bot.callback_query_handler(func=lambda call: call.data.startswith(("approve_", "reject_")) and call.from_user.id == ADMIN_ID)
def handle_order_action(call):
    action, order_code = call.data.split("_")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM orders WHERE order_code=?", (order_code,))
    order = cursor.fetchone()
    if not order:
        bot.answer_callback_query(call.id, "سفارش پیدا نشد.")
        conn.close()
        return
    user_id = order[0]
    if action == "approve":
        cursor.execute("UPDATE orders SET status='تایید شده' WHERE order_code=?", (order_code,))
        bot.send_message(user_id, f"✅ سفارش استارز شما با کد پیگیری `{order_code}` انجام و تایید شد.", parse_mode="Markdown")
        bot.edit_message_text(f"✅ سفارش `{order_code}` تایید شد.", call.message.chat.id, call.message.message_id)
    else:
        msg = bot.send_message(call.message.chat.id, f"علت رد سفارش `{order_code}` را وارد کنید:")
        bot.register_next_step_handler(msg, lambda m: finalize_reject(m, order_code, user_id))
    conn.commit()
    conn.close()

def finalize_reject(message, order_code, user_id):
    reason = message.text
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status='رد شده', reason=? WHERE order_code=?", (reason, order_code))
    conn.commit()
    conn.close()
    bot.send_message(user_id, f"❌ سفارش شما با کد `{order_code}` رد شد.\nعلت: {reason}", parse_mode="Markdown")
    bot.send_message(ADMIN_ID, f"سفارش `{order_code}` رد شد و به کاربر اطلاع داده شد.")

if __name__ == "__main__":
    print("Bot started successfully...")
    bot.infinity_polling(skip_pending=True)
        
