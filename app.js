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

async function apiPatient(subject) {
  return apiFetch('/api/patient/' + encodeURIComponent(subject) + '?cut=' + currentCut());
}

async function apiLookup(type, value) {
  return apiFetch('/api/lookup?type=' + encodeURIComponent(type) + '&value=' + encodeURIComponent(value) + '&cut=' + currentCut());
}

function termButton(type, value) {
  return '<button class="termchip" data-term-type="' + escapeHtml(type) + '" data-term-value="' + escapeHtml(value) + '">' + escapeHtml(value) + '</button>';
}

function renderPatientTerms(patient) {
  const meds = [...new Set((patient?.domains?.CM || []).map(r => r.CMTRT).filter(Boolean))];
  const diseases = [...new Set((patient?.domains?.MH || []).map(r => r.MHTERM).filter(Boolean))];
  const aes = [...new Set((patient?.domains?.AE || []).map(r => r.AETERM).filter(Boolean))];
  safeHtml('medsContent', meds.length ? '<div class="termchips">' + meds.map(x => termButton('medication',x)).join('') + '</div>' : '<span class="termempty">No medications at this cut.</span>');
  const diseaseTerms = diseases.map(x => termButton('disease',x));
  safeHtml('diseaseContent', diseaseTerms.length
    ? '<div class="termchips">' + diseaseTerms.join('') + '</div>'
    : '<span class="termempty">No diseases at this cut.</span>');
  const labs = (patient?.domains?.LB || []).filter(r => r?.LBTEST || r?.LBORRES != null || r?.LBSTRESN != null);
  const labRows = labs.map(r => {
    const test = r.LBTEST || 'Lab';
    const value = r.LBSTRESN ?? r.LBORRES ?? '—';
    const unit = r.LBSTRESU || '';
    const date = r.LBDTC || r.LBDY || '';
    return '<div class="labrow"><div><b>' + escapeHtml(test) + '</b><small>' + escapeHtml(date) + '</small></div><strong>' + escapeHtml(value) + (unit ? ' ' + escapeHtml(unit) : '') + '</strong></div>';
  });
  safeHtml('labsContent', labRows.length
    ? labRows.join('')
    : '<span class="termempty">No laboratory records at this cut.</span>');
  safeHtml('patientTerms', diseases.length ? '<div class="termchips">' + diseases.map(x => termButton('disease',x)).join('') + '</div>' : '<span class="termempty">No medical history at this cut.</span>');
  document.querySelectorAll('.termchip').forEach(btn => btn.addEventListener('click', () => reverseLookup(btn.dataset.termType, btn.dataset.termValue)));
}

async function loadPatientTerms(subject) {
  try {
    const patient = await apiPatient(subject);
    renderPatientTerms(patient);
  } catch {
    safeHtml('patientTerms', '<span class="termempty">Unable to load patient terms.</span>');
  }
}

async function reverseLookup(type, value) {
  const title = (type === 'medication' ? 'Medication' : type === 'disease' ? 'Disease' : 'Adverse event') + ' · ' + value;
  openModal('queryModal');
  safeText('queryTitle', title);
  safeText('queryAnswer', 'Finding all matching subjects…');
  safeHtml('queryEvidence', '<div class="queryev">Loading source records…</div>');
  safeHtml('lookupSubjects', '<div class="queryev">Searching StudyGraph…</div>');
  try {
    const data = await apiLookup(type, value);
    safeText('queryAnswer', data.count + ' subject' + (data.count === 1 ? '' : 's') + ' match ' + value + '.');
    safeHtml('lookupSubjects', data.subjects.length
      ? data.subjects.map(s => '<button class="subjectlookup" data-subject="' + escapeHtml(s) + '">' + escapeHtml(s) + '</button>').join('')
      : '<span class="termempty">No matching subjects.</span>');
    safeHtml('queryEvidence', renderEvidence(data.evidence));
    document.querySelectorAll('.subjectlookup').forEach(btn => {
      btn.addEventListener('click', async () => {
        closeModal('queryModal');
        await focusSubject(btn.dataset.subject, 'What is the patient360 for ' + btn.dataset.subject + '?', btn.dataset.subject);
      });
    });
    trace('<b>[reverse_lookup]</b> ' + escapeHtml(type) + ' · ' + escapeHtml(value) + ' → ' + data.count + ' subjects');
  } catch (error) {
    safeText('queryAnswer', error.message);
    safeHtml('lookupSubjects', '<span class="termempty">Lookup failed.</span>');
    safeHtml('queryEvidence', '<div class="queryev">Query failed.</div>');
  }
}

