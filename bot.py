import json
import os
import random
import telebot
from telebot import types

# --- تنظیمات اصلی ---
TOKEN = '8328122794:AAG67dIJIsz5tqgtVF0BHo80aZWIGtECc-A'
ADMIN_ID = 7530457395
ADMIN_USERNAME = '@vcxczc'
DB_FILE = 'database.json'

bot = telebot.TeleBot(TOKEN)

# --- متغیرهای جهانی ---
user_data = {}
locked_channels = []
pending_free_stars = []
withdraw_requests = []


# --- مدیریت دیتابیس ---
def load_data():
    global locked_channels, pending_free_stars, withdraw_requests, user_data
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                locked_channels = data.get('locked_channels', [])
                pending_free_stars = data.get('pending_free_stars', [])
                withdraw_requests = data.get('withdraw_requests', [])
                user_data = {int(k): v for k, v in data.get('user_data', {}).items()}
        except Exception as e:
            print(f"خطا در بارگذاری دیتابیس: {e}")


def save_data():
    data = {
        'locked_channels': locked_channels,
        'pending_free_stars': pending_free_stars,
        'withdraw_requests': withdraw_requests,
        'user_data': user_data,
    }
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"خطا در ذخیره دیتابیس: {e}")


load_data()


# --- توابع ابزاری ---
def get_config(user_id):
    user_id = int(user_id)
    if user_id not in user_data:
        user_data[user_id] = {
            'channel_id': None,
            'btn_text': None,
            'btn_url': None,
            'state': None,
            'captcha_answer': None,
            'captcha_passed': False,
            'generated_code': None,
        }
        save_data()
    return user_data[user_id]


def clean_channel_target(ch):
    ch = str(ch).strip()
    if ch.startswith('-100') or (ch.startswith('-') and ch[1:].isdigit()):
        return int(ch)
    if 't.me/' in ch:
        ch = ch.split('t.me/')[-1].replace('/', '')
        if ch.startswith('+'):
            return ch
    if not ch.startswith('@') and not ch.startswith('+'):
        ch = '@' + ch
    return ch


def get_channel_url(ch):
    ch = str(ch).strip()
    if ch.startswith('http://') or ch.startswith('https://'):
        return ch
    if ch.startswith('@'):
        return f"https://t.me/{ch[1:]}"
    if ch.startswith('+'):
        return f"https://t.me/{ch}"
    return f"https://t.me/{ch}"


def check_user_joined_all(user_id):
    if not locked_channels:
        return True, []

    not_joined = []
    for ch in locked_channels:
        target = clean_channel_target(ch)
        try:
            member = bot.get_chat_member(target, user_id)
            if member.status in ['left', 'kicked']:
                not_joined.append(ch)
        except Exception as e:
            print(f"خطا در بررسی کانال {target}: {e}")
            not_joined.append(ch)

    return len(not_joined) == 0, not_joined


def send_force_join_msg(chat_id, missing_channels):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for idx, ch in enumerate(missing_channels, 1):
        url = get_channel_url(ch)
        display_name = (
            ch if (ch.startswith('@') or 't.me' in ch) else f"کانال شماره {idx}"
        )
        markup.add(
            types.InlineKeyboardButton(
                text=f"📢 عضویت در {display_name}", url=url
            )
        )

    markup.add(
        types.InlineKeyboardButton(
            text="✅ عضو شدم", callback_data="check_start_join"
        )
    )

    text = (
        f"🔒 **جهت استفاده از ربات، لطفاً ابتدا در کانال‌های زیر عضو شوید:**\n\n"
        f"🆔 **پشتیبانی ادمین:** {ADMIN_USERNAME}\n\n"
        f"پس از عضویت، روی دکمه **«✅ عضو شدم»** کلیک کنید."
    )
    try:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        bot.send_message(
            chat_id,
            f"🔒 جهت استفاده از ربات در کانال‌های قفل‌شده عضو شوید.\nپشتیبانی ادمین: {ADMIN_USERNAME}",
            reply_markup=markup,
        )


