FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install uv for faster dependency management
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/

# Install dependencies
RUN uv pip install --system --no-cache -e .

# Create data directory for database
RUN mkdir -p /data

# Environment variables
ENV PKMDEX_API_KEY=""
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Run the web app
CMD ["uvicorn", "src.web:app", "--host", "0.0.0.0", "--port", "8000"]
