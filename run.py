import base64
import csv
import json
import logging
import os
import shutil
import socket
import sqlite3
import sys
import time
import zipfile
from datetime import datetime
import multiprocessing
from multiprocessing import Process, Queue, cpu_count
import cv2
import numpy as np
import requests
from sklearn.cluster import DBSCAN
from ultralytics import YOLO
import mailtrap as mt

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("ptz_capture.log")
    ]
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment Variable Loading
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info("✅ Loaded environment variables from .env file")
except ImportError:
    logger.warning("⚠️ python-dotenv not installed. Install with: pip install python-dotenv")
    logger.warning("⚠️ Using default values or system environment variables")

# ---------------------------------------------------------------------------
# Configuration (from environment with fallbacks)
# ---------------------------------------------------------------------------
CAMERA_IP = os.getenv("CAMERA_IP", "192.168.0.100")
VISCA_PORT = int(os.getenv("VISCA_PORT", "5678"))
CAMERA_USER = os.getenv("CAMERA_USER", "admin")
CAMERA_PASS = os.getenv("CAMERA_PASS", "admin")

MODEL_PATH = os.getenv("MODEL_PATH", "models/best.pt")
INFER_CONF = float(os.getenv("INFER_CONF", "0.25"))
INFER_IOU = float(os.getenv("INFER_IOU", "0.45"))
CLUSTER_EPS = int(os.getenv("CLUSTER_EPS", "50"))
MIN_CLUSTER_SIZE = int(os.getenv("MIN_CLUSTER_SIZE", "2"))
DEFAULT_BATCH_SIZE = int(os.getenv("BATCH_SIZE", "4"))  # Not directly used
DEFAULT_NUM_WORKERS = int(os.getenv("NUM_WORKERS", "4"))

OUTPUT_BASE_DIR = "output"

# Email Configuration
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "name@email.com")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "name@email.com")
EMAIL_API = os.getenv("EMAIL_API", "YOUR_MAILTRAP_API_KEY")

# Preset configuration
PRESET_CONFIG_FILE = os.getenv("PRESET_CONFIG_FILE", "preset_config.json")
PRESETS = []
PRESET_MAP = {}

try:
    with open(PRESET_CONFIG_FILE, "r") as f:
        config = json.load(f)
        presets_data = config.get("presets", [])
        PRESETS = [preset["number"] for preset in presets_data]
        PRESET_MAP = {
            preset["number"]: preset.get("name", f"Preset {preset['number']}")
            for preset in presets_data
        }
        logger.info(f"Loaded {len(PRESETS)} presets from {PRESET_CONFIG_FILE}: {PRESETS}")
        logger.info(f"Preset names mapped: {list(PRESET_MAP.values())}")
