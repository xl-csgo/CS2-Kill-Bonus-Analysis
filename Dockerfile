# Use Python 3.11 as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt

# Copy the analysis scripts
COPY *.py ./

# Create directories for output (these will be volumes)
RUN mkdir -p /app/demos \
    /app/bonus_analysis \
    /app/equipment_analysis \
    /app/kills_analysis \
    /app/utility_analysis \
    /app/combined_analysis

# Set environment variables
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1

# Create a non-root user for security
RUN useradd -m -u 1000 analyst && \
    chown -R analyst:analyst /app
USER analyst

# Default command
CMD ["python", "main.py"]
