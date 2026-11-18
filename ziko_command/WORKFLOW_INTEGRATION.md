# Command ↔ Workflow owner gateway 0.2.0-rc1

## Capabilities
Existing HA Ingress remains the only trusted request channel.
Only the configured, stable HA operator_user_id may access GET /api/work.
The Command app verifies a recent (maximum 90 seconds) HMAC-SHA256 signed
Workflow status feed, keyed separately from owner-decision signing.

POST /api/work/approve accepts a canonical Workflow job UUID and exact
artifact SHA256. It verifies the HA Ingress identity, rejects work not in
meeting_ready and writes an owner-only approval receipt inside /data/approvals.
The receipt is not an execution command or deployment. The Workflow engine
must independently read back the canonical Todo, Work Hub and Knowledge gates,
verify the exact artifact and the decision signature, and require deployment
receipt reconciliation. No credentials or private task data are logged.

A false or absent source never claims Ziko AI, ZikoTodo or executor is active.

## Provisioning required (NOT performed by this prototype)
- Keep addon ingress=true, homeassistant_api=false, auth_api=false,
  host_network=false, ports={} and panel_admin=true.
- Set the existing owner HA user ID in the addon option owner_user_id.
  The empty default disables the owner-only board/approval.
- Privately place a signed Workflow feed at
  /data/workflow_signed_feed.json (fresh at most 90 seconds).
- Provision a dedicated feed HMAC verifier key as the addon process owner,
  /data/keys/workflow-feed.key, 0600, at least 32 random bytes.
- Provision a different Command-approval HMAC signing key,
  /data/keys/command-approval.key, 0600, at least 32 random bytes.
- Create /data/approvals, 0700, owner the addon process.
- Arrange a separately authorized, integrity-checked PVE-to-HA signed-feed
  delivery and HA-to-PVE receipt retrieval route. NONE exists by default.
- On PVE Workflow engine_v1/command_feed.py supports --signing-key with
  a separately provisioned 0600 key file. Never put keys in GitHub, Knowledge,
  Todo, Vault, chat transcript, frontend, or addon options.
- Recheck all ACLs and key ownership after Supervisor upgrades/restarts.

## Testing, rollout and rollback
- 45/45 Python Command unit+local-loopback HTTP tests PASS.
- 80/80 combined legacy and new Workflow tests PASS.
- Node.js JavaScript source parse PASS (CT103 read-only check).
- No Docker image build, native HA Ingress browser E2E, remote feed delivery,
  mobile device test or model inference was performed.
- Keep live addon 0.1.0 unchanged until transport is truly available and
  role-scoped end-to-end QA passes. This source is staged as an rc1 PR.
- Rollback after approval: revert addon to previous version, retain original
  /data/command.sqlite3, revoke transport keys and retain decision/audit receipts.
  Do not globally restore HA databases or create a second Command app.
