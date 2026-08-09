import json
import os
import threading
import time
from datetime import datetime

import telebot
from telebot import types

# =========================
# CONFIG
# =========================
TOKEN = "8786315286:AAFtV2BlWQJHiKGXZ7D8ynTm2GwfD11d94U"
ADMIN_ID = 7530457395
DB_FILE = "database.json"

bot = telebot.TeleBot(TOKEN)

# =========================
# DATABASE
# =========================
DEFAULT_DB = {
    "users": {},
    "channels": {},
    "buttons": {},
    "scheduled": []
}

def load_db():
    if not os.path.exists(DB_FILE):
        save_db(DEFAULT_DB.copy())
        return DEFAULT_DB.copy()

    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        for key, value in DEFAULT_DB.items():
            if key not in data:
                data[key] = value

        return data
    except Exception:
        return DEFAULT_DB.copy()

db = load_db()

def save_db(data=None):
    global db
    if data is not None:
        db = data

    tmp = DB_FILE + ".tmp"

    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)

        os.replace(tmp, DB_FILE)
    except Exception as e:
        print("Database error:", e)

# =========================
# USER
# =========================
def get_user(user_id):
    uid = str(user_id)

    if uid not in db["users"]:
        db["users"][uid] = {
            "id": user_id,
            "username": "",
            "first_name": "",
            "state": None
        }
        save_db()

    return db["users"][uid]

def set_state(user_id, state):
    get_user(user_id)["state"] = state
    save_db()

def clear_state(user_id):
    get_user(user_id)["state"] = None
    save_db()

# =========================
# KEYBOARDS
# =========================
def main_keyboard():
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2
    )

    kb.add(
        "📤 ارسال پست لحظه‌ای",
        "⏰ ارسال پست زمان‌بندی"
    )

    kb.add(
        "📢 تنظیم کانال",
        "🔗 دکمه شیشه‌ای"
    )

    kb.add(
        "🗑 حذف دکمه",
        "🧪 تست کانال"
    )

    if ADMIN_ID:
        kb.add("👑 پنل مدیریت")

    return kb

def admin_keyboard():
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2
    )

    kb.add(
        "📊 آمار ربات",
        "📢 اطلاعات کانال"
    )

    kb.add(
        "📋 پست‌های زمان‌بندی",
        "🗑 حذف زمان‌بندی"
    )

    kb.add(
        "🔙 منوی اصلی"
    )

    return kb

# =========================
# START
# =========================
@bot.message_handler(commands=["start"])
def start(message):
    user = get_user(message.from_user.id)

    user["username"] = message.from_user.username or ""
    user["first_name"] = message.from_user.first_name or ""

    save_db()

    bot.send_message(
        message.chat.id,
        "🤖 EMPIRE X\n\n"
        "سیستم مدیریت کانال آماده است.\n"
        "از منوی زیر انتخاب کنید:",
        reply_markup=main_keyboard()
    )

# =========================
# ADMIN
# =========================
@bot.message_handler(
    func=lambda m: m.text == "👑 پنل مدیریت"
)
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return

    bot.send_message(
        message.chat.id,
        "👑 پنل مدیریت EMPIRE X",
        reply_markup=admin_keyboard()
    )

@bot.message_handler(
    func=lambda m: m.text == "🔙 منوی اصلی"
)
def back_main(message):
    clear_state(message.from_user.id)

    bot.send_message(
        message.chat.id,
        "🏠 منوی اصلی",
        reply_markup=main_keyboard()
    )

# =========================
# CHANNEL SETUP
# =========================
@bot.message_handler(
    func=lambda m: m.text == "📢 تنظیم کانال"
)
def set_channel(message):
    set_state(message.from_user.id, "channel")

    bot.send_message(
        message.chat.id,
        "📢 آیدی یا شناسه کانال را ارسال کن.\n\n"
        "مثال:\n"
        "@MyChannel\n\n"
        "یا:\n"
        "-100123456789"
    )

