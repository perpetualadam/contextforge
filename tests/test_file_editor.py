"""
Tests for ContextForge File Editor tools.

Copyright (c) 2025 ContextForge
"""

import os
import pytest
import tempfile
import shutil
from pathlib import Path

from services.tools.file_editor import (
    FileEditor,
    StrReplaceRequest,
    StrReplaceEntry,
    SaveFileRequest,
    RemoveFilesRequest,
    FileEditResult,
    EditResultStatus,
    get_file_editor
)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory."""
    workspace = tempfile.mkdtemp()
    yield workspace
    shutil.rmtree(workspace, ignore_errors=True)


@pytest.fixture
def editor(temp_workspace):
    """Create a FileEditor instance with temp workspace."""
    return FileEditor(workspace_root=temp_workspace)


@pytest.fixture
def sample_file(temp_workspace):
    """Create a sample file for testing."""
    file_path = Path(temp_workspace) / "sample.py"
    content = '''def hello():
    print("Hello, World!")
    return True

def goodbye():
    print("Goodbye!")
    return False
'''
    file_path.write_text(content)
    return file_path


class TestStrReplace:
    """Tests for string replacement functionality."""
    
    def test_simple_replacement(self, editor, sample_file):
        """Test basic string replacement."""
        request = StrReplaceRequest(
            path=str(sample_file),
            replacements=[
                StrReplaceEntry(
                    old_str='print("Hello, World!")',
                    new_str='print("Hi there!")'
                )
            ]
        )
        
        result = editor.str_replace(request)
        
        assert result.status == EditResultStatus.SUCCESS
        assert result.changes_made == 1
        assert 'print("Hi there!")' in sample_file.read_text()
    
    def test_replacement_with_line_numbers(self, editor, sample_file):
        """Test replacement with line number disambiguation."""
        # Add duplicate content
        content = sample_file.read_text()
        content += '\ndef another():\n    print("Hello, World!")\n'
        sample_file.write_text(content)
        
        request = StrReplaceRequest(
            path=str(sample_file),
            replacements=[
                StrReplaceEntry(
                    old_str='print("Hello, World!")',
                    new_str='print("First one!")',
                    start_line=2,
                    end_line=2
                )
            ]
        )
        
        result = editor.str_replace(request)
        
        assert result.status == EditResultStatus.SUCCESS
        content = sample_file.read_text()
        assert 'print("First one!")' in content
        # Second occurrence should be unchanged
        assert content.count('print("Hello, World!")') == 1
    
    def test_multiple_matches_error(self, editor, sample_file):
        """Test error when multiple matches found without line numbers."""
        # Add duplicate content
        content = sample_file.read_text()
        content += '\ndef another():\n    print("Hello, World!")\n'
        sample_file.write_text(content)
        
        request = StrReplaceRequest(
            path=str(sample_file),
            replacements=[
                StrReplaceEntry(
                    old_str='print("Hello, World!")',
                    new_str='print("Changed!")'
                )
            ]
        )
        
        result = editor.str_replace(request)
        
        assert result.status == EditResultStatus.MULTIPLE_MATCHES
        assert "Multiple matches" in result.message
    
    def test_string_not_found(self, editor, sample_file):
        """Test error when string not found."""
        request = StrReplaceRequest(
            path=str(sample_file),
            replacements=[
                StrReplaceEntry(
                    old_str='nonexistent string',
                    new_str='replacement'
                )
            ]
        )
        
        result = editor.str_replace(request)
        
        assert result.status == EditResultStatus.NO_MATCH
    
    def test_file_not_found(self, editor, temp_workspace):
        """Test error when file doesn't exist."""
        request = StrReplaceRequest(
            path=os.path.join(temp_workspace, "nonexistent.py"),
            replacements=[
                StrReplaceEntry(old_str='a', new_str='b')
            ]
        )
        
        result = editor.str_replace(request)
        
        assert result.status == EditResultStatus.FILE_NOT_FOUND
    
    def test_backup_creation(self, editor, sample_file):
        """Test that backup is created."""
        original_content = sample_file.read_text()
        
        request = StrReplaceRequest(
            path=str(sample_file),
            replacements=[
                StrReplaceEntry(
                    old_str='def hello():',
                    new_str='def greet():'
                )
            ],
            create_backup=True
        )
        
        result = editor.str_replace(request)
        
        assert result.status == EditResultStatus.SUCCESS
        assert result.backup_path is not None
        assert Path(result.backup_path).exists()
        assert Path(result.backup_path).read_text() == original_content


