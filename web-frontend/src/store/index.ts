import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ChatMessage, AgentStatus, HealthStatus, CodeContext } from '../api/client';

// Theme Store
interface ThemeState {
  isDark: boolean;
  toggle: () => void;
  setDark: (dark: boolean) => void;
}

export const useTheme = create<ThemeState>()(
  persist(
    (set) => ({
      isDark: window.matchMedia('(prefers-color-scheme: dark)').matches,
      toggle: () => set((state) => ({ isDark: !state.isDark })),
      setDark: (dark) => set({ isDark: dark }),
    }),
    { name: 'contextforge-theme' }
  )
);

// Connection Store
interface ConnectionState {
  isOnline: boolean;
  lastChecked: number | null;
  setOnline: (online: boolean) => void;
}

export const useConnection = create<ConnectionState>((set) => ({
  isOnline: true,
  lastChecked: null,
  setOnline: (online) => set({ isOnline: online, lastChecked: Date.now() }),
}));

// Chat Store
interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

interface ChatState {
  conversations: Conversation[];
  activeConversationId: string | null;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  createConversation: () => string;
  setActiveConversation: (id: string | null) => void;
  addMessage: (conversationId: string, message: ChatMessage) => void;
  updateConversationTitle: (id: string, title: string) => void;
  deleteConversation: (id: string) => void;
  clearHistory: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  getActiveConversation: () => Conversation | null;
}

export const useChat = create<ChatState>()(
  persist(
    (set, get) => ({
      conversations: [],
      activeConversationId: null,
      isLoading: false,
      error: null,
      
      createConversation: () => {
        const id = `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        const conversation: Conversation = {
          id,
          title: 'New Conversation',
          messages: [],
          createdAt: Date.now(),
          updatedAt: Date.now(),
        };
        set((state) => ({
          conversations: [conversation, ...state.conversations],
          activeConversationId: id,
        }));
        return id;
      },
      
      setActiveConversation: (id) => set({ activeConversationId: id }),
      
      addMessage: (conversationId, message) => set((state) => ({
        conversations: state.conversations.map((conv) =>
          conv.id === conversationId
            ? {
                ...conv,
                messages: [...conv.messages, { ...message, timestamp: Date.now() }],
                updatedAt: Date.now(),
                title: conv.messages.length === 0 && message.role === 'user' 
                  ? message.content.slice(0, 50) + (message.content.length > 50 ? '...' : '')
                  : conv.title,
              }
            : conv
        ),
      })),
      
      updateConversationTitle: (id, title) => set((state) => ({
        conversations: state.conversations.map((conv) =>
          conv.id === id ? { ...conv, title } : conv
        ),
      })),
      
      deleteConversation: (id) => set((state) => ({
        conversations: state.conversations.filter((conv) => conv.id !== id),
        activeConversationId: state.activeConversationId === id ? null : state.activeConversationId,
      })),
      
      clearHistory: () => set({ conversations: [], activeConversationId: null }),
      
      setLoading: (loading) => set({ isLoading: loading }),
      setError: (error) => set({ error }),
      
      getActiveConversation: () => {
        const state = get();
        return state.conversations.find((c) => c.id === state.activeConversationId) || null;
      },
    }),
    { name: 'contextforge-chat' }
  )
);

// Status Store
interface StatusState {
  health: HealthStatus | null;
  agents: AgentStatus | null;
  isLoading: boolean;
  setHealth: (health: HealthStatus | null) => void;
  setAgents: (agents: AgentStatus | null) => void;
  setLoading: (loading: boolean) => void;
}

export const useStatus = create<StatusState>((set) => ({
  health: null,
  agents: null,
  isLoading: false,
  setHealth: (health) => set({ health }),
  setAgents: (agents) => set({ agents }),
  setLoading: (loading) => set({ isLoading: loading }),
}));

// Query Results Store
interface QueryState {
  lastQuery: string | null;
  lastResult: { answer: string; contexts: CodeContext[] } | null;
  isLoading: boolean;
  error: string | null;
  setQuery: (query: string) => void;
  setResult: (result: { answer: string; contexts: CodeContext[] } | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useQuery = create<QueryState>((set) => ({
  lastQuery: null,
  lastResult: null,
  isLoading: false,
  error: null,
  setQuery: (query) => set({ lastQuery: query }),
  setResult: (result) => set({ lastResult: result }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}));

