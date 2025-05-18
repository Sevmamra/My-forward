import os
import logging
from telegram import Update, Video, Document, PhotoSize
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
    """Manages active upload session"""
    def __init__(self):
        self.current_topic = None
        self.current_thread_id = None

    def new_session(self, topic_name, thread_id):
        self.current_topic = topic_name
        self.current_thread_id = thread_id
        logger.info(f"New session started: {topic_name}")

    def validate_user(self, user_id):
        return user_id == AUTHORIZED_USER_ID

session = SessionManager()

async def start_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initialize new upload session with topic creation"""
    if not session.validate_user(update.message.from_user.id):
        return

    try:
        topic_name = ' '.join(context.args)
        if not topic_name:
            await update.message.reply_text("Usage: /start <TOPIC_NAME>")
            return

        # Create forum topic
        result = await context.bot.create_forum_topic(
            chat_id=MAIN_GROUP_ID,
            name=topic_name
        )
        
        session.new_session(topic_name, result.message_thread_id)
        await update.message.reply_text(
            f"✅ Session ready for topic: {topic_name}\n"
            "Now send files/text (no captions needed)"
        )

    except Exception as e:
        logger.error(f"Topic creation failed: {e}")
        await update.message.reply_text("⚠️ Failed to create topic")

async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process all incoming content for active session"""
    if not session.validate_user(update.message.from_user.id):
        return

    if not session.current_thread_id:
        await update.message.reply_text("⚠️ First create session with /start <TOPIC>")
        return

    try:
        content_types = {
            'text': await handle_text,
            'video': await handle_video,
            'document': await handle_document,
            'photo': await handle_photo
        }

        for content_type, handler in content_types.items():
            if getattr(update.message, content_type, None):
                await handler(update, context)
                break

        await update.message.reply_text("✅ Content added to topic")

    except Exception as e:
        logger.error(f"Content handling error: {e}")
        await update.message.reply_text("⚠️ Failed to process content")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=MAIN_GROUP_ID,
        text=update.message.text,
        message_thread_id=session.current_thread_id
    )

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_video(
        chat_id=MAIN_GROUP_ID,
        video=update.message.video.file_id,
        message_thread_id=session.current_thread_id,
        caption=update.message.caption or ""
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_document(
        chat_id=MAIN_GROUP_ID,
        document=update.message.document.file_id,
        message_thread_id=session.current_thread_id,
        caption=update.message.caption or ""
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_photo(
        chat_id=MAIN_GROUP_ID,
        photo=update.message.photo[-1].file_id,
        message_thread_id=session.current_thread_id,
        caption=update.message.caption or ""
    )

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
    
    app.run_polling()

if __name__ == "__main__":
    main()
