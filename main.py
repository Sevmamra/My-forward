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

        text_content = update.message.text
        logger.info(f"Processing text message (length: {len(text_content)})")

        # Send with parse_mode to preserve formatting
        await context.bot.send_message(
            chat_id=MAIN_GROUP_ID,
            message_thread_id=session.current_thread_id,
            text=text_content,
            parse_mode='HTML'  # Preserves special characters and formatting
        )
        await update.message.reply_text("✅ Text added to topic")

    except Exception as e:
        logger.error(f"Text error: {str(e)}", exc_info=True)
        await update.message.reply_text(f"⚠️ Failed to send text: {str(e)}")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not session.validate_user(update.message.from_user.id):
            return

        if not session.current_thread_id:
            await update.message.reply_text("⚠️ First create topic with /start <TOPIC>")
            return

        content = None
        if update.message.video:
            content = ("video", update.message.video.file_id)
        elif update.message.document:
            content = ("document", update.message.document.file_id)
        elif update.message.photo:
            content = ("photo", update.message.photo[-1].file_id)

        if not content:
            return

        content_type, file_id = content
        logger.info(f"Processing {content_type}")

        method = getattr(context.bot, f"send_{content_type}")
        await method(
            chat_id=MAIN_GROUP_ID,
            message_thread_id=session.current_thread_id,
            **{content_type: file_id},
            caption=update.message.caption or "",
            parse_mode='HTML'
        )
        await update.message.reply_text(f"✅ {content_type.capitalize()} added")

    except Exception as e:
        logger.error(f"Media error: {str(e)}", exc_info=True)
        await update.message.reply_text(f"⚠️ Failed to send {content_type}: {str(e)}")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start_session))
    
    # Content handlers
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
        handle_text
    ))
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & (
            filters.VIDEO |
            filters.Document.ALL |
            filters.PHOTO
        ),
        handle_media
    ))
    
    logger.info("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
