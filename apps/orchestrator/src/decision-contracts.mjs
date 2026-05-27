const DECISION_TYPES = new Set([
  'answer_proposed',
  'clarification_needed',
  'escalation_needed',
  'action_proposed',
]);

const TOOL_NAMES = new Set([
  'check_zabbix_status',
  'query_cmdb_object',
  'get_service_owner',
  'search_known_incidents',
  'start_systemcenter_runbook',
]);

const ACTION_TYPES = new Set(['read_only', 'action']);
const RISK_LEVELS = new Set(['low', 'medium', 'high', 'critical']);
const EXECUTION_MODES = new Set([
  'manual_only',
  'operator_approval',
  'auto_execute',
  'dry_run',
  'blocked',
]);

const PROHIBITED_AI_FIELDS = new Set([
  'execution_mode',
  'approval_required',
  'allowed',
  'policy_rule_id',
  'tool_results',
  'executed_actions',
  'n8n_webhook_url',
]);

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function isNonEmptyString(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function isConfidence(value) {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1;
}

function addRequiredObjectError(errors, value, path) {
  if (!isObject(value)) {
    errors.push(`${path} must be an object`);
    return true;
  }
  return false;
}

function checkNoProhibitedFields(value, path, errors) {
  for (const key of Object.keys(value)) {
    if (PROHIBITED_AI_FIELDS.has(key)) {
      errors.push(`${path}.${key} is policy/execution state and is not allowed in AI output`);
    }
  }
}

function validateCitations(citations, path, errors) {
  if (citations === undefined) return;
  if (!Array.isArray(citations)) {
    errors.push(`${path} must be an array`);
    return;
  }

  citations.forEach((citation, index) => {
    const itemPath = `${path}[${index}]`;
    if (addRequiredObjectError(errors, citation, itemPath)) return;
    if (!isNonEmptyString(citation.source_id)) {
      errors.push(`${itemPath}.source_id must be a non-empty string`);
    }
  });
}

export function validateProposedAction(action, path = 'proposed_actions[0]') {
  const errors = [];
  if (addRequiredObjectError(errors, action, path)) return { valid: false, errors };

  checkNoProhibitedFields(action, path, errors);

  if (!TOOL_NAMES.has(action.tool_name)) {
    errors.push(`${path}.tool_name must be a known tool`);
  }
  if (!isNonEmptyString(action.action_id)) {
    errors.push(`${path}.action_id must be a non-empty string`);
  }
  if (!ACTION_TYPES.has(action.action_type)) {
    errors.push(`${path}.action_type must be read_only or action`);
  }
  if (!isObject(action.parameters)) {
    errors.push(`${path}.parameters must be an object`);
  }
  if (!isNonEmptyString(action.reason)) {
    errors.push(`${path}.reason must be a non-empty string`);
  }
  if (!RISK_LEVELS.has(action.risk_level)) {
    errors.push(`${path}.risk_level must be low, medium, high, or critical`);
  }
  if (!isNonEmptyString(action.expected_effect)) {
    errors.push(`${path}.expected_effect must be a non-empty string`);
  }
  if (typeof action.requires_state_change !== 'boolean') {
    errors.push(`${path}.requires_state_change must be a boolean`);
  }

  if (action.tool_name === 'start_systemcenter_runbook') {
    if (action.action_type !== 'action') {
      errors.push(`${path}.action_type must be action for start_systemcenter_runbook`);
    }
    if (action.requires_state_change !== true) {
      errors.push(`${path}.requires_state_change must be true for start_systemcenter_runbook`);
    }
    if (!isObject(action.parameters) || !isNonEmptyString(action.parameters.runbook_name)) {
      errors.push(`${path}.parameters.runbook_name is required for start_systemcenter_runbook`);
    }
  }

  return { valid: errors.length === 0, errors };
}

export function validateAiDecision(value) {
  const errors = [];
  if (addRequiredObjectError(errors, value, 'ai_decision')) return { valid: false, errors };

  checkNoProhibitedFields(value, 'ai_decision', errors);

  if (value.schema_version !== '1.0') {
    errors.push('ai_decision.schema_version must be 1.0');
  }
  if (!isObject(value.decision)) {
    errors.push('ai_decision.decision must be an object');
    return { valid: false, errors };
  }
  if (!DECISION_TYPES.has(value.decision.type)) {
    errors.push('ai_decision.decision.type is not supported');
  }
  if (!isNonEmptyString(value.operator_message)) {
    errors.push('ai_decision.operator_message must be a non-empty string');
  }
  if (value.internal_reasoning_summary !== undefined && !isNonEmptyString(value.internal_reasoning_summary)) {
    errors.push('ai_decision.internal_reasoning_summary must be a non-empty string when present');
  }
  if (!isConfidence(value.decision.confidence)) {
    errors.push('ai_decision.decision.confidence must be a number from 0 to 1');
  }

  validateCitations(value.citations, 'ai_decision.citations', errors);

  const proposedActions = value.proposed_actions ?? [];
  if (!Array.isArray(proposedActions)) {
    errors.push('ai_decision.proposed_actions must be an array when present');
  } else if (value.decision.type === 'action_proposed') {
    if (proposedActions.length === 0) {
      errors.push('ai_decision.proposed_actions must contain at least one action for action_proposed');
    }
    proposedActions.forEach((action, index) => {
      const result = validateProposedAction(action, `ai_decision.proposed_actions[${index}]`);
      errors.push(...result.errors);
    });
  } else if (proposedActions.length > 0) {
    errors.push('ai_decision.proposed_actions must be empty unless decision.type is action_proposed');
  }

  switch (value.decision.type) {
    case 'answer_proposed':
    case 'action_proposed':
      if (!isNonEmptyString(value.decision.summary)) {
        errors.push('ai_decision.decision.summary must be a non-empty string');
      }
      break;
    case 'clarification_needed':
      if (!Array.isArray(value.decision.missing_fields) || value.decision.missing_fields.length === 0) {
        errors.push('ai_decision.decision.missing_fields must contain at least one field');
      }
      if (!isNonEmptyString(value.decision.question)) {
        errors.push('ai_decision.decision.question must be a non-empty string');
      }
      break;
    case 'escalation_needed':
      if (!isNonEmptyString(value.decision.summary)) {
        errors.push('ai_decision.decision.summary must be a non-empty string');
      }
      if (!isNonEmptyString(value.decision.reason)) {
        errors.push('ai_decision.decision.reason must be a non-empty string');
      }
      break;
  }

  return { valid: errors.length === 0, errors };
}

export function validateExecutionPolicyResult(value) {
  const errors = [];
  if (addRequiredObjectError(errors, value, 'execution_policy_result')) {
    return { valid: false, errors };
  }

  if (value.schema_version !== '1.0') {
    errors.push('execution_policy_result.schema_version must be 1.0');
  }
  if (!isNonEmptyString(value.action_id)) {
    errors.push('execution_policy_result.action_id must be a non-empty string');
  }
  if (!TOOL_NAMES.has(value.tool_name)) {
    errors.push('execution_policy_result.tool_name must be a known tool');
  }
  if (!EXECUTION_MODES.has(value.execution_mode)) {
    errors.push('execution_policy_result.execution_mode is not supported');
  }
  if (typeof value.allowed !== 'boolean') {
    errors.push('execution_policy_result.allowed must be a boolean');
  }
  if (typeof value.approval_required !== 'boolean') {
    errors.push('execution_policy_result.approval_required must be a boolean');
  }
  if (!isNonEmptyString(value.policy_rule_id)) {
    errors.push('execution_policy_result.policy_rule_id must be a non-empty string');
  }
  if (!isNonEmptyString(value.reason)) {
    errors.push('execution_policy_result.reason must be a non-empty string');
  }
  if (value.risk_level !== undefined && !RISK_LEVELS.has(value.risk_level)) {
    errors.push('execution_policy_result.risk_level must be low, medium, high, or critical');
  }

  if (value.execution_mode === 'auto_execute') {
    if (value.allowed !== true) errors.push('auto_execute requires allowed=true');
    if (value.approval_required !== false) errors.push('auto_execute requires approval_required=false');
  }
  if (value.execution_mode === 'operator_approval') {
    if (value.allowed !== true) errors.push('operator_approval requires allowed=true');
    if (value.approval_required !== true) errors.push('operator_approval requires approval_required=true');
  }
  if (value.execution_mode === 'blocked') {
    if (value.allowed !== false) errors.push('blocked requires allowed=false');
    if (value.approval_required !== false) errors.push('blocked requires approval_required=false');
  }

  return { valid: errors.length === 0, errors };
}

export function toModelOutputInvalid(errors) {
  const normalizedErrors = Array.isArray(errors) && errors.length > 0
    ? errors.map((error) => String(error))
    : ['model output failed validation'];

  return {
    schema_version: '1.0',
    workflow_state: {
      id: 'model_output_invalid',
      category: 'error',
      terminal: false,
      can_advance: false,
      requires_operator_action: true,
      description: 'The model output failed contract validation.',
    },
    can_advance: false,
    errors: normalizedErrors,
  };
}

export function validateAiDecisionForWorkflow(value) {
  const result = validateAiDecision(value);
  if (result.valid) {
    return {
      valid: true,
      value,
    };
  }

  return {
    valid: false,
    failure: toModelOutputInvalid(result.errors),
  };
}
