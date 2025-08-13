"""
Secure logging configuration that removes sensitive information
"""

import logging
import sys
from typing import Any
from .security import SecurityUtils


class SecureFormatter(logging.Formatter):
    """Logging formatter that removes sensitive information"""
    
    def format(self, record):
        # Sanitize the message
        if hasattr(record, 'msg') and record.msg:
            record.msg = SecurityUtils.sanitize_for_logging(record.msg)
        
        # Sanitize arguments
        if hasattr(record, 'args') and record.args:
            record.args = tuple(SecurityUtils.sanitize_for_logging(arg) for arg in record.args)
        
        # Sanitize exception info if present
        if hasattr(record, 'exc_info') and record.exc_info:
            # Don't sanitize exception types/tracebacks, just the message
            pass
        
        return super().format(record)


class SecureLogger:
    """Wrapper for secure logging operations"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def info(self, message: Any, *args, **kwargs):
        """Safe info logging"""
        sanitized_msg = SecurityUtils.sanitize_for_logging(message)
        sanitized_args = [SecurityUtils.sanitize_for_logging(arg) for arg in args]
        self.logger.info(sanitized_msg, *sanitized_args, **kwargs)
    
    def warning(self, message: Any, *args, **kwargs):
        """Safe warning logging"""
        sanitized_msg = SecurityUtils.sanitize_for_logging(message)
        sanitized_args = [SecurityUtils.sanitize_for_logging(arg) for arg in args]
        self.logger.warning(sanitized_msg, *sanitized_args, **kwargs)
    
    def error(self, message: Any, *args, **kwargs):
        """Safe error logging"""
        sanitized_msg = SecurityUtils.sanitize_for_logging(message)
        sanitized_args = [SecurityUtils.sanitize_for_logging(arg) for arg in args]
        self.logger.error(sanitized_msg, *sanitized_args, **kwargs)
    
    def debug(self, message: Any, *args, **kwargs):
        """Safe debug logging"""
        sanitized_msg = SecurityUtils.sanitize_for_logging(message)
        sanitized_args = [SecurityUtils.sanitize_for_logging(arg) for arg in args]
        self.logger.debug(sanitized_msg, *sanitized_args, **kwargs)
    
    def critical(self, message: Any, *args, **kwargs):
        """Safe critical logging"""
        sanitized_msg = SecurityUtils.sanitize_for_logging(message)
        sanitized_args = [SecurityUtils.sanitize_for_logging(arg) for arg in args]
        self.logger.critical(sanitized_msg, *sanitized_args, **kwargs)


def setup_secure_logging(level: str = "INFO") -> SecureLogger:
    """Setup logging with security sanitization"""
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create secure formatter
    formatter = SecureFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Setup handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    # Get root logger and configure it
    root_logger = logging.getLogger()
    
    # Clear any existing handlers to avoid duplicates
    for handler_obj in root_logger.handlers[:]:
        root_logger.removeHandler(handler_obj)
    
    root_logger.addHandler(handler)
    root_logger.setLevel(numeric_level)
    
    # Return secure logger instance
    return SecureLogger("secure_logger")


def get_secure_logger(name: str) -> SecureLogger:
    """Get a secure logger instance"""
    return SecureLogger(name)


# Convenience functions for safe logging
def safe_log_info(logger: logging.Logger, message: str, *args):
    """Safe info logging that removes sensitive data"""
    sanitized_message = SecurityUtils.sanitize_for_logging(message)
    sanitized_args = [SecurityUtils.sanitize_for_logging(arg) for arg in args]
    logger.info(sanitized_message, *sanitized_args)


def safe_log_warning(logger: logging.Logger, message: str, *args):
    """Safe warning logging that removes sensitive data"""
    sanitized_message = SecurityUtils.sanitize_for_logging(message)
    sanitized_args = [SecurityUtils.sanitize_for_logging(arg) for arg in args]
    logger.warning(sanitized_message, *sanitized_args)


def safe_log_error(logger: logging.Logger, message: str, *args):
    """Safe error logging that removes sensitive data"""
    sanitized_message = SecurityUtils.sanitize_for_logging(message)
    sanitized_args = [SecurityUtils.sanitize_for_logging(arg) for arg in args]
    logger.error(sanitized_message, *sanitized_args)