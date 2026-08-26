import telebot
from telebot import types
import sqlite3
import time
import re
import threading

# =========================================================
# تنظیمات
# =========================================================

BOT_TOKEN = "8597049833:AAFnEjGLcOz09Duy6MIvOoMD9TA1-fiRhPE"
ADMIN_ID = 7781305425

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

DB_NAME = "archive.db"

# وضعیت فعلی بات برای ادمین
states = {}

# پیام‌هایی که در عملیات فعلی باید قابل پاکسازی باشند
session_messages = {}

# پیام‌های ارسال‌شده در آخرین عملیات ارسال
last_sent_messages = {}

# قفل دیتابیس
db_lock = threading.Lock()


# =========================================================
# DATABASE
# =========================================================

def connect():
    con = sqlite3.connect(
        DB_NAME,
        timeout=30,
        check_same_thread=False
    )

    con.row_factory = sqlite3.Row

    return con


def init_db():

    with db_lock:

        con = connect()

        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")

        con.execute("""
            CREATE TABLE IF NOT EXISTS titles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)

        con.execute("""
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

        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_items_title
            ON items(user_id, title_id, item_type)
        """)

        con.commit()
        con.close()


init_db()


# =========================================================
# SECURITY
# =========================================================

def allowed(message):

    return (
        message.from_user is not None
        and message.from_user.id == ADMIN_ID
        and message.chat.type == "private"
    )


def allowed_call(call):

    return (
        call.from_user is not None
        and call.from_user.id == ADMIN_ID
    )


# =========================================================
# DATABASE - TITLES
# =========================================================

def create_title(name):

    with db_lock:

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


# =========================================================
# DATABASE - ITEMS
# =========================================================

def save_item(
    title_id,
    item_type,
    file_id=None,
    content=None
):

    with db_lock:

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

    with db_lock:

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


# =========================================================
# CONTENT DETECTION
# =========================================================

URL_PATTERN = re.compile(
    r"(https?://\S+|www\.\S+)",
    re.IGNORECASE
)


def detect_content(message):

    # عکس
    if message.content_type == "photo":

        return (
            "photo",
            message.photo[-1].file_id,
            None
        )

    # فیلم
    if message.content_type == "video":

        return (
            "video",
            message.video.file_id,
            None
        )

    # GIF / Animation
    if message.content_type == "animation":

        return (
            "gif",
            message.animation.file_id,
            None
        )

    # استیکر
    if message.content_type == "sticker":

        return (
            "sticker",
            message.sticker.file_id,
            None
        )

    # متن و لینک
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


# =========================================================
# MESSAGE MEMORY
# =========================================================

def remember_session(
    chat_id,
    message_id
):

    session_messages.setdefault(
        chat_id,
        set()
    )

    session_messages[chat_id].add(
        message_id
    )


def safe_delete(
    chat_id,
    message_id
):

    try:

        bot.delete_message(
            chat_id,
            message_id
        )

    except Exception:

        pass


def clear_session(chat_id):

    ids = list(
        session_messages.get(
            chat_id,
            set()
        )
    )

    for message_id in ids:

        safe_delete(
            chat_id,
            message_id
        )

    session_messages.pop(
        chat_id,
        None
    )


# =========================================================
# KEYBOARDS
# =========================================================

def home_keyboard():

    kb = types.InlineKeyboardMarkup(
        row_width=1
    )

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
    # =========================================================
# START
# =========================================================

@bot.message_handler(
    commands=["start"]
)
def start(message):

    if not allowed(message):
        return

    chat_id = message.chat.id

    states.pop(
        chat_id,
        None
    )

    session_messages.pop(
        chat_id,
        None
    )

    last_sent_messages.pop(
        chat_id,
        None
    )

    msg = bot.send_message(
        chat_id,
        "🗄 <b>آرشیو شخصی</b>\n\n"
        "آرشیو خودت را مدیریت کن.",
        reply_markup=home_keyboard()
    )

    remember_session(
        chat_id,
        msg.message_id
    )


# =========================================================
# SHOW TITLES
# =========================================================

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
            "هنوز هیچ عنوانی ساخته نشده."
        )

    else:

        text = (
            "📂 <b>عنوان‌های من</b>\n\n"
            "عنوان موردنظر را انتخاب کن:"
        )

        for row in rows:

            title_id = row["id"]

            total = 0

            for item_type in (
                "photo",
                "video",
                "text",
                "sticker",
                "gif",
                "link"
            ):

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

    if message_id is not None:

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

        remember_session(
            chat_id,
            msg.message_id
        )


# =========================================================
# CALLBACK HANDLER
# =========================================================

@bot.callback_query_handler(
    func=lambda call: True
)
def callbacks(call):

    if not allowed_call(call):

        bot.answer_callback_query(
            call.id
        )

        return

    chat_id = call.message.chat.id
    message_id = call.message.message_id
    data = call.data

    bot.answer_callback_query(
        call.id
    )

    # =====================================================
    # HOME
    # =====================================================

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

    # =====================================================
    # TITLES
    # =====================================================

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

    # =====================================================
    # NEW TITLE
    # =====================================================

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
                "اسم عنوان را بفرست.\n\n"
                "مثال:\n"
                "<code>وطنی</code>",
                chat_id,
                message_id,
                reply_markup=kb
            )

        except Exception:

            pass

        return

    # =====================================================
    # OPEN TITLE
    # =====================================================

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
            "بخش موردنظر را انتخاب کن:"
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

    # =====================================================
    # SAVE MODE
    # =====================================================

    if data.startswith("save:"):

        title_id = int(
            data.split(":")[1]
        )

        title = get_title(
            title_id
        )

        if not title:
            return

        # حالت ذخیره
        states[chat_id] = {
            "mode": "save",
            "title_id": title_id,
            "saved": {
                "photo": 0,
                "video": 0,
                "text": 0,
                "sticker": 0,
                "gif": 0,
                "link": 0
            }
        }

        # پیام‌های قبلی جلسه ذخیره پاک می‌شوند
        session_messages[chat_id] = set()

        kb = types.InlineKeyboardMarkup()

        kb.add(
            types.InlineKeyboardButton(
                "✅ اتمام ذخیره",
                callback_data=f"finish:{title_id}"
            )
        )

        try:

            bot.edit_message_text(
                "📥 <b>حالت ذخیره فعال شد</b>\n\n"
                f"📁 مقصد: <b>{title['name']}</b>\n\n"
                "حالا هر تعداد عکس، فیلم، متن، "
                "استیکر، GIF یا لینک خواستی بفرست "
                "یا از کانال/ربات Forward کن.\n\n"
                "⚡ همه خودکار تشخیص داده و ذخیره می‌شوند.\n\n"
                "برای پایان روی دکمه زیر بزن.",
                chat_id,
                message_id,
                reply_markup=kb
            )

        except Exception:

            pass

        return

    # =====================================================
    # FINISH SAVE
    # =====================================================

    if data.startswith("finish:"):

        title_id = int(
            data.split(":")[1]
        )

        state = states.get(
            chat_id
        )

        # اگر حالت ذخیره وجود داشته باشد
        stats = None

        if state:

            stats = state.get(
                "saved"
            )

        states.pop(
            chat_id,
            None
        )

        # پاک کردن پیام‌های جلسه
        clear_session(
            chat_id
        )

        title = get_title(
            title_id
        )

        if not title:
            return

        if stats is None:

            stats = {
                "photo": 0,
                "video": 0,
                "text": 0,
                "sticker": 0,
                "gif": 0,
                "link": 0
            }

        msg = bot.send_message(
            chat_id,
            f"✅ <b>ذخیره تمام شد</b>\n\n"
            f"📁 <b>{title['name']}</b>\n\n"
            f"🖼 عکس جدید: {stats['photo']}\n"
            f"🎬 فیلم جدید: {stats['video']}\n"
            f"📝 متن جدید: {stats['text']}\n"
            f"🎭 استیکر جدید: {stats['sticker']}\n"
            f"🎞 GIF جدید: {stats['gif']}\n"
            f"🔗 لینک جدید: {stats['link']}",
            reply_markup=title_keyboard(
                title_id
            )
        )

        remember_session(
            chat_id,
            msg.message_id
        )

        return

    # =====================================================
    # CATEGORY
    # =====================================================

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

    # =====================================================
    # CLEAR CONFIRM
    # =====================================================

    if data.startswith("clear:"):

        parts = data.split(":")

        title_id = int(
            parts[1]
        )

        item_type = parts[2]

        names = {
            "photo": "عکس",
            "video": "فیلم",
            "text": "متن",
            "sticker": "استیکر",
            "gif": "GIF",
            "link": "لینک"
        }

        count = get_count(
            title_id,
            item_type
        )

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
                f"⚠️ <b>مطمئنی؟</b>\n\n"
                f"قرار است {count} مورد از بخش "
                f"<b>{names[item_type]}</b> حذف شود.\n\n"
                "این عملیات از آرشیو حذف می‌کند "
                "و قابل برگشت نیست.",
                chat_id,
                message_id,
                reply_markup=kb
            )

        except Exception:

            pass

        return
        # =========================================================
# CONFIRM DELETE
# =========================================================

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
                "🔙 برگشت به عنوان",
                callback_data=f"title:{title_id}"
            )
        )

        try:

            bot.edit_message_text(
                "✅ <b>پاکسازی انجام شد.</b>\n\n"
                "موارد این بخش از آرشیو حذف شدند.",
                chat_id,
                message_id,
                reply_markup=kb
            )

        except Exception:

            pass

        return

    # =====================================================
    # SEND
    # =====================================================

    if data.startswith("send:"):

        parts = data.split(":")

        title_id = int(
            parts[1]
        )

        item_type = parts[2]

        # هر ارسال جدید، لیست پیام‌های قبلی را جدا می‌کند
        last_sent_messages[chat_id] = []

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

    # =====================================================
    # DELETE SENT FROM CHAT
    # =====================================================

    if data.startswith("deletechat:"):

        ids = list(
            last_sent_messages.get(
                chat_id,
                []
            )
        )

        bot.answer_callback_query(
            call.id,
            "در حال پاک کردن پیام‌ها..."
        )

        # اول پیام‌های محتوا
        for sent_id in ids:

            safe_delete(
                chat_id,
                sent_id
            )

        # سپس پنل
        safe_delete(
            chat_id,
            message_id
        )

        last_sent_messages.pop(
            chat_id,
            None
        )

        return


# =========================================================
# SEND WORKER
# =========================================================

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

        remember_session(
            chat_id,
            msg.message_id
        )

        return

    title = get_title(
        title_id
    )

    if not title:
        return

    sent_ids = []

    # ارسال بدون ذخیره مجدد
    for index, item in enumerate(items):

        try:

            sent = None

            # -----------------------------
            # PHOTO
            # -----------------------------

            if item_type == "photo":

                sent = bot.send_photo(
                    chat_id,
                    item["file_id"]
                )

            # -----------------------------
            # VIDEO
            # -----------------------------

            elif item_type == "video":

                sent = bot.send_video(
                    chat_id,
                    item["file_id"]
                )

            # -----------------------------
            # GIF
            # -----------------------------

            elif item_type == "gif":

                sent = bot.send_animation(
                    chat_id,
                    item["file_id"]
                )

            # -----------------------------
            # STICKER
            # -----------------------------

            elif item_type == "sticker":

                sent = bot.send_sticker(
                    chat_id,
                    item["file_id"]
                )

            # -----------------------------
            # TEXT / LINK
            # -----------------------------

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

        except Exception as e:

            print(
                "SEND ERROR:",
                e
            )

        # فاصله سه ثانیه
        # به جز بعد از آخرین مورد
        if index < len(items) - 1:

            time.sleep(3)

    # ذخیره شناسه پیام‌های همین ارسال
    last_sent_messages[chat_id] = sent_ids

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
        f"📦 تعداد ارسال‌شده: <b>{len(sent_ids)}</b>\n\n"
        "آرشیو اصلی دست‌نخورده باقی مانده.",
        reply_markup=kb
    )

    # پنل را هم برای حذف از چت نگه می‌داریم
    last_sent_messages[chat_id] = sent_ids


# =========================================================
# RECEIVE CONTENT
# =========================================================

@bot.message_handler(
    content_types=[
        "text",
        "photo",
        "video",
        "animation",
        "sticker"
    ]
)
def receive_content(message):

    if not allowed(message):
        return

    chat_id = message.chat.id

    state = states.get(
        chat_id
    )

    if not state:
        return

    # =====================================================
    # CREATE TITLE
    # =====================================================

    if state.get("mode") == "new_title":

        if message.content_type != "text":

            msg = bot.send_message(
                chat_id,
                "❌ اسم عنوان را به صورت متن بفرست."
            )

            remember_session(
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
                "❌ عنوان حداکثر ۶۰ کاراکتر باشد."
            )

            remember_session(
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

        remember_session(
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

        remember_session(
            chat_id,
            msg.message_id
        )

        return

    # =====================================================
    # SAVE CONTENT
    # =====================================================

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

        item_type, file_id, content = detect_content(
            message
        )

        # اگر نوع پشتیبانی نشود
        if not item_type:

            remember_session(
                chat_id,
                message.message_id
            )

            return

        # =================================================
        # ذخیره فوری
        # =================================================

        try:

            save_item(
                title_id=title_id,
                item_type=item_type,
                file_id=file_id,
                content=content
            )

            # آمار لحظه‌ای را فقط داخل حافظه زیاد می‌کنیم
            state["saved"][item_type] += 1

            # پیام ورودی ذخیره می‌شود تا اتمام عملیات پاک شود
            remember_session(
                chat_id,
                message.message_id
            )

            print(
                "SAVED:",
                item_type,
                "=>",
                title["name"]
            )

        except Exception as e:

            print(
                "SAVE ERROR:",
                e
            )

        # =================================================
        # مهم:
        # هیچ پیام تأییدی برای هر فایل ارسال نمی‌شود.
        #
        # بنابراین اگر 20 فیلم Forward شود:
        #
        # فیلم 1 -> ذخیره
        # فیلم 2 -> ذخیره
        # فیلم 3 -> ذخیره
        # ...
        # فیلم 20 -> ذخیره
        #
        # بدون 20 پیام اضافی.
        # =================================================

        return


# =========================================================
# UNSUPPORTED FILES
# =========================================================

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

    # فعلاً این نوع فایل‌ها ذخیره نمی‌شوند
    remember_session(
        message.chat.id,
        message.message_id
    )

    print(
        "UNSUPPORTED:",
        message.content_type
    )


# =========================================================
# ERROR / LOG
# =========================================================

print(
    "================================="
)

print(
    "Personal Archive Bot"
)

print(
    "Bot is running..."
)

print(
    "================================="
)


# =========================================================
# RUN
# =========================================================

bot.infinity_polling(
    skip_pending=True,
    timeout=30,
    long_polling_timeout=30
        )
