import os
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Load environment variables from .env file
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")  # Add the admin's Telegram ID in the .env file

# Define the /start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Define the buttons
    keyboard = [
        ["Submit Group Assignment", "Submit Individual Assignment"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    # Send a message with the buttons
    await update.message.reply_text(
        "Hello! I am your bot. Please choose an option:",
        reply_markup=reply_markup
    )

# Define a handler for assignment submission buttons
async def handle_assignment_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Prompt the user to send a file
    await update.message.reply_text("Please send the file for your assignment.")

# Define a handler for file submissions
async def handle_file_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # Get the file sent by the user
        if update.message.document:
            file = update.message.document
            file_id = file.file_id
            file_name = file.file_name

            # Download the file
            file_path = f"submissions/{file_name}"
            os.makedirs("submissions", exist_ok=True)  # Ensure the submissions folder exists
            new_file = await context.bot.get_file(file_id)
            await new_file.download_to_drive(file_path)

            # Notify the user of successful submission
            await update.message.reply_text(f"Your file '{file_name}' has been successfully submitted!")

            # Forward the file to the admin
            await context.bot.send_document(chat_id=ADMIN_ID, document=file.file_id, caption=f"New assignment submitted: {file_name}")
        else:
            await update.message.reply_text("Please send a valid file.")
    except Exception as e:
        # Notify the user of the failure
        await update.message.reply_text("There was an error submitting your file. Please try again later.")
        # Optionally log the error for debugging
        print(f"Error: {e}")

# Main function to set up the bot
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add the /start command handler
    application.add_handler(CommandHandler("start", start))

    # Add handlers for assignment buttons
    application.add_handler(MessageHandler(filters.Text("Submit Group Assignment"), handle_assignment_button))
    application.add_handler(MessageHandler(application.add_handler(MessageHandler(filters.Text("Submit Group Assignment"), handle_assignment_button))
.Text("Submit Individual Assignment"), handle_assignment_button))

    # Add a handler for file submissions
    application.add_handler(MessageHandler(filters.Text("Submit Group Assignment"), handle_assignment_button))
    application.add_handler(MessageHandler(filters.document, handle_file_submission))

    # Start the bot
    application.run_polling()

if __name__ == "__main__":
    main()
    