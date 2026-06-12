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
  activeMainTab: 'steps',
  workflowStarted: false,
  ticketTextSnapshot: '',
  scenarios: [],
  scenarioId: 'password_reset',
  scenarioDetail: null,
  scenarioSimulation: null,
  dryRunEnabled: true,
  testRunMode: 'config_check',
  providedSlots: {},
  activeDebugTab: 'single',
  debugProfiles: null,
  debugSimulations: [],
  debugSimulation: null,
  debugTrace: null,
  debugWaits: null,
  integrationEndpoints: [],
  endpointCaptures: null,
};

const elements = {
  debugPageTitle: document.getElementById('debugPageTitle'),
  apiStatus: document.getElementById('apiStatus'),
  operatorId: document.getElementById('operatorId'),
  ticketForm: document.getElementById('ticketForm'),
  ticketText: document.getElementById('ticketText'),
  scenarioSelect: document.getElementById('scenarioSelect'),
  dryRunToggle: document.getElementById('dryRunToggle'),
  testRunMode: document.getElementById('testRunMode'),
  allowLlmToggle: document.getElementById('allowLlmToggle'),
  allowReadonlyToggle: document.getElementById('allowReadonlyToggle'),
  allowMockToggle: document.getElementById('allowMockToggle'),
  allowActionApprovalToggle: document.getElementById('allowActionApprovalToggle'),
  loadScenarioButton: document.getElementById('loadScenarioButton'),
  enrichButton: document.getElementById('enrichButton'),
  resetSlotsButton: document.getElementById('resetSlotsButton'),
  analyzeButton: document.getElementById('analyzeButton'),
  questionView: document.getElementById('questionView'),
  slotAnswers: document.getElementById('slotAnswers'),
  scenarioSummary: document.getElementById('scenarioSummary'),
  stepsView: document.getElementById('stepsView'),
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
  mainTabs: Array.from(document.querySelectorAll('[data-main-tab]')),
  mainPanels: Array.from(document.querySelectorAll('[data-main-panel]')),
  debugTabs: Array.from(document.querySelectorAll('[data-debug-tab]')),
  debugPanels: Array.from(document.querySelectorAll('[data-debug-panel]')),
  debugFlowScenario: document.getElementById('debugFlowScenario'),
  debugFlowCount: document.getElementById('debugFlowCount'),
  debugFlowSeed: document.getElementById('debugFlowSeed'),
  debugFlowWrongDepartment: document.getElementById('debugFlowWrongDepartment'),
  debugPrepareButton: document.getElementById('debugPrepareButton'),
  debugStartButton: document.getElementById('debugStartButton'),
  debugPauseButton: document.getElementById('debugPauseButton'),
  debugCancelButton: document.getElementById('debugCancelButton'),
  debugSimulationStatus: document.getElementById('debugSimulationStatus'),
  debugSimulationItems: document.getElementById('debugSimulationItems'),
  debugTraceRunSelect: document.getElementById('debugTraceRunSelect'),
  debugLoadTraceButton: document.getElementById('debugLoadTraceButton'),
  debugTraceCaseId: document.getElementById('debugTraceCaseId'),
  debugLoadCaseTraceButton: document.getElementById('debugLoadCaseTraceButton'),
  debugCaseTraceView: document.getElementById('debugCaseTraceView'),
  debugWaitsRefreshButton: document.getElementById('debugWaitsRefreshButton'),
  debugWaitsView: document.getElementById('debugWaitsView'),
  captureEndpointSelect: document.getElementById('captureEndpointSelect'),
  captureOperationSelect: document.getElementById('captureOperationSelect'),
  captureStartButton: document.getElementById('captureStartButton'),
  captureStopSessionSelect: document.getElementById('captureStopSessionSelect'),
  captureStopButton: document.getElementById('captureStopButton'),
  captureRefreshButton: document.getElementById('captureRefreshButton'),
  captureStatus: document.getElementById('captureStatus'),
  captureSessions: document.getElementById('captureSessions'),
  captureList: document.getElementById('captureList'),
};

const scenarioApiBase = '/debug';

const visibleLabels = {
  active: 'активно',
  auto: 'авто',
  auto_agent: 'автоагент',
  auto_fill_candidate: 'кандидат автозаполнения',
  blocked: 'заблокировано',
  continue_slot_filling: 'нужно обогащение',
  blocked_by_configuration: 'ошибка конфигурации',
  completed: 'выполнено',
  draft: 'черновик',
  error: 'ошибка',
  failed: 'ошибка',
  escalated: 'требуется эскалация',
  cancel: 'отменить',
  incomplete: 'неполно',
  info: 'информация',
  agent_with_confirmation: 'агент + подтверждение',
  human_review: 'человек + подсказка',
  major_incident: 'Major Incident',
  missing: 'требуется ответ',
  model_unavailable: 'модель недоступна',
  operator_approval: 'согласование оператора',
  approval_required: 'нужно подтверждение',
  operator_manual: 'ручное заполнение оператором',
  optional: 'необязательный',
  p1: 'P1',
  p2: 'P2',
  p3: 'P3',
  p4: 'P4',
  partial: 'частично',
  pending_auto_fill: 'ожидает автозаполнения',
  pending: 'ожидает',
  planned: 'запланировано',
  provided: 'заполнено',
  ready: 'готово',
  ready_for_react: 'готово к ReAct',
  required: 'обязательный',
  resolution_pending: 'ожидает разрешения',
  skipped: 'пропущено',
  slot_autofill: 'ReAct-автозаполнение',
  started: 'запущено',
  filled_by_slot_autofill: 'заполнено ReAct-автозаполнением',
  missing_required_result_field: 'нет обязательного поля результата',
  needs_review: 'требуется эскалация',
  extraction_pending: 'ожидает извлечения',
  filled_by_model: 'заполнено моделью',
  candidate_below_threshold: 'результат ниже порога',
  waiting_operator_approval: 'ожидает подтверждения',
  external_event_wait: 'ожидание external event',
  timer_wait: 'таймер/повторная проверка',
  external_event: 'external event/callback',
  sync: 'синхронно',
  resume_agent: 'возобновить агента',
  escalate_operator: 'эскалировать оператору',
  mark_failed: 'завершить ошибкой',
  prepared: 'подготовлено',
  not_executed: 'не выполнялось',
  question_required: 'нужно уточнение у клиента',
  waiting: 'вопрос клиенту',
  resolution_profile: 'профиль разрешения',
  dry_run_simulated: 'смоделировано',
  success: 'завершено автоматически',
  unavailable: 'недоступно',
  user_question: 'вопрос клиенту',
  case: 'из данных обращения',
  llm_extraction: 'извлечение моделью',
  llm_extract: 'извлечение из текста',
  rag_search: 'поиск в базе знаний',
  case_read: 'чтение из данных обращения',
  tool_call: 'вызов инструмента',
  ticket_history_search: 'поиск по истории',
  condition: 'условие',
  clarification: 'уточнение',
  fill_slot: 'заполнение слота',
  operator_handoff: 'эскалация оператору',
  escalate: 'эскалация',
  online_interactive: 'онлайн-интерактивный',
  offline_interactive: 'офлайн-интерактивный',
  debug: 'отладочный режим',
  ask_end_user: 'вопрос клиенту',
  ask_operator: 'вопрос через оператора',
  show_debug_message: 'показать в отладке',
  save_context: 'сохранить контекст',
  create_draft: 'создать черновик',
  create_work_order: 'создать наряд',
  call_specialist: 'позвать специалиста',
  notify_on_call: 'оповестить дежурных',
  debug_stop: 'остановить с сообщением',
  standard_handoff: 'эскалация оператору',
  no_answer: 'нет ответа клиента',
  no: 'нет',
  policy_blocked: 'policy blocked',
  all_required_slots_filled: 'все обязательные слоты заполнены',
  tool_success: 'успешный результат инструмента',
  clarification_required: 'нужно уточнение у клиента',
  handoff_required: 'требуется эскалация оператору',
  iteration_limit: 'лимит итераций',
  consecutive_tool_errors: 'ошибки инструментов подряд',
  read_diagnostics: 'чтение и диагностика',
  knowledge_search: 'поиск в знаниях',
  external_status_check: 'проверка внешних систем',
  action_preparation: 'подготовка действия',
  state_changing_actions: 'действия с изменением состояния',
  communication_handoff: 'коммуникация и эскалация',
  react_call: 'ReAct-вызов чтения',
  client_question: 'вопрос клиенту',
  approval: 'согласование',
  timer: 'таймер',
  system_policy: 'политика системы',
  ticket_history: 'история заявок',
  case_data: 'данные обращения',
  auto_fill_if_confident: 'заполнить при достаточной уверенности',
  ask_clarification: 'уточнить',
  ask_disambiguation: 'уточнить выбор результата',
  empty_result: 'результат не найден',
  single_result: 'один результат',
  multiple_results: 'несколько результатов',
  accepted_by_rules: 'принято правилами',
  llm_required: 'нужна LLM-классификация',
  human_review_required: 'нужна проверка оператором',
  human_required: 'эскалировать оператору',
  yes: 'да',
};

const priorityGroupLabels = {
  who: 'кто',
  what: 'что',
  when: 'когда',
  where: 'где',
  context: 'контекст',
};

const fillMethodLabels = {
  user_question: 'вопрос клиенту',
  case: 'из данных обращения',
  llm_extraction: 'извлечение моделью',
  slot_autofill: 'ReAct-автозаполнение',
  resolution_profile: 'профиль разрешения',
  operator_manual: 'ручное заполнение оператором',
};

const stopConditionLabels = {
  all_required_slots_filled: 'все обязательные слоты заполнены',
  tool_success: 'получен успешный результат инструмента',
  clarification_required: 'нужно уточнение у клиента',
  handoff_required: 'требуется эскалация оператору',
  iteration_limit: 'достигнут лимит итераций',
  consecutive_tool_errors: 'ошибки инструментов подряд',
};

const reactActionGroupLabels = {
  read_diagnostics: 'чтение и диагностика',
  knowledge_search: 'поиск в знаниях',
  external_status_check: 'проверка внешних систем',
  action_preparation: 'подготовка действия',
  state_changing_actions: 'действия с изменением состояния',
  communication_handoff: 'коммуникация и эскалация',
};

const eventTypeLabels = {
  case_created: 'Кейс создан',
  analysis_completed: 'Анализ завершен',
  action_gate_created: 'Создано согласование',
  approval_decisioned: 'Согласование обработано',
  tool_result_recorded: 'Результат инструмента записан',
  integration_callback_received: 'Получен callback интеграции',
  feedback_recorded: 'Обратная связь записана',
  evaluation_result_recorded: 'Результат оценки записан',
};

const actorTypeLabels = {
  system: 'система',
  system_policy: 'политика',
  operator: 'оператор',
  admin: 'администратор',
  endpoint: 'подключение',
  callback: 'callback',
};

const testRunModeDefaults = {
  config_check: {
    allow_llm: false,
    allow_readonly_integrations: false,
    allow_mock_integrations: false,
    allow_action_with_approval: false,
  },
  llm: {
    allow_llm: true,
    allow_readonly_integrations: false,
    allow_mock_integrations: false,
    allow_action_with_approval: false,
  },
  llm_readonly: {
    allow_llm: true,
    allow_readonly_integrations: true,
    allow_mock_integrations: true,
    allow_action_with_approval: false,
  },
  approval_debug: {
    allow_llm: true,
    allow_readonly_integrations: true,
    allow_mock_integrations: true,
    allow_action_with_approval: true,
  },
};

function compactObject(value) {
  return Object.fromEntries(
    Object.entries(value).filter(([, item]) => item !== undefined && item !== null && item !== ''),
  );
}

function currentTestRunOptions() {
  return {
    run_mode: elements.testRunMode?.value || state.testRunMode || 'config_check',
    allow_llm: elements.allowLlmToggle?.checked === true,
    allow_readonly_integrations: elements.allowReadonlyToggle?.checked === true,
    allow_mock_integrations: elements.allowMockToggle?.checked === true,
    allow_action_with_approval: elements.allowActionApprovalToggle?.checked === true,
  };
}

