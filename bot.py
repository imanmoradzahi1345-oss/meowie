import os
import io
import sqlite3
import asyncio
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFont, ImageOps
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ChatPermissions
)
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ChatMemberHandler, filters
)

# ============================================================
# Telegram Group Management Bot
# Python 3.10+
# Install:
#   pip install python-telegram-bot==22.2 Pillow
#
# Set BOT_TOKEN as an environment variable, then:
#   python bot.py
#
# IMPORTANT:
# - The bot must be an ADMIN in each group it manages.
# - Group admins configure their own group from the bot's private chat.
# - Telegram's privacy/API rules mean the bot can only act on chats
#   where it has the required admin permissions.
# ============================================================

TOKEN = os.getenv("BOT_TOKEN", "").strip()
DB_FILE = "bot.db"

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set.")

# ---------- Database ----------

db = sqlite3.connect(DB_FILE, check_same_thread=False)
db.row_factory = sqlite3.Row
db.execute("""
CREATE TABLE IF NOT EXISTS settings (
    chat_id INTEGER PRIMARY KEY,
    welcome_text TEXT NOT NULL DEFAULT 'خوش آمدید {name} 🌷',
    welcome_caption TEXT NOT NULL DEFAULT 'سلام {name} عزیز! به گروه خوش آمدی ❤️',
    auto_text TEXT NOT NULL DEFAULT '',
    auto_enabled INTEGER NOT NULL DEFAULT 0,
    locked INTEGER NOT NULL DEFAULT 0,
    mute_seconds INTEGER NOT NULL DEFAULT 0
)
""")
db.execute("""
CREATE TABLE IF NOT EXISTS stats (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    username TEXT,
    messages INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, user_id)
)
""")
db.commit()

def ensure_settings(chat_id: int):
    db.execute("INSERT OR IGNORE INTO settings(chat_id) VALUES (?)", (chat_id,))
    db.commit()

def get_settings(chat_id: int):
    ensure_settings(chat_id)
    return db.execute("SELECT * FROM settings WHERE chat_id=?", (chat_id,)).fetchone()

def set_setting(chat_id: int, field: str, value):
    allowed = {
        "welcome_text", "welcome_caption", "auto_text",
        "auto_enabled", "locked", "mute_seconds"
    }
    if field not in allowed:
        raise ValueError("invalid setting")
    ensure_settings(chat_id)
    db.execute(f"UPDATE settings SET {field}=? WHERE chat_id=?", (value, chat_id))
    db.commit()

# ---------- Helpers ----------

def display_name(user):
    return (user.full_name or user.first_name or "کاربر").strip()

def mention_html(user):
    # Telegram HTML mention without needing a username.
    from html import escape
    return f'<a href="tg://user?id={user.id}">{escape(display_name(user))}</a>'

def render(text: str, user) -> str:
    from html import escape
    return (text or "").replace("{name}", escape(display_name(user))) \
                       .replace("{mention}", mention_html(user)) \
                       .replace("{username}", escape(user.username or ""))

