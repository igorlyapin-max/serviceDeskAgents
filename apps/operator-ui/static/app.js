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
  testRunMode: 'config_check',
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
};

const visibleLabels = {
  active: 'активно',
  auto: 'авто',
  auto_agent: 'автоагент',
  auto_fill_candidate: 'кандидат автозаполнения',
  blocked: 'заблокировано',
  continue_slot_filling: 'нужно обогащение',
  blocked_by_configuration: 'ошибка конфигурации',
  draft: 'черновик',
  error: 'ошибка',
  failed: 'ошибка',
  incomplete: 'неполно',
  info: 'информация',
  agent_with_confirmation: 'агент + подтверждение',
  human_review: 'человек + подсказка',
  major_incident: 'Major Incident',
  missing: 'требуется ответ',
  model_unavailable: 'модель недоступна',
  operator_approval: 'согласование оператора',
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
  extraction_pending: 'ожидает извлечения',
  filled_by_model: 'заполнено моделью',
  candidate_below_threshold: 'результат ниже порога',
  waiting_operator_approval: 'ожидает подтверждения',
  question_required: 'нужно уточнение',
  resolution_profile: 'профиль разрешения',
  dry_run_simulated: 'смоделировано',
  success: 'успешно',
  unavailable: 'недоступно',
  user_question: 'вопрос пользователю',
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
  operator_handoff: 'передача человеку',
  escalate: 'эскалация',
  online_interactive: 'онлайн-интерактивный',
  offline_interactive: 'офлайн-интерактивный',
  debug: 'отладочный режим',
  ask_end_user: 'вопрос пользователю',
  ask_operator: 'вопрос оператору',
  show_debug_message: 'показать в отладке',
  save_context: 'сохранить контекст',
  create_draft: 'создать черновик',
  create_work_order: 'создать наряд',
  call_specialist: 'позвать специалиста',
  notify_on_call: 'оповестить дежурных',
  debug_stop: 'остановить с сообщением',
  standard_handoff: 'обычная передача',
  no_answer: 'нет ответа',
  policy_blocked: 'policy blocked',
  all_required_slots_filled: 'все обязательные слоты заполнены',
  tool_success: 'успешный результат инструмента',
  clarification_required: 'нужно уточнение',
  handoff_required: 'требуется передача',
  iteration_limit: 'лимит итераций',
  consecutive_tool_errors: 'ошибки инструментов подряд',
  read_diagnostics: 'чтение и диагностика',
  knowledge_search: 'поиск в знаниях',
  external_status_check: 'проверка внешних систем',
  action_preparation: 'подготовка действия',
  state_changing_actions: 'действия с изменением состояния',
  communication_handoff: 'коммуникация и передача',
  react_call: 'ReAct-вызов чтения',
  ticket_history: 'история заявок',
  case_data: 'данные обращения',
  auto_fill_if_confident: 'заполнить при достаточной уверенности',
  ask_clarification: 'уточнить',
  ask_disambiguation: 'уточнить выбор результата',
  empty_result: 'результат не найден',
  single_result: 'один результат',
  multiple_results: 'несколько результатов',
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
  case: 'из данных обращения',
  llm_extraction: 'извлечение моделью',
  resolution_profile: 'профиль разрешения',
  operator_manual: 'ручное заполнение оператором',
};

const stopConditionLabels = {
  all_required_slots_filled: 'все обязательные слоты заполнены',
  tool_success: 'получен успешный результат инструмента',
  clarification_required: 'нужно уточнение',
  handoff_required: 'требуется передача',
  iteration_limit: 'достигнут лимит итераций',
  consecutive_tool_errors: 'ошибки инструментов подряд',
};

