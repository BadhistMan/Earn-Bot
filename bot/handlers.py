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

# --- State definitions for ConversationHandler ---
ASK_METHOD, ASK_DETAILS, ASK_AMOUNT = range(3)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# === USER COMMANDS & REGISTRATION FLOW ======================================
# =============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # --- Referral Logic ---
    try:
        referrer_id = int(context.args[0])
        if referrer_id == user.id: # Self-referral check
            referrer_id = None
        context.user_data['referrer_id'] = referrer_id
    except (IndexError, ValueError):
        context.user_data['referrer_id'] = None

    # --- Check if user is already registered ---
    if db.user_exists(user.id):
        await show_main_menu(update, "Welcome back!")
        return

    # --- Force Join & Verification ---
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user.id)
        if member.status not in ['member', 'administrator', 'creator']:
            await send_verification_message(update)
        else:
            await ask_for_phone(update)
    except Exception as e:
        logger.error(f"Error checking channel membership for {user.id}: {e}")
        await update.message.reply_text("Sorry, we couldn't verify your channel membership. Please try again later.")

async def verify_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user.id)
        if member.status in ['member', 'administrator', 'creator']:
            await query.edit_message_reply_markup(reply_markup=None) # Remove old buttons
            await ask_for_phone(update)
        else:
            await query.answer("You haven't joined the channel yet. Please join to continue.", show_alert=True)
    except Exception as e:
        logger.error(f"Error re-checking channel membership for {user.id}: {e}")
        await query.answer("An error occurred during verification. Please try again.", show_alert=True)

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    phone_number = update.message.contact.phone_number

    if db.user_exists(user.id):
        return # Should not happen if start logic is correct, but a good safeguard

    referrer_id = context.user_data.get('referrer_id')
    
    # Add user to database
    db.add_user(user.id, user.username or user.first_name, phone_number, referrer_id)
    
    # Process referral if exists
    if referrer_id:
        db.add_referral(referrer_id, user.id)
        db.update_balance(referrer_id, REFERRAL_BONUS)
        # Notify referrer
        await context.bot.send_message(
            chat_id=referrer_id,
            text=f"🎉 Congratulations! A new user ({user.first_name}) joined with your link. You've earned {REFERRAL_BONUS} ETB!"
        )

    await show_main_menu(update, "✅ Registration complete! Welcome to the bot.", remove_keyboard=True)

# =============================================================================
# === MAIN MENU & BUTTON HANDLERS =============================================
# =============================================================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'main_menu':
        await show_main_menu(update, "Welcome to the main menu:", edit=True)
    elif data == 'my_balance':
        await my_balance_handler(update)
    elif data == 'refer_friends':
        await refer_friends_handler(update, context)
    elif data == 'my_referrals':
        await my_referrals_handler(update)
    elif data == 'withdraw':
        return await start_withdrawal(update, context)
    elif data == 'top_referrers':
        await top_referrers_handler(update)
    elif data == 'statistics':
        await statistics_handler(update)
    elif data == 'help_support':
        await help_support_handler(update)
    elif data.startswith('admin_approve_'):
        await approve_withdrawal(update, context)
    elif data.startswith('admin_reject_'):
        await reject_withdrawal(update, context)
    elif data.startswith('withdraw_'):
        return await withdrawal_method_selected(update, context)

async def my_balance_handler(update: Update):
    user_id = update.effective_user.id
    balance = db.get_balance(user_id)
    text = f"💰 **My Balance**\n\nYour current balance is: **{balance} ETB**"
    await edit_or_reply(update, text, keyboards.back_to_menu_keyboard())

async def refer_friends_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = (await context.bot.get_me()).username
    user_id = update.effective_user.id
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    text = (
        "👥 **Refer & Earn**\n\n"
        f"Invite your friends and earn **{REFERRAL_BONUS} ETB** for each successful referral!\n\n"
        "Your unique referral link is:\n"
        f"`{referral_link}`\n\n"
        "*(Tap the link above to copy it)*"
    )
    await edit_or_reply(update, text, keyboards.back_to_menu_keyboard())

async def my_referrals_handler(update: Update):
    user_id = update.effective_user.id
    referrals = db.get_user_referrals(user_id)
    count = len(referrals)
    
    if count == 0:
        text = "You haven't referred anyone yet. Share your link to start earning!"
    else:
        text = f"📝 **My Referrals ({count})**\n\nHere are the users you've referred:\n"
        text += "\n".join([f"- @{username}" if username else f"- User ID: {uid}" for uid, username in referrals[:20]]) # Show max 20
        if count > 20:
            text += f"\n... and {count - 20} more."
            
    await edit_or_reply(update, text, keyboards.back_to_menu_keyboard())

