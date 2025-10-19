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
from datetime import datetime
from flask import Flask, jsonify, request
import logging

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
            "/update": "GET - Update from GitHub"
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

@app.route("/update", methods=["GET"])
def update_from_git():
    """Update the application from GitHub"""
    try:
        logger.info("Starting Git update process...")
        
        # Run the update script
        result = subprocess.run(
            [sys.executable, "update.py"],
            cwd="/app",
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            logger.info("Git update completed successfully")
            return jsonify({
                "message": "Update completed successfully",
                "status": "success",
                "output": result.stdout,
                "timestamp": datetime.now().isoformat(),
                "note": "Restart container to apply all changes"
            })
        else:
            logger.error(f"Git update failed with code {result.returncode}")
            return jsonify({
                "error": "Update failed",
                "status": "failed",
                "exit_code": result.returncode,
                "stderr": result.stderr,
                "stdout": result.stdout,
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

if __name__ == "__main__":
    port = int(os.getenv("API_PORT", "8000"))
    debug = os.getenv("API_DEBUG", "false").lower() == "true"
    
    logger.info(f"Starting Crowd Counter API on port {port}")
    logger.info("Available endpoints:")
    logger.info("  GET  /         - Service info")
    logger.info("  GET  /health   - Health check")
    logger.info("  GET  /start    - Start crowd counting")
    logger.info("  GET  /trigger  - Start crowd counting (alias)")
    logger.info("  GET  /update   - Update from GitHub")
    logger.info("  GET  /status   - Process status")
    logger.info("  GET  /logs     - Process logs")
    
    app.run(host="0.0.0.0", port=port, debug=debug)