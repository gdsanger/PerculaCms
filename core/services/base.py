"""
Base exceptions for PerculaCMS infrastructure services.
"""


class ServiceDisabled(Exception):
    """Raised when a service is explicitly disabled via feature toggle."""


class ServiceNotConfigured(Exception):
    """Raised when required configuration for a service is missing."""
