from pdf_processor import PDFProcessor
import os

def test_pdf_processing():
    # Sample PDF file path
    sample_pdf = "annecto_tdm_20241202-20241208.pdf"
    
    print(f"\nTesting PDF Processing for {sample_pdf}")
    print("-" * 50)
    
    # Test date extraction from filename
    print("\n1. Testing date extraction from filename:")
    dates = PDFProcessor.extract_date_from_filename(sample_pdf)
    if dates:
        start_date, end_date = dates
        print(f"✓ Start date: {start_date.strftime('%Y-%m-%d')}")
        print(f"✓ End date: {end_date.strftime('%Y-%m-%d')}")
    else:
        print("✗ Failed to extract dates from filename")
    
    # Test PDF validation
    print("\n2. Testing PDF validation:")
    if PDFProcessor.validate_pdf(sample_pdf):
        print("✓ PDF is valid and readable")
    else:
        print("✗ PDF validation failed")
    
    # Test invoice information extraction
    print("\n3. Testing invoice information extraction:")
    try:
        invoice_info = PDFProcessor.extract_invoice_info(sample_pdf)
        print("Invoice information extracted:")
        for key, value in invoice_info.items():
            print(f"✓ {key}: {value}")
    except Exception as e:
        print(f"✗ Failed to extract invoice information: {str(e)}")

if __name__ == "__main__":
    test_pdf_processing() 