# ==================== بخش ۱ از ۴ ====================
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions, ChatRestrictions
import sqlite3
import time
import re
from datetime import datetime, timedelta
from collections import defaultdict, deque

BOT_TOKEN = "8597049833:AAFnEjGLcOz09Duy6MIvOoMD9TA1-fiRhPE"
MAIN_OWNER_ID = 7530457395

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# فلود: ۱۰۰ پیام در ۲۰ ثانیه
flood_map = defaultdict(lambda: deque())
user_steps = {}

def get_db():
    return sqlite3.connect("group_manager.db", check_same_thread=False, timeout=30)

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS groups (
        chat_id INTEGER PRIMARY KEY,
        title TEXT,
        locked INTEGER DEFAULT 0,
        lock_link INTEGER DEFAULT 0,
        lock_forward INTEGER DEFAULT 0,
        lock_gif INTEGER DEFAULT 0,
        lock_sticker INTEGER DEFAULT 0,
        lock_voice INTEGER DEFAULT 0,
        welcome_text TEXT,
        welcome_type TEXT,
        welcome_file_id TEXT,
        leave_text TEXT,
        leave_enabled INTEGER DEFAULT 0,
        welcome_enabled INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS bot_owners (
        chat_id INTEGER,
        user_id INTEGER,
        PRIMARY KEY (chat_id, user_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS bot_admins (
        chat_id INTEGER,
        user_id INTEGER,
        PRIMARY KEY (chat_id, user_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS specials (
        chat_id INTEGER,
        user_id INTEGER,
        PRIMARY KEY (chat_id, user_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS swears (
        chat_id INTEGER,
        word TEXT,
        PRIMARY KEY (chat_id, word)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS autoreplies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        keyword TEXT,
        answer TEXT,
        exact_match INTEGER DEFAULT 1,
        active INTEGER DEFAULT 1
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS warns (
        chat_id INTEGER,
        user_id INTEGER,
        count INTEGER DEFAULT 0,
        PRIMARY KEY (chat_id, user_id)
    )''')

    conn.commit()
    conn.close()

init_db()

def ensure_group(chat):
    if not chat or chat.type not in ("group", "supergroup"):
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO groups (chat_id, title) VALUES (?, ?)", (chat.id, chat.title or ""))
    c.execute("UPDATE groups SET title=? WHERE chat_id=?", (chat.title or "", chat.id))
    # مالک اصلی ربات در همه گپ‌ها
    c.execute("INSERT OR IGNORE INTO bot_owners (chat_id, user_id) VALUES (?, ?)", (chat.id, MAIN_OWNER_ID))
    conn.commit()
    conn.close()

def is_main_owner(uid):
    return uid == MAIN_OWNER_ID

def is_bot_owner(chat_id, uid):
    if is_main_owner(uid):
        return True
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM bot_owners WHERE chat_id=? AND user_id=?", (chat_id, uid))
    row = c.fetchone()
    conn.close()
    return bool(row)

def is_bot_admin(chat_id, uid):
    if is_bot_owner(chat_id, uid):
        return True
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM bot_admins WHERE chat_id=? AND user_id=?", (chat_id, uid))
    row = c.fetchone()
    conn.close()
    return bool(row)

def is_special(chat_id, uid):
    if is_bot_admin(chat_id, uid):
        return True
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM specials WHERE chat_id=? AND user_id=?", (chat_id, uid))
    row = c.fetchone()
    conn.close()
    return bool(row)

def get_group(chat_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE chat_id=?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return row

def set_group_flag(chat_id, field, value):
    conn = get_db()
    c = conn.cursor()
    c.execute(f"UPDATE groups SET {field}=? WHERE chat_id=?", (value, chat_id))
    conn.commit()
    conn.close()

def can_manage(chat_id, uid):
    return is_bot_admin(chat_id, uid)

def mute_user(chat_id, user_id, minutes):
    until = int(time.time()) + max(1, minutes) * 60
    bot.restrict_chat_member(
        chat_id, user_id,
        permissions=ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False
        ),
        until_date=until
    )

def unmute_user(chat_id, user_id):
    bot.restrict_chat_member(
        chat_id, user_id,
        permissions=ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_send_polls=True,
            can_invite_users=True
        )
    )

def lock_group(chat_id):
    bot.set_chat_permissions(
        chat_id,
        ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False
        )
    )
    set_group_flag(chat_id, "locked", 1)

def unlock_group(chat_id):
    bot.set_chat_permissions(
        chat_id,
        ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_send_polls=True,
            can_invite_users=True
        )
    )
    set_group_flag(chat_id, "locked", 0)

def extract_target(message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    return None

print("✅ بخش ۱ آماده شد")
# ==================== بخش ۲ از ۴ ====================

@bot.message_handler(content_types=['new_chat_members'])
def on_new_members(message):
    try:
        ensure_group(message.chat)
        chat_id = message.chat.id

        for m in message.new_chat_members:
            # اگر خود ربات اضافه شد
            if m.id == bot.get_me().id:
                # مالک اصلی
                conn = get_db()
                c = conn.cursor()
                c.execute("INSERT OR IGNORE INTO bot_owners (chat_id, user_id) VALUES (?, ?)", (chat_id, MAIN_OWNER_ID))
                # ادمین‌های فعلی گپ → ادمین بات
                try:
                    admins = bot.get_chat_administrators(chat_id)
                    for a in admins:
                        if a.user.is_bot:
                            continue
                        c.execute("INSERT OR IGNORE INTO bot_admins (chat_id, user_id) VALUES (?, ?)", (chat_id, a.user.id))
                        # سازنده گپ را مالک بات کن
                        if a.status == "creator":
                            c.execute("INSERT OR IGNORE INTO bot_owners (chat_id, user_id) VALUES (?, ?)", (chat_id, a.user.id))
                except Exception:
                    pass
                conn.commit()
                conn.close()
                bot.send_message(chat_id, "✅ ربات مدیریت فعال شد.\nدستور: پنل")
                continue

            # خوش‌آمد
            g = get_group(chat_id)
            if g and g[12]:  # welcome_enabled index - check schema
                pass
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT welcome_enabled, welcome_text, welcome_type, welcome_file_id FROM groups WHERE chat_id=?", (chat_id,))
            w = c.fetchone()
            conn.close()
            if w and w[0]:
                name = m.first_name or "کاربر"
                text = (w[1] or "خوش آمدی {name}").replace("{name}", name).replace("{id}", str(m.id))
                try:
                    if w[2] == "photo" and w[3]:
                        bot.send_photo(chat_id, w[3], caption=text)
                    elif w[2] == "animation" and w[3]:
                        bot.send_animation(chat_id, w[3], caption=text)
                    else:
                        bot.send_message(chat_id, text)
                except Exception:
                    bot.send_message(chat_id, text)
    except Exception as e:
        print("new_members error:", e)

@bot.message_handler(content_types=['left_chat_member'])
def on_left(message):
    try:
        ensure_group(message.chat)
        chat_id = message.chat.id
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT leave_enabled, leave_text FROM groups WHERE chat_id=?", (chat_id,))
        row = c.fetchone()
        conn.close()
        if row and row[0]:
            name = message.left_chat_member.first_name or "کاربر"
            text = (row[1] or "{name} از گپ رفت").replace("{name}", name)
            bot.send_message(chat_id, text)
    except Exception as e:
        print("left error:", e)

def panel_keyboard(chat_id):
    g = get_group(chat_id)
    def on(v):
        return "✅" if v else "❌"
    if not g:
        return InlineKeyboardMarkup().add(InlineKeyboardButton("برگشت", callback_data="p_close"))

    # schema: chat_id,title,locked,lock_link,lock_forward,lock_gif,lock_sticker,lock_voice,...
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(f"لینک {on(g[3])}", callback_data="tog_link"),
        InlineKeyboardButton(f"فوروارد {on(g[4])}", callback_data="tog_forward")
    )
    kb.add(
        InlineKeyboardButton(f"گیف {on(g[5])}", callback_data="tog_gif"),
        InlineKeyboardButton(f"استیکر {on(g[6])}", callback_data="tog_sticker")
    )
    kb.add(
        InlineKeyboardButton(f"ویس {on(g[7])}", callback_data="tog_voice"),
        InlineKeyboardButton(f"قفل کل گپ {on(g[2])}", callback_data="tog_lockall")
    )
    kb.add(
        InlineKeyboardButton("مالک‌ها", callback_data="list_owners"),
        InlineKeyboardButton("ادمین‌ها", callback_data="list_admins")
    )
    kb.add(
        InlineKeyboardButton("اعضای ویژه", callback_data="list_specials"),
        InlineKeyboardButton("فحش‌ها", callback_data="list_swears")
    )
    kb.add(InlineKeyboardButton("پیشرفته (فقط مالک)", callback_data="advanced"))
    kb.add(InlineKeyboardButton("بستن", callback_data="p_close"))
    return kb

@bot.message_handler(func=lambda m: m.chat.type in ["group", "supergroup"] and m.text)
def group_commands(message):
    try:
        ensure_group(message.chat)
        chat_id = message.chat.id
        uid = message.from_user.id
        text = (message.text or "").strip()
        low = text.replace("‌", " ").strip()

        # ---- دستورات مدیریت ----
        if low in ["پنل", "پنل مدیریت"]:
            if not can_manage(chat_id, uid):
                return
            bot.reply_to(message, "🛡 پنل مدیریت گپ", reply_markup=panel_keyboard(chat_id))
            return

        if low in ["قفل", "قفل گروه", "قفل گپ"]:
            if not can_manage(chat_id, uid):
                return
            lock_group(chat_id)
            bot.reply_to(message, "🔒 گپ قفل شد.")
            return

        if low in ["باز", "باز کردن گروه", "باز کردن گپ", "باز گروه"]:
            if not can_manage(chat_id, uid):
                return
            unlock_group(chat_id)
            bot.reply_to(message, "🔓 گپ باز شد.")
            return

        # سکوت 3 / سکوت
        if low.startswith("سکوت"):
            if not can_manage(chat_id, uid):
                return
            target = extract_target(message)
            if not target:
                bot.reply_to(message, "روی پیام فرد ریپلای کن.")
                return
            if is_bot_owner(chat_id, target.id) and not is_main_owner(uid):
                bot.reply_to(message, "نمی‌تونی مالک را سکوت کنی.")
                return
            parts = low.split()
            minutes = 5
            if len(parts) >= 2 and parts[1].isdigit():
                minutes = int(parts[1])
            mute_user(chat_id, target.id, minutes)
            bot.reply_to(message, f"🔇 {target.first_name} برای {minutes} دقیقه سکوت شد.")
            return

        if low in ["حذف سکوت", "آزاد", "رفع سکوت"]:
            if not can_manage(chat_id, uid):
                return
            target = extract_target(message)
            if not target:
                bot.reply_to(message, "روی پیام فرد ریپلای کن.")
                return
            unmute_user(chat_id, target.id)
            bot.reply_to(message, f"✅ سکوت {target.first_name} برداشته شد.")
            return

        if low in ["بن", "اخراج"]:
            if not can_manage(chat_id, uid):
                return
            target = extract_target(message)
            if not target:
                bot.reply_to(message, "روی پیام فرد ریپلای کن.")
                return
            if is_bot_owner(chat_id, target.id) and not is_main_owner(uid):
                bot.reply_to(message, "نمی‌تونی مالک را بن کنی.")
                return
            bot.ban_chat_member(chat_id, target.id)
            bot.reply_to(message, f"🚫 {target.first_name} بن شد.")
            return

        if low in ["حذف بن", "آنبن"]:
            if not can_manage(chat_id, uid):
                return
            target = extract_target(message)
            if not target:
                bot.reply_to(message, "روی پیام فرد ریپلای کن.")
                return
            bot.unban_chat_member(chat_id, target.id)
            bot.reply_to(message, f"✅ بن {target.first_name} برداشته شد.")
            return

        # مالک
        if low in ["تنظیم مالک"]:
            if not is_bot_owner(chat_id, uid):
                return
            target = extract_target(message)
            if not target:
                bot.reply_to(message, "روی پیام فرد ریپلای کن.")
                return
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO bot_owners (chat_id, user_id) VALUES (?, ?)", (chat_id, target.id))
            c.execute("INSERT OR IGNORE INTO bot_admins (chat_id, user_id) VALUES (?, ?)", (chat_id, target.id))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"👑 {target.first_name} مالک بات شد.")
            return

        if low in ["حذف مالک"]:
            if not is_bot_owner(chat_id, uid):
                return
            target = extract_target(message)
            if not target:
                bot.reply_to(message, "روی پیام فرد ریپلای کن.")
                return
            if target.id == MAIN_OWNER_ID:
                bot.reply_to(message, "مالک اصلی ربات قابل حذف نیست.")
                return
            conn = get_db()
            c = conn.cursor()
            c.execute("DELETE FROM bot_owners WHERE chat_id=? AND user_id=?", (chat_id, target.id))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ {target.first_name} از مالکیت بات حذف شد.")
            return

        if low in ["تنظیم ادمین"]:
            if not is_bot_owner(chat_id, uid):
                return
            target = extract_target(message)
            if not target:
                bot.reply_to(message, "روی پیام فرد ریپلای کن.")
                return
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO bot_admins (chat_id, user_id) VALUES (?, ?)", (chat_id, target.id))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"🛡 {target.first_name} ادمین بات شد.")
            return

        if low in ["حذف ادمین"]:
            if not is_bot_owner(chat_id, uid):
                return
            target = extract_target(message)
            if not target:
                bot.reply_to(message, "روی پیام فرد ریپلای کن.")
                return
            conn = get_db()
            c = conn.cursor()
            c.execute("DELETE FROM bot_admins WHERE chat_id=? AND user_id=?", (chat_id, target.id))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ ادمین بات از {target.first_name} برداشته شد (ادمین گپ سر جایش است).")
            return

        if low in ["تنظیم ویژه"]:
            if not is_bot_owner(chat_id, uid):
                return
            target = extract_target(message)
            if not target:
                bot.reply_to(message, "روی پیام فرد ریپلای کن.")
                return
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO specials (chat_id, user_id) VALUES (?, ?)", (chat_id, target.id))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"⭐ {target.first_name} عضو ویژه شد.")
            return

        if low in ["حذف ویژه"]:
            if not is_bot_owner(chat_id, uid):
                return
            target = extract_target(message)
            if not target:
                bot.reply_to(message, "روی پیام فرد ریپلای کن.")
                return
            conn = get_db()
            c = conn.cursor()
            c.execute("DELETE FROM specials WHERE chat_id=? AND user_id=?", (chat_id, target.id))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ ویژه بودن {target.first_name} برداشته شد.")
            return

        # ضد فحش / لینک / فلود در بخش ۳
        check_filters(message)
    except Exception as e:
        print("group_commands error:", e)
        # ==================== بخش ۳ از ۴ ====================

def check_filters(message):
    try:
        chat_id = message.chat.id
        uid = message.from_user.id
        if is_bot_admin(chat_id, uid):
            # ادمین از فیلترها رد شود
            maybe_autoreply(message)
            return

        g = get_group(chat_id)
        if not g:
            return

        text = message.text or message.caption or ""

        # فلود شدید: ۱۰۰ پیام در ۲۰ ثانیه
        key = (chat_id, uid)
        now = time.time()
        q = flood_map[key]
        q.append(now)
        while q and now - q[0] > 20:
            q.popleft()
        if len(q) >= 100:
            try:
                bot.delete_message(chat_id, message.message_id)
            except Exception:
                pass
            try:
                mute_user(chat_id, uid, 10)
                bot.send_message(chat_id, f"🔇 فلود شدید از {message.from_user.first_name} — ۱۰ دقیقه سکوت")
            except Exception:
                pass
            return

        # ضد فحش
        if text:
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT word FROM swears WHERE chat_id=?", (chat_id,))
            words = [r[0] for r in c.fetchall()]
            conn.close()
            low = text.lower()
            for w in words:
                if w and w.lower() in low:
                    try:
                        bot.delete_message(chat_id, message.message_id)
                    except Exception:
                        pass
                    try:
                        bot.send_message(chat_id, "پیام پاک شد", reply_to_message_id=message.message_id)
                    except Exception:
                        try:
                            bot.send_message(chat_id, f"پیام پاک شد\nکاربر: {message.from_user.first_name}")
                        except Exception:
                            pass
                    return

        # قفل لینک
        if g[3]:
            if re.search(r"(https?://|www\.|t\.me/|telegram\.me/)", text, re.IGNORECASE):
                if not is_special(chat_id, uid):
                    try:
                        bot.delete_message(chat_id, message.message_id)
                    except Exception:
                        pass
                    return

        # قفل فوروارد
        if g[4] and (message.forward_date or message.forward_from or message.forward_from_chat):
            if not is_special(chat_id, uid):
                try:
                    bot.delete_message(chat_id, message.message_id)
                except Exception:
                    pass
                return

        # قفل گیف/استیکر/ویس
        if not is_special(chat_id, uid):
            if g[5] and message.animation:
                try:
                    bot.delete_message(chat_id, message.message_id)
                except Exception:
                    pass
                return
            if g[6] and message.sticker:
                try:
                    bot.delete_message(chat_id, message.message_id)
                except Exception:
                    pass
                return
            if g[7] and message.voice:
                try:
                    bot.delete_message(chat_id, message.message_id)
                except Exception:
                    pass
                return

        maybe_autoreply(message)
    except Exception as e:
        print("filter error:", e)

def maybe_autoreply(message):
    try:
        if not message.text:
            return
        chat_id = message.chat.id
        text = message.text.strip()
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT keyword, answer, exact_match FROM autoreplies WHERE chat_id=? AND active=1", (chat_id,))
        rows = c.fetchall()
        conn.close()
        for keyword, answer, exact in rows:
            if exact:
                if text == keyword:
                    bot.reply_to(message, answer)
                    break
            else:
                if keyword in text:
                    bot.reply_to(message, answer)
                    break
    except Exception as e:
        print("autoreply error:", e)

@bot.message_handler(func=lambda m: m.chat.type in ["group", "supergroup"], content_types=[
    'text', 'photo', 'video', 'voice', 'document', 'sticker', 'animation', 'video_note', 'audio'
])
def group_all_messages(message):
    # دستورات متنی در handler قبلی؛ اینجا فیلتر برای غیرمتن و متن‌هایی که دستور نبودند
    try:
        ensure_group(message.chat)
        if message.text:
            # اگر دستور مدیریت بود، همان handler قبلی گرفته؛ برای اطمینان فیلتر هم هست
            cmds = ["پنل", "قفل", "باز", "سکوت", "بن", "اخراج", "آزاد", "حذف", "تنظیم", "آنبن"]
            t = message.text.strip()
            if any(t.startswith(c) or t == c for c in cmds):
                return
        check_filters(message)
    except Exception as e:
        print("group_all error:", e)

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    try:
        if call.message.chat.type not in ["group", "supergroup", "private"]:
            return
        uid = call.from_user.id
        data = call.data
        chat_id = call.message.chat.id

        # در گپ
        if call.message.chat.type in ["group", "supergroup"]:
            if not can_manage(chat_id, uid):
                bot.answer_callback_query(call.id, "دسترسی نداری", show_alert=True)
                return

            mapping = {
                "tog_link": "lock_link",
                "tog_forward": "lock_forward",
                "tog_gif": "lock_gif",
                "tog_sticker": "lock_sticker",
                "tog_voice": "lock_voice",
            }

            if data in mapping:
                field = mapping[data]
                g = get_group(chat_id)
                # indexes: 3 link, 4 forward, 5 gif, 6 sticker, 7 voice
                idx = {"lock_link": 3, "lock_forward": 4, "lock_gif": 5, "lock_sticker": 6, "lock_voice": 7}[field]
                cur = g[idx] if g else 0
                set_group_flag(chat_id, field, 0 if cur else 1)
                bot.answer_callback_query(call.id, "تغییر کرد")
                bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=panel_keyboard(chat_id))
                return

            if data == "tog_lockall":
                g = get_group(chat_id)
                if g and g[2]:
                    unlock_group(chat_id)
                    bot.answer_callback_query(call.id, "گپ باز شد")
                else:
                    lock_group(chat_id)
                    bot.answer_callback_query(call.id, "گپ قفل شد")
                bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=panel_keyboard(chat_id))
                return

            if data == "list_owners":
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT user_id FROM bot_owners WHERE chat_id=?", (chat_id,))
                rows = c.fetchall()
                conn.close()
                text = "👑 مالک‌های بات:\n" + "\n".join([f"`{r[0]}`" for r in rows])
                bot.answer_callback_query(call.id)
                bot.send_message(chat_id, text, parse_mode="Markdown")
                return

            if data == "list_admins":
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT user_id FROM bot_admins WHERE chat_id=?", (chat_id,))
                rows = c.fetchall()
                conn.close()
                text = "🛡 ادمین‌های بات:\n" + ("\n".join([f"`{r[0]}`" for r in rows]) if rows else "خالی")
                bot.answer_callback_query(call.id)
                bot.send_message(chat_id, text, parse_mode="Markdown")
                return

            if data == "list_specials":
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT user_id FROM specials WHERE chat_id=?", (chat_id,))
                rows = c.fetchall()
                conn.close()
                text = "⭐ اعضای ویژه:\n" + ("\n".join([f"`{r[0]}`" for r in rows]) if rows else "خالی")
                bot.answer_callback_query(call.id)
                bot.send_message(chat_id, text, parse_mode="Markdown")
                return

            if data == "list_swears":
                if not is_bot_owner(chat_id, uid):
                    bot.answer_callback_query(call.id, "فقط مالک", show_alert=True)
                    return
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT word FROM swears WHERE chat_id=?", (chat_id,))
                rows = c.fetchall()
                conn.close()
                text = "🚫 فحش‌ها:\n" + ("\n".join([r[0] for r in rows]) if rows else "خالی")
                bot.answer_callback_query(call.id)
                bot.send_message(chat_id, text)
                return

            if data == "advanced":
                if not is_bot_owner(chat_id, uid):
                    bot.answer_callback_query(call.id, "فقط مالک بات", show_alert=True)
                    return
                kb = InlineKeyboardMarkup(row_width=1)
                kb.add(
                    InlineKeyboardButton("➕ افزودن فحش", callback_data="add_swear"),
                    InlineKeyboardButton("➖ حذف فحش", callback_data="del_swear"),
                    InlineKeyboardButton("پیام خودکار (پیوی)", callback_data="auto_help"),
                    InlineKeyboardButton("تنظیم خوش‌آمد", callback_data="set_welcome"),
                    InlineKeyboardButton("تنظیم لفت", callback_data="set_leave"),
                    InlineKeyboardButton("برگشت", callback_data="back_panel")
                )
                bot.edit_message_text("⚙️ بخش پیشرفته", chat_id, call.message.message_id, reply_markup=kb)
                return

            if data == "back_panel":
                bot.edit_message_text("🛡 پنل مدیریت گپ", chat_id, call.message.message_id, reply_markup=panel_keyboard(chat_id))
                return

            if data == "p_close":
                try:
                    bot.delete_message(chat_id, call.message.message_id)
                except Exception:
                    pass
                return

            if data == "add_swear":
                if not is_bot_owner(chat_id, uid):
                    return
                user_steps[uid] = {"step": "add_swear", "chat_id": chat_id}
                bot.answer_callback_query(call.id)
                bot.send_message(chat_id, "کلمه فحش را بفرست (در گپ):")
                return

            if data == "del_swear":
                if not is_bot_owner(chat_id, uid):
                    return
                user_steps[uid] = {"step": "del_swear", "chat_id": chat_id}
                bot.answer_callback_query(call.id)
                bot.send_message(chat_id, "کدام فحش حذف شود؟ کلمه را بفرست:")
                return

            if data == "auto_help":
                bot.answer_callback_query(call.id)
                bot.send_message(chat_id, "برای پیام خودکار برو پیوی ربات → /start → پیام خودکار")
                return

            if data == "set_welcome":
                if not is_bot_owner(chat_id, uid):
                    return
                user_steps[uid] = {"step": "set_welcome", "chat_id": chat_id}
                bot.send_message(chat_id, "متن خوش‌آمد را بفرست.\nاز {name} و {id} می‌توانی استفاده کنی.\nبرای خاموش: خاموش")
                return

            if data == "set_leave":
                if not is_bot_owner(chat_id, uid):
                    return
                user_steps[uid] = {"step": "set_leave", "chat_id": chat_id}
                bot.send_message(chat_id, "متن لفت را بفرست.\nاز {name} می‌توانی استفاده کنی.\nبرای خاموش: خاموش")
                return

        bot.answer_callback_query(call.id)
    except Exception as e:
        print("callback error:", e)
        # ==================== بخش ۴ از ۴ ====================

@bot.message_handler(commands=['start'])
def start_pv(message):
    if message.chat.type != "private":
        return
    uid = message.from_user.id
    if not (is_main_owner(uid) or True):
        pass
    kb = InlineKeyboardMarkup(row_width=1)
    if is_main_owner(uid):
        kb.add(InlineKeyboardButton("➕ افزودن پیام خودکار", callback_data="pv_add_auto"))
        kb.add(InlineKeyboardButton("📋 لیست پیام‌های خودکار", callback_data="pv_list_auto"))
    bot.reply_to(
        message,
        "ربات مدیریت گپ\n\n"
        "مرا ادمین گپ کن، بعد در گپ بنویس: پنل\n\n"
        "دستورات:\n"
        "قفل | باز\n"
        "سکوت ۳ (با ریپلای)\n"
        "حذف سکوت | بن | آنبن\n"
        "تنظیم مالک | حذف مالک\n"
        "تنظیم ادمین | حذف ادمین\n"
        "تنظیم ویژه | حذف ویژه\n"
        "پنل",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("pv_"))
def pv_callbacks(call):
    uid = call.from_user.id
    if call.message.chat.type != "private":
        return
    if call.data == "pv_add_auto":
        user_steps[uid] = {"step": "auto_chat"}
        bot.send_message(call.message.chat.id, "آیدی عددی گپ را بفرست (مثلاً -100...):")
    elif call.data == "pv_list_auto":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, chat_id, keyword, answer, exact_match FROM autoreplies ORDER BY id DESC LIMIT 30")
        rows = c.fetchall()
        conn.close()
        if not rows:
            bot.send_message(call.message.chat.id, "خالی است.")
        else:
            text = "📋 پیام‌های خودکار:\n\n"
            for r in rows:
                mode = "دقیق" if r[4] else "شامل"
                text += f"#{r[0]} | گپ `{r[1]}`\nکلمه: {r[2]}\nجواب: {r[3]}\nحالت: {mode}\n\n"
            bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda m: m.chat.type == "private", content_types=['text'])
def pv_text(message):
    uid = message.from_user.id
    step = user_steps.get(uid, {}).get("step")
    data = user_steps.get(uid, {})

    if step == "auto_chat":
        try:
            chat_id = int(message.text.strip())
            user_steps[uid] = {"step": "auto_key", "chat_id": chat_id}
            bot.reply_to(message, "کلمه کلیدی را بفرست (مثلاً سلام):")
        except Exception:
            bot.reply_to(message, "آیدی عددی معتبر بفرست.")
        return

    if step == "auto_key":
        user_steps[uid] = {"step": "auto_answer", "chat_id": data["chat_id"], "keyword": message.text.strip()}
        bot.reply_to(message, "متن جواب خودکار را بفرست:")
        return

    if step == "auto_answer":
        user_steps[uid] = {
            "step": "auto_mode",
            "chat_id": data["chat_id"],
            "keyword": data["keyword"],
            "answer": message.text.strip()
        }
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("فقط وقتی دقیقاً همان کلمه بود", callback_data="auto_exact"),
            InlineKeyboardButton("هر وقت در پیام آمد", callback_data="auto_include")
        )
        bot.reply_to(message, "حالت تشخیص را انتخاب کن:", reply_markup=kb)
        return

@bot.callback_query_handler(func=lambda c: c.data in ["auto_exact", "auto_include"])
def auto_mode_cb(call):
    uid = call.from_user.id
    data = user_steps.get(uid, {})
    if data.get("step") != "auto_mode":
        bot.answer_callback_query(call.id)
        return
    exact = 1 if call.data == "auto_exact" else 0
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO autoreplies (chat_id, keyword, answer, exact_match, active) VALUES (?, ?, ?, ?, 1)",
        (data["chat_id"], data["keyword"], data["answer"], exact)
    )
    conn.commit()
    conn.close()
    user_steps.pop(uid, None)
    bot.edit_message_text("✅ پیام خودکار ذخیره شد.", call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda m: m.chat.type in ["group", "supergroup"] and m.text)
def group_steps(message):
    uid = message.from_user.id
    data = user_steps.get(uid)
    if not data:
        return
    step = data.get("step")
    chat_id = data.get("chat_id") or message.chat.id

    if step == "add_swear" and message.chat.id == chat_id:
        if not is_bot_owner(chat_id, uid):
            return
        word = message.text.strip().lower()
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO swears (chat_id, word) VALUES (?, ?)", (chat_id, word))
        conn.commit()
        conn.close()
        user_steps.pop(uid, None)
        bot.reply_to(message, f"✅ فحش «{word}» اضافه شد.")
        return

    if step == "del_swear" and message.chat.id == chat_id:
        if not is_bot_owner(chat_id, uid):
            return
        word = message.text.strip().lower()
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM swears WHERE chat_id=? AND word=?", (chat_id, word))
        conn.commit()
        conn.close()
        user_steps.pop(uid, None)
        bot.reply_to(message, f"✅ «{word}» حذف شد.")
        return

    if step == "set_welcome" and message.chat.id == chat_id:
        if not is_bot_owner(chat_id, uid):
            return
        txt = message.text.strip()
        conn = get_db()
        c = conn.cursor()
        if txt == "خاموش":
            c.execute("UPDATE groups SET welcome_enabled=0 WHERE chat_id=?", (chat_id,))
            bot.reply_to(message, "خوش‌آمد خاموش شد.")
        else:
            c.execute("UPDATE groups SET welcome_enabled=1, welcome_text=?, welcome_type=? WHERE chat_id=?",
                      (txt, "text", chat_id))
            bot.reply_to(message, "✅ خوش‌آمد تنظیم شد.")
        conn.commit()
        conn.close()
        user_steps.pop(uid, None)
        return

    if step == "set_leave" and message.chat.id == chat_id:
        if not is_bot_owner(chat_id, uid):
            return
        txt = message.text.strip()
        conn = get_db()
        c = conn.cursor()
        if txt == "خاموش":
            c.execute("UPDATE groups SET leave_enabled=0 WHERE chat_id=?", (chat_id,))
            bot.reply_to(message, "پیام لفت خاموش شد.")
        else:
            c.execute("UPDATE groups SET leave_enabled=1, leave_text=? WHERE chat_id=?", (txt, chat_id))
            bot.reply_to(message, "✅ پیام لفت تنظیم شد.")
        conn.commit()
        conn.close()
        user_steps.pop(uid, None)
        return

print("🤖 Group Manager started")
bot.infinity_polling(timeout=60, long_polling_timeout=50)
