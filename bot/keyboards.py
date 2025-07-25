from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("💰 My Balance", callback_data='my_balance'),
         InlineKeyboardButton("👥 Refer Friends", callback_data='refer_friends')],
        [InlineKeyboardButton("📝 My Referrals", callback_data='my_referrals'),
         InlineKeyboardButton("💸 Withdraw", callback_data='withdraw')],
        [InlineKeyboardButton("🏆 Top Referrers", callback_data='top_referrers'),
         InlineKeyboardButton("📊 Statistics", callback_data='statistics')],
        [InlineKeyboardButton("⚙️ Account Settings", callback_data='account_settings'),
         InlineKeyboardButton("❓ Help & Support", callback_data='help_support')]
    ]
    return InlineKeyboardMarkup(keyboard)

def verify_join_keyboard(channel_username):
    keyboard = [
        [InlineKeyboardButton("✅ Verify", callback_data='verify_join')],
        [InlineKeyboardButton("Join Channel", url=f"https://t.me/{channel_username}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def request_phone_keyboard():
    keyboard = [[KeyboardButton("Share My Phone Number", request_contact=True)]]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

# ... (Add other keyboards for withdrawal methods, settings, etc.)
