import telebot
from telebot import types
import sqlite3
import time
import re
import threading

# =========================
# CONFIG
# =========================

BOT_TOKEN = "8597049833:AAFnEjGLcOz09Duy6MIvOoMD9TA1-fiRhPE"
ADMIN_ID = 7781305425

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

DB_NAME = "archive.db"

states = {}
sent_messages = {}


# =========================
# DATABASE
# =========================

def connect():
    con = sqlite3.connect(DB_NAME, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = connect()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS titles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title_id INTEGER NOT NULL,
            item_type TEXT NOT NULL,
            file_id TEXT,
            content TEXT,
            created_at INTEGER NOT NULL
        )
    """)

    con.commit()
    con.close()


init_db()


# =========================
# SECURITY
# =========================

def allowed(message):
    return (
        message.from_user
        and message.from_user.id == ADMIN_ID
        and message.chat.type == "private"
    )


# =========================
# DATABASE FUNCTIONS
# =========================

def create_title(name):
    con = connect()

    cur = con.cursor()

    cur.execute(
        """
        INSERT INTO titles
        (user_id, name, created_at)
        VALUES (?, ?, ?)
        """,
        (
            ADMIN_ID,
            name,
            int(time.time())
        )
    )

    title_id = cur.lastrowid

    con.commit()
    con.close()

    return title_id


def get_titles():
    con = connect()

    rows = con.execute(
        """
        SELECT *
        FROM titles
        WHERE user_id=?
        ORDER BY id DESC
        """,
        (ADMIN_ID,)
    ).fetchall()

    con.close()

    return rows


def get_title(title_id):
    con = connect()

    row = con.execute(
        """
        SELECT *
        FROM titles
        WHERE id=? AND user_id=?
        """,
        (
            title_id,
            ADMIN_ID
        )
    ).fetchone()

    con.close()

    return row


def save_item(
    title_id,
    item_type,
    file_id=None,
    content=None
):
    con = connect()

    con.execute(
        """
        INSERT INTO items
        (
            user_id,
            title_id,
            item_type,
            file_id,
            content,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            ADMIN_ID,
            title_id,
            item_type,
            file_id,
            content,
            int(time.time())
        )
    )

    con.commit()
    con.close()


def get_items(title_id, item_type):
    con = connect()

    rows = con.execute(
        """
        SELECT *
        FROM items
        WHERE
            user_id=?
            AND title_id=?
            AND item_type=?
        ORDER BY id ASC
        """,
        (
            ADMIN_ID,
            title_id,
            item_type
        )
    ).fetchall()

    con.close()

    return rows


def get_count(title_id, item_type):
    con = connect()

    row = con.execute(
        """
        SELECT COUNT(*) AS total
        FROM items
        WHERE
            user_id=?
            AND title_id=?
            AND item_type=?
        """,
        (
            ADMIN_ID,
            title_id,
            item_type
        )
    ).fetchone()

    con.close()

    return row["total"]


def delete_category(title_id, item_type):
    con = connect()

    con.execute(
        """
        DELETE FROM items
        WHERE
            user_id=?
            AND title_id=?
            AND item_type=?
        """,
        (
            ADMIN_ID,
            title_id,
            item_type
        )
    )

    con.commit()
    con.close()


# =========================
# CONTENT DETECTION
# =========================

URL_PATTERN = re.compile(
    r"(https?://\S+|www\.\S+)",
    re.IGNORECASE
)


def detect(message):

    if message.content_type == "photo":
        return (
            "photo",
            message.photo[-1].file_id,
            None
        )

    if message.content_type == "video":
        return (
            "video",
            message.video.file_id,
            None
        )

    if message.content_type == "animation":
        return (
            "gif",
            message.animation.file_id,
            None
        )

    if message.content_type == "sticker":
        return (
            "sticker",
            message.sticker.file_id,
            None
        )

    if message.content_type == "text":

        text = message.text or ""

        if URL_PATTERN.search(text):
            return (
                "link",
                None,
                text
            )

        return (
            "text",
            None,
            text
        )

    return (
        None,
        None,
        None
    )


