#!/usr/bin/env node

import { spawnSync } from 'node:child_process';
import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const postgresContainer = process.env.N8N_POSTGRES_CONTAINER || 'servicedesk-agents-postgres';
const postgresUser = process.env.N8N_DB_USER || 'servicedesk';
const postgresDb = process.env.N8N_DB_NAME || 'n8n';
const workflowId = process.env.N8N_PROVIDER_WORKFLOW_ID || 'providerChannelRepairMonitor';

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    encoding: 'utf8',
    maxBuffer: 20 * 1024 * 1024,
    ...options,
  });
  if (result.status !== 0) {
    const stderr = result.stderr?.trim();
    const stdout = result.stdout?.trim();
    const detail = stderr || stdout || result.error?.message || (result.signal ? `signal ${result.signal}` : '');
    throw new Error(`${command} ${args.join(' ')} failed${detail ? `: ${detail}` : ''}`);
  }
  return result.stdout;
}

function tempSqlPath(kind) {
  const tmpRoot = join(process.cwd(), 'tmp');
  mkdirSync(tmpRoot, { recursive: true });
  const suffix = `${Date.now()}-${process.pid}-${Math.random().toString(16).slice(2)}`;
  return {
    localPath: join(tmpRoot, `${kind}-${suffix}.sql`),
    containerPath: `/tmp/${kind}-${suffix}.sql`,
  };
}

function psql(sql) {
  const { localPath, containerPath } = tempSqlPath('query-n8n-provider');
  writeFileSync(localPath, sql, 'utf8');
  try {
    run('docker', ['cp', localPath, `${postgresContainer}:${containerPath}`]);
    return run('docker', [
      'exec',
      postgresContainer,
      'psql',
      '-U',
      postgresUser,
      '-d',
      postgresDb,
      '-v',
      'ON_ERROR_STOP=1',
      '-tA',
      '-f',
      containerPath,
    ]);
  } finally {
    rmSync(localPath, { force: true });
  }
}

function psqlFile(sql) {
  const { localPath, containerPath } = tempSqlPath('patch-n8n-provider');
  writeFileSync(localPath, sql, 'utf8');
  try {
    run('docker', ['cp', localPath, `${postgresContainer}:${containerPath}`]);
    return run('docker', [
      'exec',
      postgresContainer,
      'psql',
      '-U',
      postgresUser,
      '-d',
      postgresDb,
      '-v',
      'ON_ERROR_STOP=1',
      '-f',
      containerPath,
    ]);
  } finally {
    rmSync(localPath, { force: true });
  }
}

function fetchWorkflow() {
  const sql = `
select json_build_object('nodes', nodes, 'connections', connections)::text
from workflow_entity
where id = '${workflowId.replace(/'/g, "''")}';
`;
  const raw = psql(sql).trim();
  if (!raw) throw new Error(`Workflow ${workflowId} not found.`);
  return JSON.parse(raw);
}

