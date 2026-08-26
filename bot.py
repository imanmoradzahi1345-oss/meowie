# -*- coding: utf-8 -*-
"""
ربات تلگرام مدیریت گپ‌ها ── مسابقه بیشترین پیام
قابل اجرا در Pydroid 3
"""

import telebot
from telebot import types
import json
import os
import time
import threading

# ========== توکن ربات خود را اینجا وارد کنید ==========
TOKEN = "8535755083:AAEG-3mjw_IoCg6T5efZxViT0V_2zH7k5cs"
DATA_FILE = "bot_data.json"
# =====================================================

bot = telebot.TeleBot(TOKEN)

# ---------- پایگاه داده محلی ----------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"admin": None, "groups": []}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"admin": db["admin"], "groups": db["groups"]},
                  f, indent=2, ensure_ascii=False)

db = load_data()
admin_id = db["admin"]
groups_list = db["groups"]

user_states = {}       # وضعیت مکالمه کاربران
active_senders = {}    # ارسال‌کننده‌های فعال
data_lock = threading.Lock()


def get_chat_name(chat_id):
    try:
        chat = bot.get_chat(chat_id)
        return chat.title or f"گپ {chat_id}"
    except:
        return f"گپ {chat_id}"


def notify_admin():
    """وقتی گپ جدید اضافه/حذف میشه به ادمین پیام بده"""
    if not admin_id:
        return
    with data_lock:
        count = len(groups_list)
    if count == 0:
        bot.send_message(admin_id, "ℹ️ هیچ گپی ثبت نشده")
    elif count == 1:
        bot.send_message(admin_id, f"✅ گپ {get_chat_name(groups_list[0])} تایید شد")
    else:
        msg = "✅ گپ‌ها تایید شدن:\n\n"
        for g in groups_list:
            msg += f"📌 {get_chat_name(g)}\n🆔 {g}\n\n"
        bot.send_message(admin_id, msg)


# ==================== دستورات اصلی ====================

@bot.message_handler(commands=["start"])
def start_handler(msg):
    global admin_id, db
    uid = msg.from_user.id
    if admin_id is None:
        with data_lock:
            admin_id = uid
            db["admin"] = uid
            save_data()
        bot.reply_to(msg, "✅ شما به عنوان ادمین ثبت شدید!\n\n"
                          "ربات را به گپ‌ها اضافه کنید.\n"
                          "/groups – لیست گپ‌ها\n"
                          "/leave  – خروج از گپ\n"
                          "/stats  – آمار")
        notify_admin()
    elif uid == admin_id:
        bot.reply_to(msg, "شما ادمین هستید ✅\n\n"
                          "/groups – لیست گپ‌ها\n"
                          "/leave  – خروج از گپ\n"
                          "/stats  – آمار")
    else:
        bot.reply_to(msg, "⛔ ربات قبلاً ادمین دارد.")


@bot.message_handler(commands=["groups"])
def groups_handler(msg):
    if msg.from_user.id != admin_id:
        return
    with data_lock:
        groups = groups_list.copy()
    if not groups:
        bot.reply_to(msg, "ℹ️ هیچ گپی ثبت نشده")
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for g in groups:
        markup.add(types.InlineKeyboardButton(f"📌 {get_chat_name(g)}",
                    callback_data=f"info_{g}"))
    bot.send_message(msg.chat.id, f"📋 لیست گپ‌ها ({len(groups)}):", reply_markup=markup)


@bot.message_handler(commands=["leave"])
def leave_handler(msg):
    if msg.from_user.id != admin_id:
        return
    with data_lock:
        groups = groups_list.copy()
    if not groups:
        bot.reply_to(msg, "ℹ️ هیچ گپی برای خروج نیست")
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for g in groups:
        markup.add(types.InlineKeyboardButton(f"🚪 {get_chat_name(g)}",
                    callback_data=f"leave_{g}"))
    bot.send_message(msg.chat.id, "از کدوم گپ برم بیرون؟", reply_markup=markup)


@bot.message_handler(commands=["stats"])
def stats_handler(msg):
    if msg.from_user.id != admin_id:
        return
    with data_lock:
        groups = groups_list.copy()
    txt = f"📊 آمار ربات:\n\nتعداد گپ‌ها: {len(groups)}"
    if groups:
        txt += "\n\n📌 گپ‌ها:"
        for g in groups:
            txt += f"\n• {get_chat_name(g)}"
    bot.reply_to(msg, txt)


# ================ تشخیص اضافه شدن به گپ ================

