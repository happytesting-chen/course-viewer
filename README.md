# Course Viewer

A static documentation website generated from PDF course files.
No frameworks, no build step — just open `site/index.html` in a browser.

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Add your PDFs

Place PDF files in the correct course folders:

```
pdfs/
├── course1/   ← PDFs for Course 1
└── course2/   ← PDFs for Course 2
```

Rename the folders to anything you like — the folder name becomes the course title.

### 3. Parse PDFs

```bash
python scripts/parse_pdfs.py
```

Add `--verbose` to see heading detection output:

```bash
python scripts/parse_pdfs.py --verbose
```

This writes `data/courses.json`.

### 4. View the site

Open `site/index.html` in any browser. No server required.

> **Note:** Some browsers block `fetch()` for local files. If the page shows
> "courses.json not found", serve the project with a simple HTTP server:
>
> ```bash
> python -m http.server 8000
> # then open http://localhost:8000/site/
> ```

## Adding a new course

1. Create a new folder under `pdfs/`, e.g. `pdfs/course3/`
2. Drop your PDFs in
3. Re-run `python scripts/parse_pdfs.py`
4. Refresh the browser

## Adding a new PDF to an existing course

Drop the PDF into the relevant course folder and re-run the parser.

## Parser options

| Flag | Description |
|---|---|
| `--verbose` | Print detected headings and page count |
| `--pdfs-dir PATH` | Override the PDFs root directory |
| `--output PATH` | Override the output JSON path |

## Heading detection

The parser uses **PyMuPDF** to inspect font size and bold weight per span:

| Level | Condition |
|---|---|
| H1 | size ≥ 16 pt **and** bold |
| H2 | size ≥ 13 pt **and** bold |
| H3 | size ≥ 11 pt **and** bold |

If no headings are detected in a PDF, the parser falls back to grouping content by paragraphs.

## Project structure

```
course-viewer/
├── pdfs/                 # Your PDFs go here (git-ignored)
│   ├── course1/
│   └── course2/
├── scripts/
│   └── parse_pdfs.py     # PDF parser
├── data/
│   └── courses.json      # Parsed output (committed)
├── site/
│   ├── index.html        # Static site
│   ├── style.css
│   └── app.js
├── requirements.txt
├── README.md
└── .gitignore
```
