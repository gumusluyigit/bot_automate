from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
from flask_cors import CORS  # Add CORS support for potential frontend integration
from flask_wtf.csrf import CSRFProtect
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
from logging.handlers import RotatingFileHandler
from cachetools import TTLCache
from typing import Optional, Dict, Any, List, Union
import uuid

# Create logger instance
logger = logging.getLogger(__name__)

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

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Configure CSRF to check for X-CSRF-Token header
@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = request.headers.get('X-CSRF-Token')
        if token:
            request.form = request.form.copy()
            request.form['csrf_token'] = token

# Configure logging with rotation
log_file = 'automation.log'
handler = RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=5)  # 1MB per file, keep 5 backup files
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

# Enable CORS
CORS(app, resources={
    r"/*": {
        "origins": "*",  # In production, replace with specific origins
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-CSRF-Token"],
        "supports_credentials": True
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

        # Process the request using OpenAI API
        return process_api_request(user_input)
    except Exception as e:
        logger.error(f"Error in generate_response: {str(e)}")
        return f"Sorry, there was an error processing your request: {str(e)}"

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
        
        # Log the input and directory contents
        logger.info(f"Processing PDF request with input: {lower_input}")
        logger.info(f"PDF_SAMPLES_FOLDER path: {PDF_SAMPLES_FOLDER}")
        logger.info(f"Directory exists: {os.path.exists(PDF_SAMPLES_FOLDER)}")
        logger.info(f"Directory contents: {os.listdir(PDF_SAMPLES_FOLDER)}")
        
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
        
        logger.info(f"Extracted date: day={day}, month={month}")
        
        current_date = datetime.now()
        year = current_date.year
        
        # Adjust year for December/January crossover
        if month == 12 and current_date.month < 6:  # If requesting December and current month is in first half of year
            year = current_date.year - 1
        elif month == 1 and current_date.month > 6:  # If requesting January and current month is in second half of year
            year = current_date.year + 1
        
        target_date = datetime(year, month, day)
        week_start = target_date - timedelta(days=target_date.weekday())
        week_end = week_start + timedelta(days=6)
        
        logger.info(f"Processing week: {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}")
        
        processed_files, skipped_files = process_pdf_for_week(week_start, week_end)
        
        if not processed_files and not skipped_files:
            pdf_files = [f for f in os.listdir(PDF_SAMPLES_FOLDER) if f.endswith('.pdf')]
            logger.info(f"No files processed. Available PDF files: {pdf_files}")
            
            # Try to parse dates from filenames for debugging
            for pdf_file in pdf_files:
                try:
                    date_match = re.search(r'_(\d{8})-(\d{8})\.pdf$', pdf_file)
                    if date_match:
                        file_start = datetime.strptime(date_match.group(1), '%Y%m%d')
                        file_end = datetime.strptime(date_match.group(2), '%Y%m%d')
                        logger.info(f"File {pdf_file} period: {file_start.strftime('%Y-%m-%d')} to {file_end.strftime('%Y-%m-%d')}")
                        logger.info(f"Comparison with week: {file_start <= week_end} and {file_end >= week_start}")
                except Exception as e:
                    logger.error(f"Error parsing dates from filename {pdf_file}: {str(e)}")
            
        response = f"{day} {month_name} haftasına ait PDFleri işledim."
        
        if processed_files:
            response += "\n\nİşlenen yeni faturalar:\n"
            for file in processed_files:
                response += f"- Fatura No: {file.get('invoice_number', 'N/A')} ({file['period_start']} - {file['period_end']})"
        
        if skipped_files:
            response += "\nDaha önce işlenmiş faturalar (atlandı):\n"
            for file in skipped_files:
                status = "İşlenmiş" if file['status'] == 'Processed' else "Beklemede"
                response += f"- Fatura No: {file['invoice_number']} ({file['period_start']} - {file['period_end']}) - {status}"
        
        if not processed_files and not skipped_files:
            return f"{day} {month_name} haftası için işlenecek PDF fatura bulamadım. PDF_SAMPLES klasöründe {len(pdf_files)} adet PDF dosyası var."
        
        return response
            
    except Exception as e:
        logger.error(f"Error processing PDFs: {e}")
        return f"PDF işleme sırasında bir hata oluştu: {str(e)}"

def process_email_request(user_input: str, lower_input: str) -> str:
    """Process email-related requests"""
    try:
        # First check if email configuration is set up
        if not email_handler.sender_email or not email_handler._password:
            return "E-posta ayarları yapılandırılmamış. Lütfen önce ayarları kontrol edin."

        # Check for invoice-specific email assignment patterns
        patterns = [
            # Pattern 1: "x numaralı faturayı y@test.com adresine gönder"
            r'(\d+)\s+(?:numaral[ıi])?\s*(?:fatura(?:y[ıi])?)?(?:\s+için)?\s*(?:mail|email|e-posta)?\s*(?:adres(?:i)?|address)?:?\s*([\w\.-]+@[\w\.-]+\.\w+)(?:\s+(?:adres(?:i)?|address)?)?(?:\s+(?:gönder|yolla|at))?',
            # Pattern 2: "x numaralı faturayı y@test.com a gönder"
            r'(\d+)\s+(?:numaral[ıi])?\s*(?:fatura(?:y[ıi])?)?(?:\s+için)?\s*([\w\.-]+@[\w\.-]+\.\w+)(?:\s+(?:adres(?:i)?ne|a|e))?\s+(?:gönder|yolla|at)',
            # Pattern 3: "x isimli şirketin faturasını z@test.com a yolla"
            r'([A-Za-zçğıöşüÇĞİÖŞÜ\s]+)(?:\s+(?:isimli|adl[ıi]|ad[ıi]ndaki))?\s+(?:şirket(?:in)?|firma(?:n[ıi]n)?)?\s+fatura(?:s[ıi]n[ıi])?(?:\s+için)?\s+([\w\.-]+@[\w\.-]+\.\w+)',
            # Pattern 4: "send invoice x to y@test.com"
            r'(?:send|forward)\s+(?:invoice)?\s*(?:number)?\s*(?:#)?\s*(\d+)\s+(?:to|for)?\s*([\w\.-]+@[\w\.-]+\.\w+)',
            # Pattern 5: "send company x's invoice to y@test.com"
            r'(?:send|forward)\s+(?:the)?\s*([A-Za-z\s]+)(?:\'s)?\s+invoice\s+(?:to|for)?\s*([\w\.-]+@[\w\.-]+\.\w+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                identifier, email_address = match.groups()
                logger.info(f"Matched pattern with identifier: {identifier} and email: {email_address}")
                
                # Check if identifier is a number (invoice number) or text (company name)
                if identifier.isdigit():
                    request_info = db_handler.get_request_by_invoice(identifier)
                    logger.info(f"Looking up invoice number: {identifier}")
                else:
                    # Clean up company name and try to find matching request
                    company_name = identifier.strip()
                    request_info = db_handler.get_request_by_company(company_name)
                    logger.info(f"Looking up company name: {company_name}")
                
                if not request_info:
                    logger.error(f"No request found for identifier: {identifier}")
                    return f"{'Fatura' if 'türkçe' in lower_input else 'Invoice'} bulunamadı."
                
                company_name = request_info['company_name']
                invoice_number = request_info['invoice_number']
                
                # Check if PDF file exists
                if not os.path.exists(request_info['pdf_path']):
                    logger.error(f"PDF file not found: {request_info['pdf_path']}")
                    return f"PDF dosyası bulunamadı: {invoice_number}"
                
                try:
                    logger.info(f"Attempting to send email for invoice {invoice_number} to {email_address}")
                    # Send email
                    success = email_handler.send_email(
                        to_email=email_address,
                        subject=f"Invoice {invoice_number} for {company_name}",
                        body=f"Please find attached the invoice {invoice_number} for the period {request_info['period_start']} to {request_info['period_end']}.",
                        attachments=[request_info['pdf_path']]
                    )
                    
                    if success:
                        logger.info(f"Email sent successfully for invoice {invoice_number}")
                        # Move file to processed folder
                        processed_path = os.path.join(PROCESSED_FOLDER, os.path.basename(request_info['pdf_path']))
                        shutil.move(request_info['pdf_path'], processed_path)
                        
                        # Save email association and mark as sent
                        db_handler.add_company_email(company_name, email_address)
                        db_handler.mark_as_sent(invoice_number, email_address)
                        
                        return f"{invoice_number} numaralı fatura {email_address} adresine gönderildi ve {company_name} için kayıt edildi."
                    else:
                        logger.error(f"Failed to send email for invoice {invoice_number}")
                        return f"E-posta gönderimi başarısız oldu. Lütfen e-posta ayarlarını kontrol edin."
                        
                except Exception as e:
                    logger.error(f"Error sending email: {str(e)}")
                    return f"E-posta gönderilirken hata oluştu: {str(e)}"
                
        # If no specific patterns match, handle as a general email request
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
                    attachments=[request['pdf_path']]
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
        # First check if it's an email sending request
        lower_input = user_input.lower()
        if any(word in lower_input for word in ['mail', 'email', 'e-posta', 'gönder', 'yolla', 'send']):
            email_response = process_email_request(user_input, lower_input)
            return email_response

        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OpenAI API key not found in environment variables")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
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

Please respond in the same language as the user's query (Turkish or English).
For PDF processing requests, call the appropriate function to process the PDFs."""
        
        data = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_input}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        # Log the request details
        logger.info(f"Making API request to OpenAI")
        logger.info(f"Headers: {headers}")
        logger.info(f"Data: {json.dumps(data)}")
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=10
        )
        
        # Log the response details
        logger.info(f"API Response Status Code: {response.status_code}")
        logger.info(f"API Response Headers: {response.headers}")
        
        try:
            response_json = response.json()
            logger.info(f"API Response Body: {json.dumps(response_json)}")
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON response. Raw response: {response.text}")
            raise Exception("Invalid JSON response from API")
        
        if response.status_code != 200:
            error_message = response_json.get('error', {}).get('message', response.text)
            logger.error(f"API Error: {error_message}")
            raise Exception(f"API Error: {error_message}")
            
        if "choices" in response_json and len(response_json["choices"]) > 0:
            response_text = response_json["choices"][0]["message"]["content"]
            
            # If it's a PDF processing request, execute it
            if any(word in lower_input for word in ['işle', 'process', 'hafta']):
                pdf_response = process_pdf_request(lower_input)
                # Only return the PDF processing response, not the GPT response
                return pdf_response
            
            # Cache the response
            response_cache[user_input] = response_text
            return response_text
        
        raise Exception("Unexpected API response format")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {str(e)}")
        raise Exception(f"Failed to connect to OpenAI API: {str(e)}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        raise Exception("Invalid response format from API")
    except Exception as e:
        logger.error(f"API request error: {str(e)}")
        raise

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

# Log directory paths
print(f"PDF_SAMPLES_FOLDER: {PDF_SAMPLES_FOLDER}")
print(f"DOWNLOADS_FOLDER: {DOWNLOADS_FOLDER}")
print(f"PROCESSED_FOLDER: {PROCESSED_FOLDER}")

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
        try:
            # Check CSRF token
            csrf_token = request.headers.get('X-CSRF-Token')
            if not csrf_token:
                return jsonify({
                    'success': False,
                    'error': 'Missing CSRF token'
                }), 400

            # Validate form data
            selected_week = request.form.get('selected_week')
            if not selected_week:
                return jsonify({
                    'success': False,
                    'error': 'No week selected'
                }), 400
            
            # Parse week range
            try:
                week_start, week_end = selected_week.split(',')
                week_start_date = datetime.strptime(week_start, '%Y-%m-%d')
                week_end_date = datetime.strptime(week_end, '%Y-%m-%d')
            except (ValueError, TypeError) as e:
                return jsonify({
                    'success': False,
                    'error': f'Invalid date format: {str(e)}'
                }), 400
            
            processed_files = []
            skipped_files = []
            auto_emailed_files = []
            visible_pdfs = []
            
            logger.info(f"Selected week: {week_start} to {week_end}")
            
            # Process all PDFs in the samples folder
            for pdf_name in os.listdir(PDF_SAMPLES_FOLDER):
                if not pdf_name.endswith('.pdf'):
                    continue
                    
                pdf_path = os.path.join(PDF_SAMPLES_FOLDER, pdf_name)
                if not os.path.exists(pdf_path):
                    continue

                try:
                    # Extract information from PDF
                    pdf_info = PDFProcessor.extract_invoice_info(pdf_path)
                    
                    if not pdf_info:
                        logger.warning(f"Could not extract info from {pdf_name}")
                        continue

                    # Convert dates for comparison
                    pdf_start = datetime.strptime(pdf_info['period_start'], '%Y-%m-%d')
                    pdf_end = datetime.strptime(pdf_info['period_end'], '%Y-%m-%d')
                    
                    logger.info(f"Checking PDF: {pdf_name}")
                    logger.info(f"PDF dates: {pdf_info['period_start']} to {pdf_info['period_end']}")
                    
                    # Check if PDF's date range overlaps with selected week
                    date_overlap = (
                        (pdf_start <= week_end_date and pdf_start >= week_start_date) or  # PDF starts in week
                        (pdf_end >= week_start_date and pdf_end <= week_end_date) or      # PDF ends in week
                        (pdf_start <= week_start_date and pdf_end >= week_end_date)       # PDF encompasses week
                    )
                    
                    logger.info(f"Date overlap: {date_overlap}")
                    
                    if not date_overlap:
                        logger.info("PDF is hidden")
                        continue
                        
                    logger.info("PDF is visible")
                    
                    # Get company name from filename if not in PDF
                    company_name = pdf_info.get('company_name')
                    if not company_name:
                        company_name = pdf_name.split('_')[0].replace('_', ' ').title()

                    invoice_number = pdf_info['invoice_number']
                    
                    # Add to visible PDFs list
                    visible_pdfs.append({
                        'filename': pdf_name,
                        'invoice_number': invoice_number,
                        'company_name': company_name,
                        'period_start': pdf_info['period_start'],
                        'period_end': pdf_info['period_end']
                    })
                    
                    # Create a unique filename
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
                            'invoice_number': invoice_number,
                            'company_name': company_name,
                            'reason': 'File already exists'
                        })
                        continue

                    # Copy file to downloads folder
                    shutil.copy2(pdf_path, download_path)

                    # Check if we have a matching email for auto-sending
                    company_email = db_handler.get_company_email(company_name)
                    
                    if company_email:
                        try:
                            # Send email automatically
                            success = email_handler.send_email(
                                to_email=company_email,
                                subject=f'Invoice {invoice_number} for {company_name}',
                                body=f'Please find attached the invoice {invoice_number} for the period {pdf_info["period_start"]} to {pdf_info["period_end"]}.',
                                attachments=[download_path]
                            )
                            
                            if success:
                                # Move to processed folder after successful email
                                shutil.move(download_path, processed_path)
                                db_handler.mark_as_sent(invoice_number, company_email)
                                
                                auto_emailed_files.append({
                                    'filename': pdf_name,
                                    'invoice_number': invoice_number,
                                    'company_name': company_name,
                                    'email': company_email
                                })
                            else:
                                raise Exception("Failed to send email")
                                
                        except Exception as e:
                            logger.error(f"Error sending email for {pdf_name}: {str(e)}")
                            # Keep in downloads folder if email fails
                            processed_files.append({
                                'filename': pdf_name,
                                'invoice_number': invoice_number,
                                'company_name': company_name,
                                'status': 'pending'
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
                        
                        processed_files.append({
                            'filename': pdf_name,
                            'invoice_number': invoice_number,
                            'company_name': company_name,
                            'status': 'pending'
                        })
                        
                except Exception as e:
                    logger.error(f"Error processing {pdf_name}: {str(e)}")
                    continue
            
            # Send notification email to internal department if any files were processed
            if processed_files:
                try:
                    # Prepare email content
                    subject = f"New Pending Invoices Added (Manual Processing)"
                    body = f"The following invoices have been processed and added to the pending table:\n\n"
                    for file in processed_files:
                        body += f"- Invoice {file['invoice_number']} ({file['company_name']})\n"
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
            
            logger.info(f"Total visible PDFs: {len(visible_pdfs)}")
            
            return jsonify({
                'success': True,
                'message': f"Processed {len(processed_files)} files, auto-emailed {len(auto_emailed_files)} files, skipped {len(skipped_files)} files",
                'processed_files': processed_files,
                'auto_emailed_files': auto_emailed_files,
                'skipped_files': skipped_files,
                'visible_pdfs': visible_pdfs
            })
            
        except Exception as e:
            logger.error(f"Error in manual processing: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    # GET request - render the manual processing page
    try:
        # Get list of PDFs from the samples folder
        pdfs = []
        for pdf in os.listdir(PDF_SAMPLES_FOLDER):
            if not pdf.endswith('.pdf'):
                continue
                
            try:
                pdf_path = os.path.join(PDF_SAMPLES_FOLDER, pdf)
                pdf_info = PDFProcessor.extract_invoice_info(pdf_path)
                if pdf_info:
                    # Get company name from filename if not in PDF
                    company_name = pdf_info.get('company_name')
                    if not company_name:
                        company_name = pdf.split('_')[0].replace('_', ' ').title()
                    
                    pdfs.append({
                        'filename': pdf,
                        'invoice_number': pdf_info['invoice_number'],
                        'company_name': company_name,
                        'period_start': pdf_info['period_start'],
                        'period_end': pdf_info['period_end']
                    })
            except Exception as e:
                logger.error(f"Error processing {pdf}: {str(e)}")
                continue
                
        # Check if request wants JSON
        if request.headers.get('Accept') == 'application/json':
            return jsonify({
                'success': True,
                'pdfs': pdfs
            })
            
        # Return HTML template with generated CSRF token
        return render_template('manual_process.html', pdfs=pdfs)
        
    except Exception as e:
        logger.error(f"Error rendering manual process page: {str(e)}")
        if request.headers.get('Accept') == 'application/json':
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
        flash(f'Error: {str(e)}', 'error')
        return render_template('manual_process.html', pdfs=[])

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
    topic = db_handler.get_chat_topic(chat_id)
    
    # Return JSON if requested
    if request.headers.get('Accept') == 'application/json':
        return jsonify({
            'messages': messages,
            'topic': topic,
            'chat_id': chat_id
        })
    
    # Otherwise return HTML template
    return render_template('index.html', 
                         messages=messages, 
                         current_chat_id=chat_id,
                         chat_history=db_handler.get_chat_history())

@app.route('/chat', methods=['POST'])
def chat():
    try:
        # Check CSRF token
        csrf_token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
        if not csrf_token:
            logger.error("Missing CSRF token")
            return jsonify({
                'error': 'Missing CSRF token'
            }), 400

        if not request.is_json:
            logger.error("Request Content-Type is not application/json")
            return jsonify({
                'error': 'Content-Type must be application/json'
            }), 400

        data = request.get_json()
        if not data:
            logger.error("No JSON data in request")
            return jsonify({
                'error': 'No JSON data provided'
            }), 400

        message = data.get('message')
        chat_id = data.get('chat_id')
        
        if not message:
            logger.error("No message provided in request")
            return jsonify({
                'error': 'No message provided'
            }), 400

        # Create new chat session if needed
        if not chat_id:
            session_id = str(uuid.uuid4())
            chat_id = db_handler.create_chat_session(session_id)
            if not chat_id:
                logger.error("Failed to create chat session")
                return jsonify({
                    'error': 'Failed to create chat session'
                }), 500

        # Store user message
        if not db_handler.add_chat_message(chat_id, 'user', message):
            logger.error("Failed to store user message")
            return jsonify({
                'error': 'Failed to store user message'
            }), 500

        try:
            # Generate response using the existing generate_response function
            response = generate_response(message)
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return jsonify({
                'error': f'Error generating response: {str(e)}'
            }), 500
        
        # Store bot response
        if not db_handler.add_chat_message(chat_id, 'bot', response):
            logger.error("Failed to store bot response")
            return jsonify({
                'error': 'Failed to store bot response'
            }), 500
        
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
            'error': 'An error occurred while processing your message',
            'details': str(e)
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