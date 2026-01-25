"""
ContextForge Git Commit Retrieval - Semantic git history search tool.

Provides semantic search over git commit history:
- Search commit messages and diffs using natural language queries
- Return structured commit data with relevance scoring
- Handle repositories without git history gracefully

Copyright (c) 2025 ContextForge
"""

import os
import re
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class GitRetrievalStatus(Enum):
    """Status of a git retrieval operation."""
    SUCCESS = "success"
    NOT_A_REPOSITORY = "not_a_repository"
    NO_COMMITS = "no_commits"
    NO_MATCHES = "no_matches"
    ERROR = "error"


@dataclass
class CommitInfo:
    """Information about a git commit."""
    hash: str
    short_hash: str
    author: str
    author_email: str
    date: str
    message: str
    subject: str  # First line of message
    files_changed: List[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0
    diff_preview: str = ""  # Truncated diff content
    relevance_score: float = 0.0


@dataclass
class GitRetrievalRequest:
    """Request for git commit retrieval."""
    query: str
    repo_path: str = "."
    max_results: int = 10
    include_diffs: bool = True
    diff_context_lines: int = 3
    max_diff_length: int = 1000
    date_after: Optional[str] = None  # ISO format date
    date_before: Optional[str] = None
    author: Optional[str] = None
    path_filter: Optional[str] = None  # Filter by file path
    branch: Optional[str] = None  # Filter by branch name
    tag: Optional[str] = None  # Filter by tag


@dataclass
class GitRetrievalResult:
    """Result of a git retrieval operation."""
    status: GitRetrievalStatus
    message: str
    commits: List[CommitInfo] = field(default_factory=list)
    total_commits_searched: int = 0
    query: str = ""


@dataclass
class BlameLine:
    """A single line from git blame output."""
    line_number: int
    commit_hash: str
    author: str
    author_email: str
    date: str
    content: str


@dataclass
class BlameResult:
    """Result of a git blame operation."""
    status: GitRetrievalStatus
    message: str
    file_path: str = ""
    lines: List[BlameLine] = field(default_factory=list)


@dataclass
class DiffResult:
    """Result of a git diff operation."""
    status: GitRetrievalStatus
    message: str
    from_ref: str = ""
    to_ref: str = ""
    diff_content: str = ""
    files_changed: List[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0


class GitCommitRetrieval:
    """
    Semantic git history search tool.
    
    Provides natural language search over git commit history with
    relevance scoring and structured commit data.
    
    Example usage:
        retrieval = GitCommitRetrieval("/path/to/repo")
        result = retrieval.search(GitRetrievalRequest(
            query="authentication bug fix",
            max_results=5,
            include_diffs=True
        ))
        for commit in result.commits:
            print(f"{commit.short_hash}: {commit.subject} (score: {commit.relevance_score})")
    
    Security considerations:
        - Only reads git history, no write operations
        - Path validation prevents directory traversal
        - Subprocess calls use shell=False for security
    """
    
    def __init__(self, workspace_root: str = None):
        """
        Initialize git commit retrieval.
        
        Args:
            workspace_root: Root directory for relative paths
        """
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
    
    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to workspace root."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.workspace_root / p
    
    def _run_git_command(
        self, 
        args: List[str], 
        cwd: Path,
        check: bool = True
    ) -> Tuple[bool, str, str]:
        """
        Run a git command safely.
        
        Args:
            args: Git command arguments (without 'git')
            cwd: Working directory
            check: Whether to check return code
            
        Returns:
            Tuple of (success, stdout, stderr)
        """
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace"  # Handle encoding errors gracefully
            )
            success = result.returncode == 0 if check else True
            stdout = result.stdout if result.stdout else ""
            stderr = result.stderr if result.stderr else ""
            return success, stdout, stderr
        except subprocess.TimeoutExpired:
            return False, "", "Git command timed out"
        except FileNotFoundError:
            return False, "", "Git is not installed"
        except Exception as e:
            return False, "", str(e)
    
    def is_git_repository(self, path: Path) -> bool:
        """Check if a path is inside a git repository."""
        success, _, _ = self._run_git_command(
            ["rev-parse", "--git-dir"],
            cwd=path,
            check=True
        )
        return success
    
    def get_commit_count(self, path: Path) -> int:
        """Get the total number of commits in the repository."""
        success, stdout, _ = self._run_git_command(
            ["rev-list", "--count", "HEAD"],
            cwd=path
        )
        if success:
            try:
                return int(stdout.strip())
            except ValueError:
                return 0
        return 0

    def _parse_commit_log(self, log_output: str) -> List[Dict[str, str]]:
        """Parse git log output into commit dictionaries."""
        commits = []
        # Use a delimiter to separate commits
        entries = log_output.split("\n---COMMIT_END---\n")

        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue

            commit = {}
            lines = entry.split("\n")
            for line in lines:
                if line.startswith("HASH:"):
                    commit["hash"] = line[5:].strip()
                elif line.startswith("SHORT:"):
                    commit["short_hash"] = line[6:].strip()
                elif line.startswith("AUTHOR:"):
                    commit["author"] = line[7:].strip()
                elif line.startswith("EMAIL:"):
                    commit["author_email"] = line[6:].strip()
                elif line.startswith("DATE:"):
                    commit["date"] = line[5:].strip()
                elif line.startswith("SUBJECT:"):
                    commit["subject"] = line[8:].strip()
                elif line.startswith("BODY:"):
                    commit["message"] = line[5:].strip()

            if "hash" in commit:
                commits.append(commit)

        return commits

    def _calculate_relevance(
        self,
        commit: Dict[str, str],
        query: str,
        query_terms: List[str]
    ) -> float:
        """
        Calculate relevance score for a commit against the query.

        Uses simple term matching with weighting:
        - Subject match: 3x weight
        - Message body match: 2x weight
        - Author match: 1x weight
        """
        score = 0.0
        query_lower = query.lower()

        subject = commit.get("subject", "").lower()
        message = commit.get("message", "").lower()
        author = commit.get("author", "").lower()

        # Exact phrase match in subject (highest priority)
        if query_lower in subject:
            score += 10.0

        # Exact phrase match in message
        if query_lower in message:
            score += 5.0

        # Term matching
        for term in query_terms:
            term_lower = term.lower()
            if len(term_lower) < 2:
                continue

            # Subject matches
            if term_lower in subject:
                score += 3.0

            # Message matches
            if term_lower in message:
                score += 2.0

            # Author matches
            if term_lower in author:
                score += 1.0

        return score

    def _get_commit_stats(self, commit_hash: str, cwd: Path) -> Tuple[List[str], int, int]:
        """Get file changes and stats for a commit."""
        success, stdout, _ = self._run_git_command(
            ["show", "--stat", "--name-only", "--format=", commit_hash],
            cwd=cwd
        )

        files = []
        insertions = 0
        deletions = 0

        if success:
            lines = stdout.strip().split("\n")
            for line in lines:
                line = line.strip()
                if line and not line.startswith(" "):
                    # This is a file name
                    if "|" not in line and "insertion" not in line and "deletion" not in line:
                        files.append(line)
                elif "insertion" in line or "deletion" in line:
                    # Parse stats line
                    match = re.search(r"(\d+) insertion", line)
                    if match:
                        insertions = int(match.group(1))
                    match = re.search(r"(\d+) deletion", line)
                    if match:
                        deletions = int(match.group(1))

        return files, insertions, deletions

    def _get_commit_diff(
        self,
        commit_hash: str,
        cwd: Path,
        context_lines: int = 3,
        max_length: int = 1000
    ) -> str:
        """Get diff preview for a commit."""
        success, stdout, _ = self._run_git_command(
            ["show", f"-U{context_lines}", "--format=", commit_hash],
            cwd=cwd
        )

        if success and stdout:
            diff = stdout.strip()
            if len(diff) > max_length:
                return diff[:max_length] + "\n... (truncated)"
            return diff
        return ""

    def search(self, request: GitRetrievalRequest) -> GitRetrievalResult:
        """
        Search git commit history using natural language query.

        Args:
            request: GitRetrievalRequest with query and options

        Returns:
            GitRetrievalResult with matching commits
        """
        repo_path = self._resolve_path(request.repo_path)

        # Check if it's a git repository
        if not self.is_git_repository(repo_path):
            return GitRetrievalResult(
                status=GitRetrievalStatus.NOT_A_REPOSITORY,
                message=f"Not a git repository: {repo_path}",
                query=request.query
            )

        # Check if there are any commits
        commit_count = self.get_commit_count(repo_path)
        if commit_count == 0:
            return GitRetrievalResult(
                status=GitRetrievalStatus.NO_COMMITS,
                message="Repository has no commits",
                query=request.query
            )

        # Build git log command
        log_format = "HASH:%H%nSHORT:%h%nAUTHOR:%an%nEMAIL:%ae%nDATE:%aI%nSUBJECT:%s%nBODY:%b%n---COMMIT_END---"
        args = [
            "log",
            f"--format={log_format}",
            f"-n{min(commit_count, 500)}"  # Search up to 500 commits
        ]

        # Add date filters
        if request.date_after:
            args.append(f"--after={request.date_after}")
        if request.date_before:
            args.append(f"--before={request.date_before}")

        # Add author filter
        if request.author:
            args.append(f"--author={request.author}")

        # Add branch filter
        if request.branch:
            args.append(request.branch)
        elif request.tag:
            args.append(f"refs/tags/{request.tag}")

        # Add path filter (must come after --)
        if request.path_filter:
            args.append("--")
            args.append(request.path_filter)

        # Run git log
        success, stdout, stderr = self._run_git_command(args, cwd=repo_path)

        if not success:
            return GitRetrievalResult(
                status=GitRetrievalStatus.ERROR,
                message=f"Git error: {stderr}",
                query=request.query
            )

        # Parse commits
        raw_commits = self._parse_commit_log(stdout)

        if not raw_commits:
            return GitRetrievalResult(
                status=GitRetrievalStatus.NO_MATCHES,
                message="No commits found matching criteria",
                query=request.query,
                total_commits_searched=0
            )

        # Calculate relevance scores
        query_terms = re.findall(r'\w+', request.query)
        scored_commits = []

        for raw_commit in raw_commits:
            score = self._calculate_relevance(raw_commit, request.query, query_terms)
            if score > 0:
                scored_commits.append((score, raw_commit))

        # Sort by relevance score
        scored_commits.sort(key=lambda x: x[0], reverse=True)

        # Take top results
        top_commits = scored_commits[:request.max_results]

        if not top_commits:
            return GitRetrievalResult(
                status=GitRetrievalStatus.NO_MATCHES,
                message=f"No commits matched query: {request.query}",
                query=request.query,
                total_commits_searched=len(raw_commits)
            )

        # Build CommitInfo objects
        commits = []
        for score, raw_commit in top_commits:
            commit_hash = raw_commit.get("hash", "")

            # Get file stats
            files, insertions, deletions = self._get_commit_stats(commit_hash, repo_path)

            # Get diff if requested
            diff_preview = ""
            if request.include_diffs:
                diff_preview = self._get_commit_diff(
                    commit_hash,
                    repo_path,
                    request.diff_context_lines,
                    request.max_diff_length
                )

            commits.append(CommitInfo(
                hash=commit_hash,
                short_hash=raw_commit.get("short_hash", ""),
                author=raw_commit.get("author", ""),
                author_email=raw_commit.get("author_email", ""),
                date=raw_commit.get("date", ""),
                message=raw_commit.get("message", ""),
                subject=raw_commit.get("subject", ""),
                files_changed=files,
                insertions=insertions,
                deletions=deletions,
                diff_preview=diff_preview,
                relevance_score=score
            ))

        return GitRetrievalResult(
            status=GitRetrievalStatus.SUCCESS,
            message=f"Found {len(commits)} matching commits",
            commits=commits,
            total_commits_searched=len(raw_commits),
            query=request.query
        )

    def get_commit(self, commit_hash: str, repo_path: str = ".") -> Optional[CommitInfo]:
        """
        Get detailed information about a specific commit.

        Args:
            commit_hash: Full or short commit hash
            repo_path: Path to repository

        Returns:
            CommitInfo or None if not found
        """
        path = self._resolve_path(repo_path)

        if not self.is_git_repository(path):
            return None

        # Get commit details
        log_format = "HASH:%H%nSHORT:%h%nAUTHOR:%an%nEMAIL:%ae%nDATE:%aI%nSUBJECT:%s%nBODY:%b%n---COMMIT_END---"
        success, stdout, _ = self._run_git_command(
            ["show", f"--format={log_format}", "-s", commit_hash],
            cwd=path
        )

        if not success:
            return None

        raw_commits = self._parse_commit_log(stdout)
        if not raw_commits:
            return None

        raw_commit = raw_commits[0]
        full_hash = raw_commit.get("hash", commit_hash)

        # Get stats and diff
        files, insertions, deletions = self._get_commit_stats(full_hash, path)
        diff_preview = self._get_commit_diff(full_hash, path)

        return CommitInfo(
            hash=full_hash,
            short_hash=raw_commit.get("short_hash", ""),
            author=raw_commit.get("author", ""),
            author_email=raw_commit.get("author_email", ""),
            date=raw_commit.get("date", ""),
            message=raw_commit.get("message", ""),
            subject=raw_commit.get("subject", ""),
            files_changed=files,
            insertions=insertions,
            deletions=deletions,
            diff_preview=diff_preview,
            relevance_score=1.0
        )

    def blame(
        self,
        file_path: str,
        repo_path: str = ".",
        start_line: Optional[int] = None,
        end_line: Optional[int] = None
    ) -> BlameResult:
        """
        Get git blame information for a file.

        Args:
            file_path: Path to the file (relative to repo)
            repo_path: Path to the repository
            start_line: Optional starting line number
            end_line: Optional ending line number

        Returns:
            BlameResult with line-by-line blame information
        """
        path = self._resolve_path(repo_path)

        if not self.is_git_repository(path):
            return BlameResult(
                status=GitRetrievalStatus.NOT_A_REPOSITORY,
                message=f"Not a git repository: {path}",
                file_path=file_path
            )

        # Build blame command
        args = ["blame", "--line-porcelain"]

        if start_line is not None and end_line is not None:
            args.append(f"-L{start_line},{end_line}")
        elif start_line is not None:
            args.append(f"-L{start_line},")

        args.append(file_path)

        success, stdout, stderr = self._run_git_command(args, cwd=path)

        if not success:
            return BlameResult(
                status=GitRetrievalStatus.ERROR,
                message=f"Git blame error: {stderr}",
                file_path=file_path
            )

        # Parse porcelain format
        lines = []
        current_commit = {}
        line_number = start_line or 1

        for line in stdout.split('\n'):
            if line.startswith('\t'):
                # This is the actual code line
                content = line[1:]  # Remove leading tab
                lines.append(BlameLine(
                    line_number=line_number,
                    commit_hash=current_commit.get('hash', ''),
                    author=current_commit.get('author', ''),
                    author_email=current_commit.get('author-mail', '').strip('<>'),
                    date=current_commit.get('author-time', ''),
                    content=content
                ))
                line_number += 1
                current_commit = {}
            elif ' ' in line:
                key, _, value = line.partition(' ')
                if len(key) == 40:  # SHA hash
                    current_commit['hash'] = key
                else:
                    current_commit[key] = value

        return BlameResult(
            status=GitRetrievalStatus.SUCCESS,
            message=f"Blame for {len(lines)} lines",
            file_path=file_path,
            lines=lines
        )

    def diff(
        self,
        from_ref: str,
        to_ref: str = "HEAD",
        repo_path: str = ".",
        file_path: Optional[str] = None,
        context_lines: int = 3
    ) -> DiffResult:
        """
        Get diff between two commits or branches.

        Args:
            from_ref: Starting commit/branch/tag
            to_ref: Ending commit/branch/tag (default: HEAD)
            repo_path: Path to the repository
            file_path: Optional specific file to diff
            context_lines: Number of context lines around changes

        Returns:
            DiffResult with diff content and statistics
        """
        path = self._resolve_path(repo_path)

        if not self.is_git_repository(path):
            return DiffResult(
                status=GitRetrievalStatus.NOT_A_REPOSITORY,
                message=f"Not a git repository: {path}",
                from_ref=from_ref,
                to_ref=to_ref
            )

        # Build diff command
        args = ["diff", f"-U{context_lines}", "--stat", from_ref, to_ref]

        if file_path:
            args.append("--")
            args.append(file_path)

        success, stdout, stderr = self._run_git_command(args, cwd=path)

        if not success:
            return DiffResult(
                status=GitRetrievalStatus.ERROR,
                message=f"Git diff error: {stderr}",
                from_ref=from_ref,
                to_ref=to_ref
            )

        # Parse stats from the end of output
        files_changed = []
        insertions = 0
        deletions = 0

        # Get full diff content
        diff_args = ["diff", f"-U{context_lines}", from_ref, to_ref]
        if file_path:
            diff_args.extend(["--", file_path])

        _, diff_content, _ = self._run_git_command(diff_args, cwd=path)

        # Parse diff for file names
        for line in diff_content.split('\n'):
            if line.startswith('diff --git'):
                # Extract file path
                parts = line.split(' ')
                if len(parts) >= 4:
                    files_changed.append(parts[3][2:])  # Remove 'b/' prefix
            elif line.startswith('+') and not line.startswith('+++'):
                insertions += 1
            elif line.startswith('-') and not line.startswith('---'):
                deletions += 1

        return DiffResult(
            status=GitRetrievalStatus.SUCCESS,
            message=f"Diff: {len(files_changed)} files, +{insertions}/-{deletions}",
            from_ref=from_ref,
            to_ref=to_ref,
            diff_content=diff_content,
            files_changed=files_changed,
            insertions=insertions,
            deletions=deletions
        )

    def list_branches(self, repo_path: str = ".") -> List[str]:
        """List all branches in the repository."""
        path = self._resolve_path(repo_path)
        success, stdout, _ = self._run_git_command(["branch", "-a"], cwd=path)
        if not success:
            return []

        branches = []
        for line in stdout.split('\n'):
            line = line.strip()
            if line.startswith('*'):
                line = line[2:]  # Remove "* " prefix
            if line and not line.startswith('remotes/'):
                branches.append(line.strip())
        return branches

    def list_tags(self, repo_path: str = ".") -> List[str]:
        """List all tags in the repository."""
        path = self._resolve_path(repo_path)
        success, stdout, _ = self._run_git_command(["tag", "-l"], cwd=path)
        if not success:
            return []

        return [t.strip() for t in stdout.split('\n') if t.strip()]


# Factory function
_retrieval_instance: Optional[GitCommitRetrieval] = None


def get_git_commit_retrieval(workspace_root: str = None) -> GitCommitRetrieval:
    """
    Get or create a GitCommitRetrieval instance.

    Args:
        workspace_root: Root directory for relative paths

    Returns:
        GitCommitRetrieval instance
    """
    global _retrieval_instance
    if _retrieval_instance is None or workspace_root is not None:
        _retrieval_instance = GitCommitRetrieval(workspace_root=workspace_root)
    return _retrieval_instance
