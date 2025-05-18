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
    """Manages active upload session with thread safety"""
    def __init__(self):
        self.current_topic = None
        self.current_thread_id = None

    def new_session(self, topic_name, thread_id):
        self.current_topic = topic_name
        self.current_thread_id = thread_id
        logger.info(f"New session started: {topic_name} (Thread ID: {thread_id})")

    def validate_user(self, user_id):
        if user_id != AUTHORIZED_USER_ID:
            logger.warning(f"Unauthorized access attempt by {user_id}")
            return False
        return True

session = SessionManager()

async def start_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initialize new upload session with topic creation"""
    if not session.validate_user(update.message.from_user.id):
        await update.message.reply_text("❌ Unauthorized")
        return

    try:
        if not context.args:
            await update.message.reply_text("Usage: /start <TOPIC_NAME>")
            return

        topic_name = ' '.join(context.args)
        logger.info(f"Creating new topic: {topic_name}")

        # Create forum topic
        result = await context.bot.create_forum_topic(
            chat_id=MAIN_GROUP_ID,
            name=topic_name
        )
        
        session.new_session(topic_name, result.message_thread_id)
        await update.message.reply_text(
            f"✅ Ready to upload to: {topic_name}\n"
            "Send videos/photos/documents/text now"
        )

    except Exception as e:
        logger.error(f"Topic creation error: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Topic creation failed")

async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process all incoming content for active session"""
    if not session.validate_user(update.message.from_user.id):
        await update.message.reply_text("❌ Unauthorized")
        return

    if not session.current_thread_id:
        await update.message.reply_text("⚠️ First create topic with /start <TOPIC>")
        return

    try:
        content_type = None
        send_method = None
        content = None

        if update.message.text:
            content_type = "text"
            send_method = context.bot.send_message
            content = {"text": update.message.text}
        elif update.message.video:
            content_type = "video"
            send_method = context.bot.send_video
            content = {"video": update.message.video.file_id}
        elif update.message.document:
            content_type = "document"
            send_method = context.bot.send_document
            content = {"document": update.message.document.file_id}
        elif update.message.photo:
            content_type = "photo"
            send_method = context.bot.send_photo
            content = {"photo": update.message.photo[-1].file_id}  # Highest res

        if not content_type:
            await update.message.reply_text("❌ Unsupported content type")
            return

        logger.info(f"Processing {content_type} for thread {session.current_thread_id}")

        # Add common parameters
        content.update({
            "chat_id": MAIN_GROUP_ID,
            "message_thread_id": session.current_thread_id,
            "caption": update.message.caption or ""
        })

        await send_method(**content)
        await update.message.reply_text(f"✅ Added to {session.current_topic}")

    except Exception as e:
        logger.error(f"Content handling failed: {e}", exc_info=True)
        await update.message.reply_text(f"⚠️ Failed to process {content_type}")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start_session))
    
    # Content handlers
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & (
            filters.TEXT |
            filters.VIDEO |
            filters.Document.ALL |
            filters.PHOTO
        ),
        handle_content
    ))
    
    logger.info("Starting bot...")
    app.run_polling()

if __name__ == "__main__":
    main()
