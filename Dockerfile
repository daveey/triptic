# Use Python 3.11 slim image
FROM python:3.11-slim

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
RUN uv sync --frozen --no-dev

# Copy application code
COPY src/ ./src/
COPY public/ ./public/

# Create data directory for persistent storage
RUN mkdir -p /data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TRIPTIC_DATA_DIR=/data

# Expose port (Fly.io will set PORT env var)
EXPOSE 8080

# Run the server (in foreground, not daemon mode)
# Note: Fly.io sets PORT env var, defaults to 8080
CMD ["sh", "-c", "uv run triptic start --host 0.0.0.0 --port ${PORT:-8080} --database /data/triptic.db"]