# =========================
# GLASS BUTTON
# =========================
@bot.message_handler(
    func=lambda m: m.text == "🔗 دکمه شیشه‌ای"
)
def button_menu(message):
    kb = types.InlineKeyboardMarkup(row_width=1)

    kb.add(
        types.InlineKeyboardButton(
            "➕ افزودن / تغییر دکمه",
            callback_data="btn_add"
        ),
        types.InlineKeyboardButton(
            "🗑 حذف دکمه",
            callback_data="btn_delete"
        ),
        types.InlineKeyboardButton(
            "📋 مشاهده دکمه فعلی",
            callback_data="btn_show"
        )
    )

    bot.send_message(
        message.chat.id,
        "🔗 مدیریت دکمه شیشه‌ای",
        reply_markup=kb
    )

@bot.callback_query_handler(
    func=lambda c: c.data in [
        "btn_add",
        "btn_delete",
        "btn_show"
    ]
)
def button_callbacks(call):
    uid = str(call.from_user.id)

    if call.data == "btn_add":
        set_state(call.from_user.id, "button")

        bot.send_message(
            call.message.chat.id,
            "🔗 عنوان و لینک را با | جدا کن.\n\n"
            "مثال:\n"
            "ورود به کانال | https://t.me/MyChannel"
        )

    elif call.data == "btn_delete":
        db["buttons"].pop(uid, None)
        save_db()

        bot.answer_callback_query(
            call.id,
            "✅ دکمه حذف شد.",
            show_alert=True
        )

    elif call.data == "btn_show":
        button = db["buttons"].get(uid)

        if not button:
            text = "❌ دکمه‌ای تنظیم نشده."
        else:
            text = (
                "🔗 دکمه فعلی:\n\n"
                f"عنوان: {button['text']}\n"
                f"لینک: {button['url']}"
            )

        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            text
        )

# =========================
# DELETE BUTTON
# =========================
@bot.message_handler(
    func=lambda m: m.text == "🗑 حذف دکمه"
)
def delete_button(message):
    uid = str(message.from_user.id)

    db["buttons"].pop(uid, None)
    save_db()

    bot.send_message(
        message.chat.id,
        "🗑 دکمه شیشه‌ای حذف شد."
    )

# =========================
# SEND NOW
# =========================
@bot.message_handler(
    func=lambda m: m.text == "📤 ارسال پست لحظه‌ای"
)
def send_now(message):
    user = get_user(message.from_user.id)

    if not user.get("channel_id"):
        bot.send_message(
            message.chat.id,
            "⚠️ ابتدا کانال را تنظیم کن."
        )
        return

    set_state(
        message.from_user.id,
        "send_now"
    )

    bot.send_message(
        message.chat.id,
        "📤 پست را ارسال کن.\n\n"
        "پشتیبانی:\n"
        "📝 متن\n"
        "🖼 عکس\n"
        "🎥 گیف\n"
        "🎤 ویس\n"
        "🎞 ویدیو\n"
        "🔖 استیکر\n\n"
        "برای لغو /cancel را بزن."
    )

# =========================
# SCHEDULE
# =========================
@bot.message_handler(
    func=lambda m: m.text == "⏰ ارسال پست زمان‌بندی"
)
def schedule_start(message):
    user = get_user(message.from_user.id)

    if not user.get("channel_id"):
        bot.send_message(
            message.chat.id,
            "⚠️ ابتدا کانال را تنظیم کن."
        )
        return

    set_state(
        message.from_user.id,
        "schedule_time"
    )

    bot.send_message(
        message.chat.id,
        "⏰ زمان ارسال را وارد کن.\n\n"
        "فرمت:\n"
        "YYYY-MM-DD HH:MM\n\n"
        "مثال:\n"
        "2026-08-10 18:30"
    )

# =========================
# TEST CHANNEL
# =========================
@bot.message_handler(
    func=lambda m: m.text == "🧪 تست کانال"
)
def test_channel(message):
    user = get_user(message.from_user.id)
    channel = user.get("channel_id")

    if not channel:
        bot.send_message(
            message.chat.id,
            "❌ هنوز کانالی تنظیم نشده."
        )
        return

    try:
        chat = bot.get_chat(channel)

        member_count = bot.get_chat_member_count(
            channel
        )

        admins = bot.get_chat_administrators(
            channel
        )

        bot.send_message(
            message.chat.id,
            "🧪 اطلاعات کانال\n\n"
            f"📢 نام: {chat.title}\n"
            f"🆔 ID: {chat.id}\n"
            f"👥 تعداد اعضا: {member_count}\n"
            f"👑 تعداد ادمین‌ها: {len(admins)}\n"
            f"🔗 نوع: {chat.type}\n\n"
            "📈 برای محاسبه رشد واقعی، ربات باید "
            "آمار اعضای قبلی را نیز ذخیره کند."
        )

    except Exception as e:
        bot.send_message(
            message.chat.id,
            "❌ دسترسی به کانال ناموفق بود.\n\n"
            "مطمئن شو ربات داخل کانال ادمین است.\n\n"
            f"خطا: {e}"
        )

