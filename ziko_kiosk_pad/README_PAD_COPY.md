# ZIKO Kiosk Pad — exact fork of Miix UI, v0.3.9

Owner requirement: DO NOT modify HA native ZIKO Kiosk Thermostat v1.2.13 or Lights v1.2.16. Use a separate copy named **ZIKO Kiosk Pad** with the existing HTTPS trust+pairing bridge on the old iPad2 iOS9.

Source: immutable LIVE Házikó /local/ziko-kiosk-thermostat/kiosk-v1.2.13.js, kiosk-lights-v1.2.16.js, kiosk-v1.2.9.css, kiosk-lights-v1.2.15.css, SHA256 in source/ and in pad_copy/original archive folder. These native HA files remain byte-unchanged.

Production HTML: /kiosk-pad and /kiosk-pad/thermostat, /kiosk-pad/lights. Same Miix dashboard source markup+CSS, Babel ES5 recompile of COPIES only; polyfills core-js 3.47, webcomponentsjs 2.8, dom4 2.1.6, pepjs 0.5.3, each vendored with original license header. Only copied source adaptations: original native CSS resource URLs to /kiosk-pad/assets/, original SPA path to /kiosk-pad/, iOS9 browser inset-compatible top/right/bottom/left, and index/overlay stacking suitable for pairing prompt. Old HTML cards, classes, visuals, entity IDs and automation semantics preserved. The iPad fullscreen icon uses standard Apple Add to Home Screen metadata, not illegal Safari chrome hiding.

Existing HA Supervisor addon 29b31cdc_ziko_kiosk_pad HTTPS port18497, original KIOSK-01 IP-bound paired cookie; no secrets included in HTML/JS. The new independent HTTPS fork's /api/padcopy/states, /api/padcopy/ha, /api/padcopy/service expose only whitelisted Miix entity IDs/service actions. General proxy NEVER allows lock domain; original Miix card lock short-tap/long-touch services are mapped to pre-existing /api/entry guards (door shut, locked state, automation guard and timer) to retain secure lock behavior, not to anonymously call HA. Original secure /, /access-2226 and /kiosk-2026 stay unchanged as rollback. Existing HA native dashboard files and Node03 unaffected.

Package: pad_copy_bundle.tar.gz contains frontend + copied source + vendor polyfills. Dockerfile expands into /app/pad_copy. Source / original retained in package but never served. Build logs, SHA-256 QA and tested staged app separately in Vault, no hidden secrets.

QA: server mock HTTP routes/static 200, paired states filtered, anonymous HTTP401 and CSRF403, general lock proxy403, safe fake switch command, denies unknown target and path traversal PASS. Physical iPad2 Safari9 rendering, icon fullscreen and actual U200 lock actuation require independent tests; DO NOT claim hardware E2E pass from HTTP status.

Rollback: use original HA native /ziko-kiosk-thermostat/attekintes and /vilagitasok (unchanged), or original HTTPS root / legacy app; if necessary revert this addon source to GitHub merged 0.3.8 commit and update addon. Preserve CA, sessions, pairing options and data. NEVER delete original Miix JS/CSS.
