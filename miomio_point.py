# ==================================================
# 🟢 بخش ۱-الف: کتابخانه‌ها، تنظیمات اولیه و داده‌های بازی
# ==================================================

import asyncio
import logging
import math
import random
import sqlite3
import time
from typing import Dict, Any, Optional

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
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

# --------------------------------------------------
# ⚙️ تنظیمات اصلی و ثابت‌های ربات
# --------------------------------------------------
TOKEN = "8971798729:AAGY8Hw8osbpHdglddpckGSnDUgIR8bywfw"  # توکن ربات تلگرام خود را وارد کنید
ADMIN_ID = 8918154552            # آیدی عددی ادمین اصلی

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --------------------------------------------------
# 🐟 داده‌های ماهی‌گیری (قیمت و انرژی)
# --------------------------------------------------
FISH_DATA = {
    "🐟": {"name": "ماهی معمولی", "price": 100, "food": 10, "chance": 0.50},
    "🐠": {"name": "ماهی گرمسیری", "price": 250, "food": 20, "chance": 0.25},
    "🐡": {"name": "بادکنک ماهی", "price": 500, "food": 35, "chance": 0.15},
    "🦈": {"name": "کوسه طلایی", "price": 1500, "food": 60, "chance": 0.08},
    "🐋": {"name": "نهنگ افسانه‌ای", "price": 5000, "food": 100, "chance": 0.02},
}

# --------------------------------------------------
# 🏭 داده‌های محصولات کارخانه
# --------------------------------------------------
PRODUCTS = {
    "milk": {"name": "شیر گرم", "cost": 1000, "time": 60, "base_sell": 1500},
    "cookie": {"name": "بیسکویت ماهی", "cost": 5000, "time": 300, "base_sell": 8000},
    "toy": {"name": "اسباب‌بازی کاموایی", "cost": 20000, "time": 900, "base_sell": 35000},
    "house": {"name": "خانه گربه", "cost": 100000, "time": 3600, "base_sell": 180000},
}
# ==================================================
# 🟢 بخش ۱-ب: دیتابیس و توابع کمکی اصلی
# ==================================================

def init_db():
    """ایجاد دیتابیس و جدول‌های مورد نیاز با تمامی ستون‌های لازم"""
    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()

    # جدول اصلی کاربران
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            wallet REAL DEFAULT 0,
            bank REAL DEFAULT 0,
            cat_name TEXT DEFAULT 'پیشی',
            cat_level INTEGER DEFAULT 1,
            cat_food INTEGER DEFAULT 100,
            cat_last_feed REAL DEFAULT 0,
            cat_last_claim REAL DEFAULT 0,
            meow_count INTEGER DEFAULT 0,
            user_level INTEGER DEFAULT 1,
            last_meow_time REAL DEFAULT 0,
            producing_item TEXT DEFAULT NULL,
            produce_amount INTEGER DEFAULT 0,
            produce_start_time REAL DEFAULT 0,
            produce_cost REAL DEFAULT 0
        )
    """)

    # جدول یخچال (انبار ماهی‌ها)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fridge (
            user_id INTEGER,
            fish_type TEXT,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, fish_type)
        )
    """)

    # بررسی و اضافه کردن ستون‌های جدید در صورت بروزرسانی دیتابیس‌های قدیمی
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if "user_level" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN user_level INTEGER DEFAULT 1")
    if "meow_count" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN meow_count INTEGER DEFAULT 0")
    if "cat_name" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN cat_name TEXT DEFAULT 'پیشی'")

    conn.commit()
    conn.close()

# اجرای اتوماتیک ساخت دیتابیس هنگام لود سورس
init_db()


def get_user(user_id: int):
    """دریافت اطلاعات کاربر یا ثبت‌نام کاربر جدید در صورت عدم وجود"""
    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        now = time.time()
        cursor.execute(
            "INSERT INTO users (user_id, wallet, bank, cat_name, cat_level, cat_food, cat_last_feed, cat_last_claim, meow_count, user_level, last_meow_time) "
            "VALUES (?, 500, 0, 'پیشی', 1, 100, ?, ?, 0, 1, 0)",
            (user_id, now, now)
        )
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()

    conn.close()
    return user


def parse_amount(text: str) -> float:
    """تبدیل فرمت‌های k ،m یا اعداد معمولی به عدد"""
    text = text.lower().strip()
    if text.endswith('k'):
        return float(text[:-1]) * 1000
    elif text.endswith('m'):
        return float(text[:-1]) * 1000000
    return float(text)


def calculate_dynamic_sell_price(base_sell: float) -> float:
    """محاسبه قیمت فروش شناور بر اساس نوسان بازار"""
    multiplier = random.uniform(0.85, 1.25)
    return round(base_sell * multiplier)


async def send_pv_notify(context: ContextTypes.DEFAULT_TYPE, target_id: int, message: str):
    """ارسال اعلان پی‌وی به کاربر"""
    try:
        await context.bot.send_message(chat_id=target_id, text=message, parse_mode="Markdown")
    except Exception:
        pass
# ==================================================
# 🟢 بخش ۲-الف: سیستم میو/مع، ارتقای لول کاربر و پروفایل
# ==================================================

async def meow_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش ارسال میو/مع، اعطای پاداش و محاسبه خودکار لول کاربر"""
    user_id = update.effective_user.id
    user = get_user(user_id)

    # استخراج مقادیر از دیتابیس (بر اساس اندیس‌های بخش ۱)
    current_wallet = user[1]
    meow_count = user[8]
    user_level = user[9]
    last_meow_time = user[10]

    now = time.time()
    # بررسی کول‌داون (مثلاً ۳ ثانیه فاصله بین هر میو)
    if now - last_meow_time < 3:
        remaining = int(3 - (now - last_meow_time))
        await update.message.reply_text(f"⏱️ آروم‌تر پیشی! {remaining} ثانیه دیگه دوباره میو کن.")
        return

    # پاداش پایه هر میو/مع
    reward = random.randint(10, 30) * user_level
    new_meow_count = meow_count + 1
    new_wallet = current_wallet + reward

    # فرمول ارتقای خودکار لول کاربر (هر ۱۰ میو = ۱ لول جدید)
    # می‌توانید فرمول دلخواه خود را جایگزین کنید: math.isqrt(new_meow_count) + 1
    new_user_level = (new_meow_count // 10) + 1
    is_level_up = new_user_level > user_level

    # بروزرسانی دیتابیس
    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE users 
           SET wallet = ?, meow_count = ?, user_level = ?, last_meow_time = ? 
           WHERE user_id = ?""",
        (new_wallet, new_meow_count, new_user_level, now, user_id)
    )
    conn.commit()
    conn.close()

    # ارسال پاسخ به کاربر
    msg = f"🐾 **میووو!** شما **{reward:,}** میوپوینت دریافت کردید.\n"
    msg += f"📊 تعداد کل میو/مع: **{new_meow_count:,}**\n"

    if is_level_up:
        msg += f"\n🎉 **تبریک! لول عمومی شما به {new_user_level} ارتقا یافت!** 🚀"

    await update.message.reply_text(msg, parse_mode="Markdown")