# --- کیبوردها ---
def main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('🌟 استارز رایگان'),
        types.KeyboardButton('💸 درخواست برداشت'),
    )
    markup.add(
        types.KeyboardButton('📝 ارسال پست به کانال'),
        types.KeyboardButton('📢 تنظیم آیدی کانال'),
    )
    markup.add(
        types.KeyboardButton('🔗 تنظیم دکمه شیشه‌ای'),
        types.KeyboardButton('🗑 حذف دکمه شیشه‌ای'),
    )
    markup.add(types.KeyboardButton('🧪 تست کانال'))

    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton('👑 پنل مدیریت ادمین'))

    return markup


def admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('📥 سفارش‌های استارز رایگان'),
        types.KeyboardButton('📥 درخواست‌های برداشت'),
    )
    markup.add(
        types.KeyboardButton('🔒 تنظیم قفل کانال‌ها'),
        types.KeyboardButton('🔙 بازگشت به منوی اصلی'),
    )
    return markup


# --- دستورات شروع و عمومی ---
@bot.message_handler(commands=['start', 'cancel'])
def start_cmd(message):
    user_id = message.from_user.id
    config = get_config(user_id)
    config['state'] = None
    save_data()

    is_joined, missing = check_user_joined_all(user_id)
    if not is_joined:
        send_force_join_msg(message.chat.id, missing)
        return

    welcome_msg = "سلام! 🤖 به ربات مدیریت کانال و دریافت استارز خوش آمدید."
    if user_id == ADMIN_ID:
        welcome_msg += "\n\n👑 **ورود به عنوان ادمین اصلی**"

    bot.send_message(
        message.chat.id,
        welcome_msg,
        reply_markup=main_keyboard(user_id),
        parse_mode="Markdown",
    )


@bot.callback_query_handler(
    func=lambda call: call.data == 'check_start_join'
)
def check_start_join_callback(call):
    is_joined, missing = check_user_joined_all(call.from_user.id)
    if is_joined:
        bot.answer_callback_query(
            call.id, "✅ عضویت شما تایید شد!", show_alert=True
        )
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

        config = get_config(call.from_user.id)
        if config.get('state') == 'waiting_for_join_check':
            continue_free_stars_flow(call.message.chat.id, call.from_user.id)
        else:
            bot.send_message(
                call.message.chat.id,
                "✅ عضویت تایید شد. خوش آمدید!",
                reply_markup=main_keyboard(call.from_user.id),
            )
    else:
        bot.answer_callback_query(
            call.id, "❌ هنوز در تمامی کانال‌ها عضو نشده‌اید!", show_alert=True
        )
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        send_force_join_msg(call.message.chat.id, missing)


@bot.message_handler(
    func=lambda m: m.text == '👑 پنل مدیریت ادمین' and m.from_user.id == ADMIN_ID
)
def admin_panel(message):
    bot.send_message(
        message.chat.id,
        "👑 **پنل مدیریت ادمین**",
        reply_markup=admin_keyboard(),
        parse_mode="Markdown",
    )


@bot.message_handler(func=lambda m: m.text == '🔙 بازگشت به منوی اصلی')
def back_to_main(message):
    config = get_config(message.from_user.id)
    config['state'] = None
    save_data()
    bot.send_message(
        message.chat.id,
        "به منوی اصلی بازگشتید.",
        reply_markup=main_keyboard(message.from_user.id),
    )


@bot.message_handler(
    func=lambda m: m.text == '🔒 تنظیم قفل کانال‌ها' and m.from_user.id == ADMIN_ID
)
def lock_channels_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            "➕ افزودن کانال به قفل", callback_data="add_lock_channel"
        ),
        types.InlineKeyboardButton(
            "🗑 پاکسازی تمامی قفل‌ها", callback_data="clear_lock_channels"
        ),
    )
    ch_list = (
        "\n".join([f"• `{c}`" for c in locked_channels])
        if locked_channels
        else "⚠️ هیچ کانالی قفل نشده است."
    )
    bot.send_message(
        message.chat.id,
        f"🔒 **مدیریت قفل کانال‌ها**\n\n**کانال‌های"
        f" قفل‌شده:**\n{ch_list}\n\n🆔 **پشتیبانی ادمین:**"
        f" {ADMIN_USERNAME}\n⚠️ *نکته:* ربات باید در کانال‌های قفل‌شده ادمین باشد.",
        reply_markup=markup,
        parse_mode="Markdown",
    )


