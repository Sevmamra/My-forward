import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# Config
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTHORIZED_USER_ID = int(os.getenv("AUTHORIZED_USER_ID"))

# Group list (add your group IDs and names here)
GROUPS = {
    "-1002501498159": "CA Inter X Official",
    "-1002665578655": "CA Inter X Backup"
}

# Logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Session manager
class SessionManager:
    def __init__(self):
        self.reset()

    def reset(self):
        self.active = False
        self.group_id = None
        self.topic_id = None
        self.uploads = {"texts": 0, "photos": 0, "videos": 0, "documents": 0}
        self.pending_messages = []

    def is_authorized(self, user_id):
        return user_id == AUTHORIZED_USER_ID

session = SessionManager()

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not session.is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ *Unauthorized access!*", parse_mode="Markdown")
        return

    text = (
        "👋 *Welcome to CA Inter X Premium Bot!*\n\n"
        "🚀 This bot helps you manage media uploads, forward-free posting, and organized topics in your groups.\n\n"
        "Use /help to see available commands."
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not session.is_authorized(update.effective_user.id):
        return

    text = (
        "📖 *Available Commands:*\n\n"
        "📚 /groups — Choose a group to post in\n"
        "❌ /cancel — Cancel current session\n"
        "✅ /done — Post all uploaded content\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# /groups command
async def groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not session.is_authorized(update.effective_user.id):
        return

    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"group_{gid}")] for gid, name in GROUPS.items()
    ]
    await update.message.reply_text("📌 *Select a group:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# Handle button clicks
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not session.is_authorized(query.from_user.id):
        return

    data = query.data

    if data.startswith("group_"):
        session.group_id = data.split("_")[1]
        await query.message.reply_text(f"📌 *Selected Group:* {GROUPS[session.group_id]}\n\n"
                                       "Now enter your topic name to start a new session.", parse_mode="Markdown")
        session.active = False  # reset session before starting new

    elif data.startswith("topic_"):
        topic_id = int(data.split("_")[1])
        session.topic_id = topic_id
        session.active = True
        await query.message.reply_text(f"📝 *Selected Topic ID:* `{topic_id}`\n\nNow send your media/messages.", parse_mode="Markdown")

# Handle topic creation via /topic <name>
async def topic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not session.is_authorized(update.effective_user.id):
        return

    if not session.group_id:
        await update.message.reply_text("⚠️ First select a group using /groups")
        return

    topic_name = ' '.join(context.args)
    if not topic_name:
        await update.message.reply_text("Usage: /topic <topic name>")
        return

    result = await context.bot.create_forum_topic(chat_id=session.group_id, name=topic_name)
    session.topic_id = result.message_thread_id
    session.active = True

    await update.message.reply_text(f"✅ *Topic created:* {topic_name}\nTopic ID: `{result.message_thread_id}`\n\nNow send your media/messages.", parse_mode="Markdown")

# Upload handler
async def upload_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not session.is_authorized(update.effective_user.id) or not session.active:
        return

    message = update.message
    session.pending_messages.append(message)

    if message.text:
        session.uploads["texts"] += 1
    elif message.photo:
        session.uploads["photos"] += 1
    elif message.video:
        session.uploads["videos"] += 1
    elif message.document:
        session.uploads["documents"] += 1

# /done command
async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not session.is_authorized(update.effective_user.id):
        return

    if not session.active:
        await update.message.reply_text("⚠️ No active session.")
        return

    count = session.uploads

    for msg in session.pending_messages:
        if msg.text:
            await context.bot.send_message(chat_id=session.group_id, text=msg.text, message_thread_id=session.topic_id)
        elif msg.photo:
            await context.bot.send_photo(chat_id=session.group_id, photo=msg.photo[-1].file_id, message_thread_id=session.topic_id)
        elif msg.video:
            await context.bot.send_video(chat_id=session.group_id, video=msg.video.file_id, message_thread_id=session.topic_id)
        elif msg.document:
            await context.bot.send_document(chat_id=session.group_id, document=msg.document.file_id, message_thread_id=session.topic_id)

    report = (
        "📊 *Upload Report:*\n"
        f"📝 Texts: {count['texts']}\n"
        f"📷 Photos: {count['photos']}\n"
        f"🎥 Videos: {count['videos']}\n"
        f"📄 Documents: {count['documents']}\n"
        "➖➖➖➖➖\n"
        f"✅ Total: {sum(count.values())} items"
    )
    await update.message.reply_text(report, parse_mode="Markdown")

    session.reset()

# /cancel command
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not session.is_authorized(update.effective_user.id):
        return

    session.reset()
    await update.message.reply_text("❌ *Session cancelled.*", parse_mode="Markdown")

# App setup
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("groups", groups_command))
    app.add_handler(CommandHandler("topic", topic_command))
    app.add_handler(CommandHandler("done", done_command))
    app.add_handler(CommandHandler("cancel", cancel_command))

    app.add_handler(CallbackQueryHandler(button_handler))

    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL) & ~filters.COMMAND,
        upload_handler
    ))

    logger.info("CA Inter X Premium Bot Started.")
    app.run_polling()

if __name__ == "__main__":
    main()
