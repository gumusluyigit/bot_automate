import PyPDF2
import pdfplumber
import re
from datetime import datetime
from typing import Dict, Optional, Tuple
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
                
                # Pattern 3: Handle case where month/year might be omitted in end date
                parts = period_text.split('-')
                if len(parts) == 2:
                    try:
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
    def validate_pdf(pdf_path: str) -> bool:
        """Validate if the file is a proper PDF"""
        try:
            # Simple validation by checking file header
            with open(pdf_path, 'rb') as f:
                header = f.read(4)
                # Check if file starts with %PDF
                if header.startswith(b'%PDF'):
                    return True
                    
                # For our sample PDFs, check if it contains our marker
                f.seek(0)
                content = f.read()
                try:
                    # Try UTF-8 first
                    decoded = content.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        # Try ASCII if UTF-8 fails
                        decoded = content.decode('ascii', errors='ignore')
                    except:
                        return False
                        
                if 'Sample Invoice for' in decoded:
                    return True
            return False
        except Exception as e:
            print(f"PDF validation error: {str(e)}")
            return False
            
    @staticmethod
    def extract_invoice_info(pdf_path: str) -> dict:
        """Extract invoice information from PDF"""
        try:
            info = {}
            
            # First try to read PDF content using pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() + "\n"
                
                # Extract invoice number from PDF content - try multiple patterns
                invoice_patterns = [
                    r'Invoice\s*Number:?\s*(\d+)',  # Standard format: "Invoice Number: 12345"
                    r'Invoice\s*#:?\s*(\d+)',       # Alternative format: "Invoice #: 12345"
                    r'Invoice\s*ID:?\s*(\d+)',      # Alternative format: "Invoice ID: 12345"
                    r'Invoice:\s*(\d+)',            # Simple format: "Invoice: 12345"
                    r'#\s*(\d+)',                   # Very simple format: "# 12345"
                    r'Number:\s*(\d+)',             # Simple format: "Number: 12345"
                    r'ID:\s*(\d+)',                 # Simple format: "ID: 12345"
                    r'(\d{8,})'                     # Any 8+ digit number (likely an invoice number)
                ]
                
                for pattern in invoice_patterns:
                    invoice_match = re.search(pattern, text, re.IGNORECASE)
                    if invoice_match:
                        info['invoice_number'] = invoice_match.group(1).strip()
                        break
                
                # If no invoice number found in content, try to extract from filename
                if 'invoice_number' not in info:
                    filename = os.path.basename(pdf_path)
                    # Try to find any 8+ digit number in the filename
                    number_match = re.search(r'(\d{8,})', filename)
                    if number_match:
                        info['invoice_number'] = number_match.group(1)
                
                # Extract company name
                company_patterns = [
                    r'Company:?\s*([^\n]+)',
                    r'Client:?\s*([^\n]+)',
                    r'Customer:?\s*([^\n]+)',
                    r'Bill\s+To:?\s*([^\n]+)'
                ]
                
                for pattern in company_patterns:
                    company_match = re.search(pattern, text, re.IGNORECASE)
                    if company_match:
                        info['company_name'] = company_match.group(1).strip()
                        break
                
                # If no company name found in content, extract from filename
                if 'company_name' not in info:
                    filename = os.path.basename(pdf_path)
                    match = re.match(r'([a-zA-Z0-9_]+)(?:_tdm)?_(\d{8})-(\d{8})\.pdf', filename)
                    if match:
                        info['company_name'] = match.group(1).replace('_', ' ').title()
                
                # Extract period dates
                period_patterns = [
                    r'Period:?\s*(\d{4}-\d{2}-\d{2})\s*to\s*(\d{4}-\d{2}-\d{2})',
                    r'Date:?\s*(\d{4}-\d{2}-\d{2})\s*to\s*(\d{4}-\d{2}-\d{2})',
                    r'From:?\s*(\d{4}-\d{2}-\d{2})\s*to\s*(\d{4}-\d{2}-\d{2})'
                ]
                
                for pattern in period_patterns:
                    period_match = re.search(pattern, text, re.IGNORECASE)
                    if period_match:
                        info['period_start'] = datetime.strptime(period_match.group(1).strip(), '%Y-%m-%d')
                        info['period_end'] = datetime.strptime(period_match.group(2).strip(), '%Y-%m-%d')
                        break
                
                # If no period found in content, extract from filename
                if 'period_start' not in info or 'period_end' not in info:
                    filename = os.path.basename(pdf_path)
                    match = re.match(r'([a-zA-Z0-9_]+)(?:_tdm)?_(\d{8})-(\d{8})\.pdf', filename)
                    if match:
                        try:
                            info['period_start'] = datetime.strptime(match.group(2), '%Y%m%d')
                            info['period_end'] = datetime.strptime(match.group(3), '%Y%m%d')
                        except ValueError as e:
                            print(f"Error parsing dates from filename: {str(e)}")
            
            # Check if we found all required information
            required_fields = ['invoice_number', 'company_name', 'period_start', 'period_end']
            if all(field in info for field in required_fields):
                return info
            
            missing_fields = [field for field in required_fields if field not in info]
            raise Exception(f"Could not extract required information from PDF. Missing fields: {missing_fields}")
            
        except Exception as e:
            print(f"Error extracting invoice info from {pdf_path}: {str(e)}")
            raise 