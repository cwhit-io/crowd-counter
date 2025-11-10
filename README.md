# PTZ Camera Capture and Analysis System

This project is designed to control a PTZ (Pan-Tilt-Zoom) camera, capture images from predefined preset positions, process these images using a YOLO model to detect and count people, and send the results via email. The system supports parallel image processing for efficiency and logs all operations for debugging and monitoring.

## Features

- **REST API**: Simple HTTP API to trigger crowd counting and monitor status
- **Camera Control**: Communicates with a PTZ camera using VISCA commands over a socket connection.
- **Image Capture**: Captures images from specified preset positions via HTTP requests.
- **Object Detection**: Uses a YOLO model to detect people in captured images.
- **Clustering**: Applies DBSCAN clustering to count distinct groups of people.
- **Parallel Processing**: Processes images concurrently using multiprocessing.
- **Result Compilation**: Saves annotated images and counts to a CSV file.
- **Email Notification**: Zips results and sends them via email using the Mailtrap API.

## Requirements

### Docker (Recommended)
- Docker installed on your system
- A PTZ camera accessible over a network with VISCA protocol support
- **Note**: YOLO model is automatically downloaded from CDN - no manual setup needed!

### Local Installation
- Python 3.8 or higher
- A PTZ camera accessible over a network with VISCA protocol support
- A trained YOLO model for person detection (e.g., `best.pt`)
- Install dependencies: `pip install -r requirements.txt`

## Configuration

Environment variables can be set in a `.env` file or directly in your system. Below are the configurable parameters:

- `CAMERA_IP`: IP address of the PTZ camera (default: none, must be set)
- `VISCA_PORT`: Port for VISCA commands (default: `5678`)
- `CAMERA_USER`: Camera username (default: none, must be set)
- `CAMERA_PASS`: Camera password (default: none, must be set)
- `MODEL_PATH`: Path to the YOLO model file (default: `models/best.pt`)
- `INFER_CONF`: Confidence threshold for YOLO inference (default: `0.25`)
- `INFER_IOU`: IoU threshold for YOLO inference (default: `0.45`)
- `CLUSTER_EPS`: DBSCAN epsilon parameter for clustering (default: `50`)
- `MIN_CLUSTER_SIZE`: Minimum cluster size for DBSCAN (default: `2`)
- `BATCH_SIZE`: Batch size for processing (default: `4`)
- `NUM_WORKERS`: Number of worker processes (default: `4`)
- `EMAIL_SENDER`: Sender email address for results (default: none, must be set)
- `EMAIL_RECEIVER`: Receiver email address for results (default: none, must be set)
- `EMAIL_API`: Mailtrap API token (default: none, must be set)
- `PRESET_CONFIG_FILE`: Path to preset configuration JSON file (default: `preset_config.json`)
- `DATABASE_PATH`: Path to SQLite database file (default: `/app/crowd_counter.db`)

Example `.env` file:

```plaintext
CAMERA_IP=192.168.x.x
CAMERA_USER=your_camera_username
CAMERA_PASS=your_camera_password
EMAIL_RECEIVER=your_email@example.com
EMAIL_API=your_mailtrap_api_token
```

## Preset Configuration

Presets are loaded from a JSON file specified by `PRESET_CONFIG_FILE`. The file should have the following structure:

```json
{
  "presets": [
    { "number": 1, "name": "Entrance" },
    { "number": 2, "name": "Hallway" }
  ]
}
```

## Usage

### Running with Docker (Recommended)

The easiest way to run this application is using Docker:

```bash
# Pull the image from Docker Hub
docker pull cwhitio/crowd-counter:v2.15

# Run with environment variables
docker run -d --name crowd-counter \
  -e CAMERA_IP=192.168.1.100 \
  -e CAMERA_USER=admin \
  -e CAMERA_PASS=password \
  -e EMAIL_RECEIVER=your_email@example.com \
  -e EMAIL_API=your_mailtrap_api_token \
  -v ./models:/app/models \
  -v ./output:/app/output \
  cwhitio/crowd-counter:v2.15

# The container starts with an API server automatically
# Access the web API at http://localhost:8000

# Trigger crowd counting via API (Recommended)
curl http://localhost:8000/start

# Check process status
curl http://localhost:8000/status

# View detailed logs  
curl http://localhost:8000/logs

# Alternative: Execute directly in container
docker exec crowd-counter python run.py

# Update the application from GitHub
docker exec crowd-counter python update.py
```

## API Endpoints

The application includes a REST API server that starts automatically on port 8000:

### Available Endpoints

