# -*- coding: utf-8 -*-
"""
ربات مدیریت گپ چندگانه
- خوش‌آمد با عکس رندوم + کپشن متغیر
- پنل داخل گپ
- سکوت/بن/اخطار/لقب/آمار/پاسخ خودکار/ضد اسپم
"""

import telebot
from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ChatPermissions,
)
import sqlite3
import time
import re
import random
import threading
from collections import defaultdict, deque

# ===================== تنظیمات =====================
BOT_TOKEN = "8617545814:AAFAofo_nV39gFT1-IgfXu-esnGgXol62r4"
MAIN_OWNER_ID = 7530457395

DEFAULT_WELCOME = "سلام {mention} عزیز به گپ {group}\nخوش اومدی"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# وضعیت‌های موقت
user_steps = {}
flood_map = defaultdict(lambda: deque())
msg_count_cache = defaultdict(int)  # فقط کمکی؛ آمار اصلی در DB

# ===================== دیتابیس =====================
def get_db():
    return sqlite3.connect("group_bot.db", check_same_thread=False, timeout=30)


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS groups (
            chat_id INTEGER PRIMARY KEY,
            title TEXT,
            welcome_text TEXT,
            welcome_enabled INTEGER DEFAULT 1,
            lock_link INTEGER DEFAULT 0,
            lock_forward INTEGER DEFAULT 0,
            lock_spam INTEGER DEFAULT 1,
            warn_limit INTEGER DEFAULT 3
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_admins (
            chat_id INTEGER,
            user_id INTEGER,
            PRIMARY KEY (chat_id, user_id)
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS nicknames (
            chat_id INTEGER,
            user_id INTEGER,
            nick TEXT,
            PRIMARY KEY (chat_id, user_id)
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS warns (
            chat_id INTEGER,
            user_id INTEGER,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, user_id)
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS mutes (
            chat_id INTEGER,
            user_id INTEGER,
            until_ts INTEGER,
            PRIMARY KEY (chat_id, user_id)
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS message_stats (
            chat_id INTEGER,
            user_id INTEGER,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, user_id)
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS autoreplies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            keyword TEXT,
            answer TEXT,
            exact_match INTEGER DEFAULT 1,
            active INTEGER DEFAULT 1
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS welcome_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT UNIQUE
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS started_users (
            user_id INTEGER PRIMARY KEY
        )
        """
    )

    conn.commit()
    conn.close()


init_db()


# ===================== کمک‌ها =====================
def ensure_group(chat):
    if not chat or chat.type not in ("group", "supergroup"):
        return
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO groups (chat_id, title, welcome_text) VALUES (?, ?, ?)",
        (chat.id, chat.title or "", DEFAULT_WELCOME),
    )
    c.execute("UPDATE groups SET title=? WHERE chat_id=?", (chat.title or "", chat.id))
    # سازنده گپ و ادمین‌ها
    try:
        for a in bot.get_chat_administrators(chat.id):
            if a.user.is_bot:
                continue
            c.execute(
                "INSERT OR IGNORE INTO bot_admins (chat_id, user_id) VALUES (?, ?)",
                (chat.id, a.user.id),
            )
    except Exception:
        pass
    # مالک اصلی بات در همه گپ‌ها ادمین بات
    c.execute(
        "INSERT OR IGNORE INTO bot_admins (chat_id, user_id) VALUES (?, ?)",
        (chat.id, MAIN_OWNER_ID),
    )
    conn.commit()
    conn.close()


def is_main_owner(uid):
    return int(uid) == int(MAIN_OWNER_ID)


def is_bot_admin(chat_id, uid):
    if is_main_owner(uid):
        return True
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
    c.execute(f"UPDATE groups SET {field}=? WHERE chat_id=?", (value, chat_id))
    conn.commit()
    conn.close()


def format_welcome(template, user, chat):
    name = user.first_name or "کاربر"
    username = f"@{user.username}" if user.username else "ندارد"
    mention = f'<a href="tg://user?id={user.id}">{name}</a>'
    group = chat.title or "گپ"
    text = template or DEFAULT_WELCOME
    text = (
        text.replace("{name}", name)
        .replace("{username}", username)
        .replace("{id}", str(user.id))
        .replace("{group}", group)
        .replace("{mention}", mention)
    )
    return text


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
        "INSERT OR REPLACE INTO mutes (chat_id, user_id, until_ts) VALUES (?, ?, ?)",
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
        "INSERT OR IGNORE INTO warns (chat_id, user_id, count) VALUES (?, ?, 0)",
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
        "INSERT OR IGNORE INTO message_stats (chat_id, user_id, count) VALUES (?, ?, 0)",
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
    def m(v):
        return "✅" if v else "❌"
    kb = InlineKeyboardMarkup(row_width=2)
    if not g:
        return kb
    # g: 0 chat_id,1 title,2 welcome_text,3 welcome_enabled,4 lock_link,5 lock_forward,6 lock_spam,7 warn_limit
    kb.add(
        InlineKeyboardButton(f"لینک {m(g[4])}", callback_data=f"g:{chat_id}:tog_link"),
        InlineKeyboardButton(f"فوروارد {m(g[5])}", callback_data=f"g:{chat_id}:tog_fwd"),
    )
    kb.add(
        InlineKeyboardButton(f"ضدسپم {m(g[6])}", callback_data=f"g:{chat_id}:tog_spam"),
        InlineKeyboardButton(f"خوش‌آمد {m(g[3])}", callback_data=f"g:{chat_id}:tog_wel"),
    )
    kb.add(InlineKeyboardButton("متن خوش‌آمد", callback_data=f"g:{chat_id}:set_wel_text"))
    kb.add(InlineKeyboardButton("پاسخ خودکار", callback_data=f"g:{chat_id}:auto"))
    kb.add(InlineKeyboardButton("بستن", callback_data=f"g:{chat_id}:close"))
    return kb


def owner_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📤 آپلود عکس خوش‌آمد", callback_data="own:upload"))
    kb.add(InlineKeyboardButton("🖼 لیست/پاک عکس‌ها", callback_data="own:photos"))
    kb.add(InlineKeyboardButton("📢 تبلیغ به گپ‌ها", callback_data="own:bc_groups"))
    kb.add(InlineKeyboardButton("📢 تبلیغ به استارت‌کننده‌ها", callback_data="own:bc_users"))
    return kb


# ===================== جوین / لفت =====================
@bot.message_handler(content_types=["new_chat_members"])
def on_new_members(message):
    try:
        ensure_group(message.chat)
        chat_id = message.chat.id
        me = bot.get_me()

        for member in message.new_chat_members:
            if member.id == me.id:
                ensure_group(message.chat)
                bot.send_message(chat_id, "✅ ربات فعال شد.\nبرای پنل بنویس: پنل")
                continue

            g = get_group_row(chat_id)
            if not g or not g[3]:
                continue

            template = g[2] or DEFAULT_WELCOME
            caption = format_welcome(template, member, message.chat)

            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT file_id FROM welcome_photos")
            photos = [r[0] for r in c.fetchall()]
            conn.close()

            try:
                if photos:
                    fid = random.choice(photos)
                    bot.send_photo(
                        chat_id,
                        fid,
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


# ===================== دستورات گپ =====================
@bot.message_handler(
    func=lambda m: m.chat.type in ["group", "supergroup"],
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

        # آمار پیام
        if not message.from_user.is_bot:
            inc_stat(chat_id, uid)

        # استپ تنظیم متن خوش‌آمد
        step = user_steps.get(uid, {})
        if step.get("step") == "wel_text" and step.get("chat_id") == chat_id:
            if not is_bot_admin(chat_id, uid):
                return
            set_group_field(chat_id, "welcome_text", text)
            user_steps.pop(uid, None)
            bot.reply_to(message, "✅ متن خوش‌آمد ذخیره شد.")
            return

        if text:
            # --- پنل ---
            if text in ["پنل", "پنل مدیریت"]:
                if not is_bot_admin(chat_id, uid):
                    return
                bot.reply_to(message, "🛡 پنل مدیریت گپ", reply_markup=panel_kb(chat_id))
                return

            # --- آمار کل ---
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
                    bot.reply_to(message, "هنوز آماری نیست.")
                    return
                lines = ["📊 آمار کل گپ\n"]
                for i, (u, cnt) in enumerate(rows, 1):
                    nick = get_nick(chat_id, u)
                    label = nick or str(u)
                    lines.append(f"{i}. {label} — {cnt} پیام")
                bot.reply_to(message, "\n".join(lines))
                return

            # --- دستورات ادمین ---
            if is_bot_admin(chat_id, uid):
                # سکوت 10
                if text.startswith("سکوت"):
                    target = extract_target(message)
                    if not target:
                        bot.reply_to(message, "روی پیام کاربر ریپلای کن.")
                        return
                    parts = text.split()
                    sec = 60
                    if len(parts) >= 2 and parts[1].isdigit():
                        sec = int(parts[1])
                    mute_user(chat_id, target.id, sec)
                    bot.reply_to(message, f"🔇 سکوت به مدت {sec} ثانیه")
                    return

                if text == "حذف سکوت":
                    target = extract_target(message)
                    if not target:
                        bot.reply_to(message, "ریپلای کن.")
                        return
                    unmute_user(chat_id, target.id)
                    bot.reply_to(message, "✅ سکوت برداشته شد.")
                    return

                if text == "بن":
                    target = extract_target(message)
                    if not target:
                        bot.reply_to(message, "ریپلای کن.")
                        return
                    bot.ban_chat_member(chat_id, target.id)
                    bot.reply_to(message, "🚫 بن شد.")
                    return

                if text == "حذف بن":
                    target = extract_target(message)
                    if not target:
                        bot.reply_to(message, "ریپلای کن.")
                        return
                    bot.unban_chat_member(chat_id, target.id, only_if_banned=True)
                    bot.reply_to(message, "✅ بن برداشته شد.")
                    return

                if text == "پاکسازی لیست بن":
                    # تلگرام API لیست کامل بن را همیشه نمی‌دهد؛ تلاش با administrators نه
                    bot.reply_to(
                        message,
                        "برای آنبن همه، از تلگرام لیست بن‌شده‌ها در دسترس کامل نیست.\n"
                        "کاربران را تکی با «حذف بن» آزاد کن.",
                    )
                    return

                if text == "اخطار":
                    target = extract_target(message)
                    if not target:
                        bot.reply_to(message, "ریپلای کن.")
                        return
                    cnt = add_warn(chat_id, target.id)
                    g = get_group_row(chat_id)
                    limit = g[7] if g else 3
                    bot.reply_to(message, f"⚠️ اخطار {cnt}/{limit}")
                    if cnt >= limit:
                        mute_user(chat_id, target.id, 600)
                        bot.reply_to(message, "به‌خاطر اخطار زیاد، ۱۰ دقیقه سکوت شد.")
                    return

                if text == "حذف اخطار":
                    target = extract_target(message)
                    if not target:
                        bot.reply_to(message, "ریپلای کن.")
                        return
                    clear_warn(chat_id, target.id)
                    bot.reply_to(message, "✅ اخطار پاک شد.")
                    return

                if text == "پاکسازی لیست اخطار":
                    conn = get_db()
                    c = conn.cursor()
                    c.execute("DELETE FROM warns WHERE chat_id=?", (chat_id,))
                    conn.commit()
                    conn.close()
                    bot.reply_to(message, "✅ همه اخطارها پاک شد.")
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
                    bot.reply_to(message, "✅ لیست سکوت پاکسازی شد.")
                    return

                if text == "تنظیم ادمین":
                    target = extract_target(message)
                    if not target:
                        bot.reply_to(message, "ریپلای کن.")
                        return
                    conn = get_db()
                    c = conn.cursor()
                    c.execute(
                        "INSERT OR IGNORE INTO bot_admins (chat_id, user_id) VALUES (?, ?)",
                        (chat_id, target.id),
                    )
                    conn.commit()
                    conn.close()
                    bot.reply_to(message, f"✅ {target.first_name} ادمین ربات شد و می‌تواند از پنل استفاده کند.")
                    return

                if text.startswith("تنظیم لقب"):
                    target = extract_target(message)
                    if not target:
                        bot.reply_to(message, "ریپلای کن.")
                        return
                    parts = text.split(maxsplit=2)
                    if len(parts) < 3:
                        bot.reply_to(message, "مثال: تنظیم لقب گرگ")
                        return
                    nick = parts[2].strip()
                    conn = get_db()
                    c = conn.cursor()
                    c.execute(
                        "INSERT OR REPLACE INTO nicknames (chat_id, user_id, nick) VALUES (?, ?, ?)",
                        (chat_id, target.id, nick),
                    )
                    conn.commit()
                    conn.close()
                    bot.reply_to(message, f"✅ لقب ثبت شد: {nick}")
                    return

                if text == "حذف":
                    if message.reply_to_message:
                        safe_delete(chat_id, message.reply_to_message.message_id)
                        safe_delete(chat_id, message.message_id)
                    return

                if text.startswith("حذف ") and text.split()[0] == "حذف":
                    parts = text.split()
                    if len(parts) == 2 and parts[1].isdigit():
                        n = min(int(parts[1]), 100)
                        # حذف پیام‌های اخیر تا حد ممکن
                        safe_delete(chat_id, message.message_id)
                        # تلگرام API مستقیم bulk delete محدود است؛ از message_id رو به عقب
                        mid = message.message_id
                        deleted = 0
                        for i in range(1, n + 1):
                            try:
                                bot.delete_message(chat_id, mid - i)
                                deleted += 1
                            except Exception:
                                pass
                        try:
                            bot.send_message(chat_id, f"🗑 حدود {deleted} پیام حذف شد.")
                        except Exception:
                            pass
                        return

        # فیلترها و پاسخ خودکار
        apply_filters_and_auto(message)
    except Exception as e:
        print("on_group:", e)


def apply_filters_and_auto(message):
    chat_id = message.chat.id
    uid = message.from_user.id
    if is_bot_admin(chat_id, uid):
        maybe_auto(message)
        return

    g = get_group_row(chat_id)
    if not g:
        return

    text = message.text or message.caption or ""

    # ضد اسپم ساده: بیش از ۲۵ پیام در ۱۰ ثانیه
    if g[6]:
        key = (chat_id, uid)
        now = time.time()
        q = flood_map[key]
        q.append(now)
        while q and now - q[0] > 10:
            q.popleft()
        if len(q) >= 25:
            try:
                safe_delete(chat_id, message.message_id)
                mute_user(chat_id, uid, 120)
            except Exception:
                pass
            return

    # قفل لینک
    if g[4] and text and re.search(r"(https?://|www\.|t\.me/)", text, re.I):
        safe_delete(chat_id, message.message_id)
        return

    # قفل فوروارد
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
        if not exact and keyword in text:
            bot.reply_to(message, answer)
            return


# ===================== کال‌بک پنل گپ =====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("g:"))
def group_panel_cb(call):
    try:
        parts = call.data.split(":")
        # g:chat_id:action
        chat_id = int(parts[1])
        action = parts[2]
        uid = call.from_user.id

        if not is_bot_admin(chat_id, uid):
            bot.answer_callback_query(call.id, "دسترسی نداری", show_alert=True)
            return

        if action == "tog_link":
            g = get_group_row(chat_id)
            set_group_field(chat_id, "lock_link", 0 if g[4] else 1)
        elif action == "tog_fwd":
            g = get_group_row(chat_id)
            set_group_field(chat_id, "lock_forward", 0 if g[5] else 1)
        elif action == "tog_spam":
            g = get_group_row(chat_id)
            set_group_field(chat_id, "lock_spam", 0 if g[6] else 1)
        elif action == "tog_wel":
            g = get_group_row(chat_id)
            set_group_field(chat_id, "welcome_enabled", 0 if g[3] else 1)
        elif action == "set_wel_text":
            user_steps[uid] = {"step": "wel_text", "chat_id": chat_id}
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id,
                "متن خوش‌آمد جدید را بفرست.\n"
                "متغیرها: {name} {username} {id} {group} {mention}",
            )
            return
        elif action == "auto":
            code = f"AUTO-{chat_id}"
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id,
                "برای تنظیم پاسخ خودکار این کد را در پیوی ربات بفرست:\n\n"
                f"`{code}`\n\n"
                "کد را لمس کن تا کپی شود.",
                parse_mode="Markdown",
            )
            return
        elif action == "close":
            safe_delete(call.message.chat.id, call.message.message_id)
            bot.answer_callback_query(call.id)
            return

        bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=panel_kb(chat_id),
        )
        bot.answer_callback_query(call.id, "انجام شد")
    except Exception as e:
        print("panel cb:", e)
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass


# ===================== پیوی =====================
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
        bot.reply_to(
            message,
            "👑 پنل ادمین اصلی\n\n"
            "عکس خوش‌آمد را از دکمه آپلود کن.\n"
            "تبلیغات را از همین‌جا بفرست.",
            reply_markup=owner_kb(),
        )
    else:
        bot.reply_to(
            message,
            "سلام 👋\n"
            "ربات را ادمین گپ کن و در گپ بنویس: پنل\n\n"
            "اگر کد پاسخ خودکار داری (مثل AUTO-100...) همین‌جا بفرست.",
        )


@bot.callback_query_handler(func=lambda c: c.data.startswith("own:"))
def owner_cb(call):
    uid = call.from_user.id
    if not is_main_owner(uid):
        bot.answer_callback_query(call.id, "فقط ادمین اصلی", show_alert=True)
        return
    action = call.data.split(":")[1]

    if action == "upload":
        user_steps[uid] = {"step": "upload_photo"}
        bot.send_message(uid, "عکس‌های خوش‌آمد را بفرست (هر پیام یک عکس).\nبرای پایان: /done")
    elif action == "photos":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM welcome_photos")
        n = c.fetchone()[0]
        conn.close()
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🗑 پاک کردن همه عکس‌ها", callback_data="own:clear_photos"))
        bot.send_message(uid, f"تعداد عکس‌های خوش‌آمد: {n}", reply_markup=kb)
    elif action == "clear_photos":
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM welcome_photos")
        conn.commit()
        conn.close()
        bot.send_message(uid, "✅ همه عکس‌ها پاک شد.")
    elif action == "bc_groups":
        user_steps[uid] = {"step": "bc_groups"}
        bot.send_message(uid, "متن یا رسانه تبلیغ برای همه گپ‌ها را بفرست:")
    elif action == "bc_users":
        user_steps[uid] = {"step": "bc_users"}
        bot.send_message(uid, "متن یا رسانه تبلیغ برای استارت‌کننده‌ها را بفرست:")

    bot.answer_callback_query(call.id)


@bot.message_handler(commands=["done"])
def cmd_done(message):
    if message.chat.type != "private":
        return
    uid = message.from_user.id
    if user_steps.get(uid, {}).get("step") == "upload_photo":
        user_steps.pop(uid, None)
        bot.reply_to(message, "✅ آپلود تمام شد.")


@bot.message_handler(
    func=lambda m: m.chat.type == "private",
    content_types=["text", "photo", "video", "animation", "document", "voice", "sticker"],
)
def on_private(message):
    uid = message.from_user.id
    text = (message.text or "").strip()
    step_data = user_steps.get(uid, {})
    step = step_data.get("step")

    # کد پاسخ خودکار
    if text.startswith("AUTO-"):
        try:
            chat_id = int(text.replace("AUTO-", "").strip())
        except Exception:
            bot.reply_to(message, "کد نامعتبر است.")
            return
        if not is_bot_admin(chat_id, uid) and not is_main_owner(uid):
            bot.reply_to(message, "به این گپ دسترسی نداری.")
            return
        user_steps[uid] = {"step": "auto_key", "chat_id": chat_id}
        bot.reply_to(message, "کلمه کلیدی را بفرست (مثال: سلام)")
        return

    if step == "auto_key":
        user_steps[uid] = {
            "step": "auto_ans",
            "chat_id": step_data["chat_id"],
            "keyword": text,
        }
        bot.reply_to(message, "متن جواب خودکار را بفرست:")
        return

    if step == "auto_ans":
        user_steps[uid] = {
            "step": "auto_mode",
            "chat_id": step_data["chat_id"],
            "keyword": step_data["keyword"],
            "answer": text,
        }
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(
            InlineKeyboardButton("فقط دقیقاً همان کلمه", callback_data="auto:exact"),
            InlineKeyboardButton("هر جا در متن بود", callback_data="auto:include"),
        )
        bot.reply_to(message, "حالت تشخیص را انتخاب کن:", reply_markup=kb)
        return

    # آپلود عکس خوش‌آمد
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
            bot.reply_to(message, f"✅ ذخیره شد. تعداد کل: {n}\nادامه بده یا /done")
        else:
            bot.reply_to(message, "فقط عکس بفرست یا /done")
        return

    # تبلیغات
    if step in ("bc_groups", "bc_users") and is_main_owner(uid):
        targets = []
        conn = get_db()
        c = conn.cursor()
        if step == "bc_groups":
            c.execute("SELECT chat_id FROM groups")
            targets = [r[0] for r in c.fetchall()]
        else:
            c.execute("SELECT user_id FROM started_users")
            targets = [r[0] for r in c.fetchall()]
        conn.close()

        ok = 0
        for t in targets:
            try:
                if message.photo:
                    bot.send_photo(t, message.photo[-1].file_id, caption=message.caption or None)
                elif message.video:
                    bot.send_video(t, message.video.file_id, caption=message.caption or None)
                elif message.text:
                    bot.send_message(t, message.text)
                elif message.animation:
                    bot.send_animation(t, message.animation.file_id, caption=message.caption or None)
                else:
                    bot.copy_message(t, message.chat.id, message.message_id)
                ok += 1
                time.sleep(0.05)
            except Exception:
                pass
        user_steps.pop(uid, None)
        bot.reply_to(message, f"✅ ارسال شد به {ok} مقصد.")
        return

    if is_main_owner(uid) and not step:
        bot.reply_to(message, "از منوی زیر استفاده کن:", reply_markup=owner_kb())


@bot.callback_query_handler(func=lambda c: c.data.startswith("auto:"))
def auto_mode_cb(call):
    uid = call.from_user.id
    data = user_steps.get(uid, {})
    if data.get("step") != "auto_mode":
        bot.answer_callback_query(call.id)
        return
    exact = 1 if call.data == "auto:exact" else 0
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO autoreplies (chat_id, keyword, answer, exact_match, active) VALUES (?, ?, ?, ?, 1)",
        (data["chat_id"], data["keyword"], data["answer"], exact),
    )
    conn.commit()
    conn.close()
    user_steps.pop(uid, None)
    bot.edit_message_text("✅ پاسخ خودکار ذخیره شد.", call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)


# ===================== اجرا =====================
if __name__ == "__main__":
    print("Bot started...")
    bot.infinity_polling(none_stop=True, timeout=60, long_polling_timeout=50)
