#!/usr/bin/env python3
"""
Mercari.jp new-listing watch — V Jump PJ13 / Berry Match (One Piece card).
Runs on GitHub Actions (Playwright). TG alert on NEW listing ids.
State = repo state.json. Requires guest search to render (results contain 円;
SG$ cells are ads and are filtered out).
"""
import json, os, re, sys, urllib.request, urllib.parse
from datetime import datetime, timezone

QUERIES = [
    ("vjump_pj13", "vジャンプ pj13"),
    ("pj13_broad", "pj13"),
]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def tg(text):
    tok, cid = os.environ.get("TG_BOT_TOKEN",""), os.environ.get("TG_CHAT_ID","")
    if not tok or not cid:
        print("TG secrets missing"); return False
    url = f"https://api.telegram.org/bot{tok}/sendMessage?chat_id={cid}&text={urllib.parse.quote(text)}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"mw"}), timeout=20) as r:
            body = r.read().decode()
        print("TG:", '"ok":true' in body.replace(" ",""))
        return '"ok":true' in body.replace(" ","")
    except Exception as e:
        print("TG err:", e); return False

def scrape(pg):
    """Return list of {id,name,price} from rendered search page."""
    seen, items = set(), []
    for key, q in QUERIES:
        url = f"https://jp.mercari.com/search?keyword={urllib.parse.quote(q)}&status=on_sale"
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=60000)
            pg.wait_for_timeout(6000)
        except Exception as e:
            print(f"goto {key} err: {e}"); continue
        cells = pg.eval_on_selector_all(
            'a[href*="jp.mercari.com/item/"]',
            "els => els.map(e => ({href: e.href, t: (e.innerText||'').replace(/\\s+/g,' ').trim()}))")
        n = 0
        for c in cells:
            m = re.search(r"(m\d{8,})", c["href"])
            if not m or m.group(1) in seen:
                continue
            t = c["t"]
            if "円" not in t:          # ads render as SG$/US$ — skip
                continue
            seen.add(m.group(1))
            price = ""
            pm = re.search(r"([\\d,]+)\\s*円", t)
            if pm: price = pm.group(1) + "円"
            name = re.sub(r"^.*?円\\s*", "", t).strip() or t[:80]
            items.append({"id": m.group(1), "name": name[:100], "price": price,
                          "query": key, "url": c["href"].split("?")[0]})
            n += 1
        print(f"{key}: {n} real items ({len(cells)} raw cells)")
    return items

def main():
    try:
        state = json.load(open("state.json"))
    except Exception:
        state = {"known": [], "runs": 0}
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(locale="ja-JP", timezone_id="Asia/Tokyo", user_agent=UA,
                            viewport={"width": 1366, "height": 900})
        pg = ctx.new_page()
        items = scrape(pg)
        b.close()
    known = set(state.get("known", []))
    fresh = [i for i in items if i["id"] not in known]
    state["known"] = sorted(known | {i["id"] for i in items})[-500:]
    state["runs"] = state.get("runs", 0) + 1
    state["last_run"] = now
    state["last_count"] = len(items)
    json.dump(state, open("state.json", "w"), indent=1)
    print(f"total={len(items)} new={len(fresh)} run={state['runs']}")
    if state["runs"] <= 1:
        tg(f"👀 Mercari watcher first run: {len(items)} PJ13 listings indexed "
           f"({'✅ search renders from GH IPs' if items else '⚠️ ZERO items — guest auth blocked, check logs'}). "
           f"New listings will alert. [{now}]")
        return
    for i in fresh[:5]:
        tg(f"🆕 Mercari PJ13 new listing!\n{i['name']}\n💴 {i['price']}\n{i['url']}\n[{now}]")

if __name__ == "__main__":
    main()
