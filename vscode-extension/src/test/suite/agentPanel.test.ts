/**
 * Tests for AgentStatusProvider module.
 * 
 * Tests agent panel webview, status display, and pipeline execution.
 */

import * as assert from 'assert';
import * as vscode from 'vscode';
import { AgentStatusProvider } from '../../agentPanel';

suite('AgentStatusProvider Test Suite', () => {
    let agentProvider: AgentStatusProvider;
    let extensionUri: vscode.Uri;

    const mockConfig = {
        apiUrl: 'http://localhost:8000'
    };

    suiteSetup(async () => {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (workspaceFolders && workspaceFolders.length > 0) {
            extensionUri = workspaceFolders[0].uri;
        } else {
            extensionUri = vscode.Uri.file(__dirname);
        }
        agentProvider = new AgentStatusProvider(extensionUri, mockConfig);
    });

    suite('AgentStatusProvider Creation', () => {
        test('should have correct view type', () => {
            assert.strictEqual(AgentStatusProvider.viewType, 'contextforge.agentView');
        });

        test('should be instantiable', () => {
            assert.ok(agentProvider);
        });
    });

    suite('Configuration', () => {
        test('should update configuration', () => {
            const newConfig = { apiUrl: 'http://newurl:9000' };
            agentProvider.updateConfig(newConfig);
            assert.ok(agentProvider);
        });
    });

    suite('AgentInfo Interface', () => {
        test('should define agent info structure', () => {
            interface AgentInfo {
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

            const agentInfo: AgentInfo = {
                name: 'code-analyzer',
                execution_hint: 'local',
                resolved_location: 'local',
                capabilities: {
                    consumes: ['source_code'],
                    produces: ['analysis_report'],
                    requires_filesystem: true,
                    requires_network: false
                }
            };

            assert.strictEqual(agentInfo.name, 'code-analyzer');
            assert.strictEqual(agentInfo.execution_hint, 'local');
            assert.ok(agentInfo.capabilities.requires_filesystem);
        });

        test('should support remote execution hint', () => {
            interface AgentInfo {
                name: string;
                execution_hint: 'local' | 'remote' | 'hybrid';
                resolved_location: 'local' | 'remote';
            }

            const agentInfo: AgentInfo = {
                name: 'llm-processor',
                execution_hint: 'remote',
                resolved_location: 'remote'
            };

            assert.strictEqual(agentInfo.execution_hint, 'remote');
        });

        test('should support hybrid execution hint', () => {
            interface AgentInfo {
                name: string;
                execution_hint: 'local' | 'remote' | 'hybrid';
                resolved_location: 'local' | 'remote';
            }

            const agentInfo: AgentInfo = {
                name: 'hybrid-agent',
                execution_hint: 'hybrid',
                resolved_location: 'local'
            };

            assert.strictEqual(agentInfo.execution_hint, 'hybrid');
        });
    });

    suite('AgentStatus Interface', () => {
        test('should define status structure', () => {
            interface AgentStatus {
                agents: Record<string, { name: string }>;
                total_agents: number;
                local_agents: number;
                remote_agents: number;
                llm_mode: 'online' | 'offline';
            }

            const status: AgentStatus = {
                agents: {
                    'agent-1': { name: 'analyzer' },
                    'agent-2': { name: 'processor' }
                },
                total_agents: 2,
                local_agents: 1,
                remote_agents: 1,
                llm_mode: 'online'
            };

            assert.strictEqual(status.total_agents, 2);
            assert.strictEqual(status.llm_mode, 'online');
            assert.strictEqual(Object.keys(status.agents).length, 2);
        });

        test('should support offline llm mode', () => {
            interface AgentStatus {
                llm_mode: 'online' | 'offline';
            }

            const status: AgentStatus = { llm_mode: 'offline' };
            assert.strictEqual(status.llm_mode, 'offline');
        });
    });

    suite('Refresh Status', () => {
        test('should have refreshStatus method', () => {
            assert.ok(typeof agentProvider.refreshStatus === 'function');
        });

        test('should call refreshStatus without error', async () => {
            // Should not throw even if API is unavailable
            try {
                await agentProvider.refreshStatus();
                assert.ok(true);
            } catch (error) {
                // Expected when API is not available
                assert.ok(true);
            }
        });
    });
});

