import logging
import os

from logging.handlers import RotatingFileHandler

def setup_logger(name, log_file, level=logging.DEBUG):
    """Function to set up a logger with file and console handlers"""
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    os.makedirs(log_dir, exist_ok=True)
    
    # File Handler
    file_handler = RotatingFileHandler(log_file, maxBytes=10000000, backupCount=5)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Create a logger for the application
log_file_path = os.path.join('/home/samjd/Apps/claude-dev/grizz-ai/logs', 'out.log')
app_logger = setup_logger('forest_chronicles', log_file_path)
