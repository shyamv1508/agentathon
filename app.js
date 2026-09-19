const el = id => document.getElementById(id);
const cutEl = el('cut');

const escapeHtml = v => String(v ?? '').replace(/[&<>'"]/g, c => ({
  '&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'
}[c]));

const protocolFor = cut => cut >= 9 ? 'v3' : cut >= 6 ? 'v2' : 'v1';

function safeText(id, value) {
  const node = el(id);
  if (node) node.textContent = value ?? '';
}

function safeHtml(id, value) {
  const node = el(id);
  if (node) node.innerHTML = value ?? '';
}

function trace(message) {
  const box = el('trace');
  if (!box) return;
  const row = document.createElement('p');
  row.innerHTML = message;
  box.appendChild(row);
  box.scrollTop = box.scrollHeight;
}

function setPipeline(active = -1, done = -1) {
  for (let i = 0; i < 6; i++) {
    const node = el('p' + i);
    if (!node) continue;
    node.classList.remove('active', 'complete');
    const state = node.querySelector('em');
    if (i === active) {
      node.classList.add('active');
      if (state) state.textContent = 'ACTIVE';
    } else if (i <= done) {
      node.classList.add('complete');
      if (state) state.textContent = 'DONE';
    } else if (state) {
      state.textContent = 'READY';
    }
  }
}

async function apiFetch(url, options = {}) {
  const response = await fetch(url, options);
  const raw = await response.text();
  let data = {};
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    throw new Error('API returned an invalid response (' + response.status + ')');
  }
  if (!response.ok) {
    throw new Error(data.detail || data.message || ('API request failed (' + response.status + ')'));
  }
  return data;
}

function currentCut() {
  return +(cutEl?.value || 12);
}

async function loadCut(value) {
  const cut = +value;
  const stats = await apiFetch('/api/stats?cut=' + cut);
  const protocol = protocolFor(cut);

  safeText('subjects', stats.subjects ?? '—');
  safeText('records', stats.records ?? '—');
  safeText('siteCount', (stats.sites ?? 12) + ' sites');
  safeText('cutCount', (stats.cuts ?? 12) + ' cuts indexed');
  safeText('protocol', protocol);
  safeText('protocolContext', 'Protocol ' + protocol);
  safeText('critical', stats.critical ?? '—');
  safeText('pending', stats.pending ?? '—');
  safeText('medicalContext', 'Evidence is resolved from data cut ' + cut + '; protocol ' + protocol + '.');

  document.querySelectorAll('.focus').forEach(button => button.classList.remove('activefocus'));
  const defaultFocus = document.querySelector('.focus[data-subject="042-S07-001"]');
  defaultFocus?.classList.add('activefocus');

  trace('<b>[system]</b> Data cut ' + cut + ' loaded · ' + (stats.records ?? 0) + ' visible records · protocol ' + protocol);
}

async function apiQuery(question) {
  return apiFetch('/api/query?q=' + encodeURIComponent(question) + '&cut=' + currentCut());
}

function openModal(id) {
  el(id)?.classList.remove('hidden');
}

function closeModal(id) {
  el(id)?.classList.add('hidden');
}

function renderEvidence(evidence) {
  if (!evidence?.length) return '<div class="queryev">No source records returned.</div>';
  return evidence.map(item => {
    const id = item.usubjid || item.document || 'document';
    const seq = item.seq != null ? ' · seq ' + item.seq : '';
    const section = item.section ? ' · ' + item.section : '';
    return '<div class="queryev"><b>' + escapeHtml(item.domain || 'DOC') + '</b> · ' +
      escapeHtml(id) + escapeHtml(seq) + escapeHtml(section) + '</div>';
  }).join('');
}

async function showQuery(title, question, options = {}) {
  openModal('queryModal');
  safeText('queryTitle', title);
  safeText('queryAnswer', 'Querying StudyGraph…');
  safeHtml('queryEvidence', '<div class="queryev">Loading source records…</div>');

  try {
    const data = await apiQuery(question);
    safeText('queryAnswer', data.text || (data.answer || []).join(', ') || 'No answer returned.');
    safeHtml('queryEvidence', renderEvidence(data.evidence));

    if (options.subject) {
      selectSubjectVisual(options.subject);
      safeText('patient', options.subject);
      safeText('liveAnswerTitle', title);
      safeText('liveAnswer', data.text || (data.answer || []).join(', ') || 'Evidence loaded.');
      safeText('medicalContext', 'Live StudyGraph answer at cut ' + currentCut() + '.');
    }

    trace('<b>[query]</b> ' + escapeHtml(title) + ' · ' + (data.evidence?.length || 0) + ' evidence records');
    return data;
  } catch (error) {
    safeText('queryAnswer', error.message);
    safeHtml('queryEvidence', '<div class="queryev">Query failed.</div>');
    trace('<b>[error]</b> ' + escapeHtml(error.message));
    throw error;
  }
}

