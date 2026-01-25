"""
ContextForge Tools Module.

Provides essential file and code manipulation tools for AI assistants:
- File editing with string replacement (str-replace-editor)
- File creation and saving (save-file)
- File deletion (remove-files)
- File and directory viewing (view)
- Process management (launch, read, write, kill, list)
- File watching (real-time file system monitoring)
- Process streaming (real-time output streaming)
- Git commit retrieval (git history search)
- Task list management (task hierarchy operations)

Copyright (c) 2025 ContextForge
"""

from .file_editor import (
    FileEditor,
    StrReplaceRequest,
    StrReplaceEntry,
    SaveFileRequest,
    RemoveFilesRequest,
    FileEditResult,
    EditResultStatus,
    get_file_editor
)

from .code_viewer import (
    CodeViewer,
    ViewRequest,
    ViewResult,
    ViewResultStatus,
    get_code_viewer
)

from .process_manager import (
    ProcessManager,
    LaunchProcessRequest,
    ProcessInfo,
    ProcessResult,
    ProcessState,
    get_process_manager
)

from .file_watcher import (
    FileWatcher,
    FileEvent,
    FileEventType,
    WatchConfig,
    get_file_watcher
)

from .process_streamer import (
    ProcessStreamer,
    StreamConfig,
    StreamLine,
    get_process_streamer
)

from .git_commit_retrieval import (
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

from .tasklist_manager import (
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

from .browser_opener import (
    BrowserOpener,
    BrowserOpenRequest,
    BrowserOpenResult,
    BrowserOpenStatus,
    get_browser_opener,
    reset_browser_opener
)

from .terminal_reader import (
    TerminalReader,
    TerminalReadRequest,
    TerminalReadResult,
    TerminalReadStatus,
    TerminalInfo,
    TerminalState,
    get_terminal_reader,
    reset_terminal_reader
)

from .truncated_content import (
    TruncatedContentManager,
    ContentReference,
    ViewRangeRequest,
    ViewRangeResult,
    SearchRequest,
    SearchResult,
    SearchMatch,
    TruncatedContentStatus,
    get_truncated_content_manager,
    reset_truncated_content_manager
)

__all__ = [
    # File Editor
    "FileEditor",
    "StrReplaceRequest",
    "StrReplaceEntry",
    "SaveFileRequest",
    "RemoveFilesRequest",
    "FileEditResult",
    "EditResultStatus",
    "get_file_editor",
    # Code Viewer
    "CodeViewer",
    "ViewRequest",
    "ViewResult",
    "ViewResultStatus",
    "get_code_viewer",
    # Process Manager
    "ProcessManager",
    "LaunchProcessRequest",
    "ProcessInfo",
    "ProcessResult",
    "ProcessState",
    "get_process_manager",
    # File Watcher
    "FileWatcher",
    "FileEvent",
    "FileEventType",
    "WatchConfig",
    "get_file_watcher",
    # Process Streamer
    "ProcessStreamer",
    "StreamConfig",
    "StreamLine",
    "get_process_streamer",
    # Git Commit Retrieval
    "GitCommitRetrieval",
    "GitRetrievalRequest",
    "GitRetrievalResult",
    "GitRetrievalStatus",
    "CommitInfo",
    "BlameLine",
    "BlameResult",
    "DiffResult",
    "get_git_commit_retrieval",
    # Task List Manager
    "TaskListManager",
    "Task",
    "TaskState",
    "TaskListSnapshot",
    "ReorganizeRequest",
    "ReorganizeResult",
    "TaskListValidationError",
    "get_tasklist_manager",
    "reset_tasklist_manager",
    # Browser Opener
    "BrowserOpener",
    "BrowserOpenRequest",
    "BrowserOpenResult",
    "BrowserOpenStatus",
    "get_browser_opener",
    "reset_browser_opener",
    # Terminal Reader
    "TerminalReader",
    "TerminalReadRequest",
    "TerminalReadResult",
    "TerminalReadStatus",
    "TerminalInfo",
    "TerminalState",
    "get_terminal_reader",
    "reset_terminal_reader",
    # Truncated Content
    "TruncatedContentManager",
    "ContentReference",
    "ViewRangeRequest",
    "ViewRangeResult",
    "SearchRequest",
    "SearchResult",
    "SearchMatch",
    "TruncatedContentStatus",
    "get_truncated_content_manager",
    "reset_truncated_content_manager"
]
