#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🤖 ربات جایزه بیشترین پیام (Telegram Prize Bot)
نسخه: ۱.۰
ساخته شده برای PyDroid 3

نصب پکیج مورد نیاز در PyDroid:
   pip install python-telegram-bot

نحوه استفاده:
   ۱. توکن ربات خود را در BOT_TOKEN قرار دهید
   ۲. آیدی عددی ادمین را در ADMIN_ID تنظیم کنید
   ۳. فایل را در PyDroid اجرا کنید
"""

import logging
import json
import os
import asyncio
from datetime import datetime
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ChatMemberHandler,
    filters, CallbackQueryHandler, ContextTypes, ConversationHandler
)

# ==============================
# ✏️  تنظیمات (CONFIGURATION)
# ==============================
BOT_TOKEN = "8850722490:AAHjx9fjn-QGwvRff-4kzeRA_mU1B-yqtOA"   # <--- توکن ربات خود را اینجا وارد کنید
ADMIN_ID = 7530457395               # <--- آیدی عددی ادمین اصلی
DATA_FILE = "bot_data.json"         # فایل ذخیره اطلاعات

# حالت‌های مکالمه (Conversation States)
STATE_CONTENT, STATE_COUNT, STATE_INTERVAL = range(3)

# ==============================
# 💾  مدیریت دیتا (DATA LAYER)
# ==============================
def load_data():
    """بارگذاری اطلاعات از فایل JSON"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # مقدار پیش‌فرض: ادمین اصلی همیشه تایید شده است
    return {"groups": [], "approved": [ADMIN_ID]}

def save_data(data_dict):
    """ذخیره اطلاعات در فایل JSON"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data_dict, f, ensure_ascii=False, indent=2)

db = load_data()          # دیتابیس در حافظه

# ==============================
# 📝  لاگینگ (LOGGING)
# ==============================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ==============================
# 🔧  توابع کمکی (UTILITY)
# ==============================
def is_admin(user_id: int) -> bool:
    """آیا کاربر ادمین اصلی است؟"""
    return user_id == ADMIN_ID

def is_approved(user_id: int) -> bool:
    """آیا کاربر تایید شده؟"""
    return user_id in db.get("approved", [])

def get_groups_text() -> str:
    """متن وضعیت گپ‌ها"""
    groups = db.get("groups", [])
    if not groups:
        return "❌ ربات در هیچ گپی عضو نیست."
    if len(groups) == 1:
        g = groups[0]
        return f"✅ گپ تایید شد:\n{g['title']} (ID: {g['id']})"
    text = "✅ گپ ها تایید شدن:\n"
    for i, g in enumerate(groups, 1):
        text += f"{i}. {g['title']} (ID: {g['id']})\n"
    return text

def get_send_button():
    """دکمه ارسال - فقط اگر گپ وجود داشته باشد"""
    if db.get("groups"):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 ارسال", callback_data="send")]
        ])
    return None

async def send_content_to_chat(bot, chat_id: int, content: dict):
    """ارسال محتوا بر اساس نوع آن"""
    ctype = content["type"]
    try:
        if ctype == "text":
            await bot.send_message(chat_id, content["text"])
        elif ctype == "photo":
            await bot.send_photo(chat_id, content["file_id"],
                                 caption=content.get("caption", ""))
        elif ctype == "video":
            await bot.send_video(chat_id, content["file_id"],
                                 caption=content.get("caption", ""))
        elif ctype == "sticker":
            await bot.send_sticker(chat_id, content["file_id"])
        elif ctype == "animation":
            await bot.send_animation(chat_id, content["file_id"],
                                     caption=content.get("caption", ""))
        elif ctype == "audio":
            await bot.send_audio(chat_id, content["file_id"],
                                 caption=content.get("caption", ""))
        elif ctype == "document":
            await bot.send_document(chat_id, content["file_id"],
                                    caption=content.get("caption", ""))
        elif ctype == "voice":
            await bot.send_voice(chat_id, content["file_id"])
    except Exception as e:
        log.error(f"خطا در ارسال به {chat_id}: {e}")
        raise

async def send_to_all_groups(bot, admin_id: int, content: dict,
                              total_count: int, interval: float, context):
    """تسک پس‌زمینه: ارسال محتوا به تمام گپ‌ها

    به صورت round-robin: در هر دور به تمام گپ‌ها ارسال می‌کند
    و به اندازه interval ثانیه صبر می‌کند.
    """
    groups = db.get("groups", [])
    if not groups:
        await bot.send_message(admin_id, "❌ هیچ گپی برای ارسال وجود ندارد.")
        return

    await bot.send_message(
        admin_id,
        f"📤 ارسال شروع شد\n"
        f"📦 تعداد: {total_count}\n"
        f"⏱ فاصله: {interval} ثانیه\n"
        f"👥 گپ‌ها: {len(groups)} عدد"
    )

    total_sent = 0
    for rnd in range(total_count):
        # بررسی دستور توقف
        if context.chat_data.get("stop_sending", False):
            await bot.send_message(admin_id, "⛔ ارسال متوقف شد.")
            context.chat_data["stop_sending"] = False
            return

        for g in groups:
            try:
                await send_content_to_chat(bot, g["id"], content)
                total_sent += 1
            except Exception as e:
                log.error(f"❌ ارسال به {g['title']} ناموفق: {e}")

        # بین دورها صبر کن (به جز دور آخر)
        if rnd < total_count - 1:
            await asyncio.sleep(interval)

    context.chat_data["stop_sending"] = False
    await bot.send_message(
        admin_id,
        f"✅ ارسال با موفقیت کامل شد!\n"
        f"📊 کل پیام‌های ارسال شده: {total_sent}"
    )

# ==============================
# 🎯  هندلرهای فرمان (COMMAND HANDLERS)
# ==============================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فرمان /start"""
    user = update.effective_user
    if not is_approved(user.id):
        await update.message.reply_text("⛔ شما دسترسی به این ربات ندارید.")
        return

    if is_admin(user.id):
        text = f"👋 خوش آمدید ادمین عزیز!\n\n{get_groups_text()}"
        await update.message.reply_text(text, reply_markup=get_send_button())
    else:
        await update.message.reply_text(
            "✅ شما تایید شدید! می‌توانید از ربات استفاده کنید."
        )


