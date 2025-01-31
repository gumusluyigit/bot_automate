import sqlite3
from pdf_processor import PDFProcessor
import os
from datetime import datetime

def add_invoice_numbers():
    """Add invoice numbers from PDFs to the database"""
    db_path = "invoice_emails.db"
    
    try:
        print(f"Connecting to database: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"\nAvailable tables: {[table[0] for table in tables]}")
        
        # Get table structure
        cursor.execute("PRAGMA table_info(invoice_emails)")
        columns = cursor.fetchall()
        print("\nTable structure:")
        for col in columns:
            print(f"- {col[1]} ({col[2]})")
        
        added_count = 0
        errors = []
        
        # Scan all PDFs in the pdf_samples directory
        samples_dir = os.path.join(os.getcwd(), 'pdf_samples')
        if os.path.exists(samples_dir):
            for filename in os.listdir(samples_dir):
                if not filename.lower().endswith('.pdf'):
                    continue
                    
                pdf_path = os.path.join(samples_dir, filename)
                print(f"\nProcessing PDF: {filename}")
                
                try:
                    # Extract invoice number from PDF
                    pdf_info = PDFProcessor.extract_invoice_info(pdf_path)
                    invoice_number = pdf_info['invoice_number']
                    company_name = pdf_info['company_name']
                    print(f"Extracted invoice number: {invoice_number}")
                    print(f"Company name: {company_name}")
                    
                    # Check if invoice number already exists
                    cursor.execute('SELECT invoice_number FROM invoice_emails WHERE invoice_number = ?', (invoice_number,))
                    existing = cursor.fetchone()
                    
                    if not existing:
                        # Add the invoice number to the database
                        cursor.execute('''
                            INSERT INTO invoice_emails (invoice_number, email_address, added_date)
                            VALUES (?, ?, ?)
                        ''', (invoice_number, f"{company_name.lower().replace(' ', '')}@example.com", datetime.now()))
                        
                        added_count += 1
                        print(f"Added invoice number {invoice_number} to database")
                    else:
                        print(f"Invoice number {invoice_number} already exists in database")
                
                except Exception as e:
                    error_msg = f"Error processing {filename}: {str(e)}"
                    print(f"Error: {error_msg}")
                    errors.append(error_msg)
        
        # Commit all changes
        print("\nCommitting changes to database...")
        conn.commit()
        
        # Print summary
        print(f"\nSummary:")
        print(f"Records added: {added_count}")
        print(f"Errors encountered: {len(errors)}")
        
        if errors:
            print("\nErrors:")
            for error in errors:
                print(f"- {error}")
    
    except Exception as e:
        print(f"Database error: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    add_invoice_numbers() 