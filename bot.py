import telebot
from telebot import types
from telebot.types import ChatPermissions
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

db_lock = threading.Lock()
flood_data = defaultdict(lambda: defaultdict(deque))
last_messages = defaultdict(dict)
temporary_actions = {}
temporary_lock = threading.Lock()

LOCK_TYPES = {
    "link": "🔗 لینک",
    "photo": "🖼 عکس",
    "video": "🎬 فیلم",
    "animation": "🎞 GIF",
    "sticker": "🎭 استیکر",
    "voice": "🎤 ویس",
    "audio": "🎵 آهنگ",
    "document": "📄 فایل",
    "forward": "↪️ فوروارد",
    "all_media": "📦 رسانه"
}

LOCK_ALIASES = {
    "لینک": "link",
    "عکس": "photo",
    "فیلم": "video",
    "ویدیو": "video",
    "گیف": "animation",
    "استیکر": "sticker",
    "ویس": "voice",
    "صوت": "voice",
    "آهنگ": "audio",
    "فایل": "document",
    "فوروارد": "forward",
    "رسانه": "all_media"
}

BAD_WORDS = {
    "spamword",
    "badword"
}

LINK_PATTERN = re.compile(
    r"(https?://|www\.|t\.me/|telegram\.me/)",
    re.IGNORECASE
)


def db():
    con = sqlite3.connect(
        DB_NAME,
        timeout=30,
        check_same_thread=False
    )
    con.row_factory = sqlite3.Row
    return con


def init_db():

    with db_lock:

        con = db()

        con.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                chat_id INTEGER PRIMARY KEY,
                title TEXT,
                welcome TEXT DEFAULT '',
                warn_limit INTEGER DEFAULT 3,
                flood_limit INTEGER DEFAULT 6,
                flood_seconds INTEGER DEFAULT 5,
                anti_link INTEGER DEFAULT 0,
                anti_forward INTEGER DEFAULT 0,
                anti_repeat INTEGER DEFAULT 0,
                badword_filter INTEGER DEFAULT 0,
                welcome_enabled INTEGER DEFAULT 1,
                log_chat_id INTEGER DEFAULT 0,
                created_at INTEGER
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


init_db()


