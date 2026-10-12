"""Lagerbevakare för Elgiganten: notifierar via ntfy när en vald butik får in en produkt.

Kör:  .venv/bin/python bevakare.py          (loopar tills stop_at)
      .venv/bin/python bevakare.py --once   (en kontroll, visar status, skickar inga notiser)
"""

import argparse
import json
import logging
import os
import random
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import yaml

BASE_DIR = Path(__file__).resolve().parent
TZ = ZoneInfo("Europe/Stockholm")
API_URL = "https://www.elgiganten.se/api/trpc/location.getProductStoresWithStock,product.getDynamicProductData"

log = logging.getLogger("bevakare")


class BlockedError(Exception):
    """Sajten verkar blockera oss (403/429, CAPTCHA, bot-skydd)."""


class FormatError(Exception):
    """Svaret ser inte ut som förväntat."""


def load_config():
    with open(BASE_DIR / "config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # ntfy-ämnet hålls utanför GitHub: läses från miljövariabeln NTFY_TOPIC (GitHub Secret)
    # eller från den lokala filen config.local.yaml.
    local = BASE_DIR / "config.local.yaml"
    if local.exists():
        with open(local, encoding="utf-8") as f:
            cfg["ntfy"].update((yaml.safe_load(f) or {}).get("ntfy", {}))
    if os.environ.get("NTFY_TOPIC"):
        cfg["ntfy"]["topic"] = os.environ["NTFY_TOPIC"]
    if not cfg["ntfy"].get("topic"):
        sys.exit("Inget ntfy-ämne: sätt NTFY_TOPIC eller topic i config.local.yaml")
    cfg["stores"] = {str(k): v for k, v in cfg["stores"].items()}
    return cfg


def setup_logging(cfg):
    fmt = logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S")
    log.setLevel(logging.INFO)
    for handler in (logging.StreamHandler(sys.stdout),
                    logging.FileHandler(BASE_DIR / cfg["files"]["log"], encoding="utf-8")):
        handler.setFormatter(fmt)
        log.addHandler(handler)


# ---------- ntfy ----------

def notify(cfg, title, message, priority=3, tags=None, click=None):
    payload = {"topic": cfg["ntfy"]["topic"], "title": title, "message": message, "priority": priority}
    if tags:
        payload["tags"] = tags
    if click:
        payload["click"] = click
    try:
        r = httpx.post(cfg["ntfy"]["server"], json=payload, timeout=15)
        r.raise_for_status()
        log.info("Notis skickad: %s", title)
        return True
    except httpx.HTTPError as e:
        log.error("Kunde inte skicka notis (%s): %s", title, e)
        return False


# ---------- Elgiganten ----------

def fetch(cfg, client):
    """Ett HTTP-anrop som returnerar (butiker_med_lager, pris). Retry med backoff vid nätverksfel."""
    sku = cfg["product"]["sku"]
    loc = cfg["location"]
    inp = {"0": {"sku": sku, "storeId": str(loc["store_id"]), "lat": loc["lat"], "lng": loc["lng"]},
           "1": {"sku": sku}}
    params = {"batch": "1", "input": json.dumps(inp, separators=(",", ":"))}

    backoffs = cfg["errors"]["backoff_seconds"]
    attempts = cfg["errors"]["retries"] + 1
    for attempt in range(attempts):
        try:
            r = client.get(API_URL, params=params)
            break
        except httpx.TransportError as e:
            if attempt == attempts - 1:
                raise
            wait = backoffs[min(attempt, len(backoffs) - 1)]
            log.warning("Nätverksfel (%s), försöker igen om %s s", e, wait)
            time.sleep(wait)

    is_json = "json" in r.headers.get("content-type", "")
    body_lower = r.text[:5000].lower()
    if r.status_code in (403, 429) or (not is_json and ("captcha" in body_lower or "challenge" in body_lower)):
        raise BlockedError(f"HTTP {r.status_code}, content-type {r.headers.get('content-type')}")
    if r.status_code >= 500:
        raise httpx.HTTPStatusError(f"Serverfel HTTP {r.status_code}", request=r.request, response=r)
    if r.status_code != 200 or not is_json:
        raise FormatError(f"Oväntat svar: HTTP {r.status_code}, content-type {r.headers.get('content-type')}")

    return parse(r.json())


def parse(data):
    try:
        stock = data[0]["result"]["data"]
        entries = [stock["primary"], *stock["other"]] if stock.get("primary") else list(stock["other"])
        int(stock["storesWithStock"])
        in_stock = {}
        for s in entries:
            if s["stock"]["inStock"]:
                in_stock[str(s["id"])] = {"name": s["displayName"], "level": s["stock"].get("level")}
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise FormatError(f"Svarsformatet har ändrats: {e!r}") from e

    price = None
    try:
        price = data[1]["result"]["data"]["price"]["current"][0]
    except (KeyError, IndexError, TypeError):
        log.warning("Kunde inte läsa priset ur svaret")
    return in_stock, price, stock["storesWithStock"]


# ---------- tillstånd ----------

def load_state(path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("state.json var trasig, börjar om")
    return {"stores": {}, "failures": 0, "broken_notified": False}


def save_state(path, state):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def fmt_price(price):
    return f"{price:,.0f} kr".replace(",", " ") if price is not None else "okänt pris"


def fmt_level(level):
    return f"{level} st" if level else "antal okänt"


def status_lines(cfg, in_stock):
    return [f"{name}: {fmt_level(in_stock[sid]['level']) if sid in in_stock else '0'}"
            for sid, name in cfg["stores"].items()]


# ---------- huvudloop ----------

def run_check(cfg, client, state, send=True):
    in_stock, price, total = fetch(cfg, client)
    watched_now = {sid: v for sid, v in in_stock.items() if sid in cfg["stores"]}

    log.info("Kontroll OK. Pris %s. Lager i %s butiker totalt, %d av %d bevakade.",
             fmt_price(price), total, len(watched_now), len(cfg["stores"]))
    for line in status_lines(cfg, in_stock):
        log.info("   %s", line)

    url = cfg["product"]["url"]
    prev = state["stores"]
    for sid, name in cfg["stores"].items():
        was = prev.get(sid, {}).get("in_stock", False)
        now = sid in watched_now
        if now and not was:
            lvl = watched_now[sid]["level"]
            log.info(">>> NYTT LAGER: %s (%s)", name, fmt_level(lvl))
            if send:
                notify(cfg, f"I lager: {name}",
                       f"{cfg['product']['name']}\n{name}: {fmt_level(lvl)}\nPris: {fmt_price(price)}\n{url}",
                       priority=5, tags=["tv", "tada"], click=url)
        elif was and not now:
            log.info("<<< Lagret borta: %s", name)
            if send:
                notify(cfg, f"Slut igen: {name}",
                       f"{cfg['product']['name']} finns inte längre i lager i {name}.\n{url}",
                       priority=3, tags=["x"], click=url)
        prev[sid] = {"in_stock": now, "level": watched_now.get(sid, {}).get("level")}

    if state.get("broken_notified") and send:
        notify(cfg, "Bevakaren fungerar igen", "Lagerkontrollerna lyckas igen.", tags=["white_check_mark"])
    state["failures"] = 0
    state["broken_notified"] = False
    state["last_ok"] = datetime.now(TZ).isoformat(timespec="seconds")
    return in_stock, price


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="kör en kontroll och visa status, utan notiser")
    ap.add_argument("--max-minutes", type=float, help="avsluta efter så här många minuter (för GitHub Actions)")
    ap.add_argument("--quiet-start", action="store_true", help="skicka startnotis bara första gången (inget sparat tillstånd)")
    args = ap.parse_args()

    cfg = load_config()
    setup_logging(cfg)
    state_path = BASE_DIR / cfg["files"]["state"]
    stop_at = datetime.strptime(cfg["schedule"]["stop_at"], "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    client = httpx.Client(timeout=30, headers={
        "User-Agent": cfg["user_agent"],
        "Accept": "application/json",
        "Accept-Language": "sv-SE,sv;q=0.9",
        "Referer": cfg["product"]["url"],
    })

    if args.once:
        state = load_state(state_path)
        run_check(cfg, client, {"stores": dict(state["stores"])}, send=False)
        return

    running = True

    def stop(signum, _frame):
        nonlocal running
        log.info("Avslutar (signal %s)", signum)
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    if datetime.now(TZ) >= stop_at:
        log.info("Slutdatum %s har passerats, startar inte.", stop_at)
        return

    log.info("Bevakaren startar. Bevakar %d butiker till %s.", len(cfg["stores"]), stop_at.strftime("%Y-%m-%d %H:%M"))
    first_run = not state_path.exists()
    state = load_state(state_path)
    minutes = round(cfg["schedule"]["interval_seconds"] / 60)
    if first_run or not args.quiet_start:
        notify(cfg, "Bevakaren har startat",
               f"Testnotis: bevakar {cfg['product']['name']} i {len(cfg['stores'])} Stockholmsbutiker "
               f"var {minutes}:e minut till {stop_at:%d/%m %H:%M}.", tags=["eyes"], click=cfg["product"]["url"])
    session_end = time.monotonic() + args.max_minutes * 60 if args.max_minutes else float("inf")

    threshold = cfg["errors"]["failures_before_alert"]
    while running and datetime.now(TZ) < stop_at and time.monotonic() < session_end:
        try:
            run_check(cfg, client, state)
        except BlockedError as e:
            log.error("Elgiganten verkar blockera anropen: %s. Stoppar.", e)
            notify(cfg, "Bevakaren stoppad: blockerad",
                   f"Elgiganten verkar blockera bevakaren ({e}). Den har stoppats och försöker inte kringgå "
                   "spärren. Kolla lagret manuellt på sidan.", priority=4, tags=["warning"], click=cfg["product"]["url"])
            save_state(state_path, state)
            return
        except (httpx.HTTPError, FormatError, ValueError) as e:
            state["failures"] = state.get("failures", 0) + 1
            log.error("Kontrollen misslyckades (%d i rad): %s", state["failures"], e)
            if state["failures"] >= threshold and not state.get("broken_notified"):
                notify(cfg, "Bevakaren är trasig",
                       f"{state['failures']} kontroller i rad har misslyckats. Senaste fel: {e}\n"
                       "Saknade notiser betyder alltså INTE att lagret är tomt. Kolla manuellt.",
                       priority=4, tags=["warning"], click=cfg["product"]["url"])
                state["broken_notified"] = True
        save_state(state_path, state)

        delay = cfg["schedule"]["interval_seconds"] + random.uniform(-1, 1) * cfg["schedule"]["jitter_seconds"]
        wake = min(time.monotonic() + delay, session_end)
        while running and time.monotonic() < wake:
            time.sleep(1)

    if running and datetime.now(TZ) >= stop_at:
        log.info("Slutdatum nått, bevakaren avslutas.")
        notify(cfg, "Bevakaren avslutad", "Kampanjperioden är slut, bevakaren har stängts av.", tags=["checkered_flag"])


if __name__ == "__main__":
    main()
