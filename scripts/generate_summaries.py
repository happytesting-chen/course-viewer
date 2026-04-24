#!/usr/bin/env python3
"""
Summary Slide Generator
For each module in courses.json, extracts slide text, calls Claude API
to generate a summary, renders it as a JPEG slide, and appends it to the module.

Requirements:
  pip install anthropic pillow PyMuPDF
  ANTHROPIC_API_KEY must be set in .env

Usage:
    python scripts/generate_summaries.py
    python scripts/generate_summaries.py --course course1
    python scripts/generate_summaries.py --force   # regenerate existing summaries
"""

import argparse
import json
import os
import re
import sys
import textwrap
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont

ROOT     = Path(__file__).resolve().parent.parent
PDFS_DIR = ROOT / "pdfs"
DOCS_DIR = ROOT / "docs"
JSON_PATH = DOCS_DIR / "data" / "courses.json"

# Slide canvas size (matches 150 DPI render of a 16:9 PDF page)
SLIDE_W, SLIDE_H = 1600, 900

# Colours
BG_TOP    = (15,  23,  42)   # #0f172a  dark navy
BG_BODY   = (22,  33,  55)   # #162137  slightly lighter
ACCENT    = (59, 130, 246)   # #3b82f6  blue
ACCENT2   = (96, 165, 250)   # #60a5fa  lighter blue
TEXT_HEAD = (255, 255, 255)
TEXT_BODY = (203, 213, 225)  # #cbd5e1
TEXT_DIM  = (100, 116, 139)  # #64748b

FONT_BOLD   = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_NORMAL = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


# ── Font loader ────────────────────────────────────────────────────────────

def load_font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


# ── Env / API key ──────────────────────────────────────────────────────────

def get_api_key() -> str:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("ANTHROPIC_API_KEY", "")


# ── Page map: global slide number → (pdf_path, local page index) ───────────

def build_page_map(course_dir: Path) -> dict[int, tuple[Path, int]]:
    page_map: dict[int, tuple[Path, int]] = {}
    idx = 0
    for pdf_path in sorted(course_dir.glob("*.pdf")):
        doc = fitz.open(str(pdf_path))
        for i in range(len(doc)):
            idx += 1
            page_map[idx] = (pdf_path, i)
        doc.close()
    return page_map


# ── Text extraction ────────────────────────────────────────────────────────

def extract_module_text(module: dict, page_map: dict) -> str:
    """Pull raw text from every PDF page that belongs to this module."""
    open_docs: dict[Path, fitz.Document] = {}
    parts: list[str] = []

    for section in module.get("sections", []):
        for slide_rel in section.get("slides", []):
            m = re.search(r'page_(\d+)\.jpg', slide_rel)
            if not m:
                continue
            gidx = int(m.group(1))
            if gidx not in page_map:
                continue
            pdf_path, local_idx = page_map[gidx]
            if pdf_path not in open_docs:
                open_docs[pdf_path] = fitz.open(str(pdf_path))
            page_text = open_docs[pdf_path][local_idx].get_text().strip()
            if page_text:
                parts.append(page_text)

    for doc in open_docs.values():
        doc.close()

    return "\n\n".join(parts)


# ── Claude summarisation ───────────────────────────────────────────────────

def summarise_with_claude(module_title: str, raw_text: str, client) -> str:
    """Ask Claude to produce a structured module summary."""
    if not raw_text.strip():
        return "• No extractable text found on these slides."

    prompt = f"""You are summarising a training course module titled "{module_title}".

Below is text extracted from the slides. Write a concise module summary with:
1. A one-sentence overview (what this module is about)
2. KEY TOPICS: 5–8 bullet points of the main concepts/techniques covered
3. KEY TAKEAWAYS: 2–3 practical things the learner can do after this module

Rules:
- Be specific — mention tools, techniques, or concepts by name if they appear in the text
- Each bullet point max 15 words
- No fluff, no repetition
- Output plain text only, no markdown headers (use ALL CAPS for section labels)

--- SLIDE TEXT ---
{raw_text[:6000]}
"""
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


# ── Fallback: extract headings when API key not available ──────────────────

def summarise_headings(raw_text: str) -> str:
    lines = []
    for line in raw_text.splitlines():
        line = line.strip()
        if 5 < len(line) < 80 and not re.match(r'^\d+$', line):
            lines.append(line)
    unique = list(dict.fromkeys(lines))[:12]
    if not unique:
        return "• No extractable text found on these slides."
    return "KEY TOPICS:\n" + "\n".join(f"• {l}" for l in unique[:10])


# ── Slide rendering ────────────────────────────────────────────────────────

