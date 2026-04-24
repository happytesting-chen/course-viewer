#!/usr/bin/env python3
"""
PDF Course Parser
Reads PDFs from pdfs/course1/ and pdfs/course2/, detects headings via font size/bold,
and writes structured JSON to data/courses.json.

Usage:
    python scripts/parse_pdfs.py
    python scripts/parse_pdfs.py --verbose
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF not found. Install with: pip install PyMuPDF", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
PDFS_DIR = ROOT / "pdfs"
OUTPUT_FILE = ROOT / "data" / "courses.json"

# Font-size thresholds for heading detection (points)
H1_MIN_SIZE = 16
H2_MIN_SIZE = 13
H3_MIN_SIZE = 11

# Patterns to strip (page numbers, headers/footers, etc.)
STRIP_PATTERNS = [
    re.compile(r"^\s*\d+\s*$"),                      # bare page numbers
    re.compile(r"^\s*page\s+\d+\s*(of\s+\d+)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*©.*$", re.IGNORECASE),           # copyright lines
]

# Minimum content length to be considered a real section (chars)
MIN_CONTENT_CHARS = 20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_noise_line(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    for pat in STRIP_PATTERNS:
        if pat.match(t):
            return True
    return False


def classify_span(span: dict) -> str | None:
    """Return 'h1', 'h2', 'h3', or None based on font properties."""
    size = span.get("size", 0)
    flags = span.get("flags", 0)
    is_bold = bool(flags & 2**4)  # bit 4 = bold in PyMuPDF

    if size >= H1_MIN_SIZE and is_bold:
        return "h1"
    if size >= H2_MIN_SIZE and is_bold:
        return "h2"
    if size >= H3_MIN_SIZE and is_bold:
        return "h3"
    return None


def clean_text(text: str) -> str:
    # Collapse excessive whitespace but preserve paragraph breaks
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------

def parse_pdf(pdf_path: Path, verbose: bool = False) -> list[dict]:
    """
    Parse a single PDF and return a flat list of blocks:
        {"level": "h1"|"h2"|"h3"|"body", "text": "..."}
    """
    doc = fitz.open(str(pdf_path))
    blocks: list[dict] = []

    if verbose:
        print(f"  Parsing: {pdf_path.name} ({len(doc)} pages)")

    for page_num, page in enumerate(doc, start=1):
        raw_dict = page.get_text("rawdict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        for block in raw_dict.get("blocks", []):
            if block.get("type") != 0:  # 0 = text block
                continue

            block_level = None
            block_text_parts = []

            for line in block.get("lines", []):
                line_text = ""
                line_level = None

                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    if not span_text.strip():
                        continue

                    level = classify_span(span)
                    if level and line_level is None:
                        line_level = level

                    line_text += span_text

                line_text = line_text.strip()
                if not line_text or is_noise_line(line_text):
                    continue

                if line_level:
                    # Flush accumulated body text before this heading line
                    if block_text_parts and block_level is None:
                        body = clean_text("\n".join(block_text_parts))
                        if body:
                            blocks.append({"level": "body", "text": body})
                        block_text_parts = []
                    # Emit heading immediately
                    blocks.append({"level": line_level, "text": line_text})
                    if verbose:
                        print(f"    [{line_level.upper()}] {line_text[:80]}")
                else:
                    block_text_parts.append(line_text)

            # Flush remaining body text
            if block_text_parts:
                body = clean_text("\n".join(block_text_parts))
                if body:
                    blocks.append({"level": "body", "text": body})

    doc.close()
    return blocks


def blocks_to_chapters(blocks: list[dict], verbose: bool = False) -> list[dict]:
    """
    Convert flat block list into nested chapter/section structure.
    Strategy:
      h1 → new chapter
      h2 → new section within current chapter
      h3 → sub-heading prepended to section content
      body → appended to current section content
    Falls back to page-based splitting if no headings are detected.
    """
    chapters: list[dict] = []
    current_chapter: dict | None = None
    current_section: dict | None = None

    heading_count = sum(1 for b in blocks if b["level"] in ("h1", "h2", "h3"))

    if heading_count == 0:
        if verbose:
            print("  No headings detected — falling back to paragraph grouping")
        # Group every ~5 body blocks as one section under a single chapter
        chapter = {"title": "Content", "sections": []}
        body_parts: list[str] = []
        section_idx = 1
        for i, block in enumerate(blocks):
            body_parts.append(block["text"])
            if (i + 1) % 10 == 0 or i == len(blocks) - 1:
                if body_parts:
                    chapter["sections"].append({
                        "heading": f"Part {section_idx}",
                        "content": "\n\n".join(body_parts)
                    })
                    section_idx += 1
                    body_parts = []
        chapters.append(chapter)
        return chapters

    def flush_section():
        nonlocal current_section
        if current_section and current_chapter is not None:
            content = current_section.get("_content_parts", [])
            current_section["content"] = clean_text("\n\n".join(content))
            del current_section["_content_parts"]
            current_chapter["sections"].append(current_section)
        current_section = None

    def flush_chapter():
        nonlocal current_chapter
        flush_section()
        if current_chapter is not None:
            if not current_chapter["sections"]:
                current_chapter["sections"].append({
                    "heading": current_chapter["title"],
                    "content": ""
                })
            chapters.append(current_chapter)
        current_chapter = None

    for block in blocks:
        level = block["level"]
        text = block["text"]

        if level == "h1":
            flush_chapter()
            current_chapter = {"title": text, "sections": []}

        elif level == "h2":
            if current_chapter is None:
                current_chapter = {"title": "Introduction", "sections": []}
            flush_section()
            current_section = {"heading": text, "_content_parts": []}

        elif level == "h3":
            if current_chapter is None:
                current_chapter = {"title": "Introduction", "sections": []}
            if current_section is None:
                current_section = {"heading": text, "_content_parts": []}
            else:
                # Treat h3 as bold sub-heading in body
                current_section["_content_parts"].append(f"**{text}**")

        elif level == "body":
            if current_chapter is None:
                current_chapter = {"title": "Introduction", "sections": []}
            if current_section is None:
                current_section = {"heading": "Overview", "_content_parts": []}
            if len(text) >= MIN_CONTENT_CHARS:
                current_section["_content_parts"].append(text)

    flush_chapter()
    return chapters


def parse_course(course_dir: Path, course_name: str, verbose: bool = False) -> dict:
    """Parse all PDFs in a course directory into a course object."""
    pdf_files = sorted(course_dir.glob("*.pdf"))
    if not pdf_files:
        if verbose:
            print(f"  No PDFs found in {course_dir}")
        return {"name": course_name, "chapters": []}

    all_chapters: list[dict] = []
    for pdf_path in pdf_files:
        blocks = parse_pdf(pdf_path, verbose=verbose)
        chapters = blocks_to_chapters(blocks, verbose=verbose)
        # Prefix chapter titles with the PDF filename if multiple PDFs
        if len(pdf_files) > 1:
            stem = pdf_path.stem
            for ch in chapters:
                ch["_source"] = stem
        all_chapters.extend(chapters)

    return {"name": course_name, "chapters": all_chapters}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Parse PDFs into courses.json")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print detected headings and debug info")
    parser.add_argument("--pdfs-dir", type=Path, default=PDFS_DIR,
                        help=f"Root PDFs directory (default: {PDFS_DIR})")
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE,
                        help=f"Output JSON path (default: {OUTPUT_FILE})")
    args = parser.parse_args()

    pdfs_root: Path = args.pdfs_dir
    output: Path = args.output

    if not pdfs_root.exists():
        print(f"Error: PDFs directory not found: {pdfs_root}", file=sys.stderr)
        sys.exit(1)

    # Discover course folders (any subdirectory of pdfs/)
    course_dirs = [d for d in sorted(pdfs_root.iterdir()) if d.is_dir()]
    if not course_dirs:
        print(f"No course subdirectories found in {pdfs_root}.", file=sys.stderr)
        print("Create pdfs/course1/ and pdfs/course2/ and place PDFs inside.", file=sys.stderr)
        sys.exit(1)

    courses = []
    for course_dir in course_dirs:
        course_name = course_dir.name.replace("-", " ").replace("_", " ").title()
        if args.verbose:
            print(f"\nCourse: {course_name} ({course_dir})")
        course = parse_course(course_dir, course_name, verbose=args.verbose)
        courses.append(course)

    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"courses": courses}
    with open(output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    total_chapters = sum(len(c["chapters"]) for c in courses)
    total_sections = sum(
        len(ch["sections"])
        for c in courses
        for ch in c["chapters"]
    )
    print(f"\nDone. {len(courses)} course(s), {total_chapters} chapter(s), "
          f"{total_sections} section(s) → {output}")


if __name__ == "__main__":
    main()