async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش کامل پروفایل کاربر، موجودی‌ها و سطح‌ها"""
    user_id = update.effective_user.id
    user = get_user(user_id)

    wallet = user[1]
    bank = user[2]
    cat_name = user[3]
    cat_level = user[4]
    meow_count = user[8]
    user_level = user[9]

    first_name = update.effective_user.first_name

    profile_text = (
        f"👤 **پروفایل کاربری {first_name}**\n"
        f"🆔 آیدی عددی: `{user_id}`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⭐ **لول عمومی (میو/مع):** `{user_level}`\n"
        f"🐾 **تعداد کل میوها:** `{meow_count:,}`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 **کیف پول:** `{int(wallet):,}` میوپوینت\n"
        f"🏦 **بانک:** `{int(bank):,}` میوپوینت\n"
        f"💳 **مجموع دارایی:** `{int(wallet + bank):,}` میوپوینت\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🐱 **نام پیشی:** {cat_name}\n"
        f"📈 **سطح پیشی:** `{cat_level}`"
    )

    await update.message.reply_text(profile_text, parse_mode="Markdown")
        # ==================================================
# 🟢 بخش ۲-ب: داشبورد پیشی و ورودی‌های متنی اختصاصی
# ==================================================

async def cat_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش پنل مدیریت پیشی همراه با دکمه‌های شیشه‌ای"""
    user_id = update.effective_user.id
    user = get_user(user_id)

    wallet = user[1]
    cat_name = user[3]
    cat_level = user[4]
    cat_food = user[5]
    cat_last_claim = user[7]

    # محاسبه میوپوینت تولید شده توسط پیشی (هر سطح = ۲ میو در ثانیه)
    mps = cat_level * 2
    now = time.time()
    produced = int((now - cat_last_claim) * mps) if cat_last_claim > 0 else 0
    upgrade_cost = cat_level * 500

    text = (
        f"🐱 **داشبورد اختصاصی {cat_name}**\n\n"
        f"🏷️ **نام:** {cat_name}\n"
        f"⭐ **سطح گربه:** `{cat_level}`\n"
        f"🍖 **میزان سیر بودن:** `{cat_food}%`\n"
        f"⚡ **نرخ تولید:** `{mps}` میوپوینت در ثانیه\n"
        f"💰 **آماده برداشت:** `{produced:,}` میوپوینت\n\n"
        f"🪙 **هزینه ارتقای سطح گربه:** `{upgrade_cost:,}` میوپوینت"
    )

    buttons = [
        [
            InlineKeyboardButton("💰 برداشت میوپوینت", callback_data="cat_claim"),
            InlineKeyboardButton("🚀 ارتقای سطح گربه", callback_data="cat_upgrade")
        ],
        [
            InlineKeyboardButton("✍️ تغییر نام پیشی", callback_data="cat_change_name")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")


async def custom_text_inputs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دریافت ورودی‌های متنی مانند تغییر اسم گربه و شرط‌های دلخواه کازینو"""
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    text = update.message.text.strip()

    # ۱. دریافت نام جدید گربه
    if context.user_data.get('waiting_for_cat_name'):
        if len(text) > 30:
            await update.message.reply_text("❌ نام پیشی نمی‌تواند بیشتر از ۳۰ کاراکتر باشد.")
            return

        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET cat_name = ? WHERE user_id = ?", (text, user_id))
        conn.commit()
        conn.close()

        context.user_data.pop('waiting_for_cat_name', None)
        await update.message.reply_text(f"✅ نام پیشی شما با موفقیت به **{text}** تغییر یافت!", parse_mode="Markdown")
        return

    # ۲. دریافت مبلغ دلخواه کازینو
    if 'casino_custom' in context.user_data:
        try:
            bet_amount = parse_amount(text)
            user = get_user(user_id)

            if bet_amount <= 0:
                await update.message.reply_text("❌ مبلغ شرط باید بیشتر از ۰ باشد.")
                return

            if user[1] < bet_amount:
                await update.message.reply_text(f"❌ موجودی کافی نیست! موجودی کیف پول: {int(user[1]):,} میو")
                return

            c_data = context.user_data.pop('casino_custom')
            game_type = c_data['game_type']
            players = c_data['players']

            if game_type == "dice":
                buttons = [
                    [
                        InlineKeyboardButton("🔵 زوج (x1.5)", callback_data=f"casino_start_dice_{players}_{bet_amount}_even"),
                        InlineKeyboardButton("🔴 فرد (x1.5)", callback_data=f"casino_start_dice_{players}_{bet_amount}_odd")
                    ],
                    [
                        InlineKeyboardButton("🎯 ۱ (x2)", callback_data=f"casino_start_dice_{players}_{bet_amount}_1"),
                        InlineKeyboardButton("🎯 ۲ (x2)", callback_data=f"casino_start_dice_{players}_{bet_amount}_2"),
                        InlineKeyboardButton("🎯 ۳ (x2)", callback_data=f"casino_start_dice_{players}_{bet_amount}_3")
                    ],
                    [
                        InlineKeyboardButton("🎯 ۴ (x2)", callback_data=f"casino_start_dice_{players}_{bet_amount}_4"),
                        InlineKeyboardButton("🎯 ۵ (x2)", callback_data=f"casino_start_dice_{players}_{bet_amount}_5"),
                        InlineKeyboardButton("🎯 ۶ (x2)", callback_data=f"casino_start_dice_{players}_{bet_amount}_6")
                    ]
                ]
                await update.message.reply_text(
                    f"🎲 شرط دلخواه **{int(bet_amount):,}** میو ثبت شد.\nپیش‌بینی خود را انتخاب کنید:",
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode="Markdown"
                )
            else:
                conn = sqlite3.connect("meow_point.db")
                conn.cursor().execute("UPDATE users SET wallet = wallet - ? WHERE user_id = ?", (bet_amount, user_id))
                conn.commit()
                conn.close()

                context.user_data['pending_casino_game'] = {'type': game_type, 'bet': bet_amount, 'prediction': None}
                emoji_icon = {"slot": "🎰", "bowling": "🎳"}.get(game_type)
                await update.message.reply_text(
                    f"✅ شرط شما به مبلغ **{int(bet_amount):,}** میوپوینت ثبت شد.\n\n"
                    f"👇 **لطفاً ایموجی {emoji_icon} را ارسال کنید!**",
                    parse_mode="Markdown"
                )
        except ValueError:
            await update.message.reply_text("❌ فرمول یا مبلغ وارد شده نامعتبر است! (مثال‌های معتبر: `50k` یا `1.5m` یا `10000`)")
# ==================================================
# 🟢 بخش ۳-الف: پنل مدیریت بانک، واریز و برداشت
# ==================================================

async def bank_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش پنل اصلی بانک و موجودی‌ها"""
    user_id = update.effective_user.id
    user = get_user(user_id)

    wallet = user[1]
    bank = user[2]

    bank_text = (
        f"🏦 **پنل مدیریت حساب بانکی میوپوینت**\n\n"
        f"💳 **شماره حساب شما:** `{user_id}`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💵 **موجودی کیف پول:** `{int(wallet):,}` میوپوینت\n"
        f"🏦 **موجودی حساب بانک:** `{int(bank):,}` میوپوینت\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💡 **راهنمای دستورات سریع:**\n"
        f"▫️ `واریز 10k` یا `واریز همه` - انتقال از کیف پول به بانک\n"
        f"▫️ `برداشت 10k` یا `برداشت همه` - انتقال از بانک به کیف پول\n"
        f"▫️ `انتقال بانکی [شماره_حساب] [مبلغ]` - کارت به کارت بانکی"
    )
    await update.message.reply_text(bank_text, parse_mode="Markdown")


async def bank_deposit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتقال موجودی از کیف پول به حساب بانک (واریز)"""
    user_id = update.effective_user.id
    text = update.message.text.strip().split()

    if len(text) < 2:
        await update.message.reply_text("⚠️ **فرمت اشتباه!**\nمثال: `واریز 50k` یا `واریز همه`", parse_mode="Markdown")
        return

    user = get_user(user_id)
    wallet = user[1]

    amount_str = text[1].lower()
    if amount_str in ["همه", "all"]:
        amount = wallet
    else:
        try:
            amount = parse_amount(amount_str)
        except ValueError:
            await update.message.reply_text("❌ مبلغ وارد شده نامعتبر است.")
            return

    if amount <= 0:
        await update.message.reply_text("❌ مبلغ واریز باید بیشتر از ۰ باشد.")
        return

    if wallet < amount:
        await update.message.reply_text(f"❌ موجودی کیف پول شما کافی نیست!\nموجودی فعلی: **{int(wallet):,}** میوپوینت", parse_mode="Markdown")
        return

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET wallet = wallet - ?, bank = bank + ? WHERE user_id = ?", (amount, amount, user_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ **واریز با موفقیت انجام شد!**\n\n"
        f"📥 مبلغ **{int(amount):,}** میوپوینت به حساب بانک منتقل شد.",
        parse_mode="Markdown"
    )


async def bank_withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتقال موجودی از بانک به کیف پول (برداشت)"""
    user_id = update.effective_user.id
    text = update.message.text.strip().split()

    if len(text) < 2:
        await update.message.reply_text("⚠️ **فرمت اشتباه!**\nمثال: `برداشت 50k` یا `برداشت همه`", parse_mode="Markdown")
        return

    user = get_user(user_id)
    bank = user[2]

    amount_str = text[1].lower()
    if amount_str in ["همه", "all"]:
        amount = bank
    else:
        try:
            amount = parse_amount(amount_str)
        except ValueError:
            await update.message.reply_text("❌ مبلغ وارد شده نامعتبر است.")
            return

    if amount <= 0:
        await update.message.reply_text("❌ مبلغ برداشت باید بیشتر از ۰ باشد.")
        return

    if bank < amount:
        await update.message.reply_text(f"❌ موجودی بانک شما کافی نیست!\nموجودی فعلی بانک: **{int(bank):,}** میوپوینت", parse_mode="Markdown")
        return

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET bank = bank - ?, wallet = wallet + ? WHERE user_id = ?", (amount, amount, user_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ **برداشت با موفقیت انجام شد!**\n\n"
        f"📤 مبلغ **{int(amount):,}** میوپوینت به کیف پول منتقل شد.",
        parse_mode="Markdown"
                              )
        # ==================================================
# 🟢 بخش ۳-ب: انتقال بانکی و انتقال مستقیم (ریپلی)
# ==================================================

async def bank_transfer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتقال حساب به حساب بانکی با استفاده از آیدی عددی کاربر مقصد"""
    user_id = update.effective_user.id
    text = update.message.text.strip().split()

    if len(text) < 3:
        await update.message.reply_text(
            "⚠️ **فرمت اشتباه!**\n"
            "مثال: `انتقال بانکی 123456789 50k`",
            parse_mode="Markdown"
        )
        return

    try:
        target_id = int(text[1])
        amount_str = text[2]
    except ValueError:
        await update.message.reply_text("❌ شماره حساب مقصد یا مبلغ وارد شده نامعتبر است.")
        return

    if target_id == user_id:
        await update.message.reply_text("❌ نمی‌توانید به حساب خودتان پول انتقال دهید!")
        return

    target_user = get_user(target_id)
    if not target_user:
        await update.message.reply_text("❌ حساب مقصد در سیستم یافت نشد.")
        return

    sender_user = get_user(user_id)
    sender_bank = sender_user[2]

    try:
        amount = parse_amount(amount_str)
    except ValueError:
        await update.message.reply_text("❌ مبلغ وارد شده نامعتبر است.")
        return

    if amount <= 0:
        await update.message.reply_text("❌ مبلغ انتقال باید بیشتر از ۰ باشد.")
        return

    if sender_bank < amount:
        await update.message.reply_text(f"❌ موجودی بانک شما کافی نیست!\nموجودی بانک: **{int(sender_bank):,}** میوپوینت", parse_mode="Markdown")
        return

    # انجام تراکنش بانکی
    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET bank = bank - ? WHERE user_id = ?", (amount, user_id))
    cursor.execute("UPDATE users SET bank = bank + ? WHERE user_id = ?", (amount, target_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"💸 **انتقال بانکی با موفقیت انجام شد!**\n\n"
        f"👤 حساب مقصد: `{target_id}`\n"
        f"💰 مبلغ: **{int(amount):,}** میوپوینت\n"
        f"🏦 کارمزد: **۰** میوپوینت",
        parse_mode="Markdown"
    )

    await send_pv_notify(
        context,
        target_id,
        f"🏦 **دریافت واریزی بانکی!**\n"
        f"مبلغ **{int(amount):,}** میوپوینت از حساب `{user_id}` به حساب بانک شما واریز شد."
    )


async def direct_transfer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتقال مستقیم کیف پول به کیف پول از طریق ریپلی کردن روی پیام کاربر"""
    user_id = update.effective_user.id

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ لطفاً این دستور را روی پیام کاربر مقصد **ریپلی** کنید!\nمثال: `انتقال میویی 10k`", 
            parse_mode="Markdown"
        )
        return

    target_user_obj = update.message.reply_to_message.from_user
    target_id = target_user_obj.id

    if target_id == user_id:
        await update.message.reply_text("❌ نمی‌توانید به خودتان میوپوینت انتقال دهید!")
        return

    if target_user_obj.is_bot:
        await update.message.reply_text("❌ امکان انتقال میوپوینت به ربات وجود ندارد!")
        return

    text = update.message.text.strip().split()
    if len(text) < 2:
        await update.message.reply_text("⚠️ لطفاً مبلغ را وارد کنید.\nمثال: `انتقال میویی 20k`", parse_mode="Markdown")
        return

    try:
        amount = parse_amount(text[1])
    except ValueError:
        await update.message.reply_text("❌ مبلغ وارد شده نامعتبر است.")
        return

    if amount <= 0:
        await update.message.reply_text("❌ مبلغ انتقال باید بیشتر از ۰ باشد.")
        return

    sender = get_user(user_id)
    if sender[1] < amount:
        await update.message.reply_text(f"❌ موجودی کیف پول شما کافی نیست!\nموجودی کیف پول: **{int(sender[1]):,}** میو", parse_mode="Markdown")
        return

    # ذخیره داده‌های تراکنش جهت تأیید نهایی در کالبک
    context.user_data['pending_transfer'] = {
        'target_id': target_id,
        'target_name': target_user_obj.first_name,
        'amount': amount
    }

    buttons = [
        [
            InlineKeyboardButton("✅ تأیید انتقال", callback_data="confirm_direct_transfer"),
            InlineKeyboardButton("❌ لغو", callback_data="cancel_direct_transfer")
        ]
    ]

    await update.message.reply_text(
        f"❓ **تأییدیه انتقال میویی:**\n\n"
        f"👤 دریافت‌کننده: {target_user_obj.first_name} (`{target_id}`)\n"
        f"💰 مبلغ: **{int(amount):,}** میوپوینت\n\n"
        f"آیا از انجام این انتقال مطمئن هستید؟",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
)
        # ==================================================
