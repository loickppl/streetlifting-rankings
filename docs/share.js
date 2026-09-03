/* Share cards — 1080×1920 story images drawn on a canvas, handed to the
   phone's native share sheet (Web Share API → Instagram Stories, etc.) or
   downloaded when file sharing isn't available. Relies on app.js globals. */

const SITE_URL = "loickppl.github.io/streetlifting-rankings";
const CW = 1080, CH = 1920;
const PAL = { bg: "#ffffff", surface: "#f7f7f5", ink: "#171717", ink2: "#686868", ink3: "#929292", border: "#e6e6e3", accent: "#c8102e" };
const cfont = (weight, size) => `${weight} ${size}px Archivo, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`;

async function ensureCanvasFonts() {
  if (!document.fonts) return;
  try { await Promise.all([900, 800, 700, 600, 500].map(w => document.fonts.load(cfont(w, 20)))); } catch {}
}

const _flagImgs = {};
function loadFlag(iso) {
  if (!iso || iso.length !== 2) return Promise.resolve(null);
  const cc = iso.toLowerCase();
  return _flagImgs[cc] ??= new Promise(res => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => res(img);
    img.onerror = () => res(null);
    img.src = `https://flagcdn.com/w80/${cc}.png`;
  });
}

/* ── drawing helpers ─────────────────────────────────────────── */
function setFont(ctx, weight, size, color, spacing = 0) {
  ctx.font = cfont(weight, size);
  ctx.fillStyle = color;
  try { ctx.letterSpacing = `${spacing}px`; } catch {}
}
function truncate(ctx, text, max) {
  let s = String(text ?? "");
  if (ctx.measureText(s).width <= max) return s;
  while (s.length > 1 && ctx.measureText(s + "…").width > max) s = s.slice(0, -1);
  return s.trimEnd() + "…";
}
function fitSize(ctx, text, max, weight, size, min, spacingEm = 0) {
  for (let sz = size; sz >= min; sz -= 4) {
    setFont(ctx, weight, sz, PAL.ink, sz * spacingEm);
    if (ctx.measureText(text).width <= max) return sz;
  }
  return min;
}
function hairline(ctx, x1, x2, y, color = PAL.border) {
  ctx.fillStyle = color;
  ctx.fillRect(x1, Math.round(y), x2 - x1, 2);
}
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}
function drawFlag(ctx, img, iso, x, y, w, h) {
  ctx.save();
  roundRect(ctx, x, y, w, h, 4); ctx.clip();
  if (img) ctx.drawImage(img, x, y, w, h);
  else {
    ctx.fillStyle = PAL.surface; ctx.fillRect(x, y, w, h);
    setFont(ctx, 700, Math.round(h * .42), PAL.ink2);
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText((iso || "").toUpperCase(), x + w / 2, y + h / 2 + 1);
  }
  ctx.restore();
  ctx.strokeStyle = "rgba(23,23,23,.12)"; ctx.lineWidth = 2;
  roundRect(ctx, x, y, w, h, 4); ctx.stroke();
}
// value right-aligned at `right`, unit trailing in a smaller weight
function drawValue(ctx, value, unit, right, y, size, color) {
  ctx.textAlign = "right"; ctx.textBaseline = "alphabetic";
  let ux = right;
  if (unit) {
    setFont(ctx, 600, Math.round(size * .46), PAL.ink2);
    ctx.fillText(unit, right, y);
    ux = right - ctx.measureText(unit).width - Math.round(size * .14);
  }
  setFont(ctx, 900, size, color, -size * .02);
  ctx.fillText(value, ux, y);
  return ux - ctx.measureText(value).width;
}

