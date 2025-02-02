import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
import sqlite3
import os
import json

class EmailHandler:
    def __init__(self, sender_email=None, internal_email=None):
        self.sender_email = sender_email
        self.internal_email = internal_email
        self._password = None
        
    def save_credentials(self, app_password):
        """Save the app password"""
        try:
            self._password = app_password
            return True
        except Exception as e:
            print(f"Error saving credentials: {e}")
            return False
            
    def authenticate(self):
        """Test authentication with saved credentials"""
        if not self.sender_email or not self._password:
            return False
            
        try:
            # Try to connect to Gmail's SMTP server
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(self.sender_email, self._password)
            return True
        except Exception as e:
            print(f"Authentication failed: {e}")
            return False
    
    def send_email(self, to_email, subject, body, attachments=None):
        """Send an email with optional attachments"""
        if not self.sender_email or not self._password:
            print("Email settings not configured")
            return False
            
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add body
            msg.attach(MIMEText(body, 'plain'))
            
            # Add attachments
            if attachments:
                if isinstance(attachments, str):
                    attachments = [attachments]
                    
                for attachment in attachments:
                    if os.path.exists(attachment):
                        with open(attachment, 'rb') as f:
                            part = MIMEApplication(f.read(), Name=os.path.basename(attachment))
                            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment)}"'
                            msg.attach(part)
            
            # Send email
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(self.sender_email, self._password)
                server.send_message(msg)
                
            return True
            
        except Exception as e:
            print(f"Error sending email: {e}")
            return False
            
    def send_email_directly(self, invoice_number, pdf_path, company_name, email, subject=None, body=None):
        """Send an email for a specific invoice"""
        if not subject:
            subject = f'Invoice {invoice_number} for {company_name}'
            
        if not body:
            body = f'Please find attached the invoice {invoice_number} for {company_name}.'
            
        return self.send_email(
            to_email=email,
            subject=subject,
            body=body,
            attachments=[pdf_path] if pdf_path else None
        )

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create invoice_emails table to store known email mappings
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoice_emails (
            invoice_number TEXT PRIMARY KEY,
            email_address TEXT NOT NULL,
            company_name TEXT,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create invoice_details table to store PDF content information
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoice_details (
            invoice_number TEXT PRIMARY KEY,
            company_name TEXT NOT NULL,
            period_start DATE,
            period_end DATE,
            due_date DATE,
            amount_due DECIMAL(10,2),
            currency TEXT,
            pdf_path TEXT,
            processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create pending_requests table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_requests (
            invoice_number TEXT PRIMARY KEY,
            company_name TEXT,
            pdf_path TEXT,
            period_start TEXT,
            period_end TEXT,
            status TEXT DEFAULT 'pending',
            content_summary TEXT
        )
        ''')
        
        # Create sent_emails table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_emails (
            invoice_number TEXT PRIMARY KEY,
            email TEXT,
            company_name TEXT,
            status TEXT,
            sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            pdf_path TEXT
        )
        ''')
        
        conn.commit()
        conn.close()
        
    def get_email_for_invoice(self, invoice_number: str) -> tuple:
        """Get email address and company name for invoice number from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT email_address, company_name FROM invoice_emails WHERE invoice_number = ?', 
                      (invoice_number,))
        result = cursor.fetchone()
        
        conn.close()
        return result if result else (None, None)
    
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
            if not self._password:
                if not self.authenticate():
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
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(self.sender_email, self._password)
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
        # Update sent_emails table
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO sent_emails 
            (invoice_number, email_address, pdf_path)
            VALUES (?, ?, ?)
        ''', (invoice_number, email_address, pdf_path))
        
        conn.commit()
        conn.close()
        
        # Update pending_requests table using DatabaseHandler
        self.db.mark_as_sent(invoice_number, email_address, "sent")

    def send_receipt_to_company(self, company_email: str, invoice_number: str, 
                              pdf_path: str) -> bool:
        """Send PDF receipt to company email"""
        try:
            # Check if already sent
            if self.check_if_sent(invoice_number):
                print(f"Receipt for invoice {invoice_number} was already sent to {company_email}")
                return False
                
            if not self._password:
                if not self.authenticate():
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
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(self.sender_email, self._password)
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

    def get_pending_requests(self):
        """Get all pending requests"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT invoice_number, company_name, pdf_path, period_start, period_end, status
                FROM pending_requests
                WHERE status = 'pending'
                ORDER BY invoice_number
            ''')
            
            results = cursor.fetchall()
            conn.close()
            
            return results
        except Exception as e:
            print(f"Error getting pending requests: {str(e)}")
            return []
            
    def add_to_pending(self, invoice_number: str, company_name: str, pdf_path: str,
                      period_start: str, period_end: str) -> bool:
        """Add a request to pending requests"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO pending_requests 
                (invoice_number, company_name, pdf_path, period_start, period_end, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
            ''', (invoice_number, company_name, pdf_path, period_start, period_end))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error adding to pending requests: {str(e)}")
            return False
            
    def is_invoice_pending(self, invoice_number: str) -> bool:
        """Check if an invoice is in pending requests"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT 1 FROM pending_requests WHERE invoice_number = ?', 
                         (invoice_number,))
            
            result = cursor.fetchone() is not None
            conn.close()
            
            return result
        except Exception as e:
            print(f"Error checking pending status: {str(e)}")
            return False
            
    def get_email_history(self, invoice_number=None):
        """Get email sending history"""
        return self.db.get_email_history(invoice_number)

    def get_company_due_date(self, company_name: str) -> str:
        """Get the latest due date for a company"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT due_date 
            FROM invoice_details 
            WHERE company_name = ? 
            ORDER BY due_date DESC 
            LIMIT 1
        ''', (company_name,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None

    def get_company_amount_due(self, company_name: str, start_date: str, end_date: str) -> tuple:
        """Get amount due for a company within a specific period"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # First try to get amount from invoice_details
            cursor.execute('''
                SELECT amount_due, currency 
                FROM invoice_details 
                WHERE company_name = ? 
                AND (
                    (period_start <= ? AND period_end >= ?) OR
                    (period_start <= ? AND period_end >= ?) OR
                    (period_start >= ? AND period_end <= ?)
                )
                ORDER BY processed_date DESC
                LIMIT 1
            ''', (company_name, end_date, start_date, end_date, start_date, start_date, end_date))
            
            result = cursor.fetchone()
            
            if not result:
                # If not found in invoice_details, check pending_requests
                cursor.execute('''
                    SELECT i.amount_due, i.currency
                    FROM pending_requests p
                    JOIN invoice_details i ON p.invoice_number = i.invoice_number
                    WHERE p.company_name = ? 
                    AND (
                        (p.period_start <= ? AND p.period_end >= ?) OR
                        (p.period_start <= ? AND p.period_end >= ?) OR
                        (p.period_start >= ? AND p.period_end <= ?)
                    )
                    ORDER BY i.processed_date DESC
                    LIMIT 1
                ''', (company_name, end_date, start_date, end_date, start_date, start_date, end_date))
                
                result = cursor.fetchone()
            
            conn.close()
            return result if result else (None, None)
            
        except Exception as e:
            print(f"Error getting amount due: {str(e)}")
            return (None, None)

    def get_company_email(self, company_name: str) -> str:
        """Get the email address for a company"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT email_address 
            FROM invoice_emails 
            WHERE company_name = ? 
            ORDER BY added_date DESC 
            LIMIT 1
        ''', (company_name,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None

    def store_invoice_details(self, invoice_number: str, company_name: str, 
                            period_start: str, period_end: str, due_date: str, 
                            amount_due: float, currency: str, pdf_path: str) -> bool:
        """Store invoice details in the database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO invoice_details 
                (invoice_number, company_name, period_start, period_end, 
                 due_date, amount_due, currency, pdf_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (invoice_number, company_name, period_start, period_end, 
                 due_date, amount_due, currency, pdf_path))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error storing invoice details: {str(e)}")
            return False

    def get_pdf_path_for_invoice(self, invoice_number: str) -> str:
        """Get the PDF file path for a given invoice number"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get PDF path from pending_requests table
            cursor.execute("""
                SELECT pdf_path FROM pending_requests 
                WHERE invoice_number = ? AND status = 'pending'
            """, (invoice_number,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return result[0]
            return None
            
        except Exception as e:
            print(f"Error getting PDF path: {str(e)}")
            return None

    def get_invoice_period(self, company_name: str, start_date: str, end_date: str) -> tuple:
        """Get the actual invoice period for a company within a date range"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT period_start, period_end FROM pending_requests 
                WHERE company_name = ? 
                AND (
                    (period_start <= ? AND period_end >= ?) OR
                    (period_start <= ? AND period_end >= ?) OR
                    (period_start >= ? AND period_end <= ?)
                )
                ORDER BY period_start ASC
                LIMIT 1
            """, (company_name, end_date, start_date, end_date, start_date, start_date, end_date))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return result[0], result[1]
            return None
            
        except Exception as e:
            print(f"Error getting invoice period: {str(e)}")
            return None 