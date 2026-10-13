# Ziko HA Tools – általános előzmény- és naplóolvasás

Állapot: ellenőrizhető megvalósítási terv; még nincs telepítve vagy implementálva.

## 1. Cél és elfogadási feltétel

Ziko magyarul feltett kérdésekből tudja lekérdezni a Házikó eszközeinek rögzített előzményeit, mérési statisztikáit, eseményeit, automatizálási futásnyomait és HA-hibáit. A megoldás általános: nem kell külön kód vagy segédszenzor minden radiátorhoz, lámpához vagy hőmérőhöz.

Első elfogadási teszt: „Mikor volt utoljára 27 °C felett a nagyszobai mért hőmérséklet?” A bővítés a rögzített mérési soron keresi a legutóbbi megfelelő értéket. Radiátornál a mért `current_temperature` attribútumot használja; a célérték külön adat. A választ össze kell vetni a HA saját előzményeivel.

További tesztek: utolsó lámpakapcsolás; korábbi ajtónyitás; tegnapi hőmérsékleti maximum; egy engedélyezett automatizálás utolsó megőrzött futásának lépései; egy valós HA-hiba. Hiányzó, törölt vagy hozzáférhetetlen adat esetén a bővítés ezt közli, nem állítja, hogy az esemény nem történt meg.

## 2. Illesztés a meglévő rendszerhez

Új, külön Home Assistant-integráció: `custom_components/ziko_ha_tools`. Minimum HA Core 2026.10.0, a HA tényleges futtatókörnyezete szerint Python 3.14.2 vagy újabb. A natív `llm.py` platformon ad olvasóeszközöket az `assist` API-hoz, amelyet a jelenlegi Codex Assist használ. A meglévő beszélgető ügynök, modell, instrukció, Whisper és Edge TTS megmarad.

Nem módosítjuk a Codex Assist, a Home Assistant Core vagy a meglévő automatizálások forrását. Az előzményadatok a HA saját adatbázisából származnak. Az LLM csak a kérdéshez kiválasztott, korlátozott eredményt kapja meg; nem az egész adatbázist.

Az ellenőrzött kész alternatívák korlátai: a Tools for Assist saját választható API-t regisztrál, a Codex Assist 0.4.8 azonban az `assist` API-t rögzíti. Az AI Subscription Assist előzményolvasója minimális Recorder-válaszoknál nem kezeli megbízhatóan a szótárként visszaadott állapotokat. Ezeket nem telepítjük vakon a működő rendszer helyére.

## 3. Háztartási hatókör

Az első beállításkor a felhasználó egy többválasztós mezőben kijelöli a Házikó tényleges HA-területeit. A nevek helyett a belső területazonosítókat tároljuk. A hatókör az entitás saját területéből, illetve ennek hiányában az eszköz területéből számítható. A beszélgetés szövege nem bővítheti a hatókört.

Alapértelmezésben a kijelölt területek Assist számára közzétett entitásai olvashatók. Egy külön, egyértelmű beállítás engedélyezheti a kijelölt területek további, HA-ban engedélyezett entitásainak olvasását is. Ez nem ad nekik vezérlési jogosultságot. A HA-ban letiltott entitások nem kerülnek bele.

Terület nélküli entitásokhoz egyetlen további többválasztós lista használható. Automatizálásoknál külön többválasztós lista vagy HA-címke határozza meg a Házikóhoz tartozást; a hivatkozott eszközök és az elérhető futásnyomok is ellenőrzendők. Vegyes, más ingatlanra is hivatkozó automatizálás futásnyomát nem adjuk ki.

Üres hatókör nem jelent teljes hozzáférést. A jogosultságot minden eszközhíváskor újra ellenőrizzük, beleértve a lapozást és a korábbi találatok ismételt lekérését is.

## 4. Eszközkészlet

1. `ziko_ha_tools__list_sources`: a hatókörön belüli entitások és olvasható adatforrások felderítése; név, helyiség, entitásazonosító, adattípus, támogatott mérési attribútum. Nem ad vissza más ingatlan leltárát.
2. `ziko_ha_tools__query_history`: állapotelőzmények vagy megadott attribútum változásai. Opcionális numerikus vagy állapotfeltétel és legutóbbi találat keresése. A keresési eredményt a háttérkód számítja, nem egy ritkított mintából találja ki az LLM.
3. `ziko_ha_tools__query_statistics`: megőrzött statisztikák átlaga, minimuma, maximuma, összege vagy fogyasztásváltozása, megfelelő egységgel és időszakkal. Csak támogatott statisztikával rendelkező entitásoknál.
4. `ziko_ha_tools__query_logbook`: célzott eseménynapló, kizárólag a jóváhagyott entitásokról. Az entitásszűrés nélküli globális naplólekérés nem megengedett.
5. `ziko_ha_tools__list_traces` és `ziko_ha_tools__read_trace`: jóváhagyott automatizálások megőrzött futásainak listája és lépései. A kiváltó okot és a hibát a tényleges futásnyomból közli. Törölt futást nem rekonstruál kitalálással.
6. `ziko_ha_tools__query_errors`: strukturált HA-hibák és elérhető HA Core naplósorok, csak olvasásra.

A rendszer-, Supervisor-, operációsrendszer- és alkalmazásnaplók elérhetősége külön képesség. Az első csomag csak a HA Core felől ténylegesen elérhető forrásokat támogatja. A többi forrást egyértelműen nem támogatottként jelzi; nem állít korlátlan „minden napló” hozzáférést. A Supervisorhoz nem hozunk létre széles jogosultságú tokent pusztán ezért.

