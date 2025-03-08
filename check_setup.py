#!/usr/bin/env python3
"""
Setup Verification Script for Receipt Automation System

This script checks if the Receipt Automation System is properly set up.
It verifies the presence of required files, directories, and environment variables.
"""

import os
import sys
import sqlite3
from dotenv import load_dotenv

def check_environment_variables():
    """Check if required environment variables are set"""
    print("\nChecking environment variables...")
    
    # Load environment variables
    load_dotenv()
    
    required_vars = [
        'BEOX_USERNAME',
        'BEOX_PASSWORD',
        'SMTP_SERVER',
        'SMTP_PORT',
        'SMTP_USERNAME',
        'SMTP_PASSWORD',
        'INTERNAL_EMAIL',
        'SECRET_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease create a .env file with these variables. See .env.example for reference.")
        return False
    else:
        print("✅ All required environment variables are set.")
        return True

def check_directories():
    """Check if required directories exist"""
    print("\nChecking directories...")
    
    required_dirs = [
        'downloads',
        'processed',
        'cache'
    ]
    
    missing_dirs = []
    for directory in required_dirs:
        if not os.path.exists(directory):
            missing_dirs.append(directory)
    
    if missing_dirs:
        print("❌ Missing required directories:")
        for directory in missing_dirs:
            print(f"  - {directory}")
        
        create = input("\nDo you want to create these directories now? (y/N): ")
        if create.lower() == 'y':
            for directory in missing_dirs:
                os.makedirs(directory, exist_ok=True)
                print(f"  Created directory: {directory}")
            return True
        else:
            return False
    else:
        print("✅ All required directories exist.")
        return True

def check_database():
    """Check if the database exists and has the required tables"""
    print("\nChecking database...")
    
    if not os.path.exists('invoice_emails.db'):
        print("❌ Database file not found.")
        init = input("Do you want to initialize the database now? (y/N): ")
        if init.lower() == 'y':
            try:
                import init_db
                init_db.initialize_database()
                return True
            except Exception as e:
                print(f"Error initializing database: {str(e)}")
                return False
        else:
            return False
    
    try:
        conn = sqlite3.connect('invoice_emails.db')
        cursor = conn.cursor()
        
        # Check for required tables
        required_tables = ['Companies', 'Invoices']
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        existing_tables = [table[0] for table in cursor.fetchall()]
        
        missing_tables = [table for table in required_tables if table not in existing_tables]
        
        if missing_tables:
            print("❌ Database is missing required tables:")
            for table in missing_tables:
                print(f"  - {table}")
            
            init = input("Do you want to reinitialize the database? (y/N): ")
            if init.lower() == 'y':
                try:
                    import init_db
                    init_db.initialize_database()
                    return True
                except Exception as e:
                    print(f"Error initializing database: {str(e)}")
                    return False
            else:
                return False
        else:
            print("✅ Database exists and contains required tables.")
            return True
            
    except Exception as e:
        print(f"❌ Error checking database: {str(e)}")
        return False

def check_dependencies():
    """Check if required Python packages are installed"""
    print("\nChecking Python dependencies...")
    
    try:
        import flask
        import PyPDF2
        import pdfplumber
        import requests
        import bs4
        print("✅ Core dependencies are installed.")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {str(e)}")
        print("Please install all required dependencies with: pip install -r requirements.txt")
        return False

if __name__ == "__main__":
    print("Receipt Automation System - Setup Verification")
    print("="*50)
    
    env_check = check_environment_variables()
    dir_check = check_directories()
    db_check = check_database()
    dep_check = check_dependencies()
    
    print("\nVerification Summary:")
    print(f"Environment Variables: {'✅ OK' if env_check else '❌ Issues Found'}")
    print(f"Directories: {'✅ OK' if dir_check else '❌ Issues Found'}")
    print(f"Database: {'✅ OK' if db_check else '❌ Issues Found'}")
    print(f"Dependencies: {'✅ OK' if dep_check else '❌ Issues Found'}")
    
    if all([env_check, dir_check, db_check, dep_check]):
        print("\n✅ All checks passed! The system is ready to run.")
        print("You can start the application with: python app.py")
    else:
        print("\n❌ Some checks failed. Please fix the issues before running the application.")
        sys.exit(1) 