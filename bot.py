#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🤖 ربات جایزه بیشترین پیام (نسخه نهایی)
نسخه: ۳.۰
ساخته شده برای PyDroid 3

نصب: pip install python-telegram-bot
"""

import logging
import json
import os
import asyncio
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ChatMemberHandler,
    filters, CallbackQueryHandler, ContextTypes, ConversationHandler
)

# ═══════════════════════════════
# ✏️  تنظیمات
# ═══════════════════════════════
BOT_TOKEN = "8850722490:AAHjx9fjn-QGwvRff-4kzeRA_mU1B-yqtOA"
ADMIN_ID = 7530457395
DATA_FILE = "bot_data.json"

STATE_CONTENT, STATE_COUNT, STATE_INTERVAL = range(3)

# ═══════════════════════════════
# 💾  دیتابیس
# ═══════════════════════════════
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"groups": [], "approved": [ADMIN_ID]}

def save_data(data_dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data_dict, f, ensure_ascii=False, indent=2)

db = load_data()

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

# ═══════════════════════════════
# 🔧  توابع کمکی
# ═══════════════════════════════
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def is_approved(user_id: int) -> bool:
    return user_id in db.get("approved", [])

def build_groups_keyboard():
    groups = db.get("groups", [])
    if not groups:
        return None
    buttons = [[InlineKeyboardButton(g["title"], callback_data=f"grp_{g['id']}")] for g in groups]
    return InlineKeyboardMarkup(buttons)

async def send_content_to_chat(bot, chat_id: int, content: dict):
    ctype = content["type"]
    try:
        if ctype == "text":
            await bot.send_message(chat_id, content["text"])
        elif ctype == "photo":
            await bot.send_photo(chat_id, content["file_id"], caption=content.get("caption", ""))
        elif ctype == "video":
            await bot.send_video(chat_id, content["file_id"], caption=content.get("caption", ""))
        elif ctype == "sticker":
            await bot.send_sticker(chat_id, content["file_id"])
        elif ctype == "animation":
            await bot.send_animation(chat_id, content["file_id"], caption=content.get("caption", ""))
        elif ctype == "audio":
            await bot.send_audio(chat_id, content["file_id"], caption=content.get("caption", ""))
        elif ctype == "document":
            await bot.send_document(chat_id, content["file_id"], caption=content.get("caption", ""))
        elif ctype == "voice":
            await bot.send_voice(chat_id, content["file_id"])
    except Exception as e:
        log.error(f"خطا در ارسال به {chat_id}: {e}")
        raise

async def send_loop(update_obj, context, target_chat_id: int, content: dict,
                    total_count: int, interval: float):
    admin_id = update_obj.effective_user.id
    bot = context.bot

    stop_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⛔ توقف", callback_data="stop_sending")]
    ])

    status_msg = await bot.send_message(
        admin_id,
        f"📤 در حال ارسال...\n0/{total_count}",
        reply_markup=stop_keyboard
    )

    context.chat_data["stop_msg_id"] = status_msg.message_id
    context.chat_data["stop_sending"] = False

    for i in range(1, total_count + 1):
        if context.chat_data.get("stop_sending", False):
            context.chat_data["stop_sending"] = False
            await status_msg.edit_text("⏹ متوقف شد.", reply_markup=None)
            return False

        try:
            await send_content_to_chat(bot, target_chat_id, content)
        except Exception as e:
            await bot.send_message(admin_id, f"❌ خطا در ارسال: {e}")

        if i % 5 == 0 or i == total_count:
            try:
                await status_msg.edit_text(
                    f"📤 در حال ارسال...\n{i}/{total_count}",
                    reply_markup=stop_keyboard
                )
            except:
                pass

        if i < total_count:
            await asyncio.sleep(interval)

    await status_msg.edit_text(f"✅ ارسال کامل شد!\n📊 {total_count} پیام ارسال شد.", reply_markup=None)
    return True

# ═══════════════════════════════
# 👀  تشخیص اضافه شدن به گپ
# ═══════════════════════════════
async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    my_chat_member = update.my_chat_member
    if my_chat_member is None:
        return
    new_status = my_chat_member.new_chat_member.status
    chat = my_chat_member.chat

    if new_status in ("member", "administrator"):
        if any(g["id"] == chat.id for g in db["groups"]):
            return
        db["groups"].append({
            "id": chat.id,
            "title": chat.title or "بدون نام",
            "added": str(datetime.now())
        })
        save_data(db)
        try:
            groups = db["groups"]
            if len(groups) == 1:
                msg = f"✅ گپ تایید شد!\n{chat.title}\nID: {chat.id}"
            else:
                msg = "✅ گپ ها تایید شدن:\n"
                for i, g in enumerate(groups, 1):
                    msg += f"{i}. {g['title']} (ID: {g['id']})\n"
            await context.bot.send_message(ADMIN_ID, msg)
        except Exception as e:
            log.error(f"خطا در اطلاع به ادمین: {e}")

    elif new_status in ("left", "kicked"):
        old_count = len(db["groups"])
        db["groups"] = [g for g in db["groups"] if g["id"] != chat.id]
        if len(db["groups"]) != old_count:
            save_data(db)

# ═══════════════════════════════
# 📞  کالبک‌ها
# ═══════════════════════════════
async def cb_group_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    gid = int(query.data[4:])
    group = next((g for g in db["groups"] if g["id"] == gid), None)
    if not group:
        await query.edit_message_text("❌ گپ یافت نشد.")
        return
    context.chat_data["target_group"] = group
    context.chat_data["pending_content"] = None
    context.chat_data["pending_count"] = None
    context.chat_data["pending_interval"] = None
    await query.edit_message_text(
        f"✅ گپ انتخاب شد: {group['title']}\n\n"
        f"📤 لطفاً محتوای ارسالی رو تایید کنید:\n"
        f"(عکس، فیلم، استیکر، متن، گیف، صدا، فایل)"
    )
    return STATE_CONTENT

async def cb_stop_sending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.chat_data["stop_sending"] = True
    await query.edit_message_text("⏹ متوقف شد.", reply_markup=None)

# ═══════════════════════════════
# 💬  مکالمه ارسال
# ═══════════════════════════════
async def conv_receive_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    msg = update.message
    content = None
    if msg.text and not msg.text.startswith("/"):
        content = {"type": "text", "text": msg.text}
    elif msg.photo:
        content = {"type": "photo", "file_id": msg.photo[-1].file_id, "caption": msg.caption or ""}
    elif msg.video:
        content = {"type": "video", "file_id": msg.video.file_id, "caption": msg.caption or ""}
    elif msg.sticker:
        content = {"type": "sticker", "file_id": msg.sticker.file_id}
    elif msg.animation:
        content = {"type": "animation", "file_id": msg.animation.file_id, "caption": msg.caption or ""}
    elif msg.audio:
        content = {"type": "audio", "file_id": msg.audio.file_id, "caption": msg.caption or ""}
    elif msg.document:
        content = {"type": "document", "file_id": msg.document.file_id, "caption": msg.caption or ""}
    elif msg.voice:
        content = {"type": "voice", "file_id": msg.voice.file_id}
    else:
        await update.message.reply_text("❌ این نوع پیام پشتیبانی نمی‌شود.\nلطفاً عکس، فیلم، استیکر، متن، گیف، صدا یا فایل بفرستید.")
        return STATE_CONTENT
    context.chat_data["pending_content"] = content
    await update.message.reply_text("✅ محتوا دریافت شد.\n\n🔢 حالا **تعداد** را وارد کنید:\nمثال: 100")
    return STATE_COUNT

async def conv_receive_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    text = update.message.text.strip()
    try:
        count = int(text)
        if count < 1 or count > 9999:
            await update.message.reply_text("❌ تعداد باید بین 1 تا 9999 باشد.")
            return STATE_COUNT
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید.")
        return STATE_COUNT
    context.chat_data["pending_count"] = count
    await update.message.reply_text(f"✅ تعداد: {count}\n\n⏱ حالا **فاصله زمانی (ثانیه)** را وارد کنید:\nمثال: 3")
    return STATE_INTERVAL

async def conv_receive_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    text = update.message.text.strip()
    try:
        interval = float(text)
        if interval < 0.5:
            await update.message.reply_text("❌ حداقل فاصله 0.5 ثانیه است.")
            return STATE_INTERVAL
        if interval > 3600:
            await update.message.reply_text("❌ حداکثر فاصله 3600 ثانیه است.")
            return STATE_INTERVAL
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید.")
        return STATE_INTERVAL
    content = context.chat_data.get("pending_content")
    count = context.chat_data.get("pending_count")
    group = context.chat_data.get("target_group")
    if not content or not count or not group:
        await update.message.reply_text("❌ خطا: اطلاعات ناقص است.")
        return ConversationHandler.END
    await update.message.reply_text(f"✅ تنظیمات:\n📍 گپ: {group['title']}\n📦 تعداد: {count}\n⏱ فاصله: {interval} ثانیه\n\n🚀 در حال شروع ارسال...")
    asyncio.create_task(send_loop(update, context, group["id"], content, count, interval))
    return ConversationHandler.END

async def conv_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    await update.message.reply_text("❌ عملیات لغو شد.")
    return ConversationHandler.END

# ═══════════════════════════════════════════════
# 🎯  هندلر اصلی ادمین (ادغام شده)
# ═══════════════════════════════════════════════
async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    یک هندلر برای همه پیام‌های متنی ادمین:
    - اگر شبیه @username یا آیدی عددی باشد ← تایید کاربر
    - در غیر این صورت ← نمایش لیست گپ‌ها
    """
    text = update.message.text.strip()

    # --- تشخیص تایید کاربر ---
    is_username = text.startswith("@") and len(text) > 1
    is_numeric = text.lstrip("-").isdigit() and len(text) >= 5

    if is_username or is_numeric:
        if is_username:
            username = text[1:]
            approved_usernames = db.setdefault("approved_usernames", [])
            if username not in approved_usernames:
                approved_usernames.append(username)
                save_data(db)
            await update.message.reply_text(f"✅ کاربر {text} تایید شد! می‌تواند از ربات استفاده کند.")
        else:
            try:
                target_id = int(text)
            except ValueError:
                return
            if target_id == ADMIN_ID:
                await update.message.reply_text("👑 این خود شما هستید!")
                return
            if target_id in db["approved"]:
                await update.message.reply_text("✅ این کاربر قبلاً تایید شده است.")
                return
            db["approved"].append(target_id)
            save_data(db)
            await update.message.reply_text(f"✅ کاربر با آیدی {target_id} تایید شد! می‌تواند از ربات استفاده کند.")
        return

    # --- در غیر این صورت: نمایش لیست گپ‌ها ---
    groups = db.get("groups", [])
    if not groups:
        await update.message.reply_text(
            "❌ ربات در هیچ گپی عضو نیست.\n"
            "ربات را به یک گپ اضافه کنید تا بتوانید ارسال کنید."
        )
        return

    keyboard = build_groups_keyboard()
    await update.message.reply_text(
        "📋 لطفاً گپ مورد نظر را انتخاب کنید:",
        reply_markup=keyboard
    )

