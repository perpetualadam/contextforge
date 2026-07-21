/**
 * Pure helpers for the chat composer (enhance prompt + voice input).
 * Kept free of vscode imports so unit tests can run in Node.
 */

export interface PromptEnhancementResult {
    original: string;
    enhanced: string;
    suggestions: string[];
    improvements: string[];
}

export interface EnhancePromptRequest {
    prompt: string;
    context?: string;
    style?: string;
}

export type VoiceInputState = 'idle' | 'listening' | 'unsupported' | 'error';

export interface VoiceInputStatus {
    state: VoiceInputState;
    message?: string;
    transcript?: string;
}

export interface ComposerControlIds {
    enhanceButton: string;
    voiceButton: string;
    sendButton: string;
    messageInput: string;
    composerStatus: string;
}

export const COMPOSER_CONTROL_IDS: ComposerControlIds = {
    enhanceButton: 'enhancePromptButton',
    voiceButton: 'voiceInputButton',
    sendButton: 'sendButton',
    messageInput: 'messageInput',
    composerStatus: 'composerStatus',
};

/**
 * Validate whether a prompt can be enhanced.
 */
export function canEnhancePrompt(prompt: string | null | undefined): boolean {
    return Boolean(prompt && prompt.trim().length > 0);
}

/**
 * Build the request payload for POST /prompts/enhance.
 */
export function buildEnhancePromptRequest(
    prompt: string,
    options?: { context?: string; style?: string }
): EnhancePromptRequest {
    const trimmed = (prompt || '').trim();
    if (!trimmed) {
        throw new Error('Prompt is required to enhance');
    }

    return {
        prompt: trimmed,
        context: options?.context,
        style: options?.style || 'professional',
    };
}

/**
 * Apply an enhancement result to the current draft.
 * Prefer the API's enhanced text; fall back to the original draft if empty.
 */
export function applyEnhancementToDraft(
    currentDraft: string,
    result: PromptEnhancementResult | null | undefined
): string {
    if (!result) {
        return currentDraft;
    }
    const enhanced = (result.enhanced || '').trim();
    if (enhanced) {
        return enhanced;
    }
    return currentDraft;
}

/**
 * Guard against applying a stale enhance response after the draft changed
 * or a newer enhance request was started.
 */
export function shouldApplyEnhancementResult(options: {
    requestId?: number | null;
    activeRequestId?: number | null;
    sourcePrompt?: string | null;
    currentDraft?: string | null;
}): boolean {
    const { requestId, activeRequestId, sourcePrompt, currentDraft } = options;

    if (
        typeof requestId === 'number' &&
        typeof activeRequestId === 'number' &&
        requestId !== activeRequestId
    ) {
        return false;
    }

    if (typeof sourcePrompt === 'string' && typeof currentDraft === 'string') {
        if (currentDraft.trim() !== sourcePrompt.trim()) {
            return false;
        }
    }

    return true;
}

/**
 * Merge speech transcript into the composer draft.
 * Final transcripts append as new text; interim replaces a trailing interim marker.
 */
export function mergeVoiceTranscript(
    currentDraft: string,
    transcript: string,
    options?: { isFinal?: boolean; replaceAll?: boolean }
): string {
    const spoken = (transcript || '').trim();
    if (!spoken) {
        return currentDraft;
    }

    if (options?.replaceAll) {
        return spoken;
    }

    const draft = currentDraft || '';
    if (!draft.trim()) {
        return spoken;
    }

    // Append with a space when the draft does not already end with whitespace.
    const needsSpace = !/\s$/.test(draft);
    return needsSpace ? `${draft} ${spoken}` : `${draft}${spoken}`;
}

/**
 * Derive next voice UI state from recognition events.
 */
export function nextVoiceInputStatus(
    current: VoiceInputStatus,
    event: {
        type: 'start' | 'result' | 'end' | 'error' | 'unsupported';
        transcript?: string;
        message?: string;
    }
): VoiceInputStatus {
    switch (event.type) {
        case 'unsupported':
            return {
                state: 'unsupported',
                message: event.message || 'Speech recognition is not available in this environment',
            };
        case 'start':
            return { state: 'listening', message: 'Listening…', transcript: '' };
        case 'result':
            return {
                state: 'listening',
                message: current.state === 'listening' ? current.message : 'Listening…',
                transcript: event.transcript || '',
            };
        case 'end':
            return {
                state: 'idle',
                message: undefined,
                transcript: event.transcript ?? current.transcript,
            };
        case 'error':
            return {
                state: 'error',
                message: event.message || 'Voice input failed',
                transcript: current.transcript,
            };
        default:
            return current;
    }
}

