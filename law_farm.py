from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackContext
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from collections import Counter

# === CONFIGURATION ===
SHEET_URL = "https://docs.google.com/spreadsheets/d/1XA2x26P6FQktl1JR8YdZVOPW3FqcRYzIlvxJnxgrdKE/edit"
TAB_NAME = "New law firms"
CREDENTIAL_PATH = r"X:\instalink\credentials.json"
BOT_TOKEN = "8082606695:AAEBQuoUMuC3eD7_sNCaUqSAHXIi-51azlU"

# === SHEET SETUP ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIAL_PATH, scope)
client = gspread.authorize(creds)
sheet = client.open_by_url(SHEET_URL).worksheet(TAB_NAME)

# === BOT STATES ===
FIRM, WEBSITE, EMAIL, CONTACT = range(4)
user_data = {}

# === MAIN MENU BUTTON ===
main_menu = ReplyKeyboardMarkup(
    [['➕ Add Law Firm'], ['📈 Daily Report', '👤 My Profile'], ['📆 Weekly Summary', '🏆 Leaderboard']],
    resize_keyboard=True
)

def start(update, context):
    update.message.reply_text("👋 Welcome! What would you like to do?", reply_markup=main_menu)

def add_start(update, context):
    update.message.reply_text("🏢 Please enter the Law Firm Name:")
    return FIRM

def get_firm(update, context):
    firm_name = update.message.text.strip()
    uid = update.effective_user.id
    username = f"@{update.effective_user.username or 'unknown'}"
    user_data[uid] = {
        'firm': firm_name,
        'username': username
    }

    all_records = sheet.get_all_records(head=2)
    for row in all_records:
        if row.get('Law Firm Name', '').strip().lower() == firm_name.lower():
            update.message.reply_text(
                f"⚠️ *Duplicate Found!*\n\nAlready added by `{row.get('Your Name in Telegram', '')}`\n"
                f"🏢 {row.get('Law Firm Name', '')}\n🌐 {row.get('Website URL', '')}\n📧 {row.get('Email', '')}",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

    update.message.reply_text("✅ Firm not found. Now enter the Website URL:")
    return WEBSITE

def get_website(update, context):
    uid = update.effective_user.id
    user_data[uid]['website'] = update.message.text.strip()
    update.message.reply_text("📧 Now enter the Email address (or type 'none'):")
    return EMAIL

def get_email(update, context):
    uid = update.effective_user.id
    email = update.message.text.strip()
    user_data[uid]['email'] = email if email.lower() != "none" else "None"
    update.message.reply_text("📞 Finally, enter the Contact Number (or type 'none'):")
    return CONTACT

def find_next_user_row_auto(username):
    all_values = sheet.get_all_values()
    user_rows = []

    for i, row in enumerate(all_values[2:], start=3):  # skip first 2 header rows
        if len(row) > 0 and row[0].strip() == username:
            user_rows.append(i)

    if user_rows:
        return max(user_rows) + 1
    else:
        return len(all_values) + 1

def get_contact(update, context):
    uid = update.effective_user.id
    contact = update.message.text.strip()
    user_info = user_data[uid]
    user_info['contact'] = contact if contact.lower() != "none" else "None"

    username = user_info['username']
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    row_data = [''] * 14
    row_data[0] = username
    row_data[1] = user_info['firm']
    row_data[2] = user_info['website']
    row_data[3] = user_info['email']
    row_data[4] = user_info['contact']
    row_data[-1] = timestamp

    next_row = find_next_user_row_auto(username)
    sheet.update(values=[row_data], range_name=f"A{next_row}:N{next_row}")

    update.message.reply_text("✅ Law firm added successfully!", reply_markup=main_menu)
    return ConversationHandler.END

def cancel(update, context):
    update.message.reply_text("❌ Cancelled.", reply_markup=main_menu)
    return ConversationHandler.END

def is_recent(timestamp_str, threshold):
    try:
        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        return timestamp >= threshold
    except:
        return False

def handle_buttons(update, context):
    text = update.message.text
    uid = update.effective_user.id
    username = f"@{update.effective_user.username or 'unknown'}"
    all_data = sheet.get_all_records(head=2)

    if text == '➕ Add Law Firm':
        return add_start(update, context)

    elif text == '📈 Daily Report':
        today = datetime.now().strftime('%Y-%m-%d')
        timestamps = sheet.col_values(14)[2:]
        indices = [i for i, val in enumerate(timestamps, start=3) if val.startswith(today)]
        if indices:
            update.message.reply_text(f"📅 Date: {today}\n📊 Firms Added Today: {len(indices)}\n🧾 Rows: {indices[0]} ➡️ {indices[-1]}")
        else:
            update.message.reply_text(f"📅 Date: {today}\n📊 No entries today.")

    elif text == '👤 My Profile':
        user_entries = [row for row in all_data if row.get('Your Name in Telegram') == username]
        total = len(user_entries)
        week_ago = datetime.now() - timedelta(days=7)
        weekly = [row for row in user_entries if is_recent(row.get('Timestamp'), week_ago)]
        update.message.reply_text(
            f"👤 Your Profile\n🧑 Name: {username}\n🗂️ Total Law Firms Added: {total}\n📅 Last 7 Days: {len(weekly)}"
        )

    elif text == '📆 Weekly Summary':
        week_ago = datetime.now() - timedelta(days=7)
        recent_entries = [row for row in all_data if is_recent(row.get('Timestamp'), week_ago)]
        counter = Counter(row.get('Your Name in Telegram') for row in recent_entries)
        lines = [f"📊 Weekly Summary ({(datetime.now() - timedelta(days=6)).date()} ➡️ {datetime.now().date()})\n"]
        for name, count in counter.most_common():
            lines.append(f"🧑 {name} — {count} entries")
        lines.append(f"\n✅ Total Firms Added This Week: {sum(counter.values())}")
        update.message.reply_text("\n".join(lines))

    elif text == '🏆 Leaderboard':
        counter = Counter(row.get('Your Name in Telegram') for row in all_data)
        top = counter.most_common(5)
        lines = ["🏆 Top Contributors (All-Time)\n"]
        for i, (name, count) in enumerate(top, 1):
            medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i - 1]
            lines.append(f"{medal} {name} — {count} entries")
        update.message.reply_text("\n".join(lines))

    else:
        update.message.reply_text("❓ Unknown command. Use the menu buttons.", reply_markup=main_menu)

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('^(➕ Add Law Firm)$'), add_start)],
        states={
            FIRM: [MessageHandler(Filters.text & ~Filters.command, get_firm)],
            WEBSITE: [MessageHandler(Filters.text & ~Filters.command, get_website)],
            EMAIL: [MessageHandler(Filters.text & ~Filters.command, get_email)],
            CONTACT: [MessageHandler(Filters.text & ~Filters.command, get_contact)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(conv_handler)
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_buttons))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
