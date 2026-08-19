import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import threading
import time
import sqlite3

# ========== تنظیمات ==========
BOT_TOKEN = "8875102057:AAE5JvIk9HhGoeizZhYUjyRvSdCRIsEzoxU"
ADMIN_ID = 7530457395

bot = telebot.TeleBot(BOT_TOKEN)

counter_state = {
    "running": False,
    "channel": None,
    "interval": 6,
    "current": 0,
    "thread": None
}

def get_db():
    return sqlite3.connect("counter_bot.db", check_same_thread=False)

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    c.execute("SELECT value FROM settings WHERE key='channel'")
    row = c.fetchone()
    if row:
        counter_state["channel"] = row[0]
    c.execute("SELECT value FROM settings WHERE key='interval'")
    row = c.fetchone()
    if row:
        counter_state["interval"] = int(row[0])
    c.execute("SELECT value FROM settings WHERE key='current'")
    row = c.fetchone()
    if row:
        counter_state["current"] = int(row[0])
    conn.commit()
    conn.close()

init_db()

def save_setting(key, value):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def is_admin(uid):
    return uid == ADMIN_ID

def main_menu():
    m = InlineKeyboardMarkup(row_width=1)
    status = "🟢 روشن" if counter_state["running"] else "🔴 خاموش"
    ch = counter_state["channel"] or "تنظیم نشده"
    m.add(InlineKeyboardButton(f"وضعیت: {status}", callback_data="status"))
    m.add(InlineKeyboardButton(f"📢 کانال: {ch}", callback_data="set_channel"))
    m.add(InlineKeyboardButton(f"⏱ سرعت: هر {counter_state['interval']} ثانیه", callback_data="set_speed"))
    m.add(InlineKeyboardButton(f"🔢 عدد فعلی: {counter_state['current']}", callback_data="noop"))
    if counter_state["running"]:
        m.add(InlineKeyboardButton("⏹ توقف", callback_data="stop"))
    else:
        m.add(InlineKeyboardButton("▶️ شروع شمارش", callback_data="start"))
    m.add(InlineKeyboardButton("🔄 ریست عدد به ۰", callback_data="reset"))
    return m

def counter_worker():
    while counter_state["running"]:
        try:
            if not counter_state["channel"]:
                break
            counter_state["current"] += 1
            save_setting("current", counter_state["current"])
            bot.send_message(counter_state["channel"], str(counter_state["current"]))
        except Exception as e:
            try:
                bot.send_message(ADMIN_ID, f"❌ خطا در ارسال:\n{e}")
            except:
                pass
            time.sleep(3)
        time.sleep(counter_state["interval"])

@bot.message_handler(commands=['start'])
def start(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "فقط ادمین می‌تونه از این ربات استفاده کنه.")
        return
    if message.chat.type != "private":
        bot.reply_to(message, "فقط در پیوی ربات کار می‌کنه.")
        return

    text = """
🔢 **ربات شمارنده کانال**

۱. ربات رو تو کانال ادمین کن
۲. کانال رو تنظیم کن
۳. سرعت رو مشخص کن
۴. شروع شمارش رو بزن

ربات بدون توقف عدد می‌فرسته.
"""
    bot.reply_to(message, text, parse_mode="Markdown", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "دسترسی نداری", show_alert=True)
        return
    if call.message.chat.type != "private":
        bot.answer_callback_query(call.id, "فقط پیوی", show_alert=True)
        return

    data = call.data

    if data == "status":
        bot.answer_callback_query(call.id)

    elif data == "set_channel":
        bot.edit_message_text(
            "📢 آیدی یا یوزرنیم کانال را بفرست:\n\n"
            "مثال:\n"
            "`@mychannel`\n"
            "یا\n"
            "`-1001234567890`\n\n"
            "نکته: ربات باید ادمین کانال باشد.",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown"
        )
        bot.register_next_step_handler(call.message, save_channel)

    elif data == "set_speed":
        bot.edit_message_text(
            "⏱ سرعت را به ثانیه بفرست:\n\n"
            "مثال: `6` یعنی هر ۶ ثانیه یک عدد\n"
            "حداقل: ۱ ثانیه",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown"
        )
        bot.register_next_step_handler(call.message, save_speed)

    elif data == "start":
        if not counter_state["channel"]:
            bot.answer_callback_query(call.id, "اول کانال را تنظیم کن!", show_alert=True)
            return
        if counter_state["running"]:
            bot.answer_callback_query(call.id, "قبلاً روشنه!", show_alert=True)
            return

        counter_state["running"] = True
        t = threading.Thread(target=counter_worker, daemon=True)
        counter_state["thread"] = t
        t.start()
        bot.answer_callback_query(call.id, "شمارش شروع شد ✅", show_alert=True)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=main_menu())

    elif data == "stop":
        counter_state["running"] = False
        bot.answer_callback_query(call.id, "متوقف شد ⏹", show_alert=True)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=main_menu())

    elif data == "reset":
        counter_state["current"] = 0
        save_setting("current", 0)
        bot.answer_callback_query(call.id, "عدد ریست شد به ۰", show_alert=True)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=main_menu())

    elif data == "noop":
        bot.answer_callback_query(call.id)

def save_channel(message):
    if not is_admin(message.from_user.id):
        return
    ch = message.text.strip()
    try:
        chat = bot.get_chat(ch)
        test_msg = bot.send_message(ch, "✅ ربات متصل شد و آماده شمارش است.")
        try:
            bot.delete_message(ch, test_msg.message_id)
        except:
            pass

        counter_state["channel"] = ch
        save_setting("channel", ch)
        bot.reply_to(message, f"✅ کانال تنظیم شد:\n{chat.title}\n`{ch}`", parse_mode="Markdown", reply_markup=main_menu())
    except Exception as e:
        bot.reply_to(message, f"❌ خطا:\n{e}\n\nمطمئن شو ربات ادمین کانال است و آیدی درست است.", reply_markup=main_menu())

def save_speed(message):
    if not is_admin(message.from_user.id):
        return
    try:
        sec = int(message.text.strip())
        if sec < 1:
            bot.reply_to(message, "حداقل ۱ ثانیه باید باشد.")
            return
        counter_state["interval"] = sec
        save_setting("interval", sec)
        bot.reply_to(message, f"✅ سرعت تنظیم شد: هر {sec} ثانیه", reply_markup=main_menu())
    except:
        bot.reply_to(message, "فقط عدد بفرست (مثال: 6)")

print("🔢 ربات شمارنده روشن شد")
bot.infinity_polling()
