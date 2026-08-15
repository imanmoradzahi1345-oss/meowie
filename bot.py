import sqlite3
import json
import os
import random
from datetime import datetime
import telebot
from telebot import types

# ==========================================
# ⚙️ تنظیمات اصلی و کلیدهای ارتباطی
# ==========================================
BOT_TOKEN = "8875102057:AAE5JvIk9HhGoeizZhYUjyRvSdCRIsEzoxU"
ADMIN_ID = 7530457395
DB_NAME = "zombie_survival.db"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ==========================================
# 🗄️ راه‌اندازی و ساختار کامل دیتابیس (DB ENGINE)
# ==========================================
def get_db():
    """ارتباط امن با پایگاه داده SQLite"""
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """ایجاد کلیه جداول لازم برای بازی ZOMBIE SURVIVAL"""
    conn = get_db()
    cursor = conn.cursor()

    # 1. جدول کاربران
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        level INTEGER DEFAULT 1,
        xp INTEGER DEFAULT 0,
        hp INTEGER DEFAULT 100,
        max_hp INTEGER DEFAULT 100,
        hunger INTEGER DEFAULT 100,
        thirst INTEGER DEFAULT 100,
        energy INTEGER DEFAULT 100,
        sanity INTEGER DEFAULT 100,
        infection INTEGER DEFAULT 0,
        scrap INTEGER DEFAULT 100,
        zombie_kills INTEGER DEFAULT 0,
        deaths INTEGER DEFAULT 0,
        current_region_id INTEGER DEFAULT NULL,
        current_weapon_id INTEGER DEFAULT NULL,
        current_shelter_id INTEGER DEFAULT NULL,
        clan_id INTEGER DEFAULT NULL,
        role TEXT DEFAULT 'player',
        is_banned INTEGER DEFAULT 0,
        created_at TEXT
    )
    ''')

    # 2. نقشه‌ها (Maps)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS maps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        image_id TEXT,
        is_active INTEGER DEFAULT 1
    )
    ''')

    # 3. مناطق (Regions - چندلایه و تو در تو)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS regions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        map_id INTEGER NOT NULL,
        parent_region_id INTEGER DEFAULT NULL,
        name TEXT NOT NULL,
        description TEXT,
        image_id TEXT,
        region_type TEXT DEFAULT 'normal',
        danger_level INTEGER DEFAULT 1,
        min_level INTEGER DEFAULT 1,
        is_secret INTEGER DEFAULT 0,
        is_locked INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        zombie_chance INTEGER DEFAULT 40,
        loot_chance INTEGER DEFAULT 30,
        rare_loot_chance INTEGER DEFAULT 10,
        survivor_chance INTEGER DEFAULT 5,
        event_chance INTEGER DEFAULT 5,
        FOREIGN KEY (map_id) REFERENCES maps(id) ON DELETE CASCADE,
        FOREIGN KEY (parent_region_id) REFERENCES regions(id) ON DELETE SET NULL
    )
    ''')

    # 4. سلاح‌ها (Weapons)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS weapons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        image_id TEXT,
        price INTEGER DEFAULT 0,
        damage INTEGER DEFAULT 10,
        ammo_capacity INTEGER DEFAULT 10,
        rarity TEXT DEFAULT 'Common',
        req_level INTEGER DEFAULT 1,
        weapon_type TEXT DEFAULT 'Melee',
        is_active INTEGER DEFAULT 1
    )
    ''')

    # 5. پناهگاه‌ها (Shelters)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS shelters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        image_id TEXT,
        price INTEGER DEFAULT 0,
        defense INTEGER DEFAULT 10,
        capacity INTEGER DEFAULT 50,
        req_level INTEGER DEFAULT 1,
        rarity TEXT DEFAULT 'Common',
        is_active INTEGER DEFAULT 1
    )
    ''')

    # 6. آیتم‌ها (Items)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        image_id TEXT,
        item_type TEXT DEFAULT 'misc',
        price INTEGER DEFAULT 0,
        rarity TEXT DEFAULT 'Common',
        max_stack INTEGER DEFAULT 99,
        heal_hp INTEGER DEFAULT 0,
        heal_hunger INTEGER DEFAULT 0,
        heal_thirst INTEGER DEFAULT 0,
        heal_sanity INTEGER DEFAULT 0,
        reduce_infection INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1
    )
    ''')

    # 7. کوله‌پشتی کاربران (User Inventory)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        item_id INTEGER NOT NULL,
        quantity INTEGER DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
    )
    ''')

    # 8. سلاح‌های خریداری شده کاربر (User Weapons)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_weapons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        weapon_id INTEGER NOT NULL,
        ammo_left INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (weapon_id) REFERENCES weapons(id) ON DELETE CASCADE
    )
    ''')

    # 9. زامبی‌ها (Zombies)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS zombies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        image_id TEXT,
        hp INTEGER DEFAULT 50,
        damage INTEGER DEFAULT 10,
        defense INTEGER DEFAULT 2,
        speed INTEGER DEFAULT 5,
        xp_reward INTEGER DEFAULT 20,
        scrap_reward INTEGER DEFAULT 15,
        infection_chance INTEGER DEFAULT 10,
        rarity TEXT DEFAULT 'Common',
        is_active INTEGER DEFAULT 1
    )
    ''')

    # 10. سیستم نبرد زنده (Active Combat State)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS active_combat (
        user_id INTEGER PRIMARY KEY,
        zombie_id INTEGER NOT NULL,
        zombie_current_hp INTEGER NOT NULL,
        player_turn INTEGER DEFAULT 1,
        is_resolved INTEGER DEFAULT 0,
        created_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (zombie_id) REFERENCES zombies(id) ON DELETE CASCADE
    )
    ''')

    # 11. مأموریت‌ها (Quests)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS quests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        image_id TEXT,
        target_type TEXT NOT NULL,
        target_id INTEGER DEFAULT 0,
        target_count INTEGER DEFAULT 1,
        region_id INTEGER DEFAULT NULL,
        xp_reward INTEGER DEFAULT 50,
        scrap_reward INTEGER DEFAULT 50,
        item_reward_id INTEGER DEFAULT NULL,
        is_active INTEGER DEFAULT 1
    )
    ''')

    # 12. وضعیت مأموریت‌های کاربر (User Quests)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_quests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        quest_id INTEGER NOT NULL,
        current_count INTEGER DEFAULT 0,
        is_completed INTEGER DEFAULT 0,
        is_reward_claimed INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (quest_id) REFERENCES quests(id) ON DELETE CASCADE
    )
    ''')

    # 13. کلن‌ها (Clans)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS clans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        image_id TEXT,
        owner_id INTEGER NOT NULL,
        level INTEGER DEFAULT 1,
        xp INTEGER DEFAULT 0,
        created_at TEXT
    )
    ''')

    # 14. اعضای کلن (Clan Members)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS clan_members (
        user_id INTEGER PRIMARY KEY,
        clan_id INTEGER NOT NULL,
        role TEXT DEFAULT 'member',
        joined_at TEXT,
        FOREIGN KEY (clan_id) REFERENCES clans(id) ON DELETE CASCADE
    )
    ''')

    # 15. رویدادها (Events)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        image_id TEXT,
        region_id INTEGER DEFAULT NULL,
        zombie_mult REAL DEFAULT 1.0,
        loot_mult REAL DEFAULT 1.0,
        xp_mult REAL DEFAULT 1.0,
        is_active INTEGER DEFAULT 0
    )
    ''')

    # 16. غول‌های جهانی (World Bosses)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS world_bosses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        image_id TEXT,
        max_hp INTEGER DEFAULT 10000,
        current_hp INTEGER DEFAULT 10000,
        damage INTEGER DEFAULT 50,
        scrap_reward_pool INTEGER DEFAULT 10000,
        is_active INTEGER DEFAULT 0,
        is_defeated INTEGER DEFAULT 0
    )
    ''')

    # 17. مشارکت در مبارزه با غول جهانی (Boss Contributions)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS boss_contributions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        boss_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        damage_dealt INTEGER DEFAULT 0,
        reward_claimed INTEGER DEFAULT 0,
        FOREIGN KEY (boss_id) REFERENCES world_bosses(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )
    ''')

    # 18. صفحات راهنمای بازی (Dynamic Help Pages)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS help_pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key_name TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        image_id TEXT,
        display_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1
    )
    ''')

    # 19. ثبت لاگ‌های امنیتی سیستم (System Logs)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS system_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT NOT NULL,
        details TEXT,
        timestamp TEXT
    )
    ''')

    # 20. مدیریت وضعیت فرم‌های مدیریتی (User States)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_states (
        user_id INTEGER PRIMARY KEY,
        state TEXT,
        data TEXT
    )
    ''')

    conn.commit()
    conn.close()

