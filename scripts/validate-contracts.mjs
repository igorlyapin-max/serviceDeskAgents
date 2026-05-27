#!/usr/bin/env node
import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  validateAiDecision,
  validateAiDecisionForWorkflow,
  validateExecutionPolicyResult,
} from '../apps/orchestrator/src/decision-contracts.mjs';

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

async function readJson(relativePath) {
  const absolutePath = path.join(rootDir, relativePath);
  const raw = await readFile(absolutePath, 'utf8');
  return JSON.parse(raw);
}

async function validateJsonFiles(relativeDir) {
  const absoluteDir = path.join(rootDir, relativeDir);
  const entries = await readdir(absoluteDir, { withFileTypes: true });
  const files = entries
    .filter((entry) => entry.isFile() && entry.name.endsWith('.json'))
    .map((entry) => path.join(relativeDir, entry.name))
    .sort();

  for (const file of files) {
    await readJson(file);
    console.log(`json ok: ${file}`);
  }
}

async function runCases({ relativeDir, validator, expectedValid }) {
  const absoluteDir = path.join(rootDir, relativeDir);
  const entries = await readdir(absoluteDir, { withFileTypes: true });
  const files = entries
    .filter((entry) => entry.isFile() && entry.name.endsWith('.json'))
    .map((entry) => path.join(relativeDir, entry.name))
    .sort();

  for (const file of files) {
    const data = await readJson(file);
    const result = validator(data);
    if (result.valid !== expectedValid) {
      const expectation = expectedValid ? 'valid' : 'invalid';
      throw new Error(`${file} expected ${expectation}, got errors: ${result.errors.join('; ')}`);
    }
    console.log(`${expectedValid ? 'valid' : 'invalid'} case ok: ${file}`);
  }
}

await validateJsonFiles('contracts/decisions');
await validateJsonFiles('contracts/tools');
await validateJsonFiles('contracts/integrations');
await validateJsonFiles('contracts/execution');
await validateJsonFiles('contracts/workflow');
await validateJsonFiles('contracts/knowledge');
await validateJsonFiles('contracts/feedback');
await validateJsonFiles('contracts/cases');

await runCases({
  relativeDir: 'contracts/examples/ai-decisions/valid',
  validator: validateAiDecision,
  expectedValid: true,
});

await runCases({
  relativeDir: 'contracts/examples/ai-decisions/invalid',
  validator: validateAiDecision,
  expectedValid: false,
});

await runCases({
  relativeDir: 'contracts/examples/execution-policy/valid',
  validator: validateExecutionPolicyResult,
  expectedValid: true,
});

await validateJsonFiles('contracts/examples/failures/valid');

const invalidDecision = await readJson('contracts/examples/ai-decisions/invalid/direct-execution-mode.json');
const workflowResult = validateAiDecisionForWorkflow(invalidDecision);
if (
  workflowResult.valid ||
  workflowResult.failure?.can_advance !== false ||
  workflowResult.failure?.workflow_state?.id !== 'model_output_invalid'
) {
  throw new Error('invalid AI decision did not convert to model_output_invalid');
}
console.log('failure path ok: model_output_invalid');

const stateCatalog = await readJson('contracts/workflow/workflow-state-catalog.json');
const transitionRules = await readJson('contracts/workflow/workflow-transition-rules.json');
const stateIds = new Set(stateCatalog.states.map((state) => state.id));
for (const rule of transitionRules.rules) {
  if (!stateIds.has(rule.state_id)) {
    throw new Error(`workflow transition references unknown state_id: ${rule.state_id}`);
  }
}
console.log('workflow catalog ok: transition rules reference known states');

const endpointCatalog = await readJson('contracts/integrations/integration-endpoint-catalog.json');
const toolCatalog = await readJson('contracts/tools/tool-catalog.json');
const proposedActionSchema = await readJson('contracts/tools/proposed-action.schema.json');
const endpointById = new Map();
for (const endpoint of endpointCatalog.endpoints) {
  if (endpointById.has(endpoint.endpoint_id)) {
    throw new Error(`duplicate endpoint_id: ${endpoint.endpoint_id}`);
  }
  endpointById.set(endpoint.endpoint_id, endpoint);
}

const toolNames = new Set();
for (const tool of toolCatalog.tools) {
  if (toolNames.has(tool.tool_name)) {
    throw new Error(`duplicate tool_name: ${tool.tool_name}`);
  }
  toolNames.add(tool.tool_name);
  if (!tool.parameters_schema || !tool.result_schema || !tool.policy) {
    throw new Error(`${tool.tool_name} must define parameters_schema, result_schema, and policy`);
  }
  for (const binding of tool.endpoint_bindings) {
    const endpoint = endpointById.get(binding.endpoint_id);
    if (!endpoint) {
      throw new Error(`${tool.tool_name} references unknown endpoint_id: ${binding.endpoint_id}`);
    }
    if (!endpoint.operations[binding.operation_id]) {
      throw new Error(
        `${tool.tool_name} references unknown operation_id ${binding.operation_id} on ${binding.endpoint_id}`,
      );
    }
  }
}
for (const toolName of proposedActionSchema.properties.tool_name.enum) {
  if (!toolNames.has(toolName)) {
    throw new Error(`tool catalog missing proposed-action tool: ${toolName}`);
  }
}
console.log('integration catalog ok: tool bindings reference known endpoints and operations');

const knowledgeSourceCatalog = await readJson('contracts/knowledge/knowledge-source-catalog.json');
const sourceIds = new Set();
for (const source of knowledgeSourceCatalog.sources) {
  if (sourceIds.has(source.source_id)) {
    throw new Error(`duplicate knowledge source_id: ${source.source_id}`);
  }
  sourceIds.add(source.source_id);
  if (source.enabled === false && !source.disabled_reason) {
    throw new Error(`${source.source_id} disabled source must define disabled_reason`);
  }
  if (source.connector_type === 'local_files' && !source.path) {
    throw new Error(`${source.source_id} local_files source must define path`);
  }
}
console.log('knowledge source catalog ok: source ids and connector metadata are valid');

console.log('Contract validation completed.');
