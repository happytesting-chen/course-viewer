#!/usr/bin/env python3
"""
Summary Slide Generator
Renders a styled summary JPEG for each module and appends it as the last slide.

Static summaries are baked in below. To regenerate with Claude API instead,
add ANTHROPIC_API_KEY to .env and run with --ai flag.

Usage:
    python scripts/generate_summaries.py              # render static summaries
    python scripts/generate_summaries.py --course course1
    python scripts/generate_summaries.py --force      # re-render existing
    python scripts/generate_summaries.py --ai         # use Claude API
"""

import argparse
import json
import os
import re
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT      = Path(__file__).resolve().parent.parent
PDFS_DIR  = ROOT / "pdfs"
DOCS_DIR  = ROOT / "docs"
JSON_PATH = DOCS_DIR / "data" / "courses.json"

SLIDE_W, SLIDE_H = 1600, 900

BG_TOP   = (15,  23,  42)
BG_BODY  = (22,  33,  55)
ACCENT   = (59, 130, 246)
ACCENT2  = (96, 165, 250)
TEXT_HEAD = (255, 255, 255)
TEXT_BODY = (203, 213, 225)
TEXT_DIM  = (100, 116, 139)

FONT_BOLD   = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_NORMAL = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


# ── Static summaries ───────────────────────────────────────────────────────
# Format per module:
#   "overview":   one sentence
#   "topics":     list of bullet strings
#   "takeaways":  list of bullet strings

