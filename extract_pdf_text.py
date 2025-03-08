import sys
import pdfplumber

def extract_pdf_text(pdf_path):
    """Extract and print the full text from a PDF"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    print(f"\n--- PAGE {i+1} ---\n")
                    print(text)
                else:
                    print(f"\n--- PAGE {i+1} ---\n[No text extracted]")
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_pdf_text.py <pdf_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    print(f"Extracting text from: {pdf_path}")
    extract_pdf_text(pdf_path) 