@bot.message_handler(content_types=["new_chat_members"])
def on_new_members(msg):
    me = bot.get_me()
    for m in msg.new_chat_members:
        if m.id == me.id:
            cid = msg.chat.id
            with data_lock:
                global groups_list, db
                if cid not in groups_list:
                    groups_list.append(cid)
                    db["groups"] = groups_list
                    save_data()
            notify_admin()
            break


@bot.my_chat_member_handler()
def on_my_chat_member(upd):
    chat = upd.chat
    if chat.type not in ("group", "supergroup"):
        return
    cid = chat.id
    st = upd.new_chat_member.status
    if st in ("member", "administrator"):
        with data_lock:
            global groups_list, db
            if cid not in groups_list:
                groups_list.append(cid)
                db["groups"] = groups_list
                save_data()
        notify_admin()
    elif st in ("left", "kicked"):
        with data_lock:
            if cid in groups_list:
                groups_list.remove(cid)
                db["groups"] = groups_list
                save_data()
        if admin_id:
            bot.send_message(admin_id, f"⛔ ربات از {get_chat_name(cid)} خارج شد")


# ================= سیستم ارسال خودکار =================

@bot.message_handler(func=lambda m: m.from_user.id == admin_id and m.chat.id == admin_id,
                     content_types=["text", "photo", "video", "sticker",
                                    "animation", "document", "audio", "voice"])
def content_handler(msg):
    uid = msg.from_user.id

    # ----- مرحله دریافت تعداد -----
    if uid in user_states:
        st = user_states[uid]
        if st["step"] == "count":
            try:
                c = int(msg.text)
                if not 1 <= c <= 10000:
                    raise ValueError
            except:
                bot.reply_to(msg, "❌ عددی بین 1 تا 10000 وارد کنید")
                return
            st["count"] = c
            st["step"] = "interval"
            bot.reply_to(msg, "⏱ ثانیه رو وارد کنید (مثلاً 3):")
            return

        # ----- مرحله دریافت فاصله زمانی -----
        if st["step"] == "interval":
            try:
                interval = float(msg.text)
                if interval < 0.5:
                    interval = 0.5
            except:
                bot.reply_to(msg, "❌ یک عدد معتبر وارد کنید (مثل 3)")
                return
            st["interval"] = interval
            st["step"] = "done"

            txt = (f"📤 تأیید نهایی:\n📎 نوع: {st['content']['type']}\n"
                   f"📍 گپ: {get_chat_name(st['target'])}\n"
                   f"🔢 تعداد: {st['count']}\n"
                   f"⏱ فاصله: {interval} ثانیه\n\n"
                   "آیا ارسال بشه؟")
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("✅ ارسال شود",
                        callback_data="confirm_send"),
                       types.InlineKeyboardButton("❌ لغو",
                        callback_data="cancel_send"))
            bot.reply_to(msg, txt, reply_markup=markup)
            return

    # ----- شروع فرآیند: ذخیره محتوای دریافتی -----
    content = {"type": "text"}
    if msg.photo:
        content["type"] = "photo"
        content["file_id"] = msg.photo[-1].file_id
    elif msg.video:
        content["type"] = "video"
        content["file_id"] = msg.video.file_id
    elif msg.sticker:
        content["type"] = "sticker"
        content["file_id"] = msg.sticker.file_id
    elif msg.animation:
        content["type"] = "animation"
        content["file_id"] = msg.animation.file_id
    elif msg.document:
        content["type"] = "document"
        content["file_id"] = msg.document.file_id
    elif msg.audio:
        content["type"] = "audio"
        content["file_id"] = msg.audio.file_id
    elif msg.voice:
        content["type"] = "voice"
        content["file_id"] = msg.voice.file_id
    elif msg.text:
        content["type"] = "text"
        content["text"] = msg.text

    user_states[uid] = {"step": "wait_group", "content": content}

    with data_lock:
        groups = groups_list.copy()
    if not groups:
        bot.reply_to(msg, "ℹ️ هیچ گپی ثبت نشده. اول ربات رو اضافه کنید.")
        del user_states[uid]
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for g in groups:
        markup.add(types.InlineKeyboardButton(f"📌 {get_chat_name(g)}",
                    callback_data=f"target_{g}"))
    markup.add(types.InlineKeyboardButton("❌ لغو", callback_data="cancel_send"))
    bot.reply_to(msg, "📍 محتوای ارسالی رو تایید کنید.\nبه کدوم گپ ارسال بشه؟",
                 reply_markup=markup)


# ==================== Callback‌ها ====================

