# ==========================================
# بخش 1 از 8: تنظیمات اولیه و اتصال به دیتابیس
# ==========================================
import datetime
import random
import sqlite3
import telebot
from telebot import types

TOKEN = '8968618358:AAHReb2nlduQkclIJE1V-_FKh206VxmYmuc'
ADMIN_ID = 7530457395

bot = telebot.TeleBot(TOKEN)


def init_db():
  conn = sqlite3.connect('economy_game.db')
  cursor = conn.cursor()

  # جدول کاربران
  cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        wallet INTEGER DEFAULT 1000,
        bank INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        xp INTEGER DEFAULT 0,
        spouse_id INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        last_daily TEXT,
        last_crime TEXT,
        last_work TEXT,
        referred_by INTEGER DEFAULT 0
    )
    ''')

  # جدول فروشگاه (ماشین، خانه/ویلا، آیتم)
  cursor.execute('''
    CREATE TABLE IF NOT EXISTS shop_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        category TEXT,
        price INTEGER
    )
    ''')

  # جدول دارایی کاربران
  cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        item_name TEXT,
        category TEXT
    )
    ''')

  # جدول درخواست‌های ازدواج
  cursor.execute('''
    CREATE TABLE IF NOT EXISTS marriage_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_id INTEGER,
        to_id INTEGER
    )
    ''')

  conn.commit()
  conn.close()


init_db()
# ==========================================
# بخش 2 از 8: توابع کمکی دیتابیس
# ==========================================
def get_user(user_id, username="", ref_id=0):
  conn = sqlite3.connect("economy_game.db")
  cursor = conn.cursor()
  cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
  user = cursor.fetchone()

  if not user:
    cursor.execute(
        "INSERT INTO users (user_id, username, wallet, bank, referred_by)"
        " VALUES (?, ?, 1000, 0, ?)",
        (user_id, str(username), ref_id),
    )
    conn.commit()

    # پاداش دعوت کننده
    if ref_id > 0 and ref_id != user_id:
      cursor.execute(
          "UPDATE users SET wallet = wallet + 2000 WHERE user_id = ?",
          (ref_id,),
      )
      conn.commit()

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

  conn.close()
  return user


def is_banned(user_id):
  user = get_user(user_id)
  return user[7] == 1


def update_wallet(user_id, amount):
  conn = sqlite3.connect("economy_game.db")
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE users SET wallet = wallet + ? WHERE user_id = ?",
      (amount, user_id),
  )
  conn.commit()
  conn.close()


def update_bank(user_id, amount):
  conn = sqlite3.connect("economy_game.db")
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE users SET bank = bank + ? WHERE user_id = ?", (amount, user_id)
  )
  conn.commit()
  conn.close()


def add_xp(user_id, amount):
  conn = sqlite3.connect("economy_game.db")
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE users SET xp = xp + ? WHERE user_id = ?", (amount, user_id)
  )
  conn.commit()

  cursor.execute("SELECT level, xp FROM users WHERE user_id = ?", (user_id,))
  lvl, xp = cursor.fetchone()

  needed_xp = lvl * 100
  if xp >= needed_xp:
    cursor.execute(
        "UPDATE users SET level = level + 1, xp = 0 WHERE user_id = ?",
        (user_id,),
    )
    conn.commit()
    conn.close()
    return True
  conn.close()
  return False


def get_shop_items(category=None):
  conn = sqlite3.connect("economy_game.db")
  cursor = conn.cursor()
  if category:
    cursor.execute(
        "SELECT name, price FROM shop_items WHERE category = ?", (category,)
    )
  else:
    cursor.execute("SELECT name, category, price FROM shop_items")
  items = cursor.fetchall()
  conn.close()
  return items


def add_shop_item(name, category, price):
  conn = sqlite3.connect("economy_game.db")
  cursor = conn.cursor()
  try:
    cursor.execute(
        "INSERT OR REPLACE INTO shop_items (name, category, price) VALUES (?, "
        "?, ?)",
        (name, category, price),
    )
    conn.commit()
    success = True
  except Exception:
    success = False
  conn.close()
  return success


