import sqlite3
from datetime import datetime
import os
from typing import Optional, Dict, Any
import logging

# Configure logging
logger = logging.getLogger(__name__)

class DatabaseHandler:
    def __init__(self, db_path="pending_requests.db"):
        """Initialize database connection"""
        self.db_path = db_path
        self.initialize_database()  # Only initialize if needed, don't recreate
        
    def recreate_database(self):
        """Recreate the database from scratch. Use this method with caution as it will delete all data."""
        # If database exists, delete it
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
                print(f"Deleted existing database: {self.db_path}")
            except Exception as e:
                print(f"Error deleting database: {e}")
        
        # Create new database
        self.initialize_database()
        print(f"Created new database: {self.db_path}")
        
    def initialize_database(self):
        """Create database and tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create pending_requests table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pending_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_number TEXT NOT NULL,
                    company_name TEXT NOT NULL,
                    pdf_path TEXT NOT NULL,
                    period_start DATE,
                    period_end DATE,
                    status TEXT DEFAULT 'pending',
                    request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sent_to TEXT,
                    sent_at TIMESTAMP,
                    display_invoice_number TEXT
                )
            ''')
            
            # Create company_emails table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS company_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_name TEXT UNIQUE NOT NULL,
                    email TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create chat_history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    topic TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create chat_messages table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chat_id) REFERENCES chat_history(id)
                )
            ''')
            
            # Create transactions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_name TEXT NOT NULL,
                    invoice_number TEXT NOT NULL,
                    amount DECIMAL(10,2),
                    transaction_date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (company_name) REFERENCES company_emails(company_name)
                )
            ''')
            
            # Create sent_emails table to track history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sent_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_number TEXT,
                    company_name TEXT,
                    sent_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    email TEXT,
                    status TEXT,
                    error_message TEXT NULL
                )
            ''')
            
            # Add company_name column to sent_emails if it doesn't exist
            try:
                cursor.execute('SELECT company_name FROM sent_emails LIMIT 1')
            except sqlite3.OperationalError:
                cursor.execute('ALTER TABLE sent_emails ADD COLUMN company_name TEXT')
            
            # Create indexes for faster lookups
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_invoice_number ON pending_requests(invoice_number)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_company_name ON company_emails(company_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sent_invoice ON sent_emails(invoice_number)')
            
            conn.commit()
            print(f"Database initialized at: {self.db_path}")

    def get_company_info(self, company_name):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get the latest transaction and total count
            cursor.execute('''
                SELECT 
                    MAX(transaction_date) as last_transaction_date,
                    COUNT(*) as total_transactions
                FROM transactions 
                WHERE company_name LIKE ?
            ''', (f'%{company_name}%',))
            
            result = cursor.fetchone()
            
            if result and result[0]:
                return {
                    'last_transaction_date': result[0],
                    'total_transactions': result[1]
                }
            return None

    def get_company_email(self, company_name):
        """Get email address for a company"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT email FROM company_emails WHERE company_name LIKE ?', (f'%{company_name}%',))
                result = cursor.fetchone()
                return result[0] if result else None
        except sqlite3.Error as e:
            print(f"Error getting company email: {e}")
            return None

    def add_company_email(self, company_name, email):
        """Add or update company email"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO company_emails (company_name, email)
                    VALUES (?, ?)
                ''', (company_name, email))
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Error adding company email: {e}")
            return False

    def add_pending_request(self, invoice_number, company_name, pdf_path, period_start=None, period_end=None):
        """Add a new pending request"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO pending_requests (invoice_number, company_name, pdf_path, period_start, period_end)
                    VALUES (?, ?, ?, ?, ?)
                ''', (invoice_number, company_name, pdf_path, period_start, period_end))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error adding pending request: {e}")
            return False
            
    def get_pending_requests(self):
        """Get all pending requests"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT invoice_number, company_name, pdf_path, period_start, period_end, request_time
                    FROM pending_requests
                    WHERE status = 'pending'
                    AND invoice_number NOT IN (
                        SELECT invoice_number 
                        FROM sent_emails 
                        WHERE status = 'sent'
                    )
                    ORDER BY request_time DESC
                ''')
                columns = ['invoice_number', 'company_name', 'pdf_path', 'period_start', 'period_end', 'created_at']
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                logger.info(f"Found {len(results)} pending requests")
                return results
        except sqlite3.Error as e:
            logger.error(f"Error getting pending requests: {e}")
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
                
                # Get company name for this invoice
                cursor.execute('''
                    SELECT company_name FROM pending_requests
                    WHERE invoice_number = ?
                ''', (invoice_number,))
                result = cursor.fetchone()
                if result:
                    company_name = result[0]
                    # Store the company-email association
                    cursor.execute('''
                        INSERT OR REPLACE INTO company_emails (company_name, email)
                        VALUES (?, ?)
                    ''', (company_name, email))
                
                    # Add to sent_emails history with company_name
                    cursor.execute('''
                        INSERT INTO sent_emails (invoice_number, email, company_name, status, error_message)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (invoice_number, email, company_name, status, error_message))
                    
                    # Delete from pending_requests
                    cursor.execute('''
                        DELETE FROM pending_requests
                        WHERE invoice_number = ?
                    ''', (invoice_number,))
                    
                    conn.commit()
                    return True
                return False
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
            
            # Clear company_emails table
            cursor.execute('DELETE FROM company_emails')
            
            # Clear transactions table
            cursor.execute('DELETE FROM transactions')
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error clearing tables: {str(e)}")
            return False

    def get_request_by_invoice(self, invoice_number):
        """Get request details by invoice number"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT invoice_number, company_name, pdf_path, period_start, period_end, status, sent_to, sent_at
                    FROM pending_requests
                    WHERE invoice_number = ?
                    AND status = 'pending'
                ''', (invoice_number,))
                
                row = cursor.fetchone()
                if row:
                    columns = ['invoice_number', 'company_name', 'pdf_path', 'period_start', 'period_end', 'status', 'sent_to', 'sent_at']
                    return dict(zip(columns, row))
                return None
        except sqlite3.Error as e:
            print(f"Error getting request by invoice: {e}")
            return None
            
    def get_recent_requests(self, limit: int = 5) -> list:
        """Get recent pending requests"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT invoice_number, company_name, status, request_time, sent_to, sent_at
                FROM pending_requests
                WHERE status = 'pending'
                AND (sent_to IS NULL OR sent_at IS NULL)
                AND invoice_number NOT IN (
                    SELECT invoice_number 
                    FROM sent_emails 
                    WHERE status = 'sent'
                )
                ORDER BY request_time DESC
                LIMIT ?
            ''', (limit,))
            
            columns = ['invoice_number', 'company_name', 'status', 'created_at', 'sent_to', 'sent_at']
            recent = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            conn.close()
            return recent
        except Exception as e:
            print(f"Error getting recent requests: {str(e)}")
            return []

    def get_company_name_by_invoice(self, invoice_number):
        """Get company name for an invoice number"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                print(f"Looking up company name for invoice: {invoice_number}")  # Debug print
                
                # First check pending_requests
                cursor.execute('''
                    SELECT company_name
                    FROM pending_requests
                    WHERE invoice_number = ?
                ''', (invoice_number,))
                result = cursor.fetchone()
                if result:
                    print(f"Found company name in pending_requests: {result[0]}")  # Debug print
                    return result[0]
                
                # If not found, check invoice_details
                cursor.execute('''
                    SELECT company_name
                    FROM invoice_details
                    WHERE invoice_number = ?
                ''', (invoice_number,))
                result = cursor.fetchone()
                if result:
                    print(f"Found company name in invoice_details: {result[0]}")  # Debug print
                    return result[0]
                
                print(f"No company name found for invoice: {invoice_number}")  # Debug print
                return None
                
        except sqlite3.Error as e:
            print(f"Error getting company name: {e}")
            return None

    def update_company_email(self, company_name, new_email, old_email=None):
        """Update email address for a company and log the change"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get current email if old_email not provided
                if not old_email:
                    cursor.execute('SELECT email FROM company_emails WHERE company_name = ?', (company_name,))
                    result = cursor.fetchone()
                    if result:
                        old_email = result[0]
                
                # Update email in company_emails table
                cursor.execute('''
                    INSERT OR REPLACE INTO company_emails (company_name, email)
                    VALUES (?, ?)
                ''', (company_name, new_email))
                
                # Add a record in sent_emails to track the change
                if old_email:
                    cursor.execute('''
                        INSERT INTO sent_emails (invoice_number, email, company_name, status, error_message)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        None,  # No specific invoice
                        new_email,
                        company_name,
                        'email_updated',
                        f'Email updated from {old_email} to {new_email}'
                    ))
                
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Error updating company email: {e}")
            return False

    def get_company_email_history(self, company_name):
        """Get email history for a company"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get current email
                cursor.execute('''
                    SELECT email, created_at 
                    FROM company_emails 
                    WHERE company_name = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (company_name,))
                current = cursor.fetchone()
                
                # Get email update history
                cursor.execute('''
                    SELECT email, sent_time, status, error_message
                    FROM sent_emails
                    WHERE company_name = ? 
                    AND (status = 'email_updated' OR status = 'sent')
                    ORDER BY sent_time DESC
                ''', (company_name,))
                history = cursor.fetchall()
                
                result = {
                    'current_email': current[0] if current else None,
                    'last_updated': current[1] if current else None,
                    'history': [{
                        'email': row[0],
                        'timestamp': row[1],
                        'message': f"Email {'updated' if row[2] == 'email_updated' else 'used'}: {row[0]}"
                    } for row in history]
                }
                
                return result
        except sqlite3.Error as e:
            print(f"Error getting company email history: {e}")
            return None

    def get_all_companies(self):
        """Get all companies and their current emails"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT company_name, email, created_at
                    FROM company_emails
                    ORDER BY company_name
                ''')
                
                return [
                    {
                        'company_name': row[0],
                        'email': row[1],
                        'created_at': row[2]
                    }
                    for row in cursor.fetchall()
                ]
        except sqlite3.Error as e:
            print(f"Error getting all companies: {e}")
            return []

    def get_company_invoices(self, company_name):
        """Get all invoices for a company"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # First check pending_requests table
                cursor.execute('''
                    SELECT invoice_number, company_name, pdf_path, period_start, period_end
                    FROM pending_requests
                    WHERE company_name LIKE ?
                    AND status = 'pending'
                    ORDER BY period_start DESC
                ''', (f'%{company_name}%',))
                
                columns = ['invoice_number', 'company_name', 'pdf_path', 'period_start', 'period_end']
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                
                # Then check invoice_details table
                cursor.execute('''
                    SELECT invoice_number, company_name, pdf_path, period_start, period_end
                    FROM invoice_details
                    WHERE company_name LIKE ?
                    ORDER BY period_start DESC
                ''', (f'%{company_name}%',))
                
                results.extend([dict(zip(columns, row)) for row in cursor.fetchall()])
                
                # Remove duplicates based on invoice_number
                seen = set()
                unique_results = []
                for result in results:
                    if result['invoice_number'] not in seen:
                        seen.add(result['invoice_number'])
                        unique_results.append(result)
                
                return unique_results
                
        except sqlite3.Error as e:
            print(f"Error getting company invoices: {e}")
            return []

    def create_chat_session(self, session_id: str, topic: str = None) -> int:
        """Create a new chat session and return its ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO chat_history (session_id, topic)
                    VALUES (?, ?)
                ''', (session_id, topic))
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error creating chat session: {e}")
            return None

    def add_chat_message(self, chat_id: int, role: str, content: str) -> bool:
        """Add a message to an existing chat session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO chat_messages (chat_id, role, content)
                    VALUES (?, ?, ?)
                ''', (chat_id, role, content))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error adding chat message: {e}")
            return False

    def get_chat_history(self, limit: int = 10) -> list:
        """Get recent chat sessions with their topics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        ch.id,
                        ch.session_id,
                        ch.topic,
                        ch.created_at,
                        COUNT(cm.id) as message_count,
                        MAX(cm.timestamp) as last_activity
                    FROM chat_history ch
                    LEFT JOIN chat_messages cm ON ch.id = cm.chat_id
                    GROUP BY ch.id
                    ORDER BY last_activity DESC
                    LIMIT ?
                ''', (limit,))
                return [dict(zip(['id', 'session_id', 'topic', 'created_at', 'message_count', 'last_activity'], row))
                        for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Error getting chat history: {e}")
            return []

    def get_chat_messages(self, chat_id: int) -> list:
        """Get all messages for a specific chat session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT role, content, timestamp
                    FROM chat_messages
                    WHERE chat_id = ?
                    ORDER BY timestamp ASC
                ''', (chat_id,))
                return [dict(zip(['role', 'content', 'timestamp'], row))
                        for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Error getting chat messages: {e}")
            return []

    def update_chat_topic(self, chat_id: int, topic: str) -> bool:
        """Update the topic of a chat session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE chat_history
                    SET topic = ?
                    WHERE id = ?
                ''', (topic, chat_id))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error updating chat topic: {e}")
            return False

    def get_chat_topic(self, chat_id: int) -> Optional[str]:
        """Get the topic of a chat session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT topic
                    FROM chat_history
                    WHERE id = ?
                ''', (chat_id,))
                result = cursor.fetchone()
                return result[0] if result else None
        except sqlite3.Error as e:
            logger.error(f"Error getting chat topic: {e}")
            return None

    def delete_chat(self, chat_id: int) -> bool:
        """Delete a chat session and all its messages"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Delete all messages first due to foreign key constraint
                cursor.execute('DELETE FROM chat_messages WHERE chat_id = ?', (chat_id,))
                # Then delete the chat history entry
                cursor.execute('DELETE FROM chat_history WHERE id = ?', (chat_id,))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error deleting chat: {e}")
            return False

    def get_request_by_company(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Get a pending request by company name"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, invoice_number, company_name, pdf_path, period_start, period_end, status, sent_to
                    FROM pending_requests
                    WHERE company_name LIKE ? AND status = 'pending'
                    ORDER BY request_time DESC
                    LIMIT 1
                ''', (f'%{company_name}%',))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'id': result[0],
                        'invoice_number': result[1],
                        'company_name': result[2],
                        'pdf_path': result[3],
                        'period_start': result[4],
                        'period_end': result[5],
                        'status': result[6],
                        'sent_to': result[7]
                    }
                return None
        except sqlite3.Error as e:
            logger.error(f"Error getting request by company: {e}")
            return None 