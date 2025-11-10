"""Image capture logic for PTZ camera presets."""
import logging
import os
import time
import requests
from .config import Config, PresetConfig


logger = logging.getLogger(__name__)


def capture_image(controller, preset_number, preset_name, output_dir, max_retries=3):
    """
    Capture image for a given preset using HTTP snapshot.
    
    Args:
        controller: PTZCameraController instance
        preset_number: Preset number to recall
        preset_name: Human-readable preset name
        output_dir: Base output directory
        max_retries: Number of capture attempts
    
    Returns:
        str: Path to captured image, or None on failure
    """
    logger.info(f"Recalling preset {preset_number} ({preset_name})")
    
    if not controller.recall_preset(preset_number):
        logger.error(f"Failed to recall preset {preset_number}")
        return None
    
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
    
    return None


def capture_all_presets(controller, presets, output_dir):
    """
    Capture images for all presets.
    
    Args:
        controller: PTZCameraController instance
        presets: List of (preset_number, preset_name) tuples
        output_dir: Base output directory
    
    Returns:
        tuple: (captured_images list, failed_presets list)
    """
    captured_images = []
    failed_presets = []

    for preset_number, preset_name in presets:
        try:
            image_path = capture_image(controller, preset_number, preset_name, output_dir)
            if image_path:
                captured_images.append(image_path)
            else:
                failed_presets.append(preset_number)
        except Exception as e:
            logger.error(f"Failed to capture preset {preset_number}: {str(e)}")
            failed_presets.append(preset_number)
    
    return captured_images, failed_presets
