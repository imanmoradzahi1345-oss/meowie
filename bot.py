# ==================== بخش ۱ از ۴ - نسخه ۳ اصلاح‌شده ====================
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
import sqlite3
import threading
import time
import json
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

def init_db():
    conn = sqlite3.connect("nova_v3_fixed.db")
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        is_premium INTEGER DEFAULT 0,
        premium_until TEXT,
        max_channels INTEGER DEFAULT 3,
        is_banned INTEGER DEFAULT 0,
        referral_code TEXT,
        joined_at TEXT,
        last_active TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS user_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        channel_id TEXT,
        channel_title TEXT,
        is_active INTEGER DEFAULT 0,
        UNIQUE(user_id, channel_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS forced_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT UNIQUE,
        channel_title TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

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

    c.execute('''CREATE TABLE IF NOT EXISTS premium_emojis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        emoji_id TEXT,
        title TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        details TEXT,
        created_at TEXT
    )''')

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
    return sqlite3.connect("nova_v3_fixed.db")

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
        c.execute("INSERT INTO users (user_id, username, full_name, max_channels, referral_code, joined_at, last_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (user.id, user.username or "", user.full_name or "", max_ch, code,
                   now_tehran().strftime("%Y-%m-%d %H:%M"), now_tehran().strftime("%Y-%m-%d %H:%M")))
    else:
        c.execute("UPDATE users SET username=?, full_name=?, last_active=? WHERE user_id=?",
                  (user.username or "", user.full_name or "", now_tehran().strftime("%Y-%m-%d %H:%M"), user.id))
    conn.commit()
    conn.close()

