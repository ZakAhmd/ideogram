#!/usr/bin/env python3
"""
pod_factory.py — one command: ideas -> print-ready designs -> editable SVG -> mockups -> catalog.

For every line in ideas.csv it uses the Ideogram API to:
  1. generate the design with Ideogram 4.5 on a transparent background (PNG, ready for DTF)
  2. convert it to a real, editable SVG with Ideogram Vector
  3. put it on a t-shirt mockup (Ideogram 4.5 edit, the design as the source image)
  4. (optional) upscale the PNG for big prints
Then it writes catalog.html so you can review everything in the browser.

Usage
  export IDEOGRAM_API_KEY="your key"          # ideogram.ai/platform -> API Keys
  pip install requests
  python pod_factory.py ideas.csv              # all ideas
  python pod_factory.py ideas.csv --limit 3    # first 3 only
  python pod_factory.py ideas.csv --upscale    # also make a 2x print file
  python pod_factory.py ideas.csv --quote      # price quote only, nothing is generated

ideas.csv columns: slogan, scene, colors, tee   (tee = black or white)
"""
import argparse, csv, html, json, os, re, sys, time
import requests

BASE = os.environ.get("IDEOGRAM_BASE_URL", "https://api.ideogram.ai")
KEY = os.environ.get("IDEOGRAM_API_KEY", "")
POLL_SECONDS = float(os.environ.get("IDEOGRAM_POLL_SECONDS", "3"))


def api(method, path, quote=False, **kw):
    """Call the Ideogram API. With quote=True the request is only validated and priced (dry_run)."""
    url = BASE + path + ("?dry_run=true" if quote else "")
    for attempt in range(6):                 # retry a dropped connection or a DNS hiccup: 2, 4, 8, 16, 30 s
        try:
            r = requests.request(method, url, headers={"Api-Key": KEY}, timeout=120, **kw)
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if attempt == 5:
                raise
            time.sleep(min(2 ** (attempt + 1), 30))
    if r.status_code == 429 and "Retry-After" in r.headers:
        time.sleep(float(r.headers["Retry-After"]))
        return api(method, path, quote=quote, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
    return r.json()


def wait(generation_id):
    """Poll GET /v2/generations/{id} until the job is completed, then return its data list."""
    while True:
        g = api("GET", f"/v2/generations/{generation_id}")
        if g["status"] == "completed":
            return g["data"], g.get("usage_cost_usd_micros", 0)
        if g["status"] == "failed":
            raise RuntimeError(f"generation {generation_id} failed: {g.get('failure_reason')}")
        time.sleep(POLL_SECONDS)


def run(path, data, files=None, quote=False):
    """Submit a job (async when possible) and return (items, usage_cost_usd) when it is done.
    usage_cost_usd is only filled for usage-priced steps; use --quote to see a price before you run."""
    # Ideogram expects multipart/form-data, even when no file is attached,
    # so every text field is sent as a multipart part too.
    parts = [(k, (None, str(v))) for k, v in data.items()]
    for k, v in (files or {}).items():
        parts.append((k, v))
    res = api("POST", path, quote=quote, files=parts)
    if quote:
        return res, 0
    if res.get("data"):                      # synchronous answer
        return res["data"], res.get("usage_cost_usd_micros", 0) / 1e6
    items, micros = wait(res["generation_id"])
    return items, micros / 1e6


def download(url, path, tries=5):
    """Save an image. Ideogram image URLs expire, so download them right away (retry on a broken connection)."""
    for attempt in range(tries):
        try:
            with requests.get(url, timeout=120) as r:
                r.raise_for_status()
                open(path, "wb").write(r.content)
            return path
        except requests.exceptions.RequestException:
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))


def design_prompt(idea):
    # The POD formula: subject doing something + one twist + 3-5 flat colours + one style + transparent background.
    return (f"T-shirt print, bold flat vector illustration. {idea['scene']} "
            f"Headline text, large and easy to read: \"{idea['slogan']}\". "
            f"Thick outlines, simple flat shapes, high contrast for a {idea['tee']} t-shirt. "
            f"Colors: {idea['colors']} only. Transparent background, isolated artwork.")


def mockup_prompt(idea):
    return (f"Use the uploaded artwork as the print on the front of a {idea['tee']} cotton t-shirt, "
            f"worn by a young developer at a desk with a laptop, natural light, lifestyle product photo. "
            f"Keep the artwork's wording, colors and proportions exactly the same.")


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40] or "design"


