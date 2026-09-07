"""Exception types raised by PTR Core."""


class PTRError(Exception):
    """Base class for PTR Core errors."""


class PTRParseError(PTRError, ValueError):
    """Raised when input cannot be parsed as a PTR record."""


class PTRSerializationError(PTRError, ValueError):
    """Raised when a PTR record cannot be serialized safely."""

