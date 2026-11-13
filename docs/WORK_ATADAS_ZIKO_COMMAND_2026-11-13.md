# ZIKO – FEJLESZTÉSI ÁTADÓ
**ZIKO Command × Ziko AI × ZikoTodo**  
**Állapotfelmérés dátuma:** 2026. november 13., Europe/Budapest  
**Forrásrepo:** https://github.com/habuiot/ziko-ai (public, alapértelmezett ág: main)  
**Cél:** másik fejlesztő / ChatGPT Work azonnal, biztonságosan tudja folytatni.

> **Kötelező:** Az átvétel előtt olvasd el ezt a fájlt, a ziko_command/CONTRACT.md és README.md fájlokat, majd ellenőrizd újra a Házikó élő állapotát. Az alkalmazásokat és feladatadatokat NEM szabad újrakezdeni vagy visszaállítani. A befejezettnek mondott szolgáltatások és a ténylegesen működő funkciók külön vannak jelölve.

---

## 1. Felhasználói jövőkép – ELFOGADOTT
A felhasználó hosszú távon **kizárólag a ZIKO Command parancsnokságban akar dolgozni**. Ott Zikóval beszél, nem külön-külön alkalmazásokat és feladatlistákat kezel.

- **ZIKO Command:** a felhasználó egyetlen munkahelye; parancsok, kérdések, döntések, eredmények, jogosultságok, állapotjelentések, prioritások és vizuális irányítás.
- **Ziko AI:** a háttérben dolgozó „parancsnok”, a ZIKO AI komponensben lakik; feladatokat felmér, sorrendez, végrehajtást tervez, a jogosult eszközökkel dolgozik és az eredményt ellenőrzi.
- **ZikoTodo:** az egyetlen hiteles feladatnyilvántartás: feladat-ID, projekt, prioritás, felelős, határidő, státusz, mellékletek és történet. A Command nem hozhat létre második, ettől eltérő feladat-igazságot.

**Működési alapelv:** a rendszer lehetőleg folyamatosan szolgálatban legyen, önállóan keressen hasznos, biztonságos munkát, a felhasználót pedig csak döntés, tényleges elakadás vagy fontos változás esetén kérdezze. Napi tömör beszámoló, időszakos egyeztetés, folyamatosan látható státusz. A túl gyakori megszakítás kerülendő.

**Autonómia határa:** automatikus lehet az engedélyezett, alacsony kockázatú kutatás/elemzés/tervezés/dokumentáció. Éles konfiguráció módosítása, telepítés, adat- vagy fájltörlés, jogosultságadás, biztonsági rendszer, költség, külső publikálás stb. csak a megfelelően hitelesített, explicit jóváhagyással. Az AI nem minősítheti át saját maga a művelet kockázatát, és nem adhat magának jogot.

A „soha ne álljon le” cél **folyamatos felügyelet + hibatűrő munkafeldolgozás**, nem végtelen AI-kérések vagy tartalmatlan automatikus feladatgyártás. Ha nincs biztonságosan végezhető munka, a Command ezt őszintén jelezze és készítsen korlátozott számú fejlesztési javaslatot.

---

## 2. Ellenőrzött éles Házikó-állapot

| Komponens | Azonosító / verzió | Élő állapot | Fontos beállítás |
|---|---|---|---|
| ZIKO Command | 29b31cdc_ziko_command / 0.1.0 | **started** | Ingress, Supervisor boot=auto, watchdog=true, nincsen publikált hostport |
| ZikoTodo Gateway | 29b31cdc_ziko_todo_gateway / 0.3.0 | **started** | Ingress, boot=manual, watchdog=false, nincsen publikált hostport |
| ZikoTodo Vikunja | 29b31cdc_ziko_todo_vikunja / 2.8.0-2 | **error** | boot=manual, watchdog=false; jelenleg nem használható háttérmotor |
| Ziko AI alkalmazás | ziko_ai/ 0.4.0 forrás a repóban | **nem látható telepített, futó appként** | A chat és HA-megfigyelés forrása létezik; nincs Command executor |
| ZikoTodo Lovelace | /ziko-todo/attekintes | **létező, működő dashboard** | custom:ziko-todo-board-v2; v0.5 funkciócsomag |
| OldTodo | /old-todo/feladatok | **külön megőrzött régi lista** | a korábbi adatokat NE módosítsd a migráció előtt |