# اجرای راه‌اندازی دیتابیس در زمان فراخوانی اولیه
init_db()

# ==========================================
# 🔄 توابع پایه و سرویس‌های کاربردی (CORE SERVICES)
# ==========================================

def log_system_action(user_id: int, action: str, details: str = ""):
    """ثبت لاگ‌های امنیتی و مدیریتی"""
    conn = get_db()
    conn.execute(
        "INSERT INTO system_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
        (user_id, action, details, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

def set_user_state(user_id: int, state: str, data: dict = None):
    """ذخیره استیت فعلی کاربر برای فرم‌های چند مرحله‌ای Admin"""
    conn = get_db()
    data_str = json.dumps(data or {})
    conn.execute(
        "INSERT OR REPLACE INTO user_states (user_id, state, data) VALUES (?, ?, ?)",
        (user_id, state, data_str)
    )
    conn.commit()
    conn.close()

def get_user_state(user_id: int):
    """دریافت استیت فعال کاربر"""
    conn = get_db()
    row = conn.execute("SELECT state, data FROM user_states WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        return row["state"], json.loads(row["data"] or "{}")
    return None, {}

def clear_user_state(user_id: int):
    """پاکسازی استیت کاربر"""
    conn = get_db()
    conn.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    # ==========================================
# 👤 مدیریت کاربر و سیستم ارتقاء سطح (USER ENGINE)
# ==========================================

def get_or_create_user(user_id: int, username: str, first_name: str):
    """ثبت‌نام خودکار کاربر جدید یا دریافت اطلاعات ثبت‌شده"""
    conn = get_db()
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()

    role = 'admin' if str(user_id) == str(ADMIN_ID) else 'player'

    if not user:
        cursor.execute('''
        INSERT INTO users (user_id, username, first_name, role, created_at)
        VALUES (?, ?, ?, ?, DATETIME('now'))
        ''', (user_id, username or "Survivor", first_name or "بازیکن", role))
        conn.commit()
        log_system_action(user_id, "REGISTER", "ورود بازیکن جدید به دنیای ZOMBIE SURVIVAL")
        user = cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()

    conn.close()
    return user

def add_xp_and_scrap(user_id: int, xp_gain: int, scrap_gain: int):
    """افزایش XP و Scrap همراه با سیستم سطح‌بندی (Level-Up) خودکار"""
    conn = get_db()
    cursor = conn.cursor()
    user = cursor.execute("SELECT level, xp, scrap, max_hp, hp FROM users WHERE user_id = ?", (user_id,)).fetchone()

    if not user:
        conn.close()
        return False, 0

    new_xp = user['xp'] + xp_gain
    new_scrap = user['scrap'] + scrap_gain
    current_level = user['level']
    max_hp = user['max_hp']
    current_hp = user['hp']

    required_xp = current_level * 100
    leveled_up = False

    while new_xp >= required_xp:
        new_xp -= required_xp
        current_level += 1
        max_hp += 20
        current_hp = max_hp  # بازیابی کامل سلامتی هنگام افزایش سطح
        required_xp = current_level * 100
        leveled_up = True

    cursor.execute('''
    UPDATE users 
    SET level = ?, xp = ?, scrap = ?, max_hp = ?, hp = ?
    WHERE user_id = ?
    ''', (current_level, new_xp, new_scrap, max_hp, current_hp, user_id))

    conn.commit()
    conn.close()
    return leveled_up, current_level

# ==========================================
# 🗺️ سیستم موقعیت‌نمایی تو در تو (LOCATION ENGINE)
# ==========================================

def get_full_location_path(region_id: int):
    """محاسبه کامل مسیر چندلایه موقعیت (کشور ↓ شهر ↓ منطقه ↓ ساختمان)"""
    if not region_id:
        return "🌐 بیابان‌های آخرالزمانی"

    conn = get_db()
    cursor = conn.cursor()
    
    path = []
    curr_id = region_id

    while curr_id:
        region = cursor.execute("SELECT id, parent_region_id, name, map_id FROM regions WHERE id = ?", (curr_id,)).fetchone()
        if not region:
            break
        path.append(region['name'])
        curr_id = region['parent_region_id']
        
        if not curr_id and region['map_id']:
            map_data = cursor.execute("SELECT name FROM maps WHERE id = ?", (region['map_id'],)).fetchone()
            if map_data:
                path.append(f"🏙️ {map_data['name']}")

    conn.close()
    path.reverse()
    return " ↓ ".join(path)

def update_user_location(user_id: int, region_id: int):
    """تغییر موقعیت ثبت‌شده بازیکن"""
    conn = get_db()
    conn.execute("UPDATE users SET current_region_id = ? WHERE user_id = ?", (region_id, user_id))
    conn.commit()
    conn.close()

# ==========================================
# 🎒 سیستم مدیریت کوله‌پشتی (INVENTORY ENGINE)
# ==========================================

def add_item_to_inventory(user_id: int, item_id: int, quantity: int = 1):
    """افزودن آیتم با پشتیبانی کامل از سیستم Stack"""
    conn = get_db()
    cursor = conn.cursor()

    existing = cursor.execute(
        "SELECT id, quantity FROM user_inventory WHERE user_id = ? AND item_id = ?", 
        (user_id, item_id)
    ).fetchone()

    if existing:
        new_qty = existing['quantity'] + quantity
        cursor.execute("UPDATE user_inventory SET quantity = ? WHERE id = ?", (new_qty, existing['id']))
    else:
        cursor.execute(
            "INSERT INTO user_inventory (user_id, item_id, quantity) VALUES (?, ?, ?)", 
            (user_id, item_id, quantity)
        )

    conn.commit()
    conn.close()
    return True

def remove_item_from_inventory(user_id: int, item_id: int, quantity: int = 1):
    """کاهش یا حذف ایمن آیتم از اینونتوری بدون منفی شدن"""
    conn = get_db()
    cursor = conn.cursor()

    existing = cursor.execute(
        "SELECT id, quantity FROM user_inventory WHERE user_id = ? AND item_id = ?", 
        (user_id, item_id)
    ).fetchone()

    if not existing or existing['quantity'] < quantity:
        conn.close()
        return False

    if existing['quantity'] == quantity:
        cursor.execute("DELETE FROM user_inventory WHERE id = ?", (existing['id'],))
    else:
        cursor.execute(
            "UPDATE user_inventory SET quantity = quantity - ? WHERE id = ?", 
            (quantity, existing['id'])
        )

    conn.commit()
    conn.close()
    return True

# ==========================================
# ⌨️ کیبوردهای منوی اصلی (MAIN UI KEYBOARDS)
# ==========================================

def get_main_keyboard(user_id: int):
    """کیبورد اصلی بازی با کنترل سطح دسترسی ادمین"""
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    btn_profile = types.KeyboardButton("👤 پروفایل")
    btn_map = types.KeyboardButton("🗺️ نقشه")
    btn_weapons = types.KeyboardButton("🔫 سلاح‌ها")
    btn_shelter = types.KeyboardButton("🏠 پناهگاه")
    btn_inventory = types.KeyboardButton("🎒 کوله‌پشتی")
    btn_survival = types.KeyboardButton("🧟 بقا / جستجو")
    btn_quests = types.KeyboardButton("📜 مأموریت‌ها")
    btn_clan = types.KeyboardButton("👥 کلن")
    btn_ranking = types.KeyboardButton("🏆 رتبه‌بندی")
    btn_help = types.KeyboardButton("📖 راهنما")

    kb.add(btn_profile, btn_map)
    kb.add(btn_weapons, btn_shelter)
    kb.add(btn_inventory, btn_survival)
    kb.add(btn_quests, btn_clan)
    kb.add(btn_ranking, btn_help)

    if str(user_id) == str(ADMIN_ID):
        btn_admin = types.KeyboardButton("⚙️ پنل مدیریت")
        kb.add(btn_admin)

    return kb

# ==========================================
# 🎯 هندلرهای شروع (/start & Profile)
# ==========================================

@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    user = get_or_create_user(user_id, username, first_name)

    if user['is_banned']:
        bot.send_message(message.chat.id, "🚫 حساب شما در بازی مسدود شده است.")
        return

    welcome_text = (
        f"🧟 <b>به دنیای ZOMBIE SURVIVAL خوش آمدید، {first_name}!</b>\n\n"
        f"دنیای ویران‌شده‌ای که تنها هدف شما در آن <b>زنده ماندن</b> است.\n"
        f"منابع جمع‌آوری کنید، با زامبی‌ها مبارزه کنید، پناهگاه بسازید و منطقه را تسخیر کنید.\n\n"
        f"دستورات سریع:\n"
        f"👤 /profile - مشاهده وضعیت\n"
        f"🗺️ /map - نقشه دنیای بازی\n"
        f"🎒 /inventory - کوله‌پشتی\n"
        f"📖 /help - راهنمای جامع"
    )

    bot.send_message(
        message.chat.id, 
        welcome_text, 
        reply_markup=get_main_keyboard(user_id)
    )

@bot.message_handler(commands=['profile'])
@bot.message_handler(func=lambda msg: msg.text == "👤 پروفایل")
def show_profile(message):
    user_id = message.from_user.id
    user = get_or_create_user(user_id, message.from_user.username, message.from_user.first_name)

    if user['is_banned']:
        return

    conn = get_db()
    weapon_name = "مشت خالی"
    if user['current_weapon_id']:
        w = conn.execute("SELECT name FROM weapons WHERE id = ?", (user['current_weapon_id'],)).fetchone()
        if w: weapon_name = w['name']

    shelter_name = "بدون پناهگاه"
    if user['current_shelter_id']:
        s = conn.execute("SELECT name FROM shelters WHERE id = ?", (user['current_shelter_id'],)).fetchone()
        if s: shelter_name = s['name']

    conn.close()

    location_path = get_full_location_path(user['current_region_id'])

    profile_text = (
        f"👤 <b>پروفایل بازمانده: {user['first_name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏅 <b>سطح (Level):</b> {user['level']} | <b>XP:</b> {user['xp']}/{user['level'] * 100}\n"
        f"❤️ <b>سلامت (HP):</b> {user['hp']}/{user['max_hp']}\n"
        f"🍖 <b>گرسنگی:</b> {user['hunger']}/100 | 💧 <b>تشنگی:</b> {user['thirst']}/100\n"
        f"⚡ <b>انرژی:</b> {user['energy']}/100 | 🧠 <b>روان (Sanity):</b> {user['sanity']}/100\n"
        f"☣️ <b>میزان عفونت:</b> {user['infection']}%\n"
        f"💰 <b>قطعات (Scrap):</b> {user['scrap']} 🪙\n"
        f"🧟 <b>زامبی‌های کشته‌شده:</b> {user['zombie_kills']} | ☠️ <b>دفعات مرگ:</b> {user['deaths']}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔫 <b>سلاح فعلی:</b> {weapon_name}\n"
        f"🏠 <b>پناهگاه فعلی:</b> {shelter_name}\n"
        f"📍 <b>موقعیت فعلی:</b>\n{location_path}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    bot.send_message(message.chat.id, profile_text, reply_markup=get_main_keyboard(user_id))
    # ==========================================
# 🗺️ سیستم نقشه و مناطق تو در تو (MAP & REGION HANDLERS)
# ==========================================

@bot.message_handler(commands=['map'])
@bot.message_handler(func=lambda msg: msg.text == "🗺️ نقشه")
def show_maps_menu(message):
    user_id = message.from_user.id
    user = get_or_create_user(user_id, message.from_user.username, message.from_user.first_name)

    if user['is_banned']:
        return

    conn = get_db()
    active_maps = conn.execute("SELECT * FROM maps WHERE is_active = 1").fetchall()
    conn.close()

    if not active_maps:
        bot.send_message(
            message.chat.id, 
            "🗺️ <b>هیچ نقشه‌ای در حال حاضر توسط مدیریت ایجاد نشده است.</b>"
        )
        return

    kb = types.InlineKeyboardMarkup(row_width=1)
    for m in active_maps:
        kb.add(types.InlineKeyboardButton(f"🗺️ {m['name']}", callback_data=f"map_view_{m['id']}"))

    current_loc = get_full_location_path(user['current_region_id'])

    text = (
        f"🗺️ <b>نقشه‌های فعال جهان ZOMBIE SURVIVAL</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📍 <b>موقعیت فعلی شما:</b>\n{current_loc}\n\n"
        f"یک نقشه را برای مشاهده و کاوش انتخاب کنید:"
    )

    bot.send_message(message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("map_view_"))
def callback_map_view(call):
    map_id = int(call.data.split("_")[2])
    user_id = call.from_user.id

    conn = get_db()
    map_data = conn.execute("SELECT * FROM maps WHERE id = ?", (map_id,)).fetchone()
    # دریافت مناطق سطح اول (بدون منطقه والد)
    top_regions = conn.execute(
        "SELECT * FROM regions WHERE map_id = ? AND parent_region_id IS NULL AND is_active = 1", 
        (map_id,)
    ).fetchall()
    conn.close()

    if not map_data:
        bot.answer_callback_query(call.id, "نقشه یافت نشد.")
        return

    kb = types.InlineKeyboardMarkup(row_width=1)
    for r in top_regions:
        kb.add(types.InlineKeyboardButton(f"📍 {r['name']} (سطح {r['min_level']}+)", callback_data=f"reg_view_{r['id']}"))
    
    kb.add(types.InlineKeyboardButton("⬅️ بازگشت به لیست نقشه‌ها", callback_data="map_list_back"))

    caption = (
        f"🗺️ <b>نقشه: {map_data['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📝 {map_data['description'] or 'بدون توضیح'}\n\n"
        f"👇 <b>مناطق اصلی این نقشه:</b>"
    )

    if map_data['image_id']:
        try:
            bot.send_photo(call.message.chat.id, map_data['image_id'], caption=caption, reply_markup=kb)
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            bot.send_message(call.message.chat.id, caption, reply_markup=kb)
    else:
        bot.send_message(call.message.chat.id, caption, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "map_list_back")
def callback_map_list_back(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    show_maps_menu(call.message)

@bot.callback_query_handler(func=lambda call: call.data.startswith("reg_view_"))
def callback_region_view(call):
    region_id = int(call.data.split("_")[2])
    user_id = call.from_user.id
    user = get_or_create_user(user_id, call.from_user.username, call.from_user.first_name)

    conn = get_db()
    region = conn.execute("SELECT * FROM regions WHERE id = ?", (region_id,)).fetchone()
    sub_regions = conn.execute(
        "SELECT * FROM regions WHERE parent_region_id = ? AND is_active = 1", 
        (region_id,)
    ).fetchall()
    conn.close()

    if not region:
        bot.answer_callback_query(call.id, "منطقه یافت نشد.")
        return

    kb = types.InlineKeyboardMarkup(row_width=1)

    # دکمه ورود به منطقه
    kb.add(types.InlineKeyboardButton("🚶 ورود به این منطقه", callback_data=f"reg_enter_{region['id']}"))

    # زیرمجموعه‌ها (مناطق داخل این منطقه)
    for sub in sub_regions:
        kb.add(types.InlineKeyboardButton(f"↳ 🏢 {sub['name']} (سطح {sub['min_level']}+)", callback_data=f"reg_view_{sub['id']}"))

    if region['parent_region_id']:
        kb.add(types.InlineKeyboardButton("⬅️ بازگشت به منطقه والد", callback_data=f"reg_view_{region['parent_region_id']}"))
    else:
        kb.add(types.InlineKeyboardButton("⬅️ بازگشت به نقشه", callback_data=f"map_view_{region['map_id']}"))

    danger_stars = "⚠️" * region['danger_level']
    is_here = "✅ شما هم‌اکنون اینجا هستید" if user['current_region_id'] == region['id'] else "❌ در این منطقه نیستید"

    text = (
        f"📍 <b>منطقه: {region['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📝 {region['description'] or 'بدون توضیح'}\n"
        f"⚠️ <b>سطح خطر:</b> {danger_stars} ({region['danger_level']}/5)\n"
        f"🔓 <b>سطح مورد نیاز:</b> {region['min_level']}\n"
        f"📍 <b>وضعیت حضوری:</b> {is_here}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    if region['image_id']:
        try:
            bot.send_photo(call.message.chat.id, region['image_id'], caption=text, reply_markup=kb)
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
    else:
        bot.send_message(call.message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("reg_enter_"))
def callback_region_enter(call):
    region_id = int(call.data.split("_")[2])
    user_id = call.from_user.id
    user = get_or_create_user(user_id, call.from_user.username, call.from_user.first_name)

    conn = get_db()
    region = conn.execute("SELECT * FROM regions WHERE id = ?", (region_id,)).fetchone()
    conn.close()

    if not region:
        bot.answer_callback_query(call.id, "منطقه موجود نیست.")
        return

    if user['level'] < region['min_level']:
        bot.answer_callback_query(
            call.id, 
            f"⛔ سطح شما ({user['level']}) برای ورود به این منطقه کافی نیست! (سطح لازم: {region['min_level']})",
            show_alert=True
        )
        return

    if region['is_locked']:
        bot.answer_callback_query(call.id, "🔒 این منطقه قفل است و امکان ورود وجود ندارد.", show_alert=True)
        return

    update_user_location(user_id, region_id)
    loc_path = get_full_location_path(region_id)

    bot.answer_callback_query(call.id, f"✅ شما وارد {region['name']} شدید!")
    bot.send_message(
        call.message.chat.id, 
        f"🚶 <b>موقعیت شما تغییر کرد:</b>\n{loc_path}"
    )

# ==========================================
# 🔫 فروشگاه پویای سلاح‌ها (WEAPONS SYSTEM)
# ==========================================

@bot.message_handler(commands=['weapons'])
@bot.message_handler(func=lambda msg: msg.text == "🔫 سلاح‌ها")
def show_weapons_shop(message):
    user_id = message.from_user.id
    user = get_or_create_user(user_id, message.from_user.username, message.from_user.first_name)

    if user['is_banned']:
        return

    conn = get_db()
    weapons = conn.execute("SELECT * FROM weapons WHERE is_active = 1").fetchall()
    conn.close()

    if not weapons:
        bot.send_message(message.chat.id, "🔫 <b>هیچ سلاحی در فروشگاه موجود نیست.</b>")
        return

    kb = types.InlineKeyboardMarkup(row_width=1)
    for w in weapons:
        kb.add(types.InlineKeyboardButton(
            f"🔫 {w['name']} | 💰 {w['price']} Scrap | ⭐ {w['rarity']}", 
            callback_data=f"wpn_view_{w['id']}"
        ))

    text = (
        f"🔫 <b>فروشگاه سلاح‌های آخرالزمانی</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>موجودی Scrap شما:</b> {user['scrap']} 🪙\n"
        f"جهت مشاهده جزئیات و خرید، سلاح مورد نظر را انتخاب کنید:"
    )

    bot.send_message(message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("wpn_view_"))
def callback_weapon_view(call):
    weapon_id = int(call.data.split("_")[2])
    user_id = call.from_user.id
    user = get_or_create_user(user_id, call.from_user.username, call.from_user.first_name)

    conn = get_db()
    w = conn.execute("SELECT * FROM weapons WHERE id = ?", (weapon_id,)).fetchone()
    already_owned = conn.execute(
        "SELECT id FROM user_weapons WHERE user_id = ? AND weapon_id = ?", 
        (user_id, weapon_id)
    ).fetchone()
    conn.close()

    if not w:
        bot.answer_callback_query(call.id, "سلاح یافت نشد.")
        return

    kb = types.InlineKeyboardMarkup(row_width=1)
    if already_owned:
        kb.add(types.InlineKeyboardButton("✅ این سلاح را دارید (تجهیز)", callback_data=f"wpn_equip_{w['id']}"))
    else:
        kb.add(types.InlineKeyboardButton(f"💰 خرید سلاح ({w['price']} Scrap)", callback_data=f"wpn_buy_{w['id']}"))

    kb.add(types.InlineKeyboardButton("⬅️ بازگشت به فروشگاه", callback_data="wpn_shop_back"))

    text = (
        f"🔫 <b>سلاح: {w['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚔️ <b>قدرت (Damage):</b> {w['damage']}\n"
        f"🔫 <b>ظرفیت خشاب:</b> {w['ammo_capacity']}\n"
        f"⭐ <b>کمیابی:</b> {w['rarity']}\n"
        f"🔓 <b>سطح مورد نیاز:</b> {w['req_level']}\n"
        f"💰 <b>قیمت:</b> {w['price']} Scrap\n"
        f"📝 <b>توضیحات:</b> {w['description'] or 'بدون توضیح'}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    if w['image_id']:
        try:
            bot.send_photo(call.message.chat.id, w['image_id'], caption=text, reply_markup=kb)
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
    else:
        bot.send_message(call.message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "wpn_shop_back")
def callback_wpn_shop_back(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    show_weapons_shop(call.message)

@bot.callback_query_handler(func=lambda call: call.data.startswith("wpn_buy_"))
def callback_weapon_buy(call):
    weapon_id = int(call.data.split("_")[2])
    user_id = call.from_user.id
    user = get_or_create_user(user_id, call.from_user.username, call.from_user.first_name)

    conn = get_db()
    cursor = conn.cursor()
    w = cursor.execute("SELECT * FROM weapons WHERE id = ?", (weapon_id,)).fetchone()

    if not w:
        conn.close()
        bot.answer_callback_query(call.id, "سلاح وجود ندارد.")
        return

    if user['level'] < w['req_level']:
        conn.close()
        bot.answer_callback_query(call.id, f"⛔ سطح شما برای خرید این سلاح کافی نیست! (سطح لازم: {w['req_level']})", show_alert=True)
        return

    if user['scrap'] < w['price']:
        conn.close()
        bot.answer_callback_query(call.id, f"❌ Scrap کافی ندارید! (موجود: {user['scrap']} / لازم: {w['price']})", show_alert=True)
        return

    # کسر وجه، اضافه کردن به تجهیزات و فعال‌سازی سلاح
    new_scrap = user['scrap'] - w['price']
    cursor.execute("UPDATE users SET scrap = ?, current_weapon_id = ? WHERE user_id = ?", (new_scrap, weapon_id, user_id))
    cursor.execute("INSERT INTO user_weapons (user_id, weapon_id, ammo_left) VALUES (?, ?, ?)", (user_id, weapon_id, w['ammo_capacity']))

    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, f"🎉 سلاح {w['name']} با موفقیت خریداری و مجهز شد!", show_alert=True)
    show_weapons_shop(call.message)

@bot.callback_query_handler(func=lambda call: call.data.startswith("wpn_equip_"))
def callback_weapon_equip(call):
    weapon_id = int(call.data.split("_")[2])
    user_id = call.from_user.id

    conn = get_db()
    conn.execute("UPDATE users SET current_weapon_id = ? WHERE user_id = ?", (weapon_id, user_id))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, "✅ سلاح مجهز شد!", show_alert=True)

# ==========================================
# 🏠 سیستم پناهگاه‌ها (SHELTER SYSTEM)
# ==========================================

@bot.message_handler(commands=['shelter'])
@bot.message_handler(func=lambda msg: msg.text == "🏠 پناهگاه")
def show_shelters_shop(message):
    user_id = message.from_user.id
    user = get_or_create_user(user_id, message.from_user.username, message.from_user.first_name)

    if user['is_banned']:
        return

    conn = get_db()
    shelters = conn.execute("SELECT * FROM shelters WHERE is_active = 1").fetchall()
    conn.close()

    if not shelters:
        bot.send_message(message.chat.id, "🏠 <b>هیچ پناهگاهی برای خرید وجود ندارد.</b>")
        return

    kb = types.InlineKeyboardMarkup(row_width=1)
    for s in shelters:
        kb.add(types.InlineKeyboardButton(
            f"🏠 {s['name']} | 🛡️ دفاع: {s['defense']} | 💰 {s['price']} Scrap", 
            callback_data=f"shl_view_{s['id']}"
        ))

    text = (
        f"🏠 <b>لیست پناهگاه‌های قابل ساخت و خرید</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>موجودی شما:</b> {user['scrap']} Scrap\n"
        f"پناهگاه‌ها امنیت شما را در برابر حملات زامبی‌ها افزایش می‌دهند:"
    )

    bot.send_message(message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("shl_view_"))
def callback_shelter_view(call):
    shelter_id = int(call.data.split("_")[2])
    user_id = call.from_user.id
    user = get_or_create_user(user_id, call.from_user.username, call.from_user.first_name)

    conn = get_db()
    s = conn.execute("SELECT * FROM shelters WHERE id = ?", (shelter_id,)).fetchone()
    conn.close()

    if not s:
        bot.answer_callback_query(call.id, "پناهگاه یافت نشد.")
        return

    kb = types.InlineKeyboardMarkup(row_width=1)
    if user['current_shelter_id'] == s['id']:
        kb.add(types.InlineKeyboardButton("✅ پناهگاه فعلی شما", callback_data="none"))
    else:
        kb.add(types.InlineKeyboardButton(f"🏠 خرید پناهگاه ({s['price']} Scrap)", callback_data=f"shl_buy_{s['id']}"))

    kb.add(types.InlineKeyboardButton("⬅️ بازگشت", callback_data="shl_shop_back"))

    text = (
        f"🏠 <b>پناهگاه: {s['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ <b>قدرت دفاعی:</b> {s['defense']}\n"
        f"📦 <b>ظرفیت انبار:</b> {s['capacity']}\n"
        f"⭐ <b>کمیابی:</b> {s['rarity']}\n"
        f"🔓 <b>سطح مورد نیاز:</b> {s['req_level']}\n"
        f"💰 <b>قیمت:</b> {s['price']} Scrap\n"
        f"📝 <b>توضیحات:</b> {s['description'] or 'بدون توضیح'}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    if s['image_id']:
        try:
            bot.send_photo(call.message.chat.id, s['image_id'], caption=text, reply_markup=kb)
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
    else:
        bot.send_message(call.message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "shl_shop_back")
def callback_shelter_shop_back(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    show_shelters_shop(call.message)

@bot.callback_query_handler(func=lambda call: call.data.startswith("shl_buy_"))
def callback_shelter_buy(call):
    shelter_id = int(call.data.split("_")[2])
    user_id = call.from_user.id
    user = get_or_create_user(user_id, call.from_user.username, call.from_user.first_name)

    conn = get_db()
    cursor = conn.cursor()
    s = cursor.execute("SELECT * FROM shelters WHERE id = ?", (shelter_id,)).fetchone()

    if not s:
        conn.close()
        bot.answer_callback_query(call.id, "پناهگاه یافت نشد.")
        return

    if user['level'] < s['req_level']:
        conn.close()
        bot.answer_callback_query(call.id, f"⛔ سطح شما کافی نیست! (سطح لازم: {s['req_level']})", show_alert=True)
        return

    if user['scrap'] < s['price']:
        conn.close()
        bot.answer_callback_query(call.id, f"❌ Scrap کافی ندارید! (موجود: {user['scrap']} / لازم: {s['price']})", show_alert=True)
        return

    new_scrap = user['scrap'] - s['price']
    cursor.execute("UPDATE users SET scrap = ?, current_shelter_id = ? WHERE user_id = ?", (new_scrap, shelter_id, user_id))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, f"🎉 پناهگاه {s['name']} با موفقیت خریداری شد!", show_alert=True)
    show_shelters_shop(call.message)
    # ==========================================
# 🔍 موتور کاوش، مبارزه نوبتی و سیستم عفونت (EXPLORATION & COMBAT)
# ==========================================

import random

@bot.message_handler(commands=['explore'])
@bot.message_handler(func=lambda msg: msg.text == "🔍 کاوش")
def handle_explore(message):
    user_id = message.from_user.id
    user = get_or_create_user(user_id, message.from_user.username, message.from_user.first_name)

    if user['is_banned']:
        return

    if user['hp'] <= 0:
        bot.send_message(message.chat.id, "💀 <b>شما مرده‌اید!</b> ابتدا باید با استفاده از آیتم یا پناهگاه سلامتی خود را بازیابید.")
        return

    # بررسی منطقه فعلی
    conn = get_db()
    region = conn.execute("SELECT * FROM regions WHERE id = ?", (user['current_region_id'],)).fetchone()
    
    # دریافت زامبی‌های مربوط به این سطح یا منطقه
    zombies = conn.execute("SELECT * FROM zombies WHERE req_level <= ?", (user['level'],)).fetchall()
    conn.close()

    if not region:
        bot.send_message(message.chat.id, "❌ موقعیت مکانی شما نامشخص است. لطفاً ابتدا از بخش 🗺️ نقشه یک منطقه را انتخاب کنید.")
        return

    # شانس رویدادها (بر اساس سطح خطر منطقه)
    danger = region['danger_level']
    event_roll = random.randint(1, 100)

    # 1. مواجهه با زامبی (احتمال بالا در مناطق خطرناک)
    zombie_chance = 40 + (danger * 8)
    if event_roll <= zombie_chance and zombies:
        zombie = random.choice(zombies)
        start_combat(message, user, zombie, region)
        return

    # 2. پیدا کردن لوت / Scrap
    elif event_roll <= zombie_chance + 25:
        found_scrap = random.randint(10, 30) * danger
        found_xp = random.randint(5, 15) * danger
        
        conn = get_db()
        conn.execute("UPDATE users SET scrap = scrap + ?, xp = xp + ? WHERE user_id = ?", (found_scrap, found_xp, user_id))
        conn.commit()
        conn.close()

        bot.send_message(
            message.chat.id,
            f"🔍 <b>کاوش در {region['name']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎉 شما منطقه را جستجو کردید و موفق به پیدا کردن منابع شدید!\n\n"
            f"💰 <b>Scrap دریافتی:</b> +{found_scrap}\n"
            f"⭐ <b>تجربه (XP):</b> +{found_xp}"
        )
        check_level_up(user_id, message.chat.id)

    # 3. تله یا آسیب عفونتی
    elif event_roll <= zombie_chance + 35:
        damage = random.randint(5, 15)
        inf_increase = random.randint(5, 10)
        
        new_hp = max(0, user['hp'] - damage)
        new_inf = min(100, user['infection'] + inf_increase)

        conn = get_db()
        conn.execute("UPDATE users SET hp = ?, infection = ? WHERE user_id = ?", (new_hp, new_inf, user_id))
        conn.commit()
        conn.close()

        bot.send_message(
            message.chat.id,
            f"⚠️ <b>رویداد غیرمنتظره!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"شما به یک تله سمی برخورد کردید یا زخمی شدید!\n\n"
            f"💔 <b>آسیب دیده‌شده:</b> -{damage} HP\n"
            f"☣️ <b>افزایش عفونت:</b> +{inf_increase}%"
        )

    # 4. عدم یافتن چیزی
    else:
        bot.send_message(
            message.chat.id,
            f"🔍 <b>کاوش در {region['name']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"مدتی در منطقه به کاوش پرداختید اما چیز باارزشی پیدا نکردید."
        )

def start_combat(message, user, zombie, region):
    user_id = user['user_id']
    
    # ذخیره حالت نبرد در دیتابیس
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO active_combats (user_id, zombie_id, zombie_hp, max_zombie_hp)
        VALUES (?, ?, ?, ?)
    """, (user_id, zombie['id'], zombie['hp'], zombie['hp']))
    conn.commit()
    
    weapon = conn.execute("SELECT * FROM weapons WHERE id = ?", (user['current_weapon_id'],)).fetchone()
    conn.close()

    weapon_name = weapon['name'] if weapon else "دست خالی"

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("⚔️ حمله", callback_data=f"cbt_atk_{zombie['id']}"),
        types.InlineKeyboardButton("🏃 فرار", callback_data=f"cbt_flee_{zombie['id']}")
    )

    text = (
        f"🧟 <b>مواجهه با زامبی!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"یک <b>{zombie['name']}</b> سد راه شما شده است!\n\n"
        f"📊 <b>مشخصات زامبی:</b>\n"
        f"❤️ سلامتی زامبی: {zombie['hp']}/{zombie['hp']}\n"
        f"⚔️ قدرت حمله: {zombie['damage']}\n\n"
        f"🛡️ <b>وضعیت شما:</b>\n"
        f"❤️ HP: {user['hp']}/{user['max_hp']} | 🔫 سلاح: {weapon_name}\n"
        f"☣️ عفونت: {user['infection']}%"
    )

    if zombie['image_id']:
        try:
            bot.send_photo(message.chat.id, zombie['image_id'], caption=text, reply_markup=kb)
        except Exception:
            bot.send_message(message.chat.id, text, reply_markup=kb)
    else:
        bot.send_message(message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("cbt_atk_"))
def callback_combat_attack(call):
    user_id = call.from_user.id
    user = get_or_create_user(user_id, call.from_user.username, call.from_user.first_name)

    conn = get_db()
    combat = conn.execute("SELECT * FROM active_combats WHERE user_id = ?", (user_id,)).fetchone()
    
    if not combat:
        conn.close()
        bot.answer_callback_query(call.id, "این نبرد به پایان رسیده است.")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        return

    zombie = conn.execute("SELECT * FROM zombies WHERE id = ?", (combat['zombie_id'],)).fetchone()
    weapon = conn.execute("SELECT * FROM weapons WHERE id = ?", (user['current_weapon_id'],)).fetchone()

    # محاسبه خسارت بازیکن
    player_damage = weapon['damage'] if weapon else 5
    player_damage += random.randint(-2, 5)
    
    new_zombie_hp = combat['zombie_hp'] - player_damage

    # پیروزی
    if new_zombie_hp <= 0:
        conn.execute("DELETE FROM active_combats WHERE user_id = ?", (user_id,))
        
        reward_scrap = zombie['reward_scrap']
        reward_xp = zombie['reward_xp']
        
        conn.execute("UPDATE users SET scrap = scrap + ?, xp = xp + ? WHERE user_id = ?", (reward_scrap, reward_xp, user_id))
        conn.commit()
        conn.close()

        res_text = (
            f"🎉 <b>پیروزی در نبرد!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"شما موفق شدید <b>{zombie['name']}</b> را نابود کنید!\n\n"
            f"💰 <b>پاداش Scrap:</b> +{reward_scrap}\n"
            f"⭐ <b>تجربه دریافتی:</b> +{reward_xp}"
        )

        bot.send_message(call.message.chat.id, res_text)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        check_level_up(user_id, call.message.chat.id)
        return

    # نوبت زامبی برای حمله
    zombie_damage = zombie['damage'] + random.randint(-1, 3)
    new_player_hp = max(0, user['hp'] - zombie_damage)
    
    inf_gain = random.randint(2, 8) if random.random() < 0.6 else 0
    new_infection = min(100, user['infection'] + inf_gain)

    conn.execute("UPDATE active_combats SET zombie_hp = ? WHERE user_id = ?", (new_zombie_hp, user_id))
    conn.execute("UPDATE users SET hp = ?, infection = ? WHERE user_id = ?", (new_player_hp, new_infection, user_id))
    conn.commit()
    conn.close()

    # مرگ بازیکن
    if new_player_hp <= 0:
        conn = get_db()
        conn.execute("DELETE FROM active_combats WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

        bot.answer_callback_query(call.id, "💀 شما کشته شدید!", show_alert=True)
        bot.send_message(call.message.chat.id, f"💀 <b>شما توسط {zombie['name']} کشته شدید!</b>\n\nبرای ادامه باید خود را درمان کنید.")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        return

    # ادامه مبارزه
    weapon_name = weapon['name'] if weapon else "دست خالی"
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("⚔️ حمله مجدد", callback_data=f"cbt_atk_{zombie['id']}"),
        types.InlineKeyboardButton("🏃 فرار", callback_data=f"cbt_flee_{zombie['id']}")
    )

    combat_text = (
        f"🧟 <b>در حال مبارزه با {zombie['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💥 شما {player_damage} آسیب زدید!\n"
        f"🩸 زامبی {zombie_damage} آسیب زد! (عفونت: +{inf_gain}%)\n\n"
        f"📊 <b>وضعیت نبرد:</b>\n"
        f"❤️ HP زامبی: {new_zombie_hp}/{combat['max_zombie_hp']}\n"
        f"🛡️ HP شما: {new_player_hp}/{user['max_hp']}\n"
        f"☣️ درصد عفونت: {new_infection}%\n"
        f"🔫 سلاح: {weapon_name}"
    )

    try:
        if call.message.photo:
            bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=combat_text, reply_markup=kb)
        else:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=combat_text, reply_markup=kb)
    except Exception:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("cbt_flee_"))
def callback_combat_flee(call):
    user_id = call.from_user.id
    
    if random.random() < 0.5:
        conn = get_db()
        conn.execute("DELETE FROM active_combats WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

        bot.answer_callback_query(call.id, "🏃 موفق به فرار شدید!", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "❌ فرار ناموفق بود! زامبی ضربه زد.", show_alert=True)
        callback_combat_attack(call)

def check_level_up(user_id, chat_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    
    req_xp = user['level'] * 100
    if user['xp'] >= req_xp:
        new_level = user['level'] + 1
        new_max_hp = user['max_hp'] + 20
        conn.execute("UPDATE users SET level = ?, max_hp = ?, hp = ? WHERE user_id = ?", (new_level, new_max_hp, new_max_hp, user_id))
        conn.commit()

        bot.send_message(
            chat_id,
            f"🎉 <b>ارتقای سطح! (LEVEL UP)</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎊 تبریک! شما به سطح <b>{new_level}</b> رسیدید!\n"
            f"❤️ حداکثر HP شما به <b>{new_max_hp}</b> افزایش یافت و کاملاً ترمیم شد."
        )
    conn.close()
    # ==========================================
# 🎒 سیستم کوله‌پشتی، آیتم‌ها و انتقال منابع (INVENTORY & TRANSFER)
# ==========================================

@bot.message_handler(commands=['inventory'])
@bot.message_handler(func=lambda msg: msg.text == "🎒 کوله‌پشتی")
def show_inventory(message):
    user_id = message.from_user.id
    user = get_or_create_user(user_id, message.from_user.username, message.from_user.first_name)

    if user['is_banned']:
        return

    conn = get_db()
    # دریافت آیتم‌های موجود در کوله‌پشتی
    items = conn.execute("""
        SELECT i.id, i.name, i.description, i.item_type, i.effect_value, ui.quantity
        FROM user_inventory ui
        JOIN items i ON ui.item_id = i.id
        WHERE ui.user_id = ? AND ui.quantity > 0
    """, (user_id,)).fetchall()
    
    weapon = conn.execute("SELECT name FROM weapons WHERE id = ?", (user['current_weapon_id'],)).fetchone()
    shelter = conn.execute("SELECT name FROM shelters WHERE id = ?", (user['current_shelter_id'],)).fetchone()
    conn.close()

    weapon_name = weapon['name'] if weapon else "دست خالی"
    shelter_name = shelter['name'] if shelter else "بدون پناهگاه (آواره)"

    if not items:
        text = (
            f"🎒 <b>کوله‌پشتی شما خالی است!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔫 <b>سلاح مجهز:</b> {weapon_name}\n"
            f"🏠 <b>پناهگاه:</b> {shelter_name}\n"
            f"💰 <b>موجودی Scrap:</b> {user['scrap']} 🪙"
        )
        bot.send_message(message.chat.id, text)
        return

    kb = types.InlineKeyboardMarkup(row_width=1)
    for item in items:
        kb.add(types.InlineKeyboardButton(
            f"📦 {item['name']} (تعداد: {item['quantity']})", 
            callback_data=f"inv_use_{item['id']}"
        ))

    text = (
        f"🎒 <b>کوله‌پشتی و تجهیزات شما</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔫 <b>سلاح مجهز:</b> {weapon_name}\n"
        f"🏠 <b>پناهگاه:</b> {shelter_name}\n"
        f"💰 <b>موجودی Scrap:</b> {user['scrap']} 🪙\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👇 برای استفاده از هر آیتم روی آن کلیک کنید:"
    )

    bot.send_message(message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("inv_use_"))
def callback_use_item(call):
    item_id = int(call.data.split("_")[2])
    user_id = call.from_user.id
    user = get_or_create_user(user_id, call.from_user.username, call.from_user.first_name)

    conn = get_db()
    inv_item = conn.execute("""
        SELECT ui.quantity, i.* 
        FROM user_inventory ui
        JOIN items i ON ui.item_id = i.id
        WHERE ui.user_id = ? AND ui.item_id = ? AND ui.quantity > 0
    """, (user_id, item_id)).fetchone()

    if not inv_item:
        conn.close()
        bot.answer_callback_query(call.id, "این آیتم در کوله‌پشتی شما موجود نیست.", show_alert=True)
        return

    item_type = inv_item['item_type']
    effect_val = inv_item['effect_value']
    msg_text = ""

    # آیتم‌های ترمیمی (Heal)
    if item_type == "heal":
        if user['hp'] >= user['max_hp']:
            conn.close()
            bot.answer_callback_query(call.id, "سلامتی شما کامل است و نیازی به درمان ندارید!", show_alert=True)
            return
        new_hp = min(user['max_hp'], user['hp'] + effect_val)
        conn.execute("UPDATE users SET hp = ? WHERE user_id = ?", (new_hp, user_id))
        msg_text = f"💉 شما از {inv_item['name']} استفاده کردید و {effect_val} واحد HP بازیابی شد!"

    # آیتم‌های پادزهر و درمان عفونت (Cure)
    elif item_type == "cure":
        if user['infection'] <= 0:
            conn.close()
            bot.answer_callback_query(call.id, "درصد عفونت شما ۰٪ است و نیازی به پادزهر ندارید!", show_alert=True)
            return
        new_inf = max(0, user['infection'] - effect_val)
        conn.execute("UPDATE users SET infection = ? WHERE user_id = ?", (new_inf, user_id))
        msg_text = f"🧪 شما از {inv_item['name']} استفاده کردید و {effect_val}٪ از عفونت شما کاسته شد!"

    else:
        msg_text = f"⚙️ از {inv_item['name']} استفاده شد."

    # کاهش تعداد مصرف‌شده از دیتابیس
    if inv_item['quantity'] > 1:
        conn.execute("UPDATE user_inventory SET quantity = quantity - 1 WHERE user_id = ? AND item_id = ?", (user_id, item_id))
    else:
        conn.execute("DELETE FROM user_inventory WHERE user_id = ? AND item_id = ?", (user_id, item_id))

    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, msg_text, show_alert=True)
    show_inventory(call.message)

# ==========================================
# 💸 سیستم انتقال Scrap بین بازماندگان (TRANSFER SYSTEM)
# ==========================================

@bot.message_handler(commands=['transfer', 'pay'])
def handle_transfer_command(message):
    user_id = message.from_user.id
    user = get_or_create_user(user_id, message.from_user.username, message.from_user.first_name)

    if user['is_banned']:
        return

    args = message.text.split()
    
    if len(args) < 3:
        bot.send_message(
            message.chat.id,
            "💡 <b>راهنمای انتقال Scrap:</b>\n"
            "برای انتقال قطعات Scrap به بازمانده دیگر از دستور زیر استفاده کنید:\n"
            "<code>/transfer [آیدی_عددی_مقصد] [مقدار]</code>\n\n"
            "مثال:\n<code>/transfer 123456789 100</code>"
        )
        return

    try:
        target_id = int(args[1])
        amount = int(args[2])
    except ValueError:
        bot.send_message(message.chat.id, "❌ آیدی عددی مقصد و مقدار Scrap باید به صورت عدد وارد شوند.")
        return

    if target_id == user_id:
        bot.send_message(message.chat.id, "⛔ شما نمی‌توانید به خودتان Scrap انتقال دهید!")
        return

    if amount <= 0:
        bot.send_message(message.chat.id, "⛔ مقدار انتقال باید یک عدد مثبت باشد.")
        return

    if user['scrap'] < amount:
        bot.send_message(
            message.chat.id, 
            f"❌ <b>موجودی کافی نیست!</b>\n"
            f"موجودی شما: {user['scrap']} Scrap\n"
            f"مقدار درخواست‌شده: {amount} Scrap"
        )
        return

    conn = get_db()
    target_user = conn.execute("SELECT * FROM users WHERE user_id = ?", (target_id,)).fetchone()

    if not target_user:
        conn.close()
        bot.send_message(message.chat.id, "❌ کاربر مقصد در دیتابیس ربات یافت نشد.")
        return

    # انجام تراکنش در دیتابیس
    conn.execute("UPDATE users SET scrap = scrap - ? WHERE user_id = ?", (amount, user_id))
    conn.execute("UPDATE users SET scrap = scrap + ? WHERE user_id = ?", (amount, target_id))
    conn.commit()
    conn.close()

    bot.send_message(
        message.chat.id,
        f"✅ <b>انتقال با موفقیت انجام شد!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>مقدار:</b> {amount} Scrap\n"
        f"👤 <b>گیرنده:</b> {target_user['first_name']} (<code>{target_id}</code>)\n"
        f"🪙 <b>موجودی جدید شما:</b> {user['scrap'] - amount} Scrap"
    )

    try:
        bot.send_message(
            target_id,
            f"🎁 <b>دریافت Scrap!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"بازمانده <b>{user['first_name']}</b> مقدار <b>{amount} Scrap</b> به حساب شما واریز کرد!"
        )
    except Exception:
        pass
    # ==========================================
# 📜 سیستم ماموریت‌ها و پاداش روزانه (QUESTS & DAILY REWARDS)
# ==========================================

import datetime

@bot.message_handler(commands=['daily'])
@bot.message_handler(func=lambda msg: msg.text == "🎁 پاداش روزانه")
def handle_daily_reward(message):
    user_id = message.from_user.id
    user = get_or_create_user(user_id, message.from_user.username, message.from_user.first_name)

    if user['is_banned']:
        return

    now = datetime.datetime.now()
    
    # بررسی زمان آخرین دریافت پاداش
    conn = get_db()
    row = conn.execute("SELECT last_daily_claim FROM users WHERE user_id = ?", (user_id,)).fetchone()
    
    last_claim_str = row['last_daily_claim'] if row and 'last_daily_claim' in row.keys() else None
    
    can_claim = False
    hours, minutes = 0, 0

    if not last_claim_str:
        can_claim = True
    else:
        try:
            last_claim = datetime.datetime.fromisoformat(last_claim_str)
            elapsed_sec = (now - last_claim).total_seconds()
            if elapsed_sec >= 86400:  # 24 ساعت
                can_claim = True
            else:
                remaining_sec = 86400 - int(elapsed_sec)
                hours = remaining_sec // 3600
                minutes = (remaining_sec % 3600) // 60
        except Exception:
            can_claim = True

    if not can_claim:
        conn.close()
        bot.send_message(
            message.chat.id,
            f"⏳ <b>پاداش روزانه قبلاً دریافت شده است!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"لطفاً <b>{hours} ساعت و {minutes} دقیقه</b> دیگر دوباره تلاش کنید."
        )
        return

    # محاسبه و اعطای پاداش بر اساس سطح کاربر
    reward_scrap = 100 + (user['level'] * 15)
    reward_xp = 50 + (user['level'] * 5)
    
    conn.execute(
        "UPDATE users SET scrap = scrap + ?, xp = xp + ?, last_daily_claim = ? WHERE user_id = ?",
        (reward_scrap, reward_xp, now.isoformat(), user_id)
    )
    conn.commit()
    conn.close()

    bot.send_message(
        message.chat.id,
        f"🎁 <b>پاداش روزانه دریافت شد!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Scrap دریافتی:</b> +{reward_scrap} 🪙\n"
        f"⭐ <b>تجربه (XP):</b> +{reward_xp}\n\n"
        f"فردا نیز برای دریافت پاداش جدید سر بزنید!"
    )
    check_level_up(user_id, message.chat.id)

@bot.message_handler(commands=['quests'])
@bot.message_handler(func=lambda msg: msg.text == "📜 ماموریت‌ها")
def show_quests_menu(message):
    user_id = message.from_user.id
    user = get_or_create_user(user_id, message.from_user.username, message.from_user.first_name)

    if user['is_banned']:
        return

    conn = get_db()
    quests = conn.execute("SELECT * FROM quests WHERE is_active = 1").fetchall()
    
    # دریافت وضعیت ماموریت‌های کاربر
    user_quests = conn.execute("SELECT quest_id, is_completed, reward_claimed FROM user_quests WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()

    uq_map = {uq['quest_id']: uq for uq in user_quests}

    if not quests:
        bot.send_message(message.chat.id, "📜 <b>در حال حاضر هیچ ماموریتی فعال نیست.</b>")
        return

    kb = types.InlineKeyboardMarkup(row_width=1)
    
    for q in quests:
        q_status = uq_map.get(q['id'])
        if not q_status:
            status_btn = f"📜 {q['title']} (در حال انجام)"
            cb_data = f"qst_info_{q['id']}"
        elif q_status['is_completed'] and not q_status['reward_claimed']:
            status_btn = f"✅ {q['title']} (دریافت پاداش!)"
            cb_data = f"qst_claim_{q['id']}"
        elif q_status['reward_claimed']:
            status_btn = f"☑️ {q['title']} (تکمیل شده)"
            cb_data = f"qst_info_{q['id']}"
        else:
            status_btn = f"📜 {q['title']} (در حال انجام)"
            cb_data = f"qst_info_{q['id']}"

        kb.add(types.InlineKeyboardButton(status_btn, callback_data=cb_data))

    text = (
        f"📜 <b>لیست ماموریت‌های بازماندگان</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"ماموریت‌ها را انجام دهید تا پاداش ویژه Scrap و XP دریافت کنید:"
    )

    bot.send_message(message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("qst_info_"))
def callback_quest_info(call):
    quest_id = int(call.data.split("_")[2])

    conn = get_db()
    q = conn.execute("SELECT * FROM quests WHERE id = ?", (quest_id,)).fetchone()
    conn.close()

    if not q:
        bot.answer_callback_query(call.id, "ماموریت یافت نشد.")
        return

    text = (
        f"📜 <b>ماموریت: {q['title']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📝 <b>توضیحات:</b>\n{q['description']}\n\n"
        f"🎁 <b>پاداش:</b>\n"
        f"💰 Scrap: +{q['reward_scrap']}\n"
        f"⭐ XP: +{q['reward_xp']}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text)

@bot.callback_query_handler(func=lambda call: call.data.startswith("qst_claim_"))
def callback_quest_claim(call):
    quest_id = int(call.data.split("_")[2])
    user_id = call.from_user.id

    conn = get_db()
    q = conn.execute("SELECT * FROM quests WHERE id = ?", (quest_id,)).fetchone()
    uq = conn.execute("SELECT * FROM user_quests WHERE user_id = ? AND quest_id = ?", (user_id, quest_id)).fetchone()

    if not uq or not uq['is_completed']:
        conn.close()
        bot.answer_callback_query(call.id, "این ماموریت هنوز تکمیل نشده است!", show_alert=True)
        return

    if uq['reward_claimed']:
        conn.close()
        bot.answer_callback_query(call.id, "پاداش این ماموریت قبلاً دریافت شده است.", show_alert=True)
        return

    # اعطای پاداش و ثبت دریافت
    conn.execute("UPDATE users SET scrap = scrap + ?, xp = xp + ? WHERE user_id = ?", (q['reward_scrap'], q['reward_xp'], user_id))
    conn.execute("UPDATE user_quests SET reward_claimed = 1 WHERE user_id = ? AND quest_id = ?", (user_id, quest_id))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, "🎉 پاداش ماموریت دریافت شد!", show_alert=True)
    bot.send_message(
        call.message.chat.id,
        f"🎉 <b>ماموریت تکمیل شد!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏆 <b>نام ماموریت:</b> {q['title']}\n"
        f"💰 <b>Scrap دریافتی:</b> +{q['reward_scrap']}\n"
        f"⭐ <b>تجربه دریافتی:</b> +{q['reward_xp']}"
    )
    check_level_up(user_id, call.message.chat.id)
    show_quests_menu(call.message)
# ==========================================
# 🛠️ پنل مدیریت و ادمین (ADMIN PANEL & MANAGEMENT)
# ==========================================

def is_admin(user_id):
    return user_id in ADMIN_IDS

@bot.message_handler(commands=['admin'])
@bot.message_handler(func=lambda msg: msg.text == "🛠️ پنل مدیریت")
def handle_admin_panel(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.send_message(message.chat.id, "⛔ شما دسترسی ادمین ندارید.")
        return

    conn = get_db()
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    banned_users = conn.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1").fetchone()[0]
    total_scrap = conn.execute("SELECT SUM(scrap) FROM users").fetchone()[0] or 0
    total_maps = conn.execute("SELECT COUNT(*) FROM maps").fetchone()[0]
    total_zombies = conn.execute("SELECT COUNT(*) FROM zombies").fetchone()[0]
    conn.close()

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📊 آمار دیتابیس", callback_data="adm_stats"),
        types.InlineKeyboardButton("📢 راهنمای همگانی", callback_data="adm_bc_help")
    )

    text = (
        f"🛠️ <b>پنل مدیریت ZOMBIE SURVIVAL BOT</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>تعداد کل بازماندگان:</b> {total_users}\n"
        f"🚫 <b>کاربران مسدودشده:</b> {banned_users}\n"
        f"💰 <b>کل Scrap درون بازی:</b> {total_scrap}\n"
        f"🗺️ <b>تعداد نقشه‌ها:</b> {total_maps} | 🧟 <b>تعداد زامبی‌ها:</b> {total_zombies}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>دستورات سریع ادمین:</b>\n"
        f"▫️ <code>/ban [user_id]</code> - مسدودسازی کاربر\n"
        f"▫️ <code>/unban [user_id]</code> - رفع مسدودسازی کاربر\n"
        f"▫️ <code>/givescrap [user_id] [amount]</code> - اعطای Scrap به کاربر\n"
        f"▫️ <code>/broadcast [متن پیام]</code> - ارسال پیام همگانی به همه"
    )

    bot.send_message(message.chat.id, text, reply_markup=kb)

# ------------------------------------------
# 🚫 مسدودسازی و رفع مسدودسازی (BAN / UNBAN)
# ------------------------------------------

@bot.message_handler(commands=['ban'])
def handle_ban_user(message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        bot.send_message(message.chat.id, "💡 راهنما: <code>/ban [user_id]</code>")
        return
    try:
        target_id = int(args[1])
        conn = get_db()
        conn.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_id,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"🚫 کاربر <code>{target_id}</code> با موفقیت بن شد.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ آیدی عددی نامعتبر است.")

@bot.message_handler(commands=['unban'])
def handle_unban_user(message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        bot.send_message(message.chat.id, "💡 راهنما: <code>/unban [user_id]</code>")
        return
    try:
        target_id = int(args[1])
        conn = get_db()
        conn.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (target_id,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ کاربر <code>{target_id}</code> آنبن شد.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ آیدی عددی نامعتبر است.")

# ------------------------------------------
# 🪙 اعطای مستقیم Scrap به کاربر
# ------------------------------------------

@bot.message_handler(commands=['givescrap'])
def handle_give_scrap(message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 3:
        bot.send_message(message.chat.id, "💡 راهنما: <code>/givescrap [user_id] [amount]</code>")
        return
    try:
        target_id = int(args[1])
        amount = int(args[2])
        conn = get_db()
        conn.execute("UPDATE users SET scrap = scrap + ? WHERE user_id = ?", (amount, target_id))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"🪙 مقدار {amount} Scrap به حساب کاربر <code>{target_id}</code> اضافه شد.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ ورودی‌های عددی نامعتبر است.")

# ------------------------------------------
# 📢 سیستم ارسال همگانی (BROADCAST SYSTEM)
# ------------------------------------------

@bot.message_handler(commands=['broadcast'])
def handle_broadcast_command(message):
    if not is_admin(message.from_user.id):
        return
    
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        bot.send_message(
            message.chat.id, 
            "💡 لطفاً متن اعلان همگانی را بعد از دستور وارد کنید.\n"
            "مثال:\n<code>/broadcast توجه! سرورهای بازی آپدیت شدند.</code>"
        )
        return

    conn = get_db()
    users = conn.execute("SELECT user_id FROM users WHERE is_banned = 0").fetchall()
    conn.close()

    success = 0
    failed = 0

    bot.send_message(message.chat.id, f"⏳ در حال ارسال همگانی به {len(users)} کاربر...")

    for u in users:
        try:
            bot.send_message(u['user_id'], f"📢 <b>اطلاعیه مدیریت:</b>\n\n{text}")
            success += 1
        except Exception:
            failed += 1

    bot.send_message(
        message.chat.id,
        f"📢 <b>نتیجه ارسال همگانی:</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✅ با موفقیت ارسال شد: {success}\n"
        f"❌ ناموفق (بلاک شده/شکست): {failed}"
    )

# ------------------------------------------
# ⚙️ کال‌بک‌های دکمه‌های ادمین
# ------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data == "adm_stats")
def callback_admin_stats(call):
    if not is_admin(call.from_user.id):
        return
    conn = get_db()
    reg_count = conn.execute("SELECT COUNT(*) FROM regions").fetchone()[0]
    wpn_count = conn.execute("SELECT COUNT(*) FROM weapons").fetchone()[0]
    item_count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    quest_count = conn.execute("SELECT COUNT(*) FROM quests").fetchone()[0]
    conn.close()

    bot.answer_callback_query(
        call.id,
        f"📊 آمار اجزای بازی:\n"
        f"مناطق: {reg_count} | سلاح‌ها: {wpn_count}\n"
        f"آیتم‌ها: {item_count} | ماموریت‌ها: {quest_count}",
        show_alert=True
    )

@bot.callback_query_handler(func=lambda call: call.data == "adm_bc_help")
def callback_admin_bc_help(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(
        call.id,
        "ارسال همگانی با دستور /broadcast [متن] انجام می‌شود.",
        show_alert=True
        )
    # ==========================================
# 🔄 مدیریت پیام‌های ناشناخته و حلقه اجرا (POLLING & MAIN)
# ==========================================

@bot.message_handler(func=lambda msg: True)
def handle_unknown_messages(message):
    user_id = message.from_user.id
    user = get_or_create_user(user_id, message.from_user.username, message.from_user.first_name)

    if user['is_banned']:
        return

    bot.send_message(
        message.chat.id,
        "❓ <b>دستور یا پیام وارد شده نامفهوم است!</b>\n\n"
        "لطفاً از دکمه‌های کیبورد اصلی یا دستور /start استفاده کنید."
    )

if __name__ == '__main__':
    print("🤖 ZOMBIE SURVIVAL BOT IS RUNNING...")
    print("✅ دیتابیس آماده شد و ربات فعال است.")
    
    # حلقه مقاوم در برابر قطع و وصلی اینترنت (مناسب برای اجرا روی Pydroid 3)
    import time
    while True:
        try:
            bot.infinity_polling(timeout=15, long_polling_timeout=5)
        except Exception as e:
            print(f"⚠️ خطای اتصال شبکه: {e}")
            time.sleep(3)
    
