from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import os
from dotenv import load_dotenv
from bot import handlers, database

load_dotenv()

def main():
    # Setup database
    database.setup_database()

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(os.getenv("BOT_TOKEN")).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("broadcast", handlers.broadcast))
    # ... (Add all other handlers)

    # on non command i.e message - echo the message on Telegram
    application.add_handler(CallbackQueryHandler(handlers.button_handler))
    application.add_handler(MessageHandler(filters.CONTACT, handlers.contact_handler))


    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main()