# 🟢 بخش ۴-الف: سیستم ماهی‌گیری (۱۰ نوع ماهی) و یخچال
# ==================================================

# 📌 لیست کامل ۱۰ نوع ماهی همراه با قیمت، ارزش غذایی و شانس صید
EXTENDED_FISH_DATA = {
    "🐟": {"name": "ماهی رودخانه‌ای", "price": 100, "food": 10, "weight": 35},
    "🐠": {"name": "ماهی گرمسیری", "price": 250, "food": 15, "weight": 22},
    "🐡": {"name": "بادکنک ماهی", "price": 500, "food": 25, "weight": 14},
    "🦀": {"name": "خرچنگ سرخ", "price": 800, "food": 30, "weight": 10},
    "🐙": {"name": "هشت‌پا", "price": 1200, "food": 40, "weight": 7},
    "🦑": {"name": "ماهی مرکب", "price": 2000, "food": 50, "weight": 5},
    "🐬": {"name": "دلفین نقره‌ای", "price": 3500, "food": 70, "weight": 3.5},
    "🦈": {"name": "کوسه طلایی", "price": 6000, "food": 85, "weight": 2.0},
    "🐋": {"name": "نهنگ غول‌پیکر", "price": 12000, "food": 100, "weight": 1.0},
    "🐉": {"name": "اژدهای دریایی افسانه‌ای", "price": 30000, "food": 150, "weight": 0.5}
}

