
"""CPU and CUDA compute backend implementations."""

from __future__ import annotations

from typing import Any

from app.engine.device import (
    DeviceInfo,
    DeviceType,
    DeviceUnavailableError,
    DeviceInitializationError,
    DeviceOperationError,
)


class CPUBackend:
    """CPU backend implemented using NumPy."""

    def __init__(self) -> None:
        try:
            import numpy as np

            self._numpy = np

        except ImportError as exc:
            raise DeviceInitializationError(
                "NumPy is required for CPU computation. "
                "Install it using: pip install numpy"
            ) from exc

    @property
    def array_module(self) -> Any:
        """Return the NumPy module."""

        return self._numpy

    def get_device_info(self) -> DeviceInfo:
        """Return CPU device information."""

        return DeviceInfo(
            device_type=DeviceType.CPU,
            name="CPU (NumPy)",
        )

    def synchronize(self) -> None:
        """CPU operations execute synchronously."""

        return None


class CUDABackend:
    """NVIDIA GPU backend implemented using CuPy."""

    def __init__(
        self,
        device_id: int = 0,
        cupy_module: Any | None = None,
    ) -> None:
        if device_id < 0:
            raise ValueError(
                "CUDA device ID cannot be negative."
            )

        self._device_id = device_id

        try:
            if cupy_module is None:
                import cupy as cp

                cupy_module = cp

            self._cupy = cupy_module

        except ImportError as exc:
            raise DeviceUnavailableError(
                "CuPy is not installed. "
                "Install a CUDA-compatible CuPy package "
                "for your system."
            ) from exc

        self._initialize_device()

    @property
    def array_module(self) -> Any:
        """Return the CuPy module."""

        return self._cupy

    def _initialize_device(self) -> None:
        """Verify CUDA availability and activate the requested device."""

        try:
            device_count = (
                self._cupy.cuda.runtime.getDeviceCount()
            )

            if device_count <= 0:
                raise DeviceUnavailableError(
                    "No CUDA-compatible GPU was detected."
                )

            if self._device_id >= device_count:
                raise DeviceUnavailableError(
                    f"CUDA device {self._device_id} does not exist. "
                    f"Detected devices: {device_count}."
                )

            with self._cupy.cuda.Device(self._device_id):
                self._cupy.cuda.runtime.getDeviceProperties(
                    self._device_id
                )

        except DeviceUnavailableError:
            raise

        except Exception as exc:
            raise DeviceInitializationError(
                f"Failed to initialize CUDA device "
                f"{self._device_id}: {exc}"
            ) from exc

    def get_device_info(self) -> DeviceInfo:
        """Return CUDA device name and memory information."""

        try:
            with self._cupy.cuda.Device(self._device_id):
                properties = (
                    self._cupy.cuda.runtime.getDeviceProperties(
                        self._device_id
                    )
                )

                free_memory, total_memory = (
                    self._cupy.cuda.runtime.memGetInfo()
                )

            name = properties.get(
                "name",
                "NVIDIA CUDA GPU",
            )

            if isinstance(name, bytes):
                name = name.decode(
                    "utf-8",
                    errors="replace",
                )

            return DeviceInfo(
                device_type=DeviceType.CUDA,
                name=str(name),
                device_id=self._device_id,
                total_memory_bytes=int(total_memory),
                free_memory_bytes=int(free_memory),
            )

        except Exception as exc:
            raise DeviceOperationError(
                "Unable to retrieve CUDA device information: "
                f"{exc}"
            ) from exc

    def synchronize(self) -> None:
        """Wait for operations on the selected CUDA device."""

        try:
            with self._cupy.cuda.Device(self._device_id):
                self._cupy.cuda.Stream.null.synchronize()

        except Exception as exc:
            raise DeviceOperationError(
                f"CUDA synchronization failed: {exc}"
            ) from exc
