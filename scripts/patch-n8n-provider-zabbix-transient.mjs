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
    const detail = result.stderr?.trim() || result.stdout?.trim() || result.error?.message || '';
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

function psql(sql, kind = 'query-n8n-provider-zabbix-transient') {
  const { localPath, containerPath } = tempSqlPath(kind);
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

function psqlExec(sql) {
  const { localPath, containerPath } = tempSqlPath('patch-n8n-provider-zabbix-transient');
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
  }).replace(/'/g, "''");
  const escapedWorkflowId = workflowId.replace(/'/g, "''");
  const sql = `
with payload as (
  select '${payload}'::jsonb as value
)
update workflow_entity
set
  nodes = (select value->'nodes' from payload)::json,
  connections = (select value->'connections' from payload)::json,
  "updatedAt" = now()
where id = '${escapedWorkflowId}';

with payload as (
  select '${payload}'::jsonb as value
),
active_version as (
  select "activeVersionId"
  from workflow_entity
  where id = '${escapedWorkflowId}'
)
update workflow_history
set
  nodes = (select value->'nodes' from payload)::json,
  connections = (select value->'connections' from payload)::json,
  "updatedAt" = now()
where "versionId" = (select "activeVersionId" from active_version);
`;
  psqlExec(sql);
}

function byName(nodes, name) {
  return nodes.find((node) => node.name === name);
}

function replaceRequired(source, from, to, label) {
  if (!source.includes(from)) {
    throw new Error(`Expected code fragment not found: ${label}`);
  }
  return source.replace(from, to);
}

const zabbixFailureTerminal = `} catch (error) {
  return [{
    json: terminal('ERROR', 'Не удалось проверить статус Zabbix problem.', {
      error: { code: 'zabbix_status_failed', message: 'Не удалось проверить статус Zabbix problem.', reason: safeMessage(error) }
    })
  }];
}`;

const zabbixFailureProgress = `} catch (error) {
  const now = new Date();
  const deadline = new Date(state.deadline_at);
  const failure = {
    code: 'zabbix_status_failed',
    message: 'Не удалось проверить статус Zabbix problem.',
    reason: safeMessage(error),
    checked_at: now.toISOString()
  };
  if (now >= deadline) {
    return [{
      json: terminal('ERROR', 'Не удалось проверить статус Zabbix problem.', {
        error: failure
      })
    }];
  }
  return [{
    json: {
      ...state,
      terminal: false,
      zabbix_status: state.zabbix_status || null,
      zabbix_status_last_error: failure
    }
  }];
}`;

function patchWorkflow(workflow) {
  const zabbixNode = byName(workflow.nodes, 'Проверка статуса Zabbix');
  if (!zabbixNode?.parameters?.jsCode) {
    throw new Error('Required node not found: Проверка статуса Zabbix');
  }
  zabbixNode.parameters.jsCode = replaceRequired(
    zabbixNode.parameters.jsCode,
    zabbixFailureTerminal,
    zabbixFailureProgress,
    'zabbix transient failure branch',
  );

  const evaluateNode = byName(workflow.nodes, 'Оценка ответа провайдера');
  if (!evaluateNode?.parameters?.jsCode) {
    throw new Error('Required node not found: Оценка ответа провайдера');
  }
  evaluateNode.parameters.jsCode = replaceRequired(
    evaluateNode.parameters.jsCode,
    `  zabbix_status: state.zabbix_status?.status || null,
  deadline_at: state.deadline_at,
  last_error: null,`,
    `  zabbix_status: state.zabbix_status?.status || null,
  deadline_at: state.deadline_at,
  last_error: state.zabbix_status_last_error || null,`,
    'polling diagnostic last_error',
  );
}

const workflow = fetchWorkflow();
patchWorkflow(workflow);
saveWorkflow(workflow);
console.log(`Workflow ${workflowId} patched: transient Zabbix status failures now keep provider polling open until deadline.`);
