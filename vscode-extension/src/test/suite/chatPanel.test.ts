/**
 * Tests for ContextForgeChatProvider module.
 * 
 * Tests chat panel webview, message handling, and file attachments.
 */

import * as assert from 'assert';
import * as vscode from 'vscode';
import { ContextForgeChatProvider } from '../../chatPanel';

suite('ContextForgeChatProvider Test Suite', () => {
    let chatProvider: ContextForgeChatProvider;
    let extensionUri: vscode.Uri;

    const mockConfig = {
        apiUrl: 'http://localhost:8000',
        autoIngest: false,
        maxResults: 5,
        enableWebSearch: false,
        showLineNumbers: true,
        autoTerminalMode: false,
        autoTerminalTimeout: 30,
        autoTerminalWhitelist: [],
        chatHistoryEnabled: true,
        chatMaxHistory: 10,
        fileAttachmentsEnabled: true,
        maxFileSize: 10485760,
        allowedFileTypes: ['.txt', '.py', '.js', '.ts']
    };

    suiteSetup(async () => {
        // Get the extension URI from the workspace
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (workspaceFolders && workspaceFolders.length > 0) {
            extensionUri = workspaceFolders[0].uri;
        } else {
            extensionUri = vscode.Uri.file(__dirname);
        }
        chatProvider = new ContextForgeChatProvider(extensionUri, mockConfig);
    });

    suite('ChatProvider Creation', () => {
        test('should have correct view type', () => {
            assert.strictEqual(ContextForgeChatProvider.viewType, 'contextforge.chatView');
        });

        test('should be instantiable', () => {
            assert.ok(chatProvider);
        });
    });

    suite('Configuration', () => {
        test('should update configuration', () => {
            const newConfig = { ...mockConfig, apiUrl: 'http://newurl:9000' };
            chatProvider.updateConfig(newConfig);
            // Provider should accept new config without error
            assert.ok(chatProvider);
        });

        test('should handle chat history setting', () => {
            const configWithHistoryDisabled = { ...mockConfig, chatHistoryEnabled: false };
            const provider = new ContextForgeChatProvider(extensionUri, configWithHistoryDisabled);
            assert.ok(provider);
        });
    });

    suite('File Attachment Types', () => {
        test('should define FileAttachment interface structure', () => {
            interface FileAttachment {
                id: string;
                name: string;
                type: string;
                size: number;
                data: string;
                extractedText?: string;
                analysisResult?: string;
            }

            const attachment: FileAttachment = {
                id: 'test-123',
                name: 'test.txt',
                type: 'text/plain',
                size: 1024,
                data: 'base64encodeddata'
            };

            assert.strictEqual(attachment.id, 'test-123');
            assert.strictEqual(attachment.name, 'test.txt');
            assert.strictEqual(attachment.type, 'text/plain');
            assert.strictEqual(attachment.size, 1024);
            assert.ok(!attachment.extractedText);
        });
    });

    suite('ChatMessage Interface', () => {
        test('should support user role', () => {
            interface ChatMessage {
                id: string;
                role: 'user' | 'assistant';
                content: string;
                timestamp: Date;
                isMarkdown?: boolean;
            }

            const userMessage: ChatMessage = {
                id: 'msg-1',
                role: 'user',
                content: 'Hello world',
                timestamp: new Date()
            };

            assert.strictEqual(userMessage.role, 'user');
        });

        test('should support assistant role', () => {
            interface ChatMessage {
                id: string;
                role: 'user' | 'assistant';
                content: string;
                timestamp: Date;
                isMarkdown?: boolean;
            }

            const assistantMessage: ChatMessage = {
                id: 'msg-2',
                role: 'assistant',
                content: 'Hello! How can I help?',
                timestamp: new Date(),
                isMarkdown: true
            };

            assert.strictEqual(assistantMessage.role, 'assistant');
            assert.strictEqual(assistantMessage.isMarkdown, true);
        });
    });

    suite('ChatSession Interface', () => {
        test('should create valid session object', () => {
            interface ChatSession {
                id: string;
                messages: Array<{ id: string; role: string; content: string }>;
                title: string;
                createdAt: Date;
                updatedAt: Date;
            }

            const session: ChatSession = {
                id: 'session-1',
                messages: [],
                title: 'New Chat',
                createdAt: new Date(),
                updatedAt: new Date()
            };

            assert.strictEqual(session.id, 'session-1');
            assert.strictEqual(session.title, 'New Chat');
            assert.ok(Array.isArray(session.messages));
        });
    });
});

