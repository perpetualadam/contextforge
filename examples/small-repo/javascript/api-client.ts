/**
 * API Client Module
 * 
 * TypeScript API client for communicating with the ContextForge Example API.
 * Provides type-safe methods for authentication, user management, and data access.
 */

// Type definitions
export interface User {
    id: number;
    username: string;
    email: string;
    role: 'admin' | 'user' | 'guest';
    created_at: string;
    last_login?: string;
    is_active: boolean;
}

export interface LoginRequest {
    username: string;
    password: string;
}

export interface LoginResponse {
    access_token: string;
    token_type: string;
    user_id: string;
    username: string;
    role: string;
    expires_in: number;
}

export interface UserCreateRequest {
    username: string;
    email: string;
    password: string;
    role?: 'admin' | 'user' | 'guest';
}

export interface UserUpdateRequest {
    email?: string;
    role?: 'admin' | 'user' | 'guest';
    is_active?: boolean;
}

export interface ApiError {
    error: string;
    detail: string;
    timestamp: string;
}

export interface ApiResponse<T> {
    data?: T;
    error?: ApiError;
    status: number;
}

/**
 * Configuration for the API client
 */
export interface ApiClientConfig {
    baseUrl: string;
    timeout?: number;
    defaultHeaders?: Record<string, string>;
}

/**
 * API Client class for ContextForge Example API
 */
export class ApiClient {
    private baseUrl: string;
    private timeout: number;
    private defaultHeaders: Record<string, string>;
    private accessToken: string | null = null;

    constructor(config: ApiClientConfig) {
        this.baseUrl = config.baseUrl.replace(/\/$/, ''); // Remove trailing slash
        this.timeout = config.timeout || 10000; // 10 seconds default
        this.defaultHeaders = {
            'Content-Type': 'application/json',
            ...config.defaultHeaders
        };
    }

    /**
     * Set the access token for authenticated requests
     */
    setAccessToken(token: string | null): void {
        this.accessToken = token;
    }

    /**
     * Get the current access token
     */
    getAccessToken(): string | null {
        return this.accessToken;
    }

    /**
     * Make an HTTP request with error handling
     */
    private async request<T>(
        endpoint: string,
        options: RequestInit = {}
    ): Promise<ApiResponse<T>> {
        const url = `${this.baseUrl}${endpoint}`;
        
        // Prepare headers
        const headers: Record<string, string> = {
            ...this.defaultHeaders,
            ...options.headers as Record<string, string>
        };

        // Add authorization header if token is available
        if (this.accessToken) {
            headers['Authorization'] = `Bearer ${this.accessToken}`;
        }

        // Prepare request options
        const requestOptions: RequestInit = {
            ...options,
            headers,
            signal: AbortSignal.timeout(this.timeout)
        };

        try {
            const response = await fetch(url, requestOptions);
            const data = await response.json();

            if (!response.ok) {
                return {
                    error: data,
                    status: response.status
                };
            }

            return {
                data,
                status: response.status
            };
        } catch (error) {
            if (error instanceof Error) {
                return {
                    error: {
                        error: 'Network Error',
                        detail: error.message,
                        timestamp: new Date().toISOString()
                    },
                    status: 0
                };
            }
            
            return {
                error: {
                    error: 'Unknown Error',
                    detail: 'An unexpected error occurred',
                    timestamp: new Date().toISOString()
                },
                status: 0
            };
        }
    }

    /**
     * GET request helper
     */
    private async get<T>(endpoint: string): Promise<ApiResponse<T>> {
        return this.request<T>(endpoint, { method: 'GET' });
    }

    /**
     * POST request helper
     */
    private async post<T>(endpoint: string, data?: any): Promise<ApiResponse<T>> {
        return this.request<T>(endpoint, {
            method: 'POST',
            body: data ? JSON.stringify(data) : undefined
        });
    }

    /**
     * PUT request helper
     */
    private async put<T>(endpoint: string, data?: any): Promise<ApiResponse<T>> {
        return this.request<T>(endpoint, {
            method: 'PUT',
            body: data ? JSON.stringify(data) : undefined
        });
    }

    /**
     * DELETE request helper
     */
    private async delete<T>(endpoint: string): Promise<ApiResponse<T>> {
        return this.request<T>(endpoint, { method: 'DELETE' });
    }

    // Authentication methods

    /**
     * Login with username and password
     */
    async login(credentials: LoginRequest): Promise<ApiResponse<LoginResponse>> {
        const response = await this.post<LoginResponse>('/auth/login', credentials);
        
        if (response.data) {
            this.setAccessToken(response.data.access_token);
        }
        
        return response;
    }

