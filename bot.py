# -*- coding: utf-8 -*-
"""
ربات کارت کلکسیون - نسخه کامل تمام بخش‌ها
"""
import logging, json, os, random, string, re
from datetime import date, datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, filters, ChatMemberHandler,
)
from telegram.constants import ChatMemberStatus, ChatType

BOT_TOKEN = "8273833935:AAFKVpl4Atb_ldgciIJfqtvFUlixvz2l1S4"
MAIN_ADMIN = 7530457395
DATA = "card_data.json"
DAILY = 100

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger("cardbot")

# ---------- storage ----------
def D():
    return {
        "admins": [MAIN_ADMIN],
        "pool": [],
        "shop": [],
        "users": {},
        "groups": {},
        "rarities": [
            {"name": "معمولی", "emoji": "⚪", "weight": 40, "max_per_day_group": 10},
            {"name": "لجند", "emoji": "🌟", "weight": 25, "max_per_day_group": 5},
            {"name": "اپیک", "emoji": "⚡", "weight": 15, "max_per_day_group": 3},
            {"name": "اولتیمت", "emoji": "🔥", "weight": 10, "max_per_day_group": 2},
            {"name": "افسانه‌ای", "emoji": "👑", "weight": 5, "max_per_day_group": 1},
            {"name": "فوق‌کمیاب", "emoji": "💎", "weight": 2, "max_per_day_group": 1},
        ],
        "titles": [],
        "collections": [],
        "transfer_cmds": ["انتقال کارت", "/c", "/sh", "شیر کارت"],
        "profile_tpl": "👤 {name} ({tag})\n🏷 {title}\n📊 سطح {level}\n💰 {points}\n🃏 {cards}\n📦 کالکشن {collections}\n🏆 {best_card}\n📊 {rarity_summary}",
        "start_msg": "🎴 ربات کارت\nپروفایلم | /help | /top\nتو گپ: ریپلای + کارت",
        "msg_threshold": 560,
        "sell_mult": 2.0,
        "games": {},
    }

def load():
    if os.path.exists(DATA):
        try:
            with open(DATA, "r", encoding="utf-8") as f:
                d = json.load(f)
            b = D()
            for k, v in b.items():
                d.setdefault(k, v)
            return d
        except Exception as e:
            log.error(e)
    return D()

def save(d):
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def adm(uid, d=None):
    d = d or load()
    return uid == MAIN_ADMIN or uid in d.get("admins", [])

def code(n=6):
    return "c" + "".join(random.choices(string.ascii_lowercase + string.digits, k=n))

def eu(d, user):
    uid = str(user.id)
    if uid not in d["users"]:
        d["users"][uid] = {
            "name": user.full_name, "username": user.username or "",
            "cards": [], "profile_code": None, "points": 0, "level": 1,
            "title": "-", "last_daily": None, "collections_done": [],
        }
    else:
        d["users"][uid]["name"] = user.full_name
        d["users"][uid]["username"] = user.username or ""
    return d["users"][uid]

def ri(d, name):
    for r in d.get("rarities", []):
        if r["name"] == name:
            return r
    return {"name": name, "emoji": "✨", "weight": 10, "max_per_day_group": 5}

