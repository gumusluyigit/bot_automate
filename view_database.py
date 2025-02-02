import sqlite3
from datetime import datetime

def view_database_contents(db_path="invoice_emails.db"):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print("\n=== Database Contents ===\n")
        
        for table in tables:
            table_name = table[0]
            print(f"\n=== Table: {table_name} ===")
            
            # Get column names
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = [column[1] for column in cursor.fetchall()]
            print("\nColumns:", ", ".join(columns))
            
            # Get all rows
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            
            if rows:
                print("\nRows:")
                for row in rows:
                    print("-" * 50)
                    for col, value in zip(columns, row):
                        print(f"{col}: {value}")
            else:
                print("\nNo data in table")
            
            print("\n" + "=" * 50)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Error accessing database: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    view_database_contents() 