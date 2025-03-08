import PyPDF2
import pdfplumber
import re
from datetime import datetime
from typing import Dict, Optional, Tuple, List
import os
import concurrent.futures
import logging
from pdf_downloader import PDFDownloader

# Get logger instance
logger = logging.getLogger('pdf_processor')

class PDFProcessor:
    def __init__(self):
        self.pdf_downloader = PDFDownloader()
        self.processed_cache = {}  # Cache for processed PDFs
    
    def download_and_process_pdfs(self, week_start=None, week_end=None) -> List[Dict]:
        """
        Download PDFs from Beox website and process them using concurrent processing.
        If week_start and week_end are provided, only download PDFs for that week.
        Returns a list of processed invoice information.
        """
        # Get PDF links with date filtering already applied
        pdf_info_list = self.pdf_downloader.get_pdf_links(week_start, week_end)
        logger.info(f"Found {len(pdf_info_list)} PDFs to process")
        
        # First download all PDFs concurrently with more workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Create a dictionary mapping futures to their corresponding pdf_info
            future_to_pdf = {
                executor.submit(self.pdf_downloader.download_pdf, pdf_info): pdf_info 
                for pdf_info in pdf_info_list
            }
            
            downloaded_pdfs = []
            for future in concurrent.futures.as_completed(future_to_pdf):
                pdf_info = future_to_pdf[future]
                try:
                    filepath = future.result()
                    if filepath:
                        pdf_info['pdf_path'] = filepath
                        downloaded_pdfs.append(pdf_info)
                except Exception as e:
                    logger.error(f"Error downloading {pdf_info['filename']}: {str(e)}")
        
        logger.info(f"Successfully downloaded {len(downloaded_pdfs)} PDFs")
        
        # Then process all downloaded PDFs concurrently with more workers
        processed_invoices = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Create a list of futures for processing each PDF
            future_to_pdf = {
                executor.submit(self.process_single_pdf, pdf_info): pdf_info 
                for pdf_info in downloaded_pdfs
            }
            
            for future in concurrent.futures.as_completed(future_to_pdf):
                pdf_info = future_to_pdf[future]
                try:
                    invoice_info = future.result()
                    if invoice_info:
                        processed_invoices.append(invoice_info)
                except Exception as e:
                    logger.error(f"Error processing {pdf_info['filename']}: {str(e)}")
        
        logger.info(f"Successfully processed {len(processed_invoices)} PDFs")
        return processed_invoices
    
    def process_single_pdf(self, pdf_info: Dict) -> Optional[Dict]:
        """Process a single PDF file and extract invoice information"""
        filepath = pdf_info.get('pdf_path')
        
        # Check if we've already processed this file
        if filepath in self.processed_cache:
            logger.info(f"Using cached result for {filepath}")
            return self.processed_cache[filepath]
        
        if not filepath or not self.validate_pdf(filepath):
            return None
        
        # Extract invoice information directly without sample text extraction
        logger.info(f"Processing PDF: {filepath}")
        
        # Extract invoice information
        invoice_info = self.extract_invoice_info(filepath)
        if invoice_info:
            # Store the original company name for comparison
            original_company_name = pdf_info.get('company_name')
            
            # Merge PDF info with extracted info, but prioritize company_name from PDF content
            result = {**pdf_info, **invoice_info}
            
            # Store the original company name for logging purposes
            result['original_company_name'] = original_company_name
            
            # Ensure we're using the company name from the PDF content (Customer Account Code)
            if 'company_name' in invoice_info and invoice_info['company_name']:
                # Log the company name change if different
                if original_company_name != invoice_info['company_name']:
                    logger.info(f"Updated company name from '{original_company_name}' to '{invoice_info['company_name']}' based on PDF content")
                result['company_name'] = invoice_info['company_name']
            else:
                logger.warning(f"No company name found in PDF content for {filepath}, using original name: {original_company_name}")
            
            # Cache the result
            self.processed_cache[filepath] = result
            return result
        
        return None

    def extract_invoice_period(self, text: str) -> Optional[tuple]:
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
                        
                        # If end date is missing month/year, use from start date
                        if len(end_parts) == 1 and len(start_parts) >= 3:
                            end_parts = [start_parts[0], end_parts[0], start_parts[2]]
                        
                        start_date = datetime.strptime(' '.join(start_parts), '%b %d %Y')
                        end_date = datetime.strptime(' '.join(end_parts), '%b %d %Y')
                        return start_date, end_date
                    except (ValueError, IndexError):
                        pass
        except Exception as e:
            logger.error(f"Error extracting invoice period: {str(e)}")
        return None

    def validate_pdf(self, pdf_path: str) -> bool:
        """Validate if the PDF file exists and has a non-zero size"""
        try:
            if not os.path.exists(pdf_path):
                logger.warning(f"PDF file not found: {pdf_path}")
                return False
            
            # Check if file has content (non-zero size)
            if os.path.getsize(pdf_path) == 0:
                logger.warning(f"PDF file is empty: {pdf_path}")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error validating PDF {pdf_path}: {str(e)}")
            return False

    def extract_invoice_number(self, text: str) -> Optional[str]:
        """Extract invoice number from PDF content"""
        try:
            # Look for invoice number in the text
            patterns = [
                r'Invoice\s+(?:No|Number|#)?\s*[:.]?\s*(\d+)',  # Invoice No: 12345
                r'Fatura\s+(?:No|Numarası)?\s*[:.]?\s*(\d+)',  # Fatura No: 12345
                r'(?:No|Number|#)\s*[:.]?\s*(\d+)',  # No: 12345
                r'(?<!\d)(\d{5,6})(?!\d)'  # Standalone 5-6 digit number
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1)
            
            return None
        except Exception as e:
            logger.error(f"Error extracting invoice number: {str(e)}")
            return None

    def extract_invoice_info(self, pdf_path: str) -> dict:
        """Extract information from a PDF invoice"""
        invoice_info = {}

        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Extract text from first page only for faster processing
                # Most invoice information is typically on the first page
                pages_to_extract = min(2, len(pdf.pages))
                text = "\n".join([pdf.pages[i].extract_text() for i in range(pages_to_extract) if pdf.pages[i].extract_text()])
                
                # Compile regex patterns once for better performance
                company_patterns = [
                    re.compile(r'Customer\s+([^\n\r]+)', re.IGNORECASE),
                    re.compile(r'Customer\s+Account\s+Code\s*[:.]\s*([^\n\r]+)', re.IGNORECASE),
                    re.compile(r'Customer\s+Account\s*[:.]\s*([^\n\r]+)', re.IGNORECASE),
                    re.compile(r'Account\s+Code\s*[:.]\s*([^\n\r]+)', re.IGNORECASE),
                    re.compile(r'Customer\s+Code\s*[:.]\s*([^\n\r]+)', re.IGNORECASE),
                    re.compile(r'Customer\s+Name\s*[:.]\s*([^\n\r]+)', re.IGNORECASE),
                    re.compile(r'Company\s+Name\s*[:.]\s*([^\n\r]+)', re.IGNORECASE),
                    re.compile(r'Bill\s+To\s*:?\s*([^\n\r]+)', re.IGNORECASE)
                ]
                
                # Extract company name
                company_name = None
                for pattern in company_patterns:
                    company_match = pattern.search(text)
                    if company_match:
                        company_name = company_match.group(1).strip()
                        logger.info(f"Extracted company name: {company_name}")
                        break
                
                if company_name:
                    invoice_info['company_name'] = company_name
                else:
                    # If we can't find the company name, use filename-based name
                    filename = os.path.basename(pdf_path)
                    name_parts = filename.replace('.pdf', '').split('_')
                    if len(name_parts) > 1:
                        company_name = '_'.join(name_parts[:-1]).replace('_', ' ').title()
                        invoice_info['company_name'] = company_name
                        logger.info(f"Using filename-based company name: {company_name}")
                
                # Compile invoice number patterns
                invoice_patterns = [
                    re.compile(r'Invoice\s+#\s*(\d+)', re.IGNORECASE),
                    re.compile(r'Invoice\s+Number\s*[:.]\s*(\d+)', re.IGNORECASE),
                    re.compile(r'Invoice\s+No\s*[:.]\s*(\d+)', re.IGNORECASE),
                    re.compile(r'Invoice\s+ID\s*[:.]\s*(\d+)', re.IGNORECASE),
                    re.compile(r'Fatura\s+No\s*[:.]\s*(\d+)', re.IGNORECASE)
                ]
                
                # Extract Invoice Number
                invoice_number = None
                for pattern in invoice_patterns:
                    invoice_match = pattern.search(text)
                    if invoice_match:
                        invoice_number = invoice_match.group(1)
                        break
                
                if invoice_number:
                    invoice_info['invoice_number'] = invoice_number
                else:
                    # Try alternative method if needed
                    invoice_number = self.extract_invoice_number(text)
                    if invoice_number:
                        invoice_info['invoice_number'] = invoice_number

                # Extract Invoice Period using compiled patterns
                period_patterns = [
                    re.compile(r'Invoice Period\s+([^\n]+)', re.IGNORECASE),
                    re.compile(r'Period\s*[:.]\s*([^\n]+)', re.IGNORECASE),
                    re.compile(r'Date Range\s*[:.]\s*([^\n]+)', re.IGNORECASE)
                ]
                
                period_found = False
                for pattern in period_patterns:
                    period_match = pattern.search(text)
                    if period_match:
                        period_text = period_match.group(1).strip()
                        date_match = re.findall(r'(\w+\s+\d{2},\s+\d{4})', period_text)
                        if len(date_match) == 2:
                            invoice_info['start_date'] = datetime.strptime(date_match[0], '%b %d, %Y')
                            invoice_info['end_date'] = datetime.strptime(date_match[1], '%b %d, %Y')
                            period_found = True
                            break
                
                if not period_found:
                    # Try alternative method
                    invoice_period = self.extract_invoice_period(text)
                    if invoice_period:
                        start_date, end_date = invoice_period
                        invoice_info['start_date'] = start_date
                        invoice_info['end_date'] = end_date

                # Compile amount patterns
                amount_patterns = [
                    re.compile(r'Total Amount Due:\s*[€$]?([\d,.]+)', re.IGNORECASE),
                    re.compile(r'Total Amount:\s*[€$]?([\d,.]+)', re.IGNORECASE),
                    re.compile(r'Amount Due:\s*[€$]?([\d,.]+)', re.IGNORECASE),
                    re.compile(r'Grand Total:\s*[€$]?([\d,.]+)', re.IGNORECASE),
                    re.compile(r'Total:\s*[€$]?([\d,.]+)', re.IGNORECASE),
                    re.compile(r'Toplam Tutar:\s*[€$]?([\d,.]+)', re.IGNORECASE),
                    re.compile(r'Toplam:\s*[€$]?([\d,.]+)', re.IGNORECASE),
                    re.compile(r'Tutar:\s*[€$]?([\d,.]+)', re.IGNORECASE),
                    re.compile(r'Genel Toplam:\s*[€$]?([\d,.]+)', re.IGNORECASE),
                ]
                
                # Extract Total Amount Due
                amount_found = False
                for pattern in amount_patterns:
                    amount_match = pattern.search(text)
                    if amount_match:
                        try:
                            # Remove any non-numeric characters except for decimal point
                            amount_str = amount_match.group(1).replace(',', '')
                            amount = float(amount_str)
                            invoice_info['total_due'] = amount
                            amount_found = True
                            break
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Error parsing amount: {e}")
                
                if not amount_found:
                    logger.warning(f"Could not extract total amount from PDF content in {pdf_path}")
                
                # Add PDF Path
                invoice_info['pdf_path'] = pdf_path

            return invoice_info

        except Exception as e:
            logger.error(f"Error extracting invoice info from {pdf_path}: {str(e)}")
            return invoice_info

    def extract_invoice_info_old(self, pdf_path: str) -> dict:
        """Legacy method for extracting information from a PDF invoice"""
        try:
            invoice_info = {}
            
            # Extract text using PyPDF2
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text()
                
                # Extract invoice period
                invoice_period = self.extract_invoice_period(text)
                if invoice_period:
                    start_date, end_date = invoice_period
                    invoice_info['start_date'] = start_date
                    invoice_info['end_date'] = end_date
                
                # Add the PDF path
                invoice_info['pdf_path'] = pdf_path
                
                return invoice_info
        except Exception as e:
            print(f"Error extracting invoice info from {pdf_path}: {str(e)}")
            return {}

    def extract_sample_text(self, pdf_path: str) -> str:
        """Extract and return a sample of text from a PDF for debugging purposes"""
        # Skip extraction if debug logging is not enabled
        if not logger.isEnabledFor(logging.DEBUG):
            return "Debug logging disabled"
            
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Extract text from first page only
                if len(pdf.pages) > 0 and pdf.pages[0].extract_text():
                    text = pdf.pages[0].extract_text()
                    # Log only the first 500 characters (reduced from 1000)
                    sample = text[:500]
                    logger.debug(f"Sample text from {pdf_path}:\n{sample}")
                    return sample
                return "No text extracted"
        except Exception as e:
            logger.error(f"Error extracting sample text from {pdf_path}: {str(e)}")
            return f"Error: {str(e)}" 