# ============================================================
# STARS BOT
# PART 1/8
# CORE + DATABASE
# ============================================================

import sqlite3
import secrets
import string
import logging
from datetime import datetime, timezone

import telebot
from telebot import types


# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = "8968618358:AAHReb2nlduQkclIJE1V-_FKh206VxmYmuc"
ADMIN_ID = 7530457395
DB_FILE = "stars_bot.db"


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("StarsBot")


# ============================================================
# BOT
# ============================================================

if BOT_TOKEN == "TOKEN_HERE":
    raise RuntimeError(
        "توکن ربات را داخل BOT_TOKEN قرار بده."
    )

bot = telebot.TeleBot(
    BOT_TOKEN,
    parse_mode="HTML"
)


# ============================================================
# DATABASE
# ============================================================

db = sqlite3.connect(
    DB_FILE,
    check_same_thread=False
)

db.row_factory = sqlite3.Row


def query(
    sql,
    params=(),
    commit=False
):

    cur = db.cursor()

    cur.execute(
        sql,
        params
    )

    if commit:
        db.commit()

    return cur


def now():

    return datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# ============================================================
# DATABASE TABLES
# ============================================================

def init_database():

    query("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            first_name TEXT DEFAULT '',
            last_name TEXT DEFAULT '',
            balance INTEGER DEFAULT 0,
            total_deposit INTEGER DEFAULT 0,
            total_spent INTEGER DEFAULT 0,
            total_orders INTEGER DEFAULT 0,
            completed_orders INTEGER DEFAULT 0,
            referral_count INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT 0,
            blocked INTEGER DEFAULT 0,
            joined_at TEXT DEFAULT '',
            last_seen TEXT DEFAULT ''
        )
    """)

    query("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        )
    """)

    query("""
        CREATE TABLE IF NOT EXISTS locked_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT UNIQUE,
            title TEXT DEFAULT '',
            username TEXT DEFAULT '',
            invite_link TEXT DEFAULT '',
            active INTEGER DEFAULT 1
        )
    """)

    query("""
        CREATE TABLE IF NOT EXISTS missions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT DEFAULT '',
            description TEXT DEFAULT '',
            mission_type TEXT DEFAULT '',
            target TEXT DEFAULT '',
            reward INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT ''
        )
    """)

    query("""
        CREATE TABLE IF NOT EXISTS mission_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_id INTEGER,
            user_id INTEGER,
            completed INTEGER DEFAULT 0,
            completed_at TEXT DEFAULT '',
            UNIQUE(mission_id, user_id)
        )
    """)

    query("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            code TEXT UNIQUE,
            title TEXT DEFAULT '',
            reason TEXT DEFAULT '',
            post_link TEXT DEFAULT '',
            amount INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )
    """)

    query("""
        CREATE TABLE IF NOT EXISTS gift_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            code_type TEXT DEFAULT 'stars',
            amount INTEGER DEFAULT 0,
            gift_info TEXT DEFAULT '',
            sticker_file_id TEXT DEFAULT '',
            max_uses INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0,
            expires_at TEXT DEFAULT '',
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT ''
        )
    """)

    query("""
        CREATE TABLE IF NOT EXISTS gift_code_uses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code_id INTEGER,
            user_id INTEGER,
            used_at TEXT DEFAULT '',
            UNIQUE(code_id, user_id)
        )
    """)

    query("""
        CREATE TABLE IF NOT EXISTS giveaways (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT DEFAULT '',
            description TEXT DEFAULT '',
            prize_type TEXT DEFAULT '',
            prize_amount INTEGER DEFAULT 0,
            prize_info TEXT DEFAULT '',
            sticker_file_id TEXT DEFAULT '',
            channel_id TEXT DEFAULT '',
            message_id INTEGER DEFAULT 0,
            max_winners INTEGER DEFAULT 1,
            end_time TEXT DEFAULT '',
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT ''
        )
    """)

    query("""
        CREATE TABLE IF NOT EXISTS giveaway_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            giveaway_id INTEGER,
            user_id INTEGER,
            joined_at TEXT DEFAULT '',
            UNIQUE(giveaway_id, user_id)
        )
    """)

    query("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            stars INTEGER DEFAULT 0,
            payload TEXT DEFAULT '',
            telegram_charge_id TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT ''
        )
    """)

    query("""
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT DEFAULT '',
            target_user INTEGER DEFAULT 0,
            details TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        )
    """)

    query("""
        CREATE TABLE IF NOT EXISTS states (
            user_id INTEGER PRIMARY KEY,
            state TEXT DEFAULT '',
            data TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )
    """)

    db.commit()


# ============================================================
# DEFAULT SETTINGS
# ============================================================

DEFAULT_SETTINGS = {

    "bot_enabled": "1",

    "maintenance": "0",

    "force_join": "0",

    "free_stars": "1",

    "orders": "1",

    "gift_codes": "1",

    "giveaways": "1",

    "referrals": "1",

    "stars_price": "40000",

    "stars_package": "10",

    "minimum_charge": "1",

    "maximum_charge": "10000",

    "referral_reward": "1",

    "code_channel_id": "",

    "giveaway_channel_id": "",

    "support_username": "",

    "bot_title": "Stars Bot"
}


def init_settings():

    for key, value in DEFAULT_SETTINGS.items():

        row = query(
            """
            SELECT key
            FROM settings
            WHERE key = ?
            """,
            (key,)
        ).fetchone()

        if row is None:

            query(
                """
                INSERT INTO settings(
                    key,
                    value
                )
                VALUES (?, ?)
                """,
                (
                    key,
                    value
                )
            )

    db.commit()


def get_setting(
    key,
    default=""
):

    row = query(
        """
        SELECT value
        FROM settings
        WHERE key = ?
        """,
        (key,)
    ).fetchone()

    if row is None:
        return default

    return row["value"]


def set_setting(
    key,
    value
):

    query(
        """
        INSERT INTO settings(
            key,
            value
        )
        VALUES (?, ?)

        ON CONFLICT(key)
        DO UPDATE SET
            value = excluded.value
        """,
        (
            key,
            str(value)
        ),
        True
    )


# ============================================================
# USER FUNCTIONS
# ============================================================

def ensure_user(
    user
):

    row = query(
        """
        SELECT user_id
        FROM users
        WHERE user_id = ?
        """,
        (user.id,)
    ).fetchone()

    username = user.username or ""
    first_name = user.first_name or ""
    last_name = user.last_name or ""

    if row is None:

        query(
            """
            INSERT INTO users(
                user_id,
                username,
                first_name,
                last_name,
                balance,
                total_deposit,
                total_spent,
                total_orders,
                completed_orders,
                referral_count,
                referred_by,
                blocked,
                joined_at,
                last_seen
            )

            VALUES(
                ?, ?, ?, ?,
                0, 0, 0, 0, 0,
                0, 0, 0, ?, ?
            )
            """,
            (
                user.id,
                username,
                first_name,
                last_name,
                now(),
                now()
            ),
            True
        )

    else:

        query(
            """
            UPDATE users

            SET username = ?,
                first_name = ?,
                last_name = ?,
                last_seen = ?

            WHERE user_id = ?
            """,
            (
                username,
                first_name,
                last_name,
                now(),
                user.id
            ),
            True
        )


def get_user(
    user_id
):

    return query(
        """
        SELECT *
        FROM users
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()


def get_balance(
    user_id
):

    user = get_user(
        user_id
    )

    if user is None:
        return 0

    return int(
        user["balance"]
    )


def add_balance(
    user_id,
    amount
):

    amount = int(amount)

    if amount <= 0:
        return False

    query(
        """
        UPDATE users

        SET balance = balance + ?,
            total_deposit = total_deposit + ?

        WHERE user_id = ?
        """,
        (
            amount,
            amount,
            user_id
        ),
        True
    )

    return True


def remove_balance(
    user_id,
    amount
):

    amount = int(amount)

    if amount <= 0:
        return False

    balance = get_balance(
        user_id
    )

    if balance < amount:
        return False

    query(
        """
        UPDATE users

        SET balance = balance - ?,
            total_spent = total_spent + ?

        WHERE user_id = ?
        """,
        (
            amount,
            amount,
            user_id
        ),
        True
    )

    return True


# ============================================================
# ADMIN
# ============================================================

def is_admin(
    user_id
):

    try:
        return int(user_id) == ADMIN_ID
    except Exception:
        return False


def admin_log(
    action,
    target_user=0,
    details=""
):

    query(
        """
        INSERT INTO admin_logs(
            admin_id,
            action,
            target_user,
            details,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            ADMIN_ID,
            action,
            target_user,
            details,
            now()
        ),
        True
    )


# ============================================================
# STATES
# ============================================================

def set_state(
    user_id,
    state,
    data=""
):

    query(
        """
        INSERT INTO states(
            user_id,
            state,
            data,
            updated_at
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(user_id)
        DO UPDATE SET
            state = excluded.state,
            data = excluded.data,
            updated_at = excluded.updated_at
        """,
        (
            user_id,
            state,
            data,
            now()
        ),
        True
    )


def get_state(
    user_id
):

    return query(
        """
        SELECT *
        FROM states
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()


def clear_state(
    user_id
):

    query(
        """
        DELETE FROM states
        WHERE user_id = ?
        """,
        (user_id,),
        True
    )


# ============================================================
# RANDOM CODES
# ============================================================

def random_code(
    length=8
):

    chars = (
        string.ascii_letters +
        string.digits
    )

    return "".join(
        secrets.choice(chars)
        for _ in range(length)
    )


def unique_order_code():

    while True:

        code = random_code(8)

        row = query(
            """
            SELECT id
            FROM orders
            WHERE code = ?
            """,
            (code,)
        ).fetchone()

        if row is None:
            return code


def unique_gift_code():

    while True:

        code = random_code(10)

        row = query(
            """
            SELECT id
            FROM gift_codes
            WHERE code = ?
            """,
            (code,)
        ).fetchone()

        if row is None:
            return code


# ============================================================
# FORMAT
# ============================================================

def number(
    value
):

    try:
        return f"{int(value):,}"
    except Exception:
        return "0"


# ============================================================
# INITIALIZE
# ============================================================

init_database()
init_settings()


# ============================================================
# PART 1 COMPLETE
# ============================================================
# ============================================================
# STARS BOT
# PART 2/8
# MAIN MENU + PROFILE + CHARGE
# ============================================================


# ============================================================
# BASIC HELPERS
# ============================================================

def safe_name(
    user
):

    name = user.first_name or "کاربر"

    if len(name) > 40:
        name = name[:40]

    return name


def user_username(
    user
):

    if user.username:
        return "@" + user.username

    return "ندارد"


# ============================================================
# MAIN KEYBOARD
# ============================================================

def main_keyboard(
    user_id
):

    keyboard = types.InlineKeyboardMarkup(
        row_width=2
    )

    keyboard.add(

        types.InlineKeyboardButton(
            "⭐ Stars و جوایز",
            callback_data="menu_stars"
        ),

        types.InlineKeyboardButton(
            "🎯 قرعه‌کشی",
            callback_data="menu_giveaways"
        ),

        types.InlineKeyboardButton(
            "👤 پروفایل",
            callback_data="menu_profile"
        ),

        types.InlineKeyboardButton(
            "🎁 کد هدیه",
            callback_data="menu_gift"
        )
    )

    if is_admin(user_id):

        keyboard.add(
            types.InlineKeyboardButton(
                "⚙️ پنل مدیریت",
                callback_data="admin_panel"
            )
        )

    return keyboard


def main_text(
    user_id
):

    user = get_user(
        user_id
    )

    if user is None:

        balance = 0
        name = "کاربر"

    else:

        balance = user["balance"]
        name = user["first_name"] or "کاربر"

    title = get_setting(
        "bot_title",
        "Stars Bot"
    )

    return (
        f"🤖 <b>{title}</b>\n\n"

        f"سلام <b>{name}</b> 👋\n\n"

        f"⭐ موجودی شما: "
        f"<b>{number(balance)} Stars</b>\n\n"

        "از منوی زیر انتخاب کنید:"
    )


# ============================================================
# PROFILE
# ============================================================

def profile_keyboard():

    keyboard = types.InlineKeyboardMarkup(
        row_width=2
    )

    keyboard.add(

        types.InlineKeyboardButton(
            "💳 شارژ حساب",
            callback_data="charge_menu"
        ),

        types.InlineKeyboardButton(
            "📊 آمار حساب",
            callback_data="profile_stats"
        ),

        types.InlineKeyboardButton(
            "📦 سفارش‌های من",
            callback_data="my_orders"
        ),

        types.InlineKeyboardButton(
            "👥 دعوت دوستان",
            callback_data="referral_menu"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="main_menu"
        )
    )

    return keyboard


def profile_text(
    user_id
):

    user = get_user(
        user_id
    )

    if user is None:
        return "❌ اطلاعات کاربر پیدا نشد."

    username = (
        "@" + user["username"]
        if user["username"]
        else "ندارد"
    )

    return (
        "👤 <b>پروفایل شما</b>\n\n"

        f"👤 نام:\n"
        f"<b>{user['first_name'] or 'کاربر'}</b>\n\n"

        f"🆔 شناسه:\n"
        f"<code>{user_id}</code>\n\n"

        f"🔗 یوزرنیم:\n"
        f"{username}\n\n"

        f"⭐ موجودی:\n"
        f"<b>{number(user['balance'])} Stars</b>\n\n"

        f"💰 مجموع شارژ:\n"
        f"<b>{number(user['total_deposit'])} Stars</b>\n\n"

        f"💸 مجموع مصرف:\n"
        f"<b>{number(user['total_spent'])} Stars</b>\n\n"

        f"📦 تعداد سفارش:\n"
        f"<b>{user['total_orders']}</b>\n\n"

        f"👥 دعوت‌ها:\n"
        f"<b>{user['referral_count']}</b>"
    )


def profile_stats_text(
    user_id
):

    user = get_user(
        user_id
    )

    if user is None:
        return "❌ کاربر پیدا نشد."

    total_orders = query(
        """
        SELECT COUNT(*) AS c
        FROM orders
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()["c"]

    pending_orders = query(
        """
        SELECT COUNT(*) AS c
        FROM orders
        WHERE user_id = ?
        AND status = 'pending'
        """,
        (user_id,)
    ).fetchone()["c"]

    completed_orders = query(
        """
        SELECT COUNT(*) AS c
        FROM orders
        WHERE user_id = ?
        AND status = 'completed'
        """,
        (user_id,)
    ).fetchone()["c"]

    giveaways = query(
        """
        SELECT COUNT(*) AS c
        FROM giveaway_participants
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()["c"]

    codes = query(
        """
        SELECT COUNT(*) AS c
        FROM gift_code_uses
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()["c"]

    return (
        "📊 <b>آمار حساب</b>\n\n"

        f"⭐ موجودی: "
        f"<b>{number(user['balance'])}</b>\n\n"

        f"💰 مجموع شارژ: "
        f"<b>{number(user['total_deposit'])}</b>\n\n"

        f"💸 مجموع مصرف: "
        f"<b>{number(user['total_spent'])}</b>\n\n"

        f"📦 کل سفارش‌ها: "
        f"<b>{total_orders}</b>\n\n"

        f"⏳ در انتظار: "
        f"<b>{pending_orders}</b>\n\n"

        f"✅ تکمیل‌شده: "
        f"<b>{completed_orders}</b>\n\n"

        f"🎯 شرکت در قرعه‌کشی: "
        f"<b>{giveaways}</b>\n\n"

        f"🎁 کدهای استفاده‌شده: "
        f"<b>{codes}</b>"
    )


# ============================================================
# STARS MENU
# ============================================================

def stars_keyboard():

    keyboard = types.InlineKeyboardMarkup(
        row_width=1
    )

    keyboard.add(

        types.InlineKeyboardButton(
            "⭐ Stars رایگان",
            callback_data="free_stars"
        ),

        types.InlineKeyboardButton(
            "💳 شارژ حساب",
            callback_data="charge_menu"
        ),

        types.InlineKeyboardButton(
            "🎁 استفاده از کد هدیه",
            callback_data="menu_gift"
        ),

        types.InlineKeyboardButton(
            "🎯 قرعه‌کشی‌ها",
            callback_data="menu_giveaways"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="main_menu"
        )
    )

    return keyboard


def stars_text():

    package = get_setting(
        "stars_package",
        "10"
    )

    price = get_setting(
        "stars_price",
        "40000"
    )

    return (
        "⭐ <b>Stars و جوایز</b>\n\n"

        "از این بخش می‌توانید:\n\n"

        "⭐ Stars رایگان دریافت کنید\n"
        "💳 حساب خود را شارژ کنید\n"
        "🎁 کد هدیه استفاده کنید\n"
        "🎯 در قرعه‌کشی‌ها شرکت کنید\n\n"

        f"💰 نرخ فعلی:\n"
        f"<b>{package} Stars = "
        f"{number(price)} تومان</b>"
    )


# ============================================================
# CHARGE
# ============================================================

def charge_keyboard():

    keyboard = types.InlineKeyboardMarkup(
        row_width=2
    )

    amounts = [
        10,
        25,
        50,
        100,
        250,
        500
    ]

    buttons = []

    for amount in amounts:

        buttons.append(
            types.InlineKeyboardButton(
                f"⭐ {amount}",
                callback_data=f"charge:{amount}"
            )
        )

    for i in range(
        0,
        len(buttons),
        2
    ):

        keyboard.row(
            *buttons[
                i:i + 2
            ]
        )

    keyboard.add(
        types.InlineKeyboardButton(
            "✏️ مقدار دلخواه",
            callback_data="charge_custom"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="menu_profile"
        )
    )

    return keyboard


def charge_text():

    package = int(
        get_setting(
            "stars_package",
            "10"
        )
    )

    price = int(
        get_setting(
            "stars_price",
            "40000"
        )
    )

    if package <= 0:
        package = 10

    unit = round(
        price / package
    )

    return (
        "💳 <b>شارژ حساب</b>\n\n"

        "مقدار Stars موردنظر را انتخاب کنید.\n\n"

        f"⭐ نرخ فعلی:\n"
        f"<b>{package} Stars = "
        f"{number(price)} تومان</b>\n\n"

        f"🔹 قیمت هر Star:\n"
        f"<b>{number(unit)} تومان</b>\n\n"

        "پرداخت از طریق Telegram Stars "
        "انجام خواهد شد."
    )


def calculate_price(
    stars
):

    try:
        stars = int(stars)
    except Exception:
        return 0

    package = int(
        get_setting(
            "stars_package",
            "10"
        )
    )

    price = int(
        get_setting(
            "stars_price",
            "40000"
        )
    )

    if package <= 0:
        package = 10

    if stars <= 0:
        return 0

    return round(
        stars * price / package
    )


def charge_confirm_keyboard(
    stars
):

    keyboard = types.InlineKeyboardMarkup(
        row_width=2
    )

    keyboard.add(

        types.InlineKeyboardButton(
            "💳 پرداخت",
            callback_data=f"pay:{stars}"
        ),

        types.InlineKeyboardButton(
            "❌ لغو",
            callback_data="charge_menu"
        )
    )

    return keyboard


def charge_confirm_text(
    stars
):

    price = calculate_price(
        stars
    )

    return (
        "💳 <b>تأیید شارژ</b>\n\n"

        f"⭐ مقدار:\n"
        f"<b>{number(stars)} Stars</b>\n\n"

        f"💰 ارزش:\n"
        f"<b>{number(price)} تومان</b>\n\n"

        "برای ادامه روی «پرداخت» بزنید."
    )


# ============================================================
# SIMPLE BACK BUTTON
# ============================================================

def back_button(
    callback
):

    keyboard = types.InlineKeyboardMarkup()

    keyboard.add(
        types.InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data=callback
        )
    )

    return keyboard


# ============================================================
# SAFE EDIT
# ============================================================

def edit_message(
    call,
    text,
    keyboard=None
):

    try:

        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )

    except Exception as error:

        if "message is not modified" not in str(
            error
        ).lower():

            try:

                bot.send_message(
                    call.message.chat.id,
                    text,
                    reply_markup=keyboard
                )

            except Exception:
                pass


