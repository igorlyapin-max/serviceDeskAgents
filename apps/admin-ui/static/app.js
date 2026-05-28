const state = {
  activeView: 'dashboard',
  actorId: 'admin-1',
  scenarioId: 'password_reset',
  scenarioOperation: 'modify',
  slotSchemaId: 'slot.password_reset',
  slotSchemaOperation: 'modify',
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
  integrationEndpointId: 'mock',
  integrationEndpointOperation: 'modify',
  toolCatalogName: 'start_systemcenter_runbook',
  toolCatalogOperation: 'modify',
  operationBindingToolName: 'start_systemcenter_runbook',
  operationBindingEndpointId: 'mock',
  operationBindingOperationId: 'start_systemcenter_runbook',
  modelRoutingBaseVersionId: '',
  lastData: {
    toolCatalog: [],
    integrationEndpoints: [],
  },
};

const viewTitles = {
  dashboard: 'Панель обзора',
  scenarios: 'Сценарии',
  scenarioSlots: '0. Слоты',
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
  ask_user: 'спросить пользователя',
  operator_approval: 'согласование оператора',
  operator_handoff: 'передать оператору',
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
  operator_manual: 'ручное заполнение оператором',
  resolution_pending: 'ожидает разрешения',
  resolution_profile: 'профиль разрешения',
  user_question: 'вопрос пользователю',
  llm_extract: 'извлечение из текста моделью',
  rag_search: 'поиск в базе знаний',
  case_read: 'чтение из данных обращения',
  tool_call: 'ReAct-вызов ИИ',
  ticket_history_search: 'поиск по истории заявок',
  condition: 'условие',
  clarification: 'уточняющий вопрос',
  fill_slot: 'заполнение слота',
  escalate: 'эскалация',
  sequential: 'последовательно',
  branching: 'с ветвлениями',
  profile: 'на профиль',
  step: 'на шаг',
  clarification_required: 'нужно уточнение',
  all_required_slots_filled: 'все обязательные слоты заполнены',
  tool_success: 'успешный результат ReAct-вызова',
  handoff_required: 'требуется передача',
  iteration_limit: 'лимит итераций',
  consecutive_tool_errors: 'ошибки ReAct-вызовов подряд',
  slot: 'слот',
  react: 'параметр вызова',
  constant: 'константа',
  secret: 'секрет',
  context: 'контекст',
  read_diagnostics: 'чтение и диагностика',
  knowledge_search: 'поиск в знаниях',
  external_status_check: 'проверка внешних систем',
  action_preparation: 'подготовка действия',
  state_changing_actions: 'действия с изменением состояния',
  communication_handoff: 'коммуникация и передача',
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
    help: 'Передача включается, когда уверенность решения ниже 0.50.',
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
    help: 'Сколько времени осталось до нарушения SLA на момент передачи.',
  },
  {
    value: 'user_notification',
    label: 'Текст уведомления пользователя',
    help: 'Сообщение, которое увидит пользователь или оператор канала.',
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
    label: 'Коммуникация и передача',
    help: 'Уточняющие вопросы, уведомления и передача в канал взаимодействия.',
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
    label: 'Нужно уточнение',
    help: 'Оркестратор останавливает цикл и задает следующий вопрос через выбранный канал.',
  },
  {
    value: 'handoff_required',
    label: 'Требуется передача',
    help: 'Дальнейшее действие определяется блоком 5 и каналом взаимодействия.',
  },
  {
    value: 'iteration_limit',
    label: 'Достигнут лимит итераций',
    help: 'Срабатывает при достижении поля "Максимум итераций" в этом блоке.',
  },
  {
    value: 'consecutive_tool_errors',
    label: 'Ошибки ReAct-вызовов подряд',
    help: 'Срабатывает при достижении поля "Ошибок ReAct-вызовов подряд до передачи".',
  },
];

const elements = {
  apiStatus: document.getElementById('apiStatus'),
  actorId: document.getElementById('actorId'),
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

function badge(value) {
  const label = String(value ?? 'н/д');
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

function table(headersList, rows) {
  if (!rows.length) {
    return '<div class="empty">Нет данных</div>';
  }
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>${headersList.map((header) => `<th>${escapeHtml(header)}</th>`).join('')}</tr>
        </thead>
        <tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody>
      </table>
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
  elements.apiStatus.textContent = isBusy ? 'Загрузка' : `Инициатор: ${state.actorId}`;
}

function section(title, body, actions = '') {
  return `
    <section class="section">
      <div class="section-head">
        <h2 class="section-title">${escapeHtml(title)}</h2>
        <div>${actions}</div>
      </div>
      ${body}
    </section>
  `;
}

async function loadView(view = state.activeView) {
  state.activeView = view;
  state.actorId = elements.actorId.value.trim() || 'admin-1';
  elements.viewTitle.textContent = viewTitles[view] || view;
  elements.navItems.forEach((item) => item.classList.toggle('active', item.dataset.view === view));
  setNotice('');
  setBusy(true);
  try {
    await renderView(view);
    elements.apiStatus.textContent = `Готово / инициатор: ${state.actorId}`;
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
  } else if (view === 'scenarios') {
    await renderScenarios();
  } else if (view === 'scenarioSlots') {
    await renderScenarioSlots();
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
    <button type="button" data-action="scenario-load">Загрузить</button>
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
      <button type="button" data-action="${escapeHtml(actionPrefix)}-load">Загрузить</button>
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
  const [active, scenariosConfig, resolutionProfilesConfig] = await Promise.all([
    api('/admin/config/active/slot_schemas'),
    api('/admin/config/active/service_scenarios'),
    api('/admin/config/active/attribute_resolution_profiles'),
  ]);
  const slotSchemas = active.payload?.slot_schemas || [];
  const scenarios = scenariosConfig.payload?.scenarios || [];
  const resolutionProfiles = resolutionProfilesConfig.payload?.profiles || [];
  state.lastData.resolutionProfiles = resolutionProfiles;
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
      })}`,
    ),
  ].join('');
  attachCatalogSelect('slotSchemaSelect', 'slotSchemaId', renderScenarioSlots);
  syncAllSlotCardFillMethods();
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
  const confidenceDefaults = active.payload?.confidence_defaults || {};
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
      ${renderSystemConfidenceDefaults(confidenceDefaults)}
      ${renderPolicyEditor({ policy: selected, policies, scenarios })}`,
    ),
  ].join('');
  attachCatalogSelect('policySelect', 'policyId', renderScenarioReact);
}

function renderSystemConfidenceDefaults(confidenceDefaults) {
  return `
    <form class="scenario-editor panel" data-form="confidence-defaults-editor">
      <div>
        <div class="metric-label">Системные пороги уверенности</div>
        <div class="meta">Базовые значения для slot filling, извлечения моделью и принятия результатов. Сценарии, слоты и профили могут переопределять их только в исключительных случаях.</div>
      </div>
      ${renderConfidenceThresholdInputs('system_confidence', confidenceDefaults, { required: true })}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">Сохранить системные пороги</button>
      </div>
    </form>
  `;
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
  const [active, scenariosConfig] = await Promise.all([
    api('/admin/config/active/prompt_packs'),
    api('/admin/config/active/service_scenarios'),
  ]);
  const packs = active.payload?.packs || [];
  const scenarios = scenariosConfig.payload?.scenarios || [];
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
        <button type="button" data-action="prompt-pack-load">Загрузить</button>
      </div>
      <div class="scenario-menu">
        <button type="button" class="${state.promptPackOperation === 'create' ? 'primary' : ''}" data-action="prompt-pack-operation" data-operation="create">Создать</button>
        <button type="button" class="${state.promptPackOperation === 'modify' ? 'primary' : ''}" data-action="prompt-pack-operation" data-operation="modify">Модифицировать</button>
        <button type="button" class="${state.promptPackOperation === 'delete' ? 'primary' : ''}" data-action="prompt-pack-operation" data-operation="delete">Удалить</button>
      </div>
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
    waiting_policy: template.waiting_policy || {
      first_reminder_after_seconds: 0,
      discussion_timeout_seconds: 0,
      sla_elapsed_percent_threshold: 0,
      on_no_answer: 'debug_stop',
    },
    incomplete_discussion_action: template.incomplete_discussion_action || {
      action_type: 'debug_stop',
      message_template: 'Остановить сценарий и показать недостающий контекст.',
    },
    escalation_action: template.escalation_action || {
      action_type: 'debug_stop',
      message_template: 'Остановить сценарий и показать причину эскалации.',
    },
    action_profiles: template.action_profiles || defaultChannelActionProfiles(template.channel_id || 'debug'),
    audit_required: template.audit_required ?? true,
    enabled: template.enabled ?? true,
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
  return `
    <form class="scenario-editor panel" data-form="interaction-channel-editor">
      <input type="hidden" name="channel_id" value="${escapeHtml(current.channel_id)}">
      <label>Название<input name="display_name" value="${escapeHtml(current.display_name || '')}" autocomplete="off"></label>
      <label>Описание<textarea name="description" rows="3">${escapeHtml(current.description || '')}</textarea></label>
      <div class="grid two">
        <label>Режим<select name="mode">${optionList(['online_interactive', 'offline_interactive', 'debug'], current.mode)}</select></label>
        <label>Канал включен<select name="enabled">${booleanOptions(current.enabled)}</select></label>
        <label>Аудит обязателен<select name="audit_required">${booleanOptions(current.audit_required)}</select></label>
      </div>
      <fieldset class="launch-editor">
        <legend>Ожидание ответа</legend>
        <div class="grid two">
          <label>Первое напоминание, сек<input name="first_reminder_after_seconds" type="number" min="0" max="604800" value="${escapeHtml(current.waiting_policy?.first_reminder_after_seconds ?? 0)}"></label>
          <label>Таймаут обсуждения, сек<input name="discussion_timeout_seconds" type="number" min="0" max="604800" value="${escapeHtml(current.waiting_policy?.discussion_timeout_seconds ?? 0)}"></label>
          <label>Порог SLA для офлайн-канала, %<input name="sla_elapsed_percent_threshold" type="number" min="0" max="100" value="${escapeHtml(current.waiting_policy?.sla_elapsed_percent_threshold ?? 0)}"></label>
          <label>Если ответа нет<select name="on_no_answer">${optionList(['save_context', 'create_draft', 'create_work_order', 'call_specialist', 'debug_stop'], current.waiting_policy?.on_no_answer || 'debug_stop')}</select></label>
        </div>
      </fieldset>
      ${renderChannelActionFields('question_delivery', 'Доставка вопроса', current.question_delivery)}
      ${renderChannelActionFields('incomplete_discussion_action', 'Незавершенное обсуждение', current.incomplete_discussion_action)}
      ${renderChannelActionFields('escalation_action', 'Действие эскалации', current.escalation_action)}
      ${renderChannelActionProfiles(current.action_profiles || [])}
      ${channelUsagePanel(scenarios, current.channel_id)}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">${state.interactionChannelOperation === 'create' ? 'Создать канал' : 'Сохранить канал'}</button>
      </div>
    </form>
  `;
}

function renderChannelActionProfiles(profiles) {
  return `
    <fieldset class="launch-editor">
      <legend>Профили действий канала</legend>
      <div class="meta">Профиль связывает логическое событие из блока "5. Решение и эскалация" с реальным действием канала.</div>
      <div id="channelProfileCards">${(profiles || []).map((profile) => renderChannelProfileCard(profile)).join('')}</div>
      <button type="button" data-action="channel-profile-add">Добавить профиль</button>
    </fieldset>
  `;
}

