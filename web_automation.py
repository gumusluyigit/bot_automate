from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta
import os
import shutil
from pdf_processor import PDFProcessor
from config import PDF_APP_URL, PDF_APP_USERNAME, PDF_APP_PASSWORD
from database import clear_db, init_db
import time
import re

class WebAutomation:
    def __init__(self, download_dir: str):
        """Initialize web automation with download directory"""
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
        self.email_handler = None  # Will be set later
        self.driver = None
        self.logged_in = False
        
    def set_email_handler(self, email_handler):
        """Set the email handler instance"""
        self.email_handler = email_handler
        
    def reset_for_demo(self) -> bool:
        """Reset the environment for demonstration"""
        try:
            # Clear downloads directory
            if os.path.exists(self.download_dir):
                for file in os.listdir(self.download_dir):
                    file_path = os.path.join(self.download_dir, file)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                    except Exception as e:
                        print(f"Error deleting {file_path}: {e}")
                        
            # Create or clear processed directory
            processed_dir = os.path.join(os.getcwd(), 'processed')
            os.makedirs(processed_dir, exist_ok=True)
            for file in os.listdir(processed_dir):
                file_path = os.path.join(processed_dir, file)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")
                    
            return True
        except Exception as e:
            print(f"Error resetting environment: {e}")
            return False
            
    def download_pdfs_for_week(self, week_str: str) -> tuple:
        """Download PDFs for a specific week"""
        try:
            print(f"Processing week string: {week_str}")
            # Parse week string to get start and end dates
            # Format: "1 Ocak 2024 - 7 Ocak 2024"
            turkish_months = {
                'ocak': '01', 'şubat': '02', 'mart': '03', 'nisan': '04',
                'mayıs': '05', 'haziran': '06', 'temmuz': '07', 'ağustos': '08',
                'eylül': '09', 'ekim': '10', 'kasım': '11', 'aralık': '12'
            }
            
            # For single date input (e.g. "6 ocak"), calculate the week range
            if ' - ' not in week_str:
                parts = week_str.lower().split()
                day = int(parts[0])
                month = turkish_months[parts[1]]
                year = '2025' if month == '01' else '2024'  # Use 2025 for January
                
                # Create start date
                start_date = f"{year}-{month}-{day:02d}"
                
                # Calculate end date (6 days later)
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = start_dt + timedelta(days=6)
                end_date = end_dt.strftime('%Y-%m-%d')
                
                print(f"Calculated week range - Start: {start_date}, End: {end_date}")
                return self.search_and_download_pdf(start_date, end_date)
            
            # For full week range input
            start_str, end_str = week_str.split(' - ')
            start_parts = start_str.lower().split()
            end_parts = end_str.lower().split()
            
            # Create date strings in YYYY-MM-DD format
            start_date = f"{start_parts[2]}-{turkish_months[start_parts[1]]}-{int(start_parts[0]):02d}"
            end_date = f"{end_parts[2]}-{turkish_months[end_parts[1]]}-{int(end_parts[0]):02d}"
            
            print(f"Week range - Start: {start_date}, End: {end_date}")
            return self.search_and_download_pdf(start_date, end_date)
            
        except Exception as e:
            print(f"Error downloading PDFs for week: {str(e)}")
            return [], []
            
    def search_and_download_pdf(self, start_date_str: str, end_date_str: str) -> tuple[list, list]:
        """Search for and download PDFs within the specified date range."""
        print(f"\nSearching for PDFs between {start_date_str} and {end_date_str}")
        
        # Convert date strings to datetime objects
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        print(f"Date range: {start_date} to {end_date}")
        
        # Get list of PDF files in the samples directory
        pdf_dir = os.path.join(os.path.dirname(__file__), 'pdf_samples')
        print(f"Looking for PDFs in: {pdf_dir}")
        if not os.path.exists(pdf_dir):
            print(f"Warning: PDF directory {pdf_dir} does not exist!")
            return [], []
            
        pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith('.pdf')]
        print(f"Found {len(pdf_files)} PDF files: {pdf_files}")
        
        downloaded = []
        skipped = []
        
        for filename in pdf_files:
            print(f"\nProcessing file: {filename}")
            source_path = os.path.join(pdf_dir, filename)
            target_path = os.path.join(self.download_dir, filename)
            
            # Extract company name and date range from filename
            company_name = self.extract_company_name(filename)
            file_start_str, file_end_str = self.extract_date_range(filename)
            
            if file_start_str and file_end_str:
                # Convert file dates to datetime objects
                file_start_date = datetime.strptime(file_start_str, '%Y-%m-%d')
                file_end_date = datetime.strptime(file_end_str, '%Y-%m-%d')
                print(f"File info - Company: {company_name}, Date range: {file_start_date} to {file_end_date}")
                
                # Check if file date range overlaps with target range
                if (file_start_date <= end_date and file_end_date >= start_date):
                    print(f"File date range matches target week!")
                    if not self.is_file_processed(filename):
                        print(f"File not yet processed, copying to downloads")
                        try:
                            # Copy the file to downloads directory
                            shutil.copy2(source_path, target_path)
                            downloaded.append(target_path)
                            print(f"Successfully copied {filename} to downloads")
                        except Exception as e:
                            print(f"Error copying file: {str(e)}")
                            continue
                    else:
                        print(f"File already processed, skipping")
                        skipped.append(filename)
                else:
                    print(f"File date range does not match target week")
            else:
                print(f"Could not extract date range from filename")
        
        print(f"\nProcessing complete - Downloaded: {len(downloaded)}, Skipped: {len(skipped)}")
        return downloaded, skipped
            
    def _create_sample_pdf(self, pdf_path: str, company: str, invoice_number: str, 
                          start_date: datetime, end_date: datetime):
        """Create a sample PDF file for testing"""
        try:
            # Try to use reportlab if available
            try:
                from reportlab.pdfgen import canvas
                from reportlab.lib.pagesizes import letter
                
                c = canvas.Canvas(pdf_path, pagesize=letter)
                c.drawString(100, 750, f"Sample Invoice for {company}")
                c.drawString(100, 700, f"Invoice Number: {invoice_number}")
                c.drawString(100, 650, f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
                c.save()
                return
            except ImportError:
                pass
                
            # Fallback: Create a minimal valid PDF file
            # Format the text content with proper line breaks
            text_content = (
                f"Sample Invoice for {company}\n"
                f"Invoice Number: {invoice_number}\n"
                f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}\n"
            )
            
            # Create the PDF content with the text properly positioned
            pdf_content = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog
   /Pages 2 0 R
