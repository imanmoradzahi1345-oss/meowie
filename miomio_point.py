import sqlite3
import time
import random
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

logging.basicConfig(level=logging.ERROR)

# ==========================================
# ⚙️ تنظیمات اختصاصی شما (تنظیم شده)
# ==========================================
TOKEN = "8832161480:AAG3LFT5wMDdSFRPzb16gKSW31Ocdh1ao2w"
ADMIN_ID = 8918154552

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"⚠️ خطایی رخ داد اما ربات زنده ماند: {context.error}")

def init_db():
    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                cat_name TEXT DEFAULT 'پیشی',
                cat_level INTEGER DEFAULT 1,
                cat_type INTEGER DEFAULT 1,
                pocket_size REAL DEFAULT 1000,
                production_rate REAL DEFAULT 1,
                points REAL DEFAULT 0,
                last_claim REAL DEFAULT 0,
                meow_count INTEGER DEFAULT 0,
                meow_streak INTEGER DEFAULT 0,
                last_meow REAL DEFAULT 0,
                bank_balance REAL DEFAULT 0,
                last_fish_time REAL DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fridge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                fish_name TEXT,
                fish_val REAL
            )
        """)
        conn.commit()
    finally:
        conn.close()

def get_user(user_id: int):
    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()
    finally:
        conn.close()

def register_user(user_id: int):
    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    now = time.time()
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, last_claim, last_meow, last_fish_time)
            VALUES (?, ?, ?, ?)
        """, (user_id, now, now, 0))
        conn.commit()
    finally:
        conn.close()