async def top_referrers_handler(update: Update):
    top_users = db.get_top_referrers()
    text = "🏆 **Top 10 Referrers**\n\n"
    if not top_users:
        text += "No referrals recorded yet."
    else:
        for i, (username, ref_count, balance) in enumerate(top_users):
            text += f"{i+1}. @{username or 'user'} - {ref_count} referrals\n"
    await edit_or_reply(update, text, keyboards.back_to_menu_keyboard())

async def statistics_handler(update: Update):
    total_users = db.get_total_user_count()
    text = f"📊 **Bot Statistics**\n\nTotal Registered Users: **{total_users}**"
    await edit_or_reply(update, text, keyboards.back_to_menu_keyboard())

async def help_support_handler(update: Update):
    text = (
        "❓ **Help & Support**\n\n"
        "**How does it work?**\n"
        "Share your referral link. When a new user joins through your link, completes the channel join, and phone verification, you earn 5 ETB.\n\n"
        "**How can I withdraw?**\n"
        f"You need a minimum of {MIN_WITHDRAWAL} ETB to request a withdrawal. Go to the 'Withdraw' section and follow the instructions.\n\n"
        "**Is self-referral allowed?**\n"
        "No, referring yourself is strictly forbidden and will result in a ban.\n\n"
        "If you need further help, please contact the admin."
    )
    await edit_or_reply(update, text, keyboards.back_to_menu_keyboard())


# =============================================================================
# === WITHDRAWAL CONVERSATION HANDLER =========================================
# =============================================================================

async def start_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    balance = db.get_balance(user_id)
    
    if balance < MIN_WITHDRAWAL:
        await query.answer(f"You need at least {MIN_WITHDRAWAL} ETB to withdraw. Your balance is {balance} ETB.", show_alert=True)
        return ConversationHandler.END
    
    context.user_data['balance'] = balance
    await query.edit_message_text(
        "💸 **Withdrawal**\n\nPlease select your preferred withdrawal method:",
        reply_markup=keyboards.withdrawal_methods_keyboard()
    )
    return ASK_METHOD

async def withdrawal_method_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    method = query.data.split('_')[1].upper() # e.g., 'TELEBIRR'
    context.user_data['withdrawal_method'] = method
    
    prompts = {
        'TELEBIRR': 'Please enter your Telebirr phone number:',
        'CBE': 'Please enter your CBE bank account number:',
        'USDT': 'Please enter your USDT (TRC20) wallet address:'
    }
    await query.edit_message_text(text=prompts[method])
    return ASK_DETAILS

async def withdrawal_details_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['withdrawal_details'] = update.message.text
    balance = context.user_data['balance']
    await update.message.reply_text(f"Your balance is {balance} ETB. How much would you like to withdraw?")
    return ASK_AMOUNT

async def withdrawal_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        amount = int(update.message.text)
        balance = context.user_data['balance']
        if amount <= 0:
            await update.message.reply_text("Invalid amount. Please enter a positive number.")
            return ASK_AMOUNT
        if amount > balance:
            await update.message.reply_text(f"You cannot withdraw more than your balance ({balance} ETB). Please enter a valid amount.")
            return ASK_AMOUNT
        if amount < MIN_WITHDRAWAL:
             await update.message.reply_text(f"The minimum withdrawal amount is {MIN_WITHDRAWAL} ETB. Please enter a higher amount.")
             return ASK_AMOUNT

        method = context.user_data['withdrawal_method']
        details = context.user_data['withdrawal_details']

        # Process withdrawal
        db.create_withdrawal_request(user_id, method, details, amount)

        await update.message.reply_text(
            "✅ Your withdrawal request has been submitted successfully!\n"
            "It will be reviewed by an admin shortly."
        )
        await show_main_menu(update, "Welcome to the main menu:")

        # Notify admin
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"⚠️ New Withdrawal Request!\n\n"
                f"User: @{update.effective_user.username} ({user_id})\n"
                f"Method: {method}\n"
                f"Details: {details}\n"
                f"Amount: {amount} ETB"
            )
        )
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text("Invalid input. Please enter a number.")
        return ASK_AMOUNT

async def cancel_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update, "Withdrawal cancelled.", edit=False)
    return ConversationHandler.END

# =============================================================================
# === ADMIN COMMANDS ==========================================================
# =============================================================================

