import sqlite3
from datetime import datetime

def init_db():
    """Initialize the database"""
    conn = sqlite3.connect('invoice_emails.db')
    cursor = conn.cursor()
    
    # Create invoice_emails table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoice_emails (
            invoice_number TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            company_name TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create sent_emails table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_emails (
            invoice_number TEXT PRIMARY KEY,
            email_address TEXT NOT NULL,
            sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            pdf_path TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def get_email_by_invoice(invoice_number: str) -> str:
    """Get email address for an invoice number"""
    conn = sqlite3.connect('invoice_emails.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT email FROM invoice_emails WHERE invoice_number = ?', (invoice_number,))
    result = cursor.fetchone()
    
    conn.close()
    return result[0] if result else None

def add_invoice_email(invoice_number: str, email: str, company_name: str = None):
    """Add or update invoice-email mapping"""
    conn = sqlite3.connect('invoice_emails.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO invoice_emails (invoice_number, email, company_name, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    ''', (invoice_number, email, company_name))
    
    conn.commit()
    conn.close()

def clear_db():
    """Clear all records from the database"""
    conn = sqlite3.connect('invoice_emails.db')
    cursor = conn.cursor()
    
    # Clear both tables
    cursor.execute('DELETE FROM invoice_emails')
    cursor.execute('DELETE FROM sent_emails')
    
    conn.commit()
    conn.close() 