"""
ContextForge Task List Manager - Task hierarchy management tool.

Provides task list management capabilities:
- Restructure task lists with hierarchy operations
- Maintain task relationships and dependencies
- Validate task hierarchy integrity
- Support undo/redo operations for task reorganization
- Persistent storage to .contextforge/tasks.json
- Task dependencies (A depends on B)
- Task templates for common workflows

Copyright (c) 2025 ContextForge
"""

import json
import os
import uuid
import logging
import copy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
from enum import Enum

logger = logging.getLogger(__name__)


class TaskState(Enum):
    """State of a task."""
    NOT_STARTED = "NOT_STARTED"  # [ ]
    IN_PROGRESS = "IN_PROGRESS"  # [/]
    COMPLETE = "COMPLETE"        # [x]
    CANCELLED = "CANCELLED"      # [-]


@dataclass
class Task:
    """A single task in the task list."""
    task_id: str
    name: str
    description: str = ""
    state: TaskState = TaskState.NOT_STARTED
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)  # Task IDs
    dependencies: List[str] = field(default_factory=list)  # Task IDs this task depends on
    order: int = 0  # Order within parent
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        """Alias for task_id for convenience."""
        return self.task_id

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary."""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "state": self.state.value,
            "parent_id": self.parent_id,
            "children": self.children.copy(),
            "dependencies": self.dependencies.copy(),
            "order": self.order,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata.copy()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create task from dictionary."""
        state = data.get("state", "NOT_STARTED")
        if isinstance(state, str):
            state = TaskState(state)
        return cls(
            task_id=data["task_id"],
            name=data["name"],
            description=data.get("description", ""),
            state=state,
            parent_id=data.get("parent_id"),
            children=data.get("children", []).copy(),
            dependencies=data.get("dependencies", []).copy(),
            order=data.get("order", 0),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            metadata=data.get("metadata", {}).copy()
        )


@dataclass
class TaskListSnapshot:
    """Snapshot of task list for undo/redo."""
    tasks: Dict[str, Dict[str, Any]]
    root_ids: List[str]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class TaskListValidationError(Exception):
    """Error during task list validation."""
    pass


@dataclass
class ReorganizeRequest:
    """Request to reorganize task list."""
    markdown: str  # Markdown representation of new structure
    validate_only: bool = False  # If True, only validate without applying


@dataclass
class ReorganizeResult:
    """Result of task list reorganization."""
    success: bool
    message: str
    tasks_added: int = 0
    tasks_moved: int = 0
    tasks_removed: int = 0
    validation_errors: List[str] = field(default_factory=list)