const reactActionGroupLabels = {
  read_diagnostics: 'чтение и диагностика',
  knowledge_search: 'поиск в знаниях',
  external_status_check: 'проверка внешних систем',
  action_preparation: 'подготовка действия',
  state_changing_actions: 'действия с изменением состояния',
  communication_handoff: 'коммуникация и передача',
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

function formatMap(map) {
  const entries = Object.entries(map || {});
  return entries.length
    ? entries.map(([key, value]) => `${escapeHtml(key)} = ${escapeHtml(value)}`).join(', ')
    : 'н/д';
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
  if (slot.case_source_ref) return slot.case_source_ref;
  if (slot.extraction_instruction) return slot.extraction_instruction;
  if (slot.operator_hint) return slot.operator_hint;
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
  return stateItem?.pending_question || simulation?.next_question || slotQuestionText(slot) || '';
}

function slotQuestionText(slot) {
  const fillMethod = slotFillMethod(slot);
  if (fillMethod === 'user_question') return slot.user_question || slot.question;
  if (fillMethod === 'resolution_profile') return slot.fallback_question || slot.question;
  if (fillMethod === 'operator_manual') return slot.operator_hint || slot.question;
  return '';
}

function slotContextText(slot) {
  const fillMethod = slotFillMethod(slot);
  if (fillMethod === 'user_question') return slot.user_question || slot.question || 'н/д';
  if (fillMethod === 'case') return slot.case_source_ref || slot.auto_fill_ref || 'н/д';
  if (fillMethod === 'llm_extraction') return slot.extraction_instruction || slot.question || 'н/д';
  if (fillMethod === 'resolution_profile') return slotResolutionProfile(slot)?.display_name || slot.fallback_question || slot.question || 'н/д';
  if (fillMethod === 'operator_manual') return slot.operator_hint || slot.question || 'н/д';
  return 'н/д';
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

function launchRuntimeStatus(launch) {
  const runtime = launchRuntimeSummary(launch);
  return runtime?.status || 'pending';
}

function launchRuntimeSummary(launch) {
  const ready = state.scenarioSimulation?.ready_tool_launches || [];
  const blocked = state.scenarioSimulation?.blocked_tool_launches || [];
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
    `<span>Вопросов оператору: ${escapeHtml(answerableCount)}</span>`,
    mode.allow_llm ? '<span>LLM включен</span>' : '<span>LLM выключен</span>',
  ].join(' ');
}

function renderQuestion() {
  const simulation = state.scenarioSimulation;
  const detail = state.scenarioDetail;
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
    <div class="question-title">Нужно уточнение</div>
    <div class="question-text">${escapeHtml(resolutionQuestion(slot, simulation))}</div>
    <div class="question-meta">Слот: ${escapeHtml(slot.display_name || slotId)} / приоритет: ${
      escapeHtml(priorityGroupLabels[slot.priority_group] || slot.priority_group || 'н/д')
    }</div>
    <div class="question-meta">Канал: ${escapeHtml(channel.display_name || 'н/д')} / доставка: ${escapeHtml(visibleLabels[questionDelivery.action_type] || questionDelivery.action_type || 'н/д')}</div>
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
  const channel = simulation?.interaction_channel || detail.interaction_channel || {};
  const waitingPolicy = simulation?.waiting_policy || channel.waiting_policy || {};
  const escalationAction = simulation?.escalation_action || channel.escalation_action || {};
  const channelProfiles = simulation?.channel_action_profiles || detail.channel_action_profiles || {};
  const slotRows = orderedSlots(slotSchema).map((slot) => [
    escapeHtml(slot.display_name),
    escapeHtml(priorityGroupLabels[slot.priority_group] || slot.priority_group),
    badge(slot.required ? 'required' : 'optional'),
    escapeHtml(fillMethodLabels[slotFillMethod(slot)] || slotFillMethod(slot)),
    badge(slotStatus(slot)),
    escapeHtml(state.scenarioSimulation?.slot_values?.[slot.slot_id]?.confidence ?? 'н/д'),
    escapeHtml(slotContextText(slot)),
    escapeHtml(state.scenarioSimulation?.slot_values?.[slot.slot_id]?.reason || 'н/д'),
  ]);
  const resolutionRows = (simulation?.attribute_resolution || []).map((item) => [
    escapeHtml(slotLabel(slotSchema, item.slot_id)),
    escapeHtml(item.profile_name),
    badge(item.status),
    escapeHtml(visibleLabels[item.candidate_source?.source_type] || item.candidate_source?.source_type || 'н/д'),
    escapeHtml(`${item.attempt || 1}/${item.max_attempts || 1}`),
    escapeHtml(resolutionProgressText(item)),
    escapeHtml(item.pending_question || item.fallback?.question || item.fallback?.action || 'н/д'),
    escapeHtml(formatList(item.handoff_policy?.package)),
  ]);
  const routeRows = [
    ['Правила', `${escapeHtml(route.confidence?.rules_min ?? 'н/д')} / ${escapeHtml(formatList(route.rules?.keywords))}`],
    ['LLM few-shot', escapeHtml(route.confidence?.llm_min ?? 'н/д')],
    ['Передача человеку ниже', escapeHtml(route.confidence?.human_handoff_below ?? 'н/д')],
    ['Top категорий', escapeHtml(route.top_categories_on_low_confidence ?? 'н/д')],
    ['Совпадения в тексте', escapeHtml(formatList(simulation?.classification?.keyword_hits))],
  ];
  const launchRows = (detail.tool_launches || []).map((launch) => {
    const runtime = launchRuntimeSummary(launch);
    const blockReasons = [
      ...(runtime.missing_slots || []).map((slotId) => `не заполнен: ${slotId}`),
      ...(runtime.unknown_required_slots || []).map((slotId) => `нет в схеме: ${slotId}`),
    ];
    return [
      badge(runtime.status),
      escapeHtml(launch.tool_name),
      badge(launch.target_execution_level || launch.execution_level),
      escapeHtml(formatList(launch.required_slots)),
      formatMap(launch.parameter_bindings),
      escapeHtml(`${launch.endpoint_id} / ${launch.operation_id}`),
      badge(launch.risk_level),
      formatList(blockReasons),
    ];
  });
  const packageLabels = {
    slots: 'собранные слоты',
    react_history: 'история ReAct',
    tool_results: 'результаты инструментов',
    agent_hypothesis: 'гипотеза агента',
    sla_remaining: 'остаток SLA',
    user_notification: 'уведомление пользователя',
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
  const executionTraceRows = (simulation?.execution_trace || []).map((item) => [
    escapeHtml(item.step || 'н/д'),
    badge(item.status || 'info'),
    escapeHtml(item.title || 'н/д'),
    escapeHtml(item.message || 'н/д'),
  ]);
  elements.stepsView.innerHTML = [
    stepBlock(
      1,
      'Приём и нормализация',
      answerableMissingSlotIds(simulation, detail).length
        ? 'missing'
        : (simulation?.missing_slots?.length ? 'partial' : 'ready'),
      `<div class="grid">
        ${metric('Сценарий', escapeHtml(scenarioName()))}
        ${metric('Обязательные слоты', escapeHtml(formatList(slotSchema.required_slots)))}
        ${metric('Автозаполнение', escapeHtml(formatList(slotSchema.auto_fill_slots)))}
        ${metric('Таймауты', escapeHtml(`${slotSchema.timeouts?.reminder_after_seconds || 'н/д'} сек / ${slotSchema.timeouts?.draft_after_seconds || 'н/д'} сек`))}
      </div>
      ${table(['Слот', 'Приоритет', 'Тип', 'Способ заполнения', 'Статус', 'Confidence', 'Настройка заполнения', 'Причина'], slotRows)}
      ${resolutionRows.length ? table(['Слот', 'Профиль', 'Статус', 'Операция разрешения', 'Попытка', 'Решение dry-run', 'Следующий вопрос', 'Пакет передачи'], resolutionRows) : ''}`,
    ),
    stepBlock(
      2,
      'Классификация и маршрутизация',
      simulation?.classification?.confidence >= 0.85 ? 'ready' : 'partial',
      `<div class="grid">
        ${metric('Приоритет', badge(route.priority))}
        ${metric('Маршрут', badge(route.route))}
        ${metric('Workflow state', escapeHtml(route.workflow_state_id || 'н/д'))}
        ${metric('Канал', escapeHtml(channel.display_name || 'н/д'))}
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
        ${metric('Ошибок до эскалации', escapeHtml(policy.consecutive_tool_errors_to_escalate || 'н/д'))}
        ${metric('Группы действий ReAct', escapeHtml(formatList(policy.allowed_react_action_groups, (item) => reactActionGroupLabels[item] || item)))}
        ${metric('Стоп-условия', escapeHtml(formatList(policy.stop_conditions, (item) => stopConditionLabels[item] || item)))}
      </div>`,
    ),
    stepBlock(
      4,
      'Выполнение и инструменты',
      simulation?.blocked_tool_launches?.length ? 'blocked' : 'ready',
      `${table(['Готовность', 'ReAct-вызов', 'Вид запуска', 'Слоты', 'Параметры вызова', 'Подключение / операция', 'Риск', 'Причина блокировки'], launchRows)}
      <div class="hint">Action-инструменты в MVP запускаются через подтверждение оператора, даже если вид запуска отмечен как авто.</div>`,
    ),
    stepBlock(
      5,
      'Решение и эскалация',
      simulation?.final_decision || 'pending',
      `<div class="grid">
        ${metric('Автозакрытие', escapeHtml(escalation.auto_close?.requires_user_confirmation ? 'после подтверждения пользователя' : 'по политике'))}
        ${metric('Ожидание ответа', escapeHtml(`${escalation.waiting?.auto_close_after_hours || 'н/д'} ч`))}
        ${metric('Таймаут канала', escapeHtml(`${waitingPolicy.first_reminder_after_seconds ?? 'н/д'} сек / ${waitingPolicy.discussion_timeout_seconds ?? 'н/д'} сек`))}
        ${metric('Нет ответа', badge(waitingPolicy.on_no_answer || 'missing'))}
        ${metric('Действие эскалации', badge(escalationAction.action_type || 'missing'))}
        ${metric('Major Incident', escapeHtml(`${escalation.major_incident?.affected_users_threshold || 'н/д'} пользователей`))}
        ${metric('Условия передачи', escapeHtml(formatList(escalation.handoff_conditions, (item) => conditionLabels[item] || item)))}
        ${metric('Пакет передачи', escapeHtml(formatList(escalation.handoff_package, (item) => packageLabels[item] || item)))}
      </div>
      ${profileRows.length ? table(['Событие', 'Профиль канала', 'Действие', 'ReAct-вызов / подключение / операция'], profileRows) : ''}
      <div class="message-block">
        <div class="metric-label">Уведомление пользователю</div>
        <p>${escapeHtml(escalation.user_notification_template || 'н/д')}</p>
      </div>
      ${executionTraceRows.length ? `
        <div class="message-block">
          <div class="metric-label">Трасса тестового прогона</div>
          ${table(['Шаг', 'Статус', 'Событие', 'Сообщение'], executionTraceRows)}
        </div>
      ` : ''}`,
    ),
  ].join('');
}

function syncAnalyzeButton() {
  const answerableSlots = state.dryRunEnabled ? answerableMissingSlotIds() : [];
  const disabled = !state.scenarioDetail || (state.dryRunEnabled && !state.scenarioSimulation) || answerableSlots.length > 0;
  elements.analyzeButton.disabled = disabled;
  elements.analyzeButton.title = answerableSlots.length
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
    const runOptions = currentTestRunOptions();
    state.scenarioSimulation = await api(`/operator/scenarios/${encodeURIComponent(state.scenarioId)}/simulate`, {
      method: 'POST',
      body: JSON.stringify({
        text: elements.ticketText.value.trim(),
        provided_slots: state.providedSlots,
        operator_id: elements.operatorId.value.trim() || 'operator-1',
        ...runOptions,
      }),
    });
  } catch (error) {
    const runOptions = currentTestRunOptions();
    state.scenarioSimulation = {
      schema_version: '1.0',
      scenario_id: state.scenarioId,
      input_text: elements.ticketText.value.trim(),
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
  await loadScenarioDetail(state.scenarioId, { resetSlots: false });
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
  if (answerableMissingSlotIds().length) return 'clarification';
  if (route === 'major_incident' || route === 'human_review') return 'escalation';
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
    if (state.scenarioSimulation) {
      if (state.activeTab === 'tools') {
        const trace = state.scenarioSimulation.execution_trace || [];
        elements.traceView.innerHTML = trace.length
          ? trace.map((item) => `
              <div class="trace-item">
                <div class="trace-title">${escapeHtml(item.title)} ${badge(item.status)}</div>
                <div class="trace-meta">Шаг ${escapeHtml(item.step)} / ${escapeHtml(item.message)}</div>
              </div>
            `).join('')
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
  if (answerableMissingSlotIds().length) {
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

elements.loadScenarioButton.addEventListener('click', refreshScenarioPreservingInput);
elements.enrichButton.addEventListener('click', simulateScenario);
elements.resetSlotsButton.addEventListener('click', resetSlots);
elements.scenarioSelect.addEventListener('change', (event) => loadScenarioDetail(event.target.value, { resetSlots: true }));
elements.ticketText.addEventListener('input', scheduleScenarioSimulation);
elements.dryRunToggle.addEventListener('change', (event) => setDryRunEnabled(event.target.checked));
elements.testRunMode?.addEventListener('change', () => {
  syncTestRunModeDefaults();
  scheduleScenarioSimulation();
});
[
  elements.allowLlmToggle,
  elements.allowReadonlyToggle,
  elements.allowMockToggle,
  elements.allowActionApprovalToggle,
].forEach((toggle) => {
  toggle?.addEventListener('change', scheduleScenarioSimulation);
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

syncTestRunModeDefaults();
renderAnalysis();
renderScenario();
loadScenarios();
loadKnowledgeStatus();
