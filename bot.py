# -*- coding: utf-8 -*-
"""ربات کارت - اصلاح باگ: پنل گپ، فلش پیوی، ارسال فوری، state با ریپلای+تایم‌اوت"""
import logging, json, os, random, string, re, time
from datetime import date, datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, filters, ChatMemberHandler,
)
from telegram.constants import ChatMemberStatus, ChatType

BOT_TOKEN = "8273833935:AAFKVpl4Atb_ldgciIJfqtvFUlixvz2l1S4"
MAIN_ADMIN = 7530457395
DATA = "card_data.json"
DAILY = 100
STATE_TTL = 50

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger("cardbot")

def D():
    return {
        "admins": [MAIN_ADMIN], "pool": [], "shop": [], "users": {}, "groups": {},
        "rarities": [
            {"name": "معمولی", "emoji": "⚪", "weight": 40, "max_per_day_group": 10},
            {"name": "لجند", "emoji": "🌟", "weight": 25, "max_per_day_group": 5},
            {"name": "اپیک", "emoji": "⚡", "weight": 15, "max_per_day_group": 3},
            {"name": "اولتیمت", "emoji": "🔥", "weight": 10, "max_per_day_group": 2},
            {"name": "افسانه‌ای", "emoji": "👑", "weight": 5, "max_per_day_group": 1},
            {"name": "فوق‌کمیاب", "emoji": "💎", "weight": 2, "max_per_day_group": 1},
        ],
        "titles": [], "collections": [],
        "transfer_cmds": ["انتقال کارت", "/c", "/sh", "شیر کارت"],
        "profile_tpl": "👤 {name} ({tag})\n🏷 {title}\n📊 سطح {level}\n💰 {points}\n🃏 {cards}\n📦 {collections}\n🏆 {best_card}\n📊 {rarity_summary}",
        "start_msg": "🎴 ربات کارت\nپروفایلم | /help | /top | /force",
        "msg_threshold": 560, "sell_mult": 2.0, "games": {},
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
            best_card=best(u), rarity_summary=rsum(u), profile_code=u.get("profile_code") or "-",
        )
    except Exception:
        return f"{u.get('name')} | L{u.get('level')} | {u.get('points')}p"

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
        [InlineKeyboardButton("⚡ ارسال فوری کارت", callback_data="a_force")],
        [InlineKeyboardButton("🏷 سطوح", callback_data="a_rar")],
        [InlineKeyboardButton("📛 لقب", callback_data="a_tit")],
        [InlineKeyboardButton("🛒 فروشگاه ادمین", callback_data="a_shop")],
        [InlineKeyboardButton("📦 کالکشن", callback_data="a_col")],
        [InlineKeyboardButton("⚙️ تنظیمات", callback_data="a_set")],
        [InlineKeyboardButton("👤 ادمین", callback_data="a_adm")],
        [InlineKeyboardButton("📊 آمار", callback_data="a_st")],
    ])

def cancel_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="cancel_st")]])

def set_state(c, kind, extra=None):
    c.user_data["st"] = {"kind": kind, "ts": time.time(), "extra": extra or {}}

def get_state(c):
    st = c.user_data.get("st")
    if not st or not isinstance(st, dict):
        return None
    if time.time() - st.get("ts", 0) > STATE_TTL:
        c.user_data.pop("st", None)
        return None
    return st

def clear_state(c):
    c.user_data.pop("st", None)

def is_reply_to_bot(u, c):
    msg = u.message
    if not msg or not msg.reply_to_message:
        return False
    try:
        return msg.reply_to_message.from_user and msg.reply_to_message.from_user.id == c.bot.id
    except Exception:
        return False

# ---- cmds ----
async def cmd_start(u, c):
    user = u.effective_user
    d = load(); eu(d, user)
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

async def cmd_help(u, c):
    await u.message.reply_text(
        "📖 راهنما\n• ریپلای+کارت\n• پروفایلم\n• ریپلای+پروفایل کارتی\n• جستجو کد\n• /top /force\n"
        "وقتی ربات کد خواست روی همان پیام ریپلای کن (۵۰ث)",
        reply_markup=pkb(),
    )

async def cmd_top(u, c):
    d = load()
    us = sorted(d["users"].items(), key=lambda x: x[1].get("points", 0), reverse=True)
    lines = ["🏆 ۱۰ برتر\n"]
    for i, (_, x) in enumerate(us[:10], 1):
        tg = f"@{x['username']}" if x.get("username") else x.get("name")
        lines.append(f"{i}. {tg} — {x.get('points',0)}")
    await u.message.reply_text("\n".join(lines))

async def cmd_admin(u, c):
    d = load()
    if not adm(u.effective_user.id, d):
        return
    if u.effective_chat.type != ChatType.PRIVATE:
        await u.message.reply_text("فقط پیوی"); return
    await u.message.reply_text("🔐 ادمین", reply_markup=akb())

async def cmd_force(u, c):
    d = load()
    if not adm(u.effective_user.id, d):
        return
    await do_force(c, d, u.message.reply_text)

