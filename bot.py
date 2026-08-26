# -*- coding: utf-8 -*-
"""
ربات تلگرام مدیریت گپ‌ها ── مسابقه بیشترین پیام ── چند ادمینه ── بخش ۱/۲
قابل اجرا در Pydroid 3
"""

import telebot
from telebot import types
import json
import os
import time
import threading

# ====================== تنظیمات ======================
TOKEN = "8535755083:AAEG-3mjw_IoCg6T5efZxViT0V_2zH7k5cs"
DATA_FILE = "bot_data.json"
SUPER_ADMIN = 7530457395
# =====================================================

bot = telebot.TeleBot(TOKEN)

# ---------- دیتابیس ----------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "admin_usernames": [],
        "admin_ids": [],
        "groups": []
    }

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

db = load_data()

if SUPER_ADMIN not in db["admin_ids"]:
    db["admin_ids"].append(SUPER_ADMIN)
    save_data()

user_states = {}
active_senders = {}
data_lock = threading.Lock()


# ================ بررسی مجدد گپ‌ها ====================

def refresh_groups_from_updates():
    added = 0
    try:
        updates = bot.get_updates(allowed_updates=["my_chat_member"])
        for upd in updates:
            if upd.my_chat_member:
                chat = upd.my_chat_member.chat
                if chat.type in ("group", "supergroup"):
                    status = upd.my_chat_member.new_chat_member.status
                    if status in ("member", "administrator"):
                        with data_lock:
                            if chat.id not in db["groups"]:
                                db["groups"].append(chat.id)
                                added += 1
        if added > 0:
            save_data()
    except Exception as e:
        print(f"⚠️ خطا در refresh: {e}")
    return added


def refresh_groups_by_test():
    removed = 0
    with data_lock:
        gids = db["groups"].copy()
    for gid in gids:
        try:
            bot.get_chat(gid)
        except Exception as e:
            if "chat not found" in str(e).lower() or "bot was kicked" in str(e).lower() or "bot is not a member" in str(e).lower():
                with data_lock:
                    if gid in db["groups"]:
                        db["groups"].remove(gid)
                        removed += 1
    if removed > 0:
        save_data()
    return removed


print("🔄 بررسی گپ‌های عضو...")
added_count = refresh_groups_from_updates()
print(f"✅ {added_count} گپ جدید از آپدیت‌های قدیمی پیدا شد.")

# ======================================================


def is_admin(user_id):
    if user_id == SUPER_ADMIN:
        return True
    with data_lock:
        return user_id in db["admin_ids"]

def get_all_admin_ids():
    with data_lock:
        admins = set(db["admin_ids"])
    admins.add(SUPER_ADMIN)
    return list(admins)


def get_chat_name(chat_id):
    try:
        chat = bot.get_chat(chat_id)
        return chat.title or f"گپ {chat_id}"
    except:
        return f"گپ {chat_id}"


def notify_admins(text):
    for aid in get_all_admin_ids():
        try:
            bot.send_message(aid, text)
        except:
            pass


def notify_admin_about_groups():
    with data_lock:
        count = len(db["groups"])
    if count == 0:
        notify_admins("ℹ️ هیچ گپی ثبت نشده")
    elif count == 1:
        g = db["groups"][0]
        notify_admins(f"✅ گپ {get_chat_name(g)} تایید شد")
    else:
        msg = "✅ گپ‌ها تایید شدن:\n\n"
        for g in db["groups"]:
            msg += f"📌 {get_chat_name(g)}\n🆔 {g}\n\n"
        notify_admins(msg)


# ================== دستورات عمومی ادمین ===================

