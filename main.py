import os
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# Configuration
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MAIN_GROUP_ID = int(os.getenv("MAIN_GROUP_ID"))  # -100xxxxxxx format
AUTHORIZED_USER_ID = int(os.getenv("AUTHORIZED_USER_ID"))

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self):
        self.current_topic = None
        self.current_thread_id = None

    def new_session(self, topic_name, thread_id):
        self.current_topic = topic_name
        self.current_thread_id = thread_id
        logger.info(f"New session: {topic_name} (Thread: {thread_id})")

    def validate_user(self, user_id):
        if user_id != AUTHORIZED_USER_ID:
            logger.warning(f"Unauthorized access: {user_id}")
            return False
        return True

session = SessionManager()

async def start_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not session.validate_user(update.message.from_user.id):
        await update.message.reply_text("❌ Unauthorized")
        return

    try:
        topic_name = ' '.join(context.args) if context.args else None
        if not topic_name:
            await update.message.reply_text("Usage: /start <TOPIC_NAME>")
            return

        logger.info(f"Creating topic: {topic_name}")
        result = await context.bot.create_forum_topic(
            chat_id=MAIN_GROUP_ID,
            name=topic_name
        )
        
        session.new_session(topic_name, result.message_thread_id)
        await update.message.reply_text(
            f"✅ Ready for: {topic_name}\n"
            "Now send any: text/videos/photos/documents"
        )

    except Exception as e:
        logger.error(f"Topic error: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Topic creation failed")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not session.validate_user(update.message.from_user.id):
            return

        if not session.current_thread_id:
            await update.message.reply_text("⚠️ First create topic with /start <TOPIC>")
            return

        # Get the raw text with all entities (formatting)
        text_content = update.message.text
        entities = update.message.entities or update.message.caption_entities
        
        logger.info(f"Processing text with {len(entities or [])} formatting entities")

        # Forward the message with original formatting
        await context.bot.forward_message(
            chat_id=MAIN_GROUP_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id,
            message_thread_id=session.current_thread_id
        )
        await update.message.reply_text("✅ Text forwarded with original formatting")

    except Exception as e:
        logger.error(f"Text error: {str(e)}", exc_info=True)
        await update.message.reply_text(f"⚠️ Failed to forward text: {str(e)}")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not session.validate_user(update.message.from_user.id):
            return

        if not session.current_thread_id:
            await update.message.reply_text("⚠️ First create topic with /start <TOPIC>")
            return

        # Forward media with original caption and formatting
        await context.bot.forward_message(
            chat_id=MAIN_GROUP_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id,
            message_thread_id=session.current_thread_id
        )
        await update.message.reply_text("✅ Media forwarded with original formatting")

    except Exception as e:
        logger.error(f"Media error: {str(e)}", exc_info=True)
        await update.message.reply_text(f"⚠️ Failed to forward media: {str(e)}")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start_session))
    
    # Content handlers - now using forwarding instead of re-sending
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & (
            filters.TEXT |
            filters.VIDEO |
            filters.Document.ALL |
            filters.PHOTO
        ) & ~filters.COMMAND,
        handle_media if filters.VIDEO | filters.Document.ALL | filters.PHOTO else handle_text
    ))
    
    logger.info("Bot started with message forwarding")
    app.run_polling()

if __name__ == "__main__":
    main()