def parse_amount(amount_str: str) -> float:
    try:
        amount_str = amount_str.lower().strip()
        persian_digits = '۰۱۲۳۴۵۶۷۸۹'
        english_digits = '0123456789'
        amount_str = amount_str.translate(str.maketrans(persian_digits, english_digits))

        multiplier = 1
        for s in ['کا', 'k', 'هزار']:
            if amount_str.endswith(s):
                multiplier = 1000
                amount_str = amount_str[:-len(s)]
                break
        for s in ['م', 'm', 'میلیون']:
            if amount_str.endswith(s):
                multiplier = 1000000
                amount_str = amount_str[:-len(s)]
                break

        return float(amount_str) * multiplier
    except Exception:
        return 0.0

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🐾 **لیست تمام دستورات ربات میو پوینت:**\n\n"
        "💰 **دستورات مالی:**\n"
        "▫️ `سکه` یا `موجودی` : مشاهده سریع کیف پول و بانک\n"
        "▫️ `میوو` یا `مع` : دریافت میوپوینت‌های جیب گربه\n"
        "▫️ `انتقال [مقدار]` (با ریپلی) : انتقال سکه به دیگران\n"
        "▫️ `بانک` : واریز و برداشت از حساب بانکی\n\n"
        "🐱 **دستورات گربه:**\n"
        "▫️ `پیشی` یا `گربه` : وضعیت گربه و ارتقا\n"
        "▫️ `تغییر اسم [اسم]` : تغییر نام گربه\n"
        "▫️ `پروفایل` (با ریپلی) : مشاهده اطلاعات سایرین\n\n"
        "🎰 **کازینو و بازی‌ها:**\n"
        "▫️ `کازینو [مقدار]` : منوی انتخاب بازی‌ها (تاس، اسلات، بولینگ)\n"
        "▫️ `تاس [مقدار]` : بازی حدس زوج یا فرد تاس\n"
        "▫️ `اسلات [مقدار]` : ماشین اسلات شانس\n"
        "▫️ `بولینگ [مقدار]` : پرتاب بولینگ\n"
        "▫️ `ماهی` : صید ماهی و کسب درآمد\n"
        "▫️ `یخچال` : مدیریت و فروش ماهی‌ها\n\n"
        "👑 **دستورات ادمین:**\n"
        "▫️ `ادمین` : مشاهده پنل مدیریت\n"
        "▫️ `اعطای سکه [مقدار]` (ریپلی) : واریز سکه توسط ادمین\n"
        "▫️ `آمار` : آمار کل اعضا و سکه‌ها\n"
        "▫️ `همگانی [متن]` : ارسال پیام به تمام کاربران"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def show_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        register_user(user_id)
        user = get_user(user_id)

    wallet_bal = user[6]
    bank_bal = user[11]
    total = wallet_bal + bank_bal

    msg = (
        f"💰 **موجودی حساب شما:**\n\n"
        f"💵 کیف پول: **{int(wallet_bal):,}** میو\n"
        f"🏦 بانک: **{int(bank_bal):,}** میو\n"
        f"💎 دارایی کل: **{int(total):,}** میوپوینت"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
async def show_cat_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        register_user(user_id)
        user = get_user(user_id)

    cat_name, level, cat_type, pocket_size, rate, points, last_claim = (
        user[1], user[2], user[3], user[4], user[5], user[6], user[7]
    )

    now = time.time()
    elapsed = now - last_claim
    produced = min(elapsed * rate, pocket_size)

    cat_types = {1: "🐱 گربه معمولی", 2: "😺 گربه خوش‌شانس", 3: "😼 گربه اعیانی", 4: "🦁 گربه لجندری"}
    type_str = cat_types.get(cat_type, "🐱 گربه")
    upgrade_cost = level * 500

    msg = (
        f"🐾 **پروفایل {cat_name}** ({type_str})\n\n"
        f"📊 **سطح:** {level}\n"
        f"⚡️ **نرخ تولید:** {rate:.1f} میو در ثانیه\n"
        f"🎒 **ظرفیت جیب:** {pocket_size:.0f} میو\n"
        f"📦 **تولید شده در جیب:** {int(produced):,} / {int(pocket_size):,}\n"
        f"💰 **موجودی کیف پول:** {int(points):,} میو"
    )

    buttons = [
        [InlineKeyboardButton(f"📥 دریافت میو ({int(produced)})", callback_data="claim_points")],
        [InlineKeyboardButton(f"⬆️ ارتقا به سطح {level + 1} ({upgrade_cost:,} میو)", callback_data="upgrade_cat")]
    ]

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def change_cat_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        register_user(user_id)

    text = update.message.text.strip()
    new_name = text.replace("تغییر اسم", "").replace("تغییر نام", "").strip()

    if not new_name:
        await update.message.reply_text("⚠️ لطفا اسم جدید را وارد کن!\nمثال: `تغییر اسم ململ`", parse_mode="Markdown")
        return

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET cat_name = ? WHERE user_id = ?", (new_name, user_id))
        conn.commit()
    finally:
        conn.close()

    await update.message.reply_text(f"🎉 اسم گربه‌ات با موفقیت به **«{new_name}»** تغییر کرد!", parse_mode="Markdown")

async def inspect_user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ برای مشاهده پروفایل باید روی پیام شخص ریپلی بزنی!")
        return

    target_id = update.message.reply_to_message.from_user.id
    target_user = get_user(target_id)
    if not target_user:
        await update.message.reply_text("❌ این کاربر هنوز در ربات ثبت‌نام نکرده است.")
        return

    name = update.message.reply_to_message.from_user.full_name
    cat_name, level, points, bank = target_user[1], target_user[2], target_user[6], target_user[11]

    msg = (
        f"👤 **پروفایل {name}**\n\n"
        f"🐱 **نام گربه:** {cat_name}\n"
        f"📊 **سطح گربه:** {level}\n"
        f"💵 **کیف پول:** {int(points):,} میو\n"
        f"🏦 **موجودی بانک:** {int(bank):,} میو"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ================= =================
# 🎰 سیستم کامل کازینو (تاس، اسلات، بولینگ)
# ================= =================
async def casino_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        register_user(user_id)
        user = get_user(user_id)

    parts = update.message.text.strip().split()
    if len(parts) < 2:
        await update.message.reply_text(
            "🎰 **کازینو میو پوینت:**\n"
            "برای شروع مبلغ شرط را وارد کنید.\n\n"
            "مثال‌ها:\n"
            "▫️ `کازینو 1000`\n"
            "▫️ `تاس 5کا`\n"
            "▫️ `اسلات 10کا`\n"
            "▫️ `بولینگ 2000`",
            parse_mode="Markdown"
        )
        return

    bet_amount = parse_amount(parts[-1])
    if bet_amount <= 0:
        await update.message.reply_text("⚠️ لطفا یک مبلغ معتبر وارد کنید!")
        return

    wallet = user[6]
    if wallet < bet_amount:
        await update.message.reply_text(f"❌ موجودی کیف پول کافی نیست!\n💵 موجودی شما: **{int(wallet):,}** میو", parse_mode="Markdown")
        return

    context.user_data['casino_bet'] = bet_amount

    buttons = [
        [
            InlineKeyboardButton("🎲 تاس (زوج)", callback_data="casino_dice_even"),
            InlineKeyboardButton("🎲 تاس (فرد)", callback_data="casino_dice_odd")
        ],
        [
            InlineKeyboardButton("🎰 ماشین اسلات", callback_data="casino_slot"),
            InlineKeyboardButton("🎳 بازی بولینگ", callback_data="casino_bowling")
        ]
    ]

    await update.message.reply_text(
        f"🎰 **انتخاب بازی کازینو**\n\n"
        f"💵 مبلغ شرط: **{int(bet_amount):,}** میوپوینت\n\n"
        f"یک بازی یا حالت شرط‌بندی را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )

async def casino_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    bet_amount = context.user_data.get('casino_bet', 0)

    if bet_amount <= 0:
        await query.edit_message_text("❌ مبلغ شرط مشخص نشده یا منقضی شده است. مجدداً دستور کازینو را بزنید.")
        return

    user = get_user(user_id)
    if not user or user[6] < bet_amount:
        await query.edit_message_text("❌ موجودی کیف پول شما کافی نیست!")
        return

    action = query.data
    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()

    try:
        if action in ["casino_dice_even", "casino_dice_odd"]:
            choice = "زوج" if action == "casino_dice_even" else "فرد"
            await query.message.delete()

            dice_msg = await query.message.chat.send_dice(emoji="🎲")
            val = dice_msg.dice.value
            await asyncio.sleep(2.5)

            is_even = (val % 2 == 0)
            won = (is_even and choice == "زوج") or (not is_even and choice == "فرد")

            if won:
                win_amt = bet_amount
                cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (win_amt, user_id))
                conn.commit()
                await query.message.chat.send_message(
                    f"🎉 **تبریک! تاس {val} آمد ({'زوج' if is_even else 'فرد'})**\n"
                    f"حدس شما **{choice}** بود و برنده شدید! 💰\n"
                    f"➕ پاداش: **+{int(win_amt):,}** میوپوینت",
                    parse_mode="Markdown"
                )
            else:
                cursor.execute("UPDATE users SET points = points - ? WHERE user_id = ?", (bet_amount, user_id))
                conn.commit()
                await query.message.chat.send_message(
                    f"💸 **باختید! تاس {val} آمد ({'زوج' if is_even else 'فرد'})**\n"
                    f"حدس شما **{choice}** بود.\n"
                    f"➖ کسر شد: **-{int(bet_amount):,}** میوپوینت",
                    parse_mode="Markdown"
                )

        elif action == "casino_slot":
            await query.message.delete()
            slot_msg = await query.message.chat.send_dice(emoji="🎰")
            val = slot_msg.dice.value
            await asyncio.sleep(2.5)

            # مقادیر استاندارد تلگرام برای اسلات (1 تا 64)
            if val == 64:  # 777 (Jackpot)
                win_amt = bet_amount * 5
                cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (win_amt, user_id))
                conn.commit()
                await query.message.chat.send_message(
                    f"🏆 **جک‌پات فوق‌العاده! (777)** 🎉\n"
                    f"۵ برابر مبلغ شرط برنده شدید!\n"
                    f"➕ پاداش: **+{int(win_amt):,}** میوپوینت",
                    parse_mode="Markdown"
                )
            elif val in [1, 22, 43]:  # 3 شکل یکسان
                win_amt = bet_amount * 3
                cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (win_amt, user_id))
                conn.commit()
                await query.message.chat.send_message(
                    f"🎉 **سه شکل یکسان!**\n"
                    f"۳ برابر مبلغ شرط برنده شدید!\n"
                    f"➕ پاداش: **+{int(win_amt):,}** میوپوینت",
                    parse_mode="Markdown"
                )
            elif val in [16, 32, 48, 2, 3, 4, 5]:  # 2 شکل یکسان
                win_amt = int(bet_amount * 1.5)
                cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (win_amt, user_id))
                conn.commit()
                await query.message.chat.send_message(
                    f"✨ **دو شکل یکسان!**\n"
                    f"۱.۵ برابر برنده شدید!\n"
                    f"➕ پاداش: **+{int(win_amt):,}** میوپوینت",
                    parse_mode="Markdown"
                )
            else:
                cursor.execute("UPDATE users SET points = points - ? WHERE user_id = ?", (bet_amount, user_id))
                conn.commit()
                await query.message.chat.send_message(
                    f"💸 **شانس نداشتید!** ترکیب برنده نیاورد.\n"
                    f"➖ کسر شد: **-{int(bet_amount):,}** میوپوینت",
                    parse_mode="Markdown"
                )

        elif action == "casino_bowling":
            await query.message.delete()
            bowl_msg = await query.message.chat.send_dice(emoji="🎳")
            pins = bowl_msg.dice.value
            await asyncio.sleep(2.5)

            if pins == 6:  # Strike
                win_amt = bet_amount * 3
                cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (win_amt, user_id))
                conn.commit()
                await query.message.chat.send_message(
                    f"💥 **استرااایک عالی! همه ۶ پین افتاد!** 🎳\n"
                    f"۳ برابر برنده شدید!\n"
                    f"➕ پاداش: **+{int(win_amt):,}** میوپوینت",
                    parse_mode="Markdown"
                )
            elif pins in [4, 5]:
                win_amt = int(bet_amount * 1.5)
                cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (win_amt, user_id))
                conn.commit()
                await query.message.chat.send_message(
                    f"👏 **پرتاب خوب! {pins} پین افتاد.**\n"
                    f"۱.۵ برابر برنده شدید!\n"
                    f"➕ پاداش: **+{int(win_amt):,}** میوپوینت",
                    parse_mode="Markdown"
                )
            elif pins in [2, 3]:
                loss = int(bet_amount * 0.5)
                cursor.execute("UPDATE users SET points = points - ? WHERE user_id = ?", (loss, user_id))
                conn.commit()
                await query.message.chat.send_message(
                    f"🤏 **فقط {pins} پین افتاد.**\n"
                    f"نصف مبلغ شرط کسر شد.\n"
                    f"➖ کسر شد: **-{int(loss):,}** میوپوینت",
                    parse_mode="Markdown"
                )
            else:  # 1 pin (Gutter)
                cursor.execute("UPDATE users SET points = points - ? WHERE user_id = ?", (bet_amount, user_id))
                conn.commit()
                await query.message.chat.send_message(
                    f"💥 **خطا! فقط {pins} پین افتاد.** ❌\n"
                    f"کل شرط کسر شد.\n"
                    f"➖ کسر شد: **-{int(bet_amount):,}** میوپوینت",
                    parse_mode="Markdown"
                )
    finally:
        conn.close()
        context.user_data.pop('casino_bet', None)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ شما دسترسی به بخش ادمین ندارید!")
        return

    msg = (
        "👑 **پنل مدیریت ادمین:**\n\n"
        "▫️ `اعطای سکه [مقدار]` (با ریپلی) : واریز سکه به کاربر\n"
        "▫️ `آمار` : مشاهده تعداد کاربران و مجموع سکه‌ها\n"
        "▫️ `همگانی [متن]` : ارسال پیام همگانی به همه اعضا"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def admin_add_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ روی پیام فرد موردنظر ریپلی بزنید!")
        return

    parts = update.message.text.strip().split()
    if len(parts) < 2:
        await update.message.reply_text("⚠️ مقدار سکه را وارد کنید. مثال: `اعطای سکه 50000`", parse_mode="Markdown")
        return

    amount = parse_amount(parts[-1])
    target_id = update.message.reply_to_message.from_user.id

    if not get_user(target_id):
        register_user(target_id)

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, target_id))
        conn.commit()
    finally:
        conn.close()

    target_name = update.message.reply_to_message.from_user.full_name
    await update.message.reply_text(f"✅ مقدار **{int(amount):,}** میوپوینت با موفقیت به **{target_name}** اعطا شد!", parse_mode="Markdown")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*), SUM(points), SUM(bank_balance) FROM users")
        total_users, total_points, total_bank = cursor.fetchone()
    finally:
        conn.close()

    total_points = total_points or 0
    total_bank = total_bank or 0

    msg = (
        f"📊 **آمار کل ربات:**\n\n"
        f"👥 تعداد اعضا: **{total_users:,}** نفر\n"
        f"💵 کل سکه‌های کیف‌پول‌ها: **{int(total_points):,}** میو\n"
        f"🏦 کل سکه‌های بانک‌ها: **{int(total_bank):,}** میو\n"
        f"💎 کل دارایی موجود در سیستم: **{int(total_points + total_bank):,}** میو"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    text = update.message.text.replace("همگانی", "").strip()
    if not text:
        await update.message.reply_text("⚠️ متن پیام را وارد کنید. مثال:\n`همگانی سلام به همه!`", parse_mode="Markdown")
        return

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
    finally:
        conn.close()

    success = 0
    for u in users:
        try:
            await context.bot.send_message(chat_id=u[0], text=f"📢 **پیام همگانی ادمین:**\n\n{text}", parse_mode="Markdown")
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await update.message.reply_text(f"✅ پیام به **{success}** کاربر با موفقیت ارسال شد.")
async def transfer_meow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ برای انتقال باید روی پیام فرد ریپلی بزنی!\nمثال: `انتقال 50` یا `انتقال 10کا`", parse_mode="Markdown")
        return

    parts = update.message.text.strip().split()
    if len(parts) < 2:
        await update.message.reply_text("⚠️ لطفا مقدار انتقال را وارد کن.\nمثال: `انتقال 100` یا `انتقال 10کا`", parse_mode="Markdown")
        return

    amount = parse_amount(parts[-1])
    if amount <= 0:
        await update.message.reply_text("⚠️ لطفا یک مقدار عددی معتبر وارد کن.", parse_mode="Markdown")
        return

    sender_id = update.effective_user.id
    target_id = update.message.reply_to_message.from_user.id

    if sender_id == target_id:
        await update.message.reply_text("❌ نمی‌تونی به خودت میوپوینت منتقل کنی!")
        return

    if not get_user(target_id):
        register_user(target_id)

    sender = get_user(sender_id)
    if not sender or sender[6] < amount:
        await update.message.reply_text("❌ موجودی میوپوینت شما برای این انتقال کافی نیست!")
        return

    context.user_data['transfer'] = {'target': target_id, 'amount': amount}
    buttons = [[
        InlineKeyboardButton("✅ تایید", callback_data="confirm_transfer"),
        InlineKeyboardButton("❌ کنسل", callback_data="cancel_transfer")
    ]]

    target_name = update.message.reply_to_message.from_user.full_name
    await update.message.reply_text(
        f"آیا از انتقال **{int(amount):,}** میوپوینت به **{target_name}** مطمئنی؟",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )

async def confirm_transfer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_transfer":
        transfer_data = context.user_data.get('transfer')
        if not transfer_data:
            await query.edit_message_text("❌ اطلاعات نشست منقضی شده است.")
            return

        sender_id = query.from_user.id
        target_id = transfer_data['target']
        amount = transfer_data['amount']

        sender = get_user(sender_id)
        if not sender or sender[6] < amount:
            await query.edit_message_text("❌ موجودی شما برای این انتقال کافی نیست!")
            return

        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET points = points - ? WHERE user_id = ?", (amount, sender_id))
            cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, target_id))
            conn.commit()
        finally:
            conn.close()

        context.user_data.pop('transfer', None)
        await query.edit_message_text(f"✅ مقدار **{int(amount):,}** میوپوینت با موفقیت منتقل شد!", parse_mode="Markdown")

    elif query.data == "cancel_transfer":
        context.user_data.pop('transfer', None)
        await query.edit_message_text("❌ عملیات انتقال لغو شد.")

