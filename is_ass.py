import os
import json
import uuid
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from keep_alive import keep_alive

keep_alive()

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
subjects = ["Internet programming(IP)", "Information security", "Networking", "Ecommerce", "OOSAD", "Mobile computing"]

if not BOT_TOKEN or not ADMIN_ID:
    raise ValueError("BOT_TOKEN or ADMIN_ID not found in .env file.")

exam_dates = []
submitted_files = []
user_ids = set()

# === File I/O Helpers ===
def save_user_ids():
    with open("user_ids.json", "w") as f:
        json.dump(list(user_ids), f)

def load_user_ids():
    global user_ids
    try:
        with open("user_ids.json", "r") as f:
            user_ids = set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        user_ids = set()

def save_exam_dates():
    with open("exam_dates.json", "w") as f:
        json.dump(exam_dates, f)

def load_exam_dates():
    global exam_dates
    try:
        with open("exam_dates.json", "r") as f:
            exam_dates = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        exam_dates = []

def save_submitted_files():
    with open("submitted_files.json", "w") as f:
        json.dump(submitted_files, f)

def load_submitted_files():
    global submitted_files
    try:
        with open("submitted_files.json", "r") as f:
            submitted_files = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        submitted_files = []

def escape_markdown_v2(text):
    special_chars = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{char}" if char in special_chars else char for char in text)

# Load data on startup
load_user_ids()
load_exam_dates()
load_submitted_files()

# === Bot Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_ids.add(update.effective_user.id)
    save_user_ids()
    is_admin = str(update.effective_user.id) == ADMIN_ID

    keyboard = [
        ["Exam Announcement", "View Assignments"] if is_admin else ["Submit Group Assignment", "Submit Individual Assignment"],
        ["Add Exam Date", "Delete Exam"] if is_admin else ["Exam Announcement"],
        ["Post Message", "Buy me coffee"] if is_admin else ["Manage Files", "Buy me coffee"]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    name = update.effective_user.first_name or "Student"
    
    await update.message.reply_text(
        f"👋 Hello {escape_markdown_v2(name)}\\! 🫠🫠 Welcome to *IS Section 3 Bot*\\! 🫠🫠\n\n"
        "📚 I'm here to help you with assignments, exams, and more\\. Let's get started\\! 🚀",
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

async def handle_assignment_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[subject] for subject in subjects]
    keyboard.append(["Exit"])

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "📚 🙏🏻 *Enter the date when you submit the assignment in the caption.* 🙏🏻\n\n"
        "Please select the subject for which you want to submit the assignment:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    context.user_data["selecting_subject"] = True

async def handle_file_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document:
        await update.message.reply_text("⚠️ Please send a valid document.")
        return

    file = update.message.document
    if file.file_size > 50 * 1024 * 1024:  # 50 MB in bytes
        await update.message.reply_text("❌ The file is too large. Please upload a file smaller than 50 MB.")
        return

    if "selected_subject" not in context.user_data:
        await update.message.reply_text("⚠️ Please select a subject first.")
        return

    subject = context.user_data["selected_subject"]
    os.makedirs(f"submissions/{subject}", exist_ok=True)
    file_path = f"submissions/{subject}/{file.file_name}"
    
    try:
        new_file = await context.bot.get_file(file.file_id)
        await new_file.download_to_drive(file_path)
    except Exception as e:
        await update.message.reply_text(f"❌ Error downloading file: {str(e)}")
        return

    submitted_files.append({
        "file_name": file.file_name,
        "file_id": file.file_id,
        "submitted_by": update.effective_user.username or "Unknown User",
        "subject": subject,
        "submission_date": datetime.now().strftime("%Y-%m-%d")
    })
    save_submitted_files()

    await update.message.reply_text(f"✅ File '{file.file_name}' for *{subject}* submitted successfully!")
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📥 New assignment submitted for *{subject}* by @{update.effective_user.username or 'Unknown'}."
    )
    context.user_data.pop("selected_subject", None)

async def handle_view_assignments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to view assignments.")
        return

    keyboard = [[subject] for subject in subjects]
    keyboard.append(["Exit"])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "📅 *Assignments*:\n\n"
        "Click on an the subject below to view its details! 💪",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    context.user_data["viewing_subject"] = True

async def handle_add_exam_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to add exams.")
        return

    context.user_data["adding_exam"] = {"step": "name"}
    await update.message.reply_text("📚 Enter exam name:")

