# Receipt Automation System

A comprehensive web application for automating the processing of PDF invoices, extracting key information, and managing email delivery to clients.

## Features

- **Automated PDF Processing**: Automatically download and process PDF invoices from Beox Cockpit
- **Data Extraction**: Extract invoice numbers, company names, dates, and amounts from PDFs
- **Email Management**: Send invoices to clients via email with tracking
- **Company Email Association**: Remember email addresses for companies for future automation
- **Manual Processing**: Process PDFs for specific date ranges manually
- **Pending Requests Management**: View and manage pending invoice requests
- **Search Functionality**: Filter company names in the pending requests list
- **Settings Management**: Configure system settings and email templates

## Technical Overview

The system is built with:
- **Backend**: Python with Flask web framework
- **Database**: SQLite for data storage
- **PDF Processing**: PyPDF2 and pdfplumber for text extraction
- **Web Scraping**: Requests and BeautifulSoup for downloading PDFs
- **Email**: SMTP integration for sending emails
- **Frontend**: Bootstrap 5, HTML, CSS, and JavaScript

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git (optional, for cloning the repository)

### Installation

1. Clone the repository (or download and extract the ZIP file):
   ```
   git clone https://github.com/gumusluyigit/bot_automate.git
   cd bot_automate
   ```

2. Create and activate a virtual environment (recommended):
   ```
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root with the following variables:
   ```
   # Beox Cockpit credentials
   BEOX_USERNAME=your_username
   BEOX_PASSWORD=your_password
   
   # Email configuration
   SMTP_SERVER=smtp.example.com
   SMTP_PORT=587
   SMTP_USERNAME=your_email@example.com
   SMTP_PASSWORD=your_email_password
   
   # Internal notification email
   INTERNAL_EMAIL=notifications@example.com
   
   # OpenAI API key (optional, for AI features)
   OPENAI_API_KEY=your_openai_api_key
   
   # Flask secret key (for session security)
   SECRET_KEY=generate_a_secure_random_key
   ```

5. Initialize the database:
   ```
   python database_handler.py
   ```

### Running the Application

1. Start the Flask application:
   ```
   python app.py
   ```

2. Access the web interface at:
   ```
   http://localhost:5000
   ```

## Usage Guide

### Manual Processing

1. Navigate to the "Manual Processing" page
2. Select a week from the dropdown menu
3. The system will display available PDFs for that week
4. Click "Process PDFs" to extract information and store in the database
5. PDFs for companies with registered emails will be sent automatically
6. Other PDFs will be added to the pending requests

### Pending Requests

1. Navigate to the "Pending Requests" page
2. Use the search bar to filter by company name
3. Click "Send Email" for a specific invoice
4. Enter the recipient's email address
5. The system will send the invoice and remember the email for future use

### Settings

1. Navigate to the "Settings" page
2. Configure email templates and system settings
3. View and manage company email associations

## Troubleshooting

- **PDF Processing Issues**: Check the `automation.log` file for detailed error messages
- **Email Sending Failures**: Verify SMTP settings in the `.env` file
- **Database Errors**: Use the `check_db.py` script to diagnose database issues

## Maintenance

- **Logs**: Check `automation.log` for system activity and errors
- **Database Backup**: Periodically backup the `invoice_emails.db` file
- **Cache Clearing**: Delete files in the `cache` directory if experiencing issues

## License

This project is proprietary software. All rights reserved.

## Support

For support inquiries, please contact the developer at your_email@example.com.
