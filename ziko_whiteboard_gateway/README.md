# ZIKO Whiteboard — Home Assistant authenticated Ingress (0.5.0)

A separate authenticated transport layer for the EXISTING Proxmox CT107 Whitebophir editor. NOT a second editor, drawing engine or board database. All 10 channels and drawings remain on CT107.

- Supervisor login required. Ingress gateway verifies the immediate peer is 172.30.32.2, trusted X-Remote-User-Id and valid X-Ingress-Path. Anonymous requests denied.
- No public host port. Ingress streaming supports the existing Socket.IO WebSocket and Server-Sent Events API. Fixed backend 192.168.10.18 private LAN only.
- Browser cookie: only wbo-user-secret-v1 proxied, scoped to the specific HA ingress path; HA auth cookies NEVER forwarded upstream.
- The backend CSRF Origin is adjusted AFTER Supervisor session validation only, custom X-ZIKO-Action still required.
- The browser sees the SAME HTTPS origin as Home Assistant. HA ingress -> CT107 backend hop remains HTTP/private LAN, not end-to-end TLS.
- Frontend code must use relative boards and ziko-api paths (Whiteboard release 0.5.0). This supports dynamic Supervisor ingress paths and the original direct HTTP fallback.
- Installed HA addon panel slug: 29b31cdc_ziko_whiteboard_gateway, supports native ingress view and the already installed addon-iframe-card custom Lovelace card.
- Admin-only panel. No public domain, router change, WAN exposure or new users.

IMPORTANT: CT107 direct LAN address http://192.168.10.18/ is still unauthenticated. This addon secures ONLY the HA access route. Do not put confidential work on Whiteboard before the backend itself is protected. The CT107 IP may change (DHCP). A real browser with authenticated HA HTTPS session must verify pen, WebSocket drawing, ingress session and iOS/Android behavior.

Rollback: revert HA Whiteboard dashboard config via validated API patch, stop/uninstall this addon if necessary; no drawing data changes. Never delete or reset original CT107 drawings. WBO upstream carries AGPL license.
