"""Core device definitions for GeneWeaver's compute engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class DeviceType(str, Enum):
    """Supported compute device types."""

    CPU = "cpu"
    CUDA = "cuda"


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    """Immutable information about a compute device."""

    device_type: DeviceType
    name: str
    device_id: int | None = None
    total_memory_bytes: int | None = None
    free_memory_bytes: int | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Device name cannot be empty.")

        if self.device_id is not None and self.device_id < 0:
            raise ValueError("Device ID cannot be negative.")

        for field_name in (
            "total_memory_bytes",
            "free_memory_bytes",
        ):
            value = getattr(self, field_name)

            if value is not None and value < 0:
                raise ValueError(f"{field_name} cannot be negative.")

        if (
            self.total_memory_bytes is not None
            and self.free_memory_bytes is not None
            and self.free_memory_bytes > self.total_memory_bytes
        ):
            raise ValueError("Free memory cannot exceed total memory.")

    @property
    def used_memory_bytes(self) -> int | None:
        """Return used device memory, if memory data is available."""

        if self.total_memory_bytes is None or self.free_memory_bytes is None:
            return None

        return self.total_memory_bytes - self.free_memory_bytes


class DeviceManagerError(RuntimeError):
    """Base exception for compute device failures."""


class DeviceUnavailableError(DeviceManagerError):
    """Raised when a requested compute device is unavailable."""


class DeviceInitializationError(DeviceManagerError):
    """Raised when a compute device cannot be initialized."""


class DeviceOperationError(DeviceManagerError):
    """Raised when an operation on a compute device fails."""


@runtime_checkable
class ComputeBackend(Protocol):
    """Common interface for compute backend implementations."""

    @property
    def array_module(self) -> Any:
        """Return NumPy or CuPy."""

        ...

    def get_device_info(self) -> DeviceInfo:
        """Return information about the active device."""

        ...

    def synchronize(self) -> None:
        """Wait for pending operations to complete."""

        ...
