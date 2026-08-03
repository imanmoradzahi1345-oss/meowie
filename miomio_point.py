import telebot
from telebot import types
import sqlite3
import time
import json
import random
import threading

# ==========================================
# تنظیمات اصلی ربات (Configuration)
# ==========================================
TOKEN = "8971798729:AAGY8Hw8osbpHdglddpckGSnDUgIR8bywfw"
ADMIN_ID = 8918154552

bot = telebot.TeleBot(TOKEN)

# ==========================================
# مدیریت پایگاه داده (Database Management)
# ==========================================
DB_NAME = "cat_bot.db"

def get_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # جدول اطلاعات کاربران
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            cat_name TEXT DEFAULT 'پیشی',
            pocket_points INTEGER DEFAULT 100,
            meow_count INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            last_meow_time REAL DEFAULT 0
        )
    ''')
    
    # جدول مدیریت بازی‌های فعال کازینو
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS active_games (
            game_id TEXT PRIMARY KEY,
            chat_id INTEGER,
            message_id INTEGER,
            creator_id INTEGER,
            game_type TEXT,
            target_players INTEGER,
            bet_amount INTEGER,
            players_json TEXT,
            predictions_json TEXT,
            status TEXT,
            created_at REAL
        )
    ''')
    
    conn.commit()
    conn.close()

# ساخت دیتابیس در هنگام اجرای اولیه
init_db()

