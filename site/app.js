/* Course Viewer — app.js */
"use strict";

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let COURSES = [];
let activeView = "home"; // "home" | "chapter" | "search"
let activeCourseIdx = null;
let activeChapterIdx = null;
let searchIndex = []; // flat list of {courseIdx, chapterIdx, sectionIdx, heading, content, path}

// ---------------------------------------------------------------------------
// DOM refs
// ---------------------------------------------------------------------------
const sidebar      = document.getElementById("sidebar");
const contentEl    = document.getElementById("content");
const searchInput  = document.getElementById("search-input");
const themeToggle  = document.getElementById("theme-toggle");
const menuToggle   = document.getElementById("menu-toggle");

// ---------------------------------------------------------------------------
// Theme
// ---------------------------------------------------------------------------
function initTheme() {
  const saved = localStorage.getItem("theme") || "light";
  document.documentElement.setAttribute("data-theme", saved);
  themeToggle.textContent = saved === "dark" ? "☀ Light" : "☾ Dark";
}

themeToggle.addEventListener("click", () => {
  const current = document.documentElement.getAttribute("data-theme");
  const next = current === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("theme", next);
  themeToggle.textContent = next === "dark" ? "☀ Light" : "☾ Dark";
});

// ---------------------------------------------------------------------------
// Sidebar toggle (mobile)
// ---------------------------------------------------------------------------
menuToggle.addEventListener("click", () => {
  sidebar.classList.toggle("open");
});

document.addEventListener("click", (e) => {
  if (!sidebar.contains(e.target) && e.target !== menuToggle) {
    sidebar.classList.remove("open");
  }
});

// ---------------------------------------------------------------------------
// Build sidebar
// ---------------------------------------------------------------------------
function buildSidebar() {
  sidebar.innerHTML = "";

  COURSES.forEach((course, ci) => {
    const courseEl = document.createElement("div");
    courseEl.className = "sidebar-course";

    const courseBtn = document.createElement("button");
    courseBtn.className = "course-toggle open";
    courseBtn.innerHTML = `<span>${escHtml(course.name)}</span><span class="caret">▶</span>`;
    courseEl.appendChild(courseBtn);

    const chapterList = document.createElement("div");
    chapterList.className = "chapter-list open";

    course.chapters.forEach((chapter, chi) => {
      const chapterItem = document.createElement("div");
      chapterItem.className = "chapter-item";

      const chBtn = document.createElement("button");
      chBtn.className = "chapter-toggle";
      chBtn.innerHTML = `<span>${escHtml(chapter.title)}</span><span class="caret">▶</span>`;
      chapterItem.appendChild(chBtn);

      const sectionList = document.createElement("div");
      sectionList.className = "section-list";

      chapter.sections.forEach((section, si) => {
        const link = document.createElement("a");
        link.className = "section-link";
        link.href = "#";
        link.textContent = section.heading;
        link.dataset.ci = ci;
        link.dataset.chi = chi;
        link.dataset.si = si;

        link.addEventListener("click", (e) => {
          e.preventDefault();
          sidebar.classList.remove("open");
          showChapter(ci, chi, si);
        });

        sectionList.appendChild(link);
      });

      chBtn.addEventListener("click", () => {
        const isOpen = sectionList.classList.toggle("open");
        chBtn.classList.toggle("open", isOpen);

        // If chapter has sections, navigate to it on first click (when opening)
        if (isOpen) {
          showChapter(ci, chi, null);
        }
      });

      chapterItem.appendChild(sectionList);
      chapterList.appendChild(chapterItem);
    });

    courseBtn.addEventListener("click", () => {
      const isOpen = chapterList.classList.toggle("open");
      courseBtn.classList.toggle("open", isOpen);
    });

    courseEl.appendChild(chapterList);
    sidebar.appendChild(courseEl);
  });
}

