import telebot
from telebot import types
import sqlite3
import time
import threading
import re
from collections import defaultdict, deque

# =========================
# CONFIG
# =========================

BOT_TOKEN = "8636563885:AAH-Ihpb7-Ql9MwD1lZ824rwu1sdb3uUH8o"

DB_NAME = "group_manager.db"

bot = telebot.TeleBot(
    BOT_TOKEN,
    parse_mode="HTML",
    threaded=True,
    num_threads=20
)

DB_LOCK = threading.Lock()

flood_data = defaultdict(
    lambda: defaultdict(deque)
)

repeat_data = {}

mute_data = {}

LOCK_NAMES = {
    "link": "🔗 لینک",
    "photo": "🖼 عکس",
    "video": "🎬 فیلم",
    "animation": "🎞 گیف",
    "sticker": "🎭 استیکر",
    "voice": "🎤 ویس",
    "audio": "🎵 آهنگ",
    "document": "📄 فایل",
    "forward": "↪️ فوروارد"
}

LOCK_ALIASES = {
    "لینک": "link",
    "عکس": "photo",
    "فیلم": "video",
    "ویدیو": "video",
    "گیف": "animation",
    "استیکر": "sticker",
    "ویس": "voice",
    "آهنگ": "audio",
    "صوت": "audio",
    "فایل": "document",
    "فوروارد": "forward"
}

LINK_RE = re.compile(
    r"(https?://|www\.|t\.me/|telegram\.me/)",
    re.IGNORECASE
)


# =========================
# DATABASE
# =========================

def connect_db():
    con = sqlite3.connect(
        DB_NAME,
        timeout=30,
        check_same_thread=False
    )
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with DB_LOCK:
        con = connect_db()

        con.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            chat_id INTEGER PRIMARY KEY,
            title TEXT DEFAULT '',
            warn_limit INTEGER DEFAULT 3,
            flood_limit INTEGER DEFAULT 6,
            flood_seconds INTEGER DEFAULT 5,
            anti_link INTEGER DEFAULT 0,
            anti_forward INTEGER DEFAULT 0,
            anti_repeat INTEGER DEFAULT 0,
            welcome_enabled INTEGER DEFAULT 1,
            welcome TEXT DEFAULT ''
        )
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            chat_id INTEGER,
            user_id INTEGER,
            count INTEGER DEFAULT 0,
            PRIMARY KEY(chat_id, user_id)
        )
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS locks (
            chat_id INTEGER,
            lock_name TEXT,
            enabled INTEGER DEFAULT 0,
            PRIMARY KEY(chat_id, lock_name)
        )
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            admin_id INTEGER,
            action TEXT,
            reason TEXT,
            created_at INTEGER
        )
        """)

        con.commit()
        con.close()


def ensure_group(chat):
    if chat.type not in ("group", "supergroup"):
        return

    with DB_LOCK:
        con = connect_db()

        con.execute("""
        INSERT OR IGNORE INTO groups
        (chat_id, title, welcome)
        VALUES (?, ?, ?)
        """, (
            chat.id,
            chat.title or "Group",
            "👋 سلام {name}!\n\n"
            "به <b>{group}</b> خوش اومدی ❤️"
        ))

        con.execute("""
        UPDATE groups
        SET title=?
        WHERE chat_id=?
        """, (
            chat.title or "Group",
            chat.id
        ))

        con.commit()
        con.close()


def get_settings(chat_id):
    con = connect_db()

    row = con.execute("""
    SELECT *
    FROM groups
    WHERE chat_id=?
    """, (chat_id,)).fetchone()

    con.close()

    return row


def set_setting(chat_id, field, value):
    allowed = {
        "warn_limit",
        "flood_limit",
        "flood_seconds",
        "anti_link",
        "anti_forward",
        "anti_repeat",
        "welcome_enabled",
        "welcome"
    }

    if field not in allowed:
        return

    with DB_LOCK:
        con = connect_db()

        con.execute(
            f"""
            UPDATE groups
            SET {field}=?
            WHERE chat_id=?
            """,
            (value, chat_id)
        )

        con.commit()
        con.close()


def get_lock(chat_id, name):
    con = connect_db()

    row = con.execute("""
    SELECT enabled
    FROM locks
    WHERE chat_id=?
    AND lock_name=?
    """, (
        chat_id,
        name
    )).fetchone()

    con.close()

    if not row:
        return False

    return bool(row["enabled"])


def set_lock(chat_id, name, enabled):
    with DB_LOCK:
        con = connect_db()

        con.execute("""
        INSERT INTO locks
        (chat_id, lock_name, enabled)
        VALUES (?, ?, ?)
        ON CONFLICT(chat_id, lock_name)
        DO UPDATE SET enabled=excluded.enabled
        """, (
            chat_id,
            name,
            1 if enabled else 0
        ))

        con.commit()
        con.close()


def get_warn(chat_id, user_id):
    con = connect_db()

    row = con.execute("""
    SELECT count
    FROM warnings
    WHERE chat_id=?
    AND user_id=?
    """, (
        chat_id,
        user_id
    )).fetchone()

    con.close()

    return row["count"] if row else 0


def set_warn(chat_id, user_id, count):
    with DB_LOCK:
        con = connect_db()

        con.execute("""
        INSERT INTO warnings
        (chat_id, user_id, count)
        VALUES (?, ?, ?)
        ON CONFLICT(chat_id, user_id)
        DO UPDATE SET count=excluded.count
        """, (
            chat_id,
            user_id,
            max(0, count)
        ))

        con.commit()
        con.close()


def reset_warn(chat_id, user_id):
    with DB_LOCK:
        con = connect_db()

        con.execute("""
        DELETE FROM warnings
        WHERE chat_id=?
        AND user_id=?
        """, (
            chat_id,
            user_id
        ))

        con.commit()
        con.close()


def save_action(
    chat_id,
    user_id,
    admin_id,
    action,
    reason=""
):
    with DB_LOCK:
        con = connect_db()

        con.execute("""
        INSERT INTO actions
        (chat_id, user_id, admin_id,
         action, reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            chat_id,
            user_id,
            admin_id,
            action,
            reason,
            int(time.time())
        ))

        con.commit()
        con.close()


