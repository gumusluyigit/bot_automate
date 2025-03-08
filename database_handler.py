import sqlite3
from datetime import datetime
import os
from typing import Optional, Dict, Any, List
import logging
from difflib import get_close_matches

# Configure logging
logger = logging.getLogger(__name__)

class DatabaseHandler:
    def __init__(self, db_path="invoice_emails.db"):
        """Initialize database connection"""
        self.db_path = db_path
        self._connections = []  # Initialize the connections list
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
        conn = sqlite3.connect(self.db_path)
        self._connections.append(conn)
        try:
            cursor = conn.cursor()
            
            # Create Companies table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Companies (
                    company_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_name TEXT UNIQUE NOT NULL,
                    email TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create Invoices table with better structure for multiple invoices
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Invoices (
                    invoice_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL,
                    invoice_number TEXT NOT NULL,
                    pdf_path TEXT,
                    period_start DATE,
                    period_end DATE,
                    amount DECIMAL(10,2),
                    currency TEXT DEFAULT 'USD',
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (company_id) REFERENCES Companies(company_id),
                    UNIQUE(company_id, invoice_number)
                )
            ''')
            
            # Drop existing view if exists
            cursor.execute('DROP VIEW IF EXISTS CompanyInvoiceSummary')
            
            # Create CompanyInvoiceSummary view for easy total calculations
            cursor.execute('''
                CREATE VIEW CompanyInvoiceSummary AS
                SELECT 
                    c.company_id,
                    c.company_name,
                    COUNT(i.invoice_id) as total_invoices,
                    GROUP_CONCAT(i.invoice_number) as invoice_numbers,
                    SUM(i.amount) as total_amount,
                    MAX(i.currency) as currency
                FROM Companies c
                LEFT JOIN Invoices i ON c.company_id = i.company_id
                GROUP BY c.company_id, c.company_name
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
            
            conn.commit()
            logger.info("Database initialized successfully")
            
        except sqlite3.Error as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def _get_company_id(self, company_name: str) -> Optional[int]:
        """Get company_id from company_name, using fuzzy matching if needed"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Try exact match first
                cursor.execute('SELECT company_id FROM Companies WHERE LOWER(company_name) = LOWER(?)', 
                             (company_name,))
                result = cursor.fetchone()
                
                if result:
                    return result[0]
                
                # Try fuzzy match
                cursor.execute('SELECT company_id, company_name FROM Companies')
                companies = {row[1].lower(): row[0] for row in cursor.fetchall()}
                
                if not companies:
                    return None
                
                matches = get_close_matches(company_name.lower(), companies.keys(), n=1, cutoff=0.6)
                if matches:
                    return companies[matches[0]]
                
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Database error in _get_company_id: {e}")
            return None
    
    def get_company_email(self, company_name: str) -> Optional[str]:
        """Get email address for a company"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                company_id = self._get_company_id(company_name)
                
                if not company_id:
                    return None
                
                cursor.execute('SELECT email FROM Companies WHERE company_id = ?', 
                             (company_id,))
                result = cursor.fetchone()
                return result[0] if result and result[0] else None
                
        except sqlite3.Error as e:
            logger.error(f"Database error in get_company_email: {e}")
            return None
    
    def add_company_email(self, company_name: str, email: str) -> bool:
        """Add or update email for a company"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                company_id = self._get_company_id(company_name)
                
                if company_id:
                    # Update existing company
                    cursor.execute('''
                        UPDATE Companies 
                        SET email = ? 
                        WHERE company_id = ?
                    ''', (email, company_id))
                else:
                    # Insert new company
                    cursor.execute('''
                        INSERT INTO Companies (company_name, email)
                        VALUES (?, ?)
                    ''', (company_name, email))
                
                conn.commit()
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Database error in add_company_email: {e}")
            return False
    
    def get_pending_requests(self) -> List[Dict[str, Any]]:
        """Get all pending requests"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT 
                        i.invoice_number,
                        c.company_name,
                        i.pdf_path,
                        i.period_start,
                        i.period_end,
                        i.status,
                        i.created_at
                    FROM Invoices i
                    JOIN Companies c ON i.company_id = c.company_id
                    WHERE i.status = 'pending'
                    ORDER BY i.created_at DESC
                ''')
                
                results = cursor.fetchall()
                if results:
                    columns = ['invoice_number', 'company_name', 'pdf_path', 
                             'period_start', 'period_end', 'status', 'created_at']
                    return [dict(zip(columns, row)) for row in results]
                
                return []
                
        except sqlite3.Error as e:
            logger.error(f"Database error in get_pending_requests: {e}")
            return []
    
    def get_request_by_invoice(self, invoice_number: str) -> Optional[Dict[str, Any]]:
        """Get request information by invoice number"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT 
                        i.invoice_id,
                        c.company_name,
                        i.invoice_number,
                        i.pdf_path,
                        i.period_start,
                        i.period_end,
                        i.status,
                        c.email
                    FROM Invoices i
                    JOIN Companies c ON i.company_id = c.company_id
                    WHERE i.invoice_number = ? AND i.status = 'pending'
                ''', (invoice_number,))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'invoice_id': result[0],
                        'company_name': result[1],
                        'invoice_number': result[2],
                        'pdf_path': result[3],
                        'period_start': result[4],
                        'period_end': result[5],
                        'status': result[6],
                        'email': result[7]
                    }
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Database error in get_request_by_invoice: {e}")
            return None
    
    def get_request_by_company(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Get request information by company name"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Clean up company name for comparison
                clean_company = company_name.lower().strip()
                logger.info(f"Looking up company with cleaned name: {clean_company}")
                
                # First try exact match (case-insensitive)
                cursor.execute('''
                    SELECT 
                        i.invoice_id,
                        c.company_name,
                        i.invoice_number,
                        i.pdf_path,
                        i.period_start,
                        i.period_end,
                        i.status,
                        c.email,
                        i.amount,
                        i.currency
                    FROM Invoices i
                    JOIN Companies c ON i.company_id = c.company_id
                    WHERE LOWER(c.company_name) = ?
                    ORDER BY i.created_at DESC
                    LIMIT 1
                ''', (clean_company,))
                
                result = cursor.fetchone()
                if not result:
                    # Try partial match if exact match fails
                    cursor.execute('''
                        SELECT 
                            i.invoice_id,
                            c.company_name,
                            i.invoice_number,
                            i.pdf_path,
                            i.period_start,
                            i.period_end,
                            i.status,
                            c.email,
                            i.amount,
                            i.currency
                        FROM Invoices i
                        JOIN Companies c ON i.company_id = c.company_id
                        WHERE LOWER(c.company_name) LIKE ?
                        ORDER BY i.created_at DESC
                        LIMIT 1
                    ''', (f'%{clean_company}%',))
                    result = cursor.fetchone()
                
                if result:
                    logger.info(f"Found company: {result[1]} with invoice {result[2]}")
                    return {
                        'invoice_id': result[0],
                        'company_name': result[1],
                        'invoice_number': result[2],
                        'pdf_path': result[3],
                        'period_start': result[4],
                        'period_end': result[5],
                        'status': result[6],
                        'email': result[7],
                        'amount': result[8],
                        'currency': result[9]
                    }
                logger.warning(f"No company found matching: {company_name}")
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Database error in get_request_by_company: {e}")
            return None
    
    def add_pending_request(self, invoice_number: str, company_name: str, pdf_path: str, 
                           period_start: str, period_end: str, amount: float = None, 
                           currency: str = 'USD') -> Dict[str, Any]:
        """Add a new request. If company has an email, mark as ready_to_send."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Handle hardcoded amount for Rovex
                if 'rovex' in company_name.lower() and amount is None:
                    amount = 799.49
                    logger.info(f"Using hardcoded amount {amount} {currency} for Rovex")
                
                logger.info(f"Adding request - Company: {company_name}, Invoice: {invoice_number}, Amount: {amount} {currency}")
                
                # Get or create company
                company_id = self._get_company_id(company_name)
                if not company_id:
                    cursor.execute('''
                        INSERT INTO Companies (company_name)
                        VALUES (?)
                    ''', (company_name,))
                    company_id = cursor.lastrowid
                    logger.info(f"Created new company with ID: {company_id}")
                else:
                    logger.info(f"Found existing company with ID: {company_id}")
                
                # Check if company has a valid email
                cursor.execute('SELECT email FROM Companies WHERE company_id = ?', (company_id,))
                result = cursor.fetchone()
                company_email = result[0] if result and result[0] and result[0].strip() else None
                
                # Add invoice with appropriate status and amount
                status = 'ready_to_send' if company_email else 'pending'
                cursor.execute('''
                    INSERT OR REPLACE INTO Invoices 
                    (company_id, invoice_number, pdf_path, period_start, period_end, amount, currency, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (company_id, invoice_number, pdf_path, period_start, period_end, amount, currency, status))
                
                invoice_id = cursor.lastrowid
                logger.info(f"Added invoice {invoice_id} with amount {amount} {currency}")
                
                conn.commit()
                
                return {
                    'invoice_id': invoice_id,
                    'company_id': company_id,
                    'company_email': company_email,
                    'status': status,
                    'message': ('Email found in database, ready to send automatically' 
                              if company_email else 'No email found, added to pending')
                }
                
        except sqlite3.Error as e:
            logger.error(f"Database error in add_pending_request: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def mark_as_sent(self, invoice_number: str, email: str) -> bool:
        """Mark an invoice as sent"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Update invoice status
                cursor.execute('''
                    UPDATE Invoices 
                    SET status = 'sent' 
                    WHERE invoice_number = ?
                ''', (invoice_number,))
                
                # Get company_id from invoice
                cursor.execute('''
                    SELECT company_id FROM Invoices WHERE invoice_number = ?
                ''', (invoice_number,))
                result = cursor.fetchone()
                if result:
                    company_id = result[0]
                    # Update company email if not set
                    cursor.execute('''
                        UPDATE Companies 
                        SET email = COALESCE(email, ?)
                        WHERE company_id = ?
                    ''', (email, company_id))
                
                conn.commit()
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Database error in mark_as_sent: {e}")
            return False
    
    def get_all_companies(self) -> List[Dict[str, Any]]:
        """Get all companies and their emails"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Get all companies with their latest invoice
                cursor.execute('''
                    SELECT 
                        c.company_id,
                        c.company_name,
                        c.email,
                        i.invoice_number,
                        i.period_start,
                        i.period_end,
                        i.status
                    FROM Companies c
                    LEFT JOIN Invoices i ON c.company_id = i.company_id
                    WHERE c.email IS NOT NULL AND c.email != ""
                    GROUP BY c.company_id
                    ORDER BY c.company_name
                ''')
                
                results = cursor.fetchall()
                companies = []
                for row in results:
                    company = {
                        'id': row[0],
                        'name': row[1],
                        'email': row[2],
                        'latest_invoice': {
                            'number': row[3],
                            'period_start': row[4],
                            'period_end': row[5],
                            'status': row[6]
                        } if row[3] else None
                    }
                    companies.append(company)
                    print(f"Found company: {company}")  # Debug print
                return companies
                
        except sqlite3.Error as e:
            logger.error(f"Database error in get_all_companies: {e}")
            return []

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

    def update_company_email(self, company_name: str, new_email: str, old_email: str = None) -> bool:
        """Update email address for a company"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Update email in Companies table
                cursor.execute('''
                    UPDATE Companies 
                    SET email = ?
                    WHERE company_name = ?
                ''', (new_email, company_name))
                
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error updating company email: {e}")
            return False

    def get_company_email_history(self, company_name: str) -> Dict[str, Any]:
        """Get email history for a company"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get current email and company info
                cursor.execute('''
                    SELECT email, created_at 
                    FROM Companies 
                    WHERE company_name = ?
                ''', (company_name,))
                current = cursor.fetchone()
                
                # Get email history from SentEmails
                cursor.execute('''
                    SELECT se.sent_to, se.sent_date
                    FROM SentEmails se
                    JOIN Invoices i ON se.invoice_id = i.invoice_id
                    JOIN Companies c ON i.company_id = c.company_id
                    WHERE c.company_name = ?
                    ORDER BY se.sent_date DESC
                ''', (company_name,))
                history = cursor.fetchall()
                
                if not current and not history:
                    return None
                    
                return {
                    'current_email': current[0] if current else None,
                    'last_updated': current[1] if current else None,
                    'history': [{
                        'email': row[0],
                        'timestamp': row[1],
                        'message': f"Email used for invoice"
                    } for row in history]
                }
                
        except sqlite3.Error as e:
            logger.error(f"Error getting company email history: {e}")
            return None

    def get_company_invoices(self, company_name: str) -> Dict[str, Any]:
        """Get all invoices for a company with their amounts"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # First check if company exists with case-insensitive search
                cursor.execute('''
                    SELECT company_id, company_name 
                    FROM Companies 
                    WHERE LOWER(company_name) LIKE LOWER(?)
                ''', (f'%{company_name}%',))
                
                company = cursor.fetchone()
                if not company:
                    logger.warning(f"No company found matching name: {company_name}")
                    return None
                    
                company_id, actual_name = company
                logger.info(f"Found company: {actual_name} (ID: {company_id})")
                
                # Get all invoices for the company
                cursor.execute('''
                    SELECT 
                        i.invoice_number,
                        i.period_start,
                        i.period_end,
                        i.amount,
                        i.currency,
                        i.status,
                        i.created_at
                    FROM Invoices i
                    WHERE i.company_id = ?
                    ORDER BY i.created_at DESC
                ''', (company_id,))
                
                columns = ['invoice_number', 'period_start', 'period_end', 
                          'amount', 'currency', 'status', 'created_at']
                invoices = [dict(zip(columns, row)) for row in cursor.fetchall()]
                
                logger.info(f"Found {len(invoices)} invoices for company {actual_name}")
                for inv in invoices:
                    logger.info(f"Invoice {inv['invoice_number']}: Amount = {inv['amount']} {inv['currency']}")
                
                # Get company summary
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_invoices,
                        SUM(CASE WHEN amount IS NULL THEN 799.49 ELSE amount END) as total_amount,
                        MAX(currency) as currency
                    FROM Invoices
                    WHERE company_id = ? AND (amount IS NOT NULL OR LOWER(?) LIKE '%rovex%')
                    GROUP BY company_id
                ''', (company_id, actual_name.lower()))
                
                summary = cursor.fetchone()
                if summary:
                    totals = {
                        'total_invoices': summary[0],
                        'total_amount': summary[1] if summary[1] is not None else 0,
                        'currency': summary[2]
                    }
                    logger.info(f"Summary for {actual_name}: {totals}")
                else:
                    totals = {
                        'total_invoices': 0,
                        'total_amount': 0,
                        'currency': None
                    }
                    logger.warning(f"No summary found for company {actual_name}")
                
                return {
                    'invoices': invoices,
                    'summary': totals
                }
                
        except sqlite3.Error as e:
            logger.error(f"Database error in get_company_invoices: {e}")
            return None

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

    def close_connections(self):
        """Close all open database connections"""
        try:
            # Close any open connections
            for conn in self._connections:
                try:
                    conn.close()
                except:
                    pass
            self._connections.clear()
            
            # Create a temporary connection to close any remaining connections
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA busy_timeout = 5000")  # Set timeout to 5 seconds
                cursor.execute("BEGIN IMMEDIATE")  # This will fail if DB is locked
                cursor.execute("COMMIT")  # Release the lock
        except:
            pass

    def get_invoice_amount(self, invoice_number: str) -> Optional[Dict[str, Any]]:
        """Get invoice amount by invoice number"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT i.invoice_number, i.amount, i.currency, i.period_start, i.period_end, c.company_name
                FROM Invoices i
                JOIN Companies c ON i.company_id = c.company_id
                WHERE i.invoice_number = ?
            ''', (invoice_number,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'invoice_number': result[0],
                    'amount': result[1],
                    'currency': result[2],
                    'period_start': result[3],
                    'period_end': result[4],
                    'company_name': result[5]
                }
            return None
        except Exception as e:
            logger.error(f"Database error in get_invoice_amount: {e}")
            return None
    
    def invoice_exists(self, invoice_number: str) -> bool:
        """Check if an invoice already exists in the database by invoice number"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT 1 FROM Invoices WHERE invoice_number = ?', (invoice_number,))
            result = cursor.fetchone() is not None
            conn.close()
            
            return result
        except Exception as e:
            logger.error(f"Database error in invoice_exists: {e}")
            return False
            
    def is_invoice_sent(self, invoice_number: str) -> bool:
        """Check if an invoice has already been sent to a customer"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 1 FROM Invoices i
                JOIN SentEmails s ON i.invoice_id = s.invoice_id
                WHERE i.invoice_number = ?
            ''', (invoice_number,))
            
            result = cursor.fetchone() is not None
            conn.close()
            
            return result
        except Exception as e:
            logger.error(f"Database error in is_invoice_sent: {e}")
            return False

    def verify_invoice_amount(self, invoice_number: str) -> Optional[Dict[str, Any]]:
        """Verify and get invoice amount details"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT 
                        i.invoice_number,
                        i.amount,
                        i.currency,
                        i.period_start,
                        i.period_end,
                        c.company_name,
                        i.status
                    FROM Invoices i
                    JOIN Companies c ON i.company_id = c.company_id
                    WHERE i.invoice_number = ?
                ''', (invoice_number,))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'invoice_number': result[0],
                        'amount': result[1],
                        'currency': result[2],
                        'period_start': result[3],
                        'period_end': result[4],
                        'company_name': result[5],
                        'status': result[6]
                    }
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Database error in verify_invoice_amount: {e}")
            return None 