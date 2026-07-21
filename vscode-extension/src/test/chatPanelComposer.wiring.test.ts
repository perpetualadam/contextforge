/**
 * Wiring tests: ensure the chat panel HTML/composer uses enhance + voice controls.
 * Run with: npm run test:unit
 */

import { describe, it } from 'node:test';
import * as assert from 'assert';
import * as fs from 'fs';
import * as path from 'path';
import { composerHtmlIncludesInputControls } from '../chatComposerFeatures';

describe('Chat panel composer wiring', () => {
    const chatPanelPath = path.join(__dirname, '..', '..', 'src', 'chatPanel.ts');
    const source = fs.readFileSync(chatPanelPath, 'utf8');

    it('imports and renders the shared chat input section builder', () => {
        assert.ok(source.includes("from './chatComposerFeatures'"));
        assert.ok(source.includes('buildChatInputSectionHtml'));
        assert.ok(source.includes('${buildChatInputSectionHtml(COMPOSER_CONTROL_IDS)}'));
    });

    it('handles enhancePrompt messages from the webview', () => {
        assert.ok(source.includes("case 'enhancePrompt'"));
        assert.ok(source.includes('handleEnhancePrompt'));
        assert.ok(source.includes('/prompts/enhance'));
    });

    it('includes voice input controls and speech recognition in the webview script', () => {
        assert.ok(source.includes('toggleVoiceInput'));
        assert.ok(source.includes('webkitSpeechRecognition') || source.includes('SpeechRecognition'));
        assert.ok(source.includes('voiceInputButton'));
        assert.ok(source.includes('enhancePromptButton'));
    });

    it('exposes insertText for Prompt Generator → chat handoff', () => {
        assert.ok(source.includes('public async insertText') || source.includes('public insertText'));
        assert.ok(source.includes('_pendingInsertText'));
        assert.ok(source.includes('flushPendingInsertText'));
        assert.ok(source.includes('contextforge.chatView.focus'));
    });

    it('guards enhance results against stale overwrites', () => {
        assert.ok(source.includes('shouldApplyEnhancementResult'));
        assert.ok(source.includes('requestId'));
        assert.ok(source.includes('sourcePrompt'));
        assert.ok(source.includes('activeEnhanceRequestId') || source.includes('_enhanceRequestSeq'));
    });

    it('keeps enhance and voice in the same input interface as the textarea', () => {
        const fragmentStart = source.indexOf('${buildChatInputSectionHtml(COMPOSER_CONTROL_IDS)}');
        assert.ok(fragmentStart > 0, 'chat input builder must be embedded in the webview HTML');

        const window = source.slice(Math.max(0, fragmentStart - 1200), fragmentStart + 120);
        assert.ok(window.includes('input-container'));
        assert.ok(window.includes('buildChatInputSectionHtml'));
        assert.ok(
            window.includes('file-upload-area') || window.includes('Attach'),
            'composer remains in the chat input container with attachments'
        );
    });
});

describe('Compiled chat composer helpers stay consistent', () => {
    it('reports missing controls for a send-only composer', () => {
        const checks = composerHtmlIncludesInputControls(
            '<textarea id="messageInput"></textarea><button id="sendButton">Send</button>'
        );
        assert.strictEqual(checks.hasEnhance, false);
        assert.strictEqual(checks.hasVoice, false);
    });
});
