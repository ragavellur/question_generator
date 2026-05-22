const STORAGE_KEY = 'chat_sessions';

let sessions = [];
let currentSessionId = null;
let inputDisabled = false;

/* ===== Session persistence ===== */

function loadSessions() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        sessions = raw ? JSON.parse(raw) : [];
    } catch (e) {
        sessions = [];
    }
}

function saveSessions() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
}

/* ===== Session CRUD ===== */

function createSession(docId, docName) {
    const session = {
        id: crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2),
        doc_id: docId,
        doc_name: docName,
        title: 'New chat',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        messages: [],
        provider: 'ollama',
        hybrid_enabled: false,
    };
    sessions.unshift(session);
    saveSessions();
    return session;
}

function deleteSession(id) {
    sessions = sessions.filter(s => s.id !== id);
    if (currentSessionId === id) {
        currentSessionId = null;
    }
    saveSessions();
    renderSessionList();
    if (currentSessionId) {
        loadSession(currentSessionId);
    } else {
        clearChatArea();
    }
}

function selectSession(id) {
    currentSessionId = id;
    renderSessionList();
    loadSession(id);
}

function getCurrentSession() {
    return sessions.find(s => s.id === currentSessionId) || null;
}

/* ===== Rendering ===== */

function renderSessionList() {
    const container = document.getElementById('session-list');
    if (!container) return;

    if (!sessions.length) {
        container.innerHTML = '<div style="color:#94a3b8" class="text-center py-8">No sessions yet</div>';
        return;
    }

    let html = '';
    sessions.forEach(s => {
        const active = s.id === currentSessionId;
        html += `
            <div class="session-item ${active ? 'bg-blue-50 border-blue-200' : 'hover:bg-gray-50 border-transparent'} border rounded-lg px-3 py-2 cursor-pointer flex items-center justify-between group"
                 onclick="selectSession('${s.id}')">
                <div class="flex-1 min-w-0">
                    <div class="text-sm font-medium truncate" style="color:${active ? '#1e4d8c' : '#1e293b'}">${escapeHtml(s.title)}</div>
                    <div class="text-xs truncate" style="color:#94a3b8">${escapeHtml(s.doc_name || 'Unknown')} ${s.provider === 'groq' ? '<span class="ml-1 text-blue-500 font-medium">[Groq]</span>' : '<span class="ml-1 text-gray-400">[Local]</span>'}${s.hybrid_enabled ? ' <span class="text-green-600 font-medium">[Hybrid]</span>' : ''}</div>
                </div>
                <button onclick="event.stopPropagation(); deleteSession('${s.id}')"
                        class="text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity ml-2 text-lg leading-none">&times;</button>
            </div>
        `;
    });
    container.innerHTML = html;
}

function clearChatArea() {
    const container = document.getElementById('chat-messages');
    if (!container) return;
    container.innerHTML = `
        <div class="text-center py-12" style="color:#94a3b8">
            <div class="text-4xl mb-3">💬</div>
            <p class="text-sm">Select a document and start asking questions</p>
        </div>
    `;
    document.getElementById('chat-input').disabled = true;
    document.getElementById('chat-send-btn').disabled = true;
    document.getElementById('chat-doc-select').value = '';
    const ps = document.getElementById('chat-provider-select');
    if (ps) ps.value = 'ollama';
    const ht = document.getElementById('chat-hybrid-toggle');
    if (ht) ht.checked = false;
}

function loadSession(id) {
    const session = sessions.find(s => s.id === id);
    if (!session) return;

    const container = document.getElementById('chat-messages');
    const docSelect = document.getElementById('chat-doc-select');
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send-btn');
    const providerSelect = document.getElementById('chat-provider-select');
    const hybridToggle = document.getElementById('chat-hybrid-toggle');

    docSelect.value = session.doc_id || '';
    if (providerSelect && session.provider) {
        providerSelect.value = session.provider;
    }
    if (hybridToggle) {
        hybridToggle.checked = session.hybrid_enabled || false;
    }
    container.innerHTML = '';

    if (session.messages.length === 0) {
        container.innerHTML = `
            <div class="text-center py-12" style="color:#94a3b8">
                <div class="text-4xl mb-3">💬</div>
                <p class="text-sm">Ask a question to get started</p>
            </div>
        `;
    } else {
        session.messages.forEach(m => {
            appendMessage(m.role, m.content, m.sources || null);
        });
        container.scrollTop = container.scrollHeight;
    }

    input.disabled = !session.doc_id;
    sendBtn.disabled = !session.doc_id;
}

