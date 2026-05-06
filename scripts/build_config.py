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
    password   = ""
    hint       = ""
    admin_email = ""
    proxy_url  = ""
    proxy_token = ""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("SITE_PASSWORD="):
                password = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("SITE_HINT="):
                hint = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("ADMIN_EMAIL="):
                admin_email = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("PROXY_URL="):
                proxy_url = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("PROXY_AUTH_TOKEN="):
                proxy_token = line.split("=", 1)[1].strip().strip('"').strip("'")
    else:
        print(f"No .env file found at {ENV_FILE}")
        print("Copy .env.example to .env and set your password.")
        return

    CONFIG_JS.write_text(
        f"window.SITE_PASSWORD    = '{password}';\n"
        f"window.SITE_HINT        = '{hint}';\n"
        f"window.ADMIN_EMAIL      = '{admin_email}';\n"
        f"window.PROXY_URL        = '{proxy_url}';\n"
        f"window.PROXY_AUTH_TOKEN = '{proxy_token}';\n"
    )
    print(f"Written: {CONFIG_JS}")

if __name__ == "__main__":
    main()
