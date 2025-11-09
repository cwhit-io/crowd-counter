# Use Ultralytics CPU image as base (includes PyTorch, OpenCV, YOLO, etc.)
FROM ultralytics/ultralytics:latest-cpu

# Install additional system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install additional Python dependencies not in base image
RUN pip install --no-cache-dir \
    python-dotenv>=0.19.0 \
    mailtrap>=1.0.0 \
    flask>=2.3.0 \
    scikit-learn>=1.0.0

# Set working directory
WORKDIR /app

# Clone the latest code from GitHub
RUN git clone https://github.com/cwhit-io/crowd-counter.git /tmp/repo && \
    cp -r /tmp/repo/* /app/ && \
    rm -rf /tmp/repo && \
    chmod +x /app/*.sh /app/*.py 2>/dev/null || true

# Create directories for output and models
RUN mkdir -p /app/output /app/data /app/models

# Download the pre-trained YOLO model from CDN
RUN curl -L -o /app/models/best.pt https://cwhit-io.b-cdn.net/best.pt && \
    echo "✅ Downloaded YOLO model ($(du -h /app/models/best.pt | cut -f1))"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# PTZOptics Camera Configuration
ENV CAMERA_IP=192.168.1.100
ENV CAMERA_USER=admin
ENV CAMERA_PASS=admin

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

# Database Configuration
ENV DATABASE_PATH=/app/crowd_counter.db

# API Configuration
ENV API_PORT=8000
ENV API_DEBUG=false

# Expose API port
EXPOSE 8000

# Start API server by default
CMD ["python", "api.py"]