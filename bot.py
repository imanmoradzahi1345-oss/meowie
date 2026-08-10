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

# دکمه‌ها و وضعیت استفاده از دکمه
user_buttons = {}      # {user_id: [ {"text": "...", "url": "..."}, ... ]}
use_buttons_flag = {}   # {user_id: True/False}

def get_use_buttons(uid):
    return use_buttons_flag.get(uid, True)  # پیش‌فرض روشن

# ----------------- منوها -----------------
def main_menu(uid):
    use_btn = get_use_buttons(uid)
    btn_status = "روشن ✅" if use_btn else "خاموش ❌"
    
    m = InlineKeyboardMarkup(row_width=2)
    m.add(
        InlineKeyboardButton("📢 تنظیم کانال", callback_data="set_channel"),
        InlineKeyboardButton("🧪 آمار کانال", callback_data="channel_stats"),
    )
    m.add(
        InlineKeyboardButton("📤 ارسال لحظه‌ای", callback_data="send_now"),
        InlineKeyboardButton("⏰ ارسال زمان‌بندی", callback_data="schedule_post"),
    )
    m.add(
        InlineKeyboardButton("🔘 مدیریت دکمه‌ها", callback_data="buttons_menu"),
        InlineKeyboardButton(f"دکمه شیشه‌ای: {btn_status}", callback_data="toggle_buttons"),
    )
    m.add(
        InlineKeyboardButton("📌 پین پست", callback_data="pin_post"),
        InlineKeyboardButton("🗑 حذف پست", callback_data="delete_post"),
    )
    m.add(
        InlineKeyboardButton("👑 پنل ادمین", callback_data="admin_panel"),
    )
    return m

