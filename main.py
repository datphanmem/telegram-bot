import requests
import time
import re
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import random
import os
import json
from datetime import datetime, timezone
from bs4 import BeautifulSoup

# Lưu trữ email có mã code (key: chat_id, value: [{"email": email, "code": code, "create_at": timestamp}])
emails_with_codes = {}

# Thay YOUR_BOT_TOKEN bằng token từ BotFather
TOKEN = "7515268728:AAELI0s5QUCK-Yj3uIkAmXgIumFYXcmEpL4"

# Cấu hình Temp-Mail API
TEMPMAIL_API_KEY = "tempmail.20250623.yb3yvj0im9am9cwkyxovyd34k2zchy3mtg7cc71htoq67ml6"
TEMPMAIL_API_URL = "https://api.tempmail.lol"

# Domain được phép sử dụng (dựa trên Temp-Mail)
ALLOWED_DOMAIN = "tempmail.lol"

# Lưu trữ email đã tạo (key: chat_id, value: [{"email": email, "token": token}])
email_storage = {}

# File để lưu email_storage
EMAIL_STORAGE_FILE = "email_storage.json"

# Danh sách tiêu đề email chứa mã OTP trong các ngôn ngữ
VERIFICATION_CODE_TITLES = [
    "Verification code",          # Tiếng Anh
    "Bestätigungscode",           # Tiếng Đức
    "Code de vérification",       # Tiếng Pháp
    "Código de verificación",     # Tiếng Tây Ban Nha
    "Codice di verifica",         # Tiếng Ý
    "認証コード",                  # Tiếng Nhật (Ninshō kōdo)
    "인증 코드",                   # Tiếng Hàn (Injeung kodeu)
    "验证码",                     # Tiếng Trung Giản thể (Yànzhèng mǎ)
    "Код подтверждения",          # Tiếng Nga (Kod podtverzhdeniya)
    "Código de verificação",      # Tiếng Bồ Đào Nha
    "رمز التحقق",                # Tiếng Ả Rập (Ramz at-taḥqīq)
    "Verificatiecode",            # Tiếng Hà Lan
    "Verifieringskod",            # Tiếng Thụy Điển
]

# Danh sách tên và họ phổ biến
FIRST_NAMES = [
    "alexander", "amanda", "andrew", "angela", "anna", "anthony", "ashley", "benjamin", "bethany", "brandon",
    "brian", "brittany", "catherine", "charles", "christopher", "daniel", "david", "deborah", "dennis", "diana",
    "donald", "elizabeth", "emily", "eric", "frank", "george", "heather", "jacob", "james", "jennifer",
    "jessica", "john", "jonathan", "joshua", "karen", "katherine", "kevin", "kimberly", "laura", "linda",
    "mark", "mary", "matthew", "melissa", "michael", "nancy", "nicholas", "patricia", "robert", "sarah"
]

LAST_NAMES = [
    "adams", "allen", "anderson", "bailey", "baker", "barnes", "bell", "bennett", "brooks", "brown",
    "bryant", "campbell", "carter", "clark", "coleman", "collins", "cook", "cooper", "cox", "davis",
    "edwards", "evans", "fisher", "flores", "foster", "garcia", "gomez", "gonzalez", "gray", "green",
    "hall", "harris", "hernandez", "hill", "jackson", "james", "johnson", "jones", "king", "lee",
    "lewis", "martin", "martinez", "miller", "mitchell", "moore", "morgan", "parker", "smith", "taylor"
]

# Lưu trữ số lượng email cuối cùng được yêu cầu (key: chat_id, value: quantity)
last_quantity = {}

