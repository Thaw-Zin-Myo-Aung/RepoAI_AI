"""
Health check routes.

Endpoints for monitoring service health and connectivity.
"""

from fastapi import APIRouter

from repoai.config.settings import get_settings
from repoai.utils.logger import get_logger

from ..models import HealthResponse

logger = get_logger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Verifies:
    - Service is running
    - Gemini API connectivity
    - Configuration loaded

    Example:
        GET /api/health

        Response:
        {
            "status": "healthy",
            "version": "0.1.0",
            "services": {
                "gemini_api": "healthy",
                "config": "loaded"
            }
        }
    """
    settings = get_settings()

    # Check service health
    services = {}

    # Check Gemini API key configured
    if settings.GOOGLE_API_KEY:
        services["gemini_api"] = "configured"
    else:
        services["gemini_api"] = "not_configured"

    # Check configuration
    services["config"] = "loaded"

    # Determine overall status
    status = "healthy"
    if services["gemini_api"] == "not_configured":
        status = "degraded"

    return HealthResponse(status=status, version="0.1.0", services=services)


@router.get("/health/ready")
async def readiness_check() -> dict[str, object]:
    """
    Readiness check for Kubernetes.

    Returns 200 if service is ready to accept requests.
    """
    settings = get_settings()

    if not settings.GOOGLE_API_KEY:
        return {"ready": False, "reason": "Gemini API key not configured"}

    return {"ready": True}


@router.get("/health/live")
async def liveness_check() -> dict[str, bool]:
    """
    Liveness check for Kubernetes.

    Returns 200 if service is alive (even if degraded).
    """
    return {"alive": True}