async def do_force(c, d, reply):
    if not any(x.get("remain_dist", 1) > 0 for x in d.get("pool", [])):
        await reply("استخر خالی — اول آپلود کن")
        return
    groups = list(d.get("groups", {}).keys())
    if not groups:
        await reply("گپی نیست — ربات را به گپ اضافه کن و یک پیام در گپ بفرست")
        return
    ok = 0
    for gid in groups:
        try:
            await dist(c, int(gid), d)
            ok += 1
        except Exception as e:
            log.error("force %s %s", gid, e)
    await reply(f"⚡ ارسال فوری به {ok} گپ\nباقی: {len([x for x in load().get('pool',[]) if x.get('remain_dist',1)>0])}")

async def on_join(u, c):
    r = u.my_chat_member
    ch = r.chat
    if ch.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    if r.new_chat_member.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR):
        d = load()
        d["groups"].setdefault(str(ch.id), {"title": ch.title or "", "msg_count": 0, "active_msg_id": None, "pending": None, "daily_rare": {}, "last_dist": {}})
        save(d)
        try:
            await c.bot.send_message(ch.id, "🎴 ربات کارت فعال\nریپلای + کارت\nپروفایلم | /help")
        except Exception:
            pass

async def on_gmsg(u, c):
    if not u.message or u.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    if u.message.text and u.message.text.startswith("/"):
        return
    d = load()
    cid = str(u.effective_chat.id)
    g = d["groups"].setdefault(cid, {"title": u.effective_chat.title or "", "msg_count": 0, "active_msg_id": None, "pending": None, "daily_rare": {}, "last_dist": {}})
    g["msg_count"] = g.get("msg_count", 0) + 1
    if g["msg_count"] >= d.get("msg_threshold", 560):
        g["msg_count"] = 0
        save(d)
        try:
            await dist(c, u.effective_chat.id, d)
        except Exception as e:
            log.error(e)
    else:
        save(d)

async def dist(c, chat_id, d=None):
    d = d or load()
    cid = str(chat_id)
    g = d["groups"].setdefault(cid, {"msg_count": 0, "daily_rare": {}, "last_dist": {}})
    today = str(date.today())
    avail = []
    for card in d["pool"]:
        if card.get("remain_dist", 1) <= 0:
            continue
        rar = card.get("rarity", "معمولی")
        info = ri(d, rar)
        key = f"{today}:{rar}"
        if g.get("daily_rare", {}).get(key, 0) >= info.get("max_per_day_group", 5):
            continue
        avail.append(card)
    if not avail:
        avail = [x for x in d["pool"] if x.get("remain_dist", 1) > 0]
    if not avail:
        raise RuntimeError("empty pool")
    w = [max(1, ri(d, x.get("rarity", "")).get("weight", 10)) for x in avail]
    card = random.choices(avail, weights=w, k=1)[0]
    card["remain_dist"] = card.get("remain_dist", 1) - 1
    rar = card.get("rarity", "")
    key = f"{today}:{rar}"
    g.setdefault("daily_rare", {})[key] = g.get("daily_rare", {}).get(key, 0) + 1
    if card["remain_dist"] <= 0:
        d["pool"] = [x for x in d["pool"] if x["code"] != card["code"]]
    em = ri(d, rar).get("emoji", "✨")
    cap = f"{em} <b>{card.get('name')}</b>\n{card.get('description','')}\n\n🏷 {rar}\n⭐ {card.get('points',0)}\n🆔 <code>{card['code']}</code>\n\nریپلای + <b>کارت</b>"
    msg = await c.bot.send_photo(chat_id, photo=card["file_id"], caption=cap, parse_mode="HTML")
    g["active_msg_id"] = msg.message_id
    g["pending"] = card
    save(d)

async def claim(u, c, d):
    user = u.effective_user
    ch = u.effective_chat
    rp = u.message.reply_to_message
    g = d["groups"].get(str(ch.id))
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
    })
    gain = int(card.get("points", 0))
    x["points"] = old + gain
    upd(d, uid)
    await check_collections(c, d, uid, user)
    save(d)
    tag = f"@{user.username}" if user.username else user.full_name
    nc = f"✅ {tag}\n{card.get('name')} | +{gain} ({old}→{x['points']})"
    try:
        await c.bot.edit_message_caption(ch.id, rp.message_id, caption=nc)
    except Exception:
        await u.message.reply_text(nc)


