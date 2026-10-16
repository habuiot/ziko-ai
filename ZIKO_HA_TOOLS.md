# Ziko HA Tools 0.2.0

Natív Assist-bővítés Codex Assist mellé: előzmény, statisztika, napló, tulajdonosi diagnosztika, pontos élő állapotok, közös tartós memória, lámpapresetek és ellenőrzött automatizálási tervek. A működő bejelentkezést és hangot megőrzi. A régi Ziko AI 0.4.0 alkalmazás külön komponens.

**Tesztalap:** valódi HA Core 2026.10.0, Python 3.14.8. A ZIP-telepítő alapértelmezésben a 2026.10-es Core-családot fogadja el; későbbi HA-hoz új kompatibilitási ellenőrzés szükséges.

## Telepítés

A ZIP `KEZDD_ITT.md` fájlja tartalmazza az egyparancsos indítást és az átvételi próbákat. Teljes HA-mentés után egy feltöltés és egy helyi parancs telepíti a kódot, kódmentéssel és újraindítással. Nem szerkeszt configuration.yaml-t vagy hitelesítőket, nem aktivál letiltott entitást és nem nyit új portot.

HACS: `https://github.com/habuiot/ziko-ai`, egyéni Integration-tároló. A főágban megjelent változat letölthető; ZIP-készítés és közzététel külön állapot. Régi 0.1.0 bejegyzésnél az új memória/írás/automatizálási jogokat egyszer, kifejezetten engedélyezni kell.

## Jogosultságok

A meglévő olvasási scope helyiségeket és egyedi entitásokat kezel. A HA-ban letiltott entitás kimarad. Közzé nem tett, engedélyezett entitás olvasásához külön opció van. A vezérlési jog ettől külön marad.

Új memóriaeszközök: a konfigurált aktív tulajdonos, illetve külön engedélyezett, a Házikó helyiségéhez tartozó hangszatellit. A memória közös háztartási tudás, nem személyes napló. A prompt és a kimondott név nem jogosultság. A pipeline „acts as user” beállítása nem bizonyítja a beszélő személyazonosságát.

Eszközírás: külön engedély + aktuális scope + Assist-közzététel + stabil regiszterazonosság. Alapként a háztartási lámpák; kapcsoló/termosztát/médialejátszó csak külön írási listából. A natív Assist saját eszközeit a bővítés nem fogja el, ezért érzékeny zár/riasztó/egyéb eszköz ne legyen korlátlanul közzétéve.

## Új eszközök és kezelőpanel

`get_state`, `remember`, `recall`, `forget`, `save_light_preset`, `restore_light_preset`, `propose_automation`, `list_automations`, mind `ziko_ha_tools__` előtaggal. A korábbi olvasóeszközök és tulajdonosi diagnosztika megmaradnak. Minden a natív Assist API-hoz csatlakozik.

A pontos állapot csak engedélyezett attribútumokat ad ki, nem teljes nyers dumpot. A lámpapreset a tényleges színmódot és fényerőt rögzíti bekapcsolt lámpán. A visszaállítás ismétlésvédett; `verified` csak visszaolvasott egyezést jelent, a többi státusz nem fizikai siker.

Oldalsáv → **Ziko központ** (`/ziko-tools`): állapot, memória/preset, export/törlés, függő tervek, jóváhagyás, engedélyezés és revízió-visszaállítás. A meglévő HA websocket-hitelesítést használja, további tulajdonos-ellenőrzéssel. Nincs modellből elérhető jóváhagyó eszköz és nincs böngészőben tárolt új token.

## Automatizálási szerződés

Kötött specifikáció: állapot/numerikus/idő/nap trigger; állapot/numerikus/nap feltétel; lámpa be/ki/fényerő/CCT, engedélyezett kapcsoló, 16-26 °C közötti termosztátcél készülékhatárral, legfeljebb 70%-os médiahangerő, legfeljebb 300 s késleltetés. Nincs tetszőleges YAML, template, szolgáltatás, shell, URL vagy kód.

Elsőként saját új Ziko-szabályok szerkeszthetők; meglévő tetszőleges szabály nem kerül automatikusan átalakításra. A tulajdonos a konkrét tervet jóváhagyja; új/módosított szabály kikapcsolva mentődik. Engedélyezés külön lépés. A HA helyben futtatja a logikát, AI-hívás nélkül.

