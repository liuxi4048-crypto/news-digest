import base64
import feedparser
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from groq import Groq

JST = timezone(timedelta(hours=9))

RSS_FEEDS = [
    "https://gigazine.net/news/rss_2.0/",
    "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml",
    "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml",
    "https://pc.watch.impress.co.jp/data/rss/1.0/pcw/feed.rdf",
    "https://news.mynavi.jp/rss/index.xml",
]

def fetch_articles(hours=36):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            source = feed.feed.get("title", url)
            for entry in feed.entries[:15]:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    except Exception:
                        pass
                if published is None or published >= cutoff:
                    articles.append({
                        "title": entry.get("title", "").strip(),
                        "link": entry.get("link", ""),
                        "summary": entry.get("summary", "")[:300].strip(),
                        "source": source,
                    })
        except Exception as e:
            print(f"Feed error {url}: {e}", file=sys.stderr)
    return articles

def generate_digest():
    today = datetime.now(JST)
    today_str = today.strftime("%Y年%m月%d日")
    today_iso = today.strftime("%Y-%m-%d")

    articles = fetch_articles()
    if not articles:
        raise RuntimeError("No articles fetched from RSS feeds")

    articles_text = "\n\n".join(
        f"[{a['source']}]\nタイトル: {a['title']}\nURL: {a['link']}\n概要: {a['summary']}"
        for a in articles[:40]
    )

    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    prompt = f"""以下は本日（{today_str}）取得した日本のテクノロジーニュース記事の一覧です。

{articles_text}

これらから各カテゴリ3〜5件を選んで以下の完全なHTMLドキュメントを出力してください。HTMLのみを出力し、マークダウンのコードブロックは絶対に使わないでください。

<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI・ITニュースダイジェスト - {today_str}</title>
<style>
body{{font-family:'Helvetica Neue',Arial,sans-serif;max-width:800px;margin:0 auto;padding:20px;background:#f5f5f5;color:#333}}
h1{{color:#1a1a2e;border-bottom:3px solid #e94560;padding-bottom:10px}}
h2{{color:#16213e;margin-top:30px}}
.article{{background:white;padding:15px 20px;margin:10px 0;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,.1)}}
.article h3{{margin:0 0 8px 0;font-size:1em}}
.article h3 a{{color:#e94560;text-decoration:none}}
.article p{{margin:0;font-size:.9em;line-height:1.6}}
.date{{color:#666;font-size:.85em}}
footer{{margin-top:40px;padding-top:20px;border-top:1px solid #ddd;font-size:.8em;color:#666}}
</style>
</head>
<body>
<h1>📰 Daily Digest — {today_str} 09:00 JST</h1>
<p class="date">自動生成 by AI（Llama, Meta）| 著作権は各メディア・原著作者に帰属</p>

<h2>🤖 AI</h2>

（生成AI・LLM・AIサービス関連を3〜5件）

<h2>💻 IT/PC</h2>

（クラウド・セキュリティ・PC・ソフトウェア関連を3〜5件）

<h2>📱 スマホ・ツール</h2>

（スマートフォン・アプリ・ガジェット関連を3〜5件）

<footer>
<p>このサイトはGitHub Actionsにより毎日09:00 JSTに自動更新されます。</p>
<p>要約はAI（Llama, Meta）が自動生成。著作権は各メディア・原著作者に帰属。情報提供目的のみ。</p>
</footer>
</body>
</html>

各記事は以下の形式で出力:
<div class="article">
<h3><a href="[元記事のURL]" target="_blank">[記事タイトル]</a></h3>
<p>[3〜5行の日本語要約]</p>
</div>"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=8000,
    )
    html = response.choices[0].message.content
    if "<!DOCTYPE" in html:
        start = html.index("<!DOCTYPE")
        end = html.rindex("</html>") + 7
        html = html[start:end]
    return html, today_iso

def api_call(path, method="GET", data=None):
    headers = {
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    url = f"https://api.github.com{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 422:
            return {"error": "conflict"}
        raise

def main():
    repo = os.environ.get("GITHUB_REPOSITORY", "liuxi4048-crypto/news-digest")
    html, today_iso = generate_digest()

    current = api_call(f"/repos/{repo}/contents/index.html")
    current_sha = current["sha"]
    current_content_b64 = current["content"].replace("\n", "")

    yesterday = (datetime.now(JST) - timedelta(days=1)).strftime("%Y-%m-%d")
    result = api_call(f"/repos/{repo}/contents/archive/{yesterday}.html", "PUT", {
        "message": f"Archive {yesterday} digest",
        "content": current_content_b64,
        "branch": "main",
    })
    if result.get("error") == "conflict":
        print(f"Archive {yesterday} already exists, skipping", file=sys.stderr)

    new_b64 = base64.b64encode(html.encode("utf-8")).decode("ascii")
    api_call(f"/repos/{repo}/contents/index.html", "PUT", {
        "message": f"Update digest {today_iso}",
        "content": new_b64,
        "sha": current_sha,
        "branch": "main",
    })
    print(f"Done: {today_iso}", file=sys.stderr)

if __name__ == "__main__":
    main()
