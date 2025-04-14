import os
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Load environment variables from .env file
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")  # Add the admin's Telegram ID in the .env file

exam_dates = []
submitted_files = []  # Store submitted file details for the admin to view

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Define the buttons
    if str(update.effective_user.id) == ADMIN_ID:
        keyboard = [
            ["Submit Group Assignment", "Submit Individual Assignment"],
            ["Exam Announcement","View Assignments"],
            ["Add Exam Date"]  # Admin-only button
        ]
    else:
        keyboard = [
            ["Submit Group Assignment", "Submit Individual Assignment"],
            ["Exam Announcement","Buy me coffee"]
        ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    user_name = update.effective_user.first_name or "Student"
    await update.message.reply_text(
        f"Hello {user_name}! 👋\nWelcome to  IS section 3 Bot, Am ur virtual assistance. Please choose an option below:",
        reply_markup=reply_markup
    )

async def buy_me_coffee(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Buy me a coffee? @kipa_s 😁😁😁i can't wait dawg...")
async def handle_assignment_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Prompt the user to send a file
    option = update.message.text
    if "Group" in option:
        await update.message.reply_text(
            "You selected **Submit Group Assignment**. 📂\nPlease upload your group assignment file now."
        )
    elif "Individual" in option:
        await update.message.reply_text(
            "You selected **Submit Individual Assignment**. 📄\nPlease upload your individual assignment file now."
        )

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

            await update.message.reply_text(
                f"✅ Your file '{file_name}' has been successfully submitted! 🎉\nThank you for submitting your assignment."
            )

            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text="📥 New assignment is submitted."
            )

            submitted_files.append({"file_name": file_name, "file_id": file_id, "submitted_by": update.effective_user.username or "Unknown User"})
        else:
            await update.message.reply_text("⚠️ Please send a valid file. Only documents are accepted.")
    except Exception as e:
        # Notify the user of the failure
        await update.message.reply_text(
            "❌ There was an error submitting your file. Please try again later or contact support."
        )
        print(f"Error: {e}")

async def handle_view_assignments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.effective_user.id) == ADMIN_ID:
        if submitted_files:
            for file in submitted_files:
                await context.bot.send_document(
                    chat_id=ADMIN_ID,
                    document=file["file_id"],
                    caption=f"📂 File: {file['file_name']}\nSubmitted by: @{file['submitted_by']}"
                )
        else:
            await update.message.reply_text("ℹ️ No assignments have been submitted yet.")
    else:
        await update.message.reply_text("❌ You are not authorized to view this information.")


async def handle_add_exam_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.effective_user.id) == ADMIN_ID:
        await update.message.reply_text(
            "Please enter the exam name."
        )
        context.user_data["adding_exam"] = {"step": "name"}
    else:
        await update.message.reply_text("❌ You are not authorized to add exam details.")

async def process_exam_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if "adding_exam" in context.user_data:
        step = context.user_data["adding_exam"]["step"]

        if step == "name":
            context.user_data["adding_exam"]["name"] = update.message.text.strip()
            context.user_data["adding_exam"]["step"] = "date"
            await update.message.reply_text("Please enter the exam date in the format `YYYY-MM-DD`.")
        
        elif step == "date":
            exam_date = update.message.text.strip()
            if len(exam_date) == 10 and exam_date.count("-") == 2:
                context.user_data["adding_exam"]["date"] = exam_date
                context.user_data["adding_exam"]["step"] = "time"
                await update.message.reply_text("Please enter the exam time in the format `HH:MM`.")
            else:
                await update.message.reply_text("❌ Invalid date format. Please enter the date in the format `YYYY-MM-DD`.")
        
        elif step == "time":
            exam_time = update.message.text.strip()
            if len(exam_time) == 5 and exam_time.count(":") == 1:
                context.user_data["adding_exam"]["time"] = exam_time

                exam_name = context.user_data["adding_exam"]["name"]
                exam_date = context.user_data["adding_exam"]["date"]
                exam_time = context.user_data["adding_exam"]["time"]
                exam_details = f"{exam_name} on {exam_date} at {exam_time}"
                exam_dates.append(exam_details)

                if len(exam_dates) > 4:
                    exam_dates.pop(0)

                await update.message.reply_text(f"✅ Exam '{exam_name}' has been scheduled for {exam_date} at {exam_time}!")
                # Clear the flag
                del context.user_data["adding_exam"]
            else:
                await update.message.reply_text("❌ Invalid time format. Please enter the time in the format `HH:MM`.")

# Define a handler for viewing exam announcements
async def handle_exam_announcement(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.effective_user.id) == ADMIN_ID:
        # Admin can view all exam details
        if exam_dates:
            await update.message.reply_text(
                "📅 Here are the scheduled exams:\n" + "\n".join(f"- {exam}" for exam in exam_dates)
            )
        else:
            await update.message.reply_text("ℹ️ No exams have been scheduled yet.")
    else:
        # Students can view the last 4 exam details
        if exam_dates:
            await update.message.reply_text(
                "📅 Here are the last 4 scheduled exams:\n" + "\n".join(f"- {exam}" for exam in exam_dates)
            )
        else:
            await update.message.reply_text("ℹ️ No exams have been scheduled yet.")
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))

    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("Submit Group Assignment"), handle_assignment_button))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("Submit Individual Assignment"), handle_assignment_button))

    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("Exam Announcement"), handle_exam_announcement))

    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("Add Exam Date"), handle_add_exam_date))
     

    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("Buy me coffee"), buy_me_coffee))
    
    application.add_handler(MessageHandler(filters.TEXT, process_exam_date))

    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("View Assignments"), handle_view_assignments))

    application.add_handler(MessageHandler(filters.Document.ALL, handle_file_submission))

    application.run_polling()

if __name__ == "__main__":
    main()