# =========================
# MESSAGE MEMORY
# =========================

def remember(chat_id, message_id):

    if chat_id not in sent_messages:
        sent_messages[chat_id] = set()

    sent_messages[chat_id].add(message_id)


def delete_message(chat_id, message_id):

    try:
        bot.delete_message(
            chat_id,
            message_id
        )
    except Exception:
        pass


def clear_session(chat_id):

    ids = list(
        sent_messages.get(
            chat_id,
            set()
        )
    )

    for message_id in ids:
        delete_message(
            chat_id,
            message_id
        )

    sent_messages.pop(
        chat_id,
        None
    )


# =========================
# KEYBOARDS
# =========================

def home_keyboard():

    kb = types.InlineKeyboardMarkup()

    kb.add(
        types.InlineKeyboardButton(
            "➕ ساخت عنوان",
            callback_data="new_title"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "📂 عنوان‌های من",
            callback_data="titles"
        )
    )

    return kb


def title_keyboard(title_id):

    kb = types.InlineKeyboardMarkup(
        row_width=2
    )

    photo = get_count(
        title_id,
        "photo"
    )

    video = get_count(
        title_id,
        "video"
    )

    text = get_count(
        title_id,
        "text"
    )

    sticker = get_count(
        title_id,
        "sticker"
    )

    gif = get_count(
        title_id,
        "gif"
    )

    link = get_count(
        title_id,
        "link"
    )

    kb.add(
        types.InlineKeyboardButton(
            f"🖼 عکس {photo}",
            callback_data=f"cat:{title_id}:photo"
        ),
        types.InlineKeyboardButton(
            f"🎬 فیلم {video}",
            callback_data=f"cat:{title_id}:video"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            f"📝 متن {text}",
            callback_data=f"cat:{title_id}:text"
        ),
        types.InlineKeyboardButton(
            f"🎭 استیکر {sticker}",
            callback_data=f"cat:{title_id}:sticker"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            f"🎞 GIF {gif}",
            callback_data=f"cat:{title_id}:gif"
        ),
        types.InlineKeyboardButton(
            f"🔗 لینک {link}",
            callback_data=f"cat:{title_id}:link"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "➕ ذخیره محتوا",
            callback_data=f"save:{title_id}"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="titles"
        )
    )

    return kb
    # =========================
# TITLES PAGE
# =========================

def show_titles(
    chat_id,
    message_id=None
):

    rows = get_titles()

    kb = types.InlineKeyboardMarkup(
        row_width=1
    )

    if not rows:

        text = (
            "📂 <b>عنوان‌های من</b>\n\n"
            "هنوز عنوانی نداری."
        )

    else:

        text = (
            "📂 <b>عنوان‌های من</b>\n\n"
            "عنوان موردنظر را انتخاب کن:"
        )

        for row in rows:

            title_id = row["id"]

            total = 0

            for item_type in [
                "photo",
                "video",
                "text",
                "sticker",
                "gif",
                "link"
            ]:
                total += get_count(
                    title_id,
                    item_type
                )

            kb.add(
                types.InlineKeyboardButton(
                    f"📁 {row['name']} • {total}",
                    callback_data=f"title:{title_id}"
                )
            )

    kb.add(
        types.InlineKeyboardButton(
            "➕ ساخت عنوان",
            callback_data="new_title"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "🔙 منوی اصلی",
            callback_data="home"
        )
    )

    if message_id:

        try:
            bot.edit_message_text(
                text,
                chat_id,
                message_id,
                reply_markup=kb
            )
        except Exception:
            pass

    else:

        msg = bot.send_message(
            chat_id,
            text,
            reply_markup=kb
        )

        remember(
            chat_id,
            msg.message_id
        )


