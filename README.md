# CFMOTO 450MT accessories

A browsable, filterable list of the accessories offered for the CFMOTO 450MT on
[cfmotoparts.eu](https://cfmotoparts.eu/search-accessories?field_accessory_category_tid=1265),
with pictures, prices converted to HUF, functional groups, and a running total for the items you tick.
Items also sold by the Hungarian importer [cfmoto-official.hu](https://www.cfmoto-official.hu/hu/motorkerekpar-kiegeszitok)
are matched by CFMOTO part number and show both prices.

**Live page:** https://zchovan.github.io/cfmoto-450mt-accessories/

## How it works

| File | What it does |
|---|---|
| `scrape.py` | Reads the 450MT accessory category and every product page (10 s between requests, as the site's robots.txt asks), converts EUR to HUF at the ECB daily rate, writes `data/accessories.json`. |
| `scrape_hu.py` | Reads every product in the motorcycle-accessory subcategories of cfmoto-official.hu (2 s between requests) and takes each product's part number, gross HUF price and stock from its schema.org data. Writes `data/hu_shop.json`. |
| `build.py` | Removes duplicate SKUs, joins Hungarian prices by exact part number, assigns each item to a group (keyword rules in `GROUPS`), writes `data/accessories.csv` and the page `site/index.html`. |
| `.github/workflows/update.yml` | Every Monday: scrape both shops → build → commit changed data → deploy to GitHub Pages. Also runs on every push (rebuild only) and on demand. |

Because the data is committed on each run, `git log -p data/accessories.csv` shows how prices changed over time.

## Run locally

```bash
python3 scrape.py      # ~12 minutes
python3 scrape_hu.py   # ~12 minutes
python3 build.py
open site/index.html
```

No dependencies beyond Python 3.

## Refresh now

GitHub → **Actions** → **Update prices and deploy page** → **Run workflow**.

cfmotoparts.eu prices are retail prices in EUR and their HUF values an approximate conversion; cfmoto-official.hu prices
are as listed there (HUF, incl. VAT). Shipping is not included. Where the same part number has wildly different
prices on the two sites (>50 %), the page flags it instead of comparing, as the listings may not cover the same thing.
