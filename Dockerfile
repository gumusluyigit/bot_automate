# Use an official Python runtime as the base image
FROM python:3.9-slim

# Set working directory for the backend
WORKDIR /app

# Copy backend requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY . .

# Install Node.js and npm
RUN apt-get update && apt-get install -y \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set working directory for the frontend
WORKDIR /app/frontend

# Install frontend dependencies
RUN npm install

# Build the frontend
RUN npm run build

# Set working directory back to the root
WORKDIR /app

# Create necessary directories
RUN mkdir -p uploads processed

# Expose the port the app runs on
EXPOSE 5000

# Command to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"] 