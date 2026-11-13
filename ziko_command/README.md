# ZIKO Command — Parancsnokság 0.1

**A ZIKO-rendszer egyetlen vezetői munkafelülete felé vezető első működő lépés.**

A három modul szerepe:

| Modul | Egységes felelősség |
| --- | --- |
| **ZIKO Command** | Egyetlen felület az embernek, parancsbeérkezés, felügyelet, engedélyek, munkafutások nyilvántartása, jelentés-előkészítés. |
| **Ziko AI** | A gondolkodó parancsnok: feladatok elemzése és priorizálása, tervezés, önálló végrehajtás *jóváhagyott képességek és keretek között*. |
| **ZikoTodo** | **Kanonikus** feladatforrás: létrehozás, státuszok, megbízott, határidő, végső elkészült állapot. |

**Egyetlen hiteles feladatállapot**: Command `jobs` csak végrehajtási *próbákat* tárol. ZikoTodo feladatot sem a Command, sem Ziko AI nem jelölhet készen bizonyított eredmény és az integrációs ellenőrzés nélkül.

## A mostani 0.1-es változat

- Home Assistant **Ingress**-csatornán megnyitható saját reszponzív, sötét ZIKO-felület.
- **Valós felhasználói üzenetbeérkezés**: minden, Házikóval hitelesített felhasználó csak a saját parancsait látja. A kérelmek helyi SQLite-adatbázisban maradnak; üzenet nem indít AI-végrehajtást.
- Idempotens kérésazonosító, korlátos szöveghossz, napi 40 beérkező üzenetes felhasználónkénti limit.
- **Folyamatos éberség**: 60 másodpercenkénti könnyű heartbeat, megszakadt futásoknak visszaállítási logika, max. 3 automatikus újrapróbálkozás.
- **Jóváhagyási politika**: alacsony kockázatú, megengedett feladattípusok végrehajthatók lesznek; a közepes/magas kockázat mindig explicit, igazolt emberi jóváhagyásra vár.
- Idempotens feladathivatkozások, prioritási sor, végrehajtási bérlet és token, lejáratkor halasztott újrapróbálás.
- **Napi rövid összegzés előkészítése** 19:00 után, Budapest idő szerint. *Az értesítésküldés még nincs bekötve.* A jelentést tárolja, nem továbbítja.
- Legfeljebb **3 önálló fejlesztési javaslat naponta**; a javaslatok nem lesznek automatikusan éles végrehajtási feladatok.
- Az AI offline állapotát **őszintén mutatja**; nem állítja, hogy egy üzenet feldolgozás vagy végrehajtás alatt áll.

## Telepítés és biztonság

GitHub add-on path: `ziko_command/`; HA slug: `29b31cdc_ziko_command`.
Python standard library; nincsenek külső Python-függőségek vagy felhős kapcsolat. A Docker az app saját `/data/command.sqlite3` könyvtárába ír, `0600` adatbázisjogosultsággal.

Ingress közvetítő: `172.30.32.2`, a belépett felhasználó stabil `X-Remote-User-Id` értéke. Hamis, közvetlen kliensek elutasítva. Nincs publikált port, nincs Home Assistant API, nincs Supervisor API, nincs hozzáférés a konfigurációs könyvtárhoz. A hozzáférések szerepkörös további finomítását a ZikoTodo Gateway végzi majd.

A Command HTTP-API-ja **csak saját üzenetet** fogad, jóváhagyást, szerverfeladatot, Home Assistant műveletet és AI-hívást **nem** hajt végre.

Az alapértelmezett friss telepítés `boot:manual`, `watchdog:false` az első tesztig. **A jelenlegi Házikón 2026-11-13-án** sikeres 37/37 egységteszt és konténer-indulási próba után a Supervisor beállítása **`boot:auto`, `watchdog:true`**, és a Command app elindult. Ez az alkalmazás szintjén biztosít újraindítási felügyeletet, de nem garantálja a teljes Házikó hardverének vagy hálózatának folyamatos működését.

## Valós kiadási állapot (2026-11-13)

- **37/37 automatikus Python-teszt és Docker konténerindítás sikeres**, kézi webes teljes körű teszt még nem történt.
- A Házikó egyetlen új appot kapott: `29b31cdc_ziko_command` 0.1.0, **started**.
- Közvetlen, Home Assistant-Ingress nélküli API-lekérdezés **HTTP 403** választ kapott. A tényleges Android böngészős, jóváhagyott HA-session teszt még hátra van.
- A ZikoTodo dashboard új **Parancsnokság** nézetében közvetlen indítógomb és a meglévő natív AI Todo-lista található, az OldTodo változatlan.
- A Ziko AI app nincs élesben futó példányként regisztrálva; az önálló LLM-feladatvégrehajtó továbbra is hiányzik. A naplózott Command üzenetek önmagukban nem indítanak végrehajtást.

## Fejlesztési sorrend

1. Command 0.1: tartós parancsbeérkezés, működési pulzus, biztonságos Ingress UI, naplózás, ütemezett jelentés-előkészítés.
2. **ZikoTodo adapter 0.2**: jogosultságkezelt, csak olvasású AI-feladatlista beolvasása; a Command ugyanarra a feladatra hivatkozik, nem készít új feladatadatbázist.
3. **Ziko AI végrehajtó 0.3**: hitelesített szolgáltatás-szolgáltatás kapcsolat, korlátos képességek, munkabérletek, eredményellenőrzés.
4. **Human-in-the-loop 0.4**: Commandban válaszolható kérdések, jóváhagyás, delegálás, központi döntéstár; alacsony kockázatú munka automatikus.
5. **Jelentések és proaktív javaslatok 0.5**: napi összefoglaló, heti tervezés, súlyos elakadáskor azonnali, korlátozott számú kérdés. A csendes időszakok 22:00–08:00 alapértéket kapnak; biztonsági kivétel csak kifejezett szabállyal.
6. **Vikunja teljes integrációja** a háttérmotor helyreállítása után, idempotens migrációval. OldTodo nem veszít adatot.

## Tesztelés

```sh
cd ziko_command
python -m unittest discover -v -p 'test_*.py'
node --check web/app.js
```

A GitHub Actions külön ellenőrzi a Docker indulását, a privát adatbázis létrehozását, az életjelet és a közvetlen, hamis hitelesítéssel küldött kérés megtagadását.

**Nem kész még**: saját magát fejlesztő, 24/7 AI-ügynök; Ziko AI a Házikó alkalmazások között jelenleg nincs működő példányként telepítve. A Command 0.1 valódi, de *nem* hajt végre AI-munkát, és nem küld értesítést. Az önműködést csak a fenti biztonsági és integrációs lépések után kapcsoljuk be.
