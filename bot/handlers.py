# bot/handlers.py
import os
import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from . import database as db
from . import keyboards

# --- Environment Variables & Constants ---
ADMIN_ID = int(os.environ.get('ADMIN_TELEGRAM_ID'))
CHANNEL_ID = os.environ.get('FORCE_JOIN_CHANNEL')
REFERRAL_BONUS = 5
MIN_WITHDRAWAL = 100
BONUS_THRESHOLD = 10 # Refer 10 users...
BONUS_AMOUNT = 10    # ...to get a 10 ETB bonus

# --- State definitions for ConversationHandlers ---
(ASK_WITHDRAWAL_METHOD, ASK_WITHDRAWAL_DETAILS, ASK_WITHDRAWAL_AMOUNT) = range(3)
(ASK_BROADCAST_MESSAGE, CONFIRM_BROADCAST) = range(2)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# === USER COMMANDS & REGISTRATION FLOW ======================================
# =============================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        referrer_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
        if referrer_id == user.id: referrer_id = None # Block self-referral
        context.user_data['referrer_id'] = referrer_id
    except (IndexError, ValueError):
        context.user_data['referrer_id'] = None

    if db.user_exists(user.id):
        await show_main_menu(update, "Welcome back!")
        return

    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user.id)
        if member.status not in ['member', 'administrator', 'creator']:
            await send_verification_message(update)
        else:
            await ask_for_phone(update)
    except Exception as e:
        logger.error(f"Error checking channel membership for {user.id}: {e}")
        await update.message.reply_text("Sorry, we couldn't verify your channel membership. Please ensure the bot has admin rights in the channel and try again.")

async def verify_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=query.from_user.id)
    if member.status in ['member', 'administrator', 'creator']:
        await query.message.delete()
        await ask_for_phone(update)
    else:
        await query.answer("You haven't joined the channel yet. Please join to continue.", show_alert=True)

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    phone_number = update.message.contact.phone_number

    if db.user_exists(user.id): return

    referrer_id = context.user_data.get('referrer_id')
    db.add_user(user.id, user.username or user.first_name, phone_number, None, referrer_id)

    if referrer_id:
        db.add_referral(referrer_id, user.id)
        db.update_balance(referrer_id, REFERRAL_BONUS)
        await notify_referrer(context, referrer_id, user)
        
        # --- NEW: Check for Bonus ---
        referral_count = db.get_referral_count(referrer_id)
        if referral_count == BONUS_THRESHOLD:
            db.update_balance(referrer_id, BONUS_AMOUNT)
            await context.bot.send_message(
                chat_id=referrer_id,
                text=f"🎉 **BONUS!** You've reached {BONUS_THRESHOLD} referrals and earned an extra **{BONUS_AMOUNT} ETB**! Keep going!"
            )

    await update.message.reply_text("✅ Registration complete! Welcome.", reply_markup=ReplyKeyboardRemove())
    await show_main_menu(update, "Here is your dashboard:")

# =============================================================================
# === MAIN MENU & BUTTON HANDLERS =============================================
# =============================================================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # User Menu Routes
    if data == 'main_menu': await show_main_menu(update, "Welcome to the main menu:", edit=True)
    elif data == 'my_balance': await my_balance_handler(update)
    elif data == 'refer_friends': await refer_friends_handler(update, context)
    elif data == 'my_referrals': await my_referrals_handler(update)
    elif data == 'top_referrers': await top_referrers_handler(update)
    elif data == 'statistics': await statistics_handler(update)
    elif data == 'help_support': await help_support_handler(update)
    # Admin Menu Routes
    elif data == 'admin_stats': await admin_stats_handler(update)
    elif data == 'admin_withdrawals': await admin_withdrawals_handler(update)
    elif data.startswith('admin_approve_'): await approve_withdrawal(update, context)
    elif data.startswith('admin_reject_'): await reject_withdrawal(update, context)

async def my_balance_handler(update: Update):
    balance = db.get_balance(update.effective_user.id)
    await edit_or_reply(update, f"💰 **My Balance**\n\nYour current balance is: **{balance} ETB**", keyboards.back_to_menu_keyboard())

async def refer_friends_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={update.effective_user.id}"
    text = f"👥 **Refer & Earn**\n\nInvite friends and earn **{REFERRAL_BONUS} ETB** for each one!\n\nYour link:\n`{referral_link}`"
    await edit_or_reply(update, text, keyboards.back_to_menu_keyboard())

