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
            # Get all chats where bot is member
            chats = await bot.get_updates()
            
            # Filter for supergroups where bot is admin
            for update in chats:
                if update.my_chat_member and update.my_chat_member.chat.type in ['group', 'supergroup']:
                    chat = update.my_chat_member.chat
                    status = update.my_chat_member.new_chat_member.status
                    
                    if status in ['administrator', 'creator']:
                        self.available_groups[chat.title] = chat.id
                        
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
- Detailed upload reports

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
/refresh - Reload group list

📌 *How to Upload:*
1. Select a group with /groups
2. Choose a topic
3. Send all your files
4. Type /done when finished
"""
    keyboard = [
        [InlineKeyboardButton("📂 View Groups", callback_data='list_groups')],
        [InlineKeyboardButton("🔄 Refresh Groups", callback_data='refresh_groups')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        help_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def refresh_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Refresh group list"""
    if not session.validate_user(update.callback_query.from_user.id):
        return

    await session.refresh_groups(context.bot)
    await update.callback_query.answer("Group list refreshed!")
    await list_groups(update, context)

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List available groups where bot is admin"""
    if not session.validate_user(update.callback_query.from_user.id if update.callback_query else update.message.from_user.id):
        return

    if not session.available_groups:
        await session.refresh_groups(context.bot)

    if not session.available_groups:
        await (update.callback_query.edit_message_text if update.callback_query else update.message.reply_text)(
            "❌ No groups found where bot is admin",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    keyboard = []
    for group_name in session.available_groups:
        keyboard.append(
            [InlineKeyboardButton(group_name, callback_data=f"group_{group_name}")]
        )
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await (update.callback_query.edit_message_text if update.callback_query else update.message.reply_text)(
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
        'id': session.available_groups[group_name]
    }
    
    # Get topics for this group (in real implementation, fetch from Telegram)
    topics = ["General", "Lectures", "Notes"]  # Placeholder - implement actual topic fetching
    
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

# ... (rest of the code remains the same as previous implementation)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Set bot commands
    commands = [
        BotCommand("start", "Welcome message"),
        BotCommand("help", "Show help"),
        BotCommand("groups", "List available groups"),
        BotCommand("refresh", "Refresh group list"),
        BotCommand("done", "Finish uploading"),
        BotCommand("cancel", "Cancel operation")
    ]
    app.bot.set_my_commands(commands)
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("groups", list_groups),
            CommandHandler("refresh", list_groups),
            CallbackQueryHandler(list_groups, pattern="^list_groups$"),
            CallbackQueryHandler(refresh_groups, pattern="^refresh_groups$")
        ],
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
    
    logger.info("Premium bot with dynamic group detection started")
    app.run_polling()

if __name__ == "__main__":
    main()