function selectSubjectVisual(subject) {
  document.querySelectorAll('.subject').forEach(node => {
    node.classList.toggle('selected', node.dataset.subject === subject);
  });
  document.querySelectorAll('.focus').forEach(button => {
    button.classList.toggle('activefocus', button.dataset.subject === subject);
  });
}

async function focusSubject(subject, question, label) {
  selectSubjectVisual(subject);
  safeText('patient', subject);
  safeText('liveAnswerTitle', 'Loading ' + label + '…');
  safeText('liveAnswer', 'Fetching live evidence from StudyGraph…');
  try {
    const data = await apiQuery(question);
    safeText('liveAnswerTitle', label);
    safeText('liveAnswer', data.text || (data.answer || []).join(', ') || 'No findings returned.');
    safeText('medicalContext', 'Cut ' + currentCut() + ' · ' + protocolFor(currentCut()) + ' · ' + (data.evidence?.length || 0) + ' source records');
    trace('<b>[focus]</b> ' + subject + ' selected');
    return data;
  } catch (error) {
    safeText('liveAnswerTitle', 'Query error');
    safeText('liveAnswer', error.message);
  }
}

async function runCycle() {
  const button = el('cycle');
  if (button) button.disabled = true;

  safeText('termstatus', 'RUNNING');
  setPipeline(0, -1);
  trace('<b>[system]</b> Starting live MONITOR cycle…');

  const stages = [
    ['detect', 0],
    ['medical_review', 1],
    ['data_manager', 2],
    ['compliance', 3],
    ['human_gate', 4],
    ['execute', 5]
  ];

  let stageTimer;
  try {
    stageTimer = setInterval(() => {
      const active = +(window.__atlasStage || 0);
      if (active < stages.length - 1) {
        window.__atlasStage = active + 1;
        setPipeline(active + 1, active);
        trace('<b>[' + stages[active + 1][0] + ']</b> node active');
      }
    }, 550);

    const data = await apiFetch('/api/cycle?cut=' + currentCut());
    clearInterval(stageTimer);
    window.__atlasStage = 5;
    setPipeline(-1, 5);

    const stats = data.stats || {};
    const findings = stats.findings ?? data.findings?.length ?? 0;
    const escalations = stats.escalations ?? data.escalations?.length ?? 0;
    const pending = stats.pending_escalations ?? data.pending_escalations?.length ?? 0;

    safeText('pending', pending);
    safeText('critical', escalations);
    safeText('footerStatus', findings + ' findings · ' + escalations + ' escalations · cut ' + currentCut());
    safeText('termstatus', 'COMPLETE');

    trace('<b>[execute]</b> cycle complete · ' + findings + ' findings · ' + escalations + ' escalations');
    trace('<b>[memory]</b> duplicate query/escalation protection retained');
  } catch (error) {
    clearInterval(stageTimer);
    setPipeline(-1, -1);
    safeText('termstatus', 'ERROR');
    trace('<b>[error]</b> ' + escapeHtml(error.message));
  } finally {
    if (button) button.disabled = false;
    setTimeout(() => safeText('termstatus', 'IDLE'), 1200);
  }
}

