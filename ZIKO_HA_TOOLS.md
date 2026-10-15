# Ziko HA Tools 0.1.0

A Codex Assist mellett futó, csak olvasó Home Assistant integráció. Ziko az engedélyezett eszközök rögzített előzményeit, statisztikáit és eseményeit kérdezheti le. Külön engedéllyel automatizálási futásnyomokat és HA-hibákat is olvashat. Nem kell minden szenzorhoz külön automatizálás vagy új AI-fiók.

**Követelmény:** HA Core 2026.10.0 vagy újabb. A tesztek a valódi 2026.10.0 csomagon, Python 3.14-en futnak; későbbi HA-verziók kompatibilitását külön ellenőrizni kell. A jelenlegi Codex Assist, Ziko prompt, Whisper és Edge TTS maradhat.

## Telepítés ZIP-ből

1. Készíts HA-mentést. Töltsd le a `Ziko_HA_Tools_0.1.0.zip` csomagot.
2. Studio Code Server vagy Samba segítségével másold a ZIP-ből a `custom_components/ziko_ha_tools` mappát a HA `/config/custom_components/` könyvtárába. A végső útvonal: `/config/custom_components/ziko_ha_tools/manifest.json`.
3. Indítsd újra a Home Assistantot.
4. **Beállítások → Eszközök és szolgáltatások → Integráció hozzáadása → Ziko HA Tools.** HA-adminisztrátorként végezd a beállítást.
5. Jelöld ki egyszerre a Házikóhoz tartozó helyiségeket. Ha egy entitásnak és eszközének sincs helyisége, a „További egyedi entitások” mezőben adhatod hozzá.
6. Kapcsold be az **Assist számára nem közzétett entitások olvasását**, ha minden engedélyezett, kijelölt helyiségben levő entitás előzménye kell. A HA-ban letiltott entitásokat ez sem aktiválja. Más házak helyiségeit ne válaszd ki.
7. A futásnyomokhoz jelöld ki az automatizálásokat és engedélyezd a **tulajdonosi diagnosztikát**. Ez az opció a teljes HA Core hibanaplójának olvasását is lehetővé teszi. A jogosult tulajdonos a beállításokat mentő HA-adminisztrátor.
8. Mentés után indíts új Assist-beszélgetést Zikóval. Nem kell újra bejelentkezni a ChatGPT-fiókba.

Ha a ZIP-et először a `/config/` mappába töltöd fel, Terminal & SSH alatt a fájlok elhelyezése:

```sh
unzip -o /config/Ziko_HA_Tools_0.1.0.zip 'custom_components/ziko_ha_tools/*' -d /config
ha core restart
```

A parancs kizárólag ezt az integrációt helyezi el/frissíti. A ZIP az integráció forrását és ezt az útmutatót tartalmazza; nem teljes HA-mentés vagy korábbi Ziko alkalmazás-frissítés.

## HACS-frissítés

A forráskönyvtár HACS-kompatibilis. A GitHubra kerülő verziónál a `https://github.com/habuiot/ziko-ai` egyéni tárolóként, **Integration** kategóriában adható hozzá. Amíg a változtatás nincs a főágban, a ZIP-et használd. A korábbi, kizárólag Ziko alkalmazást tartalmazó `v0.4.0` kiadás nem telepíti ezt az új integrációt; az integrációt már tartalmazó ágat/verziót kell letölteni. HACS-forrás: https://www.hacs.xyz/docs/publish/integration/.

## Mit kap Ziko?

| Eszköz | Funkció |
|---|---|
| `ziko_ha_tools__list_sources` | Entitáskeresés név/helyiség szerint, mért attribútumok felderítése |
| `ziko_ha_tools__query_history` | Állapot- vagy attribútumelőzmény; utolsó rögzített küszöbtalálat |
| `ziko_ha_tools__query_statistics` | Tárolt numerikus statisztika, régebbi időszakok összesítése |
| `ziko_ha_tools__query_logbook` | Kijelölt entitások HA Activity eseményei |
| `ziko_ha_tools__list_traces` | Kijelölt automatizálás megőrzött, ellenőrizhető futásainak listája |
| `ziko_ha_tools__read_trace` | Futáslépések eredménye/hibája; nyers változók nélkül |
| `ziko_ha_tools__query_errors` | HA strukturált hibalista vagy rögzített Core naplófájl vége |