def update_item_price(name, new_price):
  conn = sqlite3.connect("economy_game.db")
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE shop_items SET price = ? WHERE name = ?", (new_price, name)
  )
  affected = cursor.rowcount
  conn.commit()
  conn.close()
  return affected > 0
      # ==========================================
# بخش 3 از 8: منوی اصلی و پروفایل کاربر
# ==========================================
def main_keyboard(user_id):
  markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
  markup.add("👤 پروفایل من", "💼 کار کردن")
  markup.add("🛒 فروشگاه و املاک", "🦹 دزدی و جرم")
  markup.add("💍 ازدواج", "🎯 مأموریت‌ها")
  markup.add("🏆 رتبه‌بندی", "💰 کیف پول و انتقال")
  markup.add("🏦 بانک مرکزی", "🎁 دعوت دوستان")
  markup.add("📖 راهنما و دستورات")

  if user_id == ADMIN_ID:
    markup.add("⚙️ پنل مدیریت")

  return markup


@bot.message_handler(commands=["start"])
def send_welcome(message):
  ref_id = 0
  args = message.text.split()
  if len(args) > 1 and args[1].isdigit():
    ref_id = int(args[1])

  user = get_user(
      message.from_user.id, message.from_user.username or "", ref_id
  )

  if is_banned(message.from_user.id):
    bot.send_message(
        message.chat.id, "❌ حساب کاربری شما توسط مدیریت مسدود شده است."
    )
    return

  text = f"سلام {message.from_user.first_name} عزیز! 👋\nبه بازی اقتصادی خوش آمدید."
  bot.send_message(
      message.chat.id, text, reply_markup=main_keyboard(message.from_user.id)
  )


@bot.message_handler(func=lambda m: m.text == "👤 پروفایل من")
def show_profile(message):
  if is_banned(message.from_user.id):
    return
  user = get_user(message.from_user.id)

  conn = sqlite3.connect("economy_game.db")
  cursor = conn.cursor()
  cursor.execute(
      "SELECT item_name, category FROM user_inventory WHERE user_id = ?",
      (message.from_user.id,),
  )
  inventory = cursor.fetchall()

  spouse_text = "مجرد"
  if user[6] != 0:
    cursor.execute(
        "SELECT username, user_id FROM users WHERE user_id = ?", (user[6],)
    )
    sp = cursor.fetchone()
    spouse_text = (
        f"@{sp[0]}" if sp and sp[0] else f"کاربر {user[6]}" if sp else "همسر"
    )

  conn.close()

  cars = [i[0] for i in inventory if i[1] == "car"]
  houses = [i[0] for i in inventory if i[1] == "house"]
  items = [i[0] for i in inventory if i[1] == "item"]

  profile_text = (
      f"👤 **پروفایل کاربری:**\n\n"
      f"🆔 آیدی عددی: `{user[0]}`\n"
      f"⭐ لول: {user[4]} (XP: {user[5]}/{user[4]*100})\n"
      f"💍 همسر: {spouse_text}\n\n"
      f"💵 موجودی کیف پول: {user[2]:,} سکه\n"
      f"🏦 موجودی بانک: {user[3]:,} سکه\n\n"
      f"🏎 ماشین‌ها: {', '.join(cars) if cars else 'ندارید'}\n"
      f"🏰 املاک و خانه: {', '.join(houses) if houses else 'ندارید'}\n"
      f"📦 آیتم‌ها: {', '.join(items) if items else 'ندارید'}"
  )
  bot.send_message(message.chat.id, profile_text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "📖 راهنما و دستورات")
def help_guide(message):
  if is_banned(message.from_user.id):
    return
  text = (
      "📖 **راهنمای بازی:**\n\n"
      "1️⃣ با **💼 کار کردن** یا **🦹 دزدی** سکه و XP به دست آورید.\n"
      "2️⃣ سکه‌های خود را در **🏦 بانک مرکزی** پس‌انداز کنید تا در دزدی"
      " باخت ندهید.\n"
      "3️⃣ از **🛒 فروشگاه** ماشین و خانه بخرید.\n"
      "4️⃣ با استفاده از دستور زیر به دوستانتان پول انتقال دهید:\n"
      "`انتقال آیدی_عددی مبلغ`\nمثال:\n`انتقال 123456789 5000`\n"
      "5️⃣ با لینک دعوت خود در **🎁 دعوت دوستان** دیگران را دعوت کنید و 2,000"
      " سکه پاداش بگیرید!"
  )
  bot.send_message(message.chat.id, text, parse_mode="Markdown")
    # ==========================================
