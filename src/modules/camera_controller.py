"""PTZ Camera Controller - VISCA over IP commands."""
import logging
import socket
import time
from .config import Config, PresetConfig


logger = logging.getLogger(__name__)


class PTZCameraController:
    """Controller for sending VISCA over IP commands to the PTZ camera."""

    def __init__(self, camera_ip, camera_user="admin", camera_pass="admin", visca_port=5678):
        self.camera_ip = camera_ip
        self.camera_user = camera_user
        self.camera_pass = camera_pass
        self.visca_port = visca_port
        self.socket_timeout = 15.0
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
