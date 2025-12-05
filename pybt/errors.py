"""Unified exception hierarchy for PyBT."""


class PyBTError(Exception):
    """Base class for framework errors."""


class ConfigurationError(PyBTError):
    """Configuration or wiring errors."""


class DataError(PyBTError):
    """Data quality or parsing issues."""


class FeedError(PyBTError):
    """Live/streaming feed failures."""


class ExecutionError(PyBTError):
    """Order execution failures."""


class RiskError(PyBTError):
    """Risk checks or constraint violations."""


class PersistenceError(PyBTError):
    """Persistence or storage failures."""


__all__ = [
    "PyBTError",
    "ConfigurationError",
    "DataError",
    "FeedError",
    "ExecutionError",
    "RiskError",
    "PersistenceError",
]
