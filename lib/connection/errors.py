"""
Connection-specific exceptions.

This module defines the exception hierarchy for connection-related errors.
All exceptions inherit from ConnectionError for easy catching.
"""


class ConnectionError(Exception):
    """
    Base exception for connection errors.

    All connection-related exceptions inherit from this class,
    allowing catch-all exception handling when needed.
    """
    pass


class AuthenticationError(ConnectionError):
    """
    Authentication or login failed.

    Raised when credentials are invalid, authentication is rejected,
    or login process fails.
    """
    pass


class NotConnectedError(ConnectionError):
    """
    Operation requires active connection.

    Raised when attempting to send messages or perform actions
    without an established connection.
    """
    pass


class SendError(ConnectionError):
    """
    Failed to send message or data.

    Raised when message transmission fails due to network issues,
    protocol errors, or platform restrictions.
    """
    pass


class UserNotFoundError(ConnectionError):
    """
    Target user does not exist.

    Raised when attempting to send a private message or interact
    with a user that doesn't exist on the platform.
    """
    pass


class ProtocolError(ConnectionError):
    """
    Platform protocol violation.

    Raised when the platform sends unexpected data or when
    protocol requirements are not met.
    """
    pass
