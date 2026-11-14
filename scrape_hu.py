#!/usr/bin/env python3
"""Scrape motorcycle accessories from the Hungarian CFMOTO shop (cfmoto-official.hu) into data/hu_shop.json.

Each product page carries schema.org JSON-LD with the CFMOTO part number (sku/mpn), the gross HUF
price and availability; build.py matches those part numbers against the cfmotoparts.eu list.

Usage: python3 scrape_hu.py
Waits 2 seconds between requests (robots.txt sets no crawl delay); a full run takes ~12 minutes.
Exits non-zero without touching the data file if the result looks broken.
"""
import datetime, html, json, pathlib, re, sys, time, urllib.request

BASE = "https://www.cfmoto-official.hu"
# Subcategories of /hu/motorkerekpar-kiegeszitok (motorcycle accessories)
CATEGORIES = [
    "motorkerekpar-tartozekok-hasznos",
    "vedorudak",
    "hasznos-motoros-cikkek",
    "motorkerekpar-huzatok",
    "motoros-dobozok-es-taskak",
    "motorkerekpar-kipufogok",
    "motorkerekpar-tukrok",
    "szelvedok-es-szelterelok",
]
DELAY = 2
MAX_PAGES = 40  # per category, safety stop
MIN_PRODUCTS = 50
OUT = pathlib.Path(__file__).resolve().parent / "data" / "hu_shop.json"
UA = {"User-Agent": "Mozilla/5.0 (accessory-list script)"}


def get(url, tries=3):
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as ex:
            if attempt == tries:
                raise
            print(f"retry {attempt} for {url}: {ex}", file=sys.stderr)
            time.sleep(DELAY * 5)


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def product_jsonld(page):
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for d in data if isinstance(data, list) else [data]:
            if isinstance(d, dict) and d.get("@type") == "Product":
                return d
    return None


def main():
    listing = {}  # url -> {name, image, category}
    for cat in CATEGORIES:
        for page in range(1, MAX_PAGES + 1):
            url = f"{BASE}/hu/{cat}" + (f"/page/{page}" if page > 1 else "")
            h = get(url)
            time.sleep(DELAY)
            cards = re.findall(
                r'<div class="category-product-image">.*?<img[^>]+src="([^"]+)".*?'
                r'<h2><a class="text-decoration-none" href="([^"]+)">(.*?)</a></h2>', h, re.S)
            new = 0
            for img, href, name in cards:
                if href not in listing:
                    listing[href] = {"name": clean(name), "image": img, "category": cat}
                    new += 1
            print(f"{cat} p{page}: {len(cards)} cards, {new} new", file=sys.stderr)
            if not cards or not new or f"/hu/{cat}/page/{page + 1}" not in h:
                break

    items = []
    for i, (url, p) in enumerate(listing.items(), 1):
        page = get(url)
        time.sleep(DELAY)
        ld = product_jsonld(page) or {}
        offer = ld.get("offers") or {}
        if isinstance(offer, list):
            offer = offer[0] if offer else {}
        sku = (ld.get("sku") or ld.get("mpn") or "").strip()
        if not sku:
            m = re.search(r'Referencia:\s*<span>([^<]+)</span>', page)
            sku = m.group(1).strip() if m else ""
        price = offer.get("price")
        items.append({
            "name": p["name"],
            "sku": sku,
            "price_huf": round(float(price)) if price not in (None, "") else None,
            "available": (offer.get("availability") or "").rsplit("/", 1)[-1],
            "image": p["image"],
            "url": url,
            "category": p["category"],
        })
        print(f"[{i}/{len(listing)}] {sku or '?'} {p['name'][:60]}", file=sys.stderr)

    with_sku = sum(1 for r in items if r["sku"])
    if len(items) < MIN_PRODUCTS or with_sku < len(items) / 2:
        sys.exit(f"result looks broken ({len(items)} products, {with_sku} with part number); data not written")
    OUT.parent.mkdir(exist_ok=True)
    scraped_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    with open(OUT, "w") as f:
        json.dump({"scraped_at": scraped_at, "source": f"{BASE}/hu/motorkerekpar-kiegeszitok", "items": items},
                  f, ensure_ascii=False, indent=1)
    print(f"done: {len(items)} products, {with_sku} with part number", file=sys.stderr)


if __name__ == "__main__":
    main()