    /**
     * Logout and clear access token
     */
    logout(): void {
        this.setAccessToken(null);
    }

    /**
     * Get current user information
     */
    async getCurrentUser(): Promise<ApiResponse<User>> {
        return this.get<User>('/auth/me');
    }

    // User management methods

    /**
     * Get list of users (admin only)
     */
    async getUsers(skip: number = 0, limit: number = 100): Promise<ApiResponse<User[]>> {
        return this.get<User[]>(`/users?skip=${skip}&limit=${limit}`);
    }

    /**
     * Create a new user (admin only)
     */
    async createUser(userData: UserCreateRequest): Promise<ApiResponse<User>> {
        return this.post<User>('/users', userData);
    }

    /**
     * Update a user (admin only)
     */
    async updateUser(userId: number, userData: UserUpdateRequest): Promise<ApiResponse<User>> {
        return this.put<User>(`/users/${userId}`, userData);
    }

    /**
     * Delete a user (admin only)
     */
    async deleteUser(userId: number): Promise<ApiResponse<void>> {
        return this.delete<void>(`/users/${userId}`);
    }

    // Utility methods

    /**
     * Check API health
     */
    async healthCheck(): Promise<ApiResponse<{ status: string; timestamp: string; service: string; database: string }>> {
        return this.get('/health');
    }

    /**
     * Get API information
     */
    async getApiInfo(): Promise<ApiResponse<{ message: string; version: string; docs: string; health: string }>> {
        return this.get('/');
    }
}

/**
 * Create a configured API client instance
 */
export function createApiClient(baseUrl: string, config?: Partial<ApiClientConfig>): ApiClient {
    return new ApiClient({
        baseUrl,
        timeout: 10000,
        ...config
    });
}

/**
 * Default API client instance
 */
export const apiClient = createApiClient('http://localhost:8000');

/**
 * Authentication helper functions
 */
export class AuthService {
    private static readonly TOKEN_KEY = 'contextforge_access_token';
    private static readonly USER_KEY = 'contextforge_current_user';

    /**
     * Save authentication data to localStorage
     */
    static saveAuth(loginResponse: LoginResponse, user: User): void {
        localStorage.setItem(this.TOKEN_KEY, loginResponse.access_token);
        localStorage.setItem(this.USER_KEY, JSON.stringify(user));
        apiClient.setAccessToken(loginResponse.access_token);
    }

    /**
     * Load authentication data from localStorage
     */
    static loadAuth(): { token: string | null; user: User | null } {
        const token = localStorage.getItem(this.TOKEN_KEY);
        const userJson = localStorage.getItem(this.USER_KEY);
        
        let user: User | null = null;
        if (userJson) {
            try {
                user = JSON.parse(userJson);
            } catch (error) {
                console.warn('Failed to parse stored user data:', error);
            }
        }

        if (token) {
            apiClient.setAccessToken(token);
        }

        return { token, user };
    }

    /**
     * Clear authentication data
     */
    static clearAuth(): void {
        localStorage.removeItem(this.TOKEN_KEY);
        localStorage.removeItem(this.USER_KEY);
        apiClient.setAccessToken(null);
    }

    /**
     * Check if user is authenticated
     */
    static isAuthenticated(): boolean {
        return !!localStorage.getItem(this.TOKEN_KEY);
    }

    /**
     * Get current user from localStorage
     */
    static getCurrentUser(): User | null {
        const userJson = localStorage.getItem(this.USER_KEY);
        if (userJson) {
            try {
                return JSON.parse(userJson);
            } catch (error) {
                console.warn('Failed to parse stored user data:', error);
            }
        }
        return null;
    }

    /**
     * Check if current user has admin role
     */
    static isAdmin(): boolean {
        const user = this.getCurrentUser();
        return user?.role === 'admin';
    }
}

/**
 * Error handling utilities
 */
export class ApiErrorHandler {
    /**
     * Handle API response and throw error if needed
     */
    static handleResponse<T>(response: ApiResponse<T>): T {
        if (response.error) {
            throw new Error(response.error.detail || response.error.error);
        }
        
        if (!response.data) {
            throw new Error('No data received from API');
        }
        
        return response.data;
    }

    /**
     * Check if error is authentication related
     */
    static isAuthError(error: ApiError): boolean {
        return error.error === 'Unauthorized' || error.detail.includes('token');
    }

    /**
     * Check if error is authorization related
     */
    static isAuthzError(error: ApiError): boolean {
        return error.error === 'Forbidden' || error.detail.includes('Access denied');
    }
}

// Initialize authentication on module load
AuthService.loadAuth();
