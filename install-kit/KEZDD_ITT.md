# Ziko 0.2.0 - előkészített telepítőcsomag

A natív **Ziko HA Tools** integráció frissítése. A működő Codex Assist-bejelentkezés, gpt-6.1-sol modell, Whisper és Edge-hang megmarad. A régi Ziko AI 0.4.0 alkalmazást és a windowsos bejelentkező segédet nem kell újraindítani.

## A legrövidebb telepítés

**1. Készíts teljes HA-mentést.** A telepítő ezen felül csak a korábbi Ziko-kódot menti; ez nem helyettesíti a teljes HA-mentést.

**2. Töltsd fel a `Ziko_HA_Tools_0.2.0.zip` fájlt a HA `/config/` mappájába.** Studio Code Server vagy a meglévő fájlkezelőd megfelelő. Nem kell kicsomagolni vagy egyesével másolni a fájlokat.

**3. Terminal & SSH alatt ezt az egy sort futtasd:**

```sh
unzip -p /config/Ziko_HA_Tools_0.2.0.zip START.sh | sh -s -- /config/Ziko_HA_Tools_0.2.0.zip
```

A helyi ZIP-ből ellenőrzi a fájlokat és a HA-verziót, menti a korábbi integrációkódot, kicseréli kizárólag Zikót, HA-ellenőrzést kér, majd újraindítja a Core-t. Ha a terminálban nincs Python, az Alpine-alapú terminálalkalmazásba telepíti a `python3` csomagot. Egyéb környezetben világos hibával megáll. Nem szerkeszti a configuration.yaml-t, nem másol fiókhitelesítőket és nem indít új szervert.

**4. Újraindulás után egyszer nyisd meg a Ziko HA Tools beállításait:**

- A meglévő helyiséglista maradjon pontosan a Házikóé. Más Tuya-otthont ne válassz ki.
- **Közös tartós memória: BE.**
- **Eszközírás: BE**, ha a preset-visszaállítást és az automatizálásokat is kéred.
- **Automatizálási tervek: BE.**
- **Hangszatellitek közös memóriája:** az állomás helyiséghez rendelése után BE, ha használod.
- Kapcsolót, termosztátot és médialejátszót csak akkor adj a külön írási listához, ha Ziko ezeket is kezelheti. A közzétett háztartási lámpákhoz nem kell külön pluszkijelölés.
- A vizuális szolgáltatók maradjanak üresek a szükséges LLM Tools-integráció telepítéséig.

Első telepítésnél: **Beállítások → Eszközök és szolgáltatások → Integráció hozzáadása → Ziko HA Tools**. Régi 0.1.0 beállítását az új funkciók nem bővítik csendben: egyszer meg kell adnod az új engedélyeket.

**5. A Codex Assist utasításmezőjébe a `Ziko_prompt_v2.txt` tartalma kerülhet.** Saját korábbi szövegedet előtte mentsd el. A prompt személyiségi instrukció; a jogokat az integráció ellenőrzi.

**6. Oldalsáv → Ziko központ, majd új Assist-beszélgetés.** A központot a beállításokat mentő HA-adminisztrátor látogassa. Másik admin sem kap automatikusan tulajdonosi jogot.

## Három átvételi próba

1. Bekapcsolt lámpán: „Jegyezd meg a nagyszobai lámpa mostani fehérét feher néven.” Állíts másik színt, majd: „Állítsd vissza a feher beállítást.” A mentett értékek a központban láthatók.
2. „Jegyezd meg esti_feny néven, hogy este halvány meleg fényt szeretek.” Új beszélgetésben, majd HA-újraindítás után is kérdezz rá.
3. „Készíts tervet: minden este 20:00-kor legyen 20 százalékos a nagyszobai lámpa.” Nézd át a központban, mentsd kikapcsolva, majd a helyes célok ellenőrzése után engedélyezd.

A múltbeli hőmérséklet-kérdést ugyanannak a tényleges szenzornak/attribútumnak a HA-grafikonjával ellenőrizd. Törölt Recorder-adatból nincs kitalált időpont.

## HACS és visszaállítás

Ha a 0.2.0 már a tároló főágában van: HACS → Ziko HA Tools → Információk frissítése → frissítés → HA-újraindítás. Ez helyettesíti a ZIP-es kódtelepítést. Az átadási üzenet jelzi a tényleges publikációs állapotot.

A ZIP-telepítő kiírja a `backup_id` értéket. A korábbi kód ezzel állítható vissza; a helyi HA-adatok és beállítások megmaradnak:

```sh
unzip -p /config/Ziko_HA_Tools_0.2.0.zip install_ziko.py > /tmp/install_ziko.py
python3 /tmp/install_ziko.py --rollback A_KIIRT_BACKUP_ID --restart
```

Az `A_KIIRT_BACKUP_ID` helyére a tényleges azonosító kerül. Közben kézzel vagy újabb frissítéssel módosított kódot a régi visszaállítás nem ír felül. HACS-nál a teljes HA-mentés a biztos visszaállítási alap.

## Ami szükségszerűen kézi

Az új jogok egyszeri engedélyezése, Android telepítési/mikrofonengedély, saját HA-hitelesítés, Bluetooth-párosítás és a hangpróba. Ezekhez a `profiles/` lapjai adják a sorrendet. Lépéslapok, nem ismeretlen formátumú, állítólag importálható profilok.

## A csomag határai

Tartalmazza a pontos állapotokat, a tartós memóriát, lámpapreseteket, a kötött automatizálási szerkesztőt, panelt, vizuális API-adaptert, telepítőt és új promptot. Nem korlátlan HA-admin: meglévő tetszőleges sablonos/YAML-automatizálást nem alakít át automatikusan. Supervisor/OS/app napló, Echo nyers mikrofon, egyedi Ziko ébresztőszó és többmikrofonos koordináció nincs késznek állítva. A felhős modell és az Edge-hang internetet használhat; kérdés/adat/válaszszöveg juthat a szolgáltatóhoz.
