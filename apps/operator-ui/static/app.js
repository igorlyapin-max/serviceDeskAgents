const state = {
  analysis: null,
  approvalResults: {},
  feedback: null,
  ticketInput: null,
  caseRecord: null,
  caseTimeline: null,
  casePoll: null,
  knowledge: null,
  activeTab: 'rag',
};

const elements = {
  apiStatus: document.getElementById('apiStatus'),
  operatorId: document.getElementById('operatorId'),
  ticketForm: document.getElementById('ticketForm'),
  analyzeButton: document.getElementById('analyzeButton'),
  rebuildButton: document.getElementById('rebuildButton'),
  copyButton: document.getElementById('copyButton'),
  summaryView: document.getElementById('summaryView'),
  caseView: document.getElementById('caseView'),
  caseStatus: document.getElementById('caseStatus'),
  caseTimeline: document.getElementById('caseTimeline'),
  approvalView: document.getElementById('approvalView'),
  feedbackView: document.getElementById('feedbackView'),
  feedbackNote: document.getElementById('feedbackNote'),
  correctedResponse: document.getElementById('correctedResponse'),
  feedbackStatus: document.getElementById('feedbackStatus'),
  feedbackButtons: Array.from(document.querySelectorAll('[data-feedback-rating]')),
  knowledgeStatus: document.getElementById('knowledgeStatus'),
  traceView: document.getElementById('traceView'),
  copyText: document.getElementById('copyText'),
  tabs: Array.from(document.querySelectorAll('.tab')),
};

function compactObject(value) {
  return Object.fromEntries(
    Object.entries(value).filter(([, item]) => item !== undefined && item !== null && item !== ''),
  );
}

const eventTypeLabels = {
  case_created: 'Кейс создан',
  analysis_completed: 'Анализ завершен',
  action_gate_created: 'Создано согласование',
  approval_decisioned: 'Согласование обработано',
  tool_result_recorded: 'Результат инструмента записан',
  integration_callback_received: 'Получен callback интеграции',
  feedback_recorded: 'Обратная связь записана',
};

const actorTypeLabels = {
  system: 'система',
  system_policy: 'политика',
  operator: 'оператор',
  endpoint: 'endpoint',
  callback: 'callback',
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = body.detail?.message || body.detail?.errors?.join('; ') || response.statusText;
    throw new Error(message);
  }
  return body;
}

function formPayload() {
  const data = new FormData(elements.ticketForm);
  return compactObject({
    user: data.get('user'),
    service: data.get('service'),
    environment: data.get('environment'),
    priority: data.get('priority'),
    scenario: data.get('scenario'),
    description: data.get('description'),
  });
}

function badge(status) {
  const normalized = String(status || 'info').replace(/[^a-z0-9_-]/gi, '_').toLowerCase();
  return `<span class="badge ${normalized}">${escapeHtml(status || 'н/д')}</span>`;
}

function metric(label, value) {
  return `
    <div class="metric">
      <div class="metric-label">${escapeHtml(label)}</div>
      <div class="metric-value">${value}</div>
    </div>
  `;
}

function renderKnowledge() {
  const knowledge = state.knowledge;
  if (!knowledge) {
    elements.knowledgeStatus.innerHTML = '<div class="empty span-all">Нет статуса</div>';
    return;
  }
  const manifest = knowledge.index_manifest;
  if (!manifest) {
    elements.knowledgeStatus.innerHTML = [
      metric('Статус', badge(knowledge.status)),
      metric('Путь индекса', escapeHtml(knowledge.index_path || 'н/д')),
      `<div class="message-block"><div class="metric-label">Ошибка</div><p>${escapeHtml(knowledge.error?.message || 'н/д')}</p></div>`,
    ].join('');
    return;
  }
  elements.knowledgeStatus.innerHTML = [
    metric('Статус', badge(manifest.status)),
    metric('Построен', escapeHtml(manifest.built_at)),
    metric('Документы', String(manifest.document_count)),
    metric('Фрагменты', String(manifest.chunk_count)),
    `<div class="message-block"><div class="metric-label">Источники</div><p>${escapeHtml(
      manifest.sources.map((source) => `${source.source_id}: ${source.status}`).join(', '),
    )}</p></div>`,
  ].join('');
}

