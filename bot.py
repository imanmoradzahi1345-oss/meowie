import telebot
from telebot import types
import sqlite3
import time
import re
import threading
from collections import defaultdict, deque

BOT_TOKEN = "8636563885:AAH-Ihpb7-Ql9MwD1lZ824rwu1sdb3uUH8o"

bot = telebot.TeleBot(
    BOT_TOKEN,
    parse_mode="HTML",
    threaded=True,
    num_threads=20
)

DB_NAME = "group_manager.db"
DB_LOCK = threading.Lock()

flood_data = defaultdict(lambda: defaultdict(deque))
repeat_data = {}
mute_data = {}
mute_lock = threading.Lock()

LOCK_NAMES = {
    "link": "🔗 لینک",
    "photo": "🖼 عکس",
    "video": "🎬 فیلم",
    "animation": "🎞 گیف",
    "sticker": "🎭 استیکر",
    "voice": "🎤 ویس",
    "audio": "🎵 آهنگ",
    "document": "📄 فایل",
    "forward": "↪️ فوروارد",
    "all_media": "📦 همه رسانه‌ها"
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
    "فوروارد": "forward",
    "رسانه": "all_media"
}

LINK_RE = re.compile(
    r"(https?://|www\.|t\.me/|telegram\.me/)",
    re.IGNORECASE
)


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
                badword_filter INTEGER DEFAULT 0,
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
        "badword_filter",
        "welcome_enabled",
        "welcome"
    }

    if field not in allowed:
        return

    with DB_LOCK:
        con = connect_db()

        con.execute(
            f"UPDATE groups SET {field}=? WHERE chat_id=?",
            (value, chat_id)
        )

        con.commit()
        con.close()


def get_lock(chat_id, name):
    con = connect_db()

    row = con.execute("""
        SELECT enabled
        FROM locks
        WHERE chat_id=? AND lock_name=?
    """, (
        chat_id,
        name
    )).fetchone()

    con.close()

    return bool(row["enabled"]) if row else False


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


init_db()
def delete_msg(message):
    try:
        bot.delete_message(
            message.chat.id,
            message.message_id
        )
        return True
    except Exception as e:
        print("DELETE:", e)
        return False


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


def get_warn(chat_id, user_id):
    con = connect_db()

    row = con.execute("""
        SELECT count
        FROM warnings
        WHERE chat_id=? AND user_id=?
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
            WHERE chat_id=? AND user_id=?
        """, (
            chat_id,
            user_id
        ))

        con.commit()
        con.close()


def get_target(message):
    if message.reply_to_message:
        return message.reply_to_message.from_user

    parts = (message.text or "").split()

    if len(parts) >= 2:
        value = parts[1]

        if value.lstrip("-").isdigit():
            try:
                member = bot.get_chat_member(
                    message.chat.id,
                    int(value)
                )
                return member.user
            except Exception:
                return None

    return None


def duration_from_message(message):
    parts = (message.text or "").split()

    if len(parts) < 2:
        return 600

    match = re.match(
        r"^(\d+)(s|m|h|d)?$",
        parts[1].lower()
    )

    if not match:
        return 600

    number = int(match.group(1))
    unit = match.group(2) or "m"

    multiplier = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400
    }

    return min(
        number * multiplier[unit],
        30 * 86400
    )


def get_media_type(message):
    return {
        "photo": "photo",
        "video": "video",
        "animation": "animation",
        "sticker": "sticker",
        "voice": "voice",
        "audio": "audio",
        "document": "document"
    }.get(message.content_type)


def is_forwarded(message):
    if getattr(message, "forward_origin", None):
        return True

    if getattr(message, "forward_from", None):
        return True

    if getattr(message, "forward_from_chat", None):
        return True

    return False


def has_link(message):
    text = (
        message.text
        or message.caption
        or ""
    )

    return bool(
        LINK_RE.search(text)
    )


