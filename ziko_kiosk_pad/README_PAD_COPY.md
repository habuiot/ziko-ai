# ZIKO Kiosk Pad — exact fork of Miix UI, v0.3.9

Owner requirement: DO NOT modify HA native ZIKO Kiosk Thermostat v1.2.13 or Lights v1.2.16. Use a separate copy named **ZIKO Kiosk Pad** with the existing HTTPS trust+pairing bridge on the old iPad2 iOS9.

Source: immutable LIVE Házikó /local/ziko-kiosk-thermostat/kiosk-v1.2.13.js, kiosk-lights-v1.2.16.js, kiosk-v1.2.9.css, kiosk-lights-v1.2.15.css, SHA256 in source/ and in pad_copy/original archive folder. These native HA files remain byte-unchanged.

Production HTML: /kiosk-pad and /kiosk-pad/thermostat, /kiosk-pad/lights. Same Miix dashboard source markup+CSS, Babel ES5 recompile of COPIES only; polyfills core-js 3.47, webcomponentsjs 2.8, dom4 2.1.6, pepjs 0.5.3, each vendored with original license header. Only copied source adaptations: original native CSS resource URLs to /kiosk-pad/assets/, original SPA path to /kiosk-pad/, iOS9 browser inset-compatible top/right/bottom/left, and index/overlay stacking suitable for pairing prompt. Old HTML cards, classes, visuals, entity IDs and automation semantics preserved. The iPad fullscreen icon uses standard Apple Add to Home Screen metadata, not illegal Safari chrome hiding.

Existing HA Supervisor addon 29b31cdc_ziko_kiosk_pad HTTPS port18497, original KIOSK-01 IP-bound paired cookie; no secrets included in HTML/JS. The new independent HTTPS fork's /api/padcopy/states, /api/padcopy/ha, /api/padcopy/service expose only whitelisted Miix entity IDs/service actions. General proxy NEVER allows lock domain; original Miix card lock short-tap/long-touch services are mapped to pre-existing /api/entry guards (door shut, locked state, automation guard and timer) to retain secure lock behavior, not to anonymously call HA. Original secure /, /access-2226 and /kiosk-2026 stay unchanged as rollback. Existing HA native dashboard files and Node03 unaffected.

Package: pad_copy_bundle.tar.gz contains frontend + copied source + vendor polyfills. Dockerfile expands into /app/pad_copy. Source / original retained in package but never served. Build logs, SHA-256 QA and tested staged app separately in Vault, no hidden secrets.

QA: server mock HTTP routes/static 200, paired states filtered, anonymous HTTP401 and CSRF403, general lock proxy403, safe fake switch command, denies unknown target and path traversal PASS. Physical iPad2 Safari9 rendering, icon fullscreen and actual U200 lock actuation require independent tests; DO NOT claim hardware E2E pass from HTTP status.

Rollback: use original HA native /ziko-kiosk-thermostat/attekintes and /vilagitasok (unchanged), or original HTTPS root / legacy app; if necessary revert this addon source to GitHub merged 0.3.8 commit and update addon. Preserve CA, sessions, pairing options and data. NEVER delete original Miix JS/CSS.
\nCompatibility refinement v0.3.10: stylesheet kiosk-pad-legacy.css is appended only to the fork copy shadow roots; with @supports not(display:grid) it emulates the original layout using iOS9-supported flexbox. Native Miix v1.2.13/v1.2.16 JS and original CSS are still byte-identical. New fallback is not visible on modern CSS Grid browsers.\n
### 2026-11-22 v0.3.11 diagnostic incident
Owner photo and repeat report: iPad2 Safari9 shows only "A ZIKO Kiosk másolata inicializálódik…" despite every asset HTTP200. The prior retry timer stopped after 27.6s without error.
New CODE ONLY in copied Kiosk Pad (original Miix JS/CSS unchanged):
* Early, same-origin ES5 diagnostic asset records script load failures/JS exceptions and only the registration boolean; paired KIOSK-01 protected POST /api/padcopy/diag accepts sanitized structured error metadata, **never** cookie/pair code, sensor values or passwords; logs only low-risk file/line/type. No new network port, no different authentication.
* After 28s, visible failure with ÚJRAPRÓBÁLOM button rather than forever loading. No real U200 command.
This is instrumentation and failure recovery, not proof of iOS9 compatibility. The next actual iPad load is needed for precise JavaScript exception from Safari. Prior v0.3.10 remains available through Git history and Vault.

## Kiosk Pad 0.3.12 / Safari iOS 9 Intl runtime fix
2026-11-22 genuine KIOSK-01 iPad2 diagnostic captured via the **paired, sanitized** /api/padcopy/diag, exact message: ReferenceError: Can't find variable: Intl (in kiosk-thermostat-copy.es5.js line 1); customElements exists but thermostat and lights elements were not registered. All scripts and authenticated state GETs were HTTP200, so the prior root cause is not HTTP/network.
Only the copied iPad Kiosk package adds local Intl.js 1.2.5 (MIT, bundled LICENSE) and hu-HU JSONP CLDR locale pack *before* the exact copied Miix component assets. A bounded, browser-feature-detected wrapper adds Budapest timezone support when the old polyfill itself supports only UTC; uses EU DST last-Sunday-March and last-Sunday-October rules in UTC. Native Intl implementations remain unchanged. This is a browser compatibility layer, NOT a redesign of Miix UI, and does not touch native Miix source.
Node VM with window.Intl explicitly unavailable: number formatting hu-HU PASS, winter Budapest UTC+1 PASS, summer UTC+2 PASS, November UTC+1 PASS. Python compiled/isolated fake HA HTML/auth/security test PASS; generic lock proxy still blocked, no physical U200 command.
Physical iPad2 reloading and component mounting MUST be verified from actual IPAD_BOOT_DIAG logs after deploy; do not claim device E2E from runtime simulation. Prior 0.3.11 and immutable original Miix and old HTTPS root remain rollback.


## 0.3.13 Kiosk Pad iPad2 compact Lights
Fork-only iOS9 ES5 light interface. All old Miix copies and control logic preserved. Six first-page and four second-page group cards, quick scenes, room custom RGB/white and full corridor PIR/timer controls. Only Pad, no original Miix/Node03 or U200 edits; v0.3.12 rollback. Physical iPad beta QA remains open.