def ensure_group(chat):

    if chat.type not in ("group", "supergroup"):
        return

    with db_lock:

        con = db()

        con.execute("""
            INSERT OR IGNORE INTO groups
            (chat_id, title, created_at)
            VALUES (?, ?, ?)
        """, (
            chat.id,
            chat.title or "Group",
            int(time.time())
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

    con = db()

    row = con.execute("""
        SELECT *
        FROM groups
        WHERE chat_id=?
    """, (chat_id,)).fetchone()

    con.close()

    return row


def set_setting(chat_id, column, value):

    allowed = {
        "warn_limit",
        "flood_limit",
        "flood_seconds",
        "anti_link",
        "anti_forward",
        "anti_repeat",
        "badword_filter",
        "welcome_enabled",
        "log_chat_id",
        "welcome"
    }

    if column not in allowed:
        return

    with db_lock:

        con = db()

        con.execute(
            f"""
            UPDATE groups
            SET {column}=?
            WHERE chat_id=?
            """,
            (value, chat_id)
        )

        con.commit()
        con.close()


def get_lock(chat_id, name):

    con = db()

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

    with db_lock:

        con = db()

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


def is_admin_user(chat_id, user_id):

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


def admin_only(message):

    return (
        is_group(message)
        and
        is_admin_user(
            message.chat.id,
            message.from_user.id
        )
    )


def protected_user(chat_id, user_id):

    return is_admin_user(
        chat_id,
        user_id
    )


def user_mention(user):

    name = user.first_name or "User"

    return (
        f'<a href="tg://user?id={user.id}">'
        f'{name}</a>'
    )


def save_action(
    chat_id,
    user_id,
    admin_id,
    action,
    reason=""
):

    with db_lock:

        con = db()

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
        def send_log(chat_id, text):

    settings = get_settings(chat_id)

    if not settings:
        return

    log_chat_id = settings["log_chat_id"]

    if not log_chat_id:
        return

    try:
        bot.send_message(
            log_chat_id,
            text
        )
    except Exception as e:
        print("LOG ERROR:", e)


def get_warns(chat_id, user_id):

    con = db()

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


def add_warn(chat_id, user_id):

    new_count = get_warns(
        chat_id,
        user_id
    ) + 1

    with db_lock:

        con = db()

        con.execute("""
            INSERT INTO warnings
            (chat_id, user_id, count)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id, user_id)
            DO UPDATE SET count=excluded.count
        """, (
            chat_id,
            user_id,
            new_count
        ))

        con.commit()
        con.close()

    return new_count


def remove_warn(chat_id, user_id):

    new_count = max(
        0,
        get_warns(
            chat_id,
            user_id
        ) - 1
    )

    with db_lock:

        con = db()

        con.execute("""
            INSERT INTO warnings
            (chat_id, user_id, count)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id, user_id)
            DO UPDATE SET count=excluded.count
        """, (
            chat_id,
            user_id,
            new_count
        ))

        con.commit()
        con.close()

    return new_count


def reset_warns(chat_id, user_id):

    with db_lock:

        con = db()

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

    parts = message.text.split()

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
                pass

    return None


def parse_duration(text):

    parts = text.split()

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


@bot.message_handler(commands=["panel", "پنل"])
def panel_command(message):

    if not is_group(message):
        return

    ensure_group(message.chat)

    if not admin_only(message):
        return

    bot.send_message(
        message.chat.id,
        "⚙️ <b>پنل مدیریت گروه</b>\n\n"
        "بخش موردنظر را انتخاب کنید:",
        reply_markup=admin_panel()
    )


@bot.message_handler(commands=["help"])
def group_help(message):

    if not is_group(message):
        return

    bot.send_message(
        message.chat.id,
        "📖 <b>راهنمای ربات</b>\n\n"
        "⚙️ /panel — پنل مدیریت\n\n"
        "👤 مدیریت کاربران:\n"
        "• بن\n"
        "• کیک\n"
        "• سکوت 10m\n"
        "• رفع سکوت\n"
        "• اخطار\n"
        "• برداشتن اخطار\n\n"
        "🔒 قفل‌ها:\n"
        "قفل لینک\n"
        "قفل عکس\n"
        "قفل فیلم\n"
        "قفل گیف\n"
        "قفل استیکر\n"
        "قفل ویس\n"
        "قفل فایل\n"
        "قفل فوروارد"
    )


@bot.message_handler(
    func=lambda m:
    is_group(m)
    and m.text
    and m.text.split()[0].lower()
    in ("بن", "ban")
)
def ban_user(message):

    if not admin_only(message):
        return

    target = get_target(message)

    if not target:
        bot.reply_to(
            message,
            "❌ روی پیام کاربر ریپلای کن."
        )
        return

    if protected_user(
        message.chat.id,
        target.id
    ):
        bot.reply_to(
            message,
            "❌ نمی‌توانی ادمین را بن کنی."
        )
        return

    try:

        bot.ban_chat_member(
            message.chat.id,
            target.id
        )

        save_action(
            message.chat.id,
            target.id,
            message.from_user.id,
            "BAN"
        )

        send_log(
            message.chat.id,
            f"🔨 <b>BAN</b>\n"
            f"👤 {user_mention(target)}\n"
            f"👮 {user_mention(message.from_user)}"
        )

        bot.reply_to(
            message,
            f"🔨 {user_mention(target)} <b>بن شد.</b>"
        )

    except Exception as e:

        bot.reply_to(
            message,
            "❌ خطا در بن کردن."
        )

        print(e)


@bot.message_handler(
    func=lambda m:
    is_group(m)
    and m.text
    and m.text.split()[0].lower()
    in ("کیک", "kick")
)
def kick_user(message):

    if not admin_only(message):
        return

    target = get_target(message)

    if not target:
        bot.reply_to(
            message,
            "❌ روی پیام کاربر ریپلای کن."
        )
        return

    if protected_user(
        message.chat.id,
        target.id
    ):
        bot.reply_to(
            message,
            "❌ ادمین قابل کیک نیست."
        )
        return

    try:

        bot.ban_chat_member(
            message.chat.id,
            target.id
        )

        bot.unban_chat_member(
            message.chat.id,
            target.id,
            only_if_banned=True
        )

        save_action(
            message.chat.id,
            target.id,
            message.from_user.id,
            "KICK"
        )

        bot.reply_to(
            message,
            f"👢 {user_mention(target)} <b>کیک شد.</b>"
        )

    except Exception as e:

        bot.reply_to(
            message,
            "❌ خطا در کیک."
        )

        print(e)


@bot.message_handler(
    func=lambda m:
    is_group(m)
    and m.text
    and m.text.split()[0].lower()
    in ("سکوت", "mute", "میت")
)
def mute_user(message):

    if not admin_only(message):
        return

    target = get_target(message)

    if not target:
        bot.reply_to(
            message,
            "❌ روی پیام کاربر ریپلای کن.\n"
            "مثال: <code>سکوت 10m</code>"
        )
        return

    if protected_user(
        message.chat.id,
        target.id
    ):
        bot.reply_to(
            message,
            "❌ ادمین قابل میوت نیست."
        )
        return

    seconds = parse_duration(
        message.text
    )

    until = int(
        time.time() + seconds
    )

    try:

        bot.restrict_chat_member(
            message.chat.id,
            target.id,
            permissions=ChatPermissions(
                can_send_messages=False
            ),
            until_date=until
        )

        with temporary_lock:

            temporary_actions[
                (message.chat.id, target.id)
            ] = until

        save_action(
            message.chat.id,
            target.id,
            message.from_user.id,
            "MUTE",
            str(seconds)
        )

        bot.reply_to(
            message,
            f"🔇 {user_mention(target)}\n"
            f"برای <b>{seconds}</b> ثانیه میوت شد."
        )

    except Exception as e:

        bot.reply_to(
            message,
            "❌ خطا در میوت."
        )

        print(e)
@bot.message_handler(
    func=lambda m:
    is_group(m)
    and m.text
    and m.text.lower()
    in ("رفع سکوت", "unmute")
)
def unmute_user(message):

    if not admin_only(message):
        return

    target = get_target(message)

    if not target:
        bot.reply_to(
            message,
            "❌ روی پیام کاربر ریپلای کن."
        )
        return

    permissions = ChatPermissions(
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

    try:

        bot.restrict_chat_member(
            message.chat.id,
            target.id,
            permissions=permissions
        )

        with temporary_lock:

            temporary_actions.pop(
                (message.chat.id, target.id),
                None
            )

        bot.reply_to(
            message,
            f"🔊 {user_mention(target)} "
            f"<b>رفع سکوت شد.</b>"
        )

    except Exception as e:

        bot.reply_to(
            message,
            "❌ خطا در رفع سکوت."
        )

        print(e)


@bot.message_handler(
    func=lambda m:
    is_group(m)
    and m.text
    and m.text.split()[0].lower()
    in ("اخطار", "warn")
)
def warn_user(message):

    if not admin_only(message):
        return

    target = get_target(message)

    if not target:
        bot.reply_to(
            message,
            "❌ روی پیام کاربر ریپلای کن."
        )
        return

    if protected_user(
        message.chat.id,
        target.id
    ):
        bot.reply_to(
            message,
            "❌ نمی‌توانی به ادمین اخطار بدهی."
        )
        return

    count = add_warn(
        message.chat.id,
        target.id
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

        try:

            bot.ban_chat_member(
                message.chat.id,
                target.id
            )

            reset_warns(
                message.chat.id,
                target.id
            )

            bot.reply_to(
                message,
                f"🚫 {user_mention(target)}\n"
                f"به حد اخطار رسید و <b>بن شد.</b>"
            )

        except Exception:

            bot.reply_to(
                message,
                "⚠️ اخطار ثبت شد ولی بن خودکار نشد."
            )

        return

    bot.reply_to(
        message,
        f"⚠️ <b>اخطار ثبت شد</b>\n\n"
        f"👤 {user_mention(target)}\n"
        f"📊 {count}/{limit}"
    )


@bot.message_handler(
    func=lambda m:
    is_group(m)
    and m.text
    and m.text.lower()
    in ("برداشتن اخطار", "رفع اخطار", "unwarn")
)
def unwarn_user(message):

    if not admin_only(message):
        return

    target = get_target(message)

    if not target:
        bot.reply_to(
            message,
            "❌ روی پیام کاربر ریپلای کن."
        )
        return

    count = remove_warn(
        message.chat.id,
        target.id
    )

    bot.reply_to(
        message,
        f"✅ یک اخطار برداشته شد.\n"
        f"📊 فعلی: <b>{count}</b>"
    )


@bot.message_handler(
    func=lambda m:
    is_group(m)
    and m.text
    and m.text.lower()
    in ("حذف اخطارها", "resetwarn")
)
def reset_warning_user(message):

    if not admin_only(message):
        return

    target = get_target(message)

    if not target:
        bot.reply_to(
            message,
            "❌ روی پیام کاربر ریپلای کن."
        )
        return

    reset_warns(
        message.chat.id,
        target.id
    )

    bot.reply_to(
        message,
        "🧹 تمام اخطارهای کاربر پاک شد."
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

    if not admin_only(message):
        return

    parts = message.text.split()

    if len(parts) < 2:
        return

    name = parts[1].strip().lower()

    lock_name = LOCK_ALIASES.get(name)

    if not lock_name:

        bot.reply_to(
            message,
            "❌ نوع قفل شناخته نشد."
        )
        return

    enabled = (
        message.text.startswith("قفل ")
    )

    set_lock(
        message.chat.id,
        lock_name,
        enabled
    )

    bot.reply_to(
        message,
        (
            "🔒 قفل فعال شد\n"
            if enabled
            else
            "🔓 قفل غیرفعال شد\n"
        )
        + LOCK_TYPES[lock_name]
    )


def has_link(text):

    if not text:
        return False

    return bool(
        LINK_PATTERN.search(text)
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


def message_lock_type(message):

    types_map = {
        "photo": "photo",
        "video": "video",
        "animation": "animation",
        "sticker": "sticker",
        "voice": "voice",
        "audio": "audio",
        "document": "document"
    }

    return types_map.get(
        message.content_type
    )


def contains_badword(text):

    if not text:
        return False

    low = text.lower()

    return any(
        word in low
        for word in BAD_WORDS
    )


def delete_message(message):

    try:

        bot.delete_message(
            message.chat.id,
            message.message_id
        )

        return True

    except Exception as e:

        print(
            "DELETE ERROR:",
            e
        )

        return False
        def check_flood(message):

    settings = get_settings(
        message.chat.id
    )

    if not settings:
        return False

    user_id = message.from_user.id
    now = time.time()

    queue = flood_data[
        message.chat.id
    ][user_id]

    queue.append(now)

    limit = settings["flood_limit"]
    seconds = settings["flood_seconds"]

    while queue and (
        now - queue[0] > seconds
    ):
        queue.popleft()

    return len(queue) > limit


def check_repeat(message):

    text = (
        message.text
        or message.caption
        or ""
    )

    if not text:
        return False

    chat_id = message.chat.id
    user_id = message.from_user.id

    previous = last_messages[
        chat_id
    ].get(user_id)

    last_messages[
        chat_id
    ][user_id] = text

    return (
        previous is not None
        and previous == text
    )


def auto_mute(message, reason):

    user = message.from_user

    if protected_user(
        message.chat.id,
        user.id
    ):
        return

    try:

        until = int(
            time.time() + 600
        )

        bot.restrict_chat_member(
            message.chat.id,
            user.id,
            permissions=ChatPermissions(
                can_send_messages=False
            ),
            until_date=until
        )

        save_action(
            message.chat.id,
            user.id,
            0,
            "AUTO_MUTE",
            reason
        )

        send_log(
            message.chat.id,
            f"🤖 <b>AUTO MUTE</b>\n"
            f"👤 {user_mention(user)}\n"
            f"📌 {reason}"
        )

    except Exception as e:

        print(
            "AUTO MUTE ERROR:",
            e
        )


def auto_ban(message, reason):

    user = message.from_user

    if protected_user(
        message.chat.id,
        user.id
    ):
        return

    try:

        bot.ban_chat_member(
            message.chat.id,
            user.id
        )

        save_action(
            message.chat.id,
            user.id,
            0,
            "AUTO_BAN",
            reason
        )

        send_log(
            message.chat.id,
            f"🤖 <b>AUTO BAN</b>\n"
            f"👤 {user_mention(user)}\n"
            f"📌 {reason}"
        )

    except Exception as e:

        print(
            "AUTO BAN ERROR:",
            e
        )


def moderate_message(message):

    if not is_group(message):
        return

    ensure_group(message.chat)

    user = message.from_user

    if not user:
        return

    if protected_user(
        message.chat.id,
        user.id
    ):
        return

    settings = get_settings(
        message.chat.id
    )

    if check_flood(message):

        delete_message(message)

        auto_mute(
            message,
            "Flood / Spam"
        )

        return

    if settings["anti_repeat"]:

        if check_repeat(message):

            delete_message(message)
            return

    text = (
        message.text
        or message.caption
        or ""
    )

    if (
        settings["anti_link"]
        and has_link(text)
    ):

        delete_message(message)
        return

    if (
        settings["anti_forward"]
        and is_forwarded(message)
    ):

        delete_message(message)
        return

    if (
        settings["badword_filter"]
        and contains_badword(text)
    ):

        delete_message(message)

        auto_mute(
            message,
            "Bad Word Filter"
        )

        return

    media_type = message_lock_type(
        message
    )

    if media_type:

        if get_lock(
            message.chat.id,
            media_type
        ):

            delete_message(message)
            return

        if get_lock(
            message.chat.id,
            "all_media"
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

    if (
        get_lock(
            message.chat.id,
            "link"
        )
        and has_link(text)
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
        moderate_message(message)


@bot.message_handler(
    content_types=["new_chat_members"]
)
def new_member(message):

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

        welcome = settings["welcome"]

        if not welcome:

            welcome = (
                "👋 سلام {name}!\n\n"
                "به <b>{group}</b> خوش اومدی ❤️"
            )

        welcome = welcome.replace(
            "{name}",
            user_mention(user)
        )

        welcome = welcome.replace(
            "{group}",
            message.chat.title or "گروه"
        )

        try:

            bot.send_message(
                message.chat.id,
                welcome
            )

        except Exception as e:

            print(
                "WELCOME ERROR:",
                e
            )


@bot.message_handler(
    content_types=["left_chat_member"]
)
def left_member(message):

    if not is_group(message):
        return

    try:

        bot.delete_message(
            message.chat.id,
            message.message_id
        )

    except Exception:
        pass


@bot.message_handler(
    func=lambda m:
    is_group(m)
    and m.text
    and m.text.startswith("خوشامد ")
)
def set_welcome(message):

    if not admin_only(message):
        return

    welcome = message.text[
        len("خوشامد "):
    ].strip()

    if not welcome:

        bot.reply_to(
            message,
            "❌ متن خوشامد را وارد کن."
        )

        return

    set_setting(
        message.chat.id,
        "welcome",
        welcome
    )

    bot.reply_to(
        message,
        "✅ متن خوشامد ذخیره شد.\n\n"
        "متغیرها:\n"
        "<code>{name}</code>\n"
        "<code>{group}</code>"
    )


@bot.message_handler(
    func=lambda m:
    is_group(m)
    and m.text
    and m.text.lower()
    in (
        "خوشامد روشن",
        "welcome on",
        "خوشامد خاموش",
        "welcome off"
    )
)
def welcome_toggle(message):

    if not admin_only(message):
        return

    enabled = message.text.lower() in (
        "خوشامد روشن",
        "welcome on"
    )

    set_setting(
        message.chat.id,
        "welcome_enabled",
        1 if enabled else 0
    )

    bot.reply_to(
        message,
        "👋 خوشامدگویی "
        + (
            "فعال شد."
            if enabled
            else
            "غیرفعال شد."
        )
)
     def admin_panel():

    kb = types.InlineKeyboardMarkup(
        row_width=2
    )

    kb.add(
        types.InlineKeyboardButton(
            "🛡 مدیریت کاربر",
            callback_data="panel:users"
        ),
        types.InlineKeyboardButton(
            "🔒 قفل‌ها",
            callback_data="panel:locks"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "🤖 ضداسپم",
            callback_data="panel:antispam"
        ),
        types.InlineKeyboardButton(
            "⚠️ اخطارها",
            callback_data="panel:warnings"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "📊 آمار",
            callback_data="panel:stats"
        ),
        types.InlineKeyboardButton(
            "⚙️ تنظیمات",
            callback_data="panel:settings"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "📜 لاگ",
            callback_data="panel:logs"
        ),
        types.InlineKeyboardButton(
            "📖 راهنما",
            callback_data="panel:help"
        )
    )

    return kb


def edit_panel(call, text, keyboard):

    try:

        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )

    except Exception as e:

        print(
            "PANEL ERROR:",
            e
        )


@bot.callback_query_handler(
    func=lambda call:
    call.data.startswith("panel:")
)
def panel_callback(call):

    chat_id = call.message.chat.id

    if not is_admin_user(
        chat_id,
        call.from_user.id
    ):

        bot.answer_callback_query(
            call.id,
            "⛔ فقط ادمین‌ها.",
            show_alert=True
        )

        return

    section = call.data.split(":")[1]

    if section == "users":

        text = (
            "🛡 <b>مدیریت کاربران</b>\n\n"
            "روی پیام کاربر ریپلای کن:\n\n"
            "🔨 بن\n"
            "👢 کیک\n"
            "🔇 سکوت 10m\n"
            "🔊 رفع سکوت\n"
            "⚠️ اخطار\n"
            "➖ برداشتن اخطار"
        )

        kb = types.InlineKeyboardMarkup()

        kb.add(
            types.InlineKeyboardButton(
                "🔙 برگشت",
                callback_data="panel:main"
            )
        )

        edit_panel(call, text, kb)
        return

    if section == "locks":

        lines = [
            "🔒 <b>وضعیت قفل‌ها</b>\n"
        ]

        for key, title in LOCK_TYPES.items():

            status = (
                "🔴 فعال"
                if get_lock(chat_id, key)
                else
                "🟢 خاموش"
            )

            lines.append(
                f"{status} — {title}"
            )

        lines.append(
            "\nمثال:\n"
            "<code>قفل لینک</code>\n"
            "<code>باز لینک</code>"
        )

        kb = types.InlineKeyboardMarkup()

        kb.add(
            types.InlineKeyboardButton(
                "🔙 برگشت",
                callback_data="panel:main"
            )
        )

        edit_panel(
            call,
            "\n".join(lines),
            kb
        )

        return

    if section == "antispam":

        settings = get_settings(chat_id)

        text = (
            "🤖 <b>ضداسپم</b>\n\n"
            f"📨 Flood: "
            f"<b>{settings['flood_limit']}</b>\n"
            f"⏱ بازه: "
            f"<b>{settings['flood_seconds']} ثانیه</b>\n\n"
            f"🔗 ضدلینک: "
            f"{'فعال' if settings['anti_link'] else 'خاموش'}\n"
            f"↪️ ضدفوروارد: "
            f"{'فعال' if settings['anti_forward'] else 'خاموش'}\n"
            f"🔁 ضدتکرار: "
            f"{'فعال' if settings['anti_repeat'] else 'خاموش'}\n"
            f"🤬 فیلتر کلمات: "
            f"{'فعال' if settings['badword_filter'] else 'خاموش'}"
        )

        kb = types.InlineKeyboardMarkup(
            row_width=2
        )

        kb.add(
            types.InlineKeyboardButton(
                "🔗 ضدلینک",
                callback_data="toggle:anti_link"
            ),
            types.InlineKeyboardButton(
                "↪️ ضدفوروارد",
                callback_data="toggle:anti_forward"
            )
        )

        kb.add(
            types.InlineKeyboardButton(
                "🔁 ضدتکرار",
                callback_data="toggle:anti_repeat"
            ),
            types.InlineKeyboardButton(
                "🤬 فیلتر کلمات",
                callback_data="toggle:badword_filter"
            )
        )

        kb.add(
            types.InlineKeyboardButton(
                "🔙 برگشت",
                callback_data="panel:main"
            )
        )

        edit_panel(
            call,
            text,
            kb
        )

        return

    if section == "warnings":

        settings = get_settings(chat_id)

        text = (
            "⚠️ <b>سیستم اخطار</b>\n\n"
            f"حد فعلی: "
            f"<b>{settings['warn_limit']}</b>\n\n"
            "رسیدن به حد = بن خودکار"
        )

        kb = types.InlineKeyboardMarkup()

        kb.add(
            types.InlineKeyboardButton(
                "🔙 برگشت",
                callback_data="panel:main"
            )
        )

        edit_panel(
            call,
            text,
            kb
        )

        return

    if section == "stats":

        con = db()

        actions = con.execute("""
            SELECT COUNT(*) total
            FROM actions
            WHERE chat_id=?
        """, (chat_id,)).fetchone()["total"]

        bans = con.execute("""
            SELECT COUNT(*) total
            FROM actions
            WHERE chat_id=?
            AND action IN ('BAN','AUTO_BAN')
        """, (chat_id,)).fetchone()["total"]

        warns = con.execute("""
            SELECT COUNT(*) total
            FROM actions
            WHERE chat_id=?
            AND action='WARN'
        """, (chat_id,)).fetchone()["total"]

        con.close()

        text = (
            "📊 <b>آمار گروه</b>\n\n"
            f"📋 عملیات: <b>{actions}</b>\n"
            f"🔨 بن: <b>{bans}</b>\n"
            f"⚠️ اخطار: <b>{warns}</b>\n"
            f"🆔 ID: <code>{chat_id}</code>"
        )

        kb = types.InlineKeyboardMarkup()

        kb.add(
            types.InlineKeyboardButton(
                "🔙 برگشت",
                callback_data="panel:main"
            )
        )

        edit_panel(
            call,
            text,
            kb
        )

        return

    if section == "settings":

        settings = get_settings(chat_id)

        text = (
            "⚙️ <b>تنظیمات</b>\n\n"
            f"⚠️ حد اخطار: "
            f"<b>{settings['warn_limit']}</b>\n"
            f"🤖 Flood: "
            f"<b>{settings['flood_limit']}</b> / "
            f"{settings['flood_seconds']}s\n"
            f"👋 خوشامد: "
            f"{'فعال' if settings['welcome_enabled'] else 'خاموش'}"
        )

        kb = types.InlineKeyboardMarkup()

        kb.add(
            types.InlineKeyboardButton(
                "⚠️ حد اخطار 3",
                callback_data="warnlimit:3"
            ),
            types.InlineKeyboardButton(
                "⚠️ حد اخطار 5",
                callback_data="warnlimit:5"
            )
        )

        kb.add(
            types.InlineKeyboardButton(
                "🔙 برگشت",
                callback_data="panel:main"
            )
        )

        edit_panel(
            call,
            text,
            kb
        )

        return

    if section == "logs":

        con = db()

        rows = con.execute("""
            SELECT *
            FROM actions
            WHERE chat_id=?
            ORDER BY id DESC
            LIMIT 8
        """, (chat_id,)).fetchall()

        con.close()

        if not rows:

            text = (
                "📜 <b>لاگ</b>\n\n"
                "هنوز عملیاتی ثبت نشده."
            )

        else:

            lines = [
                "📜 <b>آخرین عملیات</b>\n"
            ]

            for row in rows:

                lines.append(
                    f"• <b>{row['action']}</b> "
                    f"User: <code>{row['user_id']}</code>"
                )

            text = "\n".join(lines)

        kb = types.InlineKeyboardMarkup()

        kb.add(
            types.InlineKeyboardButton(
                "🔙 برگشت",
                callback_data="panel:main"
            )
        )

        edit_panel(
            call,
            text,
            kb
        )

        return

    if section == "help":

        text = (
            "📖 <b>راهنمای مدیریت</b>\n\n"
            "🔨 بن / کیک\n"
            "🔇 میوت موقت\n"
            "⚠️ اخطار\n"
            "🔒 قفل رسانه‌ها\n"
            "🤖 ضداسپم\n"
            "🔗 ضدلینک\n"
            "↪️ ضدفوروارد\n"
            "🔁 ضدتکرار\n"
            "👋 خوشامدگویی\n"
            "📊 آمار\n"
            "📜 لاگ"
        )

        kb = types.InlineKeyboardMarkup()

        kb.add(
            types.InlineKeyboardButton(
                "🔙 برگشت",
                callback_data="panel:main"
            )
        )

        edit_panel(
            call,
            text,
            kb
        )

        return

    if section == "main":

        edit_panel(
            call,
            "⚙️ <b>پنل مدیریت گروه</b>\n\n"
            "بخش موردنظر را انتخاب کن:",
            admin_panel()
        )


@bot.callback_query_handler(
    func=lambda call:
    call.data.startswith("toggle:")
)
def toggle_callback(call):

    chat_id = call.message.chat.id

    if not is_admin_user(
        chat_id,
        call.from_user.id
    ):
        return

    setting = call.data.split(":")[1]

    settings = get_settings(chat_id)

    current = settings[setting]
    new_value = 0 if current else 1

    set_setting(
        chat_id,
        setting,
        new_value
    )

    bot.answer_callback_query(
        call.id,
        "✅ تغییر کرد."
    )

    panel_callback(
        type(
            "FakeCall",
            (),
            {
                "message": call.message,
                "from_user": call.from_user,
                "data": "panel:antispam"
            }
        )()
    )
@bot.callback_query_handler(
    func=lambda call:
    call.data.startswith("warnlimit:")
)
def warnlimit_callback(call):

    chat_id = call.message.chat.id

    if not is_admin_user(
        chat_id,
        call.from_user.id
    ):
        return

    value = int(
        call.data.split(":")[1]
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

    try:

        bot.edit_message_text(
            f"✅ <b>تنظیم شد</b>\n\n"
            f"⚠️ حد اخطار: <b>{value}</b>",
            chat_id,
            call.message.message_id,
            reply_markup=admin_panel()
        )

    except Exception:
        pass


@bot.message_handler(commands=["start"])
def private_start(message):

    if message.chat.type != "private":
        return

    kb = types.InlineKeyboardMarkup(
        row_width=2
    )

    kb.add(
        types.InlineKeyboardButton(
            "🛡 امکانات",
            callback_data="private:features"
        ),
        types.InlineKeyboardButton(
            "📖 راهنما",
            callback_data="private:help"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "🤖 وضعیت",
            callback_data="private:status"
        )
    )

    bot.send_message(
        message.chat.id,
        "🤖 <b>Group Manager</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🛡 ربات حرفه‌ای مدیریت گروه\n\n"
        "بات را به گروه اضافه کن، "
        "ادمینش کن و سپس:\n\n"
        "<code>/panel</code>\n\n"
        "را بزن.",
        reply_markup=kb
    )


@bot.callback_query_handler(
    func=lambda call:
    call.data.startswith("private:")
)
def private_callback(call):

    section = call.data.split(":")[1]

    if section == "features":

        text = (
            "🛡 <b>امکانات ربات</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔨 بن\n"
            "👢 کیک\n"
            "🔇 میوت موقت\n"
            "⚠️ سیستم اخطار\n"
            "🤖 ضد Flood\n"
            "🔗 ضد لینک\n"
            "↪️ ضد فوروارد\n"
            "🔁 ضد تکرار\n"
            "🤬 فیلتر کلمات\n"
            "🔒 قفل عکس\n"
            "🔒 قفل فیلم\n"
            "🔒 قفل GIF\n"
            "🔒 قفل استیکر\n"
            "🔒 قفل ویس\n"
            "🔒 قفل فایل\n"
            "👋 خوشامدگویی\n"
            "📊 آمار\n"
            "📜 لاگ\n"
            "⚙️ پنل شیشه‌ای\n"
            "💾 تنظیمات جدا برای هر گروه"
        )

    elif section == "status":

        text = (
            "🟢 <b>ربات آنلاین است</b>\n\n"
            "⚡ آماده مدیریت گروه‌ها\n"
            "🛡 سیستم امنیتی آماده\n"
            "💾 دیتابیس فعال"
        )

    elif section == "help":

        text = (
            "📖 <b>راهنما</b>\n\n"
            "1️⃣ بات را به گروه اضافه کن.\n"
            "2️⃣ بات را ادمین کن.\n"
            "3️⃣ دسترسی حذف پیام بده.\n"
            "4️⃣ دسترسی Ban/Restrict بده.\n"
            "5️⃣ در BotFather بخش Privacy را "
            "روی Disable قرار بده.\n"
            "6️⃣ داخل گروه <code>/panel</code> بزن."
        )

    else:

        text = (
            "🤖 <b>Group Manager</b>\n\n"
            "ربات مدیریت حرفه‌ای گروه."
        )

    kb = types.InlineKeyboardMarkup()

    kb.add(
        types.InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="private:back"
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


@bot.my_chat_member_handler()
def bot_status_update(message):

    try:

        chat = message.chat

        if chat.type not in (
            "group",
            "supergroup"
        ):
            return

        ensure_group(chat)

        status = (
            message.new_chat_member.status
        )

        if status in (
            "administrator",
            "member"
        ):

            try:

                bot.send_message(
                    chat.id,
                    "🤖 <b>سلام!</b>\n\n"
                    "من برای مدیریت گروه آماده‌ام.\n\n"
                    "⚙️ پنل:\n"
                    "<code>/panel</code>\n\n"
                    "📖 راهنما:\n"
                    "<code>/help</code>"
                )

            except Exception:
                pass

    except Exception as e:

        print(
            "STATUS ERROR:",
            e
        )


def temporary_worker():

    while True:

        now = int(time.time())
        expired = []

        with temporary_lock:

            for key, until in list(
                temporary_actions.items()
            ):

                if now >= until:
                    expired.append(key)

        for chat_id, user_id in expired:

            try:

                permissions = ChatPermissions(
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

                bot.restrict_chat_member(
                    chat_id,
                    user_id,
                    permissions=permissions
                )

            except Exception as e:

                print(
                    "AUTO UNMUTE ERROR:",
                    e
                )

            with temporary_lock:

                temporary_actions.pop(
                    (chat_id, user_id),
                    None
                )

        time.sleep(5)


def startup():

    print(
        "================================"
    )

    print(
        "🤖 Group Manager"
    )

    print(
        "🟢 Bot is running..."
    )

    print(
        "💾 Database:",
        DB_NAME
    )

    print(
        "================================"
    )


threading.Thread(
    target=temporary_worker,
    daemon=True
).start()

startup()

bot.infinity_polling(
    skip_pending=True,
    timeout=60,
    long_polling_timeout=60
        )
