# ZIKO Downloads — Home Assistant Ingress gateway v0.1.0

Standalone, unprivileged, HA Supervisor Ingress-only access to the original
ZIKO Downloads CT108 data and backend.

Every logged-in Home Assistant account may view, upload, schedule removal,
restore or permanently delete a file with the existing per-file long-press
confirmation. There is NO second Downloads admin-key prompt.

Security:
- Supervisor verifies HA identity; gateway only accepts Supervisor private
  peer 172.30.32.2 with X-Remote-User-Id and validated X-Ingress-Path.
- Separate 256-bit SSO secret is provided in protected Supervisor options
  and in a CT108 private 0600 file. No shared admin key or PFX is used.
- Gateway signs each request with time, nonce, method, route, user HMAC.
  CT108 rejects expired, replayed, tampered, unsigned requests.
- TLS to CT108 uses the public pinned self-signed cert, without disabling
  verification. No privileged HA API, host networking, Docker privileges
  or host-port publishing.
- Prior CT108 view-only /library bearer URL remains READ ONLY and does not
  grant upload or delete. Direct old admin URL/key continues as fallback.
- Same existing 500GB quota, 2GiB max file, staged SHA and 72h restore.
- Uploads are streamed with normalized Content-Length, including chunked
  HA Ingress framing, with no full file in RAM.
- A physical Opera/Tab A9 test is still necessary after install.
