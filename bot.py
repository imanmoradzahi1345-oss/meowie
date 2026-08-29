# -*- coding: utf-8 -*-
"""
ربات تلگرام نمایشی (دمو) با پنل ادمین کامل
- ادمین: 7530457395
- تنظیم منوی استارت
- اضافه کردن بخش‌ها با دکمه شیشه‌ای + متن + عکس + توضیحات
- درخواست شماره تماس و لوکیشن
- مشاهده پیام‌های کاربران
- ارسال پیام همگانی
"""

import logging
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InputMediaPhoto,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ==================== تنظیمات ====================
BOT_TOKEN = "8927379360:AAHn_W7JKAiAMKe9Gj-pAB5Lz6OeItdpszk"
ADMIN_ID = 7530457395

# فایل ذخیره‌سازی تنظیمات و کاربران
DATA_FILE = "bot_data.json"

# وضعیت‌های Conversation
(
    ADMIN_MENU,
    ADD_SECTION_TITLE,
    ADD_SECTION_TEXT,
    ADD_SECTION_PHOTO,
    ADD_SECTION_DESC,
    EDIT_START_MSG,
    BROADCAST_MSG,
    WAITING_CONTACT,
    WAITING_LOCATION,
) = range(9)

# ==================== لاگ ====================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ==================== مدیریت داده ====================
def load_data() -> dict:
    """بارگذاری داده‌ها از فایل"""
    default = {
        "start_message": "👋 سلام! به ربات خوش آمدید.\n\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        "sections": [
            {
                "id": "about",
                "title": "ℹ️ درباره ما",
                "text": "این یک ربات نمایشی است.",
                "photo": None,
                "description": "توضیحات بخش درباره ما",
            },
            {
                "id": "contact_us",
                "title": "📞 تماس با ما",
                "text": "برای ارتباط با ما از دکمه‌های زیر استفاده کنید.",
                "photo": None,
                "description": "بخش تماس",
            },
        ],
        "users": {},          # user_id -> {name, username, phone, location, joined}
        "messages": [],       # لیست پیام‌های کاربران
        "require_contact": True,
        "require_location": True,
        "after_contact_msg": "✅ شماره شما ثبت شد. حالا لوکیشن خود را ارسال کنید:",
        "after_location_msg": "✅ لوکیشن شما ثبت شد. ممنون!",
        "final_msg": "🎉 ثبت‌نام شما با موفقیت انجام شد.",
    }
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # ادغام با پیش‌فرض برای کلیدهای جدید
                for k, v in default.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception as e:
            logger.error(f"خطا در خواندن فایل: {e}")
    return default


