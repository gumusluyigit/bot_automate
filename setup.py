#!/usr/bin/env python3
"""
Setup Script for Receipt Automation System

This script helps set up the Receipt Automation System by:
1. Creating required directories
2. Setting up the database
3. Creating a .env file from .env.example
"""

import os
import sys
import shutil
import getpass
import secrets
from pathlib import Path

def create_directories():
    """Create required directories if they don't exist"""
    print("\nCreating required directories...")
    
    directories = [
        'downloads',
        'processed',
        'cache',
        'uploads'
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            print(f"  Created directory: {directory}")
        else:
            print(f"  Directory already exists: {directory}")
    
    return True

def setup_database():
    """Set up the database"""
    print("\nSetting up the database...")
    
    try:
        # Import the database initialization script
        import init_db
        
        # Initialize the database
        success = init_db.initialize_database()
        
        if success:
            print("  Database setup completed successfully.")
            return True
        else:
            print("  Database setup failed.")
            return False
    except Exception as e:
        print(f"  Error setting up database: {str(e)}")
        return False

def setup_env_file():
    """Set up the .env file from .env.example"""
    print("\nSetting up environment variables...")
    
    if os.path.exists('.env'):
        overwrite = input("  .env file already exists. Do you want to overwrite it? (y/N): ")
        if overwrite.lower() != 'y':
            print("  Keeping existing .env file.")
            return True
    
    if not os.path.exists('.env.example'):
        print("  Error: .env.example file not found.")
        return False
    
    try:
        # Read the .env.example file
        with open('.env.example', 'r') as f:
            env_example = f.read()
        
        # Generate a secret key
        secret_key = secrets.token_hex(16)
        
        # Replace placeholders with actual values
        env_content = env_example
        
        # Ask for Beox credentials
        print("\n  Please enter your Beox Cockpit credentials:")
        beox_username = input("  Username: ")
        beox_password = getpass.getpass("  Password: ")
        
        # Ask for email configuration
        print("\n  Please enter your email configuration:")
        smtp_server = input("  SMTP Server (e.g., smtp.gmail.com): ")
        smtp_port = input("  SMTP Port (e.g., 587): ")
        smtp_username = input("  SMTP Username: ")
        smtp_password = getpass.getpass("  SMTP Password: ")
        sender_email = input("  Sender Email: ")
        internal_email = input("  Internal Notification Email: ")
        
        # Replace placeholders in the .env file
        replacements = {
            'your_beox_username': beox_username,
            'your_beox_password': beox_password,
            'smtp.example.com': smtp_server,
            '587': smtp_port,
            'your_email@example.com': smtp_username,
            'your_email_password': smtp_password,
            'notifications@example.com': internal_email,
            'generate_a_secure_random_key': secret_key
        }
        
        for placeholder, value in replacements.items():
            env_content = env_content.replace(placeholder, value)
        
        # Write the .env file
        with open('.env', 'w') as f:
            f.write(env_content)
        
        print("  Created .env file with your configuration.")
        return True
    except Exception as e:
        print(f"  Error setting up .env file: {str(e)}")
        return False

def install_dependencies():
    """Install Python dependencies"""
    print("\nInstalling Python dependencies...")
    
    try:
        import subprocess
        
        # Check if pip is available
        try:
            subprocess.run([sys.executable, "-m", "pip", "--version"], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            print("  Error: pip is not available. Please install pip first.")
            return False
        
        # Install dependencies
        print("  Running: pip install -r requirements.txt")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            check=True,
            capture_output=True,
            text=True
        )
        
        print("  Dependencies installed successfully.")
        return True
    except Exception as e:
        print(f"  Error installing dependencies: {str(e)}")
        return False

if __name__ == "__main__":
    print("Receipt Automation System - Setup")
    print("="*50)
    print("This script will help you set up the Receipt Automation System.")
    print("It will create required directories, set up the database, and create a .env file.")
    
    proceed = input("\nDo you want to proceed with the setup? (y/N): ")
    if proceed.lower() != 'y':
        print("Setup cancelled.")
        sys.exit(0)
    
    # Create directories
    dir_success = create_directories()
    
    # Set up database
    db_success = setup_database()
    
    # Set up .env file
    env_success = setup_env_file()
    
    # Install dependencies
    dep_success = install_dependencies()
    
    # Print summary
    print("\nSetup Summary:")
    print(f"Directories: {'✅ Success' if dir_success else '❌ Failed'}")
    print(f"Database: {'✅ Success' if db_success else '❌ Failed'}")
    print(f"Environment Variables: {'✅ Success' if env_success else '❌ Failed'}")
    print(f"Dependencies: {'✅ Success' if dep_success else '❌ Failed'}")
    
    if all([dir_success, db_success, env_success, dep_success]):
        print("\n✅ Setup completed successfully!")
        print("You can now run the application with: python app.py")
    else:
        print("\n❌ Setup completed with errors. Please fix the issues before running the application.")
        sys.exit(1) 