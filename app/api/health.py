from fastapi import APIRouter, Depends
from typing import Dict
import asyncio
from datetime import datetime

from app.config import settings


router = APIRouter()


@router.get("/")
async def health_check() -> Dict:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.app_env,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/detailed")
async def detailed_health_check() -> Dict:
    """Detailed health check with service status."""
    health_status = {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.app_env,
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }

    # Check Redis
    try:
        import redis.asyncio as redis
        redis_client = redis.from_url(settings.redis_url)
        await redis_client.ping()
        health_status["services"]["redis"] = "healthy"
        await redis_client.close()
    except Exception as e:
        health_status["services"]["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    # Check Database
    try:
        from app.db.session import get_db_session
        async for session in get_db_session():
            await session.execute("SELECT 1")
            health_status["services"]["database"] = "healthy"
            break
    except Exception as e:
        health_status["services"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    return health_status


@router.get("/live")
async def liveness() -> Dict:
    """Kubernetes liveness probe - is the app running?"""
    return {"status": "alive"}


@router.get("/ready")
async def readiness() -> Dict:
    """Kubernetes readiness probe - is the app ready to serve traffic?"""
    # Check critical services
    try:
        import redis.asyncio as redis
        redis_client = redis.from_url(settings.redis_url)
        await redis_client.ping()
        await redis_client.close()
        return {"status": "ready"}
    except Exception:
        return {"status": "not_ready", "reason": "Redis unavailable"}
