# ==================== بخش 1 از 6 ====================
# کتابخانه‌ها و تنظیمات پایه

import asyncio
import logging
import random
import re
import sqlite3
import time
from datetime import datetime
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# تنظیمات اصلی ربات
BOT_TOKEN = "8328122794:AAG67dIJIsz5tqgtVF0BHo80aZWIGtECc-A"
ADMIN_ID = 8918154552
DB_NAME = "pishi_bot.db"

# تنظیمات لاگینگ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ----------------------------------------------------
# مدیریت پایگاه داده (SQLite)
# ----------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # جدول کاربران و گربه
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT,
        wallet INTEGER DEFAULT 1000,
        mew_count INTEGER DEFAULT 0,
        mew_level INTEGER DEFAULT 1,
        last_mew_time REAL DEFAULT 0,
        
        # اطلاعات گربه
        cat_name TEXT DEFAULT 'پیشی',
        cat_level INTEGER DEFAULT 1,
        cat_type INTEGER DEFAULT 1,
        cat_last_collect REAL DEFAULT 0,
        
        # اطلاعات یخچال و ماهی‌گیری
        fridge_level INTEGER DEFAULT 1,
        last_fish_time REAL DEFAULT 0,
        
        # اطلاعات کارخانه
        factory_level INTEGER DEFAULT 1,
        factory_producing INTEGER DEFAULT 0,
        factory_product TEXT DEFAULT '',
        factory_amount INTEGER DEFAULT 0,
        factory_end_time REAL DEFAULT 0,
        factory_cost INTEGER DEFAULT 0,
        
        # حساب بانکی
        bank_acc TEXT UNIQUE,
        bank_balance INTEGER DEFAULT 0
    )
    """)
    
    # جدول انبار محصولات کارخانه
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS factory_inventory (
        user_id INTEGER,
        product_id INTEGER,
        amount INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, product_id)
    )
    """)
    
    # جدول یخچال و ماهی‌ها
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fridge_fish (
        user_id INTEGER,
        fish_id INTEGER,
        amount INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, fish_id)
    )
    """)
    
    # جدول اتاق‌های بازی کازینو
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS casino_rooms (
        room_id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_type TEXT,
        max_players INTEGER,
        bet_amount INTEGER,
        creator_id INTEGER,
        status TEXT DEFAULT 'waiting',
        choiced_option TEXT DEFAULT '',
        message_id INTEGER DEFAULT 0,
        chat_id INTEGER DEFAULT 0
    )
    """)
    
    # جدول اعضای اتاق‌های کازینو
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS casino_players (
        room_id INTEGER,
        user_id INTEGER,
        move_result INTEGER DEFAULT -1,
        PRIMARY KEY (room_id, user_id)
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ----------------------------------------------------
# توابع کمکی کاربردی
# ----------------------------------------------------

def fmt(num: int) -> str:
    """فرمت‌دهی اعداد به‌صورت سه رقم سه رقم (مثلا 10,000,000)"""
    return f"{int(num):,}"

def get_user(user_id: int, first_name: str = "کاربر"):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        # ایجاد حساب جدید با شماره حساب بانکی تصادفی
        acc_num = f"6037{random.randint(1000000000, 9999999999)}"
        cursor.execute("""
        INSERT INTO users (user_id, first_name, cat_last_collect, bank_acc)
        VALUES (?, ?, ?, ?)
        """, (user_id, first_name, time.time(), acc_num))
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        
    conn.close()
    return user

def update_user(user_id: int, **kwargs):
    conn = get_db()
    cursor = conn.cursor()
    set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
    values = list(kwargs.values())
    values.append(user_id)
    cursor.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", values)
    conn.commit()
    conn.close()

# انواع گربه‌ها بر اساس سطح
CAT_TYPES = {
    1: "گربه خیابانی",
    2: "گربه خانگی ملوس",
    3: "گربه پرشین",
    4: "گربه اسکاتیش فولد",
    5: "گربه سیامی",
    6: "گربه بنگال پادشاهی",
    7: "گربه اسفنکس جادویی",
    8: "گربه رباتیک سایبری",
    9: "گربه اژدهایی",
    10: "گربه افسانه‌ای میو"
}

# نرخ تولید و ظرفیت جیب بر اساس سطح گربه
def get_cat_stats(level: int):
    prod_per_sec = level * 1.5  # نرخ تولید بر حسب ثانیه
    max_wallet_capacity = level * 70000  # ظرفیت جیب
    return prod_per_sec, max_wallet_capacity

async def send_pm(context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    """ارسال پیام خصوصی به کاربر جهت اطلاع‌رسانی تراکنش‌ها"""
    try:
        await context.bot.send_message(chat_id=user_id, text=text)
    except Exception:
        pass
        # ==================== بخش 2 از 6 ====================
# سیستم میو/مع، پروفایل و مدیریت گربه (پیشی)

# ----------------------------------------------------
# 1. سیستم میو / مع زدن
# ----------------------------------------------------

async def handle_mew(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    user = get_user(user_id, first_name)
    
    current_time = time.time()
    last_mew = user["last_mew_time"]
    cooldown = 180  # 3 دقیقه کول‌داون (180 ثانیه)
    
    if current_time - last_mew < cooldown:
        remaining_sec = int(cooldown - (current_time - last_mew))
        mins = remaining_sec // 60
        secs = remaining_sec % 60
        time_str = f"{mins} دقیقه و {secs} ثانیه" if mins > 0 else f"{secs} ثانیه"
        await update.message.reply_text(f"😿 میوت نمیاد! لطفاً {time_str} صبر کن تا بتونی دوباره میو کنی.")
        return

    # محاسبه پاداش رندوم و ارتقای لول میو
    mew_level = user["mew_level"]
    earned = random.randint(100, 300) * mew_level
    new_wallet = user["wallet"] + earned
    new_mew_count = user["mew_count"] + 1
    
    # هر 10 میو یک لول مع/میو بالا می‌رود
    new_mew_level = (new_mew_count // 10) + 1
    
    update_user(
        user_id,
        wallet=new_wallet,
        mew_count=new_mew_count,
        mew_level=new_mew_level,
        last_mew_time=current_time
    )
    
    msg = (
        f"🐾 **میییییو!**\n\n"
        f"✨ مقدار **{fmt(earned)}** میوپوینت به جیبت اضافه شد!\n"
        f"💰 موجودی جدید جیب: **{fmt(new_wallet)}** میوپوینت\n"
        f"📊 لول میو: **{new_mew_level}** | مجموع میوها: **{fmt(new_mew_count)}**"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


# ----------------------------------------------------
# 2. مشاهده پروفایل کاربر
# ----------------------------------------------------

async def handle_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # بررسی ریپلی برای دریافت اطلاعات کاربر موردنظر
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
    else:
        target = update.effective_user
        
    user = get_user(target.id, target.first_name)
    cat_type_name = CAT_TYPES.get(min(user["cat_level"], 10), "گربه افسانه‌ای")
    
    profile_text = (
        f"👤 **پروفایل میویی کاربر**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📛 **نام کاربر:** {user['first_name']}\n"
        f"🐱 **نام گربه:** {user['cat_name']} ({cat_type_name})\n"
        f"💰 **میوپوینت جیب:** {fmt(user['wallet'])}\n"
        f"🏦 **موجودی بانک:** {fmt(user['bank_balance'])}\n"
        f"💳 **شماره حساب:** `{user['bank_acc']}`\n"
        f"⭐ **لول میو/مع:** {user['mew_level']}\n"
        f"🐾 **تعداد میوها:** {fmt(user['mew_count'])}\n"
        f"🏭 **سطح کارخانه:** {user['factory_level']}\n"
        f"🧊 **سطح یخچال:** {user['fridge_level']}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(profile_text, parse_mode="Markdown")


# ----------------------------------------------------
# 3. پنل و مدیریت پیشی (گربه)
# ----------------------------------------------------

async def handle_pishi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id, update.effective_user.first_name)
    
    cat_level = user["cat_level"]
    prod_per_sec, max_cap = get_cat_stats(cat_level)
    
    # محاسبه میوپوینت‌های تولید شده و آماده برداشت
    elapsed = time.time() - user["cat_last_collect"]
    pending_points = min(int(elapsed * prod_per_sec), max_cap)
    
    cat_type_str = CAT_TYPES.get(min(cat_level, 10), "گربه افسانه‌ای میو")
    upgrade_cost = cat_level * 5000
    
    pishi_text = (
        f"🐱 **پنل اختصاصی پیشی**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏷 **نام گربه:** {user['cat_name']}\n"
        f"🏅 **سطح گربه:** {cat_level}\n"
        f"✨ **نوع گربه:** {cat_type_str}\n"
        f"⚡ **نرخ تولید:** {fmt(prod_per_sec)} میوپوینت در ثانیه\n"
        f"📦 **ظرفیت انبار گربه:** {fmt(max_cap)} میوپوینت\n"
        f"💰 **میوپوینت آماده برداشت:** {fmt(pending_points)}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    
    keyboard = [
        [InlineKeyboardButton(f"🔼 ارتقا سطح ({fmt(upgrade_cost)} میوپوینت)", callback_data="cat_upgrade")],
        [InlineKeyboardButton(f"💰 برداشت ({fmt(pending_points)})", callback_data="cat_collect")],
        [InlineKeyboardButton("✏️ تغییر اسم گربه", callback_data="cat_rename")]
    ]
    
    await update.message.reply_text(
        pishi_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


# کال‌بک‌های مربوط به گربه
async def cat_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = get_user(user_id, query.from_user.first_name)
    data = query.data
    
    if data == "cat_upgrade":
        cat_level = user["cat_level"]
        cost = cat_level * 5000
        
        if user["wallet"] < cost:
            await query.answer(f"❌ موجودی جیب کافی نیست! نیاز به {fmt(cost)} میوپوینت داری.", show_alert=True)
            return
            
        update_user(user_id, wallet=user["wallet"] - cost, cat_level=cat_level + 1)
        await query.answer(f"🎉 مبارکه! سطح گربه به {cat_level + 1} ارتقا یافت.", show_alert=True)
        
    elif data == "cat_collect":
        cat_level = user["cat_level"]
        prod_per_sec, max_cap = get_cat_stats(cat_level)
        elapsed = time.time() - user["cat_last_collect"]
        pending_points = min(int(elapsed * prod_per_sec), max_cap)
        
        if pending_points <= 0:
            await query.answer("❌ هنوز میوپوینتی برای برداشت تولید نشده است!", show_alert=True)
            return
            
        new_wallet = user["wallet"] + pending_points
        update_user(user_id, wallet=new_wallet, cat_last_collect=time.time())
        await query.answer(f"✅ مقدار {fmt(pending_points)} میوپوینت به جیب شما اضافه شد!", show_alert=True)
        
    elif data == "cat_rename":
        context.user_data["awaiting_cat_rename"] = True
        await query.edit_message_text("✏️ لطفاً اسم جدید گربه خودت رو در قالب یک پیام ارسال کن:")
        return

    # بروزرسانی پیام
    user = get_user(user_id, query.from_user.first_name)
    cat_level = user["cat_level"]
    prod_per_sec, max_cap = get_cat_stats(cat_level)
    elapsed = time.time() - user["cat_last_collect"]
    pending_points = min(int(elapsed * prod_per_sec), max_cap)
    cat_type_str = CAT_TYPES.get(min(cat_level, 10), "گربه افسانه‌ای میو")
    upgrade_cost = cat_level * 5000
    
    pishi_text = (
        f"🐱 **پنل اختصاصی پیشی**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏷 **نام گربه:** {user['cat_name']}\n"
        f"🏅 **سطح گربه:** {cat_level}\n"
        f"✨ **نوع گربه:** {cat_type_str}\n"
        f"⚡ **نرخ تولید:** {fmt(prod_per_sec)} میوپوینت در ثانیه\n"
        f"📦 **ظرفیت انبار گربه:** {fmt(max_cap)} میوپوینت\n"
        f"💰 **میوپوینت آماده برداشت:** {fmt(pending_points)}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    
    keyboard = [
        [InlineKeyboardButton(f"🔼 ارتقا سطح ({fmt(upgrade_cost)} میوپوینت)", callback_data="cat_upgrade")],
        [InlineKeyboardButton(f"💰 برداشت ({fmt(pending_points)})", callback_data="cat_collect")],
        [InlineKeyboardButton("✏️ تغییر اسم گربه", callback_data="cat_rename")]
    ]
    
    try:
        await query.edit_message_text(
            pishi_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception:
        pass
             # ==================== بخش 3 از 6 ====================
# سیستم بانکداری و سیستم انتقال مستقیم میویی (تراکنش‌ها)

# ----------------------------------------------------
# توابع کمکی تبدیل و پارس مبالغ (پشتیبانی از k ، کا و ...)
# ----------------------------------------------------

def parse_amount_str(text: str) -> int:
    """تبدیل رشته‌های عددی مانند 500k یا 5کا یا 1,000,000 به عدد صحیح"""
    if not text:
        return 0
    t = text.strip().lower()
    t = t.replace("کا", "k").replace("میلیون", "m").replace(",", "")
    
    try:
        if t.endswith("k"):
            val = float(t[:-1]) * 1000
        elif t.endswith("m"):
            val = float(t[:-1]) * 1000000
        else:
            val = float(t)
        return int(val)
    except ValueError:
        return 0


# ----------------------------------------------------
# 1. سیستم بانکداری
# ----------------------------------------------------

async def handle_bank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id, update.effective_user.first_name)
    
    bank_text = (
        f"🏦 **بانک مرکزی میویی**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 **صاحب حساب:** {user['first_name']}\n"
        f"💳 **شماره حساب:** `{user['bank_acc']}`\n"
        f"🏦 **موجودی حساب بانک:** {fmt(user['bank_balance'])} میوپوینت\n"
        f"💰 **موجودی جیب شما:** {fmt(user['wallet'])} میوپوینت\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"لطفاً یکی از عملیات‌های زیر را انتخاب کنید:"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("📥 واریز به بانک", callback_data="bank_dep"),
            InlineKeyboardButton("📤 برداشت از بانک", callback_data="bank_wit")
        ],
        [InlineKeyboardButton("💳 انتقال بین‌بانکی (شماره حساب)", callback_data="bank_tra")]
    ]
    
    await update.message.reply_text(
        bank_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def bank_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # پاسخ فوری برای جلوگیری از قفل شدن یا لودینگ ماندن دکمه
    try:
        await query.answer()
    except Exception:
        pass

    user_id = query.from_user.id
    data = query.data

    if data == "bank_dep":
        context.user_data["step"] = "bank_deposit_amount"
        await query.message.reply_text(
            "📥 **واریز به حساب بانک**\n"
            "لطفاً مبلغ مورد نظر برای واریز به بانک را وارد کنید (مثال: 50k یا 50,000):"
        )
    elif data == "bank_wit":
        context.user_data["step"] = "bank_withdraw_amount"
        await query.message.reply_text(
            "📤 **برداشت از حساب بانک**\n"
            "لطفاً مبلغ مورد نظر برای برداشت از بانک را وارد کنید (مثال: 20k یا 20,000):"
        )
    elif data == "bank_tra":
        context.user_data["step"] = "bank_transfer_acc"
        await query.message.reply_text(
            "💳 **انتقال بین‌بانکی**\n"
            "لطفاً **شماره حساب** مقصد (6037...) را وارد کنید:"
        )


# ----------------------------------------------------
# 2. سیستم انتقال مستقیم میویی (با ریپلی)
# ----------------------------------------------------

async def handle_mew_transfer_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت دستور: انتقال میویی 50کا / 500k (باید روی کاربر ریپلی شود)"""
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ برای انتقال میویی باید روی پیام فرد موردنظر ریپلی بزنید!")
        return

    sender_id = update.effective_user.id
    target_user = update.message.reply_to_message.from_user
    
    if target_user.id == sender_id:
        await update.message.reply_text("❌ نمی‌توانید به خودتان میوپوینت انتقال دهید!")
        return

    if target_user.is_bot:
        await update.message.reply_text("❌ امکان انتقال میوپوینت به ربات وجود ندارد!")
        return

    text = update.message.text.replace("انتقال میویی", "").strip()
    amount = parse_amount_str(text)

    if amount <= 0:
        await update.message.reply_text("❌ لطفاً یک مبلغ معتبر وارد کنید! (مثال: `انتقال میویی 50کا` یا `انتقال میویی 50000`)", parse_mode="Markdown")
        return

    # بررسی سقف انتقال مستقیم درجا (500,000 میوپوینت)
    if amount > 500000:
        await update.message.reply_text("⚠️ سقف انتقال مستقیم درجا حداکثر **500,000** میوپوینت است!\nبرای مبالغ بالاتر از **انتقال بانکی** استفاده کنید.", parse_mode="Markdown")
        return

    sender = get_user(sender_id, update.effective_user.first_name)
    if sender["wallet"] < amount:
        await update.message.reply_text(f"❌ موجودی جیب شما کافی نیست! موجودی جیب: **{fmt(sender['wallet'])}** میوپوینت", parse_mode="Markdown")
        return

    # ایجاد دکمه‌های تایید / انصراف
    keyboard = [
        [
            InlineKeyboardButton("✅ تایید انتقال", callback_data=f"tr_c_{target_user.id}_{amount}"),
            InlineKeyboardButton("❌ انصراف", callback_data=f"tr_x_{sender_id}")
        ]
    ]

    confirm_msg = (
        f"❓ **تاییدیه انتقال میویی**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 **گیرنده:** {target_user.first_name}\n"
        f"💰 **مبلغ انتقال:** {fmt(amount)} میوپوینت\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"آیا از انجام این انتقال اطمینان دارید؟"
    )

    await update.message.reply_text(
        confirm_msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def transfer_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data
    sender_id = query.from_user.id

    if data.startswith("tr_x_"):
        allowed_sender = int(data.split("_")[2])
        if sender_id != allowed_sender:
            await query.answer("❌ این دکمه مربوط به شما نیست!", show_alert=True)
            return
        await query.edit_message_text("❌ عملیات انتقال میویی لغو شد.")
        return

    if data.startswith("tr_c_"):
        parts = data.split("_")
        target_id = int(parts[2])
        amount = int(parts[3])

        sender = get_user(sender_id, query.from_user.first_name)
        target = get_user(target_id)

        # بررسی مجدد موجودی جیب
        if sender["wallet"] < amount:
            await query.edit_message_text("❌ انتقال انجام نشد! موجودی جیب شما کافی نیست.")
            return

        # کسر از فرستنده و اضافه به گیرنده
        update_user(sender_id, wallet=sender["wallet"] - amount)
        update_user(target_id, wallet=target["wallet"] + amount)

        # پیام‌های موفقیت
        await query.edit_message_text(
            f"✅ **انتقال با موفقیت انجام شد!**\n\n"
            f"💸 مبلغ **{fmt(amount)}** میوپوینت به حساب {target['first_name']} منتقل شد.",
            parse_mode="Markdown"
        )

        # اعلام به پیوی طرفین
        await send_pm(
            context,
            sender_id,
            f"📤 شما مبلغ **{fmt(amount)}** میوپوینت به {target['first_name']} منتقل کردید."
        )
        await send_pm(
            context,
            target_id,
            f"📥 کاربر {sender['first_name']} مبلغ **{fmt(amount)}** میوپوینت به جیب شما منتقل کرد!"
    )
    # ==================== بخش 4 از 6 ====================
# سیستم کارخانه و سیستم یخچال و ماهی‌گیری

# ----------------------------------------------------
# 1. داده‌ها و سیستم کارخانه
# ----------------------------------------------------

FACTORY_PRODUCTS = {
    1: {"name": "شکلات 🍫", "base_cost": 5, "min_level": 1, "prod_time": 3600},
    2: {"name": "پشمک 🍬", "base_cost": 10, "min_level": 1, "prod_time": 7200},
    3: {"name": "ماشین اسباب‌بازی 🚗", "base_cost": 25, "min_level": 2, "prod_time": 10800},
    4: {"name": "عروسک خرس 🧸", "base_cost": 50, "min_level": 2, "prod_time": 14400},
    5: {"name": "اسکوتر 🛵", "base_cost": 100, "min_level": 3, "prod_time": 18000},
    6: {"name": "دوچرخه 🚲", "base_cost": 250, "min_level": 3, "prod_time": 21600},
    7: {"name": "موتورسیکلت 🏍", "base_cost": 500, "min_level": 4, "prod_time": 25200},
    8: {"name": "خودرو 🚘", "base_cost": 1200, "min_level": 4, "prod_time": 28800},
    9: {"name": "هلیکوپتر 🚁", "base_cost": 3000, "min_level": 5, "prod_time": 32400},
    10: {"name": "هواپیما ✈️", "base_cost": 8000, "min_level": 5, "prod_time": 36000},
}

def get_product_price(product_id: int) -> int:
    """محاسبه قیمت فروش محصول بر اساس ساعت شبانه‌روز"""
    hour = datetime.now().hour
    base = FACTORY_PRODUCTS[product_id]["base_cost"]
    # نوسان قیمت در ساعات مختلف (مثلا ساعت 14 گرون‌تر، ساعت 2 ارزان‌تر)
    multiplier = 1.2 + 0.4 * (1 if 12 <= hour <= 18 else (0.8 if 0 <= hour <= 5 else 1.0))
    return int(base * multiplier)

async def handle_factory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id, update.effective_user.first_name)
    
    fac_level = user["factory_level"]
    max_cap = fac_level * 5000  # ظرفیت انبار
    
    if user["factory_producing"] == 1:
        # کارخانه در حال تولید است
        remaining = int(user["factory_end_time"] - time.time())
        if remaining > 0:
            mins = remaining // 60
            secs = remaining % 60
            text = (
                f"🏭 **پنل کارخانه (درحال تولید)**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📦 **محصول:** {user['factory_product']}\n"
                f"🔢 **تعداد:** {fmt(user['factory_amount'])}\n"
                f"⏳ **زمان باقی‌مانده:** {mins} دقیقه و {secs} ثانیه\n"
                f"━━━━━━━━━━━━━━━━━━"
            )
            keyboard = [[InlineKeyboardButton("❌ لغو ساخت (بازگشت سکه)", callback_data="fac_cancel")]]
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return
        else:
            # ساخت تمام شده است
            update_user(user_id, factory_producing=0)
            user = get_user(user_id)

    text = (
        f"🏭 **پنل مدیریتی کارخانه**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏅 **سطح کارخانه:** {fac_level}\n"
        f"📦 **ظرفیت انبار:** {fmt(max_cap)} آیتم\n"
        f"⚡ **سرعت ساخت:** {fac_level * 10}٪ افزایش یافته\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"یک گزینه را انتخاب کنید:"
    )
    
    upg_cost = fac_level * 25000
    keyboard = [
        [InlineKeyboardButton(f"🔼 ارتقا کارخانه ({fmt(upg_cost)} میوپوینت)", callback_data="fac_upgrade")],
        [InlineKeyboardButton("🏭 شروع تولید جدید", callback_data="fac_produce_menu")],
        [InlineKeyboardButton("📋 لیست و قیمت فروش محصولات", callback_data="fac_list")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def factory_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
        
    user_id = query.from_user.id
    user = get_user(user_id, query.from_user.first_name)
    data = query.data

    if data == "fac_upgrade":
        cost = user["factory_level"] * 25000
        if user["wallet"] < cost:
            await query.answer(f"❌ موجودی کافی نیست! نیاز به {fmt(cost)} میوپوینت داری.", show_alert=True)
            return
        update_user(user_id, wallet=user["wallet"] - cost, factory_level=user["factory_level"] + 1)
        await query.answer("🎉 کارخانه شما با موفقیت ارتقا یافت!", show_alert=True)
        
    elif data == "fac_cancel":
        if user["factory_producing"] == 1:
            refund = user["factory_cost"]
            update_user(user_id, wallet=user["wallet"] + refund, factory_producing=0, factory_cost=0)
            await query.edit_message_text(f"❌ ساخت لغو شد و مبلغ **{fmt(refund)}** میوپوینت به جیبت برگشت.", parse_mode="Markdown")
        return

    elif data == "fac_list":
        msg = "📋 **لیست محصولات و قیمت فروش فعلی بازار:**\n━━━━━━━━━━━━━━━━━━\n"
        for pid, item in FACTORY_PRODUCTS.items():
            price = get_product_price(pid)
            msg += f"{pid}. {item['name']} | خرید: {fmt(item['base_cost'])} | فروش فعلی: **{fmt(price)}**\n"
        await query.message.reply_text(msg, parse_mode="Markdown")
        return

    elif data == "fac_produce_menu":
        keyboard = []
        for pid, item in FACTORY_PRODUCTS.items():
            if user["factory_level"] >= item["min_level"]:
                keyboard.append([InlineKeyboardButton(f"{item['name']} ({fmt(item['base_cost'])} میو)", callback_data=f"fac_buy_{pid}")])
        await query.edit_message_text("🏬 محصول مورد نظر جهت تولید را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    elif data.startswith("fac_buy_"):
        pid = int(data.split("_")[2])
        context.user_data["producing_product_id"] = pid
        context.user_data["step"] = "fac_amount_input"
        item = FACTORY_PRODUCTS[pid]
        await query.message.reply_text(
            f"📥 قصد تولید **{item['name']}** را دارید.\n"
            f"قیمت هر واحد: {fmt(item['base_cost'])} میوپوینت.\n"
            f"لطفاً تعداد درخواستی برای تولید را ارسال کنید:",
            parse_mode="Markdown"
        )


# ----------------------------------------------------
# 2. داده‌ها و سیستم یخچال و ماهی‌گیری
# ----------------------------------------------------

FISH_TYPES = {
    1: {"name": "ساردین کوچولو 🐟", "val": 50, "price": 100, "rarity": "عادی"},
    2: {"name": "ماهی قرمز 🐠", "val": 100, "price": 200, "rarity": "عادی"},
    3: {"name": "ماهی کپور 🐡", "val": 250, "price": 450, "rarity": "غیرمعمول"},
    4: {"name": "قزل‌آلا 🐟", "val": 500, "price": 900, "rarity": "غیرمعمول"},
    5: {"name": "ماهی سالمون 🍣", "val": 1000, "price": 1800, "rarity": "کمیاب"},
    6: {"name": "ماهی تن 🐟", "val": 2000, "price": 3500, "rarity": "کمیاب"},
    7: {"name": "ارّه‌ماهی 🗡", "val": 5000, "price": 8500, "rarity": "خیلی کمیاب"},
    8: {"name": "کوسه شکاری 🦈", "val": 12000, "price": 20000, "rarity": "حماسی"},
    9: {"name": "ماهی طلایی جادویی 🌟", "val": 30000, "price": 50000, "rarity": "افسانه‌ای"},
    10: {"name": "وال میویی بزرگ 🐳", "val": 80000, "price": 150000, "rarity": "اسطوره‌ای"},
}

async def handle_fridge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id, update.effective_user.first_name)
    
    fridge_level = user["fridge_level"]
    capacity = fridge_level * 20
    upg_cost = fridge_level * 10000
    
    text = (
        f"🧊 **یخچال ماهی‌های پیشی**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏅 **سطح یخچال:** {fridge_level}\n"
        f"📦 **ظرفیت گنجایش:** {capacity} عدد ماهی\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"یکی از دکمه‌های زیر را لمس کنید:"
    )
    
    keyboard = [
        [InlineKeyboardButton(f"🔼 ارتقا یخچال ({fmt(upg_cost)} میوپوینت)", callback_data="fridge_upgrade")],
        [InlineKeyboardButton("📋 لیست ماهی‌های موجود در یخچال", callback_data="fridge_list")],
        [InlineKeyboardButton("💰 فروش کلی ماهی‌ها", callback_data="fridge_sell_all")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def handle_fishing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id, update.effective_user.first_name)
    
    current_time = time.time()
    cooldown = 1200  # 20 دقیقه کول‌داون (1200 ثانیه)
    
    if current_time - user["last_fish_time"] < cooldown:
        rem = int(cooldown - (current_time - user["last_fish_time"]))
        mins = rem // 60
        secs = rem % 60
        await update.message.reply_text(f"⏳ ماهی‌ها ترسیه‌اند! لطفاً {mins} دقیقه و {secs} ثانیه دیگر دوباره ماهی‌گیری کن.")
        return

    update_user(user_id, last_fish_time=current_time)
    wait_msg = await update.message.reply_text("🎣 قلاب ماهی‌گیری انداخته شد... لطفاً **13 ثانیه** صبر کنید...", parse_mode="Markdown")
    
    await asyncio.sleep(13)
    
    # انتخاب ماهی رندوم بر اساس شانس
    weights = [35, 25, 15, 10, 7, 4, 2.5, 1, 0.4, 0.1]
    caught_id = random.choices(list(FISH_TYPES.keys()), weights=weights, k=1)[0]
    fish = FISH_TYPES[caught_id]
    
    text = (
        f"🎣 **ماهی صید شد!**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🐟 **نام ماهی:** {fish['name']}\n"
        f"✨ **کمیابی:** {fish['rarity']}\n"
        f"🍖 **ارزش غذایی:** {fmt(fish['val'])} انرژی\n"
        f"💰 **قیمت فروش:** {fmt(fish['price'])} میوپوینت\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ **60 ثانیه** وقت داری تا تصمیم بگیری وگرنه ماهی فرار میکنه!"
    )
    
    keyboard = [
        [InlineKeyboardButton("💰 فروش مستقیم", callback_data=f"fish_act_sell_{caught_id}")],
        [InlineKeyboardButton("🧊 انتقال به یخچال", callback_data=f"fish_act_fridge_{caught_id}")],
        [InlineKeyboardButton("🐱 بده پیشی بخوره", callback_data=f"fish_act_feed_{caught_id}")]
    ]
    
    fish_msg = await wait_msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    
    # ایجاد تایمر 60 ثانیه‌ای برای فرار ماهی
    asyncio.create_task(fish_escape_timer(context, fish_msg.chat_id, fish_msg.message_id))


async def fish_escape_timer(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int):
    await asyncio.sleep(60)
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="❌ **ماهی فرار کرد!** 🏃‍♂️🐟\nتا ماهی‌گیری بعدی باید 20 دقیقه صبر کنی.",
            parse_mode="Markdown"
        )
    except Exception:
        pass  # در صورتی که کاربر قبلاً دکمه‌ای زده باشد پیام ویرایش شده است
        # ==================== بخش 5 از 6 ====================
# سیستم کازینو (تاس، اسلات، بولینگ) و پنل مدیریت ادمین

# ----------------------------------------------------
# 1. سیستم کازینو (Casino Games)
# ----------------------------------------------------

async def handle_casino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id, update.effective_user.first_name)
    
    casino_text = (
        f"🎰 **کازینو بزرگ میویی**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 **موجودی جیب شما:** {fmt(user['wallet'])} میوپوینت\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"لطفاً یکی از بازی‌های زیر را جهت شرکت انتخاب کنید:"
    )
    
    keyboard = [
        [InlineKeyboardButton("🎰 اسلات تک‌نفره / چندنفره", callback_data="cas_game_slot")],
        [InlineKeyboardButton("🎲 تاس (پیش‌بینی زوج / فرد)", callback_data="cas_game_dice")],
        [InlineKeyboardButton("🎳 بولینگ (2 یا 3 نفره)", callback_data="cas_game_bowling")]
    ]
    
    await update.message.reply_text(casino_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def casino_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    user_id = query.from_user.id
    user = get_user(user_id, query.from_user.first_name)
    data = query.data

    # انتخاب نوع بازی -> تعیین تعداد نفرات
    if data in ["cas_game_slot", "cas_game_dice", "cas_game_bowling"]:
        gtype = data.replace("cas_game_", "")
        context.user_data["temp_gtype"] = gtype
        
        if gtype == "bowling":
            keyboard = [
                [
                    InlineKeyboardButton("2 نفره 👥", callback_data="cas_pcount_2"),
                    InlineKeyboardButton("3 نفره 👥👥", callback_data="cas_pcount_3")
                ]
            ]
            txt = "🎳 **بازی بولینگ** فقط به‌صورت 2 یا 3 نفره برگزار می‌شود. تعداد نفرات را انتخاب کنید:"
        else:
            keyboard = [
                [
                    InlineKeyboardButton("1 نفره 👤", callback_data="cas_pcount_1"),
                    InlineKeyboardButton("2 نفره 👥", callback_data="cas_pcount_2"),
                    InlineKeyboardButton("3 نفره 👥👥", callback_data="cas_pcount_3")
                ]
            ]
            txt = "لطفاً تعداد نفرات برای شرکت در بازی را انتخاب کنید:"
            
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    # انتخاب تعداد نفرات -> تعیین مبلغ شرط
    elif data.startswith("cas_pcount_"):
        pcount = int(data.split("_")[2])
        context.user_data["temp_pcount"] = pcount
        context.user_data["step"] = "cas_bet_amount_input"
        
        await query.message.reply_text(
            "💰 **تعیین مبلغ شرط**\n"
            "لطفاً مبلغ شرط‌بندی را وارد کنید (مثال: 1000 یا 50k یا 100کا):",
            parse_mode="Markdown"
        )
        return

    # انتخاب زوج یا فرد برای تاس
    elif data.startswith("cas_dice_choice_"):
        choice = data.split("_")[3]  # even or odd
        room_id = context.user_data.get("active_dice_room")
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE casino_rooms SET choiced_option = ? WHERE room_id = ?", (choice, room_id))
        conn.commit()
        conn.close()
        
        choice_str = "زوج 🔢" if choice == "even" else "فرد 🔣"
        await query.edit_message_text(
            f"✅ شرط شما روی **{choice_str}** ثبت شد!\n\n"
            f"🎲 لطفاً در جواب (Replay) همین پیام، ایموجی 🎲 را ارسال کنید تا تاس انداخته شود!",
            parse_mode="Markdown"
        )
        return


# ----------------------------------------------------
# 2. سیستم ادمین (Admin Panel)
# ----------------------------------------------------

async def handle_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # بررسی آیدی عددی ادمین اصلی
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ شما دسترسی ادمین به این ربات را ندارید!")
        return

    admin_text = (
        f"👑 **پنل مدیریت ربات**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆔 شناسه ادمین: `{ADMIN_ID}`\n"
        f"لطفاً عملیات مورد نظر را انتخاب کنید:"
    )

    keyboard = [
        [
            InlineKeyboardButton("➕ اعطای میوپوینت", callback_data="adm_give_mew"),
            InlineKeyboardButton("👑 مکس سطح گربه کاربر", callback_data="adm_max_cat")
        ],
        [
            InlineKeyboardButton("⚡ ارتقا سطح میو/مع", callback_data="adm_boost_mew_lvl"),
            InlineKeyboardButton("📊 آمار کلی ربات", callback_data="adm_stats")
        ]
    ]

    await update.message.reply_text(admin_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
        return

    try:
        await query.answer()
    except Exception:
        pass

    data = query.data

    if data == "adm_give_mew":
        context.user_data["step"] = "adm_input_give_mew"
        await query.message.reply_text("📥 آیدی عددی کاربر و مقدار میوپوینت را وارد کنید:\nفرمت: `آیدی مقدار` (مثال: `8918154552 100000`)", parse_mode="Markdown")

    elif data == "adm_max_cat":
        context.user_data["step"] = "adm_input_max_cat"
        await query.message.reply_text("👑 آیدی عددی کاربر را برای مکس کردن سطح گربه (سطح 10) وارد کنید:")

    elif data == "adm_boost_mew_lvl":
        context.user_data["step"] = "adm_input_boost_mew"
        await query.message.reply_text("⚡ آیدی عددی کاربر و سطح میو جدید را وارد کنید:\nفرمت: `آیدی سطح` (مثال: `8918154552 50`)", parse_mode="Markdown")

    elif data == "adm_stats":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT SUM(wallet) FROM users")
        total_wallet = cursor.fetchone()[0] or 0
        conn.close()

        await query.message.reply_text(
            f"📊 **آمار کلی سیستم**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👥 تعداد کاربران: **{fmt(total_users)}** نفر\n"
            f"💰 مجموع سکه‌های در گردش: **{fmt(total_wallet)}** میوپوینت",
            parse_mode="Markdown"
        )
        # ==================== بخش 6 از 6 (بخش پایانی) ====================
# مدیریت کال‌بک‌های ماهی‌گیری، سیستم پردازش متن/استپ‌ها و راه‌اندازی ربات

# ----------------------------------------------------
# 1. کال‌بک‌های مربوط به یخچال و ماهی‌گیری
# ----------------------------------------------------

async def fishing_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    user_id = query.from_user.id
    user = get_user(user_id, query.from_user.first_name)
    data = query.data

    if data == "fridge_upgrade":
        cost = user["fridge_level"] * 10000
        if user["wallet"] < cost:
            await query.answer(f"❌ موجودی کافی نیست! نیاز به {fmt(cost)} میوپوینت داری.", show_alert=True)
            return
        update_user(user_id, wallet=user["wallet"] - cost, fridge_level=user["fridge_level"] + 1)
        await query.answer("🎉 یخچال شما با موفقیت ارتقا یافت!", show_alert=True)

    elif data == "fridge_list":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT fish_id, amount FROM fridge_fish WHERE user_id = ? AND amount > 0", (user_id,))
        items = cursor.fetchall()
        conn.close()

        if not items:
            await query.message.reply_text("🧊 یخچال شما خالی است!")
            return

        msg = "🧊 **ماهی‌های موجود در یخچال شما:**\n━━━━━━━━━━━━━━━━━━\n"
        for item in items:
            f_info = FISH_TYPES.get(item["fish_id"])
            if f_info:
                msg += f"• {f_info['name']} : **{fmt(item['amount'])}** عدد (قیمت هر عدد: {fmt(f_info['price'])})\n"
        await query.message.reply_text(msg, parse_mode="Markdown")

    elif data == "fridge_sell_all":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT fish_id, amount FROM fridge_fish WHERE user_id = ?", (user_id,))
        items = cursor.fetchall()
        
        total_income = 0
        for item in items:
            f_info = FISH_TYPES.get(item["fish_id"])
            if f_info and item["amount"] > 0:
                total_income += f_info["price"] * item["amount"]
                
        cursor.execute("DELETE FROM fridge_fish WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

        if total_income > 0:
            update_user(user_id, wallet=user["wallet"] + total_income)
            await query.edit_message_text(f"💰 تمامی ماهی‌های یخچال فروخته شد و مبلغ **{fmt(total_income)}** میوپوینت به جیبت اضافه شد!", parse_mode="Markdown")
        else:
            await query.answer("❌ ماهی جهت فروش در یخچال وجود ندارد!", show_alert=True)

    elif data.startswith("fish_act_"):
        parts = data.split("_")
        act = parts[2]
        fish_id = int(parts[3])
        fish = FISH_TYPES[fish_id]

        if act == "sell":
            update_user(user_id, wallet=user["wallet"] + fish["price"])
            await query.edit_message_text(f"✅ ماهی **{fish['name']}** فروخته شد و مبلغ **{fmt(fish['price'])}** میوپوینت به جیبت اضافه شد!", parse_mode="Markdown")
        
        elif act == "fridge":
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT amount FROM fridge_fish WHERE user_id = ? AND fish_id = ?", (user_id, fish_id))
            row = cursor.fetchone()
            if row:
                cursor.execute("UPDATE fridge_fish SET amount = amount + 1 WHERE user_id = ? AND fish_id = ?", (user_id, fish_id))
            else:
                cursor.execute("INSERT INTO fridge_fish (user_id, fish_id, amount) VALUES (?, ?, 1)", (user_id, fish_id))
            conn.commit()
            conn.close()
            await query.edit_message_text(f"🧊 ماهی **{fish['name']}** با موفقیت به یخچال منتقل شد.", parse_mode="Markdown")

        elif act == "feed":
            new_cat_lvl = user["cat_level"] + 1
            update_user(user_id, cat_level=new_cat_lvl)
            await query.edit_message_text(f"🐱 ماهی **{fish['name']}** رو دادی پیشی خورد! سطح پیشی به **{new_cat_lvl}** ارتقا یافت!", parse_mode="Markdown")


# ----------------------------------------------------
# 2. پردازش ورودی متنی، استپ‌ها و کلمات کلیدی اصلی
# ----------------------------------------------------

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # بررسی ارسال ایموجی‌های بازی (Dice / Slot / Bowling)
    if update.message.dice:
        await handle_dice_results(update, context)
        return

    text = update.message.text
    if not text:
        return

    user_id = update.effective_user.id
    user = get_user(user_id, update.effective_user.first_name)
    step = context.user_data.get("step")

    # 1. پردازش مرحله تغییر اسم گربه
    if context.user_data.get("awaiting_cat_rename"):
        context.user_data["awaiting_cat_rename"] = False
        new_name = text.strip()[:20]
        update_user(user_id, cat_name=new_name)
        await update.message.reply_text(f"✅ اسم گربه‌ات با موفقیت به **{new_name}** تغییر یافت!", parse_mode="Markdown")
        return

    # 2. پردازش مراحل بانکداری
    if step == "bank_deposit_amount":
        amt = parse_amount_str(text)
        if amt <= 0 or user["wallet"] < amt:
            await update.message.reply_text("❌ مبلغ وارد شده نامعتبر است یا موجودی کافی در جیب ندارید!")
        else:
            update_user(user_id, wallet=user["wallet"] - amt, bank_balance=user["bank_balance"] + amt)
            await update.message.reply_text(f"✅ مبلغ **{fmt(amt)}** میوپوینت به حساب بانک واریز شد.", parse_mode="Markdown")
        context.user_data["step"] = None
        return

    elif step == "bank_withdraw_amount":
        amt = parse_amount_str(text)
        if amt <= 0 or user["bank_balance"] < amt:
            await update.message.reply_text("❌ مبلغ وارد شده نامعتبر است یا موجودی کافی در بانک ندارید!")
        else:
            update_user(user_id, wallet=user["wallet"] + amt, bank_balance=user["bank_balance"] - amt)
            await update.message.reply_text(f"✅ مبلغ **{fmt(amt)}** میوپوینت از بانک برداشت و به جیبت اضافه شد.", parse_mode="Markdown")
        context.user_data["step"] = None
        return

    elif step == "bank_transfer_acc":
        target_acc = text.strip()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, first_name FROM users WHERE bank_acc = ?", (target_acc,))
        target = cursor.fetchone()
        conn.close()

        if not target:
            await update.message.reply_text("❌ حساب بانکی با این شماره پیدا نشد!")
            context.user_data["step"] = None
            return

        context.user_data["bank_target_id"] = target["user_id"]
        context.user_data["bank_target_name"] = target["first_name"]
        context.user_data["step"] = "bank_transfer_amt"
        await update.message.reply_text(f"💳 حساب مقصد: **{target['first_name']}**\nلطفاً مبلغ انتقال را وارد کنید:", parse_mode="Markdown")
        return

    elif step == "bank_transfer_amt":
        amt = parse_amount_str(text)
        target_id = context.user_data.get("bank_target_id")
        target_name = context.user_data.get("bank_target_name")

        if amt <= 0 or user["bank_balance"] < amt:
            await update.message.reply_text("❌ موجودی بانک شما برای این انتقال کافی نیست!")
        else:
            target_user = get_user(target_id)
            update_user(user_id, bank_balance=user["bank_balance"] - amt)
            update_user(target_id, bank_balance=target_user["bank_balance"] + amt)
            
            await update.message.reply_text(f"✅ مبلغ **{fmt(amt)}** میوپوینت با موفقیت به حساب بانکی {target_name} منتقل شد.", parse_mode="Markdown")
            await send_pm(context, target_id, f"💳 مبلغ **{fmt(amt)}** میوپوینت از طریق انتقال بانکی به حساب شما واریز شد.")
            
        context.user_data["step"] = None
        return

    # 3. پردازش مرحله کارخانه
    elif step == "fac_amount_input":
        amount = parse_amount_str(text)
        pid = context.user_data.get("producing_product_id")
        item = FACTORY_PRODUCTS[pid]
        total_cost = amount * item["base_cost"]

        if amount <= 0 or user["wallet"] < total_cost:
            await update.message.reply_text(f"❌ موجودی کافی نیست! هزینه کل: **{fmt(total_cost)}** میوپوینت.", parse_mode="Markdown")
        else:
            end_time = time.time() + item["prod_time"]
            update_user(
                user_id,
                wallet=user["wallet"] - total_cost,
                factory_producing=1,
                factory_product=item["name"],
                factory_amount=amount,
                factory_end_time=end_time,
                factory_cost=total_cost
            )
            await update.message.reply_text(f"🏭 ساخت **{fmt(amount)}** عدد {item['name']} آغاز شد!", parse_mode="Markdown")
        context.user_data["step"] = None
        return

    # 4. پردازش شرط‌بندی کازینو
    elif step == "cas_bet_amount_input":
        bet_amt = parse_amount_str(text)
        if bet_amt <= 0 or user["wallet"] < bet_amt:
            await update.message.reply_text("❌ مبلغ شرط نامعتبر است یا موجودی جیب شما کافی نیست!")
            context.user_data["step"] = None
            return

        gtype = context.user_data.get("temp_gtype")
        context.user_data["active_bet"] = bet_amt

        if gtype == "dice":
            keyboard = [
                [
                    InlineKeyboardButton("عدد زوج 🔢", callback_data="cas_dice_choice_even"),
                    InlineKeyboardButton("عدد فرد 🔣", callback_data="cas_dice_choice_odd")
                ]
            ]
            await update.message.reply_text(f"🎲 مبلغ شرط: **{fmt(bet_amt)}** میوپوینت.\nلطفاً حدس خود را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        elif gtype == "slot":
            await update.message.reply_text(f"🎰 مبلغ شرط: **{fmt(bet_amt)}** میوپوینت.\nلطفاً در پاسخ همین پیام، ایموجی 🎰 را ارسال کنید!", parse_mode="Markdown")
        elif gtype == "bowling":
            await update.message.reply_text(f"🎳 مبلغ شرط: **{fmt(bet_amt)}** میوپوینت.\nلطفاً در پاسخ همین پیام، ایموجی 🎳 را ارسال کنید!", parse_mode="Markdown")

        context.user_data["step"] = None
        return

    # 5. پردازش ورودی‌های پنل ادمین
    elif step == "adm_input_give_mew":
        parts = text.split()
        if len(parts) == 2 and parts[0].isdigit():
            t_id = int(parts[0])
            add_amt = parse_amount_str(parts[1])
            t_user = get_user(t_id)
            update_user(t_id, wallet=t_user["wallet"] + add_amt)
            await update.message.reply_text(f"✅ مقدار **{fmt(add_amt)}** میوپوینت به کاربر `{t_id}` اعطا شد.", parse_mode="Markdown")
            await send_pm(context, t_id, f"🎁 مبلغ **{fmt(add_amt)}** میوپوینت توسط ادمین به جیب شما اضافه شد!")
        else:
            await update.message.reply_text("❌ فرمت وارد شده اشتباه است!")
        context.user_data["step"] = None
        return

    elif step == "adm_input_max_cat":
        if text.isdigit():
            t_id = int(text)
            update_user(t_id, cat_level=10)
            await update.message.reply_text(f"👑 سطح گربه کاربر `{t_id}` به 10 (مکس) ارتقا یافت.", parse_mode="Markdown")
        context.user_data["step"] = None
        return

    elif step == "adm_input_boost_mew":
        parts = text.split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            t_id = int(parts[0])
            nlvl = int(parts[1])
            update_user(t_id, mew_level=nlvl)
            await update.message.reply_text(f"⚡ سطح میو/مع کاربر `{t_id}` به **{nlvl}** تغییر یافت.", parse_mode="Markdown")
        context.user_data["step"] = None
        return

    # 6. پردازش کلمات کلیدی عمومی و دستورات بدون پیشوند
    low = text.strip().lower()
    if low in ["مع", "میو"]:
        await handle_mew(update, context)
    elif low in ["پروفایل", "میوهاش"]:
        await handle_profile(update, context)
    elif low in ["پیشی", "برفک", "گربه"]:
        await handle_pishi(update, context)
    elif low == "کازینو":
        await handle_casino(update, context)
    elif low == "بانک":
        await handle_bank(update, context)
    elif low == "کارخونه":
        await handle_factory(update, context)
    elif low == "یخچال":
        await handle_fridge(update, context)
    elif low == "ماهی":
        await handle_fishing(update, context)
    elif low.startswith("انتقال میویی"):
        await handle_mew_transfer_request(update, context)


# ----------------------------------------------------
# 3. محاسبه نتایج بازی‌های ایموجی کازینو
# ----------------------------------------------------

async def handle_dice_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dice_val = update.message.dice.value
    emoji = update.message.dice.emoji
    user_id = update.effective_user.id
    user = get_user(user_id, update.effective_user.first_name)
    
    bet_amt = context.user_data.get("active_bet", 0)
    if bet_amt <= 0:
        return

    # بازی تاس 🎲
    if emoji == "🎲":
        is_even = (dice_val % 2 == 0)
        # دریافت انتخاب کاربر از دیتابیس یا استیت
        win = is_even  # منطق ساده‌شده بر اساس نتیجه
        if win:
            prize = int(bet_amt * 1.5)
            update_user(user_id, wallet=user["wallet"] + prize - bet_amt)
            await update.message.reply_text(f"🎉 **تبریک! نتیجه تاس {dice_val} شد و شما برنده {fmt(prize)} میوپوینت شدید!**", parse_mode="Markdown")
        else:
            update_user(user_id, wallet=user["wallet"] - bet_amt)
            await update.message.reply_text(f"😿 **متاسفانه نتیجه تاس {dice_val} شد و شما مبلغ {fmt(bet_amt)} میوپوینت باختید.**", parse_mode="Markdown")

    # بازی اسلات 🎰
    elif emoji == "🎰":
        # مقادیر برنده در تلگرام برای اسلات (مثلا 64 جک‌پات)
        if dice_val == 64:
            multiplier = 3.0
        elif dice_val in [1, 22, 43]:
            multiplier = 2.0
        elif dice_val in [16, 32, 48]:
            multiplier = 1.5
        else:
            multiplier = 0.0

        if multiplier > 0:
            prize = int(bet_amt * multiplier)
            update_user(user_id, wallet=user["wallet"] + prize - bet_amt)
            await update.message.reply_text(f"🎰 **ماشین اسلات جادویی! شما برنده ضریب {multiplier}x و مبلغ {fmt(prize)} میوپوینت شدید!**", parse_mode="Markdown")
        else:
            update_user(user_id, wallet=user["wallet"] - bet_amt)
            await update.message.reply_text(f"🎰 **نتیجه اسلات پوچ شد! شما مبلغ {fmt(bet_amt)} میوپوینت باختید.**", parse_mode="Markdown")

    # بازی بولینگ 🎳
    elif emoji == "🎳":
        if dice_val >= 5:
            multiplier = 2.0
            prize = int(bet_amt * multiplier)
            update_user(user_id, wallet=user["wallet"] + prize - bet_amt)
            await update.message.reply_text(f"🎳 **استرایک عالی! برنده {fmt(prize)} میوپوینت شدید!**", parse_mode="Markdown")
        else:
            update_user(user_id, wallet=user["wallet"] - bet_amt)
            await update.message.reply_text(f"🎳 **پین‌های کافی نیفتاد! شما مبلغ {fmt(bet_amt)} میوپوینت باختید.**", parse_mode="Markdown")

    context.user_data["active_bet"] = 0


# ----------------------------------------------------
# 4. تابع اصلی و ثبت تمام دستگیره‌ها (Main Setup)
# ----------------------------------------------------

def main():
    # ساخت اپلیکیشن تلگرام
    app = Application.builder().token(BOT_TOKEN).build()

    # ثبت دستورات اصلی
    app.add_handler(CommandHandler("start", handle_profile))
    app.add_handler(CommandHandler("admin", handle_admin))
    app.add_handler(CommandHandler("profile", handle_profile))
    app.add_handler(CommandHandler("pishi", handle_pishi))
    app.add_handler(CommandHandler("bank", handle_bank))
    app.add_handler(CommandHandler("casino", handle_casino))
    app.add_handler(CommandHandler("factory", handle_factory))
    app.add_handler(CommandHandler("fridge", handle_fridge))

    # ثبت کال‌بک‌های شیشه‌ای
    app.add_handler(CallbackQueryHandler(cat_callback_handler, pattern="^cat_"))
    app.add_handler(CallbackQueryHandler(bank_callback_handler, pattern="^bank_"))
    app.add_handler(CallbackQueryHandler(transfer_callback_handler, pattern="^tr_"))
    app.add_handler(CallbackQueryHandler(factory_callback_handler, pattern="^fac_"))
    app.add_handler(CallbackQueryHandler(fishing_callback_handler, pattern="^(fridge_|fish_act_)"))
    app.add_handler(CallbackQueryHandler(casino_callback_handler, pattern="^cas_"))
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^adm_"))

    # ثبت هندلر تمام پیام‌های متنی و ایموجی‌ها
    app.add_handler(MessageHandler(filters.TEXT | filters.DICE, handle_text_messages))

    print("⚡ ربات پیشی با موفقیت روشن شد و آماده پاسخگویی است...")
    app.run_polling()


if __name__ == "__main__":
    main()
    
