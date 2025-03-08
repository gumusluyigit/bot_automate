import os
import json
import time
import functools
from datetime import datetime
from ms_graph_client import MSGraphClient

def retry_on_failure(retries=3, delay=2):
    """Retry decorator for handling temporary network issues"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < retries - 1:  # Don't sleep on the last attempt
                        time.sleep(delay)
            print(f"Failed after {retries} attempts. Last error: {last_error}")
            return False
        return wrapper
    return decorator

class EmailHandler:
    def __init__(self, sender_email=None, internal_email=None):
        self.sender_email = sender_email
        self.internal_email = internal_email
        
        # Initialize Microsoft Graph client
        self.graph_client = MSGraphClient()
        
    def authenticate(self):
        """Test authentication with Microsoft Graph API"""
        try:
            # Test connection to Microsoft Graph API
            success, message = self.graph_client.test_connection(self.sender_email)
            if success:
                return True
            else:
                print(f"Authentication failed: {message}")
                return False
        except Exception as e:
            print(f"Authentication failed: {e}")
            return False
    
    @retry_on_failure(retries=3, delay=2)
    def send_email(self, to_email, subject, body, attachments=None):
        """Send an email with optional attachments using Microsoft Graph API"""
        if not self.sender_email:
            print("Email settings not configured")
            return False
            
        try:
            # Send email using Microsoft Graph API
            return self.graph_client.send_email(
                sender_email=self.sender_email,
                to_email=to_email,
                subject=subject,
                body=body,
                attachments=attachments
            )
            
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
    
    def request_company_email(self, invoice_number: str, subject: str, pdf_path: str) -> bool:
        """Send email to internal department requesting company email"""
        try:
            if not self.internal_email:
                raise Exception("Internal email not configured")
                    
            body = f"Please provide the email address for invoice number: {invoice_number}"
            
            # Send email using Microsoft Graph API
            return self.send_email(
                to_email=self.internal_email,
                subject=f"Email Request: {subject}",
                body=body,
                attachments=[pdf_path] if pdf_path else None
            )
                
        except Exception as e:
            print(f"Error requesting company email: {e}")
            return False
    
    def format_html_email(self, subject, body_html, attachments=None):
        """Format an HTML email with optional attachments"""
        try:
            return self.send_email(
                to_email=self.internal_email,
                subject=subject,
                body=body_html,
                attachments=attachments
            )
        except Exception as e:
            print(f"Error sending HTML email: {e}")
            return False

    def send_receipt_to_company(self, company_email: str, invoice_number: str, 
                              pdf_path: str) -> bool:
        """Send PDF receipt to company email"""
        try:
            body = "Please find attached the receipt for your records."
            
            # Send email using Microsoft Graph API
            return self.send_email(
                to_email=company_email,
                subject=f"Receipt for Invoice {invoice_number}",
                body=body,
                attachments=[pdf_path] if os.path.exists(pdf_path) else None
            )
                
        except Exception as e:
            print(f"Error sending receipt: {e}")
            return False 