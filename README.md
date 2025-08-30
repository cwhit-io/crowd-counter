# PTZ Camera Capture and Analysis System

This project is designed to control a PTZ (Pan-Tilt-Zoom) camera, capture images from predefined preset positions, process these images using a YOLO model to detect and count people, and send the results via email. The system supports parallel image processing for efficiency and logs all operations for debugging and monitoring.

## Features

- **Camera Control**: Communicates with a PTZ camera using VISCA commands over a socket connection.
- **Image Capture**: Captures images from specified preset positions via HTTP requests.
- **Object Detection**: Uses a YOLO model to detect people in captured images.
- **Clustering**: Applies DBSCAN clustering to count distinct groups of people.
- **Parallel Processing**: Processes images concurrently using multiprocessing.
- **Result Compilation**: Saves annotated images and counts to a CSV file.
- **Email Notification**: Zips results and sends them via email using the Mailtrap API.

## Requirements

- Python 3.8 or higher
- A PTZ camera accessible over a network with VISCA protocol support
- A trained YOLO model for person detection (e.g., `best.pt`)

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

Run the script to start capturing and processing images from the camera presets:

```bash
python ptz_capture.py
```

- The script will create an output directory with a timestamp (e.g., `output/run_YYYYMMDD_HHMMSS`).
- Raw images, annotated images, and a CSV file with counts will be generated.
- Results are zipped and emailed to the configured recipient.

## Output Structure

- `output/run_YYYYMMDD_HHMMSS/`
  - `annotated_images/`: Images with detection annotations
  - `results/count_results.csv`: CSV file with preset numbers, names, and people counts
  - `ptz_capture_results_YYYYMMDD_HHMMSS.zip`: Zipped results sent via email

## Logging

Logs are saved to `ptz_capture.log` in the project directory and also printed to the console for real-time monitoring.

## Troubleshooting

- **Camera Connection Issues**: Ensure the camera IP and port are correct, and the camera supports VISCA commands.
- **Image Capture Failures**: Verify camera credentials and network connectivity.
- **Email Sending Errors**: Check Mailtrap API token and recipient email configuration.
- **Processing Errors**: Ensure the YOLO model path is correct and the model is trained for person detection.

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