def level_of(u):
    cards = u.get("cards", [])
    pts = u.get("points", 0)
    rare = sum(max(1, c.get("points", 1) // 5) for c in cards)
    return max(1, min(1 + (pts // 50 + len(cards) + rare // 3) // 10, 999))

def title_of(d, pts):
    t = "-"
    for x in sorted(d.get("titles", []), key=lambda i: i.get("min_points", 0)):
        if pts >= x.get("min_points", 0):
            t = x["name"]
    return t

def upd(d, uid):
    u = d["users"].get(uid)
    if not u:
        return
    u["level"] = level_of(u)
    u["title"] = title_of(d, u.get("points", 0))

def best(u):
    if not u.get("cards"):
        return "-"
    c = max(u["cards"], key=lambda x: x.get("points", 0))
    return f"{c.get('name')} ({c.get('code')})"

def rsum(u):
    c = {}
    for x in u.get("cards", []):
        c[x.get("rarity", "?")] = c.get(x.get("rarity", "?"), 0) + 1
    return " | ".join(f"{k}:{v}" for k, v in c.items()) or "-"

def profile(d, uid):
    u = d["users"].get(uid)
    if not u:
        return "نیست"
    tag = f"@{u['username']}" if u.get("username") else u.get("name", "-")
    tpl = d.get("profile_tpl") or D()["profile_tpl"]
    try:
        return tpl.format(
            name=u.get("name", "-"), tag=tag, title=u.get("title", "-"),
            level=u.get("level", 1), points=u.get("points", 0),
            cards=len(u.get("cards", [])), collections=len(u.get("collections_done", [])),
            best_card=best(u), rarity_summary=rsum(u),
            profile_code=u.get("profile_code") or "-",
        )
    except Exception:
        return f"{u.get('name')} | L{u.get('level')} | {u.get('points')}p | {len(u.get('cards',[]))}c"

def pkb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 لیست کارت‌هام", callback_data="myc")],
        [InlineKeyboardButton("🖼 تنظیم پروفایل", callback_data="setp")],
        [InlineKeyboardButton("🛒 فروشگاه", callback_data="shop")],
        [InlineKeyboardButton("📦 کالکشن", callback_data="cols")],
        [InlineKeyboardButton("🎮 بازی کارتی", callback_data="game")],
        [InlineKeyboardButton("🔄 تعویض کارت", callback_data="exch")],
    ])

def akb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 آپلود کارت", callback_data="a_up")],
        [InlineKeyboardButton("🏷 سطوح کمیابی", callback_data="a_rar")],
        [InlineKeyboardButton("📛 لقب‌ها", callback_data="a_tit")],
        [InlineKeyboardButton("🛒 فروشگاه", callback_data="a_shop")],
        [InlineKeyboardButton("📦 کالکشن", callback_data="a_col")],
        [InlineKeyboardButton("🔗 دستور انتقال", callback_data="a_tr")],
        [InlineKeyboardButton("⚙️ تنظیمات", callback_data="a_set")],
        [InlineKeyboardButton("👤 ادمین", callback_data="a_adm")],
        [InlineKeyboardButton("📊 آمار", callback_data="a_st")],
    ])

# ---------- commands ----------
async def cmd_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    user = u.effective_user
    d = load()
    eu(d, user)
    uid = str(user.id)
    today = str(date.today())
    note = ""
    if d["users"][uid].get("last_daily") != today:
        d["users"][uid]["points"] = d["users"][uid].get("points", 0) + DAILY
        d["users"][uid]["last_daily"] = today
        upd(d, uid)
        note = f"\n\n🎁 +{DAILY} امتیاز روزانه"
    save(d)
    kb = akb() if adm(user.id, d) and u.effective_chat.type == ChatType.PRIVATE else pkb()
    await u.message.reply_text(d.get("start_msg", "سلام") + note, reply_markup=kb)

async def cmd_help(u: Update, c: ContextTypes.DEFAULT_TYPE):
    t = (
        "📖 <b>راهنما</b>\n"
        "• ریپلای کارت + <b>کارت</b>\n"
        "• <code>پروفایلم</code> | ریپلای + <code>پروفایل کارتی</code>\n"
        "• <code>جستجو کد</code>\n"
        "• <code>کالکشن</code>\n"
        "• انتقال: <code>انتقال کارت کد</code> + ریپلای\n"
        "• <code>/top</code> برترین‌ها\n"
        "• فروشگاه / بازی / تعویض از دکمه‌ها\n"
        "• روزانه ۱۰۰ امتیاز با /start"
    )
    await u.message.reply_text(t, parse_mode="HTML", reply_markup=pkb())

async def cmd_top(u: Update, c: ContextTypes.DEFAULT_TYPE):
    d = load()
    us = sorted(d["users"].items(), key=lambda x: x[1].get("points", 0), reverse=True)
    lines = ["🏆 <b>۱۰ برتر</b>\n"]
    for i, (_, x) in enumerate(us[:10], 1):
        tg = f"@{x['username']}" if x.get("username") else x.get("name")
        lines.append(f"{i}. {tg} — {x.get('points',0)} | L{x.get('level',1)}")
    cards = []
    for _, x in d["users"].items():
        for c0 in x.get("cards", []):
            cards.append((c0, x))
    cards.sort(key=lambda z: z[0].get("points", 0), reverse=True)
    lines.append("\n💎 کمیاب‌ترین")
    for c0, o in cards[:5]:
        tg = f"@{o['username']}" if o.get("username") else o.get("name")
        lines.append(f"• {c0.get('name')} ({c0.get('code')}) {c0.get('points')} | {tg}")
    await u.message.reply_text("\n".join(lines), parse_mode="HTML")

async def cmd_admin(u: Update, c: ContextTypes.DEFAULT_TYPE):
    d = load()
    if not adm(u.effective_user.id, d):
        return
    if u.effective_chat.type != ChatType.PRIVATE:
        await u.message.reply_text("فقط پیوی")
        return
    await u.message.reply_text("🔐 ادمین", reply_markup=akb())

# ---------- join group ----------
async def on_join(u: Update, c: ContextTypes.DEFAULT_TYPE):
    r = u.my_chat_member
    ch = r.chat
    if ch.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    if r.new_chat_member.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR):
        d = load()
        cid = str(ch.id)
        d["groups"].setdefault(cid, {
            "title": ch.title or "", "msg_count": 0,
            "active_msg_id": None, "pending": None,
            "daily_rare": {}, "last_dist": {},
        })
        save(d)
        try:
            await c.bot.send_message(ch.id,
                "🎴 ربات کارت فعال شد\nریپلای + <b>کارت</b>\nپروفایلم | /help | /top | کالکشن",
                parse_mode="HTML")
        except Exception:
            pass

