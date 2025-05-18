import os
import logging
from typing import Dict, Optional
from telegram import Update, Bot, Video, Document
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
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
ADMIN_USER_IDS = [AUTHORIZED_USER_ID]  # Add more IDs if needed

# Database setup (in-memory for simplicity, replace with Redis/Postgres in production)
topics_db: Dict[str, int] = {}  # {topic_name: thread_id}

class UnauthorizedAccessError(Exception):
    """Custom exception for unauthorized users"""
    pass

async def validate_access(update: Update) -> None:
    """Check if user is authorized"""
    if update.effective_user.id not in ADMIN_USER_IDS:
        raise UnauthorizedAccessError(
            f"Unauthorized access attempt by {update.effective_user.id}"
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /start command"""
    try:
        await validate_access(update)
        await update.message.reply_text(
            "🚀 Bot activated!\n"
            "Send files with caption: /upload TOPIC_NAME"
        )
    except UnauthorizedAccessError as e:
        logger.warning(e)
        await update.message.reply_text("⛔ Access denied")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process uploaded media files"""
    try:
        await validate_access(update)
        
        if not update.message.caption or not update.message.caption.startswith("/upload"):
            return

        # Parse command
        _, *topic_parts = update.message.caption.split()
        topic_name = " ".join(topic_parts).upper()
        file = update.message.video or update.message.document
        
        if not file:
            await update.message.reply_text("❌ No valid file detected")
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
        if isinstance(file, Video):
            await context.bot.send_video(
                chat_id=MAIN_GROUP_ID,
                video=file.file_id,
                reply_to_message_id=thread_id,
                caption=f"🎬 {topic_name}"
            )
        elif isinstance(file, Document):
            await context.bot.send_document(
                chat_id=MAIN_GROUP_ID,
                document=file.file_id,
                reply_to_message_id=thread_id,
                caption=f"📄 {topic_name}"
            )
            
        await update.message.reply_text(f"✅ Uploaded to '{topic_name}'")
        
    except UnauthorizedAccessError as e:
        logger.warning(e)
    except Exception as e:
        logger.error(f"Error in handle_media: {e}", exc_info=True)
        await update.message.reply_text("⚠️ An error occurred")

def setup_handlers(application):
    """Configure bot handlers"""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & 
            (filters.VIDEO | filters.DOCUMENT),
            handle_media
        )
    )

async def post_init(application):
    """Run after bot initialization"""
    await application.bot.set_my_commands([
        ("start", "Initialize the bot"),
        ("upload", "Upload files to topics")
    ])
    logger.info("Bot setup complete")

def main():
    """Run the bot"""
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in environment")
    
    application = ApplicationBuilder() \
        .token(TOKEN) \
        .post_init(post_init) \
        .build()

    setup_handlers(application)
    
    logger.info("Starting bot...")
    application.run_polling()

if __name__ == "__main__":
    main()