function setSidebarActive(ci, chi, si) {
  document.querySelectorAll(".section-link").forEach(l => l.classList.remove("active"));

  if (si === null) return;

  const link = sidebar.querySelector(
    `.section-link[data-ci="${ci}"][data-chi="${chi}"][data-si="${si}"]`
  );
  if (!link) return;
  link.classList.add("active");

  // Ensure parent lists are open
  const sectionList = link.closest(".section-list");
  const chBtn = sectionList?.previousElementSibling;
  if (sectionList && !sectionList.classList.contains("open")) {
    sectionList.classList.add("open");
    chBtn?.classList.add("open");
  }
  const chapterList = link.closest(".chapter-list");
  const courseBtn = chapterList?.previousElementSibling;
  if (chapterList && !chapterList.classList.contains("open")) {
    chapterList.classList.add("open");
    courseBtn?.classList.add("open");
  }
}

// ---------------------------------------------------------------------------
// Views
// ---------------------------------------------------------------------------
function showHome() {
  activeView = "home";
  activeCourseIdx = null;
  activeChapterIdx = null;
  setSidebarActive(null, null, null);

  const cards = COURSES.map((c, ci) => `
    <div class="course-card" data-ci="${ci}">
      <h3>${escHtml(c.name)}</h3>
      <p>${c.chapters.length} chapter${c.chapters.length !== 1 ? "s" : ""} &bull; ${countSections(c)} sections</p>
    </div>
  `).join("");

  contentEl.innerHTML = `
    <div id="home-view">
      <h1>Course Viewer</h1>
      <p>Select a chapter from the sidebar or choose a course below to get started.</p>
      <div class="course-cards">${cards}</div>
    </div>
  `;

  contentEl.querySelectorAll(".course-card").forEach(card => {
    card.addEventListener("click", () => {
      const ci = parseInt(card.dataset.ci);
      showChapter(ci, 0, null);
    });
  });
}

function showChapter(ci, chi, scrollToSection) {
  activeView = "chapter";
  activeCourseIdx = ci;
  activeChapterIdx = chi;

  const course = COURSES[ci];
  const chapter = course.chapters[chi];

  setSidebarActive(ci, chi, scrollToSection);

  const sectionsHtml = chapter.sections.map((sec, si) => `
    <div class="section-card${scrollToSection === si ? " open" : ""}" data-si="${si}">
      <div class="section-header">
        <h2>${escHtml(sec.heading)}</h2>
        <span class="section-caret">▶</span>
      </div>
      <div class="section-body">${formatContent(sec.content)}</div>
    </div>
  `).join("");

  contentEl.innerHTML = `
    <div id="breadcrumb">
      <span class="crumb" data-action="home">Home</span>
      <span>›</span>
      <span>${escHtml(course.name)}</span>
      <span>›</span>
      <span>${escHtml(chapter.title)}</span>
    </div>
    <div id="chapter-view">
      <h1>${escHtml(chapter.title)}</h1>
      ${sectionsHtml}
    </div>
  `;

  // Section expand/collapse
  contentEl.querySelectorAll(".section-card").forEach(card => {
    card.querySelector(".section-header").addEventListener("click", () => {
      card.classList.toggle("open");
    });
  });

  // Breadcrumb home
  contentEl.querySelector(".crumb[data-action='home']")?.addEventListener("click", showHome);

  // Scroll to target section
  if (scrollToSection !== null) {
    const target = contentEl.querySelector(`.section-card[data-si="${scrollToSection}"]`);
    if (target) {
      setTimeout(() => target.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    }
  } else {
    window.scrollTo({ top: 0 });
  }
}

function showSearchResults(query) {
  if (!query.trim()) {
    showHome();
    return;
  }

  activeView = "search";
  setSidebarActive(null, null, null);

  const results = searchIndex.filter(item => {
    const q = query.toLowerCase();
    return item.heading.toLowerCase().includes(q) || item.content.toLowerCase().includes(q);
  }).slice(0, 50);

  const resultsHtml = results.length === 0
    ? `<p style="color:var(--text-muted);margin-top:1rem">No results for "<strong>${escHtml(query)}</strong>".</p>`
    : results.map(r => {
        const snippet = getSnippet(r.content, query);
        return `
          <div class="result-item" data-ci="${r.courseIdx}" data-chi="${r.chapterIdx}" data-si="${r.sectionIdx}">
            <div class="result-title">${highlight(escHtml(r.heading), query)}</div>
            <div class="result-path">${escHtml(r.path)}</div>
            <div class="result-snippet">${highlight(escHtml(snippet), query)}</div>
          </div>
        `;
      }).join("");

  contentEl.innerHTML = `
    <div id="search-results-info" style="display:block">
      ${results.length} result${results.length !== 1 ? "s" : ""} for "<strong>${escHtml(query)}</strong>"
    </div>
    <div id="search-view">${resultsHtml}</div>
  `;

  contentEl.querySelectorAll(".result-item").forEach(item => {
    item.addEventListener("click", () => {
      const ci  = parseInt(item.dataset.ci);
      const chi = parseInt(item.dataset.chi);
      const si  = parseInt(item.dataset.si);
      searchInput.value = "";
      showChapter(ci, chi, si);
    });
  });
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------
function buildSearchIndex() {
  searchIndex = [];
  COURSES.forEach((course, ci) => {
    course.chapters.forEach((chapter, chi) => {
      chapter.sections.forEach((section, si) => {
        searchIndex.push({
          courseIdx: ci,
          chapterIdx: chi,
          sectionIdx: si,
          heading: section.heading,
          content: section.content || "",
          path: `${course.name} › ${chapter.title}`,
        });
      });
    });
  });
}

let searchTimer = null;
searchInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  const q = searchInput.value;
  searchTimer = setTimeout(() => {
    if (q.trim()) {
      showSearchResults(q);
    } else {
      if (activeView === "search") showHome();
    }
  }, 220);
});

