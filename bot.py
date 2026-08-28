# -*- coding: utf-8 -*-

import sqlite3
import random
import time
import html
import threading
import telebot
from telebot import types

BOT_TOKEN = "8699716698:AAHWtpFpC_GRmCTRgU0hvVVyebJaMtG1CqE"
ADMIN_ID = 7530457395
DB_NAME = "kian_bot.db"

bot = telebot.TeleBot(
    BOT_TOKEN,
    parse_mode="HTML",
    threaded=True
)

db = sqlite3.connect(
    DB_NAME,
    check_same_thread=False
)
db.row_factory = sqlite3.Row
lock = threading.Lock()

admin_state = {}


# =========================
# DATABASE
# =========================

def init_db():

    with lock:
        c = db.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS triggers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT UNIQUE
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS photos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_id INTEGER,
            file_id TEXT,
            used INTEGER DEFAULT 0
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS groups_table(
            id INTEGER PRIMARY KEY,
            title TEXT
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)

        db.commit()


init_db()


# =========================
# HELPERS
# =========================

def is_admin(uid):
    try:
        return int(uid) == ADMIN_ID
    except:
        return False


def clean(text):
    return (text or "").strip().lower()


def esc(text):
    return html.escape(str(text or ""))


def tag(user):
    return (
        f'<a href="tg://user?id={user.id}">'
        f'{esc(user.first_name or "کاربر")}'
        f'</a>'
    )


def save_user(user):

    if not user:
        return

    with lock:
        c = db.cursor()

        c.execute("""
        INSERT INTO users
        (id,username,first_name,last_name)
        VALUES(?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
        username=excluded.username,
        first_name=excluded.first_name,
        last_name=excluded.last_name
        """, (
            user.id,
            user.username or "",
            user.first_name or "",
            user.last_name or ""
        ))

        db.commit()


def save_group(chat):

    if chat.type not in ("group", "supergroup"):
        return

    with lock:
        c = db.cursor()

        c.execute("""
        INSERT INTO groups_table(id,title)
        VALUES(?,?)
        ON CONFLICT(id) DO UPDATE SET
        title=excluded.title
        """, (
            chat.id,
            chat.title or ""
        ))

        db.commit()


def set_setting(key, value):

    with lock:
        c = db.cursor()

        c.execute("""
        INSERT INTO settings(key,value)
        VALUES(?,?)
        ON CONFLICT(key) DO UPDATE SET
        value=excluded.value
        """, (key, str(value)))

        db.commit()


def get_setting(key, default=""):

    with lock:
        c = db.cursor()

        c.execute(
            "SELECT value FROM settings WHERE key=?",
            (key,)
        )

        row = c.fetchone()

    return row["value"] if row else default


# =========================
# AUTO RESPONSES
# =========================

def get_trigger(keyword):

    with lock:
        c = db.cursor()

        c.execute(
            "SELECT * FROM triggers WHERE keyword=?",
            (clean(keyword),)
        )

        return c.fetchone()


def create_trigger(keyword):

    keyword = clean(keyword)

    if not keyword:
        return False

    with lock:
        c = db.cursor()

        c.execute(
            "INSERT OR IGNORE INTO triggers(keyword) VALUES(?)",
            (keyword,)
        )

        db.commit()

    return True


def add_photo(keyword, file_id):

    create_trigger(keyword)

    trigger = get_trigger(keyword)

    if not trigger:
        return False

    with lock:
        c = db.cursor()

        c.execute("""
        INSERT INTO photos(trigger_id,file_id,used)
        VALUES(?,?,0)
        """, (
            trigger["id"],
            file_id
        ))

        db.commit()

    return True


