#!/usr/bin/env python3
"""Build site/index.html and data/accessories.csv from data/accessories.json."""
import collections, csv, html, json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent

# Functional groups, assigned by keyword on name + product title. First match wins, so order matters.
GROUPS = [
    ("Stands & electronics", r"SIDE STAND|CENTRAL STAND|MIDDLE SUPPORT|T-BOX"),
    ("Protection", r"GUARD|BUMPER|CRASH BAR|SKID|ENGINE LOWER PANEL|ENGINE SIDE COVER|CHAIN GUIDE"),
    ("Luggage racks & mounts", r"BRACKET|3P SYSTEM|4P SYSTEM|TOP MASTER|PLATE \+ SCREWS|ADAPTOR"),
    ("Comfort & ergonomics", r"SEAT|HEATED|HEATING|HANDLEBAR|WINDSHIELD|FOOTREST|CLUTCH|TANKPAD|TANK PAD|BACKREST"),
    ("Luggage: hard cases", r"CASE|SUITCASE|BOXES|INTERNAL BAG"),
    ("Luggage: soft bags", r"\bBAGS?\b|SADDLEBAGS|PETATE"),
    ("Performance & chassis", r"AKRAPOVI|AIR FILTER|TFX|CARTRIDGE|SHOCK|WHEEL"),
    ("Body & styling", r"FENDER|MIRROR"),
]


def match(text):
    for g, pat in GROUPS:
        if re.search(pat, text.upper()):
            return g


def group_of(r):
    # The name is the most specific; product titles of bundle pages ("... SHAD boxes") can mislead.
    return match(r["name"]) or match(r["product"]) or "Other"


d = json.load(open(ROOT / "data" / "accessories.json"))
raw = d["items"]
# Bundle pages (e.g. "450 MT - SHAD boxes") repeat SKUs that also have their own page.
# Keep one row per SKU, taken from the page with the fewest variants (the standalone one).
per_page = collections.Counter(r["url"] for r in raw)
best = {}
for r in raw:
    k = r["sku"] or r["url"]
    if k not in best or per_page[r["url"]] < per_page[best[k]["url"]]:
        best[k] = r
order = ["Protection", "Comfort & ergonomics", "Luggage: hard cases", "Luggage: soft bags",
         "Luggage racks & mounts", "Performance & chassis", "Body & styling", "Stands & electronics", "Other"]
for r in best.values():
    r["group"] = group_of(r)
items = sorted(best.values(), key=lambda r: (order.index(r["group"]), r["name"].lower()))

# Cross-reference with the Hungarian CFMOTO shop by part number (exact, case/space-insensitive).
norm = lambda s: re.sub(r"\s+", "", (s or "").upper())
hu_path = ROOT / "data" / "hu_shop.json"
hu = json.load(open(hu_path)) if hu_path.exists() else {"items": [], "scraped_at": None}
hu_by_sku = {}
for h in hu["items"]:
    if h["sku"] and h["price_huf"]:
        hu_by_sku.setdefault(norm(h["sku"]), h)
for r in items:
    h = hu_by_sku.get(norm(r["sku"]))
    r["hu_price_huf"] = h["price_huf"] if h else None
    r["hu_url"] = h["url"] if h else ""
    r["hu_available"] = h["available"] if h else ""
n_both = sum(1 for r in items if r["hu_url"])
counts = collections.Counter(r["group"] for r in items)
with open(ROOT / "data" / "accessories.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=["group", "name", "product", "sku", "stock", "price_huf", "price_eur", "image", "url",
                                       "hu_price_huf", "hu_available", "hu_url"])
    w.writeheader()
    w.writerows({k: r[k] for k in w.fieldnames} for r in items)
e = html.escape


def fmt_huf(v):
    return "–" if v is None else f"{v:,}".replace(",", " ") + " Ft"


def fmt_eur(v):
    return "–" if v is None else f"{v:,.2f} €"