function saveWorkflow(workflow) {
  const payload = JSON.stringify({
    nodes: workflow.nodes,
    connections: workflow.connections,
  });
  const escaped = payload.replace(/'/g, "''");
  const sql = `
with payload as (
  select '${escaped}'::jsonb as value
)
update workflow_entity
set
  nodes = (select value->'nodes' from payload)::json,
  connections = (select value->'connections' from payload)::json,
  "updatedAt" = now()
where id = '${workflowId.replace(/'/g, "''")}';

with payload as (
  select '${escaped}'::jsonb as value
),
active_version as (
  select "activeVersionId"
  from workflow_entity
  where id = '${workflowId.replace(/'/g, "''")}'
)
update workflow_history
set
  nodes = (select value->'nodes' from payload)::json,
  connections = (select value->'connections' from payload)::json,
  "updatedAt" = now()
where "versionId" = (select "activeVersionId" from active_version);
`;
  psqlFile(sql);
}

function byName(nodes, name) {
  return nodes.find((node) => node.name === name);
}

function terminalErrorCode() {
  return `
const baseState = (state) => ({
  ...state,
  terminal: true,
});

function terminalError(state, code, message, details = {}) {
  return baseState({
    ...state,
    response: {
      runbook_status: 'ERROR',
      message,
      error: { code, message, ...details },
      host: state.host,
      problemUrl: state.problemUrl,
      service_request: state.service_request,
      provider_email_context: state.provider_email_context || null,
      email_dispatch: state.email_dispatch || null,
      zabbix_status: state.zabbix_status || null,
      email_result: null,
      started_at: state.started_at,
      finished_at: new Date().toISOString(),
      poll_interval_minutes: state.poll_interval_minutes,
      timeout_minutes: state.timeout_minutes
    }
  });
}

function text(value) {
  return value === undefined || value === null ? '' : String(value).trim();
}

function bodyOf(value) {
  return value && value.body && typeof value.body === 'object' ? value.body : value;
}

function statusOf(value) {
  return Number(value?.statusCode || 200);
}

function safeMessage(error) {
  return String(error?.message || error || 'unknown_error').replace(/token|password|secret|authorization/ig, '[redacted]').slice(0, 500);
}
`.trim();
}

function providerNodes() {
  const common = terminalErrorCode();
  return [
    {
      id: 'provider-channel-monitor-cmdbuild-prepare',
      name: 'Подготовка CMDBuild контекста',
      type: 'n8n-nodes-base.code',
      typeVersion: 2,
      position: [1360, 160],
      parameters: {
        jsCode: `${common}

const state = $input.first().json || {};
const rawBaseUrl = text((typeof $env !== 'undefined' && $env.CMDBUILD_BASE_URL) || (typeof process !== 'undefined' && process.env.CMDBUILD_BASE_URL) || 'http://hostmachine:8090/cmdbuild');
if (!/^https?:\\/\\/[^/?#]+(?:\\/[^?#]*)?$/i.test(rawBaseUrl)) {
  return [{ json: terminalError(state, 'invalid_cmdbuild_base_url', 'CMDBUILD_BASE_URL должен быть http/https URL без query/fragment.') }];
}
const cmdbuildBaseUrl = rawBaseUrl.replace(/\\/+$/, '');
const filter = {
  attribute: {
    or: [
      {
        simple: {
          attribute: 'Description',
          operator: 'equal',
          value: [state.host]
        }
      },
      {
        simple: {
          attribute: 'hostname',
          operator: 'equal',
          value: [state.host]
        }
      },
      {
        simple: {
          attribute: 'Code',
          operator: 'equal',
          value: [state.host]
        }
      }
    ]
  }
};
return [{
  json: {
    ...state,
    terminal: false,
    cmdbuild_base_url: cmdbuildBaseUrl,
    router_search_url: cmdbuildBaseUrl + '/services/rest/v3/classes/routerG/cards?limit=2&filter=' + encodeURIComponent(JSON.stringify(filter))
  }
}];`,
      },
    },
    {
      id: 'provider-channel-monitor-cmdbuild-search-router',
      name: 'CMDBuild поиск routerG',
      type: 'n8n-nodes-base.httpRequest',
      typeVersion: 4.1,
      position: [1640, 160],
      parameters: {
        url: '={{ $json.router_search_url }}',
        options: {
          response: {
            response: {
              neverError: true,
              fullResponse: true,
              responseFormat: 'json',
            },
          },
        },
        authentication: 'genericCredentialType',
        genericAuthType: 'httpBasicAuth',
      },
      credentials: {
        httpBasicAuth: {
          id: 'localCmdbuildAdminTest',
          name: 'Local CMDBuild Admin Test',
        },
      },
    },
    {
      id: 'provider-channel-monitor-cmdbuild-parse-router',
      name: 'Разбор routerG для письма',
      type: 'n8n-nodes-base.code',
      typeVersion: 2,
      position: [1920, 160],
      parameters: {
        jsCode: `${common}

const state = $('Подготовка CMDBuild контекста').first().json || {};
const searchResponse = $input.first().json || {};
const body = bodyOf(searchResponse);
const httpStatus = statusOf(searchResponse);
if (httpStatus === 401 || httpStatus === 403) {
  return [{ json: terminalError(state, 'cmdbuild_auth_failed', 'CMDBuild authentication failed.', { http_status: httpStatus }) }];
}
if (httpStatus >= 400 || body?.success === false) {
  return [{ json: terminalError(state, 'cmdbuild_lookup_failed', 'CMDBuild routerG lookup failed.', { cmdbuild_status: httpStatus || null }) }];
}

const rows = Array.isArray(body?.data) ? body.data : [];
const total = Number(body?.meta?.total ?? rows.length);
if (total === 0 || rows.length === 0) {
  return [{ json: terminalError(state, 'router_not_found', 'routerG не найден по Description, hostname или Code.', { hostname: state.host }) }];
}
if (total > 1 || rows.length > 1) {
  return [{ json: terminalError(state, 'router_not_unique', 'По hostname найдено несколько routerG объектов.', { hostname: state.host, match_count: total || rows.length }) }];
}

const router = rows[0] || {};
const missing = [];
const providerEmail = text(router.email);
const contract = text(router.contract);
const ipaddressId = text(router.ipaddress);
const roomId = text(router.Location);
if (!providerEmail) missing.push('email');
if (!contract) missing.push('contract');
if (!ipaddressId) missing.push('ipaddress');
if (!roomId) missing.push('Location');
if (missing.length) {
  return [{ json: terminalError(state, 'missing_cmdbuild_field', 'В routerG не заполнены обязательные атрибуты.', {
    hostname: state.host,
    router_id: router._id || null,
    missing_fields: missing
  }) }];
}

return [{
  json: {
    ...state,
    terminal: false,
    router_id: router._id,
    router_code: text(router.Code),
    provider_email: providerEmail,
    contract,
    ipaddress_id: ipaddressId,
    room_id: roomId,
    ip_url: state.cmdbuild_base_url + '/services/rest/v3/classes/IpAddress/cards/' + encodeURIComponent(ipaddressId),
    room_url: state.cmdbuild_base_url + '/services/rest/v3/classes/Room/cards/' + encodeURIComponent(roomId)
  }
}];`,
      },
    },
    {
      id: 'provider-channel-monitor-cmdbuild-terminal',
      name: 'CMDBuild контекст терминальный?',
      type: 'n8n-nodes-base.if',
      typeVersion: 1,
      position: [2200, 160],
      parameters: {
        conditions: {
          boolean: [
            {
              value1: '={{ $json.terminal }}',
              value2: true,
              operation: 'equal',
            },
          ],
        },
        combineOperation: 'all',
      },
    },
    {
      id: 'provider-channel-monitor-cmdbuild-get-ip',
      name: 'CMDBuild чтение IpAddress',
      type: 'n8n-nodes-base.httpRequest',
      typeVersion: 4.1,
      position: [2480, 300],
      parameters: {
        url: '={{ $json.ip_url }}',
        options: {
          response: {
            response: {
              neverError: true,
              fullResponse: true,
              responseFormat: 'json',
            },
          },
        },
        authentication: 'genericCredentialType',
        genericAuthType: 'httpBasicAuth',
      },
      credentials: {
        httpBasicAuth: {
          id: 'localCmdbuildAdminTest',
          name: 'Local CMDBuild Admin Test',
        },
      },
    },
    {
      id: 'provider-channel-monitor-cmdbuild-get-room',
      name: 'CMDBuild чтение Room',
      type: 'n8n-nodes-base.httpRequest',
      typeVersion: 4.1,
      position: [2760, 300],
      parameters: {
        url: "={{ $('Разбор routerG для письма').first().json.room_url }}",
        options: {
          response: {
            response: {
              neverError: true,
              fullResponse: true,
              responseFormat: 'json',
            },
          },
        },
        authentication: 'genericCredentialType',
        genericAuthType: 'httpBasicAuth',
      },
      credentials: {
        httpBasicAuth: {
          id: 'localCmdbuildAdminTest',
          name: 'Local CMDBuild Admin Test',
        },
      },
    },
    {
      id: 'provider-channel-monitor-cmdbuild-get-floor',
      name: 'CMDBuild чтение Floor',
      type: 'n8n-nodes-base.httpRequest',
      typeVersion: 4.1,
      position: [3040, 300],
      parameters: {
        url: "={{ $('Разбор routerG для письма').first().json.cmdbuild_base_url + '/services/rest/v3/classes/Floor/cards/' + (((($('CMDBuild чтение Room').first().json.body || {}).data || {}).Floor) || '0') }}",
        options: {
          response: {
            response: {
              neverError: true,
              fullResponse: true,
              responseFormat: 'json',
            },
          },
        },
        authentication: 'genericCredentialType',
        genericAuthType: 'httpBasicAuth',
      },
      credentials: {
        httpBasicAuth: {
          id: 'localCmdbuildAdminTest',
          name: 'Local CMDBuild Admin Test',
        },
      },
    },
    {
      id: 'provider-channel-monitor-cmdbuild-get-building',
      name: 'CMDBuild чтение Building',
      type: 'n8n-nodes-base.httpRequest',
      typeVersion: 4.1,
      position: [3320, 300],
      parameters: {
        url: "={{ $('Разбор routerG для письма').first().json.cmdbuild_base_url + '/services/rest/v3/classes/Building/cards/' + (((($('CMDBuild чтение Floor').first().json.body || {}).data || {}).Building) || '0') }}",
        options: {
          response: {
            response: {
              neverError: true,
              fullResponse: true,
              responseFormat: 'json',
            },
          },
        },
        authentication: 'genericCredentialType',
        genericAuthType: 'httpBasicAuth',
      },
      credentials: {
        httpBasicAuth: {
          id: 'localCmdbuildAdminTest',
          name: 'Local CMDBuild Admin Test',
        },
      },
    },
    {
      id: 'provider-channel-monitor-cmdbuild-normalize',
      name: 'Нормализация CMDBuild контекста',
      type: 'n8n-nodes-base.code',
      typeVersion: 2,
      position: [3600, 300],
      parameters: {
        jsCode: `${common}

const state = $('Разбор routerG для письма').first().json || {};
const ipResponse = $('CMDBuild чтение IpAddress').first().json || {};
const roomResponse = $('CMDBuild чтение Room').first().json || {};
const floorResponse = $('CMDBuild чтение Floor').first().json || {};
const buildingResponse = $('CMDBuild чтение Building').first().json || {};

function dataOf(value) {
  const body = bodyOf(value);
  return body && typeof body === 'object' ? body.data : null;
}

const checkedResponses = [
  ['IpAddress', ipResponse],
  ['Room', roomResponse],
  ['Floor', floorResponse],
  ['Building', buildingResponse]
];
for (const [className, httpResponse] of checkedResponses) {
  const httpStatus = statusOf(httpResponse);
  const body = bodyOf(httpResponse);
  if (httpStatus === 401 || httpStatus === 403) {
    return [{ json: terminalError(state, 'cmdbuild_auth_failed', 'CMDBuild authentication failed.', { class_name: className }) }];
  }
  if (httpStatus >= 400 || body?.success === false) {
    return [{ json: terminalError(state, 'cmdbuild_lookup_failed', 'CMDBuild reference lookup failed.', { class_name: className, cmdbuild_status: httpStatus || null }) }];
  }
}

const ip = dataOf(ipResponse) || {};
const room = dataOf(roomResponse) || {};
const floor = dataOf(floorResponse) || {};
const building = dataOf(buildingResponse) || {};

const missing = [];
const ipAddress = text(ip.Description);
const location = text(room.Description);
const floorId = text(room.Floor);
const buildingId = text(floor.Building);
const city = text(building.City);
if (!ipAddress) missing.push('IpAddress.Description');
if (!location) missing.push('Room.Description');
if (!floorId) missing.push('Room.Floor');
if (!buildingId) missing.push('Floor.Building');
if (!city) missing.push('Building.City');
if (missing.length) {
  return [{ json: terminalError(state, 'missing_cmdbuild_field', 'В CMDBuild reference chain не заполнены обязательные атрибуты.', {
    hostname: state.host,
    router_id: state.router_id || null,
    missing_fields: missing
  }) }];
}

return [{
  json: {
    ...state,
    terminal: false,
    provider_email_context: {
      status: 'OK',
      hostname: state.host,
      router_id: state.router_id,
      city,
      location,
      ip_address: ipAddress,
      contract: state.contract,
      provider_email: state.provider_email
    }
  }
}];`,
      },
    },
    {
      id: 'provider-channel-monitor-email-prepare',
      name: 'Подготовка email провайдеру',
      type: 'n8n-nodes-base.code',
      typeVersion: 2,
      position: [3880, 300],
      parameters: {
        jsCode: `${common}

const state = $input.first().json || {};
const context = state.provider_email_context || {};
if (!context || context.status !== 'OK') {
  return [{ json: terminalError(state, 'provider_context_invalid', 'CMDBuild вернул некорректный контекст письма провайдеру.') }];
}

const emailRe = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
const toEmail = text(context.provider_email);
if (!emailRe.test(toEmail)) {
  return [{ json: terminalError(state, 'invalid_provider_email', 'CMDBuild вернул некорректный email провайдера.', { router_id: context.router_id || null }) }];
}

const mailboxWaitStrategy = 'imap_index_by_service_request';
const fromEmail = text(state.from_email);
const replyTo = text(state.reply_to);
if (!fromEmail) {
  return [{ json: terminalError(state, 'missing_from', 'Поле from обязательно.', {
    mailbox_wait_strategy: mailboxWaitStrategy
  }) }];
}
if (!replyTo) {
  return [{ json: terminalError(state, 'missing_reply_to', 'Поле replyTo обязательно.', {
    mailbox_wait_strategy: mailboxWaitStrategy
  }) }];
}
if (!emailRe.test(fromEmail) || !emailRe.test(replyTo)) {
  return [{ json: terminalError(state, 'invalid_email', 'Некорректный email адрес.', {
    from: fromEmail,
    reply_to: replyTo,
    mailbox_wait_strategy: mailboxWaitStrategy
  }) }];
}

const subject = ('Пропадание связи по каналу ' + text(context.city)).trim();
const body = [
  'Добрый день.',
  'Фиксируем пропадание канала на объекте по адресу ' + text(context.location),
  'IP адрес ' + text(context.ip_address),
  '№ ' + text(context.contract),
  'Просьба выяснить причину и устранить аварию.',
  '',
  'Запись в системе учета заявок ГКМ Наряд № ' + text(state.service_request),
  '',
  '!! Просьба, при ответе на письмо, цитировать всю переписку, использовать кнопку "Ответить всем";',
  'При необходимости для оперативного решения вопросов или получения уточнений звонить:',
  '+7-495- 11111111 (в рабочее время)',
  '+7-495- 22222222 (круглосуточно)',
  ''
].join('\\n');

return [{
  json: {
    ...state,
    terminal: false,
    toEmail,
    ccEmail: (state.direct_recipients?.cc || []).join(', '),
    bccEmail: (state.direct_recipients?.bcc || []).join(', '),
    from_email: fromEmail,
    reply_to: replyTo,
    reply_mailbox_address: replyTo,
    mailbox_wait_strategy: mailboxWaitStrategy,
    email_subject: subject,
    email_body: body
  }
}];`,
      },
    },
    {
      id: 'provider-channel-monitor-email-send',
      name: 'Отправка email провайдеру',
      type: 'n8n-nodes-base.emailSend',
      typeVersion: 2.1,
      position: [4160, 300],
      parameters: {
        text: '={{ $json.email_body }}',
        options: {
          ccEmail: '={{ $json.ccEmail }}',
          replyTo: '={{ $json.reply_to }}',
          bccEmail: '={{ $json.bccEmail }}',
          appendAttribution: false,
        },
        subject: '={{ $json.email_subject }}',
        toEmail: '={{ $json.toEmail }}',
        resource: 'email',
        fromEmail: '={{ $json.from_email }}',
        operation: 'send',
        emailFormat: 'text',
      },
      credentials: {
        smtp: {
          id: 'Fh3kVhbHL6XxDh1c',
          name: 'GreenMail SMTP (local test)',
        },
      },
      continueOnFail: true,
    },
    {
      id: 'provider-channel-monitor-email-result',
      name: 'Результат email провайдеру',
      type: 'n8n-nodes-base.code',
      typeVersion: 2,
      position: [4440, 300],
      parameters: {
        jsCode: `${common}

const state = $('Подготовка email провайдеру').first().json || {};
const result = $input.first().json || {};
const err = result.error || result.message?.error;
if (err) {
  return [{ json: terminalError(state, 'provider_email_send_failed', 'Не удалось отправить письмо провайдеру.', {
    reason: safeMessage(err),
    provider_email_context: {
      ...state.provider_email_context,
      provider_email: '[redacted]'
    }
  }) }];
}

return [{
  json: {
    ...state,
    terminal: false,
    email_dispatch: {
      status: 'sent',
      templateId: state.templateId,
      request_id: state.request_id,
      to: state.toEmail,
      from: state.from_email,
      reply_to: state.reply_to,
      reply_mailbox_address: state.reply_mailbox_address,
      mailbox_wait_strategy: state.mailbox_wait_strategy
    }
  }
}];`,
      },
    },
  ];
}

function providerDeliveryCode() {
  return `
const input = $input.first().json || {};
const response = input.response || {};
const asyncCallback = input.async_callback;
if (!asyncCallback) throw new Error('async_callback is required for async result delivery.');

const normalizeSource = (value) => String(value || '').replace(/[^A-Za-z0-9]+/g, '_').replace(/^_+|_+$/g, '').toUpperCase();
const transport = String(asyncCallback.result_transport || '');
const statusToExternal = (status) => {
  if (status === 'NOT_FOUND') return 'timeout';
  if (status === 'ERROR' || status === 'DELIVERY_FAILED') return 'error';
  return 'success';
};
const externalStatus = statusToExternal(response.runbook_status);
const eventSuffix = String(response.runbook_status || 'UNKNOWN').toLowerCase();
const shouldPublishKafka = transport === 'kafka_event' || transport === 'both';
const deliveryStatus = {
  requested_transport: transport,
  http_callback: (transport === 'http_callback' || transport === 'both') ? 'pending' : 'not_requested',
  kafka_event: shouldPublishKafka ? 'pending' : 'not_requested'
};
const externalEvent = {
  schema_version: '1.0',
  event_id: asyncCallback.idempotency_key_base + ':provider_channel_repair_' + eventSuffix,
  case_id: asyncCallback.case_id,
  wait_id: asyncCallback.wait_id,
  correlation_id: asyncCallback.correlation_id,
  source: asyncCallback.source,
  event_type: asyncCallback.event_type,
  status: externalStatus,
  idempotency_key: asyncCallback.idempotency_key_base + ':provider_channel_repair_' + eventSuffix,
  result: {
    action_id: input.action_id || 'monitor_provider_channel_repair',
    invocation_id: input.invocation_id,
    ...response,
    delivery_status: deliveryStatus
  }
};

if (externalStatus === 'error') {
  const errorPayload = response.error && typeof response.error === 'object' ? response.error : {};
  externalEvent.error = {
    code: String(errorPayload.code || response.runbook_status || 'provider_channel_repair_error'),
    message: String(errorPayload.message || response.message || 'Provider channel repair workflow failed.').slice(0, 1000)
  };
}

if (transport === 'http_callback' || transport === 'both') {
  const sourceKey = normalizeSource(asyncCallback.source);
  const token = (typeof $env !== 'undefined' && ($env['INTEGRATION_CALLBACK_TOKEN__' + sourceKey] || $env.INTEGRATION_CALLBACK_TOKEN))
    || (typeof process !== 'undefined' && (process.env['INTEGRATION_CALLBACK_TOKEN__' + sourceKey] || process.env.INTEGRATION_CALLBACK_TOKEN))
    || '';
  if (!token) {
    deliveryStatus.http_callback = 'failed';
    deliveryStatus.http_callback_error = 'missing_callback_token';
    if (!shouldPublishKafka) throw new Error('missing_callback_token');
  }
  const httpRequest = this?.helpers?.httpRequest?.bind(this.helpers);
  if (token && !httpRequest) {
    deliveryStatus.http_callback = 'failed';
    deliveryStatus.http_callback_error = 'http_request_helper_unavailable';
    if (!shouldPublishKafka) throw new Error('n8n httpRequest helper is not available in Code node.');
  }
  if (token && httpRequest) {
    try {
      await httpRequest({
        method: 'POST',
        url: asyncCallback.callback_url,
        headers: {
          'Content-Type': 'application/json',
          'X-ServiceDesk-Callback-Token': token
        },
        body: externalEvent,
        json: true
      });
      deliveryStatus.http_callback = 'sent';
    } catch (error) {
      deliveryStatus.http_callback = 'failed';
      deliveryStatus.http_callback_error = 'callback_delivery_failed';
      if (!shouldPublishKafka) throw new Error('callback_delivery_failed');
    }
  }
}

return [{
  json: {
    ...input,
    externalEvent,
    shouldPublishKafka,
    delivery_status: deliveryStatus,
    kafkaTopic: asyncCallback.result_topic || '',
    kafkaHeaders: JSON.stringify({
      correlation_id: asyncCallback.correlation_id,
      wait_id: asyncCallback.wait_id,
      idempotency_key: externalEvent.idempotency_key,
      event_type: asyncCallback.event_type
    })
  }
}];
`.trim();
}

function patchWorkflow(workflow) {
  const required = [
    'Ответ accepted',
    'Начальный этап терминальный?',
    'Доставка async результата',
    'Подготовка SQL поиска письма',
    'Ожидание следующего опроса',
  ];
  for (const name of required) {
    if (!byName(workflow.nodes, name)) throw new Error(`Required node not found: ${name}`);
  }

  const replacedNames = new Set([
    'Получение контекста и отправка письма',
    ...providerNodes().map((node) => node.name),
  ]);
  const replacedIds = new Set([
    'provider-channel-monitor-initial-actions',
    ...providerNodes().map((node) => node.id),
  ]);

  workflow.nodes = workflow.nodes
    .filter((node) => !replacedNames.has(node.name) && !replacedIds.has(node.id))
    .concat(providerNodes());

  const deliveryNode = byName(workflow.nodes, 'Доставка async результата');
  if (!deliveryNode) throw new Error('Required node not found: Доставка async результата');
  deliveryNode.parameters = {
    ...(deliveryNode.parameters || {}),
    jsCode: providerDeliveryCode(),
  };

  delete workflow.connections['Получение контекста и отправка письма'];

  workflow.connections['Ответ accepted'] = {
    main: [[{ node: 'Подготовка CMDBuild контекста', type: 'main', index: 0 }]],
  };
  workflow.connections['Подготовка CMDBuild контекста'] = {
    main: [[{ node: 'CMDBuild поиск routerG', type: 'main', index: 0 }]],
  };
  workflow.connections['CMDBuild поиск routerG'] = {
    main: [[{ node: 'Разбор routerG для письма', type: 'main', index: 0 }]],
  };
  workflow.connections['Разбор routerG для письма'] = {
    main: [[{ node: 'CMDBuild контекст терминальный?', type: 'main', index: 0 }]],
  };
  workflow.connections['CMDBuild контекст терминальный?'] = {
    main: [
      [{ node: 'Доставка async результата', type: 'main', index: 0 }],
      [{ node: 'CMDBuild чтение IpAddress', type: 'main', index: 0 }],
    ],
  };
  workflow.connections['CMDBuild чтение IpAddress'] = {
    main: [[{ node: 'CMDBuild чтение Room', type: 'main', index: 0 }]],
  };
  workflow.connections['CMDBuild чтение Room'] = {
    main: [[{ node: 'CMDBuild чтение Floor', type: 'main', index: 0 }]],
  };
  workflow.connections['CMDBuild чтение Floor'] = {
    main: [[{ node: 'CMDBuild чтение Building', type: 'main', index: 0 }]],
  };
  workflow.connections['CMDBuild чтение Building'] = {
    main: [[{ node: 'Нормализация CMDBuild контекста', type: 'main', index: 0 }]],
  };
  workflow.connections['Нормализация CMDBuild контекста'] = {
    main: [[{ node: 'Подготовка email провайдеру', type: 'main', index: 0 }]],
  };
  workflow.connections['Подготовка email провайдеру'] = {
    main: [[{ node: 'Отправка email провайдеру', type: 'main', index: 0 }]],
  };
  workflow.connections['Отправка email провайдеру'] = {
    main: [[{ node: 'Результат email провайдеру', type: 'main', index: 0 }]],
  };
  workflow.connections['Результат email провайдеру'] = {
    main: [[{ node: 'Начальный этап терминальный?', type: 'main', index: 0 }]],
  };

  workflow.connections['Начальный этап терминальный?'] = {
    main: [
      [{ node: 'Доставка async результата', type: 'main', index: 0 }],
      [{ node: 'Подготовка SQL поиска письма', type: 'main', index: 0 }],
    ],
  };
  workflow.connections['Ожидание следующего опроса'] = {
    main: [[{ node: 'Подготовка SQL поиска письма', type: 'main', index: 0 }]],
  };
}

const workflow = fetchWorkflow();
patchWorkflow(workflow);
saveWorkflow(workflow);
console.log(`Workflow ${workflowId} patched: provider context is inline and email is sent with Email Send node.`);
