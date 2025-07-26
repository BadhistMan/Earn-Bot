# main.py
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
)
from bot import handlers, database

load_dotenv()

def main():
    """Run the bot."""
    database.setup_database()
    
    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN:
        raise ValueError("No BOT_TOKEN found in environment variables")

    application = Application.builder().token(TOKEN).build()

    # --- Conversation Handler for Withdrawal ---
    withdrawal_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handlers.start_withdrawal, pattern='^withdraw$')],
        states={
            handlers.ASK_WITHDRAWAL_METHOD: [
                CallbackQueryHandler(handlers.withdrawal_method_selected, pattern='^withdraw_')
            ],
            handlers.ASK_WITHDRAWAL_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.withdrawal_details_received)
            ],
            handlers.ASK_WITHDRAWAL_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.withdrawal_amount_received)
            ],
        },
        fallbacks=[
            CommandHandler('cancel', handlers.cancel_conversation),
            CallbackQueryHandler(handlers.show_main_menu, pattern='^main_menu$'),
        ],
    )
    
    # --- Conversation Handler for Admin Broadcast ---
    broadcast_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handlers.start_broadcast, pattern='^admin_broadcast$')],
        states={
            handlers.ASK_BROADCAST_MESSAGE: [
                MessageHandler(filters.ALL & ~filters.COMMAND, handlers.broadcast_message_received)
            ],
            handlers.CONFIRM_BROADCAST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.broadcast_confirmed)
            ],
        },
        fallbacks=[CommandHandler('cancel', handlers.cancel_conversation)],
    )

    # --- Add all handlers ---
    # Top-level commands
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("admin", handlers.admin_command))
    application.add_handler(CommandHandler("myid", handlers.my_id_command)) # ADD THIS LINE
    
    # Registration Flow
    application.add_handler(MessageHandler(filters.CONTACT, handlers.contact_handler))
    application.add_handler(CallbackQueryHandler(handlers.verify_join_callback, pattern='^verify_join$'))
    
    # Add Conversation Handlers
    application.add_handler(withdrawal_handler)
    application.add_handler(broadcast_handler)
    
    # This handler routes all other button clicks.
    application.add_handler(CallbackQueryHandler(handlers.button_handler))

    print("Bot is starting... Final version with Admin Panel fix.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