# =========================
# CANCEL
# =========================
@bot.message_handler(commands=["cancel"])
def cancel(message):
    clear_state(message.from_user.id)

    bot.send_message(
        message.chat.id,
        "❌ عملیات لغو شد.",
        reply_markup=main_keyboard()
    )

# =========================
# INPUT PROCESSOR
# =========================
@bot.message_handler(
    content_types=[
        "text",
        "photo",
        "video",
        "animation",
        "voice",
        "audio",
        "document",
        "sticker"
    ]
)
def process_input(message):

    uid = message.from_user.id
    user = get_user(uid)
    state = user.get("state")

    # -------------------------
    # CHANNEL
    # -------------------------
    if state == "channel":

        if not message.text:
            bot.send_message(
                message.chat.id,
                "❌ فقط آیدی کانال را ارسال کن."
            )
            return

        channel = message.text.strip()

        if not (
            channel.startswith("@")
            or channel.startswith("-100")
        ):
            bot.send_message(
                message.chat.id,
                "❌ فرمت کانال اشتباه است."
            )
            return

        try:
            chat = bot.get_chat(channel)

            user["channel_id"] = channel
            user["channel_title"] = chat.title

            clear_state(uid)

            bot.send_message(
                message.chat.id,
                f"✅ کانال ثبت شد.\n\n"
                f"📢 {chat.title}\n"
                f"🆔 {chat.id}",
                reply_markup=main_keyboard()
            )

        except Exception as e:
            bot.send_message(
                message.chat.id,
                "❌ ربات به این کانال دسترسی ندارد.\n"
                "مطمئن شو ادمین است."
            )

        return

    # -------------------------
    # BUTTON
    # -------------------------
    if state == "button":

        if not message.text or "|" not in message.text:
            bot.send_message(
                message.chat.id,
                "❌ فرمت اشتباه است.\n"
                "مثال:\n"
                "ورود | https://t.me/example"
            )
            return

        text, url = message.text.split(
            "|",
            1
        )

        text = text.strip()
        url = url.strip()

        if not (
            url.startswith("http://")
            or url.startswith("https://")
        ):
            bot.send_message(
                message.chat.id,
                "❌ لینک باید با http:// یا https:// شروع شود."
            )
            return

        db["buttons"][str(uid)] = {
            "text": text,
            "url": url
        }

        clear_state(uid)

        bot.send_message(
            message.chat.id,
            "✅ دکمه ذخیره شد.\n\n"
            f"🔘 {text}\n"
            f"🔗 {url}",
            reply_markup=main_keyboard()
        )

        return

    # -------------------------
    # SCHEDULE TIME
    # -------------------------
    if state == "schedule_time":

        if not message.text:
            bot.send_message(
                message.chat.id,
                "❌ زمان را به صورت متنی وارد کن."
            )
            return

        try:
            dt = datetime.strptime(
                message.text.strip(),
                "%Y-%m-%d %H:%M"
            )

            if dt <= datetime.now():
                bot.send_message(
                    message.chat.id,
                    "❌ این زمان گذشته است."
                )
                return

            user["schedule_time"] = message.text.strip()
            set_state(uid, "schedule_post")

            bot.send_message(
                message.chat.id,
                "✅ زمان ثبت شد.\n\n"
                f"⏰ {message.text}\n\n"
                "حالا پستی که باید در این زمان ارسال شود "
                "را بفرست."
            )

        except ValueError:
            bot.send_message(
                message.chat.id,
                "❌ فرمت اشتباه است.\n\n"
                "مثال:\n"
                "2026-08-10 18:30"
            )

        return

    # -------------------------
    # SEND NOW
    # -------------------------
    if state == "send_now":

        channel = user.get("channel_id")

        try:
            send_content(
                channel,
                message,
                uid
            )

            clear_state(uid)

            bot.send_message(
                message.chat.id,
                "✅ پست با موفقیت ارسال شد.",
                reply_markup=main_keyboard()
            )

        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"❌ ارسال ناموفق بود:\n{e}"
            )

        return

    # -------------------------
    # SCHEDULE POST
    # -------------------------
    if state == "schedule_post":

        if message.content_type not in [
            "text",
            "photo",
            "video",
            "animation",
            "voice",
            "audio",
            "document",
            "sticker"
        ]:
            bot.send_message(
                message.chat.id,
                "❌ این نوع فایل پشتیبانی نمی‌شود."
            )
            return

        item = {
            "id": len(db["scheduled"]) + 1,
            "user_id": uid,
            "channel_id": user["channel_id"],
            "time": user["schedule_time"],
            "content_type": message.content_type,
            "message_id": message.message_id,
            "chat_id": message.chat.id,
            "status": "pending"
        }

        db["scheduled"].append(item)

        user.pop("schedule_time", None)
        clear_state(uid)

        save_db()

        bot.send_message(
            message.chat.id,
            "✅ پست زمان‌بندی شد.\n\n"
            f"⏰ زمان: {item['time']}\n"
            f"🆔 شماره: #{item['id']}",
            reply_markup=main_keyboard()
        )

        return

