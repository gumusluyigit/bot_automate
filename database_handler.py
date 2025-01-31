import sqlite3
from datetime import datetime
import os

class DatabaseHandler:
    def __init__(self, db_path="pending_requests.db"):
        """Initialize database connection"""
        self.db_path = db_path
        self.initialize_database()
        
    def initialize_database(self):
        """Create database and tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create pending_requests table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pending_requests (
                    invoice_number TEXT PRIMARY KEY,
                    company_name TEXT,
                    request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    pdf_path TEXT,
                    status TEXT DEFAULT 'pending',
                    email TEXT NULL,
                    period_start DATE,
                    period_end DATE
                )
            ''')
            
            # Create sent_emails table to track history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sent_emails (
                    invoice_number TEXT,
                    sent_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    email TEXT,
                    status TEXT,
                    error_message TEXT NULL
                )
            ''')
            
            conn.commit()
            
    def add_pending_request(self, invoice_number, company_name, pdf_path, period_start=None, period_end=None):
        """Add a new pending request"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO pending_requests 
                    (invoice_number, company_name, pdf_path, period_start, period_end)
                    VALUES (?, ?, ?, ?, ?)
                ''', (invoice_number, company_name, pdf_path, period_start, period_end))
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Error adding pending request: {e}")
            return False
            
    def get_pending_requests(self):
        """Get all pending requests"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT invoice_number, company_name, request_time, pdf_path, status, email,
                           period_start, period_end
                    FROM pending_requests
                    WHERE status = 'pending'
                    ORDER BY request_time DESC
                ''')
                return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error getting pending requests: {e}")
            return []
            
    def update_email(self, invoice_number, email):
        """Update email for a pending request"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE pending_requests
                    SET email = ?, status = 'email_added'
                    WHERE invoice_number = ?
                ''', (email, invoice_number))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Error updating email: {e}")
            return False
            
    def mark_as_sent(self, invoice_number, email, status="sent", error_message=None):
        """Mark a request as sent and move to history"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Add to sent_emails history
                cursor.execute('''
                    INSERT INTO sent_emails (invoice_number, email, status, error_message)
                    VALUES (?, ?, ?, ?)
                ''', (invoice_number, email, status, error_message))
                
                # Update status in pending_requests
                cursor.execute('''
                    UPDATE pending_requests
                    SET status = ?
                    WHERE invoice_number = ?
                ''', (status, invoice_number))
                
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Error marking request as sent: {e}")
            return False
            
    def is_invoice_pending(self, invoice_number):
        """Check if an invoice is already in pending requests"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) FROM pending_requests
                    WHERE invoice_number = ? AND status = 'pending'
                ''', (invoice_number,))
                count = cursor.fetchone()[0]
                return count > 0
        except sqlite3.Error as e:
            print(f"Error checking invoice status: {e}")
            return False
            
    def get_email_history(self, invoice_number=None):
        """Get email sending history for an invoice or all invoices"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                if invoice_number:
                    cursor.execute('''
                        SELECT invoice_number, sent_time, email, status, error_message
                        FROM sent_emails
                        WHERE invoice_number = ?
                        ORDER BY sent_time DESC
                    ''', (invoice_number,))
                else:
                    cursor.execute('''
                        SELECT invoice_number, sent_time, email, status, error_message
                        FROM sent_emails
                        ORDER BY sent_time DESC
                    ''')
                return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error getting email history: {e}")
            return []
            
    def clear_all_tables(self):
        """Clear all tables in the database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Clear pending_requests table
            cursor.execute('DELETE FROM pending_requests')
            
            # Clear sent_emails table
            cursor.execute('DELETE FROM sent_emails')
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error clearing tables: {str(e)}")
            return False 