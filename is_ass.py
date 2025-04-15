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

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

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
    except FileNotFoundError:
        user_ids = set()

def save_exam_dates():
    with open("exam_dates.json", "w") as f:
        json.dump(exam_dates, f)

def load_exam_dates():
    global exam_dates
    try:
        with open("exam_dates.json", "r") as f:
            exam_dates = json.load(f)
    except FileNotFoundError:
        exam_dates = []

def save_submitted_files():
    with open("submitted_files.json", "w") as f:
        json.dump(submitted_files, f)

def load_submitted_files():
    global submitted_files
    try:
        with open("submitted_files.json", "r") as f:
            submitted_files = json.load(f)
    except FileNotFoundError:
        submitted_files = []

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
        ["Add Exam Date", "Delete Exam"] if is_admin else [],
        ["Post Message", "Buy me coffee"] if is_admin else ["Exam Announcement", "Buy me coffee"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    name = update.effective_user.first_name or "Student"
    await update.message.reply_text(f"Hello {name}! Welcome to IS section 3 Bot:", reply_markup=reply_markup)

async def handle_assignment_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    option = update.message.text
    if "Group" in option:
        await update.message.reply_text("*You selected Submit Group Assignment.*\nPlease upload your file.", parse_mode="Markdown")
    elif "Individual" in option:
        await update.message.reply_text("*You selected Submit Individual Assignment.*\nPlease upload your file.", parse_mode="Markdown")

async def handle_file_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.document:
        file = update.message.document
        os.makedirs("submissions", exist_ok=True)
        file_path = f"submissions/{file.file_name}"
        new_file = await context.bot.get_file(file.file_id)
        await new_file.download_to_drive(file_path)

        submitted_files.append({
            "file_name": file.file_name,
            "file_id": file.file_id,
            "submitted_by": update.effective_user.username or "Unknown User"
        })
        save_submitted_files()

        await update.message.reply_text(f"✅ File '{file.file_name}' submitted successfully!")
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"📥 New assignment submitted by @{update.effective_user.username or 'Unknown'}.")
    else:
        await update.message.reply_text("⚠️ Please send a valid document.")

async def handle_view_assignments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) == ADMIN_ID:
        if submitted_files:
            for file in submitted_files:
                await context.bot.send_document(
                    chat_id=ADMIN_ID,
                    document=file["file_id"],
                    caption=f"📂 {file['file_name']} submitted by @{file['submitted_by']}"
                )
        else:
            await update.message.reply_text("ℹ️ No assignments submitted yet.")
    else:
        await update.message.reply_text("❌ You are not authorized.")

async def handle_add_exam_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) == ADMIN_ID:
        context.user_data["adding_exam"] = {"step": "name"}
        await update.message.reply_text("📚 Enter exam name:")

async def handle_delete_exam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not exam_dates:
        await update.message.reply_text("📭 No exams to delete.")
        return
    context.user_data["deleting_exam"] = True
    await show_exams(update, context)
    await update.message.reply_text("Please enter the exam number to delete.")

async def handle_exam_announcement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if exam_dates:
        keyboard = [[InlineKeyboardButton(f"📚 {exam['name']}", callback_data=f"exam_{i}")] for i, exam in enumerate(exam_dates)]
        await update.message.reply_text("📅 Scheduled exams:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("ℹ️ No exams scheduled.")

async def handle_exam_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    index = int(query.data.split("_")[1])
    if 0 <= index < len(exam_dates):
        exam = exam_dates[index]
        await query.edit_message_text(
            f"📚Exam name: {exam['name']}\n📅Exam Date: {exam['date']}\n⏰Exam Time: {exam['time']}\n📝Exam Content: {exam['content']}\n\n✅ Stay prepared!"
        )

async def handle_post_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) == ADMIN_ID:
        context.user_data["pending_broadcast"] = True
        await update.message.reply_text("✉️ Send the message to broadcast.")

async def buy_me_coffee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Buy me coffee? @kipa_s 😁")

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
        context.user_data.pop("deleting_exam")
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

    # Exam scheduling steps
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
                if len(exam_dates) > 4:
                    exam_dates.pop(0)
                save_exam_dates()
                await update.message.reply_text(f"✅ Exam '{data['name']}' scheduled.")
            else:
                await update.message.reply_text("❌ Exam scheduling canceled.")
            context.user_data.pop("adding_exam")

async def remove_past_exams():
    while True:
        now = datetime.now()
        for exam in list(exam_dates):
            if datetime.strptime(exam["date"], "%Y-%m-%d") < now:
                exam_dates.remove(exam)
        save_exam_dates()
        await asyncio.sleep(3600)

async def show_exams(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if exam_dates:
        msg = "\n".join([
            f"{i+1}. {e['name']} - {e['date']} {e['time']} (ID: {e['id'][:6]})" for i, e in enumerate(exam_dates)
        ])
        await update.message.reply_text(f"📚 Exams:\n{msg}")
    else:
        await update.message.reply_text("ℹ️ No exams scheduled.")

# === Main App ===
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("exams", show_exams))
    app.add_handler(CallbackQueryHandler(handle_exam_details))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("Submit Group Assignment"), handle_assignment_button))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("Submit Individual Assignment"), handle_assignment_button))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("Exam Announcement"), handle_exam_announcement))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("Add Exam Date"), handle_add_exam_date))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("Delete Exam"), handle_delete_exam))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("View Assignments"), handle_view_assignments))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("Post Message"), handle_post_message))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("Buy me coffee"), buy_me_coffee))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file_submission))
    app.add_handler(MessageHandler(filters.TEXT, text_router))

    async def startup(_: ApplicationBuilder):
        asyncio.create_task(remove_past_exams())

    app.post_init = startup
    app.run_polling()

if __name__ == "__main__":
    main()
