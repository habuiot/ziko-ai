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

## 0.2.2: Bejárat page simplified
- KIOSK-01 Bejárat only: remove/hide the second "KIOSK-01 · BEJÁRAT" quick-control container; the doors/windows/front-lock/swipe overview now fills the available width.
- Other pads retain their own quick-control panels; lights and media tabs are unchanged.
- Lock opening remains disabled on HTTP while an authenticated HTTPS path is prepared.
- Rollback branch: archive/kiosk-pad-v0.2.1.

## 0.3.0 - HTTPS-only physical lock release

Legacy HTTP :8096 remains for light and media, but cannot open locks. HTTPS :8097 has separate Secure HttpOnly sessions; HTTP :8098 serves only a local CA installation profile (public certificate, no secret key).

1. Verify the `ZIKO Kiosk CA SHA256 fingerprint` from the App logs before trusting the CA downloaded over plain HTTP.
2. On the iPad: `http://homeassistant.local:8098/ca.mobileconfig`; install the ZIKO CA after independently checking its fingerprint. Enable full trust if your iOS offers that option.
3. Open `https://homeassistant.local:8097`; pair KIOSK-01 again with the pairing code from the App logs. Save the new HTTPS site to the home screen.
4. Configure an 8-12 digit `unlock_pin` in Home Assistant > Apps > ZIKO Kiosk Pad > Configuration. Never commit this value or share it in chat. The setting is read per unlock.
5. Swipe fully left-to-right and enter PIN. Only this combination requests `lock.unlock` on `lock.eloszoba_bejarati_ajto_also_zar` and checks feedback from HA.

Never expose ports 8096/8097/8098 to the internet; keep on trusted LAN. Physical iOS 9 certificate compatibility remains to be tested. Private TLS keys persist only inside the HA App data. Rollback branch: `archive/kiosk-pad-v0.2.2`.
