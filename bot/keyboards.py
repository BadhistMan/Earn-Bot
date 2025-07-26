# bot/keyboards.py
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

def verify_join_keyboard():
    channel_username = os.environ.get('FORCE_JOIN_CHANNEL', '').lstrip('@')
    keyboard = [[InlineKeyboardButton("✅ I Have Joined", callback_data='verify_join')],[InlineKeyboardButton("➡️ Join Channel", url=f"https://t.me/{channel_username}")]]
    return InlineKeyboardMarkup(keyboard)

def request_phone_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("📱 Share My Phone Number", request_contact=True)]], one_time_keyboard=True, resize_keyboard=True)

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("💰 My Balance", callback_data='my_balance'), InlineKeyboardButton("👥 Refer Friends", callback_data='refer_friends')],
        [InlineKeyboardButton("📝 My Referrals", callback_data='my_referrals'), InlineKeyboardButton("💸 Withdraw", callback_data='withdraw')],
        [InlineKeyboardButton("🏆 Top Referrers", callback_data='top_referrers'), InlineKeyboardButton("📊 Statistics", callback_data='statistics')],
        [InlineKeyboardButton("❓ Help & Support", callback_data='help_support')]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_to_menu_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main Menu", callback_data='main_menu')]])

def withdrawal_methods_keyboard():
    keyboard = [
        [InlineKeyboardButton("💵 Telebirr", callback_data='withdraw_telebirr'), InlineKeyboardButton("🏦 CBE Bank", callback_data='withdraw_cbe')],
        [InlineKeyboardButton("💎 USDT (TRC20)", callback_data='withdraw_usdt')],
        [InlineKeyboardButton("⬅️ Back", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 View Statistics", callback_data='admin_stats')],
        [InlineKeyboardButton("📢 Broadcast Message", callback_data='admin_broadcast')],
        [InlineKeyboardButton("⏳ Pending Withdrawals", callback_data='admin_withdrawals')]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_withdrawal_keyboard(withdrawal_id):
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve", callback_data=f'admin_approve_{withdrawal_id}'), InlineKeyboardButton("❌ Reject", callback_data=f'admin_reject_{withdrawal_id}')]])
