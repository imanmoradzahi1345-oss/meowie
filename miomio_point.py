import sqlite3
import random
import time
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, 
    ContextTypes, filters
)

# ==================================================
# 🔑 اطلاعات اصلی ربات و ادمین
# ==================================================
TOKEN = "8832161480:AAG3LFT5wMDdSFRPzb16gKSW31Ocdh1ao2w"
ADMIN_ID = 8918154552

# ==================================================
# 🗄️ راه‌اندازی کامل دیتابیس SQLite
# ==================================================
def init_db():
    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    
    # جدول اصلی کاربران
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            wallet REAL DEFAULT 0,
            bank REAL DEFAULT 0,
            acc_num TEXT UNIQUE,
            meow_count INTEGER DEFAULT 0,
            cat_name TEXT DEFAULT 'پیشی کوچولو',
            cat_level INTEGER DEFAULT 1,
            cat_food INTEGER DEFAULT 100,
            last_meow_time REAL DEFAULT 0,
            cat_last_claim REAL DEFAULT 0,
            factory_level INTEGER DEFAULT 1,
            factory_capacity INTEGER DEFAULT 10000,
            producing_item TEXT DEFAULT NULL,
            produce_amount INTEGER DEFAULT 0,
            produce_start_time REAL DEFAULT 0,
            produce_duration INTEGER DEFAULT 0,
            produce_cost REAL DEFAULT 0,
            last_bank_interest REAL DEFAULT 0
        )
    ''')
    
    # جدول انبار یخچال (ماهی‌ها)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fridge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            fish_type TEXT,
            count INTEGER DEFAULT 1
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ==================================================
# 🛠️ توابع کمکی محاسباتی و اعلانات
# ==================================================
def get_user(user_id):
    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def register_user(user_id, username):
    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    # تولید شماره حساب رندوم ۱۲ رقمی
    acc_num = f"{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"
    now = time.time()
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, acc_num, cat_last_claim, last_bank_interest) VALUES (?, ?, ?, ?, ?)",
        (user_id, username, acc_num, now, now)
    )
    conn.commit()
    conn.close()

def parse_amount(text):
    text = str(text).lower().replace("کا", "000").replace("k", "000").replace(",", "").strip()
    try:
        return float(text)
    except ValueError:
        return 0.0

def get_user_level(meow_count):
    # محاسبات لول کاربر بر اساس تعداد میو
    return (meow_count // 10) + 1

async def send_pv_notify(context: ContextTypes.DEFAULT_TYPE, user_id: int, message: str):
    try:
        await context.bot.send_message(chat_id=user_id, text=f"🔔 **اعلان مالی ربات:**\n\n{message}", parse_mode="Markdown")
    except Exception:
        pass

def get_cat_title(level):
    if level < 10:
        return "گربه کوچولو 🐾"
    elif level < 20:
        return "گربه باهوش 🐱"
    elif level < 30:
        return "گربه زرنگ 😼"
    elif level < 50:
        return "گربه سلطان 🦁"
    else:
        return "گربه اسطوره⚡️"
                  # ==================================================
# 🐱 سیستم میو / مع زدن (با تایمر ۳ دقیقه‌ای دقیق)
# ==================================================
async def meow_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    user = get_user(user_id)
    if not user:
        register_user(user_id, username)
        user = get_user(user_id)

    last_meow = user[9]
    now = time.time()
    cooldown = 180  # 3 دقیقه (180 ثانیه)

    if now - last_meow < cooldown:
        rem = int(cooldown - (now - last_meow))
        mins, secs = divmod(rem, 60)
        await update.message.reply_text(
            f"⏱ هنوز **{mins} دقیقه و {secs} ثانیه** تا میو بعدی مونده!\n"
            f"تو میوت نمیاد 😸 فعلاً صبر کن!",
            parse_mode="Markdown"
        )
        return

    reward = 100
    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET wallet = wallet + ?, meow_count = meow_count + 1, last_meow_time = ? WHERE user_id = ?",
        (reward, now, user_id)
    )
    conn.commit()
    conn.close()

    new_wallet = user[2] + reward
    await update.message.reply_text(
        f"✨ **به شما ۱۰۰ میوپوینت داده شد!** 🎉\n\n"
        f"💵 میوپوینت‌های داخل جیبت: **{int(new_wallet):,}** میوپوینت",
        parse_mode="Markdown"
    )

# ==================================================
# 👤 سیستم پروفایل (خود کاربر یا ریپلی روی بقیه)
# ==================================================
async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_user_id = update.effective_user.id
    target_name = update.effective_user.first_name

    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
        target_name = update.message.reply_to_message.from_user.first_name

    user = get_user(target_user_id)
    if not user:
        await update.message.reply_text("❌ کاربر مورد نظر هنوز در ربات ثبت‌نام نکرده است.")
        return

    level = get_user_level(user[5])
    await update.message.reply_text(
        f"👤 **پروفایل میویی کاربر:** {target_name}\n\n"
        f"👤 **اسم کاربر:** {user[1]}\n"
        f"🐱 **اسم گربه:** {user[6]}\n"
        f"💵 **میوپوینت جیب:** {int(user[2]):,} میو\n"
        f"🐾 **تعداد میوها/مع‌ها:** {user[5]} بار\n"
        f"⭐️ **سطح (لول):** {level}\n"
        f"💳 **شماره حساب بانک:** `{user[4]}`",
        parse_mode="Markdown"
    )

# ==================================================
# 🐾 داشبورد مدیریت گربه (Triggers: پیشی / گربه / اسم گربه)
# ==================================================
async def cat_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        register_user(user_id, update.effective_user.first_name)
        user = get_user(user_id)

    cat_name = user[6]
    cat_level = user[7]
    cat_title = get_cat_title(cat_level)
    mps = cat_level * 2  # میزان تولید میوپوینت در ثانیه
    
    now = time.time()
    last_claim = user[10]
    produced = int((now - last_claim) * mps)
    
    food_level = user[8]
    food_status = "سیره 🟢" if food_level > 50 else ("گشنشه 🟡" if food_level > 20 else "خیلی گشنشه 🔴")

    buttons = [
        [
            InlineKeyboardButton("⭐️ ارتقا گربه", callback_data="cat_upgrade"),
            InlineKeyboardButton("💰 برداشت میوپوینت", callback_data="cat_claim")
        ],
        [
            InlineKeyboardButton("✏️ تغییر اسم گربه", callback_data="cat_rename")
        ]
    ]

    await update.message.reply_text(
        f"🐱 **صفحه اختصاصی پیشی شما**\n\n"
        f"📛 **اسم گربه:** {cat_name} ({cat_title})\n"
        f"⭐️ **لول گربه:** {cat_level}\n"
        f"⚡️ **تولید در ثانیه:** {mps} میوپوینت\n"
        f"📦 **میوپوینت تولید شده:** {produced:,} میوپوینت\n"
        f"🍖 **وضعیت غذا:** {food_status} ({food_level}%)\n",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )
    # ==================================================
# 🏦 سیستم بانک (باز شدن در لول ۲)
# ==================================================
async def bank_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        register_user(user_id, update.effective_user.first_name)
        user = get_user(user_id)

    level = get_user_level(user[5])
    if level < 2:
        await update.message.reply_text("❌ سیستم بانک در **لول ۲** باز می‌شود! (با میو زدن لول خود را افزایش دهید)")
        return

    # محاسبه سود روزانه ۳ درصد
    now = time.time()
    last_interest = user[18]
    bank_balance = user[3]
    
    # اگر ۲۴ ساعت (۸۶۴۰۰ ثانیه) گذشته باشد
    if now - last_interest >= 86400 and bank_balance > 0:
        days = int((now - last_interest) // 86400)
        interest_added = bank_balance * ((1.03 ** days) - 1)
        new_balance = bank_balance + interest_added
        
        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET bank = ?, last_bank_interest = ? WHERE user_id = ?", (new_balance, now, user_id))
        conn.commit()
        conn.close()
        
        bank_balance = new_balance
        await send_pv_notify(context, user_id, f"📈 مبلغ {int(interest_added):,} میوپوینت سود روزانه ۳٪ به حساب بانک شما اضافه شد!")

    buttons = [
        [
            InlineKeyboardButton("📥 واریز به بانک", callback_data="bank_deposit_prompt"),
            InlineKeyboardButton("📤 برداشت از بانک", callback_data="bank_withdraw_prompt")
        ],
        [
            InlineKeyboardButton("💸 انتقال با شماره حساب", callback_data="bank_transfer_prompt")
        ]
    ]

    await update.message.reply_text(
        f"🏦 **پنل مدیریت بانک میو**\n\n"
        f"💳 **شماره حساب اختصاصی شما:**\n`{user[4]}`\n\n"
        f"💰 **موجودی حساب بانک:** **{int(bank_balance):,}** میوپوینت\n"
        f"💵 **موجودی جیب:** **{int(user[2]):,}** میوپوینت\n"
        f"📈 **نرخ سود روزانه:** ۳ درصد",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )

# ==================================================
# 📥 واریز و برداشت بانک
# ==================================================
async def process_bank_action(update: Update, context: ContextTypes.DEFAULT_TYPE, action_type, amount):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if amount <= 0:
        return "⚠️ لطفاً مبلغ معتبری وارد کنید."

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()

    if action_type == "deposit":
        if user[2] < amount:
            conn.close()
            return "❌ موجودی جیب شما کافی نیست!"
        cursor.execute("UPDATE users SET wallet = wallet - ?, bank = bank + ? WHERE user_id = ?", (amount, amount, user_id))
        conn.commit()
        conn.close()
        await send_pv_notify(context, user_id, f"📥 مبلغ {int(amount):,} میوپوینت به بانک واریز شد.")
        return f"✅ مبلغ **{int(amount):,}** میوپوینت با موفقیت به بانک واریز شد."

    elif action_type == "withdraw":
        if user[3] < amount:
            conn.close()
            return "❌ موجودی بانک شما کافی نیست!"
        cursor.execute("UPDATE users SET bank = bank - ?, wallet = wallet + ? WHERE user_id = ?", (amount, amount, user_id))
        conn.commit()
        conn.close()
        await send_pv_notify(context, user_id, f"📤 مبلغ {int(amount):,} میوپوینت از بانک برداشت شد.")
        return f"✅ مبلغ **{int(amount):,}** میوپوینت با موفقیت از بانک برداشت شد."
    # ==================================================
# 🎣 سیستم ماهیگیری و ایموجی‌های ماهی
# ==================================================
FISH_DATA = {
    "🐟": {"name": "ماهی معمولی", "price": 200, "food": 15},
    "🐠": {"name": "ماهی طلایی", "price": 500, "food": 30},
    "🦐": {"name": "میگو کوچک", "price": 300, "food": 20},
    "🦈": {"name": "کوسه کمیاب", "price": 2500, "food": 60},
    "🐡": {"name": "بادکنک ماهی", "price": 800, "food": 35},
    "🦑": {"name": "اختاپوس", "price": 1200, "food": 40},
    "🦦": {"name": "سمور آبی", "price": 1800, "food": 50},
    "🐙": {"name": "هشت‌پا غول‌پیکر", "price": 3000, "food": 70}
}

async def fish_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    fish_emoji = random.choice(list(FISH_DATA.keys()))
    fish_info = FISH_DATA[fish_emoji]

    msg = await update.message.reply_text(f"🎣 در حال انداختن قلاب به آب...\n\n{fish_emoji}")
    await asyncio.sleep(1.5)

    buttons = [
        [
            InlineKeyboardButton("💰 فروش فوری", callback_data=f"fish_sell_{fish_emoji}"),
            InlineKeyboardButton("🍖 بده پیشی بخوره", callback_data=f"fish_feed_{fish_emoji}")
        ],
        [
            InlineKeyboardButton("❄️ ببر تو یخچال", callback_data=f"fish_keep_{fish_emoji}")
        ]
    ]

    await msg.edit_text(
        f"🎉 **شما یک {fish_info['name']} ({fish_emoji}) صید کردید!**\n\n"
        f"💵 ارزش فروش: **{fish_info['price']:,}** میوپوینت\n"
        f"🍖 میزان سیرکنندگی: **{fish_info['food']}%**\n\n"
        f"انتخاب کنید چی کارش کنم؟",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )

# ==================================================
# ❄️ سیستم یخچال (نمایش و انتخاب ماهی‌ها)
# ==================================================
async def fridge_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    cursor.execute("SELECT fish_type, count FROM fridge WHERE user_id = ?", (user_id,))
    items = cursor.fetchall()
    conn.close()

    if not items:
        await update.message.reply_text("❄️ **یخچال شما خالی است!** می‌توانید با دستور `ماهی` صید کنید.")
        return

    text = "❄️ **محتویات یخچال شما:**\n\n"
    buttons = []
    for fish_emoji, count in items:
        if count > 0:
            fish_info = FISH_DATA.get(fish_emoji, {"name": "ماهی"})
            text += f"{fish_emoji} **{fish_info['name']}:** {count} عدد\n"
            buttons.append([
                InlineKeyboardButton(f"🍖 دادن {fish_emoji} به پیشی", callback_data=f"fridge_feed_{fish_emoji}"),
                InlineKeyboardButton(f"💰 فروش {fish_emoji}", callback_data=f"fridge_sell_{fish_emoji}")
            ])

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

# ==================================================
# 💸 انتقال مستقیم در چت (انتقال میویی - حداکثر ۶۰۰کا)
# ==================================================
async def direct_transfer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ لطفاً این دستور را روی پیام فردی که می‌خواهید برایش واریز کنید ریپلی کنید.")
        return

    target_id = update.message.reply_to_message.from_user.id
    target_name = update.message.reply_to_message.from_user.first_name

    if target_id == user_id:
        await update.message.reply_text("❌ نمی‌توانید به خودتان انتقال دهید!")
        return

    parts = update.message.text.split()
    amount = parse_amount(parts[-1])

    if amount <= 0:
        await update.message.reply_text("⚠️ لطفاً یک مبلغ معتبر وارد کنید.")
        return

    if amount > 600000:
        await update.message.reply_text("❌ سقف انتقال مستقیم چت **۶۰۰,۰۰۰ (۶۰۰کا)** است!\nبرای انتقال مبالغ بالاتر از **بانک و شماره حساب** استفاده کنید.")
        return

    if user[2] < amount:
        await update.message.reply_text("❌ موجودی کیف پول (جیب) شما کافی نیست!")
        return

    # ذخیره در context برای تایید
    context.user_data['pending_transfer'] = {
        'target_id': target_id,
        'target_name': target_name,
        'amount': amount
    }

    buttons = [[
        InlineKeyboardButton("✅ تایید", callback_data="confirm_direct_transfer"),
        InlineKeyboardButton("❌ کنسل", callback_data="cancel_direct_transfer")
    ]]

    await update.message.reply_text(
        f"❓ **آیا اطمینان دارید از انتقال؟**\n\n"
        f"👤 به کاربر: **{target_name}**\n"
        f"💵 مبلغ: **{int(amount):,}** میوپوینت",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
        )
    # ==================================================
# 🏭 سیستم کارخانه (باز شدن در لول ۴)
# ==================================================
PRODUCTS = {
    1: {"name": "شکلات 🍫", "cost": 3, "base_sell": 6, "time": 60, "min_fac_level": 1},
    2: {"name": "آبنبات 🍬", "cost": 10, "base_sell": 20, "time": 120, "min_fac_level": 2},
    3: {"name": "پشمک 🍥", "cost": 30, "base_sell": 60, "time": 300, "min_fac_level": 3},
    4: {"name": "کیک 🎂", "cost": 100, "base_sell": 220, "time": 600, "min_fac_level": 4},
    5: {"name": "هواپیمای مسافربری ✈️", "cost": 1000, "base_sell": 2500, "time": 1800, "min_fac_level": 5},
    6: {"name": "جنگنده 🚀", "cost": 5000, "base_sell": 12000, "time": 3600, "min_fac_level": 6},
    7: {"name": "ساختمان 🏢", "cost": 20000, "base_sell": 50000, "time": 7200, "min_fac_level": 7}
}

def calculate_dynamic_sell_price(base_sell):
    # تغییر قیمت بر اساس ساعت واقعی سیستم
    current_hour = datetime.now().hour
    if current_hour == 22:  # ۱۰ شب
        return int(base_sell)
    elif current_hour == 6:  # ۶ صبح
        return int(base_sell * 1.5)
    elif current_hour == 1:  # ۱ بامداد
        return int(base_sell * 1.2)
    else:
        # نوسان رندوم در بقیه ساعات
        factor = random.choice([0.9, 1.1, 1.3, 0.85, 1.15])
        return max(1, int(base_sell * factor))

async def factory_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        register_user(user_id, update.effective_user.first_name)
        user = get_user(user_id)

    level = get_user_level(user[5])
    if level < 4:
        await update.message.reply_text("❌ سیستم کارخانه در **لول ۴** باز می‌شود! (با میو زدن لول بگیرید)")
        return

    fac_level = user[11]
    capacity = user[12]
    producing_item = user[13]

    if producing_item:
        produce_start = user[15]
        duration = user[16]
        elapsed = time.time() - produce_start
        rem = duration - elapsed

        if rem > 0:
            mins, secs = divmod(int(rem), 60)
            buttons = [[InlineKeyboardButton("🛑 اتمام تولید (انصراف و بازگشت پول)", callback_data="factory_cancel")]]
            await update.message.reply_text(
                f"🏭 **کارخانه در حال ساخت محصول:** {producing_item}\n\n"
                f"⏱ زمان باقی‌مانده تا اتمام: **{mins} دقیقه و {secs} ثانیه**\n"
                f"📦 تعداد: {user[14]:,} عدد",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="Markdown"
            )
            return
        else:
            # ساخت تمام شده
            item_info = next((v for k, v in PRODUCTS.items() if v['name'] == producing_item), None)
            current_sell_price = calculate_dynamic_sell_price(item_info['base_sell']) if item_info else 10
            total_sell = current_sell_price * user[14]

            buttons = [[InlineKeyboardButton(f"💰 فروش محصول ({current_sell_price} میو per/item)", callback_data="factory_sell")]]
            await update.message.reply_text(
                f"🎉 **تولید محصول {producing_item} با موفقیت به پایان رسید!**\n\n"
                f"📦 تعداد تولید شده: **{user[14]:,}** عدد\n"
                f"📊 قیمت فعلی بازار (ساعت {datetime.now().hour}): **{current_sell_price}** میوپوینت بر دانه\n"
                f"💵 سود کل پیشنهادی: **{total_sell:,}** میوپوینت",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="Markdown"
            )
            return

    # منوی ساخت محصول
    buttons = [
        [InlineKeyboardButton("⚙️ ارتقا کارخانه (افزایش سرعت و ظرفیت)", callback_data="factory_upgrade")]
    ]

    text = f"🏭 **پنل مدیریت کارخانه**\n\n"
    text += f"⭐️ **سطح کارخانه:** {fac_level}\n"
    text += f"📦 **ظرفیت انبار:** {capacity:,} کالا\n\n"
    text += "🛠 **محصولات قابل ساخت:**\n"

    for pid, pdata in PRODUCTS.items():
        if fac_level >= pdata['min_fac_level']:
            total_cost = pdata['cost'] * capacity
            text += f"🔹 {pdata['name']} | هزینه ساخت: {total_cost:,} میو\n"
            buttons.append([InlineKeyboardButton(f"ساخت {pdata['name']}", callback_data=f"factory_start_{pid}")])
        else:
            text += f"🔒 {pdata['name']} (نیازمند لول {pdata['min_fac_level']} کارخانه)\n"

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
            # ==================================================
# 🟢 بخش ۶ از ۶: سیستم کامل بازی‌های کازینو، پنل ادمین جامع، کلیدهای شیشه‌ای و اجرای Bot
# ==================================================

# ==================================================
# 🎰 سیستم بازی‌های کازینو (۱ تا ۳ نفره)
# ==================================================
CASINO_LOBBIES = {}

async def casino_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("🎰 اسلات", callback_data="casino_select_slot")],
        [InlineKeyboardButton("🎲 تاس", callback_data="casino_select_dice")],
        [InlineKeyboardButton("🎳 بولینگ", callback_data="casino_select_bowling")]
    ]
    await update.message.reply_text("🎰 **یکی از بازی‌های کازینو را انتخاب کنید:**", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

# ==================================================
# 👑 پنل ادمین کامل (شامل همگانی، آمار، شارژ و ارتقا)
# ==================================================
async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # بررسی دسترسی ادمین با آیدی عددی
    if update.effective_user.id != ADMIN_ID:
        return

    text = update.message.text.split(maxsplit=1)
    cmd = text[0]

    # ۱. راهنمای پنل ادمین
    if cmd == "/admin":
        await update.message.reply_text(
            "👑 **پنل مدیریت ادمین ربات**\n\n"
            "▫️ `/give_points [user_id] [مبلغ]` - اهدای میوپوینت به کاربر\n"
            "▫️ `/max_cat [user_id]` - فول ارتقا دادن گربه کاربر (لول ۱۰۰)\n"
            "▫️ `/bc [متن پیام]` - ارسال پیام همگانی به تمام کاربران\n"
            "▫️ `/stats` - مشاهده آمار کامل کاربران و موجودی‌ها",
            parse_mode="Markdown"
        )

    # ۲. مشاهده آمار ربات
    elif cmd == "/stats":
        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), SUM(wallet), SUM(bank) FROM users")
        row = cursor.fetchone()
        total_users = row[0] or 0
        total_wallet = row[1] or 0
        total_bank = row[2] or 0
        conn.close()

        await update.message.reply_text(
            f"📊 **آمار کلی ربات:**\n\n"
            f"👥 تعداد کل کاربران: **{total_users:,}** نفر\n"
            f"💵 کل میوپوینت جیب کاربران: **{int(total_wallet):,}** میو\n"
            f"🏦 کل میوپوینت بانک کاربران: **{int(total_bank):,}** میو",
            parse_mode="Markdown"
        )

    # ۳. دادن میوپوینت به کاربر
    elif cmd == "/give_points":
        sub_parts = update.message.text.split()
        if len(sub_parts) >= 3:
            target = int(sub_parts[1])
            amt = parse_amount(sub_parts[2])
            
            conn = sqlite3.connect("meow_point.db")
            conn.cursor().execute("UPDATE users SET wallet = wallet + ? WHERE user_id = ?", (amt, target))
            conn.commit()
            conn.close()

            await update.message.reply_text(f"✅ مبلغ **{int(amt):,}** میوپوینت با موفقیت به کاربر `{target}` داده شد.", parse_mode="Markdown")
            await send_pv_notify(context, target, f"🎁 مبلغ **{int(amt):,}** میوپوینت توسط ادمین به کیف پول شما اضافه شد!")

    # ۴. فول ارتقا دادن گربه کاربر
    elif cmd == "/max_cat":
        sub_parts = update.message.text.split()
        if len(sub_parts) >= 2:
            target = int(sub_parts[1])
            
            conn = sqlite3.connect("meow_point.db")
            conn.cursor().execute("UPDATE users SET cat_level = 100 WHERE user_id = ?", (target,))
            conn.commit()
            conn.close()

            await update.message.reply_text(f"🚀 لول گربه کاربر `{target}` با موفقیت به **۱۰۰ (حداکثر)** رسید.", parse_mode="Markdown")
            await send_pv_notify(context, target, "🚀 گربه شما توسط ادمین به حداکثر سطح (لول ۱۰۰) ارتقا یافت!")

    # ۵. ارسال پیام همگانی به تمام کاربران
    elif cmd == "/bc":
        if len(text) < 2:
            await update.message.reply_text("⚠️ لطفاً متن پیام همگانی را بعد از دستور وارد کنید.\n\nمثال:\n`/bc سلام به همه کاربران ربات`", parse_mode="Markdown")
            return

        bc_message = text[1]
        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        conn.close()

        success = 0
        failed = 0
        await update.message.reply_text(f"⏳ در حال ارسال پیام همگانی به {len(users)} کاربر...")

        for u in users:
            try:
                await context.bot.send_message(
                    chat_id=u[0], 
                    text=f"📢 **پیام عمومی از طرف مدیریت:**\n\n{bc_message}", 
                    parse_mode="Markdown"
                )
                success += 1
                await asyncio.sleep(0.05)  # رعایت محدودیت ارسال تلگرام
            except Exception:
                failed += 1

        await update.message.reply_text(
            f"✅ **ارسال پیام همگانی به پایان رسید.**\n\n"
            f"🟢 دریافت موفق: {success} نفر\n"
            f"🔴 ناموفق (کاربر بلاک کرده یا غیرفعال است): {failed} نفر"
        )

# ==================================================
# 📜 راهنمای دستورات ربات
# ==================================================
async def help_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **راهنمای جامع دستورات ربات میوپوینت:**\n\n"
        "🐾 `میو` یا `مع` - دریافت ۱۰۰ میوپوینت رایگان (هر ۳ دقیقه)\n"
        "👤 `پروفایل` یا `میوهاش` - مشاهده پروفایل و لول شما یا بقیه (با ریپلی)\n"
        "🐱 `پیشی` یا `گربه` - پنل مدیریت پیشی و ارتقا\n"
        "🏦 `بانک` - پنل بانک، شماره حساب، سود روزانه ۳٪ و انتقال (لول ۲)\n"
        "🎣 `ماهی` - صید ماهی‌های مختلف و کمیاب\n"
        "❄️ `یخچال` - انبار ماهی‌های صید شده\n"
        "🏭 `کارخونه` - ساخت محصولات و فروش با نرخ متغیر ساعت (لول ۴)\n"
        "🎰 `کازینو` - بازی‌های اسلات، تاس و بولینگ ۱ تا ۳ نفره\n"
        "💸 `انتقال میویی [مبلغ]` - انتقال چت مستقیم تا سقف ۶۰۰کا (با ریپلی)\n"
        "📜 `دستورات ربات` - نمایش همین راهنما",
        parse_mode="Markdown"
    )

# ==================================================
# 🎛️ مدیریت کلیک روی تمامی دکمه‌های شیشه‌ای (Callback Router)
# ==================================================
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    await query.answer()

    # --- تایید یا لغو انتقال مستقیم ---
    if data == "confirm_direct_transfer":
        pt = context.user_data.get('pending_transfer')
        if not pt:
            await query.edit_message_text("❌ زمان انجام این تراکنش منقضی شده است.")
            return
        
        user = get_user(user_id)
        if user[2] < pt['amount']:
            await query.edit_message_text("❌ موجودی شما کافی نیست!")
            return

        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET wallet = wallet - ? WHERE user_id = ?", (pt['amount'], user_id))
        cursor.execute("UPDATE users SET wallet = wallet + ? WHERE user_id = ?", (pt['amount'], pt['target_id']))
        conn.commit()
        conn.close()

        await query.edit_message_text(f"✅ **انتقال با موفقیت انجام شد!**\nمبلغ {int(pt['amount']):,} میوپوینت به {pt['target_name']} منتقل شد.")
        await send_pv_notify(context, pt['target_id'], f"💸 مبلغ {int(pt['amount']):,} میوپوینت از طرف {query.from_user.first_name} به کیف پول شما منتقل شد.")
        await send_pv_notify(context, user_id, f"💸 مبلغ {int(pt['amount']):,} میوپوینت از کیف پول شما کسر و به {pt['target_name']} منتقل شد.")
        context.user_data.pop('pending_transfer', None)

    elif data == "cancel_direct_transfer":
        await query.edit_message_text("❌ **انتقال لغو شد.**")

    # --- مدیریت ارتقا و برداشت میوپوینت گربه ---
    elif data == "cat_upgrade":
        user = get_user(user_id)
        cost = user[7] * 500
        if user[2] < cost:
            await query.message.reply_text(f"❌ میوپوینت کافی نیست! هزینه ارتقا: {cost:,} میو")
            return
        conn = sqlite3.connect("meow_point.db")
        conn.cursor().execute("UPDATE users SET wallet = wallet - ?, cat_level = cat_level + 1 WHERE user_id = ?", (cost, user_id))
        conn.commit()
        conn.close()
        await query.message.reply_text(f"🎉 گربه شما به لول {user[7] + 1} ارتقا یافت!")

    elif data == "cat_claim":
        user = get_user(user_id)
        mps = user[7] * 2
        now = time.time()
        produced = int((now - user[10]) * mps)
        if produced <= 0:
            await query.message.reply_text("❌ هنوز میوپوینتی تولید نشده است!")
            return
        conn = sqlite3.connect("meow_point.db")
        conn.cursor().execute("UPDATE users SET wallet = wallet + ?, cat_last_claim = ? WHERE user_id = ?", (produced, now, user_id))
        conn.commit()
        conn.close()
        await query.message.reply_text(f"✅ مبلغ {produced:,} میوپوینت تولید شده به جیب شما منتقل شد.")

    # --- عملیات فروش، تغذیه و ذخیره ماهی ---
    elif data.startswith("fish_sell_"):
        emoji = data.split("_")[2]
        info = FISH_DATA.get(emoji, {"price": 200})
        conn = sqlite3.connect("meow_point.db")
        conn.cursor().execute("UPDATE users SET wallet = wallet + ? WHERE user_id = ?", (info['price'], user_id))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"💰 ماهی {emoji} به مبلغ **{info['price']:,}** میوپوینت فروخته شد.")

    elif data.startswith("fish_feed_"):
        emoji = data.split("_")[2]
        info = FISH_DATA.get(emoji, {"food": 15})
        conn = sqlite3.connect("meow_point.db")
        conn.cursor().execute("UPDATE users SET cat_food = MIN(100, cat_food + ?) WHERE user_id = ?", (info['food'], user_id))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"🍖 ماهی {emoji} به پیشی داده شد! (+{info['food']}% غذای پیشی)")

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
        await query.edit_message_text(f"❄️ ماهی {emoji} با موفقیت در یخچال ذخیره شد.")

    # --- انصراف و فروش محصولات کارخانه ---
    elif data == "factory_cancel":
        user = get_user(user_id)
        refund = user[17]
        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET wallet = wallet + ?, producing_item = NULL, produce_amount = 0, produce_start_time = 0, produce_cost = 0 WHERE user_id = ?",
            (refund, user_id)
        )
        conn.commit()
        conn.close()
        await query.edit_message_text(f"🛑 تولید لغو شد و اصل مبلغ **{int(refund):,}** میوپوینت به شما بازگردانده شد.")

    elif data == "factory_sell":
        user = get_user(user_id)
        item_info = next((v for k, v in PRODUCTS.items() if v['name'] == user[13]), None)
        price_per_item = calculate_dynamic_sell_price(item_info['base_sell']) if item_info else 10
        total = price_per_item * user[14]

        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET wallet = wallet + ?, factory_level = factory_level + 1, producing_item = NULL, produce_amount = 0, produce_start_time = 0 WHERE user_id = ?",
            (total, user_id)
        )
        conn.commit()
        conn.close()
        await query.edit_message_text(f"🎉 کل محصولات به مبلغ **{total:,}** میوپوینت فروخته شد!\n⭐️ سطح کارخانه شما ۱ لول افزایش یافت.")

    # --- انتخاب بازی کازینو ---
    elif data.startswith("casino_select_"):
        game_type = data.split("_")[2]
        buttons = [
            [
                InlineKeyboardButton("👤 ۱ نفره", callback_data=f"casino_start_{game_type}_1"),
                InlineKeyboardButton("👥 ۲ نفره", callback_data=f"casino_start_{game_type}_2"),
                InlineKeyboardButton("👨‍👩‍👦 ۳ نفره", callback_data=f"casino_start_{game_type}_3")
            ]
        ]
        await query.edit_message_text(f"🎮 حالت بازی **{game_type.upper()}** را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(buttons))

# ==================================================
# 🚀 اجرای اصلی ربات (Main Function)
# ==================================================
def main():
    app = Application.builder().token(TOKEN).build()

    # هاندرهای پیام متنی و دستورات فارسی
    app.add_handler(MessageHandler(filters.Regex(r"^(میو|مع)$"), meow_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^(پروفایل|میوهاش)$"), profile_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^(پیشی|گربه)$"), cat_dashboard))
    app.add_handler(MessageHandler(filters.Regex(r"^بانک$"), bank_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^ماهی$"), fish_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^یخچال$"), fridge_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^کارخونه$"), factory_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^کازینو$"), casino_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^انتقال میویی"), direct_transfer_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^دستورات ربات$"), help_command_handler))

    # دستورات کامل پنل ادمین
    app.add_handler(CommandHandler(["admin", "give_points", "max_cat", "stats", "bc"], admin_handler))

    # کلیک روی کلیه دکمه‌های شیشه‌ای
    app.add_handler(CallbackQueryHandler(callback_router))

    print("🟢 Meow Point Bot Online & Ready!")
    app.run_polling()

if __name__ == "__main__":
    main()
        