# =========================
# SEND CONTENT
# =========================
def make_markup(user_id):
    button = db["buttons"].get(str(user_id))

    if not button:
        return None

    kb = types.InlineKeyboardMarkup()

    kb.add(
        types.InlineKeyboardButton(
            button["text"],
            url=button["url"]
        )
    )

    return kb

def send_content(channel, message, user_id):

    markup = make_markup(user_id)
    ct = message.content_type

    if ct == "text":
        bot.send_message(
            channel,
            message.text,
            reply_markup=markup
        )

    elif ct == "photo":
        bot.send_photo(
            channel,
            message.photo[-1].file_id,
            caption=message.caption or "",
            reply_markup=markup
        )

    elif ct == "video":
        bot.send_video(
            channel,
            message.video.file_id,
            caption=message.caption or "",
            reply_markup=markup
        )

    elif ct == "animation":
        bot.send_animation(
            channel,
            message.animation.file_id,
            caption=message.caption or "",
            reply_markup=markup
        )

    elif ct == "voice":
        bot.send_voice(
            channel,
            message.voice.file_id,
            caption=message.caption or "",
            reply_markup=markup
        )

    elif ct == "audio":
        bot.send_audio(
            channel,
            message.audio.file_id,
            caption=message.caption or "",
            reply_markup=markup
        )

    elif ct == "document":
        bot.send_document(
            channel,
            message.document.file_id,
            caption=message.caption or "",
            reply_markup=markup
        )

    elif ct == "sticker":
        bot.send_sticker(
            channel,
            message.sticker.file_id,
            reply_markup=markup
    )
         # =========================
# ADMIN STATS
# =========================
@bot.message_handler(
    func=lambda m: m.text == "📊 آمار ربات"
)
def bot_stats(message):

    if message.from_user.id != ADMIN_ID:
        return

    users = len(db["users"])
    scheduled = len([
        x for x in db["scheduled"]
        if x.get("status") == "pending"
    ])

    channels = len([
        x for x in db["users"].values()
        if x.get("channel_id")
    ])

    bot.send_message(
        message.chat.id,
        "📊 آمار EMPIRE X\n\n"
        f"👤 کاربران: {users}\n"
        f"📢 کانال‌های تنظیم‌شده: {channels}\n"
        f"⏰ پست‌های زمان‌بندی‌شده: {scheduled}"
    )

# =========================
# CHANNEL INFO ADMIN
# =========================
@bot.message_handler(
    func=lambda m: m.text == "📢 اطلاعات کانال"
)
def admin_channel_info(message):

    if message.from_user.id != ADMIN_ID:
        return

    channels = []

    for u in db["users"].values():
        ch = u.get("channel_id")

        if ch and ch not in channels:
            channels.append(ch)

    if not channels:
        bot.send_message(
            message.chat.id,
            "❌ هنوز کانالی ثبت نشده."
        )
        return

    for channel in channels:

        try:
            chat = bot.get_chat(channel)
            count = bot.get_chat_member_count(channel)
            admins = bot.get_chat_administrators(channel)

            bot.send_message(
                message.chat.id,
                "📢 اطلاعات کانال\n\n"
                f"نام: {chat.title}\n"
                f"ID: {chat.id}\n"
                f"👥 اعضا: {count}\n"
                f"👑 ادمین‌ها: {len(admins)}"
            )

        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"❌ خطا برای {channel}\n{e}"
            )

