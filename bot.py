import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import threading
import time
import re
import traceback
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
    TEHRAN = ZoneInfo("Asia/Tehran")
except Exception:
    TEHRAN = None

BOT_TOKEN = "8597049833:AAFnEjGLcOz09Duy6MIvOoMD9TA1-fiRhPE"
ADMIN_ID = 7530457395

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
waiting = set()
admin_steps = {}
timer_thread_started = False
lock = threading.Lock()

def get_db():
    conn = sqlite3.connect("kian_bot.db", check_same_thread=False, timeout=30)
    return conn

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
    c.execute('''CREATE TABLE IF NOT EXISTS archive (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        content_type TEXT NOT NULL,
        file_id TEXT,
        text TEXT,
        created_at TEXT
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

try:
    init_db()
except Exception as e:
    print("DB init error:", e)

def is_admin(uid):
    try:
        return int(uid) == int(ADMIN_ID)
    except Exception:
        return False

def get_setting(key, default=""):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else default
    except Exception:
        return default

def set_setting(key, value):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()
        conn.close()
    except Exception as e:
        print("set_setting error:", e)

def now_tehran():
    try:
        if TEHRAN:
            return datetime.now(TEHRAN)
    except Exception:
        pass
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
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO links (admin_msg_id, user_id) VALUES (?, ?)", (admin_msg_id, user_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print("save_link error:", e)

def find_user_from_reply(reply_msg):
    try:
        if not reply_msg:
            return None
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id FROM links WHERE admin_msg_id=?", (reply_msg.message_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return row[0]
        if getattr(reply_msg, "forward_from", None):
            return reply_msg.forward_from.id
        text = reply_msg.text or reply_msg.caption or ""
        match = re.search(r"🆔\s*`?(\d+)`?", text)
        if match:
            return int(match.group(1))
    except Exception as e:
        print("find_user error:", e)
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

def get_stats():
    result = {"photo": 0, "video": 0, "text": 0, "sticker": 0, "link": 0, "total": 0}
    try:
        conn = get_db()
        c = conn.cursor()
        for cat in ["photo", "video", "text", "sticker", "link"]:
            c.execute("SELECT COUNT(*) FROM archive WHERE category=?", (cat,))
            n = c.fetchone()[0]
            result[cat] = n
            result["total"] += n
        conn.close()
    except Exception as e:
        print("stats error:", e)
    return result

def admin_menu():
    st = get_stats()
    ch = get_setting("channel") or "تنظیم نشده"
    active = get_setting("timer_active") == "1"
    m = InlineKeyboardMarkup(row_width=2)
    m.add(
        InlineKeyboardButton(f"🖼 عکس ({st['photo']})", callback_data="cat_photo"),
        InlineKeyboardButton(f"🎬 ویدیو ({st['video']})", callback_data="cat_video")
    )
    m.add(
        InlineKeyboardButton(f"📝 متن ({st['text']})", callback_data="cat_text"),
        InlineKeyboardButton(f"🏷 استیکر ({st['sticker']})", callback_data="cat_sticker")
    )
    m.add(
        InlineKeyboardButton(f"🔗 لینک ({st['link']})", callback_data="cat_link"),
        InlineKeyboardButton(f"📊 آمار ({st['total']})", callback_data="stats")
    )
    m.add(InlineKeyboardButton("💾 حالت سیو", callback_data="save_mode"))
    m.add(InlineKeyboardButton(f"📢 کانال/تایمر | {ch[:20]}", callback_data="channel_menu"))
    m.add(InlineKeyboardButton("⏹ توقف تایمر" if active else "▶️ وضعیت تایمر", callback_data="channel_menu"))
    return m

def channel_menu():
    ch = get_setting("channel") or "تنظیم نشده"
    active = get_setting("timer_active") == "1"
    title = get_setting("timer_title") or "بدون عنوان"
    m = InlineKeyboardMarkup(row_width=1)
    m.add(InlineKeyboardButton(f"📢 کانال: {ch}", callback_data="adm_set_channel"))
    m.add(InlineKeyboardButton("⏱ تنظیم تایمر (روز)", callback_data="adm_set_timer"))
    m.add(InlineKeyboardButton("🏷 عنوان تایمر", callback_data="adm_set_title"))
    if active:
        m.add(InlineKeyboardButton("⏹ توقف ساعت/تایمر", callback_data="adm_stop_timer"))
    else:
        m.add(InlineKeyboardButton("▶️ شروع ساعت + تایمر", callback_data="adm_start_timer"))
    m.add(InlineKeyboardButton(f"📌 {title}", callback_data="noop"))
    m.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_admin"))
    return m

def build_channel_text():
    now = now_tehran()
    t12 = now.strftime("%I:%M %p").lstrip("0")
    t24 = now.strftime("%H:%M")
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    month_name = JALALI_MONTHS.get(jm, "")
    jalali_date = f"{jy}/{jm}/{jd}"
    text = (
        f"📅 تاریخ ایران\n{jalali_date}\n{month_name}\n\n"
        f"🕒 ساعت ایران\n\n۱۲ ساعته: {t12}\n۲۴ ساعته: {t24}\n"
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
    return max(0.5, (next_minute - now).total_seconds())

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

def timer_worker():
    while True:
        try:
            time.sleep(seconds_until_next_minute())
            if get_setting("timer_active") == "1":
                update_channel_message()
        except Exception as e:
            print("timer error:", e)
            time.sleep(5)

def start_timer_thread():
    global timer_thread_started
    with lock:
        if not timer_thread_started:
            t = threading.Thread(target=timer_worker, daemon=True)
            t.start()
            timer_thread_started = True

def detect_and_save(message):
    category = None
    content_type = None
    file_id = None
    text = message.caption or message.text or ""

    if message.photo:
        category, content_type, file_id = "photo", "photo", message.photo[-1].file_id
    elif message.video:
        category, content_type, file_id = "video", "video", message.video.file_id
    elif message.animation:
        category, content_type, file_id = "video", "animation", message.animation.file_id
    elif message.sticker:
        category, content_type, file_id = "sticker", "sticker", message.sticker.file_id
    elif message.document:
        mime = (message.document.mime_type or "").lower()
        file_id = message.document.file_id
        if mime.startswith("video"):
            category, content_type = "video", "document"
        elif mime.startswith("image"):
            category, content_type = "photo", "document"
        else:
            category, content_type = "text", "document"
            text = (message.document.file_name or "") + (("\n" + text) if text else "")
    elif message.text:
        t = message.text.strip()
        if t.startswith("@") or "t.me/" in t.lower() or t.lower().startswith("http"):
            category, content_type, text = "link", "text", t
        else:
            category, content_type, text = "text", "text", t
    else:
        return None

    try:
        conn = get_db()
        c = conn.cursor()
        c.execute(
            "INSERT INTO archive (category, content_type, file_id, text, created_at) VALUES (?, ?, ?, ?, ?)",
            (category, content_type, file_id, text, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
        return category
    except Exception as e:
        print("save archive error:", e)
        return None

def send_category_items(chat_id, category):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT content_type, file_id, text FROM archive WHERE category=? ORDER BY id ASC", (category,))
        rows = c.fetchall()
        conn.close()
    except Exception as e:
        bot.send_message(chat_id, f"خطا در خواندن آرشیو: {e}")
        return

    if not rows:
        bot.send_message(chat_id, "این بخش خالی است.", reply_markup=admin_menu())
        return

    bot.send_message(chat_id, f"ارسال {len(rows)} مورد با فاصله ۱ ثانیه...")
    for content_type, file_id, text in rows:
        try:
            if content_type == "photo":
                bot.send_photo(chat_id, file_id, caption=text or None)
            elif content_type == "video":
                bot.send_video(chat_id, file_id, caption=text or None)
            elif content_type == "animation":
                bot.send_animation(chat_id, file_id, caption=text or None)
            elif content_type == "sticker":
                bot.send_sticker(chat_id, file_id)
            elif content_type == "document":
                bot.send_document(chat_id, file_id, caption=text or None)
            else:
                bot.send_message(chat_id, text or "-")
        except Exception as e:
            try:
                bot.send_message(chat_id, f"خطا در یک مورد: {e}")
            except Exception:
                pass
        time.sleep(1)
    try:
        bot.send_message(chat_id, "✅ تمام شد.", reply_markup=admin_menu())
    except Exception:
        pass

def safe_delete(chat_id, msg_id):
    try:
        bot.delete_message(chat_id, msg_id)
    except Exception:
        pass
        @bot.message_handler(commands=['start'])
def start(message):
    try:
        uid = message.from_user.id
        if message.chat.type != "private":
            return

        if is_admin(uid):
            admin_steps.pop(uid, None)
            bot.reply_to(
                message,
                "👋 پنل ادمین\n\n"
                "• پیام کاربران اینجا می‌آید\n"
                "• حالت سیو برای آرشیو عکس/ویدیو/متن/استیکر/لینک\n"
                "• کانال و تایمر از منو",
                reply_markup=admin_menu()
            )
            return

        waiting.add(uid)
        bot.reply_to(
            message,
            "سلام 👋\n\nتو در حال ارسال پیام برای **کیان** هستی (به صورت ناشناس).\n\nپیامت را بنویس و بفرست:",
            parse_mode="Markdown"
        )
    except Exception as e:
        print("start error:", e)

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    try:
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
                bot.send_message(uid, f"💬 پاسخ کیان:\n\n{row[1]}", reply_markup=new_msg_button())
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

        if data == "back_admin":
            admin_steps.pop(uid, None)
            bot.edit_message_text("منوی ادمین:", call.message.chat.id, call.message.message_id, reply_markup=admin_menu())

        elif data == "stats":
            st = get_stats()
            text = (
                f"📊 آمار\n\n"
                f"🖼 عکس: {st['photo']}\n"
                f"🎬 ویدیو: {st['video']}\n"
                f"📝 متن: {st['text']}\n"
                f"🏷 استیکر: {st['sticker']}\n"
                f"🔗 لینک: {st['link']}\n"
                f"📦 مجموع: {st['total']}"
            )
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, text, reply_markup=admin_menu())

        elif data == "save_mode":
            admin_steps[uid] = "save"
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, "💾 حالت سیو فعال شد.\nعکس/ویدیو/متن/استیکر/لینک بفرست یا فوروارد کن.\nخروج: /start")

        elif data.startswith("cat_"):
            category = data.split("_", 1)[1]
            bot.answer_callback_query(call.id)
            threading.Thread(target=send_category_items, args=(call.message.chat.id, category), daemon=True).start()

        elif data == "channel_menu":
            bot.edit_message_text("تنظیمات کانال و تایمر:", call.message.chat.id, call.message.message_id, reply_markup=channel_menu())

        elif data == "adm_set_channel":
            admin_steps[uid] = "set_channel"
            bot.edit_message_text("آیدی/یوزرنیم کانال را بفرست:", call.message.chat.id, call.message.message_id)

        elif data == "adm_set_timer":
            admin_steps[uid] = "set_timer"
            bot.edit_message_text("تعداد روز تایمر را بفرست (مثال 380):", call.message.chat.id, call.message.message_id)

        elif data == "adm_set_title":
            admin_steps[uid] = "set_title"
            bot.edit_message_text("عنوان تایمر را بفرست\nحذف با: -", call.message.chat.id, call.message.message_id)

        elif data == "adm_start_timer":
            channel = get_setting("channel")
            if not channel:
                bot.answer_callback_query(call.id, "اول کانال را تنظیم کن", show_alert=True)
                return
            if not get_setting("timer_end"):
                bot.answer_callback_query(call.id, "اول تایمر را تنظیم کن", show_alert=True)
                return
            try:
                text = build_channel_text()
                msg = bot.send_message(channel, text)
                set_setting("timer_msg_id", msg.message_id)
                set_setting("timer_active", "1")
                start_timer_thread()
                bot.answer_callback_query(call.id, "شروع شد", show_alert=True)
                bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=channel_menu())
            except Exception as e:
                bot.answer_callback_query(call.id, f"خطا: {e}", show_alert=True)

        elif data == "adm_stop_timer":
            set_setting("timer_active", "0")
            bot.answer_callback_query(call.id, "متوقف شد", show_alert=True)
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=channel_menu())

        bot.answer_callback_query(call.id)
    except Exception as e:
        print("callback error:", e)
        traceback.print_exc()
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

@bot.message_handler(func=lambda m: m.chat.type == "private", content_types=[
    'text', 'photo', 'video', 'voice', 'document', 'sticker', 'animation'
])
def handle_private(message):
    try:
        uid = message.from_user.id

        if is_admin(uid):
            step = admin_steps.get(uid)

            if step == "set_channel":
                ch = (message.text or "").strip()
                try:
                    chat = bot.get_chat(ch)
                    test = bot.send_message(ch, "✅ متصل شد")
                    safe_delete(ch, test.message_id)
                    set_setting("channel", ch)
                    admin_steps.pop(uid, None)
                    bot.reply_to(message, f"✅ کانال: {chat.title}", reply_markup=channel_menu())
                except Exception as e:
                    bot.reply_to(message, f"❌ خطا: {e}")
                return

            if step == "set_timer":
                try:
                    days = int((message.text or "").strip())
                    if days < 0:
                        bot.reply_to(message, "عدد منفی مجاز نیست")
                        return
                    end = now_tehran() + timedelta(days=days)
                    set_setting("timer_end", end.isoformat())
                    admin_steps.pop(uid, None)
                    bot.reply_to(message, f"✅ تایمر {days} روزه تنظیم شد", reply_markup=channel_menu())
                except Exception:
                    bot.reply_to(message, "فقط عدد بفرست")
                return

            if step == "set_title":
                title = (message.text or "").strip()
                if title == "-":
                    set_setting("timer_title", "")
                    bot.reply_to(message, "✅ عنوان حذف شد", reply_markup=channel_menu())
                else:
                    set_setting("timer_title", title)
                    bot.reply_to(message, f"✅ عنوان: {title}", reply_markup=channel_menu())
                admin_steps.pop(uid, None)
                return

            if step == "save":
                cat = detect_and_save(message)
                if not cat:
                    bot.reply_to(message, "این نوع پشتیبانی نمی‌شود")
                    return
                names = {"photo": "عکس", "video": "ویدیو", "text": "متن", "sticker": "استیکر", "link": "لینک"}
                conf = bot.reply_to(message, f"✅ سیو شد در: {names.get(cat, cat)}")
                time.sleep(0.3)
                safe_delete(message.chat.id, message.message_id)
                safe_delete(message.chat.id, conf.message_id)
                return

            if message.reply_to_message:
                target = find_user_from_reply(message.reply_to_message)
                if not target:
                    bot.reply_to(message, "کاربر پیدا نشد. روی پیام فوروارد/اطلاعات ریپلای کن.")
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
                        "💬 کیان جوابت را داد\nبرای دیدن، دکمه زیر را بزن:",
                        reply_markup=view_reply_button(reply_id)
                    )
                    bot.reply_to(message, f"✅ ارسال شد برای {target}")
                except Exception as e:
                    bot.reply_to(message, f"ارسال نشد: {e}")
                return

            bot.reply_to(message, "از منو استفاده کن یا /start", reply_markup=admin_menu())
            return

        if uid not in waiting:
            bot.reply_to(message, "برای ارسال پیام دکمه زیر را بزن:", reply_markup=new_msg_button())
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
                bot.reply_to(message, "❌ خطا در ارسال")
                return

        try:
            info = bot.send_message(
                ADMIN_ID,
                f"📥 پیام جدید\n👤 {name}\n🆔 `{uid}`\nیوزرنیم: {uname}\n\nبرای جواب روی این پیام یا پیام بالا ریپلای کن.",
                parse_mode="Markdown"
            )
            save_link(info.message_id, uid)
        except Exception:
            pass

        waiting.discard(uid)
        if sent_ok:
            bot.reply_to(message, "✅ پیامت برای کیان ارسال شد.", reply_markup=new_msg_button())
    except Exception as e:
        print("handle_private error:", e)
        traceback.print_exc()

if get_setting("timer_active") == "1":
    start_timer_thread()

print("Bot started successfully")
while True:
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=50)
    except Exception as e:
        print("polling error:", e)
        traceback.print_exc()
        time.sleep(3)