async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    text = (
        "🧑‍💻 **Admin Panel**\n\n"
        "`/users` - Get total user count.\n"
        "`/broadcast <message>` - Send a message to all users.\n"
        "`/withdrawals` - View pending withdrawal requests.\n"
        "`/referrals <user_id>` - See who a user referred."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    message_to_send = " ".join(context.args)
    if not message_to_send:
        await update.message.reply_text("Usage: /broadcast <message>")
        return

    user_ids = db.get_all_user_ids()
    sent_count = 0
    failed_count = 0
    for user_id in user_ids:
        try:
            await context.bot.send_message(chat_id=user_id, text=message_to_send)
            sent_count += 1
        except Exception:
            failed_count += 1
    
    await update.message.reply_text(f"Broadcast finished.\nSent: {sent_count}\nFailed: {failed_count}")

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    count = db.get_total_user_count()
    await update.message.reply_text(f"Total registered users: {count}")

async def withdrawals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    pending = db.get_pending_withdrawals()
    if not pending:
        await update.message.reply_text("No pending withdrawals.")
        return
        
    for w_id, u_id, u_name, method, details, amount in pending:
        text = (
            f"**Request ID:** {w_id}\n"
            f"**User:** @{u_name} ({u_id})\n"
            f"**Method:** {method}\n"
            f"**Details:** `{details}`\n"
            f"**Amount:** {amount} ETB"
        )
        await update.message.reply_text(
            text,
            reply_markup=keyboards.admin_withdrawal_keyboard(w_id),
            parse_mode=ParseMode.MARKDOWN
        )

async def referrals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        target_id = int(context.args[0])
        referrals = db.get_user_referrals(target_id)
        count = len(referrals)
        text = f"User {target_id} has referred {count} users:\n\n"
        text += "\n".join([f"- @{username}" if username else f"- User ID: {uid}" for uid, username in referrals])
        await update.message.reply_text(text or f"User {target_id} has no referrals.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /referrals <user_id>")

async def approve_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID: return
    await query.answer("Processing approval...")
    
    withdrawal_id = int(query.data.split('_')[2])
    db.update_withdrawal_status(withdrawal_id, 'approved')
    
    await query.edit_message_text(text=query.message.text + "\n\n**Status: ✅ Approved**", parse_mode=ParseMode.MARKDOWN)

async def reject_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID: return
    await query.answer("Processing rejection...")

    withdrawal_id = int(query.data.split('_')[2])
    
    # Refund the user
    user_to_refund, amount_to_refund = db.get_withdrawal_for_refund(withdrawal_id)
    if user_to_refund:
        db.update_balance(user_to_refund, amount_to_refund)
    
    db.update_withdrawal_status(withdrawal_id, 'rejected')

    await query.edit_message_text(text=query.message.text + "\n\n**Status: ❌ Rejected (Amount Refunded)**", parse_mode=ParseMode.MARKDOWN)

    # Notify user
    await context.bot.send_message(
        chat_id=user_to_refund,
        text=f"Your withdrawal request was rejected by the admin. The amount of {amount_to_refund} ETB has been returned to your balance."
    )

# =============================================================================
# === HELPER FUNCTIONS ========================================================
# =============================================================================

async def send_verification_message(update: Update):
    text = "👋 Welcome!\n\nTo use this bot, you must be a member of our channel. Please join and then click 'Verify'."
    # Check if update is from a command or a callback
    if update.callback_query:
        await update.callback_query.message.reply_photo(
            photo=open('assets/welcome.png', 'rb'),
            caption=text,
            reply_markup=keyboards.verify_join_keyboard()
        )
    else:
        await update.message.reply_photo(
            photo=open('assets/welcome.png', 'rb'),
            caption=text,
            reply_markup=keyboards.verify_join_keyboard()
        )
        
async def ask_for_phone(update: Update):
    text = "✅ Thank you for joining!\n\nTo complete your registration, please share your phone number with us by clicking the button below."
    if update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=keyboards.request_phone_keyboard())
    else:
        await update.message.reply_text(text, reply_markup=keyboards.request_phone_keyboard())
        
async def show_main_menu(update: Update, text: str, edit: bool = False, remove_keyboard: bool = False):
    reply_markup = keyboards.main_menu_keyboard()
    if remove_keyboard:
        # Also remove the "Share Phone" reply keyboard if it's there
        reply_markup = ReplyKeyboardRemove()
        await update.message.reply_text(text, reply_markup=reply_markup)
        # Then send the main menu as a new message
        await update.message.reply_text("Here is your dashboard:", reply_markup=keyboards.main_menu_keyboard())
        return

    if edit or update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def edit_or_reply(update: Update, text: str, reply_markup):
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