def flood_check(message):
    settings = get_settings(
        message.chat.id
    )

    if not settings:
        return False

    chat_id = message.chat.id
    user_id = message.from_user.id
    now = time.time()

    queue = flood_data[
        chat_id
    ][user_id]

    queue.append(now)

    while queue and (
        now - queue[0]
        > settings["flood_seconds"]
    ):
        queue.popleft()

    return len(queue) > settings["flood_limit"]


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
    def restrict_user(chat_id, user_id, seconds=600):
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

        return True

    except Exception as e:
        print("RESTRICT:", e)
        return False


def unrestrict_user(chat_id, user_id):
    try:
        bot.restrict_chat_member(
            chat_id,
            user_id,
            permissions=types.ChatPermissions(
                can_send_messages=True
            )
        )

        return True

    except Exception as e:
        print("UNRESTRICT:", e)
        return False


def ban_user(chat_id, user_id):
    try:
        bot.ban_chat_member(
            chat_id,
            user_id
        )
        return True

    except Exception as e:
        print("BAN:", e)
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
        print("KICK:", e)
        return False


@bot.message_handler(commands=["start"])
def start(message):
    if message.chat.type != "private":
        return

    kb = types.InlineKeyboardMarkup(
        row_width=2
    )

    kb.add(
        types.InlineKeyboardButton(
            "🛡 امکانات",
            callback_data="p_features"
        ),
        types.InlineKeyboardButton(
            "📖 راهنما",
            callback_data="p_help"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "⚙️ وضعیت",
            callback_data="p_status"
        )
    )

    bot.send_message(
        message.chat.id,
        "🤖 <b>GROUP MANAGER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🛡 ربات حرفه‌ای مدیریت گروه\n\n"
        "ربات را به گروه اضافه کن و "
        "ادمینش کن.\n\n"
        "بعد داخل گروه بزن:\n"
        "<code>/panel</code>",
        reply_markup=kb
    )


@bot.message_handler(commands=["help"])
def help_command(message):
    bot.send_message(
        message.chat.id,
        "📖 <b>راهنمای ربات</b>\n\n"
        "⚙️ /panel — پنل مدیریت\n\n"
        "👤 مدیریت:\n"
        "• بن\n"
        "• کیک\n"
        "• سکوت 10m\n"
        "• رفع سکوت\n"
        "• اخطار\n"
        "• رفع اخطار\n\n"
        "🔒 قفل:\n"
        "قفل لینک\n"
        "قفل عکس\n"
        "قفل فیلم\n"
        "قفل گیف\n"
        "قفل استیکر\n"
        "قفل ویس\n"
        "قفل فایل\n"
        "قفل فوروارد\n\n"
        "مثال:\n"
        "<code>قفل لینک</code>\n"
        "<code>باز لینک</code>"
    )


@bot.message_handler(commands=["panel"])
def panel_command(message):
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