# ═══════════════════════════════
# 🚀  فرمان‌ها
# ═══════════════════════════════
async def cmd_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    groups = db.get("groups", [])
    if not groups:
        await update.message.reply_text("❌ هیچ گپی وجود ندارد.")
        return
    text = "📋 لیست گپ‌ها:\n"
    for i, g in enumerate(groups, 1):
        text += f"{i}. {g['title']} (ID: {g['id']})\n"
    await update.message.reply_text(text, reply_markup=build_groups_keyboard())

async def cmd_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    groups = db.get("groups", [])
    if not groups:
        await update.message.reply_text("❌ ربات در هیچ گپی عضو نیست.")
        return
    if len(groups) == 1:
        g = groups[0]
        try:
            await context.bot.leave_chat(g["id"])
            db["groups"] = []
            save_data(db)
            await update.message.reply_text(f"✅ از گپ {g['title']} خارج شدم.")
        except Exception as e:
            await update.message.reply_text(f"❌ خطا: {e}")
    else:
        buttons = [[InlineKeyboardButton(g["title"], callback_data=f"leave_{g['id']}")] for g in groups]
        buttons.append([InlineKeyboardButton("❌ لغو", callback_data="cancel_leave")])
        await update.message.reply_text("📋 کدام گپ را ترک کنم؟", reply_markup=InlineKeyboardMarkup(buttons))

