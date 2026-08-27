# -*- coding: utf-8 -*-

import io
import math
import telebot

from PIL import Image, ImageDraw, ImageFont, ImageFilter


# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = "8617545814:AAFAofo_nV39gFT1-IgfXu-esnGgXol62r4"

ADMIN_ID = 7530457395

bot = telebot.TeleBot(
    BOT_TOKEN,
    parse_mode="HTML"
)


# =========================================================
# FONTS
# =========================================================

def get_font(size, bold=False):
    if bold:
        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
    else:
        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]

    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass

    return ImageFont.load_default()


def fit_font(draw, text, max_width, size, bold=False):
    while size >= 14:
        font = get_font(size, bold)

        box = draw.textbbox(
            (0, 0),
            text,
            font=font
        )

        width = box[2] - box[0]

        if width <= max_width:
            return font

        size -= 2

    return get_font(14, bold)


def center_text(draw, text, y, font, fill, width):
    box = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    text_width = box[2] - box[0]

    x = (width - text_width) / 2

    draw.text(
        (x, y),
        text,
        font=font,
        fill=fill
    )


# =========================================================
# COLORS
# =========================================================

PURPLE = (155, 70, 255, 255)
BLUE = (60, 170, 255, 255)
PINK = (255, 65, 190, 255)

WHITE = (245, 245, 255, 255)
SOFT_WHITE = (205, 210, 240, 255)
MUTED = (115, 130, 180, 255)


# =========================================================
# GLOW
# =========================================================

def glow_circle(base, x, y, radius, color, blur=35):
    layer = Image.new(
        "RGBA",
        base.size,
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(layer)

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
        ImageFilter.GaussianBlur(blur)
    )

    base.alpha_composite(layer)


def neon_line(base, points, color, width=3):
    glow = Image.new(
        "RGBA",
        base.size,
        (0, 0, 0, 0)
    )

    glow_draw = ImageDraw.Draw(glow)

    glow_draw.line(
        points,
        fill=color,
        width=width + 18,
        joint="curve"
    )

    glow = glow.filter(
        ImageFilter.GaussianBlur(10)
    )

    base.alpha_composite(glow)

    draw = ImageDraw.Draw(base)

    draw.line(
        points,
        fill=color,
        width=width,
        joint="curve"
    )


# =========================================================
# BACKGROUND
# =========================================================

def make_background(width, height):
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

            r = int(8 + 25 * nx + 15 * ny)
            g = int(7 + 4 * nx)
            b = int(27 + 55 * (1 - nx) + 25 * (1 - ny))

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

    draw = ImageDraw.Draw(avatar)

    draw.ellipse(
        (4, 4, size - 4, size - 4),
        fill=(28, 30, 65, 255)
    )

    cx = size // 2

    draw.ellipse(
        (
            cx - 45,
            55,
            cx + 45,
            145
        ),
        fill=(190, 195, 225, 255)
    )

    draw.rounded_rectangle(
        (
            cx - 82,
            155,
            cx + 82,
            275
        ),
        radius=45,
        fill=(105, 75, 220, 255)
    )

    return avatar


# =========================================================
# MAKE CIRCLE AVATAR
# =========================================================

def circle_avatar(data, size):
    try:
        original = Image.open(
            io.BytesIO(data)
        ).convert("RGB")

        w, h = original.size
        side = min(w, h)

        left = (w - side) // 2
        top = (h - side) // 2

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

        mask_draw = ImageDraw.Draw(mask)

        mask_draw.ellipse(
            (0, 0, size - 1, size - 1),
            fill=255
        )

        result.paste(
            original,
            (0, 0),
            mask
        )

        return result

    except Exception as e:
        print("Avatar error:", e)
        return default_avatar(size)


# =========================================================
# GET PROFILE PHOTO
# =========================================================

def get_profile_photo(user_id):
    try:
        photos = bot.get_user_profile_photos(
            user_id,
            limit=1
        )

        if photos.total_count <= 0:
            return None

        photo = photos.photos[0][-1]

        file_info = bot.get_file(
            photo.file_id
        )

        return bot.download_file(
            file_info.file_path
        )

    except Exception as e:
        print("Profile photo error:", e)
        return None


# =========================================================
# AVATAR RINGS
# =========================================================

def draw_rings(base, cx, cy):
    glow = Image.new(
        "RGBA",
        base.size,
        (0, 0, 0, 0)
    )

    gd = ImageDraw.Draw(glow)

    rings = [
        (172, BLUE, 5),
        (181, PURPLE, 4),
        (190, PINK, 3)
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
            width=width + 13
        )

    glow = glow.filter(
        ImageFilter.GaussianBlur(12)
    )

    base.alpha_composite(glow)

    draw = ImageDraw.Draw(base)

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
# CREATE CARD
# =========================================================

