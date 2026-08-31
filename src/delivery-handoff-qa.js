const results = $input.all().map((item) => item.json);
const mismatches = results
  .filter((item) => item.status !== item.expected_status)
  .map((item) => ({
    case_id: item.case_id,
    expected: item.expected_status,
    actual: item.status,
  }));

const statusCounts = {};
for (const item of results) {
  statusCounts[item.status] = (statusCounts[item.status] || 0) + 1;
}

return [{
  json: {
    total: results.length,
    passed: results.length - mismatches.length,
    failed: mismatches.length,
    mismatches,
    status_counts: statusCounts,
    external_calls: results.reduce((sum, item) => sum + item.external_calls, 0),
    real_customer_data: results.some((item) => item.data_origin !== 'FICTIONAL'),
    production_ready: false,
    statement: 'Controlled offline proof with fictional data; not approved for production.',
  },
}];
