"""Reporting functionality: CSV generation, zip creation, and email sending."""
import base64
import csv
import logging
import os
import zipfile
from datetime import datetime
from .config import Config, PresetConfig
import json  # Add this import at the top with other imports



import mailtrap as mt

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Handles result reporting: CSV, zip files, and email notifications."""
    
    def __init__(self, output_dir, run_id):
        self.output_dir = output_dir
        self.run_id = run_id
        self.results_dir = os.path.join(output_dir, "results")
        os.makedirs(self.results_dir, exist_ok=True)
    
    def save_to_csv(self, results, preset_map):
        """
        Save results to CSV file.
        
        Args:
            results: List of result dictionaries from processing
            preset_map: Dictionary mapping preset numbers to names
        
        Returns:
            tuple: (csv_path, total_count)
        """
        csv_path = os.path.join(self.results_dir, "count_results.csv")
        
        total_count = 0
        with open(csv_path, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Preset", "Name", "Count"])
            
            for r in results:
                if "count" in r and "error" not in r:
                    total_count += r["count"]
                    preset_num = r["preset"].split('_')[0] if '_' in r["preset"] else r["preset"]
                    preset_num_int = int(preset_num)
                    writer.writerow([
                        preset_num,
                        preset_map.get(preset_num_int, f"Preset {preset_num}"),
                        r["count"]
                    ])
        
        logger.info(f"Results saved to {csv_path} with total count: {total_count}")
        return csv_path, total_count
    
    def create_zip(self, annotated_dir, csv_path):
        """
        Create a zip file containing annotated images and CSV results.
        
        Args:
            annotated_dir: Directory containing annotated images
            csv_path: Path to CSV results file
        
        Returns:
            str: Path to created zip file
        """
        zip_path = os.path.join(self.output_dir, f"ptz_capture_results_{self.run_id}.zip")
        logger.info(f"Creating zip file: {zip_path}")
        
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Add annotated images
            for root, _, files in os.walk(annotated_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, start=self.output_dir)
                    zipf.write(file_path, arcname)
                    logger.debug(f"Added {arcname} to zip")
            
            # Add CSV
            arcname = os.path.relpath(csv_path, start=self.output_dir)
            zipf.write(csv_path, arcname)
            logger.debug(f"Added {arcname} to zip")
        
        logger.info(f"Zip file created successfully: {zip_path}")
        return zip_path


class EmailNotifier:
    """Handles email notifications via Mailtrap."""
    
    def __init__(self, sender, api_key):
        self.sender = sender
        self.api_key = api_key
        self.client = mt.MailtrapClient(token=api_key)
    
    def send_results(self, zip_path, run_id, total_count, receivers):
        """
        Send email with zip attachment.
        
        Args:
            zip_path: Path to zip file to attach
            run_id: Run identifier (timestamp format)
            total_count: Total people counted
            receivers: Comma-separated email addresses or single address
        
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        logger.info(f"Preparing email with attachment: {zip_path}")
        
        # Format datetime for display
        run_datetime = datetime.strptime(run_id, "%Y%m%d_%H%M%S").strftime("%B %d, %Y at %I:%M %p")
        run_date = datetime.strptime(run_id, "%Y%m%d_%H%M%S").strftime("%B %d, %Y")
        
        # Build email body
        body = self._build_email_body(run_datetime, total_count)
        
        try:
            # Read and encode zip file
            with open(zip_path, "rb") as zip_file:
                zip_content = zip_file.read()
            logger.info(f"Read zip file: {len(zip_content)} bytes")
            
            zip_content_base64 = base64.b64encode(zip_content)
            logger.debug("Encoded zip content to base64")
            
            # Parse recipients
            email_recipients = [email.strip() for email in receivers.split(',') if email.strip()]
            recipient_addresses = [mt.Address(email=email) for email in email_recipients]
            logger.info(f"Sending to {len(recipient_addresses)} recipient(s): {email_recipients}")
            
            # Build and send email
            mail = mt.Mail(
                sender=mt.Address(email=self.sender, name="Blackhawk Crowd Counter"),
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
            
            response = self.client.send(mail)
            logger.info(f"Email sent successfully. Response: {response}")
            return True
            
        except FileNotFoundError:
            logger.error(f"Zip file not found: {zip_path}")
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
        
        return False
    
    def _build_email_body(self, run_datetime, total_count):
        """Build the email body text."""
        return f"""
Hello,

Your PTZ camera capture has completed successfully! Here are the results:

 Summary:
• Capture completed on: {run_datetime}
• Total people counted: {total_count}

📁 The attached zip file includes:
• Annotated images showing detected people
• A CSV file with detailed counting results

📦 To access the files, please download the attachment and unzip it on your computer.

Best regards,
PTZ Capture System
"""


def generate_report(output_dir, run_id, results, preset_map, 
                   email_config=None, send_email=False, receivers=None, hour=None):
    """
    High-level function to generate complete report with optional email.
    
    Args:
        output_dir: Output directory for this run
        run_id: Run identifier
        results: Processing results
        preset_map: Preset number to name mapping
        email_config: Dict with 'sender' and 'api_key' keys
        send_email: Whether to send email notification
        receivers: Email recipients (defaults to email_config if None)
    
    Returns:
        dict: Report metadata (csv_path, zip_path, total_count, email_sent)
    """
    # Generate CSV
    reporter = ReportGenerator(output_dir, run_id)
    csv_path, total_count = reporter.save_to_csv(results, preset_map)
    
    # Create zip
    annotated_dir = os.path.join(output_dir, "annotated_images")
    zip_path = None
    email_sent = False
    
    if os.path.exists(annotated_dir):
        zip_path = reporter.create_zip(annotated_dir, csv_path)
        
        # Send email if requested
        if send_email and email_config and zip_path:
            if receivers is None:
                receivers = email_config.get("receiver")
            
            notifier = EmailNotifier(
                sender=email_config["sender"],
                api_key=email_config["api_key"]
            )
            email_sent = notifier.send_results(zip_path, run_id, total_count, receivers)
            
            if email_sent:
                logger.info("Results successfully zipped and emailed")
            else:
                logger.error("❌ Failed to send email with results")
        else:
            logger.info("📦 Results zipped (email not requested)")
    else:
        logger.warning("⚠️ No annotated images directory found, skipping zip creation")
    
    report_data = {
        "csv_path": csv_path,
        "zip_path": zip_path,
        "total_count": total_count,
        "email_sent": email_sent
    }
    
    # Add hour if specified
    if hour:
        report_data["hour"] = hour

    # Export to last_run.json
    last_run_path = os.path.join(os.path.dirname(output_dir), "last_run.json")
    with open(last_run_path, "w") as json_file:
        json.dump(report_data, json_file, indent=4)
    logger.info(f"Exported last run data to {last_run_path}")
    
    return report_data