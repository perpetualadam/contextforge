"""
Internet / public-facing deployment profile for the API gateway.

When PUBLIC_DEPLOYMENT=true, startup fails fast unless required security env vars are set.
When false (default), no checks run — local dev and tests unchanged.

Does not remove features: same endpoints; only enforces a safe configuration surface.
"""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Minimum length for each API key when PUBLIC_DEPLOYMENT is enabled (use long random secrets).
MIN_API_KEY_LENGTH = 24


def is_public_deployment() -> bool:
    return os.getenv("PUBLIC_DEPLOYMENT", "").lower() in ("true", "1", "yes")


def audit_public_deployment() -> Dict[str, Any]:
    """
    Non-destructive readiness report (no secrets). Safe to expose via GET /config.
    """
    enabled = is_public_deployment()
    errors: List[str] = []
    warnings: List[str] = []
    recommendations: List[str] = [
        "Terminate TLS at a reverse proxy (nginx, Caddy, Traefik, cloud LB); do not expose uvicorn directly.",
        "Allow only the proxy security group / firewall to reach the gateway port; browsers hit the proxy URL.",
        "Point ALLOWED_ORIGINS at your real SPA origin(s), e.g. https://app.example.com",
        "Set CSRF_SECRET_KEY to a stable random value so CSRF cookies survive restarts.",
    ]

    if not enabled:
        return {
            "public_deployment": False,
            "ready": True,
            "errors": [],
            "warnings": [],
            "recommendations": recommendations,
        }

    if os.getenv("API_KEY_ENABLED", "").lower() not in ("true", "1", "yes"):
        errors.append("API_KEY_ENABLED must be true when PUBLIC_DEPLOYMENT=true")

    raw_keys = os.getenv("API_KEYS") or ""
    keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
    if not keys:
        errors.append("API_KEYS must contain at least one key when PUBLIC_DEPLOYMENT=true")
    else:
        short = [k for k in keys if len(k) < MIN_API_KEY_LENGTH]
        if short:
            warnings.append(
                f"Each API key should be at least {MIN_API_KEY_LENGTH} characters; "
                "generate with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )

    if not (os.getenv("TRUSTED_HOSTS", "").strip()):
        errors.append("TRUSTED_HOSTS must be set (comma-separated Host values) when PUBLIC_DEPLOYMENT=true")

    origins = [o.strip() for o in (os.getenv("ALLOWED_ORIGINS") or "").split(",") if o.strip()]
    if not origins:
        errors.append("ALLOWED_ORIGINS must list at least one explicit origin when PUBLIC_DEPLOYMENT=true")
    else:
        for o in origins:
            if o == "*":
                errors.append(
                    "ALLOWED_ORIGINS cannot be '*' when PUBLIC_DEPLOYMENT=true (incompatible with credentials/CORS safety)"
                )
            if o.startswith("http://") and "localhost" not in o and "127.0.0.1" not in o:
                warnings.append(
                    f"Origin {o!r} uses http — prefer https for production public deployments"
                )

    if os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("false", "0", "no"):
        warnings.append("RATE_LIMIT_ENABLED is off — consider leaving rate limiting on for public endpoints")

    if not (os.getenv("CSRF_SECRET_KEY", "").strip()):
        warnings.append("CSRF_SECRET_KEY is unset — CSRF tokens reset on every gateway restart")

    if os.getenv("COOKIE_SECURE", "").lower() not in ("true", "1", "yes"):
        warnings.append(
            "COOKIE_SECURE should be true for HTTPS public deployments (auth cookies)"
        )

    return {
        "public_deployment": True,
        "ready": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "recommendations": recommendations,
    }


def validate_public_deployment_settings() -> None:
    """
    Call during application startup. Raises RuntimeError if PUBLIC_DEPLOYMENT=true and checks fail.
    """
    if not is_public_deployment():
        return
    report = audit_public_deployment()
    for w in report.get("warnings", []):
        logger.warning("[PUBLIC_DEPLOYMENT] %s", w)
    if report.get("errors"):
        for e in report["errors"]:
            logger.error("[PUBLIC_DEPLOYMENT] %s", e)
        detail = "; ".join(report["errors"])
        raise RuntimeError(
            f"PUBLIC_DEPLOYMENT=true but configuration is not safe for internet exposure: {detail}. "
            "See .env.example (PUBLIC_DEPLOYMENT section)."
        )
    logger.info("PUBLIC_DEPLOYMENT mode: security checks passed")