# ============================================================
# START
# ============================================================

@bot.message_handler(
    commands=["start"]
)
def start_handler(
    message
):

    user_id = message.from_user.id

    ensure_user(
        message.from_user
    )

    if not is_admin(
        user_id
    ):

        if get_setting(
            "bot_enabled",
            "1"
        ) != "1":

            bot.send_message(
                message.chat.id,
                "⛔ ربات فعلاً غیرفعال است."
            )

            return

        if get_setting(
            "maintenance",
            "0"
        ) == "1":

            bot.send_message(
                message.chat.id,
                "🔧 ربات موقتاً در حال تعمیر است."
            )

            return

    bot.send_message(
        message.chat.id,

        main_text(
            user_id
        ),

        reply_markup=main_keyboard(
            user_id
        )
    )


# ============================================================
# MENU COMMAND
# ============================================================

@bot.message_handler(
    commands=["menu"]
)
def menu_handler(
    message
):

    user_id = message.from_user.id

    ensure_user(
        message.from_user
    )

    bot.send_message(
        message.chat.id,

        main_text(
            user_id
        ),

        reply_markup=main_keyboard(
            user_id
        )
    )


# ============================================================
# CALLBACKS - MAIN MENU
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data in (
            "main_menu",
            "menu_profile",
            "profile_stats",
            "menu_stars",
            "charge_menu",
            "charge_custom"
        )
        or call.data.startswith("charge:")
)
def main_menu_callback(
    call
):

    user_id = call.from_user.id

    ensure_user(
        call.from_user
    )

    try:

        bot.answer_callback_query(
            call.id
        )

    except Exception:
        pass

    data = call.data

    # --------------------------------------------------------
    # MAIN
    # --------------------------------------------------------

    if data == "main_menu":

        edit_message(
            call,
            main_text(user_id),
            main_keyboard(user_id)
        )

        return

    # --------------------------------------------------------
    # PROFILE
    # --------------------------------------------------------

    if data == "menu_profile":

        edit_message(
            call,
            profile_text(user_id),
            profile_keyboard()
        )

        return

    # --------------------------------------------------------
    # PROFILE STATS
    # --------------------------------------------------------

    if data == "profile_stats":

        edit_message(
            call,
            profile_stats_text(user_id),
            back_button("menu_profile")
        )

        return

    # --------------------------------------------------------
    # STARS
    # --------------------------------------------------------

    if data == "menu_stars":

        edit_message(
            call,
            stars_text(),
            stars_keyboard()
        )

        return

    # --------------------------------------------------------
    # CHARGE MENU
    # --------------------------------------------------------

    if data == "charge_menu":

        edit_message(
            call,
            charge_text(),
            charge_keyboard()
        )

        return

    # --------------------------------------------------------
    # CUSTOM CHARGE
    # --------------------------------------------------------

    if data == "charge_custom":

        set_state(
            user_id,
            "custom_charge"
        )

        edit_message(
            call,

            "✏️ <b>شارژ دلخواه</b>\n\n"

            "تعداد Stars را ارسال کنید.\n\n"

            "مثال:\n"
            "<code>100</code>\n\n"

            "برای لغو بنویسید:\n"
            "<code>لغو</code>",

            back_button(
                "charge_menu"
            )
        )

        return

    # --------------------------------------------------------
    # CHARGE AMOUNT
    # --------------------------------------------------------

    if data.startswith(
        "charge:"
    ):

        try:

            stars = int(
                data.split(
                    ":",
                    1
                )[1]
            )

        except Exception:

            return

        minimum = int(
            get_setting(
                "minimum_charge",
                "1"
            )
        )

        maximum = int(
            get_setting(
                "maximum_charge",
                "10000"
            )
        )

        if stars < minimum:

            edit_message(
                call,

                f"❌ حداقل شارژ "
                f"<b>{number(minimum)} Stars</b> است.",

                back_button(
                    "charge_menu"
                )
            )

            return

        if stars > maximum:

            edit_message(
                call,

                f"❌ حداکثر شارژ "
                f"<b>{number(maximum)} Stars</b> است.",

                back_button(
                    "charge_menu"
                )
            )

            return

        edit_message(
            call,

            charge_confirm_text(
                stars
            ),

            charge_confirm_keyboard(
                stars
            )
        )

        return


# ============================================================
# TEXT STATE HANDLER
# ============================================================

@bot.message_handler(
    content_types=["text"]
)
def basic_state_handler(
    message
):

    user_id = message.from_user.id

    ensure_user(
        message.from_user
    )

    state_row = get_state(
        user_id
    )

    if state_row is None:

        return

    state = state_row["state"]

    text = (
        message.text or ""
    ).strip()

    # --------------------------------------------------------
    # CANCEL
    # --------------------------------------------------------

    if text.lower() in (
        "لغو",
        "cancel"
    ):

        clear_state(
            user_id
        )

        bot.send_message(
            message.chat.id,

            "❌ عملیات لغو شد.",

            reply_markup=main_keyboard(
                user_id
            )
        )

        return

    # --------------------------------------------------------
    # CUSTOM CHARGE
    # --------------------------------------------------------

    if state == "custom_charge":

        try:

            stars = int(
                text
            )

        except ValueError:

            bot.send_message(
                message.chat.id,

                "❌ مقدار نامعتبر است.\n\n"
                "فقط عدد ارسال کنید.\n"
                "مثال: <code>100</code>"
            )

            return

        minimum = int(
            get_setting(
                "minimum_charge",
                "1"
            )
        )

        maximum = int(
            get_setting(
                "maximum_charge",
                "10000"
            )
        )

        if stars < minimum:

            bot.send_message(
                message.chat.id,

                f"❌ حداقل مقدار "
                f"<b>{number(minimum)} Stars</b> است."
            )

            return

        if stars > maximum:

            bot.send_message(
                message.chat.id,

                f"❌ حداکثر مقدار "
                f"<b>{number(maximum)} Stars</b> است."
            )

            return

        clear_state(
            user_id
        )

        bot.send_message(
            message.chat.id,

            charge_confirm_text(
                stars
            ),

            reply_markup=charge_confirm_keyboard(
                stars
            )
        )

        return


# ============================================================
# PART 2 COMPLETE
# ============================================================
# ============================================================
# STARS BOT
# PART 3/8
# FORCE JOIN + MISSIONS + FREE STARS
# ============================================================


# ============================================================
# FORCE JOIN SETTINGS
# ============================================================

def force_join_enabled():

    return get_setting(
        "force_join",
        "0"
    ) == "1"


def get_locked_channels():

    return query(
        """
        SELECT *
        FROM locked_channels
        WHERE active = 1
        ORDER BY id ASC
        """
    ).fetchall()


def get_channel_link(
    channel
):

    invite = (
        channel["invite_link"]
        or ""
    ).strip()

    if invite:
        return invite

    username = (
        channel["username"]
        or ""
    ).strip()

    if username:

        if username.startswith("@"):
            username = username[1:]

        return (
            "https://t.me/"
            + username
        )

    return ""


def is_member(
    user_id,
    chat_id
):

    try:

        member = bot.get_chat_member(
            chat_id,
            user_id
        )

        if member.status in (
            "creator",
            "administrator",
            "member"
        ):

            return True

        if member.status == "restricted":

            return bool(
                getattr(
                    member,
                    "is_member",
                    False
                )
            )

        return False

    except Exception as error:

        logger.warning(
            "Join check failed: %s",
            error
        )

        return False


def missing_channels(
    user_id
):

    if not force_join_enabled():

        return []

    channels = get_locked_channels()

    missing = []

    for channel in channels:

        if not is_member(
            user_id,
            channel["chat_id"]
        ):

            missing.append(
                channel
            )

    return missing


def join_keyboard(
    channels
):

    keyboard = types.InlineKeyboardMarkup(
        row_width=1
    )

    for channel in channels:

        title = (
            channel["title"]
            or channel["username"]
            or "کانال"
        )

        link = get_channel_link(
            channel
        )

        if link:

            keyboard.add(
                types.InlineKeyboardButton(
                    f"📢 {title}",
                    url=link
                )
            )

    keyboard.add(
        types.InlineKeyboardButton(
            "🔄 بررسی عضویت",
            callback_data="check_join"
        )
    )

    return keyboard


def join_text():

    return (
        "🔒 <b>عضویت اجباری</b>\n\n"

        "برای استفاده از ربات باید ابتدا "
        "در کانال‌های مشخص‌شده عضو شوید.\n\n"

        "پس از عضویت، روی دکمه "
        "«بررسی عضویت» بزنید."
    )


def send_join_message(
    chat_id,
    channels
):

    bot.send_message(
        chat_id,

        join_text(),

        reply_markup=join_keyboard(
            channels
        )
    )


# ============================================================
# ACCESS CHECK
# ============================================================

def check_access(
    message
):

    user_id = message.from_user.id

    if is_admin(
        user_id
    ):

        return True

    if get_setting(
        "bot_enabled",
        "1"
    ) != "1":

        bot.send_message(
            message.chat.id,
            "⛔ ربات فعلاً غیرفعال است."
        )

        return False

    if get_setting(
        "maintenance",
        "0"
    ) == "1":

        bot.send_message(
            message.chat.id,
            "🔧 ربات در حال تعمیر است."
        )

        return False

    missing = missing_channels(
        user_id
    )

    if missing:

        send_join_message(
            message.chat.id,
            missing
        )

        return False

    return True