SUMMARIES = {

    # ── COURSE 2 ────────────────────────────────────────────────────────────

    "course2": {

        "mod1": {
            "overview": "Introduces the AI cybersecurity landscape, course structure, and the dual-use nature of AI in attack and defence.",
            "topics": [
                "AI adoption trends and the expanding attack surface",
                "Threat actors leveraging AI for offensive operations",
                "Defensive AI: anomaly detection, automated response",
                "Course roadmap: modules, labs, and learning outcomes",
                "Key terminology: LLMs, agents, prompt injection, red-teaming",
            ],
            "takeaways": [
                "Articulate why AI systems introduce fundamentally new security risks",
                "Navigate the course structure and set personal learning goals",
            ],
        },

        "mod2": {
            "overview": "Deep-dives into Large Language Model internals and the unique attack surface they create.",
            "topics": [
                "Transformer architecture: attention, tokens, context windows",
                "Training pipeline: pre-training, RLHF, fine-tuning",
                "Prompt injection: direct and indirect attack patterns",
                "Jailbreaking techniques: role-play, encoding, many-shot",
                "Hallucination exploitation and data poisoning risks",
                "Model extraction and membership-inference attacks",
            ],
            "takeaways": [
                "Explain how transformer internals enable specific attack classes",
                "Craft and detect prompt injection payloads in a test environment",
            ],
        },

        "mod3": {
            "overview": "Examines security risks across the AI supply chain from training data to third-party model dependencies.",
            "topics": [
                "AI supply chain components: data, models, APIs, plugins",
                "Training-data poisoning and backdoor insertion",
                "Malicious models on public hubs (HuggingFace, etc.)",
                "Dependency confusion and pickle-file exploits",
                "SBOM for AI: tracking model provenance and lineage",
                "Mitigation: sandboxing, signing, and model scanning",
            ],
            "takeaways": [
                "Map trust boundaries across an end-to-end AI pipeline",
                "Apply supply-chain hygiene controls to model acquisition",
            ],
        },

        "mod4": {
            "overview": "Applies structured threat modelling frameworks (STRIDE, PASTA, MITRE ATLAS) to AI systems.",
            "topics": [
                "MITRE ATLAS: tactics and techniques for ML adversaries",
                "STRIDE applied to LLM-powered applications",
                "Data-flow diagrams for AI pipelines",
                "Trust-boundary analysis: user, model, tool, data store",
                "Risk scoring and prioritisation for AI threats",
                "Threat model templates for chatbots, RAG, and agents",
            ],
            "takeaways": [
                "Produce a threat model for a given AI application architecture",
                "Map identified threats to MITRE ATLAS techniques",
            ],
        },

        "mod5": {
            "overview": "Covers AI governance frameworks, regulatory requirements, and organisational policies for responsible AI deployment.",
            "topics": [
                "EU AI Act: risk tiers, obligations, and enforcement",
                "NIST AI RMF: Govern, Map, Measure, Manage functions",
                "ISO/IEC 42001 AI management system standard",
                "Internal AI policy: acceptable use, review boards",
                "Bias, fairness, and explainability requirements",
                "Incident response and accountability for AI failures",
            ],
            "takeaways": [
                "Align an AI deployment to applicable regulatory requirements",
                "Draft an organisational AI acceptable-use policy skeleton",
            ],
        },

        "mod6": {
            "overview": "Analyses Model Context Protocol (MCP) as an attack surface and explores emerging security controls.",
            "topics": [
                "MCP architecture: host, client, server, and tool layers",
                "Tool-poisoning: malicious server tool definitions",
                "Prompt injection via MCP tool responses",
                "Cross-session data leakage through shared context",
                "Rug-pull attacks: tool behaviour changing post-approval",
                "Defensive controls: tool allowlisting, output validation",
            ],
            "takeaways": [
                "Identify MCP-specific attack vectors in agentic deployments",
                "Apply least-privilege principles to MCP tool configurations",
            ],
        },

        "mod7": {
            "overview": "Explores advanced prompt injection techniques including multi-turn, indirect, and encoding-based bypasses.",
            "topics": [
                "Multi-turn jailbreaks: building context across messages",
                "Indirect injection via documents, URLs, and tool outputs",
                "Encoding tricks: Base64, ROT13, Unicode homoglyphs",
                "Many-shot and few-shot persuasion patterns",
                "Automated red-teaming with PyRIT and Garak",
                "Detection strategies: input/output filtering, classifiers",
            ],
            "takeaways": [
                "Execute multi-vector prompt injection in a lab environment",
                "Design layered defences against advanced injection techniques",
            ],
        },

        "mod8": {
            "overview": "Second-day deep-dive covering practitioner labs, red-team exercises, and emerging offensive AI research.",
            "topics": [
                "Hands-on red-team scenario walkthroughs",
                "Agent exploitation labs: tool misuse and loop attacks",
                "Multi-modal attack surfaces (vision, audio, code)",
                "Live demonstration of automated attack pipelines",
                "Emerging research: adversarial suffixes, sleeper agents",
                "Blue-team response exercises and incident triage",
            ],
            "takeaways": [
                "Conduct a structured red-team engagement against an AI system",
                "Document findings in a reproducible security report",
            ],
        },

        "mod9": {
            "overview": "Introduces structured prompt engineering and context design to improve security and reliability of LLM outputs.",
            "topics": [
                "System prompt architecture: roles, constraints, personas",
                "Context window management and sensitive data handling",
                "Instruction hierarchy and conflict resolution",
                "Few-shot examples as security controls",
                "Output format enforcement and schema validation",
                "Testing prompts for robustness and adversarial inputs",
            ],
            "takeaways": [
                "Write system prompts that enforce security boundaries by design",
                "Systematically test prompt configurations for injection resilience",
            ],
        },

        "mod10": {
            "overview": "Reviews NCSC and international guidelines for building and deploying secure AI systems.",
            "topics": [
                "NCSC principles: secure design, development, deployment",
                "Secure-by-default configurations for AI services",
                "Access control, authentication, and API key management",
                "Logging, monitoring, and anomaly detection for AI",
                "Vulnerability disclosure and patching for AI components",
                "Red-team and penetration-test planning for AI systems",
            ],
            "takeaways": [
                "Apply NCSC secure-development guidelines to an AI project",
                "Build a monitoring baseline to detect AI-specific anomalies",
            ],
        },
    },

    # ── COURSE 1 ────────────────────────────────────────────────────────────

    "course1": {

        "mod0": {
            "overview": "Course logistics, lab environment setup, and an overview of the AI red-teaming training programme.",
            "topics": [
                "Training schedule and module breakdown",
                "Lab environment: Playground, Coding Labs, MCP Labs",
                "Discord channel for Q&A and collaboration",
                "Prerequisites: Python basics, API fundamentals",
                "Safety and responsible disclosure guidelines",
            ],
            "takeaways": [
                "Set up and verify access to all training lab environments",
                "Understand the scope and rules of engagement for the course",
            ],
        },

        "mod1": {
            "overview": "Welcomes participants, introduces the trainer and training structure, and sets the context for AI red-teaming.",
            "topics": [
                "Trainer background: Gary Lopez, AI security research",
                "AI for security vs. security of AI — two sides of the coin",
                "What is AI red-teaming and why it differs from classic pentesting",
                "Lab platform walkthrough: Playground and coding environments",
                "MCP Labs and Agent Labs overview",
                "Course communication and community channels",
            ],
            "takeaways": [
                "Distinguish AI red-teaming from traditional penetration testing",
                "Navigate all lab environments used throughout the course",
            ],
        },

        "mod2": {
            "overview": "Builds the ML and GenAI foundations needed to understand and exploit modern AI systems.",
            "topics": [
                "Supervised, unsupervised, and reinforcement learning",
                "Neural network fundamentals: layers, activations, loss",
                "Transformer architecture: self-attention and positional encoding",
                "Large language models: pre-training, fine-tuning, RLHF",
                "Embeddings, vector stores, and retrieval-augmented generation",
                "Model evaluation: benchmarks, perplexity, and red-team metrics",
            ],
            "takeaways": [
                "Explain transformer internals at a level useful for attack planning",
                "Identify which ML component is the target for a given attack class",
            ],
        },

        "mod3": {
            "overview": "Maps the adversarial ML landscape and introduces the GenAI-specific attack taxonomy.",
            "topics": [
                "From adversarial examples to LLM jailbreaks — the evolution",
                "Prompt injection: direct, indirect, and second-order",
                "Training-data extraction and membership inference",
                "Model inversion and model stealing attacks",
                "Evasion attacks on classifiers and safety filters",
                "MITRE ATLAS: mapping GenAI attacks to the framework",
            ],
            "takeaways": [
                "Categorise a novel attack technique using the MITRE ATLAS taxonomy",
                "Demonstrate a prompt injection exploit against a target LLM",
            ],
        },

        "mod4": {
            "overview": "Examines agentic AI architectures and the expanded attack surface they create through tool use and autonomy.",
            "topics": [
                "Agent anatomy: planner, memory, tools, and executor",
                "ReAct and chain-of-thought reasoning patterns",
                "Tool misuse: abusing function-calling and API access",
                "Multi-agent systems: trust delegation and message spoofing",
                "Case Study: OpenClaw — a real-world agentic exploitation",
                "Prompt injection into agent pipelines via external data",
            ],
            "takeaways": [
                "Identify exploitable trust relationships in a multi-agent architecture",
                "Execute a tool-misuse attack in the OpenClaw lab environment",
            ],
        },

        "mod5": {
            "overview": "Hands-on introduction to leading open-source AI red-teaming tools: AutoGen, Inspect AI, and PyRIT.",
            "topics": [
                "AutoGen: orchestrating multi-agent attack scenarios",
                "AutoGen Lab: building adversarial agent conversations",
                "Inspect AI: structured evaluation and benchmark attacks",
                "Inspect AI Evaluations: scoring model safety properties",
                "PyRIT: Python Risk Identification Toolkit for LLMs",
                "PyRIT Lab: automated jailbreak and injection pipelines",
            ],
            "takeaways": [
                "Build an automated red-team pipeline using PyRIT or AutoGen",
                "Produce a structured evaluation report with Inspect AI",
            ],
        },

        "mod6": {
            "overview": "Advanced attack techniques day-two content covering sophisticated exploitation of LLMs and agent systems.",
            "topics": [
                "Advanced jailbreaking: GCG adversarial suffixes",
                "Sleeper-agent attacks and hidden backdoors",
                "Cross-context injection in RAG pipelines",
                "Exploiting long-context windows and memory",
                "Chained attacks combining multiple techniques",
                "Real-world case studies from bug bounty and research",
            ],
            "takeaways": [
                "Chain multiple attack primitives into a realistic exploit scenario",
                "Identify sleeper-agent indicators in model behaviour",
            ],
        },

        "mod7": {
            "overview": "Explores attack and defence considerations unique to multi-modal models combining vision, audio, and text.",
            "topics": [
                "Evolution from text-only to multi-modal LLMs (GPT-4V, Gemini)",
                "Visual adversarial examples: imperceptible image perturbations",
                "Prompt injection via images, PDFs, and audio inputs",
                "OCR exploitation and document-based injection",
                "Audio jailbreaks and voice-cloning misuse",
                "Multi-modal safety benchmarks and evaluation",
            ],
            "takeaways": [
                "Craft an image-based prompt injection against a vision-language model",
                "Assess a multi-modal system for cross-modality attack paths",
            ],
        },

        "mod8": {
            "overview": "Frames AI red-teaming within Responsible AI principles and introduces a repeatable red-team process.",
            "topics": [
                "Responsible AI pillars: fairness, reliability, safety, privacy",
                "AI red-team charter: scope, rules, and ethics",
                "The AIRT process: plan → execute → document → remediate",
                "Findings classification: severity, exploitability, impact",
                "Communicating results to engineering and executive audiences",
                "Integrating AI red-teaming into the SDLC",
            ],
            "takeaways": [
                "Run an AI red-team engagement using the AIRT process framework",
                "Write a findings report aligned to responsible disclosure standards",
            ],
        },

        "mod9": {
            "overview": "Surveys defence-in-depth strategies and mitigations that reduce AI-specific attack risk.",
            "topics": [
                "Defence-in-depth for AI: layers from data to inference",
                "Input validation and prompt sanitisation techniques",
                "Output filtering: classifiers, blocklists, and schema checks",
                "Least-privilege for agents: minimal tool scope and access",
                "Monitoring and anomaly detection for LLM workloads",
                "Patch management and model versioning strategies",
            ],
            "takeaways": [
                "Design a layered defence architecture for an LLM-powered application",
                "Implement output validation controls to block common attack payloads",
            ],
        },

        "mod10": {
            "overview": "Looks at AI applications in scientific research and closes the course with open discussion on future directions.",
            "topics": [
                "AI x Science: drug discovery, climate, and materials science",
                "Unique security risks in scientific AI pipelines",
                "Dual-use research of concern (DURC) in AI",
                "Emerging threats: autonomous AI agents in the wild",
                "Open Q&A: participant scenarios and edge cases",
                "Resources for continued learning and community involvement",
            ],
            "takeaways": [
                "Recognise dual-use risks in AI-assisted scientific workflows",
                "Identify next steps for deepening AI security expertise",
            ],
        },
    },
}