**Élő Todo-entitások:**
- todo.zikotodo_ai_feladatok — a legutolsó lekérdezéskor **34 összes / 33 nyitott / 1 kész**.
- todo.zikotodo_emberi_feladatok — **15 nyitott** a legutolsó lekérdezéskor.
- todo.zikotodo_csapatfeladatok — **0**.
- todo.haziko_eszkozok_felvetele — **38 összes / 35 nyitott / 3 kész** (OldTodo).

**FONTOS!** Más beszélgetésekben és automatizált munkafolyamatokban a Todo-listák egyidejűleg változnak. A feladatszámok nem rögzített specifikációk; új munkamenetben a valódi számokat frissen kell lekérni. A meglévő UUID-kat, sorrendet, állapotokat és leírásokat őrizd meg.

**Dashboard nézetek:** /ziko-todo/attekintes, /ziko-todo/ai, /ziko-todo/emberi, /ziko-todo/csapat, /ziko-todo/hozzaferesek, /ziko-todo/parancsnoksag.

**Egy fontos eltérés:** a ziko_command/config.yaml forrásfájlban boot=manual szerepel alapértékként, de a **telepített** Supervisor beállítása már boot=auto és watchdog=true; a tényleges működési állapotot mindig a Supervisorból olvasd.

---

## 3. GitHub belépési pontok / kötelező források

**Parancsnokság:**
- ziko_command/README.md – funkciók, használat, biztonság, fejlesztési roadmap.
- ziko_command/CONTRACT.md – a három rendszer egyetlen hiteles adatképét biztosító szerződés és eseményformátum.
- ziko_command/CHANGELOG_0.1.md – az eddig élesített csomag és teszteredmények.
- ziko_command/engine.py – tartós SQLite munkafutások, idempotencia, lease, hibafelépülés, prioritások, jóváhagyás-előkészítés, javaslatok, digest.
- ziko_command/server.py – Ingress-only HTTP-alkalmazás; hitelesített parancsbeérkezés, read-only státuszlekérdezés.
- ziko_command/web/index.html, style.css, app.js – sötét-neonos, érintőbarát parancsnoki UI.
- ziko_command/config.yaml, Dockerfile, start.sh – saját HA-kiegészítő.
- ziko_command/test_engine.py, test_server.py – biztonsági és működési tesztek.
- .github/workflows/ziko-command.yml – CI, Python tesztek, JS szintaxis, Docker indulás és tiltásellenőrzés.

**ZikoTodo:**
- ziko_todo_frontend/zikotodo-board-v02.js – élő egyedi HA kártya, Kanban v0.5; a „v02” fájlnév kompatibilitási okból változatlan.
- ziko_todo_frontend/CHANGELOG_0.5.md, README.md – Kanban és feladatkezelés.
- ziko_todo_vikunja/INTEGRATION_PLAN.md – Vikunja/SSO/adatmigrációs terv.
- ziko_todo_gateway/server.py, acl.py, panel.py, admin_cli.py – Házikó-Ingress identitás, explicit projekt ACL, mobil hozzáférési panel, offline adminsegéd.
- ziko_todo_gateway/README.md, CHANGELOG_0.3.md – cél, API-k, korlátok, tesztek.

**Ziko AI:**
- ziko_ai/config.yaml – 0.4.0 app leíró.
- ziko_ai/src/ziko/main.py – FastAPI, chat és HA observer szolgáltatás.
- ziko_ai/src/ziko/chat.py – ChatService, üzenetfolyam; nincs eszközvezérlés/automatikus munkavégrehajtás.
- ziko_ai/src/ziko/provider.py – szöveges modellválasz, Responses API streaming.
- ziko_ai/src/ziko/storage.py – beszélgetések, emlékek, beállítások lokális tárolása.
- ziko_ai/src/ziko/access.py – Ingress-azonosítás, operator ellenőrzés.
- ziko_ai/CHANGELOG.md – a tényleges 0.4-es tudás leírása.

