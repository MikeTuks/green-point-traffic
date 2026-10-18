const ROUTES = [["outbound", "Going out to the N1"], ["return", "Coming home"]];
const STEP = 15;
const BEFORE = 300;
const BAD = 2;

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const dayFmt = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "Africa/Johannesburg" });
const timeFmt = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Africa/Johannesburg" });

function dayLabel(iso, today) {
  return iso.slice(0, 10) === today ? "Today" : dayFmt.format(new Date(iso.slice(0, 10) + "T12:00:00+02:00"));
}

function addMinutes(hhmm, minutes) {
  const total = (+hhmm.slice(0, 2) * 60 + +hhmm.slice(3) + minutes + 1440) % 1440;
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

function minutesBetween(a, b) {
  let d = (+b.slice(0, 2) * 60 + +b.slice(3)) - (+a.slice(0, 2) * 60 + +a.slice(3));
  return d <= 0 ? d + 1440 : d;
}

function level(v) {
  return Math.min(1, 0.55 + (v - BAD) * 0.06).toFixed(2);
}

function verdict(out) {
  if (!out || !out.games) return ["unknown", "Not enough games logged yet"];
  if (!out.bad.length) return ["clear", "Clear all day"];
  return ["", out.bad.map(([a, b]) => `${a} to ${b}`).join("<br>")];
}

function strip(out, event) {
  const n = out && out.median ? out.median.length : (BEFORE + minutesBetween(event.start, event.end) + 180) / STEP;
  const values = out && out.median ? out.median : Array(n).fill(null);
  const from = out && out.from ? out.from : addMinutes(event.start, -BEFORE);
  const kick = BEFORE / STEP;
  const end = kick + minutesBetween(event.start, event.end) / STEP;
  const rects = values.map((v, i) => {
    const cls = v === null ? "slot none" : v < BAD ? "slot calm" : "slot";
    const style = v !== null && v >= BAD ? ` style="--level:${level(v)}"` : "";
    const title = v === null ? "no data" : `${v > 0 ? "+" : ""}${v} min`;
    return `<rect x="${i}" width="0.86" height="1" class="${cls}"${style}><title>${addMinutes(from, i * STEP)} ${title}</title></rect>`;
  }).join("");
  const pct = (i) => (i / n * 100).toFixed(2);
  return `
    <svg class="strip" viewBox="0 0 ${n} 1" preserveAspectRatio="none" height="30" aria-hidden="true">
      ${rects}
      <line class="tick" x1="${kick}" x2="${kick}" y1="-0.25" y2="1.25" vector-effect="non-scaling-stroke"/>
      <line class="tick" x1="${end}" x2="${end}" y1="-0.25" y2="1.25" vector-effect="non-scaling-stroke"/>
    </svg>
    <div class="axis-row">
      ${pct(kick) > 14 ? `<span style="left:0">${from}</span>` : ""}
      <span class="kick" style="left:${pct(kick)}%">${event.start}</span>
      <span class="kick" style="left:${pct(end)}%">${event.end}</span>
      ${pct(end) < 86 ? `<span style="right:0">${addMinutes(from, n * STEP)}</span>` : ""}
    </div>`;
}

function chart(out) {
  const v = out.median, lo = out.low, hi = out.high, n = v.length;
  const known = hi.filter((x) => x !== null).concat(lo.filter((x) => x !== null));
  const top = Math.max(4, ...known), bottom = Math.min(-2, ...known);
  const y = (m) => ((top - m) / (top - bottom) * 100).toFixed(2);
  let line = "", band = "";
  let seg = [];
  const flush = () => {
    if (seg.length) {
      line += "M" + seg.map((i) => `${i + 0.5},${y(v[i])}`).join("L");
      band += `<polygon class="band" points="${seg.map((i) => `${i + 0.5},${y(hi[i])}`).concat(seg.slice().reverse().map((i) => `${i + 0.5},${y(lo[i])}`)).join(" ")}"/>`;
    }
    seg = [];
  };
  v.forEach((m, i) => (m === null ? flush() : seg.push(i)));
  flush();
  return `
    <div class="chart-wrap" data-from="${out.from}" data-top="${top}" data-bottom="${bottom}" data-values="${esc(JSON.stringify(v))}">
      <div class="hover" hidden><span class="hover-dot"></span><span class="hover-text"></span></div>
      <span class="chart-label" style="top:0">+${Math.round(top)} min</span>
      <span class="chart-label" style="top:${y(0)}%">normal</span>
      <svg class="chart" viewBox="0 0 ${n} 100" preserveAspectRatio="none" height="140" aria-hidden="true">
        ${band}
        <line class="zero" x1="0" x2="${n}" y1="${y(0)}" y2="${y(0)}" vector-effect="non-scaling-stroke"/>
        <line class="limit" x1="0" x2="${n}" y1="${y(BAD)}" y2="${y(BAD)}" vector-effect="non-scaling-stroke"/>
        <path class="line" d="${line}" vector-effect="non-scaling-stroke"/>
      </svg>
    </div>
    <p class="basis">Line: typical extra delay. Shading: range across logged games.</p>`;
}

function direction(event, route, label, id) {
  const out = event.outlook && event.outlook[route];
  if (!event.outlook) {
    return `<div class="direction"><h3>${label}</h3><p class="verdict unknown">Time not confirmed yet</p></div>`;
  }
  const [cls, text] = verdict(out);
  const hasChart = out.games > 0;
  const basis = out.games ? `Based on ${out.games} logged game${out.games === 1 ? "" : "s"} like this one` : "";
  const body = strip(out, event);
  return `
    <div class="direction">
      <h3>${label}</h3>
      <p class="verdict ${cls}">${text}</p>
      ${hasChart
        ? `<button class="strip-button" aria-expanded="false" aria-controls="${id}">${body}<span class="sr">Show detail</span></button>
           <div class="detail" id="${id}" hidden>${chart(out)}</div>`
        : body}
      ${basis ? `<p class="basis">${basis}</p>` : ""}
    </div>`;
}

function badges(event, today) {
  const list = [];
  if (event.days > 1) list.push(["", `${event.days} days`]);
  if (event.size === "big") list.push(["", "Big crowd"]);
  if (event.closures.length) list.push(["warn", "Roads closed"]);
  if (event.status === "cancelled") list.push(["warn", "Cancelled"]);
  if (event.status === "unconfirmed") list.push(["", "Not confirmed"]);
  if (event.rescheduled_from) list.push(["", `Moved from ${dayLabel(event.rescheduled_from, today)}`]);
  return list.map(([c, t]) => `<span class="badge ${c}">${esc(t)}</span>`).join("");
}

function closures(event) {
  if (!event.closures.length) return "";
  const item = (c) => `<li>${esc(c.road)} closed ${dayFmt.format(new Date(c.from))} ${timeFmt.format(new Date(c.from))} to ${dayFmt.format(new Date(c.to))} ${timeFmt.format(new Date(c.to))}</li>`;
  return `<ul class="closures">${event.closures.map(item).join("")}</ul>`;
}

function directions(event, prefix) {
  return ROUTES.map(([r, label]) => direction(event, r, label, `${prefix}-${r}`)).join("");
}

function render(data) {
  const today = data.updated.slice(0, 10);
  const status = document.getElementById("status");
  const failing = data.sources.filter((s) => !s.ok);
  status.className = "status" + (failing.length ? " bad" : "");
  status.textContent = failing.length
    ? `${failing.map((s) => s.name).join(" and ")} not responding since ${dayLabel(failing[0].failing_since || today, today)}. Times may be out of date.`
    : `Updated ${dayLabel(data.updated, today)}, ${data.updated.slice(11, 16)}`;

  const [next, ...later] = data.events;
  const nextEl = document.getElementById("next");
  if (!next) {
    nextEl.innerHTML = `<p class="verdict unknown">No events listed at the stadium yet.</p>`;
    return;
  }
  const kickWord = next.category === "sport" ? "kick-off" : "starts";
  nextEl.innerHTML = `
    <p class="when">${dayLabel(next.date, today)}${next.start ? `, ${kickWord} ${next.start}` : ", time to be confirmed"} <span class="badges">${badges(next, today)}</span></p>
    <h2 class="what">${esc(next.name)}</h2>
    ${closures(next)}
    <div class="next-strips">${directions(next, "next")}</div>`;

  document.getElementById("later").hidden = !later.length;
  document.getElementById("later-list").innerHTML = later.map((e, i) => `
    <li>
      <details>
        <summary>
          <span class="day">${dayLabel(e.date, today)}</span>
          <span class="name">${esc(e.name)}</span>
          <span class="time">${e.start || "Time TBC"}</span>
          ${badges(e, today) ? `<span class="badges">${badges(e, today)}</span>` : ""}
        </summary>
        ${closures(e)}
        ${directions(e, `later${i}`)}
      </details>
    </li>`).join("");
}

document.addEventListener("click", (ev) => {
  const button = ev.target.closest(".strip-button");
  if (!button) return;
  const detail = document.getElementById(button.getAttribute("aria-controls"));
  const open = button.getAttribute("aria-expanded") === "true";
  button.setAttribute("aria-expanded", String(!open));
  detail.hidden = open;
});

function showHover(ev) {
  const wrap = ev.target.closest(".chart-wrap");
  document.querySelectorAll(".hover").forEach((h) => { if (!wrap || !wrap.contains(h)) h.hidden = true; });
  if (!wrap) return;
  const values = JSON.parse(wrap.dataset.values), n = values.length;
  const box = wrap.querySelector(".chart").getBoundingClientRect();
  const i = Math.max(0, Math.min(n - 1, Math.floor((ev.clientX - box.left) / box.width * n)));
  const hover = wrap.querySelector(".hover"), v = values[i];
  if (v === null) { hover.hidden = true; return; }
  const top = +wrap.dataset.top, bottom = +wrap.dataset.bottom;
  hover.style.left = `${(i + 0.5) / n * 100}%`;
  hover.style.top = `${(top - v) / (top - bottom) * box.height}px`;
  hover.querySelector(".hover-text").textContent =
    `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v)} min at ${addMinutes(wrap.dataset.from, i * STEP)}`;
  hover.classList.toggle("flip", i > n * 0.6);
  hover.hidden = false;
}

document.addEventListener("pointermove", showHover);
document.addEventListener("pointerdown", showHover);

fetch("data.json", { cache: "no-cache" })
  .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status))))
  .then(render)
  .catch(() => {
    const status = document.getElementById("status");
    status.className = "status bad";
    status.textContent = "Couldn't load the event list. Check your connection and reload.";
  });

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}
