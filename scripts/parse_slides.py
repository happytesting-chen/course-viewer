#!/usr/bin/env python3
"""
Slide Deck Parser
Converts PDF slides to JPEG images and builds docs/data/courses.json.

Detection rules:
  AGENDA_PAGE    — text contains "Agenda" near top + "Module N" anywhere
  SECTION_TITLE  — first non-footer line matches ^\d+\.\d+[\s:]
  FOOTER         — lines matching footer_patterns in config.yaml, or bare numbers → ignored
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
# FOOTER_RE is built per-course from config.yaml footer_patterns (see load_config)
FOOTER_RE       = re.compile(r'(?!)', re.I)   # default: match nothing
BARE_NUMBER_RE  = re.compile(r'^\d{1,3}$')
AGENDA_RE       = re.compile(r'\bAgenda\b', re.I)
MODULE_RE       = re.compile(r'\bModule\s+(\d+)\b', re.I)
DURATION_RE     = re.compile(r'(\d+)\s*min', re.I)
SECTION_LIST_RE = re.compile(r'^[-•➤]?\s*(\d+\.\d+)\s*[:\-\s]\s*(.+)')
SECTION_TITLE_RE= re.compile(r'^(\d+\.\d+)[\s:]+(.*)')
SUMMARY_RE      = re.compile(r'\bsummary\b', re.I)


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

    # ── Summary slide detection ───────────────────────────────────────────
    # Triggered when "Summary" appears in the first 2 non-footer lines
    if any(SUMMARY_RE.search(l) for l in lines[:2]):
        return "summary", {}

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


# ── Filename cleaner ───────────────────────────────────────────────────────

def clean_stem(stem: str) -> str:
    """Auto-derive a readable title from a PDF filename stem."""
    s = re.sub(r'^\d+[\.\s\-_]*', '', stem)   # strip leading "01." / "02 "
    s = re.sub(r'^pre_read_', '', s, flags=re.I)
    s = s.replace('-', ' ').replace('_', ' ')
    return s.strip().title() or stem


# ── Per-file mode (one module per PDF) ────────────────────────────────────

def parse_course_per_file(course_dir: Path, cfg: dict, args) -> dict:
    """Each PDF becomes one module; all its pages form one section."""
    course_id   = cfg.get("id",     course_dir.name)
    course_name = cfg.get("name",   course_dir.name.replace("-", " ").title())
    author      = cfg.get("author", "")
    file_names  = cfg.get("file_names", {})   # stem → display name overrides
    verbose     = args.verbose
    dpi         = args.dpi
    quality     = args.quality

    slide_dir = DOCS_DIR / "slides" / course_id
    slide_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(course_dir.glob("*.pdf"))
    if not pdfs:
        print(f"  No PDFs in {course_dir}", file=sys.stderr)
        return {"id": course_id, "name": course_name, "author": author, "modules": []}

    modules: list[dict] = []
    global_idx = 0

    for mod_num, pdf_path in enumerate(pdfs, start=1):
        stem  = pdf_path.stem
        title = file_names.get(stem, clean_stem(stem))
        doc   = fitz.open(str(pdf_path))

        if verbose:
            print(f"  [{mod_num}] {title}  ← {pdf_path.name} ({len(doc)} pages)")

        slides: list[str] = []
        for page in doc:
            global_idx += 1
            img_name = f"page_{global_idx:04d}.jpg"
            img_path = slide_dir / img_name
            render_page(page, img_path, dpi, quality)
            slides.append(f"slides/{course_id}/{img_name}")

        doc.close()

        mod_id = f"mod{mod_num}"
        sections = [{
            "id":     f"s{mod_num}_0",
            "number": str(mod_num),
            "title":  title,
            "slides": slides,
        }]
        # Attach generated summary slide if it exists
        summary_img = slide_dir / f"summary_{mod_id}.jpg"
        if summary_img.exists():
            sections.append({
                "id":     f"{mod_id}_sum",
                "number": "summary",
                "title":  "📝 Summary",
                "slides": [f"slides/{course_id}/summary_{mod_id}.jpg"],
            })

        modules.append({
            "id":          mod_id,
            "number":      mod_num,
            "title":       title,
            "duration":    "",
            "agenda_slide": slides[0] if slides else "",
            "sections":    sections,
        })

    total = sum(len(m["sections"][0]["slides"]) for m in modules)
    print(f"  {course_name}: {len(modules)} modules, {total} slides → {slide_dir}")
    return {"id": course_id, "name": course_name, "author": author, "modules": modules}


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

    def mod_title_for_log(mod):
        return mod.get("title", "") if mod else ""

    def flush_sec():
        nonlocal cur_sec
        if cur_sec and cur_mod is not None:
            cur_mod["sections"].append(cur_sec)
        cur_sec = None

    def flush_mod():
        nonlocal cur_mod
        flush_sec()
        if cur_mod:
            # Dedup sections by number — merge slides from duplicates into first occurrence
            seen: dict[str, dict] = {}
            deduped: list[dict] = []
            for sec in cur_mod["sections"]:
                n = sec["number"]
                if n in seen:
                    seen[n]["slides"].extend(sec["slides"])
                else:
                    seen[n] = sec
                    deduped.append(sec)
            cur_mod["sections"] = [s for s in deduped if s["slides"]]
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

        if role == "summary":
            if cur_mod is None:
                preamble_slides.append(rel_path)
                continue
            # Find or create the dedicated Summary section
            sum_sec = next((s for s in cur_mod["sections"] if s["number"] == "summary"), None)
            if sum_sec is None:
                sum_sec = {
                    "id":     f"{cur_mod['id']}_sum",
                    "number": "summary",
                    "title":  "📝 Summary",
                    "slides": [],
                }
                cur_mod["sections"].append(sum_sec)
            sum_sec["slides"].append(rel_path)
            cur_sec = sum_sec
            if verbose:
                print(f"    p{entry['idx']:04d} [SUMMARY] {mod_title_for_log(cur_mod)}")
            continue

        # Content slide
        if cur_mod is None:
            preamble_slides.append(rel_path)
        elif cur_sec is not None:
            cur_sec["slides"].append(rel_path)
        elif cur_mod["sections"]:
            cur_mod["sections"][-1]["slides"].append(rel_path)
        else:
            # Module has no sections yet — create a default one so slides aren't lost
            cur_sec = {
                "id":     f"s{cur_mod['number']}_1",
                "number": f"{cur_mod['number']}.1",
                "title":  cur_mod["title"],
                "slides": [rel_path],
            }
            cur_mod["sections"].append(cur_sec)

    flush_mod()

    # Add fallback "📝 Summary" section for modules without a detected summary slide
    for mod in modules:
        if not any(s["number"] == "summary" for s in mod["sections"]):
            fallback_img = slide_dir / f"summary_{mod['id']}.jpg"
            if fallback_img.exists():
                mod["sections"].append({
                    "id":     f"{mod['id']}_sum",
                    "number": "summary",
                    "title":  "📝 Summary",
                    "slides": [f"slides/{course_id}/summary_{mod['id']}.jpg"],
                })

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
    cfg = {}
    if p.exists():
        with open(p) as f:
            cfg = yaml.safe_load(f) or {}
    cfg.setdefault("id",   course_dir.name)
    cfg.setdefault("name", course_dir.name.replace("-", " ").title())

    # Build FOOTER_RE from config so no author/org names appear in this script
    patterns = cfg.get("footer_patterns", [])
    if patterns:
        global FOOTER_RE
        FOOTER_RE = re.compile("|".join(re.escape(p) for p in patterns), re.I)
    return cfg


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
        if cfg.get("structure") == "per_file":
            course = parse_course_per_file(course_dir, cfg, args)
        else:
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
