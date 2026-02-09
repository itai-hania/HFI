# Stage 1: Base image with Playwright
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Copy requirements first for better layer caching
# Build context is project root, so path is src/scraper/requirements.txt
COPY src/scraper/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium browser (optimized for headless scraping)
# --with-deps ensures all necessary system libraries are installed
RUN playwright install chromium --with-deps

# Copy all source packages
COPY src/ /app/src/
ENV PYTHONPATH=/app/src

# Create directories for data persistence
RUN mkdir -p /app/data/session /app/data/media /app/config

# Set environment variables for Playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

# Run as non-root user for security
# The playwright image already has a 'pwuser' with UID 1000
USER pwuser

# Default command: Run the scraper
# In K8s CronJob, this will be overridden
CMD ["python", "-m", "scraper.main"]
