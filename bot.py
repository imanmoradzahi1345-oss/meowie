# -*- coding: utf-8 -*-
"""
ربات تلگرام نمایشی با پنل ادمین کامل
- ادمین: 7530457395
- منوی استارت قابل تنظیم
- بخش‌ها با دکمه شیشه‌ای + متن + عکس + توضیحات
- درخواست شماره/لوکیشن فقط در بخشی که ادمین مشخص کند
- مشاهده پیام‌های کاربران
- ارسال پیام همگانی
"""

import logging
import json
import os
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ==================== تنظیمات ====================
BOT_TOKEN = "8898641243:AAHB-k76A8ZUcoAGwghUHLuf1EWzAyyYmPU"
ADMIN_ID = 7530457395
DATA_FILE = "bot_data.json"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ==================== مدیریت داده ====================
def load_data() -> dict:
    default = {
        "start_message": "👋 سلام! به ربات خوش آمدید.\n\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        "sections": [],  # هیچ بخش پیش‌فرضی نیست - همه چیز از پنل ادمین ساخته می‌شود
        "users": {},
        "messages": [],
        "after_contact_msg": "✅ شماره شما با موفقیت ثبت شد. ممنون!",
        "after_location_msg": "✅ لوکیشن شما با موفقیت ثبت شد. ممنون!",
    }
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in default.items():
                    if k not in data:
                        data[k] = v
                # مطمئن شو همه بخش‌ها type دارند
                for sec in data.get("sections", []):
                    if "type" not in sec:
                        sec["type"] = "normal"
                return data
        except Exception as e:
            logger.error(f"خطا در خواندن فایل: {e}")
    return default


def save_data(data: dict):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"خطا در ذخیره فایل: {e}")


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# ==================== کیبوردها ====================
def get_main_keyboard(data: dict) -> InlineKeyboardMarkup:
    buttons = []
    for sec in data.get("sections", []):
        buttons.append([
            InlineKeyboardButton(sec["title"], callback_data=f"sec_{sec['id']}")
        ])
    return InlineKeyboardMarkup(buttons) if buttons else InlineKeyboardMarkup([])


