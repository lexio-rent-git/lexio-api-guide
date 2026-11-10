#!/usr/bin/env python3
"""Copie locale (SQLite) des locations d'une agence Lexio Rent, tenue à jour par GET /events.

Usage :
    export LEXIO_API_KEY="lck_..."       # clé du loueur, scope rentals.read suffisant
    python sync_locations.py --db locations.sqlite
    python sync_locations.py --db locations.sqlite --once   # une passe puis sortie

Documentation : https://docs.lexio.rent/synchronisation
Guide : https://docs.page/lexio-rent-git/lexio-api-guide
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sqlite3
import sys
import time

import requests

BASE_URL = "https://api.lexio.rent/api/external/v1"
PAGE_SIZE = 100
IDLE_SECONDS = 30
STOP = False


def _stop(*_):
    global STOP
    STOP = True


class Store:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS rentals ("
            " id TEXT PRIMARY KEY, number TEXT, status TEXT, start_at TEXT, end_at TEXT,"
            " vehicle_plate TEXT, total_ttc REAL, currency TEXT, updated_at TEXT, raw TEXT)"
        )
        self.db.execute("CREATE TABLE IF NOT EXISTS state (k TEXT PRIMARY KEY, v TEXT)")
        self.db.commit()

    def upsert(self, r: dict) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO rentals VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                r["id"], r.get("number"), r.get("status"),
                (r.get("period") or {}).get("startAt"), (r.get("period") or {}).get("endAt"),
                (r.get("vehicle") or {}).get("plate"), r.get("totalTTC"), r.get("currency"),
                r.get("updatedAt"), json.dumps(r, ensure_ascii=False),
            ),
        )

    def delete(self, rental_id: str) -> None:
        self.db.execute("DELETE FROM rentals WHERE id = ?", (rental_id,))

    def load_cursor(self) -> str | None:
        row = self.db.execute("SELECT v FROM state WHERE k = 'cursor'").fetchone()
        return row[0] if row else None

    def save_cursor(self, cursor: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO state VALUES ('cursor', ?)", (cursor,))
        self.db.commit()  # le curseur et les lignes de la page sont validés ensemble

    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM rentals").fetchone()[0]


def lexio_session() -> requests.Session:
    key = os.environ.get("LEXIO_API_KEY")
    if not key:
        sys.exit("LEXIO_API_KEY manquante (clé lck_... fournie par le loueur).")
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "User-Agent": "lexio-api-guide-sync/1.0 (+https://github.com/lexio-rent-git/lexio-api-guide)",
    })
    return s


def get(session: requests.Session, path: str, params: dict | None = None, attempts: int = 6):
    """GET avec respect de Retry-After (429) et renvoi sur erreur réseau ou 502/503/504."""
    for attempt in range(attempts):
        try:
            r = session.get(f"{BASE_URL}{path}", params=params, timeout=30)
        except (requests.ConnectionError, requests.Timeout):
            time.sleep(min(2 ** attempt, 60))
            continue
        if r.status_code in (429, 500, 502, 503, 504):  # une lecture se renvoie sans risque
            time.sleep(int(r.headers.get("Retry-After", min(2 ** attempt, 60))))
            continue
        return r
    raise RuntimeError(f"GET {path} : abandon après {attempts} essais")


def check(r: requests.Response) -> dict:
    if r.ok:
        return r.json()
    try:
        problem = r.json()
    except ValueError:
        problem = {}
    sys.exit(
        f"Erreur {r.status_code} {problem.get('code', '')} : {problem.get('detail', r.text[:200])}"
        f" (X-Request-Id {r.headers.get('X-Request-Id', '?')})"
    )


def initial_sync(session, store: Store) -> str:
    cursor = check(get(session, "/events", {"start": "LATEST"}))["nextCursor"]
    params = {"limit": PAGE_SIZE}
    while True:
        page = check(get(session, "/rentals", params))
        for rental in page["data"]:
            store.upsert(rental)
        if page.get("nextCursor") is None:
            break
        params["cursor"] = page["nextCursor"]
    store.save_cursor(cursor)
    print(f"Copie initiale : {store.count()} locations.")
    return cursor


def follow(session, store: Store, once: bool) -> None:
    cursor = store.load_cursor() or initial_sync(session, store)
    while not STOP:
        r = get(session, "/events", {"cursor": cursor, "limit": PAGE_SIZE})
        if r.status_code == 410:  # CURSOR_EXPIRED : plus de 30 jours d'arrêt
            print("Curseur expiré, nouvelle copie complète.")
            cursor = initial_sync(session, store)
            continue
        page = check(r)
        for event in page["data"]:
            rental_id = event["resource"]["id"]
            if event["type"] == "rental.deleted":
                store.delete(rental_id)
                continue
            rr = get(session, f"/rentals/{rental_id}")
            if rr.status_code == 404:
                store.delete(rental_id)
                continue
            store.upsert(check(rr)["data"])
        cursor = page["nextCursor"]
        store.save_cursor(cursor)
        if page["data"]:
            print(f"{len(page['data'])} événement(s) traité(s), {store.count()} locations en base.")
        if len(page["data"]) < PAGE_SIZE:
            if once:
                return
            for _ in range(IDLE_SECONDS):
                if STOP:
                    return
                time.sleep(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default="locations.sqlite", help="fichier SQLite")
    parser.add_argument("--once", action="store_true", help="une passe puis sortie")
    args = parser.parse_args()
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    follow(lexio_session(), Store(args.db), args.once)


if __name__ == "__main__":
    main()
