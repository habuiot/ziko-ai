# 0.4.0

- Tartós, helyi eseménynapló: 14 nap, legfeljebb 10 000 bejegyzés; 10 másodpercenkénti mentés.
- Közös jelzések: akkumulátor 20% alatt (25%-nál megszűnik), nyitásérzékelő 10 perce nyitva, minden figyelt állapotentitás 10 perce unavailable.
- A „Láttam” jelölés megmarad, de nem szünteti meg a hibát. Ismeretlen vagy elavult állapot nem igazol hibát vagy helyreállást.
- A napló és jelzések költöztetéskor megmaradnak. A chat megkapja az aktuális jelzéseket.
- Nincs telefonos push, eszközvezérlés vagy automatikus AI-hívás.

# Változások

## 0.3.1

- A HA által felsorolt select és enum szenzorállapotok láthatók a felületen és a chat állapotképében.
- A felsorolt üzemmódok és eseménytípusok, valamint az aktuális választásuk megmaradnak.
- URL-ek, jelszójellegű értékek és nem deklarált szabad szöveg továbbra sem kerülnek az AI állapotképébe.

## 0.3.0

- Tárolóból telepíthető alkalmazás.
- Személyes eszközlista kizárólag helyi konfigurációban.
- Jelszóval titkosított költöztetés: kapcsolat, hostazonosító, memória, beszélgetések, eszközlista.
- Tartós szüneteltetés a régi alkalmazásban mentés után.
- Minden jóváhagyott eszköz minden engedélyezett entitásának megfigyelése.
- Helyiség-API area_id kompatibilitás és titkokat nem tartalmazó hibadiagnosztika.