COOLDOWN_FISHING = 25 * 60  # ۲۵ دقیقه به ثانیه (۱۵۰۰ ثانیه)


async def fish_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انجام ماهی‌گیری با بررسی کول‌داون ۲۵ دقیقه‌ای و ثبت در یخچال"""
    user_id = update.effective_user.id
    _ = get_user(user_id)

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()

    # بررسی ستون last_fish_time در دیتابیس
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if "last_fish_time" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN last_fish_time REAL DEFAULT 0")
        conn.commit()

    cursor.execute("SELECT last_fish_time FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    last_fish_time = res[0] if res and res[0] else 0

    now = time.time()
    elapsed = now - last_fish_time

    # بررسی تایمر ۲۵ دقیقه‌ای
    if elapsed < COOLDOWN_FISHING:
        remaining_seconds = int(COOLDOWN_FISHING - elapsed)
        minutes = remaining_seconds // 60
        seconds = remaining_seconds % 60
        await update.message.reply_text(
            f"🎣 **قلاب ماهی‌گیری شما هنوز آماده نیست!**\n\n"
            f"⏱️ زمان باقی‌مانده تا ماهی‌گیری بعدی: **{minutes} دقیقه و {seconds} ثانیه**",
            parse_mode="Markdown"
        )
        conn.close()
        return

    # انتخاب تصادفی ماهی بر اساس ضریب شانس (Weight)
    fish_emojis = list(EXTENDED_FISH_DATA.keys())
    weights = [EXTENDED_FISH_DATA[f]["weight"] for f in fish_emojis]
    caught_emoji = random.choices(fish_emojis, weights=weights, k=1)[0]
    caught_fish = EXTENDED_FISH_DATA[caught_emoji]

    # ثبت ماهی در یخچال
    cursor.execute("""
        INSERT INTO fridge (user_id, fish_type, count)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, fish_type) DO UPDATE SET count = count + 1
    """, (user_id, caught_emoji))

    # بروزرسانی زمان آخرین ماهی‌گیری
    cursor.execute("UPDATE users SET last_fish_time = ? WHERE user_id = ?", (now, user_id))
    conn.commit()
    conn.close()

    msg = (
        f"🎣 **ماهی‌گیری موفقیت‌آمیز بود!**\n\n"
        f"شما یک **{caught_emoji} {caught_fish['name']}** صید کردید!\n"
        f"💰 ارزش فروش: **{caught_fish['price']:,}** میو\n"
        f"🍖 ارزش سیرکنندگی: **{caught_fish['food']}%**\n\n"
        f"📦 ماهی صید شده به **یخچال** شما منتقل شد."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def fridge_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مشاهده موجودی یخچال و فهرست ۱۰ نوع ماهی"""
    user_id = update.effective_user.id

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    cursor.execute("SELECT fish_type, count FROM fridge WHERE user_id = ? AND count > 0", (user_id,))
    items = cursor.fetchall()
    conn.close()

    if not items:
        await update.message.reply_text("🧊 **یخچال شما خالی است!**\nبا دستور `ماهی‌گیری` قلاب بندازید.", parse_mode="Markdown")
        return

    text = "🧊 **موجودی یخچال شما:**\n━━━━━━━━━━━━━━━━━━\n"
    total_val = 0

    for fish_emoji, count in items:
        if fish_emoji in EXTENDED_FISH_DATA:
            f_info = EXTENDED_FISH_DATA[fish_emoji]
            val = f_info['price'] * count
            total_val += val
            text += f"{fish_emoji} **{f_info['name']}:** `{count}` عدد (ارزش: {val:,} میو)\n"

    text += f"━━━━━━━━━━━━━━━━━━\n📊 **ارزش کل ماهی‌ها:** `{total_val:,}` میوپوینت"

    buttons = [
        [InlineKeyboardButton("💰 فروش همه ماهی‌ها", callback_data="sell_all_fish")],
        [InlineKeyboardButton("🍖 غذا دادن به پیشی با ماهی", callback_data="feed_cat_fish_menu")]
    ]

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
        # ==================================================
# 🟢 بخش ۴-ب: سیستم کامل کارخانه و تولید محصول
# ==================================================

async def factory_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """داشبورد اصلی کارخانه و وضعیت خط تولید"""
    user_id = update.effective_user.id
    user = get_user(user_id)

    # اطلاعات خط تولید کاربر
    producing_item = user[11]
    produce_amount = user[12]
    produce_start_time = user[13]

    now = time.time()
    text = "🏭 **داشبورد خط تولید کارخانه میو**\n━━━━━━━━━━━━━━━━━━\n"

    if producing_item and producing_item in PRODUCTS:
        p_info = PRODUCTS[producing_item]
        duration = p_info["time"]
        passed = now - produce_start_time

        if passed >= duration:
            text += (
                f"✅ **تولید محصول به پایان رسید!**\n"
                f"📦 محصول: **{p_info['name']}** ({produce_amount} عدد)\n"
                f"👇 برای دریافت و فروش محصول دکمه زیر را بزنید."
            )
            buttons = [[InlineKeyboardButton("📦 دریافت محصول و واریز به کیف پول", callback_data="claim_factory_product")]]
        else:
            rem = int(duration - passed)
            m, s = rem // 60, rem % 60
            text += (
                f"⚙️ **در حال تولید...**\n"
                f"📦 محصول: **{p_info['name']}** ({produce_amount} عدد)\n"
                f"⏱️ زمان باقی‌مانده: **{m} دقیقه و {s} ثانیه**"
            )
            buttons = [[InlineKeyboardButton("🔄 بروزرسانی وضعیت", callback_data="refresh_factory")]]
    else:
        text += "💤 **کارخانه هم‌اکنون متوقف است.**\nیکی از محصولات زیر را برای ساخت انتخاب کنید:\n\n"
        buttons = []
        for key, item in PRODUCTS.items():
            dynamic_price = calculate_dynamic_sell_price(item["base_sell"])
            text += (
                f"🔹 **{item['name']}**\n"
                f"💰 هزینه ساخت: `{item['cost']:,}` | 📈 قیمت فروش تقریبی: `{dynamic_price:,}`\n"
                f"⏱️ زمان ساخت: `{item['time'] // 60}` دقیقه\n\n"
            )
            buttons.append([InlineKeyboardButton(f"🛠️ ساخت {item['name']}", callback_data=f"start_factory_{key}")])

    reply_markup = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")