async def meow_bank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        register_user(user_id)
        user = get_user(user_id)

    wallet_bal = user[6]
    bank_bal = user[11]

    buttons = [
        [
            InlineKeyboardButton("💵 واریز به بانک", callback_data="bank_dep"),
            InlineKeyboardButton("🏧 برداشت از بانک", callback_data="bank_wd")
        ]
    ]

    msg = (
        f"🏦 **بانک میویی**\n\n"
        f"💵 موجودی کیف پول: **{int(wallet_bal):,}** میوپوینت\n"
        f"🏦 موجودی در بانک: **{int(bank_bal):,}** میوپوینت\n\n"
        f"برای واریز یا برداشت، یکی از دکمه‌های زیر را انتخاب کنید:"
    )
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def bank_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "bank_dep":
        context.user_data['awaiting_bank_action'] = 'deposit'
        await query.message.reply_text("💵 **مبلغ واریزی به بانک را وارد کنید:**\n(مثال: `1000` یا `10کا` یا `100م`)", parse_mode="Markdown")
    elif query.data == "bank_wd":
        context.user_data['awaiting_bank_action'] = 'withdraw'
        await query.message.reply_text("🏧 **مبلغ برداشتی از بانک را وارد کنید:**\n(مثال: `1000` یا `10کا` یا `100م`)", parse_mode="Markdown")

