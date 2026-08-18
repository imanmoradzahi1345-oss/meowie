import telebot
from telebot import types
from datetime import datetime
from zoneinfo import ZoneInfo
import time
import threading

TOKEN = "8875102057:AAE5JvIk9HhGoeizZhYUjyRvSdCRIsEzoxU"

bot = telebot.TeleBot(TOKEN)

users = {}

waiting_channel = set()
waiting_text = set()


def get_time():
    now = datetime.now(ZoneInfo("Asia/Tehran"))

    h12 = now.strftime("%I:%M").lstrip("0")
    h24 = now.strftime("%H:%M")

    return h12, h24


def make_text(data):
    h12, h24 = get_time()

    text = f"{h12}\n{h24}"

    if data.get("extra_text"):
        text += f"\n\n{data['extra_text']}"

    return text


# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(message):

    uid = message.from_user.id

    if uid not in users:
        users[uid] = {
            "channel": None,
            "message_id": None,
            "running": False,
            "extra_text": ""
        }

    keyboard = types.InlineKeyboardMarkup()

    keyboard.add(
        types.InlineKeyboardButton(
            "📢 تعیین کانال",
            callback_data="channel"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "📝 تعیین متن",
            callback_data="text"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "▶️ شروع",
            callback_data="start"
        ),
        types.InlineKeyboardButton(
            "⛔ توقف",
            callback_data="stop"
        )
    )

    bot.send_message(
        uid,
        "⚙️ تنظیمات ساعت\n\n"
        "اول کانال را تعیین کن.",
        reply_markup=keyboard
    )


# =========================
# تعیین کانال
# =========================

@bot.callback_query_handler(func=lambda c: c.data == "channel")
def channel_button(call):

    waiting_channel.add(call.from_user.id)

    bot.answer_callback_query(call.id)

    bot.send_message(
        call.message.chat.id,
        "📢 آیدی کانال را بفرست:\n\n"
        "@MyChannel\n\n"
        "ربات باید ادمین کانال باشد."
    )


@bot.message_handler(
    func=lambda m: m.from_user.id in waiting_channel
)
def get_channel(message):

    uid = message.from_user.id
    channel = message.text.strip()

    if not channel.startswith("@"):
        bot.send_message(
            message.chat.id,
            "❌ آیدی باید با @ شروع شود."
        )
        return

    waiting_channel.discard(uid)

    if uid not in users:
        users[uid] = {
            "channel": None,
            "message_id": None,
            "running": False,
            "extra_text": ""
        }

    users[uid]["channel"] = channel

    bot.send_message(
        message.chat.id,
        f"✅ کانال ثبت شد:\n{channel}"
    )


# =========================
# تعیین متن
# =========================

@bot.callback_query_handler(func=lambda c: c.data == "text")
def text_button(call):

    waiting_text.add(call.from_user.id)

    bot.answer_callback_query(call.id)

    bot.send_message(
        call.message.chat.id,
        "📝 متن دلخواهت را بفرست.\n\n"
        "اگر نمی‌خواهی متنی باشد، بنویس:\n"
        "خالی"
    )


@bot.message_handler(
    func=lambda m: m.from_user.id in waiting_text
)
def get_text(message):

    uid = message.from_user.id

    waiting_text.discard(uid)

    if uid not in users:
        users[uid] = {
            "channel": None,
            "message_id": None,
            "running": False,
            "extra_text": ""
        }

    if message.text.strip() == "خالی":
        users[uid]["extra_text"] = ""
    else:
        users[uid]["extra_text"] = message.text

    bot.send_message(
        message.chat.id,
        "✅ متن ذخیره شد."
    )


# =========================
# شروع
# =========================

@bot.callback_query_handler(func=lambda c: c.data == "start")
def start_clock(call):

    uid = call.from_user.id

    if uid not in users or not users[uid]["channel"]:
        bot.answer_callback_query(
            call.id,
            "❌ اول کانال را تعیین کن."
        )
        return

    data = users[uid]

    if data["running"]:
        bot.answer_callback_query(
            call.id,
            "⏰ ساعت از قبل فعال است."
        )
        return

    channel = data["channel"]

    try:

        msg = bot.send_message(
            channel,
            make_text(data)
        )

        data["message_id"] = msg.message_id
        data["running"] = True

        bot.answer_callback_query(
            call.id,
            "✅ شروع شد"
        )

        bot.send_message(
            call.message.chat.id,
            "✅ ساعت در کانال فعال شد."
        )

    except Exception as e:

        bot.answer_callback_query(
            call.id,
            "❌ خطا"
        )

        bot.send_message(
            call.message.chat.id,
            f"❌ ارسال پیام به کانال ناموفق بود:\n\n{e}"
        )


# =========================
# توقف
# =========================

@bot.callback_query_handler(func=lambda c: c.data == "stop")
def stop_clock(call):

    uid = call.from_user.id

    if uid in users:
        users[uid]["running"] = False

    bot.answer_callback_query(
        call.id,
        "⛔ متوقف شد"
    )

    bot.send_message(
        call.message.chat.id,
        "⛔ ساعت متوقف شد."
    )


# =========================
# آپدیت ساعت
# =========================

def clock_worker():

    last_time = ""

    while True:

        try:

            current_time = datetime.now(
                ZoneInfo("Asia/Tehran")
            ).strftime("%H:%M")

            # فقط وقتی دقیقه عوض شد
            if current_time != last_time:

                last_time = current_time

                for uid, data in list(users.items()):

                    if not data["running"]:
                        continue

                    channel = data["channel"]
                    message_id = data["message_id"]

                    if not channel or not message_id:
                        continue

                    try:

                        bot.edit_message_text(
                            chat_id=channel,
                            message_id=message_id,
                            text=make_text(data)
                        )

                        print(
                            f"Updated {channel} -> {current_time}"
                        )

                    except Exception as e:

                        print(
                            f"EDIT ERROR {channel}: {e}"
                        )

        except Exception as e:

            print(
                f"WORKER ERROR: {e}"
            )

        time.sleep(1)


# =========================
# Worker
# =========================

threading.Thread(
    target=clock_worker,
    daemon=True
).start()


print("BOT STARTED")

bot.infinity_polling(
    skip_pending=True
        )
