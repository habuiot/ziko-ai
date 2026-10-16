# Média és KALLSUP - kész beüzemelési lap

## Music Assistant

A HA médiaközpont kezelőfelület marad; a sorokat, forrásokat és zónákat Music Assistant kezeli.

- Hivatalos HA-tároló: https://github.com/music-assistant/home-assistant-addon
- Előkészített hozzáadás: https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fmusic-assistant%2Fhome-assistant-addon

A stabil alkalmazást telepítsd/indítsd. Helyi zenét vagy meglévő fiókot adhatsz hozzá; előfizetést nem hozunk létre. Először egy tabletes/Sendspin-lejátszó működjön.

## KALLSUP

Az ellenőrzéskor elérhető Sendspin Bluetooth Bridge: **v2.76.4**.

- Kiadás: https://github.com/trudenboy/sendspin-bt-bridge/releases/tag/v2.76.4
- HA-tároló: https://github.com/trudenboy/sendspin-bt-bridge
- Előkészített hozzáadás: https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Ftrudenboy%2Fsendspin-bt-bridge

A saját varázslójában csatlakozik a helyi Music Assistanthoz. Egyetlen KALLSUP kerüljön párosításba; válaszd ki a tényleges adaptert és hangszórót. Fizikai gombnyomás nélkül ez nem végezhető el. A szokásos BLE proxy nem automatikusan Bluetooth-audiohíd.

Próbasor: zeneindítás/megállítás/hangerő; 30 perc lejátszás; ki/be utáni újracsatlakozás; Ziko-bemondás alatti halkítás és folytatás; saját hangra ne ébredjen; csak ezután második hangszóró és szinkron. A projektben volt KALLSUP/BlueZ-hibajavítás, ezért a konkrét adapter próbája szükséges. Nem ígérünk tetszőleges számú hangszórót egy rádión.

A működő HA media_player kerüljön a saját helyiségébe és az Assist-közzétételbe. A Ziko kötött automatizálási hangerőműveletéhez a külön írási listába is fel kell venni. Helyi zene és szállítás maradhat LAN-on; az online forrás internetet használ. Nincs szükség nyilvános adminportra. A KALLSUP kimenet, nem mikrofon.
