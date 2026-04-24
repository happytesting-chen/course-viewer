#!/usr/bin/env python3
"""
Quick OCR sanity check — runs on a single page of one PDF.

Usage:
    python scripts/test_ocr.py
    python scripts/test_ocr.py --pdf pdfs/course2/01.Introduction.pdf --page 2
"""

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, default=None,
                        help="Path to a PDF file (default: first PDF found)")
    parser.add_argument("--page", type=int, default=1,
                        help="Page number to test (1-indexed, default: 1)")
    args = parser.parse_args()

    # Auto-pick first PDF if none specified
    pdf_path: Path = args.pdf
    if pdf_path is None:
        candidates = sorted((ROOT / "pdfs").rglob("*.pdf"))
        if not candidates:
            print("No PDFs found under pdfs/")
            return
        pdf_path = candidates[0]

    print(f"PDF  : {pdf_path}")
    print(f"Page : {args.page}")
    print("-" * 60)

    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError:
        print("Missing deps. Run: pip install pdf2image pytesseract")
        return

    images = convert_from_path(str(pdf_path), dpi=200,
                               first_page=args.page, last_page=args.page)
    if not images:
        print("Could not render page.")
        return

    text = pytesseract.image_to_string(images[0], lang="eng")
    print(text)
    print("-" * 60)
    print(f"Extracted {len(text)} characters, {len(text.splitlines())} lines")

if __name__ == "__main__":
    main()
