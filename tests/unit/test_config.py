"""Unit tests for GeneWeaver configuration."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_default_settings():
    """Test default application configuration."""

    config = Settings(
        _env_file=None,
        _env_prefix="GW_TEST_",
    )

    assert config.app_name == "GeneWeaver"
    assert config.app_version == "0.1.0"
    assert config.environment == "development"
    assert config.debug is True
    assert config.alignment_backend == "cpu"


def test_custom_settings():
    """Test custom application configuration."""

    config = Settings(
        _env_file=None,
        _env_prefix="GW_TEST_",
        app_name="GeneWeaver Research",
        environment="testing",
        debug=False,
        alignment_backend="gpu",
        max_upload_size_mb=200,
    )

    assert config.app_name == "GeneWeaver Research"
    assert config.environment == "testing"
    assert config.debug is False
    assert config.alignment_backend == "gpu"
    assert config.max_upload_size_mb == 200


def test_environment_variable_loading(monkeypatch):
    """Test loading configuration from environment."""

    monkeypatch.setenv("GW_APP_NAME", "GeneWeaver Production")
    monkeypatch.setenv("GW_ENVIRONMENT", "production")
    monkeypatch.setenv("GW_DEBUG", "false")

    config = Settings(_env_file=None)

    assert config.app_name == "GeneWeaver Production"
    assert config.environment == "production"
    assert config.debug is False


def test_invalid_alignment_backend():
    """Reject unsupported alignment backend."""

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            _env_prefix="GW_TEST_",
            alignment_backend="quantum",
        )


def test_invalid_upload_size():
    """Reject invalid upload limits."""

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            _env_prefix="GW_TEST_",
            max_upload_size_mb=0,
        )


def test_invalid_api_prefix():
    """Reject API prefixes without a leading slash."""

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            _env_prefix="GW_TEST_",
            api_prefix="api/v1",
        )


def test_settings_cache():
    """Verify cached settings are reused."""

    get_settings.cache_clear()

    first = get_settings()
    second = get_settings()

    assert first is second

    get_settings.cache_clear()