@bot.message_handler(commands=["start"])
def start_handler(msg):
    uid = msg.from_user.id
    username = msg.from_user.username

    if username and uid != SUPER_ADMIN:
        with data_lock:
            normalized = username.lower()
            ulist_lower = [u.lower() for u in db["admin_usernames"]]
            if normalized in ulist_lower and uid not in db["admin_ids"]:
                db["admin_ids"].append(uid)
                save_data()
                bot.reply_to(msg, "✅ شما به عنوان ادمین ثبت شدید!\n\n"
                                  "همه دسترسی‌های ارسال را دارید.\n"
                                  "/admins – لیست ادمین‌ها")
                notify_admins(f"✅ ادمین جدید: @{username}")
                return

    if not is_admin(uid):
        bot.reply_to(msg, "⛔ دسترسی ندارید")
        return

    txt = ("🎯 پنل مدیریت ربات\n\n"
           "📌 دستورات:\n"
           "/admins – لیست ادمین‌ها\n"
           "/addadmin @username – افزودن ادمین\n"
           "/removeadmin @username – حذف ادمین\n"
           "/groups – لیست گپ‌ها\n"
           "/leave – خروج از گپ\n"
           "/refresh – بروزرسانی گپ‌ها\n"
           "/stats – آمار\n\n"
           "💬 برای ارسال خودکار، هر نوع محتوایی بفرستید.")
    bot.reply_to(msg, txt)


@bot.message_handler(commands=["refresh"])
def refresh_handler(msg):
    if not is_admin(msg.from_user.id):
        return

    m = bot.reply_to(msg, "🔄 در حال بررسی گپ‌ها...")
    added = refresh_groups_from_updates()
    removed = refresh_groups_by_test()

    with data_lock:
        total = len(db["groups"])

    txt = (f"✅ بروزرسانی انجام شد:\n"
           f"📌 گپ جدید: {added}\n"
           f"🗑 گپ حذف‌شده: {removed}\n"
           f"🏷 مجموع: {total}")

    try:
        bot.edit_message_text(txt, msg.chat.id, m.message_id)
    except:
        bot.reply_to(msg, txt)


@bot.message_handler(commands=["admins"])
def admins_list_handler(msg):
    if not is_admin(msg.from_user.id):
        return

    txt = "👥 لیست ادمین‌ها:\n\n"

    try:
        s = bot.get_chat(SUPER_ADMIN)
        sname = f"@{s.username}" if s.username else s.first_name
    except:
        sname = str(SUPER_ADMIN)
    txt += f"⭐ {sname} (مالک)\n🆔 {SUPER_ADMIN}\n\n"

    with data_lock:
        for uid in db["admin_ids"]:
            if uid == SUPER_ADMIN:
                continue
            try:
                c = bot.get_chat(uid)
                uname = f"@{c.username}" if c.username else c.first_name
            except:
                uname = str(uid)
            txt += f"👤 {uname}\n🆔 {uid}\n\n"

    with data_lock:
        pending = []
        for u in db["admin_usernames"]:
            found = False
            for aid in db["admin_ids"]:
                try:
                    c = bot.get_chat(aid)
                    if c.username and c.username.lower() == u.lower():
                        found = True
                        break
                except:
                    pass
            if not found:
                pending.append(u)

    if pending:
        txt += "⏳ در انتظار ثبت‌نام:\n"
        for u in pending:
            txt += f"• @{u}\n"

    bot.reply_to(msg, txt)


@bot.message_handler(commands=["addadmin"])
def add_admin_handler(msg):
    uid = msg.from_user.id
    if uid != SUPER_ADMIN:
        bot.reply_to(msg, "⛔ فقط مالک ربات می‌تواند ادمین اضافه کند")
        return

    parts = msg.text.split()
    if len(parts) < 2:
        bot.reply_to(msg, "❌ روش استفاده:\n/addadmin @username")
        return

    target_uname = parts[1].strip().lstrip("@")
    if not target_uname:
        bot.reply_to(msg, "❌ یوزرنیم نامعتبر")
        return

    with data_lock:
        normalized = target_uname.lower()
        current = [u.lower() for u in db["admin_usernames"]]
        if normalized in current:
            bot.reply_to(msg, "ℹ️ این یوزرنیم قبلاً اضافه شده")
            return
        db["admin_usernames"].append(target_uname)
        save_data()

    bot.reply_to(msg, f"✅ @{target_uname} به لیست ادمین‌ها اضافه شد.\n"
                      "پس از اینکه `/start` بزنه، دسترسی کامل پیدا می‌کنه.")


