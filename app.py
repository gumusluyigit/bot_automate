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
import time
from ms_graph_client import MSGraphClient

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
        # Skip CSRF for API endpoints if they use token authentication
        if request.path.startswith('/api/') and request.headers.get('Authorization'):
            return
            
        # Skip CSRF check for now - Flask-WTF handles it automatically
        # This is a temporary fix until we can properly implement CSRF protection
        pass

# Configure logging with rotation
log_file = 'automation.log'

class SafeRotatingFileHandler(RotatingFileHandler):
    def doRollover(self):
        """
        Do a rollover, as described in __init__().
        """
        if self.stream:
            self.stream.close()
            self.stream = None
        
        try:
            # Add a number to the end of the filename
            for i in range(self.backupCount - 1, 0, -1):
                sfn = self.rotation_filename("%s.%d" % (self.baseFilename, i))
                dfn = self.rotation_filename("%s.%d" % (self.baseFilename, i + 1))
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        try:
                            os.remove(dfn)
                        except:
                            pass
                    try:
                        os.rename(sfn, dfn)
                    except:
                        pass
            dfn = self.rotation_filename(self.baseFilename + ".1")
            if os.path.exists(dfn):
                try:
                    os.remove(dfn)
                except:
                    pass
            if os.path.exists(self.baseFilename):
                try:
                    os.rename(self.baseFilename, dfn)
                except:
                    pass
        except:
            # If rotation fails, just try to open the base file
            pass

        if not self.delay:
            self.stream = self._open()

# Configure handler with custom rotation
handler = SafeRotatingFileHandler(
    log_file,
    maxBytes=1024*1024,  # 1MB per file
    backupCount=5,       # Keep 5 backup files
    delay=True           # Delay file creation until first log
)
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

# Configure root logger
logging.root.setLevel(logging.INFO)
logging.root.handlers.clear()  # Remove any existing handlers
logging.root.addHandler(handler)

# Configure app logger
app.logger.setLevel(logging.INFO)
app.logger.handlers.clear()  # Remove any existing handlers
app.logger.addHandler(handler)

# Configure our logger instance
logger.setLevel(logging.INFO)
logger.handlers.clear()  # Remove any existing handlers
logger.addHandler(handler)

# Enable CORS
# In development, allow all origins, but in production restrict to specific domains
if os.getenv('DEBUG', 'False').lower() == 'true':
    # Development mode - allow all origins
    CORS(app, resources={
        r"/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-CSRF-Token"],
            "supports_credentials": True
        }
    })