- **GET /** - Service information and available endpoints
- **GET /health** - Detailed health check with system status
- **GET /start** - Start the crowd counting process
- **GET /trigger** - Alternative endpoint to start counting
- **POST /email** - Send crowd counter notification email to specified receiver(s)
- **POST /db/update** - Run crowd counting and update service attendance table
- **GET /update** - Update application from GitHub
- **GET /status** - Check current process status
- **GET /logs** - Get process logs and output

### API Usage Examples

**Linux/macOS (curl):**
```bash
# Start crowd counting
curl http://localhost:8000/start

# Check process status
curl http://localhost:8000/status

# Get detailed logs
curl http://localhost:8000/logs

# Health check
curl http://localhost:8000/health

# Update from GitHub
curl http://localhost:8000/update

# Send custom email
curl -X POST http://localhost:8000/email \
  -H "Content-Type: application/json" \
  -d '{"receiver": "user@example.com,user2@example.com"}'

# Send email to default receivers (from .env EMAIL_RECEIVER)
curl -X POST http://localhost:8000/email \
  -H "Content-Type: application/json" \
  -d '{}'

# Update database (runs crowd counting internally)
curl -X POST http://localhost:8000/db/update \
  -H "Content-Type: application/json" \
  -d '{"service": "9am"}'
```

**Windows (PowerShell):**
```powershell
# Start crowd counting
Invoke-RestMethod -Uri "http://localhost:8000/start" -Method GET

# Check process status  
Invoke-RestMethod -Uri "http://localhost:8000/status" -Method GET

# Get detailed logs
Invoke-RestMethod -Uri "http://localhost:8000/logs" -Method GET

# Health check
Invoke-RestMethod -Uri "http://localhost:8000/health" -Method GET

# Update from GitHub  
Invoke-RestMethod -Uri "http://localhost:8000/update" -Method GET

# Send custom email
Invoke-RestMethod -Uri "http://localhost:8000/email" -Method POST -Body (@{
    receiver = "user@example.com,user2@example.com"
} | ConvertTo-Json) -ContentType "application/json"

# Send email to default receivers (from .env EMAIL_RECEIVER)
Invoke-RestMethod -Uri "http://localhost:8000/email" -Method POST -Body (@{
} | ConvertTo-Json) -ContentType "application/json"

# Update database (runs crowd counting internally)
Invoke-RestMethod -Uri "http://localhost:8000/db/update" -Method POST -Body (@{
    service = "9am"
} | ConvertTo-Json) -ContentType "application/json"

### Using Docker Compose

Create a `docker-compose.yml` file:

```yaml
version: '3.8'
services:
  crowd-counter:
    image: cwhitio/crowd-counter:v2.15
    container_name: crowd-counter
    environment:
      - CAMERA_IP=192.168.1.100
      - CAMERA_USER=admin
      - CAMERA_PASS=password
      - EMAIL_RECEIVER=your_email@example.com
      - EMAIL_API=your_mailtrap_api_token
    volumes:
      - ./models:/app/models
      - ./output:/app/output
```

Then run:
```bash
docker-compose up -d
# API server starts automatically - trigger via web API
curl http://localhost:8000/start
```

### Running Locally

Run the script to start capturing and processing images from the camera presets:

```bash
python run.py
```

- The script will create an output directory with a timestamp (e.g., `output/run_YYYYMMDD_HHMMSS`).
- Raw images, annotated images, and a CSV file with counts will be generated.
- Results are zipped and emailed to the configured recipient.

## Database Schema

The application uses SQLite to store service attendance data. The `service_counts` table has the following structure:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `date` | TEXT | Date of the service (YYYY-MM-DD format) |
| `weather` | TEXT | Weather conditions (optional) |
| `temp` | REAL | Temperature (optional) |
| `service_9am_sanctuary` | INTEGER | Attendance count for 9:00 AM service |
| `service_1045am_sanctuary` | INTEGER | Attendance count for 10:45 AM service |
| `created_at` | TEXT | Record creation timestamp |

**Notes:**
- Each date can only have one record (UNIQUE constraint on date)
- If a record for the current date doesn't exist, it will be created
- If a record exists, it will be updated with the new service count
- Weather and temperature are optional and will update existing records

## Logging

Logs are saved to `ptz_capture.log` in the project directory and also printed to the console for real-time monitoring.

## Troubleshooting

- **Camera Connection Issues**: Ensure the camera IP and port are correct, and the camera supports VISCA commands.
- **Image Capture Failures**: Verify camera credentials and network connectivity.
- **Email Sending Errors**: Check Mailtrap API token and recipient email configuration.
- **Processing Errors**: Ensure the YOLO model path is correct and the model is trained for person detection.

## Docker

This application is available as a Docker image on Docker Hub: `cwhitio/crowd-counter:v2.15`

### Image Details
- **Base**: Ultralytics/ultralytics:latest-cpu (optimized ML environment)
- **Size**: ~2.9GB (includes PyTorch, OpenCV, YOLO pre-installed)
- **Includes**: All dependencies + pre-trained YOLO model from CDN
- **Architecture**: CPU-only (no GPU required)
- **Updates**: Automatically pulls latest code from GitHub during build
- **Latest Version**: v2.15 (includes automatic database updates and enhanced email API)

### Building Locally
```bash
git clone https://github.com/cwhit-io/crowd-counter.git
cd crowd-counter
docker build -t crowd-counter .
```

### Key Improvements
- **🚀 Faster builds**: Uses optimized Ultralytics base image (~50% faster)
- **📦 Self-contained**: YOLO model auto-downloaded from CDN
- **🔄 Always current**: Pulls latest code from GitHub during build
- **🌐 API-ready**: REST API server included for remote triggering
- ** Status monitoring**: Real-time process status and logging
- **🔧 Easy integration**: Simple HTTP endpoints for automation

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/your-feature-name`).
3. Commit your changes (`git commit -am 'Add some feature'`).
4. Push to the branch (`git push origin feature/your-feature-name`).
5. Create a new Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

For issues or contributions, please open an issue on this repository or contact the project maintainer.
