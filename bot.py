# -*- coding: utf-8 -*-

import io
import os
import json
import html
import traceback

import telebot

from PIL import (
    Image,
    ImageDraw,
    ImageFont,
    ImageFilter
)


# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = "8617545814:AAFAofo_nV39gFT1-IgfXu-esnGgXol62r4"

ADMIN_ID = 7530457395

SETTINGS_FILE = "welcome_settings.json"


DEFAULT_WELCOME = (
    "👋 {mention} عزیز، خوش اومدی به {group} ❤️"
)


# =========================================================
# BOT
# =========================================================

bot = telebot.TeleBot(
    BOT_TOKEN,
    parse_mode="HTML"
)


# =========================================================
# COLORS
# =========================================================

WHITE = (
    245,
    245,
    255,
    255
)

SOFT_WHITE = (
    215,
    220,
    245,
    255
)

MUTED = (
    145,
    155,
    195,
    255
)

BLUE = (
    60,
    170,
    255,
    255
)

PURPLE = (
    155,
    70,
    255,
    255
)

PINK = (
    255,
    65,
    190,
    255
)


# =========================================================
# LOAD SETTINGS
# =========================================================

def load_settings():

    try:

        if not os.path.exists(
            SETTINGS_FILE
        ):

            return {
                "welcome_text":
                DEFAULT_WELCOME
            }

        with open(
            SETTINGS_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if not isinstance(
            data,
            dict
        ):

            return {
                "welcome_text":
                DEFAULT_WELCOME
            }

        text = data.get(
            "welcome_text",
            DEFAULT_WELCOME
        )

        if not isinstance(
            text,
            str
        ):

            text = DEFAULT_WELCOME

        if not text.strip():

            text = DEFAULT_WELCOME

        return {
            "welcome_text":
            text
        }

    except Exception as e:

        print(
            "SETTINGS LOAD ERROR:",
            e
        )

        return {
            "welcome_text":
            DEFAULT_WELCOME
        }


# =========================================================
# SAVE SETTINGS
# =========================================================

def save_settings(data):

    try:

        with open(
            SETTINGS_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2
            )

        return True

    except Exception as e:

        print(
            "SETTINGS SAVE ERROR:",
            e
        )

        return False


# =========================================================
# GLOBAL SETTINGS
# =========================================================

settings = load_settings()


# =========================================================
# ADMIN CHECK
# =========================================================

def is_admin(message):

    try:

        return (
            message.from_user is not None
            and
            message.from_user.id == ADMIN_ID
        )

    except Exception:

        return False


# =========================================================
# FONT PATHS
# =========================================================

FONT_NORMAL_PATHS = [

    "/usr/share/fonts/truetype/dejavu/"
    "DejaVuSans.ttf",

    "/usr/share/fonts/truetype/liberation2/"
    "LiberationSans-Regular.ttf",

    "/data/data/com.termux/files/usr/share/"
    "fonts/truetype/dejavu/"
    "DejaVuSans.ttf",

    "/storage/emulated/0/Fonts/"
    "DejaVuSans.ttf"
]


FONT_BOLD_PATHS = [

    "/usr/share/fonts/truetype/dejavu/"
    "DejaVuSans-Bold.ttf",

    "/usr/share/fonts/truetype/liberation2/"
    "LiberationSans-Bold.ttf",

    "/data/data/com.termux/files/usr/share/"
    "fonts/truetype/dejavu/"
    "DejaVuSans-Bold.ttf",

    "/storage/emulated/0/Fonts/"
    "DejaVuSans-Bold.ttf"
]


# =========================================================
# GET FONT
# =========================================================

def get_font(
    size,
    bold=False
):

    paths = (
        FONT_BOLD_PATHS
        if bold
        else FONT_NORMAL_PATHS
    )

    for path in paths:

        try:

            if os.path.exists(path):

                return ImageFont.truetype(
                    path,
                    size
                )

        except Exception:
            pass

    try:

        return ImageFont.truetype(
            "DejaVuSans-Bold.ttf"
            if bold
            else "DejaVuSans.ttf",
            size
        )

    except Exception:

        return ImageFont.load_default()


# =========================================================
# FIT FONT
# =========================================================

def fit_font(
    draw,
    text,
    max_width,
    start_size,
    bold=False
):

    if not text:

        return get_font(
            start_size,
            bold
        )

    size = start_size

    while size >= 18:

        font = get_font(
            size,
            bold
        )

        try:

            box = draw.textbbox(
                (0, 0),
                text,
                font=font
            )

            width = (
                box[2]
                - box[0]
            )

            if width <= max_width:

                return font

        except Exception:
            pass

        size -= 2

    return get_font(
        18,
        bold
    )


# =========================================================
# CENTER TEXT
# =========================================================

def draw_center_text(
    draw,
    text,
    center_x,
    y,
    font,
    fill
):

    box = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    text_width = (
        box[2]
        - box[0]
    )

    x = (
        center_x
        - text_width / 2
    )

    draw.text(
        (x, y),
        text,
        font=font,
        fill=fill
    )


# =========================================================
# GLOW CIRCLE
# =========================================================

def glow_circle(
    base,
    x,
    y,
    radius,
    color,
    blur=35
):

    layer = Image.new(
        "RGBA",
        base.size,
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(
        layer
    )

    draw.ellipse(
        (
            x - radius,
            y - radius,
            x + radius,
            y + radius
        ),
        fill=color
    )

    layer = layer.filter(
        ImageFilter.GaussianBlur(
            blur
        )
    )

    base.alpha_composite(
        layer
    )


# =========================================================
# NEON LINE
# =========================================================

def neon_line(
    base,
    points,
    color,
    width=3
):

    glow = Image.new(
        "RGBA",
        base.size,
        (0, 0, 0, 0)
    )

    gd = ImageDraw.Draw(
        glow
    )

    gd.line(
        points,
        fill=color,
        width=width + 16,
        joint="curve"
    )

    glow = glow.filter(
        ImageFilter.GaussianBlur(9)
    )

    base.alpha_composite(
        glow
    )

    draw = ImageDraw.Draw(
        base
    )

    draw.line(
        points,
        fill=color,
        width=width,
        joint="curve"
    )


# =========================================================
# BACKGROUND
# =========================================================

def make_background(
    width,
    height
):

    image = Image.new(
        "RGBA",
        (width, height),
        (7, 8, 24, 255)
    )

    pixels = image.load()

    for y in range(height):

        for x in range(width):

            nx = x / width
            ny = y / height

            r = int(
                7
                + 22 * nx
                + 12 * ny
            )

            g = int(
                8
                + 5 * nx
            )

            b = int(
                28
                + 55 * (1 - nx)
                + 25 * (1 - ny)
            )

            pixels[x, y] = (
                min(r, 255),
                min(g, 255),
                min(b, 255),
                255
            )

    return image
    # =========================================================
# DEFAULT AVATAR
# =========================================================

def default_avatar(size):

    avatar = Image.new(
        "RGBA",
        (size, size),
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(
        avatar
    )

    draw.ellipse(
        (
            2,
            2,
            size - 2,
            size - 2
        ),
        fill=(
            28,
            30,
            65,
            255
        )
    )

    cx = size // 2

    head = int(
        size * 0.30
    )

    draw.ellipse(
        (
            cx - head,
            int(size * 0.15),
            cx + head,
            int(size * 0.15)
            + head * 2
        ),
        fill=(
            190,
            195,
            225,
            255
        )
    )

    draw.rounded_rectangle(
        (
            int(size * 0.18),
            int(size * 0.55),
            int(size * 0.82),
            int(size * 1.02)
        ),
        radius=int(size * 0.18),
        fill=(
            105,
            75,
            220,
            255
        )
    )

    return avatar


# =========================================================
# GET PROFILE PHOTO
# =========================================================

def get_profile_photo(user_id):

    try:

        photos = (
            bot.get_user_profile_photos(
                user_id,
                limit=1
            )
        )

        if photos is None:
            return None

        if photos.total_count <= 0:
            return None

        if not photos.photos:
            return None

        photo = (
            photos.photos[0][-1]
        )

        file_info = bot.get_file(
            photo.file_id
        )

        data = bot.download_file(
            file_info.file_path
        )

        if not data:
            return None

        return data

    except Exception as e:

        print(
            "PROFILE PHOTO ERROR:",
            e
        )

        return None


# =========================================================
# CIRCLE AVATAR
# =========================================================

def circle_avatar(
    data,
    size
):

    try:

        original = Image.open(
            io.BytesIO(data)
        ).convert("RGB")

        width, height = (
            original.size
        )

        side = min(
            width,
            height
        )

        left = (
            width - side
        ) // 2

        top = (
            height - side
        ) // 2

        original = original.crop(
            (
                left,
                top,
                left + side,
                top + side
            )
        )

        original = original.resize(
            (size, size),
            Image.Resampling.LANCZOS
        )

        result = Image.new(
            "RGBA",
            (size, size),
            (0, 0, 0, 0)
        )

        mask = Image.new(
            "L",
            (size, size),
            0
        )

        mask_draw = ImageDraw.Draw(
            mask
        )

        mask_draw.ellipse(
            (
                0,
                0,
                size - 1,
                size - 1
            ),
            fill=255
        )

        result.paste(
            original,
            (0, 0),
            mask
        )

        return result

    except Exception as e:

        print(
            "CIRCLE AVATAR ERROR:",
            e
        )

        return default_avatar(
            size
        )


# =========================================================
# AVATAR RINGS
# =========================================================

def draw_rings(
    base,
    cx,
    cy,
    avatar_size
):

    glow = Image.new(
        "RGBA",
        base.size,
        (0, 0, 0, 0)
    )

    gd = ImageDraw.Draw(
        glow
    )

    rings = [

        (
            avatar_size // 2 + 10,
            BLUE,
            4
        ),

        (
            avatar_size // 2 + 18,
            PURPLE,
            3
        ),

        (
            avatar_size // 2 + 26,
            PINK,
            2
        )
    ]

    for radius, color, width in rings:

        gd.ellipse(
            (
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius
            ),
            outline=color,
            width=width + 9
        )

    glow = glow.filter(
        ImageFilter.GaussianBlur(9)
    )

    base.alpha_composite(
        glow
    )

    draw = ImageDraw.Draw(
        base
    )

    for radius, color, width in rings:

        draw.ellipse(
            (
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius
            ),
            outline=color,
            width=width
        )


# =========================================================
# CLEAN DISPLAY TEXT
# =========================================================

def clean_display_text(
    text,
    maximum
):

    if not text:
        return ""

    text = str(
        text
    ).strip()

    if len(text) > maximum:

        text = (
            text[:maximum - 3]
            + "..."
        )

    return text


# =========================================================
# DRAW SIDE TEXT
# =========================================================

def draw_side_text(
    draw,
    text,
    center_x,
    y,
    max_width,
    size,
    bold,
    fill
):

    font = fit_font(
        draw,
        text,
        max_width,
        size,
        bold
    )

    draw_center_text(
        draw,
        text,
        center_x,
        y,
        font,
        fill
    )


# =========================================================
# CREATE WELCOME CARD
# =========================================================

def create_welcome_card(
    user,
    chat
):

    WIDTH = 1200
    HEIGHT = 700

    base = make_background(
        WIDTH,
        HEIGHT
    )

    # -----------------------------------------------------
    # BACKGROUND GLOWS
    # -----------------------------------------------------

    glow_circle(
        base,
        40,
        80,
        180,
        (70, 90, 255, 55),
        70
    )

    glow_circle(
        base,
        1160,
        80,
        180,
        (255, 50, 190, 55),
        70
    )

    glow_circle(
        base,
        50,
        630,
        170,
        (155, 70, 255, 45),
        70
    )

    glow_circle(
        base,
        1150,
        630,
        170,
        (60, 170, 255, 45),
        70
    )

    # -----------------------------------------------------
    # GLASS PANEL
    # -----------------------------------------------------

    panel = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0)
    )

    pd = ImageDraw.Draw(
        panel
    )

    pd.rounded_rectangle(
        (
            25,
            25,
            WIDTH - 25,
            HEIGHT - 25
        ),
        radius=45,
        fill=(
            14,
            16,
            38,
            242
        ),
        outline=(
            95,
            110,
            180,
            210
        ),
        width=3
    )

    base.alpha_composite(
        panel
    )

    draw = ImageDraw.Draw(
        base
    )

    # -----------------------------------------------------
    # CORNER LINES
    # -----------------------------------------------------

    neon_line(
        base,
        [
            (65, 105),
            (225, 105)
        ],
        BLUE,
        3
    )

    neon_line(
        base,
        [
            (975, 105),
            (1135, 105)
        ],
        PINK,
        3
    )

    neon_line(
        base,
        [
            (65, 595),
            (225, 595)
        ],
        PURPLE,
        3
    )

    neon_line(
        base,
        [
            (975, 595),
            (1135, 595)
        ],
        BLUE,
        3
    )

    # -----------------------------------------------------
    # DATA
    # -----------------------------------------------------

    name = clean_display_text(
        user.first_name or "User",
        18
    )

    if user.username:

        username = (
            "@"
            + user.username
        )

    else:

        username = "@NoUsername"

    username = clean_display_text(
        username,
        18
    )

    group_name = clean_display_text(
        chat.title or "THE GROUP",
        18
    )

    # -----------------------------------------------------
    # LEFT TOP — WELCOME
    # -----------------------------------------------------

    draw_side_text(
        draw,
        "WELCOME",
        200,
        245,
        350,
        50,
        True,
        WHITE
    )

    # -----------------------------------------------------
    # RIGHT TOP — NAME
    # -----------------------------------------------------

    draw_side_text(
        draw,
        name,
        1000,
        245,
        350,
        45,
        True,
        WHITE
    )

    # -----------------------------------------------------
    # PROFILE PHOTO
    # -----------------------------------------------------

    AVATAR_SIZE = 210

    photo_data = get_profile_photo(
        user.id
    )

    if photo_data:

        avatar = circle_avatar(
            photo_data,
            AVATAR_SIZE
        )

    else:

        avatar = default_avatar(
            AVATAR_SIZE
        )

    avatar_x = (
        WIDTH - AVATAR_SIZE
    ) // 2

    avatar_y = 175

    center_x = WIDTH // 2

    center_y = (
        avatar_y
        + AVATAR_SIZE // 2
    )

    glow_circle(
        base,
        center_x,
        center_y,
        145,
        (70, 110, 255, 65),
        45
    )

    base.alpha_composite(
        avatar,
        (
            avatar_x,
            avatar_y
        )
    )

    draw_rings(
        base,
        center_x,
        center_y,
        AVATAR_SIZE
    )

    # -----------------------------------------------------
    # ID
    # -----------------------------------------------------

    id_text = (
        "ID  •  "
        + str(user.id)
    )

    id_font = get_font(
        29,
        True
    )

    draw_center_text(
        draw,
        id_text,
        WIDTH // 2,
        405,
        id_font,
        MUTED
    )

    # -----------------------------------------------------
    # LEFT BOTTOM — GROUP
    # -----------------------------------------------------

    draw_side_text(
        draw,
        group_name,
        200,
        470,
        350,
        40,
        True,
        (
            205,
            145,
            255,
            255
        )
    )

    # -----------------------------------------------------
    # RIGHT BOTTOM — USERNAME
    # -----------------------------------------------------

    draw_side_text(
        draw,
        username,
        1000,
        470,
        350,
        36,
        False,
        SOFT_WHITE
    )

    # -----------------------------------------------------
    # CENTER LINE
    # -----------------------------------------------------

    neon_line(
        base,
        [
            (500, 505),
            (700, 505)
        ],
        PURPLE,
        2
    )

    # -----------------------------------------------------
    # DECORATIVE DOTS
    # -----------------------------------------------------

    dots = [

        (
            80,
            75,
            7,
            BLUE
        ),

        (
            1120,
            75,
            7,
            PINK
        ),

        (
            80,
            625,
            7,
            PURPLE
        ),

        (
            1120,
            625,
            7,
            BLUE
        )
    ]

    for x, y, r, color in dots:

        glow_circle(
            base,
            x,
            y,
            r,
            color,
            10
        )

        draw.ellipse(
            (
                x - r,
                y - r,
                x + r,
                y + r
            ),
            fill=color
        )

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    output = io.BytesIO()

    output.name = (
        "welcome_card.jpg"
    )

    base.convert(
        "RGB"
    ).save(
        output,
        format="JPEG",
        quality=95,
        optimize=True
    )

    output.seek(0)

    return output
    # =========================================================
# USER MENTION
# =========================================================

def make_mention(user):

    name = (
        user.first_name
        or "کاربر"
    )

    safe_name = html.escape(
        name
    )

    return (
        '<a href="tg://user?id='
        + str(user.id)
        + '">'
        + safe_name
        + '</a>'
    )


# =========================================================
# MAKE CAPTION
# =========================================================

def make_welcome_caption(
    user,
    chat
):

    name = (
        user.first_name
        or "کاربر"
    )

    username = (
        "@"
        + user.username
        if user.username
        else "بدون یوزرنیم"
    )

    group = (
        chat.title
        or "گپ"
    )

    mention = make_mention(
        user
    )

    safe_name = html.escape(
        name
    )

    safe_username = html.escape(
        username
    )

    safe_group = html.escape(
        group
    )

    template = settings.get(
        "welcome_text",
        DEFAULT_WELCOME
    )

    if not isinstance(
        template,
        str
    ):

        template = DEFAULT_WELCOME

    safe_template = html.escape(
        template
    )

    safe_template = (
        safe_template
        .replace(
            "{name}",
            safe_name
        )
        .replace(
            "{username}",
            safe_username
        )
        .replace(
            "{id}",
            str(user.id)
        )
        .replace(
            "{group}",
            safe_group
        )
        .replace(
            "{mention}",
            mention
        )
    )

    if len(safe_template) > 900:

        safe_template = (
            safe_template[:897]
            + "..."
        )

    return safe_template


# =========================================================
# SEND WELCOME
# =========================================================

def send_welcome(
    message,
    user
):

    # -----------------------------------------------------
    # IGNORE BOT
    # -----------------------------------------------------

    try:

        bot_id = bot.get_me().id

        if user.id == bot_id:

            print(
                "BOT JOINED - IGNORED"
            )

            return

    except Exception as e:

        print(
            "BOT ID ERROR:",
            e
        )

    # -----------------------------------------------------
    # CREATE CARD
    # -----------------------------------------------------

    try:

        print(
            "CREATING CARD FOR:",
            user.id
        )

        card = create_welcome_card(
            user,
            message.chat
        )

        print(
            "CARD CREATED:",
            user.id
        )

    except Exception as e:

        print(
            "CARD CREATION ERROR:",
            e
        )

        traceback.print_exc()

        card = None

    # -----------------------------------------------------
    # CAPTION
    # -----------------------------------------------------

    try:

        caption = make_welcome_caption(
            user,
            message.chat
        )

    except Exception as e:

        print(
            "CAPTION ERROR:",
            e
        )

        caption = (
            "👋 "
            + make_mention(user)
            + " عزیز، خوش اومدی! ❤️"
        )

    # -----------------------------------------------------
    # SEND PHOTO + CAPTION
    # -----------------------------------------------------

    if card is not None:

        try:

            bot.send_photo(
                message.chat.id,
                card,
                caption=caption
            )

            print(
                "WELCOME SENT:",
                user.id
            )

            return

        except Exception as e:

            print(
                "SEND PHOTO ERROR:",
                e
            )

            traceback.print_exc()

    # -----------------------------------------------------
    # FALLBACK
    # -----------------------------------------------------

    try:

        bot.send_message(
            message.chat.id,
            caption
        )

        print(
            "FALLBACK MESSAGE SENT:",
            user.id
        )

    except Exception as e:

        print(
            "FALLBACK ERROR:",
            e
        )


# =========================================================
# NEW MEMBERS
# =========================================================

@bot.message_handler(
    content_types=[
        "new_chat_members"
    ]
)
def new_member_handler(
    message
):

    try:

        print(
            "================================"
        )

        print(
            "NEW MEMBER EVENT"
        )

        print(
            "CHAT:",
            message.chat.id
        )

        print(
            "TITLE:",
            message.chat.title
        )

        print(
            "COUNT:",
            len(
                message.new_chat_members
            )
        )

        for user in (
            message.new_chat_members
        ):

            send_welcome(
                message,
                user
            )

    except Exception as e:

        print(
            "NEW MEMBER ERROR:",
            e
        )

        traceback.print_exc()


# =========================================================
# ADMIN PRIVATE PANEL
# =========================================================

@bot.message_handler(
    func=lambda message:
        message.chat.type == "private"
        and
        message.from_user is not None
        and
        message.from_user.id == ADMIN_ID,
    content_types=[
        "text"
    ]
)
def admin_private_handler(
    message
):

    global settings

    text = (
        message.text
        or ""
    ).strip()

    if not text:

        return

    # -----------------------------------------------------
    # START
    # -----------------------------------------------------

    if text.lower().startswith(
        "/start"
    ):

        current = settings.get(
            "welcome_text",
            DEFAULT_WELCOME
        )

        bot.send_message(
            message.chat.id,

            "👑 <b>پنل خوشامدگویی</b>\n\n"

            "هر متنی که اینجا بفرستی، "
            "برای عضو جدید در توضیحات "
            "همان عکس قرار می‌گیرد.\n\n"

            "❌ پیام جداگانه بعد از عکس "
            "ارسال نمی‌شود.\n\n"

            "<b>متغیرها:</b>\n\n"

            "<code>{name}</code> "
            "اسم کاربر\n"

            "<code>{username}</code> "
            "یوزرنیم\n"

            "<code>{id}</code> "
            "آیدی عددی\n"

            "<code>{group}</code> "
            "اسم گپ\n"

            "<code>{mention}</code> "
            "تگ واقعی کاربر\n\n"

            "<b>متن فعلی:</b>\n"
            + html.escape(
                current
            )
        )

        return

    # -----------------------------------------------------
    # SHOW CURRENT
    # -----------------------------------------------------

    if text.lower() == "/welcome":

        current = settings.get(
            "welcome_text",
            DEFAULT_WELCOME
        )

        bot.send_message(
            message.chat.id,

            "📝 <b>متن فعلی:</b>\n\n"
            + html.escape(
                current
            )
            + "\n\n"
            "متن جدید را بفرست."
        )

        return

    # -----------------------------------------------------
    # SAVE TEXT
    # -----------------------------------------------------

    settings["welcome_text"] = text

    if save_settings(
        settings
    ):

        bot.send_message(
            message.chat.id,

            "✅ <b>متن ذخیره شد.</b>\n\n"

            "از این به بعد متن تو "
            "در توضیحات عکس خوشامدگویی "
            "قرار می‌گیرد.\n\n"

            "📸 هیچ پیام جداگانه‌ای "
            "بعد از عکس ارسال نمی‌شود."
        )

    else:

        bot.send_message(
            message.chat.id,
            "❌ ذخیره متن انجام نشد."
        )


# =========================================================
# NON ADMIN PRIVATE
# =========================================================

@bot.message_handler(
    func=lambda message:
        message.chat.type == "private"
        and
        (
            message.from_user is None
            or
            message.from_user.id != ADMIN_ID
        ),
    content_types=[
        "text"
    ]
)
def other_private_handler(
    message
):

    bot.send_message(
        message.chat.id,
        "🤖 ربات خوشامدگویی گپ است."
    )


# =========================================================
# START INFO
# =========================================================

def print_start_info():

    print(
        "=========================================="
    )

    print(
        "          NEON WELCOME BOT"
    )

    print(
        "=========================================="
    )

    print(
        "ADMIN ID:",
        ADMIN_ID
    )

    print(
        "SETTINGS:",
        SETTINGS_FILE
    )

    print(
        "WELCOME TEXT:"
    )

    print(
        settings.get(
            "welcome_text",
            DEFAULT_WELCOME
        )
    )

    print(
        "=========================================="
    )


# =========================================================
# RUN BOT
# =========================================================

if __name__ == "__main__":

    print_start_info()

    print(
        "BOT IS STARTING..."
    )

    try:

        bot.infinity_polling(
            skip_pending=True,
            timeout=60,
            long_polling_timeout=60,
            allowed_updates=[
                "message"
            ]
        )

    except Exception as e:

        print(
            "BOT CRASHED:"
        )

        print(
            e
        )

        traceback.print_exc()