# ---------- distribute ----------
async def on_gmsg(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not u.message or u.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    if u.message.text and u.message.text.startswith("/"):
        return
    d = load()
    cid = str(u.effective_chat.id)
    g = d["groups"].setdefault(cid, {
        "title": u.effective_chat.title or "", "msg_count": 0,
        "active_msg_id": None, "pending": None, "daily_rare": {}, "last_dist": {},
    })
    g["msg_count"] = g.get("msg_count", 0) + 1
    th = d.get("msg_threshold", 560)
    if g["msg_count"] >= th:
        g["msg_count"] = 0
        save(d)
        await dist(c, u.effective_chat.id, d)
    else:
        save(d)

async def dist(c, chat_id, d=None):
    d = d or load()
    cid = str(chat_id)
    g = d["groups"].setdefault(cid, {"msg_count": 0, "daily_rare": {}, "last_dist": {}})
    today = str(date.today())
    # filter by remain + daily rarity limit
    avail = []
    for card in d["pool"]:
        if card.get("remain_dist", 1) <= 0:
            continue
        rar = card.get("rarity", "معمولی")
        info = ri(d, rar)
        key = f"{today}:{rar}"
        used = g.get("daily_rare", {}).get(key, 0)
        if used >= info.get("max_per_day_group", 5):
            continue
        # avoid same card too soon in same group
        last = g.get("last_dist", {}).get(card["code"])
        if last:
            try:
                if (datetime.now() - datetime.fromisoformat(last)).total_seconds() < 3600:
                    continue
            except Exception:
                pass
        avail.append(card)
    if not avail:
        return
    w = [max(1, ri(d, x.get("rarity", "")).get("weight", 10)) for x in avail]
    card = random.choices(avail, weights=w, k=1)[0]
    card["remain_dist"] = card.get("remain_dist", 1) - 1
    rar = card.get("rarity", "")
    key = f"{today}:{rar}"
    g.setdefault("daily_rare", {})[key] = g.get("daily_rare", {}).get(key, 0) + 1
    g.setdefault("last_dist", {})[card["code"]] = datetime.now().isoformat()
    if card["remain_dist"] <= 0:
        d["pool"] = [x for x in d["pool"] if x["code"] != card["code"]]
    em = ri(d, rar).get("emoji", "✨")
    cap = (
        f"{em} <b>{card.get('name')}</b>\n{card.get('description','')}\n\n"
        f"🏷 {rar}\n⭐ {card.get('points',0)}\n🆔 <code>{card['code']}</code>\n"
        f"📤 باقی توزیع کل: {card.get('remain_dist',0)}\n\nریپلای + <b>کارت</b>"
    )
    try:
        msg = await c.bot.send_photo(chat_id, photo=card["file_id"], caption=cap, parse_mode="HTML")
        g["active_msg_id"] = msg.message_id
        g["pending"] = card
        save(d)
    except Exception as e:
        log.error(e)
        card["remain_dist"] = card.get("remain_dist", 0) + 1
        if card.get("remain_dist", 0) > 0 and not any(x["code"] == card["code"] for x in d["pool"]):
            d["pool"].append(card)
        save(d)

async def claim(u, c, d):
    user = u.effective_user
    ch = u.effective_chat
    rp = u.message.reply_to_message
    cid = str(ch.id)
    g = d["groups"].get(cid)
    if not g or not g.get("pending") or rp.message_id != g.get("active_msg_id"):
        return
    card = g["pending"]
    g["pending"] = None
    g["active_msg_id"] = None
    uid = str(user.id)
    eu(d, user)
    x = d["users"][uid]
    old = x.get("points", 0)
    x["cards"].append({
        "code": card["code"], "file_id": card["file_id"], "name": card.get("name"),
        "description": card.get("description", ""), "rarity": card.get("rarity"),
        "points": card.get("points", 0), "emoji": card.get("emoji", ""),
        "collection": card.get("collection"),
    })
    gain = int(card.get("points", 0))
    x["points"] = old + gain
    upd(d, uid)
    # collection check
    await check_collections(c, d, uid, user)
    save(d)
    tag = f"@{user.username}" if user.username else user.full_name
    nc = f"✅ {tag}\n{card.get('name')} | +{gain} ({old}→{x['points']}) | L{x.get('level')}"
    try:
        await c.bot.edit_message_caption(ch.id, rp.message_id, caption=nc)
    except Exception:
        await u.message.reply_text(nc)
    await u.message.reply_text(f"🎉 {tag} گرفت!")

async def check_collections(c, d, uid, user):
    u = d["users"][uid]
    codes = {x["code"] for x in u.get("cards", [])}
    names = {x.get("name") for x in u.get("cards", [])}
    for col in d.get("collections", []):
        if col.get("id") in u.get("collections_done", []):
            continue
        need = set(col.get("card_codes", []))
        if need and need.issubset(codes):
            u.setdefault("collections_done", []).append(col["id"])
            prize = col.get("prize")
            if prize:
                u["cards"].append(dict(prize, code=code()))
                u["points"] = u.get("points", 0) + int(prize.get("points", 0))
            upd(d, uid)
            tag = f"@{user.username}" if user.username else user.full_name
            txt = col.get("done_text") or f"🏆 کالکشن {col.get('name')} کامل شد توسط {tag}"
            for gid in col.get("groups", []) or list(d.get("groups", {}).keys()):
                try:
                    await c.bot.send_message(int(gid), txt)
                except Exception:
                    pass

# ---------- text ----------
async def on_text(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not u.message or not u.message.text:
        return
    user = u.effective_user
    ch = u.effective_chat
    text = u.message.text.strip()
    d = load()
    eu(d, user)
    uid = str(user.id)
    st = c.user_data.get("st")

    if text == "کارت" and u.message.reply_to_message and ch.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        await claim(u, c, d)
        return

    if text in ("پروفایلم", "پروفایل من"):
        upd(d, uid); save(d)
        txt = profile(d, uid)
        ph = None
        uu = d["users"][uid]
        if uu.get("profile_code"):
            for cd in uu["cards"]:
                if cd["code"] == uu["profile_code"]:
                    ph = cd["file_id"]; break
        if ph:
            await u.message.reply_photo(ph, caption=txt, reply_markup=pkb())
        else:
            await u.message.reply_text(txt, reply_markup=pkb())
        return

    if text in ("پروفایل کارتی", "پروفایل کارت") and u.message.reply_to_message:
        t = u.message.reply_to_message.from_user
        if not t:
            return
        eu(d, t); upd(d, str(t.id)); save(d)
        txt = profile(d, str(t.id))
        uu = d["users"][str(t.id)]
        ph = None
        if uu.get("profile_code"):
            for cd in uu["cards"]:
                if cd["code"] == uu["profile_code"]:
                    ph = cd["file_id"]; break
        if ph:
            await u.message.reply_photo(ph, caption=txt, reply_markup=pkb())
        else:
            await u.message.reply_text(txt, reply_markup=pkb())
        return

    if text == "کالکشن":
        await show_collections(u, d, uid)
        return

    if text.startswith("جستجو "):
        await search(u, d, text.split(" ", 1)[1].strip().lstrip("`"))
        return

    if text.startswith("کارت های ") or text.startswith("کارت‌های "):
        rar = text.split(" ", 2)[-1].strip()
        await rarity_panel(u, c, d, rar)
        return

    if text in ("کمیاب ترین کارت ها", "کمیاب‌ترین کارت‌ها"):
        await cmd_top(u, c)
        return

    for cmd in d.get("transfer_cmds", []):
        if text.lower().startswith(cmd.lower()):
            rest = text[len(cmd):].strip()
            cd0 = rest.split()[0].lstrip("`") if rest else ""
            if not cd0 or not u.message.reply_to_message:
                await u.message.reply_text(f"{cmd} کد + ریپلای گیرنده")
                return
            tg = u.message.reply_to_message.from_user
            if not tg or tg.id == user.id or tg.is_bot:
                await u.message.reply_text("گیرنده نامعتبر")
                return
            card = next((x for x in d["users"][uid].get("cards", []) if x["code"] == cd0), None)
            if not card:
                await u.message.reply_text("مال تو نیست")
                return
            c.user_data["tr"] = {"code": cd0, "from": uid, "to": str(tg.id), "to_name": tg.full_name}
            await u.message.reply_text(
                f"انتقال {card.get('name')} به {tg.full_name}؟",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅", callback_data="tr_y"),
                    InlineKeyboardButton("❌", callback_data="tr_n"),
                ]]),
            )
            return

    # states
    if st == "setp":
        cd0 = text.lstrip("`")
        uu = d["users"][uid]
        fnd = next((x for x in uu["cards"] if x["code"] == cd0), None)
        if not fnd:
            await u.message.reply_text("نیست")
        else:
            uu["profile_code"] = cd0
            save(d)
            await u.message.reply_photo(fnd["file_id"], caption=f"✅ <code>{cd0}</code>", parse_mode="HTML", reply_markup=pkb())
        c.user_data.pop("st", None)
        return

    if st == "sell":
        await do_sell(u, c, d, text)
        return

    if st == "exch_codes":
        # چند کد با فاصله
        codes = text.replace(",", " ").split()
        await do_exchange(u, c, d, codes)
        return

    if st and st.startswith("game_"):
        await game_text(u, c, d, text)
        return

    if adm(user.id, d) and ch.type == ChatType.PRIVATE:
        await admin_text(u, c, d, text)

