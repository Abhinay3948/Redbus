# Use an official Python runtime as the base image
FROM python:3.11-slim

# Install system dependencies for Chromium and ChromeDriver
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-chromedriver \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port your app runs on
EXPOSE 5001

# Command to run the Flask app with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "app:app"]
