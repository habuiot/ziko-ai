# ZIKO Command ↔ Ziko AI ↔ ZikoTodo — Single-truth contract

## Canonical ownership

**ZikoTodo:** one definitive task ID, current task status, priority, assignee(s), deadlines, attachments, and project permissions. Currently HA native `todo` entities; Vikunja is a planned backend and is currently in an error state.

**ZIKO Command:** user interactions, event ledger, execution attempts, operator approvals, notifications, proposals and periodic briefings. A Command `job` always references a ZikoTodo `source_task_id`. Its `state` is **job attempt**, not Todo task state.

**Ziko AI:** planning, reasoning and bounded tool execution. It may request new tasks/proposals, submit evidence and report blockers. It must not mark a canonical task complete without accepted verification in ZikoTodo.

## Human messaging

1. Operator sends instruction in Command. It is a **message**, status `awaiting_ai`. Never silently turn it into an executed operation.
2. When the Ziko AI service adapter exists, it triages this message, consults ZikoTodo and proposes a plan or a canonical task.
3. On approval if needed, Command records an auditable `approval_granted` event tied to verified stable HA user ID.
4. Agent works on one leased job at a time with bounded retries and explicit capabilities.
5. Artifacts and evidence return to Command as `review` (default). Canonical ZikoTodo status is only updated through a verified adapter and ID match.

## Capability policy

| Risk | Examples | Default |
| --- | --- | --- |
| low | Read-only code exploration, independent research, issue analysis, drafting documentation | Auto-dispatch *once an actual executor is authenticated* |
| medium | New feature patches, editing files, modifying dashboard layouts, adding automations, sharing internal documents | Explicit scoped approval |
| high | Delete/irreversible operations, payments, credentials, access grants, changing alarms/locks/security, publishing externally | Explicit action-specific human approval with verification |
| unknown | Anything missing a trusted task ID, unknown capabilities, ambiguous actor | Deny/ask |

Never let the LLM set its own authorization tier, mint capabilities, impersonate the user or approve its own actions.

## Availability and load budgets

- Command pulse runs on a low-cost, non-LLM tick (60 s), only on its private SQLite store.
- A disconnected executor cannot claim any job. A stale lease is recovered only after timeout. Maximum three attempts per job, with exponential backoff.
- Autonomous new ideas: at most 3 per local calendar day and never automatically promoted to execution.
- User requests are capped (40/day/user, <=2000 chars) and idempotent per client key.
- Daily report *prepared* at 19:00 Europe/Budapest; notification transport is still disconnected.
- Work queues and approvals survive restart. No guarantees against physical hardware failure; requires HA backups and host watchdog/UPS monitoring.

## Cross-system event envelope (planned)

```json
{
  "schema": "ziko.command.event.v1",
  "event_id": "uuid",
  "source": "command | ziko-ai | zikotodo",
  "actor_type": "ha-user | agent | service",
  "actor_id": "stable-server-side-identity",
  "source_task_id": "todo:stable-id",
  "work_run_id": "uuid",
  "type": "task_queued | task_started | output_ready | approval_requested | approval_granted | task_verified | task_blocked",
  "idempotency_key": "string",
  "at": "UTC ISO-8601",
  "payload": {}
}
```

Server-side idempotency is mandatory. Consumer retries never cause duplicate external actions. The event log must be append-only and avoid raw passwords, credentials and unnecessary private data.

## Failure response

- If Ziko AI is unavailable, Command reports **offline**, continues its own heartbeat, and retains incoming messages. It does not imply that AI tasks are being executed.
- If Todo or Vikunja is unavailable, neither Command nor Ziko AI invents canonical task states. Operations suspend or remain queued.
- If command process or HA host restarts, expired leases are requeued up to bounded retries; dangerous operations cannot auto-retry without explicit idempotency guarantees.
- If all executable work has been exhausted, Command reports *no safe work available* and can prepare up to 3 justified proposals/day rather than inventing endless tasks.

## Operational phases

- **0.1:** source + safe live Command inbox, local scheduler, honest offline status.
- **0.2:** link authenticated read-only Todo connector.
- **0.3:** link the actual Ziko AI executor with narrow cap tokens.
- **0.4:** approvals, sync, review/verification.
- **0.5:** daily/weekly briefing delivery and bounded proactive planning.