def get_random_photo(keyword):

    trigger = get_trigger(keyword)

    if not trigger:
        return None

    tid = trigger["id"]

    with lock:
        c = db.cursor()

        c.execute("""
        SELECT * FROM photos
        WHERE trigger_id=? AND used=0
        ORDER BY RANDOM()
        LIMIT 1
        """, (tid,))

        row = c.fetchone()

        if not row:

            c.execute("""
            SELECT COUNT(*) FROM photos
            WHERE trigger_id=?
            """, (tid,))

            if c.fetchone()[0] == 0:
                return None

            c.execute("""
            UPDATE photos SET used=0
            WHERE trigger_id=?
            """, (tid,))

            db.commit()

            c.execute("""
            SELECT * FROM photos
            WHERE trigger_id=?
            ORDER BY RANDOM()
            LIMIT 1
            """, (tid,))

            row = c.fetchone()

        if not row:
            return None

        c.execute(
            "UPDATE photos SET used=1 WHERE id=?",
            (row["id"],)
        )

        db.commit()

        return row["file_id"]


def photo_count(keyword):

    trigger = get_trigger(keyword)

    if not trigger:
        return 0

    with lock:
        c = db.cursor()

        c.execute("""
        SELECT COUNT(*) FROM photos
        WHERE trigger_id=?
        """, (trigger["id"],))

        return c.fetchone()[0]


def delete_trigger(keyword):

    trigger = get_trigger(keyword)

    if not trigger:
        return False

    with lock:
        c = db.cursor()

        c.execute(
            "DELETE FROM photos WHERE trigger_id=?",
            (trigger["id"],)
        )

        c.execute(
            "DELETE FROM triggers WHERE id=?",
            (trigger["id"],)
        )

        db.commit()

    return True
    # =========================
# INLINE PANELS
# =========================

def main_keyboard():

    kb = types.InlineKeyboardMarkup(row_width=2)

    kb.add(
        types.InlineKeyboardButton(
            "📸 پاسخ خودکار",
            callback_data="auto"
        ),
        types.InlineKeyboardButton(
            "👋 خوشامدگویی",
            callback_data="welcome"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "📊 آمار",
            callback_data="stats"
        )
    )

    return kb


def auto_keyboard():

    kb = types.InlineKeyboardMarkup(row_width=2)

    kb.add(
        types.InlineKeyboardButton(
            "➕ ساخت پاسخ",
            callback_data="add_auto"
        ),
        types.InlineKeyboardButton(
            "📋 لیست پاسخ‌ها",
            callback_data="list_auto"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "🔢 تعداد عکس",
            callback_data="count_auto"
        ),
        types.InlineKeyboardButton(
            "🗑 حذف پاسخ",
            callback_data="delete_auto"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="home"
        )
    )

    return kb


def welcome_keyboard():

    status = get_setting(
        "welcome_enabled",
        "0"
    )

    status_text = (
        "🟢 فعال"
        if status == "1"
        else
        "🔴 غیرفعال"
    )

    kb = types.InlineKeyboardMarkup(row_width=2)

    kb.add(
        types.InlineKeyboardButton(
            status_text,
            callback_data="welcome_toggle"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "🖼 عکس",
            callback_data="welcome_photo"
        ),
        types.InlineKeyboardButton(
            "📝 متن",
            callback_data="welcome_text"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "👀 پیش‌نمایش",
            callback_data="welcome_preview"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="home"
        )
    )

    return kb


# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(message):

    save_user(message.from_user)

    if (
        message.chat.type == "private"
        and is_admin(message.from_user.id)
    ):

        bot.send_message(
            message.chat.id,
            """
<b>👑 پنل مدیریت</b>

همه تنظیمات ربات را از دکمه‌های زیر مدیریت کن.
""",
            reply_markup=main_keyboard()
        )

    elif message.chat.type == "private":

        bot.send_message(
            message.chat.id,
            "سلام 👋"
        )


# =========================
# CALLBACKS
# =========================

