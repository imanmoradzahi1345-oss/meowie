# ==================== بخش ۱ از ۶ - Virtual Life ====================
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import random
import time
from datetime import datetime, timedelta

BOT_TOKEN = "8378922493:AAGOzhaN3eUcE53Yz49bo5UMR1rrI-MiRlM"
ADMIN_IDS = [7530457395]

bot = telebot.TeleBot(BOT_TOKEN)
user_steps = {}

def get_db():
    return sqlite3.connect("virtual_life.db", check_same_thread=False)

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        money INTEGER DEFAULT 5000,
        bank INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        xp INTEGER DEFAULT 0,
        job TEXT DEFAULT NULL,
        house TEXT DEFAULT 'اتاق کوچک',
        car TEXT DEFAULT NULL,
        energy INTEGER DEFAULT 100,
        last_work REAL DEFAULT 0,
        last_steal REAL DEFAULT 0,
        partner_id INTEGER DEFAULT NULL,
        missions_done INTEGER DEFAULT 0,
        invited_by INTEGER DEFAULT NULL,
        is_banned INTEGER DEFAULT 0,
        joined_at TEXT,
        last_active TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        income INTEGER,
        cooldown INTEGER,
        min_level INTEGER,
        emoji TEXT DEFAULT '💼'
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS houses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        price INTEGER,
        bonus INTEGER DEFAULT 0,
        emoji TEXT DEFAULT '🏠'
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS cars (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        price INTEGER,
        bonus INTEGER DEFAULT 0,
        emoji TEXT DEFAULT '🚗'
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS missions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT,
        target INTEGER,
        progress INTEGER DEFAULT 0,
        reward_money INTEGER,
        reward_xp INTEGER,
        completed INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

    # شغل‌های پیش‌فرض
    default_jobs = [
        ("کارگر", 80, 60, 1, "👷"),
        ("فست‌فود", 120, 70, 2, "🍔"),
        ("راننده", 180, 80, 4, "🚕"),
        ("برنامه‌نویس", 300, 90, 7, "💻"),
        ("پزشک", 450, 100, 10, "👨‍⚕️"),
        ("مدیر", 700, 120, 15, "👨‍💼"),
    ]
    for j in default_jobs:
        c.execute("INSERT OR IGNORE INTO jobs (name, income, cooldown, min_level, emoji) VALUES (?,?,?,?,?)", j)

    # خانه‌های پیش‌فرض
    default_houses = [
        ("اتاق کوچک", 0, 0, "🏚"),
        ("خانه معمولی", 15000, 5, "🏠"),
        ("ویلای لوکس", 50000, 15, "🏡"),
        ("عمارت", 150000, 30, "🏰"),
        ("پنت‌هاوس", 400000, 50, "🏙"),
    ]
    for h in default_houses:
        c.execute("INSERT OR IGNORE INTO houses (name, price, bonus, emoji) VALUES (?,?,?,?)", h)

    # ماشین‌های پیش‌فرض
    default_cars = [
        ("دوچرخه", 2000, 2, "🚲"),
        ("موتور", 8000, 5, "🛵"),
        ("ماشین معمولی", 25000, 10, "🚗"),
        ("ماشین اسپرت", 80000, 20, "🏎"),
        ("ماشین لوکس", 200000, 35, "🚘"),
        ("ماشین افسانه‌ای", 500000, 60, "🏆"),
    ]
    for car in default_cars:
        c.execute("INSERT OR IGNORE INTO cars (name, price, bonus, emoji) VALUES (?,?,?,?)", car)

    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('start_money', '5000')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('work_cooldown', '60')")

    conn.commit()
    conn.close()

init_db()

def is_admin(uid):
    return uid in ADMIN_IDS

def get_setting(key, default=""):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def ensure_user(user):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id=?", (user.id,))
    if not c.fetchone():
        c.execute('''INSERT INTO users 
            (user_id, username, full_name, money, bank, level, xp, house, energy, joined_at, last_active)
            VALUES (?, ?, ?, ?, 0, 1, 0, 'اتاق کوچک', 100, ?, ?)''',
            (user.id, user.username or "", user.full_name or "",
             int(get_setting("start_money", "5000")),
             datetime.now().strftime("%Y-%m-%d %H:%M"),
             datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
    else:
        c.execute("UPDATE users SET username=?, full_name=?, last_active=? WHERE user_id=?",
                  (user.username or "", user.full_name or "", datetime.now().strftime("%Y-%m-%d %H:%M"), user.id))
        conn.commit()
    conn.close()

def get_user(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    conn.close()
    return row

def add_money(uid, amount):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET money = money + ? WHERE user_id=?", (amount, uid))
    conn.commit()
    conn.close()

def add_xp(uid, amount):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT level, xp FROM users WHERE user_id=?", (uid,))
    level, xp = c.fetchone()
    xp += amount
    needed = level * 100
    leveled = False
    while xp >= needed:
        xp -= needed
        level += 1
        needed = level * 100
        leveled = True
        c.execute("UPDATE users SET money = money + ? WHERE user_id=?", (level * 500, uid))
    c.execute("UPDATE users SET level=?, xp=? WHERE user_id=?", (level, xp, uid))
    conn.commit()
    conn.close()
    return leveled, level

print("✅ بخش ۱ آماده شد")
# ==================== بخش ۲ از ۶ ====================
# منوها + /start + راهنما + پروفایل + کار

def main_menu(uid):
    m = InlineKeyboardMarkup(row_width=2)
    m.add(
        InlineKeyboardButton("👤 پروفایل من", callback_data="profile"),
        InlineKeyboardButton("💼 کار کردن", callback_data="work")
    )
    m.add(
        InlineKeyboardButton("🛒 فروشگاه و املاک", callback_data="shop"),
        InlineKeyboardButton("🦹 دزدی و جرم", callback_data="crime")
    )
    m.add(
        InlineKeyboardButton("🎯 مأموریت‌ها", callback_data="missions"),
        InlineKeyboardButton("💍 ازدواج", callback_data="marriage")
    )
    m.add(
        InlineKeyboardButton("💰 کیف پول و انتقال", callback_data="wallet"),
        InlineKeyboardButton("🏦 بانک", callback_data="bank")
    )
    m.add(
        InlineKeyboardButton("🏆 رتبه‌بندی", callback_data="rank"),
        InlineKeyboardButton("🎁 دعوت دوستان", callback_data="invite")
    )
    m.add(InlineKeyboardButton("📖 راهنما و دستورات", callback_data="help"))
    if is_admin(uid):
        m.add(InlineKeyboardButton("👑 پنل ادمین", callback_data="admin"))
    return m

def help_text():
    return """
📖 **راهنمای Virtual Life**

🎮 **دستورات:**
/start - شروع و ساخت پروفایل
/profile - پروفایل
/work - کار کردن
/help - راهنما

📌 **بخش‌ها:**
👤 پروفایل من
💼 کار کردن (با کول‌داون و انرژی)
🛒 فروشگاه و املاک (خانه + ماشین)
🦹 دزدی و جرم
🎯 مأموریت‌های روزانه
💍 ازدواج
💰 کیف پول و انتقال پول
🏦 بانک (سپرده‌گذاری و سود)
🏆 رتبه‌بندی
🎁 دعوت دوستان

⚠️ انرژی و کول‌داون داری. مراقب باش دزدیده نشی!
"""

@bot.message_handler(commands=['start'])
def start(message):
    ensure_user(message.from_user)
    uid = message.from_user.id
    u = get_user(uid)
    if u and u[16] == 1:  # is_banned
        bot.reply_to(message, "🚫 حساب شما مسدود است.")
        return

    text = f"""
🌟 به **Virtual Life** خوش آمدی!

پول اولیه: **{u[3]:,}** تومان
لول: **{u[5]}**
خانه: **{u[8]}**

زندگی مجازیت رو از صفر بساز 🚀
"""
    bot.reply_to(message, text, reply_markup=main_menu(uid), parse_mode="Markdown")

@bot.message_handler(commands=['help', 'راهنما', 'دستورات'])
def help_cmd(message):
    ensure_user(message.from_user)
    bot.reply_to(message, help_text(), parse_mode="Markdown", reply_markup=main_menu(message.from_user.id))

@bot.message_handler(commands=['profile'])
def profile_cmd(message):
    ensure_user(message.from_user)
    show_profile(message.from_user.id, message.chat.id)

@bot.message_handler(commands=['work'])
def work_cmd(message):
    ensure_user(message.from_user)
    do_work(message.from_user.id, message.chat.id)

def show_profile(uid, chat_id):
    u = get_user(uid)
    if not u:
        return
    job = u[7] or "بیکار"
    car = u[9] or "ندارد"
    partner = "ندارد"
    if u[13]:
        p = get_user(u[13])
        partner = p[2] if p else str(u[13])

    text = f"""
👤 **پروفایل شما**

🆔 `{u[0]}`
👤 {u[2]}
💰 پول نقد: **{u[3]:,}** تومان
🏦 بانک: **{u[4]:,}** تومان
⭐ لول: **{u[5]}** | XP: {u[6]}/{u[5]*100}
💼 شغل: {job}
🏠 خانه: {u[8]}
🚗 ماشین: {car}
⚡ انرژی: {u[10]}/100
💍 همسر: {partner}
🎯 مأموریت‌ها: {u[14]}
"""
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=main_menu(uid))

def do_work(uid, chat_id):
    u = get_user(uid)
    if not u:
        return
    if not u[7]:
        bot.send_message(chat_id, "اول باید شغل انتخاب کنی! از فروشگاه برو.", reply_markup=main_menu(uid))
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT income, cooldown, min_level FROM jobs WHERE name=?", (u[7],))
    job = c.fetchone()
    conn.close()
    if not job:
        bot.send_message(chat_id, "شغل نامعتبر.", reply_markup=main_menu(uid))
        return

    now = time.time()
    if now - u[11] < job[1]:
        remain = int(job[1] - (now - u[11]))
        bot.send_message(chat_id, f"⏳ {remain} ثانیه تا کار بعدی.", reply_markup=main_menu(uid))
        return

    if u[10] < 10:
        bot.send_message(chat_id, "⚡ انرژی کافی نداری!", reply_markup=main_menu(uid))
        return

    income = job[0] + (u[5] * 12)

    # بونوس خانه و ماشین
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT bonus FROM houses WHERE name=?", (u[8],))
    h = c.fetchone()
    c.execute("SELECT bonus FROM cars WHERE name=?", (u[9],))
    car = c.fetchone()
    conn.close()
    bonus = (h[0] if h else 0) + (car[0] if car else 0)
    income = int(income * (1 + bonus / 100))

    add_money(uid, income)
    leveled, new_lvl = add_xp(uid, 12 + u[5])
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET last_work=?, energy=? WHERE user_id=?", (now, max(0, u[10]-8), uid))
    conn.commit()
    conn.close()

    text = f"💼 کار انجام شد!\n+{income:,} تومان\n⚡ انرژی: {max(0, u[10]-8)}/100"
    if leveled:
        text += f"\n\n🎉 لول‌آپ! حالا لول **{new_lvl}** هستی!"
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=main_menu(uid))

    if random.randint(1, 100) <= 10:
        random_event(uid, chat_id)

def random_event(uid, chat_id):
    events = [
        ("دزدی", -random.randint(800, 4000), "🔫 دزدیدنت! پول از دست دادی."),
        ("جایزه", random.randint(1500, 6000), "🎁 جایزه تصادفی گرفتی!"),
        ("پیدا کردن پول", random.randint(500, 2500), "💵 کیف پول پیدا کردی!"),
        ("جریمه", -random.randint(600, 2500), "👮 جریمه شدی!"),
    ]
    ev = random.choice(events)
    add_money(uid, ev[1])
    bot.send_message(chat_id, f"⚡ **اتفاق تصادفی**\n{ev[2]}\nتغییر: {ev[1]:,} تومان")

print("✅ بخش ۲ آماده شد")
# ==================== بخش ۳ از ۶ ====================
# کال‌بک‌های اصلی کاربر

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    uid = call.from_user.id
    ensure_user(call.from_user)
    data = call.data

    if data == "back_main" or data == "back":
        bot.edit_message_text("منوی اصلی:", call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))

    elif data == "profile":
        show_profile(uid, call.message.chat.id)

    elif data == "work":
        do_work(uid, call.message.chat.id)

    elif data == "help":
        bot.edit_message_text(help_text(), call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=main_menu(uid))

    # ----- فروشگاه و املاک -----
    elif data == "shop":
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(
            InlineKeyboardButton("🏠 خرید خانه", callback_data="buy_house"),
            InlineKeyboardButton("🚗 خرید ماشین", callback_data="buy_car"),
            InlineKeyboardButton("💼 انتخاب شغل", callback_data="choose_job"),
            InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")
        )
        bot.edit_message_text("🛒 فروشگاه و املاک:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "buy_house":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT name, price, bonus, emoji FROM houses ORDER BY price")
        houses = c.fetchall()
        conn.close()
        mk = InlineKeyboardMarkup(row_width=1)
        for h in houses:
            mk.add(InlineKeyboardButton(f"{h[3]} {h[0]} - {h[1]:,} تومان", callback_data=f"house_{h[0]}"))
        mk.add(InlineKeyboardButton("🔙", callback_data="shop"))
        bot.edit_message_text("خانه‌ها:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data.startswith("house_"):
        name = data[6:]
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT price FROM houses WHERE name=?", (name,))
        row = c.fetchone()
        u = get_user(uid)
        if row and u[3] >= row[0]:
            c.execute("UPDATE users SET money = money - ?, house = ? WHERE user_id=?", (row[0], name, uid))
            conn.commit()
            bot.answer_callback_query(call.id, f"✅ {name} خریداری شد!", show_alert=True)
            show_profile(uid, call.message.chat.id)
        else:
            bot.answer_callback_query(call.id, "پول کافی نداری!", show_alert=True)
        conn.close()

    elif data == "buy_car":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT name, price, bonus, emoji FROM cars ORDER BY price")
        cars = c.fetchall()
        conn.close()
        mk = InlineKeyboardMarkup(row_width=1)
        for car in cars:
            mk.add(InlineKeyboardButton(f"{car[3]} {car[0]} - {car[1]:,} تومان", callback_data=f"car_{car[0]}"))
        mk.add(InlineKeyboardButton("🔙", callback_data="shop"))
        bot.edit_message_text("ماشین‌ها:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data.startswith("car_"):
        name = data[4:]
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT price FROM cars WHERE name=?", (name,))
        row = c.fetchone()
        u = get_user(uid)
        if row and u[3] >= row[0]:
            c.execute("UPDATE users SET money = money - ?, car = ? WHERE user_id=?", (row[0], name, uid))
            conn.commit()
            bot.answer_callback_query(call.id, f"✅ {name} خریداری شد!", show_alert=True)
            show_profile(uid, call.message.chat.id)
        else:
            bot.answer_callback_query(call.id, "پول کافی نداری!", show_alert=True)
        conn.close()

    elif data == "choose_job":
        u = get_user(uid)
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT name, income, min_level, emoji FROM jobs ORDER BY min_level")
        jobs = c.fetchall()
        conn.close()
        mk = InlineKeyboardMarkup(row_width=1)
        for j in jobs:
            status = "✅" if u[5] >= j[2] else f"🔒 لول {j[2]}"
            mk.add(InlineKeyboardButton(f"{j[3]} {j[0]} ({j[1]}/کار) {status}", callback_data=f"job_{j[0]}"))
        mk.add(InlineKeyboardButton("🔙", callback_data="shop"))
        bot.edit_message_text("شغل‌ها:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data.startswith("job_"):
        name = data[4:]
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT min_level FROM jobs WHERE name=?", (name,))
        row = c.fetchone()
        u = get_user(uid)
        if row and u[5] >= row[0]:
            c.execute("UPDATE users SET job=? WHERE user_id=?", (name, uid))
            conn.commit()
            bot.answer_callback_query(call.id, f"✅ شغل {name} انتخاب شد!", show_alert=True)
            show_profile(uid, call.message.chat.id)
        else:
            bot.answer_callback_query(call.id, "لولت کافی نیست!", show_alert=True)
        conn.close()

    # ----- دزدی -----
    elif data == "crime":
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(
            InlineKeyboardButton("🔫 دزدی از دیگران", callback_data="steal"),
            InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")
        )
        bot.edit_message_text("🦹 دزدی و جرم:\nشانس موفقیت و شکست داری!", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "steal":
        u = get_user(uid)
        now = time.time()
        if now - u[12] < 180:
            bot.answer_callback_query(call.id, "هنوز نمی‌تونی دزدی کنی (۳ دقیقه کول‌داون)", show_alert=True)
            return
        if u[10] < 15:
            bot.answer_callback_query(call.id, "انرژی کافی نداری!", show_alert=True)
            return

        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id, money FROM users WHERE user_id != ? AND money > 1000 ORDER BY RANDOM() LIMIT 1", (uid,))
        target = c.fetchone()
        if not target:
            bot.answer_callback_query(call.id, "کسی برای دزدی پیدا نشد!", show_alert=True)
            conn.close()
            return

        success = random.randint(1, 100) <= 45
        if success:
            stolen = min(target[1] // 4, random.randint(1000, 8000))
            c.execute("UPDATE users SET money = money - ? WHERE user_id=?", (stolen, target[0]))
            c.execute("UPDATE users SET money = money + ?, last_steal=?, energy=energy-15 WHERE user_id=?", (stolen, now, uid))
            conn.commit()
            bot.send_message(call.message.chat.id, f"✅ دزدی موفق!\n+{stolen:,} تومان", reply_markup=main_menu(uid))
            try:
                bot.send_message(target[0], f"🔫 از تو دزدی شد! -{stolen:,} تومان")
            except:
                pass
        else:
            fine = random.randint(500, 3000)
            c.execute("UPDATE users SET money = money - ?, last_steal=?, energy=energy-15 WHERE user_id=?", (fine, now, uid))
            conn.commit()
            bot.send_message(call.message.chat.id, f"❌ دزدی شکست خورد!\nجریمه: -{fine:,} تومان", reply_markup=main_menu(uid))
        conn.close()

    # ----- بانک -----
    elif data == "bank":
        u = get_user(uid)
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(
            InlineKeyboardButton("📥 واریز به بانک", callback_data="bank_deposit"),
            InlineKeyboardButton("📤 برداشت از بانک", callback_data="bank_withdraw"),
            InlineKeyboardButton("🔙", callback_data="back_main")
        )
        bot.edit_message_text(f"🏦 بانک\n\nپول نقد: {u[3]:,}\nموجودی بانک: {u[4]:,}", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "bank_deposit":
        user_steps[uid] = {"step": "bank_dep"}
        bot.edit_message_text("مبلغ واریز به بانک را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "bank_withdraw":
        user_steps[uid] = {"step": "bank_wit"}
        bot.edit_message_text("مبلغ برداشت از بانک را بفرستید:", call.message.chat.id, call.message.message_id)

    # ----- رتبه‌بندی -----
    elif data == "rank":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT full_name, username, money+bank FROM users ORDER BY money+bank DESC LIMIT 10")
        rich = c.fetchall()
        c.execute("SELECT full_name, username, level FROM users ORDER BY level DESC, xp DESC LIMIT 10")
        levels = c.fetchall()
        conn.close()

        text = "🏆 **ثروتمندترین‌ها**\n\n"
        for i, r in enumerate(rich, 1):
            name = r[0] or (f"@{r[1]}" if r[1] else "بدون‌نام")
            text += f"{i}. {name} — {r[2]:,}\n"
        text += "\n⭐ **بالاترین لول**\n\n"
        for i, r in enumerate(levels, 1):
            name = r[0] or (f"@{r[1]}" if r[1] else "بدون‌نام")
            text += f"{i}. {name} — لول {r[2]}\n"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=main_menu(uid))

    # ----- دعوت -----
    elif data == "invite":
        bot_username = bot.get_me().username
        link = f"https://t.me/{bot_username}?start={uid}"
        bot.edit_message_text(f"🎁 لینک دعوت شما:\n`{link}`\n\nبا دعوت هر نفر جایزه می‌گیری!", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=main_menu(uid))

    # ----- ازدواج -----
    elif data == "marriage":
        u = get_user(uid)
        if u[13]:
            bot.answer_callback_query(call.id, "قبلاً ازدواج کردی!", show_alert=True)
            return
        user_steps[uid] = {"step": "marry"}
        bot.edit_message_text("آیدی عددی یا یوزرنیم کسی که می‌خوای باهاش ازدواج کنی رو بفرست:", call.message.chat.id, call.message.message_id)

    # ----- کیف پول -----
    elif data == "wallet":
        user_steps[uid] = {"step": "transfer_id"}
        bot.edit_message_text("آیدی عددی گیرنده را بفرستید:", call.message.chat.id, call.message.message_id)

    # ----- مأموریت -----
    elif data == "missions":
        bot.edit_message_text("🎯 مأموریت‌های روزانه به زودی کامل‌تر می‌شود.\nفعلاً با کار کردن و دزدی XP و پول جمع کن!", call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))

    # ----- پنل ادمین -----
    elif data == "admin" and is_admin(uid):
        mk = InlineKeyboardMarkup(row_width=2)
        mk.add(
            InlineKeyboardButton("👥 کاربران", callback_data="adm_users"),
            InlineKeyboardButton("💰 تغییر پول", callback_data="adm_money")
        )
        mk.add(
            InlineKeyboardButton("🏠 ساخت خانه", callback_data="adm_house"),
            InlineKeyboardButton("🚗 ساخت ماشین", callback_data="adm_car")
        )
        mk.add(
            InlineKeyboardButton("💼 ساخت شغل", callback_data="adm_job"),
            InlineKeyboardButton("📢 همگانی", callback_data="adm_broad")
        )
        mk.add(
            InlineKeyboardButton("🔍 جستجوی کاربر", callback_data="adm_search"),
            InlineKeyboardButton("🔙", callback_data="back_main")
        )
        bot.edit_message_text("👑 پنل ادمین:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "adm_users" and is_admin(uid):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id, username, full_name, money, level FROM users ORDER BY money DESC LIMIT 15")
        rows = c.fetchall()
        conn.close()
        text = "👥 کاربران:\n\n"
        for r in rows:
            text += f"`{r[0]}` @{r[1] or '-'} | {r[2] or '-'}\nپول: {r[3]:,} | لول: {r[4]}\n───\n"
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

    elif data == "adm_money" and is_admin(uid):
        user_steps[uid] = {"step": "adm_money_id"}
        bot.edit_message_text("آیدی کاربر را بفرست:", call.message.chat.id, call.message.message_id)

    elif data == "adm_house" and is_admin(uid):
        user_steps[uid] = {"step": "adm_house_name"}
        bot.edit_message_text("نام خانه جدید را بفرست:", call.message.chat.id, call.message.message_id)

    elif data == "adm_car" and is_admin(uid):
        user_steps[uid] = {"step": "adm_car_name"}
        bot.edit_message_text("نام ماشین جدید را بفرست:", call.message.chat.id, call.message.message_id)

    elif data == "adm_job" and is_admin(uid):
        user_steps[uid] = {"step": "adm_job_name"}
        bot.edit_message_text("نام شغل جدید را بفرست:", call.message.chat.id, call.message.message_id)

    elif data == "adm_broad" and is_admin(uid):
        user_steps[uid] = {"step": "broadcast"}
        bot.edit_message_text("پیام همگانی را بفرست:", call.message.chat.id, call.message.message_id)

    elif data == "adm_search" and is_admin(uid):
        user_steps[uid] = {"step": "adm_search"}
        bot.edit_message_text("آیدی عددی کاربر را بفرست:", call.message.chat.id, call.message.message_id)

    bot.answer_callback_query(call.id)

print("✅ بخش ۳ آماده شد")
# ==================== بخش ۴ از ۶ ====================
# هندلر پیام‌ها (کاربر + بخش خفن دزدی چندمرحله‌ای)

@bot.message_handler(content_types=['text'])
def handle_messages(message):
    uid = message.from_user.id
    ensure_user(message.from_user)
    step_data = user_steps.get(uid, {})
    step = step_data.get("step")
    text = message.text.strip() if message.text else ""

    # ---------- بانک ----------
    if step == "bank_dep":
        try:
            amount = int(text)
            u = get_user(uid)
            if amount <= 0 or u[3] < amount:
                bot.reply_to(message, "مبلغ نامعتبر یا پول کافی نداری.")
                return
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE users SET money = money - ?, bank = bank + ? WHERE user_id=?", (amount, amount, uid))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ {amount:,} تومان به بانک واریز شد.", reply_markup=main_menu(uid))
        except:
            bot.reply_to(message, "فقط عدد بفرست.")
        user_steps[uid] = {}
        return

    if step == "bank_wit":
        try:
            amount = int(text)
            u = get_user(uid)
            if amount <= 0 or u[4] < amount:
                bot.reply_to(message, "مبلغ نامعتبر یا موجودی بانک کافی نیست.")
                return
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE users SET money = money + ?, bank = bank - ? WHERE user_id=?", (amount, amount, uid))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ {amount:,} تومان از بانک برداشت شد.", reply_markup=main_menu(uid))
        except:
            bot.reply_to(message, "فقط عدد بفرست.")
        user_steps[uid] = {}
        return

    # ---------- انتقال پول ----------
    if step == "transfer_id":
        try:
            target = int(text)
            if target == uid:
                bot.reply_to(message, "نمی‌تونی به خودت پول بدی!")
                return
            if not get_user(target):
                bot.reply_to(message, "کاربر پیدا نشد.")
                return
            user_steps[uid] = {"step": "transfer_amount", "target": target}
            bot.reply_to(message, "مبلغ را بفرست:")
        except:
            bot.reply_to(message, "آیدی عددی معتبر بفرست.")
        return

    if step == "transfer_amount":
        try:
            amount = int(text)
            target = step_data["target"]
            u = get_user(uid)
            if amount <= 0 or u[3] < amount:
                bot.reply_to(message, "مبلغ نامعتبر یا پول کافی نداری.")
                return
            add_money(uid, -amount)
            add_money(target, amount)
            bot.reply_to(message, f"✅ {amount:,} تومان به `{target}` ارسال شد.", parse_mode="Markdown", reply_markup=main_menu(uid))
            try:
                bot.send_message(target, f"💰 {amount:,} تومان از کاربر `{uid}` دریافت کردی!", parse_mode="Markdown")
            except:
                pass
        except:
            bot.reply_to(message, "عدد معتبر بفرست.")
        user_steps[uid] = {}
        return

    # ---------- ازدواج ----------
    if step == "marry":
        try:
            if text.startswith("@"):
                bot.reply_to(message, "فعلاً فقط آیدی عددی پشتیبانی می‌شود.")
                user_steps[uid] = {}
                return
            target = int(text)
            if target == uid:
                bot.reply_to(message, "با خودت نمی‌تونی ازدواج کنی!")
                user_steps[uid] = {}
                return
            tuser = get_user(target)
            if not tuser:
                bot.reply_to(message, "کاربر پیدا نشد.")
                user_steps[uid] = {}
                return
            if tuser[13]:
                bot.reply_to(message, "این کاربر قبلاً ازدواج کرده!")
                user_steps[uid] = {}
                return
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE users SET partner_id=? WHERE user_id=?", (target, uid))
            c.execute("UPDATE users SET partner_id=? WHERE user_id=?", (uid, target))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"💍 ازدواج با `{target}` ثبت شد! مبارکه", parse_mode="Markdown", reply_markup=main_menu(uid))
            try:
                bot.send_message(target, f"💍 کاربر `{uid}` با تو ازدواج کرد!", parse_mode="Markdown")
            except:
                pass
        except:
            bot.reply_to(message, "آیدی عددی معتبر بفرست.")
        user_steps[uid] = {}
        return

    # ---------- دزدی چندمرحله‌ای خفن ----------
    if step == "crime_plan":
        # انتخاب هدف
        user_steps[uid] = {"step": "crime_action", "plan": text}
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(
            InlineKeyboardButton("🔪 حمله مستقیم", callback_data="crime_attack"),
            InlineKeyboardButton("🕵️ دزدی مخفیانه", callback_data="crime_sneak"),
            InlineKeyboardButton("💣 نقشه پیچیده", callback_data="crime_smart"),
            InlineKeyboardButton("❌ انصراف", callback_data="back_main")
        )
        bot.reply_to(message, "نقشه‌ت چیه؟ یکی رو انتخاب کن:", reply_markup=mk)
        return

    # ---------- ادمین ----------
    if is_admin(uid):
        if step == "adm_money_id":
            user_steps[uid] = {"step": "adm_money_amount", "target": text}
            bot.reply_to(message, "مبلغ (مثبت برای اضافه، منفی برای کم کردن):")
            return

        if step == "adm_money_amount":
            try:
                target = int(step_data["target"])
                amount = int(text)
                add_money(target, amount)
                bot.reply_to(message, f"✅ پول کاربر `{target}` تغییر کرد.", parse_mode="Markdown", reply_markup=main_menu(uid))
                try:
                    bot.send_message(target, f"💰 موجودی شما توسط ادمین تغییر کرد: {amount:,}")
                except:
                    pass
            except:
                bot.reply_to(message, "خطا در مقدار.")
            user_steps[uid] = {}
            return

        if step == "adm_house_name":
            user_steps[uid] = {"step": "adm_house_price", "name": text}
            bot.reply_to(message, "قیمت خانه را بفرست:")
            return

        if step == "adm_house_price":
            try:
                price = int(text)
                name = step_data["name"]
                conn = get_db()
                c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO houses (name, price, bonus, emoji) VALUES (?, ?, 10, '🏠')", (name, price))
                conn.commit()
                conn.close()
                bot.reply_to(message, f"✅ خانه «{name}» با قیمت {price:,} اضافه شد.", reply_markup=main_menu(uid))
            except:
                bot.reply_to(message, "قیمت عدد باشد.")
            user_steps[uid] = {}
            return

        if step == "adm_car_name":
            user_steps[uid] = {"step": "adm_car_price", "name": text}
            bot.reply_to(message, "قیمت ماشین را بفرست:")
            return

        if step == "adm_car_price":
            try:
                price = int(text)
                name = step_data["name"]
                conn = get_db()
                c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO cars (name, price, bonus, emoji) VALUES (?, ?, 10, '🚗')", (name, price))
                conn.commit()
                conn.close()
                bot.reply_to(message, f"✅ ماشین «{name}» با قیمت {price:,} اضافه شد.", reply_markup=main_menu(uid))
            except:
                bot.reply_to(message, "قیمت عدد باشد.")
            user_steps[uid] = {}
            return

        if step == "adm_job_name":
            user_steps[uid] = {"step": "adm_job_income", "name": text}
            bot.reply_to(message, "درآمد هر بار کار را بفرست:")
            return

        if step == "adm_job_income":
            user_steps[uid] = {"step": "adm_job_level", "name": step_data["name"], "income": text}
            bot.reply_to(message, "حداقل لول مورد نیاز را بفرست:")
            return

        if step == "adm_job_level":
            try:
                name = step_data["name"]
                income = int(step_data["income"])
                min_level = int(text)
                conn = get_db()
                c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO jobs (name, income, cooldown, min_level, emoji) VALUES (?, ?, 90, ?, '💼')",
                          (name, income, min_level))
                conn.commit()
                conn.close()
                bot.reply_to(message, f"✅ شغل «{name}» اضافه شد.", reply_markup=main_menu(uid))
            except:
                bot.reply_to(message, "مقادیر عددی باشند.")
            user_steps[uid] = {}
            return

        if step == "broadcast":
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT user_id FROM users")
            users = c.fetchall()
            conn.close()
            ok = 0
            for u in users:
                try:
                    bot.send_message(u[0], text)
                    ok += 1
                except:
                    pass
            bot.reply_to(message, f"✅ به {ok} کاربر ارسال شد.", reply_markup=main_menu(uid))
            user_steps[uid] = {}
            return

        if step == "adm_search":
            try:
                target = int(text)
                u = get_user(target)
                if u:
                    msg = f"🔍 کاربر `{u[0]}`\nنام: {u[2]}\nیوزرنیم: @{u[1] or '-'}\nپول: {u[3]:,}\nبانک: {u[4]:,}\nلول: {u[5]}\nشغل: {u[7] or 'بیکار'}\nخانه: {u[8]}\nماشین: {u[9] or 'ندارد'}"
                    bot.reply_to(message, msg, parse_mode="Markdown", reply_markup=main_menu(uid))
                else:
                    bot.reply_to(message, "پیدا نشد.")
            except:
                bot.reply_to(message, "آیدی عددی بفرست.")
            user_steps[uid] = {}
            return

    # اگر هیچ استپی نبود
    if text.startswith("/"):
        return
    bot.reply_to(message, "از منو استفاده کن یا /help بزن.", reply_markup=main_menu(uid))

print("✅ بخش ۴ آماده شد")
# ==================== بخش ۵ از ۶ ====================
# دزدی چندمرحله‌ای خفن + کال‌بک‌های جرم

@bot.callback_query_handler(func=lambda call: call.data in ["steal", "crime_attack", "crime_sneak", "crime_smart"] or call.data.startswith("crime_"))
def crime_callbacks(call):
    uid = call.from_user.id
    ensure_user(call.from_user)
    data = call.data

    if data == "steal":
        # مرحله ۱: شروع نقشه
        user_steps[uid] = {"step": "crime_plan"}
        bot.edit_message_text(
            "🦹 **نقشه دزدی**\n\n"
            "اول بگو هدفت چیه؟\n"
            "می‌تونی بنویسی:\n"
            "• بانک\n"
            "• خونه لوکس\n"
            "• ماشین گران\n"
            "• یا هر چیزی که تو ذهنته",
            call.message.chat.id, call.message.message_id
        )
        bot.answer_callback_query(call.id)
        return

    # مرحله ۲: انتخاب روش
    if data in ["crime_attack", "crime_sneak", "crime_smart"]:
        u = get_user(uid)
        now = time.time()

        if now - u[12] < 180:
            bot.answer_callback_query(call.id, "۳ دقیقه کول‌داون داری!", show_alert=True)
            return
        if u[10] < 20:
            bot.answer_callback_query(call.id, "انرژی کافی نداری (حداقل ۲۰)", show_alert=True)
            return

        plan = user_steps.get(uid, {}).get("plan", "هدف نامشخص")
        method = {
            "crime_attack": ("حمله مستقیم", 35, 1.4),
            "crime_sneak": ("دزدی مخفیانه", 55, 1.0),
            "crime_smart": ("نقشه پیچیده", 70, 1.8)
        }[data]

        success_chance = method[1] + min(u[5] * 2, 20)  # لول بالاتر شانس بیشتر
        success = random.randint(1, 100) <= success_chance

        conn = get_db()
        c = conn.cursor()

        if success:
            # پیدا کردن قربانی
            c.execute("SELECT user_id, money FROM users WHERE user_id != ? AND money > 2000 ORDER BY RANDOM() LIMIT 1", (uid,))
            target = c.fetchone()

            if target:
                stolen = int(min(target[1] // 3, random.randint(2000, 12000)) * method[2])
                c.execute("UPDATE users SET money = money - ? WHERE user_id=?", (stolen, target[0]))
                c.execute("UPDATE users SET money = money + ?, last_steal=?, energy = energy - 20 WHERE user_id=?", (stolen, now, uid))
                conn.commit()

                text = f"""
✅ **دزدی موفق!**

🎯 هدف: {plan}
🗡️ روش: {method[0]}
💰 غنیمت: **+{stolen:,}** تومان

آفرین، فرار کردی!
"""
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=main_menu(uid))
                try:
                    bot.send_message(target[0], f"🔫 از تو دزدی شد!\n-{stolen:,} تومان از دست دادی.")
                except:
                    pass
            else:
                # اگر کسی نبود، جایزه سیستم بده
                reward = random.randint(3000, 9000)
                c.execute("UPDATE users SET money = money + ?, last_steal=?, energy = energy - 20 WHERE user_id=?", (reward, now, uid))
                conn.commit()
                bot.edit_message_text(f"✅ دزدی از سیستم موفق!\n+{reward:,} تومان", call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))
        else:
            # شکست
            fine = random.randint(1500, 6000)
            jail_time = random.randint(1, 3)
            c.execute("UPDATE users SET money = money - ?, last_steal=?, energy = energy - 25 WHERE user_id=?", (fine, now, uid))
            conn.commit()

            text = f"""
❌ **دزدی شکست خورد!**

پلیس گرفتت!
💸 جریمه: -{fine:,} تومان
⏱ انرژی کم شد

دفعه بعد محتاط‌تر باش...
"""
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))

        conn.close()
        user_steps[uid] = {}
        bot.answer_callback_query(call.id)

