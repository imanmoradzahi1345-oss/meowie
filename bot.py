# ==================== بخش ۱ از ۶ ====================
import asyncio
import aiosqlite
import random
import time
from typing import Optional, Dict

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# ==================== تنظیمات ====================
BOT_TOKEN = "8971798729:AAGY8Hw8osbpHdglddpckGSnDUgIR8bywfw"
ADMIN_ID = 8918154552
DB_PATH = "meow_bot.db"

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# ==================== حالت‌ها ====================
class CasinoStates(StatesGroup):
    choosing_players = State()
    entering_bet = State()
    choosing_even_odd = State()
    waiting_dice = State()

class TransferStates(StatesGroup):
    confirming = State()

class AdminStates(StatesGroup):
    waiting_user = State()
    waiting_amount = State()
    waiting_level = State()
    waiting_cat_level = State()

class FactoryStates(StatesGroup):
    choosing_product = State()
    entering_amount = State()

class CatStates(StatesGroup):
    changing_name = State()

# ==================== داده‌های ثابت ====================
CAT_TYPES = [
    "گربه خیابانی", "گربه خانگی", "گربه پشمالو", "گربه سیامی",
    "گربه ایرانی", "گربه بنگال", "گربه مین‌کون", "گربه اسفینکس",
    "گربه نادر", "گربه افسانه‌ای"
]

FACTORY_PRODUCTS = {
    1: {"name": "پشمک", "cost": 5, "base_time": 2, "unlock": 1},
    2: {"name": "شکلات", "cost": 8, "base_time": 3, "unlock": 2},
    3: {"name": "آبنبات", "cost": 12, "base_time": 4, "unlock": 3},
    4: {"name": "کیک", "cost": 20, "base_time": 5, "unlock": 4},
    5: {"name": "بستنی", "cost": 30, "base_time": 6, "unlock": 5},
    6: {"name": "پیتزا", "cost": 50, "base_time": 8, "unlock": 6},
    7: {"name": "همبرگر", "cost": 80, "base_time": 10, "unlock": 7},
    8: {"name": "هواپیمای اسباب‌بازی", "cost": 150, "base_time": 15, "unlock": 8},
    9: {"name": "ماشین کنترلی", "cost": 250, "base_time": 20, "unlock": 9},
    10: {"name": "ربات میو", "cost": 500, "base_time": 30, "unlock": 10},
}

FISH_TYPES = [
    {"name": "ماهی کپور", "rarity": 1, "price": 15, "food": 5},
    {"name": "ماهی قزل‌آلا", "rarity": 2, "price": 35, "food": 12},
    {"name": "ماهی تن", "rarity": 3, "price": 60, "food": 20},
    {"name": "ماهی سالمون", "rarity": 4, "price": 100, "food": 35},
    {"name": "ماهی خاویار", "rarity": 5, "price": 180, "food": 55},
    {"name": "ماهی طلایی", "rarity": 6, "price": 300, "food": 80},
    {"name": "ماهی الماسی", "rarity": 7, "price": 500, "food": 120},
    {"name": "ماهی افسانه‌ای", "rarity": 8, "price": 900, "food": 200},
    {"name": "نهنگ کوچک", "rarity": 9, "price": 1500, "food": 350},
    {"name": "ماهی اژدها", "rarity": 10, "price": 3000, "food": 700},
]