def main_panel():
    kb = types.InlineKeyboardMarkup(
        row_width=2
    )

    kb.add(
        types.InlineKeyboardButton(
            "🛡 مدیریت کاربران",
            callback_data="panel_users"
        ),
        types.InlineKeyboardButton(
            "🔒 قفل‌ها",
            callback_data="panel_locks"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "🤖 ضداسپم",
            callback_data="panel_spam"
        ),
        types.InlineKeyboardButton(
            "⚠️ اخطار",
            callback_data="panel_warn"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "📊 آمار",
            callback_data="panel_stats"
        ),
        types.InlineKeyboardButton(
            "⚙️ تنظیمات",
            callback_data="panel_settings"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "📖 راهنما",
            callback_data="panel_help"
        )
    )

    return kb
    @bot.callback_query_handler(
    func=lambda c: c.data.startswith("panel_")
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

    section = call.data

    if section == "panel_main":
        text = (
            "⚙️ <b>پنل مدیریت گروه</b>\n\n"
            "یک بخش را انتخاب کن:"
        )
        keyboard = main_panel()

    elif section == "panel_users":
        text = (
            "🛡 <b>مدیریت کاربران</b>\n\n"
            "دستورات روی پیام کاربر:\n\n"
            "🔨 بن\n"
            "👢 کیک\n"
            "🔇 سکوت 10m\n"
            "🔊 رفع سکوت\n"
            "⚠️ اخطار\n"
            "➖ رفع اخطار"
        )
        keyboard = back_button()

    elif section == "panel_locks":
        lines = ["🔒 <b>وضعیت قفل‌ها</b>\n"]

        for key, title in LOCK_NAMES.items():
            status = (
                "🔴 فعال"
                if get_lock(chat_id, key)
                else "🟢 خاموش"
            )
            lines.append(
                f"{status} — {title}"
            )

        lines.append(
            "\nبرای تغییر:\n"
            "<code>قفل لینک</code>\n"
            "<code>باز لینک</code>"
        )

        text = "\n".join(lines)
        keyboard = back_button()

    elif section == "panel_spam":
        settings = get_settings(chat_id)

        text = (
            "🤖 <b>ضداسپم</b>\n\n"
            f"📨 حد Flood: "
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

    elif section == "panel_warn":
        settings = get_settings(chat_id)

        text = (
            "⚠️ <b>سیستم اخطار</b>\n\n"
            f"حد اخطار فعلی: "
            f"<b>{settings['warn_limit']}</b>\n\n"
            "وقتی کاربر به این تعداد اخطار "
            "برسد، بن می‌شود."
        )

        keyboard = types.InlineKeyboardMarkup()

        keyboard.add(
            types.InlineKeyboardButton(
                "3️⃣ حد = 3",
                callback_data="warn_3"
            ),
            types.InlineKeyboardButton(
                "5️⃣ حد = 5",
                callback_data="warn_5"
            )
        )

        keyboard.add(
            types.InlineKeyboardButton(
                "🔙 برگشت",
                callback_data="panel_main"
            )
        )

    elif section == "panel_stats":
        con = connect_db()

        actions = con.execute("""
            SELECT COUNT(*) AS c
            FROM actions
            WHERE chat_id=?
        """, (chat_id,)).fetchone()["c"]

        bans = con.execute("""
            SELECT COUNT(*) AS c
            FROM actions
            WHERE chat_id=?
            AND action IN ('BAN','AUTO_BAN')
        """, (chat_id,)).fetchone()["c"]

        warns = con.execute("""
            SELECT COUNT(*) AS c
            FROM actions
            WHERE chat_id=?
            AND action='WARN'
        """, (chat_id,)).fetchone()["c"]

        con.close()

        text = (
            "📊 <b>آمار گروه</b>\n\n"
            f"📋 عملیات: <b>{actions}</b>\n"
            f"🔨 بن: <b>{bans}</b>\n"
            f"⚠️ اخطار: <b>{warns}</b>\n\n"
            f"🆔 <code>{chat_id}</code>"
        )

        keyboard = back_button()

    elif section == "panel_settings":
        settings = get_settings(chat_id)

        text = (
            "⚙️ <b>تنظیمات گروه</b>\n\n"
            f"⚠️ حد اخطار: "
            f"<b>{settings['warn_limit']}</b>\n"
            f"📨 Flood: "
            f"<b>{settings['flood_limit']}</b>\n"
            f"⏱ زمان Flood: "
            f"<b>{settings['flood_seconds']}s</b>\n"
            f"👋 خوشامد: "
            f"{'🟢' if settings['welcome_enabled'] else '🔴'}"
        )

        keyboard = back_button()

    elif section == "panel_help":
        text = (
            "📖 <b>راهنمای سریع</b>\n\n"
            "1️⃣ ربات را ادمین کن.\n"
            "2️⃣ دسترسی حذف پیام بده.\n"
            "3️⃣ دسترسی Ban و Restrict بده.\n"
            "4️⃣ برای مدیریت /panel را بزن.\n\n"
            "💡 بیشتر دستورات روی پیام کاربر "
            "با Reply اجرا می‌شوند."
        )

        keyboard = back_button()

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


def back_button():
    kb = types.InlineKeyboardMarkup()

    kb.add(
        types.InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="panel_main"
        )
    )

    return kb
    @bot.callback_query_handler(
    func=lambda c: c.data.startswith("toggle_")
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

    new_value = 0 if settings[field] else 1

    set_setting(
        chat_id,
        field,
        new_value
    )

    bot.answer_callback_query(
        call.id,
        "✅ تغییر کرد."
    )

    call.data = "panel_spam"
    panel_callback(call)


@bot.callback_query_handler(
    func=lambda c: c.data.startswith("warn_")
)
def warn_limit_callback(call):
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
        f"حد اخطار {value} شد."
    )

    call.data = "panel_warn"
    panel_callback(call)


@bot.message_handler(
    func=lambda m:
    is_group(m)
    and m.text
    and m.text.split()[0].lower()
    in ("بن", "ban")
)
def command_ban(message):
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
            "❌ ادمین قابل بن نیست."
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
            f"🔨 {mention(target)} <b>بن شد.</b>"
        )


