import sqlite3
from pdf_processor import PDFProcessor
import os

def fix_invoice_numbers():
    """Fix incorrect invoice numbers in the database by re-reading them from PDFs"""
    db_path = "invoice_emails.db"
    
    try:
        print(f"Connecting to database: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all invoice numbers from the database
        print("\nFetching all invoice numbers from database...")
        cursor.execute('SELECT invoice_number, email_address FROM invoice_emails')
        db_records = cursor.fetchall()
        print(f"Found {len(db_records)} records in database")
        
        # Create a mapping of company names to invoice numbers from PDFs
        pdf_records = {}
        samples_dir = os.path.join(os.getcwd(), 'pdf_samples')
        if os.path.exists(samples_dir):
            for filename in os.listdir(samples_dir):
                if not filename.lower().endswith('.pdf'):
                    continue
                    
                pdf_path = os.path.join(samples_dir, filename)
                try:
                    pdf_info = PDFProcessor.extract_invoice_info(pdf_path)
                    invoice_number = pdf_info['invoice_number']
                    company_name = pdf_info['company_name'].lower().replace(' ', '')
                    pdf_records[company_name] = invoice_number
                except Exception as e:
                    print(f"Error processing {filename}: {str(e)}")
        
        # Check for discrepancies
        fixed_count = 0
        for db_invoice, email in db_records:
            company = email.split('@')[0]  # Extract company name from email
            if company in pdf_records:
                correct_invoice = pdf_records[company]
                if db_invoice != correct_invoice:
                    print(f"\nFound discrepancy for {company}:")
                    print(f"Database invoice number: {db_invoice}")
                    print(f"Correct invoice number: {correct_invoice}")
                    
                    # Update the invoice number
                    cursor.execute('''
                        UPDATE invoice_emails 
                        SET invoice_number = ?
                        WHERE invoice_number = ?
                    ''', (correct_invoice, db_invoice))
                    
                    # Update sent_emails if it exists
                    cursor.execute('''
                        UPDATE sent_emails 
                        SET invoice_number = ?
                        WHERE invoice_number = ?
                    ''', (correct_invoice, db_invoice))
                    
                    fixed_count += 1
                    print(f"Fixed invoice number: {db_invoice} -> {correct_invoice}")
        
        # Commit changes
        if fixed_count > 0:
            print("\nCommitting changes to database...")
            conn.commit()
        
        # Print summary
        print(f"\nSummary:")
        print(f"Total records checked: {len(db_records)}")
        print(f"Records fixed: {fixed_count}")
    
    except Exception as e:
        print(f"Database error: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    fix_invoice_numbers() 