def get_admin_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📝 تنظیم پیام استارت", callback_data="admin_edit_start")],
        [InlineKeyboardButton("➕ افزودن بخش جدید", callback_data="admin_add_section")],
        [InlineKeyboardButton("📋 لیست بخش‌ها / حذف", callback_data="admin_list_sections")],
        [InlineKeyboardButton("💬 پیام‌های کاربران", callback_data="admin_messages")],
        [InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("👥 آمار کاربران", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 بستن پنل", callback_data="admin_close")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 ارسال شماره تماس", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def get_location_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📍 ارسال لوکیشن", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# ==================== /start ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = load_data()
    user_id = str(user.id)

    # ثبت کاربر
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "name": user.full_name,
            "username": user.username or "-",
            "phone": None,
            "location": None,
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    else:
        data["users"][user_id]["name"] = user.full_name
        data["users"][user_id]["username"] = user.username or "-"
    save_data(data)

    # ادمین → پنل
    if is_admin(user.id):
        await update.message.reply_text(
            "🔐 <b>پنل مدیریت ربات</b>\n\nاز منوی زیر تنظیمات را انجام دهید:",
            reply_markup=get_admin_keyboard(),
            parse_mode="HTML",
        )
        return

    # کاربر عادی → فقط پیام استارت + دکمه‌های بخش‌ها (بدون اجبار شماره)
    await update.message.reply_text(
        data.get("start_message", "سلام!"),
        reply_markup=get_main_keyboard(data),
        parse_mode="HTML",
    )


# ==================== کال‌بک بخش‌ها (کاربر) ====================
async def section_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = load_data()
    sec_id = query.data.replace("sec_", "")
    section = next((s for s in data["sections"] if s["id"] == sec_id), None)

    if not section:
        await query.edit_message_text("❌ بخش پیدا نشد.")
        return

    sec_type = section.get("type", "normal")

    # ---- بخش درخواست شماره ----
    if sec_type == "contact":
        text = section.get("text") or "لطفاً شماره تماس خود را ارسال کنید:"
        if section.get("description"):
            text = f"{section['description']}\n\n{text}"
        try:
            await query.message.reply_text(
                text,
                reply_markup=get_contact_keyboard(),
                parse_mode="HTML",
            )
            await query.delete_message()
        except Exception:
            await query.edit_message_text(text, parse_mode="HTML")
            await query.message.reply_text(
                "دکمه زیر را بزنید:",
                reply_markup=get_contact_keyboard(),
            )
        return

    # ---- بخش درخواست لوکیشن ----
    if sec_type == "location":
        text = section.get("text") or "لطفاً لوکیشن خود را ارسال کنید:"
        if section.get("description"):
            text = f"{section['description']}\n\n{text}"
        try:
            await query.message.reply_text(
                text,
                reply_markup=get_location_keyboard(),
                parse_mode="HTML",
            )
            await query.delete_message()
        except Exception:
            await query.edit_message_text(text, parse_mode="HTML")
            await query.message.reply_text(
                "دکمه زیر را بزنید:",
                reply_markup=get_location_keyboard(),
            )
        return

    # ---- بخش عادی ----
    text = f"<b>{section['title']}</b>\n\n"
    if section.get("description"):
        text += f"{section['description']}\n\n"
    if section.get("text"):
        text += section["text"]

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
        except Exception as e:
            logger.warning(f"خطا در ارسال عکس: {e}")

    await query.edit_message_text(
        text or "محتوایی وجود ندارد.",
        parse_mode="HTML",
        reply_markup=get_main_keyboard(data),
    )


# ==================== هندلر شماره تماس ====================
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
    await update.message.reply_text(
        "از منوی زیر استفاده کنید:",
        reply_markup=get_main_keyboard(data),
    )


# ==================== هندلر لوکیشن ====================
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
        "از منوی زیر استفاده کنید:",
        reply_markup=get_main_keyboard(data),
    )


# ==================== پیام متنی کاربران ====================
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user.id):
        return  # ادمین در admin_message_handler هندل می‌شود

    text = update.message.text or ""
    data = load_data()
    user_id = str(user.id)

    data["messages"].append({
        "user_id": user_id,
        "name": user.full_name,
        "type": "text",
        "content": text,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    save_data(data)

    await update.message.reply_text(
        "✅ پیام شما دریافت شد.\nاز منوی زیر استفاده کنید:",
        reply_markup=get_main_keyboard(data),
    )


# ==================== پنل ادمین (کال‌بک) ====================
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("⛔ دسترسی ندارید.")
        return

    data = load_data()
    action = query.data

    if action == "admin_menu":
        await query.edit_message_text(
            "🔐 <b>پنل مدیریت ربات</b>\n\nاز منوی زیر انتخاب کنید:",
            reply_markup=get_admin_keyboard(),
            parse_mode="HTML",
        )
        return

    if action == "admin_close":
        await query.edit_message_text("✅ پنل بسته شد.")
        return

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

    if action == "admin_list_sections":
        if not data["sections"]:
            text = "هیچ بخشی تعریف نشده."
            buttons = [[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_menu")]]
        else:
            text = "📋 <b>لیست بخش‌ها:</b>\n\n"
            buttons = []
            for sec in data["sections"]:
                ttype = {"normal": "عادی", "contact": "شماره", "location": "لوکیشن"}.get(sec.get("type", "normal"), "عادی")
                text += f"• {sec['title']}  [{ttype}]\n"
                buttons.append([
                    InlineKeyboardButton(
                        f"🗑 حذف «{sec['title']}»",
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

    if action.startswith("admin_del_sec_"):
        sec_id = action.replace("admin_del_sec_", "")
        data["sections"] = [s for s in data["sections"] if s["id"] != sec_id]
        save_data(data)
        await query.edit_message_text(
            "✅ بخش حذف شد.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_list_sections")]
            ]),
        )
        return

    if action == "admin_messages":
        msgs = data.get("messages", [])[-25:]
        if not msgs:
            text = "هنوز پیامی ثبت نشده."
        else:
            text = "💬 <b>آخرین پیام‌های کاربران:</b>\n\n"
            for m in reversed(msgs):
                content = str(m.get("content", ""))[:70]
                text += (
                    f"👤 {m.get('name', '-')} ({m.get('user_id', '-')})\n"
                    f"📌 {m.get('type', '-')}: {content}\n"
                    f"🕐 {m.get('time', '-')}\n"
                    f"{'─' * 18}\n"
                )
        await query.edit_message_text(
            text[:4000],
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 پاک کردن همه", callback_data="admin_clear_msgs")],
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

    if action == "admin_add_section":
        await query.edit_message_text(
            "➕ <b>افزودن بخش جدید</b>\n\n"
            "نوع بخش را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📄 بخش عادی (متن/عکس)", callback_data="admin_add_type_normal")],
                [InlineKeyboardButton("📱 بخش درخواست شماره", callback_data="admin_add_type_contact")],
                [InlineKeyboardButton("📍 بخش درخواست لوکیشن", callback_data="admin_add_type_location")],
                [InlineKeyboardButton("🔙 انصراف", callback_data="admin_menu")],
            ]),
            parse_mode="HTML",
        )
        return

    if action.startswith("admin_add_type_"):
        sec_type = action.replace("admin_add_type_", "")
        context.user_data["new_section"] = {"type": sec_type}
        context.user_data["admin_state"] = "add_title"
        type_name = {"normal": "عادی", "contact": "درخواست شماره", "location": "درخواست لوکیشن"}.get(sec_type, "")
        await query.edit_message_text(
            f"نوع انتخاب‌شده: <b>{type_name}</b>\n\n"
            "حالا <b>عنوان دکمه</b> را ارسال کنید\n"
            "(مثال: 🛍️ فروشگاه یا 📱 ارسال شماره):",
            parse_mode="HTML",
        )
        return

    if action == "admin_edit_start":
        await query.edit_message_text(
            "📝 پیام فعلی استارت:\n\n"
            f"<code>{data.get('start_message', '')}</code>\n\n"
            "پیام جدید را ارسال کنید:",
            parse_mode="HTML",
        )
        context.user_data["admin_state"] = "edit_start"
        return

    if action == "admin_broadcast":
        await query.edit_message_text(
            "📢 <b>ارسال پیام همگانی</b>\n\n"
            "پیام خود را ارسال کنید (متن یا عکس با کپشن):",
            parse_mode="HTML",
        )
        context.user_data["admin_state"] = "broadcast"
        return