async def fishing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        register_user(user_id)
        user = get_user(user_id)

    now = time.time()
    last_fish = user[12]
    cooldown = 1380  # ۲۳ دقیقه

    if now - last_fish < cooldown:
        rem = int((cooldown - (now - last_fish)) / 60)
        sec = int((cooldown - (now - last_fish)) % 60)
        await update.message.reply_text(f"⏳ قلاب ماهی‌گیری خسته‌ست! {rem} دقیقه و {sec} ثانیه دیگه دوباره تلاش کن.")
        return

    msg = await update.message.reply_text("🎣 لطفاً **۱۳ ثانیه** صبر کنید تا ماهی صید شود...")
    await asyncio.sleep(13)

    fish_types = [
        ("ماهی قرمز کوچولو", 50),
        ("شاه ماهی", 150),
        ("ماهی طلایی کمیاب", 400),
        ("نهنگ افسانه‌ای", 1000)
    ]
    caught = random.choice(fish_types)
    fish_name, fish_val = caught[0], caught[1]

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET last_fish_time = ? WHERE user_id = ?", (now, user_id))
        conn.commit()
    finally:
        conn.close()

    context.user_data['caught_fish'] = {'name': fish_name, 'val': fish_val}

    buttons = [
        [InlineKeyboardButton("🧊 انتقال به یخچال", callback_data="fish_act:fridge")],
        [
            InlineKeyboardButton(f"💰 فروش ({fish_val} میو)", callback_data="fish_act:sell"),
            InlineKeyboardButton("🐱 بده پیشی بخوره", callback_data="fish_act:feed")
        ]
    ]

    await msg.edit_text(
        f"🎉 **ماهی صید شد!**\n\n🐟 نام: **{fish_name}**\n💎 ارزش: **{fish_val}** میوپوینت\n\nحالا چیکار دوست داری بکنی؟",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )

async def fishing_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data
    fish_data = context.user_data.get('caught_fish')

    if not fish_data:
        await query.edit_message_text("❌ زمان استفاده از این گزینه منقضی شده است.")
        return

    fish_name = fish_data['name']
    fish_val = fish_data['val']

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    try:
        if data == "fish_act:fridge":
            cursor.execute("INSERT INTO fridge (user_id, fish_name, fish_val) VALUES (?, ?, ?)", (user_id, fish_name, fish_val))
            conn.commit()
            context.user_data.pop('caught_fish', None)
            await query.edit_message_text(f"🧊 **{fish_name}** با موفقیت به یخچال منتقل شد!")

        elif data == "fish_act:sell":
            cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (fish_val, user_id))
            conn.commit()
            context.user_data.pop('caught_fish', None)
            await query.edit_message_text(f"💰 **{fish_name}** به قیمت **{fish_val}** میوپوینت فروخته شد!")

        elif data == "fish_act:feed":
            bonus_val = int(fish_val * 1.5)
            cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (bonus_val, user_id))
            conn.commit()
            context.user_data.pop('caught_fish', None)
            await query.edit_message_text(f"🐱 **پیشی با خوشحالی {fish_name} رو خورد!**\nبه عنوان پاداش **{bonus_val}** میوپوینت دریافت کردی! 🐾")
    finally:
        conn.close()

