#!/usr/bin/env python3
"""
Generates an overall course summary for each course using Claude.
Reads the module overviews already stored in courses.json and asks Claude
to synthesise them into one cohesive paragraph, written back as courses[].summary.

Usage:
    python scripts/generate_course_summary.py

Requires ANTHROPIC_API_KEY in .env (or set as an environment variable).
"""

import json
import os
from pathlib import Path

import anthropic

ROOT      = Path(__file__).resolve().parent.parent
ENV_FILE  = ROOT / ".env"
JSON_PATH = ROOT / "docs" / "data" / "courses.json"


def get_api_key() -> str:
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("ANTHROPIC_API_KEY", "")


def generate_summary(client: anthropic.Anthropic, course_name: str, overviews: list[str]) -> str:
    bullet_list = "\n".join(f"- {ov}" for ov in overviews)
    prompt = (
        f'You are writing the overall summary for a training course titled "{course_name}".\n\n'
        f"Below are the one-sentence summaries of each module in the course:\n{bullet_list}\n\n"
        "Write a single cohesive paragraph (3-5 sentences) that summarises what the entire "
        "course covers. Write in third person. Be specific and technical. "
        "Do not use bullet points or a heading. Output only the paragraph text."
    )
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=350,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def main():
    key = get_api_key()
    if not key:
        print("Error: ANTHROPIC_API_KEY not found.")
        print("Add it to .env:  ANTHROPIC_API_KEY=sk-ant-...")
        return

    client = anthropic.Anthropic(api_key=key)

    with open(JSON_PATH) as f:
        data = json.load(f)

    for course in data["courses"]:
        overviews = [m["overview"] for m in course["modules"] if m.get("overview")]
        if not overviews:
            print(f"[skip] {course['name']} — no module overviews found")
            continue

        print(f"Generating summary for: {course['name']} ({len(overviews)} modules)...")
        summary = generate_summary(client, course["name"], overviews)
        course["summary"] = summary
        print(f"  {summary}\n")

    with open(JSON_PATH, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Done. Updated {JSON_PATH}")


if __name__ == "__main__":
    main()