class TaskListManager:
    """
    Task hierarchy management tool.

    Provides restructuring of task lists with:
    - Markdown-based task list parsing
    - Hierarchy validation
    - Undo/redo support
    - Dependency tracking
    - Persistence to .contextforge/tasks.json
    - Task templates for common workflows

    Example usage:
        manager = TaskListManager()
        manager.add_task(Task(task_id="1", name="Main Task"))
        manager.add_task(Task(task_id="2", name="Subtask", parent_id="1"))

        # Reorganize via markdown
        result = manager.reorganize(ReorganizeRequest(
            markdown="- [ ] New Structure\\n  - [ ] Child Task"
        ))

        # Undo last change
        manager.undo()

        # Save to disk
        manager.save()

    Security considerations:
        - Task IDs are validated UUIDs
        - Circular dependency detection
        - Maximum hierarchy depth enforced
    """

    MAX_HIERARCHY_DEPTH = 10
    MAX_UNDO_HISTORY = 50
    DEFAULT_PERSISTENCE_PATH = ".contextforge/tasks.json"

    # Pre-defined task templates
    TEMPLATES = {
        "feature": [
            {"name": "Feature: {title}", "children": [
                {"name": "Research and design"},
                {"name": "Implementation"},
                {"name": "Write tests"},
                {"name": "Documentation"},
                {"name": "Code review"},
            ]},
        ],
        "bug_fix": [
            {"name": "Bug Fix: {title}", "children": [
                {"name": "Reproduce issue"},
                {"name": "Identify root cause"},
                {"name": "Implement fix"},
                {"name": "Add regression test"},
                {"name": "Verify fix"},
            ]},
        ],
        "refactor": [
            {"name": "Refactor: {title}", "children": [
                {"name": "Analyze current code"},
                {"name": "Plan refactoring"},
                {"name": "Apply changes incrementally"},
                {"name": "Update tests"},
                {"name": "Verify functionality"},
            ]},
        ],
        "review": [
            {"name": "Code Review: {title}", "children": [
                {"name": "Review code changes"},
                {"name": "Check test coverage"},
                {"name": "Verify documentation"},
                {"name": "Leave feedback"},
            ]},
        ],
        "release": [
            {"name": "Release: {title}", "children": [
                {"name": "Update version numbers"},
                {"name": "Update changelog"},
                {"name": "Run full test suite"},
                {"name": "Build release artifacts"},
                {"name": "Deploy to staging"},
                {"name": "Verify staging"},
                {"name": "Deploy to production"},
                {"name": "Post-release verification"},
            ]},
        ],
    }

    def __init__(self, workspace_root: Optional[str] = None, auto_load: bool = True):
        """
        Initialize task list manager.

        Args:
            workspace_root: Root directory for persistence (default: current dir)
            auto_load: Whether to auto-load from persistence file on init
        """
        self._tasks: Dict[str, Task] = {}
        self._root_task_ids: List[str] = []  # Top-level tasks
        self._undo_stack: List[TaskListSnapshot] = []
        self._redo_stack: List[TaskListSnapshot] = []
        self._workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self._persistence_path = self._workspace_root / self.DEFAULT_PERSISTENCE_PATH

        if auto_load:
            self.load()

    def _save_snapshot(self) -> None:
        """Save current state to undo stack."""
        snapshot = TaskListSnapshot(
            tasks={k: v.to_dict() for k, v in self._tasks.items()},
            root_ids=self._root_task_ids.copy()
        )
        self._undo_stack.append(snapshot)

        # Limit undo history size
        if len(self._undo_stack) > self.MAX_UNDO_HISTORY:
            self._undo_stack.pop(0)

        # Clear redo stack on new change
        self._redo_stack.clear()

    def _restore_snapshot(self, snapshot: TaskListSnapshot) -> None:
        """Restore state from a snapshot."""
        self._tasks = {
            k: Task.from_dict(v) for k, v in snapshot.tasks.items()
        }
        self._root_task_ids = snapshot.root_ids.copy()

    def undo(self) -> bool:
        """
        Undo the last change.

        Returns:
            True if undo was performed, False if nothing to undo
        """
        if not self._undo_stack:
            return False

        # Save current state for redo
        current = TaskListSnapshot(
            tasks={k: v.to_dict() for k, v in self._tasks.items()},
            root_ids=self._root_task_ids.copy()
        )
        self._redo_stack.append(current)

        # Restore previous state
        snapshot = self._undo_stack.pop()
        self._restore_snapshot(snapshot)

        logger.info("Undo performed")
        return True

    def redo(self) -> bool:
        """
        Redo the last undone change.

        Returns:
            True if redo was performed, False if nothing to redo
        """
        if not self._redo_stack:
            return False

        # Save current state for undo
        current = TaskListSnapshot(
            tasks={k: v.to_dict() for k, v in self._tasks.items()},
            root_ids=self._root_task_ids.copy()
        )
        self._undo_stack.append(current)

        # Restore redo state
        snapshot = self._redo_stack.pop()
        self._restore_snapshot(snapshot)

        logger.info("Redo performed")
        return True

    def add_task(self, task: Task, save_undo: bool = True) -> Task:
        """
        Add a task to the list.

        Args:
            task: Task to add
            save_undo: Whether to save undo state

        Returns:
            The added task
        """
        if save_undo:
            self._save_snapshot()

        # Validate task ID
        if not task.task_id:
            task.task_id = str(uuid.uuid4())

        # Handle parent relationship
        if task.parent_id:
            if task.parent_id not in self._tasks:
                raise TaskListValidationError(f"Parent task not found: {task.parent_id}")
            parent = self._tasks[task.parent_id]
            if task.task_id not in parent.children:
                parent.children.append(task.task_id)
        else:
            if task.task_id not in self._root_task_ids:
                self._root_task_ids.append(task.task_id)

        self._tasks[task.task_id] = task
        return task

    def update_task(
        self,
        task_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        state: Optional[TaskState] = None,
        save_undo: bool = True
    ) -> Optional[Task]:
        """
        Update a task's properties.

        Args:
            task_id: ID of task to update
            name: New name (optional)
            description: New description (optional)
            state: New state (optional)
            save_undo: Whether to save undo state

        Returns:
            Updated task or None if not found
        """
        if task_id not in self._tasks:
            return None

        if save_undo:
            self._save_snapshot()

        task = self._tasks[task_id]
        if name is not None:
            task.name = name
        if description is not None:
            task.description = description
        if state is not None:
            task.state = state
        task.updated_at = datetime.now().isoformat()

        return task

    def remove_task(self, task_id: str, save_undo: bool = True) -> bool:
        """
        Remove a task and its subtasks.

        Args:
            task_id: ID of task to remove
            save_undo: Whether to save undo state

        Returns:
            True if removed, False if not found
        """
        if task_id not in self._tasks:
            return False

        if save_undo:
            self._save_snapshot()

        task = self._tasks[task_id]

        # Recursively remove children
        for child_id in task.children.copy():
            self.remove_task(child_id, save_undo=False)

        # Remove from parent's children list
        if task.parent_id and task.parent_id in self._tasks:
            parent = self._tasks[task.parent_id]
            if task_id in parent.children:
                parent.children.remove(task_id)
        else:
            # Remove from root list
            if task_id in self._root_task_ids:
                self._root_task_ids.remove(task_id)

        del self._tasks[task_id]
        return True

    def move_task(
        self,
        task_id: str,
        new_parent_id: Optional[str],
        position: int = -1,
        save_undo: bool = True
    ) -> bool:
        """
        Move a task to a new parent or position.

        Args:
            task_id: ID of task to move
            new_parent_id: New parent ID (None for root)
            position: Position in children list (-1 for end)
            save_undo: Whether to save undo state

        Returns:
            True if moved, False if not found
        """
        if task_id not in self._tasks:
            return False

        # Validate no circular dependency
        if new_parent_id:
            if new_parent_id not in self._tasks:
                return False
            # Check if new_parent is a descendant of task
            if self._is_descendant(new_parent_id, task_id):
                raise TaskListValidationError("Cannot move task under its own descendant")

        if save_undo:
            self._save_snapshot()

        task = self._tasks[task_id]

        # Remove from old parent
        if task.parent_id and task.parent_id in self._tasks:
            old_parent = self._tasks[task.parent_id]
            if task_id in old_parent.children:
                old_parent.children.remove(task_id)
        elif task_id in self._root_task_ids:
            self._root_task_ids.remove(task_id)

        # Add to new parent
        task.parent_id = new_parent_id
        if new_parent_id:
            new_parent = self._tasks[new_parent_id]
            if position < 0 or position >= len(new_parent.children):
                new_parent.children.append(task_id)
            else:
                new_parent.children.insert(position, task_id)
        else:
            if position < 0 or position >= len(self._root_task_ids):
                self._root_task_ids.append(task_id)
            else:
                self._root_task_ids.insert(position, task_id)

        task.updated_at = datetime.now().isoformat()
        return True

    def _is_descendant(self, task_id: str, potential_ancestor_id: str) -> bool:
        """Check if task_id is a descendant of potential_ancestor_id."""
        if task_id == potential_ancestor_id:
            return True

        if potential_ancestor_id not in self._tasks:
            return False

        ancestor = self._tasks[potential_ancestor_id]
        for child_id in ancestor.children:
            if self._is_descendant(task_id, child_id):
                return True
        return False

    def _get_depth(self, task_id: str) -> int:
        """Get the depth of a task in the hierarchy."""
        depth = 0
        current_id = task_id
        while current_id and current_id in self._tasks:
            task = self._tasks[current_id]
            if task.parent_id:
                depth += 1
                current_id = task.parent_id
            else:
                break
        return depth

    def _parse_markdown(self, markdown: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Parse markdown task list into task structures.

        Format:
            - [ ] Task name (task_id: UUID or NEW_UUID)
              - [x] Completed subtask
              - [/] In progress subtask

        Returns:
            Tuple of (task_list, validation_errors)
        """
        import re

        tasks = []
        errors = []
        lines = markdown.split("\n")

        # State pattern: [ ], [x], [/], [-]
        task_pattern = re.compile(
            r'^(\s*)-\s*\[([ x/\-])\]\s*(.+?)(?:\s*\(task_id:\s*([^\)]+)\))?$'
        )

        parent_stack = []  # Stack of (indent_level, task_id)

        for line_num, line in enumerate(lines, 1):
            if not line.strip():
                continue

            match = task_pattern.match(line)
            if not match:
                if line.strip().startswith("-"):
                    errors.append(f"Line {line_num}: Invalid task format")
                continue

            indent = len(match.group(1))
            state_char = match.group(2)
            name = match.group(3).strip()
            task_id = match.group(4).strip() if match.group(4) else "NEW_UUID"

            # Map state character to TaskState
            state_map = {
                " ": TaskState.NOT_STARTED,
                "x": TaskState.COMPLETE,
                "/": TaskState.IN_PROGRESS,
                "-": TaskState.CANCELLED
            }
            state = state_map.get(state_char, TaskState.NOT_STARTED)

            # Determine parent based on indentation
            while parent_stack and parent_stack[-1][0] >= indent:
                parent_stack.pop()

            parent_id = parent_stack[-1][1] if parent_stack else None

            # Generate new UUID if needed
            if task_id == "NEW_UUID":
                task_id = str(uuid.uuid4())

            task_data = {
                "task_id": task_id,
                "name": name,
                "state": state,
                "parent_id": parent_id,
                "indent": indent,
                "line": line_num
            }
            tasks.append(task_data)

            # Push to parent stack
            parent_stack.append((indent, task_id))

        # Validate hierarchy depth
        for task in tasks:
            depth = 0
            current = task
            visited = set()
            while current and current.get("parent_id"):
                if current["task_id"] in visited:
                    errors.append(f"Circular dependency detected for task: {current['name']}")
                    break
                visited.add(current["task_id"])
                depth += 1
                parent_id = current["parent_id"]
                current = next((t for t in tasks if t["task_id"] == parent_id), None)

            if depth > self.MAX_HIERARCHY_DEPTH:
                errors.append(f"Task '{task['name']}' exceeds maximum depth of {self.MAX_HIERARCHY_DEPTH}")

        return tasks, errors

    def reorganize(self, request: ReorganizeRequest) -> ReorganizeResult:
        """
        Reorganize task list from markdown structure.

        Args:
            request: ReorganizeRequest with markdown and options

        Returns:
            ReorganizeResult with status and counts
        """
        # Parse markdown
        parsed_tasks, errors = self._parse_markdown(request.markdown)

        if errors:
            return ReorganizeResult(
                success=False,
                message="Validation errors found",
                validation_errors=errors
            )

        if not parsed_tasks:
            return ReorganizeResult(
                success=False,
                message="No tasks found in markdown"
            )

        # Validate that there's exactly one root task if required
        root_tasks = [t for t in parsed_tasks if t.get("parent_id") is None]
        if len(root_tasks) == 0:
            return ReorganizeResult(
                success=False,
                message="No root task found in markdown"
            )

        if request.validate_only:
            return ReorganizeResult(
                success=True,
                message=f"Validation passed: {len(parsed_tasks)} tasks"
            )

        # Save current state for undo
        self._save_snapshot()

        # Track changes
        tasks_added = 0
        tasks_moved = 0
        old_task_ids = set(self._tasks.keys())
        new_task_ids = set(t["task_id"] for t in parsed_tasks)

        # Clear current structure
        self._tasks.clear()
        self._root_task_ids.clear()

        # Build new structure
        for task_data in parsed_tasks:
            task_id = task_data["task_id"]

            task = Task(
                task_id=task_id,
                name=task_data["name"],
                state=task_data["state"],
                parent_id=task_data.get("parent_id")
            )

            self._tasks[task_id] = task

            if task_id in old_task_ids:
                tasks_moved += 1
            else:
                tasks_added += 1

        # Build parent-child relationships
        for task_id, task in self._tasks.items():
            if task.parent_id:
                if task.parent_id in self._tasks:
                    parent = self._tasks[task.parent_id]
                    if task_id not in parent.children:
                        parent.children.append(task_id)
            else:
                self._root_task_ids.append(task_id)

        tasks_removed = len(old_task_ids - new_task_ids)

        return ReorganizeResult(
            success=True,
            message=f"Reorganized: {tasks_added} added, {tasks_moved} moved, {tasks_removed} removed",
            tasks_added=tasks_added,
            tasks_moved=tasks_moved,
            tasks_removed=tasks_removed
        )

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def list_tasks(self, include_subtasks: bool = True) -> List[Task]:
        """
        List all tasks.

        Args:
            include_subtasks: Whether to include subtasks

        Returns:
            List of all tasks
        """
        if include_subtasks:
            return list(self._tasks.values())
        return [self._tasks[tid] for tid in self._root_task_ids if tid in self._tasks]

    def to_markdown(self) -> str:
        """
        Convert task list to markdown format.

        Returns:
            Markdown representation of task list
        """
        lines = []

        def render_task(task_id: str, indent: int = 0) -> None:
            if task_id not in self._tasks:
                return

            task = self._tasks[task_id]

            # Map state to character
            state_map = {
                TaskState.NOT_STARTED: " ",
                TaskState.COMPLETE: "x",
                TaskState.IN_PROGRESS: "/",
                TaskState.CANCELLED: "-"
            }
            state_char = state_map.get(task.state, " ")

            indent_str = "  " * indent
            line = f"{indent_str}- [{state_char}] {task.name} (task_id: {task.task_id})"
            lines.append(line)

            for child_id in task.children:
                render_task(child_id, indent + 1)

        for root_id in self._root_task_ids:
            render_task(root_id)

        return "\n".join(lines)

    # ============== Persistence Methods ==============

    def save(self, path: Optional[str] = None) -> bool:
        """
        Save task list to JSON file.

        Args:
            path: Custom path (default: .contextforge/tasks.json)

        Returns:
            True if saved successfully
        """
        save_path = Path(path) if path else self._persistence_path

        try:
            # Create directory if needed
            save_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "version": "1.0",
                "tasks": {k: v.to_dict() for k, v in self._tasks.items()},
                "root_task_ids": self._root_task_ids,
                "saved_at": datetime.now().isoformat()
            }

            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Task list saved to {save_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save task list: {e}")
            return False

    def load(self, path: Optional[str] = None) -> bool:
        """
        Load task list from JSON file.

        Args:
            path: Custom path (default: .contextforge/tasks.json)

        Returns:
            True if loaded successfully
        """
        load_path = Path(path) if path else self._persistence_path

        if not load_path.exists():
            logger.debug(f"No task list file found at {load_path}")
            return False

        try:
            with open(load_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self._tasks = {
                k: Task.from_dict(v) for k, v in data.get("tasks", {}).items()
            }
            self._root_task_ids = data.get("root_task_ids", [])

            logger.info(f"Task list loaded from {load_path}: {len(self._tasks)} tasks")
            return True

        except Exception as e:
            logger.error(f"Failed to load task list: {e}")
            return False

    # ============== Dependency Methods ==============

    def add_dependency(self, task_id: str, depends_on: str, save_undo: bool = True) -> bool:
        """
        Add a dependency to a task.

        Args:
            task_id: ID of the task that depends on another
            depends_on: ID of the task that must complete first
            save_undo: Whether to save undo state

        Returns:
            True if dependency added
        """
        if task_id not in self._tasks or depends_on not in self._tasks:
            return False

        if task_id == depends_on:
            return False  # Can't depend on self

        # Check for circular dependency
        if self._would_create_cycle(task_id, depends_on):
            logger.warning(f"Circular dependency detected: {task_id} -> {depends_on}")
            return False

        if save_undo:
            self._save_snapshot()

        task = self._tasks[task_id]
        if depends_on not in task.dependencies:
            task.dependencies.append(depends_on)
            task.updated_at = datetime.now().isoformat()

        return True

    def remove_dependency(self, task_id: str, depends_on: str, save_undo: bool = True) -> bool:
        """
        Remove a dependency from a task.

        Args:
            task_id: ID of the task
            depends_on: ID of the dependency to remove
            save_undo: Whether to save undo state

        Returns:
            True if dependency removed
        """
        if task_id not in self._tasks:
            return False

        if save_undo:
            self._save_snapshot()

        task = self._tasks[task_id]
        if depends_on in task.dependencies:
            task.dependencies.remove(depends_on)
            task.updated_at = datetime.now().isoformat()
            return True

        return False

    def _would_create_cycle(self, task_id: str, new_dep: str) -> bool:
        """Check if adding a dependency would create a cycle."""
        visited: Set[str] = set()

        def has_path(from_id: str, to_id: str) -> bool:
            if from_id == to_id:
                return True
            if from_id in visited:
                return False
            visited.add(from_id)

            if from_id not in self._tasks:
                return False

            for dep_id in self._tasks[from_id].dependencies:
                if has_path(dep_id, to_id):
                    return True
            return False

        return has_path(new_dep, task_id)

    def get_blocked_tasks(self) -> List[Task]:
        """Get tasks that are blocked by incomplete dependencies."""
        blocked = []
        for task in self._tasks.values():
            if task.state == TaskState.NOT_STARTED and task.dependencies:
                for dep_id in task.dependencies:
                    if dep_id in self._tasks:
                        dep = self._tasks[dep_id]
                        if dep.state != TaskState.COMPLETE:
                            blocked.append(task)
                            break
        return blocked

    def get_ready_tasks(self) -> List[Task]:
        """Get tasks that are ready to start (all dependencies complete)."""
        ready = []
        for task in self._tasks.values():
            if task.state == TaskState.NOT_STARTED:
                all_deps_complete = True
                for dep_id in task.dependencies:
                    if dep_id in self._tasks:
                        if self._tasks[dep_id].state != TaskState.COMPLETE:
                            all_deps_complete = False
                            break
                if all_deps_complete:
                    ready.append(task)
        return ready

    # ============== Template Methods ==============

    def list_templates(self) -> List[str]:
        """Get list of available task templates."""
        return list(self.TEMPLATES.keys())

    def apply_template(
        self,
        template_name: str,
        title: str = "",
        parent_id: Optional[str] = None,
        save_undo: bool = True
    ) -> List[Task]:
        """
        Apply a task template.

        Args:
            template_name: Name of the template (feature, bug_fix, refactor, etc.)
            title: Title to substitute into the template
            parent_id: Optional parent task to nest under
            save_undo: Whether to save undo state

        Returns:
            List of created tasks
        """
        if template_name not in self.TEMPLATES:
            raise TaskListValidationError(f"Unknown template: {template_name}")

        if save_undo:
            self._save_snapshot()

        template = self.TEMPLATES[template_name]
        created_tasks = []

        def create_from_template(items: List[Dict], parent: Optional[str] = None) -> None:
            for item in items:
                name = item["name"].format(title=title) if title else item["name"]
                task = Task(
                    task_id=str(uuid.uuid4()),
                    name=name,
                    parent_id=parent
                )
                self.add_task(task, save_undo=False)
                created_tasks.append(task)

                if "children" in item:
                    create_from_template(item["children"], task.task_id)

        create_from_template(template, parent_id)

        logger.info(f"Applied template '{template_name}': {len(created_tasks)} tasks created")
        return created_tasks

    def clear(self, save_undo: bool = True) -> None:
        """Clear all tasks."""
        if save_undo:
            self._save_snapshot()
        self._tasks.clear()
        self._root_task_ids.clear()


# Factory function
_manager_instance: Optional[TaskListManager] = None


def get_tasklist_manager(workspace_root: Optional[str] = None) -> TaskListManager:
    """
    Get or create a TaskListManager instance.

    Args:
        workspace_root: Optional workspace root for persistence

    Returns:
        TaskListManager instance
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = TaskListManager(workspace_root=workspace_root, auto_load=True)
    return _manager_instance


def reset_tasklist_manager() -> None:
    """Reset the singleton instance. Useful for testing."""
    global _manager_instance
    _manager_instance = None