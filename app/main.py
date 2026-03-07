from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from contextlib import asynccontextmanager

from app.config import settings
from app.api import whatsapp_uazapi, pixbank, health


# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info(f"Starting {settings.app_name}...")
    logger.info(f"Environment: {settings.app_env}")
    yield
    logger.info(f"Shutting down {settings.app_name}...")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Sistema de Automação Comercial com IA para WhatsApp",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )


# Include routers
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(whatsapp_uazapi.router, prefix="/webhooks/whatsapp", tags=["WhatsApp"])
app.include_router(pixbank.router, prefix="/webhooks/pixbank", tags=["PixBank"])


# Root endpoint
@app.get("/")
async def root():
    return {
        "app": settings.app_name,
        "version": "1.0.0",
        "status": "running",
        "environment": settings.app_env
    }


# Startup info
@app.on_event("startup")
async def startup_event():
    logger.info(f"API ready and listening on {settings.api_host}:{settings.api_port}")
