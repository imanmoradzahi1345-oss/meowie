# -*- coding: utf-8 -*-

import io
import os
import json
import html
import telebot

from PIL import Image, ImageDraw, ImageFont, ImageFilter


# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = "8617545814:AAFAofo_nV39gFT1-IgfXu-esnGgXol62r4"

ADMIN_ID = 7530457395

SETTINGS_FILE = "welcome_settings.json"

DEFAULT_WELCOME = (
    "👋 {mention} عزیز، به <b>{group}</b> خوش اومدی! ❤️\n\n"
    "✨ امیدواریم اینجا بهت خوش بگذره."
)

bot = telebot.TeleBot(
    BOT_TOKEN,
    parse_mode="HTML"
)


# =========================================================
# LOAD / SAVE SETTINGS
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
        ) as f:

            data = json.load(f)

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
            "welcome_text": text
        }

    except Exception as e:

        print(
            "LOAD SETTINGS ERROR:",
            e
        )

        return {
            "welcome_text":
                DEFAULT_WELCOME
        }


def save_settings(data):

    try:

        with open(
            SETTINGS_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2
            )

        return True

    except Exception as e:

        print(
            "SAVE SETTINGS ERROR:",
            e
        )

        return False


settings = load_settings()


# =========================================================
# ADMIN CHECK
# =========================================================

def is_admin(message):

    return (
        message.from_user is not None
        and
        message.from_user.id == ADMIN_ID
    )


# =========================================================
# FONTS
# =========================================================

def get_font(
    size,
    bold=False
):

    if bold:

        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            "/data/data/com.termux/files/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        ]

    else:

        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/data/data/com.termux/files/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ]

    for path in paths:

        try:

            return ImageFont.truetype(
                path,
                size
            )

        except Exception:
            pass

    return ImageFont.load_default()


def fit_font(
    draw,
    text,
    max_width,
    size,
    bold=False
):

    while size >= 16:

        font = get_font(
            size,
            bold
        )

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

        size -= 2

    return get_font(
        16,
        bold
    )


def center_text(
    draw,
    text,
    y,
    font,
    fill,
    width
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
        width
        - text_width
    ) / 2

    draw.text(
        (x, y),
        text,
        font=font,
        fill=fill
    )


# =========================================================
# COLORS
# =========================================================

PURPLE = (
    155,
    70,
    255,
    255
)

BLUE = (
    60,
    170,
    255,
    255
)

PINK = (
    255,
    65,
    190,
    255
)

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


