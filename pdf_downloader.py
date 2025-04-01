import os
import logging
from typing import List, Optional, Dict
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import time
from datetime import datetime
import re
import hashlib
import pickle

# Load environment variables
load_dotenv()

# Get logger instance
logger = logging.getLogger('pdf_downloader')

class PDFDownloader:
    def __init__(self):
        self.login_url = "https://example.com"  # Base URL for the PDF source
        self.invoice_url = "https://example.com/pages/list_invoices.php"
        self.download_folder = "downloads"
        self.cache_folder = "cache"
        self.session = requests.Session()
        
        # Get credentials from environment variables
        self.username = os.getenv('BEOX_USERNAME')
        self.password = os.getenv('BEOX_PASSWORD')
        
        if not all([self.username, self.password]):
            raise ValueError("Missing credentials in environment variables. Please set BEOX_USERNAME and BEOX_PASSWORD")
        
        # Ensure download and cache directories exist
        os.makedirs(self.download_folder, exist_ok=True)
        os.makedirs(self.cache_folder, exist_ok=True)
        
        # Initialize cache
        self.pdf_links_cache = {}
        self.load_cache()
    
    def load_cache(self):
        """Load cached data if available"""
        cache_file = os.path.join(self.cache_folder, 'pdf_links_cache.pkl')
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'rb') as f:
                    self.pdf_links_cache = pickle.load(f)
                logger.info(f"Loaded {len(self.pdf_links_cache)} items from cache")
            except Exception as e:
                logger.error(f"Error loading cache: {str(e)}")
                self.pdf_links_cache = {}
    
    def save_cache(self):
        """Save cache to disk"""
        cache_file = os.path.join(self.cache_folder, 'pdf_links_cache.pkl')
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(self.pdf_links_cache, f)
            logger.info(f"Saved {len(self.pdf_links_cache)} items to cache")
        except Exception as e:
            logger.error(f"Error saving cache: {str(e)}")
    
    def parse_date_from_filename(self, filename: str) -> Optional[Dict]:
        """
        Parse dates from filename.
        Expected format: company_name_YYYYMMDD-YYYYMMDD.pdf
        """
        try:
            # Split filename into parts
            name_parts = filename.replace('.pdf', '').split('_')
            if len(name_parts) < 2:
                return None
            
            # Last part should contain the date range
            date_part = name_parts[-1]
            
            # Split date range
            start_str, end_str = date_part.split('-')
            
            # Parse dates
            start_date = datetime.strptime(start_str, '%Y%m%d')
            end_date = datetime.strptime(end_str, '%Y%m%d')
            
            return {
                'start_date': start_date,
                'end_date': end_date
            }
        except Exception as e:
            logger.error(f"Error parsing dates from filename {filename}: {str(e)}")
            return None
    
    def login(self) -> bool:
        """
        Log in to the website using stored credentials.
        Returns True if login successful, False otherwise.
        """
        try:
            # Simple payload with just username and password
            payload = {
                'Login': self.username,
                'Password': self.password
            }
            
            # Basic headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            logger.info(f"Attempting to log in with username: {self.username}")
            
            # First get the login page to establish session
            response = self.session.get(self.login_url, headers=headers)
            response.raise_for_status()
            
            # Submit login form
            response = self.session.post(self.login_url, data=payload, headers=headers, allow_redirects=True)
            response.raise_for_status()
            
            # Test if we can access the invoice page
            test_response = self.session.get(self.invoice_url)
            test_response.raise_for_status()
            
            # If we can get the invoice page and it contains PDF links, we're logged in
            if test_response.status_code == 200 and '.pdf' in test_response.text.lower():
                logger.info("Successfully logged in and accessed invoice page")
                return True
            
            logger.warning("Could not verify login success")
            return False
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Login failed due to network error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during login: {str(e)}")
            return False
    
    def get_pdf_links(self, week_start=None, week_end=None) -> List[Dict]:
        """
        Fetch and filter PDF links based on date range.
        Uses caching to avoid redundant network requests.
        """
        # Create a cache key based on the date range
        cache_key = f"pdf_links_{week_start}_{week_end}"
        
        # Check if we have cached results for this query
        if cache_key in self.pdf_links_cache:
            cached_data = self.pdf_links_cache[cache_key]
            cache_time = cached_data.get('timestamp', 0)
            # Use cache if it's less than 24 hours old (increased from 1 hour)
            if time.time() - cache_time < 86400:  # 24 hours in seconds
                logger.info(f"Using cached PDF links from {datetime.fromtimestamp(cache_time)}")
                return cached_data.get('data', [])
        
        try:
            # Ensure we're logged in
            if not self.login():
                logger.error("Failed to log in, cannot fetch PDF links")
                return []
                
            response = self.session.get(self.invoice_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            pdf_info_list = []

            logger.info("Searching for PDF links in the page...")
            pdf_links = soup.find_all('a', href=lambda href: href and href.lower().endswith('.pdf'))
            logger.info(f"Found {len(pdf_links)} PDF links")

            # Process all links at once to avoid redundant network requests
            for pdf_link in pdf_links:
                href = pdf_link['href']
                filename = os.path.basename(href)
                date_info = self.parse_date_from_filename(filename)

                if date_info:
                    # Filter PDFs by the provided date range
                    if week_start and week_end:
                        if not (date_info['end_date'] >= week_start and date_info['start_date'] <= week_end):
                            continue  # Skip if not in range

                    # Extract temporary company name from filename (will be updated later from PDF content)
                    name_parts = filename.replace('.pdf', '').split('_')
                    temp_company_name = '_'.join(name_parts[:-1]).replace('_', ' ').title()
                    
                    pdf_info_list.append({
                        'url': href,
                        'filename': filename,
                        'company_name': temp_company_name,  # Temporary name, will be updated from PDF
                        'start_date': date_info['start_date'],
                        'end_date': date_info['end_date']
                    })
            
            # Cache the results
            self.pdf_links_cache[cache_key] = {
                'timestamp': time.time(),
                'data': pdf_info_list
            }
            self.save_cache()
            
            logger.info(f"Total PDFs found and filtered: {len(pdf_info_list)}")
            return pdf_info_list
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch PDF links: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in get_pdf_links: {str(e)}")
            return []
    
    def download_pdf(self, pdf_info: Dict, max_retries: int = 3) -> Optional[str]:
        """
        Download a single PDF file with retry mechanism.
        Checks if file already exists before downloading.
        Args:
            pdf_info: Dictionary containing PDF information
            max_retries: Maximum number of retry attempts (default: 3)
        Returns:
            The path to the downloaded file if successful, None otherwise.
        """
        # Check if file already exists
        filepath = os.path.join(self.download_folder, pdf_info['filename'])
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            logger.info(f"PDF already exists: {filepath}")
            return filepath
            
        retries = 0
        while retries < max_retries:
            try:
                # Construct full URL if needed
                pdf_url = pdf_info['url']
                if not pdf_url.startswith('http'):
                    full_url = f"https://example.com{pdf_url}"
                else:
                    full_url = pdf_url
                
                logger.info(f"Downloading PDF: {full_url} (Attempt {retries + 1}/{max_retries})")
                
                response = self.session.get(full_url, stream=True)
                response.raise_for_status()
                
                # Download with progress tracking for large files
                total_size = int(response.headers.get('content-length', 0))
                block_size = 8192
                
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=block_size):
                        if chunk:
                            f.write(chunk)
                
                logger.info(f"Successfully downloaded: {filepath}")
                return filepath
                
            except requests.exceptions.RequestException as e:
                retries += 1
                if retries < max_retries:
                    logger.warning(f"Download attempt {retries} failed: {str(e)}. Retrying...")
                    time.sleep(2 ** retries)  # Exponential backoff
                else:
                    logger.error(f"Failed to download PDF after {max_retries} attempts: {str(e)}")
                    return None
            except IOError as e:
                logger.error(f"Failed to save PDF: {str(e)}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error downloading PDF: {str(e)}")
                return None
    
    def download_all_pdfs(self) -> List[Dict]:
        """
        Download all available PDF files.
        Returns a list of dictionaries containing PDF information.
        """
        if not self.login():
            logger.error("Cannot download PDFs - Login failed")
            return []
        
        pdf_info_list = self.get_pdf_links()
        if not pdf_info_list:
            logger.warning("No PDF links found to download")
            return []
        
        downloaded_files = []
        for pdf_info in pdf_info_list:
            if filepath := self.download_pdf(pdf_info):
                pdf_info['pdf_path'] = filepath
                downloaded_files.append(pdf_info)
        
        logger.info(f"Successfully downloaded {len(downloaded_files)} PDFs")
        return downloaded_files

def main():
    """
    Main function to demonstrate usage.
    """
    try:
        downloader = PDFDownloader()
        downloaded_files = downloader.download_all_pdfs()
        
        if downloaded_files:
            print(f"Successfully downloaded {len(downloaded_files)} PDFs:")
            for file in downloaded_files:
                print(f"- {file['filename']} ({file['company_name']}: {file['start_date']} - {file['end_date']})")
        else:
            print("No PDFs were downloaded")
            
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        logger.error(f"Main execution failed: {str(e)}")

if __name__ == "__main__":
    main() 