async def my_referrals_handler(update: Update):
    referrals = db.get_user_referrals(update.effective_user.id)
    count = len(referrals)
    text = f"📝 **My Referrals ({count})**\n\n" + ("\n".join([f"- @{u[1]}" if u[1] else f"- User ID: {u[0]}" for u in referrals[:20]]) or "You haven't referred anyone yet.")
    await edit_or_reply(update, text, keyboards.back_to_menu_keyboard())

async def top_referrers_handler(update: Update):
    top_users = db.get_top_referrers()
    text = "🏆 **Top 10 Referrers**\n\n" + ("\n".join([f"{i+1}. @{u[0] or 'user'} - {u[1]} referrals" for i, u in enumerate(top_users)]) or "No referrals recorded yet.")
    await edit_or_reply(update, text, keyboards.back_to_menu_keyboard())

async def statistics_handler(update: Update):
    await edit_or_reply(update, f"📊 **Bot Statistics**\n\nTotal Users: **{db.get_total_user_count()}**", keyboards.back_to_menu_keyboard())

async def help_support_handler(update: Update):
    text = f"❓ **Help & Support**\n\n**How it works:** Share your referral link. When a friend joins and completes verification, you earn {REFERRAL_BONUS} ETB.\n\n**Withdrawals:** You need a minimum of {MIN_WITHDRAWAL} ETB. Go to 'Withdraw' to start.\n\n**Bonus:** Get an extra {BONUS_AMOUNT} ETB when you refer {BONUS_THRESHOLD} people!\n\nFor issues, contact the admin."
    await edit_or_reply(update, text, keyboards.back_to_menu_keyboard())

# =============================================================================
# === WITHDRAWAL CONVERSATION =================================================
# =============================================================================
async def start_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    balance = db.get_balance(query.from_user.id)
    if balance < MIN_WITHDRAWAL:
        await query.answer(f"You need at least {MIN_WITHDRAWAL} ETB. Your balance is {balance} ETB.", show_alert=True)
        return ConversationHandler.END
    context.user_data['balance'] = balance
    await query.edit_message_text("💸 **Withdrawal**\n\nPlease select your preferred withdrawal method:", reply_markup=keyboards.withdrawal_methods_keyboard())
    return ASK_WITHDRAWAL_METHOD

async def withdrawal_method_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    context.user_data['withdrawal_method'] = query.data.split('_')[1].upper()
    prompts = {'TELEBIRR': 'Enter your Telebirr phone number:', 'CBE': 'Enter your CBE bank account number:', 'USDT': 'Enter your USDT (TRC20) wallet address:'}
    await query.edit_message_text(text=prompts[context.user_data['withdrawal_method']])
    return ASK_WITHDRAWAL_DETAILS

async def withdrawal_details_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['withdrawal_details'] = update.message.text
    await update.message.reply_text(f"Your balance is {context.user_data['balance']} ETB. How much would you like to withdraw?")
    return ASK_WITHDRAWAL_AMOUNT

async def withdrawal_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = int(update.message.text)
        if not (MIN_WITHDRAWAL <= amount <= context.user_data['balance']):
            await update.message.reply_text(f"Invalid amount. Please enter an amount between {MIN_WITHDRAWAL} and {context.user_data['balance']} ETB.")
            return ASK_WITHDRAWAL_AMOUNT
    except ValueError:
        await update.message.reply_text("Invalid input. Please enter a number."); return ASK_WITHDRAWAL_AMOUNT

    user_id = update.effective_user.id
    method = context.user_data['withdrawal_method']
    details = context.user_data['withdrawal_details']
    withdrawal_id = db.create_withdrawal_request(user_id, method, details, amount)
    
    await update.message.reply_text("✅ Your withdrawal request has been submitted successfully!")
    await show_main_menu(update, "Welcome to the main menu:")
    await notify_admin_of_withdrawal(context, update.effective_user, method, details, amount, withdrawal_id)
    return ConversationHandler.END

# =============================================================================
# === ADMIN PANEL & CONVERSATIONS ============================================
# =============================================================================
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text("🧑‍💻 Welcome to the Admin Panel!", reply_markup=keyboards.admin_panel_keyboard())

async def admin_stats_handler(update: Update):
    text = f"📊 **Bot Statistics**\n\nTotal Users: **{db.get_total_user_count()}**"
    await edit_or_reply(update, text, keyboards.admin_panel_keyboard())

