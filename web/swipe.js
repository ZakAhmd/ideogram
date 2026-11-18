// "Tinder for t-shirts": like = the next design uses this one as a visual reference,
// dislike = the next design moves to a style this customer has not rejected yet.
const app = document.getElementById("app");
let job = null, file = null, busy = false;
const liked = [], log = [];

app.innerHTML = `<div class="fade">
  <h1 class="center">تيندر للتيشيرتات<span class="en">Tinder for t-shirts</span></h1>
  <p class="sub center">يمين = أعجبني · يسار = ليس لي</p>
  <div class="cols">
    <div class="side"><h3>ذاكرة الذوق · taste memory</h3><div class="log" id="log"></div></div>
    <div><div class="deck" id="deck"></div>
      <div class="actions"><button class="round yes" id="yes">♥</button><button class="round no" id="no">✕</button></div></div>
    <div class="side"><h3>أعجبك · liked</h3><div class="liked" id="liked"></div></div>
  </div></div>`;
const deck = document.getElementById("deck");

function loadingCard(text) {
  deck.innerHTML = `<div class="card"><div class="loading"><div class="spin"></div>${text}</div></div>`;
}
function showCard(src, style) {
  deck.innerHTML = `<div class="card fade" id="cur"><span class="stamp like">LIKE</span><span class="stamp nope">NOPE</span>
    ${teeHTML(src)}<div class="chip" style="margin-top:14px">🎨 ${style}</div></div>`;
}
function renderSide() {
  document.getElementById("log").innerHTML = log.slice(-8).map(l => l).join("<br>");
  document.getElementById("liked").innerHTML = liked.map(s => `<img src="${s}">`).join("");
}
async function start() {
  loadingCard("نجهّز أول تصميم..<span class='en'>first design</span>");
  const r = await post("/api/swipe/start");
  job = r.job; file = r.file;
  log.push(`style → <b>${r.style_en}</b>`);
  renderSide(); showCard(r.url, r.style);
}
async function swipe(doLike) {
  if (busy || !file) return;
  busy = true;
  const cur = document.getElementById("cur");
  if (cur) cur.classList.add(doLike ? "out-r" : "out-l");
  const src = cur ? cur.querySelector("img").getAttribute("src") : null;
  if (doLike) { liked.push(src); log.push(`♥ like → <b>reference</b>`); }
  else log.push(`<span class="no">✕ nope</span> → move away`);
  renderSide();
  await new Promise(r => setTimeout(r, 550));
  loadingCard(doLike ? "نولّد تصميماً بنفس الأسلوب..<span class='en'>same style, new idea</span>"
                     : "نجرب أسلوباً آخر..<span class='en'>trying another style</span>");
  try {
    const r = await post("/api/swipe", {job, file, do: doLike ? "like" : "dislike"});
    file = r.file;
    log.push(`style → <b>${r.style_en}</b>`);
    renderSide(); showCard(r.url, r.style);
  } finally { busy = false; }
}
document.getElementById("yes").onclick = () => swipe(true);
document.getElementById("no").onclick = () => swipe(false);
document.addEventListener("keydown", e => {
  if (e.key === "ArrowRight") swipe(true);
  if (e.key === "ArrowLeft") swipe(false);
});
start();