# ============================================================
# MISSIONS
# ============================================================

def get_active_missions():

    return query(
        """
        SELECT *
        FROM missions
        WHERE active = 1
        ORDER BY id DESC
        """
    ).fetchall()


def get_mission(
    mission_id
):

    return query(
        """
        SELECT *
        FROM missions
        WHERE id = ?
        """,
        (mission_id,)
    ).fetchone()


def has_completed_mission(
    user_id,
    mission_id
):

    row = query(
        """
        SELECT id
        FROM mission_progress
        WHERE user_id = ?
        AND mission_id = ?
        AND completed = 1
        """,
        (
            user_id,
            mission_id
        )
    ).fetchone()

    return row is not None


def mission_button_keyboard():

    keyboard = types.InlineKeyboardMarkup(
        row_width=1
    )

    missions = get_active_missions()

    if not missions:

        keyboard.add(
            types.InlineKeyboardButton(
                "❌ مأموریتی موجود نیست",
                callback_data="no_action"
            )
        )

    else:

        for mission in missions:

            title = (
                mission["title"]
                or "مأموریت"
            )

            reward = int(
                mission["reward"]
                or 0
            )

            keyboard.add(
                types.InlineKeyboardButton(
                    f"🎯 {title} | ⭐ {number(reward)}",
                    callback_data=(
                        f"mission:{mission['id']}"
                    )
                )
            )

    keyboard.add(
        types.InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="free_stars"
        )
    )

    return keyboard


def missions_page():

    missions = get_active_missions()

    if not missions:

        return (
            "🎯 <b>مأموریت‌ها</b>\n\n"
            "❌ فعلاً مأموریتی فعال نیست."
        )

    text = (
        "🎯 <b>مأموریت‌های Stars</b>\n\n"
        "یکی از مأموریت‌های زیر را انتخاب کنید:\n\n"
    )

    for index, mission in enumerate(
        missions,
        1
    ):

        title = (
            mission["title"]
            or "بدون عنوان"
        )

        reward = int(
            mission["reward"]
            or 0
        )

        text += (
            f"{index}. "
            f"<b>{title}</b>\n"
            f"   ⭐ پاداش: "
            f"<b>{number(reward)}</b>\n\n"
        )

    return text


def mission_type_name(
    mission_type
):

    names = {

        "channel":
            "عضویت در کانال",

        "join_channel":
            "عضویت در کانال",

        "bot":
            "استارت ربات",

        "start_bot":
            "استارت ربات",

        "manual":
            "بررسی دستی",

        "group":
            "عضویت در گروه"
    }

    return names.get(
        mission_type,
        mission_type or "نامشخص"
    )


def mission_page(
    mission
):

    mission_type = (
        mission["mission_type"]
        or ""
    )

    target = (
        mission["target"]
        or "تعیین نشده"
    )

    title = (
        mission["title"]
        or "مأموریت"
    )

    description = (
        mission["description"]
        or "توضیحی ثبت نشده است."
    )

    reward = int(
        mission["reward"]
        or 0
    )

    return (
        "🎯 <b>مأموریت</b>\n\n"

        f"📌 عنوان:\n"
        f"<b>{title}</b>\n\n"

        f"📝 توضیحات:\n"
        f"{description}\n\n"

        f"🔧 نوع:\n"
        f"<b>{mission_type_name(mission_type)}</b>\n\n"

        f"🎯 هدف:\n"
        f"<code>{target}</code>\n\n"

        f"🎁 پاداش:\n"
        f"<b>{number(reward)} Stars</b>\n\n"

        "بعد از انجام مأموریت، "
        "دکمه بررسی را بزنید."
    )


def mission_keyboard(
    mission_id
):

    keyboard = types.InlineKeyboardMarkup(
        row_width=1
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "✅ بررسی مأموریت",
            callback_data=(
                f"verify_mission:{mission_id}"
            )
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🔙 مأموریت‌ها",
            callback_data="active_missions"
        )
    )

    return keyboard


# ============================================================
# VERIFY MISSION
# ============================================================

def verify_mission(
    user_id,
    mission
):

    mission_id = int(
        mission["id"]
    )

    if has_completed_mission(
        user_id,
        mission_id
    ):

        return (
            False,
            "⚠️ این مأموریت را قبلاً انجام داده‌اید."
        )

    mission_type = (
        mission["mission_type"]
        or ""
    ).lower().strip()

    target = (
        mission["target"]
        or ""
    ).strip()

    verified = False

    # --------------------------------------------------------
    # CHANNEL
    # --------------------------------------------------------

    if mission_type in (
        "channel",
        "join_channel",
        "channel_join"
    ):

        if target:

            verified = is_member(
                user_id,
                target
            )

    # --------------------------------------------------------
    # GROUP
    # --------------------------------------------------------

    elif mission_type == "group":

        if target:

            verified = is_member(
                user_id,
                target
            )

    # --------------------------------------------------------
    # BOT
    # --------------------------------------------------------

    elif mission_type in (
        "bot",
        "start_bot"
    ):

        user = get_user(
            user_id
        )

        verified = (
            user is not None
        )

    # --------------------------------------------------------
    # MANUAL
    # --------------------------------------------------------

    elif mission_type == "manual":

        return (
            False,
            "⏳ این مأموریت نیاز به تأیید ادمین دارد."
        )

    if not verified:

        return (
            False,
            "❌ انجام مأموریت تأیید نشد.\n\n"
            "مطمئن شوید مرحله موردنظر را "
            "کامل انجام داده‌اید."
        )

    reward = int(
        mission["reward"]
        or 0
    )

    query(
        """
        INSERT OR IGNORE INTO mission_progress(
            mission_id,
            user_id,
            completed,
            completed_at
        )
        VALUES (?, ?, 1, ?)
        """,
        (
            mission_id,
            user_id,
            now()
        ),
        True
    )

    add_balance(
        user_id,
        reward
    )

    return (
        True,
        (
            "🎉 <b>مأموریت با موفقیت تأیید شد!</b>\n\n"
            f"🎁 پاداش: "
            f"<b>{number(reward)} Stars</b>\n\n"
            f"⭐ موجودی فعلی: "
            f"<b>{number(get_balance(user_id))} Stars</b>"
        )
    )


# ============================================================
# FREE STARS PAGE
# ============================================================

def free_stars_keyboard():

    keyboard = types.InlineKeyboardMarkup(
        row_width=1
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🎯 مأموریت‌ها",
            callback_data="active_missions"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "📦 سفارش‌های من",
            callback_data="my_orders"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="menu_stars"
        )
    )

    return keyboard


def free_stars_page():

    if get_setting(
        "free_stars",
        "1"
    ) != "1":

        return (
            "⭐ <b>Stars رایگان</b>\n\n"
            "❌ این بخش فعلاً غیرفعال است."
        )

    missions = get_active_missions()

    return (
        "⭐ <b>Stars رایگان</b>\n\n"

        "با انجام مأموریت‌های تعیین‌شده "
        "می‌توانید Stars دریافت کنید.\n\n"

        f"🎯 تعداد مأموریت‌های فعال: "
        f"<b>{len(missions)}</b>\n\n"

        "از دکمه زیر وارد مأموریت‌ها شوید."
    )


# ============================================================
# CALLBACK HANDLER
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data in (
            "check_join",
            "free_stars",
            "active_missions",
            "no_action"
        )
        or call.data.startswith(
            "mission:"
        )
        or call.data.startswith(
            "verify_mission:"
        )
)
def stars_mission_callback(
    call
):

    user_id = call.from_user.id

    ensure_user(
        call.from_user
    )

    data = call.data

    try:

        bot.answer_callback_query(
            call.id
        )

    except Exception:
        pass

    # --------------------------------------------------------
    # CHECK JOIN
    # --------------------------------------------------------

    if data == "check_join":

        missing = missing_channels(
            user_id
        )

        if missing:

            edit_message(
                call,
                join_text(),
                join_keyboard(
                    missing
                )
            )

            return

        edit_message(
            call,

            main_text(
                user_id
            ),

            main_keyboard(
                user_id
            )
        )

        return

    # --------------------------------------------------------
    # FREE STARS
    # --------------------------------------------------------

    if data == "free_stars":

        missing = missing_channels(
            user_id
        )

        if missing:

            edit_message(
                call,

                join_text(),

                join_keyboard(
                    missing
                )
            )

            return

        edit_message(
            call,

            free_stars_page(),

            free_stars_keyboard()
        )

        return

    # --------------------------------------------------------
    # MISSIONS
    # --------------------------------------------------------

    if data == "active_missions":

        edit_message(
            call,

            missions_page(),

            mission_button_keyboard()
        )

        return

    # --------------------------------------------------------
    # NO ACTION
    # --------------------------------------------------------

    if data == "no_action":

        try:

            bot.answer_callback_query(
                call.id,
                "❌ موردی وجود ندارد.",
                show_alert=True
            )

        except Exception:
            pass

        return

    # --------------------------------------------------------
    # MISSION DETAIL
    # --------------------------------------------------------

    if data.startswith(
        "mission:"
    ):

        try:

            mission_id = int(
                data.split(
                    ":",
                    1
                )[1]
            )

        except Exception:

            return

        mission = get_mission(
            mission_id
        )

        if mission is None:

            edit_message(
                call,

                "❌ مأموریت پیدا نشد.",

                back_button(
                    "active_missions"
                )
            )

            return

        if int(
            mission["active"]
        ) != 1:

            edit_message(
                call,

                "❌ این مأموریت غیرفعال شده است.",

                back_button(
                    "active_missions"
                )
            )

            return

        if has_completed_mission(
            user_id,
            mission_id
        ):

            text = (
                mission_page(
                    mission
                )

                +

                "\n\n"
                "✅ <b>این مأموریت قبلاً تکمیل شده است.</b>"
            )

            edit_message(
                call,

                text,

                back_button(
                    "active_missions"
                )
            )

            return

        edit_message(
            call,

            mission_page(
                mission
            ),

            mission_keyboard(
                mission_id
            )
        )

        return

    # --------------------------------------------------------
    # VERIFY
    # --------------------------------------------------------

    if data.startswith(
        "verify_mission:"
    ):

        try:

            mission_id = int(
                data.split(
                    ":",
                    1
                )[1]
            )

        except Exception:

            return

        mission = get_mission(
            mission_id
        )

        if mission is None:

            edit_message(
                call,

                "❌ مأموریت پیدا نشد.",

                back_button(
                    "active_missions"
                )
            )

            return

        success, result = verify_mission(
            user_id,
            mission
        )

        if success:

            edit_message(
                call,

                result,

                back_button(
                    "active_missions"
                )
            )

        else:

            edit_message(
                call,

                result,

                mission_keyboard(
                    mission_id
                )
            )

        return


# ============================================================
# FORCE JOIN COMMAND
# ============================================================

@bot.message_handler(
    commands=["check"]
)
def check_command(
    message
):

    ensure_user(
        message.from_user
    )

    missing = missing_channels(
        message.from_user.id
    )

    if missing:

        send_join_message(
            message.chat.id,
            missing
        )

        return

    bot.send_message(
        message.chat.id,

        "✅ <b>عضویت شما تأیید شد.</b>\n\n"
        "اکنون می‌توانید از ربات استفاده کنید.",

        reply_markup=main_keyboard(
            message.from_user.id
        )
    )


# ============================================================
# MISSIONS COMMAND
# ============================================================

@bot.message_handler(
    commands=["missions"]
)
def missions_command(
    message
):

    if not check_access(
        message
    ):

        return

    bot.send_message(
        message.chat.id,

        missions_page(),

        reply_markup=mission_button_keyboard()
    )


# ============================================================
# FREE STARS COMMAND
# ============================================================

@bot.message_handler(
    commands=["free"]
)
def free_command(
    message
):

    if not check_access(
        message
    ):

        return

    bot.send_message(
        message.chat.id,

        free_stars_page(),

        reply_markup=free_stars_keyboard()
    )


# ============================================================
# PART 3 COMPLETE
# ============================================================
# ============================================================
# STARS BOT
# PART 4/8
# GIFT CODES + TELEGRAM GIFTS
# ============================================================


# ============================================================
# GIFT MENU
# ============================================================

def gift_menu_keyboard():

    keyboard = types.InlineKeyboardMarkup(
        row_width=1
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🎁 وارد کردن کد هدیه",
            callback_data="enter_gift_code"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "⭐ کدهای Stars",
            callback_data="gift_help_stars"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🎁 کدهای Gift",
            callback_data="gift_help_gift"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="main_menu"
        )
    )

    return keyboard


def gift_menu_text():

    return (
        "🎁 <b>بخش کد هدیه</b>\n\n"

        "در این بخش می‌توانید کدهای هدیه "
        "دریافت‌شده را وارد کنید.\n\n"

        "⭐ کد Stars می‌تواند موجودی حساب "
        "شما را افزایش دهد.\n\n"

        "🎁 کد Gift می‌تواند اطلاعات یک "
        "هدیه تلگرامی را در اختیار شما قرار دهد.\n\n"

        "برای استفاده از کد، روی گزینه "
        "«وارد کردن کد هدیه» بزنید."
    )


# ============================================================
# GIFT CODE LOOKUP
# ============================================================

def get_gift_code(
    code
):

    return query(
        """
        SELECT *
        FROM gift_codes
        WHERE code = ?
        """,
        (code,)
    ).fetchone()


def gift_code_expired(
    row
):

    expires = (
        row["expires_at"]
        or ""
    ).strip()

    if not expires:
        return False

    try:

        expiry = datetime.strptime(
            expires,
            "%Y-%m-%d %H:%M:%S"
        )

        current = datetime.now(
            timezone.utc
        ).replace(
            tzinfo=None
        )

        return current >= expiry

    except Exception:

        return False


def gift_code_available(
    row
):

    if row is None:
        return False

    if int(
        row["active"]
        or 0
    ) != 1:

        return False

    if gift_code_expired(
        row
    ):

        return False

    max_uses = int(
        row["max_uses"]
        or 1
    )

    used = int(
        row["used_count"]
        or 0
    )

    if max_uses > 0 and used >= max_uses:

        return False

    return True


def user_used_gift_code(
    user_id,
    code_id
):

    row = query(
        """
        SELECT id
        FROM gift_code_uses
        WHERE user_id = ?
        AND code_id = ?
        """,
        (
            user_id,
            code_id
        )
    ).fetchone()

    return row is not None


# ============================================================
# REDEEM STARS CODE
# ============================================================

