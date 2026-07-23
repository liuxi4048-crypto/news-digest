"""
Convert generated digests into Obsidian-native notes, organised by category.

Reads `digests/*.md` (produced by generate_digest.py) and writes one note per
topic under `obsidian/AI News/<カテゴリ>/`, plus an `_AI News MOC.md` index.
Categories mirror the digest sections (AI / SaaS・ツール / IT全般); the date
survives only as a filename prefix so notes sort chronologically *inside* a
category. This matches the vault rule "manage by information, not by date"
(2026-07-23 user decision).

Pure stdlib and idempotent: safe to re-run over the whole history at any time.
No API keys required, so this also runs fine on a laptop with no secrets.

Usage:
    python scripts/export_obsidian.py            # all digests
    python scripts/export_obsidian.py 2026-07-20 # a single date
"""
import hashlib
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIGESTS_DIR = os.path.join(REPO_ROOT, "digests")
OBSIDIAN_DIR = os.path.join(REPO_ROOT, "obsidian", "AI News")
MOC_NAME = "_AI News MOC"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Entities worth turning into graph nodes. Matched case-insensitively against
# whole words so "Meta" does not fire on "metadata" and "AI" not on "said".
ENTITIES = [
    "OpenAI", "Anthropic", "Google", "DeepMind", "Meta", "Microsoft", "Apple",
    "Amazon", "AWS", "NVIDIA", "Mistral", "Hugging Face", "Alibaba", "Qwen",
    "DeepSeek", "Moonshot", "xAI", "Perplexity", "Stability AI", "Cohere",
    "ChatGPT", "Claude", "Gemini", "Llama", "Grok", "Copilot", "Sora",
]
ENTITY_RES = [
    (name, re.compile(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", re.I))
    for name in ENTITIES
]

# Digest section heading -> (folder name, tag)
CATEGORIES = {
    "🤖 AI": ("AI", "ai"),
    "☁️ SaaS・ツール": ("SaaS・ツール", "saas"),
    "💻 IT全般": ("IT全般", "it"),
}
FALLBACK_CATEGORY = ("その他", "misc")


def parse_digest(text):
    """Parse a digest markdown file into a structured dict."""
    result = {"date": None, "sections": []}

    m = re.search(r"^# Daily Digest — (\d{4}-\d{2}-\d{2})", text, re.M)
    if m:
        result["date"] = m.group(1)

    # Split off the trailing feed-inventory section; it is provenance noise in
    # a note you actually read, and it is identical every day.
    body = re.split(r"^## 📡 ", text, maxsplit=1, flags=re.M)[0]

    for chunk in re.split(r"^## ", body, flags=re.M)[1:]:
        lines = chunk.split("\n")
        heading = lines[0].strip()
        section = {"heading": heading, "topics": []}
        for tchunk in re.split(r"^### ", "\n".join(lines[1:]), flags=re.M)[1:]:
            section["topics"].append(parse_topic(tchunk))
        if section["topics"]:
            result["sections"].append(section)
    return result


def parse_topic(chunk):
    lines = chunk.split("\n")
    title = re.sub(r"^\d+\.\s*", "", lines[0].strip())

    badge = ""
    summary_lines, sources = [], []
    in_sources = False
    for line in lines[1:]:
        m = re.match(r"^\*\*ソース(?:（(.*?)）)?:?\*\*", line.strip())
        if m:
            badge = m.group(1) or ""
            in_sources = True
            continue
        if in_sources:
            sm = re.match(r"^- \[(.*?)\]\((.*?)\)\s*—\s*(.*)$", line.strip())
            if sm:
                sources.append({
                    "title": sm.group(1), "url": sm.group(2),
                    "domain": sm.group(3).strip(),
                })
        elif line.strip():
            summary_lines.append(line.strip())

    return {
        "title": title,
        "summary": " ".join(summary_lines),
        "badge": badge,
        "sources": sources,
    }


def find_entities(text):
    return [name for name, rx in ENTITY_RES if rx.search(text)]


def yaml_escape(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def note_basename(date, title):
    """Stable, filesystem/Obsidian-safe basename: date prefix + title + hash."""
    clean = re.sub(r'[\\/:*?"<>|#^\[\]]', "", title)
    clean = re.sub(r"\s+", " ", clean).strip()[:48].rstrip()
    digest = hashlib.md5(title.encode("utf-8")).hexdigest()[:4]
    return f"{date} {clean} {digest}"


def build_topic_note(date, heading, topic):
    folder, tag = CATEGORIES.get(heading, FALLBACK_CATEGORY)
    entities = find_entities(topic["title"] + " " + topic["summary"])
    corroborated = "裏取り" in topic["badge"]

    fm = [
        "---",
        f"title: {yaml_escape(topic['title'])}",
        f"date: {date}",
        "type: news-topic",
        "source: news-digest",
        f"category: {yaml_escape(folder)}",
        "tags:",
        "  - ai-news",
        f"  - {tag}",
        f"corroborated: {'true' if corroborated else 'false'}",
    ]
    if entities:
        fm.append("entities:")
        fm.extend(f"  - {yaml_escape(e)}" for e in entities)
    fm.append("---")

    out = fm + ["", f"# {topic['title']}", ""]
    if topic["summary"]:
        out += [topic["summary"], ""]
    if topic["sources"]:
        label = topic["badge"] or "ソース"
        out.append(f"> [!quote]- {label}")
        for s in topic["sources"]:
            out.append(f"> - [{s['title']}]({s['url']}) — `{s['domain']}`")
        out.append("")

    out += ["---", "", f"索引: [[{MOC_NAME}]]"]
    if entities:
        out.append("登場: " + " · ".join(f"[[{e}]]" for e in entities))
    out.append("")
    return "\n".join(out)


def build_moc(by_category, latest_date):
    """by_category: {folder: [(date, basename, title, corroborated), ...] newest first}."""
    total = sum(len(v) for v in by_category.values())
    out = [
        "---",
        f"title: {yaml_escape(MOC_NAME)}",
        "type: moc",
        "tags:",
        "  - ai-news",
        "  - moc",
        "---",
        "",
        "# 🗂️ AI News — 索引",
        "",
        "毎朝 08:00 JST に Claude Code が収集・要約したニュース。1トピック=1ノートで、",
        "**カテゴリ別フォルダ**に日付プレフィックス付きで蓄積される。生成元は `news-digest` リポジトリ。",
        "",
    ]

    if not total:
        out += [
            "> [!info] まだノートがない",
            "> 次回の自動実行を待つか、Claude Code で `/ai-news-digest` を実行する。",
            "",
        ]
        return "\n".join(out)

    out += [
        "> [!abstract] 統計",
        f"> トピックノート **{total}件** · 最新の収集日: **{latest_date}**",
        "> " + " / ".join(f"{k} {len(v)}" for k, v in by_category.items()),
        "",
    ]

    for folder, rows in by_category.items():
        out += ["", f"## {folder}", "", "| 日付 | トピック |", "| --- | --- |"]
        for date, basename, title, corroborated in rows:
            mark = " ✅" if corroborated else ""
            out.append(f"| {date} | [[{basename}\\|{title}]]{mark} |")

    out.append("")
    return "\n".join(out)


def write_if_changed(path, content):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            if f.read() == content:
                return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return True


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    os.makedirs(OBSIDIAN_DIR, exist_ok=True)

    dates = sorted(
        f[:-3] for f in os.listdir(DIGESTS_DIR)
        if f.endswith(".md") and DATE_RE.match(f[:-3])
    )

    written = 0
    by_category = {folder: [] for folder, _ in CATEGORIES.values()}
    for date in dates:
        with open(os.path.join(DIGESTS_DIR, f"{date}.md"), encoding="utf-8") as f:
            parsed = parse_digest(f.read())
        if not parsed["date"] or not parsed["sections"]:
            continue  # empty digest — an empty note is worse than no note

        for section in parsed["sections"]:
            folder, _ = CATEGORIES.get(section["heading"], FALLBACK_CATEGORY)
            cat_dir = os.path.join(OBSIDIAN_DIR, folder)
            os.makedirs(cat_dir, exist_ok=True)
            for topic in section["topics"]:
                basename = note_basename(date, topic["title"])
                by_category.setdefault(folder, []).append(
                    (date, basename,
                     topic["title"], "裏取り" in topic["badge"])
                )
                if only and date != only:
                    continue
                note = build_topic_note(date, section["heading"], topic)
                if write_if_changed(os.path.join(cat_dir, basename + ".md"), note):
                    written += 1

    latest = max((r[0] for rows in by_category.values() for r in rows), default="")
    for rows in by_category.values():
        rows.sort(reverse=True)
    by_category = {k: v for k, v in by_category.items() if v}
    write_if_changed(
        os.path.join(OBSIDIAN_DIR, f"{MOC_NAME}.md"),
        build_moc(by_category, latest),
    )

    total = sum(len(v) for v in by_category.values())
    # stdout, not stderr: the PowerShell wrapper runs with ErrorAction=Stop,
    # which promotes any stderr line from a native command into a failure.
    print(f"Obsidian export: {written} note(s) written, {total} topic note(s) total.")


if __name__ == "__main__":
    main()
