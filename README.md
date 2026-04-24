# Course Viewer

A private static slide viewer hosted on GitHub Pages.
Each course is organized by module and section with a sidebar, fullscreen viewer, and keyboard navigation.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Add PDFs

Place PDFs in the correct course folders (git-ignored):

```
pdfs/
├── course1/
│   ├── config.yaml   ← course settings + footer_patterns
│   └── *.pdf
└── course2/
    ├── config.yaml
    └── *.pdf
```

### 3. Parse slides

```bash
python scripts/parse_slides.py --course course1 --verbose
```

This converts each PDF page to a JPEG and writes `docs/data/courses.json`.

### 4. Preview locally

```bash
python scripts/build_config.py   # generates docs/config.js from .env
python -m http.server 8000
# open http://localhost:8000/docs/
```

### 5. Deploy

```bash
git add docs/ && git commit -m "update slides" && git push
```

GitHub Actions injects the password from the `SITE_PASSWORD` secret and deploys to Pages.

## Changing the password

1. Go to repo → Settings → Secrets → Actions
2. Update `SITE_PASSWORD`
3. Re-run the Deploy workflow (or push any commit)

## Parser options

| Flag | Description |
|---|---|
| `--verbose` | Show detected modules and sections |
| `--course NAME` | Process one course only |
| `--dpi N` | Render DPI (default 150) |
| `--quality N` | JPEG quality 1–95 (default 85) |

## Project structure

```
course-viewer/
├── pdfs/                    # Local only — git-ignored
│   ├── course1/
│   │   ├── config.yaml
│   │   └── *.pdf
│   └── course2/
├── scripts/
│   ├── parse_slides.py      # PDF → JPEG + JSON
│   └── build_config.py      # Injects password for local dev
├── docs/                    # GitHub Pages root
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   ├── data/courses.json
│   └── slides/
│       ├── course1/
│       └── course2/
├── .github/workflows/
│   └── deploy.yml           # CI: inject password + deploy Pages
├── .env                     # Local only — git-ignored
├── .env.example
└── .gitignore
```
