FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.lock .

# Install Python dependencies
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

# Copy application code and migration tooling
COPY bot/ ./bot/
COPY config/ ./config/
COPY migrations/ ./migrations/
COPY alembic.ini ./alembic.ini
COPY docker-entrypoint.sh ./docker-entrypoint.sh
RUN chmod +x ./docker-entrypoint.sh

# Create logs directory
RUN mkdir -p /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Health check (standalone probe: opens its own DB/Redis connections)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -m bot.utils.health || exit 1

# Apply DB migrations, then run the bot
ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]