# بخش 4 از 8: بانک، انتقال پول و زیرمجموعه
# ==========================================
@bot.message_handler(func=lambda m: m.text == "🏦 بانک مرکزی")
def bank_menu(message):
  if is_banned(message.from_user.id):
    return
  user = get_user(message.from_user.id)
  markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
  markup.add("📥 واریز به بانک", "📤 برداشت از بانک")
  markup.add("🔙 بازگشت به منوی اصلی")

  text = (
      f"🏦 **سیستم بانکی**\n\n"
      f"💵 کیف پول: {user[2]:,} سکه\n"
      f"🏛 حساب بانک: {user[3]:,} سکه\n\n"
      f"عملیات مورد نظر را انتخاب کنید:"
  )
  bot.send_message(
      message.chat.id, text, parse_mode="Markdown", reply_markup=markup
  )


@bot.message_handler(func=lambda m: m.text == "📥 واریز به بانک")
def deposit_start(message):
  if is_banned(message.from_user.id):
    return
  msg = bot.send_message(
      message.chat.id, "مبلغ مورد نظر برای واریز به بانک را وارد کنید:"
  )
  bot.register_next_step_handler(msg, process_deposit)


def process_deposit(message):
  if message.text == "🔙 بازگشت به منوی اصلی":
    send_welcome(message)
    return
  try:
    amount = int(message.text)
    user = get_user(message.from_user.id)
    if amount <= 0 or user[2] < amount:
      bot.send_message(message.chat.id, "❌ موجودی کیف پول کافی نیست!")
      return
    update_wallet(message.from_user.id, -amount)
    update_bank(message.from_user.id, amount)
    bot.send_message(
        message.chat.id, f"✅ مبلغ {amount:,} سکه به بانک واریز شد."
    )
  except ValueError:
    bot.send_message(message.chat.id, "❌ لطفاً فقط عدد وارد کنید.")


@bot.message_handler(func=lambda m: m.text == "📤 برداشت از بانک")
def withdraw_start(message):
  if is_banned(message.from_user.id):
    return
  msg = bot.send_message(
      message.chat.id, "مبلغ مورد نظر برای برداشت از بانک را وارد کنید:"
  )
  bot.register_next_step_handler(msg, process_withdraw)


def process_withdraw(message):
  if message.text == "🔙 بازگشت به منوی اصلی":
    send_welcome(message)
    return
  try:
    amount = int(message.text)
    user = get_user(message.from_user.id)
    if amount <= 0 or user[3] < amount:
      bot.send_message(message.chat.id, "❌ موجودی بانک کافی نیست!")
      return
    update_bank(message.from_user.id, -amount)
    update_wallet(message.from_user.id, amount)
    bot.send_message(
        message.chat.id, f"✅ مبلغ {amount:,} سکه از بانک برداشت شد."
    )
  except ValueError:
    bot.send_message(message.chat.id, "❌ لطفاً فقط عدد وارد کنید.")


