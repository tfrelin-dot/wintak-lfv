# WinTAK LFV – experimentell prototyp

**Inte för flygoperativ användning.** Visar LFV R-områden och ett begränsat urval tillfälliga R-områden från NOTAM. Alla områden är **lila (status okänd)** tills en tillförlitlig DUP-/statusintegration är klar. Frånvaro från kartan innebär **inte** att luftrummet är fritt. Kontakta officiella AIS/ATS-källor.

## Kom igång

1. Lägg upp filerna i ett **publikt** GitHub-repository, med samma katalogstruktur (inklusive `.github/workflows/publish.yml`).
2. Öppna **Settings → Pages → Build and deployment → Source → GitHub Actions**.
3. Öppna **Actions → Update WinTAK KML → Run workflow**. Vänta tills körningen och Pages-publiceringen är klara.
4. Din KML finns på `https://<användarnamn>.github.io/<repo>/lfv.kml` (för detta projekt: `https://tfrelin-dot.github.io/wintak-lfv/lfv.kml`). Kontrollera att länken fungerar innan du lägger in den i WinTAK.
5. I WinTAK, använd Network Link/URL om din version stöder detta. Ange KML-URL och aktivera periodisk uppdatering där det är möjligt. Alternativt importera den publicerade KML-filen manuellt.

## Begränsningar

- Schemalagd körning var **15:e minut** (kan försenas av GitHub). Inte verifierad realtidsstatus.
- DUP ingår **inte** ännu. R-områden visas därför alltid med **okänd** aktiveringsstatus.
- `dynais:NOTAM` innehåller många NOTAM som inte avser luftrumsrestriktioner. Vi tar endast med NOTAM som uttryckligen anger `TEMPORARY RESTRICTED AREA ESR...` och har en läsbar explicit polygon i `ITEM_E` efter `AREA BOUNDED BY:`. NOTAM utan sådan geometri utelämnas hellre än att ritas som en felaktig cirkel.
- NOTAM kan innehålla komplicerade scheman i `ITEM_D`; dessa tolkas inte till aktivering i prototypen.
- D-områden och AIP SUP är ännu inte integrerade.
- Ingen datakälla här är auktoritativ för faktisk aktivering. Uppgifterna får inte användas för operativ flygplanering.
- Om datakällorna inte kan hämtas misslyckas körningen och tidigare KML kan ligga kvar på Pages. Kontrollera `status.json` för genereringstid. KML:s metadata visar också hämtningstid.

## Utveckling

Kör `python scripts/build.py` med Python 3.12 eller senare. Inga externa Pythonpaket behövs. Utdata skapas i `site/lfv.kml` och `site/status.json`.