def redeem_stars_code(
    user_id,
    row
):

    code_id = int(
        row["id"]
    )

    if user_used_gift_code(
        user_id,
        code_id
    ):

        return (
            False,
            "⚠️ شما قبلاً از این کد استفاده کرده‌اید."
        )

    if not gift_code_available(
        row
    ):

        return (
            False,
            "❌ این کد منقضی شده یا ظرفیت آن تکمیل شده است."
        )

    amount = int(
        row["amount"]
        or 0
    )

    if amount <= 0:

        return (
            False,
            "❌ مقدار این کد نامعتبر است."
        )

    query(
        """
        INSERT INTO gift_code_uses(
            code_id,
            user_id,
            used_at
        )
        VALUES (?, ?, ?)
        """,
        (
            code_id,
            user_id,
            now()
        ),
        True
    )

    query(
        """
        UPDATE gift_codes

        SET used_count = used_count + 1

        WHERE id = ?
        """,
        (code_id,),
        True
    )

    add_balance(
        user_id,
        amount
    )

    return (
        True,
        (
            "🎉 <b>کد با موفقیت فعال شد!</b>\n\n"
            f"⭐ پاداش: "
            f"<b>{number(amount)} Stars</b>\n\n"
            f"💰 موجودی جدید: "
            f"<b>{number(get_balance(user_id))} Stars</b>"
        )
    )


# ============================================================
# REDEEM GIFT CODE
# ============================================================

def redeem_gift_code(
    user_id,
    row
):

    code_id = int(
        row["id"]
    )

    if user_used_gift_code(
        user_id,
        code_id
    ):

        return (
            False,
            "⚠️ شما قبلاً از این کد استفاده کرده‌اید."
        )

    if not gift_code_available(
        row
    ):

        return (
            False,
            "❌ این کد منقضی شده یا ظرفیت آن تکمیل شده است."
        )

    query(
        """
        INSERT INTO gift_code_uses(
            code_id,
            user_id,
            used_at
        )
        VALUES (?, ?, ?)
        """,
        (
            code_id,
            user_id,
            now()
        ),
        True
    )

    query(
        """
        UPDATE gift_codes

        SET used_count = used_count + 1

        WHERE id = ?
        """,
        (code_id,),
        True
    )

    gift_info = (
        row["gift_info"]
        or "اطلاعات Gift ثبت نشده است."
    )

    return (
        True,
        (
            "🎁 <b>کد Gift با موفقیت فعال شد!</b>\n\n"

            f"🎁 اطلاعات هدیه:\n"
            f"<b>{gift_info}</b>\n\n"

            "⚠️ دریافت یا ارسال واقعی Gift "
            "به امکانات رسمی Telegram و نوع Gift "
            "وابسته است."
        )
    )


# ============================================================
# REDEEM ANY CODE
# ============================================================

def redeem_code(
    user_id,
    code
):

    code = (
        code or ""
    ).strip()

    if not code:

        return (
            False,
            "❌ کد خالی است."
        )

    row = get_gift_code(
        code
    )

    if row is None:

        return (
            False,
            "❌ کد پیدا نشد."
        )

    code_type = (
        row["code_type"]
        or "stars"
    ).lower()

    if code_type == "stars":

        return redeem_stars_code(
            user_id,
            row
        )

    if code_type == "gift":

        return redeem_gift_code(
            user_id,
            row
        )

    return (
        False,
        "❌ نوع کد نامعتبر است."
    )


# ============================================================
# CODE INFO
# ============================================================

def gift_code_info(
    row
):

    code_type = (
        row["code_type"]
        or "stars"
    )

    max_uses = int(
        row["max_uses"]
        or 1
    )

    used = int(
        row["used_count"]
        or 0
    )

    remaining = max(
        max_uses - used,
        0
    )

    if code_type == "stars":

        reward = (
            f"⭐ {number(row['amount'])} Stars"
        )

    else:

        reward = (
            "🎁 Gift"
        )

    return (
        f"🎟 نوع کد: <b>{code_type}</b>\n"
        f"🎁 پاداش: <b>{reward}</b>\n"
        f"👥 استفاده: "
        f"<b>{used}/{max_uses}</b>\n"
        f"📌 باقی‌مانده: <b>{remaining}</b>"
    )


# ============================================================
# GIFT HELP
# ============================================================

def stars_code_help():

    return (
        "⭐ <b>کد Stars</b>\n\n"

        "کد Stars توسط ادمین ساخته می‌شود "
        "و می‌تواند برای یک یا چند کاربر قابل استفاده باشد.\n\n"

        "هر کاربر فقط یک‌بار می‌تواند "
        "از یک کد مشخص استفاده کند."
    )


def gift_code_help():

    return (
        "🎁 <b>کد Gift</b>\n\n"

        "کد Gift می‌تواند اطلاعات هدیه "
        "و در صورت وجود شناسه فایل استیکر "
        "را در خود داشته باشد.\n\n"

        "تعداد استفاده و زمان انقضا "
        "توسط ادمین تعیین می‌شود."
    )


# ============================================================
# GIFT CALLBACK
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data in (
            "menu_gift",
            "enter_gift_code",
            "gift_help_stars",
            "gift_help_gift"
        )
)
def gift_menu_callback(
    call
):

    user_id = call.from_user.id

    ensure_user(
        call.from_user
    )

    try:

        bot.answer_callback_query(
            call.id
        )

    except Exception:
        pass

    data = call.data

    if data == "menu_gift":

        edit_message(
            call,

            gift_menu_text(),

            gift_menu_keyboard()
        )

        return

    if data == "enter_gift_code":

        set_state(
            user_id,
            "redeem_gift_code"
        )

        edit_message(
            call,

            (
                "🎁 <b>وارد کردن کد</b>\n\n"

                "کد هدیه خود را ارسال کنید.\n\n"

                "مثال:\n"
                "<code>54378hao</code>\n\n"

                "برای لغو:\n"
                "<code>لغو</code>"
            ),

            back_button(
                "menu_gift"
            )
        )

        return

    if data == "gift_help_stars":

        edit_message(
            call,

            stars_code_help(),

            back_button(
                "menu_gift"
            )
        )

        return

    if data == "gift_help_gift":

        edit_message(
            call,

            gift_code_help(),

            back_button(
                "menu_gift"
            )
        )

        return


# ============================================================
# GIFT COMMAND
# ============================================================

@bot.message_handler(
    commands=["gifts", "gift"]
)
def gifts_command(
    message
):

    if not check_access(
        message
    ):

        return

    set_state(
        message.from_user.id,
        "redeem_gift_code"
    )

    bot.send_message(
        message.chat.id,

        (
            "🎁 <b>کد Gift</b>\n\n"
            "کد خود را ارسال کنید."
        ),

        reply_markup=back_button(
            "menu_gift"
        )
    )


# ============================================================
# GIFT TEXT STATE
# ============================================================

def handle_gift_code_text(
    message
):

    user_id = message.from_user.id

    code = (
        message.text or ""
    ).strip()

    if len(code) < 3:

        bot.send_message(
            message.chat.id,
            "❌ کد واردشده خیلی کوتاه است."
        )

        return True

    row = get_gift_code(
        code
    )

    if row is None:

        bot.send_message(
            message.chat.id,

            (
                "❌ <b>کد نامعتبر است.</b>\n\n"
                "این کد در سیستم پیدا نشد."
            )
        )

        return True

    if not gift_code_available(
        row
    ):

        bot.send_message(
            message.chat.id,

            (
                "❌ <b>کد قابل استفاده نیست.</b>\n\n"
                "ممکن است منقضی شده باشد "
                "یا ظرفیت استفاده از آن تکمیل شده باشد."
            )
        )

        clear_state(
            user_id
        )

        return True

    success, result = redeem_code(
        user_id,
        code
    )

    clear_state(
        user_id
    )

    bot.send_message(
        message.chat.id,
        result
    )

    return True


# ============================================================
# OVERRIDE TEXT STATE
# ============================================================

@bot.message_handler(
    content_types=["text"],
    func=lambda message:
        (
            get_state(
                message.from_user.id
            ) is not None
            and
            get_state(
                message.from_user.id
            )["state"] == "redeem_gift_code"
        )
)
def gift_state_handler(
    message
):

    if message.text and message.text.lower() in (
        "لغو",
        "cancel"
    ):

        clear_state(
            message.from_user.id
        )

        bot.send_message(
            message.chat.id,

            "❌ عملیات لغو شد.",

            reply_markup=main_keyboard(
                message.from_user.id
            )
        )

        return

    handle_gift_code_text(
        message
    )


# ============================================================
# ADMIN GIFT CODE HELPERS
# ============================================================

def create_stars_code(
    amount,
    max_uses=1,
    expires_at=""
):

    amount = int(
        amount
    )

    max_uses = int(
        max_uses
    )

    if amount <= 0:
        raise ValueError(
            "amount must be positive"
        )

    if max_uses <= 0:
        max_uses = 1

    code = unique_gift_code()

    query(
        """
        INSERT INTO gift_codes(
            code,
            code_type,
            amount,
            gift_info,
            sticker_file_id,
            max_uses,
            used_count,
            expires_at,
            active,
            created_at
        )
        VALUES(
            ?, 'stars', ?, '', '',
            ?, 0, ?, 1, ?
        )
        """,
        (
            code,
            amount,
            max_uses,
            expires_at,
            now()
        ),
        True
    )

    return code


def create_gift_code(
    gift_info,
    sticker_file_id="",
    max_uses=1,
    expires_at=""
):

    max_uses = int(
        max_uses
    )

    if max_uses <= 0:
        max_uses = 1

    code = unique_gift_code()

    query(
        """
        INSERT INTO gift_codes(
            code,
            code_type,
            amount,
            gift_info,
            sticker_file_id,
            max_uses,
            used_count,
            expires_at,
            active,
            created_at
        )
        VALUES(
            ?, 'gift', 0, ?, ?,
            ?, 0, ?, 1, ?
        )
        """,
        (
            code,
            gift_info,
            sticker_file_id,
            max_uses,
            expires_at,
            now()
        ),
        True
    )

    return code


def deactivate_gift_code(
    code
):

    query(
        """
        UPDATE gift_codes
        SET active = 0
        WHERE code = ?
        """,
        (
            code
        ),
        True
    )


# ============================================================
# GIFT STATISTICS
# ============================================================

def gift_statistics():

    total = query(
        """
        SELECT COUNT(*) AS c
        FROM gift_codes
        """
    ).fetchone()["c"]

    active = query(
        """
        SELECT COUNT(*) AS c
        FROM gift_codes
        WHERE active = 1
        """
    ).fetchone()["c"]

    stars = query(
        """
        SELECT COUNT(*) AS c
        FROM gift_codes
        WHERE code_type = 'stars'
        """
    ).fetchone()["c"]

    gifts = query(
        """
        SELECT COUNT(*) AS c
        FROM gift_codes
        WHERE code_type = 'gift'
        """
    ).fetchone()["c"]

    used = query(
        """
        SELECT COUNT(*) AS c
        FROM gift_code_uses
        """
    ).fetchone()["c"]

    return {
        "total": total,
        "active": active,
        "stars": stars,
        "gifts": gifts,
        "used": used
    }


# ============================================================
# PART 4 COMPLETE
# ============================================================
# ============================================================
# STARS BOT
# PART 5/8
# GIVEAWAY SYSTEM
# ============================================================


# ============================================================
# GIVEAWAY HELPERS
# ============================================================

def get_giveaway(
    giveaway_id
):

    return query(
        """
        SELECT *
        FROM giveaways
        WHERE id = ?
        """,
        (giveaway_id,)
    ).fetchone()


def active_giveaways():

    return query(
        """
        SELECT *
        FROM giveaways
        WHERE active = 1
        ORDER BY id DESC
        """
    ).fetchall()


def giveaway_participant_count(
    giveaway_id
):

    row = query(
        """
        SELECT COUNT(*) AS c
        FROM giveaway_participants
        WHERE giveaway_id = ?
        """,
        (giveaway_id,)
    ).fetchone()

    return int(
        row["c"]
    )


def is_giveaway_participant(
    giveaway_id,
    user_id
):

    row = query(
        """
        SELECT id
        FROM giveaway_participants
        WHERE giveaway_id = ?
        AND user_id = ?
        """,
        (
            giveaway_id,
            user_id
        )
    ).fetchone()

    return row is not None


def add_giveaway_participant(
    giveaway_id,
    user_id
):

    if is_giveaway_participant(
        giveaway_id,
        user_id
    ):

        return False

    query(
        """
        INSERT INTO giveaway_participants(
            giveaway_id,
            user_id,
            joined_at
        )
        VALUES (?, ?, ?)
        """,
        (
            giveaway_id,
            user_id,
            now()
        ),
        True
    )

    return True


# ============================================================
# GIVEAWAY TEXT
# ============================================================

def giveaway_prize_text(
    giveaway
):

    prize_type = (
        giveaway["prize_type"]
        or ""
    ).lower()

    amount = int(
        giveaway["prize_amount"]
        or 0
    )

    info = (
        giveaway["prize_info"]
        or ""
    )

    if prize_type == "stars":

        return (
            f"⭐ جایزه: "
            f"<b>{number(amount)} Stars</b>"
        )

    if prize_type == "gift":

        return (
            "🎁 جایزه: "
            f"<b>{info or 'Telegram Gift'}</b>"
        )

    return (
        f"🎁 جایزه: "
        f"<b>{info or 'جایزه ویژه'}</b>"
    )


def giveaway_status(
    giveaway
):

    end_time = (
        giveaway["end_time"]
        or ""
    ).strip()

    if not end_time:

        return "🟢 فعال"

    try:

        end = datetime.strptime(
            end_time,
            "%Y-%m-%d %H:%M:%S"
        )

        current = datetime.now(
            timezone.utc
        ).replace(
            tzinfo=None
        )

        if current >= end:
            return "🔴 پایان‌یافته"

        return "🟢 فعال"

    except Exception:

        return "🟢 فعال"


def giveaway_text(
    giveaway
):

    giveaway_id = giveaway["id"]

    title = (
        giveaway["title"]
        or "قرعه‌کشی"
    )

    description = (
        giveaway["description"]
        or ""
    )

    winners = int(
        giveaway["max_winners"]
        or 1
    )

    participants = giveaway_participant_count(
        giveaway_id
    )

    status = giveaway_status(
        giveaway
    )

    return (
        "🎯 <b>قرعه‌کشی جدید</b>\n\n"

        f"📌 <b>{title}</b>\n\n"

        f"{description}\n\n"

        f"{giveaway_prize_text(giveaway)}\n\n"

        f"👥 شرکت‌کنندگان: "
        f"<b>{number(participants)}</b>\n\n"

        f"🏆 تعداد برنده: "
        f"<b>{number(winners)}</b>\n\n"

        f"📊 وضعیت: {status}\n\n"

        "برای شرکت روی دکمه زیر بزنید."
    )


