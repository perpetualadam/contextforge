"""
Tests for ContextForge Git Commit Retrieval tool.

Copyright (c) 2025 ContextForge
"""

import os
import pytest
import tempfile
import shutil
import subprocess
from pathlib import Path

from services.tools.git_commit_retrieval import (
    GitCommitRetrieval,
    GitRetrievalRequest,
    GitRetrievalResult,
    GitRetrievalStatus,
    CommitInfo,
    BlameLine,
    BlameResult,
    DiffResult,
    get_git_commit_retrieval
)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory."""
    workspace = tempfile.mkdtemp()
    yield workspace
    shutil.rmtree(workspace, ignore_errors=True)


@pytest.fixture
def git_repo(temp_workspace):
    """Create a temporary git repository with commits."""
    repo_path = Path(temp_workspace)
    
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_path, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path, capture_output=True
    )
    
    # Create initial commit
    (repo_path / "file1.py").write_text("print('hello')")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit: Add file1.py"],
        cwd=repo_path, capture_output=True
    )
    
    # Create second commit
    (repo_path / "file2.py").write_text("def feature(): pass")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: Add new feature in file2"],
        cwd=repo_path, capture_output=True
    )
    
    # Create third commit
    (repo_path / "file1.py").write_text("print('hello world')")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "fix: Update file1 with bug fix"],
        cwd=repo_path, capture_output=True
    )
    
    return repo_path


@pytest.fixture
def retrieval(temp_workspace):
    """Create a GitCommitRetrieval instance with temp workspace."""
    return GitCommitRetrieval(workspace_root=temp_workspace)


class TestIsGitRepository:
    """Tests for git repository detection."""
    
    def test_is_git_repository_true(self, retrieval, git_repo):
        """Test detecting a valid git repository."""
        assert retrieval.is_git_repository(git_repo) is True
    
    def test_is_git_repository_false(self, retrieval, temp_workspace):
        """Test detecting a non-git directory."""
        non_git_dir = Path(temp_workspace) / "not_a_repo"
        non_git_dir.mkdir()
        assert retrieval.is_git_repository(non_git_dir) is False


class TestGetCommitCount:
    """Tests for commit count functionality."""
    
    def test_get_commit_count(self, retrieval, git_repo):
        """Test getting commit count."""
        count = retrieval.get_commit_count(git_repo)
        assert count == 3
    
    def test_get_commit_count_no_repo(self, retrieval, temp_workspace):
        """Test commit count for non-repo."""
        count = retrieval.get_commit_count(Path(temp_workspace))
        assert count == 0


class TestSearch:
    """Tests for git commit search functionality."""
    
    def test_search_basic(self, retrieval, git_repo):
        """Test basic search."""
        request = GitRetrievalRequest(
            query="feature",
            repo_path=str(git_repo),
            max_results=5
        )
        
        result = retrieval.search(request)
        
        assert result.status == GitRetrievalStatus.SUCCESS
        assert len(result.commits) >= 1
        assert any("feature" in c.subject.lower() for c in result.commits)
    
    def test_search_with_author_filter(self, retrieval, git_repo):
        """Test search with author filter."""
        request = GitRetrievalRequest(
            query="commit",
            repo_path=str(git_repo),
            author="Test User"
        )
        
        result = retrieval.search(request)
        
        assert result.status == GitRetrievalStatus.SUCCESS
        for commit in result.commits:
            assert commit.author == "Test User"
    
    def test_search_no_matches(self, retrieval, git_repo):
        """Test search with no matches."""
        request = GitRetrievalRequest(
            query="xyznonexistent123",
            repo_path=str(git_repo)
        )

        result = retrieval.search(request)

        assert result.status == GitRetrievalStatus.NO_MATCHES
        assert len(result.commits) == 0

    def test_search_not_a_repository(self, retrieval, temp_workspace):
        """Test search on non-git directory."""
        non_git = Path(temp_workspace) / "not_git"
        non_git.mkdir()

        request = GitRetrievalRequest(
            query="anything",
            repo_path=str(non_git)
        )

        result = retrieval.search(request)

        assert result.status == GitRetrievalStatus.NOT_A_REPOSITORY

    def test_search_with_diffs(self, retrieval, git_repo):
        """Test search with diff previews included."""
        request = GitRetrievalRequest(
            query="file1",
            repo_path=str(git_repo),
            include_diffs=True,
            max_diff_length=500
        )

        result = retrieval.search(request)

        assert result.status == GitRetrievalStatus.SUCCESS
        # At least one commit should have diff preview
        has_diff = any(c.diff_preview for c in result.commits)
        assert has_diff


class TestGetCommit:
    """Tests for getting specific commit details."""

    def test_get_commit_by_hash(self, retrieval, git_repo):
        """Test getting a specific commit by hash."""
        # First get a commit hash
        request = GitRetrievalRequest(
            query="Initial",
            repo_path=str(git_repo)
        )
        search_result = retrieval.search(request)
        assert len(search_result.commits) > 0

        commit_hash = search_result.commits[0].hash

        # Now get the commit directly
        commit = retrieval.get_commit(commit_hash, str(git_repo))

        assert commit is not None
        assert commit.hash == commit_hash
        assert "Initial" in commit.subject

    def test_get_commit_not_found(self, retrieval, git_repo):
        """Test getting a non-existent commit."""
        commit = retrieval.get_commit("0000000000000000", str(git_repo))
        assert commit is None


class TestCommitInfo:
    """Tests for CommitInfo data class."""

    def test_commit_info_fields(self, retrieval, git_repo):
        """Test that CommitInfo has all expected fields."""
        request = GitRetrievalRequest(
            query="feature",
            repo_path=str(git_repo)
        )

        result = retrieval.search(request)
        assert len(result.commits) > 0

        commit = result.commits[0]

        assert commit.hash is not None
        assert commit.short_hash is not None
        assert commit.author is not None
        assert commit.date is not None
        assert commit.subject is not None
        assert isinstance(commit.files_changed, list)
        assert isinstance(commit.relevance_score, float)


class TestFactoryFunction:
    """Tests for the get_git_commit_retrieval factory function."""

    def test_get_retrieval(self, temp_workspace):
        """Test getting a retrieval instance."""
        retrieval = get_git_commit_retrieval(temp_workspace)

        assert isinstance(retrieval, GitCommitRetrieval)
        assert retrieval.workspace_root == Path(temp_workspace)

    def test_singleton_behavior(self, temp_workspace):
        """Test that factory returns same instance without workspace."""
        retrieval1 = get_git_commit_retrieval()
        retrieval2 = get_git_commit_retrieval()

        # Should be the same instance
        assert retrieval1 is retrieval2


class TestBlame:
    """Tests for git blame functionality."""

    def test_blame_file(self, retrieval, git_repo):
        """Test blame on a file."""
        result = retrieval.blame("file1.py", str(git_repo))

        assert result.status == GitRetrievalStatus.SUCCESS
        assert len(result.lines) > 0
        assert result.file_path == "file1.py"

    def test_blame_line_info(self, retrieval, git_repo):
        """Test that blame lines have expected info."""
        result = retrieval.blame("file1.py", str(git_repo))

        if result.lines:
            line = result.lines[0]
            assert isinstance(line, BlameLine)
            assert line.line_number >= 1
            assert line.commit_hash is not None
            assert line.author is not None

    def test_blame_not_a_repo(self, retrieval, temp_workspace):
        """Test blame on non-repository."""
        result = retrieval.blame("somefile.py", temp_workspace)

        assert result.status == GitRetrievalStatus.NOT_A_REPOSITORY

    def test_blame_nonexistent_file(self, retrieval, git_repo):
        """Test blame on nonexistent file."""
        result = retrieval.blame("nonexistent.py", str(git_repo))

        assert result.status == GitRetrievalStatus.ERROR


class TestDiff:
    """Tests for git diff functionality."""

    def test_diff_between_commits(self, retrieval, git_repo):
        """Test diff between two commits."""
        # Get commit hashes
        request = GitRetrievalRequest(query="", repo_path=str(git_repo))
        search_result = retrieval.search(request)

        if len(search_result.commits) >= 2:
            from_ref = search_result.commits[-1].hash
            to_ref = search_result.commits[0].hash

            result = retrieval.diff(from_ref, to_ref, str(git_repo))

            assert result.status == GitRetrievalStatus.SUCCESS
            assert result.from_ref == from_ref
            assert result.to_ref == to_ref

    def test_diff_has_content(self, retrieval, git_repo):
        """Test that diff has content."""
        request = GitRetrievalRequest(query="", repo_path=str(git_repo))
        search_result = retrieval.search(request)

        if len(search_result.commits) >= 2:
            from_ref = search_result.commits[-1].hash
            to_ref = search_result.commits[0].hash

            result = retrieval.diff(from_ref, to_ref, str(git_repo))

            assert result.diff_content is not None
            assert len(result.files_changed) > 0

    def test_diff_not_a_repo(self, retrieval, temp_workspace):
        """Test diff on non-repository."""
        result = retrieval.diff("abc123", "def456", temp_workspace)

        assert result.status == GitRetrievalStatus.NOT_A_REPOSITORY


class TestBranchesAndTags:
    """Tests for branch and tag functionality."""

    def test_list_branches(self, retrieval, git_repo):
        """Test listing branches."""
        branches = retrieval.list_branches(str(git_repo))

        # Should at least have main/master
        assert len(branches) >= 1

    def test_list_tags(self, retrieval, git_repo):
        """Test listing tags (empty repo)."""
        tags = retrieval.list_tags(str(git_repo))

        # No tags created, should be empty
        assert isinstance(tags, list)

    def test_search_with_branch_filter(self, retrieval, git_repo):
        """Test search with branch filter."""
        # Get the current branch name
        branches = retrieval.list_branches(str(git_repo))

        if branches:
            request = GitRetrievalRequest(
                query="commit",
                repo_path=str(git_repo),
                branch=branches[0]
            )

            result = retrieval.search(request)

            # Should complete without error
            assert result.status in [
                GitRetrievalStatus.SUCCESS,
                GitRetrievalStatus.NO_MATCHES
            ]

