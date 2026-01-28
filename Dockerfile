# Build stage - install dependencies
FROM python:3.13-slim as builder

WORKDIR /app

# Install uv for faster dependency management
RUN pip install --no-cache-dir uv

# Copy only requirements files first for better caching
COPY pyproject.toml ./

# Install dependencies
RUN uv pip install --system --no-cache -e .

# Runtime stage - minimal image
FROM python:3.13-slim

WORKDIR /app

# Copy only necessary files from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/

# Create data directory for database
RUN mkdir -p /data

# Create and switch to non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app /data
USER appuser

# Environment variables
ENV PKMDEX_API_KEY=""
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Run the web app
CMD ["uvicorn", "src.web:app", "--host", "0.0.0.0", "--port", "8000"]