def create_welcome_card(user, chat):
    WIDTH = 1200
    HEIGHT = 700

    base = make_background(
        WIDTH,
        HEIGHT
    )

    # Background glows
    glow_circle(
        base,
        80,
        100,
        170,
        (80, 80, 255, 80),
        65
    )

    glow_circle(
        base,
        1120,
        100,
        180,
        (255, 50, 190, 75),
        70
    )

    glow_circle(
        base,
        600,
        690,
        220,
        (60, 150, 255, 55),
        80
    )

    # Main glass panel
    panel = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0)
    )

    pd = ImageDraw.Draw(panel)

    pd.rounded_rectangle(
        (28, 28, WIDTH - 28, HEIGHT - 28),
        radius=48,
        fill=(13, 15, 38, 230),
        outline=(100, 115, 190, 180),
        width=3
    )

    base.alpha_composite(panel)

    draw = ImageDraw.Draw(base)

    # Decorative lines
    neon_line(
        base,
        [(65, 105), (290, 105)],
        BLUE,
        3
    )

    neon_line(
        base,
        [(910, 595), (1135, 595)],
        PINK,
        3
    )

    # Top title
    title_font = get_font(
        62,
        True
    )

    center_text(
        draw,
        "WELCOME",
        55,
        title_font,
        WHITE,
        WIDTH
    )

    neon_line(
        base,
        [(470, 135), (730, 135)],
        PURPLE,
        3
    )

    # Profile photo
    photo_data = get_profile_photo(
        user.id
    )

    if photo_data:
        avatar = circle_avatar(
            photo_data,
            300
        )
    else:
        avatar = default_avatar(
            300
        )

    avatar_x = 450
    avatar_y = 160

    glow_circle(
        base,
        600,
        310,
        175,
        (90, 100, 255, 85),
        50
    )

    base.alpha_composite(
        avatar,
        (avatar_x, avatar_y)
    )

    draw_rings(
        base,
        600,
        310
    )

    # User name
    name = user.first_name or "User"

    if len(name) > 24:
        name = name[:21] + "..."

    name_font = fit_font(
        draw,
        name,
        650,
        44,
        True
    )

    center_text(
        draw,
        name,
        485,
        name_font,
        WHITE,
        WIDTH
    )

    # Username
    if user.username:
        username = "@" + user.username
    else:
        username = "@NoUsername"

    if len(username) > 30:
        username = username[:27] + "..."

    username_font = fit_font(
        draw,
        username,
        650,
        28,
        False
    )

    center_text(
        draw,
        username,
        535,
        username_font,
        SOFT_WHITE,
        WIDTH
    )
        # Numeric ID
    id_text = "ID  •  " + str(user.id)

    id_font = get_font(
        24,
        False
    )

    center_text(
        draw,
        id_text,
        572,
        id_font,
        MUTED,
        WIDTH
    )

    # Group name
    group_name = chat.title or "THE GROUP"

    if len(group_name) > 34:
        group_name = group_name[:31] + "..."

    group_font = fit_font(
        draw,
        group_name.upper(),
        750,
        26,
        True
    )

    center_text(
        draw,
        group_name.upper(),
        615,
        group_font,
        (215, 150, 255, 255),
        WIDTH
    )

    # Small bottom text
    tiny_font = get_font(
        12,
        False
    )

    center_text(
        draw,
        "NEON COMMUNITY",
        654,
        tiny_font,
        (90, 105, 160, 255),
        WIDTH
    )

    # Decorative dots
    dots = [
        (85, 75, 6, BLUE),
        (1115, 75, 6, PINK),
        (95, 620, 5, PURPLE),
        (1105, 620, 5, BLUE),
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

    # Final image
    output = io.BytesIO()

    output.name = "welcome_card.jpg"

    base.convert("RGB").save(
        output,
        format="JPEG",
        quality=95,
        optimize=True
    )

    output.seek(0)

    return output


# =========================================================
# ADMIN CHECK
# =========================================================

def is_admin(message):
    return (
        message.from_user is not None
        and message.from_user.id == ADMIN_ID
    )


# =========================================================
# START
# =========================================================

@bot.message_handler(
    commands=["start"]
)
def start_handler(message):
    if is_admin(message):
        bot.send_message(
            message.chat.id,
            "👑 <b>ربات خوشامدگویی فعال است</b>\n\n"
            "ربات را داخل گپ ادمین کن.\n"
            "با ورود هر عضو جدید، کارت اختصاصی او "
            "به‌صورت خودکار ساخته می‌شود."
        )
    else:
        bot.send_message(
            message.chat.id,
            "🤖 ربات فعال است."
        )


# =========================================================
# NEW MEMBERS
# =========================================================

@bot.message_handler(
    content_types=["new_chat_members"]
)
def new_member_handler(message):
    for user in message.new_chat_members:

        try:
            # اگر خود ربات وارد گپ شد، کارت نساز
            me = bot.get_me()

            if user.id == me.id:
                continue

            # ساخت کارت اختصاصی
            card = create_welcome_card(
                user,
                message.chat
            )

            # ارسال عکس
            bot.send_photo(
                message.chat.id,
                card
            )

            # ساخت تگ واقعی کاربر
            first_name = user.first_name or "کاربر"

            mention = (
                '<a href="tg://user?id='
                + str(user.id)
                + '">'
                + first_name
                + '</a>'
            )

            group_name = (
                message.chat.title
                or "گپ"
            )

            # متن جداگانه، نه روی عکس
            welcome_text = (
                "👋 "
                + mention
                + " عزیز، خوش اومدی به "
                + "<b>"
                + group_name
                + "</b>"
                + " ❤️\n\n"
                + "✨ امیدواریم اینجا بهت خوش بگذره!"
            )

            bot.send_message(
                message.chat.id,
                welcome_text
            )

        except Exception as e:
            print(
                "NEW MEMBER ERROR:",
                e
            )


# =========================================================
# PRIVATE ADMIN MESSAGES
# =========================================================

@bot.message_handler(
    func=lambda message:
        message.chat.type == "private"
)
def private_handler(message):

    if not is_admin(message):
        return

    if message.text and message.text.startswith("/start"):
        return

    bot.send_message(
        message.chat.id,
        "✅ ربات آماده است.\n\n"
        "کارت خوشامدگویی به‌صورت خودکار "
        "برای اعضای جدید ساخته می‌شود."
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    print("===================================")
    print("       NEON WELCOME BOT")
    print("===================================")
    print("ADMIN ID:", ADMIN_ID)
    print("BOT IS RUNNING...")

    bot.infinity_polling(
        skip_pending=True,
        timeout=60,
        long_polling_timeout=60
                       )
