# ==============================================================================
# 📄 bot.py - PART 1/8: COMPLETE CONFIGURATION, ENUMS & DATABASE MODELS
# ==============================================================================

import os
import sys
import math
import json
import random
import logging
import asyncio
from datetime import datetime, timedelta
from enum import Enum as PyEnum
from typing import Optional, List, Dict, Any, Union, Callable, Awaitable

from aiogram import Bot, Dispatcher, Router, F, BaseMiddleware
from aiogram.types import (
    Message, CallbackQuery, TelegramObject, User as TgUser,
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from sqlalchemy import (
    Column, BigInteger, String, Integer, Float, DateTime, ForeignKey,
    Boolean, Text, Enum as SQLEnum, select, update, delete, func, and_, or_
)
from sqlalchemy.orm import declarative_base, relationship, selectinload
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# ------------------------------------------------------------------------------
# ⚙️ تنظیمات اصلی و متغیرهای محیطی
# ------------------------------------------------------------------------------
BOT_TOKEN = "8378922493:AAGOzhaN3eUcE53Yz49bo5UMR1rrI-MiRlM"
ADMIN_IDS = [7530457395]
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///zombie_survival_v2.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ZombieSurvivalEngine")

Base = declarative_base()
engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


# ------------------------------------------------------------------------------
# 📊 ENUMها و ساختارهای داده
# ------------------------------------------------------------------------------
class ItemType(str, PyEnum):
    WEAPON = "WEAPON"
    ARMOR = "ARMOR"
    FOOD = "FOOD"
    DRINK = "DRINK"
    MEDICINE = "MEDICINE"
    MATERIAL = "MATERIAL"
    AMMO = "AMMO"
    SPECIAL = "SPECIAL"


class Rarity(str, PyEnum):
    COMMON = "عادی"
    UNCOMMON = "غیرعادی"
    RARE = "کمیاب"
    EPIC = "حماسی"
    LEGENDARY = "افسانه‌ای"


class DangerLevel(str, PyEnum):
    SAFE = "🟢 امن"
    LOW = "🟡 کم‌خطر"
    MEDIUM = "🟠 خطر متوسط"
    HIGH = "🔴 پرخطر"
    DEADLY = "💀 مرگبار"


class QuestType(str, PyEnum):
    KILL_ZOMBIES = "KILL_ZOMBIES"
    SCAVENGE = "SCAVENGE"
    CRAFT = "CRAFT"
    UPGRADE_SHELTER = "UPGRADE_SHELTER"


class ClanRole(str, PyEnum):
    LEADER = "رهبر"
    OFFICER = "ارشد"
    MEMBER = "عضو"


# ------------------------------------------------------------------------------
# 🗄️ مدل‌های دیتابیس (DATABASE MODELS)
# ------------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(64), nullable=True)
    display_name = Column(String(64), nullable=False)

    # علائم حیاتی و سلامت
    hp = Column(Integer, default=100)
    max_hp = Column(Integer, default=100)
    hunger = Column(Integer, default=100)
    thirst = Column(Integer, default=100)
    energy = Column(Integer, default=100)
    sanity = Column(Integer, default=100)
    infection = Column(Integer, default=0)
    radiation = Column(Integer, default=0)

    # اقتصاد، سطح و آمار
    scrap = Column(Integer, default=250)
    gold = Column(Integer, default=10)
    level = Column(Integer, default=1)
    xp = Column(Integer, default=0)
    zombie_kills = Column(Integer, default=0)
    boss_kills = Column(Integer, default=0)
    deaths = Column(Integer, default=0)
    successful_scavenges = Column(Integer, default=0)

    # کلن و پناهگاه
    clan_id = Column(Integer, ForeignKey("clans.id", ondelete="SET NULL"), nullable=True)
    clan_role = Column(String(20), default=ClanRole.MEMBER.value)

    # زمان‌بندی‌ها
    last_active = Column(DateTime, default=datetime.utcnow)
    last_scavenge = Column(DateTime, default=datetime.utcnow)
    last_daily = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # روابط
    inventory = relationship("Inventory", back_populates="user", cascade="all, delete-orphan")
    shelter = relationship("Shelter", back_populates="user", uselist=False, cascade="all, delete-orphan")
    user_quests = relationship("UserQuest", back_populates="user", cascade="all, delete-orphan")
    clan = relationship("Clan", back_populates="members")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False)
    description = Column(Text, nullable=False)
    item_type = Column(String(32), nullable=False)
    rarity = Column(String(32), default=Rarity.COMMON.value)

    # ویژگی‌های رزمی و مصرفی
    attack_power = Column(Integer, default=0)
    defense_power = Column(Integer, default=0)
    heal_hp = Column(Integer, default=0)
    restore_hunger = Column(Integer, default=0)
    restore_thirst = Column(Integer, default=0)
    restore_energy = Column(Integer, default=0)
    reduce_infection = Column(Integer, default=0)

    # ارزش مالی
    buy_price = Column(Integer, default=10)
    sell_price = Column(Integer, default=5)


class Inventory(Base):
    __tablename__ = "inventories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, default=1)
    is_equipped = Column(Boolean, default=False)

    user = relationship("User", back_populates="inventory")
    item = relationship("Item")


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    description = Column(Text, nullable=False)
    danger_level = Column(String(32), default=DangerLevel.LOW.value)
    min_level = Column(Integer, default=1)
    energy_cost = Column(Integer, default=15)
    scrap_multiplier = Column(Float, default=1.0)


class Zombie(Base):
    __tablename__ = "zombies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    hp = Column(Integer, default=50)
    max_hp = Column(Integer, default=50)
    attack = Column(Integer, default=10)
    defense = Column(Integer, default=2)
    xp_reward = Column(Integer, default=20)
    scrap_reward = Column(Integer, default=30)
    is_boss = Column(Boolean, default=False)


class Shelter(Base):
    __tablename__ = "shelters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    level = Column(Integer, default=1)
    defense = Column(Integer, default=50)
    water_collector_level = Column(Integer, default=0)
    food_farm_level = Column(Integer, default=0)
    medical_lab_level = Column(Integer, default=0)
    last_harvest = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="shelter")


class Quest(Base):
    __tablename__ = "quests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(128), nullable=False)
    description = Column(Text, nullable=False)
    quest_type = Column(String(32), nullable=False)
    target_amount = Column(Integer, default=1)
    reward_scrap = Column(Integer, default=100)
    reward_xp = Column(Integer, default=50)