init_db()
# =========================
# HELPERS
# =========================

def is_group(message):
    return message.chat.type in (
        "group",
        "supergroup"
    )


def is_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(
            chat_id,
            user_id
        )

        return member.status in (
            "administrator",
            "creator"
        )

    except Exception:
        return False


def mention(user):
    name = user.first_name or "User"

    return (
        f'<a href="tg://user?id={user.id}">'
        f'{name}</a>'
    )


def get_target(message):
    if message.reply_to_message:
        return message.reply_to_message.from_user

    parts = (message.text or "").split()

    if len(parts) > 1:
        value = parts[1]

        if value.lstrip("-").isdigit():
            try:
                member = bot.get_chat_member(
                    message.chat.id,
                    int(value)
                )

                return member.user

            except Exception:
                pass

    return None


def delete_message(message):
    try:
        bot.delete_message(
            message.chat.id,
            message.message_id
        )
    except Exception as e:
        print("Delete:", e)


def ban_user(chat_id, user_id):
    try:
        bot.ban_chat_member(
            chat_id,
            user_id
        )
        return True

    except Exception as e:
        print("Ban:", e)
        return False


def kick_user(chat_id, user_id):
    try:
        bot.ban_chat_member(
            chat_id,
            user_id
        )

        bot.unban_chat_member(
            chat_id,
            user_id,
            only_if_banned=True
        )

        return True

    except Exception as e:
        print("Kick:", e)
        return False


def mute_user(
    chat_id,
    user_id,
    seconds
):
    try:
        until = int(
            time.time() + seconds
        )

        bot.restrict_chat_member(
            chat_id,
            user_id,
            permissions=types.ChatPermissions(
                can_send_messages=False
            ),
            until_date=until
        )

        mute_data[
            (chat_id, user_id)
        ] = until

        return True

    except Exception as e:
        print("Mute:", e)
        return False