@bot.callback_query_handler(
    func=lambda call: call.data in ['add_lock_channel', 'clear_lock_channels']
)
def handle_lock_callbacks(call):
    if call.from_user.id != ADMIN_ID:
        return
    if call.data == 'add_lock_channel':
        config = get_config(call.from_user.id)
        config['state'] = 'waiting_for_lock_channel'
        save_data()
        bot.send_message(
            call.message.chat.id,
            "آیدی یا لینک کانال را ارسال کنید:\nمثال: `@MyChannel` یا"
            " `-100123456789`",
        )
        bot.answer_callback_query(call.id)
    elif call.data == 'clear_lock_channels':
        locked_channels.clear()
        save_data()
        bot.send_message(call.message.chat.id, "✅ قفل تمامی کانال‌ها پاک شد.")
        bot.answer_callback_query(call.id)
# --- جریان استارز رایگان ---
@bot.message_handler(func=lambda m: m.text == '🌟 استارز رایگان')
def free_stars_start(message):
    user_id = message.from_user.id
    config = get_config(user_id)
    
    # ۱. کچپا
    if not config['captcha_passed']:
        num1 = random.randint(1, 9)
        num2 = random.randint(1, 9)
        config['captcha_answer'] = str(num1 + num2)
        config['state'] = 'waiting_for_captcha'
        save_data()
        bot.send_message(message.chat.id, f"🧠 **تایید هویت (کچپا):**\nلطفاً حاصل عبارت زیر را ارسال کنید:\n\n`{num1} + {num2} = ?`", parse_mode="Markdown")
        return

    # ۲. بررسی قفل کانال‌ها
    is_joined, missing = check_user_joined_all(user_id)
    if not is_joined:
        config['state'] = 'waiting_for_join_check'
        save_data()
        send_force_join_msg(message.chat.id, missing)
        return

    continue_free_stars_flow(message.chat.id, user_id)

def continue_free_stars_flow(chat_id, user_id):
    config = get_config(user_id)
    generated_code = str(random.randint(100000, 999999))
    config['generated_code'] = generated_code
    config['state'] = 'waiting_for_user_post_link'
    save_data()
    
    msg_text = (
        f"✅ **عضویت شما در کانال‌ها تایید شد!**\n\n"
        f"🔢 **کد اختصاصی شما:** `{generated_code}`\n"
        f"*(روی کد بزنید تا کپی شود)*\n\n"
        f"📩 **راهنما:** کد مورد نظر رو واسه ادمین بفرستید ({ADMIN_USERNAME})\n\n"
        f"🔗 اکنون **لینک پستی** که می‌خواهید استارز به آن زده شود را ارسال کنید:\n"
        f"مثال: `https://t.me/MyChannel/123`"
    )
    bot.send_message(chat_id, msg_text, parse_mode="Markdown")

