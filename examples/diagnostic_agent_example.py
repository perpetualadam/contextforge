"""
Example usage of Integrated Diagnostic System.

Demonstrates:
- Internal diagnostic checks within MultiModeAgent
- Drift detection before edits
- Confidence checking
- Loop/token limit enforcement
- Comprehensive task review

Copyright (c) 2025 ContextForge
"""

import sys
from pathlib import Path

# Add services to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.core.local_multi_mode_agent import LocalMultiModeAgent
from services.core.safety import OperationLimits, OperationMetrics


def main():
    """Demonstrate integrated diagnostic system usage."""

    print("\n" + "="*70)
    print("  Integrated Diagnostic System Example")
    print("="*70 + "\n")

    # Initialize multi-mode agent with integrated diagnostics
    workspace_root = str(Path(__file__).parent.parent)
    agent = LocalMultiModeAgent(
        name="diagnostic-example",
        workspace_root=workspace_root,
        limits=OperationLimits(
            max_tool_calls=50,
            max_revisions=10,
            max_tokens=100000,
            max_files_per_operation=20,
            max_loop_iterations=5,
            timeout_seconds=300,
        )
    )

    print("✅ MultiModeAgent initialized with integrated diagnostics\n")
    print(f"   Agent: {agent.name}")
    print(f"   Diagnostics: {agent.diagnostics.__class__.__name__}\n")
    
    # Example 1: Check drift for a file using integrated diagnostics
    print("="*70)
    print("Example 1: Drift Detection (Integrated)")
    print("="*70 + "\n")

    test_file = "services/core/fingerprint.py"
    print(f"Checking drift for: {test_file}")

    # Access integrated diagnostics
    drift_result = agent.diagnostics.check_drift(test_file)
    print(f"\nResult: {drift_result.severity.upper()}")
    print(f"Passed: {drift_result.passed}")
    print(f"Message: {drift_result.message}")
    if drift_result.details:
        print(f"Details: {drift_result.details}")
    
    # Example 2: Check confidence using integrated diagnostics
    print("\n" + "="*70)
    print("Example 2: Confidence Checking (Integrated)")
    print("="*70 + "\n")

    print(f"Setting confidence for {test_file} to 85.0")
    confidence_result = agent.diagnostics.check_confidence(test_file, confidence=85.0)
    print(f"\nResult: {confidence_result.severity.upper()}")
    print(f"Passed: {confidence_result.passed}")
    print(f"Message: {confidence_result.message}")

    print(f"\nSetting confidence for {test_file} to 35.0 (critical)")
    confidence_result = agent.diagnostics.check_confidence(test_file, confidence=35.0)
    print(f"\nResult: {confidence_result.severity.upper()}")
    print(f"Passed: {confidence_result.passed}")
    print(f"Message: {confidence_result.message}")
    
    # Example 3: Check operation limits using integrated diagnostics
    print("\n" + "="*70)
    print("Example 3: Operation Limits (Integrated)")
    print("="*70 + "\n")

    print("Checking limits with safe values...")
    limit_result = agent.diagnostics.check_loop_limits(
        tool_calls=10,
        revisions=2,
        tokens_used=5000,
        files_accessed=5,
        loop_iterations=1
    )
    print(f"\nResult: {limit_result.severity.upper()}")
    print(f"Passed: {limit_result.passed}")
    print(f"Message: {limit_result.message}")

    print("\nChecking limits with exceeded values...")
    limit_result = agent.diagnostics.check_loop_limits(
        tool_calls=60,  # Exceeds max_tool_calls=50
        revisions=2,
        tokens_used=5000,
        files_accessed=5,
        loop_iterations=1
    )
    print(f"\nResult: {limit_result.severity.upper()}")
    print(f"Passed: {limit_result.passed}")
    print(f"Message: {limit_result.message}")
    
    # Example 4: Comprehensive task review using integrated diagnostics
    print("\n" + "="*70)
    print("Example 4: Comprehensive Task Review (Integrated)")
    print("="*70 + "\n")

    # Simulate task files and metrics
    task_files = [
        "services/core/fingerprint.py",
        "services/core/drift_detection.py",
    ]

    task_metrics = OperationMetrics()
    task_metrics.tool_calls = 5
    task_metrics.revisions = 1
    task_metrics.tokens_used = 2000
    task_metrics.loop_iterations = 0
    task_metrics.files_accessed = set(task_files)

    print("Reviewing task before execution...")
    print(f"Files: {task_files}")
    print(f"Mode: IMPLEMENT")

    # Run comprehensive review using integrated diagnostics
    results = agent.diagnostics.review_task(
        files=task_files,
        metrics=task_metrics,
        mode="IMPLEMENT"
    )

    print(f"\n📊 Diagnostic Results:")
    print(f"   Total Checks: {len(results)}")

    critical_count = sum(1 for r in results if r.severity in ("critical", "error") and not r.passed)
    warning_count = sum(1 for r in results if r.severity == "warning")
    passed_count = sum(1 for r in results if r.passed)

    print(f"   Passed: {passed_count}")
    print(f"   Warnings: {warning_count}")
    print(f"   Critical/Errors: {critical_count}")
    print(f"   Has Critical Issues: {agent.diagnostics.has_critical_issues(results)}")
    
    # Example 5: View diagnostic history
    print("\n" + "="*70)
    print("Example 5: Diagnostic History")
    print("="*70 + "\n")

    history = agent.diagnostics.diagnostic_history
    print(f"📈 Diagnostic History:")
    print(f"   Total Checks: {len(history)}")

    if history:
        passed = sum(1 for r in history if r.passed)
        critical = sum(1 for r in history if r.severity in ("critical", "error") and not r.passed)
        warnings = sum(1 for r in history if r.severity == "warning")

        print(f"   Passed: {passed} ({passed/len(history)*100:.1f}%)")
        print(f"   Critical/Errors: {critical}")
        print(f"   Warnings: {warnings}")

        print(f"\n   Recent Checks:")
        for r in history[-5:]:
            status = "✅" if r.passed else "❌"
            print(f"      {status} [{r.severity.upper()}] {r.message}")

    print("\n" + "="*70)
    print("✅ Integrated Diagnostic System example completed!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()

