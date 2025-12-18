"""Main entry point for the RPC Benchmarker application."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import router as api_router
from .core.config import settings
from .core.database import init_db
from .services import ChainService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    print(f"Starting RPC Benchmarker v{settings.app_version}")
    print(f"Data directory: {settings.data_dir}")

    # Ensure data directory exists
    settings.ensure_data_dir()

    # Initialize database
    await init_db()

    # Load preset chains
    chain_service = ChainService()
    chain_service.ensure_presets_loaded()

    yield

    # Shutdown
    print("Shutting down RPC Benchmarker")


app = FastAPI(
    title="RPC Benchmarker",
    description="Benchmark and compare RPC provider performance",
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(api_router, prefix="/api")

# Static files
frontend_dir = Path(__file__).parent.parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/")
async def index():
    """Serve the main HTML page."""
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "RPC Benchmarker API", "docs": "/docs"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}


def main():
    """Run the application with uvicorn."""
    import uvicorn

    uvicorn.run(
        "backend.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
