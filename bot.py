import telebot
from telebot import types

TOKEN = '8328122794:AAG67dIJIsz5tqgtVF0BHo80aZWIGtECc-A'
bot = telebot.TeleBot(TOKEN)

# حافظه موقت برای ذخیره تنظیمات کاربران
user_data = {}

def get_config(user_id):
    if user_id not in user_data:
        user_data[user_id] = {
            'channel_id': None,
            'btn_text': None,
            'btn_url': None,
            'state': None
        }
    return user_data[user_id]

def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('📝 ارسال پست به کانال'),
        types.KeyboardButton('🔗 تنظیم دکمه شیشه‌ای')
    )
    markup.add(
        types.KeyboardButton('📢 تنظیم آیدی کانال'),
        types.KeyboardButton('🗑 حذف دکمه شیشه‌ای')
    )
    return markup

@bot.message_handler(commands=['start', 'cancel'])
def start_cmd(message):
    config = get_config(message.from_user.id)
    config['state'] = None
    
    text = (
        "سلام! 🤖 به پنل مدیریت کانال خوش آمدید.\n\n"
        "از دکمه‌های زیر برای تنظیم آیدی کانال، لینک شیشه‌ای و ارسال پست استفاده کنید."
    )
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard())

@bot.message_handler(func=lambda m: m.text == '📢 تنظیم آیدی کانال')
def set_channel_prompt(message):
    config = get_config(message.from_user.id)
    config['state'] = 'waiting_for_channel'
    bot.send_message(
        message.chat.id, 
        "لطفاً آیدی کانال خود را همراه با `@` بفرستید.\nمثال: `@MyChannel`",
        reply_markup=main_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == '🔗 تنظیم دکمه شیشه‌ای')
def set_link_prompt(message):
    config = get_config(message.from_user.id)
    config['state'] = 'waiting_for_link'
    msg = (
        "عنوان دکمه و لینک خود را با علامت **|** از هم جدا کرده و بفرستید.\n\n"
        "**فرمت ارسال:**\n"
        "`عنوان دکمه | https://t.me/example`\n\n"
        "مثال:\n"
        "`عضویت در کانال | https://t.me/MyChannel`"
    )
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == '🗑 حذف دکمه شیشه‌ای')
def remove_button(message):
    config = get_config(message.from_user.id)
    config['btn_text'] = None
    config['btn_url'] = None
    bot.send_message(message.chat.id, "✅ دکمه شیشه‌ای با موفقیت حذف شد.")

@bot.message_handler(func=lambda m: m.text == '📝 ارسال پست به کانال')
def prepare_post(message):
    config = get_config(message.from_user.id)
    if not config['channel_id']:
        bot.send_message(message.chat.id, "❌ ابتدا از بخش «📢 تنظیم آیدی کانال» آیدی کانال خود را وارد کنید.")
        return

    config['state'] = 'waiting_for_post'
    
    status_link = f"تنظیم شده ({config['btn_text']})" if config['btn_text'] else "تنظیم نشده"
    bot.send_message(
        message.chat.id, 
        f"پست خود را ارسال کنید (متن، عکس، ویدیو، فایل و...).\n\n"
        f"📢 **کانال مقصد:** `{config['channel_id']}`\n"
        f"🔗 **دکمه شیشه‌ای:** {status_link}\n\n"
        f"هر پیامی بفرستید مستقیماً به کانال ارسال می‌شود.",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: True, content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'animation'])
def handle_user_inputs(message):
    config = get_config(message.from_user.id)
    state = config['state']

    # ۱. دریافت و ثبت آیدی کانال
    if state == 'waiting_for_channel':
        ch_id = message.text.strip()
        if not ch_id.startswith('@') and not ch_id.startswith('-100'):
            ch_id = '@' + ch_id
        config['channel_id'] = ch_id
        config['state'] = None
        bot.send_message(message.chat.id, f"✅ کانال مقصد روی `{ch_id}` تنظیم شد.", parse_mode="Markdown")
        return

    # ۲. دریافت و ثبت دکمه شیشه‌ای
    if state == 'waiting_for_link':
        if '|' in message.text:
            parts = message.text.split('|', 1)
            title = parts[0].strip()
            url = parts[1].strip()

            if not (url.startswith('http://') or url.startswith('https://') or url.startswith('t.me/')):
                url = 'https://' + url

            config['btn_text'] = title
            config['btn_url'] = url
            config['state'] = None
            bot.send_message(message.chat.id, f"✅ دکمه شیشه‌ای ذخیره شد:\n[ {title} ] ➔ {url}")
        else:
            bot.send_message(message.chat.id, "❌ فرمت نادرست است! لطفاً عنوان و لینک را با علامت | جدا کنید.\nمثال: `ورود به سایت | https://google.com`", parse_mode="Markdown")
        return

    # ۳. ارسال پست به کانال
    if state == 'waiting_for_post':
        channel_id = config['channel_id']
        
        # ساخت دکمه شیشه‌ای در صورت وجود
        inline_markup = None
        if config['btn_text'] and config['btn_url']:
            inline_markup = types.InlineKeyboardMarkup()
            inline_markup.add(types.InlineKeyboardButton(text=config['btn_text'], url=config['btn_url']))

        try:
            # ارسال دقیق پست به کانال
            bot.copy_message(
                chat_id=channel_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=inline_markup
            )
            bot.send_message(message.chat.id, "🚀 پست با موفقیت در کانال منتشر شد!")
        except Exception as e:
            bot.send_message(
                message.chat.id, 
                f"❌ **خطا در ارسال پست!**\n\n"
                f"• مطمئن شوید ربات در کانال `{channel_id}` **ادمین** است و دسترسی ارسال پیام دارد.",
                parse_mode="Markdown"
            )

print("ربات مدیریت کانال فعال شد...")
bot.infinity_polling()
    
