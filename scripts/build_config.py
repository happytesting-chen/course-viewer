#!/usr/bin/env python3
"""
Local dev helper — reads .env and writes docs/config.js.
Run this before opening the site locally.

Usage:
    python scripts/build_config.py
"""
from pathlib import Path

ROOT      = Path(__file__).resolve().parent.parent
ENV_FILE  = ROOT / ".env"
CONFIG_JS = ROOT / "docs" / "config.js"

def main():
    password = ""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("SITE_PASSWORD="):
                password = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    else:
        print(f"No .env file found at {ENV_FILE}")
        print("Copy .env.example to .env and set your password.")
        return

    CONFIG_JS.write_text(f"window.SITE_PASSWORD = '{password}';\n")
    print(f"Written: {CONFIG_JS}")

if __name__ == "__main__":
    main()
