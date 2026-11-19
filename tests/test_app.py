"""Integration tests for GeneWeaver FastAPI application."""

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def create_test_settings() -> Settings:
    """Create isolated settings for testing."""

    return Settings(
        _env_file=None,
        app_name="GeneWeaver Test",
        app_version="0.1.0",
        environment="testing",
        debug=False,
        api_prefix="/api/v1",
        cors_origins=["http://localhost:3000"],
    )


def test_application_initialization():
    """Verify that the application is created."""

    application = create_app(create_test_settings())

    assert application.title == "GeneWeaver Test"
    assert application.version == "0.1.0"


def test_root_health_endpoint():
    """Verify root health endpoint."""

    application = create_app(create_test_settings())

    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == 200

    assert response.json() == {
        "status": "healthy",
        "service": "GeneWeaver Test",
        "version": "0.1.0",
    }


def test_versioned_health_endpoint():
    """Verify versioned health endpoint."""

    application = create_app(create_test_settings())

    with TestClient(application) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_swagger_documentation():
    """Verify Swagger documentation is accessible."""

    application = create_app(create_test_settings())

    with TestClient(application) as client:
        response = client.get("/docs")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_openapi_schema():
    """Verify OpenAPI schema generation."""

    application = create_app(create_test_settings())

    with TestClient(application) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200

    schema = response.json()

    assert schema["info"]["title"] == "GeneWeaver Test"
    assert schema["info"]["version"] == "0.1.0"


def test_cors_preflight_request():
    """Verify that configured frontend origin is permitted."""

    application = create_app(create_test_settings())

    with TestClient(application) as client:
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_unconfigured_origin_is_not_allowed():
    """Verify that an unconfigured origin is rejected."""

    application = create_app(create_test_settings())

    with TestClient(application) as client:
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://untrusted.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert "access-control-allow-origin" not in response.headers


def test_production_disables_api_documentation():
    """Verify Swagger and OpenAPI are disabled in production."""

    production_settings = Settings(
        _env_file=None,
        app_name="GeneWeaver",
        environment="production",
        debug=False,
    )

    application = create_app(production_settings)

    with TestClient(application) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