**GitHub Actions ellenőrzött:** ZIKO Command 37/37 Python-teszt + JS szintaxis + Docker boot sikeres; futás: https://github.com/habuiot/ziko-ai/actions/runs/43476827745 . Gateway 0.3 korábban 38/38 tesztet teljesített. A tesztek **nem helyettesítik** a valós androidos Ingress- és többfelhasználós végigpróbálást.

---

## 4. Mi készült el ténylegesen?

### ZIKO Command 0.1 – igen
- Telepítve, elindítva, Supervisor auto boot és watchdog bekapcsolva; csak a saját izolált app, a Házikót nem kellett újraindítani.
- Saját sötét/neon Command felület. A Házikó dashboard Parancsnokság oldaláról navigálható.
- Házikó Ingress-felhasználóazonosítás (X-Remote-User-Id, védett Ingress proxy), közvetlen hamisított API-kérésre HTTP 403.
- Tartós, felhasználóhoz kötött parancsbeérkezés és visszaolvasható saját üzenetlista; új üzenet státusza: awaiting_ai.
- Saját SQLite állapot, 0600 fájljog, 2000 karakteres beérkező üzenet, idempotens klienskulcs és napi 40 üzenetes biztonsági keret.
- 60 másodperces nem-LLM életjel; időkorlátos munkabérlet (600 s), max. három próbálkozás, ütközésmentes claim, egyszerű backoff/lejárt lease helyreállítás.
- Leendő munkafajták allowlistája: research, analysis, planning, documentation, readonly_audit. Közepes/magas kockázatú job alapból waiting_approval; alacsony kockázatú job sorba tehető.
- Javaslatok max. napi 3 darab; NEM automatikusan indítanak tényleges végrehajtást.
- Budapest idő szerint 19:00 után naponta legfeljebb egy **helyi jelentés készül elő**. Nincs értesítésküldés vagy automatikus ChatGPT-válasz.
- Tartós, auditálható munkakísérlet-tábla és eseménytábla. **A Command job állapota nem ugyanaz, mint a Todo feladat státusza.**

### ZikoTodo / Gateway – igen
- A saját ZikoTodo v0.5 sötét-neon Kanban működik a natív Home Assistant todo entitásokból; élő keresés, 34 px felső kereső, AI/Saját/Csapat szűrők, projektek, prioritás, határidő, gyorsfelvitel, oszlopváltás, mobileszközön külön állapotválasztó.
- Gateway 0.3 fut, deny-by-default projektszintű SQLite ACL: viewer, editor, manager. READ-ONLY projekt API. Másik felhasználó privát projektje nem kérdezhető le jogosultság nélkül.
- OldTodo külön megőrizve.

---

## 5. MI NINCS MÉG KÉSZ – ezeket tilos késznek jelenteni

1. **Nincs csatlakoztatott Ziko AI végrehajtó.** A ziko_ai/0.4.0 forrás korábbi megfigyelő és beszélgető motor; nem egy valóban autonóm, eszközhívásokat végző Command executor. Nincs élő telepített Ziko AI példány az aktuális Házikó app-listában.
2. **A Command nem olvassa még a ZikoTodo feladatait automatikusan**; a /api/work jelenleg tilt (403), és a Todo adapter hiányzik. A Command felület navigációs hivatkozásai és a dashboard beágyazott natív Todo-kártyája NEM egyenlő a háttérrendszerek összekapcsolásával.
3. **A parancsbeérkezés nem indít AI-munkát.** Az awaiting_ai üzenetek tartósan várakoznak.
4. **Nincs aktív feladat-felvétel, kiválasztás és végrehajtás** a Ziko AI és Command közötti hitelesített, szűk hatókörű executor API-n át.
5. **Nincs tényleges, végfelhasználós projektmegosztás vagy feladatjogosultság**; Gateway projekt ACL alapja elkészült, de a valós felhasználók kiosztása, többfelhasználós tesztje és a Vikunja jogosultság-szinkron hiányzik.
6. **A Vikunja 2.8.0-2 error állapotban van.** Hibája nincs megbízhatóan diagnosztizálva. Ne indítsd újra, ne migrálj, ne írj felül adatot ellenőrzött mentés és külön műveleti jóváhagyás nélkül.
7. **Nincs távoli értesítés / ténylegesen kiküldött napi riport.** A 19:00-s összefoglaló csak a Command SQLite táblájában készül el.
8. **A végfelhasználó telefonos Ingress-megjelenítése és a valós parancsbeküldés még nincs végtesztelve.** A CI és a szerver futása önmagában nem bizonyítja ezt.
9. **A kockázati osztályozás jelenleg protokoll, nem ténylegesen ellenőrzött eszközjog.** A Command belső approve() és claim(executor_connected=True) függvényei NEM hitelesített külső szolgáltatási API-k. Ne engedd közvetlenül AI-modellnek meghívni őket. A jogosultság- és képességkiosztás szerveroldali ellenőrzése szükséges.
10. **Az önmagát bővítő, megállás nélkül fejlesztő agent nincs megvalósítva.** A jelenlegi verzió felügyeleti alap, nem dolgozó AI-munkatárs.