function syncTestRunModeDefaults() {
  state.testRunMode = elements.testRunMode?.value || 'config_check';
  const defaults = testRunModeDefaults[state.testRunMode] || testRunModeDefaults.config_check;
  if (elements.allowLlmToggle) elements.allowLlmToggle.checked = defaults.allow_llm;
  if (elements.allowReadonlyToggle) elements.allowReadonlyToggle.checked = defaults.allow_readonly_integrations;
  if (elements.allowMockToggle) elements.allowMockToggle.checked = defaults.allow_mock_integrations;
  if (elements.allowActionApprovalToggle) elements.allowActionApprovalToggle.checked = defaults.allow_action_with_approval;
}

function apiHeaders(extra = {}) {
  const actorId = elements.operatorId.value.trim() || 'admin-1';
  return {
    'Content-Type': 'application/json',
    'X-ServiceDesk-Actor': actorId,
    'X-ServiceDesk-Session': `debug-ui:${actorId}`,
    ...extra,
  };
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: apiHeaders(options.headers || {}),
  });
  const text = await response.text();
  const body = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const message = body.detail?.message || body.detail?.errors?.join('; ') || response.statusText;
    throw new Error(message);
  }
  return body;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function badge(status) {
  const label = String(status || 'info');
  const normalized = label.replace(/[^a-zа-яё0-9_-]/gi, '_').toLowerCase();
  return `<span class="badge ${escapeHtml(normalized)}">${escapeHtml(visibleLabels[normalized] || label)}</span>`;
}

function stripHtml(value) {
  const template = document.createElement('template');
  template.innerHTML = String(value ?? '');
  return template.content.textContent.trim();
}

function statusStrip(items) {
  const visibleItems = items.filter(Boolean).slice(0, 5);
  if (!visibleItems.length) return '<div class="empty">Нет статуса</div>';
  return `
    <div class="status-strip">
      ${visibleItems.map((item) => `
        <div class="status-strip-item ${item.risk ? 'risk' : ''}">
          <div class="status-strip-label">${escapeHtml(item.label)}</div>
          <div class="status-strip-value">${item.value}</div>
        </div>
      `).join('')}
    </div>
  `;
}

function metric(label, value) {
  return `
    <div class="metric">
      <div class="metric-label">${escapeHtml(label)}</div>
      <div class="metric-value">${value}</div>
    </div>
  `;
}

function mobileResourceCards(headers, rows) {
  return `
    <div class="resource-card-list" aria-label="Список ресурсов">
      ${rows.map((row) => {
        const actionIndex = row.findIndex((cell) => String(cell).includes('<button'));
        const statusIndex = row.findIndex((cell) => String(cell).includes('class="badge'));
        const titleIndex = row.findIndex((cell, index) => index !== actionIndex && index !== statusIndex && stripHtml(cell));
        const title = titleIndex >= 0 ? row[titleIndex] : row[0];
        const facts = row
          .map((cell, index) => ({ cell, index }))
          .filter(({ cell, index }) => index !== actionIndex && index !== titleIndex && index !== statusIndex && stripHtml(cell))
          .slice(0, 4);
        return `
          <article class="resource-card">
            <div class="resource-card-title">${title}</div>
            ${statusIndex >= 0 ? `<div class="resource-card-status">${row[statusIndex]}</div>` : ''}
            ${facts.length ? `<div class="resource-card-facts">
              ${facts.map(({ cell, index }) => `
                <div class="resource-card-fact">
                  <div class="resource-card-label">${escapeHtml(headers[index] || '')}</div>
                  <div class="resource-card-value">${cell}</div>
                </div>
              `).join('')}
            </div>` : ''}
            ${actionIndex >= 0 ? `<div class="resource-card-actions">${row[actionIndex]}</div>` : ''}
          </article>
        `;
      }).join('')}
    </div>
  `;
}

function table(headers, rows) {
  if (!rows.length) {
    return '<div class="empty">Нет данных</div>';
  }
  return `
    <div class="table-wrap has-resource-cards">
      <table>
        <thead>
          <tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join('')}</tr>
        </thead>
        <tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody>
      </table>
      ${mobileResourceCards(headers, rows)}
    </div>
  `;
}

