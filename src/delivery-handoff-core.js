const DEMO_DATE = '2026-08-16';
const BASE_BUSINESS_FIELDS = 14;
const MAX_BUSINESS_FIELDS = 25;
const seenDealIds = new Set();

function validEmail(value) {
  return typeof value === 'string' && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value);
}

function validIsoDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

function baseResult(deal) {
  return {
    case_id: deal.case_id,
    deal_id: deal.deal_id,
    expected_status: deal.expected_status,
    status: null,
    reason_codes: [],
    project_id: null,
    folder_id: null,
    crm_status: 'DEAL_WON',
    approval_actor: deal.approved_by || null,
    created_resources: [],
    rollback_actions: [],
    untrusted_text_executed: false,
    external_calls: 0,
    data_origin: deal.data_origin,
  };
}

function finish(result, status, reasons) {
  result.status = status;
  result.reason_codes = reasons;
  return { json: result };
}

return $input.all().map((item) => {
  const deal = item.json;
  const result = baseResult(deal);
  const projectId = `PRJ-${deal.case_id}`;
  const folderId = `FOLDER-${deal.case_id}`;
  const customFieldCount = Object.keys(deal.custom_fields || {}).length;

  if (deal.data_origin !== 'FICTIONAL') {
    return finish(result, 'NEEDS_DATA', ['NON_FICTIONAL_DATA_BLOCKED']);
  }

  if (BASE_BUSINESS_FIELDS + customFieldCount > MAX_BUSINESS_FIELDS) {
    return finish(result, 'OUT_OF_SCOPE', ['FIELD_LIMIT_EXCEEDED']);
  }

  const missing = [];
  if (typeof deal.company_name !== 'string' || !deal.company_name.trim()) missing.push('company_name');
  if (!validEmail(deal.primary_contact_email)) missing.push('primary_contact_email');
  if (typeof deal.package_code !== 'string' || !deal.package_code.trim()) missing.push('package_code');
  if (!validIsoDate(deal.start_date)) missing.push('start_date');
  if (!validEmail(deal.delivery_owner_email)) missing.push('delivery_owner_email');
  if (!Number.isFinite(deal.contract_value) || deal.contract_value <= 0) missing.push('contract_value');
  if (deal.currency !== 'EUR') missing.push('currency');
  if (missing.length > 0) return finish(result, 'NEEDS_DATA', missing);

  if (deal.start_date < DEMO_DATE) {
    return finish(result, 'MANUAL_REVIEW', ['START_DATE_IN_PAST']);
  }

  if (deal.approval_status === 'REJECTED') {
    return finish(result, 'REJECTED', ['HUMAN_REJECTED']);
  }
  if (deal.approval_status !== 'APPROVED' || !validEmail(deal.approved_by)) {
    return finish(result, 'AWAITING_APPROVAL', ['HUMAN_APPROVAL_REQUIRED']);
  }

  if ((deal.existing_project_ids || []).includes(projectId) || seenDealIds.has(deal.deal_id)) {
    return finish(result, 'DUPLICATE_BLOCKED', ['IDEMPOTENCY_KEY_EXISTS']);
  }

  if (deal.simulate_fail_at === 'PROJECT') {
    return finish(result, 'FAILED_SAFE', ['PROJECT_CREATE_FAILED']);
  }
  result.project_id = projectId;
  result.created_resources.push(`PROJECT:${projectId}`);

  if (deal.simulate_fail_at === 'FOLDER') {
    result.rollback_actions.push(`DELETE_PROJECT:${projectId}`);
    result.created_resources = [];
    result.project_id = null;
    return finish(result, 'ROLLED_BACK', ['FOLDER_CREATE_FAILED']);
  }
  result.folder_id = folderId;
  result.created_resources.push(`FOLDER:${folderId}`);

  if (deal.simulate_fail_at === 'CRM') {
    result.rollback_actions.push(`DELETE_FOLDER:${folderId}`, `DELETE_PROJECT:${projectId}`);
    result.created_resources = [];
    result.project_id = null;
    result.folder_id = null;
    return finish(result, 'ROLLED_BACK', ['CRM_UPDATE_FAILED']);
  }

  result.crm_status = 'HANDOFF_COMPLETED';
  seenDealIds.add(deal.deal_id);
  return finish(result, 'CREATED', ['HANDOFF_COMPLETE']);
});