async def cb_leave_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    data = query.data
    if data == "cancel_leave":
        await query.edit_message_text("❌ لغو شد.")
        return
    if data.startswith("leave_"):
        gid = int(data[6:])
        group = next((g for g in db["groups"] if g["id"] == gid), None)
        if not group:
            await query.edit_message_text("❌ گپ یافت نشد.")
            return
        try:
            await context.bot.leave_chat(gid)
            db["groups"] = [g for g in db["groups"] if g["id"] != gid]
            save_data(db)
            await query.edit_message_text(f"✅ از گپ {group['title']} خارج شدم.")
        except Exception as e:
            await query.edit_message_text(f"❌ خطا: {e}")

async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    users = db.get("approved", [])
    if not users or users == [ADMIN_ID]:
        await update.message.reply_text("👥 هیچ کاربر غیر از ادمین تایید نشده است.")
        return
    text = "👥 کاربران تایید شده:\n"
    for u in users:
        text += f"• {u}\n"
    await update.message.reply_text(text)

async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    args = context.args
    if not args:
        await update.message.reply_text("❌ /remove <id>")
        return
    try:
        uid = int(args[0])
        if uid == ADMIN_ID:
            await update.message.reply_text("❌ نمی‌توانید ادمین اصلی را حذف کنید.")
            return
        if uid in db["approved"]:
            db["approved"].remove(uid)
            save_data(db)
            await update.message.reply_text(f"✅ دسترسی کاربر {uid} حذف شد.")
        else:
            await update.message.reply_text("❌ این کاربر در لیست نیست.")
    except ValueError:
        await update.message.reply_text("❌ آیدی نامعتبر.")

