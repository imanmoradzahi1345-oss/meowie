import telebot
from telebot import types
import json
import os
import time
import random
import re

TOKEN = "8617545814:AAFAofo_nV39gFT1-IgfXu-esnGgXol62r4"
MAIN_ADMIN_ID = 7530457395

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
DB_FILE = "db.json"

# --- مدیریت دیتابیس ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "photos": [],
        "bot_users": [],
        "bot_groups": [],
        "groups": {}
    }

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

db = load_db()

# --- ساختار داده‌های هر گروه ---
def get_group_data(chat_id):
    chat_str = str(chat_id)
    if chat_str not in db["groups"]:
        db["groups"][chat_str] = {
            "welcome_enabled": True,
            "welcome_text": "سلام {mention} عزیز به گپ {group} خوش اومدی",
            "antispam": False,
            "admins": [],
            "mutes": [],
            "bans": [],
            "warns": {},
            "titles": {},
            "stats": {},
            "autoreplies": {}
        }
        save_db(db)
    return db["groups"][chat_str]

# --- بررسی دسترسی ادمین ---
def is_bot_admin(chat_id, user_id):
    if user_id == MAIN_ADMIN_ID:
        return True
    try:
        member = bot.get_chat_member(chat_id, user_id)
        if member.status in ['creator', 'administrator']:
            return True
    except Exception:
        pass
    gdata = get_group_data(chat_id)
    return user_id in gdata.get("admins", [])

# --- فرمت متن خوشامدگویی ---
def format_welcome_text(text, user, chat_title):
    mention = f'<a href="tg://user?id={user.id}">{user.first_name}</a>'
    username = f"@{user.username}" if user.username else user.first_name
    
    formatted = text.replace("{name}", user.first_name or "")
    formatted = formatted.replace("{username}", username)
    formatted = formatted.replace("{id}", str(user.id))
    formatted = formatted.replace("{group}", chat_title or "")
    formatted = formatted.replace("{mention}", mention)
    return formatted

# --- ثبت اعضا و گروه‌ها برای تبلیغات ---
def register_chat(message):
    if message.chat.type == 'private':
        if message.from_user.id not in db["bot_users"]:
            db["bot_users"].append(message.from_user.id)
            save_db(db)
    elif message.chat.type in ['group', 'supergroup']:
        if message.chat.id not in db["bot_groups"]:
            db["bot_groups"].append(message.chat.id)
            save_db(db)

# --- سیستم قفل ضد اسپم (در حافظه) ---
user_msg_tracker = {}

