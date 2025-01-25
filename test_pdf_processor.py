from pdf_processor import PDFProcessor
import os
import pdfplumber

def test_pdf_processing():
    # Get the sample PDF file
    sample_pdf = "annecto_tdm_20241202-20241208.pdf"
    
    if not os.path.exists(sample_pdf):
        print(f"Error: Sample PDF '{sample_pdf}' not found!")
        return
    
    print(f"\nTesting PDF processing for: {sample_pdf}")
    print("-" * 50)
    
    # Print raw PDF content
    print("\nRaw PDF Content:")
    print("-" * 50)
    with pdfplumber.open(sample_pdf) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            print(text)
            print("-" * 50)
    
    # Test date extraction from filename
    print("\n1. Testing date extraction from filename:")
    dates = PDFProcessor.extract_date_from_filename(sample_pdf)
    if dates:
        start_date, end_date = dates
        print(f"Start Date: {start_date.strftime('%Y-%m-%d')}")
        print(f"End Date: {end_date.strftime('%Y-%m-%d')}")
    else:
        print("Failed to extract dates from filename")
    
    # Test PDF validation
    print("\n2. Testing PDF validation:")
    is_valid = PDFProcessor.validate_pdf(sample_pdf)
    print(f"PDF is valid: {is_valid}")
    
    # Test invoice information extraction
    print("\n3. Testing invoice information extraction:")
    try:
        invoice_info = PDFProcessor.extract_invoice_info(sample_pdf)
        print("Extracted information:")
        for key, value in invoice_info.items():
            print(f"{key}: {value}")
    except Exception as e:
        print(f"Error extracting invoice info: {str(e)}")

if __name__ == "__main__":
    test_pdf_processing() 