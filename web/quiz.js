// 5 questions -> Python builds a prompt -> Ideogram API -> a design for this customer only.
const QUESTIONS = [
  {key: "drink", ar: "أتاي أم قهوة؟", en: "Atay or coffee?", opts: [
    {v: "atay", e: "🫖", ar: "أتاي", en: "Mint tea"}, {v: "coffee", e: "☕", ar: "قهوة", en: "Coffee"}]},
  {key: "lang", ar: "تكتب Python أم JavaScript؟", en: "Python or JavaScript?", opts: [
    {v: "python", e: "🐍", ar: "Python", en: "Python"}, {v: "javascript", e: "⚡", ar: "JavaScript", en: "JavaScript"}]},
  {key: "time", ar: "كائن ليلي أم صباحي؟", en: "Night owl or early bird?", opts: [
    {v: "night", e: "🌙", ar: "ليلي", en: "Night owl"}, {v: "morning", e: "☀️", ar: "صباحي", en: "Early bird"}]},
  {key: "movies", ar: "ما نوع الأفلام التي تشدّك؟", en: "Your kind of movie?", opts: [
    {v: "scifi", e: "🚀", ar: "خيال علمي", en: "Sci-fi"}, {v: "fantasy", e: "🧙", ar: "فانتازيا", en: "Fantasy"},
    {v: "action", e: "💥", ar: "أكشن", en: "Action"}, {v: "comedy", e: "😂", ar: "كوميديا", en: "Comedy"}]},
  {key: "style", ar: "Retro كلاسيكي أم Minimal بسيط؟", en: "Retro or minimal?", opts: [
    {v: "retro", e: "📼", ar: "Retro", en: "Vintage badge"}, {v: "minimal", e: "◻️", ar: "Minimal", en: "Clean line art"}]},
];
const app = document.getElementById("app");
const answers = {};
let step = 0;

function progress() {
  return `<div class="progress">${QUESTIONS.map((_, i) => `<i class="${i < step || (i === step && answers[QUESTIONS[i].key]) ? "on" : ""}"></i>`).join("")}</div>`;
}
function ask() {
  const q = QUESTIONS[step];
  app.innerHTML = `<div class="fade">
    <h1>تيشيرت على مقاس شخصيتك<span class="en">A t-shirt designed for your personality</span></h1>
    <p class="sub">خمسة أسئلة سريعة.. والتصميم يُصنع لك وحدك.</p>${progress()}
    <div class="step-n">${step + 1} / ${QUESTIONS.length}</div>
    <div class="q">${q.ar}<span class="en">${q.en}</span></div>
    <div class="opts">${q.opts.map(o => `<button class="opt" data-v="${o.v}"><span class="e">${o.e}</span><b>${o.ar}</b><span class="en">${o.en}</span></button>`).join("")}</div></div>`;
  app.querySelectorAll(".opt").forEach(b => b.onclick = () => {
    answers[q.key] = b.dataset.v;
    b.classList.add("on");
    setTimeout(() => { step++; step < QUESTIONS.length ? ask() : summary(); }, 450);
  });
}
function label(q) { return q.opts.find(o => o.v === answers[q.key]); }
function summary() {
  app.innerHTML = `<div class="fade">
    <h1>جاهز؟<span class="en">Ready?</span></h1>${progress()}
    <div class="chips">${QUESTIONS.map(q => { const o = label(q); return `<span class="chip">${o.e} ${o.ar}</span>`; }).join("")}</div>
    <button class="btn" id="go">✨ صمّم تيشيرتي</button></div>`;
  document.getElementById("go").onclick = design;
}
async function design() {
  app.innerHTML = `<div class="fade">
    <h1>نصمّم قطعتك الآن..<span class="en">Designing your piece</span></h1>
    <div class="pipe"><div class="s on">٥ إجابات<span class="en">5 answers</span></div><span class="arr">←</span>
      <div class="s run" id="s2">كود Python<span class="en">builds the prompt</span></div><span class="arr">←</span>
      <div class="s" id="s3">Ideogram API<span class="en">generates</span></div><span class="arr">←</span>
      <div class="s" id="s4">تصميمك<span class="en">your design</span></div></div>
    <div class="code" id="code"><span class="k">prompt</span> = …</div></div>`;
  try {
    const code = document.getElementById("code");
    const {prompt} = await post("/api/quiz/prompt", {answers});
    await typeText(code, prompt);
    document.getElementById("s2").className = "s on";
    document.getElementById("s3").className = "s run";
    const res = await post("/api/quiz", {answers});
    document.getElementById("s3").className = "s on";
    document.getElementById("s4").className = "s on";
    setTimeout(() => result(res), 900);
  } catch (e) {
    app.innerHTML = `<p class="sub">حدث خطأ: ${e.message}</p><button class="btn ghost" onclick="location.reload()">حاول مجدداً</button>`;
  }
}
function typeText(el, text) {
  return new Promise(done => {
    let i = 0;
    el.innerHTML = '<span class="k">prompt</span> = "';
    const t = setInterval(() => {
      i += 4;
      el.innerHTML = '<span class="k">prompt</span> = "' + text.slice(0, i).replace(/</g, "&lt;") + (i >= text.length ? '"' : "▌");
      if (i >= text.length) { clearInterval(t); done(); }
    }, 18);
  });
}
function result(res) {
  const show = src => {
    document.getElementById("teeBox").innerHTML = teeHTML(src);
    document.querySelectorAll(".thumbs img").forEach(im => im.classList.toggle("on", im.getAttribute("src") === src));
  };
  app.innerHTML = `<div class="result fade">
    <div><div id="teeBox"></div><div class="thumbs">${res.images.map(s => `<img src="${s}">`).join("")}</div></div>
    <div><h1>هذا أنت.<span class="en">This is you.</span></h1>
      <div class="chips">${QUESTIONS.map(q => { const o = label(q); return `<span class="chip">${o.e} ${o.ar}</span>`; }).join("")}</div>
      <p class="sub">تصميم واحد.. لك وحدك. لن تجده في أي كتالوج.</p>
      <div class="price">تيشيرت قطن أسود · مطبوع عند الطلب</div>
      <button class="btn">🛒 أضف إلى السلة</button> <a class="btn ghost" href="/quiz">اختبار جديد</a></div></div>`;
  document.querySelectorAll(".thumbs img").forEach(im => im.onclick = () => show(im.getAttribute("src")));
  show(res.images[0]);
}
ask();
