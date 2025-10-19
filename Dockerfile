# Use Python 3.10 as base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for OpenCV and git
RUN apt-get update && apt-get install -y \
    git \
    libgl1-mesa-dri \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Clone the repository
RUN git clone https://github.com/cwhit-io/crowd-counter.git .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create directories for output if needed
RUN mkdir -p /app/output /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default command (can be overridden)
CMD ["python", "--version"]