except Exception as e:
    logger.error(f"Error loading preset configuration: {str(e)}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# PTZ Camera Controller
# ---------------------------------------------------------------------------
class PTZCameraController:
    """Controller for sending VISCA over IP commands to the PTZ camera."""

    def __init__(self, camera_ip, camera_user="admin", camera_pass="admin", visca_port=5678):
        self.camera_ip = camera_ip
        self.camera_user = camera_user
        self.camera_pass = camera_pass
        self.visca_port = visca_port
        self.socket_timeout = 15.0  # Increased timeout
        logger.info(f"Initialized PTZ Controller for {camera_ip}:{visca_port}")

    def send_visca_command(self, command_bytes, description=""):
        """
        Send a VISCA command to the camera with retries.
        Returns True on success, False on failure.
        """
        sock = None
        max_retries = 2

        for attempt in range(max_retries):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.socket_timeout)

                logger.debug(f"Attempt {attempt + 1}: Connecting to {self.camera_ip}:{self.visca_port}")
                sock.connect((self.camera_ip, self.visca_port))

                command_hex = " ".join(f"{b:02X}" for b in command_bytes)
                logger.debug(f"Sending VISCA command ({description}): {command_hex}")
                sock.send(command_bytes)

                response = sock.recv(1024)
                if response:
                    response_hex = " ".join(f"{b:02X}" for b in response)
                    logger.debug(f"Received response: {response_hex}")

                    if len(response) >= 3 and response[0] == 0x90:
                        high = response[1] & 0xF0
                        if high == 0x40:  # ACK
                            logger.debug("Command acknowledged, waiting for completion...")
                            try:
                                completion = sock.recv(1024)
                                if completion:
                                    comp_hex = " ".join(f"{b:02X}" for b in completion)
                                    logger.debug(f"Completion response: {comp_hex}")
                                    if (completion[1] & 0xF0) == 0x50:  # Completion
                                        logger.debug("Command completed successfully")
                                        return True
                            except socket.timeout:
                                logger.warning("Timeout waiting for completion message")
                                return True  # Assume success after ACK
                        elif high == 0x50:  # Immediate completion
                            logger.debug("Command completed immediately")
                            return True
                        elif high == 0x60:  # Error
                            error_code = response[2] if len(response) > 2 else 0
                            error_msg = {
                                0x02: "Syntax Error",
                                0x03: "Command Buffer Full",
                                0x04: "Command Canceled",
                                0x05: "No Socket",
                                0x41: "Command Not Executable"
                            }.get(error_code, f"Unknown Error ({error_code:02X})")
                            logger.error(f"VISCA Error: {error_msg}")
                            return False
                logger.warning(f"Unexpected or no response on attempt {attempt + 1}")
            except socket.timeout:
                logger.warning(f"Socket timeout on attempt {attempt + 1}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to send command after {max_retries} attempts")
                    return False
            except Exception as e:
                logger.error(f"Socket error on attempt {attempt + 1}: {str(e)}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed after {max_retries} attempts")
                    return False
            finally:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass
            time.sleep(1)
        return False

    def recall_preset(self, preset_number):
        """Recall a preset position (1-256)."""
        if not 1 <= preset_number <= 256:
            logger.error(f"Invalid preset number: {preset_number}. Must be 1-256.")
            return False
        command = bytes([0x81, 0x01, 0x04, 0x3F, 0x02, preset_number & 0xFF, 0xFF])
        return self.send_visca_command(command, f"Recall Preset {preset_number}")


# ---------------------------------------------------------------------------
# Image Capture
# ---------------------------------------------------------------------------
def capture_image(controller, preset_number, preset_name, output_dir, max_retries=3):
    """
    Capture image for a given preset using HTTP snapshot.
    Returns image path or None.
    """
    logger.info(f"Recalling preset {preset_number} ({preset_name})")
    if controller.recall_preset(preset_number):
        time.sleep(1)  # Allow camera to move/stabilize
        raw_image_path = os.path.join(
            output_dir,
            "raw_images",
            f"preset_{preset_number:03d}_{preset_name.replace(' ', '_')}.jpg"
        )
        os.makedirs(os.path.dirname(raw_image_path), exist_ok=True)

        snapshot_url = f"http://{controller.camera_ip}/snapshot.jpg"

        for attempt in range(max_retries):
            try:
                logger.info(f"Capturing image for preset {preset_number} (Attempt {attempt + 1}/{max_retries})")
                response = requests.get(
                    snapshot_url,
                    auth=(controller.camera_user, controller.camera_pass),
                    timeout=10
                )
                if response.status_code == 200:
                    with open(raw_image_path, "wb") as f:
                        f.write(response.content)
                    logger.info(f"Captured image for preset {preset_number} at {raw_image_path}")
                    return raw_image_path
                else:
                    logger.error(
                        f"Failed to capture image for preset {preset_number}: "
                        f"HTTP {response.status_code} (Attempt {attempt + 1}/{max_retries})"
                    )
                    if attempt == max_retries - 1:
                        logger.error(
                            f"Failed to capture image for preset {preset_number} after {max_retries} attempts"
                        )
                        return None
            except requests.exceptions.RequestException as e:
                logger.error(
                    f"Error capturing image for preset {preset_number}: {str(e)} "
                    f"(Attempt {attempt + 1}/{max_retries})"
                )
                if attempt == max_retries - 1:
                    logger.error(
                        f"Failed to capture image for preset {preset_number} after {max_retries} attempts"
                    )
                    return None
            time.sleep(0.5)
    else:
        logger.error(f"Failed to recall preset {preset_number}")
    return None