# --- مدیریت سفارش‌های استارز رایگان توسط ادمین ---
@bot.message_handler(func=lambda m: m.text == '📥 سفارش‌های استارز رایگان' and m.from_user.id == ADMIN_ID)
def show_free_stars_orders(message):
    pending = [p for p in pending_free_stars if p['status'] == 'pending']
    if not pending:
        bot.send_message(message.chat.id, "📥 هیچ سفارشی در صف انتظار نیست.")
        return

    for item in pending:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ انجام شد", callback_data=f"approve_stars_{item['id']}"),
            types.InlineKeyboardButton("❌ رد شد", callback_data=f"reject_stars_{item['id']}")
        )
        bot.send_message(
            message.chat.id,
            f"🌟 **سفارش استارز رایگان #{item['id']}**\n\n"
            f"👤 کاربر: `{item['user_id']}` (@{item['username']})\n"
            f"🔢 کد عددی کاربر: `{item['code']}`\n"
            f"🔗 لینک پست: {item['post_link']}",
            reply_markup=markup,
            parse_mode="Markdown"
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith(('approve_stars_', 'reject_stars_')))
def handle_stars_order_action(call):
    if call.from_user.id != ADMIN_ID:
        return

    action, order_id = call.data.rsplit('_', 1)
    order_id = int(order_id)
    
    order = next((p for p in pending_free_stars if p['id'] == order_id), None)
    if not order or order['status'] != 'pending':
        bot.answer_callback_query(call.id, "این سفارش قبلاً تعیین تکلیف شده است.", show_alert=True)
        return

    if action == 'approve_stars':
        order['status'] = 'approved'
        save_data()
        bot.edit_message_text(f"{call.message.text}\n\n✅ **وضعیت: انجام شد.**", chat_id=call.message.chat.id, message_id=call.message.message_id)
        try:
            bot.send_message(order['user_id'], f"🎉 **سفارش استارز شما با موفقیت انجام شد!**\n\n🔢 کد پیگیری: `{order['code']}`\n🔗 لینک: {order['post_link']}", parse_mode="Markdown")
        except Exception:
            pass
    else:
        order['status'] = 'rejected'
        save_data()
        bot.edit_message_text(f"{call.message.text}\n\n❌ **وضعیت: رد شد.**", chat_id=call.message.chat.id, message_id=call.message.message_id)
        try:
            bot.send_message(order['user_id'], f"❌ **سفارش استارز شما رد شد.**\n🔢 کد پیگیری: `{order['code']}`", parse_mode="Markdown")
        except Exception:
            pass

# --- تنظیمات کانال و پست‌گذاری ---
@bot.message_handler(func=lambda m: m.text == '📢 تنظیم آیدی کانال')
def set_channel_prompt(message):
    config = get_config(message.from_user.id)
    config['state'] = 'waiting_for_channel'
    save_data()
    bot.send_message(message.chat.id, "📢 آیدی کانال مقصد را بفرستید (مثال: `@MyChannel`):")

@bot.message_handler(func=lambda m: m.text == '🔗 تنظیم دکمه شیشه‌ای')
def set_glass_btn_prompt(message):
    config = get_config(message.from_user.id)
    config['state'] = 'waiting_for_link'
    save_data()
    bot.send_message(message.chat.id, "🔗 عنوان و لینک را با `|` جدا کنید:\nمثال: `کانال ما | https://t.me/MyChannel`", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == '🗑 حذف دکمه شیشه‌ای')
def remove_glass_btn(message):
    config = get_config(message.from_user.id)
    config['btn_text'] = None
    config['btn_url'] = None
    save_data()
    bot.send_message(message.chat.id, "🗑 دکمه شیشه‌ای حذف شد.")

@bot.message_handler(func=lambda m: m.text == '📝 ارسال پست به کانال')
def send_post_prompt(message):
    config = get_config(message.from_user.id)
    if not config.get('channel_id'):
        bot.send_message(message.chat.id, "⚠️ ابتدا از دکمه «📢 تنظیم آیدی کانال» آیدی کانال خود را ثبت کنید.")
        return
    config['state'] = 'waiting_for_post'
    save_data()
    bot.send_message(message.chat.id, "📝 پستی که می‌خواهید به کانال ارسال شود را بفرستید:")

@bot.message_handler(func=lambda m: m.text == '🧪 تست کانال')
def test_channel_access(message):
    config = get_config(message.from_user.id)
    ch = config.get('channel_id')
    if not ch:
        bot.send_message(message.chat.id, "❌ آیدی کانالی تنظیم نشده است.")
        return
    try:
        test_msg = bot.send_message(ch, "🧪 تست ارتباط ربات...")
        bot.delete_message(ch, test_msg.message_id)
        bot.send_message(message.chat.id, f"✅ ارتباط با کانال `{ch}` برقرار است.", parse_mode="Markdown")
    except Exception:
        bot.send_message(message.chat.id, f"❌ خطا در دسترسی به کانال `{ch}`. مطمئن شوید ربات ادمین است.")