# ============================================================
# GIVEAWAY KEYBOARD
# ============================================================

def giveaway_keyboard(
    giveaway_id
):

    keyboard = types.InlineKeyboardMarkup(
        row_width=1
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🎯 شرکت در قرعه‌کشی",
            callback_data=(
                f"join_giveaway:{giveaway_id}"
            )
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "📊 وضعیت قرعه‌کشی",
            callback_data=(
                f"giveaway_info:{giveaway_id}"
            )
        )
    )

    return keyboard


def giveaways_list_keyboard():

    keyboard = types.InlineKeyboardMarkup(
        row_width=1
    )

    giveaways = active_giveaways()

    if not giveaways:

        keyboard.add(
            types.InlineKeyboardButton(
                "❌ قرعه‌کشی فعالی نیست",
                callback_data="no_action"
            )
        )

    else:

        for giveaway in giveaways:

            title = (
                giveaway["title"]
                or "قرعه‌کشی"
            )

            keyboard.add(
                types.InlineKeyboardButton(
                    f"🎯 {title}",
                    callback_data=(
                        f"view_giveaway:{giveaway['id']}"
                    )
                )
            )

    keyboard.add(
        types.InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="main_menu"
        )
    )

    return keyboard


# ============================================================
# GIVEAWAYS PAGE
# ============================================================

def giveaways_page():

    giveaways = active_giveaways()

    if not giveaways:

        return (
            "🎯 <b>قرعه‌کشی‌ها</b>\n\n"
            "❌ در حال حاضر قرعه‌کشی فعالی وجود ندارد."
        )

    text = (
        "🎯 <b>قرعه‌کشی‌های فعال</b>\n\n"
        "یک قرعه‌کشی را انتخاب کنید:\n\n"
    )

    for giveaway in giveaways:

        title = (
            giveaway["title"]
            or "قرعه‌کشی"
        )

        count = giveaway_participant_count(
            giveaway["id"]
        )

        text += (
            f"🎯 <b>{title}</b>\n"
            f"👥 شرکت‌کنندگان: "
            f"<b>{number(count)}</b>\n\n"
        )

    return text


# ============================================================
# GIVEAWAY CALLBACK
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data in (
            "menu_giveaways",
        )
        or call.data.startswith(
            "view_giveaway:"
        )
        or call.data.startswith(
            "join_giveaway:"
        )
        or call.data.startswith(
            "giveaway_info:"
        )
)
def giveaway_callback(
    call
):

    user_id = call.from_user.id

    ensure_user(
        call.from_user
    )

    try:

        bot.answer_callback_query(
            call.id
        )

    except Exception:
        pass

    data = call.data

    # --------------------------------------------------------
    # MENU
    # --------------------------------------------------------

    if data == "menu_giveaways":

        edit_message(
            call,

            giveaways_page(),

            giveaways_list_keyboard()
        )

        return

    # --------------------------------------------------------
    # VIEW
    # --------------------------------------------------------

    if data.startswith(
        "view_giveaway:"
    ):

        try:

            giveaway_id = int(
                data.split(
                    ":",
                    1
                )[1]
            )

        except Exception:

            return

        giveaway = get_giveaway(
            giveaway_id
        )

        if giveaway is None:

            edit_message(
                call,

                "❌ قرعه‌کشی پیدا نشد.",

                back_button(
                    "menu_giveaways"
                )
            )

            return

        edit_message(
            call,

            giveaway_text(
                giveaway
            ),

            giveaway_keyboard(
                giveaway_id
            )
        )

        return

    # --------------------------------------------------------
    # JOIN
    # --------------------------------------------------------

    if data.startswith(
        "join_giveaway:"
    ):

        try:

            giveaway_id = int(
                data.split(
                    ":",
                    1
                )[1]
            )

        except Exception:

            return

        giveaway = get_giveaway(
            giveaway_id
        )

        if giveaway is None:

            try:

                bot.answer_callback_query(
                    call.id,
                    "❌ قرعه‌کشی پیدا نشد.",
                    show_alert=True
                )

            except Exception:
                pass

            return

        if int(
            giveaway["active"]
            or 0
        ) != 1:

            try:

                bot.answer_callback_query(
                    call.id,
                    "❌ این قرعه‌کشی پایان یافته است.",
                    show_alert=True
                )

            except Exception:
                pass

            return

        if giveaway_status(
            giveaway
        ) != "🟢 فعال":

            try:

                bot.answer_callback_query(
                    call.id,
                    "⏰ زمان قرعه‌کشی تمام شده است.",
                    show_alert=True
                )

            except Exception:
                pass

            return

        missing = missing_channels(
            user_id
        )

        if missing:

            edit_message(
                call,

                join_text(),

                join_keyboard(
                    missing
                )
            )

            return

        if is_giveaway_participant(
            giveaway_id,
            user_id
        ):

            try:

                bot.answer_callback_query(
                    call.id,
                    "⚠️ شما قبلاً در این قرعه‌کشی شرکت کرده‌اید.",
                    show_alert=True
                )

            except Exception:
                pass

            return

        added = add_giveaway_participant(
            giveaway_id,
            user_id
        )

        if not added:

            return

        try:

            bot.answer_callback_query(
                call.id,
                "🎉 با موفقیت در قرعه‌کشی شرکت کردید!",
                show_alert=True
            )

        except Exception:
            pass

        updated = get_giveaway(
            giveaway_id
        )

        edit_message(
            call,

            giveaway_text(
                updated
            ),

            giveaway_keyboard(
                giveaway_id
            )
        )

        return

    # --------------------------------------------------------
    # INFO
    # --------------------------------------------------------

    if data.startswith(
        "giveaway_info:"
    ):

        try:

            giveaway_id = int(
                data.split(
                    ":",
                    1
                )[1]
            )

        except Exception:

            return

        giveaway = get_giveaway(
            giveaway_id
        )

        if giveaway is None:

            return

        count = giveaway_participant_count(
            giveaway_id
        )

        joined = is_giveaway_participant(
            giveaway_id,
            user_id
        )

        joined_text = (
            "✅ شما شرکت کرده‌اید."
            if joined
            else
            "❌ شما هنوز شرکت نکرده‌اید."
        )

        text = (
            f"📊 <b>وضعیت قرعه‌کشی</b>\n\n"

            f"🎯 عنوان:\n"
            f"<b>{giveaway['title']}</b>\n\n"

            f"👥 شرکت‌کنندگان:\n"
            f"<b>{number(count)}</b>\n\n"

            f"🏆 برندگان:\n"
            f"<b>{number(giveaway['max_winners'])}</b>\n\n"

            f"📌 وضعیت:\n"
            f"{giveaway_status(giveaway)}\n\n"

            f"{joined_text}"
        )

        edit_message(
            call,

            text,

            back_button(
                f"view_giveaway:{giveaway_id}"
            )
        )

        return


# ============================================================
# GIVEAWAY COMMAND
# ============================================================

@bot.message_handler(
    commands=["giveaways", "giveaway"]
)
def giveaways_command(
    message
):

    if not check_access(
        message
    ):

        return

    bot.send_message(
        message.chat.id,

        giveaways_page(),

        reply_markup=giveaways_list_keyboard()
    )


# ============================================================
# ADMIN GIVEAWAY CREATION
# ============================================================

