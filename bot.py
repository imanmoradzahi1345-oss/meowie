import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
import sqlite3
import time
import re
from collections import defaultdict, deque

BOT_TOKEN = "8597049833:AAFnEjGLcOz09Duy6MIvOoMD9TA1-fiRhPE"
MAIN_OWNER_ID = 7530457395

bot = telebot.TeleBot(BOT_TOKEN)
flood_map = defaultdict(lambda: deque())
user_steps = {}

def get_db():
    return sqlite3.connect("group_manager.db", check_same_thread=False, timeout=30)

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        chat_id INTEGER PRIMARY KEY,
        title TEXT,
        locked INTEGER DEFAULT 0,
        lock_link INTEGER DEFAULT 0,
        lock_forward INTEGER DEFAULT 0,
        lock_gif INTEGER DEFAULT 0,
        lock_sticker INTEGER DEFAULT 0,
        lock_voice INTEGER DEFAULT 0,
        welcome_text TEXT,
        welcome_type TEXT DEFAULT 'text',
        welcome_file_id TEXT,
        leave_text TEXT,
        leave_enabled INTEGER DEFAULT 0,
        welcome_enabled INTEGER DEFAULT 0
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS bot_owners (
        chat_id INTEGER,
        user_id INTEGER,
        PRIMARY KEY (chat_id, user_id)
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS bot_admins (
        chat_id INTEGER,
        user_id INTEGER,
        PRIMARY KEY (chat_id, user_id)
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS specials (
        chat_id INTEGER,
        user_id INTEGER,
        PRIMARY KEY (chat_id, user_id)
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS swears (
        chat_id INTEGER,
        word TEXT,
        PRIMARY KEY (chat_id, word)
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS autoreplies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        keyword TEXT,
        answer TEXT,
        exact_match INTEGER DEFAULT 1,
        active INTEGER DEFAULT 1
    )
    """)
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
    c.execute("INSERT OR IGNORE INTO bot_owners (chat_id, user_id) VALUES (?, ?)", (chat.id, MAIN_OWNER_ID))
    conn.commit()
    conn.close()

def is_main_owner(uid):
    return int(uid) == int(MAIN_OWNER_ID)

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

def can_manage(chat_id, uid):
    return is_bot_admin(chat_id, uid)

def get_group(chat_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE chat_id=?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return row

def set_flag(chat_id, field, value):
    allowed = {
        "locked", "lock_link", "lock_forward", "lock_gif", "lock_sticker",
        "lock_voice", "welcome_enabled", "leave_enabled", "welcome_text",
        "leave_text", "welcome_type", "welcome_file_id"
    }
    if field not in allowed:
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE groups SET {}=? WHERE chat_id=?".format(field), (value, chat_id))
    conn.commit()
    conn.close()

def mute_user(chat_id, user_id, minutes):
    until = int(time.time()) + max(1, int(minutes)) * 60
    bot.restrict_chat_member(
        chat_id,
        user_id,
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
        chat_id,
        user_id,
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
    set_flag(chat_id, "locked", 1)

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
    set_flag(chat_id, "locked", 0)

def extract_target(message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    return None

def panel_kb(chat_id):
    g = get_group(chat_id)
    def mark(v):
        return "✅" if v else "❌"
    kb = InlineKeyboardMarkup(row_width=2)
    if not g:
        return kb
    kb.add(
        InlineKeyboardButton("لینک " + mark(g[3]), callback_data="tog_link"),
        InlineKeyboardButton("فوروارد " + mark(g[4]), callback_data="tog_forward")
    )
    kb.add(
        InlineKeyboardButton("گیف " + mark(g[5]), callback_data="tog_gif"),
        InlineKeyboardButton("استیکر " + mark(g[6]), callback_data="tog_sticker")
    )
    kb.add(
        InlineKeyboardButton("ویس " + mark(g[7]), callback_data="tog_voice"),
        InlineKeyboardButton("قفل کل " + mark(g[2]), callback_data="tog_lockall")
    )
    kb.add(
        InlineKeyboardButton("مالک‌ها", callback_data="list_owners"),
        InlineKeyboardButton("ادمین‌ها", callback_data="list_admins")
    )
    kb.add(
        InlineKeyboardButton("ویژه‌ها", callback_data="list_specials"),
        InlineKeyboardButton("فحش‌ها", callback_data="list_swears")
    )
    kb.add(InlineKeyboardButton("پیشرفته", callback_data="advanced"))
    kb.add(InlineKeyboardButton("بستن", callback_data="p_close"))
    return kb

def maybe_autoreply(message):
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
        if exact and text == keyword:
            bot.reply_to(message, answer)
            return
        if (not exact) and keyword in text:
            bot.reply_to(message, answer)
            return

def check_filters(message):
    chat_id = message.chat.id
    uid = message.from_user.id
    if is_bot_admin(chat_id, uid):
        maybe_autoreply(message)
        return
    g = get_group(chat_id)
    if not g:
        return
    text = message.text or message.caption or ""

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
            bot.send_message(chat_id, "فلود شدید - ۱۰ دقیقه سکوت")
        except Exception:
            pass
        return

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
                    bot.send_message(chat_id, "پیام پاک شد")
                except Exception:
                    pass
                return

    if g[3] and text and re.search(r"(https?://|www\.|t\.me/|telegram\.me/)", text, re.I):
        if not is_special(chat_id, uid):
            try:
                bot.delete_message(chat_id, message.message_id)
            except Exception:
                pass
            return

    if g[4] and (message.forward_date or message.forward_from or message.forward_from_chat):
        if not is_special(chat_id, uid):
            try:
                bot.delete_message(chat_id, message.message_id)
            except Exception:
                pass
            return

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

def save_auto(d, exact):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO autoreplies (chat_id, keyword, answer, exact_match, active) VALUES (?, ?, ?, ?, 1)",
        (d["chat_id"], d["keyword"], d["answer"], exact)
    )
    conn.commit()
    conn.close()

def handle_group_step(message):
    uid = message.from_user.id
    data = user_steps.get(uid, {})
    step = data.get("step")
    chat_id = data.get("chat_id")
    if message.chat.id != chat_id:
        return
    if not is_bot_owner(chat_id, uid):
        return
    if step == "add_swear":
        word = message.text.strip().lower()
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO swears (chat_id, word) VALUES (?, ?)", (chat_id, word))
        conn.commit()
        conn.close()
        user_steps.pop(uid, None)
        bot.reply_to(message, "فحش اضافه شد")
        return
    if step == "del_swear":
        word = message.text.strip().lower()
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM swears WHERE chat_id=? AND word=?", (chat_id, word))
        conn.commit()
        conn.close()
        user_steps.pop(uid, None)
        bot.reply_to(message, "فحش حذف شد")
        return
    if step == "set_welcome":
        txt = message.text.strip()
        if txt == "خاموش":
            set_flag(chat_id, "welcome_enabled", 0)
            bot.reply_to(message, "خوش آمد خاموش شد")
        else:
            set_flag(chat_id, "welcome_text", txt)
            set_flag(chat_id, "welcome_enabled", 1)
            bot.reply_to(message, "خوش آمد ذخیره شد")
        user_steps.pop(uid, None)
        return
    if step == "set_leave":
        txt = message.text.strip()
        if txt == "خاموش":
            set_flag(chat_id, "leave_enabled", 0)
            bot.reply_to(message, "لفت خاموش شد")
        else:
            set_flag(chat_id, "leave_text", txt)
            set_flag(chat_id, "leave_enabled", 1)
            bot.reply_to(message, "لفت ذخیره شد")
        user_steps.pop(uid, None)
        return
        @bot.message_handler(content_types=["new_chat_members"])
def on_new_members(message):
    try:
        ensure_group(message.chat)
        chat_id = message.chat.id
        me = bot.get_me()
        for m in message.new_chat_members:
            if m.id == me.id:
                conn = get_db()
                c = conn.cursor()
                c.execute("INSERT OR IGNORE INTO bot_owners (chat_id, user_id) VALUES (?, ?)", (chat_id, MAIN_OWNER_ID))
                try:
                    for a in bot.get_chat_administrators(chat_id):
                        if a.user.is_bot:
                            continue
                        c.execute("INSERT OR IGNORE INTO bot_admins (chat_id, user_id) VALUES (?, ?)", (chat_id, a.user.id))
                        if a.status == "creator":
                            c.execute("INSERT OR IGNORE INTO bot_owners (chat_id, user_id) VALUES (?, ?)", (chat_id, a.user.id))
                except Exception:
                    pass
                conn.commit()
                conn.close()
                bot.send_message(chat_id, "ربات فعال شد\nدستور: پنل")
                continue
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT welcome_enabled, welcome_text FROM groups WHERE chat_id=?", (chat_id,))
            w = c.fetchone()
            conn.close()
            if w and w[0]:
                name = m.first_name or "کاربر"
                text = (w[1] or "خوش آمدی {name}").replace("{name}", name).replace("{id}", str(m.id))
                bot.send_message(chat_id, text)
    except Exception as e:
        print("new_members:", e)

@bot.message_handler(content_types=["left_chat_member"])
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
            text = (row[1] or "{name} رفت").replace("{name}", name)
            bot.send_message(chat_id, text)
    except Exception as e:
        print("left:", e)

@bot.message_handler(func=lambda m: m.chat.type in ["group", "supergroup"], content_types=[
    "text", "photo", "video", "voice", "document", "sticker", "animation", "audio", "video_note"
])
def on_group_message(message):
    try:
        ensure_group(message.chat)
        chat_id = message.chat.id
        uid = message.from_user.id
        text = (message.text or "").strip()

        if text:
            low = text

            if low in ["پنل", "پنل مدیریت"]:
                if can_manage(chat_id, uid):
                    bot.reply_to(message, "پنل مدیریت", reply_markup=panel_kb(chat_id))
                return

            if low in ["قفل", "قفل گروه", "قفل گپ"]:
                if can_manage(chat_id, uid):
                    lock_group(chat_id)
                    bot.reply_to(message, "گپ قفل شد")
                return

            if low in ["باز", "باز کردن گروه", "باز کردن گپ", "باز گروه"]:
                if can_manage(chat_id, uid):
                    unlock_group(chat_id)
                    bot.reply_to(message, "گپ باز شد")
                return

            if low.startswith("سکوت"):
                if not can_manage(chat_id, uid):
                    return
                target = extract_target(message)
                if not target:
                    bot.reply_to(message, "روی پیام فرد ریپلای کن")
                    return
                parts = low.split()
                minutes = 5
                if len(parts) >= 2 and parts[1].isdigit():
                    minutes = int(parts[1])
                mute_user(chat_id, target.id, minutes)
                bot.reply_to(message, "سکوت {} دقیقه".format(minutes))
                return

            if low in ["حذف سکوت", "آزاد", "رفع سکوت"]:
                if not can_manage(chat_id, uid):
                    return
                target = extract_target(message)
                if not target:
                    bot.reply_to(message, "روی پیام فرد ریپلای کن")
                    return
                unmute_user(chat_id, target.id)
                bot.reply_to(message, "سکوت برداشته شد")
                return

            if low in ["بن", "اخراج"]:
                if not can_manage(chat_id, uid):
                    return
                target = extract_target(message)
                if not target:
                    bot.reply_to(message, "روی پیام فرد ریپلای کن")
                    return
                bot.ban_chat_member(chat_id, target.id)
                bot.reply_to(message, "بن شد")
                return

            if low in ["حذف بن", "آنبن"]:
                if not can_manage(chat_id, uid):
                    return
                target = extract_target(message)
                if not target:
                    bot.reply_to(message, "روی پیام فرد ریپلای کن")
                    return
                bot.unban_chat_member(chat_id, target.id)
                bot.reply_to(message, "آنبن شد")
                return

            if low == "تنظیم مالک":
                if not is_bot_owner(chat_id, uid):
                    return
                target = extract_target(message)
                if not target:
                    bot.reply_to(message, "ریپلای کن")
                    return
                conn = get_db()
                c = conn.cursor()
                c.execute("INSERT OR IGNORE INTO bot_owners (chat_id, user_id) VALUES (?, ?)", (chat_id, target.id))
                c.execute("INSERT OR IGNORE INTO bot_admins (chat_id, user_id) VALUES (?, ?)", (chat_id, target.id))
                conn.commit()
                conn.close()
                bot.reply_to(message, "مالک بات شد")
                return

            if low == "حذف مالک":
                if not is_bot_owner(chat_id, uid):
                    return
                target = extract_target(message)
                if not target:
                    bot.reply_to(message, "ریپلای کن")
                    return
                if target.id == MAIN_OWNER_ID:
                    bot.reply_to(message, "مالک اصلی قابل حذف نیست")
                    return
                conn = get_db()
                c = conn.cursor()
                c.execute("DELETE FROM bot_owners WHERE chat_id=? AND user_id=?", (chat_id, target.id))
                conn.commit()
                conn.close()
                bot.reply_to(message, "از مالکیت حذف شد")
                return

            if low == "تنظیم ادمین":
                if not is_bot_owner(chat_id, uid):
                    return
                target = extract_target(message)
                if not target:
                    bot.reply_to(message, "ریپلای کن")
                    return
                conn = get_db()
                c = conn.cursor()
                c.execute("INSERT OR IGNORE INTO bot_admins (chat_id, user_id) VALUES (?, ?)", (chat_id, target.id))
                conn.commit()
                conn.close()
                bot.reply_to(message, "ادمین بات شد")
                return

            if low == "حذف ادمین":
                if not is_bot_owner(chat_id, uid):
                    return
                target = extract_target(message)
                if not target:
                    bot.reply_to(message, "ریپلای کن")
                    return
                conn = get_db()
                c = conn.cursor()
                c.execute("DELETE FROM bot_admins WHERE chat_id=? AND user_id=?", (chat_id, target.id))
                conn.commit()
                conn.close()
                bot.reply_to(message, "ادمین بات حذف شد")
                return

            if low == "تنظیم ویژه":
                if not is_bot_owner(chat_id, uid):
                    return
                target = extract_target(message)
                if not target:
                    bot.reply_to(message, "ریپلای کن")
                    return
                conn = get_db()
                c = conn.cursor()
                c.execute("INSERT OR IGNORE INTO specials (chat_id, user_id) VALUES (?, ?)", (chat_id, target.id))
                conn.commit()
                conn.close()
                bot.reply_to(message, "ویژه شد")
                return

            if low == "حذف ویژه":
                if not is_bot_owner(chat_id, uid):
                    return
                target = extract_target(message)
                if not target:
                    bot.reply_to(message, "ریپلای کن")
                    return
                conn = get_db()
                c = conn.cursor()
                c.execute("DELETE FROM specials WHERE chat_id=? AND user_id=?", (chat_id, target.id))
                conn.commit()
                conn.close()
                bot.reply_to(message, "ویژه حذف شد")
                return

            step = user_steps.get(uid, {}).get("step")
            if step and user_steps.get(uid, {}).get("chat_id") == chat_id:
                handle_group_step(message)
                return

        check_filters(message)
    except Exception as e:
        print("group msg:", e)

@bot.callback_query_handler(func=lambda call: True)
def on_callback(call):
    try:
        uid = call.from_user.id
        data = call.data
        chat = call.message.chat

        if chat.type in ["group", "supergroup"]:
            chat_id = chat.id
            if not can_manage(chat_id, uid):
                bot.answer_callback_query(call.id, "دسترسی نداری", show_alert=True)
                return

            toggles = {
                "tog_link": "lock_link",
                "tog_forward": "lock_forward",
                "tog_gif": "lock_gif",
                "tog_sticker": "lock_sticker",
                "tog_voice": "lock_voice"
            }
            if data in toggles:
                field = toggles[data]
                g = get_group(chat_id)
                idx = {"lock_link": 3, "lock_forward": 4, "lock_gif": 5, "lock_sticker": 6, "lock_voice": 7}[field]
                cur = g[idx] if g else 0
                set_flag(chat_id, field, 0 if cur else 1)
                bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=panel_kb(chat_id))
                bot.answer_callback_query(call.id, "OK")
                return

            if data == "tog_lockall":
                g = get_group(chat_id)
                if g and g[2]:
                    unlock_group(chat_id)
                else:
                    lock_group(chat_id)
                bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=panel_kb(chat_id))
                bot.answer_callback_query(call.id, "OK")
                return

            if data == "list_owners":
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT user_id FROM bot_owners WHERE chat_id=?", (chat_id,))
                rows = c.fetchall()
                conn.close()
                bot.send_message(chat_id, "مالک ها:\n" + "\n".join(str(r[0]) for r in rows))
            elif data == "list_admins":
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT user_id FROM bot_admins WHERE chat_id=?", (chat_id,))
                rows = c.fetchall()
                conn.close()
                bot.send_message(chat_id, "ادمین ها:\n" + ("\n".join(str(r[0]) for r in rows) if rows else "خالی"))
            elif data == "list_specials":
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT user_id FROM specials WHERE chat_id=?", (chat_id,))
                rows = c.fetchall()
                conn.close()
                bot.send_message(chat_id, "ویژه ها:\n" + ("\n".join(str(r[0]) for r in rows) if rows else "خالی"))
            elif data == "list_swears":
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT word FROM swears WHERE chat_id=?", (chat_id,))
                rows = c.fetchall()
                conn.close()
                bot.send_message(chat_id, "فحش ها:\n" + ("\n".join(r[0] for r in rows) if rows else "خالی"))
            elif data == "advanced":
                if not is_bot_owner(chat_id, uid):
                    bot.answer_callback_query(call.id, "فقط مالک", show_alert=True)
                    return
                kb = InlineKeyboardMarkup(row_width=1)
                kb.add(InlineKeyboardButton("افزودن فحش", callback_data="add_swear"))
                kb.add(InlineKeyboardButton("حذف فحش", callback_data="del_swear"))
                kb.add(InlineKeyboardButton("خوش آمد", callback_data="set_welcome"))
                kb.add(InlineKeyboardButton("پیام لفت", callback_data="set_leave"))
                kb.add(InlineKeyboardButton("پیام خودکار از پیوی", callback_data="auto_help"))
                kb.add(InlineKeyboardButton("برگشت", callback_data="back_panel"))
                bot.edit_message_text("پیشرفته", chat_id, call.message.message_id, reply_markup=kb)
            elif data == "back_panel":
                bot.edit_message_text("پنل مدیریت", chat_id, call.message.message_id, reply_markup=panel_kb(chat_id))
            elif data == "p_close":
                try:
                    bot.delete_message(chat_id, call.message.message_id)
                except Exception:
                    pass
            elif data == "add_swear":
                user_steps[uid] = {"step": "add_swear", "chat_id": chat_id}
                bot.send_message(chat_id, "کلمه فحش را بفرست")
            elif data == "del_swear":
                user_steps[uid] = {"step": "del_swear", "chat_id": chat_id}
                bot.send_message(chat_id, "کلمه فحش برای حذف")
            elif data == "set_welcome":
                user_steps[uid] = {"step": "set_welcome", "chat_id": chat_id}
                bot.send_message(chat_id, "متن خوش آمد را بفرست\nاز {name} و {id} استفاده کن\nخاموش = غیرفعال")
            elif data == "set_leave":
                user_steps[uid] = {"step": "set_leave", "chat_id": chat_id}
                bot.send_message(chat_id, "متن لفت را بفرست\nخاموش = غیرفعال")
            elif data == "auto_help":
                bot.send_message(chat_id, "برو پیوی ربات /start بعد پیام خودکار")

            bot.answer_callback_query(call.id)
            return

        if chat.type == "private":
            if data == "pv_add_auto":
                user_steps[uid] = {"step": "auto_chat"}
                bot.send_message(uid, "آیدی گپ را بفرست مثلا -100...")
            elif data == "auto_exact":
                d = user_steps.get(uid, {})
                if d.get("step") == "auto_mode":
                    save_auto(d, 1)
                    user_steps.pop(uid, None)
                    bot.send_message(uid, "ذخیره شد حالت دقیق")
            elif data == "auto_include":
                d = user_steps.get(uid, {})
                if d.get("step") == "auto_mode":
                    save_auto(d, 0)
                    user_steps.pop(uid, None)
                    bot.send_message(uid, "ذخیره شد حالت شامل")
            bot.answer_callback_query(call.id)
    except Exception as e:
        print("callback:", e)

@bot.message_handler(commands=["start"])
def start_cmd(message):
    if message.chat.type != "private":
        return
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("افزودن پیام خودکار", callback_data="pv_add_auto"))
    bot.reply_to(
        message,
        "ربات مدیریت گپ\nربات را ادمین گپ کن و بنویس: پنل\n\nقفل | باز\nسکوت 3\nحذف سکوت | بن | آنبن\nتنظیم مالک | حذف مالک\nتنظیم ادمین | حذف ادمین\nتنظیم ویژه | حذف ویژه",
        reply_markup=kb
    )

@bot.message_handler(func=lambda m: m.chat.type == "private", content_types=["text"])
def pv_text(message):
    uid = message.from_user.id
    data = user_steps.get(uid, {})
    step = data.get("step")

    if step == "auto_chat":
        try:
            chat_id = int(message.text.strip())
            user_steps[uid] = {"step": "auto_key", "chat_id": chat_id}
            bot.reply_to(message, "کلمه کلیدی:")
        except Exception:
            bot.reply_to(message, "آیدی عددی بفرست")
        return

    if step == "auto_key":
        user_steps[uid] = {"step": "auto_answer", "chat_id": data["chat_id"], "keyword": message.text.strip()}
        bot.reply_to(message, "متن جواب:")
        return

    if step == "auto_answer":
        user_steps[uid] = {
            "step": "auto_mode",
            "chat_id": data["chat_id"],
            "keyword": data["keyword"],
            "answer": message.text.strip()
        }
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("فقط دقیقا همان کلمه", callback_data="auto_exact"))
        kb.add(InlineKeyboardButton("هر وقت در متن آمد", callback_data="auto_include"))
        bot.reply_to(message, "حالت را انتخاب کن:", reply_markup=kb)
        return

print("Bot started")
bot.infinity_polling(none_stop=True, timeout=60, long_polling_timeout=50)