def make_one(i, idea, out, upscale, quote):
    """Make one idea. Files that already exist are kept, so a stopped run can simply be started again."""
    folder = os.path.join(out, f"{i:02d}_{slugify(idea['slogan'])}")
    os.makedirs(folder, exist_ok=True)
    png, svg = os.path.join(folder, "design.png"), os.path.join(folder, "design.svg")
    mock, big = os.path.join(folder, "mockup.png"), os.path.join(folder, "print_2x.png")

    # 1) design: Ideogram 4.5, transparent background
    if quote or not os.path.exists(png):
        items, _ = run("/v2/image/generate/ideogram-4-5",
                       {"prompt": design_prompt(idea), "background": "transparent",
                        "quality": "high", "num_images": "1", "async": "true"}, quote=quote)
        if quote:
            return {"step": "design", "quote": items}
        download(items[0]["url"], png)

    # 2) editable vector: Ideogram Vector (image -> SVG)
    if not os.path.exists(svg):
        with open(png, "rb") as f:
            items, _ = run("/v2/svg/vectorize/ideogram-vector-1", {"mode": "auto"}, files={"image": f})
        download(items[0]["url"], svg)

    # 3) mockup: Ideogram 4.5 with the design as the source image
    if not os.path.exists(mock):
        with open(png, "rb") as f:
            items, _ = run("/v2/image/generate/ideogram-4-5",
                           {"prompt": mockup_prompt(idea), "quality": "medium", "size": "1536x2048",
                            "num_images": "1", "async": "true"}, files={"images": ("design.png", f, "image/png")})
        download(items[0]["url"], mock)

    # 4) optional: bigger print file (keeps transparency)
    if upscale and not os.path.exists(big):
        for factor in ("2x", "x2"):          # docs show "2x"; some clients use "x2"
            try:
                with open(png, "rb") as f:
                    items, _ = run("/v2/image/upscale/auto", {"upscale_factor": factor, "async": "true"},
                                   files={"image": f})
                download(items[0]["url"], big)
                break
            except RuntimeError as e:
                if "400" not in str(e) or factor == "x2":
                    raise

    info = {"slogan": idea["slogan"], "tee": idea["tee"], "folder": folder,
            "design_png": png, "design_svg": svg, "mockup": mock,
            "print_2x": big if os.path.exists(big) else None,
            "svg_shapes": open(svg, encoding="utf-8", errors="ignore").read().count("<path")}
    json.dump(info, open(os.path.join(folder, "info.json"), "w"), indent=2, ensure_ascii=False)
    return info


def catalog(results, out):
    cards = []
    for r in results:
        rel = lambda p: os.path.relpath(p, out) if p else ""
        cards.append(f"""<figure><img src="{rel(r['mockup'])}" alt="mockup">
<img class="d {html.escape(r['tee'])}" src="{rel(r['design_png'])}" alt="design">
<figcaption><b>{html.escape(r['slogan'])}</b><br>{r['svg_shapes']} vector shapes
· <a href="{rel(r['design_svg'])}">SVG</a> · <a href="{rel(r['design_png'])}">PNG</a></figcaption></figure>""")
    page = f"""<!doctype html><meta charset="utf-8"><title>POD Factory catalog</title>
<style>body{{font-family:system-ui;margin:24px;background:#f4f2ee}}main{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}}
figure{{margin:0;background:#fff;border-radius:12px;padding:10px}}img{{width:100%;border-radius:8px}}img.d{{width:40%;padding:6px;margin-top:6px}}
img.d.black{{background:#111}}img.d.white{{background:#eee}}figcaption{{font-size:13px;margin-top:6px}}</style>
<h1>POD Factory — {len(results)} designs</h1><main>{''.join(cards)}</main>"""
    path = os.path.join(out, "catalog.html")
    open(path, "w", encoding="utf-8").write(page)
    return path


def main():
    ap = argparse.ArgumentParser(description="Ideas -> designs -> SVG -> mockups, with the Ideogram API")
    ap.add_argument("ideas")
    ap.add_argument("--out", default="out")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--upscale", action="store_true")
    ap.add_argument("--quote", action="store_true", help="price of one design image, nothing is generated")
    a = ap.parse_args()
    if not KEY:
        sys.exit("Set IDEOGRAM_API_KEY first (ideogram.ai/platform -> API Keys).")
    ideas = list(csv.DictReader(open(a.ideas, encoding="utf-8")))
    if a.limit:
        ideas = ideas[: a.limit]
    os.makedirs(a.out, exist_ok=True)
    if a.quote:
        print(json.dumps(make_one(1, ideas[0], a.out, False, True), indent=2))
        return
    results, t0 = [], time.time()
    for i, idea in enumerate(ideas, 1):
        print(f"[{i}/{len(ideas)}] {idea['slogan']} ...", flush=True)
        try:
            r = make_one(i, idea, a.out, a.upscale, False)
            results.append(r)
            print(f"      done: {r['svg_shapes']} vector shapes", flush=True)
        except Exception as e:                 # one bad idea should not stop the whole batch
            print(f"      skipped: {e}", flush=True)
    page = catalog(results, a.out)
    print(f"\n{len(results)} designs in {time.time() - t0:.0f}s · open {page}")


if __name__ == "__main__":
    main()
