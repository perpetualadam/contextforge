/**
 * ContextForge API Client
 * Handles all communication with the ContextForge backend
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';
const API_KEY_STORAGE = 'contextforge_api_key';
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000;

export interface ApiError {
  message: string;
  code?: string;
  status?: number;
}

export interface EditorContext {
  current_file?: string;
  current_selection?: string;
  cursor_line?: number;
  open_files?: string[];
  recent_files?: string[];
  git_diff?: string;
}

export interface QueryRequest {
  query: string;
  max_tokens?: number;
  enable_web_search?: boolean;
  top_k?: number;
  task_scope?: string;
  editor_context?: EditorContext;
  project_rules?: string;
  privacy_mode?: boolean;
  auto_terminal_mode?: boolean;
  auto_terminal_timeout?: number;
}

export interface QueryResponse {
  answer: string;
  contexts: CodeContext[];
  web_results?: WebResult[];
  latency_ms: number;
}

export interface CodeContext {
  content: string;
  source: string;
  line_start?: number;
  line_end?: number;
  score: number;
  language?: string;
}

export interface WebResult {
  title: string;
  url: string;
  snippet: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: number;
}

export interface Attachment {
  name: string;
  type: string;
  data?: string;
  extracted_text?: string;
}

export interface ChatRequest {
  messages: ChatMessage[];
  /** Local-only id for UI; stripped before POST (not in gateway schema). */
  conversation_id?: string;
  enable_context?: boolean;
  max_tokens?: number;
  enable_web_search?: boolean;
  provider?: string;
  editor_context?: EditorContext;
  attachments?: Attachment[];
  resolved_mentions?: string;
  project_rules?: string;
  privacy_mode?: boolean;
}

export interface CompletionRequest {
  prefix: string;
  suffix?: string;
  language?: string;
  file_path?: string;
  max_tokens?: number;
  privacy_mode?: boolean;
}

export interface CompletionResponse {
  completion: string;
  model: string;
  latency_ms: number;
}

export interface InlineEditRequest {
  code: string;
  instruction: string;
  language?: string;
  file_path?: string;
  context_before?: string;
  context_after?: string;
  project_rules?: string;
  privacy_mode?: boolean;
}

export interface InlineEditResponse {
  edited_code: string;
  explanation: string;
  model: string;
}

export interface AgentExecuteRequest {
  task: string;
  repo_path: string;
  mode?: string;
  project_rules?: string;
  privacy_mode?: boolean;
  dry_run?: boolean;
}

export interface FileChange {
  path: string;
  diff: string;
  newContent: string;
  action: string;
}

export interface AgentExecuteResponse {
  changes: FileChange[];
  plan: string;
  status: string;
}

export interface SmartApplyRequest {
  file_path: string;
  file_content: string;
  code_block: string;
  language?: string;
}

export interface SmartApplyResponse {
  start_line: number;
  end_line: number;
  replacement: string;
  new_content: string;
  confidence: number;
}

export interface SymbolLookupRequest {
  symbol: string;
  file_path?: string;
  line?: number;
  kind?: 'definition' | 'references';
}

export interface ComposerStartRequest {
  task: string;
  repo_path: string;
  project_rules?: string;
  privacy_mode?: boolean;
}

export interface MultiCursorEditRequest {
  file_content: string;
  instruction: string;
  language?: string;
  file_path?: string;
}

export interface EditLocation {
  start_line: number;
  start_col: number;
  end_line: number;
  end_col: number;
  new_text: string;
}

export interface MultiCursorEditResponse {
  edits: EditLocation[];
}

export interface TerminalExecuteRequest {
  command: string;
  working_directory?: string;
  timeout?: number;
}

export interface TerminalSuggestRequest {
  task_description: string;
  context?: string;
  working_directory?: string;
}

export type GitRepoOperation =
  | 'status'
  | 'branch'
  | 'log'
  | 'diff'
  | 'diff_staged'
  | 'remote'
  | 'head'
  | 'stash_list';

