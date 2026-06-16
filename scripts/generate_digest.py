import anthropic
import base64
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

def search_news(client, query):
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
        messages=[{"role": "user", "content": f"Search for latest news: {query}. Date: {datetime.now(JST).strftime('%Y-%m-%d')}"}]
    )
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    return ""

def generate_digest():
    today = datetime.now(JST)
    today_str = today.strftime("%Y年%m月%d日")
    today_iso = today.strftime("%Y-%m-%d")
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    ai_news = search_news(client, f"生成AI LLM AI新製品 最新ニュース {today_iso}")
    it_news = search_news(client, f"テクノロジー クラウド セキュリティ 最新 {today_iso}")
    sp_news = search_news(client, f"スマートフォン アプリ 便利ツール 新機能 {today_iso}")

    prompt = f"""今日（{today_str}）のニュースダイジェストを作成してください。

AI関連ニュース:
{ai_news}

IT/PCニュース:
{it_news}

スマホ・ツールニュース:
{sp_news}

以下の完全なHTMLドキュメントを出力してください:

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
<p class="date">自動生成 by AI（Claude, Anthropic Inc.）| 著作権は各メディア・原著作者に帰属</p>
<h2>🤖 AI</h2>
[各3〜5件の記事を div.article 形式で]
<h2>💻 IT/PC</h2>
[各3〜5件の記事を div.article 形式で]
<h2>📱 スマホ・ツール</h2>
[各3〜5件の記事を div.article 形式で]
<footer>
<p>このサイトはGitHub Actionsにより毎日09:00 JSTに自動更新されます。</p>
<p>要約はAI（Claude, Anthropic Inc.）が自動生成。著作権は各メディア・原著作者に帰属。情報提供目的のみ。</p>
</footer>
</body>
</html>

各記事は以下の形式で出力:
<div class="article">
  <h3><a href="[URL]" target="_blank">[タイトル]</a></h3>
  <p>[3〜5行の日本語要約]</p>
</div>"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}]
    )
    html = response.content[0].text
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
        "Content-Type": "application/json"
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
        "branch": "main"
    })
    if result.get("error") == "conflict":
        print(f"Archive {yesterday} already exists, skipping", file=sys.stderr)

    new_b64 = base64.b64encode(html.encode("utf-8")).decode("ascii")
    api_call(f"/repos/{repo}/contents/index.html", "PUT", {
        "message": f"Update digest {today_iso}",
        "content": new_b64,
        "sha": current_sha,
        "branch": "main"
    })
    print(f"Done: {today_iso}", file=sys.stderr)

if __name__ == "__main__":
    main()