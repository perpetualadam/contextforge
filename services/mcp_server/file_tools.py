"""
ContextForge MCP File Tools - File and code manipulation tools for MCP.

This module exposes the file editing, viewing, and process management
tools through the MCP protocol.

Copyright (c) 2025 ContextForge
"""

import os
import logging
from typing import Optional, List, Dict, Any, Tuple

from mcp.server.fastmcp import FastMCP

from services.tools import (
    FileEditor,
    StrReplaceRequest,
    StrReplaceEntry,
    SaveFileRequest,
    RemoveFilesRequest,
    EditResultStatus,
    CodeViewer,
    ViewRequest,
    ViewResultStatus,
    ProcessManager,
    LaunchProcessRequest,
    ProcessState,
    # Git Commit Retrieval
    GitCommitRetrieval,
    GitRetrievalRequest,
    GitRetrievalStatus,
    # Task List Manager
    TaskListManager,
    Task,
    TaskState,
    ReorganizeRequest
)

logger = logging.getLogger(__name__)

# Get workspace root from environment or use current directory
WORKSPACE_ROOT = os.getenv("CONTEXTFORGE_WORKSPACE", os.getcwd())


def register_file_tools(mcp: FastMCP) -> None:
    """Register file and code manipulation tools with the MCP server."""

    # Initialize tool instances
    file_editor = FileEditor(workspace_root=WORKSPACE_ROOT)
    code_viewer = CodeViewer(workspace_root=WORKSPACE_ROOT)
    process_manager = ProcessManager(workspace_root=WORKSPACE_ROOT)
    git_retrieval = GitCommitRetrieval(workspace_root=WORKSPACE_ROOT)
    tasklist_manager = TaskListManager()
    
    # ============== File Editing Tools ==============
    
    @mcp.tool()
    async def str_replace_editor(
        path: str,
        replacements: List[Dict[str, Any]]
    ) -> str:
        """
        Edit a file by replacing specific strings with new content.
        
        Use this tool to make precise edits to existing files. Each replacement
        must match exactly one location in the file.
        
        Args:
            path: Path to the file to edit (relative to workspace)
            replacements: List of replacement entries, each with:
                - old_str: The exact string to find and replace
                - new_str: The replacement string
                - start_line: (optional) Line number hint for disambiguation
                - end_line: (optional) End line number hint
        
        Returns:
            Status message with snippet of the edited content
        """
        try:
            entries = []
            for i, r in enumerate(replacements):
                entries.append(StrReplaceEntry(
                    old_str=r.get("old_str", ""),
                    new_str=r.get("new_str", ""),
                    start_line=r.get("start_line"),
                    end_line=r.get("end_line")
                ))
            
            request = StrReplaceRequest(path=path, entries=entries)
            result = file_editor.str_replace(request)
            
            if result.status == EditResultStatus.SUCCESS:
                snippet = result.content[:500] if result.content else ""
                return f"✓ Successfully edited {path}\n\n```\n{snippet}\n```"
            else:
                return f"✗ Edit failed: {result.message}"
                
        except Exception as e:
            logger.error(f"str_replace_editor error: {e}")
            return f"✗ Error: {str(e)}"
    
    @mcp.tool()
    async def save_file(
        path: str,
        content: str,
        overwrite: bool = False
    ) -> str:
        """
        Create a new file with the specified content.
        
        Use this tool to create new files. By default, it will not overwrite
        existing files - use the str_replace_editor for editing existing files.
        
        Args:
            path: Path for the new file (relative to workspace)
            content: The content to write to the file
            overwrite: Whether to overwrite if file exists (default: False)
        
        Returns:
            Status message confirming file creation
        """
        try:
            request = SaveFileRequest(
                path=path,
                content=content,
                overwrite=overwrite
            )
            result = file_editor.save_file(request)
            
            if result.status == EditResultStatus.SUCCESS:
                return f"✓ File saved: {path}"
            else:
                return f"✗ Save failed: {result.message}"
                
        except Exception as e:
            logger.error(f"save_file error: {e}")
            return f"✗ Error: {str(e)}"
    
    @mcp.tool()
    async def remove_files(
        paths: List[str],
        create_backup: bool = True,
        allow_directories: bool = False,
        dry_run: bool = False,
        force: bool = False
    ) -> str:
        """
        Remove one or more files.

        This tool safely removes files with optional backup creation.
        Changes can be undone if backups are enabled.

        Protected files (.git, .gitignore, .env, etc.) are blocked by default.
        Use force=True to override protection (use with caution).

        Args:
            paths: List of file paths to remove (relative to workspace)
            create_backup: Whether to create backups before removal (default: True)
            allow_directories: Allow removing directories recursively (default: False)
            dry_run: Preview what would be removed without actually removing (default: False)
            force: Override protection for protected files (default: False)

        Returns:
            Status message for each file removal
        """
        try:
            request = RemoveFilesRequest(
                paths=paths,
                create_backup=create_backup,
                allow_directories=allow_directories,
                dry_run=dry_run,
                force=force
            )
            results = file_editor.remove_files(request)

            output = []
            for r in results:
                if r.status == EditResultStatus.SUCCESS:
                    if dry_run:
                        output.append(f"⚠ Would remove: {r.path}")
                    else:
                        output.append(f"✓ Removed: {r.path}")
                        if r.backup_path:
                            output.append(f"  Backup: {r.backup_path}")
                elif r.status == EditResultStatus.VALIDATION_ERROR:
                    output.append(f"⛔ Protected: {r.path} - {r.message}")
                else:
                    output.append(f"✗ Failed: {r.path} - {r.message}")

            return "\n".join(output)

        except Exception as e:
            logger.error(f"remove_files error: {e}")
            return f"✗ Error: {str(e)}"

    # ============== Code Viewing Tools ==============

    @mcp.tool()
    async def view(
        path: str,
        view_type: str = "file",
        view_range: Optional[Tuple[int, int]] = None,
        search_query_regex: Optional[str] = None,
        case_sensitive: bool = False,
        context_lines_before: int = 5,
        context_lines_after: int = 5
    ) -> str:
        """
        View file or directory contents.

        For files: displays content with line numbers. Can view specific line
        ranges or search with regex patterns.

        For directories: lists files and subdirectories up to 2 levels deep.

        Args:
            path: Path to file or directory (relative to workspace)
            view_type: "file" or "directory"
            view_range: Optional (start_line, end_line) tuple for files
            search_query_regex: Optional regex pattern to search for
            case_sensitive: Whether regex search is case-sensitive
            context_lines_before: Lines of context before regex matches
            context_lines_after: Lines of context after regex matches

        Returns:
            File content with line numbers, or directory listing
        """
        try:
            request = ViewRequest(
                path=path,
                view_type=view_type,
                view_range=view_range,
                search_query_regex=search_query_regex,
                case_sensitive=case_sensitive,
                context_lines_before=context_lines_before,
                context_lines_after=context_lines_after
            )

            result = code_viewer.view(request)

            if result.status == ViewResultStatus.SUCCESS:
                header = f"📄 {path}"
                if result.total_lines:
                    header += f" ({result.total_lines} lines)"
                if result.is_truncated:
                    header += " [truncated]"
                return f"{header}\n\n{result.content}"
            else:
                return f"✗ View failed: {result.message}"

        except Exception as e:
            logger.error(f"view error: {e}")
            return f"✗ Error: {str(e)}"

    # ============== Process Management Tools ==============

    @mcp.tool()
    async def launch_process(
        command: str,
        cwd: str,
        wait: bool = True,
        max_wait_seconds: float = 600
    ) -> str:
        """
        Launch a new process.

        Use wait=True for short commands that should complete before proceeding.
        Use wait=False for background processes like servers.

        Args:
            command: The shell command to execute
            cwd: Working directory (absolute path required)
            wait: Whether to wait for completion (default: True)
            max_wait_seconds: Timeout for waiting processes (default: 600)

        Returns:
            Process output and status, or terminal ID for background processes
        """
        try:
            request = LaunchProcessRequest(
                command=command,
                cwd=cwd,
                wait=wait,
                max_wait_seconds=max_wait_seconds
            )

            result = process_manager.launch_process(request)

            output = f"Terminal ID: {result.terminal_id}\n"
            output += f"Status: {result.state.value if result.state else 'unknown'}\n"

            if result.return_code is not None:
                output += f"Return Code: {result.return_code}\n"

            if result.output:
                output += f"\n--- Output ---\n{result.output}"

            if not result.success:
                output = f"✗ {result.message}\n" + output

            return output

        except Exception as e:
            logger.error(f"launch_process error: {e}")
            return f"✗ Error: {str(e)}"

    @mcp.tool()
    async def read_process(
        terminal_id: int,
        wait: bool = False,
        max_wait_seconds: float = 60
    ) -> str:
        """
        Read output from a running or completed process.

        Args:
            terminal_id: The terminal ID returned by launch_process
            wait: Whether to wait for process completion
            max_wait_seconds: Maximum time to wait

        Returns:
            Process output and current status
        """
        try:
            result = process_manager.read_process(
                terminal_id=terminal_id,
                wait=wait,
                max_wait_seconds=max_wait_seconds
            )

            if not result.success:
                return f"✗ {result.message}"

            output = f"Terminal ID: {terminal_id}\n"
            output += f"Status: {result.state.value if result.state else 'unknown'}\n"

            if result.return_code is not None:
                output += f"Return Code: {result.return_code}\n"

            output += f"\n--- Output ---\n{result.output}"
            return output

        except Exception as e:
            logger.error(f"read_process error: {e}")
            return f"✗ Error: {str(e)}"

    @mcp.tool()
    async def write_process(
        terminal_id: int,
        input_text: str
    ) -> str:
        """
        Write input to a running process.

        Args:
            terminal_id: The terminal ID to write to
            input_text: Text to send to the process stdin

        Returns:
            Status message
        """
        try:
            result = process_manager.write_process(terminal_id, input_text)

            if result.success:
                return f"✓ Wrote {len(input_text)} characters to terminal {terminal_id}"
            else:
                return f"✗ {result.message}"

        except Exception as e:
            logger.error(f"write_process error: {e}")
            return f"✗ Error: {str(e)}"

    @mcp.tool()
    async def kill_process(terminal_id: int) -> str:
        """
        Kill a running process.

        Args:
            terminal_id: The terminal ID to kill

        Returns:
            Status message
        """
        try:
            result = process_manager.kill_process(terminal_id)

            if result.success:
                return f"✓ Process {terminal_id} killed"
            else:
                return f"✗ {result.message}"

        except Exception as e:
            logger.error(f"kill_process error: {e}")
            return f"✗ Error: {str(e)}"

    @mcp.tool()
    async def list_processes() -> str:
        """
        List all managed processes and their states.

        Returns:
            Table of all processes with their status
        """
        try:
            processes = process_manager.list_processes()

            if not processes:
                return "No processes currently managed."

            output = "| Terminal ID | Command | State | Return Code |\n"
            output += "|-------------|---------|-------|-------------|\n"

            for p in processes:
                cmd = p.command[:30] + "..." if len(p.command) > 30 else p.command
                rc = str(p.return_code) if p.return_code is not None else "-"
                output += f"| {p.terminal_id} | {cmd} | {p.state.value} | {rc} |\n"

            return output

        except Exception as e:
            logger.error(f"list_processes error: {e}")
            return f"✗ Error: {str(e)}"

    # ============== Git Commit Retrieval Tools ==============

    @mcp.tool()
    async def git_commit_retrieval(
        query: str,
        repo_path: str = ".",
        max_results: int = 10,
        author: Optional[str] = None,
        date_after: Optional[str] = None,
        date_before: Optional[str] = None,
        include_diffs: bool = False
    ) -> str:
        """
        Search git commit history using natural language queries.

        This tool searches commit messages, subjects, and authors to find
        relevant commits based on your query. Results are ranked by relevance.

        Args:
            query: Natural language search query (e.g., "fix authentication bug")
            repo_path: Path to the git repository (default: current workspace)
            max_results: Maximum number of commits to return (default: 10)
            author: Filter by author name (optional)
            date_after: Filter commits after this date (YYYY-MM-DD)
            date_before: Filter commits before this date (YYYY-MM-DD)
            include_diffs: Include diff previews in results (default: False)

        Returns:
            Formatted list of matching commits with details
        """
        try:
            request = GitRetrievalRequest(
                query=query,
                repo_path=repo_path,
                max_results=max_results,
                author=author,
                date_after=date_after,
                date_before=date_before,
                include_diffs=include_diffs
            )

            result = git_retrieval.search(request)

            if result.status == GitRetrievalStatus.NOT_A_REPOSITORY:
                return f"✗ Not a git repository: {repo_path}"
            elif result.status == GitRetrievalStatus.NO_COMMITS:
                return "✗ Repository has no commits"
            elif result.status == GitRetrievalStatus.NO_MATCHES:
                return f"No commits found matching: {query}"
            elif result.status != GitRetrievalStatus.SUCCESS:
                return f"✗ Error: {result.message}"

            output = f"**Found {len(result.commits)} commits matching '{query}'**\n\n"

            for commit in result.commits:
                output += f"### {commit.short_hash}: {commit.subject}\n"
                output += f"- **Author:** {commit.author}\n"
                output += f"- **Date:** {commit.date}\n"
                output += f"- **Files:** {len(commit.files_changed)} changed "
                output += f"(+{commit.insertions}/-{commit.deletions})\n"

                if commit.message and commit.message != commit.subject:
                    output += f"- **Message:** {commit.message[:200]}...\n"

                if commit.diff_preview:
                    output += f"\n```diff\n{commit.diff_preview[:500]}\n```\n"

                output += "\n"

            return output

        except Exception as e:
            logger.error(f"git_commit_retrieval error: {e}")
            return f"✗ Error: {str(e)}"

    @mcp.tool()
    async def git_show_commit(
        commit_hash: str,
        repo_path: str = "."
    ) -> str:
        """
        Get detailed information about a specific git commit.

        Args:
            commit_hash: Full or short commit hash
            repo_path: Path to the git repository

        Returns:
            Detailed commit information including diff
        """
        try:
            commit = git_retrieval.get_commit(commit_hash, repo_path)

            if not commit:
                return f"✗ Commit not found: {commit_hash}"

            output = f"## Commit {commit.short_hash}\n\n"
            output += f"**Subject:** {commit.subject}\n"
            output += f"**Author:** {commit.author} <{commit.author_email}>\n"
            output += f"**Date:** {commit.date}\n\n"

            if commit.message:
                output += f"**Message:**\n{commit.message}\n\n"

            output += f"**Stats:** {len(commit.files_changed)} files changed, "
            output += f"+{commit.insertions}/-{commit.deletions}\n\n"

            if commit.files_changed:
                output += "**Files:**\n"
                for f in commit.files_changed[:20]:
                    output += f"- {f}\n"
                if len(commit.files_changed) > 20:
                    output += f"- ... and {len(commit.files_changed) - 20} more\n"

            if commit.diff_preview:
                output += f"\n**Diff Preview:**\n```diff\n{commit.diff_preview}\n```"

            return output

        except Exception as e:
            logger.error(f"git_show_commit error: {e}")
            return f"✗ Error: {str(e)}"

    # ============== Task List Manager Tools ==============

    @mcp.tool()
    async def view_tasklist() -> str:
        """
        View the current task list in markdown format.

        Shows all tasks in a hierarchical structure with their current states:
        - [ ] Not started
        - [/] In progress
        - [x] Complete
        - [-] Cancelled

        Returns:
            Markdown formatted task list
        """
        try:
            return tasklist_manager.to_markdown()
        except Exception as e:
            logger.error(f"view_tasklist error: {e}")
            return f"✗ Error: {str(e)}"

    @mcp.tool()
    async def add_tasks(
        tasks: List[Dict[str, Any]]
    ) -> str:
        """
        Add one or more new tasks to the task list.

        Args:
            tasks: List of task definitions, each with:
                - name: Task name (required)
                - description: Task description (optional)
                - parent_task_id: UUID of parent task for subtasks (optional)
                - state: Initial state - NOT_STARTED, IN_PROGRESS, COMPLETE, CANCELLED (default: NOT_STARTED)

        Returns:
            Confirmation with task IDs
        """
        try:
            created = []
            for task_def in tasks:
                state = TaskState[task_def.get("state", "NOT_STARTED")]
                task = tasklist_manager.add_task(
                    name=task_def["name"],
                    description=task_def.get("description", ""),
                    parent_id=task_def.get("parent_task_id"),
                    state=state
                )
                created.append(task)

            output = f"✓ Created {len(created)} task(s):\n\n"
            for task in created:
                output += f"- **{task.name}** (ID: `{task.id}`)\n"

            return output

        except Exception as e:
            logger.error(f"add_tasks error: {e}")
            return f"✗ Error: {str(e)}"

    @mcp.tool()
    async def update_tasks(
        tasks: List[Dict[str, Any]]
    ) -> str:
        """
        Update one or more existing tasks.

        Args:
            tasks: List of task updates, each with:
                - task_id: UUID of the task to update (required)
                - name: New task name (optional)
                - description: New description (optional)
                - state: New state - NOT_STARTED, IN_PROGRESS, COMPLETE, CANCELLED (optional)

        Returns:
            Confirmation of updates
        """
        try:
            updated = []
            for task_def in tasks:
                task_id = task_def["task_id"]

                state = None
                if "state" in task_def:
                    state = TaskState[task_def["state"]]

                result = tasklist_manager.update_task(
                    task_id=task_id,
                    name=task_def.get("name"),
                    description=task_def.get("description"),
                    state=state
                )
                if result:
                    updated.append(result)

            if not updated:
                return "✗ No tasks were updated (task IDs may not exist)"

            output = f"✓ Updated {len(updated)} task(s):\n\n"
            for task in updated:
                state_symbol = {
                    TaskState.NOT_STARTED: "[ ]",
                    TaskState.IN_PROGRESS: "[/]",
                    TaskState.COMPLETE: "[x]",
                    TaskState.CANCELLED: "[-]"
                }.get(task.state, "[ ]")
                output += f"- {state_symbol} **{task.name}**\n"

            return output

        except Exception as e:
            logger.error(f"update_tasks error: {e}")
            return f"✗ Error: {str(e)}"

    @mcp.tool()
    async def reorganize_tasklist(
        markdown: str,
        validate_only: bool = False
    ) -> str:
        """
        Reorganize the task list structure from markdown.

        Use this for major restructuring like reordering tasks or changing hierarchy.
        The markdown format should be:

        - [ ] Task name (ID: uuid or NEW_UUID) - Description
          - [/] Subtask name (ID: uuid)

        Args:
            markdown: The markdown representation of the new task list structure
            validate_only: If True, only validate the markdown without applying changes

        Returns:
            Confirmation or validation result
        """
        try:
            request = ReorganizeRequest(
                markdown=markdown,
                validate_only=validate_only
            )

            result = tasklist_manager.reorganize(request)

            if not result.success:
                return f"✗ Reorganization failed:\n" + "\n".join(f"- {e}" for e in result.errors)

            if validate_only:
                return f"✓ Markdown is valid\n\n{tasklist_manager.to_markdown()}"

            return f"✓ Task list reorganized:\n\n{tasklist_manager.to_markdown()}"

        except Exception as e:
            logger.error(f"reorganize_tasklist error: {e}")
            return f"✗ Error: {str(e)}"

    @mcp.tool()
    async def undo_task_operation() -> str:
        """
        Undo the last task list operation.

        Returns:
            Confirmation and current task list state
        """
        try:
            if tasklist_manager.undo():
                return f"✓ Undone. Current state:\n\n{tasklist_manager.to_markdown()}"
            else:
                return "✗ Nothing to undo"
        except Exception as e:
            logger.error(f"undo_task_operation error: {e}")
            return f"✗ Error: {str(e)}"

    @mcp.tool()
    async def redo_task_operation() -> str:
        """
        Redo a previously undone task operation.

        Returns:
            Confirmation and current task list state
        """
        try:
            if tasklist_manager.redo():
                return f"✓ Redone. Current state:\n\n{tasklist_manager.to_markdown()}"
            else:
                return "✗ Nothing to redo"
        except Exception as e:
            logger.error(f"redo_task_operation error: {e}")
            return f"✗ Error: {str(e)}"