# ==========================================
# توابع کمکی کاربر و دیتابیس (Helper Functions)
# ==========================================
def get_user(user_id, first_name="کاربر"):
    """دریافت اطلاعات کاربر یا ثبت نام کاربر جدید در صورت عدم وجود"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute('''
            INSERT INTO users (user_id, first_name, cat_name, pocket_points, meow_count, level, last_meow_time)
            VALUES (?, ?, 'پیشی', 100, 0, 1, 0)
        ''', (user_id, first_name))
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        
    conn.close()
    return user

def calculate_level(meow_count):
    """محاسبه لول کاربر بر اساس تعداد میوها (هر ۱۰ میو ۱ لول)"""
    return (meow_count // 10) + 1

def check_meow_cooldown(user_id):
    """بررسی کولدون ۳ دقیقه‌ای برای میو/مع"""
    user = get_user(user_id)
    last_time = user['last_meow_time']
    current_time = time.time()
    cooldown = 180  # 3 دقیقه = 180 ثانیه
    
    remaining = cooldown - (current_time - last_time)
    if remaining <= 0:
        return True, 0
    return False, int(remaining)

def register_meow(user_id):
    """ثبت میو جدید، افزودن میوپوینت خودکار سیستم و به‌روزرسانی لول"""
    user = get_user(user_id)
    new_meow_count = user['meow_count'] + 1
    new_level = calculate_level(new_meow_count)
    earned_points = 15  # میوپوینت اعطا شده توسط ربات (نه از جیب کسی)
    new_pocket = user['pocket_points'] + earned_points
    current_time = time.time()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET meow_count = ?, level = ?, pocket_points = ?, last_meow_time = ?
        WHERE user_id = ?
    ''', (new_meow_count, new_level, new_pocket, current_time, user_id))
    conn.commit()
    conn.close()
    
    return new_meow_count, new_level, earned_points
    # ==========================================
# تنظیمات محصولات کارخانه (۱۰ محصول متناسب با لول)
# ==========================================
FACTORY_PRODUCTS = {
    "1": {"name": "پشمک", "min_level": 1, "cost": 2, "base_sell": 4},
    "2": {"name": "شکلات", "min_level": 1, "cost": 5, "base_sell": 8},
    "3": {"name": "آبنبات", "min_level": 2, "cost": 10, "base_sell": 16},
    "4": {"name": "کیک", "min_level": 3, "cost": 25, "base_sell": 40},
    "5": {"name": "بستنی", "min_level": 4, "cost": 50, "base_sell": 85},
    "6": {"name": "عروسک", "min_level": 5, "cost": 100, "base_sell": 170},
    "7": {"name": "لباس گربه", "min_level": 6, "cost": 250, "base_sell": 420},
    "8": {"name": "ماشین شارژی", "min_level": 7, "cost": 500, "base_sell": 850},
    "9": {"name": "جت شخصی", "min_level": 8, "cost": 1000, "base_sell": 1800},
    "10": {"name": "هواپیما", "min_level": 10, "cost": 5000, "base_sell": 9500}
}

# دیکشنری نگهداری وضعیت موقت کاربران
user_states = {}

# ==========================================
# ۱. سیستم میو / مع (با ثبت خودکار و سیستم کولدون)
# ==========================================
@bot.message_handler(func=lambda m: m.text and m.text.strip().lower() in ['میو', 'مع'])
def handle_meow(message):
    user_id = message.from_user.id
    can_meow, remaining = check_meow_cooldown(user_id)
    
    if not can_meow:
        mins, secs = divmod(remaining, 60)
        bot.reply_to(message, f"⏳ شما تازه میو کردید! برای میو بعدی باید {mins} دقیقه و {secs} ثانیه صبر کنید.")
        return

    meow_count, level, points = register_meow(user_id)
    bot.reply_to(message, f"🐱 **میو!** شما یک میو کردید.\n➕ **+{points} میوپوینت** به جیب شما اضافه شد (از سیستم)!\n📊 مجموع میوها: {meow_count} | لول شما: {level}", parse_mode="Markdown")

# ==========================================
# ۲. مشاهده پروفایل (خود یا کاربر ریپلی شده)
# ==========================================
@bot.message_handler(func=lambda m: m.text and m.text.strip().lower() in ['پروفایل', 'میوهاش'])
def handle_profile(message):
    target_id = message.from_user.id
    target_name = message.from_user.first_name
    
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        target_name = message.reply_to_message.from_user.first_name

    user = get_user(target_id, target_name)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'factory_level' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN factory_level INTEGER DEFAULT 1")
        cursor.execute("ALTER TABLE users ADD COLUMN factory_prod TEXT DEFAULT ''")
        conn.commit()
        
    cursor.execute("SELECT factory_level FROM users WHERE user_id = ?", (target_id,))
    f_row = cursor.fetchone()
    factory_lvl = f_row['factory_level'] if f_row and f_row['factory_level'] else 1
    conn.close()

    profile_text = (
        f"👤 **پروفایل میویی کاربر:** {user['first_name']}\n"
        f"🐱 **اسم گربه:** {user['cat_name']}\n"
        f"💰 **میوپوینت موجود در جیب:** {user['pocket_points']:,} میوپوینت\n"
        f"🐾 **تعداد دفعات میو/مع:** {user['meow_count']}\n"
        f"⭐ **لول کاربر:** {user['level']}\n"
        f"🏭 **سطح کارخانه:** {factory_lvl}"
    )
    bot.reply_to(message, profile_text, parse_mode="Markdown")

# ==========================================
# ۳. پنل اختصاصی پیشی / گربه / برفک
# ==========================================
@bot.message_handler(func=lambda m: m.text and any(k in m.text.strip().lower() for k in ['پیشی', 'برفک', 'گربه']))
def handle_cat_panel(message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    
    markup = types.InlineKeyboardMarkup()
    btn_rename = types.InlineKeyboardButton("✏️ تغییر اسم گربه", callback_data="cat_rename")
    btn_info = types.InlineKeyboardButton("ℹ️ وضعیت پیشی", callback_data="cat_info")
    markup.add(btn_rename, btn_info)
    
    bot.reply_to(
        message, 
        f"😺 سلام! من **{user['cat_name']}** هستم. چه کاری می‌تونی برام انجام بدی؟",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# ==========================================
# ۴. سیستم کامل کارخانه (Factory System)
# ==========================================
@bot.message_handler(func=lambda m: m.text and m.text.strip().lower() == 'کارخونه')
def handle_factory(message):
    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.first_name)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'factory_level' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN factory_level INTEGER DEFAULT 1")
        cursor.execute("ALTER TABLE users ADD COLUMN factory_prod TEXT DEFAULT ''")
        conn.commit()

    cursor.execute("SELECT factory_level, factory_prod FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    factory_lvl = row['factory_level'] if row and row['factory_level'] else 1
    factory_prod_raw = row['factory_prod'] if row and row['factory_prod'] else ""
    conn.close()

    # اگر کارخانه در حال تولید باشد
    if factory_prod_raw:
        prod_data = json.loads(factory_prod_raw)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ لغو کردن تولید (بازگشت کامل وجه)", callback_data="factory_cancel"))
        
        prod_text = (
            f"🏭 **پنل کارخانه (در حال تولید)**\n\n"
            f"📦 **محصول در حال ساخت:** {prod_data['name']}\n"
            f"🔢 **تعداد:** {prod_data['amount']:,}\n"
            f"💰 **سرمایه درگیر:** {prod_data['total_cost']:,} میوپوینت\n"
            f"⏳ **وضعیت:** خط تولید فعال است...\n\n"
            f"اگر قصد لغو سفارش را دارید، با زدن دکمه زیر ۱۰۰٪ مبلغ اولیه به جیب شما برمی‌گردد."
        )
        bot.send_message(message.chat.id, prod_text, reply_markup=markup, parse_mode="Markdown")
        return

    # پنل اصلی کارخانه
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_upgrade = types.InlineKeyboardButton("⬆️ ارتقا کارخانه (افزایش انبار و سرعت)", callback_data="factory_upgrade")
    btn_start = types.InlineKeyboardButton("🏭 شروع تولید محصول", callback_data="factory_start")
    btn_list = types.InlineKeyboardButton("📜 لیست محصولات کارخانه", callback_data="factory_list")
    markup.add(btn_upgrade, btn_start, btn_list)

    capacity = factory_lvl * 50000
    text = (
        f"🏭 **پنل مدیریت کارخانه**\n\n"
        f"⭐ **سطح کارخانه:** {factory_lvl}\n"
        f"📦 **ظرفیت انبار:** {capacity:,} واحد\n"
        f"💰 **میوپوینت موجود در جیب:** {user['pocket_points']:,}\n\n"
        f"یکی از گزینه‌های زیر را انتخاب کنید:"
    )
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

# ------------------------------------------
# دکمه‌های شیشه‌ای کارخانه و پیشی
# ------------------------------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith(('cat_', 'factory_')))
def handle_cat_factory_callbacks(call):
    user_id = call.from_user.id
    
    if call.data == "cat_rename":
        user_states[user_id] = "waiting_for_cat_name"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "✏️ لطفاً اسم جدید گربه خود را ارسال کنید:")
        
    elif call.data == "cat_info":
        user = get_user(user_id)
        bot.answer_callback_query(call.id, f"اسم گربه: {user['cat_name']} | لول: {user['level']}", show_alert=True)

    elif call.data == "factory_list":
        bot.answer_callback_query(call.id)
        text = "📜 **لیست ۱۰ محصول کارخانه:**\n\n"
        for key, p in FACTORY_PRODUCTS.items():
            text += f"{key}. **{p['name']}** | سطح لازم: {p['min_level']} | قیمت خرید هر عدد: {p['cost']} میوپوینت\n"
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

    elif call.data == "factory_upgrade":
        user = get_user(user_id)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT factory_level FROM users WHERE user_id = ?", (user_id,))
        lvl = cursor.fetchone()['factory_level'] or 1
        
        upgrade_cost = lvl * 10000
        if user['pocket_points'] < upgrade_cost:
            bot.answer_callback_query(call.id, f"❌ میوپوینت کافی ندارید! هزینه ارتقا: {upgrade_cost:,}", show_alert=True)
            conn.close()
            return

        new_lvl = lvl + 1
        new_pocket = user['pocket_points'] - upgrade_cost
        cursor.execute("UPDATE users SET factory_level = ?, pocket_points = ? WHERE user_id = ?", (new_lvl, new_pocket, user_id))
        conn.commit()
        conn.close()
        
        bot.answer_callback_query(call.id, f"🎉 کارخانه به سطح {new_lvl} ارتقا یافت!", show_alert=True)
        bot.edit_message_text(f"✅ **کارخانه شما با موفقیت به سطح {new_lvl} ارتقا یافت!**", call.message.chat.id, call.message.message_id)

    elif call.data == "factory_cancel":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT factory_prod, pocket_points FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if row and row['factory_prod']:
            prod_data = json.loads(row['factory_prod'])
            refund = prod_data['total_cost']
            new_pocket = row['pocket_points'] + refund
            
            cursor.execute("UPDATE users SET factory_prod = '', pocket_points = ? WHERE user_id = ?", (new_pocket, user_id))
            conn.commit()
            bot.answer_callback_query(call.id, "✅ تولید لول شد و مبلغ اولیه به جیب شما بازگشت.", show_alert=True)
            bot.edit_message_text(f"❌ **تولید لغو شد.** مبلغ {refund:,} میوپوینت به جیب شما بازگشت.", call.message.chat.id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "هیچ خط تولید فعالی یافت نشد.", show_alert=True)
        conn.close()

    elif call.data == "factory_start":
        bot.answer_callback_query(call.id)
        user_states[user_id] = "waiting_for_factory_order"
        msg = "🏭 **جهت شروع تولید، کد محصول و تعداد را مانند نمونه زیر بفرستید:**\n\n"
        msg += "`تولید 2 10000`\n\n"
        msg += "(عدد اول کد محصول مثلاً 2 برای شکلات و عدد دوم تعداد ساخت است)"
        bot.send_message(call.message.chat.id, msg, parse_mode="Markdown")

# ------------------------------------------
# پردازش پیام‌های ورود اطلاعات (تغییر اسم و ثبت سفارش کارخانه)
# ------------------------------------------
@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) in ["waiting_for_cat_name", "waiting_for_factory_order"])
def handle_state_inputs(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    
    if state == "waiting_for_cat_name":
        new_name = message.text.strip()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET cat_name = ? WHERE user_id = ?", (new_name, user_id))
        conn.commit()
        conn.close()
        
        del user_states[user_id]
        bot.reply_to(message, f"✅ اسم گربه شما با موفقیت به **{new_name}** تغییر یافت!", parse_mode="Markdown")

    elif state == "waiting_for_factory_order":
        text = message.text.strip().split()
        if len(text) < 3 or text[0] != "تولید":
            bot.reply_to(message, "❌ فرمت نادرست است! مثال صحیح: `تولید 2 10000`", parse_mode="Markdown")
            return
            
        prod_id = text[1]
        try:
            amount = int(text[2])
        except ValueError:
            bot.reply_to(message, "❌ تعداد باید عدد باشد!")
            return

        if prod_id not in FACTORY_PRODUCTS:
            bot.reply_to(message, "❌ کد محصول یافت نشد!")
            return

        product = FACTORY_PRODUCTS[prod_id]
        user = get_user(user_id)
        
        # بررسی سطح کارخانه
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT factory_level FROM users WHERE user_id = ?", (user_id,))
        f_lvl = cursor.fetchone()['factory_level'] or 1
        
        if f_lvl < product['min_level']:
            bot.reply_to(message, f"❌ برای تولید {product['name']} سطح کارخانه شما باید حداقل {product['min_level']} باشد.")
            conn.close()
            return

        total_cost = amount * product['cost']
        if user['pocket_points'] < total_cost:
            bot.reply_to(message, f"❌ میوپوینت کافی ندارید! هزینه کل: {total_cost:,} میوپوینت (موجودی جیب: {user['pocket_points']:,})")
            conn.close()
            return

        # کسر هزینه و ثبت سفارش فعال
        new_pocket = user['pocket_points'] - total_cost
        prod_info = json.dumps({
            "id": prod_id,
            "name": product['name'],
            "amount": amount,
            "total_cost": total_cost,
            "time": time.time()
        })
        
        cursor.execute("UPDATE users SET pocket_points = ?, factory_prod = ? WHERE user_id = ?", (new_pocket, prod_info, user_id))
        conn.commit()
        conn.close()
        
        del user_states[user_id]
        bot.reply_to(message, f"✅ **خط تولید فعال شد!**\n\n📦 محصول: {product['name']}\n🔢 تعداد: {amount:,}\n💰 کل مبلغ پرداختی: {total_cost:,} میوپوینت\n\nجهت مشاهده یا لغو، کلمه `کارخونه` را ارسال کنید.", parse_mode="Markdown")
    # ==========================================
# توابع کمکی تبدیل اعداد و مبالغ (K / کا / میلیون)
# ==========================================
def parse_fa_num(text):
    """تبدیل اعداد فارسی و عربی به انگلیسی"""
    fa_digits = '۰۱۲۳۴۵۶۷۸۹'
    en_digits = '0123456789'
    trans = str.maketrans(fa_digits, en_digits)
    return text.translate(trans)

def parse_amount(text):
    """پردازش دقیق فرمت‌های متنی مثل 50k, ۵کا, 500k"""
    if not text:
        return None
    text = parse_fa_num(text.strip().lower())
    multiplier = 1
    if text.endswith('کا'):
        multiplier = 1000
        text = text[:-2].strip()
    elif text.endswith('ka'):
        multiplier = 1000
        text = text[:-2].strip()
    elif text.endswith('k'):
        multiplier = 1000
        text = text[:-1].strip()
    elif text.endswith('m') or text.endswith('ام'):
        multiplier = 1000000
        text = text[:-1].strip() if text.endswith('m') else text[:-2].strip()
    
    try:
        val = float(text)
        return int(val * multiplier)
    except ValueError:
        return None

# ==========================================
# ۱. سیستم انتقال میویی (Transfer System)
# ==========================================
@bot.message_handler(func=lambda m: m.text and 'انتقال میویی' in m.text)
def handle_meow_transfer(message):
    if not message.reply_to_message:
        bot.reply_to(message, "❌ برای انتقال میویی باید روی پیام فرد مورد نظر ریپلی بزنید!")
        return

    sender_id = message.from_user.id
    target_id = message.reply_to_message.from_user.id

    if sender_id == target_id:
        bot.reply_to(message, "❌ شما نمی‌توانید به خودتان میوپوینت منتقل کنید!")
        return

    # استخراج مبلغ از متن پیام
    parts = message.text.strip().split()
    if len(parts) < 3:
        bot.reply_to(message, "❌ فرمت دستور نادرست است!\nنمونه: `انتقال میویی 50k` یا `انتقال میویی ۵کا`", parse_mode="Markdown")
        return

    raw_amount = parts[-1]
    amount = parse_amount(raw_amount)

    if not amount or amount <= 0:
        bot.reply_to(message, "❌ مبلغ وارد شده معتبر نیست!")
        return

    # سقف انتقال درجا ۵۰۰کا
    MAX_TRANSFER = 500000
    if amount > MAX_TRANSFER:
        bot.reply_to(message, f"❌ سقف هر انتقال میویی درجا ۵۰۰,۰۰۰ ({MAX_TRANSFER:,}) میوپوینت است!")
        return

    sender = get_user(sender_id, message.from_user.first_name)
    if sender['pocket_points'] < amount:
        bot.reply_to(message, f"❌ میوپوینت کافی در جیب ندارید! موجودی جیب شما: {sender['pocket_points']:,}")
        return

    target_name = message.reply_to_message.from_user.first_name
    get_user(target_id, target_name) # اطمینان از ثبت کاربر مقصد

    markup = types.InlineKeyboardMarkup()
    btn_yes = types.InlineKeyboardButton("✅ تایید انتقال", callback_data=f"tr_confirm:{target_id}:{amount}")
    btn_no = types.InlineKeyboardButton("❌ خیر (لغو)", callback_data="tr_cancel")
    markup.add(btn_yes, btn_no)

    text = (
        f"❓ **تایید انتقال میویی**\n\n"
        f"آیا مطمئن هستید که می‌خواهید مبلغ **{amount:,}** میوپوینت از جیب خود به **{target_name}** منتقل کنید؟"
    )
    bot.reply_to(message, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('tr_confirm:', 'tr_cancel')))
def handle_transfer_callbacks(call):
    if call.data == "tr_cancel":
        bot.answer_callback_query(call.id, "انتقال لغو شد.")
        bot.edit_message_text("❌ **انتقال میویی لغو شد.**", call.message.chat.id, call.message.message_id)
        return

    _, target_id, amount_str = call.data.split(':')
    target_id = int(target_id)
    amount = int(amount_str)
    sender_id = call.from_user.id

    sender = get_user(sender_id)
    if sender['pocket_points'] < amount:
        bot.answer_callback_query(call.id, "❌ موجودی جیب شما کافی نیست!", show_alert=True)
        return

    conn = get_db()
    cursor = conn.cursor()
    
    # کسر از جیب فرستنده و اضافه به جیب گیرنده
    cursor.execute("UPDATE users SET pocket_points = pocket_points - ? WHERE user_id = ?", (amount, sender_id))
    cursor.execute("UPDATE users SET pocket_points = pocket_points + ? WHERE user_id = ?", (amount, target_id))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, "✅ انتقال با موفقیت انجام شد!")
    bot.edit_message_text(f"✅ **انتقال با موفقیت انجام شد!**\n💰 مبلغ **{amount:,}** میوپوینت منتقل گردید.", call.message.chat.id, call.message.message_id)

# ==========================================
# ۲. سیستم کامل بانک (Bank System)
# ==========================================
def generate_account_number(user_id):
    """تولید شماره حساب بانکی ۱۶ رقمی یکتا"""
    random.seed(user_id + 777)
    acc = "6037" + "".join([str(random.randint(0, 9)) for _ in range(12)])
    random.seed()
    return acc

@bot.message_handler(func=lambda m: m.text and m.text.strip().lower() == 'بانک')
def handle_bank(message):
    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.first_name)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users)")
    cols = [c[1] for c in cursor.fetchall()]
    if 'bank_points' not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN bank_points INTEGER DEFAULT 0")
    if 'account_number' not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN account_number TEXT DEFAULT ''")
    conn.commit()

    cursor.execute("SELECT bank_points, account_number FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    bank_pts = row['bank_points'] if row and row['bank_points'] else 0
    acc_num = row['account_number'] if row and row['account_number'] else generate_account_number(user_id)
    
    if not row or not row['account_number']:
        cursor.execute("UPDATE users SET account_number = ? WHERE user_id = ?", (acc_num, user_id))
        conn.commit()
    conn.close()

    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_dep = types.InlineKeyboardButton("📥 واریز به حساب بانکی", callback_data="bank_dep")
    btn_wth = types.InlineKeyboardButton("📤 برداشت از حساب بانکی", callback_data="bank_wth")
    btn_trf = types.InlineKeyboardButton("💳 انتقال بین بانکی", callback_data="bank_trf")
    markup.add(btn_dep, btn_wth, btn_trf)

    bank_card = (
        f"🏦 **سیستم بانک میویی**\n\n"
        f"👤 **صاحب حساب:** {user['first_name']}\n"
        f"💳 **شماره حساب:** `{acc_num}`\n"
        f"💵 **موجودی جیب:** {user['pocket_points']:,} میوپوینت\n"
        f"🏦 **موجودی بانک:** {bank_pts:,} میوپوینت\n\n"
        f"لطفاً عملیات مورد نظر خود را انتخاب کنید:"
    )
    bot.send_message(message.chat.id, bank_card, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('bank_'))
def handle_bank_callbacks(call):
    user_id = call.from_user.id
    
    if call.data == "bank_dep":
        user_states[user_id] = "waiting_bank_dep"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📥 **مبلغ واریزی به بانک را بفرستید:**\n(مثال: `50k` یا `20000`)", parse_mode="Markdown")

    elif call.data == "bank_wth":
        user_states[user_id] = "waiting_bank_wth"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📤 **مبلغ برداشتی از بانک را بفرستید:**\n(مثال: `50k` یا `20000`)", parse_mode="Markdown")

    elif call.data == "bank_trf":
        user_states[user_id] = "waiting_bank_trf"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "💳 **انتقال بین بانکی:**\nلطفاً شماره حساب مقصد و مبلغ را با فاصله ارسال کنید:\nمثال: `6037123456789012 50k`", parse_mode="Markdown")

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) in ["waiting_bank_dep", "waiting_bank_wth", "waiting_bank_trf"])
def handle_bank_inputs(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    user = get_user(user_id, message.from_user.first_name)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT bank_points, account_number FROM users WHERE user_id = ?", (user_id,))
    u_row = cursor.fetchone()
    bank_pts = u_row['bank_points'] if u_row and u_row['bank_points'] else 0

    if state == "waiting_bank_dep":
        amt = parse_amount(message.text)
        if not amt or amt <= 0:
            bot.reply_to(message, "❌ مبلغ نامعتبر است!")
            conn.close()
            return
        if user['pocket_points'] < amt:
            bot.reply_to(message, f"❌ موجودی جیب شما کافی نیست! ({user['pocket_points']:,})")
            conn.close()
            return

        new_pocket = user['pocket_points'] - amt
        new_bank = bank_pts + amt
        cursor.execute("UPDATE users SET pocket_points = ?, bank_points = ? WHERE user_id = ?", (new_pocket, new_bank, user_id))
        conn.commit()
        del user_states[user_id]
        bot.reply_to(message, f"✅ **مبلغ {amt:,} میوپوینت با موفقیت به بانک واریز شد.**", parse_mode="Markdown")

    elif state == "waiting_bank_wth":
        amt = parse_amount(message.text)
        if not amt or amt <= 0:
            bot.reply_to(message, "❌ مبلغ نامعتبر است!")
            conn.close()
            return
        if bank_pts < amt:
            bot.reply_to(message, f"❌ موجودی بانک شما کافی نیست! ({bank_pts:,})")
            conn.close()
            return

        new_pocket = user['pocket_points'] + amt
        new_bank = bank_pts - amt
        cursor.execute("UPDATE users SET pocket_points = ?, bank_points = ? WHERE user_id = ?", (new_pocket, new_bank, user_id))
        conn.commit()
        del user_states[user_id]
        bot.reply_to(message, f"✅ **مبلغ {amt:,} میوپوینت با موفقیت از بانک برداشت شد.**", parse_mode="Markdown")

    elif state == "waiting_bank_trf":
        parts = message.text.strip().split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ فرمت ورودی اشتباه است! مثال: `6037123456789012 50k`", parse_mode="Markdown")
            conn.close()
            return

        dest_acc = parse_fa_num(parts[0])
        amt = parse_amount(parts[1])

        if not amt or amt <= 0:
            bot.reply_to(message, "❌ مبلغ وارد شده معتبر نیست!")
            conn.close()
            return

        if bank_pts < amt:
            bot.reply_to(message, f"❌ موجودی بانک شما برای این انتقال کافی نیست! ({bank_pts:,})")
            conn.close()
            return

        cursor.execute("SELECT user_id, first_name FROM users WHERE account_number = ?", (dest_acc,))
        dest_user = cursor.fetchone()

        if not dest_user:
            bot.reply_to(message, "❌ شماره حساب مقصد یافت نشد!")
            conn.close()
            return

        if dest_user['user_id'] == user_id:
            bot.reply_to(message, "❌ شما نمی‌توانید به حساب خودتان کارت به کارت کنید!")
            conn.close()
            return

        # کسر از بانک فرستنده و واریز به بانک گیرنده
        cursor.execute("UPDATE users SET bank_points = bank_points - ? WHERE user_id = ?", (amt, user_id))
        cursor.execute("UPDATE users SET bank_points = bank_points + ? WHERE user_id = ?", (amt, dest_user['user_id']))
        conn.commit()

        del user_states[user_id]
        bot.reply_to(message, f"✅ **انتقال بین بانکی انجام شد!**\n💳 مبلغ **{amt:,}** میوپوینت به حساب **{dest_user['first_name']}** واریز گردید.", parse_mode="Markdown")

    conn.close()
        # ==========================================
# سیستم جامع کازینو (Casino Core System)
# ==========================================

# نگهداری حالت موقت ایجاد بازی برای هر کاربر
casino_temp_states = {}

# ------------------------------------------
# ۱. دستور اصلی ورود به کازینو
# ------------------------------------------
@bot.message_handler(func=lambda m: m.text and m.text.strip().lower() == 'کازینو')
def handle_casino_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_slot = types.InlineKeyboardButton("🎰 اسلات (۱ تا ۳ نفره)", callback_data="casino_select:slot")
    btn_dice = types.InlineKeyboardButton("🎲 تاس (۱ تا ۳ نفره)", callback_data="casino_select:dice")
    btn_bowling = types.InlineKeyboardButton("🎳 بولینگ (فقط ۲ یا ۳ نفره)", callback_data="casino_select:bowling")
    markup.add(btn_slot, btn_dice, btn_bowling)

    text = (
        f"🎰 **به کازینو میویی خوش آمدید!** 🎲\n\n"
        f"لطفاً یکی از بازی‌های زیر را برای شروع انتخاب کنید:"
    )
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

# ------------------------------------------
# ۲. انتخاب بازی و انتخاب تعداد نفرات
# ------------------------------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith('casino_select:'))
def handle_casino_select_game(call):
    game_type = call.data.split(':')[1]
    user_id = call.from_user.id
    
    casino_temp_states[user_id] = {'game_type': game_type}

    markup = types.InlineKeyboardMarkup()
    if game_type == 'bowling':
        # بولینگ تک‌نفره ندارد
        btn2 = types.InlineKeyboardButton("👥 ۲ نفره", callback_data="casino_players:2")
        btn3 = types.InlineKeyboardButton("👥👥 ۳ نفره", callback_data="casino_players:3")
        markup.add(btn2, btn3)
    else:
        btn1 = types.InlineKeyboardButton("👤 ۱ نفره", callback_data="casino_players:1")
        btn2 = types.InlineKeyboardButton("👥 ۲ نفره", callback_data="casino_players:2")
        btn3 = types.InlineKeyboardButton("👥👥 ۳ نفره", callback_data="casino_players:3")
        markup.add(btn1, btn2, btn3)

    game_titles = {'slot': '🎰 اسلات', 'dice': '🎲 تاس', 'bowling': '🎳 بولینگ'}
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        f"🎮 بازی انتخاب شده: **{game_titles[game_type]}**\n\nلطفاً تعداد نفرات بازی را انتخاب کنید:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown"
    )

# ------------------------------------------
# ۳. انتخاب تعداد نفرات و تعیین مبلغ شرط
# ------------------------------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith('casino_players:'))
def handle_casino_select_players(call):
    target_players = int(call.data.split(':')[1])
    user_id = call.from_user.id
    
    if user_id not in casino_temp_states:
        casino_temp_states[user_id] = {'game_type': 'dice'}
        
    casino_temp_states[user_id]['target_players'] = target_players

    markup = types.InlineKeyboardMarkup()
    btn_bet = types.InlineKeyboardButton("💰 تعیین مبلغ شرط", callback_data="casino_set_bet")
    markup.add(btn_bet)

    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        f"👥 تعداد نفرات انتخاب شده: **{target_players} نفره**\n\n"
        f"جهت وارد کردن مبلغ شرط، روی دکمه زیر کلیک کنید:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "casino_set_bet")
def handle_casino_set_bet_btn(call):
    user_id = call.from_user.id
    user_states[user_id] = "waiting_casino_bet_input"
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        "💵 **لطفاً مبلغ شرط را وارد کنید:**\n(مثال: `10k` یا `5000` یا `۵کا`)",
        parse_mode="Markdown"
    )

# ------------------------------------------
# ۴. دریافت مبلغ شرط و ادامه مسیر (زوج/فرد برای تاس ۱نفره یا ایجاد لابی)
# ------------------------------------------
@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "waiting_casino_bet_input")
def handle_casino_bet_input(message):
    user_id = message.from_user.id
    bet = parse_amount(message.text)
    user = get_user(user_id, message.from_user.first_name)

    if not bet or bet <= 0:
        bot.reply_to(message, "❌ مبلغ شرط وارد شده معتبر نیست!")
        return

    if user['pocket_points'] < bet:
        bot.reply_to(message, f"❌ میوپوینت کافی در جیب ندارید! (موجودی: {user['pocket_points']:,})")
        return

    del user_states[user_id]
    state_info = casino_temp_states.get(user_id, {})
    game_type = state_info.get('game_type', 'dice')
    target_players = state_info.get('target_players', 1)

    if game_type == 'dice' and target_players == 1:
        # برای تاس ۱ نفره: انتخاب زوج یا فرد
        markup = types.InlineKeyboardMarkup()
        btn_even = types.InlineKeyboardButton("🔴 زوج", callback_data=f"dice_single_pred:even:{bet}")
        btn_odd = types.InlineKeyboardButton("🔵 فرد", callback_data=f"dice_single_pred:odd:{bet}")
        markup.add(btn_even, btn_odd)

        bot.reply_to(
            message,
            f"🎲 **تاس تک‌نفره** (مبلغ شرط: {bet:,} میوپوینت)\n\n"
            f"لطفاً پیش‌بینی کنید نتیجه تاس **زوج** خواهد بود یا **فرد**؟",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    else:
        # ایجاد اتاق بازی (اسلات تک‌نفره/چندنفره یا تاس/بولینگ چندنفره)
        create_casino_room(message, game_type, target_players, bet)

# ------------------------------------------
# ۵. پیش‌بینی زوج/فرد در تاس تک‌نفره
# ------------------------------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith('dice_single_pred:'))
def handle_dice_single_pred(call):
    _, pred, bet_str = call.data.split(':')
    bet = int(bet_str)
    user_id = call.from_user.id

    user = get_user(user_id)
    if user['pocket_points'] < bet:
        bot.answer_callback_query(call.id, "❌ موجودی کافی نیست!", show_alert=True)
        return

    # ثبت لابی تک‌نفره تاس
    game_id = f"game_{int(time.time())}_{user_id}"
    players = {str(user_id): {'name': call.from_user.first_name, 'score': None, 'pred': pred}}
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO active_games (game_id, chat_id, message_id, creator_id, game_type, target_players, bet_amount, players_json, predictions_json, status, created_at)
        VALUES (?, ?, ?, ?, 'dice_single', 1, ?, ?, '', 'waiting', ?)
    ''', (game_id, call.message.chat.id, call.message.message_id, user_id, bet, json.dumps(players), time.time()))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id)
    pred_text = "🔴 زوج" if pred == "even" else "🔵 فرد"
    bot.edit_message_text(
        f"🎲 **بازی تاس ۱ نفره**\n"
        f"💵 مبلغ شرط: {bet:,} میوپوینت\n"
        f"🎯 پیش‌بینی شما: {pred_text}\n\n"
        f"⚠️ **لطفاً دقیقاً در جواب (ریپلی) همین پیام ایموجی 🎲 را بفرستید!**",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )

# ------------------------------------------
# ۶. ساخت لابی چندنفره یا اسلات
# ------------------------------------------
def create_casino_room(message, game_type, target_players, bet):
    user_id = message.from_user.id
    game_id = f"game_{int(time.time())}_{user_id}"
    
    players = {str(user_id): {'name': message.from_user.first_name, 'score': None}}

    conn = get_db()
    cursor = conn.cursor()

    if target_players == 1 and game_type == 'slot':
        # اسلات ۱ نفره
        cursor.execute('''
            INSERT INTO active_games (game_id, chat_id, message_id, creator_id, game_type, target_players, bet_amount, players_json, status, created_at)
            VALUES (?, ?, ?, ?, 'slot_single', 1, ?, ?, 'waiting', ?)
        ''', (game_id, message.chat.id, 0, user_id, bet, json.dumps(players), time.time()))
        conn.commit()
        conn.close()

        sent_msg = bot.send_message(
            message.chat.id,
            f"🎰 **بازی اسلات ۱ نفره**\n"
            f"💵 مبلغ شرط: {bet:,} میوپوینت\n\n"
            f"⚠️ **لطفاً دقیقاً در جواب (ریپلی) همین پیام ایموجی 🎰 را بفرستید!**",
            parse_mode="Markdown"
        )
        
        # ثبت message_id دقیق جهت بررسی ریپلی
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE active_games SET message_id = ? WHERE game_id = ?", (sent_msg.message_id, game_id))
        conn.commit()
        conn.close()
        return

    # لابی‌های چندنفره (۲ یا ۳ نفره)
    markup = types.InlineKeyboardMarkup()
    btn_join = types.InlineKeyboardButton("🎮 ورود به بازی", callback_data=f"casino_join:{game_id}")
    markup.add(btn_join)

    emoji_map = {'slot': '🎰', 'dice': '🎲', 'bowling': '🎳'}
    sent_msg = bot.send_message(
        message.chat.id,
        f"🎮 **لابی جدید بازی {emoji_map.get(game_type, '')}**\n\n"
        f"👤 سازنده: {message.from_user.first_name}\n"
        f"👥 ظرفیت: ۱ از {target_players} نفر\n"
        f"💵 مبلغ شرط: {bet:,} میوپوینت\n\n"
        f"جهت شرکت در بازی دکمه زیر را لمس کنید:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

    cursor.execute('''
        INSERT INTO active_games (game_id, chat_id, message_id, creator_id, game_type, target_players, bet_amount, players_json, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'lobby', ?)
    ''', (game_id, message.chat.id, sent_msg.message_id, user_id, game_type, target_players, bet, json.dumps(players), time.time()))
    conn.commit()
    conn.close()

# ------------------------------------------
# ۷. پیوستن سایر بازیکنان به لابی چندنفره
# ------------------------------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith('casino_join:'))
def handle_casino_join(call):
    game_id = call.data.split(':')[1]
    user_id = call.from_user.id
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM active_games WHERE game_id = ?", (game_id,))
    game = cursor.fetchone()

    if not game or game['status'] != 'lobby':
        bot.answer_callback_query(call.id, "❌ این بازی فعال نیست یا پر شده است!", show_alert=True)
        conn.close()
        return

    players = json.loads(game['players_json'])

    if str(user_id) in players:
        bot.answer_callback_query(call.id, "❌ شما قبلاً به این بازی پیوسته‌اید!", show_alert=True)
        conn.close()
        return

    bet = game['bet_amount']
    user = get_user(user_id, call.from_user.first_name)

    if user['pocket_points'] < bet:
        bot.answer_callback_query(call.id, f"❌ میوپوینت کافی در جیب ندارید! (مبلغ شرط: {bet:,})", show_alert=True)
        conn.close()
        return

    players[str(user_id)] = {'name': call.from_user.first_name, 'score': None}
    current_count = len(players)
    target_count = game['target_players']

    emoji_map = {'slot': '🎰', 'dice': '🎲', 'bowling': '🎳'}
    current_emoji = emoji_map.get(game['game_type'], '🎲')

    if current_count < target_count:
        # هنوز کامل نشده
        cursor.execute("UPDATE active_games SET players_json = ? WHERE game_id = ?", (json.dumps(players), game_id))
        conn.commit()
        conn.close()

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎮 ورود به بازی", callback_data=f"casino_join:{game_id}"))

        bot.answer_callback_query(call.id, "✅ با موفقیت وارد بازی شدید!")
        bot.edit_message_text(
            f"🎮 **لابی بازی {current_emoji}**\n\n"
            f"👥 ظرفیت: {current_count} از {target_count} نفر\n"
            f"💵 مبلغ شرط: {bet:,} میوپوینت\n\n"
            f"اعضا: {', '.join([p['name'] for p in players.values()])}\n"
            f"منتظر بقیه بازیکنان...",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    else:
        # لابی کامل شد -> ویرایش اتوماتیک پیام طبق دستور
        cursor.execute("UPDATE active_games SET players_json = ?, status = 'waiting' WHERE game_id = ?", (json.dumps(players), game_id))
        conn.commit()
        conn.close()

        bot.answer_callback_query(call.id, "🎉 ظرفیت بازی تکمیل شد!")
        bot.edit_message_text(
            f"✅ **شرکت در بازی تمام شد، {target_count} عضو آمدند!**\n\n"
            f"🎯 **انداختن {current_emoji}**\n\n"
            f"⚠️ همه بازیکنان **در ۶۰ ثانیه آینده** مهلت دارند **در جواب (ریپلی) همین پیام** ایموجی {current_emoji} را بفرستند!",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown"
        )

# ------------------------------------------
# ۸. دریافتی تاس / اسلات / بولینگ ریپلی شده و محاسبه نتایج
# ------------------------------------------
@bot.message_handler(content_types=['dice'])
def handle_dice_rolls(message):
    if not message.reply_to_message:
        return

    replied_msg_id = message.reply_to_message.message_id
    user_id = message.from_user.id
    dice_emoji = message.dice.emoji
    val = message.dice.value

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM active_games WHERE message_id = ? AND status = 'waiting'", (replied_msg_id,))
    game = cursor.fetchone()

    if not game:
        conn.close()
        return

    game_id = game['game_id']
    players = json.loads(game['players_json'])

    if str(user_id) not in players:
        conn.close()
        return

    if players[str(user_id)]['score'] is not None:
        bot.reply_to(message, "❌ شما قبلاً حرکت خود را ارسال کرده‌اید!")
        conn.close()
        return

    # ثبت امتیاز کاربر
    players[str(user_id)]['score'] = val
    bet = game['bet_amount']

    # --- بررسی تاس تک‌نفره (حدس زوج/فرد) ---
    if game['game_type'] == 'dice_single':
        pred = players[str(user_id)]['pred']
        is_even = (val % 2 == 0)
        win = (pred == 'even' and is_even) or (pred == 'odd' and not is_even)

        user = get_user(user_id)

        if win:
            payout = int(bet * 1.5)
            new_pocket = user['pocket_points'] + (payout - bet)
            cursor.execute("UPDATE users SET pocket_points = ? WHERE user_id = ?", (new_pocket, user_id))
            res_text = f"🎉 **شما برنده شدید!**\nنتیجه تاس: {val} | حدس شما درست بود (۱.۵ برابر شد).\n💰 سود شما: {payout - bet:,} | موجودی جدید: {new_pocket:,}"
        else:
            new_pocket = user['pocket_points'] - bet
            cursor.execute("UPDATE users SET pocket_points = ? WHERE user_id = ?", (new_pocket, user_id))
            res_text = f"💣 **شما باختید!**\nنتیجه تاس: {val} | حدس شما اشتباه بود.\n📉 ضرر: {bet:,} | موجودی جدید: {new_pocket:,}"

        cursor.execute("UPDATE active_games SET status = 'finished' WHERE game_id = ?", (game_id,))
        conn.commit()
        conn.close()

        bot.reply_to(message, res_text, parse_mode="Markdown")
        return

    # --- بررسی اسلات تک‌نفره ---
    if game['game_type'] == 'slot_single':
        user = get_user(user_id)
        # محاسبه ضریب براساس نتیجه اسلات تلگرام (val از ۱ تا ۶۴)
        if val == 64: # 777
            mult = 3.0
        elif val in [1, 22, 43]: # 3 Bars
            mult = 2.5
        elif val in [16, 32, 48]: # 3 Lemons
            mult = 2.0
        elif val in [4, 8, 12, 20, 24, 28, 40, 44, 52]: # جفت نماد
            mult = 1.0
        elif val in [2, 3, 5, 6, 7]: # شانس کوچک
            mult = 0.5
        else: # باخت کامل
            mult = 0.0

        payout = int(bet * mult)
        diff = payout - bet
        new_pocket = user['pocket_points'] + diff

        cursor.execute("UPDATE users SET pocket_points = ? WHERE user_id = ?", (new_pocket, user_id))
        cursor.execute("UPDATE active_games SET status = 'finished' WHERE game_id = ?", (game_id,))
        conn.commit()
        conn.close()

        if mult > 1.0:
            msg_res = f"🎉 **برد عالی!** ضریب: {mult}x\n💰 دریافتی: {payout:,} میوپوینت (سود: {diff:,})"
        elif mult == 1.0:
            msg_res = f"آسیبی ندیدید! اصل پول شما بازگشت. ({bet:,} میوپوینت)"
        elif mult == 0.5:
            msg_res = f"⚠️ نیم برابر پول شما برگشت. (دریافتی: {payout:,} | ضرر: {abs(diff):,})"
        else:
            msg_res = f"💀 **کامل باختید!** ضریب: 0x | ضرر: {bet:,} میوپوینت"

        bot.reply_to(message, f"🎰 نتیجه اسلات: {val}\n" + msg_res, parse_mode="Markdown")
        return

    # --- بررسی بازی‌های چندنفره (۲ یا ۳ نفره) ---
    all_done = all(p['score'] is not None for p in players.values())

    if not all_done:
        cursor.execute("UPDATE active_games SET players_json = ? WHERE game_id = ?", (json.dumps(players), game_id))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ حرکت {message.from_user.first_name} ثبت شد! منتظر بقیه بازیکنان...")
        return

    # همه بازیکنان حرکت خود را زده‌اند -> تعیین برنده اصلی کل پول
    cursor.execute("UPDATE active_games SET status = 'finished' WHERE game_id = ?", (game_id,))
    conn.commit()

    # یافتن بالاترین امتیاز
    best_score = -1
    winner_id = None
    winner_name = ""

    total_pot = bet * len(players)

    summary = "📊 **نتایج نهایی بازی:**\n"
    for pid, pdata in players.items():
        summary += f"👤 {pdata['name']}: امتیاز {pdata['score']}\n"
        # کسر ابتدا از همه
        cursor.execute("UPDATE users SET pocket_points = pocket_points - ? WHERE user_id = ?", (bet, int(pid)))
        if pdata['score'] > best_score:
            best_score = pdata['score']
            winner_id = int(pid)
            winner_name = pdata['name']

    conn.commit()

    # اهدا کل پول شرط به برنده
    if winner_id:
        cursor.execute("UPDATE users SET pocket_points = pocket_points + ? WHERE user_id = ?", (total_pot, winner_id))
        conn.commit()

    conn.close()

    summary += f"\n🏆 **برنده نهایی:** {winner_name}\n💰 **کل جایزه:** {total_pot:,} میوپوینت"
    bot.send_message(message.chat.id, summary, parse_mode="Markdown")
# ==========================================
# ۱. جدول نژادهای گربه و تولید خودکار میوپوینت
# ==========================================
CAT_TYPES = {
    1: {"name": "🐱 گربه خیابانی (DSH)", "rate_per_hour": 50},
    2: {"name": "🐈 گربه پرشین (Persian)", "rate_per_hour": 150},
    3: {"name": "🐱‍👤 گربه سیامی (Siamese)", "rate_per_hour": 400},
    4: {"name": "🐈‍⬛ گربه بریتانیایی (British Shorthair)", "rate_per_hour": 1000},
    5: {"name": "🦁 گربه اسکاتیش فولد (Scottish Fold)", "rate_per_hour": 2500},
    6: {"name": "🐅 گربه مِین کون (Maine Coon)", "rate_per_hour": 6000},
    7: {"name": "🐆 گربه رگدال (Ragdoll)", "rate_per_hour": 15000},
    8: {"name": "🐆 گربه بنگال (Bengal)", "rate_per_hour": 35000},
    9: {"name": "🧙‍♂️ گربه اسفنکس (Sphynx)", "rate_per_hour": 80000},
    10: {"name": "👑 گربه سلطنتی (Royal Cat)", "rate_per_hour": 200000}
}

def get_cat_type(cat_level):
    lvl = min(max(cat_level, 1), 10)
    return CAT_TYPES[lvl]

def calculate_passive_meows(user_id):
    """محاسبه میوپوینت‌های تولید شده توسط گربه بر اساس زمان گذشته"""
    conn = get_db()
    cursor = conn.cursor()
    
    # اطمینان از وجود ستون‌های مورد نیاز
    cursor.execute("PRAGMA table_info(users)")
    cols = [c[1] for c in cursor.fetchall()]
    if 'cat_level' not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN cat_level INTEGER DEFAULT 1")
    if 'last_claim_time' not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN last_claim_time REAL DEFAULT 0")
    if 'meow_level' not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN meow_level INTEGER DEFAULT 1")
    conn.commit()

    cursor.execute("SELECT cat_level, last_claim_time FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    cat_lvl = row['cat_level'] if row and row['cat_level'] else 1
    last_claim = row['last_claim_time'] if row and row['last_claim_time'] else time.time()
    conn.close()

    now = time.time()
    hours_passed = (now - last_claim) / 3600.0
    cat_info = get_cat_type(cat_lvl)
    produced = int(hours_passed * cat_info['rate_per_hour'])
    
    return produced, cat_lvl, last_claim

# ==========================================
# ۲. آپدیت سیستم میو / مع (با رندوم میوپوینت و کولدون ۳ دقیقه‌ای)
# ==========================================
@bot.message_handler(func=lambda m: m.text and m.text.strip().lower() in ['میو', 'مع'])
def handle_meow_updated(message):
    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.first_name)
    
    can_meow, remaining = check_meow_cooldown(user_id)
    
    if not can_meow:
        mins, secs = divmod(remaining, 60)
        bot.reply_to(message, f"❌ **میوت نمی‌یاد!**\nلطفاً صبر کنید تا **{mins} دقیقه و {secs} ثانیه** دیگر تا بتوانید دوباره میو کنید.")
        return

    # دریافت لول میو برای جایزه رندوم بیشتر
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users)")
    cols = [c[1] for c in cursor.fetchall()]
    if 'meow_level' not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN meow_level INTEGER DEFAULT 1")
        conn.commit()

    cursor.execute("SELECT meow_level, meow_count, pocket_points FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    meow_lvl = row['meow_level'] if row and row['meow_level'] else 1
    
    # جایزه رندوم میوپوینت بر اساس لول میو
    base_random = random.randint(50, 200)
    earned_points = base_random * meow_lvl
    
    new_meow_count = user['meow_count'] + 1
    new_pocket = user['pocket_points'] + earned_points
    current_time = time.time()

    cursor.execute('''
        UPDATE users 
        SET meow_count = ?, pocket_points = ?, last_meow_time = ?
        WHERE user_id = ?
    ''', (new_meow_count, new_pocket, current_time, user_id))
    conn.commit()
    conn.close()

    bot.reply_to(
        message, 
        f"🐱 **میو!**\n\n"
        f"🎉 مقدار **{earned_points:,} میوپوینت** به جیبتون اضافه شد!\n"
        f"💵 **موجودی جدید جیب شما:** {new_pocket:,} میوپوینت\n"
        f"🐾 مجموع میوها: {new_meow_count}",
        parse_mode="Markdown"
    )

# ==========================================
# ۳. آپدیت پروفایل کامل (با ریپلی و لول میو)
# ==========================================
@bot.message_handler(func=lambda m: m.text and m.text.strip().lower() in ['پروفایل', 'میوهاش'])
def handle_profile_updated(message):
    target_id = message.from_user.id
    target_name = message.from_user.first_name
    
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        target_name = message.reply_to_message.from_user.first_name

    user = get_user(target_id, target_name)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users)")
    cols = [c[1] for c in cursor.fetchall()]
    if 'meow_level' not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN meow_level INTEGER DEFAULT 1")
    if 'cat_level' not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN cat_level INTEGER DEFAULT 1")
    conn.commit()

    cursor.execute("SELECT meow_level, cat_level FROM users WHERE user_id = ?", (target_id,))
    row = cursor.fetchone()
    meow_lvl = row['meow_level'] if row and row['meow_level'] else 1
    cat_lvl = row['cat_level'] if row and row['cat_level'] else 1
    conn.close()

    cat_info = get_cat_type(cat_lvl)

    profile_text = (
        f"👤 **نام اکانت:** {target_name}\n"
        f"🐱 **اسم گربه:** {user['cat_name']}\n"
        f"🏷 **نژاد گربه:** {cat_info['name']}\n"
        f"⭐ **سطح گربه:** {cat_lvl}\n"
        f"⚡ **لول مع/میو:** {meow_lvl}\n"
        f"🐾 **تعداد میو/مع:** {user['meow_count']:,}\n"
        f"💰 **میوپوینت داخل جیب:** {user['pocket_points']:,} میوپوینت"
    )
    bot.reply_to(message, profile_text, parse_mode="Markdown")

# ==========================================
# ۴. پنل هوشمند پیشی (با صدا زدن اسم گربه یا «پیشی»)
# ==========================================
@bot.message_handler(func=lambda m: m.text and any(k in m.text.strip().lower() for k in ['پیشی', 'گربه', 'برفک']))
def handle_cat_smart_panel(message):
    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.first_name)
    
    produced, cat_lvl, _ = calculate_passive_meows(user_id)
    cat_info = get_cat_type(cat_lvl)

    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_upgrade = types.InlineKeyboardButton(f"⬆️ ارتقا سطح گربه (سطح فعلی: {cat_lvl})", callback_data="cat_upgrade_level")
    btn_claim = types.InlineKeyboardButton(f"🎁 برداشت میوپوینت ({produced:,})", callback_data="cat_claim_points")
    btn_rename = types.InlineKeyboardButton("✏️ تغییر اسم گربه", callback_data="cat_rename")
    markup.add(btn_upgrade, btn_claim, btn_rename)

    text = (
        f"😺 **پنل اختصاصی پیشی**\n\n"
        f"📛 **اسم پیشی:** {user['cat_name']}\n"
        f"⭐ **سطح پیشی:** {cat_lvl}\n"
        f"🐱 **نژاد:** {cat_info['name']}\n"
        f"⚡ **نرخ تولید:** {cat_info['rate_per_hour']:,} میوپوینت / ساعت\n"
        f"💎 **میوپوینت آماده برداشت:** {produced:,} میوپوینت\n\n"
        f"چه کاری می‌خوای برات انجام بدم؟"
    )
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_'))
def handle_cat_panel_callbacks(call):
    user_id = call.from_user.id
    
    if call.data == "cat_upgrade_level":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT cat_level, pocket_points FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        cat_lvl = row['cat_level'] if row and row['cat_level'] else 1
        pocket = row['pocket_points'] if row else 0

        if cat_lvl >= 10:
            bot.answer_callback_query(call.id, "👑 سطح گربه شما در حداکثر میزان ممکن (۱۰) قرار دارد!", show_alert=True)
            conn.close()
            return

        upgrade_cost = cat_lvl * 15000
        if pocket < upgrade_cost:
            bot.answer_callback_query(call.id, f"❌ میوپوینت کافی در جیب ندارید! هزینه ارتقا: {upgrade_cost:,}", show_alert=True)
            conn.close()
            return

        new_lvl = cat_lvl + 1
        new_pocket = pocket - upgrade_cost
        cursor.execute("UPDATE users SET cat_level = ?, pocket_points = ? WHERE user_id = ?", (new_lvl, new_pocket, user_id))
        conn.commit()
        conn.close()

        bot.answer_callback_query(call.id, f"🎉 سطح گربه شما به {new_lvl} ارتقا یافت!", show_alert=True)
        bot.edit_message_text(f"✅ **سطح گربه شما با موفقیت به {new_lvl} ارتقا یافت!**", call.message.chat.id, call.message.message_id)

    elif call.data == "cat_claim_points":
        produced, cat_lvl, _ = calculate_passive_meows(user_id)
        
        if produced <= 0:
            bot.answer_callback_query(call.id, "❌ هنوز میوپوینتی برای برداشت تولید نشده است!", show_alert=True)
            return

        user = get_user(user_id)
        new_pocket = user['pocket_points'] + produced
        now = time.time()

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET pocket_points = ?, last_claim_time = ? WHERE user_id = ?", (new_pocket, now, user_id))
        conn.commit()
        conn.close()

        bot.answer_callback_query(call.id, f"✅ مقدار {produced:,} میوپوینت به جیب شما اضافه شد!", show_alert=True)
        bot.edit_message_text(f"💰 **مقدار {produced:,} میوپوینت تولید شده توسط گربه با موفقیت برداشت شد!**", call.message.chat.id, call.message.message_id)

# ==========================================
# ۵. پنل اختصاصی ادمین (Admin Panel)
# ==========================================
@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.text and m.text.strip().lower() in ['ادمین', '/admin'])
def handle_admin_panel(message):
    text = (
        f"🛠 **پنل مدیریت ادمین**\n\n"
        f"فرمان‌های دسترس ادمین:\n\n"
        f"1️⃣ **اعطای میوپوینت به کاربر:**\n"
        f"`اعطا 12345678 50k`\n\n"
        f"2️⃣ **تنظیم سطح گربه کاربر:**\n"
        f"`سطح گربه 12345678 5`\n\n"
        f"3️⃣ **مکس کردن سطح گربه کاربر (لول ۱۰):**\n"
        f"`مکس گربه 12345678`\n\n"
        f"4️⃣ **افزایش لول مع/میو کاربر:**\n"
        f"`سطح میو 12345678 3`\n\n"
        f"*(می‌توانید دستورات را با آیدی عددی کاربر بفرستید)*"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

# پردازش دستورات متنی ادمین
@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.text)
def handle_admin_commands(message):
    text = message.text.strip().split()
    if not text:
        return

    cmd = text[0]

    # ۱. اعطا / ارسال میوپوینت
    if cmd == "اعطا" and len(text) >= 3:
        try:
            target_id = int(parse_fa_num(text[1]))
            amount = parse_amount(text[2])
            if amount:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET pocket_points = pocket_points + ? WHERE user_id = ?", (amount, target_id))
                conn.commit()
                conn.close()
                bot.reply_to(message, f"✅ مقدار **{amount:,} میوپوینت** به کاربر `{target_id}` اعطا شد.", parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"❌ خطا: {e}")

    # ۲. تغییر سطح گربه
    elif cmd == "سطح" and len(text) >= 4 and text[1] == "گربه":
        try:
            target_id = int(parse_fa_num(text[2]))
            lvl = int(parse_fa_num(text[3]))
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET cat_level = ? WHERE user_id = ?", (lvl, target_id))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ سطح گربه کاربر `{target_id}` به **{lvl}** تغییر یافت.", parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"❌ خطا: {e}")

    # ۳. مکس سطح گربه
    elif cmd == "مکس" and len(text) >= 3 and text[1] == "گربه":
        try:
            target_id = int(parse_fa_num(text[2]))
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET cat_level = 10 WHERE user_id = ?", (target_id,))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"👑 سطح گربه کاربر `{target_id}` مکس شد (سطح ۱۰).", parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"❌ خطا: {e}")

    # ۴. افزایش لول مع/میو
    elif cmd == "سطح" and len(text) >= 4 and text[1] == "میو":
        try:
            target_id = int(parse_fa_num(text[2]))
            lvl = int(parse_fa_num(text[3]))
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET meow_level = ? WHERE user_id = ?", (lvl, target_id))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"⚡ لول میو/مع کاربر `{target_id}` به **{lvl}** ارتقا یافت.", parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"❌ خطا: {e}")
import time
import random
import threading
from telebot import types

# ==========================================
# ۱. جدول ۱۰ نوع ماهی بر اساس کمیابی و ارزش
# ==========================================
FISH_TYPES = {
    1: {"name": "🐟 ماهی کیلکا (ساده)", "rarity": "عادی", "price": 500, "nutritional_val": 100},
    2: {"name": "🐠 ماهی قزل‌آلا", "rarity": "عادی", "price": 1200, "nutritional_val": 250},
    3: {"name": "🐟 کپور طلایی", "rarity": "کم‌یاب", "price": 3000, "nutritional_val": 500},
    4: {"name": "🐡 ماهی بادکنکی", "rarity": "کم‌یاب", "price": 7500, "nutritional_val": 1000},
    5: {"name": "شیرماهی خلیج", "rarity": "نایاب", "price": 18000, "nutritional_val": 2200},
    6: {"name": "🦈 کوسه کوچک شیشه‌ای", "rarity": "نایاب", "price": 45000, "nutritional_val": 5000},
    7: {"name": "🐬 دلفین جادویی", "rarity": "افسانه‌ای", "price": 100000, "nutritional_val": 12000},
    8: {"name": "🐉 اژدهای آبی ocean", "rarity": "افسانه‌ای", "price": 250000, "nutritional_val": 30000},
    9: {"name": "✨ ماهی کریستالی میو", "rarity": "اسطوره‌ای", "price": 600000, "nutritional_val": 75000},
    10: {"name": "👑 ماهی سلطنتی خاویار", "rarity": "اسطوره‌ای", "price": 1500000, "nutritional_val": 200000}
}

# حافظه موقت برای مدیریت ماهی‌های صید شده
active_fishes = {}  # {user_id: {"fish_id": int, "msg_id": int, "claimed": bool}}

def get_random_fish():
    """انتخاب ماهی بر اساس شانس و کمیابی"""
    rand = random.random()
    if rand < 0.35:      # ۳۵٪ شانسی
        fish_id = random.choice([1, 2])
    elif rand < 0.65:    # ۳۰٪ شانسی
        fish_id = random.choice([3, 4])
    elif rand < 0.85:    # ۲۰٪ شانسی
        fish_id = random.choice([5, 6])
    elif rand < 0.96:    # ۱۱٪ شانسی
        fish_id = random.choice([7, 8])
    else:               # ۴٪ شانسی
        fish_id = random.choice([9, 10])
    return fish_id, FISH_TYPES[fish_id]

# ==========================================
# ۲. ساخت و آماده‌سازی جدول‌های یخچال و ماهی‌گیری
# ==========================================
def init_fishing_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # جدول یخچال کاربران
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_fridge (
            user_id INTEGER PRIMARY KEY,
            capacity INTEGER DEFAULT 5,
            last_fish_time REAL DEFAULT 0
        )
    ''')
    
    # جدول ماهی‌های موجود در یخچال
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fridge_fishes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            fish_type_id INTEGER,
            catch_time REAL
        )
    ''')
    conn.commit()
    conn.close()

init_fishing_db()

# ==========================================
# ۳. سیستم ماهی‌گیری (با تایمر ۱۳ ثانیه‌ای و ۶۰ ثانیه‌ای)
# ==========================================
@bot.message_handler(func=lambda m: m.text and m.text.strip().lower() == 'ماهی')
def handle_fishing_start(message):
    user_id = message.from_user.id
    get_user(user_id, message.from_user.first_name)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT last_fish_time FROM user_fridge WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    now = time.time()
    last_fish = row['last_fish_time'] if row and row['last_fish_time'] else 0
    cooldown = 20 * 60  # ۲۰ دقیقه
    
    if now - last_fish < cooldown:
        remaining = int(cooldown - (now - last_fish))
        mins, secs = divmod(remaining, 60)
        bot.reply_to(message, f"🎣 **ماهی‌ها ترسیدن!**\nلطفاً **{mins} دقیقه و {secs} ثانیه** صبر کنید تا بتوانید دوباره ماهی‌گیری کنید.")
        conn.close()
        return

    # به‌روزرسانی زمان آخرین ماهی‌گیری
    cursor.execute("INSERT OR REPLACE INTO user_fridge (user_id, capacity, last_fish_time) VALUES (?, COALESCE((SELECT capacity FROM user_fridge WHERE user_id = ?), 5), ?)", (user_id, user_id, now))
    conn.commit()
    conn.close()

    sent_msg = bot.reply_to(message, "🎣 قلاب ماهی‌گیری به آب انداخته شد...\nلطفاً **۱۳ ثانیه** صبر کنید تا ماهی به قلاب بیفته!")

    # اجرای نخ جانبی برای انتظار ۱۳ ثانیه‌ای صید
    def catch_task():
        time.sleep(13)
        fish_id, fish_info = get_random_fish()
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_sell = types.InlineKeyboardButton(f"💰 فروش فوری ({fish_info['price']:,} میوپوینت)", callback_data=f"fish_sell_{fish_id}")
        btn_fridge = types.InlineKeyboardButton("🧊 انتقال به یخچال", callback_data=f"fish_to_fridge_{fish_id}")
        btn_feed = types.InlineKeyboardButton("🐱 بده پیشی بخوره", callback_data=f"fish_feed_{fish_id}")
        markup.add(btn_sell, btn_fridge, btn_feed)

        text = (
            f"🎉 **ماهی صید شد!**\n\n"
            f"📛 **نام ماهی:** {fish_info['name']}\n"
            f"✨ **درجه کمیابی:** {fish_info['rarity']}\n"
            f"🍖 **ارزش غذایی:** {fish_info['nutritional_val']:,} میوپوینت\n"
            f"💵 **قیمت فروش:** {fish_info['price']:,} میوپوینت\n\n"
            f"⏰ **توجه:** فقط ۶۰ ثانیه فرصت دارید یکی از دکمه‌های زیر را انتخاب کنید!"
        )
        
        try:
            bot.edit_message_text(text, sent_msg.chat.id, sent_msg.message_id, reply_markup=markup, parse_mode="Markdown")
            active_fishes[user_id] = {"fish_id": fish_id, "msg_id": sent_msg.message_id, "claimed": False}
            
            # تایمر ۶۰ ثانیه‌ای برای فرار ماهی
            def escape_task():
                time.sleep(60)
                if user_id in active_fishes and not active_fishes[user_id]["claimed"]:
                    active_fishes[user_id]["claimed"] = True
                    try:
                        bot.edit_message_text(
                            "🏃‍♂️💨 **ماهی فرار کرد!**\nشما در ۶۰ ثانیه تصمیمی نگرفتید. تا ماهی‌گیری بعدی **۲۰ دقیقه** باید صبر کنید.",
                            sent_msg.chat.id,
                            sent_msg.message_id
                        )
                    except Exception:
                        pass
            
            threading.Thread(target=escape_task, daemon=True).start()

        except Exception as e:
            print(f"Error in fishing update: {e}")

    threading.Thread(target=catch_task, daemon=True).start()

# پردازش دکمه‌های ماهی صیدشده
@bot.callback_query_handler(func=lambda call: call.data.startswith('fish_'))
def handle_caught_fish_actions(call):
    user_id = call.from_user.id
    data = call.data.split('_')
    action = data[1]
    
    if action in ['sell', 'to', 'feed']:
        if user_id not in active_fishes or active_fishes[user_id]["claimed"]:
            bot.answer_callback_query(call.id, "❌ زمان این ماهی به پایان رسیده یا ماهی فرار کرده است!", show_alert=True)
            return

        fish_id = int(data[-1])
        fish_info = FISH_TYPES[fish_id]
        active_fishes[user_id]["claimed"] = True

        if action == "sell":
            user = get_user(user_id)
            new_pocket = user['pocket_points'] + fish_info['price']
            
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET pocket_points = ? WHERE user_id = ?", (new_pocket, user_id))
            conn.commit()
            conn.close()

            bot.answer_callback_query(call.id, f"💰 ماهی با موفقیت به قیمت {fish_info['price']:,} فروخته شد!", show_alert=True)
            bot.edit_message_text(f"💵 **ماهی {fish_info['name']} فروخته شد!**\nمبلغ {fish_info['price']:,} میوپوینت به جیب شما اضافه گردید.", call.message.chat.id, call.message.message_id)

        elif action == "to": # انتقال به یخچال
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT capacity FROM user_fridge WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            cap = row['capacity'] if row else 5

            cursor.execute("SELECT COUNT(*) as count FROM fridge_fishes WHERE user_id = ?", (user_id,))
            current_count = cursor.fetchone()['count']

            if current_count >= cap:
                bot.answer_callback_query(call.id, f"🧊 یخچال شما پر است! (ظرفیت فعلی: {cap})", show_alert=True)
                active_fishes[user_id]["claimed"] = False  # اجازه انتخاب گزینه‌های دیگر
                conn.close()
                return

            cursor.execute("INSERT INTO fridge_fishes (user_id, fish_type_id, catch_time) VALUES (?, ?, ?)", (user_id, fish_id, time.time()))
            conn.commit()
            conn.close()

            bot.answer_callback_query(call.id, "🧊 ماهی با موفقیت در یخچال ذخیره شد!", show_alert=True)
            bot.edit_message_text(f"✅ **ماهی {fish_info['name']} به یخچال منتقل شد.**", call.message.chat.id, call.message.message_id)

        elif action == "feed": # دادن به پیشی
            user = get_user(user_id)
            gained_points = fish_info['nutritional_val']
            new_pocket = user['pocket_points'] + gained_points

            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET pocket_points = ? WHERE user_id = ?", (new_pocket, user_id))
            conn.commit()
            conn.close()

            bot.answer_callback_query(call.id, f"😋 پیشی ماهی رو خورد و انرژی گرفت! (+{gained_points:,} میوپوینت)", show_alert=True)
            bot.edit_message_text(f"😸 **پیشی با لذت {fish_info['name']} رو خورد!**\nارزش غذایی: +{gained_points:,} میوپوینت به جیب اضافه شد.", call.message.chat.id, call.message.message_id)

# ==========================================
# ۴. پنل یخچال و مدیریت ماهی‌های داخل آن
# ==========================================
@bot.message_handler(func=lambda m: m.text and m.text.strip().lower() == 'یخچال')
def handle_fridge_panel(message):
    user_id = message.from_user.id
    get_user(user_id, message.from_user.first_name)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT capacity FROM user_fridge WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    cap = row['capacity'] if row else 5

    cursor.execute("SELECT COUNT(*) as count FROM fridge_fishes WHERE user_id = ?", (user_id,))
    fish_count = cursor.fetchone()['count']
    conn.close()

    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_upgrade = types.InlineKeyboardButton(f"⬆️ ارتقای ارتفاع یخچال (ظرفیت فعلی: {cap})", callback_data="fridge_upgrade")
    btn_list = types.InlineKeyboardButton(f"🐟 لیست ماهی‌های درون یخچال ({fish_count}/{cap})", callback_data="fridge_list")
    btn_sell_all = types.InlineKeyboardButton("💰 فروش یکجای تمام ماهی‌های یخچال", callback_data="fridge_sell_all")
    markup.add(btn_upgrade, btn_list, btn_sell_all)

    text = (
        f"🧊 **پنل یخچال و نگهداری ماهی**\n\n"
        f"📦 **ظرفیت فعلی:** {fish_count} از {cap} ماهی\n"
        f"💡 *با ارتقای ارتفاع یخچال می‌توانید ماهی‌های بیشتری ذخیره کنید!*"
    )
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('fridge_'))
def handle_fridge_callbacks(call):
    user_id = call.from_user.id
    
    if call.data == "fridge_upgrade":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT capacity FROM user_fridge WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        cap = row['capacity'] if row else 5
        
        user = get_user(user_id)
        cost = cap * 20000

        if user['pocket_points'] < cost:
            bot.answer_callback_query(call.id, f"❌ میوپوینت کافی ندارید! هزینه ارتقا: {cost:,}", show_alert=True)
            conn.close()
            return

        new_cap = cap + 5
        new_pocket = user['pocket_points'] - cost

        cursor.execute("UPDATE user_fridge SET capacity = ? WHERE user_id = ?", (new_cap, user_id))
        cursor.execute("UPDATE users SET pocket_points = ? WHERE user_id = ?", (new_pocket, user_id))
        conn.commit()
        conn.close()

        bot.answer_callback_query(call.id, f"🎉 ارتفاع یخچال افزایش یافت! ظرفیت جدید: {new_cap}", show_alert=True)
        bot.edit_message_text(f"🧊 **ارتفاع یخچال ارتقا یافت!**\nظرفیت جدید: {new_cap} ماهی", call.message.chat.id, call.message.message_id)

    elif call.data == "fridge_list":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, fish_type_id FROM fridge_fishes WHERE user_id = ?", (user_id,))
        fishes = cursor.fetchall()
        conn.close()

        if not fishes:
            bot.answer_callback_query(call.id, "🧊 یخچال شما خالی است!", show_alert=True)
            return

        markup = types.InlineKeyboardMarkup(row_width=2)
        for item in fishes:
            f_info = FISH_TYPES[item['fish_type_id']]
            btn = types.InlineKeyboardButton(f"{f_info['name']}", callback_data=f"fitem_select_{item['id']}")
            markup.add(btn)

        markup.add(types.InlineKeyboardButton("🔙 خروج از یخچال", callback_data="fridge_exit"))
        bot.edit_message_text("🧊 **لیست ماهی‌های موجود در یخچال:**\nیکی را برای انجام عملیات انتخاب کنید:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "fridge_sell_all":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT fish_type_id FROM fridge_fishes WHERE user_id = ?", (user_id,))
        fishes = cursor.fetchall()

        if not fishes:
            bot.answer_callback_query(call.id, "❌ هیچ ماهی در یخچال نیست!", show_alert=True)
            conn.close()
            return

        total_price = sum(FISH_TYPES[f['fish_type_id']]['price'] for f in fishes)
        cursor.execute("DELETE FROM fridge_fishes WHERE user_id = ?", (user_id,))
        
        user = get_user(user_id)
        new_pocket = user['pocket_points'] + total_price
        cursor.execute("UPDATE users SET pocket_points = ? WHERE user_id = ?", (new_pocket, user_id))
        
        conn.commit()
        conn.close()

        bot.answer_callback_query(call.id, f"💰 تمام ماهی‌ها به مبلغ {total_price:,} فروخته شدند!", show_alert=True)
        bot.edit_message_text(f"💵 **تمام ماهی‌های یخچال به مبلغ {total_price:,} میوپوینت فروخته شدند!**", call.message.chat.id, call.message.message_id)

    elif call.data == "fridge_exit":
        bot.edit_message_text("🚪 **از یخچال خارج شدید.**", call.message.chat.id, call.message.message_id)

# مدیریت دکمه‌های تکی ماهی‌های درون یخچال
@bot.callback_query_handler(func=lambda call: call.data.startswith('fitem_'))
def handle_fridge_item_action(call):
    user_id = call.from_user.id
    data = call.data.split('_')
    action = data[1]
    
    if action == "select":
        item_id = int(data[2])
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT fish_type_id FROM fridge_fishes WHERE id = ? AND user_id = ?", (item_id, user_id))
        row = cursor.fetchone()
        conn.close()

        if not row:
            bot.answer_callback_query(call.id, "❌ این ماهی در یخچال یافت نشد!", show_alert=True)
            return

        f_info = FISH_TYPES[row['fish_type_id']]

        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_sell = types.InlineKeyboardButton(f"💰 فروش ({f_info['price']:,} میوپوینت)", callback_data=f"fitem_dosell_{item_id}")
        btn_feed = types.InlineKeyboardButton("🐱 بده پیشی بخوره", callback_data=f"fitem_dofeed_{item_id}")
        btn_exit = types.InlineKeyboardButton("🔙 خروج از یخچال", callback_data="fridge_exit")
        markup.add(btn_sell, btn_feed, btn_exit)

        text = (
            f"🐟 **ماهی انتخاب شده:** {f_info['name']}\n"
            f"💵 **قیمت فروش:** {f_info['price']:,} میوپوینت\n"
            f"🍖 **ارزش غذایی:** {f_info['nutritional_val']:,} میوپوینت\n\n"
            f"چه عملیاتی می‌خواهید انجام دهید؟"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif action == "dosell":
        item_id = int(data[2])
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT fish_type_id FROM fridge_fishes WHERE id = ? AND user_id = ?", (item_id, user_id))
        row = cursor.fetchone()

        if row:
            f_info = FISH_TYPES[row['fish_type_id']]
            cursor.execute("DELETE FROM fridge_fishes WHERE id = ?", (item_id,))
            
            user = get_user(user_id)
            new_pocket = user['pocket_points'] + f_info['price']
            cursor.execute("UPDATE users SET pocket_points = ? WHERE user_id = ?", (new_pocket, user_id))
            conn.commit()

            bot.answer_callback_query(call.id, f"💰 ماهی با قیمت {f_info['price']:,} فروخته شد!", show_alert=True)
            bot.edit_message_text(f"💵 **ماهی {f_info['name']} از یخچال فروخته شد!**", call.message.chat.id, call.message.message_id)
        conn.close()

    elif action == "dofeed":
        item_id = int(data[2])
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT fish_type_id FROM fridge_fishes WHERE id = ? AND user_id = ?", (item_id, user_id))
        row = cursor.fetchone()

        if row:
            f_info = FISH_TYPES[row['fish_type_id']]
            cursor.execute("DELETE FROM fridge_fishes WHERE id = ?", (item_id,))
            
            user = get_user(user_id)
            new_pocket = user['pocket_points'] + f_info['nutritional_val']
            cursor.execute("UPDATE users SET pocket_points = ? WHERE user_id = ?", (new_pocket, user_id))
            conn.commit()

            bot.answer_callback_query(call.id, "😋 پیشی ماهی رو خورد!", show_alert=True)
            bot.edit_message_text(f"😸 **پیشی ماهی {f_info['name']} را نوش جان کرد!** (+{f_info['nutritional_val']:,} میوپوینت)", call.message.chat.id, call.message.message_id)
        conn.close()

# ==========================================
# ۵. راه اندازی پایانی ربات (Infinity Polling)
# ==========================================
if __name__ == "__main__":
    print("🤖 ربات پیشی شاپ با موفقیت روشن شد و در حال پاسخگویی است...")
    bot.infinity_polling(skip_pending=True)
        