# ==================== پیام‌های ادمین (حالت‌ها) ====================
async def admin_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return

    state = context.user_data.get("admin_state")
    if not state:
        # اگر ادمین پیام عادی فرستاد، فقط جواب نده (یا منو نشون بده)
        return

    data = load_data()
    text = update.message.text or ""

    # ویرایش پیام استارت
    if state == "edit_start":
        data["start_message"] = text
        save_data(data)
        context.user_data["admin_state"] = None
        await update.message.reply_text(
            "✅ پیام استارت با موفقیت تغییر کرد.",
            reply_markup=get_admin_keyboard(),
        )
        return

    # افزودن بخش - عنوان
    if state == "add_title":
        context.user_data["new_section"]["title"] = text
        context.user_data["admin_state"] = "add_text"
        await update.message.reply_text(
            "حالا <b>متن اصلی</b> بخش را بفرستید\n"
            "(یا /skip برای رد کردن):",
            parse_mode="HTML",
        )
        return

    # افزودن بخش - متن
    if state == "add_text":
        if text.strip() != "/skip":
            context.user_data["new_section"]["text"] = text
        else:
            context.user_data["new_section"]["text"] = ""
        context.user_data["admin_state"] = "add_desc"
        await update.message.reply_text(
            "توضیحات کوتاه (اختیاری) را بفرستید\n"
            "(یا /skip):"
        )
        return

    # افزودن بخش - توضیحات
    if state == "add_desc":
        if text.strip() != "/skip":
            context.user_data["new_section"]["description"] = text
        else:
            context.user_data["new_section"]["description"] = ""
        context.user_data["admin_state"] = "add_photo"
        await update.message.reply_text(
            "اگر عکس می‌خواهید، عکس را ارسال کنید.\n"
            "در غیر این صورت /skip بزنید:"
        )
        return

    # افزودن بخش - عکس
    if state == "add_photo":
        new_sec = context.user_data.get("new_section", {})
        photo_id = None

        if update.message.photo:
            photo_id = update.message.photo[-1].file_id
        elif text.strip() == "/skip":
            photo_id = None
        else:
            await update.message.reply_text("لطفاً عکس بفرستید یا /skip بزنید.")
            return

        sec_id = f"s_{int(datetime.now().timestamp())}"
        section = {
            "id": sec_id,
            "title": new_sec.get("title", "بدون عنوان"),
            "text": new_sec.get("text", ""),
            "description": new_sec.get("description", ""),
            "photo": photo_id,
            "type": new_sec.get("type", "normal"),
        }
        data["sections"].append(section)
        save_data(data)

        context.user_data["admin_state"] = None
        context.user_data["new_section"] = None

        type_name = {"normal": "عادی", "contact": "درخواست شماره", "location": "درخواست لوکیشن"}.get(section["type"], "")
        await update.message.reply_text(
            f"✅ بخش «{section['title']}» ({type_name}) با موفقیت اضافه شد.",
            reply_markup=get_admin_keyboard(),
        )
        return

    # برودکست
    if state == "broadcast":
        context.user_data["admin_state"] = None
        users = list(data["users"].keys())
        success = 0
        fail = 0

        status = await update.message.reply_text("⏳ در حال ارسال به کاربران...")

        for uid in users:
            try:
                if update.message.photo:
                    await context.bot.send_photo(
                        chat_id=int(uid),
                        photo=update.message.photo[-1].file_id,
                        caption=update.message.caption or "",
                    )
                else:
                    await context.bot.send_message(chat_id=int(uid), text=text)
                success += 1
            except Exception as e:
                fail += 1
                logger.warning(f"ارسال به {uid} ناموفق: {e}")

        await status.edit_text(
            f"✅ ارسال تمام شد.\n\nموفق: {success}\nناموفق: {fail}"
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
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))

    app.add_handler(CallbackQueryHandler(section_callback, pattern=r"^sec_"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin_"))

    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))

    # پیام‌های ادمین (متن و عکس) برای حالت‌های تنظیم
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.PHOTO) & ~filters.COMMAND,
            admin_message_handler,
        ),
        group=0,
    )

    # پیام‌های کاربران عادی
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message),
        group=1,
    )

    logger.info("ربات شروع شد...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