# ── Font helpers ───────────────────────────────────────────────────────────

def load_font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


# ── Slide renderer ─────────────────────────────────────────────────────────

def render_summary_slide(mod_title: str, summary: dict, output_path: Path) -> None:
    img  = Image.new("RGB", (SLIDE_W, SLIDE_H), BG_TOP)
    draw = ImageDraw.Draw(img)

    f_label  = load_font(FONT_BOLD,   26)
    f_title  = load_font(FONT_BOLD,   36)
    f_sec    = load_font(FONT_BOLD,   22)
    f_body   = load_font(FONT_NORMAL, 21)
    f_foot   = load_font(FONT_NORMAL, 17)

    # Header bar
    draw.rectangle([0, 0, SLIDE_W, 105], fill=ACCENT)
    draw.text((44, 14), "MODULE SUMMARY", font=f_label, fill=(220, 235, 255))
    title = mod_title if len(mod_title) <= 62 else mod_title[:59] + "…"
    draw.text((44, 54), title, font=f_title, fill=TEXT_HEAD)

    # Body background
    draw.rectangle([0, 105, SLIDE_W, SLIDE_H], fill=BG_BODY)

    # Accent rule
    draw.rectangle([40, 118, SLIDE_W - 40, 121], fill=ACCENT)

    y = 136

    # Overview line
    overview = summary.get("overview", "")
    if overview:
        for wl in textwrap.wrap(overview, 100):
            draw.text((44, y), wl, font=f_body, fill=(180, 200, 230))
            y += 28
        y += 10

    # Topics
    topics = summary.get("topics", [])
    if topics:
        draw.text((44, y), "KEY TOPICS:", font=f_sec, fill=ACCENT2)
        y += 32
        for bullet in topics:
            if y > SLIDE_H - 110:
                break
            for i, wl in enumerate(textwrap.wrap("•  " + bullet, 88)):
                draw.text((56 if i == 0 else 72, y), wl, font=f_body, fill=TEXT_BODY)
                y += 27
        y += 8

    # Takeaways
    takeaways = summary.get("takeaways", [])
    if takeaways and y < SLIDE_H - 120:
        draw.text((44, y), "KEY TAKEAWAYS:", font=f_sec, fill=ACCENT2)
        y += 32
        for bullet in takeaways:
            if y > SLIDE_H - 70:
                break
            for i, wl in enumerate(textwrap.wrap("✓  " + bullet, 88)):
                draw.text((56 if i == 0 else 72, y), wl, font=f_body, fill=(160, 220, 160))
                y += 27

    # Footer
    draw.rectangle([0, SLIDE_H - 46, SLIDE_W, SLIDE_H], fill=(12, 18, 35))
    draw.text((44, SLIDE_H - 30), "Module Summary  •  Course Viewer",
              font=f_foot, fill=TEXT_DIM)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "JPEG", quality=90)