function renderChannelProfileCard(profile = {}) {
  const action = profile.action || {};
  return `
    <fieldset class="launch-editor" data-channel-profile-card>
      <legend>${escapeHtml(profile.display_name || 'Профиль действия')}</legend>
      <input type="hidden" name="profile_id" value="${escapeHtml(profile.profile_id || 'custom_profile')}">
      <label>Название<input name="display_name" value="${escapeHtml(profile.display_name || '')}" autocomplete="off"></label>
      <div class="grid two">
        <label>Тип события<select name="event_type">${optionList(['standard_handoff', 'no_answer', 'major_incident', 'policy_blocked', 'debug_stop'], profile.event_type || 'standard_handoff')}</select></label>
        <label>Действие<select name="action_type">${optionList(channelActionTypes(), action.action_type || 'debug_stop')}</select></label>
        <label>ReAct-вызов ИИ<input name="tool_name" value="${escapeHtml(action.tool_name || '')}" autocomplete="off" placeholder="необязательно"></label>
        <label>Подключение<input name="endpoint_id" value="${escapeHtml(action.endpoint_id || '')}" autocomplete="off" placeholder="mock / n8n / direct_http"></label>
        <label>Операция<input name="operation_id" value="${escapeHtml(action.operation_id || '')}" autocomplete="off" placeholder="operation_id"></label>
      </div>
      <label>Шаблон сообщения<textarea name="message_template" rows="3">${escapeHtml(action.message_template || '')}</textarea></label>
      <button class="danger" type="button" data-action="channel-profile-remove">Удалить профиль</button>
    </fieldset>
  `;
}

function renderChannelActionFields(prefix, title, action = {}) {
  return `
    <fieldset class="launch-editor">
      <legend>${escapeHtml(title)}</legend>
      <div class="grid two">
        <label>Действие<select name="${escapeHtml(prefix)}_action_type">${optionList(channelActionTypes(), action.action_type || 'debug_stop')}</select></label>
        <label>ReAct-вызов ИИ<input name="${escapeHtml(prefix)}_tool_name" value="${escapeHtml(action.tool_name || '')}" autocomplete="off" placeholder="необязательно"></label>
        <label>Подключение<input name="${escapeHtml(prefix)}_endpoint_id" value="${escapeHtml(action.endpoint_id || '')}" autocomplete="off" placeholder="mock / n8n / direct_http"></label>
        <label>Операция<input name="${escapeHtml(prefix)}_operation_id" value="${escapeHtml(action.operation_id || '')}" autocomplete="off" placeholder="operation_id"></label>
      </div>
      <label>Шаблон сообщения<textarea name="${escapeHtml(prefix)}_message_template" rows="3">${escapeHtml(action.message_template || '')}</textarea></label>
    </fieldset>
  `;
}

function channelActionTypes() {
  return ['ask_end_user', 'ask_operator', 'show_debug_message', 'save_context', 'create_draft', 'create_work_order', 'call_specialist', 'notify_on_call', 'debug_stop'];
}

