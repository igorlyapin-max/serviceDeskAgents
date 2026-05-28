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
  scenarios: [],
  scenarioId: 'password_reset',
  scenarioDetail: null,
  scenarioSimulation: null,
  dryRunEnabled: true,
  providedSlots: {},
  scenarioSimulationTimer: null,
};

const elements = {
  apiStatus: document.getElementById('apiStatus'),
  operatorId: document.getElementById('operatorId'),
  ticketForm: document.getElementById('ticketForm'),
  ticketText: document.getElementById('ticketText'),
  scenarioSelect: document.getElementById('scenarioSelect'),
  dryRunToggle: document.getElementById('dryRunToggle'),
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
};

const visibleLabels = {
  active: 'активно',
  auto: 'авто',
  auto_agent: 'автоагент',
  auto_fill_candidate: 'кандидат автозаполнения',
  blocked: 'заблокировано',
  continue_slot_filling: 'нужно обогащение',
  draft: 'черновик',
  error: 'ошибка',
  failed: 'ошибка',
  incomplete: 'неполно',
  info: 'информация',
  l1_hint: 'Л1 + подсказка',
  l2_major_incident: 'Л2 + Major Incident',
  missing: 'требуется ответ',
  operator_approval: 'согласование оператора',
  operator_handoff: 'передать оператору',
  operator_manual: 'ручное заполнение оператором',
  optional: 'необязательный',
  p1: 'P1',
  p2: 'P2',
  p3: 'P3',
  p4: 'P4',
  partial: 'частично',
  pending: 'ожидает',
  planned: 'запланировано',
  provided: 'заполнено',
  ready: 'готово',
  ready_for_react: 'готово к ReAct',
  required: 'обязательный',
  resolution_pending: 'ожидает разрешения',
  question_required: 'нужно уточнение',
  resolution_profile: 'профиль разрешения',
  dry_run_simulated: 'смоделировано',
  success: 'успешно',
  unavailable: 'недоступно',
  user_question: 'вопрос пользователю',
  case: 'текущий кейс',
  llm_extraction: 'извлечение моделью',
  llm_extract: 'извлечение из текста',
  rag_search: 'поиск в базе знаний',
  case_read: 'чтение кейса',
  tool_call: 'вызов инструмента',
  ticket_history_search: 'поиск по истории',
  condition: 'условие',
  clarification: 'уточнение',
  fill_slot: 'заполнение слота',
  operator_handoff: 'передача Л1',
  escalate: 'эскалация',
};

const priorityGroupLabels = {
  who: 'кто',
  what: 'что',
  when: 'когда',
  where: 'где',
  context: 'контекст',
};

const fillMethodLabels = {
  user_question: 'вопрос пользователю',
  case: 'текущий кейс',
  llm_extraction: 'извлечение моделью',
  resolution_profile: 'профиль разрешения',
  operator_manual: 'ручное заполнение оператором',
};

const stopConditionLabels = {
  user_confirmed_success: 'пользователь подтвердил успех',
  waiting_for_user: 'ожидание пользователя',
  tool_errors_limit: 'лимит ошибок инструментов',
  iteration_limit: 'лимит итераций',
  low_confidence: 'низкая уверенность',
  major_incident: 'Major Incident',
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
  endpoint: 'endpoint',
  callback: 'callback',
};

function compactObject(value) {
  return Object.fromEntries(
    Object.entries(value).filter(([, item]) => item !== undefined && item !== null && item !== ''),
  );
}

