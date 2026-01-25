"""
CLI Agent for Multi-Mode Agent Interaction.

Provides a command-line interface to interact with multi-mode agents.
All safety checks are handled by the integrated InternalDiagnosticAgent
within MultiModeAgent.

Copyright (c) 2025 ContextForge
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .local_multi_mode_agent import LocalMultiModeAgent
from .multi_mode_agent import AgentMode, DiagnosticResult

logger = logging.getLogger(__name__)


class CLIAgent:
    """
    CLI Agent for interactive multi-mode agent operations.

    Responsibilities:
    - Interactive command-line interface
    - Command parsing and validation
    - Task execution through LocalMultiModeAgent
    - Diagnostic reporting via integrated InternalDiagnosticAgent

    Design:
    - All safety checks handled by MultiModeAgent's integrated diagnostics
    - No separate diagnostic agent - uses MultiModeAgent.diagnostics
    - Human-readable output with emoji indicators
    - Command history and help system

    Supported Commands:
    - plan: Decompose task into steps (PLAN mode)
    - edit: Make code changes (IMPLEMENT mode)
    - review: Analyze code (REVIEW mode)
    - index: Build embeddings (INDEX mode)
    - test: Run tests (TEST mode)
    - diagnose: Run diagnostic checks via integrated diagnostics
    - exit: Exit CLI
    """

    def __init__(
        self,
        workspace_root: Optional[str] = None,
        multi_mode_agent: Optional[LocalMultiModeAgent] = None,
    ):
        """
        Initialize CLI agent.

        Args:
            workspace_root: Root directory for operations
            multi_mode_agent: Optional multi-mode agent instance
        """
        self.workspace_root = workspace_root or str(Path.cwd())

        # Initialize multi-mode agent (with integrated diagnostics)
        self.agent = multi_mode_agent or LocalMultiModeAgent(
            name="cli-agent",
            workspace_root=self.workspace_root
        )
        
        # Command history
        self.command_history: List[str] = []
        self.running = False
        
        # Command mapping
        self.commands = {
            "plan": self._cmd_plan,
            "edit": self._cmd_edit,
            "review": self._cmd_review,
            "index": self._cmd_index,
            "test": self._cmd_test,
            "diagnose": self._cmd_diagnose,
            "help": self._cmd_help,
            "exit": self._cmd_exit,
            "quit": self._cmd_exit,
        }
    
    def run(self) -> None:
        """
        Start interactive CLI loop.
        
        Workflow:
        1. Display welcome message
        2. Read user input
        3. Parse and validate command
        4. Execute command with diagnostic checks
        5. Display results
        6. Repeat until exit
        """
        self.running = True
        
        print("\n" + "="*70)
        print("  ContextForge CLI Agent - Multi-Mode Agent Interface")
        print("="*70)
        print("\nType 'help' for available commands, 'exit' to quit.\n")
        
        while self.running:
            try:
                # Read command
                command_line = input("contextforge> ").strip()
                
                if not command_line:
                    continue
                
                # Add to history
                self.command_history.append(command_line)
                
                # Parse command
                parts = command_line.split(maxsplit=1)
                command = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""
                
                # Execute command
                if command in self.commands:
                    self.commands[command](args)
                else:
                    print(f"❌ Unknown command: {command}")
                    print("   Type 'help' for available commands.")
                
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted. Type 'exit' to quit.")
            except EOFError:
                print("\n")
                break
            except Exception as e:
                logger.error(f"CLI error: {e}", exc_info=True)
                print(f"❌ Error: {e}")
        
        print("\n👋 Goodbye!\n")

    def run_agent_task(
        self,
        command: str,
        task_payload: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Execute agent task with integrated diagnostic checks.

        Args:
            command: Command name (plan, edit, review, index, test)
            task_payload: Task payload for agent

        Returns:
            Task result or None if failed

        Safety Workflow:
        1. MultiModeAgent runs integrated diagnostic checks automatically
        2. Execute task (diagnostics run internally)
        3. Display results and diagnostic history
        """
        # Map command to agent mode
        mode_map = {
            "plan": AgentMode.PLAN,
            "edit": AgentMode.IMPLEMENT,
            "review": AgentMode.REVIEW,
            "index": AgentMode.INDEX,
            "test": AgentMode.TEST,
        }

        agent_mode = mode_map.get(command)
        if not agent_mode:
            print(f"❌ Invalid command: {command}")
            return None

        print(f"\n🔍 Executing {command} task with integrated safety checks...")

        # Execute task (diagnostics run automatically inside MultiModeAgent)
        try:
            result = self.agent.execute(
                mode=agent_mode,
                task=task_payload
            )

            # Display diagnostic history from integrated diagnostics
            recent_diagnostics = self.agent.diagnostics.diagnostic_history[-10:]
            if recent_diagnostics:
                print(f"\n📊 Diagnostic Checks ({len(recent_diagnostics)} recent):")
                self._display_diagnostic_results(recent_diagnostics)

            print(f"\n✅ Task completed successfully!")
            return result

        except Exception as e:
            logger.error(f"Task execution failed: {e}", exc_info=True)
            print(f"\n❌ Task execution failed: {e}")

            # Show diagnostic history for debugging
            recent_diagnostics = self.agent.diagnostics.diagnostic_history[-5:]
            if recent_diagnostics:
                print(f"\n📊 Recent Diagnostic Checks:")
                self._display_diagnostic_results(recent_diagnostics)

            return None

    def run_diagnostic(self, files: Optional[List[str]] = None) -> List[DiagnosticResult]:
        """
        Run diagnostic checks on specified files using integrated diagnostics.

        Args:
            files: Optional list of files to check (default: all tracked files)

        Returns:
            List of diagnostic results
        """
        if not files:
            # Get all tracked files from agent's drift detector
            files = list(self.agent.drift_detector.fingerprints.keys())

        if not files:
            print("⚠️  No files to diagnose. Register files first.")
            return []

        print(f"\n🔍 Running diagnostics on {len(files)} file(s)...")

        # Run diagnostic review using integrated diagnostics
        results = self.agent.diagnostics.review_task(
            files=files,
            metrics=self.agent.metrics,
            mode="diagnostic"
        )

        # Display results
        self._display_diagnostic_results(results)

        # Display summary
        self._display_diagnostic_summary()

        return results

    def _display_diagnostic_results(self, results: List[DiagnosticResult]) -> None:
        """Display diagnostic results in human-readable format."""
        if not results:
            return

        print(f"\n{'='*70}")
        print(f"  Diagnostic Results ({len(results)} checks)")
        print(f"{'='*70}\n")

        # Group results by severity
        critical = [r for r in results if r.severity == "critical"]
        errors = [r for r in results if r.severity == "error"]
        warnings = [r for r in results if r.severity == "warning"]
        info = [r for r in results if r.severity == "info"]

        if critical:
            print(f"🚨 CRITICAL ({len(critical)}):")
            for r in critical:
                print(f"   • {r.message}")

        if errors:
            print(f"\n❌ ERRORS ({len(errors)}):")
            for r in errors:
                print(f"   • {r.message}")

        if warnings:
            print(f"\n⚠️  WARNINGS ({len(warnings)}):")
            for r in warnings:
                print(f"   • {r.message}")

        if info and not (critical or errors or warnings):
            print(f"✅ All checks passed ({len(info)} checks)")

        print(f"\n{'='*70}\n")

    def _display_diagnostic_summary(self) -> None:
        """Display summary of all diagnostic checks."""
        history = self.agent.diagnostics.diagnostic_history

        if not history:
            print("📊 No diagnostic history available")
            return

        total = len(history)
        passed = sum(1 for r in history if r.passed)
        critical = sum(1 for r in history if r.severity in ("critical", "error") and not r.passed)
        warnings = sum(1 for r in history if r.severity == "warning")

        print(f"📊 Diagnostic Summary:")
        print(f"   Total Checks: {total}")
        print(f"   Passed: {passed} ({passed/total*100:.1f}%)")
        print(f"   Critical/Errors: {critical}")
        print(f"   Warnings: {warnings}")

    def _format_status(self, status: str) -> str:
        """Format status with emoji."""
        status_map = {
            "passed": "✅ PASSED",
            "warning": "⚠️  WARNING",
            "failed": "❌ FAILED",
            "pending": "⏳ PENDING",
        }
        return status_map.get(status, status.upper())

    # Command implementations

    def _cmd_plan(self, args: str) -> None:
        """Execute PLAN mode: decompose task into steps."""
        if not args:
            print("❌ Usage: plan <task_description>")
            print("   Example: plan Refactor authentication module")
            return

        task_payload = {
            "description": args,
            "mode": "plan",
            "files": [],
            "metrics": {"tool_calls": 0, "revisions": 0, "tokens_used": 0, "loop_iterations": 0}
        }

        result = self.run_agent_task("plan", task_payload)
        if result:
            print(f"\n📋 Plan Result:")
            print(f"{result}")

    def _cmd_edit(self, args: str) -> None:
        """Execute IMPLEMENT mode: make code changes."""
        if not args:
            print("❌ Usage: edit <file_path> <description>")
            print("   Example: edit src/auth.py Add password validation")
            return

        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            print("❌ Please provide both file path and description")
            return

        file_path, description = parts

        task_payload = {
            "file_path": file_path,
            "description": description,
            "mode": "implement",
            "files": [file_path],
            "metrics": {"tool_calls": 0, "revisions": 0, "tokens_used": 0, "loop_iterations": 0}
        }

        result = self.run_agent_task("edit", task_payload)
        if result:
            print(f"\n✏️  Edit Result:")
            print(f"{result}")

    def _cmd_review(self, args: str) -> None:
        """Execute REVIEW mode: analyze code."""
        if not args:
            print("❌ Usage: review <file_path>")
            print("   Example: review src/auth.py")
            return

        file_path = args.strip()

        task_payload = {
            "file_path": file_path,
            "mode": "review",
            "files": [file_path],
            "metrics": {"tool_calls": 0, "revisions": 0, "tokens_used": 0, "loop_iterations": 0}
        }

        result = self.run_agent_task("review", task_payload)
        if result:
            print(f"\n🔍 Review Result:")
            print(f"{result}")

    def _cmd_index(self, args: str) -> None:
        """Execute INDEX mode: build embeddings."""
        files = args.split() if args else []

        task_payload = {
            "files": files,
            "mode": "index",
            "metrics": {"tool_calls": 0, "revisions": 0, "tokens_used": 0, "loop_iterations": 0}
        }

        result = self.run_agent_task("index", task_payload)
        if result:
            print(f"\n📚 Index Result:")
            print(f"{result}")

    def _cmd_test(self, args: str) -> None:
        """Execute TEST mode: run tests."""
        test_files = args.split() if args else []

        task_payload = {
            "test_files": test_files,
            "mode": "test",
            "files": test_files,
            "metrics": {"tool_calls": 0, "revisions": 0, "tokens_used": 0, "loop_iterations": 0}
        }

        result = self.run_agent_task("test", task_payload)
        if result:
            print(f"\n🧪 Test Result:")
            print(f"{result}")

    def _cmd_diagnose(self, args: str) -> None:
        """Run diagnostic checks using integrated diagnostics."""
        files = args.split() if args else None

        results = self.run_diagnostic(files)

    def _cmd_help(self, args: str) -> None:
        """Display help information."""
        print("\n" + "="*70)
        print("  Available Commands")
        print("="*70)
        print("\n  📋 plan <task_description>")
        print("     Decompose task into steps (PLAN mode)")
        print("\n  ✏️  edit <file_path> <description>")
        print("     Make code changes (IMPLEMENT mode)")
        print("\n  🔍 review <file_path>")
        print("     Analyze code (REVIEW mode)")
        print("\n  📚 index [file1 file2 ...]")
        print("     Build embeddings (INDEX mode)")
        print("\n  🧪 test [test_file1 test_file2 ...]")
        print("     Run tests (TEST mode)")
        print("\n  🔬 diagnose [file1 file2 ...]")
        print("     Run diagnostic checks on files")
        print("\n  ❓ help")
        print("     Show this help message")
        print("\n  🚪 exit / quit")
        print("     Exit CLI")
        print("\n" + "="*70 + "\n")

    def _cmd_exit(self, args: str) -> None:
        """Exit CLI."""
        self.running = False

