import telebot
import gspread
from google.oauth2.service_account import Credentials
import datetime
import re
import matplotlib.pyplot as plt
from io import BytesIO
import os

# Configuration from environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', r'credentials.json')  # Default to local file if not set
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')

# Google Sheets setup
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scopes)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# Telegram bot setup
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Category mapping for better parsing
CATEGORY_MAPPING = {
    'makanan': 'Makanan',
    'minuman': 'Minuman',
    'belanja': 'Belanja Online',
    'online': 'Belanja Online',
    'transportasi': 'Transportasi',
    'hiburan': 'Hiburan',
    'tagihan': 'Tagihan',
    'kopi': 'Minuman',
    'ayam': 'Makanan',
    'food': 'Makanan',
    'drink': 'Minuman',
    'shopping': 'Belanja Online',
    'transport': 'Transportasi',
    'entertainment': 'Hiburan',
    'bills': 'Tagihan'
}

# Regex-based parsing function with category mapping
def parsing_message(message):
    match = re.search(r'(?:spent|beli\s+saya)?\s*(\d+(?:\.\d+)?)(?:\s+ribu)?\s+(?:on|pada)?\s*(\w+)(?:\s+(.*))?', message.lower())
    if match:
        amount_str = match.group(1)
        category_input = match.group(2).lower()
        description = match.group(3) or ''
        amount = float(amount_str) * 1000 if 'ribu' in message.lower() else float(amount_str)
        # Map category to predefined list, fallback to 'Lain-lain'
        category = CATEGORY_MAPPING.get(category_input, 'Lain-lain')
        return amount, category, description
    return None

# Handler for /start command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    format_info = (
        "Specific format examples:\n"
        "- English: 'I spent 50 on Makanan [description]' (e.g., 'I spent 50 on Makanan groceries')\n"
        "- Indonesian: 'Beli 20 ribu pada Makanan [description]' (e.g., 'Beli 20 ribu pada Makanan ayam krispi')\n"
        "Categories: Makanan, Minuman, Belanja Online, Transportasi, Hiburan, Tagihan, Lain-lain.\n"
        "- <amount>: Number (e.g., 50, 20.5). Add 'ribu' for thousands (e.g., 20 ribu = 20,000).\n"
        "- [description]: Optional details.\n"
        "Use /report for today's total or /graph for a 30-day spending chart."
    )
    bot.reply_to(message, f"Hi! I'm your SpendTrackerBot. {format_info}")

# Handler for text messages (spending entries)
@bot.message_handler(func=lambda message: not message.text.startswith('/'))
def handle_message(message):
    parsed = parsing_message(message.text)
    if parsed:
        amount, category, description = parsed
        today = datetime.date.today().strftime('%Y-%m-%d')
        
        # Append to spreadsheet
        row = [today, amount, category, description]
        sheet.append_row(row)
        
        bot.reply_to(message, f"Added {amount} to {category} with description '{description}' on {today}.")
    else:
        format_info = (
            "Specific format examples:\n"
            "- English: 'I spent 50 on Makanan [description]' (e.g., 'I spent 50 on Makanan groceries')\n"
            "- Indonesian: 'Beli 20 ribu pada Makanan [description]' (e.g., 'Beli 20 ribu pada Makanan ayam krispi')\n"
            "Categories: Makanan, Minuman, Belanja Online, Transportasi, Hiburan, Tagihan, Lain-lain.\n"
            "- <amount>: Number (e.g., 50, 20.5). Add 'ribu' for thousands (e.g., 20 ribu = 20,000).\n"
            "- [description]: Optional details."
        )
        bot.reply_to(message, f"Sorry, I couldn't parse that. Please follow this format: {format_info}")

# Handler for /report command
@bot.message_handler(commands=['report'])
def send_report(message):
    today = datetime.date.today().strftime('%Y-%m-%d')
    data = sheet.get_all_records()  # Assumes headers: Date, Amount, Category, Description
    today_spending = [float(row['Amount']) for row in data if row['Date'] == today]
    total = sum(today_spending) if today_spending else 0.0
    bot.reply_to(message, f"Total spending for {today}: {total}.")

# Handler for /graph command
@bot.message_handler(commands=['graph'])
def send_graph(message):
    today = datetime.date.today()
    thirty_days_ago = today - datetime.timedelta(days=30)
    data = sheet.get_all_records()  # Assumes headers: Date, Amount, Category, Description
    
    # Filter data for the last 30 days and aggregate by category
    spending_data = {}
    for row in data:
        date = datetime.datetime.strptime(row['Date'], '%Y-%m-%d').date()
        if thirty_days_ago <= date <= today:
            category = row['Category']
            amount = float(row['Amount'])
            spending_data[category] = spending_data.get(category, 0) + amount
    
    if not spending_data:
        bot.reply_to(message, "No spending data for the last 30 days.")
        return
    
    # Create bar chart
    categories = list(spending_data.keys())
    amounts = list(spending_data.values())
    
    plt.figure(figsize=(10, 6))
    plt.bar(categories, amounts, color='skyblue')
    plt.title(f'Spending by Category (Last 30 Days: {thirty_days_ago.strftime("%Y-%m-%d")} to {today.strftime("%Y-%m-%d")})')
    plt.xlabel('Category')
    plt.ylabel('Amount')
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Save to BytesIO and send
    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    bot.send_photo(message.chat.id, buf)
    plt.close()
    buf.close()

# Start the bot
if __name__ == "__main__":
    bot.polling(none_stop=True)