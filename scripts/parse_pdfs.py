#!/usr/bin/env python3
"""
PDF Course Parser
Reads PDFs from pdfs/course1/ and pdfs/course2/, detects headings via font size/bold,
and writes structured JSON to data/courses.json.

Falls back to OCR (tesseract) automatically for image-based PDFs.

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

# OCR deps — imported lazily so text-based PDFs don't require them
def _import_ocr():
    try:
        from pdf2image import convert_from_path
        import pytesseract
        return convert_from_path, pytesseract
    except ImportError:
        print(
            "OCR dependencies missing. Install with:\n"
            "  pip install pdf2image pytesseract\n"
            "  sudo apt-get install tesseract-ocr poppler-utils",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
PDFS_DIR = ROOT / "pdfs"
RAW_DIR  = ROOT / "raw"
OUTPUT_FILE = ROOT / "data" / "courses.json"

H1_MIN_SIZE = 16
H2_MIN_SIZE = 13
H3_MIN_SIZE = 11

STRIP_PATTERNS = [
    re.compile(r"^\s*\d+\s*$"),
    re.compile(r"^\s*page\s+\d+\s*(of\s+\d+)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*©.*$", re.IGNORECASE),
]

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
    size = span.get("size", 0)
    flags = span.get("flags", 0)
    is_bold = bool(flags & 2**4)
    if size >= H1_MIN_SIZE and is_bold:
        return "h1"
    if size >= H2_MIN_SIZE and is_bold:
        return "h2"
    if size >= H3_MIN_SIZE and is_bold:
        return "h3"
    return None


def clean_text(text: str) -> str:
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def has_text(doc) -> bool:
    """Return True if the PDF has meaningful extractable text (not just metadata/page numbers)."""
    total_chars = 0
    for i, page in enumerate(doc):
        total_chars += len(page.get_text().strip())
        if i >= 4:
            break
    # Require at least 300 chars across the first 5 pages to count as text-based
    return total_chars > 300


# ---------------------------------------------------------------------------
# OCR path
# ---------------------------------------------------------------------------

def raw_path_for(pdf_path: Path) -> Path:
    """Mirror pdfs/<course>/<name>.pdf → raw/<course>/<name>.txt"""
    rel = pdf_path.relative_to(PDFS_DIR)
    return RAW_DIR / rel.with_suffix(".txt")


def save_raw(text: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")


def ocr_pdf(pdf_path: Path, verbose: bool = False) -> list[dict]:
    """Convert each page to an image, run Tesseract OCR, save raw text, return blocks."""
    convert_from_path, pytesseract = _import_ocr()

    if verbose:
        print(f"  [OCR] {pdf_path.name}")

    images = convert_from_path(str(pdf_path), dpi=200)
    page_texts: list[str] = []

    for page_num, img in enumerate(images, start=1):
        page_texts.append(pytesseract.image_to_string(img, lang="eng"))
        if verbose:
            print(f"    page {page_num}/{len(images)} done", end="\r")

    if verbose:
        print()

    full_text = "\n\n--- PAGE BREAK ---\n\n".join(page_texts)

    # Save raw output so the user can review / edit it
    dest = raw_path_for(pdf_path)
    save_raw(full_text, dest)
    if verbose:
        print(f"  Raw text saved → {dest}")

    return _text_to_blocks(full_text)


def _text_to_blocks(text: str) -> list[dict]:
    """Convert a raw OCR string into body blocks, stripping page-break markers."""
    blocks: list[dict] = []
    # Remove page-break markers inserted during OCR
    text = re.sub(r"\n*--- PAGE BREAK ---\n*", "\n\n", text)

    paragraph_parts: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or is_noise_line(line):
            if paragraph_parts:
                para = " ".join(paragraph_parts).strip()
                if len(para) >= MIN_CONTENT_CHARS:
                    blocks.append({"level": "body", "text": para})
                paragraph_parts = []
        else:
            paragraph_parts.append(line)

    if paragraph_parts:
        para = " ".join(paragraph_parts).strip()
        if len(para) >= MIN_CONTENT_CHARS:
            blocks.append({"level": "body", "text": para})

    return blocks


# ---------------------------------------------------------------------------
# Native text path
# ---------------------------------------------------------------------------

def parse_pdf_native(pdf_path: Path, verbose: bool = False) -> list[dict]:
    doc = fitz.open(str(pdf_path))
    blocks: list[dict] = []

    if verbose:
        print(f"  [native] {pdf_path.name} ({len(doc)} pages)")

    for page in doc:
        raw_dict = page.get_text("dict")

        for block in raw_dict.get("blocks", []):
            if block.get("type") != 0:
                continue

            block_text_parts: list[str] = []

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
                    if block_text_parts:
                        body = clean_text("\n".join(block_text_parts))
                        if body:
                            blocks.append({"level": "body", "text": body})
                        block_text_parts = []
                    blocks.append({"level": line_level, "text": line_text})
                    if verbose:
                        print(f"    [{line_level.upper()}] {line_text[:80]}")
                else:
                    block_text_parts.append(line_text)

            if block_text_parts:
                body = clean_text("\n".join(block_text_parts))
                if body:
                    blocks.append({"level": "body", "text": body})

    doc.close()
    return blocks


def parse_pdf(pdf_path: Path, verbose: bool = False) -> list[dict]:
    """Auto-detect text vs image PDF and choose the right extraction path.

    If a raw/<course>/<stem>.txt already exists, use it directly (skips OCR).
    Edit that file to fix OCR mistakes, then re-run the parser without re-doing OCR.
    """
    raw = raw_path_for(pdf_path)

    if raw.exists():
        if verbose:
            print(f"  [raw cache] {pdf_path.name} → using {raw}")
        return _text_to_blocks(raw.read_text(encoding="utf-8"))

    doc = fitz.open(str(pdf_path))
    text_based = has_text(doc)
    doc.close()

    if text_based:
        return parse_pdf_native(pdf_path, verbose=verbose)

    if verbose:
        print(f"  No text layer in {pdf_path.name} — running OCR")
    return ocr_pdf(pdf_path, verbose=verbose)


# ---------------------------------------------------------------------------
# Block → chapter/section structure
# ---------------------------------------------------------------------------

def blocks_to_chapters(blocks: list[dict], verbose: bool = False) -> list[dict]:
    chapters: list[dict] = []
    current_chapter: dict | None = None
    current_section: dict | None = None

    heading_count = sum(1 for b in blocks if b["level"] in ("h1", "h2", "h3"))

    if heading_count == 0:
        if verbose:
            print("  No headings detected — grouping by paragraphs")
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
        if chapter["sections"]:
            chapters.append(chapter)
        return chapters

    def flush_section():
        nonlocal current_section
        if current_section and current_chapter is not None:
            parts = current_section.pop("_content_parts", [])
            current_section["content"] = clean_text("\n\n".join(parts))
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
        level, text = block["level"], block["text"]

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
    pdf_files = sorted(course_dir.glob("*.pdf"))
    if not pdf_files:
        if verbose:
            print(f"  No PDFs found in {course_dir}")
        return {"name": course_name, "chapters": []}

    all_chapters: list[dict] = []
    for pdf_path in pdf_files:
        blocks = parse_pdf(pdf_path, verbose=verbose)
        chapters = blocks_to_chapters(blocks, verbose=verbose)
        if len(pdf_files) > 1:
            for ch in chapters:
                ch["_source"] = pdf_path.stem
        all_chapters.extend(chapters)

    return {"name": course_name, "chapters": all_chapters}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    global RAW_DIR

    parser = argparse.ArgumentParser(description="Parse PDFs into courses.json")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--pdfs-dir", type=Path, default=PDFS_DIR)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR,
                        help="Directory for raw OCR text files")
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    parser.add_argument("--force-ocr", action="store_true",
                        help="Re-run OCR even if raw/*.txt files already exist")
    args = parser.parse_args()

    RAW_DIR = args.raw_dir

    if args.force_ocr:
        for f in RAW_DIR.rglob("*.txt"):
            f.unlink()
        if args.verbose:
            print("Cleared raw cache — will re-run OCR")

    if not args.pdfs_dir.exists():
        print(f"Error: PDFs directory not found: {args.pdfs_dir}", file=sys.stderr)
        sys.exit(1)

    course_dirs = [d for d in sorted(args.pdfs_dir.iterdir()) if d.is_dir()]
    if not course_dirs:
        print(f"No course subdirectories found in {args.pdfs_dir}.", file=sys.stderr)
        sys.exit(1)

    courses = []
    for course_dir in course_dirs:
        course_name = course_dir.name.replace("-", " ").replace("_", " ").title()
        if args.verbose:
            print(f"\nCourse: {course_name}")
        course = parse_course(course_dir, course_name, verbose=args.verbose)
        courses.append(course)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"courses": courses}, f, ensure_ascii=False, indent=2)

    total_chapters = sum(len(c["chapters"]) for c in courses)
    total_sections = sum(len(ch["sections"]) for c in courses for ch in c["chapters"])
    print(f"\nDone. {len(courses)} course(s), {total_chapters} chapter(s), "
          f"{total_sections} section(s) → {args.output}")


if __name__ == "__main__":
    main()