# --- بخش درخواست برداشت ---
@bot.message_handler(func=lambda m: m.text == '💸 درخواست برداشت')
def withdraw_request_prompt(message):
    user_id = message.from_user.id
    is_joined, missing = check_user_joined_all(user_id)
    if not is_joined:
        send_force_join_msg(message.chat.id, missing)
        return

    config = get_config(user_id)
    config['state'] = 'waiting_for_withdraw_amount'
    save_data()
    bot.send_message(message.chat.id, "💸 لطفاً تعداد استارز درخواستی جهت برداشت را به عدد وارد کنید:")

@bot.message_handler(func=lambda m: m.text == '📥 درخواست‌های برداشت' and m.from_user.id == ADMIN_ID)
def show_withdraw_requests(message):
    pending = [w for w in withdraw_requests if w['status'] == 'pending']
    if not pending:
        bot.send_message(message.chat.id, "📥 هیچ درخواست برداشتی در صف انتظار نیست.")
        return

    for item in pending:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ تسویه شد", callback_data=f"approve_w_{item['id']}"),
            types.InlineKeyboardButton("❌ رد شد", callback_data=f"reject_w_{item['id']}")
        )
        bot.send_message(
            message.chat.id,
            f"💸 **درخواست برداشت #{item['id']}**\n\n👤 کاربر: `{item['user_id']}` (@{item['username']})\n💰 مقدار: `{item['amount']}` استارز\nℹ️ اطلاعات: `{item['info']}`",
            reply_markup=markup,
            parse_mode="Markdown"
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith(('approve_w_', 'reject_w_')))
def handle_withdraw_action(call):
    if call.from_user.id != ADMIN_ID:
        return

    action, req_id = call.data.rsplit('_', 1)
    req_id = int(req_id)
    
    req = next((w for w in withdraw_requests if w['id'] == req_id), None)
    if not req or req['status'] != 'pending':
        bot.answer_callback_query(call.id, "تعیین تکلیف شده است.", show_alert=True)
        return

    if action == 'approve_w':
        req['status'] = 'approved'
        save_data()
        bot.edit_message_text(f"{call.message.text}\n\n✅ **تسویه شد.**", chat_id=call.message.chat.id, message_id=call.message.message_id)
        try:
            bot.send_message(req['user_id'], f"🎉 درخواست برداشت {req['amount']} استارز شما تسویه شد.")
        except Exception:
            pass
    else:
        req['status'] = 'rejected'
        save_data()
        bot.edit_message_text(f"{call.message.text}\n\n❌ **رد شد.**", chat_id=call.message.chat.id, message_id=call.message.message_id)
        try:
            bot.send_message(req['user_id'], f"❌ درخواست برداشت {req['amount']} استارز شما رد شد.")
        except Exception:
            pass

