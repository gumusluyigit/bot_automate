from dotenv import load_dotenv
import os

load_dotenv()

# Email Configuration
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

# Database Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///receipts.db')

# PDF Source Application Configuration
PDF_APP_URL = os.getenv('PDF_APP_URL')
PDF_APP_USERNAME = os.getenv('PDF_APP_USERNAME')
PDF_APP_PASSWORD = os.getenv('PDF_APP_PASSWORD')

# Parasut Configuration
PARASUT_URL = os.getenv('PARASUT_URL', 'https://parasut.com')
PARASUT_USERNAME = os.getenv('PARASUT_USERNAME')
PARASUT_PASSWORD = os.getenv('PARASUT_PASSWORD')

# Internal Department Configuration
INTERNAL_DEPT_EMAIL = os.getenv('INTERNAL_DEPT_EMAIL') 