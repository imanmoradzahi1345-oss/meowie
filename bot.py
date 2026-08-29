# -*- coding: utf-8 -*-
"""
ربات کارت کلکسیون
- آپلود کارت توسط ادمین + سطح کمیابی
- ارسال زمان‌بندی‌شده در گپ‌ها
- گرفتن کارت با ریپلای «کارت»
- پروفایل کارتی، لیست کارت، تنظیم پروفایل، انتقال کارت
- لقب و سطح بر اساس کارت‌ها
"""

import logging
import json
import os
import random
import string
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatMemberUpdated,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ChatMemberHandler,
)
from telegram.constants import ChatMemberStatus, ChatType

# ==================== تنظیمات ====================
BOT_TOKEN = "8273833935:AAHqnz3EBZPdDtThKRDZ4aN6cyybbujmXd0"
ADMIN_ID = 7530457395
DATA_FILE = "card_bot_data.json"

INTERVALS = [
    3600, 5400, 7200, 9000, 10800, 12600, 14400, 16200, 18000,
]

RARITIES = ["فوق‌کمیاب", "افسانه‌ای", "اولتیمت", "اپیک", "لجند"]
RARITY_EMOJI = {
    "فوق‌کمیاب": "💎",
    "افسانه‌ای": "👑",
    "اولتیمت": "🔥",
    "اپیک": "⚡",
    "لجند": "🌟",
}
RARITY_POINTS = {
    "فوق‌کمیاب": 50,
    "افسانه‌ای": 30,
    "اولتیمت": 20,
    "اپیک": 10,
    "لجند": 5,
}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def default_data():
    return {
        "pool": [],
        "users": {},
        "groups": {},
        "titles": [
            {"name": "تازه‌وارد", "min_points": 0},
            {"name": "جمع‌کننده", "min_points": 20},
            {"name": "شکارچی کارت", "min_points": 50},
            {"name": "افسانه", "min_points": 100},
            {"name": "اسطوره", "min_points": 200},
        ],
    }


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            base = default_data()
            for k, v in base.items():
                if k not in d:
                    d[k] = v
            return d
        except Exception as e:
            logger.error(e)
    return default_data()


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


def gen_code(length=6) -> str:
    chars = string.ascii_lowercase + string.digits
    return "c" + "".join(random.choice(chars) for _ in range(length))


def ensure_user(data, user) -> dict:
    uid = str(user.id)
    if uid not in data["users"]:
        data["users"][uid] = {
            "name": user.full_name,
            "username": user.username or "",
            "cards": [],
            "profile_code": None,
            "points": 0,
            "level": 1,
            "title": "تازه‌وارد",
        }
    else:
        data["users"][uid]["name"] = user.full_name
        data["users"][uid]["username"] = user.username or ""
    return data["users"][uid]


def calc_points(cards: list) -> int:
    return sum(RARITY_POINTS.get(c.get("rarity", "لجند"), 5) for c in cards)


def calc_level(points: int) -> int:
    level = 1
    need = 15
    total = 0
    while points >= total + need:
        total += need
        level += 1
        need = int(need * 1.4) + 10
    return level


def pick_title(data, points: int) -> str:
    titles = sorted(data.get("titles", []), key=lambda t: t.get("min_points", 0))
    chosen = "تازه‌وارد"
    for t in titles:
        if points >= t.get("min_points", 0):
            chosen = t["name"]
    return chosen


def update_user_stats(data, uid: str):
    u = data["users"].get(uid)
    if not u:
        return
    pts = calc_points(u["cards"])
    u["points"] = pts
    u["level"] = calc_level(pts)
    u["title"] = pick_title(data, pts)


def rarity_caption(rarity: str, code: str) -> str:
    em = RARITY_EMOJI.get(rarity, "✨")
    templates = {
        "فوق‌کمیاب": f"{em} یک کارت فوق‌کمیاب ظاهر شد!\nکد: `{code}`\nبرای گرفتن، ریپلای کن و بنویس: کارت",
        "افسانه‌ای": f"{em} کارت افسانه‌ای از راه رسید!\nکد: `{code}`\nریپلای + کلمه کارت = مال تو",
        "اولتیمت": f"{em} قدرت اولتیمت آزاد شد!\nکد: `{code}`\nاولین نفری که «کارت» بفرسته برنده‌ست",
        "اپیک": f"{em} کارت اپیک پیدا شد!\nکد: `{code}`\nریپلای کن و بنویس کارت",
        "لجند": f"{em} کارت لجند آماده شکار!\nکد: `{code}`\nبا ریپلای و نوشتن کارت مال تو می‌شه",
    }
    return templates.get(rarity, f"{em} کارت جدید!\nکد: `{code}`\nریپلای + کارت")