function renderAnalysis() {
  const analysis = state.analysis;
  if (!analysis) {
    elements.summaryView.innerHTML = '<div class="empty span-all">Нет анализа</div>';
    elements.caseStatus.textContent = 'Нет кейса';
    elements.caseTimeline.innerHTML = '';
    elements.approvalView.innerHTML = '';
    elements.traceView.innerHTML = '<div class="empty">Нет трассировки</div>';
    elements.copyText.textContent = '';
    elements.copyButton.disabled = true;
    return;
  }

  const decision = analysis.ai_decision?.decision;
  elements.summaryView.innerHTML = [
    metric('Заявка', escapeHtml(analysis.ticket_id)),
    metric('Состояние', badge(analysis.workflow_state?.id)),
    metric('Решение', escapeHtml(decision?.type || 'invalid')),
    metric('RAG', badge(analysis.rag_trace?.status || 'н/д')),
    `<div class="message-block"><div class="metric-label">Сообщение оператору</div><p>${escapeHtml(
      analysis.operator_message || '',
    )}</p></div>`,
    `<div class="message-block"><div class="metric-label">Кратко</div><p>${escapeHtml(
      decision?.summary || decision?.question || decision?.reason || 'н/д',
    )}</p></div>`,
  ].join('');

  renderApprovals();
  renderCase();
  renderFeedback();
  renderTrace();
  elements.copyText.textContent = buildCopyText();
  elements.copyButton.disabled = false;
}

function renderCase() {
  const caseRecord = state.caseRecord;
  const timeline = state.caseTimeline;
  if (!state.analysis?.case_id) {
    elements.caseStatus.textContent = 'Нет кейса';
    elements.caseTimeline.innerHTML = '';
    return;
  }
  const workflow = caseRecord?.current_workflow_state?.id || state.analysis.workflow_state?.id || 'н/д';
  const eventCount = caseRecord?.event_count ?? timeline?.events?.length ?? 0;
  const updatedAt = caseRecord?.updated_at || 'н/д';
  elements.caseStatus.innerHTML = [
    `Кейс: <strong>${escapeHtml(state.analysis.case_id)}</strong>`,
    `Состояние: ${badge(workflow)}`,
    `Событий: ${escapeHtml(eventCount)}`,
    `Обновлен: ${escapeHtml(updatedAt)}`,
  ].join(' / ');

  const events = timeline?.events || [];
  if (!events.length) {
    elements.caseTimeline.innerHTML = '<div class="empty">Нет событий timeline</div>';
    return;
  }
  elements.caseTimeline.innerHTML = events
    .slice(-8)
    .map(
      (event) => `
        <div class="timeline-event">
          <div class="timeline-time">${escapeHtml(event.created_at)}</div>
          <div>
            <div class="timeline-type">${escapeHtml(eventTypeLabels[event.event_type] || event.event_type)}</div>
            <div class="timeline-meta">${escapeHtml(event.summary || event.actor_id)}</div>
          </div>
          ${badge(actorTypeLabels[event.correlation?.invocation_id ? 'callback' : event.actor_type] || event.actor_type)}
        </div>
      `,
    )
    .join('');
}

function renderFeedback() {
  const hasAnalysis = Boolean(
    state.analysis?.ticket_id && !['n/a', 'н/д'].includes(state.analysis.ticket_id),
  );
  elements.feedbackButtons.forEach((button) => {
    button.disabled = !hasAnalysis;
  });
  if (state.feedback) {
    elements.feedbackStatus.textContent = `Обратная связь сохранена: ${state.feedback.feedback_id} / ${state.feedback.rating}`;
    return;
  }
  elements.feedbackStatus.textContent = hasAnalysis
    ? 'Обратная связь не сохранена'
    : 'Сначала выполните анализ заявки';
}

function renderApprovals() {
  const approvals = state.analysis?.approval_requests || [];
  if (!approvals.length) {
    elements.approvalView.innerHTML = '';
    return;
  }

  elements.approvalView.innerHTML = approvals
    .map((approval) => {
      const result = state.approvalResults[approval.approval_id];
      const resultStatus = result?.gate?.status || approval.status;
      const toolStatus = result?.tool_result?.status;
      return `
        <div class="approval-item">
          <div class="approval-title">
            <span>${escapeHtml(approval.tool_name)}</span>
            ${badge(resultStatus)}
          </div>
          <div class="approval-meta">
            <div>Действие: ${escapeHtml(approval.action_id)}</div>
            <div>Риск: ${escapeHtml(approval.risk_level)} / ${escapeHtml(approval.policy_rule_id)}</div>
            <div>Эффект: ${escapeHtml(approval.expected_effect)}</div>
            <div>Параметры: ${escapeHtml(JSON.stringify(approval.parameters))}</div>
            ${toolStatus ? `<div>Результат инструмента: ${badge(toolStatus)}</div>` : ''}
          </div>
          <div class="approval-actions">
            <input id="comment-${approval.approval_id}" placeholder="Комментарий к решению">
            <button class="approve" type="button" data-approval="${approval.approval_id}" data-decision="approve" ${
              result ? 'disabled' : ''
            }>Согласовать</button>
            <button class="reject" type="button" data-approval="${approval.approval_id}" data-decision="reject" ${
              result ? 'disabled' : ''
            }>Отклонить</button>
          </div>
        </div>
      `;
    })
    .join('');

  elements.approvalView.querySelectorAll('[data-approval]').forEach((button) => {
    button.addEventListener('click', () => decideApproval(button.dataset.approval, button.dataset.decision));
  });
}