class UserQuest(Base):
    __tablename__ = "user_quests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    quest_id = Column(Integer, ForeignKey("quests.id", ondelete="CASCADE"), nullable=False)
    current_amount = Column(Integer, default=0)
    completed = Column(Boolean, default=False)
    reward_claimed = Column(Boolean, default=False)

    user = relationship("User", back_populates="user_quests")
    quest = relationship("Quest")


class Clan(Base):
    __tablename__ = "clans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False)
    tag = Column(String(10), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    leader_id = Column(BigInteger, nullable=False)
    level = Column(Integer, default=1)
    treasury_scrap = Column(Integer, default=0)
    max_members = Column(Integer, default=10)
    created_at = Column(DateTime, default=datetime.utcnow)

    members = relationship("User", back_populates="clan")
    # ==============================================================================
# 📄 bot.py - PART 2/8: FSM STATES, KEYBOARDS & MIDDLEWARES
# ==============================================================================

# ------------------------------------------------------------------------------
# 🌀 FSM STATES (حالت‌های گفتگو)
# ------------------------------------------------------------------------------
class AdminStates(StatesGroup):
    waiting_for_broadcast_text = State()
    waiting_for_user_id_reward = State()
    waiting_for_reward_amount = State()

class ClanStates(StatesGroup):
    waiting_for_clan_name = State()
    waiting_for_clan_tag = State()
    waiting_for_clan_description = State()

class TradeStates(StatesGroup):
    waiting_for_trade_user = State()
    waiting_for_trade_item = State()

# ------------------------------------------------------------------------------
# ⌨️ KEYBOARDS (کیبوردهای کامل ربات)
# ------------------------------------------------------------------------------
def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="👤 پروفایل"), KeyboardButton(text="🗺️ کاوش و مناطق")],
        [KeyboardButton(text="🎒 کوله‌پشتی"), KeyboardButton(text="⚔️ مبارزه و شکار")],
        [KeyboardButton(text="🏠 پناهگاه"), KeyboardButton(text="🛠️ ساخت و ساز")],
        [KeyboardButton(text="📜 مأموریت‌ها"), KeyboardButton(text="👥 کلن و اتحاد")],
        [KeyboardButton(text="🛒 فروشگاه"), KeyboardButton(text="📖 راهنما و پشتیبانی")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_combat_keyboard(zombie_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚔️ حمله مستقیم", callback_data=f"combat:attack:{zombie_id}"),
                InlineKeyboardButton(text="🛡️ دفاع و سنگر", callback_data=f"combat:defend:{zombie_id}")
            ],
            [
                InlineKeyboardButton(text="🧪 مصرف دارو", callback_data=f"combat:heal:{zombie_id}"),
                InlineKeyboardButton(text="🏃 فرار تاکتیکی", callback_data=f"combat:flee:{zombie_id}")
            ]
        ]
    )

def get_inventory_keyboard(item_id: int, is_equipped: bool, item_type: str) -> InlineKeyboardMarkup:
    buttons = []
    if item_type in ["WEAPON", "ARMOR"]:
        if is_equipped:
            buttons.append([InlineKeyboardButton(text="🔻 خارج کردن تجهیزات", callback_data=f"inv:unequip:{item_id}")])
        else:
            buttons.append([InlineKeyboardButton(text="🛡️ تجهیز کردن", callback_data=f"inv:equip:{item_id}")])
    elif item_type in ["FOOD", "DRINK", "MEDICINE"]:
        buttons.append([InlineKeyboardButton(text="🧪 مصرف / استفاده", callback_data=f"inv:use:{item_id}")])
    
    buttons.append([
        InlineKeyboardButton(text="💰 فروش", callback_data=f"inv:sell:{item_id}"),
        InlineKeyboardButton(text="🗑️ دور انداختن", callback_data=f"inv:drop:{item_id}")
    ])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به کوله", callback_data="inv:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_locations_keyboard(locations: list) -> InlineKeyboardMarkup:
    buttons = []
    for loc in locations:
        buttons.append([
            InlineKeyboardButton(
                text=f"{loc.name} ({loc.danger_level}) - مصرف انرژی: {loc.energy_cost}",
                callback_data=f"loc:select:{loc.id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به منو", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_shelter_keyboard(shelter) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬆️ ارتقای کلی پناهگاه", callback_data="shelter:upgrade_main")],
            [
                InlineKeyboardButton(text="💧 تصفیه آب", callback_data="shelter:upgrade_water"),
                InlineKeyboardButton(text="🌾 مزرعه غذا", callback_data="shelter:upgrade_food")
            ],
            [
                InlineKeyboardButton(text="🏥 آزمایشگاه پزشکی", callback_data="shelter:upgrade_med"),
                InlineKeyboardButton(text="🌾/💧 برداشت محصولات", callback_data="shelter:harvest")
            ],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="menu:main")]
        ]
    )

def get_clan_keyboard(in_clan: bool, is_leader: bool = False) -> InlineKeyboardMarkup:
    if not in_clan:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="➕ ساخت کلن جدید", callback_data="clan:create")],
                [InlineKeyboardButton(text="📜 لیست کلن‌ها", callback_data="clan:list")]
            ]
        )
    buttons = [
        [
            InlineKeyboardButton(text="👥 اعضای کلن", callback_data="clan:members"),
            InlineKeyboardButton(text="💰 خزانه کلن", callback_data="clan:treasury")
        ]
    ]
    if is_leader:
        buttons.append([InlineKeyboardButton(text="⚙️ مدیریت و ارتقا کلن", callback_data="clan:manage")])
    buttons.append([InlineKeyboardButton(text="🚪 خروج از کلن", callback_data="clan:leave")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 آمار سرور", callback_data="admin:stats"),
                InlineKeyboardButton(text="📢 پیام همگانی", callback_data="admin:broadcast")
            ],
            [
                InlineKeyboardButton(text="🎁 اعطای پاداش به کاربر", callback_data="admin:reward"),
                InlineKeyboardButton(text="🔄 بازنشانی دیتابیس", callback_data="admin:reset_db")
            ]
        ]
    )

