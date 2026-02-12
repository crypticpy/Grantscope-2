"""
Security Module for Foresight API

Implements production-grade security hardening including:
- Rate limiting (IP-based using slowapi)
- Security headers middleware
- Request ID generation for audit logging
- Request size validation
- Secure error response handling

Configuration via environment variables:
- RATE_LIMIT_PER_MINUTE: Requests per minute per IP (default: 100)
- MAX_REQUEST_SIZE_MB: Maximum request body size in MB (default: 10)
- ENVIRONMENT: 'production' or 'development' (affects error detail exposure)
"""

import os
import uuid
import time
import logging
import ipaddress
from typing import Callable, Optional
from datetime import datetime

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

# Rate limiting configuration
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "100"))
DEFAULT_RATE_LIMIT = f"{RATE_LIMIT_PER_MINUTE}/minute"

# Request size limit (in bytes)
MAX_REQUEST_SIZE_MB = int(os.getenv("MAX_REQUEST_SIZE_MB", "10"))
MAX_REQUEST_SIZE_BYTES = MAX_REQUEST_SIZE_MB * 1024 * 1024

# Environment (affects error detail exposure)
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT.lower() == "production"


# =============================================================================
# Rate Limiter Setup
# =============================================================================

def _is_valid_ip(ip_str: str) -> bool:
    """Validate that a string is a valid IP address (IPv4 or IPv6)."""
    if not ip_str or len(ip_str) > 45:  # Max length for IPv6
        return False
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False


# Number of trusted proxies in front of the application
# Railway/Vercel typically add 1 proxy. Adjust based on your infrastructure.
TRUSTED_PROXY_COUNT = int(os.getenv("TRUSTED_PROXY_COUNT", "1"))


