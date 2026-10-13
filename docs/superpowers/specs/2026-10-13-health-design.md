# Local house health and journal

User approved shared automatic observations without per-entity setup. Implement locally in the existing HA observer, with no model calls, HA service calls, external messages or device control. Show automatic findings in Ziko's UI and context for chat.

Retain sanitized observed state changes in the existing SQLite database for 14 days, capped at 10000 events. Record connection gaps explicitly, never manufacture missed changes. Batch pending writes every 10 seconds; make overflow visible. Flush at clean shutdown. Migration exports the same database, preserving new tables.

Shared rules: percentage battery below 20%, resolve at 25% to avoid flapping; binary battery-low sensors also supported. Do not interpret voltage as percentage. Door/window/opening/garage-door binary sensors open for 600 seconds, resolve when closed. Whole-device unavailability for 600 seconds only when all relevant state entities are unavailable, with no known-live ones. Unknown/missing state or a stale HA snapshot never proves a new fault or recovery.

Persist active/resolved findings and timing across restart. Deduplicate by rule and device/entity. Acknowledgement means seen, not resolved; healthy state resolves automatically. Display verification status and per-rule coverage. Only current approved scope is visible; fresh scope removal resolves old findings as removed from observation.

Operator/Ingress authorization and CSRF checks remain. No raw HA attributes, secrets, camera URLs or foreign devices enter the journal. No secret data or private scope IDs are published. New 0.4.0 is a normal HA repository update.