def unmute_user(chat_id, user_id):
    try:
        bot.restrict_chat_member(
            chat_id,
            user_id,
            permissions=types.ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )

        mute_data.pop(
            (chat_id, user_id),
            None
        )

        return True

    except Exception as e:
        print("Unmute:", e)
        return False


def duration_from_message(message):
    parts = (message.text or "").split()

    if len(parts) < 2:
        return 600

    value = parts[1].lower()

    match = re.match(
        r"^(\d+)(s|m|h|d)?$",
        value
    )

    if not match:
        return 600

    number = int(match.group(1))
    unit = match.group(2) or "m"

    multipliers = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400
    }

    return min(
        number * multipliers[unit],
        30 * 86400
    )


def has_link(message):
    text = (
        message.text
        or message.caption
        or ""
    )

    return bool(
        LINK_RE.search(text)
    )


def is_forwarded(message):
    if getattr(
        message,
        "forward_origin",
        None
    ):
        return True

    if getattr(
        message,
        "forward_from",
        None
    ):
        return True

    if getattr(
        message,
        "forward_from_chat",
        None
    ):
        return True

    return False


def media_type(message):
    mapping = {
        "photo": "photo",
        "video": "video",
        "animation": "animation",
        "sticker": "sticker",
        "voice": "voice",
        "audio": "audio",
        "document": "document"
    }

    return mapping.get(
        message.content_type
    )


def flood_check(message):
    settings = get_settings(
        message.chat.id
    )

    if not settings:
        return False

    now = time.time()

    queue = flood_data[
        message.chat.id
    ][message.from_user.id]

    queue.append(now)

    while queue and (
        now - queue[0]
        > settings["flood_seconds"]
    ):
        queue.popleft()

    return (
        len(queue)
        > settings["flood_limit"]
    )


def repeat_check(message):
    text = (
        message.text
        or message.caption
        or ""
    ).strip()

    if not text:
        return False

    key = (
        message.chat.id,
        message.from_user.id
    )

    old = repeat_data.get(key)

    repeat_data[key] = text

    return old == text


# =========================
# PRIVATE START
# =========================

@bot.message_handler(
    commands=["start"]
)
def start(message):
    if message.chat.type != "private":
        return

    keyboard = types.InlineKeyboardMarkup(
        row_width=2
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🛡 امکانات",
            callback_data="private_features"
        ),
        types.InlineKeyboardButton(
            "📖 راهنما",
            callback_data="private_help"
        )
    )

    bot.send_message(
        message.chat.id,
        "🤖 <b>GROUP MANAGER</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🛡 ربات حرفه‌ای مدیریت گروه\n\n"
        "ربات را به گروه اضافه کن، "
        "ادمینش کن و سپس داخل گروه بزن:\n\n"
        "<code>/panel</code>",
        reply_markup=keyboard
    )


@bot.message_handler(
    commands=["help"]
)
def help_command(message):
    bot.send_message(
        message.chat.id,
        "📖 <b>راهنمای ربات</b>\n\n"
        "⚙️ /panel\n"
        "باز کردن پنل مدیریت\n\n"
        "مدیریت کاربران با Reply:\n"
        "🔨 بن\n"
        "👢 کیک\n"
        "🔇 سکوت 10m\n"
        "🔊 رفع سکوت\n"
        "⚠️ اخطار\n"
        "➖ رفع اخطار\n\n"
        "قفل‌ها:\n"
        "<code>قفل لینک</code>\n"
        "<code>باز لینک</code>\n"
        "<code>قفل عکس</code>\n"
        "<code>قفل فیلم</code>\n"
        "<code>قفل گیف</code>\n"
        "<code>قفل استیکر</code>\n"
        "<code>قفل ویس</code>\n"
        "<code>قفل فایل</code>\n"
        "<code>قفل فوروارد</code>"
    )


# =========================
# PANEL
# =========================