Az eszközök a HA natív Assist API-jához csatlakoznak. A vezérlés közzétételi beállításai külön maradnak: egy entitás előzményének olvasása nem ad új vezérlési jogot. A szöveges és hangos kérdések ugyanazokat az olvasóeszközöket használhatják. A diagnosztikai eszközök csak hitelesített tulajdonosi HA-kérésekben érhetők el; egy névtelen hangszatellit nem kapja meg őket attól, hogy kimondod a neved.

## Pontosság és korlátok

- A radiátor mért hőmérséklete `current_temperature`; a `temperature` a beállított célérték. Ziko külön utasítást kap erre.
- A HA grafikonkezdethez létrehozott mesterséges kezdőállapota külön, ismert kezdőértékként jelenik meg; nem számít új mérésnek és nem kap kitalált mérési időpontot.
- A küszöbkeresés a feldolgozott adatsoron történik, a válasz rövidítése előtt. Az eredmény rögzített mérés ideje, nem interpolált küszöbátlépés vagy egy időszak pontos vége.
- Egy lekérdezés legfeljebb 5 entitást, 14 napnyi részletes előzményt és 50 000 feldolgozott sort érinthet; a megjelenítés legfeljebb 200 sor. Az adatok naponként, a Recorder háttérszálában olvasódnak. Egy napi Recorder-lekérdezés több sort is betölthet, mint a feldolgozási keret; a 30 másodperces várakozási korlát nem állít le már elindult adatbázis-szálat.
- Alapértelmezés: utolsó 24 óra. Más időszakot kérj konkrét dátummal; egy kérés legfeljebb 14 nap. Statisztika: legfeljebb 366 nap, ötperces adatoknál 14 nap.
- A HA Recorder megőrzési idejét és kizárásait nem változtatjuk. Törölt, nem rögzített vagy hiányzó adatot nem lehet visszaállítani. Üres eredmény nem bizonyítja, hogy az esemény soha nem történt meg.
- Az órás/napi statisztika egy időszakot igazolhat, pontos percet nem; a climate attribútumokhoz nem feltétlenül létezik hosszú távú statisztika.
- Az eseménynapló más entitásokra utaló szülőkontextusai és egyedi szabad szöveges üzenetei kimaradnak. Ez nem teljes, korlátlan naplóexport és nem mindig mondja meg, ki okozta a változást.
- A futásnyomokból a nyers konfiguráció, változók, felhasználói kontextus és gyermek-futásnyomok kimaradnak. A címke/emelettel célzó, vegyes helyiségű, nem ellenőrizhető vagy sablont tartalmazó futásnyomok elutasításra kerülnek. Csak a HA által megőrzött futások érhetők el.
- **Supervisor-, HA OS- és alkalmazás/add-on-naplók ebben a verzióban nem támogatottak.** A Core fájlnapló is csak akkor olvasható, ha az adott telepítésen létezik `/config/home-assistant.log`.
- A jelszó/tokenmaszkolás több gyakori formátumot kezel, de nem garantálja minden szabad szöveges titok felismerését. A lekért adatok a beszélgetés során a beállított AI-szolgáltatóhoz kerülhetnek; nyers hibafájlt ne tegyél közzé.
- Ez a bővítés olvasóeszközöket ad: nem szerkeszt automatizálást vagy rendszerbeállítást és nem indít új háttérriasztásokat.

## Első ellenőrzés a Házikóban

Új Ziko-beszélgetésben:

> Keresd meg a Nagyszoba mért hőmérsékletének naplóforrását. A radiátor aktuális hőmérsékletét használd, ne a célhőmérsékletet. Mikor volt a legutóbbi rögzített mérés 27 °C felett 2026. október 10. 00:00 és október 13. 23:59 között? Mondd meg az entitást, a mért értéket és a helyi időpontot. Jelezd a hiányzó vagy csonkolt adatot. Semmit ne kapcsolj át.

Hasonlítsd össze a HA Előzmények kék „Radiátor aktuális hőmérséklet” görbéjével. A jövőbeli időhatárt a bővítés a jelen pillanatra vágja.

Második próba:

> Mikor változott legutóbb a közlekedő lámpa állapota az elmúlt 24 órában? Az előzményből válaszolj; semmit ne kapcsolj át.

Diagnosztika engedélyezése után a tulajdonos HA-böngészős beszélgetésében:

> Kérdezd le a HA legutóbbi strukturált hibáit. Ha nincs jogod vagy nincs ilyen naplóforrás, mondd meg; ne találj ki hibát.

## Visszavonás és fejlesztői ellenőrzés

