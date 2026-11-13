# Ziko™ ● Todo 0.5 — Kanban gyorsszűrők és mobilos oszlopváltás
Kiadás: 2026-11-13 · Házikó: `/ziko-todo/attekintes`

## Éles fejlesztés
- A meglévő v0.4 felső 34px kereső, gyors feladatfelvitel és sötét-neonos UI megmaradt.
- A Kanbanban egyetlen mozdulattal szűrhetők a munkalisták: Mind / AI / Saját / Csapat. Ez a szűrés **nem** változtat jogosultságon vagy adatforráson.
- Projektválasztó: az összes aktuális projektből szűrés, a meglévő keresővel együttműködve.
- „Fontos” kapcsoló: Magas és Sürgős prioritás; kombinálható projekt- és csoportszűrővel.
- Látható feladatok számának kijelzése, kereséskor újraszámolva.
- Mobilon egyérintéses oszlopugrás a négy aktív Kanban-fázisba.
- Projektkártyára koppintáskor a projekt saját Kanban-szűrt nézete nyílik meg.
- A nézet visszaállításakor Kanban marad az alapértelmezés.

## Műszaki adatok
- Forrás: `ziko_todo_frontend/zikotodo-board-v02.js` (az egyedi elem azonosítója kompatibilitási okból változatlan).
- Lovelace erőforrás: `eab4e93b188d4108bc668dee98c0f725`.
- Nincs új telepítés vagy HA újraindítás, a felület natív `todo` entitásokból olvas.
- Hozzáférés / AI-ügynök jogok nem változtak.

## Tesztek
- 13/13 programozott UI-próba: Kanban kezdőnézet, négy csoport, kombinált magas prioritás és projekt szűrés, projektnézetből visszalépés, mobilos oszlopnavigáció, erőforrás-regisztráció.
- A Lovelace kártya továbbra is `custom:ziko-todo-board-v2`.
- A három ZikoTodo-lista változatlan, és az OldTodo korábbi 38 bejegyzéséhez nem nyúltunk.
- Éles telefonos vizuális és érintéses ellenőrzés továbbra is szükséges.

## Következő biztonsági függőség
- A Vikunja-kiegészítő `29b31cdc_ziko_todo_vikunja` Supervisor-állapota 2026-11-13-án `error`, IP-je `0.0.0.0`, a naplók nem adnak friss konkrét hibaokot.
- Újraindítást nem kezdeményeztünk. A „ZikoTodo – Házikó SSO-alapú Vikunja API-híd” AI-feladat `Blokkolt` státuszt kapott.
- A teljes Vikunja-integráció, többfelhasználós szerveroldali jogosultság és önálló AI-futtatás **nem kész**.
