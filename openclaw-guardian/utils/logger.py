"""
Logger - Logging setup for OpenClaw Guardian

This module provides logging functionality for the application.
It logs messages to both console (terminal) and file.

Beginner Python Notes:
- import: brings in external code (libraries) to use in our file
- logging: Python's built-in library for creating log messages
- formatter: controls how log messages look
- handler: determines where log messages go (console, file, etc.)
- singleton: a design pattern where we only create one instance of a class
"""

# ============================================================================
# IMPORTS - Bring in external libraries we need
# ============================================================================

import logging
# logging: Python's built-in library for tracking events
# It replaces print() statements and offers:
#   - Different log levels (DEBUG, INFO, WARNING, ERROR)
#   - Multiple outputs (console, file, etc.)
#   - Timestamps and formatting

import os
# os: Built-in Python library for file/directory operations
# We use it to check if log directory exists and create paths

from datetime import datetime
# datetime: Built-in Python library for working with dates/times
# We use it to include timestamps in log filenames

from pathlib import Path
# pathlib: Built-in Python library for file path operations

from typing import Optional
# typing: Built-in Python library for type hints
# Optional: value can be either the specified type or None


# ============================================================================
# LOGGER CLASS - Main logging handler
# ============================================================================

class Logger:
    """
    A custom logger class that handles logging to both console and file.
    
    Think of this like a diary that writes down everything the program does:
    - INFO: Normal operations ("Checking for outdated packages")
    - WARNING: Something unexpected but not critical ("No updates found")
    - ERROR: Something went wrong ("Failed to clone repository")
    - DEBUG: Detailed information for debugging
    
    Attributes:
        name: The name of the logger (usually the module name)
        log_file: Path to the log file
        level: The minimum log level to record
    """
    
    # Class variable to store the single logger instance (singleton pattern)
    # This ensures we only create one logger even if Logger is imported many times
    _instance: Optional['Logger'] = None
    _logger: Optional[logging.Logger] = None

    def __new__(cls, *args, **kwargs):
        """
        Creates a singleton instance of Logger.
        
        This ensures we only have one logger in the entire application,
        which is a best practice for logging.
        
        Returns:
            The single Logger instance
        """
        # Check if we've already created a logger
        if cls._instance is None:
            # If not, create a new one
            cls._instance = super(Logger, cls).__new__(cls)
        # Return the existing instance
        return cls._instance

    def __init__(
        self, 
        name: str = 'openclaw-guardian',
        log_dir: str = 'logs',
        level: int = logging.INFO
    ):
        """
        Initialize the logger with the given settings.
        
        Args:
            name: Name of the logger (defaults to 'openclaw-guardian')
            log_dir: Directory to store log files (defaults to 'logs')
            level: Minimum log level to record (defaults to INFO)
        
        Note:
            __init__ only runs the first time we create a Logger.
            Subsequent calls with different args are ignored.
        """
        # If logger already exists, don't reconfigure
        if Logger._logger is not None:
            return
        
        # Store settings
        self.name = name
        self.log_dir = log_dir
        self.level = level
        
        # Create log directory if it doesn't exist
        # exist_ok=True means don't error if directory already exists
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Generate log filename with current date
        # Example: openclaw-guardian-2024-01-15.log
        date_str = datetime.now().strftime('%Y-%m-%d')
        self.log_file = os.path.join(self.log_dir, f'{name}-{date_str}.log')
        
        # Create the actual Python logger
        self._setup_logger()

    def _setup_logger(self):
        """
        Sets up the Python logging system with handlers and formatters.
        
        This creates:
        1. A logger object with our name
        2. A console handler (shows logs in terminal)
        3. A file handler (saves logs to file)
        4. A formatter (defines how logs look)
        """
        # Create the logger object
        # This is the main object we'll use to log messages
        logger = logging.getLogger(self.name)
        
        # Set the minimum log level
        # Only messages at this level or higher will be recorded
        logger.setLevel(self.level)
        
        # Clear any existing handlers
        # This prevents duplicate logs if we accidentally call setup twice
        logger.handlers.clear()
        
        # ----------------------
        # Create Formatter
        # ----------------------
        # Formatter defines how each log message looks
        # Example output:
        # 2024-01-15 10:30:45 [INFO] - Checking for outdated packages
        
        formatter = logging.Formatter(
            fmt='%(asctime)s [%(levelname)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        # %(asctime)s: Human-readable timestamp
        # %(levelname)s: INFO, WARNING, ERROR, etc.
        # %(message)s: The actual log message
        
        # ----------------------
        # Console Handler
        # ----------------------
        # Handler sends logs to a destination
        # StreamHandler sends to console (terminal)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.level)  # Set level for this handler
        console_handler.setFormatter(formatter)  # Apply our format
        logger.addHandler(console_handler)  # Add handler to logger
        
        # ----------------------
        # File Handler
        # ----------------------
        # FileHandler sends logs to a file
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(self.level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Store logger for later use
        Logger._logger = logger
        
        # Log a startup message
        logger.info(f"Logger initialized. Log file: {self.log_file}")

    def debug(self, message: str):
        """
        Log a debug message.
        
        Debug messages are detailed information used for troubleshooting.
        They show exactly what's happening step by step.
        
        Args:
            message: The message to log
        
        Example:
            logger.debug("Opening config file at: config.yaml")
        """
        Logger._logger.debug(message)

    def info(self, message: str):
        """
        Log an info message.
        
        Info messages confirm that normal operations are happening.
        
        Args:
            message: The message to log
        
        Example:
            logger.info("Successfully cloned repository")
        """
        Logger._logger.info(message)

    def warning(self, message: str):
        """
        Log a warning message.
        
        Warning messages indicate something unexpected happened,
        but the program can continue running.
        
        Args:
            message: The message to log
        
        Example:
            logger.warning("No outdated packages found")
        """
        Logger._logger.warning(message)

    def error(self, message: str):
        """
        Log an error message.
        
        Error messages indicate something failed, but the program
        might be able to recover or continue.
        
        Args:
            message: The message to log
        
        Example:
            logger.error("Failed to connect to GitHub API")
        """
        Logger._logger.error(message)

    def critical(self, message: str):
        """
        Log a critical message.
        
        Critical messages indicate a serious problem that prevents
        the program from continuing.
        
        Args:
            message: The message to log
        
        Example:
            logger.critical("Cannot load configuration - exiting")
        """
        Logger._logger.critical(message)


# ============================================================================
# CONVENIENCE FUNCTION - Simple way to get a logger
# ============================================================================

def get_logger(
    name: str = 'openclaw-guardian',
    log_dir: str = 'logs',
    level: int = logging.INFO
) -> Logger:
    """
    Get or create a Logger instance.
    
    This is the main function other code will use to get a logger.
    It uses the singleton pattern, so calling this multiple times
    always returns the same logger.
    
    Args:
        name: Name of the logger (defaults to 'openclaw-guardian')
        log_dir: Directory to store log files (defaults to 'logs')
        level: Minimum log level (defaults to logging.INFO)
    
    Returns:
        A Logger instance
    
    Example:
        logger = get_logger()
        logger.info("Starting application")
    """
    # Create logger instance (singleton ensures only one exists)
    logger = Logger(name, log_dir, level)
    return logger


# ============================================================================
# EXAMPLE USAGE - How to use this logger
# ============================================================================

if __name__ == "__main__":
    """
    This block runs when we execute: python logger.py
    
    It demonstrates how to use the logger.
    """
    # Get a logger instance
    logger = get_logger()
    
    # Log messages at different levels
    logger.info("Application starting")
    logger.debug("Debug information: x=5, y=10")
    logger.warning("This is a warning")
    logger.error("This is an error")
    
    print(f"\nLog file created at: {logger.log_file}")
    print("Check the log file to see all the messages!")
