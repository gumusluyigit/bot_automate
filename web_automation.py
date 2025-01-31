from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
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
            
    def search_and_download_pdf(self, target_week: tuple) -> tuple:
        """
        Search for and copy PDFs from pdf_samples folder for the target week
        Returns tuple of (downloaded_pdfs, skipped_pdfs)
        """
        downloaded = []
        skipped = []
        
        try:
            start_date, end_date = target_week
            
            # Validate date range
            if start_date > end_date:
                raise ValueError("Start date cannot be after end date")
                
            # Ensure we're getting PDFs for the correct week
            if (end_date - start_date).days > 7:
                raise ValueError("Date range cannot exceed 7 days")
                
            # Check if pdf_samples directory exists
            samples_dir = os.path.join(os.getcwd(), 'pdf_samples')
            if not os.path.exists(samples_dir):
                raise Exception("pdf_samples directory not found")
                
            # Get all PDF files from the samples directory that match our date range
            matching_pdfs = []
            for filename in os.listdir(samples_dir):
                if not filename.lower().endswith('.pdf'):
                    continue
                    
                try:
                    # Extract dates from filename using regex
                    match = re.match(r'([a-zA-Z0-9_]+)(?:_[a-zA-Z0-9_]+)?_(\d{8})-(\d{8})\.pdf', filename)
                    if not match:
                        continue
                        
                    company, file_start_str, file_end_str = match.groups()
                    file_start_date = datetime.strptime(file_start_str, '%Y%m%d')
                    file_end_date = datetime.strptime(file_end_str, '%Y%m%d')
                    
                    # Check if the file's date range overlaps with our target week
                    if (file_start_date <= end_date and file_end_date >= start_date):
                        source_path = os.path.join(samples_dir, filename)
                        target_path = os.path.join(self.download_dir, filename)
                        
                        # Skip if file already exists in downloads
                        if os.path.exists(target_path):
                            continue
                            
                        matching_pdfs.append((source_path, target_path))
                        
                except Exception:
                    continue
                    
            # Process matching PDFs
            if matching_pdfs:
                print(f"Found {len(matching_pdfs)} PDF(s) within target week\n")
                
                for i, (source_path, target_path) in enumerate(matching_pdfs, 1):
                    filename = os.path.basename(target_path)
                    print(f"Processing PDF ({i}/{len(matching_pdfs)}): {filename}")
                    
                    try:
                        # Copy the file to downloads directory
                        shutil.copy2(source_path, target_path)
                        downloaded.append(target_path)
                    except Exception as e:
                        print(f"Error copying {filename}: {str(e)}")
                        continue
                        
            return downloaded, skipped
            
        except Exception as e:
            print(f"Error in search_and_download_pdf: {str(e)}")
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