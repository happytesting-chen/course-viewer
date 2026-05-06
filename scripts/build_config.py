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
    hint = ""
    admin_email = ""
    api_key = ""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("SITE_PASSWORD="):
                password = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("SITE_HINT="):
                hint = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("ADMIN_EMAIL="):
                admin_email = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("ANTHROPIC_API_KEY="):
                api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
    else:
        print(f"No .env file found at {ENV_FILE}")
        print("Copy .env.example to .env and set your password.")
        return

    CONFIG_JS.write_text(
        f"window.SITE_PASSWORD     = '{password}';\n"
        f"window.SITE_HINT         = '{hint}';\n"
        f"window.ADMIN_EMAIL       = '{admin_email}';\n"
        f"window.ANTHROPIC_API_KEY = '{api_key}';\n"
    )
    print(f"Written: {CONFIG_JS}")

if __name__ == "__main__":
    main()
