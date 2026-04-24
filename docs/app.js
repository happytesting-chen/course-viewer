"use strict";

// ── State ──────────────────────────────────────────────────────────────────
let COURSES      = [];
let curCourse    = null;   // course object
let curMod       = null;   // module object
let curSec       = null;   // section object
let curSlide     = 0;      // index within section.slides

// ── DOM ────────────────────────────────────────────────────────────────────
const D = id => document.getElementById(id);
const courseTabs  = D("course-tabs");
const navTree     = D("nav-tree");
const slideImg    = D("slide-img");
const placeholder = D("slide-placeholder");
const counter     = D("slide-counter");
const btnPrev     = D("btn-prev");
const btnNext     = D("btn-next");
const searchInput = D("search-input");
const searchRes   = D("search-results");
const searchList  = D("search-list");
const viewer      = D("viewer");
const themeBtn    = D("theme-btn");
const fsOverlay   = D("fullscreen-overlay");
const fsImg       = D("fs-img");
const fsCounter   = D("fs-counter");
const sidebarEl   = D("sidebar");
const sbOpen      = D("sidebar-open");
const sbClose     = D("sidebar-close");

// ── Theme ──────────────────────────────────────────────────────────────────
(function initTheme() {
  const t = localStorage.getItem("theme") || "dark";
  document.documentElement.setAttribute("data-theme", t);
  themeBtn.textContent = t === "dark" ? "☀" : "☾";
})();

themeBtn.addEventListener("click", () => {
  const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("theme", next);
  themeBtn.textContent = next === "dark" ? "☀" : "☾";
});

// ── Sidebar mobile ─────────────────────────────────────────────────────────
sbOpen.addEventListener("click",  () => sidebarEl.classList.add("open"));
sbClose.addEventListener("click", () => sidebarEl.classList.remove("open"));
document.addEventListener("click", e => {
  if (!sidebarEl.contains(e.target) && e.target !== sbOpen)
    sidebarEl.classList.remove("open");
});