export interface GitRepoCommandRequest {
  repo_path: string;
  operation: GitRepoOperation;
  log_limit?: number;
  timeout?: number;
}

/** Response shape from terminal executor (forwarded by gateway). */
export interface GitCommandTerminalResult {
  command: string;
  exit_code: number;
  stdout: string;
  stderr: string;
  execution_time: number;
  working_directory: string;
}

export interface CommitMessageGenerateRequest {
  diff: string;
  staged_files: string[];
  branch: string;
  recent_commits: string[];
}

export interface CommitMessageGenerateResponse {
  message: string;
  description?: string;
  confidence: number;
}

export interface PromptEnhancementRequest {
  prompt: string;
  context?: string;
  style?: string;
}

export interface PromptEnhancementResponse {
  original: string;
  enhanced: string;
  suggestions: string[];
  improvements: string[];
}

export interface PromptContextEnhanceRequest {
  prompt: string;
  context?: string;
  task_type?: string;
  code?: string;
  file_path?: string;
  include_embeddings?: boolean;
  include_git?: boolean;
  include_tests?: boolean;
  max_tokens?: number;
}

export interface PromptContextEnhanceResponse {
  original: string;
  enhanced: string;
  context_sections: string[];
  estimated_tokens: number;
  task_type: string;
}

export interface ChatResponse {
  response: string;
  conversation_id: string;
  contexts?: CodeContext[];
}

export interface IngestRequest {
  path: string;
  recursive?: boolean;
  file_patterns?: string[];
}

export interface IngestResponse {
  status: string;
  files_indexed: number;
  chunks_created: number;
  duration_ms: number;
}

export interface AgentInfo {
  name: string;
  execution_hint: 'local' | 'remote' | 'hybrid';
  resolved_location: 'local' | 'remote';
  capabilities: {
    consumes: string[];
    produces: string[];
    requires_filesystem: boolean;
    requires_network: boolean;
  };
}

export interface AgentStatus {
  agents: Record<string, AgentInfo>;
  total_agents: number;
  local_agents: number;
  remote_agents: number;
  llm_mode: 'online' | 'offline';
}

export interface HealthStatus {
  status: string;
  services: Record<string, { status: string; latency_ms?: number }>;
  version?: string;
}

/** GET /github/status — future server-side GitHub API (token on gateway only). */
export interface GitHubServerStatus {
  github_server_configured: boolean;
  github_server_disabled: boolean;
  implementation: string;
  planned_capabilities: string[];
  client_hint: string;
}

