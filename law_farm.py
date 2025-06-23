import asyncio
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from collections import Counter
from pytz import utc
from telegram.ext import Application, ApplicationBuilder, JobQueue
from apscheduler.schedulers.asyncio import AsyncIOScheduler


# === CONFIG ===
SHEET_URL = "https://docs.google.com/spreadsheets/d/1XA2x26P6FQktl1JR8YdZVOPW3FqcRYzIlvxJnxgrdKE/edit"
TAB_NAME = "New law firms"
CREDENTIAL_PATH = r"X:\instalink\credentials.json"
BOT_TOKEN = "8082606695:AAEBQuoUMuC3eD7_sNCaUqSAHXIi-51azlU"

# === Sheet Setup ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIAL_PATH, scope)
client = gspread.authorize(creds)
sheet = client.open_by_url(SHEET_URL).worksheet(TAB_NAME)

# === States ===
FIRM, WEBSITE, EMAIL, CONTACT = range(4)
user_data = {}

main_menu = ReplyKeyboardMarkup(
    [['➕ Add Law Firm'], ['📈 Daily Report', '👤 My Profile'], ['📆 Weekly Summary', '🏆 Leaderboard']],
    resize_keyboard=True
)

# === HANDLERS ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Choose an option:", reply_markup=main_menu)

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏢 Enter the Law Firm Name:")
    return FIRM

async def get_firm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text in main_menu.keyboard[0] + main_menu.keyboard[1] + main_menu.keyboard[2]:
        await handle_buttons(update, context)
        return ConversationHandler.END

    uid = update.effective_user.id
    username = f"@{update.effective_user.username or 'unknown'}"
    user_data[uid] = {'firm': text, 'username': username}

    headers = sheet.row_values(2)
    all_records = sheet.get_all_records(head=2, expected_headers=headers)
    for row in all_records:
        if row.get('Law Firm Name', '').strip().lower() == text.lower():
            await update.message.reply_text(
                f"⚠️ Duplicate Found!\nAlready added by `{row.get('Your Name in Telegram', '')}`\n"
                f"🏢 {row.get('Law Firm Name')}\n🌐 {row.get('Website URL')}\n📧 {row.get('Email')}",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

    await update.message.reply_text("✅ Firm not found. Now enter the Website URL:")
    return WEBSITE

async def get_website(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data[uid]['website'] = update.message.text.strip()
    await update.message.reply_text("📧 Enter Email (or type 'none'):")
    return EMAIL

async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    email = update.message.text.strip()
    user_data[uid]['email'] = email if email.lower() != "none" else "None"
    await update.message.reply_text("📞 Enter Contact Number (or type 'none'):")
    return CONTACT

async def get_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    contact = update.message.text.strip()
    user_info = user_data[uid]
    user_info['contact'] = contact if contact.lower() != "none" else "None"

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    row_data = [''] * 13
    row_data[0] = user_info['username']
    row_data[1] = user_info['firm']
    row_data[2] = user_info['website']
    row_data[3] = user_info['email']
    row_data[4] = user_info['contact']
    row_data[12] = timestamp

    sheet.append_row(row_data)
    await update.message.reply_text("✅ Law firm added successfully!", reply_markup=main_menu)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.", reply_markup=main_menu)
    return ConversationHandler.END

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id
    username = f"@{update.effective_user.username or 'unknown'}"
    headers = sheet.row_values(2)
    all_data = sheet.get_all_records(head=2, expected_headers=headers)

    if text == '➕ Add Law Firm':
        return await add_start(update, context)

    elif text == '📈 Daily Report':
        today = datetime.now().strftime('%Y-%m-%d')
        timestamps = sheet.col_values(13)[2:]
        indices = [i for i, val in enumerate(timestamps, start=3) if val.startswith(today)]
        msg = f"📅 {today}\n📊 Firms Today: {len(indices)}" if indices else f"📅 {today}\n📊 No entries today."
        await update.message.reply_text(msg)

    elif text == '👤 My Profile':
        my_entries = [r for r in all_data if r.get('Your Name in Telegram') == username]
        week_ago = datetime.now() - timedelta(days=7)
        recent = [r for r in my_entries if is_recent(r.get('Timestamp'), week_ago)]
        await update.message.reply_text(
            f"👤 Profile for {username}\n📌 Total: {len(my_entries)}\n🗓️ Last 7 Days: {len(recent)}"
        )

    elif text == '📆 Weekly Summary':
        week_ago = datetime.now() - timedelta(days=7)
        recent_entries = [r for r in all_data if is_recent(r.get('Timestamp'), week_ago)]
        counter = Counter(r.get('Your Name in Telegram') for r in recent_entries)
        lines = [f"📆 Weekly Summary\n"]
        for name, count in counter.most_common():
            lines.append(f"🧑 {name} — {count}")
        lines.append(f"\n✅ Total: {sum(counter.values())}")
        await update.message.reply_text("\n".join(lines))

    elif text == '🏆 Leaderboard':
        counter = Counter(r.get('Your Name in Telegram') for r in all_data)
        lines = ["🏆 Top Contributors\n"]
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, (name, count) in enumerate(counter.most_common(5)):
            lines.append(f"{medals[i]} {name} — {count}")
        await update.message.reply_text("\n".join(lines))

    else:
        await update.message.reply_text("❓ Unknown command. Use the menu below.", reply_markup=main_menu)

def is_recent(ts, threshold):
    try:
        return datetime.strptime(ts, '%Y-%m-%d %H:%M:%S') >= threshold
    except:
        return False

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^➕ Add Law Firm$'), add_start)],
        states={
            FIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_firm)],
            WEBSITE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_website)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
            CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_contact)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))

    app.run_polling()

if __name__ == '__main__':
    main()
