import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import threading
import time
import re
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
    TEHRAN = ZoneInfo("Asia/Tehran")
except Exception:
    TEHRAN = None

BOT_TOKEN = "8597049833:AAFnEjGLcOz09Duy6MIvOoMD9TA1-fiRhPE"
ADMIN_ID = 7530457395

bot = telebot.TeleBot(BOT_TOKEN)
waiting = set()
timer_thread_started = False

def get_db():
    return sqlite3.connect("kian_secret.db", check_same_thread=False)

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS links (
        admin_msg_id INTEGER PRIMARY KEY,
        user_id INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS replies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        reply_text TEXT,
        reply_type TEXT DEFAULT 'text',
        file_id TEXT,
        created_at TEXT,
        seen INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    defaults = {
        "channel": "",
        "timer_end": "",
        "timer_title": "",
        "timer_msg_id": "",
        "timer_active": "0"
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()

init_db()

def is_admin(uid):
    return uid == ADMIN_ID

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

def now_tehran():
    if TEHRAN:
        return datetime.now(TEHRAN)
    return datetime.now()

def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = gy + 1 if gm > 2 else gy
    days = (365 * gy) + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 - 80 + gd + g_d_m[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd

JALALI_MONTHS = {
    1: "فروردین", 2: "اردیبهشت", 3: "خرداد", 4: "تیر",
    5: "مرداد", 6: "شهریور", 7: "مهر", 8: "آبان",
    9: "آذر", 10: "دی", 11: "بهمن", 12: "اسفند"
}

def save_link(admin_msg_id, user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO links (admin_msg_id, user_id) VALUES (?, ?)", (admin_msg_id, user_id))
    conn.commit()
    conn.close()

def find_user_from_reply(reply_msg):
    if not reply_msg:
        return None
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM links WHERE admin_msg_id=?", (reply_msg.message_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    if reply_msg.forward_from:
        return reply_msg.forward_from.id
    text = reply_msg.text or reply_msg.caption or ""
    match = re.search(r"🆔\s*`?(\d+)`?", text)
    if match:
        return int(match.group(1))
    return None

def new_msg_button():
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("✉️ ارسال پیام جدید", callback_data="new_message"))
    return m

def view_reply_button(reply_id):
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("👁 مشاهده پاسخ", callback_data=f"view_{reply_id}"))
    m.add(InlineKeyboardButton("✉️ ارسال پیام جدید", callback_data="new_message"))
    return m

def admin_menu():
    ch = get_setting("channel") or "تنظیم نشده"
    active = get_setting("timer_active") == "1"
    title = get_setting("timer_title") or "بدون عنوان"
    m = InlineKeyboardMarkup(row_width=1)
    m.add(InlineKeyboardButton(f"📢 کانال: {ch}", callback_data="adm_set_channel"))
    m.add(InlineKeyboardButton("⏱ تنظیم تایمر (روز)", callback_data="adm_set_timer"))
    m.add(InlineKeyboardButton("🏷 عنوان تایمر (اختیاری)", callback_data="adm_set_title"))
    if active:
        m.add(InlineKeyboardButton("⏹ توقف ساعت/تایمر", callback_data="adm_stop_timer"))
    else:
        m.add(InlineKeyboardButton("▶️ شروع ساعت + تایمر در کانال", callback_data="adm_start_timer"))
    m.add(InlineKeyboardButton(f"📌 عنوان فعلی: {title}", callback_data="noop"))
    return m

def build_channel_text():
    now = now_tehran()
    t12 = now.strftime("%I:%M %p").lstrip("0")
    t24 = now.strftime("%H:%M")
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    month_name = JALALI_MONTHS.get(jm, "")
    jalali_date = f"{jy}/{jm}/{jd}"
    text = (
        f"📅 تاریخ ایران\n"
        f"{jalali_date}\n"
        f"{month_name}\n\n"
        f"🕒 ساعت ایران\n\n"
        f"۱۲ ساعته: {t12}\n"
        f"۲۴ ساعته: {t24}\n"
    )
    if get_setting("timer_active") == "1" and get_setting("timer_end"):
        try:
            end = datetime.fromisoformat(get_setting("timer_end"))
            if TEHRAN:
                if end.tzinfo is None:
                    end = end.replace(tzinfo=TEHRAN)
                else:
                    end = end.astimezone(TEHRAN)
            diff = end - now_tehran()
            title = get_setting("timer_title")
            if diff.total_seconds() <= 0:
                remain = "۰ روز و ۰ ساعت و ۰ دقیقه"
            else:
                days = diff.days
                hours = diff.seconds // 3600
                minutes = (diff.seconds % 3600) // 60
                remain = f"{days} روز و {hours} ساعت و {minutes} دقیقه"
            text += "\n⏳ "
            if title:
                text += f"{title}\n"
            text += remain
        except Exception:
            pass
    return text

def seconds_until_next_minute():
    now = now_tehran()
    next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
    return max(0.2, (next_minute - now).total_seconds())

def update_channel_message():
    channel = get_setting("channel")
    msg_id = get_setting("timer_msg_id")
    if not channel or not msg_id:
        return
    text = build_channel_text()
    try:
        bot.edit_message_text(text, channel, int(msg_id))
    except Exception as e:
        err = str(e).lower()
        if "message to edit not found" in err or "message can't be edited" in err:
            try:
                m = bot.send_message(channel, text)
                set_setting("timer_msg_id", m.message_id)
            except Exception:
                pass
        elif "message is not modified" in err:
            pass

def timer_worker():
    while True:
        try:
            time.sleep(seconds_until_next_minute())
            if get_setting("timer_active") == "1":
                update_channel_message()
        except Exception:
            time.sleep(2)

def start_timer_thread():
    global timer_thread_started
    if not timer_thread_started:
        t = threading.Thread(target=timer_worker, daemon=True)
        t.start()
        timer_thread_started = True

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    if is_admin(uid) and message.chat.type == "private":
        bot.reply_to(
            message,
            "👋 سلام کیان\n\nاز این منو کانال و تایمر را مدیریت کن.\nپیام کاربران هم اینجا می‌آید.",
            reply_markup=admin_menu()
        )
        return
    if message.chat.type != "private":
        return
    waiting.add(uid)
    bot.reply_to(
        message,
        "سلام 👋\n\nتو در حال ارسال پیام برای **کیان** هستی (به صورت ناشناس).\n\nپیامت را بنویس و بفرست:",
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    uid = call.from_user.id
    data = call.data

    if data == "new_message":
        waiting.add(uid)
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "✉️ پیام جدیدت را برای **کیان** بنویس:", parse_mode="Markdown")
        return

    if data.startswith("view_"):
        reply_id = int(data.split("_")[1])
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id, reply_text, reply_type, file_id FROM replies WHERE id=?", (reply_id,))
        row = c.fetchone()
        if not row or row[0] != uid:
            bot.answer_callback_query(call.id, "پیامی پیدا نشد", show_alert=True)
            conn.close()
            return
        c.execute("UPDATE replies SET seen=1 WHERE id=?", (reply_id,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id)
        if row[2] == "text":
            bot.send_message(uid, f"💬 **پاسخ کیان:**\n\n{row[1]}", parse_mode="Markdown", reply_markup=new_msg_button())
        elif row[2] == "photo":
            bot.send_photo(uid, row[3], caption=f"💬 پاسخ کیان:\n{row[1] or ''}", reply_markup=new_msg_button())
        elif row[2] == "voice":
            bot.send_voice(uid, row[3], caption="💬 پاسخ کیان", reply_markup=new_msg_button())
        elif row[2] == "video":
            bot.send_video(uid, row[3], caption=f"💬 پاسخ کیان:\n{row[1] or ''}", reply_markup=new_msg_button())
        elif row[2] == "sticker":
            bot.send_sticker(uid, row[3])
            bot.send_message(uid, "💬 پاسخ کیان", reply_markup=new_msg_button())
        else:
            bot.send_message(uid, f"💬 پاسخ کیان:\n{row[1] or ''}", reply_markup=new_msg_button())
        return

    if not is_admin(uid) or call.message.chat.type != "private":
        bot.answer_callback_query(call.id, "دسترسی نداری", show_alert=True)
        return

    if data == "noop":
        bot.answer_callback_query(call.id)
        return

    if data == "adm_set_channel":
        bot.edit_message_text(
            "📢 آیدی یا یوزرنیم کانال را بفرست:\n`@channel` یا `-100...`",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown"
        )
        bot.register_next_step_handler(call.message, admin_save_channel)
    elif data == "adm_set_timer":
        bot.edit_message_text(
            "⏱ تعداد روز تایمر را بفرست:\nمثال: `380`",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown"
        )
        bot.register_next_step_handler(call.message, admin_save_timer)
    elif data == "adm_set_title":
        bot.edit_message_text(
            "🏷 عنوان تایمر را بفرست (اختیاری):\nبرای حذف عنوان بنویس: `-`",
            call.message.chat.id, call.message.message_id
        )
        bot.register_next_step_handler(call.message, admin_save_title)
    elif data == "adm_start_timer":
        channel = get_setting("channel")
        if not channel:
            bot.answer_callback_query(call.id, "اول کانال را تنظیم کن", show_alert=True)
            return
        if not get_setting("timer_end"):
            bot.answer_callback_query(call.id, "اول تعداد روز تایمر را تنظیم کن", show_alert=True)
            return
        try:
            text = build_channel_text()
            msg = bot.send_message(channel, text)
            set_setting("timer_msg_id", msg.message_id)
            set_setting("timer_active", "1")
            start_timer_thread()
            bot.answer_callback_query(call.id, "شروع شد ✅", show_alert=True)
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=admin_menu())
        except Exception as e:
            bot.answer_callback_query(call.id, f"خطا: {e}", show_alert=True)
    elif data == "adm_stop_timer":
        set_setting("timer_active", "0")
        bot.answer_callback_query(call.id, "متوقف شد", show_alert=True)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=admin_menu())

    bot.answer_callback_query(call.id)

def admin_save_channel(message):
    if not is_admin(message.from_user.id):
        return
    ch = message.text.strip()
    try:
        chat = bot.get_chat(ch)
        test = bot.send_message(ch, "✅ ربات به کانال متصل شد.")
        try:
            bot.delete_message(ch, test.message_id)
        except Exception:
            pass
        set_setting("channel", ch)
        bot.reply_to(message, f"✅ کانال تنظیم شد:\n{chat.title}", reply_markup=admin_menu())
    except Exception as e:
        bot.reply_to(message, f"❌ خطا:\n{e}\nربات باید ادمین کانال باشد.", reply_markup=admin_menu())

def admin_save_timer(message):
    if not is_admin(message.from_user.id):
        return
    try:
        days = int(message.text.strip())
        if days < 0:
            bot.reply_to(message, "عدد منفی مجاز نیست.")
            return
        end = now_tehran() + timedelta(days=days)
        set_setting("timer_end", end.isoformat())
        bot.reply_to(message, f"✅ تایمر برای {days} روز تنظیم شد.", reply_markup=admin_menu())
    except Exception:
        bot.reply_to(message, "فقط عدد بفرست (مثال: 380)", reply_markup=admin_menu())

def admin_save_title(message):
    if not is_admin(message.from_user.id):
        return
    title = message.text.strip()
    if title == "-":
        set_setting("timer_title", "")
        bot.reply_to(message, "✅ عنوان حذف شد.", reply_markup=admin_menu())
    else:
        set_setting("timer_title", title)
        bot.reply_to(message, f"✅ عنوان تنظیم شد:\n{title}", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.chat.type == "private", content_types=['text', 'photo', 'video', 'voice', 'document', 'sticker', 'animation'])
def handle_private(message):
    uid = message.from_user.id

    if is_admin(uid):
        if not message.reply_to_message:
            return
        target = find_user_from_reply(message.reply_to_message)
        if not target:
            bot.reply_to(message, "نتونستم کاربر را پیدا کنم. روی پیام کاربر یا پیام اطلاعات ریپلای کن.")
            return
        reply_type = "text"
        file_id = None
        reply_text = message.text or message.caption or ""
        if message.photo:
            reply_type = "photo"
            file_id = message.photo[-1].file_id
        elif message.voice:
            reply_type = "voice"
            file_id = message.voice.file_id
        elif message.video:
            reply_type = "video"
            file_id = message.video.file_id
        elif message.sticker:
            reply_type = "sticker"
            file_id = message.sticker.file_id
        elif message.document:
            reply_type = "document"
            file_id = message.document.file_id
        conn = get_db()
        c = conn.cursor()
        c.execute(
            "INSERT INTO replies (user_id, reply_text, reply_type, file_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (target, reply_text, reply_type, file_id, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        reply_id = c.lastrowid
        conn.commit()
        conn.close()
        try:
            bot.send_message(
                target,
                "💬 **کیان جوابت را داد**\n\nبرای دیدن پاسخ، روی دکمه زیر بزن:",
                parse_mode="Markdown",
                reply_markup=view_reply_button(reply_id)
            )
            bot.reply_to(message, f"✅ جواب برای `{target}` ارسال شد.", parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"ارسال نشد:\n{e}")
        return

    if uid not in waiting:
        bot.reply_to(message, "برای ارسال پیام روی دکمه زیر بزن:", reply_markup=new_msg_button())
        return

    name = message.from_user.first_name or ""
    uname = f"@{message.from_user.username}" if message.from_user.username else "ندارد"
    sent_ok = False

    try:
        fwd = bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
        save_link(fwd.message_id, uid)
        sent_ok = True
    except Exception:
        try:
            if message.text:
                m = bot.send_message(ADMIN_ID, f"📩 پیام کاربر:\n\n{message.text}")
            elif message.photo:
                m = bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=message.caption or "📩 عکس")
            elif message.voice:
                m = bot.send_voice(ADMIN_ID, message.voice.file_id)
            elif message.video:
                m = bot.send_video(ADMIN_ID, message.video.file_id, caption=message.caption or "📩 ویدیو")
            elif message.sticker:
                m = bot.send_sticker(ADMIN_ID, message.sticker.file_id)
            else:
                m = bot.send_message(ADMIN_ID, "📩 پیام دریافت شد")
            save_link(m.message_id, uid)
            sent_ok = True
        except Exception:
            bot.reply_to(message, "❌ خطا در ارسال.")
            return

    try:
        info = bot.send_message(
            ADMIN_ID,
            f"📥 پیام جدید\n👤 {name}\n🆔 `{uid}`\nیوزرنیم: {uname}\n\nبرای جواب، روی این پیام یا پیام بالا ریپلای کن.",
            parse_mode="Markdown"
        )
        save_link(info.message_id, uid)
    except Exception:
        pass

    waiting.discard(uid)
    if sent_ok:
        bot.reply_to(message, "✅ پیامت برای کیان ارسال شد.", reply_markup=new_msg_button())

if get_setting("timer_active") == "1":
    start_timer_thread()

print("KiAN Secret bot started")
bot.infinity_polling()
