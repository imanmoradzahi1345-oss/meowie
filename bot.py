# -*- coding: utf-8 -*-

import telebot
import os

BOT_TOKEN = "8617545814:AAFAofo_nV39gFT1-IgfXu-esnGgXol62r4"

ADMIN_ID = 7530457395

bot = telebot.TeleBot(BOT_TOKEN)

TEXT_FILE = "start_text.txt"

# متن پیش‌فرض
if not os.path.exists(TEXT_FILE):
    with open(TEXT_FILE, "w", encoding="utf-8") as f:
        f.write("سلام 👋\nبه ربات خوش آمدید!")


# گرفتن متن
def get_text():
    with open(TEXT_FILE, "r", encoding="utf-8") as f:
        return f.read()


# ذخیره متن
def save_text(text):
    with open(TEXT_FILE, "w", encoding="utf-8") as f:
        f.write(text)


# وضعیت انتظار متن ادمین
waiting_for_text = set()


# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(message):

    text = get_text()

    bot.send_message(
        message.chat.id,
        text
    )


# =========================
# SETTEXT
# =========================

@bot.message_handler(commands=["settext"])
def settext(message):

    if message.from_user.id != ADMIN_ID:
        bot.send_message(
            message.chat.id,
            "❌ شما ادمین نیستید."
        )
        return

    waiting_for_text.add(message.from_user.id)

    bot.send_message(
        message.chat.id,
        "📝 متن جدید را همینجا ارسال کن:"
    )


# =========================
# دریافت پیام ادمین
# =========================

@bot.message_handler(
    func=lambda message: message.from_user.id == ADMIN_ID
)
def admin_message(message):

    if message.from_user.id not in waiting_for_text:
        return

    if not message.text:
        bot.send_message(
            message.chat.id,
            "❌ لطفاً متن ارسال کن."
        )
        return

    save_text(message.text)

    waiting_for_text.remove(message.from_user.id)

    bot.send_message(
        message.chat.id,
        "✅ متن جدید با موفقیت ذخیره شد!\n\n"
        "از این به بعد هرکس /start بزنه، این متن رو می‌بینه."
    )


# =========================
# اجرا
# =========================

print("🤖 ربات روشن شد...")

bot.infinity_polling(
    skip_pending=True
)