# Hàm lưu email_storage vào file JSON
def save_email_storage():
    try:
        with open(EMAIL_STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(email_storage, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Lỗi khi lưu email_storage: {str(e)}")

# Hàm tải email_storage từ file JSON
def load_email_storage():
    global email_storage
    try:
        if os.path.exists(EMAIL_STORAGE_FILE):
            with open(EMAIL_STORAGE_FILE, "r", encoding="utf-8") as f:
                email_storage = json.load(f)
                email_storage = {int(k): v for k, v in email_storage.items()}
        else:
            email_storage = {}
    except Exception as e:
        print(f"Lỗi khi tải email_storage: {str(e)}")
        email_storage = {}

# Hàm tạo tài khoản Temp-Mail
def create_temp_mail_account(chat_id, quantity):
    print(f"Đang tạo {quantity} email cho chat_id: {chat_id}")
    try:
        headers = {"Authorization": f"Bearer {TEMPMAIL_API_KEY}"}
        emails = []
        time_start = time.time()
        
        for i in range(quantity):
            while True:
                if time.time() - time_start > 30:
                    break
                first_name = random.choice(FIRST_NAMES)
                last_name = random.choice(LAST_NAMES)
                random_number = random.randint(10, 99)
                email_name = f"{first_name}{last_name}{random_number}"
                
                try:
                    response = requests.post(
                        f"{TEMPMAIL_API_URL}/generate",
                        json={"address": f"{email_name}@{ALLOWED_DOMAIN}"},
                        headers=headers
                    )
                    if response.status_code == 200:
                        data = response.json()
                        emails.append({"email": data["address"], "token": data["token"]})
                        break
                    else:
                        print(f"Không tạo được email {email_name}: {response.text}")
                        continue
                except Exception as e:
                    print(f"Không tạo được email {email_name}: {str(e)}")
                    continue

        email_storage[chat_id] = emails
        save_email_storage()
        if not emails:
            return f"Không tạo được email nào do lỗi Temp-Mail. Vui lòng kiểm tra API key hoặc domain {ALLOWED_DOMAIN}.", []
        result = "\n".join([f"Generated Mail {i+1}\n<code>{e['email']}</code>" for i, e in enumerate(emails)])
        return result, emails
    except Exception as e:
        return f"Lỗi khi tạo email: {str(e)}", []

# Hàm kiểm tra email tồn tại
def check_email_exists(email_address):
    try:
        headers = {"Authorization": f"Bearer {TEMPMAIL_API_KEY}"}
        response = requests.get(f"{TEMPMAIL_API_URL}/inbox/{email_address}", headers=headers)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Không kiểm tra được email {email_address}: {str(e)}")
        return None

# Hàm lấy mã OTP từ email
async def get_code_from_email(chat_id, email_address):
    print(f"Bắt đầu xử lý .gc cho {email_address}")
    
    if not email_address.endswith(f"@{ALLOWED_DOMAIN}"):
        return f"Email: <code>{email_address}</code>\nLỗi: Chỉ hỗ trợ email với domain @{ALLOWED_DOMAIN}."

    token = None
    if chat_id in email_storage and email_storage[chat_id]:
        for email in email_storage[chat_id]:
            if email["email"].lower() == email_address.lower():
                token = email["token"]
                break
    
    if not token:
        email_data = check_email_exists(email_address)
        if email_data and "token" in email_data:
            token = email_data["token"]
            if chat_id not in email_storage:
                email_storage[chat_id] = []
            email_storage[chat_id].append({"email": email_address, "token": token})
            save_email_storage()
        else:
            return f"Email: <code>{email_address}</code>\nKhông tìm thấy email. Vui lòng tạo email mới bằng .gm hoặc kiểm tra email tồn tại trên Temp-Mail."

    headers = {"Authorization": f"Bearer {TEMPMAIL_API_KEY}"}
    max_attempts = 24
    attempt = 0

    while attempt < max_attempts:
        try:
            response = requests.get(
                f"{TEMPMAIL_API_URL}/inbox/{email_address}",
                headers=headers
            )
            if response.status_code == 200:
                emails = response.json().get("emails", [])
                for email in emails:
                    if any(title.lower() in email.get("subject", "").lower() for title in VERIFICATION_CODE_TITLES) and "adobe.com" in email.get("from", "").lower():
                        content = email.get("html") or email.get("text", "")
                        print(f"Nội dung email: Subject: {email.get('subject')}, Text: {content[:500]}...")

                        soup = BeautifulSoup(content, 'html.parser')
                        strong_tags = soup.find_all('strong', style=re.compile(r'font-size:\s*28px'))
                        code = None
                        for tag in strong_tags:
                            text = tag.get_text().strip()
                            if re.match(r'^\d{6}$', text):
                                code = text
                                break
                        
                        if not code:
                            text_content = soup.get_text()
                            match = re.search(r'(Verification code|Bestätigungscode|Code de vérification|Código de verificación|Codice di verifica|認証コード|인증 코드|验证码|Код подтверждения|Código de verificação|رمز التحقق|Verificatiecode|Verifieringskod):.*?(\d{6})', text_content, re.DOTALL | re.IGNORECASE)
                            code = match.group(2) if match else "Không tìm thấy mã trong email"
                        
                        print(f"Mã OTP tìm được: {code}")
                        received_time = datetime.fromisoformat(email.get("date").replace("Z", "+00:00"))
                        current_time = datetime.now(timezone.utc)
                        received_minutes = int((current_time - received_time).total_seconds() / 60)

                        if code != "Không tìm thấy mã trong email":
                            if chat_id not in emails_with_codes:
                                emails_with_codes[chat_id] = []
                            emails_with_codes[chat_id].append({
                                "email": email_address,
                                "code": code,
                                "create_at": received_time
                            })

                        return f"Email: <code>{email_address}</code>\nAdobe Code Is: <code>{code}</code>\nReceived {received_minutes} Minutes Ago"
                
                print(f"Chưa có email chứa mã xác minh từ Adobe, thử lại sau 5 giây (lần {attempt + 1}/{max_attempts})")
                attempt += 1
                await asyncio.sleep(5)
            else:
                return f"Email: <code>{email_address}</code>\nLỗi khi lấy nội dung email: {response.text}"
        except Exception as e:
            print(f"Lỗi khi lấy email: {str(e)}")
            return f"Email: <code>{email_address}</code>\nLỗi khi lấy nội dung email: {str(e)}"

    return f"Email: <code>{email_address}</code>\nChưa có mã xác minh nào được gửi. Vui lòng kiểm tra Temp-Mail thủ công."

# Hàm xử lý lệnh /gm
async def gm_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    await update.message.reply_text("Mail generating...")
    try:
        quantity = int(context.args[0]) if context.args else 1
        if quantity <= 0 or quantity > 10:
            await update.message.reply_text("Số lượng phải từ 1 đến 10.")
            return
        last_quantity[chat_id] = quantity  # Lưu số lượng cho chat_id
        result, emails = create_temp_mail_account(chat_id, quantity)
        keyboard = [
            [InlineKeyboardButton(f"📧 Get code {email['email']}", callback_data=f".gc {email['email']}")]
            for email in emails
        ]
        # Thêm nút "Generate More"
        keyboard.append([InlineKeyboardButton("🔄 Generate More", callback_data=f".gm_more {quantity}")])
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        await update.message.reply_text(result, parse_mode="HTML", reply_markup=reply_markup)
    except ValueError:
        await update.message.reply_text("Vui lòng nhập số lượng hợp lệ. Ví dụ: /gm 2")

# Hàm xử lý lệnh /getcode
async def getcode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    if not context.args:
        await update.message.reply_text(f"Vui lòng cung cấp email. Ví dụ: /getcode example@{ALLOWED_DOMAIN}")
        return
    email = context.args[0]
    if "gc_tasks" not in context.bot_data:
        context.bot_data["gc_tasks"] = []
    context.bot_data["gc_tasks"].append(asyncio.create_task(
        process_gc_task(update, context, chat_id, email)
    ))

# Hàm xử lý tác vụ .gc
async def process_gc_task(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id, email):
    await update.message.reply_text(f"Waiting For Code for {email} ...")
    result = await get_code_from_email(chat_id, email)
    await context.bot.send_message(chat_id=chat_id, text=result, parse_mode="HTML")

# Hàm xử lý callback từ inline buttons
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    callback_data = query.data
    
    if callback_data.startswith(".gc"):
        email = callback_data.split(" ", 1)[1] if len(callback_data.split(" ")) > 1 else ""
        if not email:
            await query.message.reply_text("Lỗi: Không tìm thấy email trong callback.")
            return
        if "gc_tasks" not in context.bot_data:
            context.bot_data["gc_tasks"] = []
        context.bot_data["gc_tasks"].append(asyncio.create_task(
            process_gc_task_callback(query, context, chat_id, email)
        ))
    
    elif callback_data.startswith(".gm_more"):
        try:
            quantity = int(callback_data.split(" ")[1])
            if quantity <= 0 or quantity > 10:
                await query.message.reply_text("Số lượng phải từ 1 đến 10.")
                return
            last_quantity[chat_id] = quantity  # Cập nhật số lượng
            await query.message.reply_text("Mail generating...")
            result, emails = create_temp_mail_account(chat_id, quantity)
            keyboard = [
                [InlineKeyboardButton(f"📧 Get code {email['email']}", callback_data=f".gc {email['email']}")]
                for email in emails
            ]
            # Thêm lại nút "Generate More"
            keyboard.append([InlineKeyboardButton("🔄 Generate More", callback_data=f".gm_more {quantity}")])
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            await query.message.reply_text(result, parse_mode="HTML", reply_markup=reply_markup)
        except ValueError:
            await query.message.reply_text("Lỗi: Số lượng không hợp lệ.")

# Hàm xử lý tác vụ .gc từ callback
async def process_gc_task_callback(query, context, chat_id, email):
    await query.message.reply_text(f"Waiting For Code for {email} ...")
    result = await get_code_from_email(chat_id, email)
    await context.bot.send_message(chat_id=chat_id, text=result, parse_mode="HTML")

# Hàm xử lý lệnh .gm, .gc
async def handle_dot_commands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    message_text = update.message.text.strip()
    print(f"Nhận tin nhắn DOT: {message_text} từ chat_id: {chat_id}")

    if message_text.startswith(".gm"):
        await update.message.reply_text("Mail generating...")
        try:
            args = message_text.split()
            quantity = int(args[1]) if len(args) > 1 else 1
            if quantity <= 0 or quantity > 10:
                await update.message.reply_text("Số lượng phải từ 1 đến 10.")
                return
            last_quantity[chat_id] = quantity  # Lưu số lượng cho chat_id
            result, emails = create_temp_mail_account(chat_id, quantity)
            keyboard = [
                [InlineKeyboardButton(f"📧 Get code {email['email']}", callback_data=f".gc {email['email']}")]
                for email in emails
            ]
            # Thêm nút "Generate More"
            keyboard.append([InlineKeyboardButton("🔄 Generate More", callback_data=f".gm_more {quantity}")])
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            await update.message.reply_text(result, parse_mode="HTML", reply_markup=reply_markup)
        except ValueError:
            await update.message.reply_text("Vui lòng nhập số lượng hợp lệ. Ví dụ: .gm 2")

    elif message_text.startswith(".gc"):
        args = message_text.split()
        if len(args) < 2:
            await update.message.reply_text(f"Vui lòng cung cấp email. Ví dụ: .gc example@{ALLOWED_DOMAIN}")
            return
        email = args[1]
        if "gc_tasks" not in context.bot_data:
            context.bot_data["gc_tasks"] = []
        context.bot_data["gc_tasks"].append(asyncio.create_task(
            process_gc_task(update, context, chat_id, email)
        ))

# Hàm khởi động bot
def main():
    try:
        load_email_storage()
        application = Application.builder().token(TOKEN).connect_timeout(10).read_timeout(10).build()
        application.add_handler(CommandHandler("gm", gm_command))
        application.add_handler(CommandHandler("getcode", getcode_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_dot_commands))
        application.add_handler(CallbackQueryHandler(button_callback))
        print("Bot đang khởi động...")
        application.run_polling()
    except Exception as e:
        print(f"Lỗi khi khởi động bot: {str(e)}")

if __name__ == "__main__":
    main()