def main_panel():
    keyboard = types.InlineKeyboardMarkup(
        row_width=2
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🛡 کاربران",
            callback_data="panel_users"
        ),
        types.InlineKeyboardButton(
            "🔒 قفل‌ها",
            callback_data="panel_locks"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🤖 ضداسپم",
            callback_data="panel_spam"
        ),
        types.InlineKeyboardButton(
            "⚠️ اخطار",
            callback_data="panel_warn"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "📊 آمار",
            callback_data="panel_stats"
        ),
        types.InlineKeyboardButton(
            "⚙️ تنظیمات",
            callback_data="panel_settings"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "📖 راهنما",
            callback_data="panel_help"
        )
    )

    return keyboard


def back_keyboard():
    keyboard = types.InlineKeyboardMarkup()

    keyboard.add(
        types.InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="panel_main"
        )
    )

    return keyboard


@bot.message_handler(
    commands=["panel"]
)
def panel(message):
    if not is_group(message):
        return

    ensure_group(message.chat)

    if not is_admin(
        message.chat.id,
        message.from_user.id
    ):
        bot.reply_to(
            message,
            "⛔ فقط ادمین‌ها می‌توانند پنل را باز کنند."
        )
        return

    bot.send_message(
        message.chat.id,
        "⚙️ <b>پنل مدیریت گروه</b>\n\n"
        "بخش موردنظر را انتخاب کن:",
        reply_markup=main_panel()
    )


# =========================
# PANEL CALLBACK
# =========================

