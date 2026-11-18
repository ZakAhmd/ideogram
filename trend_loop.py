#!/usr/bin/env python3
"""
trend_loop.py — a store that designs new t-shirts from what its customers do.

1. Reads events.csv: how many times each design was viewed, liked, added to cart and sold.
2. Scores every design and keeps the top ones.
3. Asks Ideogram (Describe) what makes each winner work: style, palette, elements.
4. Makes new designs in the same style with new slogans (Ideogram 4.5, the winner as reference).
5. Writes trend_report.html: the winners, why they won, and the new designs to test next week.

Run
  pip install requests
  export IDEOGRAM_API_KEY="your key"
  python trend_loop.py events.csv slogans.txt --top 3 --per-winner 2

events.csv columns: design_file, views, likes, carts, sales
slogans.txt: one new slogan per line (or ask any AI model to suggest them for your audience)
"""
import argparse, csv, html, json, os, sys
from pod_factory import api, run, download, slugify, KEY

WEIGHTS = {"likes": 1, "carts": 3, "sales": 10}   # a sale says more than a like


def score(row):
    views = max(int(row["views"]), 1)
    return sum(int(row[k]) * w for k, w in WEIGHTS.items()) / views


def describe(path):
    with open(path, "rb") as f:
        res = api("POST", "/v2/image/describe/ideogram-4",
                  files=[("include_style_descriptions", (None, "true")), ("image", f)])
    jp = res.get("json_prompt", {})
    style = jp.get("style_description") or {}
    return {"summary": jp.get("high_level_description", ""),
            "style": "; ".join(f"{k}: {v}" for k, v in style.items() if v and not isinstance(v, (list, dict))),
            "palette": style.get("color_palette")}


def main():
    ap = argparse.ArgumentParser(description="New designs from customer behavior, with the Ideogram API")
    ap.add_argument("events")
    ap.add_argument("slogans")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--per-winner", type=int, default=2)
    ap.add_argument("--out", default="trend_out")
    a = ap.parse_args()
    if not KEY:
        sys.exit("Set IDEOGRAM_API_KEY first (ideogram.ai/platform -> API Keys).")
    rows = list(csv.DictReader(open(a.events, encoding="utf-8")))
    slogans = [s.strip() for s in open(a.slogans, encoding="utf-8") if s.strip()]
    winners = sorted(rows, key=score, reverse=True)[: a.top]
    os.makedirs(a.out, exist_ok=True)
    report, n = [], 0
    for w in winners:
        why = describe(w["design_file"])
        new = []
        for _ in range(a.per_winner):
            if n >= len(slogans):
                break
            slogan = slogans[n]; n += 1
            with open(w["design_file"], "rb") as f:
                items, _ = run("/v2/image/generate/ideogram-4-5",
                               {"prompt": f"Create a NEW t-shirt design in exactly the same art style, line weight and "
                                          f"color palette as the uploaded design, with a new illustration that fits this "
                                          f"headline: \"{slogan}\". Large, easy-to-read text. Transparent background.",
                                "background": "transparent", "quality": "high", "async": "true"},
                               files={"images": ("winner.png", f, "image/png")})
            p = download(items[0]["url"], os.path.join(a.out, f"{slugify(slogan)}.png"))
            new.append({"slogan": slogan, "file": os.path.basename(p)})
            print(f"  new: {slogan}", flush=True)
        report.append({"winner": w, "score": round(score(w), 3), "why": why, "new": new})
    json.dump(report, open(os.path.join(a.out, "trend.json"), "w"), indent=2, ensure_ascii=False)
    cards = []
    for r in report:
        w = r["winner"]
        news = "".join(f'<figure><img src="{html.escape(x["file"])}"><figcaption>{html.escape(x["slogan"])}</figcaption></figure>'
                       for x in r["new"])
        cards.append(f"""<section><h2>{html.escape(os.path.basename(w['design_file']))} · score {r['score']}</h2>
<p>{w['views']} views · {w['likes']} likes · {w['carts']} carts · {w['sales']} sales</p>
<p><b>Why it works:</b> {html.escape(r['why']['summary'])}<br><small>{html.escape(r['why']['style'])}</small></p>
<div class="g">{news}</div></section>""")
    page = f"""<!doctype html><meta charset="utf-8"><title>Trend report</title>
<style>body{{font-family:system-ui;margin:24px;background:#f4f2ee}}section{{background:#fff;border-radius:12px;padding:16px;margin:12px 0}}
.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}}img{{width:100%;border-radius:8px}}figure{{margin:0}}</style>
<h1>This week's winners → next week's designs</h1>{''.join(cards)}"""
    open(os.path.join(a.out, "trend_report.html"), "w", encoding="utf-8").write(page)
    print(f"\n{n} new designs · open {a.out}/trend_report.html")


if __name__ == "__main__":
    main()
