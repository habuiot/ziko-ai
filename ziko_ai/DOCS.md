# Ziko AI – Home Assistant

Magyar szöveges asszisztens, helyi beszélgetés és kézzel mentett memória, folyamatos Home Assistant állapotmegfigyelés. Saját ChatGPT-fiókkal kapcsolható. Eszközvezérlés és automatikus riasztás még nincs.

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