async def fridge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, fish_name, fish_val FROM fridge WHERE user_id = ?", (user_id,))
        fishes = cursor.fetchall()
    finally:
        conn.close()

    if not fishes:
        await update.message.reply_text("🧊 **یخچال شما خالی است!**\nبا استفاده از دستور `ماهی` می‌توانی ماهی صید کنی.", parse_mode="Markdown")
        return

    total_val = sum(f[2] for f in fishes)
    text = f"🧊 **محتویات یخچال شما ({len(fishes)} عدد):**\n\n"
    for idx, f in enumerate(fishes, 1):
        text += f"{idx}. 🐟 {f[1]} — 💎 {int(f[2]):,} میو\n"

    text += f"\n💰 **ارزش کل:** {int(total_val):,} میوپوینت"

    buttons = [
        [InlineKeyboardButton("💵 فروش همه ماهی‌ها", callback_data="fridge_sell_all")],
        [InlineKeyboardButton("🐱 غذادادن همه به پیشی", callback_data="fridge_feed_all")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def fridge_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, fish_name, fish_val FROM fridge WHERE user_id = ?", (user_id,))
        fishes = cursor.fetchall()

        if not fishes:
            await query.edit_message_text("🧊 یخچال شما خالی است!")
            return

        if data == "fridge_sell_all":
            total_val = sum(f[2] for f in fishes)
            cursor.execute("DELETE FROM fridge WHERE user_id = ?", (user_id,))
            cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (total_val, user_id))
            conn.commit()
            await query.edit_message_text(f"💰 تمام ماهی‌های یخچال به ارزش **{int(total_val):,}** میوپوینت فروخته شدند!", parse_mode="Markdown")

        elif data == "fridge_feed_all":
            total_val = sum(f[2] * 1.5 for f in fishes)
            cursor.execute("DELETE FROM fridge WHERE user_id = ?", (user_id,))
            cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (total_val, user_id))
            conn.commit()
            await query.edit_message_text(f"🐱 تمام ماهی‌های یخچال به پیشی داده شد و **{int(total_val):,}** میوپوینت پاداش گرفتی!", parse_mode="Markdown")
    finally:
        conn.close()