/* ── frame: brand header, kicker/title, footer ───────────────── */
function drawFrame(ctx, { kicker, title, sub }) {
  ctx.fillStyle = PAL.bg; ctx.fillRect(0, 0, CW, CH);
  ctx.textBaseline = "alphabetic"; ctx.textAlign = "left";

  // brand mark
  ctx.fillStyle = PAL.ink; roundRect(ctx, 80, 92, 78, 78, 8); ctx.fill();
  setFont(ctx, 900, 36, "#fff", 1); ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText("SL", 119, 133);
  ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
  setFont(ctx, 900, 30, PAL.ink, .3);
  ctx.fillText("STREET", 178, 124); ctx.fillText("LIFTING", 178, 156);
  setFont(ctx, 600, 14, PAL.ink3, 5.5);
  ctx.fillText("RANKINGS", 178, 182);
  hairline(ctx, 80, CW - 80, 232);

  // kicker + title + sub
  setFont(ctx, 700, 24, PAL.accent, 4.5);
  ctx.fillText(truncate(ctx, kicker.toUpperCase(), CW - 160), 80, 318);
  const T = title.toUpperCase();
  const sz = fitSize(ctx, T, CW - 160, 900, 150, 72, -.03);
  setFont(ctx, 900, sz, PAL.ink, -sz * .03);
  ctx.fillText(truncate(ctx, T, CW - 160), 76, 318 + sz + 14);
  const subY = 318 + sz + 14 + 58;
  if (sub) {
    setFont(ctx, 500, 30, PAL.ink2);
    ctx.fillText(truncate(ctx, sub, CW - 160), 80, subY);
  }
  // barbell divider
  const dy = subY + 46;
  ctx.fillStyle = PAL.ink;
  ctx.fillRect(80, dy, 180, 3); ctx.fillRect(98, dy - 6, 5, 15); ctx.fillRect(237, dy - 6, 5, 15);

  // footer
  hairline(ctx, 80, CW - 80, 1782);
  setFont(ctx, 700, 26, PAL.ink); ctx.textAlign = "left";
  ctx.fillText(SITE_URL, 80, 1832);
  setFont(ctx, 500, 22, PAL.ink3); ctx.textAlign = "right";
  ctx.fillText(`${t().updated} ${fmtDate(state.meta?.generated_at?.slice(0, 10))}`, CW - 80, 1832);
  setFont(ctx, 500, 21, PAL.ink3); ctx.textAlign = "left";
  ctx.fillText(t().hero_kicker, 80, 1872);
  return dy + 60; // content top
}

function genderLabel(g) { return g === "male" ? t().men : t().women; }
function classTitle(c) {
  if (!c || c === "all") return t().all_classes;
  return c.replace(/kg$/i, " kg");
}
function countryNames(list) { return (list || []).map(countryLabel).join(" · "); }

