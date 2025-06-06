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

async def copy_message_without_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not session.validate_user(update.message.from_user.id):
            return

        if not session.current_thread_id:
            await update.message.reply_text("⚠️ First create topic with /start <TOPIC>")
            return

        # For text messages
        if update.message.text:
            await context.bot.send_message(
                chat_id=MAIN_GROUP_ID,
                text=update.message.text,
                message_thread_id=session.current_thread_id,
                entities=update.message.entities,
                parse_mode=None  # Preserve original formatting
            )
        
        # For media with captions
        elif update.message.caption:
            if update.message.photo:
                await context.bot.send_photo(
                    chat_id=MAIN_GROUP_ID,
                    photo=update.message.photo[-1].file_id,
                    caption=update.message.caption,
                    caption_entities=update.message.caption_entities,
                    message_thread_id=session.current_thread_id,
                    parse_mode=None
                )
            elif update.message.video:
                await context.bot.send_video(
                    chat_id=MAIN_GROUP_ID,
                    video=update.message.video.file_id,
                    caption=update.message.caption,
                    caption_entities=update.message.caption_entities,
                    message_thread_id=session.current_thread_id,
                    parse_mode=None
                )
            elif update.message.document:
                await context.bot.send_document(
                    chat_id=MAIN_GROUP_ID,
                    document=update.message.document.file_id,
                    caption=update.message.caption,
                    caption_entities=update.message.caption_entities,
                    message_thread_id=session.current_thread_id,parse_mode=None
                )
        
        # For media without captions
        else:
            if update.message.photo:
                await context.bot.send_photo(
                    chat_id=MAIN_GROUP_ID,
                    photo=update.message.photo[-1].file_id,
                    message_thread_id=session.current_thread_id
                )
            elif update.message.video:
                await context.bot.send_video(
                    chat_id=MAIN_GROUP_ID,
                    video=update.message.video.file_id,
                    message_thread_id=session.current_thread_id
                )
            elif update.message.document:
                await context.bot.send_document(
                    chat_id=MAIN_GROUP_ID,
                    document=update.message.document.file_id,
                    message_thread_id=session.current_thread_id
                )

        await update.message.reply_text("✅ Content posted without forward tag")

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        await update.message.reply_text(f"⚠️ Failed to post: {str(e)}")

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
        ) & ~filters.COMMAND,
        copy_message_without_forward
    ))
    
    logger.info("Bot started with no-forwarding mode")
    app.run_polling()

if __name__ == "__main__":
    main()