async def handle_meow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        register_user(user_id)
        user = get_user(user_id)

    pocket_size, rate, points, last_claim = user[4], user[5], user[6], user[7]
    now = time.time()
    elapsed = now - last_claim
    produced = min(elapsed * rate, pocket_size)

    conn = sqlite3.connect("meow_point.db")
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET points = points + ?, last_claim = ? WHERE user_id = ?", (produced, now, user_id))
        conn.commit()
    finally:
        conn.close()

    total_points = points + produced
    await update.message.reply_text(
        f"🐾 **میووو!**\nمقدار **{int(produced):,}** میوپوینت از جیب گربه خالی شد!\n"
        f"💰 موجودی کیف پول: **{int(total_points):,}** میوپوینت",
        parse_mode="Markdown"
    )

async def general_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    action = context.user_data.get('awaiting_bank_action')

    if action:
        user_id = update.effective_user.id
        amount = parse_amount(text)
        if amount <= 0:
            await update.message.reply_text("⚠️ لطفاً یک مقدار عددی معتبر وارد کنید.\nمثال: `1000` یا `10کا` یا `100م`", parse_mode="Markdown")
            return

        user = get_user(user_id)
        if not user:
            context.user_data.pop('awaiting_bank_action', None)
            return

        wallet, bank = user[6], user[11]
        conn = sqlite3.connect("meow_point.db")
        cursor = conn.cursor()

        try:
            if action == "deposit":
                if wallet < amount:
                    await update.message.reply_text(f"❌ موجودی کیف پول کافی نیست!\n💵 کیف پول: **{int(wallet):,}** میو", parse_mode="Markdown")
                    return
                cursor.execute("UPDATE users SET points = points - ?, bank_balance = bank_balance + ? WHERE user_id = ?", (amount, amount, user_id))
                conn.commit()
                context.user_data.pop('awaiting_bank_action', None)
                await update.message.reply_text(f"✅ مقدار **{int(amount):,}** میو به بانک واریز شد! 🏦", parse_mode="Markdown")

            elif action == "withdraw":
                if bank < amount:
                    await update.message.reply_text(f"❌ موجودی بانک کافی نیست!\n🏦 بانک: **{int(bank):,}** میو", parse_mode="Markdown")
                    return
                cursor.execute("UPDATE users SET points = points + ?, bank_balance = bank_balance - ? WHERE user_id = ?", (amount, amount, user_id))
                conn.commit()
                context.user_data.pop('awaiting_bank_action', None)
                await update.message.reply_text(f"✅ مقدار **{int(amount):,}** میو از بانک برداشت شد! 🏧", parse_mode="Markdown")
        finally:
            conn.close()
        return

    if "میو" in text or "مع" in text:
        await handle_meow(update, context)

