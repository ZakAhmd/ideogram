// A plain t-shirt drawn in SVG, with the design image on the chest.
function teeHTML(src, color) {
  color = color || "#15171c";
  return `<div class="tee"><svg viewBox="0 0 400 440" aria-hidden="true">
  <path d="M128 18 L164 6 Q200 44 236 6 L272 18 L384 84 L344 168 L302 146 L302 428 L98 428 L98 146 L56 168 L16 84 Z"
        fill="${color}" stroke="#2c3344" stroke-width="2" stroke-linejoin="round"/>
  <path d="M164 6 Q200 44 236 6" fill="none" stroke="#2c3344" stroke-width="5"/>
  </svg>${src ? `<img src="${src}" alt="design">` : ""}</div>`;
}
async function post(url, body) {
  const r = await fetch(url, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body || {})});
  let j;
  try { j = await r.json(); } catch (e) { throw new Error("server error " + r.status); }
  if (!r.ok) throw new Error(j.error || r.status);
  return j;
}
