/**
 * Computer Use Demo — Frontend Application
 *
 * Manages sessions, real-time WebSocket streaming, chat UI, and VNC viewer.
 */
(function () {
    'use strict';

    // ─── State ───────────────────────────────────────────────────────────
    const state = {
        currentSessionId: null,
        currentSessionName: null,
        ws: null,
        isRunning: false,
        sessions: [],
    };

    // ─── DOM refs ────────────────────────────────────────────────────────
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const dom = {
        sessionList: $('#session-list'),
        sessionName: $('#current-session-name'),
        chatMessages: $('#chat-messages'),
        chatForm: $('#chat-form'),
        chatInput: $('#chat-input'),
        btnSend: $('#btn-send'),
        btnCancel: $('#btn-cancel'),
        btnDelete: $('#btn-delete-session'),
        btnNewSession: $('#btn-new-session'),
        connectionStatus: $('#connection-status'),
        toggleVnc: $('#toggle-vnc'),
        vncPanel: $('#vnc-panel'),
        vncFrame: $('#vnc-frame'),
        btnCloseVnc: $('#btn-close-vnc'),
        configModal: $('#config-modal'),
        configForm: $('#config-form'),
        btnCancelConfig: $('#btn-cancel-config'),
        cfgProvider: $('#cfg-provider'),
        cfgThinkingMode: $('#cfg-thinking-mode'),
        cfgApiKey: $('#cfg-apikey'),
        apikeyGroup: $('#apikey-group'),
        thinkingEffortGroup: $('#thinking-effort-group'),
    };

    // ─── API Helpers ─────────────────────────────────────────────────────
    const API = {
        async request(method, path, body) {
            const opts = {
                method,
                headers: { 'Content-Type': 'application/json' },
            };
            if (body) opts.body = JSON.stringify(body);
            const res = await fetch(path, opts);
            if (res.status === 204) return null;
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
            return data;
        },
        createSession(name, config) {
            return API.request('POST', '/api/sessions', { name, config });
        },
        listSessions() {
            return API.request('GET', '/api/sessions');
        },
        getSession(id) {
            return API.request('GET', `/api/sessions/${id}`);
        },
        deleteSession(id) {
            return API.request('DELETE', `/api/sessions/${id}`);
        },
        sendMessage(id, message) {
            return API.request('POST', `/api/sessions/${id}/chat`, { message });
        },
        cancelSession(id) {
            return API.request('POST', `/api/sessions/${id}/cancel`);
        },
        getMessages(id) {
            return API.request('GET', `/api/sessions/${id}/messages`);
        },
    };

    // ─── WebSocket ──────────────────────────────────────────────────────
    function connectWebSocket(sessionId) {
        if (state.ws) {
            state.ws.close();
            state.ws = null;
        }

        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${location.host}/ws/sessions/${sessionId}`;
        const ws = new WebSocket(wsUrl);
        state.ws = ws;

        ws.onopen = () => {
            console.log('WebSocket connected');
            dom.connectionStatus.classList.add('connected');
            dom.connectionStatus.title = 'Connected';
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                handleWSEvent(msg);
            } catch (e) {
                console.error('Failed to parse WS message:', e);
            }
        };

        ws.onclose = () => {
            console.log('WebSocket disconnected');
            dom.connectionStatus.classList.remove('connected');
            dom.connectionStatus.title = 'Disconnected';
            state.ws = null;
        };

        ws.onerror = (err) => {
            console.error('WebSocket error:', err);
        };
    }

    function handleWSEvent(msg) {
        switch (msg.type) {
            case 'connected':
                console.log('WS session connected:', msg.data);
                break;
            case 'status':
                addMessage('status', msg.data.message || msg.data.phase);
                break;
            case 'text_delta':
                appendOrCreateTextDelta(msg.data.text);
                break;
            case 'thinking':
                addMessage('thinking', msg.data.thinking || 'Thinking...');
                break;
            case 'tool_use':
                addToolUseMessage(msg.data);
                break;
            case 'tool_result':
                addToolResultMessage(msg.data);
                break;
            case 'error':
                addMessage('error', msg.data.message || 'Unknown error');
                state.isRunning = false;
                updateUIState();
                break;
            case 'done':
                addMessage('status', msg.data.message || 'Agent finished');
                state.isRunning = false;
                updateUIState();
                break;
            case 'cancelled':
                addMessage('status', msg.data.message || 'Cancelled');
                state.isRunning = false;
                updateUIState();
                break;
            case 'ping':
                // keep-alive
                break;
        }
        scrollToBottom();
    }

    // Track the last text-delta message element for appending
    let lastTextDeltaEl = null;

    function appendOrCreateTextDelta(text) {
        if (lastTextDeltaEl && lastTextDeltaEl.classList.contains('assistant') && !lastTextDeltaEl.querySelector('.tool-name')) {
            // Append to existing text bubble
            lastTextDeltaEl.textContent += text;
        } else {
            lastTextDeltaEl = addMessage('assistant', text);
        }
    }

    // ─── Message Rendering ──────────────────────────────────────────────
    function addMessage(role, content) {
        const container = dom.chatMessages;
        // Remove empty state if present
        const emptyState = container.querySelector('.empty-state');
        if (emptyState) emptyState.remove();

        const el = document.createElement('div');
        el.classList.add('message', role);

        if (role === 'error') {
            el.innerHTML = `<strong>⚠ Error:</strong> ${escapeHtml(content)}`;
        } else if (role === 'status') {
            el.textContent = content;
        } else {
            el.textContent = content;
        }

        container.appendChild(el);
        return el;
    }

    function addToolUseMessage(data) {
        const container = dom.chatMessages;
        const emptyState = container.querySelector('.empty-state');
        if (emptyState) emptyState.remove();

        lastTextDeltaEl = null; // reset text delta tracking

        const el = document.createElement('div');
        el.classList.add('message', 'tool');
        el.innerHTML = `
            <div class="tool-name">🔧 ${escapeHtml(data.name)}</div>
            <div class="tool-input">${escapeHtml(JSON.stringify(data.input, null, 2))}</div>
        `;
        container.appendChild(el);
        scrollToBottom();
    }

    function addToolResultMessage(data) {
        const container = dom.chatMessages;
        const emptyState = container.querySelector('.empty-state');
        if (emptyState) emptyState.remove();

        lastTextDeltaEl = null;

        const el = document.createElement('div');
        el.classList.add('message', 'tool');

        let html = `<div class="tool-name">📋 Result</div>`;
        if (data.output) {
            html += `<div>${escapeHtml(data.output).substring(0, 800)}</div>`;
        }
        if (data.error) {
            html += `<div style="color:var(--danger)">Error: ${escapeHtml(data.error)}</div>`;
        }
        if (data.base64_image) {
            html += `<img class="screenshot" src="data:image/png;base64,${data.base64_image}" alt="Screenshot" />`;
        }
        el.innerHTML = html;
        container.appendChild(el);
        scrollToBottom();
    }

    function renderMessageFromHistory(msg) {
        const container = dom.chatMessages;
        const emptyState = container.querySelector('.empty-state');
        if (emptyState) emptyState.remove();

        const content = msg.content;
        const role = msg.role;

        // Handle array content (multiple blocks)
        if (Array.isArray(content)) {
            content.forEach(block => {
                if (typeof block === 'string') {
                    addMessage(role, block);
                } else if (block.type === 'text') {
                    addMessage(role === 'user' ? 'user' : 'assistant', block.text);
                } else if (block.type === 'thinking') {
                    addMessage('thinking', block.thinking || '');
                } else if (block.type === 'tool_use') {
                    addToolUseMessage({ id: block.id, name: block.name, input: block.input });
                } else if (block.type === 'tool_result') {
                    const outputBlocks = Array.isArray(block.content) ? block.content : [];
                    let output = '';
                    let base64Image = null;
                    outputBlocks.forEach(b => {
                        if (typeof b === 'string') output += b;
                        else if (b.type === 'text') output += b.text;
                        else if (b.type === 'image' && b.source) base64Image = b.source.data;
                    });
                    addToolResultMessage({
                        output: output,
                        error: block.is_error ? output : null,
                        base64_image: base64Image,
                    });
                }
            });
        } else if (typeof content === 'string') {
            addMessage(role === 'user' ? 'user' : 'assistant', content);
        }
    }

    function clearMessages() {
        dom.chatMessages.innerHTML = '';
        lastTextDeltaEl = null;
    }

    function showEmptyState() {
        dom.chatMessages.innerHTML = `
            <div class="empty-state">
                <p>👋 Welcome! Create or select a session to get started.</p>
                <p>Type a task for Claude to control the virtual desktop.</p>
            </div>
        `;
    }

    function scrollToBottom() {
        dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;
    }

    // ─── UI State ────────────────────────────────────────────────────────
    function updateUIState() {
        const hasSession = !!state.currentSessionId;
        const running = state.isRunning;

        dom.chatInput.disabled = !hasSession || running;
        dom.btnSend.disabled = !hasSession || running || !dom.chatInput.value.trim();
        dom.btnCancel.disabled = !running;
        dom.btnDelete.disabled = !hasSession;

        if (running) {
            dom.btnSend.textContent = '⏳ Processing...';
        } else {
            dom.btnSend.textContent = 'Send';
        }

        dom.sessionName.textContent = state.currentSessionName || 'Select or create a session';
    }

    // ─── Session List ────────────────────────────────────────────────────
    async function loadSessions() {
        try {
            const data = await API.listSessions();
            state.sessions = data.sessions || [];
            renderSessionList();
        } catch (e) {
            console.error('Failed to load sessions:', e);
        }
    }

    function renderSessionList() {
        const list = dom.sessionList;
        list.innerHTML = '';

        if (state.sessions.length === 0) {
            list.innerHTML = '<div style="padding:12px;color:var(--text-muted);font-size:12px;text-align:center">No sessions yet</div>';
            return;
        }

        state.sessions.forEach(s => {
            const item = document.createElement('div');
            item.classList.add('session-item');
            if (s.id === state.currentSessionId) item.classList.add('active');

            item.innerHTML = `
                <span class="session-name">${escapeHtml(s.name)}</span>
                <span class="session-status ${s.status}">${s.status}</span>
                <button class="btn-delete-session-item" data-id="${s.id}" title="Delete">✕</button>
            `;

            item.addEventListener('click', (e) => {
                // Don't select if clicking delete button
                if (e.target.closest('.btn-delete-session-item')) return;
                selectSession(s.id);
            });

            list.appendChild(item);
        });

        // Attach delete handlers
        list.querySelectorAll('.btn-delete-session-item').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const id = btn.dataset.id;
                if (confirm('Delete this session?')) {
                    await API.deleteSession(id);
                    if (state.currentSessionId === id) {
                        state.currentSessionId = null;
                        state.currentSessionName = null;
                        clearMessages();
                        showEmptyState();
                        if (state.ws) { state.ws.close(); state.ws = null; }
                        updateUIState();
                    }
                    await loadSessions();
                }
            });
        });
    }

    async function selectSession(sessionId) {
        if (state.isRunning) {
            alert('Please wait for the current agent to finish or cancel it first.');
            return;
        }

        state.currentSessionId = sessionId;
        state.currentSessionName = state.sessions.find(s => s.id === sessionId)?.name || 'Session';

        // Connect WebSocket
        connectWebSocket(sessionId);

        // Load messages
        clearMessages();
        try {
            const data = await API.getMessages(sessionId);
            if (data.messages && data.messages.length > 0) {
                data.messages.forEach(m => renderMessageFromHistory(m));
            } else {
                showEmptyState();
            }
        } catch (e) {
            console.error('Failed to load messages:', e);
            showEmptyState();
        }

        updateUIState();
        renderSessionList();
        scrollToBottom();
    }

    async function createNewSession(configData) {
        const name = $('#cfg-name').value || 'New Session';
        const config = {
            model: $('#cfg-model').value,
            provider: $('#cfg-provider').value,
            api_key: $('#cfg-apikey').value,
            tool_version: $('#cfg-tool-version').value,
            max_tokens: parseInt($('#cfg-max-tokens').value) || 16384,
            thinking_mode: $('#cfg-thinking-mode').value,
            thinking_effort: $('#cfg-thinking-effort').value,
            thinking_budget: null,
            only_n_most_recent_images: 3,
            custom_system_prompt: '',
            token_efficient_tools_beta: false,
        };

        try {
            const session = await API.createSession(name, config);
            await loadSessions();
            // Find and select the new session
            const newId = session.id;
            const found = state.sessions.find(s => s.id === newId);
            if (found) {
                await selectSession(newId);
            }
            dom.configModal.classList.add('hidden');
        } catch (e) {
            alert(`Failed to create session: ${e.message}`);
        }
    }

    // ─── Chat Input ──────────────────────────────────────────────────────
    dom.chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = dom.chatInput.value.trim();
        if (!message || !state.currentSessionId || state.isRunning) return;

        // Show user message
        addMessage('user', message);
        dom.chatInput.value = '';
        state.isRunning = true;
        updateUIState();
        lastTextDeltaEl = null;

        try {
            await API.sendMessage(state.currentSessionId, message);
        } catch (e) {
            addMessage('error', `Failed to send message: ${e.message}`);
            state.isRunning = false;
            updateUIState();
        }
    });

    dom.chatInput.addEventListener('input', () => {
        dom.btnSend.disabled = !state.currentSessionId || state.isRunning || !dom.chatInput.value.trim();
    });

    // Allow Enter to send (Shift+Enter for newline)
    dom.chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            dom.chatForm.dispatchEvent(new Event('submit'));
        }
    });

    // ─── Cancel ──────────────────────────────────────────────────────────
    dom.btnCancel.addEventListener('click', async () => {
        if (!state.currentSessionId || !state.isRunning) return;
        try {
            await API.cancelSession(state.currentSessionId);
        } catch (e) {
            console.error('Cancel failed:', e);
        }
        // Also send cancel via WebSocket
        if (state.ws && state.ws.readyState === WebSocket.OPEN) {
            state.ws.send(JSON.stringify({ type: 'cancel' }));
        }
    });

    // ─── Delete Session ──────────────────────────────────────────────────
    dom.btnDelete.addEventListener('click', async () => {
        if (!state.currentSessionId) return;
        if (!confirm('Delete this session and all its messages?')) return;

        const id = state.currentSessionId;
        await API.deleteSession(id);
        state.currentSessionId = null;
        state.currentSessionName = null;
        clearMessages();
        showEmptyState();
        if (state.ws) { state.ws.close(); state.ws = null; }
        updateUIState();
        await loadSessions();
    });

    // ─── VNC Panel ──────────────────────────────────────────────────────
    function updateVncFrame() {
        const host = location.hostname;
        // Connect to noVNC on port 6080 with autoconnect
        dom.vncFrame.src = `http://${host}:6080/vnc.html?view_only=1&autoconnect=1&resize=scale`;
    }

    dom.toggleVnc.addEventListener('change', () => {
        if (dom.toggleVnc.checked) {
            dom.vncPanel.classList.remove('hidden');
            updateVncFrame();
        } else {
            dom.vncPanel.classList.add('hidden');
        }
    });

    dom.btnCloseVnc.addEventListener('click', () => {
        dom.toggleVnc.checked = false;
        dom.vncPanel.classList.add('hidden');
    });

    // ─── Config Modal ────────────────────────────────────────────────────
    dom.btnNewSession.addEventListener('click', () => {
        dom.configModal.classList.remove('hidden');
        $('#cfg-name').focus();
    });

    dom.btnCancelConfig.addEventListener('click', () => {
        dom.configModal.classList.add('hidden');
    });

    dom.configModal.addEventListener('click', (e) => {
        if (e.target === dom.configModal) {
            dom.configModal.classList.add('hidden');
        }
    });

    dom.configForm.addEventListener('submit', (e) => {
        e.preventDefault();
        createNewSession();
    });

    // Show/hide API key field based on provider
    dom.cfgProvider.addEventListener('change', () => {
        const provider = dom.cfgProvider.value;
        if (provider === 'anthropic' || provider === 'deepseek') {
            dom.apikeyGroup.style.display = 'block';
        } else {
            dom.apikeyGroup.style.display = 'none';
            dom.cfgApiKey.value = '';
        }
        // Auto-set model when switching provider
        const cfgModel = $('#cfg-model');
        if (provider === 'deepseek') {
            cfgModel.value = 'deepseek-chat';
        } else {
            cfgModel.value = 'claude-sonnet-4-20250514';
        }
    });

    // Show/hide thinking effort based on thinking mode
    dom.cfgThinkingMode.addEventListener('change', () => {
        const mode = dom.cfgThinkingMode.value;
        if (mode === 'adaptive') {
            dom.thinkingEffortGroup.style.display = 'block';
        } else {
            dom.thinkingEffortGroup.style.display = 'none';
        }
    });

    // ─── Utilities ──────────────────────────────────────────────────────
    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ─── Init ────────────────────────────────────────────────────────────
    async function init() {
        // Set initial VNC URL
        updateVncFrame();

        // Handle keyboard shortcut to close modal
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !dom.configModal.classList.contains('hidden')) {
                dom.configModal.classList.add('hidden');
            }
        });

        // Load sessions
        await loadSessions();

        // If there are sessions, auto-select the first one
        if (state.sessions.length > 0) {
            await selectSession(state.sessions[0].id);
        }

        updateUIState();
    }

    init();
})();
