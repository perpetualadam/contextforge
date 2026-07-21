/**
 * Unit tests for chat composer features: enhance prompt + voice input.
 * Run with: npm run test:unit
 */

import { describe, it } from 'node:test';
import * as assert from 'assert';
import {
    applyEnhancementToDraft,
    buildChatInputSectionHtml,
    buildComposerActionControlsHtml,
    buildEnhancePromptRequest,
    canEnhancePrompt,
    COMPOSER_CONTROL_IDS,
    composerHtmlIncludesInputControls,
    getSpeechRecognitionConstructor,
    isSpeechRecognitionSupported,
    mergeVoiceTranscript,
    nextVoiceInputStatus,
    shouldApplyEnhancementResult,
    voiceButtonLabel,
} from '../chatComposerFeatures';

describe('Chat composer enhance prompt', () => {
    it('rejects empty prompts for enhancement', () => {
        assert.strictEqual(canEnhancePrompt(''), false);
        assert.strictEqual(canEnhancePrompt('   '), false);
        assert.strictEqual(canEnhancePrompt(null), false);
        assert.strictEqual(canEnhancePrompt(undefined), false);
    });

    it('accepts non-empty prompts for enhancement', () => {
        assert.strictEqual(canEnhancePrompt('fix my bug'), true);
        assert.strictEqual(canEnhancePrompt('  explain auth  '), true);
    });

    it('builds a professional enhance request by default', () => {
        const req = buildEnhancePromptRequest('  make this better  ');
        assert.deepStrictEqual(req, {
            prompt: 'make this better',
            context: undefined,
            style: 'professional',
        });
    });

    it('includes optional context and style', () => {
        const req = buildEnhancePromptRequest('review this', {
            context: 'auth module',
            style: 'concise',
        });
        assert.strictEqual(req.context, 'auth module');
        assert.strictEqual(req.style, 'concise');
    });

    it('throws when building a request from an empty prompt', () => {
        assert.throws(() => buildEnhancePromptRequest('   '), /required/i);
    });

    it('applies enhanced text to the draft', () => {
        const next = applyEnhancementToDraft('short prompt', {
            original: 'short prompt',
            enhanced: 'A detailed, specific prompt with clear goals.',
            suggestions: ['Add examples'],
            improvements: ['More specific'],
        });
        assert.strictEqual(next, 'A detailed, specific prompt with clear goals.');
    });

    it('keeps the current draft when enhancement is missing or empty', () => {
        assert.strictEqual(applyEnhancementToDraft('keep me', null), 'keep me');
        assert.strictEqual(
            applyEnhancementToDraft('keep me', {
                original: 'keep me',
                enhanced: '   ',
                suggestions: [],
                improvements: [],
            }),
            'keep me'
        );
    });

    it('rejects stale enhance results when request ids differ', () => {
        assert.strictEqual(
            shouldApplyEnhancementResult({
                requestId: 1,
                activeRequestId: 2,
                sourcePrompt: 'old',
                currentDraft: 'old',
            }),
            false
        );
    });

    it('rejects enhance results when the draft changed while in flight', () => {
        assert.strictEqual(
            shouldApplyEnhancementResult({
                requestId: 3,
                activeRequestId: 3,
                sourcePrompt: 'original prompt',
                currentDraft: 'user edited while waiting',
            }),
            false
        );
    });

    it('accepts enhance results for the active request and unchanged draft', () => {
        assert.strictEqual(
            shouldApplyEnhancementResult({
                requestId: 4,
                activeRequestId: 4,
                sourcePrompt: 'same prompt',
                currentDraft: 'same prompt',
            }),
            true
        );
    });
});

