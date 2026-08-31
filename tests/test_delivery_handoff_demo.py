#!/usr/bin/env python3
"""Behavior and safety test for the fictional Deal-Won-to-Project n8n demo."""

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "workflow" / "delivery-handoff-demo.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require(WORKFLOW.exists(), f"workflow source missing: {WORKFLOW}")
workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))

require(workflow["active"] is False, "demo workflow must stay inactive")
require(
    workflow["settings"].get("availableInMCP") is False,
    "demo workflow must not be exposed through MCP",
)
require(not workflow.get("credentials"), "demo workflow must not contain credentials")

node_types = {node["type"] for node in workflow["nodes"]}
require("n8n-nodes-base.manualTrigger" in node_types, "manual trigger is required")
require("n8n-nodes-base.code" in node_types, "code nodes are required")
require(
    not any(
        token in node_type.lower()
        for node_type in node_types
        for token in ("httprequest", "email", "hubspot", "google", "clickup", "webhook")
    ),
    "offline demo must not call or expose an external system",
)

nodes_by_name = {node["name"]: node for node in workflow["nodes"]}
required_nodes = [
    "20 fictional test deals",
    "Execute controlled handoff",
    "Acceptance report",
]
for name in required_nodes:
    require(name in nodes_by_name, f"required node missing: {name}")

codes = {
    name: nodes_by_name[name]["parameters"]["jsCode"]
    for name in required_nodes
}

harness = f"""
const codes = {json.dumps(codes)};
function run(code, inputItems) {{
  const $input = {{ all: () => inputItems }};
  return (() => {{
    {""}
    return eval(`(() => {{${{code}}}})()`);
  }})();
}}
const fixtures = run(codes['20 fictional test deals'], []);
const results = run(codes['Execute controlled handoff'], fixtures);
const report = run(codes['Acceptance report'], results);
const retryBase = {{
  company_id: 'RETRY-COMPANY', company_name: 'Retry Beispiel GmbH',
  primary_contact_email: 'buyer@example.invalid', package_code: 'CRM-IMPLEMENTATION',
  contract_value: 18000, currency: 'EUR', start_date: '2026-09-01',
  delivery_owner_email: 'delivery@example.invalid', approval_status: 'APPROVED',
  approved_by: 'lead@example.invalid', existing_project_ids: [], custom_fields: {{}},
  notes: 'Fiktiver Wiederholungsfall.', data_origin: 'FICTIONAL'
}};
const retryFixtures = [
  {{ json: {{ ...retryBase, case_id: 'RETRY-01', deal_id: 'RETRY-DEAL', simulate_fail_at: 'PROJECT', expected_status: 'FAILED_SAFE' }} }},
  {{ json: {{ ...retryBase, case_id: 'RETRY-02', deal_id: 'RETRY-DEAL', simulate_fail_at: null, expected_status: 'CREATED' }} }},
];
const retryResults = run(codes['Execute controlled handoff'], retryFixtures);
process.stdout.write(JSON.stringify({{ fixtures, results, report, retryResults }}));
"""

completed = subprocess.run(
    ["node", "-e", harness],
    check=True,
    capture_output=True,
    text=True,
    timeout=30,
)
payload = json.loads(completed.stdout)
fixtures = [item["json"] for item in payload["fixtures"]]
results = [item["json"] for item in payload["results"]]
report = payload["report"][0]["json"]
retry_results = [item["json"] for item in payload["retryResults"]]

require(len(fixtures) == 20, f"expected 20 fixtures, got {len(fixtures)}")
require(len(results) == 20, f"expected 20 results, got {len(results)}")
require(
    len({item["case_id"] for item in fixtures}) == 20,
    "fixture case IDs must be unique",
)

expected_statuses = {
    "DH-01": "CREATED",
    "DH-02": "NEEDS_DATA",
    "DH-03": "NEEDS_DATA",
    "DH-04": "NEEDS_DATA",
    "DH-05": "NEEDS_DATA",
    "DH-06": "NEEDS_DATA",
    "DH-07": "AWAITING_APPROVAL",
    "DH-08": "REJECTED",
    "DH-09": "DUPLICATE_BLOCKED",
    "DH-10": "DUPLICATE_BLOCKED",
    "DH-11": "FAILED_SAFE",
    "DH-12": "ROLLED_BACK",
    "DH-13": "ROLLED_BACK",
    "DH-14": "CREATED",
    "DH-15": "OUT_OF_SCOPE",
    "DH-16": "NEEDS_DATA",
    "DH-17": "MANUAL_REVIEW",
    "DH-18": "NEEDS_DATA",
    "DH-19": "CREATED",
    "DH-20": "NEEDS_DATA",
}
actual_by_case = {item["case_id"]: item for item in results}
require(
    set(actual_by_case) == set(expected_statuses),
    "result case IDs do not match the acceptance set",
)
require(
    {case_id: actual_by_case[case_id]["status"] for case_id in expected_statuses}
    == expected_statuses,
    f"unexpected statuses: {actual_by_case!r}",
)

for case_id in ("DH-01", "DH-14", "DH-19"):
    item = actual_by_case[case_id]
    require(item["project_id"] == f"PRJ-{case_id}", f"wrong project ID for {case_id}")
    require(item["folder_id"] == f"FOLDER-{case_id}", f"wrong folder ID for {case_id}")
    require(item["crm_status"] == "HANDOFF_COMPLETED", f"CRM not finalized for {case_id}")
    require(item["rollback_actions"] == [], f"successful case contains rollback for {case_id}")

require(
    actual_by_case["DH-11"]["created_resources"] == [],
    "project-system failure must leave no resource behind",
)
require(
    actual_by_case["DH-12"]["rollback_actions"] == ["DELETE_PROJECT:PRJ-DH-12"],
    "folder failure must roll back the previously created project",
)
require(
    actual_by_case["DH-13"]["rollback_actions"]
    == ["DELETE_FOLDER:FOLDER-DH-13", "DELETE_PROJECT:PRJ-DH-13"],
    "CRM failure must roll back folder and project in reverse order",
)
require(
    actual_by_case["DH-13"]["created_resources"] == [],
    "rolled-back CRM failure must report no surviving resource",
)

injection_case = actual_by_case["DH-14"]
require(injection_case["status"] == "CREATED", "untrusted notes changed control flow")
require(
    injection_case["untrusted_text_executed"] is False,
    "untrusted note must never be interpreted as an instruction",
)
require(
    injection_case["approval_actor"] == "lead@example.invalid",
    "untrusted note must not overwrite approval identity",
)

require(report["total"] == 20, "QA report total must be 20")
require(report["passed"] == 20, "all 20 cases must match their expected route")
require(report["failed"] == 0, "QA report must contain no failed case")
require(report["external_calls"] == 0, "offline demo must make zero external calls")
require(report["real_customer_data"] is False, "demo must use fictional data only")
require(report["production_ready"] is False, "demo must not claim production readiness")
require(
    report["statement"]
    == "Controlled offline proof with fictional data; not approved for production.",
    "public proof statement must be explicit and readable in English",
)
require(
    [item["status"] for item in retry_results] == ["FAILED_SAFE", "CREATED"],
    "a failure before resource creation must not block a clean retry",
)

print("PASS: 20/20 fictional handoff cases, safety routes, and rollbacks verified")
