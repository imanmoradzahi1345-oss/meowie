# ==================== بخش ۱ از ۴ - نسخه ۳ ====================
# تنظیمات + دیتابیس کامل + توابع پایه + منوها

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
import sqlite3
import threading
import time
import json
import re
import random
import string
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
    TEHRAN = ZoneInfo("Asia/Tehran")
except:
    TEHRAN = None

BOT_TOKEN = "8924668463:AAH7rV1LMZZ6Amn3JEQV6SRHeEM9KwI6lgA"
ADMIN_IDS = [7530457395]

bot = telebot.TeleBot(BOT_TOKEN)

# ----------------- دیتابیس کامل -----------------
def init_db():
    conn = sqlite3.connect("nova_v3.db")
    c = conn.cursor()

    # کاربران
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        is_premium INTEGER DEFAULT 0,
        premium_until TEXT,
        max_channels INTEGER DEFAULT 3,
        is_banned INTEGER DEFAULT 0,
        referral_code TEXT UNIQUE,
        referred_by INTEGER,
        joined_at TEXT,
        last_active TEXT
    )''')

    # کانال‌های کاربران
    c.execute('''CREATE TABLE IF NOT EXISTS user_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        channel_id TEXT,
        channel_title TEXT,
        is_active INTEGER DEFAULT 0,
        UNIQUE(user_id, channel_id)
    )''')

    # قفل کانال‌ها (چندتایی)
    c.execute('''CREATE TABLE IF NOT EXISTS forced_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT UNIQUE,
        channel_title TEXT
    )''')

    # تنظیمات
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

    # پست‌های زمان‌بندی
    c.execute('''CREATE TABLE IF NOT EXISTS scheduled_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        channel_id TEXT,
        content_type TEXT,
        file_id TEXT,
        text_content TEXT,
        caption TEXT,
        buttons TEXT,
        send_time TEXT,
        status TEXT DEFAULT 'pending'
    )''')

    # تاریخچه اعضا برای آنالیز
    c.execute('''CREATE TABLE IF NOT EXISTS member_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT,
        members INTEGER,
        recorded_at TEXT
    )''')

    # قالب‌ها
    c.execute('''CREATE TABLE IF NOT EXISTS templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        content TEXT
    )''')

    # لاگ
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        details TEXT,
        created_at TEXT
    )''')

    # تنظیمات پیش‌فرض
    defaults = {
        "premium_price": "10",
        "premium_days": "30",
        "max_channels_default": "3",
        "maintenance": "0",
        "footer_global": ""
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect("nova_v3.db")

def is_main_admin(uid):
    return uid in ADMIN_IDS

def now_tehran():
    if TEHRAN:
        return datetime.now(TEHRAN)
    return datetime.now()

def get_setting(key, default=""):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key, value):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def ensure_user(user):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id=?", (user.id,))
    if not c.fetchone():
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        max_ch = int(get_setting("max_channels_default", "3"))
        c.execute('''INSERT INTO users 
            (user_id, username, full_name, max_channels, referral_code, joined_at, last_active) 
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (user.id, user.username or "", user.full_name or "", max_ch, code,
             now_tehran().strftime("%Y-%m-%d %H:%M"), now_tehran().strftime("%Y-%m-%d %H:%M")))
    else:
        c.execute("UPDATE users SET username=?, full_name=?, last_active=? WHERE user_id=?",
                  (user.username or "", user.full_name or "", now_tehran().strftime("%Y-%m-%d %H:%M"), user.id))
    conn.commit()
    conn.close()

def is_premium(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT is_premium, premium_until FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row or row[0] == 0:
        return False
    if row[1]:
        try:
            until = datetime.strptime(row[1], "%Y-%m-%d %H:%M")
            if now_tehran().replace(tzinfo=None) > until:
                return False
        except:
            pass
    return True

def get_user_active_channel(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT channel_id, channel_title FROM user_channels WHERE user_id=? AND is_active=1", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def get_user_channels_count(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM user_channels WHERE user_id=?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

def log_action(user_id, action, details=""):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO logs (user_id, action, details, created_at) VALUES (?, ?, ?, ?)",
              (user_id, action, details, now_tehran().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

# دکمه‌های موقت
user_buttons = {}

def build_markup(user_id):
    buttons = user_buttons.get(user_id, [])
    if not buttons:
        return None
    markup = InlineKeyboardMarkup(row_width=2)
    btns = [InlineKeyboardButton(b["text"], url=b["url"]) for b in buttons]
    markup.add(*btns)
    return markup

# ----------------- منوها -----------------
def main_menu(user_id):
    active = get_user_active_channel(user_id)
    active_text = (active[1][:18] + "..") if active and active[1] else "انتخاب نشده"
    premium = "⭐ پرمیوم" if is_premium(user_id) else ""

    m = InlineKeyboardMarkup(row_width=2)
    m.add(InlineKeyboardButton(f"📢 کانال فعال: {active_text}", callback_data="my_channels"))
    m.add(
        InlineKeyboardButton("📤 ارسال لحظه‌ای", callback_data="send_now"),
        InlineKeyboardButton("👀 پست آزمایشی", callback_data="preview_post"),
    )
    m.add(
        InlineKeyboardButton("⏰ زمان‌بندی", callback_data="schedule_post"),
        InlineKeyboardButton("🔘 دکمه‌ها", callback_data="buttons_menu"),
    )
    m.add(
        InlineKeyboardButton("📊 آنالیز", callback_data="analyze_channel"),
        InlineKeyboardButton("📌 پین / 🗑 حذف", callback_data="pin_delete_menu"),
    )
    m.add(
        InlineKeyboardButton("📝 قالب‌ها", callback_data="templates_menu"),
        InlineKeyboardButton("✍️ امضا", callback_data="set_footer"),
    )
    m.add(
        InlineKeyboardButton("⭐ خرید پرمیوم", callback_data="buy_premium"),
        InlineKeyboardButton("🎁 دعوت دوستان", callback_data="referral"),
    )
    if is_main_admin(user_id):
        m.add(InlineKeyboardButton("👑 پنل ادمین", callback_data="admin_panel"))
    if premium:
        m.add(InlineKeyboardButton(premium, callback_data="premium_info"))
    return m

print("✅ بخش ۱ نسخه ۳ آماده شد")
# ==================== بخش ۲ از ۴ ====================
# کال‌بک‌ها + پنل کاربر + پنل ادمین + پرمیوم + قفل چندتایی

@bot.message_handler(commands=['start'])
def start(message):
    ensure_user(message.from_user)
    uid = message.from_user.id

    # حالت تعمیرات
    if get_setting("maintenance") == "1" and not is_main_admin(uid):
        bot.send_message(message.chat.id, "🛠️ ربات در حال تعمیرات است. لطفاً بعداً مراجعه کنید.")
        return

    # بررسی مسدود بودن
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    conn.close()
    if row and row[0] == 1:
        bot.send_message(message.chat.id, "🚫 حساب شما مسدود شده است.")
        return

    # بررسی قفل کانال‌های چندتایی
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT channel_id, channel_title FROM forced_channels")
    forced_list = c.fetchall()
    conn.close()

    if forced_list and not is_main_admin(uid):
        not_joined = []
        for ch_id, title in forced_list:
            try:
                member = bot.get_chat_member(ch_id, uid)
                if member.status in ["left", "kicked"]:
                    not_joined.append((ch_id, title))
            except:
                not_joined.append((ch_id, title))

        if not_joined:
            markup = InlineKeyboardMarkup(row_width=1)
            for ch_id, title in not_joined:
                link = ch_id if ch_id.startswith("http") else f"https://t.me/{ch_id.replace('@','')}"
                markup.add(InlineKeyboardButton(f"📢 عضویت در {title or ch_id}", url=link))
            markup.add(InlineKeyboardButton("✅ عضو شدم، بررسی مجدد", callback_data="check_forced"))
            bot.send_message(message.chat.id, "🔒 برای استفاده از ربات باید در کانال‌های زیر عضو شوید:", reply_markup=markup)
            return

    bot.send_message(message.chat.id,
        f"سلام {message.from_user.first_name}!\n\nبه ربات پیشرفته مدیریت کانال (نسخه ۳) خوش آمدید.",
        reply_markup=main_menu(uid))

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    uid = call.from_user.id
    ensure_user(call.from_user)
    data = call.data
    bot.user_steps = getattr(bot, "user_steps", {})

    if data == "back_main":
        bot.edit_message_text("منوی اصلی:", call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))

    elif data == "check_forced":
        bot.answer_callback_query(call.id, "در حال بررسی...")
        # دوباره استارت رو شبیه‌سازی می‌کنیم
        start(call.message)
        return

    # ---------- مدیریت کانال‌ها ----------
    elif data == "my_channels":
        channels = []
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT channel_id, channel_title, is_active FROM user_channels WHERE user_id=?", (uid,))
        channels = c.fetchall()
        conn.close()

        m = InlineKeyboardMarkup(row_width=1)
        for ch_id, title, active in channels:
            status = "✅ " if active else ""
            m.add(InlineKeyboardButton(f"{status}{title or ch_id}", callback_data=f"select_ch_{ch_id}"))
        m.add(InlineKeyboardButton("➕ اضافه کردن کانال", callback_data="add_channel"))
        m.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
        bot.edit_message_text("📢 کانال‌های شما:", call.message.chat.id, call.message.message_id, reply_markup=m)

    elif data == "add_channel":
        bot.user_steps[uid] = {"step": "add_channel"}
        bot.edit_message_text("آیدی کانالی که ادمین آن هستید را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data.startswith("select_ch_"):
        ch_id = data.replace("select_ch_", "")
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE user_channels SET is_active=0 WHERE user_id=?", (uid,))
        c.execute("UPDATE user_channels SET is_active=1 WHERE user_id=? AND channel_id=?", (uid, ch_id))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "✅ کانال فعال شد")
        bot.edit_message_text("منوی اصلی:", call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))

    # ---------- ارسال و پیش‌نمایش ----------
    elif data == "send_now":
        if not get_user_active_channel(uid):
            bot.answer_callback_query(call.id, "اول کانال فعال انتخاب کنید", show_alert=True)
            return
        bot.user_steps[uid] = {"step": "send_now"}
        bot.edit_message_text("محتوا را بفرستید (متن یا عکس/ویدیو + کپشن):", call.message.chat.id, call.message.message_id)

    elif data == "preview_post":
        if not get_user_active_channel(uid):
            bot.answer_callback_query(call.id, "اول کانال فعال انتخاب کنید", show_alert=True)
            return
        bot.user_steps[uid] = {"step": "preview_post"}
        bot.edit_message_text("محتوا را برای پیش‌نمایش بفرستید:", call.message.chat.id, call.message.message_id)

    # ---------- زمان‌بندی ----------
    elif data == "schedule_post":
        if not get_user_active_channel(uid):
            bot.answer_callback_query(call.id, "اول کانال فعال انتخاب کنید", show_alert=True)
            return
        bot.user_steps[uid] = {"step": "schedule_content"}
        now = now_tehran().strftime("%H:%M")
        bot.edit_message_text(f"محتوا را بفرستید.\nساعت فعلی ایران: `{now}`", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    # ---------- دکمه‌ها ----------
    elif data == "buttons_menu":
        m = InlineKeyboardMarkup(row_width=1)
        m.add(
            InlineKeyboardButton("➕ اضافه کردن دکمه", callback_data="add_btn"),
            InlineKeyboardButton("👁 مشاهده", callback_data="view_btn"),
            InlineKeyboardButton("🧹 پاک کردن", callback_data="clear_btn"),
            InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")
        )
        bot.edit_message_text("مدیریت دکمه‌های شیشه‌ای:", call.message.chat.id, call.message.message_id, reply_markup=m)

    elif data == "add_btn":
        bot.user_steps[uid] = {"step": "btn_text"}
        bot.edit_message_text("متن دکمه را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "view_btn":
        btns = user_buttons.get(uid, [])
        text = "دکمه‌های فعلی:\n\n" + "\n".join([f"{i+1}. {b['text']} - {b['url']}" for i, b in enumerate(btns)]) if btns else "خالی"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙", callback_data="buttons_menu")))

    elif data == "clear_btn":
        user_buttons[uid] = []
        bot.answer_callback_query(call.id, "پاک شد", show_alert=True)

    # ---------- آنالیز ----------
    elif data == "analyze_channel":
        active = get_user_active_channel(uid)
        if not active:
            bot.answer_callback_query(call.id, "کانال فعال انتخاب کنید", show_alert=True)
            return
        try:
            chat = bot.get_chat(active[0])
            members = bot.get_chat_member_count(active[0])
            admins = len(bot.get_chat_administrators(active[0]))
            
            # ذخیره تاریخچه
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO member_history (channel_id, members, recorded_at) VALUES (?, ?, ?)",
                      (active[0], members, now_tehran().strftime("%Y-%m-%d %H:%M")))
            conn.commit()
            conn.close()

            text = f"""
📊 **آنالیز کانال**

📌 {chat.title}
👥 اعضا: **{members:,}**
👑 ادمین: **{admins}**
🆔 `{chat.id}`

وضعیت: {"عالی" if members > 5000 else "خوب" if members > 1000 else "در حال رشد"}
"""
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid), parse_mode="Markdown")
        except Exception as e:
            bot.answer_callback_query(call.id, f"خطا: {e}", show_alert=True)

    # ---------- پین و حذف ----------
    elif data == "pin_delete_menu":
        m = InlineKeyboardMarkup(row_width=2)
        m.add(
            InlineKeyboardButton("📌 پین", callback_data="do_pin"),
            InlineKeyboardButton("🗑 حذف", callback_data="do_delete")
        )
        m.add(InlineKeyboardButton("🔙", callback_data="back_main"))
        bot.edit_message_text("انتخاب کنید:", call.message.chat.id, call.message.message_id, reply_markup=m)

    elif data == "do_pin":
        bot.user_steps[uid] = {"step": "pin"}
        bot.edit_message_text("آیدی پیام برای پین:", call.message.chat.id, call.message.message_id)

    elif data == "do_delete":
        bot.user_steps[uid] = {"step": "delete"}
        bot.edit_message_text("آیدی پیام برای حذف:", call.message.chat.id, call.message.message_id)

    # ---------- پرمیوم ----------
    elif data == "buy_premium":
        price = get_setting("premium_price", "10")
        days = get_setting("premium_days", "30")
        bot.user_steps[uid] = {"step": "confirm_premium"}
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton(f"پرداخت {price} استارز", callback_data="pay_premium"))
        m.add(InlineKeyboardButton("انصراف", callback_data="back_main"))
        bot.edit_message_text(f"⭐ پرمیوم ({days} روزه)\n\nمزایا:\n• کانال نامحدود\n• امکانات بیشتر\n\nقیمت: {price} استارز", 
                              call.message.chat.id, call.message.message_id, reply_markup=m)

    elif data == "pay_premium":
        price = int(get_setting("premium_price", "10"))
        prices = [LabeledPrice(label="Premium", amount=price)]
        bot.send_invoice(
            call.message.chat.id,
            title="خرید پرمیوم",
            description=f"اشتراک پرمیوم {get_setting('premium_days')} روزه",
            invoice_payload=f"premium_{uid}",
            provider_token="",
            currency="XTR",
            prices=prices
        )

    # ---------- دعوت ----------
    elif data == "referral":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT referral_code FROM users WHERE user_id=?", (uid,))
        code = c.fetchone()[0]
        conn.close()
        bot_username = bot.get_me().username
        link = f"https://t.me/{bot_username}?start={code}"
        bot.edit_message_text(f"🎁 لینک دعوت شما:\n`{link}`\n\nبا دعوت دوستان سقف کانال شما افزایش می‌یابد.", 
                              call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=main_menu(uid))

    # ---------- پنل ادمین ----------
    elif data == "admin_panel" and is_main_admin(uid):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE is_premium=1")
        premiums = c.fetchone()[0]
        conn.close()

        m = InlineKeyboardMarkup(row_width=1)
        m.add(
            InlineKeyboardButton(f"👥 کاربران: {total} | پرمیوم: {premiums}", callback_data="admin_users"),
            InlineKeyboardButton("💰 تنظیم قیمت پرمیوم", callback_data="admin_premium_price"),
            InlineKeyboardButton("🔒 مدیریت قفل کانال‌ها", callback_data="admin_forced"),
            InlineKeyboardButton("⚙️ سقف کانال پیش‌فرض", callback_data="admin_max_ch"),
            InlineKeyboardButton("🛠️ حالت تعمیرات", callback_data="admin_maintenance"),
            InlineKeyboardButton("📅 زمان‌بندی‌ها", callback_data="admin_sched"),
            InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")
        )
        bot.edit_message_text("👑 پنل ادمین نسخه ۳:", call.message.chat.id, call.message.message_id, reply_markup=m)

    elif data == "admin_premium_price" and is_main_admin(uid):
        bot.user_steps[uid] = {"step": "set_premium_price"}
        bot.edit_message_text(f"قیمت فعلی: {get_setting('premium_price')} استارز\nقیمت جدید را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "admin_forced" and is_main_admin(uid):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, channel_id, channel_title FROM forced_channels")
        rows = c.fetchall()
        conn.close()
        m = InlineKeyboardMarkup(row_width=1)
        for r in rows:
            m.add(InlineKeyboardButton(f"❌ {r[2] or r[1]}", callback_data=f"del_forced_{r[0]}"))
        m.add(InlineKeyboardButton("➕ اضافه کردن کانال قفل", callback_data="add_forced"))
        m.add(InlineKeyboardButton("🔙", callback_data="admin_panel"))
        bot.edit_message_text("کانال‌های قفل‌شده:", call.message.chat.id, call.message.message_id, reply_markup=m)

    elif data == "add_forced" and is_main_admin(uid):
        bot.user_steps[uid] = {"step": "add_forced"}
        bot.edit_message_text("آیدی کانال برای قفل را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data.startswith("del_forced_") and is_main_admin(uid):
        fid = int(data.split("_")[2])
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM forced_channels WHERE id=?", (fid,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "حذف شد")

    elif data == "admin_maintenance" and is_main_admin(uid):
        current = get_setting("maintenance")
        new = "0" if current == "1" else "1"
        set_setting("maintenance", new)
        status = "فعال شد" if new == "1" else "غیرفعال شد"
        bot.answer_callback_query(call.id, f"حالت تعمیرات {status}", show_alert=True)

    bot.answer_callback_query(call.id)

print("✅ بخش ۲ آماده شد")
# ==================== بخش ۳ از ۴ ====================
# هندلر پیام‌ها + ارسال + زمان‌بندی + پیش‌نمایش + تنظیمات ادمین

def send_to_channel(channel, content_type, file_id=None, text=None, caption=None, buttons=None):
    footer = get_setting("footer_global")
    if footer:
        if caption:
            caption = f"{caption}\n\n{footer}"
        elif text:
            text = f"{text}\n\n{footer}"
        else:
            caption = footer

    try:
        if content_type == "text":
            return bot.send_message(channel, text, reply_markup=buttons, parse_mode="Markdown")
        elif content_type == "photo":
            return bot.send_photo(channel, file_id, caption=caption, reply_markup=buttons)
        elif content_type == "video":
            return bot.send_video(channel, file_id, caption=caption, reply_markup=buttons)
        elif content_type == "animation":
            return bot.send_animation(channel, file_id, caption=caption, reply_markup=buttons)
        elif content_type == "voice":
            return bot.send_voice(channel, file_id, caption=caption, reply_markup=buttons)
        elif content_type == "sticker":
            return bot.send_sticker(channel, file_id, reply_markup=buttons)
        elif content_type == "document":
            return bot.send_document(channel, file_id, caption=caption, reply_markup=buttons)
    except Exception as e:
        raise e

@bot.message_handler(content_types=['text', 'photo', 'video', 'animation', 'voice', 'sticker', 'document'])
def handle_all(message):
    uid = message.from_user.id
    ensure_user(message.from_user)
    bot.user_steps = getattr(bot, "user_steps", {})
    step_data = bot.user_steps.get(uid, {})
    step = step_data.get("step")

    # ---------- اضافه کردن کانال ----------
    if step == "add_channel":
        ch = message.text.strip()
        try:
            member = bot.get_chat_member(ch, uid)
            if member.status not in ["administrator", "creator"]:
                bot.send_message(message.chat.id, "❌ شما ادمین این کانال نیستید.", reply_markup=main_menu(uid))
                bot.user_steps[uid] = {}
                return

            # چک سقف کانال
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT max_channels, is_premium FROM users WHERE user_id=?", (uid,))
            row = c.fetchone()
            max_ch = 999 if (row and row[1] == 1) else (row[0] if row else 3)
            c.execute("SELECT COUNT(*) FROM user_channels WHERE user_id=?", (uid,))
            current = c.fetchone()[0]

            if current >= max_ch:
                bot.send_message(message.chat.id, f"❌ سقف کانال شما ({max_ch}) پر است. برای افزایش، پرمیوم بخرید.", reply_markup=main_menu(uid))
                conn.close()
                bot.user_steps[uid] = {}
                return

            chat = bot.get_chat(ch)
            c.execute("INSERT OR IGNORE INTO user_channels (user_id, channel_id, channel_title, is_active) VALUES (?, ?, ?, 0)",
                      (uid, str(chat.id), chat.title or ch))
            conn.commit()
            conn.close()
            bot.send_message(message.chat.id, f"✅ کانال «{chat.title}» اضافه شد.", reply_markup=main_menu(uid))
            log_action(uid, "add_channel", chat.title)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا: {e}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ---------- دکمه‌ها ----------
    if step == "btn_text":
        bot.user_steps[uid] = {"step": "btn_url", "text": message.text.strip()}
        bot.send_message(message.chat.id, "لینک دکمه را بفرستید (https://...):")
        return

    if step == "btn_url":
        url = message.text.strip()
        if not url.startswith("http"):
            bot.send_message(message.chat.id, "لینک باید با http شروع شود.")
            return
        if uid not in user_buttons:
            user_buttons[uid] = []
        user_buttons[uid].append({"text": step_data["text"], "url": url})
        bot.send_message(message.chat.id, f"✅ دکمه اضافه شد. تعداد: {len(user_buttons[uid])}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ---------- ارسال لحظه‌ای ----------
    if step == "send_now":
        active = get_user_active_channel(uid)
        if not active:
            bot.send_message(message.chat.id, "کانال فعال انتخاب کنید.", reply_markup=main_menu(uid))
            bot.user_steps[uid] = {}
            return
        try:
            buttons = build_markup(uid)
            ctype = message.content_type
            if ctype == "text":
                send_to_channel(active[0], "text", text=message.text, buttons=buttons)
            elif ctype == "photo":
                send_to_channel(active[0], "photo", file_id=message.photo[-1].file_id, caption=message.caption, buttons=buttons)
            elif ctype == "video":
                send_to_channel(active[0], "video", file_id=message.video.file_id, caption=message.caption, buttons=buttons)
            elif ctype == "animation":
                send_to_channel(active[0], "animation", file_id=message.animation.file_id, caption=message.caption, buttons=buttons)
            elif ctype == "voice":
                send_to_channel(active[0], "voice", file_id=message.voice.file_id, caption=message.caption, buttons=buttons)
            elif ctype == "sticker":
                send_to_channel(active[0], "sticker", file_id=message.sticker.file_id, buttons=buttons)
            elif ctype == "document":
                send_to_channel(active[0], "document", file_id=message.document.file_id, caption=message.caption, buttons=buttons)
            bot.send_message(message.chat.id, "✅ ارسال شد.", reply_markup=main_menu(uid))
            log_action(uid, "send_now", ctype)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا: {e}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ---------- پیش‌نمایش ----------
    if step == "preview_post":
        try:
            buttons = build_markup(uid)
            ctype = message.content_type
            # ارسال پیش‌نمایش به خود کاربر
            if ctype == "text":
                bot.send_message(message.chat.id, message.text, reply_markup=buttons, parse_mode="Markdown")
            elif ctype == "photo":
                bot.send_photo(message.chat.id, message.photo[-1].file_id, caption=message.caption, reply_markup=buttons)
            elif ctype == "video":
                bot.send_video(message.chat.id, message.video.file_id, caption=message.caption, reply_markup=buttons)
            else:
                bot.send_message(message.chat.id, "این نوع محتوا برای پیش‌نمایش پشتیبانی می‌شود (متن/عکس/ویدیو).")
            
            m = InlineKeyboardMarkup()
            m.add(InlineKeyboardButton("✅ تأیید و ارسال به کانال", callback_data="confirm_preview"))
            m.add(InlineKeyboardButton("❌ انصراف", callback_data="back_main"))
            bot.send_message(message.chat.id, "پیش‌نمایش بالا را ببینید. تأیید می‌کنید؟", reply_markup=m)
            
            # ذخیره موقت برای ارسال بعدی
            bot.user_steps[uid] = {
                "step": "confirm_preview",
                "ctype": ctype,
                "file_id": message.photo[-1].file_id if ctype == "photo" else (message.video.file_id if ctype == "video" else None),
                "text": message.text if ctype == "text" else None,
                "caption": message.caption
            }
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا: {e}", reply_markup=main_menu(uid))
            bot.user_steps[uid] = {}
        return

    # ---------- زمان‌بندی ----------
    if step == "schedule_content":
        temp = {"ctype": message.content_type, "file_id": None, "text": None, "caption": message.caption}
        if message.content_type == "text":
            temp["text"] = message.text
        elif message.content_type == "photo":
            temp["file_id"] = message.photo[-1].file_id
        elif message.content_type == "video":
            temp["file_id"] = message.video.file_id
        elif message.content_type == "animation":
            temp["file_id"] = message.animation.file_id
        elif message.content_type == "document":
            temp["file_id"] = message.document.file_id
        bot.user_steps[uid] = {"step": "schedule_time", "temp": temp}
        bot.send_message(message.chat.id, "ساعت ارسال را بفرستید (مثال: 18:30 یا 2026-08-12 18:30):")
        return

    if step == "schedule_time":
        try:
            time_text = message.text.strip()
            now = now_tehran()
            if len(time_text) <= 5:
                h, m = map(int, time_text.split(":"))
                send_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if send_time <= now:
                    send_time += timedelta(days=1)
            else:
                send_time = datetime.strptime(time_text, "%Y-%m-%d %H:%M")

            active = get_user_active_channel(uid)
            temp = step_data["temp"]
            buttons_json = json.dumps(user_buttons.get(uid, []))

            conn = get_db()
            c = conn.cursor()
            c.execute('''INSERT INTO scheduled_posts 
                (user_id, channel_id, content_type, file_id, text_content, caption, buttons, send_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (uid, active[0], temp["ctype"], temp.get("file_id"), temp.get("text"), temp.get("caption"),
                 buttons_json, send_time.strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            sid = c.lastrowid
            conn.close()
            bot.send_message(message.chat.id, f"✅ زمان‌بندی شد (#{sid})\nزمان: {send_time.strftime('%Y-%m-%d %H:%M')}", reply_markup=main_menu(uid))
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا: {e}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ---------- پین و حذف ----------
    if step == "pin":
        active = get_user_active_channel(uid)
        try:
            bot.pin_chat_message(active[0], int(message.text.strip()))
            bot.send_message(message.chat.id, "✅ پین شد.", reply_markup=main_menu(uid))
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا: {e}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    if step == "delete":
        active = get_user_active_channel(uid)
        try:
            bot.delete_message(active[0], int(message.text.strip()))
            bot.send_message(message.chat.id, "✅ حذف شد.", reply_markup=main_menu(uid))
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا: {e}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ---------- تنظیمات ادمین ----------
    if step == "set_premium_price" and is_main_admin(uid):
        try:
            price = int(message.text.strip())
            set_setting("premium_price", str(price))
            bot.send_message(message.chat.id, f"✅ قیمت پرمیوم به {price} استارز تغییر کرد.", reply_markup=main_menu(uid))
        except:
            bot.send_message(message.chat.id, "عدد معتبر بفرستید.")
        bot.user_steps[uid] = {}
        return

    if step == "add_forced" and is_main_admin(uid):
        ch = message.text.strip()
        try:
            chat = bot.get_chat(ch)
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO forced_channels (channel_id, channel_title) VALUES (?, ?)", (str(chat.id), chat.title))
            conn.commit()
            conn.close()
            bot.send_message(message.chat.id, f"✅ کانال قفل اضافه شد: {chat.title}", reply_markup=main_menu(uid))
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا: {e}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # پیش‌فرض
    bot.send_message(message.chat.id, "از منو استفاده کنید:", reply_markup=main_menu(uid))

print("✅ بخش ۳ آماده شد")
# ==================== بخش ۴ از ۴ ====================
# پرداخت + تأیید پیش‌نمایش + زمان‌بند + اجرا نهایی

# ---------- پیش‌پرداخت ----------
@bot.pre_checkout_query_handler(func=lambda q: True)
def pre_checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# ---------- پرداخت موفق ----------
@bot.message_handler(content_types=['successful_payment'])
def successful_payment(message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    uid = message.from_user.id
    amount = payment.total_amount

    if payload.startswith("premium_"):
        days = int(get_setting("premium_days", "30"))
        until = (now_tehran() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
        
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET is_premium=1, premium_until=?, max_channels=999 WHERE user_id=?", (until, uid))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, 
            f"✅ **پرمیوم فعال شد!**\n\nمدت: {days} روز\nتا تاریخ: {until}\nحالا می‌توانید کانال نامحدود اضافه کنید.",
            parse_mode="Markdown", reply_markup=main_menu(uid))
        log_action(uid, "premium_activated", f"days={days}")
        
        for admin in ADMIN_IDS:
            try:
                bot.send_message(admin, f"⭐ کاربر `{uid}` پرمیوم خرید\nمبلغ: {amount} استارز", parse_mode="Markdown")
            except:
                pass
    else:
        bot.send_message(message.chat.id, f"✅ پرداخت {amount} استارز با موفقیت انجام شد.", reply_markup=main_menu(uid))
        log_action(uid, "payment", f"amount={amount}")

# ---------- تأیید پیش‌نمایش و ارسال ----------
@bot.callback_query_handler(func=lambda call: call.data == "confirm_preview")
def confirm_preview(call):
    uid = call.from_user.id
    bot.user_steps = getattr(bot, "user_steps", {})
    data = bot.user_steps.get(uid, {})
    
    if data.get("step") != "confirm_preview":
        bot.answer_callback_query(call.id, "منقضی شده", show_alert=True)
        return
    
    active = get_user_active_channel(uid)
    if not active:
        bot.answer_callback_query(call.id, "کانال فعال نیست", show_alert=True)
        return
    
    try:
        buttons = build_markup(uid)
        ctype = data.get("ctype")
        if ctype == "text":
            send_to_channel(active[0], "text", text=data.get("text"), buttons=buttons)
        elif ctype == "photo":
            send_to_channel(active[0], "photo", file_id=data.get("file_id"), caption=data.get("caption"), buttons=buttons)
        elif ctype == "video":
            send_to_channel(active[0], "video", file_id=data.get("file_id"), caption=data.get("caption"), buttons=buttons)
        
        bot.edit_message_text("✅ پست با موفقیت به کانال ارسال شد.", call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))
        log_action(uid, "preview_sent", ctype)
    except Exception as e:
        bot.edit_message_text(f"❌ خطا در ارسال: {e}", call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))
    
    bot.user_steps[uid] = {}
    bot.answer_callback_query(call.id)

# ---------- مدیریت زمان‌بندی ادمین ----------
@bot.callback_query_handler(func=lambda call: call.data == "admin_sched" or call.data.startswith("cancel_sch_"))
def admin_sched_handler(call):
    uid = call.from_user.id
    if not is_main_admin(uid):
        return

    if call.data == "admin_sched":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, user_id, content_type, send_time FROM scheduled_posts WHERE status='pending' ORDER BY send_time LIMIT 15")
        rows = c.fetchall()
        conn.close()

        if not rows:
            bot.send_message(call.message.chat.id, "هیچ پست زمان‌بندی‌شده‌ای وجود ندارد.")
            return

        text = "📅 **پست‌های در انتظار:**\n\n"
        m = InlineKeyboardMarkup(row_width=1)
        for r in rows:
            text += f"#{r[0]} | کاربر `{r[1]}` | {r[2]} | {r[3]}\n"
            m.add(InlineKeyboardButton(f"❌ لغو #{r[0]}", callback_data=f"cancel_sch_{r[0]}"))
        m.add(InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel"))
        bot.send_message(call.message.chat.id, text, reply_markup=m, parse_mode="Markdown")

    elif call.data.startswith("cancel_sch_"):
        sid = int(call.data.split("_")[2])
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE scheduled_posts SET status='canceled' WHERE id=?", (sid,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, f"پست #{sid} لغو شد", show_alert=True)

# ---------- ترد زمان‌بندی ----------
def scheduler_worker():
    print("⏰ سیستم زمان‌بندی نسخه ۳ فعال شد (وقت ایران)...")
    while True:
        try:
            conn = get_db()
            c = conn.cursor()
            now_str = now_tehran().strftime("%Y-%m-%d %H:%M:%S")
            c.execute("SELECT * FROM scheduled_posts WHERE status='pending' AND send_time <= ?", (now_str,))
            rows = c.fetchall()

            for row in rows:
                try:
                    # id, user_id, channel_id, content_type, file_id, text_content, caption, buttons, send_time, status
                    buttons_list = json.loads(row[7]) if row[7] else []
                    markup = None
                    if buttons_list:
                        markup = InlineKeyboardMarkup(row_width=2)
                        btns = [InlineKeyboardButton(b["text"], url=b["url"]) for b in buttons_list]
                        markup.add(*btns)

                    send_to_channel(
                        channel=row[2],
                        content_type=row[3],
                        file_id=row[4],
                        text=row[5],
                        caption=row[6],
                        buttons=markup
                    )
                    c.execute("UPDATE scheduled_posts SET status='sent' WHERE id=?", (row[0],))
                    conn.commit()
                    print(f"✅ پست زمان‌بندی #{row[0]} ارسال شد")
                    log_action(row[1], "scheduled_sent", str(row[0]))
                except Exception as e:
                    print(f"❌ خطا در #{row[0]}: {e}")
                    c.execute("UPDATE scheduled_posts SET status='error' WHERE id=?", (row[0],))
                    conn.commit()
            conn.close()
        except Exception as e:
            print("Scheduler Error:", e)
        time.sleep(20)

# ---------- اجرا ----------
threading.Thread(target=scheduler_worker, daemon=True).start()

print("🤖 ربات Nova نسخه ۳ با موفقیت روشن شد")
print("قابلیت‌های فعال:")
print("- مدیریت چند کانال + پرمیوم")
print("- قفل کانال چندتایی")
print("- پست آزمایشی (Preview)")
print("- زمان‌بندی با وقت ایران")
print("- آنالیز + دکمه‌های شیشه‌ای")
print("- پنل ادمین کامل")
bot.infinity_polling()