@bot.message_handler(
    func=lambda m: m.text == "💰 کیف پول و انتقال"
    or m.text.startswith("انتقال")
)
def wallet_and_transfer(message):
  if is_banned(message.from_user.id):
    return
  if message.text == "💰 کیف پول و انتقال":
    user = get_user(message.from_user.id)
    text = (
        f"💰 **کیف پول:** {user[2]:,} سکه\n\n"
        f"برای انتقال سکه به کاربر دیگر از دستور زیر استفاده کنید:\n"
        f"`انتقال آیدی_عددی مبلغ`\n\nمثال:\n`انتقال 123456789 5000`"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")
    return

  parts = message.text.split()
  if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
    target_id = int(parts[1])
    amount = int(parts[2])
    sender = get_user(message.from_user.id)

    if amount <= 0 or sender[2] < amount:
      bot.send_message(message.chat.id, "❌ موجودی کافی نیست!")
      return

    target = get_user(target_id)
    if not target:
      bot.send_message(message.chat.id, "❌ کاربر مقصد یافت نشد!")
      return

    update_wallet(message.from_user.id, -amount)
    update_wallet(target_id, amount)
    bot.send_message(
        message.chat.id,
        f"✅ مبلغ {amount:,} سکه با موفقیت به کاربر {target_id} منتقل شد.",
    )
    bot.send_message(
        target_id,
        f"🎉 کاربر {message.from_user.id} مبلغ {amount:,} سکه به شما منتقل"
        " کرد!",
    )


@bot.message_handler(func=lambda m: m.text == "🎁 دعوت دوستان")
def referral_system(message):
  if is_banned(message.from_user.id):
    return
  bot_info = bot.get_me()
  link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"
  text = (
      f"🎁 **دعوت از دوستان:**\n\nبا دعوت دوستان خود به ربات، **2,000"
      f" سکه** پاداش بگیرید!\n\nلینک اختصاصی شما:\n`{link}`"
  )
  bot.send_message(message.chat.id, text, parse_mode="Markdown")
        # ==========================================
# بخش 5 از 8: کار، دزدی، مأموریت و لیدربورد
# ==========================================
@bot.message_handler(func=lambda m: m.text == '💼 کار کردن')
def work_game(message):
  if is_banned(message.from_user.id):
    return
  reward = random.randint(200, 800)
  xp_gained = random.randint(10, 30)

  update_wallet(message.from_user.id, reward)
  lvl_up = add_xp(message.from_user.id, xp_gained)

  msg = f'🔨 شما کار کردید و **{reward:,} سکه** و **{xp_gained} XP** به دست آوردید!'
  if lvl_up:
    msg += '\n🎉 تبریک! سطح شما ارتقا یافت!'
  bot.send_message(message.chat.id, msg, parse_mode='Markdown')


@bot.message_handler(func=lambda m: m.text == '🦹 دزدی و جرم')
def crime_game(message):
  if is_banned(message.from_user.id):
    return
  user = get_user(message.from_user.id)
  success = random.choice([True, False, True])  # 66% شانس موفقیت

  if success:
    stolen = random.randint(500, 2000)
    update_wallet(message.from_user.id, stolen)
    add_xp(message.from_user.id, 40)
    bot.send_message(
        message.chat.id,
        f'🎭 دزدی با موفقیت انجام شد! **{stolen:,} سکه** جیب زدید!',
        parse_mode='Markdown',
    )
  else:
    fine = random.randint(300, 1000)
    if user[2] >= fine:
      update_wallet(message.from_user.id, -fine)
      bot.send_message(
          message.chat.id,
          f'🚨 پلیس دستگیرتون کرد و **{fine:,} سکه** جریمه شدید!',
          parse_mode='Markdown',
      )
    else:
      bot.send_message(
          message.chat.id,
          '🚨 پلیس دستگیرتون کرد ولی چون پولی تو کیف پولتون نبود از دستش'
          ' فرار کردید!',
      )


@bot.message_handler(func=lambda m: m.text == '🎯 مأموریت‌ها')
def missions_menu(message):
  if is_banned(message.from_user.id):
    return
  text = (
      '🎯 **مأموریت‌های فعال:**\n\n'
      '1️⃣ **کارگر نمونه:** 5 بار کار کنید 🎁 پاداش: 1,500 سکه\n'
      '2️⃣ **دزد حرفه‌ای:** 3 دزدی موفق انجام دهید 🎁 پاداش: 3,000 سکه\n\n'
      '*(مأموریت‌ها به صورت خودکار محاسبه و اعمال می‌شوند)*'
  )
  bot.send_message(message.chat.id, text, parse_mode='Markdown')


@bot.message_handler(func=lambda m: m.text == '🏆 رتبه‌بندی')
def leaderboard(message):
  if is_banned(message.from_user.id):
    return
  conn = sqlite3.connect('economy_game.db')
  cursor = conn.cursor()
  cursor.execute(
      'SELECT username, user_id, (wallet + bank) as total FROM users ORDER BY'
      ' total DESC LIMIT 10'
  )
  top_users = cursor.fetchall()
  conn.close()

  text = '🏆 **برترین و ثروتمندترین کاربران:**\n\n'
  for idx, u in enumerate(top_users, 1):
    uname = f'@{u[0]}' if u[0] else f'کاربر {u[1]}'
    text += f'{idx}. {uname} ➔ {u[2]:,} سکه\n'

  bot.send_message(message.chat.id, text, parse_mode='Markdown')
# ==========================================
# بخش 6 از 8: فروشگاه املاک و سیستم ازدواج
# ==========================================
@bot.message_handler(func=lambda m: m.text == '🛒 فروشگاه و املاک')
def shop_menu(message):
  if is_banned(message.from_user.id):
    return
  markup = types.InlineKeyboardMarkup(row_width=2)
  markup.add(
      types.InlineKeyboardButton('🏎 ماشین‌ها', callback_data='shop_car'),
      types.InlineKeyboardButton(
          '🏰 املاک و خانه', callback_data='shop_house'
      ),
      types.InlineKeyboardButton('📦 سایر آیتم‌ها', callback_data='shop_item'),
  )
  bot.send_message(
      message.chat.id,
      '🛍 دسته مورد نظر را انتخاب کنید:',
      reply_markup=markup,
  )


@bot.callback_query_handler(func=lambda call: call.data.startswith('shop_'))
def show_category_items(call):
  category = call.data.split('_')[1]
  items = get_shop_items(category)

  if not items:
    bot.answer_callback_query(
        call.id, 'آیتمی در این دسته وجود ندارد!', show_alert=True
    )
    return

  markup = types.InlineKeyboardMarkup()
  for name, price in items:
    markup.add(
        types.InlineKeyboardButton(
            f'{name} - {price:,} سکه', callback_data=f'buy_{name}'
        )
    )

  bot.edit_message_text(
      'لیست موارد موجود:',
      call.message.chat.id,
      call.message.message_id,
      reply_markup=markup,
  )


@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def buy_item(call):
  item_name = call.data.split('_')[1]
  conn = sqlite3.connect('economy_game.db')
  cursor = conn.cursor()
  cursor.execute(
      'SELECT category, price FROM shop_items WHERE name = ?', (item_name,)
  )
  item = cursor.fetchone()

  if not item:
    bot.answer_callback_query(call.id, 'این آیتم پیدا نشد!')
    conn.close()
    return

  category, price = item
  user = get_user(call.from_user.id)

  if user[2] < price:
    bot.answer_callback_query(
        call.id, f'❌ شما به {price:,} سکه نیاز دارید!', show_alert=True
    )
    conn.close()
    return

  update_wallet(call.from_user.id, -price)
  cursor.execute(
      'INSERT INTO user_inventory (user_id, item_name, category) VALUES (?,'
      ' ?, ?)',
      (call.from_user.id, item_name, category),
  )
  conn.commit()
  conn.close()

  bot.answer_callback_query(
      call.id, f'🎉 با موفقیت {item_name} خریده شد!', show_alert=True
  )


@bot.message_handler(func=lambda m: m.text == '💍 ازدواج')
def marriage_menu(message):
  if is_banned(message.from_user.id):
    return
  user = get_user(message.from_user.id)
  if user[6] != 0:
    bot.send_message(message.chat.id, '💍 شما در حال حاضر متأهل هستید!')
    return

  msg = bot.send_message(
      message.chat.id,
      'برای درخواست ازدواج، آیدی عددی فرد مورد نظر را ارسال کنید:',
  )
  bot.register_next_step_handler(msg, process_marriage_request)


def process_marriage_request(message):
  try:
    target_id = int(message.text)
    if target_id == message.from_user.id:
      bot.send_message(message.chat.id, '❌ نمی‌توانید با خودتان ازدواج کنید!')
      return

    target = get_user(target_id)
    if not target or target[6] != 0:
      bot.send_message(
          message.chat.id, '❌ کاربر یافت نشد یا در حال حاضر متأهل است!'
      )
      return

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            '✅ قبول درخواست', callback_data=f'acceptm_{message.from_user.id}'
        ),
        types.InlineKeyboardButton(
            '❌ رد درخواست', callback_data=f'rejectm_{message.from_user.id}'
        ),
    )
    bot.send_message(
        target_id,
        f'💍 کاربر {message.from_user.id} به شما پیشنهاد ازدواج داده است!',
        reply_markup=markup,
    )
    bot.send_message(message.chat.id, '💌 پیشنهاد ازدواج ارسال شد.')
  except Exception:
    bot.send_message(message.chat.id, '❌ آیدی عددی نامعتبر است.')