def create_giveaway(
    title,
    description,
    prize_type,
    prize_amount=0,
    prize_info="",
    sticker_file_id="",
    max_winners=1,
    end_time="",
    channel_id=""
):

    if not title:

        raise ValueError(
            "title is required"
        )

    max_winners = int(
        max_winners
    )

    if max_winners <= 0:
        max_winners = 1

    prize_amount = int(
        prize_amount or 0
    )

    query(
        """
        INSERT INTO giveaways(
            title,
            description,
            prize_type,
            prize_amount,
            prize_info,
            sticker_file_id,
            channel_id,
            message_id,
            max_winners,
            end_time,
            active,
            created_at
        )
        VALUES(
            ?, ?, ?, ?, ?, ?,
            ?, 0, ?, ?, 1, ?
        )
        """,
        (
            title,
            description,
            prize_type,
            prize_amount,
            prize_info,
            sticker_file_id,
            channel_id,
            max_winners,
            end_time,
            now()
        ),
        True
    )

    row = query(
        """
        SELECT id
        FROM giveaways
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()

    return int(
        row["id"]
    )


def close_giveaway(
    giveaway_id
):

    query(
        """
        UPDATE giveaways
        SET active = 0
        WHERE id = ?
        """,
        (
            giveaway_id
        ),
        True
    )


# ============================================================
# RANDOM WINNER SELECTION
# ============================================================

def giveaway_winners(
    giveaway_id
):

    giveaway = get_giveaway(
        giveaway_id
    )

    if giveaway is None:
        return []

    count = int(
        giveaway["max_winners"]
        or 1
    )

    rows = query(
        """
        SELECT user_id
        FROM giveaway_participants
        WHERE giveaway_id = ?
        """,
        (
            giveaway_id
        )
    ).fetchall()

    users = [
        int(row["user_id"])
        for row in rows
    ]

    if not users:
        return []

    if count > len(users):
        count = len(users)

    import random

    return random.sample(
        users,
        count
    )


def finish_giveaway(
    giveaway_id
):

    giveaway = get_giveaway(
        giveaway_id
    )

    if giveaway is None:

        return (
            False,
            "❌ قرعه‌کشی پیدا نشد."
        )

    if int(
        giveaway["active"]
        or 0
    ) != 1:

        return (
            False,
            "⚠️ قرعه‌کشی قبلاً بسته شده است."
        )

    winners = giveaway_winners(
        giveaway_id
    )

    if not winners:

        close_giveaway(
            giveaway_id
        )

        return (
            False,
            "❌ هیچ شرکت‌کننده‌ای وجود ندارد."
        )

    close_giveaway(
        giveaway_id
    )

    return (
        True,
        winners
    )


# ============================================================
# WINNER TEXT
# ============================================================

def winner_text(
    giveaway,
    winners
):

    title = (
        giveaway["title"]
        or "قرعه‌کشی"
    )

    text = (
        "🏆 <b>نتیجه قرعه‌کشی</b>\n\n"

        f"🎯 <b>{title}</b>\n\n"

        f"{giveaway_prize_text(giveaway)}\n\n"

        "🏆 برندگان:\n"
    )

    for index, user_id in enumerate(
        winners,
        1
    ):

        text += (
            f"{index}. "
            f"<code>{user_id}</code>\n"
        )

    return text


# ============================================================
# SEND GIVEAWAY TO CHAT
# ============================================================

def publish_giveaway(
    giveaway_id,
    chat_id
):

    giveaway = get_giveaway(
        giveaway_id
    )

    if giveaway is None:

        return None

    sent = bot.send_message(
        chat_id,

        giveaway_text(
            giveaway
        ),

        reply_markup=giveaway_keyboard(
            giveaway_id
        )
    )

    query(
        """
        UPDATE giveaways

        SET channel_id = ?,
            message_id = ?

        WHERE id = ?
        """,
        (
            str(chat_id),
            sent.message_id,
            giveaway_id
        ),
        True
    )

    return sent


# ============================================================
# GIVEAWAY ADMIN UTILITIES
# ============================================================

def giveaway_count():

    row = query(
        """
        SELECT COUNT(*) AS c
        FROM giveaways
        """
    ).fetchone()

    return int(
        row["c"]
    )


def active_giveaway_count():

    row = query(
        """
        SELECT COUNT(*) AS c
        FROM giveaways
        WHERE active = 1
        """
    ).fetchone()

    return int(
        row["c"]
    )


def giveaway_statistics():

    total = giveaway_count()

    active = active_giveaway_count()

    participants = query(
        """
        SELECT COUNT(*) AS c
        FROM giveaway_participants
        """
    ).fetchone()["c"]

    return (
        total,
        active,
        int(participants)
    )


# ============================================================
# PART 5 COMPLETE
# ============================================================
# ============================================================
# STARS BOT
# PART 6/8
# BALANCE + TELEGRAM STARS PAYMENTS + ORDERS
# ============================================================


# ============================================================
# BALANCE MENU
# ============================================================

def balance_menu_keyboard():

    keyboard = types.InlineKeyboardMarkup(
        row_width=1
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "💳 شارژ حساب",
            callback_data="charge_account"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "💰 موجودی من",
            callback_data="my_balance"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "📦 سفارش‌های من",
            callback_data="my_orders"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="main_menu"
        )
    )

    return keyboard


def balance_page(
    user_id
):

    balance = get_balance(
        user_id
    )

    rate = get_setting(
        "stars_rate",
        "4000"
    )

    try:
        rate = int(rate)
    except Exception:
        rate = 4000

    return (
        "💰 <b>حساب کاربری</b>\n\n"

        f"⭐ موجودی Stars:\n"
        f"<b>{number(balance)}</b>\n\n"

        f"💵 نرخ فعلی:\n"
        f"<b>هر 1 Star = {number(rate)} تومان</b>\n\n"

        "برای افزایش موجودی، "
        "روی «شارژ حساب» بزنید."
    )


# ============================================================
# CHARGE MENU
# ============================================================

def charge_menu_keyboard():

    keyboard = types.InlineKeyboardMarkup(
        row_width=2
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "⭐ 10 Stars",
            callback_data="charge:10"
        ),
        types.InlineKeyboardButton(
            "⭐ 25 Stars",
            callback_data="charge:25"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "⭐ 50 Stars",
            callback_data="charge:50"
        ),
        types.InlineKeyboardButton(
            "⭐ 100 Stars",
            callback_data="charge:100"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "✏️ مبلغ دلخواه",
            callback_data="charge_custom"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="menu_balance"
        )
    )

    return keyboard


def charge_page():

    rate = get_setting(
        "stars_rate",
        "4000"
    )

    try:
        rate = int(rate)
    except Exception:
        rate = 4000

    return (
        "💳 <b>شارژ حساب</b>\n\n"

        f"⭐ نرخ فعلی:\n"
        f"<b>1 Star = {number(rate)} تومان</b>\n\n"

        "مقدار موردنظر خود را انتخاب کنید."
    )


# ============================================================
# PAYMENT DATA
# ============================================================

def create_payment_order(
    user_id,
    stars
):

    stars = int(stars)

    rate = get_setting(
        "stars_rate",
        "4000"
    )

    try:
        rate = int(rate)
    except Exception:
        rate = 4000

    toman = stars * rate

    order_code = unique_order_code()

    query(
        """
        INSERT INTO orders(
            order_code,
            user_id,
            order_type,
            amount,
            stars,
            status,
            description,
            created_at
        )
        VALUES(
            ?, ?, 'charge',
            ?, ?, 'pending',
            ?, ?
        )
        """,
        (
            order_code,
            user_id,
            toman,
            stars,
            f"شارژ {stars} Stars",
            now()
        ),
        True
    )

    row = query(
        """
        SELECT *
        FROM orders
        WHERE order_code = ?
        """,
        (
            order_code
        )
    ).fetchone()

    return row


# ============================================================
# TELEGRAM STARS INVOICE
# ============================================================

def send_stars_invoice(
    message,
    stars
):

    stars = int(stars)

    if stars <= 0:

        bot.send_message(
            message.chat.id,
            "❌ تعداد Stars باید بیشتر از صفر باشد."
        )

        return

    order = create_payment_order(
        message.from_user.id,
        stars
    )

    order_code = order["order_code"]

    prices = [
        types.LabeledPrice(
            label=f"{stars} Telegram Stars",
            amount=stars
        )
    ]

    try:

        bot.send_invoice(
            message.chat.id,

            title="شارژ حساب",

            description=(
                f"شارژ حساب به مقدار "
                f"{stars} Stars"
            ),

            invoice_payload=(
                f"charge:{order_code}"
            ),

            provider_token="",

            currency="XTR",

            prices=prices,

            start_parameter=(
                f"charge_{order_code}"
            )
        )

        set_state(
            message.from_user.id,
            None
        )

    except Exception as error:

        logger.exception(
            "Invoice error: %s",
            error
        )

        query(
            """
            UPDATE orders
            SET status = 'failed'
            WHERE order_code = ?
            """,
            (
                order_code
            ),
            True
        )

        bot.send_message(
            message.chat.id,

            (
                "❌ ایجاد پرداخت انجام نشد.\n\n"
                "لطفاً دوباره تلاش کنید."
            )
        )


# ============================================================
# PRE-CHECKOUT
# ============================================================

@bot.pre_checkout_query_handler(
    func=lambda query: True
)
def process_pre_checkout(
    pre_checkout
):

    payload = (
        pre_checkout.invoice_payload
        or ""
    )

    if not payload.startswith(
        "charge:"
    ):

        bot.answer_pre_checkout_query(
            pre_checkout.id,
            ok=False,
            error_message=(
                "پرداخت نامعتبر است."
            )
        )

        return

    order_code = payload.split(
        ":",
        1
    )[1]

    order = query(
        """
        SELECT *
        FROM orders
        WHERE order_code = ?
        """,
        (
            order_code
        )
    ).fetchone()

    if order is None:

        bot.answer_pre_checkout_query(
            pre_checkout.id,
            ok=False,
            error_message=(
                "سفارش پیدا نشد."
            )
        )

        return

    if order["status"] != "pending":

        bot.answer_pre_checkout_query(
            pre_checkout.id,
            ok=False,
            error_message=(
                "این سفارش قبلاً پردازش شده است."
            )
        )

        return

    bot.answer_pre_checkout_query(
        pre_checkout.id,
        ok=True
    )


# ============================================================
# SUCCESSFUL PAYMENT
# ============================================================

@bot.message_handler(
    content_types=[
        "successful_payment"
    ]
)
def successful_payment(
    message
):

    payment = (
        message.successful_payment
    )

    payload = (
        payment.invoice_payload
        or ""
    )

    if not payload.startswith(
        "charge:"
    ):

        return

    order_code = payload.split(
        ":",
        1
    )[1]

    order = query(
        """
        SELECT *
        FROM orders
        WHERE order_code = ?
        """,
        (
            order_code
        )
    ).fetchone()

    if order is None:

        logger.error(
            "Payment order not found: %s",
            order_code
        )

        return

    if order["status"] == "paid":

        return

    stars = int(
        order["stars"]
        or 0
    )

    query(
        """
        UPDATE orders

        SET status = 'paid',
            telegram_charge_id = ?

        WHERE order_code = ?
        """,
        (
            payment.telegram_payment_charge_id,
            order_code
        ),
        True
    )

    add_balance(
        message.from_user.id,
        stars
    )

    new_balance = get_balance(
        message.from_user.id
    )

    bot.send_message(
        message.chat.id,

        (
            "✅ <b>پرداخت موفق بود!</b>\n\n"

            f"⭐ مبلغ شارژ:\n"
            f"<b>{number(stars)} Stars</b>\n\n"

            f"💰 موجودی جدید:\n"
            f"<b>{number(new_balance)} Stars</b>\n\n"

            f"🧾 شماره سفارش:\n"
            f"<code>{order_code}</code>"
        )
    )

    notify_admin_payment(
        message.from_user,
        order,
        stars
    )


# ============================================================
# ADMIN PAYMENT NOTIFICATION
# ============================================================

def notify_admin_payment(
    user,
    order,
    stars
):

    try:

        username = (
            f"@{user.username}"
            if user.username
            else "ندارد"
        )

        text = (
            "💳 <b>پرداخت جدید</b>\n\n"

            f"👤 نام:\n"
            f"<b>{escape(user.first_name or '')}</b>\n\n"

            f"🆔 ID:\n"
            f"<code>{user.id}</code>\n\n"

            f"🔗 Username:\n"
            f"<code>{username}</code>\n\n"

            f"⭐ Stars:\n"
            f"<b>{number(stars)}</b>\n\n"

            f"🧾 سفارش:\n"
            f"<code>{order['order_code']}</code>"
        )

        bot.send_message(
            ADMIN_ID,
            text
        )

    except Exception as error:

        logger.warning(
            "Admin payment notification failed: %s",
            error
        )


# ============================================================
# CUSTOM CHARGE
# ============================================================

def custom_charge_text():

    return (
        "✏️ <b>شارژ دلخواه</b>\n\n"

        "تعداد Stars موردنظر را ارسال کنید.\n\n"

        "مثال:\n"
        "<code>75</code>\n\n"

        "برای لغو:\n"
        "<code>لغو</code>"
    )


def start_custom_charge(
    user_id
):

    set_state(
        user_id,
        "custom_charge"
    )


def handle_custom_charge(
    message
):

    user_id = message.from_user.id

    text = (
        message.text or ""
    ).strip()

    if text.lower() in (
        "لغو",
        "cancel"
    ):

        clear_state(
            user_id
        )

        bot.send_message(
            message.chat.id,
            "❌ عملیات لغو شد."
        )

        return True

    try:

        stars = int(
            text
        )

    except Exception:

        bot.send_message(
            message.chat.id,
            "❌ فقط عدد وارد کنید."
        )

        return True

    if stars <= 0:

        bot.send_message(
            message.chat.id,
            "❌ تعداد Stars نامعتبر است."
        )

        return True

    if stars > 100000:

        bot.send_message(
            message.chat.id,
            "❌ مقدار واردشده بیش از حد مجاز است."
        )

        return True

    clear_state(
        user_id
    )

    send_stars_invoice(
        message,
        stars
    )

    return True


# ============================================================
# BALANCE CALLBACK
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data in (
            "menu_balance",
            "charge_account",
            "my_balance",
            "charge_custom"
        )
        or call.data.startswith(
            "charge:"
        )
)
def balance_callback(
    call
):

    user_id = call.from_user.id

    ensure_user(
        call.from_user
    )

    try:

        bot.answer_callback_query(
            call.id
        )

    except Exception:
        pass

    data = call.data

    # --------------------------------------------------------
    # BALANCE MENU
    # --------------------------------------------------------

    if data == "menu_balance":

        edit_message(
            call,

            balance_page(
                user_id
            ),

            balance_menu_keyboard()
        )

        return

    # --------------------------------------------------------
    # CHARGE ACCOUNT
    # --------------------------------------------------------

    if data == "charge_account":

        edit_message(
            call,

            charge_page(),

            charge_menu_keyboard()
        )

        return

    # --------------------------------------------------------
    # MY BALANCE
    # --------------------------------------------------------

    if data == "my_balance":

        edit_message(
            call,

            balance_page(
                user_id
            ),

            balance_menu_keyboard()
        )

        return

    # --------------------------------------------------------
    # CUSTOM
    # --------------------------------------------------------

    if data == "charge_custom":

        start_custom_charge(
            user_id
        )

        edit_message(
            call,

            custom_charge_text(),

            back_button(
                "charge_account"
            )
        )

        return

    # --------------------------------------------------------
    # FIXED AMOUNT
    # --------------------------------------------------------

    if data.startswith(
        "charge:"
    ):

        try:

            stars = int(
                data.split(
                    ":",
                    1
                )[1]
            )

        except Exception:

            return

        fake_message = call.message

        send_stars_invoice(
            fake_message,
            stars
        )

        return


# ============================================================
# ORDERS
# ============================================================

def get_user_orders(
    user_id,
    limit=10
):

    return query(
        """
        SELECT *
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (
            user_id,
            limit
        )
    ).fetchall()


def order_status_text(
    status
):

    values = {

        "pending":
            "⏳ در انتظار پرداخت",

        "paid":
            "✅ پرداخت شده",

        "failed":
            "❌ ناموفق",

        "completed":
            "✅ تکمیل شده",

        "cancelled":
            "🚫 لغو شده"
    }

    return values.get(
        status,
        status
    )


def my_orders_text(
    user_id
):

    orders = get_user_orders(
        user_id
    )

    if not orders:

        return (
            "📦 <b>سفارش‌های من</b>\n\n"
            "❌ هنوز سفارشی ثبت نکرده‌اید."
        )

    text = (
        "📦 <b>آخرین سفارش‌های شما</b>\n\n"
    )

    for order in orders:

        text += (
            f"🧾 <code>{order['order_code']}</code>\n"
            f"📌 {order['description'] or 'سفارش'}\n"
            f"⭐ {number(order['stars'] or 0)}\n"
            f"📊 {order_status_text(order['status'])}\n\n"
        )

    return text


def orders_keyboard():

    keyboard = types.InlineKeyboardMarkup(
        row_width=1
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🔄 بروزرسانی",
            callback_data="my_orders"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="menu_balance"
        )
    )

    return keyboard


@bot.callback_query_handler(
    func=lambda call:
        call.data == "my_orders"
)
def my_orders_callback(
    call
):

    user_id = call.from_user.id

    ensure_user(
        call.from_user
    )

    try:

        bot.answer_callback_query(
            call.id
        )

    except Exception:
        pass

    edit_message(
        call,

        my_orders_text(
            user_id
        ),

        orders_keyboard()
    )


# ============================================================
# CHARGE COMMAND
# ============================================================

@bot.message_handler(
    commands=["charge", "balance"]
)
def charge_command(
    message
):

    if not check_access(
        message
    ):

        return

    bot.send_message(
        message.chat.id,

        balance_page(
            message.from_user.id
        ),

        reply_markup=balance_menu_keyboard()
    )


# ============================================================
# MY ORDERS COMMAND
# ============================================================

@bot.message_handler(
    commands=["orders"]
)
def orders_command(
    message
):

    if not check_access(
        message
    ):

        return

    bot.send_message(
        message.chat.id,

        my_orders_text(
            message.from_user.id
        ),

        reply_markup=orders_keyboard()
    )


# ============================================================
# CUSTOM CHARGE STATE
# ============================================================

@bot.message_handler(
    content_types=["text"],
    func=lambda message:
        (
            get_state(
                message.from_user.id
            ) is not None
            and
            get_state(
                message.from_user.id
            )["state"] == "custom_charge"
        )
)
def custom_charge_state_handler(
    message
):

    handle_custom_charge(
        message
    )


# ============================================================
# ADMIN MANUAL BALANCE
# ============================================================

def admin_add_balance(
    user_id,
    amount,
    reason="شارژ توسط ادمین"
):

    user_id = int(
        user_id
    )

    amount = int(
        amount
    )

    if amount <= 0:

        raise ValueError(
            "amount must be positive"
        )

    ensure_user_id(
        user_id
    )

    add_balance(
        user_id,
        amount
    )

    query(
        """
        INSERT INTO balance_logs(
            user_id,
            amount,
            reason,
            admin_id,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user_id,
            amount,
            reason,
            ADMIN_ID,
            now()
        ),
        True
    )

    return get_balance(
        user_id
    )


def admin_remove_balance(
    user_id,
    amount,
    reason="کسر توسط ادمین"
):

    user_id = int(
        user_id
    )

    amount = int(
        amount
    )

    current = get_balance(
        user_id
    )

    if amount <= 0:

        raise ValueError(
            "amount must be positive"
        )

    if current < amount:

        raise ValueError(
            "insufficient balance"
        )

    add_balance(
        user_id,
        -amount
    )

    query(
        """
        INSERT INTO balance_logs(
            user_id,
            amount,
            reason,
            admin_id,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user_id,
            -amount,
            reason,
            ADMIN_ID,
            now()
        ),
        True
    )

    return get_balance(
        user_id
    )


# ============================================================
# BALANCE HISTORY
# ============================================================

