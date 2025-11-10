"""PTZ Crowd Counter - Main orchestration script."""
import argparse
import logging
import os
import shutil
import sys
from datetime import datetime
from multiprocessing import Queue, cpu_count
import multiprocessing

# Import from modules package
from modules import (
    PTZCameraController,
    capture_all_presets,
    start_processing_workers,
    stop_workers,
    collect_results,
    Config,
    PresetConfig,
    generate_report,
    update_attendance_from_last_run
)

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


def main():
    """Main orchestration function."""
    # Parse arguments
    parser = argparse.ArgumentParser(
        description='PTZ Crowd Counter - Automated people counting system',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/main.py                                    # Run without email
  python src/main.py --send-email                       # Run and send email
  python src/main.py --send-email --email-receivers "person1@email.com,person2@email.com"
  python src/main.py --hour 9am                         # Run and track 9am service attendance
  python src/main.py --send-email --hour 1045am         # Run, send email, and track 10:45am service
        """
    )
    parser.add_argument(
        '--send-email',
        action='store_true',
        help='Send email with results after processing'
    )
    parser.add_argument(
        '--email-receivers',
        help='Comma-separated list of email receivers (overrides .env setting)'
    )
    parser.add_argument(
        '--hour',
        choices=['9am', '1045am'],
        help='Service hour for attendance tracking (9am or 1045am)'
    )
    args = parser.parse_args()
    
    # Validate configuration
    logger.info("Validating configuration...")
    Config.validate()
    
    # Setup run
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(Config.OUTPUT_BASE_DIR, f"run_{run_id}")
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info("=" * 60)
    logger.info(f"Starting crowd counter run: {run_id}")
    logger.info(f"Output directory: {output_dir}")
    logger.info("=" * 60)
    
    # Load presets
    logger.info("Loading preset configuration...")
    preset_config = PresetConfig()
    presets = preset_config.get_presets()
    logger.info(f"Loaded {len(presets)} presets: {preset_config.get_preset_numbers()}")
    
    # Initialize camera controller
    logger.info("Initializing camera controller...")
    cam_config = Config.get_camera_config()
    controller = PTZCameraController(
        cam_config["ip"],
        cam_config["user"],
        cam_config["password"],
        cam_config["port"]
    )
    
    # Multiprocessing setup
    try:
        multiprocessing.set_start_method("spawn")
    except RuntimeError:
        pass  # Already set
    
    image_queue = Queue()
    result_queue = Queue()
    num_workers = min(cpu_count(), Config.NUM_WORKERS)
    
    # Start processing workers
    logger.info(f"Starting {num_workers} processing workers...")
    model_config = Config.get_model_config()
    workers = start_processing_workers(
        num_workers, image_queue, result_queue,
        model_config["path"], output_dir,
        model_config["conf"], model_config["iou"],
        model_config["cluster_eps"], model_config["min_cluster_size"]
    )
    
    # Capture images
    logger.info("Starting image capture...")
    captured_images, failed_presets = capture_all_presets(controller, presets, output_dir)
    
    if failed_presets:
        logger.warning(f"⚠️  Failed to capture {len(failed_presets)} preset(s): {failed_presets}")
    logger.info(f"Capture complete: {len(captured_images)} successful, {len(failed_presets)} failed")
    
    # Queue images for processing
    logger.info("Queuing images for processing...")
    for image_path in captured_images:
        image_queue.put(image_path)
    
    # Stop workers and collect results
    logger.info("Processing images with YOLO model...")
    stop_workers(workers, image_queue, num_workers)
    results = collect_results(result_queue)
    logger.info(f"Processing complete: {len(results)} results collected")
    
    # Generate report
    logger.info(" Generating report...")
    report = generate_report(
        output_dir=output_dir,
        run_id=run_id,
        results=results,
        preset_map=preset_config.get_preset_map(),
        email_config=Config.get_email_config(),
        send_email=args.send_email,
        receivers=args.email_receivers,
        hour=args.hour
    )
    
    # Update attendance database if hour is specified
    logger.info("Updating attendance database...")
    db_updated = update_attendance_from_last_run()
    if db_updated:
        logger.info("Attendance database updated successfully")
    else:
        logger.warning("Failed to update attendance database")
    
    # Cleanup raw images
    logger.info(" Cleaning up temporary files...")
    raw_dir = os.path.join(output_dir, "raw_images")
    if os.path.exists(raw_dir):
        shutil.rmtree(raw_dir, ignore_errors=True)
        logger.info(f"   Removed raw images directory")
    
    # Final summary
    logger.info("=" * 60)
    logger.info(f"Run {run_id} completed successfully!")
    logger.info(f" Total people counted: {report['total_count']}")
    logger.info(f"Results CSV: {report['csv_path']}")
    if report['zip_path']:
        logger.info(f"📦 Results ZIP: {report['zip_path']}")
    if report['email_sent']:
        logger.info(f"Email: Sent successfully")
    elif args.send_email:
        logger.warning(f"Email: Failed to send")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("\n  Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)
