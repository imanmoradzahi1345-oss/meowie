# -*- coding: utf-8 -*-

import telebot
import sqlite3

# =========================
# تنظیمات
# =========================

BOT_TOKEN = "8617545814:AAFAofo_nV39gFT1-IgfXu-esnGgXol62r4"

ADMIN_ID = 7530457395

bot = telebot.TeleBot(BOT_TOKEN)

# =========================
# دیتابیس
# =========================

conn = sqlite3.connect("bot_data.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY,
    start_text TEXT
)
""")

cursor.execute("""
INSERT OR IGNORE INTO settings (id, start_text)
VALUES (1, 'سلام 👋\nبه ربات خوش آمدید!')
""")

conn.commit()


# =========================
# گرفتن متن فعلی
# =========================

def get_start_text():
    cursor.execute(
        "SELECT start_text FROM settings WHERE id = 1"
    )

    result = cursor.fetchone()

    if result:
        return result[0]

    return "سلام 👋"


# =========================
# بررسی ادمین
# =========================

def is_admin(user_id):
    return user_id == ADMIN_ID


# =========================
# /start
# =========================

@bot.message_handler(commands=["start"])
def start(message):

    text = get_start_text()

    bot.send_message(
        message.chat.id,
        text
    )


# =========================
# /settext
# =========================

@bot.message_handler(commands=["settext"])
def set_text(message):

    if not is_admin(message.from_user.id):
        bot.reply_to(
            message,
            "❌ شما اجازه انجام این کار را ندارید."
        )
        return

    msg = bot.send_message(
        message.chat.id,
        "📝 متن جدیدی که می‌خواهی هنگام /start نمایش داده شود را بفرست:"
    )

    bot.register_next_step_handler(
        msg,
        save_new_text
    )


# =========================
# ذخیره متن جدید
# =========================

def save_new_text(message):

    if not is_admin(message.from_user.id):
        return

    new_text = message.text

    if not new_text:
        bot.send_message(
            message.chat.id,
            "❌ متن معتبر نیست."
        )
        return

    cursor.execute(
        "UPDATE settings SET start_text = ? WHERE id = 1",
        (new_text,)
    )

    conn.commit()

    bot.send_message(
        message.chat.id,
        "✅ متن /start با موفقیت تغییر کرد."
    )


# =========================
# /myid
# =========================

@bot.message_handler(commands=["myid"])
def my_id(message):

    bot.reply_to(
        message,
        f"🆔 آیدی عددی شما:\n`{message.from_user.id}`",
        parse_mode="Markdown"
    )


# =========================
# اجرای ربات
# =========================

print("🤖 Bot is running...")

bot.infinity_polling(
    skip_pending=True
)