async function askAtlas() {
  const input = el('questionInput');
  const question = input?.value.trim();
  if (!question) return;
  const button = el('askQuestion');
  if (button) button.disabled = true;
  try {
    await showQuery('ATLAS · ' + question, question);
  } finally {
    if (button) button.disabled = false;
  }
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
  safeHtml('lookupSubjects', '<div class="queryev">Reading answer…</div>');

  try {
    const data = await apiQuery(question);
    safeText('queryAnswer', data.text || (data.answer || []).join(', ') || 'No answer returned.');
    const answerValues = Array.isArray(data.answer) ? data.answer : [];
    const evidenceSubjects = Array.isArray(data.evidence)
      ? data.evidence.map(x => x?.usubjid).filter(Boolean)
      : [];
    const answerSubjects = [...new Set([...answerValues, ...evidenceSubjects]
      .map(x => String(x))
      .filter(x => /^042-S\d{2}-\d{3}$/.test(x)))];
    safeHtml('lookupSubjects', answerSubjects.length
      ? answerSubjects.map(s => '<button class="subjectlookup" data-subject="' + escapeHtml(s) + '">' + escapeHtml(s) + '</button>').join('')
      : '<span class="termempty">' + escapeHtml(data.text || 'No subject list in this answer.') + '</span>');
    document.querySelectorAll('.subjectlookup').forEach(btn => {
      btn.addEventListener('click', async () => {
        closeModal('queryModal');
        await focusSubject(btn.dataset.subject, 'What is the patient360 for ' + btn.dataset.subject + '?', btn.dataset.subject);
      });
    });
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

  const center = el('centerPatient');
  const graph = document.querySelector('.graph');
  if (center && graph) {
    graph.classList.add('centerhidden');
    center.classList.remove('hidden');
    safeText('centerPatientId', subject);
    safeText('centerPatientMeta', 'SITE ' + (subject.split('-')[1] || '—') + ' · CUT ' + currentCut());
    safeText('centerStatus', 'LOADING');
    safeText('centerAnswer', 'Fetching live evidence from StudyGraph…');
    safeText('centerProtocol', 'Protocol ' + protocolFor(currentCut()));
    safeText('centerContext', 'Resolving patient360 and source records…');
    safeText('centerEvidence', 'Loading…');
  }

  try {
    const data = await apiQuery(question);
    const answerText = data.text || (data.answer || []).join(', ') || 'No findings returned.';
    const evidence = Array.isArray(data.evidence) ? data.evidence : [];

    safeText('liveAnswerTitle', label);
    safeText('liveAnswer', answerText);
    safeText('medicalContext', 'Cut ' + currentCut() + ' · ' + protocolFor(currentCut()) + ' · ' + evidence.length + ' source records');

    if (center) {
      safeText('centerStatus', label || 'PATIENT 360');
      safeText('centerAnswer', answerText);
      safeText('centerContext', 'Cut ' + currentCut() + ' · ' + protocolFor(currentCut()) + ' · ' + evidence.length + ' source records');
      const evidenceHtml = evidence.length
        ? evidence.map(e => '<div class="evidence-row"><b>' + escapeHtml(e.domain || 'RECORD') + '</b><span>' + escapeHtml([e.usubjid, e.seq != null ? 'seq ' + e.seq : '', e.document, e.section].filter(Boolean).join(' · ')) + '</span></div>').join('')
        : 'No source records returned.';
      center.querySelector('#centerEvidence').innerHTML = evidenceHtml;
    }

    await loadPatientTerms(subject);
    trace('<b>[focus]</b> ' + subject + ' opened in center');
    return data;
  } catch (error) {
    safeText('liveAnswerTitle', 'Query error');
    safeText('liveAnswer', error.message);
    if (center) {
      safeText('centerStatus', 'QUERY ERROR');
      safeText('centerAnswer', error.message);
    }
  }
}

async function runCycle() {
  const button = el('cycle');
  if (button) {
    button.disabled = true;
    button.classList.remove('done');
    button.classList.add('running');
    button.textContent = '● RUNNING…';
  }

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

    const cyclePromise = apiFetch('/api/cycle?cut=' + currentCut());
    const minimumAnimation = new Promise(resolve => setTimeout(resolve, 3300));
    const data = await Promise.all([cyclePromise, minimumAnimation]).then(results => results[0]);
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
    if (button) {
      button.classList.remove('running');
      button.classList.add('done');
      button.textContent = '✓ CYCLE COMPLETE';
    }

    trace('<b>[execute]</b> cycle complete · ' + findings + ' findings · ' + escalations + ' escalations');
    trace('<b>[memory]</b> duplicate query/escalation protection retained');
  } catch (error) {
    clearInterval(stageTimer);
    setPipeline(-1, -1);
    safeText('termstatus', 'ERROR');
    trace('<b>[error]</b> ' + escapeHtml(error.message));
  } finally {
    if (button) {
      button.disabled = false;
      setTimeout(() => {
        button.classList.remove('running','done');
        button.textContent = '▶ RUN MONITOR CYCLE';
      }, 2200);
    }
    setTimeout(() => safeText('termstatus', 'IDLE'), 1200);
  }
}

