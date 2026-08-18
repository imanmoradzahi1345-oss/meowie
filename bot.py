import telebot
from telebot import types
from datetime import datetime
from zoneinfo import ZoneInfo
import time
import threading

TOKEN = "8875102057:AAE5JvIk9HhGoeizZhYUjyRvSdCRIsEzoxU"

bot = telebot.TeleBot(TOKEN)

# اطلاعات کانال‌ها
channels = {}

# منتظر دریافت آیدی کانال
waiting_for_channel = set()


def iran_time():
    return datetime.now(
        ZoneInfo("Asia/Tehran")
    ).strftime("%H:%M")


# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(message):

    keyboard = types.InlineKeyboardMarkup()

    add_button = types.InlineKeyboardButton(
        "➕ افزودن کانال",
        callback_data="add_channel"
    )

    keyboard.add(add_button)

    bot.send_message(
        message.chat.id,
        "سلام 👋\n\n"
        "برای شروع، کانال خودت رو اضافه کن.\n"
        "⚠️ ربات باید ادمین کانال باشد.",
        reply_markup=keyboard
    )


# =========================
# دکمه افزودن کانال
# =========================

@bot.callback_query_handler(func=lambda call: call.data == "add_channel")
def add_channel(call):

    waiting_for_channel.add(call.from_user.id)

    bot.answer_callback_query(call.id)

    bot.send_message(
        call.message.chat.id,
        "آیدی کانال رو بفرست.\n\n"
        "مثال:\n"
        "@MyChannel"
    )


# =========================
# دریافت آیدی کانال
# =========================

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
            "❌ آیدی کانال باید با @ شروع بشه.\n\n"
            "مثال:\n"
            "@MyChannel"
        )
        return

    waiting_for_channel.discard(user_id)

    channels[user_id] = {
        "channel": channel,
        "message_id": None,
        "running": False
    }

    keyboard = types.InlineKeyboardMarkup()

    start_button = types.InlineKeyboardButton(
        "🕐 شروع ساعت",
        callback_data="start_clock"
    )

    stop_button = types.InlineKeyboardButton(
        "⛔ توقف ساعت",
        callback_data="stop_clock"
    )

    keyboard.add(start_button)
    keyboard.add(stop_button)

    bot.send_message(
        message.chat.id,
        f"✅ کانال ثبت شد:\n{channel}\n\n"
        "حالا روی «🕐 شروع ساعت» بزن.",
        reply_markup=keyboard
    )


# =========================
# شروع ساعت
# =========================

@bot.callback_query_handler(func=lambda call: call.data == "start_clock")
def start_clock(call):

    user_id = call.from_user.id

    if user_id not in channels:
        bot.answer_callback_query(
            call.id,
            "❌ اول کانال رو اضافه کن."
        )
        return

    data = channels[user_id]

    if data["running"]:
        bot.answer_callback_query(
            call.id,
            "⏰ ساعت از قبل فعاله."
        )
        return

    channel = data["channel"]

    try:

        # ارسال پیام اولیه
        msg = bot.send_message(
            channel,
            f"🕐 ساعت ایران\n\n{iran_time()}"
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

    if user_id not in channels:
        bot.answer_callback_query(
            call.id,
            "❌ کانالی ثبت نشده."
        )
        return

    channels[user_id]["running"] = False

    bot.answer_callback_query(
        call.id,
        "⛔ ساعت متوقف شد."
    )

    bot.send_message(
        call.message.chat.id,
        "⛔ ساعت متوقف شد."
    )


# =========================
# بروزرسانی ساعت‌ها
# =========================

def clock_worker():

    last_minute = None

    while True:

        current_minute = iran_time()

        # فقط وقتی دقیقه تغییر کرد
        if current_minute != last_minute:

            last_minute = current_minute

            for user_id, data in list(channels.items()):

                if not data["running"]:
                    continue

                channel = data["channel"]
                message_id = data["message_id"]

                try:

                    bot.edit_message_text(
                        f"🕐 ساعت ایران\n\n{current_minute}",
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