def count_by_rarity(cards: list) -> dict:
    c = {r: 0 for r in RARITIES}
    for card in cards:
        r = card.get("rarity", "لجند")
        c[r] = c.get(r, 0) + 1
    return c


def profile_text(data, uid: str) -> str:
    u = data["users"].get(uid)
    if not u:
        return "کاربر پیدا نشد."
    counts = count_by_rarity(u["cards"])
    lines = [
        f"👤 <b>{u.get('name', '-')}</b>",
        f"🏷 لقب: <b>{u.get('title', '-')}</b>",
        f"📊 سطح: <b>{u.get('level', 1)}</b>",
        f"⭐ امتیاز: <b>{u.get('points', 0)}</b>",
        f"🃏 تعداد کل کارت: <b>{len(u['cards'])}</b>",
        "",
        "📦 به تفکیک:",
    ]
    for r in RARITIES:
        if counts.get(r, 0):
            lines.append(f"{RARITY_EMOJI.get(r, '')} {r}: {counts[r]}")
    if u.get("profile_code"):
        lines.append(f"\n🖼 پروفایل کارتی: <code>{u['profile_code']}</code>")
    else:
        lines.append("\n🖼 پروفایل کارتی: تنظیم نشده")
    return "\n".join(lines)


def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 آپلود کارت جدید", callback_data="ad_upload")],
        [InlineKeyboardButton("📋 موجودی استخر کارت", callback_data="ad_pool")],
        [InlineKeyboardButton("🏷 مدیریت لقب‌ها", callback_data="ad_titles")],
        [InlineKeyboardButton("👥 آمار", callback_data="ad_stats")],
        [InlineKeyboardButton("📢 ارسال فوری در همه گپ‌ها", callback_data="ad_force")],
    ])


def rarity_keyboard():
    rows = [[InlineKeyboardButton(f"{RARITY_EMOJI.get(r, '')} {r}", callback_data=f"ad_rar_{r}")] for r in RARITIES]
    rows.append([InlineKeyboardButton("❌ انصراف", callback_data="ad_cancel")])
    return InlineKeyboardMarkup(rows)


def profile_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 لیست کارت‌هام", callback_data="my_cards")],
        [InlineKeyboardButton("🖼 تنظیم پروفایل کارتی", callback_data="set_profile")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = load_data()
    ensure_user(data, user)
    save_data(data)

    if is_admin(user.id) and update.effective_chat.type == ChatType.PRIVATE:
        await update.message.reply_text(
            "🔐 <b>پنل ادمین</b>\n\nاز منو استفاده کن. تو هم می‌تونی تو گپ‌ها کارت جمع کنی.",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )
        return

    text = (
        "🎴 <b>ربات کارت کلکسیون</b>\n\n"
        "تو گپ‌ها کارت رندوم میاد.\n"
        "اولین نفری که ریپلای کنه و بنویسه <b>کارت</b> برنده‌ست.\n\n"
        "دستورات:\n"
        "• <code>پروفایلم</code> → پروفایل خودت\n"
        "• ریپلای + <code>پروفایل کارتی</code> → پروفایل اون نفر\n"
        "• <code>انتقال کارت کد</code> → انتقال کارت (با ریپلای روی گیرنده)\n\n"
        "از دکمه‌ها هم استفاده کن:"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=profile_keyboard())


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.message.reply_text("پنل ادمین فقط تو پیوی رباته.")
        return
    await update.message.reply_text("🔐 پنل ادمین:", reply_markup=admin_keyboard())


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 <b>راهنما</b>\n\n"
        "• وقتی کارت تو گپ میاد، ریپلای کن و بنویس: <b>کارت</b>\n"
        "• <code>پروفایلم</code> → پروفایل خودت\n"
        "• ریپلای روی کسی + <code>پروفایل کارتی</code> → پروفایل اون\n"
        "• <code>انتقال کارت کد</code> + ریپلای روی گیرنده\n"
        "• دکمه‌های لیست کارت و تنظیم پروفایل\n\n"
        "ربات را به گپ اضافه کن تا خودکار شروع کند.",
        parse_mode="HTML",
        reply_markup=profile_keyboard(),
    )


