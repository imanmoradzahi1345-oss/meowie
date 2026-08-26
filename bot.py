import telebot
from telebot import types
import sqlite3
import time
import threading

# =========================
# CONFIG
# =========================

BOT_TOKEN = "8636563885:AAH-Ihpb7-Ql9MwD1lZ824rwu1sdb3uUH8o"

DB_NAME = "sender_bot.db"

# محدودیت ایمن ارسال
MAX_MESSAGES = 20
MIN_DELAY = 10

bot = telebot.TeleBot(
    BOT_TOKEN,
    parse_mode="HTML",
    threaded=True
)

DB_LOCK = threading.Lock()

# وضعیت عملیات کاربران
user_states = {}

# عملیات ارسال فعال
active_jobs = {}

# محتوای موقت
pending_content = {}


# =========================
# DATABASE
# =========================

def db():
    con = sqlite3.connect(
        DB_NAME,
        timeout=30,
        check_same_thread=False
    )
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with DB_LOCK:
        con = db()

        con.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY,
            title TEXT,
            username TEXT,
            added_at INTEGER
        )
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            state TEXT DEFAULT '',
            selected_chat INTEGER
        )
        """)

        con.commit()
        con.close()


def save_user(user_id, state="", selected_chat=None):
    with DB_LOCK:
        con = db()

        con.execute("""
        INSERT INTO users
        (user_id, state, selected_chat)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            state=excluded.state,
            selected_chat=excluded.selected_chat
        """, (
            user_id,
            state,
            selected_chat
        ))

        con.commit()
        con.close()


def get_user(user_id):
    con = db()

    row = con.execute("""
    SELECT *
    FROM users
    WHERE user_id=?
    """, (user_id,)).fetchone()

    con.close()

    return row


def add_chat(chat):
    with DB_LOCK:
        con = db()

        con.execute("""
        INSERT INTO chats
        (chat_id, title, username, added_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(chat_id)
        DO UPDATE SET
            title=excluded.title,
            username=excluded.username
        """, (
            chat.id,
            chat.title or "",
            getattr(chat, "username", "") or "",
            int(time.time())
        ))

        con.commit()
        con.close()


def remove_chat(chat_id):
    with DB_LOCK:
        con = db()

        con.execute("""
        DELETE FROM chats
        WHERE chat_id=?
        """, (chat_id,))

        con.commit()
        con.close()


def get_chats():
    con = db()

    rows = con.execute("""
    SELECT *
    FROM chats
    ORDER BY added_at DESC
    """).fetchall()

    con.close()

    return rows


def get_chat(chat_id):
    con = db()

    row = con.execute("""
    SELECT *
    FROM chats
    WHERE chat_id=?
    """, (chat_id,)).fetchone()

    con.close()

    return row


init_db()


# =========================
# KEYBOARDS
# =========================

def main_keyboard():
    kb = types.InlineKeyboardMarkup(
        row_width=2
    )

    kb.add(
        types.InlineKeyboardButton(
            "➕ افزودن گپ",
            callback_data="add_chat"
        ),
        types.InlineKeyboardButton(
            "📋 گپ‌های من",
            callback_data="chat_list"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "📤 ارسال",
            callback_data="send_menu"
        )
    )

    return kb


def back_button():
    kb = types.InlineKeyboardMarkup()

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

@bot.message_handler(
    commands=["start"]
)
def start(message):

    if message.chat.type != "private":
        return

    save_user(
        message.from_user.id,
        ""
    )

    text = (
        "🤖 <b>Content Sender</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "📤 ارسال محتوای انتخابی به گپ\n\n"
        "ابتدا بات را داخل گپ اضافه کن "
        "و داخل همان گپ دستور زیر را بفرست:\n\n"
        "<code>/register</code>\n\n"
        "بعد از ثبت، گپ در پنل پیوی نمایش داده می‌شود."
    )

    bot.send_message(
        message.chat.id,
        text,
        reply_markup=main_keyboard()
    )


# =========================
# REGISTER CHAT
# =========================

@bot.message_handler(
    commands=["register"]
)
def register(message):

    if message.chat.type not in (
        "group",
        "supergroup"
    ):
        bot.reply_to(
            message,
            "❌ این دستور باید داخل گپ اجرا شود."
        )
        return

    # بات باید امکان ارسال پیام داشته باشد
    try:
        me = bot.get_me()

        member = bot.get_chat_member(
            message.chat.id,
            me.id
        )

        if member.status == "kicked":
            return

    except Exception as e:
        bot.reply_to(
            message,
            "❌ نتوانستم وضعیت عضویت خودم را بررسی کنم."
        )
        print(e)
        return

    add_chat(message.chat)

    bot.reply_to(
        message,
        "✅ <b>گپ با موفقیت ثبت شد.</b>\n\n"
        f"📌 نام: <b>{message.chat.title}</b>\n"
        f"🆔 <code>{message.chat.id}</code>\n\n"
        "حالا به پیوی من برو و بخش "
        "📤 ارسال را انتخاب کن."
    )


# =========================
# HOME CALLBACK
# =========================

@bot.callback_query_handler(
    func=lambda c: c.data == "home"
)
def home_callback(call):

    bot.edit_message_text(
        "🤖 <b>پنل اصلی</b>\n\n"
        "یک گزینه را انتخاب کن:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=main_keyboard()
    )

    bot.answer_callback_query(call.id)


# =========================
# CHAT LIST
# =========================

@bot.callback_query_handler(
    func=lambda c: c.data == "chat_list"
)
def chat_list(call):

    if call.message.chat.type != "private":
        return

    chats = get_chats()

    if not chats:
        bot.edit_message_text(
            "📋 <b>گپی ثبت نشده.</b>\n\n"
            "بات را داخل گپ اضافه کن و "
            "<code>/register</code> را بفرست.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=back_button()
        )

        bot.answer_callback_query(call.id)
        return

    kb = types.InlineKeyboardMarkup(
        row_width=1
    )

    for chat in chats:

        title = chat["title"] or "بدون نام"

        kb.add(
            types.InlineKeyboardButton(
                f"💬 {title}",
                callback_data=f"chat:{chat['chat_id']}"
            )
        )

    kb.add(
        types.InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="home"
        )
    )

    bot.edit_message_text(
        "📋 <b>گپ‌های ثبت‌شده</b>\n\n"
        "برای مدیریت یک گپ روی آن بزن:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=kb
    )

    bot.answer_callback_query(call.id)


# =========================
# CHAT DETAILS
# =========================

@bot.callback_query_handler(
    func=lambda c: c.data.startswith("chat:")
)
def chat_details(call):

    try:
        chat_id = int(
            call.data.split(":", 1)[1]
        )
    except Exception:
        return

    chat = get_chat(chat_id)

    if not chat:
        bot.answer_callback_query(
            call.id,
            "گپ پیدا نشد.",
            show_alert=True
        )
        return

    title = chat["title"] or "بدون نام"

    kb = types.InlineKeyboardMarkup(
        row_width=1
    )

    kb.add(
        types.InlineKeyboardButton(
            "📤 ارسال محتوا",
            callback_data=f"send:{chat_id}"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "🗑 حذف از لیست",
            callback_data=f"remove:{chat_id}"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "🔙 گپ‌ها",
            callback_data="chat_list"
        )
    )

    bot.edit_message_text(
        "💬 <b>مدیریت گپ</b>\n\n"
        f"📌 نام: <b>{title}</b>\n"
        f"🆔 <code>{chat_id}</code>\n\n"
        "چه کاری انجام شود؟",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=kb
    )

    bot.answer_callback_query(call.id)


# =========================
# REMOVE CHAT
# =========================

@bot.callback_query_handler(
    func=lambda c: c.data.startswith("remove:")
)
def remove_chat_callback(call):

    try:
        chat_id = int(
            call.data.split(":", 1)[1]
        )
    except Exception:
        return

    kb = types.InlineKeyboardMarkup(
        row_width=2
    )

    kb.add(
        types.InlineKeyboardButton(
            "✅ بله",
            callback_data=f"remove_yes:{chat_id}"
        ),
        types.InlineKeyboardButton(
            "❌ خیر",
            callback_data=f"chat:{chat_id}"
        )
    )

    bot.edit_message_text(
        "⚠️ <b>مطمئنی؟</b>\n\n"
        "گپ فقط از لیست ربات حذف می‌شود "
        "و از خود گپ خارج نمی‌شود.",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=kb
    )

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(
    func=lambda c:
    c.data.startswith("remove_yes:")
)
def remove_yes(call):

    try:
        chat_id = int(
            call.data.split(":", 1)[1]
        )
    except Exception:
        return

    remove_chat(chat_id)

    bot.answer_callback_query(
        call.id,
        "🗑 گپ حذف شد."
    )

    chats = get_chats()

    if not chats:
        bot.edit_message_text(
            "📋 لیست گپ‌ها خالی است.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=back_button()
        )
        return

    chat_list(call)


# =========================
# SEND MENU
# =========================

@bot.callback_query_handler(
    func=lambda c: c.data == "send_menu"
)
def send_menu(call):

    chats = get_chats()

    if not chats:
        bot.answer_callback_query(
            call.id,
            "اول یک گپ ثبت کن.",
            show_alert=True
        )
        return

    kb = types.InlineKeyboardMarkup(
        row_width=1
    )

    for chat in chats:

        title = chat["title"] or "بدون نام"

        kb.add(
            types.InlineKeyboardButton(
                f"📤 {title}",
                callback_data=f"send:{chat['chat_id']}"
            )
        )

    kb.add(
        types.InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="home"
        )
    )

    bot.edit_message_text(
        "📤 <b>انتخاب گپ</b>\n\n"
        "محتوا در کدام گپ ارسال شود؟",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=kb
    )

    bot.answer_callback_query(call.id)


# =========================
# SEND CONTENT
# =========================

@bot.callback_query_handler(
    func=lambda c: c.data.startswith("send:")
)
def send_start(call):

    try:
        chat_id = int(
            call.data.split(":", 1)[1]
        )
    except Exception:
        return

    chat = get_chat(chat_id)

    if not chat:
        bot.answer_callback_query(
            call.id,
            "گپ پیدا نشد.",
            show_alert=True
        )
        return

    user_id = call.from_user.id

    user_states[user_id] = {
        "state": "waiting_content",
        "chat_id": chat_id
    }

    bot.edit_message_text(
        "📨 <b>محتوا را ارسال کن</b>\n\n"
        "می‌توانی یکی از این موارد را بفرستی:\n"
        "📝 متن\n"
        "🖼 عکس\n"
        "🎬 فیلم\n"
        "🎞 GIF\n"
        "🎭 استیکر\n\n"
        "بعد از دریافت، ربات ازت تأیید می‌گیرد.",
        call.message.chat.id,
        call.message.message_id
    )

    bot.answer_callback_query(call.id)


# =========================
# CONTENT HANDLER
# =========================

@bot.message_handler(
    func=lambda m:
    m.chat.type == "private",
    content_types=[
        "text",
        "photo",
        "video",
        "animation",
        "sticker"
    ]
)
def receive_content(message):

    user_id = message.from_user.id

    state = user_states.get(
        user_id
    )

    if not state:
        return

    if state.get("state") != "waiting_content":
        return

    if message.content_type == "text":

        if message.text.startswith("/"):
            return

        content = {
            "type": "text",
            "text": message.text
        }

    elif message.content_type == "photo":

        content = {
            "type": "photo",
            "file_id": message.photo[-1].file_id,
            "caption": message.caption or ""
        }

    elif message.content_type == "video":

        content = {
            "type": "video",
            "file_id": message.video.file_id,
            "caption": message.caption or ""
        }

    elif message.content_type == "animation":

        content = {
            "type": "animation",
            "file_id": message.animation.file_id,
            "caption": message.caption or ""
        }

    elif message.content_type == "sticker":

        content = {
            "type": "sticker",
            "file_id": message.sticker.file_id
        }

    else:
        return

    pending_content[user_id] = content

    kb = types.InlineKeyboardMarkup(
        row_width=2
    )

    kb.add(
        types.InlineKeyboardButton(
            "✅ تأیید",
            callback_data="content_yes"
        ),
        types.InlineKeyboardButton(
            "❌ لغو",
            callback_data="content_no"
        )
    )

    bot.send_message(
        message.chat.id,
        "📦 <b>محتوا دریافت شد.</b>\n\n"
        "آیا همین محتوا ارسال شود؟",
        reply_markup=kb
    )
    # =========================
# CONTENT CONFIRMATION
# =========================

@bot.callback_query_handler(
    func=lambda c: c.data == "content_yes"
)
def content_yes(call):

    user_id = call.from_user.id

    state = user_states.get(user_id)
    content = pending_content.get(user_id)

    if not state or not content:
        bot.answer_callback_query(
            call.id,
            "❌ محتوایی وجود ندارد.",
            show_alert=True
        )
        return

    state["state"] = "waiting_count"

    bot.answer_callback_query(
        call.id,
        "✅ محتوا تأیید شد."
    )

    bot.send_message(
        call.message.chat.id,
        "🔢 <b>تعداد ارسال را وارد کن.</b>\n\n"
        "مثال:\n"
        "<code>10</code>"
    )


@bot.callback_query_handler(
    func=lambda c: c.data == "content_no"
)
def content_no(call):

    user_id = call.from_user.id

    user_states.pop(
        user_id,
        None
    )

    pending_content.pop(
        user_id,
        None
    )

    bot.answer_callback_query(
        call.id,
        "❌ لغو شد."
    )

    bot.send_message(
        call.message.chat.id,
        "❌ ارسال لغو شد.\n\n"
        "برای شروع دوباره از 📤 ارسال استفاده کن."
    )


# =========================
# COUNT
# =========================

@bot.message_handler(
    func=lambda m:
    m.chat.type == "private"
    and user_states.get(
        m.from_user.id,
        {}
    ).get("state") == "waiting_count"
)
def receive_count(message):

    user_id = message.from_user.id

    try:
        count = int(
            message.text.strip()
        )
    except Exception:
        bot.reply_to(
            message,
            "❌ فقط عدد وارد کن.\n"
            "مثال: <code>10</code>"
        )
        return

    if count < 1:
        bot.reply_to(
            message,
            "❌ تعداد باید حداقل 1 باشد."
        )
        return

    if count > MAX_MESSAGES:
        bot.reply_to(
            message,
            f"❌ حداکثر تعداد فعلی "
            f"<b>{MAX_MESSAGES}</b> است."
        )
        return

    state = user_states.get(user_id)

    if not state:
        return

    state["count"] = count
    state["state"] = "waiting_delay"

    bot.send_message(
        message.chat.id,
        "⏱ <b>فاصله بین ارسال‌ها را وارد کن.</b>\n\n"
        f"حداقل فاصله: <b>{MIN_DELAY} ثانیه</b>\n\n"
        "مثال:\n"
        "<code>10</code>"
    )


# =========================
# DELAY
# =========================

@bot.message_handler(
    func=lambda m:
    m.chat.type == "private"
    and user_states.get(
        m.from_user.id,
        {}
    ).get("state") == "waiting_delay"
)
def receive_delay(message):

    user_id = message.from_user.id

    try:
        delay = float(
            message.text.strip()
        )
    except Exception:
        bot.reply_to(
            message,
            "❌ فقط عدد وارد کن.\n"
            "مثال: <code>10</code>"
        )
        return

    if delay < MIN_DELAY:
        bot.reply_to(
            message,
            f"❌ فاصله نمی‌تواند کمتر از "
            f"<b>{MIN_DELAY} ثانیه</b> باشد."
        )
        return

    state = user_states.get(user_id)

    if not state:
        return

    content = pending_content.get(user_id)

    if not content:
        bot.reply_to(
            message,
            "❌ محتوا پیدا نشد. دوباره شروع کن."
        )

        user_states.pop(
            user_id,
            None
        )

        return

    state["delay"] = delay
    state["state"] = "ready"

    count = state["count"]
    chat_id = state["chat_id"]

    chat = get_chat(chat_id)

    title = (
        chat["title"]
        if chat
        else "گپ"
    )

    kb = types.InlineKeyboardMarkup(
        row_width=2
    )

    kb.add(
        types.InlineKeyboardButton(
            "🚀 شروع",
            callback_data="job_start"
        ),
        types.InlineKeyboardButton(
            "❌ لغو",
            callback_data="job_cancel"
        )
    )

    bot.send_message(
        message.chat.id,
        "📋 <b>خلاصه ارسال</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"💬 گپ: <b>{title}</b>\n"
        f"📦 نوع محتوا: <b>{content['type']}</b>\n"
        f"🔢 تعداد: <b>{count}</b>\n"
        f"⏱ فاصله: <b>{delay}</b> ثانیه\n\n"
        "برای شروع تأیید کن:",
        reply_markup=kb
    )


# =========================
# START JOB
# =========================

@bot.callback_query_handler(
    func=lambda c: c.data == "job_start"
)
def job_start(call):

    user_id = call.from_user.id

    state = user_states.get(user_id)
    content = pending_content.get(user_id)

    if not state or not content:
        bot.answer_callback_query(
            call.id,
            "❌ عملیات پیدا نشد.",
            show_alert=True
        )
        return

    if state.get("state") != "ready":
        bot.answer_callback_query(
            call.id,
            "❌ عملیات آماده نیست.",
            show_alert=True
        )
        return

    if user_id in active_jobs:
        bot.answer_callback_query(
            call.id,
            "⚠️ یک ارسال در حال اجرا داری.",
            show_alert=True
        )
        return

    chat_id = state["chat_id"]
    count = state["count"]
    delay = state["delay"]

    # بررسی وجود گپ
    chat = get_chat(chat_id)

    if not chat:
        bot.answer_callback_query(
            call.id,
            "❌ گپ دیگر ثبت نشده.",
            show_alert=True
        )
        return

    # بررسی اینکه بات هنوز می‌تواند پیام بفرستد
    try:
        me = bot.get_me()

        member = bot.get_chat_member(
            chat_id,
            me.id
        )

        if member.status in (
            "left",
            "kicked"
        ):
            bot.answer_callback_query(
                call.id,
                "❌ بات دیگر در گپ نیست.",
                show_alert=True
            )
            return

    except Exception as e:

        print(
            "Membership check:",
            e
        )

        bot.answer_callback_query(
            call.id,
            "❌ دسترسی ارسال در گپ بررسی نشد.",
            show_alert=True
        )

        return

    job = {
        "user_id": user_id,
        "chat_id": chat_id,
        "count": count,
        "delay": delay,
        "content": content,
        "stop": False,
        "sent": 0
    }

    active_jobs[user_id] = job

    user_states.pop(
        user_id,
        None
    )

    pending_content.pop(
        user_id,
        None
    )

    bot.answer_callback_query(
        call.id,
        "🚀 ارسال شروع شد."
    )

    kb = types.InlineKeyboardMarkup()

    kb.add(
        types.InlineKeyboardButton(
            "⛔ توقف ارسال",
            callback_data="job_stop"
        )
    )

    status = bot.send_message(
        call.message.chat.id,
        "🚀 <b>ارسال شروع شد.</b>\n\n"
        f"📦 تعداد کل: <b>{count}</b>\n"
        "📤 ارسال‌شده: <b>0</b>",
        reply_markup=kb
    )

    job["status_message_id"] = (
        status.message_id
    )

    thread = threading.Thread(
        target=send_worker,
        args=(user_id,),
        daemon=True
    )

    thread.start()


# =========================
# CANCEL JOB
# =========================

@bot.callback_query_handler(
    func=lambda c: c.data == "job_cancel"
)
def job_cancel(call):

    user_id = call.from_user.id

    user_states.pop(
        user_id,
        None
    )

    pending_content.pop(
        user_id,
        None
    )

    bot.answer_callback_query(
        call.id,
        "❌ لغو شد."
    )

    bot.edit_message_text(
        "❌ <b>ارسال لغو شد.</b>",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=back_button()
    )


# =========================
# STOP JOB
# =========================

@bot.callback_query_handler(
    func=lambda c: c.data == "job_stop"
)
def job_stop(call):

    user_id = call.from_user.id

    job = active_jobs.get(user_id)

    if not job:
        bot.answer_callback_query(
            call.id,
            "ارسالی در حال اجرا نیست."
        )
        return

    job["stop"] = True

    bot.answer_callback_query(
        call.id,
        "⛔ دستور توقف ارسال داده شد."
    )


# =========================
# SEND CONTENT TO CHAT
# =========================

def send_content(
    chat_id,
    content
):
    content_type = content["type"]

    if content_type == "text":

        return bot.send_message(
            chat_id,
            content["text"]
        )

    if content_type == "photo":

        return bot.send_photo(
            chat_id,
            content["file_id"],
            caption=content.get(
                "caption",
                ""
            )
        )

    if content_type == "video":

        return bot.send_video(
            chat_id,
            content["file_id"],
            caption=content.get(
                "caption",
                ""
            )
        )

    if content_type == "animation":

        return bot.send_animation(
            chat_id,
            content["file_id"],
            caption=content.get(
                "caption",
                ""
            )
        )

    if content_type == "sticker":

        return bot.send_sticker(
            chat_id,
            content["file_id"]
        )

    raise ValueError(
        "Unsupported content type"
    )


# =========================
# SEND WORKER
# =========================

def send_worker(user_id):

    job = active_jobs.get(
        user_id
    )

    if not job:
        return

    chat_id = job["chat_id"]
    count = job["count"]
    delay = job["delay"]
    content = job["content"]

    sent = 0
    stopped = False
    failed = False

    while sent < count:

        if job["stop"]:
            stopped = True
            break

        try:

            send_content(
                chat_id,
                content
            )

            sent += 1

            job["sent"] = sent

            update_status(
                job,
                sent,
                count
            )

        except Exception as e:

            print(
                "SEND ERROR:",
                e
            )

            failed = True

            notify_user(
                user_id,
                "❌ ارسال متوقف شد.\n\n"
                f"📤 ارسال‌شده: {sent}/{count}\n"
                "تلگرام اجازه ادامه ارسال را نداد."
            )

            break

        if sent < count:

            # توقف در صورت درخواست
            # با بررسی‌های کوتاه
            # بدون تلاش برای دور زدن Rate Limit

            remaining = delay
            step = 0.5

            while remaining > 0:

                if job["stop"]:
                    stopped = True
                    break

                time.sleep(
                    min(
                        step,
                        remaining
                    )
                )

                remaining -= step

            if stopped:
                break

    active_jobs.pop(
        user_id,
        None
    )

    if stopped:

        notify_user(
            user_id,
            "⛔ <b>ارسال متوقف شد.</b>\n\n"
            f"📤 تعداد ارسال‌شده: "
            f"<b>{sent}/{count}</b>"
        )

    elif failed:
        pass

    else:

        notify_user(
            user_id,
            "✅ <b>ارسال کامل شد.</b>\n\n"
            f"📤 تعداد ارسال‌شده: "
            f"<b>{sent}/{count}</b>"
        )


# =========================
# UPDATE STATUS
# =========================

def update_status(
    job,
    sent,
    total
):

    user_id = job["user_id"]

    message_id = job.get(
        "status_message_id"
    )

    if not message_id:
        return

    try:

        kb = types.InlineKeyboardMarkup()

        kb.add(
            types.InlineKeyboardButton(
                "⛔ توقف ارسال",
                callback_data="job_stop"
            )
        )

        bot.edit_message_text(
            "🚀 <b>ارسال در حال انجام است</b>\n\n"
            f"📤 ارسال‌شده: <b>{sent}</b>\n"
            f"📦 کل: <b>{total}</b>\n"
            f"📊 پیشرفت: "
            f"<b>{sent}/{total}</b>",
            user_id,
            message_id,
            reply_markup=kb
        )

    except Exception:
        pass


# =========================
# NOTIFY
# =========================

def notify_user(
    user_id,
    text
):

    try:

        bot.send_message(
            user_id,
            text,
            reply_markup=main_keyboard()
        )

    except Exception as e:

        print(
            "Notify error:",
            e
        )


# =========================
# MY CHATS COMMAND
# =========================

@bot.message_handler(
    commands=["chats"]
)
def chats_command(message):

    if message.chat.type != "private":
        return

    chats = get_chats()

    if not chats:

        bot.send_message(
            message.chat.id,
            "📋 هیچ گپی ثبت نشده.",
            reply_markup=main_keyboard()
        )

        return

    lines = [
        "📋 <b>گپ‌های ثبت‌شده</b>",
        ""
    ]

    for index, chat in enumerate(
        chats,
        1
    ):

        title = (
            chat["title"]
            or "بدون نام"
        )

        lines.append(
            f"{index}. 💬 {title}"
        )

    bot.send_message(
        message.chat.id,
        "\n".join(lines),
        reply_markup=main_keyboard()
    )


# =========================
# STOP COMMAND
# =========================

@bot.message_handler(
    commands=["stop"]
)
def stop_command(message):

    if message.chat.type != "private":
        return

    user_id = message.from_user.id

    job = active_jobs.get(
        user_id
    )

    if not job:

        bot.send_message(
            message.chat.id,
            "ℹ️ هیچ ارسال فعالی نداری."
        )

        return

    job["stop"] = True

    bot.send_message(
        message.chat.id,
        "⛔ درخواست توقف ثبت شد.\n"
        "ارسال پس از پایان چرخه فعلی متوقف می‌شود."
    )


# =========================
# UNKNOWN PRIVATE MESSAGE
# =========================

@bot.message_handler(
    func=lambda m:
    m.chat.type == "private"
)
def private_unknown(message):

    user_id = message.from_user.id

    state = user_states.get(
        user_id
    )

    if state:
        return

    bot.send_message(
        message.chat.id,
        "🤖 از منوی زیر استفاده کن:",
        reply_markup=main_keyboard()
    )
    # =========================
# BOT HEALTH CHECK
# =========================

def bot_health_check():
    try:
        me = bot.get_me()

        print(
            "================================"
        )

        print(
            "🤖 BOT:",
            me.first_name
        )

        print(
            "🆔 ID:",
            me.id
        )

        print(
            "🟢 STATUS: ONLINE"
        )

        print(
            "================================"
        )

        return True

    except Exception as e:

        print(
            "❌ BOT CHECK ERROR:",
            e
        )

        return False


# =========================
# CLEAN OLD USER STATES
# =========================

def cleanup_states():

    while True:

        try:

            # وضعیت‌های ناقص را پاک می‌کنیم
            # تا حافظه بی‌دلیل پر نشود.

            if len(user_states) > 1000:

                keys = list(
                    user_states.keys()
                )

                for user_id in keys[:500]:

                    user_states.pop(
                        user_id,
                        None
                    )

                    pending_content.pop(
                        user_id,
                        None
                    )

            time.sleep(300)

        except Exception as e:

            print(
                "Cleanup error:",
                e
            )

            time.sleep(60)


# =========================
# CLEANUP THREAD
# =========================

threading.Thread(
    target=cleanup_states,
    daemon=True
).start()


# =========================
# ERROR HANDLER
# =========================

@bot.message_handler(
    commands=["cancel"]
)
def cancel_command(message):

    if message.chat.type != "private":
        return

    user_id = message.from_user.id

    job = active_jobs.get(
        user_id
    )

    if job:

        job["stop"] = True

        bot.send_message(
            message.chat.id,
            "⛔ درخواست توقف ارسال ثبت شد."
        )

        return

    user_states.pop(
        user_id,
        None
    )

    pending_content.pop(
        user_id,
        None
    )

    bot.send_message(
        message.chat.id,
        "❌ عملیات فعلی لغو شد.",
        reply_markup=main_keyboard()
    )


# =========================
# STATUS COMMAND
# =========================

@bot.message_handler(
    commands=["status"]
)
def status_command(message):

    if message.chat.type != "private":
        return

    user_id = message.from_user.id

    job = active_jobs.get(
        user_id
    )

    if not job:

        bot.send_message(
            message.chat.id,
            "ℹ️ در حال حاضر هیچ ارسال فعالی نداری.",
            reply_markup=main_keyboard()
        )

        return

    sent = job.get(
        "sent",
        0
    )

    total = job.get(
        "count",
        0
    )

    bot.send_message(
        message.chat.id,
        "📊 <b>وضعیت ارسال</b>\n\n"
        f"📤 ارسال‌شده: <b>{sent}</b>\n"
        f"📦 کل: <b>{total}</b>\n"
        f"📊 پیشرفت: <b>{sent}/{total}</b>",
        reply_markup=main_keyboard()
    )


# =========================
# GROUP TEST
# =========================

@bot.message_handler(
    commands=["bot"]
)
def group_bot_info(message):

    if message.chat.type not in (
        "group",
        "supergroup"
    ):
        return

    bot.reply_to(
        message,
        "🤖 <b>بات فعال است.</b>\n\n"
        "برای ثبت این گپ در پنل پیوی:\n"
        "<code>/register</code>"
    )


# =========================
# REGISTER HELP
# =========================

@bot.message_handler(
    commands=["register_help"]
)
def register_help(message):

    if message.chat.type == "private":

        bot.send_message(
            message.chat.id,
            "📖 <b>ثبت گپ</b>\n\n"
            "1️⃣ بات را به گپ اضافه کن.\n"
            "2️⃣ داخل گپ دستور زیر را بفرست:\n\n"
            "<code>/register</code>\n\n"
            "3️⃣ به پیوی بات برگرد.\n"
            "4️⃣ روی 📋 گپ‌های من بزن.\n\n"
            "گپ ثبت‌شده در آنجا نمایش داده می‌شود."
        )

        return

    bot.reply_to(
        message,
        "📖 برای ثبت گپ کافی است:\n\n"
        "<code>/register</code>"
    )


# =========================
# CHECK REGISTERED CHATS
# =========================

def verify_chats():

    while True:

        try:

            chats = get_chats()

            for chat in chats:

                chat_id = chat["chat_id"]

                try:

                    me = bot.get_me()

                    member = bot.get_chat_member(
                        chat_id,
                        me.id
                    )

                    if member.status in (
                        "left",
                        "kicked"
                    ):

                        print(
                            "Removing unavailable chat:",
                            chat_id
                        )

                        remove_chat(
                            chat_id
                        )

                except Exception as e:

                    print(
                        "Chat verification:",
                        chat_id,
                        e
                    )

            time.sleep(600)

        except Exception as e:

            print(
                "Verify error:",
                e
            )

            time.sleep(120)


threading.Thread(
    target=verify_chats,
    daemon=True
).start()


# =========================
# STARTUP
# =========================

if __name__ == "__main__":

    print("")
    print(
        "========================================"
    )
    print(
        "🚀 CONTENT SENDER BOT"
    )
    print(
        "========================================"
    )
    print(
        "📦 Database:",
        DB_NAME
    )
    print(
        "🔢 Max messages:",
        MAX_MESSAGES
    )
    print(
        "⏱ Minimum delay:",
        MIN_DELAY,
        "seconds"
    )
    print(
        "========================================"
    )

    if not bot_health_check():

        print(
            "❌ Bot token is invalid "
            "or Telegram is unreachable."
        )

        raise SystemExit(1)

    print(
        "🟢 Starting polling..."
    )

    while True:

        try:

            bot.infinity_polling(
                skip_pending=True,
                timeout=60,
                long_polling_timeout=60,
                allowed_updates=[
                    "message",
                    "callback_query"
                ]
            )

        except KeyboardInterrupt:

            print(
                "🛑 Bot stopped."
            )

            break

        except Exception as e:

            print(
                "⚠️ Polling error:",
                e
            )

            print(
                "🔄 Restarting polling in 10 seconds..."
            )

            time.sleep(10)
