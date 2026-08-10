# ==================== بخش ۱ ====================
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import threading
import time
from datetime import datetime, timedelta
import json

BOT_TOKEN = "8328122794:AAG67dIJIsz5tqgtVF0BHo80aZWIGtECc-A"
ADMIN_IDS = [7530457395]

bot = telebot.TeleBot(BOT_TOKEN)

# ----------------- دیتابیس -----------------
def init_db():
    conn = sqlite3.connect("channel_manager.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS channel_stats (
        channel_id TEXT PRIMARY KEY, last_members INTEGER, last_check TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS scheduled_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT, content_type TEXT, file_id TEXT,
        text_content TEXT, caption TEXT, buttons TEXT,
        send_time TEXT, status TEXT DEFAULT 'pending')''')
    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect("channel_manager.db")

def is_admin(uid):
    return uid in ADMIN_IDS

def get_setting(key, default=None):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key, value):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def get_channel():
    return get_setting("channel_id")

# دکمه‌های فعلی هر ادمین
user_buttons = {}   # {user_id: [{"text": "..", "url": ".."}, ...]}

# ----------------- منوها -----------------
def main_menu():
    m = InlineKeyboardMarkup(row_width=2)
    m.add(
        InlineKeyboardButton("📢 تنظیم کانال", callback_data="set_channel"),
        InlineKeyboardButton("🧪 آمار کانال", callback_data="channel_stats"),
    )
    m.add(
        InlineKeyboardButton("📝 ارسال لحظه‌ای", callback_data="send_now"),
        InlineKeyboardButton("⏰ ارسال زمان‌بندی", callback_data="schedule_post"),
    )
    m.add(
        InlineKeyboardButton("🔘 مدیریت دکمه‌ها", callback_data="buttons_menu"),
        InlineKeyboardButton("📌 پین / حذف پست", callback_data="pin_delete_menu"),
    )
    m.add(
        InlineKeyboardButton("👑 پنل ادمین", callback_data="admin_panel"),
    )
    return m

def buttons_menu():
    m = InlineKeyboardMarkup(row_width=1)
    m.add(
        InlineKeyboardButton("➕ تنظیم / تغییر دکمه‌ها", callback_data="set_buttons"),
        InlineKeyboardButton("👁 مشاهده دکمه‌های فعلی", callback_data="view_buttons"),
        InlineKeyboardButton("🧹 پاک کردن همه دکمه‌ها", callback_data="clear_buttons"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"),
    )
    return m

def content_type_menu(prefix):
    m = InlineKeyboardMarkup(row_width=2)
    m.add(
        InlineKeyboardButton("💬 متن", callback_data=f"{prefix}_text"),
        InlineKeyboardButton("🖼 عکس", callback_data=f"{prefix}_photo"),
        InlineKeyboardButton("🎬 گیف", callback_data=f"{prefix}_animation"),
        InlineKeyboardButton("🎙 ویس", callback_data=f"{prefix}_voice"),
        InlineKeyboardButton("🏷 استیکر", callback_data=f"{prefix}_sticker"),
    )
    m.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
    return m

def with_or_without_buttons(prefix):
    """انتخاب با دکمه یا بدون دکمه"""
    m = InlineKeyboardMarkup(row_width=1)
    m.add(
        InlineKeyboardButton("✅ ارسال با دکمه شیشه‌ای", callback_data=f"{prefix}_withbtn"),
        InlineKeyboardButton("❌ ارسال بدون دکمه", callback_data=f"{prefix}_nobtn"),
        InlineKeyboardButton("🔙 انصراف", callback_data="back_main"),
    )
    return m

def pin_delete_menu():
    m = InlineKeyboardMarkup(row_width=1)
    m.add(
        InlineKeyboardButton("📌 پین کردن پست", callback_data="pin_post"),
        InlineKeyboardButton("🗑 حذف پست از کانال", callback_data="delete_post"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"),
    )
    return m

def admin_menu():
    m = InlineKeyboardMarkup(row_width=1)
    m.add(
        InlineKeyboardButton("📋 لیست زمان‌بندی‌ها", callback_data="list_scheduled"),
        InlineKeyboardButton("🗑 پاک کردن همه زمان‌بندی‌ها", callback_data="clear_scheduled"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"),
    )
    return m

# ----------------- /start -----------------
@bot.message_handler(commands=['start'])
def start(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔️ شما ادمین نیستید.")
        return
    bot.send_message(message.chat.id, "🤖 **ربات مدیریت کانال**\nاز منوی زیر استفاده کنید.", 
                     reply_markup=main_menu(), parse_mode="Markdown")

# ----------------- کال‌بک‌ها -----------------
@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    uid = call.from_user.id
    if not is_admin(uid):
        bot.answer_callback_query(call.id, "دسترسی ندارید", show_alert=True)
        return

    data = call.data
    bot.user_steps = getattr(bot, "user_steps", {})

    if data == "back_main":
        bot.edit_message_text("منوی اصلی:", call.message.chat.id, call.message.message_id, reply_markup=main_menu())

    # تنظیم کانال
    elif data == "set_channel":
        bot.user_steps[uid] = {"step": "waiting_channel"}
        bot.edit_message_text("📢 آیدی کانال را بفرستید:\n`@channel` یا `-100xxxx`", 
                              call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    # آمار کانال
    elif data == "channel_stats":
        channel = get_channel()
        if not channel:
            bot.answer_callback_query(call.id, "اول کانال را تنظیم کنید", show_alert=True)
            return
        try:
            chat = bot.get_chat(channel)
            members = bot.get_chat_member_count(channel)
            admins = bot.get_chat_administrators(channel)
            admin_count = len(admins)

            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT last_members, last_check FROM channel_stats WHERE channel_id=?", (str(channel),))
            row = c.fetchone()

            if row:
                diff = members - row[0]
                growth = f"📈 +{diff}" if diff > 0 else (f"📉 {diff}" if diff < 0 else "➖ بدون تغییر")
                last_check = row[1]
            else:
                growth = "اولین بررسی"
                last_check = "—"

            c.execute("INSERT OR REPLACE INTO channel_stats VALUES (?, ?, ?)",
                      (str(channel), members, datetime.now().strftime("%Y-%m-%d %H:%M")))
            conn.commit()
            conn.close()

            text = f"""
🧪 **آمار کانال**

📌 {chat.title}
🆔 `{chat.id}`
👥 اعضا: **{members:,}**
👑 ادمین‌ها: **{admin_count}**

{growth}
آخرین بررسی: {last_check}
⏰ الان: {datetime.now().strftime("%Y-%m-%d %H:%M")}
"""
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                  reply_markup=main_menu(), parse_mode="Markdown")
        except Exception as e:
            bot.answer_callback_query(call.id, f"خطا: {e}", show_alert=True)

    # منوی دکمه‌ها
    elif data == "buttons_menu":
        bot.edit_message_text("🔘 مدیریت دکمه‌های شیشه‌ای:", call.message.chat.id, call.message.message_id, reply_markup=buttons_menu())

    elif data == "set_buttons":
        bot.user_steps[uid] = {"step": "waiting_buttons"}
        bot.edit_message_text(
            "دکمه‌ها را به این شکل بفرستید (هر خط یک دکمه):\n\n"
            "`متن دکمه - https://link.com`\n\n"
            "مثال:\n`عضویت - https://t.me/example`\n`سایت - https://google.com`",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif data == "view_buttons":
        btns = user_buttons.get(uid, [])
        if not btns:
            text = "هیچ دکمه‌ای تنظیم نشده."
        else:
            text = "🔘 **دکمه‌های فعلی:**\n\n"
            for i, b in enumerate(btns, 1):
                text += f"{i}. {b['text']} → {b['url']}\n"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                              reply_markup=buttons_menu(), parse_mode="Markdown")

    elif data == "clear_buttons":
        user_buttons[uid] = []
        bot.answer_callback_query(call.id, "✅ همه دکمه‌ها پاک شدند", show_alert=True)

    # ارسال لحظه‌ای
    elif data == "send_now":
        if not get_channel():
            bot.answer_callback_query(call.id, "اول کانال را تنظیم کنید", show_alert=True)
            return
        bot.edit_message_text("نوع محتوا را انتخاب کنید:", call.message.chat.id, call.message.message_id, 
                              reply_markup=content_type_menu("send"))

    # زمان‌بندی
    elif data == "schedule_post":
        if not get_channel():
            bot.answer_callback_query(call.id, "اول کانال را تنظیم کنید", show_alert=True)
            return
        bot.edit_message_text("نوع محتوا برای زمان‌بندی:", call.message.chat.id, call.message.message_id, 
                              reply_markup=content_type_menu("sch"))

    # انتخاب نوع محتوا
    elif data.startswith("send_") or data.startswith("sch_"):
        mode, ctype = data.split("_", 1)
        bot.user_steps[uid] = {"step": f"{mode}_{ctype}"}
        bot.edit_message_text(f"محتوای {ctype} را بفرستید:", call.message.chat.id, call.message.message_id)

    # بعد از گرفتن محتوا → انتخاب با دکمه یا بدون دکمه
    elif data.endswith("_withbtn") or data.endswith("_nobtn"):
        use_btn = data.endswith("_withbtn")
        prefix = data.replace("_withbtn", "").replace("_nobtn", "")
        # این قسمت در هندلر پیام کامل می‌شود
        bot.user_steps[uid]["use_buttons"] = use_btn
        bot.user_steps[uid]["step"] = f"confirm_{prefix}"
        bot.answer_callback_query(call.id, "حالا محتوا را بفرستید" if "confirm" not in bot.user_steps[uid]["step"] else "تأیید شد")

    # پین و حذف
    elif data == "pin_delete_menu":
        bot.edit_message_text("پین یا حذف پست:", call.message.chat.id, call.message.message_id, reply_markup=pin_delete_menu())

    elif data == "pin_post":
        bot.user_steps[uid] = {"step": "pin_msgid"}
        bot.edit_message_text("آیدی پیامی که می‌خواهید پین شود را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "delete_post":
        bot.user_steps[uid] = {"step": "delete_msgid"}
        bot.edit_message_text("آیدی پیامی که می‌خواهید حذف شود را بفرستید:", call.message.chat.id, call.message.message_id)

    # پنل ادمین
    elif data == "admin_panel":
        bot.edit_message_text("👑 پنل ادمین:", call.message.chat.id, call.message.message_id, reply_markup=admin_menu())

    elif data == "list_scheduled":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, content_type, send_time FROM scheduled_posts WHERE status='pending' ORDER BY send_time")
        rows = c.fetchall()
        conn.close()
        if not rows:
            bot.send_message(call.message.chat.id, "هیچ پست زمان‌بندی‌شده‌ای نیست.")
        else:
            text = "📋 **پست‌های در انتظار:**\n\n"
            m = InlineKeyboardMarkup()
            for r in rows:
                text += f"#{r[0]} | {r[1]} | {r[2]}\n"
                m.add(InlineKeyboardButton(f"❌ لغو #{r[0]}", callback_data=f"cancel_sch_{r[0]}"))
            m.add(InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel"))
            bot.send_message(call.message.chat.id, text, reply_markup=m, parse_mode="Markdown")

    elif data.startswith("cancel_sch_"):
        sid = int(data.split("_")[2])
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE scheduled_posts SET status='canceled' WHERE id=?", (sid,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, f"پست #{sid} لغو شد", show_alert=True)

    elif data == "clear_scheduled":
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM scheduled_posts WHERE status='pending'")
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "همه پاک شدند", show_alert=True)

    bot.answer_callback_query(call.id)

print("✅ بخش ۱ آماده - بخش ۲ را دقیقاً زیر این کد پیست کنید")
# ==================== بخش ۲ ====================

def build_markup(buttons_list):
    if not buttons_list:
        return None
    markup = InlineKeyboardMarkup(row_width=1)
    for btn in buttons_list:
        markup.add(InlineKeyboardButton(btn["text"], url=btn["url"]))
    return markup

def send_to_channel(channel, content_type, file_id=None, text=None, caption=None, buttons=None):
    if content_type == "text":
        return bot.send_message(channel, text, reply_markup=buttons, parse_mode="Markdown")
    elif content_type == "photo":
        return bot.send_photo(channel, file_id, caption=caption, reply_markup=buttons)
    elif content_type == "animation":
        return bot.send_animation(channel, file_id, caption=caption, reply_markup=buttons)
    elif content_type == "voice":
        return bot.send_voice(channel, file_id, caption=caption, reply_markup=buttons)
    elif content_type == "sticker":
        return bot.send_sticker(channel, file_id, reply_markup=buttons)

# ----------------- هندلر همه پیام‌ها -----------------
@bot.message_handler(content_types=['text', 'photo', 'animation', 'voice', 'sticker'])
def handle_all(message):
    uid = message.from_user.id
    if not is_admin(uid):
        return

    bot.user_steps = getattr(bot, "user_steps", {})
    step_data = bot.user_steps.get(uid, {})
    step = step_data.get("step")
    channel = get_channel()

    # ----- تنظیم کانال -----
    if step == "waiting_channel":
        set_setting("channel_id", message.text.strip())
        bot.user_steps[uid] = {}
        bot.send_message(message.chat.id, f"✅ کانال تنظیم شد:\n`{message.text.strip()}`",
                         parse_mode="Markdown", reply_markup=main_menu())
        return

    # ----- تنظیم دکمه‌ها -----
    if step == "waiting_buttons":
        lines = message.text.strip().split("\n")
        buttons = []
        for line in lines:
            if " - " in line:
                parts = line.split(" - ", 1)
                if len(parts) == 2 and parts[1].startswith("http"):
                    buttons.append({"text": parts[0].strip(), "url": parts[1].strip()})
        if buttons:
            user_buttons[uid] = buttons
            bot.send_message(message.chat.id, f"✅ {len(buttons)} دکمه ذخیره شد.", reply_markup=main_menu())
        else:
            bot.send_message(message.chat.id, "❌ فرمت اشتباه است.\nمثال:\nعضویت - https://t.me/example")
        bot.user_steps[uid] = {}
        return

    # ----- پین پست -----
    if step == "pin_msgid":
        try:
            msg_id = int(message.text.strip())
            bot.pin_chat_message(channel, msg_id)
            bot.send_message(message.chat.id, "✅ پست پین شد.", reply_markup=main_menu())
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا: {e}")
        bot.user_steps[uid] = {}
        return

    # ----- حذف پست -----
    if step == "delete_msgid":
        try:
            msg_id = int(message.text.strip())
            bot.delete_message(channel, msg_id)
            bot.send_message(message.chat.id, "✅ پست حذف شد.", reply_markup=main_menu())
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا: {e}")
        bot.user_steps[uid] = {}
        return

    # ----- دریافت محتوا برای ارسال لحظه‌ای -----
    if step and step.startswith("send_"):
        content_type = step.replace("send_", "")
        # ذخیره موقت محتوا
        temp = {"content_type": content_type, "file_id": None, "text": None, "caption": None}
        if content_type == "text":
            temp["text"] = message.text
        elif content_type == "photo":
            temp["file_id"] = message.photo[-1].file_id
            temp["caption"] = message.caption
        elif content_type == "animation":
            temp["file_id"] = message.animation.file_id
            temp["caption"] = message.caption
        elif content_type == "voice":
            temp["file_id"] = message.voice.file_id
            temp["caption"] = message.caption
        elif content_type == "sticker":
            temp["file_id"] = message.sticker.file_id

        bot.user_steps[uid] = {"step": "choose_btn_send", "temp": temp}
        bot.send_message(message.chat.id, "آیا با دکمه شیشه‌ای ارسال شود؟",
                         reply_markup=with_or_without_buttons("dosend"))
        return

    # ----- دریافت محتوا برای زمان‌بندی -----
    if step and step.startswith("sch_"):
        content_type = step.replace("sch_", "")
        temp = {"content_type": content_type, "file_id": None, "text": None, "caption": None}
        if content_type == "text":
            temp["text"] = message.text
        elif content_type == "photo":
            temp["file_id"] = message.photo[-1].file_id
            temp["caption"] = message.caption
        elif content_type == "animation":
            temp["file_id"] = message.animation.file_id
            temp["caption"] = message.caption
        elif content_type == "voice":
            temp["file_id"] = message.voice.file_id
            temp["caption"] = message.caption
        elif content_type == "sticker":
            temp["file_id"] = message.sticker.file_id

        bot.user_steps[uid] = {"step": "choose_btn_sch", "temp": temp}
        bot.send_message(message.chat.id, "آیا این پست زمان‌بندی‌شده با دکمه شیشه‌ای باشد؟",
                         reply_markup=with_or_without_buttons("dosch"))
        return

    # اگر هیچ مرحله‌ای فعال نبود
    bot.send_message(message.chat.id, "از منو استفاده کنید:", reply_markup=main_menu())


# ----------------- ادامه کال‌بک (انتخاب با/بدون دکمه) -----------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("dosend_") or call.data.startswith("dosch_"))
def button_choice(call):
    uid = call.from_user.id
    if not is_admin(uid):
        return

    bot.user_steps = getattr(bot, "user_steps", {})
    step_data = bot.user_steps.get(uid, {})
    if not step_data:
        bot.answer_callback_query(call.id, "مجدد تلاش کنید")
        return

    use_buttons = call.data.endswith("_withbtn")
    temp = step_data.get("temp", {})
    channel = get_channel()
    buttons_list = user_buttons.get(uid, []) if use_buttons else []
    markup = build_markup(buttons_list)

    # ----- ارسال لحظه‌ای -----
    if call.data.startswith("dosend_"):
        try:
            send_to_channel(
                channel=channel,
                content_type=temp["content_type"],
                file_id=temp.get("file_id"),
                text=temp.get("text"),
                caption=temp.get("caption"),
                buttons=markup
            )
            status = "با دکمه" if use_buttons else "بدون دکمه"
            bot.edit_message_text(f"✅ پست {status} با موفقیت ارسال شد.", call.message.chat.id, call.message.message_id,
                                  reply_markup=main_menu())
        except Exception as e:
            bot.edit_message_text(f"❌ خطا: {e}", call.message.chat.id, call.message.message_id, reply_markup=main_menu())
        bot.user_steps[uid] = {}

    # ----- زمان‌بندی -----
    elif call.data.startswith("dosch_"):
        bot.user_steps[uid] = {
            "step": "waiting_schedule_time",
            "temp": temp,
            "use_buttons": use_buttons
        }
        bot.edit_message_text(
            "⏰ ساعت ارسال را بفرستید:\n\n"
            "فرمت:\n`14:30` (امروز)\n`2026-08-10 14:30` (تاریخ کامل)",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    bot.answer_callback_query(call.id)


# ----------------- دریافت ساعت زمان‌بندی -----------------
@bot.message_handler(func=lambda m: getattr(bot, "user_steps", {}).get(m.from_user.id, {}).get("step") == "waiting_schedule_time")
def get_schedule_time(message):
    uid = message.from_user.id
    if not is_admin(uid):
        return

    step_data = bot.user_steps.get(uid, {})
    temp = step_data.get("temp", {})
    use_buttons = step_data.get("use_buttons", False)
    channel = get_channel()

    try:
        time_text = message.text.strip()
        now = datetime.now()
        if len(time_text) <= 5:
            hour, minute = map(int, time_text.split(":"))
            send_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if send_time <= now:
                send_time += timedelta(days=1)
        else:
            send_time = datetime.strptime(time_text, "%Y-%m-%d %H:%M")

        buttons_json = json.dumps(user_buttons.get(uid, []) if use_buttons else [])

        conn = get_db()
        c = conn.cursor()
        c.execute('''INSERT INTO scheduled_posts 
            (channel_id, content_type, file_id, text_content, caption, buttons, send_time, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')''',
            (channel, temp["content_type"], temp.get("file_id"), temp.get("text"),
             temp.get("caption"), buttons_json, send_time.strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        sid = c.lastrowid
        conn.close()

        bot.send_message(message.chat.id,
            f"✅ پست زمان‌بندی شد\nشماره: #{sid}\nزمان: {send_time.strftime('%Y-%m-%d %H:%M')}",
            reply_markup=main_menu())
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطا در زمان: {e}")

    bot.user_steps[uid] = {}


# ----------------- ترد زمان‌بندی -----------------
def scheduler_worker():
    while True:
        try:
            conn = get_db()
            c = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute("SELECT * FROM scheduled_posts WHERE status='pending' AND send_time <= ?", (now,))
            rows = c.fetchall()

            for row in rows:
                try:
                    buttons_list = json.loads(row[6]) if row[6] else []
                    markup = build_markup(buttons_list)
                    send_to_channel(
                        channel=row[1],
                        content_type=row[2],
                        file_id=row[3],
                        text=row[4],
                        caption=row[5],
                        buttons=markup
                    )
                    c.execute("UPDATE scheduled_posts SET status='sent' WHERE id=?", (row[0],))
                    conn.commit()
                    print(f"✅ زمان‌بندی #{row[0]} ارسال شد")
                except Exception as e:
                    print(f"خطا در #{row[0]}: {e}")
                    c.execute("UPDATE scheduled_posts SET status='error' WHERE id=?", (row[0],))
                    conn.commit()
            conn.close()
        except Exception as e:
            print("Scheduler error:", e)
        time.sleep(25)


# ----------------- اجرا -----------------
threading.Thread(target=scheduler_worker, daemon=True).start()
print("🤖 ربات مدیریت کانال با موفقیت روشن شد...")
bot.infinity_polling()
