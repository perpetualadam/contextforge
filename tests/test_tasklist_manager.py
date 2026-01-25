"""
Tests for ContextForge Task List Manager tool.

Copyright (c) 2025 ContextForge
"""

import os
import pytest
import tempfile
import shutil
from pathlib import Path
from services.tools.tasklist_manager import (
    TaskListManager,
    Task,
    TaskState,
    TaskListSnapshot,
    ReorganizeRequest,
    ReorganizeResult,
    TaskListValidationError,
    get_tasklist_manager,
    reset_tasklist_manager
)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory."""
    workspace = tempfile.mkdtemp()
    yield workspace
    shutil.rmtree(workspace, ignore_errors=True)


@pytest.fixture
def manager(temp_workspace):
    """Create a fresh TaskListManager instance."""
    mgr = TaskListManager(workspace_root=temp_workspace, auto_load=False)
    mgr.clear(save_undo=False)
    return mgr


class TestTaskCRUD:
    """Tests for basic task CRUD operations."""
    
    def test_add_task(self, manager):
        """Test adding a task."""
        task = manager.add_task(Task(
            task_id="1",
            name="Test Task",
            description="A test task"
        ))
        
        assert task.task_id == "1"
        assert task.name == "Test Task"
        assert task.state == TaskState.NOT_STARTED
    
    def test_add_task_auto_id(self, manager):
        """Test adding a task with auto-generated ID."""
        task = manager.add_task(Task(
            task_id="",
            name="Auto ID Task"
        ))
        
        assert task.task_id != ""
        assert len(task.task_id) == 36  # UUID length
    
    def test_add_subtask(self, manager):
        """Test adding a subtask."""
        parent = manager.add_task(Task(task_id="parent", name="Parent"))
        child = manager.add_task(Task(
            task_id="child",
            name="Child",
            parent_id="parent"
        ))
        
        assert child.parent_id == "parent"
        parent_task = manager.get_task("parent")
        assert "child" in parent_task.children
    
    def test_update_task(self, manager):
        """Test updating a task."""
        manager.add_task(Task(task_id="1", name="Original"))
        
        updated = manager.update_task(
            "1",
            name="Updated",
            state=TaskState.COMPLETE
        )
        
        assert updated.name == "Updated"
        assert updated.state == TaskState.COMPLETE
    
    def test_update_nonexistent_task(self, manager):
        """Test updating a non-existent task."""
        result = manager.update_task("nonexistent", name="Test")
        assert result is None
    
    def test_remove_task(self, manager):
        """Test removing a task."""
        manager.add_task(Task(task_id="1", name="To Remove"))
        
        result = manager.remove_task("1")
        
        assert result is True
        assert manager.get_task("1") is None
    
    def test_remove_task_with_children(self, manager):
        """Test removing a task removes its children."""
        manager.add_task(Task(task_id="parent", name="Parent"))
        manager.add_task(Task(task_id="child", name="Child", parent_id="parent"))
        
        manager.remove_task("parent")
        
        assert manager.get_task("parent") is None
        assert manager.get_task("child") is None
    
    def test_get_task(self, manager):
        """Test getting a task by ID."""
        manager.add_task(Task(task_id="1", name="Test"))
        
        task = manager.get_task("1")
        
        assert task is not None
        assert task.name == "Test"
    
    def test_list_tasks(self, manager):
        """Test listing all tasks."""
        manager.add_task(Task(task_id="1", name="Task 1"))
        manager.add_task(Task(task_id="2", name="Task 2"))
        manager.add_task(Task(task_id="3", name="Task 3", parent_id="1"))
        
        all_tasks = manager.list_tasks(include_subtasks=True)
        root_tasks = manager.list_tasks(include_subtasks=False)
        
        assert len(all_tasks) == 3
        assert len(root_tasks) == 2


class TestMoveTask:
    """Tests for moving tasks in the hierarchy."""
    
    def test_move_task_to_new_parent(self, manager):
        """Test moving a task to a new parent."""
        manager.add_task(Task(task_id="1", name="Task 1"))
        manager.add_task(Task(task_id="2", name="Task 2"))
        manager.add_task(Task(task_id="3", name="Task 3", parent_id="1"))
        
        result = manager.move_task("3", "2")
        
        assert result is True
        task3 = manager.get_task("3")
        assert task3.parent_id == "2"
        assert "3" in manager.get_task("2").children
        assert "3" not in manager.get_task("1").children
    
    def test_move_task_to_root(self, manager):
        """Test moving a task to root level."""
        manager.add_task(Task(task_id="parent", name="Parent"))
        manager.add_task(Task(task_id="child", name="Child", parent_id="parent"))
        
        result = manager.move_task("child", None)
        
        assert result is True
        child = manager.get_task("child")
        assert child.parent_id is None
    
    def test_move_task_circular_dependency(self, manager):
        """Test that circular dependencies are prevented."""
        manager.add_task(Task(task_id="1", name="Task 1"))
        manager.add_task(Task(task_id="2", name="Task 2", parent_id="1"))

        with pytest.raises(TaskListValidationError):
            manager.move_task("1", "2")  # Would create circular dependency


class TestUndoRedo:
    """Tests for undo/redo functionality."""

    def test_undo_add_task(self, manager):
        """Test undoing task addition."""
        manager.add_task(Task(task_id="1", name="Task 1"))

        result = manager.undo()

        assert result is True
        assert manager.get_task("1") is None

    def test_redo_add_task(self, manager):
        """Test redoing task addition."""
        manager.add_task(Task(task_id="1", name="Task 1"))
        manager.undo()

        result = manager.redo()

        assert result is True
        assert manager.get_task("1") is not None

    def test_undo_empty_stack(self, manager):
        """Test undo with empty stack."""
        result = manager.undo()
        assert result is False

    def test_redo_empty_stack(self, manager):
        """Test redo with empty stack."""
        result = manager.redo()
        assert result is False

    def test_undo_update(self, manager):
        """Test undoing a task update."""
        manager.add_task(Task(task_id="1", name="Original"))
        manager.update_task("1", name="Updated")

        manager.undo()

        task = manager.get_task("1")
        assert task.name == "Original"


class TestMarkdownConversion:
    """Tests for markdown parsing and generation."""

    def test_to_markdown(self, manager):
        """Test converting task list to markdown."""
        manager.add_task(Task(task_id="1", name="Task 1"))
        manager.add_task(Task(task_id="2", name="Task 2", parent_id="1"))
        manager.update_task("2", state=TaskState.COMPLETE)

        markdown = manager.to_markdown()

        assert "- [ ] Task 1" in markdown
        assert "- [x] Task 2" in markdown
        assert "task_id: 1" in markdown

    def test_markdown_state_symbols(self, manager):
        """Test all state symbols in markdown."""
        manager.add_task(Task(task_id="1", name="Not Started", state=TaskState.NOT_STARTED))
        manager.add_task(Task(task_id="2", name="In Progress", state=TaskState.IN_PROGRESS))
        manager.add_task(Task(task_id="3", name="Complete", state=TaskState.COMPLETE))
        manager.add_task(Task(task_id="4", name="Cancelled", state=TaskState.CANCELLED))

        markdown = manager.to_markdown()

        assert "[ ] Not Started" in markdown
        assert "[/] In Progress" in markdown
        assert "[x] Complete" in markdown
        assert "[-] Cancelled" in markdown


class TestReorganize:
    """Tests for task list reorganization."""

    def test_reorganize_basic(self, manager):
        """Test basic reorganization from markdown."""
        markdown = """- [ ] New Task 1 (task_id: NEW_UUID)
  - [ ] Subtask 1 (task_id: NEW_UUID)