A tényleges HA konfigurációs nézet közös írási zárát, validátorát és atomikus íróját használja. Szükséges az egyetlen szokásos `automation: !include automations.yaml` a configuration.yaml-ban. Eltérő szerkezetnél vagy hiányzó natív szerződésnél megáll; nincs másik nyers fájlátírási út. Más szabályok megmaradnak; a cél közben kézzel végzett módosítását lenyomat-ütközés védi.

A létrehozott műveletek helyi `ziko_ha_tools.guarded_action` kapun futnak. Minden alkalommal ellenőrzi az aktuális engedélyeket és a jóváhagyott akcióverziót. Scope-visszavonás, írásszünet vagy integrációleállás esetén nem hajtja végre az eszközműveletet. Ziko működése helyben szükséges hozzá, felhős modell nem.

A reloadhiba, megkezdett és bizonytalan írás külön státusz. Nincs vak ismétlés. A mentett előző konfiguráció visszaállítható, ha a szabályt közben nem módosították máshol. A Ziko írásszünet nem állít le minden korábbi HA-automatizálást vagy natív Assist-eszközt.

## Vizuális adapter és hang

Opcionálisan csak a név szerint támogatott Voice Satellite LLM Tools időjárás/Wikipédia/web/kép API kapcsolható be. Nincs tetszőleges API vagy Assist-visszacsatolás. A szolgáltató saját konfigurációja és az élő kioszk megjelenítési próbája szükséges. Entitáskártya és videó nincs csendben áthidalva. A `profiles/` lapjai az A9/Kiosk, további végpontok és Music Assistant/KALLSUP ellenőrzött bevezetési sorrendjét adják.

## Adatvédelem és korlátok

Helyi, privát és atomikus HA Store, korlátos mérettel, kulcsonként legfeljebb öt korábbi értékkel; nem titokkezelő. Az explicit emlék, a kérdés és az eszközeredmény beszélgetéskor AI-szolgáltatóhoz kerülhet. Edge TTS a válaszszöveget külső szolgáltatáshoz küldi. Nem folyamatos teljes adatbázis-stream és nem automatikus nyilvános publikálás, de nem is teljesen offline rendszer.

A korábbi Recorder-korlátok megmaradnak: 5 entitás/14 nap/50 000 feldolgozott sor/200 kimeneti sor; statisztika 366 nap, ötpercesnél 14 nap. A 30 s kéréskorlát nem állít le már futó adatbázisszálat. Mesterséges kezdőállapot nem új mérés, aggregátum nem pontos küszöbátlépés, törölt adat nem rekonstruálható.

Supervisor/OS/app napló nincs; Core-napló az egész HA-ról szólhat. A titokmaszkolás nem tökéletes garancia. Nyers trace-konfiguráció/változó és nem ellenőrizhető vegyes/dinamikus cél kimaradhat. Korábbi appmemória nincs automatikusan importálva.

## Fejlesztői ellenőrzés

```sh
python -m pip install 'homeassistant==2026.10.0' 'pytest==9.1.1' 'pytest-asyncio==1.4.0'
python -m pytest -c tools_tests/pytest.ini tools_tests -q
node --check custom_components/ziko_ha_tools/frontend/ziko-panel.js
python tools/pack_ha_tools.py --output-dir dist
```

Valódi HA Store, szolgáltatás, Recorder SQLite, konfigurációs zár/validátor/író és natív eszköz/websocket-szerződés tesztelve. Ez nem helyettesíti az élő Házikó, mikrofon és Bluetooth átvételét.

### Megőrzés és ismétlésvédelem (0.2.0)

A tények és fénybeállítások külön-külön legfeljebb 100 aktív bejegyzést tartanak, törlésük felszabadítja a helyet. A verziógeneráció megakadályozza a törlés előtti verzióval való felülírást. A tervek legfeljebb 100, a revíziók 200 bejegyzést őriznek: a régi tervek és lezárt, nem aktuális revíziók automatikusan kikerülhetnek; a bizonytalan/előkészített módosításokat a rendszer nem dobja el. Az exportot fontos változtatás előtt érdemes letölteni. A beállításoknak és az írások szüneteltetésének elkülönített keretük van.

A preset-visszaállításhoz az AI előbb a `prepare_light_restore` eszközzel öt percig érvényes kérést kér, majd ugyanazt az azonosítót használja az ismétléshez. A műveleti napló tíz perc után a következő íráskor takarítható; a lejárt azonosító ezután sem hajt végre újabb parancsot. Legfeljebb 256 aktuális művelet fér el; gyors ismétlés esetén a rendszer várakozást kér. Lejárat után új kérést csak élő állapotellenőrzés és továbbra is fennálló felhasználói kérés alapján szabad indítani.