async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result: ChatMemberUpdated = update.my_chat_member
    chat = result.chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    new = result.new_chat_member
    if new.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR):
        data = load_data()
        cid = str(chat.id)
        if cid not in data["groups"]:
            data["groups"][cid] = {
                "interval_index": 0,
                "next_send": datetime.now().isoformat(),
                "active_msg_id": None,
                "active_card_code": None,
                "title": chat.title or "",
            }
            save_data(data)
            try:
                await context.bot.send_message(
                    chat.id,
                    "🎴 ربات کارت فعال شد!\n"
                    "هر از گاهی کارت رندوم میاد.\n"
                    "با ریپلای و نوشتن <b>کارت</b> می‌تونی بگیری‌ش.\n\n"
                    "دستورات: پروفایلم | پروفایل کارتی (ریپلای) | انتقال کارت",
                    parse_mode="HTML",
                )
            except Exception:
                pass
            if context.job_queue:
                context.job_queue.run_once(
                    job_send_card,
                    when=20,
                    chat_id=chat.id,
                    name=f"send_{cid}",
                    data={"chat_id": chat.id},
                )


async def job_send_card(context: ContextTypes.DEFAULT_TYPE):
    chat_id = None
    if context.job and context.job.data:
        chat_id = context.job.data.get("chat_id")
    if not chat_id and context.job:
        chat_id = context.job.chat_id
    if not chat_id:
        return
    await send_card_to_group(context, int(chat_id))