@bot.callback_query_handler(
    func=lambda call: call.data.startswith(('acceptm_', 'rejectm_'))
)
def marriage_response(call):
  action, sender_id = call.data.split('_')
  sender_id = int(sender_id)

  if action == 'acceptm':
    conn = sqlite3.connect('economy_game.db')
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE users SET spouse_id = ? WHERE user_id = ?',
        (call.from_user.id, sender_id),
    )
    cursor.execute(
        'UPDATE users SET spouse_id = ? WHERE user_id = ?',
        (sender_id, call.from_user.id),
    )
    conn.commit()
    conn.close()

    bot.send_message(
        call.message.chat.id, '🎉 پیوندتان مبارک! شما با هم ازدواج کردید.'
    )
    bot.send_message(
        sender_id, '🎉 پیشنهاد ازدواج شما پذیرفته شد! مبارک باشد.'
    )
  else:
    bot.send_message(call.message.chat.id, '❌ درخواست رد شد.')
    bot.send_message(sender_id, '💔 پیشنهاد ازدواج شما رد شد.')
      # ==========================================
# بخش 7 از 8: پنل مدیریت - مدیریت کاربران
# ==========================================
@bot.message_handler(
    func=lambda m: m.text == '⚙️ پنل مدیریت'
    or m.text == '🔙 بازگشت به منوی ادمین'
)
def admin_panel(message):
  if message.from_user.id != ADMIN_ID:
    return

  markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
  markup.add('📊 آمار و لیست کاربران', '🔍 جستجوی کاربر')
  markup.add('💰 تغییر موجودی کاربر', '⭐ تغییر لول کاربر')
  markup.add('🚫 مسدود کاربر', '✅ رفع مسدود')
  markup.add('➕ اضافه کردن ماشین', '➕ اضافه کردن خانه')
  markup.add('✏️ تغییر قیمت آیتم', '🔙 بازگشت به منوی اصلی')

  bot.send_message(
      message.chat.id, '🛠 **پنل مدیریت ربات:**', reply_markup=markup
  )


