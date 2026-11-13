# HÁZIKÓ GUARD 4.0 / ZIKO VISION — NYILVÁNOS FEJLESZTŐI ÁTADÓ

**Dátum:** 2026-11-13  
**Projekt:** Házikó / ZIKO — Home Assistant Guard 4.0 és Ziko Vision  
**Típus:** szűrt, nyilvános fejlesztői dokumentáció; nem telepíthető konfiguráció

> **Adatvédelmi megjegyzés:** A habuiot/ziko-ai GitHub-repository NYILVÁNOS. Ezért a teljes, belső 2026-11-13-i átadó konkrét otthoni kamera- és beléptetési részleteit, entitáslistáit, belső infrastruktúráját, élő állapotait és visszaállítási állományait itt nem közöljük. A részletes eredeti dokumentum külön, hozzáférésvédett mellékletként marad meg: HAZIKO_GUARD_4_ZIKO_VISION_ATADO_2026-11-13.md.

## 1. Projektcél

A Guard 4.0 a Házikó egységes, neonos biztonsági és kameraközpontja. A meglévő, élesben működő Home Assistant modulokat kell továbbfejleszteni, nem nulláról újrakezdeni. Egységes, telefonon és érintőképernyőn jól használható sötétkék–cián–lila arculat kell, párhuzamos frontend shell-ek és duplikált streamkezelés nélkül.

**Védett határ:** a korábban kivont régi Zikó Guard riasztómotort, PIN-es élesítést és szirénafunkciókat semmilyen átszervezés nem kapcsolhatja vissza. A független kamera-, zár- és érzékelőfunkciók maradnak.

## 2. Átadandó fő funkciócsoportok

1. **Egységes kép** — hat kameraképből álló közös nézet; ez többkamerás mozaik, nem mesterséges panoráma. A Frigate- és kiegészítő képforrásokat a szerver terhelésének figyelembevételével kell megjeleníteni.
2. **Maps** — a már elkészült közös 2D alaprajz és a kamerák, érzékelők, észlelési területek, zónák vizualizációja.
3. **Személyek** — tényleges Frigate-darabszámok, occupancy-állapotok, idővonal, elérhető észlelési képek. A személydetektálás nem személyazonosítás.
4. **Felvételek** — meglévő Frigate/NVR-videótár és tárhelyfelügyelet.
5. **Vision-beállítások** — kamerakalibráció, zónák, kép- és hangforrások, diagnosztika.
6. **Telefon és hangkeverés** — meglévő többkamerás böngészős WebRTC/Web Audio hallgatás, mikrofon és kibeszélés.
7. **Észlelés / radar** — események és jelenlét valós forrásokon alapuló összefogása.
8. **Belépés / érzékelők** — független hozzáférés- és szenzorállapotok, riasztóélesítés nélkül.
9. **Napló / diagnosztika** — az érintett modulok hibái és működésük hiteles állapotjelzése.

## 3. Korábban megépített komponensek

- haziko-unified-vision-center — eredeti Vision-navigáció: Személyek, Térkép, Kamerák, Felvételek, Beállítások. **A teljes örökölt nézetet ne állítsd vissza vakon**, mert kivont biztonsági kezelőket is tartalmazhat.
- ziko-vision-floor-map-v5 — Maps, vizuális kamerák és észlelések, meglévő alaprajz.
- haziko-vision-camera-hub-v6 — többkamerás böngészős hangkeverő és kibeszélés.
- haziko-nvr-center — Frigate-videótár.
- haziko-vision-diagnostics és haziko-security-log — diagnosztika és napló.
- ziko-floor-calibrator-v2 és ziko-vision-zones — kalibráció és zónák.
- Haziko_Guard_Neon — dedikált Guard/Vision színtéma.

A komponensek telepítési módját, verzióját és tényleges elérhetőségét **a célrendszerben külön ellenőrizni kell**. Ne cserélj meglévő konfigurációt dokumentációban talált elavult állapotra.

## 4. Készültségi és bizonyítottsági szintek