@bot.message_handler(
    func=lambda m:
    is_group(m)
    and m.text
    and m.text.split()[0].lower()
    in ("کیک", "kick")
)
def command_kick(message):
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
            f"👢 {mention(target)} <b>کیک شد.</b>"
        )


@bot.message_handler(
    func=lambda m:
    is_group(m)
    and m.text
    and m.text.split()[0].lower()
    in ("سکوت", "mute")
)
def command_mute(message):
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

    if restrict_user(
        message.chat.id,
        target.id,
        seconds
    ):
        with mute_lock:
            mute_data[
                (message.chat.id, target.id)
            ] = time.time() + seconds

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
            f"برای <b>{seconds}</b> ثانیه سکوت شد."
        )


@bot.message_handler(
    func=lambda m:
    is_group(m)
    and m.text
    and m.text.lower()
    in ("رفع سکوت", "unmute")
)
def command_unmute(message):
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

    if unrestrict_user(
        message.chat.id,
        target.id
    ):
        with mute_lock:
            mute_data.pop(
                (message.chat.id, target.id),
                None
            )

        bot.reply_to(
            message,
            f"🔊 {mention(target)} "
            f"<b>رفع سکوت شد.</b>"
        )


@bot.message_handler(
    func=lambda m:
    is_group(m)
    and m.text
    and m.text.split()[0].lower()
    in ("اخطار", "warn")
)
def command_warn(message):
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

            bot.reply_to(
                message,
                f"🚫 {mention(target)}\n"
                f"به <b>{limit}</b> اخطار رسید و بن شد."
            )
            return

    bot.reply_to(
        message,
        f"⚠️ <b>اخطار</b>\n"
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
def command_unwarn(message):
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
        f"✅ اخطار برداشته شد.\n"
        f"📊 اخطار فعلی: <b>{count}</b>"
    )
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
    lock_name = LOCK_ALIASES.get(alias)

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
        text = (
            "🔒 <b>قفل فعال شد</b>\n\n"
            f"{LOCK_NAMES[lock_name]}"
        )
    else:
        text = (
            "🔓 <b>قفل غیرفعال شد</b>\n\n"
            f"{LOCK_NAMES[lock_name]}"
        )

    bot.reply_to(
        message,
        text
    )


