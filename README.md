# Receipt Automation

A web application for automating receipt processing and email handling.

## Features

- PDF Receipt Processing
- Automated Email Handling
- Database Management
- Web Interface for Easy Access
- RESTful API Backend

## Prerequisites

- Python 3.9 or higher
- Node.js 18 or higher
- Docker (optional)

## Installation

### Option 1: Running with Docker

1. Clone the repository:
```bash
git clone https://github.com/gumusluyigit/bot_automate.git
cd bot_automate
```

2. Build and run with Docker Compose:
```bash
docker-compose up --build
```

The application will be available at http://localhost:5000

### Option 2: Manual Setup

1. Clone the repository:
```bash
git clone https://github.com/gumusluyigit/bot_automate.git
cd bot_automate
```

2. Set up the backend:
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

3. Set up the frontend:
```bash
cd frontend
npm install
npm run build
cd ..
```

4. Create necessary directories:
```bash
mkdir uploads processed
```

5. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

6. Run the application:
```bash
python app.py
```

The application will be available at http://localhost:5000

## API Endpoints

- `GET /api/health` - Health check endpoint
- `POST /api/process_pdf` - Process a PDF file
- `GET /api/pending_requests` - Get all pending requests
- `POST /api/send_email` - Send email with receipt
- `GET /api/download_pdf/<invoice_number>` - Download a processed PDF

## Development

### Backend Development

The backend is built with Flask and provides RESTful APIs for the frontend.

To run the backend in development mode:
```bash
python app.py
```

### Frontend Development

The frontend is built with React and Material-UI.

To run the frontend in development mode:
```bash
cd frontend
npm start
```

## Testing

Run the tests with:
```bash
python -m pytest
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
