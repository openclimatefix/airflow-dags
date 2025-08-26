"""Functionts to clean up logs."""
import logging
import os
import time

logger = logging.getLogger(__name__)

# Constants
MILLISECONDS_TO_KEEP = 7 * 86400 * 1000  # 7 days

def delete_old_logs_and_empty_dirs(log_base_path:str, age_threshold_ms:int) -> None:
    """Delete old log files and empty directories."""
    now_ms = time.time() * 1000

    for root, _dirs, files in os.walk(log_base_path, topdown=False):

        logger.info(f"Checking directory: {root}")

        if "dag_processor_manager" in root:
            continue

        for file in files:
            file_path = os.path.join(root, file)
            try:
                mtime_ms = os.path.getmtime(file_path) * 1000
                if now_ms - mtime_ms > age_threshold_ms:
                    logger.info(f"Deleting old log file: {file_path}")
                    os.unlink(file_path)
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {e}")

        try:
            if not os.listdir(root):
                logger.info(f"Removing empty directory: {root}")
                os.rmdir(root)
        except Exception as e:
            logger.error(f"Error removing directory {root}: {e}")

def cleanup_logs() -> None:
    """Clean up airflow logs."""
    # the logs of the dags seem to be at /airflow/logs/
    log_dir = "/airflow/logs"

    logger.info(f"Starting log cleanup in directory: {log_dir}")

    delete_old_logs_and_empty_dirs(log_dir, age_threshold_ms=MILLISECONDS_TO_KEEP)