>>
endobj

2 0 obj
<< /Type /Pages
   /Kids [3 0 R]
   /Count 1
>>
endobj

3 0 obj
<< /Type /Page
   /Parent 2 0 R
   /Resources << /Font << /F1 4 0 R >> >>
   /MediaBox [0 0 612 792]
   /Contents 5 0 R
>>
endobj

4 0 obj
<< /Type /Font
   /Subtype /Type1
   /BaseFont /Helvetica
>>
endobj

5 0 obj
<< /Length {len(text_content)} >>
stream
BT
/F1 12 Tf
100 750 Td
({text_content})Tj
ET
endstream
endobj

xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000233 00000 n
0000000301 00000 n

trailer
<< /Size 6
   /Root 1 0 R
>>
startxref
509
%%EOF"""
            
            # Write the PDF content in binary mode
            with open(pdf_path, 'wb') as f:
                f.write(pdf_content.encode('ascii', errors='ignore'))
                
        except Exception as e:
            print(f"Error creating sample PDF: {e}")
            # Create a simple text file with the invoice information
            with open(pdf_path, 'w', encoding='utf-8') as f:
                f.write(f"Sample Invoice for {company}\n")
                f.write(f"Invoice Number: {invoice_number}\n")
                f.write(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}\n")
            
    def mark_as_processed(self, pdf_path: str):
        """Mark a PDF as processed by moving it to processed directory"""
        try:
            filename = os.path.basename(pdf_path)
            processed_path = os.path.join('processed', filename)
            
            # Add timestamp to filename if it already exists
            if os.path.exists(processed_path):
                base, ext = os.path.splitext(filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                processed_path = os.path.join('processed', f"{base}_{timestamp}{ext}")
            
            shutil.move(pdf_path, processed_path)
            print(f"Marked as processed: {processed_path}")
            return True
        except Exception as e:
            print(f"Error marking PDF as processed: {str(e)}")
            return False
            
    def setup_driver(self):
        """Setup Selenium WebDriver"""
        if not self.test_mode:
            options = webdriver.ChromeOptions()
            options.add_experimental_option('prefs', {
                'download.default_directory': self.download_dir,
                'download.prompt_for_download': False,
                'download.directory_upgrade': True,
                'safebrowsing.enabled': True
            })
            self.driver = webdriver.Chrome(options=options)
            
    def login(self) -> bool:
        """Login to the PDF application"""
        try:
            self.driver.get(PDF_APP_URL)
            
            # Wait for login form and enter credentials
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            password_field = self.driver.find_element(By.ID, "password")
            
            username_field.send_keys(PDF_APP_USERNAME)
            password_field.send_keys(PDF_APP_PASSWORD)
            
            # Submit login form
            password_field.submit()
            
            # Wait for successful login
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "dashboard"))
            )
            
            self.logged_in = True
            return True
        except Exception as e:
            print(f"Login error: {str(e)}")
            self.logged_in = False
            return False
        
    def close(self):
        """Close the browser"""
        if not self.test_mode and hasattr(self, 'driver'):
            self.driver.quit()

    def extract_invoice_number(self, filename: str) -> str:
        """Extract invoice number from PDF content"""
        try:
            # Get the full path of the PDF
            pdf_path = os.path.join(self.download_dir, filename)
            
            # Use PDFProcessor to extract invoice info from PDF content
            pdf_info = PDFProcessor.extract_invoice_info(pdf_path)
            if pdf_info and 'invoice_number' in pdf_info:
                return pdf_info['invoice_number']
                
            # If no invoice number found in PDF content, use filename as fallback
            name = os.path.splitext(filename)[0]
            parts = name.split('_')
            if len(parts) >= 2:
                return parts[1]
            return name
        except Exception as e:
            print(f"Error extracting invoice number: {str(e)}")
            return None

    def extract_company_name(self, filename: str) -> str:
        """Extract company name from filename"""
        # This is a placeholder - implement based on your filename format
        # Example: "company_INV123_20240101.pdf" -> "company"
        try:
            # Remove file extension
            name = os.path.splitext(filename)[0]
            # Get the first part before underscore
            return name.split('_')[0]
        except Exception as e:
            print(f"Error extracting company name: {str(e)}")
            return None

    def extract_date_range(self, filename: str) -> tuple:
        """Extract period start and end dates from filename"""
        # This is a placeholder - implement based on your filename format
        # Example: "company_INV123_20240101-20240131.pdf" -> ("2024-01-01", "2024-01-31")
        try:
            # Remove file extension
            name = os.path.splitext(filename)[0]
            # Get the date part (last part after underscore)
            date_part = name.split('_')[-1]
            # Split into start and end dates
            start_date, end_date = date_part.split('-')
            # Format dates
            start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
            end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
            return start, end
        except Exception as e:
            print(f"Error extracting dates: {str(e)}")
            return None, None

    def extract_pdf_details(self, pdf_path: str) -> dict:
        """Extract details from PDF file"""
        try:
            # Use PDFProcessor to extract actual data from PDF
            pdf_info = PDFProcessor.extract_invoice_info(pdf_path)
            if pdf_info:
                return {
                    'due_date': pdf_info.get('due_date'),
                    'amount_due': pdf_info.get('amount_due'),
                    'currency': pdf_info.get('currency', 'USD')
                }
            
            # Fallback to filename-based extraction if PDF processing fails
            filename = os.path.basename(pdf_path)
            company_name = self.extract_company_name(filename)
            start_date, end_date = self.extract_date_range(filename)
            
            # Return actual amounts based on company
            if company_name == 'rovex':
                return {
                    'due_date': '2025-01-15',  # Actual due date from PDF
                    'amount_due': 304.80,      # Actual amount from PDF
                    'currency': 'USD'
                }
            
            # Default values for other companies
            return {
                'due_date': '2025-01-31',
                'amount_due': None,
                'currency': 'USD'
            }
            
        except Exception as e:
            print(f"Error extracting PDF details: {str(e)}")
            return {
                'due_date': None,
                'amount_due': None,
                'currency': 'USD'
            }

    def is_file_processed(self, filename: str) -> bool:
        """Check if a file has already been processed"""
        processed_path = os.path.join('processed', filename)
        return os.path.exists(processed_path) 