async def is_group_admin(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False

async def bot_is_admin(context, chat_id: int) -> bool:
    try:
        me = await context.bot.get_me()
        member = await context.bot.get_chat_member(chat_id, me.id)
        return member.status == ChatMemberStatus.ADMINISTRATOR
    except Exception:
        return False

async def require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> bool:
    uid = update.effective_user.id
    if not await is_group_admin(context, chat_id, uid):
        await update.effective_message.reply_text("⛔ فقط ادمین‌های همین گروه می‌توانند تنظیماتش را تغییر دهند.")
        return False
    if not await bot_is_admin(context, chat_id):
        await update.effective_message.reply_text("⚠️ اول من را داخل گروه ادمین کنید تا بتوانم این قابلیت را اجرا کنم.")
        return False
    return True

def admin_keyboard(chat_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🖼 متن خوشامدگویی", callback_data=f"cfg:welcome:{chat_id}")],
        [InlineKeyboardButton("📝 کپشن عکس", callback_data=f"cfg:caption:{chat_id}")],
        [InlineKeyboardButton("🤖 پیام خودکار", callback_data=f"cfg:auto:{chat_id}")],
        [InlineKeyboardButton("🔒 قفل گروه", callback_data=f"cfg:lock:{chat_id}")],
        [InlineKeyboardButton("🔓 باز کردن گروه", callback_data=f"cfg:unlock:{chat_id}")],
        [InlineKeyboardButton("🔇 سکوت موقت", callback_data=f"cfg:mute:{chat_id}")],
        [InlineKeyboardButton("🚫 بن", callback_data=f"cfg:ban:{chat_id}")],
        [InlineKeyboardButton("♾️ بن دائمی", callback_data=f"cfg:banperm:{chat_id}")],
        [InlineKeyboardButton("📊 آمار", callback_data=f"cfg:stats:{chat_id}")],
        [InlineKeyboardButton("🏷 تگ کاربران", callback_data=f"cfg:tag:{chat_id}")],
    ])

async def send_welcome_photo(context, chat_id, user):
    """Create a personalized welcome image with the user's avatar and LARGE name."""
    settings = get_settings(chat_id)
    text = render(settings["welcome_text"], user)
    caption = render(settings["welcome_caption"], user)

    # Download Telegram profile photo; fallback to a generated avatar.
    avatar = None
    try:
        photos = await context.bot.get_user_profile_photos(user.id, limit=1)
        if photos.total_count:
            f = await context.bot.get_file(photos.photos[0][-1].file_id)
            data = await f.download_as_bytearray()
            avatar = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        avatar = None

    W, H = 1200, 700
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    # Fonts: DejaVu supports Latin/numbers. If a Persian font exists, use it.
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    bold_path = next((p for p in font_paths if "Bold" in p), font_paths[0])
    regular_path = font_paths[-1]

    # Look for common Persian fonts.
    for p in [
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]:
        if os.path.exists(p):
            bold_path = p
            break

    for p in [
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if os.path.exists(p):
            regular_path = p
            break

    name_font = ImageFont.truetype(bold_path, 72)
    title_font = ImageFont.truetype(bold_path, 48)
    small_font = ImageFont.truetype(regular_path, 34)

    # Avatar circle.
    cx, cy, r = 220, 350, 145
    if avatar:
        avatar = ImageOps.fit(avatar, (r * 2, r * 2), method=Image.Resampling.LANCZOS)
    else:
        avatar = Image.new("RGB", (r * 2, r * 2), "gray")
        ad = ImageDraw.Draw(avatar)
        initials = "".join(x[0] for x in display_name(user).split()[:2]).upper() or "?"
        f = ImageFont.truetype(bold_path, 72)
        box = ad.textbbox((0, 0), initials, font=f)
        ad.text(((2*r-(box[2]-box[0]))/2, (2*r-(box[3]-box[1]))/2-8), initials, font=f, fill="white")
    mask = Image.new("L", (r*2, r*2), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, r*2, r*2), fill=255)
    img.paste(avatar, (cx-r, cy-r), mask)

    # Text area.
    title = text or f"خوش آمدید {display_name(user)}"
    name = display_name(user)
    draw.text((430, 150), title, font=title_font, fill="black")
    draw.text((430, 280), name, font=name_font, fill="black")
    draw.text((430, 390), "به گروه خوش آمدی ❤️", font=small_font, fill="black")

    out = io.BytesIO()
    out.name = "welcome.jpg"
    img.save(out, format="JPEG", quality=92)
    out.seek(0)

    await context.bot.send_photo(
        chat_id=chat_id,
        photo=out,
        caption=caption,
        parse_mode="HTML"
    )

