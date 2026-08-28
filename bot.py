# -*- coding: utf-8 -*-
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
import sqlite3
import time
import re
import random
from collections import defaultdict, deque

BOT_TOKEN = "8617545814:AAFAofo_nV39gFT1-IgfXu-esnGgXol62r4"
MAIN_OWNER_ID = 7530457395
DEFAULT_WELCOME = "سلام {mention} عزیز به گپ {group}\nخوش اومدی"

bot = telebot.TeleBot(BOT_TOKEN)
user_steps = {}
flood_map = defaultdict(lambda: deque())

def db():
    return sqlite3.connect("group_bot.db", check_same_thread=False, timeout=30)

def init_db():
    con = db()
    c = con.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS groups(
        chat_id INTEGER PRIMARY KEY,
        title TEXT,
        welcome_text TEXT,
        welcome_enabled INTEGER DEFAULT 1,
        lock_link INTEGER DEFAULT 0,
        lock_forward INTEGER DEFAULT 0,
        lock_spam INTEGER DEFAULT 1,
        warn_limit INTEGER DEFAULT 3
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS bot_admins(
        chat_id INTEGER, user_id INTEGER,
        PRIMARY KEY(chat_id, user_id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS nicknames(
        chat_id INTEGER, user_id INTEGER, nick TEXT,
        PRIMARY KEY(chat_id, user_id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS warns(
        chat_id INTEGER, user_id INTEGER, count INTEGER DEFAULT 0,
        PRIMARY KEY(chat_id, user_id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS mutes(
        chat_id INTEGER, user_id INTEGER, until_ts INTEGER,
        PRIMARY KEY(chat_id, user_id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS message_stats(
        chat_id INTEGER, user_id INTEGER, count INTEGER DEFAULT 0,
        PRIMARY KEY(chat_id, user_id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS autoreplies(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER, keyword TEXT, answer TEXT,
        exact_match INTEGER DEFAULT 1, active INTEGER DEFAULT 1
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS welcome_photos(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT UNIQUE
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS started_users(
        user_id INTEGER PRIMARY KEY
    )""")
    con.commit()
    con.close()

init_db()

def ensure_group(chat):
    if not chat or chat.type not in ("group", "supergroup"):
        return
    con = db()
    c = con.cursor()
    c.execute("INSERT OR IGNORE INTO groups(chat_id,title,welcome_text) VALUES(?,?,?)",
              (chat.id, chat.title or "", DEFAULT_WELCOME))
    c.execute("UPDATE groups SET title=? WHERE chat_id=?", (chat.title or "", chat.id))
    c.execute("INSERT OR IGNORE INTO bot_admins(chat_id,user_id) VALUES(?,?)",
              (chat.id, MAIN_OWNER_ID))
    try:
        for a in bot.get_chat_administrators(chat.id):
            if a.user.is_bot:
                continue
            c.execute("INSERT OR IGNORE INTO bot_admins(chat_id,user_id) VALUES(?,?)",
                      (chat.id, a.user.id))
    except Exception:
        pass
    con.commit()
    con.close()

def is_owner(uid):
    return int(uid) == int(MAIN_OWNER_ID)

def is_admin(chat_id, uid):
    if is_owner(uid):
        return True
    try:
        st = bot.get_chat_member(chat_id, uid).status
        if st in ("creator", "administrator"):
            con = db()
            c = con.cursor()
            c.execute("INSERT OR IGNORE INTO bot_admins(chat_id,user_id) VALUES(?,?)",
                      (chat_id, uid))
            con.commit()
            con.close()
            return True
    except Exception:
        pass
    con = db()
    c = con.cursor()
    c.execute("SELECT 1 FROM bot_admins WHERE chat_id=? AND user_id=?", (chat_id, uid))
    ok = c.fetchone() is not None
    con.close()
    return ok

def grow(chat_id):
    con = db()
    c = con.cursor()
    c.execute("SELECT * FROM groups WHERE chat_id=?", (chat_id,))
    r = c.fetchone()
    con.close()
    return r

def setf(chat_id, field, value):
    con = db()
    c = con.cursor()
    c.execute("UPDATE groups SET {}=? WHERE chat_id=?".format(field), (value, chat_id))
    con.commit()
    con.close()

def fmt_welcome(tpl, user, chat):
    name = user.first_name or "کاربر"
    un = "@"+user.username if user.username else "ندارد"
    mention = '<a href="tg://user?id={}">{}</a>'.format(user.id, name)
    t = tpl or DEFAULT_WELCOME
    return (t.replace("{name}", name).replace("{username}", un)
             .replace("{id}", str(user.id)).replace("{group}", chat.title or "گپ")
             .replace("{mention}", mention))

def mute(chat_id, user_id, sec):
    sec = max(1, int(sec))
    until = int(time.time()) + sec
    bot.restrict_chat_member(
        chat_id, user_id,
        permissions=ChatPermissions(
            can_send_messages=False, can_send_media_messages=False,
            can_send_other_messages=False, can_add_web_page_previews=False
        ),
        until_date=until
    )
    con = db()
    c = con.cursor()
    c.execute("INSERT OR REPLACE INTO mutes(chat_id,user_id,until_ts) VALUES(?,?,?)",
              (chat_id, user_id, until))
    con.commit()
    con.close()

def unmute(chat_id, user_id):
    bot.restrict_chat_member(
        chat_id, user_id,
        permissions=ChatPermissions(
            can_send_messages=True, can_send_media_messages=True,
            can_send_other_messages=True, can_add_web_page_previews=True,
            can_send_polls=True, can_invite_users=True
        )
    )
    con = db()
    c = con.cursor()
    c.execute("DELETE FROM mutes WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    con.commit()
    con.close()

def target_user(msg):
    if msg.reply_to_message and msg.reply_to_message.from_user:
        return msg.reply_to_message.from_user
    return None

def delmsg(chat_id, mid):
    try:
        bot.delete_message(chat_id, mid)
    except Exception:
        pass

def panel_kb(chat_id):
    g = grow(chat_id)
    def m(v):
        return "✅" if v else "❌"
    kb = InlineKeyboardMarkup(row_width=2)
    if not g:
        return kb
    # g: 0id 1title 2wtext 3wen 4link 5fwd 6spam 7warn
    kb.add(
        InlineKeyboardButton("لینک "+m(g[4]), callback_data="p_link"),
        InlineKeyboardButton("فوروارد "+m(g[5]), callback_data="p_fwd")
    )
    kb.add(
        InlineKeyboardButton("ضدسپم "+m(g[6]), callback_data="p_spam"),
        InlineKeyboardButton("خوش‌آمد "+m(g[3]), callback_data="p_wel")
    )
    kb.add(InlineKeyboardButton("📝 متن خوش‌آمد", callback_data="p_weltext"))
    kb.add(InlineKeyboardButton("🤖 پاسخ خودکار", callback_data="p_auto"))
    kb.add(InlineKeyboardButton("📖 راهنما", callback_data="p_help"))
    kb.add(InlineKeyboardButton("❌ بستن", callback_data="p_close"))
    return kb

def owner_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📤 آپلود عکس خوش‌آمد", callback_data="o_upload"))
    kb.add(InlineKeyboardButton("🖼 عکس‌ها / پاک کردن", callback_data="o_photos"))
    kb.add(InlineKeyboardButton("📢 تبلیغ گپ‌ها", callback_data="o_bcg"))
    kb.add(InlineKeyboardButton("📢 تبلیغ کاربران", callback_data="o_bcu"))
    return kb

print("part1 ok")
@bot.message_handler(content_types=["new_chat_members"])
def on_join(message):
    try:
        ensure_group(message.chat)
        chat_id = message.chat.id
        me = bot.get_me()
        for u in message.new_chat_members:
            if u.id == me.id:
                ensure_group(message.chat)
                bot.send_message(chat_id, "✅ ربات فعال شد\nبنویس: پنل")
                continue
            g = grow(chat_id)
            if not g or not g[3]:
                continue
            cap = fmt_welcome(g[2], u, message.chat)
            con = db()
            c = con.cursor()
            c.execute("SELECT file_id FROM welcome_photos")
            photos = [r[0] for r in c.fetchall()]
            con.close()
            try:
                if photos:
                    bot.send_photo(chat_id, random.choice(photos), caption=cap, parse_mode="HTML")
                else:
                    bot.send_message(chat_id, cap, parse_mode="HTML")
            except Exception:
                bot.send_message(chat_id, cap, parse_mode="HTML")
    except Exception as e:
        print("join", e)

def inc_stat(chat_id, uid):
    con = db()
    c = con.cursor()
    c.execute("INSERT OR IGNORE INTO message_stats(chat_id,user_id,count) VALUES(?,?,0)", (chat_id, uid))
    c.execute("UPDATE message_stats SET count=count+1 WHERE chat_id=? AND user_id=?", (chat_id, uid))
    con.commit()
    con.close()

def add_warn(chat_id, uid):
    con = db()
    c = con.cursor()
    c.execute("INSERT OR IGNORE INTO warns(chat_id,user_id,count) VALUES(?,?,0)", (chat_id, uid))
    c.execute("UPDATE warns SET count=count+1 WHERE chat_id=? AND user_id=?", (chat_id, uid))
    c.execute("SELECT count FROM warns WHERE chat_id=? AND user_id=?", (chat_id, uid))
    n = c.fetchone()[0]
    con.commit()
    con.close()
    return n

def maybe_auto(message):
    if not message.text:
        return
    con = db()
    c = con.cursor()
    c.execute("SELECT keyword,answer,exact_match FROM autoreplies WHERE chat_id=? AND active=1",
              (message.chat.id,))
    rows = c.fetchall()
    con.close()
    t = message.text.strip()
    for kw, ans, exact in rows:
        if exact and t == kw:
            bot.reply_to(message, ans)
            return
        if not exact and kw in t:
            bot.reply_to(message, ans)
            return

def filters(message):
    chat_id = message.chat.id
    uid = message.from_user.id
    if is_admin(chat_id, uid):
        maybe_auto(message)
        return
    g = grow(chat_id)
    if not g:
        return
    text = message.text or message.caption or ""
    if g[6]:
        key = (chat_id, uid)
        now = time.time()
        q = flood_map[key]
        q.append(now)
        while q and now - q[0] > 10:
            q.popleft()
        if len(q) >= 25:
            delmsg(chat_id, message.message_id)
            try:
                mute(chat_id, uid, 120)
            except Exception:
                pass
            return
    if g[4] and text and re.search(r"(https?://|www\.|t\.me/)", text, re.I):
        delmsg(chat_id, message.message_id)
        return
    if g[5] and (message.forward_date or message.forward_from or message.forward_from_chat):
        delmsg(chat_id, message.message_id)
        return
    maybe_auto(message)

@bot.message_handler(func=lambda m: m.chat.type in ("group", "supergroup"),
                     content_types=["text","photo","video","voice","document","sticker","animation","audio","video_note"])
def on_group(message):
    try:
        ensure_group(message.chat)
        chat_id = message.chat.id
        uid = message.from_user.id
        text = (message.text or "").strip()
        if not message.from_user.is_bot:
            inc_stat(chat_id, uid)

        st = user_steps.get(uid, {})
        if st.get("step") == "wel_text" and st.get("chat_id") == chat_id:
            if is_admin(chat_id, uid):
                setf(chat_id, "welcome_text", text)
                user_steps.pop(uid, None)
                bot.reply_to(message, "✅ متن خوش‌آمد ذخیره شد")
            return

        if not text:
            filters(message)
            return

        if text in ("پنل", "پنل مدیریت"):
            if not is_admin(chat_id, uid):
                bot.reply_to(message, "فقط ادمین")
                return
            bot.reply_to(message, "🛡 پنل مدیریت", reply_markup=panel_kb(chat_id))
            return

        if text == "آمار کل":
            con = db()
            c = con.cursor()
            c.execute("SELECT user_id,count FROM message_stats WHERE chat_id=? ORDER BY count DESC LIMIT 15",
                      (chat_id,))
            rows = c.fetchall()
            con.close()
            if not rows:
                bot.reply_to(message, "آماری نیست")
                return
            lines = ["📊 آمار کل\n"]
            for i,(u,cnt) in enumerate(rows,1):
                con = db()
                c = con.cursor()
                c.execute("SELECT nick FROM nicknames WHERE chat_id=? AND user_id=?", (chat_id,u))
                n = c.fetchone()
                con.close()
                label = n[0] if n else str(u)
                lines.append("{}. {} — {}".format(i, label, cnt))
            bot.reply_to(message, "\n".join(lines))
            return

        if not is_admin(chat_id, uid):
            filters(message)
            return

        if text.startswith("سکوت"):
            t = target_user(message)
            if not t:
                bot.reply_to(message, "ریپلای کن")
                return
            parts = text.split()
            sec = 60
            if len(parts) >= 2 and parts[1].isdigit():
                sec = int(parts[1])
            try:
                mute(chat_id, t.id, sec)
                bot.reply_to(message, "🔇 سکوت {} ثانیه".format(sec))
            except Exception as e:
                bot.reply_to(message, "خطا دسترسی: {}".format(e))
            return

        if text == "حذف سکوت":
            t = target_user(message)
            if not t:
                bot.reply_to(message, "ریپلای کن")
                return
            try:
                unmute(chat_id, t.id)
                bot.reply_to(message, "✅ حذف سکوت")
            except Exception as e:
                bot.reply_to(message, str(e))
            return

        if text == "بن":
            t = target_user(message)
            if not t:
                bot.reply_to(message, "ریپلای کن")
                return
            try:
                bot.ban_chat_member(chat_id, t.id)
                bot.reply_to(message, "🚫 بن شد")
            except Exception as e:
                bot.reply_to(message, str(e))
            return

        if text == "حذف بن":
            t = target_user(message)
            if not t:
                bot.reply_to(message, "ریپلای کن")
                return
            try:
                bot.unban_chat_member(chat_id, t.id, only_if_banned=True)
                bot.reply_to(message, "✅ حذف بن")
            except Exception as e:
                bot.reply_to(message, str(e))
            return

        if text == "اخطار":
            t = target_user(message)
            if not t:
                bot.reply_to(message, "ریپلای کن")
                return
            n = add_warn(chat_id, t.id)
            g = grow(chat_id)
            lim = g[7] if g else 3
            bot.reply_to(message, "⚠️ اخطار {}/{}".format(n, lim))
            if n >= lim:
                try:
                    mute(chat_id, t.id, 600)
                    bot.reply_to(message, "سقف اخطار — ۱۰ دقیقه سکوت")
                except Exception:
                    pass
            return

        if text == "حذف اخطار":
            t = target_user(message)
            if not t:
                bot.reply_to(message, "ریپلای کن")
                return
            con = db()
            c = con.cursor()
            c.execute("DELETE FROM warns WHERE chat_id=? AND user_id=?", (chat_id, t.id))
            con.commit()
            con.close()
            bot.reply_to(message, "✅ حذف اخطار")
            return

        if text == "پاکسازی لیست اخطار":
            con = db()
            c = con.cursor()
            c.execute("DELETE FROM warns WHERE chat_id=?", (chat_id,))
            con.commit()
            con.close()
            bot.reply_to(message, "✅ لیست اخطار پاک شد")
            return

        if text == "پاکسازی لیست سکوت":
            con = db()
            c = con.cursor()
            c.execute("SELECT user_id FROM mutes WHERE chat_id=?", (chat_id,))
            rows = c.fetchall()
            c.execute("DELETE FROM mutes WHERE chat_id=?", (chat_id,))
            con.commit()
            con.close()
            for (u,) in rows:
                try:
                    unmute(chat_id, u)
                except Exception:
                    pass
            bot.reply_to(message, "✅ لیست سکوت پاک شد")
            return

        if text == "پاکسازی لیست بن":
            bot.reply_to(message, "API تلگرام لیست بن کامل نمی‌دهد. تکی حذف بن کن.")
            return

        if text == "تنظیم ادمین":
            t = target_user(message)
            if not t:
                bot.reply_to(message, "ریپلای کن")
                return
            con = db()
            c = con.cursor()
            c.execute("INSERT OR IGNORE INTO bot_admins(chat_id,user_id) VALUES(?,?)", (chat_id, t.id))
            con.commit()
            con.close()
            bot.reply_to(message, "✅ ادمین ربات شد")
            return

        if text.startswith("تنظیم لقب"):
            t = target_user(message)
            if not t:
                bot.reply_to(message, "ریپلای کن")
                return
            parts = text.split(maxsplit=2)
            if len(parts) < 3:
                bot.reply_to(message, "مثال: تنظیم لقب گرگ")
                return
            nick = parts[2].strip()
            con = db()
            c = con.cursor()
            c.execute("INSERT OR REPLACE INTO nicknames(chat_id,user_id,nick) VALUES(?,?,?)",
                      (chat_id, t.id, nick))
            con.commit()
            con.close()
            bot.reply_to(message, "✅ لقب: "+nick)
            return

        if text == "حذف":
            if message.reply_to_message:
                delmsg(chat_id, message.reply_to_message.message_id)
                delmsg(chat_id, message.message_id)
            return

        if text.startswith("حذف "):
            parts = text.split()
            if len(parts)==2 and parts[1].isdigit():
                n = min(int(parts[1]), 100)
                mid = message.message_id
                delmsg(chat_id, mid)
                d = 0
                for i in range(1, n+1):
                    try:
                        bot.delete_message(chat_id, mid-i)
                        d += 1
                    except Exception:
                        pass
                bot.send_message(chat_id, "🗑 {} پیام حذف شد".format(d))
                return

        filters(message)
    except Exception as e:
        print("group", e)

print("part2 ok")
@bot.callback_query_handler(func=lambda call: True)
def cb(call):
    try:
        uid = call.from_user.id
        data = call.data or ""
        chat = call.message.chat
        chat_id = chat.id

        # همیشه اول جواب بده تا دکمه گیر نکند
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

        # ----- پنل گپ (آیدی از خود پیام گپ) -----
        if data.startswith("p_"):
            if chat.type not in ("group", "supergroup"):
                bot.send_message(uid, "این دکمه فقط داخل گپ کار می‌کند")
                return
            if not is_admin(chat_id, uid):
                bot.send_message(chat_id, "دسترسی نداری")
                return

            g = grow(chat_id)
            if not g:
                bot.send_message(chat_id, "گپ ثبت نشده. یک پیام بفرست و دوباره پنل بزن")
                return

            if data == "p_link":
                setf(chat_id, "lock_link", 0 if g[4] else 1)
                bot.send_message(chat_id, "لینک: "+("خاموش" if g[4] else "روشن"))
            elif data == "p_fwd":
                setf(chat_id, "lock_forward", 0 if g[5] else 1)
                bot.send_message(chat_id, "فوروارد: "+("خاموش" if g[5] else "روشن"))
            elif data == "p_spam":
                setf(chat_id, "lock_spam", 0 if g[6] else 1)
                bot.send_message(chat_id, "ضدسپم: "+("خاموش" if g[6] else "روشن"))
            elif data == "p_wel":
                setf(chat_id, "welcome_enabled", 0 if g[3] else 1)
                bot.send_message(chat_id, "خوش‌آمد: "+("خاموش" if g[3] else "روشن"))
            elif data == "p_weltext":
                user_steps[uid] = {"step": "wel_text", "chat_id": chat_id}
                bot.send_message(chat_id, "متن خوش‌آمد را بفرست\n{name} {username} {id} {group} {mention}")
                return
            elif data == "p_auto":
                code = "AUTO-{}".format(chat_id)
                bot.send_message(chat_id, "کد را کپی کن و در پیوی ربات بفرست:\n\n`{}`".format(code),
                                 parse_mode="Markdown")
                return
            elif data == "p_help":
                bot.send_message(chat_id,
                    "دستورات با ریپلای:\n"
                    "سکوت 30 | حذف سکوت\nبن | حذف بن\n"
                    "اخطار | حذف اخطار\n"
                    "پاکسازی لیست اخطار | پاکسازی لیست سکوت\n"
                    "تنظیم ادمین | تنظیم لقب گرگ\n"
                    "حذف | حذف 50\nآمار کل | پنل")
                return
            elif data == "p_close":
                delmsg(chat_id, call.message.message_id)
                return

            # رفرش پنل
            try:
                bot.edit_message_reply_markup(chat_id, call.message.message_id,
                                              reply_markup=panel_kb(chat_id))
            except Exception:
                bot.send_message(chat_id, "پنل:", reply_markup=panel_kb(chat_id))
            return

        # ----- پنل پیوی ادمین اصلی -----
        if data.startswith("o_"):
            if not is_owner(uid):
                bot.send_message(uid, "فقط ادمین اصلی")
                return
            if data == "o_upload":
                user_steps[uid] = {"step": "upload_photo"}
                bot.send_message(uid, "عکس بفرست. پایان: /done")
            elif data == "o_photos":
                con = db()
                c = con.cursor()
                c.execute("SELECT COUNT(*) FROM welcome_photos")
                n = c.fetchone()[0]
                con.close()
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("پاک کردن همه عکس‌ها", callback_data="o_clear"))
                bot.send_message(uid, "تعداد عکس: {}".format(n), reply_markup=kb)
            elif data == "o_clear":
                con = db()
                c = con.cursor()
                c.execute("DELETE FROM welcome_photos")
                con.commit()
                con.close()
                bot.send_message(uid, "✅ همه عکس‌ها پاک شد")
            elif data == "o_bcg":
                user_steps[uid] = {"step": "bc_groups"}
                bot.send_message(uid, "محتوای تبلیغ برای گپ‌ها را بفرست")
            elif data == "o_bcu":
                user_steps[uid] = {"step": "bc_users"}
                bot.send_message(uid, "محتوای تبلیغ برای کاربران را بفرست")
            return

        if data in ("auto_exact", "auto_include"):
            d = user_steps.get(uid, {})
            if d.get("step") != "auto_mode":
                return
            exact = 1 if data == "auto_exact" else 0
            con = db()
            c = con.cursor()
            c.execute("INSERT INTO autoreplies(chat_id,keyword,answer,exact_match,active) VALUES(?,?,?,?,1)",
                      (d["chat_id"], d["keyword"], d["answer"], exact))
            con.commit()
            con.close()
            user_steps.pop(uid, None)
            bot.send_message(uid, "✅ پاسخ خودکار ذخیره شد")
            return
    except Exception as e:
        print("cb", e)
        try:
            bot.answer_callback_query(call.id, "خطا")
        except Exception:
            pass

print("part3 ok")
@bot.message_handler(commands=["start"])
def start(message):
    if message.chat.type != "private":
        return
    uid = message.from_user.id
    con = db()
    c = con.cursor()
    c.execute("INSERT OR IGNORE INTO started_users(user_id) VALUES(?)", (uid,))
    con.commit()
    con.close()
    if is_owner(uid):
        bot.reply_to(message, "👑 پنل ادمین اصلی\nدکمه‌ها را بزن:", reply_markup=owner_kb())
    else:
        bot.reply_to(message, "ربات را ادمین گپ کن و بنویس: پنل\nکد AUTO-... را هم اینجا بفرست.")

@bot.message_handler(commands=["done"])
def done(message):
    if message.chat.type != "private":
        return
    uid = message.from_user.id
    if user_steps.get(uid, {}).get("step") == "upload_photo":
        user_steps.pop(uid, None)
        bot.reply_to(message, "✅ آپلود تمام")

@bot.message_handler(func=lambda m: m.chat.type == "private",
                     content_types=["text","photo","video","animation","document","voice","sticker"])
def on_pv(message):
    uid = message.from_user.id
    text = (message.text or "").strip()
    st = user_steps.get(uid, {})
    step = st.get("step")

    if text.startswith("AUTO-"):
        try:
            cid = int(text.replace("AUTO-", "").strip())
        except Exception:
            bot.reply_to(message, "کد نامعتبر")
            return
        if not (is_admin(cid, uid) or is_owner(uid)):
            bot.reply_to(message, "دسترسی نداری")
            return
        user_steps[uid] = {"step": "auto_key", "chat_id": cid}
        bot.reply_to(message, "کلمه کلیدی:")
        return

    if step == "auto_key":
        user_steps[uid] = {"step": "auto_ans", "chat_id": st["chat_id"], "keyword": text}
        bot.reply_to(message, "متن جواب:")
        return

    if step == "auto_ans":
        user_steps[uid] = {
            "step": "auto_mode",
            "chat_id": st["chat_id"],
            "keyword": st["keyword"],
            "answer": text
        }
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("فقط دقیقاً همان", callback_data="auto_exact"))
        kb.add(InlineKeyboardButton("هر جا در متن", callback_data="auto_include"))
        bot.reply_to(message, "حالت:", reply_markup=kb)
        return

    if step == "upload_photo" and is_owner(uid):
        if message.photo:
            fid = message.photo[-1].file_id
            con = db()
            c = con.cursor()
            c.execute("INSERT OR IGNORE INTO welcome_photos(file_id) VALUES(?)", (fid,))
            con.commit()
            c.execute("SELECT COUNT(*) FROM welcome_photos")
            n = c.fetchone()[0]
            con.close()
            bot.reply_to(message, "✅ ذخیره | کل {}\n/done".format(n))
        else:
            bot.reply_to(message, "فقط عکس یا /done")
        return

    if step in ("bc_groups", "bc_users") and is_owner(uid):
        con = db()
        c = con.cursor()
        if step == "bc_groups":
            c.execute("SELECT chat_id FROM groups")
        else:
            c.execute("SELECT user_id FROM started_users")
        targets = [r[0] for r in c.fetchall()]
        con.close()
        ok = 0
        for t in targets:
            try:
                bot.copy_message(t, message.chat.id, message.message_id)
                ok += 1
                time.sleep(0.05)
            except Exception:
                pass
        user_steps.pop(uid, None)
        bot.reply_to(message, "✅ به {} نفر/گپ ارسال شد".format(ok))
        return

    if is_owner(uid) and not step:
        bot.reply_to(message, "منو:", reply_markup=owner_kb())

print("Bot started")
bot.infinity_polling(none_stop=True, timeout=60, long_polling_timeout=50)