function traceJson(value) {
  if (value === undefined || value === null || value === '') {
    return 'н/д';
  }
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return escapeHtml(value);
  }
  return `<pre class="trace-payload">${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
}

function traceCallLabel(item) {
  const details = item.details || {};
  const callName = details.react_call || details.tool_name || '';
  const endpoint = details.endpoint_id || '';
  const operation = details.operation_id || '';
  if (callName && endpoint && operation) {
    return `${callName} -> ${endpoint}/${operation}`;
  }
  if (callName) return callName;
  if (endpoint || operation) return `${endpoint || 'н/д'}/${operation || 'н/д'}`;
  if (details.provider || details.model) return `${details.provider || 'LLM'} / ${details.model || 'модель не указана'}`;
  return '';
}

function traceParameters(item) {
  const details = item.details || {};
  if (details.parameters !== undefined && details.parameter_sources !== undefined) {
    return {
      'значения параметров': details.parameters,
      'источники параметров': details.parameter_sources,
    };
  }
  if (details.parameters !== undefined) return details.parameters;
  if (details.parameter_sources !== undefined) return details.parameter_sources;
  const fallback = {};
  for (const key of ['missing_parameters', 'missing_slots', 'missing_parameter_slots', 'slot_ids']) {
    if (details[key] !== undefined) fallback[key] = details[key];
  }
  return Object.keys(fallback).length ? fallback : '';
}

function traceResult(item) {
  const details = item.details || {};
  if (details.filled_slot_values !== undefined) {
    return {
      'заполнено в слоты': details.filled_slot_values,
      'ответ операции': details.result,
    };
  }
  if (details.result !== undefined) return details.result;
  if (details.output_values !== undefined) return details.output_values;
  const fallback = {};
  for (const key of [
    'planned_wait',
    'completion_policy',
    'output_slots',
    'missing_required_result_fields',
    'candidate_count',
    'confidence',
    'decision',
    'positive_hits',
    'negative_hits',
  ]) {
    if (details[key] !== undefined) fallback[key] = details[key];
  }
  return Object.keys(fallback).length ? fallback : '';
}

function formatTraceInlineValue(value) {
  if (value === undefined || value === null || value === '') return 'н/д';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value);
}

function renderFilledSlotValues(items = []) {
  if (!Array.isArray(items) || !items.length) return '';
  return `
    <div class="filled-slot-list">
      <div class="metric-label">Заполнено</div>
      ${items.map((item) => `
        <div class="filled-slot-row">
          <strong>${escapeHtml(item.target_slot || 'слот не задан')}</strong>
          <span>${escapeHtml(formatTraceInlineValue(item.value))}</span>
          <small>из поля результата ${escapeHtml(item.result_field || 'н/д')}</small>
        </div>
      `).join('')}
    </div>
  `;
}

function traceStatusHint(status) {
  const hints = {
    completed: 'Шаг выполнен успешно.',
    ready: 'Вызов подготовлен, но в dry-run не выполнялся.',
    blocked: 'Продолжение заблокировано настройками, политикой или недостающими параметрами.',
    skipped: 'Шаг пропущен выбранным режимом тестового прогона.',
    error: 'Шаг завершился ошибкой.',
    failed: 'Шаг завершился ошибкой.',
    approval_required: 'Требуется подтверждение оператора перед выполнением.',
    question_required: 'Нужно уточнение у клиента.',
    waiting: 'Открыто ожидание результата или ответа.',
    started: 'Шаг начат.',
  };
  return hints[String(status || '').toLowerCase()] || '';
}

function renderDryRunTraceItem(item, index) {
  const callLabel = traceCallLabel(item);
  const parameters = traceParameters(item);
  const result = traceResult(item);
  const filledSlotValues = item.details?.filled_slot_values || [];
  const statusHint = traceStatusHint(item.status);
  return `
    <div class="dry-run-trace-item">
      <div class="dry-run-trace-head">
        <span class="trace-step">#${index + 1} / шаг ${escapeHtml(item.step || 'н/д')}</span>
        <strong>${escapeHtml(item.title || 'Событие')}</strong>
        ${badge(item.status || 'info')}
      </div>
      <div class="trace-meta">${escapeHtml(item.message || '')}</div>
      ${statusHint ? `<div class="trace-hint">${escapeHtml(statusHint)}</div>` : ''}
      ${renderFilledSlotValues(filledSlotValues)}
      <div class="dry-run-trace-grid">
        <div>
          <div class="metric-label">Что вызывалось</div>
          <div class="trace-value">${escapeHtml(callLabel || 'нет внешнего вызова')}</div>
        </div>
        <div>
          <div class="metric-label">Параметры</div>
          <div class="trace-value">${traceJson(parameters)}</div>
        </div>
        <div>
          <div class="metric-label">Результат</div>
          <div class="trace-value">${traceJson(result)}</div>
        </div>
      </div>
    </div>
  `;
}

function renderDryRunTracePanel(simulation) {
  const trace = simulation?.execution_trace || [];
  if (!trace.length) {
    return `
      <details class="trace-run-block" open>
        <summary>
          <span class="trace-run-title">Трасса тестового прогона</span>
          ${badge('pending')}
        </summary>
        <div class="trace-run-body"><div class="empty">Тестовый прогон еще не выполнялся</div></div>
      </details>
    `;
  }
  return `
    <details class="trace-run-block" open>
      <summary>
        <span class="trace-run-title">Трасса тестового прогона</span>
        <span class="summary-line">${trace.length} событий</span>
      </summary>
      <div class="trace-run-body">
        ${trace.map((item, index) => renderDryRunTraceItem(item, index)).join('')}
      </div>
    </details>
  `;
}

function stepBlock(number, title, status, body) {
  return `
    <details class="step-block">
      <summary>
        <span class="step-number">${number}</span>
        <span class="step-title">${escapeHtml(title)}</span>
        ${status ? badge(status) : ''}
      </summary>
      <div class="step-body">${body}</div>
    </details>
  `;
}

function formatList(items, mapper = (item) => item) {
  const values = (items || []).map(mapper).filter(Boolean);
  return values.length ? values.map(escapeHtml).join(', ') : 'н/д';
}

function formatRuleHits(items) {
  return formatList(items, (item) => item.explanation || item.text);
}

function formatMap(map) {
  const entries = Object.entries(map || {});
  return entries.length
    ? entries.map(([key, value]) => `${escapeHtml(key)} = ${escapeHtml(value)}`).join(', ')
    : 'н/д';
}

function normalizeWaitingPolicy(waitingPolicy = {}) {
  return {
    first_reminder_after_seconds: waitingPolicy.first_reminder_after_seconds ?? 0,
    discussion_timeout_seconds: waitingPolicy.discussion_timeout_seconds ?? 0,
    sla_elapsed_percent_threshold: waitingPolicy.sla_elapsed_percent_threshold ?? 0,
    on_no_answer: waitingPolicy.on_no_answer || 'debug_stop',
    auto_close_requires_client_confirmation: waitingPolicy.auto_close_requires_client_confirmation ?? true,
    pause_sla_on_client_wait: waitingPolicy.pause_sla_on_client_wait ?? true,
    client_wait_auto_close_after_hours: waitingPolicy.client_wait_auto_close_after_hours ?? 24,
  };
}

function clientAgentOutcome(simulation) {
  if (!simulation) {
    return {
      status: 'pending',
      label: 'Ожидает запуска',
      summary: 'Тестовый прогон еще не выполнялся.',
      next_step: 'Введите текст заявки и нажмите «Анализировать».',
    };
  }
  if (simulation.agent_outcome) return simulation.agent_outcome;
  if (simulation.error) {
    return {
      status: 'error',
      label: 'Ошибка',
      summary: simulation.error.message || 'Тестовый прогон завершился ошибкой.',
      next_step: 'Исправьте ошибку и повторите запуск.',
    };
  }
  if (simulation.operator_escalation?.required) {
    return {
      status: 'escalated',
      label: 'Эскалировано',
      summary: simulation.operator_escalation.reason || 'Агент подготовил передачу оператору.',
      next_step: 'Проверьте пакет передачи и канал эскалации.',
      missing_slots: simulation.missing_slots || [],
    };
  }
  if (simulation.awaiting_client_response || simulation.next_question) {
    return {
      status: 'waiting',
      label: 'Ожидает клиента',
      summary: 'Агент сформировал вопрос и не может продолжить без ответа клиента.',
      next_step: simulation.next_question || 'Передайте вопрос клиенту и продолжите после ответа.',
      missing_slots: simulation.missing_slots || [],
    };
  }
  if ((simulation.missing_slots || []).length || ['pending_auto_fill', 'waiting_operator_approval'].includes(simulation.final_decision)) {
    if ((simulation.missing_slots || []).length) {
      return {
        status: 'waiting',
        label: 'Вопрос клиенту',
        summary: 'Агенту не хватает обязательных данных: нужно задать вопрос клиенту.',
        next_step: simulation.next_question || 'Передайте вопрос клиенту и продолжите после ответа.',
        missing_slots: simulation.missing_slots || [],
      };
    }
    return {
      status: 'escalated',
      label: 'Требуется эскалация',
      summary: 'Агент не может надежно продолжить автоматически: требуется передача оператору.',
      next_step: 'Проверьте пакет передачи и трассу обработки.',
      missing_slots: simulation.missing_slots || [],
    };
  }
  return {
    status: 'success',
    label: 'Завершено автоматически',
    summary: 'Агент собрал обязательные данные и завершил тестовый прогон автоматически.',
    next_step: 'Проверьте трассу и итоговые данные при необходимости.',
  };
}

function outcomeList(values = []) {
  return values.length ? values.map(escapeHtml).join(', ') : 'нет';
}

function outcomeCallLabel(item) {
  if (!item) return '';
  const name = item.react_call || item.tool_name || 'ReAct-вызов';
  const endpoint = item.endpoint_id || '';
  const operation = item.operation_id || '';
  return endpoint || operation
    ? `${name} -> ${endpoint || 'н/д'}/${operation || 'н/д'}`
    : name;
}

function renderAgentOutcomePanel(simulation) {
  const outcome = clientAgentOutcome(simulation);
  const readyCalls = outcome.ready_react_calls || [];
  const blockedCalls = outcome.blocked_react_calls || [];
  const details = [
    metric('Статус агента', badge(outcome.status)),
    metric('Заполнено слотов', escapeHtml(outcomeList(outcome.filled_slots || []))),
    metric('Не хватает слотов', escapeHtml(outcomeList(outcome.missing_slots || []))),
    metric('Готовые ReAct-вызовы', escapeHtml(outcomeList(readyCalls.map(outcomeCallLabel)))),
    metric('Заблокированные вызовы', escapeHtml(outcomeList(blockedCalls.map(outcomeCallLabel)))),
  ].join('');
  return `
    <section class="agent-outcome agent-outcome-${escapeHtml(outcome.status || 'pending')}">
      <div class="agent-outcome-header">
        <h3>Итог работы агента</h3>
        ${badge(outcome.status || 'pending')}
      </div>
      <p>${escapeHtml(outcome.summary || outcome.label || 'Итог не рассчитан')}</p>
      <div class="agent-outcome-next">
        <div class="metric-label">Следующий шаг</div>
        <div>${escapeHtml(outcome.next_step || 'Проверьте трассу тестового прогона.')}</div>
      </div>
      <div class="grid">${details}</div>
    </section>
  `;
}

function scenarioName() {
  return state.scenarioDetail?.scenario?.display_name || state.scenarioId || 'н/д';
}

function orderedSlots(slotSchema) {
  const slots = slotSchema?.slots || [];
  const byId = Object.fromEntries(slots.map((slot) => [slot.slot_id, slot]));
  const ordered = (slotSchema?.question_order || []).map((slotId) => byId[slotId]).filter(Boolean);
  const rest = slots.filter((slot) => !ordered.some((orderedSlot) => orderedSlot.slot_id === slot.slot_id));
  return [...ordered, ...rest];
}

function slotLabel(slotSchema, slotId) {
  return (slotSchema?.slots || []).find((slot) => slot.slot_id === slotId)?.display_name || slotId;
}

function slotStatus(slot, simulation = state.scenarioSimulation) {
  const resolution = slotResolutionState(slot, simulation);
  if (resolution?.status) return resolution.status;
  const simulationValue = simulation?.slot_values?.[slot.slot_id];
  if (simulationValue?.status) return simulationValue.status;
  if (!slot.required) return 'optional';
  return 'missing';
}

function slotDisplayValue(slot, simulation = state.scenarioSimulation, detail = state.scenarioDetail) {
  const simulationValue = simulation?.slot_values?.[slot.slot_id];
  if (simulationValue?.value !== undefined && simulationValue?.value !== null && simulationValue?.value !== '') {
    return simulationValue.value;
  }
  const profile = slotResolutionProfile(slot, detail);
  if (profile) return profile.display_name;
  if (slot.case_source_ref) return slot.case_source_ref;
  if (slot.extraction_instruction) return slot.extraction_instruction;
  if (slot.operator_hint) return slot.operator_hint;
  return 'н/д';
}

function readableSlotValue(value) {
  if (value === undefined || value === null || value === '') return '';
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function slotResultValue(slot, simulation = state.scenarioSimulation, providedSlots = state.providedSlots) {
  const simulationValue = simulation?.slot_values?.[slot.slot_id];
  const result = readableSlotValue(simulationValue?.value);
  const provided = readableSlotValue(providedSlots[slot.slot_id]);
  return result || provided || 'не заполнен';
}

function slotFillMethod(slot) {
  if (slot.fill_method) return slot.fill_method;
  if (slot.source === 'user_question') return 'user_question';
  if (slot.source === 'case') return 'case';
  if (slot.source === 'llm') return 'llm_extraction';
  return 'resolution_profile';
}

function slotResolutionProfile(slot, detail = state.scenarioDetail) {
  return (detail?.attribute_resolution_profiles || [])
    .find((profile) => profile.profile_id === slot.resolution_profile_id);
}

function slotResolutionState(slot, simulation = state.scenarioSimulation) {
  return simulation?.resolution_state?.[slot.slot_id] || null;
}

function resolutionQuestion(slot, simulation) {
  const stateItem = slotResolutionState(slot, simulation);
  return stateItem?.pending_question || simulation?.next_question || slotQuestionText(slot) || '';
}

function slotQuestionText(slot) {
  const fillMethod = slotFillMethod(slot);
  if (fillMethod === 'user_question') return slot.user_question || slot.question;
  if (fillMethod === 'resolution_profile') return slot.fallback_question || slot.question;
  if (fillMethod === 'operator_manual') return slot.operator_hint || slot.question;
  return '';
}

function slotById(detail, slotId) {
  return (detail?.slot_schema?.slots || []).find((item) => item.slot_id === slotId) || null;
}

function answerableMissingSlotIds(simulation = state.scenarioSimulation, detail = state.scenarioDetail) {
  return (simulation?.missing_slots || []).filter((slotId) => {
    const slot = slotById(detail, slotId);
    return slot && Boolean(resolutionQuestion(slot, simulation));
  });
}

function automaticMissingSlotIds(simulation = state.scenarioSimulation, detail = state.scenarioDetail) {
  const answerable = new Set(answerableMissingSlotIds(simulation, detail));
  return (simulation?.missing_slots || []).filter((slotId) => !answerable.has(slotId));
}

function resolutionProgressText(item) {
  if (!item) return 'н/д';
  const summary = item.result_summary || item.candidate_summary || {};
  if (item.llm_decision) {
    const count = summary.item_count ?? summary.count ?? item.candidate_count;
    const decision = item.llm_decision.decision || item.decision;
    const reason = item.llm_decision.reason || item.reason || '';
    return `результатов: ${count ?? 'н/д'} -> ${visibleLabels[decision] || decision}${reason ? `; ${reason}` : ''}`;
  }
  if (item.decision) {
    const count = summary.item_count ?? summary.count ?? item.candidate_count;
    const objectFound = summary.object_found;
    const prefix = summary.result_type === 'object'
      ? `объект найден: ${objectFound === undefined ? 'н/д' : (objectFound ? 'да' : 'нет')}`
      : `результатов: ${count ?? 'н/д'}`;
    return `${prefix} -> ${visibleLabels[item.decision] || item.decision}`;
  }
  const completed = (item.completed_steps || [])
    .map((step) => step.display_name)
    .join(' -> ');
  const current = item.current_step_name || 'ожидает запуска';
  return completed ? `${completed} -> ${current}` : current;
}

function resolutionEnrichmentLabel(steps = []) {
  if (!steps.length) return 'нет ReAct-вызовов';
  return steps
    .map((step, index) => `${step.step_name || step.react_call || `Шаг ${index + 1}`} (${step.step_id || `step${index + 1}`})`)
    .join('; ');
}

function formatOutputValues(values = {}) {
  const entries = Object.entries(values || {});
  if (!entries.length) return 'н/д';
  return entries.map(([key, value]) => `${key}: ${value}`).join('; ');
}

function formatResolutionOutputSlots(rules = []) {
  if (!rules.length) return 'н/д';
  return rules
    .slice()
    .sort((left, right) => (left.order || 0) - (right.order || 0))
    .map((rule) => `${rule.order || '?'} ${rule.slot_id}${rule.required_for_success ? ' *' : ''}`)
    .join('; ');
}

function formatMissingAutofillResultFields(fields = []) {
  return formatList(fields, (item) => {
    if (typeof item === 'string') return item;
    const resultField = item.result_field || 'поле не задано';
    const targetSlot = item.target_slot ? ` -> ${item.target_slot}` : '';
    return `${resultField}${targetSlot}`;
  });
}

function formatAutofillFilledSlots(item = {}) {
  const filled = item.filled_slot_values || [];
  if (filled.length) {
    return filled
      .map((slot) => `${slot.target_slot}: ${formatTraceInlineValue(slot.value)} <- ${slot.result_field}`)
      .join('; ');
  }
  return formatOutputValues(item.output_values || {});
}

function formatDurationSeconds(seconds) {
  const value = Number(seconds || 0);
  if (!value) return 'нет ожидания';
  if (value % 86400 === 0) return `${value / 86400} д`;
  if (value % 3600 === 0) return `${value / 3600} ч`;
  if (value % 60 === 0) return `${value / 60} мин`;
  return `${value} сек`;
}

function completionPolicySummary(policy = {}) {
  const mode = policy.mode || 'sync';
  if (mode === 'sync') return 'синхронно';
  const parts = [
    visibleLabels[mode] || mode,
    `до ${formatDurationSeconds(policy.max_wait_seconds)}`,
  ];
  if (policy.check_interval_seconds) {
    parts.push(`проверка ${formatDurationSeconds(policy.check_interval_seconds)}`);
  }
  if (policy.expected_event_type) {
    parts.push(`событие ${policy.expected_event_type}`);
  }
  if (policy.timeout_action) {
    parts.push(`timeout: ${visibleLabels[policy.timeout_action] || policy.timeout_action}`);
  }
  return parts.join('; ');
}

function waitOriginSummary(origin = {}) {
  if (!origin || !origin.kind) return 'н/д';
  const kind = visibleLabels[origin.kind] || origin.kind;
  if (origin.kind === 'react_call') {
    const call = origin.react_call || origin.tool_name || 'ReAct-вызов';
    const endpoint = origin.endpoint_id || 'endpoint н/д';
    const operation = origin.operation_id || 'операция н/д';
    return `${kind}: ${call} -> ${endpoint}/${operation}`;
  }
  if (origin.kind === 'client_question') {
    return `${kind}: ${formatList(origin.slot_ids || origin.expected_slots || [])}`;
  }
  if (origin.kind === 'approval') {
    return `${kind}: ${formatList(origin.approval_ids || [])}`;
  }
  return `${kind}: ${origin.reason || origin.wait_type || 'н/д'}`;
}

function waitPlanSummary(wait = {}) {
  const parts = [
    visibleLabels[wait.wait_type] || wait.wait_type || 'ожидание',
    wait.max_wait_seconds ? `до ${formatDurationSeconds(wait.max_wait_seconds)}` : '',
    wait.check_interval_seconds ? `проверка ${formatDurationSeconds(wait.check_interval_seconds)}` : '',
    wait.expected_event_type ? `событие ${wait.expected_event_type}` : '',
    wait.timeout_action ? `timeout: ${visibleLabels[wait.timeout_action] || wait.timeout_action}` : '',
  ].filter(Boolean);
  return parts.join('; ') || 'н/д';
}

function launchRuntimeStatus(launch, simulation = state.scenarioSimulation) {
  const runtime = launchRuntimeSummary(launch, simulation);
  return runtime?.status || 'pending';
}

function launchRuntimeSummary(launch, simulation = state.scenarioSimulation) {
  const ready = simulation?.ready_tool_launches || [];
  const blocked = simulation?.blocked_tool_launches || [];
  const readyItem = ready.find((item) => item.launch_id === launch.launch_id);
  if (readyItem) return { ...readyItem, status: 'ready' };
  const blockedItem = blocked.find((item) => item.launch_id === launch.launch_id);
  if (blockedItem) return { ...blockedItem, status: 'blocked' };
  return { status: 'pending', missing_slots: [], unknown_required_slots: [] };
}

function renderScenarioSelect() {
  if (!state.scenarios.length) {
    elements.scenarioSelect.innerHTML = '<option value="">нет сценариев</option>';
    return;
  }
  elements.scenarioSelect.innerHTML = state.scenarios
    .map(
      (scenario) => `<option value="${escapeHtml(scenario.scenario_id)}" ${
        scenario.scenario_id === state.scenarioId ? 'selected' : ''
      }>${escapeHtml(scenario.display_name)}</option>`,
    )
    .join('');
}

function renderScenario() {
  renderScenarioSummary();
  renderQuestion();
  renderSlotAnswers();
  renderSteps();
  renderTrace();
  syncAnalyzeButton();
}

function renderScenarioSummary() {
  const detail = state.scenarioDetail;
  const simulation = state.scenarioSimulation;
  if (!state.workflowStarted) {
    elements.scenarioSummary.textContent = 'Работа начнется после кнопки «Анализировать»';
    return;
  }
  if (!detail) {
    elements.scenarioSummary.textContent = 'Сценарий не загружен';
    return;
  }
  const missingCount = simulation?.missing_slots?.length ?? 0;
  const answerableCount = answerableMissingSlotIds(simulation, detail).length;
  const route = detail.route || {};
  const channel = detail.interaction_channel || simulation?.interaction_channel || {};
  const mode = simulation?.simulation_options || currentTestRunOptions();
  elements.scenarioSummary.innerHTML = [
    `<span>${escapeHtml(detail.scenario.display_name)}</span>`,
    badge(detail.readiness?.status),
    badge(route.priority),
    `<span>${escapeHtml(channel.display_name || 'канал не задан')}</span>`,
    `<span>${escapeHtml(simulation?.simulation_options?.display_name || elements.testRunMode?.selectedOptions?.[0]?.textContent || 'тестовый прогон')}</span>`,
    badge(simulation?.final_decision || 'pending'),
    `<span>Недостающих слотов: ${escapeHtml(missingCount)}</span>`,
    `<span>Вопросов для уточнения: ${escapeHtml(answerableCount)}</span>`,
    mode.allow_llm ? '<span>LLM включен</span>' : '<span>LLM выключен</span>',
  ].join(' ');
}

function renderQuestion() {
  const simulation = state.scenarioSimulation;
  const detail = state.scenarioDetail;
  if (!state.workflowStarted) {
    elements.questionView.innerHTML = '<div class="empty">Введите текст заявки и нажмите «Анализировать»</div>';
    return;
  }
  if (!simulation || !detail) {
    elements.questionView.innerHTML = '<div class="empty">Вопрос появится после проверки слотов</div>';
    return;
  }
  const missingSlotIds = simulation.missing_slots || [];
  const answerableSlotIds = answerableMissingSlotIds(simulation, detail);
  const slotId = answerableSlotIds[0];
  if (!missingSlotIds.length) {
    elements.questionView.innerHTML = `
      <div class="question-ready">
        <div class="question-title">Данных достаточно для следующего шага</div>
        <div class="question-meta">Оператор может запускать анализ, а сценарий перейдет к ReAct-планированию.</div>
      </div>
    `;
    return;
  }
  if (!slotId) {
    const pendingRows = automaticMissingSlotIds(simulation, detail)
      .map((pendingSlotId) => {
        const slot = slotById(detail, pendingSlotId);
        const fillMethod = slot ? slotFillMethod(slot) : 'unknown';
        return `${slot?.display_name || pendingSlotId}: ${fillMethodLabels[fillMethod] || fillMethod}`;
      });
    elements.questionView.innerHTML = `
      <div class="question-title">Ожидает автоматического заполнения</div>
      <div class="question-text">В сценарии нет вопроса для оператора по недостающим слотам. Их должен заполнить настроенный способ: извлечение моделью, данные обращения или профиль разрешения атрибута.</div>
      <div class="question-meta">Слоты: ${formatList(pendingRows)}</div>
    `;
    return;
  }
  const slot = slotById(detail, slotId) || {};
  const resolution = slotResolutionState(slot);
  const resolutionMeta = resolution
    ? `
      <div class="question-meta">Профиль: ${escapeHtml(resolution.profile_name)} / попытка: ${escapeHtml(`${resolution.attempt || 1}/${resolution.max_attempts || 1}`)}</div>
      <div class="question-meta">${escapeHtml(resolution.reason || '')}</div>
    `
    : '';
  const channel = simulation.interaction_channel || detail.interaction_channel || {};
  const questionDelivery = simulation.question_delivery || channel.question_delivery || {};
  elements.questionView.innerHTML = `
    <div class="question-title">Нужно уточнение у клиента</div>
    <div class="question-text">${escapeHtml(resolutionQuestion(slot, simulation))}</div>
    <div class="question-meta">Слот: ${escapeHtml(slot.display_name || slotId)} / приоритет: ${
      escapeHtml(priorityGroupLabels[slot.priority_group] || slot.priority_group || 'н/д')
    }</div>
    <div class="question-meta">Канал: ${escapeHtml(channel.display_name || 'н/д')} / доставка вопроса клиенту: ${escapeHtml(visibleLabels[questionDelivery.action_type] || questionDelivery.action_type || 'н/д')}</div>
    ${resolutionMeta}
    <div class="question-input-row">
      <input id="slotAnswerInput" autocomplete="off" placeholder="Ответ клиента или введенный оператором ответ">
      <button id="addSlotAnswerButton" class="primary" type="button">Записать ответ</button>
    </div>
  `;
  document.getElementById('addSlotAnswerButton')?.addEventListener('click', addSlotAnswer);
  document.getElementById('slotAnswerInput')?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') addSlotAnswer();
  });
}

function renderSlotAnswers() {
  const detail = state.scenarioDetail;
  if (!detail) {
    elements.slotAnswers.innerHTML = '';
    return;
  }
  const rows = orderedSlots(detail.slot_schema).map((slot) => `
    <div class="slot-chip">
      <div>
        <strong>${escapeHtml(slot.display_name)}</strong>
        <span>${escapeHtml(priorityGroupLabels[slot.priority_group] || slot.priority_group || 'н/д')}</span>
      </div>
      ${badge(slotStatus(slot))}
      <div class="slot-value">${escapeHtml(slotDisplayValue(slot))}</div>
    </div>
  `);
  elements.slotAnswers.innerHTML = rows.join('');
}

function renderFiveStepView(detail, simulation, options = {}) {
  if (!detail) {
    return '<div class="empty">Сценарий не загружен</div>';
  }
  const providedSlots = options.providedSlots || state.providedSlots || {};
  const runtimeWaits = options.runtimeWaits || simulation?.runtime_waits || [];
  const scenarioTitle = options.scenarioName
    || detail.scenario?.display_name
    || detail.scenario?.scenario_id
    || 'н/д';
  const slotSchema = detail.slot_schema || {};
  const route = detail.route || {};
  const policy = detail.orchestrator_policy || {};
  const escalation = detail.escalation_policy || {};
  const channel = simulation?.interaction_channel || detail.interaction_channel || {};
  const waitingPolicy = normalizeWaitingPolicy(simulation?.waiting_policy || channel.waiting_policy || {});
  const escalationAction = simulation?.escalation_action || channel.escalation_action || {};
  const channelProfiles = simulation?.channel_action_profiles || detail.channel_action_profiles || {};
  const slotRows = orderedSlots(slotSchema).map((slot) => [
    escapeHtml(slot.display_name),
    escapeHtml(priorityGroupLabels[slot.priority_group] || slot.priority_group),
    badge(slot.required ? 'required' : 'optional'),
    escapeHtml(fillMethodLabels[slotFillMethod(slot)] || slotFillMethod(slot)),
    badge(slotStatus(slot, simulation)),
    escapeHtml(slotResultValue(slot, simulation, providedSlots)),
    escapeHtml(simulation?.slot_values?.[slot.slot_id]?.confidence ?? 'н/д'),
    escapeHtml(simulation?.slot_values?.[slot.slot_id]?.reason || 'н/д'),
  ]);
  const resolutionRows = (simulation?.attribute_resolution || []).map((item) => [
    escapeHtml(slotLabel(slotSchema, item.slot_id)),
    escapeHtml(item.profile_name),
    badge(item.status),
    escapeHtml(resolutionEnrichmentLabel(item.enrichment_steps || [])),
    escapeHtml(`${item.attempt || 1}/${item.max_attempts || 1}`),
    escapeHtml(resolutionProgressText(item)),
    escapeHtml(formatOutputValues(item.output_values)),
    escapeHtml(formatResolutionOutputSlots(item.output_slots_order)),
    escapeHtml(item.pending_question || item.fallback?.question || item.fallback?.action || 'н/д'),
    escapeHtml(formatList(item.human_resolution_policy?.handoff_package)),
  ]);
  const slotAutofillRows = (simulation?.slot_autofill || []).map((item) => [
    escapeHtml(item.profile_name || item.profile_id),
    escapeHtml(item.react_call || 'н/д'),
    badge(item.status),
    escapeHtml(formatAutofillFilledSlots(item)),
    escapeHtml(formatList(item.filled_slots)),
    escapeHtml(formatMissingAutofillResultFields(item.missing_required_result_fields)),
    escapeHtml(item.result_summary?.source || 'н/д'),
    escapeHtml(item.reason || 'н/д'),
  ]);
  const classification = simulation?.classification || {};
  const topRouteRows = (classification.top_routes || []).map((item) => [
    escapeHtml(item.display_name || item.route_id),
    badge(item.route),
    escapeHtml(item.priority || 'н/д'),
    escapeHtml(item.confidence ?? 'н/д'),
    escapeHtml(formatRuleHits(item.positive_hits)),
    escapeHtml(formatRuleHits(item.negative_hits)),
  ]);
  const routeRows = [
    ['Решение правил', escapeHtml(visibleLabels[classification.decision_level] || classification.decision_level || 'н/д')],
    ['Настроенный маршрут сценария', escapeHtml(classification.configured_route_id || route.route_id || 'н/д')],
    ['Совпадает со сценарием', escapeHtml(classification.matches_configured_route ? 'да' : 'нет')],
    ['Порог правил', escapeHtml(route.confidence?.rules_min ?? 'н/д')],
    ['LLM few-shot', escapeHtml(route.confidence?.llm_min ?? 'н/д')],
    ['Эскалация оператору ниже', escapeHtml(route.confidence?.human_handoff_below ?? 'н/д')],
    ['Top категорий', escapeHtml(route.top_categories_on_low_confidence ?? 'н/д')],
    ['Позитивные совпадения', escapeHtml(formatRuleHits(classification.positive_hits))],
    ['Негативные совпадения', escapeHtml(formatRuleHits(classification.negative_hits))],
    ['Блокирующие правила', escapeHtml(formatRuleHits(classification.blocked_by_rules))],
  ];
  const launchRows = (detail.tool_launches || []).map((launch) => {
    const runtime = launchRuntimeSummary(launch, simulation);
    const completionPolicy = runtime.completion_policy || launch.completion_policy || { mode: 'sync' };
    const blockReasons = [
      ...(runtime.missing_slots || []).map((slotId) => `не заполнен: ${slotId}`),
      ...(runtime.unknown_required_slots || []).map((slotId) => `нет в схеме: ${slotId}`),
    ];
    return [
      badge(runtime.status),
      escapeHtml(launch.tool_name),
      badge(launch.target_execution_level || launch.execution_level),
      escapeHtml(completionPolicySummary(completionPolicy)),
      escapeHtml(formatList(launch.required_slots)),
      formatMap(launch.parameter_bindings),
      escapeHtml(`${launch.endpoint_id} / ${launch.operation_id}`),
      badge(launch.risk_level),
      formatList(blockReasons),
    ];
  });
  const plannedWaitRows = (simulation?.planned_waits || [])
    .filter(Boolean)
    .map((wait) => [
      badge('planned'),
      badge(wait.wait_type),
      escapeHtml(waitOriginSummary(wait.origin)),
      escapeHtml(waitPlanSummary(wait)),
      escapeHtml(wait.expected_event_type || 'н/д'),
      escapeHtml(visibleLabels[wait.timeout_action] || wait.timeout_action || 'н/д'),
    ]);
  const runtimeWaitRows = (runtimeWaits || []).map((wait) => [
    badge(wait.status),
    badge(wait.wait_type),
    escapeHtml(waitOriginSummary(wait.origin)),
    escapeHtml(wait.deadline_at || 'н/д'),
    escapeHtml(wait.correlation_id || 'н/д'),
    escapeHtml((wait.payload || {}).last_external_event ? formatTraceInlineValue((wait.payload || {}).last_external_event) : 'н/д'),
  ]);
  const packageLabels = {
    slots: 'собранные слоты',
    react_history: 'история ReAct',
    tool_results: 'результаты инструментов',
    agent_hypothesis: 'гипотеза агента',
    sla_remaining: 'остаток SLA',
    user_notification: 'уведомление клиента',
  };
  const conditionLabels = {
    two_tool_errors: '2 ошибки инструментов подряд',
    iteration_limit: 'достигнут лимит ReAct-итераций',
    confidence_below_050: 'confidence ниже 0.50',
    affected_users_threshold: 'превышен порог Major Incident',
    policy_blocked: 'политика заблокировала автоисполнение',
  };
  const profileRows = ['standard_handoff', 'no_answer', 'major_incident', 'policy_blocked']
    .map((eventType) => {
      const profile = channelProfiles[eventType];
      if (!profile) return null;
      const action = profile.action || {};
      return [
        badge(eventType),
        escapeHtml(profile.display_name || profile.profile_id),
        badge(action.action_type || 'missing'),
        escapeHtml(action.tool_name ? `${action.tool_name} / ${action.endpoint_id || 'н/д'} / ${action.operation_id || 'н/д'}` : 'без ReAct-вызова'),
      ];
    })
    .filter(Boolean);
  return [
    renderAgentOutcomePanel(simulation),
    renderDryRunTracePanel(simulation),
    stepBlock(
      1,
      'Приём и нормализация',
      answerableMissingSlotIds(simulation, detail).length
        ? 'missing'
        : (simulation?.missing_slots?.length ? 'partial' : 'ready'),
      `<div class="grid">
        ${metric('Сценарий', escapeHtml(scenarioTitle))}
        ${metric('Обязательные слоты', escapeHtml(formatList(slotSchema.required_slots)))}
        ${metric('Автозаполнение', escapeHtml(formatList(slotSchema.auto_fill_slots)))}
        ${metric('Таймауты', escapeHtml(`${slotSchema.timeouts?.reminder_after_seconds || 'н/д'} сек / ${slotSchema.timeouts?.draft_after_seconds || 'н/д'} сек`))}
      </div>
      ${table(['Слот', 'Приоритет', 'Тип', 'Способ заполнения', 'Статус', 'Результат слота', 'Confidence', 'Причина'], slotRows)}
      ${slotAutofillRows.length ? table(['Профиль автозаполнения', 'ReAct-вызов', 'Статус', 'Значения', 'Заполненные слоты', 'Нет обязательных полей', 'Источник', 'Причина'], slotAutofillRows) : ''}
      ${resolutionRows.length ? table(['Слот', 'Профиль', 'Статус', 'Обогащение контекста', 'Попытка', 'Решение dry-run', 'Результаты слотов', 'Выходные слоты', 'Вопрос клиенту', 'Пакет эскалации'], resolutionRows) : ''}`,
    ),
    stepBlock(
      2,
      'Классификация и маршрутизация',
      simulation?.classification?.confidence >= 0.85 ? 'ready' : 'partial',
      `<div class="grid">
        ${metric('Приоритет', badge(classification.priority || route.priority))}
        ${metric('Маршрут', badge(classification.route || route.route))}
        ${metric('Workflow state', escapeHtml(classification.workflow_state_id || route.workflow_state_id || 'н/д'))}
        ${metric('Канал', escapeHtml(channel.display_name || 'н/д'))}
        ${metric('Confidence dry-run', escapeHtml(classification.confidence ?? 'н/д'))}
      </div>
      ${table(['Уровень', 'Значение'], routeRows)}
      ${topRouteRows.length ? table(['Кандидат маршрута', 'Маршрут', 'Приоритет', 'Confidence', 'Позитивные признаки', 'Негативные признаки'], topRouteRows) : ''}`,
    ),
    stepBlock(
      3,
      'Планирование ReAct',
      'ready',
      `<div class="grid">
        ${metric('Лимит итераций', escapeHtml(policy.max_iterations || 'н/д'))}
        ${metric('Ошибок до эскалации оператору', escapeHtml(policy.consecutive_tool_errors_to_escalate || 'н/д'))}
        ${metric('Группы действий ReAct', escapeHtml(formatList(policy.allowed_react_action_groups, (item) => reactActionGroupLabels[item] || item)))}
        ${metric('Стоп-условия', escapeHtml(formatList(policy.stop_conditions, (item) => stopConditionLabels[item] || item)))}
      </div>`,
    ),
    stepBlock(
      4,
      'Выполнение и инструменты',
      simulation?.blocked_tool_launches?.length ? 'blocked' : 'ready',
      `${table(['Готовность', 'ReAct-вызов', 'Вид запуска', 'Получение результата', 'Слоты', 'Параметры вызова', 'Подключение / операция', 'Риск', 'Причина блокировки'], launchRows)}
      <div class="hint">Action-инструменты в MVP запускаются через подтверждение оператора, даже если вид запуска отмечен как авто.</div>`,
    ),
    stepBlock(
      5,
      'Решение и эскалация',
      simulation?.final_decision || 'pending',
      `<div class="grid">
        ${metric('Автозакрытие', escapeHtml(waitingPolicy.auto_close_requires_client_confirmation ? 'после подтверждения клиента' : 'по политике канала'))}
        ${metric('Ожидание ответа клиента', escapeHtml(`${waitingPolicy.client_wait_auto_close_after_hours || 'н/д'} ч`))}
        ${metric('SLA при ожидании', escapeHtml(waitingPolicy.pause_sla_on_client_wait ? 'приостанавливается' : 'продолжается'))}
        ${metric('Таймаут канала', escapeHtml(`${waitingPolicy.first_reminder_after_seconds ?? 'н/д'} сек / ${waitingPolicy.discussion_timeout_seconds ?? 'н/д'} сек`))}
        ${metric('Клиент не ответил', badge(waitingPolicy.on_no_answer || 'missing'))}
        ${metric('Эскалация оператору', badge(escalationAction.action_type || 'missing'))}
        ${metric('Major Incident', escapeHtml(`${escalation.major_incident?.affected_users_threshold || 'н/д'} пользователей`))}
        ${metric('Условия эскалации', escapeHtml(formatList(escalation.handoff_conditions, (item) => conditionLabels[item] || item)))}
        ${metric('Пакет эскалации', escapeHtml(formatList(escalation.handoff_package, (item) => packageLabels[item] || item)))}
        ${metric('Ожидает клиента', badge(simulation?.awaiting_client_response ? 'yes' : 'no'))}
        ${metric('Передано оператору', badge(simulation?.operator_escalation?.required ? 'yes' : 'no'))}
      </div>
      ${plannedWaitRows.length ? table(['Статус', 'Тип', 'Источник', 'План ожидания', 'Ожидаемое событие', 'Timeout'], plannedWaitRows) : ''}
      ${runtimeWaitRows.length ? table(['Статус', 'Тип', 'Источник', 'Deadline', 'Correlation', 'Последнее событие'], runtimeWaitRows) : ''}
      ${profileRows.length ? table(['Событие', 'Профиль канала', 'Действие', 'ReAct-вызов / подключение / операция'], profileRows) : ''}
      <div class="message-block">
        <div class="metric-label">Уведомление клиенту</div>
        <p>${escapeHtml(escalation.user_notification_template || 'н/д')}</p>
      </div>`,
    ),
  ].join('');
}

function renderSteps() {
  const detail = state.scenarioDetail;
  if (!state.workflowStarted) {
    elements.stepsView.innerHTML = '<div class="empty">Сценарная работа начнется после кнопки «Анализировать»</div>';
    return;
  }
  elements.stepsView.innerHTML = renderFiveStepView(detail, state.scenarioSimulation, {
    scenarioName: scenarioName(),
    providedSlots: state.providedSlots,
  });
}

function syncAnalyzeButton() {
  const answerableSlots = state.dryRunEnabled ? answerableMissingSlotIds() : [];
  const disabled = !state.scenarios.length || !state.scenarioId || !elements.ticketText.value.trim() || answerableSlots.length > 0;
  elements.analyzeButton.disabled = disabled;
  elements.analyzeButton.title = answerableSlots.length
    ? 'Сначала ответьте на вопрос обогащения заявки'
    : '';
  elements.enrichButton.disabled = !state.workflowStarted || !state.dryRunEnabled;
  elements.resetSlotsButton.disabled = !state.workflowStarted;
  elements.loadScenarioButton.disabled = !state.workflowStarted;
}

async function loadScenarios() {
  try {
    const overview = await api(`${scenarioApiBase}/scenarios`);
    state.scenarios = overview.scenarios || [];
    if (!state.scenarios.some((scenario) => scenario.scenario_id === state.scenarioId)) {
      state.scenarioId = state.scenarios[0]?.scenario_id || '';
    }
    renderScenarioSelect();
    renderDebugScenarioOptions();
    elements.apiStatus.textContent = 'API готов';
    renderScenario();
  } catch (error) {
    elements.apiStatus.textContent = `Ошибка API: ${error.message}`;
    elements.stepsView.innerHTML = '<div class="empty">Сценарии не загружены</div>';
  }
}

async function loadScenarioDetail(scenarioId = state.scenarioId, options = {}) {
  if (!scenarioId) return;
  state.scenarioId = scenarioId;
  if (options.resetSlots) state.providedSlots = {};
  state.scenarioDetail = await api(`${scenarioApiBase}/scenarios/${encodeURIComponent(scenarioId)}`);
  state.scenarioSimulation = null;
  renderScenario();
  if (options.simulate === true && state.dryRunEnabled) {
    await simulateScenario();
  }
}

async function simulateScenario() {
  if (!state.workflowStarted || !state.scenarioId) {
    renderScenario();
    return;
  }
  if (!state.dryRunEnabled) {
    state.scenarioSimulation = null;
    renderScenario();
    return;
  }
  elements.enrichButton.disabled = true;
  try {
    const runOptions = currentTestRunOptions();
    state.scenarioSimulation = await api(`${scenarioApiBase}/scenarios/${encodeURIComponent(state.scenarioId)}/simulate`, {
      method: 'POST',
      body: JSON.stringify({
        text: state.ticketTextSnapshot,
        provided_slots: state.providedSlots,
        operator_id: elements.operatorId.value.trim() || 'admin-1',
        ...runOptions,
      }),
    });
  } catch (error) {
    const runOptions = currentTestRunOptions();
    state.scenarioSimulation = {
      schema_version: '1.0',
      scenario_id: state.scenarioId,
      input_text: state.ticketTextSnapshot,
      run_mode: runOptions.run_mode,
      simulation_options: runOptions,
      slot_values: {},
      missing_slots: [],
      next_question: null,
      attribute_resolution: [],
      classification: {},
      ready_tool_launches: [],
      blocked_tool_launches: [],
      execution_trace: [
        {
          step: '0',
          status: 'error',
          title: 'Тестовый прогон',
          message: error.message,
        },
      ],
      final_decision: 'error',
      agent_outcome: {
        status: 'error',
        label: 'Ошибка',
        summary: error.message,
        next_step: 'Исправьте ошибку и повторите тестовый прогон.',
      },
      dry_run: true,
      error: { message: error.message },
    };
    elements.apiStatus.textContent = `Ошибка сценария: ${error.message}`;
  } finally {
    elements.enrichButton.disabled = !state.dryRunEnabled;
    renderScenario();
  }
}

function addSlotAnswer() {
  if (!savePendingSlotAnswer()) return;
  simulateScenario();
}

function savePendingSlotAnswer() {
  const slotId = answerableMissingSlotIds()[0];
  const input = document.getElementById('slotAnswerInput');
  const value = input?.value.trim();
  if (!slotId || !value) return false;
  state.providedSlots[slotId] = value;
  if (input) input.value = '';
  return true;
}

async function refreshScenarioPreservingInput() {
  savePendingSlotAnswer();
  if (!state.workflowStarted) {
    renderScenario();
    return;
  }
  await loadScenarioDetail(state.scenarioId, { resetSlots: false, simulate: true });
}

function resetSlots() {
  state.providedSlots = {};
  if (state.workflowStarted) {
    simulateScenario();
  } else {
    renderScenario();
  }
}

function setDryRunEnabled(enabled) {
  state.dryRunEnabled = enabled;
  elements.enrichButton.disabled = !enabled;
  if (!enabled) state.scenarioSimulation = null;
  renderScenario();
}

function firstSlotValue(slotIds) {
  for (const slotId of slotIds) {
    const value = state.providedSlots[slotId];
    if (value !== undefined && value !== null && String(value).trim() !== '') {
      return String(value).trim();
    }
  }
  return '';
}

function legacyScenarioForAnalyze() {
  const route = state.scenarioDetail?.route?.route;
  const hasLaunches = (state.scenarioDetail?.tool_launches || []).length > 0;
  if (answerableMissingSlotIds().length) return 'clarification';
  if (route === 'major_incident' || route === 'human_review') return 'escalation';
  if (hasLaunches) return 'runbook';
  return 'answer';
}

function formPayload() {
  const text = state.ticketTextSnapshot || elements.ticketText.value.trim();
  const slotSummary = Object.entries(state.providedSlots)
    .map(([key, value]) => `${key}: ${value}`)
    .join('; ');
  const description = slotSummary ? `${text}\n\nСобранные слоты: ${slotSummary}` : text;
  const routePriority = state.scenarioDetail?.route?.priority || 'P3';
  const service = firstSlotValue(['app_name', 'resource_name', 'device_id', 'account_type', 'symptom', 'location'])
    || state.scenarioDetail?.scenario?.display_name
    || 'заявка';
  return compactObject({
    user: firstSlotValue(['user_login', 'user_id']) || 'не указан',
    service,
    priority: routePriority.toLowerCase(),
    scenario: legacyScenarioForAnalyze(),
    description,
  });
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
      statusStrip([
        { label: 'Статус', value: badge(knowledge.status), risk: knowledge.status === 'error' },
        { label: 'Путь индекса', value: escapeHtml(knowledge.index_path || 'н/д') },
      ]),
      `<div class="message-block"><div class="metric-label">Ошибка</div><p>${escapeHtml(knowledge.error?.message || 'н/д')}</p></div>`,
    ].join('');
    return;
  }
  elements.knowledgeStatus.innerHTML = [
    statusStrip([
      { label: 'Статус', value: badge(manifest.status), risk: manifest.status === 'error' },
      { label: 'Построен', value: escapeHtml(manifest.built_at) },
      { label: 'Документы', value: escapeHtml(manifest.document_count) },
      { label: 'Фрагменты', value: escapeHtml(manifest.chunk_count) },
    ]),
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
    statusStrip([
      { label: 'Состояние', value: badge(analysis.workflow_state?.id), risk: ['failed', 'blocked', 'error'].includes(analysis.workflow_state?.id) },
      { label: 'Решение', value: escapeHtml(decision?.type || 'invalid'), risk: ['error', 'invalid'].includes(decision?.type) },
      { label: 'RAG', value: badge(analysis.rag_trace?.status || 'н/д'), risk: analysis.rag_trace?.status === 'error' },
      { label: 'Заявка', value: escapeHtml(analysis.ticket_id) },
    ]),
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
    if (state.scenarioSimulation) {
      if (state.activeTab === 'tools') {
        const trace = state.scenarioSimulation.execution_trace || [];
        elements.traceView.innerHTML = trace.length
          ? trace.map((item, index) => renderDryRunTraceItem(item, index)).join('')
          : '<div class="empty">Нет событий тестового прогона</div>';
        return;
      }
      if (state.activeTab === 'json') {
        elements.traceView.innerHTML = `<pre>${escapeHtml(JSON.stringify(state.scenarioSimulation, null, 2))}</pre>`;
        return;
      }
    }
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

function setMainTab(tabName) {
  state.activeMainTab = tabName || 'steps';
  elements.mainTabs.forEach((tab) => {
    const active = tab.dataset.mainTab === state.activeMainTab;
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  elements.mainPanels.forEach((panel) => {
    panel.hidden = panel.dataset.mainPanel !== state.activeMainTab;
  });
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
    `Сценарий: ${scenarioName()}`,
    `Решение: ${decision?.type || 'н/д'}`,
    `Кратко: ${decision?.summary || decision?.question || decision?.reason || 'н/д'}`,
    `Сообщение оператору: ${analysis.operator_message || 'н/д'}`,
    `Слоты: ${Object.entries(state.providedSlots).map(([key, value]) => `${key}=${value}`).join(', ') || 'нет'}`,
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
  state.workflowStarted = true;
  state.ticketTextSnapshot = elements.ticketText.value.trim();
  if (!state.ticketTextSnapshot) {
    renderScenario();
    return;
  }
  state.analysis = null;
  state.approvalResults = {};
  state.feedback = null;
  state.caseRecord = null;
  state.caseTimeline = null;
  stopCasePolling();
  renderAnalysis();
  if (!state.scenarioDetail || state.scenarioDetail.scenario?.scenario_id !== state.scenarioId) {
    try {
      await loadScenarioDetail(state.scenarioId, { resetSlots: false, simulate: false });
    } catch (error) {
      elements.apiStatus.textContent = `Ошибка сценария: ${error.message}`;
      renderScenario();
      return;
    }
  }
  if (state.dryRunEnabled) {
    await simulateScenario();
  }
  if (answerableMissingSlotIds().length) {
    renderQuestion();
    syncAnalyzeButton();
    return;
  }
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
    syncAnalyzeButton();
    renderAnalysis();
  }
}

async function submitFeedback(rating) {
  if (!state.analysis || !state.ticketInput) return;
  const correctedResponse = elements.correctedResponse.value.trim();
  const payload = compactObject({
    schema_version: '1.0',
    ticket_id: state.analysis.ticket_id,
    operator_id: elements.operatorId.value.trim() || 'admin-1',
    rating,
    ticket_input: state.ticketInput,
    analysis_snapshot: state.analysis,
    approval_snapshot: Object.keys(state.approvalResults).length ? state.approvalResults : undefined,
    operator_note: elements.feedbackNote.value.trim(),
    corrected_response: rating === 'edited' ? correctedResponse || buildCopyText() : undefined,
    extensions: {
      ui: 'operator-static-orchestrator-steps',
      case_id: state.analysis.case_id,
      scenario_id: state.scenarioId,
      provided_slots: state.providedSlots,
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
      body: JSON.stringify({ operator_id: elements.operatorId.value.trim() || 'admin-1' }),
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
    operator_id: elements.operatorId.value.trim() || 'admin-1',
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

function setDebugTab(tabId) {
  state.activeDebugTab = tabId || 'single';
  const titleByTab = {
    single: 'Одиночный прогон',
    flow: 'Мультиагентный поток',
    traces: 'Трассы обращений',
    waits: 'Активные ожидания',
    captures: 'Mock из endpoint-вызовов',
  };
  if (elements.debugPageTitle) {
    elements.debugPageTitle.textContent = titleByTab[state.activeDebugTab] || state.activeDebugTab;
  }
  elements.debugTabs.forEach((tab) => {
    const active = tab.dataset.debugTab === state.activeDebugTab;
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  elements.debugPanels.forEach((panel) => {
    panel.hidden = panel.dataset.debugPanel !== state.activeDebugTab;
  });
  if (state.activeDebugTab === 'flow') {
    loadDebugProfiles();
    loadDebugSimulations();
  } else if (state.activeDebugTab === 'traces') {
    loadDebugSimulations();
  } else if (state.activeDebugTab === 'waits') {
    loadDebugWaits();
  } else if (state.activeDebugTab === 'captures') {
    loadDebugIntegrationOperations();
    loadEndpointCaptures();
  }
}

function renderDebugScenarioOptions() {
  if (!elements.debugFlowScenario) return;
  const selected = elements.debugFlowScenario.value || state.scenarioId;
  elements.debugFlowScenario.innerHTML = state.scenarios
    .map((scenario) => `
      <option value="${escapeHtml(scenario.scenario_id)}" ${scenario.scenario_id === selected ? 'selected' : ''}>
        ${escapeHtml(scenario.display_name || scenario.scenario_id)}
      </option>
    `)
    .join('');
}

async function loadDebugProfiles() {
  if (state.debugProfiles) {
    renderDebugScenarioOptions();
    return;
  }
  try {
    state.debugProfiles = await api('/debug/simulations/profiles');
    renderDebugScenarioOptions();
  } catch (error) {
    if (elements.debugSimulationStatus) {
      elements.debugSimulationStatus.textContent = `Профили генерации не загружены: ${error.message}`;
    }
  }
}

async function loadDebugSimulations() {
  try {
    const data = await api('/debug/simulations');
    state.debugSimulations = data.runs || [];
    renderDebugTraceRunSelect();
  } catch (error) {
    if (elements.debugCaseTraceView) {
      elements.debugCaseTraceView.innerHTML = `<div class="empty">Симуляции не загружены: ${escapeHtml(error.message)}</div>`;
    }
  }
}

async function prepareDebugSimulation() {
  const scenarioId = elements.debugFlowScenario?.value || state.scenarioId;
  if (!scenarioId) return;
  elements.debugPrepareButton.disabled = true;
  try {
    state.debugSimulation = await api('/debug/simulations/prepare', {
      method: 'POST',
      body: JSON.stringify({
        source: 'scenario_profiles',
        scenario_ids: [scenarioId],
        count_per_scenario: Number(elements.debugFlowCount?.value || 1),
        channel_id: 'debug',
        seed: elements.debugFlowSeed?.value || undefined,
        include_wrong_department: elements.debugFlowWrongDepartment?.checked === true,
        mode: 'dry_run',
        dry_run: true,
      }),
    });
    state.debugSimulations = [state.debugSimulation.run, ...state.debugSimulations.filter(
      (run) => run.run_id !== state.debugSimulation.run.run_id,
    )];
    renderDebugSimulation();
    renderDebugTraceRunSelect();
  } catch (error) {
    elements.debugSimulationStatus.textContent = `Ошибка подготовки потока: ${error.message}`;
  } finally {
    elements.debugPrepareButton.disabled = false;
  }
}

function debugExpectedValue(value) {
  if (value === undefined || value === null || value === '') return 'н/д';
  if (typeof value === 'object') {
    if (value.value !== undefined && value.value !== null && value.value !== '') {
      return String(value.value);
    }
    return JSON.stringify(value);
  }
  return String(value);
}

function debugExpectedBlock(title, values) {
  const entries = Object.entries(values || {});
  return `
    <div class="simulation-expected-block">
      <div class="metric-label">${escapeHtml(title)}</div>
      ${entries.length
        ? entries.map(([key, value]) => `
          <div class="simulation-expected-row">
            <strong>${escapeHtml(key)}</strong>
            <span>${escapeHtml(debugExpectedValue(value))}</span>
          </div>
        `).join('')
        : '<div class="muted-text">нет</div>'}
    </div>
  `;
}

function renderSimulationExpectations(item) {
  return `
    <div class="simulation-expectations">
      ${debugExpectedBlock('В тексте заявки', item.text_slots)}
      ${debugExpectedBlock('Ожидается из автозаполнения', item.expected_autofill)}
      ${debugExpectedBlock('Ожидается из разрешения атрибутов', item.expected_resolution)}
      <div class="simulation-expected-block">
        <div class="metric-label">Итог</div>
        <div>${escapeHtml(item.expected_outcome || 'н/д')}</div>
        ${item.expected_gaps?.length ? `<div class="muted-text">Пробелы: ${escapeHtml(item.expected_gaps.join(', '))}</div>` : ''}
        ${item.generation_notes?.length ? `<div class="muted-text">${escapeHtml(item.generation_notes.join(' '))}</div>` : ''}
      </div>
    </div>
  `;
}

function renderDebugAgentOutcome(item) {
  const outcome = item.agent_outcome || null;
  if (!outcome) {
    return `<div class="debug-agent-outcome">${badge(item.status || 'prepared')}<div class="muted-text">Запустите поток, чтобы получить итог агента.</div></div>`;
  }
  return `
    <div class="debug-agent-outcome debug-agent-outcome-${escapeHtml(outcome.status || 'pending')}">
      <div>${badge(outcome.status || 'pending')}</div>
      <strong>${escapeHtml(outcome.label || visibleLabels[outcome.status] || outcome.status || 'н/д')}</strong>
      <span>${escapeHtml(outcome.summary || 'н/д')}</span>
      <small>${escapeHtml(outcome.next_step || '')}</small>
    </div>
  `;
}

function renderDebugSimulation() {
  const run = state.debugSimulation?.run;
  const items = state.debugSimulation?.items || [];
  if (!run) {
    elements.debugSimulationStatus.textContent = 'Поток не сформирован';
    elements.debugSimulationItems.innerHTML = '<div class="empty">Сначала сформируйте поток</div>';
    elements.debugStartButton.disabled = true;
    elements.debugPauseButton.disabled = true;
    elements.debugCancelButton.disabled = true;
    return;
  }
  const counters = run.counters || {};
  elements.debugSimulationStatus.innerHTML = [
    `Запуск: <strong>${escapeHtml(run.run_id)}</strong>`,
    `Статус: ${badge(run.status)}`,
    `Seed: ${escapeHtml(run.seed)}`,
    `Подготовлено: ${escapeHtml(counters.prepared || 0)}`,
    `Завершено: ${escapeHtml(counters.completed || 0)}`,
    `Ожиданий: ${escapeHtml(counters.waiting || 0)}`,
    `Ошибок: ${escapeHtml(counters.failed || 0)}`,
  ].join(' / ');
  elements.debugStartButton.disabled = !['prepared', 'paused'].includes(run.status);
  elements.debugPauseButton.disabled = !['prepared', 'running'].includes(run.status);
  elements.debugCancelButton.disabled = ['completed', 'cancelled'].includes(run.status);
  if (!items.length) {
    elements.debugSimulationItems.innerHTML = '<div class="empty">В потоке нет обращений</div>';
    return;
  }
  elements.debugSimulationItems.innerHTML = `
    <div class="table-wrap wide-table">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Статус</th>
            <th>Сценарий</th>
            <th>Вариант</th>
            <th>Текст обращения</th>
            <th>Ожидаемые данные</th>
            <th>Итог агента</th>
            <th>Case</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${items.map((item) => `
            <tr data-sim-item="${escapeHtml(item.item_id)}">
              <td>${escapeHtml(item.sort_order)}</td>
              <td>${badge(item.status)}</td>
              <td>${escapeHtml(item.scenario_display_name || item.scenario_id)}</td>
              <td>${escapeHtml(item.variant || 'н/д')}</td>
              <td><textarea class="compact-textarea" data-sim-item-text>${escapeHtml(item.text || '')}</textarea></td>
              <td>${renderSimulationExpectations(item)}</td>
              <td>${renderDebugAgentOutcome(item)}</td>
              <td>${item.case_id ? `<button type="button" data-action="debug-open-case" data-case-id="${escapeHtml(item.case_id)}">${escapeHtml(item.case_id)}</button>` : 'не создан'}</td>
              <td>
                <div class="button-column">
                  <button type="button" data-action="debug-save-item">Сохранить</button>
                  <button type="button" data-action="debug-toggle-exclude">${item.excluded ? 'Вернуть' : 'Исключить'}</button>
                </div>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

async function saveDebugSimulationItem(row, overrides = {}) {
  const runId = state.debugSimulation?.run?.run_id;
  const itemId = row?.dataset.simItem;
  if (!runId || !itemId) return;
  const text = row.querySelector('[data-sim-item-text]')?.value || '';
  const current = (state.debugSimulation.items || []).find((item) => item.item_id === itemId) || {};
  const response = await api(`/debug/simulations/${encodeURIComponent(runId)}/items/${encodeURIComponent(itemId)}`, {
    method: 'PATCH',
    body: JSON.stringify({
      patch: {
        text,
        excluded: current.excluded === true,
        ...overrides,
      },
    }),
  });
  state.debugSimulation.items = state.debugSimulation.items.map((item) => (
    item.item_id === itemId ? response.item : item
  ));
  renderDebugSimulation();
}

async function startDebugSimulation() {
  const runId = state.debugSimulation?.run?.run_id;
  if (!runId) return;
  elements.debugStartButton.disabled = true;
  try {
    state.debugSimulation = await api(`/debug/simulations/${encodeURIComponent(runId)}/start`, {
      method: 'POST',
      body: JSON.stringify({
        operator_id: elements.operatorId.value.trim() || 'admin-1',
        stop_on_mismatch: false,
      }),
    });
    renderDebugSimulation();
    await loadDebugSimulations();
  } catch (error) {
    elements.debugSimulationStatus.textContent = `Ошибка запуска потока: ${error.message}`;
  }
}

async function pauseDebugSimulation() {
  const runId = state.debugSimulation?.run?.run_id;
  if (!runId) return;
  try {
    const result = await api(`/debug/simulations/${encodeURIComponent(runId)}/pause`, { method: 'POST', body: '{}' });
    state.debugSimulation.run = result.run;
    renderDebugSimulation();
  } catch (error) {
    elements.debugSimulationStatus.textContent = `Ошибка паузы: ${error.message}`;
  }
}

async function cancelDebugSimulation() {
  const runId = state.debugSimulation?.run?.run_id;
  if (!runId) return;
  try {
    const result = await api(`/debug/simulations/${encodeURIComponent(runId)}/cancel`, { method: 'POST', body: '{}' });
    state.debugSimulation.run = result.run;
    renderDebugSimulation();
  } catch (error) {
    elements.debugSimulationStatus.textContent = `Ошибка отмены: ${error.message}`;
  }
}

function renderDebugTraceRunSelect() {
  if (!elements.debugTraceRunSelect) return;
  const current = elements.debugTraceRunSelect.value || state.debugSimulation?.run?.run_id || state.debugSimulations[0]?.run_id || '';
  elements.debugTraceRunSelect.innerHTML = state.debugSimulations
    .map((run) => `<option value="${escapeHtml(run.run_id)}" ${run.run_id === current ? 'selected' : ''}>${escapeHtml(run.run_id)} / ${escapeHtml(run.status)}</option>`)
    .join('');
}

async function loadSelectedSimulationTrace() {
  const runId = elements.debugTraceRunSelect?.value || state.debugSimulation?.run?.run_id;
  if (!runId) {
    elements.debugCaseTraceView.innerHTML = '<div class="empty">Нет выбранного запуска симуляции</div>';
    return;
  }
  try {
    const trace = await api(`/debug/simulations/${encodeURIComponent(runId)}/trace`);
    renderSimulationTrace(trace);
  } catch (error) {
    elements.debugCaseTraceView.innerHTML = `<div class="empty">Трасса не загружена: ${escapeHtml(error.message)}</div>`;
  }
}

async function loadDebugCaseTrace(caseId = elements.debugTraceCaseId?.value.trim()) {
  if (!caseId) return;
  try {
    state.debugTrace = await api(`/debug/cases/${encodeURIComponent(caseId)}/trace`);
    renderCaseCentricTrace(state.debugTrace);
  } catch (error) {
    elements.debugCaseTraceView.innerHTML = `<div class="empty">Обращение не загружено: ${escapeHtml(error.message)}</div>`;
  }
}

function renderSimulationTrace(trace) {
  const rows = (trace.items || []).map((item) => [
    escapeHtml(item.sort_order),
    badge(item.status),
    item.agent_outcome ? badge(item.agent_outcome.status) : 'н/д',
    escapeHtml(item.scenario_display_name || item.scenario_id),
    escapeHtml(item.variant || 'н/д'),
    item.case_id ? `<button type="button" data-action="debug-open-case" data-case-id="${escapeHtml(item.case_id)}">${escapeHtml(item.case_id)}</button>` : 'не создан',
  ]);
  elements.debugCaseTraceView.innerHTML = [
    `<div class="status-line">Запуск ${escapeHtml(trace.run.run_id)} / ${badge(trace.run.status)}</div>`,
    table(['#', 'Статус', 'Итог агента', 'Сценарий', 'Вариант', 'Case'], rows),
  ].join('');
}

function renderCaseCentricTrace(trace) {
  const events = trace.events || [];
  const steps = trace.steps || [];
  const hasFiveStepTrace = trace.scenario_detail && trace.simulation_snapshot;
  if (!events.length && !steps.length && !hasFiveStepTrace) {
    elements.debugCaseTraceView.innerHTML = '<div class="empty">Нет данных трассы</div>';
    return;
  }
  const fiveStepView = hasFiveStepTrace
      ? renderFiveStepView(trace.scenario_detail, trace.simulation_snapshot, {
        scenarioName:
          trace.scenario_detail?.scenario?.display_name
          || trace.debug_item?.scenario_display_name
          || trace.scenario_detail?.scenario?.scenario_id
          || trace.debug_item?.scenario_id
          || 'н/д',
        providedSlots: trace.debug_item?.text_slots || {},
        runtimeWaits: trace.waits || [],
      })
    : `
      <div class="hint">Для этого обращения нет сохраненного снимка сценария, показана fallback-трасса.</div>
      <div class="case-trace-steps">
        ${steps.map(renderCaseTraceStep).join('')}
      </div>
    `;
  elements.debugCaseTraceView.innerHTML = `
    ${renderCaseTraceSummary(trace)}
    ${fiveStepView}
    ${renderCaseTraceEvents(events, trace.agent_outcome?.status === 'error')}
  `;
}

function renderCaseTraceSummary(trace) {
  const summary = trace.summary || {};
  const outcome = trace.agent_outcome || summary.agent_outcome || {};
  return `
    <div class="case-trace-summary">
      <div class="section-head">
        <h3>Обращение ${escapeHtml(trace.case_id || summary.case_id || 'н/д')}</h3>
        ${badge(outcome.status || summary.workflow_category || 'info')}
      </div>
      <div class="grid">
        ${metric('Итог агента', outcome.status ? badge(outcome.status) : escapeHtml(outcome.label || 'н/д'))}
        ${metric('Ticket ID', escapeHtml(summary.ticket_id || trace.case?.ticket_id || 'н/д'))}
        ${metric('Workflow state', badge(summary.workflow_state || 'missing'))}
        ${metric('Runs / Tasks', escapeHtml(`${summary.run_count ?? 0} / ${summary.task_count ?? 0}`))}
        ${metric('Ожидания', escapeHtml(`${summary.active_wait_count ?? 0} активных / ${summary.wait_count ?? 0} всего`))}
        ${metric('События', escapeHtml(summary.event_count ?? (trace.events || []).length))}
      </div>
      <div class="message-block">
        <div class="metric-label">Что дальше</div>
        <p>${escapeHtml(outcome.next_step || outcome.summary || 'н/д')}</p>
      </div>
    </div>
  `;
}

function renderCaseTraceStep(step) {
  const metrics = step.metrics || [];
  const tables = step.tables || [];
  const events = step.events || [];
  const body = `
    <div class="message-block">
      <div class="metric-label">Смысл шага</div>
      <p>${escapeHtml(step.summary || 'н/д')}</p>
    </div>
    ${metrics.length ? `<div class="grid">${metrics.map(renderCaseTraceMetric).join('')}</div>` : ''}
    ${tables.map(renderCaseTraceTable).join('')}
    ${events.length ? renderCaseTraceEvents(events, false, 'События шага') : ''}
  `;
  return stepBlock(step.order || '?', step.title || 'Шаг', step.status || 'info', body);
}

function renderCaseTraceMetric(item) {
  const value = item.kind === 'badge'
    ? badge(item.status || item.value || 'missing')
    : escapeHtml(item.value || 'н/д');
  return metric(item.label || 'Параметр', value);
}

function renderCaseTraceTable(tableDef) {
  const rows = (tableDef.rows || []).map((row) => row.map((cell) => escapeHtml(cell ?? 'н/д')));
  return `
    <div class="case-trace-table">
      <h4>${escapeHtml(tableDef.title || 'Данные')}</h4>
      ${table(tableDef.columns || [], rows)}
    </div>
  `;
}

function renderCaseTraceEvents(events, open = false, title = 'Технические события timeline') {
  if (!events.length) return '';
  return `
    <details class="trace-run-block case-trace-events" ${open ? 'open' : ''}>
      <summary>
        <span class="trace-run-title">${escapeHtml(title)}</span>
        <span class="summary-line">${events.length} событий</span>
      </summary>
      <div class="case-trace-list">
        ${events.map((event) => `
          <details class="case-trace-event">
            <summary>
              <span>${escapeHtml(event.created_at || 'н/д')}</span>
              <strong>${escapeHtml(event.event_type || 'event')}</strong>
              <span>${escapeHtml(event.summary || '')}</span>
              ${event.agent_id ? badge(event.agent_id) : ''}
            </summary>
            <div class="dry-run-trace-grid">
              <div><div class="metric-label">Run / Task</div><div class="trace-value">${escapeHtml(event.run_id || 'н/д')} / ${escapeHtml(event.task_id || 'н/д')}</div></div>
              <div><div class="metric-label">Correlation</div><div class="trace-value">${escapeHtml(event.correlation_id || event.idempotency_key || 'н/д')}</div></div>
              <div><div class="metric-label">Payload</div><div class="trace-value">${traceJson(event.payload)}</div></div>
            </div>
          </details>
        `).join('')}
      </div>
    </details>
  `;
}

async function loadDebugWaits() {
  try {
    state.debugWaits = await api('/debug/waits');
    const rows = (state.debugWaits.waits || []).map((wait) => [
      escapeHtml(wait.wait_id),
      wait.case_id ? `<button type="button" data-action="debug-open-case" data-case-id="${escapeHtml(wait.case_id)}">${escapeHtml(wait.case_id)}</button>` : 'н/д',
      badge(wait.wait_type),
      badge(wait.status),
      escapeHtml(waitOriginSummary(wait.origin)),
      escapeHtml(wait.deadline_at || 'н/д'),
      escapeHtml(wait.correlation_id || 'н/д'),
      escapeHtml(wait.reason || 'н/д'),
    ]);
    elements.debugWaitsView.innerHTML = table(['Ожидание', 'Case', 'Тип', 'Статус', 'Источник', 'Deadline', 'Correlation', 'Причина'], rows);
  } catch (error) {
    elements.debugWaitsView.innerHTML = `<div class="empty">Ожидания не загружены: ${escapeHtml(error.message)}</div>`;
  }
}

async function loadDebugIntegrationOperations() {
  try {
    const payload = await api('/debug/integration-operations');
    state.integrationEndpoints = payload.endpoints || [];
    renderCaptureEndpointSelectors();
  } catch (error) {
    elements.captureStatus.textContent = `Операции не загружены: ${error.message}`;
  }
}

function renderCaptureEndpointSelectors() {
  const selectedEndpointId = elements.captureEndpointSelect?.value || state.integrationEndpoints[0]?.endpoint_id || '';
  if (elements.captureEndpointSelect) {
    elements.captureEndpointSelect.innerHTML = state.integrationEndpoints
      .map((endpoint) => `<option value="${escapeHtml(endpoint.endpoint_id)}" ${endpoint.endpoint_id === selectedEndpointId ? 'selected' : ''}>${escapeHtml(endpoint.display_name || endpoint.endpoint_id)}</option>`)
      .join('');
  }
  const endpoint = state.integrationEndpoints.find((item) => item.endpoint_id === selectedEndpointId) || state.integrationEndpoints[0];
  const operations = Object.entries(endpoint?.operations || {});
  const selectedOperationId = elements.captureOperationSelect?.value || operations[0]?.[0] || '';
  if (elements.captureOperationSelect) {
    elements.captureOperationSelect.innerHTML = operations
      .map(([operationId, operation]) => `<option value="${escapeHtml(operationId)}" ${operationId === selectedOperationId ? 'selected' : ''}>${escapeHtml(operation.display_name || operationId)}</option>`)
      .join('');
  }
}

async function startEndpointCapture() {
  try {
    const result = await api('/debug/endpoint-captures/start', {
      method: 'POST',
      body: JSON.stringify({
        endpoint_id: elements.captureEndpointSelect.value,
        operation_id: elements.captureOperationSelect.value,
        operator_id: elements.operatorId.value.trim() || 'admin-1',
      }),
    });
    elements.captureStatus.textContent = `Захват включен: ${result.session.session_id}`;
    await loadEndpointCaptures();
  } catch (error) {
    elements.captureStatus.textContent = `Захват не включен: ${error.message}`;
  }
}

async function stopEndpointCapture() {
  const sessionId = elements.captureStopSessionSelect?.value;
  if (!sessionId) return;
  try {
    await api('/debug/endpoint-captures/stop', {
      method: 'POST',
      body: JSON.stringify({
        session_id: sessionId,
        operator_id: elements.operatorId.value.trim() || 'admin-1',
      }),
    });
    elements.captureStatus.textContent = `Захват остановлен: ${sessionId}`;
    await loadEndpointCaptures();
  } catch (error) {
    elements.captureStatus.textContent = `Захват не остановлен: ${error.message}`;
  }
}

async function loadEndpointCaptures() {
  try {
    state.endpointCaptures = await api('/debug/endpoint-captures');
    renderEndpointCaptures();
  } catch (error) {
    elements.captureStatus.textContent = `Сессии захвата не загружены: ${error.message}`;
  }
}

function renderEndpointCaptures() {
  const sessions = state.endpointCaptures?.sessions || [];
  const captures = state.endpointCaptures?.captures || [];
  elements.captureStatus.innerHTML = `Сессий: ${escapeHtml(sessions.length)} / captured: ${escapeHtml(captures.length)}`;
  const activeSessions = sessions.filter((session) => session.status === 'active');
  elements.captureStopSessionSelect.innerHTML = activeSessions
    .map((session) => `<option value="${escapeHtml(session.session_id)}">${escapeHtml(session.endpoint_id)}/${escapeHtml(session.operation_id)} · ${escapeHtml(session.session_id)}</option>`)
    .join('');
  elements.captureSessions.innerHTML = table(
    ['Сессия', 'Операция', 'Статус', 'Captured', 'Обновлено'],
    sessions.map((session) => [
      escapeHtml(session.session_id),
      escapeHtml(`${session.endpoint_id}/${session.operation_id}`),
      badge(session.status),
      escapeHtml(session.capture_count || 0),
      escapeHtml(session.updated_at || 'н/д'),
    ]),
  );
  elements.captureList.innerHTML = table(
    ['Capture', 'Операция', 'Статус', 'Schema', 'Sanitized', 'Действия'],
    captures.map((capture) => [
      escapeHtml(capture.capture_id),
      escapeHtml(`${capture.endpoint_id}/${capture.operation_id}`),
      badge(capture.status),
      badge(capture.validation?.status || 'н/д'),
      badge(capture.sanitized ? 'yes' : 'no'),
      `<div class="button-column">
        <button type="button" data-action="capture-sanitize" data-capture-id="${escapeHtml(capture.capture_id)}">Обезличить</button>
        <button type="button" data-action="capture-create-mock" data-capture-id="${escapeHtml(capture.capture_id)}">Создать mock</button>
      </div>`,
    ]),
  );
}

async function sanitizeCapture(captureId) {
  try {
    await api(`/debug/endpoint-captures/${encodeURIComponent(captureId)}/sanitize`, {
      method: 'POST',
      body: JSON.stringify({ operator_id: elements.operatorId.value.trim() || 'admin-1' }),
    });
    await loadEndpointCaptures();
  } catch (error) {
    elements.captureStatus.textContent = `Обезличивание не выполнено: ${error.message}`;
  }
}

async function createMockFromCapture(captureId) {
  try {
    const result = await api(`/debug/endpoint-captures/${encodeURIComponent(captureId)}/create-mock`, {
      method: 'POST',
      body: JSON.stringify({
        operator_id: elements.operatorId.value.trim() || 'admin-1',
        example_name: `Captured ${captureId}`,
        tags: ['captured', 'debug'],
      }),
    });
    elements.captureStatus.textContent = `Mock создан и активирован: ${result.config_version.version_id}`;
    await loadEndpointCaptures();
  } catch (error) {
    elements.captureStatus.textContent = `Mock не создан: ${error.message}`;
  }
}

elements.loadScenarioButton.addEventListener('click', refreshScenarioPreservingInput);
elements.enrichButton.addEventListener('click', simulateScenario);
elements.resetSlotsButton.addEventListener('click', resetSlots);
elements.scenarioSelect.addEventListener('change', (event) => {
  state.scenarioId = event.target.value;
  state.workflowStarted = false;
  state.ticketTextSnapshot = '';
  state.scenarioDetail = null;
  state.scenarioSimulation = null;
  state.providedSlots = {};
  state.analysis = null;
  state.approvalResults = {};
  state.feedback = null;
  state.caseRecord = null;
  state.caseTimeline = null;
  stopCasePolling();
  renderScenario();
  renderAnalysis();
});
elements.ticketText.addEventListener('input', syncAnalyzeButton);
elements.dryRunToggle.addEventListener('change', (event) => setDryRunEnabled(event.target.checked));
elements.testRunMode?.addEventListener('change', () => {
  syncTestRunModeDefaults();
  syncAnalyzeButton();
});
[
  elements.allowLlmToggle,
  elements.allowReadonlyToggle,
  elements.allowMockToggle,
  elements.allowActionApprovalToggle,
].forEach((toggle) => {
  toggle?.addEventListener('change', syncAnalyzeButton);
});
elements.operatorId.addEventListener('change', () => {
  loadScenarios();
  loadKnowledgeStatus();
});
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
elements.mainTabs.forEach((tab) => {
  tab.addEventListener('click', () => setMainTab(tab.dataset.mainTab));
});
elements.debugTabs.forEach((tab) => {
  tab.addEventListener('click', () => setDebugTab(tab.dataset.debugTab));
});
elements.debugPrepareButton?.addEventListener('click', prepareDebugSimulation);
elements.debugStartButton?.addEventListener('click', startDebugSimulation);
elements.debugPauseButton?.addEventListener('click', pauseDebugSimulation);
elements.debugCancelButton?.addEventListener('click', cancelDebugSimulation);
elements.debugLoadTraceButton?.addEventListener('click', loadSelectedSimulationTrace);
elements.debugLoadCaseTraceButton?.addEventListener('click', () => loadDebugCaseTrace());
elements.debugWaitsRefreshButton?.addEventListener('click', loadDebugWaits);
elements.captureEndpointSelect?.addEventListener('change', renderCaptureEndpointSelectors);
elements.captureRefreshButton?.addEventListener('click', () => {
  loadDebugIntegrationOperations();
  loadEndpointCaptures();
});
elements.captureStartButton?.addEventListener('click', startEndpointCapture);
elements.captureStopButton?.addEventListener('click', stopEndpointCapture);
document.addEventListener('click', (event) => {
  const target = event.target.closest('[data-action]');
  if (!target) return;
  const action = target.dataset.action;
  if (action === 'debug-save-item') {
    saveDebugSimulationItem(target.closest('[data-sim-item]'));
  } else if (action === 'debug-toggle-exclude') {
    const row = target.closest('[data-sim-item]');
    const itemId = row?.dataset.simItem;
    const current = (state.debugSimulation?.items || []).find((item) => item.item_id === itemId);
    saveDebugSimulationItem(row, { excluded: !current?.excluded });
  } else if (action === 'debug-open-case') {
    setDebugTab('traces');
    if (elements.debugTraceCaseId) elements.debugTraceCaseId.value = target.dataset.caseId || '';
    loadDebugCaseTrace(target.dataset.caseId || '');
  } else if (action === 'capture-sanitize') {
    sanitizeCapture(target.dataset.captureId);
  } else if (action === 'capture-create-mock') {
    createMockFromCapture(target.dataset.captureId);
  }
});

syncTestRunModeDefaults();
setDebugTab(state.activeDebugTab);
setMainTab(state.activeMainTab);
renderAnalysis();
renderScenario();
loadScenarios();
loadKnowledgeStatus();