def is_premium(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT is_premium, premium_until FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    conn.close()
    if not row or not row[0]:
        return False
    if row[1]:
        try:
            if now_tehran().replace(tzinfo=None) > datetime.strptime(row[1], "%Y-%m-%d %H:%M"):
                return False
        except:
            pass
    return True

def get_active_channel(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT channel_id, channel_title FROM user_channels WHERE user_id=? AND is_active=1", (uid,))
    row = c.fetchone()
    conn.close()
    return row

def log_action(uid, action, details=""):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO logs (user_id, action, details, created_at) VALUES (?, ?, ?, ?)",
              (uid, action, details, now_tehran().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

user_buttons = {}
preview_data = {}  # برای ذخیره موقت پست آزمایشی

def build_markup(uid):
    btns = user_buttons.get(uid, [])
    if not btns:
        return None
    m = InlineKeyboardMarkup(row_width=2)
    m.add(*[InlineKeyboardButton(b["text"], url=b["url"]) for b in btns])
    return m

def main_menu(uid):
    active = get_active_channel(uid)
    active_text = (active[1][:16] + "..") if active and active[1] else "انتخاب نشده"
    m = InlineKeyboardMarkup(row_width=2)
    m.add(InlineKeyboardButton(f"📢 کانال: {active_text}", callback_data="my_channels"))
    m.add(InlineKeyboardButton("📤 ارسال لحظه‌ای", callback_data="send_now"),
          InlineKeyboardButton("👀 پست آزمایشی", callback_data="preview_post"))
    m.add(InlineKeyboardButton("⏰ زمان‌بندی", callback_data="schedule_post"),
          InlineKeyboardButton("🔘 دکمه‌ها", callback_data="buttons_menu"))
    m.add(InlineKeyboardButton("📊 آنالیز", callback_data="analyze"),
          InlineKeyboardButton("📌 پین/حذف", callback_data="pin_delete"))
    m.add(InlineKeyboardButton("⭐ پرمیوم", callback_data="buy_premium"),
          InlineKeyboardButton("😀 ایموجی پرمیوم", callback_data="premium_emoji"))
    if is_main_admin(uid):
        m.add(InlineKeyboardButton("👑 پنل ادمین", callback_data="admin_panel"))
    return m

print("✅ بخش ۱ آماده")
# ==================== بخش ۲ از ۴ ====================
# کال‌بک‌ها + پنل کاربر + پنل ادمین (با لیست کاربران کامل)

@bot.message_handler(commands=['start'])
def start(message):
    ensure_user(message.from_user)
    uid = message.from_user.id

    if get_setting("maintenance") == "1" and not is_main_admin(uid):
        bot.send_message(message.chat.id, "🛠️ ربات در حال تعمیرات است.")
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    if row and row[0] == 1:
        bot.send_message(message.chat.id, "🚫 حساب شما مسدود است.")
        conn.close()
        return

    # قفل کانال چندتایی
    c.execute("SELECT channel_id, channel_title FROM forced_channels")
    forced = c.fetchall()
    conn.close()

    if forced and not is_main_admin(uid):
        not_joined = []
        for ch_id, title in forced:
            try:
                m = bot.get_chat_member(ch_id, uid)
                if m.status in ["left", "kicked"]:
                    not_joined.append((ch_id, title))
            except:
                not_joined.append((ch_id, title))
        if not_joined:
            mk = InlineKeyboardMarkup(row_width=1)
            for ch_id, title in not_joined:
                link = f"https://t.me/{str(ch_id).replace('@','').replace('-100','')}" if not str(ch_id).startswith("http") else ch_id
                mk.add(InlineKeyboardButton(f"📢 {title or ch_id}", url=link))
            mk.add(InlineKeyboardButton("✅ عضو شدم - بررسی", callback_data="check_forced"))
            bot.send_message(message.chat.id, "🔒 باید در کانال‌های زیر عضو شوید:", reply_markup=mk)
            return

    bot.send_message(message.chat.id, f"سلام {message.from_user.first_name}!\nربات مدیریت کانال نسخه ۳", reply_markup=main_menu(uid))

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    uid = call.from_user.id
    ensure_user(call.from_user)
    data = call.data
    bot.user_steps = getattr(bot, "user_steps", {})

    if data == "back_main":
        bot.edit_message_text("منوی اصلی:", call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))

    elif data == "check_forced":
        bot.answer_callback_query(call.id)
        start(call.message)
        return

    # ----- کانال‌ها -----
    elif data == "my_channels":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT channel_id, channel_title, is_active FROM user_channels WHERE user_id=?", (uid,))
        rows = c.fetchall()
        conn.close()
        mk = InlineKeyboardMarkup(row_width=1)
        for ch_id, title, act in rows:
            mk.add(InlineKeyboardButton(f"{'✅ ' if act else ''}{title or ch_id}", callback_data=f"sel_ch_{ch_id}"))
        mk.add(InlineKeyboardButton("➕ اضافه کردن کانال", callback_data="add_channel"))
        mk.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
        bot.edit_message_text("کانال‌های شما:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "add_channel":
        bot.user_steps[uid] = {"step": "add_channel"}
        bot.edit_message_text("آیدی کانال (که ادمین آن هستید) را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data.startswith("sel_ch_"):
        ch = data.replace("sel_ch_", "")
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE user_channels SET is_active=0 WHERE user_id=?", (uid,))
        c.execute("UPDATE user_channels SET is_active=1 WHERE user_id=? AND channel_id=?", (uid, ch))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "✅ کانال فعال شد")
        bot.edit_message_text("منوی اصلی:", call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))

    # ----- ارسال -----
    elif data == "send_now":
        if not get_active_channel(uid):
            bot.answer_callback_query(call.id, "اول کانال فعال انتخاب کنید", show_alert=True)
            return
        bot.user_steps[uid] = {"step": "send_now"}
        bot.edit_message_text("هر محتوایی بفرستید (متن، عکس+کپشن، ویدیو+کپشن، گیف، استیکر، ویس، فایل):", call.message.chat.id, call.message.message_id)

    elif data == "preview_post":
        if not get_active_channel(uid):
            bot.answer_callback_query(call.id, "اول کانال فعال انتخاب کنید", show_alert=True)
            return
        bot.user_steps[uid] = {"step": "preview"}
        bot.edit_message_text("محتوا را برای پیش‌نمایش بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "confirm_send":
        # رفع مشکل تأیید پست آزمایشی
        data_p = preview_data.get(uid)
        if not data_p:
            bot.answer_callback_query(call.id, "منقضی شده، دوباره تلاش کنید", show_alert=True)
            return
        active = get_active_channel(uid)
        if not active:
            bot.answer_callback_query(call.id, "کانال فعال نیست", show_alert=True)
            return
        try:
            buttons = build_markup(uid)
            send_to_channel(active[0], data_p["ctype"], file_id=data_p.get("file_id"),
                            text=data_p.get("text"), caption=data_p.get("caption"), buttons=buttons)
            bot.edit_message_text("✅ پست با موفقیت به کانال ارسال شد.", call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))
            log_action(uid, "preview_sent", data_p["ctype"])
        except Exception as e:
            bot.edit_message_text(f"❌ خطا: {e}", call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))
        preview_data.pop(uid, None)
        bot.answer_callback_query(call.id)

    # ----- زمان‌بندی -----
    elif data == "schedule_post":
        if not get_active_channel(uid):
            bot.answer_callback_query(call.id, "اول کانال فعال انتخاب کنید", show_alert=True)
            return
        bot.user_steps[uid] = {"step": "sch_content"}
        bot.edit_message_text(f"محتوا را بفرستید.\nساعت فعلی ایران: `{now_tehran().strftime('%H:%M')}`", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    # ----- دکمه‌ها -----
    elif data == "buttons_menu":
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(InlineKeyboardButton("➕ اضافه کردن دکمه", callback_data="add_btn"),
               InlineKeyboardButton("👁 مشاهده دکمه‌ها", callback_data="view_btn"),
               InlineKeyboardButton("🧹 پاک کردن همه", callback_data="clear_btn"),
               InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
        bot.edit_message_text("مدیریت دکمه‌های شیشه‌ای:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "add_btn":
        bot.user_steps[uid] = {"step": "btn_text"}
        bot.edit_message_text("متن دکمه را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "view_btn":
        btns = user_buttons.get(uid, [])
        text = "دکمه‌های فعلی:\n\n" + "\n".join([f"{i+1}. {b['text']}\n{b['url']}" for i,b in enumerate(btns)]) if btns else "هیچ دکمه‌ای نیست"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                              reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙", callback_data="buttons_menu")))

    elif data == "clear_btn":
        user_buttons[uid] = []
        bot.answer_callback_query(call.id, "پاک شد", show_alert=True)

    # ----- آنالیز -----
    elif data == "analyze":
        active = get_active_channel(uid)
        if not active:
            bot.answer_callback_query(call.id, "کانال فعال انتخاب کنید", show_alert=True)
            return
        try:
            chat = bot.get_chat(active[0])
            members = bot.get_chat_member_count(active[0])
            admins = len(bot.get_chat_administrators(active[0]))
            text = f"📊 **آنالیز کانال**\n\n📌 {chat.title}\n👥 اعضا: **{members:,}**\n👑 ادمین: {admins}\n🆔 `{chat.id}`"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid), parse_mode="Markdown")
        except Exception as e:
            bot.answer_callback_query(call.id, f"خطا: {e}", show_alert=True)

    # ----- پین حذف -----
    elif data == "pin_delete":
        mk = InlineKeyboardMarkup(row_width=2)
        mk.add(InlineKeyboardButton("📌 پین", callback_data="do_pin"),
               InlineKeyboardButton("🗑 حذف", callback_data="do_delete"))
        mk.add(InlineKeyboardButton("🔙", callback_data="back_main"))
        bot.edit_message_text("انتخاب کنید:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "do_pin":
        bot.user_steps[uid] = {"step": "pin"}
        bot.edit_message_text("آیدی پیام را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "do_delete":
        bot.user_steps[uid] = {"step": "delete"}
        bot.edit_message_text("آیدی پیام را بفرستید:", call.message.chat.id, call.message.message_id)

    # ----- پرمیوم -----
    elif data == "buy_premium":
        price = get_setting("premium_price", "10")
        mk = InlineKeyboardMarkup()
        mk.add(InlineKeyboardButton(f"پرداخت {price} استارز", callback_data="pay_premium"))
        mk.add(InlineKeyboardButton("انصراف", callback_data="back_main"))
        bot.edit_message_text(f"⭐ پرمیوم\nقیمت: {price} استارز\n\nمزایا:\n• کانال نامحدود\n• امکانات بیشتر", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "pay_premium":
        price = int(get_setting("premium_price", "10"))
        bot.send_invoice(call.message.chat.id, title="خرید پرمیوم", description="اشتراک پرمیوم",
                         invoice_payload=f"premium_{uid}", provider_token="", currency="XTR",
                         prices=[LabeledPrice("Premium", price)])

    # ----- ایموجی پرمیوم -----
    elif data == "premium_emoji":
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(InlineKeyboardButton("➕ اضافه کردن ایموجی پرمیوم", callback_data="add_prem_emoji"),
               InlineKeyboardButton("📋 لیست ایموجی‌های من", callback_data="list_prem_emoji"),
               InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
        bot.edit_message_text("😀 مدیریت ایموجی پرمیوم\n(custom_emoji_id را وارد کنید)", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "add_prem_emoji":
        bot.user_steps[uid] = {"step": "add_emoji_id"}
        bot.edit_message_text("custom_emoji_id را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "list_prem_emoji":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, emoji_id, title FROM premium_emojis WHERE user_id=?", (uid,))
        rows = c.fetchall()
        conn.close()
        text = "لیست ایموجی‌های پرمیوم شما:\n\n" + "\n".join([f"#{r[0]} | {r[2] or ''} | `{r[1]}`" for r in rows]) if rows else "خالی"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown",
                              reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙", callback_data="premium_emoji")))

    # ----- پنل ادمین (لیست کاربران کامل) -----
    elif data == "admin_panel" and is_main_admin(uid):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE is_premium=1")
        prem = c.fetchone()[0]
        conn.close()
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(InlineKeyboardButton(f"👥 کاربران: {total} | پرمیوم: {prem}", callback_data="admin_users"),
               InlineKeyboardButton("📋 لیست کامل کاربران + کانال‌ها", callback_data="admin_user_list"),
               InlineKeyboardButton("💰 قیمت پرمیوم", callback_data="admin_price"),
               InlineKeyboardButton("⚙️ سقف کانال پیش‌فرض", callback_data="admin_maxch"),
               InlineKeyboardButton("🔒 قفل کانال‌ها", callback_data="admin_forced"),
               InlineKeyboardButton("🛠️ تعمیرات", callback_data="admin_maint"),
               InlineKeyboardButton("📅 زمان‌بندی‌ها", callback_data="admin_sched"),
               InlineKeyboardButton("🔙", callback_data="back_main"))
        bot.edit_message_text("👑 پنل ادمین:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "admin_user_list" and is_main_admin(uid):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id, username, full_name, max_channels, is_premium FROM users ORDER BY last_active DESC LIMIT 25")
        users = c.fetchall()
        text = "👥 **لیست کاربران:**\n\n"
        for u in users:
            c.execute("SELECT channel_title FROM user_channels WHERE user_id=?", (u[0],))
            chs = [r[0] for r in c.fetchall()]
            ch_text = ", ".join(chs[:3]) if chs else "بدون کانال"
            uname = f"@{u[1]}" if u[1] else "بدون یوزرنیم"
            prem = "⭐" if u[4] else ""
            text += f"{prem}`{u[0]}` | {uname}\nنام: {u[2] or '-'}\nسقف: {u[3]} | کانال‌ها: {ch_text}\n────────────\n"
        conn.close()
        bot.send_message(call.message.chat.id, text[:4000], parse_mode="Markdown")

    elif data == "admin_price" and is_main_admin(uid):
        bot.user_steps[uid] = {"step": "set_price"}
        bot.edit_message_text(f"قیمت فعلی: {get_setting('premium_price')}\nقیمت جدید را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "admin_maxch" and is_main_admin(uid):
        bot.user_steps[uid] = {"step": "set_maxch"}
        bot.edit_message_text(f"سقف فعلی: {get_setting('max_channels_default')}\nعدد جدید را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "admin_forced" and is_main_admin(uid):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, channel_id, channel_title FROM forced_channels")
        rows = c.fetchall()
        conn.close()
        mk = InlineKeyboardMarkup(row_width=1)
        for r in rows:
            mk.add(InlineKeyboardButton(f"❌ {r[2] or r[1]}", callback_data=f"delf_{r[0]}"))
        mk.add(InlineKeyboardButton("➕ اضافه کردن", callback_data="add_forced"))
        mk.add(InlineKeyboardButton("🔙", callback_data="admin_panel"))
        bot.edit_message_text("کانال‌های قفل:", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "add_forced" and is_main_admin(uid):
        bot.user_steps[uid] = {"step": "add_forced"}
        bot.edit_message_text("آیدی کانال قفل را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data.startswith("delf_") and is_main_admin(uid):
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM forced_channels WHERE id=?", (int(data.split("_")[1]),))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "حذف شد")

    elif data == "admin_maint" and is_main_admin(uid):
        cur = get_setting("maintenance")
        set_setting("maintenance", "0" if cur == "1" else "1")
        bot.answer_callback_query(call.id, "تغییر کرد", show_alert=True)

    bot.answer_callback_query(call.id)

print("✅ بخش ۲ آماده")
# ==================== بخش ۳ از ۴ ====================
# هندلر پیام‌ها + ارسال همه نوع محتوا + دکمه با هر لینک + سقف کانال

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
        elif content_type == "video_note":
            return bot.send_video_note(channel, file_id, reply_markup=buttons)
    except Exception as e:
        raise e

@bot.message_handler(content_types=['text', 'photo', 'video', 'animation', 'voice', 'sticker', 'document', 'video_note'])
def handle_messages(message):
    uid = message.from_user.id
    ensure_user(message.from_user)
    bot.user_steps = getattr(bot, "user_steps", {})
    step_data = bot.user_steps.get(uid, {})
    step = step_data.get("step")

    # ----- اضافه کردن کانال -----
    if step == "add_channel":
        ch = message.text.strip()
        try:
            member = bot.get_chat_member(ch, uid)
            if member.status not in ["administrator", "creator"]:
                bot.send_message(message.chat.id, "❌ شما ادمین این کانال نیستید.", reply_markup=main_menu(uid))
                bot.user_steps[uid] = {}
                return

            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT max_channels, is_premium FROM users WHERE user_id=?", (uid,))
            row = c.fetchone()
            max_ch = 999 if (row and row[1]) else (row[0] if row else int(get_setting("max_channels_default", "3")))
            c.execute("SELECT COUNT(*) FROM user_channels WHERE user_id=?", (uid,))
            current = c.fetchone()[0]

            if current >= max_ch:
                bot.send_message(message.chat.id, f"❌ سقف کانال شما ({max_ch}) پر است.\nبا خرید پرمیوم می‌توانید نامحدود اضافه کنید.", reply_markup=main_menu(uid))
                conn.close()
                bot.user_steps[uid] = {}
                return

            chat = bot.get_chat(ch)
            c.execute("INSERT OR IGNORE INTO user_channels (user_id, channel_id, channel_title, is_active) VALUES (?, ?, ?, 0)",
                      (uid, str(chat.id), chat.title or ch))
            conn.commit()
            conn.close()
            bot.send_message(message.chat.id, f"✅ کانال «{chat.title}» اضافه شد.", reply_markup=main_menu(uid))
            log_action(uid, "add_channel", str(chat.id))
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا: {e}\nربات و شما باید ادمین کانال باشید.", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ----- ساخت دکمه شیشه‌ای (هر نوع لینک قبول می‌شود) -----
    if step == "btn_text":
        bot.user_steps[uid] = {"step": "btn_url", "text": message.text.strip()}
        bot.send_message(message.chat.id, "لینک دکمه را بفرستید:\n(هر نوع لینکی قبول است: https، t.me، لینک عادی و ...)")
        return

    if step == "btn_url":
        url = message.text.strip()
        # هر نوع لینکی را قبول می‌کنیم
        if not url:
            bot.send_message(message.chat.id, "لینک خالی است. دوباره بفرستید.")
            return
        if uid not in user_buttons:
            user_buttons[uid] = []
        user_buttons[uid].append({"text": step_data["text"], "url": url})
        bot.send_message(message.chat.id, f"✅ دکمه اضافه شد.\nتعداد دکمه‌ها: {len(user_buttons[uid])}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ----- ارسال لحظه‌ای (همه نوع محتوا + کپشن) -----
    if step == "send_now":
        active = get_active_channel(uid)
        if not active:
            bot.send_message(message.chat.id, "کانال فعال انتخاب نشده.", reply_markup=main_menu(uid))
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
            elif ctype == "animation":  # گیف
                send_to_channel(active[0], "animation", file_id=message.animation.file_id, caption=message.caption, buttons=buttons)
            elif ctype == "voice":
                send_to_channel(active[0], "voice", file_id=message.voice.file_id, caption=message.caption, buttons=buttons)
            elif ctype == "sticker":
                send_to_channel(active[0], "sticker", file_id=message.sticker.file_id, buttons=buttons)
            elif ctype == "document":
                send_to_channel(active[0], "document", file_id=message.document.file_id, caption=message.caption, buttons=buttons)
            elif ctype == "video_note":
                send_to_channel(active[0], "video_note", file_id=message.video_note.file_id, buttons=buttons)

            bot.send_message(message.chat.id, "✅ پست ارسال شد.", reply_markup=main_menu(uid))
            log_action(uid, "send_now", ctype)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا در ارسال:\n{e}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ----- پست آزمایشی -----
    if step == "preview":
        try:
            buttons = build_markup(uid)
            ctype = message.content_type
            file_id = None
            text = None
            caption = message.caption

            if ctype == "text":
                text = message.text
                bot.send_message(message.chat.id, text, reply_markup=buttons, parse_mode="Markdown")
            elif ctype == "photo":
                file_id = message.photo[-1].file_id
                bot.send_photo(message.chat.id, file_id, caption=caption, reply_markup=buttons)
            elif ctype == "video":
                file_id = message.video.file_id
                bot.send_video(message.chat.id, file_id, caption=caption, reply_markup=buttons)
            elif ctype == "animation":
                file_id = message.animation.file_id
                bot.send_animation(message.chat.id, file_id, caption=caption, reply_markup=buttons)
            elif ctype == "sticker":
                file_id = message.sticker.file_id
                bot.send_sticker(message.chat.id, file_id, reply_markup=buttons)
            else:
                bot.send_message(message.chat.id, "این نوع برای پیش‌نمایش پشتیبانی می‌شود.")
                bot.user_steps[uid] = {}
                return

            preview_data[uid] = {"ctype": ctype, "file_id": file_id, "text": text, "caption": caption}
            mk = InlineKeyboardMarkup()
            mk.add(InlineKeyboardButton("✅ تأیید و ارسال به کانال", callback_data="confirm_send"))
            mk.add(InlineKeyboardButton("❌ انصراف", callback_data="back_main"))
            bot.send_message(message.chat.id, "پیش‌نمایش بالا را ببینید. ارسال شود؟", reply_markup=mk)
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا: {e}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ----- زمان‌بندی -----
    if step == "sch_content":
        temp = {"ctype": message.content_type, "file_id": None, "text": None, "caption": message.caption}
        if message.content_type == "text":
            temp["text"] = message.text
        elif message.content_type == "photo":
            temp["file_id"] = message.photo[-1].file_id
        elif message.content_type == "video":
            temp["file_id"] = message.video.file_id
        elif message.content_type == "animation":
            temp["file_id"] = message.animation.file_id
        elif message.content_type == "sticker":
            temp["file_id"] = message.sticker.file_id
        elif message.content_type == "document":
            temp["file_id"] = message.document.file_id
        elif message.content_type == "voice":
            temp["file_id"] = message.voice.file_id

        bot.user_steps[uid] = {"step": "sch_time", "temp": temp}
        bot.send_message(message.chat.id, f"ساعت فعلی ایران: `{now_tehran().strftime('%H:%M')}`\n\nساعت ارسال را بفرستید:\n`18:30` یا `2026-08-12 18:30`", parse_mode="Markdown")
        return

    if step == "sch_time":
        try:
            t = message.text.strip()
            now = now_tehran()
            if len(t) <= 5:
                h, m = map(int, t.split(":"))
                send_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if send_time <= now:
                    send_time += timedelta(days=1)
            else:
                send_time = datetime.strptime(t, "%Y-%m-%d %H:%M")

            active = get_active_channel(uid)
            temp = step_data["temp"]
            buttons_json = json.dumps(user_buttons.get(uid, []))

            conn = get_db()
            c = conn.cursor()
            c.execute('''INSERT INTO scheduled_posts 
                (user_id, channel_id, content_type, file_id, text_content, caption, buttons, send_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (uid, active[0], temp["ctype"], temp.get("file_id"), temp.get("text"),
                 temp.get("caption"), buttons_json, send_time.strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            sid = c.lastrowid
            conn.close()
            bot.send_message(message.chat.id, f"✅ زمان‌بندی شد #{sid}\nزمان: {send_time.strftime('%Y-%m-%d %H:%M')}", reply_markup=main_menu(uid))
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا در زمان: {e}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ----- پین و حذف -----
    if step == "pin":
        active = get_active_channel(uid)
        try:
            bot.pin_chat_message(active[0], int(message.text.strip()))
            bot.send_message(message.chat.id, "✅ پین شد.", reply_markup=main_menu(uid))
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا: {e}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    if step == "delete":
        active = get_active_channel(uid)
        try:
            bot.delete_message(active[0], int(message.text.strip()))
            bot.send_message(message.chat.id, "✅ حذف شد.", reply_markup=main_menu(uid))
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا: {e}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ----- ایموجی پرمیوم -----
    if step == "add_emoji_id":
        eid = message.text.strip()
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO premium_emojis (user_id, emoji_id, title) VALUES (?, ?, ?)", (uid, eid, "emoji"))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ ایموجی پرمیوم ذخیره شد:\n`{eid}`", parse_mode="Markdown", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ----- تنظیمات ادمین -----
    if step == "set_price" and is_main_admin(uid):
        try:
            set_setting("premium_price", str(int(message.text.strip())))
            bot.send_message(message.chat.id, "✅ قیمت پرمیوم تغییر کرد.", reply_markup=main_menu(uid))
        except:
            bot.send_message(message.chat.id, "عدد معتبر بفرستید.")
        bot.user_steps[uid] = {}
        return

    if step == "set_maxch" and is_main_admin(uid):
        try:
            num = int(message.text.strip())
            set_setting("max_channels_default", str(num))
            # آپدیت همه کاربران غیرپرمیوم
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE users SET max_channels=? WHERE is_premium=0", (num,))
            conn.commit()
            conn.close()
            bot.send_message(message.chat.id, f"✅ سقف کانال پیش‌فرض به {num} تغییر کرد و برای کاربران اعمال شد.", reply_markup=main_menu(uid))
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

    bot.send_message(message.chat.id, "از منو استفاده کنید:", reply_markup=main_menu(uid))

print("✅ بخش ۳ آماده")
# ==================== بخش ۴ از ۴ ====================
# پرداخت + زمان‌بند + مدیریت زمان‌بندی + اجرا

@bot.pre_checkout_query_handler(func=lambda q: True)
def pre_checkout(q):
    bot.answer_pre_checkout_query(q.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def on_payment(message):
    uid = message.from_user.id
    payload = message.successful_payment.invoice_payload
    amount = message.successful_payment.total_amount

    if payload.startswith("premium_"):
        days = int(get_setting("premium_days", "30"))
        until = (now_tehran() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET is_premium=1, premium_until=?, max_channels=999 WHERE user_id=?", (until, uid))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id,
            f"✅ پرمیوم فعال شد!\nمدت: {days} روز\nتا: {until}\nحالا کانال نامحدود دارید.",
            reply_markup=main_menu(uid))
        log_action(uid, "premium_buy", f"amount={amount}")
        for adm in ADMIN_IDS:
            try:
                bot.send_message(adm, f"⭐ کاربر `{uid}` پرمیوم خرید ({amount} استارز)", parse_mode="Markdown")
            except:
                pass
    else:
        bot.send_message(message.chat.id, f"✅ پرداخت {amount} استارز انجام شد.", reply_markup=main_menu(uid))

# ----- مدیریت زمان‌بندی ادمین -----
@bot.callback_query_handler(func=lambda c: c.data == "admin_sched" or c.data.startswith("cancel_sch_"))
def admin_sched(c):
    uid = c.from_user.id
    if not is_main_admin(uid):
        return

    if c.data == "admin_sched":
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, user_id, content_type, send_time FROM scheduled_posts WHERE status='pending' ORDER BY send_time LIMIT 20")
        rows = cur.fetchall()
        conn.close()
        if not rows:
            bot.send_message(c.message.chat.id, "هیچ پست زمان‌بندی‌شده‌ای نیست.")
            return
        text = "📅 پست‌های در انتظار:\n\n"
        mk = InlineKeyboardMarkup(row_width=1)
        for r in rows:
            text += f"#{r[0]} | کاربر `{r[1]}` | {r[2]} | {r[3]}\n"
            mk.add(InlineKeyboardButton(f"❌ لغو #{r[0]}", callback_data=f"cancel_sch_{r[0]}"))
        mk.add(InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel"))
        bot.send_message(c.message.chat.id, text, reply_markup=mk, parse_mode="Markdown")

    elif c.data.startswith("cancel_sch_"):
        sid = int(c.data.split("_")[2])
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE scheduled_posts SET status='canceled' WHERE id=?", (sid,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(c.id, f"#{sid} لغو شد", show_alert=True)

# ----- سیستم زمان‌بندی -----
def scheduler():
    print("⏰ زمان‌بند فعال شد (وقت ایران)")
    while True:
        try:
            conn = get_db()
            c = conn.cursor()
            now = now_tehran().strftime("%Y-%m-%d %H:%M:%S")
            c.execute("SELECT * FROM scheduled_posts WHERE status='pending' AND send_time <= ?", (now,))
            rows = c.fetchall()
            for row in rows:
                try:
                    buttons_list = json.loads(row[7]) if row[7] else []
                    markup = None
                    if buttons_list:
                        markup = InlineKeyboardMarkup(row_width=2)
                        markup.add(*[InlineKeyboardButton(b["text"], url=b["url"]) for b in buttons_list])
                    send_to_channel(row[2], row[3], file_id=row[4], text=row[5], caption=row[6], buttons=markup)
                    c.execute("UPDATE scheduled_posts SET status='sent' WHERE id=?", (row[0],))
                    conn.commit()
                    print(f"✅ زمان‌بندی #{row[0]} ارسال شد")
                except Exception as e:
                    print(f"خطا #{row[0]}: {e}")
                    c.execute("UPDATE scheduled_posts SET status='error' WHERE id=?", (row[0],))
                    conn.commit()
            conn.close()
        except Exception as e:
            print("Scheduler error:", e)
        time.sleep(20)

# ----- اجرا -----
threading.Thread(target=scheduler, daemon=True).start()

print("🤖 ربات Nova نسخه ۳ (اصلاح‌شده) روشن شد")
print("رفع شده‌ها:")
print("- لیست کاربران + یوزرنیم + کانال‌ها")
print("- سقف کانال پیش‌فرض")
print("- تأیید پست آزمایشی")
print("- قبول همه نوع محتوا (عکس+کپشن، ویدیو، گیف، استیکر...)")
print("- دکمه شیشه‌ای با هر نوع لینک")
print("- بخش ایموجی پرمیوم")
bot.infinity_polling()