# ── AI summarisation (optional) ────────────────────────────────────────────

def get_api_key() -> str:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("ANTHROPIC_API_KEY", "")


def build_page_map(course_dir: Path) -> dict:
    import fitz
    page_map = {}
    idx = 0
    for pdf_path in sorted(course_dir.glob("*.pdf")):
        doc = fitz.open(str(pdf_path))
        for i in range(len(doc)):
            idx += 1
            page_map[idx] = (pdf_path, i)
        doc.close()
    return page_map


def extract_module_text(module: dict, page_map: dict) -> str:
    import fitz
    open_docs = {}
    parts = []
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
            t = open_docs[pdf_path][local_idx].get_text().strip()
            if t:
                parts.append(t)
    for doc in open_docs.values():
        doc.close()
    return "\n\n".join(parts)


def ai_summary_to_dict(mod_title: str, raw_text: str, client) -> dict:
    prompt = f"""Summarise this training module titled "{mod_title}" from its slide text.

Return ONLY a JSON object with these keys:
  "overview": one sentence (max 20 words)
  "topics": list of 5-7 strings, each max 12 words, specific and technical
  "takeaways": list of 2-3 strings, each starting with an action verb, max 15 words

Slide text:
{raw_text[:5000]}"""
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    import json as _json
    text = msg.content[0].text.strip()
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return _json.loads(text)


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", help="Only process this course (e.g. course1)")
    ap.add_argument("--force",  action="store_true", help="Re-render existing summaries")
    ap.add_argument("--ai",     action="store_true", help="Use Claude API (needs ANTHROPIC_API_KEY)")
    args = ap.parse_args()

    client = None
    if args.ai:
        key = get_api_key()
        if not key:
            print("--ai flag requires ANTHROPIC_API_KEY in .env"); sys.exit(1)
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        print("Claude API: connected")

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
        slide_dir = DOCS_DIR / "slides" / cid
        print(f"\n{'─'*60}\nCourse: {course['name']}")

        page_map = None
        if args.ai:
            course_dir = PDFS_DIR / cid
            if course_dir.exists():
                page_map = build_page_map(course_dir)

        for mod in course["modules"]:
            mod_id    = mod["id"]
            mod_title = mod["title"]
            img_name  = f"summary_{mod_id}.jpg"
            rel_path  = f"slides/{cid}/{img_name}"
            img_path  = slide_dir / img_name

            sum_sec = next((s for s in mod["sections"] if s.get("number") == "summary"), None)
            already = sum_sec is not None and sum_sec.get("slides")
            if already and not args.force:
                print(f"  [skip] {mod_id}: {mod_title}")
                continue

            # Get summary dict
            if args.ai and page_map:
                print(f"  [AI]   {mod_id}: {mod_title}")
                raw = extract_module_text(mod, page_map)
                try:
                    summary = ai_summary_to_dict(mod_title, raw, client)
                except Exception as e:
                    print(f"    API error: {e} — falling back to static")
                    summary = SUMMARIES.get(cid, {}).get(mod_id, {
                        "overview": f"Summary of {mod_title}",
                        "topics": [], "takeaways": []
                    })
            else:
                summary = SUMMARIES.get(cid, {}).get(mod_id, {
                    "overview": f"Summary of {mod_title}.",
                    "topics": [], "takeaways": []
                })
                print(f"  [static] {mod_id}: {mod_title}")

            render_summary_slide(mod_title, summary, img_path)
            print(f"    → {img_path.name}")

            # Create or update dedicated "📝 Summary" section (always last)
            if sum_sec:
                sum_sec["slides"] = [rel_path]
            else:
                mod["sections"].append({
                    "id":     f"{mod_id}_sum",
                    "number": "summary",
                    "title":  "📝 Summary",
                    "slides": [rel_path],
                })
            changed = True

    if changed:
        with open(JSON_PATH, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n✓ Updated {JSON_PATH}")
    else:
        print("\nNothing to update — use --force to re-render.")


if __name__ == "__main__":
    main()
