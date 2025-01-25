import PyPDF2
import pdfplumber
import re
from datetime import datetime
from typing import Dict, Optional
import os

class PDFProcessor:
    @staticmethod
    def extract_invoice_period(text: str) -> Optional[tuple]:
        """Extract invoice period from PDF content"""
        try:
            # Look for invoice period in the text
            period_match = re.search(r'Invoice Period\s+(.*?)(?=Due Date|$)', text, re.DOTALL)
            if period_match:
                period_text = period_match.group(1).strip()
                
                # Clean up the text: remove email addresses and extra whitespace
                period_text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', period_text)
                period_text = ' '.join(period_text.split())
                
                # Pattern 1: "Dec 02, 2024 - Dec 08, 2024" (with possible line breaks)
                pattern1 = r'(\w+\s+\d{2},\s+\d{4})\s*-\s*(\w+\s+\d{2},\s+\d{4})'
                match1 = re.search(pattern1, period_text)
                if match1:
                    try:
                        start_date = datetime.strptime(match1.group(1), '%b %d, %Y')
                        end_date = datetime.strptime(match1.group(2), '%b %d, %Y')
                        return start_date, end_date
                    except ValueError:
                        pass
                
                # Pattern 2: "Dec 02, 2024 - Dec" + "08, 2024" (split across lines)
                pattern2 = r'(\w+)\s+(\d{2}),\s+(\d{4})\s*-\s*(\w+)\s+(\d{2}),\s+(\d{4})'
                match2 = re.search(pattern2, period_text)
                if match2:
                    try:
                        start_month, start_day, start_year, end_month, end_day, end_year = match2.groups()
                        start_date = datetime.strptime(f"{start_month} {start_day}, {start_year}", '%b %d, %Y')
                        end_date = datetime.strptime(f"{end_month} {end_day}, {end_year}", '%b %d, %Y')
                        return start_date, end_date
                    except ValueError:
                        pass
                
                # Pattern 3: Extract from filename as fallback
                filename_match = re.search(r'(\d{8})-(\d{8})', text)
                if filename_match:
                    try:
                        start_str, end_str = filename_match.groups()
                        start_date = datetime.strptime(start_str, '%Y%m%d')
                        end_date = datetime.strptime(end_str, '%Y%m%d')
                        return start_date, end_date
                    except ValueError:
                        pass
                
                # If we get here, try to reconstruct from split parts
                parts = period_text.split('-')
                if len(parts) == 2:
                    try:
                        # Handle case where month/year might be omitted in end date
                        start_parts = parts[0].strip().split()
                        end_parts = parts[1].strip().split()
                        
                        if len(start_parts) == 3 and len(end_parts) >= 2:  # "Dec 02, 2024 - Dec 08"
                            start_date = datetime.strptime(f"{start_parts[0]} {start_parts[1]} {start_parts[2]}", '%b %d, %Y')
                            # Use start date's year if missing from end date
                            if len(end_parts) == 2:
                                end_parts.append(start_parts[2])
                            end_date = datetime.strptime(f"{end_parts[0]} {end_parts[1]} {end_parts[2]}", '%b %d, %Y')
                            return start_date, end_date
                    except ValueError:
                        pass
                
                print(f"Could not parse dates from period text: {period_text}")
            else:
                print("No invoice period found in text")
                
            return None
            
        except Exception as e:
            print(f"Error extracting invoice period: {str(e)}")
            print(f"Text content: {text[:200]}...")  # Print first 200 chars for debugging
            return None

    @staticmethod
    def extract_invoice_info(pdf_path: str) -> Dict:
        """Extract invoice information from PDF"""
        invoice_info = {}
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Process first page
                first_page = pdf.pages[0]
                text = first_page.extract_text()
                
                # Add filename to text for backup date extraction
                filename = os.path.basename(pdf_path)
                text = f"{text}\n{filename}"
                
                # Extract invoice number (primary identifier)
                invoice_match = re.search(r'Invoice #\s*(\d+)', text)
                if invoice_match:
                    invoice_info['invoice_number'] = invoice_match.group(1)
                
                # Extract company name from filename if not found in PDF
                company_match = re.search(r'Customer\s+(.+?)(?=\n|Account)', text)
                if company_match:
                    invoice_info['company_name'] = company_match.group(1).strip()
                else:
                    # Extract from filename (e.g., "company_name_20250101-20250115.pdf")
                    filename_company = filename.split('_')[0].title()
                    invoice_info['company_name'] = filename_company
                
                # Extract invoice date
                date_match = re.search(r'Invoice Date\s+(.+?)(?=\n)', text)
                if date_match:
                    invoice_info['invoice_date'] = date_match.group(1).strip()
                
                # Extract invoice period
                period = PDFProcessor.extract_invoice_period(text)
                if period:
                    start_date, end_date = period
                    invoice_info['period_start'] = start_date
                    invoice_info['period_end'] = end_date
                else:
                    # Try to extract period from filename as fallback
                    filename_dates = re.search(r'(\d{8})-(\d{8})', filename)
                    if filename_dates:
                        start_str, end_str = filename_dates.groups()
                        invoice_info['period_start'] = datetime.strptime(start_str, '%Y%m%d')
                        invoice_info['period_end'] = datetime.strptime(end_str, '%Y%m%d')
                
                # Extract total amount
                amount_match = re.search(r'Total Amount Due:\s*([\d.]+)', text)
                if amount_match:
                    invoice_info['total_amount'] = float(amount_match.group(1))
                
                # Extract billing email if present
                email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text)
                if email_match:
                    invoice_info['billing_email'] = email_match.group(1)
                
                # Validate required information
                if not invoice_info.get('invoice_number'):
                    raise Exception("Could not extract invoice number from PDF")
                
                if not invoice_info.get('period_start') or not invoice_info.get('period_end'):
                    raise Exception("Could not extract invoice period from PDF or filename")
        
        except Exception as e:
            print(f"Error processing PDF {pdf_path}: {str(e)}")
            raise
        
        return invoice_info

    @staticmethod
    def validate_pdf(pdf_path: str) -> bool:
        """Validate if the PDF is readable and contains required information"""
        try:
            # First check if it's a valid PDF
            with open(pdf_path, 'rb') as file:
                PyPDF2.PdfReader(file)
            
            # Then check for required content
            with pdfplumber.open(pdf_path) as pdf:
                text = pdf.pages[0].extract_text()
                
                # Check for essential elements
                required_elements = [
                    'Invoice #',
                    'Customer',
                    'Invoice Period'
                ]
                
                if not all(element in text for element in required_elements):
                    return False
                
                # Try to extract invoice period
                if not PDFProcessor.extract_invoice_period(text):
                    return False
                
                return True
        except Exception as e:
            print(f"PDF validation error: {str(e)}")
            return False 