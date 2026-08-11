# ==================== بخش ۱ از ۴ ====================
# تنظیمات + دیتابیس + توابع پایه + منوها

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
import sqlite3
import threading
import time
import json
from datetime import datetime, timedelta

# سعی می‌کنیم از zoneinfo استفاده کنیم (وقت ایران)
try:
    from zoneinfo import ZoneInfo
    TEHRAN = ZoneInfo("Asia/Tehran")
except:
    TEHRAN = None  # اگر پشتیبانی نشد از ساعت سیستم استفاده می‌شه

BOT_TOKEN = "8924668463:AAH7rV1LMZZ6Amn3JEQV6SRHeEM9KwI6lgA"
ADMIN_IDS = [7530457395]

bot = telebot.TeleBot(BOT_TOKEN)

# ----------------- دیتابیس -----------------
def init_db():
    conn = sqlite3.connect("advanced_channel.db")
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS channel_stats (
        channel_id TEXT PRIMARY KEY,
        last_members INTEGER,
        last_check TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS scheduled_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT,
        content_type TEXT,
        file_id TEXT,
        text_content TEXT,
        caption TEXT,
        buttons TEXT,
        send_time TEXT,
        status TEXT DEFAULT 'pending'
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        content TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT,
        details TEXT,
        created_at TEXT
    )''')
    
    # تنظیمات پیش‌فرض
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('footer', '')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('use_buttons', '1')")
    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect("advanced_channel.db")

def is_admin(uid):
    return uid in ADMIN_IDS

def get_setting(key, default=""):
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

def log_action(action, details=""):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO logs (action, details, created_at) VALUES (?, ?, ?)",
              (action, details, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def now_tehran():
    if TEHRAN:
        return datetime.now(TEHRAN)
    return datetime.now()

# دکمه‌های شیشه‌ای فعلی
user_buttons = {}  # {user_id: [{"text": "...", "url": "..."}]}

def get_use_buttons():
    return get_setting("use_buttons", "1") == "1"

def build_markup(uid=None):
    if not get_use_buttons():
        return None
    buttons = user_buttons.get(uid or ADMIN_IDS[0], [])
    if not buttons:
        return None
    markup = InlineKeyboardMarkup(row_width=1)
    for btn in buttons:
        markup.add(InlineKeyboardButton(btn["text"], url=btn["url"]))
    return markup

# ----------------- منوها -----------------
def main_menu():
    use_btn = "روشن ✅" if get_use_buttons() else "خاموش ❌"
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
        InlineKeyboardButton(f"دکمه شیشه‌ای: {use_btn}", callback_data="toggle_buttons"),
    )
    m.add(
        InlineKeyboardButton("📌 پین پست", callback_data="pin_post"),
        InlineKeyboardButton("🗑 حذف پست", callback_data="delete_post"),
    )
    m.add(
        InlineKeyboardButton("📝 قالب‌ها", callback_data="templates_menu"),
        InlineKeyboardButton("✍️ تنظیم امضا", callback_data="set_footer"),
    )
    m.add(
        InlineKeyboardButton("⭐ پرداخت استارز", callback_data="payment"),
        InlineKeyboardButton("📋 لاگ‌ها", callback_data="show_logs"),
    )
    m.add(
        InlineKeyboardButton("👑 پنل ادمین", callback_data="admin_panel"),
    )
    return m

def buttons_menu():
    m = InlineKeyboardMarkup(row_width=1)
    m.add(
        InlineKeyboardButton("➕ اضافه کردن دکمه", callback_data="add_button"),
        InlineKeyboardButton("👁 مشاهده دکمه‌ها", callback_data="view_buttons"),
        InlineKeyboardButton("🧹 پاک کردن همه", callback_data="clear_buttons"),
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

def templates_menu():
    m = InlineKeyboardMarkup(row_width=1)
    m.add(
        InlineKeyboardButton("➕ اضافه کردن قالب", callback_data="add_template"),
        InlineKeyboardButton("📋 لیست قالب‌ها", callback_data="list_templates"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"),
    )
    return m

print("✅ بخش ۱ لود شد - منتظر بخش ۲ باش")
# ==================== بخش ۲ از ۴ ====================
# کال‌بک‌ها و مدیریت منوها

@bot.message_handler(commands=['start'])
def start(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔️ شما ادمین نیستید.")
        return
    bot.send_message(
        message.chat.id,
        "🤖 **ربات پیشرفته مدیریت کانال**\n\nاز دکمه‌های زیر استفاده کنید.",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    uid = call.from_user.id
    if not is_admin(uid):
        bot.answer_callback_query(call.id, "دسترسی ندارید", show_alert=True)
        return

    data = call.data
    bot.user_steps = getattr(bot, "user_steps", {})

    # ---------- بازگشت ----------
    if data == "back_main":
        bot.edit_message_text("منوی اصلی:", call.message.chat.id, call.message.message_id, reply_markup=main_menu())

    # ---------- تنظیم کانال ----------
    elif data == "set_channel":
        bot.user_steps[uid] = {"step": "waiting_channel"}
        bot.edit_message_text(
            "📢 آیدی کانال را بفرستید:\nمثال: `@channelname` یا `-100xxxxxxxxxx`",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown"
        )

    # ---------- آمار کانال ----------
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
                if diff > 0:
                    growth = f"📈 رشد: **+{diff}**"
                elif diff < 0:
                    growth = f"📉 کاهش: **{diff}**"
                else:
                    growth = "➖ بدون تغییر"
                last_check = row[1]
            else:
                growth = "اولین بررسی"
                last_check = "—"

            now_str = now_tehran().strftime("%Y-%m-%d %H:%M")
            c.execute("INSERT OR REPLACE INTO channel_stats (channel_id, last_members, last_check) VALUES (?, ?, ?)",
                      (str(channel), members, now_str))
            conn.commit()
            conn.close()

            text = f"""
🧪 **آمار کانال**

📌 نام: {chat.title}
🆔 آیدی: `{chat.id}`
👥 تعداد اعضا: **{members:,}**
👑 تعداد ادمین‌ها: **{admin_count}**

{growth}
آخرین بررسی قبلی: {last_check}
⏰ زمان فعلی (ایران): {now_str}
"""
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  reply_markup=main_menu(), parse_mode="Markdown")
            log_action("channel_stats", f"members={members}")
        except Exception as e:
            bot.answer_callback_query(call.id, f"خطا: {e}", show_alert=True)

    # ---------- مدیریت دکمه‌ها ----------
    elif data == "buttons_menu":
        bot.edit_message_text("🔘 مدیریت دکمه‌های شیشه‌ای:", call.message.chat.id, call.message.message_id, reply_markup=buttons_menu())

    elif data == "add_button":
        bot.user_steps[uid] = {"step": "waiting_btn_text"}
        bot.edit_message_text("✏️ متن دکمه را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "view_buttons":
        btns = user_buttons.get(uid, [])
        if not btns:
            text = "هیچ دکمه‌ای تنظیم نشده است."
        else:
            text = "🔘 **دکمه‌های فعلی:**\n\n"
            for i, b in enumerate(btns, 1):
                text += f"{i}. {b['text']}\n   🔗 {b['url']}\n\n"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                              reply_markup=buttons_menu(), parse_mode="Markdown")

    elif data == "clear_buttons":
        user_buttons[uid] = []
        bot.answer_callback_query(call.id, "✅ همه دکمه‌ها پاک شدند", show_alert=True)
        log_action("clear_buttons")

    elif data == "toggle_buttons":
        current = get_use_buttons()
        new_val = "0" if current else "1"
        set_setting("use_buttons", new_val)
        status = "روشن شد ✅" if new_val == "1" else "خاموش شد ❌"
        bot.answer_callback_query(call.id, f"دکمه‌های شیشه‌ای {status}", show_alert=True)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=main_menu())

    # ---------- ارسال لحظه‌ای ----------
    elif data == "send_now":
        if not get_channel():
            bot.answer_callback_query(call.id, "اول کانال را تنظیم کنید", show_alert=True)
            return
        bot.user_steps[uid] = {"step": "waiting_content_now"}
        bot.edit_message_text(
            "📤 **ارسال لحظه‌ای**\n\nهر محتوایی بفرستید (متن، عکس، ویدیو، گیف، ویس، استیکر، فایل).\nربات خودکار آن را در کانال ارسال می‌کند.",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown"
        )

    # ---------- زمان‌بندی ----------
    elif data == "schedule_post":
        if not get_channel():
            bot.answer_callback_query(call.id, "اول کانال را تنظیم کنید", show_alert=True)
            return
        bot.user_steps[uid] = {"step": "waiting_content_sch"}
        bot.edit_message_text(
            "⏰ **ارسال زمان‌بندی‌شده**\n\nاول محتوا را بفرستید، سپس ساعت را مشخص می‌کنیم.\n(وقت ایران)",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown"
        )

    # ---------- پین و حذف ----------
    elif data == "pin_post":
        bot.user_steps[uid] = {"step": "pin_msgid"}
        bot.edit_message_text("📌 آیدی پیامی که می‌خواهید پین شود را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "delete_post":
        bot.user_steps[uid] = {"step": "delete_msgid"}
        bot.edit_message_text("🗑 آیدی پیامی که می‌خواهید حذف شود را بفرستید:", call.message.chat.id, call.message.message_id)

    # ---------- قالب‌ها ----------
    elif data == "templates_menu":
        bot.edit_message_text("📝 مدیریت قالب‌ها:", call.message.chat.id, call.message.message_id, reply_markup=templates_menu())

    elif data == "add_template":
        bot.user_steps[uid] = {"step": "waiting_template_name"}
        bot.edit_message_text("نام قالب را بفرستید:", call.message.chat.id, call.message.message_id)

    elif data == "list_templates":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, name FROM templates ORDER BY id DESC")
        rows = c.fetchall()
        conn.close()
        if not rows:
            bot.send_message(call.message.chat.id, "هیچ قالبی وجود ندارد.")
        else:
            text = "📋 **لیست قالب‌ها:**\n\n"
            for r in rows:
                text += f"#{r[0]} - {r[1]}\n"
            bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

    # ---------- امضا ----------
    elif data == "set_footer":
        bot.user_steps[uid] = {"step": "waiting_footer"}
        current = get_setting("footer")
        bot.edit_message_text(
            f"✍️ امضای فعلی:\n`{current or 'خالی'}`\n\nامضای جدید را بفرستید (یا کلمه `خالی` برای پاک کردن):",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown"
        )

    # ---------- پرداخت استارز ----------
    elif data == "payment":
        bot.user_steps[uid] = {"step": "waiting_stars_amount"}
        bot.edit_message_text(
            "⭐ **پرداخت استارز**\n\nتعداد استارزی که می‌خواهید پرداخت شود را به صورت عدد بفرستید:\nمثال: `50`",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown"
        )

    # ---------- لاگ‌ها ----------
    elif data == "show_logs":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT action, details, created_at FROM logs ORDER BY id DESC LIMIT 15")
        rows = c.fetchall()
        conn.close()
        if not rows:
            text = "هنوز لاگی ثبت نشده."
        else:
            text = "📋 **آخرین لاگ‌ها:**\n\n"
            for r in rows:
                text += f"• {r[0]} | {r[2]}\n  {r[1][:40]}\n"
        bot.send_message(call.message.chat.id, text)

    # ---------- پنل ادمین ----------
    elif data == "admin_panel":
        bot.edit_message_text("👑 پنل ادمین:", call.message.chat.id, call.message.message_id, reply_markup=admin_menu())

    elif data == "list_scheduled":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, content_type, send_time FROM scheduled_posts WHERE status='pending' ORDER BY send_time")
        rows = c.fetchall()
        conn.close()
        if not rows:
            bot.send_message(call.message.chat.id, "هیچ پست زمان‌بندی‌شده‌ای وجود ندارد.")
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
        log_action("cancel_scheduled", f"id={sid}")

    elif data == "clear_scheduled":
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM scheduled_posts WHERE status='pending'")
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "همه پست‌های زمان‌بندی‌شده پاک شدند", show_alert=True)
        log_action("clear_all_scheduled")

    bot.answer_callback_query(call.id)

print("✅ بخش ۲ لود شد - منتظر بخش ۳ باش")
# ==================== بخش ۳ از ۴ ====================
# هندلر پیام‌ها + ارسال محتوا + زمان‌بندی

def send_to_channel(channel, content_type, file_id=None, text=None, caption=None, buttons=None):
    footer = get_setting("footer")
    if footer and content_type in ["text", "photo", "video", "animation", "document", "voice"]:
        if caption:
            caption = f"{caption}\n\n{footer}"
        elif text:
            text = f"{text}\n\n{footer}"
        else:
            caption = footer

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

@bot.message_handler(content_types=['text', 'photo', 'video', 'animation', 'voice', 'sticker', 'document'])
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
        ch = message.text.strip()
        set_setting("channel_id", ch)
        bot.user_steps[uid] = {}
        bot.send_message(message.chat.id, f"✅ کانال تنظیم شد:\n`{ch}`", parse_mode="Markdown", reply_markup=main_menu())
        log_action("set_channel", ch)
        return

    # ----- اضافه کردن دکمه (مرحله ۱: متن) -----
    if step == "waiting_btn_text":
        bot.user_steps[uid] = {"step": "waiting_btn_url", "btn_text": message.text.strip()}
        bot.send_message(message.chat.id, "حالا لینک دکمه را بفرستید:\n(هر لینکی که با http یا https شروع شود قبول است)")
        return

    # ----- اضافه کردن دکمه (مرحله ۲: لینک) -----
    if step == "waiting_btn_url":
        url = message.text.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            bot.send_message(message.chat.id, "❌ لینک باید با http:// یا https:// شروع شود. دوباره لینک را بفرستید.")
            return
        
        btn_text = step_data.get("btn_text", "دکمه")
        if uid not in user_buttons:
            user_buttons[uid] = []
        user_buttons[uid].append({"text": btn_text, "url": url})
        
        bot.user_steps[uid] = {}
        bot.send_message(message.chat.id, 
            f"✅ دکمه اضافه شد:\nمتن: {btn_text}\nلینک: {url}\n\nتعداد دکمه‌های فعلی: {len(user_buttons[uid])}",
            reply_markup=main_menu())
        log_action("add_button", btn_text)
        return

    # ----- تنظیم امضا -----
    if step == "waiting_footer":
        text = message.text.strip()
        if text == "خالی":
            set_setting("footer", "")
            bot.send_message(message.chat.id, "✅ امضا پاک شد.", reply_markup=main_menu())
        else:
            set_setting("footer", text)
            bot.send_message(message.chat.id, f"✅ امضا تنظیم شد:\n{text}", reply_markup=main_menu())
        bot.user_steps[uid] = {}
        log_action("set_footer")
        return

    # ----- اضافه کردن قالب -----
    if step == "waiting_template_name":
        bot.user_steps[uid] = {"step": "waiting_template_content", "name": message.text.strip()}
        bot.send_message(message.chat.id, "محتوای قالب را بفرستید:")
        return

    if step == "waiting_template_content":
        name = step_data.get("name", "بدون‌نام")
        content = message.text
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO templates (name, content) VALUES (?, ?)", (name, content))
        conn.commit()
        conn.close()
        bot.user_steps[uid] = {}
        bot.send_message(message.chat.id, f"✅ قالب «{name}» ذخیره شد.", reply_markup=main_menu())
        log_action("add_template", name)
        return

    # ----- پین پست -----
    if step == "pin_msgid":
        try:
            msg_id = int(message.text.strip())
            bot.pin_chat_message(channel, msg_id)
            bot.send_message(message.chat.id, "✅ پست پین شد.", reply_markup=main_menu())
            log_action("pin_post", str(msg_id))
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا: {e}", reply_markup=main_menu())
        bot.user_steps[uid] = {}
        return

    # ----- حذف پست -----
    if step == "delete_msgid":
        try:
            msg_id = int(message.text.strip())
            bot.delete_message(channel, msg_id)
            bot.send_message(message.chat.id, "✅ پست حذف شد.", reply_markup=main_menu())
            log_action("delete_post", str(msg_id))
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا: {e}", reply_markup=main_menu())
        bot.user_steps[uid] = {}
        return

    # ----- پرداخت استارز (دریافت تعداد) -----
    if step == "waiting_stars_amount":
        try:
            amount = int(message.text.strip())
            if amount < 1:
                bot.send_message(message.chat.id, "تعداد باید حداقل ۱ باشد.")
                return
            
            prices = [LabeledPrice(label=f"{amount} استارز", amount=amount)]
            bot.send_invoice(
                chat_id=message.chat.id,
                title=f"پرداخت {amount} استارز",
                description="پرداخت با تلگرام استارز\nپس از پرداخت موفق، تأییدیه دریافت می‌کنید.",
                invoice_payload=f"stars_pay_{amount}_{uid}",
                provider_token="",  # برای استارز خالی
                currency="XTR",
                prices=prices
            )
            bot.user_steps[uid] = {}
            log_action("create_invoice", f"amount={amount}")
        except:
            bot.send_message(message.chat.id, "❌ فقط عدد بفرستید.")
        return

    # ----- ارسال لحظه‌ای -----
    if step == "waiting_content_now":
        if not channel:
            bot.send_message(message.chat.id, "اول کانال را تنظیم کنید.", reply_markup=main_menu())
            bot.user_steps[uid] = {}
            return
        try:
            buttons = build_markup(uid)
            ctype = message.content_type

            if ctype == "text":
                send_to_channel(channel, "text", text=message.text, buttons=buttons)
            elif ctype == "photo":
                send_to_channel(channel, "photo", file_id=message.photo[-1].file_id, caption=message.caption, buttons=buttons)
            elif ctype == "video":
                send_to_channel(channel, "video", file_id=message.video.file_id, caption=message.caption, buttons=buttons)
            elif ctype == "animation":
                send_to_channel(channel, "animation", file_id=message.animation.file_id, caption=message.caption, buttons=buttons)
            elif ctype == "voice":
                send_to_channel(channel, "voice", file_id=message.voice.file_id, caption=message.caption, buttons=buttons)
            elif ctype == "sticker":
                send_to_channel(channel, "sticker", file_id=message.sticker.file_id, buttons=buttons)
            elif ctype == "document":
                send_to_channel(channel, "document", file_id=message.document.file_id, caption=message.caption, buttons=buttons)
            else:
                bot.send_message(message.chat.id, "این نوع محتوا پشتیبانی نمی‌شود.")
                return

            status = "با دکمه" if get_use_buttons() and user_buttons.get(uid) else "بدون دکمه"
            bot.send_message(message.chat.id, f"✅ پست ارسال شد ({status})", reply_markup=main_menu())
            log_action("send_now", ctype)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا در ارسال:\n{e}", reply_markup=main_menu())
        bot.user_steps[uid] = {}
        return

    # ----- شروع زمان‌بندی (محتوا) -----
    if step == "waiting_content_sch":
        temp = {"content_type": message.content_type, "file_id": None, "text": None, "caption": None}
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
            "⏰ ساعت ارسال را بفرستید (وقت ایران):\n\n"
            "`18:30`  ← امروز\n"
            "`2026-08-11 18:30`  ← تاریخ کامل",
            parse_mode="Markdown")
        return

    # ----- دریافت ساعت زمان‌بندی -----
    if step == "waiting_schedule_time":
        try:
            time_text = message.text.strip()
            now = now_tehran()

            if len(time_text) <= 5:
                hour, minute = map(int, time_text.split(":"))
                send_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if send_time <= now:
                    send_time += timedelta(days=1)
            else:
                send_time = datetime.strptime(time_text, "%Y-%m-%d %H:%M")
                if TEHRAN:
                    send_time = send_time.replace(tzinfo=TEHRAN)

            temp = step_data["temp"]
            buttons_json = json.dumps(user_buttons.get(uid, []) if get_use_buttons() else [])

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
                f"✅ پست زمان‌بندی شد\nشماره: #{sid}\nزمان: `{send_time.strftime('%Y-%m-%d %H:%M')}` (ایران)",
                parse_mode="Markdown", reply_markup=main_menu())
            log_action("schedule_post", f"id={sid}")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا در زمان:\n{e}", reply_markup=main_menu())
        bot.user_steps[uid] = {}
        return

    # پیش‌فرض
    bot.send_message(message.chat.id, "از منوی شیشه‌ای استفاده کنید:", reply_markup=main_menu())

print("✅ بخش ۳ لود شد - منتظر بخش ۴ باش")
# ==================== بخش ۴ از ۴ ====================
# پرداخت استارز + زمان‌بند + اجرا

# ---------- تأیید پیش‌پرداخت ----------
@bot.pre_checkout_query_handler(func=lambda query: True)
def pre_checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# ---------- پرداخت موفق استارز ----------
@bot.message_handler(content_types=['successful_payment'])
def successful_payment(message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    
    if payload.startswith("stars_pay_"):
        parts = payload.split("_")
        try:
            amount = int(parts[2])
            user_id = int(parts[3])
        except:
            amount = payment.total_amount
            user_id = message.from_user.id

        bot.send_message(
            message.chat.id,
            f"✅ **پرداخت موفق**\n\n"
            f"تعداد استارز: **{amount}**\n"
            f"مبلغ: {payment.total_amount} XTR\n\n"
            f"استارزها به اکانت صاحب ربات واریز شد.",
            parse_mode="Markdown"
        )
        log_action("successful_payment", f"amount={amount} user={user_id}")
        
        # اطلاع به ادمین‌ها
        for admin in ADMIN_IDS:
            try:
                bot.send_message(admin, f"⭐ پرداخت جدید\nتعداد: {amount} استارز\nاز کاربر: `{user_id}`", parse_mode="Markdown")
            except:
                pass

# ---------- ترد زمان‌بندی ----------
def scheduler_worker():
    print("⏰ زمان‌بند شروع به کار کرد...")
    while True:
        try:
            conn = get_db()
            c = conn.cursor()
            now_str = now_tehran().strftime("%Y-%m-%d %H:%M:%S")
            
            c.execute("SELECT * FROM scheduled_posts WHERE status='pending' AND send_time <= ?", (now_str,))
            rows = c.fetchall()
            
            for row in rows:
                try:
                    # row: id, channel_id, content_type, file_id, text_content, caption, buttons, send_time, status
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
                    print(f"✅ پست زمان‌بندی‌شده #{row[0]} ارسال شد")
                    log_action("scheduled_sent", f"id={row[0]}")
                    
                except Exception as e:
                    print(f"❌ خطا در ارسال پست #{row[0]}: {e}")
                    c.execute("UPDATE scheduled_posts SET status='error' WHERE id=?", (row[0],))
                    conn.commit()
            
            conn.close()
        except Exception as e:
            print("Scheduler Error:", e)
        
        time.sleep(20)  # هر ۲۰ ثانیه چک می‌کند

# ---------- شروع ترد و ربات ----------
threading.Thread(target=scheduler_worker, daemon=True).start()

print("🤖 ربات پیشرفته مدیریت کانال با موفقیت روشن شد...")
print("زمان‌بند فعال است | وقت ایران پشتیبانی می‌شود")
bot.infinity_polling()
