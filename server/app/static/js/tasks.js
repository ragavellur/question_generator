/* ===== TASKS PAGE ===== */

document.addEventListener('DOMContentLoaded', loadTasks);

async function loadTasks() {
    const container = document.getElementById('tasks-list');
    const errorSection = document.getElementById('error-section');
    errorSection.classList.add('hidden');

    try {
        const resp = await fetch('/api/tasks');
        if (!resp.ok) throw new Error('Failed to fetch tasks');
        const tasks = await resp.json();
        renderTasks(tasks);
    } catch (e) {
        container.innerHTML = '';
        errorSection.textContent = 'Error loading tasks: ' + e.message;
        errorSection.classList.remove('hidden');
    }
}

function relativeTime(ts) {
    const diff = Date.now() / 1000 - ts;
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return Math.floor(diff / 86400) + 'd ago';
}

function statusBadge(status) {
    const map = {
        done: { cls: 'bg-green-100 text-green-700', dot: 'bg-green-600', label: 'Done' },
        running: { cls: 'bg-blue-100 text-blue-700', dot: 'bg-blue-600 pulse', label: 'Running' },
        queued: { cls: 'bg-gray-100 text-gray-600', dot: 'bg-gray-400', label: 'Queued' },
        error: { cls: 'bg-red-100 text-red-700', dot: 'bg-red-600', label: 'Error' },
    };
    const s = map[status] || { cls: 'bg-gray-100 text-gray-600', dot: 'bg-gray-400', label: status };
    return `<span class="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${s.cls}">
        <span class="inline-block w-2 h-2 rounded-full ${s.dot}"></span>
        <span>${s.label}</span>
    </span>`;
}

function typeSummary(selected, completed) {
    if (!selected || !selected.length) return '';
    const n = completed ? completed.length : 0;
    return `${n}/${selected.length}`;
}

function renderTasks(tasks) {
    const container = document.getElementById('tasks-list');

    if (!tasks.length) {
        container.innerHTML = `
            <div class="text-center py-12" style="color:#64748b">
                <div class="text-4xl mb-3">📋</div>
                <p class="mb-2">No tasks yet</p>
                <p class="text-sm"><a href="/generate" class="text-blue-600 hover:underline">Generate questions</a> to create tasks</p>
            </div>`;
        return;
    }

    let html = '<div class="overflow-x-auto rounded-xl border border-gray-200">';
    html += '<table class="w-full text-sm" style="background:#ffffff">';
    html += `<thead>
        <tr style="background:#f8fafc; border-bottom:2px solid #e2e8f0">
            <th class="text-left px-4 py-3 font-semibold" style="color:#0a1f3f">Task ID</th>
            <th class="text-left px-4 py-3 font-semibold" style="color:#0a1f3f">Status</th>
            <th class="text-left px-4 py-3 font-semibold" style="color:#0a1f3f">Message</th>
            <th class="text-center px-4 py-3 font-semibold" style="color:#0a1f3f">Questions</th>
            <th class="text-center px-4 py-3 font-semibold" style="color:#0a1f3f">Types</th>
            <th class="text-right px-4 py-3 font-semibold" style="color:#0a1f3f">Created</th>
            <th class="text-center px-4 py-3 font-semibold" style="color:#0a1f3f">Action</th>
        </tr>
    </thead>`;
    html += '<tbody>';

    tasks.forEach((t, i) => {
        const tid = t.task_id || '';
        const shortId = tid.length > 8 ? tid.substring(0, 8) + '...' : tid;
        const qcount = (t.questions || []).length;
        const isRunning = t.status === 'running';
        const isDone = t.status === 'done';
        const deletable = t.status === 'done' || t.status === 'error' || t.status === 'queued';

        html += `<tr class="${i < tasks.length - 1 ? 'border-b border-gray-100' : ''} ${isRunning ? 'bg-blue-50/30' : ''} hover:bg-gray-50 transition-colors">`;
        html += `<td class="px-4 py-3 font-mono text-xs" style="color:#64748b">${shortId}</td>`;
        html += `<td class="px-4 py-3">${statusBadge(t.status)}</td>`;
        html += `<td class="px-4 py-3 max-w-xs truncate" style="color:#1e293b" title="${(t.message || '').replace(/"/g, '&quot;')}">${t.message || ''}</td>`;
        html += `<td class="px-4 py-3 text-center font-medium" style="color:#0a1f3f">${qcount}</td>`;
        html += `<td class="px-4 py-3 text-center text-xs" style="color:#64748b">${typeSummary(t.selected_types, t.completed_types)}</td>`;
        html += `<td class="px-4 py-3 text-right text-xs" style="color:#93a3b8">${relativeTime(t.created_at || 0)}</td>`;
        html += `<td class="px-4 py-3 text-center flex items-center justify-center space-x-2">`;
        if (isDone) {
            html += `<button onclick="viewTaskQuestions('${tid}')" class="text-blue-500 hover:text-blue-700 transition-colors text-sm font-medium" title="View questions">View</button>`;
        }
        if (deletable) {
            html += `<button onclick="deleteTask('${tid}')" class="text-red-400 hover:text-red-600 transition-colors text-base" title="Delete task">🗑️</button>`;
        } else {
            html += `<span class="text-gray-300 text-base" title="Cannot delete running task">–</span>`;
        }
        html += `</td>`;
        html += `</tr>`;
    });

    html += '</tbody></table></div>';
    container.innerHTML = html;
}