# =========================
# START
# =========================

@bot.message_handler(
    commands=["start"]
)
def start(message):

    if not allowed(message):
        return

    states.pop(
        message.chat.id,
        None
    )

    msg = bot.send_message(
        message.chat.id,
        "🗄 <b>آرشیو شخصی</b>\n\n"
        "به آرشیو خودت خوش آمدی.",
        reply_markup=home_keyboard()
    )

    remember(
        message.chat.id,
        msg.message_id
    )


# =========================
# CALLBACKS
# =========================

@bot.callback_query_handler(
    func=lambda call: True
)
def callbacks(call):

    if call.from_user.id != ADMIN_ID:
        return

    chat_id = call.message.chat.id
    message_id = call.message.message_id
    data = call.data

    bot.answer_callback_query(
        call.id
    )

    # ---------------------
    # HOME
    # ---------------------

    if data == "home":

        states.pop(
            chat_id,
            None
        )

        try:
            bot.edit_message_text(
                "🗄 <b>آرشیو شخصی</b>\n\n"
                "یک گزینه انتخاب کن:",
                chat_id,
                message_id,
                reply_markup=home_keyboard()
            )
        except Exception:
            pass

        return

    # ---------------------
    # TITLES
    # ---------------------

    if data == "titles":

        states.pop(
            chat_id,
            None
        )

        show_titles(
            chat_id,
            message_id
        )

        return

    # ---------------------
    # NEW TITLE
    # ---------------------

    if data == "new_title":

        states[chat_id] = {
            "mode": "new_title"
        }

        kb = types.InlineKeyboardMarkup()

        kb.add(
            types.InlineKeyboardButton(
                "❌ لغو",
                callback_data="home"
            )
        )

        try:
            bot.edit_message_text(
                "🏷 <b>ساخت عنوان</b>\n\n"
                "نام عنوان را بفرست.\n\n"
                "مثال:\n"
                "<code>وطنی</code>",
                chat_id,
                message_id,
                reply_markup=kb
            )
        except Exception:
            pass

        return

    # ---------------------
    # OPEN TITLE
    # ---------------------

    if data.startswith("title:"):

        title_id = int(
            data.split(":")[1]
        )

        title = get_title(
            title_id
        )

        if not title:
            return

        counts = {
            "photo": get_count(
                title_id,
                "photo"
            ),
            "video": get_count(
                title_id,
                "video"
            ),
            "text": get_count(
                title_id,
                "text"
            ),
            "sticker": get_count(
                title_id,
                "sticker"
            ),
            "gif": get_count(
                title_id,
                "gif"
            ),
            "link": get_count(
                title_id,
                "link"
            )
        }

        text = (
            f"📁 <b>{title['name']}</b>\n\n"
            f"🖼 عکس: {counts['photo']}\n"
            f"🎬 فیلم: {counts['video']}\n"
            f"📝 متن: {counts['text']}\n"
            f"🎭 استیکر: {counts['sticker']}\n"
            f"🎞 GIF: {counts['gif']}\n"
            f"🔗 لینک: {counts['link']}\n\n"
            "یک بخش را انتخاب کن:"
        )

        try:
            bot.edit_message_text(
                text,
                chat_id,
                message_id,
                reply_markup=title_keyboard(
                    title_id
                )
            )
        except Exception:
            pass

        return

    # ---------------------
    # SAVE MODE
    # ---------------------

    if data.startswith("save:"):

        title_id = int(
            data.split(":")[1]
        )

        title = get_title(
            title_id
        )

        if not title:
            return

        states[chat_id] = {
            "mode": "save",
            "title_id": title_id
        }

        kb = types.InlineKeyboardMarkup()

        kb.add(
            types.InlineKeyboardButton(
                "✅ اتمام ذخیره",
                callback_data=f"finish:{title_id}"
            )
        )

        try:
            bot.edit_message_text(
                f"📥 <b>حالت ذخیره فعال شد</b>\n\n"
                f"📁 عنوان: <b>{title['name']}</b>\n\n"
                "هر چیزی بفرستی یا Forward کنی "
                "خودکار تشخیص داده می‌شود.\n\n"
                "🖼 عکس\n"
                "🎬 فیلم\n"
                "📝 متن\n"
                "🎭 استیکر\n"
                "🎞 GIF\n"
                "🔗 لینک",
                chat_id,
                message_id,
                reply_markup=kb
            )
        except Exception:
            pass

        return

    # ---------------------
    # FINISH SAVE
    # ---------------------

    if data.startswith("finish:"):

        title_id = int(
            data.split(":")[1]
        )

        states.pop(
            chat_id,
            None
        )

        clear_session(
            chat_id
        )

        title = get_title(
            title_id
        )

        if title:

            msg = bot.send_message(
                chat_id,
                f"✅ <b>ذخیره تمام شد</b>\n\n"
                f"📁 {title['name']}",
                reply_markup=title_keyboard(
                    title_id
                )
            )

            remember(
                chat_id,
                msg.message_id
            )

        return

    # ---------------------
    # CATEGORY
    # ---------------------

    if data.startswith("cat:"):

        parts = data.split(":")

        title_id = int(
            parts[1]
        )

        item_type = parts[2]

        title = get_title(
            title_id
        )

        if not title:
            return

        names = {
            "photo": "🖼 عکس",
            "video": "🎬 فیلم",
            "text": "📝 متن",
            "sticker": "🎭 استیکر",
            "gif": "🎞 GIF",
            "link": "🔗 لینک"
        }

        count = get_count(
            title_id,
            item_type
        )

        kb = types.InlineKeyboardMarkup()

        if count > 0:

            kb.add(
                types.InlineKeyboardButton(
                    f"📤 ارسال {names[item_type]}ها",
                    callback_data=f"send:{title_id}:{item_type}"
                )
            )

            kb.add(
                types.InlineKeyboardButton(
                    "🧹 پاکسازی لیست",
                    callback_data=f"clear:{title_id}:{item_type}"
                )
            )

        kb.add(
            types.InlineKeyboardButton(
                "🔙 برگشت",
                callback_data=f"title:{title_id}"
            )
        )

        try:
            bot.edit_message_text(
                f"📁 <b>{title['name']}</b>\n\n"
                f"{names[item_type]}\n\n"
                f"📊 تعداد: <b>{count}</b>",
                chat_id,
                message_id,
                reply_markup=kb
            )
        except Exception:
            pass

        return

    # ---------------------
    # CLEAR CONFIRM
    # ---------------------

    if data.startswith("clear:"):

        parts = data.split(":")

        title_id = int(
            parts[1]
        )

        item_type = parts[2]

        kb = types.InlineKeyboardMarkup(
            row_width=2
        )

        kb.add(
            types.InlineKeyboardButton(
                "❌ خیر",
                callback_data=f"cat:{title_id}:{item_type}"
            ),
            types.InlineKeyboardButton(
                "⚠️ بله، حذف کن",
                callback_data=f"confirm:{title_id}:{item_type}"
            )
        )

        try:
            bot.edit_message_text(
                "⚠️ <b>مطمئنی؟</b>\n\n"
                "تمام موارد این بخش از آرشیو حذف "
                "می‌شوند.\n\n"
                "این عملیات قابل برگشت نیست.",
                chat_id,
                message_id,
                reply_markup=kb
            )
        except Exception:
            pass

        return

    # ---------------------
    # CONFIRM DELETE
    # ---------------------

    if data.startswith("confirm:"):

        parts = data.split(":")

        title_id = int(
            parts[1]
        )

        item_type = parts[2]

        delete_category(
            title_id,
            item_type
        )

        kb = types.InlineKeyboardMarkup()

        kb.add(
            types.InlineKeyboardButton(
                "🔙 برگشت",
                callback_data=f"title:{title_id}"
            )
        )

        try:
            bot.edit_message_text(
                "✅ <b>پاک شد.</b>\n\n"
                "موارد این بخش از آرشیو حذف شدند.",
                chat_id,
                message_id,
                reply_markup=kb
            )
        except Exception:
            pass

        return

    # ---------------------
    # SEND
    # ---------------------

    if data.startswith("send:"):

        parts = data.split(":")

        title_id = int(
            parts[1]
        )

        item_type = parts[2]

        threading.Thread(
            target=send_worker,
            args=(
                chat_id,
                title_id,
                item_type
            ),
            daemon=True
        ).start()

        return
        # =========================