async def cmd_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فرمان /groups - نمایش لیست گپ‌ها"""
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(get_groups_text(), reply_markup=get_send_button())


async def cmd_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فرمان /leave - خروج از گپ"""
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
            await update.message.reply_text(f"❌ خطا در خروج: {e}")
    else:
        # چند گپ → منو انتخاب
        buttons = [
            [InlineKeyboardButton(g["title"], callback_data=f"leave_{g['id']}")]
            for g in groups
        ]
        buttons.append([InlineKeyboardButton("❌ لغو", callback_data="cancel_leave")])
        await update.message.reply_text(
            "📋 کدام گپ را ترک کنم؟",
            reply_markup=InlineKeyboardMarkup(buttons)
        )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فرمان /stop - توقف ارسال"""
    if not is_admin(update.effective_user.id):
        return
    context.chat_data["stop_sending"] = True
    await update.message.reply_text("⛛ دستور توقف ارسال صادر شد.")


async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فرمان /users - نمایش کاربران تایید شده"""
    if not is_admin(update.effective_user.id):
        return

    users = db.get("approved", [])
    if not users or users == [ADMIN_ID]:
        await update.message.reply_text("👥 هیچ کاربر غیر از ادمین تایید نشده است.")
        return

    text = "👥 کاربران تایید شده:\n"
    for u in users:
        if u == ADMIN_ID:
            text += f"• {u} (ادمین اصلی)\n"
        else:
            text += f"• {u}\n"
    await update.message.reply_text(text)