async def factory_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت کالبک‌های مربوط به شروع تولید و برداشت محصول کارخانه"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data
    user = get_user(user_id)

    wallet = user[1]
    producing_item = user[11]

    # ۱. شروع خط تولید
    if data.startswith("start_factory_"):
        product_key = data.replace("start_factory_", "")
        if product_key not in PRODUCTS:
            return

        if producing_item:
            await query.message.reply_text("❌ خط تولید شما در حال حاضر مشغول است!")
            return

        p_info = PRODUCTS[product_key]
        cost = p_info["cost"]

        if wallet < cost:
            await query.message.reply_text(f"❌ موجودی شما کافی نیست! هزینه ساخت: **{cost:,}** میو", parse_mode="Markdown")
            return

        now = time.time()
        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE users 
               SET wallet = wallet - ?, producing_item = ?, produce_amount = 1, produce_start_time = ? 
               WHERE user_id = ?""",
            (cost, product_key, now, user_id)
        )
        conn.commit()
        conn.close()

        await query.message.reply_text(f"🚀 تولید **{p_info['name']}** با موفقیت آغاز شد!", parse_mode="Markdown")
        await factory_dashboard(update, context)

    # ۲. برداشت محصول و فروش با قیمت شناور بازار
    elif data == "claim_factory_product":
        if not producing_item or producing_item not in PRODUCTS:
            await query.message.reply_text("❌ هیچ محصولی آماده دریافت نیست.")
            return

        p_info = PRODUCTS[producing_item]
        now = time.time()
        if now - user[13] < p_info["time"]:
            await query.message.reply_text("⏳ تولید محصول هنوز تمام نشده است!")
            return

        # محاسبه درآمد با سود بازار شناور
        sell_price = calculate_dynamic_sell_price(p_info["base_sell"])

        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE users 
               SET wallet = wallet + ?, producing_item = NULL, produce_amount = 0, produce_start_time = 0 
               WHERE user_id = ?""",
            (sell_price, user_id)
        )
        conn.commit()
        conn.close()

        await query.message.reply_text(
            f"🎉 **محصول فروخته شد!**\n\n"
            f"📦 محصول: **{p_info['name']}**\n"
            f"💵 سود حاصل از فروش بازار: **{sell_price:,}** میوپوینت به کیف پول شما اضافه شد.",
            parse_mode="Markdown"
        )
        await factory_dashboard(update, context)

    elif data == "refresh_factory":
        await factory_dashboard(update, context)
            # ==================================================
# 🟢 بخش ۵-الف: پنل کازینو و بازی‌های تک‌نفره
# ==================================================

async def casino_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش پنل اصلی کازینو و انتخاب بازی‌ها"""
    text = (
        "🎰 **کازینوی بزرگ میوپوینت**\n\n"
        "یکی از بازی‌های زیر را برای شرط‌بندی انتخاب کنید:\n\n"
        "🎲 **تاس (Dice):** پیش‌بینی زوج/فرد یا عدد دقیق\n"
        "🎰 **اسلات ماشین (Slot):** شانس خود را برای جک‌پات امتحان کنید\n"
        "🎳 **بولینگ (Bowling):** کسب ضریب بر اساس تعداد پین‌های انداخته‌شده\n"
        "⚔️ **دوئل ۲ نفره (Duel):** رقابت مستقیم با یک کاربر دیگر"
    )

    buttons = [
        [
            InlineKeyboardButton("🎲 تاس", callback_data="casino_select_dice"),
            InlineKeyboardButton("🎰 اسلات ماشین", callback_data="casino_select_slot")
        ],
        [
            InlineKeyboardButton("🎳 بولینگ", callback_data="casino_select_bowling"),
            InlineKeyboardButton("⚔️ دوئل ۲ نفره", callback_data="casino_select_duel")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")


async def casino_bet_select_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, game_type: str):
    """نمایش منوی انتخاب مبلغ شرط برای بازی انتخابی"""
    query = update.callback_query
    
    game_names = {
        "dice": "🎲 تاس",
        "slot": "🎰 اسلات ماشین",
        "bowling": "🎳 بولینگ",
        "duel": "⚔️ دوئل"
    }

    text = (
        f"🎯 بازی انتخابی: **{game_names.get(game_type, game_type)}**\n\n"
        f"لطفاً مبلغ شرط‌بندی را انتخاب کنید یا گزینه «مبلغ دلخواه» را بزنید:"
    )

    buttons = [
        [
            InlineKeyboardButton("1,000 میو", callback_data=f"casino_bet_{game_type}_1000"),
            InlineKeyboardButton("5,000 میو", callback_data=f"casino_bet_{game_type}_5000"),
            InlineKeyboardButton("10,000 میو", callback_data=f"casino_bet_{game_type}_10000")
        ],
        [
            InlineKeyboardButton("50,000 میو", callback_data=f"casino_bet_{game_type}_50000"),
            InlineKeyboardButton("100,000 میو", callback_data=f"casino_bet_{game_type}_100000")
        ],
        [
            InlineKeyboardButton("✍️ مبلغ دلخواه", callback_data=f"casino_bet_{game_type}_custom"),
            InlineKeyboardButton("🔙 بازگشت", callback_data="casino_main_menu")
        ]
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def native_dice_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بررسی و پردازش ایموجی‌های انیمیشن‌دار (تاس، اسلات، بولینگ) فرستاده شده توسط کاربر"""
    if not update.message or not update.message.dice:
        return

    user_id = update.effective_user.id
    pending = context.user_data.get('pending_casino_game')

    if not pending:
        return

    dice_obj = update.message.dice
    game_type = pending['type']
    bet_amount = pending['bet']
    prediction = pending.get('prediction')

    # حذف بازی در جریان
    context.user_data.pop('pending_casino_game', None)
    value = dice_obj.value

    # صبر کوتاه برای پایان انیمیشن تلگرام
    await asyncio.sleep(2.5)

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()

    win_amount = 0
    is_win = False
    result_text = ""

    # ۱. پردازش تاس 🎲
    if dice_obj.emoji == "🎲" and game_type == "dice":
        if prediction == "even" and value % 2 == 0:
            is_win = True
            win_amount = int(bet_amount * 1.5)
            result_text = f"🎯 عدد تاس: **{value}** (زوج) - شما برنده شدید!"
        elif prediction == "odd" and value % 2 != 0:
            is_win = True
            win_amount = int(bet_amount * 1.5)
            result_text = f"🎯 عدد تاس: **{value}** (فرد) - شما برنده شدید!"
        elif str(value) == str(prediction):
            is_win = True
            win_amount = int(bet_amount * 3.0)
            result_text = f"🎯 عدد تاس: **{value}** (پیش‌بینی دقیق) - شما ۳ برابر برنده شدید!"
        else:
            result_text = f"🎯 عدد تاس: **{value}** - متأسفانه باختید!"

    # ۲. پردازش اسلات ماشین 🎰
    elif dice_obj.emoji == "🎰" and game_type == "slot":
        # مقادیر جک‌پات تلگرام برای اسلات: 1 (۳ لیمو)، 22 (۳ انگور)، 43 (۳ بار)، 64 (۳ ۷۷۷)
        if value == 64:  # ۳ تا هفت (۷۷۷)
            is_win = True
            win_amount = int(bet_amount * 10.0)
            result_text = "🎉 **جک‌پات بزرگ! (۷۷۷)** شما ۱۰ برابر برنده شدید!"
        elif value in [1, 22, 43]:
            is_win = True
            win_amount = int(bet_amount * 3.0)
            result_text = f"✨ **سه شکل همسان!** شما ۳ برابر برنده شدید!"
        else:
            result_text = "❌ ترکیبی برنده نشد. دوباره شانس خودت رو امتحان کن!"

    # ۳. پردازش بولینگ 🎳
    elif dice_obj.emoji == "🎳" and game_type == "bowling":
        # value: 1 (خیلی بد) تا 6 (تمام ۶ پین افتاد - استرایک)
        if value == 6:
            is_win = True
            win_amount = int(bet_amount * 3.0)
            result_text = "🎳 **استرایک عالی! (۶ پین)** شما ۳ برابر برنده شدید!"
        elif value in [4, 5]:
            is_win = True
            win_amount = int(bet_amount * 1.5)
            result_text = f"🎳 **نتیجه خوب! ({value} پین)** شما ۱.۵ برابر برنده شدید!"
        else:
            result_text = f"🎳 فقط **{value}** پین افتاد. باختید!"

    # اعمال تغییرات مالی دیتابیس
    if is_win and win_amount > 0:
        cursor.execute("UPDATE users SET wallet = wallet + ? WHERE user_id = ?", (win_amount, user_id))
        msg = f"{result_text}\n💰 پاداش: **{win_amount:,}** میوپوینت به کیف پول اضافه شد."
    else:
        msg = f"{result_text}\n💸 مبلغ **{int(bet_amount):,}** میوپوینت از دست رفت."

    conn.commit()
    conn.close()

    await update.message.reply_text(msg, parse_mode="Markdown")
            # ==================================================
