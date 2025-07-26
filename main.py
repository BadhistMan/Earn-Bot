# main.py
import os
from dotenv import load_dotenv
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
)
from bot import handlers, database

load_dotenv()

def main():
    """Run the bot."""
    database.setup_database()
    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN: raise ValueError("No BOT_TOKEN found in environment variables")

    application = Application.builder().token(TOKEN).build()

    # Conversation handler for Withdrawal
    withdrawal_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(pattern='^withdraw$')],
        states={
            handlers.ASK_WITHDRAWAL_METHOD: [CallbackQueryHandler(pattern='^withdraw_')],
            handlers.ASK_WITHDRAWAL_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.withdrawal_details_received)],
            handlers.ASK_WITHDRAWAL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.withdrawal_amount_received)],
        },
        fallbacks=[CommandHandler('cancel', handlers.cancel_conversation), CallbackQueryHandler(pattern='^main_menu$')],
        map_to_parent={ ConversationHandler.END: ConversationHandler.END }
    )
    
    # Conversation handler for Admin Broadcast
    broadcast_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(pattern='^admin_broadcast$')],
        states={
            handlers.ASK_BROADCAST_MESSAGE: [MessageHandler(filters.ALL & ~filters.COMMAND, handlers.broadcast_message_received)],
            handlers.CONFIRM_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.broadcast_confirmed)],
        },
        fallbacks=[CommandHandler('cancel', handlers.cancel_conversation)],
    )

    # Main Conversation Handler to route between user and admin states
    main_conversation = ConversationHandler(
        entry_points=[
            CommandHandler("start", handlers.start),
            CommandHandler("admin", handlers.admin_command),
            CallbackQueryHandler(handlers.button_handler),
            withdrawal_handler, # Nest withdrawal handler
            broadcast_handler,  # Nest broadcast handler
        ],
        states={},
        fallbacks=[
            CommandHandler("start", handlers.start),
            CommandHandler("admin", handlers.admin_command)
        ]
    )
    
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("admin", handlers.admin_command))
    application.add_handler(MessageHandler(filters.CONTACT, handlers.contact_handler))
    application.add_handler(CallbackQueryHandler(handlers.verify_join_callback, pattern='^verify_join$'))
    
    # Add conversation handlers
    application.add_handler(withdrawal_handler)
    application.add_handler(broadcast_handler)
    
    # This handler must be last. It routes all other button clicks.
    application.add_handler(CallbackQueryHandler(handlers.button_handler))

    print("Bot is running with all new features...")
    application.run_polling()

if __name__ == "__main__":
    main()