let activeGate = null;

async function loadHumanGate() {
  openModal('modal');
  safeText('gateCode', 'Loading…');
  safeText('gateSubject', '—');
  safeText('gateRecord', '—');
  safeText('gateSummary', 'Loading pending escalations…');
  safeText('gateEvidence', '—');
  try {
    const data = await apiFetch('/api/escalations?cut=' + currentCut());
    const items = Array.isArray(data.escalations) ? data.escalations : [];
    activeGate = items[0] || null;
    if (!activeGate) {
      safeText('gateCode', 'No pending escalation');
      safeText('gateSummary', 'All escalations at this cut have been handled.');
      safeText('gateEvidence', '—');
      return;
    }
    safeText('gateEscalation', 'ESCALATION ' + String(items.indexOf(activeGate) + 1).padStart(2, '0'));
    safeText('gateCode', activeGate.code || 'ESCALATION');
    safeText('gateSubject', activeGate.usubjid || 'Site-level');
    safeText('gateRecord', (activeGate.evidence?.[0]?.domain || '') + (activeGate.evidence?.[0]?.seq != null ? ' · seq ' + activeGate.evidence[0].seq : ''));
    safeText('gateSummary', activeGate.summary || 'No summary available.');
    const ev = (activeGate.evidence || []).map(e => [e.domain, e.usubjid, e.seq != null ? 'seq ' + e.seq : ''].filter(Boolean).join(' · '));
    safeText('gateEvidence', ev.join(' | ') || 'No record evidence');
  } catch (error) {
    safeText('gateCode', 'Gate unavailable');
    safeText('gateSummary', error.message);
  }
}

