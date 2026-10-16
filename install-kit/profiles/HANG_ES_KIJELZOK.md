# Szobai hang és kijelző - kész beüzemelési lap

## Első állomás: Samsung A9

Az ellenőrzéskor elérhető Kiosk Satellite: **2026.10.26** (kiadásazonosító, nem saját hardverpróba). A dokumentáció szerint beépített natív Assist-végpontot ad. Ne indíts két ébresztőszó-motort ugyanarra a mikrofonra.

- Kiadás: https://github.com/jxlarrea/kiosk-satellite/releases/tag/2026.10.26
- Univerzális APK: https://github.com/jxlarrea/kiosk-satellite/releases/download/2026.10.26/kiosk-satellite-2026.10.26.apk
- Útmutató: https://github.com/jxlarrea/kiosk-satellite

1. APK telepítése, Android telepítési és mikrofonengedély jóváhagyása.
2. Saját helyi HA-cím és a varázsló által kért HA-hitelesítés. Titkot ne küldj chatbe. Dedikált kioszk-fiók adminjog nélkül; a tulajdonosi jóváhagyás a saját telefonodon marad.
3. A meglévő **Ziko** pipeline kiválasztása: magyar Whisper, az elfogadott Edge-hang.
4. A felfedezett állomás hozzáadása HA-ban, valódi helyiség kijelölése. Ezután engedélyezhető a közös hangmemória.
5. Kezdetben támogatott gyári ébresztőszó. A saját „Ziko” szóhoz külön modell/próba kellhet. Legyen némítás és gombos indítás is.

## Ellenőrzőlista

Újraindítás után magától indul; kijelzőalvásban az elvárt üzemmód működik; „itt kapcsold fel” helyes szobában egyszer hajtódik végre; saját válasz/zene nem ébreszti újra; némítás tényleg működik; Wi-Fi-visszatérés után helyreáll. Először a tablet saját hangszórója, utána Bluetooth.

A Foldon elsőként a meglévő Companion gombos/szöveges Assistja marad. Hordozható telefonhoz nem rendelünk állandó szobát. Az NSPanel Pro Gen2 firmware/mikrofon/Android-kompatibilitása külön igazolandó. Az ESP32-C3 szenzorhub nem kész távoli mikrofon, az Echo Dot nyers mikrofonját nem feltételezzük Assist-bemenetnek.

## Képernyős eredmények

Opcionális Voice Satellite LLM Tools: az ellenőrzéskor **v1.3.1**.

https://github.com/jxlarrea/voice-satellite-card-llm-tools/releases/tag/v1.3.1

HACS-ban telepíthető a projekt dokumentációja szerint. Először Wikipédia vagy engedélyezett household weather-entitás: állítsd be a saját LLM Tools-integrációban, majd válaszd ki a Ziko beállításainál a megfelelő API-t és töltsd újra Zikót. A központ mutatja, megtalálta-e az adapter. A natív HA-híváslánc tesztelt; a konkrét kioszk képernyős próbája helyszíni lépés.

Web-/képkeresőhöz saját szolgáltató vagy SearXNG kell, nincs automatikus fizetős fiók. A korlátlan entitáskártya-API nincs áthidalva, hogy ne bővítse csendben a háztartási adatkört.
