"""Custom exceptions for MCP Router."""


class MCPRouterException(Exception):
    """Base exception for all MCP Router errors."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)

    def to_dict(self):
        return {"error": self.message, "code": self.code}


class ConfigurationError(MCPRouterException):
    """Raised when there's a configuration error."""

    def __init__(self, message: str):
        super().__init__(message, "CONFIG_ERROR")


class ValidationError(MCPRouterException):
    """Raised when input validation fails."""

    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")


class InstanceNotFoundError(MCPRouterException):
    """Raised when an MCP instance is not found."""

    def __init__(self, instance_name: str):
        message = f"Instance not found: {instance_name}"
        super().__init__(message, "INSTANCE_NOT_FOUND")
        self.instance_name = instance_name


class ToolNotFoundError(MCPRouterException):
    """Raised when a tool is not found in an instance."""

    def __init__(self, tool_name: str, instance_name: str):
        message = f"Tool '{tool_name}' not found in instance '{instance_name}'"
        super().__init__(message, "TOOL_NOT_FOUND")
        self.tool_name = tool_name
        self.instance_name = instance_name


class TimeoutError(MCPRouterException):
    """Raised when an operation times out."""

    def __init__(self, timeout: float):
        message = f"Timeout exceeded: {timeout}s"
        super().__init__(message, "TIMEOUT")
        self.timeout = timeout


class TransportError(MCPRouterException):
    """Raised when there's a transport layer error."""

    def __init__(self, message: str):
        super().__init__(message, "TRANSPORT_ERROR")


class SecurityError(MCPRouterException):
    """Raised when there's a security violation."""

    def __init__(self, message: str):
        super().__init__(message, "SECURITY_ERROR")