# 🟢 بخش ۵-ب: سیستم دوئل ۲ نفره و مدیریت کالبک‌ها
# ==================================================

async def duel_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور ایجاد مبارزه/دوئل ۲ نفره روی پیام یک کاربر دیگر"""
    user_id = update.effective_user.id

    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ لطفاً این دستور را روی پیام حریف خود **ریپلی** کنید!\nمثال: `دوئل 50k`", parse_mode="Markdown")
        return

    target_user = update.message.reply_to_message.from_user
    target_id = target_user.id

    if target_id == user_id:
        await update.message.reply_text("❌ نمی‌توانید با خودتان دوئل کنید!")
        return

    if target_user.is_bot:
        await update.message.reply_text("❌ امکان دوئل با ربات وجود ندارد!")
        return

    text = update.message.text.strip().split()
    if len(text) < 2:
        await update.message.reply_text("⚠️ لطفاً مبلغ دوئل را مشخص کنید.\nمثال: `دوئل 10k`", parse_mode="Markdown")
        return

    try:
        bet_amount = parse_amount(text[1])
    except ValueError:
        await update.message.reply_text("❌ مبلغ وارد شده نامعتبر است.")
        return

    challeger_user = get_user(user_id)
    opponent_user = get_user(target_id)

    if challeger_user[1] < bet_amount:
        await update.message.reply_text("❌ موجودی کیف پول شما برای این دوئل کافی نیست!")
        return

    if opponent_user[1] < bet_amount:
        await update.message.reply_text("❌ موجودی کیف پول حریف شما برای این دوئل کافی نیست!")
        return

    # ثبت شناسه دوئل در context.bot_data
    duel_id = f"{user_id}_{target_id}_{int(time.time())}"
    context.bot_data[f"duel_{duel_id}"] = {
        "challenger": user_id,
        "opponent": target_id,
        "amount": bet_amount,
        "status": "pending"
    }

    buttons = [
        [
            InlineKeyboardButton("⚔️ قبول دوئل", callback_data=f"accept_duel_{duel_id}"),
            InlineKeyboardButton("❌ رد دوئل", callback_data=f"decline_duel_{duel_id}")
        ]
    ]

    await update.message.reply_text(
        f"⚔️ **چالش دوئل جدید!**\n\n"
        f"👤 درخواست‌کننده: {update.effective_user.first_name}\n"
        f"🎯 حریف: {target_user.first_name}\n"
        f"💰 مبلغ شرط: **{int(bet_amount):,}** میوپوینت\n\n"
        f"آیا دوئل را می‌پذیرید؟",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


async def duel_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت قبول یا رد درخواست دوئل و اجرای پرتاب تاس مبارزه"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    if data.startswith("accept_duel_"):
        duel_id = data.replace("accept_duel_", "")
        duel_info = context.bot_data.get(f"duel_{duel_id}")

        if not duel_info:
            await query.message.edit_text("❌ این دوئل منقضی شده یا یافت نشد.")
            return

        if user_id != duel_info["opponent"]:
            await query.answer("❌ این درخواست دوئل برای شما نیست!", show_alert=True)
            return

        challenger_id = duel_info["challenger"]
        opponent_id = duel_info["opponent"]
        bet_amount = duel_info["amount"]

        c_user = get_user(challenger_id)
        o_user = get_user(opponent_id)

        if c_user[1] < bet_amount or o_user[1] < bet_amount:
            await query.message.edit_text("❌ موجودی کیف پول یکی از طرفین برای شروع دوئل کافی نیست!")
            return

        # کسر مبلغ از هر دو بازیکن
        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET wallet = wallet - ? WHERE user_id = ?", (bet_amount, challenger_id))
        cursor.execute("UPDATE users SET wallet = wallet - ? WHERE user_id = ?", (bet_amount, opponent_id))
        conn.commit()

        # پرتاب تاس برای دو طرف
        msg_c = await context.bot.send_dice(chat_id=query.message.chat_id, emoji="🎲")
        msg_o = await context.bot.send_dice(chat_id=query.message.chat_id, emoji="🎲")

        await asyncio.sleep(3)

        val_c = msg_c.dice.value
        val_o = msg_o.dice.value

        total_prize = int(bet_amount * 2)

        if val_c > val_o:
            cursor.execute("UPDATE users SET wallet = wallet + ? WHERE user_id = ?", (total_prize, challenger_id))
            result = f"🎉 بازیکن درخواست‌کننده (`{val_c}` vs `{val_o}`) برنده شد و **{total_prize:,}** میو دریافت کرد!"
        elif val_o > val_c:
            cursor.execute("UPDATE users SET wallet = wallet + ? WHERE user_id = ?", (total_prize, opponent_id))
            result = f"🎉 بازیکن حریف (`{val_o}` vs `{val_c}`) برنده شد و **{total_prize:,}** میو دریافت کرد!"
        else:
            # مساوی: بازگشت سرمایه
            cursor.execute("UPDATE users SET wallet = wallet + ? WHERE user_id = ?", (bet_amount, challenger_id))
            cursor.execute("UPDATE users SET wallet = wallet + ? WHERE user_id = ?", (bet_amount, opponent_id))
            result = f"🤝 دوئل مساوی شد (`{val_c}` vs `{val_o}`)! مبالغ به کیف پول بازگردانده شد."

        conn.commit()
        conn.close()

        context.bot_data.pop(f"duel_{duel_id}", None)
        await query.message.edit_text(f"⚔️ **نتیجه نهایی دوئل:**\n\n{result}", parse_mode="Markdown")

    elif data.startswith("decline_duel_"):
        duel_id = data.replace("decline_duel_", "")
        duel_info = context.bot_data.get(f"duel_{duel_id}")

        if duel_info and user_id in [duel_info["challenger"], duel_info["opponent"]]:
            context.bot_data.pop(f"duel_{duel_id}", None)
            await query.message.edit_text("❌ درخواست دوئل لغو شد.")


async def casino_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت کلیه کالبک‌دکمه‌های انتخاب بازی و مبالغ شرط کازینو"""
    query = update.callback_query
    data = query.data

    if data == "casino_main_menu":
        await casino_dashboard(update, context)
        return

    if data.startswith("casino_select_"):
        game_type = data.replace("casino_select_", "")
        if game_type == "duel":
            await query.answer("💡 برای دوئل، دستور «دوئل [مبلغ]» را روی پیام کاربر ریپلی کنید.", show_alert=True)
            return
        await casino_bet_select_menu(update, context, game_type)

    elif data.startswith("casino_bet_"):
        parts = data.split("_")
        game_type = parts[2]
        amount_str = parts[3]

        if amount_str == "custom":
            context.user_data['casino_custom'] = {'game_type': game_type, 'players': 1}
            await query.message.reply_text("✍️ لطفاً مبلغ شرط‌بندی دلخواه خود را وارد کنید:\n(مثال: `25k` یا `50000`)", parse_mode="Markdown")
            return

        bet_amount = float(amount_str)
        user_id = query.from_user.id
        user = get_user(user_id)

        if user[1] < bet_amount:
            await query.answer("❌ موجودی کیف پول شما کافی نیست!", show_alert=True)
            return

        if game_type == "dice":
            buttons = [
                [
                    InlineKeyboardButton("🔵 زوج (x1.5)", callback_data=f"casino_start_dice_1_{bet_amount}_even"),
                    InlineKeyboardButton("🔴 فرد (x1.5)", callback_data=f"casino_start_dice_1_{bet_amount}_odd")
                ],
                [
                    InlineKeyboardButton("🎯 ۱ (x3)", callback_data=f"casino_start_dice_1_{bet_amount}_1"),
                    InlineKeyboardButton("🎯 ۲ (x3)", callback_data=f"casino_start_dice_1_{bet_amount}_2"),
                    InlineKeyboardButton("🎯 ۳ (x3)", callback_data=f"casino_start_dice_1_{bet_amount}_3")
                ],
                [
                    InlineKeyboardButton("🎯 ۴ (x3)", callback_data=f"casino_start_dice_1_{bet_amount}_4"),
                    InlineKeyboardButton("🎯 ۵ (x3)", callback_data=f"casino_start_dice_1_{bet_amount}_5"),
                    InlineKeyboardButton("🎯 ۶ (x3)", callback_data=f"casino_start_dice_1_{bet_amount}_6")
                ]
            ]
            await query.edit_message_text(
                f"🎲 شرط **{int(bet_amount):,}** میو ثبت شد.\nپیش‌بینی خود را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="Markdown"
            )
        else:
            conn = sqlite3.connect("meow_point.db")
            conn.cursor().execute("UPDATE users SET wallet = wallet - ? WHERE user_id = ?", (bet_amount, user_id))
            conn.commit()
            conn.close()

            context.user_data['pending_casino_game'] = {'type': game_type, 'bet': bet_amount, 'prediction': None}
            emoji_icon = {"slot": "🎰", "bowling": "🎳"}.get(game_type)
            await query.edit_message_text(
                f"✅ شرط شما به مبلغ **{int(bet_amount):,}** میوپوینت ثبت شد.\n\n"
                f"👇 **لطفاً ایموجی {emoji_icon} را ارسال کنید!**",
                parse_mode="Markdown"
            )

    elif data.startswith("casino_start_dice_"):
        parts = data.split("_")
        bet_amount = float(parts[4])
        prediction = parts[5]
        user_id = query.from_user.id

        conn = sqlite3.connect("meow_point.db")
        conn.cursor().execute("UPDATE users SET wallet = wallet - ? WHERE user_id = ?", (bet_amount, user_id))
        conn.commit()
        conn.close()

        context.user_data['pending_casino_game'] = {'type': 'dice', 'bet': bet_amount, 'prediction': prediction}
        await query.edit_message_text(
            f"✅ شرط شما روی پیش‌بینی **{prediction}** به مبلغ **{int(bet_amount):,}** میو ثبت شد.\n\n"
            f"👇 **لطفاً ایموجی 🎲 را ارسال کنید!**",
            parse_mode="Markdown"
        )