/* ── cards ───────────────────────────────────────────────────── */
async function drawRankingCard(ctx) {
  const { gender, metric, klass } = state;
  const country = $("#f-country").value;
  const period = $("#f-period").value;
  const q = $("#f-search").value.trim();
  const rows = rankingRows().filter(r => !r._dq).slice(0, 10);
  const unit = metric === "ris" ? "" : "kg";

  let periodTxt = t().p_all;
  if (period === "custom") {
    const [from, to] = dateRange();
    periodTxt = `${from ? `${t().share_since} ${fmtDate(from)}` : ""} ${to ? `${t().share_until} ${fmtDate(to)}` : ""}`.trim() || t().p_all;
  } else if (period) periodTxt = t().share_period[period] || periodTxt;

  const kicker = `${country ? `${t().share_national_ranking} · ${countryLabel(country)}` : t().share_world_ranking} · ${genderLabel(gender)}`;
  const sub = [classTitle(klass), periodTxt, `${t().share_top} ${rows.length}`, q ? `“${q}”` : ""].filter(Boolean).join(" · ");
  const top = drawFrame(ctx, { kicker, title: t().metric_names[metric], sub });

  const flags = await Promise.all(rows.map(r => loadFlag((r.countries || [r.country])[0])));
  const bottom = 1760, rh = Math.min(116, Math.floor((bottom - top) / Math.max(rows.length, 1)));
  if (!rows.length) {
    setFont(ctx, 600, 34, PAL.ink3); ctx.textAlign = "center";
    ctx.fillText(t().no_data, CW / 2, top + 120); ctx.textAlign = "left";
    return;
  }
  rows.forEach((r, i) => {
    const y0 = top + i * rh;
    hairline(ctx, 80, CW - 80, y0 + rh - 2);
    ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
    setFont(ctx, 800, 38, i === 0 ? PAL.ink : PAL.ink3, -1);
    ctx.fillText(String(i + 1), 80, y0 + 66);
    drawFlag(ctx, flags[i], (r.countries || [r.country])[0], 158, y0 + 34, 52, 39);
    const pre = (metric === "ris" && r.ris_est) ? "~" : "";
    const left = drawValue(ctx, pre + fmt(r[metric]), unit, CW - 80, y0 + 70, 50, i === 0 ? PAL.accent : PAL.ink);
    const nameMax = left - 236 - 36;
    ctx.textAlign = "left";
    setFont(ctx, 700, 38, PAL.ink, -.5);
    ctx.fillText(truncate(ctx, r.athlete, nameMax), 236, y0 + 58);
    setFont(ctx, 500, 23, PAL.ink3);
    const meta = [!klass && r.class ? `${r.class_inferred ? "~\u2009" : ""}${r.class}` : "", r.competition, fmtDate(r.date)].filter(Boolean).join(" · ");
    ctx.fillText(truncate(ctx, meta, CW - 80 - 236), 236, y0 + 94);
  });
}

async function drawRecordsCard(ctx, klass) {
  const gender = state.rGender;
  const country = $("#r-country").value;
  const order = ["total", "ris", "muscle_up", "pull_up", "dip", "squat"];
  let off = {}, best = {};
  if (country) {
    nationalRecords(gender, country).filter(r => r.class === klass).forEach(r => off[r.movement] = r);
  } else {
    (state.records.official || []).forEach(r => { if (r.gender === gender && r.class === klass) off[r.movement] = r; });
    (state.records.best || []).forEach(r => { if (r.gender === gender && r.class === klass) best[r.movement] = r; });
  }
  const kicker = `${country ? `${t().share_national_records} · ${countryLabel(country)}` : t().share_wr} · ${genderLabel(gender)}`;
  const top = drawFrame(ctx, { kicker, title: classTitle(klass), sub: order.map(m => t().metric_names[m]).join(" · ") });

  const items = order.map(m => ({ m, o: off[m], b: best[m] })).filter(x => x.o || x.b);
  const flags = await Promise.all(items.map(x => loadFlag((x.o || x.b).country)));
  const bottom = 1760, rh = Math.min(190, Math.floor((bottom - top) / Math.max(items.length, 1)));
  items.forEach(({ m, o, b }, i) => {
    const y0 = top + i * rh;
    hairline(ctx, 80, CW - 80, y0 + rh - 2);
    const main = o || b;
    const unit = m === "ris" ? "" : "kg";
    ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
    setFont(ctx, 700, 22, PAL.accent, 4);
    ctx.fillText(`${t().metric_names[m].toUpperCase()}${!o && b ? ` · ${t().rec_best.toUpperCase()}` : ""}`, 80, y0 + 40);
    drawFlag(ctx, flags[i], main.country, 80, y0 + 66, 52, 39);
    const pre = main.class_inferred || main.estimated ? "~" : "";
    const left = drawValue(ctx, pre + fmt(main.value), unit, CW - 80, y0 + 108, 58, PAL.ink);
    ctx.textAlign = "left";
    setFont(ctx, 800, 42, PAL.ink, -.8);
    ctx.fillText(truncate(ctx, main.athlete, left - 152 - 36), 152, y0 + 104);
    if (o && b && b.value > o.value) {
      setFont(ctx, 600, 24, PAL.ink2);
      const line = `${t().rec_best} · ${b.athlete} · ${b.class_inferred || b.estimated ? "~" : ""}${fmt(b.value)}${unit ? " " + unit : ""}`;
      ctx.fillText(truncate(ctx, line, CW - 160), 80, y0 + 152);
    }
  });
}