def main():
    init_db()

    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .build()
    )

    app.add_error_handler(error_handler)

    app.add_handler(CommandHandler(["start", "help"], show_help))
    app.add_handler(MessageHandler(filters.Regex(r"^(راهنما|راهنمایی)$"), show_help))
    app.add_handler(MessageHandler(filters.Regex(r"^(سکه|موجودی)$"), show_coins))
    app.add_handler(MessageHandler(filters.Regex(r"^(پیشی|گربه)"), show_cat_profile))
    app.add_handler(MessageHandler(filters.Regex(r"^(تغییر اسم|تغییر نام)"), change_cat_name))
    app.add_handler(MessageHandler(filters.Regex(r"^(پروفایل)$"), inspect_user_profile))
    app.add_handler(MessageHandler(filters.Regex(r"^(انتقال|انتقال میویی)"), transfer_meow))
    app.add_handler(MessageHandler(filters.Regex(r"^(بانک)$"), meow_bank))
    app.add_handler(MessageHandler(filters.Regex(r"^(کازینو|تاس|اسلات|بولینگ|شرط)"), casino_game))
    app.add_handler(MessageHandler(filters.Regex(r"^(ماهی)$"), fishing))
    app.add_handler(MessageHandler(filters.Regex(r"^(یخچال)$"), fridge))

    app.add_handler(MessageHandler(filters.Regex(r"^(ادمین|پنل ادمین)$"), admin_panel))
    app.add_handler(MessageHandler(filters.Regex(r"^(اعطای سکه)"), admin_add_coins))
    app.add_handler(MessageHandler(filters.Regex(r"^(آمار)$"), admin_stats))
    app.add_handler(MessageHandler(filters.Regex(r"^(همگانی)"), admin_broadcast))

    app.add_handler(CallbackQueryHandler(casino_callback_handler, pattern="^casino_"))
    app.add_handler(CallbackQueryHandler(confirm_transfer_handler, pattern="^(confirm_transfer|cancel_transfer)$"))
    app.add_handler(CallbackQueryHandler(bank_button_handler, pattern="^(bank_dep|bank_wd)$"))
    app.add_handler(CallbackQueryHandler(fishing_action_handler, pattern="^fish_act:"))
    app.add_handler(CallbackQueryHandler(fridge_action_handler, pattern="^fridge_"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, general_text_handler))

    print("🚀 ربات میو پوینت با موفقیت روشن شد!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            print(f"⚠️ ربات قطع شد ({e}). تلاش مجدد در ۵ ثانیه...")
            time.sleep(5)