searchInput.addEventListener("keydown", e => {
  if (e.key === "Escape") {
    searchInput.value = "";
    if (activeView === "search") showHome();
  }
});

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function escHtml(str) {
  return (str || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                    .replace(/"/g, "&quot;");
}

function highlight(html, query) {
  if (!query) return html;
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return html.replace(new RegExp(`(${escaped})`, "gi"), "<mark>$1</mark>");
}

function getSnippet(text, query, radius = 140) {
  const lower = text.toLowerCase();
  const idx = lower.indexOf(query.toLowerCase());
  if (idx === -1) return text.slice(0, radius * 2);
  const start = Math.max(0, idx - radius);
  const end = Math.min(text.length, idx + query.length + radius);
  return (start > 0 ? "…" : "") + text.slice(start, end) + (end < text.length ? "…" : "");
}

function formatContent(text) {
  if (!text) return "<p><em>No content.</em></p>";
  return text
    .split(/\n\n+/)
    .map(para => {
      const p = para.trim();
      if (!p) return "";
      // Bold markers **text**
      const html = escHtml(p).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
      return `<p>${html}</p>`;
    })
    .join("");
}

function countSections(course) {
  return course.chapters.reduce((s, ch) => s + ch.sections.length, 0);
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
async function init() {
  initTheme();

  try {
    const resp = await fetch("../data/courses.json");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    COURSES = data.courses || [];
  } catch (err) {
    contentEl.innerHTML = `
      <div style="padding:3rem;text-align:center;color:var(--text-muted)">
        <h2 style="margin-bottom:.5rem">courses.json not found</h2>
        <p>Run <code>python scripts/parse_pdfs.py</code> first, then refresh this page.</p>
        <p style="margin-top:.5rem;font-size:.85rem">${escHtml(err.message)}</p>
      </div>
    `;
    return;
  }

  buildSidebar();
  buildSearchIndex();
  showHome();
}

init();
