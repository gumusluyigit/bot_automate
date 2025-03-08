#!/usr/bin/env python3
"""
Database Initialization Script for Receipt Automation System

This script initializes the database for the Receipt Automation System.
Run this script once before starting the application for the first time.
"""

import os
import sys
import sqlite3
from database_handler import DatabaseHandler

def initialize_database():
    """Initialize the database with required tables"""
    print("Initializing database...")
    
    try:
        # Create database handler instance
        db_handler = DatabaseHandler()
        
        # Initialize database (creates tables if they don't exist)
        db_handler.initialize_database()
        
        # Verify database was created
        if os.path.exists('invoice_emails.db'):
            print("Database initialized successfully!")
            print("Tables created:")
            
            # Connect to the database and list tables
            conn = sqlite3.connect('invoice_emails.db')
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            for table in tables:
                print(f"  - {table[0]}")
            
            conn.close()
            return True
        else:
            print("Error: Database file was not created.")
            return False
            
    except Exception as e:
        print(f"Error initializing database: {str(e)}")
        return False

if __name__ == "__main__":
    print("Receipt Automation System - Database Initialization")
    print("="*50)
    
    if os.path.exists('invoice_emails.db'):
        response = input("Database already exists. Do you want to reinitialize it? (y/N): ")
        if response.lower() != 'y':
            print("Database initialization cancelled.")
            sys.exit(0)
    
    success = initialize_database()
    
    if success:
        print("\nDatabase initialization complete!")
        print("You can now start the application with: python app.py")
    else:
        print("\nDatabase initialization failed. Please check the error messages above.")
        sys.exit(1) 