FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency definition files
COPY pyproject.toml ./

# Install dependencies into the system's python environment
COPY requirements.txt ./
RUN uv pip install -r requirements.txt --system

# Copy the application source code
COPY camp44/ ./camp44/

# Expose the port the app runs on
EXPOSE 5050