**Megvalósított frontend:** egységes Guard-navigáció, neonos megjelenés, többkamerás nézet, Maps és Személyek külön oldala, korábban meglévő hangkeverő, NVR, érzékelés, diagnosztika és vezérlőoldalak.

**További hitelesítést igényel:**
- Segédkamerák streamjeinek hosszú távú stabilitása, kameravezérlés és éjszakai világítás.
- A kamerák közötti személyátadás és mozgáslánc **nem tekinthető igazolt személy-reidentifikációnak**.
- A Maps helyiségszintű észleléseit **tilos** hitelesített kalibráció nélkül precíz emberpozícióként feltüntetni.
- A külön DSP-kiegészítő és a V6 böngészős keverő két külön rendszer; a hibáikat külön vizsgáljuk.
- Az automatizált videótörlést csak naplózottan, bizonyított működés után lehet elfogadni.
- A mobilos mikrofon- és hangfunkciók fizikai végtesztje nélkül nem tekinthetők lezártnak.

## 5. Következő fejlesztési lépések

1. **Biztonságos átvétel:** a jogosult fejlesztő a hozzáférésvédett teljes átadóval vesse össze az aktuális Home Assistant-konfigurációt; ellenőrizze az erőforrásokat, állapotokat és hozzon létre visszaállítási pontot.
2. **Egységes Guard UX:** a neonos modulok rendezése, egységes menük és állapotjelzések, redundáns kamerastream-ek és duplikált keretek megszüntetése.
3. **Maps + Személyek:** térképi kamera/észlelési kapcsolatok és idővonal fejlesztése; forrásbizonytalanság, adatfrissülés és kalibráció státuszának megjelenítése.
4. **Kamera/PTZ:** forrásstabilitás és vezérlők célzott diagnosztikája, meglévő rögzítés megszakítása nélkül.
5. **Telefon/hang:** böngészős és szerveroldali hangmodulok szétválasztása; hozzáférési engedélyek, hangutak és kikapcsolási viselkedés.
6. **Felvételek:** megőrzési és automatikus törlési szabályok biztonságos, dokumentált ellenőrzése. Ellenőrizetlen tömeges törlés tilos.
7. **Végső regresszióteszt:** a felhasználó munkarendje szerint az összes fejlesztés után kamera, PTZ, hang, privát mód, Maps, Személyek, videótár és mobil UI teszt.

## 6. Kötelező működési szabályok

- Ne indítsd újra a projektet és ne bontsd meg a stabil, működő komponenseket.
- Ne aktiváld vissza a kivont riasztómotort, PIN-élesítést vagy szirénát.
- Ne indíts feleslegesen egyszerre több élő kamera- és hangstreamet.
- Minden éles módosításhoz előzetes mentés, konfigurációellenőrzés, ellenőrző visszaolvasás és visszaállítási lehetőség tartozzon.
- Személyészlelés ≠ azonosítás ≠ kamerák közötti követés ≠ kalibrált térképi koordináta.
- A kamera- és személy-pillanatképekre a privát mód következetesen vonatkozzon.
- Nem feltételezünk ismeretlen támogatást: a PTZ, IR, rögzítés, mikrofon és automatikák valós állapotát ellenőrizni kell.
- **Az éles otthoni biztonsági rendszer részletes konfigurációja ne kerüljön nyilvános repositoryba.**

## 7. Új fejlesztőnek szóló átvételi utasítás

> Folytasd a Házikó Guard 4.0 / Ziko Vision fejlesztését a **belső, teljes** 2026-11-13-i átadó és az aktuális HA-rendszer alapján. Az Egységes kép, Maps és Személyek integrációját tedd egységes, neonos, informatív központtá. Őrizd meg a működő PTZ-t, V6 hangkeverőt és NVR-t. Ne aktiváld a kivont riasztót, ne duplikálj streameket, és a funkcionális tesztet a fejlesztési szakasz végén végezd el.

**Megjegyzés:** Ez a fájl tudatosan szűrt nyilvános átadó. A konkrét éles rendszeradatokat tartalmazó teljes változatot ne másold ide automatikusan.
