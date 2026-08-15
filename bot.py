# ==================== بخش ۱ از ۸ - ZOMBIE SURVIVAL ====================
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import random
import time
import json
from datetime import datetime, timedelta

BOT_TOKEN = "8875102057:AAE5JvIk9HhGoeizZhYUjyRvSdCRIsEzoxU"
ADMIN_IDS = [7530457395]

bot = telebot.TeleBot(BOT_TOKEN)
user_steps = {}

def get_db():
    return sqlite3.connect("zombie_survival.db", check_same_thread=False)

def init_db():
    conn = get_db()
    c = conn.cursor()

    # ---------- بازیکن ----------
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        level INTEGER DEFAULT 1,
        xp INTEGER DEFAULT 0,
        hp INTEGER DEFAULT 100,
        max_hp INTEGER DEFAULT 100,
        hunger INTEGER DEFAULT 100,
        thirst INTEGER DEFAULT 100,
        energy INTEGER DEFAULT 100,
        sanity INTEGER DEFAULT 100,
        infection INTEGER DEFAULT 0,
        scrap INTEGER DEFAULT 500,
        zombie_kills INTEGER DEFAULT 0,
        deaths INTEGER DEFAULT 0,
        current_region_id INTEGER DEFAULT NULL,
        current_weapon_id INTEGER DEFAULT NULL,
        current_shelter_id INTEGER DEFAULT NULL,
        clan_id INTEGER DEFAULT NULL,
        is_banned INTEGER DEFAULT 0,
        joined_at TEXT,
        last_active TEXT
    )''')

    # ---------- نقشه ----------
    c.execute('''CREATE TABLE IF NOT EXISTS maps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        image_file_id TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT
    )''')

    # ---------- منطقه (سلسله‌مراتبی) ----------
    c.execute('''CREATE TABLE IF NOT EXISTS regions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        map_id INTEGER,
        parent_id INTEGER DEFAULT NULL,
        name TEXT NOT NULL,
        description TEXT,
        image_file_id TEXT,
        region_type TEXT DEFAULT 'normal',
        danger_level INTEGER DEFAULT 1,
        min_level INTEGER DEFAULT 1,
        zombie_chance INTEGER DEFAULT 40,
        loot_chance INTEGER DEFAULT 50,
        rare_loot_chance INTEGER DEFAULT 10,
        infection_chance INTEGER DEFAULT 15,
        is_active INTEGER DEFAULT 1,
        created_at TEXT,
        FOREIGN KEY(map_id) REFERENCES maps(id),
        FOREIGN KEY(parent_id) REFERENCES regions(id)
    )''')

    # ---------- سلاح ----------
    c.execute('''CREATE TABLE IF NOT EXISTS weapons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        image_file_id TEXT,
        price INTEGER DEFAULT 0,
        damage INTEGER DEFAULT 10,
        ammo_capacity INTEGER DEFAULT 0,
        rarity TEXT DEFAULT 'common',
        min_level INTEGER DEFAULT 1,
        weapon_type TEXT DEFAULT 'gun',
        is_active INTEGER DEFAULT 1
    )''')

    # ---------- پناهگاه ----------
    c.execute('''CREATE TABLE IF NOT EXISTS shelters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        image_file_id TEXT,
        price INTEGER DEFAULT 0,
        defense INTEGER DEFAULT 10,
        capacity INTEGER DEFAULT 5,
        min_level INTEGER DEFAULT 1,
        rarity TEXT DEFAULT 'common',
        is_active INTEGER DEFAULT 1
    )''')

    # ---------- آیتم ----------
    c.execute('''CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        image_file_id TEXT,
        item_type TEXT DEFAULT 'misc',
        price INTEGER DEFAULT 0,
        rarity TEXT DEFAULT 'common',
        max_stack INTEGER DEFAULT 99,
        heal_hp INTEGER DEFAULT 0,
        heal_hunger INTEGER DEFAULT 0,
        heal_thirst INTEGER DEFAULT 0,
        heal_energy INTEGER DEFAULT 0,
        reduce_infection INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1
    )''')

    # ---------- اینونتوری ----------
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        item_type TEXT,
        item_id INTEGER,
        quantity INTEGER DEFAULT 1,
        UNIQUE(user_id, item_type, item_id)
    )''')

    # ---------- زامبی ----------
    c.execute('''CREATE TABLE IF NOT EXISTS zombies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        image_file_id TEXT,
        hp INTEGER DEFAULT 50,
        damage INTEGER DEFAULT 10,
        defense INTEGER DEFAULT 0,
        speed INTEGER DEFAULT 5,
        xp_reward INTEGER DEFAULT 20,
        scrap_reward INTEGER DEFAULT 15,
        infection_chance INTEGER DEFAULT 20,
        rarity TEXT DEFAULT 'common',
        is_active INTEGER DEFAULT 1
    )''')

    # ---------- مأموریت ----------
    c.execute('''CREATE TABLE IF NOT EXISTS quests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        image_file_id TEXT,
        quest_type TEXT DEFAULT 'kill',
        target_id INTEGER,
        target_count INTEGER DEFAULT 1,
        region_id INTEGER,
        reward_xp INTEGER DEFAULT 50,
        reward_scrap INTEGER DEFAULT 100,
        reward_item_id INTEGER,
        is_active INTEGER DEFAULT 1
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS user_quests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        quest_id INTEGER,
        progress INTEGER DEFAULT 0,
        completed INTEGER DEFAULT 0,
        claimed INTEGER DEFAULT 0,
        UNIQUE(user_id, quest_id)
    )''')

    # ---------- کلن ----------
    c.execute('''CREATE TABLE IF NOT EXISTS clans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        description TEXT,
        image_file_id TEXT,
        owner_id INTEGER,
        level INTEGER DEFAULT 1,
        xp INTEGER DEFAULT 0,
        created_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS clan_members (
        clan_id INTEGER,
        user_id INTEGER,
        role TEXT DEFAULT 'member',
        joined_at TEXT,
        PRIMARY KEY(clan_id, user_id)
    )''')

    # ---------- ایونت ----------
    c.execute('''CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        image_file_id TEXT,
        region_id INTEGER,
        start_time TEXT,
        end_time TEXT,
        zombie_multiplier REAL DEFAULT 1.0,
        loot_multiplier REAL DEFAULT 1.0,
        xp_multiplier REAL DEFAULT 1.0,
        is_active INTEGER DEFAULT 1
    )''')

    # ---------- ورلد باس ----------
    c.execute('''CREATE TABLE IF NOT EXISTS world_bosses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        image_file_id TEXT,
        max_hp INTEGER DEFAULT 10000,
        current_hp INTEGER DEFAULT 10000,
        damage INTEGER DEFAULT 50,
        defense INTEGER DEFAULT 20,
        region_id INTEGER,
        start_time TEXT,
        end_time TEXT,
        is_active INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS boss_damage (
        boss_id INTEGER,
        user_id INTEGER,
        damage INTEGER DEFAULT 0,
        claimed INTEGER DEFAULT 0,
        PRIMARY KEY(boss_id, user_id)
    )''')

    # ---------- راهنما ----------
    c.execute('''CREATE TABLE IF NOT EXISTS help_sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT,
        image_file_id TEXT,
        sort_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1
    )''')

    # ---------- لاگ ----------
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        details TEXT,
        created_at TEXT
    )''')

    # تنظیمات
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('start_scrap', '500')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('start_hp', '100')")

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
        c.execute('''INSERT INTO users 
            (user_id, username, full_name, scrap, hp, max_hp, joined_at, last_active)
            VALUES (?, ?, ?, 500, 100, 100, ?, ?)''',
            (user.id, user.username or "", user.full_name or "",
             datetime.now().strftime("%Y-%m-%d %H:%M"),
             datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
    else:
        c.execute("UPDATE users SET username=?, full_name=?, last_active=? WHERE user_id=?",
                  (user.username or "", user.full_name or "",
                   datetime.now().strftime("%Y-%m-%d %H:%M"), user.id))
        conn.commit()
    conn.close()

def get_user(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    conn.close()
    return row

def log_action(uid, action, details=""):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO logs (user_id, action, details, created_at) VALUES (?, ?, ?, ?)",
              (uid, action, details, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

print("✅ بخش ۱ آماده شد - دیتابیس کامل Dynamic")
# ==================== بخش ۲ از ۸ ====================
# منوی اصلی + /start + پروفایل + راهنما پایه

def main_menu(uid):
    m = InlineKeyboardMarkup(row_width=2)
    m.add(
        InlineKeyboardButton("👤 پروفایل", callback_data="profile"),
        InlineKeyboardButton("🗺️ نقشه", callback_data="map")
    )
    m.add(
        InlineKeyboardButton("🔫 سلاح‌ها", callback_data="weapons"),
        InlineKeyboardButton("🏠 پناهگاه", callback_data="shelters")
    )
    m.add(
        InlineKeyboardButton("🎒 کوله‌پشتی", callback_data="inventory"),
        InlineKeyboardButton("🧟 بقا / جستجو", callback_data="explore")
    )
    m.add(
        InlineKeyboardButton("📜 مأموریت‌ها", callback_data="quests"),
        InlineKeyboardButton("👥 کلن", callback_data="clan")
    )
    m.add(
        InlineKeyboardButton("🏆 رتبه‌بندی", callback_data="ranking"),
        InlineKeyboardButton("📖 راهنما", callback_data="help")
    )
    if is_admin(uid):
        m.add(InlineKeyboardButton("👑 پنل مدیریت", callback_data="admin"))
    return m

def get_location_path(region_id):
    """ساخت مسیر کامل موقعیت بازیکن"""
    if not region_id:
        return "نامشخص"
    path = []
    conn = get_db()
    c = conn.cursor()
    current = region_id
    while current:
        c.execute("SELECT id, name, parent_id FROM regions WHERE id=?", (current,))
        row = c.fetchone()
        if not row:
            break
        path.append(row[1])
        current = row[2]
    conn.close()
    path.reverse()
    return " → ".join(path) if path else "نامشخص"

def show_profile(uid, chat_id):
    u = get_user(uid)
    if not u:
        return

    location = get_location_path(u[15])  # current_region_id

    # سلاح فعلی
    weapon_name = "ندارد"
    if u[16]:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT name FROM weapons WHERE id=?", (u[16],))
        w = c.fetchone()
        conn.close()
        if w:
            weapon_name = w[0]

    # پناهگاه فعلی
    shelter_name = "ندارد"
    if u[17]:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT name FROM shelters WHERE id=?", (u[17],))
        s = c.fetchone()
        conn.close()
        if s:
            shelter_name = s[0]

    text = f"""
🧟 **ZOMBIE SURVIVAL** - پروفایل

👤 {u[2]}
🆔 `{u[0]}`

⭐ Level: **{u[3]}** | XP: {u[4]}
❤️ HP: {u[5]}/{u[6]}
🍖 Hunger: {u[7]} | 💧 Thirst: {u[8]}
⚡ Energy: {u[9]} | 🧠 Sanity: {u[10]}
☣️ Infection: **{u[11]}%**

🪙 Scrap: **{u[12]:,}**
🧟 Zombie Kills: {u[13]}
☠️ Deaths: {u[14]}

📍 موقعیت فعلی:
{location}

🔫 سلاح: {weapon_name}
🏠 پناهگاه: {shelter_name}
"""
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=main_menu(uid))

@bot.message_handler(commands=['start'])
def start(message):
    ensure_user(message.from_user)
    uid = message.from_user.id
    u = get_user(uid)

    if u and u[19] == 1:  # is_banned
        bot.reply_to(message, "🚫 حساب شما مسدود شده است.")
        return

    text = """
🧟‍♂️ **ZOMBIE SURVIVAL**

دنیای آخرالزمان شروع شده...
زامبی‌ها همه‌جا هستن.

تو باید زنده بمونی، منابع جمع کنی، سلاح پیدا کنی، پناهگاه بسازی و از Infection جلوگیری کنی.

از منوی زیر شروع کن.
"""
    bot.reply_to(message, text, parse_mode="Markdown", reply_markup=main_menu(uid))

@bot.message_handler(commands=['profile'])
def profile_cmd(message):
    ensure_user(message.from_user)
    show_profile(message.from_user.id, message.chat.id)

@bot.message_handler(commands=['help'])
def help_cmd(message):
    ensure_user(message.from_user)
    show_help(message.chat.id, message.from_user.id)

def show_help(chat_id, uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT title, content FROM help_sections WHERE is_active=1 ORDER BY sort_order, id")
    sections = c.fetchall()
    conn.close()

    if not sections:
        text = """
📖 **راهنمای ZOMBIE SURVIVAL**

هنوز بخشی توسط ادمین اضافه نشده.

دستورات اصلی:
/start - شروع
/profile - پروفایل
/help - راهنما
"""
    else:
        text = "📖 **راهنمای بازی**\n\n"
        for s in sections:
            text += f"**{s[0]}**\n{s[1]}\n\n"

    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=main_menu(uid))

print("✅ بخش ۲ آماده شد")
# ==================== بخش ۳ از ۸ ====================
# نقشه + مناطق + ورود به منطقه + موقعیت

@bot.callback_query_handler(func=lambda call: True)
def main_callbacks(call):
    uid = call.from_user.id
    ensure_user(call.from_user)
    data = call.data

    if data in ["back_main", "back"]:
        bot.edit_message_text("منوی اصلی:", call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))
        bot.answer_callback_query(call.id)
        return

    elif data == "profile":
        show_profile(uid, call.message.chat.id)
        bot.answer_callback_query(call.id)
        return

    elif data == "help":
        show_help(call.message.chat.id, uid)
        bot.answer_callback_query(call.id)
        return

    # ---------- نقشه ----------
    elif data == "map":
        show_maps(uid, call.message.chat.id, call.message.message_id)

    elif data.startswith("select_map_"):
        map_id = int(data.split("_")[2])
        show_map_regions(uid, map_id, call.message.chat.id, call.message.message_id)

    elif data.startswith("select_region_"):
        region_id = int(data.split("_")[2])
        show_region_detail(uid, region_id, call.message.chat.id, call.message.message_id)

    elif data.startswith("enter_region_"):
        region_id = int(data.split("_")[2])
        enter_region(uid, region_id, call.message.chat.id, call.message.message_id)

    elif data.startswith("back_map_"):
        map_id = int(data.split("_")[2])
        show_map_regions(uid, map_id, call.message.chat.id, call.message.message_id)

    # ---------- سلاح ----------
    elif data == "weapons":
        show_weapons(uid, call.message.chat.id, call.message.message_id)

    elif data.startswith("weapon_"):
        weapon_id = int(data.split("_")[1])
        show_weapon_detail(uid, weapon_id, call.message.chat.id, call.message.message_id)

    elif data.startswith("buy_weapon_"):
        weapon_id = int(data.split("_")[2])
        buy_weapon(uid, weapon_id, call)

    # ---------- پناهگاه ----------
    elif data == "shelters":
        show_shelters(uid, call.message.chat.id, call.message.message_id)

    elif data.startswith("shelter_"):
        shelter_id = int(data.split("_")[1])
        show_shelter_detail(uid, shelter_id, call.message.chat.id, call.message.message_id)

    elif data.startswith("buy_shelter_"):
        shelter_id = int(data.split("_")[2])
        buy_shelter(uid, shelter_id, call)

    # ---------- کوله‌پشتی ----------
    elif data == "inventory":
        show_inventory(uid, call.message.chat.id, call.message.message_id)

    # ---------- بقا / جستجو ----------
    elif data == "explore":
        start_explore(uid, call.message.chat.id, call.message.message_id)

    # ---------- مأموریت ----------
    elif data == "quests":
        show_quests(uid, call.message.chat.id, call.message.message_id)

    # ---------- کلن ----------
    elif data == "clan":
        show_clan_menu(uid, call.message.chat.id, call.message.message_id)

    # ---------- رتبه‌بندی ----------
    elif data == "ranking":
        show_ranking(call.message.chat.id, uid)

    # ---------- پنل ادمین ----------
    elif data == "admin" and is_admin(uid):
        show_admin_panel(call.message.chat.id, call.message.message_id)

    bot.answer_callback_query(call.id)

def show_maps(uid, chat_id, message_id=None):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name, description, image_file_id FROM maps WHERE is_active=1")
    maps = c.fetchall()
    conn.close()

    if not maps:
        text = "🗺️ هنوز هیچ نقشه‌ای توسط ادمین ساخته نشده."
        mk = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
        if message_id:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=mk)
        else:
            bot.send_message(chat_id, text, reply_markup=mk)
        return

    u = get_user(uid)
    current_loc = get_location_path(u[15]) if u else "نامشخص"

    text = f"🗺️ **نقشه‌های موجود**\n\n📍 موقعیت فعلی شما:\n{current_loc}\n\nیک نقشه انتخاب کن:"
    mk = InlineKeyboardMarkup(row_width=1)
    for m in maps:
        mk.add(InlineKeyboardButton(f"🗺️ {m[1]}", callback_data=f"select_map_{m[0]}"))
    mk.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))

    # اگر نقشه عکس داشت، اولی رو بفرست
    first_image = maps[0][3] if maps and maps[0][3] else None
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, parse_mode="Markdown", reply_markup=mk)
        except:
            bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=mk)
    else:
        if first_image:
            try:
                bot.send_photo(chat_id, first_image, caption=text, parse_mode="Markdown", reply_markup=mk)
            except:
                bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=mk)
        else:
            bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=mk)

def show_map_regions(uid, map_id, chat_id, message_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name, description, image_file_id FROM maps WHERE id=? AND is_active=1", (map_id,))
    m = c.fetchone()
    if not m:
        bot.answer_callback_query(call.id if 'call' in dir() else None, "نقشه پیدا نشد")
        return

    # مناطق سطح بالا (بدون parent)
    c.execute("SELECT id, name, danger_level, min_level FROM regions WHERE map_id=? AND parent_id IS NULL AND is_active=1", (map_id,))
    regions = c.fetchall()
    conn.close()

    u = get_user(uid)
    current_loc = get_location_path(u[15]) if u else "نامشخص"

    text = f"🗺️ **{m[0]}**\n\n{m[1] or ''}\n\n📍 موقعیت فعلی:\n{current_loc}\n\nمناطق قابل انتخاب:"
    mk = InlineKeyboardMarkup(row_width=1)
    for r in regions:
        danger = "🔴" if r[2] >= 4 else "🟡" if r[2] >= 2 else "🟢"
        mk.add(InlineKeyboardButton(f"{danger} {r[1]} (خطر {r[2]} | لول {r[3]}+)", callback_data=f"select_region_{r[0]}"))
    mk.add(InlineKeyboardButton("🔙 بازگشت به نقشه‌ها", callback_data="map"))

    try:
        bot.edit_message_text(text, chat_id, message_id, parse_mode="Markdown", reply_markup=mk)
    except:
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=mk)

def show_region_detail(uid, region_id, chat_id, message_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM regions WHERE id=? AND is_active=1", (region_id,))
    r = c.fetchone()
    if not r:
        bot.send_message(chat_id, "منطقه پیدا نشد.")
        return

    # زیرمنطقه‌ها
    c.execute("SELECT id, name, danger_level FROM regions WHERE parent_id=? AND is_active=1", (region_id,))
    children = c.fetchall()
    conn.close()

    u = get_user(uid)
    path = get_location_path(region_id)

    text = f"""
📍 **{r[3]}**

{r[4] or 'بدون توضیحات'}

⚠️ سطح خطر: {r[7]}
🔓 حداقل لول: {r[8]}
🏷️ نوع: {r[6]}

📍 مسیر:
{path}
"""
    mk = InlineKeyboardMarkup(row_width=1)
    mk.add(InlineKeyboardButton("🚶 ورود به این منطقه", callback_data=f"enter_region_{region_id}"))

    for ch in children:
        mk.add(InlineKeyboardButton(f"➡️ {ch[1]} (خطر {ch[2]})", callback_data=f"select_region_{ch[0]}"))

    mk.add(InlineKeyboardButton("🔙 بازگشت", callback_data=f"back_map_{r[1]}"))

    # عکس منطقه
    if r[5]:
        try:
            bot.send_photo(chat_id, r[5], caption=text, parse_mode="Markdown", reply_markup=mk)
            return
        except:
            pass
    try:
        bot.edit_message_text(text, chat_id, message_id, parse_mode="Markdown", reply_markup=mk)
    except:
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=mk)

def enter_region(uid, region_id, chat_id, message_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name, min_level, is_active FROM regions WHERE id=?", (region_id,))
    r = c.fetchone()
    if not r or not r[2]:
        bot.send_message(chat_id, "این منطقه در دسترس نیست.")
        conn.close()
        return

    u = get_user(uid)
    if u[3] < r[1]:
        bot.send_message(chat_id, f"برای ورود به این منطقه حداقل لول {r[1]} لازم است.")
        conn.close()
        return

    c.execute("UPDATE users SET current_region_id=? WHERE user_id=?", (region_id, uid))
    conn.commit()
    conn.close()

    path = get_location_path(region_id)
    bot.send_message(chat_id, f"✅ وارد منطقه **{r[0]}** شدی.\n\n📍 موقعیت جدید:\n{path}", parse_mode="Markdown", reply_markup=main_menu(uid))
    log_action(uid, "enter_region", str(region_id))

print("✅ بخش ۳ آماده شد")
# ==================== بخش ۴ از ۸ ====================
# سلاح‌ها + پناهگاه + کوله‌پشتی + خرید

def show_weapons(uid, chat_id, message_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name, price, damage, rarity, min_level FROM weapons WHERE is_active=1 ORDER BY price")
    weapons = c.fetchall()
    conn.close()

    if not weapons:
        text = "🔫 هنوز هیچ سلاحی توسط ادمین اضافه نشده."
        mk = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=mk)
        except:
            bot.send_message(chat_id, text, reply_markup=mk)
        return

    text = "🔫 **سلاح‌های موجود**\n\nیک سلاح انتخاب کن:"
    mk = InlineKeyboardMarkup(row_width=1)
    for w in weapons:
        mk.add(InlineKeyboardButton(f"🔫 {w[1]} | {w[2]:,}🪙 | DMG {w[3]} | {w[4]}", callback_data=f"weapon_{w[0]}"))
    mk.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
    try:
        bot.edit_message_text(text, chat_id, message_id, parse_mode="Markdown", reply_markup=mk)
    except:
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=mk)

def show_weapon_detail(uid, weapon_id, chat_id, message_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM weapons WHERE id=? AND is_active=1", (weapon_id,))
    w = c.fetchone()
    conn.close()
    if not w:
        bot.send_message(chat_id, "سلاح پیدا نشد.")
        return

    text = f"""
🔫 **{w[1]}**

{w[2] or ''}

⚔️ قدرت: {w[5]}
🔫 ظرفیت خشاب: {w[6]}
⭐ کمیابی: {w[7]}
🔓 لول مورد نیاز: {w[8]}
💰 قیمت: **{w[4]:,}** Scrap
"""
    mk = InlineKeyboardMarkup(row_width=1)
    mk.add(InlineKeyboardButton("💰 خرید سلاح", callback_data=f"buy_weapon_{weapon_id}"))
    mk.add(InlineKeyboardButton("🔙 بازگشت", callback_data="weapons"))

    if w[3]:  # image
        try:
            bot.send_photo(chat_id, w[3], caption=text, parse_mode="Markdown", reply_markup=mk)
            return
        except:
            pass
    try:
        bot.edit_message_text(text, chat_id, message_id, parse_mode="Markdown", reply_markup=mk)
    except:
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=mk)

def buy_weapon(uid, weapon_id, call):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name, price, min_level FROM weapons WHERE id=? AND is_active=1", (weapon_id,))
    w = c.fetchone()
    if not w:
        bot.answer_callback_query(call.id, "سلاح موجود نیست", show_alert=True)
        conn.close()
        return

    u = get_user(uid)
    if u[3] < w[2]:
        bot.answer_callback_query(call.id, f"لول {w[2]} لازم است!", show_alert=True)
        conn.close()
        return
    if u[12] < w[1]:
        bot.answer_callback_query(call.id, "Scrap کافی نداری!", show_alert=True)
        conn.close()
        return

    # کم کردن پول و اضافه کردن به اینونتوری + تجهیز
    c.execute("UPDATE users SET scrap = scrap - ?, current_weapon_id = ? WHERE user_id=?", (w[1], weapon_id, uid))
    c.execute("INSERT OR IGNORE INTO inventory (user_id, item_type, item_id, quantity) VALUES (?, 'weapon', ?, 1)", (uid, weapon_id))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, f"✅ {w[0]} خریداری و تجهیز شد!", show_alert=True)
    show_profile(uid, call.message.chat.id)
    log_action(uid, "buy_weapon", str(weapon_id))

def show_shelters(uid, chat_id, message_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name, price, defense, min_level FROM shelters WHERE is_active=1 ORDER BY price")
    shelters = c.fetchall()
    conn.close()

    if not shelters:
        text = "🏠 هنوز هیچ پناهگاهی توسط ادمین اضافه نشده."
        mk = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=mk)
        except:
            bot.send_message(chat_id, text, reply_markup=mk)
        return

    text = "🏠 **پناهگاه‌های موجود**"
    mk = InlineKeyboardMarkup(row_width=1)
    for s in shelters:
        mk.add(InlineKeyboardButton(f"🏠 {s[1]} | {s[2]:,}🪙 | دفاع {s[3]}", callback_data=f"shelter_{s[0]}"))
    mk.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
    try:
        bot.edit_message_text(text, chat_id, message_id, parse_mode="Markdown", reply_markup=mk)
    except:
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=mk)

def show_shelter_detail(uid, shelter_id, chat_id, message_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM shelters WHERE id=? AND is_active=1", (shelter_id,))
    s = c.fetchone()
    conn.close()
    if not s:
        bot.send_message(chat_id, "پناهگاه پیدا نشد.")
        return

    text = f"""
🏠 **{s[1]}**

{s[2] or ''}

🛡️ دفاع: {s[5]}
👥 ظرفیت: {s[6]}
🔓 لول مورد نیاز: {s[7]}
💰 قیمت: **{s[4]:,}** Scrap
"""
    mk = InlineKeyboardMarkup(row_width=1)
    mk.add(InlineKeyboardButton("🏠 خرید پناهگاه", callback_data=f"buy_shelter_{shelter_id}"))
    mk.add(InlineKeyboardButton("🔙 بازگشت", callback_data="shelters"))

    if s[3]:
        try:
            bot.send_photo(chat_id, s[3], caption=text, parse_mode="Markdown", reply_markup=mk)
            return
        except:
            pass
    try:
        bot.edit_message_text(text, chat_id, message_id, parse_mode="Markdown", reply_markup=mk)
    except:
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=mk)

def buy_shelter(uid, shelter_id, call):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name, price, min_level FROM shelters WHERE id=? AND is_active=1", (shelter_id,))
    s = c.fetchone()
    if not s:
        bot.answer_callback_query(call.id, "پناهگاه موجود نیست", show_alert=True)
        conn.close()
        return

    u = get_user(uid)
    if u[3] < s[2]:
        bot.answer_callback_query(call.id, f"لول {s[2]} لازم است!", show_alert=True)
        conn.close()
        return
    if u[12] < s[1]:
        bot.answer_callback_query(call.id, "Scrap کافی نداری!", show_alert=True)
        conn.close()
        return

    c.execute("UPDATE users SET scrap = scrap - ?, current_shelter_id = ? WHERE user_id=?", (s[1], shelter_id, uid))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, f"✅ {s[0]} خریداری شد!", show_alert=True)
    show_profile(uid, call.message.chat.id)
    log_action(uid, "buy_shelter", str(shelter_id))

def show_inventory(uid, chat_id, message_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT item_type, item_id, quantity FROM inventory WHERE user_id=? AND quantity > 0", (uid,))
    items = c.fetchall()

    text = "🎒 **کوله‌پشتی**\n\n"
    if not items:
        text += "خالی است."
    else:
        for it in items:
            if it[0] == "weapon":
                c.execute("SELECT name FROM weapons WHERE id=?", (it[1],))
                name = c.fetchone()
                text += f"🔫 {name[0] if name else 'سلاح'} ×{it[2]}\n"
            elif it[0] == "item":
                c.execute("SELECT name FROM items WHERE id=?", (it[1],))
                name = c.fetchone()
                text += f"📦 {name[0] if name else 'آیتم'} ×{it[2]}\n"
            else:
                text += f"• {it[0]} #{it[1]} ×{it[2]}\n"
    conn.close()

    mk = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
    try:
        bot.edit_message_text(text, chat_id, message_id, parse_mode="Markdown", reply_markup=mk)
    except:
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=mk)

print("✅ بخش ۴ آماده شد")
# ==================== بخش ۵ از ۸ ====================
# سیستم جستجو (Explore) + مبارزه با زامبی

def start_explore(uid, chat_id, message_id):
    u = get_user(uid)
    if not u or not u[15]:
        text = "اول باید وارد یک منطقه بشی.\nاز بخش 🗺️ نقشه یک منطقه انتخاب کن و وارد شو."
        mk = InlineKeyboardMarkup().add(InlineKeyboardButton("🗺️ رفتن به نقشه", callback_data="map"),
                                        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=mk)
        except:
            bot.send_message(chat_id, text, reply_markup=mk)
        return

    if u[9] < 10:  # energy
        bot.send_message(chat_id, "⚡ انرژی کافی برای جستجو نداری!", reply_markup=main_menu(uid))
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name, zombie_chance, loot_chance, rare_loot_chance, infection_chance, danger_level FROM regions WHERE id=?", (u[15],))
    region = c.fetchone()
    conn.close()

    if not region:
        bot.send_message(chat_id, "منطقه نامعتبر است.", reply_markup=main_menu(uid))
        return

    # کم کردن انرژی
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET energy = energy - 10 WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()

    # تصمیم‌گیری اتفاق
    roll = random.randint(1, 100)
    zombie_chance = region[1] or 40

    if roll <= zombie_chance:
        # برخورد با زامبی
        start_combat(uid, chat_id, message_id)
    elif roll <= zombie_chance + (region[2] or 30):
        # لوت معمولی
        give_loot(uid, chat_id, rare=False)
    elif roll <= zombie_chance + (region[2] or 30) + (region[3] or 10):
        # لوت کمیاب
        give_loot(uid, chat_id, rare=True)
    else:
        # چیزی پیدا نشد + احتمال عفونت
        text = f"🔍 تو منطقه **{region[0]}** جستجو کردی...\n\nچیزی پیدا نشد."
        if random.randint(1, 100) <= (region[4] or 10):
            add_infection(uid, random.randint(3, 12))
            text += "\n\n☣️ احساس بیماری می‌کنی... Infection افزایش یافت!"
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=main_menu(uid))

def give_loot(uid, chat_id, rare=False):
    conn = get_db()
    c = conn.cursor()
    if rare:
        c.execute("SELECT id, name FROM items WHERE is_active=1 AND rarity IN ('rare','epic','legendary') ORDER BY RANDOM() LIMIT 1")
    else:
        c.execute("SELECT id, name FROM items WHERE is_active=1 ORDER BY RANDOM() LIMIT 1")
    item = c.fetchone()

    scrap = random.randint(20, 80) if not rare else random.randint(80, 250)
    c.execute("UPDATE users SET scrap = scrap + ? WHERE user_id=?", (scrap, uid))

    text = f"🎒 چیزی پیدا کردی!\n\n🪙 +{scrap} Scrap"
    if item:
        c.execute("INSERT INTO inventory (user_id, item_type, item_id, quantity) VALUES (?, 'item', ?, 1) ON CONFLICT(user_id, item_type, item_id) DO UPDATE SET quantity = quantity + 1", (uid, item[0]))
        text += f"\n📦 {item[1]} ×1"
    conn.commit()
    conn.close()
    bot.send_message(chat_id, text, reply_markup=main_menu(uid))

def add_infection(uid, amount):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET infection = MIN(100, infection + ?) WHERE user_id=?", (amount, uid))
    conn.commit()
    conn.close()

def start_combat(uid, chat_id, message_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name, hp, damage, defense, xp_reward, scrap_reward, infection_chance, image_file_id FROM zombies WHERE is_active=1 ORDER BY RANDOM() LIMIT 1")
    z = c.fetchone()
    conn.close()

    if not z:
        bot.send_message(chat_id, "زامبی‌ای برای مبارزه تعریف نشده. ادمین باید زامبی اضافه کند.", reply_markup=main_menu(uid))
        return

    # ذخیره وضعیت مبارزه موقت
    user_steps[uid] = {
        "step": "combat",
        "zombie_id": z[0],
        "zombie_name": z[1],
        "zombie_hp": z[2],
        "zombie_max_hp": z[2],
        "zombie_damage": z[3],
        "zombie_defense": z[4],
        "xp_reward": z[5],
        "scrap_reward": z[6],
        "infection_chance": z[7]
    }

    u = get_user(uid)
    text = f"""
⚔️ **مبارزه شروع شد!**

🧟 **{z[1]}**
❤️ HP: {z[2]}/{z[2]}

👤 تو
❤️ HP: {u[5]}/{u[6]}
"""
    mk = InlineKeyboardMarkup(row_width=2)
    mk.add(
        InlineKeyboardButton("⚔️ حمله", callback_data="combat_attack"),
        InlineKeyboardButton("🏃 فرار", callback_data="combat_escape")
    )
    mk.add(InlineKeyboardButton("🎒 کوله‌پشتی", callback_data="inventory"))

    if z[8]:
        try:
            bot.send_photo(chat_id, z[8], caption=text, parse_mode="Markdown", reply_markup=mk)
            return
        except:
            pass
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=mk)

@bot.callback_query_handler(func=lambda call: call.data in ["combat_attack", "combat_escape"])
def combat_handler(call):
    uid = call.from_user.id
    data = call.data
    combat = user_steps.get(uid, {})

    if combat.get("step") != "combat":
        bot.answer_callback_query(call.id, "مبارزه منقضی شده", show_alert=True)
        return

    u = get_user(uid)

    if data == "combat_escape":
        # شانس فرار
        if random.randint(1, 100) <= 55:
            user_steps[uid] = {}
            bot.edit_message_text("🏃 با موفقیت فرار کردی!", call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))
        else:
            # زامبی حمله می‌کنه
            dmg = max(1, combat["zombie_damage"] - 5)
            new_hp = max(0, u[5] - dmg)
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE users SET hp=? WHERE user_id=?", (new_hp, uid))
            conn.commit()
            conn.close()
            if new_hp <= 0:
                handle_death(uid, call.message.chat.id)
                user_steps[uid] = {}
            else:
                bot.edit_message_text(f"❌ فرار ناموفق!\nزامبی بهت زد: -{dmg} HP\n❤️ HP باقی‌مانده: {new_hp}", call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))
        bot.answer_callback_query(call.id)
        return

    # حمله بازیکن
    weapon_damage = 8
    if u[16]:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT damage FROM weapons WHERE id=?", (u[16],))
        w = c.fetchone()
        conn.close()
        if w:
            weapon_damage = w[0]

    player_dmg = max(1, weapon_damage - combat["zombie_defense"] // 2)
    combat["zombie_hp"] -= player_dmg

    if combat["zombie_hp"] <= 0:
        # پیروزی
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET scrap = scrap + ?, zombie_kills = zombie_kills + 1, xp = xp + ? WHERE user_id=?",
                  (combat["scrap_reward"], combat["xp_reward"], uid))
        conn.commit()
        conn.close()

        # چک لول‌آپ ساده
        u2 = get_user(uid)
        needed = u2[3] * 100
        if u2[4] >= needed:
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE users SET level = level + 1, xp = xp - ?, scrap = scrap + 200 WHERE user_id=?", (needed, uid))
            conn.commit()
            conn.close()

        text = f"""
✅ **پیروزی!**

🧟 {combat['zombie_name']} کشته شد.

🪙 +{combat['scrap_reward']} Scrap
⭐ +{combat['xp_reward']} XP
"""
        if random.randint(1, 100) <= combat["infection_chance"]:
            add_infection(uid, random.randint(5, 15))
            text += "\n☣️ گاز گرفته شدی! Infection افزایش یافت."

        user_steps[uid] = {}
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=main_menu(uid))
        log_action(uid, "kill_zombie", combat["zombie_name"])
        bot.answer_callback_query(call.id)
        return

    # نوبت زامبی
    zombie_dmg = max(1, combat["zombie_damage"] - 3)
    new_hp = max(0, u[5] - zombie_dmg)
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET hp=? WHERE user_id=?", (new_hp, uid))
    conn.commit()
    conn.close()

    if new_hp <= 0:
        handle_death(uid, call.message.chat.id)
        user_steps[uid] = {}
        bot.answer_callback_query(call.id)
        return

    # ادامه مبارزه
    user_steps[uid] = combat
    text = f"""
⚔️ **ادامه مبارزه**

🧟 {combat['zombie_name']}
❤️ HP: {combat['zombie_hp']}/{combat['zombie_max_hp']}

👤 تو
❤️ HP: {new_hp}/{u[6]}

تو زدی: -{player_dmg}
زامبی زد: -{zombie_dmg}
"""
    mk = InlineKeyboardMarkup(row_width=2)
    mk.add(
        InlineKeyboardButton("⚔️ حمله", callback_data="combat_attack"),
        InlineKeyboardButton("🏃 فرار", callback_data="combat_escape")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)
    bot.answer_callback_query(call.id)

def handle_death(uid, chat_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET deaths = deaths + 1, hp = max_hp, energy = 50, infection = MAX(0, infection - 10) WHERE user_id=?", (uid,))
    # از دست دادن کمی scrap
    c.execute("UPDATE users SET scrap = MAX(0, scrap - 50) WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()
    bot.send_message(chat_id, "☠️ **کشته شدی!**\n\nدوباره زنده شدی ولی کمی Scrap از دست دادی و Infection کمی کم شد.", reply_markup=main_menu(uid))
    log_action(uid, "death")

print("✅ بخش ۵ آماده شد")
# ==================== بخش ۶ از ۸ ====================
# مأموریت + کلن + رتبه‌بندی + پایه ایونت

def show_quests(uid, chat_id, message_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT q.id, q.name, q.description, q.target_count, q.reward_xp, q.reward_scrap, uq.progress, uq.completed FROM quests q LEFT JOIN user_quests uq ON q.id = uq.quest_id AND uq.user_id=? WHERE q.is_active=1", (uid,))
    quests = c.fetchall()
    conn.close()

    if not quests:
        text = "📜 هنوز هیچ مأموریتی توسط ادمین ساخته نشده."
    else:
        text = "📜 **مأموریت‌های فعال**\n\n"
        for q in quests:
            progress = q[6] or 0
            status = "✅ انجام شده" if q[7] else f"پیشرفت: {progress}/{q[3]}"
            text += f"**{q[1]}**\n{q[2] or ''}\n{status}\nجایزه: {q[5]}🪙 + {q[4]} XP\n\n"

    mk = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
    try:
        bot.edit_message_text(text, chat_id, message_id, parse_mode="Markdown", reply_markup=mk)
    except:
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=mk)

def show_clan_menu(uid, chat_id, message_id):
    u = get_user(uid)
    text = "👥 **سیستم کلن**\n\n"
    mk = InlineKeyboardMarkup(row_width=1)

    if u[18]:  # clan_id
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT name, level, xp FROM clans WHERE id=?", (u[18],))
        clan = c.fetchone()
        conn.close()
        if clan:
            text += f"کلن فعلی: **{clan[0]}**\nلول کلن: {clan[1]}\nXP: {clan[2]}"
            mk.add(InlineKeyboardButton("🚪 خروج از کلن", callback_data="clan_leave"))
        else:
            text += "کلن پیدا نشد."
    else:
        text += "تو هنوز عضو هیچ کلنی نیستی."
        mk.add(InlineKeyboardButton("➕ ساخت کلن", callback_data="clan_create"))
        mk.add(InlineKeyboardButton("🔎 جستجوی کلن", callback_data="clan_search"))

    mk.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
    try:
        bot.edit_message_text(text, chat_id, message_id, parse_mode="Markdown", reply_markup=mk)
    except:
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=mk)

@bot.callback_query_handler(func=lambda call: call.data in ["clan_create", "clan_search", "clan_leave"])
def clan_actions(call):
    uid = call.from_user.id
    data = call.data

    if data == "clan_create":
        user_steps[uid] = {"step": "clan_name"}
        bot.edit_message_text("نام کلن را بفرست (حداقل ۳ حرف):", call.message.chat.id, call.message.message_id)
    elif data == "clan_leave":
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET clan_id=NULL WHERE user_id=?", (uid,))
        c.execute("DELETE FROM clan_members WHERE user_id=?", (uid,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "از کلن خارج شدی", show_alert=True)
        show_clan_menu(uid, call.message.chat.id, call.message.message_id)
    elif data == "clan_search":
        bot.edit_message_text("فعلاً ساخت کلن فعال است. جستجو به زودی کامل‌تر می‌شود.", call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))
    bot.answer_callback_query(call.id)

def show_ranking(chat_id, uid):
    conn = get_db()
    c = conn.cursor()

    text = "🏆 **رتبه‌بندی**\n\n"

    # Level
    c.execute("SELECT full_name, username, level FROM users ORDER BY level DESC, xp DESC LIMIT 8")
    text += "⭐ **بالاترین لول**\n"
    for i, r in enumerate(c.fetchall(), 1):
        name = r[0] or (f"@{r[1]}" if r[1] else "ناشناس")
        text += f"{i}. {name} — لول {r[2]}\n"

    # Zombie Kills
    c.execute("SELECT full_name, username, zombie_kills FROM users ORDER BY zombie_kills DESC LIMIT 8")
    text += "\n🧟 **بیشترین کشتار زامبی**\n"
    for i, r in enumerate(c.fetchall(), 1):
        name = r[0] or (f"@{r[1]}" if r[1] else "ناشناس")
        text += f"{i}. {name} — {r[2]} کشته\n"

    # Wealth
    c.execute("SELECT full_name, username, scrap FROM users ORDER BY scrap DESC LIMIT 8")
    text += "\n🪙 **ثروتمندترین‌ها**\n"
    for i, r in enumerate(c.fetchall(), 1):
        name = r[0] or (f"@{r[1]}" if r[1] else "ناشناس")
        text += f"{i}. {name} — {r[2]:,} Scrap\n"

    conn.close()
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=main_menu(uid))

print("✅ بخش ۶ آماده شد")
# ==================== بخش ۷ از ۸ ====================
# پنل ادمین (فقط پیوی + فقط ادمین اصلی)

def show_admin_panel(chat_id, message_id=None):
    mk = InlineKeyboardMarkup(row_width=2)
    mk.add(
        InlineKeyboardButton("🗺️ نقشه‌ها", callback_data="adm_maps"),
        InlineKeyboardButton("📍 مناطق", callback_data="adm_regions")
    )
    mk.add(
        InlineKeyboardButton("🔫 سلاح‌ها", callback_data="adm_weapons"),
        InlineKeyboardButton("🏠 پناهگاه‌ها", callback_data="adm_shelters")
    )
    mk.add(
        InlineKeyboardButton("📦 آیتم‌ها", callback_data="adm_items"),
        InlineKeyboardButton("🧟 زامبی‌ها", callback_data="adm_zombies")
    )
    mk.add(
        InlineKeyboardButton("📜 مأموریت‌ها", callback_data="adm_quests"),
        InlineKeyboardButton("📖 راهنما", callback_data="adm_help")
    )
    mk.add(
        InlineKeyboardButton("👤 مدیریت کاربر", callback_data="adm_users"),
        InlineKeyboardButton("📢 پیام همگانی", callback_data="adm_broadcast")
    )
    mk.add(
        InlineKeyboardButton("📊 آمار ربات", callback_data="adm_stats"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")
    )
    text = "👑 **پنل مدیریت ZOMBIE SURVIVAL**\n\nفقط برای ادمین اصلی و فقط در پیوی ربات."
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, parse_mode="Markdown", reply_markup=mk)
        except:
            bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=mk)
    else:
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=mk)

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_") or call.data.startswith("admin"))
def admin_callbacks(call):
    uid = call.from_user.id

    # فقط ادمین اصلی
    if not is_admin(uid):
        bot.answer_callback_query(call.id, "دسترسی نداری!", show_alert=True)
        return

    # فقط در پیوی
    if call.message.chat.type != "private":
        bot.answer_callback_query(call.id, "پنل ادمین فقط در پیوی ربات کار می‌کند!", show_alert=True)
        return

    data = call.data

    if data == "admin":
        show_admin_panel(call.message.chat.id, call.message.message_id)

    # ---------- آمار ----------
    elif data == "adm_stats":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM maps")
        maps = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM regions")
        regions = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM weapons")
        weapons = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM zombies")
        zombies = c.fetchone()[0]
        conn.close()
        text = f"""
📊 **آمار ربات**

👥 کاربران: {users}
🗺️ نقشه‌ها: {maps}
📍 مناطق: {regions}
🔫 سلاح‌ها: {weapons}
🧟 زامبی‌ها: {zombies}
"""
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

    # ---------- مدیریت کاربر ----------
    elif data == "adm_users":
        user_steps[uid] = {"step": "adm_find_user"}
        bot.edit_message_text("آیدی عددی یا یوزرنیم کاربر را بفرست:", call.message.chat.id, call.message.message_id)

    # ---------- پیام همگانی ----------
    elif data == "adm_broadcast":
        user_steps[uid] = {"step": "adm_broadcast"}
        bot.edit_message_text("پیام همگانی را بفرست:", call.message.chat.id, call.message.message_id)

    # ---------- نقشه‌ها ----------
    elif data == "adm_maps":
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(
            InlineKeyboardButton("➕ افزودن نقشه", callback_data="adm_add_map"),
            InlineKeyboardButton("📋 لیست نقشه‌ها", callback_data="adm_list_maps"),
            InlineKeyboardButton("🔙", callback_data="admin")
        )
        bot.edit_message_text("🗺️ مدیریت نقشه‌ها:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "adm_add_map":
        user_steps[uid] = {"step": "adm_map_name"}
        bot.edit_message_text("نام نقشه را بفرست:", call.message.chat.id, call.message.message_id)

    elif data == "adm_list_maps":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, name, is_active FROM maps ORDER BY id DESC")
        rows = c.fetchall()
        conn.close()
        text = "📋 لیست نقشه‌ها:\n\n"
        mk = InlineKeyboardMarkup(row_width=1)
        for r in rows:
            status = "🟢" if r[2] else "🔴"
            text += f"{status} #{r[0]} — {r[1]}\n"
            mk.add(InlineKeyboardButton(f"{'🔴 غیرفعال' if r[2] else '🟢 فعال'} #{r[0]}", callback_data=f"adm_toggle_map_{r[0]}"))
        mk.add(InlineKeyboardButton("🔙", callback_data="adm_maps"))
        bot.send_message(call.message.chat.id, text, reply_markup=mk)

    elif data.startswith("adm_toggle_map_"):
        mid = int(data.split("_")[3])
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE maps SET is_active = 1 - is_active WHERE id=?", (mid,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "وضعیت تغییر کرد", show_alert=True)

    # ---------- سلاح‌ها ----------
    elif data == "adm_weapons":
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(
            InlineKeyboardButton("➕ افزودن سلاح", callback_data="adm_add_weapon"),
            InlineKeyboardButton("📋 لیست سلاح‌ها", callback_data="adm_list_weapons"),
            InlineKeyboardButton("🔙", callback_data="admin")
        )
        bot.edit_message_text("🔫 مدیریت سلاح‌ها:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "adm_add_weapon":
        user_steps[uid] = {"step": "adm_weapon_name"}
        bot.edit_message_text("نام سلاح را بفرست:", call.message.chat.id, call.message.message_id)

    elif data == "adm_list_weapons":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, name, price, damage, is_active FROM weapons ORDER BY id DESC LIMIT 20")
        rows = c.fetchall()
        conn.close()
        text = "📋 سلاح‌ها:\n\n"
        for r in rows:
            status = "🟢" if r[4] else "🔴"
            text += f"{status} #{r[0]} {r[1]} | {r[2]}🪙 | DMG {r[3]}\n"
        bot.send_message(call.message.chat.id, text)

    # ---------- زامبی‌ها ----------
    elif data == "adm_zombies":
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(
            InlineKeyboardButton("➕ افزودن زامبی", callback_data="adm_add_zombie"),
            InlineKeyboardButton("📋 لیست زامبی‌ها", callback_data="adm_list_zombies"),
            InlineKeyboardButton("🔙", callback_data="admin")
        )
        bot.edit_message_text("🧟 مدیریت زامبی‌ها:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "adm_add_zombie":
        user_steps[uid] = {"step": "adm_zombie_name"}
        bot.edit_message_text("نام زامبی را بفرست:", call.message.chat.id, call.message.message_id)

    elif data == "adm_list_zombies":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, name, hp, damage, is_active FROM zombies ORDER BY id DESC LIMIT 20")
        rows = c.fetchall()
        conn.close()
        text = "📋 زامبی‌ها:\n\n"
        for r in rows:
            status = "🟢" if r[4] else "🔴"
            text += f"{status} #{r[0]} {r[1]} | HP {r[2]} | DMG {r[3]}\n"
        bot.send_message(call.message.chat.id, text)

    # ---------- پناهگاه ----------
    elif data == "adm_shelters":
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(
            InlineKeyboardButton("➕ افزودن پناهگاه", callback_data="adm_add_shelter"),
            InlineKeyboardButton("🔙", callback_data="admin")
        )
        bot.edit_message_text("🏠 مدیریت پناهگاه:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "adm_add_shelter":
        user_steps[uid] = {"step": "adm_shelter_name"}
        bot.edit_message_text("نام پناهگاه را بفرست:", call.message.chat.id, call.message.message_id)

    # ---------- آیتم ----------
    elif data == "adm_items":
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(
            InlineKeyboardButton("➕ افزودن آیتم", callback_data="adm_add_item"),
            InlineKeyboardButton("🔙", callback_data="admin")
        )
        bot.edit_message_text("📦 مدیریت آیتم:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "adm_add_item":
        user_steps[uid] = {"step": "adm_item_name"}
        bot.edit_message_text("نام آیتم را بفرست:", call.message.chat.id, call.message.message_id)

    # ---------- مناطق ----------
    elif data == "adm_regions":
        user_steps[uid] = {"step": "adm_region_map"}
        bot.edit_message_text("اول آیدی نقشه را بفرست (از لیست نقشه‌ها ببین):", call.message.chat.id, call.message.message_id)

    # ---------- مأموریت و راهنما ----------
    elif data == "adm_quests":
        user_steps[uid] = {"step": "adm_quest_name"}
        bot.edit_message_text("نام مأموریت را بفرست:", call.message.chat.id, call.message.message_id)

    elif data == "adm_help":
        user_steps[uid] = {"step": "adm_help_title"}
        bot.edit_message_text("عنوان بخش راهنما را بفرست:", call.message.chat.id, call.message.message_id)

    bot.answer_callback_query(call.id)

print("✅ بخش ۷ آماده شد - پنل ادمین (فقط پیوی + فقط ادمین)")
# ==================== بخش ۸ از ۸ ====================
# هندلر پیام‌های ادمین + ساخت محتوا + مدیریت کاربر + اجرا

@bot.message_handler(content_types=['text', 'photo'])
def handle_all(message):
    uid = message.from_user.id
    ensure_user(message.from_user)

    # فقط ادمین و فقط پیوی برای عملیات حساس
    step_data = user_steps.get(uid, {})
    step = step_data.get("step")

    if not step:
        if message.chat.type == "private":
            bot.reply_to(message, "از منو استفاده کن یا /start بزن.", reply_markup=main_menu(uid))
        return

    text = message.text.strip() if message.text else ""

    # ========== مدیریت کاربر ==========
    if step == "adm_find_user" and is_admin(uid) and message.chat.type == "private":
        target = None
        text_clean = text.lstrip("@")
        conn = get_db()
        c = conn.cursor()
        if text_clean.isdigit():
            c.execute("SELECT * FROM users WHERE user_id=?", (int(text_clean),))
        else:
            c.execute("SELECT * FROM users WHERE username=?", (text_clean,))
        target = c.fetchone()
        conn.close()

        if not target:
            bot.reply_to(message, "کاربر پیدا نشد.")
            user_steps[uid] = {}
            return

        user_steps[uid] = {"step": "adm_user_action", "target": target[0]}
        mk = InlineKeyboardMarkup(row_width=2)
        mk.add(
            InlineKeyboardButton("💰 دادن Scrap", callback_data=f"adm_give_scrap_{target[0]}"),
            InlineKeyboardButton("📉 کم کردن Scrap", callback_data=f"adm_take_scrap_{target[0]}")
        )
        mk.add(
            InlineKeyboardButton("⭐ دادن XP/Level", callback_data=f"adm_give_xp_{target[0]}"),
            InlineKeyboardButton("🚫 بن / آنبن", callback_data=f"adm_ban_{target[0]}")
        )
        mk.add(InlineKeyboardButton("🔙", callback_data="admin"))

        info = f"""
👤 کاربر پیدا شد:
آیدی: `{target[0]}`
یوزرنیم: @{target[1] or '-'}
نام: {target[2]}
Level: {target[3]} | XP: {target[4]}
HP: {target[5]}/{target[6]}
Scrap: {target[12]:,}
Infection: {target[11]}%
بن: {'بله' if target[19] else 'خیر'}
"""
        bot.reply_to(message, info, parse_mode="Markdown", reply_markup=mk)
        return

    # ========== ساخت نقشه ==========
    if step == "adm_map_name" and is_admin(uid):
        user_steps[uid] = {"step": "adm_map_desc", "name": text}
        bot.reply_to(message, "توضیحات نقشه را بفرست (یا بنویس -):")
        return

    if step == "adm_map_desc" and is_admin(uid):
        user_steps[uid] = {"step": "adm_map_photo", "name": step_data["name"], "desc": text if text != "-" else ""}
        bot.reply_to(message, "عکس نقشه را بفرست (یا بنویس رد کردن):")
        return

    if step == "adm_map_photo" and is_admin(uid):
        file_id = None
        if message.photo:
            file_id = message.photo[-1].file_id
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO maps (name, description, image_file_id, is_active, created_at) VALUES (?, ?, ?, 1, ?)",
                  (step_data["name"], step_data.get("desc", ""), file_id, datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ نقشه «{step_data['name']}» ساخته شد.", reply_markup=main_menu(uid))
        user_steps[uid] = {}
        return

    # ========== ساخت سلاح ==========
    if step == "adm_weapon_name" and is_admin(uid):
        user_steps[uid] = {"step": "adm_weapon_price", "name": text}
        bot.reply_to(message, "قیمت سلاح (Scrap):")
        return

    if step == "adm_weapon_price" and is_admin(uid):
        user_steps[uid] = {"step": "adm_weapon_damage", "name": step_data["name"], "price": text}
        bot.reply_to(message, "قدرت (Damage) سلاح:")
        return

    if step == "adm_weapon_damage" and is_admin(uid):
        try:
            name = step_data["name"]
            price = int(step_data["price"])
            damage = int(text)
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO weapons (name, price, damage, ammo_capacity, rarity, min_level, is_active) VALUES (?, ?, ?, 30, 'common', 1, 1)",
                      (name, price, damage))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ سلاح «{name}» اضافه شد.\nقیمت: {price} | قدرت: {damage}", reply_markup=main_menu(uid))
        except:
            bot.reply_to(message, "مقادیر عددی وارد کن.")
        user_steps[uid] = {}
        return

    # ========== ساخت زامبی ==========
    if step == "adm_zombie_name" and is_admin(uid):
        user_steps[uid] = {"step": "adm_zombie_hp", "name": text}
        bot.reply_to(message, "HP زامبی:")
        return

    if step == "adm_zombie_hp" and is_admin(uid):
        user_steps[uid] = {"step": "adm_zombie_damage", "name": step_data["name"], "hp": text}
        bot.reply_to(message, "Damage زامبی:")
        return

    if step == "adm_zombie_damage" and is_admin(uid):
        try:
            name = step_data["name"]
            hp = int(step_data["hp"])
            damage = int(text)
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO zombies (name, hp, damage, defense, speed, xp_reward, scrap_reward, infection_chance, is_active) VALUES (?, ?, ?, 5, 5, 25, 20, 20, 1)",
                      (name, hp, damage))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ زامبی «{name}» اضافه شد.\nHP: {hp} | DMG: {damage}", reply_markup=main_menu(uid))
        except:
            bot.reply_to(message, "مقادیر عددی وارد کن.")
        user_steps[uid] = {}
        return

    # ========== ساخت پناهگاه ==========
    if step == "adm_shelter_name" and is_admin(uid):
        user_steps[uid] = {"step": "adm_shelter_price", "name": text}
        bot.reply_to(message, "قیمت پناهگاه:")
        return

    if step == "adm_shelter_price" and is_admin(uid):
        try:
            name = step_data["name"]
            price = int(text)
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO shelters (name, price, defense, capacity, min_level, is_active) VALUES (?, ?, 20, 5, 1, 1)", (name, price))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ پناهگاه «{name}» اضافه شد.", reply_markup=main_menu(uid))
        except:
            bot.reply_to(message, "قیمت عدد باشد.")
        user_steps[uid] = {}
        return

    # ========== ساخت آیتم ==========
    if step == "adm_item_name" and is_admin(uid):
        user_steps[uid] = {"step": "adm_item_price", "name": text}
        bot.reply_to(message, "قیمت آیتم:")
        return

    if step == "adm_item_price" and is_admin(uid):
        try:
            name = step_data["name"]
            price = int(text)
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO items (name, price, item_type, rarity, max_stack, is_active) VALUES (?, ?, 'misc', 'common', 50, 1)", (name, price))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ آیتم «{name}» اضافه شد.", reply_markup=main_menu(uid))
        except:
            bot.reply_to(message, "قیمت عدد باشد.")
        user_steps[uid] = {}
        return

    # ========== ساخت منطقه ==========
    if step == "adm_region_map" and is_admin(uid):
        user_steps[uid] = {"step": "adm_region_name", "map_id": text}
        bot.reply_to(message, "نام منطقه را بفرست:")
        return

    if step == "adm_region_name" and is_admin(uid):
        try:
            map_id = int(step_data["map_id"])
            name = text
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO regions (map_id, name, danger_level, min_level, zombie_chance, loot_chance, is_active, created_at) VALUES (?, ?, 2, 1, 40, 50, 1, ?)",
                      (map_id, name, datetime.now().strftime("%Y-%m-%d %H:%M")))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ منطقه «{name}» به نقشه #{map_id} اضافه شد.", reply_markup=main_menu(uid))
        except Exception as e:
            bot.reply_to(message, f"خطا: {e}")
        user_steps[uid] = {}
        return

    # ========== ساخت مأموریت ==========
    if step == "adm_quest_name" and is_admin(uid):
        user_steps[uid] = {"step": "adm_quest_desc", "name": text}
        bot.reply_to(message, "توضیحات مأموریت:")
        return

    if step == "adm_quest_desc" and is_admin(uid):
        try:
            name = step_data["name"]
            desc = text
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO quests (name, description, target_count, reward_xp, reward_scrap, is_active) VALUES (?, ?, 5, 50, 100, 1)", (name, desc))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ مأموریت «{name}» اضافه شد.", reply_markup=main_menu(uid))
        except:
            bot.reply_to(message, "خطا در ساخت مأموریت.")
        user_steps[uid] = {}
        return

    # ========== راهنما ==========
    if step == "adm_help_title" and is_admin(uid):
        user_steps[uid] = {"step": "adm_help_content", "title": text}
        bot.reply_to(message, "متن راهنما را بفرست:")
        return

    if step == "adm_help_content" and is_admin(uid):
        title = step_data["title"]
        content = text
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO help_sections (title, content, sort_order, is_active) VALUES (?, ?, 0, 1)", (title, content))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ بخش راهنما «{title}» اضافه شد.", reply_markup=main_menu(uid))
        user_steps[uid] = {}
        return

    # ========== پیام همگانی ==========
    if step == "adm_broadcast" and is_admin(uid):
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
        bot.reply_to(message, f"✅ پیام به {ok} کاربر ارسال شد.", reply_markup=main_menu(uid))
        user_steps[uid] = {}
        return

    # ========== ساخت کلن توسط کاربر ==========
    if step == "clan_name":
        if len(text) < 3:
            bot.reply_to(message, "نام کلن حداقل ۳ حرف باشد.")
            return
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO clans (name, owner_id, created_at) VALUES (?, ?, ?)",
                      (text, uid, datetime.now().strftime("%Y-%m-%d %H:%M")))
            clan_id = c.lastrowid
            c.execute("INSERT INTO clan_members (clan_id, user_id, role, joined_at) VALUES (?, ?, 'owner', ?)",
                      (clan_id, uid, datetime.now().strftime("%Y-%m-%d %H:%M")))
            c.execute("UPDATE users SET clan_id=? WHERE user_id=?", (clan_id, uid))
            conn.commit()
            bot.reply_to(message, f"✅ کلن «{text}» ساخته شد و تو صاحبش هستی.", reply_markup=main_menu(uid))
        except:
            bot.reply_to(message, "این نام قبلاً استفاده شده.")
        conn.close()
        user_steps[uid] = {}
        return

# کال‌بک‌های سریع ادمین برای کاربر
@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_give_scrap_") or call.data.startswith("adm_take_scrap_") or call.data.startswith("adm_ban_") or call.data.startswith("adm_give_xp_"))
def admin_user_actions(call):
    uid = call.from_user.id
    if not is_admin(uid) or call.message.chat.type != "private":
        bot.answer_callback_query(call.id, "دسترسی نداری", show_alert=True)
        return

    parts = call.data.split("_")
    action = parts[1]  # give / take / ban
    target = int(parts[-1])

    if action == "give" and "scrap" in call.data:
        user_steps[uid] = {"step": "adm_set_scrap", "target": target, "mode": "add"}
        bot.edit_message_text("مقدار Scrap برای اضافه کردن:", call.message.chat.id, call.message.message_id)
    elif action == "take":
        user_steps[uid] = {"step": "adm_set_scrap", "target": target, "mode": "remove"}
        bot.edit_message_text("مقدار Scrap برای کم کردن:", call.message.chat.id, call.message.message_id)
    elif action == "ban":
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned = 1 - is_banned WHERE user_id=?", (target,))
        conn.commit()
        c.execute("SELECT is_banned FROM users WHERE user_id=?", (target,))
        status = c.fetchone()[0]
        conn.close()
        bot.answer_callback_query(call.id, "بن شد" if status else "آنبن شد", show_alert=True)
    elif action == "give" and "xp" in call.data:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET xp = xp + 100, level = level + 1 WHERE user_id=?", (target,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "+1 Level و +100 XP داده شد", show_alert=True)

    bot.answer_callback_query(call.id)

# هندلر مقدار scrap
@bot.message_handler(func=lambda m: user_steps.get(m.from_user.id, {}).get("step") == "adm_set_scrap")
def set_scrap(message):
    uid = message.from_user.id
    if not is_admin(uid):
        return
    data = user_steps[uid]
    try:
        amount = int(message.text.strip())
        target = data["target"]
        if data["mode"] == "add":
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE users SET scrap = scrap + ? WHERE user_id=?", (amount, target))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ {amount:,} Scrap اضافه شد.")
            try:
                bot.send_message(target, f"💰 ادمین {amount:,} Scrap به حسابت اضافه کرد.")
            except:
                pass
        else:
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE users SET scrap = MAX(0, scrap - ?) WHERE user_id=?", (amount, target))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ {amount:,} Scrap کم شد.")
    except:
        bot.reply_to(message, "عدد معتبر بفرست.")
    user_steps[uid] = {}

# ---------- اجرا ----------
print("🧟 ZOMBIE SURVIVAL روشن شد")
print("=" * 40)
print("توکن تنظیم شد")
print("ادمین:", ADMIN_IDS)
print("همه سیستم‌ها Dynamic هستند")
print("پنل ادمین فقط در پیوی و فقط برای ادمین اصلی")
print("=" * 40)

bot.infinity_polling()