async function drawAthleteCard(ctx, id) {
  const a = state.athletes.find(x => x.id === id);
  if (!a) throw new Error("athlete");
  const perfs = state.performances.filter(p => p.athlete_id === id)
    .slice().sort((x, y) => (y.date || "").localeCompare(x.date || ""));
  const countries = a.countries && a.countries.length ? a.countries : (a.country ? [a.country] : []);
  const kicker = [t().share_athlete, genderLabel(a.gender), countryNames(countries)].filter(Boolean).join(" · ");
  const sub = `${a.n_competitions} ${compWord(a.n_competitions)}${a.instagram ? ` · ${a.instagram}` : ""}`;
  const top = drawFrame(ctx, { kicker, title: a.name, sub });

  // personal records — 2 × 3 grid
  const mn = t().metric_names;
  const cells = [
    [mn.muscle_up, fmt(a.best?.muscle_up), "kg"], [mn.pull_up, fmt(a.best?.pull_up), "kg"],
    [mn.dip, fmt(a.best?.dip), "kg"], [mn.squat, fmt(a.best?.squat), "kg"],
    [mn.total, fmt(a.best?.total), "kg"], ["RIS", `${a.best_ris_est ? "~" : ""}${fmt(a.best_ris)}`, ""],
  ];
  setFont(ctx, 700, 22, PAL.accent, 4); ctx.textAlign = "left";
  ctx.fillText(t().share_pr.toUpperCase(), 80, top + 26);
  const gx = 80, gy = top + 56, cw = (CW - 160) / 2, chh = 150;
  cells.forEach(([label, value, unit], i) => {
    const x = gx + (i % 2) * cw, y = gy + Math.floor(i / 2) * chh;
    hairline(ctx, x + (i % 2 ? 20 : 0), x + cw - (i % 2 ? 0 : 20), y + chh - 2);
    ctx.textAlign = "left";
    setFont(ctx, 600, 22, PAL.ink3, 2.5);
    ctx.fillText(label.toUpperCase(), x + (i % 2 ? 20 : 0), y + 40);
    setFont(ctx, 900, 64, PAL.ink, -1.5);
    const vx = x + (i % 2 ? 20 : 0);
    ctx.fillText(value, vx, y + 112);
    if (unit && value !== "—") {
      const w = ctx.measureText(value).width;
      setFont(ctx, 600, 26, PAL.ink2);
      ctx.fillText(unit, vx + w + 8, y + 112);
    }
  });

  // latest competitions
  const ly = gy + 3 * chh + 60;
  setFont(ctx, 700, 22, PAL.accent, 4);
  ctx.fillText(t().share_last_comps.toUpperCase(), 80, ly);
  const list = perfs.slice(0, 5), rh = 96;
  list.forEach((p, i) => {
    const y0 = ly + 24 + i * rh;
    if (y0 + rh > 1770) return;
    hairline(ctx, 80, CW - 80, y0 + rh - 2);
    ctx.textAlign = "left";
    setFont(ctx, 800, 26, p.disqualified ? PAL.accent : PAL.ink3, -.5);
    const tag = p.disqualified ? "DQ" : p.place ? `#${p.place}` : "";
    ctx.fillText(tag, 80, y0 + 44);
    const left = p.total != null ? drawValue(ctx, fmt(p.total), "kg", CW - 80, y0 + 50, 40, PAL.ink) : CW - 80;
    ctx.textAlign = "left";
    setFont(ctx, 700, 30, PAL.ink, -.4);
    ctx.fillText(truncate(ctx, p.competition || "—", left - 160 - 30), 160, y0 + 40);
    setFont(ctx, 500, 22, PAL.ink3);
    const meta = [fmtDate(p.date), p.class ? `${p.class_inferred ? "~\u2009" : ""}${p.class}` : "", p.ris != null ? `RIS ${p.ris_est ? "~" : ""}${fmt(p.ris)}` : ""].filter(Boolean).join(" · ");
    ctx.fillText(truncate(ctx, meta, left - 160 - 30), 160, y0 + 74);
  });
}