# SEND WORKER
# =========================

def send_worker(
    chat_id,
    title_id,
    item_type
):

    items = get_items(
        title_id,
        item_type
    )

    if not items:

        msg = bot.send_message(
            chat_id,
            "❌ این بخش خالی است."
        )

        remember(
            chat_id,
            msg.message_id
        )

        return

    title = get_title(
        title_id
    )

    sent_ids = []

    for item in items:

        try:

            sent = None

            if item_type == "photo":

                sent = bot.send_photo(
                    chat_id,
                    item["file_id"]
                )

            elif item_type == "video":

                sent = bot.send_video(
                    chat_id,
                    item["file_id"]
                )

            elif item_type == "gif":

                sent = bot.send_animation(
                    chat_id,
                    item["file_id"]
                )

            elif item_type == "sticker":

                sent = bot.send_sticker(
                    chat_id,
                    item["file_id"]
                )

            elif item_type in (
                "text",
                "link"
            ):

                sent = bot.send_message(
                    chat_id,
                    item["content"]
                )

            if sent:

                sent_ids.append(
                    sent.message_id
                )

            time.sleep(3)

        except Exception as e:

            try:

                err = bot.send_message(
                    chat_id,
                    "⚠️ خطا در ارسال یک مورد."
                )

                sent_ids.append(
                    err.message_id
                )

            except Exception:
                pass

    # ذخیره پیام‌های همین ارسال
    sent_messages[chat_id] = set(
        sent_ids
    )

    kb = types.InlineKeyboardMarkup()

    kb.add(
        types.InlineKeyboardButton(
            "🗑 حذف از چت",
            callback_data=(
                f"deletechat:"
                f"{title_id}:"
                f"{item_type}"
            )
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "🔙 برگشت",
            callback_data=(
                f"cat:"
                f"{title_id}:"
                f"{item_type}"
            )
        )
    )

    msg = bot.send_message(
        chat_id,
        f"✅ <b>ارسال کامل شد</b>\n\n"
        f"📁 {title['name']}\n"
        f"📦 تعداد: {len(sent_ids)}\n\n"
        "آرشیو اصلی حذف نشده است.",
        reply_markup=kb
    )

    # پنل هم در لیست پیام‌های قابل حذف باشد
    sent_messages[chat_id].add(
        msg.message_id
    )


