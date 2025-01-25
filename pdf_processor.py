import PyPDF2
import pdfplumber
import re
from datetime import datetime
from typing import Dict, Optional

class PDFProcessor:
    @staticmethod
    def extract_date_from_filename(filename: str) -> Optional[tuple]:
        """Extract start and end dates from filename pattern like '20241202-20241208'"""
        pattern = r'(\d{8})-(\d{8})'
        match = re.search(pattern, filename)
        if match:
            start_date = datetime.strptime(match.group(1), '%Y%m%d')
            end_date = datetime.strptime(match.group(2), '%Y%m%d')
            return start_date, end_date
        return None

    @staticmethod
    def extract_invoice_info(pdf_path: str) -> Dict:
        """Extract invoice number and other relevant information from PDF"""
        invoice_info = {}
        
        with pdfplumber.open(pdf_path) as pdf:
            # Process first page
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            
            # Extract invoice number
            invoice_match = re.search(r'Invoice #\s*(\d+)', text)
            if invoice_match:
                invoice_info['invoice_number'] = invoice_match.group(1)
            
            # Extract company name
            company_match = re.search(r'Customer\s+(.+?)(?=\n|Account)', text)
            if company_match:
                invoice_info['company_name'] = company_match.group(1).strip()
            
            # Extract invoice date
            date_match = re.search(r'Invoice Date\s+(.+?)(?=\n)', text)
            if date_match:
                invoice_info['invoice_date'] = date_match.group(1).strip()
            
            # Extract invoice period (handling multi-line periods)
            period_match = re.search(r'Invoice Period\s+(.*?)(?=Due Date)', text, re.DOTALL)
            if period_match:
                # Clean up the period text
                period = period_match.group(1)
                # Remove email and clean up whitespace
                period = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', period)
                period = ' '.join(period.split())
                invoice_info['invoice_period'] = period
            
            # Extract total amount
            amount_match = re.search(r'Total Amount Due:\s*([\d.]+)', text)
            if amount_match:
                invoice_info['total_amount'] = float(amount_match.group(1))
            
            # Extract billing email
            email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text)
            if email_match:
                invoice_info['billing_email'] = email_match.group(1)
        
        return invoice_info

    @staticmethod
    def validate_pdf(pdf_path: str) -> bool:
        """Validate if the PDF is readable and contains expected information"""
        try:
            with open(pdf_path, 'rb') as file:
                PyPDF2.PdfReader(file)
                
            # Additional validation using pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = pdf.pages[0].extract_text()
                # Check if it contains key invoice elements
                required_elements = ['Invoice #', 'Customer', 'Invoice Date']
                return all(element in text for element in required_elements)
        except:
            return False 