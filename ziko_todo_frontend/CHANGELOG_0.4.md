# Ziko™ ● Todo 0.4 — kompakt keresősáv

Kiadás: 2026-11-13 · Élő Házikó dashboard: `/ziko-todo/attekintes`
Forrás: `ziko_todo_frontend/zikotodo-board-v02.js` (a custom element neve kompatibilitási okból változatlan).

## Mi változott?
- 34 px magas, minimalista kereső a felső fejléc jobb oldalán; mobilon 33 px magas, a márkanév alatt.
- A korábbi, Kanban alatti duplikált kereső megszűnt.
- Élő szűrés cím, projekt, név szerinti felelős és megjegyzés alapján, egygombos ürítés.
- Külön, kompakt frissítésikon.
- A feladatfelvitel ritkább beállításai (név szerinti felelős, prioritás, határidő, megjegyzés) összecsukható részbe kerültek.
- A Kanban oszlopok, az állapotváltás, az AI / saját / csapat listák és a központi márkaváltozó megmaradtak.

## Ellenőrzés
- 10/10 automatikus felületi mock teszt sikeres (egyetlen felső kereső, keresés és törlés, mobil CSS, Kanban, brand stb.).
- Home Assistant dashboard konfiguráció és frontend resource visszaolvasva; a telepített script verziója 0.4.
- Az élő feladatok változatlanok: 8 nyitott AI, 2 saját és 0 csapat.
- OldTodo változatlan: 38 összes, 35 nyitott feladat.
- Fizikai telefonon történő vizuális teszt és böngésző gyorsítótár-frissítés még szükséges. A végponti vizuális jóváhagyás nem igazolt.

## Biztonsági és funkcionális korlátok
- A Vikunja teljes API-alapú integrációja és a személyenkénti jogosultságkezelés továbbra sem készült el.
- Az AI-feladatlista nem indít automatikus végrehajtást. A felhasználók megjelölése a natív listában nem jelent valódi feladatmegosztási jogosultságot.
