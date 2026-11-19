"""
GeneWeaver - Main Application

Creates and configures the FastAPI application.
Provides a clickable API dashboard and startup endpoint links.
"""

import logging
from contextlib import asynccontextmanager
from html import escape

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.api.v1.endpoints.health import health_check
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings

logger = logging.getLogger("geneweaver")


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Application factory.

    Creates a configured GeneWeaver FastAPI instance.
    Supports custom settings for automated testing.
    """

    app_settings = settings or get_settings()

    is_production = app_settings.environment == "production"

    # Application lifecycle
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        """Handle application startup and shutdown."""

        logger.info("=" * 60)
        logger.info("GENEWEAVER API SERVER STARTED")
        logger.info("Application: %s", app_settings.app_name)
        logger.info("Version: %s", app_settings.app_version)
        logger.info("Environment: %s", app_settings.environment)
        logger.info("=" * 60)

        # Display available endpoints in terminal
        logger.info("AVAILABLE API ENDPOINTS:")

        endpoints = [
            ("API Dashboard", "/"),
            ("Root Health", "/health"),
            ("Versioned Health", f"{app_settings.api_prefix}/health"),
        ]

        if not is_production:
            endpoints.extend(
                [
                    ("Swagger Documentation", "/docs"),
                    ("ReDoc Documentation", "/redoc"),
                    ("OpenAPI Schema", "/openapi.json"),
                ]
            )

        for name, path in endpoints:
            logger.info("%-25s http://127.0.0.1:8000%s", name, path)

        logger.info("=" * 60)

        yield

        logger.info("GeneWeaver application shutting down.")

    # Create FastAPI instance
    application = FastAPI(
        title=app_settings.app_name,
        description=(
            "GPU-Accelerated CRISPR-Cas9 Alignment Engine "
            "for genomic sequence analysis and off-target screening."
        ),
        version=app_settings.app_version,
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
        lifespan=lifespan,
        debug=app_settings.debug,
    )

    # Make settings accessible throughout the application
    application.state.settings = app_settings

    # Configure CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=[
            "GET",
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
            "OPTIONS",
        ],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
        ],
    )

    # Register versioned API endpoints
    application.include_router(
        api_router,
        prefix=app_settings.api_prefix,
    )

    # Root health endpoint
    application.add_api_route(
        "/health",
        health_check,
        methods=["GET"],
        tags=["Health"],
        include_in_schema=False,
    )

    # API dashboard with clickable links
    @application.get(
        "/",
        response_class=HTMLResponse,
        tags=["Root"],
        include_in_schema=False,
    )
    async def root(request: Request):
        """Display all available GeneWeaver API links."""

        base_url = str(request.base_url).rstrip("/")

        endpoints = [
            ("API Dashboard", "/", "Main application page"),
            ("Health Check", "/health", "Application health status"),
            (
                "API v1 Health",
                f"{app_settings.api_prefix}/health",
                "Versioned API health status",
            ),
        ]

        if not is_production:
            endpoints.extend(
                [
                    ("Swagger UI", "/docs", "Interactive API documentation"),
                    ("ReDoc", "/redoc", "Alternative API documentation"),
                    ("OpenAPI JSON", "/openapi.json", "API specification"),
                ]
            )

        endpoint_html = ""

        for name, path, description in endpoints:
            safe_name = escape(name)
            safe_path = escape(path, quote=True)
            safe_description = escape(description)
            full_url = f"{base_url}{path}"

            endpoint_html += f"""
                <div class="endpoint">
                    <div class="endpoint-name">{safe_name}</div>
                    <div class="description">{safe_description}</div>
                    <a href="{safe_path}" target="_blank" rel="noopener noreferrer">
                        {escape(full_url)}
                    </a>
                </div>
            """

        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>GeneWeaver API Dashboard</title>

            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background: #f1f5f9;
                    margin: 0;
                    padding: 40px 20px;
                    color: #1e293b;
                }}

                .container {{
                    max-width: 850px;
                    margin: auto;
                    background: white;
                    padding: 35px;
                    border-radius: 14px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
                }}

                h1 {{
                    color: #1769aa;
                    margin-bottom: 8px;
                }}

                .status {{
                    color: #15803d;
                    font-weight: bold;
                }}

                .endpoint {{
                    background: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 9px;
                    padding: 16px;
                    margin: 14px 0;
                }}

                .endpoint-name {{
                    font-weight: bold;
                    font-size: 17px;
                    margin-bottom: 6px;
                }}

                .description {{
                    color: #64748b;
                    font-size: 13px;
                    margin-bottom: 8px;
                }}

                a {{
                    color: #1769aa;
                    text-decoration: none;
                    overflow-wrap: anywhere;
                }}

                a:hover {{
                    text-decoration: underline;
                }}

                .footer {{
                    margin-top: 25px;
                    color: #64748b;
                    font-size: 13px;
                }}
            </style>
        </head>

        <body>
            <div class="container">

                <h1>GeneWeaver API</h1>

                <p class="status">
                    ● Application is running successfully
                </p>

                <p>
                    GPU-Accelerated CRISPR-Cas9 Alignment Engine
                </p>

                <h2>Available API Endpoints</h2>

                {endpoint_html}

                <div class="footer">
                    Version: {escape(app_settings.app_version)}
                    <br>
                    Environment: {escape(app_settings.environment)}
                </div>

            </div>
        </body>
        </html>
        """

    logger.info(
        "%s application configured successfully",
        app_settings.app_name,
    )

    return application


# Main application instance
app = create_app()