# =========================
# DELETE SENT MESSAGES
# =========================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith("deletechat:")
)
def delete_chat(call):

    if call.from_user.id != ADMIN_ID:
        return

    chat_id = call.message.chat.id

    bot.answer_callback_query(
        call.id,
        "در حال حذف پیام‌ها..."
    )

    ids = list(
        sent_messages.get(
            chat_id,
            set()
        )
    )

    for message_id in ids:

        delete_message(
            chat_id,
            message_id
        )

    sent_messages.pop(
        chat_id,
        None
    )


# =========================
# RECEIVE CONTENT
# =========================

@bot.message_handler(
    content_types=[
        "text",
        "photo",
        "video",
        "animation",
        "sticker"
    ]
)
def receive(message):

    if not allowed(message):
        return

    chat_id = message.chat.id

    state = states.get(
        chat_id
    )

    if not state:
        return

    # =====================
    # CREATE TITLE
    # =====================

    if state.get("mode") == "new_title":

        if message.content_type != "text":

            msg = bot.send_message(
                chat_id,
                "❌ فقط اسم عنوان را به صورت متن بفرست."
            )

            remember(
                chat_id,
                msg.message_id
            )

            return

        name = message.text.strip()

        if not name:
            return

        if len(name) > 60:

            msg = bot.send_message(
                chat_id,
                "❌ عنوان نباید بیشتر از ۶۰ کاراکتر باشد."
            )

            remember(
                chat_id,
                msg.message_id
            )

            return

        title_id = create_title(
            name
        )

        states.pop(
            chat_id,
            None
        )

        remember(
            chat_id,
            message.message_id
        )

        msg = bot.send_message(
            chat_id,
            f"✅ <b>عنوان ساخته شد</b>\n\n"
            f"📁 {name}",
            reply_markup=title_keyboard(
                title_id
            )
        )

        remember(
            chat_id,
            msg.message_id
        )

        return

    # =====================
    # SAVE CONTENT
    # =====================

    if state.get("mode") == "save":

        title_id = state.get(
            "title_id"
        )

        title = get_title(
            title_id
        )

        if not title:
            states.pop(
                chat_id,
                None
            )
            return

        item_type, file_id, content = detect(
            message
        )

        if not item_type:

            msg = bot.send_message(
                chat_id,
                "❌ این نوع محتوا پشتیبانی نمی‌شود."
            )

            remember(
                chat_id,
                message.message_id
            )

            remember(
                chat_id,
                msg.message_id
            )

            return

        # =================
        # SAVE TO DATABASE
        # =================

        save_item(
            title_id=title_id,
            item_type=item_type,
            file_id=file_id,
            content=content
        )

        # پیام ورودی و پیام تأیید
        # بعداً با اتمام ذخیره پاک می‌شوند
        remember(
            chat_id,
            message.message_id
        )

        names = {
            "photo": "🖼 عکس",
            "video": "🎬 فیلم",
            "text": "📝 متن",
            "sticker": "🎭 استیکر",
            "gif": "🎞 GIF",
            "link": "🔗 لینک"
        }

        count = get_count(
            title_id,
            item_type
        )

        kb = types.InlineKeyboardMarkup()

        kb.add(
            types.InlineKeyboardButton(
                "✅ اتمام ذخیره",
                callback_data=(
                    f"finish:{title_id}"
                )
            )
        )

        msg = bot.send_message(
            chat_id,
            f"✅ {names[item_type]} ذخیره شد\n\n"
            f"📁 {title['name']}\n"
            f"📊 تعداد این بخش: {count}",
            reply_markup=kb
        )

        remember(
            chat_id,
            msg.message_id
        )

        return


# =========================
# UNSUPPORTED FILES
# =========================

@bot.message_handler(
    content_types=[
        "document",
        "audio",
        "voice",
        "contact",
        "location"
    ]
)
def unsupported(message):

    if not allowed(message):
        return

    state = states.get(
        message.chat.id
    )

    if not state:
        return

    if state.get("mode") != "save":
        return

    remember(
        message.chat.id,
        message.message_id
    )

    msg = bot.send_message(
        message.chat.id,
        "⚠️ این نوع فایل فعلاً پشتیبانی نمی‌شود.\n\n"
        "پشتیبانی:\n"
        "🖼 عکس\n"
        "🎬 فیلم\n"
        "📝 متن\n"
        "🎭 استیکر\n"
        "🎞 GIF\n"
        "🔗 لینک"
    )

    remember(
        message.chat.id,
        msg.message_id
    )


# =========================
# RUN
# =========================

print(
    "=============================="
)

print(
    "Personal Archive Bot Started"
)

print(
    "=============================="
)

bot.infinity_polling(
    skip_pending=True
    )