def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request with anti-spoofing protection.

    Uses the "rightmost non-trusted" approach for X-Forwarded-For to prevent
    IP spoofing attacks. The X-Forwarded-For header can be spoofed by clients,
    but proxies append the connecting IP, so we trust IPs from the right.

    Example: "spoofed, real-client, proxy1, proxy2" with TRUSTED_PROXY_COUNT=2
    Result: "real-client" (2 positions from right, after trusted proxies)

    Args:
        request: The FastAPI request object

    Returns:
        The client IP address, or "unknown" if not determinable
    """
    # First, get the direct connection IP as fallback
    direct_ip = request.client.host if request.client else None

    if forwarded_for := request.headers.get("X-Forwarded-For"):
        if ips := [
            ip.strip() for ip in forwarded_for.split(",") if ip.strip()
        ]:
            # Use rightmost non-trusted IP approach:
            # - The rightmost IPs are added by our trusted proxies
            # - The IP just before our proxies is the real client
            # - Any IPs further left could be spoofed

            if len(ips) > TRUSTED_PROXY_COUNT:
                # Get the IP just before our trusted proxy chain
                client_ip = ips[-(TRUSTED_PROXY_COUNT + 1)]
            else:
                # Not enough IPs for our proxy count, take the leftmost
                # This handles direct connections through fewer proxies
                client_ip = ips[0]

            # Validate the extracted IP to prevent log injection attacks
            if _is_valid_ip(client_ip):
                return client_ip
            else:
                logger.warning(
                    f"Invalid IP in X-Forwarded-For header: {client_ip[:50]!r}",
                    extra={"direct_ip": direct_ip}
                )
                # Fall through to use direct IP

    if real_ip := request.headers.get("X-Real-IP"):
        real_ip = real_ip.strip()
        if _is_valid_ip(real_ip):
            return real_ip
        else:
            logger.warning(
                f"Invalid X-Real-IP header: {real_ip[:50]!r}",
                extra={"direct_ip": direct_ip}
            )

    # Fallback to direct client connection IP
    return direct_ip if direct_ip and _is_valid_ip(direct_ip) else "unknown"


# Initialize the rate limiter with custom IP extraction
limiter = Limiter(
    key_func=get_client_ip,
    default_limits=[DEFAULT_RATE_LIMIT],
    storage_uri="memory://",  # In-memory storage (use Redis for multi-instance)
    strategy="fixed-window",
)


def get_rate_limiter() -> Limiter:
    """Get the configured rate limiter instance."""
    return limiter


# =============================================================================
# Security Headers Middleware
# =============================================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.

    Headers added:
    - X-Frame-Options: Prevents clickjacking attacks
    - X-Content-Type-Options: Prevents MIME type sniffing
    - Strict-Transport-Security: Enforces HTTPS
    - Referrer-Policy: Controls referrer information
    - Permissions-Policy: Restricts browser features
    - X-Request-ID: Unique request identifier for audit logging
    - X-XSS-Protection: Legacy XSS protection (for older browsers)
    - Cache-Control: Prevents caching of sensitive responses
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Generate unique request ID for audit logging
        request_id = str(uuid.uuid4())

        # Store request ID in request state for logging
        request.state.request_id = request_id
        request.state.start_time = time.time()

        # Process the request
        response = await call_next(request)

        # Add security headers
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        # HSTS header - only in production with HTTPS
        if IS_PRODUCTION:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Add request ID to response for client-side tracking
        response.headers["X-Request-ID"] = request_id

        # Prevent caching of API responses with sensitive data
        if not response.headers.get("Cache-Control"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"

        # Calculate and log request duration
        duration = time.time() - request.state.start_time
        logger.info(
            f"Request completed: {request.method} {request.url.path} "
            f"status={response.status_code} duration={duration:.3f}s "
            f"request_id={request_id} client_ip={get_client_ip(request)}"
        )

        return response


# =============================================================================
# Request Size Limit Middleware
# =============================================================================

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce request body size limits.

    Prevents denial-of-service attacks via large payloads.
    Configurable via MAX_REQUEST_SIZE_MB environment variable.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if content_length := request.headers.get("content-length"):
            try:
                size = int(content_length)
                if size > MAX_REQUEST_SIZE_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": f"Request body too large. Maximum size is {MAX_REQUEST_SIZE_MB}MB.",
                            "code": "REQUEST_TOO_LARGE"
                        }
                    )
            except ValueError:
                # Invalid content-length header
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": "Invalid Content-Length header",
                        "code": "INVALID_CONTENT_LENGTH"
                    }
                )

        return await call_next(request)


# =============================================================================
# Secure Error Handler
# =============================================================================

def create_secure_exception_handler(allowed_origins: list[str]) -> Callable:
    """
    Create a secure exception handler that sanitizes error responses.

    In production:
    - Internal server errors return generic messages
    - Stack traces are never exposed
    - Error details are logged but not returned

    In development:
    - Full error details are returned for debugging
    """

    async def secure_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle all unhandled exceptions with secure error responses."""
        # Get request ID for logging correlation
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

        # Get the origin from the request for CORS
        origin = request.headers.get("origin", "")

        # Build response headers
        headers = {"X-Request-ID": request_id}
        if origin in allowed_origins:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"

        # Log the full error for debugging
        logger.error(
            f"Unhandled exception: {type(exc).__name__}: {str(exc)} "
            f"request_id={request_id} path={request.url.path} "
            f"method={request.method} client_ip={get_client_ip(request)}",
            exc_info=True
        )

        # Determine error response based on environment
        if IS_PRODUCTION:
            # Production: Return generic error message
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "An internal server error occurred. Please try again later.",
                    "code": "INTERNAL_ERROR",
                    "request_id": request_id
                },
                headers=headers
            )
        else:
            # Development: Return full error details
            return JSONResponse(
                status_code=500,
                content={
                    "detail": str(exc),
                    "error_type": type(exc).__name__,
                    "request_id": request_id
                },
                headers=headers
            )

    return secure_exception_handler


def create_rate_limit_exceeded_handler(allowed_origins: list[str]) -> Callable:
    """
    Create a custom rate limit exceeded handler with CORS support.
    """

    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        """Handle rate limit exceeded errors."""
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        origin = request.headers.get("origin", "")

        headers = {
            "X-Request-ID": request_id,
            "Retry-After": "60"  # Suggest retry after 60 seconds
        }
        if origin in allowed_origins:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"

        # Log rate limit violation for security monitoring
        logger.warning(
            f"Rate limit exceeded: client_ip={get_client_ip(request)} "
            f"path={request.url.path} request_id={request_id}"
        )

        return JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit exceeded. Please slow down your requests.",
                "code": "RATE_LIMIT_EXCEEDED",
                "retry_after_seconds": 60,
                "request_id": request_id
            },
            headers=headers
        )

    return rate_limit_handler


