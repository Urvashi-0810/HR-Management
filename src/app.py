"""
app.py — FastAPI application factory.

Creates and configures the FastAPI app with CORS, routes, and middleware.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import LOG_LEVEL
from src.api.routes import router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
        datefmt="%H:%M:%S",
    )

    app = FastAPI(
        title="HR Management System API",
        description=(
            "Backend API for the HR Management System.\n\n"
            "**Pipeline Steps:**\n"
            "1. Download CV attachments from email\n"
            "2. Extract structured data from CVs using LLM\n"
            "3. Shortlist candidates by criteria\n"
            "4. Score candidates against a job description\n"
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS — allow React frontend (dev on localhost:3000 / 5173)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routes
    app.include_router(router)

    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "service": "HR Management System",
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


# Application instance (for uvicorn)
app = create_app()
