"""Security utilities for MCP Router."""

from typing import Optional

from ..core.exceptions import SecurityError
from ..core.logger import get_logger

logger = get_logger(__name__)


class SecurityManager:
    """Manages security features like authentication."""
    
    def __init__(self, bearer_token: Optional[str] = None, enable_validation: bool = True):
        """Initialize security manager.
        
        Args:
            bearer_token: Bearer token for API authentication (None to disable)
            enable_validation: Whether to enable validation
        """
        self.bearer_token = bearer_token
        self.enable_validation = enable_validation
        
        if bearer_token:
            logger.info("Bearer token authentication enabled")
        else:
            logger.warning("Bearer token authentication disabled")
    
    def validate_bearer_token(self, token: Optional[str]) -> bool:
        """Validate bearer token.
        
        Args:
            token: Token to validate
            
        Returns:
            True if valid, False otherwise
            
        Raises:
            SecurityError: If authentication is required but token is invalid
        """
        if not self.enable_validation:
            return True
        
        if not self.bearer_token:
            return True
        
        if not token:
            raise SecurityError("Bearer token required but not provided")
        
        token = token.replace("Bearer ", "").strip()
        
        if token != self.bearer_token:
            logger.warning("Invalid bearer token attempt")
            raise SecurityError("Invalid bearer token")
        
        return True
    
    def get_authorization_header(self, token: str) -> str:
        """Get properly formatted authorization header.
        
        Args:
            token: Bearer token
            
        Returns:
            Formatted authorization header value
        """
        if token.startswith("Bearer "):
            return token
        return f"Bearer {token}"
    
    def mask_token(self, token: Optional[str]) -> str:
        """Mask token for logging purposes.
        
        Args:
            token: Token to mask
            
        Returns:
            Masked token string
        """
        if not token:
            return "None"
        
        if len(token) <= 8:
            return "***"
        
        return f"{token[:4]}...{token[-4:]}"

