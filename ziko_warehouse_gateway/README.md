# ZIKO Warehouse — Home Assistant Ingress

This transport gateway embeds the **existing** ZIKO Warehouse (Proxmox CT103 on 192.168.10.74:8788) as an actual HA sidebar app panel instead of a dashboard button.

- No separate inventory store, user migration, privileged mount, HA API token, or externally published host port.
- Supervisor authenticates the HA Ingress session. The backend independently requires a Warehouse login; **no SSO or login bypass**.
- Only trusted Supervisor peer 172.30.32.2 with a valid user ID may use the proxy.
- Warehouse-only session cookie forwarded; new browser cookie scoped to the ingress session path; normal Warehouse CSRF protection retained.
- Browser routes, photos, exports and QR generation use the session-specific path. **Physical QR labels** remain pointed at the separately accessible Warehouse origin, never a temporary ingress token.
- The add-on-to-backend hop is HTTP over the private local network. Do not claim end-to-end private TLS until that is deployed.
- Do not hide the previous Warehouse dashboard until an authenticated browser test confirms the actual HA panel loads, signs in, shows inventory, and opens item details.