def balance_history(
    user_id,
    limit=20
):

    return query(
        """
        SELECT *
        FROM balance_logs
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (
            user_id,
            limit
        )
    ).fetchall()


# ============================================================
# PART 6 COMPLETE
# =================================
# ================= PART 7/8 =================

def admin_keyboard():
    k = types.InlineKeyboardMarkup(row_width=2)
    k.add(
        types.InlineKeyboardButton("📦 سفارشات", callback_data="a_orders"),
        types.InlineKeyboardButton("👥 کاربران", callback_data="a_users"),
        types.InlineKeyboardButton("⭐ Stars", callback_data="a_stars"),
        types.InlineKeyboardButton("🎁 کد هدیه", callback_data="a_codes"),
        types.InlineKeyboardButton("🎯 قرعه‌کشی", callback_data="a_give"),
        types.InlineKeyboardButton("🎯 مأموریت‌ها", callback_data="a_missions"),
        types.InlineKeyboardButton("🔒 قفل کانال", callback_data="a_channels"),
        types.InlineKeyboardButton("📢 همگانی", callback_data="a_broadcast"),
        types.InlineKeyboardButton("⚙️ تنظیمات", callback_data="a_settings"),
        types.InlineKeyboardButton("📊 آمار", callback_data="a_stats"),
        types.InlineKeyboardButton("💰 شارژ کاربر", callback_data="a_charge"),
        types.InlineKeyboardButton("➖ کسر موجودی", callback_data="a_remove")
    )
    return k


def back_admin():
    k = types.InlineKeyboardMarkup()
    k.add(types.InlineKeyboardButton("🔙 پنل مدیریت", callback_data="a_home"))
    return k


def admin_home_text():
    try:
        users = query(
            "SELECT COUNT(*) c FROM users"
        ).fetchone()["c"]
    except Exception:
        users = 0

    return (
        "👑 <b>پنل مدیریت</b>\n\n"
        f"👥 کاربران: <b>{users}</b>\n"
        f"🟢 وضعیت: <b>فعال</b>\n\n"
        "بخش موردنظر را انتخاب کنید:"
    )


@bot.message_handler(commands=["admin"])
def admin_cmd(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ دسترسی ندارید.")
        return

    clear_state(message.from_user.id)

    bot.send_message(
        message.chat.id,
        admin_home_text(),
        reply_markup=admin_keyboard()
    )


@bot.callback_query_handler(
    func=lambda c: c.data.startswith("a_")
)
def admin_menu(call):

    if not is_admin(call.from_user.id):
        bot.answer_callback_query(
            call.id,
            "⛔ دسترسی ندارید.",
            show_alert=True
        )
        return

    bot.answer_callback_query(call.id)

    d = call.data

    if d == "a_home":
        edit_message(
            call,
            admin_home_text(),
            admin_keyboard()
        )

    elif d == "a_orders":
        admin_orders(call)

    elif d == "a_users":
        admin_users(call)

    elif d == "a_stars":
        admin_stars(call)

    elif d == "a_codes":
        admin_codes(call)

    elif d == "a_give":
        admin_giveaways(call)

    elif d == "a_missions":
        admin_missions(call)

    elif d == "a_channels":
        admin_channels(call)

    elif d == "a_broadcast":
        admin_broadcast(call)

    elif d == "a_settings":
        admin_settings(call)

    elif d == "a_stats":
        admin_stats(call)

    elif d == "a_charge":
        set_state(
            call.from_user.id,
            "charge_user"
        )
        edit_message(
            call,
            "💰 <b>شارژ کاربر</b>\n\n"
            "آیدی عددی کاربر را بفرستید.",
            back_admin()
        )

    elif d == "a_remove":
        set_state(
            call.from_user.id,
            "remove_user"
        )
        edit_message(
            call,
            "➖ <b>کسر موجودی</b>\n\n"
            "آیدی عددی کاربر را بفرستید.",
            back_admin()
        )


def admin_orders(call):
    try:
        rows = query(
            "SELECT * FROM orders "
            "ORDER BY id DESC LIMIT 10"
        ).fetchall()
    except Exception:
        rows = []

    text = "📦 <b>سفارشات</b>\n\n"

    if not rows:
        text += "❌ سفارشی وجود ندارد."
    else:
        for r in rows:
            text += (
                f"🧾 <code>{r['order_code']}</code>\n"
                f"👤 {r['user_id']}\n"
                f"⭐ {r['stars']}\n"
                f"📌 {r['status']}\n\n"
            )

    edit_message(
        call,
        text,
        back_admin()
    )


def admin_users(call):
    try:
        total = query(
            "SELECT COUNT(*) c FROM users"
        ).fetchone()["c"]
    except Exception:
        total = 0

    k = types.InlineKeyboardMarkup(row_width=1)
    k.add(
        types.InlineKeyboardButton(
            "🔎 جستجوی کاربر",
            callback_data="a_find"
        ),
        types.InlineKeyboardButton(
            "💰 شارژ کاربر",
            callback_data="a_charge"
        ),
        types.InlineKeyboardButton(
            "➖ کسر موجودی",
            callback_data="a_remove"
        ),
        types.InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="a_home"
        )
    )

    edit_message(
        call,
        f"👥 <b>کاربران</b>\n\n"
        f"تعداد کاربران: <b>{total}</b>",
        k
    )


def admin_stars(call):
    rate = get_setting(
        "stars_rate",
        "4000"
    )

    k = types.InlineKeyboardMarkup(row_width=1)
    k.add(
        types.InlineKeyboardButton(
            "💵 تغییر قیمت Stars",
            callback_data="a_rate"
        ),
        types.InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="a_home"
        )
    )

    edit_message(
        call,
        "⭐ <b>مدیریت Stars</b>\n\n"
        f"قیمت فعلی هر Star:\n"
        f"<b>{rate} تومان</b>",
        k
    )


def admin_codes(call):
    k = types.InlineKeyboardMarkup(row_width=1)
    k.add(
        types.InlineKeyboardButton(
            "⭐ ساخت کد Stars",
            callback_data="a_make_star_code"
        ),
        types.InlineKeyboardButton(
            "🎁 ساخت کد Gift",
            callback_data="a_make_gift_code"
        ),
        types.InlineKeyboardButton(
            "🚫 غیرفعال کردن کد",
            callback_data="a_disable_code"
        ),
        types.InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="a_home"
        )
    )

    edit_message(
        call,
        "🎁 <b>مدیریت کدهای هدیه</b>\n\n"
        "از گزینه‌های زیر استفاده کنید.",
        k
    )


def admin_giveaways(call):
    k = types.InlineKeyboardMarkup(row_width=1)
    k.add(
        types.InlineKeyboardButton(
            "➕ قرعه‌کشی جدید",
            callback_data="a_new_give"
        ),
        types.InlineKeyboardButton(
            "📢 انتشار قرعه‌کشی",
            callback_data="a_publish_give"
        ),
        types.InlineKeyboardButton(
            "🏆 انتخاب برنده",
            callback_data="a_finish_give"
        ),
        types.InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="a_home"
        )
    )

    edit_message(
        call,
        "🎯 <b>مدیریت قرعه‌کشی</b>\n\n"
        "ساخت، انتشار و پایان قرعه‌کشی.",
        k
    )


def admin_missions(call):
    k = types.InlineKeyboardMarkup(row_width=1)
    k.add(
        types.InlineKeyboardButton(
            "➕ مأموریت جدید",
            callback_data="a_new_mission"
        ),
        types.InlineKeyboardButton(
            "🗑 حذف مأموریت",
            callback_data="a_del_mission"
        ),
        types.InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="a_home"
        )
    )

    edit_message(
        call,
        "🎯 <b>مأموریت‌ها</b>\n\n"
        "ادمین می‌تواند کارهای لازم برای "
        "دریافت Stars را تعیین کند.",
        k
    )


def admin_channels(call):
    k = types.InlineKeyboardMarkup(row_width=1)
    k.add(
        types.InlineKeyboardButton(
            "➕ قفل کانال",
            callback_data="a_add_channel"
        ),
        types.InlineKeyboardButton(
            "➖ حذف کانال",
            callback_data="a_del_channel"
        ),
        types.InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="a_home"
        )
    )

    edit_message(
        call,
        "🔒 <b>قفل عضویت</b>\n\n"
        "تا زمانی که کاربر عضو کانال‌های "
        "قفل‌شده نباشد، دسترسی محدود می‌شود.",
        k
    )


def admin_broadcast(call):
    k = types.InlineKeyboardMarkup(row_width=1)
    k.add(
        types.InlineKeyboardButton(
            "📢 ارسال به کاربران",
            callback_data="a_start_broadcast"
        ),
        types.InlineKeyboardButton(
            "📣 ارسال به کانال",
            callback_data="a_channel_broadcast"
        ),
        types.InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="a_home"
        )
    )

    edit_message(
        call,
        "📢 <b>ارسال همگانی</b>\n\n"
        "پیام را برای کاربران یا کانال ارسال کنید.",
        k
    )


def admin_settings(call):
    enabled = get_setting(
        "bot_enabled",
        "1"
    )

    join = get_setting(
        "force_join",
        "1"
    )

    free = get_setting(
        "free_stars",
        "1"
    )

    k = types.InlineKeyboardMarkup(row_width=1)
    k.add(
        types.InlineKeyboardButton(
            "🤖 روشن/خاموش ربات",
            callback_data="a_toggle_bot"
        ),
        types.InlineKeyboardButton(
            "🔒 قفل عضویت",
            callback_data="a_toggle_join"
        ),
        types.InlineKeyboardButton(
            "⭐ Stars رایگان",
            callback_data="a_toggle_free"
        ),
        types.InlineKeyboardButton(
            "🔙 برگشت",
            callback_data="a_home"
        )
    )

    edit_message(
        call,
        "⚙️ <b>تنظیمات</b>\n\n"
        f"🤖 ربات: {'🟢' if enabled == '1' else '🔴'}\n"
        f"🔒 عضویت اجباری: {'🟢' if join == '1' else '🔴'}\n"
        f"⭐ Stars رایگان: {'🟢' if free == '1' else '🔴'}",
        k
    )


def admin_stats(call):
    try:
        users = query(
            "SELECT COUNT(*) c FROM users"
        ).fetchone()["c"]

        orders = query(
            "SELECT COUNT(*) c FROM orders"
        ).fetchone()["c"]

        stars = query(
            "SELECT COALESCE(SUM(stars),0) s "
            "FROM orders WHERE status='paid'"
        ).fetchone()["s"]
    except Exception:
        users = orders = stars = 0

    edit_message(
        call,
        "📊 <b>آمار ربات</b>\n\n"
        f"👥 کاربران: <b>{users}</b>\n"
        f"📦 سفارشات: <b>{orders}</b>\n"
        f"⭐ Stars پرداخت‌شده: <b>{stars}</b>",
        back_admin()
    )


# -------- ADMIN ACTIONS --------

@bot.callback_query_handler(
    func=lambda c: c.data in [
        "a_rate",
        "a_find",
        "a_make_star_code",
        "a_make_gift_code",
        "a_disable_code",
        "a_new_give",
        "a_publish_give",
        "a_finish_give",
        "a_new_mission",
        "a_del_mission",
        "a_add_channel",
        "a_del_channel",
        "a_start_broadcast",
        "a_channel_broadcast",
        "a_toggle_bot",
        "a_toggle_join",
        "a_toggle_free"
    ]
)
def admin_actions(call):

    if not is_admin(call.from_user.id):
        return

    bot.answer_callback_query(call.id)

    d = call.data

    states = {
        "a_rate": "set_rate",
        "a_find": "find_user",
        "a_make_star_code": "make_star_code",
        "a_make_gift_code": "make_gift_code",
        "a_disable_code": "disable_code",
        "a_new_give": "new_give",
        "a_publish_give": "publish_give",
        "a_finish_give": "finish_give",
        "a_new_mission": "new_mission",
        "a_del_mission": "del_mission",
        "a_add_channel": "add_channel",
        "a_del_channel": "del_channel",
        "a_start_broadcast": "broadcast",
        "a_channel_broadcast": "channel_broadcast"
    }

    if d in states:
        set_state(
            call.from_user.id,
            states[d]
        )

    if d == "a_rate":
        msg = "💵 قیمت هر Star را به تومان بفرستید."

    elif d == "a_find":
        msg = "🔎 آیدی عددی کاربر را بفرستید."

    elif d == "a_make_star_code":
        msg = (
            "⭐ ساخت کد Stars\n\n"
            "فرمت:\n"
            "<code>مقدار | تعداد استفاده</code>\n\n"
            "مثال:\n"
            "<code>100 | 10</code>"
        )

    elif d == "a_make_gift_code":
        msg = (
            "🎁 ساخت کد Gift\n\n"
            "فرمت:\n"
            "<code>نام گیفت | تعداد استفاده</code>\n\n"
            "مثال:\n"
            "<code>Teddy 15 Stars | 1</code>"
        )

    elif d == "a_disable_code":
        msg = "🚫 کد موردنظر را بفرستید."

    elif d == "a_new_give":
        msg = (
            "🎯 قرعه‌کشی جدید\n\n"
            "فرمت:\n"
            "<code>عنوان | جایزه | برنده‌ها</code>"
        )

    elif d == "a_publish_give":
        msg = (
            "📢 انتشار قرعه‌کشی\n\n"
            "فرمت:\n"
            "<code>ID قرعه‌کشی | ID کانال</code>"
        )

    elif d == "a_finish_give":
        msg = "🏆 ID قرعه‌کشی را بفرستید."

    elif d == "a_new_mission":
        msg = (
            "🎯 مأموریت جدید\n\n"
            "فرمت:\n"
            "<code>عنوان | نوع | هدف | پاداش</code>"
        )

    elif d == "a_del_mission":
        msg = "🗑 ID مأموریت را بفرستید."

    elif d == "a_add_channel":
        msg = (
            "🔒 ID کانالی که ربات در آن ادمین است "
            "را بفرستید."
        )

    elif d == "a_del_channel":
        msg = "➖ ID کانال را بفرستید."

    elif d == "a_start_broadcast":
        msg = "📢 پیام موردنظر را ارسال کنید."

    elif d == "a_channel_broadcast":
        msg = (
            "📣 پیام را ارسال کنید.\n"
            "در مرحله بعد کانال مشخص می‌شود."
        )

    elif d == "a_toggle_bot":
        toggle_setting("bot_enabled", "1")
        admin_settings(call)
        return

    elif d == "a_toggle_join":
        toggle_setting("force_join", "1")
        admin_settings(call)
        return

    elif d == "a_toggle_free":
        toggle_setting("free_stars", "1")
        admin_settings(call)
        return

    else:
        return

    edit_message(
        call,
        msg,
        back_admin()
    )


# ================= END PART 7 =================
# ================= PART 8/8 =================

# -------- ADMIN TEXT PROCESSOR --------

@bot.message_handler(
    content_types=["text"],
    func=lambda m:
        is_admin(m.from_user.id)
        and get_state(m.from_user.id) is not None
)
def admin_text_processor(message):

    uid = message.from_user.id
    state_data = get_state(uid)

    if not state_data:
        return

    state = state_data["state"]
    text = (message.text or "").strip()

    if text.lower() in ["لغو", "cancel"]:
        clear_state(uid)
        bot.send_message(
            message.chat.id,
            "❌ عملیات لغو شد.",
            reply_markup=admin_keyboard()
        )
        return

    # ---------- RATE ----------

    if state == "set_rate":

        try:
            rate = int(text)

            if rate <= 0:
                raise ValueError

            set_setting(
                "stars_rate",
                str(rate)
            )

            clear_state(uid)

            bot.send_message(
                message.chat.id,
                f"✅ نرخ تغییر کرد.\n\n"
                f"⭐ هر Star = "
                f"<b>{rate:,} تومان</b>",
                reply_markup=admin_keyboard()
            )

        except Exception:
            bot.send_message(
                message.chat.id,
                "❌ فقط یک عدد معتبر وارد کنید."
            )

        return

    # ---------- FIND USER ----------

    if state == "find_user":

        try:
            target = int(text)
        except Exception:
            bot.send_message(
                message.chat.id,
                "❌ ID نامعتبر است."
            )
            return

        user = get_user(target)

        clear_state(uid)

        if not user:
            bot.send_message(
                message.chat.id,
                "❌ کاربر پیدا نشد.",
                reply_markup=admin_keyboard()
            )
            return

        username = user["username"] or "ندارد"

        bot.send_message(
            message.chat.id,

            "👤 <b>اطلاعات کاربر</b>\n\n"
            f"🆔 <code>{user['user_id']}</code>\n"
            f"👤 {user['first_name'] or ''}\n"
            f"🔗 @{username}\n"
            f"⭐ موجودی: "
            f"<b>{user['balance']}</b> Stars",

            reply_markup=admin_keyboard()
        )

        return

    # ---------- CHARGE USER ----------

    if state == "charge_user":

        try:
            target = int(text)
        except Exception:
            bot.send_message(
                message.chat.id,
                "❌ ID نامعتبر است."
            )
            return

        if not get_user(target):
            bot.send_message(
                message.chat.id,
                "❌ کاربر پیدا نشد."
            )
            return

        set_state(
            uid,
            "charge_amount",
            target
        )

        bot.send_message(
            message.chat.id,
            "⭐ مقدار Stars را بفرستید."
        )

        return

    # ---------- CHARGE AMOUNT ----------

    if state == "charge_amount":

        try:
            amount = int(text)

            if amount <= 0:
                raise ValueError

        except Exception:
            bot.send_message(
                message.chat.id,
                "❌ مقدار نامعتبر است."
            )
            return

        target = state_data.get("data")

        try:
            add_balance(
                int(target),
                amount
            )
        except Exception:
            bot.send_message(
                message.chat.id,
                "❌ عملیات انجام نشد."
            )
            return

        clear_state(uid)

        bot.send_message(
            message.chat.id,
            "✅ حساب کاربر شارژ شد.\n\n"
            f"👤 <code>{target}</code>\n"
            f"⭐ +{amount} Stars",
            reply_markup=admin_keyboard()
        )

        try:
            bot.send_message(
                int(target),
                "💰 <b>حساب شما شارژ شد!</b>\n\n"
                f"⭐ مقدار: <b>{amount}</b> Stars"
            )
        except Exception:
            pass

        return

    # ---------- REMOVE USER ----------

    if state == "remove_user":

        try:
            target = int(text)
        except Exception:
            bot.send_message(
                message.chat.id,
                "❌ ID نامعتبر است."
            )
            return

        if not get_user(target):
            bot.send_message(
                message.chat.id,
                "❌ کاربر پیدا نشد."
            )
            return

        set_state(
            uid,
            "remove_amount",
            target
        )

        bot.send_message(
            message.chat.id,
            "➖ مقدار Stars را بفرستید."
        )

        return

    # ---------- REMOVE AMOUNT ----------

    if state == "remove_amount":

        try:
            amount = int(text)

            if amount <= 0:
                raise ValueError

        except Exception:
            bot.send_message(
                message.chat.id,
                "❌ مقدار نامعتبر است."
            )
            return

        target = state_data.get("data")

        try:
            remove_balance(
                int(target),
                amount
            )
        except Exception:
            bot.send_message(
                message.chat.id,
                "❌ عملیات انجام نشد."
            )
            return

        clear_state(uid)

        bot.send_message(
            message.chat.id,
            "✅ موجودی کسر شد.\n\n"
            f"👤 <code>{target}</code>\n"
            f"➖ {amount} Stars",
            reply_markup=admin_keyboard()
        )

        return

    # ---------- STAR CODE ----------

    if state == "make_star_code":

        parts = [
            x.strip()
            for x in text.split("|")
        ]

        if len(parts) != 2:
            bot.send_message(
                message.chat.id,
                "❌ فرمت اشتباه است."
            )
            return

        try:
            amount = int(parts[0])
            uses = int(parts[1])

            if amount <= 0 or uses <= 0:
                raise ValueError

            code = create_stars_code(
                amount,
                uses
            )

        except Exception:
            bot.send_message(
                message.chat.id,
                "❌ اطلاعات نامعتبر است."
            )
            return

        clear_state(uid)

        bot.send_message(
            message.chat.id,
            "🎟 <b>کد ساخته شد</b>\n\n"
            f"⭐ مقدار: <b>{amount}</b>\n"
            f"👥 استفاده: <b>{uses}</b>\n\n"
            f"🔑 کد:\n"
            f"<code>{code}</code>",
            reply_markup=admin_keyboard()
        )

        return

    # ---------- GIFT CODE ----------

    if state == "make_gift_code":

        parts = [
            x.strip()
            for x in text.split("|")
        ]

        if len(parts) != 2:
            bot.send_message(
                message.chat.id,
                "❌ فرمت اشتباه است."
            )
            return

        gift = parts[0]

        try:
            uses = int(parts[1])

            if uses <= 0:
                raise ValueError

            code = create_gift_code(
                gift,
                "",
                uses
            )

        except Exception:
            bot.send_message(
                message.chat.id,
                "❌ اطلاعات نامعتبر است."
            )
            return

        clear_state(uid)

        bot.send_message(
            message.chat.id,
            "🎁 <b>کد Gift ساخته شد</b>\n\n"
            f"🎁 جایزه: <b>{gift}</b>\n"
            f"👥 استفاده: <b>{uses}</b>\n\n"
            f"🔑 کد:\n"
            f"<code>{code}</code>",
            reply_markup=admin_keyboard()
        )

        return

    # ---------- DISABLE CODE ----------

    if state == "disable_code":

        try:
            deactivate_gift_code(text)
        except Exception:
            pass

        clear_state(uid)

        bot.send_message(
            message.chat.id,
            "✅ کد غیرفعال شد.",
            reply_markup=admin_keyboard()
        )

        return

    # ---------- NEW GIVEAWAY ----------

    if state == "new_give":

        parts = [
            x.strip()
            for x in text.split("|")
        ]

        if len(parts) != 3:
            bot.send_message(
                message.chat.id,
                "❌ فرمت:\n"
                "<code>عنوان | جایزه | تعداد برنده</code>"
            )
            return

        title = parts[0]
        prize = parts[1]

        try:
            winners = int(parts[2])

            if winners <= 0:
                raise ValueError

            gid = create_giveaway(
                title,
                "",
                "gift",
                0,
                prize,
                "",
                winners
            )

        except Exception:
            bot.send_message(
                message.chat.id,
                "❌ اطلاعات نامعتبر است."
            )
            return

        clear_state(uid)

        bot.send_message(
            message.chat.id,
            "🎯 <b>قرعه‌کشی ساخته شد</b>\n\n"
            f"🆔 ID: <code>{gid}</code>\n"
            f"🏷 {title}\n"
            f"🎁 {prize}\n"
            f"🏆 برنده‌ها: {winners}",
            reply_markup=admin_keyboard()
        )

        return

    # ---------- PUBLISH GIVEAWAY ----------

    if state == "publish_give":

        parts = [
            x.strip()
            for x in text.split("|")
        ]

        if len(parts) != 2:
            bot.send_message(
                message.chat.id,
                "❌ فرمت:\n"
                "<code>ID | ID کانال</code>"
            )
            return

        try:
            gid = int(parts[0])
            channel = int(parts[1])

            result = publish_giveaway(
                gid,
                channel
            )

        except Exception:
            result = False

        clear_state(uid)

        bot.send_message(
            message.chat.id,
            "✅ منتشر شد."
            if result
            else
            "❌ انتشار ناموفق بود.",
            reply_markup=admin_keyboard()
        )

        return

    # ---------- FINISH GIVEAWAY ----------

    if state == "finish_give":

        try:
            gid = int(text)
            success, result = finish_giveaway(gid)
        except Exception:
            success = False
            result = "❌ ID نامعتبر است."

        clear_state(uid)

        bot.send_message(
            message.chat.id,
            str(result),
            reply_markup=admin_keyboard()
        )

        return

    # ---------- NEW MISSION ----------

    if state == "new_mission":

        parts = [
            x.strip()
            for x in text.split("|")
        ]

        if len(parts) != 4:
            bot.send_message(
                message.chat.id,
                "❌ فرمت:\n"
                "<code>عنوان | نوع | هدف | پاداش</code>"
            )
            return

        try:
            title = parts[0]
            mtype = parts[1]
            target = parts[2]
            reward = int(parts[3])

            query(
                "INSERT INTO missions "
                "(title,mission_type,target,reward,active) "
                "VALUES (?,?,?,?,1)",
                (
                    title,
                    mtype,
                    target,
                    reward
                ),
                True
            )

        except Exception:
            bot.send_message(
                message.chat.id,
                "❌ ساخت مأموریت ناموفق بود."
            )
            return

        clear_state(uid)

        bot.send_message(
            message.chat.id,
            "✅ مأموریت ساخته شد.",
            reply_markup=admin_keyboard()
        )

        return

    # ---------- DELETE MISSION ----------

    if state == "del_mission":

        try:
            mid = int(text)

            query(
                "DELETE FROM missions WHERE id=?",
                (mid,),
                True
            )

        except Exception:
            bot.send_message(
                message.chat.id,
                "❌ ID نامعتبر است."
            )
            return

        clear_state(uid)

        bot.send_message(
            message.chat.id,
            "✅ مأموریت حذف شد.",
            reply_markup=admin_keyboard()
        )

        return

    # ---------- ADD CHANNEL ----------

    if state == "add_channel":

        try:
            chat = bot.get_chat(int(text))

            query(
                "INSERT OR REPLACE INTO locked_channels "
                "(chat_id,title,username,active) "
                "VALUES (?,?,?,1)",
                (
                    str(chat.id),
                    chat.title or "",
                    chat.username or ""
                ),
                True
            )

        except Exception:
            bot.send_message(
                message.chat.id,
                "❌ کانال پیدا نشد.\n"
                "مطمئن شوید ربات ادمین کانال است."
            )
            return

        clear_state(uid)

        bot.send_message(
            message.chat.id,
            "✅ کانال قفل شد.",
            reply_markup=admin_keyboard()
        )

        return

    # ---------- DELETE CHANNEL ----------

    if state == "del_channel":

        query(
            "UPDATE locked_channels "
            "SET active=0 WHERE chat_id=?",
            (text,),
            True
        )

        clear_state(uid)

        bot.send_message(
            message.chat.id,
            "✅ قفل کانال حذف شد.",
            reply_markup=admin_keyboard()
        )

        return

    # ---------- BROADCAST ----------

    if state == "broadcast":

        clear_state(uid)

        rows = query(
            "SELECT user_id FROM users "
            "WHERE blocked=0"
        ).fetchall()

        sent = 0

        for row in rows:

            try:
                bot.send_message(
                    int(row["user_id"]),
                    text
                )
                sent += 1
            except Exception:
                pass

        bot.send_message(
            message.chat.id,
            f"📢 ارسال انجام شد.\n\n"
            f"✅ موفق: <b>{sent}</b>",
            reply_markup=admin_keyboard()
        )

        return

    # ---------- CHANNEL BROADCAST ----------

    if state == "channel_broadcast":

        set_state(
            uid,
            "channel_broadcast_id",
            text
        )

        bot.send_message(
            message.chat.id,
            "🆔 حالا ID کانال را بفرستید."
        )

        return

    if state == "channel_broadcast_id":

        channel = state_data.get("data")

        try:
            bot.send_message(
                int(text),
                channel
            )

        except Exception:
            pass

        clear_state(uid)

        bot.send_message(
            message.chat.id,
            "📢 ارسال انجام شد.",
            reply_markup=admin_keyboard()
        )

        return


# ============================================================
# USER PROFILE
# ============================================================

@bot.message_handler(commands=["profile"])
def profile_command(message):

    user = get_user(
        message.from_user.id
    )

    if not user:
        bot.reply_to(
            message,
            "❌ حساب شما پیدا نشد."
        )
        return

    rate = get_setting(
        "stars_rate",
        "4000"
    )

    balance = int(
        user["balance"] or 0
    )

    value = balance * int(rate)

    bot.send_message(
        message.chat.id,

        "👤 <b>پروفایل شما</b>\n\n"
        f"🆔 ID:\n"
        f"<code>{message.from_user.id}</code>\n\n"
        f"👤 نام:\n"
        f"{message.from_user.first_name or ''}\n\n"
        f"⭐ موجودی:\n"
        f"<b>{balance}</b> Stars\n\n"
        f"💰 ارزش موجودی:\n"
        f"<b>{value:,} تومان</b>"
    )


# ============================================================
# GIFT COMMAND
# ============================================================

@bot.message_handler(commands=["Gifts"])
def gifts_command(message):

    set_state(
        message.from_user.id,
        "use_gift_code"
    )

    bot.send_message(
        message.chat.id,

        "🎁 <b>کد Gift</b>\n\n"
        "کد خود را ارسال کنید.\n\n"
        "مثال:\n"
        "<code>54378hao</code>"
    )


@bot.message_handler(
    content_types=["text"],
    func=lambda m:
        (
            get_state(m.from_user.id)
            is not None
            and
            get_state(m.from_user.id)["state"]
            == "use_gift_code"
        )
)
def use_gift_code(message):

    code = message.text.strip()

    try:
        result = redeem_code(
            message.from_user.id,
            code
        )
    except Exception:
        result = "❌ کد نامعتبر یا منقضی شده است."

    clear_state(
        message.from_user.id
    )

    bot.send_message(
        message.chat.id,
        str(result)
    )


# ============================================================
# START
# ============================================================

@bot.message_handler(commands=["start"])
def start_command(message):

    ensure_user(
        message.from_user
    )

    if not check_force_join(
        message.from_user.id
    ):
        send_join_message(
            message
        )
        return

    k = types.InlineKeyboardMarkup(row_width=2)

    k.add(
        types.InlineKeyboardButton(
            "⭐ Stars رایگان",
            callback_data="free_stars"
        ),
        types.InlineKeyboardButton(
            "🎯 قرعه‌کشی",
            callback_data="giveaways"
        )
    )

    k.add(
        types.InlineKeyboardButton(
            "💰 شارژ حساب",
            callback_data="charge"
        ),
        types.InlineKeyboardButton(
            "👤 پروفایل",
            callback_data="profile"
        )
    )

    k.add(
        types.InlineKeyboardButton(
            "🎁 کد هدیه",
            callback_data="gift_code"
        )
    )

    bot.send_message(
        message.chat.id,

        "👋 <b>خوش آمدید!</b>\n\n"
        "از منوی زیر استفاده کنید:",

        reply_markup=k
    )


# ============================================================
# FINAL RUN
# ============================================================

if __name__ == "__main__":

    print(
        "================================"
    )

    print(
        "⭐ Stars Bot"
    )

    print(
        "🤖 Bot is starting..."
    )

    print(
        "================================"
    )

    while True:

        try:
            bot.infinity_polling(
                timeout=30,
                long_polling_timeout=30
            )

        except Exception as e:

            print(
                "Polling error:",
                e
            )

            time.sleep(5)

# ================= END 8/8 =================