async function gateDecision(decision, reason = '') {
  const payload = {
    cut: currentCut(),
    code: 'SAE_MISCODED',
    usubjid: '042-S02-004',
    decision,
    reason
  };

  const result = await apiFetch('/api/gate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });

  trace('<b>[human_gate]</b> ' + decision + ' SAE_MISCODED → ' + (result.escalation?.status || decision.toLowerCase()));
  safeText('liveAnswerTitle', 'Human Gate · ' + decision);
  safeText('liveAnswer', result.escalation?.summary || ('Decision recorded: ' + decision));
  return result;
}

async function handleFocus(button) {
  document.querySelectorAll('.focus').forEach(x => x.classList.remove('activefocus'));
  button.classList.add('activefocus');
  await focusSubject(button.dataset.subject, button.dataset.query, button.querySelector('span')?.textContent || 'Subject finding');
}

function bind() {
  el('cycle')?.addEventListener('click', runCycle);

  el('cut')?.addEventListener('change', async () => {
    try {
      setPipeline(0, -1);
      await loadCut(currentCut());
    } catch (error) {
      trace('<b>[error]</b> ' + escapeHtml(error.message));
    }
  });

  el('gate')?.addEventListener('click', () => openModal('modal'));
  el('bell')?.addEventListener('click', () => openModal('modal'));
  el('close')?.addEventListener('click', () => closeModal('modal'));
  el('queryClose')?.addEventListener('click', () => closeModal('queryModal'));

  el('reject')?.addEventListener('click', async () => {
    try {
      await gateDecision('REJECTED', 'Human monitor rejected the escalation; retain as monitoring.');
      closeModal('modal');
    } catch (error) {
      trace('<b>[error]</b> ' + escapeHtml(error.message));
    }
  });

  el('approve')?.addEventListener('click', async () => {
    try {
      await gateDecision('APPROVED', 'Human monitor approved the escalation.');
      closeModal('modal');
    } catch (error) {
      trace('<b>[error]</b> ' + escapeHtml(error.message));
    }
  });

  el('clar')?.addEventListener('click', async () => {
    const status = el('clarify');
    status?.classList.remove('hidden');
    if (status) status.textContent = '↻ Fetching context from StudyGraph…';

    try {
      await gateDecision('CLARIFY', 'Medical monitor requested additional graph context.');
      const data = await apiQuery('What is the patient360 for 042-S02-004?');
      if (status) status.textContent = '✓ Context found: ' + (data.text || 'evidence loaded');
    } catch (error) {
      if (status) status.textContent = '✕ ' + error.message;
    }
  });

  document.querySelectorAll('.focus').forEach(button => {
    button.addEventListener('click', () => handleFocus(button));
  });

  document.querySelectorAll('.subject').forEach(node => {
    node.addEventListener('click', () => {
      const subject = node.dataset.subject;
      const focus = document.querySelector('.focus[data-subject="' + subject + '"]');
      if (focus) {
        handleFocus(focus);
      } else {
        focusSubject(subject, 'What is the patient360 for ' + subject + '?', subject);
      }
    });
  });

  el('aeNode')?.addEventListener('click', () => {
    showQuery(
      'Reverse lookup · Cellulitis',
      'Which subjects have serious adverse events?'
    );
  });

  el('reverse')?.addEventListener('click', () => {
    showQuery(
      'Reverse lookup · Cellulitis',
      'Which subjects have serious adverse events?'
    );
  });

  el('report')?.addEventListener('click', () => {
    showQuery(
      'Cycle report · serious adverse events',
      'Which subjects have serious adverse events?'
    );
  });

  const core = document.querySelector('.core');
  core?.addEventListener('click', () => {
    showQuery(
      'Protocol intelligence',
      'What protocol version is active at the selected cut?'
    );
  });

  document.querySelectorAll('.site').forEach(site => {
    site.addEventListener('click', () => {
      const siteId = site.textContent.trim();
      const questions = {
        S07: 'Which subjects have Hy’s Law findings?',
        S02: 'Which subjects have serious adverse events?',
        S11: 'What findings are present for 042-S11-005?',
        S08: 'Which subjects have prohibited concomitant medications?'
      };
      showQuery('Site ' + siteId + ' intelligence', questions[siteId] || 'What findings are present?', {});
    });
  });

  document.querySelectorAll('.sat').forEach(node => {
    if (node.id === 'aeNode') return;
    node.addEventListener('click', () => {
      const label = node.textContent.trim();
      const questions = {
        ALT: 'Which subjects have Hy’s Law findings?',
        BILI: 'Which subjects have Hy’s Law findings?'
      };
      showQuery(label + ' signal lookup', questions[label] || 'Which subjects have Hy’s Law findings?');
    });
  });

  document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', event => {
      if (event.target === modal) modal.classList.add('hidden');
    });
  });

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      closeModal('modal');
      closeModal('queryModal');
    }
  });
}

async function start() {
  bind();
  setPipeline(0, -1);
  try {
    await loadCut(currentCut());
  } catch (error) {
    trace('<b>[error]</b> ' + escapeHtml(error.message));
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', start);
} else {
  start();
}
