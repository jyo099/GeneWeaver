
"""Adaptive CPU/GPU device manager for GeneWeaver."""

from __future__ import annotations

from typing import Any, Literal

from app.engine.backend import CPUBackend, CUDABackend
from app.engine.device import (
    ComputeBackend,
    DeviceInfo,
    DeviceManagerError,
)


BackendName = Literal["auto", "cpu", "cuda"]


class DeviceManager:
    """
    Select and manage the compute backend.

    Parameters
    ----------
    backend:
        "auto", "cpu", or "cuda".

    device_id:
        NVIDIA CUDA device index. Defaults to 0.

    Behaviour
    ---------
    auto:
        Select CUDA when available, otherwise CPU.

    cpu:
        Select CPU unconditionally.

    cuda:
        Require CUDA. Never silently fall back to CPU.
    """

    VALID_BACKENDS = {"auto", "cpu", "cuda"}

    def __init__(
        self,
        backend: BackendName = "auto",
        device_id: int = 0,
    ) -> None:
        if backend not in self.VALID_BACKENDS:
            raise ValueError(
                "Invalid backend. Supported values are "
                "'auto', 'cpu', and 'cuda'."
            )

        if (
            isinstance(device_id, bool)
            or not isinstance(device_id, int)
            or device_id < 0
        ):
            raise ValueError(
                "device_id must be a non-negative integer."
            )

        self.requested_backend = backend
        self.device_id = device_id

        self._backend: ComputeBackend
        self._selection_reason: str

        self._initialize_backend()

    def _initialize_backend(self) -> None:
        """Initialize the backend according to the requested mode."""

        if self.requested_backend == "cpu":
            self._backend = CPUBackend()

            self._selection_reason = (
                "CPU explicitly requested."
            )

            return

        if self.requested_backend == "cuda":
            self._backend = CUDABackend(
                device_id=self.device_id
            )

            self._selection_reason = (
                "CUDA explicitly requested."
            )

            return

        # Automatic mode.
        try:
            self._backend = CUDABackend(
                device_id=self.device_id
            )

            self._selection_reason = (
                "CUDA is available; selected automatically."
            )

        except DeviceManagerError as exc:
            self._backend = CPUBackend()

            self._selection_reason = (
                "CUDA unavailable; selected CPU backend. "
                f"Reason: {exc}"
            )

    @property
    def backend(self) -> str:
        """Return the selected backend name."""

        return self.device_info.device_type.value

    @property
    def array_module(self) -> Any:
        """
        Return the active array library.

        NumPy is returned for CPU execution.
        CuPy is returned for CUDA execution.
        """

        return self._backend.array_module

    @property
    def device_info(self) -> DeviceInfo:
        """Return current device metadata."""

        return self._backend.get_device_info()

    @property
    def selection_reason(self) -> str:
        """Explain why this backend was selected."""

        return self._selection_reason

    def synchronize(self) -> None:
        """Synchronize the active compute backend."""

        self._backend.synchronize()

    def health_check(self) -> dict[str, Any]:
        """
        Return device information in a JSON-serializable format.

        This can later be integrated into the health telemetry API.
        """

        info = self.device_info

        return {
            "status": "available",
            "requested_backend": self.requested_backend,
            "backend": info.device_type.value,
            "device_name": info.name,
            "device_id": info.device_id,
            "total_memory_bytes": info.total_memory_bytes,
            "free_memory_bytes": info.free_memory_bytes,
            "used_memory_bytes": info.used_memory_bytes,
            "selection_reason": self.selection_reason,
        }