// ── Hash routing ───────────────────────────────────────────────────────────
function parseHash() {
  const parts = location.hash.replace(/^#\/?/, "").split("/");
  return { courseId: parts[0] || null, modId: parts[1] || null, secId: parts[2] || null };
}

function setHash(courseId, modId, secId) {
  const h = `#/${courseId}/${modId}/${secId}`;
  if (location.hash !== h) history.replaceState(null, "", h);
}

function navigateFromHash() {
  const { courseId, modId, secId } = parseHash();
  const course = COURSES.find(c => c.id === courseId) || COURSES[0];
  if (!course) return;
  const mod = course.modules.find(m => m.id === modId) || course.modules[0];
  if (!mod) return;
  const sec = mod.sections.find(s => s.id === secId) || mod.sections[0];
  goTo(course, mod, sec, 0, false);
}

window.addEventListener("hashchange", navigateFromHash);

// ── Course tabs ────────────────────────────────────────────────────────────
function buildTabs() {
  courseTabs.innerHTML = "";
  COURSES.forEach(c => {
    const btn = document.createElement("button");
    btn.className = "course-tab" + (c === curCourse ? " active" : "");
    btn.textContent = c.name;
    btn.setAttribute("role", "tab");
    btn.addEventListener("click", () => {
      const mod = c.modules[0];
      const sec = mod?.sections[0];
      goTo(c, mod, sec, 0);
    });
    courseTabs.appendChild(btn);
  });
}

// ── Sidebar nav ────────────────────────────────────────────────────────────
function buildNav() {
  navTree.innerHTML = "";
  if (!curCourse) return;

  curCourse.modules.forEach(mod => {
    const wrap = document.createElement("div");
    const isActiveMod  = mod === curMod;
    const singleSection = mod.sections.length === 1;

    const btn = document.createElement("button");

    if (singleSection) {
      // Per-file mode: module button IS the nav item — one click loads slides
      const isActive = isActiveMod && mod.sections[0] === curSec;
      btn.className = "mod-toggle" + (isActive ? " open active-mod" : "");
      btn.innerHTML =
        `<span>${esc(mod.title)}</span>` +
        (mod.duration ? `<small class="mod-dur">${esc(mod.duration)}</small>` : "");
      btn.addEventListener("click", () => {
        sidebarEl.classList.remove("open");
        goTo(curCourse, mod, mod.sections[0], 0);
      });
      wrap.appendChild(btn);
    } else {
      // Multi-section mode: collapsible module with section links beneath
      btn.className = "mod-toggle" + (isActiveMod ? " open" : "");
      btn.innerHTML =
        `<span>Module ${mod.number}: ${esc(mod.title)}</span>` +
        (mod.duration ? `<small class="mod-dur">${esc(mod.duration)}</small>` : "") +
        `<span class="caret">▶</span>`;
      wrap.appendChild(btn);

      const secList = document.createElement("div");
      secList.className = "sec-list" + (isActiveMod ? " open" : "");

      mod.sections.forEach(sec => {
        const link = document.createElement("div");
        link.className = "sec-link" + (sec === curSec ? " active" : "");
        link.textContent = `${sec.number} ${sec.title}`;
        link.addEventListener("click", () => {
          sidebarEl.classList.remove("open");
          goTo(curCourse, mod, sec, 0);
        });
        secList.appendChild(link);
      });

      btn.addEventListener("click", () => {
        const open = secList.classList.toggle("open");
        btn.classList.toggle("open", open);
      });

      wrap.appendChild(secList);
    }

    navTree.appendChild(wrap);
  });
}

function scrollActiveLink() {
  const active = navTree.querySelector(".sec-link.active, .active-mod");
  active?.scrollIntoView({ block: "nearest" });
}

// ── Navigation ─────────────────────────────────────────────────────────────
function goTo(course, mod, sec, slideIdx, updateHash = true) {
  curCourse = course;
  curMod    = mod;
  curSec    = sec;
  curSlide  = slideIdx || 0;

  if (updateHash && course && mod && sec)
    setHash(course.id, mod.id, sec.id);

  buildTabs();
  buildNav();
  renderSlide();
  scrollActiveLink();
  hideSearch();
}

function renderSlide() {
  const slides = curSec?.slides || [];
  if (!slides.length) {
    slideImg.style.display = "none";
    placeholder.style.display = "";
    counter.textContent = "—";
    btnPrev.disabled = true;
    btnNext.disabled = true;
    return;
  }

  curSlide = Math.max(0, Math.min(curSlide, slides.length - 1));
  const src = "./" + slides[curSlide];
  slideImg.src = src;
  slideImg.style.display = "block";
  placeholder.style.display = "none";
  counter.textContent = `Slide ${curSlide + 1} of ${slides.length}`;
  btnPrev.disabled = curSlide === 0;
  btnNext.disabled = curSlide === slides.length - 1;

  if (!fsOverlay.hidden) {
    fsImg.src = src;
    fsCounter.textContent = `${curSlide + 1} / ${slides.length}`;
  }
}

function navigate(delta) {
  const slides = curSec?.slides || [];
  const next = curSlide + delta;
  if (next < 0 || next >= slides.length) return;
  curSlide = next;
  renderSlide();
}

btnPrev.addEventListener("click", () => navigate(-1));
btnNext.addEventListener("click", () => navigate(+1));

document.addEventListener("keydown", e => {
  if (e.target === searchInput) return;
  if (!fsOverlay.hidden) {
    if (e.key === "ArrowRight" || e.key === "ArrowDown") navigate(+1);
    if (e.key === "ArrowLeft"  || e.key === "ArrowUp")  navigate(-1);
    if (e.key === "Escape") closeFs();
    return;
  }
  if (e.key === "ArrowRight" || e.key === "ArrowDown") navigate(+1);
  if (e.key === "ArrowLeft"  || e.key === "ArrowUp")   navigate(-1);
});

// ── Fullscreen ─────────────────────────────────────────────────────────────
slideImg.addEventListener("click", () => {
  const slides = curSec?.slides;
  if (!slides?.length) return;
  fsImg.src = "./" + slides[curSlide];
  fsCounter.textContent = `${curSlide + 1} / ${slides.length}`;
  fsOverlay.hidden = false;
});

function closeFs() { fsOverlay.hidden = true; }
D("fs-close").addEventListener("click", closeFs);
fsOverlay.addEventListener("click", e => { if (e.target === fsOverlay) closeFs(); });
D("fs-prev").addEventListener("click", () => navigate(-1));
D("fs-next").addEventListener("click", () => navigate(+1));

// ── Search ─────────────────────────────────────────────────────────────────
function hideSearch() {
  searchRes.hidden = true;
  viewer.style.display = "";
}

function doSearch(q) {
  if (!q) { hideSearch(); return; }
  const hits = [];
  COURSES.forEach(course => {
    course.modules.forEach(mod => {
      const modTxt = `module ${mod.number} ${mod.title}`.toLowerCase();
      mod.sections.forEach(sec => {
        const secTxt = `${sec.number} ${sec.title}`.toLowerCase();
        if (modTxt.includes(q) || secTxt.includes(q))
          hits.push({ course, mod, sec });
      });
    });
  });

  viewer.style.display = "none";
  searchRes.hidden = false;
  searchList.innerHTML = hits.length
    ? hits.map((h, i) => `
        <div class="search-item" data-i="${i}">
          <div class="si-title">${esc(h.sec.number)} ${esc(h.sec.title)}</div>
          <div class="si-path">${esc(h.course.name)} › Module ${h.mod.number}: ${esc(h.mod.title)}</div>
        </div>`).join("")
    : `<p style="color:var(--text-muted)">No results for "${esc(q)}".</p>`;

  searchList.querySelectorAll(".search-item").forEach(el => {
    el.addEventListener("click", () => {
      const h = hits[parseInt(el.dataset.i)];
      searchInput.value = "";
      goTo(h.course, h.mod, h.sec, 0);
    });
  });
}

let st;
searchInput.addEventListener("input", () => {
  clearTimeout(st);
  st = setTimeout(() => doSearch(searchInput.value.toLowerCase().trim()), 200);
});
searchInput.addEventListener("keydown", e => {
  if (e.key === "Escape") { searchInput.value = ""; hideSearch(); }
});

// ── Utility ────────────────────────────────────────────────────────────────
function esc(s) {
  return (s || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

// ── Boot ───────────────────────────────────────────────────────────────────
async function init() {
  try {
    const res = await fetch("./data/courses.json");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    COURSES = (data.courses || []).filter(c => c.modules?.length);
  } catch (err) {
    placeholder.innerHTML =
      `<p>Could not load <code>data/courses.json</code>.<br>
       Run <code>python scripts/parse_slides.py</code> first.</p>
       <small style="opacity:.5">${esc(err.message)}</small>`;
    return;
  }

  if (!COURSES.length) {
    placeholder.textContent = "No courses found.";
    return;
  }

  // Navigate from hash or default to first course/module/section
  const { courseId, modId, secId } = parseHash();
  const course = COURSES.find(c => c.id === courseId) || COURSES[0];
  const mod    = course.modules.find(m => m.id === modId)    || course.modules[0];
  const sec    = mod?.sections.find(s => s.id === secId)     || mod?.sections[0];
  goTo(course, mod, sec, 0, !courseId);
}

init();