@bot.callback_query_handler(
    func=lambda call:
    call.data.startswith("panel_")
)
def panel_callback(call):
    chat_id = call.message.chat.id

    if not is_admin(
        chat_id,
        call.from_user.id
    ):
        bot.answer_callback_query(
            call.id,
            "⛔ فقط ادمین.",
            show_alert=True
        )
        return

    data = call.data

    if data == "panel_main":
        text = (
            "⚙️ <b>پنل مدیریت گروه</b>\n\n"
            "بخش موردنظر را انتخاب کن:"
        )

        keyboard = main_panel()

    elif data == "panel_users":
        text = (
            "🛡 <b>مدیریت کاربران</b>\n\n"
            "دستورات را روی پیام کاربر "
            "Reply کن:\n\n"
            "🔨 بن\n"
            "👢 کیک\n"
            "🔇 سکوت 10m\n"
            "🔊 رفع سکوت\n"
            "⚠️ اخطار\n"
            "➖ رفع اخطار"
        )

        keyboard = back_keyboard()

    elif data == "panel_locks":
        lines = [
            "🔒 <b>وضعیت قفل‌ها</b>",
            ""
        ]

        for name, title in LOCK_NAMES.items():
            status = (
                "🟢 فعال"
                if get_lock(chat_id, name)
                else "🔴 خاموش"
            )

            lines.append(
                f"{title}: {status}"
            )

        lines.extend([
            "",
            "برای تغییر:",
            "<code>قفل لینک</code>",
            "<code>باز لینک</code>"
        ])

        text = "\n".join(lines)

        keyboard = back_keyboard()

    elif data == "panel_spam":
        settings = get_settings(chat_id)

        text = (
            "🤖 <b>ضداسپم</b>\n\n"
            f"📨 Flood: "
            f"<b>{settings['flood_limit']}</b>\n"
            f"⏱ زمان: "
            f"<b>{settings['flood_seconds']} ثانیه</b>\n\n"
            f"🔗 ضدلینک: "
            f"{'🟢' if settings['anti_link'] else '🔴'}\n"
            f"↪️ ضدفوروارد: "
            f"{'🟢' if settings['anti_forward'] else '🔴'}\n"
            f"🔁 ضدتکرار: "
            f"{'🟢' if settings['anti_repeat'] else '🔴'}"
        )

        keyboard = types.InlineKeyboardMarkup(
            row_width=2
        )

        keyboard.add(
            types.InlineKeyboardButton(
                "🔗 ضدلینک",
                callback_data="toggle_anti_link"
            ),
            types.InlineKeyboardButton(
                "↪️ ضدفوروارد",
                callback_data="toggle_anti_forward"
            )
        )

        keyboard.add(
            types.InlineKeyboardButton(
                "🔁 ضدتکرار",
                callback_data="toggle_anti_repeat"
            )
        )

        keyboard.add(
            types.InlineKeyboardButton(
                "🔙 برگشت",
                callback_data="panel_main"
            )
        )

    elif data == "panel_warn":
        settings = get_settings(chat_id)

        text = (
            "⚠️ <b>سیستم اخطار</b>\n\n"
            f"حد فعلی: "
            f"<b>{settings['warn_limit']}</b>\n\n"
            "پس از رسیدن کاربر به حد، "
            "به‌صورت خودکار بن می‌شود."
        )

        keyboard = types.InlineKeyboardMarkup(
            row_width=2
        )

        keyboard.add(
            types.InlineKeyboardButton(
                "3️⃣",
                callback_data="warn_3"
            ),
            types.InlineKeyboardButton(
                "5️⃣",
                callback_data="warn_5"
            )
        )

        keyboard.add(
            types.InlineKeyboardButton(
                "🔙 برگشت",
                callback_data="panel_main"
            )
        )

    elif data == "panel_stats":
        con = connect_db()

        total = con.execute("""
        SELECT COUNT(*) c
        FROM actions
        WHERE chat_id=?
        """, (chat_id,)).fetchone()["c"]

        bans = con.execute("""
        SELECT COUNT(*) c
        FROM actions
        WHERE chat_id=?
        AND action IN ('BAN', 'AUTO_BAN')
        """, (chat_id,)).fetchone()["c"]

        warns = con.execute("""
        SELECT COUNT(*) c
        FROM actions
        WHERE chat_id=?
        AND action='WARN'
        """, (chat_id,)).fetchone()["c"]

        con.close()

        text = (
            "📊 <b>آمار گروه</b>\n\n"
            f"📋 عملیات: <b>{total}</b>\n"
            f"🔨 بن: <b>{bans}</b>\n"
            f"⚠️ اخطار: <b>{warns}</b>\n\n"
            f"🆔 <code>{chat_id}</code>"
        )

        keyboard = back_keyboard()

    elif data == "panel_settings":
        settings = get_settings(chat_id)

        text = (
            "⚙️ <b>تنظیمات</b>\n\n"
            f"⚠️ حد اخطار: "
            f"<b>{settings['warn_limit']}</b>\n"
            f"📨 Flood: "
            f"<b>{settings['flood_limit']}</b>\n"
            f"⏱ زمان Flood: "
            f"<b>{settings['flood_seconds']}s</b>\n"
            f"👋 خوشامد: "
            f"{'🟢' if settings['welcome_enabled'] else '🔴'}"
        )

        keyboard = back_keyboard()

    elif data == "panel_help":
        text = (
            "📖 <b>راهنما</b>\n\n"
            "ربات باید ادمین گروه باشد.\n\n"
            "دسترسی‌های مهم:\n"
            "✅ Delete Messages\n"
            "✅ Ban Users\n"
            "✅ Restrict Users\n\n"
            "سپس /panel را بزن."
        )

        keyboard = back_keyboard()

    else:
        return

    try:
        bot.edit_message_text(
            text,
            chat_id,
            call.message.message_id,
            reply_markup=keyboard
        )
    except Exception:
        pass

    bot.answer_callback_query(call.id)
    # =========================
# PANEL TOGGLES
# =========================

@bot.callback_query_handler(
    func=lambda call:
    call.data.startswith("toggle_")
)
def toggle_callback(call):
    chat_id = call.message.chat.id

    if not is_admin(
        chat_id,
        call.from_user.id
    ):
        bot.answer_callback_query(
            call.id,
            "⛔ فقط ادمین.",
            show_alert=True
        )
        return

    field = call.data.replace(
        "toggle_",
        ""
    )

    settings = get_settings(chat_id)

    if not settings:
        return

    current = settings[field]

    set_setting(
        chat_id,
        field,
        0 if current else 1
    )

    bot.answer_callback_query(
        call.id,
        "✅ تغییر کرد."
    )

    call.data = "panel_spam"

    panel_callback(call)


