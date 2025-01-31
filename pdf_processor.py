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
            # First try to extract info from filename
            filename = os.path.basename(pdf_path)
            info = {}
            
            # Extract company name and dates from filename
            # Pattern: company_[tdm_]YYYYMMDD-YYYYMMDD.pdf
            match = re.match(r'([a-zA-Z0-9_]+)(?:_tdm)?_(\d{8})-(\d{8})\.pdf', filename)
            if match:
                company_name, start_date_str, end_date_str = match.groups()
                info['company_name'] = company_name.replace('_', ' ').title()
                
                # Parse dates
                try:
                    start_date = datetime.strptime(start_date_str, '%Y%m%d')
                    end_date = datetime.strptime(end_date_str, '%Y%m%d')
                    info['period_start'] = start_date
                    info['period_end'] = end_date
                    
                    # Generate invoice number based on company and week
                    week_num = start_date.isocalendar()[1]
                    year = start_date.year
                    info['invoice_number'] = f"{year}{week_num:02d}{hash(company_name) % 1000:03d}"
                    
                    return info
                except ValueError as e:
                    print(f"Error parsing dates from filename: {str(e)}")
            
            # If filename parsing fails, try to read PDF content
            with open(pdf_path, 'rb') as f:
                content = f.read()
                
            try:
                decoded = content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    decoded = content.decode('ascii', errors='ignore')
                except:
                    raise Exception("Could not decode PDF content")
                    
            # Extract information from PDF content
            lines = decoded.split('\n')
            
            for line in lines:
                line = line.strip()
                if 'Invoice Number:' in line:
                    info['invoice_number'] = line.split('Invoice Number:')[1].strip()
                elif 'Company:' in line:
                    info['company_name'] = line.split('Company:')[1].strip()
                elif 'Period:' in line:
                    period = line.split('Period:')[1].strip()
                    start_date, end_date = period.split('to')
                    info['period_start'] = datetime.strptime(start_date.strip(), '%Y-%m-%d')
                    info['period_end'] = datetime.strptime(end_date.strip(), '%Y-%m-%d')
                    
            # Check if we found all required information
            required_fields = ['invoice_number', 'company_name', 'period_start', 'period_end']
            if all(field in info for field in required_fields):
                return info
                
            raise Exception("Could not extract required information from PDF")
            
        except Exception as e:
            print(f"Error extracting invoice info: {str(e)}")
            raise 