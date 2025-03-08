import sqlite3
import os
from datetime import datetime

def fix_database():
    db_path = "invoice_emails.db"
    downloads_folder = "downloads"
    pdf_samples_folder = "pdf_samples"  # Add pdf_samples folder

    try:
        # First, backup the existing database
        if os.path.exists(db_path):
            backup_path = db_path + ".backup"
            with open(db_path, 'rb') as src, open(backup_path, 'wb') as dst:
                dst.write(src.read())
            print(f"Created backup at {backup_path}")

        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Initialize database tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Companies (
                company_id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT UNIQUE NOT NULL,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Invoices (
                invoice_id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                invoice_number TEXT NOT NULL,
                pdf_path TEXT,
                period_start DATE,
                period_end DATE,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES Companies(company_id),
                UNIQUE(company_id, invoice_number)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS SentEmails (
                email_id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER,
                sent_to TEXT NOT NULL,
                sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (invoice_id) REFERENCES Invoices(invoice_id)
            )
        ''')

        # Track if we find a Rovex PDF
        found_rovex = False

        # Process PDFs in pdf_samples folder
        for filename in os.listdir(pdf_samples_folder):
            if filename.endswith('.pdf'):
                try:
                    # Parse filename
                    parts = filename.split('_')
                    # Get company name from first part
                    company_name = parts[0].replace('_', ' ').title()
                    
                    # Track if we find Rovex
                    if company_name.lower() == 'rovex':
                        found_rovex = True
                    
                    # Get dates from the last part (before .pdf)
                    date_part = parts[-1].replace('.pdf', '')
                    dates = date_part.split('-')
                    if len(dates) == 2:
                        period_start = datetime.strptime(dates[0], '%Y%m%d').strftime('%Y-%m-%d')
                        period_end = datetime.strptime(dates[1], '%Y%m%d').strftime('%Y-%m-%d')
                    else:
                        print(f"Invalid date format in {filename}")
                        continue
                    
                    # Generate an invoice number based on the start date
                    invoice_number = datetime.strptime(dates[0], '%Y%m%d').strftime('%Y%m%d')
                    
                    pdf_path = os.path.join(pdf_samples_folder, filename)

                    # First, add or get company
                    cursor.execute('''
                        INSERT OR IGNORE INTO Companies (company_name)
                        VALUES (?)
                    ''', (company_name,))
                    
                    cursor.execute('SELECT company_id FROM Companies WHERE company_name = ?', (company_name,))
                    company_id = cursor.fetchone()[0]

                    # Add invoice
                    cursor.execute('''
                        INSERT OR REPLACE INTO Invoices (
                            company_id, invoice_number, pdf_path, 
                            period_start, period_end, status
                        ) VALUES (?, ?, ?, ?, ?, 'pending')
                    ''', (company_id, invoice_number, pdf_path, period_start, period_end))
                    
                    print(f"Added {filename} to database")

                except Exception as e:
                    print(f"Error processing {filename}: {e}")
                    continue

        # Only add Rovex email if we found a Rovex PDF
        if found_rovex:
            cursor.execute('''
                UPDATE Companies 
                SET email = 'gumusluyigit@gmail.com'
                WHERE company_name = 'Rovex'
            ''')
            print("Added email for Rovex")

        conn.commit()
        print("\nFinished processing PDFs")

        # Verify the entries
        print("\nCurrent pending requests:")
        cursor.execute('''
            SELECT i.invoice_number, c.company_name, i.pdf_path, i.period_start, i.period_end, i.status
            FROM Invoices i
            JOIN Companies c ON i.company_id = c.company_id
            WHERE i.status = 'pending'
            ORDER BY c.company_name, i.invoice_number
        ''')
        results = cursor.fetchall()
        for row in results:
            print(f"\nRecord:")
            print(f"  Invoice Number: {row[0]}")
            print(f"  Company Name: {row[1]}")
            print(f"  PDF Path: {row[2]}")
            print(f"  Period Start: {row[3]}")
            print(f"  Period End: {row[4]}")
            print(f"  Status: {row[5]}")

        print("\nCompany emails:")
        cursor.execute('SELECT company_name, email FROM Companies WHERE email IS NOT NULL')
        results = cursor.fetchall()
        for row in results:
            print(f"  {row[0]}: {row[1]}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_database() 