# --- پردازش کلیه ورودی‌ها ---
@bot.message_handler(func=lambda m: True, content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'animation'])
def handle_all_inputs(message):
    user_id = message.from_user.id
    config = get_config(user_id)
    state = config.get('state')

    if state == 'waiting_for_lock_channel' and user_id == ADMIN_ID:
        ch_input = message.text.strip() if message.text else ""
        if ch_input and ch_input not in locked_channels:
            locked_channels.append(ch_input)
            
        config['state'] = None
        save_data()
        bot.send_message(message.chat.id, f"✅ کانال `{ch_input}` به قفل اضافه شد.", parse_mode="Markdown")
        return

    if not state:
        return

    if state == 'waiting_for_captcha':
        if message.text and message.text.strip() == config.get('captcha_answer'):
            config['captcha_passed'] = True
            config['state'] = None
            save_data()
            bot.send_message(message.chat.id, "✅ پاسخ کچپا درست بود!")
            free_stars_start(message)
        else:
            bot.send_message(message.chat.id, "❌ پاسخ نادرست است! دوباره سعی کنید.")
        return

    if state == 'waiting_for_user_post_link':
        link = message.text.strip() if message.text else ""
        if 't.me/' in link:
            order_id = len(pending_free_stars) + 1
            code = config.get('generated_code', '------')
            
            pending_free_stars.append({
                'id': order_id,
                'user_id': user_id,
                'username': message.from_user.username or "ندارد",
                'code': code,
                'post_link': link,
                'status': 'pending'
            })
            
            config['state'] = None
            save_data()
            
            bot.send_message(
                message.chat.id, 
                f"📥 **سفارش شما با موفقیت ثبت شد!**\n\n🔢 کد پیگیری شما: `{code}`\nدرخواست برای بررسی و واریز ادمین ارسال گردید.",
                parse_mode="Markdown"
            )
            
            try:
                bot.send_message(
                    ADMIN_ID,
                    f"🚨 **سفارش استارز رایگان جدید!**\n\n👤 کاربر: `{user_id}` (@{message.from_user.username})\n🔢 کد عددی: `{code}`\n🔗 لینک پست: {link}",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        else:
            bot.send_message(message.chat.id, "❌ لینک ارسال شده نامعتبر است. لطفاً یک لینک صحیح تلگرام ارسال کنید.")
        return

    if state == 'waiting_for_withdraw_amount':
        if message.text and message.text.isdigit():
            amount = int(message.text)
            config['temp_withdraw_amount'] = amount
            config['state'] = 'waiting_for_withdraw_info'
            save_data()
            bot.send_message(message.chat.id, "📝 لطفاً اطلاعات حساب یا آیدی خود را جهت دریافت تسویه وارد کنید:")
        else:
            bot.send_message(message.chat.id, "❌ لطفاً فقط یک عدد معتبر وارد کنید.")
        return

    if state == 'waiting_for_withdraw_info':
        info = message.text.strip() if message.text else "بدون توضیحات"
        amount = config.get('temp_withdraw_amount', 0)
        req_id = len(withdraw_requests) + 1
        
        withdraw_requests.append({
            'id': req_id,
            'user_id': user_id,
            'username': message.from_user.username or "ندارد",
            'amount': amount,
            'info': info,
            'status': 'pending'
        })
        config['state'] = None
        save_data()
        bot.send_message(message.chat.id, f"✅ درخواست برداشت ثبت شد. کد پیگیری: `{req_id}`", parse_mode="Markdown")
        return

    if state == 'waiting_for_channel':
        ch_id = message.text.strip() if message.text else ""
        config['channel_id'] = ch_id if ch_id.startswith('@') or ch_id.startswith('-100') else '@' + ch_id
        config['state'] = None
        save_data()
        bot.send_message(message.chat.id, f"✅ کانال مقصد ثبت شد: `{config['channel_id']}`", parse_mode="Markdown")
        return

    if state == 'waiting_for_link':
        if message.text and '|' in message.text:
            parts = message.text.split('|', 1)
            config['btn_text'] = parts[0].strip()
            config['btn_url'] = parts[1].strip()
            config['state'] = None
            save_data()
            bot.send_message(message.chat.id, "✅ دکمه شیشه‌ای تنظیم شد.")
        else:
            bot.send_message(message.chat.id, "❌ فرمت نادرست است.")
        return

    if state == 'waiting_for_post':
        channel_id = config['channel_id']
        inline_markup = None
        if config.get('btn_text') and config.get('btn_url'):
            inline_markup = types.InlineKeyboardMarkup()
            inline_markup.add(types.InlineKeyboardButton(text=config['btn_text'], url=config['btn_url']))

        try:
            bot.copy_message(chat_id=channel_id, from_chat_id=message.chat.id, message_id=message.message_id, reply_markup=inline_markup)
            config['state'] = None
            save_data()
            bot.send_message(message.chat.id, "🚀 پست به کانال ارسال شد.")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا در ارسال پست: {e}")
        return

# --- اجرای آنلاین ربات ---
if __name__ == '__main__':
    print("ربات با موفقیت فعال شد...")
    bot.infinity_polling(skip_pending=True)