def save_data(data: dict):
    """ذخیره داده‌ها"""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"خطا در ذخیره فایل: {e}")


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# ==================== کیبوردها ====================
def get_main_keyboard(data: dict) -> InlineKeyboardMarkup:
    """کیبورد اصلی کاربر بر اساس بخش‌های تعریف‌شده"""
    buttons = []
    for sec in data.get("sections", []):
        buttons.append([
            InlineKeyboardButton(sec["title"], callback_data=f"sec_{sec['id']}")
        ])
    return InlineKeyboardMarkup(buttons)


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """منوی اصلی ادمین"""
    keyboard = [
        [InlineKeyboardButton("📝 تنظیم پیام استارت", callback_data="admin_edit_start")],
        [InlineKeyboardButton("➕ افزودن بخش جدید", callback_data="admin_add_section")],
        [InlineKeyboardButton("📋 لیست بخش‌ها / حذف", callback_data="admin_list_sections")],
        [InlineKeyboardButton("📞 تنظیم درخواست شماره/لوکیشن", callback_data="admin_contact_loc")],
        [InlineKeyboardButton("💬 پیام‌های کاربران", callback_data="admin_messages")],
        [InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("👥 آمار کاربران", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 بستن پنل", callback_data="admin_close")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_contact_keyboard() -> ReplyKeyboardMarkup:
    """کیبورد درخواست شماره تماس"""
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 ارسال شماره تماس", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def get_location_keyboard() -> ReplyKeyboardMarkup:
    """کیبورد درخواست لوکیشن"""
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📍 ارسال لوکیشن", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# ==================== دستور /start ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = load_data()
    user_id = str(user.id)

    # ثبت/آپدیت کاربر
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "name": user.full_name,
            "username": user.username or "-",
            "phone": None,
            "location": None,
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        save_data(data)
    else:
        data["users"][user_id]["name"] = user.full_name
        data["users"][user_id]["username"] = user.username or "-"
        save_data(data)

    # اگر ادمین است → پنل ادمین
    if is_admin(user.id):
        await update.message.reply_text(
            "🔐 <b>پنل مدیریت ربات</b>\n\n"
            "از منوی زیر تنظیمات را انجام دهید:",
            reply_markup=get_admin_keyboard(),
            parse_mode="HTML",
        )
        return

    # کاربر عادی
    # اگر نیاز به شماره باشد و هنوز نداده
    if data.get("require_contact") and not data["users"][user_id].get("phone"):
        await update.message.reply_text(
            data.get("start_message", "سلام!"),
            reply_markup=get_contact_keyboard(),
        )
        context.user_data["waiting_for"] = "contact"
        return

    # اگر نیاز به لوکیشن باشد و هنوز نداده
    if data.get("require_location") and not data["users"][user_id].get("location"):
        await update.message.reply_text(
            data.get("after_contact_msg", "لطفاً لوکیشن خود را ارسال کنید:"),
            reply_markup=get_location_keyboard(),
        )
        context.user_data["waiting_for"] = "location"
        return

    # نمایش منوی اصلی
    await update.message.reply_text(
        data.get("start_message", "سلام!"),
        reply_markup=get_main_keyboard(data),
        parse_mode="HTML",
    )


# ==================== هندلر تماس و لوکیشن ====================
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.contact:
        return

    user = update.effective_user
    data = load_data()
    user_id = str(user.id)

    phone = update.message.contact.phone_number
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "name": user.full_name,
            "username": user.username or "-",
            "phone": phone,
            "location": None,
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    else:
        data["users"][user_id]["phone"] = phone
    save_data(data)

    # ذخیره پیام
    data["messages"].append({
        "user_id": user_id,
        "name": user.full_name,
        "type": "contact",
        "content": phone,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    save_data(data)

    await update.message.reply_text(
        data.get("after_contact_msg", "✅ شماره ثبت شد."),
        reply_markup=ReplyKeyboardRemove(),
    )

    # اگر لوکیشن هم لازم است
    if data.get("require_location") and not data["users"][user_id].get("location"):
        await update.message.reply_text(
            "حالا لوکیشن خود را ارسال کنید:",
            reply_markup=get_location_keyboard(),
        )
        context.user_data["waiting_for"] = "location"
    else:
        await update.message.reply_text(
            data.get("final_msg", "ثبت‌نام کامل شد."),
            reply_markup=get_main_keyboard(data),
        )


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.location:
        return

    user = update.effective_user
    data = load_data()
    user_id = str(user.id)

    loc = update.message.location
    loc_str = f"{loc.latitude}, {loc.longitude}"

    if user_id not in data["users"]:
        data["users"][user_id] = {
            "name": user.full_name,
            "username": user.username or "-",
            "phone": None,
            "location": loc_str,
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    else:
        data["users"][user_id]["location"] = loc_str
    save_data(data)

    data["messages"].append({
        "user_id": user_id,
        "name": user.full_name,
        "type": "location",
        "content": loc_str,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    save_data(data)

    await update.message.reply_text(
        data.get("after_location_msg", "✅ لوکیشن ثبت شد."),
        reply_markup=ReplyKeyboardRemove(),
    )
    await update.message.reply_text(
        data.get("final_msg", "ثبت‌نام کامل شد."),
        reply_markup=get_main_keyboard(data),
    )


# ==================== پیام‌های متنی کاربران ====================
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user.id):
        # اگر ادمین در حال تنظیم چیزی است، در conversation هندل می‌شود
        return

    text = update.message.text or ""
    data = load_data()
    user_id = str(user.id)

    # ثبت پیام
    data["messages"].append({
        "user_id": user_id,
        "name": user.full_name,
        "type": "text",
        "content": text,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    save_data(data)

    # اگر کاربر هنوز شماره/لوکیشن نداده، دوباره درخواست کن
    if data.get("require_contact") and not data["users"].get(user_id, {}).get("phone"):
        await update.message.reply_text(
            "لطفاً ابتدا شماره تماس خود را ارسال کنید:",
            reply_markup=get_contact_keyboard(),
        )
        return
    if data.get("require_location") and not data["users"].get(user_id, {}).get("location"):
        await update.message.reply_text(
            "لطفاً لوکیشن خود را ارسال کنید:",
            reply_markup=get_location_keyboard(),
        )
        return

    await update.message.reply_text(
        "پیام شما دریافت شد ✅\nاز منوی زیر استفاده کنید:",
        reply_markup=get_main_keyboard(data),
    )


# ==================== کال‌بک‌های کاربر (بخش‌ها) ====================
async def section_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = load_data()
    sec_id = query.data.replace("sec_", "")

    section = next((s for s in data["sections"] if s["id"] == sec_id), None)
    if not section:
        await query.edit_message_text("بخش پیدا نشد.")
        return

    text = f"<b>{section['title']}</b>\n\n"
    if section.get("description"):
        text += f"{section['description']}\n\n"
    if section.get("text"):
        text += section["text"]

    # اگر عکس داشت
    if section.get("photo"):
        try:
            await query.message.reply_photo(
                photo=section["photo"],
                caption=text,
                parse_mode="HTML",
                reply_markup=get_main_keyboard(data),
            )
            await query.delete_message()
            return
        except Exception:
            pass

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=get_main_keyboard(data),
    )


# ==================== پنل ادمین ====================
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if not is_admin(user_id):
        await query.edit_message_text("⛔ دسترسی ندارید.")
        return

    data = load_data()
    action = query.data

    # --- منوی اصلی ادمین ---
    if action == "admin_menu":
        await query.edit_message_text(
            "🔐 <b>پنل مدیریت ربات</b>\n\nاز منوی زیر انتخاب کنید:",
            reply_markup=get_admin_keyboard(),
            parse_mode="HTML",
        )
        return

    # --- بستن ---
    if action == "admin_close":
        await query.edit_message_text("✅ پنل بسته شد.")
        return

    # --- آمار ---
    if action == "admin_stats":
        total = len(data["users"])
        with_phone = sum(1 for u in data["users"].values() if u.get("phone"))
        with_loc = sum(1 for u in data["users"].values() if u.get("location"))
        msg_count = len(data["messages"])
        text = (
            f"📊 <b>آمار ربات</b>\n\n"
            f"👥 تعداد کاربران: <b>{total}</b>\n"
            f"📱 دارای شماره: <b>{with_phone}</b>\n"
            f"📍 دارای لوکیشن: <b>{with_loc}</b>\n"
            f"💬 تعداد پیام‌ها: <b>{msg_count}</b>"
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_menu")]
            ]),
            parse_mode="HTML",
        )
        return

    # --- لیست بخش‌ها ---
    if action == "admin_list_sections":
        if not data["sections"]:
            text = "هیچ بخشی تعریف نشده."
            buttons = [[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_menu")]]
        else:
            text = "📋 <b>لیست بخش‌ها:</b>\n\n"
            buttons = []
            for sec in data["sections"]:
                text += f"• {sec['title']} (id: <code>{sec['id']}</code>)\n"
                buttons.append([
                    InlineKeyboardButton(
                        f"🗑 حذف {sec['title']}",
                        callback_data=f"admin_del_sec_{sec['id']}"
                    )
                ])
            buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_menu")])
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML",
        )
        return

    # --- حذف بخش ---
    if action.startswith("admin_del_sec_"):
        sec_id = action.replace("admin_del_sec_", "")
        data["sections"] = [s for s in data["sections"] if s["id"] != sec_id]
        save_data(data)
        await query.edit_message_text(
            f"✅ بخش حذف شد.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_list_sections")]
            ]),
        )
        return

    # --- تنظیم درخواست شماره/لوکیشن ---
    if action == "admin_contact_loc":
        req_c = "✅ فعال" if data.get("require_contact") else "❌ غیرفعال"
        req_l = "✅ فعال" if data.get("require_location") else "❌ غیرفعال"
        text = (
            f"📞 <b>تنظیم درخواست شماره و لوکیشن</b>\n\n"
            f"درخواست شماره تماس: {req_c}\n"
            f"درخواست لوکیشن: {req_l}\n\n"
            f"با دکمه‌های زیر وضعیت را تغییر دهید."
        )
        keyboard = [
            [InlineKeyboardButton(
                f"شماره تماس: {'خاموش کردن' if data.get('require_contact') else 'روشن کردن'}",
                callback_data="admin_toggle_contact"
            )],
            [InlineKeyboardButton(
                f"لوکیشن: {'خاموش کردن' if data.get('require_location') else 'روشن کردن'}",
                callback_data="admin_toggle_location"
            )],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_menu")],
        ]
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
        return

    if action == "admin_toggle_contact":
        data["require_contact"] = not data.get("require_contact", True)
        save_data(data)
        # برگشت به همان منو
        query.data = "admin_contact_loc"
        await admin_callback(update, context)
        return

    if action == "admin_toggle_location":
        data["require_location"] = not data.get("require_location", True)
        save_data(data)
        query.data = "admin_contact_loc"
        await admin_callback(update, context)
        return

    # --- پیام‌های کاربران ---
    if action == "admin_messages":
        msgs = data.get("messages", [])[-30:]  # آخرین ۳۰ تا
        if not msgs:
            text = "هنوز پیامی ثبت نشده."
        else:
            text = "💬 <b>آخرین پیام‌های کاربران:</b>\n\n"
            for m in reversed(msgs):
                text += (
                    f"👤 {m['name']} ({m['user_id']})\n"
                    f"📌 {m['type']}: {m['content'][:80]}\n"
                    f"🕐 {m['time']}\n"
                    f"{'─' * 20}\n"
                )
        await query.edit_message_text(
            text[:4000],
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 پاک کردن همه پیام‌ها", callback_data="admin_clear_msgs")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_menu")],
            ]),
            parse_mode="HTML",
        )
        return

    if action == "admin_clear_msgs":
        data["messages"] = []
        save_data(data)
        await query.edit_message_text(
            "✅ همه پیام‌ها پاک شدند.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_menu")]
            ]),
        )
        return

    # --- شروع افزودن بخش ---
    if action == "admin_add_section":
        await query.edit_message_text(
            "➕ <b>افزودن بخش جدید</b>\n\n"
            "عنوان دکمه را ارسال کنید (مثلاً: 🛍️ فروشگاه):",
            parse_mode="HTML",
        )
        context.user_data["admin_state"] = "add_title"
        return

    # --- ویرایش پیام استارت ---
    if action == "admin_edit_start":
        await query.edit_message_text(
            "📝 پیام فعلی استارت:\n\n"
            f"{data.get('start_message', '')}\n\n"
            "پیام جدید را ارسال کنید:",
            parse_mode="HTML",
        )
        context.user_data["admin_state"] = "edit_start"
        return

    # --- شروع برودکست ---
    if action == "admin_broadcast":
        await query.edit_message_text(
            "📢 <b>ارسال پیام همگانی</b>\n\n"
            "پیام خود را ارسال کنید (متن یا عکس با کپشن):",
            parse_mode="HTML",
        )
        context.user_data["admin_state"] = "broadcast"
        return