async function cleanupTasks() {
    const age = parseInt(document.getElementById('cleanup-age').value) || 3600;
    const btn = document.getElementById('cleanup-btn');
    btn.disabled = true;
    btn.textContent = 'Deleting...';

    try {
        const resp = await fetch('/api/tasks/cleanup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ max_age: age }),
        });
        if (!resp.ok) throw new Error('Cleanup failed');
        const data = await resp.json();
        await loadTasks();
        if (data.deleted > 0) {
            showFlash('Deleted ' + data.deleted + ' finished task(s)', 'green');
        } else {
            showFlash('No tasks to delete', 'gray');
        }
    } catch (e) {
        showFlash('Error: ' + e.message, 'red');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Delete Finished Tasks';
    }
}

async function deleteTask(taskId) {
    if (!confirm('Delete this task?')) return;

    try {
        const resp = await fetch('/api/tasks/' + taskId, { method: 'DELETE' });
        if (!resp.ok) throw new Error('Delete failed');
        await loadTasks();
        showFlash('Task deleted', 'green');
    } catch (e) {
        showFlash('Error: ' + e.message, 'red');
    }
}

var modalQuestions = [];

/* ---- domain/difficulty color maps (same as generate page) ---- */
var DOMAIN_COLORS = {
    Factual:       { bg: 'bg-blue-50', text: 'text-blue-700' },
    Comprehension: { bg: 'bg-purple-50', text: 'text-purple-700' },
    Application:   { bg: 'bg-amber-50', text: 'text-amber-700' },
};
var DIFF_COLORS = {
    easy:   { bg: 'bg-green-50', text: 'text-green-700' },
    medium: { bg: 'bg-yellow-50', text: 'text-yellow-700' },
    hard:   { bg: 'bg-red-50', text: 'text-red-700' },
};
var TYPE_CLASS = {
    MCQ: 'mcq', 'True/False': 'truefalse', FIB: 'fib',
    'Very Short': 'very_short', 'Short Answer': 'short', 'Long Answer': 'long',
};

async function viewTaskQuestions(taskId) {
    try {
        var resp = await fetch('/api/generate/' + taskId);
        if (!resp.ok) throw new Error('Failed to fetch task');
        var task = await resp.json();
        modalQuestions = task.questions || [];

        document.getElementById('modal-subtitle').textContent =
            modalQuestions.length + ' question(s) \u00b7 ' + (task.selected_types || []).join(', ');

        var jsonBtn = document.getElementById('modal-download-json');
        var pdfBtn = document.getElementById('modal-download-pdf');
        if (modalQuestions.length) {
            jsonBtn.classList.remove('hidden');
            pdfBtn.classList.remove('hidden');
        } else {
            jsonBtn.classList.add('hidden');
            pdfBtn.classList.add('hidden');
        }

        renderConfigSummary(task.config || {});
        document.getElementById('modal-show-source').checked = false;
        renderModalQuestions();

        document.getElementById('questions-modal').classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    } catch (e) {
        showFlash('Error loading questions: ' + e.message, 'red');
    }
}