def moderate(message):
    if not is_group(message):
        return

    ensure_group(message.chat)

    if not message.from_user:
        return

    if is_admin(
        message.chat.id,
        message.from_user.id
    ):
        return

    settings = get_settings(
        message.chat.id
    )

    if flood_check(message):
        delete_msg(message)

        if restrict_user(
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

    text = (
        message.text
        or message.caption
        or ""
    )

    if (
        settings["anti_link"]
        and has_link(message)
    ):
        delete_msg(message)
        return

    if (
        settings["anti_forward"]
        and is_forwarded(message)
    ):
        delete_msg(message)
        return

    if (
        settings["anti_repeat"]
        and repeat_check(message)
    ):
        delete_msg(message)
        return

    media = get_media_type(message)

    if media:
        if get_lock(
            message.chat.id,
            media
        ):
            delete_msg(message)
            return

        if get_lock(
            message.chat.id,
            "all_media"
        ):
            delete_msg(message)
            return

    if (
        get_lock(
            message.chat.id,
            "link"
        )
        and has_link(message)
    ):
        delete_msg(message)
        return

    if (
        get_lock(
            message.chat.id,
            "forward"
        )
        and is_forwarded(message)
    ):
        delete_msg(message)
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
def message_handler(message):
    if is_group(message):
        moderate(message)


@bot.message_handler(
    content_types=["new_chat_members"]
)
def welcome_handler(message):
    if not is_group(message):
        return

    ensure_group(message.chat)

    settings = get_settings(
        message.chat.id
    )

    if not settings["welcome_enabled"]:
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
            print("WELCOME:", e)


@bot.message_handler(
    content_types=["left_chat_member"]
)
def left_handler(message):
    try:
        bot.delete_message(
            message.chat.id,
            message.message_id
        )
    except Exception:
        pass


@bot.callback_query_handler(
    func=lambda c:
    c.data.startswith("p_")
)
def private_callback(call):
    if call.data == "p_features":
        text = (
            "🛡 <b>امکانات</b>\n\n"
            "🔨 بن\n"
            "👢 کیک\n"
            "🔇 سکوت موقت\n"
            "⚠️ سیستم اخطار\n"
            "🔒 قفل رسانه‌ها\n"
            "🔗 ضدلینک\n"
            "↪️ ضدفوروارد\n"
            "🔁 ضدتکرار\n"
            "🤖 ضد Flood\n"
            "👋 خوشامدگویی\n"
            "📊 آمار\n"
            "⚙️ پنل شیشه‌ای"
        )

    elif call.data == "p_help":
        text = (
            "📖 <b>راهنما</b>\n\n"
            "بات را به گروه اضافه کن.\n"
            "ادمینش کن.\n"
            "دسترسی حذف پیام، Ban و Restrict "
            "را بده.\n\n"
            "سپس داخل گروه:\n"
            "<code>/panel</code>"
        )

    else:
        text = (
            "🟢 <b>ربات آنلاین است</b>\n\n"
            "⚡ سیستم مدیریت آماده است."
        )

    kb = types.InlineKeyboardMarkup()

    kb.add(
        types.InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="p_back"
        )
    )

    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb
        )
    except Exception:
        pass

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(
    func=lambda c: c.data == "p_back"
)
def private_back(call):
    kb = types.InlineKeyboardMarkup(
        row_width=2
    )

    kb.add(
        types.InlineKeyboardButton(
            "🛡 امکانات",
            callback_data="p_features"
        ),
        types.InlineKeyboardButton(
            "📖 راهنما",
            callback_data="p_help"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "⚙️ وضعیت",
            callback_data="p_status"
        )
    )

    try:
        bot.edit_message_text(
            "🤖 <b>GROUP MANAGER</b>\n\n"
            "به پنل اصلی خوش آمدی.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb
        )
    except Exception:
        pass

    bot.answer_callback_query(call.id)


def mute_worker():
    while True:
        now = time.time()
        expired = []

        with mute_lock:
            for key, until in list(
                mute_data.items()
            ):
                if now >= until:
                    expired.append(key)

        for chat_id, user_id in expired:
            unrestrict_user(
                chat_id,
                user_id
            )

            with mute_lock:
                mute_data.pop(
                    (chat_id, user_id),
                    None
                )

        time.sleep(5)


threading.Thread(
    target=mute_worker,
    daemon=True
).start()

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