A bővítés kikapcsolható/törölhető az Integrációk alatt. Az egyedi eszközök ezután nem olvasnak tovább, a Codex Assist meglévő vezérlése megmarad. A helyiségek/jogosultságok a bővítés beállításainál módosíthatók.

```sh
python -m pip install 'homeassistant==2026.10.0' 'pytest==9.1.1' 'pytest-asyncio==1.4.0'
python -m pytest -c tools_tests/pytest.ini tools_tests -q
python tools/pack_ha_tools.py
```

A tesztek között valódi SQLite Recorder-olvasás, HA-regiszterek, attribútumváltozás, natív LLM-eszközfelismerés, megőrzött HA-futásnyom és strukturált hibanapló szerepel. A helyi csomagteszt nem helyettesíti a Házikóban végzett első összehasonlítást.

## Meghozott döntések és következményeik

1. A jóváhagyott megvalósítást további általános megerősítési körök nélkül készítettem el. A beállítások módosíthatók; téves értelmezés esetén ezek korrigálhatók.
2. A tényleges HA 2026.10 követelmény alapján Python 3.14.2 vagy újabb a tesztalap. Az előzetes 3.13-as feltételezés elavult volt; téves verzióválasztás a kompatibilitási tesztet érvénytelenítené.
3. A közös eszközmodult használó fejlesztési részeket együtt rögzítettem, hogy a tesztelt futtatókörnyezet legyen egyben ellenőrizhető. Ennek ára a nagyobb közös kódellenőrzési egység.
4. A natív `ziko_ha_tools__` névelőtagot használtam, amely elkerüli a HA által jelzett 2027.3-as névkövetelmény miatti törést. Külső hívóknak az új eszközneveket kell használniuk; korábbi felhasználói beállítás nem hivatkozik rájuk.
5. A küszöbkeresés nem áll le az első találat után: a keresési keretig feldolgozza az időszakot, így az összesítések összhangban maradnak. Ennek ára több adatbázis-munka hosszú, sűrű idősoroknál.
6. A hiányzó konfigurációjú, sablonos vagy vegyes eszköztagságú futásnyomokat elutasítom, mert ezek háztartási hatóköre végrehajtás nélkül nem bizonyítható. Ez csökkenti az elemezhető automatizálások számát.
7. A diagnosztika jelenleg a HA strukturált hibáit és a rögzített Core naplót kezeli. Supervisor/OS/add-on naplókhoz további adapter kell; ez bővítés, nem az alap újraírása.
8. A Recorder megőrzését és kizárásait megtartottam. Ezért régi, törölt vagy soha nem rögzített pontos események továbbra is hiányozhatnak.
9. A valódi HA/SQLite/eszközfelismerési teszt a csomag átadását igazolja, nem az élő Házikó és a szolgáltatói kapcsolat teljes tesztjét. Telepítés után saját adatokkal összehasonlítás szükséges; telepítésfüggő eltérés javítást igényelhet.
10. A HA 2026.10.0 ellenőrzött; későbbi HA-verziók és az éles HACS-telepítés nem. Egy későbbi interfészváltozás célzott kompatibilitási frissítést tehet szükségessé.
11. A ZIP mellett külön GitHub-javaslat készül az aktuális közzétett alapra, a főág felülírása nélkül. Ennek ára, hogy a HACS főági telepítés a javaslat beolvasztásáig vár.

A független kódellenőrzés négy érdemi hibát talált: mesterséges kezdőállapot-időbélyeg, címke/emelet alapú futásnyom-célzás, korábbi pufferelt futás hatókörének visszavonása, idézőjeles JSON/Python titokmezők. Mind a négy javítást először hibát reprodukáló teszt, majd sikeres tesztfuttatás ellenőrizte. A végső készlet **56 sikeres tesztet** tartalmaz. Elhalasztott kisebb kódellenőrzési hibát nem jeleztek.

A később beküldött „jegyezd meg a lámpa jelenlegi fehér színét” példa további igény: pontos élő színadat-olvasás és tartós beállításmemória. Ez a verzió nem állítja, hogy ilyen beállítást tartósan elmentett; a teljes értékű beállításmemória külön funkció.

A tiszta GitHub-környezet további tesztjavítást tett szükségessé: a Recorder-teszt immár kifejezett tranzakciós szinkronpontra vár. A beállítófelület tényleges, hitelesített HTTP-kérése adja az adminisztrátor azonosítóját; ezt konfigurációs és beállításmódosítási próbák is ellenőrzik.
