import sqlite3
import os

def check_database():
    # Check pending_requests.db
    print("\nChecking pending_requests.db:")
    try:
        conn = sqlite3.connect(r'C:\SharedDB\pending_requests.db')
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print("\nTables in pending_requests.db:", [table[0] for table in tables])
        
        # Check pending_requests table
        print("\nPending Requests:")
        cursor.execute("SELECT * FROM pending_requests")
        requests = cursor.fetchall()
        for req in requests:
            print(f"Invoice: {req[0]}, Company: {req[1]}, Status: {req[4]}, PDF: {req[3]}")
            
        # Check sent_emails table
        print("\nSent Emails:")
        cursor.execute("SELECT * FROM sent_emails")
        sent = cursor.fetchall()
        for email in sent:
            print(f"Invoice: {email[0]}, Time: {email[1]}, Email: {email[2]}, Status: {email[3]}")
        
        conn.close()
    except Exception as e:
        print(f"Error with pending_requests.db: {str(e)}")
    
    # Check invoice_emails.db
    print("\nChecking invoice_emails.db:")
    try:
        conn = sqlite3.connect(r'C:\SharedDB\invoice_emails.db')
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print("\nTables in invoice_emails.db:", [table[0] for table in tables])
        
        # Check invoice_emails table
        print("\nInvoice Emails:")
        cursor.execute("SELECT * FROM invoice_emails")
        emails = cursor.fetchall()
        for email in emails:
            print(f"Invoice: {email[0]}, Email: {email[1]}, Added: {email[2]}")
        
        conn.close()
    except Exception as e:
        print(f"Error with invoice_emails.db: {str(e)}")

if __name__ == "__main__":
    check_database() 