class ApiClient {
  private baseUrl: string;
  private isOnline: boolean = true;
  private onlineListeners: Set<(online: boolean) => void> = new Set();
  private csrfToken: string | null = null;
  private apiKey: string | null = null;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
    try {
      if (typeof localStorage !== 'undefined') {
        this.apiKey = localStorage.getItem(API_KEY_STORAGE);
      }
    } catch {
      /* ignore */
    }
    this.startHealthCheck();
  }

  /**
   * Optional gateway API key (`Authorization: Bearer`), persisted in `localStorage`.
   * Same-origin pages can read it; do not treat as a secret against XSS—use only on trusted networks or with gateway auth you accept for your threat model.
   */
  getApiKey(): string | null {
    return this.apiKey;
  }

  setApiKey(key: string | null): void {
    this.apiKey = key?.trim() ? key.trim() : null;
    try {
      if (typeof localStorage !== 'undefined') {
        if (this.apiKey) {
          localStorage.setItem(API_KEY_STORAGE, this.apiKey);
        } else {
          localStorage.removeItem(API_KEY_STORAGE);
        }
      }
    } catch {
      /* ignore */
    }
  }

  /**
   * Set CSRF token for state-changing requests
   */
  setCSRFToken(token: string | null) {
    this.csrfToken = token;
  }

  /**
   * Get CSRF token
   */
  getCSRFToken(): string | null {
    return this.csrfToken;
  }

  onConnectionChange(listener: (online: boolean) => void) {
    this.onlineListeners.add(listener);
    return () => this.onlineListeners.delete(listener);
  }

  private notifyConnectionChange(online: boolean) {
    if (this.isOnline !== online) {
      this.isOnline = online;
      this.onlineListeners.forEach(listener => listener(online));
    }
  }

  private async startHealthCheck() {
    const check = async () => {
      try {
        const response = await fetch(`${this.baseUrl}/health`, { 
          method: 'GET',
          signal: AbortSignal.timeout(5000)
        });
        this.notifyConnectionChange(response.ok);
      } catch {
        this.notifyConnectionChange(false);
      }
    };
    
    check();
    setInterval(check, 30000); // Check every 30 seconds
  }

  private getHeaders(method: string = 'GET'): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (this.apiKey) {
      headers['Authorization'] = `Bearer ${this.apiKey}`;
    }

    // Add CSRF token for state-changing requests
    if (this.csrfToken && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
      headers['X-CSRF-Token'] = this.csrfToken;
    }

    return headers;
  }
  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    retries = MAX_RETRIES
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const method = options.method || 'GET';

    try {
      const response = await fetch(url, {
        ...options,
        headers: { ...this.getHeaders(method), ...options.headers },
        credentials: 'include', // Always include cookies for authentication
      });

      if (!response.ok) {
        const error: ApiError = {
          message: `HTTP ${response.status}: ${response.statusText}`,
          status: response.status,
        };
        try {
          const body = await response.json();
          error.message = body.detail || body.message || error.message;
          error.code = body.code;
        } catch { /* ignore parse errors */ }

        // Handle authentication errors
        if (response.status === 401) {
          error.message = 'Authentication required. Please login.';
        } else if (response.status === 403) {
          error.message = 'Access forbidden. You do not have permission.';
        }

        throw error;
      }

      this.notifyConnectionChange(true);
      return await response.json();
    } catch (err) {
      if (err instanceof TypeError && err.message.includes('fetch')) {
        this.notifyConnectionChange(false);
        if (retries > 0) {
          await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
          return this.request<T>(endpoint, options, retries - 1);
        }
      }
      throw err;
    }
  }

  // Health & Status
  async getHealth(): Promise<HealthStatus> {
    return this.request<HealthStatus>('/health');
  }

  async getAgentStatus(): Promise<AgentStatus> {
    return this.request<AgentStatus>('/agents/status');
  }

  async getConfig(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/config');
  }

  /** Reserved for future server-side GitHub (PRs/issues); token lives on API host only. */
  async getGitHubServerStatus(): Promise<GitHubServerStatus> {
    return this.request<GitHubServerStatus>('/github/status');
  }

  // Query
  async query(request: QueryRequest): Promise<QueryResponse> {
    return this.request<QueryResponse>('/query', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Chat
  async chat(request: ChatRequest): Promise<ChatResponse> {
    const { conversation_id, ...body } = request;
    void conversation_id;
    return this.request<ChatResponse>('/chat', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  // Ingestion
  async ingest(request: IngestRequest): Promise<IngestResponse> {
    return this.request<IngestResponse>('/ingest', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getIngestStatus(): Promise<{ files: number; chunks: number }> {
    return this.request('/ingest/status');
  }

  // Orchestration
  async orchestrate(repoPath: string, mode = 'auto', task = 'full_analysis') {
    return this.request('/orchestrate', {
      method: 'POST',
      body: JSON.stringify({
        repo_path: repoPath,
        mode,
        task,
        output_format: 'markdown',
      }),
    });
  }

  // Git (server-side repo on gateway host; whitelist commands via /git/repo-command)
  async gitRepoCommand(request: GitRepoCommandRequest): Promise<GitCommandTerminalResult> {
    return this.request<GitCommandTerminalResult>('/git/repo-command', {
      method: 'POST',
      body: JSON.stringify({
        repo_path: request.repo_path,
        operation: request.operation,
        log_limit: request.log_limit ?? 20,
        timeout: request.timeout ?? 60,
      }),
    });
  }

  async generateCommitMessage(
    request: CommitMessageGenerateRequest
  ): Promise<CommitMessageGenerateResponse> {
    return this.request<CommitMessageGenerateResponse>('/git/commit-message', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Search
  async searchVector(query: string, topK = 10) {
    return this.request('/search/vector', {
      method: 'POST',
      body: JSON.stringify({ query, top_k: topK }),
    });
  }

  // File Upload (gateway extracts text / images; any type up to server MAX_FILE_SIZE_MB)
  async uploadFile(file: File): Promise<{
    id: string;
    name: string;
    type: string;
    data: string;
    extractedText?: string | null;
  }> {
    const maxSize = 50 * 1024 * 1024;
    if (file.size > maxSize) {
      throw new Error(`File too large: ${(file.size / 1024 / 1024).toFixed(2)} MB. Maximum size: 50 MB`);
    }

    const formData = new FormData();
    formData.append('file', file);

    const headers: Record<string, string> = {};

    if (this.apiKey) {
      headers['Authorization'] = `Bearer ${this.apiKey}`;
    }

    if (this.csrfToken) {
      headers['X-CSRF-Token'] = this.csrfToken;
    }

    const response = await fetch(`${this.baseUrl}/files/upload`, {
      method: 'POST',
      headers,
      credentials: 'include',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.statusText}`);
    }
    const j = (await response.json()) as {
      id: string;
      name: string;
      type: string;
      data: string;
      extractedText?: string | null;
      extracted_text?: string | null;
    };
    return {
      id: j.id,
      name: j.name,
      type: j.type,
      data: j.data,
      extractedText: j.extractedText ?? j.extracted_text ?? undefined,
    };
  }

  // Inline Completion (#1)
  async completion(request: CompletionRequest): Promise<CompletionResponse> {
    return this.request<CompletionResponse>('/completion', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Inline Edit (#2)
  async inlineEdit(request: InlineEditRequest): Promise<InlineEditResponse> {
    return this.request<InlineEditResponse>('/inline-edit', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Agent Mode (#3)
  async agentExecute(request: AgentExecuteRequest): Promise<AgentExecuteResponse> {
    return this.request<AgentExecuteResponse>('/agent/execute', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Smart Apply (#10)
  async smartApply(request: SmartApplyRequest): Promise<SmartApplyResponse> {
    return this.request<SmartApplyResponse>('/smart-apply', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Symbol Lookup (#14)
  async symbolLookup(request: SymbolLookupRequest) {
    return this.request('/symbols/lookup', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Docs Index (#8)
  async indexDocs(url: string, label?: string) {
    return this.request('/docs/index', {
      method: 'POST',
      body: JSON.stringify({ url, label: label || url, recursive: true }),
    });
  }

  // Docs Search (#8)
  async searchDocs(query: string, topK = 5) {
    return this.request('/docs/search', {
      method: 'POST',
      body: JSON.stringify({ query, top_k: topK }),
    });
  }

  // Composer (#20)
  async composerStart(request: ComposerStartRequest) {
    return this.request('/composer/start', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async composerStatus(sessionId: string) {
    return this.request(`/composer/status/${sessionId}`);
  }

  async multiCursorEdit(request: MultiCursorEditRequest): Promise<MultiCursorEditResponse> {
    return this.request<MultiCursorEditResponse>('/multi-cursor-edit', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async terminalExecute(request: TerminalExecuteRequest): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/terminal/execute', {
      method: 'POST',
      body: JSON.stringify({
        command: request.command,
        working_directory: request.working_directory,
        timeout: request.timeout ?? 60,
        stream: false,
      }),
    });
  }

  async terminalSuggest(request: TerminalSuggestRequest): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/terminal/suggest', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async promptEnhance(request: PromptEnhancementRequest): Promise<PromptEnhancementResponse> {
    return this.request<PromptEnhancementResponse>('/prompts/enhance', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async promptContextEnhance(request: PromptContextEnhanceRequest): Promise<PromptContextEnhanceResponse> {
    return this.request<PromptContextEnhanceResponse>('/prompts/context-enhance', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  isConnected(): boolean {
    return this.isOnline;
  }
}

export const apiClient = new ApiClient();
export default apiClient;