---

## 6. Kötelező közös adat- és eseménymodell

**Single source of truth:**
- A ZikoTodo task az igazság: task_id + project + priority + owner + deadline + status.
- A ZIKO Command csak üzenetet, approvalt, job attemptet, lease-t, eredményt, eseményt, briefinget tárol.
- A Ziko AI tervet, döntési javaslatot és végrehajtási eredményt ad vissza, de nem írhatja át önkényesen a Todo kanonikus állapotát.

**Feladatfeldolgozás célfolyam:**
1. Ember parancsot ír a Commandban → command message, queued/awaiting_ai, tartós napló.
2. Ziko AI hitelesített szolgáltatásként triage-ol: kérdés? már létező Todo feladat? új javaslat?
3. A Todo-ban hiteles task_id + feladatprioritás és jogosultság ellenőrzése; hiányzó feladat esetén előbb létrehozási-javaslat, nem szellemfutás.
4. Command munkakísérletet hoz létre idempotens kulccsal, behatárolt risk/capability kerettel.
5. A megfelelően hitelesített executor egyetlen munkabérletet vesz fel; nem futtat egyszerre duplikált műveleteket.
6. Közepes/magas kockázatnál a Command jogosult emberi jóváhagyást kér; vélemény és modellválasz nem számít jóváhagyásnak.
7. AI végrehajt, eredményt/bizonyítékot és esetleges problémát visszaküld.
8. Command review-ban tárolja; csak bizonyított, elfogadott siker után kérhető a Todo megfelelő státuszfrissítése.
9. A felhasználó csak fontos döntésnél kap kérdést; egyébként tömör státusz és összefoglaló.

**Todo leírás-formátum:** a natív listákban gyakori a ZIKO-TODO/1 fejléces, projekt/felelős/prioritás/folyamat mezőkkel rendelkező szöveg. Vannak régi „Projekt: … | …” és más migrációs leírásváltozatok is. **Ne feltételezd minden feladatról, hogy ugyanaz a parser-formátuma.** Ismeretlen metaadatot kezeld ismert/hiányzó állapotként, ne hamis becslésként.

**A jelenlegi Kanban folyamat:** Beérkezett → Folyamatban → Ellenőrzés → Kész; Blokkolt külön állapot. A Todo completed státusza és a szöveges Folyamat mező szinkronizációját ügyelni kell. A Command job states: queued, waiting_approval, running, review, done, blocked — **ezek nem Todo fázisok**.

Részletes követelmény: ziko_command/CONTRACT.md.

---

## 7. Folytatási sorrend – a következő fejlesztőnek

### P0 / AZONNAL: valós használhatóság és AI feladatok
1. Frissen ellenőrizni: HA app állapotok; Command UI belépés Androidon; tényleges Ingress-session és a POST /api/messages parancs felvétele, üzenet újraolvasása. Kérni csak a nélkülözhetetlen kliensoldali megfigyelést, ne ismételni megválaszolt kérdéseket.
2. A meglévő **Home Assistant natív Todo** entitásokat használva elkészíteni a Command → ZikoTodo **read-only AI-feladatadaptert**. A Vikunja javításától független MVP legyen. Lekérje az eredeti feladat-ID-kat, projektet, prioritást, határidőt, státuszt és leírást.
3. A Command központi képernyőjére valódi élő **AI munkasor**: mi van soron, mi fut, mi blokkolt, mi vár döntést, mi az eredmény. Az offline Ziko AI kapcsolatra ne írja, hogy „dolgozik”.
4. Kialakítani a stabil, felhasználóhoz kötött Todo jogosultságellenőrzést. A HA login nem ad korlátlan Todo admin jogot; az egyes taskok jogosultságát szerveroldalon kell ellenőrizni.