async def check_collections(c, d, uid, user):
    """اگر همه کارت‌های یک کالکشن جمع شد → جایزه + اعلام"""
    u = d["users"].get(uid)
    if not u:
        return
    have = {x["code"] for x in u.get("cards", [])}
    for col in d.get("collections", []):
        cid = col.get("id")
        if not cid or cid in u.get("collections_done", []):
            continue
        need = set(col.get("card_codes", []))
        if not need or not need.issubset(have):
            continue
        u.setdefault("collections_done", []).append(cid)
        # کارت جایزه
        if col.get("prize"):
            pr = dict(col["prize"])
            pr["code"] = code()
            u["cards"].append(pr)
            u["points"] = u.get("points", 0) + int(pr.get("points", 0))
        # امتیاز جایزه متنی
        bonus = int(col.get("bonus_points", 0))
        if bonus:
            u["points"] = u.get("points", 0) + bonus
        upd(d, uid)
        tag = f"@{user.username}" if user.username else user.full_name
        txt = col.get("done_text") or (
            f"🏆 کالکشن <b>{col.get('name')}</b> کامل شد!\n"
            f"مالک: {tag}\n"
            f"{col.get('reward_text', '')}"
        )
        # اعلام در گپ‌ها
        targets = col.get("groups") or list(d.get("groups", {}).keys())
        for gid in targets:
            try:
                if col.get("preview"):
                    await c.bot.send_photo(int(gid), photo=col["preview"], caption=txt, parse_mode="HTML")
                else:
                    await c.bot.send_message(int(gid), txt, parse_mode="HTML")
            except Exception:
                pass
        try:
            await c.bot.send_message(user.id, f"🎉 کالکشن «{col.get('name')}» را کامل کردی!")
        except Exception:
            pass

async def send_browse(chat_id, c, cards, i, msg_id=None):
    if not cards:
        return
    i = i % len(cards)
    card = cards[i]
    cap = f"{i+1}/{len(cards)}\n{card.get('emoji','')} <b>{card.get('name')}</b>\n{card.get('description','')}\n{card.get('rarity')} | ⭐{card.get('points')}\nکد: <code>{card['code']}</code>"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️", callback_data="br_l"), InlineKeyboardButton(f"{i+1}/{len(cards)}", callback_data="noop"), InlineKeyboardButton("➡️", callback_data="br_r")]])
    if msg_id:
        try:
            await c.bot.edit_message_media(chat_id=chat_id, message_id=msg_id, media=InputMediaPhoto(media=card["file_id"], caption=cap, parse_mode="HTML"), reply_markup=kb)
            return
        except Exception as e:
            log.warning("edit_media %s", e)
    await c.bot.send_photo(chat_id, photo=card["file_id"], caption=cap, parse_mode="HTML", reply_markup=kb)

