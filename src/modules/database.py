"""Database operations for crowd counter attendance tracking."""
import json
import logging
import os
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from .config import Config

logger = logging.getLogger(__name__)


class AttendanceDatabase:
    """Handles attendance data storage in PostgreSQL."""

    def __init__(self):
        self.db_config = Config.get_database_config()

    def _get_connection(self):
        """Get database connection."""
        try:
            conn = psycopg2.connect(
                host=self.db_config["host"],
                port=self.db_config["port"],
                database=self.db_config["name"],
                user=self.db_config["user"],
                password=self.db_config["password"]
            )
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return None

    def update_attendance(self, last_run_path):
        """
        Update attendance table with data from last_run.json.

        Args:
            last_run_path: Path to last_run.json file

        Returns:
            bool: True if successful, False otherwise
        """
        if not os.path.exists(last_run_path):
            logger.warning(f"last_run.json not found at {last_run_path}")
            return False

        try:
            # Read last_run.json
            with open(last_run_path, 'r') as f:
                data = json.load(f)

            # Check if hour is specified
            if 'hour' not in data:
                logger.info("No 'hour' field in last_run.json, skipping database update")
                return True

            hour = data['hour']
            total_count = data.get('total_count', 0)
            today = datetime.now().strftime('%m/%d/%Y')  # MM/DD/YYYY format

            # Determine column based on hour
            if hour == '9am':
                column = 'service_9am_sanctuary'
            elif hour == '1045am':
                column = 'service_1045am_sanctuary'
            else:
                logger.warning(f"Unknown hour '{hour}', expected '9am' or '1045am'")
                return False

            # Update database
            conn = self._get_connection()
            if not conn:
                return False

            try:
                with conn.cursor() as cursor:
                    # Check if row exists for today
                    cursor.execute(
                        "SELECT date FROM attendance WHERE date = %s",
                        (today,)
                    )
                    exists = cursor.fetchone() is not None

                    if exists:
                        # Update existing row
                        cursor.execute(
                            f"UPDATE attendance SET {column} = %s WHERE date = %s",
                            (total_count, today)
                        )
                        logger.info(f"Updated attendance for {today}: {column} = {total_count}")
                    else:
                        # Insert new row (weather and temp will be NULL)
                        cursor.execute(
                            f"INSERT INTO attendance (date, {column}) VALUES (%s, %s)",
                            (today, total_count)
                        )
                        logger.info(f"Created new attendance record for {today}: {column} = {total_count}")

                    conn.commit()
                    return True

            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Failed to update attendance database: {e}")
            return False


def update_attendance_from_last_run(last_run_path=None):
    """
    Convenience function to update attendance from last_run.json.

    Args:
        last_run_path: Path to last_run.json (defaults to output/last_run.json)

    Returns:
        bool: True if successful, False otherwise
    """
    if last_run_path is None:
        last_run_path = os.path.join(Config.OUTPUT_BASE_DIR, "last_run.json")

    db = AttendanceDatabase()
    return db.update_attendance(last_run_path)