@bot.callback_query_handler(
    func=lambda call:
    call.data.startswith("warn_")
)
def warn_callback(call):
    chat_id = call.message.chat.id

    if not is_admin(
        chat_id,
        call.from_user.id
    ):
        return

    value = int(
        call.data.split("_")[1]
    )

    set_setting(
        chat_id,
        "warn_limit",
        value
    )

    bot.answer_callback_query(
        call.id,
        f"حد اخطار روی {value} قرار گرفت."
    )

    call.data = "panel_warn"

    panel_callback(call)


# =========================
# BAN
# =========================

@bot.message_handler(
    func=lambda m:
    is_group(m)
    and m.text
    and m.text.split()[0].lower()
    in ("بن", "ban")
)
def ban_command(message):
    if not is_admin(
        message.chat.id,
        message.from_user.id
    ):
        return

    target = get_target(message)

    if not target:
        bot.reply_to(
            message,
            "❌ روی پیام کاربر Reply کن."
        )
        return

    if is_admin(
        message.chat.id,
        target.id
    ):
        bot.reply_to(
            message,
            "❌ نمی‌توانی ادمین را بن کنی."
        )
        return

    if ban_user(
        message.chat.id,
        target.id
    ):
        save_action(
            message.chat.id,
            target.id,
            message.from_user.id,
            "BAN"
        )

        bot.reply_to(
            message,
            f"🔨 {mention(target)} "
            f"<b>بن شد.</b>"
        )


# =========================
# KICK
# =========================

@bot.message_handler(
    func=lambda m:
    is_group(m)
    and m.text
    and m.text.split()[0].lower()
    in ("کیک", "kick")
)
def kick_command(message):
    if not is_admin(
        message.chat.id,
        message.from_user.id
    ):
        return

    target = get_target(message)

    if not target:
        bot.reply_to(
            message,
            "❌ روی پیام کاربر Reply کن."
        )
        return

    if is_admin(
        message.chat.id,
        target.id
    ):
        return

    if kick_user(
        message.chat.id,
        target.id
    ):
        save_action(
            message.chat.id,
            target.id,
            message.from_user.id,
            "KICK"
        )

        bot.reply_to(
            message,
            f"👢 {mention(target)} "
            f"<b>کیک شد.</b>"
        )


# =========================
# MUTE
# =========================

@bot.message_handler(
    func=lambda m:
    is_group(m)
    and m.text
    and m.text.split()[0].lower()
    in ("سکوت", "mute")
)
def mute_command(message):
    if not is_admin(
        message.chat.id,
        message.from_user.id
    ):
        return

    target = get_target(message)

    if not target:
        bot.reply_to(
            message,
            "❌ روی پیام کاربر Reply کن.\n"
            "مثال: <code>سکوت 10m</code>"
        )
        return

    if is_admin(
        message.chat.id,
        target.id
    ):
        return

    seconds = duration_from_message(
        message
    )

    if mute_user(
        message.chat.id,
        target.id,
        seconds
    ):
        save_action(
            message.chat.id,
            target.id,
            message.from_user.id,
            "MUTE",
            str(seconds)
        )

        bot.reply_to(
            message,
            f"🔇 {mention(target)}\n"
            f"به مدت <b>{seconds}</b> ثانیه سکوت شد."
        )


@bot.message_handler(
    func=lambda m:
    is_group(m)
    and m.text
    and m.text.lower()
    in ("رفع سکوت", "unmute")
)
def unmute_command(message):
    if not is_admin(
        message.chat.id,
        message.from_user.id
    ):
        return

    target = get_target(message)

    if not target:
        bot.reply_to(
            message,
            "❌ روی پیام کاربر Reply کن."
        )
        return

    if unmute_user(
        message.chat.id,
        target.id
    ):
        bot.reply_to(
            message,
            f"🔊 {mention(target)} "
            f"<b>رفع سکوت شد.</b>"
        )


# =========================
# WARN
# =========================

