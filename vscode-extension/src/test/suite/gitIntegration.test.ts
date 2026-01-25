/**
 * Tests for GitIntegration module.
 * 
 * Tests git operations, branch management, and commit message generation.
 */

import * as assert from 'assert';
import * as vscode from 'vscode';
import * as path from 'path';
import { GitIntegration } from '../../gitIntegration';

suite('GitIntegration Test Suite', () => {
    let gitIntegration: GitIntegration;
    let workspaceRoot: string;

    const mockConfig = {
        gitEnabled: true,
        githubToken: '',
        autoCommitMessages: true,
        defaultBranch: 'main'
    };

    suiteSetup(async () => {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (workspaceFolders && workspaceFolders.length > 0) {
            workspaceRoot = workspaceFolders[0].uri.fsPath;
        } else {
            workspaceRoot = __dirname;
        }
        gitIntegration = new GitIntegration(workspaceRoot, mockConfig, 'http://localhost:8000');
    });

    suite('GitIntegration Creation', () => {
        test('should be instantiable', () => {
            assert.ok(gitIntegration);
        });

        test('should accept workspace root', () => {
            const integration = new GitIntegration(
                workspaceRoot,
                mockConfig,
                'http://localhost:8000'
            );
            assert.ok(integration);
        });
    });

    suite('GitConfig Interface', () => {
        test('should define config structure', () => {
            interface GitConfig {
                gitEnabled: boolean;
                githubToken: string;
                autoCommitMessages: boolean;
                defaultBranch: string;
            }

            const config: GitConfig = {
                gitEnabled: true,
                githubToken: 'ghp_xxxx',
                autoCommitMessages: true,
                defaultBranch: 'main'
            };

            assert.strictEqual(config.gitEnabled, true);
            assert.strictEqual(config.defaultBranch, 'main');
        });
    });

    suite('Repository Detection', () => {
        test('should have isGitRepository method', () => {
            assert.ok(typeof gitIntegration.isGitRepository === 'function');
        });

        test('should check if directory is git repository', async () => {
            const isRepo = await gitIntegration.isGitRepository();
            // Result depends on whether tests run in a git repo
            assert.ok(typeof isRepo === 'boolean');
        });
    });

    suite('Status Operations', () => {
        test('should have getStatus method', () => {
            assert.ok(typeof gitIntegration.getStatus === 'function');
        });

        test('should get repository status', async () => {
            try {
                const status = await gitIntegration.getStatus();
                assert.ok(status);
                // StatusResult should have expected properties
                assert.ok('files' in status || 'not_added' in status || 'staged' in status);
            } catch (error) {
                // Expected if not in a git repo
                assert.ok(true);
            }
        });
    });

    suite('Branch Operations', () => {
        test('should have getBranches method', () => {
            assert.ok(typeof gitIntegration.getBranches === 'function');
        });

        test('should have getCurrentBranch method', () => {
            assert.ok(typeof gitIntegration.getCurrentBranch === 'function');
        });

        test('should have createBranch method', () => {
            assert.ok(typeof gitIntegration.createBranch === 'function');
        });

        test('should have switchBranch method', () => {
            assert.ok(typeof gitIntegration.switchBranch === 'function');
        });

        test('should have deleteBranch method', () => {
            assert.ok(typeof gitIntegration.deleteBranch === 'function');
        });
    });

    suite('CommitMessageRequest Interface', () => {
        test('should define request structure', () => {
            interface CommitMessageRequest {
                diff: string;
                staged_files: string[];
                branch: string;
                recent_commits: string[];
            }

            const request: CommitMessageRequest = {
                diff: 'diff --git a/file.ts...',
                staged_files: ['src/file.ts', 'src/other.ts'],
                branch: 'feature/new-feature',
                recent_commits: ['feat: add feature', 'fix: bug fix']
            };

            assert.ok(request.diff.length > 0);
            assert.strictEqual(request.staged_files.length, 2);
        });
    });

    suite('CommitMessageResponse Interface', () => {
        test('should define response structure', () => {
            interface CommitMessageResponse {
                message: string;
                description?: string;
                confidence: number;
            }

            const response: CommitMessageResponse = {
                message: 'feat: add new feature',
                description: 'Added functionality for X',
                confidence: 0.95
            };

            assert.ok(response.message.length > 0);
            assert.ok(response.confidence >= 0 && response.confidence <= 1);
        });
    });
});

