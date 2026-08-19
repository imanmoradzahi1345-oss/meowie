import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
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

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id

    if uid == ADMIN_ID:
        bot.reply_to(message, "👋 سلام کیان\nپیام کاربران اینجا برات فوروارد می‌شه.\nروی پیام ریپلای کن تا جوابشون بدی.")
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
        bot.send_message(
            call.message.chat.id,
            "✉️ پیام جدیدت رو برای **کیان** بنویس:",
            parse_mode="Markdown"
        )
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

        # نمایش پاسخ
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
            bot.send_message(uid, "💬 پاسخ کیان (استیکر بالا)", reply_markup=new_msg_button())
        else:
            bot.send_message(uid, f"💬 پاسخ کیان:\n{row[1] or ''}", reply_markup=new_msg_button())

@bot.message_handler(func=lambda m: m.chat.type == "private", content_types=['text', 'photo', 'video', 'voice', 'document', 'sticker', 'animation'])
def handle_message(message):
    uid = message.from_user.id

    # ----- جواب ادمین (ریپلای روی پیام فوروارد شده) -----
    if uid == ADMIN_ID:
        if not message.reply_to_message:
            bot.reply_to(message, "برای جواب دادن، روی پیام کاربر ریپلای کن.")
            return

        # پیدا کردن کاربر از روی پیام فوروارد/لینک
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id FROM links WHERE admin_msg_id=?", (message.reply_to_message.message_id,))
        row = c.fetchone()

        # اگر روی پیام اطلاعات هم ریپلای کرده بود
        if not row:
            # گاهی ادمین روی پیام دوم (اطلاعات) ریپلای می‌کنه
            c.execute("SELECT user_id FROM links WHERE admin_msg_id=?", (message.reply_to_message.message_id - 1,))
            row = c.fetchone()

        if not row:
            bot.reply_to(message, "نتونستم کاربر رو پیدا کنم. روی پیام فوروارد شده ریپلای کن.")
            conn.close()
            return

        target = row[0]

        # ذخیره پاسخ
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

        c.execute(
            "INSERT INTO replies (user_id, reply_text, reply_type, file_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (target, reply_text, reply_type, file_id, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        reply_id = c.lastrowid
        conn.commit()
        conn.close()

        # اطلاع به کاربر
        try:
            bot.send_message(
                target,
                "💬 **کیان جوابت رو داد**\n\nبرای دیدن پاسخ، روی دکمه زیر بزن:",
                parse_mode="Markdown",
                reply_markup=view_reply_button(reply_id)
            )
            bot.reply_to(message, "✅ جوابت برای کاربر ارسال شد.")
        except Exception as e:
            bot.reply_to(message, f"خطا در ارسال به کاربر:\n{e}")
        return

    # ----- پیام کاربر -----
    if uid not in waiting:
        bot.reply_to(message, "برای ارسال پیام روی دکمه زیر بزن:", reply_markup=new_msg_button())
        return

    try:
        # فوروارد اصل پیام
        fwd = bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)

        name = message.from_user.first_name or ""
        uname = f"@{message.from_user.username}" if message.from_user.username else "ندارد"
        info = bot.send_message(
            ADMIN_ID,
            f"📥 پیام جدید\n"
            f"👤 {name}\n"
            f"🆔 `{uid}`\n"
            f"یوزرنیم: {uname}\n\n"
            f"برای جواب، روی پیام بالا ریپلای کن.",
            parse_mode="Markdown"
        )

        # ذخیره لینک هر دو پیام به کاربر
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO links (admin_msg_id, user_id) VALUES (?, ?)", (fwd.message_id, uid))
        c.execute("INSERT OR REPLACE INTO links (admin_msg_id, user_id) VALUES (?, ?)", (info.message_id, uid))
        conn.commit()
        conn.close()

    except Exception as e:
        bot.reply_to(message, "خطا در ارسال. دوباره تلاش کن.")
        return

    waiting.discard(uid)
    bot.reply_to(message, "✅ پیامت برای کیان ارسال شد.", reply_markup=new_msg_button())

print("ربات پیام‌رسان + پاسخ روشن شد")
bot.infinity_polling()
