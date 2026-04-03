"""
Optional OIDC (JWT via JWKS) and per-workspace RBAC.

- Identity: X-Access-Token (or X-Id-Token) carries an OIDC access/id JWT when OIDC_JWKS_URL is set.
  Authorization: Bearer remains reserved for API keys (gateway_security.verify_api_key).
- RBAC: JSON map at RBAC_MAP_PATH (see data/rbac/rbac.example.json).
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional

import jwt
from fastapi import HTTPException, Request
from jwt import PyJWKClient

RBAC_ENABLED = os.getenv("RBAC_ENABLED", "false").lower() == "true"
RBAC_TRUST_HEADERS = os.getenv("RBAC_TRUST_HEADERS", "false").lower() == "true"
RBAC_API_KEY_FALLBACK_ROLE = os.getenv("RBAC_API_KEY_FALLBACK_ROLE", "").strip().lower()

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_default_map = REPO_ROOT / "data" / "rbac" / "rbac.json"
RBAC_MAP_PATH = os.getenv("RBAC_MAP_PATH", "").strip() or str(_default_map)

OIDC_JWKS_URL = os.getenv("OIDC_JWKS_URL", "").strip()
OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE", "").strip()
OIDC_ISSUER = os.getenv("OIDC_ISSUER", "").strip()

ROLE_ORDER = {"read": 1, "write": 2, "admin": 3}

_rbac_map: Optional[Dict[str, Any]] = None
_jwks_client: Optional[PyJWKClient] = None
_jwks_lock = threading.Lock()


def load_rbac_map() -> Dict[str, Any]:
    global _rbac_map
    if _rbac_map is not None:
        return _rbac_map
    path = Path(RBAC_MAP_PATH)
    if not path.is_file():
        _rbac_map = {"workspaces": {}}
        return _rbac_map
    with open(path, encoding="utf-8") as f:
        _rbac_map = json.load(f)
    return _rbac_map


def _get_jwks() -> Optional[PyJWKClient]:
    global _jwks_client
    if not OIDC_JWKS_URL:
        return None
    with _jwks_lock:
        if _jwks_client is None:
            _jwks_client = PyJWKClient(OIDC_JWKS_URL)
        return _jwks_client


def decode_oidc_token(token: str) -> Dict[str, Any]:
    if not OIDC_AUDIENCE:
        raise ValueError("OIDC_AUDIENCE must be set when OIDC_JWKS_URL is used")
    jwks = _get_jwks()
    if not jwks:
        raise ValueError("OIDC_JWKS_URL not configured")
    signing_key = jwks.get_signing_key_from_jwt(token)
    opts: Dict[str, Any] = {
        "algorithms": ["RS256", "ES256"],
        "audience": OIDC_AUDIENCE,
    }
    if OIDC_ISSUER:
        opts["issuer"] = OIDC_ISSUER
    return jwt.decode(token, signing_key.key, **opts)


def identity_string_from_request(request: Request) -> Optional[str]:
    raw = request.headers.get("X-Access-Token") or request.headers.get("X-Id-Token")
    if raw and OIDC_JWKS_URL:
        tok = raw[7:].strip() if raw.startswith("Bearer ") else raw.strip()
        if tok:
            try:
                claims = decode_oidc_token(tok)
                return (
                    (claims.get("email") or claims.get("preferred_username") or claims.get("sub") or "")
                    .strip()
                    or None
                )
            except Exception:
                pass
    if RBAC_TRUST_HEADERS:
        email = request.headers.get("X-User-Email") or request.headers.get("X-Auth-Request-Email")
        if email:
            return email.strip()
    return None


def _effective_role_level(email: Optional[str], workspace_id: str, rbac_map: Dict[str, Any]) -> int:
    ws_all = rbac_map.get("workspaces") or {}
    best = 0
    for wid in (workspace_id, "default"):
        if wid not in ws_all:
            continue
        cfg = ws_all[wid]
        if isinstance(cfg, dict) and cfg.get("allow_all"):
            return 3
        if not isinstance(cfg, dict):
            continue
        if not email:
            continue
        for role_name in ("admin", "write", "read"):
            if role_name not in cfg:
                continue
            members = cfg.get(role_name) or []
            if not isinstance(members, list):
                continue
            if email in members or "*" in members:
                best = max(best, ROLE_ORDER.get(role_name, 0))
    return best


def enforce_workspace_rbac(
    request: Request,
    workspace_id: Optional[str],
    api_key: Optional[str],
    min_level: str = "read",
) -> None:
    if not RBAC_ENABLED:
        return
    if not workspace_id:
        return
    need = ROLE_ORDER.get(min_level, 1)
    rbac_map = load_rbac_map()
    email = identity_string_from_request(request)

    if not email and api_key and RBAC_API_KEY_FALLBACK_ROLE:
        fb = ROLE_ORDER.get(RBAC_API_KEY_FALLBACK_ROLE, 0)
        if fb >= need:
            return
        raise HTTPException(
            status_code=403,
            detail="Insufficient role for this workspace (API key fallback)",
        )

    level = _effective_role_level(email, workspace_id, rbac_map)
    if level >= need:
        return

    if not email:
        raise HTTPException(
            status_code=401,
            detail="RBAC: send X-Access-Token (OIDC JWT) or RBAC_TRUST_HEADERS with X-User-Email, "
            "or use a workspace with allow_all in rbac.json",
        )
    raise HTTPException(
        status_code=403,
        detail=f"Not allowed for workspace {workspace_id!r} at required role {min_level!r}",
    )
