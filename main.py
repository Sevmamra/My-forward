import os
import logging
from typing import Dict
from telegram import Update, Video, Document
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MAIN_GROUP_ID = int(os.getenv("MAIN_GROUP_ID", "-10012345678"))
AUTHORIZED_USER_ID = int(os.getenv("AUTHORIZED_USER_ID"))

# Database setup
topics_db: Dict[str, int] = {}

async def validate_access(update: Update) -> bool:
    """Check if user is authorized"""
    if update.effective_user.id != AUTHORIZED_USER_ID:
        await update.message.reply_text("⛔ Access denied")
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /start command"""
    if not await validate_access(update):
        return
    await update.message.reply_text(
        "🚀 Bot activated!\n"
        "Send files with caption: /upload TOPIC_NAME"
    )

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process uploaded media files"""
    try:
        if not await validate_access(update):
            return

        if not update.message.caption or not update.message.caption.startswith("/upload"):
            return

        # Parse command
        _, *topic_parts = update.message.caption.split()
        topic_name = " ".join(topic_parts).upper()
        
        # Handle both video and document
        if update.message.video:
            file = update.message.video
        elif update.message.document:
            file = update.message.document
        else:
            await update.message.reply_text("❌ Unsupported file type")
            return

        # Get or create thread
        thread_id = topics_db.get(topic_name)
        if not thread_id:
            msg = await context.bot.send_message(
                chat_id=MAIN_GROUP_ID,
                text=f"📌 New Topic: {topic_name}"
            )
            thread_id = msg.message_id
            topics_db[topic_name] = thread_id
            logger.info(f"Created new thread for {topic_name}")

        # Forward file to group
        if update.message.video:
            await context.bot.send_video(
                chat_id=MAIN_GROUP_ID,
                video=file.file_id,
                reply_to_message_id=thread_id,
                caption=f"🎬 {topic_name}"
            )
        else:  # document
            await context.bot.send_document(
                chat_id=MAIN_GROUP_ID,
                document=file.file_id,
                reply_to_message_id=thread_id,
                caption=f"📄 {topic_name}"
            )
            
        await update.message.reply_text(f"✅ Uploaded to '{topic_name}'")
        
    except Exception as e:
        logger.error(f"Error in handle_media: {e}", exc_info=True)
        await update.message.reply_text("⚠️ An error occurred")

def setup_handlers(application):
    """Configure bot handlers"""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & 
            (filters.VIDEO | filters.ATTACHMENT),
            handle_media
        )
    )

def main():
    """Run the bot"""
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in environment")
    
    application = ApplicationBuilder() \
        .token(TOKEN) \
        .build()

    setup_handlers(application)
    
    logger.info("Starting bot...")
    application.run_polling()

if __name__ == "__main__":
    main()