# ==================== هندلر پیام‌های ادمین (حالت‌های مختلف) ====================
async def admin_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return

    state = context.user_data.get("admin_state")
    if not state:
        return

    data = load_data()
    text = update.message.text or ""

    # --- ویرایش پیام استارت ---
    if state == "edit_start":
        data["start_message"] = text
        save_data(data)
        context.user_data["admin_state"] = None
        await update.message.reply_text(
            "✅ پیام استارت به‌روزرسانی شد.",
            reply_markup=get_admin_keyboard(),
        )
        return

    # --- افزودن بخش: عنوان ---
    if state == "add_title":
        context.user_data["new_section"] = {"title": text}
        context.user_data["admin_state"] = "add_text"
        await update.message.reply_text(
            "حالا متن اصلی بخش را ارسال کنید (یا /skip برای رد کردن):"
        )
        return

    # --- افزودن بخش: متن ---
    if state == "add_text":
        if text != "/skip":
            context.user_data["new_section"]["text"] = text
        else:
            context.user_data["new_section"]["text"] = ""
        context.user_data["admin_state"] = "add_desc"
        await update.message.reply_text(
            "توضیحات کوتاه بخش را ارسال کنید (یا /skip):"
        )
        return

    # --- افزودن بخش: توضیحات ---
    if state == "add_desc":
        if text != "/skip":
            context.user_data["new_section"]["description"] = text
        else:
            context.user_data["new_section"]["description"] = ""
        context.user_data["admin_state"] = "add_photo"
        await update.message.reply_text(
            "اگر می‌خواهید عکس اضافه کنید، عکس را ارسال کنید.\n"
            "در غیر این صورت /skip بزنید:"
        )
        return

    # --- افزودن بخش: عکس ---
    if state == "add_photo":
        new_sec = context.user_data.get("new_section", {})
        photo_id = None
        if update.message.photo:
            photo_id = update.message.photo[-1].file_id
        elif text == "/skip":
            photo_id = None
        else:
            await update.message.reply_text("لطفاً عکس بفرستید یا /skip بزنید.")
            return

        # ساخت id یکتا
        sec_id = f"sec_{len(data['sections']) + 1}_{int(datetime.now().timestamp())}"
        section = {
            "id": sec_id,
            "title": new_sec.get("title", "بدون عنوان"),
            "text": new_sec.get("text", ""),
            "description": new_sec.get("description", ""),
            "photo": photo_id,
        }
        data["sections"].append(section)
        save_data(data)

        context.user_data["admin_state"] = None
        context.user_data["new_section"] = None

        await update.message.reply_text(
            f"✅ بخش «{section['title']}» با موفقیت اضافه شد.",
            reply_markup=get_admin_keyboard(),
        )
        return

    # --- برودکست ---
    if state == "broadcast":
        context.user_data["admin_state"] = None
        users = list(data["users"].keys())
        success = 0
        fail = 0

        status_msg = await update.message.reply_text("⏳ در حال ارسال...")

        for uid in users:
            try:
                if update.message.photo:
                    await context.bot.send_photo(
                        chat_id=int(uid),
                        photo=update.message.photo[-1].file_id,
                        caption=update.message.caption or "",
                    )
                else:
                    await context.bot.send_message(
                        chat_id=int(uid),
                        text=text,
                    )
                success += 1
            except Exception as e:
                fail += 1
                logger.warning(f"ارسال به {uid} ناموفق: {e}")

        await status_msg.edit_text(
            f"✅ ارسال تمام شد.\n\n"
            f"موفق: {success}\n"
            f"ناموفق: {fail}",
        )
        await update.message.reply_text(
            "بازگشت به پنل:",
            reply_markup=get_admin_keyboard(),
        )
        return


# ==================== دستور /admin ====================
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ شما ادمین نیستید.")
        return
    await update.message.reply_text(
        "🔐 <b>پنل مدیریت ربات</b>",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML",
    )


# ==================== main ====================
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # دستورات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_command))

    # کال‌بک‌ها
    application.add_handler(CallbackQueryHandler(section_callback, pattern=r"^sec_"))
    application.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin_"))

    # پیام‌های خاص
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))

    # پیام‌های متنی و عکس ادمین (برای حالت‌های تنظیم)
    application.add_handler(
        MessageHandler(
            (filters.TEXT | filters.PHOTO) & ~filters.COMMAND,
            admin_message_handler,
        )
    )

    # پیام‌های کاربران عادی (بعد از ادمین)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message)
    )

    logger.info("ربات شروع به کار کرد...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