@bot.callback_query_handler(
    func=lambda call: True
)
def callbacks(call):

    if not is_admin(call.from_user.id):

        bot.answer_callback_query(
            call.id,
            "❌ دسترسی ندارید.",
            show_alert=True
        )

        return

    data = call.data

    try:
        bot.answer_callback_query(call.id)
    except:
        pass

    if data == "home":

        bot.edit_message_text(
            "<b>👑 پنل مدیریت</b>\n\nیک بخش را انتخاب کن:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_keyboard()
        )

        return

    if data == "auto":

        bot.edit_message_text(
            "<b>📸 مدیریت پاسخ‌های خودکار</b>",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=auto_keyboard()
        )

        return

    if data == "welcome":

        bot.edit_message_text(
            """
<b>👋 تنظیمات خوشامدگویی</b>

می‌توانی عکس و متن خوشامدگویی را تنظیم کنی.
""",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=welcome_keyboard()
        )

        return

    if data == "welcome_toggle":

        old = get_setting(
            "welcome_enabled",
            "0"
        )

        new = "0" if old == "1" else "1"

        set_setting(
            "welcome_enabled",
            new
        )

        bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=welcome_keyboard()
        )

        return

    if data == "welcome_photo":

        admin_state[
            call.from_user.id
        ] = {
            "mode": "welcome_photo"
        }

        bot.send_message(
            call.message.chat.id,
            "🖼 عکس خوشامدگویی را بفرست."
        )

        return

    if data == "welcome_text":

        admin_state[
            call.from_user.id
        ] = {
            "mode": "welcome_text"
        }

        bot.send_message(
            call.message.chat.id,
            """
📝 <b>متن خوشامدگویی را بفرست.</b>

متغیرهای قابل استفاده:

<code>{name}</code>
اسم کاربر

<code>{username}</code>
یوزرنیم

<code>{id}</code>
آیدی کاربر

<code>{group}</code>
اسم گپ

<code>{tag}</code>
تگ قابل کلیک کاربر

مثال:

<code>سلام {tag} 👋
به {group} خوش اومدی ❤️</code>
"""
        )

        return

    if data == "welcome_preview":

        text = get_setting(
            "welcome_text",
            "سلام {tag} 👋\nبه {group} خوش اومدی ❤️"
        )

        text = text.replace(
            "{name}", "کاربر"
        ).replace(
            "{username}", "@username"
        ).replace(
            "{id}", "123456"
        ).replace(
            "{group}", "گپ نمونه"
        ).replace(
            "{tag}",
            '<a href="tg://user?id=123456">کاربر</a>'
        )

        photo = get_setting(
            "welcome_photo",
            ""
        )

        if photo:

            bot.send_photo(
                call.message.chat.id,
                photo,
                caption=text
            )

        else:

            bot.send_message(
                call.message.chat.id,
                text
            )

        return

    if data == "add_auto":

        admin_state[
            call.from_user.id
        ] = {
            "mode": "keyword"
        }

        bot.send_message(
            call.message.chat.id,
            """
➕ <b>ساخت پاسخ خودکار</b>

عبارتی که کاربر باید بگوید را بفرست.

مثال:

<code>عکس بفرست</code>
"""
        )

        return

    if data == "count_auto":

        admin_state[
            call.from_user.id
        ] = {
            "mode": "count"
        }

        bot.send_message(
            call.message.chat.id,
            "🔢 عبارت پاسخ را بفرست."
        )

        return

    if data == "delete_auto":

        admin_state[
            call.from_user.id
        ] = {
            "mode": "delete"
        }

        bot.send_message(
            call.message.chat.id,
            "🗑 عبارت پاسخ را برای حذف بفرست."
        )

        return

    if data == "list_auto":

        with lock:
            c = db.cursor()

            c.execute("""
            SELECT t.keyword,COUNT(p.id) total
            FROM triggers t
            LEFT JOIN photos p
            ON p.trigger_id=t.id
            GROUP BY t.id
            """)

            rows = c.fetchall()

        if not rows:

            text = "📭 هنوز پاسخی ساخته نشده."

        else:

            text = "<b>📋 پاسخ‌های خودکار</b>\n\n"

            for row in rows:

                text += (
                    f"🔹 <code>{esc(row['keyword'])}</code>"
                    f" — {row['total']} عکس\n"
                )

        bot.send_message(
            call.message.chat.id,
            text,
            reply_markup=auto_keyboard()
        )

        return

    if data == "stats":

        with lock:
            c = db.cursor()

            c.execute(
                "SELECT COUNT(*) FROM users"
            )
            users = c.fetchone()[0]

            c.execute(
                "SELECT COUNT(*) FROM groups_table"
            )
            groups = c.fetchone()[0]

            c.execute(
                "SELECT COUNT(*) FROM triggers"
            )
            triggers = c.fetchone()[0]

            c.execute(
                "SELECT COUNT(*) FROM photos"
            )
            photos = c.fetchone()[0]

        bot.send_message(
            call.message.chat.id,
            f"""
📊 <b>آمار ربات</b>

👤 کاربران: <b>{users}</b>
👥 گپ‌ها: <b>{groups}</b>
⚡ پاسخ‌ها: <b>{triggers}</b>
🖼 عکس‌ها: <b>{photos}</b>
""",
            reply_markup=main_keyboard()
        )

        return