class TestSaveFile:
    """Tests for save file functionality."""

    def test_create_new_file(self, editor, temp_workspace):
        """Test creating a new file."""
        request = SaveFileRequest(
            path=os.path.join(temp_workspace, "new_file.py"),
            content='print("Hello!")'
        )

        result = editor.save_file(request)

        assert result.status == EditResultStatus.SUCCESS
        assert Path(request.path).exists()
        assert 'print("Hello!")' in Path(request.path).read_text()

    def test_create_with_directories(self, editor, temp_workspace):
        """Test creating file with nested directories."""
        request = SaveFileRequest(
            path=os.path.join(temp_workspace, "deep", "nested", "file.py"),
            content='# New file',
            create_directories=True
        )

        result = editor.save_file(request)

        assert result.status == EditResultStatus.SUCCESS
        assert Path(request.path).exists()

    def test_no_overwrite_existing(self, editor, sample_file):
        """Test that existing files are not overwritten by default."""
        request = SaveFileRequest(
            path=str(sample_file),
            content='new content',
            overwrite=False
        )

        result = editor.save_file(request)

        assert result.status == EditResultStatus.VALIDATION_ERROR
        assert "already exists" in result.message

    def test_overwrite_existing(self, editor, sample_file):
        """Test overwriting existing file when allowed."""
        request = SaveFileRequest(
            path=str(sample_file),
            content='new content',
            overwrite=True
        )

        result = editor.save_file(request)

        assert result.status == EditResultStatus.SUCCESS
        assert sample_file.read_text().strip() == 'new content'

    def test_trailing_newline(self, editor, temp_workspace):
        """Test that trailing newline is added."""
        request = SaveFileRequest(
            path=os.path.join(temp_workspace, "newline_test.py"),
            content='no newline',
            add_trailing_newline=True
        )

        result = editor.save_file(request)

        assert result.status == EditResultStatus.SUCCESS
        assert Path(request.path).read_text().endswith('\n')


class TestRemoveFiles:
    """Tests for file removal functionality."""

    def test_remove_single_file(self, editor, sample_file):
        """Test removing a single file."""
        request = RemoveFilesRequest(paths=[str(sample_file)])

        results = editor.remove_files(request)

        assert len(results) == 1
        assert results[0].status == EditResultStatus.SUCCESS
        assert not sample_file.exists()

    def test_remove_multiple_files(self, editor, temp_workspace):
        """Test removing multiple files."""
        files = []
        for i in range(3):
            f = Path(temp_workspace) / f"file{i}.txt"
            f.write_text(f"content {i}")
            files.append(str(f))

        request = RemoveFilesRequest(paths=files)

        results = editor.remove_files(request)

        assert len(results) == 3
        assert all(r.status == EditResultStatus.SUCCESS for r in results)
        assert all(not Path(f).exists() for f in files)

    def test_remove_nonexistent_file(self, editor, temp_workspace):
        """Test removing a file that doesn't exist."""
        request = RemoveFilesRequest(
            paths=[os.path.join(temp_workspace, "nonexistent.txt")]
        )

        results = editor.remove_files(request)

        assert len(results) == 1
        assert results[0].status == EditResultStatus.FILE_NOT_FOUND

    def test_remove_directory_blocked(self, editor, temp_workspace):
        """Test that directories are not removed by default."""
        dir_path = Path(temp_workspace) / "subdir"
        dir_path.mkdir()

        request = RemoveFilesRequest(paths=[str(dir_path)])

        results = editor.remove_files(request)

        assert len(results) == 1
        assert results[0].status == EditResultStatus.VALIDATION_ERROR
        assert dir_path.exists()

    def test_remove_directory_allowed(self, editor, temp_workspace):
        """Test removing directory when allowed."""
        dir_path = Path(temp_workspace) / "subdir"
        dir_path.mkdir()
        (dir_path / "file.txt").write_text("content")

        request = RemoveFilesRequest(
            paths=[str(dir_path)],
            allow_directories=True
        )

        results = editor.remove_files(request)

        assert len(results) == 1
        assert results[0].status == EditResultStatus.SUCCESS
        assert not dir_path.exists()