@bot.message_handler(func=lambda m: m.text == '📊 آمار و لیست کاربران')
def admin_user_list(message):
  if message.from_user.id != ADMIN_ID:
    return

  conn = sqlite3.connect('economy_game.db')
  cursor = conn.cursor()
  cursor.execute(
      'SELECT user_id, username, wallet, bank, is_banned FROM users LIMIT 20'
  )
  users = cursor.fetchall()
  cursor.execute('SELECT COUNT(*) FROM users')
  total_users = cursor.fetchone()[0]
  conn.close()

  text = (
      f'📊 **آمار کلی:** {total_users} کاربر ثبت‌نام کرده‌اند.\n\n📋 **لیست'
      ' آخرین کاربران:**\n'
  )
  for u in users:
    ban_status = ' 🚫[مسدود]' if u[4] == 1 else ''
    uname = f'@{u[1]}' if u[1] else 'بدون یوزرنیم'
    text += (
        f'🆔 `{u[0]}` | {uname}\n💵 کیف: {u[2]:,} | 🏦 بانک:'
        f' {u[3]:,}{ban_status}\n-------------------\n'
    )

  bot.send_message(message.chat.id, text, parse_mode='Markdown')


@bot.message_handler(func=lambda m: m.text == '🔍 جستجوی کاربر')
def admin_search_start(message):
  if message.from_user.id != ADMIN_ID:
    return
  msg = bot.send_message(
      message.chat.id,
      'آیدی عددی یا یوزرنیم کاربر (بدون @) را جهت جستجو بفرستید:',
  )
  bot.register_next_step_handler(msg, process_admin_search)


