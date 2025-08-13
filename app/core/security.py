"""
Security utilities for safe logging and data handling
"""

import re
from typing import Any, Dict, List, Union


class SecurityUtils:
    """Security utilities for safe logging and data handling"""
    
    @staticmethod
    def sanitize_for_logging(data: Any) -> Any:
        """Remove sensitive data from logging output"""
        if isinstance(data, str):
            return SecurityUtils._sanitize_string(data)
        elif isinstance(data, dict):
            return SecurityUtils._sanitize_dict(data)
        elif isinstance(data, list):
            return [SecurityUtils.sanitize_for_logging(item) for item in data]
        return data
    
    @staticmethod
    def _sanitize_string(text: str) -> str:
        """Sanitize sensitive information from strings"""
        # OpenAI API keys (sk-proj- or sk- format)
        text = re.sub(r'sk-proj-[a-zA-Z0-9_-]{20,}', '[OPENAI_API_KEY_REDACTED]', text)
        text = re.sub(r'sk-[a-zA-Z0-9]{20,}', '[OPENAI_API_KEY_REDACTED]', text)
        
        # Generic API keys (various patterns)
        text = re.sub(r'api[_-]?key["\s]*[:=]["\s]*[a-zA-Z0-9_-]{10,}', '[API_KEY_REDACTED]', text, flags=re.IGNORECASE)
        
        # Tokens
        text = re.sub(r'token["\s]*[:=]["\s]*[a-zA-Z0-9_-]{20,}', '[TOKEN_REDACTED]', text, flags=re.IGNORECASE)
        text = re.sub(r'access[_-]?token["\s]*[:=]["\s]*[a-zA-Z0-9_-]{20,}', '[ACCESS_TOKEN_REDACTED]', text, flags=re.IGNORECASE)
        
        # Passwords
        text = re.sub(r'password["\s]*[:=]["\s]*[^\s,"\']+', '[PASSWORD_REDACTED]', text, flags=re.IGNORECASE)
        text = re.sub(r'passwd["\s]*[:=]["\s]*[^\s,"\']+', '[PASSWORD_REDACTED]', text, flags=re.IGNORECASE)
        
        # Common secret patterns
        text = re.sub(r'secret["\s]*[:=]["\s]*[^\s,"\']+', '[SECRET_REDACTED]', text, flags=re.IGNORECASE)
        text = re.sub(r'private[_-]?key["\s]*[:=]["\s]*[^\s,"\']+', '[PRIVATE_KEY_REDACTED]', text, flags=re.IGNORECASE)
        
        return text
    
    @staticmethod
    def _sanitize_dict(data: Dict) -> Dict:
        """Sanitize sensitive keys in dictionaries"""
        sensitive_keys = {
            'api_key', 'apikey', 'api-key', 'openai_api_key',
            'token', 'access_token', 'auth_token', 'bearer_token',
            'password', 'passwd', 'pwd',
            'secret', 'private_key', 'credentials', 'auth',
            'authorization', 'x-api-key'
        }
        
        sanitized = {}
        for key, value in data.items():
            if key.lower() in sensitive_keys:
                sanitized[key] = '[REDACTED]'
            else:
                sanitized[key] = SecurityUtils.sanitize_for_logging(value)
        
        return sanitized
    
    @staticmethod
    def validate_environment_vars() -> List[str]:
        """Validate that sensitive environment variables are not logged"""
        import os
        warnings = []
        
        sensitive_env_vars = [
            'OPENAI_API_KEY', 'API_KEY', 'SECRET_KEY', 'PRIVATE_KEY',
            'PASSWORD', 'TOKEN', 'ACCESS_TOKEN', 'LANGCHAIN_API_KEY'
        ]
        
        for var in sensitive_env_vars:
            if var in os.environ:
                value = os.environ[var]
                if len(value) > 10:  # Only check substantial values
                    warnings.append(f"Environment variable {var} contains sensitive data")
        
        return warnings
    
    @staticmethod
    def mask_sensitive_value(value: str, show_chars: int = 4) -> str:
        """Mask a sensitive value showing only first few characters"""
        if not value or len(value) <= show_chars:
            return '[MASKED]'
        
        return f"{value[:show_chars]}***[MASKED]"


def safe_log_data(data: Any) -> Any:
    """Safe wrapper for logging any data structure"""
    return SecurityUtils.sanitize_for_logging(data)