# ==================================================
# 🟢 بخش ۶-الف: پنل ادمین و دستورات مدیریتی
# ==================================================

# 📌 لیست آیدی‌های عددی ادمین‌های ربات
ADMIN_IDS = 8918154552# ==================================================
# 🟢 بخش ۶-ب: ثبت هندرها و اجرای کامل برنامه
# ==================================================

def main():
    """راه‌اندازی کامل سیستم دیتابیس و ربات تلگرام"""
    # ۱. راه‌اندازی دیتابیس
    init_db()
    print("✅ دیتابیس میوپوینت با موفقیت آماده‌سازی شد.")

    # ۲. ساخت متغیر برنامه با توکن ربات
    BOT_TOKEN = "8971798729:AAGY8Hw8osbpHdglddpckGSnDUgIR8bywfw"  # 👈 توکن ربات تلگرام خود را اینجا قرار دهید
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # ۳. ثبت هندلرهای دستورات اصلی و سیستم گربه
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(MessageHandler(filters.Regex(r"^(میو|مع|meow)$"), meow_message_handler))
    application.add_handler(MessageHandler(filters.Regex(r"^پروفایل$"), profile_handler))
    application.add_handler(MessageHandler(filters.Regex(r"^پیشی$"), cat_status_handler))
    application.add_handler(MessageHandler(filters.Regex(r"^غذا دادن$"), feed_cat_handler))
    application.add_handler(MessageHandler(filters.Regex(r"^بازی با پیشی$"), play_cat_handler))
    application.add_handler(MessageHandler(filters.Regex(r"^خوابیدن پیشی$"), sleep_cat_handler))

    # ۴. ثبت هندلرهای مالی، بانک و انتقال
    application.add_handler(MessageHandler(filters.Regex(r"^بانک$"), bank_handler))
    application.add_handler(MessageHandler(filters.Regex(r"^واریز"), bank_deposit_handler))
    application.add_handler(MessageHandler(filters.Regex(r"^برداشت"), bank_withdraw_handler))
    application.add_handler(MessageHandler(filters.Regex(r"^انتقال بانکی"), bank_transfer_handler))
    application.add_handler(MessageHandler(filters.Regex(r"^انتقال میویی"), direct_transfer_handler))

    # ۵. ثبت هندلرهای ماهی‌گیری، یخچال و کارخانه
    application.add_handler(MessageHandler(filters.Regex(r"^ماهی‌گیری$"), fish_handler))
    application.add_handler(MessageHandler(filters.Regex(r"^یخچال$"), fridge_handler))
    application.add_handler(MessageHandler(filters.Regex(r"^کارخانه$"), factory_dashboard))

    # ۶. ثبت هندلرهای کازینو و دوئل
    application.add_handler(MessageHandler(filters.Regex(r"^کازینو$"), casino_dashboard))
    application.add_handler(MessageHandler(filters.Regex(r"^دوئل"), duel_command_handler))
    application.add_handler(MessageHandler(filters.Dice.ALL), native_dice_message_handler)

    # ۷. ثبت هندلرهای پنل مدیریت ادمین
    application.add_handler(MessageHandler(filters.Regex(r"^پنل ادمین$"), admin_dashboard))
    application.add_handler(MessageHandler(filters.Regex(r"^(اعطا|کسر)"), admin_give_coins_handler))
    application.add_handler(MessageHandler(filters.Regex(r"^مکس گربه"), admin_max_cat_handler))
    application.add_handler(MessageHandler(filters.Regex(r"^تنظیم لول"), admin_set_level_handler))

    # ۸. ثبت کالبک‌های دکمه‌های شیشه‌ای (CallbackQueryHandlers)
    application.add_handler(CallbackQueryHandler(factory_callback_handler, pattern=r"^(start_factory_|claim_factory_product|refresh_factory)"))
    application.add_handler(CallbackQueryHandler(duel_callback_handler, pattern=r"^(accept_duel_|decline_duel_)"))
    application.add_handler(CallbackQueryHandler(casino_callback_router, pattern=r"^casino_"))

    # ۹. شروع پولینگ ربات
    print("🚀 ربات میوپوینت با موفقیت روشن شد و آماده دریافت پیام‌هاست...")
    application.run_polling()


