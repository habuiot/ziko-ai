# Ziko HA Tools 0.2.0 - natív Assist-bővítés

Pontos élő eszközadatok, előzmények, közös tartós memória, fénybeállítások és ellenőrzött automatizálási tervek a működő Codex Assist mellé. A meglévő fiókkapcsolat és hang megmarad.

## Telepítés és frissítés

- HACS egyéni tároló: `https://github.com/habuiot/ziko-ai`, típus **Integration**.
- Frissítés/letöltés után indítsd újra a HA-t. Első alkalommal add hozzá a **Ziko HA Tools** integrációt.
- Meglévő 0.1.0 bejegyzésnél egyszer engedélyezd a kívánt új memória/írás/automatizálás funkciókat; korábbi jog nem bővül automatikusan.
- A Házikó helyiségeit jelöld ki, más otthon eszközeit ne. Az írás az olvasási körnél szűkebb.
- Oldalsáv → **Ziko központ**: emlékek, presetek, jóváhagyandó tervek és visszaállítások.

[Teljes működés és korlátok](ZIKO_HA_TOOLS.md) · [Gyors telepítés](install-kit/KEZDD_ITT.md) · [Változások](ZIKO_CHANGELOG.md)

Ellenőrzött alap: HA Core **2026.10.0**, Python **3.14.8**. Tetszőleges YAML/kód, korlátlan HA-admin és helyszíni hang-/Bluetooth-próba nincs késznek állítva. A modellhez továbbított kérdés és eszközeredmény külső adatkezelést jelent; a helyi tárolás nem teljes offline működés.

Az alább bemutatott korábbi **Ziko AI 0.4.0 alkalmazás** külön, történeti komponens. A natív frissítés nem azt indítja újra, és nem másolja át csendben a hitelesítőit/memóriáját.

---

# Ziko AI – Home Assistant

Magyar szöveges asszisztens, helyi beszélgetés és kézzel mentett memória, folyamatos Home Assistant állapotmegfigyelés. Saját ChatGPT-fiókkal kapcsolható. Automatikus helyi jelzések és tartós eseménynapló; eszközvezérlés és telefonos értesítés még nincs.

## Telepítés

A Home Assistant Alkalmazásbolt → Tárolók menüben add hozzá:

https://github.com/habuiot/ziko-ai

Telepítsd a Ziko AI alkalmazást. Indítás után a felület megmutatja a saját HA-felhasználóazonosítódat; azt az operator_user_id beállításba másold, majd indítsd újra az alkalmazást.

## Korábbi helyi telepítés költöztetése

A helyi és a tárolós alkalmazás külön telepítés. A régit ne töröld a költöztetés ellenőrzése előtt.

1. A régi alkalmazás költöztetést támogató változatában az Alkalmazás költöztetése résznél adj meg legalább 12 karakteres jelszót, és töltsd le a titkosított .ziko fájlt. Ez tartalmazza a kapcsolatot, helyi hostazonosítót, előzményeket, memóriát és jóváhagyott eszközlistát.
2. Ellenőrizd a letöltést, majd állítsd le a régi alkalmazást. A mentés elkészítése tartósan szünetelteti a régi alkalmazás módosításait és fiókfrissítését. Importálás előtt a Költöztetés megszakítása gombbal folytatható a régi működés.
3. Az új alkalmazásban ugyanannak a HA-felhasználónak az operator_user_id értékét állítsd be.
4. Az üres új alkalmazás Alkalmazás költöztetése részén válaszd ki a fájlt, írd be ugyanazt a jelszót és importáld.
5. Ellenőrizd a fiókkapcsolatot, memóriát, beszélgetéseket és megfigyelési számokat. Csak ezután távolítsd el a régi példányt. A költöztetési fájlt ne oszd meg; sikeres import után törölhető.

A kapcsolati fájlok és költöztetési mentések nem kerülhetnek GitHubra vagy chatbe.

## Frissítés

A tárolós telepítés új verzióit a HA Alkalmazásbolt jelzi. Frissítés előtt hagyd bekapcsolva a biztonsági mentést. A frissítés megőrzi az alkalmazás /data könyvtárát. ZIP-másolás és terminálos telepítés a későbbi frissítésekhez nem szükséges.

## Házikó eszközlista

Az approved_device_ids helyi alkalmazásbeállítás az engedélyezett HA-eszközazonosítókat tartalmazza. A költöztetésből importált eszközlista helyben marad és elsőbbséget élvez. Üres lista esetén nincs megfigyelt eszköz. Egy jóváhagyott eszköz minden HA-ban engedélyezett entitása megfigyelésbe kerül; a letiltott, ismeretlen eszközű és eszköz nélküli entitások kimaradnak.

Az állapotfigyelés helyben fut. Chatkéréskor a megfigyelt entitások állapotképe és a kézzel mentett memória az OpenAI szolgáltatásához kerül. Kapcsolati titkok, kamera-URL-ek és nem engedélyezett szöveges állapotértékek nem kerülnek az állapotképbe.

## Bejelentkező segéd új kapcsolathoz

Windows Python 3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools\ziko_login.py
```

## Fejlesztés és ellenőrzés

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

amd64 Home Assistant OS, Python 3.12. A forrásból építést a HA Supervisor végzi; helyi tesztek nem helyettesítik a valódi Docker-build és HA-próba ellenőrzését.


## Helyi jelzések és tartós napló (0.4.0)

A szabályok 10 másodpercenként a friss HA-állapotképből dolgoznak, csak a jóváhagyott Házikó-eszközökön. A teljes entitáslista továbbra is megmarad; a szabályokhoz szükséges típusokat külön számoljuk a felületen.

- Akkumulátor: `sensor` + `device_class: battery` + `%`, számszerű `battery_level` attribútum, vagy `binary_sensor` + `device_class: battery`. Százaléknál 20% alatt jelez, 25%-nál helyreáll; feszültséget nem értelmez százalékként.
- Nyitottság: ajtó/ablak/nyílás/garázsajtó osztályú bináris érzékelő, 10 perces folyamatos nyitottság. A `last_changed` segít újraindítás után is megállapítani az időt.
- Elérhetetlenség: csak akkor, ha egy eszköz összes figyelt állapotentitása `unavailable` legalább 10 perce. Egyetlen élő állapot kizárja a teljes eszköz kiesését. Beállítások és műveletgombok nem döntenek erről.

A HA-kapcsolat megszakadása, hiányzó vagy ismeretlen állapot nem bizonyít eszközhibát vagy gyógyulást. A korábbi aktív jelzés ilyenkor „jelenleg nem igazolt”. A „Láttam” nyugtázás nem zárja le a problémát; a jó állapot zárja le. A jelzések csak a Ziko-felületen jelennek meg, telefonos értesítés nincs.

A szűrt állapotváltozások helyi SQLite-naplóba kerülnek 10 másodpercenként, legfeljebb 14 napig és 10 000 bejegyzésig. A memóriabeli várólista 1000 eseményes; túlterhelésnél a kimaradt események száma látható. Szabályos leállításkor mentünk; váratlan áramvesztésnél a még nem mentett események elveszhetnek. Kapcsolati rések külön bejegyzést kapnak, a közben történt változásokat nem találjuk ki. A felület a legutóbbi 100 megmaradt eseményt mutatja. A napló, jelzések, időzítők és nyugtázások titkosított költöztetéssel együtt átkerülnek.

A háttérfigyelés helyben fut, AI-hívás nélkül; beszélgetéskor az aktív jelzések is a modell állapotkontextusába kerülnek.