async def send_card_to_group(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    data = load_data()
    cid = str(chat_id)

    if not data["pool"]:
        try:
            await context.bot.send_message(chat_id, "⏳ فعلاً کارتی تو استخر نیست.")
        except Exception:
            pass
        _schedule_next(context, data, chat_id)
        save_data(data)
        return

    card = random.choice(data["pool"])
    data["pool"] = [c for c in data["pool"] if c["code"] != card["code"]]

    caption = rarity_caption(card["rarity"], card["code"])
    try:
        msg = await context.bot.send_photo(
            chat_id=chat_id,
            photo=card["file_id"],
            caption=caption,
            parse_mode="Markdown",
        )
        if cid not in data["groups"]:
            data["groups"][cid] = {
                "interval_index": 0,
                "next_send": None,
                "active_msg_id": None,
                "active_card_code": None,
                "title": "",
            }
        g = data["groups"][cid]
        g["active_msg_id"] = msg.message_id
        g["active_card_code"] = card["code"]
        g["pending_card"] = card
        save_data(data)
    except Exception as e:
        logger.error(f"send card error: {e}")
        data["pool"].append(card)
        save_data(data)

    _schedule_next(context, data, chat_id)
    save_data(data)


def _schedule_next(context, data, chat_id: int):
    if not context.job_queue:
        return
    cid = str(chat_id)
    if cid not in data["groups"]:
        data["groups"][cid] = {"interval_index": 0}
    g = data["groups"][cid]
    idx = g.get("interval_index", 0) % len(INTERVALS)
    delay = INTERVALS[idx]
    g["interval_index"] = (idx + 1) % len(INTERVALS)
    g["next_send"] = (datetime.now() + timedelta(seconds=delay)).isoformat()

    name = f"send_{cid}"
    for job in context.job_queue.get_jobs_by_name(name):
        job.schedule_removal()

    context.job_queue.run_once(
        job_send_card,
        when=delay,
        chat_id=chat_id,
        name=name,
        data={"chat_id": chat_id},
    )


async def claim_card(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict):
    user = update.effective_user
    chat = update.effective_chat
    reply = update.message.reply_to_message
    cid = str(chat.id)

    g = data["groups"].get(cid)
    if not g or not g.get("active_card_code"):
        return
    if reply.message_id != g.get("active_msg_id"):
        return

    card = g.get("pending_card")
    if not card:
        return

    g["active_card_code"] = None
    g["pending_card"] = None
    g["active_msg_id"] = None

    uid = str(user.id)
    ensure_user(data, user)
    u = data["users"][uid]
    old_count = len(u["cards"])
    old_level = u.get("level", 1)

    u["cards"].append(card)
    update_user_stats(data, uid)
    new_count = len(u["cards"])
    new_level = u.get("level", 1)
    save_data(data)

    tag = f"@{user.username}" if user.username else user.full_name
    new_cap = (
        f"✅ کارت توسط {tag} گرفته شد!\n"
        f"نوع: {RARITY_EMOJI.get(card['rarity'], '')} {card['rarity']}\n"
        f"کد: {card['code']}\n"
        f"کارت‌ها: {old_count} → {new_count}\n"
        f"سطح: {old_level} → {new_level}"
    )
    try:
        await context.bot.edit_message_caption(
            chat_id=chat.id,
            message_id=reply.message_id,
            caption=new_cap,
        )
    except Exception:
        await update.message.reply_text(new_cap)

    await update.message.reply_text(f"🎉 {tag} کارت {card['rarity']} رو گرفت!")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    chat = update.effective_chat
    text = update.message.text.strip()
    data = load_data()
    ensure_user(data, user)

    if text.startswith("انتقال کارت"):
        await handle_transfer_start(update, context, data, text)
        return

    if text in ("پروفایلم", "پروفایل من", "/profile"):
        update_user_stats(data, str(user.id))
        save_data(data)
        uid = str(user.id)
        txt = profile_text(data, uid)
        u = data["users"][uid]
        photo = None
        if u.get("profile_code"):
            for c in u["cards"]:
                if c["code"] == u["profile_code"]:
                    photo = c["file_id"]
                    break
        if photo:
            await update.message.reply_photo(
                photo=photo, caption=txt, parse_mode="HTML", reply_markup=profile_keyboard()
            )
        else:
            await update.message.reply_text(txt, parse_mode="HTML", reply_markup=profile_keyboard())
        return

    if text in ("پروفایل کارتی", "پروفایل کارت") and update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        if not target:
            return
        ensure_user(data, target)
        update_user_stats(data, str(target.id))
        save_data(data)
        uid = str(target.id)
        txt = profile_text(data, uid)
        u = data["users"][uid]
        photo = None
        if u.get("profile_code"):
            for c in u["cards"]:
                if c["code"] == u["profile_code"]:
                    photo = c["file_id"]
                    break
        if photo:
            await update.message.reply_photo(photo=photo, caption=txt, parse_mode="HTML")
        else:
            await update.message.reply_text(txt, parse_mode="HTML")
        return

    if text == "کارت" and update.message.reply_to_message and chat.type in (
        ChatType.GROUP, ChatType.SUPERGROUP
    ):
        await claim_card(update, context, data)
        return

    if is_admin(user.id) and context.user_data.get("admin_state") == "add_title_name":
        context.user_data["new_title_name"] = text
        context.user_data["admin_state"] = "add_title_points"
        await update.message.reply_text(
            f"لقب: <b>{text}</b>\nحداقل امتیاز لازم را عدد بفرست (مثلاً ۵۰):",
            parse_mode="HTML",
        )
        return

    if is_admin(user.id) and context.user_data.get("admin_state") == "add_title_points":
        try:
            pts = int(text)
        except ValueError:
            await update.message.reply_text("یک عدد بفرست.")
            return
        name = context.user_data.get("new_title_name", "بدون‌نام")
        data["titles"].append({"name": name, "min_points": pts})
        data["titles"].sort(key=lambda t: t["min_points"])
        save_data(data)
        context.user_data.clear()
        await update.message.reply_text(
            f"✅ لقب «{name}» با حداقل {pts} امتیاز ثبت شد.",
            reply_markup=admin_keyboard(),
        )
        return

    if context.user_data.get("mode") == "set_profile":
        code = text.strip().lstrip("`")
        uid = str(user.id)
        u = data["users"][uid]
        found = next((c for c in u["cards"] if c["code"] == code), None)
        if not found:
            await update.message.reply_text("این کد بین کارت‌های تو نیست.")
            context.user_data.pop("mode", None)
            return
        u["profile_code"] = code
        save_data(data)
        context.user_data.pop("mode", None)
        await update.message.reply_photo(
            photo=found["file_id"],
            caption=f"✅ پروفایل کارتی تنظیم شد.\nکد: <code>{code}</code>",
            parse_mode="HTML",
            reply_markup=profile_keyboard(),
        )
        return


async def handle_transfer_start(update, context, data, text):
    user = update.effective_user
    parts = text.split()
    if len(parts) < 3:
        await update.message.reply_text(
            "فرمت:\n<code>انتقال کارت کدکارت</code>\nو روی پیام گیرنده ریپلای کن.",
            parse_mode="HTML",
        )
        return

    code = parts[2].strip().lstrip("`")
    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("باید روی پیام گیرنده ریپلای کنی.")
        return

    target = update.message.reply_to_message.from_user
    if target.id == user.id:
        await update.message.reply_text("نمی‌تونی به خودت منتقل کنی.")
        return
    if target.is_bot:
        await update.message.reply_text("نمی‌تونی به ربات منتقل کنی.")
        return

    uid = str(user.id)
    u = data["users"].get(uid)
    if not u:
        await update.message.reply_text("کارتی نداری.")
        return
    card = next((c for c in u["cards"] if c["code"] == code), None)
    if not card:
        await update.message.reply_text("این کد مال تو نیست.")
        return

    context.user_data["transfer"] = {
        "code": code,
        "from_id": uid,
        "to_id": str(target.id),
        "to_name": target.full_name,
    }
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ تایید انتقال", callback_data="tr_yes"),
        InlineKeyboardButton("❌ انصراف", callback_data="tr_no"),
    ]])
    await update.message.reply_text(
        f"انتقال کارت <code>{code}</code> ({card['rarity']}) به <b>{target.full_name}</b>\nمطمئنی؟",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = load_data()
    ensure_user(data, user)
    cb = query.data

    if cb == "tr_no":
        context.user_data.pop("transfer", None)
        await query.edit_message_text("انتقال لغو شد.")
        return

    if cb == "tr_yes":
        tr = context.user_data.get("transfer")
        if not tr or str(user.id) != tr["from_id"]:
            await query.edit_message_text("منقضی شده.")
            return
        from_u = data["users"][tr["from_id"]]
        card = next((c for c in from_u["cards"] if c["code"] == tr["code"]), None)
        if not card:
            await query.edit_message_text("کارت پیدا نشد.")
            return
        from_u["cards"] = [c for c in from_u["cards"] if c["code"] != tr["code"]]
        if from_u.get("profile_code") == tr["code"]:
            from_u["profile_code"] = None
        tid = tr["to_id"]
        if tid not in data["users"]:
            data["users"][tid] = {
                "name": tr["to_name"], "username": "", "cards": [],
                "profile_code": None, "points": 0, "level": 1, "title": "تازه‌وارد",
            }
        data["users"][tid]["cards"].append(card)
        update_user_stats(data, tr["from_id"])
        update_user_stats(data, tid)
        save_data(data)
        context.user_data.pop("transfer", None)
        await query.edit_message_text(
            f"✅ کارت <code>{tr['code']}</code> به {tr['to_name']} منتقل شد.",
            parse_mode="HTML",
        )
        try:
            await context.bot.send_message(
                int(tid),
                f"🎁 کارت جدید دریافت کردی!\nکد: <code>{tr['code']}</code>\nنوع: {card['rarity']}",
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    if cb == "my_cards":
        if query.message.chat.type != ChatType.PRIVATE:
            try:
                await context.bot.send_message(
                    user.id,
                    "برای دیدن کارت‌ها از دکمه‌های زیر استفاده کن یا /start بزن:",
                    reply_markup=profile_keyboard(),
                )
                await query.answer("پیوی ربات رو چک کن", show_alert=True)
            except Exception:
                await query.answer("اول پیوی ربات رو /start کن، بعد دوباره بزن.", show_alert=True)
            return
        await send_my_cards(query, data, user)
        return

    if cb == "set_profile":
        if query.message.chat.type != ChatType.PRIVATE:
            try:
                await context.bot.send_message(user.id, "کد کارتی که می‌خوای پروفایل بشه رو بفرست:")
                # mode must be set on user's context - use data file flag is hard; message them
                await query.answer("پیوی رو چک کن و کد را همانجا بفرست بعد از /start", show_alert=True)
            except Exception:
                await query.answer("اول ربات را تو پیوی /start کن.", show_alert=True)
            return
        context.user_data["mode"] = "set_profile"
        await query.edit_message_text("کد کارت را بفرست (مثلاً cabc123):")
        return

    if not is_admin(user.id):
        return

    if cb == "ad_cancel":
        context.user_data.clear()
        await query.edit_message_text("لغو شد.", reply_markup=admin_keyboard())
        return

    if cb == "ad_upload":
        context.user_data["admin_state"] = "wait_photo"
        await query.edit_message_text("عکس کارت را بفرست:")
        return

    if cb.startswith("ad_rar_"):
        rarity = cb.replace("ad_rar_", "")
        file_id = context.user_data.get("upload_file_id")
        if not file_id:
            await query.edit_message_text("عکس پیدا نشد. دوباره آپلود کن.", reply_markup=admin_keyboard())
            return
        code = gen_code()
        card = {
            "code": code,
            "file_id": file_id,
            "rarity": rarity,
            "caption": rarity_caption(rarity, code),
            "added_at": datetime.now().isoformat(),
        }
        data["pool"].append(card)
        save_data(data)
        context.user_data.clear()
        await query.edit_message_text(
            f"✅ کارت اضافه شد.\nکد: <code>{code}</code>\n"
            f"سطح: {RARITY_EMOJI.get(rarity, '')} {rarity}\n"
            f"موجودی استخر: {len(data['pool'])}",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )
        return

    if cb == "ad_pool":
        n = len(data["pool"])
        by = {}
        for c in data["pool"]:
            by[c["rarity"]] = by.get(c["rarity"], 0) + 1
        lines = [f"📦 استخر: <b>{n}</b> کارت\n"]
        for r in RARITIES:
            if by.get(r):
                lines.append(f"{RARITY_EMOJI.get(r, '')} {r}: {by[r]}")
        await query.edit_message_text("\n".join(lines) or "خالی", parse_mode="HTML", reply_markup=admin_keyboard())
        return

    if cb == "ad_stats":
        total_users = len(data["users"])
        total_cards = sum(len(u["cards"]) for u in data["users"].values())
        groups = len(data["groups"])
        await query.edit_message_text(
            f"📊 کاربران: {total_users}\n🃏 کارت‌های جمع‌شده: {total_cards}\n"
            f"📦 استخر: {len(data['pool'])}\n👥 گپ‌ها: {groups}",
            reply_markup=admin_keyboard(),
        )
        return

    if cb == "ad_titles":
        lines = ["🏷 لقب‌ها:\n"]
        for t in data.get("titles", []):
            lines.append(f"• {t['name']} (از {t.get('min_points', 0)} امتیاز)")
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ لقب جدید", callback_data="ad_add_title")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="ad_back")],
            ]),
        )
        return

    if cb == "ad_add_title":
        context.user_data["admin_state"] = "add_title_name"
        await query.edit_message_text("اسم لقب را بفرست:")
        return

    if cb == "ad_back":
        await query.edit_message_text("پنل ادمین:", reply_markup=admin_keyboard())
        return

    if cb == "ad_force":
        if not data["pool"]:
            await query.answer("استخر خالی است", show_alert=True)
            return
        count = 0
        for cid in list(data["groups"].keys()):
            try:
                await send_card_to_group(context, int(cid))
                count += 1
            except Exception as e:
                logger.error(e)
        await query.answer(f"ارسال به {count} گپ", show_alert=True)
        return


