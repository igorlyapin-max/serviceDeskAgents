const state = {
  activeView: 'dashboard',
  actorId: 'admin-1',
  scenarioId: 'password_reset',
  scenarioOperation: 'modify',
  slotSchemaId: 'slot.password_reset',
  slotSchemaOperation: 'modify',
  slotAutofillProfileId: '',
  slotAutofillOperation: 'modify',
  routeId: 'route.password_reset',
  routeOperation: 'modify',
  policyId: 'policy.password_reset',
  policyOperation: 'modify',
  toolMatrixId: 'matrix.password_reset',
  toolMatrixOperation: 'modify',
  escalationPolicyId: 'escalation.password_reset',
  escalationOperation: 'modify',
  promptPackId: 'prompt.password_reset',
  promptPackOperation: 'modify',
  interactionChannelId: 'debug',
  interactionChannelOperation: 'modify',
  resolutionProfileId: 'profile.password_reset.login_from_ad',
  resolutionOperation: 'modify',
  resolutionSlotScenarioId: 'password_reset',
  resolutionSlotProfileId: '',
  resolutionEnrichmentEditIndex: 0,
  integrationEndpointId: 'mock',
  integrationEndpointOperation: 'modify',
  toolCatalogName: 'start_systemcenter_runbook',
  toolCatalogOperation: 'modify',
  operationBindingToolName: 'start_systemcenter_runbook',
  operationBindingLastToolName: '',
  operationBindingMode: 'bind',
  operationBindingEndpointId: 'mock',
  operationBindingOperationId: 'start_systemcenter_runbook',
  orchestrationGraphView: 'scenario',
  orchestrationGraphScenarioId: 'password_reset',
  orchestrationGraphSelectedNodeId: 'slot_filling',
  orchestrationGraphZoom: 0.78,
  orchestrationGraphPanX: 24,
  orchestrationGraphPanY: 34,
  processingCaseId: '',
  modelRoutingBaseVersionId: '',
  referenceAutocomplete: {
    textarea: null,
    start: -1,
    selectedIndex: 0,
    items: [],
  },
  lastData: {
    toolCatalog: [],
    integrationEndpoints: [],
    n8nWorkflows: [],
  },
};

const viewTitles = {
  dashboard: 'Панель обзора',
  processing: 'Поток обработки',
  scenarios: 'Сценарии',
  orchestrationGraph: 'Граф оркестрации',
  scenarioSlots: '0. Слоты',
  slotAutofill: '0.1 Автозаполнение слотов',
  scenarioClassification: '2. Классификация и маршрут',
  scenarioReact: '3. ReAct-планирование',
  scenarioTools: '4. ReAct-вызовы и матрица запуска',
  scenarioEscalation: '5. Решение и эскалация',
  scenarioPrompts: '6. Промпты',
  interactionChannels: 'Каналы взаимодействия',
  resolution: '1. Разрешение атрибутов',
  knowledge: 'База знаний',
  integrations: 'Интеграции',
  reactCalls: 'ReAct-вызовы ИИ',
  operationBindings: 'Привязка операций',
  tools: 'Интеграции',
  workflow: 'Рабочий процесс',
  models: 'Модели',
  quality: 'Контроль качества',
  audit: 'Аудит',
  security: 'Безопасность',
};

const viewsWithoutPageHeader = new Set([
  'scenarios',
  'scenarioSlots',
  'slotAutofill',
  'resolution',
  'scenarioClassification',
  'scenarioReact',
  'scenarioEscalation',
  'scenarioPrompts',
  'interactionChannels',
]);

const visibleLabels = {
  active: 'активно',
  admin: 'администратор',
  blocked: 'заблокировано',
  completed: 'завершено',
  configured: 'настроено',
  denied: 'отказано',
  disabled: 'отключено',
  enabled: 'включено',
  error: 'ошибка',
  external: 'внешнее хранилище',
  failed: 'ошибка',
  info: 'информация',
  invalid: 'невалидно',
  missing: 'не задано',
  ok: 'норма',
  partial: 'частично',
  passed: 'пройдено',
  pending: 'ожидает',
  planned: 'запланировано',
  optional: 'необязательный',
  required: 'обязательный',
  read_only: 'только чтение',
  running: 'выполняется',
  skipped: 'пропущено',
  success: 'успешно',
  terminal: 'терминальное',
  unknown: 'неизвестно',
  valid: 'валидно',
  ready: 'готово',
  incomplete: 'неполно',
  auto: 'авто',
  ask_user: 'спросить клиента',
  operator_approval: 'согласование оператора',
  operator_handoff: 'эскалировать оператору',
  approver_approval: 'согласование руководителя',
  case: 'из данных обращения',
  llm_extraction: 'извлечение моделью',
  leave_empty: 'оставить пустым',
  auto_agent: 'автоагент',
  agent_with_confirmation: 'агент + подтверждение',
  human_review: 'человек + подсказка',
  major_incident: 'Major Incident',
  approver: 'согласующий',
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
  policy_blocked: 'policy blocked',
  operator_manual: 'ручное заполнение оператором',
  slot_autofill: 'ReAct-автозаполнение',
  resolution_pending: 'ожидает разрешения',
  resolution_profile: 'профиль разрешения',
  user_question: 'вопрос клиенту',
  llm_extract: 'извлечение из текста моделью',
  rag_search: 'поиск в базе знаний',
  case_read: 'чтение из данных обращения',
  tool_call: 'ReAct-вызов ИИ',
  ticket_history_search: 'поиск по истории заявок',
  condition: 'условие',
  clarification: 'уточнение у клиента',
  fill_slot: 'заполнение слота',
  escalate: 'эскалация',
  sequential: 'последовательно',
  branching: 'с ветвлениями',
  profile: 'на профиль',
  step: 'на шаг',
  clarification_required: 'нужно уточнение у клиента',
  all_required_slots_filled: 'все обязательные слоты заполнены',
  tool_success: 'успешный результат ReAct-вызова',
  handoff_required: 'требуется эскалация оператору',
  iteration_limit: 'лимит итераций',
  consecutive_tool_errors: 'ошибки ReAct-вызовов подряд',
  slot: 'слот',
  react: 'параметр ReAct-вызова',
  constant: 'константа',
  secret: 'секрет',
  context: 'контекст',
  read_diagnostics: 'чтение и диагностика',
  knowledge_search: 'поиск в знаниях',
  external_status_check: 'проверка внешних систем',
  action_preparation: 'подготовка действия',
  state_changing_actions: 'действия с изменением состояния',
  communication_handoff: 'коммуникация и эскалация',
  action: 'действие',
  vllm_cpu: 'vLLM CPU',
  openai: 'OpenAI API',
  litellm: 'LiteLLM',
  p1: 'P1',
  p2: 'P2',
  p3: 'P3',
  p4: 'P4',
  mock: 'mock',
  n8n_webhook: 'n8n webhook',
  direct_http: 'direct http',
  queue: 'queue',
  header_token: 'токен в заголовке',
  bearer_token: 'bearer token',
  none: 'без авторизации',
  phrase: 'фраза',
  word: 'слово',
  contains: 'вхождение',
  positive: 'позитивное',
  negative: 'негативное',
  accepted_by_rules: 'принято правилами',
  llm_required: 'нужна LLM-классификация',
  human_review_required: 'нужна проверка оператором',
  human_required: 'эскалировать оператору',
  queued: 'в очереди',
  leased: 'lease выдан',
  waiting: 'ожидание',
  cancelled: 'отменено',
  canceled: 'отменено',
  cancel: 'отменить',
  escalated: 'эскалировано',
  timed_out: 'timeout',
  expired: 'истекло',
  stale: 'зависло',
  open: 'открыто',
  reminded: 'напоминание отправлено',
  client_wait: 'ожидание клиента',
  external_wait: 'ожидание внешнего события',
  operator_approval: 'согласование оператора',
  react_call: 'ReAct-вызов ИИ',
  client_question: 'вопрос клиенту',
  approval: 'согласование',
  timer: 'таймер',
  system_policy: 'политика системы',
  external_event_wait: 'ожидание external event',
  external_event: 'external event/callback',
  timer_wait: 'таймер/повторная проверка',
  sync: 'синхронно',
  resume_agent: 'возобновить агента',
  escalate_operator: 'эскалировать оператору',
  mark_failed: 'завершить ошибкой',
  langgraph_run: 'LangGraph run',
  tool_use: 'ReAct-вызовы',
  decision: 'решение',
};

const activeResolverSourceTypes = ['react_call', 'disabled'];
const activeEndpointAdapterTypes = ['mock', 'n8n_webhook'];
const activeLaunchExecutionModes = ['auto', 'operator_approval', 'blocked'];
const completionModes = ['sync', 'external_event', 'timer_wait'];
const completionTimeoutActions = ['resume_agent', 'escalate_operator', 'debug_stop', 'mark_failed', 'cancel'];
const operationContractTypes = ['string', 'integer', 'number', 'boolean', 'array', 'object'];
const operationArrayItemTypes = ['string', 'integer', 'number', 'boolean', 'object'];
const operationContractTypeLabels = {
  string: 'строка',
  integer: 'целое число',
  number: 'число',
  boolean: 'да/нет',
  array: 'массив',
  object: 'объект',
};

const handoffConditionChoices = [
  {
    value: 'two_tool_errors',
    label: '2 ошибки ReAct-вызовов подряд',
    help: 'Срабатывает, когда ReAct получил два неуспешных результата вызовов подряд.',
  },
  {
    value: 'iteration_limit',
    label: 'Достигнут лимит ReAct-итераций',
    help: 'Лимит задается в блоке "3. ReAct-планирование".',
  },
  {
    value: 'confidence_below_050',
    label: 'Confidence ниже порога',
    help: 'Эскалация оператору включается, когда уверенность решения ниже 0.50.',
  },
  {
    value: 'affected_users_threshold',
    label: 'Превышен порог Major Incident',
    help: 'Порог количества затронутых пользователей задается в этом блоке.',
  },
  {
    value: 'policy_blocked',
    label: 'Политика заблокировала автоисполнение',
    help: 'Срабатывает, когда Execution Policy или матрица запуска запрещает действие.',
  },
];

const handoffPackageChoices = [
  {
    value: 'slots',
    label: 'Собранные слоты',
    help: 'Кто, что, где, когда и другие заполненные атрибуты обращения.',
    required: true,
  },
  {
    value: 'react_history',
    label: 'История ReAct',
    help: 'Последовательность "думай -> действуй -> наблюдай" с промежуточными решениями.',
  },
  {
    value: 'tool_results',
    label: 'Результаты ReAct-вызовов',
    help: 'Ответы вызванных ReAct-вызовов, статусы и ошибки.',
  },
  {
    value: 'agent_hypothesis',
    label: 'Гипотеза агента',
    help: 'Предположение агента о причине и следующем действии.',
  },
  {
    value: 'sla_remaining',
    label: 'Остаток SLA',
    help: 'Сколько времени осталось до нарушения SLA на момент эскалации оператору.',
  },
  {
    value: 'user_notification',
    label: 'Текст уведомления клиента',
    help: 'Сообщение, которое увидит клиент или оператор канала.',
    required: true,
  },
];

const reactActionGroupChoices = [
  {
    value: 'read_diagnostics',
    label: 'Чтение и диагностика',
    help: 'Локальная диагностика, разбор симптомов и безопасные проверки без изменения систем.',
  },
  {
    value: 'knowledge_search',
    label: 'Поиск в знаниях',
    help: 'RAG, корпоративная база знаний, FAQ, runbooks и справочные материалы.',
  },
  {
    value: 'external_status_check',
    label: 'Проверка внешних систем',
    help: 'Мониторинг, CMDB, AD, статусы сервисов и другие read-only интеграции.',
  },
  {
    value: 'action_preparation',
    label: 'Подготовка действия',
    help: 'Сформировать proposed action и параметры без фактического исполнения.',
  },
  {
    value: 'state_changing_actions',
    label: 'Действия с изменением состояния',
    help: 'Потенциально меняют системы. Реальный запуск все равно контролируют блок 4 и Execution Policy.',
  },
  {
    value: 'communication_handoff',
    label: 'Коммуникация и эскалация',
    help: 'Уточняющие вопросы клиенту, уведомления и эскалация оператору через канал взаимодействия.',
  },
];

const reactStopConditionChoices = [
  {
    value: 'all_required_slots_filled',
    label: 'Все обязательные слоты заполнены',
    help: 'ReAct может стартовать или завершить сбор данных, когда нет недостающих обязательных слотов.',
  },
  {
    value: 'tool_success',
    label: 'Получен успешный результат ReAct-вызова',
    help: 'Цель итерации достигнута после успешного ответа ReAct-вызова ИИ.',
  },
  {
    value: 'clarification_required',
    label: 'Нужно уточнение у клиента',
    help: 'Оркестратор задает клиенту следующий вопрос через выбранный канал и продолжает сценарий после ответа.',
  },
  {
    value: 'handoff_required',
    label: 'Требуется эскалация оператору',
    help: 'AI прекращает самостоятельную обработку, а дальнейшее действие определяется блоком 5 и каналом взаимодействия.',
  },
  {
    value: 'iteration_limit',
    label: 'Достигнут лимит итераций',
    help: 'Срабатывает при достижении поля "Максимум итераций" в этом блоке.',
  },
  {
    value: 'consecutive_tool_errors',
    label: 'Ошибки ReAct-вызовов подряд',
    help: 'Срабатывает при достижении поля "Ошибок ReAct-вызовов подряд до эскалации оператору".',
  },
];

const elements = {
  apiStatus: document.getElementById('apiStatus'),
  actorId: document.getElementById('actorId'),
  pageHeader: document.querySelector('.page-header'),
  refreshButton: document.getElementById('refreshButton'),
  viewTitle: document.getElementById('viewTitle'),
  viewContent: document.getElementById('viewContent'),
  notice: document.getElementById('notice'),
  navItems: Array.from(document.querySelectorAll('[data-view]')),
};

function headers(extra = {}) {
  return {
    'Content-Type': 'application/json',
    'X-ServiceDesk-Actor': state.actorId,
    'X-ServiceDesk-Session': `admin-ui:${state.actorId}`,
    ...extra,
  };
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: headers(options.headers || {}),
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

function jsonBlock(value) {
  return `<pre class="json-panel">${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
}

function stripHtml(value) {
  const template = document.createElement('template');
  template.innerHTML = String(value ?? '');
  return template.content.textContent.trim();
}

function badge(value) {
  const label = String(value ?? 'н/д');
  const normalized = label.replace(/[^a-zа-яё0-9_-]/gi, '_').toLowerCase();
  return `<span class="badge ${escapeHtml(normalized)}">${escapeHtml(visibleLabels[normalized] || label)}</span>`;
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

function mobileResourceCards(headersList, rows) {
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
                  <div class="resource-card-label">${escapeHtml(headersList[index] || '')}</div>
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

function table(headersList, rows) {
  if (!rows.length) {
    return '<div class="empty">Нет данных</div>';
  }
  return `
    <div class="table-wrap has-resource-cards">
      <table>
        <thead>
          <tr>${headersList.map((header) => `<th>${escapeHtml(header)}</th>`).join('')}</tr>
        </thead>
        <tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody>
      </table>
      ${mobileResourceCards(headersList, rows)}
    </div>
  `;
}

function formatList(items, mapper = (item) => item) {
  if (!items || !items.length) return 'н/д';
  return items.map(mapper).join(', ');
}

function setNotice(message, type = 'info') {
  if (!message) {
    elements.notice.hidden = true;
    elements.notice.textContent = '';
    return;
  }
  elements.notice.hidden = false;
  elements.notice.textContent = message;
  elements.notice.dataset.type = type;
}

function setBusy(isBusy) {
  elements.refreshButton.disabled = isBusy;
  if (isBusy) {
    elements.apiStatus.textContent = 'Загрузка';
  }
}

function section(title, body, actions = '') {
  const currentViewTitle = viewTitles[state.activeView] || state.activeView;
  const isDuplicateTitle = String(title || '').trim() === String(currentViewTitle || '').trim();
  const actionsHtml = actions ? `<div class="section-actions">${actions}</div>` : '';
  const headerHtml = isDuplicateTitle
    ? (actionsHtml ? `<div class="section-head actions-only">${actionsHtml}</div>` : '')
    : `<div class="section-head">
        <h2 class="section-title">${escapeHtml(title)}</h2>
        ${actionsHtml || '<div></div>'}
      </div>`;
  return `
    <section class="section">
      ${headerHtml}
      ${body}
    </section>
  `;
}

async function loadView(view = state.activeView) {
  state.activeView = view;
  state.actorId = elements.actorId.value.trim() || 'admin-1';
  const withoutPageHeader = viewsWithoutPageHeader.has(view);
  elements.pageHeader.hidden = withoutPageHeader;
  elements.pageHeader.classList.toggle('page-header-hidden', withoutPageHeader);
  if (withoutPageHeader) {
    elements.pageHeader.setAttribute('aria-hidden', 'true');
  } else {
    elements.pageHeader.removeAttribute('aria-hidden');
  }
  elements.viewTitle.textContent = viewTitles[view] || view;
  elements.navItems.forEach((item) => item.classList.toggle('active', item.dataset.view === view));
  setNotice('');
  setBusy(true);
  try {
    await renderView(view);
    elements.apiStatus.textContent = 'Готово';
  } catch (error) {
    elements.viewContent.innerHTML = '<div class="empty">Раздел не загружен</div>';
    setNotice(error.message || String(error), 'error');
    elements.apiStatus.textContent = 'Ошибка API';
  } finally {
    setBusy(false);
  }
}

async function renderView(view) {
  if (view === 'dashboard') {
    await renderDashboard();
  } else if (view === 'processing') {
    await renderProcessing();
  } else if (view === 'scenarios') {
    await renderScenarios();
  } else if (view === 'orchestrationGraph') {
    await renderOrchestrationGraph();
  } else if (view === 'scenarioSlots') {
    await renderScenarioSlots();
  } else if (view === 'slotAutofill') {
    await renderSlotAutofillProfiles();
  } else if (view === 'scenarioClassification') {
    await renderScenarioClassification();
  } else if (view === 'scenarioReact') {
    await renderScenarioReact();
  } else if (view === 'scenarioTools') {
    await renderScenarioTools();
  } else if (view === 'scenarioEscalation') {
    await renderScenarioEscalation();
  } else if (view === 'scenarioPrompts') {
    await renderScenarioPrompts();
  } else if (view === 'interactionChannels') {
    await renderInteractionChannels();
  } else if (view === 'resolution') {
    await renderResolutionProfiles();
  } else if (view === 'knowledge') {
    await renderKnowledge();
  } else if (view === 'integrations' || view === 'tools') {
    await renderIntegrations();
  } else if (view === 'reactCalls') {
    await renderReactCalls();
  } else if (view === 'operationBindings') {
    await renderOperationBindings();
  } else if (view === 'workflow') {
    await renderWorkflow();
  } else if (view === 'models') {
    await renderModels();
  } else if (view === 'quality') {
    await renderQuality();
  } else if (view === 'audit') {
    await renderAudit();
  } else if (view === 'security') {
    await renderSecurity();
  }
}

async function renderScenarios() {
  const context = await loadScenarioContext();
  const scenarioEditor = renderScenarioEditor({
    detail: context.detail,
    serviceScenarios: context.serviceScenarios,
    slotSchemas: context.slotSchemas,
    routes: context.routes,
    policies: context.policies,
    toolMatrices: context.toolMatrices,
    promptPacks: context.promptPacks,
    escalationPolicies: context.escalationPolicies,
    interactionChannels: context.interactionChannels,
  });
  elements.viewContent.innerHTML = [
    section(
      'Сценарий обработки',
      `${scenarioToolbar(context)}
      <div class="scenario-menu">
        <button type="button" class="${state.scenarioOperation === 'create' ? 'primary' : ''}" data-action="scenario-operation" data-operation="create">Создать</button>
        <button type="button" class="${state.scenarioOperation === 'modify' ? 'primary' : ''}" data-action="scenario-operation" data-operation="modify">Модифицировать</button>
        <button type="button" class="${state.scenarioOperation === 'delete' ? 'primary' : ''}" data-action="scenario-operation" data-operation="delete">Удалить</button>
      </div>
      ${scenarioEditor}`,
    ),
  ].join('');
  attachScenarioSelect();
}

async function renderOrchestrationGraph() {
  const context = await loadOrchestrationGraphContext();
  elements.viewContent.innerHTML = [
    section(
      'Граф оркестрации',
      renderOrchestrationGraphPanel(context),
    ),
  ].join('');
  attachDashboardGraphInteractions(context.graph);
}

async function loadOrchestrationGraphContext() {
  const overview = await api('/admin/scenarios');
  const scenarios = overview.scenarios || [];
  if (!scenarios.some((scenario) => scenario.scenario_id === state.orchestrationGraphScenarioId)) {
    state.orchestrationGraphScenarioId = state.scenarioId || scenarios[0]?.scenario_id || '';
  }
  const params = new URLSearchParams({
    view: state.orchestrationGraphView,
  });
  if (state.orchestrationGraphView === 'scenario' && state.orchestrationGraphScenarioId) {
    params.set('scenario_id', state.orchestrationGraphScenarioId);
  }
  const graph = await api(`/admin/orchestration-graph?${params.toString()}`);
  state.lastData.orchestrationGraph = graph;
  const selectedNode = selectedGraphNode(graph);
  if (selectedNode) {
    state.orchestrationGraphSelectedNodeId = selectedNode.id;
  }
  return { scenarios, graph, selectedNode };
}

function renderOrchestrationGraphPanel({ scenarios = [], graph = {}, selectedNode = null } = {}) {
  if (!graph.nodes?.length) {
    return `${orchestrationGraphToolbar(scenarios)}
      ${renderGraphWarnings(graph)}
      <div class="empty">Граф оркестрации пока недоступен.</div>`;
  }
  return `${orchestrationGraphToolbar(scenarios)}
    ${renderGraphWarnings(graph)}
    <div class="graph-workspace">
      <div class="graph-board panel">
        ${renderGraphControls()}
        <div class="graph-canvas" data-graph-canvas>
          ${renderGraphSvg(graph)}
        </div>
      </div>
      ${renderGraphNodeDetails(graph, selectedNode)}
    </div>`;
}

function attachDashboardGraphInteractions(graph) {
  if (!graph?.nodes?.length) {
    return;
  }
  attachOrchestrationGraphInteractions();
  updateGraphViewport();
}

async function renderCurrentGraphHost() {
  if (state.activeView === 'dashboard') {
    await renderDashboard();
  } else if (state.activeView === 'processing') {
    await renderProcessing();
  } else {
    await renderOrchestrationGraph();
  }
}

function orchestrationGraphToolbar(scenarios) {
  const scenarioOptions = (scenarios || [])
    .map(
      (scenario) => `<option value="${escapeHtml(scenario.scenario_id)}" ${
        scenario.scenario_id === state.orchestrationGraphScenarioId ? 'selected' : ''
      }>${escapeHtml(scenario.display_name || scenario.scenario_id)}</option>`,
    )
    .join('');
  return `
    <div class="toolbar compact graph-toolbar">
      <label>Режим
        <select data-graph-view-select>
          <option value="scenario" ${state.orchestrationGraphView === 'scenario' ? 'selected' : ''}>Граф сценария</option>
          <option value="base" ${state.orchestrationGraphView === 'base' ? 'selected' : ''}>Базовый граф</option>
        </select>
      </label>
      <label>Сценарий
        <select data-graph-scenario-select ${state.orchestrationGraphView === 'base' ? 'disabled' : ''}>${scenarioOptions}</select>
      </label>
      <button type="button" data-action="orchestration-graph-load">Обновить</button>
    </div>
  `;
}

function renderGraphWarnings(graph) {
  const warnings = graph.warnings || [];
  if (!warnings.length) {
    return '';
  }
  return `
    <div class="empty">
      <strong>Предупреждения конфигурации</strong>
      <ul class="usage-list">${warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join('')}</ul>
    </div>
  `;
}

function renderGraphControls() {
  return `
    <div class="graph-controls" aria-label="Масштаб графа">
      <button type="button" data-action="graph-zoom-out" title="Уменьшить">-</button>
      <button type="button" data-action="graph-zoom-in" title="Увеличить">+</button>
      <button type="button" data-action="graph-zoom-reset">100%</button>
      <button type="button" data-action="graph-zoom-fit">Вписать</button>
      <span class="meta" data-graph-zoom-label>${Math.round(state.orchestrationGraphZoom * 100)}%</span>
    </div>
  `;
}

function selectedGraphNode(graph) {
  const nodes = graph.nodes || [];
  return nodes.find((node) => node.id === state.orchestrationGraphSelectedNodeId)
    || nodes.find((node) => node.id === 'slot_filling')
    || nodes[0]
    || null;
}

function graphNodeById(graph) {
  return Object.fromEntries((graph.nodes || []).map((node) => [node.id, node]));
}

function graphTextLines(text, maxChars = 21, maxLines = 3) {
  const words = String(text || '').split(/\s+/).filter(Boolean);
  const lines = [];
  let current = '';
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length > maxChars && current) {
      lines.push(current);
      current = word;
    } else {
      current = candidate;
    }
    if (lines.length === maxLines - 1) {
      break;
    }
  }
  if (current) {
    const usedWords = lines.join(' ').split(/\s+/).filter(Boolean).length + current.split(/\s+/).filter(Boolean).length;
    const suffix = usedWords < words.length ? '...' : '';
    lines.push(`${current}${suffix}`);
  }
  return lines.slice(0, maxLines);
}

function graphNodeStatusClass(status) {
  return String(status || 'unknown').replace(/[^a-zа-яё0-9_-]/gi, '_').toLowerCase();
}

function renderGraphSvg(graph) {
  const layout = graph.layout || {};
  const width = layout.width || 1760;
  const height = layout.height || 520;
  const nodeWidth = layout.node_width || 180;
  const nodeHeight = layout.node_height || 82;
  const nodesById = graphNodeById(graph);
  return `
    <svg class="orchestration-svg" data-graph-svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(graph.title || 'Граф оркестрации')}">
      <defs>
        <marker id="graph-arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L0,6 L9,3 z"></path>
        </marker>
      </defs>
      <g data-graph-stage>
        ${(graph.edges || []).map((edge) => renderGraphEdge(edge, nodesById, nodeWidth, nodeHeight)).join('')}
        ${(graph.nodes || []).map((node) => renderGraphNode(node, nodeWidth, nodeHeight)).join('')}
      </g>
    </svg>
  `;
}

function renderGraphEdge(edge, nodesById, nodeWidth, nodeHeight) {
  const source = nodesById[edge.from];
  const target = nodesById[edge.to];
  if (!source || !target) {
    return '';
  }
  const sourceLayout = source.layout || {};
  const targetLayout = target.layout || {};
  const sx = Number(sourceLayout.x || 0) + nodeWidth;
  const sy = Number(sourceLayout.y || 0) + nodeHeight / 2;
  const tx = Number(targetLayout.x || 0);
  const ty = Number(targetLayout.y || 0) + nodeHeight / 2;
  const delta = Math.max(70, Math.abs(tx - sx) / 2);
  const path = `M ${sx} ${sy} C ${sx + delta} ${sy}, ${tx - delta} ${ty}, ${tx} ${ty}`;
  const labelX = (sx + tx) / 2;
  const labelY = (sy + ty) / 2 - 8;
  const className = `graph-edge ${escapeHtml(edge.type || 'flow')}`;
  const label = [edge.label, edge.condition].filter(Boolean).join(' / ');
  return `
    <g class="${className}">
      <path d="${path}" marker-end="url(#graph-arrow)"></path>
      ${label ? `<text x="${labelX}" y="${labelY}">${escapeHtml(label)}</text>` : ''}
    </g>
  `;
}

function renderGraphNode(node, nodeWidth, nodeHeight) {
  const layout = node.layout || {};
  const selected = node.id === state.orchestrationGraphSelectedNodeId;
  const titleLines = graphTextLines(node.title, 22, 2);
  const statusLabel = visibleLabels[graphNodeStatusClass(node.status)] || node.status || 'н/д';
  return `
    <g class="graph-node ${escapeHtml(graphNodeStatusClass(node.status))} ${selected ? 'selected' : ''}" data-action="graph-node-select" data-node-id="${escapeHtml(node.id)}" transform="translate(${Number(layout.x || 0)} ${Number(layout.y || 0)})" role="button" tabindex="0">
      <title>${escapeHtml(node.title)}</title>
      <rect width="${nodeWidth}" height="${nodeHeight}" rx="8"></rect>
      <text class="graph-node-step" x="12" y="20">${escapeHtml(node.step_number === null || node.step_number === undefined ? node.type : `${node.step_number}`)}</text>
      <circle class="graph-node-status" cx="${nodeWidth - 15}" cy="15" r="5"></circle>
      <text class="graph-node-title" x="12" y="42">
        ${titleLines.map((line, index) => `<tspan x="12" dy="${index ? 17 : 0}">${escapeHtml(line)}</tspan>`).join('')}
      </text>
      <text class="graph-node-meta" x="12" y="${nodeHeight - 10}">${escapeHtml(statusLabel)}</text>
    </g>
  `;
}

function renderGraphNodeDetails(graph, node) {
  if (!node) {
    return '<aside class="graph-details panel"><div class="empty">Узел не выбран</div></aside>';
  }
  const refs = node.config_refs || [];
  const metrics = node.metrics || [];
  return `
    <aside class="graph-details panel">
      <div>
        <div class="metric-label">Выбранный узел</div>
        <h3>${escapeHtml(node.title)}</h3>
        <div>${badge(node.status)} ${badge(node.readonly ? 'read_only' : 'active')}</div>
      </div>
      <div class="meta">${escapeHtml(node.description || 'Описание не задано.')}</div>
      ${metrics.length ? `
        <div class="grid two graph-metrics">
          ${metrics.map((item) => metric(item.label, escapeHtml(item.value))).join('')}
        </div>
      ` : ''}
      <div>
        <div class="metric-label">Связанные настройки</div>
        ${refs.length ? `
          <ul class="usage-list graph-ref-list">
            ${refs.map((ref) => `
              <li>
                <strong>${escapeHtml(ref.title)}</strong>
                <span>${escapeHtml(ref.display_name || ref.id || 'н/д')}</span>
                <button type="button" data-action="graph-config-link" data-graph-view="${escapeHtml(ref.view || '')}" data-graph-domain="${escapeHtml(ref.domain || '')}" data-graph-ref-id="${escapeHtml(ref.id || '')}">Открыть</button>
              </li>
            `).join('')}
          </ul>
        ` : '<div class="empty">Для узла нет отдельных настроек.</div>'}
      </div>
    </aside>
  `;
}

function updateGraphViewport() {
  const stage = document.querySelector('[data-graph-stage]');
  if (!stage) {
    return;
  }
  stage.setAttribute(
    'transform',
    `translate(${state.orchestrationGraphPanX} ${state.orchestrationGraphPanY}) scale(${state.orchestrationGraphZoom})`,
  );
  const label = document.querySelector('[data-graph-zoom-label]');
  if (label) {
    label.textContent = `${Math.round(state.orchestrationGraphZoom * 100)}%`;
  }
}

function setGraphZoom(nextZoom) {
  state.orchestrationGraphZoom = Math.min(2.4, Math.max(0.35, nextZoom));
  updateGraphViewport();
}

function fitGraphToCanvas() {
  const graph = state.lastData.orchestrationGraph || {};
  const canvas = document.querySelector('[data-graph-canvas]');
  const layout = graph.layout || {};
  if (!canvas || !layout.width || !layout.height) {
    setGraphZoom(0.78);
    return;
  }
  const rect = canvas.getBoundingClientRect();
  const zoom = Math.min(
    (rect.width - 28) / layout.width,
    (rect.height - 28) / layout.height,
  );
  state.orchestrationGraphZoom = Math.min(1, Math.max(0.35, zoom));
  state.orchestrationGraphPanX = Math.max(12, (rect.width - layout.width * state.orchestrationGraphZoom) / 2);
  state.orchestrationGraphPanY = Math.max(12, (rect.height - layout.height * state.orchestrationGraphZoom) / 2);
  updateGraphViewport();
}

function applyGraphConfigRefSelection(domain, refId) {
  if (!domain || !refId) {
    return;
  }
  if (domain === 'service_scenarios') {
    state.scenarioId = state.orchestrationGraphScenarioId;
  } else if (domain === 'slot_schemas') {
    state.slotSchemaId = refId;
    state.slotSchemaOperation = 'modify';
  } else if (domain === 'classification_routes') {
    state.routeId = refId;
    state.routeOperation = 'modify';
  } else if (domain === 'orchestrator_policy') {
    state.policyId = refId;
    state.policyOperation = 'modify';
  } else if (domain === 'tool_launch_matrix') {
    state.toolMatrixId = refId;
    state.toolMatrixOperation = 'modify';
  } else if (domain === 'prompt_packs') {
    state.promptPackId = refId;
    state.promptPackOperation = 'modify';
  } else if (domain === 'escalation_policies') {
    state.escalationPolicyId = refId;
    state.escalationOperation = 'modify';
  } else if (domain === 'interaction_channels') {
    state.interactionChannelId = refId;
    state.interactionChannelOperation = 'modify';
  } else if (domain === 'attribute_resolution_profiles') {
    state.resolutionProfileId = refId;
    state.resolutionOperation = 'modify';
  } else if (domain === 'tools') {
    state.toolCatalogName = refId;
    state.operationBindingToolName = refId;
    state.toolCatalogOperation = 'modify';
  } else if (domain === 'integration_endpoints') {
    state.integrationEndpointId = refId;
    state.integrationEndpointOperation = 'modify';
  }
}

function attachOrchestrationGraphInteractions() {
  const canvas = document.querySelector('[data-graph-canvas]');
  if (!canvas) {
    return;
  }
  let drag = null;
  canvas.addEventListener('pointerdown', (event) => {
    if (event.target.closest('[data-action="graph-node-select"]')) {
      return;
    }
    drag = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      panX: state.orchestrationGraphPanX,
      panY: state.orchestrationGraphPanY,
    };
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener('pointermove', (event) => {
    if (!drag || event.pointerId !== drag.pointerId) {
      return;
    }
    state.orchestrationGraphPanX = drag.panX + event.clientX - drag.startX;
    state.orchestrationGraphPanY = drag.panY + event.clientY - drag.startY;
    updateGraphViewport();
  });
  canvas.addEventListener('pointerup', () => {
    drag = null;
  });
  canvas.addEventListener('pointercancel', () => {
    drag = null;
  });
  canvas.addEventListener('wheel', (event) => {
    event.preventDefault();
    const factor = event.deltaY < 0 ? 1.08 : 0.92;
    setGraphZoom(state.orchestrationGraphZoom * factor);
  }, { passive: false });
}

async function loadScenarioContext() {
  const [
    overview,
    serviceScenariosConfig,
    slotSchemasConfig,
    routesConfig,
    policiesConfig,
    toolMatricesConfig,
    promptPacksConfig,
    escalationPoliciesConfig,
    interactionChannelsConfig,
    resolutionProfilesConfig,
  ] = await Promise.all([
    api('/admin/scenarios'),
    api('/admin/config/active/service_scenarios'),
    api('/admin/config/active/slot_schemas'),
    api('/admin/config/active/classification_routes'),
    api('/admin/config/active/orchestrator_policy'),
    api('/admin/config/active/tool_launch_matrix'),
    api('/admin/config/active/prompt_packs'),
    api('/admin/config/active/escalation_policies'),
    api('/admin/config/active/interaction_channels'),
    api('/admin/config/active/attribute_resolution_profiles'),
  ]);
  const scenarios = overview.scenarios || [];
  if (!scenarios.some((scenario) => scenario.scenario_id === state.scenarioId)) {
    state.scenarioId = scenarios[0]?.scenario_id || '';
  }
  const detail = state.scenarioId
    ? await api(`/admin/scenarios/${encodeURIComponent(state.scenarioId)}`)
    : null;
  state.lastData.resolutionProfiles = resolutionProfilesConfig.payload?.profiles || [];
  return {
    overview,
    scenarios,
    detail,
    serviceScenarios: serviceScenariosConfig.payload?.scenarios || [],
    slotSchemas: slotSchemasConfig.payload?.slot_schemas || [],
    routes: routesConfig.payload?.routes || [],
    policies: policiesConfig.payload?.policies || [],
    toolMatrices: toolMatricesConfig.payload?.matrices || [],
    promptPacks: promptPacksConfig.payload?.packs || [],
    escalationPolicies: escalationPoliciesConfig.payload?.policies || [],
    interactionChannels: interactionChannelsConfig.payload?.channels || [],
    resolutionProfiles: resolutionProfilesConfig.payload?.profiles || [],
  };
}

function scenarioToolbar(context) {
  const scenarioOptions = (context.scenarios || [])
    .map(
      (scenario) => `<option value="${escapeHtml(scenario.scenario_id)}" ${
        scenario.scenario_id === state.scenarioId ? 'selected' : ''
      }>${escapeHtml(scenario.display_name)}</option>`,
    )
    .join('');
  return `<div class="toolbar compact">
    <label>Сценарий<select id="scenarioSelect">${scenarioOptions}</select></label>
    <label>Готовность<input value="${escapeHtml(context.detail?.readiness?.status || 'н/д')}" readonly></label>
  </div>`;
}

function attachScenarioSelect() {
  document.getElementById('scenarioSelect')?.addEventListener('change', (event) => {
    state.scenarioId = event.target.value;
    renderView(state.activeView).catch((error) => setNotice(error.message || String(error), 'error'));
  });
}

function blockCatalogControls({ selectId, label, items, idKey, selectedId, labelKey, actionPrefix, operation }) {
  const options = referenceOptions(items, idKey, selectedId, labelKey);
  return `
    <div class="toolbar compact">
      <label>${escapeHtml(label)}<select id="${escapeHtml(selectId)}">${options}</select></label>
    </div>
    <div class="scenario-menu">
      <button type="button" class="${operation === 'create' ? 'primary' : ''}" data-action="${escapeHtml(actionPrefix)}-operation" data-operation="create">Создать</button>
      <button type="button" class="${operation === 'modify' ? 'primary' : ''}" data-action="${escapeHtml(actionPrefix)}-operation" data-operation="modify">Модифицировать</button>
      <button type="button" class="${operation === 'delete' ? 'primary' : ''}" data-action="${escapeHtml(actionPrefix)}-operation" data-operation="delete">Удалить</button>
    </div>
  `;
}

function attachCatalogSelect(selectId, stateKey, renderer) {
  document.getElementById(selectId)?.addEventListener('change', (event) => {
    state[stateKey] = event.target.value;
    renderer().catch((error) => setNotice(error.message || String(error), 'error'));
  });
}

function usedByScenarios(scenarios, referenceKey, referenceId) {
  return (scenarios || []).filter((scenario) => scenario[referenceKey] === referenceId);
}

function usagePanel(scenarios, referenceKey, referenceId) {
  const used = usedByScenarios(scenarios, referenceKey, referenceId);
  const names = used.map((scenario) => scenario.display_name || scenario.scenario_id);
  const text = names.length
    ? `Используется в сценариях: ${names.join(', ')}. Для удаления сначала измените или удалите эти сценарии.`
    : 'Не используется в сценариях. Блок можно удалить.';
  return `
    <div class="slot-schema-derived">
      <div class="metric-label">Где используется</div>
      <div class="meta">${escapeHtml(text)}</div>
    </div>
  `;
}

async function renderScenarioSlots() {
  const [active, scenariosConfig, resolutionProfilesConfig, policiesConfig] = await Promise.all([
    api('/admin/config/active/slot_schemas'),
    api('/admin/config/active/service_scenarios'),
    api('/admin/config/active/attribute_resolution_profiles'),
    api('/admin/config/active/orchestrator_policy'),
  ]);
  const slotSchemas = active.payload?.slot_schemas || [];
  const scenarios = scenariosConfig.payload?.scenarios || [];
  const resolutionProfiles = resolutionProfilesConfig.payload?.profiles || [];
  const confidenceDefaults = policiesConfig.payload?.confidence_defaults || {};
  state.lastData.resolutionProfiles = resolutionProfiles;
  state.lastData.confidenceDefaults = confidenceDefaults;
  if (!slotSchemas.some((slotSchema) => slotSchema.slot_schema_id === state.slotSchemaId)) {
    state.slotSchemaId = slotSchemas[0]?.slot_schema_id || '';
  }
  const selected = slotSchemas.find((slotSchema) => slotSchema.slot_schema_id === state.slotSchemaId) || null;
  elements.viewContent.innerHTML = [
    section(
      '0. Слоты',
      `${blockCatalogControls({
        selectId: 'slotSchemaSelect',
        label: 'Схема слотов',
        items: slotSchemas,
        idKey: 'slot_schema_id',
        selectedId: state.slotSchemaId,
        labelKey: 'display_name',
        actionPrefix: 'slot-schema',
        operation: state.slotSchemaOperation,
      })}
      ${renderSlotSchemaEditor({
        slotSchema: selected,
        slotSchemas,
        scenarios,
        resolutionProfiles,
        confidenceDefaults,
      })}`,
    ),
  ].join('');
  attachCatalogSelect('slotSchemaSelect', 'slotSchemaId', renderScenarioSlots);
  syncAllSlotCardFillMethods();
}

async function renderSlotAutofillProfiles() {
  const [active, slotSchemasConfig, scenariosConfig, toolsConfig] = await Promise.all([
    api('/admin/config/active/slot_autofill_profiles'),
    api('/admin/config/active/slot_schemas'),
    api('/admin/config/active/service_scenarios'),
    api('/admin/config/active/tools'),
  ]);
  const profiles = active.payload?.profiles || [];
  const slotSchemas = slotSchemasConfig.payload?.slot_schemas || [];
  const scenarios = scenariosConfig.payload?.scenarios || [];
  const tools = (toolsConfig.payload?.tools || []).filter((tool) => tool.action_type === 'read_only');
  state.lastData.slotAutofillProfiles = profiles;
  state.lastData.slotSchemas = slotSchemas;
  state.lastData.serviceScenarios = scenarios;
  state.lastData.toolCatalog = toolsConfig.payload?.tools || [];
  if (!profiles.some((profile) => profile.profile_id === state.slotAutofillProfileId)) {
    state.slotAutofillProfileId = profiles[0]?.profile_id || '';
  }
  const selected = profiles.find((profile) => profile.profile_id === state.slotAutofillProfileId) || null;
  elements.viewContent.innerHTML = [
    section(
      '0.1 Автозаполнение слотов',
      `${slotAutofillHowToPanel()}
      ${blockCatalogControls({
        selectId: 'slotAutofillProfileSelect',
        label: 'Профиль автозаполнения',
        items: profiles,
        idKey: 'profile_id',
        selectedId: state.slotAutofillProfileId,
        labelKey: 'display_name',
        actionPrefix: 'slot-autofill',
        operation: state.slotAutofillOperation,
      })}
      ${renderSlotAutofillEditor({ profile: selected, profiles, slotSchemas, scenarios, tools })}`,
    ),
  ].join('');
  attachCatalogSelect('slotAutofillProfileSelect', 'slotAutofillProfileId', renderSlotAutofillProfiles);
  syncAllSlotAutofillOutputRows();
  syncAllSlotAutofillSourceRows();
}

function slotAutofillHowToPanel() {
  return `
    <div class="slot-schema-derived">
      <div class="metric-label">Зачем нужен профиль</div>
      <div class="meta">
        Профиль запускает один read-only ReAct-вызов и детерминированно раскладывает поля результата в слоты выбранной схемы.
        Если нужного слота еще нет, выберите действие "создать новый слот": UI добавит слот в схему перед сохранением профиля.
      </div>
    </div>
  `;
}

function slotAutofillCreateTemplate(source, profiles, slotSchemas, tools) {
  const template = source || profiles[0] || {};
  const schemaId = template.slot_schema_id || state.slotSchemaId || slotSchemas[0]?.slot_schema_id || '';
  const tool = findToolInCatalog(tools, template.react_call) || tools[0] || null;
  return {
    profile_id: nextConfigItemId(template.profile_id || 'autofill.custom.profile', profiles, 'profile_id'),
    display_name: '',
    status: 'active',
    description: '',
    slot_schema_id: schemaId,
    enabled: true,
    react_call: tool?.tool_name || '',
    run_order: (profiles || []).length + 1,
    accept_policy: 'single_result',
    input_mapping: {},
    output_mapping: [],
    on_no_result: 'continue',
    on_ambiguous_result: 'ask_client',
    configuration_instruction: template.configuration_instruction || '',
    generated_structure_metadata: template.generated_structure_metadata || {},
  };
}

function renderSlotAutofillEditor({ profile, profiles, slotSchemas, scenarios, tools }) {
  if (state.slotAutofillOperation === 'delete') {
    if (!profile) {
      return '<div class="empty">Нет выбранного профиля для удаления</div>';
    }
    return `
      <form class="scenario-editor panel" data-form="slot-autofill-delete">
        <div>
          <div class="metric-label">Удаляемый профиль автозаполнения</div>
          <div class="scenario-title">${escapeHtml(profile.display_name || profile.profile_id)}</div>
        </div>
        ${slotAutofillUsagePanel(profile, slotSchemas, scenarios)}
        <button class="danger" type="submit">Удалить профиль автозаполнения</button>
      </form>
    `;
  }
  const current = state.slotAutofillOperation === 'create'
    ? slotAutofillCreateTemplate(profile, profiles, slotSchemas, tools)
    : profile;
  if (!current) {
    return '<div class="empty">Профиль автозаполнения не выбран</div>';
  }
  const slotSchema = (slotSchemas || []).find((schema) => schema.slot_schema_id === current.slot_schema_id)
    || slotSchemas[0]
    || { slots: [] };
  const tool = findToolInCatalog(tools, current.react_call) || tools[0] || null;
  return `
    <form class="scenario-editor panel" data-form="slot-autofill-editor">
      <input type="hidden" name="profile_id" value="${escapeHtml(current.profile_id || '')}">
      <input type="hidden" name="generated_structure_metadata" value="${escapeHtml(jsonPretty(current.generated_structure_metadata || {}))}">
      <div class="grid two">
        <label>Название
          <input name="display_name" value="${escapeHtml(current.display_name || '')}" autocomplete="off" placeholder="Поиск пользователя в AD">
        </label>
        <label>Схема слотов
          <select name="slot_schema_id" data-slot-autofill-schema>${referenceOptions(slotSchemas, 'slot_schema_id', slotSchema.slot_schema_id, 'display_name')}</select>
          <span class="field-help">Слоты для маппинга и создаваемые слоты относятся только к выбранной схеме.</span>
        </label>
      </div>
      <fieldset class="launch-editor">
        <legend>Инструкция настройки</legend>
        <label>Что должен сделать профиль
          <textarea name="configuration_instruction" data-slot-autofill-instruction rows="5" placeholder="Вызови get_user_login. В параметр user_fio передай слот &quot;Фамилия Имя Отчество&quot;. Если результат единственный, заполни слот &quot;Логин пользователя&quot; из поля user_login.">${escapeHtml(current.configuration_instruction || '')}</textarea>
          <span class="field-help">Укажите ReAct-вызов, правило принятия результата и действия для случаев "нет результата" / "несколько результатов". Runtime исполняет сформированную структуру ниже.</span>
        </label>
        ${slotAutofillStructurePreview(current)}
        <div class="scenario-editor-actions">
          <button type="button" data-action="slot-autofill-compile">Сформировать структуру</button>
          <span class="meta" data-slot-autofill-compile-status>Результат применится к ReAct-вызову, входным параметрам и выходным слотам формы.</span>
        </div>
      </fieldset>
      <details class="launch-editor">
        <summary>Расширенные настройки структуры</summary>
        <label>Описание
          <textarea name="description" rows="3">${escapeHtml(current.description || '')}</textarea>
        </label>
        <fieldset class="launch-editor">
          <legend>Параметры запуска профиля</legend>
          <div class="grid two">
            <label>ReAct-вызов чтения
              <select name="react_call" data-slot-autofill-react-call>${slotAutofillToolOptions(tools, current.react_call)}</select>
              <span class="field-help">Для автозаполнения доступны только read-only вызовы. Привязка к endpoint берется из меню "Вызовы и интеграции".</span>
            </label>
            <label>Порядок запуска
              <input name="run_order" type="number" min="1" max="100" value="${escapeHtml(current.run_order || 1)}">
            </label>
            <label>Когда принимать результат
              <select name="accept_policy">${optionList(['single_result', 'always'], current.accept_policy || 'single_result', slotAutofillPolicyLabels())}</select>
            </label>
            <label>Если нет результата
              <select name="on_no_result">${optionList(['continue', 'ask_client', 'operator_handoff'], current.on_no_result || 'continue', slotAutofillFailureLabels())}</select>
            </label>
            <label>Если несколько результатов
              <select name="on_ambiguous_result">${optionList(['continue', 'ask_client', 'operator_handoff'], current.on_ambiguous_result || 'ask_client', slotAutofillFailureLabels())}</select>
            </label>
          </div>
        </fieldset>
        <fieldset class="launch-editor">
          <legend>Входные параметры ReAct-вызова</legend>
          <div class="meta">Параметры берутся из контракта ReAct-вызова. Источником может быть слот схемы, поле обращения, контекст, константа или секрет.</div>
          <div class="parameter-binding-list" data-slot-autofill-input-list>
            ${renderSlotAutofillInputRows(current, tool, slotSchema)}
          </div>
        </fieldset>
        <fieldset class="launch-editor">
          <legend>Поля результата и слоты</legend>
          <div class="meta">Для каждого поля результата выберите: не использовать, заполнить существующий слот или создать новый слот из этого поля.</div>
          <datalist id="slotAutofillResultFields">${slotAutofillResultFieldDatalist(tool)}</datalist>
          <div class="parameter-binding-list" data-slot-autofill-output-list>
            ${renderSlotAutofillOutputRows(current, tool, slotSchema)}
          </div>
          <button type="button" data-action="slot-autofill-output-add">Добавить поле результата</button>
        </fieldset>
      </details>
      ${slotAutofillUsagePanel(current, slotSchemas, scenarios)}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">${state.slotAutofillOperation === 'create' ? 'Создать профиль' : 'Сохранить профиль'}</button>
      </div>
    </form>
  `;
}

function slotAutofillPolicyLabels() {
  return {
    single_result: 'если результат единственный',
    always: 'всегда брать значения',
  };
}

function slotAutofillFailureLabels() {
  return {
    continue: 'продолжить сценарий',
    ask_client: 'задать вопрос клиенту',
    operator_handoff: 'эскалировать оператору',
  };
}

function slotAutofillStructurePreview(profile = {}) {
  const inputItems = Object.entries(profile.input_mapping || {})
    .map(([parameter, source]) => `${parameter} <- ${source}`);
  const outputItems = (profile.output_mapping || [])
    .map((item) => `${item.target_slot} <- ${item.result_field}${item.required_for_success ? ' (обязательно)' : ''}`);
  return `
    <div class="slot-schema-derived">
      <div class="metric-label">Сформированная структура</div>
      <div class="meta">
        ReAct-вызов: ${escapeHtml(profile.react_call || 'не выбран')}.
        Входы: ${escapeHtml(formatList(inputItems))}.
        Выходы: ${escapeHtml(formatList(outputItems))}.
        Нет результата: ${escapeHtml(slotAutofillFailureLabels()[profile.on_no_result] || profile.on_no_result || 'не задано')}.
        Несколько результатов: ${escapeHtml(slotAutofillFailureLabels()[profile.on_ambiguous_result] || profile.on_ambiguous_result || 'не задано')}.
      </div>
    </div>
  `;
}

function slotAutofillToolOptions(tools, selectedToolName) {
  return selectOptions(
    (tools || []).map((tool) => ({
      value: tool.tool_name,
      label: tool.description ? `${tool.tool_name} — ${tool.description}` : tool.tool_name,
    })),
    selectedToolName,
    'нет read-only ReAct-вызовов',
  );
}

function slotAutofillUsagePanel(profile, slotSchemas, scenarios) {
  const schema = (slotSchemas || []).find((item) => item.slot_schema_id === profile?.slot_schema_id);
  const scenarioNames = (scenarios || [])
    .filter((scenario) => scenario.slot_schema_id === profile?.slot_schema_id)
    .map((scenario) => scenario.display_name || scenario.scenario_id);
  const targets = (profile?.output_mapping || []).map((item) => item.target_slot);
  return `
    <div class="slot-schema-derived">
      <div class="metric-label">Где используется</div>
      <div class="meta">
        Схема слотов: ${escapeHtml(schema?.display_name || profile?.slot_schema_id || 'не выбрана')}.
        Сценарии: ${escapeHtml(scenarioNames.join(', ') || 'нет')}.
        Целевые слоты: ${escapeHtml(formatList(targets))}.
      </div>
    </div>
  `;
}

function renderSlotAutofillInputRows(profile, tool, slotSchema) {
  const parameters = reactParameterNames(tool || {});
  if (!parameters.length) {
    return '<div class="empty">У выбранного ReAct-вызова нет входных параметров.</div>';
  }
  const required = new Set(schemaRequired(tool?.parameters_schema || {}));
  return `
    <div class="parameter-binding-header">
      <span>Параметр вызова</span>
      <span>Заполняется из</span>
    </div>
    ${parameters.map((parameter) => renderSlotAutofillInputRow(
      parameter,
      profile.input_mapping?.[parameter] || defaultSlotAutofillInputSource(parameter, slotSchema),
      required.has(parameter),
      slotSchema,
    )).join('')}
  `;
}

function renderSlotAutofillInputRow(parameter, sourceRef, required, slotSchema) {
  const parsed = parseAutofillSourceRef(sourceRef);
  return `
    <div class="parameter-binding-row" data-slot-autofill-input-row>
      <label>${escapeHtml(parameter)}
        <span class="field-help">${required ? 'обязательный параметр' : 'необязательный параметр'}</span>
      </label>
      <label>Источник
        <select data-slot-autofill-param-source-mode>${slotAutofillSourceModeOptions(slotSchema, parsed.mode)}</select>
        <input data-slot-autofill-param-source-custom value="${escapeHtml(parsed.custom)}" autocomplete="off" placeholder="значение или путь">
      </label>
      <input type="hidden" data-slot-autofill-param-name value="${escapeHtml(parameter)}">
    </div>
  `;
}

function parseAutofillSourceRef(sourceRef) {
  const source = String(sourceRef || '');
  if (source.startsWith('slot:')) return { mode: source, custom: '' };
  for (const prefix of ['case:', 'context:', 'constant:', 'secret:']) {
    if (source.startsWith(prefix)) {
      return { mode: prefix, custom: source.slice(prefix.length) };
    }
  }
  return { mode: '', custom: '' };
}

function slotAutofillSourceModeOptions(slotSchema, selected) {
  const slotOptions = (slotSchema?.slots || []).map((slot) => ({
    value: `slot:${slot.slot_id}`,
    label: `Слот: ${slot.display_name || slot.slot_id} (${slot.slot_id})`,
  }));
  return selectOptions(
    [
      { value: '__none__', label: 'не задано' },
      ...slotOptions,
      { value: 'case:', label: 'Поле обращения' },
      { value: 'context:', label: 'Контекст выполнения' },
      { value: 'constant:', label: 'Константа' },
      { value: 'secret:', label: 'Секрет' },
    ],
    selected || '__none__',
    'не задано',
  );
}

function defaultSlotAutofillInputSource(parameter, slotSchema) {
  const slotIds = new Set((slotSchema?.slots || []).map((slot) => slot.slot_id));
  if (slotIds.has(parameter)) return `slot:${parameter}`;
  if (parameter === 'login' && slotIds.has('user_login')) return 'slot:user_login';
  if (parameter === 'query' && slotIds.has('symptom')) return 'slot:symptom';
  return '';
}

function slotAutofillResultFieldDatalist(tool) {
  return resultFieldsFromTool(tool)
    .map((field) => `<option value="${escapeHtml(field.field_id)}">${escapeHtml(field.display_name || field.field_id)}</option>`)
    .join('');
}

function renderSlotAutofillOutputRows(profile, tool, slotSchema) {
  const mappings = profile.output_mapping?.length
    ? profile.output_mapping
    : resultFieldsFromTool(tool).map((field) => ({ result_field: field.field_id, target_slot: '', required_for_success: false }));
  return mappings.map((mapping) => renderSlotAutofillOutputRow(mapping, slotSchema)).join('');
}

function renderSlotAutofillOutputRow(mapping = {}, slotSchema = { slots: [] }) {
  const targetExists = (slotSchema.slots || []).some((slot) => slot.slot_id === mapping.target_slot);
  const action = mapping.target_slot ? (targetExists ? 'existing' : 'new') : 'ignore';
  const existingHidden = action !== 'existing' ? ' hidden' : '';
  const existingDisabled = action !== 'existing' ? ' disabled' : '';
  const newHidden = action !== 'new' ? ' hidden' : '';
  const newDisabled = action !== 'new' ? ' disabled' : '';
  const requiredHidden = action === 'ignore' ? ' hidden' : '';
  const requiredDisabled = action === 'ignore' ? ' disabled' : '';
  const existingOptions = selectOptions(
    (slotSchema.slots || []).map((slot) => ({
      value: slot.slot_id,
      label: `${slot.display_name || slot.slot_id} (${slot.slot_id})`,
    })),
    targetExists ? mapping.target_slot : '',
    'нет слотов',
  );
  return `
    <div class="parameter-binding-row slot-autofill-output-row" data-slot-autofill-output-row data-output-action="${escapeHtml(action)}">
      <div class="slot-autofill-output-fields">
        <label>Поле результата
          <input data-slot-autofill-result-field list="slotAutofillResultFields" value="${escapeHtml(mapping.result_field || '')}" autocomplete="off" placeholder="users.0.login">
          <span class="field-help">Можно выбрать поле из контракта или указать путь, например users.0.login.</span>
        </label>
        <label>Действие
          <select data-slot-autofill-output-action>
            <option value="ignore" ${action === 'ignore' ? 'selected' : ''}>не использовать</option>
            <option value="existing" ${action === 'existing' ? 'selected' : ''}>заполнить существующий слот</option>
            <option value="new" ${action === 'new' ? 'selected' : ''}>создать новый слот</option>
          </select>
        </label>
        <label data-slot-autofill-existing-slot${existingHidden}>Существующий слот
          <select data-slot-autofill-target-slot${existingDisabled}>${existingOptions}</select>
        </label>
        <label data-slot-autofill-new-slot-id${newHidden}>Ключ нового слота
          <input data-slot-autofill-new-slot-key value="${escapeHtml(targetExists ? '' : mapping.target_slot || '')}" autocomplete="off" placeholder="manager_email"${newDisabled}>
        </label>
        <label data-slot-autofill-new-slot-name${newHidden}>Название нового слота
          <input data-slot-autofill-new-slot-display value="${escapeHtml(humanizeTechnicalKey(mapping.target_slot || mapping.result_field || ''))}" autocomplete="off" placeholder="Email руководителя"${newDisabled}>
        </label>
        <label data-slot-autofill-new-slot-priority${newHidden}>Priority group
          <select data-slot-autofill-new-slot-priority-value${newDisabled}>${slotPriorityOptions('context')}</select>
        </label>
        <label class="boolean-flag" data-slot-autofill-new-slot-required${newHidden}>
          <span>Слот обязательный в схеме</span>
          <input data-slot-autofill-new-slot-required-value type="checkbox" value="true" ${mapping.required_for_success === true ? 'checked' : ''}${newDisabled}>
        </label>
        <label class="boolean-flag" data-slot-autofill-required-field${requiredHidden}>
          <span>Поле результата обязательно для профиля</span>
          <input data-slot-autofill-required type="checkbox" value="true" ${mapping.required_for_success === true ? 'checked' : ''}${requiredDisabled}>
          <span class="field-help">Даже если поле не обязательно в общем контракте ReAct-вызова, этот профиль будет считаться неуспешным, если значение не вернулось.</span>
        </label>
      </div>
      <button class="danger" type="button" data-action="slot-autofill-output-remove">Удалить</button>
    </div>
  `;
}

async function renderScenarioClassification() {
  const [active, scenariosConfig] = await Promise.all([
    api('/admin/config/active/classification_routes'),
    api('/admin/config/active/service_scenarios'),
  ]);
  const routes = active.payload?.routes || [];
  const scenarios = scenariosConfig.payload?.scenarios || [];
  if (!routes.some((route) => route.route_id === state.routeId)) {
    state.routeId = routes[0]?.route_id || '';
  }
  const selected = routes.find((route) => route.route_id === state.routeId) || null;
  elements.viewContent.innerHTML = [
    section(
      '2. Классификация и маршрут',
      `${blockCatalogControls({
        selectId: 'routeSelect',
        label: 'Маршрут',
        items: routes,
        idKey: 'route_id',
        selectedId: state.routeId,
        labelKey: 'display_name',
        actionPrefix: 'route',
        operation: state.routeOperation,
      })}
      ${renderRouteEditor({ route: selected, routes, scenarios })}`,
    ),
  ].join('');
  attachCatalogSelect('routeSelect', 'routeId', renderScenarioClassification);
}

async function renderScenarioReact() {
  const [active, scenariosConfig] = await Promise.all([
    api('/admin/config/active/orchestrator_policy'),
    api('/admin/config/active/service_scenarios'),
  ]);
  const policies = active.payload?.policies || [];
  const scenarios = scenariosConfig.payload?.scenarios || [];
  if (!policies.some((policy) => policy.policy_id === state.policyId)) {
    state.policyId = policies[0]?.policy_id || '';
  }
  const selected = policies.find((policy) => policy.policy_id === state.policyId) || null;
  elements.viewContent.innerHTML = [
    section(
      '3. ReAct-планирование',
      `${blockCatalogControls({
        selectId: 'policySelect',
        label: 'Политика',
        items: policies,
        idKey: 'policy_id',
        selectedId: state.policyId,
        labelKey: 'display_name',
        actionPrefix: 'policy',
        operation: state.policyOperation,
      })}
      ${renderPolicyEditor({ policy: selected, policies, scenarios })}`,
    ),
  ].join('');
  attachCatalogSelect('policySelect', 'policyId', renderScenarioReact);
}

function renderSystemConfidenceDefaults(confidenceDefaults, { collapsed = false } = {}) {
  const summary = systemConfidenceSummary(confidenceDefaults);
  const form = `
    <form class="scenario-editor ${collapsed ? '' : 'panel'}" data-form="confidence-defaults-editor">
      <div>
        <div class="metric-label">Системные пороги уверенности</div>
        <div class="meta">Базовые значения для slot filling, извлечения моделью и принятия результатов. Слоты и профили могут переопределять их только в исключительных случаях.</div>
      </div>
      ${renderConfidenceThresholdInputs('system_confidence', confidenceDefaults, { required: true })}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">Сохранить системные пороги</button>
      </div>
    </form>
  `;
  if (!collapsed) {
    return form;
  }
  return `
    <details class="launch-editor">
      <summary>${escapeHtml(summary)}</summary>
      <div class="meta">Глобальные значения для LLM-извлечения и slot filling. Слот может переопределить их только при способе "Извлечение моделью".</div>
      ${form}
    </details>
  `;
}

function confidenceValueLabel(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(2) : 'н/д';
}

function systemConfidenceSummary(thresholds = {}) {
  return [
    `Пороги уверенности: автопринятие ${confidenceValueLabel(thresholds.auto_accept_confidence)}`,
    `уточнение ${confidenceValueLabel(thresholds.clarification_confidence)}`,
    `оператор ${confidenceValueLabel(thresholds.operator_handoff_confidence)}`,
    `извлечение ${confidenceValueLabel(thresholds.min_extraction_confidence)}`,
  ].join(' · ');
}

async function renderScenarioTools() {
  const [active, scenariosConfig, slotSchemasConfig, toolsConfig, endpointsConfig] = await Promise.all([
    api('/admin/config/active/tool_launch_matrix'),
    api('/admin/config/active/service_scenarios'),
    api('/admin/config/active/slot_schemas'),
    api('/admin/config/active/tools'),
    api('/admin/config/active/integration_endpoints'),
  ]);
  const matrices = active.payload?.matrices || [];
  const scenarios = scenariosConfig.payload?.scenarios || [];
  const slotSchemas = slotSchemasConfig.payload?.slot_schemas || [];
  const tools = toolsConfig.payload?.tools || [];
  const integrationEndpoints = endpointsConfig.payload?.endpoints || [];
  state.lastData.toolCatalog = tools;
  state.lastData.integrationEndpoints = integrationEndpoints;
  if (!matrices.some((matrix) => matrix.matrix_id === state.toolMatrixId)) {
    state.toolMatrixId = matrices[0]?.matrix_id || '';
  }
  const selected = matrices.find((matrix) => matrix.matrix_id === state.toolMatrixId) || null;
  const slotContext = buildMatrixSlotContext(selected, scenarios, slotSchemas);
  state.lastData.toolMatrixSlotContext = slotContext;
  elements.viewContent.innerHTML = [
    section(
      '4. ReAct-вызовы и матрица запуска',
      `${blockCatalogControls({
        selectId: 'toolMatrixSelect',
        label: 'Матрица ReAct-вызовов',
        items: matrices,
        idKey: 'matrix_id',
        selectedId: state.toolMatrixId,
        labelKey: 'display_name',
        actionPrefix: 'tool-matrix',
        operation: state.toolMatrixOperation,
      })}
      ${renderToolLaunchEditor({ matrix: selected, matrices, scenarios, tools, integrationEndpoints, slotContext })}`,
    ),
  ].join('');
  attachCatalogSelect('toolMatrixSelect', 'toolMatrixId', renderScenarioTools);
}

async function renderScenarioEscalation() {
  const [active, scenariosConfig] = await Promise.all([
    api('/admin/config/active/escalation_policies'),
    api('/admin/config/active/service_scenarios'),
  ]);
  const policies = active.payload?.policies || [];
  const scenarios = scenariosConfig.payload?.scenarios || [];
  if (!policies.some((policy) => policy.policy_id === state.escalationPolicyId)) {
    state.escalationPolicyId = policies[0]?.policy_id || '';
  }
  const selected = policies.find((policy) => policy.policy_id === state.escalationPolicyId) || null;
  elements.viewContent.innerHTML = [
    section(
      '5. Решение и эскалация',
      `${blockCatalogControls({
        selectId: 'escalationPolicySelect',
        label: 'Политика',
        items: policies,
        idKey: 'policy_id',
        selectedId: state.escalationPolicyId,
        labelKey: 'display_name',
        actionPrefix: 'escalation',
        operation: state.escalationOperation,
      })}
      ${renderEscalationEditor({ policy: selected, policies, scenarios })}`,
    ),
  ].join('');
  attachCatalogSelect('escalationPolicySelect', 'escalationPolicyId', renderScenarioEscalation);
}

async function renderScenarioPrompts() {
  const [active, scenariosConfig, orchestratorPolicyConfig] = await Promise.all([
    api('/admin/config/active/prompt_packs'),
    api('/admin/config/active/service_scenarios'),
    api('/admin/config/active/orchestrator_policy'),
  ]);
  const packs = active.payload?.packs || [];
  const scenarios = scenariosConfig.payload?.scenarios || [];
  const confidenceDefaults = orchestratorPolicyConfig.payload?.confidence_defaults || {};
  if (!packs.some((pack) => pack.prompt_pack_id === state.promptPackId)) {
    state.promptPackId = packs[0]?.prompt_pack_id || '';
  }
  const selectedPack = packs.find((pack) => pack.prompt_pack_id === state.promptPackId) || null;
  const packOptions = packs
    .map(
      (pack) => `<option value="${escapeHtml(pack.prompt_pack_id)}" ${
        pack.prompt_pack_id === state.promptPackId ? 'selected' : ''
      }>${escapeHtml(promptPackLabel(pack))}</option>`,
    )
    .join('');
  const editor = renderPromptPackEditor({
    promptPack: selectedPack,
    packs,
    scenarios,
  });
  elements.viewContent.innerHTML = [
    section(
      '6. Промпты: обязательные блоки',
      `<div class="toolbar compact">
        <label>Пакет промптов<select id="promptPackSelect">${packOptions}</select></label>
      </div>
      <div class="scenario-menu">
        <button type="button" class="${state.promptPackOperation === 'create' ? 'primary' : ''}" data-action="prompt-pack-operation" data-operation="create">Создать</button>
        <button type="button" class="${state.promptPackOperation === 'modify' ? 'primary' : ''}" data-action="prompt-pack-operation" data-operation="modify">Модифицировать</button>
        <button type="button" class="${state.promptPackOperation === 'delete' ? 'primary' : ''}" data-action="prompt-pack-operation" data-operation="delete">Удалить</button>
      </div>
      ${renderSystemConfidenceDefaults(confidenceDefaults, { collapsed: true })}
      ${editor}`,
    ),
  ].join('');
  document.getElementById('promptPackSelect')?.addEventListener('change', (event) => {
    state.promptPackId = event.target.value;
    renderScenarioPrompts().catch((error) => setNotice(error.message || String(error), 'error'));
  });
}

async function renderInteractionChannels() {
  const [active, scenariosConfig] = await Promise.all([
    api('/admin/config/active/interaction_channels'),
    api('/admin/config/active/service_scenarios'),
  ]);
  const channels = active.payload?.channels || [];
  const scenarios = scenariosConfig.payload?.scenarios || [];
  if (!channels.some((channel) => channel.channel_id === state.interactionChannelId)) {
    state.interactionChannelId = channels[0]?.channel_id || '';
  }
  const selected = channels.find((channel) => channel.channel_id === state.interactionChannelId) || null;
  elements.viewContent.innerHTML = [
    section(
      'Каналы взаимодействия',
      `${blockCatalogControls({
        selectId: 'interactionChannelSelect',
        label: 'Канал',
        items: channels,
        idKey: 'channel_id',
        selectedId: state.interactionChannelId,
        labelKey: 'display_name',
        actionPrefix: 'interaction-channel',
        operation: state.interactionChannelOperation,
      })}
      ${renderInteractionChannelEditor({ channel: selected, channels, scenarios })}`,
    ),
  ].join('');
  attachCatalogSelect('interactionChannelSelect', 'interactionChannelId', renderInteractionChannels);
}

function channelCreateTemplate(source, channels) {
  const template = source || channels[0] || {};
  return {
    channel_id: nextConfigItemId(template.channel_id || 'debug', channels, 'channel_id'),
    display_name: '',
    mode: template.mode || 'debug',
    description: '',
    question_delivery: template.question_delivery || {
      action_type: 'show_debug_message',
      message_template: '{question}',
    },
    waiting_policy: normalizeChannelWaitingPolicy(template.waiting_policy || {
      first_reminder_after_seconds: 0,
      discussion_timeout_seconds: 0,
      sla_elapsed_percent_threshold: 0,
      on_no_answer: 'debug_stop',
    }),
    incomplete_discussion_action: template.incomplete_discussion_action || {
      action_type: 'debug_stop',
      message_template: 'Остановить сценарий и показать недостающий контекст.',
    },
    escalation_action: template.escalation_action || {
      action_type: 'debug_stop',
      message_template: 'Остановить сценарий и показать причину эскалации.',
    },
    action_profiles: template.action_profiles || defaultChannelActionProfiles(template.channel_id || 'debug'),
    enabled: template.enabled ?? true,
  };
}

function normalizeChannelWaitingPolicy(waitingPolicy = {}) {
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

function renderInteractionChannelEditor({ channel, channels, scenarios }) {
  if (state.interactionChannelOperation === 'delete') {
    if (!channel?.channel_id) {
      return '<div class="empty">Нет выбранного канала для удаления</div>';
    }
    return `
      <form class="scenario-editor panel" data-form="interaction-channel-delete">
        <div>
          <div class="metric-label">Удаляемый канал</div>
          <div class="scenario-title">${escapeHtml(channel.display_name)}</div>
        </div>
        ${channelUsagePanel(scenarios, channel.channel_id)}
        <button class="danger" type="submit">Удалить канал</button>
      </form>
    `;
  }
  const current = state.interactionChannelOperation === 'create'
    ? channelCreateTemplate(channel, channels)
    : channel;
  if (!current?.channel_id) {
    return '<div class="empty">Канал взаимодействия не выбран</div>';
  }
  const waitingPolicy = normalizeChannelWaitingPolicy(current.waiting_policy);
  return `
    <form class="scenario-editor panel" data-form="interaction-channel-editor">
      <input type="hidden" name="channel_id" value="${escapeHtml(current.channel_id)}">
      <label>Название<input name="display_name" value="${escapeHtml(current.display_name || '')}" autocomplete="off"></label>
      <label>Описание<textarea name="description" rows="3">${escapeHtml(current.description || '')}</textarea></label>
      <div class="grid two">
        <label>Режим<select name="mode">${optionList(['online_interactive', 'offline_interactive', 'debug'], current.mode)}</select></label>
        <label>Канал включен<select name="enabled">${booleanOptions(current.enabled)}</select></label>
      </div>
      <fieldset class="launch-editor">
        <legend>Уточнения у клиента</legend>
        <div class="meta">Этот блок не является эскалацией: AI задает клиенту вопрос, ждет ответ и после ответа продолжает тот же сценарий.</div>
        <div class="grid two">
          <label>Первое напоминание, сек<input name="first_reminder_after_seconds" type="number" min="0" max="604800" value="${escapeHtml(waitingPolicy.first_reminder_after_seconds)}"></label>
          <label>Таймаут обсуждения, сек<input name="discussion_timeout_seconds" type="number" min="0" max="604800" value="${escapeHtml(waitingPolicy.discussion_timeout_seconds)}"></label>
          <label>Порог SLA для офлайн-канала, %<input name="sla_elapsed_percent_threshold" type="number" min="0" max="100" value="${escapeHtml(waitingPolicy.sla_elapsed_percent_threshold)}"></label>
          <label>Если клиент не ответил<select name="on_no_answer">${activeOptionList(channelNoAnswerActions(current.mode), waitingPolicy.on_no_answer || 'debug_stop')}</select></label>
          <label>Автозакрытие требует подтверждение клиента<select name="auto_close_requires_client_confirmation">${booleanOptions(waitingPolicy.auto_close_requires_client_confirmation)}</select></label>
          <label>Ожидание приостанавливает SLA<select name="pause_sla_on_client_wait">${booleanOptions(waitingPolicy.pause_sla_on_client_wait)}</select></label>
          <label>Автозакрытие ожидания клиента, часов<input name="client_wait_auto_close_after_hours" type="number" min="1" max="168" value="${escapeHtml(waitingPolicy.client_wait_auto_close_after_hours)}"></label>
        </div>
        ${renderChannelActionFields('question_delivery', 'Как задать вопрос клиенту', current.question_delivery, current.mode)}
        ${renderChannelActionFields('incomplete_discussion_action', 'Что делать с незавершенным уточнением', current.incomplete_discussion_action, current.mode)}
      </fieldset>
      <fieldset class="launch-editor">
        <legend>Эскалация оператору</legend>
        <div class="meta">Этот блок используется, когда AI останавливает самостоятельную обработку и передает оператору пакет контекста.</div>
        ${renderChannelActionFields('escalation_action', 'Базовое действие эскалации оператору', current.escalation_action, current.mode)}
        ${renderChannelActionProfiles(current.action_profiles || [], current.mode)}
      </fieldset>
      ${channelUsagePanel(scenarios, current.channel_id)}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">${state.interactionChannelOperation === 'create' ? 'Создать канал' : 'Сохранить канал'}</button>
      </div>
    </form>
  `;
}

function renderChannelActionProfiles(profiles, mode = 'debug') {
  return `
    <div class="nested-editor">
      <div class="metric-label">Профили эскалации и таймаутов</div>
      <div class="meta">Профиль связывает логическое событие из блока "5. Решение и эскалация" с реальным действием канала.</div>
      <div id="channelProfileCards">${(profiles || []).map((profile) => renderChannelProfileCard(profile, mode)).join('')}</div>
      <button type="button" data-action="channel-profile-add">Добавить профиль</button>
    </div>
  `;
}

function renderChannelProfileCard(profile = {}, mode = 'debug') {
  const action = profile.action || {};
  return `
    <fieldset class="launch-editor" data-channel-profile-card>
      <legend>${escapeHtml(profile.display_name || 'Профиль действия')}</legend>
      <input type="hidden" name="profile_id" value="${escapeHtml(profile.profile_id || 'custom_profile')}">
      <label>Название<input name="display_name" value="${escapeHtml(profile.display_name || '')}" autocomplete="off"></label>
      <div class="grid two">
        <label>Тип события<select name="event_type">${optionList(['standard_handoff', 'no_answer', 'major_incident', 'policy_blocked', 'debug_stop'], profile.event_type || 'standard_handoff')}</select></label>
        <label>Действие канала<select name="action_type">${channelActionTypeOptions(mode, action.action_type || 'debug_stop')}</select></label>
      </div>
      <label>Шаблон сообщения<textarea name="message_template" rows="3">${escapeHtml(action.message_template || '')}</textarea></label>
      <button class="danger" type="button" data-action="channel-profile-remove">Удалить профиль</button>
    </fieldset>
  `;
}

function renderChannelActionFields(prefix, title, action = {}, mode = 'debug') {
  return `
    <fieldset class="launch-editor">
      <legend>${escapeHtml(title)}</legend>
      <div class="grid two">
        <label>Действие канала<select name="${escapeHtml(prefix)}_action_type">${channelActionTypeOptions(mode, action.action_type || 'debug_stop')}</select></label>
      </div>
      <label>Шаблон сообщения<textarea name="${escapeHtml(prefix)}_message_template" rows="3">${escapeHtml(action.message_template || '')}</textarea></label>
    </fieldset>
  `;
}

function channelActionTypes(mode = '') {
  if (mode === 'online_interactive') {
    return ['ask_end_user', 'create_draft', 'call_specialist', 'notify_on_call'];
  }
  if (mode === 'offline_interactive') {
    return ['ask_operator', 'save_context', 'create_work_order'];
  }
  if (mode === 'debug') {
    return ['show_debug_message', 'debug_stop'];
  }
  return ['show_debug_message', 'debug_stop'];
}

function channelNoAnswerActions(mode = '') {
  if (mode === 'online_interactive') {
    return ['create_draft', 'call_specialist'];
  }
  if (mode === 'offline_interactive') {
    return ['save_context', 'create_work_order'];
  }
  if (mode === 'debug') {
    return ['debug_stop'];
  }
  return ['debug_stop'];
}

function channelActionTypeOptions(mode, selected) {
  return activeOptionList(channelActionTypes(mode), selected);
}

function defaultChannelActionProfiles(channelId) {
  if (channelId === 'messenger_bot') {
    return [
      { profile_id: 'standard_handoff', display_name: 'Эскалация: подключить оператора к чату', event_type: 'standard_handoff', action: { action_type: 'call_specialist', message_template: 'Позвать специалиста в диалог с полным контекстом сценария.' } },
      { profile_id: 'no_answer', display_name: 'Клиент не ответил: создать черновик', event_type: 'no_answer', action: { action_type: 'create_draft', message_template: 'Создать черновик заявки и сохранить контекст диалога.' } },
      { profile_id: 'major_incident', display_name: 'Major Incident: оповестить дежурных', event_type: 'major_incident', action: { action_type: 'notify_on_call', message_template: 'Оповестить дежурную команду и приложить пакет Major Incident.' } },
      { profile_id: 'policy_blocked', display_name: 'Политика заблокировала автоисполнение', event_type: 'policy_blocked', action: { action_type: 'call_specialist', message_template: 'Позвать специалиста для ручной проверки.' } },
    ];
  }
  if (channelId === 'service_desk') {
    return [
      { profile_id: 'standard_handoff', display_name: 'Эскалация: создать наряд', event_type: 'standard_handoff', action: { action_type: 'create_work_order', message_template: 'Создать наряд ответственному специалисту с пакетом эскалации.' } },
      { profile_id: 'no_answer', display_name: 'Клиент не ответил: создать наряд', event_type: 'no_answer', action: { action_type: 'create_work_order', message_template: 'Создать наряд по незавершенному уточнению и приложить контекст.' } },
      { profile_id: 'major_incident', display_name: 'Major Incident: создать наряд дежурной группе', event_type: 'major_incident', action: { action_type: 'create_work_order', message_template: 'Создать срочный наряд дежурной группе с пакетом Major Incident.' } },
      { profile_id: 'policy_blocked', display_name: 'Политика заблокировала автоисполнение', event_type: 'policy_blocked', action: { action_type: 'create_work_order', message_template: 'Создать наряд для ручной проверки.' } },
    ];
  }
  return [
    { profile_id: 'standard_handoff', display_name: 'Отладка: эскалация оператору', event_type: 'standard_handoff', action: { action_type: 'debug_stop', message_template: 'Остановить сценарий и показать причину эскалации оператору.' } },
    { profile_id: 'no_answer', display_name: 'Отладка: клиент не ответил', event_type: 'no_answer', action: { action_type: 'debug_stop', message_template: 'Остановить dry-run из-за отсутствия ответа клиента.' } },
    { profile_id: 'major_incident', display_name: 'Отладка: Major Incident', event_type: 'major_incident', action: { action_type: 'debug_stop', message_template: 'Остановить сценарий и показать оператору причину Major Incident.' } },
    { profile_id: 'policy_blocked', display_name: 'Отладка: policy blocked', event_type: 'policy_blocked', action: { action_type: 'debug_stop', message_template: 'Остановить сценарий и показать блокировку policy.' } },
  ];
}

function channelUsagePanel(scenarios, channelId) {
  const used = (scenarios || []).filter((scenario) =>
    scenario.default_channel_id === channelId || (scenario.allowed_channel_ids || []).includes(channelId),
  );
  const names = used.map((scenario) => scenario.display_name || scenario.scenario_id);
  const text = names.length
    ? `Используется в сценариях: ${names.join(', ')}. Для удаления сначала измените или удалите эти сценарии.`
    : 'Не используется в сценариях. Канал можно удалить.';
  return `
    <div class="slot-schema-derived">
      <div class="metric-label">Где используется</div>
      <div class="meta">${escapeHtml(text)}</div>
    </div>
  `;
}

function renderScenarioEditor({
  detail,
  serviceScenarios,
  slotSchemas,
  routes,
  policies,
  toolMatrices,
  promptPacks,
  escalationPolicies,
  interactionChannels = [],
}) {
  if (state.scenarioOperation === 'delete') {
    if (!detail?.scenario) {
      return '<div class="empty">Нет выбранного сценария для удаления</div>';
    }
    return `
      <form class="scenario-editor panel" data-form="scenario-delete">
        <div>
          <div class="metric-label">Удаляемый сценарий</div>
          <div class="scenario-title">${escapeHtml(detail.scenario.display_name)}</div>
          <div class="meta">Будет удалена запись сценария из домена service_scenarios. Связанные слоты, маршруты, prompt pack и матрица ReAct-вызовов остаются в своих доменах для повторного использования или отдельной очистки.</div>
        </div>
        <button class="danger" type="submit">Удалить сценарий</button>
      </form>
    `;
  }

  const scenario = state.scenarioOperation === 'create'
    ? scenarioCreateTemplate(detail?.scenario, serviceScenarios)
    : detail?.scenario;
  if (!scenario) {
    return '<div class="empty">Нет выбранного сценария для редактирования</div>';
  }
  const statusOptions = ['active', 'draft', 'planned', 'disabled']
    .map((status) => `<option value="${status}" ${scenario.status === status ? 'selected' : ''}>${escapeHtml(visibleLabels[status] || status)}</option>`)
    .join('');
  return `
    <form class="scenario-editor panel" data-form="scenario-editor">
      <input type="hidden" name="scenario_id" value="${escapeHtml(scenario.scenario_id || '')}">
      <input type="hidden" name="existing_tags" value="${escapeHtml(JSON.stringify(scenario.tags || []))}">
      <div class="grid two">
        <label>Статус<select name="status">${statusOptions}</select></label>
      </div>
      <label>Название<input name="display_name" value="${escapeHtml(scenario.display_name || '')}" autocomplete="off"></label>
      <label>Описание<textarea name="description" rows="4">${escapeHtml(scenario.description || '')}</textarea></label>
      <div class="grid two">
        <label>Схема слотов<select name="slot_schema_id">${referenceOptions(slotSchemas, 'slot_schema_id', scenario.slot_schema_id, 'display_name')}</select></label>
        <label>Маршрут классификации<select name="classification_route_id">${referenceOptions(routes, 'route_id', scenario.classification_route_id, 'display_name')}</select></label>
        <label>Политика оркестратора<select name="orchestrator_policy_id">${referenceOptions(policies, 'policy_id', scenario.orchestrator_policy_id, 'display_name')}</select></label>
        <label>Матрица ReAct-вызовов<select name="tool_launch_matrix_id">${referenceOptions(toolMatrices, 'matrix_id', scenario.tool_launch_matrix_id, 'display_name')}</select></label>
        <label>Пакет промптов
          <select name="prompt_pack_id">${referenceOptions(promptPacks, 'prompt_pack_id', scenario.prompt_pack_id, (pack) => promptPackLabel(pack))}</select>
          <span class="field-help">Связь сценария с пакетом. Содержимое обязательных блоков редактируется в меню "Сценарии обработки -> 6. Промпты".</span>
        </label>
        <label>Политика эскалации<select name="escalation_policy_id">${referenceOptions(escalationPolicies, 'policy_id', scenario.escalation_policy_id, 'display_name')}</select></label>
        <label>Канал по умолчанию
          <select name="default_channel_id">${referenceOptions(interactionChannels, 'channel_id', scenario.default_channel_id || 'debug', 'display_name')}</select>
          <span class="field-help">Канал определяет, куда задаются вопросы, как долго ждать ответ и что делать при незавершенном обсуждении или эскалации.</span>
        </label>
        <label>Разрешенные каналы
          <select name="allowed_channel_ids" multiple size="3">${multiReferenceOptions(interactionChannels, 'channel_id', scenario.allowed_channel_ids || [scenario.default_channel_id || 'debug'], 'display_name')}</select>
          <span class="field-help">Сценарий можно запускать только в выбранных каналах. Канал по умолчанию должен входить в этот список.</span>
        </label>
      </div>
      <details class="launch-editor">
        <summary>Наблюдаемость сценария</summary>
        <div class="grid two">
          <label class="checkbox-line">
            <input type="checkbox" name="audit_required" value="true" ${scenario.audit_required ?? true ? 'checked' : ''}>
            <span>Аудит включен</span>
          </label>
          <label class="checkbox-line">
            <input type="checkbox" name="log_required" value="true" ${scenario.log_required ?? true ? 'checked' : ''}>
            <span>Логирование включено</span>
          </label>
        </div>
        <div class="meta">Настройка применяется ко всем ReAct-вызовам, профилям разрешения атрибутов и эскалациям внутри сценария.</div>
      </details>
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">${state.scenarioOperation === 'create' ? 'Создать сценарий' : 'Сохранить изменения'}</button>
      </div>
    </form>
  `;
}

async function renderResolutionProfiles() {
  const [active, slotSchemasConfig, scenariosConfig, toolsConfig, endpointsConfig, matricesConfig] = await Promise.all([
    api('/admin/config/active/attribute_resolution_profiles'),
    api('/admin/config/active/slot_schemas'),
    api('/admin/config/active/service_scenarios'),
    api('/admin/config/active/tools'),
    api('/admin/config/active/integration_endpoints'),
    api('/admin/config/active/tool_launch_matrix'),
  ]);
  const profiles = active.payload?.profiles || [];
  const slotSchemas = slotSchemasConfig.payload?.slot_schemas || [];
  const scenarios = scenariosConfig.payload?.scenarios || [];
  const tools = toolsConfig.payload?.tools || [];
  const endpoints = endpointsConfig.payload?.endpoints || [];
  const toolMatrices = matricesConfig.payload?.matrices || [];
  state.lastData.resolutionProfiles = profiles;
  state.lastData.slotSchemas = slotSchemas;
  state.lastData.serviceScenarios = scenarios;
  state.lastData.toolCatalog = tools;
  state.lastData.integrationEndpoints = endpoints;
  state.lastData.toolMatrices = toolMatrices;
  if (!profiles.some((profile) => profile.profile_id === state.resolutionProfileId)) {
    state.resolutionProfileId = profiles[0]?.profile_id || '';
  }
  const selectedProfile = profiles.find((profile) => profile.profile_id === state.resolutionProfileId) || null;
  const profileOptions = profiles
    .map(
      (profile) => `<option value="${escapeHtml(profile.profile_id)}" ${
        profile.profile_id === state.resolutionProfileId ? 'selected' : ''
      }>${escapeHtml(profile.display_name)}</option>`,
    )
    .join('');
  const editor = renderResolutionProfileEditor({
    profile: selectedProfile,
    profiles,
    slotSchemas,
    scenarios,
    tools,
    endpoints,
    toolMatrices,
  });
  elements.viewContent.innerHTML = [
    section(
      'Профили разрешения атрибутов',
      `${resolutionProfileHowToPanel()}
      <div class="toolbar compact">
        <label>Профиль<select id="resolutionProfileSelect">${profileOptions}</select></label>
      </div>
      <div class="scenario-menu">
        <button type="button" class="${state.resolutionOperation === 'create' ? 'primary' : ''}" data-action="resolution-operation" data-operation="create">Создать</button>
        <button type="button" class="${state.resolutionOperation === 'modify' ? 'primary' : ''}" data-action="resolution-operation" data-operation="modify">Модифицировать</button>
        <button type="button" class="${state.resolutionOperation === 'delete' ? 'primary' : ''}" data-action="resolution-operation" data-operation="delete">Удалить</button>
      </div>
      ${editor}`,
    ),
  ].join('');
  syncResolutionTargetSlotCustom(elements.viewContent);
  syncAllResolutionOutputSlotCustom(elements.viewContent);
  document.getElementById('resolutionProfileSelect')?.addEventListener('change', (event) => {
    state.resolutionProfileId = event.target.value;
    renderResolutionProfiles().catch((error) => setNotice(error.message || String(error), 'error'));
  });
}

function resolutionProfileHowToPanel() {
  return `
    <div class="slot-schema-derived">
      <div class="metric-label">Как подключить профиль к сценарию</div>
      <div class="meta">
        Здесь профиль только создается или модифицируется. Чтобы он начал заполнять слот, откройте
        "Сценарии обработки -> 0. Слоты", раскройте нужный слот, выберите "Как получить значение слота = профиль разрешения"
        и затем выберите этот профиль в поле "Профиль разрешения атрибута". Если слота еще нет, можно создать профиль по ключу будущего
        слота или сохранить слот без выбранного профиля: будет создан черновик профиля.
      </div>
    </div>
  `;
}

function resolutionProfileUsagePanel(slotSchemas, scenarios, profileId) {
  const usedSchemas = (slotSchemas || []).filter((schema) =>
    (schema.slots || []).some((slot) => slot.resolution_profile_id === profileId),
  );
  const schemaIds = new Set(usedSchemas.map((schema) => schema.slot_schema_id));
  const usedScenarios = (scenarios || []).filter((scenario) => schemaIds.has(scenario.slot_schema_id));
  const schemaNames = usedSchemas.map((schema) => schema.display_name || schema.slot_schema_id);
  const scenarioNames = usedScenarios.map((scenario) => scenario.display_name || scenario.scenario_id);
  const parts = [];
  if (schemaNames.length) {
    parts.push(`используется в схемах слотов: ${schemaNames.join(', ')}`);
  }
  if (scenarioNames.length) {
    parts.push(`затрагивает сценарии: ${scenarioNames.join(', ')}`);
  }
  const text = parts.length
    ? `${parts.join('; ')}. Для удаления сначала уберите профиль из схем слотов.`
    : 'Не используется в схемах слотов и сценариях. Профиль можно удалить.';
  return `
    <div class="slot-schema-derived">
      <div class="metric-label">Где используется</div>
      <div class="meta">${escapeHtml(text)}</div>
    </div>
  `;
}

function buildResolutionSlotContext(profile, slotSchemas, scenarios) {
  const schemaById = slotSchemaById(slotSchemas);
  const usedSchemaIds = new Set((slotSchemas || [])
    .filter((schema) => (schema.slots || []).some((slot) => slot.resolution_profile_id === profile?.profile_id))
    .map((schema) => schema.slot_schema_id));
  if (profile?.slot_schema_id) {
    usedSchemaIds.add(profile.slot_schema_id);
  }
  const usedScenarios = (scenarios || []).filter((scenario) => usedSchemaIds.has(scenario.slot_schema_id));
  const profileId = profile?.profile_id || '';
  if (state.resolutionSlotProfileId !== profileId) {
    state.resolutionSlotProfileId = profileId;
    state.resolutionSlotScenarioId = usedScenarios[0]?.scenario_id
      || (scenarios || []).find((scenario) => scenario.slot_schema_id === profile?.slot_schema_id)?.scenario_id
      || state.scenarioId
      || (scenarios || [])[0]?.scenario_id
      || '';
  }
  const selectedScenario = (scenarios || []).find((scenario) => scenario.scenario_id === state.resolutionSlotScenarioId)
    || usedScenarios[0]
    || (scenarios || []).find((scenario) => scenario.slot_schema_id === profile?.slot_schema_id)
    || (scenarios || []).find((scenario) => scenario.scenario_id === state.scenarioId)
    || (scenarios || [])[0]
    || null;
  if (selectedScenario && state.resolutionSlotScenarioId !== selectedScenario.scenario_id) {
    state.resolutionSlotScenarioId = selectedScenario.scenario_id;
  }
  const schema = selectedScenario ? schemaById[selectedScenario.slot_schema_id] : null;
  const slots = (schema?.slots || []).map((slot) => ({
    ...slot,
    scenario_ids: selectedScenario ? [selectedScenario.scenario_id] : [],
    scenario_names: selectedScenario ? [selectedScenario.display_name || selectedScenario.scenario_id] : [],
    missing_scenario_names: [],
  }));
  return {
    selectedScenario,
    schema,
    slots,
    scenarioCount: selectedScenario ? 1 : 0,
    scenarioNames: selectedScenario ? [selectedScenario.display_name || selectedScenario.scenario_id] : [],
    usedScenarios,
  };
}

function resolutionScenarioOptions(scenarios, selectedScenarioId) {
  if (!(scenarios || []).length) {
    return '<option value="">Нет сценариев</option>';
  }
  return (scenarios || [])
    .map((scenario) => `<option value="${escapeHtml(scenario.scenario_id)}" ${
      scenario.scenario_id === selectedScenarioId ? 'selected' : ''
    }>${escapeHtml(scenario.display_name || scenario.scenario_id)}</option>`)
    .join('');
}

function resolutionSlotMultiOptions(slotContext, selectedValues) {
  const selected = new Set(selectedValues || []);
  const known = new Set((slotContext.slots || []).map((slot) => slot.slot_id));
  const missingSelected = [...selected].filter((slotId) => slotId && !known.has(slotId));
  const options = [
    ...(slotContext.slots || []).map((slot) => ({
      value: slot.slot_id,
      label: slotOptionLabel(slot, slotContext),
    })),
    ...missingSelected.map((slotId) => ({
      value: slotId,
      label: `Слот не найден в выбранном сценарии: ${slotId}`,
    })),
  ];
  if (!options.length) {
    return '<option value="">Нет доступных слотов</option>';
  }
  return options
    .map(
      (option) => `<option value="${escapeHtml(option.value)}" ${selected.has(option.value) ? 'selected' : ''}>${escapeHtml(option.label)}</option>`,
    )
    .join('');
}

function resolutionSlotContextPanel(slotContext) {
  const scenarioName = slotContext.selectedScenario
    ? slotContext.selectedScenario.display_name || slotContext.selectedScenario.scenario_id
    : 'сценарий не выбран';
  const schemaName = slotContext.schema?.display_name || slotContext.schema?.slot_schema_id || 'схема слотов не найдена';
  const usedNames = (slotContext.usedScenarios || []).map((scenario) => scenario.display_name || scenario.scenario_id);
  const usedText = usedNames.length
    ? `Профиль уже используется в сценариях: ${usedNames.join(', ')}.`
    : 'Профиль пока не используется сценариями; список слотов ниже нужен для корректного выбора при настройке.';
  return `
    <div class="slot-schema-derived">
      <div class="metric-label">Контекст слотов профиля</div>
      <div class="meta">${escapeHtml(`Сейчас выбран сценарий "${scenarioName}", схема "${schemaName}". ${usedText}`)}</div>
    </div>
  `;
}

function resolutionTargetSlotField(slotContext, selectedSlotId) {
  const slots = slotContext.slots || [];
  const selectedExists = slots.some((slot) => slot.slot_id === selectedSlotId);
  const customSelected = !selectedSlotId && !slots.length;
  const options = [
    ...(slots.length ? [`<option value="" ${!selectedSlotId ? 'selected' : ''}>выберите слот</option>`] : []),
    ...slots.map((slot) => `<option value="${escapeHtml(slot.slot_id)}" ${
      slot.slot_id === selectedSlotId ? 'selected' : ''
    }>${escapeHtml(slotOptionLabel(slot, slotContext))}</option>`),
  ];
  if (selectedSlotId && !selectedExists) {
    options.unshift(
      `<option value="${escapeHtml(selectedSlotId)}" selected>${escapeHtml(`Слот пока не найден в выбранной схеме: ${selectedSlotId}`)}</option>`,
    );
  }
  options.push(`<option value="__custom__" ${customSelected ? 'selected' : ''}>Новый слот: указать ключ ниже</option>`);
  return `
    <label>Целевой слот
      <select name="target_slot_id" data-resolution-target-slot>${options.join('')}</select>
      <span class="field-help">Основной слот, ради которого выполняется профиль. Если слота еще нет, выберите создание нового и укажите его будущий ключ.</span>
    </label>
    <label data-resolution-target-slot-custom ${customSelected ? '' : 'hidden'}>
      Ключ нового слота
      <input name="target_slot_id_custom" value="" autocomplete="off" placeholder="user_login">
      <span class="field-help">Используется только для первого создания профиля до добавления слота в схему. После создания слота выберите его из списка.</span>
    </label>
  `;
}

function toolsForScenario(tools = [], scenarios = [], toolMatrices = [], scenario = null, referencedToolNames = []) {
  const matrix = scenario
    ? (toolMatrices || []).find((item) => item.matrix_id === scenario.tool_launch_matrix_id)
    : null;
  const allowedNames = new Set((matrix?.launches || []).map((launch) => launch.tool_name).filter(Boolean));
  const referenced = new Set((referencedToolNames || []).filter(Boolean));
  const result = (tools || []).filter((tool) => !allowedNames.size || allowedNames.has(tool.tool_name) || referenced.has(tool.tool_name));
  return result.length ? result : tools;
}

function renderResolutionProfileEditor({ profile, profiles, slotSchemas = [], scenarios = [], tools = [], endpoints = [], toolMatrices = [] }) {
  if (state.resolutionOperation === 'delete') {
    if (!profile) {
      return '<div class="empty">Нет выбранного профиля для удаления</div>';
    }
    return `
      <form class="scenario-editor panel" data-form="resolution-profile-delete">
        <div>
          <div class="metric-label">Удаляемый профиль</div>
          <div class="scenario-title">${escapeHtml(profile.display_name)}</div>
        </div>
        ${resolutionProfileUsagePanel(slotSchemas, scenarios, profile.profile_id)}
        <button class="danger" type="submit">Удалить профиль</button>
      </form>
    `;
  }

  const current = state.resolutionOperation === 'create'
    ? resolutionProfileCreateTemplate(profile, profiles)
    : profile;
  if (!current) {
    return '<div class="empty">Нет выбранного профиля для редактирования</div>';
  }
  const slotContext = buildResolutionSlotContext(current, slotSchemas, scenarios);
  const humanPolicy = current.human_resolution_policy || {};
  const handoffAction = humanPolicy.handoff_action || 'operator_handoff';
  const handoffOptions = ['operator_handoff', 'escalate', 'debug_stop', 'leave_empty']
    .map((value) => `<option value="${value}" ${handoffAction === value ? 'selected' : ''}>${escapeHtml(visibleLabels[value] || value)}</option>`)
    .join('');
  const fallbackAction = humanPolicy.fallback_action || current.fallback?.action || 'ask_user';
  const fallbackOptions = ['ask_user', 'operator_handoff', 'escalate', 'leave_empty']
    .map((value) => `<option value="${value}" ${fallbackAction === value ? 'selected' : ''}>${escapeHtml(visibleLabels[value] || value)}</option>`)
    .join('');
  const enrichmentSteps = profileEnrichmentSteps(current, tools, endpoints);
  const outputRules = profileOutputRules(current);
  const llmScript = current.llm_resolution_script || {};
  const contextTools = toolsForScenario(
    tools,
    scenarios,
    toolMatrices,
    slotContext.selectedScenario,
    enrichmentSteps.map((step) => step.react_call),
  );
	  return `
	    <form class="scenario-editor panel" data-form="resolution-profile-editor">
	      <input type="hidden" name="profile_id" value="${escapeHtml(current.profile_id || '')}">
	      <input type="hidden" name="slot_schema_id" value="${escapeHtml(slotContext.schema?.slot_schema_id || current.slot_schema_id || '')}">
	      <div class="grid two">
        <label>Название<input name="display_name" value="${escapeHtml(current.display_name || '')}" autocomplete="off"></label>
      </div>
      <label>Описание<textarea name="description" rows="3">${escapeHtml(current.description || '')}</textarea></label>
      ${resolutionSlotContextPanel(slotContext)}
      <div class="grid two">
        <label>Сценарий для выбора слотов
          <select name="resolution_slot_scenario_id" data-resolution-slot-scenario>${resolutionScenarioOptions(scenarios, slotContext.selectedScenario?.scenario_id || '')}</select>
          <span class="field-help">Список целевых и выходных слотов строится из схемы слотов выбранного сценария.</span>
        </label>
        ${resolutionTargetSlotField(slotContext, current.target_slot_id || '')}
        <label>Лимит попыток
          <input name="max_attempts" type="number" min="1" max="10" value="${escapeHtml(current.max_attempts || 1)}">
          <span class="field-help">Сколько раз можно уточнять признаки и повторять операцию разрешения.</span>
        </label>
      </div>
      <fieldset class="launch-editor enrichment-builder">
        <legend>Обогащение контекста</legend>
        <div class="meta">Шаги выполняются сверху вниз. Результат каждого ReAct-вызова доступен следующим шагам и LLM-правилу через ссылку вида step.</div>
        <div data-enrichment-step-list>
          ${renderEnrichmentStepCards(enrichmentSteps, slotContext, outputRules, contextTools)}
        </div>
        <button type="button" data-action="enrichment-step-add">Добавить шаг обогащения</button>
      </fieldset>
      <fieldset class="launch-editor">
        <legend>Выходные слоты и порядок заполнения</legend>
        <div class="meta">Профиль может заполнить только выбранные слоты сценария. Порядок определяет, в какой последовательности LLM-правило должно пытаться сформировать значения.</div>
        <div class="parameter-binding-list" data-resolution-output-list>
          ${renderResolutionOutputRows(outputRules, slotContext)}
        </div>
        <button type="button" data-action="resolution-output-add">Добавить выходной слот</button>
      </fieldset>
      <fieldset class="launch-editor">
        <legend>LLM-правила выбора, заполнения и уточнения</legend>
        <label>Скрипт разрешения
          <textarea name="llm_resolution_script_text" rows="7">${escapeHtml(llmScript.script_text || defaultResolutionScriptText(current))}</textarea>
          <span class="field-help">Текст объясняет модели, как оценивать ответ операции, в каком порядке заполнять выходные слоты, когда задавать уточняющий вопрос клиенту и когда эскалировать оператору.</span>
        </label>
      </fieldset>
      <details class="launch-editor">
        <summary>Пороги внутри профиля</summary>
        <div class="meta">Обычно используются системные пороги. Заполняйте эти поля только для исключений конкретного профиля.</div>
        <div class="grid two">
          <label>Базовый порог
            <input name="confidence_threshold" type="number" min="0" max="1" step="0.01" value="${escapeHtml(current.confidence_threshold ?? '')}">
            <span class="field-help">Используется как fallback для внутренних порогов профиля.</span>
          </label>
          <label>Автозаполнение от
            <input name="confidence_auto_fill" type="number" min="0" max="1" step="0.01" value="${escapeHtml(current.confidence_thresholds?.auto_fill ?? '')}">
          </label>
          <label>Уточнение ниже
            <input name="confidence_clarification" type="number" min="0" max="1" step="0.01" value="${escapeHtml(current.confidence_thresholds?.clarification ?? '')}">
          </label>
          <label>Эскалация оператору ниже
            <input name="confidence_operator_handoff" type="number" min="0" max="1" step="0.01" value="${escapeHtml(current.confidence_thresholds?.operator_handoff ?? '')}">
          </label>
        </div>
      </details>
      <fieldset class="launch-editor">
        <legend>Уточнение у клиента и эскалация оператору</legend>
        <div class="meta">Уточнение продолжает AI-сценарий после ответа клиента. Эскалация останавливает самостоятельную обработку и передает контекст оператору.</div>
        <div class="grid two">
          <label>Слоты для уточнения у клиента
            <select name="clarification_slots" multiple size="6">${resolutionSlotMultiOptions(slotContext, humanPolicy.clarification_slots || [])}</select>
            <span class="field-help">Какие слоты сценария запросить у клиента для следующей попытки разрешения атрибута.</span>
          </label>
          <label>Пакет эскалации оператору
            <select name="handoff_package" multiple size="6">${resolutionSlotMultiOptions(slotContext, humanPolicy.handoff_package || [])}</select>
            <span class="field-help">Какие слоты сценария передать оператору, если AI не может продолжить самостоятельно.</span>
          </label>
          <label>Действие эскалации оператору
            <select name="handoff_action">${handoffOptions}</select>
          </label>
          <label>Резервное действие
            <select name="fallback_action">${fallbackOptions}</select>
          </label>
        </div>
        <label>Вопрос клиенту при неоднозначном или пустом результате
          <textarea name="clarification_question" rows="2">${escapeHtml(humanPolicy.clarification_question || current.fallback?.question || '')}</textarea>
        </label>
      </fieldset>
      ${resolutionProfileUsagePanel(slotSchemas, scenarios, current.profile_id)}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">${state.resolutionOperation === 'create' ? 'Создать профиль' : 'Сохранить профиль'}</button>
      </div>
    </form>
  `;
}

const resolutionSourceTypeLabels = {
  react_call: 'endpoint-операция чтения',
  ticket_history: 'история заявок',
  case_data: 'данные обращения',
  disabled: 'отключено',
};

const resultFieldTypes = ['string', 'number', 'boolean', 'object', 'array', 'unknown'];

function profileResolverOperation(profile = {}) {
  return profile.resolver_operation || profile.candidate_source || {
    source_type: 'disabled',
    parameter_mapping: {},
  };
}

function profileOutputSlotIds(profile = {}) {
  return (profile.output_slots_order || profile.output_slots || [])
    .map((slot) => (typeof slot === 'string' ? slot : slot.slot_id))
    .filter(Boolean);
}

function profileOutputRules(profile = {}) {
  const rules = (profile.output_slots_order || []).map((rule, index) => ({
    slot_id: rule.slot_id || '',
    order: rule.order || index + 1,
    required_for_success: rule.required_for_success ?? rule.slot_id === profile.target_slot_id,
    source_hint: rule.source_hint || rule.slot_id || '',
    fallback: rule.fallback || (rule.slot_id === profile.target_slot_id ? 'ask_clarification' : 'leave_empty'),
  }));
  if (!rules.length) {
    for (const slotId of profileOutputSlotIds(profile)) {
      rules.push({
        slot_id: slotId,
        order: rules.length + 1,
        required_for_success: slotId === profile.target_slot_id,
        source_hint: slotId,
        fallback: slotId === profile.target_slot_id ? 'ask_clarification' : 'leave_empty',
      });
    }
  }
  if (profile.target_slot_id && !rules.some((rule) => rule.slot_id === profile.target_slot_id)) {
    rules.unshift({
      slot_id: profile.target_slot_id,
      order: 1,
      required_for_success: true,
      source_hint: profile.target_slot_id,
      fallback: 'ask_clarification',
    });
  }
  return rules.map((rule, index) => ({ ...rule, order: index + 1 }));
}

function candidateBindingValue(toolName, binding) {
  if (!toolName || !binding?.endpoint_id || !binding?.operation_id) return '';
  return `${toolName}::${binding.endpoint_id}::${binding.operation_id}`;
}

function selectedCandidateBinding(source) {
  return candidateBindingValue(source?.tool_name, source);
}

function candidateBindingOptions(tools, source) {
  const selected = selectedCandidateBinding(source);
  const options = ['<option value="">не выбрано</option>'];
  for (const tool of tools || []) {
    for (const binding of tool.endpoint_bindings || []) {
      const value = candidateBindingValue(tool.tool_name, binding);
      const label = `${tool.tool_name} -> ${binding.endpoint_id} / ${binding.operation_id}`;
      options.push(`<option value="${escapeHtml(value)}" ${value === selected ? 'selected' : ''}>${escapeHtml(label)}</option>`);
    }
  }
  return options.join('');
}

function selectedCandidateOperation(profile, tools, endpoints) {
  const source = profileResolverOperation(profile);
  const endpoint = (endpoints || []).find((item) => item.endpoint_id === source.endpoint_id);
  const operation = endpoint?.operations?.[source.operation_id] || null;
  const tool = (tools || []).find((item) => item.tool_name === source.tool_name) || null;
  return { tool, endpoint, operation };
}

function inferResultFieldsFromOperation(operation) {
  const output = operation?.mock_output || {};
  const listKey = Object.keys(output).find((key) => Array.isArray(output[key]));
  const sample = listKey && output[listKey]?.[0] && typeof output[listKey][0] === 'object'
    ? output[listKey][0]
    : output;
  const fields = Object.entries(sample || {})
    .filter(([, value]) => value === null || ['string', 'number', 'boolean'].includes(typeof value))
    .map(([fieldId, value]) => ({
      field_id: fieldId,
      display_name: fieldId,
      field_type: value === null ? 'unknown' : typeof value,
      description: '',
    }));
  return fields.length ? fields : [{ field_id: 'value', display_name: 'Значение', field_type: 'unknown', description: '' }];
}

function renderResolverParameterMapping(profile, slotContext, tools, endpoints) {
  const { operation } = selectedCandidateOperation(profile, tools, endpoints);
  const mapping = profileResolverOperation(profile).parameter_mapping || {};
  const names = operation ? operationParameterNames(operation, mapping) : Object.keys(mapping);
  if (!names.length) {
    return '<div class="empty">У выбранной операции нет описанных входных параметров.</div>';
  }
  return `
    <div class="parameter-binding-list">
      <div class="parameter-binding-header">
        <span>Входной параметр операции</span>
        <span>Слот сценария</span>
      </div>
      ${names.map((name) => `
        <div class="parameter-binding-row" data-resolver-param-row>
          <input type="hidden" data-resolver-param-name value="${escapeHtml(name)}">
          <div class="parameter-binding-meta">
            <strong>${escapeHtml(name)}</strong>
            <span>${escapeHtml(operation ? schemaMetaLine(name, schemaProperties(operation.request_schema || {})[name], schemaRequired(operation.request_schema || {}).includes(name), ' входной параметр') : 'входной параметр операции')}</span>
          </div>
          <label>Слот
            <select data-resolver-param-source>${resolverSlotSourceOptions(slotContext, mapping[name] || defaultResolverParameterSource(name, slotContext))}</select>
          </label>
        </div>
      `).join('')}
    </div>
  `;
}

function resolverSlotSourceOptions(slotContext, selected) {
  const options = [`<option value="" ${!selected ? 'selected' : ''}>не использовать</option>`];
  const knownValues = new Set();
  for (const slot of slotContext.slots || []) {
    const value = `slot:${slot.slot_id}`;
    knownValues.add(value);
    options.push(`<option value="${escapeHtml(value)}" ${selected === value ? 'selected' : ''}>${escapeHtml(slotOptionLabel(slot, slotContext))}</option>`);
  }
  if (selected && !knownValues.has(selected)) {
    options.push(`<option value="${escapeHtml(selected)}" selected>${escapeHtml(selected)}</option>`);
  }
  return options.join('');
}

function defaultResolverParameterSource(parameterName, slotContext) {
  const slotIds = new Set((slotContext.slots || []).map((slot) => slot.slot_id));
  if (slotIds.has(parameterName)) return `slot:${parameterName}`;
  if (parameterName === 'login' && slotIds.has('user_login')) return 'slot:user_login';
  if (parameterName === 'object_ref' && slotIds.has('device_id')) return 'slot:device_id';
  if (parameterName === 'object_ref' && slotIds.has('location')) return 'slot:location';
  if (parameterName === 'target_ref' && slotIds.has('location')) return 'slot:location';
  if (parameterName === 'target_ref' && slotIds.has('resource_name')) return 'slot:resource_name';
  if (parameterName === 'query' && slotIds.has('symptom')) return 'slot:symptom';
  return '';
}

function profileEnrichmentSteps(profile = {}, tools = [], endpoints = []) {
  if (Array.isArray(profile.enrichment_steps)) {
    return profile.enrichment_steps;
  }
  const source = profileResolverOperation(profile);
  if (source.source_type !== 'react_call' || !source.tool_name) {
    return [];
  }
  const { operation } = selectedCandidateOperation(profile, tools, endpoints);
  return [{
    step_id: 'step1',
    step_name: `Получить ${source.tool_name}`,
    react_call: source.tool_name,
    parameter_mapping: source.parameter_mapping || {},
    result_fields: inferResultFieldsFromOperation(operation),
    on_error: 'continue_to_llm',
  }];
}

function renderEnrichmentStepCards(steps, slotContext, outputRules, tools) {
  const normalizedSteps = (steps || []).map((step, index) => normalizeEnrichmentStep(step, index, tools));
  if (!normalizedSteps.length) {
    state.resolutionEnrichmentEditIndex = 0;
    return '<div class="empty">Шаги обогащения не настроены. Добавьте шаг обогащения или оставьте профиль как черновик без внешних данных.</div>';
  }
  const activeIndex = Math.max(0, Math.min(state.resolutionEnrichmentEditIndex || 0, normalizedSteps.length - 1));
  state.resolutionEnrichmentEditIndex = activeIndex;
  return `
    <div class="enrichment-step-table">
      <div class="enrichment-step-header">
        <span>N</span>
        <span>Шаг</span>
        <span>ReAct-вызов</span>
        <span>При ошибке</span>
        <span>Действия</span>
      </div>
      ${normalizedSteps.map((step, index) => renderEnrichmentStepCard(
        step,
        index,
        normalizedSteps.slice(0, index),
        slotContext,
        outputRules,
        tools,
        index === activeIndex,
      )).join('')}
    </div>
  `;
}

function normalizeEnrichmentStep(step = {}, index = 0, tools = []) {
  const tool = findToolInCatalog(tools, step.react_call) || (step.react_call ? null : tools[0]) || null;
  const reactCall = step.react_call || tool?.tool_name || '';
  return {
    step_id: normalizeEnrichmentStepId(step.step_id, index),
    step_name: step.step_name || '',
    react_call: reactCall,
    parameter_mapping: step.parameter_mapping || {},
    result_fields: step.result_fields?.length ? step.result_fields : resultFieldsFromTool(tool),
    on_error: step.on_error || 'continue_to_llm',
    configuration_instruction: step.configuration_instruction || '',
    generated_structure_metadata: step.generated_structure_metadata || {},
  };
}

function normalizeEnrichmentStepId(stepId, index = 0) {
  const value = String(stepId || '').trim();
  if (/^step[1-9][0-9]*$/.test(value)) {
    return value;
  }
  return `step${index + 1}`;
}

function renderEnrichmentStepCard(step = {}, index = 0, previousSteps = [], slotContext = { slots: [] }, outputRules = [], tools = [], active = false) {
  const tool = findToolInCatalog(tools, step.react_call) || null;
  const stepTitle = step.step_name || tool?.description || step.react_call || 'новый ReAct-вызов';
  const stepId = normalizeEnrichmentStepId(step.step_id, index);
  return `
    <div class="enrichment-step-card ${active ? 'active' : ''}" data-enrichment-step-card data-enrichment-step-index="${index}">
      ${active ? '' : `<textarea hidden data-enrichment-step-json>${escapeHtml(JSON.stringify(step))}</textarea>`}
      <div class="enrichment-step-row">
        <span class="enrichment-step-number">${index + 1}</span>
        <span>
          <strong>${escapeHtml(stepTitle)}</strong>
          <small>${escapeHtml(`Ссылка: ${stepId}`)}</small>
        </span>
        <span>${escapeHtml(tool?.description || step.react_call || 'не выбран')}</span>
        <span>${escapeHtml(enrichmentOnErrorLabel(step.on_error))}</span>
        <span class="row-actions">
          <button type="button" data-action="enrichment-step-edit" data-step-index="${index}" ${active ? 'disabled' : ''}>Изменить</button>
          <button class="danger" type="button" data-action="enrichment-step-remove">Удалить</button>
        </span>
      </div>
      ${active ? renderEnrichmentStepEditor(step, index, previousSteps, slotContext, outputRules, tools) : ''}
    </div>
  `;
}

function renderEnrichmentStepEditor(step = {}, index = 0, previousSteps = [], slotContext = { slots: [] }, outputRules = [], tools = []) {
  const tool = findToolInCatalog(tools, step.react_call) || tools[0] || null;
  const reactCall = step.react_call || tool?.tool_name || '';
  const stepId = normalizeEnrichmentStepId(step.step_id, index);
  return `
    <div class="enrichment-step-editor" data-enrichment-step-editor>
      <input type="hidden" data-enrichment-step-id value="${escapeHtml(stepId)}">
      <fieldset class="launch-editor">
        <legend>Инструкция настройки шага</legend>
        <label>Что должен сделать шаг
          <textarea data-enrichment-configuration-instruction rows="5" placeholder="Вызови get_user_login. В параметр user_fio передай слот &quot;Фамилия Имя Отчество&quot;. Если результат не найден, эскалируй оператору.">${escapeHtml(step.configuration_instruction || '')}</textarea>
          <span class="field-help">Помощник настройки сформирует структуру шага. Runtime использует ReAct-вызов, маппинг параметров и LLM-правило ниже, а не свободный текст напрямую.</span>
        </label>
        <input type="hidden" data-enrichment-generated-metadata value="${escapeHtml(jsonPretty(step.generated_structure_metadata || {}))}">
        <div class="scenario-editor-actions">
          <button type="button" data-action="resolution-step-compile">Сформировать структуру шага</button>
          <span class="meta" data-resolution-step-compile-status>Будут обновлены ReAct-вызов и входные параметры активного шага.</span>
        </div>
      </fieldset>
      <details class="launch-editor">
        <summary>Параметры выполнения</summary>
        <div class="grid two enrichment-editor-main">
          <label>Название шага
            <input data-enrichment-step-name value="${escapeHtml(step.step_name || '')}" autocomplete="off" placeholder="Поиск получателя">
          </label>
          <label>ReAct-вызов
            <select data-enrichment-react-call>${toolCatalogOptions(tools, reactCall)}</select>
            <span class="field-help">Привязка к endpoint-операции берется из меню "Вызовы и интеграции".</span>
          </label>
          <label>Действие при ошибке
            <select data-enrichment-on-error>${enrichmentOnErrorOptions(step.on_error || 'continue_to_llm')}</select>
            <span class="field-help">Результат шага доступен ниже по ссылке ${escapeHtml(`\${step.${stepId}.react.${reactCall || '<react_call>'}.output.<field>}`)}.</span>
          </label>
        </div>
        ${renderEnrichmentParameterRows(step, tool, slotContext, outputRules, previousSteps, index)}
      </details>
    </div>
  `;
}

function enrichmentOnErrorOptions(selected) {
  const labels = {
    continue_to_llm: 'продолжить к LLM-правилу',
    stop_and_ask_client: 'остановить и уточнить у клиента',
    escalate_operator: 'эскалировать оператору',
  };
  return ['continue_to_llm', 'stop_and_ask_client', 'escalate_operator']
    .map((value) => `<option value="${value}" ${value === selected ? 'selected' : ''}>${labels[value]}</option>`)
    .join('');
}

function enrichmentOnErrorLabel(value) {
  const labels = {
    continue_to_llm: 'продолжить к LLM-правилу',
    stop_and_ask_client: 'уточнить у клиента',
    escalate_operator: 'эскалировать оператору',
  };
  return labels[value] || value || 'не задано';
}

function renderEnrichmentParameterRows(step, tool, slotContext, outputRules, previousSteps, stepIndex) {
  const mapping = step.parameter_mapping || {};
  const names = tool ? parameterNamesForTool(tool, mapping) : Object.keys(mapping);
  if (!names.length) {
    return '<div class="empty">У выбранного ReAct-вызова нет описанных параметров.</div>';
  }
  return `
    <div class="parameter-binding-list enrichment-param-table" data-enrichment-param-list>
      <div class="parameter-binding-header compact-three">
        <span>Параметр ReAct-вызова</span>
        <span>Тип</span>
        <span>Заполняется из</span>
      </div>
      ${names.map((name) => `
        <div class="parameter-binding-row compact-three" data-enrichment-param-row>
          <input type="hidden" data-enrichment-param-name value="${escapeHtml(name)}">
          <div class="parameter-binding-meta">
            <strong>${escapeHtml(schemaDisplayName(name, parameterSchemaProperties(tool)[name]))}</strong>
            <span>${escapeHtml(name)}</span>
          </div>
          <div class="parameter-binding-meta">
            ${escapeHtml(tool ? schemaMetaLine(name, parameterSchemaProperties(tool)[name], schemaRequired(tool.parameters_schema || {}).includes(name)) : 'параметр ReAct-вызова')}
          </div>
          <div class="enrichment-param-source">
            ${renderEnrichmentSourceControl(
              mapping[name] || defaultEnrichmentParameterSource(name, slotContext),
              slotContext,
              outputRules,
              previousSteps,
              mapping,
              stepIndex,
            )}
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

function renderEnrichmentSourceControl(selected, slotContext, outputRules, previousSteps, mapping, stepIndex) {
  const options = enrichmentSourceOptionObjects(slotContext, outputRules, previousSteps, mapping);
  const knownValues = new Set(options.map((option) => option.value));
  const mode = selected && knownValues.has(selected)
    ? selected
    : selected?.startsWith('constant:')
      ? 'constant:'
      : selected?.startsWith('secret:')
        ? 'secret:'
        : selected
          ? 'custom:'
          : '';
  const customValue = mode === 'constant:' || mode === 'secret:'
    ? selected.slice(mode.length)
    : mode === 'custom:'
      ? selected
      : '';
  return `
    <select data-enrichment-param-source-mode>
      <option value="" ${!mode ? 'selected' : ''}>не использовать</option>
      ${options.map((option) => `<option value="${escapeHtml(option.value)}" ${mode === option.value ? 'selected' : ''}>${escapeHtml(option.label)}</option>`).join('')}
      <option value="constant:" ${mode === 'constant:' ? 'selected' : ''}>Константа</option>
      <option value="secret:" ${mode === 'secret:' ? 'selected' : ''}>Секрет</option>
      ${mode === 'custom:' ? '<option value="custom:" selected>Техническая ссылка</option>' : '<option value="custom:">Техническая ссылка</option>'}
    </select>
    <input data-enrichment-param-source-custom value="${escapeHtml(customValue)}" autocomplete="off" placeholder="значение или ссылка" ${customValue || mode === 'constant:' || mode === 'secret:' || mode === 'custom:' ? '' : 'hidden'}>
  `;
}

function enrichmentSourceOptionObjects(slotContext, outputRules, previousSteps, mapping = {}) {
  const values = new Map();
  const add = (value, label) => {
    if (value && !values.has(value)) {
      values.set(value, label);
    }
  };
  for (const value of Object.values(mapping || {})) {
    if (value && !value.startsWith('constant:') && !value.startsWith('secret:')) {
      add(value, enrichmentSourceLabel(value, slotContext, outputRules, previousSteps));
    }
  }
  for (const slot of slotContext.slots || []) {
    add(`slot:${slot.slot_id}`, `Слот: ${slot.display_name || slot.slot_id}`);
  }
  for (const rule of outputRules || []) {
    if (!rule.slot_id) continue;
    const slot = (slotContext.slots || []).find((item) => item.slot_id === rule.slot_id);
    add(`output:${rule.slot_id}`, `Выходной слот: ${slot?.display_name || rule.slot_id}`);
  }
  for (const step of previousSteps || []) {
    const stepId = normalizeEnrichmentStepId(step.step_id, (previousSteps || []).indexOf(step));
    const reactCall = step.react_call || '';
    const tool = findToolInCatalog(state.lastData.toolCatalog || [], reactCall);
    if (reactCall) {
      for (const parameter of reactParameterNames(tool || {})) {
        add(
          `step:${stepId}.react.${reactCall}.input.${parameter}`,
          `Шаг ${stepId.replace('step', '')}: вход ${reactCall}.${parameter}`,
        );
      }
    }
    for (const field of stepResultFields(step, tool)) {
      if (!field.field_id) continue;
      if (reactCall) {
        add(
          `step:${stepId}.react.${reactCall}.output.${field.field_id}`,
          `Шаг ${stepId.replace('step', '')}: результат ${reactCall}.${field.display_name || field.field_id}`,
        );
      }
    }
  }
  return Array.from(values, ([value, label]) => ({ value, label }));
}

function stepResultFields(step = {}, tool = null) {
  return step.result_fields?.length ? step.result_fields : resultFieldsFromTool(tool);
}

function enrichmentSourceLabel(sourceRef, slotContext, outputRules, previousSteps) {
  if (!sourceRef) return '';
  const { source, value } = parseBindingString(sourceRef);
  if (source === 'slot') {
    const slot = (slotContext.slots || []).find((item) => item.slot_id === value);
    return `Слот: ${slot?.display_name || value}`;
  }
  if (source === 'output') {
    const slot = (slotContext.slots || []).find((item) => item.slot_id === value);
    const known = (outputRules || []).some((rule) => rule.slot_id === value);
    return `${known ? 'Выходной слот' : 'Выходной слот вне списка'}: ${slot?.display_name || value}`;
  }
  if (source === 'step') {
    const match = value.match(/^(step[1-9][0-9]*)\.react\.([a-z][a-z0-9_.-]*)\.(input|output)\.([A-Za-z0-9_][A-Za-z0-9_.-]*)$/);
    if (match) {
      const [, stepId, reactCall, kind, field] = match;
      return `Шаг ${stepId.replace('step', '')}: ${kind === 'input' ? 'вход' : 'результат'} ${reactCall}.${field}`;
    }
  }
  if (source === 'constant') return `Константа: ${value}`;
  if (source === 'secret') return `Секрет: ${value}`;
  return sourceRef;
}

function defaultEnrichmentParameterSource(parameterName, slotContext) {
  return defaultResolverParameterSource(parameterName, slotContext);
}

function renderOperationResultFieldRows(entity) {
  const fields = entity.available_fields?.length
    ? entity.available_fields
    : [{ field_id: '', display_name: '', field_type: 'unknown', description: '' }];
  return `
    <div class="parameter-binding-list" data-resolution-result-field-list>
      <div class="parameter-binding-header resolution-result-field-header">
        <span>Ключ поля</span>
        <span>Название</span>
        <span>Тип</span>
        <span>Описание</span>
        <span></span>
      </div>
      ${fields.map((field) => renderOperationResultFieldRow(field)).join('')}
    </div>
    <button type="button" data-action="resolution-result-field-add">Добавить поле результата</button>
  `;
}

function renderOperationResultFieldRow(field = {}) {
  const typeOptions = resultFieldTypes
    .map((type) => `<option value="${type}" ${type === (field.field_type || 'unknown') ? 'selected' : ''}>${escapeHtml(visibleLabels[type] || type)}</option>`)
    .join('');
  return `
    <div class="parameter-binding-row resolution-result-field-row" data-resolution-result-field-row>
      <label>Ключ поля
        <input data-resolution-result-field-id value="${escapeHtml(field.field_id || '')}" autocomplete="off" placeholder="login">
      </label>
      <label>Название
        <input data-resolution-result-field-name value="${escapeHtml(field.display_name || '')}" autocomplete="off" placeholder="Логин">
      </label>
      <label>Тип
        <select data-resolution-result-field-type>${typeOptions}</select>
      </label>
      <label>Описание
        <input data-resolution-result-field-description value="${escapeHtml(field.description || '')}" autocomplete="off">
      </label>
      <button class="danger" type="button" data-action="resolution-result-field-remove">Удалить</button>
    </div>
  `;
}

function resultFieldsFromTool(tool) {
  const names = reactResultFieldNames(tool || {});
  if (!names.length) {
    return [{ field_id: 'value', display_name: 'Значение', field_type: 'unknown', description: '' }];
  }
  return names.map((name) => {
    const schema = schemaAtPath(tool?.result_schema || {}, name) || {};
    return {
      field_id: name,
      display_name: schema.title || humanizeTechnicalKey(name),
      field_type: schema.type === 'integer' ? 'number' : (schema.type || 'unknown'),
      description: schema.description || '',
    };
  });
}

function renderResolutionOutputRows(rules, slotContext) {
  const rows = rules.length ? rules : [{ slot_id: '', order: 1, required_for_success: true, source_hint: '', fallback: 'ask_clarification' }];
  return `
    <div class="parameter-binding-header resolution-output-header">
      <span>Слот</span>
      <span>Порядок</span>
      <span>Обязателен</span>
      <span>Источник значения</span>
      <span>Если не заполнен</span>
      <span></span>
    </div>
    ${rows.map((rule) => renderResolutionOutputRow(rule, slotContext)).join('')}
  `;
}

function resolutionOutputSlotOptions(slotContext, selectedSlotId) {
  const slots = slotContext.slots || [];
  const selectedExists = slots.some((slot) => slot.slot_id === selectedSlotId);
  const customSelected = !selectedSlotId && !slots.length;
  const options = [
    `<option value="" ${!selectedSlotId && slots.length ? 'selected' : ''}>${slots.length ? 'выберите слот' : 'нет существующих слотов'}</option>`,
    ...slots.map((slot) => `<option value="${escapeHtml(slot.slot_id)}" ${
      slot.slot_id === selectedSlotId ? 'selected' : ''
    }>${escapeHtml(slotOptionLabel(slot, slotContext))}</option>`),
  ];
  if (selectedSlotId && !selectedExists) {
    options.unshift(
      `<option value="${escapeHtml(selectedSlotId)}" selected>${escapeHtml(`Слот пока не найден в выбранной схеме: ${selectedSlotId}`)}</option>`,
    );
  }
  options.push(`<option value="__custom__" ${customSelected ? 'selected' : ''}>Новый слот: указать ключ ниже</option>`);
  return options.join('');
}

function renderResolutionOutputRow(rule = {}, slotContext = { slots: [] }, options = {}) {
  const customSelected = options.customSelected ?? (!rule.slot_id && !(slotContext.slots || []).length);
  const slotOptionsHtml = options.slotOptionsHtml || resolutionOutputSlotOptions(slotContext, rule.slot_id || '');
  const fallbackOptions = [
    ['ask_clarification', 'уточнить у клиента'],
    ['operator_handoff', 'эскалировать оператору'],
    ['leave_empty', 'оставить пустым'],
  ]
    .map(([value, label]) => `<option value="${value}" ${value === (rule.fallback || 'leave_empty') ? 'selected' : ''}>${escapeHtml(label)}</option>`)
    .join('');
  return `
    <div class="parameter-binding-row resolution-output-row" data-resolution-output-row>
      <div class="resolution-output-slot-cell">
        <label>Слот
          <select data-resolution-output-slot>${slotOptionsHtml}</select>
        </label>
        <label data-resolution-output-slot-custom ${customSelected ? '' : 'hidden'}>Ключ нового выходного слота
          <input data-resolution-output-slot-custom-value value="" autocomplete="off" placeholder="user_login">
          <span class="field-help">Используется для первого создания профиля, если выходной слот еще не добавлен в схему слотов.</span>
        </label>
      </div>
      <label>Порядок
        <input data-resolution-output-order type="number" min="1" max="100" value="${escapeHtml(rule.order || 1)}">
      </label>
      <label>Обязателен для успеха
        <select data-resolution-output-required>${booleanOptions(rule.required_for_success ?? false)}</select>
      </label>
      <label>Источник значения
        <input data-resolution-output-source value="${escapeHtml(rule.source_hint || rule.slot_id || '')}" autocomplete="off" placeholder="login">
        <span class="field-help">Поле или путь в результате шага, например login или 0.user_login. Итоговое решение принимает LLM-правило.</span>
      </label>
      <label>Если не заполнен
        <select data-resolution-output-fallback>${fallbackOptions}</select>
      </label>
      <button class="danger" type="button" data-action="resolution-output-remove">Удалить</button>
    </div>
  `;
}

function defaultResolutionResponseContract() {
  return {
    decision: 'fill | ask_clarification | handoff | leave_empty',
    filled_slots: { '<slot_id>': 'string|null' },
    confidence: 'number 0..1',
    next_question: 'string',
    reason: 'short russian explanation',
  };
}

function defaultResolutionScriptText(profile = {}) {
  const outputSlots = profileOutputSlotIds(profile).join(', ') || profile.target_slot_id || 'целевой слот';
  const stepRefs = profileEnrichmentSteps(profile)
    .map((step, index) => {
      const stepId = normalizeEnrichmentStepId(step.step_id, index);
      const reactCall = step.react_call || 'react_call';
      return `${stepId}.react.${reactCall}.output.<field>`;
    })
    .join(', ') || 'нет результатов ReAct-вызовов';
  return [
    'Проанализируй входные слоты и результаты шагов обогащения.',
    `Доступные ссылки на результаты: ${stepRefs}.`,
    `Заполняй только разрешенные выходные слоты: ${outputSlots}.`,
    'Если результат однозначный, верни решение fill и значения слотов.',
    'Если данных недостаточно или результатов несколько, задай один уточняющий вопрос.',
    'Если уверенно решить нельзя после попыток, передай обращение человеку.',
  ].join(' ');
}

function resolutionProfileCreateTemplate(source, profiles) {
  const template = source || profiles[0] || {};
  const targetSlotId = template.target_slot_id || '';
  const outputRules = profileOutputRules(template);
  return {
    profile_id: nextProfileId(template.profile_id || 'profile.custom.attribute', profiles),
	    display_name: '',
	    status: 'active',
	    description: '',
	    slot_schema_id: template.slot_schema_id || '',
	    target_slot_id: targetSlotId,
    enrichment_steps: [],
    output_slots_order: outputRules,
    llm_resolution_script: {
      script_text: template.llm_resolution_script?.script_text || defaultResolutionScriptText(template),
      response_contract: template.llm_resolution_script?.response_contract || defaultResolutionResponseContract(),
    },
    human_resolution_policy: template.human_resolution_policy || {
      clarification_question: 'Уточните данные для заполнения атрибута.',
      clarification_slots: [targetSlotId].filter(Boolean),
      handoff_package: [targetSlotId].filter(Boolean),
      handoff_action: 'operator_handoff',
      fallback_action: 'ask_user',
    },
    fallback: template.fallback || {
      action: 'ask_user',
      question: 'Уточните значение атрибута.',
    },
    confidence_threshold: template.confidence_threshold ?? 0.7,
    confidence_thresholds: template.confidence_thresholds || {
      auto_fill: template.confidence_threshold ?? 0.7,
      clarification: template.confidence_threshold ?? 0.7,
      operator_handoff: 0.5,
    },
    max_attempts: template.max_attempts || 1,
  };
}

function currentResolutionProfileById(profileId) {
  return (state.lastData.resolutionProfiles || [])
    .find((profile) => profile.profile_id === profileId) || null;
}

function currentSlotAutofillProfileById(profileId) {
  return (state.lastData.slotAutofillProfiles || [])
    .find((profile) => profile.profile_id === profileId) || null;
}

function nextProfileId(sourceId, profiles) {
  const existing = new Set((profiles || []).map((profile) => profile.profile_id));
  const base = `${sourceId || 'profile.custom.attribute'}_copy`
    .toLowerCase()
    .replace(/[^a-z0-9_.-]+/g, '_')
    .replace(/^[^a-z]+/, 'profile_');
  let candidate = base;
  let index = 2;
  while (existing.has(candidate)) {
    candidate = `${base}_${index}`;
    index += 1;
  }
  return candidate;
}

function formatScenarioNames(scenarios, scenarioIds) {
  const byId = Object.fromEntries((scenarios || []).map((scenario) => [scenario.scenario_id, scenario.display_name]));
  return (scenarioIds || []).map((scenarioId) => byId[scenarioId] || scenarioId).join(', ') || 'н/д';
}

function referenceOptions(items, idKey, selected, labelKey) {
  return (items || [])
    .map((item) => {
      const value = item[idKey];
      const rawLabel = typeof labelKey === 'function' ? labelKey(item) : item[labelKey];
      const label = rawLabel || humanizeTechnicalKey(value);
      return `<option value="${escapeHtml(value)}" ${value === selected ? 'selected' : ''}>${escapeHtml(label)}</option>`;
    })
    .join('');
}

function multiReferenceOptions(items, idKey, selectedValues, labelKey) {
  const selected = new Set(selectedValues || []);
  return (items || [])
    .map((item) => {
      const value = item[idKey];
      const rawLabel = typeof labelKey === 'function' ? labelKey(item) : item[labelKey];
      const label = rawLabel || humanizeTechnicalKey(value);
      return `<option value="${escapeHtml(value)}" ${selected.has(value) ? 'selected' : ''}>${escapeHtml(label)}</option>`;
    })
    .join('');
}

function scenarioDisplayName(scenarios, scenarioId) {
  return (scenarios || []).find((scenario) => scenario.scenario_id === scenarioId)?.display_name || 'Выбранный сценарий';
}

function promptPackLabel(promptPack) {
  return String(promptPack?.display_name || 'Пакет промптов').replace(/^Prompt pack:/i, 'Пакет промптов:');
}

function promptPackCreateTemplate(source, packs, scenarios) {
  const template = source || packs[0] || {};
  return {
    prompt_pack_id: nextPromptPackId(template.prompt_pack_id || 'prompt.custom', packs),
    display_name: '',
    status: 'draft',
    active_version: 'v1',
    blocks: template.blocks || defaultPromptBlocks(),
  };
}

function defaultPromptBlocks() {
  return {
    role_context: 'Опишите роль агента и границы ответственности.',
    behavior_principles: 'Опишите принципы поведения агента.',
    slot_schemas: 'Опишите, как агент должен работать со слотами сценария.',
    classification_confidence: 'Опишите правила классификации и пороги confidence.',
    react_planning: 'Опишите правила ReAct-планирования и стоп-условия.',
    tool_rules: 'Опишите правила выбора и выполнения ReAct-вызовов ИИ.',
    escalation_response: 'Опишите условия эскалации и формат ответа клиенту.',
  };
}

function nextPromptPackId(sourceId, packs) {
  const existing = new Set((packs || []).map((pack) => pack.prompt_pack_id));
  const base = `${sourceId || 'prompt.custom'}_copy`
    .toLowerCase()
    .replace(/[^a-z0-9_.-]+/g, '_')
    .replace(/^[^a-z]+/, 'prompt_');
  let candidate = base;
  let index = 2;
  while (existing.has(candidate)) {
    candidate = `${base}_${index}`;
    index += 1;
  }
  return candidate;
}

function humanizeTechnicalKey(value) {
  const tail = String(value || '').split('.').pop() || 'элемент';
  return tail.replace(/[_-]+/g, ' ');
}

function scenarioCreateTemplate(source, serviceScenarios) {
  const template = source || serviceScenarios[0] || {};
  return {
    scenario_id: nextScenarioId(template.scenario_id || 'custom_scenario', serviceScenarios),
    display_name: '',
    status: 'draft',
    description: '',
    slot_schema_id: template.slot_schema_id || '',
    classification_route_id: template.classification_route_id || '',
    orchestrator_policy_id: template.orchestrator_policy_id || '',
    tool_launch_matrix_id: template.tool_launch_matrix_id || '',
    prompt_pack_id: template.prompt_pack_id || '',
    escalation_policy_id: template.escalation_policy_id || '',
    default_channel_id: template.default_channel_id || 'debug',
    allowed_channel_ids: template.allowed_channel_ids || ['messenger_bot', 'service_desk', 'debug'],
    audit_required: template.audit_required ?? true,
    log_required: template.log_required ?? true,
    tags: template.tags || [],
  };
}

function nextScenarioId(sourceId, scenarios) {
  const existing = new Set((scenarios || []).map((scenario) => scenario.scenario_id));
  const base = `${sourceId || 'custom_scenario'}_copy`
    .toLowerCase()
    .replace(/[^a-z0-9_.-]+/g, '_')
    .replace(/^[^a-z]+/, 'scenario_');
  let candidate = base;
  let index = 2;
  while (existing.has(candidate)) {
    candidate = `${base}_${index}`;
    index += 1;
  }
  return candidate;
}

function slotSchemaCreateTemplate(source, slotSchemas) {
  const template = source || slotSchemas[0] || {};
  return {
    slot_schema_id: nextConfigItemId(template.slot_schema_id || 'slot.custom', slotSchemas, 'slot_schema_id'),
    display_name: '',
    required_slots: template.required_slots || [],
    auto_fill_slots: template.auto_fill_slots || [],
    question_order: template.question_order || [],
    slots: template.slots || [
      {
        slot_id: 'user_login',
        display_name: 'Логин пользователя',
        priority_group: 'who',
        required: true,
        fill_method: 'user_question',
        user_question: 'Уточните логин пользователя.',
      },
    ],
  };
}

function nextConfigItemId(sourceId, items, idKey) {
  const existing = new Set((items || []).map((item) => item[idKey]));
  const base = `${sourceId || 'custom.item'}_copy`
    .toLowerCase()
    .replace(/[^a-z0-9_.-]+/g, '_')
    .replace(/^[^a-z]+/, 'item_');
  let candidate = base;
  let index = 2;
  while (existing.has(candidate)) {
    candidate = `${base}_${index}`;
    index += 1;
  }
  return candidate;
}

function renderSlotSchemaEditor({ slotSchema, slotSchemas, scenarios, resolutionProfiles = [], confidenceDefaults = {} }) {
  if (state.slotSchemaOperation === 'delete') {
    if (!slotSchema) {
      return '<div class="empty">Нет выбранной схемы для удаления</div>';
    }
    return `
      <form class="scenario-editor panel" data-form="slot-schema-delete">
        <div>
          <div class="metric-label">Удаляемая схема слотов</div>
          <div class="scenario-title">${escapeHtml(slotSchema.display_name)}</div>
        </div>
        ${usagePanel(scenarios, 'slot_schema_id', slotSchema.slot_schema_id)}
        <button class="danger" type="submit">Удалить схему слотов</button>
      </form>
    `;
  }
  const current = state.slotSchemaOperation === 'create'
    ? slotSchemaCreateTemplate(slotSchema, slotSchemas)
    : slotSchema;
  if (!current) {
    return '<div class="empty">Схема слотов не выбрана</div>';
  }
  const cards = (current.slots || [])
    .map((slot, index) => renderSlotCard(slot, index + 1, false, resolutionProfiles, confidenceDefaults))
    .join('');
  return `
    <form class="scenario-editor panel" data-form="slot-schema-editor">
      <input type="hidden" name="slot_schema_id" value="${escapeHtml(current.slot_schema_id)}">
      <label>Название<input name="display_name" value="${escapeHtml(current.display_name)}" autocomplete="off"></label>
      <div class="slot-schema-derived">
        <div class="metric-label">Где выбрать профиль разрешения атрибута</div>
        <div class="meta">
          Раскройте карточку нужного слота. В поле "Как получить значение слота" выберите "профиль разрешения",
          затем в поле "Профиль разрешения атрибута" выберите готовый профиль. В сценарии напрямую профиль не выбирается:
          сценарий выбирает схему слотов, а схема слотов уже содержит связь слота с профилем.
        </div>
      </div>
      <div id="slotCards" class="slot-card-list">${cards}</div>
      <button type="button" data-action="slot-add">Добавить слот</button>
      ${usagePanel(scenarios, 'slot_schema_id', current.slot_schema_id)}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">${state.slotSchemaOperation === 'create' ? 'Создать схему слотов' : 'Сохранить слоты'}</button>
      </div>
    </form>
  `;
}

function renderSlotCard(slot = {}, order = '', open = false, resolutionProfiles = [], confidenceDefaults = {}) {
  const required = slot.required === true;
  const fillMethod = slot.fill_method || legacyFillMethod(slot.source);
  const priorityGroup = slot.priority_group || 'what';
  const title = slot.display_name || slot.slot_id || 'Новый слот';
  const keyLabel = slot.slot_id || 'Ключ не задан';
  const requiredLabel = required ? 'обязательный' : 'необязательный';
  const profile = resolutionProfiles.find((item) => item.profile_id === slot.resolution_profile_id);
  const methodLabel = profile?.display_name || visibleLabels[fillMethod] || fillMethod;
  const slotConfidenceSummary = hasConfidenceOverrides(slot.confidence_overrides || {})
    ? 'Пороги извлечения моделью: включено переопределение'
    : 'Пороги извлечения моделью: используются системные';
  const profileHint = profile
    ? `<div class="slot-schema-derived">
        <div class="metric-label">Выбранный профиль разрешения</div>
        <div class="meta">
          ${escapeHtml(profile.display_name)}. Целевой слот: ${escapeHtml(profile.target_slot_id || 'н/д')}.
          Выходы: ${escapeHtml(formatList(profileOutputSlotIds(profile)))}.
          Вопрос при неоднозначности: ${escapeHtml(profile.human_resolution_policy?.clarification_question || profile.fallback?.question || 'н/д')}.
        </div>
      </div>`
    : `<div class="slot-schema-derived">
        <div class="metric-label">Профиль разрешения не выбран</div>
        <div class="meta">Если готового профиля еще нет, оставьте поле профиля пустым и сохраните слот: система создаст черновик профиля для этого слота. Затем настройте его в меню "1. Разрешение атрибутов".</div>
      </div>`;
  const openAttribute = open ? ' open' : '';
  return `
    <details class="slot-card" data-slot-card${openAttribute}>
      <summary class="slot-card-summary">
        <div class="slot-card-summary-main">
          <strong>${escapeHtml(title)}</strong>
          <span>${escapeHtml(keyLabel)} · ${escapeHtml(priorityGroup)} · ${escapeHtml(methodLabel)} · ${escapeHtml(requiredLabel)}</span>
        </div>
        <button class="danger slot-delete-button" type="button" data-action="slot-remove">Удалить</button>
      </summary>
      <div class="slot-card-body">
        <div class="slot-card-note">
          <div class="metric-label">Составляющая схемы слотов</div>
          <div class="meta">Описывает одно поле, которое агент должен получить, заполнить автоматически или вывести из контекста.</div>
        </div>
        <div class="grid two">
          <label>Ключ слота
            <input name="slot_id" value="${escapeHtml(slot.slot_id || '')}" autocomplete="off" placeholder="user_login">
            <span class="field-help">Технический ключ поля. Используется в матрице ReAct-вызовов и prompt pack. Формат: латиница, цифры, _, -, .</span>
          </label>
          <label>Название
            <input name="display_name" value="${escapeHtml(slot.display_name || '')}" autocomplete="off" placeholder="Логин пользователя">
            <span class="field-help">Человекочитаемая подпись для администратора и оператора.</span>
          </label>
          <label>Priority group
            <select name="priority_group">${slotPriorityOptions(priorityGroup)}</select>
            <span class="field-help">Приоритет вопроса: who - кто, what - что, when - когда, where - где, context - служебный контекст.</span>
          </label>
          <label>Обязательный
            <select name="required">${booleanOptions(required)}</select>
            <span class="field-help">Если да, без значения этого слота сценарий не должен переходить к выполнению.</span>
          </label>
          <label>Как получить значение слота
            <select name="fill_method" data-slot-fill-method>${fillMethodOptions(fillMethod)}</select>
            <span class="field-help">Выберите, откуда платформа берет значение слота.</span>
            <span class="field-help" data-fill-method-help>${escapeHtml(fillMethodHelpText(fillMethod))}</span>
          </label>
        </div>
        <div class="slot-method-section" data-fill-method-section="user_question">
          <label>Вопрос клиенту
            <textarea name="user_question" rows="3" placeholder="Уточните логин пользователя.">${escapeHtml(slot.user_question || slot.question || '')}</textarea>
            <span class="field-help">Текст вопроса, который будет отправлен клиенту или показан оператору канала для ввода ответа клиента.</span>
          </label>
        </div>
        <div class="slot-method-section" data-fill-method-section="case">
          <label>Путь в данных обращения
            <input name="case_source_ref" value="${escapeHtml(slot.case_source_ref || slot.auto_fill_ref || '')}" autocomplete="off" placeholder="requester.login">
            <span class="field-help">Например: requester.login, requester.email, channel.user_id, ticket.id, ticket.sla.deadline, context.device_name. Внешние системы здесь не вызываются.</span>
          </label>
        </div>
        <div class="slot-method-section" data-fill-method-section="llm_extraction">
          <label>Инструкция для модели
            <textarea name="extraction_instruction" rows="3" placeholder="Извлеки ФИО сотрудника, которому нужно сбросить пароль.">${escapeHtml(slot.extraction_instruction || slot.question || '')}</textarea>
            <span class="field-help">Что именно модель должна извлечь из текста обращения и уже собранного контекста. Значение нельзя выдумывать.</span>
          </label>
          <label>Примеры для модели
            <textarea name="examples" rows="3" placeholder="Нужен сброс пароля Иванову Ивану Ивановичу">${escapeHtml((slot.examples || []).join('\n'))}</textarea>
            <span class="field-help">Необязательные примеры, по одному на строку.</span>
          </label>
        </div>
        <div class="slot-method-section" data-fill-method-section="slot_autofill">
          <div class="slot-schema-derived">
            <div class="metric-label">ReAct-автозаполнение</div>
            <div class="meta">Связь с ReAct-вызовом и полем результата настраивается в меню "Сценарии обработки -> 0.1 Автозаполнение слотов". Runtime сам не создает слоты, он только заполняет уже активированную схему.</div>
          </div>
          <label>Источник автозаполнения
            <input name="autofill_source_ref" value="${escapeHtml(slot.autofill_source_ref || '')}" autocomplete="off" placeholder="autofill.profile:users.0.login">
            <span class="field-help">Служебная подсказка для администратора. На выполнение влияет профиль автозаполнения, а не это поле.</span>
          </label>
        </div>
        <div class="slot-method-section" data-fill-method-section="resolution_profile">
          ${profileHint}
          <label>Профиль разрешения атрибута
            <select name="resolution_profile_id">${resolutionProfileOptions(resolutionProfiles, slot.resolution_profile_id, slot.slot_id)}</select>
            <span class="field-help">Профиль задает порядок извлечения моделью, endpoint-операций чтения и уточняющих вопросов.</span>
          </label>
          <label>Запасной вопрос
            <textarea name="fallback_question" rows="3" placeholder="Уточните ФИО, должность или табельный номер пользователя.">${escapeHtml(slot.fallback_question || slot.question || '')}</textarea>
            <span class="field-help">Используется, если профиль не смог однозначно заполнить слот и не вернул свой вопрос.</span>
          </label>
        </div>
        <div class="slot-method-section" data-fill-method-section="operator_manual">
          <label>Подсказка оператору
            <textarea name="operator_hint" rows="3" placeholder="Проверьте значение вручную и заполните слот.">${escapeHtml(slot.operator_hint || slot.question || '')}</textarea>
            <span class="field-help">Инструкция оператору, когда значение не должно заполняться автоматически.</span>
          </label>
        </div>
        <div class="slot-method-section" data-fill-method-order>
          <div class="grid two">
          <label>Порядок вопроса
            <input name="question_order" type="number" min="1" max="999" value="${escapeHtml(order || '')}">
            <span class="field-help">Позиция в очереди обогащения. Учитывается для вопросов клиенту, профилей разрешения и ручного заполнения оператором.</span>
          </label>
          </div>
        </div>
        <details class="slot-method-section" data-fill-method-advanced="llm_extraction" ${fillMethod === 'llm_extraction' ? '' : 'hidden'}>
          <summary>${escapeHtml(slotConfidenceSummary)}</summary>
          <div class="meta">Обычно используются системные пороги из "6. Промпты". Меняйте только для исключений конкретного слота.</div>
          ${renderConfidenceOverrideControls({
            prefix: 'slot_confidence',
            overrides: slot.confidence_overrides || {},
            baseThresholds: confidenceDefaults,
            enabledText: 'Слот использует собственные пороги для LLM-извлечения.',
            disabledText: 'Переопределение выключено. Сейчас используются системные настройки из "6. Промпты".',
          })}
        </details>
      </div>
    </details>
  `;
}

function slotPriorityOptions(selected) {
  const labels = {
    who: 'who / кто',
    what: 'what / что',
    when: 'when / когда',
    where: 'where / где',
    context: 'context / контекст',
  };
  return ['who', 'what', 'when', 'where', 'context']
    .map((value) => `<option value="${value}" ${value === selected ? 'selected' : ''}>${labels[value]}</option>`)
    .join('');
}

function legacyFillMethod(source) {
  const mapping = {
    user_question: 'user_question',
    case: 'case',
    llm: 'llm_extraction',
  };
  if (!source) return 'user_question';
  return mapping[source] || 'resolution_profile';
}

function fillMethodOptions(selected) {
  const values = ['user_question', 'llm_extraction', 'slot_autofill', 'resolution_profile', 'operator_manual'];
  return activeOptionList(values, selected);
}

function fillMethodHelpText(method) {
  const help = {
    user_question: 'Платформа задает вопрос клиенту или показывает его оператору канала для ввода ответа клиента.',
    case: 'Значение уже есть в текущем обращении: канал, карточка заявки, сохраненный контекст или системные поля. Внешние системы здесь не вызываются.',
    llm_extraction: 'Модель извлекает значение из текста обращения и уже собранного контекста без вызова внешних систем.',
    slot_autofill: 'Read-only ReAct-вызов детерминированно заполняет один или несколько слотов по настроенному профилю автозаполнения.',
    resolution_profile: 'Используется отдельный профиль с извлечением моделью, endpoint-операцией чтения, LLM-правилом и уточняющими вопросами.',
    operator_manual: 'Значение вносит оператор вручную; агент не пытается получить его автоматически.',
  };
  return help[method] || 'Выберите способ получения значения слота.';
}

const confidenceThresholdFields = [
  {
    key: 'auto_accept_confidence',
    label: 'Автопринятие от',
    help: 'Начиная с этого confidence значение можно принимать автоматически.',
  },
  {
    key: 'clarification_confidence',
    label: 'Уточнение ниже',
    help: 'Ниже этого confidence нужно задавать уточняющий вопрос.',
  },
  {
    key: 'operator_handoff_confidence',
    label: 'Оператор ниже',
    help: 'Ниже этого confidence значение передается оператору.',
  },
  {
    key: 'min_extraction_confidence',
    label: 'Минимум извлечения',
    help: 'Ниже этого confidence результат извлечения моделью не считается заполненным слотом.',
  },
];

function renderConfidenceThresholdInputs(prefix, thresholds = {}, { required = false, disabled = false } = {}) {
  return `
    <div class="grid two">
      ${confidenceThresholdFields.map((field) => `
        <label>${escapeHtml(field.label)}
          <input data-confidence-input name="${escapeHtml(`${prefix}_${field.key}`)}" type="number" min="0" max="1" step="0.01" value="${escapeHtml(thresholds?.[field.key] ?? '')}" ${required ? 'required' : ''} ${disabled ? 'disabled' : ''}>
          <span class="field-help">${escapeHtml(field.help)}</span>
        </label>
      `).join('')}
    </div>
  `;
}

function hasConfidenceOverrides(thresholds = {}) {
  return confidenceThresholdFields.some((field) => thresholds?.[field.key] !== undefined && thresholds?.[field.key] !== null && thresholds?.[field.key] !== '');
}

function mergeConfidenceThresholds(baseThresholds = {}, overrides = {}) {
  const result = {};
  for (const field of confidenceThresholdFields) {
    const override = overrides?.[field.key];
    const base = baseThresholds?.[field.key];
    result[field.key] = override ?? base ?? '';
  }
  return result;
}

function renderConfidenceOverrideControls({
  prefix,
  overrides = {},
  baseThresholds = {},
  enabledText,
  disabledText,
}) {
  const enabled = hasConfidenceOverrides(overrides);
  const values = mergeConfidenceThresholds(baseThresholds, enabled ? overrides : {});
  return `
    <div class="confidence-override" data-confidence-override>
      <label class="boolean-flag">
        <span>Включить</span>
        <input type="hidden" name="${escapeHtml(`${prefix}_enabled`)}" value="false">
        <input data-confidence-override-enabled name="${escapeHtml(`${prefix}_enabled`)}" type="checkbox" value="true" ${enabled ? 'checked' : ''}>
      </label>
      <div class="meta" data-confidence-override-meta data-enabled-text="${escapeHtml(enabledText)}" data-disabled-text="${escapeHtml(disabledText)}">${escapeHtml(enabled ? enabledText : disabledText)}</div>
      ${renderConfidenceThresholdInputs(prefix, values, { required: enabled, disabled: !enabled })}
    </div>
  `;
}

function syncConfidenceOverrideBlock(block) {
  if (!block) return;
  const enabled = block.querySelector('[data-confidence-override-enabled]')?.checked === true;
  block.querySelectorAll('[data-confidence-input]').forEach((input) => {
    input.disabled = !enabled;
    input.required = enabled;
  });
  const meta = block.querySelector('[data-confidence-override-meta]');
  if (meta) {
    meta.textContent = enabled ? meta.dataset.enabledText : meta.dataset.disabledText;
  }
}

function parseConfidenceThresholdsFromForm(data, prefix, { required = false } = {}) {
  const enabledValues = data.getAll(`${prefix}_enabled`).map((value) => String(value));
  if (!required && enabledValues.length && !enabledValues.includes('true')) {
    return {};
  }
  const result = {};
  for (const field of confidenceThresholdFields) {
    const raw = String(data.get(`${prefix}_${field.key}`) ?? '').trim();
    if (!raw) {
      if (required) {
        throw new Error(`Заполните порог "${field.label}".`);
      }
      continue;
    }
    result[field.key] = Number(raw);
  }
  return result;
}

function parseConfidenceThresholdsFromCard(card, prefix) {
  const toggle = card.querySelector(`[data-confidence-override-enabled][name="${prefix}_enabled"]`);
  if (toggle && toggle.checked !== true) {
    return {};
  }
  const result = {};
  for (const field of confidenceThresholdFields) {
    const raw = card.querySelector(`[name="${prefix}_${field.key}"]`)?.value?.trim() || '';
    if (raw) {
      result[field.key] = Number(raw);
    }
  }
  return result;
}

function resolutionProfileOptions(profiles, selected, slotId) {
  const options = ['<option value="">не выбран</option>'];
  const filtered = (profiles || []).filter((profile) => {
    const slotAllowed = !slotId || profileOutputSlotIds(profile).includes(slotId) || selected === profile.profile_id;
    return slotAllowed;
  });
  for (const profile of filtered) {
    options.push(
      `<option value="${escapeHtml(profile.profile_id)}" ${profile.profile_id === selected ? 'selected' : ''}>${escapeHtml(profile.display_name)}</option>`,
    );
  }
  return options.join('');
}

function routeCreateTemplate(source, routes) {
  const template = source || routes[0] || {};
  return {
    route_id: nextConfigItemId(template.route_id || 'route.custom', routes, 'route_id'),
    display_name: '',
    priority: template.priority || 'P3',
    route: template.route || 'agent_with_confirmation',
    action: template.action || '',
    workflow_state_id: template.workflow_state_id || 'pending_approval',
    confidence: template.confidence || {
      rules_min: 0.85,
      llm_min: 0.7,
      human_handoff_below: 0.5,
    },
    rules: template.rules || {
      rule_items: [defaultClassificationRule()],
    },
    top_categories_on_low_confidence: template.top_categories_on_low_confidence || 3,
  };
}

function renderRouteEditor({ route, routes, scenarios }) {
  if (state.routeOperation === 'delete') {
    if (!route?.route_id) {
      return '<div class="empty">Нет выбранного маршрута для удаления</div>';
    }
    return `
      <form class="scenario-editor panel" data-form="route-delete">
        <div>
          <div class="metric-label">Удаляемый маршрут</div>
          <div class="scenario-title">${escapeHtml(route.display_name)}</div>
        </div>
        ${usagePanel(scenarios, 'classification_route_id', route.route_id)}
        <button class="danger" type="submit">Удалить маршрут</button>
      </form>
    `;
  }
  const current = state.routeOperation === 'create'
    ? routeCreateTemplate(route, routes)
    : route;
  if (!current?.route_id) {
    return '<div class="empty">Маршрут классификации не выбран</div>';
  }
  return `
    <form class="scenario-editor panel" data-form="route-editor">
      <input type="hidden" name="route_id" value="${escapeHtml(current.route_id)}">
      <label>Название<input name="display_name" value="${escapeHtml(current.display_name || '')}" autocomplete="off"></label>
      <div class="grid two">
        <label>Приоритет<select name="priority">${optionList(['P1', 'P2', 'P3', 'P4'], current.priority)}</select></label>
        <label>Решение маршрутизации<select name="route">${optionList(['auto_agent', 'agent_with_confirmation', 'human_review', 'major_incident', 'approver'], current.route)}</select></label>
        <label>Состояние workflow<input name="workflow_state_id" value="${escapeHtml(current.workflow_state_id || '')}" autocomplete="off"></label>
        <label>До N категорий при низкой уверенности
          <input name="top_categories_on_low_confidence" type="number" min="1" max="5" value="${escapeHtml(current.top_categories_on_low_confidence || 3)}">
          <span class="field-help">Сколько вариантов показать оператору. Если маршрутов меньше, будут показаны все доступные.</span>
        </label>
        <label>Порог правил<input name="rules_min" type="number" min="0" max="1" step="0.01" value="${escapeHtml(current.confidence?.rules_min ?? 0.85)}"></label>
        <label>Порог LLM<input name="llm_min" type="number" min="0" max="1" step="0.01" value="${escapeHtml(current.confidence?.llm_min ?? 0.7)}"></label>
        <label>Человек ниже<input name="human_handoff_below" type="number" min="0" max="1" step="0.01" value="${escapeHtml(current.confidence?.human_handoff_below ?? 0.5)}"></label>
      </div>
      <label>Действие<textarea name="action" rows="3">${escapeHtml(current.action || '')}</textarea></label>
      ${renderClassificationRules(current)}
      ${usagePanel(scenarios, 'classification_route_id', current.route_id)}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">${state.routeOperation === 'create' ? 'Создать маршрут' : 'Сохранить классификацию'}</button>
      </div>
    </form>
  `;
}

function policyCreateTemplate(source, policies) {
  const template = source || policies[0] || {};
  return {
    policy_id: nextConfigItemId(template.policy_id || 'policy.custom', policies, 'policy_id'),
    display_name: '',
    max_iterations: template.max_iterations || 6,
    consecutive_tool_errors_to_escalate: template.consecutive_tool_errors_to_escalate || 2,
    stop_conditions: template.stop_conditions || [
      'all_required_slots_filled',
      'tool_success',
      'clarification_required',
      'handoff_required',
      'iteration_limit',
      'consecutive_tool_errors',
    ],
    allowed_react_action_groups: template.allowed_react_action_groups || [
      'read_diagnostics',
      'knowledge_search',
      'external_status_check',
      'action_preparation',
      'state_changing_actions',
      'communication_handoff',
    ],
  };
}

function renderPolicyEditor({ policy, policies, scenarios }) {
  if (state.policyOperation === 'delete') {
    if (!policy?.policy_id) {
      return '<div class="empty">Нет выбранной ReAct-политики для удаления</div>';
    }
    return `
      <form class="scenario-editor panel" data-form="policy-delete">
        <div>
          <div class="metric-label">Удаляемая ReAct-политика</div>
          <div class="scenario-title">${escapeHtml(policy.display_name)}</div>
        </div>
        ${usagePanel(scenarios, 'orchestrator_policy_id', policy.policy_id)}
        <button class="danger" type="submit">Удалить ReAct-политику</button>
      </form>
    `;
  }
  const current = state.policyOperation === 'create'
    ? policyCreateTemplate(policy, policies)
    : policy;
  if (!current?.policy_id) {
    return '<div class="empty">Политика оркестратора не выбрана</div>';
  }
  return `
    <form class="scenario-editor panel" data-form="policy-editor">
      <input type="hidden" name="policy_id" value="${escapeHtml(current.policy_id)}">
      <label>Название<input name="display_name" value="${escapeHtml(current.display_name || '')}" autocomplete="off"></label>
      <div class="grid two">
        <label>Лимит итераций<input name="max_iterations" type="number" min="1" max="20" value="${escapeHtml(current.max_iterations || 6)}"></label>
        <label>Ошибок ReAct-вызовов подряд до эскалации<input name="consecutive_tool_errors_to_escalate" type="number" min="1" max="10" value="${escapeHtml(current.consecutive_tool_errors_to_escalate || 2)}"></label>
      </div>
      <fieldset class="launch-editor">
        <legend>Разрешенные группы действий ReAct</legend>
        <div class="meta">Верхнеуровневые рамки планирования. Конкретные ReAct-вызовы ИИ и режим запуска задаются в блоке "4. ReAct-вызовы и матрица запуска".</div>
        ${renderChoiceChecklist('allowed_react_action_groups', reactActionGroupChoices, current.allowed_react_action_groups || [])}
      </fieldset>
      <fieldset class="launch-editor">
        <legend>Стоп-условия</legend>
        <div class="meta">Когда ReAct-loop должен остановиться и перейти к уточнению у клиента, результату или эскалации оператору.</div>
        ${renderChoiceChecklist('stop_conditions', reactStopConditionChoices, current.stop_conditions || [])}
      </fieldset>
      ${usagePanel(scenarios, 'orchestrator_policy_id', current.policy_id)}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">${state.policyOperation === 'create' ? 'Создать ReAct-политику' : 'Сохранить ReAct-политику'}</button>
      </div>
    </form>
  `;
}

function toolMatrixCreateTemplate(source, matrices) {
  const template = source || matrices[0] || {};
  return {
    matrix_id: nextConfigItemId(template.matrix_id || 'matrix.custom', matrices, 'matrix_id'),
    display_name: '',
    launches: template.launches || [
      {
        launch_id: 'launch.custom.tool',
        tool_name: 'check_zabbix_status',
        required_slots: [],
        parameter_bindings: {
          query: 'context:query',
        },
        execution_level: 'auto',
        target_execution_level: 'auto',
        endpoint_id: 'mock',
        operation_id: 'check_zabbix_status',
        risk_level: 'low',
        stop_on_error: true,
        completion_policy: {
          mode: 'sync',
          max_wait_seconds: 0,
          timeout_action: 'resume_agent',
        },
      },
    ],
  };
}

function selectOptions(options, selected, emptyLabel = 'Нет доступных значений') {
  const seen = new Set();
  const normalized = (options || [])
    .filter((option) => option?.value)
    .filter((option) => {
      if (seen.has(option.value)) return false;
      seen.add(option.value);
      return true;
    });
  if (selected && !seen.has(selected)) {
    normalized.unshift({
      value: selected,
      label: `Текущее значение вне каталога: ${selected}`,
    });
  }
  if (!normalized.length) {
    return `<option value="">${escapeHtml(emptyLabel)}</option>`;
  }
  return normalized
    .map(
      (option) => `<option value="${escapeHtml(option.value)}" ${
        option.value === selected ? 'selected' : ''
      }>${escapeHtml(option.label || option.value)}</option>`,
    )
    .join('');
}

function renderLaunchGroup(title, help, body, attrs = '') {
  return `
    <div class="launch-group" ${attrs}>
      <div class="launch-group-head">
        <div class="metric-label">${escapeHtml(title)}</div>
        <div class="meta">${escapeHtml(help)}</div>
      </div>
      ${body}
    </div>
  `;
}

function findToolInCatalog(tools, toolName) {
  return (tools || []).find((tool) => tool.tool_name === toolName) || null;
}

function toolCatalogOptions(tools, selectedToolName) {
  const selected = findToolInCatalog(tools, selectedToolName)?.tool_name
    || selectedToolName
    || (tools || [])[0]?.tool_name
    || '';
  return selectOptions(
    (tools || []).map((tool) => ({
      value: tool.tool_name,
      label: tool.description ? `${tool.tool_name} — ${tool.description}` : tool.tool_name,
    })),
    selected,
    'Каталог ReAct-вызовов пуст',
  );
}

function referenceHelperSlotItems(slots = []) {
  return (slots || []).map((slot) => ({
    token: `\${slot.${slot.slot_id}}`,
    label: slot.display_name ? `${slot.display_name} (${slot.slot_id})` : slot.slot_id,
    detail: slotOptionLabel(slot, { scenarioCount: 1 }),
  }));
}

function referenceHelperReactItems(tools = []) {
  return (tools || []).map((tool) => ({
    token: `\${ReAct.${tool.tool_name}}`,
    label: tool.description ? `${tool.tool_name} — ${tool.description}` : tool.tool_name,
    detail: tool.display_name || tool.description || tool.tool_name,
  }));
}

function referenceHelperParameterItems(tool, kind) {
  if (!tool?.tool_name) return [];
  const names = kind === 'input' ? reactParameterNames(tool) : reactResultFieldNames(tool);
  const properties = kind === 'input' ? schemaProperties(tool.parameters_schema || {}) : schemaProperties(tool.result_schema || {});
  return names.map((name) => {
    const schema = kind === 'input' ? (properties[name] || {}) : (schemaAtPath(tool.result_schema || {}, name) || {});
    const prefix = `paramReAct.${tool.tool_name}.${kind}`;
    return {
      token: `\${${prefix}.${name}}`,
      label: schema.title ? `${schema.title} (${name})` : name,
      detail: `${tool.tool_name}: ${schema.description || schema.title || name}`,
    };
  });
}

function referenceHelperStepItems(previousSteps = []) {
  const items = [];
  for (const [index, step] of (previousSteps || []).entries()) {
    const stepId = normalizeEnrichmentStepId(step.step_id, index);
    const reactCall = step.react_call || '';
    if (!reactCall) continue;
    const tool = findToolInCatalog(state.lastData.toolCatalog || [], reactCall);
    for (const parameter of reactParameterNames(tool || {})) {
      items.push({
        token: `\${step.${stepId}.react.${reactCall}.input.${parameter}}`,
        label: `Шаг ${index + 1}: вход ${reactCall}.${parameter}`,
        detail: step.step_name || reactCall,
      });
    }
    for (const field of stepResultFields(step, tool)) {
      if (!field.field_id) continue;
      items.push({
        token: `\${step.${stepId}.react.${reactCall}.output.${field.field_id}}`,
        label: `Шаг ${index + 1}: результат ${reactCall}.${field.field_id}`,
        detail: field.description || field.display_name || step.step_name || reactCall,
      });
    }
  }
  return items;
}

function isReferenceAutocompleteTextarea(target) {
  return target?.matches?.(
    [
      '[data-slot-autofill-instruction]',
      '[data-enrichment-configuration-instruction]',
      '[name="llm_resolution_script_text"]',
    ].join(','),
  );
}

function referenceAutocompleteGroup(title, items) {
  return (items || []).map((item) => ({ ...item, group: title }));
}

function referenceAutocompleteItems({ slots = [], tools = [], selectedTool = null, previousSteps = [] } = {}) {
  const selected = selectedTool?.tool_name ? selectedTool : null;
  const parameterTools = selected ? [selected] : (tools || []);
  return [
    ...referenceAutocompleteGroup('Слоты', referenceHelperSlotItems(slots)),
    ...referenceAutocompleteGroup('ReAct-вызовы', referenceHelperReactItems(tools)),
    ...referenceAutocompleteGroup('Входные параметры', parameterTools.flatMap((tool) => referenceHelperParameterItems(tool, 'input'))),
    ...referenceAutocompleteGroup('Поля результата', parameterTools.flatMap((tool) => referenceHelperParameterItems(tool, 'output'))),
    ...referenceAutocompleteGroup('Параметры шагов', referenceHelperStepItems(previousSteps)),
  ];
}

function safeEnrichmentStepFromCard(card, index = 0) {
  if (!card.querySelector('[data-enrichment-step-editor]')) {
    try {
      return JSON.parse(card.querySelector('[data-enrichment-step-json]')?.value || '{}');
    } catch {
      return {};
    }
  }
  const reactCall = card.querySelector('[data-enrichment-react-call]')?.value?.trim() || '';
  return {
    step_id: card.querySelector('[data-enrichment-step-id]')?.value?.trim() || normalizeEnrichmentStepId('', index),
    step_name: card.querySelector('[data-enrichment-step-name]')?.value?.trim() || `Шаг ${index + 1}`,
    react_call: reactCall,
  };
}

function safeEnrichmentStepsFromForm(form, limit = Infinity) {
  return Array.from(form?.querySelectorAll('[data-enrichment-step-card]') || [])
    .slice(0, limit)
    .map((card, index) => safeEnrichmentStepFromCard(card, index))
    .filter((step) => step && (step.react_call || step.result_fields?.length));
}

function referenceAutocompleteContextForTextarea(textarea) {
  const form = textarea.closest('form');
  if (!form) return null;
  if (textarea.matches('[data-slot-autofill-instruction]')) {
    const schemaId = form.querySelector('[name="slot_schema_id"]')?.value || '';
    const slotSchema = (state.lastData.slotSchemas || []).find((schema) => schema.slot_schema_id === schemaId) || { slots: [] };
    const tools = (state.lastData.toolCatalog || []).filter((tool) => tool.action_type === 'read_only');
    const selectedToolName = form.querySelector('[data-slot-autofill-react-call]')?.value || '';
    return {
      slots: slotSchema.slots || [],
      tools,
      selectedTool: findToolInCatalog(tools, selectedToolName) || null,
      previousSteps: [],
    };
  }
  if (textarea.matches('[data-enrichment-configuration-instruction]')) {
    const card = textarea.closest('[data-enrichment-step-card]');
    const cards = Array.from(form.querySelectorAll('[data-enrichment-step-card]'));
    const index = Math.max(0, cards.indexOf(card));
    const slotContext = currentResolutionSlotContextFromForm(form);
    const steps = safeEnrichmentStepsFromForm(form);
    const tools = currentResolutionToolsFromForm(form, steps);
    const selectedToolName = card?.querySelector('[data-enrichment-react-call]')?.value || '';
    return {
      slots: slotContext.slots || [],
      tools,
      selectedTool: findToolInCatalog(tools, selectedToolName) || null,
      previousSteps: safeEnrichmentStepsFromForm(form, index),
    };
  }
  if (textarea.matches('[name="llm_resolution_script_text"]')) {
    const slotContext = currentResolutionSlotContextFromForm(form);
    const steps = safeEnrichmentStepsFromForm(form);
    return {
      slots: slotContext.slots || [],
      tools: currentResolutionToolsFromForm(form, steps),
      selectedTool: null,
      previousSteps: steps,
    };
  }
  return null;
}

function toolBindingValue(binding) {
  if (!binding?.endpoint_id || !binding?.operation_id) {
    return '';
  }
  return `${binding.endpoint_id}|${binding.operation_id}`;
}

function findToolBinding(tool, endpointId, operationId) {
  return (tool?.endpoint_bindings || []).find(
    (binding) => binding.endpoint_id === endpointId && binding.operation_id === operationId,
  ) || null;
}

function currentToolBinding(tool) {
  return (tool?.endpoint_bindings || [])[0] || null;
}

function endpointForBinding(binding, endpoints) {
  return (endpoints || []).find((endpoint) => endpoint.endpoint_id === binding?.endpoint_id) || null;
}

function operationForBinding(binding, endpoints) {
  const endpoint = endpointForBinding(binding, endpoints);
  return endpoint?.operations?.[binding?.operation_id] || null;
}

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value ?? {}));
}

function operationBindingSummary(binding, endpoints) {
  if (!binding) {
    return 'Привязка не настроена';
  }
  const endpoint = endpointForBinding(binding, endpoints);
  const operation = operationForBinding(binding, endpoints);
  const endpointText = endpoint ? endpointLabel(endpoint) : binding.endpoint_id || 'подключение не выбрано';
  return `${endpointText} -> ${operationLabel(binding.operation_id, operation || {})}`;
}

function slotSchemaById(slotSchemas) {
  return Object.fromEntries((slotSchemas || []).map((schema) => [schema.slot_schema_id, schema]));
}

function buildMatrixSlotContext(matrix, scenarios, slotSchemas) {
  const schemaById = slotSchemaById(slotSchemas);
  const usedScenarios = (scenarios || []).filter(
    (scenario) => matrix?.matrix_id && scenario.tool_launch_matrix_id === matrix.matrix_id,
  );
  const fallbackScenario = (scenarios || []).find((scenario) => scenario.scenario_id === state.scenarioId)
    || (scenarios || [])[0]
    || null;
  const contextScenarios = usedScenarios.length ? usedScenarios : (fallbackScenario ? [fallbackScenario] : []);
  const slotMap = new Map();
  for (const scenario of contextScenarios) {
    const schema = schemaById[scenario.slot_schema_id];
    for (const slot of schema?.slots || []) {
      const entry = slotMap.get(slot.slot_id) || {
        slot_id: slot.slot_id,
        display_name: slot.display_name,
        priority_group: slot.priority_group,
        required: slot.required,
        fill_method: slot.fill_method,
        scenario_ids: new Set(),
        scenario_names: new Set(),
      };
      entry.display_name = entry.display_name || slot.display_name;
      entry.priority_group = entry.priority_group || slot.priority_group;
      entry.required = entry.required || slot.required;
      entry.fill_method = entry.fill_method || slot.fill_method;
      entry.scenario_ids.add(scenario.scenario_id);
      entry.scenario_names.add(scenario.display_name || scenario.scenario_id);
      slotMap.set(slot.slot_id, entry);
    }
  }
  const scenarioNames = contextScenarios.map((scenario) => scenario.display_name || scenario.scenario_id);
  const slots = Array.from(slotMap.values()).map((slot) => {
    const missingScenarioNames = contextScenarios
      .filter((scenario) => !slot.scenario_ids.has(scenario.scenario_id))
      .map((scenario) => scenario.display_name || scenario.scenario_id);
    return {
      ...slot,
      scenario_ids: Array.from(slot.scenario_ids),
      scenario_names: Array.from(slot.scenario_names),
      missing_scenario_names: missingScenarioNames,
    };
  });
  return {
    usedByMatrix: usedScenarios.length > 0,
    scenarioCount: contextScenarios.length,
    scenarioNames,
    slots,
  };
}

function slotContextPanel(slotContext) {
  const scope = slotContext.usedByMatrix
    ? `Матрица используется в сценариях: ${slotContext.scenarioNames.join(', ')}.`
    : `Матрица пока не привязана к сценарию; для подсказок используется контекст: ${slotContext.scenarioNames.join(', ') || 'не выбран'}.`;
  return `
    <div class="slot-schema-derived">
      <div class="metric-label">Контекст слотов для маппинга параметров</div>
      <div class="meta">${escapeHtml(scope)}</div>
    </div>
  `;
}

function parameterSchemaProperties(tool) {
  return tool?.parameters_schema?.properties || {};
}

function parameterNamesForTool(tool, parameterBindings) {
  const required = tool?.parameters_schema?.required || [];
  const schemaNames = Object.keys(parameterSchemaProperties(tool));
  const existing = Object.keys(parameterBindings || {});
  return Array.from(new Set([...required, ...schemaNames, ...existing]));
}

function defaultParameterBindingsForTool(tool) {
  const required = tool?.parameters_schema?.required || [];
  const result = {};
  for (const parameterName of required) {
    result[parameterName] = `context:${parameterName}`;
  }
  return result;
}

function parameterTypeLabel(schema) {
  if (!schema) return 'extra';
  const type = Array.isArray(schema.type) ? schema.type.join(' / ') : schema.type;
  const enumSuffix = schema.enum?.length ? `, enum: ${schema.enum.join(', ')}` : '';
  return `${type || 'object'}${enumSuffix}`;
}

function parseBindingString(binding) {
  const text = String(binding || '');
  const separatorIndex = text.indexOf(':');
  if (separatorIndex < 1) {
    return { source: '', value: '' };
  }
  return {
    source: text.slice(0, separatorIndex),
    value: text.slice(separatorIndex + 1),
  };
}

function parameterSourceOptions(selected) {
  return [
    `<option value="" ${!selected ? 'selected' : ''}>не задано</option>`,
    ...['slot', 'case', 'context', 'constant', 'secret'].map(
      (value) => `<option value="${escapeHtml(value)}" ${value === selected ? 'selected' : ''}>${escapeHtml(visibleLabels[value] || value)}</option>`,
    ),
  ].join('');
}

function slotOptionLabel(slot, slotContext) {
  const base = `${slot.display_name || slot.slot_id} (${slot.slot_id})`;
  const flags = [
    slot.required ? 'обязательный' : 'необязательный',
    visibleLabels[slot.fill_method] || slot.fill_method,
    visibleLabels[slot.priority_group] || slot.priority_group,
  ].filter(Boolean).join(', ');
  const scope = slotContext.scenarioCount > 1
    ? `; сценарии: ${slot.scenario_names.join(', ')}`
    : '';
  return `${base} — ${flags}${scope}`;
}

function slotOptions(slotContext, selectedSlotId) {
  const selectedExists = (slotContext.slots || []).some((slot) => slot.slot_id === selectedSlotId);
  const options = (slotContext.slots || []).map((slot) => ({
    value: slot.slot_id,
    label: slotOptionLabel(slot, slotContext),
  }));
  if (selectedSlotId && !selectedExists) {
    options.unshift({
      value: selectedSlotId,
      label: `Слот не найден в выбранной схеме: ${selectedSlotId}`,
    });
  }
  if (!options.length) {
    return '<option value="">Нет доступных слотов</option>';
  }
  return [
    `<option value="" ${!selectedSlotId ? 'selected' : ''}>выберите слот</option>`,
    ...options.map(
      (option) => `<option value="${escapeHtml(option.value)}" ${option.value === selectedSlotId ? 'selected' : ''}>${escapeHtml(option.label)}</option>`,
    ),
  ].join('');
}

function slotWarning(slotContext, slotId) {
  if (!slotId) return '';
  const slot = (slotContext.slots || []).find((item) => item.slot_id === slotId);
  if (!slot) {
    return `Слот ${slotId} отсутствует в выбранном контексте слотов.`;
  }
  if (slot.missing_scenario_names?.length) {
    return `Слот отсутствует в сценариях: ${slot.missing_scenario_names.join(', ')}.`;
  }
  return '';
}

function schemaDisplayName(parameterName, schema) {
  return schema?.title || parameterName;
}

function schemaMetaLine(parameterName, schema, required, suffix = '') {
  const typeText = parameterTypeLabel(schema);
  const codePrefix = schema?.title && schema.title !== parameterName ? `${parameterName} · ` : '';
  return `${codePrefix}${required ? 'обязательный' : 'необязательный'} · ${typeText}${suffix}`;
}

function renderParameterBindingRow(parameterName, binding, tool, slotContext, rowIndex) {
  const properties = parameterSchemaProperties(tool);
  const required = (tool?.parameters_schema?.required || []).includes(parameterName);
  const schema = properties[parameterName] || null;
  const parsed = parseBindingString(binding);
  const source = parsed.source || '';
  const value = parsed.value || '';
  const warning = source === 'slot' ? slotWarning(slotContext, value) : '';
  return `
    <div class="parameter-binding-row" data-param-binding-row data-required="${required ? 'true' : 'false'}">
      <input type="hidden" value="${escapeHtml(parameterName)}" data-binding-param-name>
      <div class="parameter-binding-meta">
        <strong>${escapeHtml(schemaDisplayName(parameterName, schema))}</strong>
        <span>${escapeHtml(schemaMetaLine(parameterName, schema, required))}</span>
      </div>
      <label>Заполняется из
        <select data-binding-source name="binding_source_${rowIndex}">${parameterSourceOptions(source)}</select>
      </label>
      <label data-binding-slot-wrap ${source === 'slot' ? '' : 'hidden'}>Слот
        <select data-binding-slot-select name="binding_slot_${rowIndex}">${slotOptions(slotContext, value)}</select>
        <span class="field-help" data-binding-slot-warning ${warning ? '' : 'hidden'}>${escapeHtml(warning)}</span>
      </label>
      <label data-binding-value-wrap ${source && source !== 'slot' ? '' : 'hidden'}>Параметр или значение
        <input data-binding-value-input name="binding_value_${rowIndex}" value="${source === 'slot' ? '' : escapeHtml(value)}" autocomplete="off" placeholder="${source}:...">
      </label>
    </div>
  `;
}

function parameterBindingsEditor(tool, parameterBindings, slotContext) {
  const names = parameterNamesForTool(tool, parameterBindings);
  if (!names.length) {
    return '<div class="empty" data-launch-parameters>У вызова нет описанных параметров.</div>';
  }
  const requiredNames = names.filter((name) => (tool?.parameters_schema?.required || []).includes(name));
  const optionalNames = names.filter((name) => !requiredNames.includes(name));
  const renderRows = (items, offset = 0) => items.map((name, index) => renderParameterBindingRow(
    name,
    parameterBindings?.[name] || '',
    tool,
    slotContext,
    offset + index,
  )).join('');
  return `
    <div class="parameter-binding-list" data-launch-parameters>
      <div class="parameter-binding-header">
        <span>Параметр вызова</span>
        <span>Заполняется из</span>
        <span>Параметр или значение</span>
      </div>
      ${renderRows(requiredNames)}
      ${optionalNames.length
        ? `<details class="slot-card">
            <summary class="slot-card-summary">
              <div class="slot-card-summary-main">
                <strong>Необязательные параметры</strong>
                <span>${escapeHtml(optionalNames.length)} параметров</span>
              </div>
            </summary>
            <div class="slot-card-body">${renderRows(optionalNames, requiredNames.length)}</div>
          </details>`
        : ''}
    </div>
  `;
}

function renderToolLaunchEditor({ matrix, matrices, scenarios, tools, integrationEndpoints, slotContext }) {
  if (state.toolMatrixOperation === 'delete') {
    if (!matrix?.matrix_id) {
      return '<div class="empty">Нет выбранной матрицы ReAct-вызовов для удаления</div>';
    }
    return `
      <form class="scenario-editor panel" data-form="tool-matrix-delete">
        <div>
          <div class="metric-label">Удаляемая матрица ReAct-вызовов</div>
          <div class="scenario-title">${escapeHtml(matrix.display_name)}</div>
        </div>
        ${usagePanel(scenarios, 'tool_launch_matrix_id', matrix.matrix_id)}
        <button class="danger" type="submit">Удалить матрицу ReAct-вызовов</button>
      </form>
    `;
  }
  const current = state.toolMatrixOperation === 'create'
    ? toolMatrixCreateTemplate(matrix, matrices)
    : matrix;
  if (!current?.matrix_id) {
    return '<div class="empty">Матрица ReAct-вызовов не выбрана</div>';
  }
  const launches = current.launches || [];
  const launchForms = launches
    .map((launch, index) => renderLaunchCard(launch, index, tools, integrationEndpoints, slotContext))
    .join('');
  return `
    <form class="scenario-editor panel" data-form="tool-launch-editor">
      <input type="hidden" name="matrix_id" value="${escapeHtml(current.matrix_id)}">
      <label>Название<input name="display_name" value="${escapeHtml(current.display_name || '')}" autocomplete="off"></label>
      <input type="hidden" name="launch_count" value="${escapeHtml(launches.length)}">
      ${slotContextPanel(slotContext)}
      <div id="launchCards">${launchForms}</div>
      <button type="button" data-action="launch-add">Добавить запуск</button>
      ${usagePanel(scenarios, 'tool_launch_matrix_id', current.matrix_id)}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">${state.toolMatrixOperation === 'create' ? 'Создать матрицу ReAct-вызовов' : 'Сохранить матрицу ReAct-вызовов'}</button>
      </div>
    </form>
  `;
}

function renderLaunchCard(
  launch,
  index,
  tools = state.lastData.toolCatalog || [],
  integrationEndpoints = state.lastData.integrationEndpoints || [],
  slotContext = state.lastData.toolMatrixSlotContext || { slots: [], scenarioNames: [], scenarioCount: 0, usedByMatrix: false },
) {
  const launchMode = launch.execution_level || 'operator_approval';
  const completionPolicy = normalizeCompletionPolicy(launch.completion_policy);
  const toolName = launch.tool_name || (tools || [])[0]?.tool_name || '';
  const tool = findToolInCatalog(tools, toolName);
  const binding = currentToolBinding(tool);
  const endpointId = binding?.endpoint_id || '';
  const operationId = binding?.operation_id || '';
  const bindingStatus = binding
    ? operationBindingSummary(binding, integrationEndpoints)
    : 'У выбранного ReAct-вызова ИИ нет привязки операции. Настройте ее в меню "Вызовы и интеграции -> Привязка операций".';
  return `
    <fieldset class="launch-editor" data-launch-card>
      <legend>${escapeHtml(toolName || `Запуск ${index + 1}`)}</legend>
      <input type="hidden" name="launch_id_${index}" value="${escapeHtml(launch.launch_id)}">
      <input type="hidden" name="endpoint_id_${index}" value="${escapeHtml(endpointId)}" data-launch-endpoint>
      <input type="hidden" name="operation_id_${index}" value="${escapeHtml(operationId)}" data-launch-operation>
      ${renderLaunchGroup(
        'ReAct-вызов ИИ',
        'Выберите действие, которое может предложить ИИ в ReAct-loop.',
        `<div class="grid two">
          <label>ReAct-вызов ИИ<select name="tool_name_${index}" data-launch-tool>${toolCatalogOptions(tools, toolName)}</select></label>
        </div>`,
        'data-launch-tool-group',
      )}
      ${renderLaunchGroup(
        'Текущая привязка операции',
        'Техническое подключение выбирается в меню "Вызовы и интеграции -> Привязка операций" и подставляется сюда автоматически.',
        `<div class="${binding ? 'meta' : 'field-help'}" data-launch-binding-status>${escapeHtml(bindingStatus)}</div>`,
      )}
      ${renderLaunchGroup(
        'Получение результата',
        'Показывает, завершится ли вызов сразу или откроет ожидание результата от endpoint, timer worker или n8n. Сам цикл ожидания не добавляется в ReAct-loop.',
        `<div class="grid two">
          <label>Режим результата<select name="completion_mode_${index}">${optionList(completionModes, completionPolicy.mode)}</select></label>
          <label>Максимальное ожидание, сек.<input name="completion_max_wait_seconds_${index}" type="number" min="0" max="604800" value="${escapeHtml(completionPolicy.max_wait_seconds)}"></label>
          <label>Интервал проверки, сек.<input name="completion_check_interval_seconds_${index}" type="number" min="0" max="604800" value="${escapeHtml(completionPolicy.check_interval_seconds || 0)}"></label>
          <label>Ожидаемый тип события<input name="completion_expected_event_type_${index}" value="${escapeHtml(completionPolicy.expected_event_type || '')}" autocomplete="off"></label>
          <label>Действие по timeout<select name="completion_timeout_action_${index}">${optionList(completionTimeoutActions, completionPolicy.timeout_action)}</select></label>
        </div>`,
      )}
      ${renderLaunchGroup(
        'Параметры вызова',
        'Какие слоты, поля кейса, контекст, константы или секреты заполняют параметры выбранного вызова. Технический payload endpoint настраивается в "Вызовы и интеграции -> Привязка операций". Required slots вычисляются из источников вида slot:<slot_id>.',
        parameterBindingsEditor(tool, launch.parameter_bindings || {}, slotContext),
      )}
      ${renderLaunchGroup(
        'Контроль запуска',
        'Сценарная политика исполнения: согласование, риск, аудит, логирование и остановка при ошибке.',
        `<div class="grid two">
          <label>Режим исполнения сейчас<select name="execution_mode_${index}">${activeOptionList(activeLaunchExecutionModes, launchMode)}</select></label>
          <label>Риск<select name="risk_level_${index}">${optionList(['low', 'medium', 'high', 'critical', 'blocked'], launch.risk_level)}</select></label>
          <label>Роль согласования<input name="approval_role_${index}" value="${escapeHtml(launch.approval_role || '')}" autocomplete="off"></label>
          <label>Остановить при ошибке<select name="stop_on_error_${index}">${booleanOptions(launch.stop_on_error)}</select></label>
        </div>`,
      )}
      <button class="danger" type="button" data-action="launch-remove">Удалить запуск</button>
    </fieldset>
  `;
}

function normalizeCompletionPolicy(policy = {}) {
  const mode = completionModes.includes(policy.mode) ? policy.mode : 'sync';
  if (mode === 'sync') {
    return {
      mode: 'sync',
      max_wait_seconds: 0,
      check_interval_seconds: 0,
      expected_event_type: '',
      timeout_action: policy.timeout_action || 'resume_agent',
    };
  }
  return {
    mode,
    max_wait_seconds: Number(policy.max_wait_seconds || 86400),
    check_interval_seconds: Number(policy.check_interval_seconds || 0),
    expected_event_type: policy.expected_event_type || '',
    timeout_action: completionTimeoutActions.includes(policy.timeout_action) ? policy.timeout_action : 'escalate_operator',
  };
}

function escalationCreateTemplate(source, policies) {
  const template = source || policies[0] || {};
  return {
    policy_id: nextConfigItemId(template.policy_id || 'escalation.custom', policies, 'policy_id'),
    display_name: '',
    auto_close: template.auto_close || {
      requires_tool_success: true,
    },
    handoff_conditions: template.handoff_conditions || [
      'two_tool_errors',
      'iteration_limit',
      'confidence_below_050',
      'affected_users_threshold',
      'policy_blocked',
    ],
    major_incident: template.major_incident || {
      affected_users_threshold: 10,
    },
    handoff_package: template.handoff_package || [
      'slots',
      'react_history',
      'tool_results',
      'agent_hypothesis',
      'sla_remaining',
      'user_notification',
    ],
    user_notification_template: template.user_notification_template || '',
  };
}

function renderEscalationEditor({ policy, policies, scenarios }) {
  if (state.escalationOperation === 'delete') {
    if (!policy?.policy_id) {
      return '<div class="empty">Нет выбранной политики эскалации для удаления</div>';
    }
    return `
      <form class="scenario-editor panel" data-form="escalation-delete">
        <div>
          <div class="metric-label">Удаляемая политика решения и эскалации оператору</div>
          <div class="scenario-title">${escapeHtml(policy.display_name)}</div>
        </div>
        ${usagePanel(scenarios, 'escalation_policy_id', policy.policy_id)}
        <button class="danger" type="submit">Удалить политику решения и эскалации</button>
      </form>
    `;
  }
  const current = state.escalationOperation === 'create'
    ? escalationCreateTemplate(policy, policies)
    : policy;
  if (!current?.policy_id) {
    return '<div class="empty">Политика решения и эскалации не выбрана</div>';
  }
  return `
    <form class="scenario-editor panel" data-form="escalation-editor">
      <input type="hidden" name="policy_id" value="${escapeHtml(current.policy_id)}">
      <label>Название<input name="display_name" value="${escapeHtml(current.display_name || '')}" autocomplete="off"></label>
      <div class="grid two">
        <label>Автозакрытие требует успех ReAct-вызова<select name="requires_tool_success">${booleanOptions(current.auto_close?.requires_tool_success)}</select></label>
        <label>Major Incident threshold<input name="affected_users_threshold" type="number" min="1" max="100000" value="${escapeHtml(current.major_incident?.affected_users_threshold || 10)}"></label>
      </div>
      <fieldset class="launch-editor">
        <legend>Условия эскалации оператору</legend>
        <div class="meta">Когда AI останавливает самостоятельную обработку и кейс передается оператору через выбранный канал взаимодействия.</div>
        ${renderChoiceChecklist('handoff_conditions', handoffConditionChoices, current.handoff_conditions || [])}
      </fieldset>
      <fieldset class="launch-editor">
        <legend>Пакет эскалации оператору</legend>
        <div class="meta">Какие данные попадут в пакет контекста для оператора или функциональной группы. Обязательные пункты нельзя отключить.</div>
        ${renderChoiceChecklist('handoff_package', handoffPackageChoices, current.handoff_package || [])}
      </fieldset>
      <label>Шаблон уведомления клиента<textarea name="user_notification_template" rows="4">${escapeHtml(current.user_notification_template || '')}</textarea></label>
      ${usagePanel(scenarios, 'escalation_policy_id', current.policy_id)}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">${state.escalationOperation === 'create' ? 'Создать политику решения и эскалации' : 'Сохранить решение и эскалацию'}</button>
      </div>
    </form>
  `;
}

function renderPromptPackEditor({ promptPack, packs, scenarios }) {
  if (state.promptPackOperation === 'delete') {
    if (!promptPack) {
      return '<div class="empty">Нет выбранного пакета промптов для удаления</div>';
    }
    return `
      <form class="scenario-editor panel" data-form="prompt-pack-delete">
        <div>
          <div class="metric-label">Удаляемый пакет промптов</div>
          <div class="scenario-title">${escapeHtml(promptPackLabel(promptPack))}</div>
          <div class="meta">Пакет нельзя удалить, если активный сценарий продолжает ссылаться на него.</div>
        </div>
        <button class="danger" type="submit">Удалить пакет промптов</button>
      </form>
    `;
  }

  const current = state.promptPackOperation === 'create'
    ? promptPackCreateTemplate(promptPack, packs, scenarios)
    : promptPack;
  if (!current?.prompt_pack_id) {
    return '<div class="empty">Пакет промптов не выбран</div>';
  }
  const blockLabels = {
    role_context: '1. Роль и контекст',
    behavior_principles: '2. Принципы поведения',
    slot_schemas: '3. Схемы слотов',
    classification_confidence: '4. Классификация и confidence',
    react_planning: '5. ReAct и планирование',
    tool_rules: '6. Правила ReAct-вызовов',
    escalation_response: '7. Эскалация и формат ответа',
  };
  const blockFields = Object.entries(blockLabels).map(([key, label]) => `
    <label>${escapeHtml(label)}<textarea name="${escapeHtml(key)}" rows="5">${escapeHtml(current.blocks?.[key] || '')}</textarea></label>
  `).join('');
  return `
    <form class="scenario-editor panel" data-form="prompt-pack-editor">
      <input type="hidden" name="prompt_pack_id" value="${escapeHtml(current.prompt_pack_id)}">
      <input type="hidden" name="status" value="${escapeHtml(current.status || 'draft')}">
      <input type="hidden" name="active_version" value="${escapeHtml(current.active_version || 'v1')}">
      <div class="grid two">
        <label>Название<input name="display_name" value="${escapeHtml(current.display_name || '')}" autocomplete="off"></label>
      </div>
      ${blockFields}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">${state.promptPackOperation === 'create' ? 'Создать пакет промптов' : 'Сохранить пакет промптов'}</button>
      </div>
    </form>
  `;
}

function optionList(values, selected, labels = visibleLabels) {
  return values
    .map((value) => `<option value="${escapeHtml(value)}" ${value === selected ? 'selected' : ''}>${escapeHtml(labels[value] || value)}</option>`)
    .join('');
}

function activeOptionList(values, selected, labels = visibleLabels) {
  const options = [...values];
  if (selected && !options.includes(selected)) {
    options.unshift(selected);
  }
  return options
    .map((value) => {
      const inactive = !values.includes(value);
      const suffix = inactive ? ' (не исполняется)' : '';
      return `<option value="${escapeHtml(value)}" ${value === selected ? 'selected' : ''}>${escapeHtml((labels[value] || value) + suffix)}</option>`;
    })
    .join('');
}

function booleanOptions(selected) {
  return [
    `<option value="true" ${selected === true ? 'selected' : ''}>да</option>`,
    `<option value="false" ${selected === false ? 'selected' : ''}>нет</option>`,
  ].join('');
}

function renderChoiceChecklist(name, choices, selectedValuesList) {
  const selected = new Set(selectedValuesList || []);
  return `
    <div class="choice-grid">
      ${choices.map((choice) => {
        const checked = selected.has(choice.value) || choice.required;
        const disabled = choice.required;
        const inputId = `${name}_${choice.value}`;
        return `
          <label class="choice-card" for="${escapeHtml(inputId)}">
            ${disabled ? `<input type="hidden" name="${escapeHtml(name)}" value="${escapeHtml(choice.value)}">` : ''}
            <input id="${escapeHtml(inputId)}" name="${escapeHtml(name)}" type="checkbox" value="${escapeHtml(choice.value)}" ${checked ? 'checked' : ''} ${disabled ? 'disabled' : ''}>
            <span>
              <strong>${escapeHtml(choice.label)}</strong>
              <small>${escapeHtml(choice.help)}</small>
            </span>
          </label>
        `;
      }).join('')}
    </div>
  `;
}

function csv(items) {
  return (items || []).join(', ');
}

const classificationMatchTypeLabels = {
  phrase: 'фраза',
  word: 'слово',
  contains: 'вхождение',
};

const classificationPolarityLabels = {
  positive: 'позитивное',
  negative: 'негативное',
};

function defaultClassificationRule() {
  return {
    text: '',
    match_type: 'phrase',
    polarity: 'positive',
    weight: 0.5,
    required: false,
    blocking: false,
    explanation: '',
  };
}

function classificationRuleItems(route = {}) {
  return route.rules?.rule_items?.length
    ? route.rules.rule_items
    : [defaultClassificationRule()];
}

function renderClassificationRuleCard(rule = {}, index = 0, open = false) {
  const current = { ...defaultClassificationRule(), ...rule };
  const title = current.text || `Правило ${index + 1}`;
  return `
    <details class="slot-card" data-route-rule-card${open ? ' open' : ''}>
      <summary>
        <span>${escapeHtml(title)}</span>
        <span class="slot-card-actions">
          <button class="ghost danger" type="button" data-action="route-rule-remove">Удалить</button>
        </span>
      </summary>
      <div class="grid two">
        <label>Текст признака
          <input name="rule_text" value="${escapeHtml(current.text || '')}" autocomplete="off" placeholder="сброс пароля">
          <span class="field-help">Слово или фраза, которую ищем в тексте обращения.</span>
        </label>
        <label>Тип совпадения
          <select name="rule_match_type">${optionList(Object.keys(classificationMatchTypeLabels), current.match_type, classificationMatchTypeLabels)}</select>
          <span class="field-help">Фраза ищется как текст, слово - с границами слова, вхождение - как часть строки.</span>
        </label>
        <label>Влияние
          <select name="rule_polarity">${optionList(Object.keys(classificationPolarityLabels), current.polarity, classificationPolarityLabels)}</select>
          <span class="field-help">Позитивное правило повышает уверенность маршрута, негативное снижает ее.</span>
        </label>
        <label>Вес
          <input name="rule_weight" type="number" min="0.01" max="1" step="0.01" value="${escapeHtml(current.weight ?? 0.5)}">
          <span class="field-help">Сила признака от 0.01 до 1.</span>
        </label>
        <label>Обязательное
          <select name="rule_required">${booleanOptions(current.required)}</select>
          <span class="field-help">Для позитивного правила: если признак не найден, маршрут получает confidence 0.</span>
        </label>
        <label>Блокирующее
          <select name="rule_blocking">${booleanOptions(current.blocking)}</select>
          <span class="field-help">Для негативного правила: если признак найден, маршрут блокируется.</span>
        </label>
      </div>
      <label>Пояснение
        <textarea name="rule_explanation" rows="2" placeholder="Почему этот признак относится к маршруту">${escapeHtml(current.explanation || '')}</textarea>
      </label>
    </details>
  `;
}

function renderClassificationRules(route = {}) {
  return `
    <fieldset class="launch-editor">
      <legend>Правила классификации</legend>
      <div class="meta">Правила оцениваются по всем маршрутам. Позитивные признаки повышают уверенность, негативные снижают ее или блокируют маршрут.</div>
      <div data-route-rules-list>
        ${classificationRuleItems(route).map((rule, index) => renderClassificationRuleCard(rule, index, index === 0)).join('')}
      </div>
      <button type="button" data-action="route-rule-add">Добавить правило</button>
    </fieldset>
  `;
}

function jsonPretty(value) {
  return JSON.stringify(value, null, 2);
}

async function renderDashboard() {
  const [session, dashboard, auditSummary, graphContext] = await Promise.all([
    api('/admin/security/session'),
    api('/admin/dashboard'),
    api('/admin/security/audit/summary'),
    loadOrchestrationGraphContext().catch((error) => ({
      scenarios: [],
      graph: {
        nodes: [],
        warnings: [error.message || String(error)],
      },
      selectedNode: null,
    })),
  ]);
  state.lastData.dashboard = dashboard;
  elements.viewContent.innerHTML = [
    section(
      'Обзор платформы',
      statusStrip([
        {
          label: 'Ожидают согласования',
          value: escapeHtml(dashboard.approvals?.by_status?.pending ?? 0),
          risk: Number(dashboard.approvals?.by_status?.pending || 0) > 0,
        },
        { label: 'Кейсы', value: escapeHtml(dashboard.cases?.total ?? 0) },
        { label: 'База знаний', value: badge(dashboard.knowledge?.status || dashboard.knowledge?.index_manifest?.status) },
        { label: 'Интеграции', value: escapeHtml(`${dashboard.integrations?.enabled_endpoint_count ?? 0}/${dashboard.integrations?.endpoint_count ?? 0}`) },
        { label: 'Аудит', value: escapeHtml(auditSummary.total ?? 0) },
      ]),
    ),
    section(
      'Граф оркестрации',
      renderOrchestrationGraphPanel(graphContext),
    ),
    section(
      'Ресурсы',
      `<div class="grid">
        ${metric('Обратная связь', String(dashboard.feedback?.total ?? 0))}
        ${metric('ReAct-вызовы ИИ', String(dashboard.tools?.count ?? 0))}
        ${metric('Алиас модели', escapeHtml(dashboard.models?.default_model_alias || 'н/д'))}
      </div>`,
    ),
    section(
      'Текущая сессия',
      `<div class="grid three">
        ${metric('Инициатор', escapeHtml(session.actor_id))}
        ${metric('Роли', escapeHtml(session.roles.join(', ')))}
        ${metric('Права', String(session.permissions.length))}
      </div>`,
    ),
  ].join('');
  attachDashboardGraphInteractions(graphContext.graph);
}

async function renderProcessing({ scrollToDetail = false } = {}) {
  const [overview, casesPayload, runsPayload, tasksPayload, waitsPayload, baseGraph] = await Promise.all([
    api('/admin/processing/overview'),
    api('/admin/processing/cases?limit=100'),
    api('/admin/processing/runs?limit=50'),
    api('/admin/processing/tasks?limit=50'),
    api('/admin/processing/waits?limit=50'),
    api('/admin/orchestration-graph?view=base'),
  ]);
  const cases = casesPayload.cases || [];
  if (!state.processingCaseId || !cases.some((item) => item.case_id === state.processingCaseId)) {
    state.processingCaseId = cases[0]?.case_id || '';
  }
  const detail = state.processingCaseId
    ? await api(`/admin/processing/cases/${encodeURIComponent(state.processingCaseId)}`)
    : null;
  state.lastData.processingOverview = overview;
  state.lastData.processingCaseDetail = detail;
  const graph = processingRuntimeGraph(baseGraph, detail);
  if (graph.nodes?.length) {
    state.lastData.orchestrationGraph = graph;
    const activeNode = graph.nodes.find((node) => node.status === 'running' || node.status === 'waiting')
      || graph.nodes.find((node) => node.status === 'error')
      || graph.nodes[0];
    state.orchestrationGraphSelectedNodeId = activeNode?.id || state.orchestrationGraphSelectedNodeId;
  }

  elements.viewContent.innerHTML = [
    section('Состояние потока', renderProcessingOverview(overview)),
    section('Кейсы в потоке', renderProcessingCases(cases)),
    section('Выбранный кейс', renderProcessingCaseDetail(detail)),
    section('Запуски и задачи', renderProcessingRunsAndTasks(detail, runsPayload.runs || [], tasksPayload.tasks || [])),
    section('Ожидания', renderProcessingWaits(detail, waitsPayload.waits || [])),
    section('Kafka и outbox', renderProcessingKafka(overview, detail)),
    section(
      'Граф обработки',
      graph.nodes?.length
        ? `<div class="graph-workspace processing-graph">
            <div class="graph-board panel">
              ${renderGraphControls()}
              <div class="graph-canvas" data-graph-canvas>
                ${renderGraphSvg(graph)}
              </div>
            </div>
            ${renderGraphNodeDetails(graph, selectedGraphNode(graph))}
          </div>`
        : '<div class="empty">Граф обработки пока недоступен.</div>',
    ),
  ].join('');
  if (graph.nodes?.length) {
    attachOrchestrationGraphInteractions();
    updateGraphViewport();
  }
  if (scrollToDetail) {
    document.getElementById('processingCaseDetail')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

function renderProcessingOverview(overview) {
  const active = overview.active || {};
  return statusStrip([
    { label: 'Зависшие задачи', value: escapeHtml(active.stale_tasks ?? 0), risk: Number(active.stale_tasks || 0) > 0 },
    { label: 'Активные run', value: escapeHtml(active.runs ?? 0) },
    { label: 'Активные задачи', value: escapeHtml(active.tasks ?? 0) },
    { label: 'Ожидания', value: escapeHtml(active.waits ?? 0), risk: Number(active.waits || 0) > 0 },
    { label: 'Outbox Kafka', value: escapeHtml(overview.kafka?.outbox_pending ?? 0), risk: Number(overview.kafka?.outbox_pending || 0) > 0 },
  ]) + `
    <div class="grid two">
      ${metric('Kafka bootstrap', escapeHtml(overview.kafka?.bootstrap_servers || 'н/д'))}
      ${metric('Run status', processingCounts(overview.runs_by_status))}
      ${metric('Task status', processingCounts(overview.tasks_by_status))}
    </div>
  `;
}

function processingCounts(counts = {}) {
  const items = Object.entries(counts);
  if (!items.length) return 'н/д';
  return items.map(([status, count]) => `${badge(status)} ${escapeHtml(count)}`).join(' ');
}

function renderProcessingCases(cases) {
  const rows = cases.map((item) => [
    `<button type="button" class="${item.case_id === state.processingCaseId ? 'primary' : ''}" data-action="processing-case-open" data-case-id="${escapeHtml(item.case_id)}">${item.case_id === state.processingCaseId ? 'Открыт' : 'Открыть'}</button>`,
    escapeHtml(item.case_id),
    escapeHtml(item.ticket_id),
    badge(item.workflow_state_id),
    badge(item.processing?.run_status || 'missing'),
    escapeHtml(item.processing?.current_step || 'н/д'),
    escapeHtml(item.updated_at || 'н/д'),
  ]);
  return table(['Действие', 'Кейс', 'Заявка', 'Workflow', 'Run', 'Шаг', 'Обновлено'], rows);
}

function renderProcessingCaseDetail(detail) {
  if (!detail?.case) {
    return '<div id="processingCaseDetail" class="empty">Кейс не выбран или поток обработки пуст.</div>';
  }
  const caseRecord = detail.case;
  const currentRun = (detail.runs || [])[0] || null;
  const activeWait = (detail.waits || []).find((wait) => ['open', 'reminded'].includes(wait.status));
  const slotValues = caseRecord.analysis_snapshot?.simulation?.slot_values
    || caseRecord.analysis_snapshot?.slot_values
    || {};
  const eventRows = (detail.timeline?.events || []).slice(0, 8).map((event) => [
    escapeHtml(event.created_at),
    badge(event.event_type),
    escapeHtml(event.summary || event.actor_id || 'н/д'),
  ]);
  return `
    <div id="processingCaseDetail" class="processing-anchor"></div>
    <div class="grid">
      ${metric('Кейс', escapeHtml(caseRecord.case_id))}
      ${metric('Workflow', badge(caseRecord.current_workflow_state?.id || 'н/д'))}
      ${metric('Текущий run', escapeHtml(currentRun?.run_id || 'н/д'))}
      ${metric('Активное ожидание', activeWait ? badge(activeWait.wait_type) : 'нет')}
    </div>
    <div class="scenario-editor-actions">
      <button class="danger" type="button" data-action="processing-case-escalate" data-case-id="${escapeHtml(caseRecord.case_id)}">Эскалировать кейс</button>
    </div>
    <div class="processing-split">
      <div class="panel">
        <div class="metric-label">Контекст кейса</div>
        <div class="meta">Слоты и runtime context являются снимком текущей реализации; прямое редактирование из админки запрещено.</div>
        ${jsonBlock({
          ticket_input: caseRecord.ticket_input,
          slots: slotValues,
          workflow_state: caseRecord.current_workflow_state,
        })}
      </div>
      <div class="panel">
        <div class="metric-label">Последние события timeline</div>
        ${table(['Время', 'Событие', 'Описание'], eventRows)}
      </div>
    </div>
  `;
}

function renderProcessingRunsAndTasks(detail, fallbackRuns, fallbackTasks) {
  const runs = detail?.runs?.length ? detail.runs : fallbackRuns;
  const tasks = detail?.tasks?.length ? detail.tasks : fallbackTasks;
  const runRows = runs.map((run) => [
    badge(run.status),
    escapeHtml(run.run_id),
    escapeHtml(run.case_id),
    escapeHtml(run.current_step || 'н/д'),
    escapeHtml(run.started_at || 'н/д'),
    escapeHtml(run.updated_at || 'н/д'),
    `<button class="danger" type="button" data-action="processing-run-cancel" data-run-id="${escapeHtml(run.run_id)}" ${['completed', 'failed', 'cancelled', 'escalated', 'timed_out'].includes(run.status) ? 'disabled' : ''}>Отменить</button>`,
  ]);
  const taskRows = tasks.map((task) => [
    badge(task.stale ? 'stale' : task.status),
    escapeHtml(task.task_id),
    escapeHtml(task.case_id),
    badge(task.task_type),
    escapeHtml(task.worker_id || 'н/д'),
    escapeHtml(task.attempt ?? 0),
    escapeHtml(task.heartbeat_at || 'н/д'),
    `<div class="table-actions">
      <button type="button" data-action="processing-task-retry" data-task-id="${escapeHtml(task.task_id)}" ${['failed', 'expired', 'cancelled', 'blocked'].includes(task.status) ? '' : 'disabled'}>Повторить</button>
      <button type="button" data-action="processing-task-release" data-task-id="${escapeHtml(task.task_id)}" ${['running', 'leased'].includes(task.status) ? '' : 'disabled'}>Освободить lease</button>
    </div>`,
  ]);
  return `
    <div class="processing-split">
      <div>${table(['Статус', 'Run', 'Кейс', 'Шаг', 'Старт', 'Обновлено', 'Действие'], runRows)}</div>
      <div>${table(['Статус', 'Задача', 'Кейс', 'Тип', 'Worker', 'Попытка', 'Heartbeat', 'Действия'], taskRows)}</div>
    </div>
  `;
}

function renderProcessingWaits(detail, fallbackWaits) {
  const waits = detail?.waits?.length ? detail.waits : fallbackWaits;
  const rows = waits.map((wait) => [
    badge(wait.status),
    badge(wait.wait_type),
    waitOriginSummary(wait.origin),
    escapeHtml(wait.wait_id),
    escapeHtml(wait.case_id),
    escapeHtml(wait.channel_id || 'н/д'),
    escapeHtml(wait.deadline_at || 'н/д'),
    escapeHtml(wait.reason || wait.correlation_id || 'н/д'),
    `<button type="button" data-action="processing-wait-timeout" data-wait-id="${escapeHtml(wait.wait_id)}" ${['open', 'reminded'].includes(wait.status) ? '' : 'disabled'}>Timeout</button>`,
  ]);
  return table(['Статус', 'Тип', 'Источник', 'Ожидание', 'Кейс', 'Канал', 'Дедлайн', 'Причина', 'Действие'], rows);
}

function waitOriginSummary(origin = {}) {
  if (!origin || !origin.kind) return 'н/д';
  const kind = visibleLabels[origin.kind] || origin.kind;
  if (origin.kind === 'react_call') {
    const call = origin.react_call || origin.tool_name || 'ReAct-вызов';
    const endpoint = origin.endpoint_id || 'endpoint н/д';
    const operation = origin.operation_id || 'операция н/д';
    return escapeHtml(`${kind}: ${call} -> ${endpoint}/${operation}`);
  }
  if (origin.kind === 'client_question') {
    return escapeHtml(`${kind}: ${formatList(origin.slot_ids || origin.expected_slots || [])}`);
  }
  if (origin.kind === 'approval') {
    return escapeHtml(`${kind}: ${formatList(origin.approval_ids || [])}`);
  }
  return escapeHtml(`${kind}: ${origin.reason || origin.wait_type || 'н/д'}`);
}

function renderProcessingKafka(overview, detail) {
  const topicRows = (overview.kafka?.topics || []).map((topic) => [
    escapeHtml(topic.topic),
    escapeHtml(topic.key),
    escapeHtml(topic.description),
  ]);
  const outboxRows = (detail?.outbox || []).slice(0, 12).map((message) => [
    badge(message.status),
    escapeHtml(message.topic),
    escapeHtml(message.event_type),
    escapeHtml(message.idempotency_key),
    escapeHtml(message.created_at),
  ]);
  return `
    <div class="processing-split">
      <div>
        <div class="metric-label">Топики Kafka</div>
        ${table(['Topic', 'Key', 'Назначение'], topicRows)}
      </div>
      <div>
        <div class="metric-label">Outbox выбранного кейса</div>
        ${table(['Статус', 'Topic', 'Событие', 'Idempotency key', 'Создано'], outboxRows)}
      </div>
    </div>
  `;
}

function processingRuntimeGraph(baseGraph, detail) {
  const graph = JSON.parse(JSON.stringify(baseGraph || {}));
  if (!graph.nodes) return graph;
  const run = detail?.runs?.[0] || null;
  const activeWait = (detail?.waits || []).find((wait) => ['open', 'reminded'].includes(wait.status));
  const activeStep = activeWait ? 'waiting' : run?.current_step;
  const runStatus = run?.status || 'unknown';
  const order = ['slot_filling', 'classification', 'react_planning', 'tool_use', 'decision', 'waiting'];
  const activeIndex = Math.max(order.indexOf(activeStep), 0);
  graph.title = 'Runtime-граф обработки';
  graph.nodes = graph.nodes.map((node) => {
    const index = order.indexOf(node.id);
    let status = index >= 0 && index < activeIndex ? 'completed' : 'pending';
    if (node.id === activeStep) {
      status = runStatus === 'failed' ? 'error' : activeWait ? 'waiting' : 'running';
    }
    if (runStatus === 'completed' && node.id === 'decision') {
      status = 'completed';
    }
    if (runStatus === 'escalated' && node.id === 'decision') {
      status = 'escalated';
    }
    return {
      ...node,
      status,
      metrics: [
        ...(node.metrics || []),
        ...(node.id === activeStep && run ? [
          { label: 'Run', value: run.run_id },
          { label: 'Статус', value: run.status },
        ] : []),
      ],
    };
  });
  return graph;
}

async function runProcessingCommand(path, successMessage) {
  if (!window.confirm('Выполнить административное действие с записью в audit?')) {
    return;
  }
  await api(path, {
    method: 'POST',
    body: JSON.stringify({
      operator_id: state.actorId,
      reason: 'Команда администратора из UI потока обработки.',
    }),
  });
  setNotice(successMessage, 'success');
  await renderProcessing();
}

async function renderKnowledge() {
  const [status, sources, chunks] = await Promise.all([
    api('/admin/knowledge/status'),
    api('/admin/knowledge/sources'),
    api('/admin/knowledge/chunks?limit=20'),
  ]);
  const sourceNames = Object.fromEntries(
    (sources.sources || []).map((source) => [source.source_id, source.display_name || source.path || source.source_id]),
  );
  const sourceRows = (sources.sources || []).map((source) => [
    badge(source.enabled ? 'enabled' : 'disabled'),
    escapeHtml(source.connector_type),
    escapeHtml(source.display_name || source.path || source.disabled_reason || 'н/д'),
  ]);
  const chunkRows = (chunks.chunks || []).map((chunk) => [
    escapeHtml(sourceNames[chunk.source_id] || 'н/д'),
    escapeHtml((chunk.text || '').slice(0, 180)),
  ]);
  elements.viewContent.innerHTML = [
    section(
      'Статус индекса',
      `<div class="grid">
        ${metric('Статус', badge(status.status || status.index_manifest?.status))}
        ${metric('Документы', String(status.index_manifest?.document_count ?? 0))}
        ${metric('Фрагменты', String(status.index_manifest?.chunk_count ?? 0))}
        ${metric('Путь', escapeHtml(status.index_path || 'н/д'))}
      </div>`,
      '<button class="primary" type="button" data-action="knowledge-rebuild">Перестроить</button>',
    ),
    section(
      'Тестовый поиск',
      `<form class="toolbar compact" data-form="retrieval">
        <label>Запрос<input name="query" value="billing-worker restart runbook"></label>
        <label>Количество результатов<input name="top_k" type="number" min="1" max="10" value="3"></label>
        <button type="submit">Искать</button>
      </form>
      <div id="retrievalResult"><div class="empty">Результат поиска появится здесь</div></div>`,
    ),
    section('Источники', table(['Статус', 'Коннектор', 'Описание'], sourceRows)),
    section('Фрагменты', table(['Источник', 'Текст'], chunkRows)),
  ].join('');
}

async function loadExecutionCatalogContext({ includeAudit = false } = {}) {
  const requests = [
    api('/admin/config/active/tools'),
    api('/admin/config/active/integration_endpoints'),
    api('/admin/config/active/n8n_workflows'),
    api('/admin/config/active/tool_launch_matrix'),
    api('/admin/config/active/attribute_resolution_profiles'),
    api('/admin/config/active/slot_autofill_profiles'),
    api('/admin/config/active/interaction_channels'),
  ];
  if (includeAudit) {
    requests.push(api('/admin/security/audit?limit=30'));
  }
  const [toolsActive, endpointsActive, n8nActive, matrixActive, resolutionActive, slotAutofillActive, channelsActive, audit] = await Promise.all(requests);
  const context = {
    tools: toolsActive.payload?.tools || [],
    endpoints: endpointsActive.payload?.endpoints || [],
    workflows: n8nActive.payload?.workflows || [],
    matrices: matrixActive.payload?.matrices || [],
    resolutionProfiles: resolutionActive.payload?.profiles || [],
    slotAutofillProfiles: slotAutofillActive.payload?.profiles || [],
    channels: channelsActive.payload?.channels || [],
    audit: audit || { events: [] },
  };
  state.lastData.toolCatalog = context.tools;
  state.lastData.integrationEndpoints = context.endpoints;
  state.lastData.n8nWorkflows = context.workflows;
  if (!context.endpoints.some((endpoint) => endpoint.endpoint_id === state.integrationEndpointId)) {
    state.integrationEndpointId = context.endpoints[0]?.endpoint_id || '';
  }
  if (!context.tools.some((tool) => tool.tool_name === state.toolCatalogName)) {
    state.toolCatalogName = context.tools[0]?.tool_name || '';
  }
  if (!context.tools.some((tool) => tool.tool_name === state.operationBindingToolName)) {
    state.operationBindingToolName = state.toolCatalogName || context.tools[0]?.tool_name || '';
  }
  const selectedBindingTool = context.tools.find((tool) => tool.tool_name === state.operationBindingToolName);
  const currentBinding = currentToolBinding(selectedBindingTool);
  const bindingToolChanged = state.operationBindingLastToolName !== state.operationBindingToolName;
  if (bindingToolChanged) {
    state.operationBindingLastToolName = state.operationBindingToolName;
    state.operationBindingEndpointId = currentBinding?.endpoint_id || context.endpoints[0]?.endpoint_id || '';
    state.operationBindingOperationId = currentBinding?.operation_id || '';
  } else if (!context.endpoints.some((endpoint) => endpoint.endpoint_id === state.operationBindingEndpointId)) {
    state.operationBindingEndpointId = currentBinding?.endpoint_id || context.endpoints[0]?.endpoint_id || '';
  }
  const selectedEndpoint = context.endpoints.find((endpoint) => endpoint.endpoint_id === state.operationBindingEndpointId);
  const operationIds = Object.keys(selectedEndpoint?.operations || {});
  if (!operationIds.includes(state.operationBindingOperationId)) {
    state.operationBindingOperationId = currentBinding?.endpoint_id === state.operationBindingEndpointId
      && currentBinding?.operation_id
      && operationIds.includes(currentBinding.operation_id)
      ? currentBinding.operation_id
      : operationIds[0] || '';
  }
  return context;
}

async function renderIntegrations() {
  const { tools, endpoints, workflows, audit } = await loadExecutionCatalogContext({ includeAudit: true });
  const selectedEndpoint = endpoints.find((endpoint) => endpoint.endpoint_id === state.integrationEndpointId) || null;
  const n8nRows = workflows.map((workflow) => [
    badge(workflow.enabled ? 'enabled' : 'disabled'),
    escapeHtml(workflow.business_scenario),
    escapeHtml(workflow.endpoint_id),
    escapeHtml((workflow.operations || []).join(', ')),
  ]);
  const auditRows = (audit.events || [])
    .filter((event) => ['tools.dispatch', 'callbacks.receive'].includes(event.action))
    .map((event) => [
      escapeHtml(event.created_at),
      escapeHtml(event.action),
      badge(event.outcome),
      escapeHtml(event.resource_id || 'н/д'),
      escapeHtml(event.actor_id),
    ]);
  elements.viewContent.innerHTML = [
    section('Подключения по типу адаптера', renderEndpointConnectionGroups(endpoints)),
    section(
      'Подключение и операции',
      `${endpointConnectionControls(endpoints)}
      ${renderEndpointConnectionEditor({
        endpoint: selectedEndpoint,
        endpoints,
        tools,
        workflows,
      })}`,
    ),
    section('Рабочие процессы n8n', table(['Статус', 'Сценарий', 'Точка интеграции', 'Операции'], n8nRows)),
    section('История вызовов и callbacks', table(['Время', 'Действие', 'Результат', 'Ресурс', 'Инициатор'], auditRows)),
  ].join('');
  attachCatalogSelect('integrationEndpointSelect', 'integrationEndpointId', renderIntegrations);
}

async function renderReactCalls() {
  const { tools, matrices, resolutionProfiles, slotAutofillProfiles, channels } = await loadExecutionCatalogContext();
  const selectedTool = tools.find((tool) => tool.tool_name === state.toolCatalogName) || null;
  elements.viewContent.innerHTML = [
    section(
      'ReAct-вызовы ИИ',
      `${toolCatalogControls(tools)}
      ${renderToolCatalogEditor({
        tool: selectedTool,
        tools,
        matrices,
        resolutionProfiles,
        slotAutofillProfiles,
        channels,
      })}`,
    ),
  ].join('');
  attachCatalogSelect('toolCatalogSelect', 'toolCatalogName', renderReactCalls);
}

async function renderOperationBindings() {
  const { tools, endpoints, matrices, resolutionProfiles, slotAutofillProfiles, channels } = await loadExecutionCatalogContext();
  const selectedTool = state.operationBindingMode === 'create'
    ? null
    : tools.find((tool) => tool.tool_name === state.operationBindingToolName) || null;
  elements.viewContent.innerHTML = [
    section(
      'Привязка операций',
      `${operationBindingControls(tools)}
      ${state.operationBindingMode === 'create'
        ? renderOperationBindingCreateEditor({ tools, endpoints })
        : renderOperationBindingEditor({
          tool: selectedTool,
          tools,
          endpoints,
          matrices,
          resolutionProfiles,
          slotAutofillProfiles,
          channels,
        })}`,
    ),
  ].join('');
  attachCatalogSelect('operationBindingToolSelect', 'operationBindingToolName', renderOperationBindings);
}

function endpointConnectionControls(endpoints) {
  return `
    <div class="toolbar compact">
      <label>Подключение<select id="integrationEndpointSelect">${endpointGroupedOptions(endpoints, state.integrationEndpointId)}</select></label>
    </div>
    <div class="scenario-menu">
      <button type="button" class="${state.integrationEndpointOperation === 'create' ? 'primary' : ''}" data-action="endpoint-connection-operation" data-operation="create">Создать</button>
      <button type="button" class="${state.integrationEndpointOperation === 'modify' ? 'primary' : ''}" data-action="endpoint-connection-operation" data-operation="modify">Модифицировать</button>
      <button type="button" class="${state.integrationEndpointOperation === 'delete' ? 'primary' : ''}" data-action="endpoint-connection-operation" data-operation="delete">Удалить</button>
    </div>
  `;
}

function toolCatalogControls(tools) {
  return `
    <div class="toolbar compact">
      <label>ReAct-вызов ИИ<select id="toolCatalogSelect">${referenceOptions(tools, 'tool_name', state.toolCatalogName, reactCallLabel)}</select></label>
    </div>
    <div class="scenario-menu">
      <button type="button" class="${state.toolCatalogOperation === 'create' ? 'primary' : ''}" data-action="tool-catalog-operation" data-operation="create">Создать</button>
      <button type="button" class="${state.toolCatalogOperation === 'modify' ? 'primary' : ''}" data-action="tool-catalog-operation" data-operation="modify">Модифицировать</button>
      <button type="button" class="${state.toolCatalogOperation === 'delete' ? 'primary' : ''}" data-action="tool-catalog-operation" data-operation="delete">Удалить</button>
    </div>
  `;
}

function operationBindingControls(tools) {
  return `
    <div class="scenario-menu">
      <button type="button" class="${state.operationBindingMode === 'bind' ? 'primary' : ''}" data-action="operation-binding-mode" data-mode="bind">Привязать существующий</button>
      <button type="button" class="${state.operationBindingMode === 'create' ? 'primary' : ''}" data-action="operation-binding-mode" data-mode="create">Создать и привязать ReAct-вызов ИИ</button>
    </div>
    ${state.operationBindingMode === 'bind' ? `
      <div class="toolbar compact">
        <label>ReAct-вызов ИИ<select id="operationBindingToolSelect">${referenceOptions(tools, 'tool_name', state.operationBindingToolName, reactCallLabel)}</select></label>
      </div>
    ` : ''}
  `;
}

function reactCallLabel(tool) {
  return tool?.description ? `${tool.tool_name} — ${tool.description}` : tool?.tool_name || '';
}

function operationBindingLabel(binding) {
  if (!binding) return 'привязка не выбрана';
  return `${binding.endpoint_id || 'подключение не выбрано'} / ${binding.operation_id || 'операция не выбрана'}`;
}

function endpointGroupedOptions(endpoints, selectedId) {
  const groups = endpointAdapterGroups(endpoints);
  if (!groups.length) {
    return '<option value="">Нет подключений</option>';
  }
  return groups.map(({ adapterType, items }) => `
    <optgroup label="${escapeHtml(visibleLabels[adapterType] || adapterType)}">
      ${items.map((endpoint) => `<option value="${escapeHtml(endpoint.endpoint_id)}" ${endpoint.endpoint_id === selectedId ? 'selected' : ''}>${escapeHtml(endpointLabel(endpoint))}</option>`).join('')}
    </optgroup>
  `).join('');
}

function endpointAdapterGroups(endpoints) {
  const order = ['mock', 'n8n_webhook', 'direct_http', 'queue'];
  const groups = new Map();
  for (const endpoint of endpoints || []) {
    const key = endpoint.adapter_type || 'unknown';
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key).push(endpoint);
  }
  return Array.from(groups.entries())
    .sort(([left], [right]) => {
      const leftIndex = order.indexOf(left);
      const rightIndex = order.indexOf(right);
      return (leftIndex < 0 ? 99 : leftIndex) - (rightIndex < 0 ? 99 : rightIndex) || left.localeCompare(right);
    })
    .map(([adapterType, items]) => ({
      adapterType,
      items: items.sort((left, right) => endpointLabel(left).localeCompare(endpointLabel(right), 'ru')),
    }));
}

function renderEndpointConnectionGroups(endpoints) {
  const groups = endpointAdapterGroups(endpoints);
  if (!groups.length) {
    return '<div class="empty">Точки интеграции не настроены.</div>';
  }
  return `
    <div class="endpoint-group-grid">
      ${groups.map(({ adapterType, items }) => `
        <div class="endpoint-group panel">
          <div class="metric-label">${escapeHtml(visibleLabels[adapterType] || adapterType)}</div>
          <div class="endpoint-connection-list">
            ${items.map((endpoint) => `
              <div class="endpoint-connection-card">
                <div>
                  <strong>${escapeHtml(endpoint.display_name || endpoint.endpoint_id)}</strong>
                  <span>${escapeHtml(endpoint.endpoint_id)} · ${badge(endpoint.enabled ? 'enabled' : 'disabled')}</span>
                </div>
                <div class="meta">${escapeHtml(operationSummary(endpoint))}</div>
              </div>
            `).join('')}
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

function endpointLabel(endpoint) {
  if (!endpoint) return 'подключение не выбрано';
  return endpoint.display_name ? `${endpoint.display_name} (${endpoint.endpoint_id})` : endpoint.endpoint_id;
}

function operationLabel(operationId, operation = {}) {
  return operation.display_name ? `${operation.display_name} (${operationId})` : operationId;
}

function defaultOperationRequestSchema() {
  return {
    type: 'object',
    additionalProperties: true,
  };
}

function defaultOperationResponseSchema() {
  return {
    type: 'object',
    additionalProperties: true,
  };
}

function operationSummary(endpoint) {
  const entries = Object.entries(endpoint?.operations || {});
  if (!entries.length) return 'операции не настроены';
  return entries
    .map(([operationId, operation]) => `${operationLabel(operationId, operation)}: ${operation.method} ${operation.path}`)
    .join(', ');
}

function defaultOpenApiContractSource() {
  return {
    type: 'openapi_3_1',
    enabled: true,
    method: 'GET',
    url: 'contracts/openapi.json',
  };
}

function endpointContractSource(endpoint = {}) {
  return {
    ...defaultOpenApiContractSource(),
    ...(endpoint.contract_source || {}),
  };
}

function renderEndpointContractSourceEditor(endpoint = {}) {
  if (endpoint.adapter_type !== 'n8n_webhook') {
    return '';
  }
  const source = endpointContractSource(endpoint);
  return `
    <fieldset class="launch-editor">
      <legend>OpenAPI 3.1 контракт n8n</legend>
      <div class="meta">Источник читает JSON-контракт n8n и заполняет операции подключения. Относительный URL считается от базового URL endpoint, например base_url /webhook + contracts/openapi.json = /webhook/contracts/openapi.json.</div>
      <div class="grid three">
        <label>Использовать OpenAPI<select name="contract_source_enabled">${booleanOptions(source.enabled !== false)}</select></label>
        <label>Метод<select name="contract_source_method">${optionList(['GET'], source.method || 'GET')}</select></label>
        <label>URL контракта<input name="contract_source_url" value="${escapeHtml(source.url || '')}" autocomplete="off" placeholder="contracts/openapi.json"></label>
      </div>
      <div class="scenario-editor-actions">
        <button type="button" data-action="endpoint-openapi-preview">Загрузить операции из OpenAPI</button>
        <span class="meta" data-openapi-preview-status>Операции будут заменены данными из контракта в форме. Используемые старые операции сохраняются, чтобы не сломать связи.</span>
      </div>
    </fieldset>
  `;
}

function usageListPanel(title, refs, emptyText) {
  const items = refs || [];
  return `
    <div class="slot-schema-derived">
      <div class="metric-label">${escapeHtml(title)}</div>
      ${items.length
        ? `<ul class="usage-list">${items.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`
        : `<div class="meta">${escapeHtml(emptyText)}</div>`}
    </div>
  `;
}

function integrationEndpointUsage(endpointId, tools, workflows) {
  const refs = [];
  for (const tool of tools || []) {
    for (const binding of tool.endpoint_bindings || []) {
      if (binding.endpoint_id === endpointId) {
        refs.push(`ReAct-вызов ИИ "${tool.tool_name}", операция "${binding.operation_id}"`);
      }
    }
  }
  for (const workflow of workflows || []) {
    if (workflow.endpoint_id === endpointId) {
      refs.push(`n8n workflow "${workflow.display_name || workflow.workflow_id}" как основной endpoint`);
    }
    if (workflow.callback_endpoint_id === endpointId) {
      refs.push(`n8n workflow "${workflow.display_name || workflow.workflow_id}" как callback endpoint`);
    }
  }
  return refs;
}

function integrationOperationUsage(endpointId, operationId, tools, workflows) {
  const refs = [];
  for (const tool of tools || []) {
    for (const binding of tool.endpoint_bindings || []) {
      if (binding.endpoint_id === endpointId && binding.operation_id === operationId) {
        refs.push(`ReAct-вызов ИИ "${tool.tool_name}"`);
      }
    }
  }
  for (const workflow of workflows || []) {
    if (workflow.endpoint_id === endpointId && (workflow.operations || []).includes(operationId)) {
      refs.push(`n8n workflow "${workflow.display_name || workflow.workflow_id}"`);
    }
  }
  return refs;
}

function operationDeleteDisabledReason(usage) {
  if (!usage?.length) {
    return 'Операцию можно удалить.';
  }
  return `Нельзя удалить: сначала уберите связи: ${usage.join('; ')}.`;
}

function endpointCreateTemplate(source, endpoints) {
  const template = source || endpoints[0] || {};
  const adapterType = activeEndpointAdapterTypes.includes(template.adapter_type) ? template.adapter_type : 'mock';
  return {
    endpoint_id: nextConfigItemId(template.endpoint_id || 'custom.endpoint', endpoints, 'endpoint_id'),
    adapter_type: adapterType,
    display_name: '',
    enabled: true,
    disabled_reason: '',
    base_url: template.base_url || '',
    base_url_env: template.base_url_env || '',
    auth: template.auth || { type: 'none' },
    contract_source: adapterType === 'n8n_webhook'
      ? endpointContractSource(template)
      : undefined,
    operations: {
      custom_operation: {
        display_name: 'Новая операция',
        description: 'Опишите назначение операции.',
        method: 'POST',
        path: '/custom/operation',
        request_schema: defaultOperationRequestSchema(),
        response_schema: defaultOperationResponseSchema(),
        async_event_contracts: {},
        contract_version: '1.0',
        contract_status: 'draft',
        timeout_seconds: 10,
      },
    },
  };
}

function renderEndpointConnectionEditor({ endpoint, endpoints, tools, workflows }) {
  if (state.integrationEndpointOperation === 'delete') {
    if (!endpoint?.endpoint_id) {
      return '<div class="empty">Нет выбранного подключения для удаления</div>';
    }
    const usage = integrationEndpointUsage(endpoint.endpoint_id, tools, workflows);
    return `
      <form class="scenario-editor panel" data-form="integration-endpoint-delete">
        <div>
          <div class="metric-label">Удаляемое подключение</div>
          <div class="scenario-title">${escapeHtml(endpointLabel(endpoint))}</div>
        </div>
        ${usageListPanel('Где используется', usage, 'Не используется. Подключение можно удалить.')}
        <button class="danger" type="submit" ${usage.length ? 'disabled' : ''}>Удалить подключение</button>
      </form>
    `;
  }
  const current = state.integrationEndpointOperation === 'create'
    ? endpointCreateTemplate(endpoint, endpoints)
    : endpoint;
  if (!current?.endpoint_id) {
    return '<div class="empty">Подключение не выбрано</div>';
  }
  const operationCount = Object.keys(current.operations || {}).length;
  const operationCards = Object.entries(current.operations || {})
    .map(([operationId, operation], index) => renderEndpointOperationCard({
      endpointId: current.endpoint_id,
      adapterType: current.adapter_type,
      operationId,
      operation,
      tools,
      workflows,
      open: index === 0,
    }))
    .join('');
  return `
    <form class="scenario-editor panel" data-form="integration-endpoint-editor">
      <div class="grid two">
        <label>Техническое имя подключения
          <input name="endpoint_id" value="${escapeHtml(current.endpoint_id)}" autocomplete="off" ${state.integrationEndpointOperation === 'modify' ? 'readonly' : ''}>
          <span class="field-help">Стабильный ключ подключения. Используется в логах, bindings и callback URL.</span>
        </label>
        <label>Название<input name="display_name" value="${escapeHtml(current.display_name || '')}" autocomplete="off"></label>
        <label>Тип адаптера<select name="adapter_type">${activeOptionList(activeEndpointAdapterTypes, current.adapter_type)}</select></label>
        <label>Включен<select name="enabled">${booleanOptions(current.enabled)}</select></label>
        <label>Причина отключения<input name="disabled_reason" value="${escapeHtml(current.disabled_reason || '')}" autocomplete="off"></label>
        <label>Базовый URL<input name="base_url" value="${escapeHtml(current.base_url || '')}" autocomplete="off" placeholder="http://127.0.0.1:5678/webhook"></label>
        <label>Env-переменная базового URL<input name="base_url_env" value="${escapeHtml(current.base_url_env || '')}" autocomplete="off" placeholder="N8N_WEBHOOK_BASE_URL"></label>
        <label>Тип авторизации<select name="auth_type">${optionList(['none', 'header_token', 'bearer_token'], current.auth?.type || 'none')}</select></label>
        <label>Имя заголовка<input name="auth_header_name" value="${escapeHtml(current.auth?.header_name || '')}" autocomplete="off" placeholder="X-ServiceDesk-Token"></label>
        <label>Env-переменная токена<input name="auth_token_env" value="${escapeHtml(current.auth?.token_env || '')}" autocomplete="off" placeholder="N8N_WEBHOOK_TOKEN"></label>
      </div>
      ${renderEndpointContractSourceEditor(current)}
      <details class="launch-editor endpoint-operations-toggle" data-endpoint-operations-section>
        <summary class="endpoint-operations-summary">
          <div class="slot-card-summary-main">
            <strong>Операции подключения</strong>
            <span>${escapeHtml(operationCount ? `Настроено операций: ${operationCount}` : 'Операции не настроены')}</span>
          </div>
        </summary>
        <div class="meta">Операция описывает конкретный технический вызов: путь webhook, HTTP-метод, topic или тестовый ответ mock.</div>
        <div id="endpointOperationCards" class="slot-card-list">${operationCards}</div>
        <button type="button" data-action="endpoint-operation-add">Добавить операцию</button>
      </details>
      ${usageListPanel('Где используется', integrationEndpointUsage(current.endpoint_id, tools, workflows), 'Не используется. Подключение можно удалить.')}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">${state.integrationEndpointOperation === 'create' ? 'Создать подключение' : 'Сохранить подключение'}</button>
      </div>
    </form>
  `;
}

function schemaRequiredSet(schema = {}) {
  return new Set(Array.isArray(schema.required) ? schema.required : []);
}

function schemaPropertyType(property = {}) {
  if (property.type === 'array') return 'array';
  if (property.type === 'object' || property.properties || property.additionalProperties) return 'object';
  return operationContractTypes.includes(property.type) ? property.type : 'string';
}

function schemaArrayItemType(property = {}) {
  const itemType = property.items?.type;
  return operationArrayItemTypes.includes(itemType) ? itemType : 'object';
}

function operationSchemaFields(schema = {}) {
  const required = schemaRequiredSet(schema);
  return Object.entries(schema.properties || {}).map(([fieldName, property]) => ({
    name: fieldName,
    title: property.title || humanizeTechnicalKey(fieldName),
    type: schemaPropertyType(property),
    item_type: schemaArrayItemType(property),
    required: required.has(fieldName),
    description: property.description || '',
    minLength: property.minLength ?? '',
    minimum: property.minimum ?? '',
    maximum: property.maximum ?? '',
  }));
}

function operationSchemaIsSimple(schema = {}) {
  if (!schema || schema.type !== 'object' || !schema.properties) {
    return schema?.type === 'object' || !Object.keys(schema || {}).length;
  }
  return Object.values(schema.properties || {}).every((property) => {
    if (property.anyOf || property.oneOf || property.allOf || property.$ref) return false;
    const type = schemaPropertyType(property);
    if (!operationContractTypes.includes(type)) return false;
    if (type === 'array') {
      return !property.items?.anyOf && !property.items?.oneOf && !property.items?.allOf && !property.items?.$ref;
    }
    return true;
  });
}

function operationSchemaEmpty(kind) {
  return `<div class="empty" data-operation-schema-empty>${kind === 'request' ? 'Входные параметры не настроены.' : 'Поля ответа не настроены.'}</div>`;
}

function renderOperationSchemaFieldRow(kind, field = {}) {
  const current = {
    name: '',
    title: '',
    type: 'string',
    item_type: 'object',
    required: false,
    description: '',
    minLength: '',
    minimum: '',
    maximum: '',
    ...field,
  };
  return `
    <div class="contract-field-row" data-operation-field-row data-schema-kind="${escapeHtml(kind)}">
      <div class="grid two">
        <label>Имя поля
          <input data-operation-contract-control data-operation-field-name value="${escapeHtml(current.name)}" autocomplete="off" placeholder="${kind === 'request' ? 'login' : 'message'}">
          <span class="field-help">Техническое имя параметра в payload endpoint. Используйте латиницу, цифры и подчеркивание.</span>
        </label>
        <label>Название
          <input data-operation-contract-control data-operation-field-title value="${escapeHtml(current.title)}" autocomplete="off">
          <span class="field-help">Понятное название для администратора. В JSON попадет как title.</span>
        </label>
        <label>Тип
          <select data-operation-contract-control data-operation-field-type>${optionList(operationContractTypes, current.type, operationContractTypeLabels)}</select>
          <span class="field-help">Тип проверяется при сохранении mock-ответа и JSON Schema.</span>
        </label>
        <label>Обязательное
          <select data-operation-contract-control data-operation-field-required>${booleanOptions(current.required)}</select>
          <span class="field-help">Поле попадет в required выбранной JSON Schema.</span>
        </label>
      </div>
      <label>Описание
        <textarea data-operation-contract-control data-operation-field-description rows="2">${escapeHtml(current.description)}</textarea>
      </label>
      <details class="slot-schema-derived">
        <summary>Дополнительные ограничения</summary>
        <div class="grid three">
          <label>Тип элемента массива
            <select data-operation-contract-control data-operation-field-item-type>${optionList(operationArrayItemTypes, current.item_type, operationContractTypeLabels)}</select>
          </label>
          <label>Минимальная длина строки
            <input data-operation-contract-control data-operation-field-min-length type="number" min="0" value="${escapeHtml(current.minLength)}">
          </label>
          <label>Минимум числа
            <input data-operation-contract-control data-operation-field-minimum type="number" value="${escapeHtml(current.minimum)}">
          </label>
          <label>Максимум числа
            <input data-operation-contract-control data-operation-field-maximum type="number" value="${escapeHtml(current.maximum)}">
          </label>
        </div>
      </details>
      <button class="danger" type="button" data-action="endpoint-${kind}-field-remove">Удалить поле</button>
    </div>
  `;
}

function renderOperationSchemaEditor(kind, title, schema = {}) {
  const fields = operationSchemaFields(schema);
  const rows = fields.length
    ? fields.map((field) => renderOperationSchemaFieldRow(kind, field)).join('')
    : operationSchemaEmpty(kind);
  const warning = operationSchemaIsSimple(schema)
    ? ''
    : '<div class="empty">Контракт содержит сложную JSON Schema. UI покажет поддерживаемую часть; для сложной схемы используйте JSON контрольную точку.</div>';
  return `
    <fieldset class="launch-editor" data-operation-schema-editor="${escapeHtml(kind)}">
      <legend>${escapeHtml(title)}</legend>
      <div class="meta">${kind === 'request'
        ? 'Параметры, которые adapter получает на входе операции.'
        : 'Поля, которые endpoint возвращает после выполнения операции.'}</div>
      ${warning}
      <div class="contract-field-list" data-operation-schema-rows>${rows}</div>
      <button type="button" data-action="endpoint-${kind}-field-add">Добавить поле</button>
    </fieldset>
  `;
}

function mockInputValue(value) {
  if (value === undefined || value === null) return '';
  if (typeof value === 'object') return jsonPretty(value);
  return String(value);
}

function renderOperationMockRow(field, mockOutput = {}) {
  const value = mockOutput?.[field.name];
  const commonAttrs = `data-operation-mock-control data-mock-field-value data-mock-field-name="${escapeHtml(field.name)}" data-mock-field-type="${escapeHtml(field.type)}" data-mock-field-required="${field.required ? 'true' : 'false'}"`;
  let control = '';
  if (field.type === 'boolean') {
    const selected = value === true ? 'true' : value === false ? 'false' : '';
    control = `
      <select ${commonAttrs}>
        <option value="" ${selected === '' ? 'selected' : ''}>не заполнено</option>
        <option value="true" ${selected === 'true' ? 'selected' : ''}>true</option>
        <option value="false" ${selected === 'false' ? 'selected' : ''}>false</option>
      </select>
    `;
  } else if (field.type === 'integer' || field.type === 'number') {
    control = `<input ${commonAttrs} type="number" ${field.type === 'number' ? 'step="any"' : 'step="1"'} value="${escapeHtml(mockInputValue(value))}">`;
  } else if (field.type === 'array' || field.type === 'object') {
    control = `<textarea ${commonAttrs} rows="4" placeholder="${field.type === 'array' ? '[]' : '{}'}">${escapeHtml(mockInputValue(value))}</textarea>`;
  } else {
    control = `<input ${commonAttrs} value="${escapeHtml(mockInputValue(value))}" autocomplete="off">`;
  }
  return `
    <div class="contract-field-row" data-operation-mock-row>
      <div class="parameter-binding-meta">
        <strong>${escapeHtml(field.title || field.name)}</strong>
        <span>${escapeHtml(field.name)} · ${escapeHtml(operationContractTypeLabels[field.type] || field.type)}${field.required ? ' · обязательное' : ''}</span>
      </div>
      <label>Значение mock
        ${control}
        <span class="field-help">Значение будет включено в тестовый ответ mock_output и проверено по контракту ответа.</span>
      </label>
    </div>
  `;
}

function renderOperationMockRows(responseSchema = {}, mockOutput = {}) {
  const fields = operationSchemaFields(responseSchema);
  if (!fields.length) {
    return '<div class="empty">Добавьте поля ответа операции, чтобы заполнить тестовый ответ mock.</div>';
  }
  return fields.map((field) => renderOperationMockRow(field, mockOutput)).join('');
}

function renderOperationMockEditor(adapterType, responseSchema = {}, mockOutput = {}) {
  if (adapterType !== 'mock') {
    return '';
  }
  return `
    <fieldset class="launch-editor" data-operation-mock-editor>
      <legend>Тестовый ответ mock</legend>
      <div class="meta">Форма строится из полей ответа операции. Обязательные поля должны быть заполнены.</div>
      <div class="contract-field-list" data-operation-mock-rows>${renderOperationMockRows(responseSchema, mockOutput)}</div>
    </fieldset>
  `;
}

function renderAsyncEventContractsEditor(asyncContracts = {}) {
  return `
    <fieldset class="launch-editor">
      <legend>Контракты асинхронных событий</legend>
      <div class="meta">Ключ верхнего уровня должен совпадать с expected_event_type из матрицы ReAct-вызова. result_schema проверяет success.result, progress_schema проверяет progress.result, error_schema проверяет error.error.</div>
      <label>async_event_contracts JSON
        <textarea name="operation_async_event_contracts" rows="9">${escapeHtml(jsonPretty(asyncContracts || {}))}</textarea>
      </label>
    </fieldset>
  `;
}

function renderOperationJsonCheckpoint(operation = {}, adapterType = 'mock') {
  return `
    <details class="slot-card" data-operation-json-checkpoint>
      <summary class="slot-card-summary">
        <div class="slot-card-summary-main">
          <strong>JSON контрольная точка</strong>
          <span>Итоговые request_schema, response_schema и mock_output для backend-валидации.</span>
        </div>
      </summary>
      <div class="slot-card-body">
        <label>JSON входа
          <textarea name="operation_request_schema" data-operation-json-kind="request" rows="7">${escapeHtml(jsonPretty(operation.request_schema || defaultOperationRequestSchema()))}</textarea>
        </label>
        <label>JSON ответа
          <textarea name="operation_response_schema" data-operation-json-kind="response" rows="7">${escapeHtml(jsonPretty(operation.response_schema || defaultOperationResponseSchema()))}</textarea>
        </label>
        <label>JSON тестового ответа${adapterType === 'mock' ? ' mock' : ''}
          <textarea name="operation_mock_output" data-operation-json-kind="mock" rows="5">${operation.mock_output ? escapeHtml(jsonPretty(operation.mock_output)) : ''}</textarea>
        </label>
        <button type="button" data-action="endpoint-operation-json-apply">Применить JSON в форму</button>
      </div>
    </details>
  `;
}

function renderEndpointOperationCard({ endpointId, adapterType = 'mock', operationId, operation = {}, tools = [], workflows = [], open = false }) {
  const usage = integrationOperationUsage(endpointId, operationId, tools, workflows);
  const deleteReason = operationDeleteDisabledReason(usage);
  const requestSchema = operation.request_schema || defaultOperationRequestSchema();
  const responseSchema = operation.response_schema || defaultOperationResponseSchema();
  return `
    <details class="slot-card" data-endpoint-operation-card${open ? ' open' : ''}>
      <summary class="slot-card-summary">
        <div class="slot-card-summary-main">
          <strong>${escapeHtml(operation.display_name || operationId || 'Новая операция')}</strong>
          <span>${escapeHtml(operationId || 'operation_id')} · ${escapeHtml(operation.method || 'POST')} ${escapeHtml(operation.path || '')}${usage.length ? ` · используется: ${escapeHtml(usage.join('; '))}` : ''}</span>
        </div>
        <button class="danger slot-delete-button" type="button" data-action="endpoint-operation-remove" title="${escapeHtml(deleteReason)}" ${usage.length ? 'disabled' : ''}>Удалить</button>
      </summary>
      <div class="slot-card-body">
        <div class="grid two">
          <label>Техническое имя операции
            <input name="operation_id" value="${escapeHtml(operationId || '')}" autocomplete="off">
            <span class="field-help">Ключ операции внутри подключения. Используется в bindings, матрицах запуска и логах.</span>
          </label>
          <label>Название<input name="operation_display_name" value="${escapeHtml(operation.display_name || '')}" autocomplete="off"></label>
          <label>Описание<textarea name="operation_description" rows="3">${escapeHtml(operation.description || '')}</textarea></label>
          <label>Метод<select name="operation_method">${optionList(['GET', 'POST'], operation.method || 'POST')}</select></label>
          <label>Путь webhook или topic<input name="operation_path" value="${escapeHtml(operation.path || '')}" autocomplete="off"></label>
          <label>Timeout, сек<input name="operation_timeout_seconds" type="number" min="1" max="120" value="${escapeHtml(operation.timeout_seconds || 10)}"></label>
          <label>Версия контракта<input name="operation_contract_version" value="${escapeHtml(operation.contract_version || '1.0')}" autocomplete="off"></label>
          <label>Статус контракта<select name="operation_contract_status">${optionList(['draft', 'valid', 'broken', 'deprecated'], operation.contract_status || 'valid')}</select></label>
        </div>
        ${renderOperationSchemaEditor('request', 'Входные параметры операции', requestSchema)}
        ${renderOperationSchemaEditor('response', 'Поля ответа операции', responseSchema)}
        ${renderAsyncEventContractsEditor(operation.async_event_contracts || {})}
        ${renderOperationMockEditor(adapterType, responseSchema, operation.mock_output || {})}
        ${renderOperationJsonCheckpoint(operation, adapterType)}
        ${usageListPanel('Где используется операция', usage, 'Не используется. Операцию можно удалить.')}
      </div>
    </details>
  `;
}

function toolCreateTemplate(source, tools, endpoints) {
  const template = source || tools[0] || {};
  return {
    tool_name: nextConfigItemId(template.tool_name || 'custom_tool', tools, 'tool_name'),
    action_type: template.action_type || 'read_only',
    description: '',
    endpoint_bindings: [],
    parameters_schema: {
      type: 'object',
      additionalProperties: true,
    },
    result_schema: {
      type: 'object',
      additionalProperties: true,
    },
    contract_version: '1.0',
    contract_status: 'draft',
    policy: template.policy || {
      default_timeout_seconds: 10,
      retry: {
        max_attempts: 1,
        backoff_seconds: 0,
      },
      approval_required_hint: true,
      auto_execution_eligible: false,
      max_risk_level: 'medium',
    },
  };
}

function renderToolCatalogEditor({ tool, tools, matrices, resolutionProfiles, slotAutofillProfiles = [], channels }) {
  if (state.toolCatalogOperation === 'delete') {
    if (!tool?.tool_name) {
      return '<div class="empty">Нет выбранного ReAct-вызова ИИ для удаления</div>';
    }
    const usage = toolUsage(tool.tool_name, matrices, resolutionProfiles, channels, slotAutofillProfiles);
    return `
      <form class="scenario-editor panel" data-form="tool-catalog-delete">
        <div>
          <div class="metric-label">Удаляемый ReAct-вызов ИИ</div>
          <div class="scenario-title">${escapeHtml(tool.tool_name)}</div>
        </div>
        ${usageListPanel('Где используется', usage, 'Не используется. ReAct-вызов ИИ можно удалить.')}
        <button class="danger" type="submit" ${usage.length ? 'disabled' : ''}>Удалить ReAct-вызов ИИ</button>
      </form>
    `;
  }
  const current = state.toolCatalogOperation === 'create'
    ? toolCreateTemplate(tool, tools)
    : tool;
  if (!current?.tool_name) {
    return '<div class="empty">ReAct-вызов ИИ не выбран</div>';
  }
  const policy = current.policy || {};
  const retry = policy.retry || {};
  return `
    <form class="scenario-editor panel" data-form="tool-catalog-editor">
      <div class="grid two">
        <label>Техническое имя ReAct-вызова
          <input name="tool_name" value="${escapeHtml(current.tool_name)}" autocomplete="off" ${state.toolCatalogOperation === 'modify' ? 'readonly' : ''}>
          <span class="field-help">Стабильное имя вызова, который может выбрать ИИ в ReAct-loop. Используется в матрице запуска, профилях разрешения и аудите.</span>
        </label>
        <label>Тип действия<select name="action_type">${optionList(['read_only', 'action'], current.action_type)}</select></label>
        <label>Версия контракта<input name="contract_version" value="${escapeHtml(current.contract_version || '1.0')}" autocomplete="off"></label>
        <label>Статус контракта<select name="contract_status">${optionList(['draft', 'valid', 'broken', 'deprecated'], current.contract_status || 'valid')}</select></label>
      </div>
      <label>Описание<textarea name="description" rows="3">${escapeHtml(current.description || '')}</textarea></label>
      <fieldset class="launch-editor">
        <legend>Политика ReAct-вызова</legend>
        <div class="grid two">
          <label>Таймаут по умолчанию, сек<input name="default_timeout_seconds" type="number" min="1" max="120" value="${escapeHtml(policy.default_timeout_seconds || 10)}"></label>
          <label>Максимальный риск<select name="max_risk_level">${optionList(['low', 'medium', 'high', 'critical'], policy.max_risk_level || 'medium')}</select></label>
          <label>Подсказка согласования<select name="approval_required_hint">${booleanOptions(policy.approval_required_hint)}</select></label>
          <label>Автоисполнение допустимо<select name="auto_execution_eligible">${booleanOptions(policy.auto_execution_eligible)}</select></label>
          <label>Попыток повтора<input name="retry_max_attempts" type="number" min="1" max="5" value="${escapeHtml(retry.max_attempts || 1)}"></label>
          <label>Пауза повтора, сек<input name="retry_backoff_seconds" type="number" min="0" max="30" step="0.5" value="${escapeHtml(retry.backoff_seconds ?? 0)}"></label>
        </div>
      </fieldset>
      <fieldset class="launch-editor">
        <legend>Схемы параметров и результата</legend>
        <label>JSON Schema параметров<textarea name="parameters_schema" rows="8">${escapeHtml(jsonPretty(current.parameters_schema || { type: 'object', additionalProperties: true }))}</textarea></label>
        <label>JSON Schema результата<textarea name="result_schema" rows="8">${escapeHtml(jsonPretty(current.result_schema || { type: 'object', additionalProperties: true }))}</textarea></label>
      </fieldset>
      ${usageListPanel('Где используется', toolUsage(current.tool_name, matrices, resolutionProfiles, channels, slotAutofillProfiles), 'Не используется. ReAct-вызов ИИ можно удалить.')}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">${state.toolCatalogOperation === 'create' ? 'Создать ReAct-вызов ИИ' : 'Сохранить ReAct-вызов ИИ'}</button>
      </div>
    </form>
  `;
}

function selectedOperationBinding(tool) {
  return currentToolBinding(tool);
}

function operationBindingTarget(endpoints, currentBinding = null) {
  const selectedEndpoint = endpoints.find((endpoint) => endpoint.endpoint_id === state.operationBindingEndpointId)
    || endpointForBinding(currentBinding, endpoints)
    || endpoints[0]
    || null;
  const selectedEndpointId = selectedEndpoint?.endpoint_id || '';
  const selectedOperationIds = Object.keys(selectedEndpoint?.operations || {});
  const selectedOperationId = selectedOperationIds.includes(state.operationBindingOperationId)
    ? state.operationBindingOperationId
    : (
      currentBinding?.operation_id && selectedOperationIds.includes(currentBinding.operation_id)
        ? currentBinding.operation_id
        : selectedOperationIds[0] || ''
    );
  return {
    selectedEndpoint,
    selectedEndpointId,
    selectedOperationId,
    selectedOperation: selectedEndpoint?.operations?.[selectedOperationId] || {},
  };
}

function renderOperationBindingEditor({ tool, endpoints, matrices, resolutionProfiles, slotAutofillProfiles = [], channels }) {
  if (!tool?.tool_name) {
    return '<div class="empty">ReAct-вызов ИИ не выбран</div>';
  }
  const currentBinding = selectedOperationBinding(tool);
  const usage = toolUsage(tool.tool_name, matrices, resolutionProfiles, channels, slotAutofillProfiles);
  const {
    selectedEndpoint,
    selectedEndpointId,
    selectedOperationId,
    selectedOperation,
  } = operationBindingTarget(endpoints, currentBinding);
  const bindingModel = operationBindingEditorModel(tool, selectedOperation, currentBinding, selectedEndpointId, selectedOperationId);
  const compatibility = operationBindingCompatibility(bindingModel.tool, selectedOperation, bindingModel.binding);
  const unbindReason = operationBindingUnbindDisabledReason(currentBinding, usage);
  const unbindDisabled = !currentBinding || usage.length;
  return `
    <form class="scenario-editor panel" data-form="operation-binding-editor">
      <div class="slot-schema-derived">
        <div class="metric-label">ReAct-вызов ИИ</div>
        <div class="meta">${escapeHtml(reactCallLabel(tool))}</div>
      </div>
      <div class="slot-schema-derived">
        <div class="metric-label">Текущая привязка</div>
        <div class="meta">${escapeHtml(operationBindingSummary(currentBinding, endpoints))}</div>
      </div>
      <div class="grid two">
        <label>Подключение
          <select name="binding_endpoint_id" data-operation-binding-endpoint>${endpointOptions(endpoints, selectedEndpointId)}</select>
        </label>
        <label>Операция
          <select name="binding_operation_id" data-operation-binding-operation>${operationOptionsForEndpoint(selectedEndpoint, selectedOperationId)}</select>
        </label>
      </div>
      <fieldset class="launch-editor">
        <legend>Входные параметры endpoint</legend>
        <div class="meta">Здесь выбирается, какие параметры endpoint-операции видит ReAct-вызов. Слоты сценария сюда не подставляются: они заполняют параметры ReAct в матрице запуска или профиле разрешения атрибута.</div>
        ${renderOperationParameterVisibilityEditor(bindingModel.tool, selectedOperation, bindingModel.binding)}
      </fieldset>
      <fieldset class="launch-editor">
        <legend>Поля ответа, доступные ReAct</legend>
        <div class="meta">Можно вернуть в ReAct-результат любой набор полей endpoint-ответа и задать для них понятные имена.</div>
        ${renderOperationResultVisibilityEditor(bindingModel.tool, selectedOperation, bindingModel.binding)}
      </fieldset>
      ${operationBindingCompatibilityPanel(compatibility)}
      ${usageListPanel('Где используется ReAct-вызов ИИ', usage, 'Не используется. Привязку можно отвязать.')}
      <div class="field-help">${escapeHtml(unbindReason)}</div>
      <div class="scenario-editor-actions">
        <button class="primary" type="submit" name="operation_binding_action" value="bind" ${!selectedEndpointId || !selectedOperationId ? 'disabled' : ''}>Привязать</button>
        <button class="danger" type="submit" name="operation_binding_action" value="unbind" title="${escapeHtml(unbindReason)}" ${unbindDisabled ? 'disabled' : ''}>Отвязать</button>
      </div>
    </form>
  `;
}

function defaultReactCallNameForOperation(operationId, tools) {
  const existing = new Set((tools || []).map((tool) => tool.tool_name));
  const base = String(operationId || 'custom_react_call')
    .toLowerCase()
    .replace(/[^a-z0-9_.-]+/g, '_')
    .replace(/^_+/, '')
    || 'custom_react_call';
  if (!existing.has(base)) {
    return base;
  }
  let candidate = `${base}_copy`;
  let index = 2;
  while (existing.has(candidate)) {
    candidate = `${base}_copy_${index}`;
    index += 1;
  }
  return candidate;
}

function defaultReactCallDescription(operationId, operation = {}) {
  const label = operation.display_name || operationId || 'endpoint-операция';
  return operation.description || `ReAct-вызов ИИ для операции "${label}".`;
}

function defaultOperationBindingPolicy(actionType, operation = {}) {
  const readOnly = actionType === 'read_only';
  return {
    default_timeout_seconds: Number(operation.timeout_seconds || 10),
    retry: {
      max_attempts: 1,
      backoff_seconds: 0,
    },
    approval_required_hint: !readOnly,
    auto_execution_eligible: readOnly,
    max_risk_level: readOnly ? 'low' : 'medium',
  };
}

function createReactCallTemplateFromOperation({ toolName, actionType, description, operation }) {
  return {
    tool_name: toolName,
    action_type: actionType,
    description,
    endpoint_bindings: [],
    parameters_schema: operationObjectSchema({}, []),
    result_schema: operationObjectSchema({}, []),
    contract_version: operation.contract_version || '1.0',
    contract_status: operation.contract_status || 'draft',
    policy: defaultOperationBindingPolicy(actionType, operation),
  };
}

function renderOperationBindingCreateEditor({ tools, endpoints }) {
  const {
    selectedEndpoint,
    selectedEndpointId,
    selectedOperationId,
    selectedOperation,
  } = operationBindingTarget(endpoints, null);
  const toolName = defaultReactCallNameForOperation(selectedOperationId, tools);
  const actionType = 'read_only';
  const templateTool = createReactCallTemplateFromOperation({
    toolName,
    actionType,
    description: defaultReactCallDescription(selectedOperationId, selectedOperation),
    operation: selectedOperation,
  });
  const bindingModel = operationBindingEditorModel(templateTool, selectedOperation, null, selectedEndpointId, selectedOperationId);
  const compatibility = operationBindingCompatibility(bindingModel.tool, selectedOperation, bindingModel.binding);
  return `
    <form class="scenario-editor panel" data-form="operation-binding-create-editor">
      <div class="slot-schema-derived">
        <div class="metric-label">Новый ReAct-вызов ИИ</div>
        <div class="meta">Создайте ReAct-вызов прямо из endpoint-операции. Имена параметров и полей результата ниже будут автоматически записаны в контракт ReAct.</div>
      </div>
      <div class="grid two">
        <label>Подключение
          <select name="binding_endpoint_id" data-operation-binding-endpoint>${endpointOptions(endpoints, selectedEndpointId)}</select>
        </label>
        <label>Операция
          <select name="binding_operation_id" data-operation-binding-operation>${operationOptionsForEndpoint(selectedEndpoint, selectedOperationId)}</select>
        </label>
        <label>Техническое имя ReAct-вызова
          <input name="tool_name" value="${escapeHtml(toolName)}" autocomplete="off">
          <span class="field-help">По умолчанию берется имя endpoint-операции. Если такое имя уже занято, добавляется суффикс.</span>
        </label>
        <label>Тип действия
          <select name="action_type">${optionList(['read_only', 'action'], actionType)}</select>
        </label>
      </div>
      <label>Описание
        <textarea name="description" rows="3">${escapeHtml(defaultReactCallDescription(selectedOperationId, selectedOperation))}</textarea>
      </label>
      <fieldset class="launch-editor">
        <legend>Входные параметры endpoint</legend>
        <div class="meta">Отметьте, какие endpoint-параметры будут параметрами нового ReAct-вызова. Константы и секреты попадут только в технический payload.</div>
        ${renderOperationParameterVisibilityEditor(bindingModel.tool, selectedOperation, bindingModel.binding)}
      </fieldset>
      <fieldset class="launch-editor">
        <legend>Поля ответа, доступные ReAct</legend>
        <div class="meta">Выберите поля endpoint-ответа, которые должен возвращать новый ReAct-вызов.</div>
        ${renderOperationResultVisibilityEditor(bindingModel.tool, selectedOperation, bindingModel.binding)}
      </fieldset>
      ${operationBindingCompatibilityPanel(compatibility)}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit" ${!selectedEndpointId || !selectedOperationId ? 'disabled' : ''}>Создать и привязать</button>
      </div>
    </form>
  `;
}

function endpointOptions(endpoints, selectedId) {
  return endpointGroupedOptions(endpoints, selectedId);
}

function operationOptionsForEndpoint(endpoint, selectedId) {
  const operations = Object.entries(endpoint?.operations || {}).map(([operationId, operation]) => ({
    value: operationId,
    label: operationLabel(operationId, operation),
  }));
  return selectOptions(operations, selectedId, 'У подключения нет операций');
}

function schemaRequired(schema = {}) {
  return Array.isArray(schema.required) ? schema.required : [];
}

function schemaProperties(schema = {}) {
  return schema.properties || {};
}

function schemaType(schema = {}) {
  const value = schema.type;
  return Array.isArray(value) ? value.find((item) => item !== 'null') : value;
}

function schemaAtPath(schema = {}, path = '') {
  if (!path) return schema;
  let current = schema;
  for (const rawPart of String(path).replaceAll('[]', '').split('.')) {
    if (!rawPart) continue;
    if (schemaType(current) === 'array') {
      current = current.items || {};
      if (/^\d+$/.test(rawPart)) continue;
    }
    current = schemaProperties(current)[rawPart];
    if (!current) return null;
  }
  return current;
}

function schemaResultFieldNames(schema = {}, prefix = '') {
  const names = [];
  for (const name of Object.keys(schemaProperties(schema))) {
    const path = prefix ? `${prefix}.${name}` : name;
    names.push(path);
    const property = schemaProperties(schema)[name] || {};
    const nestedSchema = schemaType(property) === 'array' ? (property.items || {}) : property;
    if (['object', 'array'].includes(schemaType(property)) && Object.keys(schemaProperties(nestedSchema)).length) {
      names.push(...schemaResultFieldNames(nestedSchema, path));
    }
  }
  return names;
}

function operationParameterNames(operation = {}, parameterMapping = {}) {
  const schema = operation.request_schema || defaultOperationRequestSchema();
  return Array.from(new Set([
    ...schemaRequired(schema),
    ...Object.keys(schemaProperties(schema)),
    ...Object.keys(parameterMapping || {}),
  ]));
}

function reactParameterNames(tool = {}) {
  return Array.from(new Set([
    ...schemaRequired(tool.parameters_schema || {}),
    ...Object.keys(schemaProperties(tool.parameters_schema || {})),
  ]));
}

function reactResultFieldNames(tool = {}) {
  return Array.from(new Set([
    ...schemaRequired(tool.result_schema || {}),
    ...schemaResultFieldNames(tool.result_schema || {}),
  ]));
}

function operationResponseFieldNames(operation = {}, resultMapping = {}) {
  const schema = operation.response_schema || defaultOperationResponseSchema();
  return Array.from(new Set([
    ...schemaRequired(schema),
    ...Object.keys(schemaProperties(schema)),
    ...Object.values(resultMapping || {}).filter(Boolean),
  ]));
}

function defaultVisibleParameterMapping(operation = {}) {
  const result = {};
  for (const parameterName of operationParameterNames(operation, {})) {
    result[parameterName] = `react:${parameterName}`;
  }
  return result;
}

function defaultVisibleResultMapping(operation = {}) {
  const result = {};
  for (const fieldName of operationResponseFieldNames(operation, {})) {
    result[fieldName] = fieldName;
  }
  return result;
}

function operationObjectSchema(properties, requiredNames = []) {
  return {
    type: 'object',
    additionalProperties: false,
    properties,
    required: Array.from(new Set(requiredNames)).filter(Boolean),
  };
}

function schemaPropertyForName(schema = {}, name, fallbackTitle = '') {
  const property = schemaProperties(schema)[name];
  if (property) {
    return cloneJson(property);
  }
  return {
    type: 'string',
    title: fallbackTitle || humanizeTechnicalKey(name),
  };
}

function visibleContractFromBinding(operation = {}, binding = {}) {
  const parameterProperties = {};
  const parameterRequired = [];
  const requestSchema = operation.request_schema || defaultOperationRequestSchema();
  const requestRequired = new Set(schemaRequired(requestSchema));
  for (const [endpointParameter, sourceRef] of Object.entries(binding.parameter_mapping || {})) {
    const parsed = parseBindingString(sourceRef);
    if (parsed.source !== 'react' || !parsed.value) continue;
    parameterProperties[parsed.value] = schemaPropertyForName(requestSchema, endpointParameter, parsed.value);
    if (requestRequired.has(endpointParameter)) {
      parameterRequired.push(parsed.value);
    }
  }

  const resultProperties = {};
  const resultRequired = [];
  const responseSchema = operation.response_schema || defaultOperationResponseSchema();
  const responseRequired = new Set(schemaRequired(responseSchema));
  for (const [reactField, endpointPath] of Object.entries(binding.result_mapping || {})) {
    resultProperties[reactField] = schemaPropertyForName(responseSchema, endpointPath, reactField);
    if (responseRequired.has(endpointPath)) {
      resultRequired.push(reactField);
    }
  }

  return {
    parameters_schema: operationObjectSchema(parameterProperties, parameterRequired),
    result_schema: operationObjectSchema(resultProperties, resultRequired),
  };
}

function operationBindingEditorModel(tool, operation, currentBinding, endpointId, operationId) {
  const currentSelected = currentBinding
    && currentBinding.endpoint_id === endpointId
    && currentBinding.operation_id === operationId;
  if (currentSelected) {
    return {
      tool,
      binding: currentBinding,
    };
  }
  const binding = {
    endpoint_id: endpointId,
    operation_id: operationId,
    parameter_mapping: defaultVisibleParameterMapping(operation),
    result_mapping: defaultVisibleResultMapping(operation),
  };
  return {
    tool: {
      ...tool,
      ...visibleContractFromBinding(operation, binding),
    },
    binding,
  };
}

function operationMappingSourceOptions(selected, endpointRequired = false) {
  return [
    `<option value="" ${!selected ? 'selected' : ''}>${endpointRequired ? 'не задано' : 'не использовать'}</option>`,
    ...['react', 'constant', 'secret'].map(
      (value) => `<option value="${escapeHtml(value)}" ${value === selected ? 'selected' : ''}>${escapeHtml(visibleLabels[value] || value)}</option>`,
    ),
  ].join('');
}

function renderOperationParameterVisibilityRow(parameterName, sourceRef, tool, operation, rowIndex) {
  const parsed = parseBindingString(sourceRef);
  const source = parsed.source || '';
  const value = parsed.value || '';
  const requestSchema = operation.request_schema || defaultOperationRequestSchema();
  const schema = schemaProperties(requestSchema)[parameterName] || null;
  const endpointRequired = schemaRequired(requestSchema).includes(parameterName);
  const reactRequired = source === 'react'
    ? schemaRequired(tool.parameters_schema || {}).includes(value)
    : endpointRequired;
  return `
    <div class="contract-field-row operation-contract-row" data-operation-param-row data-required="${endpointRequired ? 'true' : 'false'}">
      <input type="hidden" value="${escapeHtml(parameterName)}" data-operation-param-name>
      <div class="parameter-binding-meta">
        <strong>${escapeHtml(schemaDisplayName(parameterName, schema))}</strong>
        <span>${escapeHtml(schemaMetaLine(parameterName, schema, endpointRequired, ' параметр endpoint'))}</span>
      </div>
      <div class="grid three">
        <label>Источник значения
          <select data-operation-param-source name="operation_mapping_source_${rowIndex}">${operationMappingSourceOptions(source, endpointRequired)}</select>
        </label>
        <label data-operation-param-react-wrap ${source === 'react' ? '' : 'hidden'}>Имя параметра ReAct
          <input data-operation-param-react name="operation_mapping_react_${rowIndex}" value="${source === 'react' ? escapeHtml(value || parameterName) : escapeHtml(parameterName)}" autocomplete="off">
          <span class="field-help">Это имя увидит оркестратор. Слоты сценария настраиваются в матрице запуска или профиле разрешения атрибута.</span>
        </label>
        <label data-operation-param-react-wrap ${source === 'react' ? '' : 'hidden'}>Обязателен для ReAct
          <select data-operation-param-react-required name="operation_mapping_react_required_${rowIndex}">${booleanOptions(reactRequired)}</select>
        </label>
        <label data-operation-param-value-wrap ${source && source !== 'react' ? '' : 'hidden'}>Параметр или значение
          <input data-operation-param-value name="operation_mapping_value_${rowIndex}" value="${source && source !== 'react' ? escapeHtml(value) : ''}" autocomplete="off" placeholder="${source === 'secret' ? 'ENV_NAME' : 'значение'}">
        </label>
      </div>
    </div>
  `;
}

function renderOperationParameterVisibilityEditor(tool, operation, binding) {
  const mapping = binding?.parameter_mapping || {};
  const names = operationParameterNames(operation, mapping);
  if (!names.length) {
    return '<div class="empty" data-operation-param-mapping>У endpoint-операции нет описанных входных параметров.</div>';
  }
  const missingRequired = schemaRequired(operation.request_schema || {})
    .filter((parameterName) => !mapping[parameterName]);
  return `
    <div class="operation-contract-list" data-operation-param-mapping>
      ${names.map((name, index) => renderOperationParameterVisibilityRow(
        name,
        mapping[name] || '',
        tool,
        operation,
        index,
      )).join('')}
      ${missingRequired.length
        ? `<div class="field-help">Не заполнены обязательные параметры endpoint: ${escapeHtml(missingRequired.join(', '))}</div>`
        : ''}
    </div>
  `;
}

function resultMappingByEndpointField(resultMapping = {}) {
  const result = {};
  for (const [reactField, endpointPath] of Object.entries(resultMapping || {})) {
    if (!result[endpointPath]) {
      result[endpointPath] = reactField;
    }
  }
  return result;
}

function renderOperationResultVisibilityRow(endpointFieldName, reactFieldName, tool, operation, rowIndex) {
  const responseSchema = operation.response_schema || defaultOperationResponseSchema();
  const schema = schemaProperties(responseSchema)[endpointFieldName] || null;
  const endpointRequired = schemaRequired(responseSchema).includes(endpointFieldName);
  const included = Boolean(reactFieldName);
  const reactRequired = included
    ? schemaRequired(tool.result_schema || {}).includes(reactFieldName)
    : endpointRequired;
  return `
    <div class="contract-field-row operation-contract-row" data-operation-result-row>
      <input type="hidden" value="${escapeHtml(endpointFieldName)}" data-operation-response-field-name>
      <div class="parameter-binding-meta">
        <strong>${escapeHtml(schemaDisplayName(endpointFieldName, schema))}</strong>
        <span>${escapeHtml(schemaMetaLine(endpointFieldName, schema, endpointRequired, ' поле endpoint-ответа'))}</span>
      </div>
      <div class="grid three">
        <label>Вернуть в ReAct
          <select data-operation-result-include name="operation_result_include_${rowIndex}">${booleanOptions(included)}</select>
        </label>
        <label data-operation-result-react-wrap ${included ? '' : 'hidden'}>Имя поля результата ReAct
          <input data-operation-result-name name="operation_result_name_${rowIndex}" value="${escapeHtml(reactFieldName || endpointFieldName)}" autocomplete="off">
        </label>
        <label data-operation-result-react-wrap ${included ? '' : 'hidden'}>Обязательное поле результата
          <select data-operation-result-required name="operation_result_required_${rowIndex}">${booleanOptions(reactRequired)}</select>
        </label>
      </div>
    </div>
  `;
}

function renderOperationResultVisibilityEditor(tool, operation, binding) {
  const endpointToReact = resultMappingByEndpointField(binding?.result_mapping || {});
  const names = operationResponseFieldNames(operation, binding?.result_mapping || {});
  if (!names.length) {
    return '<div class="empty" data-operation-result-mapping>У endpoint-операции нет описанных полей ответа.</div>';
  }
  return `
    <div class="operation-contract-list" data-operation-result-mapping>
      ${names.map((name, index) => renderOperationResultVisibilityRow(
        name,
        endpointToReact[name] || '',
        tool,
        operation,
        index,
      )).join('')}
    </div>
  `;
}

function operationBindingCompatibility(tool, operation, binding) {
  const errors = [];
  const parameterMapping = binding?.parameter_mapping || {};
  const resultMapping = binding?.result_mapping || {};
  const reactParameters = new Set(reactParameterNames(tool));
  const endpointParameters = new Set(operationParameterNames(operation, parameterMapping));
  for (const required of schemaRequired(operation.request_schema || {})) {
    if (!parameterMapping[required]) {
      errors.push(`не заполнен обязательный параметр endpoint: ${required}`);
    }
  }
  for (const [endpointParameter, sourceRef] of Object.entries(parameterMapping)) {
    if (!endpointParameters.has(endpointParameter)) {
      errors.push(`маппинг ссылается на неизвестный параметр endpoint: ${endpointParameter}`);
    }
    const parsed = parseBindingString(sourceRef);
    if (parsed.source === 'react' && !reactParameters.has(parsed.value)) {
      errors.push(`маппинг параметра ${endpointParameter} ссылается на неизвестный параметр ReAct: ${parsed.value}`);
    }
  }
  const reactResultFields = new Set(reactResultFieldNames(tool));
  const endpointResponseFields = new Set(operationResponseFieldNames(operation, resultMapping));
  for (const required of schemaRequired(tool.result_schema || {})) {
    if (!resultMapping[required]) {
      errors.push(`не заполнено обязательное поле результата ReAct: ${required}`);
    }
  }
  for (const [reactField, endpointPath] of Object.entries(resultMapping)) {
    if (!reactResultFields.has(reactField)) {
      errors.push(`маппинг результата ссылается на неизвестное поле ReAct: ${reactField}`);
    }
    if (!endpointResponseFields.has(endpointPath)) {
      errors.push(`маппинг результата ${reactField} ссылается на неизвестное поле endpoint: ${endpointPath}`);
    }
  }
  return {
    status: errors.length ? 'broken' : 'valid',
    errors,
  };
}

function operationBindingCompatibilityPanel(compatibility) {
  const errors = compatibility.errors || [];
  return `
    <div class="slot-schema-derived">
      <div class="metric-label">Совместимость контрактов</div>
      <div class="meta">${badge(compatibility.status)} ${escapeHtml(errors.length ? 'Привязка требует исправления.' : 'ReAct-контракт и endpoint-контракт согласованы.')}</div>
      ${errors.length ? `<ul class="usage-list">${errors.map((error) => `<li>${escapeHtml(error)}</li>`).join('')}</ul>` : ''}
    </div>
  `;
}

function toolUsage(toolName, matrices, resolutionProfiles, channels, slotAutofillProfiles = []) {
  const refs = [];
  for (const matrix of matrices || []) {
    for (const launch of matrix.launches || []) {
      if (launch.tool_name === toolName) {
        refs.push(`Матрица "${matrix.display_name || matrix.matrix_id}", запуск "${launch.launch_id}"`);
      }
    }
  }
  for (const profile of resolutionProfiles || []) {
    if ((profile.enrichment_steps || []).some((step) => step.react_call === toolName)) {
      refs.push(`Профиль разрешения "${profile.display_name || profile.profile_id}", обогащение контекста`);
    }
  }
  for (const profile of slotAutofillProfiles || []) {
    if (profile.react_call === toolName) {
      refs.push(`Профиль автозаполнения "${profile.display_name || profile.profile_id}"`);
    }
  }
  for (const channel of channels || []) {
    for (const [label, action] of channelActionEntries(channel)) {
      if (action.tool_name === toolName) {
        refs.push(`Канал "${channel.display_name || channel.channel_id}", ${label}`);
      }
    }
  }
  return refs;
}

function operationBindingUnbindDisabledReason(currentBinding, usage) {
  if (!currentBinding) {
    return 'У ReAct-вызова ИИ нет текущей привязки операции.';
  }
  if (usage?.length) {
    return `Нельзя отвязать: сначала уберите связи: ${usage.join('; ')}.`;
  }
  return 'Привязку можно отвязать.';
}

function toolBindingUsage(toolName, endpointId, operationId, matrices, resolutionProfiles, channels, slotAutofillProfiles = []) {
  const refs = [];
  if (!toolName || !endpointId || !operationId) {
    return refs;
  }
  for (const matrix of matrices || []) {
    for (const launch of matrix.launches || []) {
      if (
        launch.tool_name === toolName
        && launch.endpoint_id === endpointId
        && launch.operation_id === operationId
      ) {
        refs.push(`Матрица "${matrix.display_name || matrix.matrix_id}", запуск "${launch.launch_id}"`);
      }
    }
  }
  for (const profile of resolutionProfiles || []) {
    if ((profile.enrichment_steps || []).some((step) => step.react_call === toolName)) {
      refs.push(`Профиль разрешения "${profile.display_name || profile.profile_id}", обогащение контекста`);
    }
  }
  for (const profile of slotAutofillProfiles || []) {
    if (profile.react_call === toolName) {
      refs.push(`Профиль автозаполнения "${profile.display_name || profile.profile_id}"`);
    }
  }
  for (const channel of channels || []) {
    for (const [label, action] of channelActionEntries(channel)) {
      if (
        action.tool_name === toolName
        && action.endpoint_id === endpointId
        && action.operation_id === operationId
      ) {
        refs.push(`Канал "${channel.display_name || channel.channel_id}", ${label}`);
      }
    }
  }
  return refs;
}

function channelActionEntries(channel) {
  const result = [
    ['доставка вопроса', channel.question_delivery || {}],
    ['незавершенное обсуждение', channel.incomplete_discussion_action || {}],
    ['эскалация', channel.escalation_action || {}],
  ];
  for (const profile of channel.action_profiles || []) {
    result.push([`профиль действия "${profile.display_name || profile.profile_id}"`, profile.action || {}]);
  }
  return result;
}

async function renderWorkflow() {
  const workflow = await api('/admin/catalog/workflow');
  const stateRows = (workflow.state_catalog?.states || []).map((item) => [
    escapeHtml(item.operator_label || item.description || 'Состояние'),
    badge(item.terminal ? 'terminal' : 'active'),
    escapeHtml(item.category || 'н/д'),
    escapeHtml(item.description || item.operator_label || 'н/д'),
  ]);
  const ruleRows = (workflow.transition_rules?.rules || []).map((rule) => [
    escapeHtml(rule.description || 'н/д'),
    escapeHtml(JSON.stringify(rule.when)),
  ]);
  elements.viewContent.innerHTML = [
    section('Состояния рабочего процесса', table(['Состояние', 'Тип', 'Категория', 'Описание'], stateRows)),
    section('Правила переходов', table(['Описание', 'Условие'], ruleRows)),
  ].join('');
}

async function renderModels() {
  const [models, active] = await Promise.all([
    api('/admin/models/config'),
    api('/admin/config/active/model_routing'),
  ]);
  const config = normalizeModelConfig(active.payload || models);
  state.modelRoutingBaseVersionId = active.active_version_id || '';
  state.lastData.modelConfig = config;
  const providerIds = modelProviderIds(config);
  const activeProvider = config.providers[config.active_provider] || config.providers[providerIds[0]];
  const keyStatus = modelSecretStatusLabel(config.active_provider, activeProvider, config.runtime);
  elements.viewContent.innerHTML = [
    section(
      'Настройка моделей',
      `<form class="scenario-editor panel" data-form="model-routing-editor">
        <div class="slot-schema-derived">
          <div class="metric-label">Подключения LiteLLM</div>
          <div class="meta">Каждое подключение описывает alias, модель и переменную окружения с ключом. Секрет можно ввести при сохранении; после сохранения значение очищается и показывается только статус. Новое подключение сначала сохраните, затем выберите его для маршрутов или сделайте активным.</div>
        </div>
        <div class="grid two">
          <label>Активное подключение
            <select name="active_provider">${modelProviderOptions(config, config.active_provider)}</select>
            <span class="field-help">Какое подключение использовать как основной источник ответов.</span>
          </label>
          <label>Alias по умолчанию
            <select name="default_model_alias">${modelAliasOptions(config, config.default_model_alias)}</select>
            <span class="field-help">Стабильное имя модели для workflow и prompt evaluation.</span>
          </label>
          <label>Шлюз
            <input name="gateway_type" value="${escapeHtml(config.gateway?.type || 'litellm')}" autocomplete="off">
            <span class="field-help">Для текущей архитектуры должен оставаться LiteLLM.</span>
          </label>
        <label>Базовый URL шлюза
            <input name="gateway_base_url" value="${escapeHtml(config.gateway?.base_url || 'http://127.0.0.1:4000/v1')}" autocomplete="off">
            <span class="field-help">OpenAI-compatible endpoint, через который оркестратор вызывает модель.</span>
          </label>
        </div>
        <div class="grid">
          ${metric('Текущее подключение', escapeHtml(activeProvider?.display_name || config.active_provider))}
          ${metric('Модель', escapeHtml(activeProvider?.model || 'н/д'))}
          ${metric('Секрет', escapeHtml(`${activeProvider?.api_key_env || 'не требуется'}: ${keyStatus}`))}
        </div>
        <div class="scenario-editor-actions">
          <button type="button" data-action="model-provider-add">Добавить подключение</button>
        </div>
        <div id="modelProviderCards">
          ${providerIds.map((providerId) => renderModelProviderCard(providerId, config.providers[providerId], config.active_provider, config.runtime)).join('')}
        </div>
        <fieldset class="launch-editor">
          <legend>Маршрутизация задач</legend>
          <div class="grid two">
            ${modelRouteField(config, 'default', 'Обычные ответы')}
            ${modelRouteField(config, 'classification', 'Классификация')}
            ${modelRouteField(config, 'summarization', 'Суммаризация')}
            ${modelRouteField(config, 'tool_selection', 'Выбор ReAct-вызовов')}
            ${modelRouteField(config, 'slot_resolution', 'Разрешение атрибутов')}
          </div>
        </fieldset>
        <fieldset class="launch-editor">
          <legend>Fallback</legend>
          <div class="grid two">
            <label>Если alias недоступен
              <select name="fallback_from">${modelAliasOptions(config, config.fallbacks?.[0]?.from || '')}</select>
            </label>
            <label>Переключить на
              <select name="fallback_to">${modelAliasOptions(config, config.fallbacks?.[0]?.to || '')}</select>
            </label>
          </div>
          <div class="meta">Оставьте поля пустыми, если fallback не нужен. Для OpenAI можно указать fallback на локальный vLLM CPU.</div>
        </fieldset>
        <div class="scenario-editor-actions">
          <button class="primary" type="submit">Сохранить настройки моделей</button>
        </div>
      </form>`,
    ),
  ].join('');
}

function normalizeModelConfig(config = {}) {
  const rawProviders = config.providers || {};
  const providers = {};
  providers.vllm_cpu = normalizeModelProvider('vllm_cpu', rawProviders.vllm_cpu || {}, config);
  providers.openai = normalizeModelProvider('openai', rawProviders.openai || {}, config);
  for (const [providerId, provider] of Object.entries(rawProviders)) {
    if (providerId === 'vllm_cpu' || providerId === 'openai') continue;
    providers[providerId] = normalizeModelProvider(providerId, provider, config);
  }
  const providerIds = modelProviderIds({ providers });
  const activeProvider = providerIds.includes(config.active_provider) ? config.active_provider : providerIds[0];
  const defaultAlias = config.default_model_alias || providers[activeProvider]?.model_alias || providers.vllm_cpu.model_alias;
  return {
    schema_version: '1.0',
    active_provider: activeProvider,
    providers,
    gateway: {
      type: config.gateway?.type || 'litellm',
      base_url: config.gateway?.base_url || 'http://127.0.0.1:4000/v1',
    },
    default_model_alias: defaultAlias,
    upstream_model: config.upstream_model || providers[activeProvider]?.model || '',
    routing: {
      default: config.routing?.default || defaultAlias,
      classification: config.routing?.classification || defaultAlias,
      summarization: config.routing?.summarization || defaultAlias,
      tool_selection: config.routing?.tool_selection || defaultAlias,
      slot_resolution: config.routing?.slot_resolution || defaultAlias,
    },
    fallbacks: config.fallbacks || [],
    settings: config.settings || {
      temperature: 0,
      context_length: providers[activeProvider]?.context_length || 2048,
      rate_limits: { requests_per_minute: 60 },
    },
    runtime: config.runtime || {},
  };
}

function normalizeModelProvider(providerId, provider = {}, config = {}) {
  const defaults = {
    vllm_cpu: {
      enabled: true,
      provider_type: 'vllm_cpu',
      display_name: 'vLLM CPU локально',
      base_url: config.gateway?.base_url || 'http://127.0.0.1:4000/v1',
      model_alias: config.default_model_alias || 'local-opt-125m',
      model: config.runtime?.vllm_model || 'facebook/opt-125m',
      api_key_env: 'LITELLM_MASTER_KEY',
      api_key_required: false,
      context_length: config.settings?.context_length || 2048,
      temperature: config.settings?.temperature ?? 0,
      max_tokens: 512,
      timeout_seconds: 60,
      requests_per_minute: 30,
      tokens_per_minute: 30000,
    },
    openai: {
      enabled: true,
      provider_type: 'openai',
      display_name: 'OpenAI API',
      base_url: 'https://api.openai.com/v1',
      model_alias: 'openai-primary',
      model: 'openai/gpt-4.1-mini',
      api_key_env: 'OPENAI_API_KEY',
      api_key_required: true,
      context_length: 128000,
      temperature: 0,
      max_tokens: 4096,
      timeout_seconds: 60,
      requests_per_minute: 60,
      tokens_per_minute: 120000,
    },
    litellm: {
      enabled: true,
      provider_type: 'litellm',
      display_name: 'LiteLLM подключение',
      base_url: config.gateway?.base_url || 'http://127.0.0.1:4000/v1',
      model_alias: provider.model || 'openai/gpt-4.1-mini',
      model: 'openai/gpt-4.1-mini',
      api_key_env: 'OPENAI_API_KEY',
      api_key_required: true,
      context_length: 128000,
      temperature: 0,
      max_tokens: 4096,
      timeout_seconds: 60,
      requests_per_minute: 60,
      tokens_per_minute: 120000,
    },
  };
  const base = defaults[providerId] || defaults[provider.provider_type] || defaults.litellm;
  return {
    enabled: provider.enabled ?? base.enabled,
    provider_type: provider.provider_type || base.provider_type,
    display_name: provider.display_name || base.display_name,
    base_url: provider.base_url || base.base_url,
    model_alias: provider.model_alias || base.model_alias,
    model: provider.model || base.model,
    api_key_env: provider.api_key_env || base.api_key_env,
    api_key_required: provider.api_key_required ?? base.api_key_required,
    context_length: provider.context_length || base.context_length,
    temperature: provider.temperature ?? base.temperature,
    max_tokens: provider.max_tokens || base.max_tokens,
    timeout_seconds: provider.timeout_seconds || base.timeout_seconds,
    rate_limits: {
      requests_per_minute: provider.rate_limits?.requests_per_minute || base.requests_per_minute,
      tokens_per_minute: provider.rate_limits?.tokens_per_minute || base.tokens_per_minute,
    },
    runtime: provider.runtime || {},
  };
}

function modelProviderIds(config) {
  const ids = Object.keys(config.providers || {});
  return ids.sort((left, right) => {
    const order = { vllm_cpu: 0, openai: 1 };
    return (order[left] ?? 10) - (order[right] ?? 10) || left.localeCompare(right);
  });
}

function modelProviderOptions(config, selected) {
  return modelProviderIds(config)
    .map((providerId) => {
      const provider = config.providers[providerId];
      const label = `${provider.display_name || providerId} / ${provider.model_alias || 'без alias'}`;
      return `<option value="${escapeHtml(providerId)}" ${providerId === selected ? 'selected' : ''}>${escapeHtml(label)}</option>`;
    })
    .join('');
}

function modelAliasOptions(config, selected) {
  const options = ['<option value="">не выбран</option>'];
  for (const providerId of modelProviderIds(config)) {
    const provider = config.providers[providerId];
    if (!provider.model_alias) continue;
    options.push(
      `<option value="${escapeHtml(provider.model_alias)}" ${provider.model_alias === selected ? 'selected' : ''}>${escapeHtml(provider.display_name)} / ${escapeHtml(provider.model_alias)}</option>`,
    );
  }
  return options.join('');
}

function modelRouteField(config, routeKey, label) {
  const selected = config.routing?.[routeKey] || config.default_model_alias;
  return `
    <label>${escapeHtml(label)}
      <select name="route_${escapeHtml(routeKey)}">${modelAliasOptions(config, selected)}</select>
    </label>
  `;
}

function modelSecretStatusLabel(providerId, provider = {}, runtime = {}) {
  if (!provider.api_key_required) {
    return 'параметр не требуется';
  }
  return runtime?.provider_key_configured?.[providerId] === true ? 'параметр скрыт' : 'параметр не заполнен';
}

function renderModelProviderCard(providerId, provider = {}, activeProviderId = '', runtime = {}, saved = true) {
  const coreProvider = providerId === 'vllm_cpu' || providerId === 'openai';
  const title = provider.display_name || visibleLabels[provider.provider_type] || 'LiteLLM подключение';
  const isActive = providerId === activeProviderId;
  const tokenStatus = modelSecretStatusLabel(providerId, provider, runtime);
  const tokenHelp = 'Имя переменной окружения с ключом для upstream-модели. Значение секрета можно ввести ниже; после сохранения оно не отображается.';
  return `
    <fieldset class="launch-editor" data-model-provider="${escapeHtml(providerId)}">
      <legend>${escapeHtml(title)} ${isActive ? '(активен)' : ''}</legend>
      <input type="hidden" name="model_provider_id" value="${escapeHtml(providerId)}">
      <div class="slot-schema-derived">
        <div class="metric-label">${escapeHtml(provider.model_alias || providerId)}</div>
        <div class="meta">Профиль сохраняется независимо от активного подключения. Статус секрета: ${escapeHtml(tokenStatus)}.</div>
      </div>
      <div class="grid two">
        <label>Включен<select name="${providerId}_enabled">${booleanOptions(provider.enabled)}</select></label>
        <label>Название<input name="${providerId}_display_name" value="${escapeHtml(provider.display_name || title)}" autocomplete="off"></label>
        <label>Тип подключения
          <select name="${providerId}_provider_type">${optionList(['litellm', 'openai', 'vllm_cpu'], provider.provider_type || 'litellm')}</select>
          <span class="field-help">Для новых подключений используйте LiteLLM. Типы OpenAI и vLLM CPU оставлены для базовых профилей.</span>
        </label>
        <label>Базовый URL<input name="${providerId}_base_url" value="${escapeHtml(provider.base_url || '')}" autocomplete="off"></label>
        <label>Alias в LiteLLM
          <input name="${providerId}_model_alias" value="${escapeHtml(provider.model_alias || '')}" autocomplete="off">
          <span class="field-help">Для нового подключения без отдельной записи в litellm.yaml укажите provider-prefixed model, например openai/gpt-4.1-mini.</span>
        </label>
        <label>Модель<input name="${providerId}_model" value="${escapeHtml(provider.model || '')}" autocomplete="off"></label>
        <label>Env для ключа
          <input name="${providerId}_api_key_env" value="${escapeHtml(provider.api_key_env || '')}" autocomplete="off">
          <span class="field-help">${escapeHtml(tokenHelp)}</span>
        </label>
        <label>Значение секрета
          <input name="${providerId}_secret_value" type="password" value="" placeholder="${escapeHtml(tokenStatus)}" autocomplete="new-password">
          <span class="field-help">Оставьте пустым, если секрет менять не нужно. В конфигурации сохраняется только имя переменной окружения.</span>
        </label>
        <label>Ключ обязателен<select name="${providerId}_api_key_required">${booleanOptions(provider.api_key_required)}</select></label>
        <label>Context length<input name="${providerId}_context_length" type="number" min="1" value="${escapeHtml(provider.context_length || 1)}"></label>
        <label>Temperature<input name="${providerId}_temperature" type="number" min="0" max="2" step="0.01" value="${escapeHtml(provider.temperature ?? 0)}"></label>
        <label>Max tokens<input name="${providerId}_max_tokens" type="number" min="1" value="${escapeHtml(provider.max_tokens || 1)}"></label>
        <label>Timeout, секунд<input name="${providerId}_timeout_seconds" type="number" min="1" value="${escapeHtml(provider.timeout_seconds || 60)}"></label>
        <label>Запросов в минуту<input name="${providerId}_requests_per_minute" type="number" min="1" value="${escapeHtml(provider.rate_limits?.requests_per_minute || 1)}"></label>
        <label>Токенов в минуту<input name="${providerId}_tokens_per_minute" type="number" min="1" value="${escapeHtml(provider.rate_limits?.tokens_per_minute || 1)}"></label>
      </div>
      <div class="scenario-editor-actions">
        <button class="${isActive ? '' : 'primary'}" type="button" data-action="model-provider-switch" data-provider="${escapeHtml(providerId)}" ${isActive || !saved ? 'disabled' : ''}>
          ${isActive ? 'Активен' : saved ? 'Сделать активным' : 'Сначала сохраните'}
        </button>
        <button class="danger" type="button" data-action="model-provider-remove" data-provider="${escapeHtml(providerId)}" ${coreProvider ? 'disabled' : ''}>
          ${coreProvider ? 'Базовый профиль' : 'Удалить подключение'}
        </button>
      </div>
    </fieldset>
  `;
}

async function renderQuality() {
  const [feedback, cases, runs, dashboard] = await Promise.all([
    api('/admin/feedback?limit=50'),
    api('/admin/evaluations/cases'),
    api('/admin/evaluations/runs?limit=20'),
    api('/admin/dashboard'),
  ]);
  const feedbackRows = (feedback.feedback || []).map((item) => [
    badge(item.rating),
    escapeHtml(item.ticket_id),
    escapeHtml(item.operator_id),
    escapeHtml(item.created_at),
  ]);
  const caseRows = (cases.cases || []).map((item) => [
    badge(item.expected?.rating),
    escapeHtml(item.extensions?.ticket_id || 'н/д'),
  ]);
  const runRows = (runs.runs || []).map((run) => [
    badge(run.status),
    escapeHtml(run.case_count),
    escapeHtml(run.started_at),
  ]);
  elements.viewContent.innerHTML = [
    section(
      'Сводка качества',
      `<div class="grid">
        ${metric('Обратная связь', String(dashboard.feedback?.total ?? 0))}
        ${metric('Дубликаты', String(dashboard.feedback?.duplicates ?? 0))}
        ${metric('Оценочные кейсы', String(cases.case_count ?? 0))}
        ${metric('Запуски оценки', String(runs.run_count ?? 0))}
      </div>`,
      '<button type="button" data-action="promote-feedback">Перенести обратную связь в оценку</button> <button class="primary" type="button" data-action="run-evaluation">Запустить оценку</button>',
    ),
    section('Обратная связь', table(['Оценка', 'Заявка', 'Оператор', 'Создано'], feedbackRows)),
    section('Оценочные кейсы', table(['Ожидание', 'Заявка'], caseRows)),
    section('Запуски оценки', table(['Статус', 'Кейсы', 'Старт'], runRows)),
  ].join('');
}

async function renderAudit(filters = {}) {
  const query = new URLSearchParams({ limit: '100', ...filters });
  const [summary, audit] = await Promise.all([
    api('/admin/security/audit/summary'),
    api(`/admin/security/audit?${query.toString()}`),
  ]);
  const rows = (audit.events || []).map((event) => [
    escapeHtml(event.created_at),
    escapeHtml(event.actor_id),
    escapeHtml(event.action),
    escapeHtml(event.resource_type),
    badge(event.outcome),
    escapeHtml(event.permission || 'н/д'),
    escapeHtml(event.status_code || 'н/д'),
  ]);
  elements.viewContent.innerHTML = [
    section(
      'Сводка аудита',
      `<div class="grid">
        ${metric('Всего', String(summary.total ?? 0))}
        ${metric('Успешно', String(summary.by_outcome?.success ?? 0))}
        ${metric('Отказано', String(summary.by_outcome?.denied ?? 0))}
        ${metric('Ошибки', String(summary.by_outcome?.error ?? 0))}
      </div>`,
    ),
    section(
      'Фильтр',
      `<form class="toolbar" data-form="audit-filter">
        <label>Результат<select name="outcome"><option value="">любой</option><option value="success">успешно</option><option value="denied">отказано</option><option value="error">ошибка</option></select></label>
        <label>Инициатор<input name="actor_id" placeholder="admin-1"></label>
        <label>Действие<input name="action" placeholder="admin.knowledge.rebuild"></label>
        <label>Лимит<input name="limit" type="number" min="1" max="1000" value="100"></label>
        <button type="submit">Применить</button>
      </form>`,
    ),
    section('События', table(['Время', 'Инициатор', 'Действие', 'Тип ресурса', 'Результат', 'Право', 'HTTP'], rows)),
  ].join('');
}

async function renderSecurity() {
  const [session, catalog, secrets] = await Promise.all([
    api('/admin/security/session'),
    api('/admin/security/catalog'),
    api('/admin/security/secret-references'),
  ]);
  const roleRows = (catalog.roles || []).map((role) => [
    badge(role.role_id),
    escapeHtml(role.description),
    escapeHtml(role.permissions.join(', ')),
  ]);
  const userRows = (catalog.users || []).map((user) => [
    escapeHtml(user.display_name),
    badge(user.enabled ? 'enabled' : 'disabled'),
    escapeHtml(user.roles.join(', ')),
  ]);
  const secretRows = (secrets.secret_references || []).map((secret) => [
    escapeHtml(secret.secret_type),
    escapeHtml(secret.storage),
    escapeHtml(secret.reference),
    badge(secret.configured === true ? 'configured' : secret.configured === false ? 'missing' : 'external'),
  ]);
  elements.viewContent.innerHTML = [
    section(
      'Сессия',
      `<div class="grid three">
        ${metric('Инициатор', escapeHtml(session.actor_id))}
        ${metric('Режим аутентификации', escapeHtml(session.auth_mode))}
        ${metric('Права', String(session.permissions.length))}
      </div>`,
    ),
    section('Пользователи', table(['Имя', 'Статус', 'Роли'], userRows)),
    section('Роли', table(['Роль', 'Описание', 'Права'], roleRows)),
    section('Ссылки на секреты', table(['Тип', 'Хранилище', 'Ссылка', 'Настроено'], secretRows)),
  ].join('');
}

async function rebuildKnowledge() {
  await api('/admin/knowledge/rebuild', {
    method: 'POST',
    body: JSON.stringify({ operator_id: state.actorId }),
  });
  setNotice('Перестроение базы знаний завершено.', 'success');
  await renderKnowledge();
}

async function testRetrieval(form) {
  const data = new FormData(form);
  const payload = {
    query: data.get('query'),
    top_k: Number(data.get('top_k') || 3),
  };
  const result = await api('/admin/knowledge/retrieval/test', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  document.getElementById('retrievalResult').innerHTML = jsonBlock(result);
}

async function promoteFeedback() {
  const result = await api('/admin/evaluations/promote-feedback', {
    method: 'POST',
    body: JSON.stringify({ operator_id: state.actorId }),
  });
  setNotice(`Перенос завершен: новых оценочных кейсов ${result.promoted_count}.`, 'success');
  await renderQuality();
}

async function runEvaluation() {
  const result = await api('/admin/evaluations/run', {
    method: 'POST',
    body: JSON.stringify({ operator_id: state.actorId, limit: 20 }),
  });
  setNotice(`Оценка завершена: кейсов ${result.summary?.total ?? 0}.`, 'success');
  await renderQuality();
}

function endpointAuthFromFormData(data) {
  const authType = String(data.get('auth_type') || 'none').trim();
  const authHeaderName = String(data.get('auth_header_name') || '').trim();
  const authTokenEnv = String(data.get('auth_token_env') || '').trim();
  const auth = { type: authType };
  if (authHeaderName) auth.header_name = authHeaderName;
  if (authTokenEnv) auth.token_env = authTokenEnv;
  return auth;
}

function endpointContractSourceFromFormData(data, adapterType) {
  if (adapterType !== 'n8n_webhook') {
    return null;
  }
  const sourceUrl = String(data.get('contract_source_url') || '').trim();
  const enabled = parseBoolean(data.get('contract_source_enabled'));
  if (!sourceUrl && !enabled) {
    return null;
  }
  if (!sourceUrl) {
    throw new Error('Укажите URL OpenAPI-контракта n8n.');
  }
  return {
    type: 'openapi_3_1',
    enabled,
    method: String(data.get('contract_source_method') || 'GET').trim() || 'GET',
    url: sourceUrl,
  };
}

function endpointBaseFromForm(form) {
  const data = new FormData(form);
  const adapterType = String(data.get('adapter_type') || '').trim();
  const endpoint = {
    endpoint_id: String(data.get('endpoint_id') || '').trim(),
    adapter_type: adapterType,
    display_name: String(data.get('display_name') || '').trim(),
    enabled: parseBoolean(data.get('enabled')),
    operations: {},
  };
  const disabledReason = String(data.get('disabled_reason') || '').trim();
  const baseUrl = String(data.get('base_url') || '').trim();
  const baseUrlEnv = String(data.get('base_url_env') || '').trim();
  if (disabledReason) endpoint.disabled_reason = disabledReason;
  if (baseUrl) endpoint.base_url = baseUrl;
  if (baseUrlEnv) endpoint.base_url_env = baseUrlEnv;
  endpoint.auth = endpointAuthFromFormData(data);
  const contractSource = endpointContractSourceFromFormData(data, adapterType);
  if (contractSource) endpoint.contract_source = contractSource;
  return endpoint;
}

async function saveIntegrationEndpointForm(form) {
  const data = new FormData(form);
  const adapterType = String(data.get('adapter_type') || '').trim();
  const endpoint = {
    endpoint_id: String(data.get('endpoint_id') || '').trim(),
    adapter_type: adapterType,
    display_name: String(data.get('display_name') || '').trim(),
    enabled: parseBoolean(data.get('enabled')),
    operations: parseEndpointOperationCards(form, adapterType),
  };
  const disabledReason = String(data.get('disabled_reason') || '').trim();
  const baseUrl = String(data.get('base_url') || '').trim();
  const baseUrlEnv = String(data.get('base_url_env') || '').trim();
  if (disabledReason) endpoint.disabled_reason = disabledReason;
  if (baseUrl) endpoint.base_url = baseUrl;
  if (baseUrlEnv) endpoint.base_url_env = baseUrlEnv;
  endpoint.auth = endpointAuthFromFormData(data);
  const contractSource = endpointContractSourceFromFormData(data, adapterType);
  if (contractSource) endpoint.contract_source = contractSource;
  await applyIntegrationEndpointMutation(state.integrationEndpointOperation, endpoint);
}

async function deleteIntegrationEndpointForm() {
  if (!state.integrationEndpointId) {
    throw new Error('Подключение для удаления не выбрано.');
  }
  await applyIntegrationEndpointMutation('delete', { endpoint_id: state.integrationEndpointId });
}

function rowText(row, selector) {
  return row.querySelector(selector)?.value?.trim() || '';
}

function operationFieldRowHasManualInput(row) {
  return [
    '[data-operation-field-name]',
    '[data-operation-field-title]',
    '[data-operation-field-description]',
    '[data-operation-field-min-length]',
    '[data-operation-field-minimum]',
    '[data-operation-field-maximum]',
  ].some((selector) => rowText(row, selector));
}

function operationFieldFromRow(row, label) {
  const name = rowText(row, '[data-operation-field-name]');
  if (!name && !operationFieldRowHasManualInput(row)) {
    return null;
  }
  if (!name) {
    throw new Error(`${label}: имя поля не должно быть пустым.`);
  }
  if (!/^[A-Za-z_][A-Za-z0-9_.-]*$/.test(name)) {
    throw new Error(`${label}: имя поля "${name}" должно начинаться с латинской буквы или подчеркивания.`);
  }
  return {
    name,
    title: rowText(row, '[data-operation-field-title]'),
    type: rowText(row, '[data-operation-field-type]') || 'string',
    item_type: rowText(row, '[data-operation-field-item-type]') || 'object',
    required: parseBoolean(rowText(row, '[data-operation-field-required]')),
    description: rowText(row, '[data-operation-field-description]'),
    minLength: rowText(row, '[data-operation-field-min-length]'),
    minimum: rowText(row, '[data-operation-field-minimum]'),
    maximum: rowText(row, '[data-operation-field-maximum]'),
  };
}

function operationSchemaPropertyFromField(field) {
  const property = {};
  if (field.type === 'array') {
    property.type = 'array';
    property.items = { type: field.item_type || 'object' };
    if (property.items.type === 'object') {
      property.items.additionalProperties = true;
    }
  } else if (field.type === 'object') {
    property.type = 'object';
    property.additionalProperties = true;
  } else {
    property.type = operationContractTypes.includes(field.type) ? field.type : 'string';
  }
  if (field.title) property.title = field.title;
  if (field.description) property.description = field.description;
  if (property.type === 'string' && field.minLength !== '') {
    property.minLength = parseInt(field.minLength, 10);
  }
  if ((property.type === 'integer' || property.type === 'number') && field.minimum !== '') {
    property.minimum = Number(field.minimum);
  }
  if ((property.type === 'integer' || property.type === 'number') && field.maximum !== '') {
    property.maximum = Number(field.maximum);
  }
  return property;
}

function buildOperationSchemaFromEditor(card, kind) {
  const editor = card.querySelector(`[data-operation-schema-editor="${kind}"]`);
  if (!editor) {
    return parseJsonField(card.querySelector(`[data-operation-json-kind="${kind}"]`)?.value || '{}', `${kind} JSON Schema`);
  }
  const schema = {
    type: 'object',
    properties: {},
    additionalProperties: true,
  };
  const required = [];
  const seen = new Set();
  const label = kind === 'request' ? 'Вход операции' : 'Ответ операции';
  editor.querySelectorAll('[data-operation-field-row]').forEach((row) => {
    const field = operationFieldFromRow(row, label);
    if (!field) return;
    if (seen.has(field.name)) {
      throw new Error(`${label}: дублируется поле ${field.name}.`);
    }
    seen.add(field.name);
    schema.properties[field.name] = operationSchemaPropertyFromField(field);
    if (field.required) {
      required.push(field.name);
    }
  });
  if (required.length) {
    schema.required = required;
  }
  return schema;
}

function parseMockControlValue(row, { validate = true } = {}) {
  const control = row.querySelector('[data-mock-field-value]');
  if (!control) return undefined;
  const name = control.dataset.mockFieldName;
  const type = control.dataset.mockFieldType || 'string';
  const required = control.dataset.mockFieldRequired === 'true';
  const raw = String(control.value || '').trim();
  if (!raw) {
    if (required && validate) {
      throw new Error(`Тестовый ответ mock: обязательное поле ${name} не заполнено.`);
    }
    return undefined;
  }
  if (type === 'string') {
    return raw;
  }
  if (type === 'integer') {
    const value = Number(raw);
    if (!Number.isInteger(value)) {
      if (!validate) return undefined;
      throw new Error(`Тестовый ответ mock: поле ${name} должно быть целым числом.`);
    }
    return value;
  }
  if (type === 'number') {
    const value = Number(raw);
    if (!Number.isFinite(value)) {
      if (!validate) return undefined;
      throw new Error(`Тестовый ответ mock: поле ${name} должно быть числом.`);
    }
    return value;
  }
  if (type === 'boolean') {
    if (!['true', 'false'].includes(raw)) {
      if (!validate) return undefined;
      throw new Error(`Тестовый ответ mock: поле ${name} должно быть true или false.`);
    }
    return raw === 'true';
  }
  try {
    const value = JSON.parse(raw);
    if (type === 'array' && !Array.isArray(value)) {
      throw new Error('ожидался массив');
    }
    if (type === 'object' && (Array.isArray(value) || value === null || typeof value !== 'object')) {
      throw new Error('ожидался объект');
    }
    return value;
  } catch (error) {
    if (!validate) return undefined;
    throw new Error(`Тестовый ответ mock: поле ${name} содержит невалидный JSON (${error.message}).`);
  }
}

function buildMockOutputFromEditor(card, { validate = true } = {}) {
  const editor = card.querySelector('[data-operation-mock-editor]');
  if (!editor) {
    const raw = card.querySelector('[data-operation-json-kind="mock"]')?.value?.trim() || '';
    return raw ? parseJsonField(raw, 'Тестовый ответ операции') : undefined;
  }
  const output = {};
  editor.querySelectorAll('[data-operation-mock-row]').forEach((row) => {
    const control = row.querySelector('[data-mock-field-value]');
    const name = control?.dataset.mockFieldName;
    const value = parseMockControlValue(row, { validate });
    if (name && value !== undefined) {
      output[name] = value;
    }
  });
  return output;
}

function validateMockOutputAgainstResponseSchema(mockOutput = {}, responseSchema = {}) {
  const fields = operationSchemaFields(responseSchema);
  for (const field of fields) {
    const value = mockOutput[field.name];
    if (field.required && value === undefined) {
      throw new Error(`Тестовый ответ mock: обязательное поле ${field.name} не заполнено.`);
    }
  }
}

function parseEndpointOperationCards(form, adapterType) {
  const cards = Array.from(form.querySelectorAll('[data-endpoint-operation-card]'));
  const operations = {};
  for (const card of cards) {
    const value = (name) => card.querySelector(`[name="${name}"]`)?.value?.trim() || '';
    const operationId = value('operation_id');
    if (!operationId) {
      throw new Error('У каждой операции должно быть техническое имя.');
    }
    if (operations[operationId]) {
      throw new Error(`Дублируется operation_id: ${operationId}`);
    }
    const operation = {
      display_name: value('operation_display_name'),
      description: value('operation_description'),
      method: value('operation_method'),
      path: value('operation_path'),
      request_schema: buildOperationSchemaFromEditor(card, 'request'),
      response_schema: buildOperationSchemaFromEditor(card, 'response'),
      async_event_contracts: parseJsonField(
        card.querySelector('[name="operation_async_event_contracts"]')?.value?.trim() || '{}',
        `Операция ${operationId}: async_event_contracts`,
      ),
      contract_version: value('operation_contract_version') || '1.0',
      contract_status: value('operation_contract_status') || 'draft',
      timeout_seconds: parseInt(value('operation_timeout_seconds'), 10),
    };
    if (!operation.display_name || !operation.description || !operation.method || !operation.path) {
      throw new Error(`Операция ${operationId} должна иметь название, описание, метод и path.`);
    }
    const mockOutput = buildMockOutputFromEditor(card, { validate: true });
    if (adapterType === 'mock') {
      validateMockOutputAgainstResponseSchema(mockOutput || {}, operation.response_schema);
    }
    if (adapterType === 'mock' || mockOutput !== undefined) {
      operation.mock_output = mockOutput || {};
    }
    operations[operationId] = operation;
  }
  if (!Object.keys(operations).length) {
    throw new Error('Подключение должно содержать хотя бы одну операцию.');
  }
  return operations;
}

async function saveToolCatalogForm(form) {
  const data = new FormData(form);
  const toolName = String(data.get('tool_name') || '').trim();
  const existing = (state.lastData.toolCatalog || []).find((item) => item.tool_name === toolName);
  const tool = {
    tool_name: toolName,
    action_type: String(data.get('action_type') || '').trim(),
    description: String(data.get('description') || '').trim(),
    endpoint_bindings: existing?.endpoint_bindings || [],
    parameters_schema: parseJsonField(data.get('parameters_schema'), 'Схема параметров'),
    result_schema: parseJsonField(data.get('result_schema'), 'Схема результата'),
    contract_version: String(data.get('contract_version') || '1.0').trim(),
    contract_status: String(data.get('contract_status') || 'draft').trim(),
    policy: {
      default_timeout_seconds: parseInt(data.get('default_timeout_seconds'), 10),
      retry: {
        max_attempts: parseInt(data.get('retry_max_attempts'), 10),
        backoff_seconds: Number(data.get('retry_backoff_seconds')),
      },
      approval_required_hint: parseBoolean(data.get('approval_required_hint')),
      auto_execution_eligible: parseBoolean(data.get('auto_execution_eligible')),
      max_risk_level: String(data.get('max_risk_level') || '').trim(),
    },
  };
  await applyToolCatalogMutation(state.toolCatalogOperation, tool);
}

async function deleteToolCatalogForm() {
  if (!state.toolCatalogName) {
    throw new Error('ReAct-вызов ИИ для удаления не выбран.');
  }
  await applyToolCatalogMutation('delete', { tool_name: state.toolCatalogName });
}

async function saveOperationBindingForm(form, submitter) {
  const data = new FormData(form);
  const operation = submitter?.value === 'unbind' ? 'unbind' : 'bind';
  const endpointId = String(data.get('binding_endpoint_id') || '').trim();
  const operationId = String(data.get('binding_operation_id') || '').trim();
  const endpointOperation = findEndpointOperation(endpointId, operationId);
  const contract = operation === 'unbind'
    ? {}
    : parseOperationBindingContract(form, endpointOperation);
  const binding = operation === 'unbind'
    ? {}
    : {
      endpoint_id: endpointId,
      operation_id: operationId,
      parameter_mapping: contract.parameter_mapping,
      result_mapping: contract.result_mapping,
      parameters_schema: contract.parameters_schema,
      result_schema: contract.result_schema,
    };
  await applyOperationBindingMutation({
    operation,
    toolName: state.operationBindingToolName,
    binding,
  });
}

async function saveOperationBindingCreateForm(form) {
  const data = new FormData(form);
  const endpointId = String(data.get('binding_endpoint_id') || '').trim();
  const operationId = String(data.get('binding_operation_id') || '').trim();
  const endpointOperation = findEndpointOperation(endpointId, operationId);
  const contract = parseOperationBindingContract(form, endpointOperation);
  const toolName = String(data.get('tool_name') || '').trim();
  const actionType = String(data.get('action_type') || 'read_only').trim();
  if (!toolName) {
    throw new Error('Укажите техническое имя ReAct-вызова ИИ.');
  }
  const tool = createReactCallTemplateFromOperation({
    toolName,
    actionType,
    description: String(data.get('description') || '').trim() || defaultReactCallDescription(operationId, endpointOperation),
    operation: endpointOperation,
  });
  tool.parameters_schema = contract.parameters_schema;
  tool.result_schema = contract.result_schema;
  tool.endpoint_bindings = [{
    endpoint_id: endpointId,
    operation_id: operationId,
    parameter_mapping: contract.parameter_mapping,
    result_mapping: contract.result_mapping,
  }];
  await applyOperationBindingCreateMutation(tool);
}

function findEndpointOperation(endpointId, operationId) {
  const endpoint = (state.lastData.integrationEndpoints || [])
    .find((item) => item.endpoint_id === endpointId);
  return endpoint?.operations?.[operationId] || {};
}

function parseOperationBindingContract(form, operation) {
  const parameter_mapping = {};
  const result_mapping = {};
  const parameterProperties = {};
  const parameterRequired = [];
  const resultProperties = {};
  const resultRequired = [];

  const rows = Array.from(form.querySelectorAll('[data-operation-param-row]'));
  for (const row of rows) {
    const parameterName = row.querySelector('[data-operation-param-name]')?.value?.trim() || '';
    const endpointRequired = row.dataset.required === 'true';
    const source = row.querySelector('[data-operation-param-source]')?.value?.trim() || '';
    const value = source === 'react'
      ? row.querySelector('[data-operation-param-react]')?.value?.trim() || ''
      : row.querySelector('[data-operation-param-value]')?.value?.trim() || '';
    if (!parameterName) continue;
    if (!source) {
      if (endpointRequired) {
        throw new Error(`Обязательный параметр endpoint ${parameterName} должен иметь источник значения.`);
      }
      continue;
    }
    if (!['react', 'constant', 'secret'].includes(source)) {
      throw new Error(`Параметр endpoint ${parameterName} имеет неизвестный источник: ${source}.`);
    }
    if (!value) {
      throw new Error(
        source === 'react'
          ? `Параметр endpoint ${parameterName}: укажите имя параметра ReAct.`
          : `Параметр endpoint ${parameterName}: укажите значение для ${visibleLabels[source] || source}.`,
      );
    }
    parameter_mapping[parameterName] = `${source}:${value}`;
    if (source === 'react') {
      parameterProperties[value] = parameterProperties[value]
        || schemaPropertyForName(operation.request_schema || defaultOperationRequestSchema(), parameterName, value);
      if (parseBoolean(row.querySelector('[data-operation-param-react-required]')?.value)) {
        parameterRequired.push(value);
      }
    }
  }

  const resultRows = Array.from(form.querySelectorAll('[data-operation-result-row]'));
  for (const row of resultRows) {
    const endpointFieldName = row.querySelector('[data-operation-response-field-name]')?.value?.trim() || '';
    const include = parseBoolean(row.querySelector('[data-operation-result-include]')?.value);
    if (!endpointFieldName || !include) continue;
    const reactFieldName = row.querySelector('[data-operation-result-name]')?.value?.trim() || '';
    if (!reactFieldName) {
      throw new Error(`Поле ответа endpoint ${endpointFieldName}: укажите имя поля результата ReAct.`);
    }
    if (result_mapping[reactFieldName]) {
      throw new Error(`Поле результата ReAct ${reactFieldName} указано несколько раз.`);
    }
    result_mapping[reactFieldName] = endpointFieldName;
    resultProperties[reactFieldName] = schemaPropertyForName(
      operation.response_schema || defaultOperationResponseSchema(),
      endpointFieldName,
      reactFieldName,
    );
    if (parseBoolean(row.querySelector('[data-operation-result-required]')?.value)) {
      resultRequired.push(reactFieldName);
    }
  }

  return {
    parameter_mapping,
    result_mapping,
    parameters_schema: operationObjectSchema(parameterProperties, parameterRequired),
    result_schema: operationObjectSchema(resultProperties, resultRequired),
  };
}

async function deleteOperationBindingForm() {
  if (!state.operationBindingToolName) {
    throw new Error('ReAct-вызов ИИ для отвязки не выбран.');
  }
  await applyOperationBindingMutation({
    operation: 'unbind',
    toolName: state.operationBindingToolName,
    binding: {},
  });
}

function parseExistingScenarioTags(value) {
  try {
    const parsed = JSON.parse(String(value || '[]'));
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed
      .map((tag) => String(tag || '').trim())
      .filter(Boolean);
  } catch {
    return [];
  }
}

async function saveScenarioForm(form) {
  const data = new FormData(form);
  const scenario = compactScenarioPayload({
    scenario_id: data.get('scenario_id'),
    display_name: data.get('display_name'),
    status: data.get('status'),
    description: data.get('description'),
    slot_schema_id: data.get('slot_schema_id'),
    classification_route_id: data.get('classification_route_id'),
    orchestrator_policy_id: data.get('orchestrator_policy_id'),
    tool_launch_matrix_id: data.get('tool_launch_matrix_id'),
    prompt_pack_id: data.get('prompt_pack_id'),
    escalation_policy_id: data.get('escalation_policy_id'),
    default_channel_id: data.get('default_channel_id'),
    allowed_channel_ids: selectedValues(form.elements.allowed_channel_ids),
    audit_required: data.get('audit_required') === 'true',
    log_required: data.get('log_required') === 'true',
    tags: parseExistingScenarioTags(data.get('existing_tags')),
  });
  await applyScenarioMutation(state.scenarioOperation, scenario);
}

async function deleteScenarioForm() {
  if (!state.scenarioId) {
    throw new Error('Сценарий для удаления не выбран.');
  }
  await applyScenarioMutation('delete', { scenario_id: state.scenarioId });
}

async function ensureResolutionProfilesForSlots(slots) {
  const slotsWithoutProfile = slots.filter((slot) =>
    slot.fill_method === 'resolution_profile' && !slot.resolution_profile_id,
  );
  if (!slotsWithoutProfile.length) {
    return;
  }

  const active = await api('/admin/config/active/attribute_resolution_profiles');
  const payload = JSON.parse(JSON.stringify(active.payload));
  const profiles = payload.profiles || [];
  let changed = false;

  for (const slot of slotsWithoutProfile) {
    const existingProfile = profiles.find((profile) => profileOutputSlotIds(profile).includes(slot.slot_id));
    if (existingProfile) {
      slot.resolution_profile_id = existingProfile.profile_id;
      continue;
    }
    const profile = resolutionProfileBootstrapTemplate(slot, profiles);
    profiles.push(profile);
    slot.resolution_profile_id = profile.profile_id;
    changed = true;
  }

  if (!changed) {
    return;
  }
  payload.profiles = profiles;
  await activateConfigPayload('attribute_resolution_profiles', payload, active.active_version_id);
  state.lastData.resolutionProfiles = profiles;
}

function resolutionProfileBootstrapTemplate(slot, profiles) {
  const profileId = nextBootstrapProfileId(slot.slot_id, profiles);
  const slotName = slot.display_name || humanizeTechnicalKey(slot.slot_id);
  const question = slot.fallback_question
    || slot.user_question
    || `Уточните значение поля "${slotName}".`;
  const profile = {
    profile_id: profileId,
    display_name: `Разрешение: ${slotName}`,
    status: 'active',
    description: `Черновик профиля разрешения для слота ${slot.slot_id}. Настройте источник данных и LLM-правила в разделе "1. Разрешение атрибутов".`,
    target_slot_id: slot.slot_id,
    enrichment_steps: [],
    output_slots_order: [{
      slot_id: slot.slot_id,
      order: 1,
      required_for_success: true,
      source_hint: slot.slot_id,
      fallback: 'ask_clarification',
    }],
    llm_resolution_script: {
      script_text: '',
      response_contract: defaultResolutionResponseContract(),
    },
    human_resolution_policy: {
      clarification_question: question,
      clarification_slots: [slot.slot_id],
      handoff_package: [slot.slot_id],
      handoff_action: 'operator_handoff',
      fallback_action: 'ask_user',
    },
    fallback: {
      action: 'ask_user',
      question,
    },
    confidence_threshold: 0.7,
    confidence_thresholds: {
      auto_fill: 0.7,
      clarification: 0.7,
      operator_handoff: 0.5,
    },
    max_attempts: 1,
  };
  profile.llm_resolution_script.script_text = defaultResolutionScriptText(profile);
  return profile;
}

function nextBootstrapProfileId(slotId, profiles) {
  const existing = new Set((profiles || []).map((profile) => profile.profile_id));
  const normalizedSlotId = String(slotId || 'attribute')
    .toLowerCase()
    .replace(/[^a-z0-9_.-]+/g, '_')
    .replace(/^[^a-z]+/, 'attribute_');
  const base = `profile.${normalizedSlotId}.resolution`;
  let candidate = base;
  let index = 2;
  while (existing.has(candidate)) {
    candidate = `${base}_${index}`;
    index += 1;
  }
  return candidate;
}

async function saveSlotSchemaForm(form) {
  const data = new FormData(form);
  const slots = parseSlotCards(form);
  await ensureResolutionProfilesForSlots(slots);
  const slotSchema = {
    slot_schema_id: String(data.get('slot_schema_id') || '').trim(),
    display_name: String(data.get('display_name') || '').trim(),
    required_slots: slots.filter((slot) => slot.required).map((slot) => slot.slot_id),
    auto_fill_slots: slots
      .filter((slot) => !['user_question', 'operator_manual'].includes(slot.fill_method))
      .map((slot) => slot.slot_id),
    question_order: slots
      .filter((slot) => ['user_question', 'resolution_profile', 'operator_manual'].includes(slot.fill_method))
      .sort((left, right) => left.question_order - right.question_order)
      .map((slot) => slot.slot_id),
    slots: slots.map(({ question_order: _questionOrder, ...slot }) => slot),
  };
  await applyConfigItemMutation({
    domain: 'slot_schemas',
    collectionKey: 'slot_schemas',
    idKey: 'slot_schema_id',
    item: slotSchema,
    operation: state.slotSchemaOperation,
    referenceKey: 'slot_schema_id',
    stateIdKey: 'slotSchemaId',
    stateOperationKey: 'slotSchemaOperation',
    successNoun: 'Схема слотов',
  });
}

async function deleteSlotSchemaForm() {
  if (!state.slotSchemaId) {
    throw new Error('Схема слотов для удаления не выбрана.');
  }
  await applyConfigItemMutation({
    domain: 'slot_schemas',
    collectionKey: 'slot_schemas',
    idKey: 'slot_schema_id',
    item: { slot_schema_id: state.slotSchemaId },
    operation: 'delete',
    referenceKey: 'slot_schema_id',
    stateIdKey: 'slotSchemaId',
    stateOperationKey: 'slotSchemaOperation',
    successNoun: 'Схема слотов',
  });
}

function parseSlotCards(form) {
  const cards = Array.from(form.querySelectorAll('[data-slot-card]'));
  const slots = cards.map((card, index) => {
    const value = (name) => card.querySelector(`[name="${name}"]`)?.value?.trim() || '';
    const slot = {
      slot_id: value('slot_id'),
      display_name: value('display_name'),
      priority_group: value('priority_group'),
      required: parseBoolean(value('required')),
      fill_method: value('fill_method'),
      question_order: parseInt(value('question_order') || String(index + 1), 10),
    };
    if (slot.fill_method === 'user_question') {
      slot.user_question = value('user_question');
    } else if (slot.fill_method === 'case') {
      slot.case_source_ref = value('case_source_ref');
    } else if (slot.fill_method === 'llm_extraction') {
      slot.extraction_instruction = value('extraction_instruction');
      const examples = parseLines(value('examples'));
      if (examples.length) slot.examples = examples;
    } else if (slot.fill_method === 'slot_autofill') {
      const sourceRef = value('autofill_source_ref');
      if (sourceRef) slot.autofill_source_ref = sourceRef;
    } else if (slot.fill_method === 'resolution_profile') {
      const profileId = value('resolution_profile_id');
      if (profileId) {
        slot.resolution_profile_id = profileId;
      }
      const fallbackQuestion = value('fallback_question');
      if (fallbackQuestion) slot.fallback_question = fallbackQuestion;
    } else if (slot.fill_method === 'operator_manual') {
      slot.operator_hint = value('operator_hint');
    }
    const confidenceOverrides = slot.fill_method === 'llm_extraction'
      ? parseConfidenceThresholdsFromCard(card, 'slot_confidence')
      : {};
    if (Object.keys(confidenceOverrides).length) {
      slot.confidence_overrides = confidenceOverrides;
    }
    return slot;
  });
  const emptySlot = slots.find((slot) => !slot.slot_id || !slot.display_name || !slot.priority_group || !slot.fill_method);
  if (emptySlot) {
    throw new Error('Каждый слот должен иметь ключ, название, priority group и способ заполнения.');
  }
  const invalidSlot = slots.find((slot) => !/^[a-z][a-z0-9_.-]*$/.test(slot.slot_id));
  if (invalidSlot) {
    throw new Error(`Ключ слота "${invalidSlot.slot_id}" должен начинаться с латинской буквы и содержать только латиницу, цифры, _, - или точку.`);
  }
  const duplicateSlotId = slots
    .map((slot) => slot.slot_id)
    .find((slotId, index, all) => all.indexOf(slotId) !== index);
  if (duplicateSlotId) {
    throw new Error(`Ключ слота дублируется: ${duplicateSlotId}.`);
  }
  const missingUserQuestion = slots.find((slot) => slot.fill_method === 'user_question' && !slot.user_question);
  if (missingUserQuestion) {
    throw new Error(`Для слота ${missingUserQuestion.slot_id} заполните вопрос клиенту.`);
  }
  const missingCaseSource = slots.find((slot) => slot.fill_method === 'case' && !slot.case_source_ref);
  if (missingCaseSource) {
    throw new Error(`Для слота ${missingCaseSource.slot_id} укажите путь в данных обращения.`);
  }
  const missingInstruction = slots.find((slot) => slot.fill_method === 'llm_extraction' && !slot.extraction_instruction);
  if (missingInstruction) {
    throw new Error(`Для слота ${missingInstruction.slot_id} заполните инструкцию для модели.`);
  }
  const missingOperatorHint = slots.find((slot) => slot.fill_method === 'operator_manual' && !slot.operator_hint);
  if (missingOperatorHint) {
    throw new Error(`Для слота ${missingOperatorHint.slot_id} заполните подсказку оператору.`);
  }
  const profileById = Object.fromEntries((state.lastData.resolutionProfiles || []).map((profile) => [profile.profile_id, profile]));
  const mismatchedProfile = slots.find((slot) => {
    if (slot.fill_method !== 'resolution_profile' || !slot.resolution_profile_id) return false;
    const profile = profileById[slot.resolution_profile_id];
    return profile && !profileOutputSlotIds(profile).includes(slot.slot_id);
  });
  if (mismatchedProfile) {
    const profile = profileById[mismatchedProfile.resolution_profile_id];
    throw new Error(
      `Профиль "${profile.display_name}" не заполняет слот ${mismatchedProfile.slot_id}. `
      + `Доступные выходные слоты профиля: ${formatList(profileOutputSlotIds(profile))}.`,
    );
  }
  return slots;
}

async function saveRouteForm(form) {
  const data = new FormData(form);
  const route = {
    route_id: String(data.get('route_id') || '').trim(),
    display_name: String(data.get('display_name') || '').trim(),
    priority: String(data.get('priority') || '').trim(),
    route: String(data.get('route') || '').trim(),
    action: String(data.get('action') || '').trim(),
    workflow_state_id: String(data.get('workflow_state_id') || '').trim(),
    confidence: {
      rules_min: Number(data.get('rules_min')),
      llm_min: Number(data.get('llm_min')),
      human_handoff_below: Number(data.get('human_handoff_below')),
    },
    rules: {
      rule_items: parseClassificationRules(form),
    },
    top_categories_on_low_confidence: parseInt(data.get('top_categories_on_low_confidence'), 10),
  };
  await applyConfigItemMutation({
    domain: 'classification_routes',
    collectionKey: 'routes',
    idKey: 'route_id',
    item: route,
    operation: state.routeOperation,
    referenceKey: 'classification_route_id',
    stateIdKey: 'routeId',
    stateOperationKey: 'routeOperation',
    successNoun: 'Маршрут',
  });
}

function parseClassificationRules(form) {
  const rules = [];
  form.querySelectorAll('[data-route-rule-card]').forEach((card) => {
    const text = card.querySelector('[name="rule_text"]')?.value?.trim() || '';
    if (!text) return;
    rules.push({
      text,
      match_type: card.querySelector('[name="rule_match_type"]')?.value?.trim() || 'phrase',
      polarity: card.querySelector('[name="rule_polarity"]')?.value?.trim() || 'positive',
      weight: Number(card.querySelector('[name="rule_weight"]')?.value || 0.5),
      required: parseBoolean(card.querySelector('[name="rule_required"]')?.value),
      blocking: parseBoolean(card.querySelector('[name="rule_blocking"]')?.value),
      explanation: card.querySelector('[name="rule_explanation"]')?.value?.trim() || `Признак классификации: ${text}`,
    });
  });
  if (!rules.length) {
    throw new Error('Маршрут должен содержать хотя бы одно правило классификации.');
  }
  return rules;
}

async function deleteRouteForm() {
  if (!state.routeId) {
    throw new Error('Маршрут для удаления не выбран.');
  }
  await applyConfigItemMutation({
    domain: 'classification_routes',
    collectionKey: 'routes',
    idKey: 'route_id',
    item: { route_id: state.routeId },
    operation: 'delete',
    referenceKey: 'classification_route_id',
    stateIdKey: 'routeId',
    stateOperationKey: 'routeOperation',
    successNoun: 'Маршрут',
  });
}

async function savePolicyForm(form) {
  const data = new FormData(form);
  const policy = {
    policy_id: String(data.get('policy_id') || '').trim(),
    display_name: String(data.get('display_name') || '').trim(),
    max_iterations: parseInt(data.get('max_iterations'), 10),
    consecutive_tool_errors_to_escalate: parseInt(data.get('consecutive_tool_errors_to_escalate'), 10),
    stop_conditions: formList(data, 'stop_conditions'),
    allowed_react_action_groups: formList(data, 'allowed_react_action_groups'),
  };
  await applyConfigItemMutation({
    domain: 'orchestrator_policy',
    collectionKey: 'policies',
    idKey: 'policy_id',
    item: policy,
    operation: state.policyOperation,
    referenceKey: 'orchestrator_policy_id',
    stateIdKey: 'policyId',
    stateOperationKey: 'policyOperation',
    successNoun: 'ReAct-политика',
  });
}

async function saveConfidenceDefaultsForm(form) {
  const data = new FormData(form);
  const active = await api('/admin/config/active/orchestrator_policy');
  const payload = JSON.parse(JSON.stringify(active.payload));
  payload.confidence_defaults = parseConfidenceThresholdsFromForm(data, 'system_confidence', { required: true });
  const version = await activateConfigPayload('orchestrator_policy', payload, active.active_version_id);
  setNotice(`Системные пороги уверенности сохранены. Активирована версия ${version.version_id}.`, 'success');
  await renderScenarioReact();
}

async function deletePolicyForm() {
  if (!state.policyId) {
    throw new Error('ReAct-политика для удаления не выбрана.');
  }
  await applyConfigItemMutation({
    domain: 'orchestrator_policy',
    collectionKey: 'policies',
    idKey: 'policy_id',
    item: { policy_id: state.policyId },
    operation: 'delete',
    referenceKey: 'orchestrator_policy_id',
    stateIdKey: 'policyId',
    stateOperationKey: 'policyOperation',
    successNoun: 'ReAct-политика',
  });
}

async function saveToolLaunchForm(form) {
  const data = new FormData(form);
  const launchCards = Array.from(form.querySelectorAll('[data-launch-card]'));
  const launches = [];
  for (const [index, card] of launchCards.entries()) {
    const value = (prefix) => card.querySelector(`[name^="${prefix}_"]`)?.value?.trim() || '';
    const executionMode = value('execution_mode') || 'operator_approval';
    const parameterBindings = parameterBindingsFromRows(card, {
      validate: true,
      launchLabel: `Запуск ${index + 1}`,
    });
    const toolName = value('tool_name');
    const tool = findToolInCatalog(state.lastData.toolCatalog || [], toolName);
    const binding = currentToolBinding(tool);
    if (!binding) {
      throw new Error(`Запуск ${index + 1}: для ReAct-вызова ${toolName || 'н/д'} не настроена привязка операции.`);
    }
    const launch = {
      launch_id: value('launch_id'),
      tool_name: toolName,
      required_slots: requiredSlotsFromParameterBindings(parameterBindings),
      parameter_bindings: parameterBindings,
      execution_level: executionMode,
      target_execution_level: executionMode,
      endpoint_id: binding.endpoint_id,
      operation_id: binding.operation_id,
      risk_level: value('risk_level'),
      stop_on_error: parseBoolean(value('stop_on_error')),
      completion_policy: completionPolicyFromCard(card),
    };
    const approvalRole = value('approval_role');
    if (approvalRole) {
      launch.approval_role = approvalRole;
    }
    launches.push(launch);
  }
  const matrix = {
    matrix_id: String(data.get('matrix_id') || '').trim(),
    display_name: String(data.get('display_name') || '').trim(),
    launches,
  };
  await applyConfigItemMutation({
    domain: 'tool_launch_matrix',
    collectionKey: 'matrices',
    idKey: 'matrix_id',
    item: matrix,
    operation: state.toolMatrixOperation,
    referenceKey: 'tool_launch_matrix_id',
    stateIdKey: 'toolMatrixId',
    stateOperationKey: 'toolMatrixOperation',
    successNoun: 'Матрица ReAct-вызовов',
  });
}

function completionPolicyFromCard(card) {
  const read = (prefix) => card.querySelector(`[name^="${prefix}_"]`)?.value?.trim() || '';
  const mode = read('completion_mode') || 'sync';
  const policy = {
    mode,
    max_wait_seconds: mode === 'sync' ? 0 : Number(read('completion_max_wait_seconds') || 86400),
    timeout_action: read('completion_timeout_action') || (mode === 'sync' ? 'resume_agent' : 'escalate_operator'),
  };
  const checkInterval = Number(read('completion_check_interval_seconds') || 0);
  const expectedEventType = read('completion_expected_event_type');
  if (checkInterval > 0) {
    policy.check_interval_seconds = checkInterval;
  }
  if (expectedEventType) {
    policy.expected_event_type = expectedEventType;
  }
  if (mode === 'external_event' && !policy.expected_event_type) {
    throw new Error('Для external event/callback укажите ожидаемый тип события.');
  }
  if (mode === 'timer_wait' && checkInterval > policy.max_wait_seconds) {
    throw new Error('Интервал проверки не должен быть больше максимального ожидания.');
  }
  return policy;
}

async function deleteToolMatrixForm() {
  if (!state.toolMatrixId) {
    throw new Error('Матрица ReAct-вызовов для удаления не выбрана.');
  }
  await applyConfigItemMutation({
    domain: 'tool_launch_matrix',
    collectionKey: 'matrices',
    idKey: 'matrix_id',
    item: { matrix_id: state.toolMatrixId },
    operation: 'delete',
    referenceKey: 'tool_launch_matrix_id',
    stateIdKey: 'toolMatrixId',
    stateOperationKey: 'toolMatrixOperation',
    successNoun: 'Матрица ReAct-вызовов',
  });
}

async function saveEscalationForm(form) {
  const data = new FormData(form);
  const policy = {
    policy_id: String(data.get('policy_id') || '').trim(),
    display_name: String(data.get('display_name') || '').trim(),
    auto_close: {
      requires_tool_success: parseBoolean(data.get('requires_tool_success')),
    },
    handoff_conditions: formList(data, 'handoff_conditions'),
    major_incident: {
      affected_users_threshold: parseInt(data.get('affected_users_threshold'), 10),
    },
    handoff_package: formList(data, 'handoff_package'),
    user_notification_template: String(data.get('user_notification_template') || '').trim(),
  };
  await applyConfigItemMutation({
    domain: 'escalation_policies',
    collectionKey: 'policies',
    idKey: 'policy_id',
    item: policy,
    operation: state.escalationOperation,
    referenceKey: 'escalation_policy_id',
    stateIdKey: 'escalationPolicyId',
    stateOperationKey: 'escalationOperation',
    successNoun: 'Политика эскалации',
  });
}

async function deleteEscalationForm() {
  if (!state.escalationPolicyId) {
    throw new Error('Политика эскалации для удаления не выбрана.');
  }
  await applyConfigItemMutation({
    domain: 'escalation_policies',
    collectionKey: 'policies',
    idKey: 'policy_id',
    item: { policy_id: state.escalationPolicyId },
    operation: 'delete',
    referenceKey: 'escalation_policy_id',
    stateIdKey: 'escalationPolicyId',
    stateOperationKey: 'escalationOperation',
    successNoun: 'Политика эскалации',
  });
}

async function saveInteractionChannelForm(form) {
  const data = new FormData(form);
  const channel = {
    channel_id: String(data.get('channel_id') || '').trim(),
    display_name: String(data.get('display_name') || '').trim(),
    mode: String(data.get('mode') || '').trim(),
    description: String(data.get('description') || '').trim(),
    question_delivery: parseChannelAction(data, 'question_delivery'),
    waiting_policy: {
      first_reminder_after_seconds: parseInt(data.get('first_reminder_after_seconds'), 10),
      discussion_timeout_seconds: parseInt(data.get('discussion_timeout_seconds'), 10),
      sla_elapsed_percent_threshold: parseInt(data.get('sla_elapsed_percent_threshold'), 10),
      on_no_answer: String(data.get('on_no_answer') || '').trim(),
      auto_close_requires_client_confirmation: parseBoolean(data.get('auto_close_requires_client_confirmation')),
      pause_sla_on_client_wait: parseBoolean(data.get('pause_sla_on_client_wait')),
      client_wait_auto_close_after_hours: parseInt(data.get('client_wait_auto_close_after_hours'), 10),
    },
    incomplete_discussion_action: parseChannelAction(data, 'incomplete_discussion_action'),
    escalation_action: parseChannelAction(data, 'escalation_action'),
    action_profiles: parseChannelProfileCards(form),
    enabled: parseBoolean(data.get('enabled')),
  };
  await applyInteractionChannelMutation(state.interactionChannelOperation, channel);
}

async function deleteInteractionChannelForm() {
  if (!state.interactionChannelId) {
    throw new Error('Канал для удаления не выбран.');
  }
  await applyInteractionChannelMutation('delete', { channel_id: state.interactionChannelId });
}

function parseChannelAction(data, prefix) {
  const action = {
    action_type: String(data.get(`${prefix}_action_type`) || '').trim(),
  };
  for (const field of ['tool_name', 'endpoint_id', 'operation_id', 'message_template']) {
    const value = String(data.get(`${prefix}_${field}`) || '').trim();
    if (value) {
      action[field] = value;
    }
  }
  return action;
}

function parseChannelProfileCards(form) {
  return Array.from(form.querySelectorAll('[data-channel-profile-card]')).map((card, index) => {
    const value = (name) => card.querySelector(`[name="${name}"]`)?.value?.trim() || '';
    const profile = {
      profile_id: value('profile_id') || `custom_profile_${index + 1}`,
      display_name: value('display_name'),
      event_type: value('event_type'),
      action: {
        action_type: value('action_type'),
      },
    };
    for (const field of ['tool_name', 'endpoint_id', 'operation_id', 'message_template']) {
      const fieldValue = value(field);
      if (fieldValue) {
        profile.action[field] = fieldValue;
      }
    }
    return profile;
  });
}

async function savePromptPackForm(form) {
  const data = new FormData(form);
  const promptPack = {
    prompt_pack_id: String(data.get('prompt_pack_id') || '').trim(),
    display_name: String(data.get('display_name') || '').trim(),
    status: String(data.get('status') || '').trim(),
    active_version: String(data.get('active_version') || '').trim(),
    blocks: {
      role_context: String(data.get('role_context') || '').trim(),
      behavior_principles: String(data.get('behavior_principles') || '').trim(),
      slot_schemas: String(data.get('slot_schemas') || '').trim(),
      classification_confidence: String(data.get('classification_confidence') || '').trim(),
      react_planning: String(data.get('react_planning') || '').trim(),
      tool_rules: String(data.get('tool_rules') || '').trim(),
      escalation_response: String(data.get('escalation_response') || '').trim(),
    },
  };
  await applyPromptPackMutation(state.promptPackOperation, promptPack);
}

async function deletePromptPackForm() {
  if (!state.promptPackId) {
    throw new Error('Пакет промптов для удаления не выбран.');
  }
  await applyPromptPackMutation('delete', { prompt_pack_id: state.promptPackId });
}

async function saveModelRoutingForm(form) {
  const data = new FormData(form);
  const secretUpdateCount = await saveModelSecretsFromForm(data);
  const payload = modelPayloadFromForm(data);
  const version = await activateConfigPayload('model_routing', payload, state.modelRoutingBaseVersionId);
  const secretText = secretUpdateCount ? ` Обновлено секретов: ${secretUpdateCount}; для LiteLLM может потребоваться перезапуск.` : '';
  setNotice(`Настройки моделей сохранены. Активирована версия ${version.version_id}.${secretText}`, 'success');
  await renderModels();
}

async function saveModelSecretsFromForm(data) {
  const providerIds = Array.from(new Set(data.getAll('model_provider_id').map((value) => String(value || '').trim()).filter(Boolean)));
  let savedCount = 0;
  for (const providerId of providerIds) {
    const secretValue = String(data.get(`${providerId}_secret_value`) || '');
    const envName = String(data.get(`${providerId}_api_key_env`) || '').trim();
    if (!secretValue.trim()) {
      continue;
    }
    if (!envName) {
      throw new Error(`Для подключения ${providerId} задайте Env для ключа перед сохранением секрета.`);
    }
    await api('/admin/models/secrets', {
      method: 'POST',
      body: JSON.stringify({
        provider_id: providerId,
        env_name: envName,
        secret_value: secretValue,
      }),
    });
    savedCount += 1;
  }
  return savedCount;
}

function modelPayloadFromForm(data) {
  const providerIds = Array.from(new Set(data.getAll('model_provider_id').map((value) => String(value || '').trim()).filter(Boolean)));
  if (!providerIds.length) {
    throw new Error('Добавьте хотя бы одно подключение модели.');
  }
  const providers = Object.fromEntries(providerIds.map((providerId) => [providerId, readModelProvider(data, providerId)]));
  const enabledAliases = new Set(
    Object.values(providers)
      .filter((provider) => provider.enabled && provider.model_alias)
      .map((provider) => provider.model_alias),
  );
  const fallbackProviderId = providerIds.find((providerId) => providers[providerId].enabled) || providerIds[0];
  const requestedActiveProviderId = String(data.get('active_provider') || fallbackProviderId).trim();
  const activeProviderId = providers[requestedActiveProviderId]?.enabled ? requestedActiveProviderId : fallbackProviderId;
  const activeProvider = providers[activeProviderId];
  const defaultAlias = enabledAliases.has(String(data.get('default_model_alias') || '').trim())
    ? String(data.get('default_model_alias') || '').trim()
    : activeProvider.model_alias;
  const routeAlias = (name) => {
    const alias = String(data.get(name) || '').trim();
    return enabledAliases.has(alias) ? alias : defaultAlias;
  };
  const fallbackFrom = String(data.get('fallback_from') || '').trim();
  const fallbackTo = String(data.get('fallback_to') || '').trim();
  const payload = {
    schema_version: '1.0',
    active_provider: activeProviderId,
    providers,
    gateway: {
      type: String(data.get('gateway_type') || 'litellm').trim(),
      base_url: String(data.get('gateway_base_url') || '').trim(),
    },
    default_model_alias: defaultAlias,
    upstream_model: activeProvider.model,
    routing: {
      default: routeAlias('route_default'),
      classification: routeAlias('route_classification'),
      summarization: routeAlias('route_summarization'),
      tool_selection: routeAlias('route_tool_selection'),
      slot_resolution: routeAlias('route_slot_resolution'),
    },
    fallbacks: enabledAliases.has(fallbackFrom) && enabledAliases.has(fallbackTo) ? [{ from: fallbackFrom, to: fallbackTo }] : [],
    settings: {
      temperature: activeProvider.temperature,
      context_length: activeProvider.context_length,
      rate_limits: {
        requests_per_minute: activeProvider.rate_limits.requests_per_minute,
        tokens_per_minute: activeProvider.rate_limits.tokens_per_minute,
      },
    },
    runtime: {
      active_backend: activeProviderId,
    },
  };
  return payload;
}

async function switchModelProvider(providerId) {
  const active = await api('/admin/config/active/model_routing');
  const config = normalizeModelConfig(active.payload || state.lastData.modelConfig || {});
  const provider = config.providers?.[providerId];
  if (!provider) {
    throw new Error(`Профиль модели не найден: ${providerId}`);
  }
  if (!provider.enabled) {
    throw new Error(`Профиль модели отключен: ${provider.display_name || providerId}`);
  }
  const alias = provider.model_alias;
  const payload = {
    ...config,
    active_provider: providerId,
    default_model_alias: alias,
    upstream_model: provider.model,
    routing: {
      default: alias,
      classification: alias,
      summarization: alias,
      tool_selection: alias,
      slot_resolution: alias,
    },
    settings: {
      temperature: provider.temperature,
      context_length: provider.context_length,
      rate_limits: provider.rate_limits,
    },
    runtime: {
      active_backend: providerId,
    },
  };
  if (providerId !== 'vllm_cpu' && config.providers.vllm_cpu?.enabled) {
    payload.fallbacks = [{ from: alias, to: config.providers.vllm_cpu.model_alias }];
  } else {
    payload.fallbacks = [];
  }
  const version = await activateConfigPayload('model_routing', payload, active.active_version_id);
  setNotice(`Активное подключение переключено на ${provider.display_name}. Активирована версия ${version.version_id}.`, 'success');
  await renderModels();
}

function readModelProvider(data, providerId) {
  const field = (name) => String(data.get(`${providerId}_${name}`) || '').trim();
  return {
    enabled: parseBoolean(data.get(`${providerId}_enabled`)),
    provider_type: field('provider_type') || (providerId === 'vllm_cpu' || providerId === 'openai' ? providerId : 'litellm'),
    display_name: field('display_name'),
    base_url: field('base_url'),
    model_alias: field('model_alias'),
    model: field('model'),
    api_key_env: field('api_key_env'),
    api_key_required: parseBoolean(data.get(`${providerId}_api_key_required`)),
    context_length: parseInt(field('context_length'), 10),
    temperature: Number(field('temperature')),
    max_tokens: parseInt(field('max_tokens'), 10),
    timeout_seconds: parseInt(field('timeout_seconds'), 10),
    rate_limits: {
      requests_per_minute: parseInt(field('requests_per_minute'), 10),
      tokens_per_minute: parseInt(field('tokens_per_minute'), 10),
    },
  };
}

async function saveResolutionProfileForm(form) {
  const data = new FormData(form);
  const clarificationQuestion = String(data.get('clarification_question') || '').trim();
  const selectedTargetSlotId = String(data.get('target_slot_id') || '').trim();
  const customTargetSlotId = String(data.get('target_slot_id_custom') || '').trim();
  const targetSlotId = selectedTargetSlotId === '__custom__'
    ? customTargetSlotId
    : selectedTargetSlotId;
  if (!targetSlotId) {
    throw new Error('Выберите целевой слот или укажите ключ нового слота.');
  }
  if (!/^[a-z][a-z0-9_.-]*$/.test(targetSlotId)) {
    throw new Error('Ключ целевого слота должен начинаться с латинской буквы и содержать только латиницу, цифры, _, - или точку.');
  }
  const outputRules = parseResolutionOutputRules(form, targetSlotId);
  const outputSlotIds = outputRules.map((rule) => rule.slot_id);
  const slotContext = currentResolutionSlotContextFromForm(form);
  const availableSlotIds = new Set([
    ...outputSlotIds,
    targetSlotId,
    ...(slotContext.slots || []).map((slot) => slot.slot_id),
  ].filter(Boolean));
  const clarificationSlots = formList(data, 'clarification_slots')
    .filter((slotId) => availableSlotIds.has(slotId));
  const handoffSlots = formList(data, 'handoff_package')
    .filter((slotId) => availableSlotIds.has(slotId));
  const enrichmentSteps = parseEnrichmentSteps(form);
  const existingProfile = currentResolutionProfileById(String(data.get('profile_id') || '').trim());
  const profile = {
    profile_id: String(data.get('profile_id') || '').trim(),
	    display_name: String(data.get('display_name') || '').trim(),
	    status: existingProfile?.status || 'active',
	    description: String(data.get('description') || '').trim(),
	    slot_schema_id: slotContext.schema?.slot_schema_id || String(data.get('slot_schema_id') || '').trim(),
	    target_slot_id: targetSlotId,
    enrichment_steps: enrichmentSteps,
    output_slots_order: outputRules,
    llm_resolution_script: {
      script_text: String(data.get('llm_resolution_script_text') || '').trim(),
      response_contract: defaultResolutionResponseContract(),
    },
    human_resolution_policy: {
      clarification_question: clarificationQuestion,
      clarification_slots: clarificationSlots.length ? clarificationSlots : [targetSlotId].filter(Boolean),
      handoff_package: handoffSlots.length ? handoffSlots : outputSlotIds,
      handoff_action: String(data.get('handoff_action') || 'operator_handoff').trim(),
      fallback_action: String(data.get('fallback_action') || 'ask_user').trim(),
    },
    max_attempts: parseInt(data.get('max_attempts'), 10),
  };
  if (!profile.llm_resolution_script.script_text) {
    profile.llm_resolution_script.script_text = defaultResolutionScriptText(profile);
  }
  const confidenceThreshold = String(data.get('confidence_threshold') || '').trim();
  if (confidenceThreshold) {
    profile.confidence_threshold = Number(confidenceThreshold);
  }
  const profileThresholds = {};
  for (const [field, formKey] of Object.entries({
    auto_fill: 'confidence_auto_fill',
    clarification: 'confidence_clarification',
    operator_handoff: 'confidence_operator_handoff',
  })) {
    const raw = String(data.get(formKey) || '').trim();
    if (raw) {
      profileThresholds[field] = Number(raw);
    }
  }
  if (Object.keys(profileThresholds).length) {
    profile.confidence_thresholds = profileThresholds;
  }
  await applyResolutionProfileMutation(state.resolutionOperation, profile);
}

async function deleteResolutionProfileForm() {
  if (!state.resolutionProfileId) {
    throw new Error('Профиль для удаления не выбран.');
  }
  await applyResolutionProfileMutation('delete', { profile_id: state.resolutionProfileId });
}

async function saveSlotAutofillProfileForm(form) {
  const draft = slotAutofillDraftFromForm(form);
  const existingProfile = currentSlotAutofillProfileById(draft.profile_id);
  let output = { mappings: draft.output_mapping || [], newSlots: [] };
  let profile = draft;
  if (slotAutofillInstructionNeedsCompile(draft, existingProfile)) {
    const compiled = await compileSlotAutofillDraft(draft);
    const validationErrors = compiled.result.validation_errors || [];
    if (validationErrors.length) {
      throw new Error(`Инструкция не преобразована в структуру: ${validationErrors.join('; ')}`);
    }
    profile = compiled.profile;
    output = { mappings: profile.output_mapping || [], newSlots: [] };
  } else {
    output = parseSlotAutofillOutputRows(form);
    profile = {
      ...draft,
      output_mapping: output.mappings,
    };
  }
  if (!output.mappings.length) {
    throw new Error('Добавьте хотя бы одно поле результата, которое заполняет слот.');
  }
  if (!profile.profile_id || !profile.display_name || !profile.slot_schema_id || !profile.react_call) {
    throw new Error('Заполните название, схему слотов и ReAct-вызов.');
  }
  if (output.newSlots.length) {
    await ensureSlotAutofillSlots(profile, output.newSlots);
  }
  await applySlotAutofillProfileMutation(state.slotAutofillOperation, profile);
}

async function deleteSlotAutofillProfileForm() {
  if (!state.slotAutofillProfileId) {
    throw new Error('Профиль автозаполнения для удаления не выбран.');
  }
  await applySlotAutofillProfileMutation('delete', { profile_id: state.slotAutofillProfileId });
}

function parseSlotAutofillInputMapping(form) {
  const mapping = {};
  form.querySelectorAll('[data-slot-autofill-input-row]').forEach((row) => {
    const parameter = row.querySelector('[data-slot-autofill-param-name]')?.value?.trim();
    const mode = row.querySelector('[data-slot-autofill-param-source-mode]')?.value?.trim();
    const custom = row.querySelector('[data-slot-autofill-param-source-custom]')?.value?.trim();
    if (!parameter || !mode || mode === '__none__') return;
    const sourceRef = mode.endsWith(':') ? `${mode}${custom}` : mode;
    if (sourceRef && !sourceRef.endsWith(':')) {
      mapping[parameter] = sourceRef;
    }
  });
  return mapping;
}

function parseSlotAutofillOutputRows(form) {
  const mappings = [];
  const newSlots = [];
  const seenTargets = new Set();
  form.querySelectorAll('[data-slot-autofill-output-row]').forEach((row) => {
    const resultField = row.querySelector('[data-slot-autofill-result-field]')?.value?.trim();
    const action = row.querySelector('[data-slot-autofill-output-action]')?.value || 'ignore';
    const requiredForSuccess = row.querySelector('[data-slot-autofill-required]')?.checked === true;
    if (!resultField || action === 'ignore') return;
    let targetSlot = '';
    if (action === 'existing') {
      targetSlot = row.querySelector('[data-slot-autofill-target-slot]')?.value?.trim() || '';
      if (!targetSlot) {
        throw new Error(`Для поля результата ${resultField} выберите существующий слот.`);
      }
    } else if (action === 'new') {
      targetSlot = row.querySelector('[data-slot-autofill-new-slot-key]')?.value?.trim() || '';
      const displayName = row.querySelector('[data-slot-autofill-new-slot-display]')?.value?.trim() || humanizeTechnicalKey(targetSlot);
      const priorityGroup = row.querySelector('[data-slot-autofill-new-slot-priority-value]')?.value || 'context';
      const required = row.querySelector('[data-slot-autofill-new-slot-required-value]')?.checked === true;
      if (!targetSlot || !displayName) {
        throw new Error(`Для поля результата ${resultField} заполните ключ и название нового слота.`);
      }
      newSlots.push({
        slot_id: targetSlot,
        display_name: displayName,
        priority_group: priorityGroup,
        required,
        fill_method: 'slot_autofill',
        autofill_source_ref: resultField,
      });
    }
    if (!/^[a-z][a-z0-9_.-]*$/.test(targetSlot)) {
      throw new Error(`Ключ слота "${targetSlot}" должен начинаться с латинской буквы и содержать только латиницу, цифры, _, - или точку.`);
    }
    if (seenTargets.has(targetSlot)) {
      throw new Error(`Слот ${targetSlot} указан в автозаполнении несколько раз.`);
    }
    seenTargets.add(targetSlot);
    mappings.push({
      result_field: resultField,
      target_slot: targetSlot,
      required_for_success: requiredForSuccess,
    });
  });
  return { mappings, newSlots };
}

function slotAutofillDraftFromForm(form) {
  const data = new FormData(form);
  let output = { mappings: [] };
  try {
    output = parseSlotAutofillOutputRows(form);
  } catch {
    output = { mappings: [] };
  }
  let metadata = {};
  try {
    metadata = parseJsonField(data.get('generated_structure_metadata') || '{}', 'Метаданные сформированной структуры');
  } catch {
    metadata = {};
  }
  return {
    profile_id: String(data.get('profile_id') || '').trim(),
    display_name: String(data.get('display_name') || '').trim(),
    status: currentSlotAutofillProfileById(String(data.get('profile_id') || '').trim())?.status || 'active',
    description: String(data.get('description') || '').trim(),
    slot_schema_id: String(data.get('slot_schema_id') || '').trim(),
    enabled: currentSlotAutofillProfileById(String(data.get('profile_id') || '').trim())?.enabled ?? true,
    react_call: String(data.get('react_call') || '').trim(),
    run_order: parseInt(data.get('run_order') || '1', 10),
    accept_policy: String(data.get('accept_policy') || 'single_result').trim(),
    input_mapping: parseSlotAutofillInputMapping(form),
    output_mapping: output.mappings,
    on_no_result: String(data.get('on_no_result') || 'continue').trim(),
    on_ambiguous_result: String(data.get('on_ambiguous_result') || 'ask_client').trim(),
    configuration_instruction: String(data.get('configuration_instruction') || '').trim(),
    generated_structure_metadata: metadata,
  };
}

function slotAutofillInstructionNeedsCompile(draft, existingProfile) {
  const instruction = String(draft.configuration_instruction || '').trim();
  if (!instruction) {
    return false;
  }
  const sourceInstruction = String(draft.generated_structure_metadata?.source_instruction || '').trim();
  if (sourceInstruction) {
    return sourceInstruction !== instruction;
  }
  if (state.slotAutofillOperation === 'create') {
    return true;
  }
  return String(existingProfile?.configuration_instruction || '').trim() !== instruction;
}

function slotAutofillCompileReactCall(draft) {
  const instruction = String(draft.configuration_instruction || '').toLowerCase();
  const mentionedTool = (state.lastData.toolCatalog || [])
    .filter((tool) => tool.action_type === 'read_only')
    .find((tool) => {
      const toolName = String(tool.tool_name || '').toLowerCase();
      return toolName && instruction.includes(toolName);
    });
  return mentionedTool ? '' : draft.react_call;
}

async function compileSlotAutofillDraft(draft) {
  if (!draft.configuration_instruction) {
    throw new Error('Заполните инструкцию настройки профиля автозаполнения.');
  }
  const compileReactCall = slotAutofillCompileReactCall(draft);
  const result = await api('/admin/config-assistant/slot-autofill/compile', {
    method: 'POST',
    body: JSON.stringify({
      operator_id: state.actorId,
      instruction: draft.configuration_instruction,
      slot_schema_id: draft.slot_schema_id,
      react_call: compileReactCall || null,
    }),
  });
  const structure = result.structure || {};
  const generatedMetadata = {
    ...(draft.generated_structure_metadata || {}),
    ...(structure.generated_structure_metadata || {}),
    source_instruction: draft.configuration_instruction,
  };
  return {
    result,
    profile: {
      ...draft,
      ...structure,
      configuration_instruction: draft.configuration_instruction,
      generated_structure_metadata: generatedMetadata,
    },
  };
}

async function compileSlotAutofillProfile(target) {
  const form = target.closest('form');
  if (!form) return;
  const draft = slotAutofillDraftFromForm(form);
  const status = form.querySelector('[data-slot-autofill-compile-status]');
  if (status) {
    status.textContent = 'Формирование структуры...';
  }
  const { result, profile } = await compileSlotAutofillDraft(draft);
  const slotSchemas = state.lastData.slotSchemas || [];
  const scenarios = state.lastData.serviceScenarios || [];
  const tools = (state.lastData.toolCatalog || []).filter((tool) => tool.action_type === 'read_only');
  const wrapper = document.createElement('div');
  wrapper.innerHTML = renderSlotAutofillEditor({
    profile,
    profiles: state.lastData.slotAutofillProfiles || [],
    slotSchemas,
    scenarios,
    tools,
  }).trim();
  const nextForm = wrapper.firstElementChild;
  form.replaceWith(nextForm);
  syncAllSlotAutofillOutputRows();
  syncAllSlotAutofillSourceRows();
  const issues = [...(result.validation_errors || []), ...(result.warnings || [])];
  const nextStatus = nextForm?.querySelector?.('[data-slot-autofill-compile-status]');
  if (nextStatus) {
    nextStatus.textContent = issues.length
      ? 'Структура обновлена с замечаниями. Проверьте поля перед сохранением.'
      : 'Структура обновлена из инструкции. Сохраните профиль.';
  }
  setNotice(
    issues.length
      ? `Структура сформирована с замечаниями: ${issues.join('; ')}`
      : 'Структура профиля автозаполнения обновлена из инструкции. Проверьте и сохраните профиль.',
    issues.length ? 'error' : 'success',
  );
}

async function ensureSlotAutofillSlots(profile, newSlots) {
  const active = await api('/admin/config/active/slot_schemas');
  const payload = JSON.parse(JSON.stringify(active.payload));
  const slotSchemas = payload.slot_schemas || [];
  const schema = slotSchemas.find((item) => item.slot_schema_id === profile.slot_schema_id);
  if (!schema) {
    throw new Error(`Схема слотов не найдена: ${profile.slot_schema_id}`);
  }
  let changed = false;
  const existing = new Set((schema.slots || []).map((slot) => slot.slot_id));
  for (const slot of newSlots) {
    if (existing.has(slot.slot_id)) continue;
    schema.slots.push({
      ...slot,
      autofill_source_ref: `${profile.profile_id}:${slot.autofill_source_ref}`,
    });
    existing.add(slot.slot_id);
    changed = true;
  }
  if (!changed) return;
  schema.required_slots = (schema.slots || []).filter((slot) => slot.required).map((slot) => slot.slot_id);
  schema.auto_fill_slots = (schema.slots || [])
    .filter((slot) => !['user_question', 'operator_manual'].includes(slot.fill_method))
    .map((slot) => slot.slot_id);
  schema.question_order = (schema.slots || [])
    .filter((slot) => ['user_question', 'resolution_profile', 'operator_manual'].includes(slot.fill_method))
    .map((slot) => slot.slot_id);
  payload.slot_schemas = slotSchemas;
  await activateConfigPayload('slot_schemas', payload, active.active_version_id);
}

function compactScenarioPayload(scenario) {
  const result = {
    scenario_id: String(scenario.scenario_id || '').trim(),
    display_name: String(scenario.display_name || '').trim(),
    status: String(scenario.status || '').trim(),
    description: String(scenario.description || '').trim(),
    slot_schema_id: String(scenario.slot_schema_id || '').trim(),
    classification_route_id: String(scenario.classification_route_id || '').trim(),
    orchestrator_policy_id: String(scenario.orchestrator_policy_id || '').trim(),
    tool_launch_matrix_id: String(scenario.tool_launch_matrix_id || '').trim(),
    prompt_pack_id: String(scenario.prompt_pack_id || '').trim(),
    escalation_policy_id: String(scenario.escalation_policy_id || '').trim(),
    default_channel_id: String(scenario.default_channel_id || '').trim(),
    allowed_channel_ids: scenario.allowed_channel_ids?.length
      ? scenario.allowed_channel_ids
      : [String(scenario.default_channel_id || '').trim()].filter(Boolean),
    audit_required: Boolean(scenario.audit_required),
    log_required: Boolean(scenario.log_required),
  };
  if (scenario.tags?.length) {
    result.tags = scenario.tags;
  }
  return result;
}

async function applyResolutionProfileMutation(operation, profile) {
  const active = await api('/admin/config/active/attribute_resolution_profiles');
  const payload = JSON.parse(JSON.stringify(active.payload));
  const profiles = payload.profiles || [];
  const index = profiles.findIndex((item) => item.profile_id === profile.profile_id);
  if (operation === 'create') {
    if (index >= 0) {
      throw new Error(`Профиль уже существует: ${profile.profile_id}`);
    }
    profiles.push(profile);
  } else if (operation === 'modify') {
    if (index < 0) {
      throw new Error(`Профиль не найден: ${profile.profile_id}`);
    }
    profiles[index] = profile;
  } else if (operation === 'delete') {
    if (index < 0) {
      throw new Error(`Профиль не найден: ${profile.profile_id}`);
    }
    const [slotSchemasActive, scenariosActive] = await Promise.all([
      api('/admin/config/active/slot_schemas'),
      api('/admin/config/active/service_scenarios'),
    ]);
    const usedSchemas = (slotSchemasActive.payload?.slot_schemas || []).filter((schema) =>
      (schema.slots || []).some((slot) => slot.resolution_profile_id === profile.profile_id),
    );
    if (usedSchemas.length) {
      const schemaIds = new Set(usedSchemas.map((schema) => schema.slot_schema_id));
      const scenarioNames = (scenariosActive.payload?.scenarios || [])
        .filter((scenario) => schemaIds.has(scenario.slot_schema_id))
        .map((scenario) => scenario.display_name || scenario.scenario_id);
      const schemaNames = usedSchemas.map((schema) => schema.display_name || schema.slot_schema_id);
      const details = scenarioNames.length
        ? `Сценарии: ${scenarioNames.join(', ')}.`
        : `Схемы слотов: ${schemaNames.join(', ')}.`;
      throw new Error(`Профиль используется. ${details} Сначала уберите профиль из схем слотов.`);
    }
    profiles.splice(index, 1);
  } else {
    throw new Error(`Неизвестная операция с профилем: ${operation}`);
  }
  payload.profiles = profiles;
  const version = await activateConfigPayload('attribute_resolution_profiles', payload, active.active_version_id);
  if (operation === 'delete') {
    state.resolutionProfileId = profiles[0]?.profile_id || '';
  } else {
    state.resolutionProfileId = profile.profile_id;
    state.resolutionOperation = 'modify';
  }
  const actionText = {
    create: 'создан',
    modify: 'изменен',
    delete: 'удален',
  }[operation];
  setNotice(`Профиль ${actionText}. Активирована версия ${version.version_id}.`, 'success');
  await renderResolutionProfiles();
}

async function applySlotAutofillProfileMutation(operation, profile) {
  if (operation === 'delete') {
    const [autofillActive, slotSchemasActive, scenariosActive] = await Promise.all([
      api('/admin/config/active/slot_autofill_profiles'),
      api('/admin/config/active/slot_schemas'),
      api('/admin/config/active/service_scenarios'),
    ]);
    const current = (autofillActive.payload?.profiles || []).find((item) => item.profile_id === profile.profile_id);
    const targetSlots = new Set((current?.output_mapping || []).map((item) => item.target_slot));
    const usedSchemas = (slotSchemasActive.payload?.slot_schemas || []).filter((schema) =>
      (schema.slots || []).some((slot) => slot.fill_method === 'slot_autofill' && targetSlots.has(slot.slot_id)),
    );
    if (usedSchemas.length) {
      const schemaIds = new Set(usedSchemas.map((schema) => schema.slot_schema_id));
      const scenarioNames = (scenariosActive.payload?.scenarios || [])
        .filter((scenario) => schemaIds.has(scenario.slot_schema_id))
        .map((scenario) => scenario.display_name || scenario.scenario_id);
      throw new Error(
        `Профиль автозаполнения используется слотами: ${Array.from(targetSlots).join(', ')}. `
        + `Сценарии: ${scenarioNames.join(', ') || 'не найдены'}. Сначала измените способ заполнения этих слотов.`,
      );
    }
  }
  await applyConfigItemMutation({
    domain: 'slot_autofill_profiles',
    collectionKey: 'profiles',
    idKey: 'profile_id',
    item: profile,
    operation,
    referenceKey: null,
    stateIdKey: 'slotAutofillProfileId',
    stateOperationKey: 'slotAutofillOperation',
    successNoun: 'Профиль автозаполнения',
  });
}

async function applyPromptPackMutation(operation, promptPack) {
  const active = await api('/admin/config/active/prompt_packs');
  const payload = JSON.parse(JSON.stringify(active.payload));
  const packs = payload.packs || [];
  const index = packs.findIndex((item) => item.prompt_pack_id === promptPack.prompt_pack_id);
  if (operation === 'create') {
    if (index >= 0) {
      throw new Error(`Пакет промптов уже существует: ${promptPack.prompt_pack_id}`);
    }
    packs.push(promptPack);
  } else if (operation === 'modify') {
    if (index < 0) {
      throw new Error(`Пакет промптов не найден: ${promptPack.prompt_pack_id}`);
    }
    packs[index] = promptPack;
  } else if (operation === 'delete') {
    if (index < 0) {
      throw new Error(`Пакет промптов не найден: ${promptPack.prompt_pack_id}`);
    }
    const scenariosActive = await api('/admin/config/active/service_scenarios');
    const referencedBy = (scenariosActive.payload?.scenarios || [])
      .filter((scenario) => scenario.prompt_pack_id === promptPack.prompt_pack_id)
      .map((scenario) => scenario.display_name || scenario.scenario_id);
    if (referencedBy.length) {
      throw new Error(`Пакет выбран в сценариях: ${referencedBy.join(', ')}.`);
    }
    packs.splice(index, 1);
  } else {
    throw new Error(`Неизвестная операция с пакетом промптов: ${operation}`);
  }
  payload.packs = packs;
  const version = await activateConfigPayload('prompt_packs', payload, active.active_version_id);
  if (operation === 'delete') {
    state.promptPackId = packs[0]?.prompt_pack_id || '';
  } else {
    state.promptPackId = promptPack.prompt_pack_id;
    state.promptPackOperation = 'modify';
  }
  const actionText = {
    create: 'создан',
    modify: 'изменен',
    delete: 'удален',
  }[operation];
  setNotice(`Пакет промптов ${actionText}. Активирована версия ${version.version_id}.`, 'success');
  await renderScenarioPrompts();
}

async function applyIntegrationEndpointMutation(operation, endpoint) {
  const [active, toolsActive, n8nActive] = await Promise.all([
    api('/admin/config/active/integration_endpoints'),
    api('/admin/config/active/tools'),
    api('/admin/config/active/n8n_workflows'),
  ]);
  const payload = JSON.parse(JSON.stringify(active.payload));
  const endpoints = payload.endpoints || [];
  const endpointId = endpoint.endpoint_id;
  const index = endpoints.findIndex((item) => item.endpoint_id === endpointId);
  const tools = toolsActive.payload?.tools || [];
  const workflows = n8nActive.payload?.workflows || [];
  if (operation === 'create') {
    if (index >= 0) {
      throw new Error(`Подключение уже существует: ${endpointId}`);
    }
    endpoints.push(endpoint);
  } else if (operation === 'modify') {
    if (index < 0) {
      throw new Error(`Подключение не найдено: ${endpointId}`);
    }
    const current = endpoints[index];
    const removedOperations = Object.keys(current.operations || {})
      .filter((operationId) => !endpoint.operations?.[operationId]);
    for (const operationId of removedOperations) {
      const usage = integrationOperationUsage(endpointId, operationId, tools, workflows);
      if (usage.length) {
        throw new Error(
          `Операция ${operationId} используется: ${usage.join('; ')}. Сначала уберите связи.`,
        );
      }
    }
    endpoints[index] = endpoint;
  } else if (operation === 'delete') {
    if (index < 0) {
      throw new Error(`Подключение не найдено: ${endpointId}`);
    }
    const usage = integrationEndpointUsage(endpointId, tools, workflows);
    if (usage.length) {
      throw new Error(`Подключение используется: ${usage.join('; ')}. Сначала уберите связи.`);
    }
    endpoints.splice(index, 1);
  } else {
    throw new Error(`Неизвестная операция с подключением: ${operation}`);
  }
  payload.endpoints = endpoints;
  const version = await activateConfigPayload('integration_endpoints', payload, active.active_version_id);
  if (operation === 'delete') {
    state.integrationEndpointId = endpoints[0]?.endpoint_id || '';
  } else {
    state.integrationEndpointId = endpointId;
    state.integrationEndpointOperation = 'modify';
  }
  const actionText = {
    create: 'создан',
    modify: 'изменен',
    delete: 'удален',
  }[operation];
  setNotice(`Подключение ${actionText}. Активирована версия ${version.version_id}.`, 'success');
  await renderIntegrations();
}

async function applyToolCatalogMutation(operation, tool) {
  const [active, matrixActive, resolutionActive, slotAutofillActive, channelsActive] = await Promise.all([
    api('/admin/config/active/tools'),
    api('/admin/config/active/tool_launch_matrix'),
    api('/admin/config/active/attribute_resolution_profiles'),
    api('/admin/config/active/slot_autofill_profiles'),
    api('/admin/config/active/interaction_channels'),
  ]);
  const payload = JSON.parse(JSON.stringify(active.payload));
  const tools = payload.tools || [];
  const toolName = tool.tool_name;
  const index = tools.findIndex((item) => item.tool_name === toolName);
  const matrices = matrixActive.payload?.matrices || [];
  const resolutionProfiles = resolutionActive.payload?.profiles || [];
  const slotAutofillProfiles = slotAutofillActive.payload?.profiles || [];
  const channels = channelsActive.payload?.channels || [];
  if (operation === 'create') {
    if (index >= 0) {
      throw new Error(`ReAct-вызов ИИ уже существует: ${toolName}`);
    }
    tools.push(tool);
  } else if (operation === 'modify') {
    if (index < 0) {
      throw new Error(`ReAct-вызов ИИ не найден: ${toolName}`);
    }
    const current = tools[index];
    const removedBindings = (current.endpoint_bindings || []).filter(
      (binding) => !(tool.endpoint_bindings || []).some(
        (nextBinding) =>
          nextBinding.endpoint_id === binding.endpoint_id
          && nextBinding.operation_id === binding.operation_id,
      ),
    );
    for (const binding of removedBindings) {
      const usage = toolBindingUsage(
        toolName,
        binding.endpoint_id,
        binding.operation_id,
        matrices,
        resolutionProfiles,
        channels,
        slotAutofillProfiles,
      );
      if (usage.length) {
        throw new Error(
          `Привязка операции ${binding.endpoint_id}/${binding.operation_id} используется: ${usage.join('; ')}. Сначала уберите связи.`,
        );
      }
    }
    tools[index] = tool;
  } else if (operation === 'delete') {
    if (index < 0) {
      throw new Error(`ReAct-вызов ИИ не найден: ${toolName}`);
    }
    const usage = toolUsage(toolName, matrices, resolutionProfiles, channels, slotAutofillProfiles);
    if (usage.length) {
      throw new Error(`ReAct-вызов ИИ используется: ${usage.join('; ')}. Сначала уберите связи.`);
    }
    tools.splice(index, 1);
  } else {
    throw new Error(`Неизвестная операция с ReAct-вызовом ИИ: ${operation}`);
  }
  payload.tools = tools;
  const version = await activateConfigPayload('tools', payload, active.active_version_id);
  if (operation === 'delete') {
    state.toolCatalogName = tools[0]?.tool_name || '';
  } else {
    state.toolCatalogName = toolName;
    state.toolCatalogOperation = 'modify';
  }
  const actionText = {
    create: 'создан',
    modify: 'изменен',
    delete: 'удален',
  }[operation];
  setNotice(`ReAct-вызов ИИ ${actionText}. Активирована версия ${version.version_id}.`, 'success');
  await renderReactCalls();
}

async function applyOperationBindingMutation({
  operation,
  toolName,
  binding,
}) {
  const [active, endpointsActive, matrixActive, resolutionActive, slotAutofillActive, channelsActive] = await Promise.all([
    api('/admin/config/active/tools'),
    api('/admin/config/active/integration_endpoints'),
    api('/admin/config/active/tool_launch_matrix'),
    api('/admin/config/active/attribute_resolution_profiles'),
    api('/admin/config/active/slot_autofill_profiles'),
    api('/admin/config/active/interaction_channels'),
  ]);
  const payload = JSON.parse(JSON.stringify(active.payload));
  const tools = payload.tools || [];
  const tool = tools.find((item) => item.tool_name === toolName);
  if (!tool) {
    throw new Error(`ReAct-вызов ИИ не найден: ${toolName}`);
  }
  const currentBinding = currentToolBinding(tool);
  const matrices = matrixActive.payload?.matrices || [];
  const resolutionProfiles = resolutionActive.payload?.profiles || [];
  const slotAutofillProfiles = slotAutofillActive.payload?.profiles || [];
  const channels = channelsActive.payload?.channels || [];
  const endpoints = endpointsActive.payload?.endpoints || [];
  let nextBinding = null;

  if (operation === 'bind') {
    if (!binding.endpoint_id || !binding.operation_id) {
      throw new Error('Для привязки выберите подключение и операцию.');
    }
    const selectedOperation = operationForBinding(binding, endpoints);
    if (!selectedOperation) {
      throw new Error(`Endpoint-операция не найдена: ${binding.endpoint_id}/${binding.operation_id}`);
    }
    tool.parameters_schema = binding.parameters_schema || operationObjectSchema({}, []);
    tool.result_schema = binding.result_schema || operationObjectSchema({}, []);
    tool.contract_version = selectedOperation.contract_version || tool.contract_version || '1.0';
    tool.contract_status = selectedOperation.contract_status || tool.contract_status || 'draft';
    nextBinding = {
      endpoint_id: binding.endpoint_id,
      operation_id: binding.operation_id,
      parameter_mapping: binding.parameter_mapping || {},
      result_mapping: binding.result_mapping || {},
    };
    tool.endpoint_bindings = [nextBinding];
  } else if (operation === 'unbind') {
    if (!currentBinding) {
      throw new Error('У ReAct-вызова ИИ нет текущей привязки операции.');
    }
    const usage = toolUsage(toolName, matrices, resolutionProfiles, channels, slotAutofillProfiles);
    if (usage.length) {
      throw new Error(`ReAct-вызов ИИ используется: ${usage.join('; ')}. Сначала уберите связи перед отвязкой операции.`);
    }
    tool.endpoint_bindings = [];
  } else {
    throw new Error(`Неизвестная операция с привязкой операции: ${operation}`);
  }

  const version = await activateConfigPayload('tools', payload, active.active_version_id);
  if (operation === 'bind') {
    await updateOperationBindingReferences(toolName, nextBinding);
  }
  state.operationBindingToolName = toolName;
  state.operationBindingLastToolName = toolName;
  if (operation === 'unbind') {
    state.operationBindingEndpointId = '';
    state.operationBindingOperationId = '';
  } else {
    state.operationBindingEndpointId = nextBinding.endpoint_id;
    state.operationBindingOperationId = nextBinding.operation_id;
  }
  const actionText = {
    bind: 'обновлена',
    unbind: 'удалена',
  }[operation];
  setNotice(`Привязка операции ${actionText}. Активирована версия ${version.version_id}.`, 'success');
  await renderOperationBindings();
}

async function applyOperationBindingCreateMutation(tool) {
  const active = await api('/admin/config/active/tools');
  const payload = JSON.parse(JSON.stringify(active.payload));
  const tools = payload.tools || [];
  if (tools.some((item) => item.tool_name === tool.tool_name)) {
    throw new Error(`ReAct-вызов ИИ уже существует: ${tool.tool_name}`);
  }
  if (!tool.endpoint_bindings?.[0]?.endpoint_id || !tool.endpoint_bindings?.[0]?.operation_id) {
    throw new Error('Для создания выберите подключение и операцию.');
  }
  tools.push(tool);
  payload.tools = tools;
  const version = await activateConfigPayload('tools', payload, active.active_version_id);
  const binding = currentToolBinding(tool);
  state.toolCatalogName = tool.tool_name;
  state.operationBindingToolName = tool.tool_name;
  state.operationBindingLastToolName = tool.tool_name;
  state.operationBindingMode = 'bind';
  state.operationBindingEndpointId = binding.endpoint_id;
  state.operationBindingOperationId = binding.operation_id;
  setNotice(`ReAct-вызов ИИ создан и привязан. Активирована версия ${version.version_id}.`, 'success');
  await renderOperationBindings();
}

async function updateOperationBindingReferences(toolName, binding) {
  if (!binding) return;
  const [matrixActive, channelsActive] = await Promise.all([
    api('/admin/config/active/tool_launch_matrix'),
    api('/admin/config/active/interaction_channels'),
  ]);
  const updateAction = (action) => {
    if (action?.tool_name !== toolName) return false;
    action.endpoint_id = binding.endpoint_id;
    action.operation_id = binding.operation_id;
    return true;
  };
  const matrixPayload = JSON.parse(JSON.stringify(matrixActive.payload));
  let matrixChanged = false;
  for (const matrix of matrixPayload.matrices || []) {
    for (const launch of matrix.launches || []) {
      if (launch.tool_name === toolName) {
        launch.endpoint_id = binding.endpoint_id;
        launch.operation_id = binding.operation_id;
        matrixChanged = true;
      }
    }
  }
  if (matrixChanged) {
    await activateConfigPayload('tool_launch_matrix', matrixPayload, matrixActive.active_version_id);
  }

  const channelsPayload = JSON.parse(JSON.stringify(channelsActive.payload));
  let channelsChanged = false;
  for (const channel of channelsPayload.channels || []) {
    for (const [, action] of channelActionEntries(channel)) {
      channelsChanged = updateAction(action) || channelsChanged;
    }
    for (const profile of channel.action_profiles || []) {
      channelsChanged = updateAction(profile.action) || channelsChanged;
    }
  }
  if (channelsChanged) {
    await activateConfigPayload('interaction_channels', channelsPayload, channelsActive.active_version_id);
  }
}

async function applyScenarioMutation(operation, scenario) {
  const active = await api('/admin/config/active/service_scenarios');
  const payload = JSON.parse(JSON.stringify(active.payload));
  const index = payload.scenarios.findIndex((item) => item.scenario_id === scenario.scenario_id);
  if (operation === 'create') {
    if (index >= 0) {
      throw new Error(`Сценарий уже существует: ${scenario.scenario_id}`);
    }
    payload.scenarios.push(scenario);
  } else if (operation === 'modify') {
    if (index < 0) {
      throw new Error(`Сценарий не найден: ${scenario.scenario_id}`);
    }
    payload.scenarios[index] = scenario;
  } else if (operation === 'delete') {
    if (index < 0) {
      throw new Error(`Сценарий не найден: ${scenario.scenario_id}`);
    }
    payload.scenarios.splice(index, 1);
  } else {
    throw new Error(`Неизвестная операция со сценарием: ${operation}`);
  }
  payload.scenarios = payload.scenarios.map((item) => {
    const { confidence_overrides: _confidenceOverrides, ...scenarioWithoutConfidenceOverrides } = item;
    return scenarioWithoutConfidenceOverrides;
  });

  const draft = await api('/admin/config/drafts', {
    method: 'POST',
    body: JSON.stringify({
      domain: 'service_scenarios',
      payload,
      operator_id: state.actorId,
      base_version_id: active.active_version_id,
    }),
  });
  const validated = await api(`/admin/config/drafts/${draft.draft_id}/validate`, {
    method: 'POST',
    body: JSON.stringify({ operator_id: state.actorId }),
  });
  if (validated.validation?.status !== 'valid') {
    throw new Error(`Валидация не пройдена: ${(validated.validation?.errors || []).join('; ')}`);
  }
  const checked = await api(`/admin/config/drafts/${draft.draft_id}/regression`, {
    method: 'POST',
    body: JSON.stringify({ operator_id: state.actorId, limit: 20 }),
  });
  if (checked.regression?.status === 'failed') {
    throw new Error('Регрессионная проверка не пройдена.');
  }
  const version = await api(`/admin/config/drafts/${draft.draft_id}/activate`, {
    method: 'POST',
    body: JSON.stringify({ operator_id: state.actorId }),
  });
  if (operation === 'delete') {
    state.scenarioId = payload.scenarios[0]?.scenario_id || '';
  } else {
    state.scenarioId = scenario.scenario_id;
    state.scenarioOperation = 'modify';
  }
  const actionText = {
    create: 'создан',
    modify: 'изменен',
    delete: 'удален',
  }[operation];
  setNotice(`Сценарий ${actionText}. Активирована версия ${version.version_id}.`, 'success');
  await renderScenarios();
}

async function applyInteractionChannelMutation(operation, channel) {
  const active = await api('/admin/config/active/interaction_channels');
  const payload = JSON.parse(JSON.stringify(active.payload));
  const channels = payload.channels || [];
  const index = channels.findIndex((item) => item.channel_id === channel.channel_id);
  if (operation === 'create') {
    if (index >= 0) {
      throw new Error(`Канал уже существует: ${channel.channel_id}`);
    }
    channels.push(channel);
  } else if (operation === 'modify') {
    if (index < 0) {
      throw new Error(`Канал не найден: ${channel.channel_id}`);
    }
    channels[index] = channel;
  } else if (operation === 'delete') {
    if (index < 0) {
      throw new Error(`Канал не найден: ${channel.channel_id}`);
    }
    const scenariosActive = await api('/admin/config/active/service_scenarios');
    const referencedBy = (scenariosActive.payload?.scenarios || [])
      .filter((scenario) =>
        scenario.default_channel_id === channel.channel_id || (scenario.allowed_channel_ids || []).includes(channel.channel_id),
      )
      .map((scenario) => scenario.display_name || scenario.scenario_id);
    if (referencedBy.length) {
      throw new Error(`Канал используется в сценариях: ${referencedBy.join(', ')}. Сначала измените или удалите эти сценарии.`);
    }
    channels.splice(index, 1);
  } else {
    throw new Error(`Неизвестная операция с каналом: ${operation}`);
  }
  payload.channels = channels;
  const version = await activateConfigPayload('interaction_channels', payload, active.active_version_id);
  if (operation === 'delete') {
    state.interactionChannelId = channels[0]?.channel_id || '';
  } else {
    state.interactionChannelId = channel.channel_id;
    state.interactionChannelOperation = 'modify';
  }
  const actionText = {
    create: 'создан',
    modify: 'изменен',
    delete: 'удален',
  }[operation];
  setNotice(`Канал ${actionText}. Активирована версия ${version.version_id}.`, 'success');
  await renderInteractionChannels();
}

async function replaceConfigItem(domain, collectionKey, idKey, nextItem, successMessage) {
  const active = await api(`/admin/config/active/${domain}`);
  const payload = JSON.parse(JSON.stringify(active.payload));
  const items = payload[collectionKey] || [];
  const index = items.findIndex((item) => item[idKey] === nextItem[idKey]);
  if (index < 0) {
    throw new Error(`Запись не найдена: ${nextItem[idKey]}`);
  }
  items[index] = nextItem;
  payload[collectionKey] = items;
  const version = await activateConfigPayload(domain, payload, active.active_version_id);
  setNotice(`${successMessage}. Активирована версия ${version.version_id}.`, 'success');
  await renderView(state.activeView);
}

async function applyConfigItemMutation({
  domain,
  collectionKey,
  idKey,
  item,
  operation,
  referenceKey,
  stateIdKey,
  stateOperationKey,
  successNoun,
}) {
  const active = await api(`/admin/config/active/${domain}`);
  const payload = JSON.parse(JSON.stringify(active.payload));
  const items = payload[collectionKey] || [];
  const itemId = item[idKey];
  const index = items.findIndex((current) => current[idKey] === itemId);
  if (operation === 'create') {
    if (index >= 0) {
      throw new Error(`Запись уже существует: ${itemId}`);
    }
    items.push(item);
  } else if (operation === 'modify') {
    if (index < 0) {
      throw new Error(`Запись не найдена: ${itemId}`);
    }
    items[index] = item;
  } else if (operation === 'delete') {
    if (index < 0) {
      throw new Error(`Запись не найдена: ${itemId}`);
    }
    if (referenceKey) {
      const scenariosActive = await api('/admin/config/active/service_scenarios');
      const referencedBy = (scenariosActive.payload?.scenarios || [])
        .filter((scenario) => scenario[referenceKey] === itemId)
        .map((scenario) => scenario.display_name || scenario.scenario_id);
      if (referencedBy.length) {
        throw new Error(`Блок используется в сценариях: ${referencedBy.join(', ')}. Сначала измените или удалите эти сценарии.`);
      }
    }
    items.splice(index, 1);
  } else {
    throw new Error(`Неизвестная операция: ${operation}`);
  }
  payload[collectionKey] = items;
  const version = await activateConfigPayload(domain, payload, active.active_version_id);
  if (operation === 'delete') {
    state[stateIdKey] = items[0]?.[idKey] || '';
  } else {
    state[stateIdKey] = itemId;
    state[stateOperationKey] = 'modify';
  }
  const actionText = {
    create: 'создан',
    modify: 'изменен',
    delete: 'удален',
  }[operation];
  setNotice(`${successNoun} ${actionText}. Активирована версия ${version.version_id}.`, 'success');
  await renderView(state.activeView);
}

async function activateConfigPayload(domain, payload, baseVersionId) {
  const draft = await api('/admin/config/drafts', {
    method: 'POST',
    body: JSON.stringify({
      domain,
      payload,
      operator_id: state.actorId,
      base_version_id: baseVersionId,
    }),
  });
  const validated = await api(`/admin/config/drafts/${draft.draft_id}/validate`, {
    method: 'POST',
    body: JSON.stringify({ operator_id: state.actorId }),
  });
  if (validated.validation?.status !== 'valid') {
    throw new Error(`Валидация не пройдена: ${(validated.validation?.errors || []).join('; ')}`);
  }
  const checked = await api(`/admin/config/drafts/${draft.draft_id}/regression`, {
    method: 'POST',
    body: JSON.stringify({ operator_id: state.actorId, limit: 20 }),
  });
  if (checked.regression?.status === 'failed') {
    throw new Error('Регрессионная проверка не пройдена.');
  }
  return api(`/admin/config/drafts/${draft.draft_id}/activate`, {
    method: 'POST',
    body: JSON.stringify({ operator_id: state.actorId }),
  });
}

function parseCsv(value) {
  return String(value || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseLines(value) {
  return String(value || '')
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function selectedValues(select) {
  if (!select) {
    return [];
  }
  return Array.from(select.selectedOptions || [])
    .map((option) => option.value)
    .filter(Boolean);
}

function formList(data, name) {
  return Array.from(new Set(
    data.getAll(name)
      .map((value) => String(value || '').trim())
      .filter(Boolean),
  ));
}

function parseJsonField(value, label) {
  try {
    return JSON.parse(String(value || '').trim());
  } catch (error) {
    throw new Error(`${label}: невалидный JSON (${error.message})`);
  }
}

function parseBoolean(value) {
  return String(value) === 'true';
}

function parseResolverParameterMapping(form) {
  const mapping = {};
  form.querySelectorAll('[data-resolver-param-row]').forEach((row) => {
    const parameterName = row.querySelector('[data-resolver-param-name]')?.value?.trim();
    const sourceRef = row.querySelector('[data-resolver-param-source]')?.value?.trim();
    if (parameterName && sourceRef) {
      mapping[parameterName] = sourceRef;
    }
  });
  return mapping;
}

function parseOperationResultFields(form) {
  const fields = [];
  const seen = new Set();
  form.querySelectorAll('[data-resolution-result-field-row]').forEach((row) => {
    const fieldId = row.querySelector('[data-resolution-result-field-id]')?.value?.trim();
    if (!fieldId || seen.has(fieldId)) return;
    seen.add(fieldId);
    fields.push({
      field_id: fieldId,
      display_name: row.querySelector('[data-resolution-result-field-name]')?.value?.trim() || humanizeTechnicalKey(fieldId),
      field_type: row.querySelector('[data-resolution-result-field-type]')?.value || 'unknown',
      description: row.querySelector('[data-resolution-result-field-description]')?.value?.trim() || '',
    });
  });
  if (!fields.length) {
    fields.push({ field_id: 'value', display_name: 'Значение', field_type: 'unknown', description: '' });
  }
  return fields;
}

function parseEnrichmentParameterMapping(card) {
  const mapping = {};
  card.querySelectorAll('[data-enrichment-param-row]').forEach((row) => {
    const parameterName = row.querySelector('[data-enrichment-param-name]')?.value?.trim();
    const mode = row.querySelector('[data-enrichment-param-source-mode]')?.value?.trim();
    const custom = row.querySelector('[data-enrichment-param-source-custom]')?.value?.trim();
    const sourceRef = mode === 'constant:' || mode === 'secret:'
      ? custom ? `${mode}${custom}` : ''
      : mode === 'custom:'
        ? custom || ''
        : mode || row.querySelector('[data-enrichment-param-source]')?.value?.trim() || '';
    if (parameterName && sourceRef) {
      mapping[parameterName] = sourceRef;
    }
  });
  return mapping;
}

function parseEnrichmentStepCard(card, index) {
  if (!card.querySelector('[data-enrichment-step-editor]')) {
    const jsonText = card.querySelector('[data-enrichment-step-json]')?.value || '{}';
    try {
      return JSON.parse(jsonText);
    } catch (error) {
      throw new Error(`Шаг обогащения ${index + 1}: не удалось прочитать данные (${error.message})`);
    }
  }
  const reactCall = card.querySelector('[data-enrichment-react-call]')?.value?.trim() || '';
  if (!reactCall) {
    throw new Error(`В шаге обогащения ${index + 1} выберите ReAct-вызов.`);
  }
  return {
    step_id: card.querySelector('[data-enrichment-step-id]')?.value?.trim() || normalizeEnrichmentStepId('', index),
    step_name: card.querySelector('[data-enrichment-step-name]')?.value?.trim() || `Шаг ${index + 1}`,
    react_call: reactCall,
    parameter_mapping: parseEnrichmentParameterMapping(card),
    on_error: card.querySelector('[data-enrichment-on-error]')?.value || 'continue_to_llm',
    configuration_instruction: card.querySelector('[data-enrichment-configuration-instruction]')?.value?.trim() || '',
    generated_structure_metadata: parseJsonField(
      card.querySelector('[data-enrichment-generated-metadata]')?.value || '{}',
      `Шаг обогащения ${index + 1}: метаданные сформированной структуры`,
    ),
  };
}

function parseEnrichmentSteps(form) {
  const steps = [];
  const cards = Array.from(form.querySelectorAll('[data-enrichment-step-card]'));
  for (const [index, card] of cards.entries()) {
    const parsedStep = parseEnrichmentStepCard(card, index);
    const step = {
      ...parsedStep,
      step_id: normalizeEnrichmentStepId(parsedStep.step_id, index),
    };
    delete step.result_fields;
    delete step.result_entity_name;
    delete step.result_entity_description;
    if (!step.react_call) {
      throw new Error(`В шаге обогащения ${index + 1} выберите ReAct-вызов.`);
    }
    steps.push(step);
  }
  return steps;
}

function parseResolutionOutputRules(form, targetSlotId) {
  const rows = Array.from(form.querySelectorAll('[data-resolution-output-row]'));
  const rules = [];
  const seen = new Set();
  for (const row of rows) {
    const selectedSlotId = row.querySelector('[data-resolution-output-slot]')?.value?.trim();
    const customSlotId = row.querySelector('[data-resolution-output-slot-custom-value]')?.value?.trim();
    const slotId = selectedSlotId === '__custom__' ? customSlotId : selectedSlotId;
    if (selectedSlotId === '__custom__' && !slotId) {
      throw new Error('Укажите ключ нового выходного слота.');
    }
    if (slotId && !/^[a-z][a-z0-9_.-]*$/.test(slotId)) {
      throw new Error(`Ключ выходного слота "${slotId}" должен начинаться с латинской буквы и содержать только латиницу, цифры, _, - или точку.`);
    }
    if (!slotId || seen.has(slotId)) continue;
    seen.add(slotId);
    rules.push({
      slot_id: slotId,
      order: parseInt(row.querySelector('[data-resolution-output-order]')?.value || String(rules.length + 1), 10),
      required_for_success: parseBoolean(row.querySelector('[data-resolution-output-required]')?.value),
      source_hint: row.querySelector('[data-resolution-output-source]')?.value?.trim() || slotId,
      fallback: row.querySelector('[data-resolution-output-fallback]')?.value || (slotId === targetSlotId ? 'ask_clarification' : 'leave_empty'),
    });
  }
  if (targetSlotId && !rules.some((rule) => rule.slot_id === targetSlotId)) {
    rules.unshift({
      slot_id: targetSlotId,
      order: 1,
      required_for_success: true,
      source_hint: targetSlotId,
      fallback: 'ask_clarification',
    });
  }
  if (!rules.length) {
    throw new Error('Профиль должен содержать хотя бы один выходной слот.');
  }
  return rules
    .sort((left, right) => left.order - right.order)
    .map((rule, index) => ({
      ...rule,
      order: index + 1,
      required_for_success: rule.required_for_success || rule.slot_id === targetSlotId,
    }));
}

function parseHistoryFilter(card) {
  const value = (name) => card.querySelector(`[name="${name}"]`)?.value?.trim() || '';
  const filter = {};
  const ticketStatuses = parseCsv(value('history_ticket_statuses'));
  const allowedFields = parseCsv(value('history_allowed_fields'));
  const excludedCategories = parseCsv(value('history_excluded_categories'));
  const timeWindowDays = value('history_time_window_days');
  const minQuality = value('history_min_quality');
  const similarityThreshold = value('history_similarity_threshold');
  if (ticketStatuses.length) filter.ticket_statuses = ticketStatuses;
  if (timeWindowDays) filter.time_window_days = parseInt(timeWindowDays, 10);
  if (minQuality) filter.min_quality = minQuality;
  if (similarityThreshold) filter.similarity_threshold = Number(similarityThreshold);
  if (allowedFields.length) filter.allowed_fields = allowedFields;
  if (excludedCategories.length) filter.excluded_categories = excludedCategories;
  return filter;
}

function addSlotCard() {
  const container = document.getElementById('slotCards');
  if (!container) return;
  const order = container.querySelectorAll('[data-slot-card]').length + 1;
  const wrapper = document.createElement('div');
  wrapper.innerHTML = renderSlotCard(
    {},
    order,
    true,
    state.lastData.resolutionProfiles || [],
    state.lastData.confidenceDefaults || {},
  ).trim();
  container.appendChild(wrapper.firstElementChild);
  syncSlotCardFillMethod(container.lastElementChild);
}

function addSlotAutofillOutputRow(target) {
  const form = target.closest('form');
  const container = form?.querySelector('[data-slot-autofill-output-list]');
  if (!container) return;
  const schemaId = form.querySelector('[name="slot_schema_id"]')?.value;
  const slotSchema = (state.lastData.slotSchemas || []).find((schema) => schema.slot_schema_id === schemaId) || { slots: [] };
  const wrapper = document.createElement('div');
  wrapper.innerHTML = renderSlotAutofillOutputRow({}, slotSchema).trim();
  container.appendChild(wrapper.firstElementChild);
  syncSlotAutofillOutputRow(container.lastElementChild);
}

function removeSlotAutofillOutputRow(target) {
  const row = target.closest('[data-slot-autofill-output-row]');
  if (!row) return;
  row.remove();
}

function referenceAutocompletePopup() {
  let popup = document.querySelector('[data-reference-autocomplete]');
  if (!popup) {
    popup = document.createElement('div');
    popup.className = 'reference-autocomplete';
    popup.dataset.referenceAutocomplete = 'true';
    popup.hidden = true;
    document.body.appendChild(popup);
  }
  return popup;
}

function activeReferenceFragment(textarea) {
  const cursor = textarea.selectionStart ?? 0;
  if (cursor !== (textarea.selectionEnd ?? cursor)) {
    return null;
  }
  const before = textarea.value.slice(0, cursor);
  const start = before.lastIndexOf('${');
  if (start < 0) {
    return null;
  }
  const query = before.slice(start + 2);
  if (query.includes('}') || /[\s"'«»]/.test(query)) {
    return null;
  }
  return { start, end: cursor, query };
}

function filterReferenceAutocompleteItems(items, query) {
  const normalized = String(query || '').toLowerCase();
  const result = normalized
    ? items.filter((item) => {
      const tokenText = String(item.token || '').replace(/^\$\{|\}$/g, '').toLowerCase();
      const searchText = `${tokenText} ${item.label || ''} ${item.detail || ''} ${item.group || ''}`.toLowerCase();
      return searchText.includes(normalized);
    })
    : items;
  return result.slice(0, 80);
}

function positionReferenceAutocomplete(textarea, popup) {
  const rect = textarea.getBoundingClientRect();
  const width = Math.min(Math.max(280, rect.width), 440, window.innerWidth - 16);
  let left = rect.left;
  let top = rect.bottom + 4;
  if (window.innerWidth > 760) {
    const style = window.getComputedStyle(textarea);
    const fontSize = Number.parseFloat(style.fontSize) || 13;
    const lineHeight = Number.parseFloat(style.lineHeight) || fontSize * 1.45;
    const paddingLeft = Number.parseFloat(style.paddingLeft) || 10;
    const paddingTop = Number.parseFloat(style.paddingTop) || 8;
    const before = textarea.value.slice(0, textarea.selectionStart ?? 0);
    const lines = before.split('\n');
    const currentLine = lines[lines.length - 1] || '';
    const charWidth = Math.max(7, fontSize * 0.55);
    left = rect.left + paddingLeft + Math.min(currentLine.length * charWidth, Math.max(0, rect.width - width - 12));
    top = rect.top + paddingTop + (lines.length * lineHeight) - textarea.scrollTop + 4;
  }
  if (top + 280 > window.innerHeight) {
    top = Math.max(8, rect.top - 284);
  }
  left = Math.min(Math.max(8, left), Math.max(8, window.innerWidth - width - 8));
  popup.style.left = `${left}px`;
  popup.style.top = `${top}px`;
  popup.style.width = `${width}px`;
}

function renderReferenceAutocomplete(textarea) {
  if (!isReferenceAutocompleteTextarea(textarea)) {
    hideReferenceAutocomplete();
    return;
  }
  const fragment = activeReferenceFragment(textarea);
  if (!fragment) {
    hideReferenceAutocomplete();
    return;
  }
  const context = referenceAutocompleteContextForTextarea(textarea);
  const allItems = referenceAutocompleteItems(context || {});
  const items = filterReferenceAutocompleteItems(allItems, fragment.query);
  const popup = referenceAutocompletePopup();
  const selectedIndex = Math.min(
    state.referenceAutocomplete?.selectedIndex || 0,
    Math.max(0, items.length - 1),
  );
  state.referenceAutocomplete = {
    textarea,
    start: fragment.start,
    selectedIndex,
    items,
  };
  if (!items.length) {
    popup.innerHTML = '<div class="reference-autocomplete-empty">Нет совпадений</div>';
  } else {
    let previousGroup = '';
    popup.innerHTML = `
      <div class="reference-autocomplete-list" role="listbox">
        ${items.map((item, index) => {
          const groupHeader = item.group !== previousGroup
            ? `<div class="reference-autocomplete-group">${escapeHtml(item.group || 'Ссылки')}</div>`
            : '';
          previousGroup = item.group;
          return `
            ${groupHeader}
            <button type="button" class="reference-autocomplete-item ${index === selectedIndex ? 'selected' : ''}" data-action="reference-autocomplete-select" data-reference-autocomplete-index="${index}" role="option" aria-selected="${index === selectedIndex ? 'true' : 'false'}">
              <code>${escapeHtml(item.token)}</code>
              <span>${escapeHtml(item.label || item.token)}</span>
            </button>
          `;
        }).join('')}
      </div>
    `;
  }
  popup.hidden = false;
  positionReferenceAutocomplete(textarea, popup);
}

function hideReferenceAutocomplete() {
  const popup = document.querySelector('[data-reference-autocomplete]');
  if (popup) {
    popup.hidden = true;
  }
  state.referenceAutocomplete = {
    textarea: null,
    start: -1,
    selectedIndex: 0,
    items: [],
  };
}

function setReferenceAutocompleteIndex(index) {
  const popup = referenceAutocompletePopup();
  const autocomplete = state.referenceAutocomplete || {};
  const items = autocomplete.items || [];
  if (!items.length || popup.hidden) return;
  const nextIndex = ((index % items.length) + items.length) % items.length;
  state.referenceAutocomplete.selectedIndex = nextIndex;
  popup.querySelectorAll('[data-reference-autocomplete-index]').forEach((button) => {
    const selected = Number(button.dataset.referenceAutocompleteIndex) === nextIndex;
    button.classList.toggle('selected', selected);
    button.setAttribute('aria-selected', selected ? 'true' : 'false');
    if (selected) {
      button.scrollIntoView({ block: 'nearest' });
    }
  });
}

function insertReferenceAutocompleteItem(index = state.referenceAutocomplete?.selectedIndex || 0) {
  const autocomplete = state.referenceAutocomplete || {};
  const textarea = autocomplete.textarea;
  const item = (autocomplete.items || [])[index];
  if (!textarea || !item) return;
  const end = textarea.selectionStart ?? textarea.value.length;
  const prefix = textarea.value.slice(0, autocomplete.start);
  const suffix = textarea.value.slice(end);
  textarea.value = `${prefix}${item.token}${suffix}`;
  const cursor = prefix.length + item.token.length;
  textarea.focus();
  textarea.setSelectionRange(cursor, cursor);
  hideReferenceAutocomplete();
  textarea.dispatchEvent(new Event('input', { bubbles: true }));
}

function handleReferenceAutocompleteKeydown(event) {
  const textarea = event.target;
  if (!isReferenceAutocompleteTextarea(textarea)) return false;
  const popup = document.querySelector('[data-reference-autocomplete]');
  const active = state.referenceAutocomplete?.textarea === textarea && popup && !popup.hidden;
  if (!active) return false;
  const items = state.referenceAutocomplete?.items || [];
  if (!items.length) {
    if (event.key === 'Escape') {
      event.preventDefault();
      hideReferenceAutocomplete();
      return true;
    }
    return false;
  }
  if (event.key === 'ArrowDown') {
    event.preventDefault();
    setReferenceAutocompleteIndex((state.referenceAutocomplete.selectedIndex || 0) + 1);
    return true;
  }
  if (event.key === 'ArrowUp') {
    event.preventDefault();
    setReferenceAutocompleteIndex((state.referenceAutocomplete.selectedIndex || 0) - 1);
    return true;
  }
  if (event.key === 'Enter' || event.key === 'Tab') {
    event.preventDefault();
    insertReferenceAutocompleteItem();
    return true;
  }
  if (event.key === 'Escape') {
    event.preventDefault();
    hideReferenceAutocomplete();
    return true;
  }
  return false;
}

function refreshSlotAutofillEditorAfterReactCallChange(target) {
  const form = target.closest('form');
  if (!form) return;
  const draft = slotAutofillDraftFromForm(form);
  draft.react_call = target.value;
  draft.input_mapping = {};
  draft.output_mapping = [];
  const slotSchemas = state.lastData.slotSchemas || [];
  const scenarios = state.lastData.serviceScenarios || [];
  const tools = (state.lastData.toolCatalog || []).filter((tool) => tool.action_type === 'read_only');
  const wrapper = document.createElement('div');
  wrapper.innerHTML = renderSlotAutofillEditor({
    profile: draft,
    profiles: state.lastData.slotAutofillProfiles || [],
    slotSchemas,
    scenarios,
    tools,
  }).trim();
  const nextForm = wrapper.firstElementChild;
  form.replaceWith(nextForm);
  nextForm.querySelector('details.launch-editor')?.setAttribute('open', 'open');
  syncAllSlotAutofillOutputRows();
  syncAllSlotAutofillSourceRows();
}

function addResolutionResultFieldRow(target) {
  const container = target?.closest('[data-enrichment-step-card]')?.querySelector('[data-resolution-result-field-list]')
    || document.querySelector('[data-resolution-result-field-list]');
  if (!container) return;
  const wrapper = document.createElement('div');
  wrapper.innerHTML = renderOperationResultFieldRow({
    field_id: '',
    display_name: '',
    field_type: 'unknown',
    description: '',
  }).trim();
  container.appendChild(wrapper.firstElementChild);
}

function removeResolutionResultFieldRow(target) {
  const row = target.closest('[data-resolution-result-field-row]');
  if (!row) return;
  const container = row.parentElement;
  if (container && container.querySelectorAll('[data-resolution-result-field-row]').length <= 1) {
    throw new Error('Оставьте хотя бы одно поле результата.');
  }
  row.remove();
}

function currentEnrichmentStepsFromDom(form) {
  return Array.from(form?.querySelectorAll('[data-enrichment-step-card]') || [])
    .map((card, index) => parseEnrichmentStepCard(card, index));
}

function currentResolutionOutputRulesFromDom(form) {
  return Array.from(form?.querySelectorAll('[data-resolution-output-row]') || []).map((row, index) => {
    const selectedSlotId = row.querySelector('[data-resolution-output-slot]')?.value?.trim();
    const customSlotId = row.querySelector('[data-resolution-output-slot-custom-value]')?.value?.trim();
    const slotId = selectedSlotId === '__custom__' ? customSlotId : selectedSlotId;
    return {
      slot_id: slotId || '',
      order: parseInt(row.querySelector('[data-resolution-output-order]')?.value || String(index + 1), 10),
      required_for_success: parseBoolean(row.querySelector('[data-resolution-output-required]')?.value),
      source_hint: row.querySelector('[data-resolution-output-source]')?.value?.trim() || slotId || '',
      fallback: row.querySelector('[data-resolution-output-fallback]')?.value || 'leave_empty',
    };
  }).filter((rule) => rule.slot_id);
}

function currentResolutionSlotContextFromForm(form) {
  const profileId = form?.querySelector('[name="profile_id"]')?.value?.trim() || state.resolutionProfileId;
  const targetSelectValue = form?.querySelector('[data-resolution-target-slot]')?.value?.trim() || '';
  const targetCustomValue = form?.querySelector('[name="target_slot_id_custom"]')?.value?.trim() || '';
  const targetSlotId = targetSelectValue === '__custom__' ? targetCustomValue : targetSelectValue;
  return buildResolutionSlotContext(
    {
      profile_id: profileId,
      slot_schema_id: form?.querySelector('[name="slot_schema_id"]')?.value?.trim() || '',
      target_slot_id: targetSlotId,
    },
    state.lastData.slotSchemas || [],
    state.lastData.serviceScenarios || [],
  );
}

function currentResolutionToolsFromForm(form, steps = []) {
  const slotContext = currentResolutionSlotContextFromForm(form);
  return toolsForScenario(
    state.lastData.toolCatalog || [],
    state.lastData.serviceScenarios || [],
    state.lastData.toolMatrices || [],
    slotContext.selectedScenario,
    (steps || []).map((step) => step.react_call),
  );
}

function addEnrichmentStep(target) {
  const form = target.closest('form');
  const container = form?.querySelector('[data-enrichment-step-list]');
  if (!container) return;
  const steps = currentEnrichmentStepsFromDom(form);
  const tools = currentResolutionToolsFromForm(form, steps);
  const index = steps.length;
  const tool = tools[0] || null;
  steps.push({
    step_id: normalizeEnrichmentStepId('', index),
    step_name: '',
    react_call: tool?.tool_name || '',
    parameter_mapping: {},
    result_fields: resultFieldsFromTool(tool),
    on_error: 'continue_to_llm',
  });
  state.resolutionEnrichmentEditIndex = index;
  rerenderEnrichmentSteps(form, steps);
}

function removeEnrichmentStep(target) {
  const card = target.closest('[data-enrichment-step-card]');
  if (!card) return;
  const form = target.closest('form');
  const index = Number(card.dataset.enrichmentStepIndex || 0);
  const steps = currentEnrichmentStepsFromDom(form);
  steps.splice(index, 1);
  state.resolutionEnrichmentEditIndex = Math.max(0, Math.min(index, steps.length - 1));
  rerenderEnrichmentSteps(form, steps);
}

function editEnrichmentStep(target) {
  const form = target.closest('form');
  state.resolutionEnrichmentEditIndex = Number(target.dataset.stepIndex || 0);
  rerenderEnrichmentSteps(form, currentEnrichmentStepsFromDom(form));
}

function refreshEnrichmentStepCard(target) {
  const form = target.closest('form');
  const card = target.closest('[data-enrichment-step-card]');
  const container = form?.querySelector('[data-enrichment-step-list]');
  if (!form || !card || !container) return;
  const cards = Array.from(container.querySelectorAll('[data-enrichment-step-card]'));
  const index = cards.indexOf(card);
  if (index < 0) return;
  const steps = currentEnrichmentStepsFromDom(form);
  const step = { ...steps[index], step_id: normalizeEnrichmentStepId(steps[index]?.step_id, index), react_call: target.value };
  const tool = findToolInCatalog(state.lastData.toolCatalog || [], step.react_call);
  step.result_fields = resultFieldsFromTool(tool);
  steps[index] = step;
  state.resolutionEnrichmentEditIndex = index;
  rerenderEnrichmentSteps(form, steps);
}

function rerenderEnrichmentSteps(form, steps) {
  const container = form?.querySelector('[data-enrichment-step-list]');
  if (!container) return;
  const slotContext = currentResolutionSlotContextFromForm(form);
  container.innerHTML = renderEnrichmentStepCards(
    steps,
    slotContext,
    currentResolutionOutputRulesFromDom(form),
    currentResolutionToolsFromForm(form, steps),
  );
}

function readEnrichmentStepsForCompile(form, activeIndex) {
  const cards = Array.from(form.querySelectorAll('[data-enrichment-step-card]'));
  const steps = [];
  cards.forEach((item, index) => {
    if (index === activeIndex) {
      const metadataValue = item.querySelector('[data-enrichment-generated-metadata]')?.value || '{}';
      let metadata = {};
      try {
        metadata = parseJsonField(metadataValue, `Шаг обогащения ${index + 1}: метаданные сформированной структуры`);
      } catch {
        metadata = {};
      }
      steps.push({
        step_id: item.querySelector('[data-enrichment-step-id]')?.value?.trim() || normalizeEnrichmentStepId('', index),
        step_name: item.querySelector('[data-enrichment-step-name]')?.value?.trim() || '',
        react_call: item.querySelector('[data-enrichment-react-call]')?.value?.trim() || '',
        configuration_instruction: item.querySelector('[data-enrichment-configuration-instruction]')?.value?.trim() || '',
        generated_structure_metadata: metadata,
      });
      return;
    }
    try {
      steps.push(JSON.parse(item.querySelector('[data-enrichment-step-json]')?.value || '{}'));
    } catch {
      steps.push({});
    }
  });
  return steps;
}

async function compileResolutionStep(target) {
  const card = target.closest('[data-enrichment-step-card]');
  const form = target.closest('form');
  if (!card || !form) return;
  const index = Number(card.dataset.enrichmentStepIndex || 0);
  const steps = readEnrichmentStepsForCompile(form, index);
  const current = steps[index] || {};
  if (!current.configuration_instruction) {
    throw new Error('Заполните инструкцию настройки шага.');
  }
  const status = card.querySelector('[data-resolution-step-compile-status]');
  if (status) {
    status.textContent = 'Формирование структуры шага...';
  }
  const result = await api('/admin/config-assistant/attribute-resolution-step/compile', {
    method: 'POST',
    body: JSON.stringify({
      operator_id: state.actorId,
      instruction: current.configuration_instruction,
      scenario_id: form.querySelector('[data-resolution-slot-scenario]')?.value || state.resolutionSlotScenarioId,
      react_call: current.react_call,
      step_name: current.step_name,
      previous_steps: steps.slice(0, index),
    }),
  });
  steps[index] = {
    ...current,
    ...(result.structure || {}),
  };
  state.resolutionEnrichmentEditIndex = index;
  rerenderEnrichmentSteps(form, steps);
  const issues = [...(result.validation_errors || []), ...(result.warnings || [])];
  setNotice(
    issues.length
      ? `Структура шага сформирована с замечаниями: ${issues.join('; ')}`
      : 'Структура шага сформирована. Проверьте и сохраните профиль.',
    issues.length ? 'error' : 'success',
  );
}

function syncEnrichmentSourceCustom(row) {
  const mode = row?.querySelector('[data-enrichment-param-source-mode]')?.value || '';
  const custom = row?.querySelector('[data-enrichment-param-source-custom]');
  if (!custom) return;
  custom.hidden = !(mode === 'constant:' || mode === 'secret:' || mode === 'custom:');
  if (!custom.hidden) {
    custom.focus();
  }
}

function addResolutionOutputRow() {
  const container = document.querySelector('[data-resolution-output-list]');
  if (!container) return;
  const slotOptionsHtml = container.querySelector('[data-resolution-output-slot]')?.innerHTML
    || document.querySelector('[name="target_slot_id"]')?.innerHTML
    || '<option value="">нет существующих слотов</option><option value="__custom__" selected>Новый слот: указать ключ ниже</option>';
  const order = container.querySelectorAll('[data-resolution-output-row]').length + 1;
  const wrapper = document.createElement('div');
  wrapper.innerHTML = renderResolutionOutputRow(
    { slot_id: '', order, required_for_success: false, source_hint: '', fallback: 'leave_empty' },
    { slots: [] },
    { slotOptionsHtml, customSelected: false },
  ).trim();
  container.appendChild(wrapper.firstElementChild);
  syncResolutionOutputSlotCustom(container.lastElementChild);
}

function removeResolutionOutputRow(target) {
  const row = target.closest('[data-resolution-output-row]');
  if (!row) return;
  const container = row.parentElement;
  if (container && container.querySelectorAll('[data-resolution-output-row]').length <= 1) {
    throw new Error('Профиль должен содержать хотя бы один выходной слот.');
  }
  row.remove();
}

function addRouteRuleCard() {
  const container = document.querySelector('[data-route-rules-list]');
  if (!container) return;
  const wrapper = document.createElement('div');
  wrapper.innerHTML = renderClassificationRuleCard(
    defaultClassificationRule(),
    container.querySelectorAll('[data-route-rule-card]').length,
    true,
  ).trim();
  container.appendChild(wrapper.firstElementChild);
}

function removeRouteRuleCard(target) {
  const card = target.closest('[data-route-rule-card]');
  if (!card) return;
  const container = card.parentElement;
  if (container && container.querySelectorAll('[data-route-rule-card]').length <= 1) {
    throw new Error('Маршрут должен содержать хотя бы одно правило классификации.');
  }
  card.remove();
}

function syncAllSlotCardFillMethods() {
  document.querySelectorAll('[data-slot-card]').forEach(syncSlotCardFillMethod);
}

function syncResolutionTargetSlotCustom(form = document) {
  const select = form.querySelector?.('[data-resolution-target-slot]');
  const customField = form.querySelector?.('[data-resolution-target-slot-custom]');
  if (!select || !customField) return;
  const visible = select.value === '__custom__';
  customField.hidden = !visible;
  customField.querySelectorAll('input, select, textarea').forEach((input) => {
    input.disabled = !visible;
  });
}

function syncResolutionOutputSlotCustom(row) {
  if (!row) return;
  const select = row.querySelector?.('[data-resolution-output-slot]');
  const customField = row.querySelector?.('[data-resolution-output-slot-custom]');
  if (!select || !customField) return;
  const visible = select.value === '__custom__';
  customField.hidden = !visible;
  customField.querySelectorAll('input, select, textarea').forEach((input) => {
    input.disabled = !visible;
  });
}

function syncAllResolutionOutputSlotCustom(root = document) {
  root.querySelectorAll?.('[data-resolution-output-row]').forEach(syncResolutionOutputSlotCustom);
}

function syncSlotAutofillOutputRow(row) {
  if (!row) return;
  const action = row.querySelector('[data-slot-autofill-output-action]')?.value || 'ignore';
  const existing = row.querySelector('[data-slot-autofill-existing-slot]');
  const requiredForProfile = row.querySelector('[data-slot-autofill-required-field]');
  const newFields = [
    row.querySelector('[data-slot-autofill-new-slot-id]'),
    row.querySelector('[data-slot-autofill-new-slot-name]'),
    row.querySelector('[data-slot-autofill-new-slot-priority]'),
    row.querySelector('[data-slot-autofill-new-slot-required]'),
  ].filter(Boolean);
  row.dataset.outputAction = action;
  if (existing) {
    existing.hidden = action !== 'existing';
    existing.querySelectorAll('input, select, textarea').forEach((input) => {
      input.disabled = action !== 'existing';
    });
  }
  if (requiredForProfile) {
    requiredForProfile.hidden = action === 'ignore';
    requiredForProfile.querySelectorAll('input, select, textarea').forEach((input) => {
      input.disabled = action === 'ignore';
    });
  }
  for (const field of newFields) {
    field.hidden = action !== 'new';
    field.querySelectorAll('input, select, textarea').forEach((input) => {
      input.disabled = action !== 'new';
    });
  }
}

function syncAllSlotAutofillOutputRows(root = document) {
  root.querySelectorAll?.('[data-slot-autofill-output-row]').forEach(syncSlotAutofillOutputRow);
}

function syncSlotAutofillSourceRow(row) {
  if (!row) return;
  const mode = row.querySelector('[data-slot-autofill-param-source-mode]')?.value || '';
  const custom = row.querySelector('[data-slot-autofill-param-source-custom]');
  if (!custom) return;
  custom.hidden = !(mode === 'case:' || mode === 'context:' || mode === 'constant:' || mode === 'secret:');
  custom.disabled = custom.hidden;
}

function syncAllSlotAutofillSourceRows(root = document) {
  root.querySelectorAll?.('[data-slot-autofill-input-row]').forEach(syncSlotAutofillSourceRow);
}

function removeSlotCard(target) {
  const card = target.closest('[data-slot-card]');
  if (!card) return;
  card.remove();
  renumberSlotCards();
}

function syncSlotCardFillMethod(card) {
  if (!card) return;
  const fillMethod = card.querySelector('[name="fill_method"]')?.value || '';
  const help = card.querySelector('[data-fill-method-help]');
  if (help) {
    help.textContent = fillMethodHelpText(fillMethod);
  }
  card.querySelectorAll('[data-fill-method-section]').forEach((section) => {
    const visible = section.dataset.fillMethodSection === fillMethod;
    section.hidden = !visible;
    section.querySelectorAll('input, select, textarea').forEach((input) => {
      input.disabled = !visible;
    });
  });
  const orderSection = card.querySelector('[data-fill-method-order]');
  if (orderSection) {
    const visible = ['user_question', 'resolution_profile', 'operator_manual'].includes(fillMethod);
    orderSection.hidden = !visible;
    orderSection.querySelectorAll('input, select, textarea').forEach((input) => {
      input.disabled = !visible;
    });
  }
  card.querySelectorAll('[data-fill-method-advanced]').forEach((section) => {
    const visible = section.dataset.fillMethodAdvanced === fillMethod;
    section.hidden = !visible;
    section.querySelectorAll('input, select, textarea').forEach((input) => {
      input.disabled = !visible;
    });
    if (visible) {
      syncConfidenceOverrideBlock(section.querySelector('[data-confidence-override]'));
    }
  });
}

function renumberSlotCards() {
  document.querySelectorAll('#slotCards [data-slot-card]').forEach((card, index) => {
    const orderInput = card.querySelector('[name="question_order"]');
    if (orderInput && !orderInput.value) {
      orderInput.value = String(index + 1);
    }
  });
}

function addLaunchCard() {
  const container = document.getElementById('launchCards');
  if (!container) return;
  const index = container.querySelectorAll('[data-launch-card]').length;
  const tools = state.lastData.toolCatalog || [];
  const tool = findToolInCatalog(tools, 'check_zabbix_status') || tools[0] || {};
  const binding = currentToolBinding(tool) || {};
  const wrapper = document.createElement('div');
  wrapper.innerHTML = renderLaunchCard(
    {
      launch_id: `launch.custom_${index + 1}`,
      tool_name: tool.tool_name || 'check_zabbix_status',
      required_slots: [],
      parameter_bindings: defaultParameterBindingsForTool(tool),
      execution_level: 'auto',
      target_execution_level: 'auto',
      endpoint_id: binding.endpoint_id || '',
      operation_id: binding.operation_id || '',
      risk_level: 'low',
      stop_on_error: true,
    },
    index,
    tools,
    state.lastData.integrationEndpoints || [],
    state.lastData.toolMatrixSlotContext || { slots: [], scenarioNames: [], scenarioCount: 0, usedByMatrix: false },
  ).trim();
  container.appendChild(wrapper.firstElementChild);
}

function removeLaunchCard(target) {
  const card = target.closest('[data-launch-card]');
  if (!card) return;
  card.remove();
}

function parameterBindingsFromRows(card, { validate = false, launchLabel = 'запуска' } = {}) {
  const result = {};
  const slotContext = state.lastData.toolMatrixSlotContext || { slots: [], scenarioCount: 0 };
  const slotById = Object.fromEntries((slotContext.slots || []).map((slot) => [slot.slot_id, slot]));
  const rows = Array.from(card.querySelectorAll('[data-param-binding-row]'));
  for (const row of rows) {
    const parameterName = row.querySelector('[data-binding-param-name]')?.value?.trim() || '';
    const required = row.dataset.required === 'true';
    const source = row.querySelector('[data-binding-source]')?.value?.trim() || '';
    const value = source === 'slot'
      ? row.querySelector('[data-binding-slot-select]')?.value?.trim() || ''
      : row.querySelector('[data-binding-value-input]')?.value?.trim() || '';
    if (!parameterName) {
      continue;
    }
    if (!source || !value) {
      if (validate && required) {
        throw new Error(`${launchLabel}: обязательный параметр ${parameterName} должен иметь источник значения.`);
      }
      continue;
    }
    if (validate && !['slot', 'case', 'context', 'constant', 'secret'].includes(source)) {
      throw new Error(`${launchLabel}: параметр ${parameterName} имеет неизвестный тип источника ${source}.`);
    }
    if (validate && source === 'slot') {
      const slot = slotById[value];
      if (!slot) {
        throw new Error(`${launchLabel}: параметр ${parameterName} ссылается на отсутствующий слот ${value}.`);
      }
      if (slot.missing_scenario_names?.length) {
        throw new Error(`${launchLabel}: слот ${value} отсутствует в сценариях: ${slot.missing_scenario_names.join(', ')}.`);
      }
    }
    result[parameterName] = `${source}:${value}`;
  }
  if (validate && !Object.keys(result).length) {
    throw new Error(`${launchLabel}: должен быть задан хотя бы один маппинг параметра.`);
  }
  return result;
}

function requiredSlotsFromParameterBindings(parameterBindings) {
  return Array.from(new Set(
    Object.values(parameterBindings || {})
      .map(parseBindingString)
      .filter((binding) => binding.source === 'slot' && binding.value)
      .map((binding) => binding.value),
  ));
}

function syncParameterBindingRow(row) {
  const source = row.querySelector('[data-binding-source]')?.value || '';
  const slotWrap = row.querySelector('[data-binding-slot-wrap]');
  const valueWrap = row.querySelector('[data-binding-value-wrap]');
  if (slotWrap) {
    slotWrap.hidden = source !== 'slot';
  }
  if (valueWrap) {
    valueWrap.hidden = !source || source === 'slot';
  }
  const warning = row.querySelector('[data-binding-slot-warning]');
  const slotId = row.querySelector('[data-binding-slot-select]')?.value || '';
  const text = source === 'slot'
    ? slotWarning(state.lastData.toolMatrixSlotContext || { slots: [] }, slotId)
    : '';
  if (warning) {
    warning.textContent = text;
    warning.hidden = !text;
  }
}

function syncOperationParameterMappingRow(row) {
  const source = row.querySelector('[data-operation-param-source]')?.value || '';
  row.querySelectorAll('[data-operation-param-react-wrap]').forEach((element) => {
    element.hidden = source !== 'react';
  });
  row.querySelectorAll('[data-operation-param-value-wrap]').forEach((element) => {
    element.hidden = !source || source === 'react';
  });
}

function syncOperationResultMappingRow(row) {
  const include = parseBoolean(row.querySelector('[data-operation-result-include]')?.value);
  row.querySelectorAll('[data-operation-result-react-wrap]').forEach((element) => {
    element.hidden = !include;
  });
}

function syncLaunchSelectors(card) {
  if (!card) return;
  const tools = state.lastData.toolCatalog || [];
  const integrationEndpoints = state.lastData.integrationEndpoints || [];
  const slotContext = state.lastData.toolMatrixSlotContext || { slots: [], scenarioNames: [], scenarioCount: 0, usedByMatrix: false };
  const toolSelect = card.querySelector('[data-launch-tool]');
  const endpointInput = card.querySelector('[data-launch-endpoint]');
  const operationInput = card.querySelector('[data-launch-operation]');
  const tool = findToolInCatalog(tools, toolSelect?.value);
  if (!tool) return;

  const currentParameterBindings = parameterBindingsFromRows(card, { validate: false });
  const binding = currentToolBinding(tool);
  if (endpointInput) {
    endpointInput.value = binding?.endpoint_id || '';
  }
  if (operationInput) {
    operationInput.value = binding?.operation_id || '';
  }
  const bindingStatus = card.querySelector('[data-launch-binding-status]');
  if (bindingStatus) {
    bindingStatus.textContent = binding
      ? operationBindingSummary(binding, integrationEndpoints)
      : 'У выбранного ReAct-вызова ИИ нет привязки операции. Настройте ее в меню "Вызовы и интеграции -> Привязка операций".';
    bindingStatus.className = binding ? 'meta' : 'field-help';
  }

  const legend = card.querySelector('legend');
  if (legend) {
    legend.textContent = tool.tool_name;
  }
  const parameters = card.querySelector('[data-launch-parameters]');
  if (parameters) {
    const nextParameters = document.createElement('div');
    nextParameters.innerHTML = parameterBindingsEditor(tool, currentParameterBindings, slotContext).trim();
    parameters.replaceWith(nextParameters.firstElementChild);
  }
}

function addEndpointOperationCard() {
  const container = document.getElementById('endpointOperationCards');
  if (!container) return;
  const existingIds = new Set(
    Array.from(container.querySelectorAll('input[name="operation_id"]')).map((input) => input.value),
  );
  let index = existingIds.size + 1;
  let operationId = `custom_operation_${index}`;
  while (existingIds.has(operationId)) {
    index += 1;
    operationId = `custom_operation_${index}`;
  }
  const wrapper = document.createElement('div');
  wrapper.innerHTML = renderEndpointOperationCard({
    endpointId: document.querySelector('[name="endpoint_id"]')?.value || '',
    adapterType: document.querySelector('[name="adapter_type"]')?.value || 'mock',
    operationId,
    operation: {
      display_name: 'Новая операция',
      description: 'Опишите назначение операции.',
      method: 'POST',
      path: '/custom/operation',
      request_schema: defaultOperationRequestSchema(),
      response_schema: defaultOperationResponseSchema(),
      timeout_seconds: 10,
    },
    tools: state.lastData.toolCatalog || [],
    workflows: [],
    open: true,
  }).trim();
  container.appendChild(wrapper.firstElementChild);
}

function nextOperationFieldName(card, kind) {
  const prefix = kind === 'request' ? 'param' : 'field';
  const existing = new Set(
    Array.from(card.querySelectorAll(`[data-operation-schema-editor="${kind}"] [data-operation-field-name]`))
      .map((input) => input.value.trim())
      .filter(Boolean),
  );
  let index = existing.size + 1;
  let name = `${prefix}_${index}`;
  while (existing.has(name)) {
    index += 1;
    name = `${prefix}_${index}`;
  }
  return name;
}

function addEndpointOperationFieldRow(target, kind) {
  const card = target.closest('[data-endpoint-operation-card]');
  const container = card?.querySelector(`[data-operation-schema-editor="${kind}"] [data-operation-schema-rows]`);
  if (!card || !container) return;
  container.querySelector('[data-operation-schema-empty]')?.remove();
  const wrapper = document.createElement('div');
  wrapper.innerHTML = renderOperationSchemaFieldRow(kind, {
    name: nextOperationFieldName(card, kind),
    title: '',
    type: 'string',
    item_type: 'object',
    required: false,
  }).trim();
  container.appendChild(wrapper.firstElementChild);
  if (kind === 'response') {
    syncEndpointMockRowsFromResponse(card);
  }
  updateEndpointOperationJsonPreview(card);
}

function removeEndpointOperationFieldRow(target) {
  const row = target.closest('[data-operation-field-row]');
  const card = target.closest('[data-endpoint-operation-card]');
  const kind = row?.dataset.schemaKind;
  if (!row || !card || !kind) return;
  row.remove();
  const container = card.querySelector(`[data-operation-schema-editor="${kind}"] [data-operation-schema-rows]`);
  if (container && !container.querySelector('[data-operation-field-row]')) {
    container.innerHTML = operationSchemaEmpty(kind);
  }
  if (kind === 'response') {
    syncEndpointMockRowsFromResponse(card);
  }
  updateEndpointOperationJsonPreview(card);
}

function removeEndpointOperationCard(target) {
  const card = target.closest('[data-endpoint-operation-card]');
  if (!card) return;
  card.remove();
}

function currentMockOutputFromCard(card) {
  try {
    return buildMockOutputFromEditor(card, { validate: false }) || {};
  } catch {
    return {};
  }
}

function replaceOperationSchemaRows(card, kind, schema) {
  const container = card.querySelector(`[data-operation-schema-editor="${kind}"] [data-operation-schema-rows]`);
  if (!container) return;
  const fields = operationSchemaFields(schema);
  container.innerHTML = fields.length
    ? fields.map((field) => renderOperationSchemaFieldRow(kind, field)).join('')
    : operationSchemaEmpty(kind);
}

function syncEndpointMockRowsFromResponse(card) {
  const container = card.querySelector('[data-operation-mock-rows]');
  if (!container) return;
  let responseSchema = defaultOperationResponseSchema();
  try {
    responseSchema = buildOperationSchemaFromEditor(card, 'response');
  } catch {
    return;
  }
  container.innerHTML = renderOperationMockRows(responseSchema, currentMockOutputFromCard(card));
}

function updateEndpointOperationJsonPreview(card) {
  if (!card) return;
  try {
    const requestSchema = buildOperationSchemaFromEditor(card, 'request');
    const responseSchema = buildOperationSchemaFromEditor(card, 'response');
    const requestTextarea = card.querySelector('[data-operation-json-kind="request"]');
    const responseTextarea = card.querySelector('[data-operation-json-kind="response"]');
    const mockTextarea = card.querySelector('[data-operation-json-kind="mock"]');
    if (requestTextarea) requestTextarea.value = jsonPretty(requestSchema);
    if (responseTextarea) responseTextarea.value = jsonPretty(responseSchema);
    if (mockTextarea && card.querySelector('[data-operation-mock-editor]')) {
      mockTextarea.value = jsonPretty(buildMockOutputFromEditor(card, { validate: false }) || {});
    }
  } catch {
    // Пока администратор заполняет строку, JSON-превью может быть временно невалидным.
  }
}

function applyEndpointOperationJsonToForm(target) {
  const card = target.closest('[data-endpoint-operation-card]');
  if (!card) return;
  const requestSchema = parseJsonField(
    card.querySelector('[data-operation-json-kind="request"]')?.value || jsonPretty(defaultOperationRequestSchema()),
    'JSON входа операции',
  );
  const responseSchema = parseJsonField(
    card.querySelector('[data-operation-json-kind="response"]')?.value || jsonPretty(defaultOperationResponseSchema()),
    'JSON ответа операции',
  );
  const mockText = card.querySelector('[data-operation-json-kind="mock"]')?.value?.trim() || '';
  const mockOutput = mockText ? parseJsonField(mockText, 'JSON тестового ответа') : {};
  replaceOperationSchemaRows(card, 'request', requestSchema);
  replaceOperationSchemaRows(card, 'response', responseSchema);
  const mockContainer = card.querySelector('[data-operation-mock-rows]');
  if (mockContainer) {
    mockContainer.innerHTML = renderOperationMockRows(responseSchema, mockOutput);
  }
  updateEndpointOperationJsonPreview(card);
  setNotice('JSON применен в форму операции.', 'success');
}

function mergeImportedEndpointOperations(endpointId, importedOperations) {
  const merged = { ...(importedOperations || {}) };
  const currentEndpoint = (state.lastData.integrationEndpoints || [])
    .find((endpoint) => endpoint.endpoint_id === endpointId);
  const tools = state.lastData.toolCatalog || [];
  const workflows = state.lastData.n8nWorkflows || [];
  Object.entries(currentEndpoint?.operations || {}).forEach(([operationId, operation]) => {
    if (merged[operationId]) {
      return;
    }
    const usage = integrationOperationUsage(endpointId, operationId, tools, workflows);
    if (usage.length) {
      merged[operationId] = operation;
    }
  });
  return merged;
}

async function previewEndpointOpenApiContract(target) {
  const form = target.closest('form');
  if (!form) return;
  const endpoint = endpointBaseFromForm(form);
  if (endpoint.adapter_type !== 'n8n_webhook') {
    throw new Error('OpenAPI импорт доступен только для endpoint n8n_webhook.');
  }
  if (!endpoint.contract_source?.url) {
    throw new Error('Укажите URL OpenAPI-контракта n8n.');
  }
  const status = form.querySelector('[data-openapi-preview-status]');
  if (status) {
    status.textContent = 'Загрузка OpenAPI-контракта...';
  }
  const result = await api('/admin/integration-endpoints/openapi/preview', {
    method: 'POST',
    body: JSON.stringify({
      operator_id: state.actorId,
      endpoint_id: endpoint.endpoint_id,
      contract_source: endpoint.contract_source,
    }),
  });
  const operations = mergeImportedEndpointOperations(endpoint.endpoint_id, result.operations || {});
  const container = form.querySelector('#endpointOperationCards');
  if (!container) {
    throw new Error('Блок операций подключения не найден.');
  }
  const tools = state.lastData.toolCatalog || [];
  const workflows = state.lastData.n8nWorkflows || [];
  container.innerHTML = Object.entries(operations)
    .map(([operationId, operation], index) => renderEndpointOperationCard({
      endpointId: endpoint.endpoint_id,
      adapterType: endpoint.adapter_type,
      operationId,
      operation,
      tools,
      workflows,
      open: index === 0,
    }))
    .join('');
  const warningText = (result.warnings || []).length
    ? ` Предупреждения: ${(result.warnings || []).slice(0, 3).join('; ')}${result.warnings.length > 3 ? '...' : ''}`
    : '';
  if (status) {
    status.textContent = `Загружено операций: ${Object.keys(result.operations || {}).length}.${warningText}`;
  }
  setNotice(`OpenAPI-контракт загружен: операций ${Object.keys(result.operations || {}).length}. Сохраните подключение, чтобы применить изменения.`, 'success');
}

function syncOperationBindingOperationOptions(form) {
  if (!form) return;
  const endpoints = state.lastData.integrationEndpoints || [];
  const endpointSelect = form.querySelector('[data-operation-binding-endpoint]');
  const operationSelect = form.querySelector('[data-operation-binding-operation]');
  if (!endpointSelect || !operationSelect) return;
  const endpoint = endpoints.find((item) => item.endpoint_id === endpointSelect.value) || null;
  const operationIds = Object.keys(endpoint?.operations || {});
  const selectedOperationId = operationIds.includes(operationSelect.value)
    ? operationSelect.value
    : operationIds[0] || '';
  state.operationBindingEndpointId = endpointSelect.value;
  operationSelect.innerHTML = operationOptionsForEndpoint(endpoint, selectedOperationId);
  operationSelect.value = selectedOperationId;
  state.operationBindingOperationId = selectedOperationId;
}

function addChannelProfileCard() {
  const container = document.getElementById('channelProfileCards');
  if (!container) return;
  const mode = document.querySelector('select[name="mode"]')?.value || 'debug';
  const defaultActionType = channelActionTypes(mode)[0] || 'debug_stop';
  const existingIds = new Set(
    Array.from(container.querySelectorAll('input[name="profile_id"]')).map((input) => input.value),
  );
  let index = existingIds.size + 1;
  let profileId = `custom_profile_${index}`;
  while (existingIds.has(profileId)) {
    index += 1;
    profileId = `custom_profile_${index}`;
  }
  const wrapper = document.createElement('div');
  wrapper.innerHTML = renderChannelProfileCard({
    profile_id: profileId,
    display_name: '',
    event_type: 'standard_handoff',
    action: {
      action_type: defaultActionType,
      message_template: 'Остановить сценарий и показать сообщение оператору.',
    },
  }, mode).trim();
  container.appendChild(wrapper.firstElementChild);
}

function removeChannelProfileCard(target) {
  const card = target.closest('[data-channel-profile-card]');
  if (!card) return;
  card.remove();
}

function nextModelProviderId() {
  const existing = new Set(
    Array.from(document.querySelectorAll('input[name="model_provider_id"]'))
      .map((input) => input.value),
  );
  let index = existing.size + 1;
  let providerId = `litellm_custom_${index}`;
  while (existing.has(providerId)) {
    index += 1;
    providerId = `litellm_custom_${index}`;
  }
  return providerId;
}

function addModelProviderCard() {
  const container = document.getElementById('modelProviderCards');
  if (!container) return;
  const providerId = nextModelProviderId();
  const config = state.lastData.modelConfig || {};
  const provider = normalizeModelProvider(providerId, {
    provider_type: 'litellm',
    display_name: `LiteLLM подключение ${container.querySelectorAll('[data-model-provider]').length + 1}`,
  }, config);
  const wrapper = document.createElement('div');
  wrapper.innerHTML = renderModelProviderCard(providerId, provider, config.active_provider || '', config.runtime || {}, false).trim();
  container.appendChild(wrapper.firstElementChild);
}

function removeModelProviderCard(target) {
  const card = target.closest('[data-model-provider]');
  if (!card) return;
  const providerId = card.dataset.modelProvider;
  if (providerId === 'vllm_cpu' || providerId === 'openai') {
    throw new Error('Базовые профили vLLM CPU и OpenAI API нельзя удалить; их можно отключить.');
  }
  card.remove();
}

function initEvents() {
  elements.navItems.forEach((item) => {
    item.addEventListener('click', () => loadView(item.dataset.view));
  });
  elements.refreshButton.addEventListener('click', () => loadView(state.activeView));
  elements.actorId.addEventListener('change', () => loadView(state.activeView));

  document.addEventListener('click', async (event) => {
    const target = event.target.closest('[data-action]');
    if (!target) {
      return;
    }
    const action = target.dataset.action;
    if (
      action === 'slot-remove'
      || action === 'launch-remove'
      || action === 'route-rule-remove'
      || action === 'model-provider-remove'
      || action === 'channel-profile-remove'
      || action === 'endpoint-operation-remove'
      || action === 'endpoint-request-field-remove'
      || action === 'endpoint-response-field-remove'
      || action === 'enrichment-step-remove'
      || action === 'resolution-result-field-remove'
      || action === 'resolution-output-remove'
      || action === 'slot-autofill-output-remove'
    ) {
      event.preventDefault();
      event.stopPropagation();
    }
    target.disabled = true;
    try {
      if (action === 'knowledge-rebuild') {
        await rebuildKnowledge();
      } else if (action === 'processing-case-open') {
        state.processingCaseId = target.dataset.caseId || '';
        await renderProcessing({ scrollToDetail: true });
        setNotice(`Открыт кейс ${state.processingCaseId}.`, 'success');
      } else if (action === 'processing-run-cancel') {
        await runProcessingCommand(
          `/admin/processing/runs/${encodeURIComponent(target.dataset.runId)}/cancel`,
          'Запуск обработки отменен.',
        );
      } else if (action === 'processing-task-retry') {
        await runProcessingCommand(
          `/admin/processing/tasks/${encodeURIComponent(target.dataset.taskId)}/retry`,
          'Задача поставлена на повторную обработку.',
        );
      } else if (action === 'processing-task-release') {
        await runProcessingCommand(
          `/admin/processing/tasks/${encodeURIComponent(target.dataset.taskId)}/release-lease`,
          'Lease задачи освобожден.',
        );
      } else if (action === 'processing-wait-timeout') {
        await runProcessingCommand(
          `/admin/processing/waits/${encodeURIComponent(target.dataset.waitId)}/force-timeout`,
          'Ожидание завершено по timeout.',
        );
      } else if (action === 'processing-case-escalate') {
        await runProcessingCommand(
          `/admin/processing/cases/${encodeURIComponent(target.dataset.caseId)}/escalate`,
          'Кейс передан в эскалацию.',
        );
      } else if (action === 'promote-feedback') {
        await promoteFeedback();
      } else if (action === 'run-evaluation') {
        await runEvaluation();
      } else if (action === 'orchestration-graph-load') {
        await renderCurrentGraphHost();
      } else if (action === 'graph-node-select') {
        state.orchestrationGraphSelectedNodeId = target.dataset.nodeId;
        await renderCurrentGraphHost();
      } else if (action === 'graph-zoom-in') {
        setGraphZoom(state.orchestrationGraphZoom * 1.15);
      } else if (action === 'graph-zoom-out') {
        setGraphZoom(state.orchestrationGraphZoom / 1.15);
      } else if (action === 'graph-zoom-reset') {
        state.orchestrationGraphZoom = 1;
        state.orchestrationGraphPanX = 20;
        state.orchestrationGraphPanY = 20;
        updateGraphViewport();
      } else if (action === 'graph-zoom-fit') {
        fitGraphToCanvas();
      } else if (action === 'graph-config-link') {
        applyGraphConfigRefSelection(target.dataset.graphDomain, target.dataset.graphRefId);
        await loadView(target.dataset.graphView || 'scenarios');
      } else if (action === 'scenario-operation') {
        state.scenarioOperation = target.dataset.operation;
        await renderScenarios();
      } else if (action === 'slot-schema-operation') {
        state.slotSchemaOperation = target.dataset.operation;
        await renderScenarioSlots();
      } else if (action === 'slot-autofill-operation') {
        state.slotAutofillOperation = target.dataset.operation;
        await renderSlotAutofillProfiles();
      } else if (action === 'route-operation') {
        state.routeOperation = target.dataset.operation;
        await renderScenarioClassification();
      } else if (action === 'policy-operation') {
        state.policyOperation = target.dataset.operation;
        await renderScenarioReact();
      } else if (action === 'tool-matrix-operation') {
        state.toolMatrixOperation = target.dataset.operation;
        await renderScenarioTools();
      } else if (action === 'escalation-operation') {
        state.escalationOperation = target.dataset.operation;
        await renderScenarioEscalation();
      } else if (action === 'prompt-pack-operation') {
        state.promptPackOperation = target.dataset.operation;
        await renderScenarioPrompts();
      } else if (action === 'interaction-channel-operation') {
        state.interactionChannelOperation = target.dataset.operation;
        await renderInteractionChannels();
      } else if (action === 'resolution-operation') {
        state.resolutionOperation = target.dataset.operation;
        await renderResolutionProfiles();
      } else if (action === 'endpoint-connection-operation') {
        state.integrationEndpointOperation = target.dataset.operation;
        await renderIntegrations();
      } else if (action === 'tool-catalog-operation') {
        state.toolCatalogOperation = target.dataset.operation;
        await renderReactCalls();
      } else if (action === 'operation-binding-mode') {
        state.operationBindingMode = target.dataset.mode || 'bind';
        await renderOperationBindings();
      } else if (action === 'model-provider-switch') {
        await switchModelProvider(target.dataset.provider);
      } else if (action === 'model-provider-add') {
        addModelProviderCard();
      } else if (action === 'model-provider-remove') {
        removeModelProviderCard(target);
      } else if (action === 'reference-autocomplete-select') {
        insertReferenceAutocompleteItem(Number(target.dataset.referenceAutocompleteIndex || 0));
      } else if (action === 'slot-add') {
        addSlotCard();
      } else if (action === 'slot-remove') {
        removeSlotCard(target);
      } else if (action === 'slot-autofill-output-add') {
        addSlotAutofillOutputRow(target);
      } else if (action === 'slot-autofill-output-remove') {
        removeSlotAutofillOutputRow(target);
      } else if (action === 'slot-autofill-compile') {
        await compileSlotAutofillProfile(target);
      } else if (action === 'resolution-result-field-add') {
        addResolutionResultFieldRow(target);
      } else if (action === 'resolution-result-field-remove') {
        removeResolutionResultFieldRow(target);
      } else if (action === 'enrichment-step-add') {
        addEnrichmentStep(target);
      } else if (action === 'enrichment-step-edit') {
        editEnrichmentStep(target);
      } else if (action === 'enrichment-step-remove') {
        removeEnrichmentStep(target);
      } else if (action === 'resolution-step-compile') {
        await compileResolutionStep(target);
      } else if (action === 'resolution-output-add') {
        addResolutionOutputRow();
      } else if (action === 'resolution-output-remove') {
        removeResolutionOutputRow(target);
      } else if (action === 'route-rule-add') {
        addRouteRuleCard();
      } else if (action === 'route-rule-remove') {
        removeRouteRuleCard(target);
      } else if (action === 'launch-add') {
        addLaunchCard();
      } else if (action === 'launch-remove') {
        removeLaunchCard(target);
      } else if (action === 'channel-profile-add') {
        addChannelProfileCard();
      } else if (action === 'channel-profile-remove') {
        removeChannelProfileCard(target);
      } else if (action === 'endpoint-operation-add') {
        addEndpointOperationCard();
      } else if (action === 'endpoint-operation-remove') {
        removeEndpointOperationCard(target);
      } else if (action === 'endpoint-request-field-add') {
        addEndpointOperationFieldRow(target, 'request');
      } else if (action === 'endpoint-response-field-add') {
        addEndpointOperationFieldRow(target, 'response');
      } else if (action === 'endpoint-request-field-remove' || action === 'endpoint-response-field-remove') {
        removeEndpointOperationFieldRow(target);
      } else if (action === 'endpoint-operation-json-apply') {
        applyEndpointOperationJsonToForm(target);
      } else if (action === 'endpoint-openapi-preview') {
        await previewEndpointOpenApiContract(target);
      }
    } catch (error) {
      setNotice(error.message || String(error), 'error');
    } finally {
      target.disabled = false;
    }
  });

  document.addEventListener('mousedown', (event) => {
    const popup = document.querySelector('[data-reference-autocomplete]');
    if (popup?.contains(event.target) || isReferenceAutocompleteTextarea(event.target)) {
      return;
    }
    hideReferenceAutocomplete();
  });

  document.addEventListener('click', (event) => {
    if (isReferenceAutocompleteTextarea(event.target)) {
      renderReferenceAutocomplete(event.target);
    }
  });

  document.addEventListener('keydown', (event) => {
    handleReferenceAutocompleteKeydown(event);
  });

  document.addEventListener('keyup', (event) => {
    if (
      isReferenceAutocompleteTextarea(event.target)
      && ['ArrowLeft', 'ArrowRight', 'Home', 'End', 'PageUp', 'PageDown'].includes(event.key)
    ) {
      renderReferenceAutocomplete(event.target);
    }
  });

  document.addEventListener('change', async (event) => {
    const target = event.target;
    if (target?.matches?.('[data-confidence-override-enabled]')) {
      syncConfidenceOverrideBlock(target.closest('[data-confidence-override]'));
      return;
    }
    if (target?.matches?.('[data-operation-contract-control]')) {
      const card = target.closest('[data-endpoint-operation-card]');
      if (target.closest('[data-operation-schema-editor="response"]')) {
        syncEndpointMockRowsFromResponse(card);
      }
      updateEndpointOperationJsonPreview(card);
      return;
    }
    if (target?.matches?.('[data-operation-mock-control]')) {
      updateEndpointOperationJsonPreview(target.closest('[data-endpoint-operation-card]'));
      return;
    }
    if (target?.matches?.('[data-binding-source], [data-binding-slot-select]')) {
      syncParameterBindingRow(target.closest('[data-param-binding-row]'));
      return;
    }
    if (target?.matches?.('[data-operation-param-source]')) {
      syncOperationParameterMappingRow(target.closest('[data-operation-param-row]'));
      return;
    }
    if (target?.matches?.('[data-operation-result-include]')) {
      syncOperationResultMappingRow(target.closest('[data-operation-result-row]'));
      return;
    }
    if (target?.matches?.('[data-operation-binding-endpoint]')) {
      syncOperationBindingOperationOptions(target.closest('form'));
      await renderOperationBindings();
      return;
    }
    if (target?.matches?.('[data-operation-binding-operation]')) {
      state.operationBindingOperationId = target.value;
      await renderOperationBindings();
      return;
    }
    if (target?.matches?.('[data-graph-view-select]')) {
      state.orchestrationGraphView = target.value;
      state.orchestrationGraphSelectedNodeId = 'slot_filling';
      await renderCurrentGraphHost();
      return;
    }
    if (target?.matches?.('[data-graph-scenario-select]')) {
      state.orchestrationGraphScenarioId = target.value;
      state.scenarioId = target.value;
      state.orchestrationGraphSelectedNodeId = 'slot_filling';
      await renderCurrentGraphHost();
      return;
    }
    if (target?.matches?.('[data-slot-fill-method]')) {
      syncSlotCardFillMethod(target.closest('[data-slot-card]'));
      return;
    }
    if (target?.matches?.('[data-slot-autofill-react-call]')) {
      refreshSlotAutofillEditorAfterReactCallChange(target);
      return;
    }
    if (target?.matches?.('[data-slot-autofill-output-action]')) {
      syncSlotAutofillOutputRow(target.closest('[data-slot-autofill-output-row]'));
      return;
    }
    if (target?.matches?.('[data-slot-autofill-param-source-mode]')) {
      syncSlotAutofillSourceRow(target.closest('[data-slot-autofill-input-row]'));
      return;
    }
    if (target?.matches?.('[data-resolution-slot-scenario]')) {
      state.resolutionSlotScenarioId = target.value;
      await renderResolutionProfiles();
      return;
    }
    if (target?.matches?.('[data-resolution-target-slot]')) {
      syncResolutionTargetSlotCustom(target.closest('form'));
      return;
    }
    if (target?.matches?.('[data-resolution-output-slot]')) {
      syncResolutionOutputSlotCustom(target.closest('[data-resolution-output-row]'));
      return;
    }
    if (target?.matches?.('[data-enrichment-react-call]')) {
      refreshEnrichmentStepCard(target);
      return;
    }
    if (target?.matches?.('[data-enrichment-param-source-mode]')) {
      syncEnrichmentSourceCustom(target.closest('[data-enrichment-param-row]'));
      return;
    }
    if (!target?.matches?.('[data-launch-tool]')) {
      return;
    }
    syncLaunchSelectors(target.closest('[data-launch-card]'));
  });

  document.addEventListener('input', (event) => {
    const target = event.target;
    if (isReferenceAutocompleteTextarea(target)) {
      renderReferenceAutocomplete(target);
      return;
    }
    if (target?.matches?.('[data-operation-contract-control], [data-operation-mock-control]')) {
      updateEndpointOperationJsonPreview(target.closest('[data-endpoint-operation-card]'));
    }
  });

  document.addEventListener('submit', async (event) => {
    const form = event.target;
    if (!form.dataset.form) {
      return;
    }
    event.preventDefault();
    try {
      if (form.dataset.form === 'retrieval') {
        await testRetrieval(form);
      } else if (form.dataset.form === 'scenario-editor') {
        await saveScenarioForm(form);
      } else if (form.dataset.form === 'scenario-delete') {
        await deleteScenarioForm();
      } else if (form.dataset.form === 'slot-schema-editor') {
        await saveSlotSchemaForm(form);
      } else if (form.dataset.form === 'slot-schema-delete') {
        await deleteSlotSchemaForm();
      } else if (form.dataset.form === 'slot-autofill-editor') {
        await saveSlotAutofillProfileForm(form);
      } else if (form.dataset.form === 'slot-autofill-delete') {
        await deleteSlotAutofillProfileForm();
      } else if (form.dataset.form === 'route-editor') {
        await saveRouteForm(form);
      } else if (form.dataset.form === 'route-delete') {
        await deleteRouteForm();
      } else if (form.dataset.form === 'policy-editor') {
        await savePolicyForm(form);
      } else if (form.dataset.form === 'confidence-defaults-editor') {
        await saveConfidenceDefaultsForm(form);
      } else if (form.dataset.form === 'policy-delete') {
        await deletePolicyForm();
      } else if (form.dataset.form === 'tool-launch-editor') {
        await saveToolLaunchForm(form);
      } else if (form.dataset.form === 'tool-matrix-delete') {
        await deleteToolMatrixForm();
      } else if (form.dataset.form === 'escalation-editor') {
        await saveEscalationForm(form);
      } else if (form.dataset.form === 'escalation-delete') {
        await deleteEscalationForm();
      } else if (form.dataset.form === 'prompt-pack-editor') {
        await savePromptPackForm(form);
      } else if (form.dataset.form === 'prompt-pack-delete') {
        await deletePromptPackForm();
      } else if (form.dataset.form === 'interaction-channel-editor') {
        await saveInteractionChannelForm(form);
      } else if (form.dataset.form === 'interaction-channel-delete') {
        await deleteInteractionChannelForm();
      } else if (form.dataset.form === 'model-routing-editor') {
        await saveModelRoutingForm(form);
      } else if (form.dataset.form === 'resolution-profile-editor') {
        await saveResolutionProfileForm(form);
      } else if (form.dataset.form === 'resolution-profile-delete') {
        await deleteResolutionProfileForm();
      } else if (form.dataset.form === 'integration-endpoint-editor') {
        await saveIntegrationEndpointForm(form);
      } else if (form.dataset.form === 'integration-endpoint-delete') {
        await deleteIntegrationEndpointForm();
      } else if (form.dataset.form === 'tool-catalog-editor') {
        await saveToolCatalogForm(form);
      } else if (form.dataset.form === 'tool-catalog-delete') {
        await deleteToolCatalogForm();
      } else if (form.dataset.form === 'operation-binding-editor') {
        await saveOperationBindingForm(form, event.submitter);
      } else if (form.dataset.form === 'operation-binding-create-editor') {
        await saveOperationBindingCreateForm(form);
      } else if (form.dataset.form === 'operation-binding-delete') {
        await deleteOperationBindingForm();
      } else if (form.dataset.form === 'audit-filter') {
        const data = new FormData(form);
        const filters = Object.fromEntries(
          Array.from(data.entries()).filter(([, value]) => String(value).trim() !== ''),
        );
        await renderAudit(filters);
      }
    } catch (error) {
      setNotice(error.message || String(error), 'error');
    }
  });
}

initEvents();
loadView('dashboard');
