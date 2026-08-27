#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🤖 ربات جایزه گپ (نسخه اختصاصی - اضافه کننده محور)
نسخه: ۴.۰

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
MASTER_ADMIN = 7530457395
DATA_FILE = "bot_data.json"

STATE_CONTENT, STATE_COUNT, STATE_INTERVAL = range(3)

# ═══════════════════════════════
# 💾  دیتابیس
# ═══════════════════════════════
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"groups": [], "bot_enabled": True}

def save_data(data_dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data_dict, f, ensure_ascii=False, indent=2)

db = load_data()

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

# ═══════════════════════════════
# 🔧  توابع کمکی
# ═══════════════════════════════
def is_master(user_id: int) -> bool:
    return user_id == MASTER_ADMIN

def get_user_groups(user_id: int):
    """گپ‌هایی که این کاربر ربات را به آنها اضافه کرده"""
    return [g for g in db["groups"] if g["added_by"] == user_id]

def build_user_groups_keyboard(user_id: int):
    """دکمه‌های شیشه‌ای برای گپ‌های یک کاربر"""
    groups = get_user_groups(user_id)
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
    user_id = update_obj.effective_user.id
    bot = context.bot

    stop_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⛔ توقف", callback_data="stop_sending")]
    ])

    status_msg = await bot.send_message(
        user_id,
        f"📤 در حال ارسال...\n0/{total_count}",
        reply_markup=stop_keyboard
    )
    context.chat_data["stop_sending"] = False

    for i in range(1, total_count + 1):
        if context.chat_data.get("stop_sending", False):
            context.chat_data["stop_sending"] = False
            await status_msg.edit_text("⏹ متوقف شد.", reply_markup=None)
            return False
        try:
            await send_content_to_chat(bot, target_chat_id, content)
        except Exception as e:
            await bot.send_message(user_id, f"❌ خطا: {e}")
        if i % 5 == 0 or i == total_count:
            try:
                await status_msg.edit_text(f"📤 در حال ارسال...\n{i}/{total_count}", reply_markup=stop_keyboard)
            except:
                pass
        if i < total_count:
            await asyncio.sleep(interval)

    await status_msg.edit_text(f"✅ ارسال کامل شد!\n📊 {total_count} پیام ارسال شد.", reply_markup=None)
    return True

# ═══════════════════════════════
# 👀  تشخیص اضافه شدن به گپ + شناسایی اضافه کننده
# ═══════════════════════════════
async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """وقتی ربات به گپ اضافه شد → ببین کیه اضافه کرده"""
    
    # چک خاموش/روشن بودن ربات
    if not db.get("bot_enabled", True):
        return

    my_chat_member = update.my_chat_member
    if my_chat_member is None:
        return

    new_status = my_chat_member.new_chat_member.status
    chat = my_chat_member.chat
    who_did_it = my_chat_member.from_user  # 🎯 کسی که ربات رو اضافه کرده

    # ✅ ربات به گپ اضافه شد
    if new_status in ("member", "administrator"):
        # جلوگیری از ثبت تکراری
        if any(g["id"] == chat.id for g in db["groups"]):
            return

        # ذخیره در دیتابیس
        db["groups"].append({
            "id": chat.id,
            "title": chat.title or "بدون نام",
            "added_by": who_did_it.id,
            "added_by_username": who_did_it.username,
            "added_at": str(datetime.now())
        })
        save_data(db)

        # اطلاع به ادمین اصلی
        try:
            await context.bot.send_message(
                MASTER_ADMIN,
                f"🔔 ربات به گپ جدید اضافه شد\n"
                f"📍 {chat.title}\n"
                f"👤 اضافه کننده: {who_did_it.full_name} (@{who_did_it.username or 'ندارد'})\n"
                f"🆔 {who_did_it.id}"
            )
        except:
            pass

        # ✅ ارسال پیام تایید به فرد اضافه کننده در پیوی خصوصی
        try:
            # اول بهش /start رو یادآوری می‌کنیم
            await context.bot.send_message(
                who_did_it.id,
                f"✅ شما ربات را به گپ «{chat.title}» اضافه کردید.\n\n"
                f"📍 این گپ برای شما تایید شد!\n"
                f"حالا می‌توانید از دستور /send برای ارسال استفاده کنید."
            )
        except Exception as e:
            # کاربر ربات رو استارت نکرده
            log.warning(f"کاربر {who_did_it.id} ربات را استارت نکرده. ارسال پیام در گروه...")
            try:
                await context.bot.send_message(
                    chat.id,
                    f"@{who_did_it.username or who_did_it.first_name} "
                    f"لطفاً ربات را در پیوی خصوصی استارت کنید.\n"
                    f"👉 @{(await context.bot.get_me()).username}"
                )
            except:
                pass

    # ❌ ربات از گپ حذف شد
    elif new_status in ("left", "kicked"):
        old_count = len(db["groups"])
        db["groups"] = [g for g in db["groups"] if g["id"] != chat.id]
        if len(db["groups"]) != old_count:
            save_data(db)

# ═══════════════════════════════
# 🚀  فرمان /start
# ═══════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # ادمین اصلی
    if is_master(user.id):
        status_text = "🟢 روشن" if db.get("bot_enabled", True) else "🔴 خاموش"
        await update.message.reply_text(
            f"👋 خوش آمدید ادمین اصلی!\n\n"
            f"📊 وضعیت ربات: {status_text}\n"
            f"📋 تعداد گپ‌ها: {len(db['groups'])} عدد\n\n"
            f"🔘 /on   → روشن کردن ربات\n"
            f"🔘 /off  → خاموش کردن ربات"
        )
        return

    # کاربر عادی - ببین چی گپ داره
    groups = get_user_groups(user.id)
    if not groups:
        await update.message.reply_text(
            "👋 سلام!\n\n"
            "شما هنوز ربات را به هیچ گپی اضافه نکرده‌اید.\n"
            "ربات را به یک گپ اضافه کنید تا بتوانید از آن استفاده کنید."
        )
        return

    keyboard = build_user_groups_keyboard(user.id)
    await update.message.reply_text(
        f"✅ شما {len(groups)} گپ دارید.\n"
        f"یکی را انتخاب کنید:",
        reply_markup=keyboard
    )