async def admin_withdrawals_handler(update: Update):
    await update.callback_query.edit_message_text("Fetching pending withdrawals...")
    pending = db.get_pending_withdrawals()
    if not pending:
        await edit_or_reply(update, "No pending withdrawals.", keyboards.admin_panel_keyboard())
        return
    await edit_or_reply(update, f"Found {len(pending)} pending withdrawal(s):", keyboards.admin_panel_keyboard())
    for w_id, u_id, u_name, method, details, amount in pending:
        text = f"**Request ID:** {w_id}\n**User:** @{u_name} ({u_id})\n**Method:** {method}\n**Details:** `{details}`\n**Amount:** {amount} ETB"
        await update.effective_message.reply_text(text, reply_markup=keyboards.admin_withdrawal_keyboard(w_id), parse_mode=ParseMode.MARKDOWN)

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text("Please send the message you want to broadcast to all users. To cancel, type /cancel.")
    return ASK_BROADCAST_MESSAGE

async def broadcast_message_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['broadcast_message'] = update.message
    await update.message.reply_text("This is the message you're about to send. Are you sure? Type 'YES' to confirm or /cancel to abort.")
    return CONFIRM_BROADCAST

async def broadcast_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.upper() != 'YES':
        await update.message.reply_text("Broadcast aborted.")
        return await admin_command(update, context)

    await update.message.reply_text("Broadcasting... this may take a while.")
    message = context.user_data['broadcast_message']
    user_ids = db.get_all_user_ids()
    sent_count, failed_count = 0, 0
    for user_id in user_ids:
        try:
            await message.copy(chat_id=user_id)
            sent_count += 1
        except Exception:
            failed_count += 1
    await update.message.reply_text(f"Broadcast complete.\nSent: {sent_count}\nFailed: {failed_count}")
    return ConversationHandler.END

async def approve_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer("Approving...")
    withdrawal_id = int(query.data.split('_')[2])
    db.update_withdrawal_status(withdrawal_id, 'approved')
    await query.edit_message_text(text=query.message.text + "\n\n**Status: ✅ Approved**", parse_mode=ParseMode.MARKDOWN)

async def reject_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer("Rejecting...")
    withdrawal_id = int(query.data.split('_')[2])
    user_to_refund, amount_to_refund = db.get_withdrawal_for_refund(withdrawal_id)
    if user_to_refund: db.update_balance(user_to_refund, amount_to_refund)
    db.update_withdrawal_status(withdrawal_id, 'rejected')
    await query.edit_message_text(text=query.message.text + "\n\n**Status: ❌ Rejected (Amount Refunded)**", parse_mode=ParseMode.MARKDOWN)
    await context.bot.send_message(chat_id=user_to_refund, text=f"Your withdrawal request was rejected. The amount of {amount_to_refund} ETB has been returned to your balance.")

# =============================================================================
# === HELPER FUNCTIONS ========================================================
# =============================================================================
async def send_verification_message(update: Update):
    text = "👋 **Welcome!**\n\nTo use this bot, you must first join our partner channel. Please join and then click the button below to verify."
    try: await update.message.reply_photo(photo=open('assets/welcome.png', 'rb'), caption=text, reply_markup=keyboards.verify_join_keyboard(), parse_mode=ParseMode.MARKDOWN)
    except FileNotFoundError: await update.message.reply_text(text, reply_markup=keyboards.verify_join_keyboard(), parse_mode=ParseMode.MARKDOWN)

async def ask_for_phone(update: Update):
    text = "✅ **Thank you for joining!**\n\nTo complete your registration, please share your phone number with us by clicking the button below."
    message_source = update.callback_query.message if update.callback_query else update.message
    await message_source.reply_text(text, reply_markup=keyboards.request_phone_keyboard(), parse_mode=ParseMode.MARKDOWN)

async def show_main_menu(update: Update, text: str, edit: bool = False):
    if edit or update.callback_query: await update.callback_query.edit_message_text(text, reply_markup=keyboards.main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)
    else: await update.message.reply_text(text, reply_markup=keyboards.main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)

async def edit_or_reply(update: Update, text: str, reply_markup):
    if update.callback_query: await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else: await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def notify_referrer(context, referrer_id, new_user):
    await context.bot.send_message(chat_id=referrer_id, text=f"🎉 Congratulations! User *{new_user.first_name}* joined with your link. You've earned **{REFERRAL_BONUS} ETB**!", parse_mode=ParseMode.MARKDOWN)

async def notify_admin_of_withdrawal(context, user, method, details, amount, w_id):
    text = f"⚠️ **New Withdrawal Request!**\n\n**User:** @{user.username} ({user.id})\n**Method:** {method}\n**Details:** `{details}`\n**Amount:** {amount} ETB"
    await context.bot.send_message(chat_id=ADMIN_ID, text=text, reply_markup=keyboards.admin_withdrawal_keyboard(w_id), parse_mode=ParseMode.MARKDOWN)

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Action cancelled.", reply_markup=ReplyKeyboardRemove())
    await admin_command(update, context) # Return to admin menu
    return ConversationHandler.END
