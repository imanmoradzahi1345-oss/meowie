# ==================== بخش ۱ از ۶ - Virtual Life کامل ====================
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
    return sqlite3.connect("vlife.db", check_same_thread=False)

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
        is_banned INTEGER DEFAULT 0,
        joined_at TEXT,
        last_active TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS jobs (
        name TEXT PRIMARY KEY,
        income INTEGER,
        cooldown INTEGER,
        min_level INTEGER,
        emoji TEXT DEFAULT '💼'
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS houses (
        name TEXT PRIMARY KEY,
        price INTEGER,
        bonus INTEGER DEFAULT 0,
        emoji TEXT DEFAULT '🏠'
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS cars (
        name TEXT PRIMARY KEY,
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
        done INTEGER DEFAULT 0
    )''')

    # شغل‌های پیش‌فرض
    jobs = [
        ("کارگر", 90, 55, 1, "👷"),
        ("فست‌فود", 140, 65, 2, "🍔"),
        ("راننده", 200, 75, 4, "🚕"),
        ("برنامه‌نویس", 320, 85, 7, "💻"),
        ("پزشک", 480, 95, 10, "👨‍⚕️"),
        ("مدیر", 750, 110, 15, "👨‍💼"),
    ]
    for j in jobs:
        c.execute("INSERT OR IGNORE INTO jobs VALUES (?,?,?,?,?)", j)

    # خانه‌ها
    houses = [
        ("اتاق کوچک", 0, 0, "🏚"),
        ("خانه معمولی", 18000, 6, "🏠"),
        ("ویلای لوکس", 55000, 15, "🏡"),
        ("عمارت", 160000, 30, "🏰"),
        ("پنت‌هاوس", 420000, 50, "🏙"),
    ]
    for h in houses:
        c.execute("INSERT OR IGNORE INTO houses VALUES (?,?,?,?)", h)

    # ماشین‌ها
    cars = [
        ("دوچرخه", 2500, 3, "🚲"),
        ("موتور", 9000, 6, "🛵"),
        ("ماشین معمولی", 28000, 12, "🚗"),
        ("ماشین اسپرت", 85000, 22, "🏎"),
        ("ماشین لوکس", 210000, 35, "🚘"),
        ("ماشین افسانه‌ای", 520000, 60, "🏆"),
    ]
    for car in cars:
        c.execute("INSERT OR IGNORE INTO cars VALUES (?,?,?,?)", car)

    conn.commit()
    conn.close()

init_db()

def is_admin(uid):
    return uid in ADMIN_IDS

def ensure_user(user):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id=?", (user.id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, username, full_name, money, bank, level, xp, house, energy, joined_at, last_active) VALUES (?,?,?,5000,0,1,0,'اتاق کوچک',100,?,?)",
                  (user.id, user.username or "", user.full_name or "", datetime.now().strftime("%Y-%m-%d %H:%M"), datetime.now().strftime("%Y-%m-%d %H:%M")))
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

def find_user(text):
    """پیدا کردن کاربر با آیدی یا یوزرنیم"""
    text = text.strip().lstrip("@")
    conn = get_db()
    c = conn.cursor()
    if text.isdigit():
        c.execute("SELECT * FROM users WHERE user_id=?", (int(text),))
    else:
        c.execute("SELECT * FROM users WHERE username=?", (text,))
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
        c.execute("UPDATE users SET money = money + ? WHERE user_id=?", (level * 600, uid))
    c.execute("UPDATE users SET level=?, xp=? WHERE user_id=?", (level, xp, uid))
    conn.commit()
    conn.close()
    return leveled, level

print("✅ بخش ۱ آماده شد")
# ==================== بخش ۲ از ۶ ====================
# منو + /start + پروفایل + کار + راهنما

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
/start - شروع بازی
/profile - پروفایل
/work - کار کردن
/help - راهنما

📌 **بخش‌ها:**
• 👤 پروفایل من
• 💼 کار کردن (پول + XP)
• 🛒 فروشگاه و املاک (خانه، ماشین، شغل)
• 🦹 دزدی و جرم (چندمرحله‌ای)
• 🎯 مأموریت‌های روزانه
• 💍 ازدواج (با درخواست و قبول)
• 💰 انتقال پول (با آیدی / یوزرنیم / ریپلای)
• 🏦 بانک
• 🏆 رتبه‌بندی
• 🎁 دعوت دوستان

⚠️ انرژی و کول‌داون داری. مراقب دزدی باش!
"""

@bot.message_handler(commands=['start'])
def start(message):
    ensure_user(message.from_user)
    uid = message.from_user.id
    u = get_user(uid)
    if u and u[15] == 1:
        bot.reply_to(message, "🚫 حساب شما مسدود است.")
        return

    # اگر با لینک دعوت اومده
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        inviter = int(args[1])
        if inviter != uid and get_user(inviter):
            add_money(inviter, 2000)
            add_money(uid, 1000)
            try:
                bot.send_message(inviter, "🎁 یک نفر با لینک تو وارد شد! +۲۰۰۰ تومان")
            except:
                pass

    text = f"""
🌟 به **Virtual Life** خوش اومدی!

پول اولیه: **{u[3]:,}** تومان
لول: **{u[5]}**
خانه: **{u[8]}**

زندگی مجازیت رو بساز 🚀
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
        partner = (p[2] or p[1] or str(u[13])) if p else str(u[13])

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
🎯 مأموریت‌های انجام‌شده: {u[14]}
"""
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=main_menu(uid))

def do_work(uid, chat_id):
    u = get_user(uid)
    if not u:
        return
    if not u[7]:
        bot.send_message(chat_id, "اول باید شغل انتخاب کنی! برو فروشگاه.", reply_markup=main_menu(uid))
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT income, cooldown, min_level FROM jobs WHERE name=?", (u[7],))
    job = c.fetchone()
    if not job:
        bot.send_message(chat_id, "شغل نامعتبر.", reply_markup=main_menu(uid))
        conn.close()
        return

    now = time.time()
    if now - u[11] < job[1]:
        remain = int(job[1] - (now - u[11]))
        bot.send_message(chat_id, f"⏳ {remain} ثانیه تا کار بعدی باقی مونده.", reply_markup=main_menu(uid))
        conn.close()
        return

    if u[10] < 10:
        bot.send_message(chat_id, "⚡ انرژی کافی نداری!", reply_markup=main_menu(uid))
        conn.close()
        return

    income = job[0] + (u[5] * 15)

    c.execute("SELECT bonus FROM houses WHERE name=?", (u[8],))
    h = c.fetchone()
    c.execute("SELECT bonus FROM cars WHERE name=?", (u[9],))
    car = c.fetchone()
    bonus = (h[0] if h else 0) + (car[0] if car else 0)
    income = int(income * (1 + bonus / 100))

    c.execute("UPDATE users SET money = money + ?, last_work=?, energy=? WHERE user_id=?",
              (income, now, max(0, u[10] - 8), uid))
    conn.commit()
    conn.close()

    leveled, new_lvl = add_xp(uid, 15 + u[5])

    text = f"💼 کار انجام شد!\n+**{income:,}** تومان\n⚡ انرژی: {max(0, u[10]-8)}/100"
    if leveled:
        text += f"\n\n🎉 **لول‌آپ!** حالا لول {new_lvl} هستی!"
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=main_menu(uid))

    if random.randint(1, 100) <= 12:
        random_event(uid, chat_id)

def random_event(uid, chat_id):
    events = [
        (-random.randint(1000, 5000), "🔫 دزدیدنت! پول از دست دادی."),
        (random.randint(2000, 7000), "🎁 جایزه تصادفی گرفتی!"),
        (random.randint(800, 3000), "💵 یه کیف پول پیدا کردی!"),
        (-random.randint(800, 3500), "👮 جریمه شدی!"),
    ]
    change, msg = random.choice(events)
    add_money(uid, change)
    bot.send_message(chat_id, f"⚡ **اتفاق تصادفی**\n{msg}\nتغییر: {change:,} تومان")

print("✅ بخش ۲ آماده شد")
# ==================== بخش ۳ از ۶ ====================
# کال‌بک‌های اصلی

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    uid = call.from_user.id
    ensure_user(call.from_user)
    data = call.data

    if data in ["back_main", "back"]:
        bot.edit_message_text("منوی اصلی:", call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))

    elif data == "profile":
        show_profile(uid, call.message.chat.id)

    elif data == "work":
        do_work(uid, call.message.chat.id)

    elif data == "help":
        bot.edit_message_text(help_text(), call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=main_menu(uid))

    # ---------- فروشگاه ----------
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
        c.execute("SELECT name, price, emoji FROM houses ORDER BY price")
        houses = c.fetchall()
        conn.close()
        mk = InlineKeyboardMarkup(row_width=1)
        for h in houses:
            mk.add(InlineKeyboardButton(f"{h[2]} {h[0]} — {h[1]:,} تومان", callback_data=f"h_{h[0]}"))
        mk.add(InlineKeyboardButton("🔙", callback_data="shop"))
        bot.edit_message_text("خانه‌ها:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data.startswith("h_"):
        name = data[2:]
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT price FROM houses WHERE name=?", (name,))
        row = c.fetchone()
        u = get_user(uid)
        if row and u[3] >= row[0]:
            c.execute("UPDATE users SET money = money - ?, house = ? WHERE user_id=?", (row[0], name, uid))
            conn.commit()
            bot.answer_callback_query(call.id, f"✅ {name} خریده شد!", show_alert=True)
            show_profile(uid, call.message.chat.id)
        else:
            bot.answer_callback_query(call.id, "پول کافی نداری!", show_alert=True)
        conn.close()

    elif data == "buy_car":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT name, price, emoji FROM cars ORDER BY price")
        cars = c.fetchall()
        conn.close()
        mk = InlineKeyboardMarkup(row_width=1)
        for car in cars:
            mk.add(InlineKeyboardButton(f"{car[2]} {car[0]} — {car[1]:,} تومان", callback_data=f"c_{car[0]}"))
        mk.add(InlineKeyboardButton("🔙", callback_data="shop"))
        bot.edit_message_text("ماشین‌ها:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data.startswith("c_"):
        name = data[2:]
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT price FROM cars WHERE name=?", (name,))
        row = c.fetchone()
        u = get_user(uid)
        if row and u[3] >= row[0]:
            c.execute("UPDATE users SET money = money - ?, car = ? WHERE user_id=?", (row[0], name, uid))
            conn.commit()
            bot.answer_callback_query(call.id, f"✅ {name} خریده شد!", show_alert=True)
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
            lock = "" if u[5] >= j[2] else f" 🔒 لول {j[2]}"
            mk.add(InlineKeyboardButton(f"{j[3]} {j[0]} ({j[1]}){lock}", callback_data=f"j_{j[0]}"))
        mk.add(InlineKeyboardButton("🔙", callback_data="shop"))
        bot.edit_message_text("شغل‌ها:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data.startswith("j_"):
        name = data[2:]
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT min_level FROM jobs WHERE name=?", (name,))
        row = c.fetchone()
        u = get_user(uid)
        if row and u[5] >= row[0]:
            c.execute("UPDATE users SET job=? WHERE user_id=?", (name, uid))
            conn.commit()
            bot.answer_callback_query(call.id, f"✅ شغل {name} انتخاب شد", show_alert=True)
            show_profile(uid, call.message.chat.id)
        else:
            bot.answer_callback_query(call.id, "لولت کافی نیست!", show_alert=True)
        conn.close()

    # ---------- دزدی ----------
    elif data == "crime":
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(
            InlineKeyboardButton("🔫 شروع دزدی", callback_data="start_crime"),
            InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")
        )
        bot.edit_message_text("🦹 دزدی و جرم\nشانس و ریسک داره!", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "start_crime":
        user_steps[uid] = {"step": "crime_plan"}
        bot.edit_message_text("نقشه‌ت رو بنویس (مثلاً: بانک، خونه لوکس، ماشین گران...):", call.message.chat.id, call.message.message_id)

    # ---------- بانک ----------
    elif data == "bank":
        u = get_user(uid)
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(
            InlineKeyboardButton("📥 واریز به بانک", callback_data="bank_in"),
            InlineKeyboardButton("📤 برداشت از بانک", callback_data="bank_out"),
            InlineKeyboardButton("🔙", callback_data="back_main")
        )
        bot.edit_message_text(f"🏦 بانک\n\nپول نقد: {u[3]:,}\nموجودی بانک: {u[4]:,}", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "bank_in":
        user_steps[uid] = {"step": "bank_in"}
        bot.edit_message_text("مبلغ واریز را بفرست:", call.message.chat.id, call.message.message_id)

    elif data == "bank_out":
        user_steps[uid] = {"step": "bank_out"}
        bot.edit_message_text("مبلغ برداشت را بفرست:", call.message.chat.id, call.message.message_id)

    # ---------- رتبه‌بندی ----------
    elif data == "rank":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT full_name, username, money+bank FROM users ORDER BY money+bank DESC LIMIT 10")
        rich = c.fetchall()
        c.execute("SELECT full_name, username, level FROM users ORDER BY level DESC, xp DESC LIMIT 10")
        top = c.fetchall()
        conn.close()

        text = "🏆 **ثروتمندترین‌ها**\n\n"
        for i, r in enumerate(rich, 1):
            name = r[0] or (f"@{r[1]}" if r[1] else "ناشناس")
            text += f"{i}. {name} — {r[2]:,}\n"
        text += "\n⭐ **بالاترین لول**\n\n"
        for i, r in enumerate(top, 1):
            name = r[0] or (f"@{r[1]}" if r[1] else "ناشناس")
            text += f"{i}. {name} — لول {r[2]}\n"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=main_menu(uid))

    # ---------- دعوت ----------
    elif data == "invite":
        bot_username = bot.get_me().username
        link = f"https://t.me/{bot_username}?start={uid}"
        bot.edit_message_text(f"🎁 لینک دعوت شما:\n`{link}`\n\nبا دعوت هر نفر جایزه می‌گیری!", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=main_menu(uid))

    # ---------- ازدواج ----------
    elif data == "marriage":
        u = get_user(uid)
        if u[13]:
            bot.answer_callback_query(call.id, "قبلاً ازدواج کردی!", show_alert=True)
            return
        user_steps[uid] = {"step": "marry"}
        bot.edit_message_text("آیدی عددی یا یوزرنیم طرف مقابل را بفرست\n(یا روی پیامش ریپلای کن و بنویس: ازدواج)", call.message.chat.id, call.message.message_id)

    # ---------- کیف پول ----------
    elif data == "wallet":
        user_steps[uid] = {"step": "transfer"}
        bot.edit_message_text("آیدی / یوزرنیم گیرنده را بفرست\n(یا روی پیامش ریپلای کن و بنویس: انتقال 5000)", call.message.chat.id, call.message.message_id)

    # ---------- مأموریت ----------
    elif data == "missions":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, title, target, progress, reward_money, reward_xp, done FROM missions WHERE user_id=? AND done=0", (uid,))
        missions = c.fetchall()
        if not missions:
            # ساخت مأموریت جدید
            titles = [
                ("۵ بار کار کن", 5, 3000, 40),
                ("۲ بار دزدی موفق", 2, 5000, 60),
                ("۱۰ بار کار کن", 10, 8000, 100),
            ]
            t = random.choice(titles)
            c.execute("INSERT INTO missions (user_id, title, target, progress, reward_money, reward_xp) VALUES (?,?,?,0,?,?)",
                      (uid, t[0], t[1], t[2], t[3]))
            conn.commit()
            missions = c.execute("SELECT id, title, target, progress, reward_money, reward_xp, done FROM missions WHERE user_id=? AND done=0", (uid,)).fetchall()
        conn.close()

        text = "🎯 **مأموریت‌های فعال:**\n\n"
        for m in missions:
            text += f"• {m[1]}\nپیشرفت: {m[3]}/{m[2]}\nجایزه: {m[4]:,} تومان + {m[5]} XP\n\n"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=main_menu(uid))

    # ---------- پنل ادمین ----------
    elif data == "admin" and is_admin(uid):
        mk = InlineKeyboardMarkup(row_width=2)
        mk.add(
            InlineKeyboardButton("👥 لیست کاربران", callback_data="adm_users"),
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
        c.execute("SELECT user_id, username, full_name, money, bank, level FROM users ORDER BY money+bank DESC LIMIT 15")
        rows = c.fetchall()
        conn.close()
        text = "👥 کاربران (یوزرنیم + پول + بانک):\n\n"
        for r in rows:
            text += f"`{r[0]}` @{r[1] or '-'}\n{r[2] or '-'}\nپول: {r[3]:,} | بانک: {r[4]:,} | لول: {r[5]}\n──────\n"
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

    elif data == "adm_money" and is_admin(uid):
        user_steps[uid] = {"step": "adm_money"}
        bot.edit_message_text("آیدی یا یوزرنیم کاربر را بفرست:", call.message.chat.id, call.message.message_id)

    elif data == "adm_house" and is_admin(uid):
        user_steps[uid] = {"step": "adm_house_name"}
        bot.edit_message_text("نام خانه جدید:", call.message.chat.id, call.message.message_id)

    elif data == "adm_car" and is_admin(uid):
        user_steps[uid] = {"step": "adm_car_name"}
        bot.edit_message_text("نام ماشین جدید:", call.message.chat.id, call.message.message_id)

    elif data == "adm_job" and is_admin(uid):
        user_steps[uid] = {"step": "adm_job_name"}
        bot.edit_message_text("نام شغل جدید:", call.message.chat.id, call.message.message_id)

    elif data == "adm_broad" and is_admin(uid):
        user_steps[uid] = {"step": "broadcast"}
        bot.edit_message_text("پیام همگانی را بفرست:", call.message.chat.id, call.message.message_id)

    elif data == "adm_search" and is_admin(uid):
        user_steps[uid] = {"step": "adm_search"}
        bot.edit_message_text("آیدی یا یوزرنیم کاربر را بفرست:", call.message.chat.id, call.message.message_id)

    # قبول / رد ازدواج
    elif data.startswith("accept_marry_"):
        from_id = int(data.split("_")[2])
        to_id = uid
        u1 = get_user(from_id)
        u2 = get_user(to_id)
        if not u1 or not u2 or u1[13] or u2[13]:
            bot.answer_callback_query(call.id, "دیگه امکان نداره", show_alert=True)
            return
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET partner_id=? WHERE user_id=?", (to_id, from_id))
        c.execute("UPDATE users SET partner_id=? WHERE user_id=?", (from_id, to_id))
        conn.commit()
        conn.close()
        bot.edit_message_text("💍 ازدواج انجام شد! مبارکه 🎉", call.message.chat.id, call.message.message_id)
        try:
            bot.send_message(from_id, f"💍 {call.from_user.first_name} پیشنهادت رو قبول کرد!")
        except:
            pass
        bot.answer_callback_query(call.id)

    elif data.startswith("reject_marry_"):
        from_id = int(data.split("_")[2])
        bot.edit_message_text("درخواست رد شد.", call.message.chat.id, call.message.message_id)
        try:
            bot.send_message(from_id, "پیشنهاد ازدواجت رد شد.")
        except:
            pass
        bot.answer_callback_query(call.id)

    bot.answer_callback_query(call.id)

print("✅ بخش ۳ آماده شد")
# ==================== بخش ۴ از ۶ ====================
# هندلر پیام‌ها (بانک، انتقال، ازدواج، دزدی، ادمین)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    uid = message.from_user.id
    ensure_user(message.from_user)
    step_data = user_steps.get(uid, {})
    step = step_data.get("step")
    text = message.text.strip() if message.text else ""

    # ----- بانک -----
    if step == "bank_in":
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

    if step == "bank_out":
        try:
            amount = int(text)
            u = get_user(uid)
            if amount <= 0 or u[4] < amount:
                bot.reply_to(message, "مبلغ نامعتبر یا موجودی بانک کم است.")
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

    # ----- انتقال پول (آیدی / یوزرنیم / ریپلای) -----
    if step == "transfer" or (message.reply_to_message and text.lower().startswith(("انتقال", "پرداخت", "transfer"))):
        target_user = None
        amount = None

        if message.reply_to_message:
            target_user = get_user(message.reply_to_message.from_user.id)
            parts = text.split()
            if len(parts) >= 2 and parts[-1].isdigit():
                amount = int(parts[-1])
        else:
            # اول سعی می‌کنیم یوزرنیم یا آیدی پیدا کنیم
            parts = text.split()
            if len(parts) >= 1:
                target_user = find_user(parts[0])
            if len(parts) >= 2 and parts[1].isdigit():
                amount = int(parts[1])

        if not target_user:
            bot.reply_to(message, "کاربر پیدا نشد. آیدی عددی یا یوزرنیم درست بفرست.")
            user_steps[uid] = {}
            return

        if target_user[0] == uid:
            bot.reply_to(message, "نمی‌تونی به خودت پول بدی!")
            user_steps[uid] = {}
            return

        if amount is None:
            user_steps[uid] = {"step": "transfer_amount", "target": target_user[0]}
            bot.reply_to(message, "مبلغ را بفرست:")
            return

        u = get_user(uid)
        if amount <= 0 or u[3] < amount:
            bot.reply_to(message, "پول کافی نداری.")
            user_steps[uid] = {}
            return

        add_money(uid, -amount)
        add_money(target_user[0], amount)
        bot.reply_to(message, f"✅ {amount:,} تومان به {target_user[2] or target_user[1] or target_user[0]} ارسال شد.", reply_markup=main_menu(uid))
        try:
            bot.send_message(target_user[0], f"💰 {amount:,} تومان از طرف {message.from_user.first_name} دریافت کردی!")
        except:
            pass
        user_steps[uid] = {}
        return

    if step == "transfer_amount":
        try:
            amount = int(text)
            target = step_data["target"]
            u = get_user(uid)
            if amount <= 0 or u[3] < amount:
                bot.reply_to(message, "پول کافی نداری.")
                return
            add_money(uid, -amount)
            add_money(target, amount)
            bot.reply_to(message, f"✅ {amount:,} تومان ارسال شد.", reply_markup=main_menu(uid))
            try:
                bot.send_message(target, f"💰 {amount:,} تومان دریافت کردی!")
            except:
                pass
        except:
            bot.reply_to(message, "عدد معتبر بفرست.")
        user_steps[uid] = {}
        return

    # ----- ازدواج (با درخواست) -----
    if step == "marry" or (message.reply_to_message and text in ["ازدواج", "ازدواج کن", "marriage"]):
        target_user = None
        if message.reply_to_message:
            target_user = get_user(message.reply_to_message.from_user.id)
        else:
            target_user = find_user(text)

        if not target_user:
            bot.reply_to(message, "کاربر پیدا نشد.")
            user_steps[uid] = {}
            return
        if target_user[0] == uid:
            bot.reply_to(message, "با خودت نمی‌تونی ازدواج کنی!")
            user_steps[uid] = {}
            return
        if target_user[13]:
            bot.reply_to(message, "این کاربر قبلاً ازدواج کرده!")
            user_steps[uid] = {}
            return

        mk = InlineKeyboardMarkup()
        mk.add(
            InlineKeyboardButton("✅ قبول می‌کنم", callback_data=f"accept_marry_{uid}"),
            InlineKeyboardButton("❌ رد می‌کنم", callback_data=f"reject_marry_{uid}")
        )
        try:
            bot.send_message(target_user[0],
                f"💍 **درخواست ازدواج**\n\n{message.from_user.first_name} (`{uid}`) به تو پیشنهاد ازدواج داده!",
                parse_mode="Markdown", reply_markup=mk)
            bot.reply_to(message, "✅ درخواست ازدواج ارسال شد. منتظر جواب باش.")
        except:
            bot.reply_to(message, "نتونستم پیام بدم. طرف باید ربات رو استارت کرده باشه.")
        user_steps[uid] = {}
        return

    # ----- دزدی (مرحله نقشه) -----
    if step == "crime_plan":
        user_steps[uid] = {"step": "crime_method", "plan": text}
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(
            InlineKeyboardButton("🔪 حمله مستقیم (شانس کمتر - غنیمت بیشتر)", callback_data="crime_attack"),
            InlineKeyboardButton("🕵️ دزدی مخفیانه (شانس متوسط)", callback_data="crime_sneak"),
            InlineKeyboardButton("🧠 نقشه پیچیده (شانس بالاتر)", callback_data="crime_smart"),
            InlineKeyboardButton("❌ انصراف", callback_data="back_main")
        )
        bot.reply_to(message, f"نقشه: {text}\n\nروش دزدی رو انتخاب کن:", reply_markup=mk)
        return

    # ----- ادمین -----
    if is_admin(uid):
        if step == "adm_money":
            target = find_user(text)
            if not target:
                bot.reply_to(message, "کاربر پیدا نشد.")
                user_steps[uid] = {}
                return
            user_steps[uid] = {"step": "adm_money_amount", "target": target[0]}
            bot.reply_to(message, "مبلغ را بفرست (مثبت = اضافه، منفی = کم کردن):")
            return

        if step == "adm_money_amount":
            try:
                amount = int(text)
                target = step_data["target"]
                add_money(target, amount)
                bot.reply_to(message, f"✅ پول کاربر تغییر کرد.", reply_markup=main_menu(uid))
                try:
                    bot.send_message(target, f"💰 موجودی شما توسط ادمین تغییر کرد: {amount:,}")
                except:
                    pass
            except:
                bot.reply_to(message, "عدد معتبر بفرست.")
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
                bot.reply_to(message, f"✅ خانه «{name}» اضافه شد.", reply_markup=main_menu(uid))
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
                bot.reply_to(message, f"✅ ماشین «{name}» اضافه شد.", reply_markup=main_menu(uid))
            except:
                bot.reply_to(message, "قیمت عدد باشد.")
            user_steps[uid] = {}
            return

        if step == "adm_job_name":
            user_steps[uid] = {"step": "adm_job_income", "name": text}
            bot.reply_to(message, "درآمد هر بار کار:")
            return

        if step == "adm_job_income":
            user_steps[uid] = {"step": "adm_job_level", "name": step_data["name"], "income": text}
            bot.reply_to(message, "حداقل لول:")
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
            bot.reply_to(message, f"✅ به {ok} نفر ارسال شد.", reply_markup=main_menu(uid))
            user_steps[uid] = {}
            return

        if step == "adm_search":
            u = find_user(text)
            if u:
                msg = f"""🔍 کاربر پیدا شد:
آیدی: `{u[0]}`
یوزرنیم: @{u[1] or '-'}
نام: {u[2]}
پول: {u[3]:,}
بانک: {u[4]:,}
لول: {u[5]}
شغل: {u[7] or 'بیکار'}
خانه: {u[8]}
ماشین: {u[9] or 'ندارد'}"""
                bot.reply_to(message, msg, parse_mode="Markdown", reply_markup=main_menu(uid))
            else:
                bot.reply_to(message, "پیدا نشد.")
            user_steps[uid] = {}
            return

    # پیش‌فرض
    if not text.startswith("/"):
        bot.reply_to(message, "از منو استفاده کن یا /help بزن.", reply_markup=main_menu(uid))

print("✅ بخش ۴ آماده شد")
# ==================== بخش ۵ از ۶ ====================
# دزدی چندمرحله‌ای (انتخاب روش)

@bot.callback_query_handler(func=lambda call: call.data in ["crime_attack", "crime_sneak", "crime_smart"])
def crime_method(call):
    uid = call.from_user.id
    ensure_user(call.from_user)
    data = call.data

    u = get_user(uid)
    now = time.time()

    if now - u[12] < 180:
        bot.answer_callback_query(call.id, "۳ دقیقه کول‌داون داری!", show_alert=True)
        return
    if u[10] < 20:
        bot.answer_callback_query(call.id, "انرژی کافی نداری (حداقل ۲۰)", show_alert=True)
        return

    plan = user_steps.get(uid, {}).get("plan", "هدف ناشناس")

    methods = {
        "crime_attack": ("حمله مستقیم", 38, 1.5),
        "crime_sneak": ("دزدی مخفیانه", 55, 1.1),
        "crime_smart": ("نقشه پیچیده", 72, 1.7)
    }
    method_name, base_chance, multiplier = methods[data]
    chance = min(base_chance + (u[5] * 2), 90)
    success = random.randint(1, 100) <= chance

    conn = get_db()
    c = conn.cursor()

    if success:
        c.execute("SELECT user_id, money FROM users WHERE user_id != ? AND money > 3000 ORDER BY RANDOM() LIMIT 1", (uid,))
        target = c.fetchone()

        if target:
            stolen = int(min(target[1] // 3, random.randint(2500, 15000)) * multiplier)
            c.execute("UPDATE users SET money = money - ? WHERE user_id=?", (stolen, target[0]))
            c.execute("UPDATE users SET money = money + ?, last_steal=?, energy = energy - 20 WHERE user_id=?",
                      (stolen, now, uid))
            conn.commit()

            text = f"""
✅ **دزدی موفق!**

🎯 هدف: {plan}
🗡️ روش: {method_name}
💰 غنیمت: **+{stolen:,}** تومان

فرار کردی!
"""
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=main_menu(uid))
            try:
                bot.send_message(target[0], f"🔫 از تو دزدی شد!\n-{stolen:,} تومان از دست دادی.")
            except:
                pass
        else:
            reward = int(random.randint(4000, 11000) * multiplier)
            c.execute("UPDATE users SET money = money + ?, last_steal=?, energy = energy - 20 WHERE user_id=?",
                      (reward, now, uid))
            conn.commit()
            bot.edit_message_text(f"✅ دزدی از سیستم موفق!\n+{reward:,} تومان", call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))
    else:
        fine = random.randint(2000, 7000)
        c.execute("UPDATE users SET money = money - ?, last_steal=?, energy = energy - 25 WHERE user_id=?",
                  (fine, now, uid))
        conn.commit()

        text = f"""
❌ **دزدی شکست خورد!**

پلیس گرفتت!
💸 جریمه: -{fine:,} تومان
⚡ انرژی کم شد

دفعه بعد محتاط‌تر باش...
"""
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))

    conn.close()
    user_steps[uid] = {}
    bot.answer_callback_query(call.id)

print("✅ بخش ۵ آماده شد")
# ==================== بخش ۶ از ۶ ====================
# اجرا

print("🤖 ربات Virtual Life با موفقیت روشن شد")
print("=" * 45)
print("توکن:", BOT_TOKEN[:20] + "...")
print("ادمین:", ADMIN_IDS)
print()
print("قابلیت‌های فعال:")
print("• پروفایل کامل (پول + بانک + انرژی + همسر)")
print("• کار کردن با کول‌داون و بونوس خانه/ماشین")
print("• فروشگاه (خانه + ماشین + شغل)")
print("• دزدی چندمرحله‌ای خفن")
print("• مأموریت روزانه")
print("• ازدواج دو طرفه (درخواست + قبول/رد)")
print("• انتقال پول (آیدی / یوزرنیم / ریپلای)")
print("• بانک (واریز و برداشت)")
print("• رتبه‌بندی ثروت و لول")
print("• دعوت دوستان")
print("• اتفاقات تصادفی")
print("• پنل ادمین کامل:")
print("  - لیست کاربران با یوزرنیم و پول و بانک")
print("  - تغییر پول")
print("  - ساخت خانه / ماشین / شغل جدید")
print("  - جستجوی کاربر")
print("  - پیام همگانی")
print("=" * 45)

bot.infinity_polling()
