import { useState, useRef, useEffect } from 'react';
import { Send, Plus, Trash2, User, Bot, Paperclip, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { clsx } from 'clsx';
import { Button, LoadingDots, CodeBlock } from '../components/ui';
import { useChat, useConnection, useWorkspace, buildEditorContext, clampTokens } from '../store';
import apiClient, { ChatMessage, Attachment } from '../api/client';

export function ChatPage() {
  const [input, setInput] = useState('');
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { isOnline } = useConnection();
  const {
    projectRules,
    privacyMode,
    chatMaxTokens,
    chatWebSearch,
    llmProvider,
    contextCurrentFile,
    contextSelection,
    contextCursorLine,
    contextOpenFiles,
    contextGitDiff,
  } = useWorkspace();

  const {
    conversations,
    activeConversationId,
    isLoading,
    error,
    createConversation,
    setActiveConversation,
    addMessage,
    deleteConversation,
    setLoading,
    setError,
    getActiveConversation,
  } = useChat();

  const activeConversation = getActiveConversation();

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeConversation?.messages]);

  // Focus input on load
  useEffect(() => {
    inputRef.current?.focus();
  }, [activeConversationId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if ((!input.trim() && attachments.length === 0) || isLoading) return;

    const message = input.trim() || (attachments.length ? 'See attached files.' : '');
    setInput('');
    setError(null);

    // Create new conversation if none active
    let conversationId = activeConversationId;
    if (!conversationId) {
      conversationId = createConversation();
    }

    // Add user message
    const userMessage: ChatMessage = { role: 'user', content: message };
    addMessage(conversationId, userMessage);

    // Get current messages for context
    const conv = conversations.find(c => c.id === conversationId);
    const messages = conv ? [...conv.messages, userMessage] : [userMessage];

    setLoading(true);
    try {
      const editor_context = buildEditorContext({
        contextCurrentFile,
        contextSelection,
        contextCursorLine,
        contextOpenFiles,
        contextGitDiff,
      });

      const response = await apiClient.chat({
        messages: messages.map(m => ({ role: m.role, content: m.content })),
        conversation_id: conversationId,
        enable_context: true,
        max_tokens: clampTokens(chatMaxTokens),
        enable_web_search: chatWebSearch,
        ...(llmProvider.trim() ? { provider: llmProvider.trim() } : {}),
        ...(editor_context ? { editor_context } : {}),
        ...(attachments.length ? { attachments } : {}),
        ...(projectRules.trim() ? { project_rules: projectRules.trim() } : {}),
        privacy_mode: privacyMode,
      });

      setAttachments([]);

      addMessage(conversationId, {
        role: 'assistant',
        content: response.response,
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to get response';
      setError(errorMessage);
      addMessage(conversationId, {
        role: 'assistant',
        content: `Error: ${errorMessage}. Please try again.`,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleFilePick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files?.length) return;
    setError(null);
    for (const file of Array.from(files)) {
      try {
        const up = await apiClient.uploadFile(file);
        const att: Attachment = {
          name: up.name,
          type: up.type,
          data: up.type.startsWith('image/') ? up.data : undefined,
          extracted_text: up.extractedText || undefined,
        };
        setAttachments((prev) => [...prev, att]);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Upload failed');
      }
    }
    e.target.value = '';
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex h-screen">
      {/* Conversation List - Hidden on mobile */}
      <div className="hidden md:flex w-64 flex-col bg-gray-100 dark:bg-gray-850 border-r border-gray-200 dark:border-gray-700">
        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
          <Button 
            onClick={() => { createConversation(); }}
            className="w-full"
            variant="primary"
          >
            <Plus className="w-4 h-4 mr-2" />
            New Chat
          </Button>
        </div>
        
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {conversations.map((conv) => (
            <button
              key={conv.id}
              onClick={() => setActiveConversation(conv.id)}
              className={clsx(
                'w-full text-left px-3 py-2 rounded-lg transition-colors group',
                conv.id === activeConversationId
                  ? 'bg-primary-100 dark:bg-primary-900/40 text-primary-700 dark:text-primary-300'
                  : 'hover:bg-gray-200 dark:hover:bg-gray-700'
              )}
            >
              <div className="flex items-center justify-between">
                <span className="truncate text-sm">{conv.title}</span>
                <button
                  onClick={(e) => { e.stopPropagation(); deleteConversation(conv.id); }}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-all"
                  aria-label="Delete conversation"
                >
                  <Trash2 className="w-3 h-3 text-red-500" />
                </button>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {!activeConversation && (
            <EmptyState onNewChat={createConversation} />
          )}
          
          {activeConversation?.messages.map((msg, idx) => (
            <MessageBubble key={idx} message={msg} />
          ))}
          
          {isLoading && (
            <div className="flex items-start gap-3 p-4">
              <div className="w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center">
                <Bot className="w-5 h-5 text-primary-600 dark:text-primary-400" />
              </div>
              <div className="bg-gray-100 dark:bg-gray-800 rounded-2xl px-4 py-3">
                <LoadingDots />
              </div>
            </div>
          )}
          
          {error && (
            <div className="text-center text-red-500 text-sm py-2" role="alert">
              {error}
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="border-t border-gray-200 dark:border-gray-700 p-4">
          {!isOnline && (
            <div className="text-yellow-600 text-sm mb-2 text-center">
              You are offline. Messages will be sent when connection is restored.
            </div>
          )}
          
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFilePick}
            aria-label="Attach files"
          />
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2">
              {attachments.map((a, i) => (
                <span
                  key={`${a.name}-${i}`}
                  className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-200"
                >
                  {a.name}
                  <button
                    type="button"
                    className="p-0.5 rounded hover:bg-gray-300 dark:hover:bg-gray-600"
                    onClick={() => setAttachments((prev) => prev.filter((_, j) => j !== i))}
                    aria-label={`Remove ${a.name}`}
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          )}
          <form onSubmit={handleSubmit} className="flex gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
              className="flex-1 input resize-none"
              rows={2}
              disabled={isLoading}
              aria-label="Chat message input"
            />
            <Button
              type="button"
              variant="secondary"
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading || !isOnline}
              aria-label="Attach file"
            >
              <Paperclip className="w-5 h-5" />
            </Button>
            <Button
              type="submit"
              disabled={(!input.trim() && attachments.length === 0) || isLoading}
              aria-label="Send message"
            >
              <Send className="w-5 h-5" />
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}

// Message Bubble Component
function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';

  return (
    <div className={clsx('flex items-start gap-3 message-enter', isUser && 'flex-row-reverse')}>
      <div className={clsx(
        'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
        isUser
          ? 'bg-gray-200 dark:bg-gray-700'
          : 'bg-primary-100 dark:bg-primary-900'
      )}>
        {isUser ? (
          <User className="w-5 h-5 text-gray-600 dark:text-gray-400" />
        ) : (
          <Bot className="w-5 h-5 text-primary-600 dark:text-primary-400" />
        )}
      </div>

      <div className={clsx(
        'max-w-[70%] rounded-2xl px-4 py-3',
        isUser
          ? 'bg-primary-600 text-white'
          : 'bg-gray-100 dark:bg-gray-800'
      )}>
        <div className={clsx(
          'prose prose-sm max-w-none',
          isUser ? 'prose-invert' : 'dark:prose-invert'
        )}>
          <ReactMarkdown
            components={{
              code({ className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || '');
                const isBlock = String(children).includes('\n');
                if (isBlock && match) {
                  return (
                    <CodeBlock
                      code={String(children)}
                      language={match[1]}
                    />
                  );
                }
                return (
                  <code className={className} {...props}>
                    {children}
                  </code>
                );
              },
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

// Empty State Component
function EmptyState({ onNewChat }: { onNewChat: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-4">
      <div className="w-20 h-20 bg-primary-100 dark:bg-primary-900 rounded-full flex items-center justify-center mb-6">
        <Bot className="w-10 h-10 text-primary-600 dark:text-primary-400" />
      </div>
      <h2 className="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-2">
        Welcome to ContextForge
      </h2>
      <p className="text-gray-500 dark:text-gray-400 mb-6 max-w-md">
        Start a conversation to ask questions about your codebase, get explanations,
        or explore your project's architecture.
      </p>
      <Button onClick={onNewChat}>
        <Plus className="w-4 h-4 mr-2" />
        Start New Chat
      </Button>
    </div>
  );
}