# ═══════════════════════════════
# 🎯  فرمان /send برای کاربران عادی
# ═══════════════════════════════
async def cmd_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if is_master(user.id):
        # ادمین اصلی می‌تونه به همه گپ‌ها بفرسته
        groups = db.get("groups", [])
        if not groups:
            await update.message.reply_text("❌ هیچ گپی وجود ندارد.")
            return
        buttons = [[InlineKeyboardButton(g["title"], callback_data=f"grp_{g['id']}")] for g in groups]
        await update.message.reply_text("📋 کدام گپ؟", reply_markup=InlineKeyboardMarkup(buttons))
        return

    # کاربر عادی - فقط گپ‌های خودش
    groups = get_user_groups(user.id)
    if not groups:
        await update.message.reply_text(
            "❌ شما گپی ندارید.\n"
            "ربات را به یک گپ اضافه کنید."
        )
        return

    keyboard = build_user_groups_keyboard(user.id)
    await update.message.reply_text(
        "📋 گپ مورد نظر را انتخاب کنید:",
        reply_markup=keyboard
    )

# ═══════════════════════════════
# 🔘  خاموش/روشن (فقط ادمین اصلی)
# ═══════════════════════════════
async def cmd_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_master(update.effective_user.id):
        await update.message.reply_text("⛔ فقط ادمین اصلی می‌تواند ربات را روشن کند.")
        return
    db["bot_enabled"] = True
    save_data(db)
    await update.message.reply_text("✅ ربات روشن شد.")

async def cmd_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_master(update.effective_user.id):
        await update.message.reply_text("⛔ فقط ادمین اصلی می‌تواند ربات را خاموش کند.")
        return
    db["bot_enabled"] = False
    save_data(db)
    await update.message.reply_text("🔴 ربات خاموش شد.")

# ═══════════════════════════════
# 📞  کالبک‌ها
# ═══════════════════════════════
async def cb_group_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کاربر یک گپ را انتخاب کرد → شروع دریافت محتوا"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    gid = int(query.data[4:])
    
    # پیدا کردن گپ
    group = next((g for g in db["groups"] if g["id"] == gid), None)
    if not group:
        await query.edit_message_text("❌ گپ یافت نشد.")
        return

    # بررسی دسترسی: ادمین اصلی یا اضافه کننده گپ
    if not is_master(user_id) and group["added_by"] != user_id:
        await query.edit_message_text("⛔ شما به این گپ دسترسی ندارید.")
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
    user = update.effective_user
    group = context.chat_data.get("target_group")
    if not group:
        await update.message.reply_text("❌ لطفاً اول /send را بزنید.")
        return ConversationHandler.END
    
    # بررسی دسترسی مجدد
    if not is_master(user.id) and group["added_by"] != user.id:
        await update.message.reply_text("⛔ شما به این گپ دسترسی ندارید.")
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

    await update.message.reply_text(
        f"✅ تنظیمات:\n📍 گپ: {group['title']}\n📦 تعداد: {count}\n⏱ فاصله: {interval} ثانیه\n\n🚀 در حال شروع ارسال..."
    )
    asyncio.create_task(send_loop(update, context, group["id"], content, count, interval))
    return ConversationHandler.END

async def conv_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ عملیات لغو شد.")
    return ConversationHandler.END

# ═══════════════════════════════
# 🚀  هندلر پیام‌های متنی (برای ادمین اصلی و کاربران)
# ═══════════════════════════════
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر پیش‌فرض برای پیام‌های متنی"""
    user = update.effective_user
    
    if is_master(user.id):
        # ادمین اصلی: راهنمایی
        await update.message.reply_text(
            "👋 دستورات ادمین اصلی:\n"
            "/on  - روشن کردن ربات\n"
            "/off - خاموش کردن ربات\n"
            "/send - ارسال به گپ‌ها\n"
            "/start - وضعیت"
        )
        return

    # کاربر عادی
    groups = get_user_groups(user.id)
    if not groups:
        await update.message.reply_text(
            "👋 شما ربات را به هیچ گپی اضافه نکرده‌اید.\n"
            "ربات را به یک گپ اضافه کنید."
        )
        return

    await update.message.reply_text(
        f"✅ شما {len(groups)} گپ دارید.\n"
        "از /send برای ارسال استفاده کنید."
    )

# ═══════════════════════════════
# 🚀  Main
# ═══════════════════════════════
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # فرمان‌های عمومی
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("send", cmd_send))

    # فرمان‌های ادمین اصلی (خاموش/روشن)
    app.add_handler(CommandHandler("on", cmd_on))
    app.add_handler(CommandHandler("off", cmd_off))
    app.add_handler(CommandHandler("cancel", conv_cancel))

    # تشخیص اضافه شدن به گپ (با شناسایی اضافه کننده)
    app.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))

    # کالبک توقف
    app.add_handler(CallbackQueryHandler(cb_stop_sending, pattern="^stop_sending$"))

    # مکالمه ارسال (entry_point: انتخاب گپ)
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

    # هندلر پیام‌های متنی پیش‌فرض
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    log.info("✅ ربات راه‌اندازی شد!")
    print("✅ ربات فعال است.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
