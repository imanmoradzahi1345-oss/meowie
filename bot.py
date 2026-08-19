import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import re
from datetime import datetime

BOT_TOKEN = "8597049833:AAFnEjGLcOz09Duy6MIvOoMD9TA1-fiRhPE"
ADMIN_ID = 7530457395

bot = telebot.TeleBot(BOT_TOKEN)
waiting = set()

def get_db():
    return sqlite3.connect("inbox_bot.db", check_same_thread=False)

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
    conn.commit()
    conn.close()

init_db()

def new_msg_button():
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("✉️ ارسال پیام جدید", callback_data="new_message"))
    return m

def view_reply_button(reply_id):
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("👁 مشاهده پاسخ", callback_data=f"view_{reply_id}"))
    m.add(InlineKeyboardButton("✉️ ارسال پیام جدید", callback_data="new_message"))
    return m

def save_link(admin_msg_id, user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO links (admin_msg_id, user_id) VALUES (?, ?)", (admin_msg_id, user_id))
    conn.commit()
    conn.close()

def find_user_from_reply(reply_msg):
    """پیدا کردن کاربر از ریپلای ادمین - چند روش"""
    if not reply_msg:
        return None

    # روش ۱: از دیتابیس با message_id
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM links WHERE admin_msg_id=?", (reply_msg.message_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]

    # روش ۲: اگر پیام فوروارد باشه، از forward_from
    if reply_msg.forward_from:
        return reply_msg.forward_from.id

    # روش ۳: استخراج آیدی از متن پیام اطلاعات
    text = reply_msg.text or reply_msg.caption or ""
    match = re.search(r"🆔\s*`?(\d+)`?", text)
    if match:
        return int(match.group(1))

    match2 = re.search(r"ID:\s*(\d+)", text)
    if match2:
        return int(match2.group(1))

    return None

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id

    if uid == ADMIN_ID:
        bot.reply_to(message, "👋 سلام کیان\nپیام کاربران اینجا میاد.\nروی پیام کاربر یا پیام اطلاعات ریپلای کن تا جواب بدی.")
        return

    waiting.add(uid)
    bot.reply_to(
        message,
        "سلام 👋\n\n"
        "تو در حال ارسال پیام برای **کیان** هستی (به صورت ناشناس).\n\n"
        "پیامت رو بنویس و بفرست:",
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    uid = call.from_user.id
    data = call.data

    if data == "new_message":
        waiting.add(uid)
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "✉️ پیام جدیدت رو برای **کیان** بنویس:", parse_mode="Markdown")
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

@bot.message_handler(func=lambda m: m.chat.type == "private", content_types=['text', 'photo', 'video', 'voice', 'document', 'sticker', 'animation'])
def handle_message(message):
    uid = message.from_user.id

    # ========== جواب ادمین ==========
    if uid == ADMIN_ID:
        if not message.reply_to_message:
            bot.reply_to(message, "برای جواب دادن، روی پیام کاربر ریپلای کن.")
            return

        target = find_user_from_reply(message.reply_to_message)
        if not target:
            bot.reply_to(message, "نتونستم کاربر رو پیدا کنم.\nروی پیام فوروارد شده یا پیام اطلاعات (که آیدی داره) ریپلای کن.")
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
                "💬 **کیان جوابت رو داد**\n\nبرای دیدن پاسخ، روی دکمه زیر بزن:",
                parse_mode="Markdown",
                reply_markup=view_reply_button(reply_id)
            )
            bot.reply_to(message, f"✅ جواب برای کاربر `{target}` ارسال شد.", parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"کاربر پیدا شد ولی ارسال نشد:\n{e}")
        return

    # ========== پیام کاربر ==========
    if uid not in waiting:
        bot.reply_to(message, "برای ارسال پیام روی دکمه زیر بزن:", reply_markup=new_msg_button())
        return

    name = message.from_user.first_name or ""
    uname = f"@{message.from_user.username}" if message.from_user.username else "ندارد"
    sent_ok = False

    # اول سعی کن فوروارد کنه
    try:
        fwd = bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
        save_link(fwd.message_id, uid)
        sent_ok = True
    except Exception:
        # اگر فوروارد نشد، محتوا رو کپی کن
        try:
            if message.text:
                m = bot.send_message(ADMIN_ID, f"📩 پیام کاربر:\n\n{message.text}")
                save_link(m.message_id, uid)
            elif message.photo:
                m = bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=message.caption or "📩 عکس کاربر")
                save_link(m.message_id, uid)
            elif message.voice:
                m = bot.send_voice(ADMIN_ID, message.voice.file_id, caption="📩 ویس کاربر")
                save_link(m.message_id, uid)
            elif message.video:
                m = bot.send_video(ADMIN_ID, message.video.file_id, caption=message.caption or "📩 ویدیو کاربر")
                save_link(m.message_id, uid)
            elif message.sticker:
                m = bot.send_sticker(ADMIN_ID, message.sticker.file_id)
                save_link(m.message_id, uid)
            else:
                m = bot.send_message(ADMIN_ID, "📩 یک پیام دریافت شد (نوع پشتیبانی‌نشده)")
                save_link(m.message_id, uid)
            sent_ok = True
        except Exception as e:
            bot.reply_to(message, "❌ خطا در ارسال. دوباره تلاش کن.")
            return

    # پیام اطلاعات + آیدی (مهم برای ریپلای)
    try:
        info = bot.send_message(
            ADMIN_ID,
            f"📥 پیام جدید\n"
            f"👤 {name}\n"
            f"🆔 `{uid}`\n"
            f"یوزرنیم: {uname}\n\n"
            f"برای جواب، روی این پیام یا پیام بالا ریپلای کن.",
            parse_mode="Markdown"
        )
        save_link(info.message_id, uid)
    except Exception:
        pass

    waiting.discard(uid)

    if sent_ok:
        bot.reply_to(message, "✅ پیامت برای کیان ارسال شد.", reply_markup=new_msg_button())
    else:
        bot.reply_to(message, "❌ خطا در ارسال.", reply_markup=new_msg_button())

print("ربات پیام‌رسان اصلاح‌شده روشن شد")
bot.infinity_polling()