@bot.message_handler(
    func=lambda m:
    is_group(m)
    and m.text
    and m.text.split()[0].lower()
    in ("اخطار", "warn")
)
def warn_command(message):
    if not is_admin(
        message.chat.id,
        message.from_user.id
    ):
        return

    target = get_target(message)

    if not target:
        bot.reply_to(
            message,
            "❌ روی پیام کاربر Reply کن."
        )
        return

    if is_admin(
        message.chat.id,
        target.id
    ):
        return

    count = get_warn(
        message.chat.id,
        target.id
    ) + 1

    set_warn(
        message.chat.id,
        target.id,
        count
    )

    settings = get_settings(
        message.chat.id
    )

    limit = settings["warn_limit"]

    save_action(
        message.chat.id,
        target.id,
        message.from_user.id,
        "WARN",
        str(count)
    )

    if count >= limit:
        if ban_user(
            message.chat.id,
            target.id
        ):
            reset_warn(
                message.chat.id,
                target.id
            )

            save_action(
                message.chat.id,
                target.id,
                message.from_user.id,
                "AUTO_BAN",
                "Warning limit"
            )

            bot.reply_to(
                message,
                f"🚫 {mention(target)}\n"
                f"به {limit} اخطار رسید و "
                f"<b>بن شد.</b>"
            )

            return

    bot.reply_to(
        message,
        f"⚠️ <b>اخطار</b>\n\n"
        f"👤 {mention(target)}\n"
        f"📊 {count}/{limit}"
    )


@bot.message_handler(
    func=lambda m:
    is_group(m)
    and m.text
    and m.text.lower()
    in ("رفع اخطار", "برداشتن اخطار")
)
def unwarn_command(message):
    if not is_admin(
        message.chat.id,
        message.from_user.id
    ):
        return

    target = get_target(message)

    if not target:
        bot.reply_to(
            message,
            "❌ روی پیام کاربر Reply کن."
        )
        return

    count = max(
        0,
        get_warn(
            message.chat.id,
            target.id
        ) - 1
    )

    set_warn(
        message.chat.id,
        target.id,
        count
    )

    bot.reply_to(
        message,
        f"✅ یک اخطار کم شد.\n"
        f"📊 فعلی: <b>{count}</b>"
    )


# =========================
# LOCK / UNLOCK
# =========================

@bot.message_handler(
    func=lambda m:
    is_group(m)
    and m.text
    and (
        m.text.startswith("قفل ")
        or m.text.startswith("باز ")
    )
)
def lock_command(message):
    if not is_admin(
        message.chat.id,
        message.from_user.id
    ):
        return

    parts = message.text.split()

    if len(parts) < 2:
        return

    alias = parts[1].lower()

    lock_name = LOCK_ALIASES.get(
        alias
    )

    if not lock_name:
        bot.reply_to(
            message,
            "❌ نوع قفل پیدا نشد."
        )
        return

    enabled = message.text.startswith(
        "قفل "
    )

    set_lock(
        message.chat.id,
        lock_name,
        enabled
    )

    if enabled:
        bot.reply_to(
            message,
            f"🔒 {LOCK_NAMES[lock_name]}\n"
            f"<b>قفل شد.</b>"
        )
    else:
        bot.reply_to(
            message,
            f"🔓 {LOCK_NAMES[lock_name]}\n"
            f"<b>باز شد.</b>"
        )


# =========================
# MODERATION
# =========================

def moderate(message):
    if not is_group(message):
        return

    if not message.from_user:
        return

    ensure_group(message.chat)

    if is_admin(
        message.chat.id,
        message.from_user.id
    ):
        return

    settings = get_settings(
        message.chat.id
    )

    # Flood
    if flood_check(message):
        delete_message(message)

        if mute_user(
            message.chat.id,
            message.from_user.id,
            600
        ):
            save_action(
                message.chat.id,
                message.from_user.id,
                0,
                "AUTO_MUTE",
                "Flood"
            )

        return

    # Anti link
    if (
        settings["anti_link"]
        and has_link(message)
    ):
        delete_message(message)
        return

    # Anti forward
    if (
        settings["anti_forward"]
        and is_forwarded(message)
    ):
        delete_message(message)
        return

    # Anti repeat
    if (
        settings["anti_repeat"]
        and repeat_check(message)
    ):
        delete_message(message)
        return

    media = media_type(message)

    if media:
        if get_lock(
            message.chat.id,
            media
        ):
            delete_message(message)
            return

    if (
        get_lock(
            message.chat.id,
            "link"
        )
        and has_link(message)
    ):
        delete_message(message)
        return

    if (
        get_lock(
            message.chat.id,
            "forward"
        )
        and is_forwarded(message)
    ):
        delete_message(message)
        return