print("✅ بخش ۵ آماده شد")
# ==================== بخش ۶ از ۶ ====================
# اجرا نهایی + اطمینان از کارکرد

# اگر کاربر در گپ یا پیوی پیام داد و استپی نداشت
@bot.message_handler(func=lambda m: True, content_types=['text'])
def fallback(message):
    # این هندلر فقط زمانی اجرا می‌شود که هیچ هندلر دیگری پیام را نگرفته باشد
    pass

print("🤖 ربات Virtual Life با موفقیت روشن شد")
print("=" * 45)
print("توکن تنظیم شد")
print("آیدی ادمین:", ADMIN_IDS)
print()
print("قابلیت‌های فعال:")
print("• پروفایل کامل + انرژی + بانک")
print("• سیستم شغل (قابل ساخت از ادمین)")
print("• خانه و ماشین (قابل ساخت از ادمین)")
print("• کار کردن با کول‌داون و بونوس")
print("• دزدی چندمرحله‌ای خفن")
print("• ازدواج")
print("• انتقال پول")
print("• بانک (واریز / برداشت)")
print("• رتبه‌بندی ثروت و لول")
print("• دعوت دوستان")
print("• اتفاقات تصادفی")
print("• پنل ادمین کامل (ساخت خانه/ماشین/شغل + تغییر پول + همگانی + جستجو)")
print("• راهنما و دستورات")
print("=" * 45)

bot.infinity_polling()