async def handle_delete_exam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to delete exams.")
        return

    if not exam_dates:
        await update.message.reply_text("📭 No exams to delete.")
        return

    context.user_data["deleting_exam"] = True
    await show_exams(update, context)
    await update.message.reply_text("Please enter the exam number to delete.")

async def handle_exam_announcement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not exam_dates:
        await update.message.reply_text("ℹ️ No exams scheduled.")
        return

    is_admin = str(update.effective_user.id) == ADMIN_ID
    keyboard = [[InlineKeyboardButton(f"📚 {exam['name']}", callback_data=f"exam_{i}")] for i, exam in enumerate(exam_dates)]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if is_admin:
        await update.message.reply_text("📅 Scheduled exams:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("📅 Click on an exam to view its details:", reply_markup=reply_markup)

async def handle_exam_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not query.data or "_" not in query.data:
        await query.edit_message_text("❌ Invalid exam selection.")
        return

    try:
        index = int(query.data.split("_")[1])
        if 0 <= index < len(exam_dates):
            exam = exam_dates[index]
            await query.edit_message_text(
                f"📚 *Exam Details:*\n"
                f"📖 *Name:* {exam['name']}\n"
                f"📅 *Date:* {exam['date']}\n"
                f"⏰ *Time:* {exam['time']}\n"
                f"📝 *Content:* {exam['content']}\n\n"
                "✅ Stay prepared!",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text("❌ Invalid exam index.")
    except (ValueError, IndexError):
        await query.edit_message_text("❌ An error occurred while processing your request.")

async def handle_post_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to broadcast messages.")
        return

    context.user_data["pending_broadcast"] = True
    await update.message.reply_text("✉️ Send the message to broadcast.")

async def buy_me_coffee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Buy me coffee? @kipa_s 😁😁")

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if context.user_data.get("deleting_exam"):
        try:
            idx = int(text) - 1
            if 0 <= idx < len(exam_dates):
                removed = exam_dates.pop(idx)
                save_exam_dates()
                await update.message.reply_text(f"✅ Deleted exam: {removed['name']}")
            else:
                await update.message.reply_text("❌ Invalid exam number.")
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number.")
        context.user_data.pop("deleting_exam", None)
        return

    if context.user_data.get("pending_broadcast"):
        context.user_data["broadcast_message"] = text
        context.user_data["confirm_broadcast"] = True
        context.user_data["pending_broadcast"] = False
        await update.message.reply_text(f"📢 Preview:\n{text}\n\nType 'yes' to send or 'no' to cancel.")
        return

    if context.user_data.get("confirm_broadcast"):
        if text.lower() == "yes":
            message = context.user_data["broadcast_message"]
            failed = 0
            for uid in user_ids:
                try:
                    await context.bot.send_message(chat_id=uid, text=message)
                except Exception:
                    failed += 1
            await update.message.reply_text(f"✅ Broadcast complete. Failed to reach {failed} user(s).")
        else:
            await update.message.reply_text("❌ Broadcast canceled.")
        context.user_data.pop("confirm_broadcast", None)
        context.user_data.pop("broadcast_message", None)
        return
    
    if context.user_data.get("selecting_subject"):
        if text in subjects:
            context.user_data["selected_subject"] = text
            context.user_data["selecting_subject"] = False
            await update.message.reply_text(
                f"✅ You selected *{text}*. Please upload your assignment file now.",
                parse_mode="Markdown"
            )
        elif text == "Exit":
            await return_to_main_menu(update, context)
        else:
            await update.message.reply_text("❌ Invalid subject. Please select a valid subject from the list.")
        return

    if context.user_data.get("viewing_subject"):
        if text in subjects:
            context.user_data["viewing_subject"] = False
            subject_files = [file for file in submitted_files if file.get("subject") == text]
            
            if not subject_files:
                await update.message.reply_text(f"ℹ️ No assignments submitted for *{text}*.")
                return

            for file in subject_files:
                try:
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=file["file_id"],
                        caption=f"📂 File: {file['file_name']}\nSubmitted by: @{file['submitted_by']}"
                    )
                except Exception as e:
                    await update.message.reply_text(f"❌ Error sending file {file['file_name']}: {str(e)}")
            
            await update.message.reply_text(f"✅ All assignments for *{text}* have been sent.")
        elif text == "Exit":
            await return_to_main_menu(update, context)
        else:
            await update.message.reply_text("❌ Invalid subject. Please select a valid subject from the list.")
        return
   
    if context.user_data.get("filtering_by_date"):
        try:
            entered_date = datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m-%d")
            context.user_data["filtering_by_date"] = False
            date_files = [file for file in submitted_files if file.get("submission_date") == entered_date]
            
            if not date_files:
                await update.message.reply_text(f"ℹ️ No assignments were submitted on *{entered_date}*.")
                return

            for file in date_files:
                try:
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=file["file_id"],
                        caption=f"📂 File: {file['file_name']}\nSubject: {file['subject']}\nSubmitted by: @{file['submitted_by']}\nDate: {file['submission_date']}"
                    )
                except Exception as e:
                    await update.message.reply_text(f"❌ Error sending file {file['file_name']}: {str(e)}")
            
            await update.message.reply_text(f"✅ All assignments submitted on *{entered_date}* have been sent.")
        except ValueError:
            await update.message.reply_text("❌ Invalid date format. Please enter the date in `YYYY-MM-DD` format.")
        return
    
    if "adding_exam" in context.user_data:
        step = context.user_data["adding_exam"]["step"]

        if step == "name":
            context.user_data["adding_exam"]["name"] = text
            context.user_data["adding_exam"]["step"] = "date"
            await update.message.reply_text("📅 Enter exam date (YYYY-MM-DD):")

        elif step == "date":
            try:
                datetime.strptime(text, "%Y-%m-%d")
                context.user_data["adding_exam"]["date"] = text
                context.user_data["adding_exam"]["step"] = "time"
                await update.message.reply_text("⏰ Enter exam time (HH:MM):")
            except ValueError:
                await update.message.reply_text("❌ Invalid date format.")

        elif step == "time":
            try:
                datetime.strptime(text, "%H:%M")
                context.user_data["adding_exam"]["time"] = text
                context.user_data["adding_exam"]["step"] = "content"
                await update.message.reply_text("📝 Enter exam content (e.g., syllabus):")
            except ValueError:
                await update.message.reply_text("❌ Invalid time format.")

        elif step == "content":
            context.user_data["adding_exam"]["content"] = text
            context.user_data["adding_exam"]["step"] = "verify"
            data = context.user_data["adding_exam"]
            await update.message.reply_text(
                f"📚 Confirm:\nName: {data['name']}\nDate: {data['date']}\nTime: {data['time']}\nContent: {data['content']}\nType 'yes' to confirm or 'no' to cancel."
            )

        elif step == "verify":
            if text.lower() == "yes":
                data = context.user_data["adding_exam"]
                exam_dates.append({"id": str(uuid.uuid4()), **data})
                save_exam_dates()
                await update.message.reply_text(f"✅ Exam '{data['name']}' scheduled.")
            else:
                await update.message.reply_text("❌ Exam scheduling canceled.")
            context.user_data.pop("adding_exam", None)
        return

    if text == "Exit":
        await return_to_main_menu(update, context)
        return

