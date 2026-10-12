# TV-bevakare: LG 65" C5 hos Elgiganten

Bevakaren kollar var 5:e minut (± 20 sek) om **LG 65" C5 4K OLED evo TV (2025)** (varukod 912307) finns i lager i någon Elgiganten-butik i Stockholms län. Du får en push-notis på mobilen via **ntfy** när:

- en bevakad butik går från 0 till i lager (med butik, antal, pris och länk)
- lagret i den butiken försvinner igen
- bevakaren har slutat fungera (3 misslyckade kontroller i rad), så att du vet att tystnaden inte betyder "inget lager"
- Elgiganten blockerar bevakaren (då stoppar den och försöker inte ta sig förbi spärren)
- bevakaren startar (testnotis) och när den stängs av automatiskt **2026-10-18 23:59**

## Komma igång på mobilen

Öppna ntfy-appen, tryck **+** och prenumerera på ditt ämne (server: ntfy.sh). Ämnesnamnet står i `config.local.yaml` på Macen.

## Molnet (GitHub Actions) – så körs den nu

Bevakaren körs i GitHubs moln, så datorn kan vara avstängd. Den ligger i repot **https://github.com/Rappew/tv-bevakare**.

- En körning kontrollerar var 5:e minut i 5,5 timmar. Varje timme ställer GitHub en ny körning i kö, och den tar vid så fort den förra är klar. Det ger kontroller dygnet runt.
- **Se att den kör:** öppna fliken **Actions** i repot (logga in). En gul snurra betyder att den kör. Klicka på körningen och sedan på steget **Bevaka lagret** för att se loggen. Körningar som står som "cancelled" är normala: de är köade dubbletter som ersatts av nyare.
- **Stoppa:** Actions → **Lagerbevakare** → knappen **···** → **Disable workflow**. Den stänger också av sig själv efter 2026-10-18 23:59. Stäng gärna av den då ändå, så att den inte startar i onödan.
- **Starta igen:** samma meny → **Enable workflow**, och sedan **Run workflow**.
- ntfy-ämnet ligger som en dold hemlighet (Settings → Secrets → `NTFY_TOPIC`) och syns inte i koden.

Kör **inte** bevakaren på Macen samtidigt, för då får du dubbla notiser.

## Köra på Macen i stället (reserv)

Öppna Terminal och gå till mappen:

```bash
cd ~/Projekt/tv-bevakare
```

| Vad | Kommando |
|---|---|
| **Starta** (i bakgrunden, Macen hålls vaken) | `./start.sh` |
| **Stoppa** | `./stop.sh` |
| **Se loggen live** (avsluta visningen med Ctrl+C) | `./logg.sh` |
| **Se lagret just nu** (en kontroll, inga notiser) | `./status.sh` |

`./status.sh` fungerar när som helst, även när molnet kör, eftersom den inte skickar några notiser. På Macen läses ntfy-ämnet från filen `config.local.yaml`, som inte laddas upp till GitHub. Om du stänger locket på en MacBook som går på batteri somnar den, även med `caffeinate`.

Ett tips: stäng av "Pausa" (Do Not Disturb/Fokus) för ntfy-appen på mobilen, så att notisen faktiskt hörs.

## Filer

| Fil | Vad den är |
|---|---|
| `config.yaml` | Inställningar: butikslista, intervall, slutdatum. Ändringar som laddas upp till GitHub gäller från nästa molnkörning. |
| `config.local.yaml` | Ditt ntfy-ämne, bara på Macen (laddas inte upp) |
| `.github/workflows/bevakare.yml` | Schemat för GitHub-molnet |
| `bevakare.py` | Själva programmet |
| `bevakare.log` | Loggen: tid, status per butik och fel |
| `state.json` | Kommer ihåg senaste lagerstatus, så att du bara får notis vid förändring |

### Ändra vilka butiker som bevakas
Butikerna står under `stores:` i `config.yaml` som `"butiks-ID": Namn`. Lägg till eller ta bort rader. Butiks-ID för andra butiker hittar du genom att fråga mig, eller i Elgigantens butikslista.

## Hur det fungerar (tekniskt, kort)

Elgigantens produktsida hämtar butikslagret från ett öppet API:
`https://www.elgiganten.se/api/trpc/location.getProductStoresWithStock`. Bevakaren gör **ett** vanligt HTTP-anrop per kontroll, som också hämtar priset, och läser listan över butiker som har varan i lager. Den behöver ingen webbläsare, inloggning eller cookies. Vid nätverksfel försöker den igen upp till två gånger med paus (15 s och 45 s).

## Installera om från början (om det behövs)

```bash
cd ~/Projekt/tv-bevakare
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Alternativ: egen molnserver

Om GitHub skulle börja blockeras eller bli opålitligt kan bevakaren köras på en liten VPS, t.ex. Hetzner CX22 (cirka 4 €/mån, betalas per timme). Gör så här:
1. Kopiera mappen dit.
2. Skapa `config.local.yaml` med ntfy-ämnet.
3. Installera enligt ovan.
4. Kör `nohup .venv/bin/python bevakare.py &`.