async def search(u, d, cd0):
    for _, ou in d["users"].items():
        for x in ou.get("cards", []):
            if x["code"] == cd0:
                tg = f"@{ou['username']}" if ou.get("username") else ou.get("name")
                await u.message.reply_photo(
                    x["file_id"],
                    caption=f"🃏 <b>{x.get('name')}</b>\n{x.get('description','')}\n{x.get('rarity')} | {x.get('points')}\n<code>{x['code']}</code>\nOwner {tg}",
                    parse_mode="HTML",
                )
                return
    for x in d.get("pool", []):
        if x["code"] == cd0:
            await u.message.reply_photo(x["file_id"], caption=f"آزاد\n<code>{x['code']}</code>", parse_mode="HTML")
            return
    await u.message.reply_text("نبود")

async def show_collections(u, d, uid):
    cols = d.get("collections", [])
    if not cols:
        await u.message.reply_text("کالکشنی نیست")
        return
    uu = d["users"].get(uid, {})
    have = {x["code"] for x in uu.get("cards", [])}
    for col in cols:
        need = col.get("card_codes", [])
        done = sum(1 for x in need if x in have)
        total = len(need) or 1
        cap = f"📦 <b>{col.get('name')}</b>\n{col.get('desc','')}\nپیشرفت: {done}/{total}\n{col.get('reward_text','')}"
        if col.get("preview"):
            try:
                await u.message.reply_photo(col["preview"], caption=cap, parse_mode="HTML")
                continue
            except Exception:
                pass
        await u.message.reply_text(cap, parse_mode="HTML")

async def rarity_panel(u, c, d, rar):
    # کارت‌های کاربر با این rarity — در گپ پنل ساده
    user = u.effective_user
    uu = d["users"].get(str(user.id), {})
    cards = [x for x in uu.get("cards", []) if x.get("rarity") == rar]
    if not cards:
        await u.message.reply_text(f"کارتی از نوع {rar} نداری")
        return
    c.user_data["browse"] = {"list": cards, "i": 0}
    await send_browse(u.message.chat_id, c, d, cards, 0)

