from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import os
import shutil
from pdf_processor import PDFProcessor
from config import PDF_APP_URL, PDF_APP_USERNAME, PDF_APP_PASSWORD

class WebAutomation:
    def __init__(self, download_dir: str, test_mode=True):
        self.download_dir = download_dir
        self.test_mode = test_mode
        os.makedirs(download_dir, exist_ok=True)
        os.makedirs('processed', exist_ok=True)
        
    def search_and_download_pdf(self, target_week: tuple = None) -> list:
        """Search and download unprocessed PDFs"""
        if self.test_mode:
            return self._handle_test_mode_pdfs(target_week)
        else:
            # Real implementation would go here
            # This would interact with the actual web application
            return []
            
    def _handle_test_mode_pdfs(self, target_week: tuple = None) -> list:
        """Handle PDFs in test mode"""
        downloaded_pdfs = []
        
        # Check if pdf_samples directory exists
        if not os.path.exists('pdf_samples'):
            print("Error: pdf_samples directory not found!")
            print("Please create a pdf_samples directory and add sample PDFs.")
            return []
            
        # Process each PDF in the samples directory
        for pdf_file in os.listdir('pdf_samples'):
            if not pdf_file.endswith('.pdf'):
                continue
                
            source_path = os.path.join('pdf_samples', pdf_file)
            target_path = os.path.join(self.download_dir, pdf_file)
            
            try:
                # Skip if already processed
                if os.path.exists(os.path.join('processed', pdf_file)):
                    print(f"Skipping already processed file: {pdf_file}")
                    continue
                
                # Validate PDF and extract information
                if not PDFProcessor.validate_pdf(source_path):
                    print(f"Invalid PDF file: {pdf_file}")
                    continue
                    
                # Extract invoice period
                invoice_info = PDFProcessor.extract_invoice_info(source_path)
                if not invoice_info:
                    continue
                
                # If target week is specified, check if PDF falls within that week
                if target_week:
                    target_start, target_end = target_week
                    pdf_start = invoice_info['period_start']
                    pdf_end = invoice_info['period_end']
                    
                    # Skip if PDF period doesn't overlap with target week
                    if pdf_end < target_start or pdf_start > target_end:
                        continue
                
                # Copy PDF to downloads directory if not already there
                if not os.path.exists(target_path):
                    shutil.copy2(source_path, target_path)
                    downloaded_pdfs.append(target_path)
                    print(f"Copied PDF to: {target_path}")
                else:
                    downloaded_pdfs.append(target_path)
                    
            except Exception as e:
                print(f"Error processing {pdf_file}: {str(e)}")
                continue
                
        return downloaded_pdfs
        
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
        if not self.test_mode:
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
                
                return True
            except Exception as e:
                print(f"Login error: {str(e)}")
                return False
        return True
        
    def close(self):
        """Close the browser"""
        if not self.test_mode and hasattr(self, 'driver'):
            self.driver.quit() 