## 5. Időpontok, teljesség és mérési bizonyosság

Időzónás ISO-időpontok használata; belül UTC, felhasználói válasz a HA beállított időzónájában, jelenleg Europe/Budapest. Kétértelmű, időzóna nélküli időpontot nem találgatunk. A kért időablak, ténylegesen lekérdezett időablak, forrás, mintaszám és esetleges csonkolás az eredmény része.

A legutóbbi küszöbfeltételes találat a legutolsó megfelelő rögzített értéket jelenti. Ez nem feltétlenül a küszöb átlépésének vagy a megfelelő időszak végének pillanata. Folytonosság csak a Recorder által igazolható állapotszakasz alapján állítható. Hiányzó és elérhetetlen adat megszakítja a bizonyosságot.

Az órás statisztika időszakot igazol, nem pontos percet. Egy korábbi maximum azt bizonyítja, hogy az adott időszakban volt ilyen mérés; nem helyettesíti a részletes előzményt. A célhőmérséklet, mért radiátorhőmérséklet és külön szobahőmérő nem keverhető.

## 6. Terhelési és válaszkorlátok

Egy előzményhívás legfeljebb 5 entitásról és 14 napra dolgozik; a Recorder lekérdezése legfeljebb egynapos darabokban történik. A legutóbbi találat keresése visszafelé halad, és az első bizonyított találat után megáll. Legfeljebb 50 000 rögzített sor feldolgozható egy hívásban; a korlát elérésekor az eredmény csonkoltnak és nem teljes körűnek jelölt.

A beszélgetésbe legfeljebb 200 kiválasztott részletes sor kerül, összesítéssel és a kiszámított legutóbbi találattal. A részletes sorlimit nem változtatja meg a küszöbkeresés bemeneti adatait. Az eseménynapló és naplófájl eredménye legfeljebb 200 esemény vagy sor. A futásnyomok a szükséges lépésekre és jóváhagyott entitásokra szűrtek.

Adatbázis- és fájlművelet nem blokkolja a HA fő eseményciklusát. Túl hosszú kérés, hiányzó forrás, API-hiba és időtúllépés olvasható, strukturált hibát eredményez. A törlés, naplóürítés és Recorder-konfiguráció módosítása nem része ennek a bővítésnek.

## 7. Érzékeny diagnosztika

A rendszernapló a teljes HA-telepítésről tartalmazhat információt, ezért nem ugyanaz a jogosultsági kör, mint a helyiségek eszközelőzményei. Az érzékeny diagnosztika alapból kikapcsolt. Bekapcsoláskor egy meglévő tulajdonosi HA-felhasználóhoz kötjük.

Rendszernapló és részletes futásnyom csak valódi HA-kéréskontextusból igazolható, engedélyezett adminisztrátornak adható ki. A „Mesterem vagyok” bemondása nem hitelesítés. Névtelen vagy felhasználó nélküli voice satellite kérés ezekhez nem kap hozzáférést.

Jelszó-, token-, Authorization-, cookie- és egyéb ismert titokminták kiszűrése a naplóeredményből. Szabad szövegből nem ígérünk tökéletes automatikus anonimizálást. A forrás kiválasztása előre rögzített; az LLM nem adhat meg tetszőleges fájlútvonalat, SQL-t, URL-t vagy futtatandó kódot.

## 8. Tesztelés

Valódi HA 2026.10-hez illeszkedő komponens- és adaptertesztek szükségesek. Tesztesetek: mérés attribútumban; szótárként és State-ként kapott Recorder-válasz; utolsó küszöbtalálat, amely kimaradna ritkított mintából; ismeretlen értékek és adathiány; UTC/Budapest dátumváltás és óraátállítás; más ingatlan, üres hatókör, megváltozott jogosultság; entitásszűrés nélküli naplótiltás; admin és névtelen diagnosztikai kérés; titokszűrés; elérhetetlen és törölt futásnyom; sorlimitek és csonkolás.

A helyi automatizált teszt nem bizonyítja a felhasználó élő HA-jának működését. Telepítés után a konkrét radiátor, egy lámpa és egy automatizálás HA-előzményeivel közös elfogadási ellenőrzést végzünk. A bővítés letiltása vagy eltávolítása visszavonja az extra olvasóeszközöket.

## 9. Csomagolás és kiadás

HACS-szal frissíthető integráció és telepítési útmutató. A forrás a felhasználó meglévő GitHub-projektjéhez kapcsolódik; a HACS tárolószerkezetét a csomagolás előtt ellenőrizzük. A közzététel és telepítés előtt teszteredményt és konkrét változáslistát adunk.

A nyilvános csomag nem tartalmaz háztartási UUID-listát, entitásleltárt, jelszót, kapcsolati fájlt, valódi naplót vagy képernyőképet. A hatókört a felhasználó HA-ja helyben tárolja.

## 10. Jelenlegi állapot és következő lépés

A funkciók körét a felhasználó jóváhagyta. Ez a dokumentum rögzíti a megvalósítás határait és ellenőrizhető elvárásait. A kód még nem készült el. A dokumentum ellenőrzése után külön megvalósítási terv, majd kód, automatizált ellenőrzés és telepíthető csomag következik.
