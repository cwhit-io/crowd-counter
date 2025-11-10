"""Modules package for PTZ Crowd Counter."""

from .camera_controller import PTZCameraController
from .capture import capture_all_presets
from .processing import start_processing_workers, stop_workers, collect_results
from .config import Config, PresetConfig
from .reporting import generate_report
from .database import update_attendance_from_last_run

__all__ = [
    "PTZCameraController",
    "capture_all_presets",
    "start_processing_workers",
    "stop_workers",
    "collect_results",
    "Config",
    "PresetConfig",
    "generate_report",
    "update_attendance_from_last_run"
]