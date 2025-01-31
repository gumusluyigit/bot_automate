import sqlite3
import os

def fix_database():
    """Fix the database structure by recreating the tables with correct columns"""
    db_path = "pending_requests.db"
    
    try:
        # Backup the existing database
        if os.path.exists(db_path):
            backup_path = db_path + ".backup"
            print(f"Creating backup at {backup_path}")
            with open(db_path, 'rb') as src, open(backup_path, 'wb') as dst:
                dst.write(src.read())
        
        print(f"Connecting to database: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get existing data
        print("Backing up existing data...")
        try:
            cursor.execute('SELECT * FROM pending_requests')
            existing_data = cursor.fetchall()
            print(f"Found {len(existing_data)} existing records")
        except sqlite3.OperationalError:
            existing_data = []
            print("No existing data found")
        
        # Drop and recreate the table
        print("\nRecreating tables with correct structure...")
        cursor.execute('DROP TABLE IF EXISTS pending_requests')
        
        cursor.execute('''
            CREATE TABLE pending_requests (
                invoice_number TEXT PRIMARY KEY,
                company_name TEXT,
                request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pdf_path TEXT,
                status TEXT DEFAULT 'pending',
                email TEXT NULL,
                period_start DATE,
                period_end DATE,
                display_invoice_number TEXT
            )
        ''')
        
        # Restore the data if we had any
        if existing_data:
            print("\nRestoring existing data...")
            for record in existing_data:
                try:
                    # Adjust this based on the actual column order in your backup
                    cursor.execute('''
                        INSERT INTO pending_requests 
                        (invoice_number, company_name, request_time, pdf_path, status, email, 
                         period_start, period_end, display_invoice_number)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', record)
                except Exception as e:
                    print(f"Error restoring record: {str(e)}")
        
        # Commit changes
        print("\nCommitting changes...")
        conn.commit()
        
        print("\nDatabase structure fixed successfully!")
        
    except Exception as e:
        print(f"Database error: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    fix_database() 