function escHtml(s) {
    if (!s) return '';
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function badge(label, cls) {
    return '<span class="inline-block px-2 py-0.5 rounded text-xs font-medium ' + (cls || 'bg-gray-100 text-gray-600') + '">' + escHtml(label) + '</span>';
}

function renderConfigSummary(cfg) {
    var el = document.getElementById('modal-config-summary');
    if (!cfg.doc_names && !cfg.question_types) {
        el.classList.add('hidden');
        return;
    }
    el.classList.remove('hidden');

    var rows = [];

    /* Documents */
    if (cfg.doc_names && cfg.doc_names.length) {
        var docs = cfg.doc_names.map(function(n){ return badge(n, 'bg-blue-50 text-blue-700'); }).join(' ');
        rows.push('<div class="flex items-start"><span class="font-medium w-20 shrink-0" style="color:#64748b">Documents</span><span class="flex flex-wrap gap-1">' + docs + '</span></div>');
    }

    /* Chapters */
    var ch = [];
    if (cfg.all_chapters) {
        ch.push(badge('All chapters', 'bg-green-50 text-green-700'));
    } else if (cfg.chapter_numbers && cfg.chapter_numbers.length) {
        cfg.chapter_numbers.forEach(function(c){ ch.push(badge('Ch ' + c, 'bg-cyan-50 text-cyan-700')); });
    }
    if (cfg.section_numbers && cfg.section_numbers.length) {
        cfg.section_numbers.forEach(function(s){ ch.push(badge('Sec ' + s, 'bg-teal-50 text-teal-700')); });
    }
    if (ch.length) {
        rows.push('<div class="flex items-start"><span class="font-medium w-20 shrink-0" style="color:#64748b">Chapters</span><span class="flex flex-wrap gap-1">' + ch.join(' ') + '</span></div>');
    }

    /* Question Types */
    if (cfg.type_labels && cfg.type_labels.length) {
        var count = cfg.count_per_type || '';
        var qts = cfg.type_labels.map(function(t){ return badge(t + (count ? ' \u00d7' + count : ''), 'bg-purple-50 text-purple-700'); }).join(' ');
        rows.push('<div class="flex items-start"><span class="font-medium w-20 shrink-0" style="color:#64748b">Types</span><span class="flex flex-wrap gap-1">' + qts + '</span></div>');
    }

    /* Domains */
    if (cfg.domains && cfg.domains.length) {
        var dm = cfg.domains.map(function(d){ return badge(d.charAt(0).toUpperCase() + d.slice(1), 'bg-amber-50 text-amber-700'); }).join(' ');
        rows.push('<div class="flex items-start"><span class="font-medium w-20 shrink-0" style="color:#64748b">Domains</span><span class="flex flex-wrap gap-1">' + dm + '</span></div>');
    }

    /* Difficulty */
    if (cfg.difficulty) {
        rows.push('<div class="flex items-start"><span class="font-medium w-20 shrink-0" style="color:#64748b">Difficulty</span><span class="flex flex-wrap gap-1">' + badge(cfg.difficulty.charAt(0).toUpperCase() + cfg.difficulty.slice(1), 'bg-red-50 text-red-700') + '</span></div>');
    }

    el.innerHTML = '<div class="bg-gray-50 rounded-lg p-3 text-xs space-y-1.5 border border-gray-100" style="color:#475569">' + rows.join('') + '</div>';
}

function renderModalQuestions() {
    var showSource = document.getElementById('modal-show-source').checked;
    var body = document.getElementById('modal-body');
    var qs = modalQuestions;
    if (!qs.length) {
        body.innerHTML = '<div class="text-center py-8 text-gray-400">No questions in this task</div>';
        return;
    }

    var typeOrder = { MCQ:1, 'True/False':2, FIB:3, 'Very Short':4, 'Short Answer':5, 'Long Answer':6 };
    var domainOrder = { Factual:1, Comprehension:2, Application:3 };
    var sorted = qs.slice().sort(function(a,b){
        var to = (typeOrder[a.question_type]||99) - (typeOrder[b.question_type]||99);
        if (to) return to;
        return (domainOrder[a.domain]||99) - (domainOrder[b.domain]||99);
    });

    var html = '';
    sorted.forEach(function(q, i){
        var qtype = q.question_type || '';
        var domain = q.domain || 'Factual';
        var diff = q.difficulty || 'medium';
        var marks = q.marks || '';
        var text = q.question_text || '';
        var opts = q.options || [];
        var answer = q.answer || '';
        var source = q.source || '';
        var dc = DOMAIN_COLORS[domain] || { bg:'bg-gray-50', text:'text-gray-700' };
        var df = DIFF_COLORS[diff] || { bg:'bg-gray-50', text:'text-gray-700' };
        var tc = TYPE_CLASS[qtype] || '';

        html += '<div class="question-card ' + tc + ' bg-white border border-gray-200 rounded-lg p-4">';
        html += '<div class="flex items-center justify-between mb-2">';
        html += '<div class="flex items-center space-x-2 flex-wrap gap-y-1">';
        html += '<span class="text-xs font-medium bg-gray-100 text-gray-700 px-2 py-0.5 rounded">Q' + (i+1) + '</span>';
        html += '<span class="text-xs font-medium ' + dc.bg + ' ' + dc.text + ' px-2 py-0.5 rounded">' + escHtml(domain) + '</span>';
        html += '<span class="text-xs font-medium ' + df.bg + ' ' + df.text + ' px-2 py-0.5 rounded capitalize">' + escHtml(diff) + '</span>';
        html += '<span class="text-xs text-gray-500">' + escHtml(qtype) + '</span>';
        if (showSource && source) {
            html += '<span class="text-xs text-gray-400 ml-1">| ' + escHtml(source) + '</span>';
        }
        html += '</div>';
        html += '<span class="text-sm font-medium text-gray-600">' + marks + ' mark(s)</span>';
        html += '</div>';
        html += '<p class="text-gray-900 mb-2">' + escHtml(text) + '</p>';
        if (opts.length) {
            html += '<div class="space-y-1 mb-2">';
            opts.forEach(function(o){ html += '<p class="text-sm text-gray-600">' + escHtml(o) + '</p>'; });
            html += '</div>';
        }
        html += '<details class="mt-2">';
        html += '<summary class="text-sm text-green-600 cursor-pointer hover:text-green-700">Show answer</summary>';
        html += '<p class="text-sm text-gray-700 mt-1 p-2 bg-green-50 rounded">' + escHtml(answer) + '</p>';
        html += '</details>';
        html += '</div>';
    });
    body.innerHTML = html;
}

function closeQuestionsModal() {
    document.getElementById('questions-modal').classList.add('hidden');
    document.body.style.overflow = '';
}

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeQuestionsModal();
});

