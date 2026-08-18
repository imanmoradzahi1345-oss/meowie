import telebot
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

    bot.send_message(
        message.chat.id,
        "🐺 ربات گرگینه آماده است.\n\n"
        "برای ثبت کانال بنویس:\n"
        "کانال\n\n"
        "بعد آیدی کانال را بفرست."
    )


# =========================
# ثبت کانال
# =========================

@bot.message_handler(
    func=lambda message:
    message.text and message.text.strip() == "کانال"
)
def set_channel(message):

    waiting_channel.add(message.from_user.id)

    bot.send_message(
        message.chat.id,
        "📢 آیدی کانال را بفرست:\n\n"
        "@MyChannel\n\n"
        "⚠️ ربات باید ادمین کانال باشد."
    )


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
        f"✅ کانال ثبت شد:\n\n"
        f"{channel}\n\n"
        "حالا برای شروع شمارش بنویس:\n"
        "بشمار"
    )


# =========================
# شروع شمارش
# =========================

@bot.message_handler(
    func=lambda message:
    message.text and message.text.strip() == "بشمار"
)
def start_count(message):

    user_id = message.from_user.id

    if user_id not in users:

        bot.send_message(
            message.chat.id,
            "❌ اول کانال را ثبت کن.\n"
            "بنویس: کانال"
        )

        return

    channel = users[user_id]["channel"]

    if not channel:

        bot.send_message(
            message.chat.id,
            "❌ اول کانال را ثبت کن.\n"
            "بنویس: کانال"
        )

        return

    if users[user_id]["counting"]:

        bot.send_message(
            message.chat.id,
            "⚠️ شمارش از قبل در حال اجراست."
        )

        return

    users[user_id]["counting"] = True

    bot.send_message(
        message.chat.id,
        f"🐺 شمارش در {channel} شروع شد."
    )

    threading.Thread(
        target=count_worker,
        args=(channel, user_id),
        daemon=True
    ).start()


# =========================
# توقف
# =========================

@bot.message_handler(
    func=lambda message:
    message.text and message.text.strip() == "خاموش"
)
def stop_count(message):

    user_id = message.from_user.id

    if user_id in users and users[user_id]["counting"]:

        users[user_id]["counting"] = False

        bot.send_message(
            message.chat.id,
            "⛔ شمارش متوقف شد."
        )

    else:

        bot.send_message(
            message.chat.id,
            "❌ شمارشی در حال اجرا نیست."
        )


# =========================
# Worker
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

            # سرعت ارسال
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
