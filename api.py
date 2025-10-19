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
        
        # Run the main script
        result = subprocess.run(
            [sys.executable, "run.py"],
            cwd="/app",
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        process_output.append(f"Exit code: {result.returncode}")
        if result.stdout:
            process_output.append(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            process_output.append(f"STDERR:\n{result.stderr}")
            
        if result.returncode == 0:
            process_status = "completed"
            logger.info("Crowd counting completed successfully")
        else:
            process_status = "failed"
            logger.error(f"Crowd counting failed with code {result.returncode}")
            
    except subprocess.TimeoutExpired:
        process_status = "timeout"
        logger.error("Crowd counting process timed out")
    except Exception as e:
        process_status = "error"
        process_output.append(f"Error: {str(e)}")
        logger.error(f"Error running crowd counter: {e}")

@app.route("/")
def home():
    """Health check endpoint"""
    return jsonify({
        "service": "crowd-counter-api",
        "status": "healthy",
        "version": "1.0",
        "endpoints": {
            "/start": "POST - Start crowd counting",
            "/status": "GET - Check process status",
            "/logs": "GET - Get recent logs",
            "/health": "GET - Health check"
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

@app.route("/start", methods=["POST"])
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

@app.route("/trigger", methods=["POST"])
def trigger_counting():
    """Alternative endpoint name for starting process"""
    return start_crowd_counting()

if __name__ == "__main__":
    port = int(os.getenv("API_PORT", "8000"))
    debug = os.getenv("API_DEBUG", "false").lower() == "true"
    
    logger.info(f"Starting Crowd Counter API on port {port}")
    logger.info("Available endpoints:")
    logger.info("  GET  /         - Service info")
    logger.info("  GET  /health   - Health check")
    logger.info("  POST /start    - Start crowd counting")
    logger.info("  POST /trigger  - Start crowd counting (alias)")
    logger.info("  GET  /status   - Process status")
    logger.info("  GET  /logs     - Process logs")
    
    app.run(host="0.0.0.0", port=port, debug=debug)