# Company Name Extraction Fix

## Problem
The system was not correctly extracting company names from PDF content. Instead, it was using the filename to determine the company name, which was less accurate.

## Solution
We identified that the company name in the PDFs appears on a line starting with "Customer", followed by the company name. The previous extraction method was looking for "Customer Account Code" on a single line, but in the actual PDFs, these are on separate lines.

### Changes Made:

1. **Updated the company name extraction in `pdf_processor.py`**:
   - Added a primary pattern to look for lines starting with "Customer" followed by the company name
   - Added multiple fallback patterns to increase the chances of finding the company name
   - Improved logging to track which pattern successfully extracted the company name
   - Added debug logging to see the actual text being extracted from PDFs

2. **Enhanced the `process_single_pdf` method**:
   - Added sample text extraction for debugging purposes
   - Improved logging when no company name is found in the PDF content

3. **Created testing tools**:
   - Added `extract_pdf_text.py` to extract and view the full text from PDFs
   - Created `test_pdf_extraction.py` to test company name extraction on all PDFs or specific PDFs

## Results
The system now correctly extracts company names from the PDF content. For example:
- From filename `acmetel_prm_20250217-20250223.pdf`, it now extracts "ACMETEL USA LLC"
- From filename `alltimetelecom_gold_20250217-20250223.pdf`, it now extracts "All Time Telecom"

This ensures that the correct company names are displayed throughout the system and stored in the database. 