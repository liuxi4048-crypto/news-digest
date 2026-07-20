"""
Convert generated digests into Obsidian-native notes.

Reads `digests/*.md` (produced by generate_digest.py) and writes
`obsidian/AI News/<date>.md` plus an `_AI News MOC.md` index. Output uses YAML
frontmatter, Obsidian callouts, and `[[wikilinks]]` so the notes participate in
search, graph view, and Dataview queries rather than sitting there as inert text.

Pure stdlib and idempotent: safe to re-run over the whole history at any time.
No API keys required, so this also runs fine on a laptop with no secrets.

Usage:
    python scripts/export_obsidian.py            # all digests
    python scripts/export_obsidian.py 2026-07-20 # a single date
"""
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

CATEGORY_TAGS = {
    "🤖 AI": "ai",
    "☁️ SaaS・ツール": "saas",
    "💻 IT全般": "it",
}


def parse_digest(text):
    """Parse a digest markdown file into a structured dict."""
    result = {
        "date": None, "incomplete": False, "counts_line": "",
        "corroboration_line": "", "sections": [],
    }

    m = re.search(r"^# Daily Digest — (\d{4}-\d{2}-\d{2})", text, re.M)
    if m:
        result["date"] = m.group(1)
    result["incomplete"] = "収集は不完全" in text

    m = re.search(r"^掲載トピック数: .*$", text, re.M)
    if m:
        result["counts_line"] = m.group(0)
    m = re.search(r"^うち\d+件は.*$", text, re.M)
    if m:
        result["corroboration_line"] = m.group(0)

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


def parse_counts(counts_line):
    """Pull (total, ai, saas, it) out of the counts line; zeros if unparsable."""
    m = re.search(
        r"(\d+)件（AI: (\d+) / SaaS・ツール: (\d+) / IT全般: (\d+)）", counts_line
    )
    return tuple(int(g) for g in m.groups()) if m else (0, 0, 0, 0)


def build_note(parsed, prev_date, next_date):
    date = parsed["date"]
    total, ai_n, saas_n, it_n = parse_counts(parsed["counts_line"])
    corroborated = 0
    m = re.search(r"うち(\d+)件", parsed["corroboration_line"])
    if m:
        corroborated = int(m.group(1))

    all_text = " ".join(
        t["title"] + " " + t["summary"]
        for s in parsed["sections"] for t in s["topics"]
    )
    entities = find_entities(all_text)

    fm = [
        "---",
        f"title: {yaml_escape('AI News — ' + date)}",
        f"date: {date}",
        "type: news-digest",
        "source: news-digest",
        "tags:",
        "  - ai-news",
        "  - daily-digest",
        f"topics: {total}",
        f"ai_topics: {ai_n}",
        f"corroborated: {corroborated}",
    ]
    if entities:
        fm.append("entities:")
        fm.extend(f"  - {yaml_escape(e)}" for e in entities)
    fm.append("---")

    out = fm + ["", f"# 🤖 AI News — {date}", ""]

    if parsed["incomplete"]:
        out += [
            "> [!warning] 収集が不完全",
            f"> {date} は取得できたトピックが少なく、通常より内容が薄い。",
            "",
        ]

    out += [
        "> [!abstract] サマリー",
        f"> **{total}件** — AI {ai_n} / SaaS {saas_n} / IT {it_n}",
        f"> 独立した複数ドメインで裏取り済み: **{corroborated}件**",
        "",
    ]

    for section in parsed["sections"]:
        tag = CATEGORY_TAGS.get(section["heading"], "misc")
        out += [f"## {section['heading']}", "", f"#{tag}", ""]
        for i, topic in enumerate(section["topics"], 1):
            out += [f"### {i}. {topic['title']}", ""]
            if topic["summary"]:
                out += [topic["summary"], ""]
            if topic["sources"]:
                label = topic["badge"] or "ソース"
                out.append(f"> [!quote]- {label}")
                for s in topic["sources"]:
                    out.append(f"> - [{s['title']}]({s['url']}) — `{s['domain']}`")
                out.append("")

    out += ["---", "", "## ナビゲーション", "", f"- 索引: [[{MOC_NAME}]]"]
    if prev_date:
        out.append(f"- 前日: [[{prev_date}]]")
    if next_date:
        out.append(f"- 翌日: [[{next_date}]]")

    if entities:
        out += ["", "## 登場エンティティ", ""]
        out.append(" · ".join(f"[[{e}]]" for e in entities))

    out.append("")
    return "\n".join(out)


def build_moc(entries):
    """entries: list of (date, total, ai_n, corroborated), newest first."""
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
        "毎朝 08:00 JST に Claude Code が収集・要約したダイジェスト。",
        "生成元は `news-digest` リポジトリ。",
        "",
    ]

    if not entries:
        out += [
            "> [!info] まだノートがない",
            "> 次回の自動実行を待つか、Claude Code で `/ai-news-digest` を実行する。",
            "",
        ]
        return "\n".join(out)

    total_topics = sum(e[1] for e in entries)
    out += [
        "> [!abstract] 統計",
        f"> ノート **{len(entries)}件** · 収録トピック **{total_topics}件**",
        f"> 最新: [[{entries[0][0]}]]",
        "",
    ]

    current_month = None
    for date, total, ai_n, corroborated in entries:
        month = date[:7]
        if month != current_month:
            out += ["", f"## {month}", "", "| 日付 | 件数 | AI | 裏取り |", "| --- | --- | --- | --- |"]
            current_month = month
        out.append(f"| [[{date}]] | {total} | {ai_n} | {corroborated} |")

    out.append("")
    return "\n".join(out)


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    os.makedirs(OBSIDIAN_DIR, exist_ok=True)

    dates = sorted(
        f[:-3] for f in os.listdir(DIGESTS_DIR)
        if f.endswith(".md") and DATE_RE.match(f[:-3])
    )

    parsed_by_date = {}
    for date in dates:
        with open(os.path.join(DIGESTS_DIR, f"{date}.md"), encoding="utf-8") as f:
            parsed = parse_digest(f.read())
        if not parsed["date"] or not parsed["sections"]:
            continue  # empty digest — an empty note is worse than no note
        parsed_by_date[date] = parsed

    usable = sorted(parsed_by_date)
    written = 0
    for i, date in enumerate(usable):
        if only and date != only:
            continue
        prev_date = usable[i - 1] if i > 0 else None
        next_date = usable[i + 1] if i + 1 < len(usable) else None
        note = build_note(parsed_by_date[date], prev_date, next_date)
        path = os.path.join(OBSIDIAN_DIR, f"{date}.md")
        # Skip untouched files so the vault's git history stays meaningful.
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                if f.read() == note:
                    continue
        with open(path, "w", encoding="utf-8") as f:
            f.write(note)
        written += 1

    entries = []
    for date in reversed(usable):
        p = parsed_by_date[date]
        total, ai_n, _, _ = parse_counts(p["counts_line"])
        m = re.search(r"うち(\d+)件", p["corroboration_line"])
        entries.append((date, total, ai_n, int(m.group(1)) if m else 0))

    with open(os.path.join(OBSIDIAN_DIR, f"{MOC_NAME}.md"), "w", encoding="utf-8") as f:
        f.write(build_moc(entries))

    skipped = len(dates) - len(usable)
    print(
        f"Obsidian export: {written} note(s) written, {len(usable)} total, "
        f"{skipped} empty digest(s) skipped.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
