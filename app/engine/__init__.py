"""GeneWeaver compute engine."""

from app.engine.backend import (
    CPUBackend,
    CUDABackend,
)
from app.engine.device import (
    ComputeBackend,
    DeviceInfo,
    DeviceInitializationError,
    DeviceManagerError,
    DeviceOperationError,
    DeviceType,
    DeviceUnavailableError,
)
from app.engine.device_manager import DeviceManager
from app.engine.hamming import (
    HammingDistanceEngine,
    HammingDistanceError,
    InvalidSequenceError,
    SequenceLengthMismatchError,
    batch_hamming_distance,
    hamming_distance,
)
from app.engine.off_target import (
    InvalidScoringConfigurationError,
    OffTargetResult,
    OffTargetScoringEngine,
    OffTargetScoringError,
    batch_score_off_targets,
    score_off_target,
)

__all__ = [
    "CPUBackend",
    "CUDABackend",
    "ComputeBackend",
    "DeviceInfo",
    "DeviceInitializationError",
    "DeviceManager",
    "DeviceManagerError",
    "DeviceOperationError",
    "DeviceType",
    "DeviceUnavailableError",
    "HammingDistanceEngine",
    "HammingDistanceError",
    "InvalidScoringConfigurationError",
    "InvalidSequenceError",
    "OffTargetResult",
    "OffTargetScoringEngine",
    "OffTargetScoringError",
    "SequenceLengthMismatchError",
    "batch_hamming_distance",
    "batch_score_off_targets",
    "hamming_distance",
    "score_off_target",
]