@bot.message_handler(
    content_types=[
        "text",
        "photo",
        "video",
        "animation",
        "sticker",
        "voice",
        "audio",
        "document"
    ]
)
def all_messages(message):
    if is_group(message):
        moderate(message)


# =========================
# WELCOME
# =========================

@bot.message_handler(
    content_types=["new_chat_members"]
)
def welcome(message):
    if not is_group(message):
        return

    ensure_group(message.chat)

    settings = get_settings(
        message.chat.id
    )

    if not settings[
        "welcome_enabled"
    ]:
        return

    for user in message.new_chat_members:
        if user.is_bot:
            continue

        text = settings["welcome"]

        text = text.replace(
            "{name}",
            mention(user)
        )

        text = text.replace(
            "{group}",
            message.chat.title or "گروه"
        )

        try:
            bot.send_message(
                message.chat.id,
                text
            )
        except Exception as e:
            print("Welcome:", e)


# =========================
# PRIVATE BUTTONS
# =========================

@bot.callback_query_handler(
    func=lambda call:
    call.data.startswith("private_")
)
def private_buttons(call):
    if call.data == "private_features":
        text = (
            "🛡 <b>امکانات ربات</b>\n\n"
            "🔨 بن\n"
            "👢 کیک\n"
            "🔇 سکوت\n"
            "⚠️ اخطار\n"
            "🔒 قفل رسانه\n"
            "🔗 ضدلینک\n"
            "↪️ ضدفوروارد\n"
            "🤖 ضد Flood\n"
            "🔁 ضدتکرار\n"
            "👋 خوشامد\n"
            "📊 آمار\n"
            "⚙️ پنل مدیریت"
        )

    elif call.data == "private_help":
        text = (
            "📖 <b>نحوه استفاده</b>\n\n"
            "ربات را به گروه اضافه کن.\n"
            "ادمینش کن.\n"
            "دسترسی حذف پیام، Ban و Restrict "
            "را بده.\n\n"
            "سپس داخل گروه:\n"
            "<code>/panel</code>"
        )

    else:
        return

    keyboard = types.InlineKeyboardMarkup()

    keyboard.add(
        types.InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="private_back"
        )
    )

    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
    except Exception:
        pass

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(
    func=lambda call:
    call.data == "private_back"
)
def private_back(call):
    keyboard = types.InlineKeyboardMarkup(
        row_width=2
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🛡 امکانات",
            callback_data="private_features"
        ),
        types.InlineKeyboardButton(
            "📖 راهنما",
            callback_data="private_help"
        )
    )

    try:
        bot.edit_message_text(
            "🤖 <b>GROUP MANAGER</b>\n\n"
            "به منوی اصلی برگشتی.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
    except Exception:
        pass

    bot.answer_callback_query(call.id)


# =========================
# MUTE WORKER
# =========================

def mute_worker():
    while True:
        now = int(time.time())

        expired = []

        for key, until in list(
            mute_data.items()
        ):
            if now >= until:
                expired.append(key)

        for chat_id, user_id in expired:
            try:
                unmute_user(
                    chat_id,
                    user_id
                )
            except Exception as e:
                print("Mute worker:", e)

        time.sleep(5)


threading.Thread(
    target=mute_worker,
    daemon=True
).start()


# =========================
# START BOT
# =========================

print("================================")
print("🤖 GROUP MANAGER")
print("🟢 BOT STARTED")
print("💾 DATABASE READY")
print("================================")

bot.infinity_polling(
    skip_pending=True,
    timeout=60,
    long_polling_timeout=60
        )
