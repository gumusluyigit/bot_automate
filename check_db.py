import sqlite3
import os

def check_database():
    db_path = "invoice_emails.db"
    if not os.path.exists(db_path):
        print(f"Database file {db_path} not found")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check Companies table
        print("\nChecking Companies table:")
        try:
            cursor.execute('''
                SELECT company_id, company_name, email
                FROM Companies
                WHERE company_name LIKE '%rovex%' 
                   OR company_name LIKE '%ROVEX%'
                   OR company_name LIKE '%Rovex%'
            ''')
            results = cursor.fetchall()
            if results:
                for row in results:
                    print(f"\nRecord:")
                    print(f"  Company ID: {row[0]}")
                    print(f"  Company Name: {row[1]}")
                    print(f"  Email: {row[2]}")
            else:
                print("No matching records found in Companies")
        except sqlite3.OperationalError as e:
            print(f"Error accessing Companies table: {e}")

        # Check Invoices table
        print("\nChecking Invoices table:")
        try:
            cursor.execute('''
                SELECT i.invoice_id, i.company_id, i.invoice_number, 
                       i.pdf_path, i.period_start, i.period_end, i.status,
                       c.company_name
                FROM Invoices i
                JOIN Companies c ON i.company_id = c.company_id
                WHERE c.company_name LIKE '%rovex%'
                   OR c.company_name LIKE '%ROVEX%'
                   OR c.company_name LIKE '%Rovex%'
                   OR i.invoice_number IN ('44155', '44163')
            ''')
            results = cursor.fetchall()
            if results:
                for row in results:
                    print(f"\nRecord:")
                    print(f"  Invoice ID: {row[0]}")
                    print(f"  Company ID: {row[1]}")
                    print(f"  Invoice Number: {row[2]}")
                    print(f"  PDF Path: {row[3]}")
                    print(f"  Period Start: {row[4]}")
                    print(f"  Period End: {row[5]}")
                    print(f"  Status: {row[6]}")
                    print(f"  Company Name: {row[7]}")
            else:
                print("No matching records found in Invoices")
        except sqlite3.OperationalError as e:
            print(f"Error accessing Invoices table: {e}")

        # Check all pending invoices
        print("\nAll pending invoices:")
        try:
            cursor.execute('''
                SELECT i.invoice_id, c.company_name, i.invoice_number, 
                       i.pdf_path, i.period_start, i.period_end, i.status
                FROM Invoices i
                JOIN Companies c ON i.company_id = c.company_id
                WHERE i.status = 'pending'
                ORDER BY i.created_at DESC
            ''')
            results = cursor.fetchall()
            if results:
                for row in results:
                    print(f"\nRecord:")
                    print(f"  Invoice ID: {row[0]}")
                    print(f"  Company Name: {row[1]}")
                    print(f"  Invoice Number: {row[2]}")
                    print(f"  PDF Path: {row[3]}")
                    print(f"  Period Start: {row[4]}")
                    print(f"  Period End: {row[5]}")
                    print(f"  Status: {row[6]}")
            else:
                print("No pending invoices found")
        except sqlite3.OperationalError as e:
            print(f"Error accessing Invoices table: {e}")

        # Check SentEmails table
        print("\nChecking SentEmails table:")
        try:
            cursor.execute('''
                SELECT se.email_id, se.invoice_id, se.sent_to, se.sent_date,
                       c.company_name, i.invoice_number
                FROM SentEmails se
                JOIN Invoices i ON se.invoice_id = i.invoice_id
                JOIN Companies c ON i.company_id = c.company_id
                WHERE c.company_name LIKE '%rovex%'
                   OR c.company_name LIKE '%ROVEX%'
                   OR c.company_name LIKE '%Rovex%'
                   OR i.invoice_number IN ('44155', '44163')
            ''')
            results = cursor.fetchall()
            if results:
                for row in results:
                    print(f"\nRecord:")
                    print(f"  Email ID: {row[0]}")
                    print(f"  Invoice ID: {row[1]}")
                    print(f"  Sent To: {row[2]}")
                    print(f"  Sent Date: {row[3]}")
                    print(f"  Company Name: {row[4]}")
                    print(f"  Invoice Number: {row[5]}")
            else:
                print("No matching records found in SentEmails")
        except sqlite3.OperationalError as e:
            print(f"Error accessing SentEmails table: {e}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")

def check_invoice_amount(invoice_number):
    """Check amount for a specific invoice"""
    db_path = "invoice_emails.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT i.invoice_number, i.amount, i.currency, c.company_name
            FROM Invoices i
            JOIN Companies c ON i.company_id = c.company_id
            WHERE i.invoice_number = ?
        ''', (invoice_number,))
        
        result = cursor.fetchone()
        if result:
            print(f"\nInvoice {result[0]}:")
            print(f"  Amount: {result[1]} {result[2]}")
            print(f"  Company: {result[3]}")
        else:
            print(f"\nInvoice {invoice_number} not found")
            
        conn.close()
    except Exception as e:
        print(f"Error checking invoice: {e}")

if __name__ == "__main__":
    check_database()
    check_invoice_amount('44416') 