# ---------------------------------------------------------------------------
# Worker Processing
# ---------------------------------------------------------------------------
def process_image_worker(image_queue, result_queue, model_path, output_dir):
    """
    Worker function to process images:
    - Runs YOLO inference
    - Clusters detections
    - Annotates images
    - Sends results to result_queue
    NOTE: Model is loaded per image (original behavior retained).
    """
    logger.info("Starting image processing worker")
    while True:
        image_path = image_queue.get()
        if image_path is None:
            logger.info("Worker received stop signal")
            break
        try:
            logger.info(f"Processing image: {image_path}")
            model = YOLO(model_path)  # (Kept inside loop to avoid functional change)

            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"Failed to load image: {image_path}")
                result_queue.put({
                    "preset": os.path.basename(image_path),
                    "count": 0,
                    "error": "Failed to load image"
                })
                continue

            # Run inference
            results = model.predict(img, conf=INFER_CONF, iou=INFER_IOU, verbose=False)
            boxes = (
                results[0].boxes.xyxy.cpu().numpy()
                if len(results[0].boxes) > 0
                else np.array([])
            )

            # Cluster & count
            count = 0
            if len(boxes) > 0:
                centers = np.array([(box[0] + box[2]) / 2 for box in boxes])
                if len(centers) >= MIN_CLUSTER_SIZE:
                    clustering = DBSCAN(
                        eps=CLUSTER_EPS,
                        min_samples=MIN_CLUSTER_SIZE
                    ).fit(centers.reshape(-1, 1))
                    count = len(set(clustering.labels_)) - (1 if -1 in clustering.labels_ else 0)
                else:
                    count = len(centers)

            # Draw boxes & count
            annotated_img = img.copy()
            for box in boxes:
                x1, y1, x2, y2 = map(int, box[:4])
                cv2.rectangle(annotated_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    annotated_img,
                    "Person",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2
                )
            cv2.putText(
                annotated_img,
                f"Count: {count}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2
            )

            # --- NEW: extract both preset number and name from filename ---
            # filename example: "preset_010_Balcony_Left_1.jpg"
            filename = os.path.basename(image_path)
            name_part = filename.removeprefix("preset_").rsplit(".", 1)[0]
            preset_num, preset_name_safe = name_part.split("_", 1)
            # Build output filename: annotated_preset_<num>_<name>.jpg
            annotated_filename = f"{preset_name_safe}_{preset_num}.jpg"
            annotated_path = os.path.join(
                output_dir,
                "annotated_images",
                annotated_filename
            )
            os.makedirs(os.path.dirname(annotated_path), exist_ok=True)
            cv2.imwrite(
                annotated_path,
                annotated_img,
                [int(cv2.IMWRITE_JPEG_QUALITY), 70]
            )
            logger.info(
                f"Saved annotated image to {annotated_path}, Count: {count}"
            )

            # Push result
            result_queue.put({
                "preset": preset_num,
                "name": preset_name_safe.replace("_", " "),
                "count": count,
                "annotated_path": annotated_path
            })

        except Exception as e:
            logger.error(f"Error processing {image_path}: {str(e)}")
            result_queue.put({
                "preset": os.path.basename(image_path),
                "count": 0,
                "error": str(e)
            })



# ---------------------------------------------------------------------------
# Zip Creation
# ---------------------------------------------------------------------------
def create_zip_file(output_dir, run_id, annotated_dir, csv_path):
    """
    Create a zip file containing annotated images and CSV results.
    Returns path to created zip.
    """
    zip_path = os.path.join(output_dir, f"ptz_capture_results_{run_id}.zip")
    logger.info(f"Creating zip file: {zip_path}")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(annotated_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, start=output_dir)
                zipf.write(file_path, arcname)
                logger.info(f"Added {arcname} to zip")

        arcname = os.path.relpath(csv_path, start=output_dir)
        zipf.write(csv_path, arcname)
        logger.info(f"Added {arcname} to zip")

    logger.info(f"Zip file created successfully: {zip_path}")
    return zip_path