else:
    # Production mode - restrict origins
    CORS(app, resources={
        r"/*": {
            "origins": ["https://example.com", "https://www.example.com"],  # Add your production domains here
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

# Initialize Microsoft Graph client if credentials are available
ms_tenant_id = email_config.get('ms_tenant_id') or os.getenv('MS_TENANT_ID')
ms_client_id = email_config.get('ms_client_id') or os.getenv('MS_CLIENT_ID')
ms_client_secret = email_config.get('ms_client_secret') or os.getenv('MS_CLIENT_SECRET')

if all([ms_tenant_id, ms_client_id, ms_client_secret]):
    # Initialize the graph client with credentials
    email_handler.graph_client = MSGraphClient(
        tenant_id=ms_tenant_id,
        client_id=ms_client_id,
        client_secret=ms_client_secret
    )
    print("Microsoft Graph API client initialized successfully")
else:
    print("Warning: Microsoft Graph API credentials not found or incomplete")

# Initialize response cache (5 minutes TTL)
response_cache = TTLCache(maxsize=100, ttl=300)

def validate_api_key(api_key: Optional[str]) -> bool:
    """Validate the OpenAI API key format and length"""
    if not api_key or not isinstance(api_key, str) or len(api_key) < 20:
        return False
    # Check if it starts with expected prefix
    return api_key.startswith(('sk-', 'sk-org-'))

def process_pdf_for_week(week_start: datetime, week_end: datetime) -> Dict:
    """Process PDFs for a specific week"""
    processed_files = []
    skipped_files = []
    auto_emailed_files = []  # New list to track automatically emailed files
    
    logger.info(f"Starting PDF processing for week: {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}")
    
    # Initialize PDF processor
    pdf_processor = PDFProcessor()
    
    # Connect to database once at the beginning
    conn = sqlite3.connect('invoice_emails.db')
    cursor = conn.cursor()
    
    try:
        # Begin transaction
        conn.execute('BEGIN TRANSACTION')
        
        # Download and process PDFs for the specified week
        processed_invoices = pdf_processor.download_and_process_pdfs(week_start, week_end)
        
        if not processed_invoices:
            logger.info("No PDFs found for the specified week")
            conn.close()  # Close connection before returning
            return {"processed": [], "skipped": [], "auto_emailed": []}
        
        # Lists to track processed invoices for the internal notification
        newly_processed_invoices = []
        
        # Process each invoice
        for invoice_info in processed_invoices:
            try:
                if not invoice_info.get('invoice_number'):
                    logger.warning(f"Missing invoice number for {invoice_info.get('filename')}")
                    skipped_files.append({
                        'filename': invoice_info.get('filename'),
                        'reason': 'Missing invoice number'
                    })
                    continue
                
                invoice_number = invoice_info.get('invoice_number')
                company_name = invoice_info.get('company_name')
                total_due = invoice_info.get('total_due')  # Get the total amount
                
                logger.info(f"Processing invoice {invoice_number} for {company_name} with amount {total_due}")
                
                # Skip if invoice already exists
                if db_handler.invoice_exists(invoice_number):
                    logger.info(f"Skipping invoice {invoice_number} - already exists in database")
                    skipped_files.append({
                        'filename': invoice_info.get('filename'),
                        'company_name': company_name,
                        'invoice_number': invoice_number,
                        'reason': 'Bu dosya zaten işlenmiş'
                    })
                    continue
                
                # Get or create company
                cursor.execute('INSERT OR IGNORE INTO Companies (company_name) VALUES (?)', (company_name,))
                cursor.execute('SELECT company_id FROM Companies WHERE company_name = ?', (company_name,))
                company_id = cursor.fetchone()[0]
                
                # Check if company has a registered email
                company_email = db_handler.get_company_email(company_name)
                
                # Insert invoice with amount
                cursor.execute('''
                    INSERT INTO Invoices (
                        company_id, invoice_number, pdf_path, 
                        period_start, period_end, amount, currency, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    company_id,
                    invoice_number,
                    invoice_info['pdf_path'],
                    invoice_info['start_date'].strftime('%Y-%m-%d'),
                    invoice_info['end_date'].strftime('%Y-%m-%d'),
                    float(total_due) if total_due is not None else None,  # Convert to float if exists
                    'USD',  # Default currency
                    'pending'
                ))
                
                # Log success without committing yet
                logger.info(f"Inserted invoice {invoice_number} for {company_name}")
                
                # If company has a registered email, send the invoice directly
                if company_email:
                    logger.info(f"Company {company_name} has registered email: {company_email}. Sending invoice directly.")
                    
                    # Prepare email content
                    subject = f'Invoice {invoice_number} for {company_name}'
                    body = f'Please find attached the invoice {invoice_number} for the period {invoice_info["start_date"].strftime("%Y-%m-%d")} to {invoice_info["end_date"].strftime("%Y-%m-%d")}.'
                    
                    # Send email with PDF attachment
                    success = email_handler.send_email(
                        to_email=company_email,
                        subject=subject,
                        body=body,
                        attachments=[invoice_info['pdf_path']]
                    )
                    
                    if success:
                        # Move file to processed folder
                        processed_path = os.path.join('processed', os.path.basename(invoice_info['pdf_path']))
                        shutil.move(invoice_info['pdf_path'], processed_path)
                        
                        # Mark as sent
                        db_handler.mark_as_sent(invoice_number, company_email)
                        
                        auto_emailed_files.append({
                            'company_name': company_name,
                            'invoice_number': invoice_number,
                            'period_start': invoice_info['start_date'].strftime('%Y-%m-%d'),
                            'period_end': invoice_info['end_date'].strftime('%Y-%m-%d'),
                            'amount': total_due,
                            'currency': 'USD',
                            'email': company_email
                        })
                        
                        logger.info(f"Automatically sent invoice {invoice_number} to {company_email}")
                    else:
                        logger.error(f"Failed to send email for invoice {invoice_number} to {company_email}")
                        # Add to newly processed invoices list for manual handling
                        newly_processed_invoices.append({
                            'company_name': company_name,
                            'invoice_number': invoice_number
                        })
                        
                        processed_files.append({
                            'company_name': company_name,
                            'invoice_number': invoice_number,
                            'period_start': invoice_info['start_date'].strftime('%Y-%m-%d'),
                            'period_end': invoice_info['end_date'].strftime('%Y-%m-%d'),
                            'amount': total_due,
                            'currency': 'USD'
                        })
                else:
                    # Add to newly processed invoices list
                    newly_processed_invoices.append({
                        'company_name': company_name,
                        'invoice_number': invoice_number
                    })
                    
                    processed_files.append({
                        'company_name': company_name,
                        'invoice_number': invoice_number,
                        'period_start': invoice_info['start_date'].strftime('%Y-%m-%d'),
                        'period_end': invoice_info['end_date'].strftime('%Y-%m-%d'),
                        'amount': total_due,
                        'currency': 'USD'
                    })
                
            except Exception as e:
                logger.error(f"Error processing invoice {invoice_info.get('filename')}: {str(e)}")
                skipped_files.append({
                    'filename': invoice_info.get('filename'),
                    'reason': str(e)
                })
        
        # Send a single consolidated email for all newly processed invoices
        if newly_processed_invoices:
            subject = f"New Invoices Processed - {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}"
            
            # Create a list of invoices in the email body
            invoice_list = "\n".join([
                f"- {invoice['company_name']}: Invoice #{invoice['invoice_number']}"
                for invoice in newly_processed_invoices
            ])
            
            body = f"""New invoices have been processed for the period {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}:

{invoice_list}

View all pending invoices at: http://localhost:5000/pending"""

            email_handler.send_email(
                to_email=email_handler.internal_email,
                subject=subject,
                body=body
            )
            logger.info(f"Sent consolidated internal notification for {len(newly_processed_invoices)} invoices")
        
        # If any invoices were automatically emailed, send a notification
        if auto_emailed_files:
            subject = f"Invoices Automatically Sent - {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}"
            
            # Create a list of invoices in the email body
            invoice_list = "\n".join([
                f"- {invoice['company_name']}: Invoice #{invoice['invoice_number']} sent to {invoice['email']}"
                for invoice in auto_emailed_files
            ])
            
            body = f"""The following invoices were automatically sent to registered company emails:

{invoice_list}

These invoices have been marked as sent and will not appear in the pending requests."""

            email_handler.send_email(
                to_email=email_handler.internal_email,
                subject=subject,
                body=body
            )
            logger.info(f"Sent notification for {len(auto_emailed_files)} automatically emailed invoices")
        
        # Commit transaction and close connection
        conn.commit()
        conn.close()
        
        return {
            "processed": processed_files,
            "skipped": skipped_files,
            "auto_emailed": auto_emailed_files
        }
        
    except Exception as e:
        # Rollback transaction on error
        conn.rollback()
        conn.close()
        logger.error(f"Error processing PDFs: {str(e)}")
        return {
            "processed": [],
            "skipped": [],
            "auto_emailed": [],
            "error": str(e)
        }

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
    """Process PDF request from user input"""
    try:
        # Log the input
        logger.info(f"Processing PDF request with input: {lower_input}")
        
        # Define month mapping
        month_map = {
            'ocak': 1, 'şubat': 2, 'mart': 3, 'nisan': 4, 'mayıs': 5, 'haziran': 6,
            'temmuz': 7, 'ağustos': 8, 'eylül': 9, 'ekim': 10, 'kasım': 11, 'aralık': 12
        }
        
        # Try to extract date using different patterns
        day = None
        month = None
        month_name = None
        
        # Pattern 1: "24 şubat" (day month)
        pattern1 = r'(\d{1,2})\s+(' + '|'.join(month_map.keys()) + ')'
        match1 = re.search(pattern1, lower_input)
        
        # Pattern 2: "şubat 24" (month day)
        pattern2 = r'(' + '|'.join(month_map.keys()) + ')\s+(\d{1,2})'
        match2 = re.search(pattern2, lower_input)
        
        if match1:
            day = int(match1.group(1))
            month_name = match1.group(2)
            month = month_map[month_name]
            logger.info(f"Matched pattern 'day month': {day} {month_name}")
        elif match2:
            month_name = match2.group(1)
            month = month_map[month_name]
            day = int(match2.group(2))
            logger.info(f"Matched pattern 'month day': {month_name} {day}")
        else:
            # Fallback to the original word-by-word search
            words = lower_input.split()
            for i, word in enumerate(words):
                if word.isdigit() and 1 <= int(word) <= 31:
                    day = int(word)
                if i + 1 < len(words) and words[i+1] in month_map:
                    month = month_map[words[i+1]]
                    month_name = words[i+1]
                elif word in month_map:
                    month = month_map[word]
                    month_name = word
                    # Look for a day after the month
                    if i + 1 < len(words) and words[i+1].isdigit() and 1 <= int(words[i+1]) <= 31:
                        day = int(words[i+1])
        
        if not (day and month and month_name):
            return "Lütfen geçerli bir tarih belirtin (örnek: '6 ocak' veya '15 aralık' veya 'şubat 24')"
        
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
        
        result = process_pdf_for_week(week_start, week_end)
        processed_files = result.get('processed', [])
        skipped_files = result.get('skipped', [])
        
        # Build the complete response
        response_parts = []
        
        if not processed_files and not skipped_files:
            response_parts.append(f"{day} {month_name} haftası için işlenecek PDF fatura bulunamadı.")
        else:
            response_parts.append(f"{day} {month_name} haftasına ait PDFleri işledim.")
            
            if processed_files:
                response_parts.append("\nİşlenen yeni faturalar:")
                for file in processed_files:
                    response_parts.append(f"- {file['company_name']} ({file['period_start']} - {file['period_end']})")
            
            if skipped_files:
                response_parts.append("\nAtlanan faturalar:")
                for file in skipped_files:
                    reason = file.get('reason', 'Bilinmeyen sebep')
                    filename = file.get('filename', 'Bilinmeyen dosya')
                    response_parts.append(f"- {filename} (Sebep: {reason})")
        
        # Join all response parts with appropriate line breaks
        return '\n'.join(response_parts)
            
    except Exception as e:
        logger.error(f"Error processing PDFs: {e}")
        return f"PDF işleme sırasında bir hata oluştu: {str(e)}"

def process_email_request(user_input: str, lower_input: str) -> str:
    """Process email-related requests"""
    try:
        # First check if email configuration is set up
        if not email_handler.sender_email or not hasattr(email_handler, 'graph_client') or not email_handler.graph_client.token:
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
            r'(?:send|forward)\s+(?:the)?\s*([A-Za-z\s]+)(?:\'s)?\s+invoice\s+(?:to|for)?\s*([\w\.-]+@[\w\.-]+\.\w+)',
            # Pattern 6: "x numaralı pdfi y@test.com adresine gönderebilirsin"
            r'(\d+)\s+(?:numaral[ıi])?\s*(?:pdf|fatura)(?:[ıiy])?\s+([\w\.-]+@[\w\.-]+\.\w+)(?:\s+adres(?:i)?ne)?\s+(?:gönder(?:ebilir(?:sin)?)?|yolla(?:yabilir(?:sin)?)?|at(?:abilir(?:sin)?)?)',
            # Pattern 7: Simple pattern for "invoice_number email_address"
            r'(\d+)(?:\s+numaral[ıi])?\s+(?:pdf|fatura)?.*?([\w\.-]+@[\w\.-]+\.\w+)'
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
                    if identifier.isdigit():
                        return f"{identifier} numaralı fatura bulunamadı veya işlenmemiş durumda."
                    else:
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
        
        # Check if a company name is mentioned in the request
        company_patterns = [
            r'([A-Za-zçğıöşüÇĞİÖŞÜ\s]+)(?:\s+(?:isimli|adl[ıi]|ad[ıi]ndaki))?\s+(?:şirket(?:in)?|firma(?:n[ıi]n)?)',
            r'([A-Za-zçğıöşüÇĞİÖŞÜ\s]+)(?:\s+pdf)',
            r'([A-Za-zçğıöşüÇĞİÖŞÜ\s]+)(?:\s+fatura)'
        ]
        
        company_name = None
        for pattern in company_patterns:
            company_match = re.search(pattern, user_input, re.IGNORECASE)
            if company_match:
                company_name = company_match.group(1).strip()
                break
        
        pending = db_handler.get_pending_requests()
        if not pending:
            return "Gönderilecek işlenmiş fatura bulamadım. Lütfen önce faturaları işleyin."
        
        sent_count = 0
        for request in pending:
            # If company name was found in the request, only send PDFs for that company
            # Compare company names case-insensitively and ignore extra whitespace
            if company_name:
                request_company = request['company_name'].lower().strip()
                search_company = company_name.lower().strip()
                if not (request_company == search_company or 
                       request_company in search_company or 
                       search_company in request_company):
                    continue
                
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
            if company_name:
                return f"{company_name} şirketine ait gönderilecek fatura bulunamadı."
            return "Fatura gönderimi sırasında bir hata oluştu. Lütfen daha sonra tekrar deneyin."
            
    except Exception as e:
        logger.error(f"Error in email sending: {str(e)}")
        return "E-posta gönderimi sırasında bir hata oluştu. Lütfen daha sonra tekrar deneyin."

def process_api_request(user_input: str) -> str:
    """Process API requests"""
    try:
        # First check if it's an email sending request
        lower_input = user_input.lower()
        
        # Check if user is asking about pending requests
        pending_request_patterns = [
            r'bekleyen.*fatura',
            r'bekleyen.*istek',
            r'pending.*request',
            r'pending.*invoice',
            r'bekleyen',
            r'pending'
        ]
        
        is_pending_request = any(re.search(pattern, lower_input) for pattern in pending_request_patterns)
        
        if is_pending_request:
            pending = db_handler.get_pending_requests()
            if not pending:
                return "Şu anda bekleyen fatura bulunmamaktadır." if any(char in lower_input for char in 'çğıöşü') or any(word in lower_input for word in ['bekleyen', 'fatura']) else "There are no pending invoices at the moment."
            
            # Format the response
            if any(char in lower_input for char in 'çğıöşü') or any(word in lower_input for word in ['bekleyen', 'fatura']):
                response = f"Toplam {len(pending)} adet bekleyen fatura bulunmaktadır:\n\n"
                for req in pending:
                    response += f"- {req['company_name']}: Fatura No: {req['invoice_number']}, Dönem: {req['period_start']} - {req['period_end']}\n"
            else:
                response = f"There are {len(pending)} pending invoices:\n\n"
                for req in pending:
                    response += f"- {req['company_name']}: Invoice #: {req['invoice_number']}, Period: {req['period_start']} - {req['period_end']}\n"
            
            return response

        # Check if it's a PDF processing request with date pattern
        if any(word in lower_input for word in ['işle', 'process', 'hafta']):
            # Check for date patterns first
            month_map = {
                'ocak': 1, 'şubat': 2, 'mart': 3, 'nisan': 4, 'mayıs': 5, 'haziran': 6,
                'temmuz': 7, 'ağustos': 8, 'eylül': 9, 'ekim': 10, 'kasım': 11, 'aralık': 12
            }
            
            # Look for date patterns like "24 şubat" or "şubat 24"
            date_patterns = [
                r'(\d{1,2})\s+(' + '|'.join(month_map.keys()) + ')',  # "24 şubat"
                r'(' + '|'.join(month_map.keys()) + ')\s+(\d{1,2})'   # "şubat 24"
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, lower_input)
                if match:
                    # We found a date pattern, process it
                    pdf_response = process_pdf_request(lower_input)
                    return pdf_response
        
        # Check if it's an email sending request
        if any(word in lower_input for word in ['mail', 'email', 'e-posta', 'gönder', 'yolla', 'send']):
            email_response = process_email_request(user_input, lower_input)
            return email_response
        
        # Check for invoice amount query
        # First check for invoice number in the query (must be at least 3 digits to avoid confusion with dates)
        invoice_number_patterns = [
            r'(\d{3,})(?:\s+numaral[ıi])?\s*(?:fatura(?:n[ıi]n)?)?(?:\s+(?:borcu|borç|tutar[ıi]?|amount|total))',  # 44400 numaralı fatura borcu
            r'fatura\s+(?:no|numarası|number)?\s*:?\s*(\d{3,})(?:\s+(?:borcu|borç|tutar[ıi]?|amount|total))?',  # fatura no: 44400
            r'(\d{3,})(?:\s+(?:borcu|borç|tutar[ıi]?|amount|total))',  # 44400 borcu
            r'(\d{3,})(?:\s+fatura)',  # 44400 fatura
            r'fatura\s+(\d{3,})',  # fatura 44400
            r'invoice\s+(?:no|number)?\s*:?\s*(\d{3,})',  # invoice no: 44400
            r'invoice\s+(\d{3,})',  # invoice 44400
            r'(\d{3,})'  # Just the number (3+ digits), if nothing else matches
        ]

        invoice_number = None
        for pattern in invoice_number_patterns:
            match = re.search(pattern, lower_input)
            if match:
                invoice_number = match.group(1)
                logger.info(f"Amount query - Invoice number: {invoice_number} (matched pattern: {pattern})")
                break

        if invoice_number and not any(word in lower_input for word in ['mail', 'email', 'e-posta', 'gönder', 'yolla', 'send']):
            # First try to find by invoice number (exact match)
            invoice_info = db_handler.get_invoice_amount(invoice_number)
            if invoice_info:
                amount = invoice_info.get('amount')
                if amount is not None:
                    formatted_amount = "{:,.2f}".format(float(amount))
                    return f"Fatura detayları:\nFatura No: {invoice_number}\nŞirket: {invoice_info['company_name']}\nTutar: {formatted_amount} {invoice_info.get('currency', 'USD')}\nDönem: {invoice_info['period_start']} - {invoice_info['period_end']}"
                else:
                    return f"Fatura No: {invoice_number} için tutar bilgisi bulunamadı."
            else:
                return f"{invoice_number} numaralı fatura bulunamadı."

        # If no specific pattern matched, proceed with GPT response
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
            return "Şu anda istediğiniz işlemi gerçekleştiremiyorum. Lütfen daha sonra tekrar deneyin." if is_turkish else \
                   "I'm unable to process your request at the moment. Please try again later."
        
        # Handle email-related requests
        if any(word in lower_input for word in ['mail', 'email', 'e-posta', 'eposta']):
            if not email_handler.sender_email or not hasattr(email_handler, 'graph_client') or not email_handler.graph_client.token:
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
DOWNLOADS_FOLDER = os.path.abspath('downloads')
PROCESSED_FOLDER = os.path.abspath('processed')

# Create necessary directories
os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# Log directory paths
print(f"DOWNLOADS_FOLDER: {DOWNLOADS_FOLDER}")
print(f"PROCESSED_FOLDER: {PROCESSED_FOLDER}")

# Print database status
print("Database initialized successfully")
print(f"Using database at: {db_handler.db_path}")

@app.route('/')
def index():
    # Get chat history only
    chat_history = db_handler.get_chat_history()
    return render_template('index.html', 
                         chat_history=chat_history)

@app.route('/manual-process', methods=['GET', 'POST'])
def manual_process():
    if request.method == 'POST':
        try:
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
            
            logger.info(f"Selected week: {week_start} to {week_end}")
            
            # Process PDFs for the selected week
            result = process_pdf_for_week(week_start_date, week_end_date)
            
            # Check if there was an error
            if 'error' in result:
                return jsonify({
                    'success': False,
                    'error': result['error']
                }), 500
            
            processed_files = result['processed']
            skipped_files = result['skipped']
            auto_emailed_files = result.get('auto_emailed', [])
            
            return jsonify({
                'success': True,
                'message': f"Processed {len(processed_files)} files, skipped {len(skipped_files)} files, automatically emailed {len(auto_emailed_files)} files",
                'processed_files': processed_files,
                'skipped_files': skipped_files,
                'auto_emailed_files': auto_emailed_files
            })
            
        except Exception as e:
            logger.error(f"Error in manual processing: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    # GET request - render the manual processing page
    try:
        # Return HTML template with just the date selection interface
        return render_template('manual_process.html', pdfs=[])
        
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
        if not request.is_json:
            logger.error("Request Content-Type is not application/json")
            return jsonify({
                'error': 'Request must be JSON'
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
        internal_email = request.form.get('internal_email')
        ms_tenant_id = request.form.get('ms_tenant_id')
        ms_client_id = request.form.get('ms_client_id')
        ms_client_secret = request.form.get('ms_client_secret')
        
        if not all([sender_email, internal_email]):
            flash('Email addresses are required', 'error')
            return redirect(url_for('settings'))
        
        try:
            # Update email handler
            email_handler.sender_email = sender_email
            email_handler.internal_email = internal_email
            
            # Save Microsoft Graph API settings to environment variables
            if ms_tenant_id:
                os.environ['MS_TENANT_ID'] = ms_tenant_id
            if ms_client_id:
                os.environ['MS_CLIENT_ID'] = ms_client_id
            
            # Only update client secret if a new value is provided
            if ms_client_secret and ms_client_secret.strip():
                os.environ['MS_CLIENT_SECRET'] = ms_client_secret
                logger.info("Client secret updated")
            else:
                # Keep existing client secret
                ms_client_secret = os.getenv('MS_CLIENT_SECRET', '')
                logger.info("Using existing client secret")
            
            # Save configuration
            config_handler.save_config(
                sender_email=sender_email,
                internal_email=internal_email,
                ms_tenant_id=ms_tenant_id,
                ms_client_id=ms_client_id,
                ms_client_secret=ms_client_secret if ms_client_secret and ms_client_secret.strip() else None
            )
            
            # Test authentication if Microsoft Graph API credentials are provided
            if all([ms_tenant_id, ms_client_id, os.getenv('MS_CLIENT_SECRET')]):
                # Reinitialize the graph client with new credentials
                email_handler.graph_client = MSGraphClient(
                    tenant_id=ms_tenant_id,
                    client_id=ms_client_id,
                    client_secret=os.getenv('MS_CLIENT_SECRET')
                )
                
                if email_handler.authenticate():
                    flash('Email settings saved and authenticated successfully with Microsoft Graph API', 'success')
                else:
                    flash('Authentication failed with provided Microsoft Graph API credentials', 'error')
            else:
                flash('Email settings saved. Microsoft Graph API credentials are incomplete or missing.', 'warning')
                
        except Exception as e:
            logger.error(f"Error saving settings: {str(e)}")
            flash(f'Error saving settings: {str(e)}', 'error')
        
        return redirect(url_for('settings'))
    
    # Get current configuration
    email_config = config_handler.get_config()
    
    # Get Microsoft Graph API settings from environment variables
    ms_tenant_id = os.getenv('MS_TENANT_ID', '')
    ms_client_id = os.getenv('MS_CLIENT_ID', '')
    # Don't pass the actual client secret to the template for security
    ms_client_secret = ''
    
    # Get all companies with their current emails
    companies = db_handler.get_all_companies()
        
    return render_template('settings.html',
        sender_email=email_config['sender_email'],
        internal_email=email_config['internal_email'],
        ms_tenant_id=ms_tenant_id,
        ms_client_id=ms_client_id,
        ms_client_secret=ms_client_secret,
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

        # Close any existing database connections
        try:
            db_handler.close_connections()
        except:
            pass

        # Delete and recreate database
        if os.path.exists(db_handler.db_path):
            try:
                os.remove(db_handler.db_path)
            except PermissionError:
                # If file is still locked, try force closing all connections
                import gc
                gc.collect()  # Force garbage collection
                try:
                    os.remove(db_handler.db_path)
                except Exception as e:
                    flash(f'Could not delete database file: {str(e)}. Please restart the application.', 'error')
                    return redirect(url_for('settings'))

        # Initialize fresh database
        db_handler.initialize_database()

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

@app.route('/company-email-history/<path:company_name>')
def company_email_history(company_name):
    """View email history for a company"""
    try:
        history = db_handler.get_company_email_history(company_name)
        if not history:
            flash('No email history found for this company', 'warning')
            return redirect(url_for('settings'))
            
        return render_template('email_history.html', 
                             company_name=company_name, 
                             history=history)
    except Exception as e:
        logger.error(f"Error getting email history: {e}")
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

@app.route('/get-pdfs-for-week', methods=['POST'])
def get_pdfs_for_week():
    try:
        # Get date range from request
        data = request.get_json()
        if not data or 'week_start' not in data or 'week_end' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing date range'
            }), 400

        # Parse dates
        try:
            week_start = datetime.strptime(data['week_start'], '%Y-%m-%d')
            week_end = datetime.strptime(data['week_end'], '%Y-%m-%d')
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': f'Invalid date format: {str(e)}'
            }), 400

        # Initialize PDF processor and get PDFs for the week
        pdf_processor = PDFProcessor()
        pdf_info_list = pdf_processor.pdf_downloader.get_pdf_links(week_start, week_end)
        
        # Filter PDFs for the selected week (already filtered by get_pdf_links)
        filtered_pdfs = []
        for pdf_info in pdf_info_list:
            # Add a flag to indicate the company name is temporary
            filtered_pdfs.append({
                'filename': pdf_info['filename'],
                'company_name': pdf_info['company_name'],
                'company_name_temporary': True,  # Add this flag to indicate the name is temporary
                'period_start': pdf_info['start_date'].strftime('%Y-%m-%d'),
                'period_end': pdf_info['end_date'].strftime('%Y-%m-%d'),
                'url': pdf_info['url']
            })

        return jsonify({
            'success': True,
            'pdfs': filtered_pdfs,
            'note': 'Company names shown are temporary and will be updated from PDF content during processing'
        })

    except Exception as e:
        logger.error(f"Error fetching PDFs for week: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    print("\nStarting Flask server...")
    print("Access the application at: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
else:
    # This ensures we see the server info even when running with 'flask run'
    print("\nWARNING: This is a development server. Do not use it in a production deployment.")
    print("Use a production WSGI server instead.")
    print(" * Running on http://127.0.0.1:5000")
    print("Press CTRL+C to quit\n") 