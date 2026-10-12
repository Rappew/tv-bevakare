# TV-bevakare: LG 65" C5 hos Elgiganten

Bevakaren kollar var 3:e minut (± 20 sek) om **LG 65" C5 4K OLED evo TV (2025)** (varukod 912307) finns i lager i någon Elgiganten-butik i Stockholms län. Du får en push-notis på mobilen via **ntfy** när:

- en bevakad butik går från 0 till i lager (med butik, antal, pris och länk)
- lagret i den butiken försvinner igen
- bevakaren har slutat fungera (3 misslyckade kontroller i rad), så att du vet att tystnaden inte betyder "inget lager"
- Elgiganten blockerar bevakaren (då stoppar den och försöker inte ta sig förbi spärren)
- bevakaren startar (testnotis) och när den stängs av automatiskt **2026-10-18 23:59**

## Komma igång på mobilen

Öppna ntfy-appen, tryck **+** och prenumerera på ämnet **`tv-bevakare-1f4f73c9`** (server: ntfy.sh).

## Starta, stoppa, se loggen

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

Bevakaren fortsätter köra även om du stänger Terminal-fönstret. `start.sh` kör den med `caffeinate`, som hindrar Macen från att somna. **Obs:** om du stänger locket på en MacBook som går på batteri somnar den ändå. Låt den stå med laddaren i, eller låt locket vara öppet.

Ett tips: stäng av "Pausa" (Do Not Disturb/Fokus) för ntfy-appen på mobilen, så att notisen faktiskt hörs.

## Filer

| Fil | Vad den är |
|---|---|
| `config.yaml` | Inställningar: ntfy-ämne, butikslista, intervall, slutdatum. Ändra och starta om (`./stop.sh` och sedan `./start.sh`). |
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

## Köra när datorn är avstängd (förslag, inte byggt)

**Alternativ 1: Billig molnserver (rekommenderas).** Hyr en minsta VPS, t.ex. Hetzner CX22 (cirka 4 €/mån, betalas per timme, alltså några kronor för en vecka) eller DigitalOcean (cirka 4–6 $/mån). Gör så här:
1. Kopiera mappen dit med `scp`.
2. Kör de tre installationsraderna ovan.
3. Starta med `nohup .venv/bin/python bevakare.py &`, eller som en `systemd`-tjänst som startar om sig själv.

`caffeinate` behövs inte där. Ta bort servern efter 18 oktober. Nackdel: Elgiganten kan behandla datacenter-IP-adresser strängare än hemma-IP. Fungerar det inte, säger bevakaren till via "blockerad"-notisen.

**Alternativ 2: GitHub Actions.** Lägg koden i ett (privat) GitHub-repo och skapa ett schemalagt arbetsflöde (`schedule: cron: "*/5 * * * *"`) som kör `bevakare.py --once`-liknande logik. `state.json` får då sparas mellan körningarna, t.ex. genom att committa den eller med `actions/cache`. Nackdelar:
- 5 minuter är kortaste intervallet.
- GitHub försenar ofta schemalagda körningar med 5–15 minuter eller hoppar över dem vid hög belastning.
- Privata repon har en gräns på gratisminuter.

Det duger, men är mindre pålitligt än en server.
