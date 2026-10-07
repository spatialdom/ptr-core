"""Exception types raised by PTR Core."""


class PTRError(Exception):
    """Base class for PTR Core errors."""


class PTRParseError(PTRError, ValueError):
    """Raised when input cannot be parsed as a PTR record."""


class PTRSerializationError(PTRError, ValueError):
    """Raised when a PTR record cannot be serialized safely."""


class PTRUnsupportedVersionError(PTRParseError):
    """Raised when a PTR record uses an unsupported PTR specification version."""


class MissingOptionalDependencyError(PTRError, ImportError):
    """An advanced capability needs an optional geospatial dependency."""

    def __init__(self, dependency: str, capability: str) -> None:
        self.dependency = dependency
        self.capability = capability
        super().__init__(
            f"{capability} requires {dependency}; "
            'install the geospatial extra with: pip install "ptr-core[geospatial]"'
        )
