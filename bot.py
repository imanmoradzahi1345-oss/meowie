import telebot
from telebot import types
import threading
import time

TOKEN = "8875102057:AAE5JvIk9HhGoeizZhYUjyRvSdCRIsEzoxU"

bot = telebot.TeleBot(TOKEN)

users = {}
waiting_channel = set()


# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(message):

    user_id = message.from_user.id

    if user_id not in users:
        users[user_id] = {
            "channel": None,
            "counting": False
        }

    show_panel(message.chat.id)


def show_panel(chat_id):

    keyboard = types.InlineKeyboardMarkup(row_width=2)

    channel_btn = types.InlineKeyboardButton(
        "📢 تعیین کانال",
        callback_data="set_channel"
    )

    start_btn = types.InlineKeyboardButton(
        "🐺 شروع شمارش",
        callback_data="start_count"
    )

    stop_btn = types.InlineKeyboardButton(
        "⛔ خاموش",
        callback_data="stop_count"
    )

    keyboard.add(channel_btn)
    keyboard.add(start_btn, stop_btn)

    bot.send_message(
        chat_id,
        "🐺 پنل گرگینه\n\n"
        "از دکمه‌های زیر استفاده کن:",
        reply_markup=keyboard
    )


# =========================
# دکمه تعیین کانال
# =========================

@bot.callback_query_handler(
    func=lambda call: call.data == "set_channel"
)
def set_channel(call):

    waiting_channel.add(call.from_user.id)

    bot.answer_callback_query(call.id)

    bot.send_message(
        call.message.chat.id,
        "📢 آیدی کانال را بفرست:\n\n"
        "@MyChannel\n\n"
        "⚠️ ربات باید ادمین کانال باشد."
    )


# =========================
# دریافت کانال
# =========================

@bot.message_handler(
    func=lambda message:
    message.from_user.id in waiting_channel
)
def receive_channel(message):

    user_id = message.from_user.id

    channel = message.text.strip()

    if not channel.startswith("@"):

        bot.send_message(
            message.chat.id,
            "❌ آیدی کانال باید با @ شروع شود.\n\n"
            "مثال:\n"
            "@MyChannel"
        )

        return

    waiting_channel.discard(user_id)

    if user_id not in users:
        users[user_id] = {
            "channel": None,
            "counting": False
        }

    users[user_id]["channel"] = channel

    bot.send_message(
        message.chat.id,
        f"✅ کانال ثبت شد:\n\n{channel}"
    )

    show_panel(message.chat.id)


# =========================
# دکمه شروع
# =========================

@bot.callback_query_handler(
    func=lambda call: call.data == "start_count"
)
def start_count(call):

    user_id = call.from_user.id

    if user_id not in users:
        bot.answer_callback_query(
            call.id,
            "❌ اول /start را بزن."
        )
        return

    channel = users[user_id]["channel"]

    if not channel:
        bot.answer_callback_query(
            call.id,
            "❌ اول کانال را تعیین کن."
        )
        return

    if users[user_id]["counting"]:
        bot.answer_callback_query(
            call.id,
            "⚠️ شمارش از قبل فعال است."
        )
        return

    users[user_id]["counting"] = True

    bot.answer_callback_query(
        call.id,
        "🐺 شروع شد!"
    )

    bot.send_message(
        call.message.chat.id,
        f"🐺 شمارش در {channel} شروع شد."
    )

    threading.Thread(
        target=count_worker,
        args=(channel, user_id),
        daemon=True
    ).start()


# =========================
# دکمه توقف
# =========================

@bot.callback_query_handler(
    func=lambda call: call.data == "stop_count"
)
def stop_count(call):

    user_id = call.from_user.id

    if user_id in users:
        users[user_id]["counting"] = False

    bot.answer_callback_query(
        call.id,
        "⛔ متوقف شد."
    )

    bot.send_message(
        call.message.chat.id,
        "⛔ شمارش متوقف شد."
    )


# =========================
# دستور متنی بشمار
# =========================

@bot.message_handler(
    func=lambda message:
    message.text and message.text.strip() == "بشمار"
)
def text_start(message):

    user_id = message.from_user.id

    if user_id not in users:
        users[user_id] = {
            "channel": None,
            "counting": False
        }

    if not users[user_id]["channel"]:
        bot.send_message(
            message.chat.id,
            "❌ اول کانال را تعیین کن."
        )
        return

    if users[user_id]["counting"]:
        return

    users[user_id]["counting"] = True

    threading.Thread(
        target=count_worker,
        args=(users[user_id]["channel"], user_id),
        daemon=True
    ).start()


# =========================
# دستور متنی خاموش
# =========================

@bot.message_handler(
    func=lambda message:
    message.text and message.text.strip() == "خاموش"
)
def text_stop(message):

    user_id = message.from_user.id

    if user_id in users:
        users[user_id]["counting"] = False

    bot.send_message(
        message.chat.id,
        "⛔ شمارش متوقف شد."
    )


# =========================
# شمارش
# =========================

def count_worker(channel, user_id):

    number = 1

    while users.get(user_id, {}).get("counting", False):

        try:

            bot.send_message(
                channel,
                f"{number} (به عنوان گرگینه)"
            )

            number += 1

            time.sleep(0.05)

        except Exception as e:

            print("ERROR:", e)

            users[user_id]["counting"] = False

            break


# =========================
# اجرا
# =========================

print("🐺 Werewolf Bot Started...")

bot.infinity_polling(
    skip_pending=True
            )