# =============================================================================
# HTTP Exception Handler (for 4xx errors)
# =============================================================================

def create_http_exception_handler(allowed_origins: list[str]) -> Callable:
    """
    Create an HTTP exception handler that maintains CORS and adds security.
    """

    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Handle HTTP exceptions with proper security measures."""
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        origin = request.headers.get("origin", "")

        headers = {"X-Request-ID": request_id}
        if origin in allowed_origins:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"

        # Log authentication failures for security monitoring
        if exc.status_code == 401:
            logger.warning(
                f"Authentication failed: client_ip={get_client_ip(request)} "
                f"path={request.url.path} request_id={request_id}"
            )
        elif exc.status_code == 403:
            logger.warning(
                f"Authorization denied: client_ip={get_client_ip(request)} "
                f"path={request.url.path} request_id={request_id}"
            )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "request_id": request_id
            },
            headers=headers
        )

    return http_exception_handler


# =============================================================================
# Security Setup Function
# =============================================================================

def setup_security(app: FastAPI, allowed_origins: list[str]) -> None:
    """
    Configure all security middleware and handlers for a FastAPI application.

    This function should be called during app initialization to set up:
    - Rate limiting
    - Security headers
    - Request size limits
    - Secure error handling

    Args:
        app: The FastAPI application instance
        allowed_origins: List of allowed CORS origins
    """
    # Store limiter in app state for use by route decorators
    app.state.limiter = limiter

    # Add rate limiting middleware
    app.add_middleware(SlowAPIMiddleware)

    # Add security headers middleware (runs after rate limiting)
    app.add_middleware(SecurityHeadersMiddleware)

    # Add request size limit middleware
    app.add_middleware(RequestSizeLimitMiddleware)

    # Register exception handlers
    app.add_exception_handler(
        RateLimitExceeded,
        create_rate_limit_exceeded_handler(allowed_origins)
    )
    app.add_exception_handler(
        Exception,
        create_secure_exception_handler(allowed_origins)
    )
    app.add_exception_handler(
        HTTPException,
        create_http_exception_handler(allowed_origins)
    )

    logger.info(
        f"Security middleware configured: "
        f"rate_limit={RATE_LIMIT_PER_MINUTE}/min, "
        f"max_request_size={MAX_REQUEST_SIZE_MB}MB, "
        f"environment={ENVIRONMENT}"
    )


# =============================================================================
# Rate Limit Decorators for Sensitive Endpoints
# =============================================================================

# Stricter rate limits for sensitive operations
SENSITIVE_RATE_LIMIT = "10/minute"  # 10 requests per minute
AUTH_RATE_LIMIT = "5/minute"  # 5 auth attempts per minute
DISCOVERY_RATE_LIMIT = "3/minute"  # 3 discovery runs per minute


def rate_limit_sensitive():
    """Decorator for sensitive endpoints with stricter rate limiting."""
    return limiter.limit(SENSITIVE_RATE_LIMIT)


def rate_limit_auth():
    """Decorator for authentication endpoints with strict rate limiting."""
    return limiter.limit(AUTH_RATE_LIMIT)


def rate_limit_discovery():
    """Decorator for discovery/research endpoints with strict rate limiting."""
    return limiter.limit(DISCOVERY_RATE_LIMIT)


# =============================================================================
# Audit Logging Utilities
# =============================================================================

def log_security_event(
    event_type: str,
    request: Request,
    details: Optional[dict] = None
) -> None:
    """
    Log a security-relevant event for audit purposes.

    Args:
        event_type: Type of security event (e.g., 'auth_failure', 'rate_limit')
        request: The request object
        details: Optional additional details to log
    """
    request_id = getattr(request.state, "request_id", "unknown")
    client_ip = get_client_ip(request)

    log_data = {
        "event_type": event_type,
        "request_id": request_id,
        "client_ip": client_ip,
        "path": request.url.path,
        "method": request.method,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if details:
        log_data |= details

    logger.warning(f"SECURITY_EVENT: {log_data}")
