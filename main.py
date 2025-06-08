import mailslurp_client
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
from telegram.error import NetworkError

# Lưu trữ email có mã code (key: chat_id, value: [{"email": email, "code": code, "create_at": timestamp}])
emails_with_codes = {}

# Thay YOUR_BOT_TOKEN bằng token từ BotFather
TOKEN = "7515268728:AAELI0s5QUCK-Yj3uIkAmXgIumFYXcmEpL4"

# Cấu hình MailSlurp
MAILSURP_API_KEY = "c96fb56bceafe20bf655af788941b0c90820f0238ee24212ec23c193f7af9093"
configuration = mailslurp_client.Configuration()
configuration.api_key['x-api-key'] = MAILSURP_API_KEY

# Domain được phép sử dụng
ALLOWED_DOMAIN = "adobeaccounts.space"

# Lưu trữ email đã tạo (key: chat_id, value: [{"email": email, "inbox_id": inbox_id}])
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

# Hàm tạo tài khoản MailSlurp
def create_mailslurp_account(chat_id, quantity):
    print(f"Đang tạo {quantity} email cho chat_id: {chat_id}")
    try:
        with mailslurp_client.ApiClient(configuration) as api_client:
            inbox_controller = mailslurp_client.InboxControllerApi(api_client)
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
                        inbox = inbox_controller.create_inbox(email_address=f"{email_name}@{ALLOWED_DOMAIN}")
                        emails.append({"email": inbox.email_address, "inbox_id": inbox.id})
                        break
                    except Exception as e:
                        print(f"Không tạo được email {email_name}: {str(e)}")
                        continue

        email_storage[chat_id] = emails
        save_email_storage()
        if not emails:
            return f"Không tạo được email nào do lỗi MailSlurp. Vui lòng kiểm tra API key hoặc domain {ALLOWED_DOMAIN}.", []
        result = "\n".join([f"Generated Mail {i+1}\n<code>{e['email']}</code>" for i, e in enumerate(emails)])
        return result, emails
    except Exception as e:
        return f"Lỗi khi tạo email: {str(e)}", []

# Hàm lấy inbox_id từ email address
def get_inbox_id_by_email(email_address):
    try:
        with mailslurp_client.ApiClient(configuration) as api_client:
            inbox_controller = mailslurp_client.InboxControllerApi(api_client)
            inbox_result = inbox_controller.get_inbox_by_email_address(email_address=email_address)
            if inbox_result and hasattr(inbox_result, 'inbox_id'):
                return inbox_result.inbox_id
            return None
    except Exception as e:
        print(f"Không lấy được inbox_id cho {email_address}: {str(e)}")
        return None

# Hàm lấy mã OTP từ email
async def get_code_from_email(chat_id, email_address):
    print(f"Bắt đầu xử lý .gc cho {email_address}")
    
    if not email_address.endswith(f"@{ALLOWED_DOMAIN}"):
        return f"Email: <code>{email_address}</code>\nLỗi: Chỉ hỗ trợ email với domain @{ALLOWED_DOMAIN}."

    inbox_id = None
    if chat_id in email_storage and email_storage[chat_id]:
        for email in email_storage[chat_id]:
            if email["email"].lower() == email_address.lower():
                inbox_id = email["inbox_id"]
                break
    
    if not inbox_id:
        inbox_id = get_inbox_id_by_email(email_address)
        if inbox_id:
            if chat_id not in email_storage:
                email_storage[chat_id] = []
            email_storage[chat_id].append({"email": email_address, "inbox_id": inbox_id})
            save_email_storage()
        else:
            return f"Email: <code>{email_address}</code>\nKhông tìm thấy inbox. Vui lòng tạo email mới bằng .gm hoặc kiểm tra email tồn tại trên MailSlurp."

    with mailslurp_client.ApiClient(configuration) as api_client:
        email_controller = mailslurp_client.EmailControllerApi(api_client)
        max_attempts = 24
        attempt = 0

        while attempt < max_attempts:
            try:
                emails = email_controller.get_emails_paginated(
                    inbox_id=[inbox_id],
                    sort="DESC",
                    size=10
                ).content
                if emails:
                    for email in emails:
                        if email.subject and any(title.lower() in email.subject.lower() for title in VERIFICATION_CODE_TITLES) and email.sender and "adobe.com" in email.sender.email_address.lower():
                            content = email_controller.get_email(email_id=email.id).body
                            print(f"Nội dung email: Subject: {email.subject}, Text: {content[:500]}...")

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
                            received_time = email.created_at
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
            except Exception as e:
                print(f"Lỗi khi lấy email: {str(e)}")
                return f"Email: <code>{email_address}</code>\nLỗi khi lấy nội dung email: {str(e)}"

        return f"Email: <code>{email_address}</code>\nChưa có mã xác minh nào được gửi. Vui lòng kiểm tra MailSlurp thủ công."

# Hàm xử lý lệnh /gm
async def gm_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    await update.message.reply_text("Mail generating...")
    try:
        quantity = int(context.args[0]) if context.args else 1
        if quantity <= 0 or quantity > 10:
            await update.message.reply_text("Số lượng phải từ 1 đến 10.")
            return
        result, emails = create_mailslurp_account(chat_id, quantity)
        keyboard = [
            [InlineKeyboardButton(f"📧 Get code {email['email']}", callback_data=f".gc {email['email']}")]
            for email in emails
        ]
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

# Hàm xử lý lệnh .getmail
async def getmail_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    filename = f"emails_with_codes_{chat_id}.txt"
    
    if chat_id not in emails_with_codes or not emails_with_codes[chat_id]:
        await update.message.reply_text("Không có email hoặc mã OTP nào để xuất.")
        return

    try:
        with open(filename, "w", encoding="utf-8") as f:
            for entry in emails_with_codes[chat_id]:
                email = entry['email']
                code = entry['code']
                create_at = entry['create_at'].isoformat()
                f.write(f"{email},{code},{create_at}\n")

        with open(filename, "rb") as f:
            await context.bot.send_document(
                chat_id=chat_id,
                document=f,
                filename=filename,
                caption="Danh sách email và mã OTP"
            )
        os.remove(filename)
    except Exception as e:
        await update.message.reply_text(f"Lỗi khi xuất file: {str(e)}")

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

# Hàm xử lý tác vụ .gc từ callback
async def process_gc_task_callback(query, context, chat_id, email):
    await query.message.reply_text(f"Waiting For Code for {email} ...")
    result = await get_code_from_email(chat_id, email)
    await context.bot.send_message(chat_id=chat_id, text=result, parse_mode="HTML")

# Hàm xử lý lệnh .gm, .gc, .getmail
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
            result, emails = create_mailslurp_account(chat_id, quantity)
            keyboard = [
                [InlineKeyboardButton(f"📧 Get code {email['email']}", callback_data=f".gc {email['email']}")]
                for email in emails
            ]
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

    elif message_text.startswith(".getmail"):
        await getmail_command(update, context)

# Hàm khởi động bot
def main():
    try:
        load_email_storage()
        application = Application.builder().token(TOKEN).connect_timeout(10).read_timeout(10).build()
        application.add_handler(CommandHandler("gm", gm_command))
        application.add_handler(CommandHandler("getcode", getcode_command))
        application.add_handler(CommandHandler("getmail", getmail_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_dot_commands))
        application.add_handler(CallbackQueryHandler(button_callback))
        print("Bot đang khởi động...")
        application.run_polling()
    except Exception as e:
        print(f"Lỗi khi khởi động bot: {str(e)}")

if __name__ == "__main__":
    main()