def process_admin_search(message):
  query = message.text.replace('@', '').strip()
  conn = sqlite3.connect('economy_game.db')
  cursor = conn.cursor()
  if query.isdigit():
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (int(query),))
  else:
    cursor.execute('SELECT * FROM users WHERE username = ?', (query,))
  user = cursor.fetchone()
  conn.close()

  if not user:
    bot.send_message(message.chat.id, '❌ کاربر یافت نشد!')
    return

  text = (
      f'🔍 **اطلاعات کاربر:**\n\n🆔 آیدی: `{user[0]}`\n👤 یوزرنیم:'
      f' @{user[1]}\n💵 کیف پول: {user[2]:,} | 🏦 بانک: {user[3]:,}\n⭐ لول:'
      f' {user[4]} | 🚫 مسدود: {"بله" if user[7]==1 else "خیر"}'
  )
  bot.send_message(message.chat.id, text, parse_mode='Markdown')


@bot.message_handler(func=lambda m: m.text == '💰 تغییر موجودی کاربر')
def admin_change_wallet_start(message):
  if message.from_user.id != ADMIN_ID:
    return
  msg = bot.send_message(
      message.chat.id,
      'اطلاعات را به شکل زیر بفرستید:\n\n`آیدی_عددی مبلغ`\nمثال برای اضافه'
      ' کردن 5000 سکه:\n`123456789 5000`\nمثال برای کم کردن 2000'
      ' سکه:\n`123456789 -2000`',
      parse_mode='Markdown',
  )
  bot.register_next_step_handler(msg, process_admin_change_wallet)


def process_admin_change_wallet(message):
  try:
    parts = message.text.split()
    uid = int(parts[0])
    amount = int(parts[1])
    update_wallet(uid, amount)
    bot.send_message(
        message.chat.id, f'✅ موجودی کیف پول کاربر {uid} به میزان {amount} تغییر یافت.'
    )
  except Exception:
    bot.send_message(message.chat.id, '❌ فرمت نامعتبر است.')


@bot.message_handler(func=lambda m: m.text == '⭐ تغییر لول کاربر')
def admin_change_lvl_start(message):
  if message.from_user.id != ADMIN_ID:
    return
  msg = bot.send_message(
      message.chat.id,
      'فرمت بفرستید:\n`آیدی_عددی لول_جدید`\nمثال:\n`123456789 5`',
      parse_mode='Markdown',
  )
  bot.register_next_step_handler(msg, process_admin_change_lvl)


def process_admin_change_lvl(message):
  try:
    parts = message.text.split()
    uid = int(parts[0])
    lvl = int(parts[1])
    conn = sqlite3.connect('economy_game.db')
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE users SET level = ? WHERE user_id = ?', (lvl, uid)
    )
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f'✅ لول کاربر {uid} به {lvl} تغییر کرد.')
  except Exception:
    bot.send_message(message.chat.id, '❌ فرمت نامعتبر.')


@bot.message_handler(
    func=lambda m: m.text == '🚫 مسدود کاربر' or m.text == '✅ رفع مسدود'
)
def admin_ban_unban(message):
  if message.from_user.id != ADMIN_ID:
    return
  action = 'ban' if '🚫' in message.text else 'unban'
  msg = bot.send_message(
      message.chat.id, f'آیدی عددی کاربر جهت {message.text} را وارد کنید:'
  )
  bot.register_next_step_handler(
      msg, lambda m: process_ban_unban(m, action)
  )


def process_ban_unban(message, action):
  if not message.text.isdigit():
    bot.send_message(message.chat.id, '❌ فقط عدد وارد کنید.')
    return
  uid = int(message.text)
  status = 1 if action == 'ban' else 0
  conn = sqlite3.connect('economy_game.db')
  cursor = conn.cursor()
  cursor.execute(
      'UPDATE users SET is_banned = ? WHERE user_id = ?', (status, uid)
  )
  conn.commit()
  conn.close()
  bot.send_message(
      message.chat.id,
      f'✅ وضعیت مسدودی کاربر {uid} به {"مسدود" if status==1 else "آزاد"} تغییر'
      ' یافت.',
      )