function renderTrace() {
  elements.tabs.forEach((tab) => tab.classList.toggle('active', tab.dataset.tab === state.activeTab));
  if (!state.analysis) {
    elements.traceView.innerHTML = '<div class="empty">Нет трассировки</div>';
    return;
  }
  if (state.activeTab === 'rag') {
    renderRagTrace();
    return;
  }
  if (state.activeTab === 'tools') {
    renderToolTrace();
    return;
  }
  elements.traceView.innerHTML = `<pre>${escapeHtml(JSON.stringify(state.analysis, null, 2))}</pre>`;
}

function renderRagTrace() {
  const trace = state.analysis.rag_trace;
  if (!trace || !trace.matches?.length) {
    elements.traceView.innerHTML = `<div class="empty">Статус RAG: ${escapeHtml(trace?.status || 'н/д')}</div>`;
    return;
  }
  elements.traceView.innerHTML = trace.matches
    .map(
      (match) => `
        <div class="trace-item">
          <div class="trace-title">${escapeHtml(match.title)} ${badge(match.score)}</div>
          <div class="trace-meta">${escapeHtml(match.source_id)} / ${escapeHtml(match.uri)}</div>
        </div>
      `,
    )
    .join('');
}

function renderToolTrace() {
  const trace = state.analysis.tool_trace || [];
  if (!trace.length) {
    elements.traceView.innerHTML = '<div class="empty">Нет вызовов инструментов</div>';
    return;
  }
  elements.traceView.innerHTML = trace
    .map(
      (item) => `
        <div class="trace-item">
          <div class="trace-title">${escapeHtml(item.tool_name)} ${badge(item.status)}</div>
          <div class="trace-meta">${escapeHtml(item.endpoint_id)} / ${escapeHtml(item.operation_id)}</div>
          <div class="trace-meta">Политика: ${escapeHtml(item.policy_rule_id)} / попыток: ${escapeHtml(
            item.attempts,
          )} / длительность: ${escapeHtml(item.duration_ms)} мс</div>
        </div>
      `,
    )
    .join('');
}

function buildCopyText() {
  const analysis = state.analysis;
  if (!analysis) return '';
  const decision = analysis.ai_decision?.decision;
  const citations = analysis.ai_decision?.citations || [];
  const toolResults = analysis.tool_results || [];
  const approvalResults = Object.values(state.approvalResults);
  return [
    `Заявка: ${analysis.ticket_id}`,
    `Кейс: ${analysis.case_id || 'н/д'}`,
    `Состояние: ${analysis.workflow_state?.id || 'н/д'}`,
    `Решение: ${decision?.type || 'н/д'}`,
    `Кратко: ${decision?.summary || decision?.question || decision?.reason || 'н/д'}`,
    `Сообщение оператору: ${analysis.operator_message || 'н/д'}`,
    citations.length ? `Источники: ${citations.map((item) => `${item.title} (${item.url})`).join('; ')}` : 'Источники: нет',
    toolResults.length ? `Результаты инструментов: ${toolResults.map((item) => `${item.tool_name}=${item.status}`).join(', ')}` : 'Результаты инструментов: нет',
    approvalResults.length
      ? `Результаты согласований: ${approvalResults.map((item) => `${item.gate.action_id}=${item.gate.status}`).join(', ')}`
      : 'Результаты согласований: нет',
  ].join('\n');
}

async function loadKnowledgeStatus() {
  try {
    state.knowledge = await api('/knowledge/status');
    elements.apiStatus.textContent = 'API готов';
  } catch (error) {
    elements.apiStatus.textContent = `Ошибка API: ${error.message}`;
    state.knowledge = null;
  }
  renderKnowledge();
}