def hu_cell(r):
    if not r["hu_url"]:
        return ""
    eu, hu_ = r["price_huf"], r["hu_price_huf"]
    diff = ""
    if eu and hu_:
        pct = round((hu_ - eu) / eu * 100)
        if abs(pct) > 50:  # e.g. a full pannier set listed suspiciously cheap on one site
            diff = '<span class="cmp warn" title="Same part number, very different price: check what each listing includes">Big gap: check both listings</span>'
        elif abs(pct) < 2:
            diff = '<span class="cmp same">about the same</span>'
        elif pct < 0:
            diff = f'<span class="cmp win">HU {-pct}% cheaper</span>'
        else:
            diff = f'<span class="cmp lose">HU {pct}% dearer</span>'
    oos = "" if r["hu_available"] in ("InStock", "") else f' <span class="sub">({e(r["hu_available"])})</span>'
    return (f'<div class="hu"><a href="{e(r["hu_url"])}" target="_blank" rel="noopener">cfmoto-<wbr>official.hu</a> '
            f'<strong>{fmt_huf(hu_)}</strong>{oos}</div>{diff}')


rows = []
for r in items:
    name = r["name"] if r["name"] and r["name"] != r["product"] else r["product"]
    sub = f'<div class="sub">{e(r["product"])}</div>' if name != r["product"] else ""
    rows.append(f"""<tr data-name="{e(name.lower())}" data-group="{e(r['group'])}" data-gi="{order.index(r['group'])}" data-huf="{r['price_huf'] if r['price_huf'] is not None else -1}" data-eur="{r['price_eur'] or 0}" data-sku="{e(r['sku'] or r['url'])}" data-label="{e(name)}" data-hu="{r['hu_price_huf'] or 0}">
<td class="pick"><input type="checkbox" aria-label="Select {e(name)}"></td>
<td class="img"><a href="{e(r['image'])}" target="_blank" rel="noopener"><img loading="lazy" src="{e(r['image'])}" alt=""></a></td>
<td><span class="tag">{e(r['group'])}</span>{'<span class="both">On both sites</span>' if r['hu_url'] else ''}<a class="name" href="{e(r['url'])}" target="_blank" rel="noopener">{e(name)}</a>{sub}<div class="sku">{e(r['sku'])} · {e(r['stock'])}</div></td>
<td class="num"><strong>{fmt_huf(r['price_huf'])}</strong><div class="sub">{fmt_eur(r['price_eur'])}</div>{hu_cell(r)}</td>
</tr>""")

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CFMOTO 450MT Accessories</title>
<style>
:root{{--bg:#fafaf9;--fg:#1c1917;--muted:#78716c;--line:#e7e5e4;--card:#fff;--accent:#0e7490}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#1c1917;--fg:#f5f5f4;--muted:#a8a29e;--line:#3a3532;--card:#262220;--accent:#22d3ee}}}}
:root[data-theme="dark"]{{--bg:#1c1917;--fg:#f5f5f4;--muted:#a8a29e;--line:#3a3532;--card:#262220;--accent:#22d3ee}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,-apple-system,sans-serif}}
main{{max-width:900px;margin:0 auto;padding:24px 16px 48px}}
h1{{margin:0 0 4px;font-size:24px}}
.meta{{color:var(--muted);font-size:13px;margin-bottom:16px}} .meta a{{color:var(--accent)}}
.bar{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}}
input,select{{font:inherit;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg)}}
input{{flex:1;min-width:180px}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}}
th{{text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);padding:10px 12px;border-bottom:1px solid var(--line)}}
td{{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:middle}}
tr:last-child td{{border-bottom:0}}
td.img{{width:112px}}
td.img img{{width:96px;height:96px;object-fit:contain;background:#fff;border-radius:6px;display:block}}
.name{{color:var(--fg);font-weight:600;text-decoration:none}} .name:hover{{color:var(--accent)}}
.sub,.sku{{color:var(--muted);font-size:12px}}
.num{{text-align:right;white-space:nowrap}}
.tag{{display:inline-block;font-size:11px;padding:1px 7px;margin:0 0 3px;border-radius:999px;border:1px solid var(--line);color:var(--muted)}}
.grouped .tag{{display:none}}
.both{{display:inline-block;font-size:11px;padding:1px 7px;margin:0 0 3px 4px;border-radius:999px;background:var(--accent);color:var(--card);font-weight:600}}
.grouped .both{{margin-left:0}}
.hu{{margin-top:6px;font-size:12px;color:var(--muted);white-space:normal}} .cmp{{white-space:normal}} .hu a{{color:var(--accent);text-decoration:none}} .hu strong{{color:var(--fg);font-size:13px}}
.cmp{{display:inline-block;font-size:11px;margin-top:2px;padding:0 6px;border-radius:999px;font-weight:600}}
.cmp.win{{color:#15803d;background:rgba(21,128,61,.12)}} .cmp.lose{{color:#b45309;background:rgba(180,83,9,.12)}} .cmp.same{{color:var(--muted);background:var(--bg)}} .cmp.warn{{color:#b91c1c;background:rgba(185,28,28,.12)}}
#sum .mix{{color:var(--muted);font-size:12px}} #sum .mix b{{color:#15803d}}
tr.ghead td{{background:var(--bg);font-weight:700;font-size:13px;letter-spacing:.02em;padding:14px 12px 8px;color:var(--accent)}}
.name{{display:block}}
td.pick{{width:36px;padding-right:0}}
td.pick input{{width:20px;height:20px;min-width:0;accent-color:var(--accent);cursor:pointer}}
#tb tr[data-sku]{{cursor:pointer}}
#tb tr.sel td{{background:var(--selbg)}}
:root{{--selbg:#ecfeff}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--selbg:#16323a}}}}
:root[data-theme="dark"]{{--selbg:#16323a}}
main{{padding-bottom:120px}}
#sum{{position:fixed;left:0;right:0;bottom:0;z-index:10;background:var(--card);border-top:1px solid var(--line);box-shadow:0 -6px 20px rgba(0,0,0,.12)}}
#sum .in{{max-width:900px;margin:0 auto;padding:12px 16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
#sum .tot{{font-size:22px;font-weight:700;font-variant-numeric:tabular-nums}}
#sum .cnt{{color:var(--muted);font-size:13px}}
#sum .sp{{flex:1}}
#sum button,#sum label{{font:inherit;font-size:13px;padding:7px 12px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--fg);cursor:pointer;display:inline-flex;align-items:center;gap:6px}}
#sum button:disabled{{opacity:.45;cursor:default}}
#sum label input{{min-width:0;width:16px;height:16px;padding:0;accent-color:var(--accent)}}
#list{{max-width:900px;margin:0 auto;padding:0 16px;max-height:40vh;overflow:auto}}
#list[hidden]{{display:none}}
#list table{{border:0;border-radius:0;margin-bottom:8px}}
#list td{{padding:6px 4px;font-size:13px}}
#list .x{{border:0;background:none;color:var(--muted);cursor:pointer;font-size:16px;padding:0 4px}}
#list .gsub td{{color:var(--muted);font-size:12px;padding-top:2px}}
.name,.sub,.sku{{overflow-wrap:anywhere}}
@media (max-width:520px){{
  table{{table-layout:fixed}}
  th:nth-child(1),td.pick{{width:30px}} th:nth-child(2),td.img{{width:60px}} th:nth-child(4),td.num{{width:104px}}
  td.img img{{width:52px;height:52px}} td{{padding:8px 4px}} th{{padding:8px 4px}}
  .name{{font-size:14px}} .num strong{{font-size:13px}}
  #sum .in{{gap:8px}} #sum .tot{{font-size:18px}} #sum .sp{{display:none}}
  #sum button,#sum label{{padding:6px 9px}}
  #list td.g{{display:none}}
}}
</style></head><body><main>
<h1>CFMOTO 450MT accessories</h1>
<div class="meta">{len(items)} items from <a href="https://cfmotoparts.eu/search-accessories?field_accessory_category_tid=1265">cfmotoparts.eu</a> (450MT category), updated {d.get('scraped_at', '?')}. HUF = retail EUR price × {d['eur_huf']} (ECB rate, {d['rate_date']}), rounded. <a href="accessories.csv" download>Download CSV</a><br>
{n_both} of them are also sold by the Hungarian importer <a href="https://www.cfmoto-official.hu/hu/motorkerekpar-kiegeszitok">cfmoto-official.hu</a> (matched by part number, prices as listed there in HUF incl. VAT, updated {hu.get('scraped_at') or '?'}). Shipping is not included on either side.</div>
<div class="bar"><input id="q" type="search" placeholder="Filter by name or SKU…">
<select id="grp"><option value="">All groups ({len(items)})</option>{''.join(f'<option value="{e(g)}">{e(g)} ({counts[g]})</option>' for g in order if counts[g])}</select>
<select id="shop"><option value="">Both shops and EU-only</option><option value="both">Available on both sites ({n_both})</option><option value="eu">cfmotoparts.eu only ({len(items) - n_both})</option><option value="hucheaper">Cheaper in Hungary</option></select>
<select id="sort"><option value="group">Sort: by group</option><option value="name">Sort: name</option><option value="asc">Price: low → high</option><option value="desc">Price: high → low</option></select></div>
<table><thead><tr><th></th><th>Picture</th><th>Accessory</th><th class="num">Price (HUF)</th></tr></thead>
<tbody id="tb">
{''.join(rows)}
</tbody></table>
</main>
<div id="sum"><div id="list" hidden></div><div class="in">
  <div><div class="tot" id="tot">0 Ft</div><div class="cnt" id="cnt">No items selected. Tick items to add them up.</div><div class="mix" id="mix"></div></div>
  <div class="sp"></div>
  <label><input type="checkbox" id="only"> Selected only</label>
  <button id="det" disabled>Show list</button>
  <button id="clr" disabled>Clear</button>
</div></div>
<script>
const tb=document.getElementById('tb'),q=document.getElementById('q'),s=document.getElementById('sort'),gs=document.getElementById('grp');
const shop=document.getElementById('shop'),only=document.getElementById('only'),det=document.getElementById('det'),clr=document.getElementById('clr'),list=document.getElementById('list');
const all=[...tb.rows];
const KEY='450mt-selection';
let sel=new Set();
try{{sel=new Set(JSON.parse(localStorage.getItem(KEY)||'[]'));}}catch(_){{}}
const huf=v=>String(Math.round(v)).replace(/\\B(?=(\\d{{3}})+(?!\\d))/g,' ')+' Ft';
const eur=v=>v.toLocaleString('en-US',{{minimumFractionDigits:2,maximumFractionDigits:2}})+' €';
function save(){{try{{localStorage.setItem(KEY,JSON.stringify([...sel]));}}catch(_){{}}}}
function updateSum(){{
  const rows=all.filter(x=>sel.has(x.dataset.sku));
  let h=0,e=0,mix=0,hun=0;rows.forEach(x=>{{const a=Math.max(0,+x.dataset.huf),b=+x.dataset.hu;h+=a;e+=+x.dataset.eur;if(b){{hun++;mix+=Math.min(a||b,b);}}else mix+=a;}});
  document.getElementById('mix').innerHTML=hun&&mix<h?`Buying the cheaper of the two shops for each item: <b>${{huf(mix)}}</b> (saves ${{huf(h-mix)}})`:(hun?'cfmotoparts.eu is the cheaper shop for every selected item.':'');
  document.getElementById('tot').textContent=huf(h);
  document.getElementById('cnt').textContent=rows.length?`${{rows.length}} item${{rows.length>1?'s':''}} at cfmotoparts.eu · ${{eur(e)}}`:'No items selected. Tick items to add them up.';
  det.disabled=clr.disabled=!rows.length;
  if(!rows.length){{list.hidden=true;det.textContent='Show list';}}
  all.forEach(x=>{{const on=sel.has(x.dataset.sku);x.classList.toggle('sel',on);x.querySelector('.pick input').checked=on;}});
  // itemised list, by group with subtotals
  const t=document.createElement('table');let cur=null,sub=0;
  const sorted=rows.slice().sort((a,b)=>a.dataset.gi-b.dataset.gi||a.dataset.name.localeCompare(b.dataset.name));
  const flush=()=>{{if(cur!==null){{const r=t.insertRow();r.className='gsub';r.insertCell().colSpan=2;r.cells[0].textContent=cur+' subtotal';const c=r.insertCell();c.className='num';c.textContent=huf(sub);r.insertCell();}}}};
  for(const x of sorted){{
    if(x.dataset.group!==cur){{flush();cur=x.dataset.group;sub=0;}}
    sub+=Math.max(0,+x.dataset.huf);
    const r=t.insertRow();
    r.insertCell().textContent=x.dataset.label;
    r.insertCell().textContent=x.dataset.group;r.cells[1].className='sub g';
    const c=r.insertCell();c.className='num';c.textContent=huf(+x.dataset.huf);
    const b=document.createElement('button');b.className='x';b.textContent='×';b.title='Remove';b.onclick=()=>toggle(x.dataset.sku,false);
    r.insertCell().appendChild(b);
  }}
  flush();
  list.replaceChildren(t);
}}
function toggle(sku,on){{on?sel.add(sku):sel.delete(sku);save();updateSum();if(only.checked)render();}}
tb.addEventListener('click',ev=>{{
  const tr=ev.target.closest('tr[data-sku]');if(!tr||ev.target.closest('a'))return;
  toggle(tr.dataset.sku,!sel.has(tr.dataset.sku));
}});
det.onclick=()=>{{list.hidden=!list.hidden;det.textContent=list.hidden?'Show list':'Hide list';}};
clr.onclick=()=>{{sel.clear();save();updateSum();render();}};
only.onchange=()=>render();
function head(g,n){{const tr=document.createElement('tr');tr.className='ghead';tr.innerHTML='<td colspan="4"></td>';tr.firstChild.textContent=g+' · '+n;return tr;}}
function render(){{
  const t=q.value.toLowerCase(),g=gs.value,k=s.value;
  const r=all.filter(x=>(!g||x.dataset.group===g)&&(!shop.value||(shop.value==='both'?+x.dataset.hu>0:shop.value==='eu'?!+x.dataset.hu:(+x.dataset.hu>0&&+x.dataset.hu<+x.dataset.huf)))&&(!only.checked||sel.has(x.dataset.sku))&&x.textContent.toLowerCase().includes(t));
  const byName=(a,b)=>a.dataset.name.localeCompare(b.dataset.name);
  if(k==='group')r.sort((a,b)=>a.dataset.gi-b.dataset.gi||byName(a,b));
  else r.sort((a,b)=>k==='name'?byName(a,b):(k==='asc'?1:-1)*(a.dataset.huf-b.dataset.huf));
  const out=[];
  if(k==='group'){{let cur=null;for(const x of r){{if(x.dataset.group!==cur){{cur=x.dataset.group;out.push(head(cur,r.filter(y=>y.dataset.group===cur).length));}}out.push(x);}}}}
  else out.push(...r);
  tb.replaceChildren(...out);
  document.body.classList.toggle('grouped',k==='group');
}}
shop.onchange=render;q.oninput=render;s.onchange=render;gs.onchange=render;render();updateSum();
</script></body></html>"""
(ROOT / "site").mkdir(exist_ok=True)
(ROOT / "site" / "index.html").write_text(page)
(ROOT / "site" / "accessories.csv").write_bytes((ROOT / "data" / "accessories.csv").read_bytes())
print("wrote site/index.html")
