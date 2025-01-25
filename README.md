# Receipt Email Automation

A Python application that automates the process of downloading PDF receipts and sending them to companies via email.

## Features

- GUI interface for easy interaction
- Automated PDF receipt processing
- Email management with Gmail integration
- Date-based receipt processing
- Pending requests tracking
- Activity logging
- Test mode for development

## Requirements

- Python 3.8+
- Required packages listed in `requirements.txt`

## Installation

1. Clone the repository:
```bash
git clone https://github.com/gumusluyigit/mail_automation.git
cd mail_automation
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file based on `.env.example` and fill in your configuration:
```bash
cp .env.example .env
```

4. Configure your Gmail account:
   - Enable 2-Step Verification
   - Generate an App Password
   - Add the App Password to the settings in the application

## Usage

1. Run the application:
```bash
python gui.py
```

2. Configure Settings:
   - Enter your Gmail address
   - Enter your Gmail App Password
   - Enter the internal department email

3. Process Receipts:
   - Select a date to process receipts for that week
   - Or use "Process All Unprocessed PDFs"
   - Monitor progress in the status window

4. Track Pending Requests:
   - View pending email requests
   - Check for responses
   - Monitor email sending status

5. View Logs:
   - Track all activities
   - Export logs for analysis
   - Clear logs when needed

## Project Structure

- `gui.py`: Main GUI application
- `web_automation.py`: Web automation for PDF downloads
- `pdf_processor.py`: PDF processing and data extraction
- `email_handler.py`: Email management and sending
- `database.py`: Database operations
- `config.py`: Configuration management

## Development

To run in test mode:
1. Create a `pdf_samples` directory
2. Add sample PDF files
3. Run the application normally - it will detect test mode

## License

This project is licensed under the MIT License - see the LICENSE file for details. 