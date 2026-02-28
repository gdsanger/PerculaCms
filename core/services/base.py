"""Base exceptions for core services."""


class ServiceError(Exception):
    """Base class for all service-layer errors."""


class ServiceNotConfigured(ServiceError):
    """Raised when a required service has no active configuration."""


class ServiceDisabled(ServiceError):
    """Raised when a service exists but is explicitly disabled."""