if __name__ == "__main__":
    main()
    # آیدی عددی خود را اینجا وارد کنید


def is_admin(user_id: int) -> bool:
    """بررسی ادمین بودن کاربر"""
    return user_id in ADMIN_IDS


async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش پنل اصلی مدیریت ربات"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*), SUM(wallet), SUM(bank) FROM users")
    stats = cursor.fetchone()
    total_users = stats[0] or 0
    total_wallet = stats[1] or 0
    total_bank = stats[2] or 0

    admin_text = (
        f"👑 **پنل مدیریت ارشد ربات میوپوینت**\n\n"
        f"📊 **آمار کل سیستم:**\n"
        f"👥 تعداد کاربران: `{total_users:,}` نفر\n"
        f"💵 کل موجودی کیف‌پول‌ها: `{int(total_wallet):,}` میو\n"
        f"🏦 کل موجودی بانک‌ها: `{int(total_bank):,}` میو\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🛠️ **دستورات مدیریتی:**\n\n"
        f"💰 **اعطای سکه / میوپوینت:**\n"
        f"▫️ `اعطا [آیدی_کاربر] [مبلغ]` - افزودن سکه به کیف پول کاربر\n"
        f"▫️ `کسر [آیدی_کاربر] [مبلغ]` - کسر سکه از کیف پول کاربر\n\n"
        f"🐱 **ارتقا و مکس کردن گربه:**\n"
        f"▫️ `مکس گربه [آیدی_کاربر]` - مکس کردن لول و وضعیت کامل گربه\n\n"
        f"⭐ **تنظیم لول (بدست آمده با مع / میو):**\n"
        f"▫️ `تنظیم لول [آیدی_کاربر] [سطح]` - تغییر مستقیم سطح کاربر"
    )
    conn.close()

    await update.message.reply_text(admin_text, parse_mode="Markdown")


async def admin_give_coins_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """افزایش یا کاهش مستقیم سکه/میوپوینت کاربر توسط ادمین"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    text = update.message.text.strip().split()
    if len(text) < 3:
        await update.message.reply_text("⚠️ **فرمت اشتباه!**\nمثال: `اعطا 123456789 100k` یا `کسر 123456789 50k`", parse_mode="Markdown")
        return

    command = text[0]
    try:
        target_id = int(text[1])
        amount = parse_amount(text[2])
    except ValueError:
        await update.message.reply_text("❌ آیدی کاربر یا مبلغ وارد شده نامعتبر است.")
        return

    target_user = get_user(target_id)
    if not target_user:
        await update.message.reply_text("❌ کاربر مورد نظر در سیستم یافت نشد.")
        return

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()

    if command == "اعطا":
        cursor.execute("UPDATE users SET wallet = wallet + ? WHERE user_id = ?", (amount, target_id))
        msg = f"✅ مبلغ **{int(amount):,}** میوپوینت با موفقیت به حساب کاربر `{target_id}` اضافه شد."
        notify_msg = f"🎁 **هدیه مدیریتی!**\nمبلغ **{int(amount):,}** میوپوینت از طرف مدیریت به کیف پول شما واریز شد."
    else:  # کسر
        cursor.execute("UPDATE users SET wallet = MAX(0, wallet - ?) WHERE user_id = ?", (amount, target_id))
        msg = f"📉 مبلغ **{int(amount):,}** میوپوینت از حساب کاربر `{target_id}` کسر شد."
        notify_msg = f"⚠️ **اطلاعیه مدیریت:**\nمبلغ **{int(amount):,}** میوپوینت توسط ادمین از کیف پول شما کسر شد."

    conn.commit()
    conn.close()

    await update.message.reply_text(msg, parse_mode="Markdown")
    await send_pv_notify(context, target_id, notify_msg)


async def admin_max_cat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مکس کردن سطح و فول کردن تمام شاخص‌های سلامتی، انرژی و گرسنگی گربه کاربر"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    text = update.message.text.strip().split()
    if len(text) < 2:
        await update.message.reply_text("⚠️ **فرمت اشتباه!**\nمثال: `مکس گربه 123456789`", parse_mode="Markdown")
        return

    try:
        target_id = int(text[1])
    except ValueError:
        await update.message.reply_text("❌ آیدی عددی کاربر نامعتبر است.")
        return

    target_user = get_user(target_id)
    if not target_user:
        await update.message.reply_text("❌ کاربر مورد نظر در دیتابیس یافت نشد.")
        return

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()

    # مکس کردن لول گربه روی ۱۰۰ و فول کردن شاخص‌ها
    cursor.execute("""
        UPDATE users 
        SET cat_level = 100, cat_xp = 0, cat_hunger = 100, cat_happiness = 100, cat_energy = 100
        WHERE user_id = ?
    """, (target_id,))

    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"👑 **گربه کاربر با موفقیت مکس شد!**\n\n"
        f"👤 کاربر: `{target_id}`\n"
        f"🎖️ لول جدید گربه: **100 (Max)**\n"
        f"🍖 سیرکنندگی: **100%** | ❤️ شادابی: **100%** | ⚡ انرژی: **100%**",
        parse_mode="Markdown"
    )

    await send_pv_notify(
        context,
        target_id,
        "👑 **ارتقای ویژه مدیریت!**\nگربه شما توسط ادمین به **سطح 100 (MAX)** ارتقا یافت و تمامی شاخص‌های آن فول شد!"
    )


async def admin_set_level_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تغییر مستقیم سطح (Level) کاربر که با ارسال «مع» یا «میو» ارتقا می‌یابد"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    text = update.message.text.strip().split()
    if len(text) < 3:
        await update.message.reply_text("⚠️ **فرمت اشتباه!**\nمثال: `تنظیم لول 123456789 50`", parse_mode="Markdown")
        return

    try:
        target_id = int(text[1])
        new_level = int(text[2])
    except ValueError:
        await update.message.reply_text("❌ آیدی کاربر یا سطح وارد شده نامعتبر است.")
        return

    if new_level < 1:
        await update.message.reply_text("❌ سطح کاربر باید حداقل ۱ باشد.")
        return

    target_user = get_user(target_id)
    if not target_user:
        await update.message.reply_text("❌ کاربر در دیتابیس پیدا نشد.")
        return

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()

    # تنظیم لول کاربر و صفر کردن XP برای لول جدید
    cursor.execute("UPDATE users SET user_level = ?, user_xp = 0 WHERE user_id = ?", (new_level, target_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ **سطح کاربر بروزرسانی شد!**\n\n"
        f"👤 آیدی کاربر: `{target_id}`\n"
        f"⭐ سطح جدید کاربر (مع / میو): **{new_level}**",
        parse_mode="Markdown"
    )

    await send_pv_notify(
        context,
        target_id,
        f"⭐ **تغییر سطح حساب کاربری!**\nسطح فعالیت شما با دستور مدیریت به **{new_level}** تغییر یافت."
        )
    
