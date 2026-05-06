"use strict";

// ── State ──────────────────────────────────────────────────────────────────
let COURSES      = [];
let curCourse    = null;   // course object
let curMod       = null;   // module object
let curSec       = null;   // section object
let curSlide     = 0;      // index within section.slides
let chatHistory  = [];     // {role, content}[] conversation turns

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
const sidebarEl      = D("sidebar");
const sbOpen         = D("sidebar-open");
const sbClose        = D("sidebar-close");
const aboutPanel      = D("about-panel");
const aboutCourseName = D("about-course-name");
const aboutPara1      = D("about-para1");
const chatPanel       = D("chat-panel");
const chatCourseName  = D("chat-course-name");
const chatMessages    = D("chat-messages");
const chatInput       = D("chat-input");
const chatSend        = D("chat-send");
const chatClear       = D("chat-clear");
const askAiBtn        = D("ask-ai-btn");

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

  // "About this course" — merges all module summary slides
  const summarySlides = [];
  curCourse.modules.forEach(mod => {
    mod.sections.forEach(sec => {
      if (sec.number === "summary") summarySlides.push(...sec.slides);
    });
  });

  if (summarySlides.length) {
    const aboutSec = { id: "__about__", title: "About this course", slides: summarySlides };
    const divider = document.createElement("div");
    divider.className = "about-divider";
    navTree.appendChild(divider);

    const aboutBtn = document.createElement("button");
    aboutBtn.className = "about-course-btn" + (curSec?.id === "__about__" ? " active" : "");
    aboutBtn.innerHTML = `<span>&#9432; About this course</span>`;
    aboutBtn.addEventListener("click", () => {
      sidebarEl.classList.remove("open");
      curSec = aboutSec;
      curMod = null;
      buildTabs();
      buildNav();
      showAbout();
    });
    navTree.appendChild(aboutBtn);
  }
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

  if (course !== curCourse) chatHistory = [];
  buildTabs();
  buildNav();
  hideAbout();
  hideChat();
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

// ── About panel ────────────────────────────────────────────────────────────
function showAbout() {
  hideSearch();
  viewer.style.display = "none";
  aboutCourseName.textContent = curCourse.name;
  aboutPara1.textContent = curCourse.summary || "";
  aboutPanel.hidden = false;
}

function hideAbout() {
  aboutPanel.hidden = true;
  viewer.style.display = "";
}

// ── Ask AI ─────────────────────────────────────────────────────────────────
function buildCourseContext() {
  const lines = [
    `You are an AI assistant for a training platform with ${COURSES.length} courses.`,
    `Answer questions based on the course content below. Be concise and technical.`,
    `The user is currently viewing: ${curCourse?.name || "unknown"}.`,
    `If a topic is not covered in the material, say so clearly.\n`,
  ];
  COURSES.forEach(course => {
    lines.push(`# ${course.name}`);
    if (course.summary) lines.push(course.summary);
    lines.push("");
    course.modules.forEach(m => {
      lines.push(`## Module ${m.number}: ${m.title}`);
      if (m.overview) lines.push(`Overview: ${m.overview}`);
      if (m.topics?.length) lines.push(`Topics: ${m.topics.join("; ")}`);
      lines.push("");
    });
  });
  return lines.join("\n");
}

function showChat() {
  hideSearch();
  hideAbout();
  viewer.style.display = "none";
  chatCourseName.textContent = curCourse?.name || "";
  chatPanel.hidden = false;
  askAiBtn.classList.add("active");
  chatInput.focus();
}

function hideChat() {
  chatPanel.hidden = true;
  viewer.style.display = "";
  askAiBtn.classList.remove("active");
}

function appendMessage(role, text) {
  const div = document.createElement("div");
  div.className = `chat-msg chat-${role}`;
  div.textContent = text;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return div;
}

async function sendMessage() {
  const question = chatInput.value.trim();
  if (!question || chatSend.disabled) return;

  chatInput.value = "";
  chatInput.disabled = true;
  chatSend.disabled = true;

  appendMessage("user", question);
  chatHistory.push({ role: "user", content: question });

  const aiDiv = appendMessage("assistant", "…");

  const apiKey = (typeof window.ANTHROPIC_API_KEY !== "undefined") ? window.ANTHROPIC_API_KEY : "";
  if (!apiKey) {
    aiDiv.textContent = "API key not configured. Add ANTHROPIC_API_KEY to config.js.";
    chatInput.disabled = false;
    chatSend.disabled = false;
    return;
  }

  try {
    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
        "anthropic-dangerous-direct-browser-access": "true",
      },
      body: JSON.stringify({
        model: "claude-haiku-4-5-20251001",
        max_tokens: 1024,
        system: buildCourseContext(),
        messages: chatHistory.slice(-12),
        stream: true,
      }),
    });

    if (!res.ok) throw new Error(`API error ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let fullText = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      for (const line of decoder.decode(value, { stream: true }).split("\n")) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (!raw || raw === "[DONE]") continue;
        try {
          const evt = JSON.parse(raw);
          if (evt.type === "content_block_delta" && evt.delta?.type === "text_delta") {
            fullText += evt.delta.text;
            aiDiv.textContent = fullText;
            chatMessages.scrollTop = chatMessages.scrollHeight;
          }
        } catch {}
      }
    }

    chatHistory.push({ role: "assistant", content: fullText });

  } catch (err) {
    aiDiv.textContent = `Error: ${err.message}`;
  }

  chatInput.disabled = false;
  chatSend.disabled = false;
  chatInput.focus();
}

askAiBtn.addEventListener("click", () => {
  sidebarEl.classList.remove("open");
  showChat();
});

chatSend.addEventListener("click", sendMessage);
chatInput.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
chatClear.addEventListener("click", () => {
  chatHistory = [];
  chatMessages.innerHTML = "";
  chatInput.focus();
});

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
