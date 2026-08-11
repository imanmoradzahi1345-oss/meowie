# ==================== بخش ۱ از ۴ ====================
# تنظیمات + دیتابیس پیشرفته + توابع پایه + منوها

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
import sqlite3
import threading
import time
import json
import re
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
    TEHRAN = ZoneInfo("Asia/Tehran")
except:
    TEHRAN = None

BOT_TOKEN = "8924668463:AAH7rV1LMZZ6Amn3JEQV6SRHeEM9KwI6lgA"
ADMIN_IDS = [7530457395]

bot = telebot.TeleBot(BOT_TOKEN)

# ----------------- دیتابیس -----------------
def init_db():
    conn = sqlite3.connect("nova_advanced.db")
    c = conn.cursor()

    # کاربران
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        is_vip INTEGER DEFAULT 0,
        max_channels INTEGER DEFAULT 3,
        joined_at TEXT,
        last_active TEXT
    )''')

    # کانال‌های هر کاربر
    c.execute('''CREATE TABLE IF NOT EXISTS user_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        channel_id TEXT,
        channel_title TEXT,
        is_active INTEGER DEFAULT 0,
        UNIQUE(user_id, channel_id)
    )''')

    # تنظیمات کلی
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

    # پست‌های زمان‌بندی‌شده
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

    # قالب‌ها
    c.execute('''CREATE TABLE IF NOT EXISTS templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        content TEXT
    )''')

    # لاگ‌ها
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        details TEXT,
        created_at TEXT
    )''')

    # تنظیمات پیش‌فرض
    defaults = {
        "max_channels_default": "3",
        "forced_join_channel": "",
        "forced_join_enabled": "0",
        "footer_global": ""
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect("nova_advanced.db")

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
        max_ch = int(get_setting("max_channels_default", "3"))
        c.execute("INSERT INTO users (user_id, username, full_name, max_channels, joined_at, last_active) VALUES (?, ?, ?, ?, ?, ?)",
                  (user.id, user.username or "", user.full_name or "", max_ch,
                   now_tehran().strftime("%Y-%m-%d %H:%M"), now_tehran().strftime("%Y-%m-%d %H:%M")))
    else:
        c.execute("UPDATE users SET username=?, full_name=?, last_active=? WHERE user_id=?",
                  (user.username or "", user.full_name or "", now_tehran().strftime("%Y-%m-%d %H:%M"), user.id))
    conn.commit()
    conn.close()

def get_user_active_channel(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT channel_id, channel_title FROM user_channels WHERE user_id=? AND is_active=1", (user_id,))
    row = c.fetchone()
    conn.close()
    return row  # (channel_id, title) or None

def get_user_channels(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT channel_id, channel_title, is_active FROM user_channels WHERE user_id=?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def log_action(user_id, action, details=""):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO logs (user_id, action, details, created_at) VALUES (?, ?, ?, ?)",
              (user_id, action, details, now_tehran().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

# دکمه‌های موقت هر کاربر
user_buttons = {}  # {user_id: [{"text": "", "url": ""}]}

def build_markup(user_id):
    buttons = user_buttons.get(user_id, [])
    if not buttons:
        return None
    markup = InlineKeyboardMarkup(row_width=2)  # چندردیفه
    btns = [InlineKeyboardButton(b["text"], url=b["url"]) for b in buttons]
    markup.add(*btns)
    return markup

# ----------------- منوهای اصلی -----------------
def main_menu(user_id):
    active = get_user_active_channel(user_id)
    active_text = active[1] if active else "هیچ کانالی انتخاب نشده"

    m = InlineKeyboardMarkup(row_width=2)
    m.add(InlineKeyboardButton(f"📢 کانال فعال: {active_text[:20]}", callback_data="my_channels"))
    m.add(
        InlineKeyboardButton("📤 ارسال لحظه‌ای", callback_data="send_now"),
        InlineKeyboardButton("⏰ زمان‌بندی", callback_data="schedule_post"),
    )
    m.add(
        InlineKeyboardButton("🔘 دکمه‌های شیشه‌ای", callback_data="buttons_menu"),
        InlineKeyboardButton("📊 آنالیز کانال", callback_data="analyze_channel"),
    )
    m.add(
        InlineKeyboardButton("📌 پین پست", callback_data="pin_post"),
        InlineKeyboardButton("🗑 حذف پست", callback_data="delete_post"),
    )
    m.add(
        InlineKeyboardButton("📝 قالب‌ها", callback_data="templates_menu"),
        InlineKeyboardButton("✍️ امضا", callback_data="set_footer"),
    )
    m.add(
        InlineKeyboardButton("📋 کپی از کانال دیگر", callback_data="copy_post"),
        InlineKeyboardButton("⭐ پرداخت استارز", callback_data="payment"),
    )
    if is_main_admin(user_id):
        m.add(InlineKeyboardButton("👑 پنل ادمین اصلی", callback_data="admin_panel"))
    return m

def channels_menu(user_id):
    channels = get_user_channels(user_id)
    m = InlineKeyboardMarkup(row_width=1)
    for ch_id, title, is_active in channels:
        status = "✅" if is_active else ""
        m.add(InlineKeyboardButton(f"{status} {title or ch_id}", callback_data=f"select_channel_{ch_id}"))
    m.add(InlineKeyboardButton("➕ اضافه کردن کانال جدید", callback_data="add_channel"))
    m.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
    return m

print("✅ بخش ۱ آماده است")
# ==================== بخش ۲ از ۴ ====================
# کال‌بک‌ها + پنل کاربر + پنل ادمین + جواب بحث

@bot.message_handler(commands=['start'])
def start(message):
    ensure_user(message.from_user)
    
    # بررسی قفل کانال (Forced Join)
    forced_enabled = get_setting("forced_join_enabled") == "1"
    forced_channel = get_setting("forced_join_channel")
    
    if forced_enabled and forced_channel and not is_main_admin(message.from_user.id):
        try:
            member = bot.get_chat_member(forced_channel, message.from_user.id)
            if member.status in ["left", "kicked"]:
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{forced_channel.replace('@','')}"))
                markup.add(InlineKeyboardButton("✅ عضو شدم، بررسی کن", callback_data="check_forced_join"))
                bot.send_message(message.chat.id, 
                    "🔒 برای استفاده از ربات باید در کانال زیر عضو شوید:", 
                    reply_markup=markup)
                return
        except:
            pass

    bot.send_message(message.chat.id, 
        f"سلام {message.from_user.first_name}!\n\n🤖 به ربات پیشرفته مدیریت کانال خوش آمدید.",
        reply_markup=main_menu(message.from_user.id))

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    uid = call.from_user.id
    ensure_user(call.from_user)
    data = call.data
    bot.user_steps = getattr(bot, "user_steps", {})

    # ---------- بازگشت ----------
    if data == "back_main":
        bot.edit_message_text("منوی اصلی:", call.message.chat.id, call.message.message_id, 
                              reply_markup=main_menu(uid))

    # ---------- بررسی عضویت اجباری ----------
    elif data == "check_forced_join":
        forced_channel = get_setting("forced_join_channel")
        try:
            member = bot.get_chat_member(forced_channel, uid)
            if member.status not in ["left", "kicked"]:
                bot.edit_message_text("✅ عضویت تأیید شد. خوش آمدید!", call.message.chat.id, call.message.message_id,
                                      reply_markup=main_menu(uid))
            else:
                bot.answer_callback_query(call.id, "هنوز عضو نشدی!", show_alert=True)
        except Exception as e:
            bot.answer_callback_query(call.id, f"خطا: {e}", show_alert=True)

    # ---------- مدیریت کانال‌های کاربر ----------
    elif data == "my_channels":
        bot.edit_message_text("📢 کانال‌های شما:", call.message.chat.id, call.message.message_id,
                              reply_markup=channels_menu(uid))

    elif data == "add_channel":
        bot.user_steps[uid] = {"step": "waiting_channel_id"}
        bot.edit_message_text(
            "آیدی کانالی که **ادمین** آن هستید را بفرستید:\nمثال: `@mychannel` یا `-100xxxxxxxxxx`",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif data.startswith("select_channel_"):
        ch_id = data.replace("select_channel_", "")
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE user_channels SET is_active=0 WHERE user_id=?", (uid,))
        c.execute("UPDATE user_channels SET is_active=1 WHERE user_id=? AND channel_id=?", (uid, ch_id))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "✅ کانال فعال شد", show_alert=True)
        bot.edit_message_text("منوی اصلی:", call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))

    # ---------- ارسال لحظه‌ای ----------
    elif data == "send_now":
        active = get_user_active_channel(uid)
        if not active:
            bot.answer_callback_query(call.id, "اول یک کانال فعال انتخاب کنید", show_alert=True)
            return
        bot.user_steps[uid] = {"step": "waiting_content_now"}
        bot.edit_message_text(
            "📤 محتوا را بفرستید (متن، عکس+کپشن، ویدیو، گیف، ویس، استیکر، فایل).\nربات خودکار در کانال فعال ارسال می‌کند.",
            call.message.chat.id, call.message.message_id)

    # ---------- زمان‌بندی ----------
    elif data == "schedule_post":
        active = get_user_active_channel(uid)
        if not active:
            bot.answer_callback_query(call.id, "اول یک کانال فعال انتخاب کنید", show_alert=True)
            return
        bot.user_steps[uid] = {"step": "waiting_content_sch"}
        now = now_tehran().strftime("%H:%M")
        bot.edit_message_text(
            f"⏰ محتوا را بفرستید.\nساعت فعلی ایران: `{now}`\nبعد از ارسال محتوا، ساعت ارسال را مشخص می‌کنیم.",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    # ---------- دکمه‌های شیشه‌ای ----------
    elif data == "buttons_menu":
        m = InlineKeyboardMarkup(row_width=1)
        m.add(
            InlineKeyboardButton("➕ اضافه کردن دکمه", callback_data="add_button"),
            InlineKeyboardButton("👁 مشاهده دکمه‌ها", callback_data="view_buttons"),
            InlineKeyboardButton("🧹 پاک کردن همه", callback_data="clear_buttons"),
            InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"),
        )
        bot.edit_message_text("🔘 مدیریت دکمه‌های شیشه‌ای:", call.message.chat.id, call.message.message_id, reply_markup=m)

    elif data == "add_button":
        bot.user_steps[uid] = {"step": "waiting_btn_text"}
        bot.edit_message_text("متن دکمه را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "view_buttons":
        btns = user_buttons.get(uid, [])
        if not btns:
            text = "هیچ دکمه‌ای وجود ندارد."
        else:
            text = "دکمه‌های فعلی:\n\n"
            for i, b in enumerate(btns, 1):
                text += f"{i}. {b['text']}\n{b['url']}\n\n"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔙 بازگشت", callback_data="buttons_menu")))

    elif data == "clear_buttons":
        user_buttons[uid] = []
        bot.answer_callback_query(call.id, "دکمه‌ها پاک شدند", show_alert=True)

    # ---------- آنالیز کانال ----------
    elif data == "analyze_channel":
        active = get_user_active_channel(uid)
        if not active:
            bot.answer_callback_query(call.id, "اول کانال فعال انتخاب کنید", show_alert=True)
            return
        try:
            chat = bot.get_chat(active[0])
            members = bot.get_chat_member_count(active[0])
            admins = bot.get_chat_administrators(active[0])
            admin_count = len(admins)
            
            text = f"""
📊 **آنالیز کانال**

📌 نام: {chat.title}
🆔 آیدی: `{chat.id}`
👥 تعداد اعضا: **{members:,}**
👑 تعداد ادمین: **{admin_count}**
📝 توضیحات: {chat.description or 'ندارد'}
🔗 یوزرنیم: @{chat.username if chat.username else 'خصوصی'}

وضعیت کلی: {'عالی' if members > 1000 else 'در حال رشد' if members > 100 else 'نوپا'}
"""
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                  reply_markup=main_menu(uid), parse_mode="Markdown")
        except Exception as e:
            bot.answer_callback_query(call.id, f"خطا: {e}", show_alert=True)

    # ---------- پین و حذف ----------
    elif data == "pin_post":
        bot.user_steps[uid] = {"step": "pin_msgid"}
        bot.edit_message_text("آیدی پست را برای پین بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "delete_post":
        bot.user_steps[uid] = {"step": "delete_msgid"}
        bot.edit_message_text("آیدی پست را برای حذف بفرستید:", call.message.chat.id, call.message.message_id)

    # ---------- کپی از کانال دیگر ----------
    elif data == "copy_post":
        bot.user_steps[uid] = {"step": "waiting_copy_link"}
        bot.edit_message_text("لینک پست مورد نظر را از کانال دیگر بفرستید:\nمثال: https://t.me/channel/123",
                              call.message.chat.id, call.message.message_id)

    # ---------- جواب بحث (Discussion) ----------
    elif data == "reply_discussion":
        active = get_user_active_channel(uid)
        if not active:
            bot.answer_callback_query(call.id, "اول کانال فعال انتخاب کنید", show_alert=True)
            return
        bot.user_steps[uid] = {"step": "waiting_discussion_reply"}
        bot.edit_message_text(
            "💬 قابلیت جواب به بحث کانال\n\n"
            "اگر کانال شما گروه بحث (Discussion) فعال دارد، پیام خود را بفرستید تا در گروه بحث ارسال شود.\n"
            "(ربات باید در گروه بحث هم ادمین باشد)",
            call.message.chat.id, call.message.message_id)

    # ---------- پرداخت ----------
    elif data == "payment":
        bot.user_steps[uid] = {"step": "waiting_stars"}
        bot.edit_message_text("تعداد استارز را وارد کنید (مثال: ۵۰):", call.message.chat.id, call.message.message_id)

    # ---------- پنل ادمین اصلی ----------
    elif data == "admin_panel" and is_main_admin(uid):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        conn.close()
        
        m = InlineKeyboardMarkup(row_width=1)
        m.add(
            InlineKeyboardButton(f"👥 تعداد کاربران: {total_users}", callback_data="admin_users"),
            InlineKeyboardButton("📋 لیست کاربران + یوزرنیم", callback_data="admin_user_list"),
            InlineKeyboardButton("⚙️ تنظیم حداکثر کانال", callback_data="admin_set_max_channels"),
            InlineKeyboardButton("🔒 تنظیم قفل کانال", callback_data="admin_forced_join"),
            InlineKeyboardButton("📅 مدیریت زمان‌بندی‌ها", callback_data="admin_scheduled"),
            InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"),
        )
        bot.edit_message_text("👑 پنل ادمین اصلی:", call.message.chat.id, call.message.message_id, reply_markup=m)

    elif data == "admin_user_list" and is_main_admin(uid):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id, username, full_name, max_channels FROM users ORDER BY last_active DESC LIMIT 30")
        rows = c.fetchall()
        conn.close()
        text = "👥 **لیست کاربران:**\n\n"
        for r in rows:
            uname = f"@{r[1]}" if r[1] else "بدون یوزرنیم"
            text += f"`{r[0]}` | {uname} | {r[2] or '-'} | سقف کانال: {r[3]}\n"
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

    elif data == "admin_set_max_channels" and is_main_admin(uid):
        bot.user_steps[uid] = {"step": "admin_max_channels"}
        bot.edit_message_text("حداکثر تعداد کانال برای کاربران را وارد کنید (عدد):", call.message.chat.id, call.message.message_id)

    elif data == "admin_forced_join" and is_main_admin(uid):
        bot.user_steps[uid] = {"step": "admin_forced_channel"}
        current = get_setting("forced_join_channel") or "تنظیم نشده"
        bot.edit_message_text(f"کانال قفل فعلی: `{current}`\n\nآیدی کانال جدید را بفرستید (یا `off` برای خاموش کردن):",
                              call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    bot.answer_callback_query(call.id)

print("✅ بخش ۲ آماده است")
# ==================== بخش ۳ از ۴ ====================
# هندلر پیام‌ها + ارسال + زمان‌بندی + کپی پست + جواب بحث

def send_to_channel(channel, content_type, file_id=None, text=None, caption=None, buttons=None, user_id=None):
    # اضافه کردن امضا اگر وجود داشته باشد
    footer = get_setting("footer_global")
    if footer:
        if caption:
            caption = f"{caption}\n\n{footer}"
        elif text:
            text = f"{text}\n\n{footer}"
        elif content_type in ["photo", "video", "animation", "document"]:
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
def handle_messages(message):
    uid = message.from_user.id
    ensure_user(message.from_user)
    
    bot.user_steps = getattr(bot, "user_steps", {})
    step_data = bot.user_steps.get(uid, {})
    step = step_data.get("step")

    # ---------- اضافه کردن کانال ----------
    if step == "waiting_channel_id":
        ch = message.text.strip()
        try:
            # چک کردن اینکه کاربر ادمین کانال باشد
            member = bot.get_chat_member(ch, uid)
            if member.status not in ["administrator", "creator"]:
                bot.send_message(message.chat.id, "❌ شما ادمین این کانال نیستید.", reply_markup=main_menu(uid))
                bot.user_steps[uid] = {}
                return
            
            chat = bot.get_chat(ch)
            title = chat.title or ch
            
            # چک سقف تعداد کانال
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT max_channels FROM users WHERE user_id=?", (uid,))
            max_ch = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM user_channels WHERE user_id=?", (uid,))
            current = c.fetchone()[0]
            
            if current >= max_ch:
                bot.send_message(message.chat.id, f"❌ سقف تعداد کانال شما ({max_ch}) پر شده است.", reply_markup=main_menu(uid))
                conn.close()
                bot.user_steps[uid] = {}
                return
            
            c.execute("INSERT OR IGNORE INTO user_channels (user_id, channel_id, channel_title, is_active) VALUES (?, ?, ?, 0)",
                      (uid, str(chat.id), title))
            conn.commit()
            conn.close()
            
            bot.send_message(message.chat.id, f"✅ کانال «{title}» اضافه شد.", reply_markup=main_menu(uid))
            log_action(uid, "add_channel", title)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا: {e}\nمطمئن شوید ربات و شما ادمین کانال هستید.", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ---------- اضافه کردن دکمه (متن) ----------
    if step == "waiting_btn_text":
        bot.user_steps[uid] = {"step": "waiting_btn_url", "btn_text": message.text.strip()}
        bot.send_message(message.chat.id, "حالا لینک دکمه را بفرستید (با https:// شروع شود):")
        return

    # ---------- اضافه کردن دکمه (لینک) ----------
    if step == "waiting_btn_url":
        url = message.text.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            bot.send_message(message.chat.id, "❌ لینک معتبر نیست. دوباره بفرستید.")
            return
        if uid not in user_buttons:
            user_buttons[uid] = []
        user_buttons[uid].append({"text": step_data["btn_text"], "url": url})
        bot.send_message(message.chat.id, f"✅ دکمه اضافه شد.\nتعداد دکمه‌ها: {len(user_buttons[uid])}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ---------- ارسال لحظه‌ای ----------
    if step == "waiting_content_now":
        active = get_user_active_channel(uid)
        if not active:
            bot.send_message(message.chat.id, "کانال فعالی انتخاب نشده.", reply_markup=main_menu(uid))
            bot.user_steps[uid] = {}
            return
        try:
            buttons = build_markup(uid)
            ctype = message.content_type
            
            if ctype == "text":
                send_to_channel(active[0], "text", text=message.text, buttons=buttons, user_id=uid)
            elif ctype == "photo":
                send_to_channel(active[0], "photo", file_id=message.photo[-1].file_id, caption=message.caption, buttons=buttons, user_id=uid)
            elif ctype == "video":
                send_to_channel(active[0], "video", file_id=message.video.file_id, caption=message.caption, buttons=buttons, user_id=uid)
            elif ctype == "animation":
                send_to_channel(active[0], "animation", file_id=message.animation.file_id, caption=message.caption, buttons=buttons, user_id=uid)
            elif ctype == "voice":
                send_to_channel(active[0], "voice", file_id=message.voice.file_id, caption=message.caption, buttons=buttons, user_id=uid)
            elif ctype == "sticker":
                send_to_channel(active[0], "sticker", file_id=message.sticker.file_id, buttons=buttons, user_id=uid)
            elif ctype == "document":
                send_to_channel(active[0], "document", file_id=message.document.file_id, caption=message.caption, buttons=buttons, user_id=uid)
            
            bot.send_message(message.chat.id, "✅ پست با موفقیت ارسال شد.", reply_markup=main_menu(uid))
            log_action(uid, "send_now", ctype)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا در ارسال:\n{e}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ---------- شروع زمان‌بندی ----------
    if step == "waiting_content_sch":
        temp = {
            "content_type": message.content_type,
            "file_id": None,
            "text": None,
            "caption": message.caption
        }
        if message.content_type == "text":
            temp["text"] = message.text
        elif message.content_type == "photo":
            temp["file_id"] = message.photo[-1].file_id
        elif message.content_type == "video":
            temp["file_id"] = message.video.file_id
        elif message.content_type == "animation":
            temp["file_id"] = message.animation.file_id
        elif message.content_type == "voice":
            temp["file_id"] = message.voice.file_id
        elif message.content_type == "sticker":
            temp["file_id"] = message.sticker.file_id
        elif message.content_type == "document":
            temp["file_id"] = message.document.file_id

        bot.user_steps[uid] = {"step": "waiting_schedule_time", "temp": temp}
        now = now_tehran().strftime("%H:%M")
        bot.send_message(message.chat.id, 
            f"ساعت فعلی ایران: `{now}`\n\nساعت ارسال را بفرستید:\n`18:30` یا `2026-08-12 18:30`",
            parse_mode="Markdown")
        return

    # ---------- ساعت زمان‌بندی ----------
    if step == "waiting_schedule_time":
        try:
            time_text = message.text.strip()
            now = now_tehran()
            if len(time_text) <= 5:
                hour, minute = map(int, time_text.split(":"))
                send_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if send_time <= now:
                    send_time += timedelta(days=1)
            else:
                send_time = datetime.strptime(time_text, "%Y-%m-%d %H:%M")
                if TEHRAN:
                    send_time = send_time.replace(tzinfo=TEHRAN)

            active = get_user_active_channel(uid)
            temp = step_data["temp"]
            buttons_json = json.dumps(user_buttons.get(uid, []))

            conn = get_db()
            c = conn.cursor()
            c.execute('''INSERT INTO scheduled_posts 
                (user_id, channel_id, content_type, file_id, text_content, caption, buttons, send_time, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')''',
                (uid, active[0], temp["content_type"], temp.get("file_id"), temp.get("text"),
                 temp.get("caption"), buttons_json, send_time.strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            sid = c.lastrowid
            conn.close()

            bot.send_message(message.chat.id, 
                f"✅ زمان‌بندی شد\nشماره: #{sid}\nزمان: {send_time.strftime('%Y-%m-%d %H:%M')} (ایران)",
                reply_markup=main_menu(uid))
            log_action(uid, "schedule", str(sid))
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا: {e}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ---------- پین ----------
    if step == "pin_msgid":
        active = get_user_active_channel(uid)
        try:
            msg_id = int(message.text.strip())
            bot.pin_chat_message(active[0], msg_id)
            bot.send_message(message.chat.id, "✅ پین شد.", reply_markup=main_menu(uid))
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا: {e}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ---------- حذف ----------
    if step == "delete_msgid":
        active = get_user_active_channel(uid)
        try:
            msg_id = int(message.text.strip())
            bot.delete_message(active[0], msg_id)
            bot.send_message(message.chat.id, "✅ حذف شد.", reply_markup=main_menu(uid))
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا: {e}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ---------- کپی پست ----------
    if step == "waiting_copy_link":
        link = message.text.strip()
        # استخراج از لینک t.me/channel/123
        match = re.search(r't\.me/([^/]+)/(\d+)', link)
        if not match:
            bot.send_message(message.chat.id, "❌ لینک معتبر نیست.", reply_markup=main_menu(uid))
            bot.user_steps[uid] = {}
            return
        try:
            # فعلاً پیام راهنما می‌ده (کپی کامل نیاز به forward یا get_message دارد)
            bot.send_message(message.chat.id, 
                "⚠️ برای کپی کامل محتوا، پست را برای ربات فوروارد کنید یا از ارسال لحظه‌ای استفاده کنید.\nاین بخش در حال بهبود است.",
                reply_markup=main_menu(uid))
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا: {e}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ---------- جواب بحث ----------
    if step == "waiting_discussion_reply":
        active = get_user_active_channel(uid)
        try:
            # تلاش برای ارسال به گروه بحث لینک‌شده
            chat = bot.get_chat(active[0])
            if hasattr(chat, 'linked_chat_id') and chat.linked_chat_id:
                bot.send_message(chat.linked_chat_id, message.text)
                bot.send_message(message.chat.id, "✅ پیام در گروه بحث ارسال شد.", reply_markup=main_menu(uid))
            else:
                bot.send_message(message.chat.id, "این کانال گروه بحث فعالی ندارد یا ربات دسترسی ندارد.", reply_markup=main_menu(uid))
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا: {e}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ---------- پرداخت استارز ----------
    if step == "waiting_stars":
        try:
            amount = int(message.text.strip())
            if amount < 1:
                bot.send_message(message.chat.id, "حداقل ۱ استارز")
                return
            prices = [LabeledPrice(label=f"{amount} Stars", amount=amount)]
            bot.send_invoice(
                chat_id=message.chat.id,
                title=f"پرداخت {amount} استارز",
                description="پرداخت با تلگرام استارز",
                invoice_payload=f"pay_{amount}_{uid}",
                provider_token="",
                currency="XTR",
                prices=prices
            )
        except:
            bot.send_message(message.chat.id, "فقط عدد بفرستید.")
        bot.user_steps[uid] = {}
        return

    # ---------- تنظیمات ادمین ----------
    if step == "admin_max_channels" and is_main_admin(uid):
        try:
            num = int(message.text.strip())
            set_setting("max_channels_default", str(num))
            # آپدیت کاربران فعلی
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE users SET max_channels=?", (num,))
            conn.commit()
            conn.close()
            bot.send_message(message.chat.id, f"✅ سقف کانال برای همه کاربران به {num} تغییر کرد.", reply_markup=main_menu(uid))
        except:
            bot.send_message(message.chat.id, "عدد معتبر بفرستید.")
        bot.user_steps[uid] = {}
        return

    if step == "admin_forced_channel" and is_main_admin(uid):
        text = message.text.strip()
        if text.lower() == "off":
            set_setting("forced_join_enabled", "0")
            set_setting("forced_join_channel", "")
            bot.send_message(message.chat.id, "✅ قفل کانال خاموش شد.", reply_markup=main_menu(uid))
        else:
            set_setting("forced_join_channel", text)
            set_setting("forced_join_enabled", "1")
            bot.send_message(message.chat.id, f"✅ قفل کانال فعال شد:\n{text}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # پیش‌فرض
    bot.send_message(message.chat.id, "از منو استفاده کنید:", reply_markup=main_menu(uid))

print("✅ بخش ۳ آماده است")
# ==================== بخش ۴ از ۴ ====================
# پرداخت + زمان‌بند + مدیریت زمان‌بندی ادمین + اجرا نهایی

# ---------- پیش‌پرداخت ----------
@bot.pre_checkout_query_handler(func=lambda q: True)
def pre_checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# ---------- پرداخت موفق ----------
@bot.message_handler(content_types=['successful_payment'])
def on_successful_payment(message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    amount = payment.total_amount
    uid = message.from_user.id

    bot.send_message(message.chat.id, 
        f"✅ پرداخت موفق!\nتعداد استارز: **{amount}**\nاز شما متشکریم.",
        parse_mode="Markdown", reply_markup=main_menu(uid))
    
    log_action(uid, "payment_success", f"amount={amount}")
    
    for admin in ADMIN_IDS:
        try:
            bot.send_message(admin, f"⭐ پرداخت جدید\nکاربر: `{uid}`\nمبلغ: {amount} استارز", parse_mode="Markdown")
        except:
            pass

# ---------- مدیریت زمان‌بندی در پنل ادمین ----------
@bot.callback_query_handler(func=lambda call: call.data in ["admin_scheduled"] or call.data.startswith("cancel_sch_"))
def admin_scheduled_handler(call):
    uid = call.from_user.id
    if not is_main_admin(uid):
        return

    if call.data == "admin_scheduled":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, user_id, channel_id, content_type, send_time FROM scheduled_posts WHERE status='pending' ORDER BY send_time LIMIT 20")
        rows = c.fetchall()
        conn.close()

        if not rows:
            bot.send_message(call.message.chat.id, "هیچ پست زمان‌بندی‌شده‌ای وجود ندارد.")
            return

        text = "📅 **پست‌های زمان‌بندی‌شده:**\n\n"
        m = InlineKeyboardMarkup(row_width=1)
        for r in rows:
            text += f"#{r[0]} | کاربر `{r[1]}` | {r[3]} | {r[4]}\n"
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
        log_action(uid, "admin_cancel_sch", str(sid))

# ---------- ترد زمان‌بندی ----------
def scheduler_worker():
    print("⏰ سیستم زمان‌بندی شروع به کار کرد (وقت ایران)...")
    while True:
        try:
            conn = get_db()
            c = conn.cursor()
            now_str = now_tehran().strftime("%Y-%m-%d %H:%M:%S")
            
            c.execute("SELECT * FROM scheduled_posts WHERE status='pending' AND send_time <= ?", (now_str,))
            rows = c.fetchall()
            
            for row in rows:
                try:
                    # row structure: id, user_id, channel_id, content_type, file_id, text_content, caption, buttons, send_time, status
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
                        buttons=markup,
                        user_id=row[1]
                    )
                    
                    c.execute("UPDATE scheduled_posts SET status='sent' WHERE id=?", (row[0],))
                    conn.commit()
                    print(f"✅ پست زمان‌بندی #{row[0]} ارسال شد")
                    log_action(row[1], "scheduled_sent", str(row[0]))
                    
                except Exception as e:
                    print(f"❌ خطا در پست #{row[0]}: {e}")
                    c.execute("UPDATE scheduled_posts SET status='error' WHERE id=?", (row[0],))
                    conn.commit()
            
            conn.close()
        except Exception as e:
            print("Scheduler Error:", e)
        
        time.sleep(20)

# ---------- اجرا ----------
threading.Thread(target=scheduler_worker, daemon=True).start()

print("🤖 ربات پیشرفته Nova آماده است...")
print("تمام بخش‌ها فعال شدند:")
print("- مدیریت چند کانال برای هر کاربر")
print("- ارسال لحظه‌ای + زمان‌بندی (وقت ایران)")
print("- دکمه‌های شیشه‌ای چندردیفه")
print("- آنالیز کانال")
print("- پین و حذف پست")
print("- کپی پست + جواب بحث")
print("- پرداخت استارز")
print("- قفل کانال (Forced Join)")
print("- پنل ادمین کامل")
bot.infinity_polling()
