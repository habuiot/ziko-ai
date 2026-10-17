# Házikó régi Ziko 0.2.4 – biztonságos archiválás

Ez **egyszer futó** Home Assistant-alkalmazás: nem nyit portot, nem futtat parancsokat kérésre, és nem indul el rendszerindításkor (`startup: once`, `boot: manual_only`). Csak a régi, **nem telepített** helyi Ziko 0.2.4 forrást kezeli a `/local_apps/ziko_ai` helyen. Nem nyúl az új GitHubos Ziko AI-hoz, Codex Assisthoz, HA-konfigurációhoz, /data adathoz, memóriához, mentésekhez.

**1. lépés – archive:** csak olvassa a régi forrásfájlokat, elkészíti a `/share/ziko_legacy_archives/ziko_024_source.tar.gz` állományt, ellenőrzi az összes tárolt fájl SHA-256 értékét, majd menti a manifestet. Nem távolít el semmit. Meglévő archívumot nem ír felül.

**2. lépés – retire:** előbb újraellenőrzi az eredeti forrás teljes fájllistáját, a manifestet, az archívum lenyomatát és a teljes tar-tartalmat. Csak egyezés esetén törli a **pontosan meghatározott régi forrásmappát**. Az archívum érintetlenül a megosztott mappában marad.

Mindkét művelet kézzel a Supervisor alkalmazás indításával aktiválódik; a konfiguráció `mode` értéke csak `archive` vagy `retire` lehet. A dolgozó feladat futása véget ér, és nem marad hátra hálózati szolgáltatás. Naplója a HA Alkalmazások / Naplók részén látható.

Ha az adatforrás nem pontosan `slug: ziko_ai`, `version: 0.2.4`, symlinket vagy módosulást talál, megtagadja a visszavonhatatlan lépést. A teljes HA biztonsági mentéseket és a korábbi Ziko memóriamentéseket külön megőrizzük.
