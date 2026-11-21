
"""GeneWeaver compute engine."""

from app.engine.device import (
    ComputeBackend,
    DeviceInfo,
    DeviceType,
    DeviceManagerError,
    DeviceUnavailableError,
    DeviceInitializationError,
    DeviceOperationError,
)

from app.engine.backend import (
    CPUBackend,
    CUDABackend,
)

from app.engine.device_manager import DeviceManager

from app.engine.hamming import (
    HammingDistanceEngine,
    HammingDistanceError,
    InvalidSequenceError,
    SequenceLengthMismatchError,
    hamming_distance,
    batch_hamming_distance,
)
from app.engine.off_target import (
    OffTargetResult,
    OffTargetScoringEngine,
    OffTargetScoringError,
    InvalidScoringConfigurationError,
    score_off_target,
    batch_score_off_targets,
)

__all__ = [
    "ComputeBackend",
    "DeviceInfo",
    "DeviceType",
    "DeviceManager",
    "DeviceManagerError",
    "DeviceUnavailableError",
    "DeviceInitializationError",
    "DeviceOperationError",
    "CPUBackend",
    "CUDABackend",
    "HammingDistanceEngine",
    "HammingDistanceError",
    "InvalidSequenceError",
    "SequenceLengthMismatchError",
    "hamming_distance",
    "batch_hamming_distance",
    "OffTargetResult",
    "OffTargetScoringEngine",
    "OffTargetScoringError",
    "InvalidScoringConfigurationError",
    "score_off_target",
    "batch_score_off_targets",
]