/* ── share modal ─────────────────────────────────────────────── */
let shareFile = null, shareLink = "", shareCanNative = false, shareLockedBody = false;

function shareBaseUrl() { return `${location.origin}${location.pathname}`; }

async function openShare(kind, opts = {}) {
  const modal = $("#share-modal"), preview = $("#share-preview");
  preview.innerHTML = `<span class="share-loading">${t().share_preparing}</span>`;
  $("#share-do").disabled = true;
  $("#share-copy").querySelector("span").textContent = t().share_copy;
  $("#share-hint").textContent = "";
  modal.classList.remove("hidden");
  if (!document.body.classList.contains("modal-open")) { lockBody(); shareLockedBody = true; }

  try {
    await ensureCanvasFonts();
    const canvas = document.createElement("canvas");
    canvas.width = CW; canvas.height = CH;
    const ctx = canvas.getContext("2d");
    let slug = kind;
    if (kind === "rankings") { await drawRankingCard(ctx); shareLink = location.href; slug = `${state.metric}-${state.gender}${state.klass ? "-" + state.klass : ""}`; }
    else if (kind === "records") { await drawRecordsCard(ctx, opts.klass); shareLink = location.href; slug = `records-${state.rGender}-${opts.klass}`; }
    else if (kind === "athlete") { await drawAthleteCard(ctx, opts.id); shareLink = `${shareBaseUrl()}#a=${encodeURIComponent(opts.id)}`; slug = opts.id; }

    preview.innerHTML = `<img alt="" src="${canvas.toDataURL("image/png")}">`;
    const blob = await new Promise(r => canvas.toBlob(r, "image/png"));
    shareFile = new File([blob], `streetlifting-${slug}.png`.replace(/[^a-z0-9.\-_]/gi, "-"), { type: "image/png" });
    shareCanNative = !!(navigator.share && navigator.canShare && navigator.canShare({ files: [shareFile] }));
    $("#share-do").querySelector("span").textContent = shareCanNative ? t().share_do : t().share_download;
    $("#share-hint").textContent = shareCanNative ? t().share_hint_native : t().share_hint_fallback;
    $("#share-do").disabled = false;
  } catch (err) {
    preview.innerHTML = `<span class="share-loading">${esc(err.message || String(err))}</span>`;
  }
}

function closeShare() {
  $("#share-modal").classList.add("hidden");
  if (shareLockedBody) { unlockBody(); shareLockedBody = false; }
}

async function doShare() {
  if (!shareFile) return;
  if (shareCanNative) {
    try { await navigator.share({ files: [shareFile], title: "Streetlifting Rankings" }); }
    catch (err) { if (err && err.name !== "AbortError") downloadShare(); }
  } else downloadShare();
}
function downloadShare() {
  const url = URL.createObjectURL(shareFile);
  const a = document.createElement("a");
  a.href = url; a.download = shareFile.name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
async function copyShareLink() {
  const label = $("#share-copy").querySelector("span");
  try { await navigator.clipboard.writeText(shareLink); }
  catch { window.prompt("URL", shareLink); return; }
  label.textContent = t().share_copied;
  setTimeout(() => { label.textContent = t().share_copy; }, 1600);
}

document.body.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-share]");
  if (!btn) return;
  e.preventDefault(); e.stopPropagation();
  const kind = btn.dataset.share;
  openShare(kind, { klass: btn.dataset.class, id: btn.dataset.id });
});
$("#share-modal").addEventListener("click", (e) => {
  if (e.target === $("#share-modal") || e.target.closest("#share-close")) closeShare();
});
$("#share-do").addEventListener("click", doShare);
$("#share-copy").addEventListener("click", copyShareLink);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !$("#share-modal").classList.contains("hidden")) closeShare();
});