function defaultChannelActionProfiles(channelId) {
  if (channelId === 'messenger_bot') {
    return [
      { profile_id: 'standard_handoff', display_name: 'Передача специалисту в чат', event_type: 'standard_handoff', action: { action_type: 'call_specialist', message_template: 'Позвать специалиста в диалог с полным контекстом сценария.' } },
      { profile_id: 'no_answer', display_name: 'Нет ответа: создать черновик', event_type: 'no_answer', action: { action_type: 'create_draft', message_template: 'Создать черновик заявки и сохранить контекст диалога.' } },
      { profile_id: 'major_incident', display_name: 'Major Incident: оповестить дежурных', event_type: 'major_incident', action: { action_type: 'notify_on_call', message_template: 'Оповестить дежурную команду и приложить пакет Major Incident.' } },
      { profile_id: 'policy_blocked', display_name: 'Политика заблокировала автоисполнение', event_type: 'policy_blocked', action: { action_type: 'call_specialist', message_template: 'Позвать специалиста для ручной проверки.' } },
    ];
  }
  if (channelId === 'service_desk') {
    return [
      { profile_id: 'standard_handoff', display_name: 'Передача: создать наряд', event_type: 'standard_handoff', action: { action_type: 'create_work_order', message_template: 'Создать наряд ответственному специалисту с пакетом эскалации.' } },
      { profile_id: 'no_answer', display_name: 'Нет ответа: создать наряд', event_type: 'no_answer', action: { action_type: 'create_work_order', message_template: 'Создать наряд по незавершенному обсуждению и приложить контекст.' } },
      { profile_id: 'major_incident', display_name: 'Major Incident: создать наряд дежурной группе', event_type: 'major_incident', action: { action_type: 'create_work_order', message_template: 'Создать срочный наряд дежурной группе с пакетом Major Incident.' } },
      { profile_id: 'policy_blocked', display_name: 'Политика заблокировала автоисполнение', event_type: 'policy_blocked', action: { action_type: 'create_work_order', message_template: 'Создать наряд для ручной проверки.' } },
    ];
  }
  return [
    { profile_id: 'standard_handoff', display_name: 'Отладка: остановить передачу', event_type: 'standard_handoff', action: { action_type: 'debug_stop', message_template: 'Остановить сценарий и показать причину эскалации оператору.' } },
    { profile_id: 'no_answer', display_name: 'Отладка: нет ответа', event_type: 'no_answer', action: { action_type: 'debug_stop', message_template: 'Остановить dry-run из-за отсутствия ответа.' } },
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
      <div class="grid two">
        <label>Статус<select name="status">${statusOptions}</select></label>
        <label>Теги<input name="tags" value="${escapeHtml((scenario.tags || []).join(', '))}" autocomplete="off"></label>
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
        <summary>Переопределение порогов уверенности</summary>
        <div class="meta">Заполняйте только если сценарий должен отличаться от системных порогов. Пустые поля наследуются от уровня системы.</div>
        ${renderConfidenceThresholdInputs('scenario_confidence', scenario.confidence_overrides || {})}
      </details>
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">${state.scenarioOperation === 'create' ? 'Создать сценарий' : 'Сохранить изменения'}</button>
      </div>
    </form>
  `;
}

async function renderResolutionProfiles() {
  const [active, slotSchemasConfig, scenariosConfig, toolsConfig, endpointsConfig] = await Promise.all([
    api('/admin/config/active/attribute_resolution_profiles'),
    api('/admin/config/active/slot_schemas'),
    api('/admin/config/active/service_scenarios'),
    api('/admin/config/active/tools'),
    api('/admin/config/active/integration_endpoints'),
  ]);
  const profiles = active.payload?.profiles || [];
  const slotSchemas = slotSchemasConfig.payload?.slot_schemas || [];
  const scenarios = scenariosConfig.payload?.scenarios || [];
  const tools = toolsConfig.payload?.tools || [];
  const endpoints = endpointsConfig.payload?.endpoints || [];
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
  });
  elements.viewContent.innerHTML = [
    section(
      'Профили разрешения атрибутов',
      `${resolutionProfileHowToPanel()}
      <div class="toolbar compact">
        <label>Профиль<select id="resolutionProfileSelect">${profileOptions}</select></label>
        <button type="button" data-action="resolution-load">Загрузить</button>
      </div>
      <div class="scenario-menu">
        <button type="button" class="${state.resolutionOperation === 'create' ? 'primary' : ''}" data-action="resolution-operation" data-operation="create">Создать</button>
        <button type="button" class="${state.resolutionOperation === 'modify' ? 'primary' : ''}" data-action="resolution-operation" data-operation="modify">Модифицировать</button>
        <button type="button" class="${state.resolutionOperation === 'delete' ? 'primary' : ''}" data-action="resolution-operation" data-operation="delete">Удалить</button>
      </div>
      ${editor}`,
    ),
  ].join('');
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
        "Сценарии обработки -> 0. Слоты", раскройте нужный слот, выберите "Способ заполнения = профиль разрешения"
        и затем выберите этот профиль в поле "Профиль разрешения атрибута".
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

function renderResolutionProfileEditor({ profile, profiles, slotSchemas = [], scenarios = [], tools = [], endpoints = [] }) {
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
  const statusOptions = ['active', 'draft', 'planned', 'disabled']
    .map((status) => `<option value="${status}" ${current.status === status ? 'selected' : ''}>${escapeHtml(visibleLabels[status] || status)}</option>`)
    .join('');
  const sourceType = current.candidate_source?.source_type || 'react_call';
  const sourceTypeOptions = ['react_call', 'ticket_history', 'case_data', 'disabled']
    .map((value) => `<option value="${value}" ${sourceType === value ? 'selected' : ''}>${escapeHtml(resolutionSourceTypeLabels[value] || value)}</option>`)
    .join('');
  const handoffAction = current.handoff_policy?.action || 'operator_handoff';
  const handoffOptions = ['operator_handoff', 'escalate', 'debug_stop', 'leave_empty']
    .map((value) => `<option value="${value}" ${handoffAction === value ? 'selected' : ''}>${escapeHtml(visibleLabels[value] || value)}</option>`)
    .join('');
  const fallbackAction = current.fallback?.action || 'ask_user';
  const fallbackOptions = ['ask_user', 'operator_handoff', 'escalate', 'leave_empty']
    .map((value) => `<option value="${value}" ${fallbackAction === value ? 'selected' : ''}>${escapeHtml(visibleLabels[value] || value)}</option>`)
    .join('');
  const resultPolicy = resolutionResultPolicy(current);
  const resultType = resultPolicy.result_type || 'list';
  const resultTypeOptions = [
    ['list', 'список результатов'],
    ['object', 'один объект'],
  ]
    .map(([value, label]) => `<option value="${value}" ${resultType === value ? 'selected' : ''}>${escapeHtml(label)}</option>`)
    .join('');
  return `
    <form class="scenario-editor panel" data-form="resolution-profile-editor">
      <input type="hidden" name="profile_id" value="${escapeHtml(current.profile_id || '')}">
      <input type="hidden" name="history_filter_json" value="${escapeHtml(JSON.stringify(current.candidate_source?.history_filter || {}))}">
      <div class="grid two">
        <label>Название<input name="display_name" value="${escapeHtml(current.display_name || '')}" autocomplete="off"></label>
        <label>Статус<select name="status">${statusOptions}</select></label>
      </div>
      <label>Описание<textarea name="description" rows="3">${escapeHtml(current.description || '')}</textarea></label>
      <div class="grid two">
        <label>Целевой слот
          <input name="target_slot_id" value="${escapeHtml(current.target_slot_id || '')}" autocomplete="off" placeholder="user_login">
          <span class="field-help">Основной слот, ради которого выполняется профиль.</span>
        </label>
        <label>Выходные слоты
          <input name="output_slots" value="${escapeHtml(csv(current.output_slots))}" autocomplete="off" placeholder="user_login, user_id">
          <span class="field-help">Слоты сценария, которые профиль может заполнить.</span>
        </label>
        <label>Лимит попыток
          <input name="max_attempts" type="number" min="1" max="10" value="${escapeHtml(current.max_attempts || 1)}">
          <span class="field-help">Сколько раз можно уточнять признаки и повторять операцию разрешения.</span>
        </label>
        <label>Audit<select name="audit_required">${booleanOptions(current.audit_required)}</select></label>
        <label>Log<select name="log_required">${booleanOptions(current.log_required)}</select></label>
      </div>
      <fieldset class="launch-editor">
        <legend>Признаки для поиска</legend>
        <div class="grid two">
          <label>Извлечь из текста обращения
            <input name="llm_attributes" value="${escapeHtml(csv(attributeIdsBySource(current, 'llm')))}" autocomplete="off" placeholder="last_name, first_name, email">
            <span class="field-help">Модель извлекает эти признаки из текста, но не принимает решение о заполнении слота.</span>
          </label>
          <label>Взять из слотов сценария
            <input name="slot_attributes" value="${escapeHtml(csv(attributeIdsBySource(current, 'slot')))}" autocomplete="off" placeholder="user_login, device_id">
            <span class="field-help">Значения уже должны быть собраны как слоты сценария.</span>
          </label>
          <label>Запросить при уточнении
            <input name="operator_attributes" value="${escapeHtml(csv(attributeIdsBySource(current, 'operator_answer')))}" autocomplete="off" placeholder="department, employee_number">
            <span class="field-help">Эти признаки можно спросить у пользователя или оператора, если результат пустой или неоднозначный.</span>
          </label>
        </div>
      </fieldset>
      <fieldset class="launch-editor">
        <legend>Операция разрешения атрибута</legend>
        <div class="grid two">
          <label>Тип выполнения
            <select name="candidate_source_type">${sourceTypeOptions}</select>
            <span class="field-help">Обычно это ReAct-вызов чтения: AD, CMDB, история заявок или другой безопасный источник результата.</span>
          </label>
          <label>ReAct-вызов и операция
            <select name="candidate_binding">${candidateBindingOptions(tools, current.candidate_source)}</select>
            <span class="field-help">Выберите связку ReAct-вызова, подключения и операции. Настройка самой операции находится в "Инструменты и интеграции".</span>
          </label>
        </div>
        ${renderCandidateParameterMapping(current, tools, endpoints)}
      </fieldset>
      <fieldset class="launch-editor">
        <legend>Как оценивать результат операции</legend>
        <div class="grid two">
          <label>Тип результата
            <select name="result_type">${resultTypeOptions}</select>
            <span class="field-help">Список используется для нескольких результатов, объект - для ответа "найдено/не найдено".</span>
          </label>
          <label>Путь списка результатов
            <input name="result_list_path" value="${escapeHtml(resultPolicy.list_path || '')}" autocomplete="off" placeholder="users">
            <span class="field-help">Для типа "список": где в ответе операции лежит массив результатов.</span>
          </label>
          <label>Путь объекта
            <input name="result_object_path" value="${escapeHtml(resultPolicy.object_path || '')}" autocomplete="off" placeholder="object">
            <span class="field-help">Для типа "один объект": где лежит объект результата. Можно оставить пустым, если ответ операции сам является объектом.</span>
          </label>
          <label>Признак успешного поиска
            <input name="result_success_path" value="${escapeHtml(resultPolicy.success_path || '')}" autocomplete="off" placeholder="object_found">
            <span class="field-help">Для типа "один объект": boolean-поле, которое говорит, что объект найден.</span>
          </label>
          <label>Значение целевого слота
            <input name="result_target_value_path" value="${escapeHtml(resultPolicy.target_value_path || '')}" autocomplete="off" placeholder="login">
            <span class="field-help">Поле результата, которым будет заполнен целевой слот профиля.</span>
          </label>
          <label>Confidence результата
            <input name="result_confidence_path" value="${escapeHtml(resultPolicy.confidence_path || '')}" autocomplete="off" placeholder="confidence">
          </label>
          <label>Отображаемое имя результата
            <input name="result_display_value_path" value="${escapeHtml(resultPolicy.display_value_path || '')}" autocomplete="off" placeholder="display_name">
          </label>
        </div>
        <label>Дополнительные выходные слоты
          <textarea name="result_output_mapping" rows="3" placeholder="user_id=user_id">${escapeHtml(formatKeyValueLines(resultPolicy.output_mapping))}</textarea>
          <span class="field-help">Одна строка на слот: слот=поле результата операции. Например user_id=user_id.</span>
        </label>
      </fieldset>
      <fieldset class="launch-editor">
        <legend>Матрица решений</legend>
        <div class="grid two">
          ${renderDecisionSelect('empty_result', 'Если результата нет', resolutionDecisionValue(current.decision_policy, 'empty_result'))}
          ${renderDecisionSelect('single_result', 'Если результат один', resolutionDecisionValue(current.decision_policy, 'single_result'))}
          ${renderDecisionSelect('multiple_results', 'Если результатов несколько', resolutionDecisionValue(current.decision_policy, 'multiple_results'))}
          ${renderDecisionSelect('source_error', 'Если источник недоступен', current.decision_policy?.source_error)}
          ${renderDecisionSelect('attempt_limit', 'Если попытки исчерпаны', current.decision_policy?.attempt_limit)}
        </div>
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
          <label>Передача человеку ниже
            <input name="confidence_operator_handoff" type="number" min="0" max="1" step="0.01" value="${escapeHtml(current.confidence_thresholds?.operator_handoff ?? '')}">
          </label>
        </div>
      </details>
      <fieldset class="launch-editor">
        <legend>Уточнение и передача человеку</legend>
        <div class="grid two">
          <label>Уточняемые атрибуты
            <input name="clarification_ask_for_attributes" value="${escapeHtml(csv(current.clarification_policy?.ask_for_attributes))}" autocomplete="off" placeholder="department, employee_number">
            <span class="field-help">Какие признаки попросить для следующей попытки поиска.</span>
          </label>
          <label>Пакет передачи человеку
            <input name="handoff_package" value="${escapeHtml(csv(current.handoff_policy?.package))}" autocomplete="off" placeholder="last_name, users, user_login">
            <span class="field-help">Какие собранные слоты и промежуточные атрибуты передать сотруднику при ручной обработке.</span>
          </label>
          <label>Действие передачи
            <select name="handoff_action">${handoffOptions}</select>
          </label>
          <label>Резервное действие
            <select name="fallback_action">${fallbackOptions}</select>
          </label>
        </div>
        <label>Вопрос при неоднозначном или пустом результате
          <textarea name="clarification_question" rows="2">${escapeHtml(current.clarification_policy?.question || current.fallback?.question || '')}</textarea>
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
  react_call: 'ReAct-вызов чтения',
  ticket_history: 'история заявок',
  case_data: 'данные обращения',
  disabled: 'отключен',
};

const resolutionDecisionLabels = {
  auto_fill_if_confident: 'заполнить, если уверенность достаточна',
  ask_clarification: 'задать уточняющий вопрос',
  ask_disambiguation: 'спросить для выбора результата',
  operator_handoff: 'передать человеку',
  escalate: 'эскалировать',
  leave_empty: 'оставить пустым',
  debug_stop: 'остановить в отладке',
};

function attributeIdsBySource(profile, source) {
  return (profile.input_attributes || [])
    .filter((attribute) => attribute.source === source)
    .map((attribute) => attribute.source === 'slot' ? attribute.source_ref || attribute.attribute_id : attribute.attribute_id);
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
  const source = profile.candidate_source || {};
  const endpoint = (endpoints || []).find((item) => item.endpoint_id === source.endpoint_id);
  const operation = endpoint?.operations?.[source.operation_id] || null;
  const tool = (tools || []).find((item) => item.tool_name === source.tool_name) || null;
  return { tool, endpoint, operation };
}

function resolutionResultPolicy(profile = {}) {
  if (profile.result_policy) return profile.result_policy;
  const mapping = profile.candidate_mapping || {};
  const looksLikeObject = mapping.candidate_count_path === 'object_found' || mapping.candidates_path === 'object';
  const policy = {
    result_type: looksLikeObject ? 'object' : 'list',
    target_value_path: mapping.value_path || profile.target_slot_id || 'value',
    confidence_path: mapping.confidence_path || '',
    display_value_path: mapping.label_path || '',
    output_mapping: mapping.output_mapping || {},
  };
  if (looksLikeObject) {
    policy.object_path = mapping.candidates_path || 'object';
    policy.success_path = mapping.candidate_count_path || '';
  } else {
    policy.list_path = mapping.candidates_path || 'candidates';
  }
  return policy;
}

function resolutionDecisionValue(policy = {}, key) {
  const legacy = {
    empty_result: 'zero_candidates',
    single_result: 'single_candidate',
    multiple_results: 'multiple_candidates',
  };
  return policy[key] || policy[legacy[key]] || defaultResolutionDecisionPolicy[key];
}

function resolutionAttributeOptions(profile, selected) {
  const attributes = profile.input_attributes || [];
  const options = [`<option value="" ${!selected ? 'selected' : ''}>не использовать</option>`];
  for (const attribute of attributes) {
    const isSlot = attribute.source === 'slot';
    const value = isSlot
      ? `slot:${attribute.source_ref || attribute.attribute_id}`
      : `attribute:${attribute.attribute_id}`;
    const labelPrefix = isSlot ? 'Слот: ' : 'Признак: ';
    const label = `${labelPrefix}${attribute.display_name || attribute.source_ref || attribute.attribute_id}`;
    options.push(`<option value="${escapeHtml(value)}" ${selected === value ? 'selected' : ''}>${escapeHtml(label)}</option>`);
  }
  if (selected && !options.some((option) => option.includes(`value="${escapeHtml(selected)}"`))) {
    options.push(`<option value="${escapeHtml(selected)}" selected>${escapeHtml(selected)}</option>`);
  }
  return options.join('');
}

function renderCandidateParameterMapping(profile, tools, endpoints) {
  const { operation } = selectedCandidateOperation(profile, tools, endpoints);
  const mapping = profile.candidate_source?.parameter_mapping || {};
  const names = operation ? operationParameterNames(operation, mapping) : Object.keys(mapping);
  if (!names.length) {
    return '<div class="empty">У выбранной операции нет описанных входных параметров.</div>';
  }
  return `
    <div class="parameter-binding-list">
      <div class="parameter-binding-header">
        <span>Входной параметр операции</span>
        <span>Значение взять из</span>
      </div>
      ${names.map((name) => `
        <div class="parameter-binding-row" data-candidate-param-row>
          <input type="hidden" data-candidate-param-name value="${escapeHtml(name)}">
          <div class="parameter-binding-meta">
            <strong>${escapeHtml(name)}</strong>
            <span>${escapeHtml(operation ? schemaMetaLine(name, schemaProperties(operation.request_schema || {})[name], schemaRequired(operation.request_schema || {}).includes(name), ' входной параметр') : 'входной параметр операции')}</span>
          </div>
          <label>Значение взять из
            <select data-candidate-param-source>${resolutionAttributeOptions(profile, mapping[name] || defaultResolutionParameterSource(name, profile))}</select>
          </label>
        </div>
      `).join('')}
    </div>
  `;
}

function defaultResolutionParameterSource(parameterName, profile) {
  const attributes = profile.input_attributes || [];
  const byId = new Map(attributes.map((attribute) => [attribute.attribute_id, attribute]));
  const bySourceRef = new Map(attributes
    .filter((attribute) => attribute.source === 'slot')
    .map((attribute) => [attribute.source_ref || attribute.attribute_id, attribute]));
  const directSlot = bySourceRef.get(parameterName);
  if (directSlot) return `slot:${directSlot.source_ref || directSlot.attribute_id}`;
  const directAttribute = byId.get(parameterName);
  if (directAttribute?.source === 'slot') return `slot:${directAttribute.source_ref || directAttribute.attribute_id}`;
  if (directAttribute) return `attribute:${parameterName}`;
  if (parameterName === 'login' && bySourceRef.has('user_login')) return 'slot:user_login';
  if (parameterName === 'login' && byId.get('user_login')?.source === 'slot') return `slot:${byId.get('user_login').source_ref || 'user_login'}`;
  if (parameterName === 'login' && byId.has('login_candidate')) return 'attribute:login_candidate';
  return '';
}

function renderDecisionSelect(key, label, selected) {
  const value = selected || defaultResolutionDecisionPolicy[key] || 'ask_clarification';
  return `
    <label>${escapeHtml(label)}
      <select name="decision_${escapeHtml(key)}">
        ${Object.entries(resolutionDecisionLabels)
          .map(([action, actionLabel]) => `<option value="${escapeHtml(action)}" ${action === value ? 'selected' : ''}>${escapeHtml(actionLabel)}</option>`)
          .join('')}
      </select>
    </label>
  `;
}

const defaultResolutionDecisionPolicy = {
  empty_result: 'ask_clarification',
  single_result: 'auto_fill_if_confident',
  multiple_results: 'ask_disambiguation',
  source_error: 'operator_handoff',
  attempt_limit: 'operator_handoff',
};

function formatKeyValueLines(value) {
  return Object.entries(value || {})
    .map(([key, item]) => `${key}=${item}`)
    .join('\n');
}

function resolutionProfileCreateTemplate(source, profiles) {
  const template = source || profiles[0] || {};
  return {
    profile_id: nextProfileId(template.profile_id || 'profile.custom.attribute', profiles),
    display_name: '',
    status: 'draft',
    description: '',
    target_slot_id: template.target_slot_id || '',
    output_slots: template.output_slots || [],
    input_attributes: template.input_attributes || [
      {
        attribute_id: 'value',
        display_name: 'Значение',
        source: 'llm',
        required: false,
        extraction_instruction: 'Извлеки значение из текста обращения.',
      },
    ],
    candidate_source: template.candidate_source || {
      source_type: 'disabled',
      parameter_mapping: {},
    },
    result_policy: template.result_policy || resolutionResultPolicy(template) || {
      result_type: 'list',
      list_path: 'candidates',
      target_value_path: 'value',
      confidence_path: 'confidence',
      display_value_path: 'display_name',
      output_mapping: {},
    },
    decision_policy: template.decision_policy || defaultResolutionDecisionPolicy,
    clarification_policy: template.clarification_policy || {
      question: 'Уточните данные для заполнения атрибута.',
      ask_for_attributes: ['value'],
    },
    handoff_policy: template.handoff_policy || {
      action: 'operator_handoff',
      package: ['value'],
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
    audit_required: template.audit_required ?? true,
    log_required: template.log_required ?? true,
  };
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
    escalation_response: 'Опишите условия эскалации и формат ответа пользователю.',
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
    timeouts: template.timeouts || {
      reminder_after_seconds: 180,
      draft_after_seconds: 480,
    },
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

function renderSlotSchemaEditor({ slotSchema, slotSchemas, scenarios, resolutionProfiles = [] }) {
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
    .map((slot, index) => renderSlotCard(slot, index + 1, false, resolutionProfiles))
    .join('');
  return `
    <form class="scenario-editor panel" data-form="slot-schema-editor">
      <input type="hidden" name="slot_schema_id" value="${escapeHtml(current.slot_schema_id)}">
      <label>Название<input name="display_name" value="${escapeHtml(current.display_name)}" autocomplete="off"></label>
      <div class="grid two">
        <label>Напоминание, секунд<input name="reminder_after_seconds" type="number" min="30" max="1800" value="${escapeHtml(current.timeouts?.reminder_after_seconds || 180)}"></label>
        <label>Черновик, секунд<input name="draft_after_seconds" type="number" min="60" max="7200" value="${escapeHtml(current.timeouts?.draft_after_seconds || 480)}"></label>
      </div>
      <div class="slot-schema-derived">
        <div class="metric-label">Служебные списки</div>
        <div class="meta">required_slots, auto_fill_slots и question_order собираются автоматически из карточек слотов при сохранении.</div>
      </div>
      <div class="slot-schema-derived">
        <div class="metric-label">Где выбрать профиль разрешения атрибута</div>
        <div class="meta">
          Раскройте карточку нужного слота. В поле "Способ заполнения" выберите "профиль разрешения",
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

function renderSlotCard(slot = {}, order = '', open = false, resolutionProfiles = []) {
  const required = slot.required === true;
  const fillMethod = slot.fill_method || legacyFillMethod(slot.source);
  const priorityGroup = slot.priority_group || 'what';
  const title = slot.display_name || slot.slot_id || 'Новый слот';
  const keyLabel = slot.slot_id || 'Ключ не задан';
  const requiredLabel = required ? 'обязательный' : 'необязательный';
  const profile = resolutionProfiles.find((item) => item.profile_id === slot.resolution_profile_id);
  const methodLabel = profile?.display_name || visibleLabels[fillMethod] || fillMethod;
  const profileHint = profile
    ? `<div class="slot-schema-derived">
        <div class="metric-label">Выбранный профиль разрешения</div>
        <div class="meta">
          ${escapeHtml(profile.display_name)}. Целевой слот: ${escapeHtml(profile.target_slot_id || 'н/д')}.
          Выходы: ${escapeHtml(formatList(profile.output_slots))}.
          Вопрос при неоднозначности: ${escapeHtml(profile.clarification_policy?.question || profile.fallback?.question || 'н/д')}.
        </div>
      </div>`
    : `<div class="slot-schema-derived">
        <div class="metric-label">Профиль разрешения не выбран</div>
        <div class="meta">Если слот должен заполняться через AD, CMDB, RAG или несколько попыток поиска, выберите "Способ заполнения = профиль разрешения" и готовый профиль ниже.</div>
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
          <label>Способ заполнения
            <select name="fill_method" data-slot-fill-method>${fillMethodOptions(fillMethod)}</select>
            <span class="field-help">Выберите, откуда платформа берет значение слота.</span>
            <span class="field-help" data-fill-method-help>${escapeHtml(fillMethodHelpText(fillMethod))}</span>
          </label>
        </div>
        <div class="slot-method-section" data-fill-method-section="user_question">
          <label>Вопрос пользователю
            <textarea name="user_question" rows="3" placeholder="Уточните логин пользователя.">${escapeHtml(slot.user_question || slot.question || '')}</textarea>
            <span class="field-help">Текст вопроса, который будет отправлен пользователю или показан оператору канала.</span>
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
        <div class="slot-method-section" data-fill-method-section="resolution_profile">
          ${profileHint}
          <label>Профиль разрешения атрибута
            <select name="resolution_profile_id">${resolutionProfileOptions(resolutionProfiles, slot.resolution_profile_id, slot.slot_id)}</select>
            <span class="field-help">Профиль задает порядок LLM extraction, ReAct-вызовов, поиска по истории и уточняющих вопросов.</span>
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
            <span class="field-help">Позиция в очереди обогащения. Учитывается для вопросов пользователю, профилей разрешения и ручного заполнения оператором.</span>
          </label>
          </div>
        </div>
        <details class="slot-method-section">
          <summary>Переопределение порогов для слота</summary>
          <div class="meta">Заполняйте только для чувствительных слотов. Пустые поля наследуются от сценария и системных порогов.</div>
          ${renderConfidenceThresholdInputs('slot_confidence', slot.confidence_overrides || {})}
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
  const values = ['user_question', 'case', 'llm_extraction', 'resolution_profile', 'operator_manual'];
  return values
    .map((value) => `<option value="${value}" ${value === selected ? 'selected' : ''}>${visibleLabels[value] || value}</option>`)
    .join('');
}

function fillMethodHelpText(method) {
  const help = {
    user_question: 'Платформа задает вопрос пользователю или оператору канала и ждет ответ.',
    case: 'Значение уже есть в текущем обращении: канал, карточка заявки, сохраненный контекст или системные поля. Внешние системы здесь не вызываются.',
    llm_extraction: 'Модель извлекает значение из текста обращения и уже собранного контекста без вызова внешних систем.',
    resolution_profile: 'Используется отдельный профиль с шагами LLM, RAG, ReAct-вызовами, поиском по истории и уточняющими вопросами.',
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

function renderConfidenceThresholdInputs(prefix, thresholds = {}, { required = false } = {}) {
  return `
    <div class="grid two">
      ${confidenceThresholdFields.map((field) => `
        <label>${escapeHtml(field.label)}
          <input name="${escapeHtml(`${prefix}_${field.key}`)}" type="number" min="0" max="1" step="0.01" value="${escapeHtml(thresholds?.[field.key] ?? '')}" ${required ? 'required' : ''}>
          <span class="field-help">${escapeHtml(field.help)}</span>
        </label>
      `).join('')}
    </div>
  `;
}

function parseConfidenceThresholdsFromForm(data, prefix, { required = false } = {}) {
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
    const slotAllowed = !slotId || profile.output_slots?.includes(slotId) || selected === profile.profile_id;
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
      keywords: [],
      negative_keywords: [],
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
        <label>Маршрут<select name="route">${optionList(['auto_agent', 'agent_with_confirmation', 'human_review', 'major_incident', 'approver'], current.route)}</select></label>
        <label>Состояние workflow<input name="workflow_state_id" value="${escapeHtml(current.workflow_state_id || '')}" autocomplete="off"></label>
        <label>Top категорий<input name="top_categories_on_low_confidence" type="number" min="1" max="5" value="${escapeHtml(current.top_categories_on_low_confidence || 3)}"></label>
        <label>Порог правил<input name="rules_min" type="number" min="0" max="1" step="0.01" value="${escapeHtml(current.confidence?.rules_min ?? 0.85)}"></label>
        <label>Порог LLM<input name="llm_min" type="number" min="0" max="1" step="0.01" value="${escapeHtml(current.confidence?.llm_min ?? 0.7)}"></label>
        <label>Человек ниже<input name="human_handoff_below" type="number" min="0" max="1" step="0.01" value="${escapeHtml(current.confidence?.human_handoff_below ?? 0.5)}"></label>
      </div>
      <label>Действие<textarea name="action" rows="3">${escapeHtml(current.action || '')}</textarea></label>
      <div class="grid two">
        <label>Ключевые слова<input name="keywords" value="${escapeHtml(csv(current.rules?.keywords))}"></label>
        <label>Негативные ключевые слова<input name="negative_keywords" value="${escapeHtml(csv(current.rules?.negative_keywords))}"></label>
      </div>
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
        <label>Ошибок ReAct-вызовов подряд до передачи<input name="consecutive_tool_errors_to_escalate" type="number" min="1" max="10" value="${escapeHtml(current.consecutive_tool_errors_to_escalate || 2)}"></label>
      </div>
      <fieldset class="launch-editor">
        <legend>Разрешенные группы действий ReAct</legend>
        <div class="meta">Верхнеуровневые рамки планирования. Конкретные ReAct-вызовы ИИ и режим запуска задаются в блоке "4. ReAct-вызовы и матрица запуска".</div>
        ${renderChoiceChecklist('allowed_react_action_groups', reactActionGroupChoices, current.allowed_react_action_groups || [])}
      </fieldset>
      <fieldset class="launch-editor">
        <legend>Стоп-условия</legend>
        <div class="meta">Когда ReAct-loop должен остановиться и перейти к уточнению, результату или передаче.</div>
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
        audit_required: true,
        log_required: true,
        stop_on_error: true,
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
  const launchMode = launch.target_execution_level || launch.execution_level || 'operator_approval';
  const toolName = launch.tool_name || (tools || [])[0]?.tool_name || '';
  const tool = findToolInCatalog(tools, toolName);
  const binding = currentToolBinding(tool);
  const endpointId = binding?.endpoint_id || '';
  const operationId = binding?.operation_id || '';
  const bindingStatus = binding
    ? operationBindingSummary(binding, integrationEndpoints)
    : 'У выбранного ReAct-вызова ИИ нет привязки операции. Настройте ее в меню "Привязка операций".';
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
        'Техническое подключение выбирается в меню "Привязка операций" и подставляется сюда автоматически.',
        `<div class="${binding ? 'meta' : 'field-help'}" data-launch-binding-status>${escapeHtml(bindingStatus)}</div>`,
      )}
      ${renderLaunchGroup(
        'Параметры вызова',
        'Какие слоты, поля кейса, контекст, константы или секреты заполняют параметры выбранного вызова. Технический payload endpoint настраивается в "Привязка операций". Required slots вычисляются из источников вида slot:<slot_id>.',
        parameterBindingsEditor(tool, launch.parameter_bindings || {}, slotContext),
      )}
      ${renderLaunchGroup(
        'Контроль запуска',
        'Сценарная политика исполнения: согласование, риск, аудит, логирование и остановка при ошибке.',
        `<div class="grid two">
          <label>Вид запуска<select name="execution_mode_${index}">${optionList(['auto', 'operator_approval', 'approver_approval', 'blocked'], launchMode)}</select></label>
          <label>Риск<select name="risk_level_${index}">${optionList(['low', 'medium', 'high', 'critical', 'blocked'], launch.risk_level)}</select></label>
          <label>Роль согласования<input name="approval_role_${index}" value="${escapeHtml(launch.approval_role || '')}" autocomplete="off"></label>
          <label>Аудит<select name="audit_required_${index}">${booleanOptions(launch.audit_required)}</select></label>
          <label>Логирование<select name="log_required_${index}">${booleanOptions(launch.log_required)}</select></label>
          <label>Остановить при ошибке<select name="stop_on_error_${index}">${booleanOptions(launch.stop_on_error)}</select></label>
        </div>`,
      )}
      <button class="danger" type="button" data-action="launch-remove">Удалить запуск</button>
    </fieldset>
  `;
}

function escalationCreateTemplate(source, policies) {
  const template = source || policies[0] || {};
  return {
    policy_id: nextConfigItemId(template.policy_id || 'escalation.custom', policies, 'policy_id'),
    display_name: '',
    auto_close: template.auto_close || {
      requires_tool_success: true,
      requires_user_confirmation: true,
    },
    waiting: template.waiting || {
      pause_sla: true,
      auto_close_after_hours: 24,
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
          <div class="metric-label">Удаляемая политика эскалации</div>
          <div class="scenario-title">${escapeHtml(policy.display_name)}</div>
        </div>
        ${usagePanel(scenarios, 'escalation_policy_id', policy.policy_id)}
        <button class="danger" type="submit">Удалить политику эскалации</button>
      </form>
    `;
  }
  const current = state.escalationOperation === 'create'
    ? escalationCreateTemplate(policy, policies)
    : policy;
  if (!current?.policy_id) {
    return '<div class="empty">Политика эскалации не выбрана</div>';
  }
  return `
    <form class="scenario-editor panel" data-form="escalation-editor">
      <input type="hidden" name="policy_id" value="${escapeHtml(current.policy_id)}">
      <label>Название<input name="display_name" value="${escapeHtml(current.display_name || '')}" autocomplete="off"></label>
      <div class="grid two">
        <label>Автозакрытие требует успех ReAct-вызова<select name="requires_tool_success">${booleanOptions(current.auto_close?.requires_tool_success)}</select></label>
        <label>Автозакрытие требует подтверждение пользователя<select name="requires_user_confirmation">${booleanOptions(current.auto_close?.requires_user_confirmation)}</select></label>
        <label>Ожидание приостанавливает SLA<select name="pause_sla">${booleanOptions(current.waiting?.pause_sla)}</select></label>
        <label>Автозакрытие ожидания, часов<input name="auto_close_after_hours" type="number" min="1" max="168" value="${escapeHtml(current.waiting?.auto_close_after_hours || 24)}"></label>
        <label>Major Incident threshold<input name="affected_users_threshold" type="number" min="1" max="100000" value="${escapeHtml(current.major_incident?.affected_users_threshold || 10)}"></label>
      </div>
      <fieldset class="launch-editor">
        <legend>Условия передачи</legend>
        <div class="meta">Когда автообработка останавливается и кейс передается в выбранный канал взаимодействия.</div>
        ${renderChoiceChecklist('handoff_conditions', handoffConditionChoices, current.handoff_conditions || [])}
      </fieldset>
      <fieldset class="launch-editor">
        <legend>Пакет передачи</legend>
        <div class="meta">Какие данные попадут в пакет контекста для канала взаимодействия. Обязательные пункты нельзя отключить.</div>
        ${renderChoiceChecklist('handoff_package', handoffPackageChoices, current.handoff_package || [])}
      </fieldset>
      <label>Шаблон уведомления пользователя<textarea name="user_notification_template" rows="4">${escapeHtml(current.user_notification_template || '')}</textarea></label>
      ${usagePanel(scenarios, 'escalation_policy_id', current.policy_id)}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">${state.escalationOperation === 'create' ? 'Создать политику эскалации' : 'Сохранить решение и эскалацию'}</button>
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
  const statusOptions = ['active', 'draft', 'planned', 'disabled']
    .map((status) => `<option value="${status}" ${current.status === status ? 'selected' : ''}>${escapeHtml(visibleLabels[status] || status)}</option>`)
    .join('');
  return `
    <form class="scenario-editor panel" data-form="prompt-pack-editor">
      <input type="hidden" name="prompt_pack_id" value="${escapeHtml(current.prompt_pack_id)}">
      <div class="grid two">
        <label>Название<input name="display_name" value="${escapeHtml(current.display_name || '')}" autocomplete="off"></label>
        <label>Статус<select name="status">${statusOptions}</select></label>
        <label>Активная версия<input name="active_version" value="${escapeHtml(current.active_version || '')}" autocomplete="off"></label>
      </div>
      ${blockFields}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">${state.promptPackOperation === 'create' ? 'Создать пакет промптов' : 'Сохранить пакет промптов'}</button>
      </div>
    </form>
  `;
}

function optionList(values, selected) {
  return values
    .map((value) => `<option value="${escapeHtml(value)}" ${value === selected ? 'selected' : ''}>${escapeHtml(visibleLabels[value] || value)}</option>`)
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

function jsonPretty(value) {
  return JSON.stringify(value, null, 2);
}

async function renderDashboard() {
  const [session, dashboard, auditSummary] = await Promise.all([
    api('/admin/security/session'),
    api('/admin/dashboard'),
    api('/admin/security/audit/summary'),
  ]);
  state.lastData.dashboard = dashboard;
  elements.viewContent.innerHTML = [
    section(
      'Обзор платформы',
      `<div class="grid">
        ${metric('Кейсы', String(dashboard.cases?.total ?? 0))}
        ${metric('Ожидающие согласования', String(dashboard.approvals?.by_status?.pending ?? 0))}
        ${metric('Обратная связь', String(dashboard.feedback?.total ?? 0))}
        ${metric('События аудита', String(auditSummary.total ?? 0))}
        ${metric('База знаний', badge(dashboard.knowledge?.status || dashboard.knowledge?.index_manifest?.status))}
        ${metric('ReAct-вызовы ИИ', String(dashboard.tools?.count ?? 0))}
        ${metric('Интеграции', `${dashboard.integrations?.enabled_endpoint_count ?? 0}/${dashboard.integrations?.endpoint_count ?? 0}`)}
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
    section('Исходные данные панели', jsonBlock(dashboard)),
  ].join('');
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
    api('/admin/config/active/interaction_channels'),
  ];
  if (includeAudit) {
    requests.push(api('/admin/security/audit?limit=30'));
  }
  const [toolsActive, endpointsActive, n8nActive, matrixActive, resolutionActive, channelsActive, audit] = await Promise.all(requests);
  const context = {
    tools: toolsActive.payload?.tools || [],
    endpoints: endpointsActive.payload?.endpoints || [],
    workflows: n8nActive.payload?.workflows || [],
    matrices: matrixActive.payload?.matrices || [],
    resolutionProfiles: resolutionActive.payload?.profiles || [],
    channels: channelsActive.payload?.channels || [],
    audit: audit || { events: [] },
  };
  state.lastData.toolCatalog = context.tools;
  state.lastData.integrationEndpoints = context.endpoints;
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
  if (currentBinding) {
    state.operationBindingEndpointId = currentBinding?.endpoint_id || context.endpoints[0]?.endpoint_id || '';
    state.operationBindingOperationId = currentBinding.operation_id || '';
  } else if (!context.endpoints.some((endpoint) => endpoint.endpoint_id === state.operationBindingEndpointId)) {
    state.operationBindingEndpointId = context.endpoints[0]?.endpoint_id || '';
  }
  const selectedEndpoint = context.endpoints.find((endpoint) => endpoint.endpoint_id === state.operationBindingEndpointId);
  const operationIds = Object.keys(selectedEndpoint?.operations || {});
  if (!operationIds.includes(state.operationBindingOperationId)) {
    state.operationBindingOperationId = currentBinding?.operation_id && operationIds.includes(currentBinding.operation_id)
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
  const { tools, matrices, resolutionProfiles, channels } = await loadExecutionCatalogContext();
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
        channels,
      })}`,
    ),
  ].join('');
  attachCatalogSelect('toolCatalogSelect', 'toolCatalogName', renderReactCalls);
}

async function renderOperationBindings() {
  const { tools, endpoints, matrices, resolutionProfiles, channels } = await loadExecutionCatalogContext();
  const selectedTool = tools.find((tool) => tool.tool_name === state.operationBindingToolName) || null;
  elements.viewContent.innerHTML = [
    section(
      'Привязка операций',
      `${operationBindingControls(tools, selectedTool)}
      ${renderOperationBindingEditor({
        tool: selectedTool,
        tools,
        endpoints,
        matrices,
        resolutionProfiles,
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
      <button type="button" data-action="endpoint-connection-load">Загрузить</button>
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
      <button type="button" data-action="tool-catalog-load">Загрузить</button>
    </div>
    <div class="scenario-menu">
      <button type="button" class="${state.toolCatalogOperation === 'create' ? 'primary' : ''}" data-action="tool-catalog-operation" data-operation="create">Создать</button>
      <button type="button" class="${state.toolCatalogOperation === 'modify' ? 'primary' : ''}" data-action="tool-catalog-operation" data-operation="modify">Модифицировать</button>
      <button type="button" class="${state.toolCatalogOperation === 'delete' ? 'primary' : ''}" data-action="tool-catalog-operation" data-operation="delete">Удалить</button>
    </div>
  `;
}

function operationBindingControls(tools, selectedTool) {
  return `
    <div class="toolbar compact">
      <label>ReAct-вызов ИИ<select id="operationBindingToolSelect">${referenceOptions(tools, 'tool_name', state.operationBindingToolName, reactCallLabel)}</select></label>
      <button type="button" data-action="operation-binding-load">Загрузить</button>
    </div>
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

function operationSummary(endpoint) {
  const entries = Object.entries(endpoint?.operations || {});
  if (!entries.length) return 'операции не настроены';
  return entries
    .map(([operationId, operation]) => `${operationLabel(operationId, operation)}: ${operation.method} ${operation.path}`)
    .join(', ');
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

function endpointCreateTemplate(source, endpoints) {
  const template = source || endpoints[0] || {};
  return {
    endpoint_id: nextConfigItemId(template.endpoint_id || 'custom.endpoint', endpoints, 'endpoint_id'),
    adapter_type: template.adapter_type || 'mock',
    display_name: '',
    enabled: true,
    disabled_reason: '',
    base_url: template.base_url || '',
    base_url_env: template.base_url_env || '',
    auth: template.auth || { type: 'none' },
    operations: {
      custom_operation: {
        display_name: 'Новая операция',
        description: 'Опишите назначение операции.',
        method: 'POST',
        path: '/custom/operation',
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
  const operationCards = Object.entries(current.operations || {})
    .map(([operationId, operation], index) => renderEndpointOperationCard({
      endpointId: current.endpoint_id,
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
        <label>Тип адаптера<select name="adapter_type">${optionList(['mock', 'n8n_webhook', 'direct_http', 'queue'], current.adapter_type)}</select></label>
        <label>Включен<select name="enabled">${booleanOptions(current.enabled)}</select></label>
        <label>Причина отключения<input name="disabled_reason" value="${escapeHtml(current.disabled_reason || '')}" autocomplete="off"></label>
        <label>Базовый URL<input name="base_url" value="${escapeHtml(current.base_url || '')}" autocomplete="off" placeholder="http://127.0.0.1:5678/webhook"></label>
        <label>Env-переменная базового URL<input name="base_url_env" value="${escapeHtml(current.base_url_env || '')}" autocomplete="off" placeholder="N8N_WEBHOOK_BASE_URL"></label>
        <label>Тип авторизации<select name="auth_type">${optionList(['none', 'header_token', 'bearer_token'], current.auth?.type || 'none')}</select></label>
        <label>Имя заголовка<input name="auth_header_name" value="${escapeHtml(current.auth?.header_name || '')}" autocomplete="off" placeholder="X-ServiceDesk-Token"></label>
        <label>Env-переменная токена<input name="auth_token_env" value="${escapeHtml(current.auth?.token_env || '')}" autocomplete="off" placeholder="N8N_WEBHOOK_TOKEN"></label>
      </div>
      <fieldset class="launch-editor">
        <legend>Операции подключения</legend>
        <div class="meta">Операция описывает конкретный технический вызов: путь webhook, HTTP-метод, topic или тестовый ответ mock.</div>
        <div id="endpointOperationCards" class="slot-card-list">${operationCards}</div>
        <button type="button" data-action="endpoint-operation-add">Добавить операцию</button>
      </fieldset>
      ${usageListPanel('Где используется', integrationEndpointUsage(current.endpoint_id, tools, workflows), 'Не используется. Подключение можно удалить.')}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">${state.integrationEndpointOperation === 'create' ? 'Создать подключение' : 'Сохранить подключение'}</button>
      </div>
    </form>
  `;
}

function renderEndpointOperationCard({ endpointId, operationId, operation = {}, tools = [], workflows = [], open = false }) {
  const usage = integrationOperationUsage(endpointId, operationId, tools, workflows);
  return `
    <details class="slot-card" data-endpoint-operation-card${open ? ' open' : ''}>
      <summary class="slot-card-summary">
        <div class="slot-card-summary-main">
          <strong>${escapeHtml(operation.display_name || operationId || 'Новая операция')}</strong>
          <span>${escapeHtml(operationId || 'operation_id')} · ${escapeHtml(operation.method || 'POST')} ${escapeHtml(operation.path || '')}</span>
        </div>
        <button class="danger slot-delete-button" type="button" data-action="endpoint-operation-remove" ${usage.length ? 'disabled' : ''}>Удалить</button>
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
        </div>
        <label>Вход операции, JSON Schema
          <textarea name="operation_request_schema" rows="7">${escapeHtml(jsonPretty(operation.request_schema || defaultOperationRequestSchema()))}</textarea>
          <span class="field-help">Технический payload, который получит adapter. Эти параметры не редактируются в сценарии.</span>
        </label>
        <label>Тестовый ответ операции
          <textarea name="operation_mock_output" rows="5">${operation.mock_output ? escapeHtml(jsonPretty(operation.mock_output)) : ''}</textarea>
        </label>
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

function renderToolCatalogEditor({ tool, tools, matrices, resolutionProfiles, channels }) {
  if (state.toolCatalogOperation === 'delete') {
    if (!tool?.tool_name) {
      return '<div class="empty">Нет выбранного ReAct-вызова ИИ для удаления</div>';
    }
    const usage = toolUsage(tool.tool_name, matrices, resolutionProfiles, channels);
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
      ${usageListPanel('Где используется', toolUsage(current.tool_name, matrices, resolutionProfiles, channels), 'Не используется. ReAct-вызов ИИ можно удалить.')}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">${state.toolCatalogOperation === 'create' ? 'Создать ReAct-вызов ИИ' : 'Сохранить ReAct-вызов ИИ'}</button>
      </div>
    </form>
  `;
}

function selectedOperationBinding(tool) {
  return currentToolBinding(tool);
}

function renderOperationBindingEditor({ tool, endpoints, matrices, resolutionProfiles, channels }) {
  if (!tool?.tool_name) {
    return '<div class="empty">ReAct-вызов ИИ не выбран</div>';
  }
  const currentBinding = selectedOperationBinding(tool);
  const usage = toolUsage(tool.tool_name, matrices, resolutionProfiles, channels);
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
  const selectedOperation = selectedEndpoint?.operations?.[selectedOperationId] || {};
  const mappingBinding = currentBinding
    && currentBinding.endpoint_id === selectedEndpointId
    && currentBinding.operation_id === selectedOperationId
    ? currentBinding
    : {
      endpoint_id: selectedEndpointId,
      operation_id: selectedOperationId,
      parameter_mapping: defaultOperationParameterMapping(tool, selectedOperation),
    };
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
        <legend>Маппинг payload операции</legend>
        <div class="meta">Здесь технические параметры операции связываются с параметрами вызова, константами или секретами. Сценарии используют только параметры вызова.</div>
        ${renderOperationParameterMappingEditor(tool, selectedOperation, mappingBinding)}
      </fieldset>
      ${usageListPanel('Где используется ReAct-вызов ИИ', usage, 'Не используется. Привязку можно отвязать.')}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit" name="operation_binding_action" value="bind" ${!selectedEndpointId || !selectedOperationId ? 'disabled' : ''}>Привязать</button>
        <button class="danger" type="submit" name="operation_binding_action" value="unbind" ${!currentBinding || usage.length ? 'disabled' : ''}>Отвязать</button>
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

function defaultOperationParameterMapping(tool = {}, operation = {}) {
  const reactNames = new Set(reactParameterNames(tool));
  const result = {};
  for (const parameterName of operationParameterNames(operation, {})) {
    if (reactNames.has(parameterName)) {
      result[parameterName] = `react:${parameterName}`;
    }
  }
  return result;
}

function operationMappingSourceOptions(selected) {
  return [
    `<option value="" ${!selected ? 'selected' : ''}>не задано</option>`,
    ...['react', 'constant', 'secret'].map(
      (value) => `<option value="${escapeHtml(value)}" ${value === selected ? 'selected' : ''}>${escapeHtml(visibleLabels[value] || value)}</option>`,
    ),
  ].join('');
}

function reactParameterOptions(tool, selected) {
  const names = reactParameterNames(tool);
  if (!names.length) {
    return '<option value="">Нет параметров вызова</option>';
  }
  return [
    `<option value="" ${!selected ? 'selected' : ''}>выберите параметр</option>`,
    ...names.map((name) => `<option value="${escapeHtml(name)}" ${name === selected ? 'selected' : ''}>${escapeHtml(name)}</option>`),
  ].join('');
}

function renderOperationParameterMappingRow(parameterName, sourceRef, tool, operation, rowIndex) {
  const parsed = parseBindingString(sourceRef);
  const source = parsed.source || '';
  const value = parsed.value || '';
  const schema = schemaProperties(operation.request_schema || {})[parameterName] || null;
  const required = schemaRequired(operation.request_schema || {}).includes(parameterName);
  return `
    <div class="parameter-binding-row" data-operation-param-row data-required="${required ? 'true' : 'false'}">
      <input type="hidden" value="${escapeHtml(parameterName)}" data-operation-param-name>
      <div class="parameter-binding-meta">
        <strong>${escapeHtml(schemaDisplayName(parameterName, schema))}</strong>
        <span>${escapeHtml(schemaMetaLine(parameterName, schema, required, ' параметр операции'))}</span>
      </div>
      <label>Заполняется из
        <select data-operation-param-source name="operation_mapping_source_${rowIndex}">${operationMappingSourceOptions(source)}</select>
      </label>
      <label data-operation-param-react-wrap ${source === 'react' ? '' : 'hidden'}>Параметр вызова
        <select data-operation-param-react name="operation_mapping_react_${rowIndex}">${reactParameterOptions(tool, value)}</select>
      </label>
      <label data-operation-param-value-wrap ${source && source !== 'react' ? '' : 'hidden'}>Параметр или значение
        <input data-operation-param-value name="operation_mapping_value_${rowIndex}" value="${source === 'react' ? '' : escapeHtml(value)}" autocomplete="off" placeholder="${source === 'secret' ? 'ENV_NAME' : 'значение'}">
      </label>
    </div>
  `;
}

function renderOperationParameterMappingEditor(tool, operation, binding) {
  const mapping = {
    ...defaultOperationParameterMapping(tool, operation),
    ...(binding?.parameter_mapping || {}),
  };
  const names = operationParameterNames(operation, mapping);
  if (!names.length) {
    return '<div class="empty" data-operation-param-mapping>У операции нет описанных входных параметров.</div>';
  }
  const missingRequired = schemaRequired(operation.request_schema || {})
    .filter((parameterName) => !mapping[parameterName]);
  return `
    <div class="parameter-binding-list" data-operation-param-mapping>
      <div class="parameter-binding-header">
        <span>Параметр endpoint-операции</span>
        <span>Заполняется из</span>
        <span>Параметр или значение</span>
      </div>
      ${names.map((name, index) => renderOperationParameterMappingRow(
        name,
        mapping[name] || '',
        tool,
        operation,
        index,
      )).join('')}
      ${missingRequired.length
        ? `<div class="field-help">Не заполнены обязательные параметры операции: ${escapeHtml(missingRequired.join(', '))}</div>`
        : ''}
    </div>
  `;
}

function toolUsage(toolName, matrices, resolutionProfiles, channels) {
  const refs = [];
  for (const matrix of matrices || []) {
    for (const launch of matrix.launches || []) {
      if (launch.tool_name === toolName) {
        refs.push(`Матрица "${matrix.display_name || matrix.matrix_id}", запуск "${launch.launch_id}"`);
      }
    }
  }
  for (const profile of resolutionProfiles || []) {
    const source = profile.candidate_source || {};
    if (source.source_type === 'react_call' && source.tool_name === toolName) {
      refs.push(`Профиль разрешения "${profile.display_name || profile.profile_id}", операция разрешения`);
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

function toolBindingUsage(toolName, endpointId, operationId, matrices, resolutionProfiles, channels) {
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
    const source = profile.candidate_source || {};
    if (
      source.source_type === 'react_call'
      && source.tool_name === toolName
      && source.endpoint_id === endpointId
      && source.operation_id === operationId
    ) {
      refs.push(`Профиль разрешения "${profile.display_name || profile.profile_id}", операция разрешения`);
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

async function saveIntegrationEndpointForm(form) {
  const data = new FormData(form);
  const endpoint = {
    endpoint_id: String(data.get('endpoint_id') || '').trim(),
    adapter_type: String(data.get('adapter_type') || '').trim(),
    display_name: String(data.get('display_name') || '').trim(),
    enabled: parseBoolean(data.get('enabled')),
    operations: parseEndpointOperationCards(form),
  };
  const disabledReason = String(data.get('disabled_reason') || '').trim();
  const baseUrl = String(data.get('base_url') || '').trim();
  const baseUrlEnv = String(data.get('base_url_env') || '').trim();
  const authType = String(data.get('auth_type') || 'none').trim();
  const authHeaderName = String(data.get('auth_header_name') || '').trim();
  const authTokenEnv = String(data.get('auth_token_env') || '').trim();
  if (disabledReason) endpoint.disabled_reason = disabledReason;
  if (baseUrl) endpoint.base_url = baseUrl;
  if (baseUrlEnv) endpoint.base_url_env = baseUrlEnv;
  endpoint.auth = { type: authType };
  if (authHeaderName) endpoint.auth.header_name = authHeaderName;
  if (authTokenEnv) endpoint.auth.token_env = authTokenEnv;
  await applyIntegrationEndpointMutation(state.integrationEndpointOperation, endpoint);
}

async function deleteIntegrationEndpointForm() {
  if (!state.integrationEndpointId) {
    throw new Error('Подключение для удаления не выбрано.');
  }
  await applyIntegrationEndpointMutation('delete', { endpoint_id: state.integrationEndpointId });
}

function parseEndpointOperationCards(form) {
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
      request_schema: parseJsonField(value('operation_request_schema') || jsonPretty(defaultOperationRequestSchema()), `Вход операции ${operationId}`),
      timeout_seconds: parseInt(value('operation_timeout_seconds'), 10),
    };
    if (!operation.display_name || !operation.description || !operation.method || !operation.path) {
      throw new Error(`Операция ${operationId} должна иметь название, описание, метод и path.`);
    }
    const mockOutput = value('operation_mock_output');
    if (mockOutput) {
      operation.mock_output = parseJsonField(mockOutput, `Ответ mock операции ${operationId}`);
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
  const binding = operation === 'unbind'
    ? {}
    : {
      endpoint_id: String(data.get('binding_endpoint_id') || '').trim(),
      operation_id: String(data.get('binding_operation_id') || '').trim(),
      parameter_mapping: parseOperationParameterMapping(form),
    };
  await applyOperationBindingMutation({
    operation,
    toolName: state.operationBindingToolName,
    binding,
  });
}

function parseOperationParameterMapping(form) {
  const mapping = {};
  const rows = Array.from(form.querySelectorAll('[data-operation-param-row]'));
  for (const row of rows) {
    const parameterName = row.querySelector('[data-operation-param-name]')?.value?.trim() || '';
    const required = row.dataset.required === 'true';
    const source = row.querySelector('[data-operation-param-source]')?.value?.trim() || '';
    const value = source === 'react'
      ? row.querySelector('[data-operation-param-react]')?.value?.trim() || ''
      : row.querySelector('[data-operation-param-value]')?.value?.trim() || '';
    if (!parameterName) continue;
    if (!source || !value) {
      if (required) {
        throw new Error(`Обязательный параметр операции ${parameterName} должен иметь источник значения.`);
      }
      continue;
    }
    if (!['react', 'constant', 'secret'].includes(source)) {
      throw new Error(`Параметр операции ${parameterName} имеет неизвестный источник: ${source}.`);
    }
    mapping[parameterName] = `${source}:${value}`;
  }
  return mapping;
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
    tags: String(data.get('tags') || '')
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean),
  });
  const confidenceOverrides = parseConfidenceThresholdsFromForm(data, 'scenario_confidence');
  if (Object.keys(confidenceOverrides).length) {
    scenario.confidence_overrides = confidenceOverrides;
  }
  await applyScenarioMutation(state.scenarioOperation, scenario);
}

async function deleteScenarioForm() {
  if (!state.scenarioId) {
    throw new Error('Сценарий для удаления не выбран.');
  }
  await applyScenarioMutation('delete', { scenario_id: state.scenarioId });
}

async function saveSlotSchemaForm(form) {
  const data = new FormData(form);
  const slots = parseSlotCards(form);
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
    timeouts: {
      reminder_after_seconds: parseInt(data.get('reminder_after_seconds'), 10),
      draft_after_seconds: parseInt(data.get('draft_after_seconds'), 10),
    },
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
    } else if (slot.fill_method === 'resolution_profile') {
      slot.resolution_profile_id = value('resolution_profile_id');
      const fallbackQuestion = value('fallback_question');
      if (fallbackQuestion) slot.fallback_question = fallbackQuestion;
    } else if (slot.fill_method === 'operator_manual') {
      slot.operator_hint = value('operator_hint');
    }
    const confidenceOverrides = parseConfidenceThresholdsFromCard(card, 'slot_confidence');
    if (Object.keys(confidenceOverrides).length) {
      slot.confidence_overrides = confidenceOverrides;
    }
    return slot;
  });
  const emptySlot = slots.find((slot) => !slot.slot_id || !slot.display_name || !slot.priority_group || !slot.fill_method);
  if (emptySlot) {
    throw new Error('Каждый слот должен иметь ключ, название, priority group и способ заполнения.');
  }
  const missingProfile = slots.find((slot) => slot.fill_method === 'resolution_profile' && !slot.resolution_profile_id);
  if (missingProfile) {
    throw new Error(`Для слота ${missingProfile.slot_id} выберите профиль разрешения атрибута.`);
  }
  const missingUserQuestion = slots.find((slot) => slot.fill_method === 'user_question' && !slot.user_question);
  if (missingUserQuestion) {
    throw new Error(`Для слота ${missingUserQuestion.slot_id} заполните вопрос пользователю.`);
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
    return profile && !profile.output_slots?.includes(slot.slot_id);
  });
  if (mismatchedProfile) {
    const profile = profileById[mismatchedProfile.resolution_profile_id];
    throw new Error(
      `Профиль "${profile.display_name}" не заполняет слот ${mismatchedProfile.slot_id}. `
      + `Доступные выходные слоты профиля: ${formatList(profile.output_slots)}.`,
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
      keywords: parseCsv(data.get('keywords')),
      negative_keywords: parseCsv(data.get('negative_keywords')),
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
      audit_required: parseBoolean(value('audit_required')),
      log_required: parseBoolean(value('log_required')),
      stop_on_error: parseBoolean(value('stop_on_error')),
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
      requires_user_confirmation: parseBoolean(data.get('requires_user_confirmation')),
    },
    waiting: {
      pause_sla: parseBoolean(data.get('pause_sla')),
      auto_close_after_hours: parseInt(data.get('auto_close_after_hours'), 10),
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
    },
    incomplete_discussion_action: parseChannelAction(data, 'incomplete_discussion_action'),
    escalation_action: parseChannelAction(data, 'escalation_action'),
    action_profiles: parseChannelProfileCards(form),
    audit_required: parseBoolean(data.get('audit_required')),
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
  const [toolName, endpointId, operationId] = String(data.get('candidate_binding') || '').split('::');
  const clarificationQuestion = String(data.get('clarification_question') || '').trim();
  const profile = {
    profile_id: String(data.get('profile_id') || '').trim(),
    display_name: String(data.get('display_name') || '').trim(),
    status: String(data.get('status') || '').trim(),
    description: String(data.get('description') || '').trim(),
    target_slot_id: String(data.get('target_slot_id') || '').trim(),
    output_slots: parseCsv(data.get('output_slots')),
    input_attributes: buildResolutionInputAttributes(data),
    candidate_source: {
      source_type: String(data.get('candidate_source_type') || 'disabled').trim(),
      parameter_mapping: parseCandidateParameterMapping(form),
    },
    result_policy: {
      result_type: String(data.get('result_type') || 'list').trim(),
      target_value_path: String(data.get('result_target_value_path') || '').trim(),
      output_mapping: parseKeyValueLines(data.get('result_output_mapping'), 'Дополнительные выходные слоты'),
    },
    decision_policy: {
      empty_result: String(data.get('decision_empty_result') || defaultResolutionDecisionPolicy.empty_result).trim(),
      single_result: String(data.get('decision_single_result') || defaultResolutionDecisionPolicy.single_result).trim(),
      multiple_results: String(data.get('decision_multiple_results') || defaultResolutionDecisionPolicy.multiple_results).trim(),
      source_error: String(data.get('decision_source_error') || defaultResolutionDecisionPolicy.source_error).trim(),
      attempt_limit: String(data.get('decision_attempt_limit') || defaultResolutionDecisionPolicy.attempt_limit).trim(),
    },
    clarification_policy: {
      question: clarificationQuestion,
      ask_for_attributes: parseCsv(data.get('clarification_ask_for_attributes')),
    },
    handoff_policy: {
      action: String(data.get('handoff_action') || 'operator_handoff').trim(),
      package: parseCsv(data.get('handoff_package')),
    },
    fallback: {
      action: String(data.get('fallback_action') || '').trim(),
      question: clarificationQuestion,
    },
    max_attempts: parseInt(data.get('max_attempts'), 10),
    audit_required: parseBoolean(data.get('audit_required')),
    log_required: parseBoolean(data.get('log_required')),
  };
  if (toolName && endpointId && operationId) {
    profile.candidate_source.tool_name = toolName;
    profile.candidate_source.endpoint_id = endpointId;
    profile.candidate_source.operation_id = operationId;
  }
  if (profile.candidate_source.source_type === 'ticket_history') {
    profile.candidate_source.history_filter = parseJsonField(data.get('history_filter_json') || '{}', 'Фильтр истории заявок');
  }
  const listPath = String(data.get('result_list_path') || '').trim();
  const objectPath = String(data.get('result_object_path') || '').trim();
  const successPath = String(data.get('result_success_path') || '').trim();
  const confidencePath = String(data.get('result_confidence_path') || '').trim();
  const displayValuePath = String(data.get('result_display_value_path') || '').trim();
  if (listPath) {
    profile.result_policy.list_path = listPath;
  }
  if (objectPath) {
    profile.result_policy.object_path = objectPath;
  }
  if (successPath) {
    profile.result_policy.success_path = successPath;
  }
  if (confidencePath) {
    profile.result_policy.confidence_path = confidencePath;
  }
  if (displayValuePath) {
    profile.result_policy.display_value_path = displayValuePath;
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
  const [active, matrixActive, resolutionActive, channelsActive] = await Promise.all([
    api('/admin/config/active/tools'),
    api('/admin/config/active/tool_launch_matrix'),
    api('/admin/config/active/attribute_resolution_profiles'),
    api('/admin/config/active/interaction_channels'),
  ]);
  const payload = JSON.parse(JSON.stringify(active.payload));
  const tools = payload.tools || [];
  const toolName = tool.tool_name;
  const index = tools.findIndex((item) => item.tool_name === toolName);
  const matrices = matrixActive.payload?.matrices || [];
  const resolutionProfiles = resolutionActive.payload?.profiles || [];
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
    const usage = toolUsage(toolName, matrices, resolutionProfiles, channels);
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
  const [active, matrixActive, resolutionActive, channelsActive] = await Promise.all([
    api('/admin/config/active/tools'),
    api('/admin/config/active/tool_launch_matrix'),
    api('/admin/config/active/attribute_resolution_profiles'),
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
  const channels = channelsActive.payload?.channels || [];
  let nextBinding = null;

  if (operation === 'bind') {
    if (!binding.endpoint_id || !binding.operation_id) {
      throw new Error('Для привязки выберите подключение и операцию.');
    }
    nextBinding = {
      endpoint_id: binding.endpoint_id,
      operation_id: binding.operation_id,
      parameter_mapping: binding.parameter_mapping || {},
    };
    tool.endpoint_bindings = [nextBinding];
  } else if (operation === 'unbind') {
    if (!currentBinding) {
      throw new Error('У ReAct-вызова ИИ нет текущей привязки операции.');
    }
    const usage = toolUsage(toolName, matrices, resolutionProfiles, channels);
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

async function updateOperationBindingReferences(toolName, binding) {
  if (!binding) return;
  const [matrixActive, resolutionActive, channelsActive] = await Promise.all([
    api('/admin/config/active/tool_launch_matrix'),
    api('/admin/config/active/attribute_resolution_profiles'),
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

  const resolutionPayload = JSON.parse(JSON.stringify(resolutionActive.payload));
  let resolutionChanged = false;
  for (const profile of resolutionPayload.profiles || []) {
    const source = profile.candidate_source || {};
    if (source.source_type === 'react_call' && source.tool_name === toolName) {
      source.endpoint_id = binding.endpoint_id;
      source.operation_id = binding.operation_id;
      resolutionChanged = true;
    }
  }
  if (resolutionChanged) {
    await activateConfigPayload('attribute_resolution_profiles', resolutionPayload, resolutionActive.active_version_id);
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

function buildResolutionInputAttributes(data) {
  const attributes = [];
  const seen = new Set();
  const pushAttribute = (attributeId, source, extra = {}) => {
    if (!attributeId || seen.has(attributeId)) return;
    seen.add(attributeId);
    attributes.push({
      attribute_id: attributeId,
      display_name: humanizeTechnicalKey(attributeId),
      source,
      required: source === 'slot',
      ...extra,
    });
  };
  for (const attributeId of parseCsv(data.get('llm_attributes'))) {
    pushAttribute(attributeId, 'llm', {
      extraction_instruction: `Извлеки ${humanizeTechnicalKey(attributeId)} из текста обращения.`,
    });
  }
  for (const attributeId of parseCsv(data.get('slot_attributes'))) {
    pushAttribute(attributeId, 'slot', { source_ref: attributeId });
  }
  for (const attributeId of parseCsv(data.get('operator_attributes'))) {
    pushAttribute(attributeId, 'operator_answer');
  }
  if (!attributes.length) {
    throw new Error('Профиль должен содержать хотя бы один признак для поиска.');
  }
  return attributes;
}

function parseCandidateParameterMapping(form) {
  const mapping = {};
  form.querySelectorAll('[data-candidate-param-row]').forEach((row) => {
    const parameterName = row.querySelector('[data-candidate-param-name]')?.value?.trim();
    const sourceRef = row.querySelector('[data-candidate-param-source]')?.value?.trim();
    if (parameterName && sourceRef) {
      mapping[parameterName] = sourceRef;
    }
  });
  return mapping;
}

function parseKeyValueLines(value, label) {
  const result = {};
  const items = String(value || '')
    .split(/\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
  for (const item of items) {
    const separatorIndex = item.indexOf('=');
    if (separatorIndex < 1) {
      throw new Error(`${label}: используйте формат параметр=источник.`);
    }
    const key = item.slice(0, separatorIndex).trim();
    const itemValue = item.slice(separatorIndex + 1).trim();
    if (!key || !itemValue) {
      throw new Error(`${label}: параметр и источник не должны быть пустыми.`);
    }
    result[key] = itemValue;
  }
  return result;
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
  ).trim();
  container.appendChild(wrapper.firstElementChild);
  syncSlotCardFillMethod(container.lastElementChild);
}

function syncAllSlotCardFillMethods() {
  document.querySelectorAll('[data-slot-card]').forEach(syncSlotCardFillMethod);
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
      audit_required: true,
      log_required: true,
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
  const reactWrap = row.querySelector('[data-operation-param-react-wrap]');
  const valueWrap = row.querySelector('[data-operation-param-value-wrap]');
  if (reactWrap) {
    reactWrap.hidden = source !== 'react';
  }
  if (valueWrap) {
    valueWrap.hidden = !source || source === 'react';
  }
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
      : 'У выбранного ReAct-вызова ИИ нет привязки операции. Настройте ее в меню "Привязка операций".';
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
    operationId,
    operation: {
      display_name: 'Новая операция',
      description: 'Опишите назначение операции.',
      method: 'POST',
      path: '/custom/operation',
      request_schema: defaultOperationRequestSchema(),
      timeout_seconds: 10,
    },
    tools: state.lastData.toolCatalog || [],
    workflows: [],
    open: true,
  }).trim();
  container.appendChild(wrapper.firstElementChild);
}

function removeEndpointOperationCard(target) {
  const card = target.closest('[data-endpoint-operation-card]');
  if (!card || target.disabled) return;
  card.remove();
}

function syncOperationBindingOperationOptions(form) {
  if (!form) return;
  const endpoints = state.lastData.integrationEndpoints || [];
  const endpointSelect = form.querySelector('[data-operation-binding-endpoint]');
  const operationSelect = form.querySelector('[data-operation-binding-operation]');
  if (!endpointSelect || !operationSelect) return;
  const endpoint = endpoints.find((item) => item.endpoint_id === endpointSelect.value) || null;
  state.operationBindingEndpointId = endpointSelect.value;
  operationSelect.innerHTML = operationOptionsForEndpoint(endpoint, operationSelect.value);
  state.operationBindingOperationId = operationSelect.value;
}

function addChannelProfileCard() {
  const container = document.getElementById('channelProfileCards');
  if (!container) return;
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
      action_type: 'debug_stop',
      message_template: 'Остановить сценарий и показать сообщение оператору.',
    },
  }).trim();
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
      || action === 'model-provider-remove'
      || action === 'channel-profile-remove'
      || action === 'endpoint-operation-remove'
    ) {
      event.preventDefault();
      event.stopPropagation();
    }
    target.disabled = true;
    try {
      if (action === 'knowledge-rebuild') {
        await rebuildKnowledge();
      } else if (action === 'promote-feedback') {
        await promoteFeedback();
      } else if (action === 'run-evaluation') {
        await runEvaluation();
      } else if (action === 'scenario-load') {
        await renderView(state.activeView);
      } else if (action === 'scenario-operation') {
        state.scenarioOperation = target.dataset.operation;
        await renderScenarios();
      } else if (action === 'slot-schema-load') {
        await renderScenarioSlots();
      } else if (action === 'slot-schema-operation') {
        state.slotSchemaOperation = target.dataset.operation;
        await renderScenarioSlots();
      } else if (action === 'route-load') {
        await renderScenarioClassification();
      } else if (action === 'route-operation') {
        state.routeOperation = target.dataset.operation;
        await renderScenarioClassification();
      } else if (action === 'policy-load') {
        await renderScenarioReact();
      } else if (action === 'policy-operation') {
        state.policyOperation = target.dataset.operation;
        await renderScenarioReact();
      } else if (action === 'tool-matrix-load') {
        await renderScenarioTools();
      } else if (action === 'tool-matrix-operation') {
        state.toolMatrixOperation = target.dataset.operation;
        await renderScenarioTools();
      } else if (action === 'escalation-load') {
        await renderScenarioEscalation();
      } else if (action === 'escalation-operation') {
        state.escalationOperation = target.dataset.operation;
        await renderScenarioEscalation();
      } else if (action === 'prompt-pack-load') {
        await renderScenarioPrompts();
      } else if (action === 'prompt-pack-operation') {
        state.promptPackOperation = target.dataset.operation;
        await renderScenarioPrompts();
      } else if (action === 'interaction-channel-load') {
        await renderInteractionChannels();
      } else if (action === 'interaction-channel-operation') {
        state.interactionChannelOperation = target.dataset.operation;
        await renderInteractionChannels();
      } else if (action === 'resolution-load') {
        await renderResolutionProfiles();
      } else if (action === 'resolution-operation') {
        state.resolutionOperation = target.dataset.operation;
        await renderResolutionProfiles();
      } else if (action === 'endpoint-connection-load') {
        await renderIntegrations();
      } else if (action === 'endpoint-connection-operation') {
        state.integrationEndpointOperation = target.dataset.operation;
        await renderIntegrations();
      } else if (action === 'tool-catalog-load') {
        await renderReactCalls();
      } else if (action === 'tool-catalog-operation') {
        state.toolCatalogOperation = target.dataset.operation;
        await renderReactCalls();
      } else if (action === 'operation-binding-load') {
        await renderOperationBindings();
      } else if (action === 'model-provider-switch') {
        await switchModelProvider(target.dataset.provider);
      } else if (action === 'model-provider-add') {
        addModelProviderCard();
      } else if (action === 'model-provider-remove') {
        removeModelProviderCard(target);
      } else if (action === 'slot-add') {
        addSlotCard();
      } else if (action === 'slot-remove') {
        removeSlotCard(target);
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
      }
    } catch (error) {
      setNotice(error.message || String(error), 'error');
    } finally {
      target.disabled = false;
    }
  });

  document.addEventListener('change', async (event) => {
    const target = event.target;
    if (target?.matches?.('[data-binding-source], [data-binding-slot-select]')) {
      syncParameterBindingRow(target.closest('[data-param-binding-row]'));
      return;
    }
    if (target?.matches?.('[data-operation-param-source]')) {
      syncOperationParameterMappingRow(target.closest('[data-operation-param-row]'));
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
    if (target?.matches?.('[data-slot-fill-method]')) {
      syncSlotCardFillMethod(target.closest('[data-slot-card]'));
      return;
    }
    if (!target?.matches?.('[data-launch-tool]')) {
      return;
    }
    syncLaunchSelectors(target.closest('[data-launch-card]'));
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
