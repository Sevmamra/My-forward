import os
import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

# Configuration
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTHORIZED_USER_ID = int(os.getenv("AUTHORIZED_USER_ID"))

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
SELECTING_GROUP, SELECTING_TOPIC, UPLOADING_CONTENT = range(3)

class SessionManager:
    def __init__(self):
        self.current_group = None
        self.current_topic = None
        self.current_thread_id = None
        self.queued_content = []
        self.available_groups = {}

    async def refresh_groups(self, bot):
        """Refresh list of groups where bot is admin"""
        self.available_groups = {}
        try:
            # This should be replaced with actual group detection logic
            # For now using placeholder groups
            self.available_groups = {
                "CA Inter Group": -1002501498159,
                "CA Final Group": -1002501498159
            }
        except Exception as e:
            logger.error(f"Error refreshing groups: {e}")

    async def get_topics(self, bot, group_id):
        """Fetch topics from a group"""
        try:
            # For actual implementation, use:
            # topics = await bot.get_forum_topics(chat_id=group_id)
            # return [(topic.name, topic.message_thread_id) for topic in topics.topics]
            
            # Placeholder - replace with actual topics from your groups
            if group_id == -10012345678:
                return [("AS 13 Investments", 123), ("AS 16 Borrowing Costs", 456)]
            elif group_id == -10087654321:
                return [("SFM", 789), ("Auditing", 101)]
            return [("General", 1)]
        except Exception as e:
            logger.error(f"Error getting topics: {e}")
            return [("General", 1)]

    def new_session(self, group_id, topic_name, thread_id):
        self.current_group = group_id
        self.current_topic = topic_name
        self.current_thread_id = thread_id
        self.queued_content = []
        logger.info(f"New session: {topic_name} (Thread: {thread_id}) in {group_id}")

    def validate_user(self, user_id):
        if user_id != AUTHORIZED_USER_ID:
            logger.warning(f"Unauthorized access: {user_id}")
            return False
        return True

session = SessionManager()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    if not session.validate_user(update.message.from_user.id):
        return

    welcome_msg = """
🌟 *Welcome to Premium Content Manager Bot* 🌟

📌 *Features:*
- Automatic topic detection
- Batch upload support
- Detailed upload reports

Tap /groups to start uploading
"""
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')
    return ConversationHandler.END

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List available groups with inline buttons"""
    if not session.validate_user(update.message.from_user.id):
        return ConversationHandler.END

    if not session.available_groups:
        await session.refresh_groups(context.bot)

    keyboard = []
    for group_name in session.available_groups:
        keyboard.append(
            [InlineKeyboardButton(group_name, callback_data=f"group_{group_name}")]
        )
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📚 *Available Groups:*\nSelect one to continue:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    return SELECTING_GROUP

async def select_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle group selection"""
    query = update.callback_query
    await query.answer()
    
    group_name = query.data.split('_')[1]
    group_id = session.available_groups[group_name]
    
    context.user_data['selected_group'] = {
        'name': group_name,
        'id': group_id
    }
    
    # Get topics for selected group
    topics = await session.get_topics(query.bot, group_id)
    
    keyboard = []
    for topic_name, thread_id in topics:
        keyboard.append(
            [InlineKeyboardButton(topic_name, callback_data=f"topic_{thread_id}_{topic_name}")]
        )
    keyboard.append(
        [InlineKeyboardButton("➕ New Topic", callback_data="new_topic")]
    )
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"📂 *{group_name}*\nSelect a topic:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    return SELECTING_TOPIC

async def select_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle topic selection"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "new_topic":
        await query.edit_message_text("✏️ Please send the new topic name:")
        return UPLOADING_CONTENT
    
    _, thread_id, topic_name = query.data.split('_')
    group_id = context.user_data['selected_group']['id']
    
    session.new_session(group_id, topic_name, int(thread_id))
    await query.edit_message_text(
        f"✅ Ready to upload to: *{topic_name}*\n"
        "Send files/media/text. Type /done when finished.",
        parse_mode='Markdown'
    )
    return UPLOADING_CONTENT