function appendMessage(role, content, sources) {
    const container = document.getElementById('chat-messages');
    const empty = container.querySelector('.text-center.py-12');
    if (empty) empty.remove();

    const isUser = role === 'user';
    const div = document.createElement('div');
    div.className = `flex ${isUser ? 'justify-end' : 'justify-start'}`;

    const inner = document.createElement('div');
    inner.className = `max-w-[80%] rounded-xl px-4 py-3 ${
        isUser
            ? 'rounded-br-sm'
            : 'rounded-bl-sm'
    }`;
    inner.style.background = isUser ? '#1e4d8c' : '#f1f5f9';
    inner.style.color = isUser ? '#ffffff' : '#1e293b';

    const text = document.createElement('div');
    text.className = 'text-sm whitespace-pre-wrap';
    text.textContent = content;
    inner.appendChild(text);

    if (!isUser && sources && sources.length) {
        const srcToggle = document.createElement('button');
        srcToggle.className = 'text-xs mt-2 flex items-center space-x-1 opacity-70 hover:opacity-100 transition-opacity';
        srcToggle.style.color = '#475569';
        srcToggle.textContent = `Sources (${sources.length})`;
        srcToggle.onclick = () => toggleSources(sources, srcToggle);
        inner.appendChild(srcToggle);

        const srcContainer = document.createElement('div');
        srcContainer.className = 'hidden mt-2 space-y-1';
        srcContainer.id = 'sources-' + Math.random().toString(36).slice(2);
        inner.appendChild(srcContainer);
        inner.dataset.srcContainerId = srcContainer.id;

        let srcHtml = '';
        sources.forEach((s, i) => {
            const loc = [s.title, s.page_start ? `p.${s.page_start}` : ''].filter(Boolean).join(' — ');
            srcHtml += `
                <div class="text-xs p-2 rounded cursor-pointer hover:bg-gray-200 transition-colors" style="background:#e2e8f0"
                     onclick="openSourceModal('${escapeHtml(s.content_preview)}', '${escapeHtml(loc)}')">
                    <span style="color:#1e4d8c">${i + 1}. ${escapeHtml(loc)}</span>
                    <div class="truncate mt-0.5" style="color:#475569">${escapeHtml(s.content_preview.slice(0, 120))}...</div>
                </div>
            `;
        });
        srcContainer.innerHTML = srcHtml;
    }

    div.appendChild(inner);
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function toggleSources(sources, btn) {
    const msgDiv = btn.parentElement;
    const containerId = msgDiv.dataset.srcContainerId;
    const container = document.getElementById(containerId);
    if (!container) return;
    container.classList.toggle('hidden');
    btn.textContent = container.classList.contains('hidden') ? `Sources (${sources.length})` : 'Hide sources';
}

function appendTypingIndicator() {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = 'flex justify-start';
    div.id = 'typing-indicator';
    div.innerHTML = `
        <div class="max-w-[80%] rounded-xl rounded-bl-sm px-4 py-3" style="background:#f1f5f9; color:#64748b">
            <div class="flex items-center space-x-2">
                <span id="typing-icon" class="text-lg">🔍</span>
                <span id="typing-text" class="text-sm">Searching document...</span>
                <span class="inline-block w-2 h-2 rounded-full bg-gray-400 processing-pulse"></span>
            </div>
        </div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function updateTypingIndicator(stage, message) {
    const icon = document.getElementById('typing-icon');
    const text = document.getElementById('typing-text');
    if (!icon || !text) return;
    if (stage === 'searching') {
        icon.textContent = '🔍';
    } else if (stage === 'generating') {
        icon.textContent = '🤖';
    }
    text.textContent = message;
}

function removeTypingIndicator() {
    const el = document.getElementById('typing-indicator');
    if (el) el.remove();
}

/* ===== Source modal ===== */

function openSourceModal(preview, location) {
    const modal = document.getElementById('source-modal');
    const content = document.getElementById('source-modal-content');
    if (!modal || !content) return;
    content.innerHTML = `<div class="mb-2 text-xs font-medium" style="color:#1e4d8c">${location}</div><div>${escapeHtml(preview)}</div>`;
    modal.classList.remove('hidden');
}

function closeSourceModal() {
    const modal = document.getElementById('source-modal');
    if (modal) modal.classList.add('hidden');
}

/* ===== Document loading ===== */

async function loadDocSelect() {
    const select = document.getElementById('chat-doc-select');
    if (!select) return;

    try {
        const resp = await fetch('/api/documents');
        const docs = await resp.json();

        if (!docs.length) {
            select.innerHTML = '<option value="">No documents available</option>';
            return;
        }

        let html = '<option value="">Select a document...</option>';
        docs.forEach(d => {
            html += `<option value="${d.id}">${d.name}</option>`;
        });
        select.innerHTML = html;

        const session = getCurrentSession();
        if (session && session.doc_id) {
            select.value = session.doc_id;
        }
    } catch (e) {
        select.innerHTML = '<option value="">Error loading documents</option>';
    }
}

/* ===== Sending messages via polling ===== */

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send-btn');
    const message = input.value.trim();
    if (!message || inputDisabled) return;

    const session = getCurrentSession();
    if (!session || !session.doc_id) return;

    inputDisabled = true;
    input.disabled = true;
    sendBtn.disabled = true;

    appendMessage('user', message, null);
    session.messages.push({ role: 'user', content: message });
    input.value = '';

    if (session.messages.length === 1) {
        session.title = message.slice(0, 60) + (message.length > 60 ? '...' : '');
        renderSessionList();
    }

    const history = session.messages.slice(-9, -1).map(m => ({
        role: m.role,
        content: m.content,
    }));

    appendTypingIndicator();

    try {
        const resp = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                doc_id: session.doc_id,
                message: message,
                history: history,
                provider: session.provider || 'ollama',
                hybrid: session.hybrid_enabled || false,
            }),
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || 'Request failed');
        }

        let { task_id } = await resp.json();
        let done = false;

        while (!done) {
            await new Promise(r => setTimeout(r, 1500));

            const statusResp = await fetch(`/api/chat/${task_id}`);
            if (statusResp.status === 404) {
                const retryResp = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        doc_id: session.doc_id,
                        message: message,
                        history: history,
                        provider: session.provider || 'ollama',
                        hybrid: session.hybrid_enabled || false,
                    }),
                });
                if (retryResp.ok) {
                    const retryData = await retryResp.json();
                    task_id = retryData.task_id;
                    continue;
                }
                throw new Error('Task expired — could not auto-restart. Please ask again.');
            }
            if (!statusResp.ok) throw new Error('Status check failed');

            const task = await statusResp.json();

            if (task.status === 'error') {
                throw new Error(task.error || 'Generation failed');
            }

            updateTypingIndicator(task.status, task.message || 'Working...');

            if (task.status === 'done') {
                removeTypingIndicator();
                if (task.answer) {
                    appendMessage('assistant', task.answer, task.sources || null);
                    session.messages.push({
                        role: 'assistant',
                        content: task.answer,
                        sources: task.sources || [],
                    });
                }
                done = true;
            }
        }
    } catch (err) {
        removeTypingIndicator();
        appendMessage('assistant', 'Error: ' + err.message, null);
        session.messages.push({ role: 'assistant', content: 'Error: ' + err.message, sources: [] });
    }

    session.updated_at = new Date().toISOString();
    saveSessions();
    renderSessionList();

    inputDisabled = false;
    input.disabled = false;
    sendBtn.disabled = false;
    input.focus();
}

/* ===== Utility ===== */

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/* ===== Init ===== */

document.addEventListener('DOMContentLoaded', function () {
    loadSessions();
    loadDocSelect();

    const chatMessages = document.getElementById('chat-messages');
    const docSelect = document.getElementById('chat-doc-select');
    const chatForm = document.getElementById('chat-form');
    const newChatBtn = document.getElementById('new-chat-btn');

    if (!chatMessages || !docSelect) return;

    if (sessions.length > 0) {
        selectSession(sessions[0].id);
    }

    renderSessionList();

    if (newChatBtn) {
        newChatBtn.addEventListener('click', function () {
            const docId = docSelect.value;
            const docName = docSelect.options[docSelect.selectedIndex]?.text || 'Unknown';
            if (!docId) return;
            const session = createSession(docId, docName);
            selectSession(session.id);
        });
    }

    const providerSelect = document.getElementById('chat-provider-select');
    const hybridToggle = document.getElementById('chat-hybrid-toggle');

    if (providerSelect) {
        const session = getCurrentSession();
        if (session && session.provider) {
            providerSelect.value = session.provider;
        }
        providerSelect.addEventListener('change', function () {
            const s = getCurrentSession();
            if (s) {
                s.provider = this.value;
                saveSessions();
            }
        });
    }

    if (hybridToggle) {
        const session = getCurrentSession();
        if (session) {
            hybridToggle.checked = session.hybrid_enabled || false;
        }
        hybridToggle.addEventListener('change', function () {
            const s = getCurrentSession();
            if (s) {
                s.hybrid_enabled = this.checked;
                saveSessions();
                renderSessionList();
            }
        });
    }

    docSelect.addEventListener('change', function () {
        const session = getCurrentSession();
        const input = document.getElementById('chat-input');
        const sendBtn = document.getElementById('chat-send-btn');
        if (session) {
            session.doc_id = this.value;
            session.doc_name = this.options[this.selectedIndex]?.text || 'Unknown';
            saveSessions();
            renderSessionList();
            input.disabled = !this.value;
            sendBtn.disabled = !this.value;
        } else if (this.value) {
            const session = createSession(this.value, this.options[this.selectedIndex]?.text || 'Unknown');
            selectSession(session.id);
        } else {
            input.disabled = true;
            sendBtn.disabled = true;
        }
    });

    if (chatForm) {
        chatForm.addEventListener('submit', function (e) {
            e.preventDefault();
            sendMessage();
        });
    }

    const modal = document.getElementById('source-modal');
    if (modal) {
        modal.addEventListener('click', function (e) {
            if (e.target === this) closeSourceModal();
        });
    }
});
