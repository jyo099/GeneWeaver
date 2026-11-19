
"""Unit tests for GeneWeaver's adaptive device manager."""

import numpy as np
import pytest

import app.engine.device_manager as manager_module

from app.engine.device import (
    DeviceInfo,
    DeviceType,
    DeviceUnavailableError,
    DeviceOperationError,
)


class FakeCPUBackend:
    """Fake CPU backend for isolated unit tests."""

    @property
    def array_module(self):
        return np

    def get_device_info(self):
        return DeviceInfo(
            device_type=DeviceType.CPU,
            name="Test CPU",
        )

    def synchronize(self):
        return None


class FakeCUDABackend:
    """Fake CUDA backend for isolated unit tests."""

    def __init__(self, device_id=0):
        self.device_id = device_id

    @property
    def array_module(self):
        return np

    def get_device_info(self):
        return DeviceInfo(
            device_type=DeviceType.CUDA,
            name="Test CUDA GPU",
            device_id=self.device_id,
            total_memory_bytes=8_000_000,
            free_memory_bytes=6_000_000,
        )

    def synchronize(self):
        return None


def test_cpu_mode_selects_cpu(monkeypatch):
    monkeypatch.setattr(
        manager_module,
        "CPUBackend",
        FakeCPUBackend,
    )

    manager = manager_module.DeviceManager(
        backend="cpu"
    )

    assert manager.backend == "cpu"
    assert manager.device_info.name == "Test CPU"


def test_auto_mode_selects_cuda_when_available(monkeypatch):
    monkeypatch.setattr(
        manager_module,
        "CUDABackend",
        FakeCUDABackend,
    )

    manager = manager_module.DeviceManager(
        backend="auto"
    )

    assert manager.backend == "cuda"
    assert manager.device_info.device_id == 0


def test_auto_mode_falls_back_to_cpu(monkeypatch):
    monkeypatch.setattr(
        manager_module,
        "CPUBackend",
        FakeCPUBackend,
    )

    def unavailable_cuda(device_id=0):
        raise DeviceUnavailableError(
            "CUDA is unavailable."
        )

    monkeypatch.setattr(
        manager_module,
        "CUDABackend",
        unavailable_cuda,
    )

    manager = manager_module.DeviceManager(
        backend="auto"
    )

    assert manager.backend == "cpu"
    assert "CUDA unavailable" in manager.selection_reason


def test_explicit_cuda_does_not_fall_back(monkeypatch):
    def unavailable_cuda(device_id=0):
        raise DeviceUnavailableError(
            "CUDA is unavailable."
        )

    monkeypatch.setattr(
        manager_module,
        "CUDABackend",
        unavailable_cuda,
    )

    with pytest.raises(DeviceUnavailableError):
        manager_module.DeviceManager(
            backend="cuda"
        )


def test_invalid_backend_is_rejected():
    with pytest.raises(ValueError):
        manager_module.DeviceManager(
            backend="tpu"
        )


@pytest.mark.parametrize(
    "device_id",
    [-1, 1.5, True, "0"],
)
def test_invalid_device_id_is_rejected(device_id):
    with pytest.raises(ValueError):
        manager_module.DeviceManager(
            backend="cpu",
            device_id=device_id,
        )


def test_health_check_returns_cpu_information(monkeypatch):
    monkeypatch.setattr(
        manager_module,
        "CPUBackend",
        FakeCPUBackend,
    )

    manager = manager_module.DeviceManager(
        backend="cpu"
    )

    health = manager.health_check()

    assert health["status"] == "available"
    assert health["backend"] == "cpu"
    assert health["device_name"] == "Test CPU"
    assert health["total_memory_bytes"] is None
    assert health["used_memory_bytes"] is None


def test_cuda_memory_usage_is_calculated(monkeypatch):
    monkeypatch.setattr(
        manager_module,
        "CUDABackend",
        FakeCUDABackend,
    )

    manager = manager_module.DeviceManager(
        backend="cuda"
    )

    assert manager.device_info.used_memory_bytes == 2_000_000


def test_array_module_is_available(monkeypatch):
    monkeypatch.setattr(
        manager_module,
        "CPUBackend",
        FakeCPUBackend,
    )

    manager = manager_module.DeviceManager(
        backend="cpu"
    )

    assert manager.array_module is np


def test_synchronize_delegates_to_backend(monkeypatch):
    monkeypatch.setattr(
        manager_module,
        "CPUBackend",
        FakeCPUBackend,
    )

    manager = manager_module.DeviceManager(
        backend="cpu"
    )

    manager.synchronize()


def test_device_info_rejects_invalid_memory():
    with pytest.raises(ValueError):
        DeviceInfo(
            device_type=DeviceType.CUDA,
            name="Test GPU",
            total_memory_bytes=100,
            free_memory_bytes=200,
        )


def test_device_info_calculates_used_memory():
    info = DeviceInfo(
        device_type=DeviceType.CUDA,
        name="Test GPU",
        total_memory_bytes=1000,
        free_memory_bytes=400,
    )

    assert info.used_memory_bytes == 600


def test_device_info_rejects_empty_name():
    with pytest.raises(ValueError):
        DeviceInfo(
            device_type=DeviceType.CPU,
            name=" ",
        )


def test_cuda_synchronization_failure_is_reported():
    class BrokenRuntime:
        @staticmethod
        def getDeviceCount():
            return 1

        @staticmethod
        def getDeviceProperties(device_id):
            return {"name": b"Test GPU"}

        @staticmethod
        def memGetInfo():
            return 500, 1000

    class BrokenStream:
        @staticmethod
        def synchronize():
            raise RuntimeError("Simulated CUDA failure")

    class FakeDevice:
        def __init__(self, device_id):
            self.device_id = device_id

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class FakeCUDA:
        runtime = BrokenRuntime()
        Stream = type(
            "Stream",
            (),
            {"null": BrokenStream()},
        )

        Device = FakeDevice

    class FakeCuPy:
        cuda = FakeCUDA()

    from app.engine.backend import CUDABackend

    backend = CUDABackend(
        device_id=0,
        cupy_module=FakeCuPy(),
    )

    with pytest.raises(DeviceOperationError):
        backend.synchronize()
