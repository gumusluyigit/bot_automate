import sqlite3
import os
from datetime import datetime
import shutil
from difflib import get_close_matches

def backup_database(db_path="invoice_emails.db"):
    """Create a backup of the existing database"""
    if os.path.exists(db_path):
        backup_path = f"{db_path}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.backup"
        shutil.copy2(db_path, backup_path)
        print(f"Created backup at {backup_path}")
    
def create_new_schema(cursor):
    """Create the new database schema"""
    # Create Companies table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Companies (
            company_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT UNIQUE NOT NULL,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create Invoices table
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
    
    # Create SentEmails table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS SentEmails (
            email_id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER,
            sent_to TEXT NOT NULL,
            sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (invoice_id) REFERENCES Invoices(invoice_id)
        )
    ''')

def migrate_existing_data(cursor):
    """Migrate data from old tables to new schema"""
    # First, get all existing tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = [table[0] for table in cursor.fetchall()]
    
    if 'pending_requests' in existing_tables:
        print("Migrating pending requests...")
        # Get all unique companies from pending_requests
        cursor.execute('SELECT DISTINCT company_name FROM pending_requests')
        companies = cursor.fetchall()
        
        # Insert companies into new Companies table
        for company in companies:
            company_name = company[0]
            # Check if we have an email for this company
            cursor.execute('SELECT email FROM company_emails WHERE company_name = ?', (company_name,))
            email_result = cursor.fetchone()
            email = email_result[0] if email_result else None
            
            cursor.execute('''
                INSERT OR IGNORE INTO Companies (company_name, email)
                VALUES (?, ?)
            ''', (company_name, email))
        
        # Migrate pending requests to Invoices
        cursor.execute('''
            SELECT pr.invoice_number, pr.company_name, pr.pdf_path, 
                   pr.period_start, pr.period_end, pr.status
            FROM pending_requests pr
        ''')
        pending_requests = cursor.fetchall()
        
        for request in pending_requests:
            invoice_number, company_name, pdf_path, period_start, period_end, status = request
            
            # Get company_id
            cursor.execute('SELECT company_id FROM Companies WHERE company_name = ?', (company_name,))
            company_id = cursor.fetchone()[0]
            
            # Insert into Invoices
            cursor.execute('''
                INSERT OR IGNORE INTO Invoices 
                (company_id, invoice_number, pdf_path, period_start, period_end, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (company_id, invoice_number, pdf_path, period_start, period_end, status))
    
    if 'sent_emails' in existing_tables:
        print("Migrating sent emails...")
        cursor.execute('''
            SELECT se.invoice_number, se.email, se.sent_time
            FROM sent_emails se
        ''')
        sent_emails = cursor.fetchall()
        
        for sent_email in sent_emails:
            invoice_number, email, sent_time = sent_email
            
            # Get invoice_id from Invoices table
            cursor.execute('''
                SELECT invoice_id FROM Invoices WHERE invoice_number = ?
            ''', (invoice_number,))
            result = cursor.fetchone()
            if result:
                invoice_id = result[0]
                cursor.execute('''
                    INSERT INTO SentEmails (invoice_id, sent_to, sent_date)
                    VALUES (?, ?, ?)
                ''', (invoice_id, email, sent_time))

def drop_old_tables(cursor):
    """Drop the old tables after successful migration"""
    tables_to_drop = ['pending_requests', 'sent_emails', 'company_emails']
    for table in tables_to_drop:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")

def verify_migration(cursor):
    """Verify the migration was successful"""
    print("\nVerifying migration...")
    
    print("\nCompanies:")
    cursor.execute('SELECT * FROM Companies')
    companies = cursor.fetchall()
    for company in companies:
        print(f"ID: {company[0]}, Name: {company[1]}, Email: {company[2]}")
    
    print("\nInvoices:")
    cursor.execute('''
        SELECT i.invoice_id, c.company_name, i.invoice_number, i.status
        FROM Invoices i
        JOIN Companies c ON i.company_id = c.company_id
    ''')
    invoices = cursor.fetchall()
    for invoice in invoices:
        print(f"ID: {invoice[0]}, Company: {invoice[1]}, Invoice #: {invoice[2]}, Status: {invoice[3]}")
    
    print("\nSent Emails:")
    cursor.execute('''
        SELECT se.email_id, c.company_name, i.invoice_number, se.sent_to, se.sent_date
        FROM SentEmails se
        JOIN Invoices i ON se.invoice_id = i.invoice_id
        JOIN Companies c ON i.company_id = c.company_id
    ''')
    sent_emails = cursor.fetchall()
    for email in sent_emails:
        print(f"ID: {email[0]}, Company: {email[1]}, Invoice #: {email[2]}, Sent To: {email[3]}, Date: {email[4]}")

def migrate_database():
    """Main migration function"""
    db_path = "invoice_emails.db"
    
    try:
        # Backup existing database
        backup_database(db_path)
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create new schema
        print("Creating new schema...")
        create_new_schema(cursor)
        
        # Migrate existing data
        print("Migrating existing data...")
        migrate_existing_data(cursor)
        
        # Verify migration
        verify_migration(cursor)
        
        # If everything is successful, drop old tables
        print("\nDropping old tables...")
        drop_old_tables(cursor)
        
        conn.commit()
        print("\nMigration completed successfully!")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    migrate_database() 