def draw_wrapped(draw, text: str, x: int, y: int, max_w: int,
                 font, fill, line_h: int) -> int:
    """Draw wrapped text; return final y position."""
    for line in text.split("\n"):
        wrapped = textwrap.wrap(line, width=max(10, max_w // (font.size // 2 + 3)))
        if not wrapped:
            y += line_h // 2
            continue
        for wl in wrapped:
            draw.text((x, y), wl, font=font, fill=fill)
            y += line_h
    return y


def render_summary_slide(module_title: str, summary_text: str,
                         output_path: Path) -> None:
    img  = Image.new("RGB", (SLIDE_W, SLIDE_H), BG_TOP)
    draw = ImageDraw.Draw(img)

    # ── Header bar ────────────────────────────────────────────────────────
    bar_h = 100
    draw.rectangle([0, 0, SLIDE_W, bar_h], fill=ACCENT)

    # "SUMMARY" badge
    f_badge = load_font(FONT_BOLD, 28)
    draw.text((44, 18), "MODULE SUMMARY", font=f_badge, fill=(255, 255, 255))

    # Module title in header
    f_title = load_font(FONT_BOLD, 34)
    title_text = module_title if len(module_title) <= 60 else module_title[:57] + "…"
    draw.text((44, 54), title_text, font=f_title, fill=(224, 236, 255))

    # ── Body background ────────────────────────────────────────────────────
    draw.rectangle([0, bar_h, SLIDE_W, SLIDE_H], fill=BG_BODY)

    # ── Divider line ───────────────────────────────────────────────────────
    draw.rectangle([40, bar_h + 20, SLIDE_W - 40, bar_h + 23], fill=ACCENT)

    # ── Summary text ───────────────────────────────────────────────────────
    f_section = load_font(FONT_BOLD,   22)
    f_body    = load_font(FONT_NORMAL, 21)

    y = bar_h + 44
    max_x = SLIDE_W - 80

    for line in summary_text.split("\n"):
        if y > SLIDE_H - 50:
            break
        line = line.rstrip()
        if not line:
            y += 14
            continue

        # Section labels in ALL CAPS ending with ":"
        if re.match(r'^[A-Z\s]{4,}:$', line):
            draw.text((44, y), line, font=f_section, fill=ACCENT2)
            y += 32
        elif line.startswith("•") or line.startswith("-"):
            bullet = "•  " + line.lstrip("•- ").strip()
            wrapped = textwrap.wrap(bullet, width=90)
            for i, wl in enumerate(wrapped):
                indent = 44 if i == 0 else 60
                draw.text((indent, y), wl, font=f_body, fill=TEXT_BODY)
                y += 28
            y += 4
        else:
            wrapped = textwrap.wrap(line, width=90)
            for wl in wrapped:
                draw.text((44, y), wl, font=f_body, fill=TEXT_BODY)
                y += 28
            y += 4

    # ── Footer ────────────────────────────────────────────────────────────
    f_foot = load_font(FONT_NORMAL, 18)
    draw.text((44, SLIDE_H - 36), "Generated Summary Slide",
              font=f_foot, fill=TEXT_DIM)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "JPEG", quality=88)


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Generate summary slides per module")
    ap.add_argument("--course", help="Only process this course (e.g. course1)")
    ap.add_argument("--force",  action="store_true",
                    help="Regenerate even if summary slide already exists")
    args = ap.parse_args()

    # API client (optional — falls back to heading extraction)
    api_key = get_api_key()
    client  = None
    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            print("Claude API: connected")
        except ImportError:
            print("anthropic package not found — using heading fallback")
    else:
        print("No ANTHROPIC_API_KEY found — using heading extraction fallback")

    with open(JSON_PATH) as f:
        data = json.load(f)

    courses = data["courses"]
    if args.course:
        courses = [c for c in courses if c["id"] == args.course]
        if not courses:
            print(f"Course '{args.course}' not found"); sys.exit(1)

    changed = False

    for course in courses:
        cid       = course["id"]
        course_dir = PDFS_DIR / cid
        slide_dir  = DOCS_DIR / "slides" / cid

        if not course_dir.exists():
            print(f"  Skipping {cid} — no PDFs dir"); continue

        print(f"\n{'─'*60}")
        print(f"Course: {course['name']}")
        page_map = build_page_map(course_dir)

        for mod in course["modules"]:
            mod_title  = mod["title"]
            summary_id = f"summary_{mod['id']}"
            img_name   = f"summary_{mod['id']}.jpg"
            rel_path   = f"slides/{cid}/{img_name}"
            img_path   = slide_dir / img_name

            # Check if already generated
            already_has = any(
                rel_path in s.get("slides", [])
                for s in mod["sections"]
            )
            if already_has and not args.force:
                print(f"  [skip] Module {mod['number']}: {mod_title} (already has summary)")
                continue

            print(f"  Module {mod['number']}: {mod_title}")

            # Extract text
            raw = extract_module_text(mod, page_map)
            print(f"    Extracted {len(raw)} chars of text")

            # Summarise
            if client:
                print("    Calling Claude API…")
                try:
                    summary = summarise_with_claude(mod_title, raw, client)
                except Exception as e:
                    print(f"    API error: {e} — using fallback")
                    summary = summarise_headings(raw)
            else:
                summary = summarise_headings(raw)

            # Render slide
            render_summary_slide(mod_title, summary, img_path)
            print(f"    Slide saved → {img_path.name}")

            # Append to last section (or dedicated summary section)
            last_sec = mod["sections"][-1] if mod["sections"] else None
            if last_sec:
                # Remove previous summary slide if regenerating
                last_sec["slides"] = [
                    s for s in last_sec["slides"] if "summary_" not in s
                ]
                last_sec["slides"].append(rel_path)
            changed = True

    if changed:
        with open(JSON_PATH, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\nUpdated {JSON_PATH}")
    else:
        print("\nNothing to update.")


if __name__ == "__main__":
    main()
