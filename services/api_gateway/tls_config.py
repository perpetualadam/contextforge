"""
TLS/SSL Configuration for API Gateway.

Provides TLS certificate loading and uvicorn SSL configuration.

Copyright (c) 2025 ContextForge
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# TLS Configuration
TLS_ENABLED = os.getenv("TLS_ENABLED", "false").lower() in ("true", "1", "yes")
TLS_CERT_PATH = os.getenv("TLS_CERT_PATH", "/run/secrets/tls_cert")
TLS_KEY_PATH = os.getenv("TLS_KEY_PATH", "/run/secrets/tls_key")

# Fallback to local certs directory if secrets not available
if not Path(TLS_CERT_PATH).exists():
    TLS_CERT_PATH = os.getenv("TLS_CERT_PATH", "./certs/server.crt")
if not Path(TLS_KEY_PATH).exists():
    TLS_KEY_PATH = os.getenv("TLS_KEY_PATH", "./certs/server.key")


def get_ssl_config() -> Optional[Dict[str, Any]]:
    """
    Get SSL configuration for uvicorn.
    
    Returns:
        Dictionary with ssl_keyfile and ssl_certfile paths, or None if TLS disabled
    """
    if not TLS_ENABLED:
        logger.info("TLS/SSL is disabled")
        return None
    
    cert_path = Path(TLS_CERT_PATH)
    key_path = Path(TLS_KEY_PATH)
    
    # Validate certificate files exist
    if not cert_path.exists():
        logger.error(f"TLS certificate not found: {cert_path}")
        logger.warning("TLS enabled but certificate missing - running without TLS")
        return None
    
    if not key_path.exists():
        logger.error(f"TLS private key not found: {key_path}")
        logger.warning("TLS enabled but private key missing - running without TLS")
        return None
    
    logger.info(f"TLS/SSL enabled with certificate: {cert_path}")
    
    return {
        "ssl_keyfile": str(key_path),
        "ssl_certfile": str(cert_path),
        "ssl_version": 3,  # TLS 1.2+
        "ssl_cert_reqs": 0,  # No client certificate required
    }


def validate_tls_config() -> bool:
    """
    Validate TLS configuration.
    
    Returns:
        True if TLS is properly configured or disabled, False if misconfigured
    """
    if not TLS_ENABLED:
        return True
    
    cert_path = Path(TLS_CERT_PATH)
    key_path = Path(TLS_KEY_PATH)
    
    if not cert_path.exists():
        logger.error(f"TLS certificate not found: {cert_path}")
        return False
    
    if not key_path.exists():
        logger.error(f"TLS private key not found: {key_path}")
        return False
    
    # Check file permissions (should be readable)
    try:
        with open(cert_path, 'r') as f:
            f.read(1)
        with open(key_path, 'r') as f:
            f.read(1)
    except PermissionError:
        logger.error("TLS certificate or key file not readable - check permissions")
        return False
    except Exception as e:
        logger.error(f"Error reading TLS files: {e}")
        return False
    
    logger.info("TLS configuration validated successfully")
    return True


def get_server_url(host: str = "0.0.0.0", port: int = 8443) -> str:
    """
    Get the server URL based on TLS configuration.
    
    Args:
        host: Server host
        port: Server port
    
    Returns:
        Full server URL with https:// or http:// scheme
    """
    scheme = "https" if TLS_ENABLED and validate_tls_config() else "http"
    
    # Use localhost for display if binding to 0.0.0.0
    display_host = "localhost" if host == "0.0.0.0" else host
    
    return f"{scheme}://{display_host}:{port}"


def log_tls_status():
    """Log TLS/SSL status on startup."""
    if TLS_ENABLED:
        if validate_tls_config():
            logger.info("=" * 60)
            logger.info("TLS/SSL ENABLED")
            logger.info(f"Certificate: {TLS_CERT_PATH}")
            logger.info(f"Private Key: {TLS_KEY_PATH}")
            logger.info("=" * 60)
        else:
            logger.warning("=" * 60)
            logger.warning("TLS/SSL CONFIGURATION ERROR")
            logger.warning("Server will run without TLS")
            logger.warning("=" * 60)
    else:
        logger.info("TLS/SSL is disabled - running in HTTP mode")

