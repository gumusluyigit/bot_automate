import os
from datetime import datetime
from web_automation import WebAutomation
from pdf_processor import PDFProcessor
from database import get_email_by_invoice, add_invoice_email, init_db
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from config import (
    EMAIL_USER, EMAIL_PASSWORD, SMTP_SERVER, SMTP_PORT,
    INTERNAL_DEPT_EMAIL
)

class ReceiptAutomation:
    def __init__(self):
        self.download_dir = os.path.join(os.getcwd(), 'downloads')
        os.makedirs(self.download_dir, exist_ok=True)
        self.web_automation = WebAutomation(self.download_dir)
        init_db()  # Initialize database

    def send_email_with_pdf(self, to_email: str, pdf_path: str, subject: str, body: str):
        """Send email with PDF attachment"""
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        with open(pdf_path, 'rb') as f:
            pdf_attachment = MIMEApplication(f.read(), _subtype='pdf')
            pdf_attachment.add_header('Content-Disposition', 'attachment', filename=os.path.basename(pdf_path))
            msg.attach(pdf_attachment)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)

    def request_email_from_department(self, invoice_number: str, company_name: str):
        """Send email to internal department requesting company email"""
        subject = f"Email Request for Invoice {invoice_number}"
        body = f"""
        Hello,
        
        Please provide the email address for the following company:
        Invoice Number: {invoice_number}
        Company Name: {company_name}
        
        Best regards,
        Receipt Automation System
        """
        
        self.send_email_with_pdf(
            INTERNAL_DEPT_EMAIL,
            subject=subject,
            body=body
        )

    def process_pdf_for_date(self, date_str: str):
        """Process PDF for a specific date"""
        try:
            # Setup and login
            self.web_automation.setup_driver()
            if not self.web_automation.login():
                raise Exception("Failed to login")

            # Download PDF
            pdf_path = self.web_automation.search_and_download_pdf(date_str)
            if not pdf_path:
                raise Exception(f"Failed to download PDF for date {date_str}")

            # Process PDF
            if not PDFProcessor.validate_pdf(pdf_path):
                raise Exception(f"Invalid PDF file: {pdf_path}")

            # Extract information
            invoice_info = PDFProcessor.extract_invoice_info(pdf_path)
            invoice_number = invoice_info.get('invoice_number')
            company_name = invoice_info.get('company_name')

            if not invoice_number:
                raise Exception("Could not extract invoice number from PDF")

            # Get email from database
            email = get_email_by_invoice(invoice_number)
            
            if not email:
                # Request email from internal department
                self.request_email_from_department(invoice_number, company_name)
                print(f"Email requested for invoice {invoice_number}")
                return

            # Send PDF to company
            subject = f"Receipt for Invoice {invoice_number}"
            body = f"""
            Dear {company_name},
            
            Please find attached the receipt for invoice {invoice_number}.
            
            Best regards,
            Your Company
            """
            
            self.send_email_with_pdf(email, pdf_path, subject, body)
            print(f"PDF sent to {email} for invoice {invoice_number}")

        except Exception as e:
            print(f"Error processing PDF for date {date_str}: {str(e)}")
        finally:
            self.web_automation.close()

def main():
    automation = ReceiptAutomation()
    
    # Example usage
    today = datetime.now()
    date_str = today.strftime("%Y%m%d")
    automation.process_pdf_for_date(date_str)

if __name__ == "__main__":
    main() 