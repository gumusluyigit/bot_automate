# Receipt Automation System

A Python-based system for automating the processing of PDF invoices and managing email communications.

## Features

- PDF invoice processing and data extraction
- Automated email handling with Gmail integration
- Invoice data storage and management
- User-friendly GUI interface
- Chat interface for querying invoice information
- Support for Turkish language queries

## Requirements

- Python 3.8+
- PyPDF2
- tkinter
- tkcalendar
- sqlite3
- O365 (for Microsoft integration)

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd receipt-automation
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

1. Gmail Setup:
   - Enable 2-Step Verification in your Google Account
   - Generate an App Password for the application
   - Configure the email settings in the application

2. Directory Setup:
   - The system will automatically create necessary directories:
     - `downloads/`: For temporary storage of downloaded PDFs
     - `processed/`: For processed PDFs
     - `db/`: For SQLite database storage

## Usage

1. Run the application:
```bash
python gui.py
```

2. Main Features:
   - Process PDFs by week
   - View and manage pending requests
   - Send emails with processed invoices
   - Query invoice information via chat interface

3. Chat Commands:
   - Check amount due: "[company] şirketinin [date] haftasının borcu"
   - Check email: "[company] şirketinin mail adresi"
   - Check due date: "[company] şirketinin son ödeme günü"
   - Process PDFs: "[date] haftasının pdflerini işle"

## Database Structure

The system uses SQLite with the following main tables:
- `invoice_emails`: Stores email mappings
- `invoice_details`: Stores PDF content information
- `pending_requests`: Manages pending email requests
- `sent_emails`: Tracks sent emails

## License

[Your License Here]