# =========================
# ADMIN TEXT
# =========================

@bot.message_handler(
    func=lambda m:
        m.chat.type == "private"
        and is_admin(m.from_user.id)
        and m.from_user.id in admin_state
        and m.content_type == "text"
)
def admin_text(message):

    state = admin_state.get(
        message.from_user.id
    )

    if not state:
        return

    mode = state["mode"]

    if mode == "keyword":

        keyword = clean(message.text)

        if not keyword:
            bot.send_message(
                message.chat.id,
                "❌ عبارت خالی است."
            )
            return

        create_trigger(keyword)

        admin_state[
            message.from_user.id
        ] = {
            "mode": "photos",
            "keyword": keyword
        }

        bot.send_message(
            message.chat.id,
            f"""
✅ عبارت ثبت شد:

<code>{esc(keyword)}</code>

حالا عکس‌ها را بفرست.

برای پایان بنویس:

<code>پایان</code>
"""
        )

        return

    if mode == "count":

        count = photo_count(
            message.text
        )

        bot.send_message(
            message.chat.id,
            f"🖼 تعداد عکس‌ها: <b>{count}</b>"
        )

        admin_state.pop(
            message.from_user.id,
            None
        )

        return

    if mode == "delete":

        if delete_trigger(message.text):

            bot.send_message(
                message.chat.id,
                "✅ پاسخ خودکار حذف شد."
            )

        else:

            bot.send_message(
                message.chat.id,
                "❌ چنین پاسخی پیدا نشد."
            )

        admin_state.pop(
            message.from_user.id,
            None
        )

        return

    if mode == "welcome_text":

        set_setting(
            "welcome_text",
            message.text
        )

        bot.send_message(
            message.chat.id,
            "✅ متن خوشامدگویی ذخیره شد."
        )

        admin_state.pop(
            message.from_user.id,
            None
        )

        return
        # =========================
# ADMIN PHOTOS
# =========================

@bot.message_handler(
    content_types=["photo"]
)
def admin_photo(message):

    if message.chat.type != "private":
        return

    if not is_admin(
        message.from_user.id
    ):
        return

    state = admin_state.get(
        message.from_user.id
    )

    if not state:
        return

    mode = state["mode"]

    if mode == "photos":

        keyword = state["keyword"]

        add_photo(
            keyword,
            message.photo[-1].file_id
        )

        count = photo_count(keyword)

        bot.send_message(
            message.chat.id,
            f"✅ عکس ذخیره شد.\nتعداد: <b>{count}</b>"
        )

        return

    if mode == "welcome_photo":

        set_setting(
            "welcome_photo",
            message.photo[-1].file_id
        )

        bot.send_message(
            message.chat.id,
            "✅ عکس خوشامدگویی ذخیره شد."
        )

        admin_state.pop(
            message.from_user.id,
            None
        )


# =========================
# FINISH UPLOAD
# =========================

@bot.message_handler(
    func=lambda m:
        m.chat.type == "private"
        and is_admin(m.from_user.id)
        and clean(m.text) == "پایان"
)
def finish_upload(message):

    state = admin_state.get(
        message.from_user.id
    )

    if not state:
        return

    if state["mode"] != "photos":
        return

    keyword = state["keyword"]

    count = photo_count(keyword)

    admin_state.pop(
        message.from_user.id,
        None
    )

    bot.send_message(
        message.chat.id,
        f"""
✅ <b>آپلود تمام شد.</b>

عبارت:
<code>{esc(keyword)}</code>

تعداد عکس:
<b>{count}</b>
"""
    )