async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فرمان /remove <id> - حذف دسترسی کاربر"""
    if not is_admin(update.effective_user.id):
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            "❌ لطفاً آیدی کاربر را وارد کنید.\n"
            "مثال: /remove 123456789"
        )
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
            await update.message.reply_text("❌ این کاربر در لیست تایید شده نیست.")
    except ValueError:
        await update.message.reply_text("❌ آیدی نامعتبر. لطفاً یک عدد وارد کنید.")


# ==============================
# 👀  هندلر عضویت در گپ (CHAT MEMBER)
# ==============================

async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تشخیص اضافه/حذف شدن ربات از گپ (my_chat_member)"""
    my_chat_member = update.my_chat_member
    if my_chat_member is None:
        return

    new_status = my_chat_member.new_chat_member.status
    chat = my_chat_member.chat

    # ✅ ربات به گپ اضافه شد
    if new_status in ("member", "administrator"):
        # جلوگیری از ثبت تکراری
        if any(g["id"] == chat.id for g in db["groups"]):
            return

        db["groups"].append({
            "id": chat.id,
            "title": chat.title or "بدون نام",
            "added": str(datetime.now())
        })
        save_data(db)

        # اطلاع به ادمین
        try:
            groups = db["groups"]
            if len(groups) == 1:
                msg = f"✅ گپ تایید شد!\n{chat.title}\nID: {chat.id}"
            else:
                msg = "✅ گپ ها تایید شدن:\n"
                for i, g in enumerate(groups, 1):
                    msg += f"{i}. {g['title']} (ID: {g['id']})\n"

            await context.bot.send_message(
                ADMIN_ID, msg, reply_markup=get_send_button()
            )
        except Exception as e:
            log.error(f"خطا در اطلاع به ادمین: {e}")

    # ❌ ربات از گپ حذف/لیفت شد
    elif new_status in ("left", "kicked"):
        old_count = len(db["groups"])
        db["groups"] = [g for g in db["groups"] if g["id"] != chat.id]
        if len(db["groups"]) != old_count:
            save_data(db)


# ==============================
# 📞  کالبک‌های دکمه‌ها (CALLBACK QUERY)
# ==============================

async def cb_leave_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کالبک دکمه انتخاب گپ برای خروج"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    data = query.data

    if data == "cancel_leave":
        await query.edit_message_text("❌ عملیات لغو شد.")
        return

    if data.startswith("leave_"):
        try:
            gid = int(data[6:])
        except ValueError:
            await query.edit_message_text("❌ خطا: آیدی نامعتبر.")
            return

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
            await query.edit_message_text(f"❌ خطا در خروج: {e}")


async def cb_send_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کالبک دکمه ارسال → شروع مکالمه"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    if not db.get("groups"):
        await query.edit_message_text("❌ ربات در هیچ گپی عضو نیست.")
        return ConversationHandler.END

    # پاک کردن داده‌های قبلی
    context.chat_data["pending_content"] = None
    context.chat_data["pending_count"] = None
    context.chat_data["pending_interval"] = None

    await query.edit_message_text(
        "📤 لطفاً محتوای ارسالی رو تایید کنید:\n"
        "(عکس، فیلم، استیکر، متن، گیف، صدا، فایل)"
    )
    return STATE_CONTENT


# ==============================
# 💬  مکالمه ارسال (SEND CONVERSATION)
# ==============================

async def conv_receive_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت محتوای ارسالی از ادمین"""
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    msg = update.message
    content = None

    if msg.text and not msg.text.startswith("/"):
        content = {"type": "text", "text": msg.text}
    elif msg.photo:
        content = {
            "type": "photo",
            "file_id": msg.photo[-1].file_id,
            "caption": msg.caption or ""
        }
    elif msg.video:
        content = {
            "type": "video",
            "file_id": msg.video.file_id,
            "caption": msg.caption or ""
        }
    elif msg.sticker:
        content = {"type": "sticker", "file_id": msg.sticker.file_id}
    elif msg.animation:
        content = {
            "type": "animation",
            "file_id": msg.animation.file_id,
            "caption": msg.caption or ""
        }
    elif msg.audio:
        content = {
            "type": "audio",
            "file_id": msg.audio.file_id,
            "caption": msg.caption or ""
        }
    elif msg.document:
        content = {
            "type": "document",
            "file_id": msg.document.file_id,
            "caption": msg.caption or ""
        }
    elif msg.voice:
        content = {"type": "voice", "file_id": msg.voice.file_id}
    else:
        await update.message.reply_text(
            "❌ این نوع پیام پشتیبانی نمی‌شود.\n"
            "لطفاً عکس، فیلم، استیکر، متن، گیف، صدا یا فایل بفرستید."
        )
        return STATE_CONTENT  # همین حالت بمان

    context.chat_data["pending_content"] = content
    await update.message.reply_text(
        "✅ محتوا دریافت شد.\n\n"
        "🔢 حالا **تعداد** را وارد کنید:\n"
        "مثال: 100"
    )
    return STATE_COUNT


async def conv_receive_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت تعداد از ادمین"""
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
    await update.message.reply_text(
        f"✅ تعداد: {count}\n\n"
        f"⏱ حالا **فاصله زمانی (ثانیه)** را وارد کنید:\n"
        f"مثال: 3"
    )
    return STATE_INTERVAL