# ==================== دیتابیس ====================
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                pocket INTEGER DEFAULT 1000,
                bank INTEGER DEFAULT 0,
                bank_account TEXT,
                meow_count INTEGER DEFAULT 0,
                meow_level INTEGER DEFAULT 1,
                last_meow REAL DEFAULT 0,
                cat_name TEXT DEFAULT 'پیشی',
                cat_level INTEGER DEFAULT 1,
                cat_points INTEGER DEFAULT 0,
                last_cat_collect REAL DEFAULT 0,
                factory_level INTEGER DEFAULT 1,
                factory_producing INTEGER DEFAULT 0,
                factory_end_time REAL DEFAULT 0,
                factory_amount INTEGER DEFAULT 0,
                factory_product_id INTEGER DEFAULT 0,
                fridge_level INTEGER DEFAULT 1,
                last_fish REAL DEFAULT 0,
                created_at REAL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS fridge_fish (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                fish_name TEXT,
                price INTEGER,
                food INTEGER
            )
        """)
        await db.commit()

async def get_user(user_id: int, username: str = None, full_name: str = None) -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                return dict(row)
            account = f"MEOW{user_id % 100000000:08d}"
            await db.execute(
                "INSERT INTO users (user_id, username, full_name, bank_account, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, full_name, account, time.time())
            )
            await db.commit()
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as c:
                return dict(await c.fetchone())

async def update_user(user_id: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [user_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {sets} WHERE user_id = ?", vals)
        await db.commit()

async def add_pocket(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET pocket = pocket + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

def format_num(n: int) -> str:
    if abs(n) >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if abs(n) >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)

def parse_amount(text: str) -> Optional[int]:
    t = text.lower().replace(",", "").replace(" ", "").replace("کا", "k").replace("ک", "k")
    if t.endswith("k"):
        try:
            return int(float(t[:-1]) * 1000)
        except:
            return None
    if t.endswith("m"):
        try:
            return int(float(t[:-1]) * 1_000_000)
        except:
            return None
    try:
        return int(t)
    except:
        return None

def get_meow_level(count: int) -> int:
    return max(1, count // 20 + 1)

def get_cat_type(level: int) -> str:
    return CAT_TYPES[min(level - 1, len(CAT_TYPES) - 1)]

def cat_rate(level: int) -> int:
    return 5 + level * 3# ==================== بخش ۲ از ۶ ====================

# ---------- میو / مع (هر ۳ دقیقه یک‌بار) ----------
@router.message(F.text.regexp(r"(?i)^(میو|مع)$"))
async def meow_handler(message: Message):
    user = await get_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    now = time.time()
    cooldown = 180

    if now - user["last_meow"] < cooldown:
        remain = int(cooldown - (now - user["last_meow"]))
        m, s = divmod(remain, 60)
        await message.reply(f"😿 میوت نمی‌آد!\nلطفاً صبر کنید تا {m} دقیقه و {s} ثانیه دیگر.")
        return

    amount = random.randint(50, 350)
    new_pocket = user["pocket"] + amount
    new_count = user["meow_count"] + 1
    new_level = get_meow_level(new_count)

    await update_user(
        message.from_user.id,
        pocket=new_pocket,
        meow_count=new_count,
        meow_level=new_level,
        last_meow=now
    )

    await message.reply(
        f"🐱 میو!\n"
        f"➕ {amount} میوپوینت به جیبتون اضافه شد\n"
        f"💰 موجودی جدید جیب: {format_num(new_pocket)}\n"
        f"📊 لول میو: {new_level} | تعداد میو: {new_count}"
    )

# ---------- پروفایل / میوهاش ----------
@router.message(F.text.regexp(r"(?i)^(پروفایل|میوهاش)$"))
async def profile_handler(message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    user = await get_user(target.id, target.username, target.full_name)

    text = (
        f"🐱 پروفایل میویی\n\n"
        f"👤 نام: {user['full_name'] or 'نامشخص'}\n"
        f"🐱 اسم گربه: {user['cat_name']}\n"
        f"💰 میوپوینت جیب: {format_num(user['pocket'])}\n"
        f"🏦 بانک: {format_num(user['bank'])}\n"
        f"📊 لول میو/مع: {user['meow_level']}\n"
        f"🔢 تعداد میو/مع: {user['meow_count']}\n"
        f"🐾 سطح گربه: {user['cat_level']} ({get_cat_type(user['cat_level'])})"
    )
    await message.reply(text)

@router.callback_query(F.data == "profile")
async def profile_cb(callback: CallbackQuery):
    user = await get_user(callback.from_user.id, callback.from_user.username, callback.from_user.full_name)
    text = (
        f"🐱 پروفایل میویی\n\n"
        f"👤 نام: {user['full_name'] or 'نامشخص'}\n"
        f"🐱 اسم گربه: {user['cat_name']}\n"
        f"💰 میوپوینت جیب: {format_num(user['pocket'])}\n"
        f"🏦 بانک: {format_num(user['bank'])}\n"
        f"📊 لول میو/مع: {user['meow_level']}\n"
        f"🔢 تعداد میو/مع: {user['meow_count']}\n"
        f"🐾 سطح گربه: {user['cat_level']} ({get_cat_type(user['cat_level'])})"
    )
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="main_menu")]
    ]))
    await callback.answer()

# ---------- پنل پیشی ----------
@router.message(F.text.regexp(r"(?i)^(پیشی|گربه)$"))
async def cat_panel_msg(message: Message):
    await show_cat_panel(message.from_user.id, message)

@router.callback_query(F.data == "cat_panel")
async def cat_panel_cb(callback: CallbackQuery):
    await show_cat_panel(callback.from_user.id, callback.message, edit=True)
    await callback.answer()

async def show_cat_panel(user_id: int, message: Message, edit: bool = False):
    user = await get_user(user_id)
    now = time.time()
    elapsed = now - user["last_cat_collect"]
    hours = elapsed / 3600
    produced = int(hours * cat_rate(user["cat_level"]))
    if produced > 0:
        await update_user(user_id, cat_points=user["cat_points"] + produced, last_cat_collect=now)
        user["cat_points"] += produced

    text = (
        f"🐱 پنل پیشی\n\n"
        f"📛 اسم: {user['cat_name']}\n"
        f"🐾 سطح: {user['cat_level']}\n"
        f"🧬 نوع: {get_cat_type(user['cat_level'])}\n"
        f"💎 میوپوینت تولیدشده: {format_num(user['cat_points'])}\n"
        f"⚡ نرخ تولید: {cat_rate(user['cat_level'])} در ساعت"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬆️ ارتقا سطح گربه", callback_data="cat_upgrade")],
        [InlineKeyboardButton(text="💰 برداشت میوپوینت", callback_data="cat_withdraw")],
        [InlineKeyboardButton(text="✏️ تغییر اسم گربه", callback_data="cat_rename")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="main_menu")]
    ])
    if edit:
        try:
            await message.edit_text(text, reply_markup=kb)
        except:
            await message.answer(text, reply_markup=kb)
    else:
        await message.reply(text, reply_markup=kb)

@router.callback_query(F.data == "cat_upgrade")
async def cat_upgrade(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    cost = user["cat_level"] * 500
    if user["pocket"] < cost:
        await callback.answer(f"موجودی کافی نیست! نیاز: {format_num(cost)}", show_alert=True)
        return
    await update_user(callback.from_user.id, pocket=user["pocket"] - cost, cat_level=user["cat_level"] + 1)
    await callback.answer("✅ سطح گربه ارتقا یافت!")
    await show_cat_panel(callback.from_user.id, callback.message, edit=True)

@router.callback_query(F.data == "cat_withdraw")
async def cat_withdraw(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if user["cat_points"] <= 0:
        await callback.answer("چیزی برای برداشت نیست!", show_alert=True)
        return
    points = user["cat_points"]
    await update_user(callback.from_user.id, pocket=user["pocket"] + points, cat_points=0)
    await callback.answer(f"✅ {format_num(points)} میوپوینت به جیب اضافه شد!")
    await show_cat_panel(callback.from_user.id, callback.message, edit=True)

@router.callback_query(F.data == "cat_rename")
async def cat_rename_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CatStates.changing_name)
    await callback.message.edit_text("✏️ اسم جدید پیشی را بنویسید:")
    await callback.answer()

@router.message(CatStates.changing_name)
async def cat_rename_finish(message: Message, state: FSMContext):
    name = message.text.strip()[:20]
    await update_user(message.from_user.id, cat_name=name)
    await state.clear()
    await message.reply(f"✅ اسم پیشی به «{name}» تغییر کرد!")
    await show_cat_panel(message.from_user.id, message)# ==================== بخش ۳ از ۶ ====================

@router.message(F.text.regexp(r"(?i)^کازینو$"))
async def casino_msg(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 اسلات", callback_data="casino_slot")],
        [InlineKeyboardButton(text="🎲 تاس", callback_data="casino_dice")],
        [InlineKeyboardButton(text="🎳 بولینگ", callback_data="casino_bowling")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="main_menu")]
    ])
    await message.reply("🎰 پنل کازینو\nیکی از بازی‌ها را انتخاب کنید:", reply_markup=kb)

@router.callback_query(F.data == "casino")
async def casino_cb(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 اسلات", callback_data="casino_slot")],
        [InlineKeyboardButton(text="🎲 تاس", callback_data="casino_dice")],
        [InlineKeyboardButton(text="🎳 بولینگ", callback_data="casino_bowling")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="main_menu")]
    ])
    await callback.message.edit_text("🎰 پنل کازینو\nیکی از بازی‌ها را انتخاب کنید:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.in_({"casino_slot", "casino_dice", "casino_bowling"}))
async def choose_players(callback: CallbackQuery, state: FSMContext):
    game = callback.data.split("_")[1]
    await state.update_data(game=game)

    if game == "bowling":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="۲ نفره", callback_data="players_2")],
            [InlineKeyboardButton(text="۳ نفره", callback_data="players_3")],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="casino")]
        ])
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="۱ نفره", callback_data="players_1")],
            [InlineKeyboardButton(text="۲ نفره", callback_data="players_2")],
            [InlineKeyboardButton(text="۳ نفره", callback_data="players_3")],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="casino")]
        ])
    await callback.message.edit_text("تعداد نفرات را انتخاب کنید:", reply_markup=kb)
    await state.set_state(CasinoStates.choosing_players)
    await callback.answer()

@router.callback_query(F.data.startswith("players_"), CasinoStates.choosing_players)
async def set_players(callback: CallbackQuery, state: FSMContext):
    players = int(callback.data.split("_")[1])
    await state.update_data(players=players)
    await state.set_state(CasinoStates.entering_bet)
    await callback.message.edit_text(
        "مبلغ شرط را وارد کنید (مثال: 1000 یا 5k یا 10کا)\n"
        "حداقل ۱۰۰ | حداکثر ۵۰۰٬۰۰۰"
    )
    await callback.answer()

@router.message(CasinoStates.entering_bet)
async def set_bet(message: Message, state: FSMContext):
    amount = parse_amount(message.text)
    if not amount or amount < 100 or amount > 500_000:
        await message.reply("❌ مبلغ نامعتبر! بین ۱۰۰ تا ۵۰۰کا وارد کنید.")
        return

    user = await get_user(message.from_user.id)
    if user["pocket"] < amount:
        await message.reply("❌ موجودی جیب کافی نیست!")
        await state.clear()
        return

    data = await state.get_data()
    game = data["game"]
    await state.update_data(bet=amount)

    if game == "dice":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔢 زوج", callback_data="even")],
            [InlineKeyboardButton(text="🔢 فرد", callback_data="odd")],
            [InlineKeyboardButton(text="🔙 انصراف", callback_data="casino")]
        ])
        await message.reply("زوج می‌آید یا فرد؟", reply_markup=kb)
        await state.set_state(CasinoStates.choosing_even_odd)
    else:
        await start_single_game(message, state, game, amount)

@router.callback_query(F.data.in_({"even", "odd"}), CasinoStates.choosing_even_odd)
async def dice_choice(callback: CallbackQuery, state: FSMContext):
    choice = callback.data
    data = await state.get_data()
    await state.update_data(even_odd=choice)
    await start_single_game(callback.message, state, "dice", data["bet"], choice, edit=True)
    await callback.answer()

async def start_single_game(message: Message, state: FSMContext, game: str, bet: int, even_odd: str = None, edit: bool = False):
    user_id = message.from_user.id if hasattr(message, "from_user") else message.chat.id
    user = await get_user(user_id)
    await update_user(user_id, pocket=user["pocket"] - bet)

    if game == "dice":
        text = f"🎲 لطفاً در جواب همین پیام 🎲 را بفرستید\n(حدس شما: {'زوج' if even_odd == 'even' else 'فرد'})"
        if edit:
            await message.edit_text(text)
        else:
            await message.reply(text)
        await state.set_state(CasinoStates.waiting_dice)
        await state.update_data(game="dice", bet=bet, even_odd=even_odd)

    elif game == "slot":
        msg = await message.answer_dice(emoji="🎰")
        await asyncio.sleep(2.5)
        value = msg.dice.value
        if value in (1, 22, 43):
            multi = 3.0
        elif value == 64:
            multi = 5.0
        elif value % 4 == 0:
            multi = 2.0
        elif value % 2 == 0:
            multi = 1.5
        else:
            multi = 0.5
        win = int(bet * multi)
        await add_pocket(user_id, win)
        await message.answer(f"🎰 نتیجه: {value}\nضریب: ×{multi}\n{format_num(win)} میوپوینت")
        await state.clear()

    elif game == "bowling":
        msg = await message.answer_dice(emoji="🎳")
        await asyncio.sleep(3)
        value = msg.dice.value
        if value >= 5:
            multi = 2.5
        elif value >= 3:
            multi = 1.5
        else:
            multi = 0.5
        win = int(bet * multi)
        await add_pocket(user_id, win)
        await message.answer(f"🎳 امتیاز: {value}\nضریب: ×{multi}\n{format_num(win)} میوپوینت")
        await state.clear()

@router.message(CasinoStates.waiting_dice, F.dice)
async def process_dice(message: Message, state: FSMContext):
    if message.dice.emoji != "🎲":
        await message.reply("لطفاً فقط 🎲 بفرستید!")
        return

    data = await state.get_data()
    value = message.dice.value
    is_odd = value % 2 == 1
    user_choice = data.get("even_odd")
    bet = data["bet"]

    correct = (user_choice == "odd" and is_odd) or (user_choice == "even" and not# ==================== بخش ۴ از ۶ ====================

def get_sell_price(name: str) -> int:
    hour = time.localtime().tm_hour
    base = {
        "پشمک": 8, "شکلات": 12, "آبنبات": 18, "کیک": 30, "بستنی": 45,
        "پیتزا": 75, "همبرگر": 120, "هواپیمای اسباب‌بازی": 220,
        "ماشین کنترلی": 380, "ربات میو": 750
    }
    price = base.get(name, 10)
    if 14 <= hour < 18:
        return int(price * 1.3)
    if 22 <= hour or hour < 6:
        return int(price * 0.8)
    return price

# ---------- کارخانه ----------
@router.message(F.text.regexp(r"(?i)^کارخانه$"))
async def factory_msg(message: Message):
    await show_factory(message.from_user.id, message)

@router.callback_query(F.data == "factory")
async def factory_cb(callback: CallbackQuery):
    await show_factory(callback.from_user.id, callback.message, edit=True)
    await callback.answer()

async def show_factory(user_id: int, message: Message, edit: bool = False):
    user = await get_user(user_id)
    now = time.time()

    if user["factory_producing"] and now >= user["factory_end_time"]:
        prod = FACTORY_PRODUCTS.get(user["factory_product_id"])
        if prod:
            profit = user["factory_amount"] * get_sell_price(prod["name"])
            await update_user(user_id,
                              pocket=user["pocket"] + profit,
                              factory_producing=0,
                              factory_amount=0,
                              factory_product_id=0)
            await message.answer(f"✅ تولید تمام شد! {format_num(profit)} میوپوینت به جیب اضافه شد.")

    status = "🟢 در حال تولید..." if user["factory_producing"] else "🔴 آماده تولید"
    text = f"🏭 پنل کارخانه\n\nسطح کارخانه: {user['factory_level']}\nوضعیت: {status}"

    buttons = [
        [InlineKeyboardButton(text="⬆️ ارتقا کارخانه", callback_data="factory_upgrade")],
        [InlineKeyboardButton(text="📦 شروع تولید", callback_data="factory_produce")],
        [InlineKeyboardButton(text="📋 لیست محصولات", callback_data="factory_list")],
    ]
    if user["factory_producing"]:
        buttons.append([InlineKeyboardButton(text="❌ لغو تولید", callback_data="factory_cancel")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="main_menu")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    if edit:
        try:
            await message.edit_text(text, reply_markup=kb)
        except:
            await message.answer(text, reply_markup=kb)
    else:
        await message.reply(text, reply_markup=kb)

@router.callback_query(F.data == "factory_upgrade")
async def factory_upgrade(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    cost = user["factory_level"] * 2000
    if user["pocket"] < cost:
        await callback.answer(f"موجودی کافی نیست! نیاز: {format_num(cost)}", show_alert=True)
        return
    await update_user(callback.from_user.id,
                      pocket=user["pocket"] - cost,
                      factory_level=user["factory_level"] + 1)
    await callback.answer("✅ کارخانه ارتقا یافت!")
    await show_factory(callback.from_user.id, callback.message, edit=True)

@router.callback_query(F.data == "factory_list")
async def factory_list(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    text = "📋 لیست محصولات کارخانه:\n\n"
    buttons = []
    for pid, prod in FACTORY_PRODUCTS.items():
        if user["factory_level"] >= prod["unlock"]:
            text += f"✅ {prod['name']} | هزینه: {prod['cost']} | زمان پایه: {prod['base_time']} ساعت\n"
            buttons.append([InlineKeyboardButton(
                text=f"تولید {prod['name']}",
                callback_data=f"produce_{pid}"
            )])
        else:
            text += f"🔒 {prod['name']} (نیاز به سطح {prod['unlock']})\n"
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="factory")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@router.callback_query(F.data.startswith("produce_"))
async def factory_start_produce(callback: CallbackQuery, state: FSMContext):
    pid = int(callback.data.split("_")[1])
    await state.update_data(product_id=pid)
    await state.set_state(FactoryStates.entering_amount)
    await callback.message.edit_text("تعداد تولید را وارد کنید (مثال: 10 یا 100):")
    await callback.answer()

@router.message(FactoryStates.entering_amount)
async def factory_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            raise ValueError
    except:
        await message.reply("❌ عدد معتبر وارد کنید.")
        return

    data = await state.get_data()
    pid = data["product_id"]
    prod = FACTORY_PRODUCTS[pid]
    user = await get_user(message.from_user.id)

    total_cost = amount * prod["cost"]
    if user["pocket"] < total_cost:
        await message.reply(f"❌ موجودی کافی نیست! نیاز: {format_num(total_cost)}")
        await state.clear()
        return

    # زمان ساخت (سطح کارخانه سرعت را بیشتر می‌کند)
    hours = max(1, prod["base_time"] - (user["factory_level"] // 3))
    end_time = time.time() + (hours * 3600)

    await update_user(message.from_user.id,
                      pocket=user["pocket"] - total_cost,
                      factory_producing=1,
                      factory_end_time=end_time,
                      factory_amount=amount,
                      factory_product_id=pid)
    await state.clear()
    await message.reply(
        f"✅ تولید شروع شد!\n"
        f"محصول: {prod['name']}\n"
        f"تعداد: {amount}\n"
        f"زمان تقریبی: {hours} ساعت\n"
        f"برای لغو از پنل کارخانه استفاده کنید."
    )

@router.callback_query(F.data == "factory_cancel")
async def factory_cancel(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user["factory_producing"]:
        await callback.answer("تولیدی در جریان نیست!", show_alert=True)
        return
    prod = FACTORY_PRODUCTS.get(user["factory_product_id"])
    refund = user["factory_amount"] * (prod["cost"] if prod else 5)
    await update_user(callback.from_user.id,
                      pocket=user["pocket"] + refund,
                      factory_producing=0,
                      factory_amount=0,
                      factory_product_id=0)
    await callback.answer("✅ تولید لغو شد و مبلغ اولیه برگشت!")
    await show_factory(callback.from_user.id, callback.message, edit=True)

@router.callback_query(F.data == "factory_produce")
async def factory_produce_btn(callback: CallbackQuery):
    await factory_list(callback)

# ---------- یخچال ----------
@router.message(F.text.regexp(r"(?i)^یخچال$"))
async def fridge_msg(message: Message):
    await show_fridge(message.from_user.id, message)

@router.callback_query(F.data == "fridge")
async def fridge_cb(callback: CallbackQuery):
    await show_fridge(callback.from_user.id, callback.message, edit=True)
    await callback.answer()

async def show_fridge(user_id: int, message: Message, edit: bool = False):
    user = await get_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM fridge_fish WHERE user_id = ?", (user_id,)) as cur:
            count = (await cur.fetchone())[0]

    capacity = 5 + (user["fridge_level"] * 3)
    text = (
        f"🧊 پنل یخچال\n\n"
        f"سطح یخچال: {user['fridge_level']}\n"
        f"ظرفیت: {count}/{capacity} ماهی"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬆️ ارتقا یخچال", callback_data="fridge_upgrade")],
        [InlineKeyboardButton(text="🐟 لیست ماهی‌ها", callback_data="fridge_list")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="main_menu")]
    ])
    if edit:
        try:
            await message.edit_text(text, reply_markup=kb)
        except:
            await message.answer(text, reply_markup=kb)
    else:
        await message.reply(text, reply_markup=kb)

@router.callback_query(F.data == "fridge_upgrade")
async def fridge_upgrade(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    cost = user["fridge_level"] * 1500
    if user["pocket"] < cost:
        await callback.answer(f"موجودی کافی نیست! نیاز: {format_num(cost)}", show_alert=True)
        return
    await update_user(callback.from_user.id,
                      pocket=user["pocket"] - cost,
                      fridge_level=user["fridge_level"] + 1)
    await callback.answer("✅ یخچال ارتقا یافت!")
    await show_fridge(callback.from_user.id, callback.message, edit=True)

@router.callback_query(F.data == "fridge_list")
async def fridge_list(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM fridge_fish WHERE user_id = ?", (user_id,)) as cur:
            rows = await cur.fetchall()

    if not rows:
        await callback.answer("یخچال خالی است!", show_alert=True)
        return

    buttons = []
    for row in rows:
        buttons.append([InlineKeyboardButton(
            text=f"{row['fish_name']} | {row['price']}💰",
            callback_data=f"fish_{row['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="fridge")])
    await callback.message.edit_text("🐟 ماهی‌های داخل یخچال:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@router.callback_query(F.data.startswith("fish_"))
async def fish_detail(callback: CallbackQuery):
    fish_id = int(callback.data.split("_")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM fridge_fish WHERE id = ?", (fish_id,)) as cur:
            fish = await cur.fetchone()
    if not fish or fish["user_id"] != callback.from_user.id:
        await callback.answer("ماهی پیدا نشد!", show_alert=True)
        return

    text = (
        f"🐟 {fish['fish_name']}\n"
        f"قیمت فروش: {fish['price']}\n"
        f"ارزش غذایی: {fish['food']}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 فروش", callback_data=f"sellfish_{fish_id}")],
        [InlineKeyboardButton(text="🐱 بده پیشی بخوره", callback_data=f"feedfish_{fish_id}")],
        [InlineKeyboardButton(text="🔙 بیرون رفتن", callback_data="fridge_list")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("sellfish_"))
async def sell_fish(callback: CallbackQuery):
    fish_id = int(callback.data.split("_")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM fridge_fish WHERE id = ?", (fish_id,)) as cur:
            fish = await cur.fetchone()
        if not fish or fish["user_id"] != callback.from_user.id:
            await callback.answer("خطا!", show_alert=True)
            return
        await db.execute("DELETE FROM fridge_fish WHERE id = ?", (fish_id,))
        await db.commit()
    await add_pocket(callback.from_user.id, fish["price"])
    await callback.answer(f"✅ فروخته شد! +{fish['price']}")
    await show_fridge(callback.from_user.id, callback.message, edit=True)

@router.callback_query(F.data.startswith("feedfish_"))
async def feed_fish(callback: CallbackQuery):
    fish_id = int(callback.data.split("_")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM fridge_fish WHERE id = ?", (fish_id,)) as cur:
            fish = await cur.fetchone()
        if not fish or fish["user_id"] != callback.from_user.id:
            await callback.answer("خطا!", show_alert=True)
            return
        await db.execute("DELETE FROM fridge_fish WHERE id = ?", (fish_id,))
        await db.commit()
    # ارزش غذایی به امتیاز گربه اضافه می‌شود
    user = await get_user(callback.from_user.id)
    await update_user(callback.from_user.id, cat_points=user["cat_points"] + fish["food"])
    await callback.answer(f"✅ پیشی خورد! +{fish['food']} امتیاز")
    await show_fridge(callback.from_user.id, callback.message, edit=True)

# ---------- ماهیگیری ----------
@router.message(F.text.regexp(r"(?i)^ماهی$"))
async def fish_catch(message: Message):
    user = await get_user(message.from_user.id)
    now = time.time()
    if now - user["last_fish"] < 1200:  # ۲۰ دقیقه
        remain = int(1200 - (now - user["last_fish"]))
        m, s = divmod(remain, 60)
        await message.reply(f"🎣 هنوز زود است!\nلطفاً {m} دقیقه و {s} ثانیه صبر کنید.")
        return

    wait_msg = await message.reply("🎣 لطفاً ۱۳ ثانیه صبر کنید...")
    await asyncio.sleep(13)

    # انتخاب ماهی بر اساس کمیابی
    weights = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
    fish = random.choices(FISH_TYPES, weights=weights, k=1)[0]

    text = (
        f"🐟 ماهی صید شد!\n\n"
        f"اسم: {fish['name']}\n"
        f"قیمت فروش: {fish['price']}\n"
        f"ارزش غذایی: {fish['food']}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 فروش فوری", callback_data=f"catchsell_{fish['name']}_{fish['price']}")],
        [InlineKeyboardButton(text="🧊 انتقال به یخچال", callback_data=f"catchstore_{fish['name']}_{fish['price']}_{fish['food']}")],
        [InlineKeyboardButton(text="🐱 بده پیشی بخوره", callback_data=f"catchfeed_{fish['food']}")]
    ])
    await wait_msg.edit_text(text, reply_markup=kb)
    await update_user(message.from_user.id, last_fish=now)

    # اگر ۶۰ ثانیه کاری نکرد، فرار کند
    await asyncio.sleep(60)
    try:
        await wait_msg.edit_text("🐟 ماهی فرار کرد!\nتا ماهیگیری بعدی ۲۰ دقیقه صبر کنید.")
    except:
        pass

@router.callback_query(F.data.startswith("catchsell_"))
async def catch_sell(callback: CallbackQuery):
    parts = callback.data.split("_")
    price = int(parts[2])
    await add_pocket(callback.from_user.id, price)
    await callback.message.edit_text(f"✅ فروخته شد! +{price} میوپوینت")
    await callback.answer()

@router.callback_query(F.data.startswith("catchstore_"))
async def catch_store(callback: CallbackQuery):
    parts = callback.data.split("_")
    name = parts[1]
    price = int(parts[2])
    food = int(parts[3])
    user = await get_user(callback.from_user.id)
    capacity = 5 + (user["fridge_level"] * 3)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM fridge_fish WHERE user_id = ?", (callback.from_user.id,)) as cur:
            count = (await cur.fetchone())[0]
        if count >= capacity:
            await callback.answer("یخچال پر است! اول ارتقا دهید.", show_alert=True)
            return
        await db.execute(
            "INSERT INTO fridge_fish (user_id, fish_name, price, food) VALUES (?, ?, ?, ?)",
            (callback.from_user.id, name, price, food)
        )
        await db.commit()
    await callback.message.edit_text(f"✅ {name} به یخچال منتقل شد!")
    await callback.answer()

@router.callback_query(F.data.startswith("catchfeed_"))
async def catch_feed(callback: CallbackQuery):
    food = int(callback.data.split("_")[1])
    user = await get_user(callback.from_user.id)
    await update_user(callback.from_user.id, cat_points=user["cat_points"] + food)
    await callback.message.edit_text(f"✅ پیشی ماهی را خورد! +{food} امتیاز")
    await callback.answer()# ==================== بخش ۵ از ۶ ====================

# ---------- بانک (سه دکمه شیشه‌ای) ----------
@router.message(F.text.regexp(r"(?i)^بانک$"))
async def bank_msg(message: Message):
    user = await get_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    text = (
        f"🏦 پنل بانک\n\n"
        f"شماره حساب شما: `{user['bank_account']}`\n"
        f"موجودی بانک: {format_num(user['bank'])}\n"
        f"موجودی جیب: {format_num(user['pocket'])}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 واریز به حساب بانکی", callback_data="bank_deposit")],
        [InlineKeyboardButton(text="📤 برداشت از حساب بانکی", callback_data="bank_withdraw")],
        [InlineKeyboardButton(text="🔄 انتقال بین بانکی", callback_data="bank_transfer")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="main_menu")]
    ])
    await message.reply(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "bank")
async def bank_cb(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    text = (
        f"🏦 پنل بانک\n\n"
        f"شماره حساب شما: `{user['bank_account']}`\n"
        f"موجودی بانک: {format_num(user['bank'])}\n"
        f"موجودی جیب: {format_num(user['pocket'])}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 واریز به حساب بانکی", callback_data="bank_deposit")],
        [InlineKeyboardButton(text="📤 برداشت از حساب بانکی", callback_data="bank_withdraw")],
        [InlineKeyboardButton(text="🔄 انتقال بین بانکی", callback_data="bank_transfer")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "bank_deposit")
async def bank_deposit_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TransferStates.confirming)
    await state.update_data(action="deposit")
    await callback.message.edit_text("مبلغ واریز به بانک را وارد کنید (مثال: 5k یا 10000):")
    await callback.answer()

@router.callback_query(F.data == "bank_withdraw")
async def bank_withdraw_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TransferStates.confirming)
    await state.update_data(action="withdraw")
    await callback.message.edit_text("مبلغ برداشت از بانک را وارد کنید (مثال: 5k یا 10000):")
    await callback.answer()

@router.callback_query(F.data == "bank_transfer")
async def bank_transfer_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TransferStates.confirming)
    await state.update_data(action="bank_transfer")
    await callback.message.edit_text(
        "شماره حساب مقصد و مبلغ را به این شکل بنویسید:\n"
        "`MEOW12345678 5000`\n"
        "یا\n"
        "`MEOW12345678 5k`"
    )
    await callback.answer()

@router.message(TransferStates.confirming)
async def bank_actions(message: Message, state: FSMContext):
    data = await state.get_data()
    action = data.get("action")

    if action == "deposit":
        amount = parse_amount(message.text)
        if not amount or amount <= 0:
            await message.reply("❌ مبلغ نامعتبر!")
            return
        user = await get_user(message.from_user.id)
        if user["pocket"] < amount:
            await message.reply("❌ موجودی جیب کافی نیست!")
            await state.clear()
            return
        await update_user(message.from_user.id,
                          pocket=user["pocket"] - amount,
                          bank=user["bank"] + amount)
        await message.reply(f"✅ {format_num(amount)} به حساب بانکی واریز شد.")
        await state.clear()

    elif action == "withdraw":
        amount = parse_amount(message.text)
        if not amount or amount <= 0:
            await message.reply("❌ مبلغ نامعتبر!")
            return
        user = await get_user(message.from_user.id)
        if user["bank"] < amount:
            await message.reply("❌ موجودی بانک کافی نیست!")
            await state.clear()
            return
        await update_user(message.from_user.id,
                          pocket=user["pocket"] + amount,
                          bank=user["bank"] - amount)
        await message.reply(f"✅ {format_num(amount)} از بانک برداشت شد.")
        await state.clear()

    elif action == "bank_transfer":
        parts = message.text.strip().split()
        if len(parts) < 2:
            await message.reply("❌ فرمت اشتباه! مثال: MEOW12345678 5k")
            return
        target_acc = parts[0].upper()
        amount = parse_amount(parts[1])
        if not amount or amount <= 0:
            await message.reply("❌ مبلغ نامعتبر!")
            return
        if amount > 500_000:
            await message.reply("❌ سقف انتقال ۵۰۰کا است!")
            return

        user = await get_user(message.from_user.id)
        if user["bank"] < amount:
            await message.reply("❌ موجودی بانک کافی نیست!")
            await state.clear()
            return

        # پیدا کردن صاحب حساب
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE bank_account = ?", (target_acc,)) as cur:
                target = await cur.fetchone()
        if not target:
            await message.reply("❌ شماره حساب پیدا نشد!")
            await state.clear()
            return
        if target["user_id"] == message.from_user.id:
            await message.reply("❌ نمی‌توانید به خودتان انتقال دهید!")
            await state.clear()
            return

        await update_user(message.from_user.id, bank=user["bank"] - amount)
        await update_user(target["user_id"], bank=target["bank"] + amount)
        await message.reply(f"✅ {format_num(amount)} به حساب {target_acc} منتقل شد.")
        await state.clear()

# ---------- انتقال میویی (ریپلای) ----------
@router.message(F.text.regexp(r"(?i)^انتقال میویی\s+(.+)$") & F.reply_to_message)
async def transfer_meow(message: Message, state: FSMContext):
    amount_text = message.text.split(maxsplit=2)[-1]
    amount = parse_amount(amount_text)
    if not amount or amount <= 0:
        await message.reply("❌ مبلغ نامعتبر!")
        return
    if amount > 500_000:
        await message.reply("❌ سقف انتقال میویی ۵۰۰کا است!")
        return

    target = message.reply_to_message.from_user
    if target.id == message.from_user.id:
        await message.reply("❌ نمی‌توانید به خودتان انتقال دهید!")
        return

    user = await get_user(message.from_user.id)
    if user["pocket"] < amount:
        await message.reply("❌ موجودی جیب کافی نیست!")
        return

    await state.update_data(
        transfer_amount=amount,
        transfer_to=target.id,
        transfer_name=target.full_name or target.username or str(target.id)
    )
    await state.set_state(TransferStates.confirming)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تایید", callback_data="transfer_yes")],
        [InlineKeyboardButton(text="❌ خیر", callback_data="transfer_no")]
    ])
    await message.reply(
        f"آیا از انتقال {format_num(amount)} میوپوینت به {target.full_name or target.username} مطمئن هستید؟",
        reply_markup=kb
    )

@router.callback_query(F.data == "transfer_yes")
async def transfer_yes(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount = data.get("transfer_amount")
    to_id = data.get("transfer_to")
    if not amount or not to_id:
        await callback.answer("خطا!", show_alert=True)
        await state.clear()
        return

    user = await get_user(callback.from_user.id)
    if user["pocket"] < amount:
        await callback.answer("موجودی کافی نیست!", show_alert=True)
        await state.clear()
        return

    await update_user(callback.from_user.id, pocket=user["pocket"] - amount)
    await add_pocket(to_id, amount)
    await callback.message.edit_text(f"✅ {format_num(amount)} میوپوینت با موفقیت منتقل شد.")
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "transfer_no")
async def transfer_no(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ انتقال لغو شد.")
    await callback.answer()# ==================== بخش ۶ از ۶ ====================

# ---------- پنل ادمین ----------
@router.message(F.text.regexp(r"(?i)^ادمین$") & F.from_user.id == ADMIN_ID)
async def admin_panel(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 دادن میوپوینت", callback_data="admin_give")],
        [InlineKeyboardButton(text="⬆️ افزایش لول میو", callback_data="admin_meow_level")],
        [InlineKeyboardButton(text="🐱 مکس کردن سطح گربه", callback_data="admin_cat_max")],
        [InlineKeyboardButton(text="⬆️ افزایش سطح گربه", callback_data="admin_cat_level")],
        [InlineKeyboardButton(text="🔙 بستن", callback_data="main_menu")]
    ])
    await message.reply("🛠 پنل ادمین\nیکی را انتخاب کنید:", reply_markup=kb)

@router.callback_query(F.data == "admin_give")
async def admin_give_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_user)
    await state.update_data(admin_action="give")
    await callback.message.edit_text("آیدی عددی کاربر را بفرستید:")
    await callback.answer()

@router.callback_query(F.data == "admin_meow_level")
async def admin_meow_level_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_user)
    await state.update_data(admin_action="meow_level")
    await callback.message.edit_text("آیدی عددی کاربر را بفرستید:")
    await callback.answer()

@router.callback_query(F.data == "admin_cat_max")
async def admin_cat_max(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_user)
    await state.update_data(admin_action="cat_max")
    await callback.message.edit_text("آیدی عددی کاربر را بفرستید:")
    await callback.answer()

@router.callback_query(F.data == "admin_cat_level")
async def admin_cat_level_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_user)
    await state.update_data(admin_action="cat_level")
    await callback.message.edit_text("آیدی عددی کاربر را بفرستید:")
    await callback.answer()

@router.message(AdminStates.waiting_user)
async def admin_get_user(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        uid = int(message.text.strip())
    except:
        await message.reply("❌ آیدی عددی معتبر وارد کنید.")
        return

    data = await state.get_data()
    action = data.get("admin_action")

    if action == "give":
        await state.update_data(target_id=uid)
        await state.set_state(AdminStates.waiting_amount)
        await message.reply("مقدار میوپوینت را وارد کنید:")
    elif action == "meow_level":
        await state.update_data(target_id=uid)
        await state.set_state(AdminStates.waiting_level)
        await message.reply("لول میو جدید را وارد کنید:")
    elif action == "cat_max":
        await update_user(uid, cat_level=10)
        await message.reply(f"✅ سطح گربه کاربر {uid} به ۱۰ (مکس) رسید.")
        await state.clear()
    elif action == "cat_level":
        await state.update_data(target_id=uid)
        await state.set_state(AdminStates.waiting_cat_level)
        await message.reply("سطح گربه جدید را وارد کنید (۱ تا ۱۰):")

@router.message(AdminStates.waiting_amount)
async def admin_give_amount(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    amount = parse_amount(message.text)
    if not amount:
        await message.reply("❌ مقدار نامعتبر!")
        return
    data = await state.get_data()
    uid = data["target_id"]
    await add_pocket(uid, amount)
    await message.reply(f"✅ {format_num(amount)} میوپوینت به کاربر {uid} داده شد.")
    await state.clear()

@router.message(AdminStates.waiting_level)
async def admin_set_meow_level(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        level = int(message.text.strip())
    except:
        await message.reply("❌ عدد معتبر وارد کنید.")
        return
    data = await state.get_data()
    uid = data["target_id"]
    await update_user(uid, meow_level=level)
    await message.reply(f"✅ لول میو کاربر {uid} به {level} تغییر کرد.")
    await state.clear()

@router.message(AdminStates.waiting_cat_level)
async def admin_set_cat_level(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        level = int(message.text.strip())
        if level < 1 or level > 10:
            raise ValueError
    except:
        await message.reply("❌ سطح باید بین ۱ تا ۱۰ باشد.")
        return
    data = await state.get_data()
    uid = data["target_id"]
    await update_user(uid, cat_level=level)
    await message.reply(f"✅ سطح گربه کاربر {uid} به {level} تغییر کرد.")
    await state.clear()

# ---------- منوی اصلی و بازگشت ----------
@router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🐱 پروفایل", callback_data="profile"),
         InlineKeyboardButton(text="🐱 پیشی", callback_data="cat_panel")],
        [InlineKeyboardButton(text="🏭 کارخانه", callback_data="factory"),
         InlineKeyboardButton(text="🧊 یخچال", callback_data="fridge")],
        [InlineKeyboardButton(text="🎰 کازینو", callback_data="casino"),
         InlineKeyboardButton(text="🏦 بانک", callback_data="bank")],
    ])
    await callback.message.edit_text("🐱 منوی اصلی ربات میو:", reply_markup=kb)
    await callback.answer()

@router.message(CommandStart())
async def start_cmd(message: Message):
    await get_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🐱 پروفایل", callback_data="profile"),
         InlineKeyboardButton(text="🐱 پیشی", callback_data="cat_panel")],
        [InlineKeyboardButton(text="🏭 کارخانه", callback_data="factory"),
         InlineKeyboardButton(text="🧊 یخچال", callback_data="fridge")],
        [InlineKeyboardButton(text="🎰 کازینو", callback_data="casino"),
         InlineKeyboardButton(text="🏦 بانک", callback_data="bank")],
    ])
    await message.reply(
        "سلام! به ربات میو خوش آمدید 🐱\n\n"
        "دستورات اصلی:\n"
        "• میو یا مع\n"
        "• پروفایل یا میوهاش\n"
        "• پیشی یا گربه\n"
        "• کازینو\n"
        "• کارخانه\n"
        "• یخچال\n"
        "• بانک\n"
        "• ماهی\n"
        "• انتقال میویی (با ریپلای)\n\n"
        "از دکمه‌های زیر هم می‌توانید استفاده کنید:",
        reply_markup=kb
    )

# ---------- اجرای ربات ----------
async def main():
    await init_db()
    print("ربات میو شروع به کار کرد...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
