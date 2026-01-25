/**
 * ContextForge API Client
 * Handles all communication with the ContextForge backend
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000;

export interface ApiError {
  message: string;
  code?: string;
  status?: number;
}

export interface QueryRequest {
  query: string;
  max_tokens?: number;
  enable_web_search?: boolean;
  top_k?: number;
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

export interface ChatRequest {
  messages: ChatMessage[];
  conversation_id?: string;
  enable_context?: boolean;
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

class ApiClient {
  private baseUrl: string;
  private isOnline: boolean = true;
  private onlineListeners: Set<(online: boolean) => void> = new Set();
  private csrfToken: string | null = null;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
    this.startHealthCheck();
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

  private getHeaders(method: string = 'GET'): HeadersInit {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };

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

  // Query
  async query(request: QueryRequest): Promise<QueryResponse> {
    return this.request<QueryResponse>('/query', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Chat
  async chat(request: ChatRequest): Promise<ChatResponse> {
    return this.request<ChatResponse>('/chat', {
      method: 'POST',
      body: JSON.stringify(request),
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

  // Search
  async searchVector(query: string, topK = 10) {
    return this.request('/search/vector', {
      method: 'POST',
      body: JSON.stringify({ query, top_k: topK }),
    });
  }

  // File Upload
  async uploadFile(file: File): Promise<{ file_id: string; content: string }> {
    // Validate file type and size
    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'application/pdf', 'text/plain', 'text/markdown'];
    const maxSize = 50 * 1024 * 1024; // 50 MB

    if (!allowedTypes.includes(file.type)) {
      throw new Error(`File type not allowed: ${file.type}. Allowed types: ${allowedTypes.join(', ')}`);
    }

    if (file.size > maxSize) {
      throw new Error(`File too large: ${(file.size / 1024 / 1024).toFixed(2)} MB. Maximum size: 50 MB`);
    }

    const formData = new FormData();
    formData.append('file', file);

    const headers: HeadersInit = {};

    // Add CSRF token for file upload
    if (this.csrfToken) {
      headers['X-CSRF-Token'] = this.csrfToken;
    }

    const response = await fetch(`${this.baseUrl}/files/upload`, {
      method: 'POST',
      headers,
      credentials: 'include', // Include cookies for authentication
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.statusText}`);
    }
    return response.json();
  }

  isConnected(): boolean {
    return this.isOnline;
  }
}

export const apiClient = new ApiClient();
export default apiClient;

