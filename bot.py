# -*- coding: utf-8 -*-
"""
ربات مدیریت گپ - نسخه اصلاح‌شده
دکمه‌های پنل + دستورات متنی + خوش‌آمد رندوم
"""

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
import sqlite3
import time
import re
import random
from collections import defaultdict, deque

BOT_TOKEN = "8617545814:AAFAofo_nV39gFT1-IgfXu-esnGgXol62r4"
MAIN_OWNER_ID = 7530457395
DEFAULT_WELCOME = "سلام {mention} عزیز به گپ {group}\nخوش اومدی"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
user_steps = {}
flood_map = defaultdict(lambda: deque())


def get_db():
    return sqlite3.connect("group_bot.db", check_same_thread=False, timeout=30)


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS groups (
        chat_id INTEGER PRIMARY KEY,
        title TEXT,
        welcome_text TEXT,
        welcome_enabled INTEGER DEFAULT 1,
        lock_link INTEGER DEFAULT 0,
        lock_forward INTEGER DEFAULT 0,
        lock_spam INTEGER DEFAULT 1,
        warn_limit INTEGER DEFAULT 3
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS bot_admins (
        chat_id INTEGER, user_id INTEGER,
        PRIMARY KEY (chat_id, user_id)
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS nicknames (
        chat_id INTEGER, user_id INTEGER, nick TEXT,
        PRIMARY KEY (chat_id, user_id)
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS warns (
        chat_id INTEGER, user_id INTEGER, count INTEGER DEFAULT 0,
        PRIMARY KEY (chat_id, user_id)
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS mutes (
        chat_id INTEGER, user_id INTEGER, until_ts INTEGER,
        PRIMARY KEY (chat_id, user_id)
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS message_stats (
        chat_id INTEGER, user_id INTEGER, count INTEGER DEFAULT 0,
        PRIMARY KEY (chat_id, user_id)
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS autoreplies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER, keyword TEXT, answer TEXT,
        exact_match INTEGER DEFAULT 1, active INTEGER DEFAULT 1
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS welcome_photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT UNIQUE
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS started_users (
        user_id INTEGER PRIMARY KEY
    )"""
    )
    conn.commit()
    conn.close()


init_db()


def ensure_group(chat):
    if not chat or chat.type not in ("group", "supergroup"):
        return
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO groups (chat_id, title, welcome_text) VALUES (?,?,?)",
        (chat.id, chat.title or "", DEFAULT_WELCOME),
    )
    c.execute("UPDATE groups SET title=? WHERE chat_id=?", (chat.title or "", chat.id))
    c.execute(
        "INSERT OR IGNORE INTO bot_admins (chat_id, user_id) VALUES (?,?)",
        (chat.id, MAIN_OWNER_ID),
    )
    try:
        for a in bot.get_chat_administrators(chat.id):
            if getattr(a.user, "is_bot", False):
                continue
            c.execute(
                "INSERT OR IGNORE INTO bot_admins (chat_id, user_id) VALUES (?,?)",
                (chat.id, a.user.id),
            )
    except Exception as e:
        print("admin sync:", e)
    conn.commit()
    conn.close()


def is_main_owner(uid):
    try:
        return int(uid) == int(MAIN_OWNER_ID)
    except Exception:
        return False


def is_bot_admin(chat_id, uid):
    if is_main_owner(uid):
        return True
    try:
        m = bot.get_chat_member(chat_id, uid)
        if m.status in ("creator", "administrator"):
            conn = get_db()
            c = conn.cursor()
            c.execute(
                "INSERT OR IGNORE INTO bot_admins (chat_id, user_id) VALUES (?,?)",
                (chat_id, uid),
            )
            conn.commit()
            conn.close()
            return True
    except Exception:
        pass
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM bot_admins WHERE chat_id=? AND user_id=?",
        (chat_id, uid),
    )
    row = c.fetchone()
    conn.close()
    return bool(row)


def get_group_row(chat_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE chat_id=?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return row


def set_group_field(chat_id, field, value):
    allowed = {
        "welcome_text",
        "welcome_enabled",
        "lock_link",
        "lock_forward",
        "lock_spam",
        "warn_limit",
        "title",
    }
    if field not in allowed:
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE groups SET {}=? WHERE chat_id=?".format(field), (value, chat_id))
    conn.commit()
    conn.close()


def format_welcome(template, user, chat):
    name = user.first_name or "کاربر"
    username = "@{}".format(user.username) if user.username else "ندارد"
    mention = '<a href="tg://user?id={}">{}</a>'.format(user.id, name)
    group = chat.title or "گپ"
    text = template or DEFAULT_WELCOME
    return (
        text.replace("{name}", name)
        .replace("{username}", username)
        .replace("{id}", str(user.id))
        .replace("{group}", group)
        .replace("{mention}", mention)
    )


def mute_user(chat_id, user_id, seconds):
    seconds = max(1, int(seconds))
    until = int(time.time()) + seconds
    bot.restrict_chat_member(
        chat_id,
        user_id,
        permissions=ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
        ),
        until_date=until,
    )
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO mutes (chat_id, user_id, until_ts) VALUES (?,?,?)",
        (chat_id, user_id, until),
    )
    conn.commit()
    conn.close()


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
            can_invite_users=True,
        ),
    )
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM mutes WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    conn.commit()
    conn.close()


def add_warn(chat_id, user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO warns (chat_id, user_id, count) VALUES (?,?,0)",
        (chat_id, user_id),
    )
    c.execute(
        "UPDATE warns SET count = count + 1 WHERE chat_id=? AND user_id=?",
        (chat_id, user_id),
    )
    c.execute(
        "SELECT count FROM warns WHERE chat_id=? AND user_id=?",
        (chat_id, user_id),
    )
    count = c.fetchone()[0]
    conn.commit()
    conn.close()
    return count


def clear_warn(chat_id, user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM warns WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    conn.commit()
    conn.close()


def inc_stat(chat_id, user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO message_stats (chat_id, user_id, count) VALUES (?,?,0)",
        (chat_id, user_id),
    )
    c.execute(
        "UPDATE message_stats SET count = count + 1 WHERE chat_id=? AND user_id=?",
        (chat_id, user_id),
    )
    conn.commit()
    conn.close()


def get_nick(chat_id, user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT nick FROM nicknames WHERE chat_id=? AND user_id=?",
        (chat_id, user_id),
    )
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def extract_target(message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    return None


def safe_delete(chat_id, msg_id):
    try:
        bot.delete_message(chat_id, msg_id)
    except Exception:
        pass


def panel_kb(chat_id):
    g = get_group_row(chat_id)

    def mark(v):
        return "✅" if v else "❌"

    kb = InlineKeyboardMarkup(row_width=2)
    if not g:
        return kb
    cid = str(chat_id)
    kb.add(
        InlineKeyboardButton("لینک " + mark(g[4]), callback_data="tog|{}|link".format(cid)),
        InlineKeyboardButton("فوروارد " + mark(g[5]), callback_data="tog|{}|fwd".format(cid)),
    )
    kb.add(
        InlineKeyboardButton("ضدسپم " + mark(g[6]), callback_data="tog|{}|spam".format(cid)),
        InlineKeyboardButton("خوش‌آمد " + mark(g[3]), callback_data="tog|{}|wel".format(cid)),
    )
    kb.add(InlineKeyboardButton("📝 متن خوش‌آمد", callback_data="act|{}|weltext".format(cid)))
    kb.add(InlineKeyboardButton("🤖 پاسخ خودکار", callback_data="act|{}|auto".format(cid)))
    kb.add(InlineKeyboardButton("📖 راهنمای دستورات", callback_data="act|{}|help".format(cid)))
    kb.add(InlineKeyboardButton("بستن", callback_data="act|{}|close".format(cid)))
    return kb


def owner_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📤 آپلود عکس خوش‌آمد", callback_data="own|upload"))
    kb.add(InlineKeyboardButton("🖼 تعداد / پاک عکس‌ها", callback_data="own|photos"))
    kb.add(InlineKeyboardButton("📢 تبلیغ به گپ‌ها", callback_data="own|bcg"))
    kb.add(InlineKeyboardButton("📢 تبلیغ به کاربران استارت", callback_data="own|bcu"))
    return kb


@bot.message_handler(content_types=["new_chat_members"])
def on_new_members(message):
    try:
        ensure_group(message.chat)
        chat_id = message.chat.id
        me = bot.get_me()
        for member in message.new_chat_members:
            if member.id == me.id:
                ensure_group(message.chat)
                bot.send_message(
                    chat_id,
                    "✅ ربات فعال شد.\nادمین‌های گپ می‌توانند بنویسند: پنل",
                )
                continue
            g = get_group_row(chat_id)
            if not g or not g[3]:
                continue
            caption = format_welcome(g[2] or DEFAULT_WELCOME, member, message.chat)
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT file_id FROM welcome_photos")
            photos = [r[0] for r in c.fetchall()]
            conn.close()
            try:
                if photos:
                    bot.send_photo(
                        chat_id,
                        random.choice(photos),
                        caption=caption,
                        parse_mode="HTML",
                    )
                else:
                    bot.send_message(chat_id, caption, parse_mode="HTML")
            except Exception:
                try:
                    bot.send_message(chat_id, caption, parse_mode="HTML")
                except Exception:
                    pass
    except Exception as e:
        print("new_members:", e)


@bot.message_handler(
    func=lambda m: m.chat.type in ("group", "supergroup"),
    content_types=[
        "text",
        "photo",
        "video",
        "voice",
        "document",
        "sticker",
        "animation",
        "audio",
        "video_note",
    ],
)
def on_group(message):
    try:
        ensure_group(message.chat)
        chat_id = message.chat.id
        uid = message.from_user.id
        text = (message.text or "").strip()

        if not message.from_user.is_bot:
            inc_stat(chat_id, uid)

        st = user_steps.get(uid, {})
        if st.get("step") == "wel_text" and st.get("chat_id") == chat_id:
            if is_bot_admin(chat_id, uid):
                set_group_field(chat_id, "welcome_text", text)
                user_steps.pop(uid, None)
                bot.reply_to(message, "✅ متن خوش‌آمد ذخیره شد.")
            return

        if text:
            if text in ("پنل", "پنل مدیریت"):
                if not is_bot_admin(chat_id, uid):
                    bot.reply_to(message, "فقط ادمین گپ / ادمین ربات")
                    return
                bot.reply_to(message, "🛡 پنل مدیریت گپ", reply_markup=panel_kb(chat_id))
                return

            if text == "آمار کل":
                conn = get_db()
                c = conn.cursor()
                c.execute(
                    "SELECT user_id, count FROM message_stats WHERE chat_id=? ORDER BY count DESC LIMIT 15",
                    (chat_id,),
                )
                rows = c.fetchall()
                conn.close()
                if not rows:
                    bot.reply_to(message, "آماری نیست.")
                    return
                lines = ["📊 آمار کل\n"]
                for i, (u, cnt) in enumerate(rows, 1):
                    nick = get_nick(chat_id, u) or str(u)
                    lines.append("{}. {} — {} پیام".format(i, nick, cnt))
                bot.reply_to(message, "\n".join(lines))
                return

            if is_bot_admin(chat_id, uid):
                if text.startswith("سکوت"):
                    target = extract_target(message)
                    if not target:
                        bot.reply_to(message, "روی پیام کاربر ریپلای کن")
                        return
                    parts = text.split()
                    sec = 60
                    if len(parts) >= 2 and parts[1].isdigit():
                        sec = int(parts[1])
                    try:
                        mute_user(chat_id, target.id, sec)
                        bot.reply_to(message, "🔇 سکوت {} ثانیه".format(sec))
                    except Exception as e:
                        bot.reply_to(message, "خطا: ربات دسترسی محدود کردن ندارد\n{}".format(e))
                    return

                if text == "حذف سکوت":
                    target = extract_target(message)
                    if not target:
                        bot.reply_to(message, "ریپلای کن")
                        return
                    try:
                        unmute_user(chat_id, target.id)
                        bot.reply_to(message, "✅ سکوت برداشته شد")
                    except Exception as e:
                        bot.reply_to(message, "خطا: {}".format(e))
                    return

                if text == "بن":
                    target = extract_target(message)
                    if not target:
                        bot.reply_to(message, "ریپلای کن")
                        return
                    try:
                        bot.ban_chat_member(chat_id, target.id)
                        bot.reply_to(message, "🚫 بن شد")
                    except Exception as e:
                        bot.reply_to(message, "خطا: {}".format(e))
                    return

                if text == "حذف بن":
                    target = extract_target(message)
                    if not target:
                        bot.reply_to(message, "ریپلای کن")
                        return
                    try:
                        bot.unban_chat_member(chat_id, target.id, only_if_banned=True)
                        bot.reply_to(message, "✅ آنبن شد")
                    except Exception as e:
                        bot.reply_to(message, "خطا: {}".format(e))
                    return

                if text == "اخطار":
                    target = extract_target(message)
                    if not target:
                        bot.reply_to(message, "ریپلای کن")
                        return
                    cnt = add_warn(chat_id, target.id)
                    g = get_group_row(chat_id)
                    limit = g[7] if g else 3
                    bot.reply_to(message, "⚠️ اخطار {}/{}".format(cnt, limit))
                    if cnt >= limit:
                        try:
                            mute_user(chat_id, target.id, 600)
                            bot.reply_to(message, "سقف اخطار — ۱۰ دقیقه سکوت")
                        except Exception:
                            pass
                    return

                if text == "حذف اخطار":
                    target = extract_target(message)
                    if not target:
                        bot.reply_to(message, "ریپلای کن")
                        return
                    clear_warn(chat_id, target.id)
                    bot.reply_to(message, "✅ اخطار پاک شد")
                    return

                if text == "پاکسازی لیست اخطار":
                    conn = get_db()
                    c = conn.cursor()
                    c.execute("DELETE FROM warns WHERE chat_id=?", (chat_id,))
                    conn.commit()
                    conn.close()
                    bot.reply_to(message, "✅ همه اخطارها پاک شد")
                    return

                if text == "پاکسازی لیست سکوت":
                    conn = get_db()
                    c = conn.cursor()
                    c.execute("SELECT user_id FROM mutes WHERE chat_id=?", (chat_id,))
                    rows = c.fetchall()
                    c.execute("DELETE FROM mutes WHERE chat_id=?", (chat_id,))
                    conn.commit()
                    conn.close()
                    for (u,) in rows:
                        try:
                            unmute_user(chat_id, u)
                        except Exception:
                            pass
                    bot.reply_to(message, "✅ لیست سکوت پاک شد")
                    return

                if text == "پاکسازی لیست بن":
                    bot.reply_to(
                        message,
                        "تلگرام لیست کامل بن را به ربات نمی‌دهد. با «حذف بن» تکی آنبن کن.",
                    )
                    return

                if text == "تنظیم ادمین":
                    target = extract_target(message)
                    if not target:
                        bot.reply_to(message, "ریپلای کن")
                        return
                    conn = get_db()
                    c = conn.cursor()
                    c.execute(
                        "INSERT OR IGNORE INTO bot_admins (chat_id, user_id) VALUES (?,?)",
                        (chat_id, target.id),
                    )
                    conn.commit()
                    conn.close()
                    bot.reply_to(
                        message,
                        "✅ {} ادمین ربات شد و می‌تواند پنل بزند".format(target.first_name),
                    )
                    return

                if text.startswith("تنظیم لقب"):
                    target = extract_target(message)
                    if not target:
                        bot.reply_to(message, "ریپلای کن")
                        return
                    parts = text.split(maxsplit=2)
                    if len(parts) < 3:
                        bot.reply_to(message, "مثال: تنظیم لقب گرگ")
                        return
                    nick = parts[2].strip()
                    conn = get_db()
                    c = conn.cursor()
                    c.execute(
                        "INSERT OR REPLACE INTO nicknames (chat_id, user_id, nick) VALUES (?,?,?)",
                        (chat_id, target.id, nick),
                    )
                    conn.commit()
                    conn.close()
                    bot.reply_to(message, "✅ لقب: {}".format(nick))
                    return

                if text == "حذف":
                    if message.reply_to_message:
                        safe_delete(chat_id, message.reply_to_message.message_id)
                        safe_delete(chat_id, message.message_id)
                    return

                if text.startswith("حذف "):
                    parts = text.split()
                    if len(parts) == 2 and parts[1].isdigit():
                        n = min(int(parts[1]), 100)
                        mid = message.message_id
                        safe_delete(chat_id, mid)
                        deleted = 0
                        for i in range(1, n + 1):
                            try:
                                bot.delete_message(chat_id, mid - i)
                                deleted += 1
                            except Exception:
                                pass
                        try:
                            bot.send_message(chat_id, "🗑 {} پیام حذف شد".format(deleted))
                        except Exception:
                            pass
                        return

        apply_filters(message)
    except Exception as e:
        print("on_group:", e)


def apply_filters(message):
    chat_id = message.chat.id
    uid = message.from_user.id
    if is_bot_admin(chat_id, uid):
        maybe_auto(message)
        return
    g = get_group_row(chat_id)
    if not g:
        return
    text = message.text or message.caption or ""

    if g[6]:
        key = (chat_id, uid)
        now = time.time()
        q = flood_map[key]
        q.append(now)
        while q and now - q[0] > 10:
            q.popleft()
        if len(q) >= 25:
            safe_delete(chat_id, message.message_id)
            try:
                mute_user(chat_id, uid, 120)
            except Exception:
                pass
            return

    if g[4] and text and re.search(r"(https?://|www\.|t\.me/)", text, re.I):
        safe_delete(chat_id, message.message_id)
        return

    if g[5] and (message.forward_date or message.forward_from or message.forward_from_chat):
        safe_delete(chat_id, message.message_id)
        return

    maybe_auto(message)


def maybe_auto(message):
    if not message.text:
        return
    chat_id = message.chat.id
    text = message.text.strip()
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT keyword, answer, exact_match FROM autoreplies WHERE chat_id=? AND active=1",
        (chat_id,),
    )
    rows = c.fetchall()
    conn.close()
    for keyword, answer, exact in rows:
        if exact and text == keyword:
            bot.reply_to(message, answer)
            return
        if (not exact) and keyword in text:
            bot.reply_to(message, answer)
            return


@bot.callback_query_handler(func=lambda call: True)
def on_callback(call):
    try:
        uid = call.from_user.id
        data = call.data or ""
        print("CB:", data, "from", uid)

        if data.startswith("tog|"):
            _, cid_s, key = data.split("|", 2)
            chat_id = int(cid_s)
            if not is_bot_admin(chat_id, uid):
                bot.answer_callback_query(call.id, "دسترسی نداری", show_alert=True)
                return
            g = get_group_row(chat_id)
            if not g:
                bot.answer_callback_query(call.id, "گپ یافت نشد", show_alert=True)
                return
            mapping = {
                "link": ("lock_link", 4),
                "fwd": ("lock_forward", 5),
                "spam": ("lock_spam", 6),
                "wel": ("welcome_enabled", 3),
            }
            if key not in mapping:
                bot.answer_callback_query(call.id)
                return
            field, idx = mapping[key]
            new_val = 0 if g[idx] else 1
            set_group_field(chat_id, field, new_val)
            try:
                bot.edit_message_reply_markup(
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=panel_kb(chat_id),
                )
            except Exception:
                pass
            bot.answer_callback_query(call.id, "تغییر کرد ✅")
            return

        if data.startswith("act|"):
            _, cid_s, act = data.split("|", 2)
            chat_id = int(cid_s)
            if not is_bot_admin(chat_id, uid):
                bot.answer_callback_query(call.id, "دسترسی نداری", show_alert=True)
                return

            if act == "weltext":
                user_steps[uid] = {"step": "wel_text", "chat_id": chat_id}
                bot.answer_callback_query(call.id)
                bot.send_message(
                    call.message.chat.id,
                    "متن خوش‌آمد را بفرست:\n{name} {username} {id} {group} {mention}",
                )
                return

            if act == "auto":
                code = "AUTO-{}".format(chat_id)
                bot.answer_callback_query(call.id)
                bot.send_message(
                    call.message.chat.id,
                    "این کد را کپی کن و در پیوی ربات بفرست:\n\n`{}`".format(code),
                    parse_mode="Markdown",
                )
                return

            if act == "help":
                bot.answer_callback_query(call.id)
                bot.send_message(
                    call.message.chat.id,
                    "📖 دستورات (با ریپلای روی کاربر):\n\n"
                    "سکوت 30\nحذف سکوت\nبن\nحذف بن\n"
                    "اخطار\nحذف اخطار\n"
                    "پاکسازی لیست اخطار\nپاکسازی لیست سکوت\n"
                    "تنظیم ادمین\nتنظیم لقب گرگ\n"
                    "حذف\nحذف 50\nآمار کل\nپنل",
                )
                return

            if act == "close":
                safe_delete(call.message.chat.id, call.message.message_id)
                bot.answer_callback_query(call.id)
                return

            bot.answer_callback_query(call.id)
            return

        if data.startswith("own|"):
            if not is_main_owner(uid):
                bot.answer_callback_query(call.id, "فقط ادمین اصلی", show_alert=True)
                return
            act = data.split("|", 1)[1]
            if act == "upload":
                user_steps[uid] = {"step": "upload_photo"}
                bot.send_message(uid, "عکس‌ها را بفرست. پایان: /done")
            elif act == "photos":
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM welcome_photos")
                n = c.fetchone()[0]
                conn.close()
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("پاک کردن همه", callback_data="own|clear"))
                bot.send_message(uid, "تعداد عکس: {}".format(n), reply_markup=kb)
            elif act == "clear":
                conn = get_db()
                c = conn.cursor()
                c.execute("DELETE FROM welcome_photos")
                conn.commit()
                conn.close()
                bot.send_message(uid, "✅ پاک شد")
            elif act == "bcg":
                user_steps[uid] = {"step": "bc_groups"}
                bot.send_message(uid, "محتوای تبلیغ گپ‌ها را بفرست")
            elif act == "bcu":
                user_steps[uid] = {"step": "bc_users"}
                bot.send_message(uid, "محتوای تبلیغ کاربران را بفرست")
            bot.answer_callback_query(call.id)
            return

        if data in ("auto_exact", "auto_include"):
            d = user_steps.get(uid, {})
            if d.get("step") != "auto_mode":
                bot.answer_callback_query(call.id)
                return
            exact = 1 if data == "auto_exact" else 0
            conn = get_db()
            c = conn.cursor()
            c.execute(
                "INSERT INTO autoreplies (chat_id, keyword, answer, exact_match, active) VALUES (?,?,?,?,1)",
                (d["chat_id"], d["keyword"], d["answer"], exact),
            )
            conn.commit()
            conn.close()
            user_steps.pop(uid, None)
            try:
                bot.edit_message_text(
                    "✅ پاسخ خودکار ذخیره شد",
                    call.message.chat.id,
                    call.message.message_id,
                )
            except Exception:
                bot.send_message(uid, "✅ ذخیره شد")
            bot.answer_callback_query(call.id)
            return

        bot.answer_callback_query(call.id)
    except Exception as e:
        print("callback error:", e)
        try:
            bot.answer_callback_query(call.id, "خطا", show_alert=True)
        except Exception:
            pass


@bot.message_handler(commands=["start"])
def cmd_start(message):
    if message.chat.type != "private":
        return
    uid = message.from_user.id
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO started_users (user_id) VALUES (?)", (uid,))
    conn.commit()
    conn.close()
    if is_main_owner(uid):
        bot.reply_to(message, "👑 پنل ادمین اصلی", reply_markup=owner_kb())
    else:
        bot.reply_to(
            message,
            "ربات را ادمین گپ کن و در گپ بنویس: پنل\n"
            "اگر کد AUTO-... داری همین‌جا بفرست.",
        )


@bot.message_handler(commands=["done"])
def cmd_done(message):
    if message.chat.type != "private":
        return
    uid = message.from_user.id
    if user_steps.get(uid, {}).get("step") == "upload_photo":
        user_steps.pop(uid, None)
        bot.reply_to(message, "✅ آپلود تمام شد")


@bot.message_handler(
    func=lambda m: m.chat.type == "private",
    content_types=["text", "photo", "video", "animation", "document", "voice", "sticker"],
)
def on_private(message):
    uid = message.from_user.id
    text = (message.text or "").strip()
    st = user_steps.get(uid, {})
    step = st.get("step")

    if text.startswith("AUTO-"):
        try:
            chat_id = int(text.replace("AUTO-", "").strip())
        except Exception:
            bot.reply_to(message, "کد نامعتبر")
            return
        if not (is_bot_admin(chat_id, uid) or is_main_owner(uid)):
            bot.reply_to(message, "دسترسی به این گپ نداری")
            return
        user_steps[uid] = {"step": "auto_key", "chat_id": chat_id}
        bot.reply_to(message, "کلمه کلیدی (مثال سلام):")
        return

    if step == "auto_key":
        user_steps[uid] = {
            "step": "auto_ans",
            "chat_id": st["chat_id"],
            "keyword": text,
        }
        bot.reply_to(message, "متن جواب:")
        return

    if step == "auto_ans":
        user_steps[uid] = {
            "step": "auto_mode",
            "chat_id": st["chat_id"],
            "keyword": st["keyword"],
            "answer": text,
        }
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("فقط دقیقاً همان کلمه", callback_data="auto_exact"))
        kb.add(InlineKeyboardButton("هر جا در متن بود", callback_data="auto_include"))
        bot.reply_to(message, "حالت:", reply_markup=kb)
        return

    if step == "upload_photo" and is_main_owner(uid):
        if message.photo:
            fid = message.photo[-1].file_id
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO welcome_photos (file_id) VALUES (?)", (fid,))
            conn.commit()
            c.execute("SELECT COUNT(*) FROM welcome_photos")
            n = c.fetchone()[0]
            conn.close()
            bot.reply_to(message, "✅ ذخیره شد | کل: {}\n/done برای پایان".format(n))
        else:
            bot.reply_to(message, "فقط عکس یا /done")
        return

    if step in ("bc_groups", "bc_users") and is_main_owner(uid):
        conn = get_db()
        c = conn.cursor()
        if step == "bc_groups":
            c.execute("SELECT chat_id FROM groups")
        else:
            c.execute("SELECT user_id FROM started_users")
        targets = [r[0] for r in c.fetchall()]
        conn.close()
        ok = 0
        for t in targets:
            try:
                bot.copy_message(t, message.chat.id, message.message_id)
                ok += 1
                time.sleep(0.04)
            except Exception:
                pass
        user_steps.pop(uid, None)
        bot.reply_to(message, "✅ ارسال به {} مقصد".format(ok))
        return

    if is_main_owner(uid) and not step:
        bot.reply_to(message, "منوی ادمین:", reply_markup=owner_kb())


if __name__ == "__main__":
    print("Bot started OK")
    bot.infinity_polling(none_stop=True, timeout=60, long_polling_timeout=50)
