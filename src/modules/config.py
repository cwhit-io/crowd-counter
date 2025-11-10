"""Configuration management for PTZ Crowd Counter."""
import json
import logging
import os
import sys

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment Variable Loading
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info("Loaded environment variables from .env file")
except ImportError:
    logger.warning("⚠️ python-dotenv not installed. Install with: pip install python-dotenv")
    logger.warning("⚠️ Using default values or system environment variables")


class Config:
    """Central configuration for the crowd counter application."""
    
    # Camera Settings
    CAMERA_IP = os.getenv("CAMERA_IP", "192.168.0.100")
    VISCA_PORT = int(os.getenv("VISCA_PORT", "5678"))
    CAMERA_USER = os.getenv("CAMERA_USER", "admin")
    CAMERA_PASS = os.getenv("CAMERA_PASS", "admin")
    
    # Model Settings
    MODEL_PATH = os.getenv("MODEL_PATH", "models/best.pt")
    INFER_CONF = float(os.getenv("INFER_CONF", "0.25"))
    INFER_IOU = float(os.getenv("INFER_IOU", "0.45"))
    
    # Clustering Settings
    CLUSTER_EPS = int(os.getenv("CLUSTER_EPS", "50"))
    MIN_CLUSTER_SIZE = int(os.getenv("MIN_CLUSTER_SIZE", "2"))
    
    # Processing Settings
    NUM_WORKERS = int(os.getenv("NUM_WORKERS", "4"))
    
    # Output Settings
    OUTPUT_BASE_DIR = os.getenv("OUTPUT_BASE_DIR", "output")
    
    # Email Settings
    EMAIL_SENDER = os.getenv("EMAIL_SENDER", "name@email.com")
    EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "name@email.com")
    EMAIL_API = os.getenv("EMAIL_API", "YOUR_MAILTRAP_API_KEY")
    
    # Database Settings
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))
    DB_NAME = os.getenv("DB_NAME", "crowd_counter")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASS = os.getenv("DB_PASS", "")
    
    # Preset Configuration
    PRESET_CONFIG_FILE = os.getenv("PRESET_CONFIG_FILE", "preset_config.json")
    
    @classmethod
    def validate(cls):
        """Validate critical configuration values."""
        errors = []
        warnings = []
        
        # Check camera IP
        if cls.CAMERA_IP == "192.168.0.100":
            warnings.append("Using default CAMERA_IP. Set in .env for production.")
        
        # Check model exists
        if not os.path.exists(cls.MODEL_PATH):
            errors.append(f"Model not found at: {cls.MODEL_PATH}")
        
        # Check preset config exists
        if not os.path.exists(cls.PRESET_CONFIG_FILE):
            errors.append(f"Preset config not found at: {cls.PRESET_CONFIG_FILE}")
        
        # Check email configuration
        if cls.EMAIL_API == "YOUR_MAILTRAP_API_KEY":
            warnings.append("Email API key not set. Email functionality will fail.")
        
        # Log warnings
        for warning in warnings:
            logger.warning(f"⚠️  {warning}")
        
        # Handle errors
        if errors:
            for error in errors:
                logger.error(f"❌ Configuration Error: {error}")
            sys.exit(1)
        
        logger.info("Configuration validated successfully")
    
    @classmethod
    def get_camera_config(cls):
        """Get camera-related configuration as a dict."""
        return {
            "ip": cls.CAMERA_IP,
            "port": cls.VISCA_PORT,
            "user": cls.CAMERA_USER,
            "password": cls.CAMERA_PASS
        }
    
    @classmethod
    def get_model_config(cls):
        """Get model-related configuration as a dict."""
        return {
            "path": cls.MODEL_PATH,
            "conf": cls.INFER_CONF,
            "iou": cls.INFER_IOU,
            "cluster_eps": cls.CLUSTER_EPS,
            "min_cluster_size": cls.MIN_CLUSTER_SIZE
        }
    
    @classmethod
    def get_email_config(cls):
        """Get email-related configuration as a dict."""
        return {
            "sender": cls.EMAIL_SENDER,
            "receiver": cls.EMAIL_RECEIVER,
            "api_key": cls.EMAIL_API
        }
    
    @classmethod
    def get_database_config(cls):
        """Get database-related configuration as a dict."""
        return {
            "host": cls.DB_HOST,
            "port": cls.DB_PORT,
            "name": cls.DB_NAME,
            "user": cls.DB_USER,
            "password": cls.DB_PASS
        }
    
    @classmethod
    def summary(cls):
        """Print configuration summary."""
        logger.info("Configuration Summary:")
        logger.info(f"  Camera: {cls.CAMERA_IP}:{cls.VISCA_PORT}")
        logger.info(f"  Model: {cls.MODEL_PATH}")
        logger.info(f"  Workers: {cls.NUM_WORKERS}")
        logger.info(f"  Output: {cls.OUTPUT_BASE_DIR}")


class PresetConfig:
    """Manages preset configuration loading and access."""
    
    def __init__(self, config_file=None):
        if config_file is None:
            config_file = Config.PRESET_CONFIG_FILE
        
        self.config_file = config_file
        self.presets = []
        self.preset_map = {}
        self._load()
    
    def _load(self):
        """Load preset configuration from JSON file."""
        try:
            with open(self.config_file, "r") as f:
                config = json.load(f)
                presets_data = config.get("presets", [])
                self.presets = [preset["number"] for preset in presets_data]
                self.preset_map = {
                    preset["number"]: preset.get("name", f"Preset {preset['number']}")
                    for preset in presets_data
                }
                logger.debug(f"Loaded {len(self.presets)} presets from {self.config_file}")
        except FileNotFoundError:
            logger.error(f"Preset configuration file not found: {self.config_file}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in preset configuration: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error loading preset configuration: {str(e)}")
            raise
    
    def get_presets(self):
        """Get list of (preset_number, preset_name) tuples."""
        return [(p, self.preset_map.get(p, f"Preset {p}")) for p in self.presets]
    
    def get_preset_name(self, preset_number):
        """Get the name for a specific preset number."""
        return self.preset_map.get(preset_number, f"Preset {preset_number}")
    
    def get_preset_numbers(self):
        """Get list of preset numbers."""
        return self.presets
    
    def get_preset_map(self):
        """Get the full preset number -> name mapping."""
        return self.preset_map