async def on_text(u, c):
    if not u.message or not u.message.text:
        return
    user = u.effective_user
    ch = u.effective_chat
    text = u.message.text.strip()
    d = load(); eu(d, user)
    uid = str(user.id)
    st = get_state(c)

    # state فقط با ریپلای به ربات
    if st and is_reply_to_bot(u, c):
        kind = st.get("kind")
        if kind == "setp":
            cd0 = text.lstrip("`").strip()
            uu = d["users"][uid]
            fnd = next((x for x in uu["cards"] if x["code"] == cd0), None)
            clear_state(c)
            if not fnd:
                await u.message.reply_text("❌ کد بین کارت‌های تو نیست")
            else:
                uu["profile_code"] = cd0; save(d)
                await u.message.reply_photo(fnd["file_id"], caption=f"✅ پروفایل\n<code>{cd0}</code>", parse_mode="HTML", reply_markup=pkb())
            return
        if kind == "sell":
            clear_state(c)
            uu = d["users"][uid]
            ql = text.lower()
            ms = [x for x in uu.get("cards", []) if x["code"] == text or ql in x.get("name", "").lower()]
            if not ms:
                await u.message.reply_text("پیدا نشد"); return
            if len(ms) > 1:
                await u.message.reply_text("کد دقیق:\n" + "\n".join(f"{x['name']} <code>{x['code']}</code>" for x in ms[:8]), parse_mode="HTML")
                set_state(c, "sell"); return
            card = ms[0]
            gain = int(card.get("points", 0) * d.get("sell_mult", 2.0))
            uu["cards"] = [x for x in uu["cards"] if x["code"] != card["code"]]
            if uu.get("profile_code") == card["code"]:
                uu["profile_code"] = None
            uu["points"] = uu.get("points", 0) + gain
            upd(d, uid); save(d)
            await u.message.reply_text(f"✅ فروش +{gain} → {uu['points']}", reply_markup=pkb())
            return
        if kind == "exch":
            clear_state(c)
            codes = [x.lstrip("`") for x in text.replace(",", " ").split() if x]
            if len(codes) < 4:
                await u.message.reply_text("حداقل ۴ کد"); return
            uu = d["users"][uid]
            cards = []
            for cd0 in codes[:4]:
                fnd = next((x for x in uu["cards"] if x["code"] == cd0), None)
                if not fnd:
                    await u.message.reply_text(f"{cd0} مال تو نیست"); return
                cards.append(fnd)
            rar = cards[0].get("rarity")
            if not all(x.get("rarity") == rar for x in cards):
                await u.message.reply_text("همه یک سطح"); return
            names = [r["name"] for r in d.get("rarities", [])]
            try:
                idx = names.index(rar)
            except ValueError:
                idx = 0
            better = names[idx+1:]
            pool = [x for x in d["pool"] if x.get("rarity") in better] or d["pool"]
            if not pool:
                await u.message.reply_text("جایزه نیست"); return
            prize = random.choice(pool)
            rm = {x["code"] for x in cards}
            uu["cards"] = [x for x in uu["cards"] if x["code"] not in rm]
            prize["remain_dist"] = prize.get("remain_dist", 1) - 1
            if prize.get("remain_dist", 0) <= 0:
                d["pool"] = [x for x in d["pool"] if x["code"] != prize["code"]]
            uu["cards"].append({k: prize.get(k) for k in ("code","file_id","name","description","rarity","points","emoji")})
            uu["points"] = uu.get("points", 0) + int(prize.get("points", 0))
            upd(d, uid); save(d)
            await u.message.reply_photo(prize["file_id"], caption=f"🔄 {prize.get('name')}", reply_markup=pkb())
            return
        if kind and kind.startswith("adm_"):
            await admin_text(u, c, d, text)
            return
    # state هست ولی ریپلای به ربات نیست → نادیده

    if text == "کارت" and u.message.reply_to_message and ch.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        await claim(u, c, d); return

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
        if not t: return
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

    if text in ("کالکشن", "کالکشن ها", "کالکشن‌ها"):
        cols = d.get("collections", [])
        if not cols:
            await u.message.reply_text("کالکشنی نیست")
            return
        have = {x["code"] for x in d["users"][uid].get("cards", [])}
        done_ids = set(d["users"][uid].get("collections_done", []))
        for col in cols:
            need = col.get("card_codes", [])
            got = sum(1 for x in need if x in have)
            total = max(len(need), 1)
            mark = "✅ کامل" if col.get("id") in done_ids else f"{got}/{total}"
            cap = (
                f"📦 <b>{col.get('name')}</b> — {mark}\n"
                f"{col.get('desc', '')}\n"
                f"جایزه: {col.get('reward_text', '-')}"
            )
            try:
                if col.get("preview"):
                    await u.message.reply_photo(col["preview"], caption=cap, parse_mode="HTML")
                else:
                    await u.message.reply_text(cap, parse_mode="HTML")
            except Exception:
                await u.message.reply_text(cap, parse_mode="HTML")
        return

    if text.startswith("جستجو "):
        cd0 = text.split(" ", 1)[1].strip().lstrip("`")
        for _, ou in d["users"].items():
            for x in ou.get("cards", []):
                if x["code"] == cd0:
                    tg = f"@{ou['username']}" if ou.get("username") else ou.get("name")
                    await u.message.reply_photo(x["file_id"], caption=f"{x.get('name')}\n<code>{x['code']}</code>\n{tg}", parse_mode="HTML")
                    return
        await u.message.reply_text("نبود"); return

    for cmd in d.get("transfer_cmds", []):
        if text.lower().startswith(cmd.lower()):
            rest = text[len(cmd):].strip()
            cd0 = rest.split()[0].lstrip("`") if rest else ""
            if not cd0 or not u.message.reply_to_message:
                await u.message.reply_text(f"{cmd} کد + ریپلای"); return
            tg = u.message.reply_to_message.from_user
            if not tg or tg.id == user.id or tg.is_bot:
                await u.message.reply_text("گیرنده نامعتبر"); return
            card = next((x for x in d["users"][uid].get("cards", []) if x["code"] == cd0), None)
            if not card:
                await u.message.reply_text("مال تو نیست"); return
            c.user_data["tr"] = {"code": cd0, "from": uid, "to": str(tg.id), "to_name": tg.full_name}
            await u.message.reply_text(f"انتقال به {tg.full_name}؟", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅", callback_data="tr_y"), InlineKeyboardButton("❌", callback_data="tr_n")]]))
            return

    if adm(user.id, d) and ch.type == ChatType.PRIVATE:
        st2 = get_state(c)
        if st2 and st2.get("kind", "").startswith("adm_"):
            # در پیوی ادمین، برای راحتی بدون ریپلای هم قبول (فقط ادمین)
            await admin_text(u, c, d, text)

async def admin_text(u, c, d, text):
    st = get_state(c)
    if not st: return
    kind = st.get("kind")
    if kind == "adm_up_name":
        c.user_data.setdefault("up", {})["name"] = text
        set_state(c, "adm_up_desc")
        await u.message.reply_text("توضیحات:", reply_markup=cancel_kb()); return
    if kind == "adm_up_desc":
        c.user_data["up"]["description"] = text
        rows = [[InlineKeyboardButton(f"{r.get('emoji','')} {r['name']}", callback_data=f"ur_{r['name']}")] for r in d["rarities"]]
        set_state(c, "adm_up_rar")
        await u.message.reply_text("سطح:", reply_markup=InlineKeyboardMarkup(rows + [[InlineKeyboardButton("❌", callback_data="cancel_st")]])); return
    if kind == "adm_up_pts":
        try: c.user_data["up"]["points"] = int(text)
        except ValueError:
            await u.message.reply_text("عدد"); return
        set_state(c, "adm_up_dist")
        await u.message.reply_text("تعداد توزیع:", reply_markup=cancel_kb()); return
    if kind == "adm_up_dist":
        try: distn = int(text)
        except ValueError:
            await u.message.reply_text("عدد"); return
        up = c.user_data.get("up", {})
        cd0 = code()
        card = {"code": cd0, "file_id": up["file_id"], "name": up.get("name"), "description": up.get("description",""), "rarity": up.get("rarity","معمولی"), "emoji": up.get("emoji",""), "points": up.get("points",0), "remain_dist": distn, "max_dist": distn}
        d["pool"].append(card); save(d); clear_state(c)
        await u.message.reply_text(f"✅ {card['name']}\n<code>{cd0}</code>\n{card['rarity']} | {card['points']} | ×{distn}", parse_mode="HTML", reply_markup=akb()); return
    if kind == "adm_rar":
        p = [x.strip() for x in text.split("|")]
        d["rarities"].append({"name": p[0], "emoji": p[1] if len(p)>1 else "✨", "weight": int(p[2]) if len(p)>2 and p[2].isdigit() else 5, "max_per_day_group": int(p[3]) if len(p)>3 and p[3].isdigit() else 2})
        save(d); clear_state(c); await u.message.reply_text("✅", reply_markup=akb()); return
    if kind == "adm_tit":
        n = 0
        for line in text.splitlines():
            line = line.strip().lstrip("•").lstrip("-").strip()
            m = re.search(r"(.+?)\s*\(از\s*(\d+)\s*امتیاز\)", line) or re.search(r"(.+?)\s+(\d+)\s*$", line)
            if m:
                d["titles"].append({"name": m.group(1).strip(), "min_points": int(m.group(2))}); n += 1
        d["titles"].sort(key=lambda t: t["min_points"]); save(d); clear_state(c)
        await u.message.reply_text(f"✅ {n}", reply_markup=akb()); return
    if kind == "adm_tpl":
        d["profile_tpl"] = text; save(d); clear_state(c); await u.message.reply_text("✅", reply_markup=akb()); return
    if kind == "adm_smsg":
        d["start_msg"] = text; save(d); clear_state(c); await u.message.reply_text("✅", reply_markup=akb()); return
    if kind == "adm_th":
        try:
            d["msg_threshold"] = max(10, int(text)); save(d); clear_state(c)
            await u.message.reply_text(f"✅ هر {d['msg_threshold']}", reply_markup=akb())
        except ValueError:
            await u.message.reply_text("عدد")
        return
    if kind == "adm_adm":
        try:
            a = int(text)
            if a not in d["admins"]: d["admins"].append(a)
            save(d); clear_state(c); await u.message.reply_text(f"✅ {a}", reply_markup=akb())
        except ValueError:
            await u.message.reply_text("آیدی")
        return
    if kind == "adm_shop_name":
        c.user_data["si"] = {"name": text}; set_state(c, "adm_shop_desc"); await u.message.reply_text("توضیح:", reply_markup=cancel_kb()); return
    if kind == "adm_shop_desc":
        c.user_data["si"]["description"] = text; set_state(c, "adm_shop_price"); await u.message.reply_text("قیمت:", reply_markup=cancel_kb()); return
    if kind == "adm_shop_price":
        try: c.user_data["si"]["price"] = int(text)
        except ValueError:
            await u.message.reply_text("عدد"); return
        set_state(c, "adm_shop_stock"); await u.message.reply_text("موجودی:", reply_markup=cancel_kb()); return
    if kind == "adm_shop_stock":
        try: c.user_data["si"]["stock"] = int(text)
        except ValueError:
            await u.message.reply_text("عدد"); return
        set_state(c, "adm_shop_ph"); await u.message.reply_text("عکس:", reply_markup=cancel_kb()); return
    # ---- کالکشن ----
    if kind == "adm_col_name":
        c.user_data["col"] = {"id": code(4), "name": text, "card_codes": [], "groups": []}
        set_state(c, "adm_col_desc")
        await u.message.reply_text("توضیحات کالکشن را بفرست:", reply_markup=cancel_kb())
        return
    if kind == "adm_col_desc":
        c.user_data["col"]["desc"] = text
        set_state(c, "adm_col_codes")
        await u.message.reply_text(
            "کد کارت‌های عضو را با فاصله بفرست:\n"
            "مثال: <code>cabc123 cdef456 cghi789</code>",
            parse_mode="HTML",
            reply_markup=cancel_kb(),
        )
        return
    if kind == "adm_col_codes":
        codes = [x.lstrip("`") for x in text.replace(",", " ").split() if x]
        if not codes:
            await u.message.reply_text("حداقل یک کد بفرست")
            return
        c.user_data["col"]["card_codes"] = codes
        set_state(c, "adm_col_reward")
        await u.message.reply_text(
            "متن جایزه / اعلام را بفرست (وقتی کسی کامل کرد نشان داده می‌شود):",
            reply_markup=cancel_kb(),
        )
        return
    if kind == "adm_col_reward":
        c.user_data["col"]["reward_text"] = text
        set_state(c, "adm_col_bonus")
        await u.message.reply_text(
            "امتیاز جایزه عددی (اگر نمی‌خوای ۰ بفرست):",
            reply_markup=cancel_kb(),
        )
        return
    if kind == "adm_col_bonus":
        try:
            c.user_data["col"]["bonus_points"] = int(text)
        except ValueError:
            await u.message.reply_text("عدد بفرست (مثلاً ۰ یا ۵۰۰)")
            return
        set_state(c, "adm_col_prize")
        await u.message.reply_text(
            "کد کارت جایزه از استخر را بفرست (اگر نمی‌خوای بنویس: - )",
            reply_markup=cancel_kb(),
        )
        return
    if kind == "adm_col_prize":
        col = c.user_data.get("col", {})
        t = text.strip().lstrip("`")
        if t != "-":
            pr = next((x for x in d["pool"] if x["code"] == t), None)
            if not pr:
                await u.message.reply_text("این کد تو استخر نیست. دوباره بفرست یا -")
                return
            col["prize"] = {
                "file_id": pr["file_id"],
                "name": pr.get("name", "جایزه"),
                "description": pr.get("description", ""),
                "rarity": pr.get("rarity", "جایزه"),
                "points": pr.get("points", 0),
                "emoji": pr.get("emoji", "🎁"),
            }
            # از استخر کم نکن مگر بخوای — جایزه کپی می‌شود
        set_state(c, "adm_col_preview")
        await u.message.reply_text("عکس پیش‌نمایش کالکشن را بفرست:", reply_markup=cancel_kb())
        return

async def on_photo(u, c):
    user = u.effective_user
    d = load()
    if not adm(user.id, d) or u.effective_chat.type != ChatType.PRIVATE:
        return
    st = get_state(c)
    if not st: return
    fid = u.message.photo[-1].file_id
    kind = st.get("kind")
    if kind == "adm_up_ph":
        c.user_data["up"] = {"file_id": fid}; set_state(c, "adm_up_name")
        await u.message.reply_text("اسم کارت:", reply_markup=cancel_kb()); return
    if kind == "adm_shop_ph":
        si = c.user_data.get("si", {})
        si["file_id"] = fid; si["code"] = code(); si["rarity"] = "فروشگاهی"; si["points"] = si.get("price", 0) // 2
        d["shop"].append(si); save(d); clear_state(c)
        await u.message.reply_text(f"✅ {si['name']}", reply_markup=akb()); return
    if kind == "adm_col_preview":
        col = c.user_data.get("col", {})
        col["preview"] = fid
        col["done_text"] = (
            f"🏆 کالکشن <b>{col.get('name')}</b> کامل شد!\n"
            f"{col.get('reward_text', '')}"
        )
        d.setdefault("collections", []).append(col)
        save(d)
        clear_state(c)
        # اعلام ساخت در همه گپ‌ها
        announce = (
            f"📦 <b>کالکشن جدید</b>\n"
            f"نام: {col.get('name')}\n"
            f"{col.get('desc', '')}\n"
            f"تعداد کارت: {len(col.get('card_codes', []))}\n"
            f"جایزه: {col.get('reward_text', '-')}\n"
            f"امتیاز جایزه: {col.get('bonus_points', 0)}"
        )
        for gid in list(d.get("groups", {}).keys())[:30]:
            try:
                await c.bot.send_photo(int(gid), photo=fid, caption=announce, parse_mode="HTML")
            except Exception:
                try:
                    await c.bot.send_message(int(gid), announce, parse_mode="HTML")
                except Exception:
                    pass
        await u.message.reply_text(
            f"✅ کالکشن «{col.get('name')}» ثبت و اعلام شد\n"
            f"کارت‌ها: {len(col.get('card_codes', []))}",
            reply_markup=akb(),
        )
        return

async def on_cb(u, c):
    q = u.callback_query
    await q.answer()
    user = q.from_user
    d = load(); eu(d, user)
    cb = q.data
    uid = str(user.id)

    if cb == "cancel_st":
        clear_state(c)
        try:
            await q.edit_message_text("❌ لغو شد")
        except Exception:
            pass
        return
    if cb == "noop":
        return
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
        return

    if cb == "myc":
        cards = d["users"][uid].get("cards", [])
        if not cards:
            await q.answer("کارتی نداری", show_alert=True); return
        lines = [f"📋 <b>{len(cards)} کارت</b>\n"]
        for i, x in enumerate(cards[:40], 1):
            lines.append(f"{i}. {x.get('name')} | {x.get('rarity')} | <code>{x['code']}</code>")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🖼 مرور فلش", callback_data="myc_br")],
            [InlineKeyboardButton("🔙", callback_data="back_p")],
        ])
        try:
            await q.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=kb)
        except Exception:
            await q.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=kb)
        return

    if cb == "myc_br":
        cards = d["users"][uid].get("cards", [])
        if not cards:
            await q.answer("خالی", show_alert=True); return
        c.user_data["browse"] = {"list": cards, "i": 0}
        await send_browse(q.message.chat_id, c, cards, 0)
        return

    if cb == "back_p":
        try:
            await q.edit_message_text(profile(d, uid), reply_markup=pkb())
        except Exception:
            await q.message.reply_text(profile(d, uid), reply_markup=pkb())
        return

    if cb == "setp":
        set_state(c, "setp")
        text = f"🖼 کد کارت را <b>با ریپلای روی همین پیام</b> بفرست\nمهلت {STATE_TTL} ثانیه\nکدها: لیست کارت‌هام"
        try:
            await q.edit_message_text(text, parse_mode="HTML", reply_markup=cancel_kb())
        except Exception:
            await q.message.reply_text(text, parse_mode="HTML", reply_markup=cancel_kb())
        return

    if cb == "shop":
        items = [s for s in d.get("shop", []) if s.get("stock", 0) > 0]
        pts = d["users"][uid].get("points", 0)
        lines = [f"🛒 امتیاز تو: <b>{pts}</b>\n"]
        rows = []
        if not items:
            lines.append("موجودی فروشگاه خالی است.")
        else:
            for s in items[:15]:
                lines.append(f"• {s['name']} — {s['price']} (×{s['stock']})")
                rows.append([InlineKeyboardButton(f"خرید {s['name']} ({s['price']})", callback_data=f"buy_{s['code']}")])
        rows.append([InlineKeyboardButton("💰 فروش کارت", callback_data="sell")])
        rows.append([InlineKeyboardButton("🔙", callback_data="back_p")])
        try:
            await q.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))
        except Exception:
            await q.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))
        return

    if cb.startswith("buy_"):
        item = next((s for s in d["shop"] if s["code"] == cb[4:]), None)
        uu = d["users"][uid]
        if not item or item.get("stock", 0) <= 0:
            await q.answer("❌ موجودی نداره", show_alert=True); return
        price = int(item.get("price", 0))
        if uu.get("points", 0) < price:
            await q.answer(f"❌ امتیاز کافی نیست (داری {uu.get('points',0)} لازم {price})", show_alert=True); return
        uu["points"] -= price; item["stock"] -= 1
        uu["cards"].append({"code": code(), "file_id": item["file_id"], "name": item["name"], "description": item.get("description",""), "rarity": "فروشگاهی", "points": item.get("points", price//2), "emoji": ""})
        upd(d, uid); save(d)
        await q.answer("✅ خرید شد", show_alert=True)
        await q.message.reply_photo(item["file_id"], caption=f"✅ {item['name']}\nامتیاز: {uu['points']}")
        return

    if cb == "sell":
        set_state(c, "sell")
        text = f"کد/اسم را با ریپلای به این پیام بفرست ({STATE_TTL}ث)"
        try:
            await q.edit_message_text(text, reply_markup=cancel_kb())
        except Exception:
            await q.message.reply_text(text, reply_markup=cancel_kb())
        return

    if cb == "cols":
        cols = d.get("collections", [])
        if not cols:
            await q.answer("کالکشنی نیست", show_alert=True)
            return
        have = {x["code"] for x in d["users"][uid].get("cards", [])}
        done_ids = set(d["users"][uid].get("collections_done", []))
        lines = ["📦 <b>کالکشن‌ها</b>\n"]
        for col in cols:
            need = col.get("card_codes", [])
            got = sum(1 for x in need if x in have)
            total = max(len(need), 1)
            mark = "✅" if col.get("id") in done_ids else f"{got}/{total}"
            lines.append(f"• <b>{col.get('name')}</b> — {mark}")
            if col.get("desc"):
                lines.append(f"  {col.get('desc')[:60]}")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🖼 پیش‌نمایش‌ها", callback_data="cols_prev")],
            [InlineKeyboardButton("🔙", callback_data="back_p")],
        ])
        try:
            await q.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=kb)
        except Exception:
            await q.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=kb)
        return

    if cb == "cols_prev":
        cols = d.get("collections", [])
        if not cols:
            await q.answer("نیست", show_alert=True)
            return
        have = {x["code"] for x in d["users"][uid].get("cards", [])}
        for col in cols[:10]:
            need = col.get("card_codes", [])
            got = sum(1 for x in need if x in have)
            total = max(len(need), 1)
            cap = (
                f"📦 <b>{col.get('name')}</b>\n"
                f"{col.get('desc', '')}\n"
                f"پیشرفت: {got}/{total}\n"
                f"جایزه: {col.get('reward_text', '-')}\n"
                f"امتیاز: {col.get('bonus_points', 0)}"
            )
            try:
                if col.get("preview"):
                    await q.message.reply_photo(col["preview"], caption=cap, parse_mode="HTML")
                else:
                    await q.message.reply_text(cap, parse_mode="HTML")
            except Exception:
                pass
        await q.answer()
        return

    if cb == "exch":
        set_state(c, "exch")
        text = f"۴ کد هم‌سطح با فاصله + ریپلای به این پیام ({STATE_TTL}ث)"
        try:
            await q.edit_message_text(text, reply_markup=cancel_kb())
        except Exception:
            await q.message.reply_text(text, reply_markup=cancel_kb())
        return

    if cb == "game":
        await q.message.reply_text("تعداد:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("۲", callback_data="gp_2"), InlineKeyboardButton("۴", callback_data="gp_4")]]))
        return
    if cb.startswith("gp_"):
        n = int(cb[3:]); gid = code(5)
        d.setdefault("games", {})[gid] = {"players": n, "plays": {}, "chat_id": q.message.chat_id}
        save(d)
        await q.edit_message_text(f"بازی {n} نفره", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("شرکت", callback_data=f"gj_{gid}")]]))
        return
    if cb.startswith("gj_"):
        gid = cb[3:]
        if gid not in d.get("games", {}):
            await q.answer("تمام", show_alert=True); return
        set_state(c, "exch")  # reuse pattern - actually game needs separate; simple: tell user send card code as claim later
        await q.message.reply_text("فعلاً کارت را با امتیاز بالاتر در /top ببین — بازی کامل در آپدیت بعدی", reply_markup=cancel_kb())
        return

    if cb in ("br_l", "br_r"):
        br = c.user_data.get("browse")
        if not br: return
        br["i"] += -1 if cb == "br_l" else 1
        await send_browse(q.message.chat_id, c, br["list"], br["i"], msg_id=q.message.message_id)
        return

    if not adm(user.id, d):
        return
    if cb == "a_force":
        async def _r(t):
            try: await q.edit_message_text(t, reply_markup=akb())
            except Exception: await q.message.reply_text(t, reply_markup=akb())
        await do_force(c, d, _r); return
    if cb == "a_up":
        set_state(c, "adm_up_ph"); await q.edit_message_text("عکس:", reply_markup=cancel_kb()); return
    if cb.startswith("ur_"):
        rar = cb[3:]; info = ri(d, rar)
        c.user_data.setdefault("up", {})["rarity"] = rar
        c.user_data["up"]["emoji"] = info.get("emoji", "")
        set_state(c, "adm_up_pts")
        await q.message.reply_text(f"{rar}\nامتیاز:", reply_markup=cancel_kb()); return
    if cb == "a_rar":
        await q.edit_message_text("\n".join(f"{r.get('emoji')} {r['name']}" for r in d["rarities"]), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕", callback_data="a_rar_add")], [InlineKeyboardButton("🔙", callback_data="a_back")]])); return
    if cb == "a_rar_add":
        set_state(c, "adm_rar"); await q.edit_message_text("اسم|ایموجی|وزن|سقف", reply_markup=cancel_kb()); return
    if cb == "a_tit":
        await q.edit_message_text("\n".join(f"• {t['name']} ({t['min_points']})" for t in d.get("titles", [])) or "خالی", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("گروهی", callback_data="a_tit_b")], [InlineKeyboardButton("🔙", callback_data="a_back")]])); return
    if cb == "a_tit_b":
        set_state(c, "adm_tit"); await q.edit_message_text("• غول (از 2000 امتیاز)", reply_markup=cancel_kb()); return
    if cb == "a_shop":
        await q.edit_message_text("فروشگاه", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕", callback_data="a_shop_add")], [InlineKeyboardButton("🔙", callback_data="a_back")]])); return
    if cb == "a_shop_add":
        set_state(c, "adm_shop_name"); await q.edit_message_text("نام:", reply_markup=cancel_kb()); return
    if cb == "a_col":
        cols = d.get("collections", [])
        lines = [f"📦 کالکشن‌ها: {len(cols)}\n"]
        for col in cols:
            lines.append(f"• {col.get('name')} ({len(col.get('card_codes', []))} کارت)")
        if not cols:
            lines.append("هنوز کالکشنی نیست.")
        await q.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ کالکشن جدید", callback_data="a_col_add")],
                [InlineKeyboardButton("🔙", callback_data="a_back")],
            ]),
        )
        return
    if cb == "a_col_add":
        set_state(c, "adm_col_name")
        await q.edit_message_text(
            "نام کالکشن را بفرست:\nمثال: مادارا",
            reply_markup=cancel_kb(),
        )
        return
    if cb == "a_set":
        await q.edit_message_text("تنظیمات", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("قالب", callback_data="a_tpl")], [InlineKeyboardButton("استارت", callback_data="a_smsg")], [InlineKeyboardButton("آستانه", callback_data="a_th")], [InlineKeyboardButton("🔙", callback_data="a_back")]])); return
    if cb == "a_tpl":
        set_state(c, "adm_tpl"); await q.edit_message_text("قالب:", reply_markup=cancel_kb()); return
    if cb == "a_smsg":
        set_state(c, "adm_smsg"); await q.edit_message_text("استارت:", reply_markup=cancel_kb()); return
    if cb == "a_th":
        set_state(c, "adm_th"); await q.edit_message_text(f"الان {d.get('msg_threshold')}:", reply_markup=cancel_kb()); return
    if cb == "a_adm":
        await q.edit_message_text("\n".join(map(str, d.get("admins", []))), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕", callback_data="a_adm_add")], [InlineKeyboardButton("🔙", callback_data="a_back")]])); return
    if cb == "a_adm_add":
        set_state(c, "adm_adm"); await q.edit_message_text("آیدی:", reply_markup=cancel_kb()); return
    if cb == "a_st":
        await q.edit_message_text(f"U{len(d['users'])} P{len(d['pool'])} S{len(d['shop'])} G{len(d['groups'])}", reply_markup=akb()); return
    if cb == "a_back":
        await q.edit_message_text("ادمین", reply_markup=akb()); return

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("force", cmd_force))
    app.add_handler(ChatMemberHandler(on_join, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(on_cb))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, on_photo))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, on_gmsg), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text), group=0)
    log.info("fixed bot up")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