# ═══════════════════════════════
# 🚀  Main
# ═══════════════════════════════
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # فرمان‌ها
    app.add_handler(CommandHandler("groups", cmd_groups))
    app.add_handler(CommandHandler("leave", cmd_leave))
    app.add_handler(CommandHandler("users", cmd_users))
    app.add_handler(CommandHandler("remove", cmd_remove))
    app.add_handler(CommandHandler("cancel", conv_cancel))

    # تشخیص اضافه/حذف شدن از گپ
    app.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))

    # کالبک خروج از گپ
    app.add_handler(CallbackQueryHandler(cb_leave_group, pattern="^leave_|^cancel_leave$"))

    # کالبک توقف ارسال
    app.add_handler(CallbackQueryHandler(cb_stop_sending, pattern="^stop_sending$"))

    # مکالمه ارسال (ورودی: انتخاب گپ)
    send_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_group_selected, pattern="^grp_")],
        states={
            STATE_CONTENT: [MessageHandler(filters.ALL & ~filters.COMMAND, conv_receive_content)],
            STATE_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, conv_receive_count)],
            STATE_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, conv_receive_interval)],
        },
        fallbacks=[CommandHandler("cancel", conv_cancel)],
        name="send_conv", persistent=False,
    )
    app.add_handler(send_conv)

    # === ✅ هندلر اصلی ادمین (یک تابع واحد) ===
    # این تنها هندلر برای متن‌های ادمین است:
    #  - @username یا عدد → تایید کاربر
    #  - هر چیز دیگر → لیست گپ‌ها
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.User(user_id=ADMIN_ID),
            handle_admin_input
        )
    )

    # هندلر کاربران عادی (غیر ادمین)
    async def non_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if is_approved(user.id):
            await update.message.reply_text("✅ شما تایید شده‌اید اما فقط ادمین می‌تواند ارسال کند.")
        else:
            await update.message.reply_text("⛔ شما دسترسی ندارید.")
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, non_admin_handler))

    log.info("✅ ربات راه‌اندازی شد!")
    print("✅ ربات فعال است.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