### P1 / A VALÓDI PARANCSNOK
5. Felmérni a ziko_ai/0.4.0 kódot és meglévő chat-/memória-adatokat; **ne kezdd újra és ne írj felül mentett adatot**. Telepítési tervet, forráskompatibilitást és kapcsolatpróbát készíteni.
6. Kialakítani a Command ↔ Ziko AI hitelesített M2M kapcsolatot: szűk képességek, titkos kulcsok kizárólag szerveroldalon, idő/költségkeret, biztonságos eszközhasználat, visszakövethető műveleti napló.
7. Először alacsony kockázatú **egy darab** valódi kutató/elemző Todo-feladaton végigpróbálni a teljes kört: átvétel → bizonyított kimenet → ellenőrzés → Todo visszajelzés. Minden AI-tevékenységnek látszódnia kell a Commandban.
8. Command kétirányú beszélgetés: Ziko kérdéskártya, válasz, jóváhagyás, elutasítás, változtatáskérés, összefoglaló és archívum. Az engedélyekhez külön validált szerveroldali operátorszerep.

### P2 / ÖNÁLLÓSÁG ÉS MEGBÍZHATÓSÁG
9. Legyen folyamatosan kiválasztható prioritásos munkasor, de a feladatgyártás kapjon keretet (max. napi 3 új ötlet; ne teljesítmény-látszatként hozzon létre ál-feladatokat).
10. Napi 19:00-s rövid tájékoztató **kézbesítése** az engedélyezett csatornán, heti közös tervezés, 22:00–08:00 alap csendes idő; fontos akadálynál rövid, egyetlen összevont kérdés.
11. Üzemstabilitás: csak saját add-on újraindítása tesztként, megszakadt job requeue, idempotens ismétlés, offline visszaállítás, memória/CPU/napló/SQLite növekedés. A Házikó teljes restartja kerülendő.
12. Mentés/helyreállítási terv a Command /data/command.sqlite3, Ziko AI memória és Todo-adatok számára. A Házikó korábban váratlanul többször lefagyott; ne adj terhelési garanciát valós hosszúteszt nélkül.

### P3 / VIKUNJA ÉS TELJES CSAPATMUNKA
13. Vikunja error állapot diagnózisa naplóval, erőforrás-ellenőrzéssel, mentéssel; ne találgass okot. Célzott indítás csak külön jóváhagyással.
14. Vikunja belső szolgáltatásazonosság + Házikó Ingress SSO, **külön felhasználói regisztráció nélkül**, ACL-tesztek és valódi többfelhasználós csapatjogok.
15. Natív HA Todo → Vikunja visszaellenőrzött, idempotens migráció; eredeti task és OldTodo megőrzése, amíg az adat- és funkcióegyezés igazolt.

---

## 8. Elvárt tesztek és elfogadás

- **Helyes identitás:** bejelentkezett HA-user saját parancsait látja; egy másik nem; hamisított ingress fejléc közvetlen hozzáféréssel 403.
- **Parancs nem „kész” pusztán elküldéstől:** a parancs awaiting_ai státusza a UI-n egyértelmű, amikor nincs executor.
- **Kanonikus Todo szinkron:** task ID ugyanaz marad, az AI/Command/HA Todo állapot koherens; hibás/fel nem ismert leírás nem okoz hamis befejezést.
- **Duplikációvédelem:** azonos client_id vagy idempotency_key nem indít kétszer külső műveletet.
- **Terhelés és újraindítás:** kis memória/CPU, heartbeat folyamatos; a munkák és üzenetek addon-újraindítás után megmaradnak; maximum három próbálkozás.
- **Jóváhagyás:** a veszélyes módosításokat a modell önmagában nem hagyhatja jóvá; emberi döntés felhasználóhoz, feladathoz és konkrét művelethez kötve.
- **Hibatűrés:** nincs Todo/Vikunja/Ziko AI kapcsolat → őszinte offline státusz; nincsenek eltitkolt, képzelt eredmények.
- **Egyeztetés:** azonnali kérdés csak indokolt blokkoló helyzetben; a többi a következő napi/ heti összefoglalóban; csendes időszak támogatása.
- **Valós kliens:** Samsung Fold7 mobilon valódi Ingress-útvonal, gombok, parancsbeadás, megjelenítés és frissítés tesztelve.
- **Visszaállíthatóság:** ismert rollback útvonal, adatmentés, az OldTodo és a natív HA Todo entitások megőrzése.

