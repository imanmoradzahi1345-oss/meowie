import telebot
from telebot import types
import threading
import time

# =========================
# TOKEN
# =========================

TOKEN = "8875102057:AAE5JvIk9HhGoeizZhYUjyRvSdCRIsEzoxU"

bot = telebot.TeleBot(TOKEN)

# =========================
# DATABASE
# =========================

users = {}

waiting_channel = set()

# برای جلوگیری از اجرای چند شمارش همزمان
worker_locks = {}


# =========================
# ساخت کاربر
# =========================

def create_user(user_id):

    if user_id not in users:

        users[user_id] = {
            "channel": None,
            "counting": False
        }


# =========================
# پنل اصلی
# =========================

def show_panel(chat_id):

    keyboard = types.InlineKeyboardMarkup(row_width=2)

    channel_button = types.InlineKeyboardButton(
        "📢 تعیین کانال",
        callback_data="set_channel"
    )

    start_button = types.InlineKeyboardButton(
        "🐺 شروع شمارش",
        callback_data="start_count"
    )

    stop_button = types.InlineKeyboardButton(
        "⛔ توقف",
        callback_data="stop_count"
    )

    keyboard.add(channel_button)

    keyboard.add(
        start_button,
        stop_button
    )

    bot.send_message(
        chat_id,
        "🐺 پنل گرگینه\n\n"
        "📢 اول کانال را تعیین کن.\n"
        "بعد روی «🐺 شروع شمارش» بزن.",
        reply_markup=keyboard
    )


# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(message):

    user_id = message.from_user.id

    create_user(user_id)

    show_panel(message.chat.id)


# =========================
# دکمه تعیین کانال
# =========================

@bot.callback_query_handler(
    func=lambda call: call.data == "set_channel"
)
def set_channel(call):

    user_id = call.from_user.id

    create_user(user_id)

    waiting_channel.add(user_id)

    bot.answer_callback_query(
        call.id,
        "📢 منتظر آیدی کانال هستم"
    )

    bot.send_message(
        call.message.chat.id,
        "📢 آیدی کانال را بفرست:\n\n"
        "مثال:\n"
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

    if not message.text:

        return

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

    create_user(user_id)

    users[user_id]["channel"] = channel

    bot.send_message(
        message.chat.id,
        f"✅ کانال ثبت شد.\n\n"
        f"📢 {channel}\n\n"
        "حالا می‌توانی شمارش را شروع کنی."
    )

    show_panel(message.chat.id)


# =========================
# شروع از دکمه
# =========================

@bot.callback_query_handler(
    func=lambda call: call.data == "start_count"
)
def start_count_button(call):

    user_id = call.from_user.id

    create_user(user_id)

    data = users[user_id]

    if not data["channel"]:

        bot.answer_callback_query(
            call.id,
            "❌ اول کانال را تعیین کن."
        )

        return

    if data["counting"]:

        bot.answer_callback_query(
            call.id,
            "⚠️ شمارش از قبل فعال است."
        )

        return

    # تست دسترسی به کانال
    try:

        bot.get_chat(data["channel"])

    except Exception as e:

        bot.answer_callback_query(
            call.id,
            "❌ کانال پیدا نشد."
        )

        bot.send_message(
            call.message.chat.id,
            "❌ ربات نتوانست کانال را پیدا کند.\n\n"
            "مطمئن شو:\n"
            "1. آیدی کانال درست است.\n"
            "2. ربات داخل کانال است.\n"
            "3. ربات ادمین کانال است."
        )

        print("CHANNEL ERROR:", e)

        return

    data["counting"] = True

    bot.answer_callback_query(
        call.id,
        "🐺 شمارش شروع شد!"
    )

    bot.send_message(
        call.message.chat.id,
        f"🐺 شمارش شروع شد.\n\n"
        f"📢 کانال: {data['channel']}"
    )

    start_worker(
        user_id,
        data["channel"]
    )


# =========================
# توقف از دکمه
# =========================

@bot.callback_query_handler(
    func=lambda call: call.data == "stop_count"
)
def stop_count_button(call):

    user_id = call.from_user.id

    create_user(user_id)

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
# دستور بشمار
# =========================

@bot.message_handler(
    func=lambda message:
    message.text
    and message.text.strip() == "بشمار"
)
def start_count_text(message):

    user_id = message.from_user.id

    create_user(user_id)

    data = users[user_id]

    if not data["channel"]:

        bot.send_message(
            message.chat.id,
            "❌ اول کانال را تعیین کن.\n\n"
            "روی «📢 تعیین کانال» بزن."
        )

        return

    if data["counting"]:

        bot.send_message(
            message.chat.id,
            "⚠️ شمارش از قبل در حال اجراست."
        )

        return

    data["counting"] = True

    bot.send_message(
        message.chat.id,
        "🐺 شروع شد!"
    )

    start_worker(
        user_id,
        data["channel"]
    )


# =========================
# دستور خاموش
# =========================

@bot.message_handler(
    func=lambda message:
    message.text
    and message.text.strip() == "خاموش"
)
def stop_count_text(message):

    user_id = message.from_user.id

    create_user(user_id)

    if not users[user_id]["counting"]:

        bot.send_message(
            message.chat.id,
            "❌ شمارشی در حال اجرا نیست."
        )

        return

    users[user_id]["counting"] = False

    bot.send_message(
        message.chat.id,
        "⛔ شمارش متوقف شد."
    )


# =========================
# اجرای Worker
# =========================

def start_worker(user_id, channel):

    if worker_locks.get(user_id):

        return

    worker_locks[user_id] = True

    thread = threading.Thread(
        target=count_worker,
        args=(user_id, channel),
        daemon=True
    )

    thread.start()


# =========================
# شمارش
# =========================

def count_worker(user_id, channel):

    number = 1

    print(
        f"🐺 Counter started: {channel}"
    )

    try:

        while users.get(
            user_id,
            {}
        ).get(
            "counting",
            False
        ):

            try:

                bot.send_message(
                    channel,
                    f"{number} (به عنوان گرگینه)"
                )

                number += 1

                # سرعت بالا
                time.sleep(0.1)

            except Exception as e:

                error_text = str(e)

                print(
                    f"COUNT ERROR: {error_text}"
                )

                # اگر تلگرام FloodWait داد
                if "Flood control exceeded" in error_text:

                    print(
                        "⚠️ Telegram flood limit!"
                    )

                    time.sleep(5)

                    continue

                # خطای موقت اتصال
                if (
                    "502" in error_text
                    or "503" in error_text
                    or "504" in error_text
                    or "Bad Gateway" in error_text
                ):

                    print(
                        "🔄 Temporary Telegram error..."
                    )

                    time.sleep(3)

                    continue

                # خطای جدی
                users[user_id]["counting"] = False

                break

    finally:

        worker_locks[user_id] = False

        print(
            f"⛔ Counter stopped: {channel}"
        )


# =========================
# مدیریت خطاهای Polling
# =========================

def run_bot():

    while True:

        try:

            print(
                "🐺 Werewolf Bot Started..."
            )

            bot.infinity_polling(
                skip_pending=True,
                timeout=30,
                long_polling_timeout=30
            )

        except Exception as e:

            print(
                "⚠️ Telegram connection error:"
            )

            print(e)

            print(
                "🔄 Reconnecting in 5 seconds..."
            )

            time.sleep(3)


# =========================
# اجرا
# =========================

if __name__ == "__main__":

    run_bot()