@bot.message_handler(commands=["removeadmin"])
def remove_admin_handler(msg):
    uid = msg.from_user.id
    if uid != SUPER_ADMIN:
        bot.reply_to(msg, "⛔ فقط مالک ربات می‌تواند ادمین حذف کند")
        return

    parts = msg.text.split()
    if len(parts) < 2:
        bot.reply_to(msg, "❌ روش استفاده:\n/removeadmin @username")
        return

    target_uname = parts[1].strip().lstrip("@")
    if not target_uname:
        bot.reply_to(msg, "❌ یوزرنیم نامعتبر")
        return

    normalized = target_uname.lower()
    removed_userid = None

    with data_lock:
        db["admin_usernames"] = [u for u in db["admin_usernames"]
                                 if u.lower() != normalized]

        for aid in db["admin_ids"][:]:
            try:
                c = bot.get_chat(aid)
                if c.username and c.username.lower() == normalized:
                    db["admin_ids"].remove(aid)
                    removed_userid = aid
                    break
            except:
                pass

        save_data()

    if removed_userid:
        bot.reply_to(msg, f"✅ @{target_uname} از ادمین‌ها حذف شد.")
    else:
        bot.reply_to(msg, f"✅ @{target_uname} از لیست انتظار حذف شد (هنوز ثبت‌نام نکرده بود).")


@bot.message_handler(commands=["groups"])
def groups_handler(msg):
    if not is_admin(msg.from_user.id):
        return
    with data_lock:
        groups = db["groups"].copy()
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
    if not is_admin(msg.from_user.id):
        return
    with data_lock:
        groups = db["groups"].copy()
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
    if not is_admin(msg.from_user.id):
        return
    with data_lock:
        groups = db["groups"].copy()
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
                if cid not in db["groups"]:
                    db["groups"].append(cid)
                    save_data()
            notify_admin_about_groups()
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
            if cid not in db["groups"]:
                db["groups"].append(cid)
                save_data()
        notify_admin_about_groups()
    elif st in ("left", "kicked"):
        with data_lock:
            if cid in db["groups"]:
                db["groups"].remove(cid)
                save_data()
        notify_admins(f"⛔ ربات از {get_chat_name(cid)} خارج شد")


# ================= سیستم ارسال خودکار =================

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and m.chat.id == m.from_user.id,
                     content_types=["text", "photo", "video", "sticker",
                                    "animation", "document", "audio", "voice"])
def content_handler(msg):
    uid = msg.from_user.id

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
        groups = db["groups"].copy()
    if not groups:
        bot.reply_to(msg, "ℹ️ هیچ گپی ثبت نشده. اول ربات رو اضافه کنید.\n"
                          "اگر ربات قبلاً توی گپ هست، /refresh رو بزنید.")
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
    if not is_admin(uid):
        bot.answer_callback_query(call.id, "⛔ دسترسی ندارید", show_alert=True)
        return

    data = call.data

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

    elif data.startswith("leave_"):
        gid = int(data[6:])
        try:
            bot.leave_chat(gid)
            with data_lock:
                if gid in db["groups"]:
                    db["groups"].remove(gid)
                    save_data()
            bot.send_message(uid, "✅ با موفقیت خارج شدم")
        except Exception as e:
            bot.send_message(uid, f"❌ خطا: {e}")
        bot.answer_callback_query(call.id)

    elif data.startswith("target_"):
        gid = int(data[7:])
        if uid in user_states:
            user_states[uid]["target"] = gid
            user_states[uid]["step"] = "count"
            bot.edit_message_text("🔢 تعداد ارسال رو وارد کنید:\nمثال: 100",
                                  uid, call.message.message_id)
        bot.answer_callback_query(call.id)

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

    elif data.startswith("stop_"):
        tid = data[5:]
        if tid in active_senders:
            active_senders[tid]["stop"] = True
            bot.edit_message_text("⏹ ارسال متوقف شد", uid, call.message.message_id)
        bot.answer_callback_query(call.id)

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