A működő Command 0.1 egységtesztje nem bizonyítja az összes fenti feltételt; többségük a következő fázisok átadási feltétele.

---

## 9. Üzemeltetési szabályok – SZIGORÚ

- A Házikó tényleges éles Home Assistant OS rendszer. **Nincs Windows gép;** a fejlesztést GitHub/HA eszközökkel végezd.
- A teljes Home Assistantot vagy host OS-t ne indítsd újra egy felületi, Todo- vagy Command-változás miatt. Először csak read-only vizsgálat; írás előtt célzott mentés, majd egyedi addon változás és ellenőrzés.
- A ZIKO Command és ZikoTodo **meglévő** kódját és navigációját őrizd meg; ne generálj helyettük új, párhuzamos „demo” felületet.
- A ZIKO a főmárka (ékezet nélkül): modulonként ZIKO Command, Ziko AI, ZikoTodo. A Command egyetlen főoldalra törekszik; a komponensek a háttérben önálló szolgáltatások.
- Ne tárolj HA user ID-t, jelszót, OpenAI tokeneket, Vikunja technikai kulcsot, helyi admin-titkokat a publikus GitHub repóban vagy böngészős JavaScriptben.
- A Gateway a külön felhasználói Vikunja-fiók **elhagyására** szolgál; ne kérj új, külső felhasználói regisztrációt.
- Ne tedd automatikusan elérhetővé az AI számára a teljes GitHub/HA/Vikunja-írási felületet. Előbb explicit szűk jogosultság és jóváhagyási modell kell.
- A feladatok és szerepkörök technikailag valódiak legyenek; az állapotjelzőket a tényleges backendből származtasd.
- Minden kiadásnál: GitHub commit, CI, Házikó telepítési állapot, tényleges kipróbálás, rövid changelog és visszaállítási út. 

---

## 10. Következő fejlesztőnek szánt átvevő utasítás

**Vedd át a ZIKO Command × Ziko AI × ZikoTodo projektet a habuiot/ziko-ai repo main ágáról.** Kötelezően olvasd el elsőként:  
1. docs/WORK_ATADAS_ZIKO_COMMAND_2026-11-13.md  
2. ziko_command/CONTRACT.md  
3. ziko_command/README.md  
4. ziko_todo_frontend/README.md és CHANGELOG_0.5.md  
5. ziko_ai/src/ziko/main.py, chat.py, provider.py  
6. ziko_todo_gateway/README.md és ziko_todo_vikunja/INTEGRATION_PLAN.md.

**Ne kezdj új projektet.** Ne állítsd, hogy a Ziko AI már autonóm feladatokat hajt végre; a Command 0.1 futó ütemező és parancsbeérkezés, a Ziko AI végrehajtó még nincs bekötve. Az első megvalósítandó fejlesztés a ZikoTodo éles natív HA AI-feladatainak **csak olvasási jogosultságú, felhasználóhoz kötött** betöltése a Commandba. Ezután kövesd a P1–P3 sorrendet, bizonyított teljes feladatlánccal, auditnyommal, kockázati jóváhagyással és visszaellenőrzött Todo-frissítéssel.

A felhasználó végcélja: **csak a ZIKO Commandban beszél Zikóval; Ziko a többi alkalmazást helyette, proaktívan, engedélyezett autonómiával koordinálja; kérdez, ha tényleg szükséges, egyébként dolgozik, naplóz és rendszeresen beszámol.**

**Átadás lezárása:** dokumentációk ellenőrizve, éles állapot újraolvasva, nincs ismeretlen reboot/migráció, a meglévő adatok változatlanok.