class TestPathValidation:
    """Tests for path security validation."""

    def test_path_traversal_blocked(self, editor, temp_workspace):
        """Test that path traversal is blocked."""
        request = SaveFileRequest(
            path=os.path.join(temp_workspace, "..", "outside.txt"),
            content='malicious'
        )

        result = editor.save_file(request)

        assert result.status == EditResultStatus.VALIDATION_ERROR
        assert "outside workspace" in result.message.lower()


class TestProtectedPaths:
    """Tests for protected path deletion prevention."""

    def test_protected_git_directory(self, editor, temp_workspace):
        """Test that .git directory is protected."""
        git_dir = Path(temp_workspace) / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("test")

        request = RemoveFilesRequest(
            paths=[str(git_dir)],
            allow_directories=True
        )

        results = editor.remove_files(request)

        assert results[0].status == EditResultStatus.VALIDATION_ERROR
        assert "protected" in results[0].message.lower()
        assert git_dir.exists()

    def test_protected_gitignore(self, editor, temp_workspace):
        """Test that .gitignore is protected."""
        gitignore = Path(temp_workspace) / ".gitignore"
        gitignore.write_text("*.pyc")

        request = RemoveFilesRequest(paths=[str(gitignore)])

        results = editor.remove_files(request)

        assert results[0].status == EditResultStatus.VALIDATION_ERROR
        assert gitignore.exists()

    def test_protected_env_file(self, editor, temp_workspace):
        """Test that .env file is protected."""
        env_file = Path(temp_workspace) / ".env"
        env_file.write_text("SECRET=value")

        request = RemoveFilesRequest(paths=[str(env_file)])

        results = editor.remove_files(request)

        assert results[0].status == EditResultStatus.VALIDATION_ERROR

    def test_force_override_protection(self, editor, temp_workspace):
        """Test that force flag overrides protection."""
        gitignore = Path(temp_workspace) / ".gitignore"
        gitignore.write_text("*.pyc")

        request = RemoveFilesRequest(
            paths=[str(gitignore)],
            force=True
        )

        results = editor.remove_files(request)

        assert results[0].status == EditResultStatus.SUCCESS
        assert not gitignore.exists()

    def test_dry_run_mode(self, editor, temp_workspace):
        """Test dry run mode doesn't delete files."""
        test_file = Path(temp_workspace) / "test.txt"
        test_file.write_text("content")

        request = RemoveFilesRequest(
            paths=[str(test_file)],
            dry_run=True
        )

        results = editor.remove_files(request)

        assert results[0].status == EditResultStatus.SUCCESS
        assert "would remove" in results[0].message.lower()
        assert test_file.exists()  # File should still exist

    def test_no_backup_option(self, editor, temp_workspace):
        """Test removal without backup."""
        test_file = Path(temp_workspace) / "test.txt"
        test_file.write_text("content")

        request = RemoveFilesRequest(
            paths=[str(test_file)],
            create_backup=False
        )

        results = editor.remove_files(request)

        assert results[0].status == EditResultStatus.SUCCESS
        assert results[0].backup_path is None
        assert not test_file.exists()


class TestFactoryFunction:
    """Tests for the get_file_editor factory function."""

    def test_get_editor(self, temp_workspace):
        """Test getting an editor instance."""
        editor = get_file_editor(temp_workspace)

        assert isinstance(editor, FileEditor)
        assert editor.workspace_root == Path(temp_workspace)

