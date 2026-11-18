#!/usr/bin/env python3
"""
my_pod_studio.py — your own mini print-on-demand studio, in one file.

Your customer types an idea and a slogan, picks a t-shirt color, and gets:
  1. 4 original designs (Ideogram 4.5, transparent background)
  2. a text fix if a letter is wrong (Ideogram 4.5 Precise Edit)
  3. a mockup of the chosen design on a t-shirt (Ideogram 4.5 with the design as a reference)
  4. a bigger print file (Upscale x2)

Two extra pages:
  /quiz   5 questions -> a prompt -> a design that fits the customer's personality
  /swipe  like = the next design uses the liked one as a style reference,
          dislike = the next design moves to a style the customer hasn't rejected

Run
  pip install flask requests
  export IDEOGRAM_API_KEY="your key"
  python my_pod_studio.py          # then open http://127.0.0.1:5000

Rules from the Ideogram API terms you must keep in a real app:
  show "Powered by Ideogram", say the images are made with AI, link Ideogram's usage
  policies, have a privacy policy, and don't let users upload images they don't own.
"""
import os, uuid
from flask import Flask, jsonify, request, send_from_directory
from pod_factory import run, download, KEY

app = Flask(__name__)
JOBS = os.path.abspath(os.environ.get("STUDIO_DIR", "studio_jobs"))
os.makedirs(JOBS, exist_ok=True)

