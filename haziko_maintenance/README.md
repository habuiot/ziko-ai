# Házikó – karbantartási ellenőrzés 0.1.0

Kis Home Assistant-alkalmazás a **régi helyi Ziko forrásának felméréséhez**.

## Biztonsági határok

- **Csak olvasás:** a `local_apps` és a `share` könyvtár read-only kötet, más könyvtár nincs becsatolva.
- **Nincs terminál vagy általános parancsfuttatás**, fájl-feltöltés, törlés, szabad elérési út, shell, tetszőleges URL vagy hitelesítőadat-kezelés.
- **Nincs publikált port**: a web API csak a Home Assistant Supervisor Ingress proxyját fogadja (`172.30.32.2`).
- `boot: manual`, védett alkalmazás, az Ingress kezelőpanelje adminisztrátori.
- Nem olvas Ziko memóriát, SQLite-tartalmat, HA titkokat vagy biztonsági mentések tartalmát.

## Végpontok

- `GET /api/v1/health`: élő állapot.
- `GET /api/v1/inventory`: a `local_ziko_ai` forrás verziója és a megosztott könyvtárban található név szerinti régi elemek száma.
- Minden POST/PUT/PATCH/DELETE: 405; nincs módosító API.

## Telepítés

A fejlesztési ág nem kerül automatikusan a Home Assistant alkalmazásboltjába. Felülvizsgálat után, külön jóváhagyással egyesíthető a főággal. Ezután az alkalmazásboltot frissíteni kell, és telepíthető az új, különálló **Házikó – karbantartási ellenőrzés** alkalmazás. A meglévő Ziko AI-t és Codex Assistot nem módosítja.

A 0.1.0 kizárólag diagnosztika. A régi fájlok archiválására később külön, ellenőrzött és jóváhagyott funkció készülhet, más jogosultsági profillal.
