# main.py
import os
from dotenv import load_dotenv
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler
)
from bot import handlers, database

# Load environment variables from .env file
load_dotenv()

def main():
    """Run the bot."""
    # Setup database
    database.setup_database()
    
    # Get bot token from environment variable
    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN:
        raise ValueError("No BOT_TOKEN found in environment variables")

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()
    
    # --- Conversation Handler for Withdrawal ---
    withdrawal_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handlers.start_withdrawal, pattern='^withdraw$')],
        states={
            handlers.ASK_METHOD: [CallbackQueryHandler(handlers.withdrawal_method_selected, pattern='^withdraw_')],
            handlers.ASK_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.withdrawal_details_received)],
            handlers.ASK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.withdrawal_amount_received)],
        },
        fallbacks=[CommandHandler('cancel', handlers.cancel_withdrawal), CallbackQueryHandler(handlers.show_main_menu, pattern='^main_menu$')],
    )

    # --- Add all handlers to the application ---
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(MessageHandler(filters.CONTACT, handlers.contact_handler))
    
    # Admin commands
    application.add_handler(CommandHandler("admin", handlers.admin_handler))
    application.add_handler(CommandHandler("broadcast", handlers.broadcast))
    application.add_handler(CommandHandler("users", handlers.users_command))
    application.add_handler(CommandHandler("withdrawals", handlers.withdrawals_command))
    application.add_handler(CommandHandler("referrals", handlers.referrals_command))

    # Add the conversation handler
    application.add_handler(withdrawal_conv_handler)
    
    # This handler must be last. It routes all button clicks.
    # We add a pattern to exclude withdrawal-related buttons, which are handled by the ConversationHandler
    application.add_handler(CallbackQueryHandler(handlers.button_handler, pattern='^(?!withdraw)'))
    application.add_handler(CallbackQueryHandler(handlers.verify_join_callback, pattern='^verify_join$'))


    # Run the bot until the user presses Ctrl-C
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