PAGE = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>My POD Studio</title>
<style>body{{font-family:system-ui;max-width:900px;margin:24px auto;padding:0 16px;background:#f4f2ee;color:#111}}
form,.card{{background:#fff;border-radius:12px;padding:16px;margin:12px 0}}input,select,button{{font:inherit;padding:8px;margin:4px 0}}
input[type=text]{{width:100%;box-sizing:border-box}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px}}
img{{width:100%;border-radius:8px;background:repeating-conic-gradient(#ddd 0 25%,#fff 0 50%) 0 0/20px 20px}}
footer{{font-size:13px;color:#555;margin:24px 0}}button{{background:#111;color:#fff;border:0;border-radius:8px;cursor:pointer}}</style>
<h1>My POD Studio</h1>{body}
<footer>Powered by Ideogram · Designs are made with AI · <a href="https://ideogram.ai/legal/usage-policy">Usage policy</a> · <a href="/privacy">Privacy policy</a></footer>"""


def design_prompt(idea, slogan, tee):
    return (f"T-shirt print, bold flat vector illustration. {idea} "
            f"Headline text, large and easy to read: \"{slogan}\". "
            f"Thick outlines, 3 to 5 flat colors, high contrast for a {tee} t-shirt. "
            f"Transparent background, isolated artwork.")


def show(job, files):
    cards = "".join(
        f"""<div class="card"><img src="/f/{job}/{f}"><form method="post" action="/pick">
<input type="hidden" name="job" value="{job}"><input type="hidden" name="file" value="{f}">
<input type="text" name="fix" placeholder="Wrong letter? Write the correct slogan">
<button name="do" value="mockup">Mockup + print file</button> <button name="do" value="fix">Fix the text</button></form></div>"""
        for f in files)
    return PAGE.format(body=f'<div class="grid">{cards}</div><p><a href="/">New idea</a></p>')


@app.get("/")
def home():
    return PAGE.format(body="""<form method="post" action="/design">
<label>Your idea</label><input type="text" name="idea" required placeholder="A camel carrying a tiny graphics card like treasure">
<label>Slogan on the shirt</label><input type="text" name="slogan" required placeholder="GPU POOR, IDEA RICH">
<label>T-shirt color</label> <select name="tee"><option>black</option><option>white</option></select>
<button>Design it (4 versions)</button></form>
<p><a href="/quiz">Take the 5-question quiz</a> · <a href="/swipe">Tinder for t-shirts (like / dislike)</a></p>""")


@app.post("/design")
def design():
    f = request.form
    job = uuid.uuid4().hex[:8]
    folder = os.path.join(JOBS, job)
    os.makedirs(folder)
    open(os.path.join(folder, "tee.txt"), "w").write(f["tee"])
    items, _ = run("/v2/image/generate/ideogram-4-5",
                   {"prompt": design_prompt(f["idea"], f["slogan"], f["tee"]), "background": "transparent",
                    "quality": "high", "num_images": "4", "async": "true"})
    files = []
    for i, it in enumerate(items):
        if it.get("url"):                      # empty url = blocked by the safety check
            files.append(os.path.basename(download(it["url"], os.path.join(folder, f"design_{i + 1}.png"))))
    return show(job, files)


@app.post("/pick")
def pick():
    f = request.form
    job, name = f["job"], os.path.basename(f["file"])
    folder = os.path.join(JOBS, job)
    src = os.path.join(folder, name)
    tee = open(os.path.join(folder, "tee.txt")).read()
    if f["do"] == "fix":
        with open(src, "rb") as img:
            items, _ = run("/v2/image/precise-edit/ideogram-4-5",
                           {"prompt": f"Change the headline text to exactly \"{f['fix']}\". Same font, colors and layout. "
                                      f"Keep everything else exactly the same.", "async": "true"},
                           files={"image": ("design.png", img, "image/png")})
        fixed = download(items[0]["url"], os.path.join(folder, "fixed_" + name))
        return show(job, [os.path.basename(fixed)])
    with open(src, "rb") as img:
        items, _ = run("/v2/image/generate/ideogram-4-5",
                       {"prompt": f"Use the uploaded artwork as the print on the front of a {tee} cotton t-shirt, "
                                  f"worn by a young developer, natural light, lifestyle product photo. "
                                  f"Keep the artwork's wording, colors and proportions exactly the same.",
                        "quality": "medium", "size": "1536x2048", "async": "true"},
                       files={"images": ("design.png", img, "image/png")})
    mock = download(items[0]["url"], os.path.join(folder, "mockup.png"))
    for factor in ("x2", "2x"):                 # clients differ on the spelling
        try:
            with open(src, "rb") as img:
                items, _ = run("/v2/image/upscale/auto", {"upscale_factor": factor, "async": "true"}, files={"image": img})
            break
        except RuntimeError as e:
            if "400" not in str(e) or factor == "2x":
                raise
    big = download(items[0]["url"], os.path.join(folder, "print_x2.png"))
    body = (f'<div class="grid"><div class="card"><img src="/f/{job}/{os.path.basename(mock)}">Mockup</div>'
            f'<div class="card"><img src="/f/{job}/{os.path.basename(big)}">'
            f'<a href="/f/{job}/{os.path.basename(big)}" download>Download the print file</a></div></div>'
            f'<p>Check every letter before you print. <a href="/">New idea</a></p>')
    return PAGE.format(body=body)


# ---------------------------------------------------------------------------
# Pages for the two ideas below (HTML + JS in the web/ folder)
# ---------------------------------------------------------------------------
WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
SHELL = """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/web/app.css"></head><body>
<header class="top"><div class="logo">🫖 <b>Code &amp; Atay</b> <span>Tees</span></div>
<nav><a href="/quiz" class="{q}">اختبار الشخصية</a><a href="/swipe" class="{s}">تيندر التيشيرتات</a></nav></header>
<main id="app"></main>
<footer>Powered by Ideogram · التصاميم مولّدة بالذكاء الاصطناعي ·
<a href="https://ideogram.ai/legal/usage-policy">سياسة الاستخدام</a> · <a href="/privacy">سياسة الخصوصية</a></footer>
<script src="/web/tee.js"></script><script src="/web/{js}"></script></body></html>"""


@app.get("/web/<name>")
def web(name):
    return send_from_directory(WEB, os.path.basename(name))


@app.get("/privacy")
def privacy():
    return PAGE.format(body="<p>Write your privacy policy here: what you store (answers, likes), for how long, "
                            "and that designs are generated by Ideogram's API.</p>")


def new_job():
    job = uuid.uuid4().hex[:8]
    os.makedirs(os.path.join(JOBS, job))
    return job, os.path.join(JOBS, job)


# ---------------------------------------------------------------------------
# Idea 1: a t-shirt that fits your personality (5-question quiz -> prompt -> design)
# ---------------------------------------------------------------------------
QUIZ = {
    "drink": {"atay": "a Moroccan teapot pouring mint tea into a small glass",
              "coffee": "a steaming cup of coffee"},
    "lang": {"python": "floating code brackets and a tiny snake-shaped cable",
             "javascript": "floating curly braces and semicolons"},
    "time": {"night": ("a programmer owl sitting on a crescent moon, typing on a glowing mint laptop", "NIGHT MODE: ON"),
             "morning": ("a programmer falcon at sunrise, typing on a glowing laptop", "EARLY COMMIT")},
    "movies": {"scifi": "wearing a small astronaut helmet, with a rocket in the sky",
               "fantasy": "wearing a tiny wizard hat, with magic sparkles",
               "action": "wearing aviator goggles, with speed lines",
               "comedy": "with a big cheeky grin"},
    "style": {"retro": "Vintage retro badge illustration, thick outlines, warm muted colors: sand, brass gold, mint, cream",
              "minimal": "Minimal flat line art, only 2 flat colors"},
}


def quiz_prompt(a):
    scene, headline = QUIZ["time"][a["time"]]
    return (f"T-shirt print. {scene}, {QUIZ['movies'][a['movies']]}. Next to it: {QUIZ['drink'][a['drink']]}. "
            f"Around it: {QUIZ['lang'][a['lang']]}. Headline text above, large and easy to read: \"{headline}\". "
            f"{QUIZ['style'][a['style']]}. High contrast for a black t-shirt. Transparent background, isolated artwork.")


@app.get("/quiz")
def quiz_page():
    return SHELL.format(title="تيشيرت على مقاس شخصيتك", q="on", s="", js="quiz.js")


@app.post("/api/quiz/prompt")
def quiz_prompt_only():
    sent = (request.get_json(silent=True) or {}).get("answers", {})
    answers = {k: sent.get(k) for k in QUIZ if sent.get(k) in QUIZ[k]}
    if len(answers) != len(QUIZ):
        return jsonify(error="Please answer all 5 questions."), 400
    return jsonify(prompt=quiz_prompt(answers))


@app.post("/api/quiz")
def quiz_design():
    sent = (request.get_json(silent=True) or {}).get("answers", {})
    answers = {k: sent.get(k) for k in QUIZ if sent.get(k) in QUIZ[k]}
    if len(answers) != len(QUIZ):
        return jsonify(error="Please answer all 5 questions."), 400
    job, folder = new_job()
    prompt = quiz_prompt(answers)
    open(os.path.join(folder, "prompt.txt"), "w").write(prompt)
    items, _ = run("/v2/image/generate/ideogram-4-5",
                   {"prompt": prompt, "background": "transparent", "quality": "high", "num_images": "2", "async": "true"})
    urls = [f"/f/{job}/" + os.path.basename(download(it["url"], os.path.join(folder, f"design_{i + 1}.png")))
            for i, it in enumerate(items) if it.get("url")]
    return jsonify(job=job, prompt=prompt, images=urls)


# ---------------------------------------------------------------------------
# Idea 2: "Tinder for t-shirts" — like = use it as a reference, dislike = move away from that style
# ---------------------------------------------------------------------------
STYLES = [("vintage retro badge, thick outlines, warm muted colors", "Retro كلاسيكي", "vintage retro"),
          ("minimal flat line art, 2 colors", "Minimal بسيط", "minimal line art"),
          ("bold pop-art comic style, halftone dots", "Pop-art كوميكس", "pop-art comic"),
          ("Japanese ukiyo-e woodblock style", "ياباني Ukiyo-e", "ukiyo-e"),
          ("neon synthwave style, glowing lines", "نيون Synthwave", "neon synthwave"),
          ("hand-drawn ink sketch, one color", "رسم حبر يدوي", "ink sketch")]
SUBJECTS = ["a camel carrying a tiny graphics card, headline \"GPU POOR, IDEA RICH\"",
            "a falcon wearing headphones, headline \"DEEP FOCUS\"",
            "a robot drinking mint tea, headline \"HUMAN IN THE LOOP\"",
            "a cat sleeping on a keyboard, headline \"IT WORKS ON MY MACHINE\"",
            "a rubber duck with sunglasses, headline \"DEBUG MODE\""]


def swipe_state(folder):
    path = os.path.join(folder, "state.txt")
    if not os.path.exists(path):
        return {"n": 0, "style": 0, "disliked": [], "liked": []}
    n, style, disliked, liked = open(path).read().split("\n")[:4]
    return {"n": int(n), "style": int(style), "disliked": [int(x) for x in disliked.split(",") if x],
            "liked": [x for x in liked.split(",") if x]}


def save_state(folder, s):
    open(os.path.join(folder, "state.txt"), "w").write(
        f"{s['n']}\n{s['style']}\n{','.join(map(str, s['disliked']))}\n{','.join(s['liked'])}")


def next_design(folder, s, reference=None):
    s["n"] += 1
    subject = SUBJECTS[s["n"] % len(SUBJECTS)]
    if reference:      # liked: keep the look, change the subject
        prompt = (f"A new t-shirt print in exactly the same art style, colors and mood as the uploaded design. "
                  f"New subject: {subject}. Transparent background, isolated artwork.")
        with open(os.path.join(folder, reference), "rb") as img:
            items, _ = run("/v2/image/generate/ideogram-4-5",
                           {"prompt": prompt, "background": "transparent", "quality": "medium",
                            "num_images": "1", "async": "true"},
                           files={"images": ("liked.png", img, "image/png")})
    else:              # first card or disliked: try a style this customer hasn't rejected
        options = [i for i in range(len(STYLES)) if i not in s["disliked"]] or list(range(len(STYLES)))
        s["style"] = options[s["n"] % len(options)]
        prompt = (f"T-shirt print, {STYLES[s['style']][0]}. {subject}. Headline large and easy to read. "
                  f"High contrast for a black t-shirt. Transparent background, isolated artwork.")
        items, _ = run("/v2/image/generate/ideogram-4-5",
                       {"prompt": prompt, "background": "transparent", "quality": "medium",
                        "num_images": "1", "async": "true"})
    name = f"swipe_{s['n']}.png"
    download(items[0]["url"], os.path.join(folder, name))
    save_state(folder, s)
    return name


def swipe_json(job, name, s):
    _, ar, en = STYLES[s["style"]]
    return jsonify(job=job, file=name, url=f"/f/{job}/{name}", style=ar, style_en=en, liked=s["liked"])


@app.get("/swipe")
def swipe_page():
    return SHELL.format(title="تيندر للتيشيرتات", q="", s="on", js="swipe.js")


@app.post("/api/swipe/start")
def swipe_start():
    job, folder = new_job()
    s = swipe_state(folder)
    return swipe_json(job, next_design(folder, s), s)


@app.post("/api/swipe")
def swipe():
    f = request.get_json(silent=True) or {}
    job, name = os.path.basename(f.get("job", "")), os.path.basename(f.get("file", ""))
    folder = os.path.join(JOBS, job)
    if not job or not os.path.exists(os.path.join(folder, name)):
        return jsonify(error="unknown design"), 400
    s = swipe_state(folder)
    if f.get("do") == "like":
        s["liked"].append(name)
        new = next_design(folder, s, reference=name)
    else:
        s["disliked"].append(s["style"])
        new = next_design(folder, s)
    return swipe_json(job, new, s)


@app.get("/f/<job>/<name>")
def files(job, name):
    return send_from_directory(os.path.join(JOBS, os.path.basename(job)), os.path.basename(name))


if __name__ == "__main__":
    if not KEY:
        raise SystemExit("Set IDEOGRAM_API_KEY first (ideogram.ai/platform -> API Keys).")
    app.run(debug=False)
