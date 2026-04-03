"""
Reserved API surface for future server-side GitHub integration (PRs, issues, etc.).

This is separate from:
- Path-based git via terminal executor: POST /git/repo-command
- VS Code extension: local simple-git + optional GitHub token in the editor

Security: tokens live only on the API gateway host (env / secrets). Never expose token values in responses.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from gateway_security import check_rate_limit, verify_api_key

router = APIRouter(prefix="/github", tags=["github-server"])


def github_server_disabled() -> bool:
    """Force-disable server GitHub features without removing secrets from the environment."""
    return os.getenv("GITHUB_SERVER_DISABLED", "").lower() in ("true", "1", "yes")


def github_server_token() -> str | None:
    """
    PAT or fine-grained token for GitHub REST API from the gateway process only.

    Precedence: GITHUB_SERVER_TOKEN (explicit server use), then GITHUB_TOKEN (common CI name).
    """
    if github_server_disabled():
        return None
    t = (
        os.getenv("GITHUB_SERVER_TOKEN", "").strip()
        or os.getenv("GITHUB_TOKEN", "").strip()
    )
    return t or None


def github_server_status_payload() -> Dict[str, Any]:
    """Serializable status for GET /github/status (no secrets)."""
    configured = bool(github_server_token())
    planned: List[str] = [
        "List/create PRs for a repo",
        "List/search issues",
        "Optional: link to indexed repo_path + remote URL validation",
    ]
    return {
        "github_server_configured": configured,
        "github_server_disabled": github_server_disabled(),
        "implementation": "stub",
        "planned_capabilities": planned,
        "client_hint": (
            "When implemented, use PyGithub or httpx against api.github.com; "
            "scope tokens minimally (repo / pull requests / issues as needed)."
        ),
    }


@router.get("/status")
async def get_github_server_status(
    request: Request,
    _rate: None = Depends(check_rate_limit),
    _api_key: Optional[str] = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    Whether a server-side GitHub token is available for future Octokit/PyGithub-style calls.
    Does not return the token or validate it against GitHub.
    """
    return github_server_status_payload()


@router.post("/server/placeholder")
async def github_server_placeholder(
    request: Request,
    _rate: None = Depends(check_rate_limit),
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Explicit 501 until PR/issue handlers exist. Keeps OpenAPI discoverability for integrators.
    """
    raise HTTPException(
        status_code=501,
        detail=(
            "Server-side GitHub API (PRs/issues) is not implemented yet. "
            "Set GITHUB_SERVER_TOKEN on the gateway for future releases; "
            "use the VS Code extension or git CLI for GitHub today."
        ),
    )