async def conv_receive_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت فاصله زمانی و شروع ارسال"""
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    text = update.message.text.strip()
    try:
        interval = float(text)
        if interval < 0.5:
            await update.message.reply_text("❌ حداقل فاصله 0.5 ثانیه است.")
            return STATE_INTERVAL
        if interval > 3600:
            await update.message.reply_text("❌ حداکثر فاصله 3600 ثانیه (1 ساعت) است.")
            return STATE_INTERVAL
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید.")
        return STATE_INTERVAL

    content = context.chat_data.get("pending_content")
    count = context.chat_data.get("pending_count")

    if not content or not count:
        await update.message.reply_text("❌ خطا: اطلاعات ناقص است. دوباره تلاش کنید.")
        return ConversationHandler.END

    # شروع ارسال در پس‌زمینه
    asyncio.create_task(
        send_to_all_groups(
            context.bot,
            update.effective_user.id,
            content,
            count,
            interval,
            context
        )
    )

    await update.message.reply_text(
        f"✅ ارسال با موفقیت شروع شد!\n"
        f"📦 تعداد: {count}\n"
        f"⏱ فاصله: {interval} ثانیه\n"
        f"👥 گپ‌ها: {len(db['groups'])} عدد\n\n"
        f"برای توقف: /stop"
    )
    return ConversationHandler.END


async def conv_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لغو مکالمه"""
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    await update.message.reply_text("❌ عملیات لغو شد.")
    return ConversationHandler.END


# ==============================
# ✅  هندلر تایید کاربر (APPROVE)
# ==============================

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر مخصوص ادمین: تایید کاربر با فرستادن آیدی یا یوزرنیم

    اگر ادمین یک متن بفرستد که شبیه @username یا آیدی عددی است،
    ربات آن کاربر را تایید می‌کند.
    """
    text = update.message.text.strip()

    # فقط اگر شبیه @username یا عدد باشد
    is_username = text.startswith("@") and len(text) > 1
    is_numeric = text.lstrip("-").isdigit() and len(text) >= 5

    if not (is_username or is_numeric):
        return  # بی‌خیال، هندل نمی‌کنیم

    # تایید یوزرنیم
    if is_username:
        username = text[1:]
        approved_usernames = db.setdefault("approved_usernames", [])
        if username not in approved_usernames:
            approved_usernames.append(username)
            save_data(db)
        await update.message.reply_text(f"✅ کاربر {text} تایید شد!")
        return

    # تایید آیدی عددی
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
    await update.message.reply_text(f"✅ کاربر با آیدی {target_id} تایید شد!")

# ==============================
# 🚀  تابع اصلی (MAIN)
# ==============================

def main():
    """راه‌اندازی و اجرای ربات"""
    app = Application.builder().token(BOT_TOKEN).build()

    # ─── فرمان‌ها ───
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("groups", cmd_groups))
    app.add_handler(CommandHandler("leave", cmd_leave))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("users", cmd_users))
    app.add_handler(CommandHandler("remove", cmd_remove))

    # ─── تشخیص اضافه/حذف شدن از گپ ───
    app.add_handler(
        ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER)
    )

    # ─── کالبک دکمه‌های خروج از گپ ───
    app.add_handler(
        CallbackQueryHandler(cb_leave_group, pattern="^leave_|^cancel_leave$")
    )

    # ─── مکالمه ارسال (دکمه "ارسال" → محتوا → تعداد → ثانیه) ───
    send_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_send_start, pattern="^send$")],
        states={
            STATE_CONTENT: [
                MessageHandler(
                    filters.ALL & ~filters.COMMAND,
                    conv_receive_content
                )
            ],
            STATE_COUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    conv_receive_count
                )
            ],
            STATE_INTERVAL: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    conv_receive_interval
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", conv_cancel)],
        name="send_conversation",
        persistent=False,
    )
    app.add_handler(send_conversation)

    # ─── تایید کاربر توسط ادمین (بدون دستور، فقط فرستادن آیدی/یوزرنیم) ───
    # این هندلر آخرین است تا با مکالمه تداخل نداشته باشد
    app.add_handler(
        MessageHandler(
            filters.Text() & filters.User(user_id=ADMIN_ID),
            handle_admin_text
        )
    )

    log.info("🤖 ربات با موفقیت راه‌اندازی شد! برای توقف Ctrl+C بزنید.")
    print("✅ ربات فعال است. منتظر پیام‌ها...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
    