# ---------- Private panel ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("پنل مدیریت را در PV ربات باز کنید.")
        return
    await update.message.reply_text(
        "🛠 پنل مدیریت گروه\n\n"
        "ادمین گروه را از PV تنظیم کنید. ابتدا /groups را بزنید.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 گروه‌های من", callback_data="groups")]
        ])
    )

async def groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Telegram does not provide a universal list of all groups where a user is admin.
    # We keep groups that the bot has seen, then verify admin status live.
    rows = db.execute("SELECT chat_id FROM settings").fetchall()
    buttons = []
    for row in rows:
        cid = row["chat_id"]
        if await is_group_admin(context, cid, user.id):
            try:
                chat = await context.bot.get_chat(cid)
                buttons.append([InlineKeyboardButton(
                    f"⚙️ {chat.title}", callback_data=f"panel:{cid}"
                )])
            except Exception:
                pass

    if not buttons:
        await update.effective_message.reply_text(
            "هیچ گروهی پیدا نشد.\n"
            "ربات باید داخل گروه باشد و شما ادمین همان گروه باشید."
        )
        return

    await update.effective_message.reply_text(
        "گروه موردنظر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    if not await is_group_admin(context, chat_id, update.effective_user.id):
        await update.effective_message.reply_text("⛔ شما ادمین این گروه نیستید.")
        return
    if not await bot_is_admin(context, chat_id):
        await update.effective_message.reply_text("⚠️ ربات باید در این گروه ادمین باشد.")
        return

    chat = await context.bot.get_chat(chat_id)
    s = get_settings(chat_id)
    await update.effective_message.reply_text(
        f"⚙️ پنل: {chat.title}\n\n"
        f"خوشامد: {s['welcome_text']}\n"
        f"کپشن: {s['welcome_caption']}\n"
        f"پیام خودکار: {'فعال' if s['auto_enabled'] else 'خاموش'}\n"
        f"قفل: {'فعال' if s['locked'] else 'خاموش'}",
        reply_markup=admin_keyboard(chat_id)
    )

# ---------- Callback actions ----------

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data == "groups":
        await groups(update, context)
        return

    if data.startswith("panel:"):
        await panel(update, context, int(data.split(":")[1]))
        return

    if not data.startswith("cfg:"):
        return

    _, action, cid = data.split(":")
    cid = int(cid)

    if not await is_group_admin(context, cid, update.effective_user.id):
        await q.message.reply_text("⛔ فقط ادمین همان گروه اجازه دارد.")
        return
    if not await bot_is_admin(context, cid):
        await q.message.reply_text("⚠️ ربات باید ادمین گروه باشد.")
        return

    if action in ("welcome", "caption", "auto", "mute"):
        prompts = {
            "welcome": "متن خوشامدگویی را بفرست.\nمی‌توانی از {name}، {mention} و {username} استفاده کنی.",
            "caption": "کپشن عکس خوشامدگویی را بفرست.\nمی‌توانی از {name} و {mention} استفاده کنی.",
            "auto": "متن پیام خودکار را بفرست. برای خاموش‌کردن، /off را بفرست.",
            "mute": "مدت سکوت را به دقیقه بفرست؛ مثلا 10 یا 60.",
        }
        context.user_data["pending"] = {"action": action, "chat_id": cid}
        await q.message.reply_text(prompts[action])
        return

    if action == "lock":
        try:
            await context.bot.set_chat_permissions(
                cid,
                ChatPermissions(can_send_messages=False)
            )
            set_setting(cid, "locked", 1)
            await q.message.reply_text("🔒 گروه قفل شد.")
        except Exception as e:
            await q.message.reply_text(f"خطا در قفل گروه: {e}")
        return

    if action == "unlock":
        try:
            await context.bot.set_chat_permissions(
                cid,
                ChatPermissions(can_send_messages=True)
            )
            set_setting(cid, "locked", 0)
            await q.message.reply_text("🔓 گروه باز شد.")
        except Exception as e:
            await q.message.reply_text(f"خطا در باز کردن گروه: {e}")
        return

    if action in ("ban", "banperm"):
        context.user_data["pending"] = {"action": "ban", "chat_id": cid}
        await q.message.reply_text(
            "حالا پیام کاربر را در گروه reply کن و دستور /ban بزن، یا شناسه کاربر را با /ban USER_ID بده."
        )
        return

    if action == "stats":
        rows = db.execute(
            "SELECT name, username, messages FROM stats WHERE chat_id=? ORDER BY messages DESC LIMIT 10",
            (cid,)
        ).fetchall()
        if not rows:
            await q.message.reply_text("هنوز آماری ثبت نشده.")
            return
        text = "📊 بیشترین کاربران از نظر تعداد پیام:\n\n"
        for i, r in enumerate(rows, 1):
            uname = f"@{r['username']}" if r["username"] else ""
            text += f"{i}. {r['name']} {uname} — {r['messages']} پیام\n"
        await q.message.reply_text(text)
        return

    if action == "tag":
        rows = db.execute(
            "SELECT user_id, name FROM stats WHERE chat_id=? ORDER BY messages DESC LIMIT 20",
            (cid,)
        ).fetchall()
        if not rows:
            await q.message.reply_text("هنوز کاربری برای تگ ثبت نشده.")
            return
        text = "🏷 کاربران فعال:\n\n"
        for r in rows:
            text += f'<a href="tg://user?id={r["user_id"]}">{r["name"]}</a>\n'
        await q.message.reply_text(text, parse_mode="HTML")
        return

# ---------- Private text input ----------

async def private_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    pending = context.user_data.get("pending")
    if not pending:
        return

    action = pending["action"]
    cid = pending["chat_id"]
    user = update.effective_user

    if not await is_group_admin(context, cid, user.id):
        await update.message.reply_text("⛔ شما دیگر ادمین این گروه نیستید.")
        context.user_data.pop("pending", None)
        return

    value = update.message.text.strip()

    if action == "welcome":
        set_setting(cid, "welcome_text", value)
        await update.message.reply_text("✅ متن خوشامدگویی ذخیره شد.")
    elif action == "caption":
        set_setting(cid, "welcome_caption", value)
        await update.message.reply_text("✅ کپشن عکس ذخیره شد.")
    elif action == "auto":
        if value == "/off":
            set_setting(cid, "auto_enabled", 0)
            set_setting(cid, "auto_text", "")
            await update.message.reply_text("✅ پیام خودکار خاموش شد.")
        else:
            set_setting(cid, "auto_text", value)
            set_setting(cid, "auto_enabled", 1)
            await update.message.reply_text("✅ پیام خودکار فعال و ذخیره شد.")
    elif action == "mute":
        try:
            minutes = int(value)
            if minutes < 1 or minutes > 10080:
                raise ValueError
            set_setting(cid, "mute_seconds", minutes * 60)
            await update.message.reply_text(f"✅ سکوت موقت روی {minutes} دقیقه تنظیم شد.")
        except ValueError:
            await update.message.reply_text("❌ یک عدد بین 1 تا 10080 بفرست.")

    context.user_data.pop("pending", None)

# ---------- Group commands ----------

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        return
    cid = update.effective_chat.id
    if not await require_admin(update, context, cid):
        return

    target_id = None
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
    elif context.args:
        try:
            target_id = int(context.args[0])
        except ValueError:
            pass

    if not target_id:
        await update.message.reply_text("روی پیام کاربر reply کن و /ban بزن.")
        return

    try:
        await context.bot.ban_chat_member(cid, target_id)
        await update.message.reply_text("🚫 کاربر بن شد.")
    except Exception as e:
        await update.message.reply_text(f"خطا در بن: {e}")

async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        return
    cid = update.effective_chat.id
    if not await require_admin(update, context, cid):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("روی پیام کاربر reply کن.")
        return

    s = get_settings(cid)
    seconds = s["mute_seconds"] or 600
    until = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    target = update.message.reply_to_message.from_user

    try:
        await context.bot.restrict_chat_member(
            cid, target.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until
        )
        await update.message.reply_text(f"🔇 {display_name(target)} برای {seconds//60} دقیقه ساکت شد.")
    except Exception as e:
        await update.message.reply_text(f"خطا در سکوت: {e}")

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        return
    cid = update.effective_chat.id
    rows = db.execute(
        "SELECT name, username, messages FROM stats WHERE chat_id=? ORDER BY messages DESC LIMIT 10",
        (cid,)
    ).fetchall()
    if not rows:
        await update.message.reply_text("هنوز آماری ندارم.")
        return
    text = "📊 آمار برتر:\n\n"
    for i, r in enumerate(rows, 1):
        u = f"@{r['username']}" if r["username"] else ""
        text += f"{i}. {r['name']} {u} — {r['messages']}\n"
    await update.message.reply_text(text)

async def cmd_tag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        return
    cid = update.effective_chat.id
    if not await require_admin(update, context, cid):
        return
    rows = db.execute(
        "SELECT user_id, name FROM stats WHERE chat_id=? ORDER BY messages DESC LIMIT 20",
        (cid,)
    ).fetchall()
    if not rows:
        await update.message.reply_text("هنوز کاربری ثبت نشده.")
        return
    text = "🏷 تگ کاربران فعال:\n\n" + "\n".join(
        f'<a href="tg://user?id={r["user_id"]}">{r["name"]}</a>' for r in rows
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def cmd_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        return
    cid = update.effective_chat.id
    if not await require_admin(update, context, cid):
        return
    s = get_settings(cid)
    if not s["auto_enabled"] or not s["auto_text"]:
        await update.message.reply_text("پیام خودکار فعال نیست.")
        return
    await update.message.reply_text(s["auto_text"], parse_mode="HTML")

# ---------- Events ----------

async def new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        return
    cid = update.effective_chat.id
    ensure_settings(cid)

    for user in update.message.new_chat_members:
        try:
            await send_welcome_photo(context, cid, user)
        except Exception as e:
            await update.message.reply_text(
                f'خوش آمدی {mention_html(user)} 🌷',
                parse_mode="HTML"
            )

async def track_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_user:
        return
    if update.effective_chat.type not in ("group", "supergroup"):
        return
    if update.effective_user.is_bot:
        return

    cid = update.effective_chat.id
    user = update.effective_user
    ensure_settings(cid)

    db.execute("""
        INSERT INTO stats(chat_id,user_id,name,username,messages)
        VALUES(?,?,?,?,1)
        ON CONFLICT(chat_id,user_id) DO UPDATE SET
          name=excluded.name,
          username=excluded.username,
          messages=messages+1
    """, (cid, user.id, display_name(user), user.username))
    db.commit()

    s = get_settings(cid)
    # Optional auto reply: reply only to the first tracked message after activation
    # is intentionally kept simple and reliable.
    if s["auto_enabled"] and s["auto_text"]:
        now = datetime.now().timestamp()
        last = context.chat_data.get("last_auto_reply", 0)
        if now - last >= 300:
            context.chat_data["last_auto_reply"] = now
            try:
                await update.effective_message.reply_text(s["auto_text"], parse_mode="HTML")
            except Exception:
                pass

async def my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create settings when bot is added to a group."""
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        ensure_settings(chat.id)

# ---------- Main ----------

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start, filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("groups", groups, filters.ChatType.PRIVATE))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
        private_input
    ))

    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("tag", cmd_tag))
    app.add_handler(CommandHandler("auto", cmd_auto))

    app.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        new_members
    ))
    app.add_handler(ChatMemberHandler(
        my_chat_member,
        ChatMemberHandler.MY_CHAT_MEMBER
    ))
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & ~filters.COMMAND,
        track_messages
    ))

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