def check_antispam(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    gdata = get_group_data(chat_id)
    
    if not gdata.get("antispam", False) or is_bot_admin(chat_id, user_id):
        return False
        
    now = time.time()
    key = f"{chat_id}:{user_id}"
    if key not in user_msg_tracker:
        user_msg_tracker[key] = []
        
    user_msg_tracker[key] = [t for t in user_msg_tracker[key] if now - t < 4]
    user_msg_tracker[key].append(now)
    
    if len(user_msg_tracker[key]) > 5:
        try:
            bot.delete_message(chat_id, message.message_id)
            bot.restrict_chat_member(chat_id, user_id, until_date=int(now + 60))
            bot.send_message(chat_id, f"کاربر <a href='tg://user?id={user_id}'>{message.from_user.first_name}</a> به دلیل اسپم ۱ دقیقه سکوت شد.")
        except Exception:
            pass
        return True
    return False

# --- خوشامدگویی به اعضای جدید ---
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    register_chat(message)
    gdata = get_group_data(message.chat.id)
    if not gdata.get("welcome_enabled", True):
        return

    for user in message.new_chat_members:
        text = format_welcome_text(gdata.get("welcome_text"), user, message.chat.title)
        photos = db.get("photos", [])
        if photos:
            photo_id = random.choice(photos)
            try:
                bot.send_photo(message.chat.id, photo_id, caption=text)
            except Exception:
                bot.send_message(message.chat.id, text)
        else:
            bot.send_message(message.chat.id, text)

# --- دستورات ادمین اصلی در پیوی ---
admin_states = {}

@bot.message_handler(commands=['start'], chat_types=['private'])
def start_pv(message):
    register_chat(message)
    if message.from_user.id == MAIN_ADMIN_ID:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("📸 آپلود عکس خوشامدگویی", "📢 ارسال تبلیغات")
        markup.add("🗑 پاکسازی عکس‌های خوشامد")
        bot.send_message(message.chat.id, "👑 به پنل ادمین اصلی ربات خوش آمدید.", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "سلام! ربات را به گروه خود اضافه کنید و ادمین سازید تا فعال شود.")

@bot.message_handler(func=lambda m: m.chat.type == 'private' and m.from_user.id == MAIN_ADMIN_ID, content_types=['text', 'photo'])
def handle_pv_admin(message):
    user_id = message.from_user.id
    state = admin_states.get(user_id)
    
    if message.text == "📸 آپلود عکس خوشامدگویی":
        admin_states[user_id] = "waiting_photo"
        bot.send_message(user_id, "لطفاً عکس مورد نظر را ارسال کنید (حداکثر ۱۰۰ عکس ذخیره می‌شود):")
        return
        
    if message.text == "🗑 پاکسازی عکس‌های خوشامد":
        db["photos"] = []
        save_db(db)
        bot.send_message(user_id, "تمام عکس‌های خوشامدگویی حذف شدند.")
        return

    if message.text == "📢 ارسال تبلیغات":
        admin_states[user_id] = "waiting_broadcast"
        bot.send_message(user_id, "پیام یا تبلیغ خود را ارسال کنید تا به تمام گروه‌ها و پیوی‌ها فرستاده شود:")
        return

    if state == "waiting_photo" and message.photo:
        photo_id = message.photo[-1].file_id
        if len(db["photos"]) >= 100:
            db["photos"].pop(0)
        db["photos"].append(photo_id)
        save_db(db)
        admin_states[user_id] = None
        bot.send_message(user_id, f"✅ عکس با موفقیت ذخیره شد. تعداد عکس‌های فعلی: {len(db['photos'])}")
        return

    if state == "waiting_broadcast" and message.text:
        admin_states[user_id] = None
        sent_users = 0
        sent_groups = 0
        for u in db.get("bot_users", []):
            try:
                bot.send_message(u, message.text)
                sent_users += 1
            except Exception:
                pass
        for g in db.get("bot_groups", []):
            try:
                bot.send_message(g, message.text)
                sent_groups += 1
            except Exception:
                pass
        bot.send_message(user_id, f"✅ تبلیغات ارسال شد.\nپیوی: {sent_users}\nگروه‌ها: {sent_groups}")
        return

# --- سیستم پاسخ خودکار و کد تنظیمات ---
@bot.message_handler(func=lambda m: m.chat.type == 'private' and m.text and m.text.startswith("SETCFG_"))
def handle_config_code(message):
    try:
        raw = message.text.replace("SETCFG_", "")
        data = json.loads(raw)
        chat_id = data.get("chat_id")
        word = data.get("word")
        reply = data.get("reply")
        
        if chat_id and is_bot_admin(chat_id, message.from_user.id):
            gdata = get_group_data(chat_id)
            gdata["autoreplies"][word] = reply
            save_db(db)
            bot.send_message(message.chat.id, f"✅ پاسخ خودکار برای کلمه «{word}» با موفقیت در گروه ثبت شد.")
        else:
            bot.send_message(message.chat.id, "❌ شما دسترسی ادمین در این گروه را ندارید.")
    except Exception:
        bot.send_message(message.chat.id, "❌ کد تنظیمات نامعتبر است.")

# --- مدیریت دستورات گروه ---
@bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup'])
def handle_group_messages(message):
    register_chat(message)
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text or ""
    gdata = get_group_data(chat_id)

    # سیستم ضد اسپم
    if check_antispam(message):
        return

    # ثبت آمار کل
    user_str = str(user_id)
    gdata["stats"][user_str] = gdata["stats"].get(user_str, 0) + 1
    save_db(db)

    # 1. تنظیم ادمین ربات
    if text == "تنظیم ادمین" and message.reply_to_message:
        if is_bot_admin(chat_id, user_id):
            target_id = message.reply_to_message.from_user.id
            if target_id not in gdata["admins"]:
                gdata["admins"].append(target_id)
                save_db(db)
                bot.reply_to(message, f"کاربر <a href='tg://user?id={target_id}'>{message.reply_to_message.from_user.first_name}</a> به‌عنوان ادمین ربات ثبت شد.")
            else:
                bot.reply_to(message, "این کاربر از قبل ادمین ربات می‌باشد.")
        return

    # 2. پنل تنظیمات گروه
    if text == "پنل":
        if is_bot_admin(chat_id, user_id):
            markup = types.InlineKeyboardMarkup(row_width=2)
            w_status = "✅ فعال" if gdata.get("welcome_enabled", True) else "❌ غیرفعال"
            s_status = "✅ فعال" if gdata.get("antispam", False) else "❌ غیرفعال"
            
            btn_welcome = types.InlineKeyboardButton(f"خوشامدگویی: {w_status}", callback_data=f"toggle_w_{chat_id}")
            btn_antispam = types.InlineKeyboardButton(f"ضد اسپم: {s_status}", callback_data=f"toggle_s_{chat_id}")
            btn_auto = types.InlineKeyboardButton("➕ افزودن پاسخ خودکار", callback_data=f"add_auto_{chat_id}")
            
            markup.add(btn_welcome, btn_antispam)
            markup.add(btn_auto)
            bot.send_message(chat_id, "⚙️ **پنل مدیریت تنظیمات گروه**", reply_markup=markup)
        return

    # 3. آمار کل
    if text == "آمار کل":
        stats = gdata.get("stats", {})
        sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)[:10]
        msg = "📊 **آمار فعال‌ترین کاربران گروه:**\n\n"
        for idx, (u_id, count) in enumerate(sorted_stats, 1):
            try:
                m = bot.get_chat_member(chat_id, int(u_id))
                name = m.user.first_name
            except Exception:
                name = f"کاربر {u_id}"
            msg += f"{idx}. {name} — {count} پیام\n"
        bot.reply_to(message, msg)
        return

    # 4. تنظیم لقب
    if text.startswith("تنظیم لقب ") and message.reply_to_message:
        if is_bot_admin(chat_id, user_id):
            title = text.replace("تنظیم لقب ", "").strip()
            target_id = message.reply_to_message.from_user.id
            gdata["titles"][str(target_id)] = title
            save_db(db)
            bot.reply_to(message, f"لقب «{title}» برای کاربر ثبت شد.")
        return

    # 5. حذف پیام (پاکسازی)
    if text == "حذف" and message.reply_to_message:
        if is_bot_admin(chat_id, user_id):
            try:
                bot.delete_message(chat_id, message.reply_to_message.message_id)
                bot.delete_message(chat_id, message.message_id)
            except Exception:
                pass
        return

    if text.startswith("حذف "):
        if is_bot_admin(chat_id, user_id):
            parts = text.split()
            if len(parts) == 2 and parts[1].isdigit():
                count = min(int(parts[1]), 100)
                current_id = message.message_id
                for i in range(count + 1):
                    try:
                        bot.delete_message(chat_id, current_id - i)
                    except Exception:
                        pass
        return

    # 6. سکوت و حذف سکوت
    if text.startswith("سکوت"):
        if is_bot_admin(chat_id, user_id):
            target_id = message.reply_to_message.from_user.id if message.reply_to_message else None
            if target_id:
                parts = text.split()
                duration = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 300
                until = int(time.time() + duration)
                bot.restrict_chat_member(chat_id, target_id, until_date=until)
                if target_id not in gdata["mutes"]:
                    gdata["mutes"].append(target_id)
                    save_db(db)
                bot.reply_to(message, f"کاربر به مدت {duration} ثانیه سکوت شد.")
        return

    if text == "حذف سکوت" and message.reply_to_message:
        if is_bot_admin(chat_id, user_id):
            target_id = message.reply_to_message.from_user.id
            bot.restrict_chat_member(chat_id, target_id, can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True)
            if target_id in gdata["mutes"]:
                gdata["mutes"].remove(target_id)
                save_db(db)
            bot.reply_to(message, "سکوت کاربر برداشته شد.")
        return

    # 7. بن و حذف بن
    if text == "بن" and message.reply_to_message:
        if is_bot_admin(chat_id, user_id):
            target_id = message.reply_to_message.from_user.id
            bot.ban_chat_member(chat_id, target_id)
            if target_id not in gdata["bans"]:
                gdata["bans"].append(target_id)
                save_db(db)
            bot.reply_to(message, "کاربر از گروه بن شد.")
        return

    if text == "حذف بن" and message.reply_to_message:
        if is_bot_admin(chat_id, user_id):
            target_id = message.reply_to_message.from_user.id
            bot.unban_chat_member(chat_id, target_id)
            if target_id in gdata["bans"]:
                gdata["bans"].remove(target_id)
                save_db(db)
            bot.reply_to(message, "بن کاربر برداشته شد.")
        return

    # 8. اخطار و حذف اخطار
    if text == "اخطار" and message.reply_to_message:
        if is_bot_admin(chat_id, user_id):
            target_id = str(message.reply_to_message.from_user.id)
            gdata["warns"][target_id] = gdata["warns"].get(target_id, 0) + 1
            save_db(db)
            warn_count = gdata["warns"][target_id]
            if warn_count >= 3:
                bot.ban_chat_member(chat_id, int(target_id))
                gdata["warns"][target_id] = 0
                save_db(db)
                bot.reply_to(message, "کاربر به دلیل دریافت ۳ اخطار بن شد.")
            else:
                bot.reply_to(message, f"اخطار به کاربر ثبت شد. تعداد اخطارها: {warn_count}/3")
        return

    if text == "حذف اخطار" and message.reply_to_message:
        if is_bot_admin(chat_id, user_id):
            target_id = str(message.reply_to_message.from_user.id)
            if target_id in gdata["warns"] and gdata["warns"][target_id] > 0:
                gdata["warns"][target_id] -= 1
                save_db(db)
                bot.reply_to(message, f"یک اخطار کسر شد. اخطارهای فعلی: {gdata['warns'][target_id]}")
        return

    # 9. پاکسازی‌های کلی
    if text == "پاکسازی لیست سکوت" and is_bot_admin(chat_id, user_id):
        for u in gdata.get("mutes", []):
            try:
                bot.restrict_chat_member(chat_id, u, can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True)
            except Exception:
                pass
        gdata["mutes"] = []
        save_db(db)
        bot.reply_to(message, "لیست سکوت پاکسازی شد.")
        return

    if text == "پاکسازی لیست بن" and is_bot_admin(chat_id, user_id):
        for u in gdata.get("bans", []):
            try:
                bot.unban_chat_member(chat_id, u)
            except Exception:
                pass
        gdata["bans"] = []
        save_db(db)
        bot.reply_to(message, "لیست اعضای بن شده پاکسازی شد.")
        return

    if text == "پاکسازی لیست اخطار" and is_bot_admin(chat_id, user_id):
        gdata["warns"] = {}
        save_db(db)
        bot.reply_to(message, "تمام اخطارها پاکسازی شدند.")
        return

    # 10. بررسی پاسخ‌های خودکار
    autoreplies = gdata.get("autoreplies", {})
    for trigger, resp in autoreplies.items():
        if trigger in text:
            bot.reply_to(message, resp)
            break