async function gateDecision(decision, reason = '') {
  if (!activeGate) return;
  const payload = {
    cut: currentCut(),
    code: activeGate.code,
    usubjid: activeGate.usubjid,
    decision,
    reason
  };

  const result = await apiFetch('/api/gate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });

  trace('<b>[human_gate]</b> ' + decision + ' ' + activeGate.code + ' → ' + (result.escalation?.status || decision.toLowerCase()));
  safeText('liveAnswerTitle', 'Human Gate · ' + decision);
  safeText('liveAnswer', result.escalation?.summary || ('Decision recorded: ' + decision));
  return result;
}

async function handleFocus(button) {
  document.querySelectorAll('.focus').forEach(x => x.classList.remove('activefocus'));
  button.classList.add('activefocus');
  await focusSubject(button.dataset.subject, button.dataset.query, button.querySelector('span')?.textContent || 'Subject finding');
}


function setupNodeHoverPreview() {
  const graph = document.querySelector('.graph');
  const preview = document.querySelector('#nodePreview');
  if (!graph || !preview) return;

  const info = node => {
    const cut = currentCut();
    const protocol = protocolFor(cut);

    if (node.classList.contains('core')) return [
      'ATLAS CORE',
      'Protocol intelligence',
      'Cut ' + cut + ' · Protocol ' + protocol,
      'Click action: opens Protocol Intelligence and answers which protocol version is active at the selected cut.'
    ];

    if (node.classList.contains('site')) {
      const id = node.textContent.trim();
      const questions = {
        S07: 'Which subjects have Hy’s Law findings?',
        S02: 'Which subjects have serious adverse events?',
        S11: 'What findings are present for 042-S11-005?',
        S08: 'Which subjects have prohibited concomitant medications?'
      };
      return [
        'SITE ' + id,
        'Site intelligence',
        'Click action: opens site intelligence.',
        'Query: ' + (questions[id] || 'What findings are present?')
      ];
    }

    if (node.classList.contains('subject')) {
      const id = node.dataset.subject || node.textContent.trim();
      return [
        id,
        'Patient 360',
        'Click action: loads the selected subject.',
        'Shows labs · adverse events · concomitant medications · medical history · dosing · source evidence.'
      ];
    }

    if (node.classList.contains('sat')) {
      const id = node.textContent.trim();
      const questions = {
        ALT: 'Which subjects have Hy’s Law findings?',
        BILI: 'Which subjects have Hy’s Law findings?',
        AE: 'Which subjects have serious adverse events?'
      };
      return [
        id + ' SIGNAL',
        'Clinical evidence signal',
        'Click action: opens the matching signal lookup.',
        'Query: ' + (questions[id] || 'Which subjects have Hy’s Law findings?')
      ];
    }

    return null;
  };

  graph.querySelectorAll('.node').forEach(node => {
    node.addEventListener('mouseenter', () => {
      const data = info(node);
      if (!data) return;
      preview.innerHTML =
        '<b>' + escapeHtml(data[0]) + '</b>' +
        '<small><strong>' + escapeHtml(data[1]) + '</strong><br>' +
        escapeHtml(data[2]) + '<br>' + escapeHtml(data[3]) + '</small>';

      const nr = node.getBoundingClientRect();
      const gr = graph.getBoundingClientRect();
      const w = Math.min(360, Math.max(285, gr.width * .27));
      const h = 125;
      let left = nr.right - gr.left + 14;
      let top = nr.top - gr.top - 12;

      if (left + w > gr.width - 12) left = nr.left - gr.left - w - 14;
      if (top + h > gr.height - 12) top = gr.height - h - 12;
      if (top < 12) top = 12;
      if (left < 12) left = 12;

      preview.style.width = w + 'px';
      preview.style.left = left + 'px';
      preview.style.top = top + 'px';
      preview.classList.add('show');
    });
    node.addEventListener('mouseleave', () => preview.classList.remove('show'));
  });
}

function bind() {
  el('centerPatientClose')?.addEventListener('click', () => {
    el('centerPatient')?.classList.add('hidden');
    document.querySelector('.graph')?.classList.remove('centerhidden');
  });

  document.querySelectorAll('.tabs .tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tabs .tab').forEach(x => x.classList.remove('active'));
      document.querySelectorAll('.tabpane').forEach(x => x.classList.remove('active'));
      tab.classList.add('active');
      el('tab-' + tab.dataset.tab)?.classList.add('active');
    });
  });
  el('cycle')?.addEventListener('click', runCycle);
  el('askQuestion')?.addEventListener('click', askAtlas);
  el('questionInput')?.addEventListener('keydown', event => {
    if (event.key === 'Enter') askAtlas();
  });

  el('cut')?.addEventListener('change', async () => {
    try {
      setPipeline(0, -1);
      await loadCut(currentCut());
    } catch (error) {
      trace('<b>[error]</b> ' + escapeHtml(error.message));
    }
  });

  el('gate')?.addEventListener('click', loadHumanGate);
  el('bell')?.addEventListener('click', loadHumanGate);
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
      const data = await apiQuery('What is the patient360 for ' + activeGate.usubjid + '?');
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
  setupNodeHoverPreview();
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
