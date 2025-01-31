import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
import sqlite3
import os
import json
from database_handler import DatabaseHandler

class EmailHandler:
    def __init__(self, sender_email: str, internal_email: str, db_path=r"C:\SharedDB\pending_requests.db"):
        self.sender_email = sender_email
        self.internal_email = internal_email
        self.db = DatabaseHandler(db_path)
        
        # Initialize database
        self.db_path = r'C:\SharedDB\invoice_emails.db'
        self.init_database()
        
        # Gmail SMTP settings
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.app_password = None  # Will be set through save_credentials
        
    def save_credentials(self, app_password: str):
        """Save Gmail App Password"""
        try:
            credentials = {
                'app_password': app_password
            }
            with open('gmail_config.json', 'w') as f:
                json.dump(credentials, f)
            self.app_password = app_password
            return True
        except Exception as e:
            print(f"Error saving credentials: {str(e)}")
            return False
            
    def _load_credentials(self):
        """Load Gmail credentials from config file"""
        try:
            if os.path.exists('gmail_config.json'):
                with open('gmail_config.json', 'r') as f:
                    credentials = json.load(f)
                    self.app_password = credentials.get('app_password')
                    return True
            return False
        except Exception as e:
            print(f"Error loading credentials: {str(e)}")
            return False
            
    def authenticate(self) -> bool:
        """Test Gmail authentication"""
        try:
            if not self.app_password:
                if not self._load_credentials():
                    raise Exception("No credentials configured")
                    
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.app_password)
            server.quit()
            return True
        except Exception as e:
            print(f"Authentication error: {str(e)}")
            return False
    
    def init_database(self):
        """Initialize SQLite database for storing invoice-email mappings"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoice_emails (
                invoice_number TEXT PRIMARY KEY,
                email_address TEXT NOT NULL,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sent_emails (
                invoice_number TEXT PRIMARY KEY,
                email_address TEXT NOT NULL,
                sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pdf_path TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_email_from_database(self, invoice_number: str) -> str:
        """Get email address for invoice number from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT email_address FROM invoice_emails WHERE invoice_number = ?', 
                      (invoice_number,))
        result = cursor.fetchone()
        
        conn.close()
        return result[0] if result else None
    
    def save_email_to_database(self, invoice_number: str, email_address: str):
        """Save or update email address for invoice number"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO invoice_emails (invoice_number, email_address)
            VALUES (?, ?)
        ''', (invoice_number, email_address))
        
        conn.commit()
        conn.close()
    
    def request_company_email(self, invoice_number: str, subject: str, pdf_path: str) -> bool:
        """Send email to internal department requesting company email"""
        try:
            if not self.app_password:
                if not self._load_credentials():
                    raise Exception("No credentials configured")
                    
            msg = MIMEMultipart()
            msg["From"] = self.sender_email
            msg["To"] = self.internal_email
            msg["Subject"] = subject
            
            body = f"Please provide the email address for invoice number: {invoice_number}"
            msg.attach(MIMEText(body, "plain"))
            
            # Attach PDF if it exists
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    pdf_attachment = MIMEApplication(f.read(), _subtype="pdf")
                    pdf_attachment.add_header(
                        "Content-Disposition", 
                        "attachment", 
                        filename=os.path.basename(pdf_path)
                    )
                    msg.attach(pdf_attachment)
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.app_password)
            server.send_message(msg)
            server.quit()
            
            # Store request details with company name from filename
            filename = os.path.basename(pdf_path)
            company_name = filename.split('_')[0].title()  # Extract company name from filename
            
            self.db.add_pending_request(invoice_number, company_name, pdf_path)
            
            return True
        except Exception as e:
            print(f"Error requesting company email: {str(e)}")
            return False
    
    def check_if_sent(self, invoice_number: str) -> bool:
        """Check if an invoice has already been sent"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT sent_date FROM sent_emails WHERE invoice_number = ?', 
                      (invoice_number,))
        result = cursor.fetchone()
        
        conn.close()
        return result is not None
        
    def mark_as_sent(self, invoice_number: str, email_address: str, pdf_path: str):
        """Mark an invoice as sent"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO sent_emails 
            (invoice_number, email_address, pdf_path)
            VALUES (?, ?, ?)
        ''', (invoice_number, email_address, pdf_path))
        
        conn.commit()
        conn.close()

    def send_receipt_to_company(self, company_email: str, invoice_number: str, 
                              pdf_path: str) -> bool:
        """Send PDF receipt to company email"""
        try:
            # Check if already sent
            if self.check_if_sent(invoice_number):
                print(f"Receipt for invoice {invoice_number} was already sent to {company_email}")
                return False
                
            if not self.app_password:
                if not self._load_credentials():
                    raise Exception("No credentials configured")
                    
            msg = MIMEMultipart()
            msg["From"] = self.sender_email
            msg["To"] = company_email
            msg["Subject"] = f"Receipt for Invoice {invoice_number}"
            
            body = "Please find attached the receipt for your records."
            msg.attach(MIMEText(body, "plain"))
            
            # Attach PDF
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    pdf_attachment = MIMEApplication(f.read(), _subtype="pdf")
                    pdf_attachment.add_header(
                        "Content-Disposition", 
                        "attachment", 
                        filename=os.path.basename(pdf_path)
                    )
                    msg.attach(pdf_attachment)
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.app_password)
            server.send_message(msg)
            server.quit()
            
            # Mark as sent
            self.mark_as_sent(invoice_number, company_email, pdf_path)
            
            return True
        except Exception as e:
            print(f"Error sending receipt: {str(e)}")
            return False
    
    def check_for_responses(self) -> dict:
        """Check for responses from internal department with company emails"""
        try:
            if not self.db.get_pending_requests():
                return None
                
            # In test mode, simulate a response for the first pending request
            for invoice_number, details in self.db.get_pending_requests().items():
                # Simulate receiving an email address
                company_email = f"company_{invoice_number}@example.com"
                
                # Save to database
                self.save_email_to_database(invoice_number, company_email)
                
                return {
                    'invoice_number': invoice_number,
                    'company_email': company_email,
                    'request_details': details
                }
            
            return None
        except Exception as e:
            print(f"Error checking responses: {str(e)}")
            return None

    def add_to_pending(self, invoice_number, company_name, pdf_path, period_start=None, period_end=None):
        """Add an invoice to pending requests"""
        return self.db.add_pending_request(invoice_number, company_name, pdf_path, period_start, period_end)
        
    def get_pending_requests(self):
        """Get all pending requests"""
        return self.db.get_pending_requests()
        
    def update_email(self, invoice_number, email):
        """Update email for a pending request"""
        return self.db.update_email(invoice_number, email)
        
    def is_invoice_pending(self, invoice_number):
        """Check if an invoice is already in pending requests"""
        return self.db.is_invoice_pending(invoice_number)
        
    def send_email(self, to_email, subject, body, attachments=None):
        """Send an email with optional attachments"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Add attachments
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as f:
                            part = MIMEApplication(f.read(), Name=os.path.basename(file_path))
                            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
                            msg.attach(part)
            
            # Send email (implementation depends on your email server setup)
            # This is a placeholder - you'll need to add your actual email sending code
            print(f"Would send email to {to_email} with subject: {subject}")
            print(f"Attachments: {attachments}")
            
            # Mark as sent in database
            for attachment in attachments or []:
                invoice_number = self._extract_invoice_number(attachment)
                if invoice_number:
                    self.db.mark_as_sent(invoice_number, to_email)
            
            return True
            
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            # Log error in database
            for attachment in attachments or []:
                invoice_number = self._extract_invoice_number(attachment)
                if invoice_number:
                    self.db.mark_as_sent(invoice_number, to_email, status="error", error_message=str(e))
            return False
            
    def _extract_invoice_number(self, pdf_path):
        """Extract invoice number from PDF filename or path"""
        # This is a placeholder - implement based on your PDF naming convention
        return None
        
    def get_email_history(self, invoice_number=None):
        """Get email sending history"""
        return self.db.get_email_history(invoice_number) 