async function analyzeTicket() {
  elements.analyzeButton.disabled = true;
  const payload = formPayload();
  try {
    state.approvalResults = {};
    state.feedback = null;
    state.ticketInput = payload;
    stopCasePolling();
    state.analysis = await api('/tickets/analyze', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    await refreshCase();
    startCasePolling();
  } catch (error) {
    state.feedback = null;
    state.caseRecord = null;
    state.caseTimeline = null;
    stopCasePolling();
    state.ticketInput = payload;
    state.analysis = {
      ticket_id: 'н/д',
      workflow_state: { id: 'error' },
      operator_message: error.message,
      ai_decision: { decision: { type: 'error', summary: error.message } },
      tool_trace: [],
      rag_trace: { status: 'error', matches: [], error_code: 'request_failed' },
      approval_requests: [],
    };
  } finally {
    elements.analyzeButton.disabled = false;
    renderAnalysis();
  }
}

async function submitFeedback(rating) {
  if (!state.analysis || !state.ticketInput) return;
  const correctedResponse = elements.correctedResponse.value.trim();
  const payload = compactObject({
    schema_version: '1.0',
    ticket_id: state.analysis.ticket_id,
    operator_id: elements.operatorId.value.trim() || 'operator-1',
    rating,
    ticket_input: state.ticketInput,
    analysis_snapshot: state.analysis,
    approval_snapshot: Object.keys(state.approvalResults).length ? state.approvalResults : undefined,
    operator_note: elements.feedbackNote.value.trim(),
    corrected_response: rating === 'edited' ? correctedResponse || buildCopyText() : undefined,
    extensions: {
      ui: 'operator-static-stage10',
      case_id: state.analysis.case_id,
    },
  });
  try {
    state.feedback = await api('/feedback', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  } catch (error) {
    state.feedback = null;
    elements.feedbackStatus.textContent = `Ошибка обратной связи: ${error.message}`;
    return;
  }
  await refreshCase();
  renderFeedback();
}

async function refreshCase() {
  const caseId = state.analysis?.case_id;
  if (!caseId) {
    state.caseRecord = null;
    state.caseTimeline = null;
    renderCase();
    return;
  }
  try {
    const [caseRecord, caseTimeline] = await Promise.all([
      api(`/cases/${encodeURIComponent(caseId)}`),
      api(`/cases/${encodeURIComponent(caseId)}/timeline`),
    ]);
    state.caseRecord = caseRecord;
    state.caseTimeline = caseTimeline;
  } catch (error) {
    state.caseRecord = null;
    state.caseTimeline = null;
    elements.caseStatus.textContent = `Ошибка кейса: ${error.message}`;
    return;
  }
  renderCase();
}

function startCasePolling() {
  stopCasePolling();
  if (!state.analysis?.case_id) return;
  state.casePoll = window.setInterval(refreshCase, 4000);
}

function stopCasePolling() {
  if (!state.casePoll) return;
  window.clearInterval(state.casePoll);
  state.casePoll = null;
}

async function rebuildKnowledge() {
  elements.rebuildButton.disabled = true;
  try {
    const result = await api('/knowledge/rebuild', {
      method: 'POST',
      body: JSON.stringify({ operator_id: elements.operatorId.value.trim() || 'operator-1' }),
    });
    state.knowledge = {
      schema_version: '1.0',
      status: result.status,
      index_path: result.index_path,
      index_manifest: result.index_manifest,
    };
  } catch (error) {
    state.knowledge = {
      schema_version: '1.0',
      status: 'error',
      index_path: 'н/д',
      error: { code: 'rebuild_failed', message: error.message },
    };
  } finally {
    elements.rebuildButton.disabled = false;
    renderKnowledge();
  }
}

async function decideApproval(approvalId, decision) {
  const commentInput = document.getElementById(`comment-${approvalId}`);
  const payload = compactObject({
    decision,
    operator_id: elements.operatorId.value.trim() || 'operator-1',
    comment: commentInput?.value,
  });
  try {
    state.approvalResults[approvalId] = await api(`/approvals/${approvalId}/decision`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  } catch (error) {
    state.approvalResults[approvalId] = {
      gate: { action_id: approvalId, status: 'failed' },
      tool_result: { status: 'error', error: { message: error.message } },
    };
  }
  await refreshCase();
  renderAnalysis();
}

async function copyResult() {
  const value = elements.copyText.textContent;
  if (!value) return;
  try {
    await navigator.clipboard.writeText(value);
  } catch {
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(elements.copyText);
    selection.removeAllRanges();
    selection.addRange(range);
  }
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

elements.analyzeButton.addEventListener('click', analyzeTicket);
elements.rebuildButton.addEventListener('click', rebuildKnowledge);
elements.copyButton.addEventListener('click', copyResult);
elements.feedbackButtons.forEach((button) => {
  button.addEventListener('click', () => submitFeedback(button.dataset.feedbackRating));
});
elements.tabs.forEach((tab) => {
  tab.addEventListener('click', () => {
    state.activeTab = tab.dataset.tab;
    renderTrace();
  });
});

renderAnalysis();
loadKnowledgeStatus();