# ---------------------------------------------------------------------------
# Email Sending
# ---------------------------------------------------------------------------
def send_email(zip_path, run_id, total_count):
    """
    Send email with zip attachment via Mailtrap.
    Attachment content is base64 encoded.
    """
    logger.info(f"Preparing email with attachment via Mailtrap: {zip_path}")

    run_datetime = datetime.strptime(run_id, "%Y%m%d_%H%M%S").strftime("%B %d, %Y at %I:%M %p")

    body = f"""
    Hello,

    Your PTZ camera capture has completed successfully! Here are the results:

    📊 Summary:
    • Capture completed on: {run_datetime}
    • Total people counted: {total_count}

    📁 The attached zip file includes:
    • Annotated images showing detected people
    • A CSV file with detailed counting results

    📦 To access the files, please download the attachment and unzip it on your computer.

    Best regards,
    PTZ Capture System
    """

    try:
        with open(zip_path, "rb") as zip_file:
            zip_content = zip_file.read()
        logger.info(f"Successfully read zip file content for attachment: {len(zip_content)} bytes")

        zip_content_base64 = base64.b64encode(zip_content)
        logger.info("Successfully encoded zip content to base64")

        # Handle multiple email recipients separated by commas
        email_recipients = [email.strip() for email in EMAIL_RECEIVER.split(',') if email.strip()]
        recipient_addresses = [mt.Address(email=email) for email in email_recipients]
        
        # Format date for subject line
        run_date = datetime.strptime(run_id, "%Y%m%d_%H%M%S").strftime("%B %d, %Y")

        mail = mt.Mail(
            sender=mt.Address(email=EMAIL_SENDER, name="Blackhawk Crowd Counter"),
            to=recipient_addresses,
            subject=f"Crowd Count: {total_count} people detected on {run_date}",
            text=body,
            category="PTZ Capture Results",
            attachments=[
                mt.Attachment(
                    content=zip_content_base64,
                    filename=os.path.basename(zip_path),
                    disposition=mt.Disposition.ATTACHMENT,
                    mimetype="application/zip"
                )
            ]
        )

        client = mt.MailtrapClient(token=EMAIL_API)
        response = client.send(mail)
        logger.info(f"Email sent successfully via Mailtrap. Response: {response}")
        return True
    except UnicodeDecodeError as ude:
        logger.error(f"Encoding error while processing attachment: {str(ude)}")
    except FileNotFoundError as fnf:
        logger.error(f"Zip file not found: {str(fnf)}")
    except Exception as e:
        logger.error(f"Failed to send email via Mailtrap: {str(e)}")
    return False


