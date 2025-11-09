#!/usr/bin/env python3
"""
Simple API server for crowd-counter application
Provides endpoints to trigger crowd counting and check status
"""

import os
import sys
import json
import subprocess
import threading
import time
import sqlite3
from datetime import datetime
from flask import Flask, jsonify, request
import logging
import mailtrap as mt

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global variables to track running processes
current_process = None
process_status = "idle"
last_run = None
process_output = []

def run_crowd_counter():
    """Run the crowd counting script in a separate thread"""
    global current_process, process_status, last_run, process_output
    
    try:
        process_status = "running"
        last_run = datetime.now().isoformat()
        process_output = []
        
        logger.info("Starting crowd counting process...")
        
        # Run the main script with real-time output streaming
        current_process = subprocess.Popen(
            [sys.executable, "run.py"],
            cwd="/app",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True
        )
        
        # Stream output in real-time
        output_lines = []
        while True:
            output = current_process.stdout.readline()
            if output == '' and current_process.poll() is not None:
                break
            if output:
                output_line = output.strip()
                print(f"[CROWD-COUNTER] {output_line}")  # Print to Docker terminal
                logger.info(f"run.py: {output_line}")     # Also log it
                output_lines.append(output_line)
        
        # Wait for process to complete and get return code
        return_code = current_process.wait()
        
        # Store the output for API access
        process_output = output_lines
        process_output.append(f"Exit code: {return_code}")
            
        if return_code == 0:
            process_status = "completed"
            logger.info("Crowd counting completed successfully")
        else:
            process_status = "failed"
            logger.error(f"Crowd counting failed with code {return_code}")
            
    except subprocess.TimeoutExpired:
        if current_process:
            current_process.kill()
        process_status = "timeout"
        logger.error("Crowd counting process timed out")
    except Exception as e:
        if current_process:
            current_process.kill()
        process_status = "error"
        process_output.append(f"Error: {str(e)}")
        logger.error(f"Error running crowd counter: {e}")
    finally:
        current_process = None

@app.route("/")
def home():
    """Health check endpoint"""
    return jsonify({
        "service": "crowd-counter-api",
        "status": "healthy",
        "version": "1.0",
        "endpoints": {
            "/start": "GET - Start crowd counting",
            "/status": "GET - Check process status",
            "/logs": "GET - Get recent logs",
            "/health": "GET - Health check",
            "/update": "GET - Update from GitHub",
            "/email": "POST - Send email with custom receiver(s) or default from .env",
            "/db/update": "POST - Update database table"
        }
    })