async def create_new_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create new topic from user input"""
    if not session.validate_user(update.message.from_user.id):
        return ConversationHandler.END

    topic_name = update.message.text
    group_id = context.user_data['selected_group']['id']
    
    try:
        # Create new topic in the group
        topic = await context.bot.create_forum_topic(
            chat_id=group_id,
            name=topic_name
        )
        
        session.new_session(group_id, topic_name, topic.message_thread_id)
        await update.message.reply_text(
            f"✅ Created new topic: *{topic_name}*\n"
            "Now send your files/media/text. Type /done when finished.",
            parse_mode='Markdown'
        )
        return UPLOADING_CONTENT
    except Exception as e:
        logger.error(f"Error creating topic: {e}")
        await update.message.reply_text("❌ Failed to create topic. Please try again.")
        return ConversationHandler.END

async def queue_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Queue content for batch upload"""
    if not session.validate_user(update.message.from_user.id):
        return UPLOADING_CONTENT
    
    # Handle new topic creation first
    if context.user_data.get('awaiting_topic_name'):
        return await create_new_topic(update, context)
    
    if update.message.text and update.message.text.startswith('/'):
        return UPLOADING_CONTENT
    
    content_type = None
    if update.message.text:
        content_type = "text"
    elif update.message.photo:
        content_type = "photo"
    elif update.message.video:
        content_type = "video"
    elif update.message.document:
        content_type = "document"
    
    if content_type:
        session.queued_content.append({
            'type': content_type,
            'message': update.message
        })
        await update.message.reply_text("📥 Added to queue. Send more or /done to finish.")
    
    return UPLOADING_CONTENT

async def done_uploading(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process all queued content"""
    if not session.validate_user(update.message.from_user.id):
        return ConversationHandler.END
    
    if not session.queued_content:
        await update.message.reply_text("❌ Queue is empty!")
        return ConversationHandler.END
    
    stats = {
        'texts': 0,
        'photos': 0,
        'videos': 0,
        'documents': 0
    }
    
    for item in session.queued_content:
        try:
            if item['type'] == "text":
                await context.bot.send_message(
                    chat_id=session.current_group,
                    text=item['message'].text,
                    message_thread_id=session.current_thread_id,
                    entities=item['message'].entities
                )
                stats['texts'] += 1
            elif item['type'] == "photo":
                await context.bot.send_photo(
                    chat_id=session.current_group,
                    photo=item['message'].photo[-1].file_id,
                    caption=item['message'].caption,
                    caption_entities=item['message'].caption_entities,
                    message_thread_id=session.current_thread_id
                )
                stats['photos'] += 1
            elif item['type'] == "video":
                await context.bot.send_video(
                    chat_id=session.current_group,
                    video=item['message'].video.file_id,
                    caption=item['message'].caption,
                    caption_entities=item['message'].caption_entities,
                    message_thread_id=session.current_thread_id
                )
                stats['videos'] += 1
            elif item['type'] == "document":
                await context.bot.send_document(
                    chat_id=session.current_group,
                    document=item['message'].document.file_id,
                    caption=item['message'].caption,
                    caption_entities=item['message'].caption_entities,
                    message_thread_id=session.current_thread_id
                )
                stats['documents'] += 1
        except Exception as e:
            logger.error(f"Upload error: {e}")
            await update.message.reply_text(f"⚠️ Failed to upload one item: {e}")
    
    report = f"""
📊 *Upload Report:*
📝 Texts: {stats['texts']}
📷 Photos: {stats['photos']}
🎥 Videos: {stats['videos']}
📄 Documents: {stats['documents']}
➖➖➖➖➖
✅ Total: {sum(stats.values())} items
"""
    await update.message.reply_text(report, parse_mode='Markdown')
    session.queued_content = []
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current operation"""
    if not session.validate_user(update.message.from_user.id):
        return ConversationHandler.END
    
    session.queued_content = []
    await update.message.reply_text("❌ Operation cancelled")
    return ConversationHandler.END

async def post_init(application):
    """Run after bot starts"""
    # Set bot commands
    commands = [
        BotCommand("start", "Welcome message"),
        BotCommand("groups", "List available groups"),
        BotCommand("done", "Finish uploading"),
        BotCommand("cancel", "Cancel operation")
    ]
    await application.bot.set_my_commands(commands)
    
    # Refresh groups list
    await session.refresh_groups(application.bot)
    logger.info("Bot setup complete")

def main():
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("groups", list_groups)],
        states={
            SELECTING_GROUP: [
                CallbackQueryHandler(select_group, pattern="^group_")
            ],
            SELECTING_TOPIC: [
                CallbackQueryHandler(select_topic, pattern="^(topic_|new_topic)")
            ],
            UPLOADING_CONTENT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    queue_content
                ),
                MessageHandler(
                    filters.PHOTO | filters.VIDEO | filters.Document.ALL,
                    queue_content
                ),
                CommandHandler("done", done_uploading)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    
    logger.info("Starting bot...")
    app.run_polling()

if __name__ == "__main__":
    main()
