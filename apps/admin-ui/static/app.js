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
  resolutionProfileId: 'profile.password_reset.login_from_ad',
  resolutionOperation: 'modify',
  modelRoutingBaseVersionId: '',
  lastData: {},
};

const viewTitles = {
  dashboard: 'Панель обзора',
  scenarios: 'Сценарии',
  scenarioSlots: '1. Слоты',
  scenarioClassification: '2. Классификация и маршрут',
  scenarioReact: '3. ReAct-планирование',
  scenarioTools: '4. Инструменты и матрица запуска',
  scenarioEscalation: '5. Решение и эскалация',
  scenarioPrompts: '6. Промпты',
  resolution: '0. Разрешение атрибутов',
  knowledge: 'База знаний',
  tools: 'Инструменты и интеграции',
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
  case: 'текущий кейс',
  llm_extraction: 'извлечение моделью',
  leave_empty: 'оставить пустым',
  auto_agent: 'автоагент',
  agent_l1: 'агент + Л1',
  l1_hint: 'Л1 + подсказка',
  l2_major_incident: 'Л2 + Major Incident',
  approver: 'согласующий',
  operator_manual: 'ручное заполнение оператором',
  resolution_pending: 'ожидает разрешения',
  resolution_profile: 'профиль разрешения',
  user_question: 'вопрос пользователю',
  llm_extract: 'извлечение из текста моделью',
  rag_search: 'поиск в базе знаний',
  case_read: 'чтение из текущего кейса',
  tool_call: 'вызов инструмента',
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
  vllm_cpu: 'vLLM CPU',
  openai: 'OpenAI API',
  litellm: 'LiteLLM',
  p1: 'P1',
  p2: 'P2',
  p3: 'P3',
  p4: 'P4',
};

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
  } else if (view === 'resolution') {
    await renderResolutionProfiles();
  } else if (view === 'knowledge') {
    await renderKnowledge();
  } else if (view === 'tools') {
    await renderTools();
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
      '1. Слоты',
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

async function renderScenarioTools() {
  const [active, scenariosConfig] = await Promise.all([
    api('/admin/config/active/tool_launch_matrix'),
    api('/admin/config/active/service_scenarios'),
  ]);
  const matrices = active.payload?.matrices || [];
  const scenarios = scenariosConfig.payload?.scenarios || [];
  if (!matrices.some((matrix) => matrix.matrix_id === state.toolMatrixId)) {
    state.toolMatrixId = matrices[0]?.matrix_id || '';
  }
  const selected = matrices.find((matrix) => matrix.matrix_id === state.toolMatrixId) || null;
  elements.viewContent.innerHTML = [
    section(
      '4. Инструменты и матрица запуска',
      `${blockCatalogControls({
        selectId: 'toolMatrixSelect',
        label: 'Матрица инструментов',
        items: matrices,
        idKey: 'matrix_id',
        selectedId: state.toolMatrixId,
        labelKey: 'display_name',
        actionPrefix: 'tool-matrix',
        operation: state.toolMatrixOperation,
      })}
      ${renderToolLaunchEditor({ matrix: selected, matrices, scenarios })}`,
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

function renderScenarioEditor({
  detail,
  serviceScenarios,
  slotSchemas,
  routes,
  policies,
  toolMatrices,
  promptPacks,
  escalationPolicies,
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
          <div class="meta">Будет удалена запись сценария из домена service_scenarios. Связанные слоты, маршруты, prompt pack и матрица инструментов остаются в своих доменах для повторного использования или отдельной очистки.</div>
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
        <label>Матрица инструментов<select name="tool_launch_matrix_id">${referenceOptions(toolMatrices, 'matrix_id', scenario.tool_launch_matrix_id, 'display_name')}</select></label>
        <label>Пакет промптов
          <select name="prompt_pack_id">${referenceOptions(promptPacks, 'prompt_pack_id', scenario.prompt_pack_id, (pack) => promptPackLabel(pack))}</select>
          <span class="field-help">Связь сценария с пакетом. Содержимое обязательных блоков редактируется в меню "Сценарии обработки -> 6. Промпты".</span>
        </label>
        <label>Политика эскалации<select name="escalation_policy_id">${referenceOptions(escalationPolicies, 'policy_id', scenario.escalation_policy_id, 'display_name')}</select></label>
      </div>
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">${state.scenarioOperation === 'create' ? 'Создать сценарий' : 'Сохранить изменения'}</button>
      </div>
    </form>
  `;
}

async function renderResolutionProfiles() {
  const [active, slotSchemasConfig, scenariosConfig] = await Promise.all([
    api('/admin/config/active/attribute_resolution_profiles'),
    api('/admin/config/active/slot_schemas'),
    api('/admin/config/active/service_scenarios'),
  ]);
  const profiles = active.payload?.profiles || [];
  const slotSchemas = slotSchemasConfig.payload?.slot_schemas || [];
  const scenarios = scenariosConfig.payload?.scenarios || [];
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
        "Сценарии обработки -> 1. Слоты", раскройте нужный слот, выберите "Способ заполнения = профиль разрешения"
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

function renderResolutionProfileEditor({ profile, profiles, slotSchemas = [], scenarios = [] }) {
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
  const fallbackOptions = ['ask_user', 'operator_handoff', 'escalate', 'leave_empty']
    .map((value) => `<option value="${value}" ${current.fallback?.action === value ? 'selected' : ''}>${escapeHtml(visibleLabels[value] || value)}</option>`)
    .join('');
  const ambiguityAction = current.ambiguity_policy?.action || 'clarification';
  const ambiguityOptions = ['clarification', 'operator_handoff', 'escalate', 'leave_empty']
    .map((value) => `<option value="${value}" ${ambiguityAction === value ? 'selected' : ''}>${escapeHtml(visibleLabels[value] || value)}</option>`)
    .join('');
  const stepCards = (current.steps || [])
    .map((step, index) => renderResolutionStepCard(step, index + 1, false))
    .join('');
  return `
    <form class="scenario-editor panel" data-form="resolution-profile-editor">
      <input type="hidden" name="profile_id" value="${escapeHtml(current.profile_id || '')}">
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
        <label>Режим выполнения
          <select name="resolution_mode">${optionList(['sequential', 'branching'], current.resolution_mode || 'sequential')}</select>
          <span class="field-help">Последовательный режим идет по шагам подряд. Режим с ветвлениями использует переходы успеха, ошибки и неоднозначности.</span>
        </label>
        <label>Лимит попыток действует
          <select name="attempt_scope">${optionList(['profile', 'step'], current.attempt_scope || 'profile')}</select>
          <span class="field-help">На весь профиль или отдельно на каждый шаг, который может повторяться после уточнения.</span>
        </label>
        <label>Входные слоты
          <input name="input_slots" value="${escapeHtml(csv(current.input_slots))}" autocomplete="off" placeholder="user_login">
          <span class="field-help">Слоты сценария, которые нужны до запуска профиля. Промежуточные атрибуты описываются внутри шагов.</span>
        </label>
        <label>Выходные слоты
          <input name="output_slots" value="${escapeHtml(csv(current.output_slots))}" autocomplete="off" placeholder="user_login, user_id">
          <span class="field-help">Слоты сценария, которые профиль может заполнить.</span>
        </label>
        <label>Промежуточные атрибуты
          <input name="intermediate_attributes" value="${escapeHtml(csv(current.intermediate_attributes))}" autocomplete="off" placeholder="last_name, ad_candidates">
          <span class="field-help">Внутренние данные mini-workflow: ФИО, кандидаты AD, признаки из истории. Они не обязаны быть слотами сценария.</span>
        </label>
        <label>Порог уверенности
          <input name="confidence_threshold" type="number" min="0" max="1" step="0.01" value="${escapeHtml(current.confidence_threshold ?? 0.7)}">
          <span class="field-help">Базовый порог, если отдельные пороги ниже не заполнены.</span>
        </label>
        <label>Автозаполнение от
          <input name="confidence_auto_fill" type="number" min="0" max="1" step="0.01" value="${escapeHtml(current.confidence_thresholds?.auto_fill ?? current.confidence_threshold ?? 0.7)}">
        </label>
        <label>Уточнение ниже
          <input name="confidence_clarification" type="number" min="0" max="1" step="0.01" value="${escapeHtml(current.confidence_thresholds?.clarification ?? current.confidence_threshold ?? 0.7)}">
        </label>
        <label>Передача Л1 ниже
          <input name="confidence_operator_handoff" type="number" min="0" max="1" step="0.01" value="${escapeHtml(current.confidence_thresholds?.operator_handoff ?? 0.5)}">
        </label>
        <label>Лимит попыток
          <input name="max_attempts" type="number" min="1" max="10" value="${escapeHtml(current.max_attempts || 1)}">
        </label>
        <label>Fallback<select name="fallback_action">${fallbackOptions}</select></label>
        <label>Audit<select name="audit_required">${booleanOptions(current.audit_required)}</select></label>
        <label>Log<select name="log_required">${booleanOptions(current.log_required)}</select></label>
      </div>
      <fieldset class="launch-editor">
        <legend>Политика неоднозначности</legend>
        <div class="grid two">
          <label>Действие
            <select name="ambiguity_action">${ambiguityOptions}</select>
            <span class="field-help">Что делать, если найдено несколько кандидатов или уверенность недостаточна.</span>
          </label>
          <label>Атрибут со списком кандидатов
            <input name="ambiguity_candidate_count_attribute" value="${escapeHtml(current.ambiguity_policy?.candidate_count_attribute || '')}" autocomplete="off" placeholder="ad_candidates">
            <span class="field-help">Например, список пользователей из AD, по которому видно 0, 1 или несколько совпадений.</span>
          </label>
          <label>Уточняемые атрибуты
            <input name="ambiguity_ask_for_attributes" value="${escapeHtml(csv(current.ambiguity_policy?.ask_for_attributes))}" autocomplete="off" placeholder="department, employee_number">
            <span class="field-help">Какие данные попросить у пользователя или оператора для следующей попытки.</span>
          </label>
          <label>Пакет передачи Л1
            <input name="operator_handoff_package" value="${escapeHtml(csv(current.operator_handoff_package))}" autocomplete="off" placeholder="last_name, ad_candidates">
            <span class="field-help">Какие собранные слоты и промежуточные атрибуты передать сотруднику при ручной обработке.</span>
          </label>
        </div>
        <label>Вопрос при неоднозначности
          <textarea name="ambiguity_question" rows="2">${escapeHtml(current.ambiguity_policy?.question || '')}</textarea>
        </label>
      </fieldset>
      <label>Fallback-вопрос<textarea name="fallback_question" rows="2">${escapeHtml(current.fallback?.question || '')}</textarea></label>
      <div class="slot-schema-derived">
        <div class="metric-label">Шаги разрешения атрибута</div>
        <div class="meta">Опишите mini-workflow заполнения слота: извлечение из текста и RAG, проверка через tools, условия, уточнение, повторная попытка, заполнение слота или передача Л1.</div>
      </div>
      <div id="resolutionStepCards" class="slot-card-list">${stepCards}</div>
      <button type="button" data-action="resolution-step-add">Добавить шаг</button>
      ${resolutionProfileUsagePanel(slotSchemas, scenarios, current.profile_id)}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">${state.resolutionOperation === 'create' ? 'Создать профиль' : 'Сохранить профиль'}</button>
      </div>
    </form>
  `;
}

function renderResolutionStepCard(step = {}, order = 1, open = false) {
  const type = step.type || 'clarification';
  const title = step.display_name || `Шаг ${order}`;
  const keyLabel = step.step_id || `step_${order}`;
  const history = step.history_filter || {};
  const openAttribute = open ? ' open' : '';
  return `
    <details class="slot-card" data-resolution-step-card${openAttribute}>
      <summary class="slot-card-summary">
        <div class="slot-card-summary-main">
          <strong>${escapeHtml(title)}</strong>
          <span>${escapeHtml(keyLabel)} · ${escapeHtml(visibleLabels[type] || type)}</span>
        </div>
        <button class="danger slot-delete-button" type="button" data-action="resolution-step-remove">Удалить</button>
      </summary>
      <div class="slot-card-body">
        <div class="slot-card-note">
          <div class="metric-label">Настройка шага профиля</div>
          <div class="meta">Шаги выполняются сверху вниз или по переходам. Для mini-workflow можно отдельно задать путь успеха, ошибки и неоднозначного результата.</div>
        </div>
        <div class="grid two">
          <label>Ключ шага
            <input name="step_id" value="${escapeHtml(step.step_id || `step_${order}`)}" autocomplete="off" placeholder="search_ad_user">
            <span class="field-help">Служебное имя шага для переходов внутри профиля. Используйте латиницу, цифры, _, -, .</span>
          </label>
          <label>Тип шага
            <select name="type">${resolutionStepTypeOptions(type)}</select>
            <span class="field-help">Определяет, что делает шаг: извлекает данные, вызывает tool, проверяет условие, задает вопрос или заполняет слот.</span>
          </label>
          <label>Название
            <input name="display_name" value="${escapeHtml(step.display_name || '')}" autocomplete="off" placeholder="Найти пользователя в Active Directory">
            <span class="field-help">Понятное имя для администратора, оператора и аудита.</span>
          </label>
          <label>Входные атрибуты
            <input name="inputs" value="${escapeHtml(csv(step.inputs))}" autocomplete="off" placeholder="last_name, first_name">
            <span class="field-help">Какие слоты или промежуточные атрибуты должны быть известны перед этим шагом.</span>
          </label>
          <label>Выходные атрибуты
            <input name="outputs" value="${escapeHtml(csv(step.outputs))}" autocomplete="off" placeholder="ad_candidates, user_login">
            <span class="field-help">Какие атрибуты или слоты может заполнить шаг.</span>
          </label>
          <label>Инструмент
            <input name="tool_name" value="${escapeHtml(step.tool_name || '')}" autocomplete="off" placeholder="search_ad_users">
            <span class="field-help">Нужен для типа "вызов инструмента". Это имя tool из каталога исполнения.</span>
          </label>
          <label>Профиль точки интеграции
            <input name="endpoint_profile" value="${escapeHtml(step.endpoint_profile || '')}" autocomplete="off" placeholder="mock">
            <span class="field-help">Какой профиль endpoint использовать для выбранного инструмента: mock, n8n, identity и т.п.</span>
          </label>
          <label>Операция
            <input name="operation_id" value="${escapeHtml(step.operation_id || '')}" autocomplete="off" placeholder="search_ad_users">
            <span class="field-help">Конкретная операция endpoint, которую выполнит tool adapter.</span>
          </label>
          <label>Следующий шаг при успехе
            <input name="on_success_step" value="${escapeHtml(step.on_success_step || '')}" autocomplete="off" placeholder="fill_login">
            <span class="field-help">Оставьте пустым, если после успеха нужен следующий шаг по порядку или завершение.</span>
          </label>
          <label>Следующий шаг при ошибке
            <input name="on_failure_step" value="${escapeHtml(step.on_failure_step || '')}" autocomplete="off" placeholder="ask_identity_hint">
            <span class="field-help">Куда перейти при технической ошибке или отсутствии результата.</span>
          </label>
          <label>Следующий шаг при неоднозначности
            <input name="on_ambiguous_step" value="${escapeHtml(step.on_ambiguous_step || '')}" autocomplete="off" placeholder="ask_identity_hint">
            <span class="field-help">Куда перейти, если найдено несколько кандидатов или результат ниже порога уверенности.</span>
          </label>
        </div>
        <label>Привязка параметров инструмента
          <textarea name="parameter_bindings" rows="4" placeholder="last_name=attribute:last_name&#10;first_name=attribute:first_name">${escapeHtml(formatKeyValueLines(step.parameter_bindings))}</textarea>
          <span class="field-help">Одна строка на параметр: параметр=источник. Источники: slot:, attribute:, constant:, secret:, case:, context:.</span>
        </label>
        <div class="grid two">
          <label>Условие
            <input name="condition" value="${escapeHtml(step.condition || '')}" autocomplete="off" placeholder="ad_candidates.count == 1">
            <span class="field-help">Проверка для шага "условие". При успехе используется переход успеха, иначе переход ошибки.</span>
          </label>
          <label>Условие неоднозначности
            <input name="ambiguity_condition" value="${escapeHtml(step.ambiguity_condition || '')}" autocomplete="off" placeholder="ad_candidates.count > 1">
            <span class="field-help">Проверка, при которой используется переход неоднозначности.</span>
          </label>
          <label>Уточняемые атрибуты
            <input name="ask_for_attributes" value="${escapeHtml(csv(step.ask_for_attributes))}" autocomplete="off" placeholder="department, employee_number">
            <span class="field-help">Какие данные нужно запросить у пользователя или оператора при неоднозначности.</span>
          </label>
          <label>Заполняемый слот
            <input name="fill_slot_id" value="${escapeHtml(step.fill_slot_id || '')}" autocomplete="off" placeholder="user_login">
            <span class="field-help">Какой слот заполнит шаг типа "заполнение слота".</span>
          </label>
          <label>Источник значения
            <input name="from_attribute" value="${escapeHtml(step.from_attribute || '')}" autocomplete="off" placeholder="ad_candidates.0.login">
            <span class="field-help">Из какого атрибута контекста взять значение для слота.</span>
          </label>
        </div>
        <label>Уточняющий вопрос
          <textarea name="clarification_question" rows="3" placeholder="Уточните должность, подразделение или табельный номер пользователя.">${escapeHtml(step.clarification_question || '')}</textarea>
          <span class="field-help">Текст вопроса для шага "уточняющий вопрос".</span>
        </label>
        <fieldset class="launch-editor">
          <legend>Фильтр истории заявок</legend>
          <div class="grid two">
            <label>Статусы заявок
              <input name="history_ticket_statuses" value="${escapeHtml(csv(history.ticket_statuses))}" autocomplete="off" placeholder="resolved, closed">
              <span class="field-help">Какие статусы закрытых заявок разрешены для поиска.</span>
            </label>
            <label>Период, дней
              <input name="history_time_window_days" type="number" min="1" max="3650" value="${escapeHtml(history.time_window_days || '')}">
              <span class="field-help">За какой период можно брать исторические заявки.</span>
            </label>
            <label>Минимальная оценка качества
              <input name="history_min_quality" value="${escapeHtml(history.min_quality || '')}" autocomplete="off" placeholder="accepted">
              <span class="field-help">Какая разметка качества ответа допускается для использования истории.</span>
            </label>
            <label>Порог похожести
              <input name="history_similarity_threshold" type="number" min="0" max="1" step="0.01" value="${escapeHtml(history.similarity_threshold ?? '')}">
              <span class="field-help">Минимальная похожесть найденной заявки на текущий кейс.</span>
            </label>
            <label>Разрешенные поля истории
              <input name="history_allowed_fields" value="${escapeHtml(csv(history.allowed_fields))}" autocomplete="off" placeholder="account_type">
              <span class="field-help">Какие поля из исторических заявок можно использовать для заполнения.</span>
            </label>
            <label>Исключенные категории
              <input name="history_excluded_categories" value="${escapeHtml(csv(history.excluded_categories))}" autocomplete="off" placeholder="security_incident, vip_case">
              <span class="field-help">Какие категории заявок нельзя использовать как источник данных.</span>
            </label>
          </div>
        </fieldset>
      </div>
    </details>
  `;
}

function resolutionStepTypeOptions(selected) {
  const values = [
    'llm_extract',
    'rag_search',
    'case_read',
    'tool_call',
    'ticket_history_search',
    'condition',
    'clarification',
    'fill_slot',
    'operator_handoff',
    'escalate',
  ];
  return values
    .map((value) => `<option value="${escapeHtml(value)}" ${value === selected ? 'selected' : ''}>${escapeHtml(visibleLabels[value] || value)}</option>`)
    .join('');
}

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
    resolution_mode: template.resolution_mode || 'branching',
    attempt_scope: template.attempt_scope || 'profile',
    input_slots: template.input_slots || [],
    output_slots: template.output_slots || [],
    intermediate_attributes: template.intermediate_attributes || ['value'],
    steps: template.steps || [
      {
        step_id: 'ask_user',
        type: 'clarification',
        display_name: 'Уточнить значение',
        clarification_question: 'Уточните значение атрибута.',
        ask_for_attributes: ['value'],
      },
    ],
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
    ambiguity_policy: template.ambiguity_policy || {
      action: 'clarification',
      question: 'Уточните данные для однозначного заполнения атрибута.',
      ask_for_attributes: [],
    },
    operator_handoff_package: template.operator_handoff_package || [],
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

function scenarioDisplayName(scenarios, scenarioId) {
  return (scenarios || []).find((scenario) => scenario.scenario_id === scenarioId)?.display_name || 'Выбранный сценарий';
}

function promptPackLabel(promptPack) {
  return String(promptPack?.display_name || 'Пакет промптов').replace(/^Prompt pack:/i, 'Пакет промптов:');
}

function promptPackCreateTemplate(source, packs, scenarios) {
  const template = source || packs[0] || {};
  const scenarioId = template.scenario_id || state.scenarioId || scenarios[0]?.scenario_id || '';
  return {
    prompt_pack_id: nextPromptPackId(template.prompt_pack_id || `prompt.${scenarioId || 'custom'}`, packs),
    scenario_id: scenarioId,
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
    tool_rules: 'Опишите правила выбора и вызова инструментов.',
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
        question: 'Уточните логин пользователя.',
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
          Вопрос при неоднозначности: ${escapeHtml(profile.ambiguity_policy?.question || profile.fallback?.question || 'н/д')}.
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
        ${fillMethod === 'resolution_profile' ? profileHint : ''}
        <div class="grid two">
          <label>Ключ слота
            <input name="slot_id" value="${escapeHtml(slot.slot_id || '')}" autocomplete="off" placeholder="user_login">
            <span class="field-help">Технический ключ поля. Используется в матрице инструментов и prompt pack. Формат: латиница, цифры, _, -, .</span>
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
            <select name="fill_method">${fillMethodOptions(fillMethod)}</select>
            <span class="field-help">Как платформа получает значение: вопрос, текущий кейс, извлечение моделью, профиль разрешения атрибута или ручное заполнение оператором.</span>
          </label>
          <label>Профиль разрешения атрибута
            <select name="resolution_profile_id">${resolutionProfileOptions(resolutionProfiles, slot.resolution_profile_id, slot.slot_id)}</select>
            <span class="field-help">Используется только для способа "профиль разрешения". Профиль задает порядок LLM extraction, вызовов tools, поиска по истории и уточняющих вопросов.</span>
          </label>
          <label>Порядок вопроса
            <input name="question_order" type="number" min="1" max="999" value="${escapeHtml(order || '')}">
            <span class="field-help">Позиция в очереди обогащения. Учитывается для вопросов пользователю и профилей, которым нужен уточняющий вопрос.</span>
          </label>
        </div>
        <label>Вопрос пользователю
          <textarea name="question" rows="3" placeholder="Уточните логин пользователя.">${escapeHtml(slot.question || '')}</textarea>
          <span class="field-help">Текст вопроса для способа "вопрос пользователю" или запасной вопрос, если профиль не смог однозначно заполнить слот.</span>
        </label>
        <div class="grid two">
          <label>Служебная ссылка
            <input name="auto_fill_ref" value="${escapeHtml(slot.auto_fill_ref || '')}" autocomplete="off" placeholder="ad.user_id">
          </label>
        </div>
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
    route: template.route || 'agent_l1',
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
        <label>Маршрут<select name="route">${optionList(['auto_agent', 'agent_l1', 'l1_hint', 'l2_major_incident', 'approver'], current.route)}</select></label>
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
      'user_confirmed_success',
      'waiting_for_user',
      'tool_errors_limit',
      'iteration_limit',
      'low_confidence',
      'major_incident',
    ],
    allowed_tool_classes: template.allowed_tool_classes || ['read_only', 'action'],
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
        <label>Ошибок инструмента до Л2<input name="consecutive_tool_errors_to_escalate" type="number" min="1" max="10" value="${escapeHtml(current.consecutive_tool_errors_to_escalate || 2)}"></label>
        <label>Классы инструментов<input name="allowed_tool_classes" value="${escapeHtml(csv(current.allowed_tool_classes))}"></label>
        <label>Стоп-условия<input name="stop_conditions" value="${escapeHtml(csv(current.stop_conditions))}"></label>
      </div>
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
        endpoint_profile: 'mock',
        operation_id: 'check_zabbix_status',
        risk_level: 'low',
        audit_required: true,
        log_required: true,
        stop_on_error: true,
      },
    ],
  };
}

function renderToolLaunchEditor({ matrix, matrices, scenarios }) {
  if (state.toolMatrixOperation === 'delete') {
    if (!matrix?.matrix_id) {
      return '<div class="empty">Нет выбранной матрицы инструментов для удаления</div>';
    }
    return `
      <form class="scenario-editor panel" data-form="tool-matrix-delete">
        <div>
          <div class="metric-label">Удаляемая матрица инструментов</div>
          <div class="scenario-title">${escapeHtml(matrix.display_name)}</div>
        </div>
        ${usagePanel(scenarios, 'tool_launch_matrix_id', matrix.matrix_id)}
        <button class="danger" type="submit">Удалить матрицу инструментов</button>
      </form>
    `;
  }
  const current = state.toolMatrixOperation === 'create'
    ? toolMatrixCreateTemplate(matrix, matrices)
    : matrix;
  if (!current?.matrix_id) {
    return '<div class="empty">Матрица инструментов не выбрана</div>';
  }
  const launches = current.launches || [];
  const launchForms = launches.map((launch, index) => renderLaunchCard(launch, index)).join('');
  return `
    <form class="scenario-editor panel" data-form="tool-launch-editor">
      <input type="hidden" name="matrix_id" value="${escapeHtml(current.matrix_id)}">
      <label>Название<input name="display_name" value="${escapeHtml(current.display_name || '')}" autocomplete="off"></label>
      <input type="hidden" name="launch_count" value="${escapeHtml(launches.length)}">
      <div id="launchCards">${launchForms}</div>
      <button type="button" data-action="launch-add">Добавить запуск</button>
      ${usagePanel(scenarios, 'tool_launch_matrix_id', current.matrix_id)}
      <div class="scenario-editor-actions">
        <button class="primary" type="submit">${state.toolMatrixOperation === 'create' ? 'Создать матрицу инструментов' : 'Сохранить матрицу инструментов'}</button>
      </div>
    </form>
  `;
}

function renderLaunchCard(launch, index) {
  return `
    <fieldset class="launch-editor" data-launch-card>
      <legend>${escapeHtml(launch.tool_name || `Запуск ${index + 1}`)}</legend>
      <input type="hidden" name="launch_id_${index}" value="${escapeHtml(launch.launch_id)}">
      <div class="grid two">
        <label>Инструмент<input name="tool_name_${index}" value="${escapeHtml(launch.tool_name)}" autocomplete="off"></label>
        <label>Обязательные слоты<input name="required_slots_${index}" value="${escapeHtml(csv(launch.required_slots))}"></label>
        <label>Текущий запуск<select name="execution_level_${index}">${optionList(['auto', 'operator_approval', 'approver_approval', 'blocked'], launch.execution_level)}</select></label>
        <label>Целевой запуск<select name="target_execution_level_${index}">${optionList(['auto', 'operator_approval', 'approver_approval', 'blocked'], launch.target_execution_level)}</select></label>
        <label>Endpoint profile<input name="endpoint_profile_${index}" value="${escapeHtml(launch.endpoint_profile)}" autocomplete="off"></label>
        <label>Операция<input name="operation_id_${index}" value="${escapeHtml(launch.operation_id)}" autocomplete="off"></label>
        <label>Риск<select name="risk_level_${index}">${optionList(['low', 'medium', 'high', 'critical', 'blocked'], launch.risk_level)}</select></label>
        <label>Роль согласования<input name="approval_role_${index}" value="${escapeHtml(launch.approval_role || '')}" autocomplete="off"></label>
        <label>Audit<select name="audit_required_${index}">${booleanOptions(launch.audit_required)}</select></label>
        <label>Log<select name="log_required_${index}">${booleanOptions(launch.log_required)}</select></label>
        <label>Stop on error<select name="stop_on_error_${index}">${booleanOptions(launch.stop_on_error)}</select></label>
      </div>
      <label>Parameter bindings, JSON<textarea name="parameter_bindings_${index}" rows="5">${escapeHtml(jsonPretty(launch.parameter_bindings || {}))}</textarea></label>
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
    l2_conditions: template.l2_conditions || [
      'two_tool_errors',
      'iteration_limit',
      'confidence_below_050',
      'affected_users_threshold',
      'policy_blocked',
    ],
    major_incident: template.major_incident || {
      affected_users_threshold: 10,
      notify_on_call: false,
    },
    escalation_package: template.escalation_package || [
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
        <label>Автозакрытие требует успех инструмента<select name="requires_tool_success">${booleanOptions(current.auto_close?.requires_tool_success)}</select></label>
        <label>Автозакрытие требует подтверждение пользователя<select name="requires_user_confirmation">${booleanOptions(current.auto_close?.requires_user_confirmation)}</select></label>
        <label>Ожидание приостанавливает SLA<select name="pause_sla">${booleanOptions(current.waiting?.pause_sla)}</select></label>
        <label>Автозакрытие ожидания, часов<input name="auto_close_after_hours" type="number" min="1" max="168" value="${escapeHtml(current.waiting?.auto_close_after_hours || 24)}"></label>
        <label>Major Incident threshold<input name="affected_users_threshold" type="number" min="1" max="100000" value="${escapeHtml(current.major_incident?.affected_users_threshold || 10)}"></label>
        <label>Оповещать дежурных<select name="notify_on_call">${booleanOptions(current.major_incident?.notify_on_call)}</select></label>
        <label>Условия Л2<input name="l2_conditions" value="${escapeHtml(csv(current.l2_conditions))}"></label>
        <label>Пакет Л2<input name="escalation_package" value="${escapeHtml(csv(current.escalation_package))}"></label>
      </div>
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
    tool_rules: '6. Правила инструментов',
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
        <label>Сценарий применения
          <select name="scenario_id">${referenceOptions(scenarios, 'scenario_id', current.scenario_id, 'display_name')}</select>
          <span class="field-help">Сценарий, для которого пакет промптов подготовлен. Связь включается в самом сценарии через поле "Пакет промптов".</span>
        </label>
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
        ${metric('Инструменты', String(dashboard.tools?.count ?? 0))}
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

async function renderTools() {
  const [tools, endpoints, n8n, audit] = await Promise.all([
    api('/admin/catalog/tools'),
    api('/admin/catalog/integration-endpoints'),
    api('/admin/n8n/workflows'),
    api('/admin/security/audit?limit=30'),
  ]);
  const toolRows = (tools.tools || []).map((tool) => [
    escapeHtml(tool.tool_name),
    badge(tool.action_type),
    escapeHtml(tool.policy?.max_risk_level || 'н/д'),
    escapeHtml(tool.policy?.default_timeout_seconds ?? 'н/д'),
    escapeHtml((tool.endpoint_bindings || []).map((binding) => `${binding.profile}: ${binding.endpoint_id}`).join(', ')),
  ]);
  const endpointRows = (endpoints.endpoints || []).map((endpoint) => [
    escapeHtml(endpoint.endpoint_id),
    badge(endpoint.enabled ? 'enabled' : 'disabled'),
    escapeHtml(endpoint.adapter_type),
    escapeHtml(Object.keys(endpoint.operations || {}).join(', ')),
    escapeHtml(endpoint.disabled_reason || endpoint.base_url_env || 'н/д'),
  ]);
  const n8nRows = (n8n.workflows || []).map((workflow) => [
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
    section('Каталог инструментов', table(['Инструмент', 'Тип', 'Максимальный риск', 'Таймаут', 'Привязки точек интеграции'], toolRows)),
    section('Точки интеграции', table(['Точка интеграции', 'Статус', 'Адаптер', 'Операции', 'Ссылка'], endpointRows)),
    section('Рабочие процессы n8n', table(['Статус', 'Сценарий', 'Точка интеграции', 'Операции'], n8nRows)),
    section('История инструментов и callbacks', table(['Время', 'Действие', 'Результат', 'Ресурс', 'Инициатор'], auditRows)),
  ].join('');
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
          <label>Base URL шлюза
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
            ${modelRouteField(config, 'tool_selection', 'Выбор инструментов')}
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
        <label>Base URL<input name="${providerId}_base_url" value="${escapeHtml(provider.base_url || '')}" autocomplete="off"></label>
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
    tags: String(data.get('tags') || '')
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean),
  });
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
      .filter((slot) => ['user_question', 'resolution_profile'].includes(slot.fill_method))
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
    const resolutionProfileId = value('resolution_profile_id');
    const question = value('question');
    const autoFillRef = value('auto_fill_ref');
    if (resolutionProfileId) {
      slot.resolution_profile_id = resolutionProfileId;
    }
    if (question) {
      slot.question = question;
    }
    if (autoFillRef) {
      slot.auto_fill_ref = autoFillRef;
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
    stop_conditions: parseCsv(data.get('stop_conditions')),
    allowed_tool_classes: parseCsv(data.get('allowed_tool_classes')),
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
    const launch = {
      launch_id: value('launch_id'),
      tool_name: value('tool_name'),
      required_slots: parseCsv(value('required_slots')),
      parameter_bindings: parseJsonField(value('parameter_bindings'), `Parameter bindings ${index + 1}`),
      execution_level: value('execution_level'),
      target_execution_level: value('target_execution_level'),
      endpoint_profile: value('endpoint_profile'),
      operation_id: value('operation_id'),
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
    successNoun: 'Матрица инструментов',
  });
}

async function deleteToolMatrixForm() {
  if (!state.toolMatrixId) {
    throw new Error('Матрица инструментов для удаления не выбрана.');
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
    successNoun: 'Матрица инструментов',
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
    l2_conditions: parseCsv(data.get('l2_conditions')),
    major_incident: {
      affected_users_threshold: parseInt(data.get('affected_users_threshold'), 10),
      notify_on_call: parseBoolean(data.get('notify_on_call')),
    },
    escalation_package: parseCsv(data.get('escalation_package')),
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

async function savePromptPackForm(form) {
  const data = new FormData(form);
  const promptPack = {
    prompt_pack_id: String(data.get('prompt_pack_id') || '').trim(),
    scenario_id: String(data.get('scenario_id') || '').trim(),
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
  const profile = {
    profile_id: String(data.get('profile_id') || '').trim(),
    display_name: String(data.get('display_name') || '').trim(),
    status: String(data.get('status') || '').trim(),
    description: String(data.get('description') || '').trim(),
    target_slot_id: String(data.get('target_slot_id') || '').trim(),
    resolution_mode: String(data.get('resolution_mode') || 'sequential').trim(),
    attempt_scope: String(data.get('attempt_scope') || 'profile').trim(),
    input_slots: parseCsv(data.get('input_slots')),
    output_slots: parseCsv(data.get('output_slots')),
    intermediate_attributes: parseCsv(data.get('intermediate_attributes')),
    steps: parseResolutionStepCards(form),
    fallback: {
      action: String(data.get('fallback_action') || '').trim(),
    },
    confidence_threshold: Number(data.get('confidence_threshold')),
    confidence_thresholds: {
      auto_fill: Number(data.get('confidence_auto_fill')),
      clarification: Number(data.get('confidence_clarification')),
      operator_handoff: Number(data.get('confidence_operator_handoff')),
    },
    ambiguity_policy: {
      action: String(data.get('ambiguity_action') || '').trim(),
    },
    operator_handoff_package: parseCsv(data.get('operator_handoff_package')),
    max_attempts: parseInt(data.get('max_attempts'), 10),
    audit_required: parseBoolean(data.get('audit_required')),
    log_required: parseBoolean(data.get('log_required')),
  };
  const fallbackQuestion = String(data.get('fallback_question') || '').trim();
  if (fallbackQuestion) {
    profile.fallback.question = fallbackQuestion;
  }
  const ambiguityCandidateCountAttribute = String(data.get('ambiguity_candidate_count_attribute') || '').trim();
  const ambiguityQuestion = String(data.get('ambiguity_question') || '').trim();
  const ambiguityAskForAttributes = parseCsv(data.get('ambiguity_ask_for_attributes'));
  if (ambiguityCandidateCountAttribute) {
    profile.ambiguity_policy.candidate_count_attribute = ambiguityCandidateCountAttribute;
  }
  if (ambiguityQuestion) {
    profile.ambiguity_policy.question = ambiguityQuestion;
  }
  if (ambiguityAskForAttributes.length) {
    profile.ambiguity_policy.ask_for_attributes = ambiguityAskForAttributes;
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

function parseResolutionStepCards(form) {
  const cards = Array.from(form.querySelectorAll('[data-resolution-step-card]'));
  const steps = cards.map((card, index) => {
    const value = (name) => card.querySelector(`[name="${name}"]`)?.value?.trim() || '';
    const step = {
      step_id: value('step_id'),
      type: value('type'),
      display_name: value('display_name'),
    };
    const inputs = parseCsv(value('inputs'));
    const outputs = parseCsv(value('outputs'));
    const toolName = value('tool_name');
    const endpointProfile = value('endpoint_profile');
    const operationId = value('operation_id');
    const parameterBindings = parseKeyValueLines(value('parameter_bindings'), `Привязка параметров шага ${index + 1}`);
    const condition = value('condition');
    const ambiguityCondition = value('ambiguity_condition');
    const clarificationQuestion = value('clarification_question');
    const askForAttributes = parseCsv(value('ask_for_attributes'));
    const fillSlotId = value('fill_slot_id');
    const fromAttribute = value('from_attribute');
    const onSuccessStep = value('on_success_step');
    const onFailureStep = value('on_failure_step');
    const onAmbiguousStep = value('on_ambiguous_step');
    const historyFilter = parseHistoryFilter(card);

    if (inputs.length) step.inputs = inputs;
    if (outputs.length) step.outputs = outputs;
    if (toolName) step.tool_name = toolName;
    if (endpointProfile) step.endpoint_profile = endpointProfile;
    if (operationId) step.operation_id = operationId;
    if (Object.keys(parameterBindings).length) step.parameter_bindings = parameterBindings;
    if (condition) step.condition = condition;
    if (ambiguityCondition) step.ambiguity_condition = ambiguityCondition;
    if (clarificationQuestion) step.clarification_question = clarificationQuestion;
    if (askForAttributes.length) step.ask_for_attributes = askForAttributes;
    if (fillSlotId) step.fill_slot_id = fillSlotId;
    if (fromAttribute) step.from_attribute = fromAttribute;
    if (Object.keys(historyFilter).length) step.history_filter = historyFilter;
    if (onSuccessStep) step.on_success_step = onSuccessStep;
    if (onFailureStep) step.on_failure_step = onFailureStep;
    if (onAmbiguousStep) step.on_ambiguous_step = onAmbiguousStep;
    return step;
  });

  if (!steps.length) {
    throw new Error('Профиль должен содержать хотя бы один шаг разрешения атрибута.');
  }
  const incompleteStep = steps.find((step) => !step.step_id || !step.type || !step.display_name);
  if (incompleteStep) {
    throw new Error('Каждый шаг должен иметь ключ, тип и название.');
  }
  const seen = new Set();
  const duplicate = steps.find((step) => {
    if (seen.has(step.step_id)) return true;
    seen.add(step.step_id);
    return false;
  });
  if (duplicate) {
    throw new Error(`Ключ шага повторяется: ${duplicate.step_id}`);
  }
  return steps;
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
}

function removeSlotCard(target) {
  const card = target.closest('[data-slot-card]');
  if (!card) return;
  card.remove();
  renumberSlotCards();
}

function renumberSlotCards() {
  document.querySelectorAll('#slotCards [data-slot-card]').forEach((card, index) => {
    const orderInput = card.querySelector('[name="question_order"]');
    if (orderInput && !orderInput.value) {
      orderInput.value = String(index + 1);
    }
  });
}

function addResolutionStepCard() {
  const container = document.getElementById('resolutionStepCards');
  if (!container) return;
  const order = container.querySelectorAll('[data-resolution-step-card]').length + 1;
  const wrapper = document.createElement('div');
  wrapper.innerHTML = renderResolutionStepCard(
    {
      step_id: `step_${order}`,
      type: 'clarification',
      display_name: 'Уточнить значение',
      clarification_question: 'Уточните значение атрибута.',
      ask_for_attributes: ['value'],
    },
    order,
    true,
  ).trim();
  container.appendChild(wrapper.firstElementChild);
}

function removeResolutionStepCard(target) {
  const card = target.closest('[data-resolution-step-card]');
  if (!card) return;
  card.remove();
}

function addLaunchCard() {
  const container = document.getElementById('launchCards');
  if (!container) return;
  const index = container.querySelectorAll('[data-launch-card]').length;
  const wrapper = document.createElement('div');
  wrapper.innerHTML = renderLaunchCard(
    {
      launch_id: `launch.custom_${index + 1}`,
      tool_name: 'check_zabbix_status',
      required_slots: [],
      parameter_bindings: {
        query: 'context:query',
      },
      execution_level: 'auto',
      target_execution_level: 'auto',
      endpoint_profile: 'mock',
      operation_id: 'check_zabbix_status',
      risk_level: 'low',
      audit_required: true,
      log_required: true,
      stop_on_error: true,
    },
    index,
  ).trim();
  container.appendChild(wrapper.firstElementChild);
}

function removeLaunchCard(target) {
  const card = target.closest('[data-launch-card]');
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
    if (action === 'slot-remove' || action === 'resolution-step-remove' || action === 'launch-remove' || action === 'model-provider-remove') {
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
      } else if (action === 'resolution-load') {
        await renderResolutionProfiles();
      } else if (action === 'resolution-operation') {
        state.resolutionOperation = target.dataset.operation;
        await renderResolutionProfiles();
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
      } else if (action === 'resolution-step-add') {
        addResolutionStepCard();
      } else if (action === 'resolution-step-remove') {
        removeResolutionStepCard(target);
      }
    } catch (error) {
      setNotice(error.message || String(error), 'error');
    } finally {
      target.disabled = false;
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
      } else if (form.dataset.form === 'route-editor') {
        await saveRouteForm(form);
      } else if (form.dataset.form === 'route-delete') {
        await deleteRouteForm();
      } else if (form.dataset.form === 'policy-editor') {
        await savePolicyForm(form);
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
      } else if (form.dataset.form === 'model-routing-editor') {
        await saveModelRoutingForm(form);
      } else if (form.dataset.form === 'resolution-profile-editor') {
        await saveResolutionProfileForm(form);
      } else if (form.dataset.form === 'resolution-profile-delete') {
        await deleteResolutionProfileForm();
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