async def send_browse(chat_id, c, d, cards, i, edit_msg=None):
    if not cards:
        return
    i = max(0, min(i, len(cards) - 1))
    card = cards[i]
    cap = f"{i+1}/{len(cards)}\n{card.get('emoji','')} <b>{card.get('name')}</b>\n{card.get('description','')}\n{card.get('rarity')} | {card.get('points')}\n<code>{card['code']}</code>"
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️", callback_data="br_l"),
        InlineKeyboardButton("➡️", callback_data="br_r"),
    ]])
    if edit_msg:
        try:
            await edit_msg.edit_media
        except Exception:
            pass
        try:
            await c.bot.edit_message_caption(chat_id, edit_msg.message_id, caption=cap, parse_mode="HTML", reply_markup=kb)
            return
        except Exception:
            pass
    try:
        await c.bot.send_photo(chat_id, photo=card["file_id"], caption=cap, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await c.bot.send_message(chat_id, cap, parse_mode="HTML", reply_markup=kb)

async def do_sell(u, c, d, q):
    user = u.effective_user
    uid = str(user.id)
    uu = d["users"][uid]
    ql = q.lower()
    ms = [x for x in uu.get("cards", []) if x["code"] == q or ql in x.get("name", "").lower()]
    c.user_data.pop("st", None)
    if not ms:
        await u.message.reply_text("نبود")
        return
    if len(ms) > 1:
        await u.message.reply_text("کد دقیق:\n" + "\n".join(f"{x['name']} <code>{x['code']}</code>" for x in ms[:10]), parse_mode="HTML")
        c.user_data["st"] = "sell"
        return
    card = ms[0]
    gain = int(card.get("points", 0) * d.get("sell_mult", 2.0))
    uu["cards"] = [x for x in uu["cards"] if x["code"] != card["code"]]
    if uu.get("profile_code") == card["code"]:
        uu["profile_code"] = None
    uu["points"] = uu.get("points", 0) + gain
    upd(d, uid); save(d)
    await u.message.reply_text(f"✅ فروش {card.get('name')} +{gain} → {uu['points']}", reply_markup=pkb())

async def do_exchange(u, c, d, codes):
    c.user_data.pop("st", None)
    user = u.effective_user
    uid = str(user.id)
    uu = d["users"][uid]
    if len(codes) < 4:
        await u.message.reply_text("حداقل ۴ کد کارت هم‌سطح بفرست")
        return
    cards = []
    for cd0 in codes[:4]:
        fnd = next((x for x in uu["cards"] if x["code"] == cd0.lstrip("`")), None)
        if not fnd:
            await u.message.reply_text(f"{cd0} مال تو نیست")
            return
        cards.append(fnd)
    rar = cards[0].get("rarity")
    if not all(x.get("rarity") == rar for x in cards):
        await u.message.reply_text("همه باید یک سطح باشند")
        return
    # جایزه از pool کمیاب‌تر
    rar_names = [r["name"] for r in d.get("rarities", [])]
    try:
        idx = rar_names.index(rar)
    except ValueError:
        idx = 0
    better = rar_names[idx + 1:] if idx + 1 < len(rar_names) else []
    prize_pool = [x for x in d["pool"] if x.get("rarity") in better] or [x for x in d["pool"] if x.get("points", 0) > cards[0].get("points", 0)]
    if not prize_pool:
        await u.message.reply_text("جایزه‌ای در استخر نیست")
        return
    prize = random.choice(prize_pool)
    # remove 4 cards
    rm = {x["code"] for x in cards}
    uu["cards"] = [x for x in uu["cards"] if x["code"] not in rm]
    prize["remain_dist"] = prize.get("remain_dist", 1) - 1
    if prize.get("remain_dist", 0) <= 0:
        d["pool"] = [x for x in d["pool"] if x["code"] != prize["code"]]
    uu["cards"].append({
        "code": prize["code"], "file_id": prize["file_id"], "name": prize.get("name"),
        "description": prize.get("description", ""), "rarity": prize.get("rarity"),
        "points": prize.get("points", 0), "emoji": prize.get("emoji", ""),
    })
    uu["points"] = uu.get("points", 0) + int(prize.get("points", 0))
    upd(d, uid); save(d)
    await u.message.reply_photo(prize["file_id"], caption=f"🔄 تعویض شد → {prize.get('name')} ({prize.get('rarity')})", reply_markup=pkb())

# ---------- game ----------
async def game_text(u, c, d, text):
    st = c.user_data.get("st")
    user = u.effective_user
    if st == "game_card":
        gid = c.user_data.get("gid")
        g = d.get("games", {}).get(gid)
        if not g:
            c.user_data.clear()
            return
        # resolve card by code or name
        uid = str(user.id)
        uu = d["users"][uid]
        ql = text.lower()
        ms = [x for x in uu.get("cards", []) if x["code"] == text or ql in x.get("name", "").lower()]
        if not ms:
            await u.message.reply_text("کارت پیدا نشد")
            return
        if len(ms) > 1:
            await u.message.reply_text("کد دقیق:\n" + "\n".join(f"{x['name']} <code>{x['code']}</code>" for x in ms[:8]), parse_mode="HTML")
            return
        card = ms[0]
        g.setdefault("plays", {})[uid] = card
        save(d)
        need = g.get("players", 2)
        if len(g["plays"]) >= need:
            await resolve_game(u, c, d, gid)
        else:
            await u.message.reply_text(f"ثبت شد ({len(g['plays'])}/{need})")
            c.user_data.pop("st", None)
        return

async def resolve_game(u, c, d, gid):
    g = d["games"].get(gid)
    if not g:
        return
    plays = g.get("plays", {})
    # بالاترین امتیاز کارت برنده
    ranked = sorted(plays.items(), key=lambda x: x[1].get("points", 0), reverse=True)
    if len(ranked) < 2:
        return
    win_uid, win_card = ranked[0]
    # امتیاز جایزه = اختلاف
    vals = [p.get("points", 0) for _, p in ranked]
    bonus = max(50, abs(vals[0] - (sum(vals[1:]) // max(1, len(vals) - 1))))
    d["users"][win_uid]["points"] = d["users"][win_uid].get("points", 0) + bonus
    # کارت بازنده‌ها به برنده نمی‌رود مگر تنظیم — امتیاز می‌دهیم
    upd(d, win_uid)
    save(d)
    w = d["users"][win_uid]
    tag = f"@{w['username']}" if w.get("username") else w.get("name")
    txt = f"🎮 برنده: {tag}\nکارت: {win_card.get('name')} ({win_card.get('points')})\n+{bonus} امتیاز"
    try:
        await c.bot.send_message(g.get("chat_id") or u.effective_chat.id, txt)
    except Exception:
        await u.message.reply_text(txt)
    d["games"].pop(gid, None)
    save(d)
    c.user_data.clear()

# ---------- admin text ----------
async def admin_text(u, c, d, text):
    st = c.user_data.get("st")
    if st == "up_name":
        c.user_data.setdefault("up", {})["name"] = text
        c.user_data["st"] = "up_desc"
        await u.message.reply_text("توضیحات:")
        return
    if st == "up_desc":
        c.user_data["up"]["description"] = text
        c.user_data["st"] = "up_rar"
        rows = [[InlineKeyboardButton(f"{r.get('emoji','')} {r['name']}", callback_data=f"ur_{r['name']}")] for r in d["rarities"]]
        await u.message.reply_text("سطح:", reply_markup=InlineKeyboardMarkup(rows + [[InlineKeyboardButton("❌", callback_data="ac")]]))
        return
    if st == "up_pts":
        try:
            c.user_data["up"]["points"] = int(text)
        except ValueError:
            await u.message.reply_text("عدد")
            return
        c.user_data["st"] = "up_dist"
        await u.message.reply_text("تعداد توزیع:")
        return
    if st == "up_dist":
        try:
            dist = int(text)
        except ValueError:
            await u.message.reply_text("عدد")
            return
        up = c.user_data.get("up", {})
        cd0 = code()
        card = {
            "code": cd0, "file_id": up["file_id"], "name": up.get("name"),
            "description": up.get("description", ""), "rarity": up.get("rarity", "معمولی"),
            "emoji": up.get("emoji", ""), "points": up.get("points", 0),
            "remain_dist": dist, "max_dist": dist, "collection": up.get("collection"),
        }
        d["pool"].append(card)
        save(d)
        c.user_data.clear()
        await u.message.reply_text(f"✅ {card['name']}\n<code>{cd0}</code>\n{card['rarity']} | {card['points']} | ×{dist}", parse_mode="HTML", reply_markup=akb())
        return
    if st == "add_rar":
        p = [x.strip() for x in text.split("|")]
        d["rarities"].append({
            "name": p[0], "emoji": p[1] if len(p) > 1 else "✨",
            "weight": int(p[2]) if len(p) > 2 and p[2].isdigit() else 5,
            "max_per_day_group": int(p[3]) if len(p) > 3 and p[3].isdigit() else 2,
        })
        save(d); c.user_data.clear()
        await u.message.reply_text("✅ سطح", reply_markup=akb())
        return
    if st == "bulk_tit":
        n = 0
        for line in text.splitlines():
            line = line.strip().lstrip("•").lstrip("-").strip()
            m = re.search(r"(.+?)\s*\(از\s*(\d+)\s*امتیاز\)", line) or re.search(r"(.+?)\s+(\d+)\s*$", line)
            if m:
                d["titles"].append({"name": m.group(1).strip(), "min_points": int(m.group(2))})
                n += 1
        d["titles"].sort(key=lambda t: t["min_points"])
        save(d); c.user_data.clear()
        await u.message.reply_text(f"✅ {n} لقب", reply_markup=akb())
        return
    if st == "tpl":
        d["profile_tpl"] = text; save(d); c.user_data.clear()
        await u.message.reply_text("✅ قالب", reply_markup=akb()); return
    if st == "smsg":
        d["start_msg"] = text; save(d); c.user_data.clear()
        await u.message.reply_text("✅ استارت", reply_markup=akb()); return
    if st == "th":
        try:
            d["msg_threshold"] = max(10, int(text)); save(d); c.user_data.clear()
            await u.message.reply_text(f"✅ هر {d['msg_threshold']}", reply_markup=akb())
        except ValueError:
            await u.message.reply_text("عدد")
        return
    if st == "add_adm":
        try:
            a = int(text)
            if a not in d["admins"]:
                d["admins"].append(a)
            save(d); c.user_data.clear()
            await u.message.reply_text(f"✅ {a}", reply_markup=akb())
        except ValueError:
            await u.message.reply_text("آیدی")
        return
    if st == "tr_add":
        if text not in d["transfer_cmds"]:
            d["transfer_cmds"].append(text)
        save(d); c.user_data.clear()
        await u.message.reply_text(f"✅ دستور `{text}`", reply_markup=akb())
        return
    if st == "shop_name":
        c.user_data["si"] = {"name": text}; c.user_data["st"] = "shop_desc"
        await u.message.reply_text("توضیح:"); return
    if st == "shop_desc":
        c.user_data["si"]["description"] = text; c.user_data["st"] = "shop_price"
        await u.message.reply_text("قیمت:"); return
    if st == "shop_price":
        try:
            c.user_data["si"]["price"] = int(text)
        except ValueError:
            await u.message.reply_text("عدد"); return
        c.user_data["st"] = "shop_stock"; await u.message.reply_text("موجودی:"); return
    if st == "shop_stock":
        try:
            c.user_data["si"]["stock"] = int(text)
        except ValueError:
            await u.message.reply_text("عدد"); return
        c.user_data["st"] = "shop_ph"; await u.message.reply_text("عکس:"); return
    if st == "col_name":
        c.user_data["col"] = {"id": code(4), "name": text, "card_codes": [], "groups": []}
        c.user_data["st"] = "col_desc"; await u.message.reply_text("توضیح کالکشن:"); return
    if st == "col_desc":
        c.user_data["col"]["desc"] = text; c.user_data["st"] = "col_codes"
        await u.message.reply_text("کد کارت‌های عضو را با فاصله بفرست:"); return
    if st == "col_codes":
        c.user_data["col"]["card_codes"] = [x.lstrip("`") for x in text.split()]
        c.user_data["st"] = "col_reward"; await u.message.reply_text("متن جایزه/اعلام:"); return
    if st == "col_reward":
        c.user_data["col"]["reward_text"] = text; c.user_data["st"] = "col_prize_code"
        await u.message.reply_text("کد کارت جایزه از استخر (یا -):"); return
    if st == "col_prize_code":
        col = c.user_data["col"]
        if text.strip() != "-":
            pr = next((x for x in d["pool"] if x["code"] == text.strip()), None)
            if pr:
                col["prize"] = dict(pr)
                d["pool"] = [x for x in d["pool"] if x["code"] != pr["code"]]
        c.user_data["st"] = "col_preview"; await u.message.reply_text("عکس پیش‌نمایش کالکشن:"); return

async def on_photo(u: Update, c: ContextTypes.DEFAULT_TYPE):
    user = u.effective_user
    d = load()
    if not adm(user.id, d) or u.effective_chat.type != ChatType.PRIVATE:
        return
    st = c.user_data.get("st")
    fid = u.message.photo[-1].file_id
    if st == "up_ph":
        c.user_data["up"] = {"file_id": fid}; c.user_data["st"] = "up_name"
        await u.message.reply_text("اسم کارت:"); return
    if st == "shop_ph":
        si = c.user_data.get("si", {})
        si["file_id"] = fid; si["code"] = code(); si["rarity"] = "فروشگاهی"
        si["points"] = si.get("price", 0) // 2
        d["shop"].append(si); save(d); c.user_data.clear()
        await u.message.reply_text(f"✅ فروشگاه {si['name']}", reply_markup=akb()); return
    if st == "col_preview":
        col = c.user_data.get("col", {})
        col["preview"] = fid
        d["collections"].append(col)
        save(d); c.user_data.clear()
        # announce
        txt = f"📦 کالکشن جدید: {col.get('name')}\n{col.get('desc','')}\n{col.get('reward_text','')}"
        for gid in list(d.get("groups", {}).keys())[:20]:
            try:
                await c.bot.send_photo(int(gid), photo=fid, caption=txt)
            except Exception:
                try:
                    await c.bot.send_message(int(gid), txt)
                except Exception:
                    pass
        await u.message.reply_text("✅ کالکشن ثبت و اعلام شد", reply_markup=akb()); return

# ---------- callbacks ----------
async def on_cb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    user = q.from_user
    d = load()
    eu(d, user)
    cb = q.data
    uid = str(user.id)

    if cb == "tr_n":
        c.user_data.pop("tr", None); await q.edit_message_text("لغو"); return
    if cb == "tr_y":
        tr = c.user_data.get("tr")
        if not tr or tr["from"] != uid:
            await q.edit_message_text("منقضی"); return
        fu = d["users"][tr["from"]]
        card = next((x for x in fu["cards"] if x["code"] == tr["code"]), None)
        if not card:
            await q.edit_message_text("نیست"); return
        fu["cards"] = [x for x in fu["cards"] if x["code"] != tr["code"]]
        if fu.get("profile_code") == tr["code"]:
            fu["profile_code"] = None
        tid = tr["to"]
        if tid not in d["users"]:
            d["users"][tid] = {"name": tr["to_name"], "username": "", "cards": [], "profile_code": None, "points": 0, "level": 1, "title": "-", "last_daily": None, "collections_done": []}
        d["users"][tid]["cards"].append(card)
        upd(d, tr["from"]); upd(d, tid); save(d)
        c.user_data.pop("tr", None)
        await q.edit_message_text(f"✅ به {tr['to_name']}")
        try:
            await c.bot.send_message(int(tid), f"🎁 {card.get('name')} ({card['code']})")
        except Exception:
            pass
        return

    if cb == "myc":
        if q.message.chat.type != ChatType.PRIVATE:
            await q.edit_message_text("اگر استارت کردی دوباره بزن؛ وگرنه اول /start پیوی")
            await q.message.reply_text("بعد از استارت:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📋 ارسال پیوی", callback_data="myc_pm")]]))
            return
        await send_cards(c, d, user)
        try:
            await q.edit_message_text("✅", reply_markup=pkb())
        except Exception:
            pass
        return
    if cb == "myc_pm":
        try:
            await send_cards(c, d, user); await q.answer("پیوی", show_alert=True)
        except Exception:
            await q.answer("اول /start", show_alert=True)
        return

    if cb == "setp":
        if q.message.chat.type != ChatType.PRIVATE:
            try:
                await c.bot.send_message(user.id, "کد کارت پروفایل را بفرست")
                # state only works in same chat context — tell user to type in PM after start
                await q.answer("پیوی", show_alert=True)
            except Exception:
                await q.answer("/start پیوی", show_alert=True)
            return
        c.user_data["st"] = "setp"
        await q.edit_message_text("کد کارت پروفایل:")
        return

    if cb == "shop":
        items = [s for s in d.get("shop", []) if s.get("stock", 0) > 0]
        if not items:
            await q.answer("خالی", show_alert=True); return
        lines = ["🛒\n"] + [f"• {s['name']} {s['price']}p ({s['stock']})" for s in items[:15]]
        rows = [[InlineKeyboardButton(f"خرید {s['name']}", callback_data=f"buy_{s['code']}")] for s in items[:15]]
        rows.append([InlineKeyboardButton("💰 فروش کارت", callback_data="sell")])
        try:
            await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))
        except Exception:
            await q.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))
        return

    if cb.startswith("buy_"):
        item = next((s for s in d["shop"] if s["code"] == cb[4:]), None)
        uu = d["users"][uid]
        if not item or item.get("stock", 0) <= 0:
            await q.answer("نیست", show_alert=True); return
        if uu.get("points", 0) < item["price"]:
            await q.answer("امتیاز کم", show_alert=True); return
        uu["points"] -= item["price"]; item["stock"] -= 1
        uu["cards"].append({
            "code": code(), "file_id": item["file_id"], "name": item["name"],
            "description": item.get("description", ""), "rarity": "فروشگاهی",
            "points": item.get("points", item["price"] // 2), "emoji": "",
        })
        upd(d, uid); save(d)
        await q.answer("خرید شد", show_alert=True)
        try:
            await c.bot.send_photo(user.id, item["file_id"], caption=f"✅ {item['name']}")
        except Exception:
            pass
        return

    if cb == "sell":
        c.user_data["st"] = "sell"
        if q.message.chat.type == ChatType.PRIVATE:
            await q.edit_message_text("کد یا اسم برای فروش:")
        else:
            try:
                await c.bot.send_message(user.id, "کد یا اسم برای فروش:")
                await q.answer("پیوی", show_alert=True)
            except Exception:
                await q.answer("/start", show_alert=True)
        return

    if cb == "cols":
        await show_collections(type("M", (), {"message": q.message})(), d, uid) if False else None
        cols = d.get("collections", [])
        if not cols:
            await q.answer("نیست", show_alert=True); return
        for col in cols:
            await q.message.reply_text(f"📦 {col.get('name')}\n{col.get('desc','')}")
        return

    if cb == "exch":
        c.user_data["st"] = "exch_codes"
        if q.message.chat.type == ChatType.PRIVATE:
            await q.edit_message_text("۴ کد کارت هم‌سطح با فاصله:")
        else:
            try:
                await c.bot.send_message(user.id, "۴ کد کارت هم‌سطح با فاصله بفرست:")
                await q.answer("پیوی", show_alert=True)
            except Exception:
                await q.answer("/start", show_alert=True)
        return

    if cb == "game":
        await q.message.reply_text(
            "🎮 ساخت بازی — تعداد بازیکن:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("۲", callback_data="gp_2"),
                InlineKeyboardButton("۴", callback_data="gp_4"),
                InlineKeyboardButton("۶", callback_data="gp_6"),
            ]]),
        )
        return
    if cb.startswith("gp_"):
        n = int(cb[3:])
        gid = code(5)
        d.setdefault("games", {})[gid] = {"players": n, "plays": {}, "chat_id": q.message.chat_id}
        save(d)
        c.user_data["st"] = "game_card"
        c.user_data["gid"] = gid
        await q.edit_message_text(f"بازی {n} نفره\nکارت خود را با کد یا اسم بفرستید\nدیگران هم بعد از /start در پیوی یا همینجا بفرستند با جوین:")
        await q.message.reply_text(
            f"برای شرکت: دکمه را بزنید سپس کارت بفرستید",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("شرکت در بازی", callback_data=f"gj_{gid}")]]),
        )
        return
    if cb.startswith("gj_"):
        gid = cb[3:]
        if gid not in d.get("games", {}):
            await q.answer("تمام شده", show_alert=True); return
        c.user_data["st"] = "game_card"
        c.user_data["gid"] = gid
        await q.answer("کارت را بفرست", show_alert=True)
        try:
            await c.bot.send_message(user.id, "کد یا اسم کارت بازی را بفرست:")
        except Exception:
            await q.message.reply_text(f"{user.full_name} کارت را اینجا بفرست")
        return

    if cb in ("br_l", "br_r"):
        br = c.user_data.get("browse")
        if not br:
            return
        br["i"] += -1 if cb == "br_l" else 1
        br["i"] %= len(br["list"])
        await send_browse(q.message.chat_id, c, d, br["list"], br["i"], edit_msg=q.message)
        return

    # admin
    if not adm(user.id, d):
        return
    if cb == "ac":
        c.user_data.clear(); await q.edit_message_text("لغو", reply_markup=akb()); return
    if cb == "a_up":
        c.user_data["st"] = "up_ph"; await q.edit_message_text("عکس کارت:"); return
    if cb.startswith("ur_"):
        rar = cb[3:]
        info = ri(d, rar)
        c.user_data.setdefault("up", {})["rarity"] = rar
        c.user_data["up"]["emoji"] = info.get("emoji", "")
        c.user_data["st"] = "up_pts"
        await q.edit_message_text(f"{rar}\nامتیاز کارت:"); return
    if cb == "a_rar":
        lines = [f"{r.get('emoji')} {r['name']} w{r.get('weight')} day{r.get('max_per_day_group')}" for r in d["rarities"]]
        await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕", callback_data="a_rar_add")], [InlineKeyboardButton("🔙", callback_data="a_back")]
        ])); return
    if cb == "a_rar_add":
        c.user_data["st"] = "add_rar"
        await q.edit_message_text("اسم | ایموجی | وزن | سقف روزانه هر گپ"); return
    if cb == "a_tit":
        lines = [f"• {t['name']} ({t['min_points']})" for t in d.get("titles", [])] or ["خالی"]
        await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ثبت گروهی", callback_data="a_tit_b")], [InlineKeyboardButton("🔙", callback_data="a_back")]
        ])); return
    if cb == "a_tit_b":
        c.user_data["st"] = "bulk_tit"
        await q.edit_message_text("• غول (از 2000 امتیاز)"); return
    if cb == "a_shop":
        await q.edit_message_text("فروشگاه ادمین", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕", callback_data="a_shop_add")],
            [InlineKeyboardButton("لیست", callback_data="a_shop_ls")],
            [InlineKeyboardButton("🔙", callback_data="a_back")],
        ])); return
    if cb == "a_shop_add":
        c.user_data["st"] = "shop_name"; await q.edit_message_text("نام:"); return
    if cb == "a_shop_ls":
        await q.edit_message_text("\n".join(f"{s['name']} {s['price']}p x{s['stock']}" for s in d.get("shop", [])) or "خالی", reply_markup=akb()); return
    if cb == "a_col":
        await q.edit_message_text("کالکشن", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ کالکشن", callback_data="a_col_add")],
            [InlineKeyboardButton("🔙", callback_data="a_back")],
        ])); return
    if cb == "a_col_add":
        c.user_data["st"] = "col_name"; await q.edit_message_text("نام کالکشن:"); return
    if cb == "a_tr":
        await q.edit_message_text("دستورات:\n" + "\n".join(d.get("transfer_cmds", [])), reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ دستور", callback_data="a_tr_add")], [InlineKeyboardButton("🔙", callback_data="a_back")]
        ])); return
    if cb == "a_tr_add":
        c.user_data["st"] = "tr_add"; await q.edit_message_text("متن دستور مثل: /Sh"); return
    if cb == "a_set":
        await q.edit_message_text("تنظیمات", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("قالب پروفایل", callback_data="a_tpl")],
            [InlineKeyboardButton("پیام استارت", callback_data="a_smsg")],
            [InlineKeyboardButton("آستانه پیام", callback_data="a_th")],
            [InlineKeyboardButton("🔙", callback_data="a_back")],
        ])); return
    if cb == "a_tpl":
        c.user_data["st"] = "tpl"
        await q.edit_message_text("{name}{tag}{title}{level}{points}{cards}{collections}{best_card}{rarity_summary}{profile_code}"); return
    if cb == "a_smsg":
        c.user_data["st"] = "smsg"; await q.edit_message_text("پیام استارت:"); return
    if cb == "a_th":
        c.user_data["st"] = "th"; await q.edit_message_text(f"الان {d.get('msg_threshold')}:"); return
    if cb == "a_adm":
        await q.edit_message_text("\n".join(map(str, d.get("admins", []))), reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕", callback_data="a_adm_add")], [InlineKeyboardButton("🔙", callback_data="a_back")]
        ])); return
    if cb == "a_adm_add":
        c.user_data["st"] = "add_adm"; await q.edit_message_text("آیدی:"); return
    if cb == "a_st":
        await q.edit_message_text(f"U{len(d['users'])} P{len(d['pool'])} S{len(d['shop'])} G{len(d['groups'])} C{len(d['collections'])}", reply_markup=akb()); return
    if cb == "a_back":
        await q.edit_message_text("ادمین", reply_markup=akb()); return

async def send_cards(c, d, user):
    uu = d["users"].get(str(user.id))
    if not uu or not uu.get("cards"):
        await c.bot.send_message(user.id, "کارتی نیست", reply_markup=pkb()); return
    # browse mode in PM
    c.user_data["browse"] = {"list": uu["cards"], "i": 0}
    await send_browse(user.id, c, d, uu["cards"], 0)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(ChatMemberHandler(on_join, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(on_cb))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, on_photo))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, on_gmsg), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text), group=0)
    log.info("full card bot up")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
