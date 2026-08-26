import asyncio
import json
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ChatMemberStatus

# ==================== تنظیمات ====================
BOT_TOKEN = "8636563885:AAH-Ihpb7-Ql9MwD1lZ824rwu1sdb3uUH8o"
ADMIN_ID = 7530457395

GROUPS_FILE = "groups.json"

# ==================== ذخیره و بارگذاری گپ‌ها ====================
def load_groups():
    if os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_groups(groups):
    with open(GROUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)

groups = load_groups()

# ==================== استیت‌ها ====================
class SendStates(StatesGroup):
    waiting_content = State()
    waiting_count = State()
    waiting_delay = State()

# ==================== کیبوردها ====================
def groups_keyboard():
    kb = []
    for chat_id, title in groups.items():
        kb.append([
            InlineKeyboardButton(text=f"📌 {title}", callback_data=f"select_{chat_id}"),
            InlineKeyboardButton(text="🚪 لف", callback_data=f"leave_{chat_id}")
        ])
    if not kb:
        return None
    return InlineKeyboardMarkup(inline_keyboard=kb)

def send_keyboard(chat_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 ارسال", callback_data=f"send_{chat_id}")]
    ])

# ==================== ربات ====================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

@dp.message(CommandStart())
async def start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "سلام ادمین 👋\n\n"
        "ربات رو به گپ‌ها اضافه کن. وقتی اضافه بشه اینجا بهت خبر می‌دم.\n"
        "برای دیدن لیست گپ‌ها از /groups استفاده کن."
    )

@dp.message(Command("groups"))
async def list_groups(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    if not groups:
        await message.answer("هنوز هیچ گپی تایید نشده.")
        return

    text = "✅ گپ‌های تایید شده:\n\n"
    for i, (cid, title) in enumerate(groups.items(), 1):
        text += f"{i}. {title}\n"

    kb = groups_keyboard()
    await message.answer(text, reply_markup=kb)

@dp.my_chat_member()
async def on_bot_added(event: types.ChatMemberUpdated):
    if event.new_chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
        chat = event.chat
        if chat.type in ["group", "supergroup"]:
            groups[str(chat.id)] = chat.title or "بدون عنوان"
            save_groups(groups)

            count = len(groups)
            if count == 1:
                text = f"✅ گپ تایید شد\n\n📌 {chat.title}"
            else:
                text = f"✅ گپ‌ها تایید شدن ({count} گپ)\n\n"
                for i, (cid, title) in enumerate(groups.items(), 1):
                    text += f"{i}. {title}\n"

            await bot.send_message(ADMIN_ID, text)

    elif event.new_chat_member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
        chat_id = str(event.chat.id)
        if chat_id in groups:
            del groups[chat_id]
            save_groups(groups)
            await bot.send_message(ADMIN_ID, f"❌ از گپ «{event.chat.title}» حذف شدم.")

@dp.callback_query(F.data.startswith("select_"))
async def select_group(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    chat_id = callback.data.split("_")[1]
    title = groups.get(chat_id, "نامشخص")
    await callback.message.edit_text(
        f"گپ انتخاب شده:\n📌 {title}",
        reply_markup=send_keyboard(chat_id)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("leave_"))
async def leave_group(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    chat_id = callback.data.split("_")[1]
    title = groups.get(chat_id, "نامشخص")
    try:
        await bot.leave_chat(int(chat_id))
        if chat_id in groups:
            del groups[chat_id]
            save_groups(groups)
        await callback.message.edit_text(f"✅ از گپ «{title}» لف دادم.")
    except Exception as e:
        await callback.message.edit_text(f"❌ خطا در لف دادن: {e}")
    await callback.answer()

@dp.callback_query(F.data.startswith("send_"))
async def start_send(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    chat_id = callback.data.split("_")[1]
    await state.update_data(target_chat=chat_id)
    await state.set_state(SendStates.waiting_content)
    await callback.message.edit_text(
        "محتوای ارسالی رو بفرست (عکس / فیلم / استیکر / پیام متنی):\n"
        "بعد از ارسال محتوا، تعداد و ثانیه رو ازت می‌پرسم."
    )
    await callback.answer()

@dp.message(SendStates.waiting_content)
async def get_content(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    data = {}
    if message.photo:
        data["type"] = "photo"
        data["file_id"] = message.photo[-1].file_id
        data["caption"] = message.caption
    elif message.video:
        data["type"] = "video"
        data["file_id"] = message.video.file_id
        data["caption"] = message.caption
    elif message.sticker:
        data["type"] = "sticker"
        data["file_id"] = message.sticker.file_id
    elif message.text:
        data["type"] = "text"
        data["text"] = message.text
    else:
        await message.answer("فقط عکس، فیلم، استیکر یا متن بفرست.")
        return

    await state.update_data(content=data)
    await state.set_state(SendStates.waiting_count)
    await message.answer("تعداد رو وارد کن (مثلاً 100):")

@dp.message(SendStates.waiting_count)
async def get_count(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.text or not message.text.isdigit():
        await message.answer("فقط عدد وارد کن.")
        return
    count = int(message.text)
    if count < 1 or count > 500:
        await message.answer("تعداد باید بین ۱ تا ۵۰۰ باشه.")
        return
    await state.update_data(count=count)
    await state.set_state(SendStates.waiting_delay)
    await message.answer("فاصله بین هر ارسال رو به ثانیه وارد کن (مثلاً 3):")

@dp.message(SendStates.waiting_delay)
async def get_delay_and_send(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.text or not message.text.replace(".", "").isdigit():
        await message.answer("فقط عدد وارد کن (مثلاً 3 یا 2.5).")
        return

    delay = float(message.text)
    if delay < 1:
        await message.answer("حداقل ۱ ثانیه.")
        return

    data = await state.get_data()
    target = int(data["target_chat"])
    content = data["content"]
    count = data["count"]

    await state.clear()
    await message.answer(f"شروع ارسال {count} تا با فاصله {delay} ثانیه...")

    success = 0
    for i in range(count):
        try:
            if content["type"] == "photo":
                await bot.send_photo(target, content["file_id"], caption=content.get("caption"))
            elif content["type"] == "video":
                await bot.send_video(target, content["file_id"], caption=content.get("caption"))
            elif content["type"] == "sticker":
                await bot.send_sticker(target, content["file_id"])
            elif content["type"] == "text":
                await bot.send_message(target, content["text"])
            success += 1
        except Exception as e:
            await message.answer(f"خطا در ارسال {i+1}: {e}")
            break
        if i < count - 1:
            await asyncio.sleep(delay)

    await message.answer(f"✅ تموم شد. {success} تا از {count} ارسال شد.")

async def main():
    print("ربات روشن شد...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