@app.route("/health")
def health():
    """Detailed health check"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "process_status": process_status,
        "last_run": last_run,
        "uptime": time.time()
    })

@app.route("/start", methods=["GET"])
def start_crowd_counting():
    """Start the crowd counting process"""
    global current_process, process_status
    
    if process_status == "running":
        return jsonify({
            "error": "Process already running",
            "status": process_status,
            "started_at": last_run
        }), 409
    
    # Start the process in a separate thread
    thread = threading.Thread(target=run_crowd_counter)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "message": "Crowd counting started",
        "status": "running", 
        "started_at": datetime.now().isoformat()
    })

@app.route("/status")
def get_status():
    """Get current process status"""
    return jsonify({
        "status": process_status,
        "last_run": last_run,
        "timestamp": datetime.now().isoformat()
    })

@app.route("/logs")
def get_logs():
    """Get process logs"""
    return jsonify({
        "status": process_status,
        "last_run": last_run,
        "output": process_output,
        "timestamp": datetime.now().isoformat()
    })

@app.route("/trigger", methods=["GET"])
def trigger_counting():
    """Alternative endpoint name for starting process"""
    return start_crowd_counting()

@app.route("/email", methods=["POST"])
def send_custom_email():
    """Send email with custom receiver(s) or default from environment"""
    try:
        data = request.get_json()
        
        # Get receivers - either from API request or environment default
        receivers = []
        if data and 'receiver' in data:
            # API can pass single email or comma-separated list
            receiver_input = data['receiver']
            if isinstance(receiver_input, str):
                # Split by comma and clean up whitespace
                receivers = [email.strip() for email in receiver_input.split(',') if email.strip()]
            elif isinstance(receiver_input, list):
                receivers = receiver_input
        else:
            # Use default from environment
            default_receiver = os.getenv("EMAIL_RECEIVER", "")
            if default_receiver:
                receivers = [email.strip() for email in default_receiver.split(',') if email.strip()]
        
        if not receivers:
            return jsonify({
                "error": "No receivers specified. Set EMAIL_RECEIVER in environment or pass 'receiver' in request body",
                "example": {
                    "receiver": "user@example.com,user2@example.com",
                    "subject": "Custom Subject (optional)",
                    "message": "Custom message (optional)"
                }
            }), 400
        
        subject = data.get('subject', 'Crowd Counter Notification') if data else 'Crowd Counter Notification'
        message = data.get('message', 'This is a notification from the Crowd Counter API.') if data else 'This is a notification from the Crowd Counter API.'
        
        # Get email configuration from environment
        email_sender = os.getenv("EMAIL_SENDER", "no-reply@example.org")
        email_api = os.getenv("EMAIL_API", "")
        
        if not email_api:
            return jsonify({
                "error": "Email API key not configured",
                "note": "Set EMAIL_API environment variable"
            }), 500
        
        # Convert receivers to Mailtrap Address objects
        recipient_addresses = [mt.Address(email=email) for email in receivers]
        
        # Send email via Mailtrap
        mail = mt.Mail(
            sender=mt.Address(email=email_sender, name="Crowd Counter API"),
            to=recipient_addresses,
            subject=subject,
            text=message,
            category="API Notification"
        )
        
        client = mt.MailtrapClient(token=email_api)
        response = client.send(mail)
        
        logger.info(f"Email sent successfully to {len(receivers)} recipient(s): {', '.join(receivers)}")
        return jsonify({
            "message": f"Email sent successfully to {len(receivers)} recipient(s)",
            "recipients": receivers,
            "subject": subject,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return jsonify({
            "error": f"Failed to send email: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route("/update", methods=["GET"])
def update_from_git():
    """Update the application from GitHub"""
    try:
        logger.info("Starting Git update process...")
        
        # Run the update script with real-time output streaming
        process = subprocess.Popen(
            [sys.executable, "update.py"],
            cwd="/app",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Stream output in real-time
        output_lines = []
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                output_line = output.strip()
                print(f"[UPDATE] {output_line}")  # Print to Docker terminal
                logger.info(f"update.py: {output_line}")  # Also log it
                output_lines.append(output_line)
        
        # Wait for process to complete
        return_code = process.wait()
        
        if return_code == 0:
            logger.info("Git update completed successfully")
            return jsonify({
                "message": "Update completed successfully (includes git pull + pip install)",
                "status": "success",
                "output": output_lines,
                "timestamp": datetime.now().isoformat(),
                "note": "Code updated and requirements installed - restart container if needed"
            })
        else:
            logger.error(f"Git update failed with code {return_code}")
            return jsonify({
                "error": "Update failed",
                "status": "failed",
                "exit_code": return_code,
                "output": output_lines,
                "timestamp": datetime.now().isoformat()
            }), 500
            
    except subprocess.TimeoutExpired:
        logger.error("Git update process timed out")
        return jsonify({
            "error": "Update process timed out",
            "status": "timeout",
            "timestamp": datetime.now().isoformat()
        }), 408
    except Exception as e:
        logger.error(f"Error during Git update: {e}")
        return jsonify({
            "error": f"Update failed: {str(e)}",
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route("/db/update", methods=["POST"])
def update_database():
    """Update database table with provided data"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "error": "Missing request body",
                "example": {
                    "table": "crowd_counts",
                    "data": {
                        "preset_id": 1,
                        "count": 25,
                        "timestamp": "2025-11-09T10:00:00"
                    }
                }
            }), 400
        
        table_name = data.get('table', 'crowd_counts')
        record_data = data.get('data', {})
        
        if not record_data:
            return jsonify({
                "error": "Missing 'data' field in request body"
            }), 400
        
        # Get database configuration from environment
        db_path = os.getenv("DATABASE_PATH", "/app/crowd_counter.db")
        
        # Connect to SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create table if it doesn't exist (basic schema)
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                preset_id INTEGER,
                count INTEGER,
                timestamp TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Prepare insert statement
        columns = ', '.join(record_data.keys())
        placeholders = ', '.join(['?' for _ in record_data])
        values = list(record_data.values())
        
        # Add created_at if not provided
        if 'created_at' not in record_data:
            columns += ', created_at'
            placeholders += ', ?'
            values.append(datetime.now().isoformat())
        
        cursor.execute(f'''
            INSERT INTO {table_name} ({columns})
            VALUES ({placeholders})
        ''', values)
        
        # Get the ID of the inserted record
        record_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        logger.info(f"Database record inserted into {table_name} with ID {record_id}")
        return jsonify({
            "message": f"Record inserted successfully into {table_name}",
            "record_id": record_id,
            "table": table_name,
            "data": record_data,
            "timestamp": datetime.now().isoformat()
        })
        
    except sqlite3.Error as e:
        logger.error(f"Database error: {str(e)}")
        return jsonify({
            "error": f"Database error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }), 500
    except Exception as e:
        logger.error(f"Failed to update database: {str(e)}")
        return jsonify({
            "error": f"Failed to update database: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }), 500

if __name__ == "__main__":
    port = int(os.getenv("API_PORT", "8000"))
    debug = os.getenv("API_DEBUG", "false").lower() == "true"
    
    logger.info(f"Starting Crowd Counter API on port {port}")
    logger.info("Available endpoints:")
    logger.info("  GET  /         - Service info")
    logger.info("  GET  /health   - Health check")
    logger.info("  GET  /start    - Start crowd counting")
    logger.info("  GET  /trigger  - Start crowd counting (alias)")
    logger.info("  POST /email    - Send email with custom receiver")
    logger.info("  POST /db/update - Update database table")
    logger.info("  GET  /update   - Update from GitHub")
    logger.info("  GET  /status   - Process status")
    logger.info("  GET  /logs     - Process logs")
    
    app.run(host="0.0.0.0", port=port, debug=debug)