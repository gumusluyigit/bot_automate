from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from datetime import datetime
import os
import time
import shutil
from config import PDF_APP_URL, PDF_APP_USERNAME, PDF_APP_PASSWORD
from pdf_processor import PDFProcessor

class WebAutomation:
    def __init__(self, download_dir: str, test_mode=True):
        self.download_dir = download_dir
        self.driver = None
        self.test_mode = test_mode
        
    def setup_driver(self):
        """Setup Edge WebDriver with custom options"""
        if self.test_mode:
            return True
            
        edge_options = Options()
        edge_options.add_experimental_option('prefs', {
            'download.default_directory': self.download_dir,
            'download.prompt_for_download': False,
            'plugins.always_open_pdf_externally': True  # Download PDF instead of opening in browser
        })
        
        service = Service(EdgeChromiumDriverManager().install())
        self.driver = webdriver.Edge(service=service, options=edge_options)
        
    def login(self):
        """Login to the PDF application"""
        if self.test_mode:
            print("[TEST MODE] Successfully logged in to the application")
            return True
            
        try:
            self.driver.get(PDF_APP_URL)
            
            # Wait for login form and fill credentials
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            password_field = self.driver.find_element(By.NAME, "password")
            
            username_field.send_keys(PDF_APP_USERNAME)
            password_field.send_keys(PDF_APP_PASSWORD)
            
            # Find and click login button
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()
            
            # Wait for successful login
            WebDriverWait(self.driver, 10).until(
                EC.url_changes(PDF_APP_URL)
            )
            return True
        except TimeoutException:
            print("Login failed: Timeout waiting for elements")
            return False
        except Exception as e:
            print(f"Login failed: {str(e)}")
            return False
    
    def get_unprocessed_pdfs(self) -> list:
        """Get list of unprocessed PDFs from the previous week"""
        if self.test_mode:
            if not os.path.exists("pdf_samples"):
                print("[TEST MODE] pdf_samples directory not found!")
                print("[TEST MODE] Please create a pdf_samples directory and add your sample PDFs")
                return []
            
            unprocessed_pdfs = []
            processed_list = self.load_processed_pdfs()
            
            # Look through all PDFs in the samples directory
            for filename in os.listdir("pdf_samples"):
                if filename.endswith(".pdf"):
                    sample_pdf = os.path.join("pdf_samples", filename)
                    # Skip if already processed
                    if sample_pdf in processed_list:
                        continue
                        
                    # Copy to downloads directory
                    target_path = os.path.join(self.download_dir, filename)
                    shutil.copy2(sample_pdf, target_path)
                    print(f"[TEST MODE] Found unprocessed PDF: {filename}")
                    unprocessed_pdfs.append(target_path)
            
            if not unprocessed_pdfs:
                print("[TEST MODE] No unprocessed PDFs found")
            
            return unprocessed_pdfs
        
        # TODO: Implement real web automation to get PDFs
        return []
        
    def load_processed_pdfs(self) -> set:
        """Load list of already processed PDFs"""
        processed_file = "processed_pdfs.txt"
        if os.path.exists(processed_file):
            with open(processed_file, 'r') as f:
                return set(line.strip() for line in f)
        return set()
        
    def mark_as_processed(self, pdf_path: str):
        """Mark a PDF as processed"""
        with open("processed_pdfs.txt", 'a') as f:
            f.write(f"{pdf_path}\n")
    
    def search_and_download_pdf(self, date_str: str = None) -> list:
        """
        Get all unprocessed PDFs. If date_str is provided, filter by that week.
        Returns a list of PDF paths.
        """
        pdfs = self.get_unprocessed_pdfs()
        
        if date_str and pdfs:
            # Filter PDFs by date if specified
            filtered_pdfs = []
            for pdf_path in pdfs:
                filename = os.path.basename(pdf_path)
                sample_dates = PDFProcessor.extract_date_from_filename(filename)
                if sample_dates:
                    pdf_date_str = f"{sample_dates[0].strftime('%Y%m%d')}-{sample_dates[1].strftime('%Y%m%d')}"
                    if pdf_date_str == date_str:
                        filtered_pdfs.append(pdf_path)
            return filtered_pdfs
            
        return pdfs
    
    def close(self):
        """Close the browser"""
        if not self.test_mode and self.driver:
            self.driver.quit()
            self.driver = None 