describe('Chat composer voice input', () => {
    it('detects unsupported speech recognition', () => {
        assert.strictEqual(isSpeechRecognitionSupported({}), false);
        assert.strictEqual(
            isSpeechRecognitionSupported({ SpeechRecognition: function SpeechRecognition() {} }),
            true
        );
        assert.strictEqual(
            isSpeechRecognitionSupported({ webkitSpeechRecognition: function webkitSpeechRecognition() {} }),
            true
        );
    });

    it('resolves the speech recognition constructor', () => {
        function FakeSpeech() {}
        assert.strictEqual(getSpeechRecognitionConstructor({}), null);
        assert.strictEqual(
            getSpeechRecognitionConstructor({ SpeechRecognition: FakeSpeech as unknown as new () => unknown }),
            FakeSpeech
        );
    });

    it('merges spoken text into an empty draft', () => {
        assert.strictEqual(mergeVoiceTranscript('', 'hello world'), 'hello world');
    });

    it('appends spoken text to an existing draft with a space', () => {
        assert.strictEqual(mergeVoiceTranscript('Please', 'fix the bug'), 'Please fix the bug');
        assert.strictEqual(mergeVoiceTranscript('Please ', 'fix the bug'), 'Please fix the bug');
    });

    it('can replace the entire draft when requested', () => {
        assert.strictEqual(
            mergeVoiceTranscript('old text', 'new spoken prompt', { replaceAll: true }),
            'new spoken prompt'
        );
    });

    it('ignores empty transcripts', () => {
        assert.strictEqual(mergeVoiceTranscript('keep', '  '), 'keep');
    });

    it('transitions voice status through start, result, and end', () => {
        let status = nextVoiceInputStatus({ state: 'idle' }, { type: 'start' });
        assert.strictEqual(status.state, 'listening');

        status = nextVoiceInputStatus(status, { type: 'result', transcript: 'hello' });
        assert.strictEqual(status.state, 'listening');
        assert.strictEqual(status.transcript, 'hello');

        status = nextVoiceInputStatus(status, { type: 'end' });
        assert.strictEqual(status.state, 'idle');
    });

    it('marks unsupported and error states clearly', () => {
        const unsupported = nextVoiceInputStatus({ state: 'idle' }, { type: 'unsupported' });
        assert.strictEqual(unsupported.state, 'unsupported');
        assert.ok(unsupported.message);

        const errored = nextVoiceInputStatus(
            { state: 'listening', transcript: 'partial' },
            { type: 'error', message: 'mic denied' }
        );
        assert.strictEqual(errored.state, 'error');
        assert.strictEqual(errored.message, 'mic denied');
        assert.strictEqual(errored.transcript, 'partial');
    });

    it('updates the speak button label while listening', () => {
        assert.strictEqual(voiceButtonLabel('idle').label.includes('Speak'), true);
        assert.strictEqual(voiceButtonLabel('listening').label.includes('Stop'), true);
    });
});

describe('Chat composer HTML controls in the human AI input interface', () => {
    it('builds enhance, speak, and send controls with stable ids', () => {
        const html = buildComposerActionControlsHtml();
        assert.ok(html.includes(COMPOSER_CONTROL_IDS.enhanceButton));
        assert.ok(html.includes(COMPOSER_CONTROL_IDS.voiceButton));
        assert.ok(html.includes(COMPOSER_CONTROL_IDS.sendButton));
        assert.ok(/Enhance/i.test(html));
        assert.ok(/Speak/i.test(html));
    });

    it('requires enhance and voice controls to sit with the message input', () => {
        const goodHtml = `
            <div class="input-wrapper">
                <textarea id="${COMPOSER_CONTROL_IDS.messageInput}"></textarea>
                <div class="composer-actions">
                    ${buildComposerActionControlsHtml()}
                </div>
            </div>
        `;
        const checks = composerHtmlIncludesInputControls(goodHtml);
        assert.strictEqual(checks.hasMessageInput, true);
        assert.strictEqual(checks.hasEnhance, true);
        assert.strictEqual(checks.hasVoice, true);
        assert.strictEqual(checks.hasSend, true);
        assert.strictEqual(checks.enhanceNearInput, true);
        assert.strictEqual(checks.voiceNearInput, true);
    });

    it('fails when enhance/voice are missing from the typing interface', () => {
        const badHtml = `
            <textarea id="${COMPOSER_CONTROL_IDS.messageInput}"></textarea>
            <button id="${COMPOSER_CONTROL_IDS.sendButton}">Send</button>
        `;
        const checks = composerHtmlIncludesInputControls(badHtml);
        assert.strictEqual(checks.hasEnhance, false);
        assert.strictEqual(checks.hasVoice, false);
        assert.strictEqual(checks.enhanceNearInput, false);
        assert.strictEqual(checks.voiceNearInput, false);
    });

    it('builds the full chat input section with enhance and speak beside the textarea', () => {
        const html = buildChatInputSectionHtml();
        const checks = composerHtmlIncludesInputControls(html);
        assert.strictEqual(checks.hasMessageInput, true);
        assert.strictEqual(checks.hasEnhance, true);
        assert.strictEqual(checks.hasVoice, true);
        assert.strictEqual(checks.hasSend, true);
        assert.strictEqual(checks.enhanceNearInput, true);
        assert.strictEqual(checks.voiceNearInput, true);
        assert.ok(html.includes(COMPOSER_CONTROL_IDS.composerStatus));
    });
});
