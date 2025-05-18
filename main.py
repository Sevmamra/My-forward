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
MAIN_GROUP_ID = int(os.getenv("MAIN_GROUP_ID"))  # -100xxxxxxx format
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
        self.user_data = {}

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

# Sample data - replace with your actual groups and topics
GROUPS = {
    "CA Inter Group": -10012345678,
    "CA Final Group": -10087654321
}

TOPICS = {
    -10012345678: ["AS 13 Investments", "AS 16 Borrowing Costs"],
    -10087654321: ["SFM", "Auditing"]
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message and suggest /help"""
    if not session.validate_user(update.message.from_user.id):
        return

    welcome_msg = """
🌟 *Welcome to Premium Content Manager Bot* 🌟

📌 *Features:*
- Batch upload 50-100 files at once
- Smart topic management
- Detailed upload reports
- Beautiful formatting preserved

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

/groups - List all available groups
/start - Welcome message
/help - This message
/done - Finish and upload queued content
/cancel - Cancel current operation

📌 *How to Upload:*
1. Select a group with /groups
2. Choose a topic
3. Send all your files
4. Type /done when finished
"""
    keyboard = [
        [InlineKeyboardButton("📂 View Groups", callback_data='list_groups')],
        [InlineKeyboardButton("🆘 Support", url='https://t.me/yourchannel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        help_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List available groups with inline buttons"""
    if not session.validate_user(update.callback_query.from_user.id):
        return

    keyboard = []
    for group_name in GROUPS:
        keyboard.append(
            [InlineKeyboardButton(group_name, callback_data=f"group_{group_name}")]
        )
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "📚 *Available Groups:*\nSelect one to continue:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    return SELECTING_GROUP

async def select_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle group selection"""
    query = update.callback_query
    group_name = query.data.split('_')[1]
    
    context.user_data['selected_group'] = {
        'name': group_name,
        'id': GROUPS[group_name]
    }
    
    keyboard = []
    for topic in TOPICS[GROUPS[group_name]]:
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
    user_data = context.user_data
    
    if query.data == "new_topic":
        await query.edit_message_text(
            "✏️ Send the new topic name:",
            parse_mode='Markdown'
        )
        return UPLOADING_CONTENT
    
    topic_name = query.data.split('_')[1]
    group_id = user_data['selected_group']['id']
    
    # In a real bot, you would create/get the thread ID here
    thread_id = 123  # Replace with actual thread ID
    
    session.new_session(group_id, topic_name, thread_id)
    
    await query.edit_message_text(
        f"✅ Ready to upload to: *{topic_name}*\n"
        "Now send all your files/media/text. Type /done when finished.",
        parse_mode='Markdown'
    )
    return UPLOADING_CONTENT

async def queue_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Queue content for batch upload"""
    if not session.validate_user(update.message.from_user.id):
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
        await update.message.reply_text(
            "📥 Added to queue. Send more or /done to finish.",
            parse_mode='Markdown'
        )
    
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

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Set bot commands
    commands = [
        BotCommand("start", "Welcome message"),
        BotCommand("help", "Show help"),
        BotCommand("groups", "List available groups"),
        BotCommand("done", "Finish uploading"),
        BotCommand("cancel", "Cancel operation")
    ]
    app.bot.set_my_commands(commands)
    
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
                MessageHandler(filters.TEXT & ~filters.COMMAND, queue_content),
                MessageHandler(filters.PHOTO, queue_content),
                MessageHandler(filters.VIDEO, queue_content),
                MessageHandler(filters.Document.ALL, queue_content),
                CommandHandler("done", done_uploading)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    
    logger.info("Premium bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