# ------------------------------------------------------------------------------
# ⚙️ MIDDLEWARES (میدل‌ورهای خط لوله)
# ------------------------------------------------------------------------------
class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        async with AsyncSessionLocal() as session:
            data["db"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise

class UserTrackerMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        event_user: Optional[TgUser] = data.get("event_from_user")
        db: Optional[AsyncSession] = data.get("db")

        if event_user and db and not event_user.is_bot:
            stmt = select(User).where(User.telegram_id == event_user.id)
            res = await db.execute(stmt)
            user = res.scalar_one_or_none()

            if user:
                user.last_active = datetime.utcnow()
                if event_user.username != user.username:
                    user.username = event_user.username
                data["db_user"] = user
            else:
                data["db_user"] = None

        return await handler(event, data)

class AdminMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        event_user: Optional[TgUser] = data.get("event_from_user")
        if event_user and event_user.id in ADMIN_IDS:
            data["is_admin"] = True
        else:
            data["is_admin"] = False
        return await handler(event, data)
    # ==============================================================================
# 📄 bot.py - PART 3/8: SEED DATA & ENGINE HELPERS
# ==============================================================================

async def seed_initial_game_data(db: AsyncSession):
    """ثبت اولیه تمامی آیتم‌ها، مناطق و زامبی‌ها در صورت خالی بودن دیتابیس"""
    loc_check = await db.execute(select(func.count(Location.id)))
    if loc_check.scalar() == 0:
        locations = [
            Location(name="🏙️ خیابان‌های متروکه", description="منطقه‌ای خلوت اما دارای اسکرپ معمولی.", danger_level=DangerLevel.LOW.value, min_level=1, energy_cost=10, scrap_multiplier=1.0),
            Location(name="🏬 مرکز خرید ویران‌شده", description="دارای کنسرو و تجهیزات اولیه.", danger_level=DangerLevel.MEDIUM.value, min_level=2, energy_cost=15, scrap_multiplier=1.5),
            Location(name="🏥 بیمارستان آلوده", description="محل کپسول‌های دارویی و زامبی‌های جهش‌یافته.", danger_level=DangerLevel.HIGH.value, min_level=4, energy_cost=20, scrap_multiplier=2.2),
            Location(name="☣️ نیروگاه هسته‌ای خاموش", description="خطر پرتو زایی و زامبی‌های غول‌پیکر با غنایم افسانه‌ای.", danger_level=DangerLevel.DEADLY.value, min_level=7, energy_cost=30, scrap_multiplier=4.0),
        ]
        db.add_all(locations)

    items_check = await db.execute(select(func.count(Item.id)))
    if items_check.scalar() == 0:
        items = [
            Item(name="🔪 چاقوی شکاری", description="سلاح سرد ساده اما کارآمد.", item_type=ItemType.WEAPON.value, rarity=Rarity.COMMON.value, attack_power=15, buy_price=50, sell_price=20),
            Item(name="🪓 تبر آتش‌نشانی", description="سلاحی قدرتمند برای شکستن استخوان زامبی.", item_type=ItemType.WEAPON.value, rarity=Rarity.UNCOMMON.value, attack_power=35, buy_price=150, sell_price=70),
            Item(name="🔫 کلت ۹ میلی‌متری", description="سلاح گرم با قدرت تخریب بالا.", item_type=ItemType.WEAPON.value, rarity=Rarity.RARE.value, attack_power=60, buy_price=400, sell_price=200),
            Item(name="🥫 کنسرو لوبیا", description="غذا برای رفع گرسنگی.", item_type=ItemType.FOOD.value, restore_hunger=35, restore_hp=10, buy_price=30, sell_price=10),
            Item(name="🧃 بطری آب معدنی", description="رفع کامل تشنگی.", item_type=ItemType.DRINK.value, restore_thirst=40, buy_price=20, sell_price=5),
            Item(name="🧪 باند و پنس ضدعفونی", description="کاهش عفونت و ترمیم جان.", item_type=ItemType.MEDICINE.value, heal_hp=45, reduce_infection=25, buy_price=80, sell_price=35),
            Item(name="🛡️ جلیقه ضدگلوله", description="کاهش آسیب دریافتی.", item_type=ItemType.ARMOR.value, rarity=Rarity.UNCOMMON.value, defense_power=20, buy_price=200, sell_price=90)
        ]
        db.add_all(items)

    zombie_check = await db.execute(select(func.count(Zombie.id)))
    if zombie_check.scalar() == 0:
        zombies = [
            Zombie(name="🧟 زامبی کندرو", hp=40, max_hp=40, attack=8, defense=2, xp_reward=15, scrap_reward=25, is_boss=False),
            Zombie(name="🏃 زامبی سریع (Runner)", hp=60, max_hp=60, attack=18, defense=5, xp_reward=35, scrap_reward=50, is_boss=False),
            Zombie(name="🤮 زامبی اسیدی (Spitter)", hp=85, max_hp=85, attack=28, defense=8, xp_reward=60, scrap_reward=90, is_boss=False),
            Zombie(name="🧌 زامبی غول‌پیکر (Tank Boss)", hp=300, max_hp=300, attack=55, defense=20, xp_reward=250, scrap_reward=500, is_boss=True)
        ]
        db.add_all(zombies)

    await db.commit()

def check_level_up(user: User) -> bool:
    """بررسی و اعمال ارتقای سطح کاربر"""
    required_xp = user.level * 100
    if user.xp >= required_xp:
        user.level += 1
        user.xp -= required_xp
        user.max_hp += 15
        user.hp = user.max_hp
        return True
    return False

async def get_user_total_stats(db: AsyncSession, user_id: int) -> dict:
    """محاسبه مجموع قدرت حمله و دفاع تجهیزات کاربر"""
    stmt = select(Inventory).options(selectinload(Inventory.item)).where(
        Inventory.user_id == user_id,
        Inventory.is_equipped == True
    )
    res = await db.execute(stmt)
    equipped_items = res.scalars().all()

    total_attack = 10  # قدرت پایه
    total_defense = 0  # دفاع پایه

    for inv in equipped_items:
        if inv.item:
            total_attack += inv.item.attack_power
            total_defense += inv.item.defense_power

    return {"attack": total_attack, "defense": total_defense}
        # ==============================================================================
# 📄 bot.py - PART 4/8: BASE COMMANDS, PROFILE SYSTEM & DAILY REWARDS
# ==============================================================================

main_router = Router()

# ------------------------------------------------------------------------------
# 🚀 دستور START و ثبت‌نام اولیه
# ------------------------------------------------------------------------------
@main_router.message(CommandStart())
async def cmd_start(message: Message, db: AsyncSession, db_user: Optional[User]):
    tg_user = message.from_user
    
    if not db_user:
        # ایجاد کاربر جدید
        display_name = tg_user.full_name or tg_user.username or f"بازمانده_{tg_user.id % 10000}"
        db_user = User(
            telegram_id=tg_user.id,
            username=tg_user.username,
            display_name=display_name
        )
        db.add(db_user)
        await db.flush()

        # ایجاد پناهگاه اولیه برای کاربر
        shelter = Shelter(user_id=db_user.id)
        db.add(shelter)
        await db.commit()

        welcome_text = (
            f"🧟 **به دنیای پسارستاخیزی زامبی خوش آمدی، {display_name}!**\n\n"
            "شهر به ویرانه تبدیل شده و زامبی‌ها همه‌جا را گرفته‌اند.\n"
            "برای زنده ماندن باید منابع جمع کنی، پناهگاهت را ارتقا دهی و با تهدیدات مبارزه کنی.\n\n"
            "🎮 **از منوی زیر برای شروع استفاده کن:**"
        )
    else:
        welcome_text = f"سلام مجدد {db_user.display_name}! آماده‌ای برای ادامه نبرد با زامبی‌ها؟"

    await message.answer(welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")


# ------------------------------------------------------------------------------
# 👤 نمایش پروفایل و آمار بازمانده
# ------------------------------------------------------------------------------
@main_router.message(F.text == "👤 پروفایل")
async def show_profile(message: Message, db: AsyncSession, db_user: User):
    if not db_user:
        await message.answer("لطفاً ابتدا /start را بزنید.")
        return

    # دریافت قدرت تجهیزات
    stats = await get_user_total_stats(db, db_user.id)
    
    # دریافت نام کلن در صورت عضویت
    clan_name = "بدون کلن"
    if db_user.clan_id:
        stmt = select(Clan.name).where(Clan.id == db_user.clan_id)
        res = await db.execute(stmt)
        clan_name = res.scalar() or "بدون کلن"

    profile_text = (
        f"📊 **پروفایل بازمانده:** `{db_user.display_name}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎖️ **سطح:** `{db_user.level}` | **XP:** `{db_user.xp}/{db_user.level * 100}`\n"
        f"❤️ **سلامتی (HP):** `{db_user.hp}/{db_user.max_hp}`\n"
        f"🍖 **گرسنگی:** `{db_user.hunger}/100` | 💧 **تشنگی:** `{db_user.thirst}/100`\n"
        f"⚡ **انرژی:** `{db_user.energy}/100` | ☣️ **عفونت:** `{db_user.infection}%`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚔️ **قدرت حمله کل:** `{stats['attack']}`\n"
        f"🛡️ **قدرت دفاع کل:** `{stats['defense']}`\n"
        f"⚙️ **قطعات فلزی (Scrap):** `{db_user.scrap}` | 🪙 **طلا:** `{db_user.gold}`\n"
        f"👥 **کلن:** `{clan_name}` | **نقش:** `{db_user.clan_role}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💀 **زامبی‌های کشته‌شده:** `{db_user.zombie_kills}`\n"
        f"🏰 **رؤسای نابودشده:** `{db_user.boss_kills}`\n"
        f"🗺️ **کاوش‌های موفق:** `{db_user.successful_scavenges}`\n"
    )

    await message.answer(profile_text, parse_mode="Markdown")


# ------------------------------------------------------------------------------
# 🎁 پاداش روزانه (DAILY REWARD)
# ------------------------------------------------------------------------------
@main_router.message(Command("daily"))
@main_router.message(F.text == "🎁 پاداش روزانه")
async def claim_daily_reward(message: Message, db: AsyncSession, db_user: User):
    if not db_user:
        return

    now = datetime.utcnow()
    if db_user.last_daily and (now - db_user.last_daily) < timedelta(hours=24):
        remaining = timedelta(hours=24) - (now - db_user.last_daily)
        hours, remainder = divmod(remaining.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        await message.answer(
            f"⏳ شما قبلاً پاداش روزانه را دریافت کرده‌اید!\n"
            f"زمان باقی‌مانده تا دریافت بعدی: **{hours} ساعت و {minutes} دقیقه**",
            parse_mode="Markdown"
        )
        return

    scrap_reward = random.randint(100, 250) * db_user.level
    xp_reward = 50 * db_user.level

    db_user.scrap += scrap_reward
    db_user.xp += xp_reward
    db_user.last_daily = now

    leveled_up = check_level_up(db_user)
    
    msg = (
        f"🎉 **پاداش روزانه دریافت شد!**\n\n"
        f"⚙️ **+{scrap_reward}** قطعه فلزی\n"
        f"⭐ **+{xp_reward}** امتیاز XP\n"
    )
    if leveled_up:
        msg += f"\n🎊 **تبریک! شما به سطح {db_user.level} ارتقا یافتید!**"

    await message.answer(msg, parse_mode="Markdown")
    # ==============================================================================
# 📄 bot.py - PART 5/8: INVENTORY SYSTEM & SCAVENGING LOCATIONS
# ==============================================================================

# ------------------------------------------------------------------------------
# 🎒 نمایش و مدیریت کوله‌پشتی
# ------------------------------------------------------------------------------
@main_router.message(F.text == "🎒 کوله‌پشتی")
async def show_inventory(message: Message, db: AsyncSession, db_user: User):
    if not db_user:
        return

    stmt = select(Inventory).options(selectinload(Inventory.item)).where(
        Inventory.user_id == db_user.id,
        Inventory.quantity > 0
    )
    res = await db.execute(stmt)
    inv_items = res.scalars().all()

    if not inv_items:
        await message.answer("🎒 **کوله‌پشتی شما خالی است!**\nبه کاوش بروید تا منابع و سلاح پیدا کنید.", parse_mode="Markdown")
        return

    text = "🎒 **محتویات کوله‌پشتی شما:**\n━━━━━━━━━━━━━━━━━━━━\n"
    buttons = []

    for inv in inv_items:
        item = inv.item
        equipped_status = " [equipped]" if inv.is_equipped else ""
        text += f"🔹 **{item.name}** ×{inv.quantity}{equipped_status}\n"
        text += f"   └ نوع: {item.item_type} | نادری: {item.rarity}\n"
        
        buttons.append([
            InlineKeyboardButton(
                text=f"{'🔻' if inv.is_equipped else '⚔️'} {item.name} ({inv.quantity})",
                callback_data=f"inv:detail:{inv.id}"
            )
        ])

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")


@main_router.callback_query(F.data.startswith("inv:detail:"))
async def inventory_item_detail(callback: CallbackQuery, db: AsyncSession, db_user: User):
    inv_id = int(callback.data.split(":")[2])
    stmt = select(Inventory).options(selectinload(Inventory.item)).where(Inventory.id == inv_id)
    res = await db.execute(stmt)
    inv = res.scalar_one_or_none()

    if not inv or inv.user_id != db_user.id:
        await callback.answer("آیتم یافت نشد یا متعلق به شما نیست.", show_alert=True)
        return

    item = inv.item
    text = (
        f"📦 **توضیحات آیتم:** `{item.name}`\n"
        f"📝 {item.description}\n\n"
        f"⚔️ **قدرت حمله:** +{item.attack_power}\n"
        f"🛡️ **قدرت دفاع:** +{item.defense_power}\n"
        f"❤️ **ترمیم جان:** +{item.heal_hp}\n"
        f"🍖 **رفع گرسنگی:** +{item.restore_hunger}\n"
        f"💧 **رفع تشنگی:** +{item.restore_thirst}\n"
        f"💰 **ارزش فروش:** {item.sell_price} اسکرپ\n"
    )

    kb = get_inventory_keyboard(inv.id, inv.is_equipped, item.item_type)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@main_router.callback_query(F.data.startswith("inv:equip:"))
async def equip_item_handler(callback: CallbackQuery, db: AsyncSession, db_user: User):
    inv_id = int(callback.data.split(":")[2])
    stmt = select(Inventory).options(selectinload(Inventory.item)).where(Inventory.id == inv_id)
    res = await db.execute(stmt)
    inv = res.scalar_one_or_none()

    if inv and inv.user_id == db_user.id:
        # خارج کردن تجهیزات قبلی از همان نوع
        stmt_other = select(Inventory).options(selectinload(Inventory.item)).where(
            Inventory.user_id == db_user.id,
            Inventory.is_equipped == True
        )
        res_other = await db.execute(stmt_other)
        for other_inv in res_other.scalars().all():
            if other_inv.item.item_type == inv.item.item_type:
                other_inv.is_equipped = False

        inv.is_equipped = True
        await db.commit()
        await callback.answer(f"🛡️ {inv.item.name} با موفقیت تجهیز شد!", show_alert=True)
        await show_inventory(callback.message, db, db_user)


# ------------------------------------------------------------------------------
# 🗺️ سیستم کاوش و پیدا کردن منابع
# ------------------------------------------------------------------------------
@main_router.message(F.text == "🗺️ کاوش و مناطق")
async def list_locations(message: Message, db: AsyncSession, db_user: User):
    if not db_user:
        return

    stmt = select(Location)
    res = await db.execute(stmt)
    locations = res.scalars().all()

    text = (
        "🗺️ **مناطق قابل کاوش:**\n"
        "منطقه‌ای را برای جستجوی اسکرپ و غنایم انتخاب کنید.\n"
        "⚠️ *توجّه:* کاوش باعث مصرف انرژی، گرسنگی و تشنگی می‌شود.\n"
    )
    await message.answer(text, reply_markup=get_locations_keyboard(locations), parse_mode="Markdown")


@main_router.callback_query(F.data.startswith("loc:select:"))
async def process_scavenge(callback: CallbackQuery, db: AsyncSession, db_user: User):
    loc_id = int(callback.data.split(":")[2])
    stmt = select(Location).where(Location.id == loc_id)
    res = await db.execute(stmt)
    location = res.scalar_one_or_none()

    if not location:
        await callback.answer("منطقه نامعتبر است.", show_alert=True)
        return

    if db_user.level < location.min_level:
        await callback.answer(f"🔒 برای کاوش در این منطقه باید حداقل سطح {location.min_level} باشید!", show_alert=True)
        return

    if db_user.energy < location.energy_cost:
        await callback.answer("⚡ انرژی کافی برای کاوش ندارید! استراحت کنید.", show_alert=True)
        return

    # کاهش منابع حیاتی
    db_user.energy -= location.energy_cost
    db_user.hunger = max(0, db_user.hunger - random.randint(5, 12))
    db_user.thirst = max(0, db_user.thirst - random.randint(8, 15))

    # شانس مبارزه با زامبی یا پیدا کردن غنیمت
    encounter_chance = random.random()

    if encounter_chance < 0.4:
        # رویارویی با زامبی
        z_stmt = select(Zombie).where(Zombie.is_boss == False).order_by(func.random())
        z_res = await db.execute(z_stmt)
        zombie = z_res.scalars().first()

        text = (
            f"🚨 **کمین زامبی!**\n\n"
            f"در حال کاوش در **{location.name}** بودید که ناگهان یک **{zombie.name}** جلوی شما سبز شد!\n"
            f"❤️ جان زامبی: `{zombie.hp}` | ⚔️ قدرت حمله: `{zombie.attack}`"
        )
        await callback.message.edit_text(text, reply_markup=get_combat_keyboard(zombie.id), parse_mode="Markdown")
    else:
        # غنیمت‌گیری موفق
        scrap_found = int(random.randint(20, 60) * location.scrap_multiplier)
        xp_gained = int(15 * location.scrap_multiplier)
        
        db_user.scrap += scrap_found
        db_user.xp += xp_gained
        db_user.successful_scavenges += 1
        
        leveled = check_level_up(db_user)

        text = (
            f"✅ **کاوش با موفقیت انجام شد!**\n\n"
            f"📍 **منطقه:** {location.name}\n"
            f"⚙️ **قطعات پیدا شده:** +{scrap_found}\n"
            f"⭐ **امتیاز XP:** +{xp_gained}\n"
        )
        if leveled:
            text += f"\n🎊 **تبریک! به سطح {db_user.level} ارتقا پیدا کردید!**"

        await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
        # ==============================================================================
# 📄 bot.py - PART 6/8: ADVANCED COMBAT ENGINE & SHELTER SYSTEM
# ==============================================================================

# ------------------------------------------------------------------------------
# ⚔️ سیستم مبارزه (COMBAT ENGINE)
# ------------------------------------------------------------------------------
@main_router.message(F.text == "⚔️ مبارزه و شکار")
async def start_random_combat(message: Message, db: AsyncSession, db_user: User):
    if not db_user:
        return

    if db_user.hp <= 15:
        await message.answer("⚠️ وضعیت سلامتی شما بسیار بحرانی است! ابتدا خود را درمان کنید.", parse_mode="Markdown")
        return

    if db_user.energy < 10:
        await message.answer("⚡ برای مبارزه انرژی کافی ندارید!", parse_mode="Markdown")
        return

    db_user.energy -= 10

    # انتخاب زامبی تصادفی براساس سطح کاربر
    stmt = select(Zombie).order_by(func.random())
    res = await db.execute(stmt)
    zombie = res.scalars().first()

    if not zombie:
        await message.answer("هیچ زامبی در اطراف یافت نشد.")
        return

    text = (
        f"🚨 **زامبی شناسایی شد!**\n\n"
        f"👾 **نام:** `{zombie.name}`\n"
        f"❤️ **جان زامبی:** `{zombie.hp}/{zombie.max_hp}`\n"
        f"⚔️ **قدرت حمله زامبی:** `{zombie.attack}`\n"
        f"🛡️ **دفاع زامبی:** `{zombie.defense}`\n\n"
        f"چگونه پاسخ می‌دهید؟"
    )
    await message.answer(text, reply_markup=get_combat_keyboard(zombie.id), parse_mode="Markdown")


@main_router.callback_query(F.data.startswith("combat:attack:"))
async def combat_attack_handler(callback: CallbackQuery, db: AsyncSession, db_user: User):
    zombie_id = int(callback.data.split(":")[2])
    stmt = select(Zombie).where(Zombie.id == zombie_id)
    res = await db.execute(stmt)
    zombie = res.scalar_one_or_none()

    if not zombie:
        await callback.answer("اطلاعات زامبی یافت نشد.", show_alert=True)
        return

    user_stats = await get_user_total_stats(db, db_user.id)
    
    # محاسبه آسیب بازیکن به زامبی
    user_damage = max(1, user_stats["attack"] - zombie.defense + random.randint(-3, 5))
    zombie_remaining_hp = zombie.hp - user_damage

    if zombie_remaining_hp <= 0:
        # پیروزی بازیکن
        db_user.zombie_kills += 1
        db_user.scrap += zombie.scrap_reward
        db_user.xp += zombie.xp_reward
        if zombie.is_boss:
            db_user.boss_kills += 1

        leveled = check_level_up(db_user)

        text = (
            f"💥 **پیروزی در مبارزه!**\n\n"
            f"شما **{zombie.name}** را نابود کردید!\n"
            f"⚔️ آسیب وارده: `{user_damage}`\n"
            f"⚙️ **غنایم:** +{zombie.scrap_reward} اسکرپ\n"
            f"⭐ **تجربه:** +{zombie.xp_reward} XP\n"
        )
        if leveled:
            text += f"\n🎊 **ارتقای سطح! شما به سطح {db_user.level} رسیدید.**"

        await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
        return

    # آسیب زامبی به بازیکن در صورت زنده ماندن
    zombie_damage = max(1, zombie.attack - user_stats["defense"] + random.randint(-2, 3))
    db_user.hp -= zombie_damage

    if db_user.hp <= 0:
        # شکست و مرگ بازیکن
        db_user.hp = 20
        db_user.deaths += 1
        db_user.scrap = int(db_user.scrap * 0.8)  # از دست دادن ۲۰ درصد اسکرپ
        
        text = (
            f"💀 **شما در مبارزه شکست خوردید!**\n\n"
            f"زامبی **{zombie.name}** شما را از پا درآورد.\n"
            f"با سخته‌کوشی به پناهگاه عقب‌نشینی کردید اما ۲۰٪ اسکرپ‌های خود را از دست دادید."
        )
        await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
        return

    # ادامه نبرد
    text = (
        f"⚔️ **مبارزه ادامه دارد!**\n\n"
        f"شما `{user_damage}` آسیب زدید. (جان زامبی: `{zombie_remaining_hp}`)\n"
        f"زامبی `{zombie_damage}` به شما آسیب زد. (جان شما: `{db_user.hp}/{db_user.max_hp}`)"
    )
    await callback.message.edit_text(text, reply_markup=get_combat_keyboard(zombie.id), parse_mode="Markdown")


@main_router.callback_query(F.data.startswith("combat:defend:"))
async def combat_defend_handler(callback: CallbackQuery, db: AsyncSession, db_user: User):
    zombie_id = int(callback.data.split(":")[2])
    stmt = select(Zombie).where(Zombie.id == zombie_id)
    res = await db.execute(stmt)
    zombie = res.scalar_one_or_none()

    if not zombie:
        return

    user_stats = await get_user_total_stats(db, db_user.id)
    reduced_damage = max(1, (zombie.attack // 2) - user_stats["defense"])
    db_user.hp = max(1, db_user.hp - reduced_damage)
    db_user.energy = min(100, db_user.energy + 10)

    text = (
        f"🛡️ **سنگر گرفتید!**\n\n"
        f"آسیب دریافتی کاهش یافت: `{reduced_damage}`\n"
        f"⚡ بازیابی انرژی: `+10`\n"
        f"❤️ جان شما: `{db_user.hp}/{db_user.max_hp}`"
    )
    await callback.message.edit_text(text, reply_markup=get_combat_keyboard(zombie.id), parse_mode="Markdown")


@main_router.callback_query(F.data.startswith("combat:flee:"))
async def combat_flee_handler(callback: CallbackQuery, db: AsyncSession, db_user: User):
    if random.random() < 0.6:
        await callback.message.edit_text("🏃 **با موفقیت از میدان نبرد فرار کردید!**", reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
    else:
        db_user.hp = max(1, db_user.hp - 15)
        await callback.message.edit_text(
            f"❌ **فرار ناموفق بود!**\nدر هنگام فرار ۱۵ واحد آسیب دیدید.\n❤️ جان باقی‌مانده: `{db_user.hp}`",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )


# ------------------------------------------------------------------------------
# 🏠 مدیریت پناهگاه (SHELTER MANAGEMENT)
# ------------------------------------------------------------------------------
@main_router.message(F.text == "🏠 پناهگاه")
async def show_shelter(message: Message, db: AsyncSession, db_user: User):
    if not db_user:
        return

    stmt = select(Shelter).where(Shelter.user_id == db_user.id)
    res = await db.execute(stmt)
    shelter = res.scalar_one_or_none()

    if not shelter:
        shelter = Shelter(user_id=db_user.id)
        db.add(shelter)
        await db.commit()

    text = (
        f"🏠 **پناهگاه اختصاصی شما:**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏰 **سطح پناهگاه:** `{shelter.level}`\n"
        f"🛡️ **استحکام و دفاع:** `{shelter.defense}`\n"
        f"💧 **تصفیه‌خانه آب:** سطح `{shelter.water_collector_level}`\n"
        f"🌾 **مزرعه غذا:** سطح `{shelter.food_farm_level}`\n"
        f"🏥 **آزمایشگاه پزشکی:** سطح `{shelter.medical_lab_level}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 *امکانات پناهگاه به شما منابع رایگان در فواصل زمانی می‌دهند.*"
    )
    await message.answer(text, reply_markup=get_shelter_keyboard(shelter), parse_mode="Markdown")


@main_router.callback_query(F.data == "shelter:upgrade_main")
async def upgrade_shelter_main(callback: CallbackQuery, db: AsyncSession, db_user: User):
    stmt = select(Shelter).where(Shelter.user_id == db_user.id)
    res = await db.execute(stmt)
    shelter = res.scalar_one_or_none()

    cost = shelter.level * 200
    if db_user.scrap < cost:
        await callback.answer(f"❌ قطعات کافی ندارید! قیمت ارتقا: {cost} اسکرپ", show_alert=True)
        return

    db_user.scrap -= cost
    shelter.level += 1
    shelter.defense += 30
    await db.commit()

    await callback.answer("✅ پناهگاه با موفقیت ارتقا یافت!", show_alert=True)
    await show_shelter(callback.message, db, db_user)


@main_router.callback_query(F.data == "shelter:harvest")
async def harvest_shelter_resources(callback: CallbackQuery, db: AsyncSession, db_user: User):
    stmt = select(Shelter).where(Shelter.user_id == db_user.id)
    res = await db.execute(stmt)
    shelter = res.scalar_one_or_none()

    now = datetime.utcnow()
    time_diff = (now - shelter.last_harvest).total_seconds() / 3600.0  # برحسب ساعت

    if time_diff < 1.0:
        await callback.answer("⏳ هنوز محصولی برای برداشت آماده نشده است (حداقل هر ۱ ساعت).", show_alert=True)
        return

    water_gained = int(time_diff * shelter.water_collector_level * 10)
    food_gained = int(time_diff * shelter.food_farm_level * 10)

    db_user.thirst = min(100, db_user.thirst + water_gained)
    db_user.hunger = min(100, db_user.hunger + food_gained)
    shelter.last_harvest = now

    await db.commit()

    await callback.message.edit_text(
        f"🌾 **برداشت محصول انجام شد!**\n\n"
        f"💧 **آب به دست آمده:** +{water_gained}\n"
        f"🍖 **غذای به دست آمده:** +{food_gained}\n"
        f"علائم حیاتی شما بروزرسانی شدند.",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )
    # ==============================================================================
# 📄 bot.py - PART 7/8: SHOP SYSTEM & CLAN SYSTEM WITH FSM
# ==============================================================================

# ------------------------------------------------------------------------------
# 🛒 سیستم فروشگاه (SHOP SYSTEM)
# ------------------------------------------------------------------------------
@main_router.message(F.text == "🛒 فروشگاه")
async def show_shop(message: Message, db: AsyncSession, db_user: User):
    stmt = select(Item)
    res = await db.execute(stmt)
    items = res.scalars().all()

    text = "🛒 **فروشگاه پسارستاخیزی:**\nخرید تجهیزات، دارو و منابع برای بقا\n━━━━━━━━━━━━━━━━━━━━\n"
    buttons = []

    for item in items:
        text += f"📦 **{item.name}** - قیمت: `{item.buy_price}` اسکرپ\n"
        buttons.append([InlineKeyboardButton(text=f"🛒 خرید {item.name} ({item.buy_price} ⚙️)", callback_data=f"shop:buy:{item.id}")])

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")


@main_router.callback_query(F.data.startswith("shop:buy:"))
async def buy_item_handler(callback: CallbackQuery, db: AsyncSession, db_user: User):
    item_id = int(callback.data.split(":")[2])
    stmt = select(Item).where(Item.id == item_id)
    res = await db.execute(stmt)
    item = res.scalar_one_or_none()

    if not item:
        await callback.answer("آیتم یافت نشد.", show_alert=True)
        return

    if db_user.scrap < item.buy_price:
        await callback.answer("❌ اسکرپ کافی برای خرید این آیتم ندارید!", show_alert=True)
        return

    db_user.scrap -= item.buy_price

    # افزودن به کوله‌پشتی
    inv_stmt = select(Inventory).where(Inventory.user_id == db_user.id, Inventory.item_id == item.id)
    inv_res = await db.execute(inv_stmt)
    inventory_item = inv_res.scalar_one_or_none()

    if inventory_item:
        inventory_item.quantity += 1
    else:
        new_inv = Inventory(user_id=db_user.id, item_id=item.id, quantity=1)
        db.add(new_inv)

    await db.commit()
    await callback.answer(f"✅ {item.name} با موفقیت خریداری شد و به کوله‌پشتی اضافه گردید!", show_alert=True)


# ------------------------------------------------------------------------------
# 👥 سیستم کلن و اتحاد (CLAN SYSTEM)
# ------------------------------------------------------------------------------
@main_router.message(F.text == "👥 کلن و اتحاد")
async def show_clan_menu(message: Message, db: AsyncSession, db_user: User):
    if not db_user:
        return

    in_clan = db_user.clan_id is not None
    is_leader = db_user.clan_role == ClanRole.LEADER.value

    if not in_clan:
        text = "👥 **سیستم کلن و اتحاد:**\n\nشما هنوز عضو هیچ کلنی نیستید. می‌توانید یک کلن جدید بسازید یا به کلن‌های موجود بپیوندید."
    else:
        stmt = select(Clan).where(Clan.id == db_user.clan_id)
        res = await db.execute(stmt)
        clan = res.scalar_one_or_none()

        text = (
            f"🏰 **کلن [{clan.tag}] {clan.name}**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 **توضیحات:** {clan.description or 'بدون توضیح'}\n"
            f"⭐ **سطح کلن:** `{clan.level}`\n"
            f"💰 **خزانه:** `{clan.treasury_scrap}` اسکرپ\n"
            f"🎖️ **نقش شما:** `{db_user.clan_role}`\n"
        )

    await message.answer(text, reply_markup=get_clan_keyboard(in_clan, is_leader), parse_mode="Markdown")


@main_router.callback_query(F.data == "clan:create")
async def start_clan_creation(callback: CallbackQuery, state: FSMContext, db_user: User):
    if db_user.clan_id:
        await callback.answer("شما قبلاً عضو یک کلن هستید!", show_alert=True)
        return

    if db_user.scrap < 500:
        await callback.answer("❌ ساخت کلن نیازمند ۵۰۰ اسکرپ است!", show_alert=True)
        return

    await state.set_state(ClanStates.waiting_for_clan_name)
    await callback.message.edit_text("📛 **لطفاً نام کلن خود را وارد کنید:**\n(حداکثر ۶۴ کاراکتر)", parse_mode="Markdown")


@main_router.message(ClanStates.waiting_for_clan_name)
async def process_clan_name(message: Message, state: FSMContext):
    await state.update_data(clan_name=message.text.strip())
    await state.set_state(ClanStates.waiting_for_clan_tag)
    await message.answer("🏷️ **لطفاً تگ کوتاه کلن را وارد کنید (بین ۲ تا ۵ کاراکتر):**")


@main_router.message(ClanStates.waiting_for_clan_tag)
async def process_clan_tag(message: Message, state: FSMContext, db: AsyncSession, db_user: User):
    tag = message.text.strip().upper()
    if len(tag) < 2 or len(tag) > 5:
        await message.answer("تگ باید بین ۲ تا ۵ حرف باشد.")
        return

    data = await state.get_data()
    clan_name = data["clan_name"]

    # ایجاد کلن در دیتابیس
    db_user.scrap -= 500
    new_clan = Clan(
        name=clan_name,
        tag=tag,
        leader_id=db_user.telegram_id,
        treasury_scrap=0
    )
    db.add(new_clan)
    await db.flush()

    db_user.clan_id = new_clan.id
    db_user.clan_role = ClanRole.LEADER.value

    await db.commit()
    await state.clear()

    await message.answer(f"🎉 **کلن [{tag}] {clan_name} با موفقیت ساخته شد!**", reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")


@main_router.callback_query(F.data == "clan:leave")
async def leave_clan_handler(callback: CallbackQuery, db: AsyncSession, db_user: User):
    if not db_user.clan_id:
        return

    if db_user.clan_role == ClanRole.LEADER.value:
        await callback.answer("رهبر کلن نمی‌تواند کلن را ترک کند! باید ابتدا کلن را حذف یا منتقل کنید.", show_alert=True)
        return

    db_user.clan_id = None
    db_user.clan_role = ClanRole.MEMBER.value
    await db.commit()

    await callback.message.edit_text("🚪 **شما از کلن خارج شدید.**", reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
        # ==============================================================================
# 📄 bot.py - PART 8/8: ADMIN PANEL & MAIN BOT ENTRYPOINT
# ==============================================================================

# ------------------------------------------------------------------------------
# 👑 پنل ادمین و مدیریت (ADMIN HANDLERS)
# ------------------------------------------------------------------------------
@main_router.message(Command("admin"))
async def cmd_admin_panel(message: Message, is_admin: bool):
    if not is_admin:
        await message.answer("⛔ شما دسترسی ادمین ندارید.")
        return

    text = "👑 **پنل مدیریت ربات پسارستاخیزی:**\nاز دکمه‌های زیر استفاده کنید."
    await message.answer(text, reply_markup=get_admin_keyboard(), parse_mode="Markdown")


@main_router.callback_query(F.data == "admin:stats")
async def admin_stats_handler(callback: CallbackQuery, db: AsyncSession, is_admin: bool):
    if not is_admin:
        return

    total_users = (await db.execute(select(func.count(User.id)))).scalar()
    total_clans = (await db.execute(select(func.count(Clan.id)))).scalar()
    total_kills = (await db.execute(select(func.sum(User.zombie_kills)))).scalar() or 0

    text = (
        f"📊 **آمار کامل سرور:**\n\n"
        f"👥 **تعداد کل بازماندگان:** `{total_users}`\n"
        f"🏰 **تعداد کلن‌های فعال:** `{total_clans}`\n"
        f"💀 **مجموع زامبی‌های کشته‌شده:** `{total_kills}`"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_keyboard(), parse_mode="Markdown")


@main_router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext, is_admin: bool):
    if not is_admin:
        return

    await state.set_state(AdminStates.waiting_for_broadcast_text)
    await callback.message.edit_text("📢 **متن پیام همگانی را ارسال کنید:**", parse_mode="Markdown")


@main_router.message(AdminStates.waiting_for_broadcast_text)
async def admin_broadcast_process(message: Message, state: FSMContext, db: AsyncSession, bot: Bot):
    broadcast_text = message.text
    stmt = select(User.telegram_id)
    res = await db.execute(stmt)
    users = res.scalars().all()

    success_count = 0
    for tid in users:
        try:
            await bot.send_message(tid, f"📢 **پیام مدیریت:**\n\n{broadcast_text}", parse_mode="Markdown")
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            continue

    await state.clear()
    await message.answer(f"✅ پیام همگانی با موفقیت به {success_count} کاربر ارسال شد.")


# ------------------------------------------------------------------------------
# 📖 راهنما و پشتیبانی
# ------------------------------------------------------------------------------
@main_router.message(F.text == "📖 راهنما و پشتیبانی")
async def show_help(message: Message):
    help_text = (
        "📖 **راهنمای بازی بقا در دنیای زامبی‌ها:**\n\n"
        "1️⃣ **کاوش:** با رفتن به بخش کاوش، اسکرپ (قطعات) و غنیمت به دست می‌آورید.\n"
        "2️⃣ **مبارزه:** زامبی‌ها را شکست دهید تا XP و اسکرپ بگیرید و سطح خود را بالا ببرید.\n"
        "3️⃣ **پناهگاه:** پناهگاه خود را ارتقا دهید تا به صورت خودکار آب و غذا تولید کند.\n"
        "4️⃣ **کلن:** با دیگران متحد شوید و کلن تشکیل دهید.\n"
        "5️⃣ **علائم حیاتی:** حواستان به HP، گرسنگی و تشنگی باشد!"
    )
    await message.answer(help_text, parse_mode="Markdown")


# ------------------------------------------------------------------------------
# 🚀 نقطه ورود اصلی و اجرای ربات (MAIN ASYNC ENGINE)
# ------------------------------------------------------------------------------
async def main():
    logger.info("در حال آماده‌سازی دیتابیس و راه‌اندازی ربات...")

    # ساخت جدول‌ها در صورت عدم وجود
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # ثبت داده‌های اولیه دیتابیس
    async with AsyncSessionLocal() as session:
        await seed_initial_game_data(session)

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # ثبت میدل‌ورها (Middlewares)
    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())

    dp.message.middleware(UserTrackerMiddleware())
    dp.callback_query.middleware(UserTrackerMiddleware())

    dp.message.middleware(AdminMiddleware())
    dp.callback_query.middleware(AdminMiddleware())

    # ثبت روتور اصلی
    dp.include_router(main_router)

    logger.info("🤖 ربات با موفقیت فعال شد و آماده دریافت دستورات است!")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("ربات متوقف شد.")
    
    
