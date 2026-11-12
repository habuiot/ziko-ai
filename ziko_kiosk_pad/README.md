# ZIKO Kiosk Pad 0.1 — Legacy iPad HMI

Separate Home Assistant App for legacy iPad 2/iOS 9 Safari. No external JS packages or CDNs.

## Safety

- Controls only five preselected light entities and one media player; reports seven contact sensors and one lock state.
- **Lock/unlock, scripts and alarm controls are not available**.
- 8-digit pairing code in App log; 4 terminal labels, HttpOnly session cookie, 5 failed attempts/IP/15 min.
- Port 8096 is unencrypted HTTP. **Trusted local LAN only; never port-forward.**
- Keep boot manual during physical iPad and Home Assistant testing.

## Install

1. In Home Assistant Settings → Apps, refresh catalog for the already-configured Ziko AI repository.
2. Install and start ZIKO Kiosk Pad. Keep autostart off during testing.
3. In logs find `setup pairing code`. On legacy iPad Safari open `http://HOME_ASSISTANT_LAN_IP:8096`.
4. Pair as KIOSK-01 and test bidirectional light control. Never expose HTTP beyond trusted LAN.

HA Supervisor provides server-only token via SUPERVISOR_TOKEN. Physical iPad verification is not yet complete.
