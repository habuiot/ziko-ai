# ZIKO Kiosk Pad 0.2 — Legacy iPad HMI

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

## 0.2.0
- Unified entrance overview containing doors, windows, front-door lock state.
- Touch drag swipe bar with animated progression. Door unlocking is **not enabled**: endpoint /api/unlock replies 423 until TLS and secondary authentication are provided.
- Per-KIOSK home quick controls and last tab memory; larger touch targets; faster state refresh with foreground wake refresh.
- Includes bathroom door contact. Previous 0.1 version at archive/kiosk-pad-v0.1.0.

## 0.2.1: Non-scrolling iPad pages
- Fixed viewport for every screen; compact text, tiles and buttons.
- Both iPad landscape and portrait mode layouts, with dynamic shrink-to-fit and resize/orientation support.
- No loss of controls: door/window/lock panel, slide gesture, lights, media and system remain.
- Existing sessions and backend untouched; security gate on exterior-door unlock remains in place.
- Backup branch: archive/kiosk-pad-v0.2.0.