- [ ] New Task 2 (task_id: NEW_UUID)"""

        result = manager.reorganize(ReorganizeRequest(markdown=markdown))

        assert result.success is True
        assert result.tasks_added >= 3

    def test_reorganize_validate_only(self, manager):
        """Test validation-only reorganization."""
        markdown = """- [ ] Task 1 (task_id: NEW_UUID)"""

        result = manager.reorganize(ReorganizeRequest(
            markdown=markdown,
            validate_only=True
        ))

        assert result.success is True
        # Should not actually add tasks
        assert len(manager.list_tasks()) == 0

    def test_reorganize_invalid_format(self, manager):
        """Test reorganization with invalid markdown."""
        markdown = """Invalid format here"""

        result = manager.reorganize(ReorganizeRequest(markdown=markdown))

        assert result.success is False


class TestFactoryFunction:
    """Tests for the get_tasklist_manager factory function."""

    def test_get_manager(self, temp_workspace):
        """Test getting a manager instance."""
        reset_tasklist_manager()
        mgr = get_tasklist_manager(temp_workspace)

        assert isinstance(mgr, TaskListManager)

    def test_singleton_behavior(self, temp_workspace):
        """Test that factory returns same instance."""
        reset_tasklist_manager()
        mgr1 = get_tasklist_manager(temp_workspace)
        mgr2 = get_tasklist_manager()

        assert mgr1 is mgr2


class TestPersistence:
    """Tests for task list persistence."""

    def test_save_and_load(self, temp_workspace):
        """Test saving and loading task list."""
        mgr1 = TaskListManager(workspace_root=temp_workspace, auto_load=False)
        mgr1.add_task(Task(task_id="1", name="Task 1"))
        mgr1.add_task(Task(task_id="2", name="Task 2", parent_id="1"))

        # Save
        assert mgr1.save() is True

        # Load in new manager
        mgr2 = TaskListManager(workspace_root=temp_workspace, auto_load=True)

        assert len(mgr2.list_tasks()) == 2
        task1 = mgr2.get_task("1")
        assert task1.name == "Task 1"
        assert "2" in task1.children

    def test_save_creates_directory(self, temp_workspace):
        """Test that save creates .contextforge directory."""
        mgr = TaskListManager(workspace_root=temp_workspace, auto_load=False)
        mgr.add_task(Task(task_id="1", name="Test"))
        mgr.save()

        assert (Path(temp_workspace) / ".contextforge" / "tasks.json").exists()

    def test_load_nonexistent_file(self, temp_workspace):
        """Test loading from nonexistent file."""
        mgr = TaskListManager(workspace_root=temp_workspace, auto_load=False)

        result = mgr.load()

        assert result is False
        assert len(mgr.list_tasks()) == 0

    def test_save_custom_path(self, temp_workspace):
        """Test saving to custom path."""
        mgr = TaskListManager(workspace_root=temp_workspace, auto_load=False)
        mgr.add_task(Task(task_id="1", name="Test"))

        custom_path = Path(temp_workspace) / "custom" / "tasks.json"
        mgr.save(str(custom_path))

        assert custom_path.exists()


class TestDependencies:
    """Tests for task dependencies."""

    def test_add_dependency(self, manager):
        """Test adding a dependency."""
        manager.add_task(Task(task_id="1", name="Task 1"))
        manager.add_task(Task(task_id="2", name="Task 2"))

        result = manager.add_dependency("2", "1")

        assert result is True
        task2 = manager.get_task("2")
        assert "1" in task2.dependencies

    def test_add_dependency_circular(self, manager):
        """Test that circular dependencies are rejected."""
        manager.add_task(Task(task_id="1", name="Task 1"))
        manager.add_task(Task(task_id="2", name="Task 2"))

        manager.add_dependency("2", "1")
        result = manager.add_dependency("1", "2")

        assert result is False

    def test_add_dependency_self(self, manager):
        """Test that self-dependency is rejected."""
        manager.add_task(Task(task_id="1", name="Task 1"))

        result = manager.add_dependency("1", "1")

        assert result is False

    def test_remove_dependency(self, manager):
        """Test removing a dependency."""
        manager.add_task(Task(task_id="1", name="Task 1"))
        manager.add_task(Task(task_id="2", name="Task 2"))
        manager.add_dependency("2", "1")

        result = manager.remove_dependency("2", "1")

        assert result is True
        task2 = manager.get_task("2")
        assert "1" not in task2.dependencies

    def test_get_blocked_tasks(self, manager):
        """Test getting blocked tasks."""
        manager.add_task(Task(task_id="1", name="Task 1"))
        manager.add_task(Task(task_id="2", name="Task 2"))
        manager.add_dependency("2", "1")

        blocked = manager.get_blocked_tasks()

        assert len(blocked) == 1
        assert blocked[0].task_id == "2"

    def test_get_blocked_tasks_when_dep_complete(self, manager):
        """Test that task is not blocked when dependency is complete."""
        manager.add_task(Task(task_id="1", name="Task 1", state=TaskState.COMPLETE))
        manager.add_task(Task(task_id="2", name="Task 2"))
        manager.add_dependency("2", "1", save_undo=False)

        blocked = manager.get_blocked_tasks()

        assert len(blocked) == 0

    def test_get_ready_tasks(self, manager):
        """Test getting ready tasks."""
        manager.add_task(Task(task_id="1", name="Task 1", state=TaskState.COMPLETE))
        manager.add_task(Task(task_id="2", name="Task 2"))
        manager.add_task(Task(task_id="3", name="Task 3"))
        manager.add_dependency("2", "1", save_undo=False)

        ready = manager.get_ready_tasks()

        # Both task 2 and 3 should be ready
        task_ids = [t.task_id for t in ready]
        assert "2" in task_ids
        assert "3" in task_ids


class TestTemplates:
    """Tests for task templates."""

    def test_list_templates(self, manager):
        """Test listing available templates."""
        templates = manager.list_templates()

        assert "feature" in templates
        assert "bug_fix" in templates
        assert "refactor" in templates
        assert "review" in templates
        assert "release" in templates

    def test_apply_template(self, manager):
        """Test applying a template."""
        tasks = manager.apply_template("feature", title="Login")

        assert len(tasks) > 0
        assert any("Login" in t.name for t in tasks)

    def test_apply_template_creates_hierarchy(self, manager):
        """Test that template creates proper hierarchy."""
        tasks = manager.apply_template("feature", title="Test")

        # Should have a root task with children
        root_tasks = [t for t in tasks if t.parent_id is None]
        assert len(root_tasks) == 1

        root = root_tasks[0]
        assert len(manager.get_task(root.task_id).children) > 0

    def test_apply_template_under_parent(self, manager):
        """Test applying template under existing parent."""
        parent = manager.add_task(Task(task_id="parent", name="Parent"))
        tasks = manager.apply_template("bug_fix", title="Issue", parent_id="parent")

        # First task should be child of parent
        assert tasks[0].parent_id == "parent"

    def test_apply_unknown_template(self, manager):
        """Test applying unknown template raises error."""
        with pytest.raises(TaskListValidationError):
            manager.apply_template("unknown_template")

