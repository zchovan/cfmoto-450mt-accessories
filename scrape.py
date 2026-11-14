#!/usr/bin/env python3
"""Scrape CFMOTO 450MT accessories from cfmotoparts.eu into data/accessories.json.

Usage: python3 scrape.py
Respects the site's robots.txt Crawl-delay of 10 seconds (a full run takes ~12 minutes).
Exits non-zero without touching the data file if the result looks broken.
"""
import datetime, html, json, pathlib, re, sys, time, urllib.request

OUT = pathlib.Path(__file__).resolve().parent / "data" / "accessories.json"
MIN_PRODUCTS = 20  # sanity floor: fewer means the site layout changed or the request was blocked

BASE = "https://cfmotoparts.eu"
CATEGORY = 1265  # "450MT" in the accessories category filter
DELAY = 10
UA = {"User-Agent": "Mozilla/5.0 (accessory-list script)"}


def get(url, tries=3):
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as ex:  # network hiccup or 5xx: wait and retry
            if attempt == tries:
                raise
            print(f"retry {attempt} for {url}: {ex}", file=sys.stderr)
            time.sleep(DELAY * 3)


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def eur(s):
    m = re.search(r"([\d.,]+)\s*€", s)
    return float(m.group(1).replace(",", "")) if m else None


def huf_rate():
    xml = get("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml")
    return (float(re.search(r"currency='HUF' rate='([\d.]+)'", xml).group(1)),
            re.search(r"time='([\d-]+)'", xml).group(1))


def main():
    products, page = [], 0
    while True:
        h = get(f"{BASE}/search-accessories?field_accessory_category_tid={CATEGORY}&page={page}")
        arts = re.findall(r'<article.*?</article>', h, re.S)
        if not arts:
            break
        for a in arts:
            href, title = re.search(r'<h3>\s*<a href="([^"]+)">(.*?)</a>', a, re.S).groups()
            img = re.search(r'<img[^>]+src="([^"]+)"', a)
            products.append({"url": BASE + href, "title": clean(title), "image": img.group(1) if img else ""})
        print(f"listing page {page}: {len(products)} products", file=sys.stderr)
        if f"page={page + 1}" not in h:
            break
        page += 1
        time.sleep(DELAY)

    rows = []
    for i, p in enumerate(products, 1):
        time.sleep(DELAY)
        h = get(p["url"])
        imgs = re.findall(r'src="(https://cfmotoparts\.eu/sites/default/files/accessory_product_image/[^"]+)"', h)
        image = p["image"] or (imgs[0] if imgs else "")
        all_trs = re.findall(r'<tr class="[^"]*sku-([^" ]+)[^"]*">(.*?)</tr>', h, re.S)
        var_img = {}  # per-variant photos live in a second table keyed by the same sku class
        for sku, tr in all_trs:
            m = re.search(r'<img[^>]+src="([^"]+)"', tr)
            if m and "add-to-cart" not in tr:
                var_img.setdefault(sku, m.group(1))
        trs = [(sku, re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S)) for sku, tr in all_trs]
        trs = [(sku, tds) for sku, tds in trs if len(tds) >= 4]
        for sku, tds in trs:
            rows.append({
                "product": p["title"],
                "sku": clean(tds[0]),
                "name": clean(tds[1]),
                "stock": clean(tds[2]),
                "price_eur": eur(tds[3]),
                "image": var_img.get(sku, image),
                "url": p["url"],
            })
        if not trs:
            rows.append({"product": p["title"], "sku": "", "name": p["title"], "stock": "",
                         "price_eur": None, "image": image, "url": p["url"]})
        print(f"[{i}/{len(products)}] {p['title']}: {len(trs)} variant(s)", file=sys.stderr)

    priced = sum(1 for r in rows if r["price_eur"] is not None)
    if len(products) < MIN_PRODUCTS or priced < len(rows) / 2:
        sys.exit(f"result looks broken ({len(products)} products, {priced}/{len(rows)} priced); data not written")

    rate, date = huf_rate()
    for r in rows:
        r["price_huf"] = round(r["price_eur"] * rate) if r["price_eur"] is not None else None
    OUT.parent.mkdir(exist_ok=True)
    scraped_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    with open(OUT, "w") as f:
        json.dump({"scraped_at": scraped_at, "eur_huf": rate, "rate_date": date, "items": rows},
                  f, ensure_ascii=False, indent=1)
    print(f"done: {len(rows)} rows from {len(products)} products, 1 EUR = {rate} HUF ({date})", file=sys.stderr)


if __name__ == "__main__":
    main()
