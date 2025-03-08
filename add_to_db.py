import sqlite3
import os
from datetime import datetime

def add_pdfs_to_database():
    db_path = "invoice_emails.db"
    downloads_folder = "downloads"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Ensure the Companies and Invoices tables exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Companies (
                company_id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT UNIQUE NOT NULL,
                email TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Invoices (
                invoice_id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                invoice_number TEXT NOT NULL,
                pdf_path TEXT NOT NULL,
                period_start DATE,
                period_end DATE,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES Companies(company_id)
            )
        ''')
        conn.commit()

        # Process each PDF in the downloads folder
        for filename in os.listdir(downloads_folder):
            if filename.endswith('.pdf'):
                try:
                    # Parse filename
                    parts = filename.split('_')
                    if len(parts) >= 2:
                        # Handle company name with spaces
                        if 'Cli' in parts:
                            # Special handling for Unicall Cli
                            company_name = ' '.join(parts[:2]).title()  # Join "Unicall" and "Cli"
                            invoice_number = parts[2]  # Use the third part as invoice number
                        else:
                            company_name = parts[0].replace('_', ' ').title()
                            invoice_number = parts[1]
                        
                        # Default period if not in filename
                        period_start = '2025-01-01'
                        period_end = '2025-01-15'
                        
                        # Try to get period from filename if available
                        if len(parts) >= 4:
                            try:
                                # For Unicall Cli, use the correct parts
                                if 'Cli' in parts:
                                    period_start = datetime.strptime(parts[3], '%Y%m%d').strftime('%Y-%m-%d')
                                    period_end = datetime.strptime(parts[4].replace('.pdf', ''), '%Y%m%d').strftime('%Y-%m-%d')
                                else:
                                    period_start = datetime.strptime(parts[2], '%Y%m%d').strftime('%Y-%m-%d')
                                    period_end = datetime.strptime(parts[3].replace('.pdf', ''), '%Y%m%d').strftime('%Y-%m-%d')
                            except ValueError:
                                print(f"Using default period for {filename}")
                        
                        pdf_path = os.path.join(downloads_folder, filename)

                        # First, add or get company
                        cursor.execute('''
                            INSERT OR IGNORE INTO Companies (company_name)
                            VALUES (?)
                        ''', (company_name,))
                        
                        cursor.execute('SELECT company_id FROM Companies WHERE company_name = ?', 
                                     (company_name,))
                        company_id = cursor.fetchone()[0]

                        # Check if invoice already exists
                        cursor.execute('''
                            SELECT 1 FROM Invoices 
                            WHERE company_id = ? AND invoice_number = ?
                        ''', (company_id, invoice_number))
                        
                        if not cursor.fetchone():
                            # Add to Invoices
                            cursor.execute('''
                                INSERT INTO Invoices (
                                    company_id, invoice_number, pdf_path, 
                                    period_start, period_end, status
                                ) VALUES (?, ?, ?, ?, ?, 'pending')
                            ''', (company_id, invoice_number, pdf_path, period_start, period_end))
                            print(f"Added {filename} to database")
                        else:
                            print(f"Skipped {filename} - already exists in database")
                except Exception as e:
                    print(f"Error processing {filename}: {e}")
                    continue

        conn.commit()
        print("\nFinished processing PDFs")

        # Verify the entries
        print("\nCurrent pending requests:")
        cursor.execute('''
            SELECT i.invoice_number, c.company_name, i.status
            FROM Invoices i
            JOIN Companies c ON i.company_id = c.company_id
            WHERE i.status = 'pending'
        ''')
        for row in cursor.fetchall():
            print(f"Invoice: {row[0]}, Company: {row[1]}, Status: {row[2]}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    add_pdfs_to_database() 