# ==================================================
# 🟢 بخش ۱-الف: کتابخانه‌ها، ثابت‌ها و ساخت کامل دیتابیس
# ==================================================
import logging
import sqlite3
import asyncio
import time
import random
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# تنظیمات لاگ‌گیری برای عیب‌یابی دقیق
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 🔑 اطلاعات اختصاصی شما
TOKEN = "8971798729:AAGY8Hw8osbpHdglddpckGSnDUgIR8bywfw"
ADMIN_ID = 8918154552

# ==================================================
# 🗄️ مقداردهی اولیه و ساخت جداول دیتابیس SQLite
# ==================================================
def init_db():
    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    
    # جدول کاربران
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        wallet REAL DEFAULT 0,
        bank REAL DEFAULT 0,
        card_number TEXT UNIQUE,
        cat_level INTEGER DEFAULT 1,
        cat_name TEXT DEFAULT 'پیشی',
        cat_food INTEGER DEFAULT 100,
        cat_last_claim REAL DEFAULT 0,
        meow_count INTEGER DEFAULT 0,
        last_meow_time REAL DEFAULT 0,
        factory_level INTEGER DEFAULT 1,
        producing_item TEXT DEFAULT NULL,
        produce_amount INTEGER DEFAULT 0,
        produce_start_time REAL DEFAULT 0,
        produce_cost REAL DEFAULT 0
    )
    """)

    # جدول یخچال ماهی‌ها
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fridge (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        fish_type TEXT,
        count INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()

init_db()
# ==================================================
# 🟢 بخش ۱-ب: داده‌های پایه و توابع محاسباتی
# ==================================================

FISH_DATA = {
    "🐟": {"name": "ماهی معمولی", "price": 150, "food": 10},
    "🐠": {"name": "ماهی گرمسیری", "price": 350, "food": 20},
    "🐡": {"name": "بادکنک ماهی", "price": 800, "food": 35},
    "🦈": {"name": "کوسه‌ماهی نایاب", "price": 2500, "food": 60}
}

PRODUCTS = {
    "1": {"name": "کنسرو ماهی", "cost": 500, "time": 60, "base_sell": 800, "min_level": 1},
    "2": {"name": "اسباب‌بازی پیشی", "cost": 2000, "time": 180, "base_sell": 3200, "min_level": 2},
    "3": {"name": "برج خارش گربه", "cost": 8000, "time": 600, "base_sell": 14000, "min_level": 3}
}

# تولید شماره حساب اختصاصی ۱۰ رقمی منحصر به فرد با پیش‌فرض 6037
def generate_card_number(user_id: int) -> str:
    prefix = "6037"
    suffix = str(user_id).zfill(6)[-6:]
    return f"{prefix}{suffix}"

# ثبت یا دریافت اطلاعات کاربر با ساخت دیتابیس امن
def get_user(user_id: int):
    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        card_num = generate_card_number(user_id)
        cursor.execute(
            "INSERT INTO users (user_id, card_number, cat_last_claim) VALUES (?, ?, ?)",
            (user_id, card_num, time.time())
        )
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()

    conn.close()
    return user

# پارس کردن دقیق مبالغ (پشتیبانی از k, m, ک, م و اعداد فارسی/انگلیسی)
def parse_amount(text: str) -> float:
    text = str(text).strip().lower()
    text = text.replace("ک", "k").replace("م", "m")
    
    # تبدیل اعداد فارسی به انگلیسی
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    english_digits = "0123456789"
    translation_table = str.maketrans(persian_digits, english_digits)
    text = text.translate(translation_table)

    match = re.match(r"^(\d+(?:\.\d+)?)\s*([km]?)$", text)
    if not match:
        raise ValueError("فرمت مبلغ وارد شده معتبر نیست.")

    val, unit = float(match.group(1)), match.group(2)
    if unit == 'k':
        val *= 1000
    elif unit == 'm':
        val *= 1000000
    return val

# ارسال اطلاع‌رسانی پی‌وی به‌صورت امن
async def send_pv_notify(context: ContextTypes.DEFAULT_TYPE, user_id: int, message: str):
    try:
        await context.bot.send_message(chat_id=user_id, text=message, parse_mode="Markdown")
    except Exception as e:
        logger.warning(f"Could not send PV notify to {user_id}: {e}")

# نرخ نوسانی فروش کارخانه
def calculate_dynamic_sell_price(base_price: float) -> int:
    multiplier = random.uniform(0.85, 1.45)
    return int(base_price * multiplier)
    # ==================================================
# 🟢 بخش ۲-الف: دستور میو/مع و پروفایل
# ==================================================

async def meow_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    last_time = user[9] or 0
    now = time.time()
    cooldown = 180  # ۳ دقیقه = ۱۸۰ ثانیه دقیق

    if now - last_time < cooldown:
        rem_seconds = int(cooldown - (now - last_time))
        mins = rem_seconds // 60
        secs = rem_seconds % 60
        
        time_str = ""
        if mins > 0:
            time_str += f"{mins} دقیقه و "
        time_str += f"{secs} ثانیه"

        await update.message.reply_text(
            f"⏳ **پیشی شما هنوز خسته است!**\nلطفاً **{time_str}** دیگر صبر کنید و مجدداً «میو» کنید.",
            parse_mode="Markdown"
        )
        return

    # تولید عدد رندوم بین ۶۰ تا ۲۲۰ میوپوینت
    random_points = random.randint(60, 220)

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET wallet = wallet + ?, meow_count = meow_count + 1, last_meow_time = ? WHERE user_id = ?",
        (random_points, now, user_id)
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"🐾 **مییییئو!** شما **{random_points:,}** میوپوینت به دست آوردید!\n"
        f"⏱️ تایمر بعدی: ۳ دقیقه دیگر.",
        parse_mode="Markdown"
    )

async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_user = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    user = get_user(target_user.id)

    wallet, bank, card_num = user[1], user[2], user[3]
    cat_level, cat_name, meow_count = user[4], user[5], user[8]

    # محاسبه دقیق لول کاربر
    user_level = (meow_count // 10) + 1
    meows_needed = 10 - (meow_count % 10)
    if meows_needed == 0:
        meows_needed = 10

    profile_text = (
        f"👤 **پروفایل کاربر:** {target_user.first_name}\n"
        f"🆔 **شناسه تلگرام:** `{target_user.id}`\n"
        f"💳 **شماره حساب بانکی:** `{card_num}`\n"
        f"🏆 **سطح (لول) کاربر:** {user_level}\n"
        f"🐾 **تعداد کل میو/مع:** {meow_count:,}\n"
        f"🎯 **میو/مع مانده تا لول بعدی:** **{meows_needed}** عدد\n\n"
        f"💵 **کیف پول:** {int(wallet):,} میو\n"
        f"🏦 **بانک:** {int(bank):,} میو\n"
        f"🐱 **پیشی شما:** {cat_name} (لول {cat_level})"
    )

    await update.message.reply_text(profile_text, parse_mode="Markdown")
    # ==================================================
# 🟢 بخش ۲-ب: مدیریت اختصاصی پیشی
# ==================================================

async def cat_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    cat_level = user[4]
    cat_name = user[5]
    cat_food = user[6]
    last_claim = user[7]

    mps = cat_level * 2
    now = time.time()
    produced = int((now - last_claim) * mps) if last_claim > 0 else 0

    upgrade_cost = cat_level * 500

    buttons = [
        [InlineKeyboardButton(f"📥 برداشت تولیدات ({produced:,} میو)", callback_data="cat_claim")],
        [InlineKeyboardButton(f"🚀 ارتقا لول گربه ({upgrade_cost:,} میو)", callback_data="cat_upgrade")],
        [InlineKeyboardButton("✍️ تغییر نام پیشی", callback_data="cat_change_name")]
    ]

    text = (
        f"🐱 **پنل اختصاصی {cat_name}**\n\n"
        f"⭐ **سطح گربه:** {cat_level}\n"
        f"🍗 **سیر بودن:** {cat_food}%\n"
        f"⚡ **نرخ تولید:** {mps} میوپوینت در ثانیه\n"
        f"💰 **میوپوینت آماده برداشت:** **{produced:,}** میو"
    )

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
    # ==================================================
# 🟢 بخش ۳-الف: سیستم کامل بانک
# ==================================================

async def bank_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    meow_count = user[8]
    user_level = (meow_count // 10) + 1

    if user_level < 2:
        await update.message.reply_text("🔒 **بخش بانک نیازمند رسیدن کاربر به لول ۲ است!**")
        return

    wallet, bank, card_num = user[1], user[2], user[3]

    text = (
        f"🏦 **بانک مرکزی میوپوینت**\n\n"
        f"💳 **شماره حساب شما:** `{card_num}`\n"
        f"💵 **موجودی کیف پول:** {int(wallet):,} میو\n"
        f"🏦 **موجودی حساب بانک:** {int(bank):,} میو\n"
        f"📈 **سود روزانه بانک:** ۳٪\n\n"
        f"🔹 **دستورات بانک:**\n"
        f"▫️ `واریز [مبلغ]`\n"
        f"▫️ `برداشت [مبلغ]`\n"
        f"▫️ `انتقال بانکی [شماره حساب] [مبلغ]`"
    )

    await update.message.reply_text(text, parse_mode="Markdown")

async def bank_deposit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text_parts = update.message.text.split()

    if len(text_parts) < 2:
        await update.message.reply_text("⚠️ لطفاً مبلغ را وارد کنید. مثال: `واریز 5000` یا `واریز 10k`", parse_mode="Markdown")
        return

    try:
        amount = parse_amount(text_parts[1])
    except Exception:
        await update.message.reply_text("❌ مبلغ وارد شده معتبر نیست.")
        return

    user = get_user(user_id)
    if user[1] < amount:
        await update.message.reply_text(f"❌ موجودی کیف پول کافی نیست! موجودی: {int(user[1]):,} میو")
        return

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET wallet = wallet - ?, bank = bank + ? WHERE user_id = ?", (amount, amount, user_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ مبلغ **{int(amount):,}** میوپوینت به حساب بانک واریز شد.", parse_mode="Markdown")

async def bank_withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text_parts = update.message.text.split()

    if len(text_parts) < 2:
        await update.message.reply_text("⚠️ لطفاً مبلغ را وارد کنید. مثال: `برداشت 5000`", parse_mode="Markdown")
        return

    try:
        amount = parse_amount(text_parts[1])
    except Exception:
        await update.message.reply_text("❌ مبلغ وارد شده معتبر نیست.")
        return

    user = get_user(user_id)
    if user[2] < amount:
        await update.message.reply_text(f"❌ موجودی بانک کافی نیست! موجودی: {int(user[2]):,} میو")
        return

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET bank = bank - ?, wallet = wallet + ? WHERE user_id = ?", (amount, amount, user_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ مبلغ **{int(amount):,}** میوپوینت از بانک برداشت شد.", parse_mode="Markdown")
    # ==================================================
# 🟢 بخش ۳-ب: سیستم انتقال وجه بدون خطا
# ==================================================

async def bank_transfer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text_parts = update.message.text.split()

    if len(text_parts) < 3:
        await update.message.reply_text("⚠️ فرمت صحیح: `انتقال بانکی [شماره حساب] [مبلغ]`\nمثال: `انتقال بانکی 6037001234 10k`", parse_mode="Markdown")
        return

    target_card = text_parts[1].strip()
    try:
        amount = parse_amount(text_parts[2])
    except Exception:
        await update.message.reply_text("❌ مبلغ وارد شده معتبر نیست.")
        return

    if amount < 100:
        await update.message.reply_text("⚠️ حداقل مبلغ برای انتقال بانکی ۱۰۰ میوپوینت است.")
        return

    sender = get_user(user_id)
    if sender[2] < amount:
        await update.message.reply_text(f"❌ موجودی حساب بانک شما کافی نیست! موجودی بانک: {int(sender[2]):,} میو")
        return

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE card_number = ?", (target_card,))
    target_row = cursor.fetchone()

    if not target_row:
        conn.close()
        await update.message.reply_text("❌ شماره حساب مقصد در سیستم پیدا نشد!")
        return

    target_id = target_row[0]

    if target_id == user_id:
        conn.close()
        await update.message.reply_text("❌ انتقال به شماره حساب خودتان امکان‌پذیر نیست!")
        return

    # کسر از بانک فرستنده و افزوده شدن به بانک گیرنده
    cursor.execute("UPDATE users SET bank = bank - ? WHERE user_id = ?", (amount, user_id))
    cursor.execute("UPDATE users SET bank = bank + ? WHERE user_id = ?", (amount, target_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ **انتقال بانکی با موفقیت انجام شد!**\n\n"
        f"💳 شماره حساب مقصد: `{target_card}`\n"
        f"💰 مبلغ: **{int(amount):,}** میوپوینت",
        parse_mode="Markdown"
    )

    await send_pv_notify(
        context, target_id,
        f"🏦 **واریز به حساب بانک!**\nمبلغ **{int(amount):,}** میوپوینت از شماره حساب `{sender[3]}` به حساب شما واریز شد."
    )

async def direct_transfer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ این دستور را روی پیام کاربر مقصد ریپلی کنید!\nمثال: `انتقال میویی 5000`", parse_mode="Markdown")
        return

    user_id = update.effective_user.id
    target_user = update.message.reply_to_message.from_user
    
    if target_user.id == user_id:
        await update.message.reply_text("❌ انتقال میوپوینت به خودتان مجاز نیست!")
        return

    parts = update.message.text.split()
    if len(parts) < 2:
        await update.message.reply_text("⚠️ لطفاً مبلغ را وارد کنید. مثال: `انتقال میویی 10k`", parse_mode="Markdown")
        return

    try:
        amount = parse_amount(parts[1])
    except Exception:
        await update.message.reply_text("❌ مبلغ وارد شده معتبر نیست.")
        return

    user = get_user(user_id)
    if user[1] < amount:
        await update.message.reply_text(f"❌ موجودی کیف پول کافی نیست! موجودی: {int(user[1]):,} میو")
        return

    context.user_data['pending_transfer'] = {
        'target_id': target_user.id,
        'target_name': target_user.first_name,
        'amount': amount
    }

    buttons = [
        [
            InlineKeyboardButton("✅ تایید انتقال", callback_data="confirm_direct_transfer"),
            InlineKeyboardButton("❌ لغو", callback_data="cancel_direct_transfer")
        ]
    ]

    await update.message.reply_text(
        f"❓ **آیا از انتقال مبلغ {int(amount):,} میوپوینت به {target_user.first_name} اطمینان دارید؟**",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
        )
    # ==================================================
# 🟢 بخش ۴-الف: سیستم صید ماهی و یخچال
# ==================================================

async def fish_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    rand = random.random()
    if rand < 0.50:
        emoji = "🐟"
    elif rand < 0.80:
        emoji = "🐠"
    elif rand < 0.95:
        emoji = "🐡"
    else:
        emoji = "🦈"

    fish_info = FISH_DATA[emoji]

    buttons = [
        [InlineKeyboardButton(f"💰 فروش ({fish_info['price']:,} میو)", callback_data=f"fish_sell_{emoji}")],
        [InlineKeyboardButton(f"🍖 دادن به پیشی (+{fish_info['food']}% غذا)", callback_data=f"fish_feed_{emoji}")],
        [InlineKeyboardButton("❄️ ذخیره در یخچال", callback_data=f"fish_keep_{emoji}")]
    ]

    await update.message.reply_text(
        f"🎣 **شما یک {fish_info['name']} ({emoji}) صید کردید!**\n\nاقدام مورد نظر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )

async def fridge_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    cursor.execute("SELECT fish_type, count FROM fridge WHERE user_id = ? AND count > 0", (user_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("❄️ **یخچال شما خالی است!**")
        return

    text = "❄️ **محتویات یخچال ماهی شما:**\n\n"
    for row in rows:
        f_type, count = row[0], row[1]
        info = FISH_DATA.get(f_type, {"name": "ماهی"})
        text += f"▫️ {f_type} {info['name']}: **{count}** عدد\n"

    await update.message.reply_text(text, parse_mode="Markdown")
    # ==================================================
# 🟢 بخش ۴-ب: مدیریت تولید و فروش محصولات کارخانه
# ==================================================

async def factory_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    meow_count = user[8]
    user_level = (meow_count // 10) + 1

    if user_level < 4:
        await update.message.reply_text("🔒 **بخش کارخانه نیازمند لول ۴ است!**")
        return

    factory_level = user[10]
    producing_item = user[11]
    produce_amount = user[12]
    produce_start_time = user[13]

    if producing_item:
        item_info = next((v for k, v in PRODUCTS.items() if v['name'] == producing_item), None)
        elapsed = time.time() - produce_start_time
        total_time = item_info['time'] if item_info else 100

        if elapsed >= total_time:
            dynamic_price = calculate_dynamic_sell_price(item_info['base_sell']) if item_info else 1000
            total_sell = dynamic_price * produce_amount

            buttons = [[InlineKeyboardButton(f"💰 فروش محصولات ({total_sell:,} میو)", callback_data="factory_sell")]]
            await update.message.reply_text(
                f"🏭 **تولید محصول {producing_item} به پایان رسید!**\n"
                f"📦 تعداد: {produce_amount} عدد\n"
                f"📈 نرخ فعلی بازار: {dynamic_price:,} میو بر هر عدد\n\n"
                f"جهت دریافت سود کلیک کنید:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="Markdown"
            )
        else:
            rem = int(total_time - elapsed)
            buttons = [[InlineKeyboardButton("🛑 لغو تولید (بازگشت اصل پول)", callback_data="factory_cancel")]]
            await update.message.reply_text(
                f"🏭 **کارخانه در حال تولید {producing_item} است...**\n"
                f"⏱️ زمان باقی‌مانده: {rem} ثانیه",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="Markdown"
            )
    else:
        text = f"🏭 **پنل کارخانه (لول {factory_level})**\n\nمحصول مورد نظر جهت ساخت را انتخاب کنید:"
        buttons = []
        for k, v in PRODUCTS.items():
            buttons.append([InlineKeyboardButton(f"📦 {v['name']} (هزینه: {v['cost']:,} میو)", callback_data=f"factory_start_{k}")])

        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
        # ==================================================
# 🟢 بخش ۵-الف: ساختار کازینو و انتخاب پیش‌بینی
# ==================================================

CASINO_LOBBIES = {}

async def casino_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("🎰 اسلات", callback_data="casino_select_slot")],
        [InlineKeyboardButton("🎲 تاس (عادی + پیش‌بینی زوج/فرد)", callback_data="casino_select_dice")],
        [InlineKeyboardButton("🎳 بولینگ", callback_data="casino_select_bowling")]
    ]
    await update.message.reply_text(
        "🎰 **کازینو میوپوینت:**\nلطفاً بازی مورد نظر خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )

async def casino_dice_options(query):
    buttons = [
        [
            InlineKeyboardButton("🎯 ۱ نفره عادی", callback_data="casino_mode_dice_1"),
            InlineKeyboardButton("👥 ۲ نفره", callback_data="casino_mode_dice_2"),
            InlineKeyboardButton("👨‍👩‍👦 ۳ نفره", callback_data="casino_mode_dice_3")
        ],
        [
            InlineKeyboardButton("🔵 پیش‌بینی تاس «زوج» (۲x)", callback_data="casino_dice_even"),
            InlineKeyboardButton("🔴 پیش‌بینی تاس «فرد» (۲x)", callback_data="casino_dice_odd")
        ]
    ]
    await query.edit_message_text(
        "🎲 **تنظیمات بازی تاس:**\nحالت بازی یا پیش‌بینی زوج/فرد را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )
    # ==================================================
# 🟢 بخش ۵-ب: پردازشگر متنی بدون خطا (گروه اولویت بالا)
# ==================================================

async def custom_text_inputs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # انصراف در صورت ارسال کلمات خاص
    if text.lower() in ["انصراف", "لغو", "/cancel"]:
        if context.user_data.get('waiting_for_cat_name') or context.user_data.get('casino_custom'):
            context.user_data.pop('waiting_for_cat_name', None)
            context.user_data.pop('casino_custom', None)
            await update.message.reply_text("❌ عملیات جاری لغو گردید.")
            return

    # پردازش تغییر نام پیشی
    if context.user_data.get('waiting_for_cat_name'):
        if len(text) > 15 or len(text) < 1:
            await update.message.reply_text("❌ نام گربه باید بین ۱ تا ۱۵ کاراکتر باشد.")
            return

        conn = sqlite3.connect("meow_point.db")
        conn.cursor().execute("UPDATE users SET cat_name = ? WHERE user_id = ?", (text, user_id))
        conn.commit()
        conn.close()

        context.user_data.pop('waiting_for_cat_name', None)
        await update.message.reply_text(f"🎉 نام پیشی به **«{text}»** تغییر کرد!", parse_mode="Markdown")
        return

    # پردازش شرط دلخواه کازینو
    casino_data = context.user_data.get('casino_custom')
    if casino_data:
        try:
            bet_amount = parse_amount(text)
        except Exception:
            await update.message.reply_text("❌ مبلغ معتبر نیست! مثلاً `20k` یا «انصراف» را بفرستید.")
            return

        if bet_amount < 100:
            await update.message.reply_text("⚠️ حداقل شرط ۱۰۰ میوپوینت است.")
            return

        user = get_user(user_id)
        if user[1] < bet_amount:
            await update.message.reply_text(f"❌ موجودی کافی نیست! موجودی: {int(user[1]):,} میو")
            return

        context.user_data.pop('casino_custom', None)
        game_type = casino_data['game_type']
        players_count = casino_data['players']
        prediction = casino_data.get('prediction', None)

        conn = sqlite3.connect("meow_point.db")
        conn.cursor().execute("UPDATE users SET wallet = wallet - ? WHERE user_id = ?", (bet_amount, user_id))
        conn.commit()
        conn.close()

        # اجرای شرط‌بندی زوج/فرد
        if prediction in ["even", "odd"]:
            await update.message.reply_text(f"🎲 **پرتاب تاس برای پیش‌بینی «{'زوج' if prediction == 'even' else 'فرد'}» با شرط {int(bet_amount):,}...**", parse_mode="Markdown")
            msg = await context.bot.send_dice(chat_id=update.message.chat_id, emoji="🎲")
            val = msg.dice.value
            await asyncio.sleep(2.5)

            is_even = (val % 2 == 0)
            win = (prediction == "even" and is_even) or (prediction == "odd" and not is_even)

            if win:
                win_amt = bet_amount * 2
                conn = sqlite3.connect("meow_point.db")
                conn.cursor().execute("UPDATE users SET wallet = wallet + ? WHERE user_id = ?", (win_amt, user_id))
                conn.commit()
                conn.close()
                await update.message.reply_text(f"🎉 **تاس عدد {val} آمد!** شما برنده **{int(win_amt):,}** میوپوینت شدید!", parse_mode="Markdown")
            else:
                await update.message.reply_text(f"❌ **تاس عدد {val} آمد!** پیش‌بینی شما اشتباه بود.", parse_mode="Markdown")
            return

        # تک‌نفره عادی
        game_emoji = {"slot": "🎰", "dice": "🎲", "bowling": "🎳"}.get(game_type, "🎲")
        if players_count == 1:
            await update.message.reply_text(f"🎮 **بازی تک‌نفره با شرط {int(bet_amount):,} میو...**", parse_mode="Markdown")
            msg = await context.bot.send_dice(chat_id=update.message.chat_id, emoji=game_emoji)
            val = msg.dice.value
            await asyncio.sleep(2.5)

            is_win = (val == 64 if game_type == "slot" else val >= 4)
            win_amt = bet_amount * 2

            if is_win:
                conn = sqlite3.connect("meow_point.db")
                conn.cursor().execute("UPDATE users SET wallet = wallet + ? WHERE user_id = ?", (win_amt, user_id))
                conn.commit()
                conn.close()
                await update.message.reply_text(f"🎉 **برنده شدید!** مبلغ **{int(win_amt):,}** میوپوینت دریافت کردید.", parse_mode="Markdown")
            else:
                await update.message.reply_text(f"❌ این بار متأسفانه برنده نشدید.", parse_mode="Markdown")
        else:
            lobby_id = f"{user_id}_{int(time.time())}"
            CASINO_LOBBIES[lobby_id] = {
                "type": game_type, "max_players": players_count, "bet": bet_amount,
                "players": [user_id], "names": [update.effective_user.first_name], "pot": bet_amount
            }
            buttons = [[InlineKeyboardButton("➕ ورود به بازی", callback_data=f"casino_join_{lobby_id}")]]
            await update.message.reply_text(
                f"🎮 **لابی {players_count} نفره ساخته شد!**\n💰 ورودی: {int(bet_amount):,} میو\n⏳ منتظر اعضا...",
                reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
            )
            # ==================================================
# 🟢 بخش ۶-الف: هندلرهای تاس، اسم گربه و کالبک‌ها
# ==================================================

async def handle_user_dice_throw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    dice_msg = update.message.dice
    
    if not dice_msg:
        return

    game = context.user_data.get('pending_casino_game')
    if not game:
        return

    expected_emoji = {"dice": "🎲", "slot": "🎰", "bowling": "🎳"}.get(game['type'])
    
    if dice_msg.emoji != expected_emoji:
        await update.message.reply_text(f"⚠️ لطفا دقیقاً ایموجی {expected_emoji} را ارسال کنید!")
        return

    val = dice_msg.value
    bet = game['bet']
    game_type = game['type']
    win_amount = 0
    is_win = False
    result_text = ""

    # ۱. پردازش بازی تاس
    if game_type == "dice":
        pred = game['prediction']
        if pred == "even" and val % 2 == 0:
            is_win = True
            win_amount = bet * 1.5
            result_text = f"🎉 **تاس {val} آمد (زوج)!** شما برنده **{int(win_amount):,}** میوپوینت شدید (ضریب ۱.۵)."
        elif pred == "odd" and val % 2 != 0:
            is_win = True
            win_amount = bet * 1.5
            result_text = f"🎉 **تاس {val} آمد (فرد)!** شما برنده **{int(win_amount):,}** میوپوینت شدید (ضریب ۱.۵)."
        elif pred.isdigit() and int(pred) == val:
            is_win = True
            win_amount = bet * 2.0
            result_text = f"🎯 **تاس دقیقاً {val} آمد!** شما برنده **{int(win_amount):,}** میوپوینت شدید (ضریب ۲)."
        else:
            result_text = f"❌ **تاس عدد {val} آمد!** پیش‌بینی شما ({pred}) اشتباه بود."

    # ۲. پردازش بازی اسلات (کدهای ۱ تا ۶۴)
    elif game_type == "slot":
        r1 = (val - 1) % 4 + 1
        r2 = ((val - 1) // 4) % 4 + 1
        r3 = ((val - 1) // 16) % 4 + 1

        if val == 64:  # Jackpot 777
            is_win = True
            win_amount = bet * 5.0
            result_text = f"💥 **جک‌پات 777!** (کد {val})\nشما برنده **{int(win_amount):,}** میوپوینت شدید! (ضریب ۵)"
        elif r1 == r2 == r3:  # ۳ نماد همسان
            is_win = True
            win_amount = bet * 3.0
            result_text = f"🎉 **۳ نماد همسان!** شما برنده **{int(win_amount):,}** میوپوینت شدید! (ضریب ۳)"
        elif r1 == r2 or r2 == r3 or r1 == r3:  # جفت
            is_win = True
            win_amount = bet * 1.5
            result_text = f"✨ **دو نماد مشابه (جفت)!** شما برنده **{int(win_amount):,}** میوپوینت شدید! (ضریب ۱.۵)"
        else:
            result_text = f"❌ پوچ شد! ترکیب برنده‌ای ننشست."

    # ۳. پردازش بازی بولینگ
    elif game_type == "bowling":
        if val == 6:
            is_win = True
            win_amount = bet * 2.5
            result_text = f"🎳 **استرایک کامل!** تمام پین‌ها ریخت.\nبرنده **{int(win_amount):,}** میوپوینت شدید! (ضریب ۲.۵)"
        elif val >= 4:
            is_win = True
            win_amount = bet * 1.5
            result_text = f"🎉 **امتیاز {val}!** شما برنده **{int(win_amount):,}** میوپوینت شدید! (ضریب ۱.۵)"
        else:
            result_text = f"❌ تنها {val} پین افتاد! شرط را باختید."

    if is_win:
        conn = sqlite3.connect("meow_point.db")
        conn.cursor().execute("UPDATE users SET wallet = wallet + ? WHERE user_id = ?", (win_amount, user_id))
        conn.commit()
        conn.close()

    await update.message.reply_text(result_text, parse_mode="Markdown")
    context.user_data.pop('pending_casino_game', None)


# 🐾 هندلر هوشمند تشخیص اسم گربه و باز کردن داشبورد
async def cat_trigger_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    text = update.message.text.strip()
    user_id = update.effective_user.id
    user = get_user(user_id)
    cat_name = user[3] if len(user) > 3 and user[3] else None

    # بررسی کلمات کلیدی یا اسم اختصاصی گربه
    if text in ["پیشی", "گربه"] or (cat_name and text.lower() == cat_name.lower()):
        await cat_dashboard(update, context)


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    try:
        await query.answer()
    except Exception:
        pass

    # ۱. مدیریت انتقال مستقیم
    if data == "confirm_direct_transfer":
        pt = context.user_data.get('pending_transfer')
        if not pt:
            await query.edit_message_text("❌ تراکنش منقضی شده یا نامعتبر است.")
            return

        user = get_user(user_id)
        if user[1] < pt['amount']:
            await query.edit_message_text("❌ موجودی کیف پول شما کافی نیست!")
            return

        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET wallet = wallet - ? WHERE user_id = ?", (pt['amount'], user_id))
        cursor.execute("UPDATE users SET wallet = wallet + ? WHERE user_id = ?", (pt['amount'], pt['target_id']))
        conn.commit()
        conn.close()

        await query.edit_message_text(
            f"✅ **انتقال موفقیت‌آمیز بود!**\n\n"
            f"👤 دریافت‌کننده: {pt['target_name']}\n"
            f"💰 مبلغ: **{int(pt['amount']):,}** میوپوینت",
            parse_mode="Markdown"
        )
        await send_pv_notify(
            context,
            pt['target_id'],
            f"💸 **دریافت میوپوینت!**\nمبلغ **{int(pt['amount']):,}** میوپوینت از طرف {query.from_user.first_name} واریز شد."
        )
        context.user_data.pop('pending_transfer', None)

    elif data == "cancel_direct_transfer":
        context.user_data.pop('pending_transfer', None)
        await query.edit_message_text("❌ عملیات انتقال مستقیم لغو شد.")

    # ۲. مدیریت گربه
    elif data in ["cat_change_name", "cat_rename"]:
        context.user_data['waiting_for_cat_name'] = True
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="✍️ **لطفاً نام جدید پیشی خود را ارسال کنید:**",
            parse_mode="Markdown"
        )

    elif data == "cat_upgrade":
        user = get_user(user_id)
        cost = user[4] * 500
        if user[1] < cost:
            await query.message.reply_text(f"❌ موجودی کافی نیست! هزینه ارتقا: {cost:,} میوپوینت")
            return

        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET wallet = wallet - ?, cat_level = cat_level + 1 WHERE user_id = ?", (cost, user_id))
        conn.commit()
        conn.close()

        await query.message.reply_text(f"🎉 **تبریک!** سطح پیشی شما به **{user[4] + 1}** ارتقا یافت.", parse_mode="Markdown")

    elif data == "cat_claim":
        user = get_user(user_id)
        mps = user[4] * 2
        now = time.time()
        produced = int((now - user[7]) * mps) if user[7] > 0 else 0

        if produced <= 0:
            await query.message.reply_text("❌ هنوز میوپوینتی برای برداشت تولید نشده است!")
            return

        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET wallet = wallet + ?, cat_last_claim = ? WHERE user_id = ?", (produced, now, user_id))
        conn.commit()
        conn.close()

        await query.message.reply_text(f"✅ مبلغ **{produced:,}** میوپوینت با موفقیت برداشت شد.", parse_mode="Markdown")

    # ۳. مدیریت ماهی و یخچال
    elif data.startswith("fish_sell_"):
        emoji = data.split("_")[2]
        info = FISH_DATA.get(emoji, {"price": 150})
        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET wallet = wallet + ? WHERE user_id = ?", (info['price'], user_id))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"💰 ماهی {emoji} به قیمت **{info['price']:,}** میوپوینت فروخته شد.", parse_mode="Markdown")

    elif data.startswith("fish_feed_"):
        emoji = data.split("_")[2]
        info = FISH_DATA.get(emoji, {"food": 10})
        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET cat_food = MIN(100, cat_food + ?) WHERE user_id = ?", (info['food'], user_id))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"🍖 ماهی {emoji} به پیشی داده شد! (+{info['food']}% سیر شدن)", parse_mode="Markdown")

    elif data.startswith("fish_keep_"):
        emoji = data.split("_")[2]
        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        cursor.execute("SELECT count FROM fridge WHERE user_id = ? AND fish_type = ?", (user_id, emoji))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE fridge SET count = count + 1 WHERE user_id = ? AND fish_type = ?", (user_id, emoji))
        else:
            cursor.execute("INSERT INTO fridge (user_id, fish_type, count) VALUES (?, ?, 1)", (user_id, emoji))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"❄️ ماهی {emoji} به یخچال منتقل شد.", parse_mode="Markdown")

    # ۴. مدیریت کارخانه
    elif data.startswith("factory_start_"):
        product_id = data.split("_")[2]
        product = PRODUCTS.get(product_id)
        if not product:
            await query.message.reply_text("❌ محصول معتبر نیست.")
            return

        user = get_user(user_id)
        if user[1] < product['cost']:
            await query.message.reply_text(f"❌ موجودی کافی نیست! هزینه: {product['cost']:,} میو")
            return

        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET wallet = wallet - ?, producing_item = ?, produce_amount = 1, produce_start_time = ?, produce_cost = ? WHERE user_id = ?",
            (product['cost'], product['name'], time.time(), product['cost'], user_id)
        )
        conn.commit()
        conn.close()

        await query.edit_message_text(f"🏭 **خط تولید {product['name']} فعال شد!**\n⏱️ زمان ساخت: {product['time']} ثانیه", parse_mode="Markdown")

    elif data == "factory_sell":
        user = get_user(user_id)
        producing_item = user[11]
        produce_amount = user[12]

        if not producing_item:
            await query.edit_message_text("❌ هیچ محصول آماده‌ای برای فروش وجود ندارد.")
            return

        item_info = next((v for k, v in PRODUCTS.items() if v['name'] == producing_item), None)
        base_sell = item_info['base_sell'] if item_info else 1000
        dynamic_price = calculate_dynamic_sell_price(base_sell)
        total_price = dynamic_price * produce_amount

        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET wallet = wallet + ?, producing_item = NULL, produce_amount = 0, produce_start_time = 0, produce_cost = 0 WHERE user_id = ?",
            (total_price, user_id)
        )
        conn.commit()
        conn.close()

        await query.edit_message_text(f"💰 **محصولات فروخته شدند!**\nمجموع دریافتی: **{total_price:,}** میوپوینت", parse_mode="Markdown")

    elif data == "factory_cancel":
        user = get_user(user_id)
        refund = user[14]
        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET wallet = wallet + ?, producing_item = NULL, produce_amount = 0, produce_start_time = 0, produce_cost = 0 WHERE user_id = ?",
            (refund, user_id)
        )
        conn.commit()
        conn.close()
        await query.edit_message_text(f"🛑 خط تولید لغو شد و {int(refund):,} میو به کیف پول بازگشت.")

    # ۵. مدیریت کازینو و منوهای ۳ مرحله‌ای
    elif data == "casino_select_slot":
        buttons = [[InlineKeyboardButton("👤 ۱ نفره (تک بازی)", callback_data="casino_mode_slot_1")]]
        await query.edit_message_text("🎰 **بازی اسلات:** حالت بازی را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

    elif data == "casino_select_dice":
        buttons = [[InlineKeyboardButton("👤 ۱ نفره (تک بازی)", callback_data="casino_mode_dice_1")]]
        await query.edit_message_text("🎲 **بازی تاس:** حالت بازی را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

    elif data == "casino_select_bowling":
        buttons = [[InlineKeyboardButton("👤 ۱ نفره (تک بازی)", callback_data="casino_mode_bowling_1")]]
        await query.edit_message_text("🎳 **بازی بولینگ:** حالت بازی را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

    elif data.startswith("casino_mode_"):
        parts = data.split("_")
        game_type = parts[2]
        players = int(parts[3])

        buttons = [
            [
                InlineKeyboardButton("💰 ۱,۰۰۰", callback_data=f"casino_start_{game_type}_{players}_1000"),
                InlineKeyboardButton("💰 ۵,۰۰۰", callback_data=f"casino_start_{game_type}_{players}_5000")
            ],
            [
                InlineKeyboardButton("💰 ۱۰,۰۰۰", callback_data=f"casino_start_{game_type}_{players}_10000"),
                InlineKeyboardButton("✏️ مبلغ دلخواه", callback_data=f"casino_custom_{game_type}_{players}")
            ]
        ]
        await query.edit_message_text(f"🎮 **مرحله ۲: مبلغ شرط‌بندی برای {game_type.upper()} را انتخاب کنید:**", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

    elif data.startswith("casino_start_"):
        parts = data.split("_")
        game_type = parts[2]
        players = int(parts[3])
        bet_amount = float(parts[4])

        user = get_user(user_id)
        if user[1] < bet_amount:
            await query.message.reply_text(f"❌ موجودی کافی نیست! موجودی شما: {int(user[1]):,} میو")
            return

        if game_type == "dice" and len(parts) == 5:
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
            await query.edit_message_text("🎲 **مرحله ۳: پیش‌بینی خود از نتیجه تاس را انتخاب کنید:**", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
            return

        conn = sqlite3.connect("meow_point.db")
        conn.cursor().execute("UPDATE users SET wallet = wallet - ? WHERE user_id = ?", (bet_amount, user_id))
        conn.commit()
        conn.close()

        pred = parts[5] if len(parts) >= 6 else None
        context.user_data['pending_casino_game'] = {'type': game_type, 'bet': bet_amount, 'prediction': pred}

        emoji_icon = {"slot": "🎰", "dice": "🎲", "bowling": "🎳"}.get(game_type)
        await query.edit_message_text(
            f"✅ شرط شما به مبلغ **{int(bet_amount):,}** میوپوینت ثبت شد.\n\n"
            f"👇 **حالا لطفاً ایموجی {emoji_icon} را در پاسخ به ربات ارسال کنید!**",
            parse_mode="Markdown"
        )

    elif data.startswith("casino_custom_"):
        parts = data.split("_")
        context.user_data['casino_custom'] = {'game_type': parts[2], 'players': int(parts[3])}
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="✍️ **لطفاً مبلغ شرط‌بندی دلخواه را بفرستید:**\n(مثال: `50k` یا `1.5m`)",
            parse_mode="Markdown"
    )
                # ==================================================
# 🟢 بخش ۶-ب: دستورات ادمین، راهنما و راه اندازی main
# ==================================================

async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    text = update.message.text.strip()
    text_parts = text.split(maxsplit=1)
    # جدا کردن نام دستور بدون یوزرنیم ربات
    cmd = text_parts[0].split('@')[0].lower()

    if cmd == "/admin":
        await update.message.reply_text(
            f"👑 **پنل مدیریت ارشد ربات میوپوینت**\n\n"
            "💰 **مدیریت مالی:**\n"
            "▫️ `/give_points [user_id] [مبلغ]` - اهدای میوپوینت\n"
            "▫️ `/take_points [user_id] [مبلغ]` - کسر میوپوینت\n\n"
            "🐱 **مدیریت لول گربه:**\n"
            "▫️ `/add_cat [user_id] [تعداد]` - افزایش سطح گربه\n"
            "▫️ `/set_cat [user_id] [سطح]` - تنظیم مستقیم سطح گربه\n"
            "▫️ `/max_cat [user_id]` - ارتقای گربه به سطح ۱۰۰\n\n"
            "⭐ **مدیریت لول عمومی کاربر (میو/مع):**\n"
            "▫️ `/add_user_level [user_id] [تعداد]` - افزایش لول عمومی کاربر\n"
            "▫️ `/set_user_level [user_id] [سطح]` - تنظیم مستقیم لول عمومی\n"
            "▫️ `/max_user_level [user_id]` - ارتقای لول عمومی به ۱۰۰\n\n"
            "⚙️ **عمومی:**\n"
            "▫️ `/reset_user [user_id]` - پاکسازی کامل داده‌های کاربر\n"
            "▫️ `/stats` - آمار کامل ربات\n"
            "▫️ `/bc [متن]` - ارسال پیام همگانی",
            parse_mode="Markdown"
        )

    elif cmd == "/stats":
        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), SUM(wallet), SUM(bank), SUM(meow_count) FROM users")
        row = cursor.fetchone()
        conn.close()

        await update.message.reply_text(
            f"📊 **آمار دیتابیس ربات:**\n\n"
            f"👥 **تعداد کاربران:** {row[0] or 0:,}\n"
            f"💵 **کل موجودی کیف پول‌ها:** {int(row[1] or 0):,} میو\n"
            f"🏦 **کل موجودی بانک‌ها:** {int(row[2] or 0):,} میو\n"
            f"🐾 **تعداد کل میو/مع:** {row[3] or 0:,}",
            parse_mode="Markdown"
        )

    elif cmd == "/give_points":
        args = text.split()
        if len(args) >= 3:
            try:
                target_id = int(args[1])
                amt = parse_amount(args[2])
                conn = sqlite3.connect("meow_point.db")
                conn.cursor().execute("UPDATE users SET wallet = wallet + ? WHERE user_id = ?", (amt, target_id))
                conn.commit()
                conn.close()
                await update.message.reply_text(f"✅ مبلغ **{int(amt):,}** میوپوینت به کاربر `{target_id}` اعطا شد.", parse_mode="Markdown")
                await send_pv_notify(context, target_id, f"🎁 مبلغ **{int(amt):,}** میوپوینت از طرف مدیریت اعطا شد.")
            except Exception as e:
                await update.message.reply_text(f"❌ خطا: {e}")

    elif cmd == "/take_points":
        args = text.split()
        if len(args) >= 3:
            try:
                target_id = int(args[1])
                amt = parse_amount(args[2])
                conn = sqlite3.connect("meow_point.db")
                conn.cursor().execute("UPDATE users SET wallet = MAX(0, wallet - ?) WHERE user_id = ?", (amt, target_id))
                conn.commit()
                conn.close()
                await update.message.reply_text(f"✅ مبلغ **{int(amt):,}** میوپوینت از کاربر `{target_id}` کسر شد.", parse_mode="Markdown")
            except Exception as e:
                await update.message.reply_text(f"❌ خطا: {e}")

    # --- مدیریت سطح گربه ---
    elif cmd == "/add_cat":
        args = text.split()
        if len(args) >= 3:
            try:
                target_id, levels = int(args[1]), int(args[2])
                conn = sqlite3.connect("meow_point.db")
                conn.cursor().execute("UPDATE users SET cat_level = cat_level + ? WHERE user_id = ?", (levels, target_id))
                conn.commit()
                conn.close()
                await update.message.reply_text(f"✅ تعداد **{levels}** سطح به گربه کاربر `{target_id}` اضافه شد.", parse_mode="Markdown")
            except Exception as e:
                await update.message.reply_text(f"❌ خطا: {e}")

    elif cmd == "/set_cat":
        args = text.split()
        if len(args) >= 3:
            try:
                target_id, level = int(args[1]), int(args[2])
                conn = sqlite3.connect("meow_point.db")
                conn.cursor().execute("UPDATE users SET cat_level = ? WHERE user_id = ?", (level, target_id))
                conn.commit()
                conn.close()
                await update.message.reply_text(f"✅ سطح گربه کاربر `{target_id}` روی **{level}** تنظیم شد.", parse_mode="Markdown")
            except Exception as e:
                await update.message.reply_text(f"❌ خطا: {e}")

    elif cmd == "/max_cat":
        args = text.split()
        if len(args) >= 2:
            try:
                target_id = int(args[1])
                conn = sqlite3.connect("meow_point.db")
                conn.cursor().execute("UPDATE users SET cat_level = 100 WHERE user_id = ?", (target_id,))
                conn.commit()
                conn.close()
                await update.message.reply_text(f"🚀 گربه کاربر `{target_id}` به سطح ۱۰۰ ارتقا یافت!", parse_mode="Markdown")
            except Exception as e:
                await update.message.reply_text(f"❌ خطا: {e}")

    # --- مدیریت سطح عمومی کاربر (که با میو/مع بالا می‌رود) ---
    elif cmd == "/add_user_level":
        args = text.split()
        if len(args) >= 3:
            try:
                target_id, levels = int(args[1]), int(args[2])
                conn = sqlite3.connect("meow_point.db")
                conn.cursor().execute("UPDATE users SET user_level = user_level + ? WHERE user_id = ?", (levels, target_id))
                conn.commit()
                conn.close()
                await update.message.reply_text(f"✅ تعداد **{levels}** لول به سطح عمومی کاربر `{target_id}` اضافه شد.", parse_mode="Markdown")
            except Exception as e:
                await update.message.reply_text(f"❌ خطا: {e}")

    elif cmd == "/set_user_level":
        args = text.split()
        if len(args) >= 3:
            try:
                target_id, level = int(args[1]), int(args[2])
                conn = sqlite3.connect("meow_point.db")
                conn.cursor().execute("UPDATE users SET user_level = ? WHERE user_id = ?", (level, target_id))
                conn.commit()
                conn.close()
                await update.message.reply_text(f"✅ سطح عمومی کاربر `{target_id}` روی لول **{level}** تنظیم شد.", parse_mode="Markdown")
            except Exception as e:
                await update.message.reply_text(f"❌ خطا: {e}")

    elif cmd == "/max_user_level":
        args = text.split()
        if len(args) >= 2:
            try:
                target_id = int(args[1])
                conn = sqlite3.connect("meow_point.db")
                conn.cursor().execute("UPDATE users SET user_level = 100 WHERE user_id = ?", (target_id,))
                conn.commit()
                conn.close()
                await update.message.reply_text(f"🚀 سطح عمومی کاربر `{target_id}` به لول ۱۰۰ ارتقا یافت!", parse_mode="Markdown")
            except Exception as e:
                await update.message.reply_text(f"❌ خطا: {e}")

    elif cmd == "/reset_user":
        args = text.split()
        if len(args) >= 2:
            try:
                target_id = int(args[1])
                conn = sqlite3.connect("meow_point.db")
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE user_id = ?", (target_id,))
                cursor.execute("DELETE FROM fridge WHERE user_id = ?", (target_id,))
                conn.commit()
                conn.close()
                await update.message.reply_text(f"🗑️ تمامی حساب و داده‌های کاربر `{target_id}` پاکسازی شد.", parse_mode="Markdown")
            except Exception as e:
                await update.message.reply_text(f"❌ خطا: {e}")

    elif cmd == "/bc":
        if len(text_parts) < 2:
            await update.message.reply_text("⚠️ لطفا متن همگانی را وارد کنید.")
            return

        bc_msg = text_parts[1]
        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        all_users = cursor.fetchall()
        conn.close()

        sent_count, fail_count = 0, 0
        for row in all_users:
            try:
                await context.bot.send_message(chat_id=row[0], text=f"📢 **اطلاعیه مدیریت:**\n\n{bc_msg}", parse_mode="Markdown")
                sent_count += 1
                await asyncio.sleep(0.04)
            except Exception:
                fail_count += 1

        await update.message.reply_text(f"✅ ارسال همگانی به پایان رسید.\nموفق: **{sent_count}** | ناموفق: **{fail_count}**", parse_mode="Markdown")


async def help_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 **راهنمای جامع ربات میوپوینت:**\n\n"
        "🐾 `میو` یا `مع` - دریافت میوپوینت رایگان و افزایش لول کاربر\n"
        "👤 `پروفایل` یا `میوهاش` - نمایش اطلاعات و لول کاربر\n"
        "🐱 `پیشی` یا `گربه` (یا صدا زدن با اسم گربه) - مدیریت داشبورد گربه\n"
        "🏦 `بانک` - ورود به پنل بانک، واریز، برداشت و کارت به کارت\n"
        "💸 `انتقال بانکی [شماره حساب] [مبلغ]` - انتقال بانکی\n"
        "💸 `انتقال میویی [مبلغ]` - انتقال روی پیام ریپلی‌شده\n"
        "🎣 `ماهی` - صید ماهی\n"
        "❄️ `یخچال` - انبار ماهی‌ها\n"
        "🏭 `کارخونه` - تولید و فروش محصولات\n"
        "🎰 `کازینو` - اسلات، تاس (زوج/فرد/عدد دقیق) و بولینگ\n"
        "ℹ️ `دستورات ربات` یا `/start` - راهنما"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


# ==================================================
# 🚀 نقطه ورود اصلی ربات (main)
# ==================================================
def main():
    app = Application.builder().token(TOKEN).build()

    # اولویت بالا برای ورودی‌های متنی، اسم گربه و تاس کاربر
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, custom_text_inputs_handler), group=-1)
    app.add_handler(MessageHandler(filters.DICE, handle_user_dice_throw))

    # هندلرهای دستورات متنی فارسی
    app.add_handler(MessageHandler(filters.Regex(r"^(میو|مع)$"), meow_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^(پروفایل|میوهاش)$"), profile_handler))
    
    # هندلر هوشمند برای صدا زدن گربه (چه با کلمات عمومی چه با اسم اختصاصی)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, cat_trigger_handler), group=1)

    app.add_handler(MessageHandler(filters.Regex(r"^بانک$"), bank_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^واریز"), bank_deposit_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^برداشت"), bank_withdraw_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^انتقال بانکی"), bank_transfer_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^ماهی$"), fish_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^یخچال$"), fridge_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^کارخونه$"), factory_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^کازینو$"), casino_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^انتقال میویی"), direct_transfer_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^(دستورات ربات|راهنما)$"), help_command_handler))
    app.add_handler(CommandHandler(["start", "help"], help_command_handler))

    # هندلر تمام دستورات ادمین
    app.add_handler(CommandHandler(
        ["admin", "give_points", "take_points", "add_cat", "set_cat", "max_cat",
         "add_user_level", "set_user_level", "max_user_level", "reset_user", "stats", "bc"],
        admin_handler
    ))

    # هندلر کلیدهای شیشه‌ای
    app.add_handler(CallbackQueryHandler(callback_router))

    print(f"🟢 ربات میوپوینت روشن شد! (آیدی ادمین: {ADMIN_ID})")
    app.run_polling()

if __name__ == "__main__":
    main()
        
