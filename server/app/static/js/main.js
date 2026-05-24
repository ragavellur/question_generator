/* ===== UPLOAD PAGE ===== */
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');

    if (dropZone && fileInput) {
        dropZone.addEventListener('click', () => fileInput.click());
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.style.borderColor = '#3b82f6';
            dropZone.style.background = '#eff6ff';
        });
        dropZone.addEventListener('dragleave', () => {
            dropZone.style.borderColor = '#93a3b8';
            dropZone.style.background = 'transparent';
        });
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.style.borderColor = '#93a3b8';
            dropZone.style.background = 'transparent';
            if (e.dataTransfer.files.length) {
                uploadFile(e.dataTransfer.files[0]);
            }
        });
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length) {
                uploadFile(fileInput.files[0]);
            }
        });
    }

    async function uploadFile(file) {
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            alert('Only PDF files are supported');
            return;
        }

        const status = document.getElementById('upload-status');
        const resultSection = document.getElementById('result-section');
        const errorSection = document.getElementById('error-section');

        status.classList.remove('hidden');
        resultSection.classList.add('hidden');
        errorSection.classList.add('hidden');

        document.getElementById('file-name').textContent = file.name;
        document.getElementById('file-size').textContent = (file.size / (1024 * 1024)).toFixed(1) + ' MB';
        document.getElementById('progress-bar').style.width = '5%';
        document.getElementById('status-message').textContent = 'Uploading...';

        const formData = new FormData();
        formData.append('file', file);

        try {
            const uploadResp = await fetch('/api/upload', {
                method: 'POST',
                body: formData,
            });

            if (!uploadResp.ok) {
                const err = await uploadResp.json();
                showError(err.detail || 'Upload failed');
                return;
            }

            const data = await uploadResp.json();
            const docId = data.document_id;

            if (data.queue_position > 1) {
                const qp = document.getElementById('queue-position');
                if (qp) qp.textContent = `⏳ Position in queue: #${data.queue_position}`;
            }

            await pollStatus(docId);

        } catch (err) {
            showError(err.message || 'Network error');
        }
    }

    const stepOrder = ['step-extract', 'step-profile', 'step-clean', 'step-chunk', 'step-verify', 'step-embed'];

    function markStep(currentStepId) {
        let found = false;
        for (const id of stepOrder) {
            const el = document.getElementById(id);
            if (!el) continue;
            if (id === currentStepId) {
                el.className = 'step-indicator step-active';
                found = true;
            } else if (!found) {
                el.className = 'step-indicator step-completed';
            } else {
                el.className = 'step-indicator';
            }
        }
    }

    async function pollStatus(docId) {
        const steps = {
            'extracting': 'step-extract',
            'profiling': 'step-profile',
            'cleaning': 'step-clean',
            'detecting_structure': 'step-chunk',
            'chunking': 'step-chunk',
            'verifying': 'step-verify',
            'embedding': 'step-embed',
            'storing': 'step-embed',
        };

        return new Promise((resolve) => {
            const interval = setInterval(async () => {
                try {
                    const resp = await fetch(`/api/upload/${docId}/status`);
                    const data = await resp.json();

                    const bar = document.getElementById('progress-bar');
                    const msg = document.getElementById('status-message');

                    bar.style.width = data.progress + '%';
                    bar.classList.add('progress-animated');
                    msg.textContent = data.message;

                    const stepId = steps[data.status];
                    if (stepId) {
                        markStep(stepId);
                    }

                    if (data.status === 'done' || data.progress >= 100) {
                        clearInterval(interval);
                        bar.classList.remove('progress-animated');
                        markStep(null);
                        showResult(data);
                        resolve();
                    } else if (data.status === 'error') {
                        clearInterval(interval);
                        showError(data.message);
                        resolve();
                    }
                } catch (e) {
                    // continue polling
                }
            }, 1000);
        });
    }

    function showResult(data) {
        document.getElementById('upload-status').classList.add('hidden');
        const section = document.getElementById('result-section');
        section.classList.remove('hidden');
        document.getElementById('result-details').textContent =
            'Document processed successfully.';
    }

    function showError(message) {
        document.getElementById('upload-status').classList.add('hidden');
        const section = document.getElementById('error-section');
        section.classList.remove('hidden');
        document.getElementById('error-message').textContent = message;
    }


    /* ===== GLOBAL PROCESSING STATUS ===== */
    (function startGlobalPolling() {
        if (!document.getElementById('global-processing-banner')) return;
        let warningEl = document.getElementById('processing-warning');

        async function pollProcessing() {
            try {
                const resp = await fetch('/api/processing/status');
                const data = await resp.json();

                const banner = document.getElementById('global-processing-banner');
                const statusText = document.getElementById('global-status-text');
                const queueText = document.getElementById('global-queue-text');

                if (data.processing) {
                    banner.classList.remove('hidden');
                    statusText.textContent = data.active_message ||
                        data.active_status || 'Processing...';
                    queueText.textContent = data.queue_length > 0
                        ? data.queue_length + ' waiting in queue'
                        : '';

                    if (warningEl) {
                        warningEl.classList.remove('hidden');
                        document.getElementById('processing-warning-text').textContent =
                            data.active_message || 'Please wait until processing finishes.';
                    }
                } else {
                    banner.classList.add('hidden');
                    if (warningEl) warningEl.classList.add('hidden');
                }

                if (window.updateGenerateButton) {
                    window.updateGenerateButton(data.processing, data.generation_active);
                }
            } catch (e) { /* ignore */ }
        }

        pollProcessing();
        setInterval(pollProcessing, 3000);
    })();

    /* ===== GENERATE PAGE ===== */
    const docSelect = document.getElementById('doc-select');
    const treeContent = document.getElementById('tree-content');
    const chapterTree = document.getElementById('chapter-tree');
    const showChunks = document.getElementById('show-chunks');
    const chunkList = document.getElementById('chunk-list');
    const chunkPreviewSection = document.getElementById('chunk-preview-section');
    const generateBtn = document.getElementById('generate-btn');
    const resultsSection = document.getElementById('results-section');
    const loadingSection = document.getElementById('loading-section');
    const questionsList = document.getElementById('questions-list');
    const regenerateBtn = document.getElementById('regenerate-btn');

    let selectedDocId = null;
    let selectedChunks = [];
    let selectedChapters = [];
    let selectedSections = [];
    let lastQuestions = [];

    if (docSelect) {
        loadDocSelect();
    }

    async function loadDocSelect() {
        try {
            const resp = await fetch('/api/documents');
            const docs = await resp.json();

            if (!docs.length) {
                docSelect.innerHTML = '<option value="">No documents available</option>';
                generateBtn.disabled = true;
                return;
            }

            let html = '<option value="">Select a document...</option>';
            docs.forEach(d => {
                html += `<option value="${d.id}">${d.name} (${d.chunk_count} chunks)</option>`;
            });
            docSelect.innerHTML = html;
            generateBtn.disabled = false;
        } catch (e) {
            docSelect.innerHTML = '<option value="">Error loading documents</option>';
        }
    }

    if (docSelect) {
        docSelect.addEventListener('change', async function () {
            selectedDocId = this.value;
            if (!selectedDocId) {
                chapterTree.classList.add('hidden');
                chunkPreviewSection.classList.add('hidden');
                return;
            }

            chapterTree.classList.remove('hidden');
            treeContent.innerHTML = '<div class="text-gray-500 py-2">Loading...</div>';

            try {
                const resp = await fetch(`/api/documents/${selectedDocId}/hierarchy`);
                const hierarchy = await resp.json();
                renderHierarchy(hierarchy);
            } catch (e) {
                treeContent.innerHTML = '<div class="text-red-500">Failed to load structure</div>';
            }
        });
    }

    function renderHierarchy(hierarchy) {
        let html = `
            <div class="flex items-center py-1 px-2 mb-1 border-b border-gray-200">
                <input type="checkbox" id="select-all-chapters" class="mr-2">
                <span class="text-xs font-semibold text-gray-600 uppercase tracking-wider">Select All Chapters</span>
                <span class="text-xs text-gray-400 ml-auto">${hierarchy.length} chapters</span>
            </div>
        `;
        hierarchy.forEach(ch => {
            const chId = 'ch-' + ch.number.replace('.', '-');
            const hasSections = (ch.sections || []).length > 0;
            html += `
                <div class="chapter-node py-1 px-2 rounded flex items-center" data-chapter="${ch.number}">
                    ${hasSections ? `<button onclick="toggleChapter('${chId}')" class="mr-1 text-gray-400 hover:text-gray-600 focus:outline-none text-xs w-4 text-center toggle-btn" data-ch="${chId}">▶</button>` : '<span class="mr-1 w-4"></span>'}
                    <input type="checkbox" class="chapter-cb mr-2" value="${ch.number}">
                    <span class="font-medium cursor-pointer" onclick="toggleChapter('${chId}')">Ch ${ch.number}: ${ch.title || 'Untitled'}</span>
                </div>
                <div class="ml-4 hidden" id="${chId}-sections">
            `;
            (ch.sections || []).forEach(sec => {
                html += `
                    <div class="section-node py-0.5 px-2 rounded flex items-center" data-chapter="${ch.number}" data-section="${sec}">
                        <input type="checkbox" class="section-cb mr-2" value="${sec}" data-chapter="${ch.number}">
                        <span class="text-sm">${sec}</span>
                    </div>
                `;
            });
            html += '</div>';
        });
        treeContent.innerHTML = html;

        const selectAll = document.getElementById('select-all-chapters');
        if (selectAll) {
            selectAll.addEventListener('change', function () {
                const checked = this.checked;
                treeContent.querySelectorAll('.chapter-cb').forEach(cb => {
                    cb.checked = checked;
                    const chapter = cb.value;
                    const sectionCbs = treeContent.querySelectorAll(`.section-cb[data-chapter="${chapter}"]`);
                    sectionCbs.forEach(scb => scb.checked = checked);
                });
                updateSelection();
            });
        }

        document.querySelectorAll('.chapter-cb').forEach(cb => {
            cb.addEventListener('change', function () {
                const chapter = this.value;
                const sectionCbs = treeContent.querySelectorAll(`.section-cb[data-chapter="${chapter}"]`);
                sectionCbs.forEach(scb => scb.checked = this.checked);
                const allChecked = treeContent.querySelectorAll('.chapter-cb:checked').length === treeContent.querySelectorAll('.chapter-cb').length;
                if (selectAll) selectAll.checked = allChecked;
                updateSelection();
            });
        });

        document.querySelectorAll('.section-cb').forEach(cb => {
            cb.addEventListener('change', updateSelection);
        });

        chunkPreviewSection.classList.remove('hidden');
    }

    window.toggleChapter = function (chId) {
        const container = document.getElementById(chId + '-sections');
        if (!container) return;
        container.classList.toggle('hidden');
        const btn = document.querySelector(`.toggle-btn[data-ch="${chId}"]`);
        if (btn) {
            btn.textContent = container.classList.contains('hidden') ? '▶' : '▼';
        }
    }

    function updateSelection() {
        const chapterCbs = treeContent.querySelectorAll('.chapter-cb:checked');
        const sectionCbs = treeContent.querySelectorAll('.section-cb:checked');

        selectedChapters = Array.from(chapterCbs).map(cb => cb.value);
        selectedSections = Array.from(sectionCbs).map(cb => cb.value);

        const hasSelection = selectedChapters.length > 0 || selectedSections.length > 0;
        generateBtn.disabled = !(selectedDocId && (hasSelection || true));

        if (showChunks && showChunks.checked && selectedDocId) {
            loadChunks();
        }
    }

    if (showChunks) {
        showChunks.addEventListener('change', function () {
            if (this.checked && selectedDocId) {
                chunkList.classList.remove('hidden');
                loadChunks();
            } else {
                chunkList.classList.add('hidden');
                selectedChunks = [];
            }
        });
    }

    async function loadChunks() {
        let url = `/api/documents/${selectedDocId}/chunks`;
        if (selectedChapters.length === 1) {
            url += `?chapter=${selectedChapters[0]}`;
        }

        try {
            const resp = await fetch(url);
            const chunks = await resp.json();
            let html = '';
            chunks.slice(0, 30).forEach(ch => {
                const cid = ch.chunk_id || ch.metadata?.chunk_id;
                const meta = ch.metadata || {};
                const preview = (ch.content || '').substring(0, 100);
                html += `
                    <label class="flex items-start p-1 hover:bg-gray-50 rounded cursor-pointer text-xs">
                        <input type="checkbox" class="chunk-cb mr-2 mt-0.5" value="${cid}">
                        <div>
                            <span class="text-gray-700">${meta.chapter_title || ''} / ${meta.section_title || ''}</span>
                            <div class="text-gray-400 truncate">${preview}...</div>
                        </div>
                    </label>
                `;
            });
            chunkList.innerHTML = html;

            document.querySelectorAll('.chunk-cb').forEach(cb => {
                cb.addEventListener('change', function () {
                    if (this.checked) {
                        selectedChunks.push(this.value);
                    } else {
                        selectedChunks = selectedChunks.filter(id => id !== this.value);
                    }
                });
            });
        } catch (e) {
            chunkList.innerHTML = '<div class="text-red-500 text-xs">Failed to load chunks</div>';
        }
    }

    window.updateGenerateButton = function (processing, generationActive) {
        if (generateBtn) {
            const disabled = processing || generationActive;
            generateBtn.disabled = disabled;
            if (processing) {
                generateBtn.title = 'A document is being processed. Please wait.';
            } else if (generationActive) {
                generateBtn.title = 'A question generation is already running. Please wait.';
            } else {
                generateBtn.title = '';
            }
        }
    };

    if (generateBtn) {
        generateBtn.addEventListener('click', generateQuestions);
    }

    if (regenerateBtn) {
        regenerateBtn.addEventListener('click', generateQuestions);
    }

    let activePollTaskId = null;

    resumeActiveTask();

    async function resumeActiveTask() {
        try {
            const resp = await fetch('/api/tasks?status=active');
            const tasks = await resp.json();
            if (tasks.length === 0) return;

            const task = tasks.reduce((a, b) =>
                (a.created_at || 0) > (b.created_at || 0) ? a : b
            );
            loadingSection.classList.remove('hidden');
            resultsSection.classList.add('hidden');
            questionsList.innerHTML = '';
            document.getElementById('gen-progress').innerHTML = '';
            if (window.updateGenerateButton) {
                window.updateGenerateButton(false, true);
            }
            activePollTaskId = task.task_id;
            await startPolling(task.task_id, null, task);
        } catch (e) {
            // no active task found
        }
    }

    async function startPolling(taskId, config, initialTask) {
        activePollTaskId = taskId;
        let allQs = initialTask ? (initialTask.questions || []) : [];
        const progressStatus = document.getElementById('progress-status');
        let retryCount = 0;
        const MAX_RETRIES = 2;

        if (initialTask) {
            allQs = initialTask.questions || [];
            renderProgressTracker(initialTask);
        }

        while (true) {
            if (activePollTaskId !== taskId) return;

            await new Promise(r => setTimeout(r, 3000));

            if (activePollTaskId !== taskId) return;

            const statusResp = await fetch(`/api/generate/${taskId}`);
            if (statusResp.status === 404) {
                if (config && retryCount < MAX_RETRIES) {
                    retryCount++;
                    const retryResp = await fetch('/api/generate', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(config),
                    });
                    if (retryResp.ok) {
                        const retryData = await retryResp.json();
                        taskId = retryData.task_id;
                        activePollTaskId = taskId;
                        continue;
                    }
                }
                loadingSection.classList.add('hidden');
                if (window.updateGenerateButton) window.updateGenerateButton(false, false);
                return;
            }
            if (!statusResp.ok) {
                loadingSection.classList.add('hidden');
                if (window.updateGenerateButton) window.updateGenerateButton(false, false);
                return;
            }

            const task = await statusResp.json();

            if (activePollTaskId !== taskId) return;

            if (task.status === 'error') {
                loadingSection.classList.add('hidden');
                if (window.updateGenerateButton) window.updateGenerateButton(false, false);
                questionsList.innerHTML = '<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">Error: ' + (task.error || 'Generation failed') + '</div>';
                resultsSection.classList.remove('hidden');
                return;
            }

            if (task.status === 'running' || task.status === 'queued') {
                if (progressStatus) progressStatus.textContent = task.message || 'Generating...';
                allQs = task.questions || [];
                renderProgressTracker(task);
            }

            if (task.status === 'done') {
                lastQuestions = task.questions || allQs;
                renderQuestions(lastQuestions);
                loadingSection.classList.add('hidden');
                resultsSection.classList.remove('hidden');
                activePollTaskId = null;
                if (window.updateGenerateButton) window.updateGenerateButton(false, false);
                return;
            }
        }
    }

    async function generateQuestions() {
        const qtypes = Array.from(document.querySelectorAll('.qtype:checked')).map(cb => cb.value);
        const domains = Array.from(document.querySelectorAll('.domain:checked')).map(cb => cb.value);

        if (!qtypes.length || !domains.length) {
            alert('Select at least one question type and domain');
            return;
        }

        const config = {
            doc_ids: [selectedDocId],
            chapter_numbers: selectedChapters.length ? selectedChapters : null,
            section_numbers: selectedSections.length ? selectedSections : null,
            chunk_ids: selectedChunks.length ? selectedChunks : null,
            question_types: qtypes,
            domains: domains,
            difficulty: document.getElementById('difficulty').value || null,
            count_per_type: parseInt(document.getElementById('count-per-type').value) || 2,
        };

        activePollTaskId = null;
        await new Promise(r => setTimeout(r, 50));

        resultsSection.classList.add('hidden');
        loadingSection.classList.remove('hidden');
        questionsList.innerHTML = '';
        document.getElementById('gen-progress').innerHTML = '';
        if (window.updateGenerateButton) window.updateGenerateButton(false, true);

        try {
            const resp = await fetch('/api/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config),
            });

            if (!resp.ok) {
                const errText = await resp.text();
                let msg = 'Generation failed';
                try { msg = JSON.parse(errText).detail || msg; } catch (e) {}
                throw new Error(msg);
            }

            let { task_id } = await resp.json();
            activePollTaskId = task_id;

            await new Promise(r => setTimeout(r, 1500));

            await startPolling(task_id, config);
        } catch (err) {
            questionsList.innerHTML = '<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">Error: ' + err.message + '</div>';
            resultsSection.classList.remove('hidden');
            loadingSection.classList.add('hidden');
            if (window.updateGenerateButton) window.updateGenerateButton(false, false);
        }
    }

    function appendQuestionSection(type, questions) {
        if (!questions || !questions.length) return;
        const container = document.getElementById('questions-list');
        let html = '<div class="question-type-section mb-6">';
        html += '<h3 class="text-md font-semibold mb-3 px-1" style="color:#0a1f3f; border-bottom:2px solid #1e4d8c; padding-bottom:6px;">' + type + ' (' + questions.length + ')</h3>';
        questions.forEach(function (q, i) {
            html += buildQuestionCard(q, i + 1);
        });
        html += '</div>';
        container.insertAdjacentHTML('beforeend', html);
    }

    function buildQuestionCard(q, idx) {
        const domainColors = { factual: { bg: 'bg-blue-100', text: 'text-blue-700' }, comprehension: { bg: 'bg-purple-100', text: 'text-purple-700' }, application: { bg: 'bg-orange-100', text: 'text-orange-700' } };
        const difficultyColors = { easy: { bg: 'bg-green-100', text: 'text-green-700' }, medium: { bg: 'bg-yellow-100', text: 'text-yellow-700' }, hard: { bg: 'bg-red-100', text: 'text-red-700' } };
        const domainKey = (q.domain || 'Factual').toLowerCase();
        const dc = domainColors[domainKey] || { bg: 'bg-gray-100', text: 'text-gray-700' };
        const diffKey = (q.difficulty || 'medium').toLowerCase();
        const df = difficultyColors[diffKey] || { bg: 'bg-gray-100', text: 'text-gray-700' };
        const showSource = document.getElementById('show-source') && document.getElementById('show-source').checked;

        let html = '<div class="question-card bg-white border border-gray-200 rounded-lg p-4 mb-3">';
        html += '<div class="flex items-center justify-between mb-2">';
        html += '<div class="flex items-center space-x-2 flex-wrap gap-y-1">';
        html += '<span class="text-xs font-medium bg-gray-100 text-gray-700 px-2 py-0.5 rounded">Q' + idx + '</span>';
        html += '<span class="text-xs font-medium ' + dc.bg + ' ' + dc.text + ' px-2 py-0.5 rounded">' + (q.domain || 'Factual') + '</span>';
        html += '<span class="text-xs font-medium ' + df.bg + ' ' + df.text + ' px-2 py-0.5 rounded capitalize">' + (q.difficulty || 'Medium') + '</span>';
        html += '<span class="text-xs text-gray-500">' + q.question_type + '</span>';
        if (showSource && q.source) html += '<span class="text-xs text-gray-400 ml-1">| ' + q.source + '</span>';
        html += '</div>';
        html += '<span class="text-sm font-medium text-gray-600">' + q.marks + ' mark' + (q.marks > 1 ? 's' : '') + '</span>';
        html += '</div>';
        html += '<p class="text-gray-900 mb-2">' + q.question_text + '</p>';
        if (q.options && q.options.length) {
            html += '<div class="space-y-1 mb-2">';
            q.options.forEach(function (opt) { html += '<p class="text-sm text-gray-600">' + opt + '</p>'; });
            html += '</div>';
        }
        html += '<details class="mt-2"><summary class="text-sm text-green-600 cursor-pointer hover:text-green-700">Show answer</summary>';
        html += '<p class="text-sm text-gray-700 mt-1 p-2 bg-green-50 rounded">' + q.answer + '</p></details>';
        html += '</div>';
        return html;
    }

    function renderQuestions(questions) {
        resultsSection.classList.remove('hidden');
        if (!questions.length) {
            questionsList.innerHTML = '<div class="text-gray-500 text-center py-8">No questions generated. Try different settings.</div>';
            return;
        }

        const showSource = document.getElementById('show-source') && document.getElementById('show-source').checked;

        const typeOrder = { 'MCQ': 1, 'True/False': 2, 'FIB': 3, 'Very Short': 4, 'Short Answer': 5, 'Long Answer': 6 };
        const domainOrder = { 'Factual': 1, 'Comprehension': 2, 'Application': 3 };

        const sorted = [...questions].sort((a, b) => {
            const ta = typeOrder[a.question_type] || 99;
            const tb = typeOrder[b.question_type] || 99;
            if (ta !== tb) return ta - tb;
            const da = domainOrder[a.domain] || 99;
            const db = domainOrder[b.domain] || 99;
            return da - db;
        });

        const difficultyColors = { easy: { bg: 'bg-green-100', text: 'text-green-700' }, medium: { bg: 'bg-yellow-100', text: 'text-yellow-700' }, hard: { bg: 'bg-red-100', text: 'text-red-700' } };
        const domainColors = { factual: { bg: 'bg-blue-100', text: 'text-blue-700' }, comprehension: { bg: 'bg-purple-100', text: 'text-purple-700' }, application: { bg: 'bg-orange-100', text: 'text-orange-700' } };

        let html = '';
        sorted.forEach((q, i) => {
            const typeClass = q.question_type.toLowerCase().replace('/', '_').replace(' ', '_');
            const domainKey = (q.domain || 'Factual').toLowerCase();
            const dc = domainColors[domainKey] || { bg: 'bg-gray-100', text: 'text-gray-700' };
            const diffKey = (q.difficulty || 'medium').toLowerCase();
            const df = difficultyColors[diffKey] || { bg: 'bg-gray-100', text: 'text-gray-700' };

            html += `
                <div class="question-card ${typeClass} bg-white border border-gray-200 rounded-lg p-4">
                    <div class="flex items-center justify-between mb-2">
                        <div class="flex items-center space-x-2 flex-wrap gap-y-1">
                            <span class="text-xs font-medium bg-gray-100 text-gray-700 px-2 py-0.5 rounded">Q${i + 1}</span>
                            <span class="text-xs font-medium ${dc.bg} ${dc.text} px-2 py-0.5 rounded">${q.domain || 'Factual'}</span>
                            <span class="text-xs font-medium ${df.bg} ${df.text} px-2 py-0.5 rounded capitalize">${q.difficulty || 'Medium'}</span>
                            <span class="text-xs text-gray-500">${q.question_type}</span>
                            ${showSource && q.source ? '<span class="text-xs text-gray-400 ml-1">| ' + q.source + '</span>' : ''}
                        </div>
                        <span class="text-sm font-medium text-gray-600">${q.marks} mark${q.marks > 1 ? 's' : ''}</span>
                    </div>
                    <p class="text-gray-900 mb-2">${q.question_text}</p>
            `;

            if (q.options && q.options.length) {
                html += '<div class="space-y-1 mb-2">';
                q.options.forEach(opt => {
                    html += `<p class="text-sm text-gray-600">${opt}</p>`;
                });
                html += '</div>';
            }

            html += `
                    <details class="mt-2">
                        <summary class="text-sm text-green-600 cursor-pointer hover:text-green-700">Show answer</summary>
                        <p class="text-sm text-gray-700 mt-1 p-2 bg-green-50 rounded">${q.answer}</p>
                    </details>
                </div>
            `;
        });

        questionsList.innerHTML = html;
        lastQuestions = sorted;
    }

    function renderProgressTracker(task) {
        const container = document.getElementById('gen-progress');
        if (!container || !task.selected_types) return;

        const comp = task.completed_types || [];
        const current = task.current_type || '';
        const nq = task.total_so_far || 0;
        const total = task.total_target || 0;
        const pct = total > 0 ? Math.round(nq / total * 100) : 0;
        const allQs = task.questions || [];

        let html = '';

        html += `<div class="w-full bg-gray-200 rounded-full h-2 mb-4">
            <div class="h-2 rounded-full transition-all duration-500" style="width:${pct}%;background:#1e4d8c"></div>
        </div>`;
        html += `<p class="text-xs text-gray-500 text-center mb-4">${nq} of ${total} questions</p>`;

        html += '<div class="space-y-1.5">';
        task.selected_types.forEach(type => {
            const done = comp.includes(type);
            const active = !done && type === current;
            const pending = !done && !active;
            const typeQs = allQs.filter(q => q.question_type === type);

            let dotClass = 'w-3 h-3 rounded-full inline-block flex-shrink-0';
            let dotStyle = '';
            if (done) {
                dotClass += ' bg-green-600';
            } else if (active) {
                dotClass += ' bg-blue-600';
                dotStyle = 'animation:pulse 1.5s ease-in-out infinite;';
            } else {
                dotClass += ' bg-gray-300';
            }

            html += `<div class="completed-type-wrapper border border-gray-200 rounded-lg overflow-hidden ${
                done ? 'cursor-pointer' : ''
            }">`;
            html += `<div class="flex items-center gap-2.5 px-3 py-2 ${
                active ? 'font-medium' : ''
            } ${done ? 'completed-type-header hover:bg-gray-50 transition-colors select-none' : ''}" data-type="${type}">`;
            html += `<span class="${dotClass}" style="${dotStyle}"></span>`;
            html += `<span class="text-sm ${done ? 'text-gray-600' : active ? 'text-blue-700' : 'text-gray-400'}">${type}</span>`;
            if (done) {
                html += `<span class="text-xs text-gray-400 ml-1">(${typeQs.length})</span>`;
                html += `<span class="text-xs text-green-600 ml-auto">Done</span>`;
                html += `<svg class="chevron w-4 h-4 text-gray-400 transition-transform ml-1" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>`;
            } else if (active) {
                html += `<span class="text-xs text-blue-500 ml-auto">Generating...</span>`;
            }
            html += `</div>`;
            if (done && typeQs.length) {
                html += `<div class="completed-type-questions hidden border-t border-gray-200 p-3 space-y-2">`;
                typeQs.forEach((q, i) => {
                    html += buildQuestionCard(q, i + 1);
                });
                html += `</div>`;
            }
            html += `</div>`;
        });
        html += '</div>';

        container.innerHTML = html;

        container.querySelectorAll('.completed-type-header').forEach(header => {
            header.addEventListener('click', function () {
                const wrapper = this.closest('.completed-type-wrapper');
                const body = wrapper.querySelector('.completed-type-questions');
                const chevron = this.querySelector('.chevron');
                if (body) {
                    body.classList.toggle('hidden');
                    if (chevron) chevron.classList.toggle('rotate-180');
                }
            });
        });
    }

    const sourceToggle = document.getElementById('show-source');
    if (sourceToggle) sourceToggle.addEventListener('change', function () {
        if (lastQuestions.length) renderQuestions(lastQuestions);
    });

    const downloadBtn = document.getElementById('download-json');
    if (downloadBtn) downloadBtn.addEventListener('click', function () {
        if (!lastQuestions.length) return;
        const blob = new Blob([JSON.stringify({ questions: lastQuestions }, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'questions.json';
        a.click();
        URL.revokeObjectURL(url);
    });

    const pdfBtn = document.getElementById('download-pdf');
    if (pdfBtn) pdfBtn.addEventListener('click', function () {
        if (!lastQuestions.length) return;
        generatePDF(lastQuestions);
    });

    function generatePDF(questions) {
        fetch('/api/generate-pdf', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ questions: questions }),
        }).then(function (resp) {
            if (!resp.ok) throw new Error('Server error');
            return resp.blob();
        }).then(function (blob) {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'questions.pdf';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }).catch(function (err) {
            alert('PDF download failed: ' + err.message);
        });
    }


    /* ===== DOCUMENTS PAGE ===== */
    loadDocumentList();

    async function loadDocumentList() {
        const container = document.getElementById('document-list');
        if (!container) return;
        try {
            const resp = await fetch('/api/documents');
            const docs = await resp.json();

            if (!docs.length) {
                container.innerHTML = `
                    <div class="text-center py-12" style="background:#ffffff; border-radius:0.75rem; box-shadow:0 1px 3px rgba(10,31,63,0.08)">
                        <div class="text-5xl mb-4">📂</div>
                        <h3 class="text-lg font-medium mb-2" style="color:#0a1f3f">No documents yet</h3>
                        <p class="mb-4" style="color:#64748b">Upload a PDF to get started</p>
                        <a href="/upload" class="btn-iaf btn-iaf-primary">Upload Document</a>
                    </div>
                `;
                return;
            }

            let html = '';
            docs.forEach(doc => {
                html += `
                    <div class="p-4 flex items-center justify-between rounded-xl" style="background:#ffffff; box-shadow:0 1px 3px rgba(10,31,63,0.08)">
                        <div class="flex items-center space-x-4">
                            <span class="text-3xl">📄</span>
                            <div>
                                <h3 class="font-medium" style="color:#0a1f3f">${doc.name || 'Unnamed'}</h3>
                                <p class="text-sm" style="color:#64748b">
                                    ${doc.total_pages || 0} pages · ${doc.chunk_count || 0} chunks
                                    ${doc.processed ? '<span style="color:#059669" class="ml-2">✓ Processed</span>' : ''}
                                </p>
                            </div>
                        </div>
                        <div class="flex items-center space-x-2">
                            <button onclick="viewHierarchy('${doc.id}')" class="btn-iaf btn-iaf-secondary text-sm">View Structure</button>
                            <a href="/generate" class="btn-iaf btn-iaf-primary text-sm">Generate</a>
                        </div>
                    </div>
                `;
            });
            container.innerHTML = html;
        } catch (e) {
            container.innerHTML = '<div class="text-center text-red-500 py-8">Failed to load documents</div>';
        }
    }

    window.viewHierarchy = async function (docId) {
        const modal = document.getElementById('hierarchy-modal');
        const content = document.getElementById('hierarchy-content');
        modal.classList.remove('hidden');
        content.innerHTML = '<div class="text-gray-500">Loading...</div>';

        try {
            const resp = await fetch(`/api/documents/${docId}/hierarchy`);
            const hierarchy = await resp.json();

            let html = '';
            hierarchy.forEach(ch => {
                const chId2 = 'hch-' + ch.number.replace('.', '-');
                const hasSects = (ch.sections || []).length > 0;
                html += `<div class="mb-2">
                    <div class="font-medium text-gray-900 flex items-center">
                        ${hasSects ? `<button onclick="toggleChapter('${chId2}')" class="mr-1 text-gray-400 hover:text-gray-600 focus:outline-none text-xs w-4 text-center toggle-btn" data-ch="${chId2}">▶</button>` : '<span class="mr-1 w-4"></span>'}
                        <span class="cursor-pointer" onclick="toggleChapter('${chId2}')">Chapter ${ch.number}: ${ch.title || ''}</span>
                    </div>
                    <div class="ml-5 mt-1 text-sm text-gray-600 hidden" id="${chId2}-sections">`;
                (ch.sections || []).forEach(sec => {
                    html += `<div class="py-0.5">• Section ${sec}</div>`;
                });
                html += `</div></div>`;
            });
            content.innerHTML = html || '<div class="text-gray-500">No structure data</div>';
        } catch (e) {
            content.innerHTML = '<div class="text-red-500">Failed to load structure</div>';
        }
    };

window.closeHierarchy = function () {
    document.getElementById('hierarchy-modal').classList.add('hidden');
};
