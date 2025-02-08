from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
from flask_cors import CORS  # Add CORS support for potential frontend integration
from pdf_processor import PDFProcessor
from database_handler import DatabaseHandler
from email_handler import EmailHandler
from config_handler import ConfigHandler
import os
from dotenv import load_dotenv
import json
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import shutil
import requests
import re
import sqlite3
import logging
from cachetools import TTLCache
from typing import Optional, Dict, Any
import uuid

# Load environment variables
load_dotenv()

# Verify environment variables
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    print("WARNING: OPENAI_API_KEY not found in environment variables")
else:
    print("OpenAI API key loaded successfully")

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')  # Required for flash messages

# Enable CORS
CORS(app, resources={
    r"/*": {
        "origins": "*",  # In production, replace with specific origins
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# API Configuration
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

# Initialize handlers
config_handler = ConfigHandler()
db_handler = DatabaseHandler(db_path="invoice_emails.db")

# Load email configuration
email_config = config_handler.get_config()
email_handler = EmailHandler(
    sender_email=email_config['sender_email'],
    internal_email=email_config['internal_email']
)

# If we have saved credentials, set them in the email handler
if email_config['app_password']:
    email_handler.save_credentials(email_config['app_password'])

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize response cache (5 minutes TTL)
response_cache = TTLCache(maxsize=100, ttl=300)

def validate_api_key(api_key: Optional[str]) -> bool:
    """Validate the OpenAI API key format and length"""
    if not api_key or not isinstance(api_key, str) or len(api_key) < 20:
        return False
    # Check if it starts with expected prefix
    return api_key.startswith(('sk-', 'sk-org-'))

def process_pdf_for_week(week_start: datetime, week_end: datetime) -> list:
    """Process PDFs for a specific week."""
    processed_files = []
    skipped_files = []
    
    logger.info(f"Starting PDF processing for week: {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}")
    logger.info(f"PDF_SAMPLES_FOLDER path: {os.path.abspath(PDF_SAMPLES_FOLDER)}")
    
    # Ensure PDF_SAMPLES_FOLDER exists and log the path
    if not os.path.exists(PDF_SAMPLES_FOLDER):
        logger.error(f"PDF_SAMPLES_FOLDER not found at path: {PDF_SAMPLES_FOLDER}")
        return processed_files
        
    logger.info(f"Found {len(os.listdir(PDF_SAMPLES_FOLDER))} files in PDF_SAMPLES_FOLDER")
    
    # Process each PDF file in the folder
    for filename in os.listdir(PDF_SAMPLES_FOLDER):
        if not filename.endswith('.pdf'):
            continue
            
        file_path = os.path.join(PDF_SAMPLES_FOLDER, filename)
        logger.info(f"Processing file: {filename}")
        
        try:
            # Extract invoice info including dates
            invoice_info = PDFProcessor.extract_invoice_info(file_path)
            if not invoice_info:
                logger.warning(f"Could not extract invoice info from {filename}")
                continue
                
            logger.info(f"Extracted invoice info: {invoice_info}")
                
            # Convert string dates to datetime objects
            try:
                period_start = datetime.strptime(invoice_info.get('period_start'), '%Y-%m-%d')
                period_end = datetime.strptime(invoice_info.get('period_end'), '%Y-%m-%d')
                logger.info(f"File {filename} period: {period_start.strftime('%Y-%m-%d')} to {period_end.strftime('%Y-%m-%d')}")
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid date format in file {filename}: {str(e)}")
                continue
            
            if not period_start or not period_end:
                logger.warning(f"Missing dates in file {filename}")
                continue
                
            # Check if the invoice period overlaps with the requested week
            if (period_start <= week_end and period_end >= week_start):
                logger.info(f"File {filename} matches the requested week")
                
                # Get company name and invoice number
                company_name = invoice_info.get('company_name', filename.split('_')[0].replace('_', ' ').title())
                invoice_number = invoice_info.get('invoice_number')
                
                # Create unique filename
                safe_company_name = secure_filename(company_name)
                period_start_str = period_start.strftime('%Y%m%d')
                period_end_str = period_end.strftime('%Y%m%d')
                unique_filename = f"{safe_company_name}_{invoice_number}_{period_start_str}_{period_end_str}.pdf"
                
                download_path = os.path.join(DOWNLOADS_FOLDER, unique_filename)
                processed_path = os.path.join(PROCESSED_FOLDER, unique_filename)
                
                # Check if file already exists in downloads or processed folder
                if os.path.exists(download_path) or os.path.exists(processed_path):
                    logger.info(f"File already exists for invoice {invoice_number}")
                    skipped_files.append({
                        'invoice_number': invoice_number,
                        'company_name': company_name,
                        'period_start': period_start.strftime('%Y-%m-%d'),
                        'period_end': period_end.strftime('%Y-%m-%d'),
                        'status': 'Processed' if os.path.exists(processed_path) else 'Pending'
                    })
                    continue
                
                # Copy file to downloads folder
                shutil.copy2(file_path, download_path)
                
                logger.info(f"Adding to pending requests: {company_name} - {invoice_number}")
                
                # Add to pending requests
                db_handler.add_pending_request(
                    invoice_number=invoice_number,
                    company_name=company_name,
                    pdf_path=download_path,
                    period_start=period_start.strftime('%Y-%m-%d'),
                    period_end=period_end.strftime('%Y-%m-%d')
                )
                
                processed_files.append({
                    'company_name': company_name,
                    'invoice_number': invoice_number,
                    'period_start': period_start.strftime('%Y-%m-%d'),
                    'period_end': period_end.strftime('%Y-%m-%d')
                })
                logger.info(f"Successfully processed {filename}")
            else:
                logger.info(f"File {filename} does not match the requested week")
                logger.info(f"Comparison results: start_check={period_start <= week_end}, end_check={period_end >= week_start}")
                
        except Exception as e:
            logger.error(f"Error processing file {filename}: {str(e)}")
            continue
            
    logger.info(f"Processed {len(processed_files)} files, Skipped {len(skipped_files)} files")
    
    # Send notification email to internal department if any files were processed
    if processed_files:
        try:
            # Prepare email content
            subject = f"New Pending Invoices Added ({week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')})"
            body = f"The following invoices have been processed and added to the pending table:\n\n"
            for file in processed_files:
                body += f"- Invoice {file['invoice_number']} ({file['period_start']} to {file['period_end']})\n"
            body += f"\nPlease review these invoices at: {request.host_url}pending"
            
            # Send notification email
            email_handler.send_email(
                to_email=email_handler.internal_email,
                subject=subject,
                body=body
            )
            logger.info("Sent notification email to internal department")
        except Exception as e:
            logger.error(f"Failed to send notification email: {str(e)}")
    
    return processed_files, skipped_files

def generate_response(user_input: str) -> str:
    """Generate response using OpenAI GPT-3.5 API with fallback to rule-based"""
    try:
        # Check cache first
        if user_input in response_cache:
            logger.info("Returning cached response")
            return response_cache[user_input]

        # Check for PDF processing requests
        lower_input = user_input.lower()
        if any(word in lower_input for word in ['işle', 'process']):
            return process_pdf_request(lower_input)
        elif 'gönder' in lower_input or 'send' in lower_input:
            return process_email_request(user_input, lower_input)
        else:
            return process_api_request(user_input)
    except Exception as e:
        logger.error(f"Error in generate_response: {str(e)}")
        return generate_response_rule_based(user_input)

def process_pdf_request(lower_input: str) -> str:
    """Process PDF-related requests"""
    try:
        # Extract date from input
        month_map = {
            'ocak': 1, 'şubat': 2, 'mart': 3, 'nisan': 4,
            'mayıs': 5, 'haziran': 6, 'temmuz': 7, 'ağustos': 8,
            'eylül': 9, 'ekim': 10, 'kasım': 11, 'aralık': 12,
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }
        
        words = lower_input.split()
        day = None
        month = None
        
        for i, word in enumerate(words):
            if word.isdigit():
                day = int(word)
            if i + 1 < len(words) and words[i+1] in month_map:
                month = month_map[words[i+1]]
                month_name = words[i+1]
        
        if not (day and month):
            return "Lütfen geçerli bir tarih belirtin (örnek: '6 ocak' veya '15 aralık')"
        
        current_date = datetime.now()
        year = current_date.year
        
        if month == 1 and current_date.month == 12:
            year = current_date.year + 1
        elif month == 12 and current_date.month == 1:
            year = current_date.year - 1
        
        target_date = datetime(year, month, day)
        week_start = target_date - timedelta(days=target_date.weekday())
        week_end = week_start + timedelta(days=6)
        
        processed_files, skipped_files = process_pdf_for_week(week_start, week_end)
        
        response = f"{day} {month_name} haftasına ait PDFleri işledim.\n"
        
        if processed_files:
            response += "\nİşlenen yeni faturalar:\n"
            for file in processed_files:
                response += f"- Fatura No: {file.get('invoice_number', 'N/A')} ({file['period_start']} - {file['period_end']})\n"
        
        if skipped_files:
            response += "\nDaha önce işlenmiş faturalar (atlandı):\n"
            for file in skipped_files:
                status = "İşlenmiş" if file['status'] == 'Processed' else "Beklemede"
                response += f"- Fatura No: {file['invoice_number']} ({file['period_start']} - {file['period_end']}) - {status}\n"
        
        if not processed_files and not skipped_files:
            return f"{day} {month_name} haftası için işlenecek PDF fatura bulamadım. Lütfen PDF_SAMPLES klasörünü kontrol edin."
        
        # Add email request information if there are new processed files
        if processed_files:
            invoices_without_email = []
            for file in processed_files:
                if not db_handler.get_company_email(file['company_name']):
                    invoices_without_email.append(file['invoice_number'])
            
            if invoices_without_email:
                response += "\nAşağıdaki fatura numaraları için e-posta adresleri eksik:\n"
                for invoice_number in invoices_without_email:
                    response += f"- {invoice_number}\n"
                response += "\nLütfen her fatura için e-posta adresini belirtin. Örnek:\n"
                response += f"'{invoices_without_email[0]} numaralı fatura için mail adresi: example@company.com'"
            else:
                response += "\nTüm yeni faturalar için e-posta adresleri mevcut. Faturalar otomatik olarak gönderilecek."
        
        return response
            
    except Exception as e:
        logger.error(f"Error processing PDFs: {e}")
        return "PDF işleme sırasında bir hata oluştu. Lütfen daha sonra tekrar deneyin."

def process_email_request(user_input: str, lower_input: str) -> str:
    """Process email-related requests"""
    try:
        # Check for invoice-specific email assignment
        invoice_match = re.search(r'(\d+)(?:\s+numaral[ıi])?(?:\s+fatura)?(?:\s+için)?\s+(?:mail|email|e-posta)?\s+(?:adres(?:i)?|address)?:?\s*([\w\.-]+@[\w\.-]+\.\w+)', user_input, re.IGNORECASE)
        if invoice_match:
            invoice_number = invoice_match.group(1)
            email_address = invoice_match.group(2)
            
            logger.info(f"Processing email assignment for invoice: {invoice_number}, email: {email_address}")
            
            # Get request info
            request_info = db_handler.get_request_by_invoice(invoice_number)
            if not request_info:
                return f"{invoice_number} numaralı fatura bulunamadı."
            
            company_name = request_info['company_name']
            
            # Save email association
            db_handler.add_company_email(company_name, email_address)
            
            try:
                logger.info(f"Attempting to send email for invoice {invoice_number}")
                
                # Check if PDF file exists
                if not os.path.exists(request_info['pdf_path']):
                    logger.error(f"PDF file not found: {request_info['pdf_path']}")
                    return f"{invoice_number} numaralı faturanın PDF dosyası bulunamadı."
                    
                success = email_handler.send_email(
                    to_email=email_address,
                    subject=f"Invoice {invoice_number} for {company_name}",
                    body=f"Please find attached the invoice {invoice_number} for the period {request_info['period_start']} to {request_info['period_end']}.",
                    attachment_path=request_info['pdf_path']
                )
                
                if success:
                    logger.info(f"Email sent successfully for invoice {invoice_number}")
                    # Move file to processed folder
                    processed_path = os.path.join(PROCESSED_FOLDER, os.path.basename(request_info['pdf_path']))
                    shutil.move(request_info['pdf_path'], processed_path)
                    # Mark as sent in database
                    db_handler.mark_as_sent(invoice_number, email_address)
                    return f"{invoice_number} numaralı fatura {email_address} adresine gönderildi ve işlendi."
                else:
                    logger.error(f"Failed to send email for invoice {invoice_number}")
                    return f"{invoice_number} numaralı fatura için e-posta gönderilemedi. Lütfen e-posta ayarlarını kontrol edin."
                    
            except Exception as e:
                logger.error(f"Error sending email for invoice {invoice_number}: {str(e)}")
                return f"{invoice_number} numaralı fatura gönderilirken hata oluştu: {str(e)}"
            
        # Handle general email requests (existing logic)
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', user_input)
        if not email_match:
            return "Lütfen geçerli bir e-posta adresi belirtin."
            
        email_address = email_match.group()
        pending = db_handler.get_pending_requests()
        
        if not pending:
            return "Gönderilecek işlenmiş fatura bulamadım. Lütfen önce faturaları işleyin."
        
        sent_count = 0
        for request in pending:
            try:
                success = email_handler.send_email(
                    to_email=email_address,
                    subject=f"Invoice {request['invoice_number']} for {request['company_name']}",
                    body=f"Please find attached the invoice {request['invoice_number']} for the period {request['period_start']} to {request['period_end']}.",
                    attachment_path=request['pdf_path']
                )
                
                if success:
                    processed_path = os.path.join(PROCESSED_FOLDER, os.path.basename(request['pdf_path']))
                    shutil.move(request['pdf_path'], processed_path)
                    db_handler.mark_as_sent(request['invoice_number'], email_address)
                    sent_count += 1
                    
            except Exception as e:
                logger.error(f"Error sending email for invoice {request['invoice_number']}: {str(e)}")
                continue
        
        if sent_count > 0:
            return f"{sent_count} adet faturayı {email_address} adresine gönderdim."
        else:
            return "Fatura gönderimi sırasında bir hata oluştu. Lütfen daha sonra tekrar deneyin."
            
    except Exception as e:
        logger.error(f"Error in email sending: {str(e)}")
        return "E-posta gönderimi sırasında bir hata oluştu. Lütfen daha sonra tekrar deneyin."

def process_api_request(user_input: str) -> str:
    """Process API requests"""
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        if not validate_api_key(api_key):
            logger.warning("Invalid or missing OpenAI API key")
            return generate_response_rule_based(user_input)
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "OpenAI-Beta": "assistants=v1"
        }
        
        system_content = """You are BeoxBot, an AI assistant for a PDF invoice automation system. The system has the following features:

1. PDF Invoice Processing:
   - Process invoices for specific weeks (e.g., "2 aralık haftası", "bu hafta", "geçen hafta")
   - Extract invoice information including amounts, dates, and company details
   - Store processed invoices in the downloads or processed folders

2. Email Management:
   - Send processed invoices to company email addresses
   - Store company email associations for future use
   - Send notifications for missing email addresses

3. Invoice Queries:
   - Look up invoice details by number (e.g., "44075 numaralı şirketin borcu")
   - Show company invoice history and total amounts
   - Display invoice periods and due dates

4. Database Operations:
   - Track pending requests
   - Store company information
   - Maintain email history

When users ask about processing a specific week's invoices, you should understand they want to use the manual processing feature. For queries about company debts or invoice amounts, you should look up the invoice details in the database.

Please respond in the same language as the user's query (Turkish or English)."""
        
        data = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_input}
            ],
            "temperature": 0.7,
            "max_tokens": 500,
            "response_format": {"type": "text"}
        }
        
        response = requests.post(OPENAI_API_URL, headers=headers, json=data, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"API Error Response: {response.text}")
            return generate_response_rule_based(user_input)
            
        result = response.json()
        
        if (isinstance(result, dict) and 
            "choices" in result and 
            isinstance(result["choices"], list) and 
            len(result["choices"]) > 0 and 
            isinstance(result["choices"][0], dict)):
            
            response_text = result["choices"][0].get("message", {}).get("content")
            if response_text:
                response_cache[user_input] = response_text
                return response_text
        
        logger.error(f"Unexpected API response format: {result}")
        return generate_response_rule_based(user_input)
            
    except requests.exceptions.RequestException as e:
        logger.error(f"API request error: {str(e)}")
        return generate_response_rule_based(user_input)

