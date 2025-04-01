# PDF Invoice Processing Automation

A robust web application that automates the process of downloading, processing, and managing PDF invoices. Built with Python Flask and React, this system provides a seamless workflow for handling invoice documents.

## 🌟 Features

- **Automated PDF Download**: Securely downloads invoices from configured sources
- **Smart Processing**: Extracts and validates invoice data using advanced algorithms
- **Email Integration**: Seamless integration with Microsoft Graph API for email operations
- **Database Management**: Efficient storage and retrieval of invoice data
- **Modern UI**: Clean and intuitive React-based frontend
- **Docker Support**: Easy deployment with containerization
- **Security**: Built-in CSRF protection and secure file handling

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Node.js 14+
- Docker (optional)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/pdf-invoice-automation.git
cd pdf-invoice-automation
```

2. Set up the Python environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Initialize the database:
```bash
python init_db.py
```

5. Start the application:
```bash
python app.py
```

### Docker Deployment

```bash
docker-compose up --build
```

## 🛠️ Configuration

### Environment Variables

Key configuration options in `.env`:

- `PDF_SOURCE_USERNAME`: Username for PDF source
- `PDF_SOURCE_PASSWORD`: Password for PDF source
- `SMTP_SERVER`: Email server configuration
- `MS_TENANT_ID`: Microsoft Graph API tenant ID
- `MS_CLIENT_ID`: Microsoft Graph API client ID

### Database

The application uses SQLite by default. Database operations are handled through the `DatabaseHandler` class.

## 📁 Project Structure

```
pdf-invoice-automation/
├── app.py                 # Main application
├── pdf_downloader.py      # PDF download operations
├── pdf_processor.py       # PDF processing logic
├── database_handler.py    # Database operations
├── email_handler.py       # Email operations
├── config_handler.py      # Configuration management
├── ms_graph_client.py     # Microsoft Graph API client
├── frontend/             # React frontend
├── templates/            # HTML templates
├── static/              # Static assets
└── init_db.py           # Database initialization
```

## 🔒 Security

- CSRF protection enabled
- Secure file handling
- Environment variable based configuration
- Input validation and sanitization

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Flask web framework
- React for frontend
- Microsoft Graph API
- All contributors and maintainers

## 📞 Support

For support, please open an issue in the GitHub repository or contact the maintainers.

---

Made with ❤️ by [Your Name/Organization]