async def return_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Helper function to return to the main menu."""
    is_admin = str(update.effective_user.id) == ADMIN_ID
    keyboard = [
        ["Exam Announcement", "View Assignments"] if is_admin else ["Submit Group Assignment", "Submit Individual Assignment"],
        ["Add Exam Date", "Delete Exam"] if is_admin else ["Exam Announcement"],
        ["Post Message", "Buy me coffee"] if is_admin else ["Manage Files", "Buy me coffee"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("🔙 Returning to the main menu:", reply_markup=reply_markup)
    
    # Clear any active context
    for key in ["selecting_subject", "viewing_subject", "filtering_by_date", "adding_exam"]:
        context.user_data.pop(key, None)

async def remove_past_exams():
    while True:
        now = datetime.now()
        for exam in list(exam_dates):
            try:
                exam_date = datetime.strptime(exam["date"], "%Y-%m-%d")
                if exam_date < now:
                    exam_dates.remove(exam)
            except ValueError:
                continue
        save_exam_dates()
        await asyncio.sleep(3600)  # Check every hour

async def show_exams(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not exam_dates:
        await update.message.reply_text("ℹ️ No exams scheduled.")
        return

    msg = "\n".join([
        f"{i+1}. {e['name']} - {e['date']} {e['time']} (ID: {e['id'][:6]})" 
        for i, e in enumerate(exam_dates)
    ])
    await update.message.reply_text(f"📚 Exams:\n{msg}")

async def handle_manage_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_files = [
        file for file in submitted_files 
        if file.get("submitted_by") == (update.effective_user.username or str(update.effective_user.id))
    ]

    if not user_files:
        await update.message.reply_text("ℹ️ You have not submitted any files.")
        return

    keyboard = [
        [InlineKeyboardButton(f"📂 {file['file_name']}", callback_data=f"delete_{i}")]
        for i, file in enumerate(user_files)
    ]
    keyboard.append([InlineKeyboardButton("Exit", callback_data="exit_manage_files")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📂 Your submitted files:", reply_markup=reply_markup)

async def handle_file_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "exit_manage_files":
        await return_to_main_menu(update, context)
        return

    try:
        if query.data.startswith("delete_"):
            index = int(query.data.split("_")[1])
            user_files = [
                file for file in submitted_files 
                if file.get("submitted_by") == (query.from_user.username or str(query.from_user.id))
            ]

            if 0 <= index < len(user_files):
                file = user_files[index]
                file_path = f"submissions/{file['subject']}/{file['file_name']}"

                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    submitted_files.remove(file)
                    save_submitted_files()
                    await query.edit_message_text(f"✅ File '{file['file_name']}' has been deleted.")
                except Exception as e:
                    await query.edit_message_text(f"❌ Error deleting file: {str(e)}")
            else:
                await query.edit_message_text("❌ Invalid file selection.")
    except (ValueError, IndexError) as e:
        await query.edit_message_text("❌ An error occurred while processing your request.")

async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    is_admin = str(update.effective_user.id) == ADMIN_ID
    
    if is_admin:
        help_text = (
            "📖 *Help Menu (Admin)*\n\n"
            "Here are the commands you can use:\n\n"
            "🔹 /start - Start the bot and display the main menu\n"
            "🔹 /exams - View the list of scheduled exams\n"
            "🔹 /help - Show this help message\n\n"
            "👨‍💻 *Admin Features:*\n"
            "1️⃣ Add Exam Date - Schedule a new exam\n"
            "2️⃣ Delete Exam - Remove an existing exam\n"
            "3️⃣ Post Message - Broadcast a message to all users\n"
            "4️⃣ View Assignments - Access submitted assignments\n"
        )
    else:
        help_text = (
            "📖 *Help Menu (Student)*\n\n"
            "/start - Start the bot and display the main menu\n"
            "/exams - View the list of scheduled exams\n"
            "/help - Show this help message\n\n"
            "*Student Features:*\n"
            "1. Submit Group Assignment - Upload your group assignment\n"
            "2. Submit Individual Assignment - Upload your individual assignment\n"
            "3. Exam Announcement - View scheduled exams\n"
            "4. Buy Me Coffee - A fun interaction with the bot\n"
        )
    
    await update.message.reply_text(help_text, parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("exams", show_exams))
    app.add_handler(CommandHandler("help", handle_help))

    # Callback handlers
    app.add_handler(CallbackQueryHandler(handle_exam_details, pattern="^exam_"))
    app.add_handler(CallbackQueryHandler(handle_file_deletion, pattern="^(delete_|exit_manage_files)"))

    # Message handlers
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("Submit Group Assignment"), handle_assignment_button))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("Submit Individual Assignment"), handle_assignment_button))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("Exam Announcement"), handle_exam_announcement))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("Add Exam Date"), handle_add_exam_date))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("Delete Exam"), handle_delete_exam))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("View Assignments"), handle_view_assignments))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("Post Message"), handle_post_message))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("Buy me coffee"), buy_me_coffee))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("Manage Files"), handle_manage_files))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file_submission))
    app.add_handler(MessageHandler(filters.TEXT, text_router))

    # Error handling
    app.add_error_handler(error_handler)

    # Startup task
    async def startup(_):
        asyncio.create_task(remove_past_exams())

    app.post_init = startup
    app.run_polling()

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors and send a message to the user."""
    from telegram.error import NetworkError
    
    try:
        raise context.error
    except NetworkError:
        print("⚠️ Network error occurred")
    except Exception as e:
        print(f"⚠️ Error: {str(e)}")
        if update and update.effective_message:
            await update.effective_message.reply_text("❌ An error occurred. Please try again.")

if __name__ == "__main__":
    main()