# =========================
# WELCOME
# =========================

@bot.message_handler(
    content_types=["new_chat_members"]
)
def welcome(message):

    save_group(message.chat)

    if get_setting(
        "welcome_enabled",
        "0"
    ) != "1":
        return

    template = get_setting(
        "welcome_text",
        "سلام {tag} 👋\nبه {group} خوش اومدی ❤️"
    )

    photo = get_setting(
        "welcome_photo",
        ""
    )

    for user in message.new_chat_members:

        save_user(user)

        try:

            if user.id == bot.get_me().id:
                continue

        except:
            pass

        username = (
            "@" + user.username
            if user.username
            else "ندارد"
        )

        text = template

        text = text.replace(
            "{name}",
            esc(user.first_name or "کاربر")
        )

        text = text.replace(
            "{username}",
            esc(username)
        )

        text = text.replace(
            "{id}",
            str(user.id)
        )

        text = text.replace(
            "{group}",
            esc(message.chat.title or "گپ")
        )

        text = text.replace(
            "{tag}",
            tag(user)
        )

        try:

            if photo:

                bot.send_photo(
                    message.chat.id,
                    photo,
                    caption=text
                )

            else:

                bot.send_message(
                    message.chat.id,
                    text
                )

        except Exception as e:

            print(
                "WELCOME ERROR:",
                e
            )


# =========================
# GROUP ADMIN CHECK
# =========================

def group_admin(message):

    if message.chat.type not in (
        "group",
        "supergroup"
    ):
        return False

    if is_admin(
        message.from_user.id
    ):
        return True

    try:

        member = bot.get_chat_member(
            message.chat.id,
            message.from_user.id
        )

        return member.status in (
            "administrator",
            "creator"
        )

    except:

        return False


def target(message):

    if not message.reply_to_message:
        return None

    return message.reply_to_message.from_user


def target_admin(message):

    user = target(message)

    if not user:
        return False

    if is_admin(user.id):
        return True

    try:

        member = bot.get_chat_member(
            message.chat.id,
            user.id
        )

        return member.status in (
            "administrator",
            "creator"
        )

    except:

        return False


# =========================
# BAN
# =========================

@bot.message_handler(
    func=lambda m: clean(m.text) == "بن"
)
def ban(message):

    if not group_admin(message):
        return

    user = target(message)

    if not user:

        bot.reply_to(
            message,
            "❌ روی پیام فرد ریپلای کن."
        )

        return

    if target_admin(message):

        bot.reply_to(
            message,
            "🛡 این فرد ادمینه."
        )

        return

    try:

        bot.ban_chat_member(
            message.chat.id,
            user.id
        )

        bot.reply_to(
            message,
            f"🚫 {tag(user)} بن شد."
        )

    except Exception as e:

        print(e)

        bot.reply_to(
            message,
            "❌ ربات دسترسی بن کردن ندارد."
        )


# =========================
# UNBAN
# =========================

@bot.message_handler(
    func=lambda m: clean(m.text) == "حذف بن"
)
def unban(message):

    if not group_admin(message):
        return

    user = target(message)

    if not user:

        bot.reply_to(
            message,
            "❌ روی پیام فرد ریپلای کن."
        )

        return

    try:

        bot.unban_chat_member(
            message.chat.id,
            user.id,
            only_if_banned=True
        )

        bot.reply_to(
            message,
            f"✅ {tag(user)} حذف بن شد."
        )

    except:

        bot.reply_to(
            message,
            "❌ حذف بن انجام نشد."
        )


# =========================
# MUTE
# =========================