# ---------------------------------------------------------------------------
# Database Update Function
# ---------------------------------------------------------------------------
def update_service_count(total_count, service_time=None):
    """Update the service attendance database with the total count"""
    try:
        # Determine service time if not provided
        if not service_time:
            service_time = os.getenv("SERVICE_TIME", "").lower().strip()
            if not service_time:
                # Auto-determine based on current time (9am service before 10am, 1045am service after 10am)
                current_hour = datetime.now().hour
                if current_hour < 10:
                    service_time = "9am"
                else:
                    service_time = "1045am"
                logger.info(f"Auto-determined service time: {service_time} (current hour: {current_hour})")
            else:
                logger.info(f"Using configured service time: {service_time}")

        # Validate service time
        if service_time not in ['9am', '1045am']:
            logger.error(f"Invalid service time: {service_time}. Must be '9am' or '1045am'")
            return False

        # Get current date and database path
        current_date = datetime.now().strftime('%Y-%m-%d')
        db_path = os.getenv("DATABASE_PATH", "/app/crowd_counter.db")

        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS service_counts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                weather TEXT,
                temp REAL,
                service_9am_sanctuary INTEGER,
                service_1045am_sanctuary INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date)
            )
        ''')

        # Check if record for today exists
        cursor.execute('SELECT id FROM service_counts WHERE date = ?', (current_date,))
        existing_record = cursor.fetchone()

        if existing_record:
            # Update existing record
            if service_time == '9am':
                cursor.execute('''
                    UPDATE service_counts
                    SET service_9am_sanctuary = ?
                    WHERE date = ?
                ''', (total_count, current_date))
            else:  # 1045am
                cursor.execute('''
                    UPDATE service_counts
                    SET service_1045am_sanctuary = ?
                    WHERE date = ?
                ''', (total_count, current_date))

            action = "updated"
        else:
            # Insert new record
            if service_time == '9am':
                cursor.execute('''
                    INSERT INTO service_counts (date, service_9am_sanctuary)
                    VALUES (?, ?)
                ''', (current_date, total_count))
            else:  # 1045am
                cursor.execute('''
                    INSERT INTO service_counts (date, service_1045am_sanctuary)
                    VALUES (?, ?)
                ''', (current_date, total_count))

            action = "inserted"

        conn.commit()
        conn.close()

        logger.info(f"✅ Service count {action} for {service_time} service: {total_count} attendees on {current_date}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to update service count in database: {str(e)}")
        return False


# ---------------------------------------------------------------------------
# Main Orchestration
# ---------------------------------------------------------------------------
def main():
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(OUTPUT_BASE_DIR, f"run_{run_id}")
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")

    controller = PTZCameraController(CAMERA_IP, CAMERA_USER, CAMERA_PASS, VISCA_PORT)

    presets = [(p, PRESET_MAP.get(p, f"Preset {p}")) for p in PRESETS]
    logger.info(f"Processing presets: {[p[0] for p in presets]}")

    # Multiprocessing setup
    try:
        multiprocessing.set_start_method("spawn")
    except AttributeError:
        logger.warning("Multiprocessing start method 'spawn' not supported on this platform")

    image_queue = Queue()
    result_queue = Queue()
    num_workers = min(cpu_count(), DEFAULT_NUM_WORKERS)
    workers = []

    logger.info(f"Starting {num_workers} image processing workers")
    for _ in range(num_workers):
        p = Process(
            target=process_image_worker,
            args=(image_queue, result_queue, MODEL_PATH, output_dir)
        )
        p.start()
        workers.append(p)

    captured_images = []
    failed_presets = []

    for preset_number, preset_name in presets:
        try:
            image_path = capture_image(controller, preset_number, preset_name, output_dir)
            if image_path:
                captured_images.append(image_path)
                image_queue.put(image_path)
            else:
                failed_presets.append(preset_number)
        except Exception as e:
            logger.error(f"Failed to capture preset {preset_number}: {str(e)}")
            failed_presets.append(preset_number)

    logger.info("Capture complete. Sending stop signals to workers.")
    for _ in range(num_workers):
        image_queue.put(None)

    for w in workers:
        w.join()
    logger.info("All processing workers have completed.")

    results = []
    while not result_queue.empty():
        results.append(result_queue.get())

    results_dir = os.path.join(output_dir, "results")
    os.makedirs(results_dir, exist_ok=True)
    csv_path = os.path.join(results_dir, "count_results.csv")

    total_count = 0
    with open(csv_path, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Preset", "Name", "Count"])
        for r in results:
            if "count" in r and "error" not in r:
                total_count += r["count"]
                # NOTE: This parsing logic is retained exactly.
                preset_num = r["preset"].split('_')[0] if '_' in r["preset"] else r["preset"]
                writer.writerow([
                    preset_num,
                    PRESET_MAP.get(int(preset_num), f"Preset {preset_num}"),
                    r["count"]
                ])

    logger.info(f"Results saved to {csv_path} with total count: {total_count}")
    logger.info(f"Processing complete. Captured: {len(captured_images)}, Failed: {len(failed_presets)}")

    # Update database with service attendance count
    db_updated = update_service_count(total_count)
    if db_updated:
        logger.info("✅ Service attendance count successfully saved to database")
    else:
        logger.warning("⚠️ Failed to save service attendance count to database")

    raw_dir = os.path.join(output_dir, "raw_images")
    if os.path.exists(raw_dir):
        shutil.rmtree(raw_dir, ignore_errors=True)
        logger.info(f"Cleaned up raw images directory: {raw_dir}")

    annotated_dir = os.path.join(output_dir, "annotated_images")
    if os.path.exists(annotated_dir):
        zip_path = create_zip_file(output_dir, run_id, annotated_dir, csv_path)
        if zip_path:
            sent = send_email(zip_path, run_id, total_count)
            if sent:
                logger.info("Results successfully zipped and emailed")
            else:
                logger.error("Failed to send email with results")
    else:
        logger.warning("No annotated images directory found, skipping zip and email")


if __name__ == "__main__":
    main()
