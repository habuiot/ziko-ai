# ZIKO Command 0.1 – Első valódi parancsnokság

Kiadás: 2026-11-13 · Komponens: `ziko_command/`

## Cél

A Ziko Command lesz a felhasználó **egyetlen munkahelye**. Ziko AI lesz a koordináló, tervező és (korlátok között) végrehajtó parancsnok. ZikoTodo tárolja az egyetlen hiteles feladatállapotot. A rendszer célja a folyamatos szolgálat, rendszeres egyeztetés és korlátos, önálló munka — ellenőrizhető jogosultságokkal és visszavonható jóváhagyásokkal.

## Működő 0.1 elemek

- Saját, sötét-neonos, mobilbarát **ZIKO Command** UI Házikó Ingress alatt; Command parancsbeérkezés és saját üzenetelőzmények.
- Házikó-stabil felhasználóazonosítóval azonosítja a saját beérkező üzeneteket; nincs második fiók.
- A beérkező parancsokat SQLite `0600` jogosultsággal tárolja; napi felhasználói limit és idempotens kérelemfeldolgozás.
- Saját 60 mp-es non-LLM ébresztő, megszakadt munka időkorlátos visszaállítása, max 3 ismétlés, atomikus munkabérlet.
- Alacsony kockázatú, allowlistás jövőbeli feladattípusok; közepes/magas műveletek jóváhagyásra várnak.
- Legfeljebb 3 önálló új feladatjavaslat/nap, automatikus éles végrehajtás nélkül.
- Naponta 19:00 Budapest idő szerinti **helyi jelentés-előkészítés** (még nincs push értesítés).
- Futtatási állapotok és napló elkülönítve a ZikoTodo hiteles feladatállapotaitól.
- No public host port, no HA API, no Supervisor API, no LLM token, no direct shell execution.

## Éles állapot

- Házikó app: `29b31cdc_ziko_command`, verzió `0.1.0`, `state: started`.
- Ingress: bekapcsolva; működő Házikó-oldalról a Command megnyitható.
- Supervisor: **`boot: auto`, `watchdog: true`** (konfigurálva tesztek után). A teljes Házikó hardveres leállását ezek nem tudják megelőzni.
- ZikoTodo oldal: **Parancsnokság** nézet `/ziko-todo/parancsnoksag`, közvetlen Command-indító és a natív AI-feladatlista.
- A Ziko AI beszélgető/végrehajtó alkalmazás jelenleg **nincs összekötve**. A parancsok "awaiting_ai" státuszban kerülnek megőrzésre; AI végrehajtás nincs. A felhasználói Ingress-böngészős próbát még végig kell járni.
- Az OldTodo és a Vikunja hibás állapotú háttérmotorja változatlanul maradt.

## Ellenőrzés

- GitHub Actions **37/37 automatikus teszt sikeres**.
- JS szintaxis ellenőrzés és Docker-konténer build sikeres.
- Docker indulási próba: adatbázis `0600`, heartbeat rögzítés, hamisított Ingress-fejléces közvetlen kérés **HTTP 403**.
- Éles HA addon `started`, közvetlen hitelesítetlen API teszt **HTTP 403**.
- Az AI, saját, csapat és OldTodo feladatok nem törlődtek.
- Fennmaradó tesztek: valódi Házikó böngészős Ingress-session, éles parancsbeküldés és újraindítás utáni helyreállítás (HA teljes újraindítása nélkül a kiegészítő célszerűen tesztelhető).

## Legfontosabb hiányzó összekötések

1. ZikoTodo → Command: hitelesített, jogosultságkezelt, csak olvasású AI-feladatok, prioritások és állapotok.
2. Command → Ziko AI: külön authentikált végrehajtó, munkajogosultság-kapuk, idő- és költségkeret.
3. AI eredmény → Command → ZikoTodo: ellenőrzött státuszfrissítés és bizonyíték.
4. Kérdések és döntések: ritka, de azonnali, valóban szükséges kérdések; napi összefoglaló, heti közös tervezés, quiet hours.
5. Vikunja helyreállítása és az összes komponens egy közös, stabil kezelőfelületbe rendezése.

A Command és a Ziko AI nem két külön feladattár: a parancsbeérkezés és a munkakísérlet naplója megmarad Commandban, a feladat teljes életciklusa pedig ZikoTodo-ban.

További részletek: `ziko_command/README.md`, `ziko_command/CONTRACT.md`.