@bot.message_handler(
    func=lambda m: clean(m.text) == "سکوت"
)
def mute(message):

    if not group_admin(message):
        return

    user = target(message)

    if not user:

        bot.reply_to(
            message,
            "❌ روی پیام فرد ریپلای کن."
        )

        return

    if target_admin(message):

        bot.reply_to(
            message,
            "🛡 این فرد ادمینه."
        )

        return

    try:

        bot.restrict_chat_member(
            message.chat.id,
            user.id,
            permissions=types.ChatPermissions(
                can_send_messages=False
            )
        )

        bot.reply_to(
            message,
            f"🔇 {tag(user)} سکوت شد."
        )

    except:

        bot.reply_to(
            message,
            "❌ ربات دسترسی سکوت کردن ندارد."
        )


# =========================
# UNMUTE
# =========================

@bot.message_handler(
    func=lambda m: clean(m.text) == "حذف سکوت"
)
def unmute(message):

    if not group_admin(message):
        return

    user = target(message)

    if not user:

        bot.reply_to(
            message,
            "❌ روی پیام فرد ریپلای کن."
        )

        return

    try:

        bot.restrict_chat_member(
            message.chat.id,
            user.id,
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

        bot.reply_to(
            message,
            f"🔊 {tag(user)} حذف سکوت شد."
        )

    except:

        bot.reply_to(
            message,
            "❌ حذف سکوت انجام نشد."
        )


# =========================
# DELETE
# =========================

@bot.message_handler(
    func=lambda m: clean(m.text) == "حذف"
)
def delete_message(message):

    if not group_admin(message):
        return

    if not message.reply_to_message:

        bot.reply_to(
            message,
            "❌ روی پیام موردنظر ریپلای کن."
        )

        return

    try:

        bot.delete_message(
            message.chat.id,
            message.reply_to_message.message_id
        )

        bot.delete_message(
            message.chat.id,
            message.message_id
        )

    except:

        bot.reply_to(
            message,
            "❌ حذف پیام انجام نشد."
        )


# =========================
# STATS
# =========================

@bot.message_handler(
    func=lambda m: clean(m.text) == "آمار"
)
def stats(message):

    if not group_admin(message):
        return

    with lock:

        c = db.cursor()

        c.execute(
            "SELECT COUNT(*) FROM users"
        )
        users = c.fetchone()[0]

        c.execute(
            "SELECT COUNT(*) FROM groups_table"
        )
        groups = c.fetchone()[0]

        c.execute(
            "SELECT COUNT(*) FROM photos"
        )
        photos = c.fetchone()[0]

        c.execute(
            "SELECT COUNT(*) FROM triggers"
        )
        triggers = c.fetchone()[0]

    bot.reply_to(
        message,
        f"""
📊 <b>آمار ربات</b>

👤 کاربران: <b>{users}</b>
👥 گپ‌ها: <b>{groups}</b>
⚡ پاسخ‌ها: <b>{triggers}</b>
🖼 عکس‌ها: <b>{photos}</b>
"""
    )


# =========================
# AUTO RESPONSE
# =========================

@bot.message_handler(
    content_types=["text"]
)
def auto_response(message):

    save_user(
        message.from_user
    )

    save_group(
        message.chat
    )

    if message.chat.type not in (
        "group",
        "supergroup"
    ):
        return

    text = clean(message.text)

    if text in (
        "بن",
        "حذف بن",
        "سکوت",
        "حذف سکوت",
        "حذف",
        "آمار"
    ):
        return

    photo = get_random_photo(text)

    if not photo:
        return

    try:

        bot.send_photo(
            message.chat.id,
            photo,
            reply_to_message_id=message.message_id
        )

    except Exception as e:

        print(
            "AUTO ERROR:",
            e
        )


# =========================
# RUN
# =========================

def run():

    print("=" * 45)
    print("KIAN BOT STARTING")
    print("ADMIN:", ADMIN_ID)
    print("=" * 45)

    while True:

        try:

            bot.infinity_polling(
                skip_pending=True,
                timeout=30,
                long_polling_timeout=30
            )

        except Exception as e:

            print(
                "POLLING ERROR:",
                e
            )

            time.sleep(5)


if __name__ == "__main__":
    run()