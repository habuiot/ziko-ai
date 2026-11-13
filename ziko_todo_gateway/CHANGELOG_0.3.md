# Ziko™ ● Todo Gateway 0.3 · Saját projektek és hozzáférések

Kiadás: 2026-11-13

## Újdonságok
- A Home Assistant Ingressre épített ZIKO projektportál friss, mobilbarát grafitos/neonos arculatot kapott.
- A portál a Home Assistantból átadott stabil felhasználóazonosító alapján jeleníti meg kizárólag a saját engedélyezett projekteket.
- Három szerep: megtekintő, szerkesztő, projektkezelő. Jogosultsági szerepek szerinti vizuális címkék.
- Projekt nélküli felhasználó számára információs üres állapot; semmilyen projektjog nem jár automatikusan.
- Nincs külső CSS, JS vagy külön Vikunja-bejelentkezés.
- XSS és sablonhelyettesítési támadások elleni tesztek.
- A ZikoTodo irányítópult új `Hozzáférések` nézete elvezet a Gateway saját Ingress-oldalának megnyitásához.

## Teszt és üzembe helyezés
- GitHub Actions 38/38 automatikus Python-teszt: SSO-azonosítás, SQL/ACL, projektizoláció, szerepkörök, biztonságos HTML, útvonalak.
- Docker build, indulás, jogosultság nélküli kérés elutasítása: sikeres.
- Home Assistant kiegészítő: `29b31cdc_ziko_todo_gateway` **0.3.0**, telepítve és elindítva.
- Éles közvetlen, hamisított `X-Remote-User-Id` kérés az `/api/me` és `/api/projects` végpontokon: mindkettő HTTP 403.
- `boot: manual`, `watchdog: false`, nyitott hostport: nincs.

## Korlátok
- Az éles, belépett felhasználó böngészős Ingress-azonosítása és a tényleges projektjog kiosztása még nincs végigtesztelve.
- Az új projektportál egyelőre csak olvas, nem képes projektet vagy feladatot szerkeszteni.
- A Vikunja 2.8.0-2 továbbra is hibás állapotú; nem indítottuk újra.
- Az AI-végrehajtás, projektmegosztás, migráció, más felhasználók meghívása továbbra is fejlesztési feladat.
- Az eredeti ZikoTodo 0.5 Kanban és OldTodo változatlan.

## Megnyitás
Házikó → **Ziko™ ● Todo** → **Hozzáférések** → **Saját hozzáférések ellenőrzése** → **Open Web UI**.

A cél, hogy az Ingress-portál később belülről, zökkenőmentesen együttműködjön a ZikoTodo saját kezelőfelületével, külön felhasználói Vikunja-fiók nélkül.
