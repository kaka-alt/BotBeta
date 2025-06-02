import logging
import os
from dotenv import load_dotenv

from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters
)
import handlers
from handlers import *

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def cancelar(update, context):
    await update.message.reply_text("Operação cancelada pelo usuário.")
    context.user_data.clear()
    return ConversationHandler.END

async def start(update, context):
    await update.message.reply_text("Olá! Use /iniciar para começar o registro de uma ocorrência.")

def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("Error: BOT_TOKEN not found in environment variables or .env file")
        return

    application = ApplicationBuilder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('iniciar', handlers.iniciar_colaborador)],
        states={
            # ... seus estados (igual acima) ...
        },
        fallbacks=[CommandHandler('cancelar', cancelar)],
    )

    application.add_handler(CommandHandler('start', start))
    application.add_handler(conv_handler)

    application.run_polling()

if __name__ == "__main__":
    main()