function apiHeaders(extra = {}) {
  const actorId = elements.operatorId.value.trim() || 'operator-1';
  return {
    'Content-Type': 'application/json',
    'X-ServiceDesk-Actor': actorId,
    'X-ServiceDesk-Session': `operator-ui:${actorId}`,
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

function metric(label, value) {
  return `
    <div class="metric">
      <div class="metric-label">${escapeHtml(label)}</div>
      <div class="metric-value">${value}</div>
    </div>
  `;
}

function table(headers, rows) {
  if (!rows.length) {
    return '<div class="empty">Нет данных</div>';
  }
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join('')}</tr>
        </thead>
        <tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody>
      </table>
    </div>
  `;
}

function stepBlock(number, title, status, body) {
  return `
    <details class="step-block" open>
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

function slotStatus(slot) {
  const resolution = slotResolutionState(slot);
  if (resolution?.status) return resolution.status;
  const simulationValue = state.scenarioSimulation?.slot_values?.[slot.slot_id];
  if (simulationValue?.status) return simulationValue.status;
  if (!slot.required) return 'optional';
  return 'missing';
}

function slotDisplayValue(slot) {
  const simulationValue = state.scenarioSimulation?.slot_values?.[slot.slot_id];
  if (simulationValue?.value !== undefined && simulationValue?.value !== null && simulationValue?.value !== '') {
    return simulationValue.value;
  }
  const profile = slotResolutionProfile(slot);
  if (profile) return profile.display_name;
  if (slot.auto_fill_ref) return slot.auto_fill_ref;
  return 'н/д';
}

function slotFillMethod(slot) {
  if (slot.fill_method) return slot.fill_method;
  if (slot.source === 'user_question') return 'user_question';
  if (slot.source === 'case') return 'case';
  if (slot.source === 'llm') return 'llm_extraction';
  return 'resolution_profile';
}

function slotResolutionProfile(slot) {
  return (state.scenarioDetail?.attribute_resolution_profiles || [])
    .find((profile) => profile.profile_id === slot.resolution_profile_id);
}

function slotResolutionState(slot) {
  return state.scenarioSimulation?.resolution_state?.[slot.slot_id] || null;
}

function resolutionQuestion(slot, simulation) {
  const stateItem = slotResolutionState(slot);
  return stateItem?.pending_question || simulation?.next_question || slot.question || `Уточните ${slot.slot_id}`;
}

function resolutionProgressText(item) {
  if (!item) return 'н/д';
  const completed = (item.completed_steps || [])
    .map((step) => step.display_name)
    .join(' -> ');
  const current = item.current_step_name || 'ожидает запуска';
  return completed ? `${completed} -> ${current}` : current;
}

function launchRuntimeStatus(launch) {
  const ready = state.scenarioSimulation?.ready_tool_launches || [];
  const blocked = state.scenarioSimulation?.blocked_tool_launches || [];
  if (ready.some((item) => item.launch_id === launch.launch_id)) return 'ready';
  if (blocked.some((item) => item.launch_id === launch.launch_id)) return 'blocked';
  return 'pending';
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
  syncAnalyzeButton();
}

function renderScenarioSummary() {
  const detail = state.scenarioDetail;
  const simulation = state.scenarioSimulation;
  if (!detail) {
    elements.scenarioSummary.textContent = 'Сценарий не загружен';
    return;
  }
  const missingCount = simulation?.missing_slots?.length ?? 0;
  const route = detail.route || {};
  elements.scenarioSummary.innerHTML = [
    `<span>${escapeHtml(detail.scenario.display_name)}</span>`,
    badge(detail.readiness?.status),
    badge(route.priority),
    badge(simulation?.final_decision || 'pending'),
    `<span>Недостающих слотов: ${escapeHtml(missingCount)}</span>`,
  ].join(' ');
}

function renderQuestion() {
  const simulation = state.scenarioSimulation;
  const detail = state.scenarioDetail;
  if (!simulation || !detail) {
    elements.questionView.innerHTML = '<div class="empty">Вопрос появится после проверки слотов</div>';
    return;
  }
  const slotId = simulation.missing_slots?.[0];
  if (!slotId) {
    elements.questionView.innerHTML = `
      <div class="question-ready">
        <div class="question-title">Данных достаточно для следующего шага</div>
        <div class="question-meta">Оператор может запускать анализ, а сценарий перейдет к ReAct-планированию.</div>
      </div>
    `;
    return;
  }
  const slot = (detail.slot_schema?.slots || []).find((item) => item.slot_id === slotId) || {};
  const resolution = slotResolutionState(slot);
  const resolutionMeta = resolution
    ? `
      <div class="question-meta">Профиль: ${escapeHtml(resolution.profile_name)} / шаг: ${escapeHtml(resolution.current_step_name || 'н/д')} / попытка: ${escapeHtml(`${resolution.attempt || 1}/${resolution.max_attempts || 1}`)}</div>
      <div class="question-meta">${escapeHtml(resolution.reason || '')}</div>
    `
    : '';
  elements.questionView.innerHTML = `
    <div class="question-title">Нужно уточнение</div>
    <div class="question-text">${escapeHtml(resolutionQuestion(slot, simulation))}</div>
    <div class="question-meta">Слот: ${escapeHtml(slot.display_name || slotId)} / приоритет: ${
      escapeHtml(priorityGroupLabels[slot.priority_group] || slot.priority_group || 'н/д')
    }</div>
    ${resolutionMeta}
    <div class="question-input-row">
      <input id="slotAnswerInput" autocomplete="off" placeholder="Ответ пользователя или оператора">
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

function renderSteps() {
  const detail = state.scenarioDetail;
  if (!detail) {
    elements.stepsView.innerHTML = '<div class="empty">Сценарий не загружен</div>';
    return;
  }
  const simulation = state.scenarioSimulation;
  const slotSchema = detail.slot_schema || {};
  const route = detail.route || {};
  const policy = detail.orchestrator_policy || {};
  const escalation = detail.escalation_policy || {};
  const slotRows = orderedSlots(slotSchema).map((slot) => [
    escapeHtml(slot.display_name),
    escapeHtml(priorityGroupLabels[slot.priority_group] || slot.priority_group),
    badge(slot.required ? 'required' : 'optional'),
    escapeHtml(fillMethodLabels[slotFillMethod(slot)] || slotFillMethod(slot)),
    badge(slotStatus(slot)),
    escapeHtml(slot.question || slotResolutionProfile(slot)?.display_name || slot.auto_fill_ref || 'н/д'),
  ]);
  const resolutionRows = (simulation?.attribute_resolution || []).map((item) => [
    escapeHtml(slotLabel(slotSchema, item.slot_id)),
    escapeHtml(item.profile_name),
    badge(item.status),
    escapeHtml(item.current_step_name || 'н/д'),
    escapeHtml(`${item.attempt || 1}/${item.max_attempts || 1}`),
    escapeHtml(resolutionProgressText(item)),
    escapeHtml(item.pending_question || item.fallback?.question || item.fallback?.action || 'н/д'),
    escapeHtml(formatList(item.operator_handoff_package)),
  ]);
  const routeRows = [
    ['Правила', `${escapeHtml(route.confidence?.rules_min ?? 'н/д')} / ${escapeHtml(formatList(route.rules?.keywords))}`],
    ['LLM few-shot', escapeHtml(route.confidence?.llm_min ?? 'н/д')],
    ['Человек Л1 ниже', escapeHtml(route.confidence?.human_handoff_below ?? 'н/д')],
    ['Top категорий', escapeHtml(route.top_categories_on_low_confidence ?? 'н/д')],
    ['Совпадения в тексте', escapeHtml(formatList(simulation?.classification?.keyword_hits))],
  ];
  const launchRows = (detail.tool_launches || []).map((launch) => [
    badge(launchRuntimeStatus(launch)),
    escapeHtml(launch.tool_name),
    badge(launch.execution_level),
    badge(launch.target_execution_level),
    escapeHtml(formatList(launch.required_slots)),
    escapeHtml(`${launch.endpoint_profile} / ${launch.operation_id}`),
    badge(launch.risk_level),
  ]);
  const packageLabels = {
    slots: 'собранные слоты',
    react_history: 'история ReAct',
    tool_results: 'результаты инструментов',
    agent_hypothesis: 'гипотеза агента',
    sla_remaining: 'остаток SLA',
    user_notification: 'уведомление пользователя',
  };
  elements.stepsView.innerHTML = [
    stepBlock(
      1,
      'Приём и нормализация',
      simulation?.missing_slots?.length ? 'missing' : 'ready',
      `<div class="grid">
        ${metric('Сценарий', escapeHtml(scenarioName()))}
        ${metric('Обязательные слоты', escapeHtml(formatList(slotSchema.required_slots)))}
        ${metric('Автозаполнение', escapeHtml(formatList(slotSchema.auto_fill_slots)))}
        ${metric('Таймауты', escapeHtml(`${slotSchema.timeouts?.reminder_after_seconds || 'н/д'} сек / ${slotSchema.timeouts?.draft_after_seconds || 'н/д'} сек`))}
      </div>
      ${table(['Слот', 'Приоритет', 'Тип', 'Способ заполнения', 'Статус', 'Вопрос или профиль'], slotRows)}
      ${resolutionRows.length ? table(['Слот', 'Профиль', 'Статус', 'Текущий шаг', 'Попытка', 'Прогресс dry-run', 'Следующий вопрос', 'Пакет Л1'], resolutionRows) : ''}`,
    ),
    stepBlock(
      2,
      'Классификация и маршрутизация',
      simulation?.classification?.confidence >= 0.85 ? 'ready' : 'partial',
      `<div class="grid">
        ${metric('Приоритет', badge(route.priority))}
        ${metric('Маршрут', badge(route.route))}
        ${metric('Workflow state', escapeHtml(route.workflow_state_id || 'н/д'))}
        ${metric('Confidence dry-run', escapeHtml(simulation?.classification?.confidence ?? 'н/д'))}
      </div>
      ${table(['Уровень', 'Значение'], routeRows)}`,
    ),
    stepBlock(
      3,
      'Планирование ReAct',
      'ready',
      `<div class="grid">
        ${metric('Лимит итераций', escapeHtml(policy.max_iterations || 'н/д'))}
        ${metric('Ошибок до Л2', escapeHtml(policy.consecutive_tool_errors_to_escalate || 'н/д'))}
        ${metric('Классы инструментов', escapeHtml(formatList(policy.allowed_tool_classes)))}
        ${metric('Стоп-условия', escapeHtml(formatList(policy.stop_conditions, (item) => stopConditionLabels[item] || item)))}
      </div>`,
    ),
    stepBlock(
      4,
      'Выполнение и инструменты',
      simulation?.blocked_tool_launches?.length ? 'blocked' : 'ready',
      `${table(['Готовность', 'Инструмент', 'Текущий запуск', 'Целевой запуск', 'Слоты', 'Endpoint / операция', 'Риск'], launchRows)}
      <div class="hint">Action-инструменты в MVP запускаются через подтверждение оператора, даже если целевой режим уже отмечен как авто.</div>`,
    ),
    stepBlock(
      5,
      'Решение и эскалация',
      simulation?.final_decision || 'pending',
      `<div class="grid">
        ${metric('Автозакрытие', escapeHtml(escalation.auto_close?.requires_user_confirmation ? 'после подтверждения пользователя' : 'по политике'))}
        ${metric('Ожидание ответа', escapeHtml(`${escalation.waiting?.auto_close_after_hours || 'н/д'} ч`))}
        ${metric('Major Incident', escapeHtml(`${escalation.major_incident?.affected_users_threshold || 'н/д'} пользователей`))}
        ${metric('Пакет Л2', escapeHtml(formatList(escalation.escalation_package, (item) => packageLabels[item] || item)))}
      </div>
      <div class="message-block">
        <div class="metric-label">Уведомление пользователю</div>
        <p>${escapeHtml(escalation.user_notification_template || 'н/д')}</p>
      </div>`,
    ),
  ].join('');
}

function syncAnalyzeButton() {
  const missingSlots = state.dryRunEnabled ? (state.scenarioSimulation?.missing_slots || []) : [];
  const disabled = !state.scenarioDetail || (state.dryRunEnabled && (!state.scenarioSimulation || missingSlots.length > 0));
  elements.analyzeButton.disabled = disabled;
  elements.analyzeButton.title = missingSlots.length
    ? 'Сначала ответьте на вопрос обогащения заявки'
    : '';
}

async function loadScenarios() {
  try {
    const overview = await api('/operator/scenarios');
    state.scenarios = overview.scenarios || [];
    if (!state.scenarios.some((scenario) => scenario.scenario_id === state.scenarioId)) {
      state.scenarioId = state.scenarios[0]?.scenario_id || '';
    }
    renderScenarioSelect();
    if (state.scenarioId) {
      await loadScenarioDetail(state.scenarioId, { resetSlots: false });
    }
    elements.apiStatus.textContent = 'API готов';
  } catch (error) {
    elements.apiStatus.textContent = `Ошибка API: ${error.message}`;
    elements.stepsView.innerHTML = '<div class="empty">Сценарии не загружены</div>';
  }
}

async function loadScenarioDetail(scenarioId = state.scenarioId, options = {}) {
  if (!scenarioId) return;
  state.scenarioId = scenarioId;
  if (options.resetSlots) state.providedSlots = {};
  state.scenarioDetail = await api(`/operator/scenarios/${encodeURIComponent(scenarioId)}`);
  state.scenarioSimulation = null;
  renderScenario();
  if (state.dryRunEnabled) {
    await simulateScenario();
  }
}

async function simulateScenario() {
  if (!state.scenarioId) return;
  if (!state.dryRunEnabled) {
    state.scenarioSimulation = null;
    renderScenario();
    return;
  }
  elements.enrichButton.disabled = true;
  try {
    state.scenarioSimulation = await api(`/operator/scenarios/${encodeURIComponent(state.scenarioId)}/simulate`, {
      method: 'POST',
      body: JSON.stringify({
        text: elements.ticketText.value.trim(),
        provided_slots: state.providedSlots,
        operator_id: elements.operatorId.value.trim() || 'operator-1',
      }),
    });
  } catch (error) {
    state.scenarioSimulation = {
      schema_version: '1.0',
      scenario_id: state.scenarioId,
      input_text: elements.ticketText.value.trim(),
      slot_values: {},
      missing_slots: [],
      next_question: null,
      attribute_resolution: [],
      classification: {},
      ready_tool_launches: [],
      blocked_tool_launches: [],
      final_decision: 'error',
      dry_run: true,
      error: { message: error.message },
    };
    elements.apiStatus.textContent = `Ошибка сценария: ${error.message}`;
  } finally {
    elements.enrichButton.disabled = !state.dryRunEnabled;
    renderScenario();
  }
}

function scheduleScenarioSimulation() {
  if (!state.dryRunEnabled) return;
  if (state.scenarioSimulationTimer) {
    window.clearTimeout(state.scenarioSimulationTimer);
  }
  state.scenarioSimulationTimer = window.setTimeout(() => {
    state.scenarioSimulationTimer = null;
    simulateScenario();
  }, 350);
}

function addSlotAnswer() {
  const slotId = state.scenarioSimulation?.missing_slots?.[0];
  const input = document.getElementById('slotAnswerInput');
  const value = input?.value.trim();
  if (!slotId || !value) return;
  state.providedSlots[slotId] = value;
  if (input) input.value = '';
  simulateScenario();
}

function resetSlots() {
  state.providedSlots = {};
  simulateScenario();
}

function setDryRunEnabled(enabled) {
  state.dryRunEnabled = enabled;
  elements.enrichButton.disabled = !enabled;
  if (state.scenarioSimulationTimer) {
    window.clearTimeout(state.scenarioSimulationTimer);
    state.scenarioSimulationTimer = null;
  }
  if (enabled) {
    simulateScenario();
  } else {
    state.scenarioSimulation = null;
    renderScenario();
  }
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
  if ((state.scenarioSimulation?.missing_slots || []).length) return 'clarification';
  if (route === 'l2_major_incident' || route === 'l1_hint') return 'escalation';
  if (hasLaunches) return 'runbook';
  return 'answer';
}

function formPayload() {
  const text = elements.ticketText.value.trim();
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
    environment: firstSlotValue(['environment']) || 'prod',
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
  if ((state.scenarioSimulation?.missing_slots || []).length) {
    renderQuestion();
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
    operator_id: elements.operatorId.value.trim() || 'operator-1',
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

elements.loadScenarioButton.addEventListener('click', () => loadScenarioDetail(state.scenarioId, { resetSlots: false }));
elements.enrichButton.addEventListener('click', simulateScenario);
elements.resetSlotsButton.addEventListener('click', resetSlots);
elements.scenarioSelect.addEventListener('change', (event) => loadScenarioDetail(event.target.value, { resetSlots: true }));
elements.ticketText.addEventListener('input', scheduleScenarioSimulation);
elements.dryRunToggle.addEventListener('change', (event) => setDryRunEnabled(event.target.checked));
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

renderAnalysis();
renderScenario();
loadScenarios();
loadKnowledgeStatus();