document.getElementById('questions-modal').addEventListener('click', function(e) {
    if (e.target === this) closeQuestionsModal();
});

/* ---- Download JSON ---- */
document.getElementById('modal-download-json').addEventListener('click', function(){
    if (!modalQuestions.length) return;
    var blob = new Blob([JSON.stringify({ questions: modalQuestions }, null, 2)], { type: 'application/json' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'questions.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
});

/* ---- Download PDF ---- */
document.getElementById('modal-download-pdf').addEventListener('click', function(){
    if (!modalQuestions.length) return;
    var btn = this;
    btn.disabled = true;
    btn.textContent = 'Generating PDF...';
    fetch('/api/generate-pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ questions: modalQuestions }),
    }).then(function(resp){
        if (!resp.ok) throw new Error('Server error');
        return resp.blob();
    }).then(function(blob){
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'questions.pdf';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        btn.disabled = false;
        btn.textContent = 'Download PDF';
    }).catch(function(err){
        alert('PDF download failed: ' + err.message);
        btn.disabled = false;
        btn.textContent = 'Download PDF';
    });
});

function showFlash(msg, color) {
    const existing = document.getElementById('flash-message');
    if (existing) existing.remove();

    const colors = { green: 'bg-green-50 text-green-700 border-green-200', red: 'bg-red-50 text-red-700 border-red-200', gray: 'bg-gray-50 text-gray-600 border-gray-200' };
    const div = document.createElement('div');
    div.id = 'flash-message';
    div.className = 'fixed top-4 right-4 z-50 px-4 py-3 rounded-lg border text-sm shadow-lg transition-opacity ' + (colors[color] || colors.gray);
    div.textContent = msg;
    document.body.appendChild(div);
    setTimeout(() => { div.style.opacity = '0'; setTimeout(() => div.remove(), 300); }, 3000);
}