def generate_response_rule_based(user_input: str) -> str:
    """Enhanced rule-based response generator with better context handling"""
    try:
        lower_input = user_input.lower()
        
        # Check if it's a Turkish query
        is_turkish = any(char in lower_input for char in 'çğıöşü') or any(word in lower_input for word in ['hafta', 'fatura', 'borç'])
        
        # Handle API-related errors
        if any(word in lower_input for word in ['api', 'openai', 'gpt']):
            return "API bağlantısında bir sorun var. Lütfen daha sonra tekrar deneyin." if is_turkish else \
                   "There's an issue with the API connection. Please try again later."
        
        # Handle invoice processing requests
        if any(word in lower_input for word in ['hafta', 'week', 'process', 'işle']):
            if not os.path.exists(PDF_SAMPLES_FOLDER):
                return "PDF klasörü bulunamadı. Lütfen sistem yöneticinize başvurun." if is_turkish else \
                       "PDF folder not found. Please contact your system administrator."
            
            pdf_files = [f for f in os.listdir(PDF_SAMPLES_FOLDER) if f.endswith('.pdf')]
            if not pdf_files:
                return "İşlenecek PDF dosyası bulunamadı. Lütfen önce PDF_SAMPLES klasörüne dosyaları yükleyin." if is_turkish else \
                       "No PDF files found for processing. Please upload files to the PDF_SAMPLES folder first."
        
        # Handle email-related requests
        if any(word in lower_input for word in ['mail', 'email', 'e-posta', 'eposta']):
            if not email_handler.sender_email or not email_handler._password:
                return "E-posta ayarları yapılandırılmamış. Lütfen ayarları kontrol edin." if is_turkish else \
                       "Email settings are not configured. Please check the settings."
        
        # Handle invoice queries
        if any(word in lower_input for word in ['borç', 'debt', 'tutar', 'amount']):
            invoice_match = re.search(r'\d+', lower_input)
            if invoice_match:
                invoice_number = invoice_match.group()
                return f"{invoice_number} numaralı fatura için şu anda bilgi alınamıyor. Lütfen daha sonra tekrar deneyin." if is_turkish else \
                       f"Unable to retrieve information for invoice #{invoice_number} at the moment. Please try again later."
        
        # Default responses
        return "Şu anda istediğiniz işlemi gerçekleştiremiyorum. Lütfen daha sonra tekrar deneyin." if is_turkish else \
               "I'm unable to process your request at the moment. Please try again later."
                
    except Exception as e:
        logger.error(f"Rule-based processing error: {str(e)}")
        return "Bir hata oluştu. Lütfen daha sonra tekrar deneyin." if is_turkish else \
               "An error occurred. Please try again later."

