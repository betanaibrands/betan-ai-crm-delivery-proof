# Acceptance cases

All records are fictional. The expected route is derived before execution and
compared with the actual result by the repository test.

| Case | Scenario | Expected route |
|---|---|---|
| DH-01 | Complete and approved deal | `CREATED` |
| DH-02 | Company name missing | `NEEDS_DATA` |
| DH-03 | Primary contact missing | `NEEDS_DATA` |
| DH-04 | Package code missing | `NEEDS_DATA` |
| DH-05 | Start date missing | `NEEDS_DATA` |
| DH-06 | Invalid calendar date | `NEEDS_DATA` |
| DH-07 | Human approval pending | `AWAITING_APPROVAL` |
| DH-08 | Human rejected the handoff | `REJECTED` |
| DH-09 | Target project already exists | `DUPLICATE_BLOCKED` |
| DH-10 | Same deal appears twice in one run | `DUPLICATE_BLOCKED` |
| DH-11 | Project creation fails before a write survives | `FAILED_SAFE` |
| DH-12 | Folder creation fails after project creation | `ROLLED_BACK` |
| DH-13 | Final CRM update fails after both resources exist | `ROLLED_BACK` |
| DH-14 | Free text contains a hostile instruction | `CREATED`, text remains data |
| DH-15 | More than 25 business fields | `OUT_OF_SCOPE` |
| DH-16 | Currency is outside the agreed scope | `NEEDS_DATA` |
| DH-17 | Start date is in the past | `MANUAL_REVIEW` |
| DH-18 | Delivery owner missing | `NEEDS_DATA` |
| DH-19 | Unicode company and contact data | `CREATED` |
| DH-20 | Contract value is zero | `NEEDS_DATA` |

An additional regression case proves that a failure before resource creation
does not poison the idempotency state: the same deal can succeed on a clean
retry.

## Compensating behavior

- If project creation fails, no resource survives.
- If folder creation fails, the project is removed.
- If the final CRM update fails, the folder and project are removed in reverse
  order.
- A production integration would verify each provider's real rollback or
  archive semantics separately; this offline proof does not claim that work is
  complete.