# --- مدیریت کلیک روی دکمه‌های شیشه‌ای (Callback) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    data = call.data

    if not is_bot_admin(chat_id, user_id):
        bot.answer_callback_query(call.id, "شما دسترسی ادمین ندارید.", show_alert=True)
        return

    gdata = get_group_data(chat_id)

    if data.startswith("toggle_w_"):
        gdata["welcome_enabled"] = not gdata.get("welcome_enabled", True)
        save_db(db)
        bot.answer_callback_query(call.id, "تنظیمات خوشامد تغییر کرد.")
    elif data.startswith("toggle_s_"):
        gdata["antispam"] = not gdata.get("antispam", False)
        save_db(db)
        bot.answer_callback_query(call.id, "تنظیمات ضد اسپم تغییر کرد.")
    elif data.startswith("add_auto_"):
        code_data = json.dumps({"chat_id": chat_id, "word": "سلام", "reply": "سلام رفیق! خوش اومدی."})
        msg = f"لطفاً کد زیر را کپی کرده و در پیوی ربات ارسال کنید تا پاسخ خودکار ثبت شود:\n\n<code>SETCFG_{code_data}</code>"
        bot.send_message(user_id, msg)
        bot.answer_callback_query(call.id, "کد به پیوی شما ارسال شد.")
        return

    # بروزرسانی پنل
    w_status = "✅ فعال" if gdata.get("welcome_enabled", True) else "❌ غیرفعال"
    s_status = "✅ فعال" if gdata.get("antispam", False) else "❌ غیرفعال"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_welcome = types.InlineKeyboardButton(f"خوشامدگویی: {w_status}", callback_data=f"toggle_w_{chat_id}")
    btn_antispam = types.InlineKeyboardButton(f"ضد اسپم: {s_status}", callback_data=f"toggle_s_{chat_id}")
    btn_auto = types.InlineKeyboardButton("➕ افزودن پاسخ خودکار", callback_data=f"add_auto_{chat_id}")
    
    markup.add(btn_welcome, btn_antispam)
    markup.add(btn_auto)

    try:
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=markup)
    except Exception:
        pass

if __name__ == "__main__":
    bot.infinity_polling(skip_pending=True)
    