# ==========================================
# بخش 8 از 8: اصلاح بخش فروشگاه و استارت ربات
# ==========================================
@bot.message_handler(func=lambda m: m.text == "➕ اضافه کردن ماشین")
def add_car_start(message):
  if message.from_user.id != ADMIN_ID:
    return
  msg = bot.send_message(
      message.chat.id,
      "نام ماشین و قیمت آن را با علامت `-` بفرستید:\n\nفرمت:\n`نام ماشین -"
      " قیمت`\nمثال:\n`پراید - 50000`",
      parse_mode="Markdown",
  )
  bot.register_next_step_handler(
      msg, lambda m: process_add_shop(m, category="car")
  )


@bot.message_handler(func=lambda m: m.text == "➕ اضافه کردن خانه")
def add_house_start(message):
  if message.from_user.id != ADMIN_ID:
    return
  msg = bot.send_message(
      message.chat.id,
      "نام خانه/املاک و قیمت آن را با علامت `-` بفرستید:\n\nفرمت:\n`نام خانه -"
      " قیمت`\nمثال:\n`ویلا ساحلی - 500000`",
      parse_mode="Markdown",
  )
  bot.register_next_step_handler(
      msg, lambda m: process_add_shop(m, category="house")
  )


def process_add_shop(message, category):
  try:
    parts = message.text.split("-")
    name = parts[0].strip()
    price = int(parts[1].strip())

    if add_shop_item(name, category, price):
      bot.send_message(
          message.chat.id,
          f"✅ آیتم **{name}** با موفقیت در دسته {category} و با قیمت {price:,}"
          " ثبت شد.",
          parse_mode="Markdown",
      )
    else:
      bot.send_message(message.chat.id, "❌ خطایی رخ داد یا نام آیتم تکراری است.")
  except Exception:
    bot.send_message(
        message.chat.id,
        "❌ فرمت ارسال اشتباه است! باید به صورت `نام - قیمت` فرستاده شود.",
        parse_mode="Markdown",
    )


@bot.message_handler(func=lambda m: m.text == "✏️ تغییر قیمت آیتم")
def change_price_start(message):
  if message.from_user.id != ADMIN_ID:
    return
  items = get_shop_items()
  if not items:
    bot.send_message(message.chat.id, "هیچ آیتمی در فروشگاه موجود نیست.")
    return

  text = "📜 **لیست آیتم‌های فروشگاه:**\n\n"
  for item in items:
    text += f"🔹 `{item[0]}` (دسته: {item[1]}) ➔ {item[2]:,} سکه\n"

  text += "\nبرای تغییر قیمت فرمت زیر را فرستید:\n`نام دقیق آیتم - قیمت جدید`"
  msg = bot.send_message(message.chat.id, text, parse_mode="Markdown")
  bot.register_next_step_handler(msg, process_change_price)


def process_change_price(message):
  try:
    parts = message.text.split("-")
    name = parts[0].strip()
    new_price = int(parts[1].strip())

    if update_item_price(name, new_price):
      bot.send_message(
          message.chat.id,
          f"✅ قیمت آیتم **{name}** با موفقیت به {new_price:,} سکه به روز شد.",
          parse_mode="Markdown",
      )
    else:
      bot.send_message(
          message.chat.id, "❌ آیتمی با این نام دقیق پیدا نشد!"
      )
  except Exception:
    bot.send_message(
        message.chat.id, "❌ فرمت ورودی اشتباه است. (مثال: پراید - 60000)"
    )


@bot.message_handler(func=lambda m: m.text == "🔙 بازگشت به منوی اصلی")
def back_to_main(message):
  send_welcome(message)


# اجرای ربات
if __name__ == "__main__":
  print("ربات بازی اقتصادی KiAN با موفقیت آنلاین شد...")
  bot.infinity_polling(skip_pending=True)
    
