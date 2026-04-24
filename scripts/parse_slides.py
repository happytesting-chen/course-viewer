#!/usr/bin/env python3
"""
Black Hat Training Slide Parser
Converts PDF slides to JPEG images and builds docs/data/courses.json.

Detection rules for course1 (AI Red Teaming):
  AGENDA_PAGE    — text contains "Agenda" near top + "Module N" anywhere
  SECTION_TITLE  — first non-footer line matches ^\d+\.\d+[\s:]
  FOOTER         — lines matching "AI Red Teaming", "Gary Lopez", or bare numbers → ignored
  INTRO_SLIDES   — pages before first Agenda → grouped as "Course Info" preamble

Usage:
    python scripts/parse_slides.py --course course1 --verbose
    python scripts/parse_slides.py --quality 80 --dpi 120
"""

import argparse
import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

try:
    import yaml
except ImportError:
    print("PyYAML not found. Run: pip install PyYAML", file=sys.stderr)
    sys.exit(1)

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).resolve().parent.parent
PDFS_DIR = ROOT / "pdfs"
DOCS_DIR = ROOT / "docs"
OUT_JSON = DOCS_DIR / "data" / "courses.json"

# ── Regexes ────────────────────────────────────────────────────────────────
FOOTER_RE       = re.compile(r'(AI Red Teaming|Gary Lopez|Black Hat|GovTech|Botanica|\bBHUS\b)', re.I)
BARE_NUMBER_RE  = re.compile(r'^\d{1,3}$')
AGENDA_RE       = re.compile(r'\bAgenda\b', re.I)
MODULE_RE       = re.compile(r'\bModule\s+(\d+)\b', re.I)
DURATION_RE     = re.compile(r'(\d+)\s*min', re.I)
SECTION_LIST_RE = re.compile(r'^[-•➤]?\s*(\d+\.\d+)\s*[:\-\s]\s*(.+)')
SECTION_TITLE_RE= re.compile(r'^(\d+\.\d+)[\s:]+(.*)')


# ── Text helpers ───────────────────────────────────────────────────────────

def extract_lines(page) -> list[str]:
    """Return non-empty page lines, stripping footer noise."""
    out = []
    for raw in page.get_text().splitlines():
        line = raw.strip()
        if not line:
            continue
        if FOOTER_RE.search(line):
            continue
        if BARE_NUMBER_RE.match(line):
            continue
        out.append(line)
    return out


# ── Page classification ────────────────────────────────────────────────────

def classify(lines: list[str]) -> tuple[str, dict]:
    """
    Returns (role, data):
      'agenda'        → {num, title, duration, sections:[{number,title}]}
      'section_start' → {number, title}
      'content'       → {}
      'noise'         → {}
    """
    if not lines:
        return "noise", {}

    # ── Agenda detection ──────────────────────────────────────────────────
    has_agenda = any(AGENDA_RE.search(l) for l in lines[:8])
    has_module = any(MODULE_RE.search(l) for l in lines)

    if has_agenda and has_module:
        mod_num   = None
        mod_title = None
        duration  = None
        sections  = []

        for i, line in enumerate(lines):
            # Duration
            dm = DURATION_RE.search(line)
            if dm and duration is None:
                duration = line.strip()

            # Section list items
            sm = SECTION_LIST_RE.match(line)
            if sm:
                title = sm.group(2).strip().rstrip("🧪c").strip()
                if len(title) > 1:
                    sections.append({"number": sm.group(1), "title": title})

            # Module number — title is the line immediately BEFORE it
            # (slide layout: Agenda → sections → title → duration → Module N)
            m = MODULE_RE.search(line)
            if m and mod_num is None:
                mod_num = int(m.group(1))
                for j in range(i - 1, max(i - 5, -1), -1):
                    cand = lines[j]
                    if (not MODULE_RE.search(cand) and not AGENDA_RE.search(cand)
                            and not DURATION_RE.search(cand)
                            and not SECTION_LIST_RE.match(cand)
                            and len(cand) > 2):
                        mod_title = cand
                        break

        return "agenda", {
            "num":      mod_num or 0,
            "title":    mod_title or f"Module {mod_num}",
            "duration": duration,
            "sections": sections,
        }

    # ── Section title detection ───────────────────────────────────────────
    m = SECTION_TITLE_RE.match(lines[0])
    if m:
        title = m.group(2).strip().rstrip("🧪").strip() or lines[0]
        return "section_start", {"number": m.group(1), "title": title}

    return "content", {}


