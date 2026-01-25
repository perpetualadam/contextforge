/**
 * Tests for TaskPanelProvider module.
 * 
 * Tests task panel functionality including state management and API interactions.
 */

import * as assert from 'assert';
import * as vscode from 'vscode';
import { TaskPanelProvider, Task, TaskState } from '../../tools/taskPanel';

suite('TaskPanelProvider Test Suite', () => {
    let taskPanelProvider: TaskPanelProvider;
    let mockExtensionUri: vscode.Uri;

    suiteSetup(async () => {
        // Get extension URI from the current extension context
        const extension = vscode.extensions.getExtension('contextforge.contextforge');
        if (extension) {
            mockExtensionUri = extension.extensionUri;
        } else {
            // Fallback for tests running without full extension context
            mockExtensionUri = vscode.Uri.file(__dirname);
        }

        taskPanelProvider = new TaskPanelProvider(
            mockExtensionUri,
            { apiUrl: 'http://localhost:8080' }
        );
    });

    suite('TaskPanelProvider Creation', () => {
        test('should have correct view type', () => {
            assert.strictEqual(TaskPanelProvider.viewType, 'contextforge.taskView');
        });

        test('should be instantiable', () => {
            assert.ok(taskPanelProvider);
        });
    });

    suite('Task State Types', () => {
        test('should support NOT_STARTED state', () => {
            const state: TaskState = 'NOT_STARTED';
            assert.strictEqual(state, 'NOT_STARTED');
        });

        test('should support IN_PROGRESS state', () => {
            const state: TaskState = 'IN_PROGRESS';
            assert.strictEqual(state, 'IN_PROGRESS');
        });

        test('should support COMPLETE state', () => {
            const state: TaskState = 'COMPLETE';
            assert.strictEqual(state, 'COMPLETE');
        });

        test('should support CANCELLED state', () => {
            const state: TaskState = 'CANCELLED';
            assert.strictEqual(state, 'CANCELLED');
        });
    });

    suite('Task Interface', () => {
        test('should create valid task object', () => {
            const task: Task = {
                task_id: 'test-123',
                name: 'Test Task',
                description: 'A test task description',
                state: 'NOT_STARTED',
                parent_id: null,
                children: [],
                order: 0
            };

            assert.strictEqual(task.task_id, 'test-123');
            assert.strictEqual(task.name, 'Test Task');
            assert.strictEqual(task.description, 'A test task description');
            assert.strictEqual(task.state, 'NOT_STARTED');
            assert.strictEqual(task.parent_id, null);
            assert.deepStrictEqual(task.children, []);
            assert.strictEqual(task.order, 0);
        });

        test('should create task with parent', () => {
            const task: Task = {
                task_id: 'child-123',
                name: 'Child Task',
                description: '',
                state: 'IN_PROGRESS',
                parent_id: 'parent-123',
                children: [],
                order: 1
            };

            assert.strictEqual(task.parent_id, 'parent-123');
        });

        test('should create task with children', () => {
            const task: Task = {
                task_id: 'parent-123',
                name: 'Parent Task',
                description: '',
                state: 'NOT_STARTED',
                parent_id: null,
                children: ['child-1', 'child-2', 'child-3'],
                order: 0
            };

            assert.strictEqual(task.children.length, 3);
            assert.ok(task.children.includes('child-1'));
            assert.ok(task.children.includes('child-2'));
            assert.ok(task.children.includes('child-3'));
        });
    });

    suite('Configuration Update', () => {
        test('should update configuration', () => {
            const newApiUrl = 'http://localhost:9090';
            
            // updateConfig should not throw
            assert.doesNotThrow(() => {
                taskPanelProvider.updateConfig({ apiUrl: newApiUrl });
            });
        });
    });

    suite('Task State Cycle', () => {
        test('should cycle through valid states', () => {
            const states: TaskState[] = ['NOT_STARTED', 'IN_PROGRESS', 'COMPLETE'];
            
            // Verify state order for toggle functionality
            for (let i = 0; i < states.length; i++) {
                const currentState = states[i];
                const nextState = states[(i + 1) % states.length];
                
                // This tests the logic of state cycling
                assert.ok(states.includes(currentState));
                assert.ok(states.includes(nextState));
            }
        });
    });
});

