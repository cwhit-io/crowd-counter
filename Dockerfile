# Multi-stage build for minimal final image
FROM python:3.10-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install dependencies
COPY requirements.txt .

# Install CPU-only PyTorch first (much smaller than CUDA version)
RUN pip install --no-cache-dir \
    torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install opencv-python-headless (smaller than opencv-python)
RUN pip install --no-cache-dir opencv-python-headless>=4.6.0

# Install other dependencies (excluding opencv-python since we have headless)
RUN pip install --no-cache-dir \
    python-dotenv>=0.19.0 \
    requests>=2.28.1 \
    numpy>=1.23.0 \
    ultralytics>=8.0.0 \
    scikit-learn>=1.1.0 \
    mailtrap>=1.0.0

# Final stage - minimal runtime image
FROM python:3.10-slim

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libfontconfig1 \
    libice6 \
    libegl1 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application files
COPY run.py .
COPY preset_config.json .
COPY .env* ./

# Create directories for output
RUN mkdir -p /app/output /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# PTZOptics Camera Configuration
ENV CAMERA_IP=192.168.1.100
ENV CAMERA_USER=username
ENV CAMERA_PASS=password

# YOLO Model Configuration
ENV MODEL_PATH=models/best.pt
ENV INFER_CONF=0.10
ENV INFER_IOU=0.30
ENV CLUSTER_EPS=15
ENV MIN_CLUSTER_SIZE=1000

# Processing Configuration
ENV BATCH_SIZE=4
ENV NUM_WORKERS=4

# Email Configuration
ENV EMAIL_SENDER=no-reply@example.org
ENV EMAIL_RECEIVER=user@example.org
ENV EMAIL_API=your_api_key_here

# Keep container running for testing
CMD ["tail", "-f", "/dev/null"]