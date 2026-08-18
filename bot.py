import telebot
from telebot import types
from datetime import datetime
from zoneinfo import ZoneInfo
import time
import threading

TOKEN = "8875102057:AAE5JvIk9HhGoeizZhYUjyRvSdCRIsEzoxU"

bot = telebot.TeleBot(TOKEN)

# اطلاعات کاربران
users = {}

waiting_for_channel = set()
waiting_for_text = set()


def iran_time():
    now = datetime.now(ZoneInfo("Asia/Tehran"))

    hour_12 = now.strftime("%I:%M").lstrip("0")
    hour_24 = now.strftime("%H:%M")

    return hour_12, hour_24


# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(message):

    user_id = message.from_user.id

    if user_id not in users:
        users[user_id] = {
            "channel": None,
            "message_id": None,
            "running": False,
            "extra_text": ""
        }

    keyboard = types.InlineKeyboardMarkup()

    keyboard.add(
        types.InlineKeyboardButton(
            "📢 تعیین کانال",
            callback_data="set_channel"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "📝 تعیین متن اضافه",
            callback_data="set_text"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🕐 شروع ساعت",
            callback_data="start_clock"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "⛔ توقف ساعت",
            callback_data="stop_clock"
        )
    )

    bot.send_message(
        message.chat.id,
        "سلام 👋\n\n"
        "از دکمه‌های زیر تنظیمات ساعت رو انجام بده.",
        reply_markup=keyboard
    )


# =========================
# تعیین کانال
# =========================

@bot.callback_query_handler(func=lambda call: call.data == "set_channel")
def set_channel(call):

    waiting_for_channel.add(call.from_user.id)

    bot.answer_callback_query(call.id)

    bot.send_message(
        call.message.chat.id,
        "📢 آیدی کانال رو بفرست:\n\n"
        "مثال:\n"
        "@MyChannel\n\n"
        "⚠️ ربات باید داخل کانال ادمین باشد."
    )


@bot.message_handler(
    func=lambda message:
    message.from_user.id in waiting_for_channel
)
def receive_channel(message):

    user_id = message.from_user.id
    channel = message.text.strip()

    if not channel.startswith("@"):
        bot.send_message(
            message.chat.id,
            "❌ آیدی کانال باید با @ شروع بشه."
        )
        return

    waiting_for_channel.discard(user_id)

    if user_id not in users:
        users[user_id] = {
            "channel": None,
            "message_id": None,
            "running": False,
            "extra_text": ""
        }

    users[user_id]["channel"] = channel

    bot.send_message(
        message.chat.id,
        f"✅ کانال ثبت شد:\n{channel}\n\n"
        "حالا می‌تونی ساعت رو شروع کنی."
    )


# =========================
# تعیین متن اضافه
# =========================

@bot.callback_query_handler(func=lambda call: call.data == "set_text")
def set_text(call):

    waiting_for_text.add(call.from_user.id)

    bot.answer_callback_query(call.id)

    bot.send_message(
        call.message.chat.id,
        "📝 متنی که می‌خوای زیر ساعت نمایش داده بشه رو بفرست.\n\n"
        "مثال:\n"
        "KIAN 🐺"
    )


@bot.message_handler(
    func=lambda message:
    message.from_user.id in waiting_for_text
)
def receive_text(message):

    user_id = message.from_user.id

    waiting_for_text.discard(user_id)

    if user_id not in users:
        users[user_id] = {
            "channel": None,
            "message_id": None,
            "running": False,
            "extra_text": ""
        }

    users[user_id]["extra_text"] = message.text

    bot.send_message(
        message.chat.id,
        "✅ متن اضافه ذخیره شد."
    )


# =========================
# شروع ساعت
# =========================

@bot.callback_query_handler(func=lambda call: call.data == "start_clock")
def start_clock(call):

    user_id = call.from_user.id

    if user_id not in users or not users[user_id]["channel"]:
        bot.answer_callback_query(
            call.id,
            "❌ اول کانال رو تعیین کن."
        )
        return

    data = users[user_id]

    if data["running"]:
        bot.answer_callback_query(
            call.id,
            "⏰ ساعت از قبل فعاله."
        )
        return

    channel = data["channel"]

    hour_12, hour_24 = iran_time()

    text = f"🕐 ساعت ایران\n\n{hour_12}\n{hour_24}"

    if data["extra_text"]:
        text += f"\n\n{data['extra_text']}"

    try:

        msg = bot.send_message(
            channel,
            text
        )

        data["message_id"] = msg.message_id
        data["running"] = True

        bot.answer_callback_query(
            call.id,
            "✅ ساعت شروع شد."
        )

        bot.send_message(
            call.message.chat.id,
            f"✅ ساعت ایران در {channel} فعال شد."
        )

    except Exception as e:

        bot.answer_callback_query(
            call.id,
            "❌ خطا"
        )

        bot.send_message(
            call.message.chat.id,
            "❌ نتونستم داخل کانال پیام بفرستم.\n\n"
            "مطمئن شو ربات ادمین کاناله و اجازه ارسال پیام داره.\n\n"
            f"خطا:\n{e}"
        )


# =========================
# توقف ساعت
# =========================

@bot.callback_query_handler(func=lambda call: call.data == "stop_clock")
def stop_clock(call):

    user_id = call.from_user.id

    if user_id not in users:
        return

    users[user_id]["running"] = False

    bot.answer_callback_query(
        call.id,
        "⛔ ساعت متوقف شد."
    )

    bot.send_message(
        call.message.chat.id,
        "⛔ ساعت متوقف شد."
    )


# =========================
# بروزرسانی ساعت
# =========================

def clock_worker():

    last_minute = None

    while True:

        current_minute = iran_time()

        if current_minute != last_minute:

            last_minute = current_minute

            for user_id, data in list(users.items()):

                if not data["running"]:
                    continue

                channel = data["channel"]
                message_id = data["message_id"]

                hour_12, hour_24 = iran_time()

                text = (
                    f"🕐 ساعت ایران\n\n"
                    f"{hour_12}\n"
                    f"{hour_24}"
                )

                if data["extra_text"]:
                    text += f"\n\n{data['extra_text']}"

                try:

                    bot.edit_message_text(
                        text,
                        channel,
                        message_id
                    )

                except Exception as e:

                    print(
                        f"Error editing {channel}: {e}"
                    )

        time.sleep(1)


# =========================
# اجرای Worker
# =========================

threading.Thread(
    target=clock_worker,
    daemon=True
).start()

print("Bot started...")

bot.infinity_polling()