/**
 * Whether the browser/webview exposes a SpeechRecognition constructor.
 */
export function isSpeechRecognitionSupported(globals: {
    SpeechRecognition?: unknown;
    webkitSpeechRecognition?: unknown;
} = {}): boolean {
    return Boolean(globals.SpeechRecognition || globals.webkitSpeechRecognition);
}

/**
 * Resolve the SpeechRecognition constructor from a window-like object.
 */
export function getSpeechRecognitionConstructor(globals: {
    SpeechRecognition?: new () => unknown;
    webkitSpeechRecognition?: new () => unknown;
}): (new () => unknown) | null {
    return globals.SpeechRecognition || globals.webkitSpeechRecognition || null;
}

/**
 * HTML for composer action buttons that must live next to the prompt textarea.
 * Tests assert these controls are present in the human AI input interface.
 */
export function buildComposerActionControlsHtml(ids: ComposerControlIds = COMPOSER_CONTROL_IDS): string {
    return [
        `<button type="button" class="composer-action-button" id="${ids.enhanceButton}" title="Enhance prompt" aria-label="Enhance prompt">✨ Enhance</button>`,
        `<button type="button" class="composer-action-button" id="${ids.voiceButton}" title="Speak prompt" aria-label="Speak prompt" data-voice-state="idle">🔊 Speak</button>`,
        `<button type="button" class="send-button" id="${ids.sendButton}" onclick="sendMessage()">Send</button>`,
    ].join('\n');
}

/**
 * Full human AI input interface: textarea + enhance + speak + send.
 * This is the composition surface where the user communicates with the AI.
 */
export function buildChatInputSectionHtml(ids: ComposerControlIds = COMPOSER_CONTROL_IDS): string {
    return `
            <div class="input-wrapper">
                <textarea
                    class="message-input"
                    id="${ids.messageInput}"
                    placeholder="Ask anything... Use @file:path @symbol:name @git @docs:query @web:query"
                    rows="1"
                ></textarea>
                <div class="composer-actions" role="group" aria-label="Prompt actions">
                    ${buildComposerActionControlsHtml(ids)}
                </div>
            </div>
            <div class="composer-status" id="${ids.composerStatus}" aria-live="polite"></div>`;
}

/**
 * Assert that HTML for the chat composer includes enhance + voice controls
 * in the same input interface as the message textarea.
 */
export function composerHtmlIncludesInputControls(html: string): {
    hasMessageInput: boolean;
    hasEnhance: boolean;
    hasVoice: boolean;
    hasSend: boolean;
    enhanceNearInput: boolean;
    voiceNearInput: boolean;
} {
    const hasMessageInput = html.includes(`id="${COMPOSER_CONTROL_IDS.messageInput}"`)
        || html.includes(`id='${COMPOSER_CONTROL_IDS.messageInput}'`);
    const hasEnhance = html.includes(`id="${COMPOSER_CONTROL_IDS.enhanceButton}"`)
        || /Enhance\s*prompt|✨\s*Enhance/i.test(html);
    const hasVoice = html.includes(`id="${COMPOSER_CONTROL_IDS.voiceButton}"`)
        || /Speak\s*prompt|🔊\s*Speak/i.test(html);
    const hasSend = html.includes(`id="${COMPOSER_CONTROL_IDS.sendButton}"`);

    // "Near" = appear after the textarea within the input-wrapper / input-container region.
    const inputIdx = html.indexOf(COMPOSER_CONTROL_IDS.messageInput);
    const enhanceIdx = html.indexOf(COMPOSER_CONTROL_IDS.enhanceButton);
    const voiceIdx = html.indexOf(COMPOSER_CONTROL_IDS.voiceButton);
    const enhanceNearInput = inputIdx >= 0 && enhanceIdx > inputIdx;
    const voiceNearInput = inputIdx >= 0 && voiceIdx > inputIdx;

    return {
        hasMessageInput,
        hasEnhance,
        hasVoice,
        hasSend,
        enhanceNearInput,
        voiceNearInput,
    };
}

/**
 * Label/title for the voice button based on listening state.
 */
export function voiceButtonLabel(state: VoiceInputState): { label: string; title: string } {
    if (state === 'listening') {
        return { label: '⏹ Stop', title: 'Stop listening' };
    }
    return { label: '🔊 Speak', title: 'Speak prompt' };
}