# ── Image conversion ───────────────────────────────────────────────────────

def render_page(page, dest: Path, dpi: int, quality: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    pix = page.get_pixmap(dpi=dpi)
    pix.save(str(dest), output="jpeg", jpg_quality=quality)


# ── Course parsing ─────────────────────────────────────────────────────────

def parse_course(course_dir: Path, cfg: dict, args) -> dict:
    course_id   = cfg.get("id",     course_dir.name)
    course_name = cfg.get("name",   course_dir.name.replace("-", " ").title())
    author      = cfg.get("author", "")
    verbose     = args.verbose
    dpi         = args.dpi
    quality     = args.quality

    slide_dir = DOCS_DIR / "slides" / course_id
    slide_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(course_dir.glob("*.pdf"))
    if not pdfs:
        print(f"  No PDFs in {course_dir}", file=sys.stderr)
        return {"id": course_id, "name": course_name, "author": author, "modules": []}

    # ── Pass 1: classify pages + render images ─────────────────────────────
    classified: list[dict] = []   # {role, data, img_path, page_num}
    global_idx = 0

    for pdf_path in pdfs:
        doc = fitz.open(str(pdf_path))
        if verbose:
            print(f"  Rendering {pdf_path.name} ({len(doc)} pages)…")

        for page in doc:
            global_idx += 1
            lines = extract_lines(page)
            role, data = classify(lines)
            img_name = f"page_{global_idx:04d}.jpg"
            img_path = slide_dir / img_name
            rel_path = f"slides/{course_id}/{img_name}"

            render_page(page, img_path, dpi, quality)

            if verbose and role in ("agenda", "section_start"):
                tag = f"[AGENDA mod{data.get('num')}]" if role == "agenda" \
                      else f"[SECTION {data.get('number')}]"
                preview = data.get("title", "")[:60]
                print(f"    p{global_idx:04d} {tag} {preview}")

            classified.append({
                "role":     role,
                "data":     data,
                "rel_path": rel_path,
                "idx":      global_idx,
            })

        doc.close()

    # ── Pass 2: build module / section structure ───────────────────────────
    modules: list[dict] = []
    preamble_slides: list[str] = []
    cur_mod:  dict | None = None
    cur_sec:  dict | None = None
    pre_agenda_done = False

    def flush_sec():
        nonlocal cur_sec
        if cur_sec and cur_mod is not None:
            cur_mod["sections"].append(cur_sec)
        cur_sec = None

    def flush_mod():
        nonlocal cur_mod
        flush_sec()
        if cur_mod:
            # drop sections with no slides
            cur_mod["sections"] = [s for s in cur_mod["sections"] if s["slides"]]
            if cur_mod["sections"] or cur_mod.get("agenda_slide"):
                modules.append(cur_mod)
        cur_mod = None

    for entry in classified:
        role     = entry["role"]
        data     = entry["data"]
        rel_path = entry["rel_path"]

        if role == "noise":
            continue

        if not pre_agenda_done and role != "agenda":
            preamble_slides.append(rel_path)
            continue

        if role == "agenda":
            flush_mod()
            pre_agenda_done = True
            num   = data["num"]
            title = data["title"]
            title = cfg.get("modules", {}).get(num, title)

            # Merge with existing module of same number (e.g. Module 5 spans Day1+Day2)
            existing_mod = next((m for m in modules if m["number"] == num), None)
            if existing_mod:
                cur_mod = existing_mod
                modules.remove(existing_mod)  # will be re-appended on flush
                cur_sec = cur_mod["sections"][-1] if cur_mod["sections"] else None
                if verbose:
                    print(f"    → Module {num}: merging continuation")
            else:
                cur_mod = {
                    "id":          f"mod{num}",
                    "number":      num,
                    "title":       title,
                    "duration":    data.get("duration", ""),
                    "agenda_slide": rel_path,
                    "sections":    [],
                }
                for sec_info in data.get("sections", []):
                    n = sec_info["number"]
                    # Don't add duplicates
                    if not any(s["number"] == n for s in cur_mod["sections"]):
                        cur_mod["sections"].append({
                            "id":     f"s{n.replace('.','_')}",
                            "number": n,
                            "title":  sec_info["title"],
                            "slides": [],
                        })
                cur_sec = cur_mod["sections"][0] if cur_mod["sections"] else None
                if verbose:
                    print(f"    → Module {num}: {title} "
                          f"({len(cur_mod['sections'])} sections from agenda)")
            continue

        if role == "section_start":
            if cur_mod is None:
                # section before any agenda — attach to first module or preamble
                preamble_slides.append(rel_path)
                continue
            number = data["number"]
            # Find pre-populated section from agenda
            match = next((s for s in cur_mod["sections"] if s["number"] == number), None)
            if match:
                cur_sec = match
            else:
                # New section not in agenda
                if cur_sec is not None and cur_sec not in cur_mod["sections"]:
                    cur_mod["sections"].append(cur_sec)
                cur_sec = {
                    "id":     f"s{number.replace('.','_')}",
                    "number": number,
                    "title":  data["title"],
                    "slides": [],
                }
                cur_mod["sections"].append(cur_sec)
            cur_sec["slides"].append(rel_path)
            continue

        # Content slide
        if cur_mod is None:
            preamble_slides.append(rel_path)
        elif cur_sec is not None:
            cur_sec["slides"].append(rel_path)
        elif cur_mod["sections"]:
            cur_mod["sections"][-1]["slides"].append(rel_path)

    flush_mod()

    # Add preamble as Module 0 if it has slides
    if preamble_slides:
        modules.insert(0, {
            "id":          "mod0",
            "number":      0,
            "title":       "Course Info",
            "duration":    "",
            "agenda_slide": "",
            "sections": [{
                "id":     "s0_0",
                "number": "0",
                "title":  "Overview",
                "slides": preamble_slides,
            }],
        })

    total_slides = sum(
        len(s["slides"])
        for m in modules for s in m["sections"]
    )
    print(f"  {course_name}: {len(modules)} modules, "
          f"{sum(len(m['sections']) for m in modules)} sections, "
          f"{total_slides} slides → {slide_dir}")

    return {
        "id":      course_id,
        "name":    course_name,
        "author":  author,
        "modules": modules,
    }


# ── Config loader ──────────────────────────────────────────────────────────

def load_config(course_dir: Path) -> dict:
    p = course_dir / "config.yaml"
    if p.exists():
        with open(p) as f:
            return yaml.safe_load(f) or {}
    return {"id": course_dir.name, "name": course_dir.name.replace("-", " ").title()}


# ── Entry point ────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Parse slide PDFs → JPEG + courses.json")
    ap.add_argument("--verbose",  "-v", action="store_true")
    ap.add_argument("--course",   help="Only process this course (e.g. course1)")
    ap.add_argument("--dpi",      type=int, default=150, help="Render DPI (default 150)")
    ap.add_argument("--quality",  type=int, default=85,  help="JPEG quality 1-95 (default 85)")
    args = ap.parse_args()

    course_dirs = [d for d in sorted(PDFS_DIR.iterdir()) if d.is_dir()]
    if args.course:
        course_dirs = [d for d in course_dirs if d.name == args.course]
        if not course_dirs:
            print(f"Course '{args.course}' not found under {PDFS_DIR}")
            sys.exit(1)

    # Load existing JSON so we can merge (preserve other courses)
    existing = {}
    if OUT_JSON.exists():
        with open(OUT_JSON) as f:
            try:
                existing = {c["id"]: c for c in json.load(f).get("courses", [])}
            except Exception:
                pass

    for course_dir in course_dirs:
        cfg    = load_config(course_dir)
        cid    = cfg.get("id", course_dir.name)
        print(f"\nProcessing: {cfg.get('name', course_dir.name)}")
        course = parse_course(course_dir, cfg, args)
        existing[cid] = course

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"courses": list(existing.values())}, f, ensure_ascii=False, indent=2)

    total = sum(
        len(s["slides"])
        for c in existing.values()
        for m in c["modules"]
        for s in m["sections"]
    )
    print(f"\nDone — {total} slides total → {OUT_JSON}")


if __name__ == "__main__":
    main()
