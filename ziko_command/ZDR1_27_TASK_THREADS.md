# ZDR1-27 – Command inline reply threads (candidate, NOT DEPLOYED)

This is an additive source-only proposal stacked on the **existing draft Command 0.2 signed Workflow bridge**. It does not create a new task database or launch an AI executor. The live Home Assistant Command addon 0.1 is unchanged.

## Implemented in candidate

- In authenticated Command `/api/messages` list, each owner's existing Command message displays a **Válasz Zikónak** button with an inline reply composer and readback.
- New `POST /api/messages/replies` requires genuine HA Ingress identity, the existing CSRF marker, strict JSON fields, parent UUID, a 1–1200 character reply and a stable client idempotency key.
- Replies persist in the **existing Command SQLite database** as append-only, original-message-linked records. Cross-user parent references fail closed, idempotency replays do not duplicate, XSS content renders only via `textContent`.
- A submitted reply is explicitly labeled **awaiting_ai**. It is **NOT** falsely displayed as a real Ziko response. No ToDo state, project, model, privileged endpoint or approval is changed.
- The existing Command owner-only signed Workflow approval prototype is left intact.
- All 93 original+new Python tests pass, including 11 newly added reply API/security cases, in isolated source tree. Python source compile PASS. Browser/JS parse and actual HA mobile ingress UI end-to-end still need tests.

## Missing / fail-closed

- Real authenticated Ziko model response to the reply, threaded **Ziko-originated** messages and the per-task canonical **ZikoTodo UID** authorization binding are not implemented. This is only the conversation storage/composer backend prototype.
- Owner approval / task closure must integrate **verified ZikoTodo identity, Workflow signing and QA evidence**, never auto-close from a chat message.
- No HA dashboard deploy or cross-node AI inference exposure; llama.cpp stays loopback within Node02 CT2203.
- A real end-to-end owner/non-owner browser test, task ACL, notification, mobile UX and rollback approval are required before a production release.

## Rollback

This branch adds a SQLite table and read/write endpoint, but the live add-on was not updated. To revert the candidate, close the draft PR or revert these source files; no production DB or HA state needs restoring. When/if deployed later, stop new writes, revert container image and keep the append-only message history for export/retention.

## Provenance

Knowledge Master `6e937e64-4734-496b-ab03-fbebba29346c` v12 (ZDR1-26/27); Command requirements `f1e129ce-2dd3-434f-8b06-c0c6c7525a45`; original Command Todo `8a122888-df8a-11f1-bcb1-9829a67b6aef`; Work Hub `ziko-command`.
