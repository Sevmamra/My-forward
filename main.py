import os
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

import os

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Render के Env Vars से लेगा
MAIN_GROUP_ID = int(os.getenv("MAIN_GROUP_ID"))  # Render पर सेट करें
AUTHORIZED_USER_ID = int(os.getenv("AUTHORIZED_USER_ID"))  # Render पर सेट करें
topics = {}

def is_authorized_user(user_id: int) -> bool:
    return user_id == AUTHORIZED_USER_ID

def is_authorized_group(chat_id: int) -> bool:
    return chat_id == MAIN_GROUP_ID

def start(update: Update, context: CallbackContext):
    if not is_authorized_user(update.message.from_user.id):
        update.message.reply_text("❌ आप इस बॉट का उपयोग नहीं कर सकते!")
        return
    update.message.reply_text("🎉 बॉट चालू है! /upload <TOPIC> लिखकर फाइलें भेजें।")

def handle_dm(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if not is_authorized_user(user_id):
        update.message.reply_text("❌ आप इस बॉट का उपयोग नहीं कर सकते!")
        return

    if not update.message.caption or not update.message.caption.startswith("/upload"):
        return

    try:
        topic_name = update.message.caption.split(" ")[1].upper()
        file_id = update.message.video.file_id if update.message.video else update.message.document.file_id

        if topic_name not in topics:
            message = context.bot.send_message(
                chat_id=MAIN_GROUP_ID,
                text=f"📌 नया टॉपिक: {topic_name}",
            )
            topics[topic_name] = message.message_id

        if update.message.video:
            context.bot.send_video(
                chat_id=MAIN_GROUP_ID,
                video=file_id,
                reply_to_message_id=topics[topic_name],
                caption=f"📹 {topic_name} - लेक्चर"
            )
        elif update.message.document:
            context.bot.send_document(
                chat_id=MAIN_GROUP_ID,
                document=file_id,
                reply_to_message_id=topics[topic_name],
                caption=f"📄 {topic_name} - नोट्स"
            )
        update.message.reply_text(f"✅ '{topic_name}' में अपलोड हो गया!")
    except Exception as e:
        update.message.reply_text(f"❌ एरर: {e}")

def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.private & (~Filters.command), handle_dm))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