# =========================
# SCHEDULE LIST
# =========================
@bot.message_handler(
    func=lambda m: m.text == "📋 پست‌های زمان‌بندی"
)
def scheduled_list(message):

    if message.from_user.id != ADMIN_ID:
        return

    items = [
        x for x in db["scheduled"]
        if x.get("status") == "pending"
    ]

    if not items:
        bot.send_message(
            message.chat.id,
            "📋 هیچ پست زمان‌بندی‌شده‌ای وجود ندارد."
        )
        return

    for item in items:

        bot.send_message(
            message.chat.id,
            "⏰ پست زمان‌بندی\n\n"
            f"🆔 #{item['id']}\n"
            f"📢 کانال: {item['channel_id']}\n"
            f"🕐 زمان: {item['time']}\n"
            f"📦 نوع: {item['content_type']}"
        )

# =========================
# DELETE SCHEDULE
# =========================
@bot.message_handler(
    func=lambda m: m.text == "🗑 حذف زمان‌بندی"
)
def delete_schedule_menu(message):

    if message.from_user.id != ADMIN_ID:
        return

    set_state(
        message.from_user.id,
        "delete_schedule"
    )

    bot.send_message(
        message.chat.id,
        "🗑 شماره پست زمان‌بندی‌شده را بفرست.\n\n"
        "مثال:\n"
        "3"
    )

# =========================
# GENERAL TEXT HANDLER
# =========================
@bot.message_handler(
    func=lambda m: True,
    content_types=["text"]
)
def general_text(message):

    uid = message.from_user.id
    user = get_user(uid)
    state = user.get("state")

    if state != "delete_schedule":
        return

    if message.from_user.id != ADMIN_ID:
        return

    try:
        item_id = int(message.text.strip())
    except ValueError:
        bot.send_message(
            message.chat.id,
            "❌ فقط شماره را وارد کن."
        )
        return

    found = False

    for item in db["scheduled"]:
        if item["id"] == item_id:
            item["status"] = "cancelled"
            found = True
            break

    clear_state(uid)

    if found:
        save_db()

        bot.send_message(
            message.chat.id,
            f"✅ زمان‌بندی #{item_id} حذف شد.",
            reply_markup=admin_keyboard()
        )
    else:
        bot.send_message(
            message.chat.id,
            "❌ چنین زمان‌بندی‌ای پیدا نشد."
        )

# =========================
# SCHEDULER
# =========================
def scheduler_loop():

    while True:

        try:
            now = datetime.now()

            for item in db["scheduled"]:

                if item.get("status") != "pending":
                    continue

                try:
                    target = datetime.strptime(
                        item["time"],
                        "%Y-%m-%d %H:%M"
                    )
                except Exception:
                    item["status"] = "error"
                    continue

                if now >= target:

                    try:

                        bot.copy_message(
                            item["channel_id"],
                            item["chat_id"],
                            item["message_id"],
                            reply_markup=make_markup(
                                item["user_id"]
                            )
                        )

                        item["status"] = "sent"

                        save_db()

                        try:
                            bot.send_message(
                                item["user_id"],
                                "✅ پست زمان‌بندی‌شده ارسال شد."
                            )
                        except Exception:
                            pass

                    except Exception as e:

                        print(
                            "Scheduled send error:",
                            e
                        )

                        item["status"] = "error"
                        save_db()

        except Exception as e:
            print(
                "Scheduler error:",
                e
            )

        time.sleep(20)

# =========================
# START SCHEDULER
# =========================
threading.Thread(
    target=scheduler_loop,
    daemon=True
).start()

# =========================
# RUN
# =========================
print("================================")
print("🤖 EMPIRE X روشن شد...")
print("💾 Database:", DB_FILE)
print("👑 Admin:", ADMIN_ID)
print("⏰ Scheduler: ON")
print("================================")

while True:
    try:
        bot.infinity_polling(
            timeout=30,
            long_polling_timeout=25,
            skip_pending=True
        )

    except Exception as e:
        print("Polling error:", e)
        time.sleep(5)
