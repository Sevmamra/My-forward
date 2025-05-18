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
            # Get all chats where bot is member (simplified for example)
            # In production, you'd need to store known admin groups
            self.available_groups = {
                "CA Inter Group": -1002501498159,  # Replace with actual group IDs
                "CA Final Group": -1002665578655
            }
            logger.info(f"Refreshed groups: {self.available_groups}")
        except Exception as e:
            logger.error(f"Error refreshing groups: {e}")

    def new_session(self, group_id, topic_name, thread_id):
        self.current_group = group_id
        self.current_topic = topic_name
        self.current_thread_id = thread_id
        self.queued_content = []
        logger.info(f"New session: {topic_name} in {group_id}")

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
- Automatic group detection
- Batch upload support
- Smart topic management

Tap /help to see all commands
"""
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help with all commands"""
    if not session.validate_user(update.message.from_user.id):
        return

    help_text = """
🛠 *Available Commands:*

/groups - List available groups
/start - Welcome message
/help - This message
/done - Finish uploading
/cancel - Cancel operation
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List available groups with inline buttons"""
    if not session.validate_user(update.message.from_user.id):
        return SELECTING_GROUP

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
    
    # Example topics - replace with actual topic fetching
    topics = ["AS 13 Investments", "AS 16 Borrowing Costs", "General"]
    
    keyboard = []
    for topic in topics:
        keyboard.append(
            [InlineKeyboardButton(topic, callback_data=f"topic_{topic}")]
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
        await query.edit_message_text("✏️ Send the new topic name:")
        return UPLOADING_CONTENT
    
    topic_name = query.data.split('_')[1]
    group_id = context.user_data['selected_group']['id']
    
    # In production, you would create/get the actual thread ID here
    thread_id = 123  # Replace with actual thread ID logic
    
    session.new_session(group_id, topic_name, thread_id)
    await query.edit_message_text(
        f"✅ Ready to upload to: *{topic_name}*\n"
        "Send files/media/text. Type /done when finished.",
        parse_mode='Markdown'
    )
    return UPLOADING_CONTENT

async def queue_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Queue content for batch upload"""
    if not session.validate_user(update.message.from_user.id):
        return UPLOADING_CONTENT
    
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
                await item['message'].copy(
                    chat_id=session.current_group,
                    message_thread_id=session.current_thread_id
                )
                stats['texts'] += 1
            elif item['type'] == "photo":
                await item['message'].copy(
                    chat_id=session.current_group,
                    message_thread_id=session.current_thread_id
                )
                stats['photos'] += 1
            elif item['type'] == "video":
                await item['message'].copy(
                    chat_id=session.current_group,
                    message_thread_id=session.current_thread_id
                )
                stats['videos'] += 1
            elif item['type'] == "document":
                await item['message'].copy(
                    chat_id=session.current_group,
                    message_thread_id=session.current_thread_id
                )
                stats['documents'] += 1
        except Exception as e:
            logger.error(f"Upload error: {e}")
    
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
    """Set bot commands after startup"""
    commands = [
        BotCommand("start", "Welcome message"),
        BotCommand("help", "Show help"),
        BotCommand("groups", "List available groups"),
        BotCommand("done", "Finish uploading"),
        BotCommand("cancel", "Cancel operation")
    ]
    await application.bot.set_my_commands(commands)
    await session.refresh_groups(application.bot)

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
                    filters.TEXT & ~filters.COMMAND |
                    filters.PHOTO |
                    filters.VIDEO |
                    filters.Document.ALL,
                    queue_content
                ),
                CommandHandler("done", done_uploading)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    
    logger.info("Bot started successfully")
    app.run_polling()

if __name__ == "__main__":
    main()
