# Use an official Python runtime with Playwright pre-installed
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies (if any additional needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Install Playwright browsers (ensure dependencies are met)
RUN playwright install chromium
RUN playwright install-deps

# Copy project
# Copy project (Already includes scripts/entrypoint.sh)
COPY . /app/

# Make entrypoint script executable
RUN chmod +x /app/scripts/entrypoint.sh

# Entrypoint
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
