# Ziko™ ● Todo — Kanban 0.3

Release: 2026-11-13. Deployed on existing Home Assistant dashboard `/ziko-todo/attekintes`.
Source remains `ziko_todo_frontend/zikotodo-board-v02.js` to preserve the registered custom element `ziko-todo-board-v2` and avoid breaking existing Lovelace cards. HA resource ID `eab4e93b188d4108bc668dee98c0f725`.

## Added
- Kanban is now the default view, but List / AI / Personal / Team / Projects / Completed remain available.
- Premium ZIKO dark/neon styling and theme: cyan intake, gold in-progress, violet review, rose blocked, green completion.
- Icons in stage headers, menu and summary tiles, smaller touch-optimized task cards.
- HTML5 drag-and-drop between four Kanban lanes on devices/browsers supporting HTML5 DnD.
- A touch-friendly stage selector on every Kanban card; the fallback is **essential** because mobile browsers do not consistently support drag-and-drop.
- Reduced-motion CSS, horizontal swipable board layout, focus/hover affordances.
- Moving a card updates the original Home Assistant `todo` record, stores stage in its structured description, and confirms with a read-back.
- Reopening a completed card now places it into Review rather than an invisible completed stage.

## Verification
- V8 syntax: pass.
- 14/14 focused simulated UI tests: stage lanes, dynamic brand, colors, icons, drag handlers, touch selector, persist transitions, completed/reopened state, and HTML escaping.
- Live HA backend isolated temporary task: created, moved, read back, marked done, verified, and cleaned up. No test tasks remain.
- Original `todo.zikotodo_ai_feladatok`, `todo.zikotodo_emberi_feladatok`, `todo.zikotodo_csapatfeladatok` remain intact.
- Browser cache refresh is required to load updated HA inline module. End-to-end touch testing on actual phone remains outstanding; no claim of visual sign-off.

## Deliberate limits
- This is the Home Assistant native to-do backend, **not yet** a full Vikunja-integrated frontend. True multi-user permissions, server-assigned identities, dependencies, Gantt, activity audit and autonomous AI execution are separate roadmap items.
- OldTodo is untouched.
- Upstream Vikunja AGPL license and its core/pro distinction remain unchanged.