def buttons_menu():
    m = InlineKeyboardMarkup(row_width=1)
    m.add(
        InlineKeyboardButton("➕ تنظیم دکمه‌ها", callback_data="set_buttons"),
        InlineKeyboardButton("👁 مشاهده دکمه‌های فعلی", callback_data="view_buttons"),
        InlineKeyboardButton("🧹 پاک کردن همه دکمه‌ها", callback_data="clear_buttons"),
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
    bot.send_message(message.chat.id, 
        "🤖 **ربات مدیریت کانال**\n\nاز دکمه‌های شیشه‌ای زیر استفاده کنید.",
        reply_markup=main_menu(message.from_user.id), parse_mode="Markdown")

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
        bot.edit_message_text("منوی اصلی:", call.message.chat.id, call.message.message_id, 
                              reply_markup=main_menu(uid))

    elif data == "set_channel":
        bot.user_steps[uid] = {"step": "waiting_channel"}
        bot.edit_message_text("📢 آیدی کانال را بفرستید:\n`@channel` یا `-100xxxxxxxxxx`",
                              call.message.chat.id, call.message.message_id, parse_mode="Markdown")

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
                                  reply_markup=main_menu(uid), parse_mode="Markdown")
        except Exception as e:
            bot.answer_callback_query(call.id, f"خطا: {e}", show_alert=True)

    elif data == "buttons_menu":
        bot.edit_message_text("🔘 مدیریت دکمه‌های شیشه‌ای:", call.message.chat.id, call.message.message_id, 
                              reply_markup=buttons_menu())

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

    elif data == "toggle_buttons":
        current = get_use_buttons(uid)
        use_buttons_flag[uid] = not current
        status = "روشن شد ✅" if not current else "خاموش شد ❌"
        bot.answer_callback_query(call.id, f"دکمه شیشه‌ای {status}", show_alert=True)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=main_menu(uid))

    elif data == "send_now":
        if not get_channel():
            bot.answer_callback_query(call.id, "اول کانال را تنظیم کنید", show_alert=True)
            return
        bot.user_steps[uid] = {"step": "waiting_content_now"}
        bot.edit_message_text(
            "📤 **ارسال لحظه‌ای**\n\nهر محتوایی بفرستید (متن، عکس، ویدیو، گیف، ویس، استیکر).\nربات خودکار در کانال پست می‌کند.",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif data == "schedule_post":
        if not get_channel():
            bot.answer_callback_query(call.id, "اول کانال را تنظیم کنید", show_alert=True)
            return
        bot.user_steps[uid] = {"step": "waiting_content_sch"}
        bot.edit_message_text(
            "⏰ **ارسال زمان‌بندی**\n\nاول محتوا را بفرستید، بعد ساعت را مشخص می‌کنیم.",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif data == "pin_post":
        bot.user_steps[uid] = {"step": "pin_msgid"}
        bot.edit_message_text("آیدی پیامی که می‌خواهید پین شود را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "delete_post":
        bot.user_steps[uid] = {"step": "delete_msgid"}
        bot.edit_message_text("آیدی پیامی که می‌خواهید حذف شود را بفرستید:", call.message.chat.id, call.message.message_id)

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

def build_markup(uid):
    """ساخت کیبورد شیشه‌ای از دکمه‌های ذخیره‌شده"""
    if not get_use_buttons(uid):
        return None
    buttons = user_buttons.get(uid, [])
    if not buttons:
        return None
    markup = InlineKeyboardMarkup(row_width=1)
    for btn in buttons:
        markup.add(InlineKeyboardButton(btn["text"], url=btn["url"]))
    return markup

def send_to_channel(channel, content_type, file_id=None, text=None, caption=None, buttons=None):
    try:
        if content_type == "text":
            return bot.send_message(channel, text, reply_markup=buttons, parse_mode="Markdown")
        elif content_type == "photo":
            return bot.send_photo(channel, file_id, caption=caption, reply_markup=buttons)
        elif content_type == "video":
            return bot.send_video(channel, file_id, caption=caption, reply_markup=buttons)
        elif content_type == "animation":
            return bot.send_animation(channel, file_id, caption=caption, reply_markup=buttons)
        elif content_type == "voice":
            return bot.send_voice(channel, file_id, caption=caption, reply_markup=buttons)
        elif content_type == "sticker":
            return bot.send_sticker(channel, file_id, reply_markup=buttons)
        elif content_type == "document":
            return bot.send_document(channel, file_id, caption=caption, reply_markup=buttons)
    except Exception as e:
        raise e

# ----------------- هندلر همه نوع محتوا -----------------
@bot.message_handler(content_types=['text', 'photo', 'video', 'animation', 'voice', 'sticker', 'document'])
def handle_content(message):
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
        bot.send_message(message.chat.id, f"✅ کانال با موفقیت تنظیم شد:\n`{message.text.strip()}`",
                         parse_mode="Markdown", reply_markup=main_menu(uid))
        return

    # ----- تنظیم دکمه‌های شیشه‌ای -----
    if step == "waiting_buttons":
        lines = message.text.strip().split("\n")
        buttons = []
        for line in lines:
            if " - " in line:
                parts = line.split(" - ", 1)
                if len(parts) == 2 and (parts[1].startswith("http://") or parts[1].startswith("https://")):
                    buttons.append({"text": parts[0].strip(), "url": parts[1].strip()})
        
        if buttons:
            user_buttons[uid] = buttons
            text = f"✅ {len(buttons)} دکمه شیشه‌ای ذخیره شد:\n\n"
            for i, b in enumerate(buttons, 1):
                text += f"{i}. {b['text']}\n"
            bot.send_message(message.chat.id, text, reply_markup=main_menu(uid))
        else:
            bot.send_message(message.chat.id, 
                "❌ فرمت اشتباه است.\n\nدرست بنویس:\n`متن دکمه - https://t.me/example`",
                parse_mode="Markdown")
        bot.user_steps[uid] = {}
        return

    # ----- پین پست -----
    if step == "pin_msgid":
        try:
            msg_id = int(message.text.strip())
            bot.pin_chat_message(channel, msg_id)
            bot.send_message(message.chat.id, "✅ پست با موفقیت پین شد.", reply_markup=main_menu(uid))
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا در پین کردن:\n{e}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ----- حذف پست -----
    if step == "delete_msgid":
        try:
            msg_id = int(message.text.strip())
            bot.delete_message(channel, msg_id)
            bot.send_message(message.chat.id, "✅ پست با موفقیت حذف شد.", reply_markup=main_menu(uid))
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا در حذف:\n{e}", reply_markup=main_menu(uid))
        bot.user_steps[uid] = {}
        return

    # ----- ارسال لحظه‌ای (هر محتوایی) -----
    if step == "waiting_content_now":
        if not channel:
            bot.send_message(message.chat.id, "اول کانال را تنظیم کنید.", reply_markup=main_menu(uid))
            bot.user_steps[uid] = {}
            return

        try:
            buttons = build_markup(uid)
            content_type = message.content_type

            if content_type == "text":
                send_to_channel(channel, "text", text=message.text, buttons=buttons)
            elif content_type == "photo":
                send_to_channel(channel, "photo", file_id=message.photo[-1].file_id, 
                                caption=message.caption, buttons=buttons)
            elif content_type == "video":
                send_to_channel(channel, "video", file_id=message.video.file_id, 
                                caption=message.caption, buttons=buttons)
            elif content_type == "animation":
                send_to_channel(channel, "animation", file_id=message.animation.file_id, 
                                caption=message.caption, buttons=buttons)
            elif content_type == "voice":
                send_to_channel(channel, "voice", file_id=message.voice.file_id, 
                                caption=message.caption, buttons=buttons)
            elif content_type == "sticker":
                send_to_channel(channel, "sticker", file_id=message.sticker.file_id, buttons=buttons)
            elif content_type == "document":
                send_to_channel(channel, "document", file_id=message.document.file_id, 
                                caption=message.caption, buttons=buttons)
            else:
                bot.send_message(message.chat.id, "این نوع محتوا پشتیبانی نمی‌شود.")
                return

            status = "با دکمه شیشه‌ای" if get_use_buttons(uid) and user_buttons.get(uid) else "بدون دکمه"
            bot.send_message(message.chat.id, f"✅ پست با موفقیت ارسال شد ({status})", reply_markup=main_menu(uid))
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا در ارسال به کانال:\n{e}", reply_markup=main_menu(uid))
        
        bot.user_steps[uid] = {}
        return

    # ----- شروع زمان‌بندی (دریافت محتوا) -----
    if step == "waiting_content_sch":
        temp = {
            "content_type": message.content_type,
            "file_id": None,
            "text": None,
            "caption": None
        }
        if message.content_type == "text":
            temp["text"] = message.text
        elif message.content_type == "photo":
            temp["file_id"] = message.photo[-1].file_id
            temp["caption"] = message.caption
        elif message.content_type == "video":
            temp["file_id"] = message.video.file_id
            temp["caption"] = message.caption
        elif message.content_type == "animation":
            temp["file_id"] = message.animation.file_id
            temp["caption"] = message.caption
        elif message.content_type == "voice":
            temp["file_id"] = message.voice.file_id
            temp["caption"] = message.caption
        elif message.content_type == "sticker":
            temp["file_id"] = message.sticker.file_id
        elif message.content_type == "document":
            temp["file_id"] = message.document.file_id
            temp["caption"] = message.caption

        bot.user_steps[uid] = {"step": "waiting_schedule_time", "temp": temp}
        bot.send_message(message.chat.id,
            "⏰ ساعت ارسال را بفرستید:\n\n"
            "فرمت‌های قابل قبول:\n"
            "`18:30`           ← امروز\n"
            "`2026-08-10 18:30` ← تاریخ کامل",
            parse_mode="Markdown")
        return

    # ----- دریافت ساعت زمان‌بندی -----
    if step == "waiting_schedule_time":
        try:
            time_text = message.text.strip()
            now = datetime.now()

            if len(time_text) <= 5:  # فقط ساعت
                hour, minute = map(int, time_text.split(":"))
                send_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if send_time <= now:
                    send_time += timedelta(days=1)
            else:
                send_time = datetime.strptime(time_text, "%Y-%m-%d %H:%M")

            temp = step_data["temp"]
            buttons_json = json.dumps(user_buttons.get(uid, []) if get_use_buttons(uid) else [])

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
                f"✅ پست زمان‌بندی شد\n\n"
                f"شماره: #{sid}\n"
                f"زمان ارسال: `{send_time.strftime('%Y-%m-%d %H:%M')}`",
                parse_mode="Markdown", reply_markup=main_menu(uid))
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا در ثبت زمان:\n{e}", reply_markup=main_menu(uid))

        bot.user_steps[uid] = {}
        return

    # اگر هیچ مرحله‌ای فعال نبود
    bot.send_message(message.chat.id, "از منوی شیشه‌ای استفاده کنید:", reply_markup=main_menu(uid))


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
                    markup = None
                    if buttons_list:
                        markup = InlineKeyboardMarkup(row_width=1)
                        for btn in buttons_list:
                            markup.add(InlineKeyboardButton(btn["text"], url=btn["url"]))

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
                    print(f"✅ پست زمان‌بندی #{row[0]} ارسال شد")
                except Exception as e:
                    print(f"❌ خطا در پست #{row[0]}: {e}")
                    c.execute("UPDATE scheduled_posts SET status='error' WHERE id=?", (row[0],))
                    conn.commit()
            conn.close()
        except Exception as e:
            print("Scheduler Error:", e)

        time.sleep(20)


# ----------------- اجرا -----------------
threading.Thread(target=scheduler_worker, daemon=True).start()
print("🤖 ربات مدیریت کانال با موفقیت روشن شد...")
bot.infinity_polling()
