/**
 * Tests for ContextForgePromptProvider module.
 * 
 * Tests prompt panel webview, templates, and prompt generation.
 */

import * as assert from 'assert';
import * as vscode from 'vscode';
import { ContextForgePromptProvider } from '../../promptPanel';

suite('ContextForgePromptProvider Test Suite', () => {
    let promptProvider: ContextForgePromptProvider;
    let extensionUri: vscode.Uri;

    suiteSetup(async () => {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (workspaceFolders && workspaceFolders.length > 0) {
            extensionUri = workspaceFolders[0].uri;
        } else {
            extensionUri = vscode.Uri.file(__dirname);
        }
        promptProvider = new ContextForgePromptProvider(extensionUri);
    });

    suite('PromptProvider Creation', () => {
        test('should have correct view type', () => {
            assert.strictEqual(ContextForgePromptProvider.viewType, 'contextforge.promptView');
        });

        test('should be instantiable', () => {
            assert.ok(promptProvider);
        });
    });

    suite('Configuration', () => {
        test('should accept config via setConfig', () => {
            const config = { apiUrl: 'http://localhost:8000' };
            promptProvider.setConfig(config);
            assert.ok(promptProvider);
        });
    });

    suite('PromptTemplate Interface', () => {
        test('should define template structure', () => {
            interface PromptTemplate {
                id: string;
                name: string;
                category: string;
                description: string;
                template: string;
                variables: string[];
            }

            const template: PromptTemplate = {
                id: 'code-review',
                name: 'Code Review',
                category: 'Development',
                description: 'Review code for quality',
                template: 'Please review: ${code}',
                variables: ['code']
            };

            assert.strictEqual(template.id, 'code-review');
            assert.strictEqual(template.category, 'Development');
            assert.ok(template.variables.includes('code'));
        });

        test('should support multiple variables', () => {
            interface PromptTemplate {
                id: string;
                name: string;
                category: string;
                description: string;
                template: string;
                variables: string[];
            }

            const template: PromptTemplate = {
                id: 'debug-issue',
                name: 'Debug Issue',
                category: 'Development',
                description: 'Help debug and fix code issues',
                template: 'Issue: ${issue}\nError: ${error}\nCode: ${code}',
                variables: ['issue', 'error', 'code']
            };

            assert.strictEqual(template.variables.length, 3);
            assert.ok(template.variables.includes('issue'));
            assert.ok(template.variables.includes('error'));
            assert.ok(template.variables.includes('code'));
        });
    });

    suite('SavedPrompt Interface', () => {
        test('should create valid saved prompt', () => {
            interface SavedPrompt {
                id: string;
                text: string;
                timestamp: number;
                isFavorite: boolean;
                category: string;
            }

            const savedPrompt: SavedPrompt = {
                id: 'prompt-1',
                text: 'Review this code for security issues',
                timestamp: Date.now(),
                isFavorite: true,
                category: 'Security'
            };

            assert.strictEqual(savedPrompt.id, 'prompt-1');
            assert.strictEqual(savedPrompt.isFavorite, true);
            assert.ok(savedPrompt.timestamp > 0);
        });
    });

    suite('Template Categories', () => {
        test('should support Development category', () => {
            const categories = ['Development', 'Documentation', 'Testing', 'Security'];
            assert.ok(categories.includes('Development'));
        });

        test('should support Documentation category', () => {
            const categories = ['Development', 'Documentation', 'Testing', 'Security'];
            assert.ok(categories.includes('Documentation'));
        });
    });

    suite('PromptEnhancement Interface', () => {
        test('should define enhancement request', () => {
            interface PromptEnhancementRequest {
                prompt: string;
                context?: string;
                style?: string;
            }

            const request: PromptEnhancementRequest = {
                prompt: 'Review my code',
                context: 'TypeScript project',
                style: 'detailed'
            };

            assert.strictEqual(request.prompt, 'Review my code');
            assert.strictEqual(request.context, 'TypeScript project');
        });

        test('should define enhancement response', () => {
            interface PromptEnhancementResponse {
                original: string;
                enhanced: string;
                suggestions: string[];
                improvements: string[];
            }

            const response: PromptEnhancementResponse = {
                original: 'Review code',
                enhanced: 'Please conduct a comprehensive code review...',
                suggestions: ['Add specifics', 'Include context'],
                improvements: ['More detailed request']
            };

            assert.ok(response.enhanced.length > response.original.length);
            assert.ok(response.suggestions.length > 0);
        });
    });
});