# Configuration
PDF_SAMPLES_FOLDER = os.path.abspath('pdf_samples')
DOWNLOADS_FOLDER = os.path.abspath('downloads')
PROCESSED_FOLDER = os.path.abspath('processed')

# Create necessary directories
os.makedirs(PDF_SAMPLES_FOLDER, exist_ok=True)
os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# Print database status
print("Database initialized successfully")
print(f"Using database at: {db_handler.db_path}")

@app.route('/')
def index():
    # Get chat history and recent requests
    chat_history = db_handler.get_chat_history()
    recent_requests = db_handler.get_recent_requests(limit=5)
    return render_template('index.html', 
                         chat_history=chat_history,
                         recent_requests=recent_requests)

@app.route('/manual-process', methods=['GET', 'POST'])
def manual_process():
    if request.method == 'POST':
        selected_week = request.form.get('selected_week')
        
        if not selected_week:
            return jsonify({'success': False, 'error': 'No week selected'})
        
        try:
            # Parse week range
            week_start, week_end = selected_week.split(',')
            week_start_date = datetime.strptime(week_start, '%Y-%m-%d')
            week_end_date = datetime.strptime(week_end, '%Y-%m-%d')
            
            processed_files = []
            skipped_files = []
            auto_emailed_files = []
            
            # Process all PDFs in the samples folder
            for pdf_name in os.listdir(PDF_SAMPLES_FOLDER):
                pdf_path = os.path.join(PDF_SAMPLES_FOLDER, pdf_name)
                if not os.path.exists(pdf_path):
                    continue

                # Extract information from PDF
                pdf_info = PDFProcessor.extract_invoice_info(pdf_path)
                
                if not pdf_info:
                    continue

                # Convert dates for comparison
                pdf_start = datetime.strptime(pdf_info['period_start'], '%Y-%m-%d')
                pdf_end = datetime.strptime(pdf_info['period_end'], '%Y-%m-%d')
                
                # Check if PDF's date range overlaps with selected week
                if not ((pdf_start <= week_end_date and pdf_end >= week_start_date) or
                        (week_start_date <= pdf_end and week_end_date >= pdf_start)):
                    continue

                # Get company name from filename if not in PDF
                company_name = pdf_info.get('company_name')
                if not company_name:
                    company_name = pdf_name.split('_')[0].replace('_', ' ').title()

                invoice_number = pdf_info['invoice_number']
                # Create a unique filename using invoice number, company name, and period dates
                safe_company_name = secure_filename(company_name)
                period_start_str = pdf_info['period_start'].replace('-', '')
                period_end_str = pdf_info['period_end'].replace('-', '')
                unique_filename = f"{safe_company_name}_{invoice_number}_{period_start_str}_{period_end_str}.pdf"
                
                download_path = os.path.join(DOWNLOADS_FOLDER, unique_filename)
                processed_path = os.path.join(PROCESSED_FOLDER, unique_filename)

                # Skip if file already exists in downloads or processed folder
                if os.path.exists(download_path) or os.path.exists(processed_path):
                    skipped_files.append({
                        'filename': pdf_name,
                        'reason': 'File already exists in downloads or processed folder'
                    })
                    continue

                # Copy file to downloads folder
                shutil.copy2(pdf_path, download_path)

                # Check if we have a matching email for auto-sending
                company_email = db_handler.get_company_email(company_name)
                
                if company_email:
                    try:
                        # Send email automatically
                        email_handler.send_email(
                            to_email=company_email,
                            subject=f'Invoice {invoice_number} for {company_name}',
                            body=f'Please find attached the invoice {invoice_number} for the period {pdf_info["period_start"]} to {pdf_info["period_end"]}.',
                            attachment_path=download_path
                        )
                        
                        # Move to processed folder after successful email
                        shutil.move(download_path, processed_path)
                        
                        auto_emailed_files.append({
                            'filename': pdf_name,
                            'invoice_number': invoice_number,
                            'company_name': company_name,
                            'email': company_email
                        })
                    except Exception as e:
                        print(f"Error sending email for {pdf_name}: {str(e)}")
                        # Keep in downloads folder if email fails
                        processed_files.append({
                            'filename': pdf_name,
                            'invoice_number': invoice_number,
                            'company_name': company_name
                        })
                else:
                    # Add to pending requests if no matching email
                    db_handler.add_pending_request(
                        invoice_number=invoice_number,
                        company_name=company_name,
                        pdf_path=download_path,
                        period_start=pdf_info['period_start'],
                        period_end=pdf_info['period_end']
                    )
                    
                    # Send notification email to internal staff
                    try:
                        # Send the notification email directly
                        email_handler.send_email(
                            to_email=email_handler.internal_email,
                            subject=f'Missing Email Address for Invoice {invoice_number}',
                            body=f'{invoice_number} numaralı şirketin mail adresi bulunamadı.\n\n'
                                 f'Bekleyen işlemleri görüntülemek için tıklayın: {request.host_url}pending'
                        )
                        print(f"Notification email sent successfully to {email_handler.internal_email}")
                    except Exception as e:
                        print(f"Error sending notification email: {str(e)}")
                        raise Exception(f"Failed to send notification email: {str(e)}")
                    
                    processed_files.append({
                        'filename': pdf_name,
                        'invoice_number': invoice_number,
                        'company_name': company_name
                    })
            
            # Prepare response message
            message_parts = []
            if processed_files:
                message_parts.append(f"Processed {len(processed_files)} PDFs")
            if auto_emailed_files:
                message_parts.append(f"Automatically emailed {len(auto_emailed_files)} PDFs")
            if skipped_files:
                message_parts.append(f"Skipped {len(skipped_files)} existing PDFs")
            
            message = ". ".join(message_parts) + "."
            
            return jsonify({
                'success': True,
                'message': message,
                'processed_files': processed_files,
                'auto_emailed_files': auto_emailed_files,
                'skipped_files': skipped_files
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    # Get list of PDFs from the samples folder
    pdfs = []
    for pdf in os.listdir(PDF_SAMPLES_FOLDER):
        try:
            pdf_path = os.path.join(PDF_SAMPLES_FOLDER, pdf)
            pdf_info = PDFProcessor.extract_invoice_info(pdf_path)
            if pdf_info:
                # Get company name from filename if not in PDF
                company_name = pdf_info.get('company_name')
                if not company_name:
                    # Extract company name from filename (before first underscore)
                    company_name = pdf.split('_')[0].replace('_', ' ').title()
                
                pdfs.append({
                    'filename': pdf,
                    'invoice_number': pdf_info['invoice_number'],
                    'company_name': company_name,
                    'period_start': pdf_info['period_start'],
                    'period_end': pdf_info['period_end']
                })
        except Exception as e:
            print(f"Error processing {pdf}: {str(e)}")
            # Try to extract dates from filename as fallback
            try:
                parts = pdf.replace('.pdf', '').split('_')
                if len(parts) >= 2:
                    date_range = parts[1]
                    period_start, period_end = date_range.split('-')
                    pdfs.append({
                        'filename': pdf,
                        'invoice_number': 'N/A',
                        'company_name': parts[0].replace('_', ' ').title(),
                        'period_start': datetime.strptime(period_start, '%Y%m%d').strftime('%Y-%m-%d'),
                        'period_end': datetime.strptime(period_end, '%Y%m%d').strftime('%Y-%m-%d')
                    })
            except Exception as e2:
                print(f"Could not extract dates from filename {pdf}: {str(e2)}")
            continue
            
    return render_template('manual_process.html', pdfs=pdfs)

@app.route('/pending')
def pending_requests():
    # Get requests directly from database instead of scanning PDF folder
    requests = db_handler.get_pending_requests()
    return render_template('pending.html', requests=requests)

@app.route('/download/<invoice_number>')
def download_pdf(invoice_number):
    try:
        # Get request info from database
        request_info = db_handler.get_request_by_invoice(invoice_number)
        if not request_info:
            flash('Invoice not found', 'error')
            return redirect(url_for('pending_requests'))
        
        pdf_path = request_info['pdf_path']
        if not os.path.exists(pdf_path):
            flash('PDF file not found', 'error')
            return redirect(url_for('pending_requests'))
        
        # Use the original filename for download
        original_filename = os.path.basename(pdf_path)
        
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=original_filename
        )
            
    except Exception as e:
        flash(f'Error downloading PDF: {str(e)}', 'error')
        return redirect(url_for('pending_requests'))

@app.route('/send-email', methods=['POST'])
def send_email():
    email_address = request.form.get('email_address')
    invoice_number = request.form.get('invoice_number')
    
    if not email_address or not invoice_number:
        flash('Missing required information', 'error')
        return redirect(url_for('pending_requests'))
    
    try:
        # Get request info from database
        request_info = db_handler.get_request_by_invoice(invoice_number)
        if not request_info:
            flash('Invoice not found', 'error')
            return redirect(url_for('pending_requests'))
        
        pdf_path = request_info['pdf_path']
        if not os.path.exists(pdf_path):
            flash('PDF file not found', 'error')
            return redirect(url_for('pending_requests'))
        
        company_name = request_info['company_name']
        
        # Prepare email content
        subject = f'Invoice {invoice_number} for {company_name}'
        body = f'Please find attached the invoice {invoice_number} for the period {request_info["period_start"]} to {request_info["period_end"]}.'
        
        # Send email with PDF attachment
        success = email_handler.send_email(
            to_email=email_address,
            subject=subject,
            body=body,
            attachments=[pdf_path]
        )
        
        if success:
            try:
                # Move file to processed folder
                processed_path = os.path.join(PROCESSED_FOLDER, os.path.basename(pdf_path))
                shutil.move(pdf_path, processed_path)
                
                # Store the email association and mark as sent
                db_handler.add_company_email(company_name, email_address)
                db_handler.mark_as_sent(invoice_number, email_address)
                
                flash(f'Email sent successfully and saved {email_address} for future use with {company_name}', 'success')
            except Exception as e:
                print(f"Error in post-send processing: {str(e)}")
                flash('Email sent but there was an error updating some information', 'warning')
            return redirect(url_for('pending_requests'))
        else:
            flash('Failed to send email. Please check email settings and try again.', 'error')
            return redirect(url_for('pending_requests'))
        
    except Exception as e:
        print(f"Error in send_email: {str(e)}")
        flash(f'Error sending email: {str(e)}', 'error')
        return redirect(url_for('pending_requests'))

@app.route('/chat/<int:chat_id>')
def get_chat(chat_id):
    """Get messages for a specific chat session"""
    messages = db_handler.get_chat_messages(chat_id)
    return jsonify({'messages': messages})

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        message = data.get('message')
        chat_id = data.get('chat_id')
        
        if not message:
            return jsonify({'error': 'No message provided'}), 400

        # Create new chat session if needed
        if not chat_id:
            session_id = str(uuid.uuid4())
            chat_id = db_handler.create_chat_session(session_id)
            if not chat_id:
                return jsonify({'error': 'Failed to create chat session'}), 500

        # Store user message
        db_handler.add_chat_message(chat_id, 'user', message)

        # Generate response using the existing generate_response function
        response = generate_response(message)
        
        # Store bot response
        db_handler.add_chat_message(chat_id, 'bot', response)
        
        # Try to generate a topic for new chats
        if not db_handler.get_chat_topic(chat_id):
            topic = generate_topic(message, response)
            db_handler.update_chat_topic(chat_id, topic)
        
        return jsonify({
            'response': response,
            'chat_id': chat_id
        })
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({
            'error': 'An error occurred while processing your message'
        }), 500

def generate_topic(user_message: str, bot_response: str) -> str:
    """Generate a topic for the chat based on the first message exchange"""
    try:
        # Use a simplified version of the first user message
        topic = user_message[:50]  # Take first 50 characters
        if len(user_message) > 50:
            topic += '...'
        return topic
    except Exception as e:
        logger.error(f"Error generating topic: {e}")
        return 'New Chat'

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        # Handle settings form submission
        sender_email = request.form.get('sender_email')
        app_password = request.form.get('app_password')
        internal_email = request.form.get('internal_email')
        
        if not all([sender_email, app_password, internal_email]):
            flash('All fields are required', 'error')
            return redirect(url_for('settings'))
        
        try:
            # Update email handler
            email_handler.sender_email = sender_email
            email_handler.internal_email = internal_email
            
            # Test authentication with new credentials
            if email_handler.save_credentials(app_password):
                if email_handler.authenticate():
                    # Save configuration only if authentication succeeds
                    config_handler.save_config(
                        sender_email=sender_email,
                        app_password=app_password,
                        internal_email=internal_email
                    )
                    flash('Email settings saved and authenticated successfully', 'success')
                else:
                    flash('Authentication failed with provided credentials', 'error')
            else:
                flash('Failed to save credentials', 'error')
                
        except Exception as e:
            flash(f'Error saving settings: {str(e)}', 'error')
        
        return redirect(url_for('settings'))
    
    # Get current configuration
    email_config = config_handler.get_config()
    
    # Get all companies with their current emails
    companies = db_handler.get_all_companies()
        
    return render_template('settings.html',
        sender_email=email_config['sender_email'],
        app_password=email_config['app_password'],
        internal_email=email_config['internal_email'],
        companies=companies
    )

@app.route('/reset-environment', methods=['POST'])
def reset_environment():
    try:
        # Clear downloads folder
        for file in os.listdir(DOWNLOADS_FOLDER):
            file_path = os.path.join(DOWNLOADS_FOLDER, file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")

        # Clear processed folder
        for file in os.listdir(PROCESSED_FOLDER):
            file_path = os.path.join(PROCESSED_FOLDER, file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")

        # Reset database
        db_handler.clear_all_tables()

        flash('Environment reset successfully', 'success')
    except Exception as e:
        flash(f'Error resetting environment: {str(e)}', 'error')

    return redirect(url_for('settings'))

@app.route('/update-company-email', methods=['POST'])
def update_company_email():
    company_name = request.form.get('company_name')
    new_email = request.form.get('new_email')
    old_email = request.form.get('old_email')  # Optional
    
    if not company_name or not new_email:
        flash('Company name and new email are required', 'error')
        return redirect(url_for('settings'))
    
    try:
        success = db_handler.update_company_email(company_name, new_email, old_email)
        if success:
            flash(f'Email for {company_name} updated to {new_email}', 'success')
        else:
            flash('Failed to update email', 'error')
    except Exception as e:
        flash(f'Error updating email: {str(e)}', 'error')
    
    return redirect(url_for('settings'))

@app.route('/company-email-history/<company_name>')
def company_email_history(company_name):
    try:
        history = db_handler.get_company_email_history(company_name)
        return render_template('email_history.html', company_name=company_name, history=history)
    except Exception as e:
        flash(f'Error getting email history: {str(e)}', 'error')
        return redirect(url_for('settings'))

@app.route('/delete-chat/<int:chat_id>', methods=['POST'])
def delete_chat(chat_id):
    """Delete a chat session and its messages"""
    try:
        if db_handler.delete_chat(chat_id):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete chat'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.template_filter('datetime')
def format_datetime(value):
    """Format a datetime object or string for display"""
    if isinstance(value, str):
        try:
            value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return value
    
    if isinstance(value, datetime):
        now = datetime.now()
        diff = now - value
        
        if diff.days == 0:
            if diff.seconds < 60:
                return 'Just now'
            if diff.seconds < 3600:
                minutes = diff.seconds // 60
                return f'{minutes}m ago'
            hours = diff.seconds // 3600
            return f'{hours}h ago'
        elif diff.days == 1:
            return 'Yesterday'
        elif diff.days < 7:
            return f'{diff.days} days ago'
        else:
            return value.strftime('%Y-%m-%d %H:%M')
    
    return value

if __name__ == '__main__':
    app.run(debug=True, port=5000) 