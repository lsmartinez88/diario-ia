#!/usr/bin/env python3
"""Verifica que los feeds de feeds.yaml respondan y tengan items recientes.

Uso: python3 check_feeds.py
Salida: una línea por feed con estado, cantidad de items y fecha del más reciente.
"""

import calendar
import concurrent.futures
import sys
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests
import yaml

TIMEOUT = 15
UA = "Mozilla/5.0 (compatible; diario-ia/1.0; +https://github.com/lsmartinez88/diario-ia)"


def check(feed):
    nombre, url = feed["nombre"], feed["url"]
    try:
        r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": UA})
        if r.status_code != 200:
            return (nombre, url, f"HTTP {r.status_code}", 0, None)
        if feed.get("tipo", "rss") != "rss":
            # fuente API JSON (Hugging Face): alcanza con que responda y tenga items
            datos = r.json()
            n = len(datos) if isinstance(datos, list) else 0
            return (nombre, url, "OK", n, datetime.now(timezone.utc))
        parsed = feedparser.parse(r.content)
        if parsed.bozo and not parsed.entries:
            return (nombre, url, f"no parsea ({type(parsed.bozo_exception).__name__})", 0, None)
        n = len(parsed.entries)
        latest = None
        for e in parsed.entries:
            t = e.get("published_parsed") or e.get("updated_parsed")
            if t:
                dt = datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc)
                if latest is None or dt > latest:
                    latest = dt
        return (nombre, url, "OK", n, latest)
    except requests.exceptions.Timeout:
        return (nombre, url, "timeout", 0, None)
    except Exception as e:
        return (nombre, url, f"error: {type(e).__name__}", 0, None)


def main():
    cfg = yaml.safe_load(Path(__file__).with_name("feeds.yaml").read_text())
    feeds = cfg["feeds"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(check, feeds))

    ok, broken, stale = 0, 0, 0
    now = datetime.now(timezone.utc)
    for nombre, url, status, n, latest in results:
        if status == "OK":
            age = f"{(now - latest).days}d" if latest else "sin fechas"
            fresh = latest and (now - latest).days <= 7
            mark = "✓" if fresh else "~"
            if fresh:
                ok += 1
            else:
                stale += 1
            print(f"{mark} {nombre:32} {n:3} items, último: {age:10} {url}")
        else:
            broken += 1
            print(f"✗ {nombre:32} {status:24} {url}")

    print(f"\n{ok} frescos, {stale} sin actividad reciente, {broken} rotos, de {len(feeds)} totales")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
