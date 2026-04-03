"""
Run test command via terminal executor in a loop until exit 0 or max iterations.

Commands are constrained by the terminal executor whitelist (same as /execute).
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional

import requests
import structlog

logger = structlog.get_logger()

POLICY_FIX_UNTIL_GREEN_DISABLED = os.getenv("POLICY_FIX_UNTIL_GREEN_DISABLED", "false").lower() == "true"
FIX_UNTIL_GREEN_MAX_ITER = max(1, min(int(os.getenv("FIX_UNTIL_GREEN_MAX_ITER", "6")), 10))


def assert_fix_until_green_allowed() -> None:
    from fastapi import HTTPException

    if POLICY_FIX_UNTIL_GREEN_DISABLED:
        raise HTTPException(
            status_code=403,
            detail="fix_until_green disabled by policy (POLICY_FIX_UNTIL_GREEN_DISABLED=true)",
        )


def clamp_iterations(requested: int) -> int:
    return min(max(1, requested), FIX_UNTIL_GREEN_MAX_ITER)


def run_test_command(
    terminal_executor_url: str,
    command: str,
    working_directory: Optional[str],
    timeout: int,
    request_timeout: float,
) -> Dict[str, Any]:
    url = f"{terminal_executor_url.rstrip('/')}/execute"
    r = requests.post(
        url,
        json={
            "command": command,
            "working_directory": working_directory,
            "timeout": timeout,
            "stream": False,
        },
        timeout=min(float(timeout) + 20.0, request_timeout + 60.0),
    )
    r.raise_for_status()
    return r.json()


def fix_until_green_loop(
    *,
    max_iterations: int,
    test_command: str,
    test_working_directory: Optional[str],
    test_timeout: int,
    terminal_executor_url: str,
    request_timeout: float,
    answer_fn: Callable[..., Dict[str, Any]],
    initial_question: str,
) -> Dict[str, Any]:
    """
    Repeatedly call answer_fn(question=...) then run test_command until exit 0 or max_iterations.
    answer_fn must return a dict with at least 'answer' and optional 'meta', 'contexts', etc.
    """
    iterations: List[Dict[str, Any]] = []
    question = initial_question
    last_response: Optional[Dict[str, Any]] = None

    for i in range(max_iterations):
        last_response = answer_fn(question=question)
        ans = last_response.get("answer", "")
        meta = last_response.get("meta") or {}
        it: Dict[str, Any] = {"iteration": i + 1, "meta": meta}
        try:
            test_out = run_test_command(
                terminal_executor_url,
                test_command,
                test_working_directory,
                test_timeout,
                request_timeout,
            )
        except Exception as e:
            logger.error("fix_until_green test execution failed", error=str(e))
            it["test_error"] = str(e)
            iterations.append(it)
            question = (
                f"{initial_question}\n\n"
                f"Previous assistant answer (iteration {i + 1}):\n{ans}\n\n"
                f"Test runner failed before completion: {e}\n"
                "Fix the issue and suggest concrete code or config changes."
            )
            continue

        it["exit_code"] = test_out.get("exit_code")
        it["stdout"] = (test_out.get("stdout") or "")[:12000]
        it["stderr"] = (test_out.get("stderr") or "")[:12000]
        iterations.append(it)

        if test_out.get("exit_code") == 0:
            return {
                "response": last_response,
                "fix_until_green": {
                    "completed": True,
                    "iterations": iterations,
                    "final_test_exit": 0,
                },
            }

        question = (
            f"{initial_question}\n\n"
            f"Previous assistant answer (iteration {i + 1}):\n{ans}\n\n"
            f"The test command failed.\n"
            f"Command: {test_command}\n"
            f"Exit code: {test_out.get('exit_code')}\n"
            f"stdout:\n{it['stdout']}\n\n"
            f"stderr:\n{it['stderr']}\n\n"
            "Propose a minimal fix (code or tests) so the command succeeds."
        )

    return {
        "response": last_response or {"answer": "", "meta": {}, "contexts": []},
        "fix_until_green": {
            "completed": False,
            "iterations": iterations,
            "final_test_exit": iterations[-1].get("exit_code") if iterations else None,
        },
    }