@bot.callback_query_handler(func=lambda c: True)
def callback_worker(call):
    uid = call.from_user.id
    if uid != admin_id:
        bot.answer_callback_query(call.id, "⛔ دسترسی ندارید", show_alert=True)
        return

    data = call.data

    # اطلاعات گپ
    if data.startswith("info_"):
        gid = int(data[5:])
        try:
            chat = bot.get_chat(gid)
            info = f"📌 {chat.title or 'بدون نام'}\n🆔 {gid}"
            try:
                info += f"\n👥 {bot.get_chat_member_count(gid)} عضو"
            except:
                pass
            bot.send_message(uid, info)
        except:
            bot.send_message(uid, f"🆔 {gid}")
        bot.answer_callback_query(call.id)

    # خروج از گپ
    elif data.startswith("leave_"):
        gid = int(data[6:])
        try:
            bot.leave_chat(gid)
            with data_lock:
                if gid in groups_list:
                    groups_list.remove(gid)
                    db["groups"] = groups_list
                    save_data()
            bot.send_message(uid, "✅ با موفقیت خارج شدم")
        except Exception as e:
            bot.send_message(uid, f"❌ خطا: {e}")
        bot.answer_callback_query(call.id)

    # انتخاب گپ هدف
    elif data.startswith("target_"):
        gid = int(data[7:])
        if uid in user_states:
            user_states[uid]["target"] = gid
            user_states[uid]["step"] = "count"
            bot.edit_message_text("🔢 تعداد ارسال رو وارد کنید:\nمثال: 100",
                                  uid, call.message.message_id)
        bot.answer_callback_query(call.id)

    # تأیید و شروع ارسال
    elif data == "confirm_send":
        if uid not in user_states:
            bot.answer_callback_query(call.id, "❌ اطلاعات یافت نشد", show_alert=True)
            return
        st = user_states[uid]
        target = st["target"]
        count = st["count"]
        interval = st["interval"]
        content = st["content"]

        bot.edit_message_text("⏳ در حال ارسال...", uid, call.message.message_id)
        bot.answer_callback_query(call.id)

        task_id = f"{uid}_{int(time.time())}"
        ctrl = {"stop": False}
        active_senders[task_id] = ctrl

        def sender():
            for i in range(count):
                if ctrl["stop"]:
                    break
                try:
                    ct = content["type"]
                    fid = content.get("file_id")
                    if ct == "text":
                        bot.send_message(target, content["text"])
                    elif ct == "photo":
                        bot.send_photo(target, fid)
                    elif ct == "video":
                        bot.send_video(target, fid)
                    elif ct == "sticker":
                        bot.send_sticker(target, fid)
                    elif ct == "animation":
                        bot.send_animation(target, fid)
                    elif ct == "document":
                        bot.send_document(target, fid)
                    elif ct == "audio":
                        bot.send_audio(target, fid)
                    elif ct == "voice":
                        bot.send_voice(target, fid)
                except Exception as e:
                    bot.send_message(uid, f"⚠️ خطا در پیام {i+1}: {e}")
                    break
                if (i + 1) % 10 == 0 or i == count - 1:
                    try:
                        bot.edit_message_text(f"⏳ ارسال: {i+1}/{count}",
                                              uid, call.message.message_id)
                    except:
                        pass
                if i < count - 1:
                    time.sleep(interval)
            try:
                bot.edit_message_text(f"✅ ارسال کامل شد ({count} پیام)",
                                      uid, call.message.message_id)
            except:
                bot.send_message(uid, f"✅ ارسال کامل شد ({count} پیام)")
            if task_id in active_senders:
                del active_senders[task_id]

        threading.Thread(target=sender, daemon=True).start()

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⏹ توقف",
                    callback_data=f"stop_{task_id}"))
        bot.edit_message_text(f"⏳ ارسال: 0/{count}", uid,
                              call.message.message_id, reply_markup=markup)
        del user_states[uid]

    # توقف ارسال
    elif data.startswith("stop_"):
        tid = data[5:]
        if tid in active_senders:
            active_senders[tid]["stop"] = True
            bot.edit_message_text("⏹ ارسال متوقف شد", uid, call.message.message_id)
        bot.answer_callback_query(call.id)

    # لغو
    elif data == "cancel_send":
        if uid in user_states:
            del user_states[uid]
        try:
            bot.edit_message_text("❌ لغو شد", uid, call.message.message_id)
        except:
            pass
        bot.answer_callback_query(call.id)


# ==================== اجرا ====================
if __name__ == "__main__":
    print("🤖 ربات در حال اجراست...")
    bot.infinity_polling()
