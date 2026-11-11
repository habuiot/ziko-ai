# Ziko™ ● Todo — Home Assistant front-end v0.2

**Delivery:** 2026-11-11. Operational dashboard: `/ziko-todo/attekintes`; source: `ziko_todo_frontend/zikotodo-board-v02.js`; Home Assistant inline module resource ID `eab4e93b188d4108bc668dee98c0f725`.

## Implemented in the live Házikó instance

- Responsive, dark-neon ZIKO-branded board with overview, live counts, quick entry and keyboard-accessible controls.
- AI, personal and team to-do lists, all local Home Assistant `local_todo` integrations.
- Search by title, project, assignee name and notes.
- Project board and filtered task view.
- Four Kanban stages: Beérkezett → Folyamatban → Ellenőrzés; Blokkolt as exception; completion via check.
- Item creation, edit, complete/reopen, change stage, guarded deletion, priority, due date, project, name-only assignee and notes.
- Native HA WebSocket retrieval `todo/item/list`, native HA services `todo.add_item`, `todo.update_item`, `todo.remove_item`.
- Structured description metadata `ZIKO-TODO/1` plus legacy `Projekt:` parser. Original 7 tasks preserved.
- Single new-brand reference: HA helper `input_text.ziko_kozponti_markanev`. Existing other product names untouched.
- AI and personal native fallback views remain as tabs; separate native team view added.
- Vikunja 2.8.0-2 app remains installed, with self-registration disabled, separately isolated and **not yet connected as the UI database**.

## Existing data

- `todo.zikotodo_ai_feladatok`: 5 open at release.
- `todo.zikotodo_emberi_feladatok`: 2 open at release.
- `todo.zikotodo_csapatfeladatok`: created; 0 open at release.

## Verification 2026-11-11

- UI source parsed in V8 with no syntax error.
- Mock HA integration automated checks (10/10): component registration, parsing, brand binding, creation form, search, list grouping, websocket list, Kanban, projects, and HTML injection escaping.
- HA backend CRUD smoke test: create → read → complete → verify → delete; 5/5 passed with no remaining test record.
- Dashboard configuration and resource registration read back successfully through HA API.
- **Browser visual/interactive verification on the user's actual client remains pending.** The screenshot service did not confirm authenticated frontend context; do not claim that device rendering is visually approved.

## Important limitations

This is a functional native-HA task-management UI, **not yet a Vikunja front-end**. It has project/priority/stage metadata in descriptions but not Vikunja project records. Team assignment is free-text only and does NOT enforce per-person permission boundaries or send invites. Do not use the shared list for confidential staff tasks before the backend permission bridge exists. Setting a task as AI-assigned is NOT autonomous task execution.

Vikunja Pro-only features require licensing and are not included; upstream Vikunja remains AGPL-3.0-or-later, while the ZIKO repository currently uses the MIT license. No one should assume the Vikunja API or MCP tools are available to ChatGPT before a dedicated authenticated integration is connected.

## Next technical integration checkpoints

1. Define HA Ingress-authenticated ZIKO task gateway and per-user authorization, with security tests.
2. Provision an internal Vikunja service identity, not an extra user signup, with isolated stored credentials.
3. Enable least-privilege Vikunja project/user/team APIs via the gateway, without public service tokens.
4. Import native `todo` tasks idempotently; compare UID/title/status before switching source of truth. Never delete source until verified.
5. Add project sharing, real invitations/assignments, attachments, Gantt and server-enforced histories to the branded UI.
6. Implement a separate scoped ChatGPT/AI connector and explicit background automation scheduling, with approvals and audit logs.
7. Test mobile/desktop visual rendering, resource usage, backups and failover before enabling app autostart.

## Rollback

The original native task data is unchanged, and the AI, personal and team fallback views remain accessible at `/ziko-todo/ai`, `/ziko-todo/emberi`, `/ziko-todo/csapat`.
To roll back the overview only, switch the dashboard view configuration to native `todo-list` cards. Do not delete the `todo.*` entities or restore the entire Home Assistant backup to fix a dashboard resource issue.