async def send_my_cards(query, data, user):
    uid = str(user.id)
    u = data["users"].get(uid)
    if not u or not u["cards"]:
        await query.edit_message_text("هنوز کارتی نداری.", reply_markup=profile_keyboard())
        return
    await query.edit_message_text(f"🃏 {len(u['cards'])} کارت داری. دارم می‌فرستم...")
    for c in u["cards"][:30]:
        cap = f"{RARITY_EMOJI.get(c['rarity'], '')} {c['rarity']}\nکد: <code>{c['code']}</code>"
        try:
            await query.message.reply_photo(photo=c["file_id"], caption=cap, parse_mode="HTML")
        except Exception:
            pass
    await query.message.reply_text("تمام.", reply_markup=profile_keyboard())


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    if context.user_data.get("admin_state") != "wait_photo":
        return
    photo = update.message.photo[-1]
    context.user_data["upload_file_id"] = photo.file_id
    context.user_data["admin_state"] = "wait_rarity"
    await update.message.reply_text("سطح کمیابی این کارت؟", reply_markup=rarity_keyboard())


async def post_init(app: Application):
    data = load_data()
    jq = app.job_queue
    if not jq:
        logger.warning('JobQueue نیست. نصب کن: pip install "python-telegram-bot[job-queue]"')
        return
    now = datetime.now()
    for cid, g in data.get("groups", {}).items():
        try:
            chat_id = int(cid)
            delay = 60
            ns = g.get("next_send")
            if ns:
                try:
                    t = datetime.fromisoformat(ns)
                    delay = max(30, int((t - now).total_seconds()))
                except Exception:
                    delay = 60
            jq.run_once(
                job_send_card,
                when=delay,
                chat_id=chat_id,
                name=f"send_{cid}",
                data={"chat_id": chat_id},
            )
            logger.info(f"scheduled {cid} in {delay}s")
        except Exception as e:
            logger.error(e)


def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    logger.info("Card bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