# =========================================================
# GLOW
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

    glow_draw = ImageDraw.Draw(
        glow
    )

    glow_draw.line(
        points,
        fill=color,
        width=width + 18,
        joint="curve"
    )

    glow = glow.filter(
        ImageFilter.GaussianBlur(10)
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
                8
                + 25 * nx
                + 15 * ny
            )

            g = int(
                7
                + 4 * nx
            )

            b = int(
                27
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
            4,
            4,
            size - 4,
            size - 4
        ),
        fill=(
            28,
            30,
            65,
            255
        )
    )

    cx = size // 2

    draw.ellipse(
        (
            cx - 38,
            40,
            cx + 38,
            116
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
            cx - 70,
            125,
            cx + 70,
            245
        ),
        radius=40,
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

def get_profile_photo(
    user_id
):

    try:

        photos = (
            bot.get_user_profile_photos(
                user_id,
                limit=1
            )
        )

        if not photos:
            return None

        if photos.total_count <= 0:
            return None

        if not photos.photos:
            return None

        photo = photos.photos[0][-1]

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

        w, h = original.size

        side = min(
            w,
            h
        )

        left = (
            w - side
        ) // 2

        top = (
            h - side
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
            "AVATAR ERROR:",
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

    # حلقه‌ها متناسب با عکس کوچکتر
    rings = [
        (
            avatar_size // 2 + 12,
            BLUE,
            4
        ),
        (
            avatar_size // 2 + 21,
            PURPLE,
            3
        ),
        (
            avatar_size // 2 + 29,
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
            width=width + 10
        )

    glow = glow.filter(
        ImageFilter.GaussianBlur(10)
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
    # BACKGROUND GLOW
    # -----------------------------------------------------

    glow_circle(
        base,
        70,
        90,
        160,
        (80, 80, 255, 70),
        60
    )

    glow_circle(
        base,
        1130,
        90,
        170,
        (255, 50, 190, 65),
        65
    )

    glow_circle(
        base,
        600,
        680,
        200,
        (60, 150, 255, 50),
        75
    )

    # -----------------------------------------------------
    # MAIN PANEL
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
            28,
            28,
            WIDTH - 28,
            HEIGHT - 28
        ),
        radius=48,
        fill=(
            13,
            15,
            38,
            235
        ),
        outline=(
            100,
            115,
            190,
            180
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
    # DECORATIVE LINES
    # -----------------------------------------------------

    neon_line(
        base,
        [
            (65, 105),
            (280, 105)
        ],
        BLUE,
        3
    )

    neon_line(
        base,
        [
            (920, 105),
            (1135, 105)
        ],
        PINK,
        3
    )

    # -----------------------------------------------------
    # WELCOME
    # -----------------------------------------------------

    title_font = get_font(
        58,
        True
    )

    center_text(
        draw,
        "WELCOME",
        52,
        title_font,
        WHITE,
        WIDTH
    )

    neon_line(
        base,
        [
            (470, 130),
            (730, 130)
        ],
        PURPLE,
        3
    )

    # -----------------------------------------------------
    # GROUP NAME
    # -----------------------------------------------------

    group_name = (
        chat.title
        or "THE GROUP"
    )

    if len(group_name) > 32:

        group_name = (
            group_name[:29]
            + "..."
        )

    group_font = fit_font(
        draw,
        group_name,
        850,
        31,
        True
    )

    center_text(
        draw,
        group_name,
        145,
        group_font,
        (
            215,
            150,
            255,
            255
        ),
        WIDTH
    )

    # -----------------------------------------------------
    # PROFILE PHOTO
    # -----------------------------------------------------

    # قبلاً 300 بود؛ الان متوسط‌تر و متناسب‌تر
    AVATAR_SIZE = 225

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

    avatar_y = 190

    avatar_center_x = WIDTH // 2

    avatar_center_y = (
        avatar_y
        + AVATAR_SIZE // 2
    )

    glow_circle(
        base,
        avatar_center_x,
        avatar_center_y,
        135,
        (90, 100, 255, 70),
        40
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
        avatar_center_x,
        avatar_center_y,
        AVATAR_SIZE
    )

    # -----------------------------------------------------
    # USER NAME
    # -----------------------------------------------------

    name = (
        user.first_name
        or "User"
    )

    if len(name) > 25:

        name = (
            name[:22]
            + "..."
        )

    name_font = fit_font(
        draw,
        name,
        700,
        38,
        True
    )

    center_text(
        draw,
        name,
        445,
        name_font,
        WHITE,
        WIDTH
    )

    # -----------------------------------------------------
    # USERNAME
    # -----------------------------------------------------

    if user.username:

        username = (
            "@"
            + user.username
        )

    else:

        username = (
            "@NoUsername"
        )

    if len(username) > 30:

        username = (
            username[:27]
            + "..."
        )

    username_font = fit_font(
        draw,
        username,
        650,
        27,
        False
    )

    center_text(
        draw,
        username,
        492,
        username_font,
        SOFT_WHITE,
        WIDTH
    )

    # -----------------------------------------------------
    # ID
    # -----------------------------------------------------

    id_text = (
        "ID  •  "
        + str(user.id)
    )

    id_font = get_font(
        25,
        False
    )

    center_text(
        draw,
        id_text,
        530,
        id_font,
        MUTED,
        WIDTH
    )

    # -----------------------------------------------------
    # BOTTOM GROUP NAME
    # -----------------------------------------------------

    group_bottom_font = fit_font(
        draw,
        group_name,
        750,
        27,
        True
    )

    center_text(
        draw,
        group_name,
        580,
        group_bottom_font,
        (
            190,
            130,
            255,
            255
        ),
        WIDTH
    )

    # -----------------------------------------------------
    # SMALL DECORATION
    # -----------------------------------------------------

    tiny_font = get_font(
        15,
        False
    )

    center_text(
        draw,
        "NEON COMMUNITY",
        625,
        tiny_font,
        (
            105,
            120,
            175,
            255
        ),
        WIDTH
    )

    dots = [
        (85, 75, 6, BLUE),
        (1115, 75, 6, PINK),
        (95, 620, 5, PURPLE),
        (1105, 620, 5, BLUE)
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
    # OUTPUT
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
# BUILD CAPTION
# =========================================================

def make_welcome_caption(
    user,
    chat
):

    first_name = (
        user.first_name
        or "کاربر"
    )

    username = (
        "@"
        + user.username
        if user.username
        else "بدون یوزرنیم"
    )

    group_name = (
        chat.title
        or "گپ"
    )

    safe_name = html.escape(
        first_name
    )

    safe_username = html.escape(
        username
    )

    safe_group = html.escape(
        group_name
    )

    # تگ واقعی کاربر
    mention = (
        '<a href="tg://user?id='
        + str(user.id)
        + '">'
        + safe_name
        + '</a>'
    )

    template = settings.get(
        "welcome_text",
        DEFAULT_WELCOME
    )

    try:

        caption = template.format(
            name=safe_name,
            username=safe_username,
            id=str(user.id),
            group=safe_group,
            mention=mention
        )

    except Exception as e:

        print(
            "CAPTION TEMPLATE ERROR:",
            e
        )

        caption = (
            "👋 "
            + mention
            + " عزیز، خوش اومدی به "
            + "<b>"
            + safe_group
            + "</b> ❤️"
        )

    return caption


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

    print(
        "================================"
    )

    print(
        "NEW MEMBER EVENT:",
        message.chat.id
    )

    if not message.new_chat_members:
        return

    # دریافت ID ربات
    try:

        me = bot.get_me()
        bot_id = me.id

    except Exception as e:

        print(
            "GET BOT INFO ERROR:",
            e
        )

        bot_id = None

    # چند عضو همزمان
    for user in message.new_chat_members:

        # ربات خودش را نادیده بگیر
        if (
            bot_id is not None
            and user.id == bot_id
        ):
            continue

        # -------------------------------------------------
        # ساخت کارت
        # -------------------------------------------------

        try:

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

            card = None

        # -------------------------------------------------
        # ساخت کپشن
        # -------------------------------------------------

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

            name = (
                user.first_name
                or "کاربر"
            )

            mention = (
                '<a href="tg://user?id='
                + str(user.id)
                + '">'
                + html.escape(name)
                + '</a>'
            )

            caption = (
                "👋 "
                + mention
                + " عزیز، خوش اومدی! ❤️"
            )

        # -------------------------------------------------
        # ارسال عکس + کپشن
        # -------------------------------------------------

        if card is not None:

            try:

                bot.send_photo(
                    message.chat.id,
                    card,
                    caption=caption
                )

                print(
                    "CARD + CAPTION SENT:",
                    user.id
                )

                # بسیار مهم:
                # هیچ پیام جداگانه‌ای ارسال نمی‌شود.

                continue

            except Exception as e:

                print(
                    "SEND PHOTO ERROR:",
                    e
                )

        # -------------------------------------------------
        # FALLBACK
        # اگر عکس ارسال نشد، حداقل متن ارسال شود
        # -------------------------------------------------

        try:

            bot.send_message(
                message.chat.id,
                caption,
                disable_web_page_preview=True
            )

            print(
                "FALLBACK TEXT SENT:",
                user.id
            )

        except Exception as e:

            print(
                "FALLBACK TEXT ERROR:",
                e
            )


# =========================================================
# ADMIN PRIVATE PANEL
# =========================================================

@bot.message_handler(
    func=lambda message:
        message.chat.type == "private"
        and message.from_user is not None
        and message.from_user.id == ADMIN_ID,
    content_types=["text"]
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
            "به‌عنوان <b>توضیحات عکس</b> "
            "برای عضو جدید استفاده می‌شود.\n\n"

            "یعنی متن <b>جداگانه ارسال نمی‌شود</b> "
            "و همراه خود عکس خواهد بود.\n\n"

            "<b>متغیرها:</b>\n"
            "{name} ← اسم\n"
            "{username} ← یوزرنیم\n"
            "{id} ← آیدی عددی\n"
            "{group} ← اسم گپ\n"
            "{mention} ← تگ واقعی کاربر\n\n"

            "<b>متن فعلی:</b>\n"
            + html.escape(current)
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
            + html.escape(current)
            + "\n\n"
            "متن جدید را همینجا بفرست."
        )

        return

    # -----------------------------------------------------
    # SAVE NEW TEXT
    # -----------------------------------------------------

    settings["welcome_text"] = text

    if save_settings(
        settings
    ):

        bot.send_message(
            message.chat.id,

            "✅ <b>ذخیره شد.</b>\n\n"

            "از این به بعد متن ارسالی "
            "در <b>توضیحات عکس خوشامدگویی</b> "
            "قرار می‌گیرد.\n\n"

            "❌ پیام جداگانه‌ای بعد از عکس "
            "ارسال نمی‌شود."
        )

    else:

        bot.send_message(
            message.chat.id,
            "❌ ذخیره متن انجام نشد."
        )


# =========================================================
# OTHER PRIVATE USERS
# =========================================================

@bot.message_handler(
    func=lambda message:
        message.chat.type == "private"
        and (
            message.from_user is None
            or message.from_user.id != ADMIN_ID
        )
)
def other_private_handler(
    message
):

    bot.send_message(
        message.chat.id,
        "🤖 ربات خوشامدگویی گروه است."
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    print(
        "======================================"
    )

    print(
        "       NEON WELCOME BOT"
    )

    print(
        "======================================"
    )

    print(
        "ADMIN ID:",
        ADMIN_ID
    )

    print(
        "WELCOME TEXT:",
        settings.get(
            "welcome_text",
            DEFAULT_WELCOME
        )
    )

    print(
        "BOT IS RUNNING..."
    )

    bot.infinity_polling(
        skip_pending=True,
        timeout=60,
        long_polling_timeout=60
    )
