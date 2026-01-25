"""
Example usage of CLIAgent with Integrated Diagnostics.

Demonstrates:
- Interactive CLI commands
- Integrated diagnostic checks (no separate diagnostic agent)
- Task execution through multi-mode agent
- Diagnostic logging and reporting

Copyright (c) 2025 ContextForge
"""

import sys
from pathlib import Path

# Add services to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.core.cli_agent import CLIAgent
from services.core.local_multi_mode_agent import LocalMultiModeAgent
from services.core.safety import OperationLimits


def example_programmatic_usage():
    """
    Demonstrate programmatic usage of CLIAgent with integrated diagnostics.

    This shows how to use CLIAgent without interactive mode,
    useful for scripting and automation.
    """

    print("\n" + "="*70)
    print("  CLIAgent Example - Programmatic Usage (Integrated Diagnostics)")
    print("="*70 + "\n")

    # Initialize components
    workspace_root = str(Path(__file__).parent.parent)

    # MultiModeAgent with integrated diagnostics
    multi_mode_agent = LocalMultiModeAgent(
        name="cli-example",
        workspace_root=workspace_root,
        limits=OperationLimits()
    )

    # CLIAgent uses the integrated diagnostics from MultiModeAgent
    cli_agent = CLIAgent(
        workspace_root=workspace_root,
        multi_mode_agent=multi_mode_agent
    )

    print("✅ CLIAgent initialized with integrated diagnostics\n")
    print(f"   Agent: {cli_agent.agent.name}")
    print(f"   Integrated Diagnostics: {cli_agent.agent.diagnostics.__class__.__name__}\n")
    
    # Example 1: Run diagnostic on files
    print("="*70)
    print("Example 1: Run Diagnostic Checks")
    print("="*70 + "\n")
    
    files_to_check = [
        "services/core/fingerprint.py",
        "services/core/drift_detection.py",
    ]
    
    print(f"Running diagnostics on {len(files_to_check)} files...")
    report = cli_agent.run_diagnostic(files_to_check)
    
    print(f"\n✅ Diagnostic completed!")
    print(f"   Operation ID: {report.operation_id}")
    print(f"   Status: {report.overall_status}")
    
    # Example 2: Execute a review task
    print("\n" + "="*70)
    print("Example 2: Execute Review Task")
    print("="*70 + "\n")
    
    review_task = {
        "file_path": "services/core/fingerprint.py",
        "description": "Review fingerprinting implementation",
        "mode": "review",
        "files": ["services/core/fingerprint.py"],
        "metrics": {
            "tool_calls": 0,
            "revisions": 0,
            "tokens_used": 0,
            "loop_iterations": 0,
        }
    }
    
    print("Executing review task with diagnostic checks...")
    result = cli_agent.run_agent_task("review", review_task)
    
    if result:
        print(f"\n✅ Review task completed successfully!")
    else:
        print(f"\n❌ Review task failed or was blocked by diagnostics")
    
    # Example 3: Execute a plan task
    print("\n" + "="*70)
    print("Example 3: Execute Plan Task")
    print("="*70 + "\n")
    
    plan_task = {
        "description": "Add support for TypeScript symbol extraction",
        "mode": "plan",
        "files": [],
        "metrics": {
            "tool_calls": 0,
            "revisions": 0,
            "tokens_used": 0,
            "loop_iterations": 0,
        }
    }
    
    print("Executing plan task with diagnostic checks...")
    result = cli_agent.run_agent_task("plan", plan_task)
    
    if result:
        print(f"\n✅ Plan task completed successfully!")
    else:
        print(f"\n❌ Plan task failed or was blocked by diagnostics")
    
    # Example 4: View diagnostic summary from integrated diagnostics
    print("\n" + "="*70)
    print("Example 4: Diagnostic Summary (Integrated)")
    print("="*70 + "\n")

    # Access diagnostic history from integrated diagnostics
    history = cli_agent.agent.diagnostics.diagnostic_history

    print("📊 Overall Diagnostic Summary:")
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
    print("✅ CLIAgent programmatic example completed!")
    print("="*70 + "\n")


def example_interactive_usage():
    """
    Demonstrate interactive CLI usage.
    
    This starts the interactive CLI loop where users can type commands.
    """
    
    print("\n" + "="*70)
    print("  CLIAgent Example - Interactive Mode")
    print("="*70 + "\n")
    
    print("Starting interactive CLI...")
    print("You can now type commands like:")
    print("  - diagnose services/core/fingerprint.py")
    print("  - review services/core/drift_detection.py")
    print("  - plan Add TypeScript support")
    print("  - help")
    print("  - exit")
    print()
    
    # Initialize CLI agent
    workspace_root = str(Path(__file__).parent.parent)
    cli_agent = CLIAgent(workspace_root=workspace_root)
    
    # Start interactive loop
    cli_agent.run()


def main():
    """Main entry point."""
    
    # Run programmatic example
    example_programmatic_usage()
    
    # Optionally run interactive mode
    print("\n" + "="*70)
    response = input("Would you like to try interactive mode? (y/n): ").strip().lower()
    if response == "y":
        example_interactive_usage()
    else:
        print("\n👋 Example completed!\n")


if __name__ == "__main__":
    main()

